from __future__ import annotations

from .errors import LexError


def tokenize(src: str) -> list[tuple[int, int]]:
    """Split a SpaceLang source into (value, line) tokens.

    Each newline terminates a token; CRLF is normalized to LF, and stray CR raises
    LexError with the offending line and byte offset.
    """
    if src == "":
        return []

    if "\r" in src:
        if "\r\n" in src:
            src = src.replace("\r\n", "\n")
        bad = src.find("\r")
        if bad != -1:
            line = src.count("\n", 0, bad) + 1
            raise LexError(line=line, ip=bad, msg="stray carriage return")

    tokens: list[tuple[int, int]] = []
    current = 0
    line = 1
    for idx, ch in enumerate(src):
        if ch == " ":
            current += 1
        elif ch == "\n":
            tokens.append((current, line))
            current = 0
            line += 1
        else:
            raise LexError(line=line, ip=idx, msg=f"invalid character: {ord(ch)!r}")
    if src.endswith("\n"):
        return tokens
    tokens.append((current, line))
    return tokens
