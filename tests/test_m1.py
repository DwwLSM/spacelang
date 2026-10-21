import pytest

from spacelang import OP, encode, parse, tokenize
from spacelang.errors import LexError, ParseError


def test_tokenize_basic_and_crlf():
    assert tokenize("   \n  \n\n") == [(3, 1), (2, 2), (0, 3)]
    assert tokenize("\r\n  \n") == [(0, 1), (2, 2)]


def test_tokenize_invalid_character():
    with pytest.raises(LexError):
        tokenize(" \tx\n")


def test_parse_simple_program():
    program = parse([7, 4, 5, 3])
    assert len(program.instrs) == 2
    assert program.instrs[0].op == OP.PUSH_INT
    assert program.instrs[0].args == [2]
    assert program.instrs[1].op == OP.OP
    assert program.instrs[1].args == [3]


def test_parse_and_encode_roundtrip():
    source = [7, 10, 1, 2, 1]
    program = parse(source)
    encoded = encode(program)
    reparsed = parse(tokenize(encoded))
    assert [(instr.op, instr.args) for instr in program.instrs] == [
        (OP.PUSH_INT, [5]),
        (OP.CALL, [2, 1]),
    ]
    assert [(instr.op, instr.args) for instr in reparsed.instrs] == [
        (OP.PUSH_INT, [5]),
        (OP.CALL, [2, 1]),
    ]


def test_unknown_opcode_and_missing_arg():
    with pytest.raises(ParseError):
        parse([99])
    with pytest.raises(ParseError):
        parse([7])
