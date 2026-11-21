#!/usr/bin/env python3
"""Diagnose how far ``native/spc.py`` is from compiling itself (read-only).

``native/spc.py`` is a compiler written in a restricted Python subset.  Stage 0
is the ordinary Python toolchain (``spacelang/pyfront.py``); stage 1 uses the
``compiler.exe`` built from ``spc.py`` itself.  For ``spc.py`` to compile its
own source, the language *it accepts* must cover the language *it is written
in*.  This tool reports that relationship:

1. an AST census of ``native/spc.py``;
2. a construct table: for every language feature used by the file, whether the
   current ``spc.py`` frontend accepts it, how often it occurs and where;
3. the first failure produced by feeding ``native/spc.py`` to its own
   tokenizer/parser (there is none once the fixed point is reached), with the
   source line and the AST node type on that line.

The tool only reads the repository; it never writes anything (except the
optional ``--json`` report).  It is the planning instrument from the
self-hosting work: the "missing" table is the work list, and it should stay
empty as the compiler grows new syntax.

Usage::

    py -S tools/bootstrap_audit.py
    py -S tools/bootstrap_audit.py --json build/bootstrap_audit.json
"""

from __future__ import annotations

import argparse
import ast
import collections
import hashlib
import json
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPC = ROOT / "native" / "spc.py"

# Builtins the spc.py frontend can emit (spc.py BUILTINS table).
SPC_BUILTINS = {"print", "input", "len", "int", "float", "str", "bool", "abs", "range", "open"}

# Every construct the audit recognises, and whether native/spc.py accepts it.
# This table is the contract between the compiler and its own source: the
# source may only use entries marked True.
FEATURE_SUPPORT = {
    "assignment to a name": True,
    "expression statement": True,
    "augmented assignment": False,
    "arithmetic binop": True,
    "comparison": True,
    "boolean and / or": True,
    "not": True,
    "unary minus": True,
    "int literal": True,
    "float literal": False,
    "string literal": True,
    "None literal": True,
    "bool literal": True,
    "module docstring / triple-quoted string": False,
    "list literal": True,
    "tuple literal": False,
    "dict literal": True,
    "set literal": False,
    "subscript read": True,
    "subscript assignment": True,
    "slice expression": True,
    "attribute read": True,
    "method call": True,
    "call to a known builtin": True,
    "call to a user-defined function": True,
    "call to an unresolved name": True,
    "keyword argument": False,
    "starred argument": False,
    "membership comparison (in / not in)": True,
    "identity comparison (is / is not)": True,
    "if / elif / else": True,
    "while": True,
    "for over range()": True,
    "for over another iterable": True,
    "break statement": True,
    "continue statement": True,
    "pass statement": True,
    "def / function definition": True,
    "return statement": True,
    "global declaration": True,
    "nonlocal statement": False,
    "conditional expression": False,
    "f-string": False,
    "comprehension": False,
    "lambda": False,
    "class definition": False,
    "try statement": False,
    "del statement": False,
    "match statement": False,
}


class ParseFailure(Exception):
    """Raised by the audited module's ``fail`` replacement."""

    def __init__(self, message: str, prepared_line: int):
        super().__init__(message)
        self.message = message
        self.prepared_line = prepared_line


def read_source() -> str:
    return SPC.read_text(encoding="utf-8")


def strip_entrypoint(source: str) -> str:
    """Drop the trailing top-level ``main()`` so the module can be imported."""
    stripped = source.rstrip()
    if stripped.endswith("main()"):
        return stripped[: -len("main()")]
    return source


def load_spc_module(source: str) -> types.ModuleType:
    module = types.ModuleType("spc_audit")
    module.__dict__["__name__"] = "spc_audit"
    module.__dict__["__file__"] = str(SPC)
    exec(compile(strip_entrypoint(source), str(SPC), "exec"), module.__dict__)
    return module


def prepared_line_map(original: str) -> list[int]:
    """Map a prepared line index (as produced by ``prepare``) to a source line.

    ``prepare`` drops blank lines and comment-only lines; reproduce that filter.
    """
    mapping: list[int] = []
    for number, line in enumerate(original.split("\n"), start=1):
        indent = 0
        while indent < len(line) and line[indent] == " ":
            indent += 1
        body = line[indent:]
        while body and body[-1] in " \t\r":
            body = body[:-1]
        if body and body[0] != "#":
            mapping.append(number)
    return mapping


def first_parse_failure(source: str) -> dict[str, object] | None:
    module = load_spc_module(source)
    state = {"prepared": 0}

    original_parse_statement = module.parse_statement

    def tracking_parse_statement(lines, position, indent):
        state["prepared"] = position
        return original_parse_statement(lines, position, indent)

    def raising_fail(message):
        raise ParseFailure(message, state["prepared"])

    module.parse_statement = tracking_parse_statement
    module.fail = raising_fail
    module.BAD = 0
    try:
        lines = module.prepare(strip_entrypoint(source))
        module.parse_block(lines, 0, 0)
    except ParseFailure as failure:
        mapping = prepared_line_map(strip_entrypoint(source))
        index = min(failure.prepared_line, max(len(mapping) - 1, 0))
        source_line = mapping[index] if mapping else 0
        text = source.split("\n")
        snippet = text[source_line - 1] if 0 < source_line <= len(text) else ""
        return {
            "prepared_line": failure.prepared_line,
            "source_line": source_line,
            "message": failure.message,
            "snippet": snippet,
        }
    return None


def parent_map(tree: ast.AST) -> dict[ast.AST, ast.AST]:
    parents: dict[ast.AST, ast.AST] = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[child] = parent
    return parents


def node_owner_name(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> str:
    """Return ``module``, ``func:<name>`` or ``class:<name>`` for diagnostics."""
    current = parents.get(node)
    while current is not None:
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return "func:" + current.name
        if isinstance(current, ast.ClassDef):
            return "class:" + current.name
        current = parents.get(current)
    return "module"


def classify(source: str) -> tuple[list[dict], list[dict], dict]:
    """Return (missing features, supported features, raw census)."""
    tree = ast.parse(source)
    parents = parent_map(tree)
    text = source.split("\n")
    function_names = {
        node.name for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    found: dict[str, list[dict]] = collections.defaultdict(list)

    def note(feature: str, node: ast.AST, detail: str = "") -> None:
        line = getattr(node, "lineno", 0)
        snippet = text[line - 1].strip() if 0 < line <= len(text) else ""
        found[feature].append(
            {"line": line, "detail": detail, "snippet": snippet, "owner": node_owner_name(node, parents)}
        )

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            note("def / function definition", node, node.name)
        elif isinstance(node, ast.Return):
            note("return statement", node, "with value" if node.value is not None else "bare")
        elif isinstance(node, ast.Global):
            note("global declaration", node, ",".join(node.names))
        elif isinstance(node, ast.Nonlocal):
            note("nonlocal statement", node, ",".join(node.names))
        elif isinstance(node, ast.List):
            note("list literal", node)
        elif isinstance(node, ast.Tuple):
            note("tuple literal", node)
        elif isinstance(node, ast.Dict):
            note("dict literal", node)
        elif isinstance(node, ast.Set):
            note("set literal", node)
        elif isinstance(node, ast.Attribute):
            note("attribute read", node, node.attr)
        elif isinstance(node, ast.Slice):
            note("slice expression", node)
        elif isinstance(node, ast.Subscript):
            if isinstance(node.slice, ast.Slice):
                pass
            elif isinstance(node.ctx, ast.Store):
                note("subscript assignment", node)
            else:
                note("subscript read", node)
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Attribute):
                note("method call", node, node.func.attr)
            elif isinstance(node.func, ast.Name):
                name = node.func.id
                if name in SPC_BUILTINS:
                    note("call to a known builtin", node, name)
                elif name in function_names:
                    note("call to a user-defined function", node, name)
                else:
                    note("call to an unresolved name", node, name)
            else:
                note("call to an unresolved name", node)
            if node.keywords:
                note("keyword argument", node)
            if any(isinstance(arg, ast.Starred) for arg in node.args):
                note("starred argument", node)
        elif isinstance(node, ast.Compare):
            for op in node.ops:
                if isinstance(op, (ast.In, ast.NotIn)):
                    note("membership comparison (in / not in)", node)
                elif isinstance(op, (ast.Is, ast.IsNot)):
                    note("identity comparison (is / is not)", node)
                else:
                    note("comparison", node)
        elif isinstance(node, ast.Constant):
            if node.value is None:
                note("None literal", node)
            elif isinstance(node.value, bool):
                note("bool literal", node)
            elif isinstance(node.value, float):
                note("float literal", node)
            elif isinstance(node.value, int):
                note("int literal", node)
            elif isinstance(node.value, str):
                note("string literal", node)
        elif isinstance(node, ast.For):
            iterator = node.iter
            is_range = (
                isinstance(iterator, ast.Call)
                and isinstance(iterator.func, ast.Name)
                and iterator.func.id == "range"
            )
            note("for over range()" if is_range else "for over another iterable", node)
        elif isinstance(node, ast.Break):
            note("break statement", node)
        elif isinstance(node, ast.Continue):
            note("continue statement", node)
        elif isinstance(node, ast.Pass):
            note("pass statement", node)
        elif isinstance(node, ast.AugAssign):
            note("augmented assignment", node, type(node.op).__name__)
        elif isinstance(node, ast.IfExp):
            note("conditional expression", node)
        elif isinstance(node, ast.JoinedStr):
            note("f-string", node)
        elif isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            note("comprehension", node)
        elif isinstance(node, ast.Delete):
            note("del statement", node)
        elif isinstance(node, ast.ClassDef):
            note("class definition", node, node.name)
        elif isinstance(node, ast.Try):
            note("try statement", node)
        elif isinstance(node, ast.Lambda):
            note("lambda", node)
        elif isinstance(node, ast.Match):
            note("match statement", node)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    note("assignment to a name", node, target.id)
        elif isinstance(node, ast.BinOp):
            note("arithmetic binop", node, type(node.op).__name__)
        elif isinstance(node, ast.BoolOp):
            note("boolean and / or", node, type(node.op).__name__)
        elif isinstance(node, ast.UnaryOp):
            if isinstance(node.op, ast.USub):
                note("unary minus", node)
            elif isinstance(node.op, ast.Not):
                note("not", node)
        elif isinstance(node, ast.If):
            note("if / elif / else", node)
        elif isinstance(node, ast.While):
            note("while", node)
        elif isinstance(node, ast.Expr):
            note("expression statement", node)

    # Module docstring: triple-quoted text the line tokenizer cannot read.
    if tree.body and isinstance(tree.body[0], ast.Expr) and isinstance(tree.body[0].value, ast.Constant):
        first = tree.body[0]
        if isinstance(first.value.value, str):
            note("module docstring / triple-quoted string", first)

    missing = []
    supported = []
    for feature, occurrences in found.items():
        row = {
            "feature": feature,
            "count": len(occurrences),
            "first_line": occurrences[0]["line"],
            "sample": occurrences[0]["snippet"],
            "owners": sorted({item["owner"] for item in occurrences}),
        }
        if FEATURE_SUPPORT.get(feature):
            supported.append(row)
        else:
            missing.append(row)
    missing.sort(key=lambda item: (-item["count"], item["first_line"]))
    supported.sort(key=lambda item: (-item["count"], item["feature"]))

    census = collections.Counter(type(node).__name__ for node in ast.walk(tree))
    census_rows = [{"node": name, "count": count} for name, count in sorted(census.items(), key=lambda kv: -kv[1])]
    return missing, supported, {"census": census_rows, "total_nodes": sum(census.values())}


def ast_nodes_on_line(tree: ast.AST, target: int) -> list[str]:
    names = []
    for node in ast.walk(tree):
        if getattr(node, "lineno", -1) == target:
            names.append(type(node).__name__)
    return sorted(set(names))


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def render_report(source: str, missing, supported, extra, failure) -> str:
    lines = []
    lines.append("# Bootstrap audit: native/spc.py vs. the language native/spc.py accepts")
    lines.append("")
    stat = SPC.stat()
    lines.append(f"- source: `{SPC.relative_to(ROOT)}`")
    lines.append(f"- lines: {len(source.splitlines())}, bytes: {stat.st_size}, sha256: `{sha256_of(SPC)}`")
    lines.append(f"- AST nodes: {extra['total_nodes']}")
    lines.append("")

    lines.append("## 1. First failure parsing spc.py with spc.py's own parser")
    lines.append("")
    if failure is None:
        lines.append("The current frontend parses the whole file: every statement and expression in")
        lines.append("spc.py's own source is accepted by the language spc.py implements.")
    else:
        lines.append(
            f"- source line {failure['source_line']} (prepared line {failure['prepared_line']}): "
            f"`{failure['message']}`"
        )
        lines.append(f"- line text: `{failure['snippet']}`")
        try:
            tree = ast.parse(source)
            candidates = ast_nodes_on_line(tree, failure["source_line"])
        except SyntaxError:  # pragma: no cover - source is known-good Python
            candidates = []
        lines.append(f"- AST node types on that line: {', '.join(candidates) or '(none)'}")
    lines.append("")

    lines.append("## 2. Constructs used by spc.py that the current frontend cannot accept")
    lines.append("")
    if not missing:
        lines.append("None. Every construct this file uses is in the accepted language.")
    else:
        lines.append("| # | construct | uses | first line | sample |")
        lines.append("| -: | --- | ---: | ---: | --- |")
        for index, row in enumerate(missing, start=1):
            sample = row["sample"].replace("|", "\\|")
            if len(sample) > 70:
                sample = sample[:67] + "..."
            lines.append(f"| {index} | {row['feature']} | {row['count']} | {row['first_line']} | `{sample}` |")
    lines.append("")

    lines.append("## 3. Constructs used by spc.py and accepted by the frontend")
    lines.append("")
    lines.append("| construct | uses | first line |")
    lines.append("| --- | ---: | ---: |")
    for row in supported:
        lines.append(f"| {row['feature']} | {row['count']} | {row['first_line']} |")
    lines.append("")

    lines.append("## 4. AST census (all node types)")
    lines.append("")
    lines.append("| node | count |")
    lines.append("| --- | ---: |")
    for row in extra["census"]:
        lines.append(f"| {row['node']} | {row['count']} |")
    lines.append("")

    lines.append("## 5. Next step")
    lines.append("")
    if missing:
        lines.append("Teach the frontend the constructs above, biggest gap first; each one unlocks more")
        lines.append("of the file. Then re-run this audit until section 2 is empty.")
    else:
        lines.append("Section 2 is empty, so the remaining question is code generation: compile spc.py")
        lines.append("with compiler.exe and compare the result with stage 0. `tools/bootstrap_check.py`")
        lines.append("runs the full three-stage chain and asserts the byte-identical fixed point.")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--json", type=Path, help="also write the audit as JSON to this path")
    args = parser.parse_args(argv)

    if not SPC.exists():
        print(f"bootstrap_audit: {SPC} not found", file=sys.stderr)
        return 2
    source = read_source()
    failure = first_parse_failure(source)
    missing, supported, extra = classify(source)
    report = render_report(source, missing, supported, extra, failure)
    print(report)

    if args.json:
        payload = {
            "source": str(SPC.relative_to(ROOT)),
            "lines": len(source.splitlines()),
            "bytes": SPC.stat().st_size,
            "sha256": sha256_of(SPC),
            "first_failure": failure,
            "missing": missing,
            "supported": supported,
            "census": extra["census"],
        }
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"wrote {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
