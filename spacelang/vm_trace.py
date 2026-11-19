"""Instruction trace schema:

Trace = list[Step]
Step = {
    "step": int, "ip": int, "opcode": str, "arg": int | str | None,
    "source_line": int | None, "operand_stack": list[Value],
    "call_stack": list[Frame], "globals": dict[str, Value],
    "heap": dict[str, HeapObj], "output": str, "error": str | None,
}
Value = {"type": str, "repr": str, "ref": str | None}
Frame = {"func": str, "locals": dict[str, Value]}
HeapObj = {"type": str, "repr": str, "refs": list[str]}
"""

from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
from types import FunctionType, ModuleType
from typing import Any

from .ir import Instr, OP
from .vm_py import Cell, Closure, Frame, VM


class TracedVM(VM):
    def __init__(self, program):
        super().__init__(program)
        self.trace: list[dict[str, Any]] = []
        self._output = StringIO()
        self._executing_ip = 0

    def _before_step(self, instr: Instr) -> None:
        self._executing_ip = self.ip

    @staticmethod
    def _is_heap_object(value: Any) -> bool:
        return (
            isinstance(value, (list, dict, tuple, set))
            or (
                hasattr(value, "__dict__")
                and not isinstance(value, (ModuleType, FunctionType, type))
            )
        )

    @staticmethod
    def _safe_repr(value: Any) -> str:
        try:
            return repr(value)
        except Exception as exc:
            return f"<{type(value).__name__} repr failed: {exc}>"

    def _snapshot_value(self, value: Any) -> dict[str, str | None]:
        return {
            "type": type(value).__name__,
            "repr": self._safe_repr(value),
            "ref": str(id(value)) if self._is_heap_object(value) else None,
        }

    def _children(self, value: Any) -> list[Any]:
        if isinstance(value, dict):
            return [item for pair in value.items() for item in pair]
        if isinstance(value, (list, tuple, set)):
            return list(value)
        if isinstance(value, Cell):
            return [value.value] if value.initialized else []
        if isinstance(value, Closure):
            return [*value.cells, *value.defaults.values()]
        if self._is_heap_object(value):
            return list(vars(value).values())
        return []

    def _collect_heap(self, roots: list[Any]) -> dict[str, dict[str, Any]]:
        heap: dict[str, dict[str, Any]] = {}
        pending = list(roots)
        while pending:
            value = pending.pop()
            if not self._is_heap_object(value):
                continue
            ref = str(id(value))
            if ref in heap:
                continue
            children = self._children(value)
            refs = sorted(
                {str(id(child)) for child in children if self._is_heap_object(child)}
            )
            heap[ref] = {
                "type": type(value).__name__,
                "repr": self._safe_repr(value),
                "refs": refs,
            }
            pending.extend(children)
        return heap

    def _frame_snapshot(self, frame: Frame) -> dict[str, Any]:
        locals_ = {}
        for index, value in enumerate(frame.locals):
            initialized = index < len(frame.initialized) and frame.initialized[index]
            if not initialized:
                continue
            if isinstance(value, Cell):
                if not value.initialized:
                    continue
                value = value.value
            locals_[f"local_{index}"] = self._snapshot_value(value)
        return {
            "func": f"func_{frame.func_id}",
            "locals": locals_,
        }

    def _after_step(self, instr: Instr, error: Exception | None = None) -> None:
        ip = self._executing_ip
        try:
            op = OP(instr.op)
            opcode = op.name
        except ValueError:
            opcode = str(instr.op)
        arg = instr.args[0] if instr.args else None
        frames = [self._frame_snapshot(frame) for frame in self.call_stack]
        roots = list(self.stack) + list(self.globals_.values())
        for frame in self.call_stack:
            roots.extend(frame.locals)
            roots.extend(frame.closure_cells)
        self.trace.append({
            "step": len(self.trace),
            "ip": ip,
            "opcode": opcode,
            "arg": arg,
            "source_line": instr.line or None,
            "operand_stack": [self._snapshot_value(value) for value in self.stack],
            "call_stack": frames,
            "globals": {
                name: self._snapshot_value(value)
                for name, value in self.globals_.items()
            },
            "heap": self._collect_heap(roots),
            "output": self._output.getvalue(),
            "error": None if error is None else str(error),
        })

    def run(self):
        with redirect_stdout(self._output):
            return super().run()

    def get_trace(self) -> list[dict[str, Any]]:
        return self.trace


__all__ = ["TracedVM"]
