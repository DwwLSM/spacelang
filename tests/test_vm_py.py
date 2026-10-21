import pytest

from spacelang import OP, Program, Instr
from spacelang.errors import JumpOutOfRange, StackUnderflow, TypeError, UndefinedName
from spacelang.vm_py import VM


def _program(instrs):
    return Program(instrs=[Instr(op, args) for op, args in instrs], names={}, labels={}, funcs={}, try_table=[])


def test_vm_arithmetic_and_stack_ops():
    vm = VM(_program([(OP.PUSH_INT, [2]), (OP.PUSH_INT, [3]), (OP.OP, [1]), (OP.HALT, [])]))
    assert vm.run() == 5

    vm = VM(_program([(OP.PUSH_INT, [9]), (OP.STACK, [1]), (OP.HALT, [])]))
    assert vm.run() == 9


def test_vm_stack_underflow_and_jump_bounds():
    vm = VM(_program([(OP.OP, [1]), (OP.HALT, [])]))
    with pytest.raises(StackUnderflow):
        vm.run()

    vm = VM(_program([(OP.JMP, [10]), (OP.HALT, [])]))
    with pytest.raises(JumpOutOfRange):
        vm.run()


def test_vm_concat_and_local_lookup():
    vm = VM(_program([(OP.PUSH_STR, [5, 104, 105, 0, 0]), (OP.HALT, [])]))
    assert vm.run() == "hi\x00\x00"

    vm = VM(_program([(OP.LOAD_LOCAL, [0]), (OP.HALT, [])]))
    with pytest.raises(UndefinedName):
        vm.run()


def test_vm_call_kw_rejects_user_functions():
    vm = VM(_program([(OP.PUSH_INT, [1]), (OP.PUSH_INT, [2]), (OP.CALL_KW, [10000, 0, 0]), (OP.HALT, [])]))
    with pytest.raises(TypeError):
        vm.run()
