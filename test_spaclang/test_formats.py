from contextlib import redirect_stdout
from io import StringIO
import json

import spacelang
from spacelang.vm_py import VM


SOURCE = "def add(a, b):\n    return a + b\n\nprint(add(2, 3))\n"
ASSEMBLY = """\
PUSH_INT 2
PUSH_INT 3
OP 1
CALL 0 1
HALT
"""


def _run_program(program) -> str:
    output = StringIO()
    with redirect_stdout(output):
        VM(program).run()
    return output.getvalue()


def test_create_sp(tmp_path):
    program = spacelang.compile_py(SOURCE)
    encoded = spacelang.encode(program)
    sp_path = tmp_path / "program.sp"
    sp_path.write_text(encoded, encoding="ascii")
    sp_path.with_suffix(".names.json").write_text(
        json.dumps(program.names),
        encoding="utf-8",
    )

    assert sp_path.exists()
    assert sp_path.read_text(encoding="ascii") == encoded


def test_run_sp(tmp_path):
    program = spacelang.compile_py(SOURCE)
    sp_path = tmp_path / "program.sp"
    sp_path.write_text(spacelang.encode(program), encoding="ascii")
    sp_path.with_suffix(".names.json").write_text(
        json.dumps(program.names),
        encoding="utf-8",
    )

    loaded = spacelang.parse(
        spacelang.tokenize(sp_path.read_bytes().decode("ascii"))
    )
    loaded.names = json.loads(
        sp_path.with_suffix(".names.json").read_text(encoding="utf-8")
    )

    assert _run_program(loaded) == "5\n"


def test_create_spasm(tmp_path):
    program = spacelang.assemble(ASSEMBLY)
    spasm_path = tmp_path / "program.spasm"
    spasm_path.write_text(spacelang.disassemble(program), encoding="utf-8")

    assert spasm_path.exists()
    assert "PUSH_INT 2" in spasm_path.read_text(encoding="utf-8")


def test_run_spasm(tmp_path):
    program = spacelang.assemble(ASSEMBLY)
    spasm_path = tmp_path / "program.spasm"
    spasm_path.write_text(spacelang.disassemble(program), encoding="utf-8")

    assembled = spacelang.assemble(
        spasm_path.read_text(encoding="utf-8")
    )

    assert _run_program(assembled) == "5\n"

