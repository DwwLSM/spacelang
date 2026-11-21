"""CLI engine selection: ``auto`` prefers the native engine and degrades cleanly.

Making the native engine the default is only safe if a missing extension costs a
warning instead of breaking ``spacelang run``, so both halves are pinned here.
"""

from __future__ import annotations

import sys

from spacelang import main as cli
from spacelang.vm_cpp import VM as CppVM
from spacelang.vm_py import VM as PythonVM


def test_default_engine_is_auto() -> None:
    args = cli._build_parser().parse_args(["run", "program.sp"])
    assert args.engine == "auto"


def test_auto_prefers_the_native_engine() -> None:
    assert cli._select_vm("auto") is CppVM


def test_explicit_engines_are_respected() -> None:
    assert cli._select_vm("py") is PythonVM
    assert cli._select_vm("cpp") is CppVM


def test_auto_falls_back_when_the_extension_is_missing(monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli, "_warned_missing_native", False)
    monkeypatch.setitem(sys.modules, "spacelang.vm_cpp", None)

    assert cli._select_vm("auto") is PythonVM
    assert "using the Python engine" in capsys.readouterr().err


def test_fallback_warning_is_printed_once(monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli, "_warned_missing_native", False)
    monkeypatch.setitem(sys.modules, "spacelang.vm_cpp", None)

    cli._select_vm("auto")
    cli._select_vm("auto")

    assert capsys.readouterr().err.count("using the Python engine") == 1


def test_explicit_cpp_still_fails_loudly_when_missing(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "spacelang.vm_cpp", None)

    try:
        cli._select_vm("cpp")
    except ImportError:
        return
    raise AssertionError("explicit --engine cpp must not fall back silently")
