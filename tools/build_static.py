#!/usr/bin/env python3
"""Prepare pinned Pyodide and pure-Python SpaceLang files for OPT_SP."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import tarfile
import tempfile
from urllib.request import urlretrieve


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "spacelang"
STATIC = PACKAGE / "opt_sp" / "static"
PYODIDE_VERSION = "0.26.2"
PYODIDE_FILES = (
    "pyodide.js",
    "pyodide.asm.wasm",
    "pyodide.asm.js",
    "pyodide-lock.json",
    "python_stdlib.zip",
)


def _check() -> int:
    required = [
        STATIC / "index.html",
        STATIC / "visualize.html",
        STATIC / "css" / "opt-sp.css",
        STATIC / "js" / "app.js",
        STATIC / "js" / "pyodide-loader.js",
        STATIC / "js" / "visualizer.js",
        STATIC / "js" / "spacelang-kernel.js",
        STATIC / "spacelang_pkg" / "manifest.json",
        *(STATIC / "pyodide" / name for name in PYODIDE_FILES),
    ]
    missing = [path for path in required if not path.is_file() or path.stat().st_size == 0]
    if missing:
        for path in missing:
            print(f"Missing or empty: {path.relative_to(ROOT)}")
        return 1
    manifest = json.loads((STATIC / "spacelang_pkg" / "manifest.json").read_text())
    if not manifest:
        print("SpaceLang module manifest is empty.")
        return 1
    for entry in manifest:
        module = STATIC / "spacelang_pkg" / entry["path"]
        if not module.is_file() or module.stat().st_size == 0:
            print(f"Missing or empty: {module.relative_to(ROOT)}")
            return 1
    print(f"OPT_SP static files verified ({len(required) + len(manifest)} required files).")
    return 0


def _copy_pyodide_distribution() -> None:
    url = (
        "https://github.com/pyodide/pyodide/releases/download/"
        f"{PYODIDE_VERSION}/pyodide-{PYODIDE_VERSION}.tar.bz2"
    )
    with tempfile.TemporaryDirectory(prefix="opt-sp-pyodide-") as temp_dir:
        archive_path = Path(temp_dir) / "pyodide.tar.bz2"
        print(f"Downloading Pyodide {PYODIDE_VERSION}…")
        urlretrieve(url, archive_path)
        destination = STATIC / "pyodide"
        destination.mkdir(parents=True, exist_ok=True)
        found = set()
        with tarfile.open(archive_path, "r:bz2") as archive:
            for member in archive.getmembers():
                filename = Path(member.name).name
                if filename not in PYODIDE_FILES or not member.isfile():
                    continue
                source = archive.extractfile(member)
                if source is None:
                    continue
                (destination / filename).write_bytes(source.read())
                found.add(filename)
        missing = set(PYODIDE_FILES) - found
        if missing:
            raise FileNotFoundError(
                f"Pyodide {PYODIDE_VERSION} archive is missing: {', '.join(sorted(missing))}"
            )


def _copy_spacelang_modules() -> None:
    destination = STATIC / "spacelang_pkg" / "spacelang"
    destination.mkdir(parents=True, exist_ok=True)
    manifest = []
    for source in sorted(PACKAGE.glob("*.py")):
        if source.name == "__init__.py":
            contents = "__version__ = '0.1.5'\n"
        else:
            contents = source.read_text(encoding="utf-8")
        target = destination / source.name
        target.write_text(contents, encoding="utf-8")
        relative = f"spacelang/{source.name}"
        manifest.append({
            "path": relative,
            "url": f"/spacelang_pkg/{relative}",
        })
    manifest_path = STATIC / "spacelang_pkg" / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="only verify built static assets")
    args = parser.parse_args()
    if args.check:
        return _check()

    _copy_pyodide_distribution()
    _copy_spacelang_modules()
    total_size = sum(path.stat().st_size for path in STATIC.rglob("*") if path.is_file())
    file_count = sum(1 for path in STATIC.rglob("*") if path.is_file())
    print(f"Prepared {file_count} files ({total_size / (1024 * 1024):.1f} MiB).")
    return _check()


if __name__ == "__main__":
    raise SystemExit(main())
