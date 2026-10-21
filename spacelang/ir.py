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
