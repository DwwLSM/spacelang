from __future__ import annotations

from .errors import EncodingError
from .ir import Instr, OP, Program


def _encode_zigzag(value: int) -> int:
    if value >= 0:
        return 2 * value
    return -2 * value - 1


def decode(value: int) -> int:
    return value // 2 if value % 2 == 0 else -(value + 1) // 2


def encode(program: Program) -> str:
    """Encode a Program back to canonical SpaceLang token stream."""
    lines: list[str] = []
    for instr in program.instrs:
        token_values: list[int] = []
        op_value = int(instr.op)
        token_values.append(op_value)

        for arg in instr.args:
            if isinstance(arg, str):
                raise EncodingError(line=instr.line, ip=0, msg="string arguments must be encoded as code points")
            if arg < 0:
                if instr.op != OP.PUSH_INT:
                    raise EncodingError(line=instr.line, ip=0, msg=f"negative argument {arg!r} not allowed")
                arg = _encode_zigzag(arg)
            token_values.append(arg)

        if instr.op == OP.PUSH_STR:
            count = int(instr.args[0])
            if count < 0:
                raise EncodingError(line=instr.line, ip=0, msg="PUSH_STR length may not be negative")
            chars = instr.args[1:]
            if len(chars) != count:
                raise EncodingError(line=instr.line, ip=0, msg="PUSH_STR payload length mismatch")
            token_values = [op_value, count, *[int(c) for c in chars]]

        if instr.op == OP.PUSH_INT:
            token_values = [op_value, _encode_zigzag(int(instr.args[0]))]

        lines.extend(" " * value + "\n" for value in token_values)

    return "".join(lines)
