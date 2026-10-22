from __future__ import annotations

import argparse
from contextlib import redirect_stdout
from io import StringIO
from statistics import median
from time import perf_counter

from spacelang.pyfront import compile_py
from spacelang.vm_cpp import VM as CppVM
from spacelang.vm_py import VM as PythonVM


def benchmark_engines(
    source: str,
    *,
    repeats: int = 7,
    warmup: int = 2,
    result_name: str | None = "result",
) -> dict[str, float]:
    """Return median execution times for CPython and both SpaceLang VMs."""
    if repeats < 1 or warmup < 0:
        raise ValueError("repeats must be >= 1 and warmup must be non-negative")

    python_code = compile(source, "<benchmark>", "exec")
    program = compile_py(source)
    engine_names = ("CPython", "SP Python", "SP C++")
    samples = {name: [] for name in engine_names}

    def run_once(engine: str) -> tuple[float, str, object]:
        output = StringIO()
        namespace = {"__name__": "__main__"}
        machine = None
        if engine == "SP Python":
            machine = PythonVM(program)
        elif engine == "SP C++":
            machine = CppVM(program)

        with redirect_stdout(output):
            started = perf_counter()
            if engine == "CPython":
                exec(python_code, namespace, namespace)
            else:
                machine.run()
            elapsed = perf_counter() - started

        state = namespace if machine is None else machine.globals_
        if result_name is None:
            result = None
        else:
            if result_name not in state:
                raise AssertionError(f"{engine} did not set {result_name!r}")
            result = state[result_name]
        return elapsed, output.getvalue(), result

    for iteration in range(warmup + repeats):
        offset = iteration % len(engine_names)
        order = engine_names[offset:] + engine_names[:offset]
        measured = {engine: run_once(engine) for engine in order}
        reference_output = measured["CPython"][1]
        reference_result = measured["CPython"][2]

        for engine, (_, output, result) in measured.items():
            if output != reference_output or type(result) is not type(reference_result) or result != reference_result:
                raise AssertionError(f"{engine} differs from CPython")

        if iteration >= warmup:
            for engine, (elapsed, _, _) in measured.items():
                samples[engine].append(elapsed)

    return {engine: median(durations) for engine, durations in samples.items()}


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare CPython and both SpaceLang VM runtimes.")
    parser.add_argument("--n", type=int, default=27, help="Fibonacci input (default: 27)")
    parser.add_argument("--repeat", type=int, default=7, help="Measured runs per engine (default: 7)")
    parser.add_argument("--warmup", type=int, default=2, help="Unmeasured runs per engine (default: 2)")
    args = parser.parse_args()
    if args.n < 0 or args.repeat < 1 or args.warmup < 0:
        parser.error("--n must be non-negative, --repeat >= 1, and --warmup >= 0")

    source = f"""
def fib(n):
    if n < 2:
        return n
    return fib(n - 1) + fib(n - 2)

result = fib({args.n})
"""
    durations = benchmark_engines(source, repeats=args.repeat, warmup=args.warmup)
    baseline = durations["CPython"]
    for name, duration in durations.items():
        comparison = "baseline" if name == "CPython" else (
            f"{baseline / duration:.2f}x faster than CPython"
            if duration < baseline
            else f"{duration / baseline:.2f}x slower than CPython"
        )
        print(f"{name} median: {duration:.6f}s ({comparison})")
    print(f"SP C++ vs SP Python: {durations['SP Python'] / durations['SP C++']:.2f}x faster")
    print("All engines produced matching output and results.")


if __name__ == "__main__":
    main()
