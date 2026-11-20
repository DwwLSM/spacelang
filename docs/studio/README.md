# OPT_SP Studio

A workspace for one SpaceLang program shown three ways at once, with the classic
debugger's state panels on the right.

```
http://127.0.0.1:8000/studio
```

Open it from the settings menu (**Studio (new tab)**) on any OPT_SP page, or
directly. If you arrived from the editor or the visualizer, the source you were
looking at is carried over in the `py`, `spasm` or `sp` pane depending on the
mode; nothing else is shared between tabs.

## Running it

```bash
pip install spacelanguage          # browser assets are included
spacelang-opt-sp --port 8000
```

From a source checkout, prepare the assets once:

```bash
python tools/build_static.py
spacelang-opt-sp --port 8000
```

If the page loads but nothing runs, `http://127.0.0.1:8000/__opt_sp/health`
answers with a per-asset check, and the page shows a banner naming what is
missing. The usual cause is a checkout where `tools/build_static.py` has not run
yet.

## The three panes

| Pane | What it holds | Who can produce it |
|---|---|---|
| `py` | Python surface syntax | a person, or the model |
| `spasm` | assembly listing | the compiler, deterministically |
| `sp` | encoded token stream (spaces) | the compiler, deterministically |

Editing any pane updates the others after a 250 ms pause. The two compiler forms
convert into each other freely. Python is different: nothing in the compiler
turns a program back into Python, so after you edit `spasm` or `sp` the `py` pane
is marked **stale** and its text is left alone until you ask for a rewrite.

`sp` is whitespace, so it looks empty. **show spaces** renders a dotted preview
underneath, and **Copy raw** copies the exact text — neither changes the
contents. Nothing in the studio trims or reformats that pane.

## Running and stepping

Each pane has its own **Run** button; the pane whose trace you are looking at
keeps an accent border. The trace fills the panels on the right:

- **Call Stack**, **Operand Stack**, **Heap / Objects**, **Printed Output**
- step controls, autoplay and speed
- **follow** keeps the active line centred in the trace view; turn it off to keep
  the view where you put it

## Layout

Every divider drags: between the panes, between the editor column and the trace
column, and between the trace code and the state panels. The settings menu
switches the panes between **stacked** and **side by side**. All of it is
remembered per browser, and narrow windows always stack.

## Rewriting the Python mirror

`py` can only be rebuilt by a model, and that is optional. Point the studio at an
OpenAI-compatible endpoint with **LLM settings** in the menu, or start the server
with flags:

```bash
spacelang-opt-sp --port 8000 \
  --llm-base-url https://host/litellm/v1 \
  --llm-model ModelName \
  --llm-api-key-file ~/.config/spacelang/llm-key
```

Or with environment variables, optionally in `.env.local` next to the working
directory (it is git-ignored):

```
LITELLM_BASE_URL=https://host/litellm/v1
LITELLM_MODEL=ModelName
LITELLM_API_KEY=...
```

Precedence: settings dialog > command line > environment/.env.local > defaults.
A key typed into the dialog lives in this browser's `localStorage`, so use it for
local work only.

### Modes

| Mode | Behaviour |
|---|---|
| **Manual** (default) | a **Sync with AI** button appears while the mirror is stale |
| **Auto** | syncs about 1.5 s after you stop editing, with a cooldown |
| **Off** | no AI is ever called |

### What gets sent, and what comes back

The request carries the Python mirror and the assembly listing. The encoded `.sp`
program is never sent: the server derives the previous assembly by compiling the
stale mirror, diffs it against the current one, and asks the model to apply that
change.

Every answer is checked before you see it: the returned Python must compile to
exactly the same instruction stream as the assembly, ignoring line numbers and
symbol tables. If it does not, the editor keeps your text and the status line
names the first differing instruction, for example:

```
Mirror rejected at instruction 7: the program needs "OP 2" but the answer compiles to "OP 3".
```

There is no "accept anyway" — a gate you can bypass is not a gate.

### Limits

Requests share a token bucket of 40 per minute (burst 4) per server process,
because campus deployments often cap concurrent use. `auto` mode can hit it;
manual mode rarely does. When it happens the status line says how long to wait.

The proxy is loopback-only: `/api/refine-py` and `/api/llm-status` refuse
non-local clients, and the key never appears in a response or a log line.

## Keyboard and mouse

- Step with the buttons, the slider, or the left/right arrow keys.
- Drag a state panel's header to reorder the panels (`Alt`+arrow keys also work).
- **Ctrl+Alt+Q** / **Cmd+Option+Q** stops the server from any page.

## Related documents

- `docs/studio/PLAN.md` — the design, decisions and measured behaviour of the
  target endpoint.
- `docs/studio/PROMPT.md` — the phase-by-phase implementation order.
- `documentation.md` — the language and tooling reference.
