from spacelang.ir import Instr, OP, Program
from spacelang.encoder import encode
from spacelang.peephole import optimize
from spacelang.pyfront import compile_py
from spacelang.vm_py import VM


def test_constant_folding_runs_arithmetic_program_correctly():
    program = compile_py("print(1 + 1)")
    optimized = optimize(program, constant_pool=False)
    assert [(instr.op, instr.args) for instr in optimized.instrs] == [
        (OP.PUSH_INT, [2]),
        (OP.CALL, [0, 1]),
        (OP.STACK, [3]),
        (OP.HALT, []),
    ]


def test_string_folding_preserves_runtime_output(capsys):
    program = compile_py('print("hello " + "world")')
    optimized = optimize(program, constant_pool=False)
    assert sum(instr.op == OP.PUSH_STR for instr in optimized.instrs) == 1
    VM(optimized).run()
    assert capsys.readouterr().out == "hello world\n"


def test_dead_code_after_jump_is_removed_and_target_remapped():
    program = Program(
        instrs=[
            Instr(OP.JMP, [3]),
            Instr(OP.PUSH_INT, [99]),
            Instr(OP.PUSH_INT, [98]),
            Instr(OP.PUSH_INT, [7]),
            Instr(OP.HALT),
        ]
    )
    optimized = optimize(program, constant_pool=False)
    assert [(instr.op, instr.args) for instr in optimized.instrs] == [
        (OP.JMP, [1]),
        (OP.PUSH_INT, [7]),
        (OP.HALT, []),
    ]
    assert VM(optimized).run() == 7


def test_constant_pool_emits_each_repeated_integer_once():
    optimized = optimize(compile_py("print(10000)\nprint(10000)"))
    assert sum(instr.op == OP.PUSH_INT and instr.args == [10000] for instr in optimized.instrs) == 1
    vm = VM(optimized)
    vm.run()
    assert vm.globals_["__const0"] == 10000


def test_constant_pool_initializes_before_control_flow_can_skip_its_first_use(capsys):
    program = Program(
        instrs=[
            Instr(OP.PUSH_INT, [1]),
            Instr(OP.JNZ, [4]),
            Instr(OP.PUSH_INT, [42]),
            Instr(OP.CALL, [0, 1]),
            Instr(OP.PUSH_INT, [42]),
            Instr(OP.CALL, [0, 1]),
            Instr(OP.HALT),
        ],
        names={},
        funcs={},
        try_table=[],
    )
    optimized = optimize(program)

    VM(optimized).run()

    assert capsys.readouterr().out == "42\n"


def test_compress_source_factors_large_single_use_integer():
    for value in (1_000_000, 1_000_000_007, -1_000_000_007, -(1 << 63)):
        program = Program(
            instrs=[Instr(OP.PUSH_INT, [value]), Instr(OP.HALT)],
            names={},
            funcs={},
            try_table=[],
        )
        optimized = optimize(
            program,
            constant_pool=False,
            dead_code=False,
            compress_source=True,
        )

        assert all(
            instr.op != OP.PUSH_INT or abs(instr.args[0]) <= 32767
            for instr in optimized.instrs
        )
        assert VM(optimized).run() == value
        if value == 1_000_000:
            compressed_length = len(encode(optimized))
            canonical_length = 7 + 2 * 1_000_000 + 29 + 4
            assert compressed_length * 50 < canonical_length
