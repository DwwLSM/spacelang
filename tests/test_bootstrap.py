"""Bootstrap and fixed-point tests for the SpaceLang compiler (native/spc.py).

The chain these tests guard is the classic three-stage one:

    stage0:  python -m spacelang compile-py native/spc.py build/spc1.sp
    stage1:  compiler1.exe native/spc.py build/spc2.sp
    stage2:  compiler2.exe native/spc.py build/spc3.sp
    fixed point <=> sha256(spc2.sp) == sha256(spc3.sp)

Stage 0 is the only step that needs Python.  The heavier tests skip unless a
local ``native/compiler.exe`` and a C++ compiler are available (both are build
outputs, so CI without a native build skips them).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
NATIVE = ROOT / "native"
SPC = NATIVE / "spc.py"
COMPILER = NATIVE / ("compiler.exe" if os.name == "nt" else "compiler")
SPVM = NATIVE / ("spvm.exe" if os.name == "nt" else "spvm")
CXX = os.environ.get("CXX") or "g++"
PYTHON = sys.executable

needs_compiler = pytest.mark.skipif(not COMPILER.is_file(), reason="native/compiler.exe is not built")
needs_cxx = pytest.mark.skipif(shutil.which(CXX) is None, reason=f"no C++ compiler ({CXX}) on PATH")


def _env() -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT)
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def _run(command: list[str], cwd: Path = ROOT) -> subprocess.CompletedProcess:
    return subprocess.run(
        command,
        cwd=str(cwd),
        env=_env(),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def test_audit_reports_no_missing_constructs(tmp_path: Path) -> None:
    """The audit must not find any construct spc.py uses that spc.py rejects."""
    report = tmp_path / "audit.json"
    result = _run([PYTHON, "-S", str(ROOT / "tools" / "bootstrap_audit.py"), "--json", str(report)])
    assert result.returncode == 0, result.stdout + result.stderr
    data = json.loads(report.read_text(encoding="utf-8"))
    assert data["missing"] == [], data["missing"]
    assert data["first_failure"] is None, data["first_failure"]


def test_stage0_is_deterministic(tmp_path: Path) -> None:
    """Stage 0 must be byte-stable across runs and PYTHONHASHSEED values."""
    outputs = []
    for index, seed in enumerate(("0", None)):
        env = _env()
        env.pop("PYTHONHASHSEED", None)
        if seed is not None:
            env["PYTHONHASHSEED"] = seed
        output = tmp_path / f"spc1_{index}.sp"
        result = subprocess.run(
            [PYTHON, "-S", "-m", "spacelang.main", "compile-py", str(SPC), str(output)],
            cwd=str(ROOT),
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert output.is_file()
        outputs.append(output.read_bytes())
    assert outputs[0] == outputs[1]


@needs_compiler
def test_compiler_compiles_its_own_source(tmp_path: Path) -> None:
    """Milestone 1: compiler.exe compiles native/spc.py itself."""
    output = tmp_path / "spc2.sp"
    result = _run([str(COMPILER), str(SPC), str(output)])
    assert result.returncode == 0, result.stdout + result.stderr
    assert output.is_file()
    # A self-compiled compiler is a multi-megabyte .sp artifact (function ids
    # are encoded unary, so ~5 MB), not a tiny stub.
    assert output.stat().st_size > 4_000_000


@needs_compiler
@needs_cxx
def test_three_stage_fixed_point(tmp_path: Path) -> None:
    """Milestone 2: stage2 == stage3, byte for byte, and stage2 behaves."""
    report_path = tmp_path / "bootstrap.json"
    result = _run(
        [
            PYTHON,
            "-S",
            str(ROOT / "tools" / "bootstrap_check.py"),
            "--skip-determinism",
            "--json",
            str(report_path),
        ]
    )
    assert result.returncode == 0, result.stdout + result.stderr
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["fixed_point"] is True
    assert report["stage1"]["sha256"] == report["stage2"]["sha256"]
    assert report["stage1"]["bytes"] == report["stage2"]["bytes"]
    assert report["examples_ok"] is True


@needs_compiler
@needs_cxx
def test_spc2_is_a_working_compiler(tmp_path: Path) -> None:
    """The stage-1 artifact runs: spc2.sp compiles a program and it executes.

    This uses the standalone VM instead of rebuilding compiler2.exe, so the
    assertion is "the self-compiled artifact works", not just "it exists".
    """
    if not SPVM.is_file():
        pytest.skip("native/spvm.exe is not built")
    spc2 = tmp_path / "spc2.sp"
    result = _run([str(COMPILER), str(SPC), str(spc2)])
    assert result.returncode == 0, result.stdout + result.stderr

    program = tmp_path / "add.py"
    program.write_text("def add(a, b):\n    return a + b\n\nprint(add(2, 3))\n", encoding="utf-8")
    compiled = tmp_path / "add.sp"
    result = _run([str(SPVM), str(spc2), str(program), str(compiled)])
    assert result.returncode == 0, result.stdout + result.stderr
    assert compiled.is_file()

    result = _run([str(SPVM), str(compiled)])
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == "5"
