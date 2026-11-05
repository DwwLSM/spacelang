# SpaceLang

SpaceLang is an experimental stack-based language toolkit. It currently
contains a Python reference VM, an experimental C++ VM, a small Python-subset
frontend, and tools for assembling, disassembling, and encoding SpaceLang
programs.

> **Status:** Early development. The frontend and VM implement a subset of
> Python and the project is not yet a drop-in Python runtime. See the source and
> tests for the behavior currently supported.

## Requirements

- Python 3.10 or newer
- A C++17 compiler and CMake 3.18 or newer to build the native extension

## Install

Install the package from a checkout:

```bash
git clone https://github.com/DwwLSM/spacelang.git
cd spacelang
python -m pip install .
```

For development, install the package with its test dependencies in editable
mode:

```bash
python -m pip install -e ".[dev]"
python -m pytest
```

## Run Python-subset source

Compile supported Python syntax to a SpaceLang program, then execute it with
the reference VM:

```python
from spacelang.pyfront import compile_py
from spacelang.vm_py import VM

source = """
def add(a, b):
    return a + b

i = 0
while i < 3:
    print(add(i, 2))
    i = i + 1
"""

program = compile_py(source)
VM(program).run()
```

Output:

```text
2
3
4
```

The current frontend handles basic integer, boolean, and string constants,
arithmetic, comparisons, boolean expressions, calls, assignments, supported
imports, `if`/`else`, `while`, simple positional functions, and `for` loops
over `range(...)`. Sequence indexing is supported for indexable values.

This is still a Python subset, not full Python; features such as classes,
exceptions in source code, generators, nested or filtered comprehensions,
keyword arguments to user functions, and general iterator protocols are not implemented.
Unsupported syntax raises an error rather than being silently compiled.

## Run a `.sp` program

Write assembly mnemonics to a `.spasm` file, assemble it into the whitespace-only
`.sp` format, then run it with the reference VM:

`example.spasm`:

```text
PUSH_INT 2
PUSH_INT 3
OP 1
CALL 0 1
STACK 3
HALT
```

Run these commands from an installed checkout:

```bash
spacelang asm example.spasm example.sp
spacelang disasm example.sp
spacelang run example.sp
```

The program prints `5`. `CALL 0 1` calls the `print` builtin; `STACK 3`
drops the builtin's return value. To use the source checkout without installing
the command, invoke the CLI as `python -m spacelang.main run example.sp`.

## How whitespace becomes instructions

A `.sp` file is a stream of integer tokens written as spaces and newlines. The
number of spaces before each newline is one token's value; the newline ends that
token. The parser reads the first token as an opcode, then consumes the number
of argument tokens required by that opcode. For example, `PUSH_INT 2` is encoded
as the tokens `7` (the `PUSH_INT` opcode) and `4` (zig-zag encoded integer 2).
`OP 1` is the tokens `5` (`OP`) and `1` (addition). The VM executes the resulting
instructions; spaces are not executed one at a time.

For the example above, the token values are:

| Assembly | Space-count tokens |
| --- | --- |
| `PUSH_INT 2` | `7, 4` |
| `PUSH_INT 3` | `7, 6` |
| `OP 1` | `5, 1` |
| `CALL 0 1` | `1, 0, 1` |
| `STACK 3` | `6, 3` |
| `HALT` | `29` |

Each individual token is limited to 65,535 spaces. A direct `PUSH_INT 100000`
would require an argument token of 200,000 spaces because positive integers use
zig-zag encoding, so it cannot be encoded as one token. For a Python-subset
source constant, use `--compress-source`; for `100000`, the compiler can factor
it into smaller constants and multiplication instructions:

`large.py`:

```python
print(100000)
```

```bash
spacelang compile-py large.py large.sp --compress-source
spacelang run large.sp
```

This prints `100000`. `--compress-source` makes the integer representable using
multiple small tokens; it does not mean that one very long run of spaces is
executed. `.spz` is a separate gzip-compressed container for an already encoded
`.sp` program.

## Create a self-copying program

For Python files, `quine` writes a new file with a small hook that copies that
generated file to a `.copy.py` sibling when run. The input file is left
unchanged:

```python
from spacelang.quine import quine

quine("example.py", "example_quine.py")
```

Then run `python example_quine.py`. The CLI equivalent is:

```bash
python -m spacelang.quine example.py example_quine.py
```

The CLI also supports `--in-place --yes`; it creates a `.bak` backup before
replacing the source. The Python API itself rejects in-place operation.
SpaceLang `.sp`/`.spz` quines produce a companion `.names.json` file because
the instruction stream stores name IDs, not their textual names.

## Command-line tools

The command-line interface supports Python compilation, assembly,
disassembly, execution with the reference VM, and `.sp`/`.spz` compression:

```bash
spacelang compile-py example.py example.sp
spacelang run example.sp
spacelang run example.sp --engine cpp
spacelang disasm example.sp
spacelang pack example.sp
spacelang run example.spz
```

The module form remains available when invoking the source checkout directly:

```bash
python -m spacelang.main run example.sp
```

Compilation enables the safe peephole optimizations and integer constant pool
by default. Pass `--no-optimize` to `compile-py` to preserve the frontend IR,
or `--compress-source` to factorize large integer constants before encoding.
The C++ engine is experimental and is not the default. GCC and Clang builds use
computed-goto instruction dispatch; other compilers use a portable switch
dispatcher. Use the Python engine as the reference for behavior that has not
yet been verified for native parity.

To compare both engines on the same recursive workload after installation:

```bash
python -m benchmarks.benchmark_vm --n 25 --repeat 3
```

The benchmark checks that both engines return the same result and reports the
median runtime and speedup. Timings depend on the host and are not a performance
guarantee.

## Assemble and run instructions

The assembler accepts one mnemonic instruction per line. For example:

```python
from spacelang.asm import assemble
from spacelang.vm_py import VM

program = assemble("""
PUSH_INT 2
PUSH_INT 3
OP 1
HALT
""")

print(VM(program).run())
```

`OP 1` adds the two values on top of the stack. This example prints `5`.

## Inspect and encode programs

```python
from spacelang.asm import assemble
from spacelang.disasm import disassemble
from spacelang.encoder import encode
from spacelang.lexer import tokenize
from spacelang.parser import parse

program = assemble("PUSH_INT 2\nPUSH_INT 3\nOP 1\nHALT\n")

print(disassemble(program))   # Human-readable instructions
encoded = encode(program)     # SpaceLang whitespace encoding
tokens = tokenize(encoded)
decoded_program = parse(tokens)
```

The package also exports the core `Program`, `Instr`, and `OP` types, along
with `assemble`, `disassemble`, `encode`, `parse`, and `tokenize` from
`spacelang`.

## Development

Run the test suite from the repository root:

```bash
python -m pytest
```

The tests cover the current IR, encoding/parser, assembler/disassembler, VM,
Python-subset frontend, and native/reference differential behavior.

## Render the introduction animation

The Manim scene source is in `scene.py`. Install the optional animation
dependency (and Manim's required system packages; see the
[Manim installation guide](https://docs.manim.community/en/stable/installation.html)):

```bash
python -m pip install -e ".[animation]"
```

Render an English version with subtitles:

```bash
manim -ql scene.py SpacelangIntroEnglishWithSubtitle
```

Use `SpacelangIntroChineseWithSubtitle`,
`SpacelangIntroEnglishWithoutSubtitle`, or
`SpacelangIntroChineseWithoutSubtitle` for the other variants. Manim writes
rendered videos and its generated assets under `media/`; these are ignored by
Git and can be recreated from `scene.py`.
