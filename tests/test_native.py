"""Tests for the native (Python-free) SpaceLang runner in native/."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
NATIVE = ROOT / "native"
RUNNER = NATIVE / ("spvm.exe" if os.name == "nt" else "spvm")
COMPILER = NATIVE / ("compiler.exe" if os.name == "nt" else "compiler")
DEMOS = ROOT / "bootstrap" / "demos"
EXAMPLES = NATIVE / "examples"


def _env() -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT)
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def _cli(*args: object) -> str:
    result = subprocess.run(
        [sys.executable, "-S", "-m", "spacelang.main", *(str(arg) for arg in args)],
        cwd=ROOT,
        env=_env(),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )
    return result.stdout


@pytest.mark.skipif(not RUNNER.is_file(), reason="native runner is not built")
@pytest.mark.parametrize("name", ["hello", "fib", "collections", "closure"])
def test_native_runner_matches_reference_vm(name: str) -> None:
    program = DEMOS / f"{name}.sp"
    if not program.is_file():
        pytest.skip(f"{program.name} has not been compiled")
    native = subprocess.run(
        [str(RUNNER), str(program)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )
    assert native.stdout == _cli("run", program)


@pytest.mark.skipif(not RUNNER.is_file(), reason="native runner is not built")
def test_native_runner_reads_sidecar_names() -> None:
    """quine.sp keeps its name table in quine.names.json."""
    quine = ROOT / "tests" / "test_quine" / "quine.sp"
    native = subprocess.run(
        [str(RUNNER), str(quine)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )
    assert native.stdout == _cli("run", quine)


@pytest.mark.skipif(
    shutil.which("g++") is None,
    reason="needs g++ to build an embedded executable",
)
def test_embed_builds_a_standalone_program(tmp_path: Path) -> None:
    program = DEMOS / "hello.sp"
    if not program.is_file():
        pytest.skip("hello.sp has not been compiled")
    output = tmp_path / "hello.exe"
    subprocess.run(
        [
            sys.executable,
            str(NATIVE / "embed.py"),
            str(program),
            "-o",
            str(output),
            "--no-static",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    result = subprocess.run(
        [str(output)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )
    assert result.stdout == _cli("run", program)


@pytest.mark.skipif(not COMPILER.is_file(), reason="compiler.exe is not built")
@pytest.mark.parametrize("name", ["tour", "flow"])
def test_compiler_compiles_and_runs_python_source(name: str, tmp_path: Path) -> None:
    """compiler.exe: Python source -> .sp (via spc.sp) -> native execution."""
    source = EXAMPLES / f"{name}.py"
    local = tmp_path / f"{name}.py"
    local.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

    result = subprocess.run(
        [str(COMPILER), str(local)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )
    assert (tmp_path / f"{name}.sp").is_file(), "the compiler should emit bytecode"

    reference = subprocess.run(
        [sys.executable, "-S", str(local)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )
    assert result.stdout == reference.stdout


@pytest.mark.skipif(not COMPILER.is_file(), reason="compiler.exe is not built")
def test_compiler_compiles_functions(tmp_path: Path) -> None:
    """The input language includes functions (needed to compile spc.py)."""
    local = tmp_path / "add.py"
    local.write_text("def add(a, b):\n    return a + b\n\nprint(add(2, 3))\n", encoding="utf-8")
    result = subprocess.run(
        [str(COMPILER), str(local)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )
    assert result.stdout.strip() == "5"
    assert (tmp_path / "add.sp").is_file()


@pytest.mark.skipif(not COMPILER.is_file(), reason="compiler.exe is not built")
def test_compiler_rejects_unsupported_syntax(tmp_path: Path) -> None:
    local = tmp_path / "bad.py"
    local.write_text("class Fancy:\n    pass\n", encoding="utf-8")
    result = subprocess.run(
        [str(COMPILER), str(local)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert result.returncode != 0
    assert "spc:" in result.stdout
    assert not (tmp_path / "bad.sp").is_file()
