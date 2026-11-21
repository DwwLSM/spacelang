from __future__ import annotations

import argparse
import getpass
import hashlib
import html
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import hmac
import ipaddress
import json
import os
from pathlib import Path
import re
import secrets
from socketserver import TCPServer
import stat
import subprocess
import sys
import tempfile
import time
from threading import Thread, Timer
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit
from urllib.request import ProxyHandler, Request, build_opener, urlopen
import webbrowser

from . import markdown_doc
from ._locate import static_dir
from ..llm_client import LLMError
from .llm_proxy import (
    MODES,
    Gate,
    LLMConfig,
    TokenBucket,
    chat_reply,
    is_loopback,
    refine_py,
    resolve_config,
    status as llm_status,
)

_SOURCE_MODES = {".py": "python", ".sp": "sp", ".spasm": "asm"}
_IGNORED_DIRECTORIES = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "__pycache__",
    "node_modules",
    "spacelang_pkg",
    "venv",
}
_MAX_SOURCE_FILE_SIZE = 1024 * 1024
_MAX_LLM_REQUEST = 64 * 1024
_MAX_CHAT_REQUEST = 64 * 1024
_MAX_DRAIN = 1024 * 1024
_LLM_STATUS = {
    "bad_config": 400,
    "bad_history": 400,
    "no_key": 400,
    "input_too_large": 413,
    "rate_limited": 429,
    "busy": 429,
    "not_equivalent": 422,
    "python_unparsable": 422,
    "assembly_unparsable": 400,
    "bad_key": 502,
    "truncated": 502,
    "empty_completion": 502,
    "upstream_error": 502,
}
_PAGES = {
    "/": "home.html",
    "/home": "home.html",
    "/editor": "editor.html",
    "/index.html": "editor.html",
    "/visualizer": "visualize.html",
    "/visualize.html": "visualize.html",
    "/studio": "studio.html",
    "/docs": "docs.html",
    "/tutorial": "tutorial.html",
}
_INCLUDE_RE = re.compile(
    r"[ \t]*<!-- #include (partials/[A-Za-z0-9_\-/]+\.html) -->[ \t]*\r?\n?"
)
_PARTIAL_RE = re.compile(r"partials/[A-Za-z0-9_\-/]+\.html")
_MAX_INCLUDE_PASSES = 2
_BACK_LINK = '<a class="back-link" href="/editor">\u2190 Back to editor</a>'
_NO_BACK_LINK = frozenset({"editor.html", "home.html"})
_PAGE_TITLES = {
    "home.html": "SpaceLang",
    "docs.html": "SpaceLang \u00b7 Documentation",
    "tutorial.html": "SpaceLang \u00b7 Tutorial",
}
_DEFAULT_PAGE_TITLE = "OPT_SP \u2014 SpaceLang Visual Debugger"
_DOCUMENTED_PAGES = frozenset({"docs.html"})
_DOCUMENT = "documentation.md"
_DOCUMENT_MISSING = (
    "<h1>Documentation is unavailable</h1>"
    "<p>This page renders <code>documentation.md</code>, which this installation "
    "does not ship. From a checkout, run <code>python tools/build_static.py</code> "
    "to bake a copy into the served static files.</p>"
)
_DOCUMENT_CACHE: tuple[tuple[str, int, int], tuple[str, str]] | None = None


def _document_path() -> Path | None:
    """Return the Markdown file behind ``/docs``, if this installation has one.

    A checkout keeps the document at the repository root. An installed wheel
    cannot ship the root file, so ``tools/build_static.py`` copies it next to
    the static pages; prefer the checkout copy so an edit never serves a stale
    build.
    """
    candidates = (
        Path(__file__).resolve().parents[2] / _DOCUMENT,
        Path(static_dir()) / _DOCUMENT,
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def _render_documentation() -> tuple[str, str]:
    """Render ``documentation.md`` to ``(body, table of contents)``.

    The result is cached against the file's modification time: the page is
    re-read only when the document changes, so browsing costs one render.
    """
    global _DOCUMENT_CACHE

    path = _document_path()
    if path is None:
        return _DOCUMENT_MISSING, ""
    try:
        stat = path.stat()
        key = (str(path), stat.st_mtime_ns, stat.st_size)
        if _DOCUMENT_CACHE is not None and _DOCUMENT_CACHE[0] == key:
            return _DOCUMENT_CACHE[1]
        source = path.read_text(encoding="utf-8")
    except OSError:
        return _DOCUMENT_MISSING, ""

    body, toc = markdown_doc.render_document(source)
    rendered = (body, markdown_doc.render_toc(toc))
    _DOCUMENT_CACHE = (key, rendered)
    return rendered


class _QuietHandler(SimpleHTTPRequestHandler):
    def __init__(
        self,
        *args,
        project_root: Path,
        project_files_enabled: bool,
        stop_token: str | None,
        llm_config: "LLMConfig | dict | None" = None,
        llm_bucket: TokenBucket | None = None,
        llm_gate: Gate | None = None,
        **kwargs,
    ):
        self.project_root = project_root
        self.project_files_enabled = project_files_enabled
        self.stop_token = stop_token
        self.llm_config = llm_config
        self.llm_bucket = llm_bucket or TokenBucket()
        self.llm_gate = llm_gate or Gate()
        super().__init__(*args, **kwargs)

    def log_message(self, format: str, *args) -> None:
        if os.environ.get("SPACELANG_OPT_SP_VERBOSE") == "1":
            super().log_message(format, *args)

    def end_headers(self) -> None:
        # ES module imports carry no cache-busting query, so a stale js/ or css/
        # file would survive a version bump on the page itself. Revalidate them
        # on every load instead (Last-Modified makes it a cheap 304).
        if urlsplit(self.path).path.startswith(("/js/", "/css/")):
            self.send_header("Cache-Control", "no-cache")
        super().end_headers()

    def do_GET(self) -> None:
        request = urlsplit(self.path)
        if request.path == "/__opt_sp/status":
            self._send_status()
        elif request.path == "/__opt_sp/health":
            self._send_health()
        elif request.path in _PAGES:
            self._send_controlled_page(_PAGES[request.path])
        elif request.path == "/api/files":
            self._send_project_files()
        elif request.path == "/api/file":
            self._send_project_file(parse_qs(request.query).get("path", [""])[0])
        elif request.path == "/api/llm-status":
            self._send_llm_status()
        else:
            super().do_GET()

    def _send_controlled_page(self, filename: str) -> None:
        try:
            body = self._render_page(filename)
        except OSError:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _render_page(self, filename: str) -> bytes:
        """Expand partial includes, then substitute per-page placeholders."""
        root = Path(static_dir())
        text = (root / filename).read_text(encoding="utf-8")
        # Includes first: {{back_link}} lives inside partials/app-header.html.
        for _ in range(_MAX_INCLUDE_PASSES):
            text, replaced = _INCLUDE_RE.subn(
                lambda match: self._read_partial(root, match.group(1)),
                text,
            )
            if not replaced:
                break
        back_link = "" if filename in _NO_BACK_LINK else _BACK_LINK
        text = text.replace("{{back_link}}", back_link)
        text = text.replace(
            "{{page_title}}",
            html.escape(_PAGE_TITLES.get(filename, _DEFAULT_PAGE_TITLE)),
        )
        text = text.replace("__OPT_SP_CONTROL_TOKEN__", self.stop_token or "")
        if filename in _DOCUMENTED_PAGES:
            body, toc = _render_documentation()
            text = text.replace("{{doc_body}}", body)
            text = text.replace("{{doc_toc}}", toc)
        return text.encode("utf-8")

    @staticmethod
    def _read_partial(root: Path, relative: str) -> str:
        if not _PARTIAL_RE.fullmatch(relative):
            return ""
        path = (root / relative).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            return ""
        try:
            return path.read_text(encoding="utf-8")
        except OSError:
            return ""

    def do_POST(self) -> None:
        request_path = urlsplit(self.path).path
        if request_path == "/api/file":
            self._overwrite_project_file()
            return
        if request_path == "/api/file/new":
            self._create_project_file()
            return
        if request_path == "/api/chat":
            self._chat()
            return
        if request_path == "/api/refine-py":
            self._refine_py()
            return
        if request_path != "/__opt_sp/stop":
            self.send_error(404)
            return
        if not self._authorized_control_request():
            self._send_json(403, {"error": "Server control is not authorized."})
            return

        self._send_json(202, {"message": "OPT_SP server is stopping."})
        Thread(target=self._stop_server, daemon=True).start()

    def _stop_server(self) -> None:
        self.server.shutdown()
        self.server.server_close()

    def _authorized_control_request(self) -> bool:
        try:
            is_loopback = ipaddress.ip_address(self.client_address[0]).is_loopback
        except ValueError:
            is_loopback = False
        provided_token = self.headers.get("Authorization", "").removeprefix("Bearer ")
        return (
            self.stop_token is not None
            and is_loopback
            and hmac.compare_digest(provided_token, self.stop_token)
        )

    def _send_status(self) -> None:
        if not self._authorized_control_request():
            self._send_json(403, {"error": "Server control is not authorized."})
            return
        self._send_json(200, {
            "pid": os.getpid(),
            "port": self.server.server_address[1],
        })

    def _send_health(self) -> None:
        try:
            is_loopback = ipaddress.ip_address(self.client_address[0]).is_loopback
        except ValueError:
            is_loopback = False
        if not is_loopback:
            self._send_json(403, {"error": "Health information is only available locally."})
            return

        root = Path(static_dir())
        checks = {
            "pyodide_js": (root / "pyodide" / "pyodide.js").is_file(),
            "python_stdlib": (root / "pyodide" / "python_stdlib.zip").is_file(),
            "spacelang_pkg": (root / "spacelang_pkg" / "manifest.json").is_file(),
            "studio_page": (root / "studio.html").is_file(),
        }
        ok = all(checks.values())
        self._send_json(200, {
            "ok": ok,
            "checks": checks,
            "hint": None if ok else "Run: python tools/build_static.py",
        })

    def _local_only(self) -> bool:
        if is_loopback(self.client_address[0]):
            return True
        self._send_json(403, {"error": "This endpoint is only available locally."})
        return False

    def _send_llm_status(self) -> None:
        if not self._local_only():
            return
        try:
            config = resolve_config(self.llm_config, self.headers)
        except LLMError as error:
            self._send_json(400, {"ok": False, "error": error.code, "message": error.message})
            return
        self._send_json(200, llm_status(config, self.llm_config))

    def _refine_py(self) -> None:
        """Ask the model for a new Python mirror, then verify it locally."""
        if not self._local_only():
            return
        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            self._send_json(400, {"ok": False, "error": "bad_request_size"})
            return
        if length < 0 or length > _MAX_LLM_REQUEST:
            # Drain a modest overshoot so the client reads the 413 instead of a
            # connection reset, then refuse.
            if 0 < length <= _MAX_DRAIN:
                self.rfile.read(length)
            self._send_json(413, {"ok": False, "error": "input_too_large"})
            return
        try:
            body = self.rfile.read(length)
        except OSError:
            return
        if self.headers.get_content_type() != "application/json":
            self._send_json(415, {"ok": False, "error": "expected_json"})
            return
        try:
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError):
            self._send_json(400, {"ok": False, "error": "invalid_json"})
            return
        if not isinstance(payload, dict):
            self._send_json(400, {"ok": False, "error": "invalid_json"})
            return
        if "sp" in payload:
            self._send_json(400, {
                "ok": False,
                "error": "sp_not_allowed",
                "message": "The encoded program is never sent to the model.",
            })
            return
        extra = set(payload) - {"py", "spasm", "src_kind"}
        if extra:
            self._send_json(400, {
                "ok": False,
                "error": "unknown_field",
                "message": f"unsupported fields: {', '.join(sorted(extra))}",
            })
            return
        py_src = payload.get("py")
        spasm_src = payload.get("spasm")
        if not isinstance(py_src, str) or not isinstance(spasm_src, str):
            self._send_json(400, {"ok": False, "error": "py_and_spasm_required"})
            return

        try:
            config = resolve_config(self.llm_config, self.headers)
            result = refine_py(
                config,
                py_src,
                spasm_src,
                bucket=self.llm_bucket,
                gate=self.llm_gate,
            )
        except LLMError as error:
            body = {"ok": False, "error": error.code}
            if error.message:
                body["message"] = error.message
            if error.retry_after is not None:
                body["retry_after"] = error.retry_after
            body.update(error.details)
            self._send_json(_LLM_STATUS.get(error.code, 502), body)
            return
        self._send_json(200, result)

    def _chat(self) -> None:
        """One assistant turn; the system prompt is chosen from ``page``."""
        if not self._local_only():
            return
        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            self._send_json(400, {"ok": False, "error": "bad_request_size"})
            return
        if length < 0 or length > _MAX_CHAT_REQUEST:
            if 0 < length <= _MAX_DRAIN:
                self.rfile.read(length)
            self._send_json(413, {"ok": False, "error": "input_too_large"})
            return
        try:
            body = self.rfile.read(length)
        except OSError:
            return
        if self.headers.get_content_type() != "application/json":
            self._send_json(415, {"ok": False, "error": "expected_json"})
            return
        try:
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError):
            self._send_json(400, {"ok": False, "error": "invalid_json"})
            return
        if not isinstance(payload, dict):
            self._send_json(400, {"ok": False, "error": "invalid_json"})
            return
        extra = set(payload) - {"messages", "page"}
        if extra:
            self._send_json(400, {
                "ok": False,
                "error": "unknown_field",
                "message": f"unsupported fields: {', '.join(sorted(extra))}",
            })
            return

        try:
            config = resolve_config(self.llm_config, self.headers)
            result = chat_reply(
                config,
                payload.get("page"),
                payload.get("messages"),
                bucket=self.llm_bucket,
                gate=self.llm_gate,
            )
        except LLMError as error:
            detail = {"ok": False, "error": error.code}
            if error.message:
                detail["message"] = error.message
            if error.retry_after is not None:
                detail["retry_after"] = error.retry_after
            detail.update(error.details)
            self._send_json(_LLM_STATUS.get(error.code, 502), detail)
            return
        self._send_json(200, result)

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _project_files_allowed(self) -> bool:
        if self.project_files_enabled:
            return True
        self._send_json(403, {"error": "Project file browsing is disabled."})
        return False

    def _send_project_files(self) -> None:
        if not self._project_files_allowed():
            return

        files = []
        for directory, subdirectories, filenames in os.walk(self.project_root):
            subdirectories[:] = sorted(
                name
                for name in subdirectories
                if name not in _IGNORED_DIRECTORIES and not name.startswith(".")
            )
            parent = Path(directory)
            for filename in filenames:
                if filename.startswith("."):
                    continue
                path = parent / filename
                mode = _SOURCE_MODES.get(path.suffix.lower())
                if mode is None or path.is_symlink():
                    continue
                try:
                    resolved = path.resolve(strict=True)
                    if not resolved.is_relative_to(self.project_root):
                        continue
                    if resolved.stat().st_size > _MAX_SOURCE_FILE_SIZE:
                        continue
                except OSError:
                    continue
                files.append({
                    "path": path.relative_to(self.project_root).as_posix(),
                    "mode": mode,
                })

        files.sort(key=lambda item: (item["path"].casefold(), item["path"]))
        self._send_json(200, {
            "root": self.project_root.name or str(self.project_root),
            "files": files,
        })

    def _send_project_file(self, relative_path: str) -> None:
        if not self._project_files_allowed():
            return
        if not relative_path or "\\" in relative_path or "\0" in relative_path:
            self._send_json(400, {"error": "Invalid project file path."})
            return

        candidate = self.project_root / relative_path
        try:
            path = candidate.resolve(strict=True)
            if not path.is_relative_to(self.project_root) or not path.is_file():
                self._send_json(404, {"error": "Project file not found."})
                return
            mode = _SOURCE_MODES.get(path.suffix.lower())
            if mode is None:
                self._send_json(415, {"error": "Unsupported project file type."})
                return
            if path.stat().st_size > _MAX_SOURCE_FILE_SIZE:
                self._send_json(413, {"error": "Project file is larger than 1 MiB."})
                return
            code = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            self._send_json(404, {"error": "Project file not found."})
            return
        except (OSError, UnicodeError, ValueError):
            self._send_json(400, {"error": "Could not read the project file as UTF-8 text."})
            return

        self._send_json(200, {
            "path": path.relative_to(self.project_root).as_posix(),
            "mode": mode,
            "code": code,
        })

    def _read_source_payload(self) -> tuple[str, bytes] | None:
        """Parse and validate a ``{path, code}`` body for the file endpoints.

        Sends the error response itself and returns ``None`` when the request is
        unusable, so overwriting and creating share one validation path.
        """
        if self.headers.get_content_type() != "application/json":
            self._send_json(415, {"error": "Expected a JSON request."})
            return None
        try:
            content_length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            self._send_json(400, {"error": "Invalid request size."})
            return None
        if content_length < 0 or content_length > _MAX_SOURCE_FILE_SIZE + 8192:
            self._send_json(413, {"error": "Request is too large."})
            return None
        try:
            payload = json.loads(self.rfile.read(content_length).decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError):
            self._send_json(400, {"error": "Invalid JSON request."})
            return None
        if not isinstance(payload, dict):
            self._send_json(400, {"error": "Invalid project file request."})
            return None
        relative_path = payload.get("path")
        code = payload.get("code")
        if not isinstance(relative_path, str) or not isinstance(code, str):
            self._send_json(400, {"error": "A project path and source text are required."})
            return None

        try:
            encoded = code.encode("utf-8")
        except UnicodeError:
            self._send_json(400, {"error": "Source text must be valid UTF-8."})
            return None
        if len(encoded) > _MAX_SOURCE_FILE_SIZE:
            self._send_json(413, {"error": "Edited source is larger than 1 MiB."})
            return None
        relative = Path(relative_path)
        if (
            not relative_path
            or relative.is_absolute()
            or ".." in relative.parts
            or "\\" in relative_path
            or "\0" in relative_path
        ):
            self._send_json(400, {"error": "Invalid project file path."})
            return None
        return relative_path, encoded

    def _overwrite_project_file(self) -> None:
        if not self._project_files_allowed():
            return
        try:
            is_loopback = ipaddress.ip_address(self.client_address[0]).is_loopback
        except ValueError:
            is_loopback = False
        if not is_loopback:
            self._send_json(403, {"error": "Project files can only be overwritten locally."})
            return
        payload = self._read_source_payload()
        if payload is None:
            return
        relative_path, encoded = payload

        candidate = self.project_root / relative_path
        try:
            if candidate.is_symlink():
                self._send_json(404, {"error": "Project file not found."})
                return
            path = candidate.resolve(strict=True)
            if not path.is_relative_to(self.project_root) or not path.is_file():
                self._send_json(404, {"error": "Project file not found."})
                return
            if path.suffix.lower() not in _SOURCE_MODES:
                self._send_json(415, {"error": "Unsupported project file type."})
                return
            if path.stat().st_size > _MAX_SOURCE_FILE_SIZE:
                self._send_json(413, {"error": "Project file is larger than 1 MiB."})
                return

            descriptor, temporary_name = tempfile.mkstemp(
                prefix=f".{path.name}.",
                dir=path.parent,
            )
            try:
                with os.fdopen(descriptor, "wb") as output:
                    output.write(encoded)
                    output.flush()
                    os.fsync(output.fileno())
                os.chmod(temporary_name, stat.S_IMODE(path.stat().st_mode))
                os.replace(temporary_name, path)
            except BaseException:
                Path(temporary_name).unlink(missing_ok=True)
                raise
        except FileNotFoundError:
            self._send_json(404, {"error": "Project file not found."})
            return
        except (OSError, ValueError):
            self._send_json(500, {"error": "Could not overwrite the project file."})
            return

        self._send_json(200, {
            "path": path.relative_to(self.project_root).as_posix(),
            "message": "Project file overwritten.",
        })

    def _create_project_file(self) -> None:
        """Create a new source file; never replace an existing path.

        Creating and overwriting are separate endpoints on purpose: a mistyped
        name has to fail instead of destroying a file.
        """
        if not self._project_files_allowed():
            return
        try:
            is_loopback = ipaddress.ip_address(self.client_address[0]).is_loopback
        except ValueError:
            is_loopback = False
        if not is_loopback:
            self._send_json(403, {"error": "Project files can only be created locally."})
            return
        payload = self._read_source_payload()
        if payload is None:
            return
        relative_path, encoded = payload

        relative = Path(relative_path)
        if relative.suffix.lower() not in _SOURCE_MODES:
            self._send_json(415, {"error": "Unsupported project file type."})
            return
        candidate = self.project_root / relative_path
        try:
            parent = candidate.parent.resolve(strict=True)
        except (OSError, ValueError):
            self._send_json(404, {"error": "Project folder not found."})
            return
        if not parent.is_relative_to(self.project_root) or not parent.is_dir():
            self._send_json(404, {"error": "Project folder not found."})
            return

        target = parent / candidate.name
        exists = {"error": "exists", "message": f"{relative_path} already exists."}
        if target.exists() or target.is_symlink():
            self._send_json(409, exists)
            return
        try:
            # "x" makes the existence check atomic with the creation itself.
            with open(target, "xb") as output:
                output.write(encoded)
                output.flush()
                os.fsync(output.fileno())
        except FileExistsError:
            self._send_json(409, exists)
            return
        except OSError:
            self._send_json(500, {"error": "Could not create the project file."})
            return

        self._send_json(201, {
            "path": target.relative_to(self.project_root).as_posix(),
            "mode": _SOURCE_MODES[target.suffix.lower()],
            "message": "Project file created.",
        })


class _OPTSPHTTPServer(ThreadingHTTPServer):
    def server_bind(self) -> None:
        TCPServer.server_bind(self)
        self.server_name = self.server_address[0]
        self.server_port = self.server_address[1]


def open_browser(port: int = 8000) -> None:
    webbrowser.open(f"http://127.0.0.1:{port}/")


def server(
    port: int = 8000,
    host: str = "127.0.0.1",
    open_browser: bool = True,
    blocking: bool = True,
    allow_project_files: bool | None = None,
    _stop_token: str | None = None,
    _ready_file: Path | None = None,
    llm: "LLMConfig | dict | None" = None,
) -> tuple[ThreadingHTTPServer, str] | None:
    if _stop_token is None:
        _stop_token = secrets.token_urlsafe(32)
    if allow_project_files is None:
        try:
            allow_project_files = ipaddress.ip_address(host).is_loopback
        except ValueError:
            allow_project_files = host.lower() == "localhost"
    try:
        effective_llm = resolve_config(llm)
    except LLMError:
        effective_llm = LLMConfig()
    handler = partial(
        _QuietHandler,
        directory=str(static_dir()),
        project_root=Path.cwd().resolve(),
        project_files_enabled=allow_project_files,
        stop_token=_stop_token,
        llm_config=llm,
        llm_bucket=TokenBucket(effective_llm.rate_limit_rpm, effective_llm.rate_limit_burst),
        llm_gate=Gate(),
    )
    httpd = _OPTSPHTTPServer((host, port), handler)
    if _ready_file is not None:
        try:
            _ready_file.touch()
        except OSError:
            httpd.server_close()
            raise
    url = f"http://{host}:{httpd.server_address[1]}"
    if open_browser:
        Timer(0.8, webbrowser.open, args=(url + "/",)).start()
    if not blocking:
        Thread(target=httpd.serve_forever, daemon=True).start()
        return httpd, url
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
    return None


def _management_file(port: int) -> Path:
    if hasattr(os, "getuid"):
        user = str(os.getuid())
    else:
        user = hashlib.sha256(getpass.getuser().encode("utf-8")).hexdigest()[:16]
    directory = Path(tempfile.gettempdir()) / f"spacelang-opt-sp-{user}"
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    return directory / f"{port}.json"


def _is_loopback_host(host: str) -> bool:
    try:
        address = ipaddress.ip_address(host)
        return address.version == 4 and address.is_loopback
    except ValueError:
        return host.lower() == "localhost"


def _control_url(host: str, port: int, endpoint: str) -> str:
    try:
        address = ipaddress.ip_address(host)
        connect_host = str(address)
        netloc = f"[{connect_host}]" if address.version == 6 else connect_host
    except ValueError:
        connect_host = "127.0.0.1" if host.lower() == "localhost" else host
        netloc = connect_host
    return f"http://{netloc}:{port}/{endpoint}"


def _control_request(
    host: str,
    port: int,
    endpoint: str,
    token: str,
    method: str,
    timeout: float = 1,
) -> dict:
    request = Request(
        _control_url(host, port, endpoint),
        headers={"Authorization": f"Bearer {token}"},
        method=method,
    )
    with build_opener(ProxyHandler({})).open(request, timeout=timeout) as response:
        return json.load(response)


def _load_management_file(path: Path) -> str:
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
        token = record["token"]
        if not isinstance(token, str) or len(token) < 32:
            raise ValueError("invalid token")
        return token
    except (OSError, KeyError, TypeError, ValueError) as error:
        raise RuntimeError(f"Could not read OPT_SP server state at {path}: {error}") from error


def _serve_background(
    host: str,
    port: int,
    state_file: Path,
    ready_file: Path,
) -> None:
    token = _load_management_file(state_file)
    try:
        server(
            port=port,
            host=host,
            open_browser=False,
            blocking=True,
            _stop_token=token,
            _ready_file=ready_file,
        )
    finally:
        ready_file.unlink(missing_ok=True)
        try:
            current_state = state_file.read_text(encoding="utf-8")
        except FileNotFoundError:
            current_state = None
        if current_state is not None:
            current_token = json.loads(current_state).get("token")
            if current_token == token:
                state_file.unlink(missing_ok=True)


def _start_background(host: str, port: int, open_browser: bool, llm_flags: list[str] | None = None) -> None:
    if not _is_loopback_host(host):
        raise RuntimeError("Background mode is limited to localhost or IPv4 loopback hosts.")
    if not 0 < port < 65536:
        raise RuntimeError("Background mode requires a port between 1 and 65535.")

    state_file = _management_file(port)
    if state_file.exists():
        token = _load_management_file(state_file)
        try:
            _control_request(host, port, "__opt_sp/status", token, "GET")
        except HTTPError as error:
            raise RuntimeError(
                f"Could not verify the OPT_SP server already using port {port}."
            ) from error
        except URLError:
            state_file.unlink(missing_ok=True)
        else:
            raise RuntimeError(f"OPT_SP is already running on {host}:{port}.")

    token = secrets.token_urlsafe(32)
    descriptor = os.open(state_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as state:
        json.dump({"token": token}, state)

    log_file = state_file.with_suffix(".log")
    ready_file = state_file.with_suffix(".ready")
    ready_file.unlink(missing_ok=True)
    process = None
    command = [
        sys.executable,
        "-c",
        "from spacelang.opt_sp.server import _cli; _cli()",
        "--host",
        host,
        "--port",
        str(port),
        "--_background-token-file",
        str(state_file),
        "--_background-ready-file",
        str(ready_file),
        *(llm_flags or []),
    ]
    try:
        if os.name == "nt":
            process_options = {
                "creationflags": (
                    subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
                )
            }
        else:
            process_options = {"start_new_session": True}
        with log_file.open("ab") as log:
            process = subprocess.Popen(
                command,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=subprocess.STDOUT,
                **process_options,
            )
        startup_deadline = time.monotonic() + 15
        while not ready_file.exists() and time.monotonic() < startup_deadline:
            if process.poll() is not None:
                raise RuntimeError(
                    f"OPT_SP failed to start. See server log: {log_file}"
                )
            time.sleep(0.05)
        if not ready_file.exists():
            try:
                log_output = log_file.read_text(encoding="utf-8").strip()
            except OSError as error:
                log_output = f"Could not read server log: {error}"
            if not log_output:
                log_output = "(server log is empty)"
            raise RuntimeError(
                "OPT_SP did not become ready within 15 seconds."
                f" See server log: {log_file}\n{log_output}"
            )
    except Exception:
        state_file.unlink(missing_ok=True)
        ready_file.unlink(missing_ok=True)
        if process is not None and process.poll() is None:
            process.terminate()
            process.wait(timeout=2)
        raise

    url = _control_url(host, port, "").rstrip("/")
    print(f"OPT_SP running in background at {url}")
    print(f"Stop it with: spacelang-opt-sp --stop --host {host} --port {port}")
    print(f"Server log: {log_file}")
    if open_browser:
        Timer(0.8, webbrowser.open, args=(url + "/",)).start()


def _stop_background(host: str, port: int) -> None:
    if not _is_loopback_host(host):
        raise RuntimeError(
            "Background servers can only be stopped via localhost or IPv4 loopback."
        )
    state_file = _management_file(port)
    if not state_file.exists():
        raise RuntimeError(f"No background OPT_SP server found for port {port}.")
    token = _load_management_file(state_file)
    try:
        _control_request(host, port, "__opt_sp/stop", token, "POST")
    except HTTPError as error:
        raise RuntimeError(
            f"Could not authorize stopping OPT_SP on port {port}."
        ) from error
    except URLError as error:
        raise RuntimeError(
            f"Could not stop OPT_SP on {host}:{port}; it may not be running."
        ) from error
    deadline = time.monotonic() + 5
    while state_file.exists() and time.monotonic() < deadline:
        time.sleep(0.05)
    if state_file.exists():
        raise RuntimeError(f"OPT_SP on port {port} did not stop within 5 seconds.")
    print(f"OPT_SP stopped on port {port}.")


def _cli() -> None:
    parser = argparse.ArgumentParser(description="Run the OPT_SP visual debugger.")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--no-browser", action="store_true")
    lifecycle = parser.add_mutually_exclusive_group()
    lifecycle.add_argument(
        "--background",
        action="store_true",
        help="Run as a detached background server.",
    )
    lifecycle.add_argument(
        "--stop",
        action="store_true",
        help="Stop a background server on this port.",
    )
    parser.add_argument(
        "--allow-project-files",
        action="store_true",
        help="Allow project file browsing when binding to a non-loopback host.",
    )
    parser.add_argument("--_background-token-file", help=argparse.SUPPRESS)
    parser.add_argument("--_background-ready-file", help=argparse.SUPPRESS)
    parser.add_argument("--llm-base-url", help="OpenAI-compatible endpoint for the AI mirror sync.")
    parser.add_argument("--llm-model", help="Model name served by that endpoint.")
    parser.add_argument(
        "--llm-api-key-file",
        help="Read the API key from this file (first non-empty line).",
    )
    parser.add_argument("--llm-mode", choices=MODES, help="manual, auto or off.")
    args = parser.parse_args()

    llm_overrides: dict[str, object] = {}
    if args.llm_base_url:
        llm_overrides["base_url"] = args.llm_base_url
    if args.llm_model:
        llm_overrides["model"] = args.llm_model
    if args.llm_mode:
        llm_overrides["mode"] = args.llm_mode
    if args.llm_api_key_file:
        try:
            contents = Path(args.llm_api_key_file).read_text(encoding="utf-8")
        except OSError as error:
            parser.error(f"Could not read the API key file: {error}")
        lines = [line.strip() for line in contents.splitlines() if line.strip()]
        if not lines:
            parser.error("The API key file is empty.")
        llm_overrides["api_key"] = lines[0]

    if args._background_token_file:
        if not args._background_ready_file:
            parser.error("Background server readiness file is required.")
        _serve_background(
            args.host,
            args.port,
            Path(args._background_token_file),
            Path(args._background_ready_file),
        )
        return
    if args.stop:
        _stop_background(args.host, args.port)
        return
    if args.background:
        llm_flags: list[str] = []
        if args.llm_base_url:
            llm_flags += ["--llm-base-url", args.llm_base_url]
        if args.llm_model:
            llm_flags += ["--llm-model", args.llm_model]
        if args.llm_mode:
            llm_flags += ["--llm-mode", args.llm_mode]
        if args.llm_api_key_file:
            llm_flags += ["--llm-api-key-file", args.llm_api_key_file]
        _start_background(args.host, args.port, not args.no_browser, llm_flags)
        return
    server(
        port=args.port,
        host=args.host,
        open_browser=not args.no_browser,
        allow_project_files=True if args.allow_project_files else None,
        llm=llm_overrides or None,
    )


if __name__ == "__main__":
    _cli()


__all__ = ["server", "open_browser"]
