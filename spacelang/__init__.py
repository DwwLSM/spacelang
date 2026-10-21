"""SpaceLang package."""

from .asm import assemble
from .disasm import disasm, disassemble
from .encoder import decode, encode
from .errors import (
    EncodingError,
    JumpOutOfRange,
    LexError,
    ParseError,
    RuntimeError,
    SpaceError,
    StackUnderflow,
    TypeError,
    UndefinedFunc,
    UndefinedModule,
    UndefinedName,
)
from .ir import Instr, OP, Program
from .lexer import tokenize
from .parser import parse

__all__ = [
    "EncodingError",
    "Instr",
    "JumpOutOfRange",
    "LexError",
    "OP",
    "ParseError",
    "Program",
    "RuntimeError",
    "SpaceError",
    "StackUnderflow",
    "TypeError",
    "UndefinedFunc",
    "UndefinedModule",
    "UndefinedName",
    "assemble",
    "decode",
    "disasm",
    "disassemble",
    "encode",
    "parse",
    "tokenize",
]
