from __future__ import annotations

import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import os
from threading import Thread, Timer
import webbrowser

from ._locate import static_dir


class _QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:
        if os.environ.get("SPACELANG_OPT_SP_VERBOSE") == "1":
            super().log_message(format, *args)


def open_browser(port: int = 8000) -> None:
    webbrowser.open(f"http://127.0.0.1:{port}/")


def server(
    port: int = 8000,
    host: str = "127.0.0.1",
    open_browser: bool = True,
    blocking: bool = True,
) -> tuple[ThreadingHTTPServer, str] | None:
    handler = partial(_QuietHandler, directory=str(static_dir()))
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


def _cli() -> None:
    parser = argparse.ArgumentParser(description="Run the OPT_SP visual debugger.")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    server(port=args.port, host=args.host, open_browser=not args.no_browser)


__all__ = ["server", "open_browser"]
