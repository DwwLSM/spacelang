#!/usr/bin/env python3
"""Embed a .sp file into a C++ header as a byte array.

    python native/make_blob.py native/spc.sp native/spc_blob.h

Used by native/build_compiler.ps1 to bake the SpaceLang compiler into
compiler.exe.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Embed a .sp program into a C++ header.")
    parser.add_argument("program", type=Path)
    parser.add_argument("header", type=Path)
    args = parser.parse_args(argv)

    data = args.program.read_bytes()
    rows = []
    for start in range(0, len(data), 20):
        chunk = data[start:start + 20]
        rows.append("    " + ", ".join(f"0x{byte:02x}" for byte in chunk) + ",")
    args.header.write_text(
        "// Generated from {name} by native/make_blob.py -- do not edit.\n"
        "static const unsigned char kCompilerBlob[] = {{\n{rows}\n}};\n"
        "static const unsigned long kCompilerBlobSize = sizeof(kCompilerBlob);\n".format(
            name=args.program.name, rows="\n".join(rows)
        ),
        encoding="utf-8",
    )
    print(f"{args.program} ({len(data):,} bytes) -> {args.header}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
