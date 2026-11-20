import pytest

from spacelang.asm import assemble
from spacelang.decoder import decode
from spacelang.web_bridge import annotate, canon, convert, trace_program, verify_py

PY_SOURCE = """\
def double(value):
    return value * 2


print(double(21))
"""


def _asm(source=PY_SOURCE):
    result = convert(source, "py")
    assert result["ok"] is True, result
    return result["texts"]["spasm"]


def test_py_to_spasm_and_sp_roundtrip():
    result = convert(PY_SOURCE, "py")
    assert result["ok"] is True
    texts = result["texts"]
    assert texts["spasm"].strip()
    # .sp is whitespace by definition: runs of spaces, one token per line.
    assert texts["sp"]
    assert set(texts["sp"]) <= {" ", "\n"}

    back = convert(texts["spasm"], "spasm")
    assert back["ok"] is True
    assert canon(decode(back["texts"]["sp"])) == canon(assemble(texts["spasm"]))


def test_spasm_to_sp_roundtrip():
    asm = _asm()
    result = convert(asm, "spasm")
    assert result["ok"] is True
    encoded = result["texts"]["sp"]
    assert set(result["texts"]) == {"sp"}
    again = convert(encoded, "sp")
    assert again["ok"] is True
    assert canon(assemble(again["texts"]["spasm"])) == canon(assemble(asm))


def test_convert_never_returns_python():
    for source, kind in ((PY_SOURCE, "py"), (_asm(), "spasm")):
        result = convert(source, kind)
        assert "py" not in result["texts"]


def test_convert_reports_unknown_source():
    result = convert(PY_SOURCE, "javascript")
    assert result["ok"] is False
    assert "unknown source kind" in result["error"]


def test_convert_reports_syntax_error():
    result = convert("def (", "py")
    assert result["ok"] is False
    assert result["texts"] == {}
    assert result["error"]


def test_convert_preserves_name_table():
    # Without include_names the assembly would come back with numeric slots.
    encoded = convert(PY_SOURCE, "py")["texts"]["sp"]
    assert ".name" in convert(encoded, "sp")["texts"]["spasm"]


def test_verify_py_accepts_equivalent_rewrite():
    asm = _asm()
    reformatted = """\
def double(value):
    return value*2


print(double(21))
"""
    result = verify_py(reformatted, asm)
    assert result["ok"] is True, result
    assert result["error"] is None


def test_verify_py_rejects_semantic_change():
    asm = _asm()
    changed = PY_SOURCE.replace("* 2", "* 3")
    result = verify_py(changed, asm)
    assert result["ok"] is False
    assert result["error"] == "not_equivalent"


def test_verify_py_reports_unparsable_python():
    result = verify_py("def (", _asm())
    assert result["ok"] is False
    assert result["error"] == "python_unparsable"


def test_verify_py_reports_unparsable_assembly():
    result = verify_py(PY_SOURCE, "NOT_AN_OPCODE")
    assert result["ok"] is False
    assert result["error"] == "assembly_unparsable"


def test_canon_ignores_line_numbers():
    program = assemble(_asm())
    shifted = type(program)(
        instrs=[type(program.instrs[0])(i.op, list(i.args), 999) for i in program.instrs],
        names=dict(program.names),
        labels=dict(program.labels),
        funcs=dict(program.funcs),
        try_table=list(program.try_table),
    )
    assert canon(program) == canon(shifted)


def test_annotate_restores_encoder_comments():
    asm = _asm()
    assert "; line=" in asm
    plain = "\n".join(line.split(" ; line=")[0] for line in asm.split("\n"))
    assert "; line=" not in plain

    result = annotate(plain)
    assert result["ok"] is True
    assert "; line=" in result["text"]
    assert canon(assemble(result["text"])) == canon(assemble(asm))


def test_annotate_reports_bad_assembly():
    result = annotate("BOGUS")
    assert result["ok"] is False
    assert result["text"] is None


def test_trace_program_still_works():
    result = trace_program("PUSH_INT 2\nHALT", is_asm=True)
    assert result["ok"] is True


@pytest.mark.parametrize("kind", ["py", "spasm", "sp"])
def test_every_source_kind_is_accepted(kind):
    source = {"py": PY_SOURCE, "spasm": _asm(), "sp": convert(PY_SOURCE, "py")["texts"]["sp"]}[kind]
    assert convert(source, kind)["ok"] is True
