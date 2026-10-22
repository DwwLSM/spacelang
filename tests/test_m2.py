import pytest

from spacelang import Instr, OP, Program, assemble, disasm
from spacelang.errors import ParseError


def test_assemble_labels_and_jumps():
    program = assemble(
        """
        .label start
        PUSH_INT 1
        JMP end
        .label end
        HALT
        """
    )
    assert program.labels["start"] == 0
    assert program.labels["end"] == 2
    assert program.instrs[1].op == OP.JMP
    assert program.instrs[1].args == [2]


def test_disasm_roundtrip_for_mnemonics():
    program = assemble(
        """
        .label loop
        PUSH_INT 2
        LOAD_GLOBAL sqrt
        CALL 1 1
        HALT
        """
    )
    text = disasm(program)
    assert ".label loop" in text
    assert "PUSH_INT 2" in text
    assert "HALT" in text


def test_disassembly_preserves_source_lines_spaces_names_and_labels():
    program = Program(
        instrs=[
            Instr(OP.PUSH_INT, [-1], line=7),
            Instr(OP.STORE_GLOBAL, [4], line=8),
            Instr(OP.JMP, [3], line=9),
            Instr(OP.HALT, line=10),
        ],
        names={"result": 4},
        labels={"start": 0},
    )

    listing = disasm(program)
    restored = assemble(listing)

    assert restored.names == program.names
    assert restored.labels == program.labels
    assert [(instr.op, instr.args, instr.line) for instr in restored.instrs] == [
        (instr.op, instr.args, instr.line) for instr in program.instrs
    ]
    assert "; line=7 spaces=7,1" in listing


def test_assemble_call_kw_operands():
    program = assemble("CALL_KW 0 2 1\n")
    assert program.instrs[0].args == [0, 2, 1]


def test_assembler_supports_quoted_strings_inline_comments_and_name_declarations():
    program = assemble(
        """
        .name greeting=9
        PUSH_STR "hello world" ; preserve quoted spaces
        STORE_GLOBAL greeting # inline comment
        HALT
        """
    )

    assert program.names == {"greeting": 9}
    assert program.instrs[0].args == [11, *map(ord, "hello world")]
    assert program.instrs[1].args == [9]


def test_enddef_must_match_function_boundary():
    program = assemble(
        """
        DEF 10000 0
        PUSH_INT 1
        RET
        .enddef
        HALT
        """
    )
    assert len(program.instrs) == 4
    assert program.funcs == {10000: (1, 3)}
    restored = assemble(disasm(program))
    assert restored.funcs == program.funcs
    assert [(instr.op, instr.args, instr.line) for instr in restored.instrs] == [
        (instr.op, instr.args, instr.line) for instr in program.instrs
    ]

    with pytest.raises(ParseError, match="does not match"):
        assemble("DEF 10000 0\n.enddef\nPUSH_INT 1\nHALT\n")
