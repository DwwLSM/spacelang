from contextlib import redirect_stdout
from io import StringIO
import textwrap

import pytest

from spacelang.errors import ParseError
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


def test_pyfront_for_range_and_sequence_indexing():
    src = textwrap.dedent("""
    for i in range(2, 8, 2):
        print(i)
    print([1, 2, 3][1])
    """)
    assert run_source(src) == "2\n4\n6\n2\n"


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


def test_pyfront_user_function_keyword_arguments_are_rejected():
    source = "def identity(value): return value\nidentity(value=1)"
    with pytest.raises(ParseError, match="keyword arguments to user functions"):
        compile_py(source)


@pytest.mark.parametrize(
    "source",
    [
        "def f(a=1): return a",
        "def f(*args): return 0",
        "def f(a, /): return a",
        "def outer():\n    def inner(): return 1\n    return inner()",
    ],
)
def test_pyfront_rejects_unsupported_function_forms(source):
    with pytest.raises(ParseError):
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


def test_pyfront_chained_comparisons_short_circuit_correctly():
    assert run_source("print(1 < 2 < 3)\nprint(1 < 2 > 3)") == "True\nFalse\n"
