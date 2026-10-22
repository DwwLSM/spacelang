from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEMO = ROOT / "demo.py"
BINARY = ROOT / "demo.sp"
ASSEMBLY = ROOT / "demo.spasm"
REBUILT = ROOT / "demo_from_spasm.sp"


def run_spacelang(*args: str) -> None:
    subprocess.run([sys.executable, "-m", "spacelang.main", *args], cwd=ROOT, check=True)


def main() -> None:
    # Convert the Python demo into the binary SpaceLang form and the assembly listing.
    run_spacelang("compile-py", str(DEMO), str(BINARY))
    run_spacelang("disasm", str(BINARY), "-o", str(ASSEMBLY))

    # Run the compiled program and then the assembly-generated equivalent.
    run_spacelang("run", str(BINARY))
    run_spacelang("asm", str(ASSEMBLY), str(REBUILT))
    run_spacelang("run", str(REBUILT))


if __name__ == "__main__":
    main()