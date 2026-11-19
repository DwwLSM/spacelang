# Bootstrapping SpaceLang (self-hosting)

SpaceLang is a programming language whose source language is `.sp`. The `.py` form is an optional surface syntax that is lowered to `.sp`.

`.sp` is the SpaceLang source language. `.py` is an optional surface syntax lowered to `.sp`.
Supporting `.py` input does not make SpaceLang Python.

> For the whole picture — the self-hosted VM, the Python-free runner, and the
> SpaceLang compiler — read [../SELFHOSTING.md](../SELFHOSTING.md). This file is
> the short version.

**Goal:** use SpaceLang (`sp`) to run SpaceLang (`sp`).

`bootstrap/sp_vm.py` is an implementation of the SpaceLang VM written in a bounded
`.py` surface syntax and lowered to `.sp`.
The ordinary toolchain compiles it once to
`bootstrap/sp_vm.sp`, and from then on that single `.sp` artifact can load and
execute other `.sp` programs — **including a compiled copy of itself**. The VM
does not call back into Python for decoding or dispatch; the only host services
it uses are the builtins the language already exposes (`open`, `print`, `len`,
…), exactly like any other SpaceLang program.

```
Python toolchain                SpaceLang artifacts
----------------                -------------------
bootstrap/sp_vm.py   --compile-py-->  bootstrap/sp_vm.sp
                                          |
                          run  ......  run  ......  run
                                          v
                                   any target.sp
```

## Quick start

From the repository root (Python 3.10+):

```bash
# 1. Build the artifacts: the self-hosted VM and the demo programs.
python bootstrap/bootstrap.py build

# 2. Compare the reference VM with the self-hosted VM on every demo.
python bootstrap/bootstrap.py check

# 3. Run a .sp program with the SpaceLang VM instead of the Python VM.
python bootstrap/bootstrap.py run bootstrap/demos/fib.sp
```

`bootstrap.py` is only a convenience wrapper; the raw commands are:

```bash
python -m spacelang.main compile-py bootstrap/sp_vm.py bootstrap/sp_vm.sp
python -m spacelang.main run bootstrap/sp_vm.sp bootstrap/demos/hello.sp
```

## The self-hosting chain

Every `sp_vm.sp` in the command line is one more interpreter level: the
leftmost runs under the Python reference VM, and each one runs the next.

```bash
# depth 1 — the .sp VM runs a .sp program
python -m spacelang.main run bootstrap/sp_vm.sp bootstrap/demos/fib.sp

# depth 2 — the .sp VM runs a compiled copy of itself, which runs the program
python -m spacelang.main run bootstrap/sp_vm.sp bootstrap/sp_vm.sp bootstrap/demos/hello.sp
```

`bootstrap.py selfhost` wraps the same idea:

```bash
python bootstrap/bootstrap.py selfhost --depth 2 --program bootstrap/demos/hello.sp
```

Measured on one Windows 11 machine (CPython 3.13, warm disk):

| Run | Time |
| --- | --- |
| `run demos/hello.sp` (Python VM, baseline) | 0.09 s |
| `run sp_vm.sp demos/hello.sp` (depth 1) | 0.20 s |
| `run sp_vm.sp sp_vm.sp demos/hello.sp` (depth 2) | 2.0 s |
| `run sp_vm.sp demos/fib.sp` (depth 1) | 0.49 s |
| `run sp_vm.sp sp_vm.sp demos/fib.sp` (depth 2) | 38 s |

Depth 2 is the demonstrated limit: an additional level multiplies the work by
roughly the per-instruction cost of an interpreted interpreter (about two
orders of magnitude here), so depth 3 did not finish in a useful time. This is
the normal shape of a naive bootstrap; it is a correctness landmark, not a
performance one.

## What is inside the VM

`sp_vm.py` mirrors `spacelang/vm_py.py` without the parts the Python frontend
cannot express (classes, exceptions, generators):

* **Loading** — `read_text` → `tokenize` (space runs become integer tokens) →
  `decode` (opcode shapes from `ARITY`, zig-zag `PUSH_INT`, `PUSH_STR` payloads,
  opcode 53 name-table JSON, or the `*.names.json` sidecar the CLI loader also
  accepts) → `build_funcs` (same DEF-range rule as `spacelang/parser.py`).
* **Execution** — an operand stack, a frame stack (locals, initialization
  flags, return ip, closure cells), and closures that bind positional,
  keyword-only, positional-only, `*args` and `**kwargs` parameters.
* **Records without classes** — cells, closures and slices are list records
  whose first slot holds a unique marker object; identity comparison keeps
  them unambiguous.
* **Iteration without `iter`/`next`** — `GET_ITER` materializes dict/set/view
  iterables through the host `__iter__`/`__next__` protocol, bounded by
  `len()`, so no `StopIteration` can escape.
* **Builtins** — `print`, `input`, `len`, `int`, `float`, `str`, `bool`, `abs`,
  `range`, `type`, `open`, `getattr`, `setattr`, `callable`, `repr`,
  `isinstance`, `set`, plus the fixed modules `math`, `random`, `os`, `re`,
  `sys`.

### Instruction coverage

| Opcodes | Status |
| --- | --- |
| `NOP`, `CALL`, `CALL_KW`, `CALL_OBJ`, `CALL_OBJ_KW`, `CALL_OBJ_EX`, `CALL_BUILTIN_EX`, `CALL_METHOD`, `IMPORT`, `OP`, `STACK`, `PUSH_INT`, `PUSH_STR`, `PUSH_NONE`, `LOAD_GLOBAL`, `STORE_GLOBAL`, `LOAD_ARG`, `LOAD_LOCAL`, `STORE_LOCAL`, `LOAD_CELL_REF`, `LOAD_DEREF`, `CELLIFY`, `GET_ATTR`, `STORE_ATTR`, `INDEX`, `STORE_INDEX`, `BUILD_LIST`, `BUILD_TUPLE`, `BUILD_DICT`, `BUILD_SET`, `BUILD_SLICE`, `CONCAT`, `UNPACK_SEQUENCE`, `DEF`, `RET`, `JMP`, `JZ`, `JNZ`, `GET_ITER`, `FOR_ITER`, `HALT`, `MAKE_CLOSURE`, `MAKE_CLOSURE_SIG`, `MAKE_CLOSURE_KWONLY`, `MAKE_CLOSURE_ARGS`, `MAKE_CLOSURE_POSONLY`, `LIST_EXTEND`, `DICT_MERGE`, `DICT_UPDATE` | implemented |
| `TRY`, `END_TRY`, `RAISE`, `SETUP_WITH` | not implemented — the Python frontend cannot emit them |

Everything the frontend *can* emit is therefore executable, which is what makes
the self-application work: `sp_vm.sp` is itself a frontend-generated program.

## The `__argv__` convention

The CLI now forwards trailing arguments to `run` and exposes them to the
program as `__argv__` (`__argv__[0]` is the program path, `__argv__[1:]` the
rest), alongside the existing `__file__` global:

```bash
python -m spacelang.main run program.sp one two
# __argv__ == ["program.sp", "one", "two"]
```

`sp_vm.sp` reads its target from `__argv__[1]` and gives the target a fresh
`__argv__ = [target, *rest]`. That is what lets the chain nest to any depth:
each VM consumes one path and forwards the remainder.

## Layout

| Path | Purpose |
| --- | --- |
| `bootstrap/sp_vm.py` | An optional `.py` frontend implementation of the VM, lowered to `.sp` |
| `bootstrap/sp_vm.sp` | Compiled artifact — the runnable self-hosted VM (~2.7 MB) |
| `bootstrap/demos/*.py` | Demo targets: `hello`, `fib`, `collections`, `closure` |
| `bootstrap/demos/*.sp` | Their compiled programs |
| `bootstrap/bootstrap.py` | `build` / `check` / `run` / `selfhost` / `all` driver |
| `tests/test_selfhost.py` | Pytest coverage: level-1 parity, depth-2 chain, argv plumbing, sidecar names |

Beyond the demo programs, the repository's own quine
(`tests/test_quine/quine.sp`, which keeps its names in `quine.names.json`) also
produces identical output under the self-hosted VM and the reference VM.

Why is `sp_vm.sp` 2.7 MB for 1,315 lines of source? Each user-function call
encodes a function id (`10000`+) as that many spaces, so every call site costs
about 10 KB of encoded source, and the VM has a few hundred call sites. The
format is honest about its own overhead; the artifact still loads in ~0.1 s.

## Limitations

* **VM only, not the compiler.** A full bootstrap would also require the
  Python-subset frontend (`pyfront.py`, 67 KB) to be rewritten in SpaceLang and
  compiled to `.sp`. That is a much larger project; this one proves the runtime
  half.
* **Diagnostics are coarse.** Runtime errors in a target surface as host
  exceptions (`KeyError`, `TypeError`) rather than `SpaceLangError`s with line
  numbers; the VM reports structural problems (unknown opcode, stack shape) on
  stderr.
* **Speed.** Interpretation is ~100× slower than the reference VM, so depth 2
  is the practical chain depth.
* **Slice assignment** is not implemented (slice *reads* are).
* **Small divergences** from the reference VM are documented in code: iterating
  a list while mutating it, `range` slices returning lists, lone surrogates and
  astral characters in string payloads.
* **Optional `.py` frontend completeness.** Expanding the frontend is separate
  from `.sp → .sp` compiler self-hosting.
