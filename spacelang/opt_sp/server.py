from __future__ import annotations

import argparse
import getpass
import hashlib
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import hmac
import ipaddress
import json
import os
from pathlib import Path
import secrets
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

from ._locate import static_dir

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


class _QuietHandler(SimpleHTTPRequestHandler):
    def __init__(
        self,
        *args,
        project_root: Path,
        project_files_enabled: bool,
        stop_token: str | None,
        **kwargs,
    ):
        self.project_root = project_root
        self.project_files_enabled = project_files_enabled
        self.stop_token = stop_token
        super().__init__(*args, **kwargs)

    def log_message(self, format: str, *args) -> None:
        if os.environ.get("SPACELANG_OPT_SP_VERBOSE") == "1":
            super().log_message(format, *args)

    def do_GET(self) -> None:
        request = urlsplit(self.path)
        if request.path == "/__opt_sp/status":
            self._send_status()
        elif request.path in {"/", "/index.html", "/visualize.html"}:
            page = (
                "index.html"
                if request.path in {"/", "/index.html"}
                else "visualize.html"
            )
            self._send_controlled_page(page)
        elif request.path == "/api/files":
            self._send_project_files()
        elif request.path == "/api/file":
            self._send_project_file(parse_qs(request.query).get("path", [""])[0])
        else:
            super().do_GET()

    def _send_controlled_page(self, filename: str) -> None:
        page = (Path(static_dir()) / filename).read_bytes()
        token = (self.stop_token or "").encode("ascii")
        body = page.replace(b"__OPT_SP_CONTROL_TOKEN__", token)
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        request_path = urlsplit(self.path).path
        if request_path == "/api/file":
            self._overwrite_project_file()
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
        if self.headers.get_content_type() != "application/json":
            self._send_json(415, {"error": "Expected a JSON request."})
            return
        try:
            content_length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            self._send_json(400, {"error": "Invalid request size."})
            return
        if content_length < 0 or content_length > _MAX_SOURCE_FILE_SIZE + 8192:
            self._send_json(413, {"error": "Request is too large."})
            return
        try:
            payload = json.loads(self.rfile.read(content_length).decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError):
            self._send_json(400, {"error": "Invalid JSON request."})
            return
        if not isinstance(payload, dict):
            self._send_json(400, {"error": "Invalid project file request."})
            return
        relative_path = payload.get("path")
        code = payload.get("code")
        if not isinstance(relative_path, str) or not isinstance(code, str):
            self._send_json(400, {"error": "A project path and source text are required."})
            return

        try:
            encoded = code.encode("utf-8")
        except UnicodeError:
            self._send_json(400, {"error": "Source text must be valid UTF-8."})
            return
        if len(encoded) > _MAX_SOURCE_FILE_SIZE:
            self._send_json(413, {"error": "Edited source is larger than 1 MiB."})
            return
        relative = Path(relative_path)
        if (
            not relative_path
            or relative.is_absolute()
            or ".." in relative.parts
            or "\\" in relative_path
            or "\0" in relative_path
        ):
            self._send_json(400, {"error": "Invalid project file path."})
            return

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


def open_browser(port: int = 8000) -> None:
    webbrowser.open(f"http://127.0.0.1:{port}/")


def server(
    port: int = 8000,
    host: str = "127.0.0.1",
    open_browser: bool = True,
    blocking: bool = True,
    allow_project_files: bool | None = None,
    _stop_token: str | None = None,
) -> tuple[ThreadingHTTPServer, str] | None:
    if _stop_token is None:
        _stop_token = secrets.token_urlsafe(32)
    if allow_project_files is None:
        try:
            allow_project_files = ipaddress.ip_address(host).is_loopback
        except ValueError:
            allow_project_files = host.lower() == "localhost"
    handler = partial(
        _QuietHandler,
        directory=str(static_dir()),
        project_root=Path.cwd().resolve(),
        project_files_enabled=allow_project_files,
        stop_token=_stop_token,
    )
    httpd = ThreadingHTTPServer((host, port), handler)
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


def _serve_background(host: str, port: int, state_file: Path) -> None:
    token = _load_management_file(state_file)
    try:
        server(
            port=port,
            host=host,
            open_browser=False,
            blocking=True,
            _stop_token=token,
        )
    finally:
        try:
            current_state = state_file.read_text(encoding="utf-8")
        except FileNotFoundError:
            current_state = None
        if current_state is not None:
            current_token = json.loads(current_state).get("token")
            if current_token == token:
                state_file.unlink(missing_ok=True)


def _start_background(host: str, port: int, open_browser: bool) -> None:
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
        last_error = None
        while time.monotonic() < startup_deadline:
            if process.poll() is not None:
                raise RuntimeError(
                    f"OPT_SP failed to start. See server log: {log_file}"
                )
            try:
                _control_request(
                    host,
                    port,
                    "__opt_sp/status",
                    token,
                    "GET",
                    timeout=min(0.25, startup_deadline - time.monotonic()),
                )
                break
            except HTTPError as error:
                raise RuntimeError(
                    f"OPT_SP rejected its startup check with HTTP {error.code}."
                ) from error
            except URLError as error:
                last_error = error
                time.sleep(min(0.1, max(0, startup_deadline - time.monotonic())))
        else:
            raise RuntimeError(
                "OPT_SP did not start within 15 seconds"
                f" (last status-check error: {last_error}). See server log: {log_file}"
            )
    except Exception:
        state_file.unlink(missing_ok=True)
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
    args = parser.parse_args()
    if args._background_token_file:
        _serve_background(args.host, args.port, Path(args._background_token_file))
        return
    if args.stop:
        _stop_background(args.host, args.port)
        return
    if args.background:
        _start_background(args.host, args.port, not args.no_browser)
        return
    server(
        port=args.port,
        host=args.host,
        open_browser=not args.no_browser,
        allow_project_files=True if args.allow_project_files else None,
    )


if __name__ == "__main__":
    _cli()


__all__ = ["server", "open_browser"]
