"""spc.py -- a SpaceLang compiler for a small Python subset.

Stage 0: the Python toolchain compiles this file into `spc.sp`
(`spacelang compile-py native/spc.py native/spc.sp`).  Stage 1: `spc.sp` is
embedded into `compiler.exe`, which then compiles Python source *without
Python*:

    compiler.exe program.py            # compile and run
    compiler.exe program.py out.sp     # compile only

Supported input (an indentation-based subset):

    x = 2 + 3 * 4            assignment, arithmetic + - * / // % **
    print(a, b)              print/len/str/int/float/bool/abs/range calls
    if / elif / else         comparisons == != < > <= >=, and/or/not
    while                    loops
    for i in range(n)        and range(start, stop)
    "text"                   string literals (ASCII, escapes \\n \\t \\\\)

Anything else is reported on stdout as `spc: ...` and no output is written.
"""

# ---------------------------------------------------------------- token values
MAX_INT = 32767
MAX_STRING = 1000
# 65535 does not fit in a single SpaceLang token, so build it at runtime
# (writing the literal is itself a compile error -- the encoder's MAX_LINE trap).
TOKEN_LIMIT = int("65535")

# Printable ASCII, index 32..126; CHAR_CODE maps a character back to its code.
ASCII = " !\"#$%&'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`abcdefghijklmnopqrstuvwxyz{|}~"

CHAR_CODE = {}
FILL = 0
while FILL < len(ASCII):
    CHAR_CODE[ASCII[FILL]] = FILL + 32
    FILL = FILL + 1

BIN_OPS = {"+": 1, "-": 2, "*": 3, "/": 4, "%": 5, "//": 16, "**": 17}
CMP_OPS = {"==": 6, "<": 7, ">": 8, "!=": 9, "<=": 10, ">=": 11}
BUILTINS = {
    "print": 0,
    "len": 2,
    "int": 3,
    "float": 4,
    "str": 5,
    "bool": 6,
    "abs": 7,
    "range": 8,
}
TWO_CHAR_OPS = ("==", "!=", "<=", ">=", "//", "**")

# ---------------------------------------------------------------- global state
INSTR = []
NAMES = {}
LABELS = {}
PENDING = []
NEXT_LABEL = 0
BAD = 0


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


def prepare(text):
    raw = text.split("\n")
    lines = []
    index = 0
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
            lines.append([indent, tokenize_line(body)])
        index = index + 1
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


def parse_comparison(tokens, index):
    pair = parse_additive(tokens, index)
    left = pair[0]
    index = pair[1]
    while index < len(tokens) and tokens[index][0] == "op":
        operator = tokens[index][1]
        if operator not in CMP_OPS:
            break
        pair = parse_additive(tokens, index + 1)
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
    return parse_primary(tokens, index)


def parse_primary(tokens, index):
    if index >= len(tokens):
        fail("unexpected end of line")
        return [{"k": "num", "v": 0}, index]
    token = tokens[index]
    if token[0] == "num":
        return [{"k": "num", "v": int(token[1])}, index + 1]
    if token[0] == "str":
        return [{"k": "str", "v": token[1]}, index + 1]
    if token[0] == "name":
        if tok_is(tokens, index + 1, "op", "("):
            name = token[1]
            arguments = []
            position = index + 2
            if not tok_is(tokens, position, "op", ")"):
                while 1:
                    pair = parse_expr(tokens, position)
                    arguments.append(pair[0])
                    position = pair[1]
                    if tok_is(tokens, position, "op", ","):
                        position = position + 1
                        continue
                    break
            if not tok_is(tokens, position, "op", ")"):
                fail("expected ')' after arguments")
            return [{"k": "call", "fn": name, "args": arguments}, position + 1]
        return [{"k": "name", "v": token[1]}, index + 1]
    if token[0] == "op" and token[1] == "(":
        pair = parse_expr(tokens, index + 1)
        if not tok_is(tokens, pair[1], "op", ")"):
            fail("expected ')'")
        return [pair[0], pair[1] + 1]
    fail("unexpected token: " + token[1])
    return [{"k": "num", "v": 0}, index + 1]


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
    target = tokens[1][1]
    if not tok_is(tokens, 2, "name", "in"):
        fail("expected 'in' after the loop variable")
    if not tok_is(tokens, 3, "name", "range"):
        fail("only 'for NAME in range(...)' loops are supported")
    if not tok_is(tokens, 4, "op", "("):
        fail("expected '(' after range")
    pair = parse_expr(tokens, 5)
    first = pair[0]
    index = pair[1]
    second = None
    if tok_is(tokens, index, "op", ","):
        pair = parse_expr(tokens, index + 1)
        second = pair[0]
        index = pair[1]
    if not tok_is(tokens, index, "op", ")"):
        fail("expected ')' after range arguments")
    expect_end(tokens, expect_colon(tokens, index + 1))
    body_pair = parse_block_at(lines, position + 1, indent)
    return [
        {"k": "for", "name": target, "first": first, "second": second, "body": body_pair[0]},
        body_pair[1],
    ]


def parse_statement(lines, position, indent):
    tokens = lines[position][1]
    head = tokens[0]
    if head[0] == "name" and head[1] == "if":
        return parse_if(lines, position, indent)
    if head[0] == "name" and head[1] == "while":
        return parse_while(lines, position, indent)
    if head[0] == "name" and head[1] == "for":
        return parse_for(lines, position, indent)
    if head[0] == "name" and head[1] == "else":
        fail("'else' without a matching 'if'")
        return [{"k": "expr", "value": {"k": "num", "v": 0}}, position + 1]
    if head[0] == "name" and tok_is(tokens, 1, "op", "="):
        pair = parse_expr(tokens, 2)
        expect_end(tokens, pair[1])
        return [{"k": "assign", "name": head[1], "value": pair[0]}, position + 1]
    pair = parse_expr(tokens, 0)
    expect_end(tokens, pair[1])
    return [{"k": "expr", "value": pair[0]}, position + 1]


# ----------------------------------------------------------------- code emitter
def gen_expr(node):
    kind = node["k"]
    if kind == "num":
        value = node["v"]
        if value > MAX_INT or value < -MAX_INT:
            fail("integer literal out of range: " + str(value))
            value = 0
        emit1(7, value)
        return
    if kind == "str":
        text = node["v"]
        if len(text) > MAX_STRING:
            fail("string literal too long")
            text = ""
        instruction = [8, len(text)]
        index = 0
        while index < len(text):
            instruction.append(char_code(text[index]))
            index = index + 1
        INSTR.append(instruction)
        return
    if kind == "name":
        emit1(9, name_id(node["v"]))
        return
    if kind == "bin":
        gen_expr(node["l"])
        gen_expr(node["r"])
        emit1(5, BIN_OPS[node["op"]])
        return
    if kind == "cmp":
        gen_expr(node["l"])
        gen_expr(node["r"])
        emit1(5, CMP_OPS[node["op"]])
        return
    if kind == "call":
        name = node["fn"]
        builtin = BUILTINS.get(name)
        if builtin is None:
            fail("unknown function: " + name)
            emit1(7, 0)
            return
        arguments = node["args"]
        index = 0
        while index < len(arguments):
            gen_expr(arguments[index])
            index = index + 1
        emit2(1, builtin, len(arguments))
        return
    if kind == "unary":
        gen_expr(node["v"])
        emit1(7, -1)
        emit1(5, 3)
        return
    if kind == "not":
        gen_expr(node["v"])
        true_label = new_label()
        end_label = new_label()
        jump_to(23, true_label)
        emit1(7, 0)
        jump_to(22, end_label)
        place(true_label)
        emit1(7, 1)
        place(end_label)
        emit2(1, 6, 1)
        return
    if kind == "and" or kind == "or":
        gen_expr(node["l"])
        emit1(6, 1)
        end_label = new_label()
        if kind == "and":
            jump_to(23, end_label)
        else:
            jump_to(24, end_label)
        emit1(6, 3)
        gen_expr(node["r"])
        place(end_label)
        return
    fail("unsupported expression")
    emit1(7, 0)


def gen_stmt(node):
    kind = node["k"]
    if kind == "assign":
        gen_expr(node["value"])
        emit1(10, name_id(node["name"]))
        return
    if kind == "expr":
        gen_expr(node["value"])
        emit1(6, 3)
        return
    if kind == "if":
        gen_expr(node["test"])
        else_label = new_label()
        end_label = new_label()
        jump_to(23, else_label)
        gen_block(node["body"])
        if len(node["orelse"]) > 0:
            jump_to(22, end_label)
            place(else_label)
            gen_block(node["orelse"])
            place(end_label)
        else:
            place(else_label)
        return
    if kind == "while":
        loop_label = new_label()
        end_label = new_label()
        place(loop_label)
        gen_expr(node["test"])
        jump_to(23, end_label)
        gen_block(node["body"])
        jump_to(22, loop_label)
        place(end_label)
        return
    if kind == "for":
        if node["second"] is None:
            gen_expr(node["first"])
            emit2(1, 8, 1)
        else:
            gen_expr(node["first"])
            gen_expr(node["second"])
            emit2(1, 8, 2)
        emit0(30)
        loop_label = new_label()
        end_label = new_label()
        place(loop_label)
        jump_to(31, end_label)
        emit1(10, name_id(node["name"]))
        gen_block(node["body"])
        jump_to(22, loop_label)
        place(end_label)
        return
    fail("unsupported statement")


def gen_block(statements):
    index = 0
    while index < len(statements):
        gen_stmt(statements[index])
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
    out = ""
    index = 0
    while index < len(INSTR):
        instruction = INSTR[index]
        op = instruction[0]
        out = out + token(op)
        slot = 1
        while slot < len(instruction):
            value = instruction[slot]
            if op == 7 and slot == 1:
                out = out + token(zigzag(value))
            else:
                out = out + token(value)
            slot = slot + 1
        index = index + 1
    payload = "{"
    first = 1
    for name in NAMES:
        if first == 0:
            payload = payload + ","
        first = 0
        payload = payload + "\"" + name + "\":" + str(NAMES[name])
    payload = payload + "}"
    out = out + token(53) + token(len(payload))
    index = 0
    while index < len(payload):
        out = out + token(char_code(payload[index]))
        index = index + 1
    return out


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
    gen_block(pair[0])
    emit0(29)
    patch()
    if BAD != 0:
        return 1
    write_text(output, encode())
    return 0


main()
