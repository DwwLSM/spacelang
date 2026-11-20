# OPT_SP Studio — Design Plan

Status: draft for review
Scope: new multi-pane editing page (`/studio`) for the OPT_SP visual debugger
Applies to: `spacelang` 0.2.x working tree (branch `main`, uncommitted UI edits present)

---

## 1. Context

SpaceLang's source language `.sp` is a token stream encoded as runs of spaces
(`spacelang/encoder.py:133` emits `" " * value + "\n"` per token). Human readers
cannot read it, which is the point: the language is designed for an environment
where visible code is destroyed. `.py` is an *optional surface syntax* lowered to
`.sp`; `spasm` is the assembly rendering of the same program.

The debugger (`spacelang-opt-sp`) serves a browser UI. Compilation and tracing run
entirely inside the browser via Pyodide. The Python server only serves static
assets plus a small JSON API.

Today the UI has two pages:

- `/` (`index.html`) — single-editor entry point; `Run` traces and navigates to
  `visualize.html` via `sessionStorage["opt-sp-trace"]`.
- `/visualize.html` — trace player: code panel + Live edit textarea, and the
  state panels (Call Stack / Operand Stack / Heap / Output) plus step controls.

The two pages duplicate their header chrome and the state-panel markup.

## 2. Goal

A third page, `/studio`, where one program is edited simultaneously in three
representations:

| Pane | Content | Produced by |
|---|---|---|
| `py` | Python surface syntax | human / LLM |
| `spasm` | assembly text | `disassemble(program)` |
| `sp` | encoded token stream (spaces) | `encode(program)` |

Editing any pane re-derives the others where a deterministic rule exists. The
readable mirror (`py`) can only be re-derived by an LLM, so an explicit,
verified "AI mirror sync" action exists. The right-hand state panels and the step
controls are the same ones the existing visualizer uses, and must not be
duplicated in source.

## 3. Non-goals

- No Node.js / Express rewrite. The server stays Python (ADR-001).
- No front-end framework, bundler, or `npm` in the runtime path (ADR-002).
- No offline/on-premise LLM. Only the configured OpenAI-compatible endpoint.
- No changes to the `spc`/`spvm` compiler or the C++ VM.
- No change to the `.sp` format, the opcode set, or the encoder.
- No multi-user server, no authentication layer for the studio page.

## 4. Hard constraints

| # | Constraint | Source |
|---|---|---|
| C1 | `spacelang-opt-sp` CLI keeps every existing flag and behaviour | `server.py:_cli` |
| C2 | `spacelang.opt_sp.server(port, host, open_browser, blocking, allow_project_files)` keeps its signature and its `(httpd, url)` return | `server.py:324` |
| C3 | `httpd.shutdown()` / `httpd.server_close()` stay valid; `tests/test_opt_sp.py` calls them | `test_opt_sp.py` |
| C4 | Existing routes `/`, `/index.html`, `/visualize.html`, `/api/files`, `/api/file`, `/__opt_sp/status`, `/__opt_sp/stop` unchanged | `server.py:60-99` |
| C5 | `pip install spacelanguage` still runs with no extra runtime dependency | `pyproject.toml` |
| C6 | `.sp` never leaves the machine (not sent to the LLM) | ADR-007 |
| C7 | Tests stay green: `pytest tests/test_opt_sp.py` | `.github/workflows/opt-sp-smoke.yml` |

## 5. Architecture decisions

### ADR-001 — Keep the server in Python

Rejected: `server.js` + Express.

Reasons:
1. `pip install` must remain self-contained (C5). A Node runtime cannot be
   shipped in a wheel: `node.exe` is ~80 MB, PyPI caps a single file at 100 MB,
   and wheels are per-interpreter (cp310–cp314) × per-platform.
2. The server's real surface is 4 HTML routes, 4 JSON endpoints, a stop token,
   and a background supervisor — `ThreadingHTTPServer` handles all of it.
3. The recurring failure "server starts but Pyodide never loads" is an asset
   problem, not a language problem; adding a runtime makes it worse.

`ThreadingHTTPServer` gives one thread per request, which is sufficient for a
handful of concurrent long-running LLM proxying calls.

### ADR-002 — No build step for the front end

Native ES modules only. `static/js/*.js` are served as written. No React, no
Vite, no TypeScript. Rationale: `tools/build_static.py --check` validates the
static tree, and CI has no `npm` step; introducing a bundler would put a build
artifact between source and wheel.

### ADR-003 — `/studio` is an added route, not a replacement

`static/studio.html` is a new file. Server gains one route. `index.html` and
`visualize.html` keep rendering exactly as today (C4). The settings menu gains
one entry that opens `/studio` in a new tab.

### ADR-004 — `py` is a derived mirror, not the source of truth

`.sp` is the artifact the project ships; `.py` is a convenience surface. When
`spasm` or `sp` changes, `py` becomes **stale** — the normal state, not an error.
`Program → py` has no deterministic implementation in the repo
(`pyfront.py` only implements `compile_py`), so staleness is resolved only by
the LLM, on demand.

### ADR-005 — AI output is accepted only if the compiler agrees

An LLM-produced `py` is valid only if `compile_py(py)` produces the same
instruction stream as `decode(sp)` (ignoring `Instr.line`, name table, labels and
debug tables). Verification runs in Pyodide, costs microseconds, and is the only
reliable guard against a fluent-but-wrong rewrite. Failure keeps the old `py`.

### ADR-006 — Streaming from the first release

Measured on the target deployment: a realistic rewrite takes **7.3 s total, of
which 6.0 s is hidden reasoning**. A spinner for six seconds is not acceptable,
so the endpoint streams (SSE) and the UI shows `thinking…` progress before code
appears. See §11 and Appendix A.

### ADR-007 — The secret does not leave the machine

`sp` is the encoded artifact the project ships. `spasm` is a readable equivalent
(`assemble(spasm)` reproduces the same `Program`) and `sp` is regenerated locally
with `encode(include_names=True)`. Therefore the LLM request carries `py` +
`spasm` only, never `.sp`.

Four reasons, strongest first:

1. **It is unnecessary.** `spasm` already describes the program completely. The
   task is "read the program, write an equivalent Python mirror"; the assembly is
   the better input.
2. **It is better input.** `disassemble()` emits `.name` and `.label`
   directives, so the model sees real symbols. An encoded `.sp` without a name
   table has no names at all and invites output full of `v0`, `v1`.
3. **Token cost.** `.sp` is one line of N spaces per token. A 300-instruction
   program is tens of thousands of whitespace characters — burning the shared
   500 000 TPM budget on spaces for a worse result.
4. **Positioning.** The project's premise is that the encoded artifact is what
   survives when visible code does not. Posting it to a third-party gateway puts
   the artifact into somebody else's request log.

**Honest scope.** This is a positioning and hygiene decision, **not a
confidentiality guarantee**: anyone holding `spasm` can rebuild `.sp` locally
with `assemble` + `encode`. What it buys is (a) no `.sp` bytes in third-party
logs, (b) smaller and more legible requests, (c) consistency with the project's
premise, (d) a payload shape that is easy to validate and test.

Enforcement: the server rejects any payload containing a `sp` key
(`test_refine_py_rejects_sp`), the client builds requests from `py` + `spasm`
only, and no `.sp` content is ever logged.

### ADR-008 — Cross-tab handoff via `localStorage`, one-shot

`sessionStorage` is per-tab; the studio opens in a new tab. The launching page
writes `localStorage["opt-sp-handout"]` and the studio consumes and deletes it.

## 6. Current-state inventory

Files that matter (line counts from the working tree):

```
spacelang/opt_sp/server.py               626  HTTP server, routing, token, background mode
spacelang/opt_sp/__init__.py              10  exports server/open_browser/trace_program
spacelang/web_bridge.py                   30  trace_program(source, is_asm, is_sp)
spacelang/pyfront.py                    1523  compile_py (Python -> Program); no reverse
spacelang/ir.py                           81  OP enum, Instr, Program
spacelang/encoder.py                     152  encode(Program, include_names=False) -> .sp text
spacelang/decoder.py                      12  decode(.sp text) -> Program
spacelang/asm.py                          —   assemble(asm text) -> Program
spacelang/disasm.py                       67  disassemble(Program) -> asm text
spacelang/opt_sp/static/index.html        86  editor page
spacelang/opt_sp/static/visualize.html    83  trace page
spacelang/opt_sp/static/js/app.js        543  page dispatch, run/visualize wiring
spacelang/opt_sp/static/js/visualizer.js 543  Visualizer class (render + live edit)
spacelang/opt_sp/static/js/editor.js      —   undo/redo, auto-complete, drag
spacelang/opt_sp/static/js/spacelang-kernel.js 53  Pyodide bootstrap + kernel.trace
tools/build_static.py                     —   stages Pyodide + spacelang_pkg (gitignored)
```

Facts that constrain the design:

1. `static/spacelang_pkg/**` and `static/pyodide/**` are **build artifacts**
   (`.gitignore`), produced by `tools/build_static.py`. Any change to
   `spacelang/web_bridge.py` requires re-running it before the browser sees it.
2. `build_static.py --check` only verifies presence and non-emptiness, not
   freshness. (§17 proposes a digest check.)
3. `_send_controlled_page()` already performs server-side placeholder
   substitution (`__OPT_SP_CONTROL_TOKEN__`). The templating mechanism in §7.2
   is an extension of that, not a new concept.
4. `visualizer.js` binds to fixed element ids (`#code-view`, `#live-editor`,
   `#call-stack`, …), so reuse requires either the same ids in the studio page
   or a split of rendering from binding.
5. `tests/test_opt_sp.py` hard-codes the cache-busting query string (`?v=6`);
   the working tree already bumped the pages to `?v=8`.

## 7. Server changes

### 7.1 New route

```python
elif request.path == "/studio":
    self._send_controlled_page("studio.html")
```

Added to the existing `do_GET` branch that already handles `/` and
`/visualize.html`. No other route changes.

### 7.2 Server-side composition (no duplication between pages)

`_send_controlled_page` currently does a single byte replacement. Extend it to a
small include pass executed **after** token substitution:

```html
<!-- #include partials/app-header.html -->
```

Rules:

- Only `<!-- #include partials/*.html -->` is recognised; the path is resolved
  inside `static/partials/` with a hard-coded allow-list (no user input, no
  traversal).
- Includes may not nest more than one level (keeps the pass trivial and
  termination obvious).
- One extra variable, `{{back_link}}`, is substituted per page: the studio and
  visualizer render a link back to `/`, the editor page renders nothing. Same
  mechanism as `__OPT_SP_CONTROL_TOKEN__`.
- Result is cached in memory keyed by the template mtime, since the files do not
  change at runtime.

Partials to create:

| Partial | Used by |
|---|---|
| `partials/app-header.html` | index, visualize, studio |
| `partials/state-panels.html` | visualize, studio |
| `partials/step-controls.html` | visualize, studio |
| `partials/settings-menu.html` | three pages |

This removes the duplication the user flagged ("the two pages are very similar")
without a build step, and the pages remain individually viewable.

### 7.3 New endpoints

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/refine-py` | Stream an LLM rewrite of the `py` mirror (SSE) |
| `GET` | `/api/llm-status` | Effective config (base URL, model, key present, mode) — never the key |
| `GET` | `/__opt_sp/health` | Asset self-check (see §17.3) |

`/api/refine-py` and `/api/llm-status` are loopback-only, like `/api/file`.
They are *not* protected by the stop token: the studio page is a normal page and
must work without one. Binding to a non-loopback host disables them (they answer
`403`), which is the safe default for a classroom.

### 7.4 Unchanged

`server()` signature and return value, `open_browser()`, `_cli()` flags,
background/stop logic, stop token semantics, project-file endpoints.

## 8. Studio page

### 8.1 Layout

Reuses the visualizer grid (`.viz-layout`): left column = three stacked editors,
right column = the shared state panels, bottom = step controls.

```
┌─────────────────────────────┬──────────────────┐
│ py        [synced/stale]    │ Call Stack       │
│                             ├──────────────────┤
├─────────────────────────────┤ Operand Stack    │
│ spasm     [synced/stale]    ├──────────────────┤
│                             │ Heap / Objects   │
├─────────────────────────────┤                  │
│ sp        [synced][·][copy] ├──────────────────┤
│                             │ Printed Output   │
├─────────────────────────────┴──────────────────┤
│ ⏮ ⏪ ⏩ ▶ speed ────────── slider ── step 12/40  │
└────────────────────────────────────────────────┘
```

Each pane header: name, state badge (`synced` / `stale` / `error` / `editing`),
per-pane actions. `py` additionally shows the **AI sync** action when stale.

The right column starts with a collapsible **Trace** code view
(`<pre id="trace-code">`): the step highlight needs the traced source, and the
editors themselves are busy being editors. Highlighting lines *inside* an editor
is explicitly out of scope for v1.

**Narrow screens.** Below 1100 px the grid collapses to a single column and the
three editors stay **stacked vertically in semantic order** (`py`, `spasm`,
`sp`), each with a fixed minimum height and its own scrollbar; the state panels
move below them. No tabbing: the derivation order is the thing the page is
teaching, and tabs hide it. The step controls stay pinned at the bottom.

### 8.2 Bootstrap

1. Read `localStorage["opt-sp-handout"]`; delete it immediately.
2. If present and younger than 5 minutes and well-formed, fill the pane for
   `mode` (`python` → `py`, `asm` → `spasm`, `sp` → `sp`) and derive the others.
3. Otherwise start empty with the default sample from `index.html`.
4. Lazy-load Pyodide only when the first conversion or trace is requested
   (same policy as `kernel.init()` today).

Handout shape:

```js
{ "mode": "python" | "asm" | "sp", "source": "...", "at": 1763600000000 }
```

Written by the launcher immediately before `window.open("/studio", "_blank")`.
Failure to parse or a stale timestamp silently yields an empty workspace.

### 8.3 `.sp` pane safety

`.sp` is whitespace; silent trimming corrupts the program. Requirements:

- `white-space: pre`, `wrap="off"` where supported, horizontal scrolling.
- No formatter, no `trim()`, no trailing-newline normalisation on read or write.
- `paste` is accepted verbatim; a marker appears if the paste contained only
  spaces (likely a lost-formatting paste).
- "Show spaces" toggle renders `·` for spaces via a CSS overlay or a mirrored
  `<pre>` (implementation detail; must not alter the textarea value).
- "Copy raw" writes `textarea.value` to the clipboard without transformation.

### 8.4 Pane layout and annotation controls

- The settings menu carries a `Panes: stacked` / `Panes: side by side` toggle
  (studio page only). The split between the three editors is draggable, exactly
  like the state-panel resizers on the right, and persisted in
  `localStorage["opt-sp-studio-layout"]`. Below 1100 px the editors always stack,
  whatever the saved orientation says.
- The boundary between the editor column and the trace column is draggable as
  well, with the same persistence and minimum widths (300 px editors, 320 px
  trace). The step controls span the full width below both.
- The same menu offers `OPT_SP editor (new tab)` back to the classic page, so the
  studio never traps the user in the new layout.
- The assembly pane header carries an `annotations` toggle for the
  `; line=N spaces=...` comments that `disassemble()` appends to every
  instruction. Hiding is a pure text transform; restoring reuses the cached
  listing so an unchanged round-trip does not renumber the `line=` fields, and
  falls back to `web_bridge.annotate()` (disassemble of the pane's own program)
  after an edit.
- The trace code view stays hidden until a trace exists; the empty reserved area
  was confusing and is not part of the empty state.

## 9. Conversion graph

```
py ──compile_py──▶ Program ──encode(include_names=True)──▶ sp
                        └──disassemble──▶ spasm
sp ──decode──▶ Program ──disassemble──▶ spasm            (deterministic)
spasm ──assemble──▶ Program ──encode──▶ sp               (deterministic)
Program ──?──▶ py                                        (does not exist)
```

Implement once, in Python, exposed to JS:

```python
# spacelang/web_bridge.py
def convert(source: str, src: str, dst: str) -> dict:
    """src/dst in {"py","spasm","sp"}. Returns {"ok","text","error"}."""
```

| src → dst | Path |
|---|---|
| `py → spasm` | `disassemble(compile_py(source))` |
| `py → sp` | `encode(compile_py(source), include_names=True)` |
| `spasm → sp` | `encode(assemble(source), include_names=True)` |
| `spasm → py` | unsupported (`{"ok": false, "error": "no_rule"}`) |
| `sp → spasm` | `disassemble(decode(source))` |
| `sp → py` | unsupported |

`include_names=True` matters: without it the name table (opcode `53`) is dropped
and `sp → spasm` loses every symbol. `compile-py` in the CLI embeds the table for
the same reason.

Kernel addition (JS):

```js
kernel.convert(source, src, dst)        // → {ok, text, error}
```

Errors are returned, never thrown, because half-typed input is a normal state.

## 10. Sync engine

### 10.1 State

Per pane: `{ text, revision, state: "synced" | "stale" | "editing" | "error" }`
plus one global `authoritative: "py" | "spasm" | "sp"`.

### 10.2 Editing

```
on input(pane):
    pane.state = "editing"
    pane.revision += 1
    authoritative = pane
    debounce 250 ms → derive(pane, pane.revision)
```

### 10.3 Deriving

```
derive(srcPane, rev):
    for each dst where edge(srcPane → dst) exists:
        r = await kernel.convert(text, src, dst)
        if r.ok:
            if still current (rev == pane.revision and not dstEditedSince): write(dst, r.text)
        else:
            mark dst as unchanged; if srcPane is authoritative and dst == "py":
                py.state = "stale"
```

Missing edge (`→ py`) ⇒ `py.state = "stale"`. Stale is a *normal* state.

### 10.4 Loop guard

Programmatic writes set `applying[pane] = true`, dispatch no `input` handling,
then clear on the next microtask. Every write also bumps a `writeStamp`; a
derivation result is applied only if `writeStamp` is unchanged.

### 10.5 Undo / caret

Programmatic writes do not enter the pane's undo stack (snapshot the stack and
restore it after the write). The caret is restored to the same character offset,
clamped to the new length. If the pane is focused, scroll position is preserved.

### 10.6 Trace

`Run` traces the **authoritative** pane using `kernel.trace(text, mode)` with the
matching mode, then renders through the shared panel. If `py` is authoritative,
its trace is the interesting one; if `sp` is, the trace shows the encoded source.

## 11. AI mirror sync

### 11.1 Trigger

| Mode | Behaviour | Default |
|---|---|---|
| `manual` | `py` shows *stale* + "Sync with AI" button; nothing runs until clicked | ✅ |
| `auto` | 1.5 s after the last edit, if `py` is stale; 5 s cooldown per session | |
| `off` | `py` only shows *stale* | |

The mode is a three-way radio in the **Settings** menu — no popup and no extra
acknowledgement. Under the `Auto` option a single grey line states the
consequence: *"Auto syncs the Python mirror about 1.5 s after you stop editing.
It shares a 40 requests/min quota with everyone using the same key."* Quota
protection lives in the server-side token bucket (§11.6), which surfaces a
`throttled` badge in the UI instead of silently failing.

### 11.2 Request

```http
POST /api/refine-py
Content-Type: application/json
Accept: text/event-stream

{
  "py":      "<current readable mirror>",
  "spasm":   "<readable assembly of the current program>",
  "old_py":  "<the mirror before the user started editing>",
  "src_kind": "sp" | "spasm"
}
```

`.sp` is never included (ADR-007).

### 11.3 Prompt

System:

> You are the Python mirror maintainer for SpaceLang. SpaceLang programs are
> assembled from integer opcodes. The user edits the low-level form; you keep a
> readable Python mirror in sync. Reply with Python code only, no prose, no
> Markdown fences.

User: current `py`, current `spasm`, and the instruction: produce a `py` whose
compilation matches the given assembly, preserving the existing names, helpers,
docstrings and structure wherever the change allows.

Constraints enforced by the server before sending: total input ≤ 12 000 chars;
`max_tokens = 4096`; `temperature = 0.2`.

### 11.4 Response handling

- Only `delta.content` is accumulated. `delta.reasoning_content` is displayed as
  a separate "thinking" indicator and **never** written to the editor.
- `finish_reason == "length"` ⇒ discard, report `truncated`.
- Empty content ⇒ discard, report `empty_completion`.
- Success ⇒ verification gate (§11.5).

### 11.5 Verification gate

```python
def verify_py(py_src: str, spasm_src: str) -> dict:
    want = canon(assemble(spasm_src))
    got  = canon(compile_py(py_src))
    return {"ok": want == got, "want_len": len(want), "got_len": len(got)}

def canon(program):
    return [(int(i.op), tuple(i.args)) for i in program.instrs]
```

Verification uses the **assembly**, not `.sp`: the assembly is already in the
request, and re-encoding to `.sp` would only re-derive it locally for no gain
(and would contradict ADR-007's "sp is generated locally, never a payload").
`canon(assemble(asm))` and `canon(decode(encode(assemble(asm))))` are the same
list.

`Instr.line`, `Program.names`, `labels`, `funcs`, `try_table` are excluded: they
are debug/symbol metadata and legitimately differ between the two front ends.

- `ok == true` → replace `py`, badge `synced`, toast "mirror verified".
- `ok == false` → **do not replace**. The editor keeps the user's text; a
  non-blocking strip reports `mirror rejected — n/nn instructions differ` with
  the first three differing opcodes, and a "Try again" action. There is no
  "accept anyway": once a bypass exists the gate stops being a gate. If the
  model is repeatedly wrong, the correct response is a better prompt or a
  smaller change, not a bypass.

### 11.6 Rate limiting

The measured deployment allows **40 requests/min** and 500 000 tokens/min, shared
by everyone using the same key.

- Process-wide token bucket, 40 tokens/min, burst 4.
- One in-flight request per browser session; one queued request; a newer request
  replaces the queued one.
- `429` with `Retry-After` when the bucket is empty.
- Server-side timeout 90 s; client `AbortController` cancels both legs.

### 11.7 SSE protocol

```
event: status   data: {"phase":"sending"} | {"phase":"thinking","elapsed_ms":3120}
event: delta    data: {"text":"def add_item(..."}      (content only)
event: done     data: {"ok":true,"py":"...","usage":{...},"verified":true}
event: error    data: {"ok":false,"error":"rate_limited","message":"…"}
```

Implemented with `protocol_version = "HTTP/1.1"` on the handler subclass and
manual chunked framing (`Transfer-Encoding: chunked`). The current handler
inherits HTTP/1.0, which cannot stream — this must be set explicitly, and only
for the streaming route if global change is undesirable.

## 12. Configuration

### 12.1 Precedence (highest wins)

1. Settings UI (per-request `X-LLM-*` headers)
2. CLI: `--llm-base-url`, `--llm-model`, `--llm-api-key-file`
3. Environment: `LITELLM_BASE_URL`, `LITELLM_MODEL`, `LITELLM_API_KEY`
4. Built-in: base URL of the campus deployment, model `Socrates`, no key

A raw `--llm-api-key` flag is deliberately **not** offered (process list and
shell history exposure). `--llm-api-key-file` reads the first non-empty line.

### 12.2 Python API

Backwards compatible; existing calls are unchanged.

```python
from spacelang.opt_sp import server, launch, LLMConfig

server(port=8000, blocking=False)                     # unchanged behaviour
server(port=8000, llm={"model": "Socrates", "api_key": "..."})   # new kwarg

launch(config={"port": 8000, "llm": LLMConfig(api_key="...")})   # convenience
```

`llm` accepts a dict or an `LLMConfig` dataclass:

```python
@dataclass
class LLMConfig:
    base_url: str = DEFAULT_BASE_URL
    model: str = "Socrates"
    api_key: str | None = None
    mode: str = "manual"          # manual | auto | off
    max_output_tokens: int = 4096
    temperature: float = 0.2
    timeout: float = 90.0
```

`launch` is a thin wrapper over `server(blocking=True)` plus CLI parsing; it
exists only because `spacelang.opt_sp` is a package and cannot be called.

### 12.3 Settings UI

The existing gear menu (already added in the working tree) gains two entries:

- **Studio** — opens `/studio` in a new tab (`target="_blank"`,
  `rel="noopener"`), writing the handout immediately before opening.
- **LLM settings** — opens an inline panel inside the studio page (not a
  `window.confirm`/`alert`, not a separate route).

Panel contents:

| Field | Notes |
|---|---|
| Base URL | placeholder = built-in default |
| Model | placeholder `Socrates` |
| API key | `type=password`, blank = "use server env/file" |
| Mode | radio `Manual` / `Auto` / `Off`, default `Manual` |
| Save / Clear | Clear removes `localStorage["opt-sp-llm"]` |

Under `Auto` sits one grey line: *"Auto syncs the Python mirror about 1.5 s
after you stop editing. It shares a 40 requests/min quota with everyone using
the same key."* No confirmation popup — the server-side bucket is the actual
guard, and the UI shows a `throttled` badge when it engages.

Values are stored in `localStorage["opt-sp-llm"]` and sent as per-request
headers; nothing is persisted server-side.

Warning text shown in the dialog: a key in `localStorage` is readable by any
script running on `127.0.0.1:<port>`, and the backend posts whatever it receives
to the configured base URL. Studio is a local tool; do not expose it on a LAN.

## 13. Security

| Item | Requirement |
|---|---|
| Key in logs | Never. `Authorization` is stripped before any log line; errors are mapped to fixed strings |
| Key in responses | Never. `/api/llm-status` returns `key_present: bool` only |
| Key at rest | Only in `.env.local` (git-ignored) or the user's `localStorage` |
| `.env.local` | Added to `.gitignore` in this change |
| Non-loopback bind | `/api/refine-py` and `/api/llm-status` answer `403` |
| Request size | 64 KiB cap on `/api/refine-py` |
| Prompt injection | The assembly is fenced and labelled as data; the model's output is not executed, only compiled and compared |
| Secret leakage | `.sp` is never sent to the LLM (ADR-007) |
| Upstream URL | `--llm-base-url` may point anywhere; document that it is trusted input |

## 14. Packaging and CI

- `pyproject.toml` — no change to `[project.scripts]`; `sdist.include` already
  covers `spacelang/opt_sp/static/**`.
- `.gitignore` — add `.env`, `.env.local`.
- `tools/build_static.py`
  - `_check()`: add `studio.html`, `partials/*.html`, `js/studio.js`,
    `js/trace-panel.js`.
  - New `--check-digest`: compare `sha256` of each `static/spacelang_pkg/**` file
    with its source under `spacelang/`, so a stale copy fails CI instead of
    silently shipping old Python into the browser.
- `.github/workflows/opt-sp-smoke.yml` — unchanged commands must keep passing.

## 15. Testing

### 15.1 Python unit tests (extend `tests/test_opt_sp.py`)

| Test | Asserts |
|---|---|
| `test_studio_route_serves_token` | `GET /studio` → 200, HTML, token substituted, includes resolved |
| `test_include_partials_are_inlined` | no `<!-- #include` remains in any served page |
| `test_assets_version_assertion` | replace the hard-coded `?v=6` with `re.search(r"\?v=\d+")` (fixes the current failure) |
| `test_convert_roundtrip` | `py → sp → spasm` and back reaches an identical canonical program |
| `test_convert_unsupported_direction` | `sp → py` returns `{"ok": false, "error": "no_rule"}` |
| `test_verify_py_accepts_equivalent` | verified rewrite of a known program passes |
| `test_verify_py_rejects_semantic_change` | an altered program fails |
| `test_refine_py_requires_loopback` | non-loopback peer → 403 |
| `test_refine_py_rate_limit` | bucket exhausted → 429 + `Retry-After` |
| `test_refine_py_rejects_sp` | payload containing a `sp` field is rejected |
| `test_llm_status_hides_key` | key never appears in the response |
| `test_config_precedence` | header > CLI > env > default |
| `test_health_reports_missing_assets` | renamed asset → `ok: false` with the missing path |

Upstream LLM calls are faked in tests (a stub HTTP server on `127.0.0.1:0`);
no test may depend on the campus deployment.

### 15.2 JS behaviour checklist (manual, documented in the doc)

1. Handout: launch from index with Python source → studio opens on `py`.
2. Edit `py` → `spasm` and `sp` update within 250 ms.
3. Edit `spasm` → `sp` updates, `py` shows *stale*.
4. Edit `sp` (paste an encoded file) → `spasm` updates, `py` shows *stale*.
5. Paste with trailing spaces preserved; "show spaces" toggle correct.
6. AI sync: `thinking…` appears, code streams in, verification passes, badge
   becomes *synced*.
7. AI sync with a semantically different result → no replacement, diff shown.
8. Cancel mid-stream → upstream request aborted, `py` unchanged.
9. Refresh `/studio` → handout gone, empty workspace.
10. `Ctrl+Z` after a programmatic sync does not undo into a broken state.

### 15.3 Optional E2E

A Playwright smoke test is out of scope for the first iteration; the manual
checklist above is the substitute. If added later, it runs headless with Pyodide
preloaded and a stub LLM.

## 16. Failure modes and messages

| Symptom | Cause | UI |
|---|---|---|
| Page loads, nothing runs | Pyodide assets missing | Banner: "Pyodide assets missing — run `python tools/build_static.py`" (from `/__opt_sp/health`) |
| `401` | bad key | "API key rejected (401). Check Settings." |
| `429` | token bucket | "Too many AI requests, retry in Ns" |
| `finish_reason=length` | reasoning ate the budget | "Model produced no code (truncated). Try again." |
| Empty content | same class | "Model returned nothing. Try again." |
| Verification failed | wrong rewrite | diff strip + "keep mine / try again" (never applied) |
| Upstream unreachable | VPN / outage | "Cannot reach the LLM endpoint." |

## 17. Phased implementation

**Phase 0 — baseline health**
Fix the `?v=` test assertion. Add `/__opt_sp/health` and the missing-asset
banner. This directly addresses the recurring "HTML only, no Pyodide" failure.

**Phase 1 — composition**
Add `partials/`, the include pass, `studio.html` shell with three static
textareas, `/studio` route, settings-menu entry (new tab), handout write/read.
No conversions yet. Tests: route + includes.

**Phase 2 — conversion graph**
`web_bridge.convert`, `kernel.convert`, sync engine (derive, loop guard,
revision, caret), pane badges. Tests: conversions + unsupported directions.

**Phase 3 — trace**
Wire the shared panels and step controls to `kernel.trace` on the authoritative
pane. Reuse `Visualizer` by extracting `TracePanel`.

**Phase 4 — AI mirror sync (non-streaming)**
`LLMConfig`, config precedence, `/api/llm-status`, `/api/refine-py` (JSON), rate
limiter, verification gate, Settings dialog. Tests: precedence, 403, 429,
key-hiding, verify.

**Phase 5 — streaming**
SSE framing on the server, `fetch`-stream parsing on the client, cancel.
`thinking…` progress. Tests: fake upstream emitting chunks.

**Phase 6 — docs and release notes**
`docs/studio/README.md` (user-facing), README section, `documentation.md` entry.

## 18. Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Model output semantically wrong but fluent | corrupted mirror | verification gate (ADR-005) |
| 6 s of hidden reasoning feels broken | abandonment | streaming + explicit `thinking…` |
| 40 RPM shared by a class | everyone throttled | manual default + bucket + single-flight |
| Whitespace corruption of `.sp` | broken programs | no-trim rules + show-spaces + raw copy |
| `web_bridge.py` changed but static copy stale | browser runs old code | `--check-digest` in CI |
| Program comparison too strict (labels/line) | false rejections | compare canonical `(op, args)` only |
| User's uncommitted UI edits conflict | merge pain | keep the working tree, build on top, no revert |

## 19. Resolved items

All three previously open questions are settled; recorded here so the prompt
generator does not reopen them.

1. **No "accept unverified".** A rejected mirror keeps the user's text and offers
   "Try again". §11.5.
2. **Narrow screens stack the editors vertically** in semantic order (`py`,
   `spasm`, `sp`); no tabs. §8.1.
3. **AI mode lives in Settings, with no confirmation popup.** A three-way radio
   plus one explanatory line under `Auto`; quota is enforced server-side. §11.1,
   §12.3.

---

## Appendix A — measured behaviour of the target LLM endpoint

Endpoint `https://socratic.cs.cityu.edu.hk/litellm/v1`, model `Socrates`,
2026-11-20.

| Probe | Result |
|---|---|
| `GET /models` | 200, single model `Socrates` |
| Invalid key | 401, clean JSON |
| Minimal completion | 200, 0.32 s, `reasoning_content` present, `reasoning_tokens: 10` |
| Streaming | supported (`text/event-stream`), first byte 0.20 s |
| Realistic rewrite (~400 prompt tokens) | **7.3 s total**, 6.0 s before first content byte, ~900 chars of code |
| `max_tokens=1500` | 200 **with empty content**, `finish_reason: "length"` — reasoning consumed the budget |
| `max_tokens=4000` | completes, 2.4 s for a short task |
| `reasoning_effort: low/none` | accepted, effectively ignored (3809 → 3055 reasoning chars) |
| `chat_template_kwargs.enable_thinking=false` | returns empty; do not use |
| `usage` in stream | absent unless `stream_options.include_usage` |

Operational limits: 500 000 tokens/min, 40 requests/min, daily budget, key
expires 2026-12-19.

Consequences: `max_tokens` must be ≥ 3000 (4096 chosen); empty/truncated replies
are an expected outcome and must be handled as errors, not as empty code;
`reasoning_content` must be discarded; streaming is required for acceptable UX.

## Appendix B — decision log

| # | Decision | Confirmed by user |
|---|---|---|
| 1 | New route `/studio` | yes |
| 2 | Opens in a new tab | yes |
| 3 | All three panes writable | yes |
| 4 | AI is manual by default, switchable in Settings | yes |
| 5 | Server-side LLM proxy, streaming | yes |
| 6 | CLI flags + per-user key in Settings + `server(llm=...)` / `launch(config=...)` | yes |
| 7 | Documentation in English only; conversation in Chinese | yes |
| 8 | `localStorage` handout with TTL | yes |
| 9 | Compiler verification gate | yes |
| 10 | `.sp` whitespace protection | yes |
| 11 | No "accept unverified": a rejected mirror is never applied | yes |
| 12 | Narrow screens keep the three editors stacked, semantic order | yes |
| 13 | AI mode is a Settings radio; no confirmation popup | yes |
