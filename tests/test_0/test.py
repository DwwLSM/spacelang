from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEMO = ROOT / "demo.py"
BINARY = ROOT / "demo.sp"
ASSEMBLY = ROOT / "demo.spasm"
REBUILT = ROOT / "demo_from_spasm.sp"


def run_spacelang(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "spacelang.main", *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )


def main() -> None:
    # Convert the Python demo into the binary SpaceLang form and the assembly listing.
    run_spacelang("compile-py", str(DEMO), str(BINARY), "--compress-source")
    run_spacelang("disasm", str(BINARY), "-o", str(ASSEMBLY))

    # Run the compiled program and then the assembly-generated equivalent.
    python_output = subprocess.run(
        [sys.executable, str(DEMO)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    expected_lines = python_output.stdout.splitlines()
    binary_output = run_spacelang("run", str(BINARY))
    assert binary_output.stdout.splitlines() == expected_lines

    run_spacelang("asm", str(ASSEMBLY), str(REBUILT))
    rebuilt_output = run_spacelang("run", str(REBUILT))
    assert rebuilt_output.stdout.splitlines() == expected_lines

    print("\n".join(expected_lines))
    print("OK: .sp and .spasm round-trip execution matches the demo output.")


if __name__ == "__main__":
    main()