from __future__ import annotations

from .ir import Program
from .lexer import tokenize
from .parser import parse


def decode(source: str) -> Program:
    return parse(tokenize(source))


__all__ = ["decode"]
