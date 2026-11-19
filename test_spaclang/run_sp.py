import json
from pathlib import Path

import spacelang
from spacelang.vm_py import VM

program_path = Path(__file__).with_name("program.sp")
program = spacelang.parse(
    spacelang.tokenize(program_path.read_bytes().decode("ascii"))
)
names_path = program_path.with_suffix(".names.json")
program.names = json.loads(names_path.read_text(encoding="utf-8"))

VM(program).run()
