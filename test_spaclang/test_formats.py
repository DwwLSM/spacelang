from contextlib import redirect_stdout
import gzip
from io import StringIO
import json

import pytest

import spacelang
from spacelang.errors import EncodingError, ParseError
from spacelang.main import main
from spacelang.vm_py import VM


SOURCE = (
    "def scale(value, factor=2):\n"
    "    return value * factor\n"
    "\n"
    "values = [1, 2, 3, 4]\n"
    "lookup = {value: value ** 2 for value in values if value > 1}\n"
    "selected = {value for value in values if value % 2 == 0}\n"
    "print(scale(3, factor=4), values[::-1], lookup[3])\n"
    "print(selected, 2 in selected)\n"
)
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


def _run_cli(*args: str) -> str:
    output = StringIO()
    with redirect_stdout(output):
        assert main(list(args)) == 0
    return output.getvalue()


def _assert_program_runs_on_both_engines(path) -> None:
    expected = "12 [4, 3, 2, 1] 9\n{2, 4} True\n"
    for engine in ("py", "cpp"):
        assert _run_cli("run", str(path), "--engine", engine) == expected


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


def test_sp_roundtrip_preserves_names_and_function_metadata(tmp_path):
    source_path = tmp_path / "source.py"
    sp_path = tmp_path / "program.sp"
    source_path.write_text(SOURCE, encoding="utf-8")

    assert main(["compile-py", str(source_path), str(sp_path)]) == 0
    names = spacelang.parse(
        spacelang.tokenize(sp_path.read_bytes().decode("ascii"))
    ).names
    assert {"values", "lookup", "selected"} <= names.keys()
    assert len(set(names.values())) == len(names)
    assert not sp_path.with_suffix(".names.json").exists()
    _assert_program_runs_on_both_engines(sp_path)


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

    assert _run_program(loaded) == "12 [4, 3, 2, 1] 9\n{2, 4} True\n"


def test_spz_roundtrip_runs_compiled_program_on_both_engines(tmp_path):
    source_path = tmp_path / "source.py"
    spz_path = tmp_path / "program.spz"
    source_path.write_text(SOURCE, encoding="utf-8")

    assert main(["compile-py", str(source_path), str(spz_path)]) == 0
    assert spacelang.unpack_bytes(spz_path.read_bytes()).startswith(b" ")
    assert not spz_path.with_suffix(".names.json").exists()
    _assert_program_runs_on_both_engines(spz_path)


def test_spasm_roundtrip_preserves_names_and_function_metadata(tmp_path):
    source_path = tmp_path / "source.py"
    spasm_path = tmp_path / "program.spasm"
    reassembled_path = tmp_path / "reassembled.sp"
    source_path.write_text(SOURCE, encoding="utf-8")
    original_path = tmp_path / "original.sp"
    assert main(["compile-py", str(source_path), str(original_path)]) == 0
    original = spacelang.parse(spacelang.tokenize(original_path.read_bytes().decode("ascii")))
    spasm_path.write_text(spacelang.disassemble(original), encoding="utf-8")

    assert main(["asm", str(spasm_path), str(reassembled_path)]) == 0
    _assert_program_runs_on_both_engines(reassembled_path)


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


def test_malformed_format_files_fail_with_clear_errors(tmp_path):
    invalid_sp = tmp_path / "invalid.sp"
    invalid_sp.write_text(" " * 999 + "\n", encoding="ascii")
    with pytest.raises(ParseError, match="unknown opcode"):
        main(["run", str(invalid_sp)])

    with pytest.raises(EncodingError, match="invalid gzip SpaceLang file"):
        spacelang.unpack_bytes(b"not gzip")


@pytest.mark.parametrize(
    ("sidecar_contents", "error_type", "message"),
    [
        ("{invalid json", json.JSONDecodeError, None),
        ("[]", ValueError, "invalid name table"),
        ('{"name": "not-an-id"}', ValueError, "invalid name table"),
    ],
)
def test_run_rejects_invalid_name_sidecars(tmp_path, sidecar_contents, error_type, message):
    sp_path = tmp_path / "program.sp"
    sp_path.write_text(spacelang.encode(spacelang.compile_py("print('ok')\n")), encoding="ascii")
    sp_path.with_suffix(".names.json").write_text(sidecar_contents, encoding="utf-8")

    if message is None:
        with pytest.raises(error_type):
            main(["run", str(sp_path)])
    else:
        with pytest.raises(error_type, match=message):
            main(["run", str(sp_path)])


@pytest.mark.parametrize(
    "compressed",
    [
        b"not gzip",
        gzip.compress(b" " * 100)[:-4],
    ],
    ids=["invalid-header", "truncated-stream"],
)
def test_run_rejects_corrupt_spz_files(tmp_path, compressed):
    spz_path = tmp_path / "corrupt.spz"
    spz_path.write_bytes(compressed)

    with pytest.raises(EncodingError, match="invalid gzip SpaceLang file"):
        main(["run", str(spz_path)])
