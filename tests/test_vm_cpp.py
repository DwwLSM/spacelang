import pytest

pytest.importorskip("spacelang._spacelang_cpp")

from spacelang import Instr, OP, Program
from spacelang.errors import RuntimeError as SpaceRuntimeError, SpaceError
from spacelang.pyfront import compile_py
from spacelang.vm_cpp import VM
from spacelang.vm_py import VM as PythonVM


def test_native_vm_runs_integer_arithmetic_and_stack_ops():
    for vm_type in (PythonVM, VM):
        program = Program(
            instrs=[
                Instr(OP.PUSH_INT, [6]),
                Instr(OP.PUSH_INT, [7]),
                Instr(OP.OP, [3]),
                Instr(OP.STACK, [1]),
                Instr(OP.STACK, [3]),
                Instr(OP.HALT),
            ]
        )
        vm = vm_type(program)
        assert vm.run() == 42
        assert vm.stack == []


def test_native_vm_fallthrough_matches_reference_return_value():
    program = Program(instrs=[Instr(OP.PUSH_INT, [42])])
    for vm_type in (PythonVM, VM):
        vm = vm_type(program)
        assert vm.run() is None
        assert vm.stack == [42]


def test_native_vm_runs_conditional_jumps():
    program = Program(
        instrs=[
            Instr(OP.PUSH_INT, [0]),
            Instr(OP.JZ, [3]),
            Instr(OP.PUSH_INT, [1]),
            Instr(OP.PUSH_INT, [2]),
            Instr(OP.HALT),
        ]
    )
    for vm_type in (PythonVM, VM):
        assert vm_type(program).run() == 2

    jump_nonzero_program = Program(
        instrs=[
            Instr(OP.PUSH_INT, [1]),
            Instr(OP.JNZ, [3]),
            Instr(OP.PUSH_INT, [0]),
            Instr(OP.PUSH_INT, [1]),
            Instr(OP.HALT),
        ]
    )
    for vm_type in (PythonVM, VM):
        assert vm_type(jump_nonzero_program).run() == 1


@pytest.mark.parametrize(
    ("operation", "values", "expected"),
    [
        (2, [1, 2], 1),
        (4, [1, 2], 1),
        (5, [1, 2, 3], 1),
    ],
)
def test_native_vm_supports_remaining_stack_operations(operation, values, expected):
    instructions = [Instr(OP.PUSH_INT, [value]) for value in values]
    instructions.extend([Instr(OP.STACK, [operation]), Instr(OP.HALT)])
    for vm_type in (PythonVM, VM):
        assert vm_type(Program(instrs=instructions)).run() == expected


def test_native_vm_uses_python_integer_fallback_on_overflow():
    cases = [
        ((1 << 63) - 1, 1, 1, 1 << 63),
        (-(1 << 63), -1, 1, -((1 << 63) + 1)),
        ((1 << 63) - 1, -1, 2, 1 << 63),
        (-(1 << 63), -1, 3, 1 << 63),
        (-3, -4, 3, 12),
    ]
    for left, right, operation, expected in cases:
        program = Program(
            instrs=[
                Instr(OP.PUSH_INT, [left]),
                Instr(OP.PUSH_INT, [right]),
                Instr(OP.OP, [operation]),
                Instr(OP.HALT),
            ]
        )
        for vm_type in (PythonVM, VM):
            assert vm_type(program).run() == expected


def test_native_vm_supports_division_and_comparison():
    divided = Program(
        instrs=[
            Instr(OP.PUSH_INT, [9]),
            Instr(OP.PUSH_INT, [2]),
            Instr(OP.OP, [4]),
            Instr(OP.HALT),
        ]
    )
    assert VM(divided).run() == 4.5

    compared = Program(
        instrs=[
            Instr(OP.PUSH_INT, [2]),
            Instr(OP.PUSH_INT, [3]),
            Instr(OP.OP, [7]),
            Instr(OP.HALT),
        ]
    )
    assert VM(compared).run() is True


def test_native_vm_calls_python_builtins_methods_and_user_functions(capsys):
    VM(compile_py('print("hello")')).run()
    assert capsys.readouterr().out == "hello\n"

    VM(compile_py('print("left", "right", sep="-")')).run()
    assert capsys.readouterr().out == "left-right\n"

    program = compile_py(
        "def add(a, b): return a + b\n"
        "result = add(20, 22)\n"
        "print(result)"
    )
    VM(program).run()
    assert capsys.readouterr().out == "42\n"


def test_native_vm_imports_modules_and_calls_methods():
    program = compile_py("import math\nresult = math.sqrt(16)")
    for vm_type in (PythonVM, VM):
        vm = vm_type(program)
        vm.run()
        assert vm.globals_["result"] == 4.0

    program = compile_py('result = "spacelang".upper()')
    for vm_type in (PythonVM, VM):
        vm = vm_type(program)
        vm.run()
        assert vm.globals_["result"] == "SPACELANG"


def test_native_vm_try_catch_finally_state_machine():
    program = Program(
        instrs=[
            Instr(OP.TRY, [5, 8]),
            Instr(OP.PUSH_STR, [1, ord("x")]),
            Instr(OP.CALL, [3, 1]),
            Instr(OP.END_TRY),
            Instr(OP.NOP),
            Instr(OP.PUSH_INT, [1]),
            Instr(OP.STORE_GLOBAL, [0]),
            Instr(OP.END_TRY),
            Instr(OP.PUSH_INT, [1]),
            Instr(OP.STORE_GLOBAL, [1]),
            Instr(OP.END_TRY),
            Instr(OP.HALT),
        ],
        names={"caught": 0, "finalized": 1},
        funcs={},
        try_table=[(0, 11, 5, 8)],
    )
    for vm_type in (PythonVM, VM):
        vm = vm_type(program)
        vm.run()
        assert vm.globals_ == {"caught": 1, "finalized": 1}


def test_native_vm_finally_exception_replaces_pending_exception():
    program = Program(
        instrs=[
            Instr(OP.TRY, [0, 5]),
            Instr(OP.PUSH_STR, [1, ord("x")]),
            Instr(OP.CALL, [3, 1]),
            Instr(OP.END_TRY),
            Instr(OP.NOP),
            Instr(OP.PUSH_STR, [1, ord("y")]),
            Instr(OP.CALL, [3, 1]),
            Instr(OP.END_TRY),
            Instr(OP.HALT),
        ],
        funcs={},
        try_table=[(0, 8, 0, 5)],
    )

    for vm_type in (PythonVM, VM):
        with pytest.raises(SpaceRuntimeError, match="'y'"):
            vm_type(program).run()


def test_native_vm_matches_catch_only_and_finally_only_transitions():
    catch_program = Program(
        instrs=[
            Instr(OP.TRY, [3, 0]),
            Instr(OP.PUSH_STR, [1, ord("x")]),
            Instr(OP.CALL, [3, 1]),
            Instr(OP.PUSH_INT, [1]),
            Instr(OP.STORE_GLOBAL, [0]),
            Instr(OP.END_TRY),
            Instr(OP.HALT),
        ],
        names={"caught": 0},
        try_table=[(0, 6, 3, 0)],
    )
    finally_program = Program(
        instrs=[
            Instr(OP.TRY, [0, 3]),
            Instr(OP.PUSH_INT, [7]),
            Instr(OP.END_TRY),
            Instr(OP.PUSH_INT, [1]),
            Instr(OP.STORE_GLOBAL, [0]),
            Instr(OP.END_TRY),
            Instr(OP.HALT),
        ],
        names={"finalized": 0},
        try_table=[(0, 6, 0, 3)],
    )
    for vm_type in (PythonVM, VM):
        caught = vm_type(catch_program)
        caught.run()
        assert caught.globals_ == {"caught": 1}

        finalized = vm_type(finally_program)
        finalized.run()
        assert finalized.globals_ == {"finalized": 1}


@pytest.mark.parametrize(
    ("op_id", "left", "right", "expected"),
    [
        (1, 7, 2, 9),
        (2, 7, 2, 5),
        (3, 7, 2, 14),
        (4, 7, 2, 3.5),
        (5, -7, 3, 2),
        (6, 7, 7, True),
        (7, 2, 3, True),
        (8, 3, 2, True),
        (9, 2, 3, True),
        (10, 2, 3, True),
        (11, 3, 2, True),
    ],
)
def test_native_vm_supports_every_numeric_operator(op_id, left, right, expected):
    program = Program(
        instrs=[
            Instr(OP.PUSH_INT, [left]),
            Instr(OP.PUSH_INT, [right]),
            Instr(OP.OP, [op_id]),
            Instr(OP.HALT),
        ]
    )
    for vm_type in (PythonVM, VM):
        assert vm_type(program).run() == expected


def test_native_vm_object_calls_containers_raise_and_setup_with():
    callable_program = Program(
        instrs=[
            Instr(OP.LOAD_GLOBAL, [0]),
            Instr(OP.PUSH_INT, [5]),
            Instr(OP.CALL_OBJ, [1]),
            Instr(OP.HALT),
        ],
        names={"callable": 0},
    )
    for vm_type in (PythonVM, VM):
        callable_vm = vm_type(callable_program)
        callable_vm.globals_["callable"] = lambda value: value * 2
        assert callable_vm.run() == 10

    container_program = Program(
        instrs=[
            Instr(OP.PUSH_INT, [1]),
            Instr(OP.PUSH_INT, [2]),
            Instr(OP.BUILD_LIST, [2]),
            Instr(OP.PUSH_INT, [3]),
            Instr(OP.BUILD_LIST, [1]),
            Instr(OP.CONCAT, [2]),
            Instr(OP.HALT),
        ]
    )
    for vm_type in (PythonVM, VM):
        assert vm_type(container_program).run() == [1, 2, 3]

    concat_program = Program(
        instrs=[
            Instr(OP.PUSH_STR, [2, ord("a"), ord("b")]),
            Instr(OP.PUSH_STR, [1, ord("c")]),
            Instr(OP.CONCAT, [2]),
            Instr(OP.HALT),
        ]
    )
    for vm_type in (PythonVM, VM):
        assert vm_type(concat_program).run() == "abc"

    tuple_program = Program(
        instrs=[
            Instr(OP.PUSH_INT, [1]),
            Instr(OP.PUSH_INT, [2]),
            Instr(OP.BUILD_TUPLE, [2]),
            Instr(OP.PUSH_INT, [0]),
            Instr(OP.INDEX, [0]),
            Instr(OP.HALT),
        ]
    )
    for vm_type in (PythonVM, VM):
        assert vm_type(tuple_program).run() == 1

    raise_program = Program(
        instrs=[Instr(OP.LOAD_GLOBAL, [0]), Instr(OP.RAISE)],
        names={"error": 0},
    )
    for vm_type in (PythonVM, VM):
        raise_vm = vm_type(raise_program)
        raise_vm.globals_["error"] = ValueError("native raise")
        with pytest.raises(SpaceRuntimeError, match="native raise"):
            raise_vm.run()

    with_program = Program(instrs=[Instr(OP.PUSH_STR, [1, ord("x")]), Instr(OP.SETUP_WITH), Instr(OP.HALT)])
    for vm_type in (PythonVM, VM):
        assert vm_type(with_program).run() is None


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        ([b"left", bytearray(b"right")], b"leftright"),
        ([[1, 2], [3]], [1, 2, 3]),
        ([(1, 2), (3,)], (1, 2, 3)),
    ],
)
def test_native_vm_concat_matches_reference_for_homogeneous_categories(values, expected):
    names = {f"value{index}": index for index in range(len(values))}
    instructions = [Instr(OP.LOAD_GLOBAL, [index]) for index in range(len(values))]
    instructions.extend([Instr(OP.CONCAT, [len(values)]), Instr(OP.HALT)])
    program = Program(instrs=instructions, names=names)

    for vm_type in (PythonVM, VM):
        vm = vm_type(program)
        vm.globals_.update({f"value{index}": value for index, value in enumerate(values)})
        assert vm.run() == expected


def test_native_vm_concat_matches_reference_error_for_mixed_categories():
    program = Program(
        instrs=[
            Instr(OP.LOAD_GLOBAL, [0]),
            Instr(OP.LOAD_GLOBAL, [1]),
            Instr(OP.CONCAT, [2]),
            Instr(OP.HALT),
        ],
        names={"text": 0, "number": 1},
    )
    errors = []
    for vm_type in (PythonVM, VM):
        vm = vm_type(program)
        vm.globals_.update({"text": "value", "number": 3})
        with pytest.raises(SpaceError) as error:
            vm.run()
        errors.append(error.value)

    assert type(errors[0]) is type(errors[1])
    assert (errors[0].line, errors[0].ip, errors[0].msg) == (
        errors[1].line,
        errors[1].ip,
        errors[1].msg,
    )


def test_native_vm_preserves_none_in_function_arguments_and_locals():
    program = Program(
        instrs=[
            Instr(OP.DEF, [10000, 0]),
            Instr(OP.LOAD_ARG, [0]),
            Instr(OP.RET),
            Instr(OP.NOP),
            Instr(OP.NOP),
            Instr(OP.NOP),
            Instr(OP.CALL, [0, 0]),
            Instr(OP.CALL, [10000, 1]),
            Instr(OP.HALT),
        ],
        funcs={10000: (1, 6)},
    )
    for vm_type in (PythonVM, VM):
        assert vm_type(program).run() is None


def test_native_vm_normalizes_host_exceptions_like_reference_vm():
    program = compile_py("int('not an integer')\n")
    errors = []
    for vm_type in (PythonVM, VM):
        with pytest.raises(SpaceRuntimeError) as error:
            vm_type(program).run()
        errors.append(error.value)

    assert type(errors[0]) is type(errors[1])
    assert errors[0].line == errors[1].line
    assert errors[0].ip == errors[1].ip
    assert errors[0].msg == errors[1].msg


@pytest.mark.parametrize(
    "program",
    [
        Program(instrs=[Instr(OP.OP, [1])]),
        Program(instrs=[Instr(OP.LOAD_GLOBAL, [0], line=7)], names={"missing": 0}),
        Program(instrs=[Instr(OP.JMP, [10])]),
        Program(instrs=[Instr(OP.CALL, [10000, 0])]),
        Program(instrs=[Instr(OP.STACK, [99])]),
        Program(instrs=[Instr(OP.OP, [99])]),
        Program(instrs=[Instr(OP.CALL, [99, 0])]),
    ],
)
def test_native_vm_matches_reference_space_errors(program):
    errors = []
    for vm_type in (PythonVM, VM):
        with pytest.raises(SpaceError) as error:
            vm_type(program).run()
        errors.append(error.value)

    assert type(errors[0]) is type(errors[1])
    assert errors[0].line == errors[1].line
    assert errors[0].ip == errors[1].ip
    assert errors[0].msg == errors[1].msg
