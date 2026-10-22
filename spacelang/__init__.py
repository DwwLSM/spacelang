"""SpaceLang package."""

from .asm import assemble
from .compress import pack_bytes, pack_file, unpack_bytes, unpack_file
from .decoder import decode
from .disasm import disasm, disassemble
from .encoder import encode
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
from .names import NameTable
from .parser import parse
from .peephole import optimize
from .pyfront import compile_py
from .quine import quine

__all__ = [
    "EncodingError",
    "Instr",
    "JumpOutOfRange",
    "LexError",
    "OP",
    "NameTable",
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
    "pack_bytes",
    "pack_file",
    "compile_py",
    "optimize",
    "quine",
    "tokenize",
    "unpack_bytes",
    "unpack_file",
]
