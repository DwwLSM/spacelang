from spacelang import OP, Program, SpaceError, TypeError, compile_py, pack_bytes, quine
from spacelang.errors import EncodingError
from spacelang.ir import Instr
from spacelang.names import NameTable


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
    assert compile_py is not None
    assert pack_bytes is not None
    assert quine is not None


def test_name_table_roundtrip_and_interning():
    names = NameTable({"known": 4})
    assert names.intern("known") == 4
    assert names.intern("next") == 5
    assert names.lookup(5) == "next"
    assert NameTable.from_dict(names.to_dict()).to_dict() == names.to_dict()
