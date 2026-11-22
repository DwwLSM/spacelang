# SpaceLang

SpaceLang is a programming language whose source language is `.sp`. The `.py` form is an optional surface syntax that is lowered to `.sp`.

`.sp` is the SpaceLang source language. `.py` is an optional surface syntax lowered to `.sp`.
Supporting `.py` input does not make SpaceLang Python.

**A small programming-language toolkit built as a university course project.**

SpaceLang explores compiler, assembly, runtime, packaging, testing, and developer-tool work. `.sp` is source; `.py` is only an optional frontend.

## Project status

Experimental and actively developed. This project does not claim completion beyond repository evidence. Optional `.py` frontend completeness is separate from the language and `.sp → .sp` self-hosting path.

## C++ analogy

| Stage | C++ | SpaceLang |
|---|---|---|
| Write source | `.cpp` | **`.sp`** (language proper) |
| Optional surface syntax | — | **`.py`** (lowered to `.sp`) |
| Compile | `C++.exe` | **`compiler.exe`** (reads `.sp` → produces `.sp` / executable artifacts) |
| Execute | OS / linker | **VM (`spvm.exe` / `sp_vm`)** |

## What you can explore

- **The `.sp` source path:** native `.sp` source, assembly tooling, and `.sp` artifacts.
- **Optional `.py` lowering:** a convenience frontend that lowers supported `.py` syntax to `.sp`.
- **Compiler and VM roles:** `compiler.exe` / `spc` compiles `.sp`; `spvm.exe` / `sp_vm` executes `.sp`.
- **Tools:** a Python reference VM, an experimental C++ engine, optimizer, CLI, tests, and browser visualizer.
- **Native tools:** [native/](native/README.md) for native execution and compiler work.
- **Self-hosting:** the runtime and compiler guide in [SELFHOSTING.md](SELFHOSTING.md).
- **The `.sp` format:** integer tokens are encoded as runs of spaces terminated
  by newlines; `.spz` is the gzip-compressed form.
- **Language features:** functions and closures, loops, collections,
  comprehensions, argument binding, and imports within a bounded subset.
- **Presentation tools:** the browser visualizer and optional Manim and Remotion
  introduction videos.

For the full architecture, language reference, instruction set, APIs, and
development notes, see [the project documentation](documentation.md).

For self-hosting, the Python-free runner, and the SpaceLang compiler, see the
complete guide: [SELFHOSTING.md](SELFHOSTING.md).

## Try it

Python 3.10 or later is required. PyPI provides prebuilt wheels for CPython
3.10–3.14 on x64 Windows, x86-64 and ARM64 Linux, and Intel/Apple Silicon
macOS. These installs do not need a local C++ toolchain:

```bash
python -m pip install spacelanguage
```

For other Python implementations or platforms, pip builds from the source
distribution; a C++17 compiler and CMake 3.18+ are then required.

```bash
git clone https://github.com/DwwLSM/spacelang.git
cd spacelang
python -m pip install -e ".[dev]"
```

## Optional `.py` frontend

`.py` is optional sugar. The frontend lowers `.py` source to `.sp`; after lowering, the program follows the same path as native `.sp` source.

### Optional `.py` frontend example

Create `hello.py`:

```python
def greet(name="world"):
    return f"Hello, {name}!"

print(greet())
```

Compile it to a portable SpaceLang program, then execute it with the reference
VM:

```bash
spacelang compile-py hello.py hello.sp
spacelang run hello.sp
```

Expected output:

```text
Hello, world!
```

The generated `.sp` file includes the program's name table. You can inspect it
with `spacelang disasm hello.sp`.

### Write and run assembly

```python
from spacelang import assemble
from spacelang.vm_py import VM

program = assemble("""
PUSH_INT 20
PUSH_INT 22
OP 1
HALT
""")
print(VM(program).run())
```

This prints `42`. Assembly makes the operand stack and operations explicit;
`OP 1` adds the top two values.

## See a program execute

The OPT_SP browser debugger can visualize optional `.py` frontend source, assembly, or a
`.sp` source artifact.
It shows the instruction trace, operand and call stacks,
globals, heap objects, and printed output. Its local Python server serves the
interface; execution and tracing happen in the browser with Pyodide. Edited
source can be downloaded from the editor or live visualizer. The editor also
supports explicitly overwriting a loaded source file after confirmation.

If you installed `spacelanguage` from PyPI, its browser assets are included.
Start the debugger directly:

```bash
spacelang-opt-sp --port 8000
```

Stop the foreground server from the debugger with **Stop server** or
**Ctrl+Alt+Q** (**Cmd+Option+Q** on macOS); you can close the tab after it
confirms shutdown. **Ctrl+C** in the terminal still stops it as well. To run
the server in the background and stop it later:

```bash
spacelang-opt-sp --background --port 8000
spacelang-opt-sp --stop --port 8000
```

When running from a source checkout, first prepare the assets from the
repository root:

```bash
python tools/build_static.py
spacelang-opt-sp --port 8000
```

The build command downloads the pinned Pyodide files and prepares the browser
assets. `python tools/build_static.py --check` verifies that they are present.

### Studio: edit the same program in three representations

`/studio` opens a workspace with the program shown as `py`, `spasm` and `sp` at
the same time. Editing one pane derives the other two (250 ms debounce), each
pane has its own **Run** button that traces that pane into the shared state
panels, and every divider is draggable.

Because `.sp` and `spasm` are compiler output, the Python mirror cannot be
derived by rule; it is marked `stale` after such an edit and must be rewritten
by a model. That is the only AI-assisted step in the tool: it is opt-in, it runs
against an OpenAI-compatible endpoint you configure, and its answer is only
accepted when `compile_py(answer)` reproduces the assembly instruction for
instruction. See `docs/studio/README.md` for setup and the design notes in
`docs/studio/PLAN.md`.

```bash
spacelang-opt-sp --port 8000 --llm-api-key-file ~/.config/spacelang/llm-key
# then open http://127.0.0.1:8000/studio
```
The interface assets and requests use paths relative to the app, so the
debugger also works when served behind a URL path prefix (such as a hosted
VS Code port proxy).

## Development

Run the tests from the repository root:

```bash
python -m pytest
```

The suite covers the assembler and file formats, compiler, Python and C++
virtual machines, optimizer, CLI, quines, debugger trace API, and differential
engine behavior. CI exercises Python 3.10–3.14 on Linux, macOS, and Windows.

To compare VM performance on the same recursive workload:

```bash
python -m benchmarks.benchmark_vm --n 25 --repeat 3
```

The benchmark checks that both engines agree on the result; reported timings
are observations, not performance guarantees.

## A short presentation walkthrough

1. Use a native `.sp` program or inspect a repository `.sp` example.
2. Optionally demonstrate lowering a supported `.py` source file to `.sp`.
3. Run the `.sp` artifact in the reference VM or native VM.
4. Explain the compiler, optimizer, runtime, tests, and current status without conflating `.py` frontend completeness with the `.sp` language.

If using a PyPI installation, OPT_SP's browser assets are already included.
When demonstrating from a source checkout, prepare them first with
`python tools/build_static.py` from the repository root.

## Showcase materials

The optional Manim animation source is [`scene.py`](scene.py). Install Manim's
system requirements and the project extra:

```bash
python -m pip install -e ".[animation]"
manim -ql scene.py SpacelangIntroEnglishWithSubtitle
```

Other scene variants are listed in [the documentation](documentation.md#project-presentation-and-animation).

The separate [`remotion/`](remotion/) project provides English and Chinese
project videos without changing the existing Manim scenes:

```bash
cd remotion
npm ci
npm run dev
npm run render
npm run render:tour
```

See [the Remotion project guide](remotion/README.md) for requirements, subtitle
files, and rendering details.

## Scope and safety

SpaceLang is a learning and experimentation project. The optional `.py` frontend has bounded syntax and is not full Python; consult [documentation.md](documentation.md) for the implemented frontend surface.

The VMs expose capabilities such as file access and selected operating-system functions, so do not run untrusted programs with them. Optional `.py` frontend completeness is not the boundary of the `.sp` language or a blocker for `.sp → .sp` compiler self-hosting.

## Project map

| Path | Purpose |
| --- | --- |
| `spacelang/pyfront.py` | Optional `.py` frontend lowering to `.sp` |
| `spacelang/ir.py` | Internal compiler structures and instruction definitions |
| `spacelang/asm.py`, `disasm.py` | Human-readable assembly tools |
| `spacelang/encoder.py`, `lexer.py`, `parser.py` | SpaceLang artifact parsing and encoding |
| `spacelang/vm_py.py` | Reference VM |
| `csrc/`, `spacelang/vm_cpp.py` | C++ VM and Python wrapper |
| `bootstrap/` | Runtime self-hosting experiments |
| `native/` | Native runner and compiler tools |
| `tests/` | Automated tests and language examples |
| [`documentation.md`](documentation.md) | Detailed project and technical reference |

## Pipeline

```
                         ┌─────────────────────────────┐
   .sp source  ─────────►│                             │
   (language proper)     │        compiler.exe         │────► .sp / executable artifacts
                         │  native .sp frontend        │
   .py source  ─lower───►│  optional .py frontend      │
   (optional sugar)      └─────────────────────────────┘
                                      │
                                      ▼
                            VM / runtime executes .sp
```

## Minimal `.sp` example

A real repository example is [`bootstrap/demos/hello.sp`](bootstrap/demos/hello.sp).
The VM/runtime executes this `.sp` artifact after the compiler/toolchain produces or supplies it.
