from contextlib import redirect_stdout
from io import StringIO

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
        "values = [1, 2, 3]\nresult = values[1]\nprint(result)",
        "import math\nresult = math.sqrt(81)\nprint(result)",
        'print("left", "right", sep="-")',
        "result = 0\nfor value in range(5):\n    result = result + value\nprint(result)",
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
