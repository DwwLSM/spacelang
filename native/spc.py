# spc.py -- a SpaceLang compiler for a small Python subset.
#
# Stage 0: the Python toolchain compiles this file into `spc.sp`
# (`spacelang compile-py native/spc.py native/spc.sp`).  Stage 1: `spc.sp` is
# embedded into `compiler.exe`, which then compiles Python source *without*
# Python:
#
#     compiler.exe program.py            # compile and run
#     compiler.exe program.py out.sp     # compile only
#
# Supported input (an indentation-based subset):
#
#     def f(a, b): return a + b        functions, return, global
#     if / elif / else                 comparisons == != < > <= >= in is
#     while / for NAME in ITER         loops with break / continue
#     x = expr / a[i] = expr           assignment
#     [1, 2] / {"a": 1}                lists, dicts, indexing, slices
#     obj.method(args)                 method calls, attributes
#     "text"                           string literals with escapes
#
# Anything else is reported on stdout as `spc: ...` and no output is written.
#
# This file is written in the same subset it accepts, so that it can compile
# itself: stage 0 (the Python toolchain) produces `spc.sp`, and from then on
# `compiler.exe` compiles `native/spc.py` without Python.  See SELFHOSTING.md.
#
# ---------------------------------------------------------------- token values
MAX_INT = 32767
MAX_STRING = 1000
# 65535 does not fit in a single SpaceLang token, so build it at runtime.
TOKEN_LIMIT = int("65535")

# Printable ASCII, index 32..126; CHAR_CODE maps a character back to its code.
ASCII = " !\"#$%&'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`abcdefghijklmnopqrstuvwxyz{|}~"

CHAR_CODE = {}
FILL = 0
while FILL < len(ASCII):
    CHAR_CODE[ASCII[FILL]] = FILL + 32
    FILL = FILL + 1

BIN_OPS = {"+": 1, "-": 2, "*": 3, "/": 4, "%": 5, "//": 16, "**": 17}
CMP_OPS = {
    "==": 6,
    "<": 7,
    ">": 8,
    "!=": 9,
    "<=": 10,
    ">=": 11,
    "in": 12,
    "not in": 13,
    "is": 14,
    "is not": 15,
}
BUILTINS = {
    "print": 0,
    "len": 2,
    "int": 3,
    "float": 4,
    "str": 5,
    "bool": 6,
    "abs": 7,
    "range": 8,
    "open": 10,
}
TWO_CHAR_OPS = ["==", "!=", "<=", ">=", "//", "**"]

# Opcode constants, for readability where an instruction is not emitted through
# one of the small helpers below.
OP_CALL = 1
OP_OP = 5
OP_STACK = 6
OP_PUSH_INT = 7
OP_PUSH_STR = 8
OP_LOAD_GLOBAL = 9
OP_STORE_GLOBAL = 10
OP_GET_ATTR = 11
OP_CALL_METHOD = 12
OP_INDEX = 13
OP_BUILD_LIST = 14
OP_DEF = 17
OP_RET = 18
OP_LOAD_LOCAL = 20
OP_STORE_LOCAL = 21
OP_JMP = 22
OP_JZ = 23
OP_JNZ = 24
OP_HALT = 29
OP_GET_ITER = 30
OP_FOR_ITER = 31
OP_STORE_INDEX = 33
OP_PUSH_NONE = 35
OP_BUILD_DICT = 44
OP_BUILD_SLICE = 52
OP_NAMES = 53

# ---------------------------------------------------------------- global state
INSTR = []
NAMES = {}
LABELS = {}
PENDING = []
NEXT_LABEL = 0
BAD = 0
FUNCS = {}
LOCALS = {}
GLOBALS = {}
FUNC_DEPTH = 0
LOOPS = []


def fail(message):
    global BAD
    BAD = 1
    print("spc: " + message)


def new_label():
    global NEXT_LABEL
    label = NEXT_LABEL
    NEXT_LABEL = NEXT_LABEL + 1
    return label


def place(label):
    LABELS[label] = len(INSTR)


def jump_to(op, label):
    PENDING.append([len(INSTR), label])
    INSTR.append([op, 0])


def patch():
    index = 0
    while index < len(PENDING):
        slot = PENDING[index]
        INSTR[slot[0]][1] = LABELS[slot[1]]
        index = index + 1


def emit0(op):
    INSTR.append([op])


def emit1(op, first):
    INSTR.append([op, first])


def emit2(op, first, second):
    INSTR.append([op, first, second])


def name_id(name):
    found = NAMES.get(name)
    if found is None:
        found = len(NAMES)
        NAMES[name] = found
    return found


# -------------------------------------------------------------------- file I/O
def read_text(path):
    handle = open(path, "r")
    text = handle.read()
    handle.close()
    return text


def write_text(path, text):
    handle = open(path, "w")
    handle.write(text)
    handle.close()


# ----------------------------------------------------------------- char codes
def char_code(character):
    if character == "\n":
        return 10
    if character == "\t":
        return 9
    if character == "\r":
        return 13
    if character in CHAR_CODE:
        return CHAR_CODE[character]
    fail("unsupported character in source: " + character)
    return 63


def is_name_start(character):
    if character == "_":
        return 1
    if character >= "a" and character <= "z":
        return 1
    if character >= "A" and character <= "Z":
        return 1
    return 0


def is_name_char(character):
    if is_name_start(character):
        return 1
    if character >= "0" and character <= "9":
        return 1
    return 0


# -------------------------------------------------------------------- tokenizer
def tokenize_line(text):
    tokens = []
    index = 0
    count = len(text)
    while index < count:
        character = text[index]
        if character == " " or character == "\t":
            index = index + 1
        elif character == "#":
            index = count
        elif character >= "0" and character <= "9":
            start = index
            while index < count and text[index] >= "0" and text[index] <= "9":
                index = index + 1
            tokens.append(["num", text[start:index]])
        elif character == "\"" or character == "'":
            quote = character
            index = index + 1
            value = ""
            while index < count and text[index] != quote:
                if text[index] == "\\" and index + 1 < count:
                    escape = text[index + 1]
                    if escape == "n":
                        value = value + "\n"
                    elif escape == "t":
                        value = value + "\t"
                    elif escape == "r":
                        value = value + "\r"
                    elif escape == "\\":
                        value = value + "\\"
                    elif escape == "\"":
                        value = value + "\""
                    elif escape == "'":
                        value = value + "'"
                    else:
                        value = value + escape
                    index = index + 2
                else:
                    value = value + text[index]
                    index = index + 1
            index = index + 1
            tokens.append(["str", value])
        elif is_name_start(character):
            start = index
            while index < count and is_name_char(text[index]):
                index = index + 1
            tokens.append(["name", text[start:index]])
        else:
            pair = ""
            if index + 1 < count:
                pair = text[index:index + 2]
            found = 0
            pairs = 0
            while pairs < len(TWO_CHAR_OPS):
                if TWO_CHAR_OPS[pairs] == pair:
                    found = 1
                pairs = pairs + 1
            if found == 1:
                tokens.append(["op", pair])
                index = index + 2
            else:
                tokens.append(["op", character])
                index = index + 1
    tokens.append(["end", ""])
    return tokens


def bracket_delta(tokens):
    delta = 0
    index = 0
    while index < len(tokens):
        if tokens[index][0] == "op":
            value = tokens[index][1]
            if value == "(" or value == "[" or value == "{":
                delta = delta + 1
            elif value == ")" or value == "]" or value == "}":
                delta = delta - 1
        index = index + 1
    return delta


def prepare(text):
    raw = text.split("\n")
    lines = []
    index = 0
    depth = 0
    pending = None
    while index < len(raw):
        line = raw[index]
        indent = 0
        while indent < len(line) and line[indent] == " ":
            indent = indent + 1
        body = line[indent:]
        while len(body) > 0:
            last = body[len(body) - 1]
            if last == " " or last == "\t" or last == "\r":
                body = body[0:len(body) - 1]
            else:
                break
        if len(body) > 0 and body[0] != "#":
            if body[0] == "\t":
                fail("tabs are not supported for indentation")
            tokens = tokenize_line(body)
            code = tokens[0:len(tokens) - 1]
            if depth == 0:
                pending = [indent, code]
            else:
                pending[1] = pending[1] + code
            depth = depth + bracket_delta(code)
            if depth <= 0:
                depth = 0
                pending[1].append(["end", ""])
                lines.append(pending)
                pending = None
        index = index + 1
    if pending is not None:
        pending[1].append(["end", ""])
        lines.append(pending)
    return lines


def tok_is(tokens, index, kind, value):
    if index >= len(tokens):
        return 0
    token = tokens[index]
    if token[0] != kind:
        return 0
    if value != "" and token[1] != value:
        return 0
    return 1


# ----------------------------------------------------------------------- parser
def parse_or(tokens, index):
    pair = parse_and(tokens, index)
    node = pair[0]
    index = pair[1]
    while tok_is(tokens, index, "name", "or"):
        pair = parse_and(tokens, index + 1)
        node = {"k": "or", "l": node, "r": pair[0]}
        index = pair[1]
    return [node, index]


def parse_and(tokens, index):
    pair = parse_not(tokens, index)
    node = pair[0]
    index = pair[1]
    while tok_is(tokens, index, "name", "and"):
        pair = parse_not(tokens, index + 1)
        node = {"k": "and", "l": node, "r": pair[0]}
        index = pair[1]
    return [node, index]


def parse_not(tokens, index):
    if tok_is(tokens, index, "name", "not"):
        pair = parse_not(tokens, index + 1)
        return [{"k": "not", "v": pair[0]}, pair[1]]
    return parse_comparison(tokens, index)


def compare_op(tokens, index):
    if index < len(tokens) and tokens[index][0] == "op":
        operator = tokens[index][1]
        if operator in CMP_OPS:
            return [operator, index + 1]
    if tok_is(tokens, index, "name", "in"):
        return ["in", index + 1]
    if tok_is(tokens, index, "name", "is"):
        if tok_is(tokens, index + 1, "name", "not"):
            return ["is not", index + 2]
        return ["is", index + 1]
    if tok_is(tokens, index, "name", "not") and tok_is(tokens, index + 1, "name", "in"):
        return ["not in", index + 2]
    return ["", index]


def parse_comparison(tokens, index):
    pair = parse_additive(tokens, index)
    left = pair[0]
    index = pair[1]
    while 1:
        op_pair = compare_op(tokens, index)
        operator = op_pair[0]
        if operator == "":
            break
        pair = parse_additive(tokens, op_pair[1])
        left = {"k": "cmp", "op": operator, "l": left, "r": pair[0]}
        index = pair[1]
    return [left, index]


def parse_additive(tokens, index):
    pair = parse_term(tokens, index)
    left = pair[0]
    index = pair[1]
    while index < len(tokens) and tokens[index][0] == "op":
        operator = tokens[index][1]
        if operator != "+" and operator != "-":
            break
        pair = parse_term(tokens, index + 1)
        left = {"k": "bin", "op": operator, "l": left, "r": pair[0]}
        index = pair[1]
    return [left, index]


def parse_term(tokens, index):
    pair = parse_unary(tokens, index)
    left = pair[0]
    index = pair[1]
    while index < len(tokens) and tokens[index][0] == "op":
        operator = tokens[index][1]
        if operator != "*" and operator != "/" and operator != "%" and operator != "//" and operator != "**":
            break
        pair = parse_unary(tokens, index + 1)
        left = {"k": "bin", "op": operator, "l": left, "r": pair[0]}
        index = pair[1]
    return [left, index]


def parse_unary(tokens, index):
    if tok_is(tokens, index, "op", "-"):
        pair = parse_unary(tokens, index + 1)
        return [{"k": "unary", "v": pair[0]}, pair[1]]
    pair = parse_atom(tokens, index)
    return parse_postfix(pair[0], tokens, pair[1])


def parse_atom(tokens, index):
    if index >= len(tokens):
        fail("unexpected end of line")
        return [{"k": "num", "v": 0}, index]
    token = tokens[index]
    if token[0] == "num":
        return [{"k": "num", "v": int(token[1])}, index + 1]
    if token[0] == "str":
        return [{"k": "str", "v": token[1]}, index + 1]
    if token[0] == "name":
        if token[1] == "None":
            return [{"k": "none"}, index + 1]
        if token[1] == "True":
            return [{"k": "bool", "v": 1}, index + 1]
        if token[1] == "False":
            return [{"k": "bool", "v": 0}, index + 1]
        return [{"k": "name", "v": token[1]}, index + 1]
    if token[0] == "op" and token[1] == "(":
        pair = parse_expr(tokens, index + 1)
        if not tok_is(tokens, pair[1], "op", ")"):
            fail("expected ')'")
        return [pair[0], pair[1] + 1]
    if token[0] == "op" and token[1] == "[":
        return parse_list_literal(tokens, index + 1)
    if token[0] == "op" and token[1] == "{":
        return parse_dict_literal(tokens, index + 1)
    fail("unexpected token: " + token[1])
    return [{"k": "num", "v": 0}, index + 1]


def parse_list_literal(tokens, index):
    items = []
    if not tok_is(tokens, index, "op", "]"):
        while 1:
            pair = parse_expr(tokens, index)
            items.append(pair[0])
            index = pair[1]
            if tok_is(tokens, index, "op", ","):
                index = index + 1
                if tok_is(tokens, index, "op", "]"):
                    break
                continue
            break
    if not tok_is(tokens, index, "op", "]"):
        fail("expected ']' after list elements")
    return [{"k": "list", "items": items}, index + 1]


def parse_dict_literal(tokens, index):
    items = []
    if not tok_is(tokens, index, "op", "}"):
        while 1:
            pair = parse_expr(tokens, index)
            key = pair[0]
            index = pair[1]
            if not tok_is(tokens, index, "op", ":"):
                fail("expected ':' after a dictionary key")
            pair = parse_expr(tokens, index + 1)
            items.append([key, pair[0]])
            index = pair[1]
            if tok_is(tokens, index, "op", ","):
                index = index + 1
                if tok_is(tokens, index, "op", "}"):
                    break
                continue
            break
    if not tok_is(tokens, index, "op", "}"):
        fail("expected '}' after dictionary entries")
    return [{"k": "dict", "items": items}, index + 1]


def parse_subscript(tokens, index):
    lower = None
    if not tok_is(tokens, index, "op", ":"):
        pair = parse_expr(tokens, index)
        lower = pair[0]
        index = pair[1]
    if tok_is(tokens, index, "op", ":"):
        index = index + 1
        upper = None
        if not tok_is(tokens, index, "op", "]") and not tok_is(tokens, index, "op", ":"):
            pair = parse_expr(tokens, index)
            upper = pair[0]
            index = pair[1]
        return [{"k": "slice", "lower": lower, "upper": upper}, index]
    return [lower, index]


def parse_postfix(node, tokens, index):
    while 1:
        if index >= len(tokens):
            break
        token = tokens[index]
        if token[0] == "op" and token[1] == "(":
            args = []
            position = index + 1
            if not tok_is(tokens, position, "op", ")"):
                while 1:
                    pair2 = parse_expr(tokens, position)
                    args.append(pair2[0])
                    position = pair2[1]
                    if tok_is(tokens, position, "op", ","):
                        position = position + 1
                        if tok_is(tokens, position, "op", ")"):
                            break
                        continue
                    break
            if not tok_is(tokens, position, "op", ")"):
                fail("expected ')' after arguments")
                break
            kind = node["k"]
            if kind == "name":
                node = {"k": "call", "fn": node["v"], "args": args}
            elif kind == "attr":
                node = {"k": "method", "obj": node["obj"], "name": node["name"], "args": args}
            else:
                fail("unsupported call target")
            index = position + 1
        elif token[0] == "op" and token[1] == ".":
            if index + 1 >= len(tokens) or tokens[index + 1][0] != "name":
                fail("expected a name after '.'")
                break
            node = {"k": "attr", "obj": node, "name": tokens[index + 1][1]}
            index = index + 2
        elif token[0] == "op" and token[1] == "[":
            pair2 = parse_subscript(tokens, index + 1)
            if not tok_is(tokens, pair2[1], "op", "]"):
                fail("expected ']' after the index")
                break
            node = {"k": "index", "obj": node, "index": pair2[0]}
            index = pair2[1] + 1
        else:
            break
    return [node, index]


def parse_expr(tokens, index):
    return parse_or(tokens, index)


# -------------------------------------------------------------------- statements
def parse_block(lines, position, indent):
    statements = []
    while position < len(lines) and lines[position][0] >= indent:
        if lines[position][0] > indent:
            fail("unexpected indentation")
            position = position + 1
            continue
        pair = parse_statement(lines, position, indent)
        statements.append(pair[0])
        position = pair[1]
    return [statements, position]


def parse_block_at(lines, position, parent_indent):
    if position >= len(lines) or lines[position][0] <= parent_indent:
        fail("expected an indented block")
        return [[], position]
    return parse_block(lines, position, lines[position][0])


def expect_colon(tokens, index):
    if not tok_is(tokens, index, "op", ":"):
        fail("expected ':' at the end of the line")
        return index
    return index + 1


def expect_end(tokens, index):
    if index >= len(tokens):
        fail("unexpected end of statement")
        return index
    if not tok_is(tokens, index, "end", ""):
        fail("unexpected trailing input: " + tokens[index][1])
    return index


def parse_if(lines, position, indent):
    tokens = lines[position][1]
    pair = parse_expr(tokens, 1)
    test = pair[0]
    expect_end(tokens, expect_colon(tokens, pair[1]))
    body_pair = parse_block_at(lines, position + 1, indent)
    body = body_pair[0]
    position = body_pair[1]
    orelse = []
    if position < len(lines) and lines[position][0] == indent:
        head = lines[position][1][0]
        if head[0] == "name" and head[1] == "else":
            else_pair = parse_block_at(lines, position + 1, indent)
            orelse = else_pair[0]
            position = else_pair[1]
        elif head[0] == "name" and head[1] == "elif":
            lines[position][1][0] = ["name", "if"]
            nested = parse_if(lines, position, indent)
            orelse = [nested[0]]
            position = nested[1]
    return [{"k": "if", "test": test, "body": body, "orelse": orelse}, position]


def parse_while(lines, position, indent):
    tokens = lines[position][1]
    pair = parse_expr(tokens, 1)
    test = pair[0]
    expect_end(tokens, expect_colon(tokens, pair[1]))
    body_pair = parse_block_at(lines, position + 1, indent)
    return [{"k": "while", "test": test, "body": body_pair[0]}, body_pair[1]]


def parse_for(lines, position, indent):
    tokens = lines[position][1]
    if not tok_is(tokens, 1, "name", ""):
        fail("expected a loop variable after 'for'")
        return [{"k": "expr", "value": {"k": "num", "v": 0}}, position + 1]
    target = tokens[1][1]
    if not tok_is(tokens, 2, "name", "in"):
        fail("expected 'in' after the loop variable")
        return [{"k": "expr", "value": {"k": "num", "v": 0}}, position + 1]
    pair = parse_expr(tokens, 3)
    expect_end(tokens, expect_colon(tokens, pair[1]))
    body_pair = parse_block_at(lines, position + 1, indent)
    return [{"k": "for", "target": target, "iter": pair[0], "body": body_pair[0]}, body_pair[1]]


def parse_def(lines, position, indent):
    if FUNC_DEPTH > 0:
        fail("nested functions are not supported")
    tokens = lines[position][1]
    name = ""
    if tok_is(tokens, 1, "name", ""):
        name = tokens[1][1]
    else:
        fail("expected a function name after 'def'")
    if not tok_is(tokens, 2, "op", "("):
        fail("expected '(' after the function name")
        return [{"k": "def", "name": name, "params": [], "body": []}, position + 1]
    params = []
    index = 3
    if not tok_is(tokens, index, "op", ")"):
        while 1:
            if not tok_is(tokens, index, "name", ""):
                fail("expected a parameter name")
                break
            params.append(tokens[index][1])
            index = index + 1
            if tok_is(tokens, index, "op", ","):
                index = index + 1
                if tok_is(tokens, index, "op", ")"):
                    break
                continue
            break
    if not tok_is(tokens, index, "op", ")"):
        fail("expected ')' after the parameters")
    expect_end(tokens, expect_colon(tokens, index + 1))
    body_pair = parse_block_at(lines, position + 1, indent)
    return [{"k": "def", "name": name, "params": params, "body": body_pair[0]}, body_pair[1]]


def parse_return(lines, position):
    tokens = lines[position][1]
    if tok_is(tokens, 1, "end", ""):
        return [{"k": "return", "value": None}, position + 1]
    pair = parse_expr(tokens, 1)
    expect_end(tokens, pair[1])
    return [{"k": "return", "value": pair[0]}, position + 1]


def parse_global(lines, position):
    tokens = lines[position][1]
    names = []
    index = 1
    while 1:
        if not tok_is(tokens, index, "name", ""):
            fail("expected a name after 'global'")
            break
        names.append(tokens[index][1])
        index = index + 1
        if tok_is(tokens, index, "op", ","):
            index = index + 1
            continue
        break
    expect_end(tokens, index)
    return [{"k": "global", "names": names}, position + 1]


def parse_statement(lines, position, indent):
    tokens = lines[position][1]
    head = tokens[0]
    if head[0] == "name" and head[1] == "if":
        return parse_if(lines, position, indent)
    if head[0] == "name" and head[1] == "while":
        return parse_while(lines, position, indent)
    if head[0] == "name" and head[1] == "for":
        return parse_for(lines, position, indent)
    if head[0] == "name" and head[1] == "def":
        return parse_def(lines, position, indent)
    if head[0] == "name" and head[1] == "return":
        return parse_return(lines, position)
    if head[0] == "name" and head[1] == "global":
        return parse_global(lines, position)
    if head[0] == "name" and head[1] == "break":
        expect_end(tokens, 1)
        return [{"k": "break"}, position + 1]
    if head[0] == "name" and head[1] == "continue":
        expect_end(tokens, 1)
        return [{"k": "continue"}, position + 1]
    if head[0] == "name" and head[1] == "pass":
        expect_end(tokens, 1)
        return [{"k": "pass"}, position + 1]
    if head[0] == "name" and head[1] == "else":
        fail("'else' without a matching 'if'")
        return [{"k": "expr", "value": {"k": "num", "v": 0}}, position + 1]
    if head[0] == "name" and head[1] == "elif":
        fail("'elif' without a matching 'if'")
        return [{"k": "expr", "value": {"k": "num", "v": 0}}, position + 1]
    pair = parse_expr(tokens, 0)
    if tok_is(tokens, pair[1], "op", "="):
        value_pair = parse_expr(tokens, pair[1] + 1)
        expect_end(tokens, value_pair[1])
        return [{"k": "assign", "target": pair[0], "value": value_pair[0]}, position + 1]
    expect_end(tokens, pair[1])
    return [{"k": "expr", "value": pair[0]}, position + 1]


# -------------------------------------------------------------- scope analysis
def append_name(names, name):
    index = 0
    while index < len(names):
        if names[index] == name:
            return
        index = index + 1
    names.append(name)


def note_target(target, names):
    if target["k"] == "name":
        append_name(names, target["v"])


def collect_function_names(statements, names, global_names):
    index = 0
    while index < len(statements):
        statement = statements[index]
        kind = statement["k"]
        if kind == "assign":
            note_target(statement["target"], names)
        elif kind == "for":
            append_name(names, statement["target"])
            collect_function_names(statement["body"], names, global_names)
        elif kind == "if":
            collect_function_names(statement["body"], names, global_names)
            collect_function_names(statement["orelse"], names, global_names)
        elif kind == "while":
            collect_function_names(statement["body"], names, global_names)
        elif kind == "global":
            global_names[statement["names"][0]] = 1
            name_index = 1
            while name_index < len(statement["names"]):
                global_names[statement["names"][name_index]] = 1
                name_index = name_index + 1
        index = index + 1


def function_scope(params, body):
    names = []
    global_names = {}
    collect_function_names(body, names, global_names)
    slots = {}
    index = 0
    while index < len(params):
        slots[params[index]] = index
        index = index + 1
    index = 0
    while index < len(names):
        name = names[index]
        if name not in global_names and name not in slots:
            slots[name] = len(slots)
        index = index + 1
    return [slots, global_names]


def collect_functions(statements):
    index = 0
    count = 0
    while index < len(statements):
        statement = statements[index]
        if statement["k"] == "def":
            FUNCS[statement["name"]] = 10000 + count
            count = count + 1
        index = index + 1


# ----------------------------------------------------------------- code emitter
def load_name(name):
    if FUNC_DEPTH > 0 and name not in GLOBALS and name in LOCALS:
        emit1(OP_LOAD_LOCAL, LOCALS[name])
        return
    emit1(OP_LOAD_GLOBAL, name_id(name))


def store_name(name):
    if FUNC_DEPTH > 0 and name not in GLOBALS and name in LOCALS:
        emit1(OP_STORE_LOCAL, LOCALS[name])
        return
    emit1(OP_STORE_GLOBAL, name_id(name))


def gen_subscript_index(index_node):
    if index_node["k"] != "slice":
        gen_expr(index_node)
        return
    if index_node["lower"] is None:
        emit0(OP_PUSH_NONE)
    else:
        gen_expr(index_node["lower"])
    if index_node["upper"] is None:
        emit0(OP_PUSH_NONE)
    else:
        gen_expr(index_node["upper"])
    emit0(OP_PUSH_NONE)
    emit0(OP_BUILD_SLICE)


def gen_expr(node):
    kind = node["k"]
    if kind == "num":
        value = node["v"]
        if value > MAX_INT or value < -MAX_INT:
            fail("integer literal out of range: " + str(value))
            value = 0
        emit1(OP_PUSH_INT, value)
        return
    if kind == "bool":
        emit1(OP_PUSH_INT, node["v"])
        emit2(OP_CALL, BUILTINS["bool"], 1)
        return
    if kind == "none":
        emit0(OP_PUSH_NONE)
        return
    if kind == "str":
        text = node["v"]
        if len(text) > MAX_STRING:
            fail("string literal too long")
            text = ""
        instruction = [OP_PUSH_STR, len(text)]
        index = 0
        while index < len(text):
            instruction.append(char_code(text[index]))
            index = index + 1
        INSTR.append(instruction)
        return
    if kind == "name":
        load_name(node["v"])
        return
    if kind == "bin":
        gen_expr(node["l"])
        gen_expr(node["r"])
        emit1(OP_OP, BIN_OPS[node["op"]])
        return
    if kind == "cmp":
        gen_expr(node["l"])
        gen_expr(node["r"])
        emit1(OP_OP, CMP_OPS[node["op"]])
        return
    if kind == "unary":
        gen_expr(node["v"])
        emit1(OP_PUSH_INT, -1)
        emit1(OP_OP, 3)
        return
    if kind == "not":
        gen_expr(node["v"])
        true_label = new_label()
        end_label = new_label()
        jump_to(OP_JZ, true_label)
        emit1(OP_PUSH_INT, 0)
        jump_to(OP_JMP, end_label)
        place(true_label)
        emit1(OP_PUSH_INT, 1)
        place(end_label)
        emit2(OP_CALL, BUILTINS["bool"], 1)
        return
    if kind == "and":
        gen_expr(node["l"])
        end_label = new_label()
        emit1(OP_STACK, 1)
        jump_to(OP_JZ, end_label)
        emit1(OP_STACK, 3)
        gen_expr(node["r"])
        place(end_label)
        return
    if kind == "or":
        gen_expr(node["l"])
        end_label = new_label()
        emit1(OP_STACK, 1)
        jump_to(OP_JNZ, end_label)
        emit1(OP_STACK, 3)
        gen_expr(node["r"])
        place(end_label)
        return
    if kind == "call":
        name = node["fn"]
        arguments = node["args"]
        index = 0
        if name in FUNCS:
            while index < len(arguments):
                gen_expr(arguments[index])
                index = index + 1
            emit2(OP_CALL, FUNCS[name], len(arguments))
            return
        builtin = BUILTINS.get(name)
        if builtin is None:
            fail("unknown function: " + name)
            return
        while index < len(arguments):
            gen_expr(arguments[index])
            index = index + 1
        emit2(OP_CALL, builtin, len(arguments))
        return
    if kind == "method":
        gen_expr(node["obj"])
        arguments = node["args"]
        index = 0
        while index < len(arguments):
            gen_expr(arguments[index])
            index = index + 1
        emit2(OP_CALL_METHOD, name_id(node["name"]), len(arguments))
        return
    if kind == "attr":
        gen_expr(node["obj"])
        emit1(OP_GET_ATTR, name_id(node["name"]))
        return
    if kind == "index":
        gen_expr(node["obj"])
        gen_subscript_index(node["index"])
        emit1(OP_INDEX, 0)
        return
    if kind == "list":
        items = node["items"]
        index = 0
        while index < len(items):
            gen_expr(items[index])
            index = index + 1
        emit1(OP_BUILD_LIST, len(items))
        return
    if kind == "dict":
        items = node["items"]
        index = 0
        while index < len(items):
            gen_expr(items[index][0])
            gen_expr(items[index][1])
            index = index + 1
        emit1(OP_BUILD_DICT, len(items))
        return
    fail("unsupported expression")


def gen_store_target(target):
    kind = target["k"]
    if kind == "name":
        store_name(target["v"])
        return
    if kind == "index":
        gen_expr(target["obj"])
        gen_subscript_index(target["index"])
        emit0(OP_STORE_INDEX)
        return
    fail("unsupported assignment target")


def loop_label(kind):
    loop = LOOPS[len(LOOPS) - 1]
    if kind == 0:
        return loop[0]
    return loop[1]


def is_for_loop():
    loop = LOOPS[len(LOOPS) - 1]
    return loop[2]


def gen_stmt(node):
    kind = node["k"]
    if kind == "assign":
        gen_expr(node["value"])
        gen_store_target(node["target"])
        return
    if kind == "expr":
        gen_expr(node["value"])
        emit1(OP_STACK, 3)
        return
    if kind == "if":
        gen_expr(node["test"])
        else_label = new_label()
        end_label = new_label()
        jump_to(OP_JZ, else_label)
        gen_block(node["body"])
        if len(node["orelse"]) > 0:
            jump_to(OP_JMP, end_label)
            place(else_label)
            gen_block(node["orelse"])
            place(end_label)
        else:
            place(else_label)
        return
    if kind == "while":
        loop_label_new = new_label()
        end_label = new_label()
        place(loop_label_new)
        gen_expr(node["test"])
        jump_to(OP_JZ, end_label)
        LOOPS.append([loop_label_new, end_label, 0])
        gen_block(node["body"])
        LOOPS.pop()
        jump_to(OP_JMP, loop_label_new)
        place(end_label)
        return
    if kind == "for":
        gen_expr(node["iter"])
        emit0(OP_GET_ITER)
        loop_label_new = new_label()
        end_label = new_label()
        place(loop_label_new)
        jump_to(OP_FOR_ITER, end_label)
        store_name(node["target"])
        LOOPS.append([loop_label_new, end_label, 1])
        gen_block(node["body"])
        LOOPS.pop()
        jump_to(OP_JMP, loop_label_new)
        place(end_label)
        return
    if kind == "return":
        if node["value"] is None:
            emit1(OP_PUSH_INT, 0)
        else:
            gen_expr(node["value"])
        emit0(OP_RET)
        return
    if kind == "break":
        if len(LOOPS) == 0:
            fail("'break' outside a loop")
            return
        if is_for_loop():
            emit1(OP_STACK, 3)
        jump_to(OP_JMP, loop_label(1))
        return
    if kind == "continue":
        if len(LOOPS) == 0:
            fail("'continue' outside a loop")
            return
        jump_to(OP_JMP, loop_label(0))
        return
    if kind == "global":
        return
    if kind == "pass":
        return
    fail("unsupported statement")


def gen_def(node):
    global LOCALS, GLOBALS, FUNC_DEPTH, LOOPS
    func_id = FUNCS[node["name"]]
    emit2(OP_DEF, func_id, len(node["params"]))
    saved_locals = LOCALS
    saved_globals = GLOBALS
    saved_depth = FUNC_DEPTH
    saved_loops = LOOPS
    pair = function_scope(node["params"], node["body"])
    LOCALS = pair[0]
    GLOBALS = pair[1]
    FUNC_DEPTH = saved_depth + 1
    LOOPS = []
    gen_block(node["body"])
    emit1(OP_PUSH_INT, 0)
    emit0(OP_RET)
    LOCALS = saved_locals
    GLOBALS = saved_globals
    FUNC_DEPTH = saved_depth
    LOOPS = saved_loops


def gen_block(statements):
    index = 0
    while index < len(statements):
        statement = statements[index]
        if statement["k"] == "def":
            gen_def(statement)
        else:
            gen_stmt(statement)
        index = index + 1


# -------------------------------------------------------------------- encoding
def token(value):
    if value < 0 or value > TOKEN_LIMIT:
        fail("token value out of range: " + str(value))
        return ""
    return " " * value + "\n"


def zigzag(value):
    if value >= 0:
        return value * 2
    return -value * 2 - 1


def encode():
    parts = []
    index = 0
    while index < len(INSTR):
        instruction = INSTR[index]
        op = instruction[0]
        parts.append(token(op))
        slot = 1
        while slot < len(instruction):
            value = instruction[slot]
            if op == OP_PUSH_INT and slot == 1:
                parts.append(token(zigzag(value)))
            else:
                parts.append(token(value))
            slot = slot + 1
        index = index + 1
    payload_parts = ["{"]
    first = 1
    for name in NAMES:
        if first == 0:
            payload_parts.append(",")
        first = 0
        payload_parts.append("\"" + name + "\":" + str(NAMES[name]))
    payload_parts.append("}")
    payload = "".join(payload_parts)
    parts.append(token(OP_NAMES))
    parts.append(token(len(payload)))
    index = 0
    while index < len(payload):
        parts.append(token(char_code(payload[index])))
        index = index + 1
    return "".join(parts)


def main():
    argv = __argv__
    if len(argv) < 2:
        print("spc: usage: spc SOURCE.py [OUTPUT.sp]")
        return 1
    source = argv[1]
    output = "spc_out.sp"
    if len(argv) > 2:
        output = argv[2]
    lines = prepare(read_text(source))
    pair = parse_block(lines, 0, 0)
    if BAD != 0:
        return 1
    collect_functions(pair[0])
    gen_block(pair[0])
    emit0(OP_HALT)
    patch()
    if BAD != 0:
        return 1
    write_text(output, encode())
    return 0


main()
