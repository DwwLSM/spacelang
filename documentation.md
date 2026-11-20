# SpaceLang Project Documentation

SpaceLang is a language implementation centered on `.sp` source. `.py` support is
an optional frontend that lowers `.py` syntax to `.sp`. The toolchain provides:

- A compiler that reads `.sp` source and produces `.sp` or executable artifacts.
- A bounded optional `.py` frontend.
- A human-readable assembly syntax.
- VM/runtime implementations that execute `.sp` artifacts.
- A peephole optimizer and tools to inspect, encode, compress, and run programs.

`.sp` is the SpaceLang source language. `.py` is an optional surface syntax lowered to `.sp`.
Supporting `.py` input does not make SpaceLang Python.

> **Audience:** students, instructors, contributors, and anyone evaluating the
> package. This guide describes the checked-in implementation and current
> behavior; it is not a promise of full Python compatibility.

## Contents

1. [Project at a glance](#project-at-a-glance)
2. [Learning goals and design](#learning-goals-and-design)
3. [Quick start](#quick-start)
4. [Compiler and execution pipeline](#compiler-and-execution-pipeline)
5. [Python-subset reference](#python-subset-reference)
6. [Assembly language](#assembly-language)
7. [Internal compiler representation](#internal-compiler-representation)
8. [Instruction set reference](#instruction-set-reference)
9. [SpaceLang file format](#spacelang-file-format)
10. [Optimization](#optimization)
11. [Virtual machines](#virtual-machines)
12. [Builtins, imports, and safety](#builtins-imports-and-safety)
13. [Command-line reference](#command-line-reference)
14. [Python API reference](#python-api-reference)
15. [OPT_SP visual debugger](#opt_sp-visual-debugger)
16. [Benchmark and animation](#benchmark-and-animation)
17. [Tests, CI, and packaging](#tests-ci-and-packaging)
18. [Known limitations and extension ideas](#known-limitations-and-extension-ideas)
19. [Glossary](#glossary)

---

## Project at a glance

SpaceLang is a Python package and experimental language implementation created
to explore programming-language construction. It provides:

- A compiler for a deliberately limited subset of Python.
- A compact instruction model and stack-based instruction set.
- A `.sp` source representation with whitespace-token serialization; `.spz` is a gzip container.
- A Python reference VM used to execute `.sp` artifacts.
- An experimental native C++17 virtual machine exposed through pybind11.
- A peephole optimizer and tooling to inspect, encode, compress, run, and
  self-copy programs.
- An optional browser visualizer, benchmark, and introduction animation.

The package metadata names the distribution `spacelanguage`, currently at
version `0.2.0`, and the import package `spacelang`. The project requires Python
3.10 or later. PyPI provides prebuilt wheels for CPython 3.10–3.14 on x64
Windows, x86-64 and ARM64 Linux, and universal2 macOS (Intel and Apple Silicon).
Installing one of these wheels does not require a local compiler. Building the
native extension from source requires CMake 3.18 or later, a C++17-capable
compiler, and pybind11 (provided by the package build configuration).

The implementation is experimental. The compiler does not accept arbitrary
Python programs, and the native VM is not a drop-in replacement for the
reference engine in all environments or for all behavior.

## Learning goals and design

The codebase is useful as a course-project showcase because it connects
multiple layers that are often taught separately:

1. **Parsing source syntax** with Python's built-in `ast` module.
2. **Compiling syntax trees** into a custom instruction sequence.
3. **Representing programs** with explicit instructions, names, labels, and
   function metadata.
4. **Executing a stack machine**, including calls, local frames, closures, and
   control flow.
5. **Designing a serialized format** that can be inspected as whitespace.
6. **Building and integrating a native extension** with CMake and pybind11.
7. **Testing two implementations** against common cases and each other.
8. **Packaging and presenting software** with a CLI, web debugger, CI, and
   supplementary media.

### Design choices

- **A Python reference engine comes first.** The Python VM makes semantics and
  instruction behavior easier to inspect while the C++ implementation evolves.
- **The `.sp` representation has a readable assembly view.** Assembly makes instruction structure easier to inspect; it is not a replacement or alternative definition of `.sp` source.
- **The encoded file uses only spaces and newlines as token delimiters.** It
  demonstrates a custom serialization scheme, not an attempt to execute
  whitespace one character at a time.
- **The language subset is explicit.** Unsupported AST forms fail during
  compilation instead of being silently approximated.
- **The browser debugger uses Pyodide.** The local Python server supplies its
  static page and assets; program tracing is performed by Python running in the
  browser.
- **`.sp` is source.** The whitespace token format is one representation of `.sp`, not the definition of the language.
- **The `.py` frontend is optional sugar.** It lowers supported syntax to `.sp` and does not define the language identity.
- **The Python VM is a readable reference implementation.** It is not the compiler or the language core.
- **Assembly is a human-readable view.** It is not the `.sp` source language.

## Quick start

### Install from PyPI

For supported CPython and platform combinations, install the prebuilt wheel:

```bash
python -m pip install spacelanguage
```

### Install from a checkout

```bash
git clone https://github.com/DwwLSM/spacelang.git
cd spacelang
python -m pip install -e ".[dev]"
```

Editable installation builds the C++ extension as part of package
installation, so a usable C++17 toolchain and CMake 3.18+ are required. The
same applies when installing from a source distribution or local checkout
without editable mode (`python -m pip install .`); supported PyPI wheel installs
do not need these build tools.

### Compile a Python-subset file

Create `hello.py`:

```python
def greet(name="world"):
    return f"Hello, {name}!"

print(greet())
```

Compile and run:

```bash
spacelang compile-py hello.py hello.sp
spacelang disasm hello.sp
spacelang run hello.sp
```

Expected output:

```text
Hello, world!
```

`compile-py` optimizes by default and embeds the program name table in the
output. `disasm` shows the decoded instructions. `run` uses the Python
reference VM unless `--engine cpp` is specified.

### Compile and execute in Python

```python
from spacelang.pyfront import compile_py
from spacelang.vm_py import VM

source = """
def square(value):
    return value * value

total = 0
for number in range(1, 5):
    total = total + square(number)
print(total)
"""

program = compile_py(source)
vm = VM(program)
vm.run()
```

This prints `30`. `compile_py` returns a `Program`; it does not run or
automatically optimize it. Apply `spacelang.optimize(program)` if you want to
use the optimizer in a Python script.

### Assemble directly

```python
from spacelang import assemble
from spacelang.vm_py import VM

program = assemble("""
PUSH_INT 20
PUSH_INT 22
OP 1
HALT
""")
assert VM(program).run() == 42
```

### Inspect an encoded program

```python
from spacelang import assemble, disassemble, encode, parse, tokenize

program = assemble("PUSH_INT 2\nPUSH_INT 3\nOP 1\nHALT\n")
encoded = encode(program)
decoded = parse(tokenize(encoded))
print(disassemble(decoded))
```

The core stages are individually callable, which is useful for classroom
demonstrations and experiments.

## Compiler and execution pipeline

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

`compiler.exe` is a compiler, not a VM or interpreter. `spvm.exe` and `sp_vm` are the VM/runtime implementations that execute `.sp`.

## Python-subset reference

The compiler uses Python's AST as a parser, then visits only supported nodes.
The list below summarizes supported constructs in this version. Some
constructs are supported only in combinations that the compiler knows how to
lower; a successful parse by Python itself does not imply SpaceLang support.

### Values and expressions

Supported values include:

- Integers, booleans, floating-point literals, strings, and `None`.
- Lists, tuples, dictionaries, and sets.
- Names, attribute reads, indexing, and slices.
- F-strings without format specifications; conversions are limited to default,
  `!s`, and `!r`.
- Conditional expressions (`a if test else b`).
- Unary plus, unary minus, and `not`.
- Boolean `and` and `or`.
- Arithmetic: `+`, `-`, `*`, `/`, `%`, `//`, and `**`.
- Comparisons: equality and ordering, membership (`in`, `not in`), and
  identity (`is`, `is not`).
- Calls, including supported positional and keyword argument binding, `*args`
  expansion, and `**kwargs` expansion.
- List, dictionary, and set comprehensions with synchronous iteration,
  name/unpacking targets, and `if` filters.

Supported mutation and assignment includes assignment to names, attributes,
and indexes; supported augmented assignment; unpacking sequences; and slice
assignment. Dictionary construction supports mapping unpacking (`**mapping`),
and dictionary comprehensions can use name or unpacking loop targets.

### Statements and functions

- Expression statements, `pass`, and `return`.
- `if`/`else`, `while`, and synchronous `for` loops.
- `break` and `continue` within supported loops.
- Top-level and nested `def` functions.
- Positional and keyword arguments, positional-only parameters (`/`),
  keyword-only parameters (`*`), default values, `*args`, and `**kwargs`.
- Captured variables in nested functions and `nonlocal` updates.
- `global` declarations.
- Supported `import` and `from ... import ...` forms for the fixed module
  table described in [Builtins, imports, and safety](#builtins-imports-and-safety).

Default expressions are compiled and evaluated at function definition time;
for nested functions, defaults are captured when the closure is created.
Function-local names are determined statically. Argument binding is implemented
by SpaceLang, not by executing the function body as native Python.

### Important unsupported syntax

The current frontend is not full Python. Among the unsupported features are:

- Classes, class definitions, and async functions/syntax.
- Source-level `try`/`except`/`finally` and exception handling constructs.
- Generators, `yield`, and asynchronous iteration.
- Starred unpacking/targets in `for` loops and comprehensions.
- Set unpacking.
- Explicit keyword arguments to methods.
- F-string format specifications and conversions other than the limited forms
  above.

The IR contains some exception-related operations, but that does not imply
that the Python frontend compiles Python exception statements. Compilation
errors are preferable to silently producing a different program.

## Assembly language

Assembly is line-oriented, with one mnemonic instruction per line. A typical
program is:

```text
PUSH_INT 2
PUSH_INT 3
OP 1
CALL 0 1
STACK 3
HALT
```

`CALL 0 1` invokes builtin ID 0 (`print`) with one positional argument.
`STACK 3` drops the return value produced by the builtin. `HALT` ends the
program.

The assembler supports the mnemonics represented in the instruction table
below, and supports symbolic labels and name-table directives. `.label` marks
a jump destination; `.name` associates source-level names with numeric IDs;
`.enddef` closes a function definition region. These are assembler conveniences
and do not have opcode IDs.

Jump targets are instruction indices after assembly resolution. Name operands
refer to the program name table. The precise accepted forms and argument
validation are implemented by `spacelang/asm.py`; use `assemble()` or the CLI
instead of assuming that Python syntax can be pasted into assembly.

## Internal compiler representation

The IR is intentionally small:

```python
from spacelang.ir import Instr, OP, Program

program = Program(
    instrs=[
        Instr(OP.PUSH_INT, [42]),
        Instr(OP.HALT),
    ]
)
```

`Instr` stores:

- `op`: an `OP` value (or integer opcode).
- `args`: a list of integer or string operands.
- `line`: optional source-line information, used in diagnostics and traces.

`Program` stores:

- `instrs`: instruction sequence.
- `names`: mapping from source names to integer IDs.
- `labels`: mapping from assembler labels to instruction indices.
- `funcs`: mapping from function IDs to entry/end instruction indices.
- `try_table`: metadata tuples used by exception-oriented VM operations.

The encoder validates opcode and operand shapes, then emits only integer tokens;
name and label concepts are resolved before serialization.

## Instruction set reference

This table describes the instruction IDs in `spacelang/ir.py`. Stack effects
are described from the perspective of the Python VM. `name_id` refers to an
entry in the `Program` name table; `target` is an instruction index. For exact
runtime behavior, particularly for hand-written `.sp`, the VM source remains
authoritative.

| ID | Mnemonic | Arguments | Summary |
| ---: | --- | --- | --- |
| 0 | `NOP` | — | No operation. |
| 1 | `CALL` | `func_id, nargs` | Call a builtin or registered function with positional arguments. |
| 2 | `CALL_KW` | `func_id, npos, nkw` | Call a builtin with positional and keyword arguments. |
| 3 | `CALL_OBJ` | `nargs` | Call a callable popped from the stack with positional arguments. |
| 4 | `IMPORT` | `module_id` | Import a module from the fixed module table. |
| 5 | `OP` | `operation_id` | Apply a binary operation to the top two values. |
| 6 | `STACK` | `stack_operation_id` | Apply a stack manipulation operation. |
| 7 | `PUSH_INT` | `integer` | Push a signed integer (zig-zag encoded in the token stream). |
| 8 | `PUSH_STR` | `length, codepoint...` | Push a string from Unicode code points. |
| 9 | `LOAD_GLOBAL` | `name_id` | Push a global value. |
| 10 | `STORE_GLOBAL` | `name_id` | Pop and store a global value. |
| 11 | `GET_ATTR` | `name_id` | Replace an object on the stack with its named attribute. |
| 12 | `CALL_METHOD` | `name_id, nargs` | Call a named method on a receiver. |
| 13 | `INDEX` | `reserved` | Pop key and container, then push `container[key]`; operand is currently ignored. |
| 14 | `BUILD_LIST` | `count` | Pop values and build a list in source order. |
| 15 | `BUILD_TUPLE` | `count` | Pop values and build a tuple in source order. |
| 16 | `CONCAT` | `count` | Pop and concatenate homogeneous strings, bytes, lists, or tuples. |
| 17 | `DEF` | `func_id, nargs` | Register/mark a function body and skip it in normal instruction flow. |
| 18 | `RET` | — | Return the top value from the active function. |
| 19 | `LOAD_ARG` | `index` | Push an argument by slot index. |
| 20 | `LOAD_LOCAL` | `slot` | Push a local variable by slot index. |
| 21 | `STORE_LOCAL` | `slot` | Pop and store a local variable. |
| 22 | `JMP` | `target` | Unconditional jump. |
| 23 | `JZ` | `target` | Pop a value; jump if it is false. |
| 24 | `JNZ` | `target` | Pop a value; jump if it is true. |
| 25 | `RAISE` | — | Pop and raise an exception through active VM handlers. |
| 26 | `TRY` | `catch_ip, finally_ip` | Enter a protected region; zero indicates an absent handler. |
| 27 | `END_TRY` | — | Finish a protected region. |
| 28 | `SETUP_WITH` | — | Push a value to the VM with-stack; this alone is not Python's full `with` protocol. |
| 29 | `HALT` | — | Stop; return the top stack value if available. |
| 30 | `GET_ITER` | — | Replace an iterable with its iterator. |
| 31 | `FOR_ITER` | `target` | Push the next iterator value, or pop exhausted iterator and jump. |
| 32 | `STORE_ATTR` | `name_id` | Pop object and value, then assign the named attribute. |
| 33 | `STORE_INDEX` | — | Pop key, container, and value; assign `container[key] = value`. |
| 34 | `UNPACK_SEQUENCE` | `count` | Unpack exactly `count` iterable values onto the stack. |
| 35 | `PUSH_NONE` | — | Push `None`. |
| 36 | `MAKE_CLOSURE` | `func_id, cell_count, arg_count` | Create a legacy positional-only closure from captured cells. |
| 37 | `CELLIFY` | `local_slot` | Wrap a local slot in a shared closure cell. |
| 38 | `LOAD_CELL_REF` | `local_slot` | Push the cell object in a local slot. |
| 39 | `LOAD_DEREF` | `closure_index` | Push a captured cell reference. |
| 40 | `CALL_OBJ_KW` | `positional_count, keyword_count` | Call a stack-provided callable with positional and named arguments. |
| 41 | `MAKE_CLOSURE_SIG` | `func_id, cell_count, arg_count, default_count` | Create a closure with positional signature/default metadata. |
| 42 | `MAKE_CLOSURE_KWONLY` | `func_id, cell_count, positional_count, keyword_only_count, positional_default_count, keyword_default_count` | Create a closure with keyword-only parameter metadata. |
| 43 | `MAKE_CLOSURE_ARGS` | `func_id, cell_count, positional_count, keyword_only_count, positional_default_count, keyword_default_count, has_varargs, has_kwargs` | Create a closure with variadic parameter metadata. |
| 44 | `BUILD_DICT` | `count` | Pop key/value pairs and build a dictionary. |
| 45 | `CALL_OBJ_EX` | — | Call a stack-provided callable with expanded positional and keyword containers. |
| 46 | `CALL_BUILTIN_EX` | `func_id` | Call a builtin with expanded positional and keyword containers. |
| 47 | `LIST_EXTEND` | — | Extend the list below the stack top with the iterable at the top. |
| 48 | `DICT_MERGE` | — | Merge a mapping into a keyword dictionary; duplicate or non-string keys are rejected. |
| 49 | `MAKE_CLOSURE_POSONLY` | `func_id, cell_count, positional_only_count, positional_count, keyword_only_count, positional_default_count, keyword_default_count, has_varargs, has_kwargs` | Create a closure with positional-only and other signature metadata. |
| 50 | `DICT_UPDATE` | — | Pop a mapping and target dictionary, then update the target with mapping values. |
| 51 | `BUILD_SET` | `count` | Pop values and build a set. |
| 52 | `BUILD_SLICE` | — | Pop lower, upper, and step values; push a Python slice object. |

Opcode 53 is **not** an executable instruction. It marks an optional embedded
JSON name-table trailer after `HALT`.

### Binary operation IDs

`OP` means a binary operation; these IDs are separate from instruction IDs.
The left operand is popped before the right operand is applied as shown.

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
| 12 | Membership (`left in right`) |
| 13 | Non-membership (`left not in right`) |
| 14 | Identity (`left is right`, using VM identity semantics) |
| 15 | Non-identity (`left is not right`) |
| 16 | Floor division (`left // right`) |
| 17 | Exponentiation (`left ** right`) |

### Stack operation IDs

The stack top is the rightmost element:

| ID | Name | Effect |
| ---: | --- | --- |
| 1 | `DUP` | Duplicate the top value. |
| 2 | `SWAP` | Swap the top two values. |
| 3 | `DROP` | Remove the top value. |
| 4 | `OVER` | Copy the second value to the top. |
| 5 | `ROT` | Rotate `[a, b, c]` to `[b, c, a]`. |

### Module IDs

The `IMPORT` instruction uses this fixed mapping:

| ID | Module |
| ---: | --- |
| 0 | `math` |
| 1 | `random` |
| 2 | `os` |
| 3 | `re` |
| 4 | `sys` |

## SpaceLang file format

### Whitespace token stream

Each token is represented as a run of spaces followed by a newline. The token's
integer value is the number of spaces in that run. The newline terminates a
token; instructions are reconstructed from opcode IDs and the known number of
operands for each opcode.

For example:

```text
PUSH_INT 2
```

is encoded as token values `7, 4`: `7` is the `PUSH_INT` opcode, and `4` is
the zig-zag representation of positive integer `2`. Similarly `OP 1` becomes
`5, 1`.

The assembly example:

```text
PUSH_INT 2
PUSH_INT 3
OP 1
CALL 0 1
STACK 3
HALT
```

has token groups:

| Assembly | Tokens |
| --- | --- |
| `PUSH_INT 2` | `7, 4` |
| `PUSH_INT 3` | `7, 6` |
| `OP 1` | `5, 1` |
| `CALL 0 1` | `1, 0, 1` |
| `STACK 3` | `6, 3` |
| `HALT` | `29` |

The lexer accepts spaces and newlines (and normalizes CRLF); other characters
raise `LexError`. A final token without a trailing newline is accepted, but
canonical output terminates every token with a newline. Encoded files should
therefore be treated as data, not as a visually meaningful text listing.

### Integer and string constraints

- A token can contain at most 65,535 spaces (`MAX_LINE`).
- `PUSH_INT` values use signed 64-bit zig-zag encoding. Large positive
  constants may not fit in a single token.
- The encoder limits a single `PUSH_STR` payload to 1,000 code points.
- The Python frontend emits long strings as chunks and concatenates chunks.
- `--compress-source` can factorize large integer constants into smaller
  representable values and operations; it does not gzip the source.

### Embedded names and `.names.json`

Names in instructions are stored by numeric ID. CLI output embeds the name
table after the final `HALT`, using opcode marker 53, a JSON payload length,
and the payload's character-code tokens. The parser recognizes this as
metadata, not executable code. This makes normal compiled `.sp` and `.spz`
files self-describing for disassembly and execution.

Some quine workflows also emit a companion `.names.json` file for SpaceLang
programs. The CLI loader can read this sidecar when an encoded program has no
embedded name table.

### `.spz` compression

`.spz` is a gzip-compressed `.sp` stream. Packing and unpacking do not compile
or transform the underlying instructions. The package uses deterministic gzip
timestamps for generated outputs where applicable.

## Optimization

The optimizer is implemented in `spacelang/peephole.py` and is exposed as
`spacelang.optimize(program, ...)`. The `compile-py` CLI command invokes it by
default; `compile_py()` itself returns the unoptimized frontend IR.

Available passes:

1. **Constant folding:** folds recognized sequences of integer constants and
   operations, while respecting branch targets and avoiding selected
   operations that could raise during folding.
2. **Dead-code removal:** removes instructions that are unreachable from the
   program's reachable control flow, remapping instruction references.
3. **Integer constant pooling:** shares repeated integer constants when the
   transformation is applicable.
4. **Source constant compression:** optional factorization of oversized
   integer constants into smaller literals and operations.

The public parameters are `constant_pool=True`, `dead_code=True`, and
`compress_source=False`. The CLI provides `--no-optimize` to skip all optimizer
passes and `--compress-source` to enable integer source compression. These
switches apply to `compile-py`.

When developing an optimizer pass, preserve jump targets, function ranges,
labels, try-table references, and source-line metadata. Optimized output should
be validated by running the same test inputs through the reference VM.

## Virtual machines

### Python reference VM

`spacelang.vm_py.VM` executes a `Program`. The VM owns an operand stack, globals,
instruction pointer, function metadata, and frames for active calls. Functions
use local slots and argument binding; nested closures share cells for captured
variables. Iteration and collection operations use Python object behavior for
the supported runtime values.

Basic usage:

```python
from spacelang import assemble
from spacelang.vm_py import VM

vm = VM(assemble("PUSH_INT 6\nPUSH_INT 7\nOP 3\nHALT\n"))
result = vm.run()
assert result == 42
```

The `VM` exposes `stack`, `globals_`, and `run()`. The CLI sets `__file__` to
the input program path before execution.

### Native C++ VM

The native engine is implemented in `csrc/vm.cpp` and exposed as
`spacelang.vm_cpp.VM`. It uses pybind11 to exchange Python objects and is built
through `CMakeLists.txt` and scikit-build-core. GCC and Clang builds use
computed-goto dispatch; other compilers use a portable switch dispatcher.

Use the native engine explicitly:

```bash
spacelang run program.sp --engine cpp
```

It is experimental. The Python VM is the reference behavior for cases that
have not been checked for parity. The differential tests and benchmark compare
both engines on selected workloads; passing those tests is not a guarantee of
identical behavior for every Python object or input.

### Errors and source locations

`spacelang.errors.SpaceError` is the base class for package-defined errors.
Subclasses include `LexError`, `ParseError`, `RuntimeError`, `TypeError`,
`StackUnderflow`, `UndefinedFunc`, `UndefinedName`, `UndefinedModule`,
`JumpOutOfRange`, and `EncodingError`. Where available, errors carry a source
`line`, instruction pointer `ip`, and message `msg`.

## Builtins, imports, and safety

The VM exposes a selected Python builtin set:

| Builtin ID | Name |
| ---: | --- |
| 0 | `print` |
| 1 | `input` |
| 2 | `len` |
| 3 | `int` |
| 4 | `float` |
| 5 | `str` |
| 6 | `bool` |
| 7 | `abs` |
| 8 | `range` |
| 9 | `type` |
| 10 | `open` |
| 11 | `getattr` |
| 12 | `setattr` |
| 13 | `callable` |
| 14 | `repr` |
| 15 | `isinstance` |
| 16 | `set` |

Additional functions are registered for the fixed modules: `math` includes
functions such as `sqrt`, `sin`, `cos`, `tan`, `floor`, `ceil`, `fabs`, `exp`,
and `log`; `random` includes `random` and `randint`; `os` includes `system`;
`re` includes `compile`; and `sys` includes `exit`.

**This is not a sandbox.** Programs can call `open`, `input`, `os.system`,
`sys.exit`, and functions or methods available on Python objects. The native
VM also interoperates with Python objects. Do not execute untrusted `.sp` source or
`.py` frontend input. OPT_SP's browser-side execution is for visualization and should not
be relied on as a security boundary.

## Command-line reference

The installed entry point is `spacelang`; the source-checkout form is
`python -m spacelang.main`. Use `spacelang --help` and subcommand `--help` for
the live argument parser.

| Command | Purpose |
| --- | --- |
| `spacelang compile-py SRC DST` | Compile supported Python source to `.sp` or `.spz`. |
| `spacelang asm SRC DST` | Assemble mnemonic source into encoded program output. |
| `spacelang disasm SRC [-o OUTPUT]` | Disassemble a `.sp` or `.spz` file to stdout or a file. |
| `spacelang run SRC [--engine py\|cpp]` | Execute a `.sp` or `.spz` program; Python engine is default. |
| `spacelang pack SRC [DST]` | Gzip a `.sp` file into `.spz`; default destination uses `.spz`. |
| `spacelang unpack SRC [DST]` | Decompress `.spz`; default destination uses `.sp`. |

`compile-py` options:

- `--no-optimize`: do not run the default optimization pipeline.
- `--compress-source`: factorize otherwise-too-large integer constants.

Examples:

```bash
spacelang compile-py source.py output.sp
spacelang compile-py source.py output.sp --no-optimize
spacelang compile-py source.py output.sp --compress-source
spacelang run output.sp --engine py
spacelang run output.sp --engine cpp
spacelang pack output.sp
spacelang unpack output.spz
```

## Python API reference

### Package-level exports

`import spacelang` exposes the following core classes, errors, and functions:

| Export | Purpose |
| --- | --- |
| `Program`, `Instr`, `OP` | IR program, instruction, and opcode enum. |
| `NameTable` | Interns names and resolves IDs. |
| `assemble` | Assembly text to `Program`. |
| `disassemble`, `disasm` | `Program` to assembly text. |
| `encode` | `Program` to whitespace-only text. |
| `tokenize` | Whitespace text to `(value, line)` tokens. |
| `parse` | Tokens to `Program`. |
| `decode` | Whitespace text directly to `Program`. |
| `compile_py` | Supported Python-subset source to `Program`. |
| `optimize` | Optimized copy of a `Program` according to enabled passes. |
| `pack_bytes`, `unpack_bytes` | Gzip compression and decompression for byte strings. |
| `pack_file`, `unpack_file` | Gzip compression and decompression for files. |
| `quine` | Generate a self-copying output file from a source file. |

The package also exports error types: `SpaceError`, `LexError`, `ParseError`,
`RuntimeError`, `TypeError`, `StackUnderflow`, `UndefinedFunc`,
`UndefinedName`, `UndefinedModule`, `JumpOutOfRange`, and `EncodingError`.

### Useful module-level APIs

| API | Module | Notes |
| --- | --- | --- |
| `VM(program)` | `spacelang.vm_py` | Python reference VM. |
| `VM(program)` | `spacelang.vm_cpp` | Native VM wrapper; requires compiled extension. |
| `trace_program(source, is_asm=True, is_sp=False)` | `spacelang.web_bridge` | Run source through traced reference VM; returns a JSON-compatible result dictionary. |
| `TracedVM(program)` | `spacelang.vm_trace` | Reference VM subclass that collects step snapshots. |
| `server(port=8000, host="127.0.0.1", open_browser=True, blocking=True)` | `spacelang.opt_sp` | Start local static debugger server. |
| `open_browser(port=8000)` | `spacelang.opt_sp` | Open the debugger URL in a browser. |

`trace_program` treats input as assembly by default. Set `is_asm=False` for
Python-subset source or `is_sp=True` for encoded whitespace source. On success
it returns `{"ok": True, "trace": ..., "error": None}`. On failure it returns
`{"ok": False, "trace": [], "error": <traceback text>}`.

### Trace shape

Each recorded step contains the instruction step number and instruction
pointer, opcode and argument, source-line information, operand stack, call
stack, globals, reachable heap objects, captured output, and optional error
text. Values are represented by type, representation, and a reference ID for
heap objects. The trace is designed for browser visualization rather than as
a stable interchange format.

## OPT_SP visual debugger

OPT_SP is the browser-based visual debugger. It offers input modes for:

- SpaceLang assembly (`.spasm`).
- Python-subset source.
- Encoded `.sp` whitespace source, entered in the editor or opened using the
  file picker.

The editor can load built-in examples. The visualizer presents program text,
call stack, operand stack, heap/object graph, printed output, and controls for
moving through the trace. Drag the vertical divider between the Program and
state panels to adjust their widths, or drag the dividers between state panels
to adjust their heights. Focused dividers can also be resized with the arrow
keys. Long printed output can be scrolled independently. Select **Live edit**
to edit the source beside the trace; OPT_SP automatically refreshes the
visualization after edits. Select **Exit live edit** to return to the
read-only program view. Live editing uses the source mode selected in the
editor. In either editor, typing `(`, `[`, `{`, `'`, or `"` inserts the
matching closer; typing one of these characters with text selected wraps that
selection. Typing an existing closer skips over it, and Backspace removes an
empty pair. Tab inserts four spaces; with lines selected, Tab indents each line
and Shift+Tab removes up to one indentation level (four spaces or one tab).
Shift+Tab also outdents the current line when there is no selection. Drag
selected text with the mouse to move it
to another position in either editor. A shadowed copy follows the pointer, and
pausing briefly previews
the drop position without moving the editor text until you release the mouse;
the original text stays highlighted throughout the drag. Small pointer
movements do not dismiss the preview; moving outside the editor hides the drag
feedback until the pointer returns. Undo with `Ctrl+Z` (or `Cmd+Z`
on macOS); redo with `Ctrl+Shift+Z` / `Cmd+Shift+Z` or `Ctrl+Y`. Undo and redo
also work in Live edit.

The editor lists `.py`, `.sp`, and `.spasm` files under the directory where
the OPT_SP server was started, including files in subfolders. Nothing is
opened automatically: the page starts empty and asks for a new or existing
file, so a visit never silently replaces the work you left behind. Hidden
files and common environment or dependency folders, including generated
Pyodide module copies, are excluded.
Project-file access is limited to UTF-8 `.py`, `.sp`, and `.spasm` files up to
1 MiB beneath that directory. **Download** saves the current editor contents
to your browser's downloads. **Overwrite** replaces the currently loaded
project file after confirmation. Files opened from your computer can also be
overwritten after confirmation in browsers that support the File System Access
API; otherwise, use Download to save an edited copy. In Live edit, Overwrite is
available while editing a loaded file and writes the live editor contents to
that source after confirmation. The overwrite action is unavailable for
examples.

A buffer that belongs to no file — a fresh "Start a file" choice, an example,
or text carried back from the Studio — has nothing to overwrite, so the button
reads **New file** and the file picker reads *New Python file*, *New Assembly
file* or *New Encoded file*. New file asks for a name, writes it under the
project folder, and refuses to replace an existing path; the editor then treats
the result as the loaded file. The server endpoint behind it is
`POST /api/file/new`, loopback only like the overwrite endpoint.

**Back to editor** in the Studio header asks which representation to carry — the
pane that was being edited is preselected — and opens it in the editor, so the
text moves with you instead of being left behind. It arrives as an unsaved
buffer: same representation, no file path, and the **New file** action to save
it. An empty Studio carries nothing and the editor keeps its own workspace.

### Pages

The server serves one page per task; the home page links all of them.

| Route | Page |
|---|---|
| `/` | home page |
| `/editor` | source editor and visualizer (`/index.html` is an alias) |
| `/visualize` | trace-only view (`/visualize.html` is an alias) |
| `/studio` | three-pane workspace |
| `/docs` | this document, rendered in the browser |
| `/tutorial` | five-minute walkthrough |

`/docs` is rendered on the server from `documentation.md` at request time:
headings, lists, fenced code blocks, tables and links become HTML, and the
table of contents is built from the same pass. Anchors follow GitHub's slug
rules, so the links written inside the document keep working on both sites,
and raw HTML in the document is escaped rather than inserted. Editing
`documentation.md` changes the page on the next request; there is no build
step. The copy that an installed wheel renders is produced by
`tools/build_static.py`, described under *Prepare browser assets*.

The header's **Settings** menu is on every page: **Home** (left out on the home
page itself), **Studio (new tab)**, **LLM settings**, **Reload page** and
**Stop server**, plus the entries that only make sense where they apply —
**New file…** in the editor, the pane layout switch and the editor/visualizer
shortcuts in the studio. The LLM settings dialog is the same one the studio
uses for the mirror sync, so the endpoint, model and key can be set before any
editor tab is open; they live in `localStorage` and travel as request headers.

### Home scene

The home page's art column runs an animated ASCII scene instead of a static
drawing. Two styles are registered: `christmas-tree`, which is the software 3D
point cloud from `design/ascii-christmas-tree.html` ported to a component, and
`token-rain`, in which SpaceLang tokens fall onto a skyline of landed
instructions. The switcher in the corner of the panel remembers the choice in
`localStorage`.

The factory is `static/js/ascii-scene.js`. It sizes the canvas to its container,
follows layout changes with a `ResizeObserver`, stops the render loop while the
tab is hidden or the panel is scrolled out of view, and releases observers,
listeners and buffers on `destroy()`. A style only projects and shades into the
shared character grid, which is what keeps the two so different scenes on one
lifecycle. The home page imports the scene with a dynamic `import()`, so the
editor and studio pages never download it, and the static tree in `home.html`
stays in the DOM as the no-script fallback.

### Assistant

Every page carries the assistant: the home page in its right column, the others
in a drawer that **Assistant** in the header folds open and shut. The
transcript is per page and lives in `localStorage`: forty messages are kept, the
last twelve travel with the next request, and **Clear** forgets the
conversation.

The system prompt is chosen by the server from the page name (`home`, `editor`,
`studio`, `visualize`, `docs`, `tutorial`) and never comes from the browser, so
the assistant answers as that page's helper rather than as a generic chatbot.
`README.md` and `documentation.md` are appended to it — re-read only when they
change, capped at 80 000 characters — because the answers live there: the
instruction table, the operator codes and the `.sp` format. That is why a turn
carries roughly 19 000 prompt tokens even before the conversation. A short
reminder closes the prompt, after the documents, so a conversation that started
with a refusal ("I have no instruction table") does not stay anchored to it.
It is asked to answer in assembly (`spasm`), because that is the readable form
of the language; the encoded `.sp` block under each listing is produced by
compiling that listing on the server, never written by the model, and a guessed
`.sp` block is dropped. The panel draws those runs of spaces as `·` so the
encoded form is visible at all.

The reverse direction is checked rather than trusted. When the question contains
an assembly listing and the answer offers Python, the server compiles both and
appends the verdict: either the two compile to the same instructions, or the
answer is called a sketch with the reason. Suggested mirrors are often wrong —
`result = 2 + 3` adds `STORE_GLOBAL`, and a bare `2 + 3` adds `STACK 3` — so a
listing with no value-consuming instruction has no Python source at all, and the
Studio's sync would reject every candidate.

Requests share the mirror sync's key, token bucket and single-flight gate, and
switch the model's hidden reasoning off; an answer cut off by the token limit is
still shown, with a note next to the input. Like the other model endpoints it is
loopback only, and the page never sends the encoded `.sp` program because it
never has it: the transcript is whatever the user typed.

### Start the server

The installed entry point is:

```bash
spacelang-opt-sp --port 8000
```

Useful options:

```bash
spacelang-opt-sp --help
spacelang-opt-sp --host 127.0.0.1 --port 8000 --no-browser
spacelang-opt-sp --background --port 8000
spacelang-opt-sp --stop --port 8000
```

Stop a foreground server from either debugger page with **Stop server** or
**Ctrl+Alt+Q** (**Cmd+Option+Q** on macOS); confirm the prompt, then close the
tab. **Ctrl+C** in the terminal remains available. Use `--background` to
detach the server; `--stop` shuts down the background server on the specified
port. Background mode is limited to loopback hosts, and its log is written to
the system temporary directory.

From Python:

```python
from spacelang.opt_sp import server

server(port=8000)
```

By default the server binds to loopback (`127.0.0.1`), opens a browser, and
blocks until interrupted. For embedding, `blocking=False` starts a daemon
server thread and returns the server object and URL; callers are responsible
for closing the returned server when finished.

The server process serves files from `spacelang/opt_sp/static`; the browser
loads Pyodide and executes the traced Python implementation in-browser. The
server is not a remote code execution API. Its project file picker is enabled
by default only when bound to loopback. Binding to a non-loopback host changes
network exposure; enable project file access there only if intended:

```bash
spacelang-opt-sp --host 0.0.0.0 --allow-project-files
```

The file picker exposes supported source files beneath the server's working
directory to clients that can reach it. Avoid enabling it on an untrusted
network.

Published PyPI wheels include the prepared browser assets, so no asset build
step is needed after a wheel installation.

### Studio, the multi-pane workspace

`http://127.0.0.1:8000/studio` (or the **Studio (new tab)** item in the settings
menu) shows one program in three representations at once:

| Pane | Content | Produced by |
|---|---|---|
| `py` | Python surface syntax | a person, or the model |
| `spasm` | assembly text | `disassemble(program)` |
| `sp` | encoded token stream | `encode(program)` |

Editing a pane re-derives the others after a 250 ms pause. The forward
direction is deterministic (`py` compiles to a program, which disassembles and
encodes); there is no rule that turns a program back into Python, so editing
`spasm` or `sp` marks `py` as `stale` and leaves its text untouched. The
`annotations` button on the assembly pane hides or restores the
`; line=N spaces=...` comments; the `follow` button keeps the active line of a
trace in view; every divider is draggable and remembered, and the settings menu
switches the panes between stacked and side by side.

Each pane carries its own **Run** button. Tracing happens in the browser and
fills the shared Call Stack, Operand Stack, Heap and Printed Output panels, so
the same page works for a `.py` source, an assembly listing and an encoded
artifact.

#### Rewriting the Python mirror

The `stale` mirror can be rewritten by a model, once you point the studio at an
OpenAI-compatible endpoint. Configuration is layered, highest first: the **LLM
settings** dialog (stored in `localStorage`), the command line, the environment
or a `.env.local` file in the working directory, then built-in defaults.

```bash
spacelang-opt-sp --port 8000 \
  --llm-base-url https://host/litellm/v1 \
  --llm-model ModelName \
  --llm-api-key-file ~/.config/spacelang/llm-key
```

The equivalent environment variables are `LITELLM_BASE_URL`, `LITELLM_MODEL` and
`LITELLM_API_KEY`; `.env.local` is read in the same order and never overrides a
real environment variable. There is deliberately no `--llm-api-key` flag: keys on
a command line end up in process listings and shell history.

Three modes are offered: `manual` (a **Sync with AI** button appears while the
mirror is stale, and nothing runs until it is clicked), `auto` (sync about 1.5 s
after an edit stops, with a cooldown) and `off`. Requests are capped by a shared
token bucket, 40 per minute by default, and `busy`/`rate_limited` answers carry a
`retry_after`.

Every answer is verified locally before it is shown: `compile_py(answer)` must
produce the same instruction stream as `assemble(spasm)`, ignoring line numbers
and symbol tables. A mismatch is reported as `not_equivalent` with the first
differing instruction, and the editor keeps its text. There is no way to accept
an unverified answer.

The encoded `.sp` program is never sent to the model: the request carries the
Python mirror and the assembly only, and the server derives the previous
assembly by compiling the stale mirror itself. The endpoint is loopback-only;
binding the server to a non-loopback host disables both `/api/refine-py` and
`/api/llm-status`.

### Prepare browser assets

Generated Pyodide and SpaceLang module assets are excluded from Git. Contributors
working from a source checkout prepare them from the repository root with:

```bash
python tools/build_static.py
python tools/build_static.py --check
```

The build helper pins Pyodide 0.26.2, downloads a subset of its distribution,
copies the pure-Python SpaceLang modules, generates a module manifest, and
copies `documentation.md` so an installed wheel can render `/docs` without the
repository root. `--check` verifies expected files, a non-empty module
manifest, and that the copied document still matches its source; edit the
Markdown at the root and rerun the helper rather than the copy. The smoke
workflow prepares and checks these files before running `tests/test_opt_sp.py`.
Generated assets are sizeable and are not necessary for the core compiler or
VM tests.

## Benchmark and animation

### VM benchmark

The benchmark lives in `benchmarks/benchmark_vm.py`:

```bash
python -m benchmarks.benchmark_vm --n 25 --repeat 3
```

It compiles a recursive workload, runs both VM engines, verifies equal results,
and reports median execution time and relative speedup. Timing depends on
hardware, build options, Python version, and system load. It is an experiment,
not a performance guarantee or a general-purpose benchmark suite.

### Project presentation and animation

`scene.py` contains a Manim introduction scene and four language/subtitle
variants:

- `SpacelangIntroEnglishWithSubtitle`
- `SpacelangIntroEnglishWithoutSubtitle`
- `SpacelangIntroChineseWithSubtitle`
- `SpacelangIntroChineseWithoutSubtitle`

Install the project's optional extra and Manim's required native/system
dependencies:

```bash
python -m pip install -e ".[animation]"
```

Render a variant:

```bash
manim -ql scene.py SpacelangIntroEnglishWithSubtitle
```

The output is written under Manim's `media/` directory, which is ignored by
Git. Refer to the official Manim installation guide for system dependencies.

The separate `remotion/` project provides a 60-second English introduction
with burned-in subtitles and an SRT sidecar, while preserving the Manim scenes.
Its visual beats move from source and compiler to one stack execution, an exact
`.sp` token walkthrough, the OPT_SP trace, and a one-pass comparison of both
VMs. From that directory, run `npm ci` and `npm run dev` to preview, or
`npm run render` to render an MP4 under `remotion/out/`. See
`remotion/README.md` for Node.js requirements and details.

### Suggested course-project walkthrough

A short demonstration can follow the same path as the implementation:

1. **Show the source example** and explain that `compile_py()` accepts a
   documented subset rather than all of Python.
2. **Compile and disassemble it** to show how source-level statements become
   stack instructions and control-flow jumps.
3. **Run the program in the reference VM**, then use `--engine cpp` to explain
   the native implementation and the role of differential tests.
4. **Open OPT_SP** and step through the operand stack, call stack, globals, and
   heap snapshots.
5. **Close with engineering work:** the encoded `.sp` format, optimization
   passes, automated test matrix, package build, and the boundaries that remain
   experimental.

For the browser portion, generate the optional static assets before the
presentation with `python tools/build_static.py`. For a concise initial
presentation, the examples in the root README are sufficient; the detailed
tables in this document are useful for questions and technical follow-up.

## Tests, CI, and packaging

### Run tests

Install development dependencies and run the complete test suite:

```bash
python -m pip install -e ".[dev]"
python -m pytest
```

The pytest configuration sets the repository root on the import path and uses
`tests/` as the test directory. Some example programs and format fixtures are
also kept in `test_spaclang/`.

### Test organization

| Test file/group | Coverage area |
| --- | --- |
| `tests/test_m0.py`, `test_m1.py`, `test_m2.py` | Early IR, VM, assembly, encoding, and control-flow behavior. |
| `tests/test_vm_py.py` | Python VM execution, calls, locals, collections, and runtime semantics. |
| `tests/test_vm_cpp.py` | Native VM behavior. |
| `tests/test_differential.py` | Selected Python/native parity cases. |
| `tests/test_pyfront.py` | Python-subset compilation and syntax behavior. |
| `tests/test_peephole.py` | Optimization transformations and behavior. |
| `tests/test_compress.py` | Gzip byte and file helpers. |
| `tests/test_main.py` | Command-line behavior and program file handling. |
| `tests/test_opt_sp.py` | Trace API and debugger server smoke tests. |
| `tests/test_quine.py` | Python and SpaceLang quine generation. |
| `tests/test_0/`, `tests/test_quine/`, `test_spaclang/` | Example programs and round-trip/format fixtures. |

### Continuous integration

- `.github/workflows/tests.yml` runs tests on Linux, macOS, and Windows with
  Python 3.10 through 3.14.
- `.github/workflows/opt-sp-smoke.yml` uses Python 3.10 through 3.12 to build
  static debugger assets, check them, and run debugger smoke tests.
- `.github/workflows/publish-testpypi.yml` is manually dispatched. It prepares
  static assets, runs tests, builds distributions, validates them with Twine,
  and publishes to TestPyPI using a repository secret.
- `.github/workflows/publish-pypi.yml` builds and tests the source distribution
  and wheels for CPython 3.10–3.14 on Linux x86-64/ARM64, Windows x64, and
  universal2 macOS. It validates packaged assets and smoke-tests each wheel;
  publishing is a separate, explicitly enabled workflow step.

CI describes configured coverage, not certification or a guarantee that every
optional toolchain is installed on every contributor machine.

### Build and distribution

The build backend is `scikit-build-core`; build requirements include pybind11.
`CMakeLists.txt` builds `_spacelang_cpp` from `csrc/binding.cpp` and
`csrc/vm.cpp`, requests C++17, and installs the extension into `spacelang`.
`pyproject.toml` configures wheel package selection, release metadata, CLI
entry points, and optional dependency groups. `MANIFEST.in` includes OPT_SP
static files in source distributions.

To build a local source and wheel distribution (requires the `build` package):

```bash
python -m pip install build
python -m build
```

The wheel built locally targets the current Python and platform. Release wheels
for supported platforms and Python versions are built by
`.github/workflows/publish-pypi.yml`. Building from source requires the native
compiler toolchain described above; installing a matching published wheel does
not.

To inspect package contents, validate that the expected Python modules,
compiled extension, and any prepared static assets are included. Static
debugger assets must be generated before a release build if that distribution
is expected to ship the browser application.

## Known limitations and extension ideas

These are current boundaries and natural areas for future work, not claims that
they are already implemented:

- Expand Python syntax only with matching compiler, VM, and test coverage.
- Improve diagnostics to identify unsupported syntax and parameter errors with
  precise source spans.
- Extend native/reference differential tests whenever VM features change.
- Decide and document whether opcode encoding remains backwards compatible
  when the instruction set grows.
- Expand installed-wheel tests to cover user-facing CLI behavior and execution,
  in addition to the current native-extension and OPT_SP asset smoke checks.
- Document platform/compiler combinations for the C++ extension and benchmark
  reproducibility more fully.
- Keep the language subset and package maturity clearly stated for users.

When adding an instruction, update the IR enum, encoder validation, parser,
assembler/disassembler maps, both VMs, frontend lowering if applicable,
documentation tables, and tests. When adding a Python syntax feature, include
positive tests, unsupported/invalid cases, and differential tests for the
native VM where relevant.

## Glossary

| Term | Meaning in this project |
| --- | --- |
| **AST** | Python abstract syntax tree parsed from source by the standard library. |
| **Instruction sequence** | Stack-machine instructions executed by a VM. |
| **Closure** | Function value that retains references to captured local cells. |
| **IR** | Internal compiler representation: `Program` plus instructions and metadata. |
| **SpaceLang source** | `.sp` source / the language's source representation. |
| **Instruction pointer (`ip`)** | Index of the instruction currently being executed. |
| **Name table** | Mapping between source identifiers and numeric operands. |
| **Operand stack** | Runtime stack holding intermediate values and call operands. |
| **Reference VM** | Python implementation used as the semantic baseline. |
| **`.sp`** | SpaceLang whitespace-token program format. |
| **`.spasm`** | Human-readable mnemonic assembly source. |
| **`.spz`** | Gzip-compressed `.sp` file. |
| **OPT_SP** | Browser-based SpaceLang instruction visualizer/debugger. |
