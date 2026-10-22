from __future__ import annotations

import gzip
import os
from pathlib import Path

from .errors import EncodingError


def pack_bytes(source: bytes) -> bytes:
    return gzip.compress(source, mtime=0)


def unpack_bytes(source: bytes) -> bytes:
    try:
        return gzip.decompress(source)
    except (OSError, EOFError) as exc:
        raise EncodingError(line=0, ip=0, msg=f"invalid gzip SpaceLang file: {exc}") from exc


def pack_file(src: str | os.PathLike[str], dst: str | os.PathLike[str]) -> None:
    source_path = Path(src)
    destination_path = Path(dst)
    compressed = pack_bytes(source_path.read_bytes())
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    destination_path.write_bytes(compressed)


def unpack_file(src: str | os.PathLike[str], dst: str | os.PathLike[str]) -> None:
    source_path = Path(src)
    destination_path = Path(dst)
    data = unpack_bytes(source_path.read_bytes())
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    destination_path.write_bytes(data)


__all__ = ["pack_bytes", "unpack_bytes", "pack_file", "unpack_file"]
