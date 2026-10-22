from __future__ import annotations

import argparse
import ast
import gzip
import json
import os
from pathlib import Path
import re
import sys
import tokenize

from .encoder import encode
from .errors import EncodingError, ParseError
from .ir import Instr, OP, Program
from .lexer import tokenize as tokenize_space
from .parser import parse


_HOOK_NAMES = (
    "__file__",
    "os",
    "path",
    "__quine_source",
    "__quine_root",
    "__quine_extension",
    "__quine_output",
    "__quine_file",
    "__quine_data",
    "__quine_sidecar_source",
    "__quine_sidecar_output",
    "__quine_sidecar_data",
    "splitext",
    "read",
    "write",
    "close",
)
_HOOK_NAME_IDS = {name: index for index, name in enumerate(_HOOK_NAMES)}


def _push_string(value: str) -> Instr:
    codepoints = [ord(character) for character in value]
    return Instr(OP.PUSH_STR, [len(codepoints), *codepoints])


def _hook_instruction(op: OP, *args: int) -> Instr:
    return Instr(op, list(args))


_HOOK_INSTRS = (
    _hook_instruction(OP.LOAD_GLOBAL, _HOOK_NAME_IDS["__file__"]),
    _hook_instruction(OP.STORE_GLOBAL, _HOOK_NAME_IDS["__quine_source"]),
    _hook_instruction(OP.IMPORT, 2),
    _hook_instruction(OP.STORE_GLOBAL, _HOOK_NAME_IDS["os"]),
    _hook_instruction(OP.LOAD_GLOBAL, _HOOK_NAME_IDS["os"]),
    _hook_instruction(OP.GET_ATTR, _HOOK_NAME_IDS["path"]),
    _hook_instruction(OP.LOAD_GLOBAL, _HOOK_NAME_IDS["__quine_source"]),
    _hook_instruction(OP.CALL_METHOD, _HOOK_NAME_IDS["splitext"], 1),
    _hook_instruction(OP.STACK, 1),
    _hook_instruction(OP.PUSH_INT, 0),
    _hook_instruction(OP.INDEX, 0),
    _hook_instruction(OP.STORE_GLOBAL, _HOOK_NAME_IDS["__quine_root"]),
    _hook_instruction(OP.PUSH_INT, 1),
    _hook_instruction(OP.INDEX, 0),
    _hook_instruction(OP.STORE_GLOBAL, _HOOK_NAME_IDS["__quine_extension"]),
    _hook_instruction(OP.LOAD_GLOBAL, _HOOK_NAME_IDS["__quine_root"]),
    _push_string(".copy"),
    _hook_instruction(OP.LOAD_GLOBAL, _HOOK_NAME_IDS["__quine_extension"]),
    _hook_instruction(OP.CONCAT, 3),
    _hook_instruction(OP.STORE_GLOBAL, _HOOK_NAME_IDS["__quine_output"]),
    _hook_instruction(OP.LOAD_GLOBAL, _HOOK_NAME_IDS["__quine_source"]),
    _push_string("rb"),
    _hook_instruction(OP.CALL, 10, 2),
    _hook_instruction(OP.STORE_GLOBAL, _HOOK_NAME_IDS["__quine_file"]),
    _hook_instruction(OP.LOAD_GLOBAL, _HOOK_NAME_IDS["__quine_file"]),
    _hook_instruction(OP.CALL_METHOD, _HOOK_NAME_IDS["read"], 0),
    _hook_instruction(OP.STORE_GLOBAL, _HOOK_NAME_IDS["__quine_data"]),
    _hook_instruction(OP.LOAD_GLOBAL, _HOOK_NAME_IDS["__quine_file"]),
    _hook_instruction(OP.CALL_METHOD, _HOOK_NAME_IDS["close"], 0),
    _hook_instruction(OP.STACK, 3),
    _hook_instruction(OP.LOAD_GLOBAL, _HOOK_NAME_IDS["__quine_output"]),
    _push_string("wb"),
    _hook_instruction(OP.CALL, 10, 2),
    _hook_instruction(OP.STORE_GLOBAL, _HOOK_NAME_IDS["__quine_file"]),
    _hook_instruction(OP.LOAD_GLOBAL, _HOOK_NAME_IDS["__quine_file"]),
    _hook_instruction(OP.LOAD_GLOBAL, _HOOK_NAME_IDS["__quine_data"]),
    _hook_instruction(OP.CALL_METHOD, _HOOK_NAME_IDS["write"], 1),
    _hook_instruction(OP.STACK, 3),
    _hook_instruction(OP.LOAD_GLOBAL, _HOOK_NAME_IDS["__quine_file"]),
    _hook_instruction(OP.CALL_METHOD, _HOOK_NAME_IDS["close"], 0),
    _hook_instruction(OP.STACK, 3),
    _hook_instruction(OP.LOAD_GLOBAL, _HOOK_NAME_IDS["__quine_root"]),
    _push_string(".names.json"),
    _hook_instruction(OP.CONCAT, 2),
    _hook_instruction(OP.STORE_GLOBAL, _HOOK_NAME_IDS["__quine_sidecar_source"]),
    _hook_instruction(OP.LOAD_GLOBAL, _HOOK_NAME_IDS["__quine_root"]),
    _push_string(".copy.names.json"),
    _hook_instruction(OP.CONCAT, 2),
    _hook_instruction(OP.STORE_GLOBAL, _HOOK_NAME_IDS["__quine_sidecar_output"]),
    _hook_instruction(OP.LOAD_GLOBAL, _HOOK_NAME_IDS["__quine_sidecar_source"]),
    _push_string("rb"),
    _hook_instruction(OP.CALL, 10, 2),
    _hook_instruction(OP.STORE_GLOBAL, _HOOK_NAME_IDS["__quine_file"]),
    _hook_instruction(OP.LOAD_GLOBAL, _HOOK_NAME_IDS["__quine_file"]),
    _hook_instruction(OP.CALL_METHOD, _HOOK_NAME_IDS["read"], 0),
    _hook_instruction(OP.STORE_GLOBAL, _HOOK_NAME_IDS["__quine_sidecar_data"]),
    _hook_instruction(OP.LOAD_GLOBAL, _HOOK_NAME_IDS["__quine_file"]),
    _hook_instruction(OP.CALL_METHOD, _HOOK_NAME_IDS["close"], 0),
    _hook_instruction(OP.STACK, 3),
    _hook_instruction(OP.LOAD_GLOBAL, _HOOK_NAME_IDS["__quine_sidecar_output"]),
    _push_string("wb"),
    _hook_instruction(OP.CALL, 10, 2),
    _hook_instruction(OP.STORE_GLOBAL, _HOOK_NAME_IDS["__quine_file"]),
    _hook_instruction(OP.LOAD_GLOBAL, _HOOK_NAME_IDS["__quine_file"]),
    _hook_instruction(OP.LOAD_GLOBAL, _HOOK_NAME_IDS["__quine_sidecar_data"]),
    _hook_instruction(OP.CALL_METHOD, _HOOK_NAME_IDS["write"], 1),
    _hook_instruction(OP.STACK, 3),
    _hook_instruction(OP.LOAD_GLOBAL, _HOOK_NAME_IDS["__quine_file"]),
    _hook_instruction(OP.CALL_METHOD, _HOOK_NAME_IDS["close"], 0),
    _hook_instruction(OP.STACK, 3),
)


def _load_name_table(src: Path, referenced_ids: set[int]) -> dict[str, int]:
    sidecar = src.with_suffix(".names.json")
    if sidecar.exists():
        try:
            data = json.loads(sidecar.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise EncodingError(line=0, ip=0, msg=f"invalid name table {sidecar}: {exc}") from exc
        if not isinstance(data, dict) or any(
            not isinstance(name, str) or not isinstance(name_id, int) or name_id < 0
            for name, name_id in data.items()
        ):
            raise EncodingError(line=0, ip=0, msg=f"invalid name table {sidecar}")
        names = dict(data)
    else:
        names = {}

    known_ids = set(names.values())
    for name_id in sorted(referenced_ids - known_ids):
        names[f"__unknown_name_{name_id}"] = name_id
    return names


def _referenced_name_ids(program: Program) -> set[int]:
    name_ops = {OP.LOAD_GLOBAL, OP.STORE_GLOBAL, OP.GET_ATTR, OP.CALL_METHOD}
    return {
        int(instr.args[0])
        for instr in program.instrs
        if instr.op in name_ops and instr.args
    }


def _shift_program(program: Program, instruction_offset: int, name_offset: int) -> list[Instr]:
    shifted: list[Instr] = []
    name_ops = {OP.LOAD_GLOBAL, OP.STORE_GLOBAL, OP.GET_ATTR, OP.CALL_METHOD}
    jump_ops = {OP.JMP, OP.JZ, OP.JNZ}
    for instr in program.instrs:
        args = list(instr.args)
        if instr.op in name_ops:
            args[0] = int(args[0]) + name_offset
        elif instr.op in jump_ops:
            args[0] = int(args[0]) + instruction_offset
        elif instr.op == OP.TRY:
            if int(args[0]) != 0:
                args[0] = int(args[0]) + instruction_offset
            if int(args[1]) != 0:
                args[1] = int(args[1]) + instruction_offset
        shifted.append(Instr(instr.op, args, line=instr.line))
    return shifted


def _space_quine(src: Path, dst: Path, data: bytes) -> None:
    if src.suffix.lower() == ".spz":
        try:
            data = gzip.decompress(data)
        except (OSError, EOFError) as exc:
            raise EncodingError(line=0, ip=0, msg=f"invalid gzip SpaceLang source: {exc}") from exc
    try:
        token_stream = tokenize_space(data.decode("ascii"))
        original = parse(token_stream)
    except (UnicodeDecodeError, ParseError) as exc:
        raise EncodingError(line=0, ip=0, msg=f"invalid SpaceLang source: {exc}") from exc

    referenced_ids = _referenced_name_ids(original)
    source_names = _load_name_table(src, referenced_ids)
    name_offset = max(source_names.values(), default=-1) + 1
    instruction_offset = len(_HOOK_INSTRS)
    shifted_instrs = _shift_program(original, instruction_offset, 0)
    instrs = [
        Instr(
            instr.op,
            [
                int(arg) + name_offset
                if instr.op in {OP.LOAD_GLOBAL, OP.STORE_GLOBAL, OP.GET_ATTR, OP.CALL_METHOD}
                and index == 0
                else arg
                for index, arg in enumerate(instr.args)
            ],
            line=instr.line,
        )
        for instr in _HOOK_INSTRS
    ]
    instrs.extend(shifted_instrs)

    names = dict(source_names)
    names.update({name: name_id + name_offset for name, name_id in _HOOK_NAME_IDS.items()})
    labels = {name: ip + instruction_offset for name, ip in original.labels.items()}
    funcs = {
        func_id: (entry_ip + instruction_offset, end_ip + instruction_offset)
        for func_id, (entry_ip, end_ip) in original.funcs.items()
    }
    try_table = [
        (
            try_ip + instruction_offset,
            end_ip + instruction_offset,
            catch_ip + instruction_offset if catch_ip else 0,
            finally_ip + instruction_offset if finally_ip else 0,
        )
        for try_ip, end_ip, catch_ip, finally_ip in original.try_table
    ]
    encoded = encode(Program(instrs, names, labels, funcs, try_table)).encode("ascii")
    if dst.suffix.lower() == ".spz":
        encoded = gzip.compress(encoded, mtime=0)
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(encoded)
    dst.with_suffix(".names.json").write_text(
        json.dumps(names, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _same_file(src: Path, dst: Path) -> bool:
    if src.resolve() == dst.resolve():
        return True
    try:
        return os.path.samefile(src, dst)
    except FileNotFoundError:
        return False


def _python_encoding(data: bytes) -> str:
    import io

    encoding, _ = tokenize.detect_encoding(io.BytesIO(data).readline)
    return encoding


def _python_quine_source(data: bytes, encoding: str) -> bytes:
    source = data.decode(encoding)
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        raise EncodingError(
            line=exc.lineno or 0,
            ip=0,
            msg=f"source is not valid Python: {exc.msg}",
        ) from exc

    reserved_names = {
        node.id for node in ast.walk(tree) if isinstance(node, ast.Name)
    }
    reserved_names.update(
        node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    )
    suffix = 0
    while True:
        helper_name = f"__spacelang_quine_hook_{suffix}"
        if helper_name not in reserved_names:
            break
        suffix += 1

    insert_after = 0
    body = tree.body
    body_index = 0
    lines = source.splitlines(keepends=True)
    for line_number, line in enumerate(lines[:2], start=1):
        if (line_number == 1 and line.startswith("#!")) or re.search(
            r"coding[:=]\s*[-\w.]+", line
        ):
            insert_after = line_number
    if (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    ):
        insert_after = body[0].end_lineno or body[0].lineno
        body_index = 1
    for node in body[body_index:]:
        if isinstance(node, ast.ImportFrom) and node.module == "__future__":
            insert_after = max(insert_after, node.end_lineno or node.lineno)
        else:
            break

    newline = "\r\n" if "\r\n" in source else "\n"
    hook = newline.join(
        (
            f"def {helper_name}():",
            "    import os",
            "    source = __file__",
            "    root, extension = os.path.splitext(source)",
            "    with open(source, 'rb') as source_file:",
            "        contents = source_file.read()",
            "    with open(root + '.copy' + extension, 'wb') as copy_file:",
            "        copy_file.write(contents)",
            f"{helper_name}()",
            f"del {helper_name}",
            "",
        )
    )
    offset = sum(len(line) for line in lines[:insert_after])
    prefix = source[:offset]
    if prefix and not prefix.endswith(("\n", "\r")):
        hook = newline + hook
    transformed = prefix + hook + source[offset:]
    return transformed.encode(encoding)


def quine(src: str | os.PathLike[str], dst: str | os.PathLike[str]) -> None:
    source_path = Path(src)
    destination_path = Path(dst)
    if _same_file(source_path, destination_path):
        raise ValueError("quine source and destination must be different files")

    data = source_path.read_bytes()
    suffix = source_path.suffix.lower()
    if suffix in {".sp", ".spz"}:
        _space_quine(source_path, destination_path, data)
        return
    if suffix != ".py":
        whitespace_bytes = set(data) <= {0x20, 0x0A, 0x0D}
        if whitespace_bytes:
            _space_quine(source_path, destination_path, data)
            return

    try:
        encoding = _python_encoding(data)
        transformed = _python_quine_source(data, encoding)
    except (SyntaxError, LookupError, UnicodeError, tokenize.TokenError) as exc:
        raise EncodingError(line=0, ip=0, msg=f"unable to identify source language: {exc}") from exc

    destination_path.parent.mkdir(parents=True, exist_ok=True)
    destination_path.write_bytes(transformed)


def _in_place(src: Path) -> None:
    temp_path = src.with_name(src.name + ".tmp")
    backup_path = src.with_name(src.name + ".bak")
    if temp_path.exists() or backup_path.exists():
        raise FileExistsError("temporary or backup file already exists")
    data = src.read_bytes()
    encoding = _python_encoding(data)
    transformed = _python_quine_source(data, encoding)
    try:
        with temp_path.open("xb") as temporary:
            temporary.write(transformed)
        with backup_path.open("xb") as backup:
            backup.write(data)
        os.replace(temp_path, src)
    except Exception:
        temp_path.unlink(missing_ok=True)
        if backup_path.exists() and src.read_bytes() == data:
            backup_path.unlink()
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inject a self-copy hook into Python source")
    parser.add_argument("src", type=Path)
    parser.add_argument("dst", nargs="?", type=Path)
    parser.add_argument("--in-place", action="store_true")
    parser.add_argument("--yes", action="store_true")
    args = parser.parse_args(argv)

    if args.in_place:
        if not args.yes:
            parser.error("--in-place requires --yes")
        if args.dst is not None:
            parser.error("dst cannot be provided with --in-place")
        _in_place(args.src)
        print(f"Processed Python source in place: {args.src}")
        return 0
    if args.dst is None:
        parser.error("dst is required unless --in-place is used")
    quine(args.src, args.dst)
    print(f"Processed Python source: {args.src} -> {args.dst}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
