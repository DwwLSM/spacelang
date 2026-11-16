import json
from urllib.request import urlopen

from spacelang.encoder import encode
from spacelang.pyfront import compile_py
from spacelang.web_bridge import trace_program
from spacelang.opt_sp import server


def test_trace_program_basic():
    result = trace_program("PUSH_INT 2\nPUSH_INT 3\nOP 1\nHALT", is_asm=True)
    assert result["ok"] is True
    assert len(result["trace"]) >= 3
    required = {"ip", "opcode", "operand_stack", "call_stack", "globals", "heap", "output"}
    assert all(required <= step.keys() for step in result["trace"])


def test_trace_program_error():
    result = trace_program("BOGUS", is_asm=True)
    assert result["ok"] is False
    assert result["error"]


def test_trace_jsonable():
    result = trace_program("PUSH_INT 2\nPUSH_INT 3\nOP 1\nHALT", is_asm=True)
    json.dumps(result)


def test_trace_captures_output_and_nested_heap():
    result = trace_program("answer = [[1, 2], [3, 4]]\nprint(answer)", is_asm=False)
    assert result["ok"] is True
    assert result["trace"][-1]["output"] == "[[1, 2], [3, 4]]\n"
    heap = result["trace"][-1]["heap"]
    assert any(node["type"] == "list" and node["refs"] for node in heap.values())


def test_trace_program_encoded_sp():
    source = encode(compile_py("print(2 + 3)"), include_names=True)
    result = trace_program(source, is_sp=True)
    assert result["ok"] is True
    assert result["trace"][-1]["output"] == "5\n"


def test_server_returns_url():
    httpd, url = server(open_browser=False, blocking=False, port=0)
    try:
        with urlopen(f"{url}/index.html") as response:
            assert response.status == 200
            assert b"OPT_SP" in response.read()
    finally:
        httpd.shutdown()
        httpd.server_close()
