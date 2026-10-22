from __future__ import annotations

from ._spacelang_cpp import VM as _NativeVM
from .ir import Program


class VM:
    def __init__(self, program: Program):
        self._vm = _NativeVM(program)

    @property
    def stack(self):
        return self._vm.stack

    @property
    def globals_(self):
        return self._vm.globals

    def run(self):
        return self._vm.run()


__all__ = ["VM"]
