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


def test_compile_py_supports_dictionary_operations_in_sp_file(tmp_path):
    source = tmp_path / "dictionary.py"
    destination = tmp_path / "dictionary.sp"
    source.write_text(
        "data = {'name': 'Ada', 'count': 1}\n"
        "data['count'] += 2\n"
        "data['active'] = True\n"
        "print(data, data['name'], data['count'], data['active'])\n"
    )

    assert main(["compile-py", str(source), str(destination)]) == 0
    for engine in ("py", "cpp"):
        output = StringIO()
        with redirect_stdout(output):
            assert main(["run", str(destination), "--engine", engine]) == 0
        assert output.getvalue() == "{'name': 'Ada', 'count': 3, 'active': True} Ada 3 True\n"


def test_compile_py_supports_dictionary_unpacking_in_sp_file(tmp_path):
    source = tmp_path / "dictionary_unpacking.py"
    destination = tmp_path / "dictionary_unpacking.sp"
    source.write_text(
        "first = {'value': 1, 'keep': 2}\n"
        "second = {'value': 3, 4: 'number'}\n"
        "result = {**first, 'extra': 5, **second, 'last': 6}\n"
        "print(result)\n"
    )

    assert main(["compile-py", str(source), str(destination)]) == 0
    for engine in ("py", "cpp"):
        output = StringIO()
        with redirect_stdout(output):
            assert main(["run", str(destination), "--engine", engine]) == 0
        assert output.getvalue() == "{'value': 3, 'keep': 2, 'extra': 5, 4: 'number', 'last': 6}\n"


def test_compile_py_supports_dictionary_comprehensions_in_sp_file(tmp_path):
    source = tmp_path / "dictionary_comprehension.py"
    destination = tmp_path / "dictionary_comprehension.sp"
    source.write_text(
        "offset = 10\n"
        "result = {x: x + offset for x in range(5) if x > 1}\n"
        "pairs = {x: y for x in [1, 2, 3] for y in range(x) if y > 0}\n"
        "overwritten = {x % 2: x for x in range(5)}\n"
        "print(result, pairs, overwritten)\n"
    )

    assert main(["compile-py", str(source), str(destination)]) == 0
    expected = "{2: 12, 3: 13, 4: 14} {2: 1, 3: 2} {0: 4, 1: 3}\n"
    for engine in ("py", "cpp"):
        output = StringIO()
        with redirect_stdout(output):
            assert main(["run", str(destination), "--engine", engine]) == 0
        assert output.getvalue() == expected


def test_compile_py_supports_sets_in_sp_file(tmp_path):
    source = tmp_path / "sets.py"
    destination = tmp_path / "sets.sp"
    source.write_text(
        "values = {1, 2, 2}\n"
        "empty = set()\n"
        "values.add(3)\n"
        "lookup = {value for value in range(6) if value % 2 == 0}\n"
        "pairs = {x + y for x in range(3) for y in range(x) if y > 0}\n"
        "print(values, empty, lookup, pairs)\n"
        "print(2 in values, 4 not in values, 'a' in {'a': 1})\n"
    )

    assert main(["compile-py", str(source), str(destination)]) == 0
    expected = "{1, 2, 3} set() {0, 2, 4} {3}\nTrue True True\n"
    for engine in ("py", "cpp"):
        output = StringIO()
        with redirect_stdout(output):
            assert main(["run", str(destination), "--engine", engine]) == 0
        assert output.getvalue() == expected


def test_compile_py_supports_slicing_in_sp_file(tmp_path):
    source = tmp_path / "slicing.py"
    destination = tmp_path / "slicing.sp"
    source.write_text(
        "values = [0, 1, 2, 3, 4, 5]\n"
        "middle = values[1:5:2]\n"
        "reverse = values[::-1]\n"
        "values[1:3] = [8, 9]\n"
        "values[::2] = [20, 21, 22]\n"
        "values[1:2] += [30]\n"
        "print(middle, reverse, values)\n"
        "print('abcdef'[1:5:2], (0, 1, 2, 3)[::-1])\n"
    )

    assert main(["compile-py", str(source), str(destination)]) == 0
    expected = "[1, 3] [5, 4, 3, 2, 1, 0] [20, 8, 30, 21, 3, 22, 5]\n" "bd (3, 2, 1, 0)\n"
    for engine in ("py", "cpp"):
        output = StringIO()
        with redirect_stdout(output):
            assert main(["run", str(destination), "--engine", engine]) == 0
        assert output.getvalue() == expected


def test_compile_py_supports_float_literals_in_sp_file(tmp_path):
    source = tmp_path / "floats.py"
    destination = tmp_path / "floats.sp"
    source.write_text(
        "integer_looking = 1.\n"
        "exponential = 1.25e2\n"
        "negative = -2.5\n"
        "sum_value = 0.1 + 0.2\n"
        "product = 1.5 * 2\n"
        "print(integer_looking, exponential, negative, sum_value, product)\n"
        "print(2.5 > 2, 3 == 3.0)\n"
    )

    assert main(["compile-py", str(source), str(destination)]) == 0
    expected = "1.0 125.0 -2.5 0.30000000000000004 3.0\nTrue True\n"
    for engine in ("py", "cpp"):
        output = StringIO()
        with redirect_stdout(output):
            assert main(["run", str(destination), "--engine", engine]) == 0
        assert output.getvalue() == expected


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


def test_compile_py_supports_saved_closure_keyword_arguments_in_sp_file(tmp_path):
    source = tmp_path / "closure_keywords.py"
    destination = tmp_path / "closure_keywords.sp"
    source.write_text(
        "def make_adder(base):\n"
        "    def add(value, extra=2):\n"
        "        return base + value + extra\n"
        "    return add\n"
        "\n"
        "fn = make_adder(5)\n"
        "print(fn(extra=4, value=3), fn(1))\n"
    )

    assert main(["compile-py", str(source), str(destination)]) == 0
    for engine in ("py", "cpp"):
        output = StringIO()
        with redirect_stdout(output):
            assert main(["run", str(destination), "--engine", engine]) == 0
        assert output.getvalue() == "12 8\n"


def test_compile_py_supports_expanded_call_arguments_in_sp_file(tmp_path):
    source = tmp_path / "expanded_arguments.py"
    destination = tmp_path / "expanded_arguments.sp"
    source.write_text(
        "def make_options(**options):\n"
        "    return options\n"
        "\n"
        "def collect(first, *rest, **options):\n"
        "    return (first, rest, options)\n"
        "\n"
        "values = [1, 2, 3]\n"
        "options = make_options(color='blue')\n"
        "print(collect(*values, **options))\n"
    )

    assert main(["compile-py", str(source), str(destination)]) == 0
    for engine in ("py", "cpp"):
        output = StringIO()
        with redirect_stdout(output):
            assert main(["run", str(destination), "--engine", engine]) == 0
        assert output.getvalue() == "(1, (2, 3), {'color': 'blue'})\n"


def test_compile_py_supports_positional_only_and_expression_defaults_in_sp_file(tmp_path):
    source = tmp_path / "parameter_edges.py"
    destination = tmp_path / "parameter_edges.sp"
    source.write_text(
        "base = 3\n"
        "def render(value, /, prefix='v=', *, suffix=str(base)):\n"
        "    return prefix + str(value) + suffix\n"
        "base = 9\n"
        "print(render(4), render(*[5], **options(prefix='x=')))\n"
        "def options(**kwargs):\n"
        "    return kwargs\n"
    )

    assert main(["compile-py", str(source), str(destination)]) == 0
    for engine in ("py", "cpp"):
        output = StringIO()
        with redirect_stdout(output):
            assert main(["run", str(destination), "--engine", engine]) == 0
        assert output.getvalue() == "v=43 x=53\n"


def test_compile_py_supports_varargs_in_sp_file(tmp_path):
    source = tmp_path / "varargs.py"
    destination = tmp_path / "varargs.sp"
    source.write_text(
        "def collect(first=1, *rest, label, suffix='!'):\n"
        "    return (first, rest, label, suffix)\n"
        "\n"
        "def make_collector(prefix):\n"
        "    def collect(first, *rest, marker='!'):\n"
        "        return (prefix, first, rest, marker)\n"
        "    return collect\n"
        "\n"
        "closure = make_collector('<')\n"
        "print(collect(2, 3, 4, label='top'))\n"
        "print(closure(5, 6, 7, marker='?'))\n"
    )

    assert main(["compile-py", str(source), str(destination)]) == 0
    for engine in ("py", "cpp"):
        output = StringIO()
        with redirect_stdout(output):
            assert main(["run", str(destination), "--engine", engine]) == 0
        assert output.getvalue() == "(2, (3, 4), 'top', '!')\n('<', 5, (6, 7), '?')\n"


def test_compile_py_supports_kwargs_in_sp_file(tmp_path):
    source = tmp_path / "kwargs.py"
    destination = tmp_path / "kwargs.sp"
    source.write_text(
        "def collect(value, **options):\n"
        "    return (value, options)\n"
        "\n"
        "def make_collector(prefix):\n"
        "    def collect(value, **options):\n"
        "        return (prefix, value, options)\n"
        "    return collect\n"
        "\n"
        "closure = make_collector('<')\n"
        "print(collect(2, color='blue', size=3))\n"
        "print(closure(4, active=True))\n"
    )

    assert main(["compile-py", str(source), str(destination)]) == 0
    for engine in ("py", "cpp"):
        output = StringIO()
        with redirect_stdout(output):
            assert main(["run", str(destination), "--engine", engine]) == 0
        assert output.getvalue() == "(2, {'color': 'blue', 'size': 3})\n('<', 4, {'active': True})\n"


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
