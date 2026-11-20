# OPT_SP Studio - Implementation Prompt

You are implementing a feature in the SpaceLang repository (a Python package with
a browser-based debugger). Work through the phases below **in order**. Each phase
is independently verifiable and ends with a commit.

This document is written for an autonomous coding agent. It is deliberately
explicit. When it conflicts with your own preferences, follow this document.

---

## 0. Read first

1. Read `docs/studio/PLAN.md` end to end. It is the design authority; this prompt
   is the execution order. If the two disagree, **stop and ask** (see section 13).
2. Read these files before editing them:
   - `spacelang/opt_sp/server.py`
   - `spacelang/opt_sp/__init__.py`
   - `spacelang/web_bridge.py`
   - `spacelang/ir.py`, `spacelang/encoder.py`, `spacelang/decoder.py`,
     `spacelang/disasm.py`, `spacelang/asm.py`
   - `spacelang/opt_sp/static/index.html`, `visualize.html`
   - `spacelang/opt_sp/static/js/app.js`, `visualizer.js`, `spacelang-kernel.js`
   - `tools/build_static.py`, `tests/test_opt_sp.py`, `pyproject.toml`

## 1. Repository facts you may rely on

| Fact | Value |
|---|---|
| Working directory | repository root (contains `spacelang/`, `tools/`, `tests/`) |
| Platform | Windows, PowerShell 5.1 available |
| Python | `.venv\Scripts\python.exe` (3.13). Bare `python` on PATH is a Store stub; **always use the venv path** |
| Test command | `.venv\Scripts\python.exe -m pytest tests/test_opt_sp.py -q` |
| Static check | `.venv\Scripts\python.exe tools/build_static.py --check` |
| Server entry point | `pyproject.toml`: `spacelang-opt-sp = "spacelang.opt_sp.server:_cli"` |
| Public API | `from spacelang.opt_sp import server, open_browser, trace_program` |
| Static pages | `spacelang/opt_sp/static/{index,visualize}.html`, cache-busted with `?v=8` |
| Build artifacts | `static/pyodide/**` and `static/spacelang_pkg/**` are git-ignored and produced by `tools/build_static.py` |
| Working tree | **has uncommitted user edits** to `index.html`, `visualize.html`, `js/app.js`, `css/opt-sp.css` (settings menu, `?v=8`). Do not revert, do not "clean up" |

Key signatures:

```python
# spacelang/opt_sp/server.py
def server(port=8000, host="127.0.0.1", open_browser=True, blocking=True,
           allow_project_files=None, _stop_token=None, _ready_file=None
           ) -> tuple[ThreadingHTTPServer, str] | None
def open_browser(port: int = 8000) -> None
def _cli() -> None                     # argparse flags

# spacelang/web_bridge.py
def trace_program(source: str, is_asm: bool = True, is_sp: bool = False) -> dict

# spacelang/pyfront.py
def compile_py(src: str, filename: str = "<stdin>") -> Program

# spacelang/ir.py
class Instr: op: OP | int; args: list[int | str]; line: int
class Program: instrs; names; labels; funcs; try_table

# spacelang/encoder.py
def encode(program: Program, *, include_names: bool = False) -> str    # -> .sp text
# spacelang/decoder.py
def decode(source: str) -> Program                                     # .sp -> Program
# spacelang/disasm.py
def disassemble(program: Program) -> str                               # -> asm text
# spacelang/asm.py
def assemble(source: str) -> Program                                   # asm -> Program

# spacelang/opt_sp/static/js/spacelang-kernel.js
kernel.init()                 // loads Pyodide + spacelang_pkg, idempotent
kernel.trace(code, mode)      // mode: "asm" | "sp" | "python" -> {ok, trace, error}
```

`Program` fields `names`, `labels`, `funcs`, `try_table` and `Instr.line` are
debug metadata; two front ends legitimately disagree on them. Only `(op, args)`
is semantic.

## 2. Non-negotiable rules

**R1.** Do not change the signature or return value of `server()`. Existing code
does:

```python
httpd, url = server(open_browser=False, blocking=False, port=0)
...
httpd.shutdown(); httpd.server_close()
```

That must keep working.

**R2.** Do not change, remove, or rename any existing CLI flag:
`--port --host --no-browser --background --stop --allow-project-files`,
including the hidden `--_background-token-file` and `--_background-ready-file`.
New flags are additive only. Never add `--llm-api-key` (use
`--llm-api-key-file`).

**R3.** Do not change existing routes or their semantics: `/`, `/index.html`,
`/visualize.html`, `/api/files`, `/api/file`, `/__opt_sp/status`,
`/__opt_sp/stop`. Add new ones.

**R4.** No new runtime dependency. Standard library only. No `npm`, no
`package.json`, no bundler, no CDN `<script>` tags, no TypeScript. Python
dependencies stay empty in `pyproject.toml`.

**R5.** Never write an API key into a tracked file. Never log it, never return it
in a response, never put it in an exception message. Tests use a local stub
server. Add `.env` and `.env.local` to `.gitignore`.

**R6.** `.sp` is whitespace. Never call `.trim()`, never normalise line endings,
never run a formatter, never `JSON.stringify`-roundtrip the `sp` pane text. Read
and write it verbatim. `.sp` is never sent to the LLM.

**R7.** Do not modify the language implementation: `spacelang/pyfront.py`,
`asm.py`, `encoder.py`, `decoder.py`, `disasm.py`, `ir.py`, `vm_*.py`,
`lexer.py`, `parser.py`, `names.py`, `csrc/**`, `native/**`. You may only *call*
them. The single exception is `web_bridge.py`, where you add functions.

**R8.** Run the test suite after every phase. A phase is not done while its own
acceptance command fails. Three pre-existing failures are environment artifacts
on this machine (`test_server_background_cli_start_and_stop` and the two
`project_files` tests, all `PermissionError` on the sandboxed temp directory).
Record them in the commit message and move on. Do **not** "fix" them by changing
production code.

**R9.** Match the surrounding code style: 4-space indent, roughly 88-100 column
lines, `from __future__ import annotations` at the top of Python modules,
double-quoted strings in HTML/JS. No reformatting of untouched lines.

**R10.** After changing any file under `spacelang/*.py` that the browser loads,
run `.venv\Scripts\python.exe tools\build_static.py --no-pyodide` (added in
Phase 0) so `static/spacelang_pkg/` is regenerated.

**R11.** Keep the source tree ASCII-only where practical. Do not introduce smart
quotes, em dashes or arrow glyphs into Python/JS/HTML source; use `--`, `->`,
`...`. The two exceptions are documented in Appendix A: the back-link arrow
(write it as the Python escape `\u2190` in the Python constant, and as the literal
character in the HTML partial) and the middle-dot toggle label.

## 3. What you are building

A third page `/studio` with three writable editors for one program:

```
py      Python surface syntax      <- human or LLM
spasm   assembly text              <- disassemble(program)
sp      encoded token stream       <- encode(program)
```

Deterministic derivation between them; `py` can only be re-derived by an LLM and
must pass a compiler-checked gate. Right-hand state panels and step controls are
shared with the existing visualizer page. All of this is specified in
`docs/studio/PLAN.md`; do not invent alternatives.

---

## Phase 0 - Baseline health

**Goal:** make the suite green for real reasons, and make "Pyodide assets are
missing" a diagnosable condition instead of a blank page.

**Files you may touch:** `tests/test_opt_sp.py`, `spacelang/opt_sp/server.py`,
`tools/build_static.py`, `spacelang/opt_sp/static/js/app.js`,
`spacelang/opt_sp/static/css/opt-sp.css`, new
`spacelang/opt_sp/static/js/health.js`.

### Steps

0.1 **Fix the cache-bust assertion.** In `tests/test_opt_sp.py`,
`test_server_assets_use_paths_relative_to_app` hard-codes `?v=6` while the pages
now use `?v=8`. Replace the two literal assertions with a pattern that survives
future bumps:

```python
import re
...
assert re.search(r'href="css/opt-sp\.css\?v=\d+"', page), page
assert re.search(r'src="js/app\.js\?v=\d+"', page), page
```

0.2 **Add `GET /__opt_sp/health`** (loopback only, like `/api/file`):

```python
def _send_health(self) -> None:
    root = Path(static_dir())
    checks = {
        "pyodide_js": (root / "pyodide" / "pyodide.js").is_file(),
        "python_stdlib": (root / "pyodide" / "python_stdlib.zip").is_file(),
        "spacelang_pkg": (root / "spacelang_pkg" / "manifest.json").is_file(),
        "studio_page": (root / "studio.html").is_file(),   # Phase 1 makes this true
    }
    self._send_json(200, {
        "ok": all(checks.values()),
        "checks": checks,
        "hint": None if all(checks.values())
                else "Run: python tools/build_static.py",
    })
```

Phase 0 acceptance may legitimately report `studio_page: false`.

0.3 **Surface it in the browser.** New module `static/js/health.js`:

```js
export async function checkAssets() {
  try {
    const response = await fetch("__opt_sp/health", { cache: "no-store" });
    if (!response.ok) return;
    const report = await response.json();
    if (report.ok) return;
    const missing = Object.entries(report.checks)
      .filter(([, ok]) => !ok).map(([name]) => name).join(", ");
    const banner = document.createElement("div");
    banner.className = "asset-banner";
    banner.setAttribute("role", "alert");
    banner.textContent =
      `Static assets incomplete (${missing}). ${report.hint ?? ""}`;
    document.body.prepend(banner);
  } catch { /* health is advisory; never break the page */ }
}
```

Import and call it from `app.js` at the end of the module (once,
unconditionally). Add `.asset-banner` styling to `css/opt-sp.css` (warning
colour, full width, small padding).

0.4 **`build_static.py --no-pyodide`.** `_copy_pyodide_distribution()` downloads
about 10 MB from GitHub on every run. Add a flag that skips it when
`static/pyodide/pyodide.js` and `python_stdlib.zip` already exist; `--check`
behaviour is unchanged.

0.5 **Tests.**

```python
def test_health_reports_state()                     # 200, has "ok" and "checks"
def test_health_marks_missing_asset(monkeypatch, tmp_path)   # point static_dir at a temp dir
```

### Acceptance

```
.venv\Scripts\python.exe -m pytest tests/test_opt_sp.py -q
.venv\Scripts\python.exe tools\build_static.py --check
```

`test_server_assets_use_paths_relative_to_app` must pass.

Manual: start the server (`spacelang-opt-sp --port 8011 --no-browser`), open
`http://127.0.0.1:8011/__opt_sp/health`; `ok` is `false` only because
`studio_page` does not exist yet.

**Commit:** `studio(p0): health endpoint, asset banner, resilient cache-bust test`

---

## Phase 1 - Composition and the `/studio` shell

**Goal:** `/studio` returns a real page whose chrome comes from shared partials;
the settings menu opens it in a new tab with the current source.

**Files you may touch:** `server.py`, `static/index.html`,
`static/visualize.html`, new `static/studio.html`, new `static/partials/*.html`,
new `static/css/studio.css`, `static/js/app.js`, new `static/js/handout.js`,
`tools/build_static.py`, `tests/test_opt_sp.py`.

### Steps

1.1 **Create partials** under `static/partials/`:

| File | Contents |
|---|---|
| `app-header.html` | `<header class="app-header">` through `</header>`, containing `{{back_link}}` inside `.server-controls`, and `<!-- #include partials/settings-menu.html -->` |
| `settings-menu.html` | the `#settings-button` and `#settings-menu` block already present in both pages, plus a new first item: `<a id="studio-link" class="settings-menu-item" role="menuitem" href="/studio" target="_blank" rel="noopener">Studio (new tab)</a>` |
| `state-panels.html` | `<section class="state-panels">` with the four `<details>` panels and their resizers |
| `step-controls.html` | `<nav class="step-controls">` with the step and autoplay controls |

Replace the corresponding inline blocks in `index.html` and `visualize.html` with
`<!-- #include partials/... -->`. Preserve the existing element ids exactly:
`#server-status`, `#settings-button`, `#settings-menu`, `#reload-page-button`,
`#stop-server-button`, `#call-stack`, `#operand-stack`, `#heap`, `#output`,
`#autoplay-button`, `#autoplay-speed`, `#autoplay-speed-label`, `#step-slider`,
`#step-label`, and `button[data-step]`. `visualizer.js` binds to them.

`{{back_link}}` renders as `<a class="back-link" href="./">` + U+2190 + ` Back to
editor</a>` on the studio and visualizer pages, and as the empty string on the
editor page.

1.2 **Include pass** in `server.py`, applied inside `_send_controlled_page`:

```python
_INCLUDE_RE = re.compile(
    r"[ \t]*<!-- #include (partials/[A-Za-z0-9_\-/]+\.html) -->[ \t]*\r?\n?")
_MAX_INCLUDE_PASSES = 2   # one level of nesting

def _render_page(self, filename: str) -> bytes:
    root = Path(static_dir())
    text = (root / filename).read_text(encoding="utf-8")
    # includes first: {{back_link}} lives inside partials/app-header.html
    for _ in range(_MAX_INCLUDE_PASSES):
        def replace(match: re.Match[str]) -> str:
            partial = match.group(1)
            if not re.fullmatch(r"partials/[A-Za-z0-9_\-/]+\.html", partial):
                return ""
            path = (root / partial).resolve()
            if not path.is_relative_to(root) or not path.is_file():
                return ""
            return path.read_text(encoding="utf-8")
        text, count = _INCLUDE_RE.subn(replace, text)
        if count == 0:
            break
    text = text.replace("{{back_link}}", self._back_link_for(filename))
    text = text.replace("__OPT_SP_CONTROL_TOKEN__", self.stop_token or "")
    return text.encode("utf-8")
```

Order matters: expanding includes after substituting `{{back_link}}` would leave
the placeholder inside the injected header. Cache by
`(filename, template mtime, partial mtimes)` in a module-level dict; invalidation
on `--check` is unnecessary (process restart). Keep `Cache-Control: no-store` as
today.

`_back_link_for` is a two-line helper:

```python
_BACK_LINK = '<a class="back-link" href="./">\u2190 Back to editor</a>'
_NO_BACK_LINK = {"index.html"}

def _back_link_for(self, filename: str) -> str:
    return "" if filename in _NO_BACK_LINK else _BACK_LINK
```

1.3 **Route `/studio`**: add `"/studio"` to the existing page branch and map it
to `studio.html`. Keep `/`, `/index.html`, `/visualize.html` untouched.

1.4 **`studio.html`**: `<body data-page="studio">`, `?v=8` for CSS and JS,
`<meta name="opt-sp-control-token">`, the header partial, and:

```html
<main class="studio-layout">
  <section class="studio-editors">
    <section class="editor-pane" data-pane="py">
      <h2 class="pane-header"><span>py</span>
        <span id="py-badge" class="pane-badge">synced</span>
        <span class="pane-actions"><button id="py-sync-button" type="button" hidden>Sync with AI</button></span>
      </h2>
      <textarea id="py-editor" class="pane-editor" spellcheck="false" wrap="off"></textarea>
    </section>
    <section class="editor-pane" data-pane="spasm">
      <h2 class="pane-header"><span>spasm</span>
        <span id="spasm-badge" class="pane-badge">synced</span></h2>
      <textarea id="spasm-editor" class="pane-editor" spellcheck="false" wrap="off"></textarea>
    </section>
    <section class="editor-pane" data-pane="sp">
      <h2 class="pane-header"><span>sp</span>
        <span id="sp-badge" class="pane-badge">synced</span>
        <span class="pane-actions">
          <button id="show-spaces-toggle" type="button" aria-pressed="false">show spaces</button>
          <button id="copy-sp-button" type="button">Copy raw</button>
        </span></h2>
      <textarea id="sp-editor" class="pane-editor pane-editor-sp" spellcheck="false" wrap="off"></textarea>
    </section>
  </section>
  <section class="trace-column">
    <pre id="trace-code" class="code-view"></pre>
    <!-- #include partials/state-panels.html -->
  </section>
  <!-- #include partials/step-controls.html -->
</main>
```

Load `js/app.js` exactly as the other pages do; `app.js` dispatches on
`document.body.dataset.page`.

1.5 **`css/studio.css`**: two-column grid
(`minmax(0, 1fr) minmax(320px, 42%)`), collapsing to one column below 1100 px
with the three panes stacked in order and each `min-height: 8rem`.
`.pane-editor { font-family: ui-monospace, monospace; white-space: pre;
overflow: auto; }`. Linked from `studio.html` only.

1.6 **Handout.** New `static/js/handout.js`:

```js
const KEY = "opt-sp-handout";
const TTL_MS = 5 * 60 * 1000;

export function writeHandout(mode, source) {
  try { localStorage.setItem(KEY, JSON.stringify({ mode, source, at: Date.now() })); }
  catch { /* storage may be disabled; the studio still opens empty */ }
}

export function takeHandout() {
  let raw = null;
  try {
    raw = localStorage.getItem(KEY);
    localStorage.removeItem(KEY);
  } catch { return null; }
  if (!raw) return null;
  try {
    const value = JSON.parse(raw);
    if (typeof value?.source !== "string") return null;
    if (!["python", "asm", "sp"].includes(value.mode)) return null;
    if (!(Date.now() - value.at < TTL_MS)) return null;
    return value;
  } catch { return null; }
}
```

In `app.js`, inside the `page === "editor"` branch and the `page === "visualize"`
branch, attach a click listener on `#studio-link` that calls `writeHandout(...)`
**without** `preventDefault()`: the anchor's `target="_blank"` does the opening,
and the handler runs first. Mode mapping: `"python" | "asm" | "sp"`; the editor
page's `<select id="source-mode">` already uses exactly these values, and the
visualizer exposes `visualizer.mode`.

1.7 **`build_static.py`**: add `studio.html`, `css/studio.css`, the four
partials and `js/handout.js` to `_check()`'s required list.

1.8 **Tests.**

```python
def test_studio_route_serves_page()             # 200, "studio-layout" in body, token replaced
def test_pages_have_no_unresolved_includes()    # GET /, /visualize.html, /studio -> no "<!-- #include"
def test_back_link_only_on_secondary_pages()    # index has none; studio and visualize do
def test_static_check_passes()                  # build_static._check() returns 0
```

### Acceptance

```
.venv\Scripts\python.exe -m pytest tests/test_opt_sp.py -q
.venv\Scripts\python.exe tools\build_static.py --no-pyodide
.venv\Scripts\python.exe tools\build_static.py --check
```

Manual: `/` renders unchanged; the gear menu has "Studio (new tab)"; clicking it
opens `/studio` in a new tab; `/studio` shows three empty panes.

**Commit:** `studio(p1): shared partials, /studio shell, cross-tab handout`

---

## Phase 2 - Conversion graph and sync engine

**Goal:** editing any pane deterministically updates the others where a rule
exists; `py` becomes `stale` when it cannot be derived.

**Files you may touch:** `spacelang/web_bridge.py`,
`static/js/spacelang-kernel.js`, new `static/js/sync-engine.js`,
`static/js/app.js`, `static/css/studio.css`, `tests/test_opt_sp.py`, new
`tests/test_web_bridge_convert.py`.

### Steps

2.1 **`web_bridge.convert`**: one round trip, all destinations.

```python
_SUPPORTED = ("py", "spasm", "sp")

def canon(program) -> list[tuple[int, tuple]]:
    return [(int(instr.op), tuple(instr.args)) for instr in program.instrs]

def convert(source: str, src: str) -> dict:
    """{"ok": bool, "texts": {"spasm": str, "sp": str}, "error": str|None}"""
    if src not in _SUPPORTED:
        return {"ok": False, "texts": {}, "error": f"unknown source kind {src!r}"}
    try:
        if src == "py":
            program = compile_py(source)
        elif src == "spasm":
            program = assemble(source)
        else:
            program = decode(source)
    except Exception:
        return {"ok": False, "texts": {}, "error": traceback.format_exc()}
    texts: dict[str, str] = {}
    if src != "spasm":
        texts["spasm"] = disassemble(program)
    if src != "sp":
        texts["sp"] = encode(program, include_names=True)
    return {"ok": True, "texts": texts, "error": None}
```

`include_names=True` is mandatory: without the name table, `spasm` loses every
symbol.

2.2 **`web_bridge.verify_py`**:

```python
def verify_py(py_src: str, spasm_src: str) -> dict:
    try:
        want = canon(assemble(spasm_src))
    except Exception:
        return {"ok": False, "error": "assembly_unparsable",
                "detail": traceback.format_exc()}
    try:
        got = canon(compile_py(py_src))
    except Exception:
        return {"ok": False, "error": "python_unparsable",
                "detail": traceback.format_exc()}
    return {"ok": want == got, "want_len": len(want), "got_len": len(got),
            "error": None if want == got else "not_equivalent"}
```

Update `__all__`. Do not change `trace_program`.

2.3 **Kernel**: extend the import line in `initialize()` from
`from spacelang.web_bridge import trace_program` to
`from spacelang.web_bridge import trace_program, convert`, then add a `convert`
method mirroring `trace`:

```js
async convert(source, src) {
  const runtime = await this.init();
  const result = await runtime.runPythonAsync(
    `convert(${JSON.stringify(source)}, ${JSON.stringify(src)})`);
  try { return result.toJs({ dict_converter: Object.fromEntries }); }
  finally { result.destroy(); }
}
```

2.4 **`sync-engine.js`**: a `SyncEngine` class.

```js
const EDGES = { py: ["spasm", "sp"], spasm: ["sp"], sp: ["spasm"] };
const DEBOUNCE_MS = 250;

class SyncEngine {
  constructor({ panes, onStateChange })   // panes: {py, spasm, sp} -> HTMLTextAreaElement
  async derive(src, revision)
  markStale(pane)
}
```

Requirements:

- 250 ms debounce per source pane; one in-flight derivation per pane; a newer
  edit increments `revision` and older results are dropped.
- Programmatic writes set `pane.dataset.applying = "1"` and are ignored by the
  input handler. These panes do not get the `editor.js` undo bindings, so there
  is no undo-stack problem to solve.
- Caret preservation: remember `selectionStart` and `selectionEnd`, rewrite,
  clamp and restore.
- `py` becomes `stale` whenever the authoritative pane is `spasm` or `sp`.
- Conversion failure marks the destination `error` and leaves its text untouched.
- No `.trim()`, no line-ending normalisation, no autocomplete binding on `sp`.

2.5 **`app.js`**: inside the `page === "studio"` branch, construct the engine,
seed from `takeHandout()` (Phase 1), and keep the three badges in sync
(`synced` / `stale` / `error`).

2.6 **Tests** (`tests/test_web_bridge_convert.py`, no browser needed):

```python
def test_py_to_spasm_and_sp_roundtrip()
def test_spasm_to_sp_roundtrip()
def test_convert_reports_unknown_source()
def test_convert_reports_syntax_error()          # "def (" -> ok False
def test_verify_py_accepts_equivalent_rewrite()
def test_verify_py_rejects_semantic_change()
def test_canon_ignores_line_numbers()
```

Use a fixed sample program (three instructions plus one function) and assert
`canon(assemble(asm)) == canon(compile_py(py))` for a hand-written equivalent.

### Acceptance

```
.venv\Scripts\python.exe -m pytest tests/test_web_bridge_convert.py -q
.venv\Scripts\python.exe -m pytest tests/test_opt_sp.py -q
.venv\Scripts\python.exe tools\build_static.py --no-pyodide
```

Manual: paste a `.py` sample into the `py` pane; `spasm` and `sp` fill in; edit
`spasm` and the `py` badge shows `stale`; paste garbage into `spasm` and the
badge shows `error` while the other panes stay unchanged.

**Commit:** `studio(p2): conversion graph, compiler-checked verifier, sync engine`

---

## Phase 3 - Trace panels

**Goal:** `Run` in the studio traces the authoritative pane and drives the shared
panels and step controls.

**Files you may touch:** `static/js/visualizer.js`, new
`static/js/trace-panel.js`, `static/js/app.js`, `static/css/opt-sp.css`,
`static/css/studio.css`.

### Steps

3.1 **Extract, do not fork.** Move the rendering members out of `Visualizer` into
`TracePanel` in `trace-panel.js`:

```js
export class TracePanel {
  constructor({ root, codeRoot, trace, sourceText, mode }) {}
  render(stepIndex) {}
  bindControls() {}
  bindPanelResizers() {}
  bindPanelReordering() {}
}
```

`Visualizer` keeps its constructor signature and public members (`mode`,
`sourceText`, `liveMode`, `liveEditor`, `bindLiveEditing`, `updateLiveTrace`,
`render`) and delegates to a `TracePanel` instance. The existing
`visualize.html` must behave identically: no id changes, no markup changes.

3.2 **Studio wiring**: `Run` traces the authoritative pane with the matching mode
(`py` -> `"python"`, `spasm` -> `"asm"`, `sp` -> `"sp"`), renders into
`#trace-code` plus the four panels, and enables the step controls. Trace errors
are shown in the panels area, not thrown.

3.3 Keep `sessionStorage["opt-sp-trace"]` and the index-to-visualize flow exactly
as it is.

### Acceptance

```
.venv\Scripts\python.exe -m pytest tests/test_opt_sp.py -q
.venv\Scripts\python.exe tools\build_static.py --check
```

Manual: `/` then Run then visualize still works, all four panels and autoplay
behave as before; `/studio`, edit py, Run, panels populate and the step slider
advances.

**Commit:** `studio(p3): extract TracePanel, wire studio tracing`

---

## Phase 4 - AI mirror sync (non-streaming)

**Goal:** a verified, rate-limited, server-side LLM rewrite of the `py` mirror.

**Files you may touch:** new `spacelang/llm_client.py`, new
`spacelang/opt_sp/llm_proxy.py`, `server.py`, `spacelang/opt_sp/__init__.py`,
`static/js/app.js`, new `static/js/llm-bridge.js`, new
`static/js/llm-settings.js`, `static/css/studio.css`, `.gitignore`, new
`tests/test_llm_proxy.py`, `tests/test_opt_sp.py`.

### Steps

4.1 **`LLMConfig`** in `llm_proxy.py`; export from `spacelang.opt_sp`:

```python
@dataclass(frozen=True)
class LLMConfig:
    base_url: str = "https://socratic.cs.cityu.edu.hk/litellm/v1"
    model: str = "Socrates"
    api_key: str | None = None
    mode: str = "manual"            # manual | auto | off
    max_output_tokens: int = 4096
    temperature: float = 0.2
    timeout: float = 90.0
```

4.2 **`server(..., llm=None)`**: accept `LLMConfig | dict | None`; keep it an
optional keyword so existing calls are unchanged. Resolution order: per-request
headers, then CLI, then environment, then defaults.

```python
DEFAULT_BASE_URL = "https://socratic.cs.cityu.edu.hk/litellm/v1"
# env: LITELLM_BASE_URL, LITELLM_MODEL, LITELLM_API_KEY
```

4.3 **CLI**: add `--llm-base-url`, `--llm-model`, `--llm-api-key-file`,
`--llm-mode {manual,auto,off}`. `--llm-api-key-file` reads the first non-empty
line, strips whitespace, errors if the file is missing. No plaintext key flag.

4.3b **Background mode must forward the LLM flags.** `_start_background` builds
the child command list; append the new flags when supplied, otherwise
`--background` silently loses the configuration:

```python
command = [sys.executable, "-c", "from spacelang.opt_sp.server import _cli; _cli()",
           "--host", host, "--port", str(port),
           "--_background-token-file", str(state_file),
           "--_background-ready-file", str(ready_file)]
if llm_base_url:  command += ["--llm-base-url", llm_base_url]
if llm_model:     command += ["--llm-model", llm_model]
if llm_key_file:  command += ["--llm-api-key-file", str(llm_key_file)]
if llm_mode:      command += ["--llm-mode", llm_mode]
```

Pass the resolved values into `_start_background` as parameters (it currently
takes only `host`, `port`, `open_browser`).

4.4 **`llm_client.py`** (standard library only): `chat(base_url, api_key, model,
messages, max_tokens, temperature, timeout, stream)`. Non-streaming returns
`{"content", "reasoning", "usage", "finish_reason"}`. Read only
`choices[0].message.content` for the answer; keep `reasoning_content` separate.
Map failures:

| Condition | Code |
|---|---|
| HTTP 401 or 403 | `bad_key` |
| HTTP 429 | `rate_limited` |
| HTTP 5xx, URLError, timeout | `upstream_error` |
| `finish_reason == "length"` | `truncated` |
| empty `content` | `empty_completion` |

4.5 **Prompt builder** in `llm_proxy.py`:

```
system: You are the Python mirror maintainer for SpaceLang. SpaceLang programs are
        assembled from integer opcodes. The user edits the low-level form; you keep
        a readable Python mirror in sync. Reply with Python code only, no prose, no
        Markdown fences.

user:   ## Current Python mirror
        ```python
        {py}
        ```
        ## Current program (assembly)
        {spasm}
        ## Task
        Produce a Python mirror that compiles to exactly the same program.
        Preserve existing names, helpers, docstrings and structure where the
        change allows.
```

Reject with `input_too_large` above 12 000 characters total. Do **not** truncate.

4.6 **Token bucket** (module-local, process-wide): 40 tokens per minute, burst 4,
`time.monotonic` plus `collections.deque`. `acquire()` returns `None` on success
or the number of seconds to wait. One in-flight request at a time (a
`threading.Lock`) and one queued request; a newer request replaces the queued one.

4.7 **`POST /api/refine-py`** (JSON in this phase; SSE in Phase 5):

```json
{ "py": "...", "spasm": "...", "src_kind": "sp" | "spasm" }
```

Validation: loopback peer; `Content-Type: application/json`; body at most 64 KiB;
`py` and `spasm` present and `str`; any key named `"sp"` is rejected with `400
sp_not_allowed`; unknown keys rejected. Responses:

```json
{"ok": true, "py": "...", "verified": true, "usage": {}, "model": "Socrates"}
{"ok": false, "error": "not_equivalent", "diff": {"want": 42, "got": 40, "first": ["PUSH_INT 7", "CALL 2"]}}
{"ok": false, "error": "rate_limited", "retry_after": 3}
```

Run `verify_py` in the server process. A failed verification is an error, never a
success with `verified: false`.

4.8 **`GET /api/llm-status`**: `{base_url, model, mode, key_present, key_source,
limits: {rpm: 40}, verified_endpoint: bool}`. `key_source` is one of
`request`, `file`, `env`, `none`. Never the key, never its length.

4.9 **Front-end**: `llm-bridge.js` (fetch, AbortController, error mapping) and
`llm-settings.js` (the panel specified in PLAN section 12.3). Headers:
`X-LLM-Base-URL`, `X-LLM-Model`, `X-LLM-Key`, `X-LLM-Mode`. On success: replace
`py`, badge `synced`, toast `mirror verified`. On `not_equivalent`: keep the text,
show `mirror rejected - {n}/{total} instructions differ` with a "Try again"
button. There is no "apply anyway" path.

4.10 **`.gitignore`**: append `.env` and `.env.local`.

4.11 **Tests** (`tests/test_llm_proxy.py`), all against a local stub server:

```python
def test_refine_py_happy_path(stub_llm)
def test_refine_py_rejects_sp_field(stub_llm)
def test_refine_py_rejects_non_loopback(monkeypatch)
def test_refine_py_rate_limited(stub_llm)
def test_refine_py_truncated_response(stub_llm)
def test_refine_py_empty_content(stub_llm)
def test_refine_py_not_equivalent(stub_llm)
def test_llm_status_hides_key()
def test_config_precedence()
def test_server_llm_kwarg_accepts_dict_or_config()
def test_background_forwards_llm_flags(monkeypatch)
```

The stub is a `ThreadingHTTPServer` on `127.0.0.1:0` serving
`/v1/chat/completions` with a canned body, passed via
`server(..., llm={"base_url": stub_url, "api_key": "test"})`. **No test may
contact the real endpoint.**

### Acceptance

```
.venv\Scripts\python.exe -m pytest tests/test_llm_proxy.py -q
.venv\Scripts\python.exe -m pytest tests/test_opt_sp.py -q
.venv\Scripts\python.exe tools\build_static.py --no-pyodide
```

Manual (real key in `.env.local`, never committed): edit `sp`, click "Sync with
AI", expect roughly 7 s of waiting, then a verified `py` or a rejection message.

**Commit:** `studio(p4): LLM config, proxy, rate limit, verification gate`

---

## Phase 5 - Streaming

> **Superseded.** Phase 4 shipped against a deployment where disabling the
> model's hidden reasoning (`chat_template_kwargs.enable_thinking=false`) turns
> the call into ~0.4 s, 19 output tokens. Streaming existed to hide six seconds
> of reasoning that turned out to be a pathological loop, so the JSON path is
> kept and this phase is deferred. It remains valid if a future endpoint cannot
> disable thinking, or once prompts grow large enough that a full listing has to
> be sent.

**Goal:** stop showing six seconds of nothing.

**Files you may touch:** `server.py`, `spacelang/llm_client.py`,
`spacelang/opt_sp/llm_proxy.py`, `static/js/llm-bridge.js`, `static/js/app.js`,
`static/css/studio.css`, `tests/test_llm_proxy.py`.

### Steps

5.1 **Server framing.** Inside the streaming branch only, before writing the
status line:

```python
self.protocol_version = "HTTP/1.1"
self.send_response(200)
self.send_header("Content-Type", "text/event-stream; charset=utf-8")
self.send_header("Cache-Control", "no-cache")
self.send_header("Connection", "close")
self.send_header("X-Accel-Buffering", "no")
self.send_header("Transfer-Encoding", "chunked")
self.end_headers()
```

Chunk writer:

```python
def _sse(self, event: str, payload: dict) -> None:
    data = f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n".encode()
    self.wfile.write(f"{len(data):X}\r\n".encode("ascii") + data + b"\r\n")
    self.wfile.flush()
```

Terminate with `b"0\r\n\r\n"` in a `finally`. The handler inherits HTTP/1.0, so
`protocol_version` **must** be set per request; do not change it globally.

5.2 **Events** (exact names):

```
event: status   data: {"phase": "connecting" | "sending" | "thinking", "elapsed_ms": 3120}
event: delta    data: {"text": "def add_item(items, name, qty):\n"}
event: done     data: {"ok": true, "py": "...", "verified": true, "usage": {}}
event: error    data: {"ok": false, "error": "truncated", "message": "..."}
```

Only `delta.content` becomes a `delta` event. `reasoning_content` never does; it
only advances the `thinking` status (send one status every second while
reasoning).

5.3 **Upstream**: `stream: true` and `stream_options: {"include_usage": true}`.
Parse `data:` lines, stop at `data: [DONE]`, and treat a mid-stream exception as
`upstream_error`, never as a short but valid program.

5.4 **Client**: `llm-bridge.js` reads the body with a `ReadableStream`
(`response.body.getReader()` plus `TextDecoder`, or `TextDecoderStream` where
available), splits lines, dispatches events, and aborts both legs through
`AbortController` on "Cancel". On abort, show `cancelled` and keep the old `py`.

5.5 **UI**: while `thinking`, the `py` pane header shows `thinking... {s}s`;
`delta` text appears in the pane with `py` marked `editing` (it is a write, not a
user edit, so set the `applying` flag). On `done`, run the same replace-or-reject
path as Phase 4.

5.6 **Tests.** Extend the stub to emit a canned SSE stream:
`test_refine_py_streams_events` (asserts `status`, `delta`, `done` framing and the
terminating chunk) and `test_refine_py_stream_ignores_reasoning`.

### Acceptance

```
.venv\Scripts\python.exe -m pytest tests/test_llm_proxy.py -q
.venv\Scripts\python.exe -m pytest tests/test_opt_sp.py -q
```

Manual: `curl -N -X POST .../api/refine-py` shows event frames as they happen;
the browser shows `thinking...` and then code appearing progressively.

**Commit:** `studio(p5): SSE streaming proxy and progressive UI`

---

## Phase 6 - Documentation and polish

**Files:** `docs/studio/README.md` (new), `README.md` (one section),
`documentation.md` (one section).

6.1 `docs/studio/README.md`: how to run, the three panes, what `stale` means, how
to configure the LLM (Settings, CLI, env), the 40 RPM caveat, and the
"assets missing" banner.

6.2 `README.md`: a three-line pointer to `/studio` in the OPT_SP paragraph.

6.3 `documentation.md`: a `### Studio` subsection under the OPT_SP section,
covering the conversion graph and the verification gate.

6.4 Final sweep: `git diff --check`, no stray `console.log`, and every new file
listed in `build_static.py --check`.

**Commit:** `studio(p6): documentation for /studio`

---

## 12. Definition of done

- [ ] `.venv\Scripts\python.exe -m pytest tests/test_opt_sp.py -q` passes except
      the three documented sandbox `PermissionError` cases, recorded in the
      commit message.
- [ ] `.venv\Scripts\python.exe -m pytest tests/test_web_bridge_convert.py tests/test_llm_proxy.py -q` passes.
- [ ] `.venv\Scripts\python.exe tools\build_static.py --check` passes.
- [ ] `spacelang-opt-sp --port 8000`, `--background` and `--stop` behave exactly
      as before; `/` and `/visualize.html` are unchanged.
- [ ] `server(...)` returns `(httpd, url)`; `.shutdown()` and `.server_close()`
      work; `python -c "from spacelang.opt_sp import server"` imports cleanly.
- [ ] No key in any tracked file, log line, response body or error message.
- [ ] No `npm`, no new Python dependency, no CDN script tag.
- [ ] `/studio` works end to end with a real key: edit, derive, stale, sync,
      verified mirror.
- [ ] Every phase has its own commit with the message given above.

## 13. Stop and ask conditions

Stop and report instead of guessing when:

1. A required change would alter `server()`'s signature, the CLI flags, or an
   existing route.
2. The verification gate rejects more than two out of three real rewrites; the
   prompt or the acceptance rule needs a human decision, not a workaround.
3. `web_bridge.convert` cannot round-trip a simple program
   (`py -> spasm -> sp -> spasm`); the encoder/decoder contract is not what this
   document assumes.
4. You feel the need to make `opt_sp(config=...)` callable; a package is not a
   function. Report instead of adding `__call__` hacks.
5. The upstream endpoint returns a shape this document does not describe, for
   example no `choices[0].delta` in a stream.
6. You are tempted to add "apply anyway" to the verification gate. That is
   explicitly out of scope.

## Appendix A - exact strings

UI copy (English, use verbatim except where a character is spelled out):

| Where | Text |
|---|---|
| Settings item 1 | `Studio (new tab)` |
| Settings item 2 | `LLM settings` |
| Auto mode note | `Auto syncs the Python mirror about 1.5 s after you stop editing. It shares a 40 requests/min quota with everyone using the same key.` |
| Stale badge | `stale` |
| Sync button | `Sync with AI` |
| Thinking | `thinking... {seconds}s` (three ASCII dots) |
| Verified toast | `mirror verified` |
| Rejected | `mirror rejected - {n}/{total} instructions differ` |
| Truncated | `model produced no code (truncated) - try again` |
| Asset banner | `Static assets incomplete ({names}). Run: python tools/build_static.py` |
| Key rejected | `API key rejected (401). Check Settings.` |
| Throttled | `too many AI requests - retry in {n}s` |
| Back link | U+2190 followed by ` Back to editor` |

The back-link arrow is the only non-ASCII glyph in the new source. Put it in the
Python constant as the escape `\u2190` and in the HTML partial as the literal
character.

Headers: `X-LLM-Base-URL`, `X-LLM-Model`, `X-LLM-Key`, `X-LLM-Mode`.
localStorage keys: `opt-sp-handout`, `opt-sp-llm`.
SSE events: `status`, `delta`, `done`, `error`.
Error codes: `bad_key`, `rate_limited`, `upstream_error`, `truncated`,
`empty_completion`, `not_equivalent`, `input_too_large`, `sp_not_allowed`,
`unparsable`, `cancelled`.

## Appendix B - file policy

May create:

```
docs/studio/README.md
spacelang/llm_client.py
spacelang/opt_sp/llm_proxy.py
spacelang/opt_sp/static/studio.html
spacelang/opt_sp/static/partials/app-header.html
spacelang/opt_sp/static/partials/settings-menu.html
spacelang/opt_sp/static/partials/state-panels.html
spacelang/opt_sp/static/partials/step-controls.html
spacelang/opt_sp/static/css/studio.css
spacelang/opt_sp/static/js/handout.js
spacelang/opt_sp/static/js/health.js
spacelang/opt_sp/static/js/sync-engine.js
spacelang/opt_sp/static/js/trace-panel.js
spacelang/opt_sp/static/js/llm-bridge.js
spacelang/opt_sp/static/js/llm-settings.js
tests/test_web_bridge_convert.py
tests/test_llm_proxy.py
```

May modify:

```
spacelang/opt_sp/server.py
spacelang/opt_sp/__init__.py
spacelang/web_bridge.py
spacelang/opt_sp/static/index.html
spacelang/opt_sp/static/visualize.html
spacelang/opt_sp/static/js/app.js
spacelang/opt_sp/static/js/visualizer.js
spacelang/opt_sp/static/js/spacelang-kernel.js
spacelang/opt_sp/static/css/opt-sp.css
tools/build_static.py
tests/test_opt_sp.py
.gitignore
README.md
documentation.md
docs/studio/PLAN.md            (only to record a decision the human approved)
```

Must not touch:

```
spacelang/pyfront.py  spacelang/asm.py  spacelang/encoder.py  spacelang/decoder.py
spacelang/disasm.py   spacelang/ir.py   spacelang/vm_*.py     spacelang/lexer.py
spacelang/parser.py   spacelang/names.py
csrc/**  native/**  benchmarks/**  remotion/**  tests/test_0*/  tests/test_m*.py
.github/workflows/**
pyproject.toml        (no new dependencies; scripts section unchanged)
```

## Appendix C - measured upstream behaviour

Deployment: `https://socratic.cs.cityu.edu.hk/litellm/v1`, model `Socrates`,
measured 2026-11-20. Design accordingly; do not "optimise" these away.

| Behaviour | Consequence for the code |
|---|---|
| Response includes `message.reasoning_content` and `usage.completion_tokens_details.reasoning_tokens` | Never concatenate it into the mirror; only `content` is code |
| `max_tokens=1500` returns HTTP 200 with empty `content` and `finish_reason: "length"` | Treat as `truncated`; default 4096 |
| Realistic rewrite: 7.3 s total, 6.0 s before the first content byte | Streaming is required; show `thinking...` |
| `stream: true` works, `text/event-stream`, first byte 0.2 s | Use it; `[DONE]` sentinel |
| `usage` absent in streams unless `stream_options.include_usage` | Send that option |
| `reasoning_effort` accepted but ineffective; `chat_template_kwargs.enable_thinking=false` returns empty | Do not expose either as a knob |
| Invalid key returns a clean `401` JSON body | Map to `bad_key` |
| Limits: 40 requests/min, 500 000 tokens/min, shared | Token bucket plus single-flight |
| `/models` lists only `Socrates` | Default model name is exactly that |

## Appendix D - notes for the human reviewer

- The working tree already contains uncommitted UI edits (settings menu,
  `?v=8`). They are the starting point, not noise.
- `tests/test_opt_sp.py::test_server_background_cli_start_and_stop` and the two
  `project_files` tests fail in this sandbox because the temp directory denies
  file creation. They pass on CI.
- `tools/build_static.py` currently re-downloads about 10 MB of Pyodide on every
  run; Phase 0 adds `--no-pyodide` so the inner loop is fast.
