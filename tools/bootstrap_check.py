#!/usr/bin/env python3
"""Check the three-stage bootstrap of ``native/spc.py`` and its fixed point.

The chain is the classic one:

    stage0:  python -m spacelang compile-py native/spc.py build/spc1.sp
    stage1:  build/compiler1.exe native/spc.py build/spc2.sp
    stage2:  build/compiler2.exe native/spc.py build/spc3.sp

``compiler1.exe`` embeds ``spc1.sp`` (the compiler compiled by the ordinary
Python toolchain); ``compiler2.exe`` embeds ``spc2.sp`` (the compiler compiled
by ``compiler1.exe``).  The fixed point is

    bytes(spc2.sp) == bytes(spc3.sp)

i.e. a compiler that is compiled by itself reproduces itself byte for byte.
Python is only used for stage 0 (and to build the two executables).

The tool also checks determinism (``PYTHONHASHSEED=0`` and unset, two runs
each) and that ``compiler2.exe`` still compiles and runs the example programs
correctly.

Usage::

    py -S tools/bootstrap_check.py
    py -S tools/bootstrap_check.py --skip-determinism --json build/report.json

Build outputs go to ``build/`` (gitignored).  Exit code 0 means the fixed
point was reached and every check passed.
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT / "native"
BUILD = ROOT / "build"
SPC_PY = NATIVE / "spc.py"
EXAMPLES = ["tour.py", "flow.py"]


def run(command: list[str], *, cwd: Path = ROOT, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        command,
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def describe(path: Path) -> str:
    if not path.is_file():
        return f"{path.relative_to(ROOT)}: MISSING"
    return f"{path.relative_to(ROOT)}: {path.stat().st_size:,} bytes sha256 {sha256(path)}"


def python_env(extra: dict[str, str] | None = None, *, hashseed: str | None = None) -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT)
    env.pop("PYTHONHASHSEED", None)
    if hashseed is not None:
        env["PYTHONHASHSEED"] = hashseed
    if extra:
        env.update(extra)
    return env


def stage0(output: Path, *, hashseed: str | None) -> None:
    result = run(
        [sys.executable, "-S", "-m", "spacelang.main", "compile-py", str(SPC_PY), str(output)],
        env=python_env(hashseed=hashseed),
    )
    if result.returncode != 0 or not output.is_file():
        raise RuntimeError(f"stage 0 failed (exit {result.returncode})\n{result.stdout}\n{result.stderr}")


def build_compiler(spc_sp: Path, exe: Path) -> None:
    """Compile compiler.cpp + spvm.cpp with `spc_sp` embedded as spc_blob.h."""
    source_dir = BUILD / "src"
    source_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(NATIVE / "compiler.cpp", source_dir / "compiler_main.cpp")
    shutil.copyfile(NATIVE / "spvm.cpp", source_dir / "spvm.cpp")
    blob = source_dir / "spc_blob.h"
    result = run([sys.executable, "-S", str(NATIVE / "make_blob.py"), str(spc_sp), str(blob)])
    if result.returncode != 0:
        raise RuntimeError(f"make_blob failed\n{result.stdout}\n{result.stderr}")
    compiler = os.environ.get("CXX") or "g++"
    common = [compiler, "-O2", "-std=c++17", "-o", str(exe), str(source_dir / "compiler_main.cpp")]
    first = run([*common[:5], "-static", *common[5:]])
    if first.returncode != 0:
        # Some toolchains have no static libstdc++; the artifact still runs.
        second = run(common)
        if second.returncode != 0:
            raise RuntimeError(f"C++ build failed\n{first.stderr}\n{second.stderr}")


def compile_with_compiler(exe: Path, source: Path, output: Path) -> None:
    result = run([str(exe), str(source), str(output)])
    if result.returncode != 0 or not output.is_file():
        raise RuntimeError(
            f"{exe.name} could not compile {source.relative_to(ROOT)} (exit {result.returncode})\n"
            f"{result.stdout}\n{result.stderr}"
        )


def report_diff(left: Path, right: Path, limit: int = 20) -> str:
    """Human-readable summary of the first bytes/lines that differ."""
    a = left.read_bytes()
    b = right.read_bytes()
    lines = [f"  sizes: {len(a):,} vs {len(b):,} bytes"]
    offset = next((i for i, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b)))
    lines.append(f"  first differing byte at offset {offset}")
    try:
        a_text = a.decode("utf-8")
        b_text = b.decode("utf-8")
    except UnicodeDecodeError:  # pragma: no cover - .sp is ASCII in practice
        return "\n".join(lines)
    diff = list(
        difflib.unified_diff(
            a_text.splitlines(),
            b_text.splitlines(),
            fromfile="spc2.sp",
            tofile="spc3.sp",
            lineterm="",
        )
    )
    lines.extend("  " + line for line in diff[:limit])
    if len(diff) > limit:
        lines.append(f"  ... ({len(diff) - limit} more diff lines)")
    return "\n".join(lines)


def check_examples(compiler: Path) -> list[str]:
    """compiler.exe one-argument mode: compile, then run; compare with CPython."""
    notes = []
    for name in EXAMPLES:
        source = NATIVE / "examples" / name
        if not source.is_file():
            notes.append(f"  [skip] {name}: not present")
            continue
        local = BUILD / name
        shutil.copyfile(source, local)
        result = run([str(compiler), str(local)])
        reference = run([sys.executable, "-S", str(local)])
        if result.returncode != 0:
            raise RuntimeError(f"{compiler.name} failed on {name} (exit {result.returncode})\n{result.stdout}\n{result.stderr}")
        if result.stdout != reference.stdout:
            raise RuntimeError(
                f"{compiler.name} output for {name} differs from CPython\n"
                f"--- compiler ---\n{result.stdout}\n--- python ---\n{reference.stdout}"
            )
        notes.append(f"  OK {name}: {len(result.stdout.splitlines())} output lines match CPython")
    return notes


def main(argv: list[str] | None = None) -> int:
    global BUILD
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--build-dir", type=Path, default=BUILD, help="where build artifacts go (default: build/)")
    parser.add_argument("--skip-determinism", action="store_true", help="do not run the four-stage-0 determinism check")
    parser.add_argument("--skip-examples", action="store_true", help="do not run the example programs through compiler2")
    parser.add_argument("--json", type=Path, help="also write a machine-readable report here")
    parser.add_argument("--keep", action="store_true", help="keep the auxiliary determinism artifacts")
    args = parser.parse_args(argv)

    BUILD = args.build_dir.resolve()
    BUILD.mkdir(parents=True, exist_ok=True)
    if shutil.which(os.environ.get("CXX") or "g++") is None:
        print("bootstrap_check: no C++ compiler found (set CXX or put g++ on PATH)", file=sys.stderr)
        return 2
    if not SPC_PY.is_file():
        print(f"bootstrap_check: {SPC_PY} not found", file=sys.stderr)
        return 2

    report: dict[str, object] = {"repo": str(ROOT), "build_dir": str(BUILD)}
    print(f"[bootstrap] {SPC_PY.relative_to(ROOT)}")
    print(f"[bootstrap] build dir: {BUILD.relative_to(ROOT)}")

    spc1 = BUILD / "spc1.sp"
    print("\n[stage0] python toolchain -> build/spc1.sp")
    stage0(spc1, hashseed=None)
    print("  " + describe(spc1))

    compiler1 = BUILD / ("compiler1.exe" if os.name == "nt" else "compiler1")
    print("\n[compiler1] link compiler.cpp + spvm.cpp with spc1.sp embedded")
    build_compiler(spc1, compiler1)
    print("  " + describe(compiler1))

    spc2 = BUILD / "spc2.sp"
    print("\n[stage1] compiler1.exe native/spc.py -> build/spc2.sp")
    compile_with_compiler(compiler1, SPC_PY, spc2)
    print("  " + describe(spc2))

    compiler2 = BUILD / ("compiler2.exe" if os.name == "nt" else "compiler2")
    print("\n[compiler2] link compiler.cpp + spvm.cpp with spc2.sp embedded")
    build_compiler(spc2, compiler2)
    print("  " + describe(compiler2))

    spc3 = BUILD / "spc3.sp"
    print("\n[stage2] compiler2.exe native/spc.py -> build/spc3.sp")
    compile_with_compiler(compiler2, SPC_PY, spc3)
    print("  " + describe(spc3))

    first = sha256(spc2)
    second = sha256(spc3)
    fixed_point = first == second
    report.update(
        {
            "stage0": {"path": str(spc1.relative_to(ROOT)), "sha256": sha256(spc1), "bytes": spc1.stat().st_size},
            "stage1": {"path": str(spc2.relative_to(ROOT)), "sha256": first, "bytes": spc2.stat().st_size},
            "stage2": {"path": str(spc3.relative_to(ROOT)), "sha256": second, "bytes": spc3.stat().st_size},
            "fixed_point": fixed_point,
        }
    )
    print("\n[fixed-point]")
    if fixed_point:
        print(f"  OK: spc2.sp == spc3.sp ({spc2.stat().st_size:,} bytes)")
        print(f"  sha256 {first}")
    else:
        print("  FAIL: spc2.sp != spc3.sp")
        print(report_diff(spc2, spc3))
        print(f"  spc2 sha256 {first}")
        print(f"  spc3 sha256 {second}")

    determinism_ok = True
    if not args.skip_determinism:
        print("\n[determinism] stage 0 twice with PYTHONHASHSEED=0 and twice unset")
        variants = []
        for seed in ("0", None):
            for run_index in (0, 1):
                suffix = f"seed{seed if seed is not None else 'unset'}_{run_index}"
                target = BUILD / f"spc1_{suffix}.sp"
                stage0(target, hashseed=seed)
                variants.append((suffix, target))
                print(f"  {suffix}: {sha256(target)}")
        hashes = {sha256(path) for _, path in variants}
        determinism_ok = len(hashes) == 1
        report["determinism"] = {
            "stage0_variants": {name: sha256(path) for name, path in variants},
            "stage0_stable": determinism_ok,
        }
        print(f"  stage0 across seeds: {'OK' if determinism_ok else 'FAIL'}")
        # A second run of each compiler process must also reproduce itself.
        if determinism_ok:
            rerun = {}
            for label, compiler, target, replace in (
                ("stage1", compiler1, BUILD / "spc2_rerun.sp", spc2),
                ("stage2", compiler2, BUILD / "spc3_rerun.sp", spc3),
            ):
                compile_with_compiler(compiler, SPC_PY, target)
                same = sha256(target) == sha256(replace)
                rerun[label] = same
                print(f"  {label} rerun identical: {'OK' if same else 'FAIL'}")
                determinism_ok = determinism_ok and same
            report["determinism"]["reruns_identical"] = rerun
        if not args.keep:
            for _, path in variants:
                path.unlink(missing_ok=True)
            for name in ("spc2_rerun.sp", "spc3_rerun.sp"):
                (BUILD / name).unlink(missing_ok=True)

    examples_ok = True
    if not args.skip_examples:
        print("\n[behavior] compiler2.exe compiles and runs the examples (compared with CPython)")
        try:
            for line in check_examples(compiler2):
                print(line)
        except RuntimeError as error:
            examples_ok = False
            print(f"  FAIL: {error}")

    report["determinism_ok"] = determinism_ok
    report["examples_ok"] = examples_ok
    report["ok"] = bool(fixed_point and determinism_ok and examples_ok)

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"\nwrote {args.json.relative_to(ROOT) if args.json.is_relative_to(ROOT) else args.json}")

    print("\n[result] " + ("PASS" if report["ok"] else "FAIL"))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
