from __future__ import annotations

from .errors import ParseError
from .ir import Instr, OP, Program


def _decode_zigzag(value: int) -> int:
    return value // 2 if value % 2 == 0 else -(value + 1) // 2


def _parse_int_value(token_stream: list[int], idx: int, line: int = 0) -> tuple[int, int]:
    if idx >= len(token_stream):
        raise ParseError(line=line, ip=idx, msg="missing integer argument")
    value = token_stream[idx]
    if not isinstance(value, int) or value < 0:
        raise ParseError(line=line, ip=idx, msg="arguments must be non-negative integers")
    return value, idx + 1


def _normalize_tokens(token_stream):
    values: list[int] = []
    lines: list[int] = []
    for token in token_stream:
        if isinstance(token, tuple):
            values.append(token[0])
            lines.append(token[1])
        elif isinstance(token, list):
            values.append(token[0])
            lines.append(token[1] if len(token) > 1 else 0)
        else:
            values.append(token)
            lines.append(0)
    return values, lines


def parse(token_stream) -> Program:
    """Parse SpaceLang tokens into a Program.

    The canonical source form is a series of integer tokens, each storing the space
    count of a single value. This parser reconstructs the instruction sequence by
    opcode shape. Accepts either raw ints or (value, line) token tuples.
    """
    token_stream, token_lines = _normalize_tokens(token_stream)
    instrs: list[Instr] = []
    i = 0

    while i < len(token_stream):
        op_index = i
        op_code = token_stream[i]
        op_line = token_lines[i]
        i += 1
        if op_code not in range(30):
            raise ParseError(line=op_line, ip=op_index, msg=f"unknown opcode {op_code}")

        op = OP(op_code)
        args: list[int | str] = []
        if op == OP.CALL_KW:
            func_id, i = _parse_int_value(token_stream, i, op_line)
            npos, i = _parse_int_value(token_stream, i, op_line)
            nkw, i = _parse_int_value(token_stream, i, op_line)
            args = [func_id, npos, nkw]
        elif op in {OP.CALL, OP.CALL_METHOD, OP.DEF}:
            func_id, i = _parse_int_value(token_stream, i, op_line)
            nargs, i = _parse_int_value(token_stream, i, op_line)
            args = [func_id, nargs]
        elif op == OP.CALL_OBJ:
            nargs, i = _parse_int_value(token_stream, i, op_line)
            args = [nargs]
        elif op in {OP.IMPORT, OP.OP, OP.STACK, OP.LOAD_GLOBAL, OP.STORE_GLOBAL, OP.GET_ATTR, OP.LOAD_ARG, OP.LOAD_LOCAL, OP.STORE_LOCAL, OP.JMP, OP.JZ, OP.JNZ, OP.INDEX, OP.BUILD_LIST, OP.BUILD_TUPLE, OP.CONCAT, OP.PUSH_INT, OP.PUSH_STR, OP.CALL, OP.CALL_KW, OP.CALL_METHOD, OP.DEF, OP.LOAD_ARG, OP.LOAD_LOCAL, OP.STORE_LOCAL, OP.JMP, OP.JZ, OP.JNZ}:
            if op == OP.PUSH_INT:
                value, i = _parse_int_value(token_stream, i, op_line)
                args = [_decode_zigzag(value)]
            elif op == OP.PUSH_STR:
                length, i = _parse_int_value(token_stream, i, op_line)
                chars: list[int] = []
                for _ in range(length):
                    if i >= len(token_stream):
                        raise ParseError(line=op_line, ip=op_index, msg="incomplete PUSH_STR payload")
                    chars.append(token_stream[i])
                    i += 1
                args = [length] + chars
            else:
                value, i = _parse_int_value(token_stream, i, op_line)
                args = [value]
        elif op == OP.TRY:
            catch_ip, i = _parse_int_value(token_stream, i, op_line)
            finally_ip, i = _parse_int_value(token_stream, i, op_line)
            args = [catch_ip, finally_ip]
        elif op in {OP.NOP, OP.RET, OP.RAISE, OP.END_TRY, OP.SETUP_WITH, OP.HALT}:
            pass

        instrs.append(Instr(op, args, line=op_line))

    definition_indices = [idx for idx, instr in enumerate(instrs) if instr.op == OP.DEF]
    implicit_returns: list[int] = []
    for def_position, def_ip in enumerate(definition_indices):
        next_def_ip = (
            definition_indices[def_position + 1]
            if def_position + 1 < len(definition_indices)
            else len(instrs)
        )
        halt_ip = next(
            (idx for idx in range(def_ip + 1, next_def_ip) if instrs[idx].op == OP.HALT),
            next_def_ip,
        )
        if halt_ip == def_ip + 1 or instrs[halt_ip - 1].op != OP.RET:
            implicit_returns.append(halt_ip)

    for insertion_ip in reversed(implicit_returns):
        for instr in instrs:
            if instr.op in {OP.JMP, OP.JZ, OP.JNZ} and int(instr.args[0]) >= insertion_ip:
                instr.args[0] = int(instr.args[0]) + 2
            elif instr.op == OP.TRY:
                instr.args[0] = int(instr.args[0]) + (2 if int(instr.args[0]) >= insertion_ip else 0)
                if int(instr.args[1]) != 0 and int(instr.args[1]) >= insertion_ip:
                    instr.args[1] = int(instr.args[1]) + 2
        def_line = next(
            (instr.line for instr in reversed(instrs[:insertion_ip]) if instr.op == OP.DEF),
            0,
        )
        instrs[insertion_ip:insertion_ip] = [
            Instr(OP.PUSH_INT, [0], line=def_line),
            Instr(OP.RET, line=def_line),
        ]

    funcs: dict[int, tuple[int, int]] = {}
    definition_indices = [idx for idx, instr in enumerate(instrs) if instr.op == OP.DEF]
    for def_position, def_ip in enumerate(definition_indices):
        func_id = int(instrs[def_ip].args[0])
        if func_id < 10000:
            raise ParseError(line=instrs[def_ip].line, ip=def_ip, msg="DEF func_id must be >= 10000")
        if func_id in funcs:
            raise ParseError(line=instrs[def_ip].line, ip=def_ip, msg=f"duplicate DEF func_id {func_id}")
        end_ip = (
            definition_indices[def_position + 1]
            if def_position + 1 < len(definition_indices)
            else len(instrs)
        )
        halt_ip = next(
            (idx for idx in range(def_ip + 1, end_ip) if instrs[idx].op == OP.HALT),
            end_ip,
        )
        funcs[func_id] = (def_ip + 1, halt_ip)

    try_table: list[tuple[int, int, int, int]] = []
    pending_tries: list[list[int]] = []
    for idx, instr in enumerate(instrs):
        if instr.op == OP.TRY:
            catch_ip, finally_ip = map(int, instr.args)
            expected_ends = 1 + int(catch_ip != 0) + int(finally_ip != 0)
            pending_tries.append([idx, expected_ends, catch_ip, finally_ip])
        elif instr.op == OP.END_TRY:
            if not pending_tries:
                raise ParseError(line=instr.line, ip=idx, msg="END_TRY without TRY")
            active = pending_tries[-1]
            active[1] -= 1
            if active[1] == 0:
                try_ip, _, catch_ip, finally_ip = pending_tries.pop()
                try_table.append((try_ip, idx + 1, catch_ip, finally_ip))

    if pending_tries:
        last_line = instrs[-1].line if instrs else 0
        raise ParseError(line=last_line, ip=len(instrs), msg="TRY without END_TRY")

    return Program(instrs=instrs, names={}, labels={}, funcs=funcs, try_table=try_table)
