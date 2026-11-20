"""Configuration, prompting and rate limiting for the AI mirror sync.

The model's only job is to rewrite the readable Python mirror so that it
compiles to the same program as the current assembly. Everything the model
returns is verified locally before it is shown as an answer; a mismatch is an
error, never a success.
"""

from __future__ import annotations

import difflib
import ipaddress
import os
import re
import threading
import time
from dataclasses import dataclass, fields, replace
from pathlib import Path
from typing import Any, Mapping

from ..llm_client import LLMError, chat
from ..web_bridge import convert, verify_py

DEFAULT_BASE_URL = "https://socratic.cs.cityu.edu.hk/litellm/v1"
DEFAULT_MODEL = "Socrates"
MAX_INPUT_CHARS = 12_000
MODES = ("manual", "auto", "off")
DOTENV_FILES = (".env.local", ".env")

HEADER_BASE_URL = "X-LLM-Base-URL"
HEADER_MODEL = "X-LLM-Model"
HEADER_KEY = "X-LLM-Key"
HEADER_MODE = "X-LLM-Mode"


@dataclass(frozen=True)
class LLMConfig:
    base_url: str = DEFAULT_BASE_URL
    model: str = DEFAULT_MODEL
    api_key: str | None = None
    mode: str = "manual"
    max_output_tokens: int = 4096
    temperature: float = 0.2
    timeout: float = 90.0
    rate_limit_rpm: int = 40
    rate_limit_burst: int = 4
    disable_thinking: bool = True

    def merged(self, overrides: "LLMConfig | Mapping[str, Any] | None") -> "LLMConfig":
        """Return a copy with every non-None override applied."""
        if overrides is None:
            return self
        if isinstance(overrides, LLMConfig):
            values = {field.name: getattr(overrides, field.name) for field in fields(self)}
            # A dataclass always carries values, so treat its defaults as "unset"
            # only for the fields the caller cannot distinguish anyway.
            changes = {
                name: value
                for name, value in values.items()
                if value is not None and value != getattr(LLMConfig(), name)
            }
            return replace(self, **changes) if changes else self
        changes = {
            field.name: overrides[field.name]
            for field in fields(self)
            if field.name in overrides and overrides[field.name] is not None
        }
        return replace(self, **changes) if changes else self

    def normalised(self) -> "LLMConfig":
        mode = self.mode if self.mode in MODES else "manual"
        base_url = (self.base_url or "").strip()
        if base_url and not base_url.split("://", 1)[0] in ("http", "https"):
            raise LLMError("bad_config", "base URL must be http:// or https://")
        return replace(
            self,
            mode=mode,
            base_url=base_url.rstrip("/"),
            model=(self.model or DEFAULT_MODEL).strip(),
            api_key=(self.api_key or None),
            max_output_tokens=max(256, int(self.max_output_tokens)),
            rate_limit_rpm=max(1, int(self.rate_limit_rpm)),
            rate_limit_burst=max(1, int(self.rate_limit_burst)),
        )


def _read_dotenv(root: Path | None = None) -> dict[str, str]:
    """Read KEY=VALUE pairs from .env.local/.env without overriding os.environ."""
    root = root or Path.cwd()
    values: dict[str, str] = {}
    for name in DOTENV_FILES:
        try:
            text = (root / name).read_text(encoding="utf-8")
        except OSError:
            continue
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in values:
                values[key] = value
    return values


def _env(name: str, dotenv: Mapping[str, str], default: str | None = None) -> str | None:
    return os.environ.get(name) or dotenv.get(name) or default


def resolve_config(
    cli: "LLMConfig | Mapping[str, Any] | None" = None,
    headers: Mapping[str, str] | None = None,
) -> LLMConfig:
    """defaults < environment/.env < CLI < per-request headers."""
    dotenv = _read_dotenv()
    config = LLMConfig(
        base_url=_env("LITELLM_BASE_URL", dotenv, DEFAULT_BASE_URL) or DEFAULT_BASE_URL,
        model=_env("LITELLM_MODEL", dotenv, DEFAULT_MODEL) or DEFAULT_MODEL,
        api_key=_env("LITELLM_API_KEY", dotenv),
        mode=_env("LITELLM_MODE", dotenv, "manual") or "manual",
    ).normalised()
    config = config.merged(cli).normalised()
    if headers:
        overrides = {
            "base_url": headers.get(HEADER_BASE_URL),
            "model": headers.get(HEADER_MODEL),
            "api_key": headers.get(HEADER_KEY),
            "mode": headers.get(HEADER_MODE),
        }
        config = config.merged(overrides).normalised()
    return config


def key_source(config: LLMConfig, cli: "LLMConfig | Mapping[str, Any] | None" = None) -> str:
    """Where the effective key came from; used by the status endpoint only."""
    if not config.api_key:
        return "none"
    cli_key = None
    if isinstance(cli, LLMConfig):
        cli_key = cli.api_key
    elif isinstance(cli, Mapping):
        cli_key = cli.get("api_key")
    if cli_key:
        return "cli"
    dotenv = _read_dotenv()
    if os.environ.get("LITELLM_API_KEY") or dotenv.get("LITELLM_API_KEY"):
        return "env"
    return "config"


SYSTEM_PROMPT = (
    "You update a Python file to match a changed SpaceLang program. You are given "
    "the current Python and a unified diff of the compiler's assembly output. Apply "
    "the change, keep everything else exactly as it is, and reply with Python only: "
    "no prose, no Markdown fences."
)

SYSTEM_PROMPT_FULL = (
    "You are the Python mirror maintainer for SpaceLang. The assembly listing is the "
    "authoritative form of the program and the Python file is a readable mirror of it. "
    "Rewrite the mirror so that compiling it produces exactly the same program, keeping "
    "existing names and structure. Reply with Python only: no prose, no Markdown fences."
)

_ANNOTATION = re.compile(r"\s*; line=\d+ spaces=[0-9,]*$")
_FENCE = re.compile(r"^\s*```[A-Za-z0-9_+-]*[ \t]*\r?\n(.*?)\r?\n\s*```\s*$", re.DOTALL)
_MAX_DIFF_CHARS = 6000

# Mirrors spacelang/pyfront.py (BinOp.op_map) and csrc/vm.cpp (try_numeric_binary_fast).
# The assembly only carries the number, so the model needs the legend to know
# that "OP 2" is a subtraction rather than a guess.
BINARY_OPERATORS = {
    1: "+",
    2: "-",
    3: "*",
    4: "/",
    5: "%",
    6: "==",
    7: "<",
    8: ">",
    9: "!=",
    10: "<=",
    11: ">=",
    16: "//",
    17: "**",
}


def operator_legend(spasm_src: str, previous_asm: str = "") -> str:
    """Explain every operator code in the listing, and in the removed side."""
    codes = sorted({
        int(code)
        for text in (spasm_src, previous_asm)
        for code in re.findall(r"^OP (\d+)", text, re.MULTILINE)
    })
    if not codes:
        return ""
    parts = [f"OP {code} = {BINARY_OPERATORS.get(code, 'unknown operator')}" for code in codes]
    return "Operator codes used by this program: " + ", ".join(parts) + ".\n\n"


def _plain_assembly(text: str) -> list[str]:
    return [_ANNOTATION.sub("", line) for line in text.split("\n")]


def assembly_diff(previous_asm: str, current_asm: str) -> str | None:
    """Unified diff of the two listings, or None when it would not be a shortcut."""
    diff = "\n".join(
        difflib.unified_diff(
            _plain_assembly(previous_asm),
            _plain_assembly(current_asm),
            "previous",
            "current",
            lineterm="",
            n=3,
        )
    )
    if not diff.strip() or len(diff) > _MAX_DIFF_CHARS:
        return None
    return diff


def _unwrap_fences(text: str) -> str:
    """Drop a Markdown code fence if the model wrapped the file in one."""
    match = _FENCE.match(text)
    return match.group(1) if match else text


def _previous_assembly(py_src: str) -> str | None:
    """The assembly the stale mirror compiles to, if it still compiles."""
    try:
        result = convert(py_src, "py")
    except Exception:
        return None
    if not result.get("ok"):
        return None
    return result["texts"].get("spasm")


def _diff_is_large(diff: str, listing: str) -> bool:
    """True when the change rewrites most of the listing."""
    changed = sum(
        1
        for line in diff.split("\n")
        if line[:1] in "+-" and not line.startswith(("+++", "---"))
    )
    total = max(1, len([line for line in listing.split("\n") if line.strip()]))
    return changed > 0.4 * total


def build_messages(py_src: str, spasm_src: str) -> list[dict[str, str]]:
    if len(py_src) + len(spasm_src) > MAX_INPUT_CHARS:
        raise LLMError(
            "input_too_large",
            f"the program is larger than {MAX_INPUT_CHARS} characters",
        )

    previous = _previous_assembly(py_src)
    diff = assembly_diff(previous, spasm_src) if previous else None
    legend = operator_legend(spasm_src, previous or "")
    if diff:
        scale = ""
        if _diff_is_large(diff, spasm_src):
            scale = (
                "\nThis is a large change. Output the complete module: the "
                "module-level constants first, then every function, in the order "
                "the assembly gives them.\n"
            )
        user = (
            "## Current Python\n"
            "```python\n"
            f"{py_src}\n"
            "```\n\n"
            f"{legend}"
            "## Change in the program (assembly diff)\n"
            "```diff\n"
            f"{diff}\n"
            "```\n\n"
            "## Task\n"
            "Apply this change to the Python and output the whole file.\n"
            f"{scale}"
        )
        return [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user},
        ]

    user = (
        "## Current Python mirror\n"
        "```python\n"
        f"{py_src}\n"
        "```\n\n"
        f"{legend}"
        "## Current program (assembly)\n"
        f"{spasm_src}\n\n"
        "## Task\n"
        "Produce a Python mirror that compiles to exactly this program.\n"
    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT_FULL},
        {"role": "user", "content": user},
    ]


class TokenBucket:
    """Process-wide request budget; shared by every browser session."""

    def __init__(self, per_minute: int = 40, burst: int = 4) -> None:
        self.capacity = max(1, int(burst))
        self.rate = max(1, int(per_minute)) / 60.0
        self._tokens = float(self.capacity)
        self._updated = time.monotonic()
        self._lock = threading.Lock()

    def take(self) -> float | None:
        """Consume one token; return None, or the seconds to wait."""
        with self._lock:
            now = time.monotonic()
            self._tokens = min(
                float(self.capacity),
                self._tokens + (now - self._updated) * self.rate,
            )
            self._updated = now
            if self._tokens >= 1.0:
                self._tokens -= 1.0
                return None
            return (1.0 - self._tokens) / self.rate


class Gate:
    """One model call at a time; a short wait instead of an unbounded queue."""

    def __init__(self, wait_seconds: float = 20.0) -> None:
        self._lock = threading.Lock()
        self.wait_seconds = wait_seconds

    def __enter__(self) -> "Gate":
        if not self._lock.acquire(timeout=self.wait_seconds):
            raise LLMError("busy", "another sync is already running", retry_after=2)
        return self

    def __exit__(self, *exc_info: object) -> None:
        self._lock.release()


def is_loopback(address: str) -> bool:
    try:
        return ipaddress.ip_address(address).is_loopback
    except ValueError:
        return False


def refine_py(
    config: LLMConfig,
    py_src: str,
    spasm_src: str,
    *,
    bucket: TokenBucket,
    gate: Gate,
) -> dict[str, Any]:
    """Ask the model for a new mirror and verify it before returning anything."""
    if not config.api_key:
        raise LLMError("no_key", "no API key is configured")
    messages = build_messages(py_src, spasm_src)

    wait = bucket.take()
    if wait is not None:
        raise LLMError(
            "rate_limited",
            "the shared request budget is exhausted",
            retry_after=round(wait, 1),
        )

    with gate:
        answer = chat(
            config.base_url,
            config.api_key,
            config.model,
            messages,
            max_tokens=config.max_output_tokens,
            temperature=config.temperature,
            timeout=config.timeout,
            disable_thinking=config.disable_thinking,
        )

    content = _unwrap_fences(answer["content"])
    report = verify_py(content, spasm_src)
    if not report["ok"]:
        # Report the real reason: an answer that does not compile is a different
        # failure from one that compiles to another program.
        code = report.get("error") or "not_equivalent"
        detail_lines = [
            line for line in (report.get("detail") or "").strip().splitlines() if line.strip()
        ]
        previous = _previous_assembly(py_src)
        diff = assembly_diff(previous, spasm_src) if previous else None
        raise LLMError(
            code,
            detail_lines[-1] if detail_lines else "the rewritten mirror was rejected",
            details={
                "want_len": report.get("want_len"),
                "got_len": report.get("got_len"),
                "first": report.get("first"),
                "large_change": bool(diff and _diff_is_large(diff, spasm_src)),
            },
        )

    return {
        "ok": True,
        "py": content,
        "verified": True,
        "model": answer["model"],
        "usage": answer["usage"],
    }


# --- assistant chat -------------------------------------------------------
#
# The system prompt is chosen by the server from the page name, never sent by
# the browser: the page decides what the assistant is for, and a caller cannot
# swap the persona for something else.

CHAT_PAGES = ("home", "editor", "studio", "visualize", "docs", "tutorial")
MAX_CHAT_MESSAGES = 24
MAX_CHAT_MESSAGE_CHARS = 4_000
MAX_CHAT_CHARS = 24_000

_CHAT_INSTRUCTIONS = (
    "Assembly mnemonics you may use, with their operands: "
    "PUSH_INT <int>; PUSH_STR <len> <codepoints...>; PUSH_NONE; "
    "LOAD_GLOBAL <name_id>; STORE_GLOBAL <name_id>; LOAD_LOCAL <slot>; "
    "STORE_LOCAL <slot>; LOAD_ARG <index>; "
    "OP <code> (1 = +, 2 = -, 3 = *, 4 = /, 5 = %, 6 = ==, 7 = <, 8 = >, "
    "9 = !=, 10 = <=, 11 = >=, 16 = //, 17 = **); STACK <code>; "
    "CALL <func_id> <nargs>; CALL_METHOD <name_id> <nargs>; DEF <func_id> <nargs>; "
    "GET_ATTR <name_id>; BUILD_LIST <count>; JMP <target>; JZ <target>; JNZ <target>; "
    "RET; HALT. Use only these; if a program needs one you are unsure of, say so "
    "instead of inventing it."
)

_CHAT_COMMON = (
    "SpaceLang is a small language whose source file is .sp: token values encoded "
    "as runs of spaces and newlines. A Python subset is an optional surface syntax "
    "that lowers to .sp, and assembly is a readable view of the same program, not a "
    "separate language. The project's own README and documentation are appended to "
    "this prompt; treat them as authoritative, quote them when they answer the "
    "question, and say so when they do not cover it. You cannot run the program, read "
    "files, or edit anything, so never claim to have done so. Answer with explanations "
    "and short examples. When you show a SpaceLang program, write it as assembly in a "
    "```spasm block: that is the readable form of the language. Keep the listing "
    "complete (it ends with HALT or RET), because the server compiles it to produce "
    "the encoded form. The encoded .sp form is generated that way and appears under "
    "your listing automatically, so never write runs of spaces yourself and never say "
    "you cannot produce it: the compiler produced it. Show the Python subset only when "
    "the user asks for it, or as a short note "
    "after the assembly. " + _CHAT_INSTRUCTIONS + " Keep replies short and concrete."
)

CHAT_SYSTEM_PROMPTS = {
    "home": (
        "You are the SpaceLang assistant on the debugger's home page. " + _CHAT_COMMON +
        " The pages are: /editor (write one representation, run it, see the trace), "
        "/studio (Python, assembly and encoded .sp side by side), /visualizer (trace "
        "only), /docs (the project documentation) and /tutorial (a five-minute tour). "
        "Help the visitor pick a starting point and understand what .sp is."
    ),
    "editor": (
        "You are the SpaceLang assistant inside the editor. The user is writing one "
        "representation at a time: assembly (.spasm), the Python subset (.py) or the "
        "encoded .sp form. " + _CHAT_COMMON +
        " Useful facts: the stack machine runs PUSH_INT, PUSH_STR, OP <code> "
        "(1 = +, 2 = -, 3 = *, 4 = /, 16 = //, 17 = **), CALL, RET and HALT; the "
        "operand stack is shown in the trace, so a wrong result is usually a wrong "
        "push order or a wrong OP code. Encoded source is only spaces: it is not meant "
        "to be read by eye."
    ),
    "studio": (
        "You are the SpaceLang assistant inside the Studio, where Python, assembly and "
        "encoded .sp are shown for the same program. " + _CHAT_COMMON +
        " The Python pane is a mirror: editing the assembly or the encoded form marks "
        "it stale, and nothing in the toolchain turns a program back into Python. The "
        "mirror is rewritten by a model and accepted only when the rewritten Python "
        "compiles to the same instructions as the assembly, so help the user judge "
        "whether a mirror is right rather than promising a rewrite."
    ),
    "visualize": (
        "You are the SpaceLang assistant on the visualizer page, which replays a "
        "recorded trace. " + _CHAT_COMMON +
        " The panels show the instruction about to run, the operand stack, the call "
        "stack, the heap and object graph, and whatever the program printed. Stepping "
        "is done with the first/back/forward/last buttons, the slider, or the arrow "
        "keys. Explain what a single step did and why a value is on the stack, and say "
        "which instruction to look at next."
    ),
    "docs": (
        "You are the SpaceLang assistant on the documentation page, which is the "
        "rendered documentation.md. " + _CHAT_COMMON +
        " It covers installation, the Python subset, the assembly syntax, the "
        "instruction set, the .sp file format, optimisation, the Python and native VMs, "
        "the CLI, the Python API and the OPT_SP debugger. Point at the section that "
        "answers the question and explain the term; say so when something is not "
        "covered instead of guessing at a flag or an export."
    ),
    "tutorial": (
        "You are the SpaceLang assistant on the tutorial page, a five-minute tour: "
        "write a listing, read the trace, see the encoded form, change the low level "
        "and keep the mirror, then run without Python. " + _CHAT_COMMON +
        " Answer for the step the reader is on, and say what to try next."
    ),
}


def chat_system_prompt(page: str) -> str:
    """The prompt for a page, falling back to the home page's."""
    return CHAT_SYSTEM_PROMPTS.get(page, CHAT_SYSTEM_PROMPTS["home"])


# The assistant is only as good as the material it is given: asked for `1 + 1` in
# assembly it invented `push`/`add`, and asked about the encoded form it guessed
# at the token table. Both are in the project's own Markdown, so the conversation
# carries it. Read once per file change, capped so a huge document cannot grow
# every request without bound.
PROJECT_DOCUMENTS = ("README.md", "readme.md", "documentation.md")
MAX_PROJECT_DOC_CHARS = 80_000
_project_docs_cache: tuple[tuple[tuple[str, int, int], ...], str] | None = None


def project_documents() -> str:
    """README and documentation, or "" when this installation has neither."""
    global _project_docs_cache

    here = Path(__file__).resolve()
    roots = (here.parents[2], here.parent, here.parent / "static")
    found: list[Path] = []
    seen: set[str] = set()
    for name in PROJECT_DOCUMENTS:
        for root in roots:
            path = root / name
            if not path.is_file() or str(path) in seen:
                continue
            seen.add(str(path))
            found.append(path)
            break
    if not found:
        return ""
    try:
        key = tuple((str(path), path.stat().st_mtime_ns, path.stat().st_size) for path in found)
    except OSError:
        return ""
    if _project_docs_cache is not None and _project_docs_cache[0] == key:
        return _project_docs_cache[1]

    parts: list[str] = []
    for path in found:
        try:
            parts.append(f"### {path.name}\n\n{path.read_text(encoding='utf-8')}")
        except (OSError, UnicodeError):
            continue
    text = "\n\n".join(parts)
    if len(text) > MAX_PROJECT_DOC_CHARS:
        text = text[:MAX_PROJECT_DOC_CHARS] + "\n\n[documentation truncated]"
    _project_docs_cache = (key, text)
    return text


def chat_prompt_with_documents(page: str) -> str:
    prompt = chat_system_prompt(page)
    documents = project_documents()
    if not documents:
        return prompt
    return (
        prompt
        + "\n\n## Project README and documentation (authoritative)\n\n"
        + documents
    )


_CHAT_FENCE = re.compile(r"```([A-Za-z0-9_+.-]*)[ \t]*\r?\n(.*?)\r?\n?```", re.DOTALL)
_SP_BLOCK = re.compile(r"\n*```sp[ \t]*\r?\n.*?\r?\n?```", re.DOTALL)
_MNEMONIC = re.compile(r"^[A-Z][A-Z_0-9]*(?:\s|$)")

# A fence the model forgot to label still counts as assembly when its first line
# starts with a mnemonic; anything else (python, diff, output) is left alone.
_ASSEMBLY_LABELS = ("", "spasm", "asm")


def _compile_listing(listing: str) -> str | None:
    first_line = next((line for line in listing.splitlines() if line.strip()), "")
    if not _MNEMONIC.match(first_line.strip()):
        return None
    try:
        result = convert(listing, "spasm")
    except Exception:  # noqa: BLE001 - a bad listing must not lose the answer
        return None
    if not result.get("ok"):
        return None
    return (result.get("texts") or {}).get("sp")


def with_compiled_sp(content: str) -> str:
    """Replace any hand-written ``.sp`` block with one the compiler produced.

    The encoded form is deterministic; a model writing runs of spaces can only
    guess. Its assembly blocks are compiled here instead, and a ``.sp`` block it
    wrote itself is dropped, because a wrong block is worse than none.
    """
    content = _SP_BLOCK.sub("", content)
    pieces: list[str] = []
    cursor = 0
    for match in _CHAT_FENCE.finditer(content):
        pieces.append(content[cursor:match.end()])
        cursor = match.end()
        if match.group(1).strip().lower() not in _ASSEMBLY_LABELS:
            continue
        encoded = _compile_listing(match.group(2))
        if encoded:
            pieces.append("\n\n```sp\n" + encoded.strip("\n") + "\n```")
    pieces.append(content[cursor:])
    return "".join(pieces)


def normalise_chat_history(messages: Any) -> list[dict[str, str]]:
    """Validate the browser's transcript; raise LLMError when it is unusable."""
    if not isinstance(messages, list) or not messages:
        raise LLMError("bad_history", "a list of messages is required")
    if len(messages) > MAX_CHAT_MESSAGES:
        raise LLMError(
            "input_too_large",
            f"the conversation is longer than {MAX_CHAT_MESSAGES} messages",
        )
    cleaned: list[dict[str, str]] = []
    for message in messages:
        if not isinstance(message, dict):
            raise LLMError("bad_history", "every message must be an object")
        role = message.get("role")
        content = message.get("content")
        if role not in ("user", "assistant") or not isinstance(content, str):
            raise LLMError("bad_history", "messages need a role and text")
        text = content.strip()
        if not text:
            continue
        if len(text) > MAX_CHAT_MESSAGE_CHARS:
            raise LLMError(
                "input_too_large",
                f"a message is longer than {MAX_CHAT_MESSAGE_CHARS} characters",
            )
        cleaned.append({"role": role, "content": text})
    if not cleaned or cleaned[-1]["role"] != "user":
        raise LLMError("bad_history", "the last message must come from the user")
    if sum(len(message["content"]) for message in cleaned) > MAX_CHAT_CHARS:
        raise LLMError(
            "input_too_large",
            f"the conversation is larger than {MAX_CHAT_CHARS} characters",
        )
    return cleaned


def chat_reply(
    config: LLMConfig,
    page: str,
    messages: Any,
    *,
    bucket: TokenBucket,
    gate: Gate,
) -> dict[str, Any]:
    """One assistant turn. Shares the mirror sync's key, budget and gate."""
    if not config.api_key:
        raise LLMError("no_key", "no API key is configured")
    history = normalise_chat_history(messages)
    if page not in CHAT_SYSTEM_PROMPTS:
        page = "home"

    wait = bucket.take()
    if wait is not None:
        raise LLMError(
            "rate_limited",
            "the shared request budget is exhausted",
            retry_after=round(wait, 1),
        )

    with gate:
        answer = chat(
            config.base_url,
            config.api_key,
            config.model,
            [{"role": "system", "content": chat_prompt_with_documents(page)}, *history],
            max_tokens=config.max_output_tokens,
            temperature=config.temperature,
            timeout=config.timeout,
            disable_thinking=config.disable_thinking,
            allow_truncation=True,
        )

    return {
        "ok": True,
        "page": page,
        "reply": {
            "role": "assistant",
            "content": with_compiled_sp(answer["content"].strip()),
        },
        "truncated": bool(answer.get("truncated")),
        "model": answer["model"],
        "usage": answer["usage"],
    }


def status(config: LLMConfig, cli: "LLMConfig | Mapping[str, Any] | None" = None) -> dict[str, Any]:    return {
        "base_url": config.base_url,
        "model": config.model,
        "mode": config.mode,
        "key_present": bool(config.api_key),
        "key_source": key_source(config, cli),
        "limits": {
            "rpm": config.rate_limit_rpm,
            "burst": config.rate_limit_burst,
        },
    }


__all__ = [
    "DEFAULT_BASE_URL",
    "DEFAULT_MODEL",
    "LLMConfig",
    "Gate",
    "TokenBucket",
    "build_messages",
    "chat_reply",
    "chat_system_prompt",
    "normalise_chat_history",
    "is_loopback",
    "key_source",
    "refine_py",
    "resolve_config",
    "status",
]
