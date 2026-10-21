from __future__ import annotations

from .errors import ParseError
from .ir import Instr, OP, Program

MNEMONICS = {
    "NOP": OP.NOP,
    "CALL": OP.CALL,
    "CALL_KW": OP.CALL_KW,
    "CALL_OBJ": OP.CALL_OBJ,
    "IMPORT": OP.IMPORT,
    "OP": OP.OP,
    "STACK": OP.STACK,
    "PUSH_INT": OP.PUSH_INT,
    "PUSH_STR": OP.PUSH_STR,
    "LOAD_GLOBAL": OP.LOAD_GLOBAL,
    "STORE_GLOBAL": OP.STORE_GLOBAL,
    "GET_ATTR": OP.GET_ATTR,
    "CALL_METHOD": OP.CALL_METHOD,
    "INDEX": OP.INDEX,
    "BUILD_LIST": OP.BUILD_LIST,
    "BUILD_TUPLE": OP.BUILD_TUPLE,
    "CONCAT": OP.CONCAT,
    "DEF": OP.DEF,
    "RET": OP.RET,
    "LOAD_ARG": OP.LOAD_ARG,
    "LOAD_LOCAL": OP.LOAD_LOCAL,
    "STORE_LOCAL": OP.STORE_LOCAL,
    "JMP": OP.JMP,
    "JZ": OP.JZ,
    "JNZ": OP.JNZ,
    "RAISE": OP.RAISE,
    "TRY": OP.TRY,
    "END_TRY": OP.END_TRY,
    "SETUP_WITH": OP.SETUP_WITH,
    "HALT": OP.HALT,
}

NAME_OPS = {
    OP.LOAD_GLOBAL,
    OP.STORE_GLOBAL,
    OP.GET_ATTR,
    OP.CALL_METHOD,
}


def _as_int(token: str, line: int) -> int:
    try:
        return int(token, 0)
    except ValueError as exc:  # pragma: no cover - defensive
        raise ParseError(line=line, ip=0, msg=f"invalid integer literal: {token}") from exc


def _parse_string_literal(token: str, line: int) -> list[int]:
    if len(token) < 2 or token[0] != token[-1] or token[0] not in {'"', "'"}:
        raise ParseError(line=line, ip=0, msg=f"invalid string literal: {token}")
    value = token[1:-1]
    out: list[int] = []
    escaped = False
    current = []
    for ch in value:
        if escaped:
            if ch == "n":
                current.append("\n")
            elif ch == "t":
                current.append("\t")
            elif ch == "\\":
                current.append("\\")
            elif ch in {'"', "'"}:
                current.append(ch)
            else:
                current.append(ch)
            escaped = False
        elif ch == "\\":
            escaped = True
        else:
            current.append(ch)
    for ch in current:
        out.append(ord(ch))
    return out


def _register_name(names: dict[str, int], name: str) -> int:
    existing = names.get(name)
    if existing is not None:
        return existing
    next_id = max(names.values(), default=-1) + 1
    names[name] = next_id
    return next_id


def assemble(src: str) -> Program:
    names: dict[str, int] = {}
    labels: dict[str, int] = {}
    instrs: list[Instr] = []
    lines = src.splitlines()

    for line_no, raw in enumerate(lines, start=1):
        text = raw.strip()
        if not text or text.startswith("#") or text.startswith(";"):
            continue
        if text.startswith(".label"):
            parts = text.split(None, 1)
            if len(parts) != 2:
                raise ParseError(line=line_no, ip=0, msg="invalid label syntax")
            labels[parts[1]] = len(instrs)
            continue
        if text == ".enddef":
            continue

        tokens = text.split()
        mnemonic = tokens[0].upper()
        op = MNEMONICS.get(mnemonic)
        if op is None:
            raise ParseError(line=line_no, ip=0, msg=f"unknown mnemonic: {mnemonic}")

        args: list[int | str] = []
        for token in tokens[1:]:
            if token.startswith(("'", '"')) and token.endswith(("'", '"')):
                if op != OP.PUSH_STR:
                    raise ParseError(line=line_no, ip=0, msg="string literal allowed only for PUSH_STR")
                args.extend(_parse_string_literal(token, line_no))
                continue
            try:
                value = int(token, 0)
            except ValueError:
                if op in NAME_OPS:
                    value = _register_name(names, token)
                else:
                    value = token
            args.append(value)

        if op == OP.PUSH_STR:
            if not args:
                raise ParseError(line=line_no, ip=0, msg="PUSH_STR requires a string literal")
            chars = args
            encoded = [len(chars)] + chars
            instrs.append(Instr(OP.PUSH_STR, encoded, line=line_no))
        elif op in {OP.CALL, OP.CALL_KW, OP.CALL_METHOD, OP.DEF} and len(args) == 2:
            instrs.append(Instr(op, args, line=line_no))
        elif op == OP.CALL_OBJ and len(args) == 1:
            instrs.append(Instr(op, args, line=line_no))
        elif op == OP.TRY and len(args) == 2:
            instrs.append(Instr(op, args, line=line_no))
        elif op in {OP.OP, OP.STACK, OP.IMPORT, OP.LOAD_GLOBAL, OP.STORE_GLOBAL, OP.GET_ATTR, OP.INDEX, OP.BUILD_LIST, OP.BUILD_TUPLE, OP.CONCAT, OP.LOAD_ARG, OP.LOAD_LOCAL, OP.STORE_LOCAL, OP.JMP, OP.JZ, OP.JNZ, OP.PUSH_INT} and len(args) == 1:
            instrs.append(Instr(op, args, line=line_no))
        elif op in {OP.NOP, OP.RET, OP.RAISE, OP.END_TRY, OP.SETUP_WITH, OP.HALT} and len(args) == 0:
            instrs.append(Instr(op, [], line=line_no))
        else:
            raise ParseError(line=line_no, ip=0, msg=f"invalid argument count for {mnemonic}")

    for instr in instrs:
        for idx, arg in enumerate(instr.args):
            if isinstance(arg, str) and arg in labels:
                instr.args[idx] = labels[arg]
            elif isinstance(arg, str):
                raise ParseError(line=instr.line, ip=0, msg=f"undefined label: {arg}")

    program = Program(instrs=instrs, names=names, labels=labels)
    return program


__all__ = ["assemble", "MNEMONICS"]
