from contextlib import redirect_stdout
import gzip
from io import StringIO

from spacelang.main import main


def test_function_roundtrip_through_compiled_sp_file(tmp_path):
    source = tmp_path / "function_program.py"
    compiled = tmp_path / "function_program.sp"
    source.write_text(
        "def add(a, b):\n"
        "    return a + b\n"
        "\n"
        "print(add(2, 3))\n"
    )

    assert main(["compile-py", str(source), str(compiled)]) == 0

    output = StringIO()
    with redirect_stdout(output):
        assert main(["run", str(compiled)]) == 0
    assert output.getvalue() == "5\n"

    output = StringIO()
    with redirect_stdout(output):
        assert main(["run", str(compiled), "--engine", "cpp"]) == 0
    assert output.getvalue() == "5\n"


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


def test_compile_py_supports_augmented_assignment(tmp_path):
    source = tmp_path / "augmented.py"
    destination = tmp_path / "augmented.sp"
    source.write_text(
        "sum_value = 0\n"
        "for i in range(5):\n"
        "    sum_value += i * 2\n"
        "print(sum_value)\n"
    )

    assert main(["compile-py", str(source), str(destination)]) == 0
    output = StringIO()
    with redirect_stdout(output):
        assert main(["run", str(destination)]) == 0
    assert output.getvalue() == "20\n"


def test_compile_py_supports_unpacking_and_index_assignment(tmp_path):
    source = tmp_path / "assignment_targets.py"
    destination = tmp_path / "assignment_targets.sp"
    source.write_text(
        "values = [1, 2]\n"
        "first, second = values\n"
        "values[0] = second\n"
        "values[1] = first\n"
        "values[0] += 3\n"
        "print(values)\n"
    )

    assert main(["compile-py", str(source), str(destination)]) == 0
    for engine in ("py", "cpp"):
        output = StringIO()
        with redirect_stdout(output):
            assert main(["run", str(destination), "--engine", engine]) == 0
        assert output.getvalue() == "[5, 1]\n"


def test_compile_py_supports_function_defaults_and_keyword_arguments(tmp_path):
    source = tmp_path / "function_parameters.py"
    destination = tmp_path / "function_parameters.sp"
    source.write_text(
        "def render(value, prefix='v='):\n"
        "    return prefix + str(value)\n"
        "\n"
        "print(render(3))\n"
        "print(render(value=4, prefix='x='))\n"
    )

    assert main(["compile-py", str(source), str(destination)]) == 0
    for engine in ("py", "cpp"):
        output = StringIO()
        with redirect_stdout(output):
            assert main(["run", str(destination), "--engine", engine]) == 0
        assert output.getvalue() == "v=3\nx=4\n"


def test_compile_py_supports_global_declarations_in_sp_file(tmp_path):
    source = tmp_path / "global_scope.py"
    destination = tmp_path / "global_scope.sp"
    source.write_text(
        "counter = 4\n"
        "def increment():\n"
        "    global counter\n"
        "    counter = counter + 1\n"
        "    return counter\n"
        "print(increment(), counter)\n"
    )

    assert main(["compile-py", str(source), str(destination)]) == 0
    output = StringIO()
    with redirect_stdout(output):
        assert main(["run", str(destination), "--engine", "cpp"]) == 0
    assert output.getvalue() == "5 5\n"


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
