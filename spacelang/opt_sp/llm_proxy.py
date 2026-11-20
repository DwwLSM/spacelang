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


def _previous_assembly(py_src: str) -> str | None:
    """The assembly the stale mirror compiles to, if it still compiles."""
    try:
        result = convert(py_src, "py")
    except Exception:
        return None
    if not result.get("ok"):
        return None
    return result["texts"].get("spasm")


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

    report = verify_py(answer["content"], spasm_src)
    if not report["ok"]:
        raise LLMError(
            "not_equivalent",
            "the rewritten mirror does not compile to the same program",
            details={
                "want_len": report.get("want_len"),
                "got_len": report.get("got_len"),
                "first": report.get("first"),
            },
        )

    return {
        "ok": True,
        "py": answer["content"],
        "verified": True,
        "model": answer["model"],
        "usage": answer["usage"],
    }


def status(config: LLMConfig, cli: "LLMConfig | Mapping[str, Any] | None" = None) -> dict[str, Any]:
    return {
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
    "is_loopback",
    "key_source",
    "refine_py",
    "resolve_config",
    "status",
]
