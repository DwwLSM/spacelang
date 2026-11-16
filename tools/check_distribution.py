#!/usr/bin/env python3
"""Verify built package archives contain all generated OPT_SP static assets."""

from __future__ import annotations

import argparse
from pathlib import Path
import tarfile
import zipfile

from build_static import STATIC


PACKAGE_STATIC = "spacelang/opt_sp/static/"


def _static_files() -> set[str]:
    return {
        path.relative_to(STATIC).as_posix()
        for path in STATIC.rglob("*")
        if path.is_file()
    }


def _archive_files(path: Path) -> set[str]:
    if path.suffix == ".whl":
        with zipfile.ZipFile(path) as archive:
            return {
                name[len(PACKAGE_STATIC):]
                for name in archive.namelist()
                if name.startswith(PACKAGE_STATIC)
                and archive.getinfo(name).file_size > 0
            }
    if path.name.endswith((".tar.gz", ".tgz")):
        with tarfile.open(path, "r:gz") as archive:
            files = set()
            for member in archive.getmembers():
                if not member.isfile() or member.size == 0 or PACKAGE_STATIC not in member.name:
                    continue
                files.add(member.name.split(PACKAGE_STATIC, 1)[1])
            return files
    raise ValueError(f"Unsupported distribution archive: {path}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archives", nargs="+", type=Path)
    args = parser.parse_args()

    required = _static_files()
    for path in args.archives:
        present = _archive_files(path)
        missing = sorted(required - present)
        if missing:
            for name in missing:
                print(f"{path}: missing {PACKAGE_STATIC}{name}")
            return 1
        print(f"{path}: verified {len(required)} OPT_SP static files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
