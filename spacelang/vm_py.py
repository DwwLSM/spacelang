from __future__ import annotations

import builtins as pybuiltins
from dataclasses import dataclass, field
from typing import Any

from .builtins_py import ALL_BUILTINS
from .errors import (
    JumpOutOfRange,
    ParseError,
    RuntimeError,
    SpaceError,
    StackUnderflow,
    TypeError,
    UndefinedFunc,
    UndefinedModule,
    UndefinedName,
)
from .ir import Instr, OP, Program
from .modules import do_import


@dataclass
class Frame:
    func_id: int
    return_ip: int
    locals: list[Any] = field(default_factory=list)


class VM:
    def __init__(self, program: Program):
        self.program = program
        self.instrs = program.instrs
        self.stack: list[Any] = []
        self.globals_: dict[str, Any] = {}
        self.call_stack: list[Frame] = []
        self.try_stack: list[dict[str, Any]] = []
        self.with_stack: list[Any] = []
        self.ip = 0
        self.funcs = program.funcs
        self.names = {value: key for key, value in program.names.items()}
        self._return_value: Any = None

    def _name(self, name_id: int) -> str:
        name = self.names.get(name_id)
        if name is None:
            raise UndefinedName(line=0, ip=self.ip, msg=f"unknown name id {name_id}")
        return name

    def _pop(self, expected: str = "value") -> Any:
        if not self.stack:
            raise StackUnderflow(line=0, ip=self.ip, msg=f"stack underflow while popping {expected}")
        return self.stack.pop()

    def _push(self, value: Any) -> None:
        self.stack.append(value)

    def _push_frame(self, func_id: int, args: list[Any], return_ip: int) -> None:
        frame = Frame(func_id=func_id, return_ip=return_ip, locals=list(args))
        self.call_stack.append(frame)

    def _current_frame(self) -> Frame | None:
        return self.call_stack[-1] if self.call_stack else None

    def _emit(self, exc: Exception) -> None:
        raise exc

    def _call_builtin(self, func_id: int, args: list[Any], kwargs: dict[str, Any] | None = None) -> Any:
        func = ALL_BUILTINS.get(func_id)
        if func is None:
            raise UndefinedFunc(line=0, ip=self.ip, msg=f"undefined builtin func_id {func_id}")
        if kwargs:
            return func(*args, **kwargs)
        return func(*args)

    def _collect_args(self, nargs: int) -> list[Any]:
        args = []
        for _ in range(nargs):
            if not self.stack:
                raise StackUnderflow(line=0, ip=self.ip, msg="missing args for call")
            args.append(self._pop("arg"))
        args.reverse()
        return args

    def _call_user_function(self, func_id: int, args: list[Any]) -> Any:
        if func_id not in self.funcs:
            raise UndefinedFunc(line=0, ip=self.ip, msg=f"undefined user function {func_id}")
        entry_ip, _ = self.funcs[func_id]
        self._push_frame(func_id, args, self.ip + 1)
        self.ip = entry_ip
        return None

    def _raise(self, exc: BaseException) -> None:
        while self.try_stack:
            active = self.try_stack[-1]
            stage = active.get("stage")
            del self.stack[int(active["stack_depth"]):]
            while len(self.call_stack) > int(active["call_depth"]):
                self.call_stack.pop()
            if stage == "body" and active.get("catch_ip"):
                active["exc"] = exc
                active["stage"] = "catch"
                self.ip = active["catch_ip"]
                return
            if stage in {"body", "catch"} and active.get("finally_ip"):
                active["exc"] = exc
                active["stage"] = "finally"
                self.ip = active["finally_ip"]
                return
            self.try_stack.pop()
        raise exc

    def _sequential_call(self, func_id: int, nargs: int, kwargs: dict[str, Any] | None = None) -> Any:
        args = []
        for _ in range(nargs):
            if not self.stack:
                raise StackUnderflow(line=0, ip=self.ip, msg="missing args for call")
            args.append(self._pop("arg"))
        args.reverse()
        if func_id >= 10000:
            self._call_user_function(func_id, args)
            return None
        if func_id in ALL_BUILTINS:
            return self._call_builtin(func_id, args, kwargs)
        raise UndefinedFunc(line=0, ip=self.ip, msg=f"undefined function {func_id}")

    def _try_end_handler(self, frame: dict[str, Any]) -> None:
        stage = frame.get("stage")
        if stage in {"body", "catch"}:
            if stage == "catch":
                frame["exc"] = None
            if frame.get("finally_ip"):
                frame["stage"] = "finally"
                frame["saved_ip"] = frame["end_ip"]
                self.ip = frame["finally_ip"]
                return
            self.try_stack.pop()
            self.ip = frame["end_ip"]
            return
        if stage == "finally":
            self.try_stack.pop()
            exc = frame.get("exc")
            if exc is not None:
                self._raise(exc)
                return
            self.ip = frame["saved_ip"]
            return

    def run(self) -> Any:
        while True:
            try:
                return self._run()
            except Exception as exc:
                runtime_exc = (
                    exc
                    if isinstance(exc, SpaceError)
                    else RuntimeError(
                        line=self.instrs[self.ip].line if 0 <= self.ip < len(self.instrs) else 0,
                        ip=self.ip,
                        msg=str(exc),
                    )
                )
                if not self.try_stack:
                    if runtime_exc is exc:
                        raise
                    raise runtime_exc from exc
                self._raise(runtime_exc)

    def _run(self) -> Any:
        while self.ip < len(self.instrs):
            instr = self.instrs[self.ip]
            op = OP(instr.op)
            args = list(instr.args)

            if op == OP.NOP:
                self.ip += 1
                continue
            if op == OP.DEF:
                func_id = int(args[0])
                if func_id in self.funcs:
                    _, end_ip = self.funcs[func_id]
                    self.ip = end_ip
                else:
                    self.ip += 1
                continue
            if op == OP.HALT:
                if self.stack:
                    self._return_value = self._pop("halt result")
                break

            if op == OP.PUSH_INT:
                value = args[0]
                self._push(value)
                self.ip += 1
                continue

            if op == OP.PUSH_STR:
                payload = list(args[1:])
                self._push("".join(chr(v) for v in payload))
                self.ip += 1
                continue

            if op == OP.LOAD_GLOBAL:
                name = self._name(int(args[0]))
                if name not in self.globals_:
                    raise UndefinedName(line=instr.line, ip=self.ip, msg=f"undefined global {name}")
                self._push(self.globals_[name])
                self.ip += 1
                continue

            if op == OP.STORE_GLOBAL:
                name = self._name(int(args[0]))
                value = self._pop("global value")
                self.globals_[name] = value
                self.ip += 1
                continue

            if op == OP.LOAD_ARG:
                frame = self._current_frame()
                if frame is None:
                    raise UndefinedName(line=0, ip=self.ip, msg="LOAD_ARG outside function")
                idx = int(args[0])
                if idx >= len(frame.locals):
                    raise UndefinedName(line=0, ip=self.ip, msg=f"undefined arg slot {idx}")
                self._push(frame.locals[idx])
                self.ip += 1
                continue

            if op == OP.LOAD_LOCAL:
                frame = self._current_frame()
                if frame is None:
                    raise UndefinedName(line=0, ip=self.ip, msg="LOAD_LOCAL outside function")
                slot = int(args[0])
                if slot >= len(frame.locals) or frame.locals[slot] is None:
                    raise UndefinedName(line=0, ip=self.ip, msg=f"undefined local slot {slot}")
                self._push(frame.locals[slot])
                self.ip += 1
                continue

            if op == OP.STORE_LOCAL:
                frame = self._current_frame()
                if frame is None:
                    raise UndefinedName(line=0, ip=self.ip, msg="STORE_LOCAL outside function")
                slot = int(args[0])
                value = self._pop("local value")
                while len(frame.locals) <= slot:
                    frame.locals.append(None)
                frame.locals[slot] = value
                self.ip += 1
                continue

            if op == OP.OP:
                op_id = int(args[0])
                rhs = self._pop("rhs")
                lhs = self._pop("lhs")
                if op_id == 1:
                    result = lhs + rhs
                elif op_id == 2:
                    result = lhs - rhs
                elif op_id == 3:
                    result = lhs * rhs
                elif op_id == 4:
                    result = lhs / rhs
                elif op_id == 5:
                    result = lhs % rhs
                elif op_id == 6:
                    result = lhs == rhs
                elif op_id == 7:
                    result = lhs < rhs
                elif op_id == 8:
                    result = lhs > rhs
                elif op_id == 9:
                    result = lhs != rhs
                elif op_id == 10:
                    result = lhs <= rhs
                elif op_id == 11:
                    result = lhs >= rhs
                else:
                    raise ParseError(line=0, ip=self.ip, msg=f"unsupported op_id {op_id}")
                self._push(result)
                self.ip += 1
                continue

            if op == OP.STACK:
                op_id = int(args[0])
                if op_id == 1:
                    if not self.stack:
                        raise StackUnderflow(line=0, ip=self.ip, msg="dup requires 1 value")
                    self.stack.append(self.stack[-1])
                elif op_id == 2:
                    if len(self.stack) < 2:
                        raise StackUnderflow(line=0, ip=self.ip, msg="swap requires 2 values")
                    a = self.stack.pop()
                    b = self.stack.pop()
                    self.stack.extend([a, b])
                elif op_id == 3:
                    if not self.stack:
                        raise StackUnderflow(line=0, ip=self.ip, msg="drop requires 1 value")
                    self.stack.pop()
                elif op_id == 4:
                    if len(self.stack) < 2:
                        raise StackUnderflow(line=0, ip=self.ip, msg="over requires 2 values")
                    self.stack.append(self.stack[-2])
                elif op_id == 5:
                    if len(self.stack) < 3:
                        raise StackUnderflow(line=0, ip=self.ip, msg="rot requires 3 values")
                    c = self.stack.pop()
                    b = self.stack.pop()
                    a = self.stack.pop()
                    self.stack.extend([b, c, a])
                else:
                    raise ParseError(line=0, ip=self.ip, msg=f"unsupported stack op {op_id}")
                self.ip += 1
                continue

            if op == OP.BUILD_LIST:
                count = int(args[0])
                values = []
                for _ in range(count):
                    values.append(self._pop("list element"))
                values.reverse()
                self._push(values)
                self.ip += 1
                continue

            if op == OP.BUILD_TUPLE:
                count = int(args[0])
                values = []
                for _ in range(count):
                    values.append(self._pop("tuple element"))
                values.reverse()
                self._push(tuple(values))
                self.ip += 1
                continue

            if op == OP.CONCAT:
                count = int(args[0])
                values = []
                for _ in range(count):
                    values.append(self._pop("concat operand"))
                values.reverse()
                if not values:
                    self._push("")
                elif all(isinstance(v, str) for v in values):
                    self._push("".join(values))
                elif all(isinstance(v, (bytes, bytearray)) for v in values):
                    result = b"".join(bytes(v) for v in values)
                    self._push(result)
                elif all(isinstance(v, list) for v in values):
                    merged = []
                    for item in values:
                        merged.extend(item)
                    self._push(merged)
                elif all(isinstance(v, tuple) for v in values):
                    merged = []
                    for item in values:
                        merged.extend(item)
                    self._push(tuple(merged))
                else:
                    raise TypeError(line=0, ip=self.ip, msg="Concat requires homogeneous types")
                self.ip += 1
                continue

            if op == OP.INDEX:
                key = self._pop("key")
                container = self._pop("container")
                self._push(container[key])
                self.ip += 1
                continue

            if op == OP.GET_ATTR:
                name_id = int(args[0])
                obj = self._pop("object")
                name = self._name(name_id)
                self._push(getattr(obj, name))
                self.ip += 1
                continue

            if op == OP.CALL_OBJ:
                nargs = int(args[0])
                args_list = []
                for _ in range(nargs):
                    args_list.append(self._pop("call arg"))
                args_list.reverse()
                callable_obj = self._pop("callable")
                result = callable_obj(*args_list)
                self._push(result)
                self.ip += 1
                continue

            if op == OP.CALL:
                func_id = int(args[0])
                nargs = int(args[1])
                if func_id >= 10000:
                    self._call_user_function(func_id, self._collect_args(nargs))
                    continue
                result = self._sequential_call(func_id, nargs)
                self._push(result)
                self.ip += 1
                continue

            if op == OP.CALL_KW:
                func_id = int(args[0])
                npos = int(args[1])
                nkw = int(args[2])
                positional = []
                for _ in range(npos):
                    positional.append(self._pop("positional arg"))
                positional.reverse()
                kwargs = {}
                for _ in range(nkw):
                    value = self._pop("keyword value")
                    name = self._pop("keyword name")
                    kwargs[self._name(int(name))] = value
                if func_id >= 10000:
                    raise TypeError(line=0, ip=self.ip, msg="CALL_KW is not supported for user functions")
                func = ALL_BUILTINS.get(func_id)
                if func is None:
                    raise UndefinedFunc(line=0, ip=self.ip, msg=f"undefined callable {func_id}")
                self._push(func(*positional, **kwargs))
                self.ip += 1
                continue

            if op == OP.CALL_METHOD:
                method_name_id = int(args[0])
                nargs = int(args[1])
                method_args = []
                for _ in range(nargs):
                    method_args.append(self._pop("method arg"))
                method_args.reverse()
                obj = self._pop("method object")
                method = getattr(obj, self._name(method_name_id))
                self._push(method(*method_args))
                self.ip += 1
                continue

            if op == OP.IMPORT:
                module_id = int(args[0])
                self._push(do_import(module_id, self.globals_))
                self.ip += 1
                continue

            if op == OP.JMP:
                target = int(args[0])
                if target < 0 or target >= len(self.instrs):
                    raise JumpOutOfRange(line=0, ip=self.ip, msg=f"jump target {target} out of range")
                self.ip = target
                continue

            if op == OP.JZ:
                target = int(args[0])
                value = self._pop("condition")
                if not value:
                    if target < 0 or target >= len(self.instrs):
                        raise JumpOutOfRange(line=0, ip=self.ip, msg=f"jump target {target} out of range")
                    self.ip = target
                else:
                    self.ip += 1
                continue

            if op == OP.JNZ:
                target = int(args[0])
                value = self._pop("condition")
                if bool(value):
                    if target < 0 or target >= len(self.instrs):
                        raise JumpOutOfRange(line=0, ip=self.ip, msg=f"jump target {target} out of range")
                    self.ip = target
                else:
                    self.ip += 1
                continue

            if op == OP.RAISE:
                exc_obj = self._pop("exception")
                if isinstance(exc_obj, BaseException):
                    self._raise(exc_obj)
                else:
                    self._raise(RuntimeError(line=0, ip=self.ip, msg=str(exc_obj)))
                continue

            if op == OP.TRY:
                catch_ip = int(args[0])
                finally_ip = int(args[1])
                for target in (catch_ip, finally_ip):
                    if target != 0 and (target < 0 or target >= len(self.instrs)):
                        raise JumpOutOfRange(line=instr.line, ip=self.ip, msg=f"try target {target} out of range")
                end_ip = self.ip + 1
                if self.program.try_table:
                    for try_ip, end, catch, finally_target in self.program.try_table:
                        if try_ip == self.ip:
                            end_ip = end
                            break
                self.try_stack.append({
                    "catch_ip": catch_ip,
                    "finally_ip": finally_ip,
                    "end_ip": end_ip,
                    "saved_ip": end_ip,
                    "stage": "body",
                    "exc": None,
                    "call_depth": len(self.call_stack),
                    "stack_depth": len(self.stack),
                })
                self.ip += 1
                continue

            if op == OP.END_TRY:
                if not self.try_stack:
                    raise ParseError(line=0, ip=self.ip, msg="END_TRY without TRY")
                self._try_end_handler(self.try_stack[-1])
                continue

            if op == OP.SETUP_WITH:
                obj = self._pop("context manager")
                self.with_stack.append(obj)
                self.ip += 1
                continue

            if op == OP.RET:
                value = self._pop("return value")
                if not self.call_stack:
                    self._return_value = value
                    break
                frame = self.call_stack.pop()
                self.ip = frame.return_ip
                self._push(value)
                continue

            raise ParseError(line=0, ip=self.ip, msg=f"unsupported opcode {op}")

        return self._return_value


__all__ = ["Frame", "VM"]
