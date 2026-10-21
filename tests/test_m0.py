from spacelang import OP, Program, SpaceError, TypeError
from spacelang.errors import EncodingError
from spacelang.ir import Instr


def test_import_and_ir_basics():
    assert OP.PUSH_INT == 7
    assert OP.HALT == 29
    assert len(OP) == 30


def test_error_types_have_line_and_ip():
    err = TypeError(line=3, ip=4, msg="bad")
    assert err.line == 3
    assert err.ip == 4
    assert "TypeError" in str(err)


def test_program_dataclass_fields():
    program = Program(
        instrs=[Instr(OP.PUSH_INT, [42], line=1)],
        names={"x": 1},
        labels={"start": 0},
        funcs={10000: (0, 1)},
        try_table=[(0, 1, 2, 3)],
    )
    assert program.funcs[10000] == (0, 1)
    assert program.try_table == [(0, 1, 2, 3)]


def test_module_exports():
    assert SpaceError is not None
    assert EncodingError is not None
