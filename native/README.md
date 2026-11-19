# A native runner: `.sp` without Python

SpaceLang is a programming language whose source language is `.sp`. The `.py` form is an optional surface syntax that is lowered to `.sp`.

`.sp` is the SpaceLang source language. `.py` is an optional surface syntax lowered to `.sp`.
Supporting `.py` input does not make SpaceLang Python.

> New here? Read [../SELFHOSTING.md](../SELFHOSTING.md) first: it explains the
> whole pipeline, including the SpaceLang compiler (`compiler.exe`). This file
> documents the native tools themselves.

`native/spvm.cpp` is a self-contained SpaceLang virtual machine — one C++17
file, standard library only. It reads a compiled `.sp` file and executes it
with **no Python at runtime**: no CPython, no pybind11, no DLLs beyond
`KERNEL32`/`msvcrt`.

```bash
powershell -ExecutionPolicy Bypass -File native/build.ps1   # or: sh native/build.sh
native/spvm.exe bootstrap/demos/fib.sp
```

That is the "`xxx.exe xxx.sp`" shape:

```
compiler.sp --compile-py--> compiler.sp   (already the artifact)
spvm.exe    compiler.sp                    (run it)
```

## What you get

| Command | Result |
| --- | --- |
| `spvm.exe PROGRAM.sp [ARG ...]` | Runs any `.sp` the Python frontend can emit; `ARG`s become `__argv__[1:]` |
| `python native/embed.py PROGRAM.sp` | A **single-file** `<name>.exe` containing the VM *and* the program — no `.sp` file needed |
| `compiler.exe PROGRAM.py` | **Compiles Python source with a compiler written in SpaceLang, then runs it** — no Python |

```bash
python native/embed.py bootstrap/demos/fib.sp -o fib.exe
./fib.exe          # 2.6 MB, runs the program directly
```

`embed.py` emits a small C++ file with the `.sp` bytes as an array and compiles
it together with the VM. This is the ahead-of-time path: program and runtime in
one binary, so you can ship it to a machine with no toolchain and no `.sp` file.

## A compiler written in SpaceLang: `compiler.exe`

`native/spc.py` implements a compiler with tokenizer, indentation-aware parser,
code generator, and `.sp` producer. It is written in a bounded `.py` surface
syntax and lowered to `.sp`.
Like the
self-hosted VM, it is compiled into `.sp` and then runs without Python:

```
spc.py --compile-py--> spc.sp --embedded--> compiler.exe
                                              |
                                    program.py --compile--> program.sp --run--> output
```

```bash
powershell -ExecutionPolicy Bypass -File native/build_compiler.ps1
native/compiler.exe native/examples/tour.py      # compiles, then runs
native/compiler.exe native/examples/flow.py out.sp   # compile only
```

`build_compiler.ps1` does the whole bootstrap: it runs the ordinary toolchain
once (`compile-py native/spc.py native/spc.sp`), bakes the resulting `.sp` into
a C++ header, and links it with the native VM. From then on `compiler.exe`
needs neither Python nor any `.sp` file.

### Input language (deliberately small)

| Feature | Example |
| --- | --- |
| Assignment, arithmetic | `x = 2 + 3 * 4`, `//`, `%`, `**` |
| Output and conversions | `print(a, b)`, `len`, `str`, `int`, `float`, `bool`, `abs` |
| Conditions | `if` / `elif` / `else`, `== != < > <= >=`, `and`, `or`, `not` |
| Loops | `while`, `for i in range(n)`, `for i in range(a, b)` |
| Strings | `"text"`, `+`, escapes `\n \t \\`, `#` comments |

Not in the input language (reported as `spc: ...`, exit 1, no output file):
`def`, classes, lists, dicts, tuples, imports, `break`/`continue`, f-strings,
`and`-chain assignment, tabs for indentation.

Because the *input* language is smaller than the language `spc.py` itself is
written in, `compiler.exe` cannot yet compile `spc.py` (no functions in the
input subset). That is the next milestone toward the classic three-stage
bootstrap; the pieces here are the last two stages of it.

## Verified on this checkout

Identical stdout to the Python reference VM (`spacelang run`) for:

- `bootstrap/demos/{hello,fib,collections,closure}.sp`
- `tests/test_quine/quine.sp` (exercises the `*.names.json` sidecar path)

Rough speed on a 20,000-iteration arithmetic loop (same `.sp`, same machine):

| Engine | Time |
| --- | --- |
| `spacelang run` (Python reference VM) | 375 ms |
| `spvm.exe` (this native VM) | 11 ms |

So the machine is ~25–34× faster than the Python VM and starts in ~2 ms
instead of ~90 ms. The `csrc/` pybind11 engine is a different thing: it needs
Python and calls back into it for globals, cells, closures and builtins.

## Supported

- The whole instruction set `pyfront.py` can emit: `PUSH_INT`/`PUSH_STR`,
  globals, locals, cells, closures (all five `MAKE_CLOSURE*` forms with full
  argument binding), `OP` ids 1–17, `STACK`, jumps, `GET_ITER`/`FOR_ITER`,
  `UNPACK_SEQUENCE`, `BUILD_*`, `CONCAT`, `LIST_EXTEND`, `DICT_MERGE`/`UPDATE`,
  `BUILD_SLICE`, `CALL*` (positional, keyword, expanded), `DEF`/`RET`/`HALT`.
- Builtins: `print` (with `sep`/`end`), `input`, `len`, `int`, `float`, `str`,
  `bool`, `abs`, `range`, `type`, `callable`, `repr`, `set`.
- Methods: `str` (`upper`, `lower`, `strip`, `split`, `join`, `replace`,
  `startswith`, `endswith`, `format`), `list` (`append`, `extend`, `pop`,
  `reverse`, `index`, `insert`), `dict` (`keys`, `values`, `items`, `get`,
  `update`), `set` (`add`).
- Python-compatible printing of containers (`{'a': 1}`, `[(1, 2)]`, `(1,)`,
  `set()`), floor division/modulo sign rules, negative indexing, `in`,
  identity vs equality.

## Not supported (fails with a clear message)

- `TRY`/`END_TRY`/`RAISE`/`SETUP_WITH` — the Python frontend cannot emit them.
- `IMPORT`, `GET_ATTR`, `STORE_ATTR` — no module system or attribute access, so
  `math.sqrt`, `os.path`, `re` and friends are unavailable. Use the Python or
  pybind11 engines for those.
- `type(x)` returns a type *name* string (there are no type objects), and
  `open()`/`getattr`/`setattr`/`isinstance` are absent.
- Strings are UTF-8 and indexing/slicing yields code points, but `len()` counts
  bytes; `%`-style formatting is absent.
- Dictionaries use insertion-ordered linear lookup (fine for program-sized
  dicts, not for large tables).

## Executing `.sp` in native form

The VM executes `.sp` source artifacts. `embed.py` creates a single executable
by linking the native VM and program artifact together. Direct machine-code
translation is a separate implementation choice.

## Layout

| File | Purpose |
| --- | --- |
| `spvm.cpp` | The VM: decoder, value model, executor, builtins, methods, file I/O |
| `spvm.exe` | Built artifact (2.7 MB, static) |
| `spc.py` | The compiler, written in the SpaceLang subset |
| `spc.sp` | Compiled `.sp` artifact for the compiler (build output, gitignored) |
| `compiler.cpp` | `compiler.exe` entry point: embedded `spc.sp` + VM |
| `build.ps1`, `build.sh` | Build the runner |
| `build_compiler.ps1` | Build `compiler.exe` (stage 0 + blob + link) |
| `embed.py` | Program + VM → single-file executable |
| `make_blob.py` | `.sp` bytes → C++ header |
| `examples/` | `tour.py`, `flow.py` — sample inputs for `compiler.exe` |
