from __future__ import annotations

import argparse
from statistics import median
from time import perf_counter

from spacelang.pyfront import compile_py
from spacelang.vm_cpp import VM as CppVM
from spacelang.vm_py import VM as PythonVM


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare SpaceLang Python and C++ VM runtimes.")
    parser.add_argument("--n", type=int, default=25, help="Fibonacci input (default: 25)")
    parser.add_argument("--repeat", type=int, default=3, help="Runs per engine (default: 3)")
    args = parser.parse_args()
    if args.n < 0 or args.repeat < 1:
        parser.error("--n must be non-negative and --repeat must be at least one")

    program = compile_py(
        f"""
def fib(n):
    if n < 2:
        return n
    return fib(n - 1) + fib(n - 2)

result = fib({args.n})
"""
    )
    durations = {}
    expected = None
    for name, vm_type in (("Python", PythonVM), ("C++", CppVM)):
        samples = []
        for _ in range(args.repeat):
            vm = vm_type(program)
            start = perf_counter()
            vm.run()
            samples.append(perf_counter() - start)
            result = vm.globals_["result"]
            if expected is None:
                expected = result
            elif result != expected:
                raise RuntimeError(f"{name} VM returned {result}, expected {expected}")
        durations[name] = median(samples)
        print(f"{name} VM median: {durations[name]:.6f}s")

    print(f"Result: {expected}")
    print(f"Speedup: {durations['Python'] / durations['C++']:.2f}x")


if __name__ == "__main__":
    main()
