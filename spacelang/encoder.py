from __future__ import annotations

from .errors import EncodingError
from .ir import Instr, OP, Program

MAX_LINE = 65535
MAX_STRING_CHUNK = 1000


def _encode_zigzag(value: int) -> int:
    if value >= 0:
        return 2 * value
    return -2 * value - 1


def decode(value: int) -> int:
    return value // 2 if value % 2 == 0 else -(value + 1) // 2


def encode(program: Program) -> str:
    """Encode a Program back to canonical SpaceLang token stream."""
    instrs = list(program.instrs)
    if not instrs or instrs[-1].op != OP.HALT:
        instrs.append(Instr(OP.HALT))

    lines: list[str] = []
    for ip, instr in enumerate(instrs):
        try:
            op = OP(instr.op)
        except ValueError as exc:
            raise EncodingError(line=instr.line, ip=ip, msg=f"unknown opcode {instr.op}") from exc

        expected_args = {
            OP.NOP: 0,
            OP.CALL: 2,
            OP.CALL_KW: 3,
            OP.CALL_OBJ: 1,
            OP.IMPORT: 1,
            OP.OP: 1,
            OP.STACK: 1,
            OP.PUSH_INT: 1,
            OP.LOAD_GLOBAL: 1,
            OP.STORE_GLOBAL: 1,
            OP.GET_ATTR: 1,
            OP.CALL_METHOD: 2,
            OP.INDEX: 1,
            OP.BUILD_LIST: 1,
            OP.BUILD_TUPLE: 1,
            OP.CONCAT: 1,
            OP.DEF: 2,
            OP.RET: 0,
            OP.LOAD_ARG: 1,
            OP.LOAD_LOCAL: 1,
            OP.STORE_LOCAL: 1,
            OP.JMP: 1,
            OP.JZ: 1,
            OP.JNZ: 1,
            OP.RAISE: 0,
            OP.TRY: 2,
            OP.END_TRY: 0,
            OP.SETUP_WITH: 0,
            OP.HALT: 0,
        }
        if op != OP.PUSH_STR and len(instr.args) != expected_args[op]:
            raise EncodingError(line=instr.line, ip=ip, msg=f"invalid argument count for {op.name}")

        token_values: list[int] = []
        op_value = int(op)
        token_values.append(op_value)

        for arg in instr.args:
            if type(arg) is not int:
                raise EncodingError(line=instr.line, ip=ip, msg="instruction arguments must be integers")
            if arg < 0:
                if op != OP.PUSH_INT:
                    raise EncodingError(line=instr.line, ip=ip, msg=f"negative argument {arg!r} not allowed")
                arg = _encode_zigzag(arg)
            token_values.append(arg)

        if op == OP.PUSH_INT:
            value = int(instr.args[0])
            if not -(1 << 63) <= value < (1 << 63):
                raise EncodingError(line=instr.line, ip=ip, msg="PUSH_INT value is outside int64 range")
            token_values = [op_value, _encode_zigzag(value)]

        if op == OP.PUSH_STR:
            if not instr.args:
                raise EncodingError(line=instr.line, ip=ip, msg="PUSH_STR requires a length")
            if type(instr.args[0]) is not int:
                raise EncodingError(line=instr.line, ip=ip, msg="PUSH_STR length must be an integer")
            count = int(instr.args[0])
            if count < 0:
                raise EncodingError(line=instr.line, ip=ip, msg="PUSH_STR length may not be negative")
            chars = instr.args[1:]
            if len(chars) != count:
                raise EncodingError(line=instr.line, ip=ip, msg="PUSH_STR payload length mismatch")
            if count > MAX_STRING_CHUNK:
                raise EncodingError(line=instr.line, ip=ip, msg=f"PUSH_STR length exceeds {MAX_STRING_CHUNK}")
            if any(not isinstance(char, int) or char < 0 or char > MAX_LINE for char in chars):
                raise EncodingError(line=instr.line, ip=ip, msg=f"PUSH_STR code points must be between 0 and {MAX_LINE}")
            token_values = [op_value, count, *[int(c) for c in chars]]

        if any(value < 0 or value > MAX_LINE for value in token_values):
            raise EncodingError(line=instr.line, ip=ip, msg=f"token exceeds MAX_LINE ({MAX_LINE})")

        lines.extend(" " * value + "\n" for value in token_values)

    return "".join(lines)
