from __future__ import annotations

from .errors import ParseError
from .ir import Instr, OP, Program


def _decode_zigzag(value: int) -> int:
    return value // 2 if value % 2 == 0 else -(value + 1) // 2


def _parse_int_value(token_stream: list[int], idx: int) -> tuple[int, int]:
    if idx >= len(token_stream):
        raise ParseError(line=0, ip=idx, msg="missing integer argument")
    return token_stream[idx], idx + 1


def _normalize_tokens(token_stream):
    values: list[int] = []
    for token in token_stream:
        if isinstance(token, tuple):
            values.append(token[0])
        elif isinstance(token, list):
            values.append(token[0])
        else:
            values.append(token)
    return values


def parse(token_stream) -> Program:
    """Parse SpaceLang tokens into a Program.

    The canonical source form is a series of integer tokens, each storing the space
    count of a single value. This parser reconstructs the instruction sequence by
    opcode shape. Accepts either raw ints or (value, line) token tuples.
    """
    token_stream = _normalize_tokens(token_stream)
    instrs: list[Instr] = []
    i = 0
    try_stack: list[tuple[int, int, int, int]] = []

    while i < len(token_stream):
        op_code = token_stream[i]
        i += 1
        if op_code not in range(30):
            raise ParseError(line=0, ip=i - 1, msg=f"unknown opcode {op_code}")

        op = OP(op_code)
        args: list[int | str] = []
        if op in {OP.CALL, OP.CALL_KW, OP.CALL_METHOD, OP.DEF}:
            func_id, i = _parse_int_value(token_stream, i)
            nargs, i = _parse_int_value(token_stream, i)
            args = [func_id, nargs]
        elif op == OP.CALL_OBJ:
            nargs, i = _parse_int_value(token_stream, i)
            args = [nargs]
        elif op in {OP.IMPORT, OP.OP, OP.STACK, OP.LOAD_GLOBAL, OP.STORE_GLOBAL, OP.GET_ATTR, OP.LOAD_ARG, OP.LOAD_LOCAL, OP.STORE_LOCAL, OP.JMP, OP.JZ, OP.JNZ, OP.INDEX, OP.BUILD_LIST, OP.BUILD_TUPLE, OP.CONCAT, OP.PUSH_INT, OP.PUSH_STR, OP.CALL, OP.CALL_KW, OP.CALL_METHOD, OP.DEF, OP.LOAD_ARG, OP.LOAD_LOCAL, OP.STORE_LOCAL, OP.JMP, OP.JZ, OP.JNZ}:
            if op == OP.PUSH_INT:
                value, i = _parse_int_value(token_stream, i)
                args = [_decode_zigzag(value)]
            elif op == OP.PUSH_STR:
                length, i = _parse_int_value(token_stream, i)
                chars: list[int] = []
                for _ in range(length):
                    if i >= len(token_stream):
                        raise ParseError(line=0, ip=i, msg="incomplete PUSH_STR payload")
                    chars.append(token_stream[i])
                    i += 1
                args = [length] + chars
            else:
                value, i = _parse_int_value(token_stream, i)
                args = [value]
        elif op == OP.TRY:
            catch_ip, i = _parse_int_value(token_stream, i)
            finally_ip, i = _parse_int_value(token_stream, i)
            args = [catch_ip, finally_ip]
            try_stack.append((len(instrs), catch_ip, finally_ip, len(instrs)))
        elif op == OP.END_TRY:
            if not try_stack:
                raise ParseError(line=0, ip=i - 1, msg="END_TRY without TRY")
            try_ip, catch_ip, finally_ip, _ = try_stack.pop()
            end_ip = len(instrs) + 1
            try_stack.append((try_ip, catch_ip, finally_ip, end_ip))
        elif op in {OP.NOP, OP.RET, OP.RAISE, OP.END_TRY, OP.SETUP_WITH, OP.HALT}:
            pass

        instrs.append(Instr(op, args, line=0))

    if try_stack:
        raise ParseError(line=0, ip=len(token_stream), msg="TRY without END_TRY")

    # Rebuild try_table and function boundaries in a single pass after parsing.
    funcs: dict[int, tuple[int, int]] = {}
    current_func: tuple[int, int] | None = None
    for idx, instr in enumerate(instrs):
        if instr.op == OP.DEF:
            if current_func is not None:
                raise ParseError(line=0, ip=idx, msg="nested DEF is not allowed")
            func_id = instr.args[0]
            if func_id < 10000:
                raise ParseError(line=0, ip=idx, msg="DEF func_id must be >= 10000")
            current_func = (func_id, idx)
        elif instr.op == OP.HALT and current_func is not None:
            funcs[current_func[0]] = (current_func[1], idx)
            current_func = None
        elif instr.op == OP.DEF and current_func is not None:
            raise ParseError(line=0, ip=idx, msg="nested DEF is not allowed")

    if current_func is not None:
        funcs[current_func[0]] = (current_func[1], len(instrs))

    try_table: list[tuple[int, int, int, int]] = []
    pending_tries: list[tuple[int, int, int, int]] = []
    for idx, instr in enumerate(instrs):
        if instr.op == OP.TRY:
            pending_tries.append((idx, idx + 1, instr.args[0], instr.args[1]))
        elif instr.op == OP.END_TRY:
            if not pending_tries:
                raise ParseError(line=0, ip=idx, msg="END_TRY without TRY")
            try_ip, _, catch_ip, finally_ip = pending_tries.pop()
            try_table.append((try_ip, idx + 1, catch_ip, finally_ip))

    if pending_tries:
        raise ParseError(line=0, ip=len(instrs), msg="TRY without END_TRY")

    return Program(instrs=instrs, names={}, labels={}, funcs=funcs, try_table=try_table)
