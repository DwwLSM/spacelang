"""A SpaceLang virtual machine written in the SpaceLang Python subset.

`spacelang compile-py bootstrap/sp_vm.py bootstrap/sp_vm.sp` turns this file
into a SpaceLang program that can load and execute other `.sp` programs --
including a compiled copy of itself.  See bootstrap/README.md.
"""

import math
import os
import random
import re
import sys

# --- value tags -------------------------------------------------------------
# type() results are cached so runtime type tests cost a lookup, not a call.
T_LIST = type([])
T_TUPLE = type(())
T_STR = type("")
T_DICT = type({})
T_RANGE = type(range(0))
T_INT = type(0)
T_FLOAT = type(0.0)
T_SET = type(set())

# Cells, closures and slices are list records.  Slot 0 holds a unique marker
# object, so `record[0] is MARK` cannot collide with any program value.
CELL_MARK = ["cell"]
CLOSURE_MARK = ["closure"]
SLICE_MARK = ["slice"]

C_TAG = 0
C_VALUE = 1
C_READY = 2

K_TAG = 0
K_FUNC = 1
K_CELLS = 2
K_PARAMS = 3
K_DEFAULTS = 4
K_POSCOUNT = 5
K_VARARG = 6
K_KWARG = 7
K_POSONLY = 8

S_TAG = 0
S_LOWER = 1
S_UPPER = 2
S_STEP = 3

# Integer literals above 32767 do not fit in a single SpaceLang token, so the
# few large constants this VM needs are parsed from strings at startup.
SURROGATE_LOW = int("55296")
SURROGATE_HIGH = int("56320")
BMP_LIMIT = int("65536")
USER_FUNC_BASE = int("10000")

NAME_TABLE_OPCODE = 53

# Fixed operand counts for every opcode with a fixed shape.  PUSH_INT (7) and
# PUSH_STR (8) carry variable payloads and are decoded separately.
ARITY = {
    0: 0,
    1: 2,
    2: 3,
    3: 1,
    4: 1,
    5: 1,
    6: 1,
    9: 1,
    10: 1,
    11: 1,
    12: 2,
    13: 1,
    14: 1,
    15: 1,
    16: 1,
    17: 2,
    18: 0,
    19: 1,
    20: 1,
    21: 1,
    22: 1,
    23: 1,
    24: 1,
    25: 0,
    26: 2,
    27: 0,
    28: 0,
    29: 0,
    30: 0,
    31: 1,
    32: 1,
    33: 0,
    34: 1,
    35: 0,
    36: 3,
    37: 1,
    38: 1,
    39: 1,
    40: 2,
    41: 4,
    42: 6,
    43: 8,
    44: 1,
    45: 0,
    46: 1,
    47: 0,
    48: 0,
    49: 9,
    50: 0,
    51: 1,
    52: 0,
}

HEX_DIGITS = "0123456789abcdef"


# --- small utilities --------------------------------------------------------
def vm_fail(message):
    print("sp_vm: " + message, file=sys.stderr)


def char_of(code):
    """Return the one-character string for a Unicode code point."""
    if code < 0 or code >= BMP_LIMIT:
        return "?"
    if code >= SURROGATE_LOW and code < SURROGATE_HIGH:
        return "?"
    if code < 256:
        return code.to_bytes(1, "big").decode("latin-1")
    return code.to_bytes(2, "big").decode("utf-16-be")


def read_text(path):
    handle = open(path, "r")
    text = handle.read()
    handle.close()
    return text


def hex_value(character):
    target = character.lower()
    index = 0
    while index < 16:
        if HEX_DIGITS[index] == target:
            return index
        index = index + 1
    return 0


def tokenize(text):
    """Split a .sp byte stream into token values (run lengths of spaces)."""
    lines = text.split("\n")
    while len(lines) > 0 and lines[-1] == "":
        lines.pop()
    values = []
    for line in lines:
        values.append(len(line))
    return values


def parse_names(text):
    """Parse the embedded JSON name table ("name": id pairs)."""
    names = {}
    count = len(text)
    index = 0
    while index < count and text[index] != "{":
        index = index + 1
    index = index + 1
    while index < count:
        while index < count and text[index] != "\"":
            index = index + 1
        if index >= count:
            break
        index = index + 1
        key = []
        closed = 0
        while index < count:
            character = text[index]
            if character == "\\":
                index = index + 1
                if index >= count:
                    break
                escape = text[index]
                if escape == "u":
                    value = 0
                    offset = 0
                    while offset < 4 and index + 1 + offset < count:
                        value = value * 16 + hex_value(text[index + 1 + offset])
                        offset = offset + 1
                    key.append(char_of(value))
                    index = index + 5
                elif escape == "n":
                    key.append("\n")
                    index = index + 1
                elif escape == "t":
                    key.append("\t")
                    index = index + 1
                elif escape == "r":
                    key.append("\r")
                    index = index + 1
                elif escape == "b":
                    key.append("\b")
                    index = index + 1
                elif escape == "f":
                    key.append("\f")
                    index = index + 1
                else:
                    key.append(escape)
                    index = index + 1
            elif character == "\"":
                index = index + 1
                closed = 1
                break
            else:
                key.append(character)
                index = index + 1
        if closed == 0:
            break
        while index < count and text[index] != ":":
            index = index + 1
        index = index + 1
        digits = []
        while index < count and text[index] != "," and text[index] != "}":
            digits.append(text[index])
            index = index + 1
        if len(digits) > 0:
            names["".join(key)] = int("".join(digits))
        if index < count and text[index] == ",":
            index = index + 1
        else:
            break
    return names


def read_payload(tokens, start, count):
    """Decode `count` character tokens into one string; return [text, next]."""
    characters = []
    index = start
    stop = start + count
    while index < stop:
        characters.append(char_of(tokens[index]))
        index = index + 1
    return ["".join(characters), index]


def decode(tokens):
    """Turn a token stream into (code, names).

    Each instruction becomes a list whose first slot is the opcode; PUSH_INT
    carries the decoded integer and PUSH_STR carries its length and payload.
    `names` maps numeric name ids to source identifiers.
    """
    code = []
    names = {}
    count = len(tokens)
    index = 0
    while index < count:
        op = tokens[index]
        index = index + 1
        if op == NAME_TABLE_OPCODE:
            if index >= count:
                break
            length = tokens[index]
            index = index + 1
            payload = read_payload(tokens, index, length)
            by_name = parse_names(payload[0])
            index = payload[1]
            for key in by_name:
                names[by_name[key]] = key
            break
        instruction = [op]
        if op == 7:
            if index >= count:
                break
            encoded = tokens[index]
            index = index + 1
            if encoded % 2 == 0:
                instruction.append(encoded // 2)
            else:
                instruction.append(-(encoded + 1) // 2)
        elif op == 8:
            if index >= count:
                break
            length = tokens[index]
            index = index + 1
            instruction.append(length)
            stop = index + length
            while index < stop and index < count:
                instruction.append(tokens[index])
                index = index + 1
        elif op in ARITY:
            wanted = ARITY[op]
            offset = 0
            while offset < wanted and index < count:
                instruction.append(tokens[index])
                index = index + 1
                offset = offset + 1
        else:
            vm_fail("unknown opcode " + str(op))
            break
        code.append(instruction)
    return [code, names]


def build_funcs(code):
    """Recover function ranges the way spacelang/parser.py does."""
    definitions = []
    index = 0
    while index < len(code):
        if code[index][0] == 17:
            definitions.append(index)
        index = index + 1
    funcs = {}
    position = 0
    while position < len(definitions):
        start = definitions[position]
        if position + 1 < len(definitions):
            limit = definitions[position + 1]
        else:
            limit = len(code)
        end = limit
        cursor = limit - 1
        found = 0
        while cursor > start:
            if code[cursor][0] == 18:
                end = cursor + 1
                found = 1
                break
            cursor = cursor - 1
        if found == 0:
            cursor = start + 1
            while cursor < limit:
                if code[cursor][0] == 29:
                    end = cursor
                    break
                cursor = cursor + 1
        funcs[code[start][1]] = [start + 1, end]
        position = position + 1
    return funcs


def collect(stack, count):
    """Pop `count` operands and return them in source order."""
    values = []
    index = 0
    while index < count:
        values.append(stack.pop())
        index = index + 1
    values.reverse()
    return values


def push_frame(frames, func_id, args, return_ip, cells):
    frame = {"l": args, "n": [1] * len(args), "r": return_ip, "c": cells}
    frames.append(frame)


def materialize(value):
    """Return something indexable that yields the same items as `value`."""
    kind = type(value)
    if kind is T_LIST or kind is T_TUPLE or kind is T_STR or kind is T_RANGE:
        return value
    # No iter()/next() builtins are available, but every Python iterable that
    # the subset can produce also implements __iter__/__next__ and len().
    starter = getattr(value, "__iter__")
    iterator = starter()
    stepper = getattr(iterator, "__next__")
    items = []
    total = len(value)
    index = 0
    while index < total:
        items.append(stepper())
        index = index + 1
    return items


def tail_names(parameters, count):
    names = []
    index = len(parameters) - count
    while index < len(parameters):
        if index >= 0:
            names.append(parameters[index])
        index = index + 1
    return names


def default_targets(parameters, positional_count, count):
    """The positional parameters that own the trailing default values."""
    names = []
    index = positional_count - count
    while index < positional_count:
        if index >= 0 and index < len(parameters):
            names.append(parameters[index])
        index = index + 1
    return names


def bind_closure(closure, positional, keywords):
    """Bind call arguments to a closure's parameters, or return None."""
    parameters = closure[K_PARAMS]
    if parameters is None:
        return positional
    defaults = closure[K_DEFAULTS]
    positional_count = closure[K_POSCOUNT]
    vararg_name = closure[K_VARARG]
    kwarg_name = closure[K_KWARG]
    positional_only = closure[K_POSONLY]
    if len(positional) > positional_count and vararg_name is None:
        vm_fail("too many positional arguments")
        return None
    bound = {}
    index = 0
    while index < len(positional) and index < positional_count:
        bound[parameters[index]] = positional[index]
        index = index + 1
    extra = {}
    for key in keywords:
        value = keywords[key]
        if key not in parameters:
            if kwarg_name is None:
                vm_fail("unexpected keyword argument " + key)
                return None
            extra[key] = value
            continue
        if parameters.index(key) < positional_only:
            if kwarg_name is None:
                vm_fail("positional-only argument passed as keyword: " + key)
                return None
            extra[key] = value
            continue
        if key in bound:
            vm_fail("multiple values for argument " + key)
            return None
        bound[key] = value
    args = []
    for name in parameters:
        if name in bound:
            args.append(bound[name])
        elif name in defaults:
            args.append(defaults[name])
        else:
            vm_fail("missing required argument " + name)
            return None
    if vararg_name is not None:
        args.append(tuple_of_tail(positional, positional_count))
    if kwarg_name is not None:
        args.append(extra)
    return args


def tuple_of_tail(values, start):
    items = []
    index = start
    while index < len(values):
        items.append(values[index])
        index = index + 1
    return T_TUPLE(items)


def slice_sequence(sequence, lower, upper, step):
    """Apply Python slice semantics to an indexable sequence."""
    total = len(sequence)
    if step is None:
        stride = 1
    else:
        stride = step
    if stride == 0:
        vm_fail("slice step cannot be zero")
        return None
    if stride > 0:
        if lower is None:
            start = 0
        else:
            start = lower
            if start < 0:
                start = start + total
        if upper is None:
            stop = total
        else:
            stop = upper
            if stop < 0:
                stop = stop + total
        if start < 0:
            start = 0
        if start > total:
            start = total
        if stop < 0:
            stop = 0
        if stop > total:
            stop = total
    else:
        if lower is None:
            start = total - 1
        else:
            start = lower
            if start < 0:
                start = start + total
        if upper is None:
            stop = -1
        else:
            stop = upper
            if stop < 0:
                stop = stop + total
        if start < -1:
            start = -1
        if start > total - 1:
            start = total - 1
        if stop < -1:
            stop = -1
        if stop > total - 1:
            stop = total - 1
    items = []
    cursor = start
    if stride > 0:
        while cursor < stop:
            items.append(sequence[cursor])
            cursor = cursor + stride
    else:
        while cursor > stop:
            items.append(sequence[cursor])
            cursor = cursor + stride
    return items


def slice_value(container, key):
    kind = type(container)
    items = slice_sequence(container, key[S_LOWER], key[S_UPPER], key[S_STEP])
    if items is None:
        return None
    if kind is T_STR:
        return "".join(items)
    if kind is T_TUPLE:
        return T_TUPLE(items)
    if kind is T_LIST:
        return items
    if kind is T_RANGE:
        return items
    vm_fail("slicing is not supported for this value")
    return None


def module_for(module_id):
    if module_id == 0:
        return math
    if module_id == 1:
        return random
    if module_id == 2:
        return os
    if module_id == 3:
        return re
    return sys


def call_builtin(func_id, args, keywords):
    """Dispatch the builtin table used by spacelang/builtins_py.py."""
    if func_id == 0:
        if len(keywords) == 0:
            if len(args) == 0:
                print()
            elif len(args) == 1:
                print(args[0])
            else:
                print(*args)
        else:
            print(*args, **keywords)
        return None
    if func_id == 2:
        return len(args[0])
    if func_id == 3:
        if len(args) >= 2:
            return int(args[0], args[1])
        return int(args[0])
    if func_id == 5:
        return str(args[0])
    if func_id == 8:
        if len(args) == 1:
            return range(args[0])
        if len(args) == 2:
            return range(args[0], args[1])
        return range(args[0], args[1], args[2])
    if func_id == 4:
        return float(args[0])
    if func_id == 6:
        return bool(args[0])
    if func_id == 7:
        return abs(args[0])
    if func_id == 10:
        if len(args) == 1:
            return open(args[0])
        if len(args) == 2:
            return open(args[0], args[1])
        return open(args[0], args[1], args[2])
    if func_id == 11:
        if len(args) >= 3:
            return getattr(args[0], args[1], args[2])
        return getattr(args[0], args[1])
    if func_id == 12:
        return setattr(args[0], args[1], args[2])
    if func_id == 13:
        return callable(args[0])
    if func_id == 14:
        return repr(args[0])
    if func_id == 15:
        if len(args) >= 3:
            return isinstance(args[0], args[1])
        return isinstance(args[0], args[1])
    if func_id == 16:
        if len(args) == 0:
            return set()
        return set(args[0])
    if func_id == 1:
        if len(args) == 0:
            return input()
        return input(args[0])
    if func_id == 9:
        return type(args[0])
    vm_fail("unsupported builtin " + str(func_id))
    return None


def binary(op_id, left, right):
    if op_id == 1:
        return left + right
    if op_id == 6:
        return left == right
    if op_id == 2:
        return left - right
    if op_id == 3:
        return left * right
    if op_id == 7:
        return left < right
    if op_id == 8:
        return left > right
    if op_id == 5:
        return left % right
    if op_id == 16:
        return left // right
    if op_id == 4:
        return left / right
    if op_id == 9:
        return left != right
    if op_id == 10:
        return left <= right
    if op_id == 11:
        return left >= right
    if op_id == 12:
        return left in right
    if op_id == 13:
        return left not in right
    if op_id == 17:
        return left ** right
    if op_id == 14:
        return left is right
    if op_id == 15:
        return left is not right
    vm_fail("unsupported binary operation " + str(op_id))
    return None


def concat(values):
    if len(values) == 0:
        return ""
    kind = type(values[0])
    uniform = 1
    for value in values:
        if type(value) is not kind:
            uniform = 0
    if uniform == 1 and kind is T_STR:
        return "".join(values)
    if uniform == 1 and kind is T_LIST:
        merged = []
        for value in values:
            merged.extend(value)
        return merged
    if uniform == 1 and kind is T_TUPLE:
        merged = []
        for value in values:
            merged.extend(value)
        return T_TUPLE(merged)
    vm_fail("CONCAT requires values of one type")
    return None


def stack_op(op_id, stack):
    if op_id == 1:
        stack.append(stack[len(stack) - 1])
        return 1
    if op_id == 2:
        first = stack.pop()
        second = stack.pop()
        stack.append(first)
        stack.append(second)
        return 1
    if op_id == 3:
        stack.pop()
        return 1
    if op_id == 4:
        stack.append(stack[len(stack) - 2])
        return 1
    if op_id == 5:
        third = stack.pop()
        second = stack.pop()
        first = stack.pop()
        stack.append(second)
        stack.append(third)
        stack.append(first)
        return 1
    vm_fail("unsupported stack operation " + str(op_id))
    return 0


def pop_parameters(stack, names, count):
    parameters = []
    index = 0
    while index < count:
        parameters.append(names[stack.pop()])
        index = index + 1
    parameters.reverse()
    return parameters


def pop_named_values(stack, names, count):
    """Pop name/value pairs pushed as (name, value) and keep source order."""
    pairs = []
    index = 0
    while index < count:
        value = stack.pop()
        pairs.append([names[stack.pop()], value])
        index = index + 1
    pairs.reverse()
    return pairs


def merge_defaults(parameters, positional_count, positional_defaults, keyword_defaults):
    table = {}
    targets = default_targets(parameters, positional_count, len(positional_defaults))
    index = 0
    while index < len(targets) and index < len(positional_defaults):
        table[targets[index]] = positional_defaults[index]
        index = index + 1
    for pair in keyword_defaults:
        table[pair[0]] = pair[1]
    return table


def make_closure(instruction, stack, names):
    """Build a closure record from the MAKE_CLOSURE* operands.

    Operands are popped in the reverse of the order the frontend pushes them:
    keyword defaults, positional defaults, parameter names, then free cells.
    """
    op = instruction[0]
    func_id = instruction[1]
    cell_count = instruction[2]
    if op == 36:
        cells = collect(stack, cell_count)
        return [CLOSURE_MARK, func_id, cells, None, {}, instruction[3], None, None, 0]
    if op == 41:
        parameter_count = instruction[3]
        default_count = instruction[4]
        defaults = collect(stack, default_count)
        parameters = pop_parameters(stack, names, parameter_count)
        cells = collect(stack, cell_count)
        table = {}
        targets = tail_names(parameters, default_count)
        index = 0
        while index < len(targets) and index < len(defaults):
            table[targets[index]] = defaults[index]
            index = index + 1
        return [
            CLOSURE_MARK,
            func_id,
            cells,
            parameters,
            table,
            parameter_count,
            None,
            None,
            0,
        ]
    if op == 42:
        positional_count = instruction[3]
        keyword_only_count = instruction[4]
        positional_defaults_count = instruction[5]
        keyword_defaults_count = instruction[6]
        keyword_defaults = pop_named_values(stack, names, keyword_defaults_count)
        positional_defaults = collect(stack, positional_defaults_count)
        parameters = pop_parameters(stack, names, positional_count + keyword_only_count)
        cells = collect(stack, cell_count)
        return [
            CLOSURE_MARK,
            func_id,
            cells,
            parameters,
            merge_defaults(
                parameters, positional_count, positional_defaults, keyword_defaults
            ),
            positional_count,
            None,
            None,
            0,
        ]
    if op == 43 or op == 49:
        if op == 43:
            positional_only_count = 0
            positional_count = instruction[3]
            keyword_only_count = instruction[4]
            positional_defaults_count = instruction[5]
            keyword_defaults_count = instruction[6]
            has_varargs = instruction[7]
            has_kwargs = instruction[8]
        else:
            positional_only_count = instruction[3]
            positional_count = instruction[4]
            keyword_only_count = instruction[5]
            positional_defaults_count = instruction[6]
            keyword_defaults_count = instruction[7]
            has_varargs = instruction[8]
            has_kwargs = instruction[9]
        kwarg_name = None
        if has_kwargs == 1:
            kwarg_name = names[stack.pop()]
        vararg_name = None
        if has_varargs == 1:
            vararg_name = names[stack.pop()]
        keyword_defaults = pop_named_values(stack, names, keyword_defaults_count)
        positional_defaults = collect(stack, positional_defaults_count)
        parameters = pop_parameters(stack, names, positional_count + keyword_only_count)
        cells = collect(stack, cell_count)
        return [
            CLOSURE_MARK,
            func_id,
            cells,
            parameters,
            merge_defaults(
                parameters, positional_count, positional_defaults, keyword_defaults
            ),
            positional_count,
            vararg_name,
            kwarg_name,
            positional_only_count,
        ]
    return None


def is_closure(value):
    return (
        type(value) is T_LIST
        and len(value) > K_TAG
        and value[K_TAG] is CLOSURE_MARK
    )


def is_cell(value):
    return type(value) is T_LIST and len(value) == 3 and value[C_TAG] is CELL_MARK


def run(code, funcs, names, globals_):
    """Execute decoded instructions until HALT."""
    stack = []
    frames = []
    total = len(code)
    ip = 0
    while ip < total:
        instruction = code[ip]
        op = instruction[0]

        if op == 7:
            stack.append(instruction[1])
            ip = ip + 1
            continue

        if op == 9:
            stack.append(globals_[names[instruction[1]]])
            ip = ip + 1
            continue

        if op == 5:
            right = stack.pop()
            left = stack.pop()
            stack.append(binary(instruction[1], left, right))
            ip = ip + 1
            continue

        if op == 23:
            if not stack.pop():
                ip = instruction[1]
            else:
                ip = ip + 1
            continue

        if op == 22:
            ip = instruction[1]
            continue

        if op == 10:
            globals_[names[instruction[1]]] = stack.pop()
            ip = ip + 1
            continue

        if op == 1:
            target = instruction[1]
            args = collect(stack, instruction[2])
            if target >= USER_FUNC_BASE:
                push_frame(frames, target, args, ip + 1, [])
                ip = funcs[target][0]
            else:
                stack.append(call_builtin(target, args, {}))
                ip = ip + 1
            continue

        if op == 20:
            frame = frames[len(frames) - 1]
            slot = instruction[1]
            locals_ = frame["l"]
            if slot < len(locals_) and frame["n"][slot]:
                value = locals_[slot]
                if is_cell(value):
                    if value[C_READY] == 0:
                        vm_fail("undefined local slot " + str(slot))
                        return
                    value = value[C_VALUE]
                stack.append(value)
            else:
                vm_fail("undefined local slot " + str(slot))
                return
            ip = ip + 1
            continue

        if op == 21:
            frame = frames[len(frames) - 1]
            slot = instruction[1]
            value = stack.pop()
            locals_ = frame["l"]
            flags = frame["n"]
            while len(locals_) <= slot:
                locals_.append(None)
                flags.append(0)
            current = locals_[slot]
            if is_cell(current):
                current[C_VALUE] = value
                current[C_READY] = 1
                flags[slot] = 1
            else:
                locals_[slot] = value
                flags[slot] = 1
            ip = ip + 1
            continue

        if op == 13:
            key = stack.pop()
            container = stack.pop()
            if type(key) is T_LIST and len(key) == 4 and key[S_TAG] is SLICE_MARK:
                value = slice_value(container, key)
                if value is None:
                    return
                stack.append(value)
            else:
                stack.append(container[key])
            ip = ip + 1
            continue

        if op == 6:
            if stack_op(instruction[1], stack) == 0:
                return
            ip = ip + 1
            continue

        if op == 12:
            args = collect(stack, instruction[2])
            receiver = stack.pop()
            method = getattr(receiver, names[instruction[1]])
            stack.append(method(*args))
            ip = ip + 1
            continue

        if op == 11:
            receiver = stack.pop()
            stack.append(getattr(receiver, names[instruction[1]]))
            ip = ip + 1
            continue

        if op == 8:
            payload = []
            index = 2
            while index < len(instruction):
                payload.append(char_of(instruction[index]))
                index = index + 1
            stack.append("".join(payload))
            ip = ip + 1
            continue

        if op == 18:
            value = stack.pop()
            if len(frames) == 0:
                return
            frame = frames.pop()
            stack.append(value)
            ip = frame["r"]
            continue

        if op == 14:
            stack.append(collect(stack, instruction[1]))
            ip = ip + 1
            continue

        if op == 24:
            if stack.pop():
                ip = instruction[1]
            else:
                ip = ip + 1
            continue

        if op == 31:
            iterator = stack[len(stack) - 1]
            sequence = iterator[0]
            position = iterator[1]
            if position < len(sequence):
                stack.append(sequence[position])
                iterator[1] = position + 1
                ip = ip + 1
            else:
                stack.pop()
                ip = instruction[1]
            continue

        if op == 30:
            stack.append([materialize(stack.pop()), 0])
            ip = ip + 1
            continue

        if op == 35:
            stack.append(None)
            ip = ip + 1
            continue

        if op == 16:
            value = concat(collect(stack, instruction[1]))
            if value is None:
                return
            stack.append(value)
            ip = ip + 1
            continue

        if op == 3:
            args = collect(stack, instruction[1])
            target = stack.pop()
            if is_closure(target):
                bound = bind_closure(target, args, {})
                if bound is None:
                    return
                push_frame(frames, target[K_FUNC], bound, ip + 1, target[K_CELLS])
                ip = funcs[target[K_FUNC]][0]
            else:
                stack.append(target(*args))
                ip = ip + 1
            continue

        if op == 17:
            target = instruction[1]
            ip = funcs[target][1]
            continue

        if op == 44:
            items = []
            index = 0
            while index < instruction[1]:
                value = stack.pop()
                key = stack.pop()
                items.append([key, value])
                index = index + 1
            items.reverse()
            table = {}
            for pair in items:
                table[pair[0]] = pair[1]
            stack.append(table)
            ip = ip + 1
            continue

        if op == 15:
            values = collect(stack, instruction[1])
            stack.append(T_TUPLE(values))
            ip = ip + 1
            continue

        if op == 34:
            values = materialize(stack.pop())
            if len(values) != instruction[1]:
                vm_fail("cannot unpack sequence into " + str(instruction[1]) + " targets")
                return
            index = instruction[1] - 1
            while index >= 0:
                stack.append(values[index])
                index = index - 1
            ip = ip + 1
            continue

        if op == 29:
            return

        if op == 2:
            positional = collect(stack, instruction[2])
            keywords = {}
            index = 0
            while index < instruction[3]:
                value = stack.pop()
                key = names[stack.pop()]
                keywords[key] = value
                index = index + 1
            target = instruction[1]
            if target >= USER_FUNC_BASE:
                vm_fail("keyword calls to user functions are not supported")
                return
            stack.append(call_builtin(target, positional, keywords))
            ip = ip + 1
            continue

        if op == 40:
            keywords = {}
            index = 0
            while index < instruction[2]:
                value = stack.pop()
                key = names[stack.pop()]
                keywords[key] = value
                index = index + 1
            args = collect(stack, instruction[1])
            target = stack.pop()
            if is_closure(target):
                bound = bind_closure(target, args, keywords)
                if bound is None:
                    return
                push_frame(frames, target[K_FUNC], bound, ip + 1, target[K_CELLS])
                ip = funcs[target[K_FUNC]][0]
            else:
                stack.append(target(*args, **keywords))
                ip = ip + 1
            continue

        if op == 46:
            keywords = stack.pop()
            positional = stack.pop()
            stack.append(call_builtin(instruction[1], positional, keywords))
            ip = ip + 1
            continue

        if op == 45:
            keywords = stack.pop()
            positional = stack.pop()
            target = stack.pop()
            if is_closure(target):
                bound = bind_closure(target, positional, keywords)
                if bound is None:
                    return
                push_frame(frames, target[K_FUNC], bound, ip + 1, target[K_CELLS])
                ip = funcs[target[K_FUNC]][0]
            else:
                stack.append(target(*positional, **keywords))
                ip = ip + 1
            continue

        if op == 52:
            step = stack.pop()
            upper = stack.pop()
            lower = stack.pop()
            stack.append([SLICE_MARK, lower, upper, step])
            ip = ip + 1
            continue

        if op == 37:
            frame = frames[len(frames) - 1]
            slot = instruction[1]
            locals_ = frame["l"]
            flags = frame["n"]
            while len(locals_) <= slot:
                locals_.append(None)
                flags.append(0)
            if not is_cell(locals_[slot]):
                locals_[slot] = [CELL_MARK, locals_[slot], flags[slot]]
            flags[slot] = 1
            ip = ip + 1
            continue

        if op == 38:
            frame = frames[len(frames) - 1]
            slot = instruction[1]
            locals_ = frame["l"]
            if slot < len(locals_) and is_cell(locals_[slot]):
                stack.append(locals_[slot])
            else:
                vm_fail("local slot " + str(slot) + " is not a cell")
                return
            ip = ip + 1
            continue

        if op == 39:
            frame = frames[len(frames) - 1]
            cells = frame["c"]
            index = instruction[1]
            if index < len(cells):
                stack.append(cells[index])
            else:
                vm_fail("undefined closure cell " + str(index))
                return
            ip = ip + 1
            continue

        if op == 19:
            frame = frames[len(frames) - 1]
            slot = instruction[1]
            if slot < len(frame["l"]):
                stack.append(frame["l"][slot])
            else:
                vm_fail("undefined argument slot " + str(slot))
                return
            ip = ip + 1
            continue

        if op == 32:
            receiver = stack.pop()
            value = stack.pop()
            setattr(receiver, names[instruction[1]], value)
            ip = ip + 1
            continue

        if op == 33:
            key = stack.pop()
            container = stack.pop()
            value = stack.pop()
            if type(key) is T_LIST and len(key) == 4 and key[S_TAG] is SLICE_MARK:
                vm_fail("slice assignment is not supported")
                return
            container[key] = value
            ip = ip + 1
            continue

        if op == 51:
            stack.append(T_SET(collect(stack, instruction[1])))
            ip = ip + 1
            continue

        if op == 47:
            iterable = stack.pop()
            target = stack.pop()
            target.extend(iterable)
            stack.append(target)
            ip = ip + 1
            continue

        if op == 48:
            mapping = stack.pop()
            target = stack.pop()
            for key in mapping:
                if key in target:
                    vm_fail("duplicate keyword argument " + str(key))
                    return
                target[key] = mapping[key]
            stack.append(target)
            ip = ip + 1
            continue

        if op == 50:
            mapping = stack.pop()
            target = stack.pop()
            for key in mapping:
                target[key] = mapping[key]
            stack.append(target)
            ip = ip + 1
            continue

        if op == 4:
            stack.append(module_for(instruction[1]))
            ip = ip + 1
            continue

        if op == 36 or op == 41 or op == 42 or op == 43 or op == 49:
            closure = make_closure(instruction, stack, names)
            if closure is None:
                return
            stack.append(closure)
            ip = ip + 1
            continue

        if op == 0:
            ip = ip + 1
            continue

        vm_fail("unsupported opcode " + str(op) + " at instruction " + str(ip))
        return


def load_sidecar_names(path):
    """Names for programs that keep them in a companion .names.json file."""
    dot = path.rfind(".")
    if dot <= 0:
        return {}
    stem = ""
    index = 0
    while index < dot:
        stem = stem + path[index]
        index = index + 1
    sidecar = stem + ".names.json"
    if not os.path.exists(sidecar):
        return {}
    return parse_names(read_text(sidecar))


def main():
    argv = __argv__
    if len(argv) < 2:
        vm_fail("usage: sp_vm.sp TARGET.sp [ARG ...]")
        return 1
    target = argv[1]
    tokens = tokenize(read_text(target))
    decoded = decode(tokens)
    code = decoded[0]
    names = decoded[1]
    if len(names) == 0:
        by_name = load_sidecar_names(target)
        for key in by_name:
            names[by_name[key]] = key
    funcs = build_funcs(code)
    inner_argv = []
    index = 1
    while index < len(argv):
        inner_argv.append(argv[index])
        index = index + 1
    state = {}
    state["__argv__"] = inner_argv
    state["__file__"] = target
    run(code, funcs, names, state)
    return 0


main()
