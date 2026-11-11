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

The current frontend handles integer, boolean, string, and `None` constants,
basic arithmetic and comparisons, boolean expressions, calls, assignment to
names, attributes and indexes, unpacking assignments, supported augmented
assignments, supported imports, `if`/`else`, `while`, `break`/`continue`, simple
positional functions including nested functions, captured variables and
`nonlocal`, and `for` loops over Python iterables. The reference and
native VMs share iterator bytecode for lists, tuples, strings, `range(...)`, and
other Python iterable objects. Sequence indexing and slicing, including slice
assignment, and list comprehensions with one or more synchronous `for` clauses,
name targets, and `if` filters are supported.

This is still a Python subset, not full Python; features such as classes,
exceptions in source code, generators, set unpacking, and async syntax are not
implemented. Set literals, `set()`, membership checks, and set comprehensions
are supported. Dictionary literals, including `**mapping` unpacking, key
lookup, assignment, and augmented assignment are supported. Dictionary
comprehensions support synchronous `for` clauses with name targets and `if`
filters.
Functions may collect extra positional arguments with `*args` and extra
keyword arguments with `**kwargs`. Positional-only parameters (`/`) and
keyword-only parameters (`*`) are supported. Default expressions use the
supported expression subset and are evaluated when the function is defined
(or, for nested functions, when the closure is created).
Keyword arguments work for top-level functions, builtins, and dynamic
SpaceLang closures. Calls may expand positional iterables and keyword mappings
with `*values` and `**options`; ordinary explicit keyword arguments to methods
remain unsupported. Arithmetic expressions support `+`, `-`, `*`, `/`, `%`,
`//`, and `**`; identity comparisons (`is` and `is not`) are supported.
Top-level and nested functions support required and optional positional
parameters, positional-only parameters, and keyword-only parameters.
Positional and keyword arguments, including argument expansion, are supported
for direct calls to known top-level functions. Builtin keyword arguments are
supported where the target builtin accepts them. Functions use statically determined
local variables; `global` declarations and lexical closures with `nonlocal`
updates are supported.
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

## Space instruction table

Every `.sp` token is the count of spaces before a newline. The first token of
each instruction is its opcode ID; the following tokens are its arguments.
`PUSH_INT` uses zig-zag encoding for its integer argument. `PUSH_STR` is
followed by a length and then one code-point token per character. Name IDs refer
to the program's name table. The `.name`, `.label`, and `.enddef` forms are
assembler directives, not VM opcodes.

| ID | Mnemonic | Arguments in `.spasm` | Reference VM effect |
| ---: | --- | --- | --- |
| 0 | `NOP` | none | Do nothing. |
| 1 | `CALL` | `func_id, nargs` | Call a builtin or user function with positional arguments. A builtin's result is pushed. |
| 2 | `CALL_KW` | `func_id, npos, nkw` | Call a builtin with positional and keyword arguments; user functions are not supported here. |
| 3 | `CALL_OBJ` | `nargs` | Pop a callable and its positional arguments, call it, and push the result. |
| 4 | `IMPORT` | `module_id` | Import a supported module and push it. |
| 5 | `OP` | `operation_id` | Pop two operands, apply the selected binary operation, and push the result. |
| 6 | `STACK` | `stack_operation_id` | Apply a stack manipulation operation. |
| 7 | `PUSH_INT` | `integer` | Push an integer; its argument token is zig-zag encoded. |
| 8 | `PUSH_STR` | `length, codepoint...` | Push a string from the specified number of code points. |
| 9 | `LOAD_GLOBAL` | `name_id` | Push a global value; an undefined name raises an error. |
| 10 | `STORE_GLOBAL` | `name_id` | Pop a value and store it as a global. |
| 11 | `GET_ATTR` | `name_id` | Pop an object and push the named attribute. |
| 12 | `CALL_METHOD` | `name_id, nargs` | Pop a receiver and arguments, call the named method, and push its result. |
| 13 | `INDEX` | `reserved` | Pop a key and container, then push `container[key]`; the argument is currently ignored. |
| 14 | `BUILD_LIST` | `count` | Pop `count` values and push a list in their original order. |
| 15 | `BUILD_TUPLE` | `count` | Pop `count` values and push a tuple in their original order. |
| 16 | `CONCAT` | `count` | Pop and concatenate `count` homogeneous strings, bytes, lists, or tuples. |
| 17 | `DEF` | `func_id, nargs` | Mark a function entry; execution skips its body when reached in normal flow. |
| 18 | `RET` | none | Return the top stack value from the current function. |
| 19 | `LOAD_ARG` | `index` | Push a function argument by slot index. |
| 20 | `LOAD_LOCAL` | `slot` | Push a local variable by slot index. |
| 21 | `STORE_LOCAL` | `slot` | Pop and store a local variable by slot index. |
| 22 | `JMP` | `target_ip` | Jump to an instruction index. |
| 23 | `JZ` | `target_ip` | Pop a condition; jump if it is false. |
| 24 | `JNZ` | `target_ip` | Pop a condition; jump if it is true. |
| 25 | `RAISE` | none | Pop an exception value and raise it through the active handler, if any. |
| 26 | `TRY` | `catch_ip, finally_ip` | Begin a protected region; `0` means that the corresponding handler is absent. |
| 27 | `END_TRY` | none | Close a try/catch/finally region and continue its control flow. |
| 28 | `SETUP_WITH` | none | Pop a value onto the VM's with-stack; this alone does not implement Python's full `with` protocol. |
| 29 | `HALT` | none | Stop execution; if the stack is non-empty, pop its top as the run result. |
| 30 | `GET_ITER` | none | Pop an iterable and push its iterator. |
| 31 | `FOR_ITER` | `target_ip` | Advance the iterator at the top of the stack and push its next value; on exhaustion, pop it and jump to `target_ip`. |
| 32 | `STORE_ATTR` | `name_id` | Pop an object and value, then assign the value to the named attribute. |
| 33 | `STORE_INDEX` | none | Pop a key, container, and value, then assign `container[key] = value`. |
| 34 | `UNPACK_SEQUENCE` | `count` | Unpack exactly `count` values from an iterable onto the stack. |
| 35 | `PUSH_NONE` | none | Push Python's `None` value. |
| 36 | `MAKE_CLOSURE` | `func_id, cell_count, arg_count` | Pop captured cells and push a legacy positional-only closure. |
| 37 | `CELLIFY` | `local_slot` | Wrap a local slot in a shared closure cell. |
| 38 | `LOAD_CELL_REF` | `local_slot` | Push the cell object stored in a local slot. |
| 39 | `LOAD_DEREF` | `closure_index` | Push a captured cell reference from the current closure. |
| 40 | `CALL_OBJ_KW` | `positional_count, keyword_count` | Call a dynamic callable with positional and named arguments. |
| 41 | `MAKE_CLOSURE_SIG` | `func_id, cell_count, arg_count, default_count` | Pop captured cells and signature metadata, then push a closure. |
| 42 | `MAKE_CLOSURE_KWONLY` | `func_id, cell_count, positional_count, keyword_only_count, positional_default_count, keyword_default_count` | Create a closure with positional and keyword-only parameter metadata. |
| 43 | `MAKE_CLOSURE_ARGS` | `func_id, cell_count, positional_count, keyword_only_count, positional_default_count, keyword_default_count, has_varargs, has_kwargs` | Create a closure with variadic argument metadata. |
| 44 | `BUILD_DICT` | `count` | Pop `count` key/value pairs and push a dictionary. |
| 45 | `CALL_OBJ_EX` | none | Call a dynamic callable with a positional list and keyword dictionary. |
| 46 | `CALL_BUILTIN_EX` | `func_id` | Call a builtin with a positional list and keyword dictionary. |
| 47 | `LIST_EXTEND` | none | Extend the list below the stack top with the iterable at the top. |
| 48 | `DICT_MERGE` | none | Merge the mapping at the stack top into the keyword dictionary below it, rejecting duplicate or non-string keys. |
| 49 | `MAKE_CLOSURE_POSONLY` | `func_id, cell_count, positional_only_count, positional_count, keyword_only_count, positional_default_count, keyword_default_count, has_varargs, has_kwargs` | Create a closure with positional-only parameter binding metadata. |

`OP` operation IDs:

| ID | Operation |
| ---: | --- |
| 1 | Addition (`left + right`) |
| 2 | Subtraction (`left - right`) |
| 3 | Multiplication (`left * right`) |
| 4 | True division (`left / right`) |
| 5 | Modulo (`left % right`) |
| 6 | Equal (`left == right`) |
| 7 | Less than (`left < right`) |
| 8 | Greater than (`left > right`) |
| 9 | Not equal (`left != right`) |
| 10 | Less than or equal (`left <= right`) |
| 11 | Greater than or equal (`left >= right`) |

`STACK` operation IDs (`top` means the rightmost stack value):

| ID | Operation | Effect |
| ---: | --- | --- |
| 1 | `DUP` | Duplicate the top value. |
| 2 | `SWAP` | Swap the top two values. |
| 3 | `DROP` | Remove the top value. |
| 4 | `OVER` | Copy the second value to the top. |
| 5 | `ROT` | Rotate the top three values from `[a, b, c]` to `[b, c, a]`. |

`IMPORT` module IDs are `0=math`, `1=random`, `2=os`, `3=re`, and `4=sys`.
Jump targets and name IDs are zero-based. Function IDs of `10000` or greater
identify user-defined functions in the reference VM.

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
