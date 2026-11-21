# Self-hosting SpaceLang — the complete guide

SpaceLang is a programming language whose source language is `.sp`. The `.py` form is an optional surface syntax that is lowered to `.sp`.

`.sp` is the SpaceLang source language. `.py` is an optional surface syntax lowered to `.sp`.
Supporting `.py` input does not make SpaceLang Python.

This document explains the three things added on top of the original project, how
they work, and exactly how to run them. It is written to be read top to bottom;
afterwards you should be able to explain the whole pipeline to someone else.

If you only want the commands, jump to [§5 Quick start](#5-quick-start).

---

## Contents

1. [The mental model](#1-the-mental-model)
2. [How the pieces fit](#2-how-the-pieces-fit)
3. [Concepts you need](#3-concepts-you-need)
4. [Requirements](#4-requirements)
5. [Quick start](#5-quick-start)
6. [Part 1 — `.sp` running `.sp`](#6-part-1--sp-running-sp-bootstrap)
7. [Part 2 — `.sp` without Python](#7-part-2--sp-without-python-native)
8. [Part 3 — Compiling Python without Python](#8-part-3--compiling-python-without-python-compilerexe)
9. [How it works inside](#9-how-it-works-inside)
10. [Performance](#10-performance)
11. [Troubleshooting](#11-troubleshooting)
12. [Limitations and roadmap](#12-limitations-and-roadmap)
13. [File map](#13-file-map)
14. [Tests](#14-tests)
15. [Merging into your repository](#15-merging-into-your-repository)

---

## 1. The mental model

The project has **one language** and now **three programs written in it**.

| Name | What it is | Written in | Runs on |
| --- | --- | --- | --- |
| `spacelang` (the CLI) | The original toolchain: compiler, assembler, disassembler, Python VM | Python | CPython |
| `sp_vm.sp` | An execution engine for `.sp` source | `.py` implementation lowered to `.sp` (`sp_vm.py`) | CPython or another `.sp` runtime |
| `spc.sp` | A compiler artifact that reads source according to its frontend | `.py` implementation lowered to `.sp` (`spc.py`) | CPython or `spvm.exe` |

Three consequences, in increasing order of impressiveness:

1. **`sp` runs `sp`** — `sp_vm.sp` is a SpaceLang program that executes other
   SpaceLang programs.
2. **`sp` runs `sp` runs `sp`** — feed `sp_vm.sp` to itself and it executes a
   compiled copy of itself. This is the self-hosting demonstration.
3. **A compiler written in `.sp` lowers optional `.py` frontend input** — `compiler.exe`
   can contain an `.sp` compiler implementation and, where applicable, accept `.py`,
   lower it to `.sp`, and run or emit the result with no Python installed.
4. **The compiler compiles itself to a fixed point** — `compiler.exe` compiles
   `native/spc.py`, a second compiler is built from that artifact, and the two
   self-produced `.sp` files are byte-identical (`stage2 == stage3`).

Important distinction:

* **Runtime self-hosting** = an execution engine is written in `.sp` and executes `.sp`.
* **Compiler self-hosting** = a compiler written in `.sp` reads `.sp` source and produces
  `.sp` or executable artifacts. Status: **verified** — `compiler.exe` compiles its own
  `native/spc.py` source and reaches a byte-identical fixed point (`stage2 == stage3`,
  see [§8.5](#85-the-fixed-point)).

Everything else — the original compiler, VM, tests, CLI — is untouched except
for six lines in `spacelang/main.py` (see [§15](#15-merging-into-your-repository)).

---

## 2. How the pieces fit

```
                        ┌───────────────────────────────────────────────┐
                        │  Stage 0: the original Python toolchain       │
                        │  spacelang/pyfront.py  →  Program (IR)        │
                        │  spacelang/encoder.py  →  .sp whitespace      │
                        └───────────────┬───────────────────────────────┘
                                        │ compile-py
        ┌───────────────────────────────┼────────────────────────────────┐
        ▼                               ▼                                ▼
  bootstrap/sp_vm.sp            bootstrap/demos/*.sp            native/spc.sp
  (interpreter, 2.8 MB)         (test programs)                 (compiler, 2.9 MB)
        │                               │                                │
        │ run                           │ run                            │ embedded in
        ▼                               ▼                                ▼
  CPython VM ──► output          native/spvm.exe ──► output      native/compiler.exe
        │                                                              │
        │ or: spacelang run sp_vm.sp  sp_vm.sp  demo.sp                 │ reads program.py
        ▼                                                              ▼
  depth-2 self-hosting chain                                   program.sp ──► runs
```

Three runtimes execute `.sp` artifacts. They must agree; the test suite checks it:

| Runtime | Language | Needs Python? | Needs a compiler? |
| --- | --- | --- | --- |
| `spacelang.vm_py.VM` | Python | yes | no |
| `native/spvm.exe` | C++ (`spvm.cpp`) | **no** | yes, once |
| `bootstrap/sp_vm.sp` | SpaceLang | no (but is itself hosted by one of the above) | no |

`csrc/` (the pybind11 engine) is a fourth one, but it is a Python extension and
calls back into CPython, so it does not count as Python-free.

---

## 3. Concepts you need

### 3.1 The `.sp` instruction model

SpaceLang source is compiled to a flat list of instructions over a value stack.
Each instruction is `op, arg, arg…`, e.g. `PUSH_INT 2`, `OP 3` (multiply),
`CALL 0 1` (call builtin 0 = `print` with one argument), `HALT`.

The full table lives in `spacelang/ir.py`; 53 opcodes exist. The subset that
`pyfront.py` can emit is what everything here supports.

### 3.2 The `.sp` format

A `.sp` file is **not** text in any readable sense. Each integer token is written
as that many **spaces** followed by a newline:

```
PUSH_INT 2      →  tokens 7, 4      →  "       \n    \n"       (7 spaces, 4 spaces)
```

* `PUSH_INT` values are **zig-zag** encoded (`2v` for `v ≥ 0`, `−2v−1` otherwise),
  so `2 → 4`, `−1 → 1`.
* `PUSH_STR` is a length followed by the character codes.
* The name table is appended after `HALT` as opcode `53`, a length, and the JSON
  payload `{"name":0,…}` as character codes.
* `MAX_LINE = 65535` per token, which is why integer literals above **32767**
  cannot be encoded directly (`spacelang/encoder.py:130`).

### 3.3 Stage-0 bootstrapping

A compiler written in language L must itself be compiled by *something*. The
standard scheme:

```
stage 0:  the Python toolchain compiles spc.py  →  spc1.sp      (needs Python, once)
stage 1:  compiler1.exe (built from spc1.sp) compiles spc.py  →  spc2.sp   (no Python)
stage 2:  compiler2.exe (built from spc2.sp) compiles spc.py  →  spc3.sp   (no Python)
fixed point:  bytes(spc2.sp) == bytes(spc3.sp)
```

Stage 0 is what `native/build_compiler.ps1` automates; it also links
`compiler1.exe`. `tools/bootstrap_check.py` runs the whole chain, builds
`compiler2.exe` from `spc2.sp`, and asserts the fixed point.

The stage-1 and stage-2 compilers are not required to be byte-identical to the
stage-0 artifact — only to each other. A compiler compiled by itself must
reproduce itself, i.e. it has to be deterministic: function ids are assigned in
source order, the name table is numbered by first use, and no timestamp, path
or hash order may reach the output.

### 3.4 `__argv__`

The CLI now forwards trailing arguments to `run` and exposes them as a global
list, alongside the existing `__file__`:

```bash
python -m spacelang.main run program.sp one two
# __argv__ == ["program.sp", "one", "two"]
```

`sp_vm.sp` reads its target from `__argv__[1]` and hands the target
`[target, *rest]`. That is what makes nesting work: each level consumes one
path and forwards the remainder.

---

## 4. Requirements

| Part | Needs |
| --- | --- |
| Part 1 (self-hosted VM) | Python 3.10+ only |
| Part 2/3 (native runner, compiler) | A C++17 compiler (`g++` recommended), plus Python once for stage 0 |

On this machine: `py` (Python 3.13) and `g++` 8.1.0 (MinGW-w64) are available;
`python` on `PATH` is the Microsoft Store stub and does **not** work — use `py`.

---

## 5. Quick start

Open a shell at the repository root:

```powershell
cd <your-spacelang-checkout>
$env:PYTHONPATH = $PWD        # make this checkout win over any installed copy
```

Then, in order:

```powershell
# 1. Part 1 — build the SpaceLang interpreter, verify it, run it under itself
py bootstrap/bootstrap.py all

# 2. Part 2 — build the Python-free runner and run a program with it
powershell -ExecutionPolicy Bypass -File native/build.ps1
native\spvm.exe bootstrap\demos\fib.sp

# 3. Part 3 — build the SpaceLang compiler and compile/run Python source
powershell -ExecutionPolicy Bypass -File native/build_compiler.ps1
native\compiler.exe native\examples\tour.py

# 4. The fixed point — compile the compiler with itself, twice (needs g++, ~30 s)
py -S tools/bootstrap_check.py
```

Expected output, step by step:

```text
# 1
[build] compiler -> SpaceLang artifacts
  sp_vm.py -> sp_vm.sp (2,835,762 bytes)
  ...
[check] reference VM vs self-hosted VM (identical output expected)
  PASS closure.sp (5 output lines)
  PASS collections.sp (10 output lines)
  PASS fib.sp (11 output lines)
  PASS hello.sp (2 output lines)
[selfhost] depth 2: sp_vm.sp -> sp_vm.sp -> hello.sp
  OK   2.06s, 2 output lines, identical to the reference VM

# 2
fib(0) = 0
fib(1) = 1
...

# 3
14
Hello, SpaceLang
0
1
2
3
4
big
15
4 7 42
and ok
not ok
3 1 1024

# 4
[stage0] python toolchain -> build/spc1.sp
  build\spc1.sp: 5,313,084 bytes sha256 8d46...
[stage1] compiler1.exe native/spc.py -> build/spc2.sp
  build\spc2.sp: 5,059,599 bytes sha256 9a6a...
[stage2] compiler2.exe native/spc.py -> build/spc3.sp
  build\spc3.sp: 5,059,599 bytes sha256 9a6a...
[fixed-point]
  OK: spc2.sp == spc3.sp (5,059,599 bytes)
...
[result] PASS
```

Total time for steps 1–3: about 15 seconds, of which 4.7 s is step 1. Step 4
rebuilds two native compilers and takes about 30 s.

---

## 6. Part 1 — `.sp` running `.sp` (`bootstrap/`)

### 6.1 What is in the directory

| File | Meaning |
| --- | --- |
| `sp_vm.py` | **Source of truth**: the interpreter, 1,335 lines of Python-subset code |
| `sp_vm.sp` | The compiled interpreter: 2,835,762 bytes of spaces |
| `demos/*.py`, `demos/*.sp` | Four test programs (source and compiled) |
| `bootstrap.py` | Driver: `build` / `check` / `run` / `selfhost` / `all` |
| `README.md` | Short version of this section |

### 6.2 Build, verify, run

```powershell
py bootstrap/bootstrap.py build      # compile sp_vm.py and the demos (~0.6 s)
py bootstrap/bootstrap.py check      # compare Python VM vs .sp VM on 4 programs
py bootstrap/bootstrap.py run bootstrap\demos\collections.sp
py bootstrap/bootstrap.py selfhost   # the self-hosting chain
```

`check` is the important one: it runs each demo twice — once on the original
Python VM, once on the SpaceLang VM — and requires byte-identical stdout.

### 6.3 The self-hosting chain

Every `sp_vm.sp` on the command line adds one interpreter level:

```powershell
# depth 1 (~0.2 s): the .sp VM runs a .sp program
py -m spacelang.main run bootstrap/sp_vm.sp bootstrap/demos/fib.sp

# depth 2 (~2 s): the .sp VM runs a compiled copy of itself, which runs the program
py -m spacelang.main run bootstrap/sp_vm.sp bootstrap/sp_vm.sp bootstrap/demos/hello.sp
```

Read the second command right to left:

* `hello.sp` is the payload;
* the right-hand `sp_vm.sp` interprets it;
* the left-hand `sp_vm.sp` interprets *that interpreter*.

That is the self-hosting claim in one line. Depth 2 is the practical limit: an
extra level multiplies the work by ~100 (see [§10](#10-performance)).

### 6.4 Your own program

```powershell
py -m spacelang.main compile-py my.py my.sp
py -m spacelang.main run bootstrap/sp_vm.sp my.sp
```

The source must be in the supported `.py` frontend surface (`documentation.md` §Python
subset reference). Closures, comprehensions, dicts, slicing, `*args`/`**kwargs`
all work.

### 6.5 What is inside the interpreter

`sp_vm.py` is a port of `spacelang/vm_py.py` minus the parts the Python frontend
cannot express (classes, exceptions, generators):

* **Loader** — `tokenize` (spaces → integers), `decode` (opcode shapes, zig-zag,
  `PUSH_STR` payloads, name-table JSON or a `.names.json` sidecar),
  `build_funcs` (the same `DEF`-range rule as `spacelang/parser.py`).
* **Executor** — operand stack, frames (locals, initialization flags, return ip,
  closure cells), closures with positional/keyword/default/`*args`/`**kwargs`
  binding, iteration, slices.
* **Tricks forced by the subset** — no classes, so cells/closures/slices are
  list records whose first slot is a unique marker object compared with `is`;
  no `iter`/`next`, so `GET_ITER` materializes sequences through
  `__iter__`/`__next__`; no `chr`, so characters are built with
  `to_bytes().decode()`.

---

## 7. Part 2 — `.sp` without Python (`native/`)

`native/spvm.cpp` is a **single-file C++17 VM** with no dependency except the
C/C++ runtime. It reads a `.sp` file and executes it.

### 7.1 Build

```powershell
powershell -ExecutionPolicy Bypass -File native\build.ps1
# or, on a POSIX shell:  sh native/build.sh
# or by hand:            g++ -O2 -std=c++17 -static -o native/spvm.exe native/spvm.cpp
```

Result: `native\spvm.exe`, 2.7 MB, static. Its only imports are `KERNEL32.dll`
and `msvcrt.dll` — no Python, no MinGW runtime DLLs. The binary is gitignored;
rebuild takes ~5 s.

### 7.2 Run

```powershell
native\spvm.exe bootstrap\demos\fib.sp
native\spvm.exe tests\test_quine\quine.sp
native\spvm.exe program.sp arg1 arg2      # args appear as __argv__[1:]
```

### 7.3 Single-file executable

```powershell
py native\embed.py bootstrap\demos\fib.sp -o fib.exe
fib.exe
```

`embed.py` writes a small C++ file containing the `.sp` bytes and compiles it
together with the VM: program and runtime in one binary, no `.sp` file next to
it. This is the ahead-of-time path.

### 7.4 What it supports

Everything `pyfront.py` can emit (ints, strings, containers, closures, slices,
expanded calls), plus `open()` file objects with `read`/`readline`/`write`/
`close`. Builtins: `print` (with `sep`/`end`), `input`, `len`, `int`, `float`,
`str`, `bool`, `abs`, `range`, `type`, `callable`, `repr`, `set`, `open`.
Methods: the common `str`/`list`/`dict`/`set`/file ones.

**Not** supported: `IMPORT`, `GET_ATTR`/`STORE_ATTR` (no modules or attribute
access), the exception opcodes. That is why `spvm.exe` cannot run `sp_vm.sp`
itself — `sp_vm.sp` imports `os` and uses `getattr` (see
[§12](#12-limitations-and-roadmap)).

---

## 8. Part 3 — Compiling Python without Python (`compiler.exe`)

### 8.1 Build

```powershell
powershell -ExecutionPolicy Bypass -File native\build_compiler.ps1
```

That script performs the stage-0 bootstrap and then links:

```text
1. py -S -m spacelang.main compile-py native/spc.py native/spc.sp   (stage 0)
2. py -S native/make_blob.py native/spc.sp native/spc_blob.h         (bytes → header)
3. g++ -O2 -std=c++17 -static -o native/compiler.exe native/compiler.cpp
```

`compiler.exe` is about 8.0 MB (5.3 MB of that is the embedded compiler `.sp`
artifact). `spc.sp` and `spc_blob.h` are build outputs and gitignored; step 0
replaces Python entirely after this point.

### 8.2 Use

```powershell
native\compiler.exe native\examples\tour.py            # compile, then run
native\compiler.exe native\examples\flow.py out.sp     # compile only
```

With one argument `.sp` source is written next to the source
(`tour.py` → `tour.sp`) and then executed. With two arguments it only compiles.

### 8.3 The input language

| Construct | Syntax |
| --- | --- |
| functions | `def add(a, b): return a + b`, `return`, `global name` |
| assignment | `x = expr`, `m[i][j] = expr` |
| arithmetic | `+ - * / // % **`, unary `-` |
| comparison | `== != < > <= >=`, `in`, `not in`, `is`, `is not` |
| logic | `and or not` |
| output/conversion | `print(a, b)`, `len`, `str`, `int`, `float`, `bool`, `abs`, `open` |
| branching | `if` / `elif` / `else` with indentation |
| loops | `while`, `for x in ITERABLE`, `break`, `continue`; iterables are lists, dicts, strings and `range(...)` |
| data | `[1, 2]`, `{"a": 1}`, `a[i]`, `s[1:3]`, `xs.append(v)`, `d.get(k)` |
| literals | integers (±32767), `"strings"` with `\n \t \r \\`, `None`, `True`, `False` |
| comments | `# …` |

Rejected with `spc: …` on stdout, exit code 1, and **no output file**:

* classes, imports, lambdas
* tuples, sets, comprehensions
* f-strings, `%` formatting
* augmented assignment (`+=`), keyword arguments
* tabs for indentation, multiple statements per line

### 8.4 What happens inside

```
program.py
   │  spc.py: tokenize_line → prepare (indentation + line continuations) → parse_*
   ▼
AST (dicts: {"k": "bin", "op": "+", "l": …, "r": …})
   │  collect_functions / function_scope: ids, slots, global names
   │  gen_expr / gen_stmt: emit [op, args…] into INSTR, patch labels
   ▼
instruction list + name table
   │  encode(): token(v) = " " * v + "\n"; zig-zag PUSH_INT; JSON name table
   ▼
program.sp  ──► spvm_exe's embedded VM ──► output
```

The compiler is about 1,200 lines and uses the same subset it accepts (no
classes, no exceptions), which is why it can compile itself.

### 8.5 The fixed point

The compiler now accepts the language it is written in, so it compiles itself:

| Stage | Command | Needs Python? |
| --- | --- | --- |
| 0 | `py -S -m spacelang.main compile-py native/spc.py build/spc1.sp` | yes, once |
| 1 | `build/compiler1.exe native/spc.py build/spc2.sp` | no |
| 2 | `build/compiler2.exe native/spc.py build/spc3.sp` | no |

`compiler1.exe` embeds `spc1.sp`; `compiler2.exe` embeds `spc2.sp`. The fixed
point is `sha256(spc2.sp) == sha256(spc3.sp)`.

Reproduce the whole chain (and its determinism checks) with:

```powershell
py -S tools/bootstrap_check.py
```

Current status on this checkout:

| Artifact | Size | sha256 |
| --- | ---: | --- |
| `build/spc1.sp` (stage 0, Python toolchain) | 5,313,084 | `8d46406a…656b6e` |
| `build/spc2.sp` (compiled by `compiler1.exe`) | 5,059,599 | `9a6a23dc…722dafa` |
| `build/spc3.sp` (compiled by `compiler2.exe`) | 5,059,599 | `9a6a23dc…722dafa` |

* fixed point: **yes** — `spc2.sp` and `spc3.sp` are byte-identical;
* determinism: four stage-0 runs (two with `PYTHONHASHSEED=0`, two unset) are
  byte-identical, and re-running stage 1 and stage 2 reproduces `spc2.sp`
  and `spc3.sp` exactly;
* behavior: `compiler2.exe` compiles and runs `native/examples/tour.py` and
  `flow.py` with the same stdout as CPython, and a self-compiled `spc2.sp`
  compiles `def add(a, b): return a + b` + `print(add(2, 3))` to a program that
  prints `5`.

Why the fixed point is reachable:

* `native/spc.py` is written in the subset it accepts: tokenizer, continuation
  aware `prepare`, recursive-descent parser, static scope analysis, code
  generator and encoder. `tools/bootstrap_audit.py` reports that the "missing
  constructs" table is empty.
* Function ids are allocated in source order starting at 10000, the name table
  is numbered on first use in emission order, and every container iteration in
  the compiler follows insertion order. No timestamp, path, random value or
  hash order reaches the output.
* The compiler does not have to reproduce the stage-0 (Python) lowering: the
  stage-1 and stage-2 compilers both use `spc.py`'s own lowering, so once each
  of them compiles the source correctly the two artifacts coincide.

Caveats:

* `.sp` encodes integers unary, so the self-compiled compiler is about 5 MB and
  a self-compile takes about 0.8 s in `compiler.exe`; the artifact size is not
  a bug (see [§10](#10-performance)).
* `tests/test_bootstrap.py` guards both milestones (self-hosting and the fixed
  point). `tools/bootstrap_audit.py` is the regression detector for "did the
  source grow syntax the compiler does not accept?" — keep its missing table
  empty.

---

## 9. How it works inside

### 9.1 A worked example

Source:

```python
def double(value):
    return value * 2

total = double(21)
print(f"answer = {total}")
```

`spacelang disasm` of the compiled result:

```text
.name total=1
DEF 10000 1              ; def double(value)
LOAD_LOCAL 0             ;   value
PUSH_INT 2               ;   2
OP 3                     ;   *
RET
PUSH_INT 21              ; double(21)
STORE_GLOBAL __spacelang_temp_0
LOAD_GLOBAL __spacelang_temp_0
CALL 10000 1
STORE_GLOBAL total
PUSH_STR "answer = "     ; f-string → str() + concat
LOAD_GLOBAL total
CALL 5 1                 ; str(
CONCAT 2
CALL 0 1                 ; print(
STACK 3                  ; drop the return value
HALT
```

Encoded, that is the token list `17, 10000, 1, 20, 0, 7, 4, 5, 3, 18, …`, where
`10000` alone occupies 10,000 bytes. This 4-line program is 24 KB of `.sp` —
the format's honest cost, see [§10](#10-performance).

### 9.2 Loading a `.sp`

All three runtimes do the same four steps:

1. read bytes; reject anything that is not a space, newline or CRLF;
2. count spaces per line → integer tokens;
3. decode by opcode shape: fixed arity table, `PUSH_INT` zig-zag, `PUSH_STR`
   length + payload, opcode 53 → name table;
4. compute function ranges from `DEF` positions (next `DEF` bounds a body; the
   end is the last `RET`+1).

### 9.3 Executing

A stack machine with:

* **operand stack** — plain values;
* **frames** — locals, initialized flags, return ip, closure cells;
* **cells** — heap boxes for variables captured by nested functions
  (`CELLIFY` boxes a slot, `LOAD_DEREF` pushes the box, `LOAD_LOCAL` unboxes);
* **closures** — function id + captured cells + parameter names + defaults;
* **iterators** — Python's `PyObject_GetIter` in C++, materialized lists in
  SpaceLang.

Function ids start at 10000 by construction (`parser.py:236`), which is how a
`CALL` distinguishes a user function from a builtin.

### 9.4 The three runtimes must agree

The Python VM is the reference. `bootstrap/bootstrap.py check` and
`tests/test_selfhost.py` prove the `.sp` VM agrees; `tests/test_native.py` proves
the C++ VM agrees on the same programs plus the repo's quine.

---

## 10. Performance

Measured on this machine (Windows 11, CPython 3.13, MinGW g++ 8.1):

| Workload | Engine | Time |
| --- | --- | --- |
| `hello.sp` | Python VM | 0.09 s |
| `hello.sp` | `sp_vm.sp` (depth 1) | 0.20 s |
| `hello.sp` | `sp_vm.sp` under `sp_vm.sp` (depth 2) | 2.0 s |
| `fib.sp` (10 terms, recursion) | `sp_vm.sp` (depth 1) | 0.49 s |
| `fib.sp` | depth 2 | 38 s |
| 20,000-iteration arithmetic loop | Python VM | 375 ms |
| same | `spvm.exe` | 11 ms |
| `_t1.py` compile+run | `compiler.exe` | ~0.39 s |
| `native/spc.py` self-compile (5.06 MB artifact) | `compiler.exe` | ~0.8 s |
| same | `compiler2.exe` | ~0.75 s |

Why:

* The Python VM is a Python implementation of the stack machine, so dispatch work has host-language overhead.
* `spvm.cpp` keeps ints/floats unboxed and uses a `switch` dispatcher, so a step
  is a few dozen native instructions — hence ~25–34× faster.
* `sp_vm.sp` is an execution engine written in `.sp`, interpreted by another
  interpreter: each level costs ~100×.

The 2.8 MB artifact size is not a bug: every user-function call site encodes a
5-digit function id as that many spaces. The same effect makes the self-compiled
compiler ~5 MB, and because `.sp` tokenizes by counting spaces, a self-compile
spends most of its time appending unary-encoded function ids.

---

## 11. Troubleshooting

| Symptom | Cause | Fix |
| --- | --- | --- |
| `Python was not found` | Windows Store alias stub | use `py` instead of `python` |
| `import spacelang` resolves to another directory | a stale editable install of a different clone shadows the checkout | run subprocesses with `-S` and `PYTHONPATH=<repo root>` (the driver already does); or `pip uninstall` the stale editable install |
| `EncodingError: token exceeds MAX_LINE (65535)` | integer literal > 32767, **including values produced by constant folding** (`256*256`) | compile with `--compress-source`, or compute the value at run time (`int("65535")`) |
| `spvm: unsupported opcode 4` | the native runner met `IMPORT` — e.g. you gave it `sp_vm.sp` | run `sp_vm.sp` on the Python VM instead, or extend `spvm.cpp` |
| `spc: unknown function: foo` | `compiler.exe` resolves calls to builtins and to module-level `def`s in the same file; nested functions and callable values are unsupported | define the function at module level in the same source file |
| fixed point fails: `spc2.sp != spc3.sp` | the name table or function ids became non-deterministic (hash order, dict iteration, temp naming) | keep ids/names in traversal order; run `py -S tools/bootstrap_check.py` to see the first 20 differing lines |
| `spc: expected an indented block` | body not indented, or tabs used | indent with 4 spaces |
| `compiler: … was not written` | the frontend rejected the source; the real message is the `spc:` line above it | fix the source |
| depth-3 chain never finishes | ~100× per interpreter level | stay at depth 2 |
| `native\spvm.exe` not found | binaries are gitignored | run `native\build.ps1` |
| `g++` is not recognized | compiler not on `PATH` | add its `bin` directory to `PATH`, or set `$env:CXX="C:\path\to\g++.exe"` |
| pytest cannot create temp dirs | Windows ACLs on the temp root | `pytest --basetemp=<fresh dir under the repo>` |

---

## 12. Limitations and roadmap

### What works today

Repository evidence for runtime, native and compiler behavior is listed in the
test and native sections. The three-stage bootstrap below is verified by
`tools/bootstrap_check.py` and `tests/test_bootstrap.py`.

- [x] `.sp → .sp` compiler fixed point
  - Input language: `.py` subset accepted by `native/spc.py` itself
  - Produced artifact: `build/spc2.sp` / `build/spc3.sp` (byte-identical)
  - Status: done — self-hosting verified and fixed point reached
  - Evidence/command: `py -S tools/bootstrap_check.py`; `py -m pytest tests/test_bootstrap.py -q`

### Optional `.py` frontend roadmap

- [x] Complete optional `def`, list, and dict frontend syntax where needed.
  - Input language: `.py`
  - Produced artifact: lowered `.sp`
  - Status: done — `native/spc.py` accepts every construct it is written in
  - Evidence/command: `py -S tools/bootstrap_audit.py` (section 2, missing
    constructs, is empty)

This was optional sugar completeness work, but it is also what unblocked the
`.sp → .sp` self-hosting path: without `def`, lists, dicts, subscripts and
method calls the compiler cannot read its own source.
