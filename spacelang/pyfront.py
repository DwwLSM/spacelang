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
        self.next_func_id = 10000
        self.pending_labels: list[tuple[str, int]] = []

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

    def _compile_expr(self, node: ast.AST) -> None:
        if isinstance(node, ast.Constant):
            value = node.value
            if isinstance(value, bool):
                _emit(self.instrs, OP.PUSH_INT, int(value), line=getattr(node, "lineno", 0))
            elif isinstance(value, int):
                _emit(self.instrs, OP.PUSH_INT, value, line=getattr(node, "lineno", 0))
            elif isinstance(value, str):
                chars = [ord(ch) for ch in value]
                _emit(self.instrs, OP.PUSH_STR, len(chars), *chars, line=getattr(node, "lineno", 0))
            elif value is None:
                _emit(self.instrs, OP.PUSH_INT, 0, line=getattr(node, "lineno", 0))
            else:
                raise ParseError(line=getattr(node, "lineno", 0), ip=0, msg=f"unsupported constant: {type(value).__name__}")
            return

        if isinstance(node, ast.Name):
            if node.id in self.locals_stack[-1]:
                slot = self.locals_stack[-1][node.id]
                _emit(self.instrs, OP.LOAD_LOCAL, slot, line=getattr(node, "lineno", 0))
            else:
                _emit(self.instrs, OP.LOAD_GLOBAL, self._name_id(node.id), line=getattr(node, "lineno", 0))
            return

        if isinstance(node, ast.Assign):
            self._compile_expr(node.value)
            if len(node.targets) != 1:
                raise ParseError(line=getattr(node, "lineno", 0), ip=0, msg="multi-target assignment is unsupported")
            target = node.targets[0]
            if isinstance(target, ast.Name):
                if self.locals_stack and target.id in self.locals_stack[-1]:
                    slot = self.locals_stack[-1][target.id]
                    _emit(self.instrs, OP.STORE_LOCAL, slot, line=getattr(node, "lineno", 0))
                else:
                    self._name_id(target.id)
                    _emit(self.instrs, OP.STORE_GLOBAL, self._name_id(target.id), line=getattr(node, "lineno", 0))
            else:
                raise ParseError(line=getattr(node, "lineno", 0), ip=0, msg="unsupported assignment target")
            return

        if isinstance(node, ast.Expr):
            self._compile_expr(node.value)
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

        if isinstance(node, ast.Compare):
            self._compile_expr(node.left)
            for idx, op in enumerate(node.ops):
                self._compile_expr(node.comparators[idx])
                op_map = {
                    ast.Eq: 6,
                    ast.NotEq: 9,
                    ast.Lt: 7,
                    ast.Gt: 8,
                    ast.LtE: 10,
                    ast.GtE: 11,
                }
                mapped = op_map.get(type(op))
                if mapped is None:
                    raise ParseError(line=getattr(node, "lineno", 0), ip=0, msg=f"unsupported compare op: {type(op).__name__}")
                _emit(self.instrs, OP.OP, mapped, line=getattr(node, "lineno", 0))
            return

        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                name = node.func.id
                if name in BUILTIN_IDS:
                    for arg in reversed(node.args):
                        self._compile_expr(arg)
                    _emit(self.instrs, OP.CALL, BUILTIN_IDS[name], len(node.args), line=getattr(node, "lineno", 0))
                    return
                if name in self.function_ids:
                    for arg in reversed(node.args):
                        self._compile_expr(arg)
                    _emit(self.instrs, OP.CALL, self.function_ids[name], len(node.args), line=getattr(node, "lineno", 0))
                    return
            if isinstance(node.func, ast.Attribute):
                self._compile_expr(node.func.value)
                for arg in reversed(node.args):
                    self._compile_expr(arg)
                _emit(self.instrs, OP.CALL_METHOD, self._name_id(node.func.attr), len(node.args), line=getattr(node, "lineno", 0))
                return
            raise ParseError(line=getattr(node, "lineno", 0), ip=0, msg=f"unsupported call target: {ast.dump(node.func)}")

        if isinstance(node, ast.Attribute):
            self._compile_expr(node.value)
            _emit(self.instrs, OP.GET_ATTR, self._name_id(node.attr), line=getattr(node, "lineno", 0))
            return

        if isinstance(node, ast.Subscript):
            self._compile_expr(node.slice)
            self._compile_expr(node.value)
            _emit(self.instrs, OP.INDEX, line=getattr(node, "lineno", 0))
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
            return

        if isinstance(node, ast.Import):
            for alias in node.names:
                module_name = alias.name
                mid = {"math": 0, "random": 1, "os": 2, "re": 3, "sys": 4}.get(module_name, 0)
                _emit(self.instrs, OP.IMPORT, mid, line=getattr(node, "lineno", 0))
            return

        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                _emit(self.instrs, OP.LOAD_GLOBAL, self._name_id(alias.name), line=getattr(node, "lineno", 0))
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

    def _compile_stmt(self, node: ast.AST) -> None:
        if isinstance(node, (ast.Assign, ast.Expr, ast.Return, ast.If, ast.While, ast.Import, ast.ImportFrom, ast.Pass)):
            self._compile_expr(node)
            return
        if isinstance(node, ast.FunctionDef):
            self._compile_function(node)
            return
        raise ParseError(line=getattr(node, "lineno", 0), ip=0, msg=f"unsupported statement: {type(node).__name__}")

    def _compile_function(self, node: ast.FunctionDef) -> None:
        if node.args.kwarg is not None:
            raise ParseError(line=getattr(node, "lineno", 0), ip=0, msg="KW functions are unsupported in this frontend")
        func_id = self._next_func_id()
        self.function_ids[node.name] = func_id
        start_ip = len(self.instrs)
        _emit(self.instrs, OP.DEF, func_id, len(node.args.args), line=getattr(node, "lineno", 0))
        start_ip = len(self.instrs)
        self.funcs[func_id] = (start_ip, start_ip)
        local_scope = {}
        for idx, arg in enumerate(node.args.args):
            local_scope[arg.arg] = idx
        self.locals_stack.append(local_scope)
        for stmt in node.body:
            self._compile_stmt(stmt)
        self.locals_stack.pop()
        self.funcs[func_id] = (start_ip, len(self.instrs))
        _emit(self.instrs, OP.PUSH_INT, 0, line=getattr(node, "lineno", 0))
        _emit(self.instrs, OP.RET, line=getattr(node, "lineno", 0))
        self.funcs[func_id] = (start_ip, len(self.instrs))

    def compile(self) -> Program:
        for stmt in self._module.body:
            self._compile_stmt(stmt)
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
