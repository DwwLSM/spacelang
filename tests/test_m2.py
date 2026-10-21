from spacelang import OP, assemble, disasm


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
