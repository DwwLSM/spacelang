from __future__ import annotations

import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PY_SOURCE = HERE / "quine.py"
SP_SOURCE = HERE / "quine.sp"
SPASM = HERE / "quine.spasm"


def _run_module(*args: str) -> None:
    subprocess.run(
        [sys.executable, "-m", *args],
        cwd=ROOT,
        check=True,
    )


def main() -> None:
    _run_module("spacelang.main", "compile-py", str(PY_SOURCE), str(SP_SOURCE))
    _run_module("spacelang.main", "disasm", str(SP_SOURCE), "-o", str(SPASM))
    print(f"Compiled {PY_SOURCE.name} to {SP_SOURCE.name} and {SPASM.name}.")


if __name__ == "__main__":
	main()
