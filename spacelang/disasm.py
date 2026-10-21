from __future__ import annotations

from .ir import OP, Program

OP_NAMES = {op.value: op.name for op in OP}


def _string_literal(value: list[int]) -> str:
    text = "".join(chr(code) for code in value)
    return '"' + text.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n') + '"'


def disassemble(program: Program) -> str:
    reverse_names = {index: name for name, index in program.names.items()}
    labels = {idx: name for name, idx in program.labels.items()}
    lines: list[str] = []

    for idx, instr in enumerate(program.instrs):
        if idx in labels:
            lines.append(f".label {labels[idx]}")
        op_name = OP_NAMES.get(int(instr.op), str(int(instr.op)))
        rendered: list[str] = []
        for arg in instr.args:
            if instr.op in {OP.LOAD_GLOBAL, OP.STORE_GLOBAL, OP.GET_ATTR, OP.CALL_METHOD}:
                rendered.append(reverse_names.get(int(arg), str(arg)))
            elif instr.op == OP.PUSH_STR and arg == instr.args[0]:
                chars = instr.args[1:]
                rendered.append(_string_literal(chars))
                break
            else:
                rendered.append(str(arg))
        if instr.op == OP.PUSH_STR:
            payload = instr.args[1:]
            rendered = [_string_literal(payload)]
        if instr.op in {OP.JMP, OP.JZ, OP.JNZ}:
            target = instr.args[0]
            rendered = [labels.get(int(target), str(target))]
        if instr.op == OP.TRY:
            rendered = [str(instr.args[0]), str(instr.args[1])]
        line = f"{op_name}"
        if rendered:
            line += " " + " ".join(rendered)
        lines.append(line)

    return "\n".join(lines) + ("\n" if lines else "")


def disasm(program: Program) -> str:
    return disassemble(program)


__all__ = ["disassemble", "disasm"]
