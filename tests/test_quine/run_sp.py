from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from to_sp import HERE, PY_SOURCE, ROOT, SPASM, SP_SOURCE


SP_FROM_ASM = HERE / "quine_from_spasm.sp"
PY_COPY = HERE / "quine.copy.py"
SP_COPY = HERE / "quine_from_sp.copy.py"
SPASM_COPY = HERE / "quine_from_spasm.copy.py"


def _run(*args: str) -> subprocess.CompletedProcess[str]:
	return subprocess.run(
		[sys.executable, "-m", *args],
		cwd=ROOT,
		check=True,
		capture_output=True,
		text=True,
	)


def _run_python(path: Path) -> str:
	result = subprocess.run(
		[sys.executable, str(path)],
		cwd=ROOT,
		check=True,
		capture_output=True,
		text=True,
	)
	return result.stdout


def main() -> None:
	subprocess.run([sys.executable, str(HERE / "to_sp.py")], cwd=ROOT, check=True)

	expected = PY_SOURCE.read_text(encoding="utf-8")
	python_output = _run_python(PY_SOURCE)
	assert python_output == expected
	PY_COPY.write_text(python_output, encoding="utf-8")
	assert PY_COPY.read_bytes() == PY_SOURCE.read_bytes()

	sp_output = _run("spacelang.main", "run", str(SP_SOURCE)).stdout
	assert sp_output == expected
	SP_COPY.write_text(sp_output, encoding="utf-8")
	assert SP_COPY.read_bytes() == PY_SOURCE.read_bytes()

	_run("spacelang.main", "asm", str(SPASM), str(SP_FROM_ASM))
	assembled_output = _run("spacelang.main", "run", str(SP_FROM_ASM)).stdout
	assert assembled_output == expected
	SPASM_COPY.write_text(assembled_output, encoding="utf-8")
	assert SPASM_COPY.read_bytes() == PY_SOURCE.read_bytes()

	sys.stdout.write(expected)
	print("OK: Python, .sp, and .spasm quines print identical source; redirected output copies match.")


if __name__ == "__main__":
	main()
