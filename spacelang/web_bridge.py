"""Bridge between source text and the traced SpaceLang VM."""

from __future__ import annotations

import traceback
from typing import Any

from .asm import assemble
from .decoder import decode
from .pyfront import compile_py
from .vm_trace import TracedVM


def trace_program(
    source: str,
    is_asm: bool = True,
    is_sp: bool = False,
) -> dict[str, Any]:
    try:
        if is_sp:
            program = decode(source)
        elif is_asm:
            program = assemble(source)
        else:
            program = compile_py(source)
        vm = TracedVM(program)
        vm.run()
        return {"ok": True, "trace": vm.get_trace(), "error": None}
    except Exception:
        return {"ok": False, "trace": [], "error": traceback.format_exc()}


__all__ = ["trace_program"]
