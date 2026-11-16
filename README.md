# SpaceLang

**A small programming-language toolkit built as a university course project.**

SpaceLang explores how source code becomes executable instructions. It includes
a Python-subset compiler, a readable stack-machine assembly, a whitespace-only
program format, a reference virtual machine, an experimental C++ engine, and a
browser-based visual debugger. It is both a working Python package and a
showcase of compiler, runtime, packaging, testing, and developer-tool work.

> **Project status:** Experimental and actively developed. SpaceLang is an
> educational language implementation, not a replacement for Python. The
> compiler accepts a documented subset of Python syntax; unsupported syntax
> raises an error.

## What you can explore

- **A compiler pipeline:** Python-subset source or SpaceLang assembly becomes
  an intermediate program, which can be optimized, encoded, inspected, and run.
- **A custom language format:** `.sp` programs encode integer tokens as runs
  of spaces terminated by newlines. `.spz` is their gzip-compressed form.
- **Two VM implementations:** a Python reference engine and an experimental
  C++17 engine built with pybind11.
- **Language features:** functions and closures, loops, collections,
  comprehensions, argument binding, imports, and more—within a clearly bounded
  subset.
- **Tools for learning and demonstration:** a command-line interface, a
  step-by-step browser visualizer, benchmarks, tests, and an optional Manim
  introduction animation.

For the full architecture, language reference, instruction set, APIs, and
development notes, see [the project documentation](documentation.md).

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

### Compile and run Python-subset source

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

The OPT_SP browser debugger can visualize Python-subset source, assembly, or an
encoded `.sp` program. It shows the instruction trace, operand and call stacks,
globals, heap objects, and printed output. Its local Python server serves the
interface; execution and tracing happen in the browser with Pyodide.

```bash
python tools/build_static.py
spacelang-opt-sp --port 8000
```

The first command downloads the pinned Pyodide files and prepares the browser
assets; you only need to repeat it when rebuilding those assets.
`python tools/build_static.py --check` verifies that they are present.

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

1. Compile a small Python-subset example and inspect its assembly with
   `spacelang disasm`.
2. Run it in the reference VM and, optionally, the experimental C++ VM.
3. Open OPT_SP to step through the stacks and program state.
4. Explain the whitespace format, optimizer, automated tests, and current
   limitations.

Prepare the optional browser assets before the demonstration with
`python tools/build_static.py`.

## Showcase materials

The optional Manim animation source is [`scene.py`](scene.py). Install Manim's
system requirements and the project extra:

```bash
python -m pip install -e ".[animation]"
manim -ql scene.py SpacelangIntroEnglishWithSubtitle
```

Other scene variants are listed in [the documentation](documentation.md#project-presentation-and-animation).

## Scope and safety

SpaceLang is a learning and experimentation project. The Python frontend does
not implement all of Python; consult the [supported-language reference](documentation.md#python-subset-reference)
for implemented syntax and known limitations. The VMs expose capabilities
such as file access and selected operating-system functions, so do not run
untrusted programs with them. OPT_SP's browser execution is useful for
demonstration, but it should not be treated as a security boundary.

## Project map

| Path | Purpose |
| --- | --- |
| `spacelang/pyfront.py` | Python-subset parser/compiler |
| `spacelang/ir.py` | Instruction set and program representation |
| `spacelang/asm.py`, `disasm.py` | Human-readable assembly tools |
| `spacelang/encoder.py`, `lexer.py`, `parser.py` | SpaceLang file encoding and parsing |
| `spacelang/vm_py.py` | Reference virtual machine |
| `csrc/`, `spacelang/vm_cpp.py` | Native C++ VM and Python wrapper |
| `spacelang/peephole.py` | Program optimization passes |
| `spacelang/opt_sp/`, `spacelang/vm_trace.py` | Browser debugger and trace support |
| `tests/` | Automated tests and language examples |
| `benchmarks/` | Python-versus-C++ VM benchmark |
| `scene.py` | Optional introduction animation |
| [`documentation.md`](documentation.md) | Detailed project and technical reference |
