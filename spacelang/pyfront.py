from __future__ import annotations

import ast
import textwrap

from .errors import ParseError
from .ir import Instr, OP, Program

BUILTIN_IDS = {
    "print": 0,
    "input": 1,
    "len": 2,
    "int": 3,
    "float": 4,
    "str": 5,
    "bool": 6,
    "abs": 7,
    "range": 8,
    "type": 9,
    "open": 10,
    "getattr": 11,
    "setattr": 12,
    "callable": 13,
    "repr": 14,
    "isinstance": 15,
}


def _emit(instrs: list[Instr], op: OP, *args: int | str, line: int = 0) -> None:
    instrs.append(Instr(op, list(args), line=line))


class _LocalNameCollector(ast.NodeVisitor):
    def __init__(self) -> None:
        self.names: list[str] = []

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, ast.Store) and node.id not in self.names:
            self.names.append(node.id)

class PyFront(ast.NodeVisitor):
    def __init__(self, filename: str = "<stdin>"):
        self.filename = filename
        self.instrs: list[Instr] = []
        self.names: dict[str, int] = {}
        self.labels: dict[str, int] = {}
        self.locals_stack: list[dict[str, int]] = [dict()]
        self.field_slots: dict[str, int] = {}
        self.funcs: dict[int, tuple[int, int]] = {}
        self.function_ids: dict[str, int] = {}
        self.function_id_by_node: dict[int, int] = {}
        self.next_func_id = 10000
        self.pending_labels: list[tuple[str, int]] = []
        self.next_temp_id = 0
        self.source_names: set[str] = set()
        self.name_overrides: list[dict[str, str]] = []

    def _next_func_id(self) -> int:
        func_id = self.next_func_id
        self.next_func_id += 1
        return func_id

    def _name_id(self, name: str) -> int:
        key = self.names.get(name)
        if key is None:
            key = len(self.names)
            self.names[name] = key
        return key

    def _symbol(self, name: str) -> str:
        return name

    def _emit_label(self, name: str) -> None:
        self.labels[name] = len(self.instrs)

    def _emit_jump(self, op: OP, label: str) -> None:
        _emit(self.instrs, op, label)

    def _resolve_labels(self) -> None:
        for instr in self.instrs:
            for idx, arg in enumerate(instr.args):
                if isinstance(arg, str):
                    if arg not in self.labels:
                        raise ParseError(line=instr.line, ip=0, msg=f"undefined label: {arg}")
                    instr.args[idx] = self.labels[arg]

    def _new_temp_name(self) -> str:
        while True:
            name = f"__spacelang_temp_{self.next_temp_id}"
            self.next_temp_id += 1
            if (
                name not in self.source_names
                and name not in self.names
                and all(name not in scope for scope in self.locals_stack)
            ):
                if len(self.locals_stack) > 1:
                    self.locals_stack[-1][name] = len(self.locals_stack[-1])
                else:
                    self._name_id(name)
                return name

    def _load_name(self, name: str, line: int) -> None:
        for overrides in reversed(self.name_overrides):
            if name in overrides:
                name = overrides[name]
                break
        if len(self.locals_stack) > 1 and name in self.locals_stack[-1]:
            _emit(self.instrs, OP.LOAD_LOCAL, self.locals_stack[-1][name], line=line)
        else:
            _emit(self.instrs, OP.LOAD_GLOBAL, self._name_id(name), line=line)

    def _store_name(self, name: str, line: int) -> None:
        if len(self.locals_stack) > 1 and name in self.locals_stack[-1]:
            _emit(self.instrs, OP.STORE_LOCAL, self.locals_stack[-1][name], line=line)
        else:
            _emit(self.instrs, OP.STORE_GLOBAL, self._name_id(name), line=line)

    def _compile_expr(self, node: ast.AST) -> None:
        if isinstance(node, ast.Constant):
            value = node.value
            if isinstance(value, bool):
                _emit(self.instrs, OP.PUSH_INT, int(value), line=getattr(node, "lineno", 0))
                _emit(self.instrs, OP.CALL, BUILTIN_IDS["bool"], 1, line=getattr(node, "lineno", 0))
            elif isinstance(value, int):
                _emit(self.instrs, OP.PUSH_INT, value, line=getattr(node, "lineno", 0))
            elif isinstance(value, str):
                chars = [ord(ch) for ch in value]
                chunks = [chars[index:index + 1000] for index in range(0, len(chars), 1000)]
                if not chunks:
                    chunks = [[]]
                for chunk in chunks:
                    _emit(self.instrs, OP.PUSH_STR, len(chunk), *chunk, line=getattr(node, "lineno", 0))
                if len(chunks) > 1:
                    _emit(self.instrs, OP.CONCAT, len(chunks), line=getattr(node, "lineno", 0))
            elif value is None:
                _emit(self.instrs, OP.PUSH_INT, 0, line=getattr(node, "lineno", 0))
            else:
                raise ParseError(line=getattr(node, "lineno", 0), ip=0, msg=f"unsupported constant: {type(value).__name__}")
            return

        if isinstance(node, ast.JoinedStr):
            line = getattr(node, "lineno", 0)
            part_count = 0
            for value in node.values:
                if isinstance(value, ast.Constant) and isinstance(value.value, str):
                    chars = [ord(ch) for ch in value.value]
                    chunks = [chars[index:index + 1000] for index in range(0, len(chars), 1000)] or [[]]
                    for chunk in chunks:
                        _emit(self.instrs, OP.PUSH_STR, len(chunk), *chunk, line=line)
                    if len(chunks) > 1:
                        _emit(self.instrs, OP.CONCAT, len(chunks), line=line)
                elif isinstance(value, ast.FormattedValue) and value.format_spec is None:
                    if value.conversion not in (-1, ord("s"), ord("r")):
                        raise ParseError(line=line, ip=0, msg="f-string conversion is unsupported")
                    self._compile_expr(value.value)
                    formatter = "repr" if value.conversion == ord("r") else "str"
                    _emit(self.instrs, OP.CALL, BUILTIN_IDS[formatter], 1, line=line)
                else:
                    raise ParseError(line=line, ip=0, msg="unsupported f-string format specifier")
                part_count += 1
            if part_count == 0:
                _emit(self.instrs, OP.PUSH_STR, 0, line=line)
            elif part_count > 1:
                _emit(self.instrs, OP.CONCAT, part_count, line=line)
            return

        if isinstance(node, ast.Name):
            self._load_name(node.id, getattr(node, "lineno", 0))
            return

        if isinstance(node, ast.Assign):
            self._compile_expr(node.value)
            if len(node.targets) != 1:
                raise ParseError(line=getattr(node, "lineno", 0), ip=0, msg="multi-target assignment is unsupported")
            target = node.targets[0]
            if isinstance(target, ast.Name):
                self._store_name(target.id, getattr(node, "lineno", 0))
            else:
                raise ParseError(line=getattr(node, "lineno", 0), ip=0, msg="unsupported assignment target")
            return

        if isinstance(node, ast.Expr):
            self._compile_expr(node.value)
            _emit(self.instrs, OP.STACK, 3, line=getattr(node, "lineno", 0))
            return

        if isinstance(node, ast.BinOp):
            self._compile_expr(node.left)
            self._compile_expr(node.right)
            op_map = {
                ast.Add: 1,
                ast.Sub: 2,
                ast.Mult: 3,
                ast.Div: 4,
                ast.Mod: 5,
            }
            op = op_map.get(type(node.op))
            if op is None:
                raise ParseError(line=getattr(node, "lineno", 0), ip=0, msg=f"unsupported binary op: {type(node.op).__name__}")
            _emit(self.instrs, OP.OP, op, line=getattr(node, "lineno", 0))
            return

        if isinstance(node, ast.UnaryOp):
            line = getattr(node, "lineno", 0)
            if isinstance(node.op, ast.UAdd):
                self._compile_expr(node.operand)
            elif isinstance(node.op, ast.USub):
                self._compile_expr(node.operand)
                _emit(self.instrs, OP.PUSH_INT, -1, line=line)
                _emit(self.instrs, OP.OP, 3, line=line)
            elif isinstance(node.op, ast.Not):
                true_label = f"not_true_{len(self.instrs)}"
                end_label = f"not_end_{len(self.instrs)}"
                self._compile_expr(node.operand)
                _emit(self.instrs, OP.JZ, true_label, line=line)
                _emit(self.instrs, OP.PUSH_INT, 0, line=line)
                _emit(self.instrs, OP.JMP, end_label, line=line)
                self._emit_label(true_label)
                _emit(self.instrs, OP.PUSH_INT, 1, line=line)
                self._emit_label(end_label)
                _emit(self.instrs, OP.CALL, BUILTIN_IDS["bool"], 1, line=line)
            else:
                raise ParseError(line=line, ip=0, msg=f"unsupported unary op: {type(node.op).__name__}")
            return

        if isinstance(node, ast.BoolOp):
            line = getattr(node, "lineno", 0)
            if not isinstance(node.op, (ast.And, ast.Or)):
                raise ParseError(line=line, ip=0, msg=f"unsupported boolean op: {type(node.op).__name__}")
            end_label = f"bool_end_{len(self.instrs)}"
            jump_op = OP.JZ if isinstance(node.op, ast.And) else OP.JNZ
            for value in node.values[:-1]:
                self._compile_expr(value)
                _emit(self.instrs, OP.STACK, 1, line=line)
                _emit(self.instrs, jump_op, end_label, line=line)
                _emit(self.instrs, OP.STACK, 3, line=line)
            self._compile_expr(node.values[-1])
            self._emit_label(end_label)
            return

        if isinstance(node, ast.Compare):
            op_map = {
                ast.Eq: 6,
                ast.NotEq: 9,
                ast.Lt: 7,
                ast.Gt: 8,
                ast.LtE: 10,
                ast.GtE: 11,
            }
            line = getattr(node, "lineno", 0)
            false_label = f"compare_false_{len(self.instrs)}"
            end_label = f"compare_end_{len(self.instrs)}"
            left_name = self._new_temp_name() if len(node.ops) > 1 else None
            right_name = self._new_temp_name() if len(node.ops) > 1 else None
            self._compile_expr(node.left)
            if left_name is not None:
                self._store_name(left_name, line)
            for idx, op in enumerate(node.ops):
                mapped = op_map.get(type(op))
                if mapped is None:
                    raise ParseError(line=line, ip=0, msg=f"unsupported compare op: {type(op).__name__}")
                if left_name is not None:
                    self._load_name(left_name, line)
                self._compile_expr(node.comparators[idx])
                if right_name is not None and idx < len(node.ops) - 1:
                    _emit(self.instrs, OP.STACK, 1, line=line)
                    self._store_name(right_name, line)
                _emit(self.instrs, OP.OP, mapped, line=line)
                if idx < len(node.ops) - 1:
                    _emit(self.instrs, OP.JZ, false_label, line=line)
                    if left_name is not None and right_name is not None:
                        self._load_name(right_name, line)
                        self._store_name(left_name, line)
            if len(node.ops) > 1:
                _emit(self.instrs, OP.JMP, end_label, line=line)
                self._emit_label(false_label)
                _emit(self.instrs, OP.PUSH_INT, 0, line=line)
                _emit(self.instrs, OP.CALL, BUILTIN_IDS["bool"], 1, line=line)
                self._emit_label(end_label)
            return

        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                name = node.func.id
                if name in BUILTIN_IDS:
                    line = getattr(node, "lineno", 0)
                    if node.keywords:
                        for keyword in node.keywords:
                            if keyword.arg is None:
                                raise ParseError(line=line, ip=0, msg="expanded keyword arguments are unsupported")
                            _emit(self.instrs, OP.PUSH_INT, self._name_id(keyword.arg), line=line)
                            self._compile_expr(keyword.value)
                        for arg in node.args:
                            self._compile_expr(arg)
                        _emit(
                            self.instrs,
                            OP.CALL_KW,
                            BUILTIN_IDS[name],
                            len(node.args),
                            len(node.keywords),
                            line=line,
                        )
                    else:
                        for arg in node.args:
                            self._compile_expr(arg)
                        _emit(self.instrs, OP.CALL, BUILTIN_IDS[name], len(node.args), line=line)
                    return
                if name in self.function_ids:
                    if node.keywords:
                        raise ParseError(
                            line=getattr(node, "lineno", 0),
                            ip=0,
                            msg="keyword arguments to user functions are unsupported",
                        )
                    for arg in node.args:
                        self._compile_expr(arg)
                    _emit(self.instrs, OP.CALL, self.function_ids[name], len(node.args), line=getattr(node, "lineno", 0))
                    return
                self._compile_expr(node.func)
                for arg in node.args:
                    self._compile_expr(arg)
                if node.keywords:
                    raise ParseError(
                        line=getattr(node, "lineno", 0),
                        ip=0,
                        msg="keyword arguments to callable objects are unsupported",
                    )
                _emit(self.instrs, OP.CALL_OBJ, len(node.args), line=getattr(node, "lineno", 0))
                return
            if isinstance(node.func, ast.Attribute):
                if node.keywords:
                    raise ParseError(
                        line=getattr(node, "lineno", 0),
                        ip=0,
                        msg="keyword arguments to methods are unsupported",
                    )
                self._compile_expr(node.func.value)
                for arg in node.args:
                    self._compile_expr(arg)
                _emit(self.instrs, OP.CALL_METHOD, self._name_id(node.func.attr), len(node.args), line=getattr(node, "lineno", 0))
                return
            raise ParseError(line=getattr(node, "lineno", 0), ip=0, msg=f"unsupported call target: {ast.dump(node.func)}")

        if isinstance(node, ast.Attribute):
            self._compile_expr(node.value)
            _emit(self.instrs, OP.GET_ATTR, self._name_id(node.attr), line=getattr(node, "lineno", 0))
            return

        if isinstance(node, ast.Subscript):
            self._compile_expr(node.value)
            self._compile_expr(node.slice)
            _emit(self.instrs, OP.INDEX, 0, line=getattr(node, "lineno", 0))
            return

        if isinstance(node, ast.List):
            for item in reversed(node.elts):
                self._compile_expr(item)
            _emit(self.instrs, OP.BUILD_LIST, len(node.elts), line=getattr(node, "lineno", 0))
            return

        if isinstance(node, ast.Tuple):
            for item in reversed(node.elts):
                self._compile_expr(item)
            _emit(self.instrs, OP.BUILD_TUPLE, len(node.elts), line=getattr(node, "lineno", 0))
            return

        if isinstance(node, ast.ListComp):
            self._compile_listcomp(node)
            return

        if isinstance(node, ast.If):
            self._compile_expr(node.test)
            false_label = f"if_false_{len(self.instrs)}"
            end_label = f"if_end_{len(self.instrs)}"
            _emit(self.instrs, OP.JZ, false_label, line=getattr(node, "lineno", 0))
            for stmt in node.body:
                self._compile_stmt(stmt)
            if node.orelse:
                _emit(self.instrs, OP.JMP, end_label, line=getattr(node, "lineno", 0))
                self._emit_label(false_label)
                for stmt in node.orelse:
                    self._compile_stmt(stmt)
                self._emit_label(end_label)
            else:
                self._emit_label(false_label)
            return

        if isinstance(node, ast.While):
            loop_label = f"while_loop_{len(self.instrs)}"
            exit_label = f"while_exit_{len(self.instrs)}"
            self._emit_label(loop_label)
            self._compile_expr(node.test)
            _emit(self.instrs, OP.JZ, exit_label, line=getattr(node, "lineno", 0))
            for stmt in node.body:
                self._compile_stmt(stmt)
            _emit(self.instrs, OP.JMP, loop_label, line=getattr(node, "lineno", 0))
            self._emit_label(exit_label)
            for stmt in node.orelse:
                self._compile_stmt(stmt)
            return

        if isinstance(node, ast.For):
            self._compile_for(node)
            return

        if isinstance(node, ast.Import):
            for alias in node.names:
                module_name = alias.name.split(".", 1)[0]
                module_ids = {"math": 0, "random": 1, "os": 2, "re": 3, "sys": 4}
                mid = module_ids.get(module_name)
                if mid is None:
                    raise ParseError(line=getattr(node, "lineno", 0), ip=0, msg=f"unsupported module: {module_name}")
                _emit(self.instrs, OP.IMPORT, mid, line=getattr(node, "lineno", 0))
                bound_name = alias.asname or module_name
                self._store_name(bound_name, getattr(node, "lineno", 0))
            return

        if isinstance(node, ast.ImportFrom):
            module_ids = {"math": 0, "random": 1, "os": 2, "re": 3, "sys": 4}
            mid = module_ids.get(node.module or "") if node.level == 0 else None
            if mid is None:
                raise ParseError(line=getattr(node, "lineno", 0), ip=0, msg="unsupported import module")
            for alias in node.names:
                if alias.name == "*":
                    raise ParseError(line=getattr(node, "lineno", 0), ip=0, msg="star imports are unsupported")
                _emit(self.instrs, OP.IMPORT, mid, line=getattr(node, "lineno", 0))
                _emit(self.instrs, OP.GET_ATTR, self._name_id(alias.name), line=getattr(node, "lineno", 0))
                self._store_name(alias.asname or alias.name, getattr(node, "lineno", 0))
            return

        if isinstance(node, ast.Return):
            if node.value is not None:
                self._compile_expr(node.value)
            else:
                _emit(self.instrs, OP.PUSH_INT, 0, line=getattr(node, "lineno", 0))
            _emit(self.instrs, OP.RET, line=getattr(node, "lineno", 0))
            return

        if isinstance(node, ast.Pass):
            return

        raise ParseError(line=getattr(node, "lineno", 0), ip=0, msg=f"unsupported AST node: {type(node).__name__}")

    def _compile_for(self, node: ast.For) -> None:
        line = getattr(node, "lineno", 0)
        if not isinstance(node.target, ast.Name):
            raise ParseError(line=line, ip=0, msg="for-loop target must be a name")
        if (
            not isinstance(node.iter, ast.Call)
            or not isinstance(node.iter.func, ast.Name)
            or node.iter.func.id != "range"
            or node.iter.keywords
            or not 1 <= len(node.iter.args) <= 3
        ):
            raise ParseError(line=line, ip=0, msg="for-loops currently require range(...) with 1 to 3 positional arguments")

        iterable_name = self._new_temp_name()
        index_name = self._new_temp_name()
        self._compile_expr(node.iter)
        self._store_name(iterable_name, line)
        _emit(self.instrs, OP.PUSH_INT, 0, line=line)
        self._store_name(index_name, line)

        loop_label = f"for_loop_{len(self.instrs)}"
        exit_label = f"for_exit_{len(self.instrs)}"
        self._emit_label(loop_label)
        self._load_name(index_name, line)
        self._load_name(iterable_name, line)
        _emit(self.instrs, OP.CALL, BUILTIN_IDS["len"], 1, line=line)
        _emit(self.instrs, OP.OP, 7, line=line)
        _emit(self.instrs, OP.JZ, exit_label, line=line)
        self._load_name(iterable_name, line)
        self._load_name(index_name, line)
        _emit(self.instrs, OP.INDEX, 0, line=line)
        self._store_name(node.target.id, line)
        for stmt in node.body:
            self._compile_stmt(stmt)
        self._load_name(index_name, line)
        _emit(self.instrs, OP.PUSH_INT, 1, line=line)
        _emit(self.instrs, OP.OP, 1, line=line)
        self._store_name(index_name, line)
        _emit(self.instrs, OP.JMP, loop_label, line=line)
        self._emit_label(exit_label)
        for stmt in node.orelse:
            self._compile_stmt(stmt)

    def _compile_listcomp(self, node: ast.ListComp) -> None:
        line = getattr(node, "lineno", 0)
        if (
            len(node.generators) != 1
            or node.generators[0].ifs
            or node.generators[0].is_async
            or not isinstance(node.generators[0].target, ast.Name)
        ):
            raise ParseError(line=line, ip=0, msg="list comprehensions support one unfiltered name target")
        generator = node.generators[0]
        iterable = generator.iter
        if (
            not isinstance(iterable, ast.Call)
            or not isinstance(iterable.func, ast.Name)
            or iterable.func.id != "range"
            or iterable.keywords
            or not 1 <= len(iterable.args) <= 3
        ):
            raise ParseError(line=line, ip=0, msg="list comprehensions currently require range(...)")

        iterable_name = self._new_temp_name()
        index_name = self._new_temp_name()
        result_name = self._new_temp_name()
        target_name = self._new_temp_name()
        self._compile_expr(iterable)
        self._store_name(iterable_name, line)
        _emit(self.instrs, OP.PUSH_INT, 0, line=line)
        self._store_name(index_name, line)
        _emit(self.instrs, OP.BUILD_LIST, 0, line=line)
        self._store_name(result_name, line)

        loop_label = f"listcomp_loop_{len(self.instrs)}"
        exit_label = f"listcomp_exit_{len(self.instrs)}"
        self._emit_label(loop_label)
        self._load_name(index_name, line)
        self._load_name(iterable_name, line)
        _emit(self.instrs, OP.CALL, BUILTIN_IDS["len"], 1, line=line)
        _emit(self.instrs, OP.OP, 7, line=line)
        _emit(self.instrs, OP.JZ, exit_label, line=line)
        self._load_name(iterable_name, line)
        self._load_name(index_name, line)
        _emit(self.instrs, OP.INDEX, 0, line=line)
        self._store_name(target_name, line)
        self.name_overrides.append({generator.target.id: target_name})
        self._load_name(result_name, line)
        self._compile_expr(node.elt)
        _emit(self.instrs, OP.CALL_METHOD, self._name_id("append"), 1, line=line)
        _emit(self.instrs, OP.STACK, 3, line=line)
        self.name_overrides.pop()
        self._load_name(index_name, line)
        _emit(self.instrs, OP.PUSH_INT, 1, line=line)
        _emit(self.instrs, OP.OP, 1, line=line)
        self._store_name(index_name, line)
        _emit(self.instrs, OP.JMP, loop_label, line=line)
        self._emit_label(exit_label)
        self._load_name(result_name, line)

    def _compile_stmt(self, node: ast.AST) -> None:
        if isinstance(node, (ast.Assign, ast.Expr, ast.Return, ast.If, ast.While, ast.For, ast.Import, ast.ImportFrom, ast.Pass)):
            self._compile_expr(node)
            return
        if isinstance(node, ast.FunctionDef):
            self._compile_function(node)
            return
        raise ParseError(line=getattr(node, "lineno", 0), ip=0, msg=f"unsupported statement: {type(node).__name__}")

    def _compile_function(self, node: ast.FunctionDef) -> None:
        if (
            node.args.posonlyargs
            or node.args.vararg is not None
            or node.args.kwonlyargs
            or node.args.kwarg is not None
            or node.args.defaults
            or node.args.kw_defaults
        ):
            raise ParseError(
                line=getattr(node, "lineno", 0),
                ip=0,
                msg="functions support required positional arguments only",
            )
        if any(
            isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
            for stmt in node.body
            for child in ast.walk(stmt)
        ):
            raise ParseError(line=getattr(node, "lineno", 0), ip=0, msg="nested functions and classes are unsupported")
        func_id = self.function_id_by_node.get(id(node))
        if func_id is None:
            func_id = self._next_func_id()
            self.function_id_by_node[id(node)] = func_id
        self.function_ids[node.name] = func_id
        start_ip = len(self.instrs)
        _emit(self.instrs, OP.DEF, func_id, len(node.args.args), line=getattr(node, "lineno", 0))
        start_ip = len(self.instrs)
        self.funcs[func_id] = (start_ip, start_ip)
        local_scope = {}
        for idx, arg in enumerate(node.args.args):
            local_scope[arg.arg] = idx
        collector = _LocalNameCollector()
        for stmt in node.body:
            collector.visit(stmt)
        for name in collector.names:
            if name not in local_scope:
                local_scope[name] = len(local_scope)
        self.locals_stack.append(local_scope)
        for stmt in node.body:
            self._compile_stmt(stmt)
        self.locals_stack.pop()
        self.funcs[func_id] = (start_ip, len(self.instrs))
        _emit(self.instrs, OP.PUSH_INT, 0, line=getattr(node, "lineno", 0))
        _emit(self.instrs, OP.RET, line=getattr(node, "lineno", 0))
        self.funcs[func_id] = (start_ip, len(self.instrs))

    def compile(self) -> Program:
        self.source_names = {
            node.id for node in ast.walk(self._module) if isinstance(node, ast.Name)
        }
        for stmt in self._module.body:
            if isinstance(stmt, ast.FunctionDef):
                func_id = self._next_func_id()
                self.function_id_by_node[id(stmt)] = func_id
                self.function_ids[stmt.name] = func_id
        for stmt in self._module.body:
            self._compile_stmt(stmt)
        _emit(self.instrs, OP.HALT)
        self._resolve_labels()
        return Program(instrs=self.instrs, names=self.names, labels=self.labels, funcs=self.funcs, try_table=[])

    def visit_Module(self, node: ast.Module):
        self._module = node
        return self.compile()

    def visit(self, node):
        if isinstance(node, ast.Module):
            return self.visit_Module(node)
        return super().visit(node)


def compile_py(src: str, filename: str = "<stdin>") -> Program:
    cleaned = textwrap.dedent(src)
    tree = ast.parse(cleaned, filename=filename)
    front = PyFront(filename)
    return front.visit(tree)


__all__ = ["compile_py"]
