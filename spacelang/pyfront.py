from __future__ import annotations

import ast
from dataclasses import dataclass, field
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
        self.global_names: set[str] = set()
        self.nonlocal_names: set[str] = set()
        self.loaded_names: set[str] = set()
        self.nested_functions: list[ast.FunctionDef] = []

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, ast.Store) and node.id not in self.names:
            self.names.append(node.id)
        elif isinstance(node.ctx, ast.Load):
            self.loaded_names.add(node.id)

    def visit_Global(self, node: ast.Global) -> None:
        self.global_names.update(node.names)

    def visit_Nonlocal(self, node: ast.Nonlocal) -> None:
        self.nonlocal_names.update(node.names)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        if node.name not in self.names:
            self.names.append(node.name)
        self.nested_functions.append(node)

    def visit_ListComp(self, node: ast.ListComp) -> None:
        self.visit(node.elt)
        for generator in node.generators:
            self.visit(generator.iter)
            for condition in generator.ifs:
                self.visit(condition)


@dataclass
class _FunctionScope:
    node: ast.FunctionDef
    local_names: set[str]
    global_names: set[str]
    nonlocal_names: set[str]
    loaded_names: set[str]
    free_names: list[str] = field(default_factory=list)
    captured_names: set[str] = field(default_factory=set)
    children: list[_FunctionScope] = field(default_factory=list)


@dataclass
class _LoopContext:
    break_label: str
    continue_label: str
    break_drops_iterator: bool


@dataclass
class _FunctionSignature:
    positional_names: list[str]
    keyword_only_names: list[str]
    defaults: dict[str, ast.expr]
    vararg_name: str | None = None
    kwarg_name: str | None = None

    @property
    def parameter_names(self) -> list[str]:
        return [*self.positional_names, *self.keyword_only_names]


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
        self.function_signatures: dict[str, _FunctionSignature] = {}
        self.function_nodes: dict[str, ast.FunctionDef] = {}
        self.function_id_by_node: dict[int, int] = {}
        self.function_scopes: dict[int, _FunctionScope] = {}
        self.next_func_id = 10000
        self.pending_labels: list[tuple[str, int]] = []
        self.pending_nested_functions: list[ast.FunctionDef] = []
        self.next_temp_id = 0
        self.source_names: set[str] = set()
        self.name_overrides: list[dict[str, str]] = []
        self.loop_stack: list[_LoopContext] = []
        self.global_names_stack: list[set[str]] = [set()]
        self.function_scope_stack: list[_FunctionScope] = []

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
        if (
            len(self.locals_stack) > 1
            and name not in self.global_names_stack[-1]
            and name in self.locals_stack[-1]
        ):
            _emit(self.instrs, OP.LOAD_LOCAL, self.locals_stack[-1][name], line=line)
        else:
            _emit(self.instrs, OP.LOAD_GLOBAL, self._name_id(name), line=line)

    def _store_name(self, name: str, line: int) -> None:
        if (
            len(self.locals_stack) > 1
            and name not in self.global_names_stack[-1]
            and name in self.locals_stack[-1]
        ):
            _emit(self.instrs, OP.STORE_LOCAL, self.locals_stack[-1][name], line=line)
        else:
            _emit(self.instrs, OP.STORE_GLOBAL, self._name_id(name), line=line)

    def _is_local_name(self, name: str) -> bool:
        for overrides in reversed(self.name_overrides):
            if name in overrides:
                return True
        return (
            len(self.locals_stack) > 1
            and name not in self.global_names_stack[-1]
            and name in self.locals_stack[-1]
        )

    def _resolve_enclosing_name(
        self,
        name: str,
        ancestors: list[_FunctionScope],
    ) -> bool:
        for scope in ancestors:
            if name in scope.global_names:
                return False
            if name in scope.local_names or name in scope.free_names:
                return True
        return False

    def _nested_function_for_call(self, name: str) -> ast.FunctionDef | None:
        for scope in reversed(self.function_scope_stack):
            if scope.node.name == name and name in scope.free_names:
                return scope.node
            if name in scope.global_names:
                return None
            if name in scope.local_names:
                return next(
                    (child.node for child in scope.children if child.node.name == name),
                    None,
                )
        return None

    def _build_function_scope(
        self,
        node: ast.FunctionDef,
        ancestors: list[_FunctionScope],
    ) -> _FunctionScope:
        collector = _LocalNameCollector()
        for stmt in node.body:
            collector.visit(stmt)
        parameter_names = {
            arg.arg for arg in [*node.args.args, *node.args.kwonlyargs]
        }
        if node.args.vararg:
            parameter_names.add(node.args.vararg.arg)
        if node.args.kwarg:
            parameter_names.add(node.args.kwarg.arg)
        conflicting = collector.global_names & collector.nonlocal_names
        if conflicting:
            name = sorted(conflicting)[0]
            raise ParseError(line=node.lineno, ip=0, msg=f"name {name!r} is nonlocal and global")
        local_names = (
            parameter_names | set(collector.names)
        ) - collector.global_names - collector.nonlocal_names
        scope = _FunctionScope(
            node=node,
            local_names=local_names,
            global_names=collector.global_names,
            nonlocal_names=collector.nonlocal_names,
            loaded_names=collector.loaded_names,
        )
        self.function_scopes[id(node)] = scope

        candidates = collector.loaded_names | collector.nonlocal_names
        for name in sorted(candidates):
            if name in local_names or name in collector.global_names:
                continue
            if name in collector.nonlocal_names:
                if not self._resolve_enclosing_name(name, ancestors):
                    raise ParseError(
                        line=node.lineno,
                        ip=0,
                        msg=f"no binding for nonlocal {name!r} found",
                    )
                scope.free_names.append(name)
            elif self._resolve_enclosing_name(name, ancestors):
                scope.free_names.append(name)

        for child_node in collector.nested_functions:
            child = self._build_function_scope(child_node, [scope, *ancestors])
            scope.children.append(child)
            for name in child.free_names:
                if name in scope.local_names:
                    scope.captured_names.add(name)
                elif name not in scope.global_names and self._resolve_enclosing_name(name, ancestors):
                    if name not in scope.free_names:
                        scope.free_names.append(name)

        return scope

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
                _emit(self.instrs, OP.PUSH_NONE, line=getattr(node, "lineno", 0))
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

        if isinstance(node, ast.IfExp):
            line = getattr(node, "lineno", 0)
            else_label = f"ifexp_else_{len(self.instrs)}"
            end_label = f"ifexp_end_{len(self.instrs)}"
            self._compile_expr(node.test)
            _emit(self.instrs, OP.JZ, else_label, line=line)
            self._compile_expr(node.body)
            _emit(self.instrs, OP.JMP, end_label, line=line)
            self._emit_label(else_label)
            self._compile_expr(node.orelse)
            self._emit_label(end_label)
            return

        if isinstance(node, ast.Assign):
            self._compile_expr(node.value)
            for index, target in enumerate(node.targets):
                if index + 1 < len(node.targets):
                    _emit(self.instrs, OP.STACK, 1, line=getattr(node, "lineno", 0))
                self._compile_store_target(target, getattr(node, "lineno", 0))
            return

        if isinstance(node, ast.AugAssign):
            op_map = {
                ast.Add: 1,
                ast.Sub: 2,
                ast.Mult: 3,
                ast.Div: 4,
                ast.Mod: 5,
            }
            op = op_map.get(type(node.op))
            if op is None:
                raise ParseError(line=getattr(node, "lineno", 0), ip=0, msg=f"unsupported augmented assignment op: {type(node.op).__name__}")
            line = getattr(node, "lineno", 0)
            target = node.target
            if isinstance(target, ast.Name):
                self._load_name(target.id, line)
            elif isinstance(target, ast.Attribute):
                object_name = self._new_temp_name()
                self._compile_expr(target.value)
                self._store_name(object_name, line)
                self._load_name(object_name, line)
                _emit(self.instrs, OP.GET_ATTR, self._name_id(target.attr), line=line)
            elif isinstance(target, ast.Subscript) and not isinstance(target.slice, ast.Slice):
                object_name = self._new_temp_name()
                index_name = self._new_temp_name()
                self._compile_expr(target.value)
                self._store_name(object_name, line)
                self._compile_expr(target.slice)
                self._store_name(index_name, line)
                self._load_name(object_name, line)
                self._load_name(index_name, line)
                _emit(self.instrs, OP.INDEX, 0, line=line)
            else:
                raise ParseError(line=line, ip=0, msg="unsupported augmented assignment target")
            self._compile_expr(node.value)
            _emit(self.instrs, OP.OP, op, line=getattr(node, "lineno", 0))
            if isinstance(target, ast.Name):
                self._store_name(target.id, line)
            elif isinstance(target, ast.Attribute):
                self._load_name(object_name, line)
                _emit(self.instrs, OP.STORE_ATTR, self._name_id(target.attr), line=line)
            else:
                self._load_name(object_name, line)
                self._load_name(index_name, line)
                _emit(self.instrs, OP.STORE_INDEX, line=line)
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
                local_callable = self._is_local_name(name)
                if name in BUILTIN_IDS and not local_callable:
                    line = getattr(node, "lineno", 0)
                    if self._has_expanded_arguments(node):
                        self._compile_call_argument_containers(node)
                        _emit(self.instrs, OP.CALL_BUILTIN_EX, BUILTIN_IDS[name], line=line)
                        return
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
                if name in self.function_ids and not local_callable:
                    self._compile_user_function_call(node, name)
                    return
                nested_function = self._nested_function_for_call(name) if local_callable else None
                if nested_function is not None:
                    self._compile_nested_function_call(node, nested_function)
                    return
                self._compile_expr(node.func)
                for arg in node.args:
                    self._compile_expr(arg)
                if node.keywords:
                    for keyword in node.keywords:
                        if keyword.arg is None:
                            raise ParseError(
                                line=getattr(node, "lineno", 0),
                                ip=0,
                                msg="expanded keyword arguments are unsupported",
                            )
                        _emit(
                            self.instrs,
                            OP.PUSH_INT,
                            self._name_id(keyword.arg),
                            line=getattr(node, "lineno", 0),
                        )
                        self._compile_expr(keyword.value)
                    _emit(
                        self.instrs,
                        OP.CALL_OBJ_KW,
                        len(node.args),
                        len(node.keywords),
                        line=getattr(node, "lineno", 0),
                    )
                else:
                    _emit(self.instrs, OP.CALL_OBJ, len(node.args), line=getattr(node, "lineno", 0))
                return
            if isinstance(node.func, ast.Attribute):
                if self._has_expanded_arguments(node):
                    self._compile_expr(node.func)
                    self._compile_call_argument_containers(node)
                    _emit(self.instrs, OP.CALL_OBJ_EX, line=getattr(node, "lineno", 0))
                    return
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
            if self._has_expanded_arguments(node):
                self._compile_expr(node.func)
                self._compile_call_argument_containers(node)
                _emit(self.instrs, OP.CALL_OBJ_EX, line=getattr(node, "lineno", 0))
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
            for item in node.elts:
                self._compile_expr(item)
            _emit(self.instrs, OP.BUILD_LIST, len(node.elts), line=getattr(node, "lineno", 0))
            return

        if isinstance(node, ast.Tuple):
            for item in node.elts:
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
            normal_exit_label = f"while_normal_exit_{len(self.instrs)}"
            break_label = f"while_break_{len(self.instrs)}"
            self._emit_label(loop_label)
            self._compile_expr(node.test)
            _emit(self.instrs, OP.JZ, normal_exit_label, line=getattr(node, "lineno", 0))
            self.loop_stack.append(_LoopContext(break_label, loop_label, False))
            for stmt in node.body:
                self._compile_stmt(stmt)
            self.loop_stack.pop()
            _emit(self.instrs, OP.JMP, loop_label, line=getattr(node, "lineno", 0))
            self._emit_label(normal_exit_label)
            for stmt in node.orelse:
                self._compile_stmt(stmt)
            self._emit_label(break_label)
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
                _emit(self.instrs, OP.PUSH_NONE, line=getattr(node, "lineno", 0))
            _emit(self.instrs, OP.RET, line=getattr(node, "lineno", 0))
            return

        if isinstance(node, ast.Pass):
            return

        if isinstance(node, ast.Global):
            return

        if isinstance(node, ast.Nonlocal):
            return

        if isinstance(node, ast.Break):
            if not self.loop_stack:
                raise ParseError(line=getattr(node, "lineno", 0), ip=0, msg="'break' outside loop")
            loop = self.loop_stack[-1]
            if loop.break_drops_iterator:
                _emit(self.instrs, OP.STACK, 3, line=getattr(node, "lineno", 0))
            _emit(self.instrs, OP.JMP, loop.break_label, line=getattr(node, "lineno", 0))
            return

        if isinstance(node, ast.Continue):
            if not self.loop_stack:
                raise ParseError(line=getattr(node, "lineno", 0), ip=0, msg="'continue' outside loop")
            _emit(self.instrs, OP.JMP, self.loop_stack[-1].continue_label, line=getattr(node, "lineno", 0))
            return

        raise ParseError(line=getattr(node, "lineno", 0), ip=0, msg=f"unsupported AST node: {type(node).__name__}")

    def _compile_for(self, node: ast.For) -> None:
        line = getattr(node, "lineno", 0)
        if not isinstance(node.target, ast.Name):
            raise ParseError(line=line, ip=0, msg="for-loop target must be a name")
        self._compile_expr(node.iter)
        _emit(self.instrs, OP.GET_ITER, line=line)

        loop_label = f"for_loop_{len(self.instrs)}"
        normal_exit_label = f"for_normal_exit_{len(self.instrs)}"
        break_label = f"for_break_{len(self.instrs)}"
        self._emit_label(loop_label)
        _emit(self.instrs, OP.FOR_ITER, normal_exit_label, line=line)
        self._store_name(node.target.id, line)
        self.loop_stack.append(_LoopContext(break_label, loop_label, True))
        for stmt in node.body:
            self._compile_stmt(stmt)
        self.loop_stack.pop()
        _emit(self.instrs, OP.JMP, loop_label, line=line)
        self._emit_label(normal_exit_label)
        for stmt in node.orelse:
            self._compile_stmt(stmt)
        self._emit_label(break_label)

    def _compile_store_target(self, target: ast.expr, line: int) -> None:
        if isinstance(target, ast.Name):
            self._store_name(target.id, line)
            return
        if isinstance(target, (ast.Tuple, ast.List)):
            if any(isinstance(item, ast.Starred) for item in target.elts):
                raise ParseError(line=line, ip=0, msg="starred assignment targets are unsupported")
            _emit(self.instrs, OP.UNPACK_SEQUENCE, len(target.elts), line=line)
            for item in target.elts:
                self._compile_store_target(item, line)
            return
        if isinstance(target, ast.Attribute):
            self._compile_expr(target.value)
            _emit(self.instrs, OP.STORE_ATTR, self._name_id(target.attr), line=line)
            return
        if isinstance(target, ast.Subscript) and not isinstance(target.slice, ast.Slice):
            self._compile_expr(target.value)
            self._compile_expr(target.slice)
            _emit(self.instrs, OP.STORE_INDEX, line=line)
            return
        raise ParseError(line=line, ip=0, msg="unsupported assignment target")

    def _compile_listcomp(self, node: ast.ListComp) -> None:
        line = getattr(node, "lineno", 0)
        result_name = self._new_temp_name()
        _emit(self.instrs, OP.BUILD_LIST, 0, line=line)
        self._store_name(result_name, line)

        if any(
            generator.is_async or not isinstance(generator.target, ast.Name)
            for generator in node.generators
        ):
            raise ParseError(
                line=line,
                ip=0,
                msg="list comprehensions require synchronous name targets",
            )

        def compile_generator(index: int) -> None:
            generator = node.generators[index]
            self._compile_expr(generator.iter)
            _emit(self.instrs, OP.GET_ITER, line=line)

            loop_label = f"listcomp_loop_{len(self.instrs)}"
            exit_label = f"listcomp_exit_{len(self.instrs)}"
            self._emit_label(loop_label)
            _emit(self.instrs, OP.FOR_ITER, exit_label, line=line)
            target_name = self._new_temp_name()
            self._store_name(target_name, line)
            self.name_overrides.append({generator.target.id: target_name})

            for condition in generator.ifs:
                self._compile_expr(condition)
                _emit(self.instrs, OP.JZ, loop_label, line=line)

            if index + 1 == len(node.generators):
                self._load_name(result_name, line)
                self._compile_expr(node.elt)
                _emit(self.instrs, OP.CALL_METHOD, self._name_id("append"), 1, line=line)
                _emit(self.instrs, OP.STACK, 3, line=line)
            else:
                compile_generator(index + 1)

            self.name_overrides.pop()
            _emit(self.instrs, OP.JMP, loop_label, line=line)
            self._emit_label(exit_label)

        compile_generator(0)
        self._load_name(result_name, line)

    def _compile_stmt(self, node: ast.AST) -> None:
        if isinstance(
            node,
            (
                ast.Assign,
                ast.AugAssign,
                ast.Expr,
                ast.Return,
                ast.If,
                ast.While,
                ast.For,
                ast.Import,
                ast.ImportFrom,
                ast.Global,
                ast.Nonlocal,
                ast.Pass,
                ast.Break,
                ast.Continue,
            ),
        ):
            self._compile_expr(node)
            return
        if isinstance(node, ast.FunctionDef):
            if len(self.locals_stack) > 1:
                self._compile_nested_function(node)
            else:
                self._compile_function(node)
            return
        raise ParseError(line=getattr(node, "lineno", 0), ip=0, msg=f"unsupported statement: {type(node).__name__}")

    def _compile_function(self, node: ast.FunctionDef, *, nested: bool = False) -> None:
        if node.args.posonlyargs:
            raise ParseError(
                line=getattr(node, "lineno", 0),
                ip=0,
                msg="positional-only parameters are unsupported",
            )
        positional_names = [arg.arg for arg in node.args.args]
        keyword_only_names = [arg.arg for arg in node.args.kwonlyargs]
        parameter_names = [*positional_names, *keyword_only_names]
        required_count = len(positional_names) - len(node.args.defaults)
        defaults = dict(zip(positional_names[required_count:], node.args.defaults))
        defaults.update(
            (name, default)
            for name, default in zip(keyword_only_names, node.args.kw_defaults)
            if default is not None
        )
        if any(not self._is_supported_default(value) for value in defaults.values()):
            raise ParseError(
                line=getattr(node, "lineno", 0),
                ip=0,
                msg="function defaults must be immutable literals",
            )
        if any(
            isinstance(child, (ast.AsyncFunctionDef, ast.ClassDef))
            for child in ast.walk(node)
        ):
            raise ParseError(line=getattr(node, "lineno", 0), ip=0, msg="async functions and classes are unsupported")
        func_id = self.function_id_by_node.get(id(node))
        if func_id is None:
            func_id = self._next_func_id()
            self.function_id_by_node[id(node)] = func_id
        if not nested:
            self.function_ids[node.name] = func_id
            self.function_signatures[node.name] = _FunctionSignature(
                positional_names,
                keyword_only_names,
                defaults,
                node.args.vararg.arg if node.args.vararg else None,
                node.args.kwarg.arg if node.args.kwarg else None,
            )
        local_parameter_names = [
            *parameter_names,
            *([node.args.vararg.arg] if node.args.vararg else []),
            *([node.args.kwarg.arg] if node.args.kwarg else []),
        ]
        _emit(self.instrs, OP.DEF, func_id, len(local_parameter_names), line=getattr(node, "lineno", 0))
        start_ip = len(self.instrs)
        self.funcs[func_id] = (start_ip, start_ip)

        scope = self.function_scopes.get(id(node))
        if scope is None:
            scope = self._build_function_scope(node, [])

        local_scope: dict[str, int] = {}
        for idx, arg in enumerate([*node.args.args, *node.args.kwonlyargs]):
            local_scope[arg.arg] = idx
        if node.args.vararg:
            local_scope[node.args.vararg.arg] = len(local_scope)
        if node.args.kwarg:
            local_scope[node.args.kwarg.arg] = len(local_scope)
        collector = _LocalNameCollector()
        for stmt in node.body:
            collector.visit(stmt)
        conflicting_globals = set(local_parameter_names) & collector.global_names
        if conflicting_globals:
            name = sorted(conflicting_globals)[0]
            raise ParseError(
                line=getattr(node, "lineno", 0),
                ip=0,
                msg=f"parameter {name!r} cannot be declared global",
            )
        for name in collector.names:
            if name in scope.local_names and name not in local_scope:
                local_scope[name] = len(local_scope)
        for name in scope.free_names:
            if name not in local_scope:
                local_scope[name] = len(local_scope)
        enclosing_loops, self.loop_stack = self.loop_stack, []
        self.locals_stack.append(local_scope)
        self.global_names_stack.append(collector.global_names)
        self.function_scope_stack.append(scope)

        for name in sorted(scope.captured_names):
            _emit(self.instrs, OP.CELLIFY, local_scope[name], line=node.lineno)
        for index, name in enumerate(scope.free_names):
            _emit(self.instrs, OP.LOAD_DEREF, index, line=node.lineno)
            _emit(self.instrs, OP.STORE_LOCAL, local_scope[name], line=node.lineno)

        for stmt in node.body:
            self._compile_stmt(stmt)
        self.global_names_stack.pop()
        self.locals_stack.pop()
        self.function_scope_stack.pop()
        self.loop_stack = enclosing_loops
        self.funcs[func_id] = (start_ip, len(self.instrs))
        _emit(self.instrs, OP.PUSH_INT, 0, line=getattr(node, "lineno", 0))
        _emit(self.instrs, OP.RET, line=getattr(node, "lineno", 0))
        self.funcs[func_id] = (start_ip, len(self.instrs))

    def _compile_nested_function(self, node: ast.FunctionDef) -> None:
        line = getattr(node, "lineno", 0)
        scope = self.function_scopes[id(node)]
        func_id = self.function_id_by_node[id(node)]
        if any(not self._is_supported_default(value) for value in node.args.defaults):
            raise ParseError(
                line=line,
                ip=0,
                msg="function defaults must be immutable literals",
            )

        for name in scope.free_names:
            if (
                name not in self.global_names_stack[-1]
                and name in self.locals_stack[-1]
            ):
                _emit(
                    self.instrs,
                    OP.LOAD_CELL_REF,
                    self.locals_stack[-1][name],
                    line=line,
                )
            else:
                raise ParseError(
                    line=line,
                    ip=0,
                    msg=f"cannot capture enclosing name {name!r}",
                )
        positional_names = [arg.arg for arg in node.args.args]
        keyword_only_names = [arg.arg for arg in node.args.kwonlyargs]
        parameter_names = [*positional_names, *keyword_only_names]
        keyword_only_defaults = [
            (name, default)
            for name, default in zip(keyword_only_names, node.args.kw_defaults)
            if default is not None
        ]
        for name in parameter_names:
            _emit(self.instrs, OP.PUSH_INT, self._name_id(name), line=line)
        for default in node.args.defaults:
            self._compile_expr(default)
        for name, default in keyword_only_defaults:
            _emit(self.instrs, OP.PUSH_INT, self._name_id(name), line=line)
            self._compile_expr(default)
        if node.args.vararg or node.args.kwarg:
            if node.args.vararg:
                _emit(self.instrs, OP.PUSH_INT, self._name_id(node.args.vararg.arg), line=line)
            if node.args.kwarg:
                _emit(self.instrs, OP.PUSH_INT, self._name_id(node.args.kwarg.arg), line=line)
            closure_op = OP.MAKE_CLOSURE_ARGS
            closure_args = (
                func_id,
                len(scope.free_names),
                len(positional_names),
                len(keyword_only_names),
                len(node.args.defaults),
                len(keyword_only_defaults),
                int(node.args.vararg is not None),
                int(node.args.kwarg is not None),
            )
        elif keyword_only_names:
            closure_op = OP.MAKE_CLOSURE_KWONLY
            closure_args = (
                func_id,
                len(scope.free_names),
                len(positional_names),
                len(keyword_only_names),
                len(node.args.defaults),
                len(keyword_only_defaults),
            )
        else:
            closure_op = OP.MAKE_CLOSURE_SIG
            closure_args = (
                func_id,
                len(scope.free_names),
                len(parameter_names),
                len(node.args.defaults),
            )
        _emit(
            self.instrs,
            closure_op,
            *closure_args,
            line=line,
        )
        self._store_name(node.name, line)
        self.pending_nested_functions.append(node)

    def _compile_nested_function_call(
        self,
        node: ast.Call,
        function: ast.FunctionDef,
    ) -> None:
        line = getattr(node, "lineno", 0)
        if self._has_expanded_arguments(node):
            self._load_name(function.name, line)
            self._compile_call_argument_containers(node)
            _emit(self.instrs, OP.CALL_OBJ_EX, line=line)
            return
        positional_names = [arg.arg for arg in function.args.args]
        keyword_only_names = [arg.arg for arg in function.args.kwonlyargs]
        parameter_names = [*positional_names, *keyword_only_names]
        required_count = len(positional_names) - len(function.args.defaults)
        defaults = dict(zip(positional_names[required_count:], function.args.defaults))
        defaults.update(
            (name, default)
            for name, default in zip(keyword_only_names, function.args.kw_defaults)
            if default is not None
        )
        if len(node.args) > len(positional_names) and function.args.vararg is None:
            raise ParseError(line=line, ip=0, msg=f"too many positional arguments for {function.name}")
        if any(isinstance(arg, ast.Starred) for arg in node.args):
            raise ParseError(line=line, ip=0, msg="expanded positional arguments are unsupported")

        provided_names = set(positional_names[:len(node.args)])
        ordered_names = positional_names[:len(node.args)]
        keyword_names: set[str] = set()
        for keyword in node.keywords:
            if keyword.arg is None:
                raise ParseError(line=line, ip=0, msg="expanded keyword arguments are unsupported")
            if keyword.arg not in parameter_names and function.args.kwarg is None:
                raise ParseError(
                    line=line,
                    ip=0,
                    msg=f"unexpected keyword argument {keyword.arg!r} for {function.name}",
                )
            if keyword.arg in ordered_names or keyword.arg in keyword_names:
                raise ParseError(line=line, ip=0, msg=f"multiple values for argument {keyword.arg!r}")
            keyword_names.add(keyword.arg)
            ordered_names.append(keyword.arg)

        provided_names.update(keyword_names)

        for parameter_name in parameter_names:
            if parameter_name not in provided_names and parameter_name not in defaults:
                raise ParseError(
                    line=line,
                    ip=0,
                    msg=f"missing required argument {parameter_name!r} for {function.name}",
                )
        self._load_name(function.name, line)
        for argument in node.args:
            self._compile_expr(argument)
        for keyword in node.keywords:
            _emit(self.instrs, OP.PUSH_INT, self._name_id(keyword.arg), line=line)
            self._compile_expr(keyword.value)
        _emit(self.instrs, OP.CALL_OBJ_KW, len(node.args), len(node.keywords), line=line)

    def _has_expanded_arguments(self, node: ast.Call) -> bool:
        return any(isinstance(argument, ast.Starred) for argument in node.args) or any(
            keyword.arg is None for keyword in node.keywords
        )

    def _compile_call_argument_containers(self, node: ast.Call) -> None:
        line = getattr(node, "lineno", 0)
        _emit(self.instrs, OP.BUILD_LIST, 0, line=line)
        for argument in node.args:
            if isinstance(argument, ast.Starred):
                self._compile_expr(argument.value)
            else:
                self._compile_expr(argument)
                _emit(self.instrs, OP.BUILD_LIST, 1, line=line)
            _emit(self.instrs, OP.LIST_EXTEND, line=line)

        _emit(self.instrs, OP.BUILD_DICT, 0, line=line)
        for keyword in node.keywords:
            if keyword.arg is None:
                self._compile_expr(keyword.value)
            else:
                _emit(
                    self.instrs,
                    OP.PUSH_STR,
                    len(keyword.arg),
                    *map(ord, keyword.arg),
                    line=line,
                )
                self._compile_expr(keyword.value)
                _emit(self.instrs, OP.BUILD_DICT, 1, line=line)
            _emit(self.instrs, OP.DICT_MERGE, line=line)

    def _compile_function_closure(self, node: ast.FunctionDef, func_id: int, line: int) -> None:
        positional_names = [arg.arg for arg in node.args.args]
        keyword_only_names = [arg.arg for arg in node.args.kwonlyargs]
        parameter_names = [*positional_names, *keyword_only_names]
        keyword_only_defaults = [
            (name, default)
            for name, default in zip(keyword_only_names, node.args.kw_defaults)
            if default is not None
        ]
        for name in parameter_names:
            _emit(self.instrs, OP.PUSH_INT, self._name_id(name), line=line)
        for default in node.args.defaults:
            self._compile_expr(default)
        for name, default in keyword_only_defaults:
            _emit(self.instrs, OP.PUSH_INT, self._name_id(name), line=line)
            self._compile_expr(default)
        if node.args.vararg:
            _emit(self.instrs, OP.PUSH_INT, self._name_id(node.args.vararg.arg), line=line)
        if node.args.kwarg:
            _emit(self.instrs, OP.PUSH_INT, self._name_id(node.args.kwarg.arg), line=line)
        if node.args.vararg or node.args.kwarg:
            _emit(
                self.instrs,
                OP.MAKE_CLOSURE_ARGS,
                func_id,
                0,
                len(positional_names),
                len(keyword_only_names),
                len(node.args.defaults),
                len(keyword_only_defaults),
                int(node.args.vararg is not None),
                int(node.args.kwarg is not None),
                line=line,
            )
        elif keyword_only_names:
            _emit(
                self.instrs,
                OP.MAKE_CLOSURE_KWONLY,
                func_id,
                0,
                len(positional_names),
                len(keyword_only_names),
                len(node.args.defaults),
                len(keyword_only_defaults),
                line=line,
            )
        else:
            _emit(
                self.instrs,
                OP.MAKE_CLOSURE_SIG,
                func_id,
                0,
                len(parameter_names),
                len(node.args.defaults),
                line=line,
            )

    def _is_supported_default(self, node: ast.expr) -> bool:
        if isinstance(node, ast.Constant):
            return node.value is None or isinstance(node.value, (bool, int, str))
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            return isinstance(node.operand, ast.Constant) and type(node.operand.value) is int
        if isinstance(node, ast.Tuple):
            return all(self._is_supported_default(item) for item in node.elts)
        return False

    def _compile_user_function_call(self, node: ast.Call, name: str) -> None:
        line = getattr(node, "lineno", 0)
        if self._has_expanded_arguments(node):
            self._compile_function_closure(self.function_nodes[name], self.function_ids[name], line)
            self._compile_call_argument_containers(node)
            _emit(self.instrs, OP.CALL_OBJ_EX, line=line)
            return
        signature = self.function_signatures[name]
        positional_names = signature.positional_names
        keyword_only_names = signature.keyword_only_names
        parameter_names = signature.parameter_names
        bound: dict[str, str] = {}
        provided_names = positional_names[:min(len(node.args), len(positional_names))]
        if len(node.args) > len(positional_names) and signature.vararg_name is None:
            raise ParseError(line=line, ip=0, msg=f"too many positional arguments for {name}")
        if any(isinstance(arg, ast.Starred) for arg in node.args):
            raise ParseError(line=line, ip=0, msg="expanded positional arguments are unsupported")

        keyword_names: set[str] = set()
        for keyword in node.keywords:
            if keyword.arg is None:
                raise ParseError(line=line, ip=0, msg="expanded keyword arguments are unsupported")
            if keyword.arg not in parameter_names and signature.kwarg_name is None:
                raise ParseError(line=line, ip=0, msg=f"unexpected keyword argument {keyword.arg!r} for {name}")
            if keyword.arg in provided_names or keyword.arg in keyword_names:
                raise ParseError(line=line, ip=0, msg=f"multiple values for argument {keyword.arg!r}")
            keyword_names.add(keyword.arg)
            if keyword.arg in parameter_names:
                bound[keyword.arg] = self._new_temp_name()

        for parameter_name, value in zip(provided_names, node.args):
            temp_name = self._new_temp_name()
            self._compile_expr(value)
            self._store_name(temp_name, line)
            bound[parameter_name] = temp_name
        vararg_temps = []
        if signature.vararg_name:
            for value in node.args[len(positional_names):]:
                temp_name = self._new_temp_name()
                self._compile_expr(value)
                self._store_name(temp_name, line)
                vararg_temps.append(temp_name)
        for parameter_name in parameter_names:
            if parameter_name in bound:
                continue
            elif parameter_name in signature.defaults:
                continue
            else:
                raise ParseError(
                    line=line,
                    ip=0,
                    msg=f"missing required argument {parameter_name!r} for {name}",
                )
        extra_keyword_temps = {
            keyword.arg: self._new_temp_name()
            for keyword in node.keywords
            if keyword.arg not in parameter_names
        }
        for keyword in node.keywords:
            temp_name = bound.get(keyword.arg)
            if temp_name is None:
                temp_name = extra_keyword_temps.get(keyword.arg)
            self._compile_expr(keyword.value)
            self._store_name(temp_name, line)
        for parameter_name in parameter_names:
            if parameter_name in bound:
                self._load_name(bound[parameter_name], line)
            elif parameter_name in signature.defaults:
                self._compile_expr(signature.defaults[parameter_name])
        if signature.vararg_name:
            for temp_name in vararg_temps:
                self._load_name(temp_name, line)
            _emit(self.instrs, OP.BUILD_TUPLE, len(vararg_temps), line=line)
        if signature.kwarg_name:
            for keyword_name, temp_name in extra_keyword_temps.items():
                _emit(self.instrs, OP.PUSH_STR, len(keyword_name), *map(ord, keyword_name), line=line)
                self._load_name(temp_name, line)
            _emit(self.instrs, OP.BUILD_DICT, len(extra_keyword_temps), line=line)
        argument_count = (
            len(parameter_names)
            + bool(signature.vararg_name)
            + bool(signature.kwarg_name)
        )
        _emit(self.instrs, OP.CALL, self.function_ids[name], argument_count, line=line)

    def compile(self) -> Program:
        self.source_names = {
            node.id for node in ast.walk(self._module) if isinstance(node, ast.Name)
        }

        def assign_function_ids(scope: _FunctionScope) -> None:
            func_id = self._next_func_id()
            self.function_id_by_node[id(scope.node)] = func_id
            for child in scope.children:
                assign_function_ids(child)

        for stmt in self._module.body:
            if isinstance(stmt, ast.FunctionDef):
                scope = self._build_function_scope(stmt, [])
                assign_function_ids(scope)
                self.function_ids[stmt.name] = self.function_id_by_node[id(stmt)]
                self.function_nodes[stmt.name] = stmt
                positional_names = [arg.arg for arg in stmt.args.args]
                keyword_only_names = [arg.arg for arg in stmt.args.kwonlyargs]
                required_count = len(positional_names) - len(stmt.args.defaults)
                defaults = dict(zip(positional_names[required_count:], stmt.args.defaults))
                defaults.update(
                    (name, default)
                    for name, default in zip(keyword_only_names, stmt.args.kw_defaults)
                    if default is not None
                )
                self.function_signatures[stmt.name] = _FunctionSignature(
                    positional_names,
                    keyword_only_names,
                    defaults,
                    stmt.args.vararg.arg if stmt.args.vararg else None,
                    stmt.args.kwarg.arg if stmt.args.kwarg else None,
                )
        for stmt in self._module.body:
            self._compile_stmt(stmt)
        _emit(self.instrs, OP.HALT)
        pending_index = 0
        while pending_index < len(self.pending_nested_functions):
            node = self.pending_nested_functions[pending_index]
            pending_index += 1
            self._compile_function(node, nested=True)
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
