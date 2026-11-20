#!/usr/bin/env python3
"""Profile the Python and C++ SpaceLang VMs on a few representative programs.

Reports, per program: executed instruction count (counted on the reference VM,
which has per-step hooks), wall time for both engines, nanoseconds per executed
instruction, and the dynamic opcode mix.

This script only observes; nothing under spacelang/ is modified.
"""

from __future__ import annotations

import argparse
import statistics
import time
from collections import Counter

from spacelang.ir import OP
from spacelang.pyfront import compile_py
from spacelang.vm_py import VM as PythonVM

try:
    from spacelang.vm_cpp import VM as CppVM
except ImportError as error:  # pragma: no cover - depends on the build
    raise SystemExit(
        f"the native extension is not available ({error}).\n"
        "Build it with: python -m pip install -e ."
    ) from error

OP_NAMES = {int(op.value): op.name for op in OP}

PROGRAMS: dict[str, str] = {
    "arithmetic": """
result = 0
for i in range(20000):
    result = result + i * 3
""",
    "calls": """
def fib(n):
    if n < 2:
        return n
    return fib(n - 1) + fib(n - 2)

result = fib(17)
""",
    "strings": """
text = ''
for i in range(3000):
    text = text + 'x'
result = text
""",
    "lists": """
items = []
for i in range(3000):
    items.append(i)
result = len(items)
""",
    "modules": """
import math

total = 0
for i in range(2000):
    total = total + math.sqrt(i)
result = total
""",
}


class CountingVM(PythonVM):
    """Reference VM that counts executed opcodes; timing is not taken from it."""

    def __init__(self, program) -> None:
        super().__init__(program)
        self.counts: Counter[int] = Counter()

    def _before_step(self, instr) -> None:  # type: ignore[override]
        self.counts[int(instr.op)] += 1


def count_instructions(program) -> tuple[int, Counter[int]]:
    vm = CountingVM(program)
    vm.run()
    total = sum(vm.counts.values())
    return total, vm.counts


def time_engine(vm_type, program, *, repeats: int, warmup: int) -> float:
    samples: list[float] = []
    for index in range(warmup + repeats):
        vm = vm_type(program)
        started = time.perf_counter()
        vm.run()
        elapsed = time.perf_counter() - started
        if index >= warmup:
            samples.append(elapsed)
    return statistics.median(samples)


def describe_engine(vm_type, program) -> object:
    vm = vm_type(program)
    vm.run()
    return vm.globals_.get("result")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeat", type=int, default=5, help="measured runs (default 5)")
    parser.add_argument("--warmup", type=int, default=1, help="unmeasured runs (default 1)")
    parser.add_argument(
        "--program",
        action="append",
        choices=sorted(PROGRAMS),
        help="limit to one or more programs",
    )
    parser.add_argument("--top", type=int, default=4, help="opcodes to list per program")
    args = parser.parse_args()

    names = args.program or list(PROGRAMS)
    header = (
        f"{'program':<12}{'instrs':>9}{'py ms':>10}{'cpp ms':>10}"
        f"{'speedup':>9}{'py ns/i':>10}{'cpp ns/i':>10}"
    )
    print(header)
    print("-" * len(header))

    rows: list[tuple[str, int, Counter[int], float, float]] = []
    for name in names:
        program = compile_py(PROGRAMS[name])
        executed, counts = count_instructions(program)

        py_result = describe_engine(PythonVM, program)
        cpp_result = describe_engine(CppVM, program)
        if py_result != cpp_result:
            raise SystemExit(f"{name}: engines disagree ({py_result!r} vs {cpp_result!r})")

        py_seconds = time_engine(PythonVM, program, repeats=args.repeat, warmup=args.warmup)
        cpp_seconds = time_engine(CppVM, program, repeats=args.repeat, warmup=args.warmup)
        py_ns = py_seconds * 1e9 / executed
        cpp_ns = cpp_seconds * 1e9 / executed
        print(
            f"{name:<12}{executed:>9,}{py_seconds * 1e3:>10.2f}{cpp_seconds * 1e3:>10.2f}"
            f"{py_seconds / cpp_seconds:>8.1f}x{py_ns:>10.1f}{cpp_ns:>10.1f}"
        )
        rows.append((name, executed, counts, py_seconds, cpp_seconds))

    for name, executed, counts, _, _ in rows:
        top = counts.most_common(args.top)
        share = ", ".join(
            f"{OP_NAMES.get(op, str(op))} {count:,} ({count * 100 / executed:.0f}%)"
            for op, count in top
        )
        print(f"\n{name}: {share}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
