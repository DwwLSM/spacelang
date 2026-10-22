from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path
import sys

from .asm import assemble
from .compress import pack_file, unpack_bytes, unpack_file
from .disasm import disassemble
from .encoder import encode
from .ir import Program
from .lexer import tokenize
from .parser import parse
from .peephole import optimize
from .pyfront import compile_py
from .vm_py import VM


def _load_program(path: Path) -> Program:
    data = path.read_bytes()
    if path.suffix.lower() == ".spz":
        data = unpack_bytes(data)
    program = parse(tokenize(data.decode("ascii")))
    names_path = path.with_suffix(".names.json")
    if names_path.exists():
        names = json.loads(names_path.read_text(encoding="utf-8"))
        if not isinstance(names, dict) or any(
            not isinstance(name, str) or not isinstance(name_id, int)
            for name, name_id in names.items()
        ):
            raise ValueError(f"invalid name table: {names_path}")
        program.names = names
    return program


def _write_program(program: Program, path: Path) -> None:
    encoded = encode(program).encode("ascii")
    if path.suffix.lower() == ".spz":
        encoded = gzip.compress(encoded, mtime=0)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(encoded)
    path.with_suffix(".names.json").write_text(
        json.dumps(program.names, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="spacelang")
    commands = parser.add_subparsers(dest="command", required=True)

    compile_command = commands.add_parser("compile-py", help="compile supported Python source")
    compile_command.add_argument("src", type=Path)
    compile_command.add_argument("dst", type=Path)
    compile_command.add_argument("--no-optimize", action="store_true")
    compile_command.add_argument("--compress-source", action="store_true")

    asm_command = commands.add_parser("asm", help="assemble mnemonic SpaceLang source")
    asm_command.add_argument("src", type=Path)
    asm_command.add_argument("dst", type=Path)

    disasm_command = commands.add_parser("disasm", help="disassemble a .sp or .spz program")
    disasm_command.add_argument("src", type=Path)
    disasm_command.add_argument("-o", "--output", type=Path)

    run_command = commands.add_parser("run", help="run a .sp or .spz program")
    run_command.add_argument("src", type=Path)
    run_command.add_argument("--engine", choices=("py", "cpp"), default="py")

    pack_command = commands.add_parser("pack", help="compress a .sp file into .spz")
    pack_command.add_argument("src", type=Path)
    pack_command.add_argument("dst", nargs="?", type=Path)

    unpack_command = commands.add_parser("unpack", help="decompress a .spz file into .sp")
    unpack_command.add_argument("src", type=Path)
    unpack_command.add_argument("dst", nargs="?", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "compile-py":
        program = compile_py(args.src.read_text(encoding="utf-8"), str(args.src))
        if not args.no_optimize:
            program = optimize(program, compress_source=args.compress_source)
        _write_program(program, args.dst)
        return 0

    if args.command == "asm":
        program = assemble(args.src.read_text(encoding="utf-8"))
        _write_program(program, args.dst)
        return 0

    if args.command == "disasm":
        output = disassemble(_load_program(args.src))
        if args.output is None:
            sys.stdout.write(output)
        else:
            args.output.write_text(output, encoding="utf-8")
        return 0

    if args.command == "run":
        if args.engine == "cpp":
            from .vm_cpp import VM as SelectedVM
        else:
            SelectedVM = VM
        vm = SelectedVM(_load_program(args.src))
        vm.globals_["__file__"] = str(args.src)
        vm.run()
        return 0

    if args.command == "pack":
        destination = args.dst or args.src.with_suffix(".spz")
        pack_file(args.src, destination)
        return 0

    if args.command == "unpack":
        destination = args.dst or args.src.with_suffix(".sp")
        unpack_file(args.src, destination)
        return 0

    parser.error(f"unknown command {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
