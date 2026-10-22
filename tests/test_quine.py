import gzip
import json
import subprocess
import sys
from contextlib import redirect_stdout
from io import StringIO

import pytest

from spacelang.asm import assemble
from spacelang.encoder import encode
from spacelang.errors import EncodingError
from spacelang.ir import Instr, OP, Program
from spacelang.lexer import tokenize
from spacelang.main import main as spacelang_main
from spacelang.parser import parse
from spacelang.pyfront import compile_py
from spacelang.quine import _HOOK_INSTRS, quine
from spacelang.quine import main as quine_main


def test_python_quine_creates_copy_without_modifying_source(tmp_path):
    source = tmp_path / "source.py"
    destination = tmp_path / "generated.py"
    source_bytes = b'"""module docs"""\nfrom __future__ import annotations\nprint("hello")\n'
    source.write_bytes(source_bytes)

    quine(source, destination)

    assert source.read_bytes() == source_bytes
    subprocess.run([sys.executable, str(destination)], check=True, cwd=tmp_path)
    copy = tmp_path / "generated.copy.py"
    assert copy.read_bytes() == destination.read_bytes()


def test_python_quine_supports_future_import_without_docstring(tmp_path):
    source = tmp_path / "future.py"
    destination = tmp_path / "future_q.py"
    source.write_text("from __future__ import annotations\nvalue = 1\n")

    quine(source, destination)

    generated = destination.read_text()
    assert generated.index("from __future__ import annotations") < generated.index("def __spacelang_quine_hook_")
    assert generated.index("def __spacelang_quine_hook_") < generated.index("value = 1")


def test_python_quine_preserves_shebang_and_encoding_cookie(tmp_path):
    source = tmp_path / "script.py"
    destination = tmp_path / "script_q.py"
    original = b"#!/usr/bin/env python3\n# coding: latin-1\nprint('caf\xe9')\n"
    source.write_bytes(original)

    quine(source, destination)

    generated = destination.read_bytes()
    assert generated.startswith(b"#!/usr/bin/env python3\n# coding: latin-1\n")
    subprocess.run([sys.executable, str(destination)], check=True, cwd=tmp_path)
    assert (tmp_path / "script_q.copy.py").read_bytes() == generated


def test_quine_rejects_same_path_and_invalid_python(tmp_path):
    source = tmp_path / "source.py"
    source.write_text("print('hello')\n")
    with pytest.raises(ValueError):
        quine(source, source)

    invalid = tmp_path / "invalid.py"
    invalid.write_text("def broken(:\n")
    with pytest.raises(EncodingError):
        quine(invalid, tmp_path / "invalid_q.py")


def test_sp_quine_copies_generated_program_and_name_table(tmp_path):
    source = tmp_path / "source.sp"
    destination = tmp_path / "generated.sp"
    original = assemble("PUSH_INT 7\nHALT\n")
    source.write_text(encode(original))

    quine(source, destination)

    assert spacelang_main(["run", str(destination)]) == 0
    copy = tmp_path / "generated.copy.sp"
    assert copy.read_bytes() == destination.read_bytes()
    assert copy.with_suffix(".names.json").read_bytes() == destination.with_suffix(".names.json").read_bytes()
    assert spacelang_main(["run", str(copy)]) == 0
    assert (tmp_path / "generated.copy.copy.sp").read_bytes() == copy.read_bytes()


def test_sp_quine_shifts_names_jumps_and_functions(tmp_path):
    source = tmp_path / "named.sp"
    destination = tmp_path / "named_q.sp"
    program = Program(
        instrs=[
            Instr(OP.DEF, [10000, 0]),
            Instr(OP.PUSH_INT, [9]),
            Instr(OP.RET),
            Instr(OP.LOAD_GLOBAL, [0]),
            Instr(OP.CALL, [0, 1]),
            Instr(OP.PUSH_INT, [1]),
            Instr(OP.JZ, [7]),
            Instr(OP.PUSH_INT, [4]),
            Instr(OP.HALT),
        ],
        names={"value": 0, "print": 1},
    )
    source.write_text(encode(program))
    source.with_suffix(".names.json").write_text('{"value": 0, "print": 1}\n')

    quine(source, destination)

    transformed = parse(tokenize(destination.read_text()))
    names = json.loads(destination.with_suffix(".names.json").read_text())
    transformed.names = names
    offset = len(_HOOK_INSTRS)
    assert transformed.funcs[10000] == (offset + 1, offset + 10)
    assert transformed.instrs[offset + 3].op == OP.LOAD_GLOBAL
    assert transformed.instrs[offset + 3].args == [0]


def test_sp_quine_preserves_keyword_name_ids_and_zero_try_targets(tmp_path):
    source = tmp_path / "keyword.sp"
    destination = tmp_path / "keyword_q.sp"
    program = compile_py('print("left", "right", sep="-")')
    source.write_text(encode(program))
    source.with_suffix(".names.json").write_text(json.dumps(program.names))

    quine(source, destination)

    transformed = parse(tokenize(destination.read_text()))
    transformed.names = json.loads(destination.with_suffix(".names.json").read_text())
    offset = len(_HOOK_INSTRS)
    keyword_name_ids = [
        instr.args[0]
        for instr in program.instrs
        if instr.op == OP.PUSH_INT and instr.args[0] in program.names.values()
    ]
    assert keyword_name_ids
    transformed_keyword_name_ids = [
        instr.args[0]
        for instr in transformed.instrs[offset:]
        if instr.op == OP.PUSH_INT and instr.args[0] in program.names.values()
    ]
    assert transformed_keyword_name_ids == keyword_name_ids
    output = StringIO()
    with redirect_stdout(output):
        spacelang_main(["run", str(destination)])
    assert output.getvalue() == "left-right\n"

    try_source = tmp_path / "try.sp"
    try_destination = tmp_path / "try_q.sp"
    try_program = Program(
        instrs=[
            Instr(OP.TRY, [0, 0]),
            Instr(OP.PUSH_INT, [1]),
            Instr(OP.END_TRY),
            Instr(OP.HALT),
        ]
    )
    try_source.write_text(encode(try_program))
    quine(try_source, try_destination)
    transformed_try = parse(tokenize(try_destination.read_text()))
    assert transformed_try.instrs[offset].args == [0, 0]


def test_spz_quine_accepts_compressed_source(tmp_path):
    source = tmp_path / "source.spz"
    destination = tmp_path / "generated.spz"
    encoded = encode(assemble("PUSH_INT 3\nHALT\n")).encode("ascii")
    source.write_bytes(gzip.compress(encoded, mtime=0))

    quine(source, destination)

    generated_source = gzip.decompress(destination.read_bytes())
    assert generated_source
    assert spacelang_main(["run", str(destination)]) == 0
    assert (tmp_path / "generated.copy.spz").read_bytes() == destination.read_bytes()


def test_quine_hook_has_no_halt_def_or_out_of_range_jump():
    assert all(instr.op not in {OP.HALT, OP.DEF} for instr in _HOOK_INSTRS)
    assert all(
        int(instr.args[0]) < len(_HOOK_INSTRS)
        for instr in _HOOK_INSTRS
        if instr.op in {OP.JMP, OP.JZ, OP.JNZ}
    )


def test_in_place_cli_requires_confirmation_and_creates_backup(tmp_path):
    source = tmp_path / "in_place.py"
    original = b"from __future__ import annotations\nprint('ok')\n"
    source.write_bytes(original)

    with pytest.raises(SystemExit):
        quine_main([str(source), "--in-place"])
    assert source.read_bytes() == original

    assert quine_main([str(source), "--in-place", "--yes"]) == 0
    assert source.with_name("in_place.py.bak").read_bytes() == original
    assert "from __future__ import annotations" in source.read_text()
