import math

import pytest

from spacelang import OP, Program, Instr
from spacelang.errors import (
    JumpOutOfRange,
    RuntimeError,
    StackUnderflow,
    TypeError,
    UndefinedName,
)
from spacelang.pyfront import compile_py
from spacelang.vm_py import VM


def _program(instrs):
    return Program(instrs=[Instr(op, args) for op, args in instrs], names={}, labels={}, funcs={}, try_table=[])


def test_vm_arithmetic_and_stack_ops():
    vm = VM(_program([(OP.PUSH_INT, [2]), (OP.PUSH_INT, [3]), (OP.OP, [1]), (OP.HALT, [])]))
    assert vm.run() == 5

    vm = VM(_program([(OP.PUSH_INT, [9]), (OP.STACK, [1]), (OP.HALT, [])]))
    assert vm.run() == 9

    vm = VM(_program([
        (OP.PUSH_INT, [1]),
        (OP.PUSH_INT, [2]),
        (OP.STACK, [4]),
        (OP.STACK, [5]),
        (OP.STACK, [3]),
        (OP.HALT, []),
    ]))
    assert vm.run() == 1

    vm = VM(_program([
        (OP.PUSH_INT, [1]),
        (OP.PUSH_INT, [2]),
        (OP.STACK, [2]),
        (OP.HALT, []),
    ]))
    assert vm.run() == 1


def test_vm_stack_underflow_and_jump_bounds():
    vm = VM(_program([(OP.OP, [1]), (OP.HALT, [])]))
    with pytest.raises(StackUnderflow):
        vm.run()

    vm = VM(_program([(OP.JMP, [10]), (OP.HALT, [])]))
    with pytest.raises(JumpOutOfRange):
        vm.run()

    vm = VM(_program([(OP.JMP, [1])]))
    with pytest.raises(JumpOutOfRange):
        vm.run()


def test_vm_concat_and_local_lookup():
    vm = VM(_program([(OP.PUSH_STR, [5, 104, 105, 0, 0]), (OP.HALT, [])]))
    assert vm.run() == "hi\x00\x00"

    vm = VM(_program([(OP.LOAD_LOCAL, [0]), (OP.HALT, [])]))
    with pytest.raises(UndefinedName):
        vm.run()

    vm = VM(Program(instrs=[Instr(OP.LOAD_GLOBAL, [0]), Instr(OP.HALT)], names={"missing": 0}))
    with pytest.raises(UndefinedName):
        vm.run()


def test_vm_call_kw_rejects_user_functions():
    vm = VM(_program([(OP.PUSH_INT, [1]), (OP.PUSH_INT, [2]), (OP.CALL_KW, [10000, 0, 0]), (OP.HALT, [])]))
    with pytest.raises(TypeError):
        vm.run()

    vm = VM(_program([(OP.PUSH_STR, [1, ord("x")]), (OP.CALL, [3, 1]), (OP.HALT, [])]))
    with pytest.raises(RuntimeError):
        vm.run()


def test_vm_call_obj_import_and_module_import_idempotence():
    vm = VM(Program(
        instrs=[
            Instr(OP.PUSH_STR, [2, ord("h"), ord("i")]),
            Instr(OP.GET_ATTR, [0]),
            Instr(OP.CALL_OBJ, [0]),
            Instr(OP.HALT),
        ],
        names={"upper": 0},
    ))
    assert vm.run() == "HI"

    vm = VM(_program([(OP.IMPORT, [0]), (OP.IMPORT, [0]), (OP.HALT, [])]))
    first = vm.run()
    assert vm.globals_["math"] is first


def test_vm_concat_dispatches_supported_container_types():
    programs = [
        (["left", "right"], "leftright"),
        ([[1, 2], [3]], [1, 2, 3]),
        ([(1, 2), (3,)], (1, 2, 3)),
        ([b"ab", b"c"], b"abc"),
    ]
    for values, expected in programs:
        names = {f"value{index}": index for index in range(len(values))}
        instrs = []
        for index in range(len(values)):
            instrs.append(Instr(OP.LOAD_GLOBAL, [index]))
        instrs.extend([Instr(OP.CONCAT, [len(values)]), Instr(OP.HALT)])
        vm = VM(Program(instrs=instrs, names=names))
        vm.globals_.update({f"value{index}": value for index, value in enumerate(values)})
        assert vm.run() == expected

    vm = VM(Program(
        instrs=[Instr(OP.LOAD_GLOBAL, [0]), Instr(OP.LOAD_GLOBAL, [1]), Instr(OP.CONCAT, [2]), Instr(OP.HALT)],
        names={"text": 0, "number": 1},
    ))
    vm.globals_.update({"text": "value", "number": 3})
    with pytest.raises(TypeError):
        vm.run()


def test_vm_runs_recursive_functions_imports_and_file_io(tmp_path):
    source = """
def fact(n):
    if n <= 1:
        return 1
    return n * fact(n - 1)

result = fact(100)
"""
    vm = VM(compile_py(source))
    vm.run()
    assert vm.globals_["result"] == math.factorial(100)

    math_vm = VM(compile_py("import math\nresult = math.sqrt(16)"))
    math_vm.run()
    assert math_vm.globals_["result"] == 4.0

    path = tmp_path / "roundtrip.txt"
    file_vm = VM(compile_py(
        f"f = open({str(path)!r}, 'w')\nf.write('data')\nf.close()\n"
        f"f = open({str(path)!r}, 'r')\ncontents = f.read()\nf.close()"
    ))
    file_vm.run()
    assert file_vm.globals_["contents"] == "data"


def test_vm_catches_call_errors_and_runs_finally():
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

    vm = VM(program)
    vm.run()

    assert vm.globals_ == {"caught": 1, "finalized": 1}


def test_vm_unwinds_user_function_frames_before_catching_in_caller():
    program = Program(
        instrs=[
            Instr(OP.DEF, [10000, 0]),
            Instr(OP.PUSH_STR, [1, ord("x")]),
            Instr(OP.CALL, [3, 1]),
            Instr(OP.RET),
            Instr(OP.TRY, [7, 0]),
            Instr(OP.CALL, [10000, 0]),
            Instr(OP.END_TRY),
            Instr(OP.PUSH_INT, [1]),
            Instr(OP.STORE_GLOBAL, [0]),
            Instr(OP.END_TRY),
            Instr(OP.HALT),
        ],
        names={"caught": 0},
        funcs={10000: (1, 4)},
        try_table=[(4, 10, 7, 0)],
    )

    vm = VM(program)
    vm.run()

    assert vm.globals_["caught"] == 1
    assert vm.call_stack == []
