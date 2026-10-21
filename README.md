# SpaceLang

SpaceLang is an experimental stack-based language toolkit. It currently
contains a Python reference VM, a small Python-subset frontend, and tools for
assembling, disassembling, and encoding SpaceLang programs.

> **Status:** Early development. The frontend and VM implement a subset of
> Python and the project is not yet a drop-in Python runtime. See the source and
> tests for the behavior currently supported.

## Requirements

- Python 3.10 or newer

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

The current frontend handles basic integer and string constants, arithmetic,
comparisons, calls, assignments, `if`/`else`, `while`, and simple functions.
Many Python features are not implemented; unsupported syntax raises an error
rather than being compiled.

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
and Python-subset frontend behavior.
