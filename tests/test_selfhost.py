"""Tests for the self-hosted SpaceLang VM (bootstrap/sp_vm.py)."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
VM_SOURCE = ROOT / "bootstrap" / "sp_vm.py"

HELLO = """
def greet(name="world"):
    return f"Hello, {name}!"

print(greet())
"""


def _env() -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT)
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def cli(*args: object) -> subprocess.CompletedProcess[str]:
    """Run the SpaceLang CLI against this checkout, isolated from site-packages."""
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
    assert result.returncode == 0, f"{command} failed:\n{result.stdout}{result.stderr}"
    return result


@pytest.fixture(scope="module")
def vm_program(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Compile the self-hosted VM once for the whole module."""
    program = tmp_path_factory.mktemp("bootstrap") / "sp_vm.sp"
    cli("compile-py", VM_SOURCE, program)
    return program


def compile_source(tmp_path: Path, name: str, source: str) -> Path:
    python_source = tmp_path / f"{name}.py"
    python_source.write_text(source, encoding="utf-8")
    program = tmp_path / f"{name}.sp"
    cli("compile-py", python_source, program)
    return program


def test_self_hosted_vm_matches_reference_vm(vm_program: Path, tmp_path: Path) -> None:
    program = compile_source(tmp_path, "hello", HELLO)
    reference = cli("run", program).stdout
    assert reference == "Hello, world!\n"
    assert cli("run", vm_program, program).stdout == reference


def test_self_hosted_vm_runs_a_compiled_copy_of_itself(
    vm_program: Path, tmp_path: Path
) -> None:
    """Depth 2: the VM interprets its own program, which interprets a target."""
    program = compile_source(tmp_path, "hello", HELLO)
    assert cli("run", vm_program, vm_program, program).stdout == "Hello, world!\n"


def test_run_passes_trailing_arguments_as_argv(tmp_path: Path) -> None:
    program = compile_source(tmp_path, "argv", "print(__argv__[1])\n")
    assert cli("run", program, "payload").stdout == "payload\n"


def test_vm_forwards_argv_to_the_program_it_runs(
    vm_program: Path, tmp_path: Path
) -> None:
    program = compile_source(
        tmp_path,
        "echo",
        "print(__argv__[0])\nprint(__argv__[1])\n",
    )
    lines = cli("run", vm_program, program, "first").stdout.splitlines()
    assert lines[0].endswith("echo.sp")
    assert lines[1] == "first"


def test_self_hosted_vm_runs_a_program_that_uses_sidecar_names(
    vm_program: Path,
) -> None:
    """tests/test_quine/quine.sp keeps its names in quine.names.json."""
    quine = ROOT / "tests" / "test_quine" / "quine.sp"
    reference = cli("run", quine).stdout
    assert reference.startswith("source = ")
    assert cli("run", vm_program, quine).stdout == reference
