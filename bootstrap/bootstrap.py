#!/usr/bin/env python3
"""Bootstrap driver for the self-hosted SpaceLang VM.

Everything here talks to the toolchain through `python -m spacelang.main`, so
this file only needs the standard library and always tests the checkout it
lives in.

    py bootstrap/bootstrap.py build          # regenerate the .sp artifacts
    py bootstrap/bootstrap.py check          # reference VM vs self-hosted VM
    py bootstrap/bootstrap.py selfhost       # sp_vm.sp running sp_vm.sp
    py bootstrap/bootstrap.py all            # build + check + selfhost

`run` is also available for one-off executions:

    py bootstrap/bootstrap.py run demos/fib.sp

Subprocesses use `-S` so that an unrelated editable install of SpaceLang in
site-packages cannot shadow this checkout; SpaceLang itself imports only the
standard library.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
VM_SOURCE = HERE / "sp_vm.py"
VM_PROGRAM = HERE / "sp_vm.sp"
DEMO_DIR = HERE / "demos"


def _env() -> dict[str, str]:
    env = dict(os.environ)
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(ROOT) + (os.pathsep + existing if existing else "")
    # Keep captured output byte-for-byte comparable on any console code page.
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def cli(*args: object, check: bool = True) -> subprocess.CompletedProcess[str]:
    """Run `python -m spacelang.main ...` against this checkout."""
    command = [sys.executable, "-S", "-m", "spacelang.main", *(str(arg) for arg in args)]
    result = subprocess.run(
        command,
        cwd=ROOT,
        env=_env(),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if check and result.returncode != 0:
        raise SystemExit(
            f"command failed ({result.returncode}): {' '.join(command)}\n"
            f"{result.stdout}{result.stderr}"
        )
    return result


def demo_sources() -> list[Path]:
    return sorted(DEMO_DIR.glob("*.py"))


def build() -> None:
    print("[build] compiler -> SpaceLang artifacts")
    started = time.perf_counter()
    cli("compile-py", VM_SOURCE, VM_PROGRAM)
    print(f"  {VM_SOURCE.name} -> {VM_PROGRAM.name} ({VM_PROGRAM.stat().st_size:,} bytes)")
    for source in demo_sources():
        target = source.with_suffix(".sp")
        cli("compile-py", source, target)
        print(f"  {source.name} -> {target.name} ({target.stat().st_size:,} bytes)")
    print(f"  built in {time.perf_counter() - started:.2f}s")


def check() -> bool:
    print("[check] reference VM vs self-hosted VM (identical output expected)")
    ok = True
    for target in sorted(DEMO_DIR.glob("*.sp")):
        reference = cli("run", target)
        hosted = cli("run", VM_PROGRAM, target, check=False)
        same = (
            hosted.returncode == reference.returncode
            and hosted.stdout == reference.stdout
        )
        if not same:
            ok = False
            print(f"  FAIL {target.name}")
            print(f"    reference stdout: {reference.stdout!r}")
            print(f"    hosted    stdout: {hosted.stdout!r}")
            if hosted.stderr:
                print(f"    hosted stderr: {hosted.stderr.strip()}")
        else:
            lines = reference.stdout.count("\n")
            print(f"  PASS {target.name} ({lines} output lines)")
    return ok


def run_target(target: Path, extra: list[str] | None = None) -> None:
    result = cli("run", VM_PROGRAM, target, *(extra or []), check=False)
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)
    raise SystemExit(result.returncode)


def selfhost(depth: int, program: Path) -> bool:
    """Run `depth` nested copies of the VM, with `program` as the innermost target."""
    chain = ["sp_vm.sp"] * depth + [str(program)]
    print(f"[selfhost] depth {depth}: " + " -> ".join(Path(part).name for part in chain))
    expected = cli("run", program).stdout
    started = time.perf_counter()
    result = cli("run", *(VM_PROGRAM, *(VM_PROGRAM for _ in range(depth - 1)), program), check=False)
    elapsed = time.perf_counter() - started
    if result.stdout == expected:
        lines = expected.count("\n")
        print(f"  OK   {elapsed:.2f}s, {lines} output lines, identical to the reference VM")
        return True
    print(f"  FAIL {elapsed:.2f}s")
    print(f"    expected: {expected!r}")
    print(f"    actual  : {result.stdout!r}")
    if result.stderr:
        print(f"    stderr: {result.stderr.strip()}")
    return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="bootstrap",
        description="Build and exercise the self-hosted SpaceLang VM.",
    )
    commands = parser.add_subparsers(dest="command")
    commands.add_parser("build", help="compile sp_vm.py and the demo programs")
    commands.add_parser("check", help="compare reference VM and self-hosted VM output")
    commands.add_parser("all", help="build, check, then run the depth-2 chain")
    run_command = commands.add_parser("run", help="run one .sp program with the self-hosted VM")
    run_command.add_argument("target", type=Path)
    run_command.add_argument("args", nargs="*")
    host_command = commands.add_parser("selfhost", help="run the VM under itself")
    host_command.add_argument("--depth", type=int, default=2)
    host_command.add_argument("--program", type=Path, default=DEMO_DIR / "hello.sp")
    args = parser.parse_args(argv)

    command = args.command or "all"
    if command in {"build", "all"}:
        build()
    if command in {"check", "all"}:
        if not check():
            return 1
    if command in {"all", "selfhost"}:
        if command == "all":
            if not selfhost(2, DEMO_DIR / "hello.sp"):
                return 1
        elif not selfhost(args.depth, args.program):
            return 1
    if command == "run":
        run_target(args.target, args.args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
