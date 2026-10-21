from contextlib import redirect_stdout
from io import StringIO
import textwrap

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
