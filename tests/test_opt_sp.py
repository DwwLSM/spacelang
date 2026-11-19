import json
import os
import socket
import subprocess
import sys
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from spacelang.encoder import encode
from spacelang.pyfront import compile_py
from spacelang.opt_sp.server import _management_file
from spacelang.web_bridge import trace_program
from spacelang.opt_sp import server


def test_trace_program_basic():
    result = trace_program("PUSH_INT 2\nPUSH_INT 3\nOP 1\nHALT", is_asm=True)
    assert result["ok"] is True
    assert len(result["trace"]) >= 3
    required = {"ip", "opcode", "operand_stack", "call_stack", "globals", "heap", "output"}
    assert all(required <= step.keys() for step in result["trace"])


def test_trace_program_error():
    result = trace_program("BOGUS", is_asm=True)
    assert result["ok"] is False
    assert result["error"]


def test_trace_jsonable():
    result = trace_program("PUSH_INT 2\nPUSH_INT 3\nOP 1\nHALT", is_asm=True)
    json.dumps(result)


def test_trace_captures_output_and_nested_heap():
    result = trace_program("answer = [[1, 2], [3, 4]]\nprint(answer)", is_asm=False)
    assert result["ok"] is True
    assert result["trace"][-1]["output"] == "[[1, 2], [3, 4]]\n"
    heap = result["trace"][-1]["heap"]
    assert any(node["type"] == "list" and node["refs"] for node in heap.values())


def test_trace_program_encoded_sp():
    source = encode(compile_py("print(2 + 3)"), include_names=True)
    result = trace_program(source, is_sp=True)
    assert result["ok"] is True
    assert result["trace"][-1]["output"] == "5\n"


def test_server_returns_url():
    httpd, url = server(open_browser=False, blocking=False, port=0)
    try:
        with urlopen(f"{url}/index.html") as response:
            assert response.status == 200
            assert b"OPT_SP" in response.read()
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_server_assets_use_paths_relative_to_app():
    httpd, url = server(open_browser=False, blocking=False, port=0)
    try:
        with urlopen(f"{url}/") as response:
            page = response.read().decode("utf-8")
        assert 'href="css/opt-sp.css?v=6"' in page
        assert 'src="js/app.js?v=6"' in page
        assert 'id="autoplay-speed" type="range" min="50" max="1500" step="50"' in page
        assert '>1 s / step</output>' in page
        assert 'for="open-project-file-browser">File</label>' in page
        assert 'id="open-project-file-browser"' in page
        assert 'id="project-file-browser"' in page
        assert 'id="close-project-file-browser"' in page

        with urlopen(f"{url}/js/visualizer.js") as response:
            visualizer = response.read().decode("utf-8")
        assert 'Number(seconds.toFixed(2))} s / step' in visualizer

        with urlopen(f"{url}/js/app.js") as response:
            app = response.read().decode("utf-8")
        assert 'fetch("api/files")' in app
        assert 'fetch("__opt_sp/stop"' in app
        assert 'openProjectFileBrowserButton.addEventListener("click"' in app
        assert 'closeProjectFileBrowserButton.addEventListener("click"' in app
        assert 'function setProjectFileButtonLabel(filename = "")' in app

        with urlopen(f"{url}/js/spacelang-kernel.js") as response:
            kernel = response.read().decode("utf-8")
        assert 'fetch("spacelang_pkg/manifest.json")' in kernel
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_server_does_not_require_reverse_dns(monkeypatch):
    monkeypatch.setattr(
        socket,
        "getfqdn",
        lambda host: pytest.fail("OPT_SP server binding must not perform reverse DNS"),
    )
    httpd, _ = server(open_browser=False, blocking=False, port=0)
    httpd.shutdown()
    httpd.server_close()


def test_server_page_can_stop_server_with_control_token():
    httpd, url = server(open_browser=False, blocking=False, port=0)
    try:
        with urlopen(f"{url}/") as response:
            page = response.read()
        token = page.split(
            b'<meta name="opt-sp-control-token" content="', 1
        )[1].split(b'"', 1)[0].decode("ascii")
        assert len(token) >= 32
        with urlopen(f"{url}/visualize.html") as response:
            assert token.encode("ascii") in response.read()

        unauthorized = Request(
            f"{url}/__opt_sp/stop",
            data=b"",
            headers={"Authorization": "Bearer invalid"},
            method="POST",
        )
        with pytest.raises(HTTPError) as error:
            urlopen(unauthorized)
        assert error.value.code == 403

        stop = Request(
            f"{url}/__opt_sp/stop",
            data=b"",
            headers={"Authorization": f"Bearer {token}"},
            method="POST",
        )
        with urlopen(stop) as response:
            assert response.status == 202
        for _ in range(50):
            try:
                urlopen(url, timeout=0.1)
            except OSError:
                break
            time.sleep(0.1)
        else:
            pytest.fail("OPT_SP server did not stop.")
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_server_background_cli_start_and_stop():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    command = [
        sys.executable,
        "-c",
        "from spacelang.opt_sp.server import _cli; _cli()",
    ]
    state_file = _management_file(port)
    environment = os.environ.copy()
    environment["http_proxy"] = "http://127.0.0.1:1"
    environment.pop("no_proxy", None)
    environment.pop("NO_PROXY", None)
    start = subprocess.run(
        command + ["--port", str(port), "--background", "--no-browser"],
        capture_output=True,
        text=True,
        timeout=20,
        env=environment,
    )
    try:
        assert start.returncode == 0, start.stderr
        assert f"http://127.0.0.1:{port}" in start.stdout
        stop = subprocess.run(
            command + ["--port", str(port), "--stop"],
            capture_output=True,
            text=True,
            timeout=10,
            env=environment,
        )
        assert stop.returncode == 0, stop.stderr
        assert f"stopped on port {port}" in stop.stdout

        for _ in range(50):
            if not state_file.exists():
                break
            time.sleep(0.1)
        assert not state_file.exists()
    finally:
        subprocess.run(
            command + ["--port", str(port), "--stop"],
            capture_output=True,
            text=True,
            timeout=10,
            env=environment,
        )
        state_file.unlink(missing_ok=True)
        state_file.with_suffix(".log").unlink(missing_ok=True)
        state_file.with_suffix(".ready").unlink(missing_ok=True)


def test_server_lists_and_reads_project_files(tmp_path, monkeypatch):
    (tmp_path / "zeta.spasm").write_text("HALT", encoding="utf-8")
    (tmp_path / "alpha.py").write_text("print(1)", encoding="utf-8")
    (tmp_path / "nested").mkdir()
    (tmp_path / "nested" / "demo.sp").write_text("encoded", encoding="utf-8")
    (tmp_path / ".hidden").mkdir()
    (tmp_path / ".hidden" / "secret.py").write_text("secret", encoding="utf-8")
    (tmp_path / ".secret.py").write_text("secret", encoding="utf-8")
    (tmp_path / "notes.md").write_text("not a supported source", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    httpd, url = server(open_browser=False, blocking=False, port=0)
    try:
        with urlopen(f"{url}/api/files") as response:
            listing = json.load(response)
        assert [item["path"] for item in listing["files"]] == [
            "alpha.py",
            "nested/demo.sp",
            "zeta.spasm",
        ]
        assert [item["mode"] for item in listing["files"]] == [
            "python",
            "sp",
            "asm",
        ]

        with urlopen(f"{url}/api/file?path=nested%2Fdemo.sp") as response:
            source = json.load(response)
        assert source == {
            "path": "nested/demo.sp",
            "mode": "sp",
            "code": "encoded",
        }

        with pytest.raises(HTTPError) as error:
            urlopen(f"{url}/api/file?path=..%2Foutside.py")
        assert error.value.code == 404
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_server_overwrites_project_file_atomically(tmp_path, monkeypatch):
    source = tmp_path / "program.py"
    source.write_text("print(1)\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    httpd, url = server(open_browser=False, blocking=False, port=0)
    try:
        request = Request(
            f"{url}/api/file",
            data=json.dumps({
                "path": "program.py",
                "code": "print('updated')\n",
            }).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request) as response:
            result = json.load(response)
        assert result == {
            "path": "program.py",
            "message": "Project file overwritten.",
        }
        assert source.read_text(encoding="utf-8") == "print('updated')\n"

        invalid_path = Request(
            f"{url}/api/file",
            data=json.dumps({"path": "../outside.py", "code": "changed"}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with pytest.raises(HTTPError) as error:
            urlopen(invalid_path)
        assert error.value.code == 400
    finally:
        httpd.shutdown()
        httpd.server_close()

    httpd, url = server(
        open_browser=False,
        blocking=False,
        port=0,
        allow_project_files=False,
    )
    try:
        request = Request(
            f"{url}/api/file",
            data=json.dumps({"path": "program.py", "code": "changed"}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with pytest.raises(HTTPError) as error:
            urlopen(request)
        assert error.value.code == 403
        assert source.read_text(encoding="utf-8") == "print('updated')\n"
    finally:
        httpd.shutdown()
        httpd.server_close()

    httpd, url = server(
        open_browser=False,
        blocking=False,
        port=0,
        allow_project_files=False,
    )
    try:
        with pytest.raises(HTTPError) as error:
            urlopen(f"{url}/api/files")
        assert error.value.code == 403
    finally:
        httpd.shutdown()
        httpd.server_close()
