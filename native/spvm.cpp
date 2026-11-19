// spvm.cpp -- a standalone SpaceLang program runner with no Python dependency.
//
//   spvm.exe PROGRAM.sp [ARG ...]
//
// It reads a compiled .sp file (whitespace token stream), decodes it into
// instructions, and executes them on a native stack machine.  Values are a
// tagged union with heap objects for strings, lists, tuples, dicts, sets,
// closures, cells, iterators and ranges, so no CPython is involved anywhere.
//
// Scope: the instruction set that spacelang/pyfront.py can emit, minus the
// exception opcodes (TRY/END_TRY/RAISE/SETUP_WITH), which the Python frontend
// cannot produce.  Builtins and container methods cover the documented subset;
// anything missing fails with a clear message instead of misbehaving.
//
// This file is deliberately self-contained: one translation unit, standard
// library only, so `g++ -O2 spvm.cpp -o spvm.exe` needs no build system.

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <iostream>
#include <map>
#include <memory>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

namespace {

struct Error : std::runtime_error {
    explicit Error(const std::string& message) : std::runtime_error(message) {}
};

enum class Tag { Nil, Bool, Int, Float, Str, List, Tuple, Dict, Set, Func, Cell, Iter, Range, Slice, File };

struct Obj;
using ObjPtr = std::shared_ptr<Obj>;

struct Value {
    Tag tag = Tag::Nil;
    bool b = false;
    long long i = 0;
    double f = 0.0;
    ObjPtr obj;
};

struct Obj {
    Tag tag;
    explicit Obj(Tag t) : tag(t) {}
    virtual ~Obj() {}
};

struct StrObj : Obj {
    std::string text;
    explicit StrObj(std::string value) : Obj(Tag::Str), text(std::move(value)) {}
};

struct ListObj : Obj {
    std::vector<Value> items;
    ListObj() : Obj(Tag::List) {}
};

struct TupleObj : Obj {
    std::vector<Value> items;
    TupleObj() : Obj(Tag::Tuple) {}
};

struct DictObj : Obj {
    // Insertion ordered, like a Python dict.  Small dicts make linear lookup fine.
    std::vector<std::pair<Value, Value>> items;
    DictObj() : Obj(Tag::Dict) {}
};

struct SetObj : Obj {
    std::vector<Value> items;
    SetObj() : Obj(Tag::Set) {}
};

struct FuncObj : Obj {
    long long func_id = 0;
    std::vector<Value> cells;
    std::vector<std::string> params;          // parameter names, in order
    std::map<std::string, Value> defaults;    // name -> default value
    long long positional_count = -1;          // -1 marks a legacy closure
    long long positional_only_count = 0;
    std::string vararg_name;
    std::string kwarg_name;
    long long legacy_arg_count = 0;
    FuncObj() : Obj(Tag::Func) {}
};

struct CellObj : Obj {
    Value value;
    bool initialized = false;
    CellObj() : Obj(Tag::Cell) {}
};

struct IterObj : Obj {
    std::vector<Value> items;
    std::size_t position = 0;
    IterObj() : Obj(Tag::Iter) {}
};

struct RangeObj : Obj {
    long long start = 0;
    long long stop = 0;
    long long step = 1;
    RangeObj() : Obj(Tag::Range) {}
};

struct SliceObj : Obj {
    Value lower;
    Value upper;
    Value step;
    SliceObj() : Obj(Tag::Slice) {}
};

struct FileObj : Obj {
    std::FILE* handle = nullptr;
    bool closed = false;
    FileObj() : Obj(Tag::File) {}
    ~FileObj() override {
        if (handle != nullptr) {
            std::fclose(handle);
        }
    }
};

// ---------------------------------------------------------------- constructors
Value make_nil() { return Value(); }

Value make_bool(bool value) {
    Value result;
    result.tag = Tag::Bool;
    result.b = value;
    return result;
}

Value make_int(long long value) {
    Value result;
    result.tag = Tag::Int;
    result.i = value;
    return result;
}

Value make_float(double value) {
    Value result;
    result.tag = Tag::Float;
    result.f = value;
    return result;
}

Value make_str(std::string value) {
    Value result;
    result.tag = Tag::Str;
    result.obj = std::make_shared<StrObj>(std::move(value));
    return result;
}

Value make_list(std::vector<Value> items) {
    auto container = std::make_shared<ListObj>();
    container->items = std::move(items);
    Value result;
    result.tag = Tag::List;
    result.obj = container;
    return result;
}

Value make_tuple(std::vector<Value> items) {
    auto container = std::make_shared<TupleObj>();
    container->items = std::move(items);
    Value result;
    result.tag = Tag::Tuple;
    result.obj = container;
    return result;
}

Value make_dict() {
    Value result;
    result.tag = Tag::Dict;
    result.obj = std::make_shared<DictObj>();
    return result;
}

Value make_set() {
    Value result;
    result.tag = Tag::Set;
    result.obj = std::make_shared<SetObj>();
    return result;
}

Value make_range(long long start, long long stop, long long step) {
    Value result;
    result.tag = Tag::Range;
    auto range = std::make_shared<RangeObj>();
    range->start = start;
    range->stop = stop;
    range->step = step;
    result.obj = range;
    return result;
}

// --------------------------------------------------------------- raw accessors
StrObj& as_str(const Value& value) { return *static_cast<StrObj*>(value.obj.get()); }
ListObj& as_list(const Value& value) { return *static_cast<ListObj*>(value.obj.get()); }
TupleObj& as_tuple(const Value& value) { return *static_cast<TupleObj*>(value.obj.get()); }
DictObj& as_dict(const Value& value) { return *static_cast<DictObj*>(value.obj.get()); }
SetObj& as_set(const Value& value) { return *static_cast<SetObj*>(value.obj.get()); }
FuncObj& as_func(const Value& value) { return *static_cast<FuncObj*>(value.obj.get()); }
CellObj& as_cell(const Value& value) { return *static_cast<CellObj*>(value.obj.get()); }
IterObj& as_iter(const Value& value) { return *static_cast<IterObj*>(value.obj.get()); }
RangeObj& as_range(const Value& value) { return *static_cast<RangeObj*>(value.obj.get()); }
SliceObj& as_slice(const Value& value) { return *static_cast<SliceObj*>(value.obj.get()); }
FileObj& as_file(const Value& value) { return *static_cast<FileObj*>(value.obj.get()); }

// Python's floor division and modulo have the sign of the divisor.
long long floor_div(long long left, long long right) {
    long long quotient = left / right;
    if ((left % right != 0) && ((left < 0) != (right < 0))) {
        --quotient;
    }
    return quotient;
}

long long floor_mod(long long left, long long right) {
    long long result = left % right;
    if (result != 0 && ((result < 0) != (right < 0))) {
        result += right;
    }
    return result;
}

bool is_number(const Value& value) {
    return value.tag == Tag::Int || value.tag == Tag::Float || value.tag == Tag::Bool;
}

double as_double(const Value& value) {
    switch (value.tag) {
        case Tag::Int: return static_cast<double>(value.i);
        case Tag::Float: return value.f;
        case Tag::Bool: return value.b ? 1.0 : 0.0;
        default: throw Error("expected a number");
    }
}

long long as_int(const Value& value) {
    switch (value.tag) {
        case Tag::Int: return value.i;
        case Tag::Bool: return value.b ? 1 : 0;
        case Tag::Float: return static_cast<long long>(value.f);
        default: throw Error("expected an integer");
    }
}

// ------------------------------------------------------------------ comparison
bool values_equal(const Value& left, const Value& right) {
    if (is_number(left) && is_number(right)) {
        if (left.tag == Tag::Float || right.tag == Tag::Float) {
            return as_double(left) == as_double(right);
        }
        return as_int(left) == as_int(right);
    }
    if (left.tag != right.tag) {
        return false;
    }
    switch (left.tag) {
        case Tag::Nil: return true;
        case Tag::Bool: return left.b == right.b;
        case Tag::Int: return left.i == right.i;
        case Tag::Float: return left.f == right.f;
        case Tag::Str: return as_str(left).text == as_str(right).text;
        case Tag::List:
        case Tag::Tuple:
        case Tag::Set: {
            const std::vector<Value>& first = left.tag == Tag::List
                ? as_list(left).items
                : (left.tag == Tag::Tuple ? as_tuple(left).items : as_set(left).items);
            const std::vector<Value>& second = right.tag == Tag::List
                ? as_list(right).items
                : (right.tag == Tag::Tuple ? as_tuple(right).items : as_set(right).items);
            if (first.size() != second.size()) {
                return false;
            }
            for (std::size_t index = 0; index < first.size(); ++index) {
                if (!values_equal(first[index], second[index])) {
                    return false;
                }
            }
            return true;
        }
        case Tag::Dict: {
            const DictObj& first = as_dict(left);
            const DictObj& second = as_dict(right);
            if (first.items.size() != second.items.size()) {
                return false;
            }
            for (const auto& item : first.items) {
                bool found = false;
                for (const auto& candidate : second.items) {
                    if (values_equal(item.first, candidate.first)
                        && values_equal(item.second, candidate.second)) {
                        found = true;
                        break;
                    }
                }
                if (!found) {
                    return false;
                }
            }
            return true;
        }
        default:
            return left.obj == right.obj;
    }
}

int compare_values(const Value& left, const Value& right) {
    if (is_number(left) && is_number(right)) {
        const double first = as_double(left);
        const double second = as_double(right);
        return first < second ? -1 : (first > second ? 1 : 0);
    }
    if (left.tag == Tag::Str && right.tag == Tag::Str) {
        const int result = as_str(left).text.compare(as_str(right).text);
        return result < 0 ? -1 : (result > 0 ? 1 : 0);
    }
    throw Error("values are not orderable");
}

bool truthy(const Value& value) {
    switch (value.tag) {
        case Tag::Nil: return false;
        case Tag::Bool: return value.b;
        case Tag::Int: return value.i != 0;
        case Tag::Float: return value.f != 0.0;
        case Tag::Str: return !as_str(value).text.empty();
        case Tag::List: return !as_list(value).items.empty();
        case Tag::Tuple: return !as_tuple(value).items.empty();
        case Tag::Dict: return !as_dict(value).items.empty();
        case Tag::Set: return !as_set(value).items.empty();
        default: return true;
    }
}

std::size_t length_of(const Value& value) {
    switch (value.tag) {
        case Tag::Str: return as_str(value).text.size();
        case Tag::List: return as_list(value).items.size();
        case Tag::Tuple: return as_tuple(value).items.size();
        case Tag::Dict: return as_dict(value).items.size();
        case Tag::Set: return as_set(value).items.size();
        case Tag::Range: {
            const RangeObj& range = as_range(value);
            if (range.step > 0) {
                return range.stop <= range.start
                    ? 0
                    : static_cast<std::size_t>((range.stop - range.start + range.step - 1) / range.step);
            }
            return range.stop >= range.start
                ? 0
                : static_cast<std::size_t>((range.start - range.stop - range.step - 1) / -range.step);
        }
        default: throw Error("object has no length");
    }
}

// Python slice semantics over a materialized sequence.
std::vector<Value> slice_vector(const std::vector<Value>& source, const SliceObj& slice) {
    const long long size = static_cast<long long>(source.size());
    const long long step = slice.step.tag == Tag::Nil ? 1 : as_int(slice.step);
    if (step == 0) {
        throw Error("slice step cannot be zero");
    }
    long long start = 0;
    long long stop = 0;
    if (step > 0) {
        start = slice.lower.tag == Tag::Nil ? 0 : as_int(slice.lower);
        if (start < 0) {
            start += size;
        }
        start = std::max(0LL, std::min(start, size));
        stop = slice.upper.tag == Tag::Nil ? size : as_int(slice.upper);
        if (stop < 0) {
            stop += size;
        }
        stop = std::max(0LL, std::min(stop, size));
    } else {
        start = slice.lower.tag == Tag::Nil ? size - 1 : as_int(slice.lower);
        if (start < 0) {
            start += size;
        }
        start = std::max(-1LL, std::min(start, size - 1));
        if (slice.upper.tag == Tag::Nil) {
            stop = -1;
        } else {
            stop = as_int(slice.upper);
            if (stop < 0) {
                stop += size;
            }
            stop = std::max(-1LL, std::min(stop, size - 1));
        }
    }
    std::vector<Value> picked;
    if (step > 0) {
        for (long long index = start; index < stop; index += step) {
            picked.push_back(source[static_cast<std::size_t>(index)]);
        }
    } else {
        for (long long index = start; index > stop; index += step) {
            picked.push_back(source[static_cast<std::size_t>(index)]);
        }
    }
    return picked;
}

// -------------------------------------------------------------------- printing
void append_utf8(std::string& out, std::uint32_t code);

std::string quote_string(const std::string& text) {
    const bool has_single = text.find('\'') != std::string::npos;
    const bool has_double = text.find('"') != std::string::npos;
    const char quote = (has_single && !has_double) ? '"' : '\'';
    std::string result(1, quote);
    for (const char character : text) {
        switch (character) {
            case '\\': result += "\\\\"; break;
            case '\n': result += "\\n"; break;
            case '\r': result += "\\r"; break;
            case '\t': result += "\\t"; break;
            case '\0': result += "\\x00"; break;
            default:
                if (character == quote) {
                    result += '\\';
                }
                result += character;
        }
    }
    result += quote;
    return result;
}

std::string format_double(double value) {
    if (std::isnan(value)) {
        return "nan";
    }
    if (std::isinf(value)) {
        return value < 0 ? "-inf" : "inf";
    }
    char buffer[64];
    for (int precision = 15; precision <= 17; ++precision) {
        std::snprintf(buffer, sizeof(buffer), "%.*g", precision, value);
        if (std::strtod(buffer, nullptr) == value) {
            break;
        }
    }
    std::string text(buffer);
    if (text.find('.') == std::string::npos && text.find('e') == std::string::npos
        && text.find("inf") == std::string::npos && text.find("nan") == std::string::npos) {
        text += ".0";
    }
    return text;
}

std::string repr(const Value& value);

std::string repr_items(const std::vector<Value>& items, const char* open, const char* close) {
    std::string out(open);
    for (std::size_t index = 0; index < items.size(); ++index) {
        if (index != 0) {
            out += ", ";
        }
        out += repr(items[index]);
    }
    out += close;
    return out;
}

std::string repr(const Value& value) {
    switch (value.tag) {
        case Tag::Nil: return "None";
        case Tag::Bool: return value.b ? "True" : "False";
        case Tag::Int: return std::to_string(value.i);
        case Tag::Float: return format_double(value.f);
        case Tag::Str: return quote_string(as_str(value).text);
        case Tag::List: return repr_items(as_list(value).items, "[", "]");
        case Tag::Tuple: {
            const std::string inner = repr_items(as_tuple(value).items, "(", ")");
            return as_tuple(value).items.size() == 1 ? inner.substr(0, inner.size() - 1) + ",)" : inner;
        }
        case Tag::Dict: {
            std::string out = "{";
            const auto& items = as_dict(value).items;
            for (std::size_t index = 0; index < items.size(); ++index) {
                if (index != 0) {
                    out += ", ";
                }
                out += repr(items[index].first) + ": " + repr(items[index].second);
            }
            out += "}";
            return out;
        }
        case Tag::Set: {
            if (as_set(value).items.empty()) {
                return "set()";
            }
            return repr_items(as_set(value).items, "{", "}");
        }
        case Tag::Range: {
            const RangeObj& range = as_range(value);
            if (range.step == 1) {
                return "range(" + std::to_string(range.start) + ", " + std::to_string(range.stop) + ")";
            }
            return "range(" + std::to_string(range.start) + ", " + std::to_string(range.stop) + ", "
                + std::to_string(range.step) + ")";
        }
        case Tag::Func: return "<function>";
        case Tag::Cell: return "<cell>";
        case Tag::Iter: return "<iterator>";
        case Tag::Slice: return "<slice>";
        case Tag::File: return "<file>";
    }
    return "<?>";
}

std::string to_text(const Value& value) {
    return value.tag == Tag::Str ? as_str(value).text : repr(value);
}

void append_utf8(std::string& out, std::uint32_t code) {
    if (code < 0x80) {
        out += static_cast<char>(code);
    } else if (code < 0x800) {
        out += static_cast<char>(0xC0 | (code >> 6));
        out += static_cast<char>(0x80 | (code & 0x3F));
    } else if (code < 0x10000) {
        out += static_cast<char>(0xE0 | (code >> 12));
        out += static_cast<char>(0x80 | ((code >> 6) & 0x3F));
        out += static_cast<char>(0x80 | (code & 0x3F));
    } else {
        out += static_cast<char>(0xF0 | (code >> 18));
        out += static_cast<char>(0x80 | ((code >> 12) & 0x3F));
        out += static_cast<char>(0x80 | ((code >> 6) & 0x3F));
        out += static_cast<char>(0x80 | (code & 0x3F));
    }
}

// ----------------------------------------------------------------------- dicts
Value* dict_find(DictObj& dict, const Value& key) {
    for (auto& item : dict.items) {
        if (values_equal(item.first, key)) {
            return &item.second;
        }
    }
    return nullptr;
}

void dict_set(DictObj& dict, const Value& key, const Value& value) {
    if (Value* existing = dict_find(dict, key)) {
        *existing = value;
        return;
    }
    dict.items.emplace_back(key, value);
}

// ------------------------------------------------------------------------ code
struct Instr {
    int op = 0;
    std::vector<long long> args;
    int line = 0;
};

struct Program {
    std::vector<Instr> instrs;
    std::unordered_map<long long, std::string> names;
    std::unordered_map<long long, std::pair<long long, long long>> funcs;
};

std::string read_file(const std::string& path) {
    std::ifstream stream(path, std::ios::binary);
    if (!stream) {
        throw Error("cannot open " + path);
    }
    std::ostringstream buffer;
    buffer << stream.rdbuf();
    return buffer.str();
}

// Fixed operand counts; PUSH_INT (7) and PUSH_STR (8) are decoded separately.
const int kArity[53] = {
    0, 2, 3, 1, 1, 1, 1, 1, 0, 1, 1, 1, 2, 1, 1, 1, 1, 2, 0, 1, 1, 1, 1, 1, 1, 0, 2,
    0, 0, 0, 0, 1, 1, 0, 1, 0, 3, 1, 1, 1, 2, 4, 6, 8, 1, 0, 1, 0, 0, 9, 0, 1, 0,
};

std::vector<long long> tokenize(const std::string& text) {
    std::vector<long long> tokens;
    long long run = 0;
    for (const char character : text) {
        if (character == ' ') {
            ++run;
        } else if (character == '\n') {
            tokens.push_back(run);
            run = 0;
        } else if (character == '\r') {
            continue;
        } else {
            throw Error("invalid character in .sp file");
        }
    }
    if (run != 0) {
        tokens.push_back(run);
    }
    return tokens;
}

int hex_digit(char character) {
    if (character >= '0' && character <= '9') {
        return character - '0';
    }
    if (character >= 'a' && character <= 'f') {
        return character - 'a' + 10;
    }
    if (character >= 'A' && character <= 'F') {
        return character - 'A' + 10;
    }
    throw Error("bad hex digit in name table");
}

// The name table is a JSON object of "name": id pairs with ASCII escapes.
std::unordered_map<long long, std::string> parse_name_json(const std::string& text) {
    std::unordered_map<long long, std::string> by_id;
    std::size_t index = text.find('{');
    if (index == std::string::npos) {
        return by_id;
    }
    ++index;
    while (index < text.size()) {
        std::size_t quote = text.find('"', index);
        if (quote == std::string::npos) {
            break;
        }
        index = quote + 1;
        std::string key;
        bool closed = false;
        while (index < text.size()) {
            const char character = text[index];
            if (character == '\\' && index + 1 < text.size()) {
                const char escape = text[index + 1];
                if (escape == 'u') {
                    if (index + 5 >= text.size()) {
                        break;
                    }
                    std::uint32_t code = 0;
                    for (int offset = 0; offset < 4; ++offset) {
                        code = code * 16 + static_cast<std::uint32_t>(hex_digit(text[index + 2 + offset]));
                    }
                    append_utf8(key, code);
                    index += 6;
                } else {
                    key += (escape == 'n') ? '\n' : (escape == 't') ? '\t' : (escape == 'r') ? '\r' : escape;
                    index += 2;
                }
            } else if (character == '"') {
                ++index;
                closed = true;
                break;
            } else {
                key += character;
                ++index;
            }
        }
        if (!closed) {
            break;
        }
        const std::size_t colon = text.find(':', index);
        if (colon == std::string::npos) {
            break;
        }
        index = colon + 1;
        long long id = 0;
        while (index < text.size() && text[index] != ',' && text[index] != '}') {
            if (text[index] >= '0' && text[index] <= '9') {
                id = id * 10 + (text[index] - '0');
            }
            ++index;
        }
        by_id[id] = key;
        if (index < text.size() && text[index] == ',') {
            ++index;
            continue;
        }
        break;
    }
    return by_id;
}

std::unordered_map<long long, std::string> parse_names(const std::vector<long long>& codes) {
    std::string text;
    for (const long long code : codes) {
        append_utf8(text, static_cast<std::uint32_t>(code));
    }
    return parse_name_json(text);
}

// Programs produced by some quine workflows keep names in a sidecar file.
std::string sidecar_path(const std::string& path) {
    const std::size_t slash = path.find_last_of("/\\");
    const std::size_t dot = path.find_last_of('.');
    if (dot != std::string::npos && (slash == std::string::npos || dot > slash)) {
        return path.substr(0, dot) + ".names.json";
    }
    return path + ".names.json";
}

Program decode(const std::vector<long long>& tokens) {
    Program program;
    std::size_t index = 0;
    while (index < tokens.size()) {
        const long long op = tokens[index++];
        if (op == 53) {
            if (index >= tokens.size()) {
                break;
            }
            const long long length = tokens[index++];
            std::vector<long long> codes;
            for (long long offset = 0; offset < length && index < tokens.size(); ++offset) {
                codes.push_back(tokens[index++]);
            }
            program.names = parse_names(codes);
            break;
        }
        if (op < 0 || op >= 53) {
            throw Error("unknown opcode " + std::to_string(op));
        }
        Instr instr;
        instr.op = static_cast<int>(op);
        if (op == 7) {
            const long long encoded = tokens[index++];
            instr.args.push_back(encoded % 2 == 0 ? encoded / 2 : -(encoded + 1) / 2);
        } else if (op == 8) {
            const long long length = tokens[index++];
            instr.args.push_back(length);
            for (long long offset = 0; offset < length && index < tokens.size(); ++offset) {
                instr.args.push_back(tokens[index++]);
            }
        } else {
            for (int offset = 0; offset < kArity[op] && index < tokens.size(); ++offset) {
                instr.args.push_back(tokens[index++]);
            }
        }
        program.instrs.push_back(std::move(instr));
    }

    // Function ranges: same rule as spacelang/parser.py (next DEF bounds a body).
    std::vector<std::size_t> definitions;
    for (std::size_t ip = 0; ip < program.instrs.size(); ++ip) {
        if (program.instrs[ip].op == 17) {
            definitions.push_back(ip);
        }
    }
    for (std::size_t position = 0; position < definitions.size(); ++position) {
        const std::size_t start = definitions[position];
        const std::size_t limit = position + 1 < definitions.size()
            ? definitions[position + 1]
            : program.instrs.size();
        std::size_t end = limit;
        for (std::size_t cursor = limit; cursor > start + 1; --cursor) {
            if (program.instrs[cursor - 1].op == 18) {
                end = cursor;
                break;
            }
        }
        program.funcs[program.instrs[start].args.at(0)] = {
            static_cast<long long>(start + 1), static_cast<long long>(end)};
    }
    return program;
}

// ---------------------------------------------------------------------- runtime
struct Frame {
    long long func_id = 0;
    long long return_ip = 0;
    std::vector<Value> locals;
    std::vector<char> initialized;
    std::vector<Value> cells;
};

class VM {
public:
    explicit VM(Program program) : program_(std::move(program)) {}

    void set_program_arguments(const std::string& path, const std::vector<std::string>& arguments);
    Value run();

private:
    Program program_;
    std::vector<Value> stack_;
    std::vector<Frame> frames_;
    std::map<std::string, Value> globals_;
    long long ip_ = 0;

    const std::string& name(long long id) const {
        const auto found = program_.names.find(id);
        if (found == program_.names.end()) {
            throw Error("unknown name id " + std::to_string(id));
        }
        return found->second;
    }

    Value pop() {
        if (stack_.empty()) {
            throw Error("stack underflow");
        }
        Value value = std::move(stack_.back());
        stack_.pop_back();
        return value;
    }

    void push(Value value) { stack_.push_back(std::move(value)); }

    std::vector<Value> pop_values(long long count) {
        if (count < 0 || static_cast<std::size_t>(count) > stack_.size()) {
            throw Error("stack underflow");
        }
        std::vector<Value> values(static_cast<std::size_t>(count));
        for (long long index = count - 1; index >= 0; --index) {
            values[static_cast<std::size_t>(index)] = pop();
        }
        return values;
    }

    void push_frame(long long func_id, std::vector<Value> locals, long long return_ip,
                    std::vector<Value> cells);

    Value call_builtin(long long func_id, std::vector<Value> args, std::map<std::string, Value> keywords);
    Value call_method(const std::string& method, Value receiver, std::vector<Value> args);
    Value binary(int op, const Value& left, const Value& right);
    Value call_value(const Value& callable, std::vector<Value> args, std::map<std::string, Value> keywords);
    std::vector<Value> bind(const FuncObj& closure, const std::vector<Value>& positional,
                            const std::map<std::string, Value>& keywords);
    Value make_iter(const Value& value);
    Value make_closure(const Instr& instr);
    Value index_value(const Value& container, const Value& key);
    void store_index(const Value& container, const Value& key, const Value& value);
};

void VM::push_frame(long long func_id, std::vector<Value> locals, long long return_ip,
                    std::vector<Value> cells) {
    Frame frame;
    frame.func_id = func_id;
    frame.return_ip = return_ip;
    frame.locals = std::move(locals);
    frame.initialized.assign(frame.locals.size(), 1);
    frame.cells = std::move(cells);
    frames_.push_back(std::move(frame));
}

Value VM::call_builtin(long long func_id, std::vector<Value> args, std::map<std::string, Value> keywords) {
    switch (func_id) {
        case 0: {  // print
            std::string separator = " ";
            std::string ending = "\n";
            if (keywords.count("sep")) {
                separator = to_text(keywords["sep"]);
            }
            if (keywords.count("end")) {
                ending = to_text(keywords["end"]);
            }
            std::string out;
            for (std::size_t index = 0; index < args.size(); ++index) {
                if (index != 0) {
                    out += separator;
                }
                out += to_text(args[index]);
            }
            out += ending;
            std::fwrite(out.data(), 1, out.size(), stdout);
            std::fflush(stdout);
            return make_nil();
        }
        case 1: {  // input
            if (!args.empty()) {
                const std::string prompt = to_text(args[0]);
                std::fwrite(prompt.data(), 1, prompt.size(), stdout);
                std::fflush(stdout);
            }
            std::string line;
            if (!std::getline(std::cin, line)) {
                throw Error("EOF while reading input");
            }
            return make_str(line);
        }
        case 2:
            return make_int(static_cast<long long>(length_of(args.at(0))));
        case 3: {
            const Value& source = args.at(0);
            if (source.tag == Tag::Int) {
                return source;
            }
            if (source.tag == Tag::Float) {
                return make_int(static_cast<long long>(source.f));
            }
            if (source.tag == Tag::Bool) {
                return make_int(source.b ? 1 : 0);
            }
            if (source.tag == Tag::Str) {
                const std::string& text = as_str(source).text;
                std::size_t used = 0;
                const long long value = std::stoll(text, &used, 0);
                if (used != text.size()) {
                    throw Error("invalid literal for int(): " + quote_string(text));
                }
                return make_int(value);
            }
            throw Error("int() cannot convert this value");
        }
        case 4:
            if (args.at(0).tag == Tag::Str) {
                return make_float(std::stod(as_str(args.at(0)).text));
            }
            return make_float(as_double(args.at(0)));
        case 5:
            return make_str(to_text(args.at(0)));
        case 6:
            return make_bool(truthy(args.at(0)));
        case 7:
            if (args.at(0).tag == Tag::Int || args.at(0).tag == Tag::Bool) {
                return make_int(std::llabs(as_int(args.at(0))));
            }
            return make_float(std::fabs(as_double(args.at(0))));
        case 8: {  // range
            if (args.empty() || args.size() > 3) {
                throw Error("range() takes 1 to 3 arguments");
            }
            long long start = 0;
            long long stop = 0;
            long long step = 1;
            if (args.size() == 1) {
                stop = as_int(args[0]);
            } else {
                start = as_int(args[0]);
                stop = as_int(args[1]);
                if (args.size() == 3) {
                    step = as_int(args[2]);
                }
            }
            if (step == 0) {
                throw Error("range() step must not be zero");
            }
            return make_range(start, stop, step);
        }
        case 9: {  // type: the subset has no type objects, so report a name
            switch (args.at(0).tag) {
                case Tag::Nil: return make_str("NoneType");
                case Tag::Bool: return make_str("bool");
                case Tag::Int: return make_str("int");
                case Tag::Float: return make_str("float");
                case Tag::Str: return make_str("str");
                case Tag::List: return make_str("list");
                case Tag::Tuple: return make_str("tuple");
                case Tag::Dict: return make_str("dict");
                case Tag::Set: return make_str("set");
                case Tag::Range: return make_str("range");
                case Tag::File: return make_str("TextIOWrapper");
                default: return make_str("object");
            }
        }
        case 10: {  // open(path, mode="r")
            if (args.empty()) {
                throw Error("open() requires a path");
            }
            const std::string path = as_str(args.at(0)).text;
            std::string mode = "r";
            if (args.size() > 1) {
                mode = as_str(args.at(1)).text;
            }
            std::string c_mode = "rb";
            if (mode.find('a') != std::string::npos) {
                c_mode = "ab";
            } else if (mode.find('w') != std::string::npos) {
                c_mode = "wb";
            }
            std::FILE* handle = std::fopen(path.c_str(), c_mode.c_str());
            if (handle == nullptr) {
                throw Error("cannot open " + path);
            }
            auto file = std::make_shared<FileObj>();
            file->handle = handle;
            Value result;
            result.tag = Tag::File;
            result.obj = file;
            return result;
        }
        case 13:
            return make_bool(args.at(0).tag == Tag::Func || args.at(0).tag == Tag::Range);
        case 14:
            return make_str(repr(args.at(0)));
        case 16: {  // set
            std::vector<Value> items;
            if (!args.empty()) {
                const std::vector<Value> source = args[0].tag == Tag::Set
                    ? as_set(args[0]).items
                    : as_iter(make_iter(args[0])).items;
                for (const Value& item : source) {
                    bool seen = false;
                    for (const Value& existing : items) {
                        if (values_equal(existing, item)) {
                            seen = true;
                            break;
                        }
                    }
                    if (!seen) {
                        items.push_back(item);
                    }
                }
            }
            Value result = make_set();
            as_set(result).items = std::move(items);
            return result;
        }
        default:
            throw Error("unsupported builtin " + std::to_string(func_id));
    }
}

Value VM::call_method(const std::string& method, Value receiver, std::vector<Value> args) {
    if (receiver.tag == Tag::Str) {
        const std::string& text = as_str(receiver).text;
        if (method == "upper" || method == "lower") {
            std::string out = text;
            for (char& character : out) {
                character = method == "upper"
                    ? static_cast<char>(std::toupper(static_cast<unsigned char>(character)))
                    : static_cast<char>(std::tolower(static_cast<unsigned char>(character)));
            }
            return make_str(out);
        }
        if (method == "strip") {
            std::size_t begin = 0;
            std::size_t end = text.size();
            while (begin < end && std::isspace(static_cast<unsigned char>(text[begin]))) {
                ++begin;
            }
            while (end > begin && std::isspace(static_cast<unsigned char>(text[end - 1]))) {
                --end;
            }
            return make_str(text.substr(begin, end - begin));
        }
        if (method == "join") {
            const Value& parts = args.at(0);
            std::vector<Value> items = as_iter(make_iter(parts)).items;
            std::string out;
            for (std::size_t index = 0; index < items.size(); ++index) {
                if (index != 0) {
                    out += text;
                }
                if (items[index].tag != Tag::Str) {
                    throw Error("join() requires strings");
                }
                out += as_str(items[index]).text;
            }
            return make_str(out);
        }
        if (method == "split") {
            std::string separator = " ";
            if (!args.empty()) {
                separator = as_str(args.at(0)).text;
            }
            std::vector<Value> parts;
            if (separator.empty()) {
                for (const char character : text) {
                    parts.push_back(make_str(std::string(1, character)));
                }
                return make_list(parts);
            }
            std::size_t start = 0;
            while (true) {
                const std::size_t found = text.find(separator, start);
                if (found == std::string::npos) {
                    parts.push_back(make_str(text.substr(start)));
                    break;
                }
                parts.push_back(make_str(text.substr(start, found - start)));
                start = found + separator.size();
            }
            return make_list(parts);
        }
        if (method == "startswith") {
            const std::string& prefix = as_str(args.at(0)).text;
            return make_bool(text.compare(0, prefix.size(), prefix) == 0);
        }
        if (method == "endswith") {
            const std::string& suffix = as_str(args.at(0)).text;
            return make_bool(text.size() >= suffix.size()
                && text.compare(text.size() - suffix.size(), suffix.size(), suffix) == 0);
        }
        if (method == "replace") {
            const std::string& from = as_str(args.at(0)).text;
            const std::string& to = as_str(args.at(1)).text;
            if (from.empty()) {
                return make_str(text);
            }
            std::string out;
            std::size_t start = 0;
            while (true) {
                const std::size_t found = text.find(from, start);
                if (found == std::string::npos) {
                    out += text.substr(start);
                    break;
                }
                out += text.substr(start, found - start) + to;
                start = found + from.size();
            }
            return make_str(out);
        }
        if (method == "format") {
            std::string out;
            std::size_t auto_index = 0;
            for (std::size_t index = 0; index < text.size(); ++index) {
                if (text[index] == '{' && index + 1 < text.size() && text[index + 1] == '}') {
                    if (auto_index >= args.size()) {
                        throw Error("not enough arguments for format()");
                    }
                    out += to_text(args[auto_index++]);
                    ++index;
                } else if (text[index] == '{' && index + 1 < text.size() && text[index + 1] == '!') {
                    const std::size_t close = text.find('}', index);
                    if (close == std::string::npos || auto_index >= args.size()) {
                        throw Error("bad format() replacement field");
                    }
                    const char conversion = text[index + 2];
                    out += conversion == 'r' ? repr(args[auto_index++]) : to_text(args[auto_index++]);
                    index = close;
                } else {
                    out += text[index];
                }
            }
            return make_str(out);
        }
        throw Error("unsupported str method '" + method + "'");
    }
    if (receiver.tag == Tag::List) {
        ListObj& list = as_list(receiver);
        if (method == "append") {
            list.items.push_back(args.at(0));
            return make_nil();
        }
        if (method == "extend") {
            std::vector<Value> items = as_iter(make_iter(args.at(0))).items;
            list.items.insert(list.items.end(), items.begin(), items.end());
            return make_nil();
        }
        if (method == "pop") {
            if (list.items.empty()) {
                throw Error("pop from empty list");
            }
            long long position = static_cast<long long>(list.items.size()) - 1;
            if (!args.empty()) {
                position = as_int(args[0]);
                if (position < 0) {
                    position += static_cast<long long>(list.items.size());
                }
            }
            if (position < 0 || position >= static_cast<long long>(list.items.size())) {
                throw Error("pop index out of range");
            }
            Value value = list.items[static_cast<std::size_t>(position)];
            list.items.erase(list.items.begin() + position);
            return value;
        }
        if (method == "reverse") {
            std::reverse(list.items.begin(), list.items.end());
            return make_nil();
        }
        if (method == "index") {
            for (std::size_t index = 0; index < list.items.size(); ++index) {
                if (values_equal(list.items[index], args.at(0))) {
                    return make_int(static_cast<long long>(index));
                }
            }
            throw Error("value is not in list");
        }
        if (method == "insert") {
            const long long position = as_int(args.at(0));
            list.items.insert(list.items.begin() + position, args.at(1));
            return make_nil();
        }
        throw Error("unsupported list method '" + method + "'");
    }
    if (receiver.tag == Tag::Dict) {
        DictObj& dict = as_dict(receiver);
        if (method == "keys" || method == "values" || method == "items") {
            std::vector<Value> out;
            for (const auto& item : dict.items) {
                if (method == "keys") {
                    out.push_back(item.first);
                } else if (method == "values") {
                    out.push_back(item.second);
                } else {
                    out.push_back(make_tuple({item.first, item.second}));
                }
            }
            return make_list(out);
        }
        if (method == "get") {
            if (const Value* found = dict_find(dict, args.at(0))) {
                return *found;
            }
            return args.size() > 1 ? args[1] : make_nil();
        }
        if (method == "update") {
            Value source = args.at(0);
            if (source.tag == Tag::Dict) {
                for (const auto& item : as_dict(source).items) {
                    dict_set(dict, item.first, item.second);
                }
            }
            return make_nil();
        }
        throw Error("unsupported dict method '" + method + "'");
    }
    if (receiver.tag == Tag::Set) {
        SetObj& set = as_set(receiver);
        if (method == "add") {
            for (const Value& existing : set.items) {
                if (values_equal(existing, args.at(0))) {
                    return make_nil();
                }
            }
            set.items.push_back(args.at(0));
            return make_nil();
        }
        throw Error("unsupported set method '" + method + "'");
    }
    if (receiver.tag == Tag::File) {
        FileObj& file = as_file(receiver);
        if (method == "close") {
            if (file.handle != nullptr) {
                std::fclose(file.handle);
                file.handle = nullptr;
            }
            file.closed = true;
            return make_nil();
        }
        if (file.handle == nullptr) {
            throw Error("I/O operation on a closed file");
        }
        if (method == "flush") {
            std::fflush(file.handle);
            return make_nil();
        }
        if (method == "write") {
            const std::string& text = as_str(args.at(0)).text;
            const std::size_t written = std::fwrite(text.data(), 1, text.size(), file.handle);
            std::fflush(file.handle);
            return make_int(static_cast<long long>(written));
        }
        if (method == "read" || method == "readline") {
            std::string text;
            char buffer[4096];
            if (method == "readline") {
                while (true) {
                    const int next = std::fgetc(file.handle);
                    if (next == EOF) {
                        break;
                    }
                    text += static_cast<char>(next);
                    if (next == '\n') {
                        break;
                    }
                }
                return make_str(text);
            }
            long long remaining = -1;
            if (!args.empty()) {
                remaining = as_int(args[0]);
            }
            while (remaining != 0) {
                const std::size_t wanted = remaining < 0
                    ? sizeof(buffer)
                    : static_cast<std::size_t>(std::min<long long>(remaining, static_cast<long long>(sizeof(buffer))));
                const std::size_t got = std::fread(buffer, 1, wanted, file.handle);
                if (got == 0) {
                    break;
                }
                text.append(buffer, got);
                if (remaining > 0) {
                    remaining -= static_cast<long long>(got);
                }
            }
            return make_str(text);
        }
        throw Error("unsupported file method '" + method + "'");
    }
    throw Error("cannot call method '" + method + "' on this value");
}

Value VM::binary(int op, const Value& left, const Value& right) {
    if (op == 6) return make_bool(values_equal(left, right));
    if (op == 9) return make_bool(!values_equal(left, right));
    if (op == 7) return make_bool(compare_values(left, right) < 0);
    if (op == 8) return make_bool(compare_values(left, right) > 0);
    if (op == 10) return make_bool(compare_values(left, right) <= 0);
    if (op == 11) return make_bool(compare_values(left, right) >= 0);
    if (op == 12 || op == 13) {
        bool found = false;
        switch (right.tag) {
            case Tag::Str:
                found = to_text(left).find(as_str(right).text) != std::string::npos;
                break;
            case Tag::List: for (const Value& item : as_list(right).items) found = found || values_equal(item, left); break;
            case Tag::Tuple: for (const Value& item : as_tuple(right).items) found = found || values_equal(item, left); break;
            case Tag::Dict: found = dict_find(as_dict(right), left) != nullptr; break;
            case Tag::Set: for (const Value& item : as_set(right).items) found = found || values_equal(item, left); break;
            case Tag::Range: break;
            default: throw Error("'in' is not supported for this value");
        }
        return make_bool(op == 12 ? found : !found);
    }
    if (op == 14 || op == 15) {
        bool identical = false;
        if (left.tag != right.tag) {
            identical = false;  // 0 is None must be False: compare tags first
        } else if (left.tag == Tag::Nil) {
            identical = true;
        } else if (left.tag == Tag::Bool) {
            identical = left.b == right.b;
        } else if (left.tag == Tag::Int) {
            identical = left.i == right.i;
        } else if (left.tag == Tag::Float) {
            identical = left.f == right.f;
        } else {
            identical = left.obj == right.obj;
        }
        return make_bool(op == 14 ? identical : !identical);
    }
    if (left.tag == Tag::Str && right.tag == Tag::Str) {
        if (op == 1) {
            return make_str(as_str(left).text + as_str(right).text);
        }
    }
    if (left.tag == Tag::List && right.tag == Tag::List && op == 1) {
        std::vector<Value> merged = as_list(left).items;
        merged.insert(merged.end(), as_list(right).items.begin(), as_list(right).items.end());
        return make_list(merged);
    }
    if ((left.tag == Tag::Str || left.tag == Tag::List) && is_number(right) && op == 3) {
        const long long count = as_int(right);
        if (left.tag == Tag::Str) {
            std::string text;
            for (long long index = 0; index < count; ++index) {
                text += as_str(left).text;
            }
            return make_str(text);
        }
        std::vector<Value> repeated;
        for (long long index = 0; index < count; ++index) {
            repeated.insert(repeated.end(), as_list(left).items.begin(), as_list(left).items.end());
        }
        return make_list(repeated);
    }
    if (!is_number(left) || !is_number(right)) {
        throw Error("unsupported operands for arithmetic");
    }
    if (left.tag == Tag::Int && right.tag == Tag::Int) {
        const long long first = left.i;
        const long long second = right.i;
        switch (op) {
            case 1: return make_int(first + second);
            case 2: return make_int(first - second);
            case 3: return make_int(first * second);
            case 16:
                if (second == 0) throw Error("integer division by zero");
                return make_int(floor_div(first, second));
            case 5:
                if (second == 0) throw Error("integer modulo by zero");
                return make_int(floor_mod(first, second));
            case 17: {
                long long result = 1;
                long long base = first;
                long long exponent = second;
                if (exponent < 0) {
                    return make_float(std::pow(static_cast<double>(first), static_cast<double>(second)));
                }
                while (exponent > 0) {
                    if (exponent & 1) result *= base;
                    base *= base;
                    exponent >>= 1;
                }
                return make_int(result);
            }
            default: break;
        }
    }
    const double first = as_double(left);
    const double second = as_double(right);
    switch (op) {
        case 1: return make_float(first + second);
        case 2: return make_float(first - second);
        case 3: return make_float(first * second);
        case 4:
            if (second == 0.0) throw Error("float division by zero");
            return make_float(first / second);
        case 16:
            if (second == 0.0) throw Error("float floor division by zero");
            return make_float(std::floor(first / second));
        case 5:
            if (second == 0.0) throw Error("float modulo by zero");
            return make_float(first - second * std::floor(first / second));
        case 17:
            return make_float(std::pow(first, second));
        default:
            throw Error("unsupported numeric operation");
    }
}

Value VM::make_iter(const Value& value) {
    auto iterator = std::make_shared<IterObj>();
    switch (value.tag) {
        case Tag::List: iterator->items = as_list(value).items; break;
        case Tag::Tuple: iterator->items = as_tuple(value).items; break;
        case Tag::Str: {
            const std::string& text = as_str(value).text;
            for (std::size_t index = 0; index < text.size();) {
                const unsigned char lead = static_cast<unsigned char>(text[index]);
                std::size_t width = lead < 0x80 ? 1 : (lead < 0xE0 ? 2 : (lead < 0xF0 ? 3 : 4));
                if (index + width > text.size()) {
                    width = 1;
                }
                iterator->items.push_back(make_str(text.substr(index, width)));
                index += width;
            }
            break;
        }
        case Tag::Dict: for (const auto& item : as_dict(value).items) iterator->items.push_back(item.first); break;
        case Tag::Set: iterator->items = as_set(value).items; break;
        case Tag::Range: {
            const RangeObj& range = as_range(value);
            if (range.step > 0) {
                for (long long cursor = range.start; cursor < range.stop; cursor += range.step) {
                    iterator->items.push_back(make_int(cursor));
                }
            } else {
                for (long long cursor = range.start; cursor > range.stop; cursor += range.step) {
                    iterator->items.push_back(make_int(cursor));
                }
            }
            break;
        }
        default:
            throw Error("value is not iterable");
    }
    Value result;
    result.tag = Tag::Iter;
    result.obj = iterator;
    return result;
}

Value VM::index_value(const Value& container, const Value& key) {
    if (container.tag == Tag::Dict) {
        if (key.tag == Tag::Slice) {
            throw Error("dictionaries cannot be sliced");
        }
        if (const Value* found = dict_find(as_dict(container), key)) {
            return *found;
        }
        throw Error("key not found: " + repr(key));
    }
    if (key.tag == Tag::Slice) {
        std::vector<Value> source;
        if (container.tag == Tag::Str) {
            source = as_iter(make_iter(container)).items;
        } else if (container.tag == Tag::List) {
            source = as_list(container).items;
        } else if (container.tag == Tag::Tuple) {
            source = as_tuple(container).items;
        } else {
            throw Error("this value cannot be sliced");
        }
        std::vector<Value> picked = slice_vector(source, as_slice(key));
        if (container.tag == Tag::Str) {
            std::string text;
            for (const Value& item : picked) {
                text += as_str(item).text;
            }
            return make_str(text);
        }
        return container.tag == Tag::Tuple ? make_tuple(picked) : make_list(picked);
    }
    if (key.tag == Tag::Int) {
        long long position = key.i;
        if (container.tag == Tag::Str || container.tag == Tag::List || container.tag == Tag::Tuple) {
            const long long size = static_cast<long long>(length_of(container));
            if (position < 0) {
                position += size;
            }
            if (position < 0 || position >= size) {
                throw Error("index out of range");
            }
            if (container.tag == Tag::Str) {
                std::vector<Value> characters = as_iter(make_iter(container)).items;
                return characters[static_cast<std::size_t>(position)];
            }
            return container.tag == Tag::List
                ? as_list(container).items[static_cast<std::size_t>(position)]
                : as_tuple(container).items[static_cast<std::size_t>(position)];
        }
        if (container.tag == Tag::Range) {
            const RangeObj& range = as_range(container);
            return make_int(range.start + position * range.step);
        }
    }
    throw Error("unsupported index operation");
}

void VM::store_index(const Value& container, const Value& key, const Value& value) {
    if (container.tag == Tag::Dict) {
        dict_set(as_dict(container), key, value);
        return;
    }
    if (container.tag == Tag::List) {
        if (key.tag != Tag::Int) {
            throw Error("list indices must be integers");
        }
        long long position = key.i;
        const long long size = static_cast<long long>(as_list(container).items.size());
        if (position < 0) {
            position += size;
        }
        if (position < 0 || position >= size) {
            throw Error("list assignment index out of range");
        }
        as_list(container).items[static_cast<std::size_t>(position)] = value;
        return;
    }
    throw Error("item assignment is not supported for this value");
}

Value VM::call_value(const Value& callable, std::vector<Value> args,
                     std::map<std::string, Value> keywords) {
    if (callable.tag != Tag::Func) {
        throw Error("value is not callable");
    }
    FuncObj& closure = as_func(callable);
    std::vector<Value> locals = bind(closure, args, keywords);
    const auto found = program_.funcs.find(closure.func_id);
    if (found == program_.funcs.end()) {
        throw Error("undefined user function " + std::to_string(closure.func_id));
    }
    push_frame(closure.func_id, std::move(locals), ip_ + 1, closure.cells);
    ip_ = found->second.first;
    return make_nil();
}

std::vector<Value> VM::bind(const FuncObj& closure, const std::vector<Value>& positional,
                            const std::map<std::string, Value>& keywords) {
    if (closure.positional_count < 0) {  // legacy MAKE_CLOSURE
        if (!keywords.empty()) {
            throw Error("keyword arguments are unavailable for this closure");
        }
        if (static_cast<long long>(positional.size()) != closure.legacy_arg_count) {
            throw Error("wrong number of arguments");
        }
        return positional;
    }
    const long long positional_count = closure.positional_count;
    if (closure.vararg_name.empty() && static_cast<long long>(positional.size()) > positional_count) {
        throw Error("too many positional arguments");
    }
    std::vector<Value> bound(closure.params.size());
    std::vector<char> assigned(closure.params.size(), 0);
    const long long assigned_positional =
        std::min(static_cast<long long>(positional.size()), positional_count);
    for (long long index = 0; index < assigned_positional; ++index) {
        bound[static_cast<std::size_t>(index)] = positional[static_cast<std::size_t>(index)];
        assigned[static_cast<std::size_t>(index)] = 1;
    }
    std::map<std::string, Value> extra;
    for (const auto& keyword : keywords) {
        std::size_t index = 0;
        while (index < closure.params.size() && closure.params[index] != keyword.first) {
            ++index;
        }
        if (index == closure.params.size()) {
            if (closure.kwarg_name.empty()) {
                throw Error("unexpected keyword argument '" + keyword.first + "'");
            }
            extra[keyword.first] = keyword.second;
            continue;
        }
        if (static_cast<long long>(index) < closure.positional_only_count) {
            if (closure.kwarg_name.empty()) {
                throw Error("positional-only argument passed as keyword");
            }
            extra[keyword.first] = keyword.second;
            continue;
        }
        if (assigned[index]) {
            throw Error("multiple values for argument '" + keyword.first + "'");
        }
        bound[index] = keyword.second;
        assigned[index] = 1;
    }
    for (std::size_t index = 0; index < closure.params.size(); ++index) {
        if (!assigned[index]) {
            const auto found = closure.defaults.find(closure.params[index]);
            if (found == closure.defaults.end()) {
                throw Error("missing required argument '" + closure.params[index] + "'");
            }
            bound[index] = found->second;
        }
    }
    std::vector<Value> locals_result = bound;
    if (!closure.vararg_name.empty()) {
        std::vector<Value> rest;
        for (std::size_t index = static_cast<std::size_t>(assigned_positional);
             index < positional.size(); ++index) {
            rest.push_back(positional[index]);
        }
        locals_result.push_back(make_tuple(rest));
    }
    if (!closure.kwarg_name.empty()) {
        Value mapping = make_dict();
        for (const auto& item : extra) {
            dict_set(as_dict(mapping), make_str(item.first), item.second);
        }
        locals_result.push_back(mapping);
    }
    return locals_result;
}

Value VM::make_closure(const Instr& instr) {
    auto closure = std::make_shared<FuncObj>();
    closure->func_id = instr.args.at(0);
    const long long cell_count = instr.args.at(1);

    if (instr.op == 36) {  // MAKE_CLOSURE: func_id, nfree, nargs (cells only)
        closure->legacy_arg_count = instr.args.at(2);
        closure->cells = pop_values(cell_count);
        Value result;
        result.tag = Tag::Func;
        result.obj = closure;
        return result;
    }

    long long positional_count = 0;
    long long keyword_only_count = 0;
    long long positional_defaults = 0;
    long long keyword_defaults = 0;
    bool has_varargs = false;
    bool has_kwargs = false;
    if (instr.op == 41) {  // MAKE_CLOSURE_SIG: func, nfree, nparams, ndefaults
        positional_count = instr.args.at(2);
        positional_defaults = instr.args.at(3);
    } else if (instr.op == 42) {  // KWONLY: func, nfree, npos, nkwonly, ndef, nkwdef
        positional_count = instr.args.at(2);
        keyword_only_count = instr.args.at(3);
        positional_defaults = instr.args.at(4);
        keyword_defaults = instr.args.at(5);
    } else {  // ARGS (43) or POSONLY (49)
        const std::size_t base = instr.op == 49 ? 1 : 0;
        if (base == 1) {
            closure->positional_only_count = instr.args.at(2);
        }
        positional_count = instr.args.at(2 + base);
        keyword_only_count = instr.args.at(3 + base);
        positional_defaults = instr.args.at(4 + base);
        keyword_defaults = instr.args.at(5 + base);
        has_varargs = instr.args.at(6 + base) == 1;
        has_kwargs = instr.args.at(7 + base) == 1;
    }
    if (has_kwargs) {
        closure->kwarg_name = name(pop().i);
    }
    if (has_varargs) {
        closure->vararg_name = name(pop().i);
    }
    for (long long index = 0; index < keyword_defaults; ++index) {
        Value value = pop();
        const long long name_id = pop().i;
        closure->defaults[name(name_id)] = value;
    }
    std::vector<Value> defaults = pop_values(positional_defaults);
    std::vector<std::string> parameters;
    parameters.reserve(static_cast<std::size_t>(positional_count + keyword_only_count));
    for (long long index = 0; index < positional_count + keyword_only_count; ++index) {
        parameters.push_back(name(pop().i));
    }
    std::reverse(parameters.begin(), parameters.end());
    closure->params = parameters;
    closure->positional_count = positional_count;
    for (long long index = 0; index < positional_defaults; ++index) {
        const std::size_t parameter_index =
            static_cast<std::size_t>(positional_count - positional_defaults + index);
        closure->defaults[parameters[parameter_index]] = defaults[static_cast<std::size_t>(index)];
    }
    // Free cells were pushed first, so they are popped last.
    closure->cells = pop_values(cell_count);
    Value result;
    result.tag = Tag::Func;
    result.obj = closure;
    return result;
}

void VM::set_program_arguments(const std::string& path, const std::vector<std::string>& arguments) {
    std::vector<Value> argv;
    argv.push_back(make_str(path));
    for (const std::string& argument : arguments) {
        argv.push_back(make_str(argument));
    }
    globals_["__file__"] = make_str(path);
    globals_["__argv__"] = make_list(argv);
}

Value VM::run() {
    Value return_value;
    while (ip_ >= 0 && ip_ < static_cast<long long>(program_.instrs.size())) {
        const Instr& instr = program_.instrs[static_cast<std::size_t>(ip_)];
        switch (instr.op) {
            case 0:  // NOP
                ++ip_;
                break;
            case 7:  // PUSH_INT
                push(make_int(instr.args.at(0)));
                ++ip_;
                break;
            case 8: {  // PUSH_STR
                std::string text;
                for (std::size_t index = 1; index < instr.args.size(); ++index) {
                    append_utf8(text, static_cast<std::uint32_t>(instr.args[index]));
                }
                push(make_str(text));
                ++ip_;
                break;
            }
            case 35:  // PUSH_NONE
                push(make_nil());
                ++ip_;
                break;
            case 9: {  // LOAD_GLOBAL
                const auto found = globals_.find(name(instr.args.at(0)));
                if (found == globals_.end()) {
                    throw Error("undefined global " + name(instr.args.at(0)));
                }
                push(found->second);
                ++ip_;
                break;
            }
            case 10:  // STORE_GLOBAL
                globals_[name(instr.args.at(0))] = pop();
                ++ip_;
                break;
            case 5:  // OP
                {
                    Value right = pop();
                    Value left = pop();
                    push(binary(static_cast<int>(instr.args.at(0)), left, right));
                }
                ++ip_;
                break;
            case 6: {  // STACK
                const long long which = instr.args.at(0);
                if (which == 1) {
                    if (stack_.empty()) throw Error("dup requires 1 value");
                    push(stack_.back());
                } else if (which == 2) {
                    Value first = pop();
                    Value second = pop();
                    push(first);
                    push(second);
                } else if (which == 3) {
                    if (stack_.empty()) throw Error("drop requires 1 value");
                    stack_.pop_back();
                } else if (which == 4) {
                    if (stack_.size() < 2) throw Error("over requires 2 values");
                    push(stack_[stack_.size() - 2]);
                } else if (which == 5) {
                    Value third = pop();
                    Value second = pop();
                    Value first = pop();
                    push(second);
                    push(third);
                    push(first);
                } else {
                    throw Error("unsupported stack operation");
                }
                ++ip_;
                break;
            }
            case 22:  // JMP
                ip_ = instr.args.at(0);
                break;
            case 23:  // JZ
                ip_ = truthy(pop()) ? ip_ + 1 : instr.args.at(0);
                break;
            case 24:  // JNZ
                ip_ = truthy(pop()) ? instr.args.at(0) : ip_ + 1;
                break;
            case 1: {  // CALL
                const long long func_id = instr.args.at(0);
                std::vector<Value> args = pop_values(instr.args.at(1));
                if (func_id >= 10000) {
                    const auto found = program_.funcs.find(func_id);
                    if (found == program_.funcs.end()) {
                        throw Error("undefined function " + std::to_string(func_id));
                    }
                    push_frame(func_id, std::move(args), ip_ + 1, {});
                    ip_ = found->second.first;
                } else {
                    push(call_builtin(func_id, std::move(args), {}));
                    ++ip_;
                }
                break;
            }
            case 2: {  // CALL_KW (builtins only, like the reference VM)
                const long long func_id = instr.args.at(0);
                std::vector<Value> positional = pop_values(instr.args.at(1));
                std::map<std::string, Value> keywords;
                for (long long index = 0; index < instr.args.at(2); ++index) {
                    Value value = pop();
                    keywords[name(pop().i)] = value;
                }
                if (func_id >= 10000) {
                    throw Error("CALL_KW is not supported for user functions");
                }
                push(call_builtin(func_id, std::move(positional), std::move(keywords)));
                ++ip_;
                break;
            }
            case 3: {  // CALL_OBJ
                std::vector<Value> args = pop_values(instr.args.at(0));
                Value callable = pop();
                if (callable.tag == Tag::Func) {
                    call_value(callable, std::move(args), {});
                } else if (callable.tag == Tag::Range) {
                    push(callable);
                    ++ip_;
                } else {
                    throw Error("value is not callable");
                }
                break;
            }
            case 40: {  // CALL_OBJ_KW
                std::vector<Value> args = pop_values(instr.args.at(0));
                std::map<std::string, Value> keywords;
                for (long long index = 0; index < instr.args.at(1); ++index) {
                    Value value = pop();
                    keywords[name(pop().i)] = value;
                }
                Value callable = pop();
                call_value(callable, std::move(args), std::move(keywords));
                break;
            }
            case 45: {  // CALL_OBJ_EX
                Value keyword_object = pop();
                Value positional_object = pop();
                Value callable = pop();
                std::vector<Value> args = as_iter(make_iter(positional_object)).items;
                std::map<std::string, Value> keywords;
                for (const auto& item : as_dict(keyword_object).items) {
                    keywords[as_str(item.first).text] = item.second;
                }
                call_value(callable, std::move(args), std::move(keywords));
                break;
            }
            case 46: {  // CALL_BUILTIN_EX
                Value keyword_object = pop();
                Value positional_object = pop();
                std::vector<Value> args = as_iter(make_iter(positional_object)).items;
                std::map<std::string, Value> keywords;
                for (const auto& item : as_dict(keyword_object).items) {
                    keywords[as_str(item.first).text] = item.second;
                }
                push(call_builtin(instr.args.at(0), std::move(args), std::move(keywords)));
                ++ip_;
                break;
            }
            case 12: {  // CALL_METHOD
                std::vector<Value> args = pop_values(instr.args.at(1));
                Value receiver = pop();
                push(call_method(name(instr.args.at(0)), receiver, std::move(args)));
                ++ip_;
                break;
            }
            case 11:  // GET_ATTR
                throw Error("attribute access is not supported by the native runner");
            case 13: {  // INDEX
                Value key = pop();
                Value container = pop();
                push(index_value(container, key));
                ++ip_;
                break;
            }
            case 33: {  // STORE_INDEX
                Value key = pop();
                Value container = pop();
                Value value = pop();
                store_index(container, key, value);
                ++ip_;
                break;
            }
            case 32:  // STORE_ATTR
                throw Error("attribute assignment is not supported by the native runner");
            case 14:  // BUILD_LIST
                push(make_list(pop_values(instr.args.at(0))));
                ++ip_;
                break;
            case 15:  // BUILD_TUPLE
                push(make_tuple(pop_values(instr.args.at(0))));
                ++ip_;
                break;
            case 44: {  // BUILD_DICT
                std::vector<Value> flat = pop_values(instr.args.at(0) * 2);
                Value dict = make_dict();
                for (std::size_t index = 0; index + 1 < flat.size(); index += 2) {
                    dict_set(as_dict(dict), flat[index], flat[index + 1]);
                }
                push(dict);
                ++ip_;
                break;
            }
            case 51: {  // BUILD_SET
                std::vector<Value> items = pop_values(instr.args.at(0));
                Value set = make_set();
                for (const Value& item : items) {
                    bool seen = false;
                    for (const Value& existing : as_set(set).items) {
                        if (values_equal(existing, item)) {
                            seen = true;
                            break;
                        }
                    }
                    if (!seen) {
                        as_set(set).items.push_back(item);
                    }
                }
                push(set);
                ++ip_;
                break;
            }
            case 16: {  // CONCAT
                std::vector<Value> values = pop_values(instr.args.at(0));
                if (values.empty()) {
                    push(make_str(""));
                    break;
                }
                const Tag kind = values[0].tag;
                for (const Value& value : values) {
                    if (value.tag != kind) {
                        throw Error("CONCAT requires homogeneous types");
                    }
                }
                if (kind == Tag::Str) {
                    std::string text;
                    for (const Value& value : values) {
                        text += as_str(value).text;
                    }
                    push(make_str(text));
                } else if (kind == Tag::List || kind == Tag::Tuple) {
                    std::vector<Value> merged;
                    for (const Value& value : values) {
                        const std::vector<Value>& items = kind == Tag::List
                            ? as_list(value).items : as_tuple(value).items;
                        merged.insert(merged.end(), items.begin(), items.end());
                    }
                    push(kind == Tag::List ? make_list(merged) : make_tuple(merged));
                } else {
                    throw Error("CONCAT requires strings, lists or tuples");
                }
                ++ip_;
                break;
            }
            case 17: {  // DEF
                const auto found = program_.funcs.find(instr.args.at(0));
                ip_ = found == program_.funcs.end() ? ip_ + 1 : found->second.second;
                break;
            }
            case 18: {  // RET
                Value value = pop();
                if (frames_.empty()) {
                    return value;
                }
                const long long return_ip = frames_.back().return_ip;
                frames_.pop_back();
                push(value);
                ip_ = return_ip;
                break;
            }
            case 20: {  // LOAD_LOCAL
                if (frames_.empty()) throw Error("LOAD_LOCAL outside function");
                Frame& frame = frames_.back();
                const std::size_t slot = static_cast<std::size_t>(instr.args.at(0));
                if (slot >= frame.locals.size() || !frame.initialized[slot]) {
                    throw Error("undefined local slot " + std::to_string(slot));
                }
                const Value& local = frame.locals[slot];
                if (local.tag == Tag::Cell) {
                    CellObj& cell = as_cell(local);
                    if (!cell.initialized) {
                        throw Error("undefined local slot " + std::to_string(slot));
                    }
                    push(cell.value);
                } else {
                    push(local);
                }
                ++ip_;
                break;
            }
            case 19: {  // LOAD_ARG
                if (frames_.empty()) throw Error("LOAD_ARG outside function");
                Frame& frame = frames_.back();
                const std::size_t slot = static_cast<std::size_t>(instr.args.at(0));
                if (slot >= frame.locals.size()) {
                    throw Error("undefined argument slot " + std::to_string(slot));
                }
                push(frame.locals[slot]);
                ++ip_;
                break;
            }
            case 21: {  // STORE_LOCAL
                if (frames_.empty()) throw Error("STORE_LOCAL outside function");
                Frame& frame = frames_.back();
                const std::size_t slot = static_cast<std::size_t>(instr.args.at(0));
                while (frame.locals.size() <= slot) {
                    frame.locals.push_back(make_nil());
                    frame.initialized.push_back(0);
                }
                Value value = pop();
                if (frame.initialized[slot] && frame.locals[slot].tag == Tag::Cell) {
                    CellObj& cell = as_cell(frame.locals[slot]);
                    cell.value = value;
                    cell.initialized = true;
                } else {
                    frame.locals[slot] = value;
                }
                frame.initialized[slot] = 1;
                ++ip_;
                break;
            }
            case 37: {  // CELLIFY
                if (frames_.empty()) throw Error("CELLIFY outside function");
                Frame& frame = frames_.back();
                const std::size_t slot = static_cast<std::size_t>(instr.args.at(0));
                while (frame.locals.size() <= slot) {
                    frame.locals.push_back(make_nil());
                    frame.initialized.push_back(0);
                }
                if (frame.locals[slot].tag != Tag::Cell) {
                    auto cell = std::make_shared<CellObj>();
                    cell->value = frame.locals[slot];
                    cell->initialized = frame.initialized[slot] != 0;
                    Value wrapped;
                    wrapped.tag = Tag::Cell;
                    wrapped.obj = cell;
                    frame.locals[slot] = wrapped;
                }
                frame.initialized[slot] = 1;
                ++ip_;
                break;
            }
            case 38: {  // LOAD_CELL_REF
                if (frames_.empty()) throw Error("LOAD_CELL_REF outside function");
                Frame& frame = frames_.back();
                const std::size_t slot = static_cast<std::size_t>(instr.args.at(0));
                if (slot >= frame.locals.size() || frame.locals[slot].tag != Tag::Cell) {
                    throw Error("local slot is not a cell");
                }
                push(frame.locals[slot]);
                ++ip_;
                break;
            }
            case 39: {  // LOAD_DEREF
                if (frames_.empty()) throw Error("LOAD_DEREF outside function");
                const std::size_t index = static_cast<std::size_t>(instr.args.at(0));
                const std::vector<Value>& cells = frames_.back().cells;
                if (index >= cells.size()) {
                    throw Error("undefined closure cell");
                }
                push(cells[index]);
                ++ip_;
                break;
            }
            case 30:  // GET_ITER
                push(make_iter(pop()));
                ++ip_;
                break;
            case 31: {  // FOR_ITER
                if (stack_.empty()) throw Error("stack underflow while iterating");
                IterObj& iterator = as_iter(stack_.back());
                if (iterator.position < iterator.items.size()) {
                    push(iterator.items[iterator.position++]);
                    ++ip_;
                } else {
                    stack_.pop_back();
                    ip_ = instr.args.at(0);
                }
                break;
            }
            case 34: {  // UNPACK_SEQUENCE
                Value value = pop();
                std::vector<Value> items = as_iter(make_iter(value)).items;
                if (static_cast<long long>(items.size()) != instr.args.at(0)) {
                    throw Error("cannot unpack " + std::to_string(items.size()) + " values into "
                        + std::to_string(instr.args.at(0)) + " targets");
                }
                for (std::size_t index = items.size(); index > 0; --index) {
                    push(items[index - 1]);
                }
                ++ip_;
                break;
            }
            case 36:
            case 41:
            case 42:
            case 43:
            case 49:
                push(make_closure(instr));
                ++ip_;
                break;
            case 47: {  // LIST_EXTEND
                Value iterable = pop();
                Value target = pop();
                if (target.tag != Tag::List) throw Error("LIST_EXTEND target must be a list");
                std::vector<Value> items = as_iter(make_iter(iterable)).items;
                as_list(target).items.insert(as_list(target).items.end(), items.begin(), items.end());
                push(target);
                ++ip_;
                break;
            }
            case 48: {  // DICT_MERGE
                Value mapping = pop();
                Value target = pop();
                if (target.tag != Tag::Dict) throw Error("DICT_MERGE target must be a dict");
                if (mapping.tag != Tag::Dict) throw Error("argument after ** must be a mapping");
                for (const auto& item : as_dict(mapping).items) {
                    if (item.first.tag != Tag::Str) throw Error("keywords must be strings");
                    if (dict_find(as_dict(target), item.first)) {
                        throw Error("duplicate keyword argument");
                    }
                    dict_set(as_dict(target), item.first, item.second);
                }
                push(target);
                ++ip_;
                break;
            }
            case 50: {  // DICT_UPDATE
                Value mapping = pop();
                Value target = pop();
                if (target.tag != Tag::Dict) throw Error("DICT_UPDATE target must be a dict");
                if (mapping.tag != Tag::Dict) throw Error("argument after ** must be a mapping");
                for (const auto& item : as_dict(mapping).items) {
                    dict_set(as_dict(target), item.first, item.second);
                }
                push(target);
                ++ip_;
                break;
            }
            case 52: {  // BUILD_SLICE
                auto slice = std::make_shared<SliceObj>();
                slice->step = pop();
                slice->upper = pop();
                slice->lower = pop();
                Value result;
                result.tag = Tag::Slice;
                result.obj = slice;
                push(result);
                ++ip_;
                break;
            }
            case 29:  // HALT
                return stack_.empty() ? make_nil() : pop();
            default:
                throw Error("unsupported opcode " + std::to_string(instr.op));
        }
    }
    return return_value;
}

}  // namespace

// Shared entry point: decode `text` and run it.  Kept outside the file-reading
// main so that an embedded build (see native/embed.py) can reuse it verbatim.
int spvm_run_text(const std::string& text, const std::string& path,
                  const std::vector<std::string>& arguments) {
    try {
        Program program = decode(tokenize(text));
        if (program.names.empty()) {
            std::ifstream sidecar(sidecar_path(path), std::ios::binary);
            if (sidecar) {
                std::ostringstream buffer;
                buffer << sidecar.rdbuf();
                program.names = parse_name_json(buffer.str());
            }
        }
        VM vm(std::move(program));
        vm.set_program_arguments(path, arguments);
        vm.run();
        return 0;
    } catch (const Error& error) {
        std::fprintf(stderr, "spvm: %s\n", error.what());
        return 1;
    } catch (const std::exception& error) {
        std::fprintf(stderr, "spvm: %s\n", error.what());
        return 1;
    }
}

#ifndef SPVM_NO_MAIN
int main(int argc, char** argv) {
    if (argc < 2) {
        std::fprintf(stderr, "usage: spvm PROGRAM.sp [ARG ...]\n");
        return 2;
    }
    try {
        const std::string path = argv[1];
        std::vector<std::string> arguments;
        for (int index = 2; index < argc; ++index) {
            arguments.push_back(argv[index]);
        }
        return spvm_run_text(read_file(path), path, arguments);
    } catch (const std::exception& error) {
        std::fprintf(stderr, "spvm: %s\n", error.what());
        return 1;
    }
}
#endif
