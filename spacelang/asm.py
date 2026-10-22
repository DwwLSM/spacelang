from __future__ import annotations

import shlex
import re

from .encoder import encode
from .errors import ParseError
from .ir import Instr, OP, Program
from .lexer import tokenize
from .parser import parse

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


def _split_tokens(text: str) -> list[str]:
    lexer = shlex.shlex(text, posix=False)
    lexer.whitespace_split = True
    lexer.commenters = "#;"
    return list(lexer)


def _annotated_line(raw: str, fallback: int) -> int:
    match = re.search(r";\s*line=(\d+)\s+spaces=[0-9,]+\s*$", raw)
    return int(match.group(1)) if match else fallback


def assemble(src: str) -> Program:
    names: dict[str, int] = {}
    labels: dict[str, int] = {}
    instrs: list[Instr] = []
    enddef_markers: list[tuple[int, int]] = []
    lines = src.splitlines()

    for line_no, raw in enumerate(lines, start=1):
        tokens = _split_tokens(raw.strip())
        if not tokens or tokens[0].lower() != ".name":
            continue
        if len(tokens) != 2 or "=" not in tokens[1]:
            raise ParseError(line=line_no, ip=0, msg="invalid .name syntax; expected .name NAME=ID")
        name, separator, raw_id = tokens[1].partition("=")
        if not name or not separator:
            raise ParseError(line=line_no, ip=0, msg="invalid .name syntax; expected .name NAME=ID")
        name_id = _as_int(raw_id, line_no)
        if name_id < 0 or name in names or name_id in names.values():
            raise ParseError(line=line_no, ip=0, msg="duplicate or negative .name entry")
        names[name] = name_id

    for line_no, raw in enumerate(lines, start=1):
        source_line = _annotated_line(raw, line_no)
        text = raw.strip()
        if not text:
            continue
        tokens = _split_tokens(text)
        if not tokens:
            continue
        directive = tokens[0].lower()
        if directive == ".label":
            if len(tokens) != 2:
                raise ParseError(line=line_no, ip=0, msg="invalid label syntax")
            if tokens[1] in labels:
                raise ParseError(line=line_no, ip=len(instrs), msg=f"duplicate label: {tokens[1]}")
            labels[tokens[1]] = len(instrs)
            continue
        if directive == ".name":
            continue
        if directive == ".enddef":
            if len(tokens) != 1:
                raise ParseError(line=line_no, ip=len(instrs), msg="invalid .enddef syntax")
            enddef_markers.append((len(instrs), line_no))
            continue

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
            instrs.append(Instr(OP.PUSH_STR, encoded, line=source_line))
        elif op == OP.CALL_KW and len(args) == 3:
            instrs.append(Instr(op, args, line=source_line))
        elif op in {OP.CALL, OP.CALL_METHOD, OP.DEF} and len(args) == 2:
            instrs.append(Instr(op, args, line=source_line))
        elif op == OP.CALL_OBJ and len(args) == 1:
            instrs.append(Instr(op, args, line=source_line))
        elif op == OP.TRY and len(args) == 2:
            instrs.append(Instr(op, args, line=source_line))
        elif op in {OP.OP, OP.STACK, OP.IMPORT, OP.LOAD_GLOBAL, OP.STORE_GLOBAL, OP.GET_ATTR, OP.INDEX, OP.BUILD_LIST, OP.BUILD_TUPLE, OP.CONCAT, OP.LOAD_ARG, OP.LOAD_LOCAL, OP.STORE_LOCAL, OP.JMP, OP.JZ, OP.JNZ, OP.PUSH_INT} and len(args) == 1:
            instrs.append(Instr(op, args, line=source_line))
        elif op in {OP.NOP, OP.RET, OP.RAISE, OP.END_TRY, OP.SETUP_WITH, OP.HALT} and len(args) == 0:
            instrs.append(Instr(op, [], line=source_line))
        else:
            raise ParseError(line=line_no, ip=0, msg=f"invalid argument count for {mnemonic}")

    for instr in instrs:
        for idx, arg in enumerate(instr.args):
            if isinstance(arg, str) and arg in labels:
                instr.args[idx] = labels[arg]
            elif isinstance(arg, str):
                raise ParseError(line=instr.line, ip=0, msg=f"undefined label: {arg}")

    definitions = [idx for idx, instr in enumerate(instrs) if instr.op == OP.DEF]
    valid_enddef_positions = set()
    for position, def_ip in enumerate(definitions):
        next_def = definitions[position + 1] if position + 1 < len(definitions) else len(instrs)
        end_ip = next(
            (idx for idx in range(def_ip + 1, next_def) if instrs[idx].op == OP.HALT),
            next_def,
        )
        valid_enddef_positions.add(end_ip)
    seen_enddefs: set[int] = set()
    for marker_ip, line_no in enddef_markers:
        if marker_ip not in valid_enddef_positions or marker_ip in seen_enddefs:
            raise ParseError(line=line_no, ip=marker_ip, msg=".enddef does not match a DEF boundary")
        seen_enddefs.add(marker_ip)

    source_instrs = instrs
    encoded_program = Program(instrs=source_instrs, names=names, labels=labels)
    parsed = parse(tokenize(encode(encoded_program)))

    parse_instrs = list(source_instrs)
    if not parse_instrs or parse_instrs[-1].op != OP.HALT:
        parse_instrs.append(Instr(OP.HALT))
    definitions = [idx for idx, instr in enumerate(parse_instrs) if instr.op == OP.DEF]
    implicit_returns: list[tuple[int, int]] = []
    for position, def_ip in enumerate(definitions):
        next_def = definitions[position + 1] if position + 1 < len(definitions) else len(parse_instrs)
        halt_ip = next(
            (idx for idx in range(def_ip + 1, next_def) if parse_instrs[idx].op == OP.HALT),
            next_def,
        )
        if halt_ip == def_ip + 1 or parse_instrs[halt_ip - 1].op != OP.RET:
            implicit_returns.append((halt_ip, parse_instrs[def_ip].line))

    def remap(ip: int) -> int:
        return ip + 2 * sum(position <= ip for position, _ in implicit_returns)

    original_lines = {idx: instr.line for idx, instr in enumerate(parse_instrs)}
    for old_ip, line in original_lines.items():
        parsed.instrs[remap(old_ip)].line = line
    for position, line in implicit_returns:
        parsed.instrs[position + 2 * sum(previous < position for previous, _ in implicit_returns)].line = line
        parsed.instrs[position + 2 * sum(previous < position for previous, _ in implicit_returns) + 1].line = line

    return Program(
        instrs=parsed.instrs,
        names=names,
        labels={name: remap(ip) for name, ip in labels.items()},
        funcs=parsed.funcs,
        try_table=parsed.try_table,
    )


__all__ = ["assemble", "MNEMONICS"]
