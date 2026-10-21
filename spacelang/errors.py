"""Error types for the SpaceLang project."""

from __future__ import annotations


class SpaceError(Exception):
    """Base class for all SpaceLang errors."""

    def __init__(self, line: int | None = None, ip: int | None = None, msg: str = ""):
        self.line = line
        self.ip = ip
        self.msg = msg
        super().__init__(msg)

    def __str__(self) -> str:
        context = []
        if self.line is not None:
            context.append(f"line={self.line}")
        if self.ip is not None:
            context.append(f"ip={self.ip}")
        if context:
            return f"{self.__class__.__name__}({', '.join(context)}, msg={self.msg})"
        return f"{self.__class__.__name__}({self.msg})"


class LexError(SpaceError):
    pass


class ParseError(SpaceError):
    pass


class RuntimeError(SpaceError):
    pass


class TypeError(SpaceError):
    pass


class StackUnderflow(SpaceError):
    pass


class UndefinedFunc(SpaceError):
    pass


class UndefinedName(SpaceError):
    pass


class UndefinedModule(SpaceError):
    pass


class JumpOutOfRange(SpaceError):
    pass


class EncodingError(SpaceError):
    pass
