from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import subprocess
import sys

from spacelang import compile_py
from spacelang.vm_py import VM


source = """\
def add(a, b):
    return a + b

print(add(2, 3))
"""

project_dir = Path(__file__).parent
source_path = project_dir / "program.py"
sp_path = project_dir / "program.sp"
spasm_path = project_dir / "program.spasm"
source_path.write_text(source, encoding="utf-8")

command = [sys.executable, "-m", "spacelang.main"]
subprocess.run(
    [*command, "compile-py", str(source_path), str(sp_path)],
    check=True,
)
subprocess.run(
    [*command, "disasm", str(sp_path), "--output", str(spasm_path)],
    check=True,
)
generated_output = subprocess.run(
    [*command, "run", str(sp_path)],
    check=True,
    capture_output=True,
    text=True,
).stdout
if generated_output != "5\n":
    raise AssertionError(f"generated .sp output was {generated_output!r}")

program = compile_py(source)
output = StringIO()
with redirect_stdout(output):
    VM(program).run()

print("SpaceLang package test output:")
print(output.getvalue(), end="")
print(f"Generated: {sp_path.name}, {spasm_path.name}")
