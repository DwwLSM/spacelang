"""Bridge between source text and the traced SpaceLang VM.

Also hosts the source-to-source conversions used by the studio page. Only the
forward direction is deterministic: ``py`` compiles to a Program, a Program
disassembles to ``spasm`` and encodes to ``sp``. There is no Program-to-Python
lowering, so the readable mirror can only be produced by the model and verified
against the assembly.
"""

from __future__ import annotations

import traceback
from typing import Any

from .asm import assemble
from .decoder import decode
from .disasm import disassemble
from .encoder import encode
from .ir import OP
from .pyfront import compile_py
from .vm_trace import TracedVM

_SOURCE_KINDS = ("py", "spasm", "sp")


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


def canon(program) -> list[tuple[int, tuple]]:
    """Semantic fingerprint of a Program.

    ``Instr.line`` and the Program's name/label/debug tables are deliberately
    excluded: they legitimately differ between the two front ends.
    """
    return [(int(instr.op), tuple(instr.args)) for instr in program.instrs]


def convert(source: str, src: str) -> dict[str, Any]:
    """Convert one representation into every deterministically derivable one.

    Returns ``{"ok": bool, "texts": {kind: text}, "error": str | None}``. A
    ``py`` destination never appears: it has no rule-based implementation.
    """
    if src not in _SOURCE_KINDS:
        return {"ok": False, "texts": {}, "error": f"unknown source kind {src!r}"}
    try:
        if src == "py":
            program = compile_py(source)
        elif src == "spasm":
            program = assemble(source)
        else:
            program = decode(source)
    except Exception:
        return {"ok": False, "texts": {}, "error": traceback.format_exc()}

    texts: dict[str, str] = {}
    try:
        if src != "spasm":
            texts["spasm"] = disassemble(program)
        if src != "sp":
            # The name table must be embedded, otherwise the assembly loses
            # every symbol on the way back.
            texts["sp"] = encode(program, include_names=True)
    except Exception:
        return {"ok": False, "texts": {}, "error": traceback.format_exc()}
    return {"ok": True, "texts": texts, "error": None}


def annotate(spasm_src: str) -> dict[str, Any]:
    """Re-render assembly with the ``; line=... spaces=...`` annotations.

    ``disassemble`` always appends the encoded token values as a trailing
    comment; the studio can hide them, and needs a way to bring them back
    without recompiling from a higher-level source.
    """
    try:
        text = disassemble(assemble(spasm_src))
    except Exception:
        return {"ok": False, "text": None, "error": traceback.format_exc()}
    return {"ok": True, "text": text, "error": None}


def _describe(entry: tuple[int, tuple]) -> str:
    try:
        name = OP(entry[0]).name
    except ValueError:
        name = str(entry[0])
    return name if not entry[1] else f"{name} " + " ".join(str(arg) for arg in entry[1])


def _first_difference(want, got) -> dict | None:
    for index, (left, right) in enumerate(zip(want, got)):
        if left != right:
            return {"index": index, "want": _describe(left), "got": _describe(right)}
    if len(want) != len(got):
        longer, shorter = ("assembly", "python") if len(want) > len(got) else ("python", "assembly")
        return {"index": min(len(want), len(got)), "want": f"{longer} continues", "got": f"{shorter} ends"}
    return None


def verify_py(py_src: str, spasm_src: str) -> dict[str, Any]:
    """Check that a proposed Python mirror compiles to the same program.

    Verification uses the assembly, never ``.sp``: the assembly is already part
    of the request and re-encoding it locally would only re-derive the same
    instructions.
    """
    try:
        want = canon(assemble(spasm_src))
    except Exception:
        return {
            "ok": False,
            "error": "assembly_unparsable",
            "detail": traceback.format_exc(),
        }
    try:
        got = canon(compile_py(py_src))
    except Exception:
        return {
            "ok": False,
            "error": "python_unparsable",
            "detail": traceback.format_exc(),
        }
    return {
        "ok": want == got,
        "want_len": len(want),
        "got_len": len(got),
        "first": None if want == got else _first_difference(want, got),
        "error": None if want == got else "not_equivalent",
    }


__all__ = ["trace_program", "convert", "annotate", "verify_py", "canon"]
