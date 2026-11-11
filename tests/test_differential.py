from contextlib import redirect_stdout
from io import StringIO
from types import SimpleNamespace

import pytest

pytest.importorskip("spacelang._spacelang_cpp")

from spacelang.errors import SpaceError
from spacelang.encoder import encode
from spacelang.ir import OP
from spacelang.lexer import tokenize
from spacelang.parser import parse
from spacelang.pyfront import compile_py
from spacelang.peephole import optimize
from spacelang.vm_cpp import VM as CppVM
from spacelang.vm_py import Closure, VM as PythonVM


@pytest.mark.parametrize(
    "source",
    [
        "print(1 + 2 * 3)",
        "def square(value): return value * value\nresult = square(9)\nprint(result)",
        "def factorial(value):\n    if value < 2:\n        return 1\n    return value * factorial(value - 1)\nprint(factorial(5))",
        "def make_counter(start):\n    value = start\n    def increment():\n        nonlocal value\n        value = value + 1\n        return value\n    return increment\ncounter = make_counter(4)\nprint(counter(), counter())",
        "def make_factorial(limit):\n    def wrapper():\n        def factorial(value):\n            if value < 2:\n                return 1\n            return value * factorial(value - 1)\n        return factorial(limit)\n    return wrapper\nfactorial = make_factorial(5)\nprint(factorial())",
        "def outer(base):\n    def combine(left, right=3, suffix=\"!\"):\n        return base + left + right\n    return combine(left=2, suffix=\"?\", right=4)\nprint(outer(10))",
        "def factorial():\n    def calculate(value, result=1):\n        if value < 2:\n            return result\n        return calculate(value=value - 1, result=result * value)\n    return calculate(value=5)\nprint(factorial())",
        "def make_adder(base):\n    def add(value, extra=2): return base + value + extra\n    return add\nfn = make_adder(5)\nprint(fn(extra=4, value=3))",
        "def make_formatter(prefix):\n    def format_value(value, *, suffix, mark='!'): return prefix + str(value) + suffix + mark\n    return format_value\nformat_value = make_formatter('<')\nprint(format_value(3, suffix='>', mark='?'), format_value(4, suffix=']'))",
        "def make_formatter(prefix):\n    def format_value(value=3, *, mark='!', suffix, end='.'): return prefix + str(value) + mark + suffix + end\n    return format_value\nformat_value = make_formatter('<')\nprint(format_value(suffix=']'))",
        "def format_value(value, *, prefix, suffix='!'): return prefix + str(value) + suffix\nprint(format_value(3, prefix='v='), format_value(4, suffix='?', prefix='x='))",
        "def outer():\n    def inner(value, *, suffix): return str(value) + suffix\n    return inner(2, suffix='!')\nprint(outer())",
        "def collect(first, *rest): return (first, rest)\nprint(collect(1), collect(1, 2, 3))",
        "def make_collector(prefix):\n    def collect(first, *rest, marker='!'): return (prefix, first, rest, marker)\n    return collect\ncollect = make_collector('<')\nprint(collect(1), collect(1, 2, 3, marker='?'))",
        "def make_formatter(prefix):\n    def format_value(first=3, *rest, marker='!', suffix, end='.'): return (prefix, first, rest, marker, suffix, end)\n    return format_value\nformat_value = make_formatter('<')\nprint(format_value(4, 5, 6, suffix=']'), format_value(suffix='>'))",
        "def outer(*values):\n    def inner(): return values\n    return inner\ninner = outer(1, 2, 3)\nprint(inner())",
        "def collect(*values): return values\nprint(collect(), collect(1, 2, 3))",
        "def collect(value, **options): return (value, options)\nprint(collect(1, color='blue', size=3))",
        "def make_options(**options): return options\n"
        "def collect(first, second=2, *rest, marker='!', **options): return (first, second, rest, marker, options)\n"
        "values = [1, 4, 5]\noptions = make_options(marker='?', color='blue')\n"
        "print(collect(*values, **options), collect(**make_options(first=7)))",
        "def make_options(**options): return options\n"
        "def outer():\n"
        "    def inner(value, **options): return (value, options)\n"
        "    values = [3]\n"
        "    options = make_options(label='nested')\n"
        "    return inner(*values, **options)\n"
        "print(outer())",
        "values = [[1, 2, 3]]\nprint(len(*values))\nprint(*['left', 'right'], sep=':')",
        "def make_collector(prefix):\n    def collect(value, *rest, marker='!', **options): return (prefix, value, rest, marker, options)\n    return collect\ncollect = make_collector('<')\nprint(collect(1, 2, 3, marker='?', color='red', size=4))",
        "def outer():\n    def inner(value, **options): return (value, options)\n    return inner(2, flag=True)\nprint(outer())",
        "counter = 4\ndef update():\n    global counter\n    counter = counter + 1\n    return counter\nprint(update(), counter)",
        "item = 9\ndef values():\n    result = [item for item in [1, 2]]\n    empty = None\n    return item, empty\nprint(values())",
        "def empty():\n    return None\nprint(empty(), None)",
        'def render(value, prefix="v="): return prefix + str(value)\nprint(render(3))\nprint(render(value=4, prefix="x="))',
        "values = [1, 2, 3]\nresult = values[1]\nprint(result)",
        "import math\nresult = math.sqrt(81)\nprint(result)",
        'print("left", "right", sep="-")',
        "result = 0\nfor value in range(5):\n    result = result + value\nprint(result)",
        "for value in [1, 2, 3, 4]:\n    if value == 2:\n        continue\n    if value == 4:\n        break\n    print(value)",
        'print([value for value in (1, 2, 3)])\nprint([letter for letter in "ab"])',
        "print([value for value in range(8) if value % 2 == 0 if value > 2])",
        "print([(x, y) for x in range(3) if x > 0 for x in [x, x + 10] if x < 10 for y in range(x)])",
        "print(1 < 2 < 3)",
    ],
)
def test_python_and_cpp_engines_match_supported_programs(source):
    program = compile_py(source)
    outputs = []
    machines = []
    for vm_type in (PythonVM, CppVM):
        output = StringIO()
        vm = vm_type(program)
        with redirect_stdout(output):
            vm.run()
        outputs.append(output.getvalue())
        machines.append(vm)

    assert outputs[0] == outputs[1]
    assert {
        name: value
        for name, value in machines[0].globals_.items()
        if not hasattr(value, "__spec__") and not isinstance(value, Closure)
    } == {
        name: value
        for name, value in machines[1].globals_.items()
        if not hasattr(value, "__spec__") and not isinstance(value, Closure)
    }


def test_python_and_cpp_engines_match_assignment_targets():
    program = compile_py(
        "box.value += 2\n"
        "items[0], items[1] = items[1], items[0]\n"
    )
    machines = []
    for vm_type in (PythonVM, CppVM):
        vm = vm_type(program)
        vm.globals_["box"] = SimpleNamespace(value=3)
        vm.globals_["items"] = [1, 2]
        vm.run()
        machines.append(vm)

    for vm in machines:
        assert vm.globals_["box"].value == 5
        assert vm.globals_["items"] == [2, 1]


@pytest.mark.parametrize(
    ("call", "message"),
    [
        ("fn(1, unknown=2)", "unexpected keyword argument 'unknown'"),
        ("fn(1, value=2)", "multiple values for argument 'value'"),
        ("fn()", "missing required argument 'value'"),
    ],
)
def test_python_and_cpp_engines_validate_saved_closure_keywords(call, message):
    source = (
        "def outer():\n"
        "    def inner(value): return value\n"
        "    return inner\n"
        "fn = outer()\n"
        f"{call}\n"
    )
    program = compile_py(source)

    for vm_type in (PythonVM, CppVM):
        with pytest.raises(SpaceError, match=message):
            vm_type(program).run()


@pytest.mark.parametrize(
    ("call", "message"),
    [
        ("fn(1, 'x')", "expected at most 1 positional arguments"),
        ("fn(1)", "missing required argument 'suffix'"),
    ],
)
def test_python_and_cpp_engines_validate_saved_closure_keyword_only_arguments(call, message):
    source = (
        "def outer():\n"
        "    def inner(value, *, suffix): return value\n"
        "    return inner\n"
        "fn = outer()\n"
        f"{call}\n"
    )
    program = compile_py(source)

    for vm_type in (PythonVM, CppVM):
        with pytest.raises(SpaceError, match=message):
            vm_type(program).run()


def test_python_and_cpp_engines_still_run_legacy_closure_bytecode():
    program = parse(
        [
            OP.DEF, 10000, 1,
            OP.LOAD_ARG, 0,
            OP.RET,
            OP.MAKE_CLOSURE, 10000, 0, 1,
            OP.PUSH_INT, 12,
            OP.CALL_OBJ, 1,
            OP.HALT,
        ]
    )

    for vm_type in (PythonVM, CppVM):
        assert vm_type(program).run() == 6


def test_python_and_cpp_engines_match_optimized_closures():
    program = optimize(
        compile_py(
            "def make_counter(value):\n"
            "    def increment():\n"
            "        nonlocal value\n"
            "        value = value + 1\n"
            "        return value\n"
            "    return increment\n"
            "counter = make_counter(10)\n"
            "print(counter(), counter())\n"
        )
    )
    serialized = parse(tokenize(encode(program)))
    assert serialized.funcs == program.funcs
    serialized.names = program.names
    outputs = []
    for vm_type in (PythonVM, CppVM):
        output = StringIO()
        with redirect_stdout(output):
            vm_type(serialized).run()
        outputs.append(output.getvalue())

    assert outputs == ["11 12\n", "11 12\n"]
