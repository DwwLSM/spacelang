import pytest

from spacelang import Instr, OP, Program, decode, encode, parse, tokenize
from spacelang.errors import EncodingError, LexError, ParseError


def test_tokenize_basic_and_crlf():
    assert tokenize("   \n  \n\n") == [(3, 1), (2, 2), (0, 3)]
    assert tokenize("\r\n  \n") == [(0, 1), (2, 2)]


def test_tokenize_invalid_character():
    with pytest.raises(LexError):
        tokenize(" \tx\n")


def test_parser_preserves_instruction_lines_and_reports_them_on_errors():
    program = parse([(OP.PUSH_INT, 4), (2, 5), (OP.NOP, 6), (OP.HALT, 7)])
    assert [instr.line for instr in program.instrs] == [4, 6, 7]

    with pytest.raises(ParseError) as error:
        parse([(OP.PUSH_INT, 8)])
    assert error.value.line == 8


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
        (OP.HALT, []),
    ]


def test_decode_accepts_canonical_source():
    program = decode(encode(parse([OP.PUSH_INT, 2, OP.HALT])))
    assert [(instr.op, instr.args) for instr in program.instrs] == [
        (OP.PUSH_INT, [1]),
        (OP.HALT, []),
    ]


def test_call_kw_roundtrip_has_three_operands():
    program = parse([OP.CALL_KW, 0, 2, 1])
    assert program.instrs[0].args == [0, 2, 1]
    reparsed = parse(tokenize(encode(program)))
    assert reparsed.instrs[0].args == [0, 2, 1]


def test_parser_matches_try_catch_finally_end_markers():
    program = parse([
        OP.TRY, 3, 5,
        OP.NOP, OP.END_TRY,
        OP.NOP, OP.END_TRY,
        OP.NOP, OP.END_TRY,
        OP.HALT,
    ])
    assert program.try_table == [(0, 7, 3, 5)]

    function = parse([OP.DEF, 10000, 0, OP.PUSH_INT, 14, OP.HALT])
    assert [(instr.op, instr.args) for instr in function.instrs] == [
        (OP.DEF, [10000, 0]),
        (OP.PUSH_INT, [7]),
        (OP.PUSH_INT, [0]),
        (OP.RET, []),
        (OP.HALT, []),
    ]
    assert function.funcs[10000] == (1, 4)

    with pytest.raises(ParseError):
        parse([OP.TRY, 0, 0, OP.NOP])
    with pytest.raises(ParseError):
        parse([OP.END_TRY])

    nested = parse([
        OP.TRY, 6, 0,
        OP.NOP,
        OP.TRY, 0, 0,
        OP.NOP, OP.END_TRY,
        OP.END_TRY,
        OP.NOP, OP.END_TRY,
        OP.HALT,
    ])
    assert nested.try_table == [(2, 5, 0, 0), (0, 8, 6, 0)]


def test_unknown_opcode_and_missing_arg():
    with pytest.raises(ParseError):
        parse([99])
    with pytest.raises(ParseError):
        parse([7])


def test_encoder_appends_halt_and_enforces_token_limits():
    assert encode(parse([OP.PUSH_INT, 0])).endswith("\n" + " " * int(OP.HALT) + "\n")

    with pytest.raises(EncodingError):
        encode(Program(instrs=[Instr(OP.PUSH_INT, [32768])]))
    with pytest.raises(EncodingError):
        encode(Program(instrs=[Instr(OP.PUSH_STR, [1, 65536])]))
    with pytest.raises(EncodingError):
        encode(Program(instrs=[Instr(OP.OP, [1.5])]))
