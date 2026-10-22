from __future__ import annotations

from collections import Counter, deque
from typing import Callable

from .ir import Instr, OP, Program


def _copy_instruction(instr: Instr) -> Instr:
    return Instr(instr.op, list(instr.args), line=instr.line)


def _branch_targets(program: Program) -> set[int]:
    targets = {
        int(instr.args[0])
        for instr in program.instrs
        if instr.op in {OP.JMP, OP.JZ, OP.JNZ} and instr.args
    }
    for instr in program.instrs:
        if instr.op == OP.TRY and instr.args:
            targets.add(int(instr.args[0]))
            if len(instr.args) > 1 and int(instr.args[1]) != 0:
                targets.add(int(instr.args[1]))
    return targets


def _remap_program(
    program: Program,
    instrs: list[Instr],
    index_map: list[int],
) -> Program:
    def remap(ip: int) -> int:
        if 0 <= ip < len(index_map):
            return index_map[ip]
        if ip == len(index_map):
            return len(instrs)
        return ip

    for instr in instrs:
        if instr.op in {OP.JMP, OP.JZ, OP.JNZ} and instr.args:
            instr.args[0] = remap(int(instr.args[0]))
        elif instr.op == OP.TRY:
            instr.args[0] = remap(int(instr.args[0]))
            if int(instr.args[1]) != 0:
                instr.args[1] = remap(int(instr.args[1]))
    return Program(
        instrs=instrs,
        names=dict(program.names),
        labels={name: remap(ip) for name, ip in program.labels.items()},
        funcs={
            func_id: (remap(entry), remap(end))
            for func_id, (entry, end) in program.funcs.items()
        },
        try_table=[
            (
                remap(try_ip),
                remap(end_ip),
                remap(catch_ip),
                remap(finally_ip) if finally_ip else 0,
            )
            for try_ip, end_ip, catch_ip, finally_ip in program.try_table
        ],
    )


def _fold_pass(program: Program) -> Program:
    instrs = program.instrs
    targets = _branch_targets(program)
    output: list[Instr] = []
    index_map = [0] * (len(instrs) + 1)
    i = 0
    while i < len(instrs):
        index_map[i] = len(output)
        folded: list[Instr] | None = None
        consumed = 1

        if (
            i + 2 < len(instrs)
            and i + 1 not in targets
            and i + 2 not in targets
            and instrs[i].op == OP.PUSH_INT
            and instrs[i + 1].op == OP.PUSH_INT
            and instrs[i + 2].op == OP.OP
        ):
            left = int(instrs[i].args[0])
            right = int(instrs[i + 1].args[0])
            op_id = int(instrs[i + 2].args[0])
            operation: Callable[[], int | bool] | None = {
                1: lambda: left + right,
                2: lambda: left - right,
                3: lambda: left * right,
                5: lambda: left % right,
                6: lambda: left == right,
                7: lambda: left < right,
                8: lambda: left > right,
                9: lambda: left != right,
                10: lambda: left <= right,
                11: lambda: left >= right,
            }.get(op_id)
            if operation is not None and not (op_id == 5 and right == 0):
                value = operation()
                if isinstance(value, bool):
                    folded = [
                        Instr(OP.PUSH_INT, [int(value)], line=instrs[i].line),
                        Instr(OP.CALL, [6, 1], line=instrs[i].line),
                    ]
                else:
                    folded = [Instr(OP.PUSH_INT, [value], line=instrs[i].line)]
                consumed = 3

        if (
            folded is None
            and i + 2 < len(instrs)
            and instrs[i].op == OP.PUSH_STR
            and instrs[i + 1].op == OP.PUSH_STR
            and (
                (
                    instrs[i + 2].op == OP.CONCAT
                    and int(instrs[i + 2].args[0]) == 2
                )
                or (
                    instrs[i + 2].op == OP.OP
                    and int(instrs[i + 2].args[0]) == 1
                )
            )
            and i + 1 not in targets
            and i + 2 not in targets
        ):
            first = [int(value) for value in instrs[i].args[1:]]
            second = [int(value) for value in instrs[i + 1].args[1:]]
            if len(first) == int(instrs[i].args[0]) and len(second) == int(instrs[i + 1].args[0]):
                chars = first + second
                chunks = [chars[start:start + 1000] for start in range(0, len(chars), 1000)] or [[]]
                folded = [
                    Instr(OP.PUSH_STR, [len(chunk), *chunk], line=instrs[i].line)
                    for chunk in chunks
                ]
                if len(chunks) > 1:
                    folded.append(Instr(OP.CONCAT, [len(chunks)], line=instrs[i].line))
                consumed = 3

        if folded is None:
            output.append(_copy_instruction(instrs[i]))
        else:
            output.extend(folded)
            for skipped in range(i + 1, i + consumed):
                index_map[skipped] = index_map[i]
        i += consumed
    index_map[len(instrs)] = len(output)
    return _remap_program(program, output, index_map)


def _reachable_instructions(program: Program) -> set[int]:
    count = len(program.instrs)
    if count == 0:
        return set()
    functions_by_id = program.funcs
    work = deque([0, *(entry for entry, _ in functions_by_id.values())])
    reachable: set[int] = set()

    while work:
        ip = work.popleft()
        if ip < 0 or ip >= count or ip in reachable:
            continue
        reachable.add(ip)
        instr = program.instrs[ip]
        op = OP(instr.op)
        if op == OP.HALT or op == OP.RET:
            continue
        if op == OP.JMP:
            work.append(int(instr.args[0]))
            continue
        if op in {OP.JZ, OP.JNZ}:
            work.append(int(instr.args[0]))
            work.append(ip + 1)
            continue
        if op == OP.TRY:
            work.append(int(instr.args[0]))
            if int(instr.args[1]) != 0:
                work.append(int(instr.args[1]))
        if op == OP.DEF:
            func_id = int(instr.args[0])
            work.append(functions_by_id.get(func_id, (ip + 1, ip + 1))[1])
            continue
        if op in {OP.CALL, OP.CALL_KW}:
            func_id = int(instr.args[0])
            if func_id in functions_by_id:
                work.append(functions_by_id[func_id][0])
        work.append(ip + 1)
    return reachable


def _dead_code_pass(program: Program) -> Program:
    reachable = _reachable_instructions(program)
    if len(reachable) == len(program.instrs):
        return program

    index_map = [0] * (len(program.instrs) + 1)
    kept: list[Instr] = []
    for ip, instr in enumerate(program.instrs):
        index_map[ip] = len(kept)
        if ip in reachable:
            kept.append(_copy_instruction(instr))
    index_map[len(program.instrs)] = len(kept)
    return _remap_program(program, kept, index_map)


def _constant_pool(program: Program) -> Program:
    counts = Counter(
        int(instr.args[0])
        for instr in program.instrs
        if instr.op == OP.PUSH_INT
    )
    repeated = {value for value, count in counts.items() if count > 1}
    if not repeated:
        return program

    names = dict(program.names)
    next_id = max(names.values(), default=-1) + 1
    pool_names: dict[int, int] = {}
    initializers: list[Instr] = []
    for instr in program.instrs:
        if instr.op != OP.PUSH_INT:
            continue
        value = int(instr.args[0])
        if value not in repeated or value in pool_names:
            continue
        base_name = f"__const{len(pool_names)}"
        name = base_name
        suffix = 0
        while name in names:
            suffix += 1
            name = f"{base_name}_{suffix}"
        name_id = next_id
        next_id += 1
        names[name] = name_id
        pool_names[value] = name_id
        initializers.extend(
            [
                Instr(OP.PUSH_INT, [value], line=instr.line),
                Instr(OP.STORE_GLOBAL, [name_id], line=instr.line),
            ]
        )

    index_map = [0] * (len(program.instrs) + 1)
    output: list[Instr] = []
    for ip, instr in enumerate(program.instrs):
        index_map[ip] = len(initializers) + len(output)
        if instr.op == OP.PUSH_INT and int(instr.args[0]) in pool_names:
            output.append(Instr(OP.LOAD_GLOBAL, [pool_names[int(instr.args[0])]], line=instr.line))
        else:
            output.append(_copy_instruction(instr))
    index_map[len(program.instrs)] = len(initializers) + len(output)
    rewritten = _remap_program(program, [*initializers, *output], index_map)
    rewritten.names = names
    return rewritten


def _compress_source(program: Program) -> Program:
    counts = Counter(
        int(instr.args[0])
        for instr in program.instrs
        if instr.op == OP.PUSH_INT
    )
    replacements: dict[int, list[Instr]] = {}
    for ip, instr in enumerate(program.instrs):
        if instr.op != OP.PUSH_INT:
            continue
        value = int(instr.args[0])
        if abs(value) <= 1000 or counts[value] != 1:
            continue
        remaining = abs(value)
        factors: list[int] = []
        divisor = 2
        while divisor <= 32767 and divisor * divisor <= remaining:
            while remaining % divisor == 0:
                factors.append(divisor)
                remaining //= divisor
            divisor += 1
        if remaining <= 32767 and remaining > 1:
            factors.append(remaining)
        if len(factors) >= 2:
            if value < 0:
                factors[0] = -factors[0]
            replacement = [Instr(OP.PUSH_INT, [factors[0]], line=instr.line)]
            for factor in factors[1:]:
                replacement.append(Instr(OP.PUSH_INT, [factor], line=instr.line))
                replacement.append(Instr(OP.OP, [3], line=instr.line))
        elif abs(value) <= 32767:
            continue
        else:
            digits = []
            remaining = abs(value)
            while remaining:
                digits.append(remaining % 32767)
                remaining //= 32767
            digits.reverse()
            sign = -1 if value < 0 else 1
            replacement = [Instr(OP.PUSH_INT, [sign * digits[0]], line=instr.line)]
            for digit in digits[1:]:
                replacement.extend(
                    [
                        Instr(OP.PUSH_INT, [32767], line=instr.line),
                        Instr(OP.OP, [3], line=instr.line),
                    ]
                )
                if digit:
                    replacement.extend(
                        [
                            Instr(OP.PUSH_INT, [sign * digit], line=instr.line),
                            Instr(OP.OP, [1], line=instr.line),
                        ]
                    )
        replacements[ip] = replacement

    if not replacements:
        return program

    old_to_new = [0] * (len(program.instrs) + 1)
    output: list[Instr] = []
    for ip, instr in enumerate(program.instrs):
        old_to_new[ip] = len(output)
        output.extend(replacements.get(ip, [_copy_instruction(instr)]))
    old_to_new[len(program.instrs)] = len(output)
    return _remap_program(program, output, old_to_new)


def optimize(
    program: Program,
    *,
    constant_pool: bool = True,
    dead_code: bool = True,
    compress_source: bool = False,
) -> Program:
    optimized = _fold_pass(program)
    if dead_code:
        optimized = _dead_code_pass(optimized)
    if constant_pool:
        optimized = _constant_pool(optimized)
    if compress_source:
        optimized = _compress_source(optimized)
    return optimized


__all__ = ["optimize"]
