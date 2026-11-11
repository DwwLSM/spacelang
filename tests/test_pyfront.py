from contextlib import redirect_stdout
from io import StringIO
from types import SimpleNamespace
import textwrap

import pytest

from spacelang.errors import ParseError, SpaceError
from spacelang.pyfront import compile_py
from spacelang.vm_py import VM


def run_source(src: str) -> str:
    program = compile_py(src)
    buf = StringIO()
    with redirect_stdout(buf):
        VM(program).run()
    return buf.getvalue()


def test_pyfront_print_math_and_function_call():
    assert run_source("print(1+2*3)") == "7\n"
    assert run_source("def add(a,b): return a+b\nprint(add(2,3))") == "5\n"
    assert run_source("def subtract(a,b): return a-b\nprint(subtract(7,2))") == "5\n"
    assert run_source("print(later(3))\ndef later(value): return value + 1") == "4\n"


def test_pyfront_drops_expression_results_and_preserves_none_call_results():
    assert run_source('print(print("inner"))') == "inner\nNone\n"
    assert run_source("def value(): return 7\nvalue()\nprint(1)") == "1\n"


def test_pyfront_while_and_if():
    src = textwrap.dedent("""
    i = 0
    while i < 3:
        print(i)
        i = i + 1
    """)
    assert run_source(src) == "0\n1\n2\n"

    src = textwrap.dedent("""
    x = 5
    if x > 3:
        print(1)
    else:
        print(0)
    """)
    assert run_source(src) == "1\n"


def test_pyfront_conditional_expression_selects_one_branch():
    source = "print(7 if True else 1 / 0)\nprint(1 if False else 9)"
    assert run_source(source) == "7\n9\n"


def test_pyfront_for_range_and_sequence_indexing():
    src = textwrap.dedent("""
    for i in range(2, 8, 2):
        print(i)
    print([1, 2, 3][1])
    """)
    assert run_source(src) == "2\n4\n6\n2\n"


def test_pyfront_for_loops_use_general_iterators_and_support_loop_control():
    source = textwrap.dedent("""
    for value in [1, 2, 3, 4]:
        if value == 2:
            continue
        if value == 4:
            break
        print(value)

    for character in "ab":
        print(character)

    for value in (5, 6):
        print(value)

    for value in [7, 8]:
        while True:
            break
        print(value)
    """)
    assert run_source(source) == "1\n3\na\nb\n5\n6\n7\n8\n"


def test_pyfront_nested_loop_control_and_loop_else():
    source = textwrap.dedent("""
    for outer in [1, 2]:
        for inner in [1, 2, 3]:
            if inner == 2:
                continue
            if outer == 2:
                break
            print(outer, inner)
    else:
        print("outer done")

    for value in []:
        print(value)
    else:
        print("empty done")

    while True:
        break
    else:
        print("unreachable")
    """)
    assert run_source(source) == "1 1\n1 3\nouter done\nempty done\n"


def test_pyfront_rejects_loop_control_outside_loops():
    for statement in ("break", "continue"):
        with pytest.raises(ParseError, match="outside loop"):
            compile_py(statement)
    with pytest.raises(ParseError, match="outside loop"):
        compile_py("while True:\n    def invalid():\n        break")


def test_pyfront_function_locals_and_range_loop():
    src = textwrap.dedent("""
    def sum_range(n):
        total = 0
        for i in range(n):
            total = total + i
        return total

    print(sum_range(5))
    """)
    program = compile_py(src)
    vm = VM(program)
    buf = StringIO()
    with redirect_stdout(buf):
        vm.run()

    assert buf.getvalue() == "10\n"
    assert "total" not in vm.globals_
    assert "i" not in vm.globals_


def test_pyfront_global_declarations_and_local_shadowing():
    source = textwrap.dedent("""
    value = 10
    def update():
        global value
        value = value + 1
        return value

    def shadow(value):
        value = value + 2
        return value

    print(update(), value, shadow(3), value)
    """)
    assert run_source(source) == "11 11 5 11\n"


def test_pyfront_none_locals_and_comprehension_targets_have_correct_scope():
    source = textwrap.dedent("""
    item = 99
    def get_item():
        values = [item for item in [1, 2]]
        empty = None
        return item, empty

    print(get_item())
    """)
    assert run_source(source) == "(99, None)\n"


@pytest.mark.parametrize("engine", ["py", "cpp"])
def test_pyfront_uninitialized_local_reports_source_line(engine):
    from spacelang.vm_cpp import VM as CppVM

    vm_type = VM if engine == "py" else CppVM
    with pytest.raises(SpaceError, match="undefined local slot") as error:
        vm_type(compile_py("def read():\n    print(value)\n    value = 1\nread()")).run()
    assert error.value.line == 2


def test_pyfront_chained_and_nested_unpacking_assignments():
    source = textwrap.dedent("""
    first = second = 8
    (left, (middle, right)) = [1, (2, 3)]
    print(first, second, left, middle, right)
    """)
    assert run_source(source) == "8 8 1 2 3\n"


def test_pyfront_attribute_index_and_augmented_assignments():
    program = compile_py(
        "box.value = 4\n"
        "box.value += 3\n"
        "items[1] = box.value\n"
        "items[0] += 2\n"
        "print(box.value, items)\n"
    )
    vm = VM(program)
    vm.globals_["box"] = SimpleNamespace(value=0)
    vm.globals_["items"] = [5, 0]
    output = StringIO()
    with redirect_stdout(output):
        vm.run()
    assert output.getvalue() == "7 [7, 7]\n"


def test_pyfront_assignment_targets_work_inside_functions():
    program = compile_py(
        "def update(box, values):\n"
        "    box.value += 2\n"
        "    values[0], values[1] = values[1], values[0]\n"
        "    return box.value\n"
        "result = update(box, values)\n"
    )
    vm = VM(program)
    box = SimpleNamespace(value=3)
    values = [1, 2]
    vm.globals_.update(box=box, values=values)
    vm.run()
    assert vm.globals_["result"] == 5
    assert box.value == 5
    assert values == [2, 1]


@pytest.mark.parametrize(
    "source",
    ["left, right = [1]", "left, right = [1, 2, 3]"],
)
def test_pyfront_unpacking_requires_exact_number_of_values(source):
    with pytest.raises(SpaceError, match="unpack"):
        VM(compile_py(source)).run()


def test_pyfront_imports_booleans_and_builtin_keywords():
    src = textwrap.dedent("""
    import math
    from math import sqrt
    print(math.sqrt(16), sqrt(9), sep=":")
    print(not False and True)
    """)
    assert run_source(src) == "4.0:3.0\nTrue\n"


def test_pyfront_long_string_is_split_into_encodable_chunks():
    value = "x" * 2001
    program = compile_py(f"print({value!r})")
    string_lengths = [instr.args[0] for instr in program.instrs if instr.op.name == "PUSH_STR"]

    assert string_lengths == [1000, 1000, 1]
    assert run_source(f"print({value!r})") == f"{value}\n"


def test_pyfront_user_functions_support_defaults_and_keyword_arguments():
    source = textwrap.dedent("""
    def format_value(value, prefix="item", suffix="!"):
        return prefix + str(value) + suffix

    print(format_value(3))
    print(format_value(4, suffix="?"))
    print(format_value(value=5, prefix="value:"))
    print(format_value(suffix=".", value=6, prefix="n="))
    """)
    assert run_source(source) == "item3!\nitem4?\nvalue:5!\nn=6.\n"


@pytest.mark.parametrize(
    "source",
    [
        "def f(*args): return 0",
        "def f(a, /): return a",
        "def f(*, value): return value",
        "def f(**kwargs): return 0",
    ],
)
def test_pyfront_rejects_unsupported_function_forms(source):
    with pytest.raises(ParseError):
        compile_py(source)


@pytest.mark.parametrize(
    "source",
    [
        "def f(a): return a\nf()",
        "def f(a): return a\nf(1, 2)",
        "def f(a): return a\nf(a=1, a=2)",
        "def f(a): return a\nf(1, a=2)",
        "def f(a): return a\nf(b=1)",
        "def f(a=[]): return a",
        "def outer():\n    def inner(value=[]): return value\n    return inner()",
    ],
)
def test_pyfront_rejects_invalid_user_function_bindings(source):
    with pytest.raises(ParseError):
        compile_py(source)


def test_pyfront_nested_functions_capture_and_update_enclosing_locals():
    source = textwrap.dedent("""
    def make_counter(start):
        value = start
        def increment():
            nonlocal value
            value = value + 1
            return value
        return increment

    counter = make_counter(4)
    print(counter(), counter())
    """)
    assert run_source(source) == "5 6\n"


def test_pyfront_nested_function_closures_forward_cells_and_recurse():
    source = textwrap.dedent("""
    def make_factorial(limit):
        def wrapper():
            def factorial(value):
                if value < 2:
                    return 1
                return value * factorial(value - 1)
            return factorial(limit)
        return wrapper

    factorial = make_factorial(5)
    print(factorial())
    """)
    assert run_source(source) == "120\n"


def test_pyfront_nested_functions_support_defaults_and_keyword_arguments():
    source = textwrap.dedent("""
    def outer(base):
        def combine(left, right=3, suffix="!"):
            return base + left + right
        return combine(left=2, suffix="?", right=4)

    def with_default():
        def answer(value=42):
            return value
        return answer()

    print(outer(10), with_default())
    """)
    assert run_source(source) == "16 42\n"


def test_pyfront_nested_recursive_function_supports_keyword_arguments():
    source = textwrap.dedent("""
    def factorial():
        def calculate(value, result=1):
            if value < 2:
                return result
            return calculate(value=value - 1, result=result * value)
        return calculate(value=5)

    print(factorial())
    """)
    assert run_source(source) == "120\n"


def test_pyfront_nested_functions_without_captured_variables():
    source = "def outer():\n    def inner(value): return value + 1\n    return inner\nf = outer()\nprint(f(4))"
    assert run_source(source) == "5\n"


def test_pyfront_rejects_nonlocal_without_enclosing_binding():
    with pytest.raises(ParseError, match="no binding for nonlocal"):
        compile_py("def invalid():\n    nonlocal missing")


def test_pyfront_nested_function_calls_validate_argument_count():
    source = "def outer():\n    def inner(value): return value\n    return inner()\nouter()"
    with pytest.raises(ParseError, match="missing required argument 'value'"):
        compile_py(source)


def test_pyfront_rejects_keyword_arguments_for_saved_closure_values():
    source = "def outer():\n    def inner(value): return value\n    return inner\nf = outer()\nf(value=3)"
    with pytest.raises(ParseError, match="keyword arguments to callable objects are unsupported"):
        compile_py(source)


def test_pyfront_supports_simple_f_strings_and_list_comprehensions():
    source = textwrap.dedent("""
    def main(text):
        for i in range(3):
            print(f"Hello: {i}, {text}", sep=" ,  ")
        values = [i for i in range(5)]
        print(values)

    main("test")
    """)
    assert run_source(source) == (
        "Hello: 0, test\n"
        "Hello: 1, test\n"
        "Hello: 2, test\n"
        "[0, 1, 2, 3, 4]\n"
    )


def test_pyfront_list_comprehensions_accept_general_iterables():
    assert run_source(
        'print([value for value in (1, 2)])\n'
        'print([character for character in "xy"])'
    ) == "[1, 2]\n['x', 'y']\n"


def test_pyfront_list_comprehensions_support_filters():
    source = textwrap.dedent("""
    value = 99
    def selected():
        return [value for value in range(8) if value % 2 == 0 if value > 2]

    print(selected(), value)
    """)
    assert run_source(source) == "[4, 6] 99\n"


def test_pyfront_list_comprehensions_support_nested_generators():
    source = textwrap.dedent("""
    outer = 99
    result = [(outer, inner) for outer in range(3) if outer > 0
              for outer in [outer, outer + 10] if outer < 10
              for inner in range(outer)]
    print(result, outer)
    """)
    assert run_source(source) == "[(1, 0), (2, 0), (2, 1)] 99\n"


def test_pyfront_chained_comparisons_short_circuit_correctly():
    assert run_source("print(1 < 2 < 3)\nprint(1 < 2 > 3)") == "True\nFalse\n"
