from contextlib import redirect_stdout
from io import StringIO
from types import SimpleNamespace

import pytest

pytest.importorskip("spacelang._spacelang_cpp")

from spacelang.pyfront import compile_py
from spacelang.vm_cpp import VM as CppVM
from spacelang.vm_py import VM as PythonVM


@pytest.mark.parametrize(
    "source",
    [
        "print(1 + 2 * 3)",
        "def square(value): return value * value\nresult = square(9)\nprint(result)",
        "def factorial(value):\n    if value < 2:\n        return 1\n    return value * factorial(value - 1)\nprint(factorial(5))",
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
        if not hasattr(value, "__spec__")
    } == {
        name: value
        for name, value in machines[1].globals_.items()
        if not hasattr(value, "__spec__")
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
