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


def test_pyfront_expands_call_arguments_for_top_level_and_nested_functions():
    source = textwrap.dedent("""
    def make_options(**options):
        return options

    def collect(first, second=2, *rest, marker="!", **options):
        return (first, second, rest, marker, options)

    def outer():
        def inner(value, **options):
            return (value, options)
        values = [3]
        options = make_options(label="nested")
        return inner(*values, **options)

    values = [1, 4, 5]
    options = make_options(marker="?", color="blue")
    print(collect(*values, **options))
    print(collect(**make_options(first=7)))
    print(outer())
    """)
    assert run_source(source) == (
        "(1, 4, (5,), '?', {'color': 'blue'})\n"
        "(7, 2, (), '!', {})\n"
        "(3, {'label': 'nested'})\n"
    )


def test_pyfront_expands_builtin_call_arguments():
    source = textwrap.dedent("""
    values = [[1, 2, 3]]
    print(len(*values))
    print(*["left", "right"], sep=":")
    """)
    assert run_source(source) == "3\nleft:right\n"


@pytest.mark.parametrize(
    ("source", "message"),
    [
        (
            "def collect(**options): return options\n"
            "def make(**options): return options\n"
            "collect(**make(value=1), **make(value=2))",
            "multiple values for keyword argument 'value'",
        ),
        (
            "def collect(**options): return options\n"
            "collect(**[1, 2])",
            r"argument after \*\* must be a mapping",
        ),
    ],
)
@pytest.mark.parametrize("engine", ["py", "cpp"])
def test_pyfront_expanded_keyword_arguments_validate_mapping(source, message, engine):
    from spacelang.vm_cpp import VM as CppVM

    vm_type = VM if engine == "py" else CppVM
    with pytest.raises(SpaceError, match=message):
        vm_type(compile_py(source)).run()


@pytest.mark.parametrize(
    "source",
    [
        "def f(a, /): return a",
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


def test_pyfront_saved_closures_support_keyword_arguments_and_defaults():
    source = textwrap.dedent("""
    def outer(base):
        def combine(left, right=3, suffix="!"):
            return base + left + right
        return combine

    fn = outer(10)
    print(fn(2), fn(2, right=4), fn(left=3, suffix="?", right=5))
    """)
    assert run_source(source) == "15 16 18\n"


@pytest.mark.parametrize(
    ("call", "message"),
    [
        ("fn(1, unknown=2)", "unexpected keyword argument 'unknown'"),
        ("fn(1, value=2)", "multiple values for argument 'value'"),
        ("fn()", "missing required argument 'value'"),
    ],
)
def test_pyfront_saved_closures_validate_keyword_bindings(call, message):
    source = f"def outer():\n    def inner(value): return value\n    return inner\nfn = outer()\n{call}"
    with pytest.raises(SpaceError, match=message):
        run_source(source)


def test_pyfront_keyword_only_parameters_on_top_level_functions():
    source = textwrap.dedent("""
    def format_value(value, *, prefix, suffix="!"):
        return prefix + str(value) + suffix

    print(format_value(3, prefix="v="), format_value(4, suffix="?", prefix="x="))
    """)
    assert run_source(source) == "v=3! x=4?\n"


def test_pyfront_saved_closures_support_keyword_only_parameters():
    source = textwrap.dedent("""
    def make_renderer(prefix):
        def render(value=3, *, marker="!", suffix, end="."):
            return prefix + str(value) + marker + suffix + end
        return render

    render = make_renderer("<")
    print(render(3, suffix=">", marker="?"), render(4, suffix="]"), render(suffix=")"))
    """)
    assert run_source(source) == "<3?>. <4!]. <3!).\n"


def test_pyfront_nested_function_direct_call_accepts_keyword_only_arguments():
    source = textwrap.dedent("""
    def outer():
        def inner(value, *, suffix):
            return str(value) + suffix
        return inner(2, suffix="!")

    print(outer())
    """)
    assert run_source(source) == "2!\n"


def test_pyfront_collects_extra_positional_arguments():
    source = textwrap.dedent("""
    def collect(first, *rest):
        return (first, rest)

    def format_values(first=1, *rest, label, suffix="!"):
        return (first, rest, label, suffix)

    print(collect(1), collect(1, 2, 3))
    print(format_values(label="x"), format_values(5, 6, 7, label="y"))
    """)
    assert run_source(source) == "(1, ()) (1, (2, 3))\n(1, (), 'x', '!') (5, (6, 7), 'y', '!')\n"


def test_pyfront_saved_closure_collects_extra_positional_arguments():
    source = textwrap.dedent("""
    def make_collector(prefix):
        def collect(first, *rest, marker="!"):
            return (prefix, first, rest, marker)
        return collect

    collect = make_collector("<")
    print(collect(1), collect(1, 2, 3, marker="?"))
    """)
    assert run_source(source) == "('<', 1, (), '!') ('<', 1, (2, 3), '?')\n"


def test_pyfront_nested_closure_can_capture_varargs():
    source = textwrap.dedent("""
    def outer(*values):
        def inner():
            return values
        return inner

    inner = outer(1, 2, 3)
    print(inner())
    """)
    assert run_source(source) == "(1, 2, 3)\n"


def test_pyfront_collects_extra_keyword_arguments():
    source = textwrap.dedent("""
    def collect(value, **options):
        return (value, options)

    def collect_all(first, *rest, **options):
        return (first, rest, options)

    def collect_keyword_only(*, label, **options):
        return (label, options)

    print(collect(1, color="blue", size=3))
    print(collect_all(1, 2, 3, color="green"))
    print(collect_all(1))
    print(collect_keyword_only(label="item", active=True))
    """)
    assert run_source(source) == (
        "(1, {'color': 'blue', 'size': 3})\n"
        "(1, (2, 3), {'color': 'green'})\n"
        "(1, (), {})\n"
        "('item', {'active': True})\n"
    )


def test_pyfront_saved_closure_collects_extra_keyword_arguments():
    source = textwrap.dedent("""
    def make_collector(prefix):
        def collect(value, *rest, marker="!", **options):
            return (prefix, value, rest, marker, options)
        return collect

    collect = make_collector("<")
    print(collect(1, 2, 3, marker="?", color="red", size=4))
    """)
    assert run_source(source) == "('<', 1, (2, 3), '?', {'color': 'red', 'size': 4})\n"


def test_pyfront_nested_function_direct_call_passes_extra_keywords():
    source = textwrap.dedent("""
    def outer():
        def inner(value, **options):
            return (value, options)
        return inner(2, flag=True)

    print(outer())
    """)
    assert run_source(source) == "(2, {'flag': True})\n"


@pytest.mark.parametrize(
    ("source", "message"),
    [
        ("def f(*, name): return name\nf('x')", "too many positional arguments"),
        ("def f(*, name): return name\nf()", "missing required argument 'name'"),
        ("def f(value, *, name): return name\nf(1, name=2, value=3)", "multiple values for argument 'value'"),
    ],
)
def test_pyfront_keyword_only_parameter_binding_errors(source, message):
    with pytest.raises(ParseError, match=message):
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
