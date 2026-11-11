"""Intermediate representation for the SpaceLang compiler."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum


class OP(IntEnum):
    NOP = 0
    CALL = 1
    CALL_KW = 2
    CALL_OBJ = 3
    IMPORT = 4
    OP = 5
    STACK = 6
    PUSH_INT = 7
    PUSH_STR = 8
    LOAD_GLOBAL = 9
    STORE_GLOBAL = 10
    GET_ATTR = 11
    CALL_METHOD = 12
    INDEX = 13
    BUILD_LIST = 14
    BUILD_TUPLE = 15
    CONCAT = 16
    DEF = 17
    RET = 18
    LOAD_ARG = 19
    LOAD_LOCAL = 20
    STORE_LOCAL = 21
    JMP = 22
    JZ = 23
    JNZ = 24
    RAISE = 25
    TRY = 26
    END_TRY = 27
    SETUP_WITH = 28
    HALT = 29
    GET_ITER = 30
    FOR_ITER = 31
    STORE_ATTR = 32
    STORE_INDEX = 33
    UNPACK_SEQUENCE = 34
    PUSH_NONE = 35
    MAKE_CLOSURE = 36
    CELLIFY = 37
    LOAD_CELL_REF = 38
    LOAD_DEREF = 39
    CALL_OBJ_KW = 40
    MAKE_CLOSURE_SIG = 41
    MAKE_CLOSURE_KWONLY = 42
    MAKE_CLOSURE_ARGS = 43
    BUILD_DICT = 44
    CALL_OBJ_EX = 45
    CALL_BUILTIN_EX = 46
    LIST_EXTEND = 47
    DICT_MERGE = 48
    MAKE_CLOSURE_POSONLY = 49


@dataclass(slots=True)
class Instr:
    op: OP | int
    args: list[int | str] = field(default_factory=list)
    line: int = 0


@dataclass(slots=True)
class Program:
    instrs: list[Instr] = field(default_factory=list)
    names: dict[str, int] = field(default_factory=dict)
    labels: dict[str, int] = field(default_factory=dict)
    funcs: dict[int, tuple[int, int]] = field(default_factory=dict)
    try_table: list[tuple[int, int, int, int]] = field(default_factory=list)


__all__ = ["OP", "Instr", "Program"]
