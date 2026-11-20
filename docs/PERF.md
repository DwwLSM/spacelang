@ e15e54f835283e3ca32077e9bb062290b91d9186

# Native engine performance baseline

Measured 2026-11-20 on this machine, against the Python reference VM. This file
records one point in time; re-measure and re-pin the commit rather than editing
the numbers in place.

## What was measured

`benchmarks/profile_vm.py` runs seven programs through `spacelang.vm_py.VM` and
`spacelang.vm_cpp.VM`, reports wall time per engine, nanoseconds per *executed
instruction*, and the dynamic opcode mix.

Instruction counts are collected on the reference VM, which exposes a
`_before_step` hook. Both engines execute the same deterministic instruction
stream for these programs, so the same count is used as the denominator for
both. The count is not taken from the native engine because it has no hook.

## Results

Controlled A/B: the shipped extension and the rebuilt extension were swapped
into the same interpreter, three invocations each, each invocation a median of
nine timed runs after two warmup runs. Numbers are the median of those three.

| program | instrs | before (ns/instr) | after (ns/instr) | gain |
| --- | ---: | ---: | ---: | ---: |
| `arithmetic` | 180,007 | 27.1 | 15.9 | 1.70x |
| `calls` | 62,005 | 118.5 | 17.3 | 6.85x |
| `strings` | 21,009 | 53.3 | 32.2 | 1.66x |
| `lists` | 21,010 | 66.9 | 41.5 | 1.61x |
| `modules` | 18,011 | 64.7 | 49.9 | 1.30x |
| `closure` | 32,020 | 174.9 | 57.4 | 3.05x |
| `higher-order` | 30,022 | 159.1 | 78.5 | 2.03x |

The last two programs were added by `59e78db`. The five original programs never
reach `CALL_OBJ` or `MAKE_CLOSURE*`, which is where the second half of the win
is.

### Second pass: call frames and closure fields

`e15e54f` removes the two costs that dominated call-heavy programs afterwards:
two vector allocations per call for the locals, and four to six `Closure`
attribute reads through `PyObject_GetAttrString` per `CALL_OBJ`.

| program | pass 1 (ns/instr) | pass 2 (ns/instr) | gain |
| --- | ---: | ---: | ---: |
| `arithmetic` | 16.2 | 14.7 | 1.10x |
| `calls` | 18.1 | 12.0 | 1.51x |
| `strings` | 37.2 | 33.2 | 1.12x |
| `lists` | 53.8 | 40.4 | 1.33x |
| `modules` | 41.2 | 45.4 | 0.91x |
| `closure` | 57.0 | 28.7 | 1.99x |
| `higher-order` | 75.7 | 36.4 | 2.08x |

Only `calls`, `closure` and `higher-order` are signal here. They improved in
both measurement orders. The other four do not execute a single call, so their
moves are noise: `lists` ranged from 40 to 54 ns/instruction across invocations,
and `modules` moved in the opposite direction in the two runs. Do not quote the
non-call rows.

Cumulative, against the pre-optimisation build: `calls` 118.5 -> 12.0,
`closure` 174.9 -> 28.7, `higher-order` 159.1 -> 36.4. Those ratios multiply two
separate A/B sessions, so treat them as approximate (about 10x, 6x and 4x).

At this commit, one invocation including the Python baseline:

| program | py ms | cpp ms | speedup | cpp ns/instr |
| --- | ---: | ---: | ---: | ---: |
| `arithmetic` | 145.09 | 2.92 | 49.7x | 16.2 |
| `calls` | 60.75 | 0.72 | 84.0x | 11.7 |
| `strings` | 20.93 | 0.62 | 33.5x | 29.7 |
| `lists` | 20.52 | 0.92 | 22.2x | 44.0 |
| `modules` | 16.29 | 0.74 | 22.1x | 41.0 |
| `closure` | 34.27 | 1.08 | 31.6x | 33.8 |
| `higher-order` | 30.06 | 1.17 | 25.7x | 39.0 |

The absolute figures differ from the A/B tables because those are interleaved
medians and this table is a single invocation. Treat the A/B ratios as the claim
and the absolute numbers as representative.

Variance is worse than it first appeared: programs that finish in well under a
millisecond moved up to 30% between invocations during the second pass, and a
run that measured all of one build before all of the other produced an 11%
"regression" that interleaving turned into a 33% improvement. Compare like for
like on one machine, interleave the two builds invocation by invocation, and
ignore any single-row difference that does not reproduce in both orders. Do not
compare a number here with a number from another machine, and do not compare a
run made with the five-program harness against a run made after `59e78db`.

## What changed

`c735ce0` is the only performance commit; the others are harness and safety work.

- `LOAD_LOCAL` and `STORE_LOCAL` resolved `spacelang.vm_py.Cell` with a module
  import on every execution (about 254 ns per import+attr pair). Local variable
  access cost 155 ns/instruction against 27 ns for globals.
- Every handler dependency is now resolved once in the `VM` constructor and held
  as a strong reference: `Cell`, `Closure`, `bytes`, `spacelang.errors`,
  `SpaceError`, `RuntimeError`, `spacelang.modules.do_import`, the seventeen
  builtins, and interned names for the global table, attribute access and the
  two `Cell` attributes.
- The cell test now runs after a tag check, so an integer local is no longer
  converted to a `PyObject` (allocating a `PyLong`) just to be type-checked.
- `Frame::closure_cells` is created on demand. `pybind11::list()` default
  constructs an empty list, so every call used to allocate one.
- Globals and attributes go through `PyDict_GetItemWithError`, `PyDict_SetItem`,
  `PyObject_GetAttr` and `PyObject_SetAttr` instead of rebuilding a Python string
  per access.
- `e15e54f` recycles frame locals through a free list capped at 64 frames, and
  interns the nine `Closure` attribute names so `CALL_OBJ` reads them through
  `PyObject_GetAttr`. Pooled vectors are cleared before reuse, so no argument
  reference survives into the next call.

## Environment

| | |
| --- | --- |
| OS | Windows 10.0.26100 |
| Compiler | MSVC 19.44.35207.1, `/O2 /std:c++17 /MD /DNDEBUG` |
| Python | CPython 3.13, x64 |
| pybind11 | 2.13.6 |
| Dispatch | **switch** (MSVC defines neither `__GNUC__` nor `__clang__`) |

Two caveats matter when reading these numbers:

1. **The computed-goto dispatcher was not exercised.** `csrc/vm.cpp` uses
   `goto *dispatch_table[op]` only for GCC and Clang. Every number here is the
   portable switch path, so Linux and macOS builds should be at least this fast
   but have not been measured.
2. **The extension was built with `cl` directly, not through
   scikit-build-core.** The checkout had no CMake, no pybind11 and no reachable
   package index, so `csrc/binding.cpp` and `csrc/vm.cpp` were compiled by hand
   into the location the editable install resolves
   (`site-packages/spacelang/_spacelang_cpp.*.pyd`). Functionally equivalent, but
   this is not the wheel build and it is not bit-identical to one.

The native engine is also not a standalone runtime: it is a C++ dispatch loop
over CPython objects, so every string, container, attribute and builtin
operation is still a CPython C-API call. These numbers describe interpreter
overhead, not a departure from CPython. `native/spvm.cpp` is the runtime that
does not need Python; it is a separate line and is not measured here.

## Reproduce

```bash
python -m pip install -e .          # or rebuild the extension by any means
python benchmarks/profile_vm.py --repeat 9 --warmup 2
```

Add `--json PATH` (`-` for stdout) to write a snapshot. `benchmarks/baselines/`
holds one per platform, and `.github/workflows/perf.yml` uploads a Linux/GCC
snapshot on every change to `csrc/` or `benchmarks/`; that job is also the only
place the computed-goto dispatcher gets exercised.

To compare two builds, swap the `.pyd` between runs instead of comparing across
sessions:

```bash
cp old.so  site-packages/spacelang/_spacelang_cpp.*.pyd
python benchmarks/profile_vm.py --repeat 9 --warmup 2
cp new.so  site-packages/spacelang/_spacelang_cpp.*.pyd
python benchmarks/profile_vm.py --repeat 9 --warmup 2
```

Check the extension really changed before trusting a result: `pip install -e .`
does not always recompile, and a stale `.pyd` makes a real change look like a
non-change.

## Test status at this commit

`318 passed, 8 skipped, 1 failed, 46 errors`. The failure
(`tests/test_opt_sp.py::test_server_background_cli_start_and_stop`) and all 46
errors come from the local sandbox denying writes under `%TEMP%`; they reproduce
unchanged with the previously installed extension and are unrelated to the
native engine. `tests/test_vm_cpp.py` and `tests/test_differential.py` pass in
full (99 tests).

## Not covered, and next levers

- **GCC/Clang computed goto** — one CI job on Linux would close this.
- **Cell access is now the hot path.** A read of a cell local costs two
  attribute operations (`initialized`, then `value`) and a write costs two more.
  `LOAD_LOCAL`/`STORE_LOCAL` also still type-check every local. A per-frame
  slot-kind flag would remove the check, and reading the instance `__dict__`
  directly would halve the attribute cost — both trade a little safety for speed
  and should be measured against the parity tests, not assumed.
- **`lists` and `modules` did not move** across either pass. If they matter,
  they need their own investigation (container mutation and method dispatch),
  not another sweep over the dispatch loop.
- **The baseline is recorded but not enforced.** `benchmarks/baselines/` holds a
  snapshot per platform and the perf workflow uploads one per run, so a
  regression can be spotted and bisected. Nothing fails the build yet: a hard
  threshold on a shared runner would mostly measure the runner. Turning this
  into a gate needs stable timings first.
