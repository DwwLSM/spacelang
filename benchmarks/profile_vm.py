#!/usr/bin/env python3
"""Profile the Python and C++ SpaceLang VMs on a few representative programs.

Reports, per program: executed instruction count (counted on the reference VM,
which has per-step hooks), wall time for both engines, nanoseconds per executed
instruction, and the dynamic opcode mix.

This script only observes; nothing under spacelang/ is modified.
"""

from __future__ import annotations

import argparse
import json
import platform as platform_info
import statistics
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

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
    "closure": """
def make_counter():
    value = 0
    def increment():
        nonlocal value
        value = value + 1
        return value
    return increment

counter = make_counter()
total = 0
for i in range(2000):
    total = total + counter()
result = total
""",
    "higher-order": """
def multiplier(factor):
    def scale(value):
        return value * factor
    return scale

double = multiplier(2)
total = 0
for i in range(2000):
    total = total + double(i)
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


ROOT = Path(__file__).resolve().parents[1]


def git_state() -> tuple[str | None, bool | None]:
    """Return (HEAD commit, working tree dirty) or (None, None) outside git."""
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None, None
    return commit or None, bool(status)


def build_payload(rows: list[tuple[str, int, Counter[int], float, float]], args) -> dict:
    """Everything needed to compare two runs later without guessing context."""
    commit, dirty = git_state()
    return {
        "schema": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "commit": commit,
        "dirty": dirty,
        "platform": {
            "system": platform_info.system(),
            "release": platform_info.release(),
            "machine": platform_info.machine(),
            "python": platform_info.python_version(),
            "implementation": platform_info.python_implementation(),
        },
        "harness": {
            "repeat": args.repeat,
            "warmup": args.warmup,
            "programs": [name for name, *_ in rows],
        },
        "results": [
            {
                "program": name,
                "instructions": executed,
                "python_seconds": py_seconds,
                "cpp_seconds": cpp_seconds,
                "python_ns_per_instruction": py_seconds * 1e9 / executed,
                "cpp_ns_per_instruction": cpp_seconds * 1e9 / executed,
                "speedup": py_seconds / cpp_seconds,
                "opcodes": {
                    OP_NAMES.get(op, str(op)): count for op, count in counts.most_common()
                },
            }
            for name, executed, counts, py_seconds, cpp_seconds in rows
        ],
    }


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
    parser.add_argument(
        "--json",
        metavar="PATH",
        help="write the results as JSON ('-' for stdout, which suppresses the table)",
    )
    args = parser.parse_args()
    quiet = args.json == "-"

    names = args.program or list(PROGRAMS)
    header = (
        f"{'program':<14}{'instrs':>9}{'py ms':>10}{'cpp ms':>10}"
        f"{'speedup':>9}{'py ns/i':>10}{'cpp ns/i':>10}"
    )
    if not quiet:
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
        if not quiet:
            print(
                f"{name:<14}{executed:>9,}{py_seconds * 1e3:>10.2f}{cpp_seconds * 1e3:>10.2f}"
                f"{py_seconds / cpp_seconds:>8.1f}x{py_ns:>10.1f}{cpp_ns:>10.1f}"
            )
        rows.append((name, executed, counts, py_seconds, cpp_seconds))

    if not quiet:
        for name, executed, counts, _, _ in rows:
            top = counts.most_common(args.top)
            share = ", ".join(
                f"{OP_NAMES.get(op, str(op))} {count:,} ({count * 100 / executed:.0f}%)"
                for op, count in top
            )
            print(f"\n{name}: {share}")

    if args.json:
        text = json.dumps(build_payload(rows, args), indent=2) + "\n"
        if args.json == "-":
            sys.stdout.write(text)
        else:
            destination = Path(args.json)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(text, encoding="utf-8")
            if not quiet:
                print(f"\nwrote {destination}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
