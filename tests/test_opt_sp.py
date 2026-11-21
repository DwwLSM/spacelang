import json
import os
import re
import socket
import subprocess
import sys
import time
import importlib.util
from importlib import import_module
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from spacelang.encoder import encode
from spacelang.pyfront import compile_py
from spacelang.opt_sp.server import _management_file
from spacelang.web_bridge import trace_program
from spacelang.opt_sp import markdown_doc
from spacelang.opt_sp import server

# The package exports the *function* `server`, which shadows the module of the
# same name, so helpers have to be reached through the import system.
server_module = import_module("spacelang.opt_sp.server")


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


def test_health_reports_state():
    httpd, url = server(open_browser=False, blocking=False, port=0)
    try:
        with urlopen(f"{url}/__opt_sp/health") as response:
            assert response.status == 200
            report = json.loads(response.read())
    finally:
        httpd.shutdown()
        httpd.server_close()
    assert set(report["checks"]) == {
        "pyodide_js",
        "python_stdlib",
        "spacelang_pkg",
        "studio_page",
    }
    assert report["ok"] == all(report["checks"].values())
    # studio.html is tracked, so it must be found. The Pyodide bundle and the
    # packaged SpaceLang modules are build artifacts (see .gitignore) and are
    # absent on a clean checkout, so their presence is not asserted here.
    assert report["checks"]["studio_page"] is True


def test_health_marks_missing_asset(monkeypatch):
    missing_root = Path(__file__).resolve().parent / "__missing_opt_sp_static__"
    # `spacelang.opt_sp.server` is shadowed by the exported `server` function,
    # so resolve the module through sys.modules instead of attribute access.
    server_module = import_module("spacelang.opt_sp.server")
    monkeypatch.setattr(server_module, "static_dir", lambda: missing_root)
    httpd, url = server(open_browser=False, blocking=False, port=0)
    try:
        with urlopen(f"{url}/__opt_sp/health") as response:
            report = json.loads(response.read())
    finally:
        httpd.shutdown()
        httpd.server_close()
    assert report["ok"] is False
    assert report["checks"]["pyodide_js"] is False
    assert "build_static" in (report["hint"] or "")


def test_studio_route_serves_page():
    httpd, url = server(open_browser=False, blocking=False, port=0)
    try:
        with urlopen(f"{url}/studio") as response:
            assert response.status == 200
            page = response.read().decode("utf-8")
    finally:
        httpd.shutdown()
        httpd.server_close()
    assert "studio-layout" in page
    assert 'id="sp-editor"' in page
    assert "__OPT_SP_CONTROL_TOKEN__" not in page
    # "Back to editor" asks which representation to carry, instead of guessing.
    assert 'id="carry-dialog"' in page
    for pane in ("py", "spasm", "sp"):
        assert f'data-pane="{pane}"' in page, pane
    # The menu item belongs to the editor page only; it ships hidden, and the
    # stylesheet reset makes `hidden` beat `display: flex` on the menu items.
    assert 'id="new-file-button"' in page
    assert not [
        line
        for line in page.splitlines()
        if 'id="new-file-button"' in line and "hidden" not in line
    ]


def test_every_page_shares_the_settings_menu():
    httpd, url = server(open_browser=False, blocking=False, port=0)
    try:
        for path in ("/", "/editor", "/visualize.html", "/studio", "/docs", "/tutorial"):
            with urlopen(f"{url}{path}") as response:
                page = response.read().decode("utf-8")
            # Home and the LLM settings dialog are global; the dialog is a
            # partial, so it must be included exactly once per page.
            assert 'id="home-menu-link"' in page, path
            assert 'id="llm-settings-button"' in page, path
            assert page.count('id="llm-settings"') == 1, path
            assert page.count('id="llm-base-url"') == 1, path
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_pages_have_no_unresolved_includes():
    httpd, url = server(open_browser=False, blocking=False, port=0)
    try:
        for path in ("/", "/editor", "/visualize.html", "/studio", "/docs", "/tutorial"):
            with urlopen(f"{url}{path}") as response:
                page = response.read().decode("utf-8")
            assert "<!-- #include" not in page, path
            assert "{{back_link}}" not in page, path
            assert "{{page_title}}" not in page, path
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_home_page_links_the_workspace():
    httpd, url = server(open_browser=False, blocking=False, port=0)
    try:
        with urlopen(f"{url}/") as response:
            page = response.read().decode("utf-8")
    finally:
        httpd.shutdown()
        httpd.server_close()
    for target in ("/editor", "/studio", "/visualizer", "/docs", "/tutorial"):
        assert f'href="{target}"' in page, target
    assert "github.com/DwwLSM/spacelang" in page


def test_assistant_ships_with_every_page():
    httpd, url = server(open_browser=False, blocking=False, port=0)
    try:
        for path in ("/", "/editor", "/visualize.html", "/studio", "/docs", "/tutorial"):
            with urlopen(f"{url}{path}") as response:
                page = response.read().decode("utf-8")
            assert page.count('id="chat-panel"') == 1, path
            assert 'id="chat-input"' in page, path
            assert 'data-role="log"' in page, path
            # The header toggle is shared, so every page can fold the drawer.
            assert 'id="chat-toggle"' in page, path
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_home_page_offers_scene_styles():
    httpd, url = server(open_browser=False, blocking=False, port=0)
    try:
        with urlopen(f"{url}/") as response:
            page = response.read().decode("utf-8")
    finally:
        httpd.shutdown()
        httpd.server_close()
    # The static tree remains the no-script fallback; the switcher only works
    # once home.js has started the scene, which draws behind the three columns.
    assert 'id="home-art"' in page
    assert 'id="home-scene"' in page
    assert 'id="scene-styles"' in page
    assert 'data-style="christmas-tree"' in page
    assert 'data-style="token-rain"' in page


def test_scene_modules_are_served():
    httpd, url = server(open_browser=False, blocking=False, port=0)
    try:
        for path in (
            "/js/ascii-scene.js",
            "/js/scene-christmas-tree.js",
            "/js/scene-token-rain.js",
            "/js/home.js",
        ):
            with urlopen(f"{url}{path}") as response:
                assert response.status == 200, path
                assert response.headers.get("Cache-Control") == "no-cache", path
                assert response.read(), path
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_editor_offers_a_new_file_dialog():
    httpd, url = server(open_browser=False, blocking=False, port=0)
    try:
        with urlopen(f"{url}/editor") as response:
            page = response.read().decode("utf-8")
    finally:
        httpd.shutdown()
        httpd.server_close()
    assert 'id="new-file-dialog"' in page
    for mode in ("python", "asm", "sp"):
        assert f'data-mode="{mode}"' in page, mode
    assert 'id="new-file-open"' in page


def test_legacy_index_alias_serves_the_editor():
    httpd, url = server(open_browser=False, blocking=False, port=0)
    try:
        with urlopen(f"{url}/index.html") as response:
            page = response.read().decode("utf-8")
    finally:
        httpd.shutdown()
        httpd.server_close()
    assert 'id="code-editor"' in page


def test_back_link_only_on_secondary_pages():
    httpd, url = server(open_browser=False, blocking=False, port=0)
    try:
        for path in ("/", "/editor"):
            with urlopen(f"{url}{path}") as response:
                assert "back-link" not in response.read().decode("utf-8"), path
        for path in ("/visualize.html", "/studio", "/docs", "/tutorial"):
            with urlopen(f"{url}{path}") as response:
                assert "back-link" in response.read().decode("utf-8"), path
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_docs_page_renders_the_documentation():
    httpd, url = server(open_browser=False, blocking=False, port=0)
    try:
        with urlopen(f"{url}/docs") as response:
            assert response.status == 200
            page = response.read().decode("utf-8")
    finally:
        httpd.shutdown()
        httpd.server_close()
    assert "{{doc_body}}" not in page
    assert "{{doc_toc}}" not in page
    assert '<h1 id="spacelang-project-documentation">' in page
    assert '<h2 id="project-at-a-glance">' in page
    assert '<a class="toc-h2" href="#project-at-a-glance">Project at a glance</a>' in page
    assert "<table>" in page
    assert '<code class="language-bash">' in page


def test_docs_page_reports_a_missing_document(monkeypatch):
    monkeypatch.setattr(server_module, "_document_path", lambda: None)
    httpd, url = server(open_browser=False, blocking=False, port=0)
    try:
        with urlopen(f"{url}/docs") as response:
            assert response.status == 200
            page = response.read().decode("utf-8")
    finally:
        httpd.shutdown()
        httpd.server_close()
    assert "Documentation is unavailable" in page
    assert "build_static" in page


def test_markdown_escapes_raw_html():
    body, toc = markdown_doc.render_document("## Title\n\n<script>alert(1)</script>\n")
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in body
    assert "<script>" not in body
    assert toc == [markdown_doc.TocEntry(2, "Title", "title")]


def test_markdown_tables_keep_escaped_pipes_in_one_cell():
    body, _ = markdown_doc.render_document(
        "| left | right |\n| :--- | ---: |\n| `a\\|b` | **c** |\n"
    )
    assert "<th>left</th>" in body
    assert '<th style="text-align:right">right</th>' in body
    assert "<td><code>a|b</code></td>" in body
    assert '<td style="text-align:right"><strong>c</strong></td>' in body


def test_markdown_nests_lists_by_indentation():
    body, _ = markdown_doc.render_document("- one\n  - two\n- three\n")
    assert "<li>one<ul><li>two</li></ul></li>" in body
    assert body.count("<ul>") == 2


def test_markdown_heading_anchors_are_unique():
    _, toc = markdown_doc.render_document("## Same\n\n## Same\n\n### Same\n")
    assert [entry.anchor for entry in toc] == ["same", "same-1", "same-2"]


def test_documentation_internal_anchors_resolve():
    path = server_module._document_path()
    if path is None:
        pytest.skip("documentation.md is not installed next to this package")
    body, toc = markdown_doc.render_document(path.read_text(encoding="utf-8"))
    anchors = set(re.findall(r'id="([^"]+)"', body))
    targets = set(re.findall(r'href="#([^"]+)"', body))
    assert targets <= anchors
    assert len(toc) >= 20
    # The document has its own "Contents" section; the sidebar replaces it, so
    # it must not be listed twice.
    assert all(entry.anchor != "contents" for entry in toc)


STATIC_ROOT = Path(__file__).resolve().parents[1] / "spacelang" / "opt_sp" / "static"
BUILT_ASSETS = (
    STATIC_ROOT / "pyodide" / "pyodide.js",
    STATIC_ROOT / "spacelang_pkg" / "manifest.json",
)


@pytest.mark.skipif(
    not all(path.is_file() for path in BUILT_ASSETS),
    reason="OPT_SP static assets are produced by tools/build_static.py",
)
def test_static_check_passes():
    tools = Path(__file__).resolve().parents[1] / "tools"
    spec = importlib.util.spec_from_file_location(
        "_opt_sp_build_static", tools / "build_static.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module._check() == 0


def test_static_scripts_must_revalidate():
    # ES module imports carry no version query, so js/ and css/ must not be
    # served from cache without checking; otherwise a version bump on the page
    # leaves the browser running an older module.
    httpd, url = server(open_browser=False, blocking=False, port=0)
    try:
        for path in ("/js/app.js", "/js/sync-engine.js", "/css/opt-sp.css"):
            with urlopen(f"{url}{path}") as response:
                assert response.headers.get("Cache-Control") == "no-cache", path
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_server_assets_use_paths_relative_to_app():
    httpd, url = server(open_browser=False, blocking=False, port=0)
    try:
        with urlopen(f"{url}/editor") as response:
            page = response.read().decode("utf-8")
        assert re.search(r'href="css/opt-sp\.css\?v=\d+"', page), page
        assert re.search(r'src="js/app\.js\?v=\d+"', page), page
        assert 'for="open-project-file-browser">File</label>' in page
        assert 'id="open-project-file-browser"' in page
        assert 'id="project-file-browser"' in page
        assert 'id="close-project-file-browser"' in page
        with urlopen(f"{url}/js/app.js") as response:
            app = response.read().decode("utf-8")
        assert 'fetch("api/files")' in app
        assert 'fetch("__opt_sp/stop"' in app
        assert 'openProjectFileBrowserButton.addEventListener("click"' in app
        assert 'closeProjectFileBrowserButton.addEventListener("click"' in app
        assert 'function updateFileButtonLabel()' in app
        assert 'function updateFileActions()' in app
        assert 'fetch("api/file/new"' in app

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
        with urlopen(f"{url}/editor") as response:
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


def test_server_creates_new_project_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    httpd, url = server(open_browser=False, blocking=False, port=0)

    def create(payload):
        request = Request(
            f"{url}/api/file/new",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        return urlopen(request)

    try:
        with create({"path": "hello.py", "code": "print('hi')\n"}) as response:
            assert response.status == 201
            result = json.load(response)
        assert result == {
            "path": "hello.py",
            "mode": "python",
            "message": "Project file created.",
        }
        assert (tmp_path / "hello.py").read_text(encoding="utf-8") == "print('hi')\n"

        # Creating never replaces: the same name is a conflict, and the original
        # contents survive.
        with pytest.raises(HTTPError) as error:
            create({"path": "hello.py", "code": "print('replaced')\n"})
        assert error.value.code == 409
        assert (tmp_path / "hello.py").read_text(encoding="utf-8") == "print('hi')\n"
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
            f"{url}/api/file/new",
            data=json.dumps({"path": "hello.py", "code": "x"}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with pytest.raises(HTTPError) as error:
            urlopen(request)
        assert error.value.code == 403
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_server_rejects_unsafe_new_file_paths(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    httpd, url = server(open_browser=False, blocking=False, port=0)
    try:
        cases = (
            ({"path": "notes.txt", "code": "x"}, 415),
            ({"path": "../outside.py", "code": "x"}, 400),
            ({"path": "missing-dir/a.py", "code": "x"}, 404),
        )
        for payload, expected in cases:
            request = Request(
                f"{url}/api/file/new",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with pytest.raises(HTTPError) as error:
                urlopen(request)
            assert error.value.code == expected, payload
    finally:
        httpd.shutdown()
        httpd.server_close()
    assert not (tmp_path / "notes.txt").exists()


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
