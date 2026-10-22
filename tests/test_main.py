from contextlib import redirect_stdout
import gzip
from io import StringIO

from spacelang.main import main


def test_compile_run_and_disassemble_commands(tmp_path):
    source = tmp_path / "program.py"
    compiled = tmp_path / "program.sp"
    source.write_text("print(1 + 1)\n")

    assert main(["compile-py", str(source), str(compiled)]) == 0
    assert compiled.with_suffix(".names.json").exists()

    output = StringIO()
    with redirect_stdout(output):
        assert main(["run", str(compiled)]) == 0
    assert output.getvalue() == "2\n"

    output = StringIO()
    with redirect_stdout(output):
        assert main(["disasm", str(compiled)]) == 0
    assert "PUSH_INT 2" in output.getvalue()

    output = StringIO()
    with redirect_stdout(output):
        assert main(["run", str(compiled), "--engine", "cpp"]) == 0
    assert output.getvalue() == "2\n"


def test_pack_and_run_compressed_program(tmp_path):
    source = tmp_path / "program.py"
    compiled = tmp_path / "program.sp"
    packed = tmp_path / "program.spz"
    source.write_text("print('packed')\n")
    main(["compile-py", str(source), str(compiled)])
    main(["pack", str(compiled), str(packed)])

    output = StringIO()
    with redirect_stdout(output):
        main(["run", str(packed)])
    assert output.getvalue() == "packed\n"


def test_compile_py_can_write_compressed_output(tmp_path):
    source = tmp_path / "hello.py"
    destination = tmp_path / "hello.spz"
    source.write_text("print(1)\n")

    assert main(["compile-py", str(source), str(destination)]) == 0
    assert gzip.decompress(destination.read_bytes())


def test_compile_py_compress_source_handles_large_integer(tmp_path):
    source = tmp_path / "large.py"
    destination = tmp_path / "large.sp"
    source.write_text("print(1000000)\n")

    assert main(["compile-py", str(source), str(destination), "--compress-source"]) == 0
    output = StringIO()
    with redirect_stdout(output):
        assert main(["run", str(destination)]) == 0
    assert output.getvalue() == "1000000\n"
