from contextlib import redirect_stdout
from io import StringIO
from types import SimpleNamespace

import pytest

pytest.importorskip("spacelang._spacelang_cpp")

from spacelang.encoder import encode
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
