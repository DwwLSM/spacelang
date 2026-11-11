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


class Cell:
    def __init__(self, value: Any = None, initialized: bool = False):
        self.value = value
        self.initialized = initialized


class Closure:
    def __init__(
        self,
        func_id: int,
        cells: list[Cell],
        parameter_names: list[str] | int,
        defaults: dict[str, Any] | None = None,
        positional_count: int | None = None,
        vararg_name: str | None = None,
        kwarg_name: str | None = None,
        positional_only_count: int = 0,
    ):
        self.func_id = func_id
        self.cells = cells
        self.arg_count = parameter_names if isinstance(parameter_names, int) else len(parameter_names)
        self.parameter_names = None if isinstance(parameter_names, int) else parameter_names
        self.defaults = defaults or {}
        self.positional_count = self.arg_count if positional_count is None else positional_count
        self.vararg_name = vararg_name
        self.kwarg_name = kwarg_name
        self.positional_only_count = positional_only_count


@dataclass
class Frame:
    func_id: int
    return_ip: int
    locals: list[Any] = field(default_factory=list)
    initialized: list[bool] = field(default_factory=list)
    closure_cells: list[Cell] = field(default_factory=list)


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

    def _push_frame(
        self,
        func_id: int,
        args: list[Any],
        return_ip: int,
        closure_cells: list[Cell] | None = None,
    ) -> None:
        frame = Frame(
            func_id=func_id,
            return_ip=return_ip,
            locals=list(args),
            initialized=[True] * len(args),
            closure_cells=closure_cells or [],
        )
        self.call_stack.append(frame)

    def _current_frame(self) -> Frame | None:
        return self.call_stack[-1] if self.call_stack else None

    def _emit(self, exc: Exception) -> None:
        raise exc

    @staticmethod
    def _identical(left: Any, right: Any) -> bool:
        if left is right:
            return True
        scalar_types = (bool, int, float, type(None))
        if type(left) in scalar_types and type(right) is type(left):
            return left == right
        return left is right

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

    def _bind_closure_args(
        self,
        closure: Closure,
        positional: list[Any],
        keywords: dict[str, Any],
        line: int,
    ) -> list[Any]:
        parameter_names = closure.parameter_names
        if len(positional) > closure.positional_count and closure.vararg_name is None:
            raise TypeError(
                line=line,
                ip=self.ip,
                msg=f"expected at most {closure.positional_count} positional arguments, got {len(positional)}",
            )
        bound = dict(zip(parameter_names, positional[:closure.positional_count]))
        extra_keywords: dict[str, Any] = {}
        for name, value in keywords.items():
            if name not in parameter_names:
                if closure.kwarg_name is None:
                    raise TypeError(line=line, ip=self.ip, msg=f"unexpected keyword argument {name!r}")
                extra_keywords[name] = value
                continue
            if parameter_names.index(name) < closure.positional_only_count:
                if closure.kwarg_name is None:
                    raise TypeError(
                        line=line,
                        ip=self.ip,
                        msg=f"positional-only argument {name!r} passed as a keyword",
                    )
                extra_keywords[name] = value
                continue
            if name in bound:
                raise TypeError(line=line, ip=self.ip, msg=f"multiple values for argument {name!r}")
            bound[name] = value
        args = []
        for name in parameter_names:
            if name in bound:
                args.append(bound[name])
            elif name in closure.defaults:
                args.append(closure.defaults[name])
            else:
                raise TypeError(line=line, ip=self.ip, msg=f"missing required argument {name!r}")
        if closure.vararg_name is not None:
            args.append(tuple(positional[closure.positional_count:]))
        if closure.kwarg_name is not None:
            args.append(extra_keywords)
        return args

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

            if op == OP.LIST_EXTEND:
                iterable = self._pop("list iterable")
                target = self._pop("list")
                if not isinstance(target, list):
                    raise TypeError(line=instr.line, ip=self.ip, msg="LIST_EXTEND target must be a list")
                target.extend(iterable)
                self._push(target)
                self.ip += 1
                continue

            if op == OP.DICT_MERGE:
                mapping = self._pop("keyword mapping")
                target = self._pop("keyword arguments")
                if not isinstance(target, dict):
                    raise TypeError(line=instr.line, ip=self.ip, msg="DICT_MERGE target must be a dictionary")
                try:
                    keys = mapping.keys()
                except AttributeError as exc:
                    raise TypeError(
                        line=instr.line,
                        ip=self.ip,
                        msg="argument after ** must be a mapping",
                    ) from exc
                for key in keys:
                    if not isinstance(key, str):
                        raise TypeError(
                            line=instr.line,
                            ip=self.ip,
                            msg="keywords must be strings",
                        )
                    if key in target:
                        raise TypeError(
                            line=instr.line,
                            ip=self.ip,
                            msg=f"got multiple values for keyword argument {key!r}",
                        )
                    target[key] = mapping[key]
                self._push(target)
                self.ip += 1
                continue
            if op == OP.DICT_UPDATE:
                mapping = self._pop("dictionary mapping")
                target = self._pop("dictionary")
                if not isinstance(target, dict):
                    raise TypeError(line=instr.line, ip=self.ip, msg="DICT_UPDATE target must be a dictionary")
                try:
                    keys = mapping.keys()
                except AttributeError as exc:
                    raise TypeError(
                        line=instr.line,
                        ip=self.ip,
                        msg="argument after ** must be a mapping",
                    ) from exc
                for key in keys:
                    target[key] = mapping[key]
                self._push(target)
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

            if op == OP.PUSH_NONE:
                self._push(None)
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
                if slot < 0 or slot >= len(frame.locals) or not frame.initialized[slot]:
                    raise UndefinedName(line=instr.line, ip=self.ip, msg=f"undefined local slot {slot}")
                value = frame.locals[slot]
                if isinstance(value, Cell):
                    if not value.initialized:
                        raise UndefinedName(line=instr.line, ip=self.ip, msg=f"undefined local slot {slot}")
                    value = value.value
                self._push(value)
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
                    frame.initialized.append(False)
                if isinstance(frame.locals[slot], Cell):
                    frame.locals[slot].value = value
                    frame.locals[slot].initialized = True
                    frame.initialized[slot] = True
                else:
                    frame.locals[slot] = value
                    frame.initialized[slot] = True
                self.ip += 1
                continue

            if op == OP.CELLIFY:
                frame = self._current_frame()
                if frame is None:
                    raise UndefinedName(line=instr.line, ip=self.ip, msg="CELLIFY outside function")
                slot = int(args[0])
                while len(frame.locals) <= slot:
                    frame.locals.append(None)
                    frame.initialized.append(False)
                if not isinstance(frame.locals[slot], Cell):
                    frame.locals[slot] = Cell(frame.locals[slot], frame.initialized[slot])
                frame.initialized[slot] = True
                self.ip += 1
                continue

            if op == OP.LOAD_CELL_REF:
                frame = self._current_frame()
                if frame is None:
                    raise UndefinedName(line=instr.line, ip=self.ip, msg="LOAD_CELL_REF outside function")
                slot = int(args[0])
                if slot >= len(frame.locals) or not isinstance(frame.locals[slot], Cell):
                    raise UndefinedName(line=instr.line, ip=self.ip, msg=f"local slot {slot} is not a cell")
                self._push(frame.locals[slot])
                self.ip += 1
                continue

            if op == OP.LOAD_DEREF:
                frame = self._current_frame()
                if frame is None:
                    raise UndefinedName(line=instr.line, ip=self.ip, msg="LOAD_DEREF outside function")
                index = int(args[0])
                if index >= len(frame.closure_cells):
                    raise UndefinedName(line=instr.line, ip=self.ip, msg=f"undefined closure cell {index}")
                self._push(frame.closure_cells[index])
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
                elif op_id == 12:
                    result = lhs in rhs
                elif op_id == 13:
                    result = lhs not in rhs
                elif op_id == 14:
                    result = self._identical(lhs, rhs)
                elif op_id == 15:
                    result = not self._identical(lhs, rhs)
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

            if op == OP.BUILD_DICT:
                count = int(args[0])
                items = []
                for _ in range(count):
                    value = self._pop("dict value")
                    key = self._pop("dict key")
                    items.append((key, value))
                items.reverse()
                self._push(dict(items))
                self.ip += 1
                continue

            if op == OP.BUILD_SET:
                count = int(args[0])
                values = []
                for _ in range(count):
                    values.append(self._pop("set element"))
                values.reverse()
                self._push(set(values))
                self.ip += 1
                continue

            if op == OP.BUILD_SLICE:
                step = self._pop("slice step")
                upper = self._pop("slice upper bound")
                lower = self._pop("slice lower bound")
                self._push(slice(lower, upper, step))
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

            if op == OP.STORE_ATTR:
                obj = self._pop("attribute object")
                value = self._pop("attribute value")
                setattr(obj, self._name(int(args[0])), value)
                self.ip += 1
                continue

            if op == OP.STORE_INDEX:
                key = self._pop("index key")
                container = self._pop("index container")
                value = self._pop("index value")
                container[key] = value
                self.ip += 1
                continue

            if op == OP.UNPACK_SEQUENCE:
                count = int(args[0])
                value = self._pop("unpack value")
                iterator = iter(value)
                items = []
                for _ in range(count):
                    try:
                        items.append(next(iterator))
                    except StopIteration as exc:
                        raise ValueError(
                            f"not enough values to unpack (expected {count}, got {len(items)})"
                        ) from exc
                try:
                    next(iterator)
                except StopIteration:
                    self.stack.extend(reversed(items))
                else:
                    raise ValueError(f"too many values to unpack (expected {count})")
                self.ip += 1
                continue

            if op == OP.GET_ITER:
                self._push(iter(self._pop("iterable")))
                self.ip += 1
                continue

            if op == OP.FOR_ITER:
                target = int(args[0])
                if target < 0 or target >= len(self.instrs):
                    raise JumpOutOfRange(line=instr.line, ip=self.ip, msg=f"jump target {target} out of range")
                if not self.stack:
                    raise StackUnderflow(line=0, ip=self.ip, msg="stack underflow while iterating")
                try:
                    self._push(next(self.stack[-1]))
                except StopIteration:
                    self.stack.pop()
                    self.ip = target
                else:
                    self.ip += 1
                continue

            if op == OP.GET_ATTR:
                name_id = int(args[0])
                obj = self._pop("object")
                name = self._name(name_id)
                self._push(getattr(obj, name))
                self.ip += 1
                continue

            if op in {OP.CALL_OBJ, OP.CALL_OBJ_KW, OP.CALL_OBJ_EX}:
                if op == OP.CALL_OBJ_EX:
                    keywords = self._pop("keyword arguments")
                    args_list = self._pop("positional arguments")
                    if not isinstance(keywords, dict) or not isinstance(args_list, list):
                        raise TypeError(line=instr.line, ip=self.ip, msg="invalid expanded call arguments")
                    callable_obj = self._pop("callable")
                else:
                    nargs = int(args[0])
                    nkw = 0 if op == OP.CALL_OBJ else int(args[1])
                    keywords = {}
                    keyword_items = []
                    for _ in range(nkw):
                        value = self._pop("keyword value")
                        name = self._name(int(self._pop("keyword name")))
                        keyword_items.append((name, value))
                    for name, value in reversed(keyword_items):
                        if name in keywords:
                            raise TypeError(line=instr.line, ip=self.ip, msg=f"multiple values for keyword {name!r}")
                        keywords[name] = value
                    args_list = self._collect_args(nargs)
                    callable_obj = self._pop("callable")
                if isinstance(callable_obj, Closure):
                    if callable_obj.func_id not in self.funcs:
                        raise UndefinedFunc(
                            line=instr.line,
                            ip=self.ip,
                            msg=f"undefined user function {callable_obj.func_id}",
                        )
                    if callable_obj.parameter_names is None:
                        if keywords:
                            raise TypeError(
                                line=instr.line,
                                ip=self.ip,
                                msg="keyword arguments are unavailable for this legacy closure",
                            )
                        if len(args_list) != callable_obj.arg_count:
                            raise TypeError(
                                line=instr.line,
                                ip=self.ip,
                                msg=(
                                    f"expected {callable_obj.arg_count} positional arguments, "
                                    f"got {len(args_list)}"
                                ),
                            )
                    else:
                        args_list = self._bind_closure_args(callable_obj, args_list, keywords, instr.line)
                    self._push_frame(
                        callable_obj.func_id,
                        args_list,
                        self.ip + 1,
                        callable_obj.cells,
                    )
                    self.ip = self.funcs[callable_obj.func_id][0]
                    continue
                if op in {OP.CALL_OBJ_KW, OP.CALL_OBJ_EX}:
                    result = callable_obj(*args_list, **keywords)
                else:
                    result = callable_obj(*args_list)
                self._push(result)
                self.ip += 1
                continue

            if op == OP.MAKE_CLOSURE:
                func_id = int(args[0])
                cell_count = int(args[1])
                arg_count = int(args[2])
                cells = [self._pop("closure cell") for _ in range(cell_count)]
                cells.reverse()
                if func_id not in self.funcs:
                    raise UndefinedFunc(line=instr.line, ip=self.ip, msg=f"undefined user function {func_id}")
                self._push(Closure(func_id, cells, arg_count))
                self.ip += 1
                continue

            if op == OP.MAKE_CLOSURE_SIG:
                func_id = int(args[0])
                cell_count = int(args[1])
                parameter_count = int(args[2])
                default_count = int(args[3])
                default_values = [self._pop("default value") for _ in range(default_count)]
                default_values.reverse()
                parameter_names = [
                    self._name(int(self._pop("parameter name")))
                    for _ in range(parameter_count)
                ]
                parameter_names.reverse()
                defaults = dict(zip(parameter_names[-default_count:] if default_count else [], default_values))
                cells = [self._pop("closure cell") for _ in range(cell_count)]
                cells.reverse()
                if func_id not in self.funcs:
                    raise UndefinedFunc(line=instr.line, ip=self.ip, msg=f"undefined user function {func_id}")
                self._push(Closure(func_id, cells, parameter_names, defaults))
                self.ip += 1
                continue

            if op == OP.MAKE_CLOSURE_KWONLY:
                func_id = int(args[0])
                cell_count = int(args[1])
                positional_count = int(args[2])
                keyword_only_count = int(args[3])
                positional_default_count = int(args[4])
                keyword_default_count = int(args[5])
                keyword_defaults = []
                for _ in range(keyword_default_count):
                    value = self._pop("keyword-only default value")
                    name = self._name(int(self._pop("keyword-only default name")))
                    keyword_defaults.append((name, value))
                keyword_defaults.reverse()
                positional_defaults = [
                    self._pop("default value") for _ in range(positional_default_count)
                ]
                positional_defaults.reverse()
                parameter_names = [
                    self._name(int(self._pop("parameter name")))
                    for _ in range(positional_count + keyword_only_count)
                ]
                parameter_names.reverse()
                defaults = dict(
                    zip(
                        parameter_names[positional_count - positional_default_count:positional_count],
                        positional_defaults,
                    )
                )
                defaults.update(keyword_defaults)
                cells = [self._pop("closure cell") for _ in range(cell_count)]
                cells.reverse()
                if func_id not in self.funcs:
                    raise UndefinedFunc(line=instr.line, ip=self.ip, msg=f"undefined user function {func_id}")
                self._push(Closure(func_id, cells, parameter_names, defaults, positional_count))
                self.ip += 1
                continue

            if op == OP.MAKE_CLOSURE_ARGS:
                func_id = int(args[0])
                cell_count = int(args[1])
                positional_count = int(args[2])
                keyword_only_count = int(args[3])
                positional_default_count = int(args[4])
                keyword_default_count = int(args[5])
                has_varargs = int(args[6]) == 1
                has_kwargs = int(args[7]) == 1
                if (
                    int(args[6]) not in {0, 1}
                    or int(args[7]) not in {0, 1}
                    or positional_default_count > positional_count
                    or keyword_default_count > keyword_only_count
                ):
                    raise RuntimeError(
                        line=instr.line,
                        ip=self.ip,
                        msg="invalid variadic closure signature",
                    )
                kwarg_name = self._name(int(self._pop("kwarg name"))) if has_kwargs else None
                vararg_name = self._name(int(self._pop("vararg name"))) if has_varargs else None
                keyword_defaults = []
                for _ in range(keyword_default_count):
                    value = self._pop("keyword-only default value")
                    name = self._name(int(self._pop("keyword-only default name")))
                    keyword_defaults.append((name, value))
                keyword_defaults.reverse()
                positional_defaults = [
                    self._pop("default value") for _ in range(positional_default_count)
                ]
                positional_defaults.reverse()
                parameter_names = [
                    self._name(int(self._pop("parameter name")))
                    for _ in range(positional_count + keyword_only_count)
                ]
                parameter_names.reverse()
                defaults = dict(
                    zip(
                        parameter_names[positional_count - positional_default_count:positional_count],
                        positional_defaults,
                    )
                )
                defaults.update(keyword_defaults)
                cells = [self._pop("closure cell") for _ in range(cell_count)]
                cells.reverse()
                if func_id not in self.funcs:
                    raise UndefinedFunc(line=instr.line, ip=self.ip, msg=f"undefined user function {func_id}")
                self._push(
                    Closure(
                        func_id,
                        cells,
                        parameter_names,
                        defaults,
                        positional_count,
                        vararg_name,
                        kwarg_name,
                    )
                )
                self.ip += 1
                continue

            if op == OP.MAKE_CLOSURE_POSONLY:
                func_id = int(args[0])
                cell_count = int(args[1])
                positional_only_count = int(args[2])
                positional_count = int(args[3])
                keyword_only_count = int(args[4])
                positional_default_count = int(args[5])
                keyword_default_count = int(args[6])
                has_varargs = int(args[7]) == 1
                has_kwargs = int(args[8]) == 1
                if (
                    positional_only_count > positional_count
                    or positional_default_count > positional_count
                    or keyword_default_count > keyword_only_count
                    or int(args[7]) not in {0, 1}
                    or int(args[8]) not in {0, 1}
                ):
                    raise RuntimeError(line=instr.line, ip=self.ip, msg="invalid positional-only closure signature")
                kwarg_name = self._name(int(self._pop("kwarg name"))) if has_kwargs else None
                vararg_name = self._name(int(self._pop("vararg name"))) if has_varargs else None
                keyword_defaults = []
                for _ in range(keyword_default_count):
                    value = self._pop("keyword-only default value")
                    name = self._name(int(self._pop("keyword-only default name")))
                    keyword_defaults.append((name, value))
                keyword_defaults.reverse()
                positional_defaults = [
                    self._pop("default value") for _ in range(positional_default_count)
                ]
                positional_defaults.reverse()
                parameter_names = [
                    self._name(int(self._pop("parameter name")))
                    for _ in range(positional_count + keyword_only_count)
                ]
                parameter_names.reverse()
                defaults = dict(
                    zip(
                        parameter_names[positional_count - positional_default_count:positional_count],
                        positional_defaults,
                    )
                )
                defaults.update(keyword_defaults)
                cells = [self._pop("closure cell") for _ in range(cell_count)]
                cells.reverse()
                if func_id not in self.funcs:
                    raise UndefinedFunc(line=instr.line, ip=self.ip, msg=f"undefined user function {func_id}")
                self._push(
                    Closure(
                        func_id,
                        cells,
                        parameter_names,
                        defaults,
                        positional_count,
                        vararg_name,
                        kwarg_name,
                        positional_only_count,
                    )
                )
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

            if op == OP.CALL_BUILTIN_EX:
                keywords = self._pop("keyword arguments")
                positional = self._pop("positional arguments")
                if not isinstance(keywords, dict) or not isinstance(positional, list):
                    raise TypeError(line=instr.line, ip=self.ip, msg="invalid expanded call arguments")
                func_id = int(args[0])
                func = ALL_BUILTINS.get(func_id)
                if func is None:
                    raise UndefinedFunc(line=instr.line, ip=self.ip, msg=f"undefined callable {func_id}")
                self._push(func(*positional, **keywords))
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
                if target < 0 or target >= len(self.instrs):
                    raise JumpOutOfRange(line=0, ip=self.ip, msg=f"jump target {target} out of range")
                value = self._pop("condition")
                if not value:
                    self.ip = target
                else:
                    self.ip += 1
                continue

            if op == OP.JNZ:
                target = int(args[0])
                if target < 0 or target >= len(self.instrs):
                    raise JumpOutOfRange(line=0, ip=self.ip, msg=f"jump target {target} out of range")
                value = self._pop("condition")
                if bool(value):
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
