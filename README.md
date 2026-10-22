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

Clone the repository and install it in editable mode:

```bash
git clone https://github.com/DwwLSM/spacelang.git
cd spacelang
python -m pip install -e .
```

For development, install pytest as well:

```bash
python -m pip install pytest
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
python -m spacelang.main compile-py example.py example.sp
python -m spacelang.main run example.sp
python -m spacelang.main run example.sp --engine cpp
python -m spacelang.main disasm example.sp
python -m spacelang.main pack example.sp
python -m spacelang.main run example.spz
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
