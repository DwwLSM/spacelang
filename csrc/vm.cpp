#include "vm.hpp"

#include <algorithm>
#include <cmath>
#include <limits>
#include <string>
#include <stdexcept>
#include <utility>

#include <Python.h>

namespace spacelang {

namespace {

enum Opcode : std::uint8_t {
    NOP = 0,
    CALL = 1,
    CALL_KW = 2,
    CALL_OBJ = 3,
    IMPORT = 4,
    OP = 5,
    STACK = 6,
    PUSH_INT = 7,
    PUSH_STR = 8,
    LOAD_GLOBAL = 9,
    STORE_GLOBAL = 10,
    GET_ATTR = 11,
    CALL_METHOD = 12,
    INDEX = 13,
    BUILD_LIST = 14,
    BUILD_TUPLE = 15,
    CONCAT = 16,
    DEF = 17,
    RET = 18,
    LOAD_ARG = 19,
    LOAD_LOCAL = 20,
    STORE_LOCAL = 21,
    JMP = 22,
    JZ = 23,
    JNZ = 24,
    RAISE = 25,
    TRY = 26,
    END_TRY = 27,
    SETUP_WITH = 28,
    HALT = 29,
    GET_ITER = 30,
    FOR_ITER = 31,
    STORE_ATTR = 32,
    STORE_INDEX = 33,
    UNPACK_SEQUENCE = 34,
    PUSH_NONE = 35,
    MAKE_CLOSURE = 36,
    CELLIFY = 37,
    LOAD_CELL_REF = 38,
    LOAD_DEREF = 39,
    CALL_OBJ_KW = 40,
    MAKE_CLOSURE_SIG = 41,
    MAKE_CLOSURE_KWONLY = 42,
    MAKE_CLOSURE_ARGS = 43,
    BUILD_DICT = 44,
    CALL_OBJ_EX = 45,
    CALL_BUILTIN_EX = 46,
    LIST_EXTEND = 47,
    DICT_MERGE = 48,
    MAKE_CLOSURE_POSONLY = 49,
    DICT_UPDATE = 50,
    BUILD_SET = 51,
    BUILD_SLICE = 52,
};

bool checked_add(std::int64_t left, std::int64_t right, std::int64_t& result) {
    if ((right > 0 && left > std::numeric_limits<std::int64_t>::max() - right)
        || (right < 0 && left < std::numeric_limits<std::int64_t>::min() - right)) {
        return false;
    }
    result = left + right;
    return true;
}

bool checked_subtract(std::int64_t left, std::int64_t right, std::int64_t& result) {
    if ((right < 0 && left > std::numeric_limits<std::int64_t>::max() + right)
        || (right > 0 && left < std::numeric_limits<std::int64_t>::min() + right)) {
        return false;
    }
    result = left - right;
    return true;
}

bool checked_multiply(std::int64_t left, std::int64_t right, std::int64_t& result) {
    constexpr auto minimum = std::numeric_limits<std::int64_t>::min();
    constexpr auto maximum = std::numeric_limits<std::int64_t>::max();
    if (left == 0 || right == 0) {
        result = 0;
        return true;
    }
    if ((left == -1 && right == minimum) || (right == -1 && left == minimum)) {
        return false;
    }
    if (left > 0) {
        if ((right > 0 && left > maximum / right) || (right < 0 && right < minimum / left)) {
            return false;
        }
    } else if ((right > 0 && left < minimum / right)
        || (right < 0 && right < maximum / left)) {
        return false;
    }
    result = left * right;
    return true;
}

bool try_numeric_binary_fast(std::int64_t op, const Value& left, const Value& right, Value& result) {
    if (left.tag == Value::Tag::INT && right.tag == Value::Tag::INT) {
        std::int64_t integer_result = 0;
        switch (op) {
            case 1:
                if (checked_add(left.data.i, right.data.i, integer_result)) {
                    result = Value(integer_result);
                    return true;
                }
                break;
            case 2:
                if (checked_subtract(left.data.i, right.data.i, integer_result)) {
                    result = Value(integer_result);
                    return true;
                }
                break;
            case 3:
                if (checked_multiply(left.data.i, right.data.i, integer_result)) {
                    result = Value(integer_result);
                    return true;
                }
                break;
            case 6:
                result = Value(left.data.i == right.data.i);
                return true;
            case 7:
                result = Value(left.data.i < right.data.i);
                return true;
            case 8:
                result = Value(left.data.i > right.data.i);
                return true;
            case 9:
                result = Value(left.data.i != right.data.i);
                return true;
            case 10:
                result = Value(left.data.i <= right.data.i);
                return true;
            case 11:
                result = Value(left.data.i >= right.data.i);
                return true;
            default:
                break;
        }
    }
    return false;
}

Value numeric_binary(std::int64_t op, const Value& left, const Value& right) {
    if (op == 14 || op == 15) {
        bool identical = left.tag == right.tag;
        if (identical) {
            switch (left.tag) {
                case Value::Tag::INT:
                    identical = left.data.i == right.data.i;
                    break;
                case Value::Tag::FLOAT:
                    identical = left.data.f == right.data.f;
                    break;
                case Value::Tag::BOOL:
                    identical = left.data.b == right.data.b;
                    break;
                case Value::Tag::NONE:
                    break;
                case Value::Tag::PYOBJ:
                    identical = left.data.obj == right.data.obj;
                    break;
            }
        }
        return Value(op == 14 ? identical : !identical);
    }

    Value fast_result;
    if (try_numeric_binary_fast(op, left, right, fast_result)) {
        return fast_result;
    }

    const auto left_object = left.to_python();
    const auto right_object = right.to_python();
    PyObject* result = nullptr;
    switch (op) {
        case 1:
            result = PyNumber_Add(left_object.ptr(), right_object.ptr());
            break;
        case 2:
            result = PyNumber_Subtract(left_object.ptr(), right_object.ptr());
            break;
        case 3:
            result = PyNumber_Multiply(left_object.ptr(), right_object.ptr());
            break;
        case 4:
            result = PyNumber_TrueDivide(left_object.ptr(), right_object.ptr());
            break;
        case 5:
            result = PyNumber_Remainder(left_object.ptr(), right_object.ptr());
            break;
        case 6:
            result = PyObject_RichCompare(left_object.ptr(), right_object.ptr(), Py_EQ);
            break;
        case 7:
            result = PyObject_RichCompare(left_object.ptr(), right_object.ptr(), Py_LT);
            break;
        case 8:
            result = PyObject_RichCompare(left_object.ptr(), right_object.ptr(), Py_GT);
            break;
        case 9:
            result = PyObject_RichCompare(left_object.ptr(), right_object.ptr(), Py_NE);
            break;
        case 10:
            result = PyObject_RichCompare(left_object.ptr(), right_object.ptr(), Py_LE);
            break;
        case 11:
            result = PyObject_RichCompare(left_object.ptr(), right_object.ptr(), Py_GE);
            break;
        case 12:
        case 13: {
            const int contains = PySequence_Contains(right_object.ptr(), left_object.ptr());
            if (contains < 0) {
                throw pybind11::error_already_set();
            }
            result = PyBool_FromLong(op == 12 ? contains : !contains);
            break;
        }
        default:
            throw pybind11::value_error("unsupported native OP id");
    }
    if (result == nullptr) {
        throw pybind11::error_already_set();
    }
    pybind11::object owned_result = pybind11::reinterpret_steal<pybind11::object>(result);
    return Value::from_python(owned_result);
}

}  // namespace

VM::VM(pybind11::object program) {
    const auto source = program.attr("instrs").cast<pybind11::sequence>();
    instrs_.reserve(source.size());
    for (const auto item : source) {
        Instr instr;
        const auto opcode = item.attr("op").cast<std::int64_t>();
        if (opcode < 0 || opcode >= 53) {
            throw pybind11::value_error("invalid native VM opcode");
        }
        instr.op = static_cast<std::uint8_t>(opcode);
        instr.line = item.attr("line").cast<std::int32_t>();
        const auto args = item.attr("args").cast<pybind11::sequence>();
        instr.args.reserve(static_cast<std::size_t>(args.size()));
        for (pybind11::ssize_t index = 0; index < args.size(); ++index) {
            instr.args.push_back(args[index].cast<std::int64_t>());
        }
        const std::size_t expected[] = {
            0, 2, 3, 1, 1, 1, 1, 1, 0, 1, 1, 1, 2, 1, 1, 1,
            1, 2, 0, 1, 1, 1, 1, 1, 1, 0, 2, 0, 0, 0, 0, 1,
            1, 0,             1, 0, 3, 1, 1,                         1, 2, 4, 6, 8, 1, 0, 1, 0, 0, 9, 0, 1, 0,
        };
        if (instr.op >= 53
            || (instr.op == PUSH_STR
                ? (instr.args.empty() || instr.args[0] < 0 || instr.args[0] > 1000
                    || instr.args.size() != static_cast<std::size_t>(instr.args[0]) + 1)
                : instr.args.size() != expected[instr.op])) {
            throw pybind11::value_error("invalid native VM instruction shape");
        }
        for (std::size_t index = 0; index < instr.args.size(); ++index) {
            if (!(instr.op == PUSH_INT && index == 0) && instr.args[index] < 0) {
                throw pybind11::value_error("native VM arguments must be non-negative");
            }
            if (instr.op == PUSH_STR && index > 0 && instr.args[index] > 65535) {
                throw pybind11::value_error("native VM string code point exceeds MAX_LINE");
            }
        }
        instrs_.push_back(instr);
    }

    const auto source_names = program.attr("names").cast<pybind11::dict>();
    for (const auto item : source_names) {
        names_[pybind11::cast<std::int64_t>(item.second)] = pybind11::cast<std::string>(item.first);
    }
    const auto source_funcs = program.attr("funcs").cast<pybind11::dict>();
    for (const auto item : source_funcs) {
        const auto bounds = item.second.cast<pybind11::sequence>();
        funcs_[pybind11::cast<std::int64_t>(item.first)] = {
            bounds[0].cast<std::int64_t>(),
            bounds[1].cast<std::int64_t>(),
        };
    }

    const auto source_tries = program.attr("try_table").cast<pybind11::sequence>();
    try_table_.reserve(static_cast<std::size_t>(source_tries.size()));
    for (const auto item : source_tries) {
        const auto entry = item.cast<pybind11::sequence>();
        if (entry.size() != 4) {
            throw pybind11::value_error("invalid try-table entry");
        }
        try_table_.emplace_back(
            entry[0].cast<std::int64_t>(),
            entry[1].cast<std::int64_t>(),
            entry[2].cast<std::int64_t>(),
            entry[3].cast<std::int64_t>()
        );
    }
}

Value VM::pop(const char* name) {
    if (stack_.empty()) {
        raise_space_error("StackUnderflow", std::string("stack underflow while popping ") + name);
    }
    Value result = std::move(stack_.back());
    stack_.pop_back();
    return result;
}

const std::string& VM::name(std::int64_t name_id) const {
    const auto found = names_.find(name_id);
    if (found == names_.end()) {
        raise_space_error("UndefinedName", "unknown name id " + std::to_string(name_id));
    }
    return found->second;
}

void VM::raise_space_error(const char* type, const std::string& message, std::int32_t line) const {
    const auto error_type = pybind11::module_::import("spacelang.errors").attr(type);
    const auto exception = error_type(line, current_ip_, message);
    PyErr_SetObject(reinterpret_cast<PyObject*>(Py_TYPE(exception.ptr())), exception.ptr());
    throw pybind11::error_already_set();
}

pybind11::object VM::builtin(std::int64_t func_id) const {
    static const char* builtin_names[] = {
        "print", "input", "len", "int", "float", "str", "bool", "abs",
        "range", "type", "open", "getattr", "setattr", "callable", "repr", "isinstance", "set",
    };
    if (func_id >= 0 && func_id < 17) {
        return pybind11::module_::import("builtins").attr(builtin_names[func_id]);
    }
    const std::pair<std::int64_t, const char*> module_functions[] = {
        {1000, "sqrt"}, {1001, "sin"}, {1002, "cos"}, {1003, "tan"},
        {1004, "floor"}, {1005, "ceil"}, {1006, "fabs"}, {1007, "exp"},
        {1008, "log"},
    };
    for (const auto& item : module_functions) {
        if (item.first == func_id) {
            return pybind11::module_::import("math").attr(item.second);
        }
    }
    if (func_id == 2000) {
        return pybind11::module_::import("random").attr("random");
    }
    if (func_id == 2001) {
        return pybind11::module_::import("random").attr("randint");
    }
    if (func_id == 3000) {
        return pybind11::module_::import("os").attr("system");
    }
    if (func_id == 4000) {
        return pybind11::module_::import("re").attr("compile");
    }
    if (func_id == 5000) {
        return pybind11::module_::import("sys").attr("exit");
    }
    raise_space_error("UndefinedFunc", "undefined function " + std::to_string(func_id));
}

bool VM::route_exception(const pybind11::object& exception, std::int64_t& ip) {
    while (!try_stack_.empty()) {
        auto& frame = try_stack_.back();
        if (stack_.size() > frame.stack_depth) {
            stack_.resize(frame.stack_depth);
        }
        if (call_stack_.size() > frame.call_depth) {
            call_stack_.resize(frame.call_depth);
        }
        if (frame.stage == TryFrame::Stage::BODY && frame.catch_ip != 0) {
            frame.exception = exception;
            frame.stage = TryFrame::Stage::CATCH;
            ip = frame.catch_ip;
            return true;
        }
        if (frame.stage != TryFrame::Stage::FINALLY && frame.finally_ip != 0) {
            frame.exception = exception;
            frame.stage = TryFrame::Stage::FINALLY;
            ip = frame.finally_ip;
            return true;
        }
        try_stack_.pop_back();
    }
    return false;
}

void VM::raise_exception(const pybind11::object& exception) {
    if (!PyExceptionInstance_Check(exception.ptr())) {
        PyErr_SetString(PyExc_RuntimeError, pybind11::str(exception).cast<std::string>().c_str());
    } else {
        PyErr_SetObject(
            reinterpret_cast<PyObject*>(Py_TYPE(exception.ptr())),
            exception.ptr()
        );
    }
    throw pybind11::error_already_set();
}

pybind11::object VM::run() {
    std::int64_t ip = 0;
    while (ip >= 0 && ip < static_cast<std::int64_t>(instrs_.size())) {
        current_ip_ = ip;
        const auto& instr = instrs_[static_cast<std::size_t>(ip)];
        const auto dispatch_exception = [&](const pybind11::object& original) {
            auto exception = original;
            const auto errors = pybind11::module_::import("spacelang.errors");
            const auto space_error = errors.attr("SpaceError");
            const int is_space_error = PyObject_IsInstance(exception.ptr(), space_error.ptr());
            if (is_space_error < 0) {
                throw pybind11::error_already_set();
            }
            if (!is_space_error) {
                exception = errors.attr("RuntimeError")(
                    instr.line,
                    ip,
                    pybind11::str(original).cast<std::string>()
                );
            }
            PyErr_SetObject(
                reinterpret_cast<PyObject*>(Py_TYPE(exception.ptr())),
                exception.ptr()
            );
            pybind11::error_already_set routed_exception;
            if (!route_exception(routed_exception.value(), ip)) {
                throw routed_exception;
            }
        };
        try {
#if defined(__GNUC__) || defined(__clang__)
        static const void* dispatch_table[] = {
            &&op_nop, &&op_call, &&op_call_kw, &&op_call_obj, &&op_import,
            &&op_operation, &&op_stack, &&op_push_int, &&op_push_str,
            &&op_load_global, &&op_store_global, &&op_get_attr, &&op_call_method,
            &&op_index, &&op_build_list, &&op_build_tuple, &&op_concat, &&op_def,
            &&op_ret, &&op_load_arg, &&op_load_local, &&op_store_local, &&op_jmp,
            &&op_jz, &&op_jnz, &&op_raise, &&op_try, &&op_end_try,
            &&op_setup_with, &&op_halt, &&op_get_iter, &&op_for_iter,
            &&op_store_attr, &&op_store_index, &&op_unpack_sequence,
            &&op_push_none, &&op_make_closure, &&op_cellify,
            &&op_load_cell_ref, &&op_load_deref, &&op_call_obj_kw,
            &&op_make_closure_sig, &&op_make_closure_kwonly, &&op_make_closure_args,
            &&op_build_dict, &&op_call_obj_ex, &&op_call_builtin_ex,
            &&op_list_extend, &&op_dict_merge, &&op_make_closure_posonly,
            &&op_dict_update, &&op_build_set,
            &&op_build_slice,
        };
        if (instr.op >= sizeof(dispatch_table) / sizeof(dispatch_table[0])) {
            throw pybind11::value_error("unknown native VM opcode");
        }
        goto *dispatch_table[instr.op];
#endif
        switch (instr.op) {
            case NOP:
#if defined(__GNUC__) || defined(__clang__)
            op_nop:
#endif
                ++ip;
                break;
            case PUSH_STR: {
#if defined(__GNUC__) || defined(__clang__)
            op_push_str:
#endif
                std::u32string text;
                text.reserve(static_cast<std::size_t>(instr.args[0]));
                for (std::int64_t index = 0; index < instr.args[0]; ++index) {
                    text.push_back(static_cast<char32_t>(instr.args[static_cast<std::size_t>(index) + 1]));
                }
                PyObject* string = PyUnicode_FromKindAndData(
                    PyUnicode_4BYTE_KIND,
                    text.data(),
                    static_cast<Py_ssize_t>(text.size())
                );
                if (string == nullptr) {
                    throw pybind11::error_already_set();
                }
                stack_.push_back(Value::from_python(pybind11::reinterpret_steal<pybind11::object>(string)));
                ++ip;
                break;
            }
            case LOAD_GLOBAL: {
#if defined(__GNUC__) || defined(__clang__)
            op_load_global:
#endif
                const auto key = pybind11::str(name(instr.args[0]));
                if (!globals_.contains(key)) {
                    raise_space_error("UndefinedName", "undefined global " + name(instr.args[0]), instr.line);
                }
                stack_.push_back(Value::from_python(globals_[key]));
                ++ip;
                break;
            }
            case STORE_GLOBAL: {
#if defined(__GNUC__) || defined(__clang__)
            op_store_global:
#endif
                const auto key = pybind11::str(name(instr.args[0]));
                globals_[key] = pop("global value").to_python();
                ++ip;
                break;
            }
            case GET_ATTR: {
#if defined(__GNUC__) || defined(__clang__)
            op_get_attr:
#endif
                const auto object = pop("object").to_python();
                stack_.push_back(Value::from_python(object.attr(name(instr.args[0]).c_str())));
                ++ip;
                break;
            }
            case CALL:
            case CALL_KW:
            case CALL_OBJ:
            case CALL_OBJ_KW:
            case CALL_OBJ_EX:
            case CALL_BUILTIN_EX:
            case CALL_METHOD: {
#if defined(__GNUC__) || defined(__clang__)
            op_call:
            op_call_kw:
            op_call_obj:
            op_call_obj_kw:
            op_call_obj_ex:
            op_call_builtin_ex:
            op_call_method:
#endif
                std::int64_t func_id = 0;
                if (instr.op == CALL || instr.op == CALL_KW || instr.op == CALL_BUILTIN_EX) {
                    func_id = instr.args[0];
                }
                std::int64_t positional_count = 0;
                std::int64_t keyword_count = 0;
                if (instr.op == CALL_KW) {
                    positional_count = instr.args[1];
                    keyword_count = instr.args[2];
                } else if (instr.op == CALL_OBJ_KW) {
                    positional_count = instr.args[0];
                    keyword_count = instr.args[1];
                } else if (instr.op == CALL_OBJ) {
                    positional_count = instr.args[0];
                } else if (instr.op == CALL_OBJ_EX) {
                    positional_count = 0;
                } else if (instr.op == CALL_BUILTIN_EX) {
                    func_id = instr.args[0];
                } else {
                    positional_count = instr.args[1];
                }
                pybind11::object callable;
                if (instr.op == CALL_METHOD) {
                    positional_count = instr.args[1];
                } else if (instr.op == CALL_OBJ) {
                    callable = pybind11::none();
                } else if (instr.op == CALL || instr.op == CALL_KW) {
                    if (func_id >= 10000) {
                        if (instr.op == CALL_KW) {
                            raise_space_error("TypeError", "CALL_KW is not supported for user functions");
                        }
                        const auto function = funcs_.find(func_id);
                        if (function == funcs_.end()) {
                            raise_space_error("UndefinedFunc", "undefined user function " + std::to_string(func_id));
                        }
                        Frame frame{func_id, ip + 1, {}, {}};
                        frame.locals.resize(static_cast<std::size_t>(positional_count));
                        frame.initialized.assign(frame.locals.size(), true);
                        for (std::int64_t index = positional_count - 1; index >= 0; --index) {
                            frame.locals[static_cast<std::size_t>(index)] = pop("function argument");
                        }
                        call_stack_.push_back(std::move(frame));
                        ip = function->second.first;
                        break;
                    }
                    callable = builtin(func_id);
                } else if (instr.op == CALL_BUILTIN_EX) {
                    callable = builtin(func_id);
                }

                pybind11::dict keywords;
                std::vector<pybind11::object> positional_values;
                const auto pop_keywords = [&]() {
                    std::vector<std::pair<std::string, pybind11::object>> items;
                    for (std::int64_t index = 0; index < keyword_count; ++index) {
                        const auto value = pop("keyword value").to_python();
                        const auto name_id = pop("keyword name").to_python().cast<std::int64_t>();
                        items.emplace_back(name(name_id), value);
                    }
                    for (auto item = items.rbegin(); item != items.rend(); ++item) {
                        const auto& key = item->first;
                        if (keywords.contains(pybind11::str(key))) {
                            raise_space_error("TypeError", "multiple values for keyword '" + key + "'", instr.line);
                        }
                        keywords[pybind11::str(key)] = item->second;
                    }
                };
                const auto pop_positional = [&]() {
                    for (std::int64_t index = 0; index < positional_count; ++index) {
                        positional_values.push_back(pop("call argument").to_python());
                    }
                    std::reverse(positional_values.begin(), positional_values.end());
                };
                if (instr.op == CALL_OBJ_EX || instr.op == CALL_BUILTIN_EX) {
                    const auto keyword_object = pop("keyword arguments").to_python();
                    const auto positional_object = pop("positional arguments").to_python();
                    if (!PyDict_Check(keyword_object.ptr()) || !PyList_Check(positional_object.ptr())) {
                        raise_space_error("TypeError", "invalid expanded call arguments", instr.line);
                    }
                    keywords = pybind11::reinterpret_borrow<pybind11::dict>(keyword_object);
                    for (const auto& value : pybind11::reinterpret_borrow<pybind11::list>(positional_object)) {
                        positional_values.push_back(pybind11::reinterpret_borrow<pybind11::object>(value));
                    }
                } else if (instr.op == CALL_OBJ_KW) {
                    pop_keywords();
                    pop_positional();
                } else {
                    pop_positional();
                    pop_keywords();
                }
                pybind11::tuple positional(positional_values.size());
                for (std::size_t index = 0; index < positional_values.size(); ++index) {
                    Py_INCREF(positional_values[index].ptr());
                    PyTuple_SET_ITEM(positional.ptr(), static_cast<Py_ssize_t>(index), positional_values[index].ptr());
                }
                if (instr.op == CALL_OBJ || instr.op == CALL_OBJ_KW || instr.op == CALL_OBJ_EX) {
                    callable = pop("callable").to_python();
                    const auto closure_type = pybind11::module_::import("spacelang.vm_py").attr("Closure");
                    if (pybind11::isinstance(callable, closure_type)) {
                        const auto func_id_value = callable.attr("func_id").cast<std::int64_t>();
                        const auto function = funcs_.find(func_id_value);
                        if (function == funcs_.end()) {
                            raise_space_error(
                                "UndefinedFunc",
                                "undefined user function " + std::to_string(func_id_value)
                            );
                        }
                        const auto parameter_names_value = callable.attr("parameter_names");
                        if (parameter_names_value.is_none()) {
                            const auto arg_count = callable.attr("arg_count").cast<std::int64_t>();
                            if (keyword_count != 0) {
                                raise_space_error(
                                    "TypeError",
                                    "keyword arguments are unavailable for this legacy closure",
                                    instr.line
                                );
                            }
                            if (positional_count != arg_count) {
                                raise_space_error(
                                    "TypeError",
                                    "expected " + std::to_string(arg_count) + " positional arguments, got "
                                        + std::to_string(positional_count),
                                    instr.line
                                );
                            }
                            Frame frame{
                                func_id_value,
                                ip + 1,
                                {},
                                {},
                                callable.attr("cells").cast<pybind11::list>(),
                            };
                            frame.locals.resize(positional_values.size());
                            frame.initialized.assign(frame.locals.size(), true);
                            for (std::size_t index = 0; index < positional_values.size(); ++index) {
                                frame.locals[index] = Value::from_python(positional_values[index]);
                            }
                            call_stack_.push_back(std::move(frame));
                            ip = function->second.first;
                            break;
                        }
                        const auto parameter_names = parameter_names_value.cast<pybind11::list>();
                        const auto positional_parameter_count =
                            callable.attr("positional_count").cast<std::int64_t>();
                        const auto vararg_name_value = callable.attr("vararg_name");
                        const bool has_varargs = !vararg_name_value.is_none();
                        const auto kwarg_name_value = callable.attr("kwarg_name");
                        const bool has_kwargs = !kwarg_name_value.is_none();
                        const auto positional_only_count =
                        callable.attr("positional_only_count").cast<std::int64_t>();
                        const auto defaults = callable.attr("defaults").cast<pybind11::dict>();
                        if (!has_varargs
                            && positional_values.size() > static_cast<std::size_t>(positional_parameter_count)) {
                            raise_space_error(
                                "TypeError",
                                "expected at most " + std::to_string(positional_parameter_count)
                                    + " positional arguments, got " + std::to_string(positional_values.size()),
                                instr.line
                            );
                        }
                        std::vector<pybind11::object> bound(static_cast<std::size_t>(parameter_names.size()));
                        std::vector<bool> assigned(bound.size(), false);
                        pybind11::dict extra_keywords;
                        const auto assigned_positional_count = std::min(
                            positional_values.size(),
                            static_cast<std::size_t>(positional_parameter_count)
                        );
                        for (std::size_t index = 0; index < assigned_positional_count; ++index) {
                            bound[index] = positional_values[index];
                            assigned[index] = true;
                        }
                        for (const auto item : keywords) {
                            const auto key = pybind11::cast<std::string>(item.first);
                            std::size_t index = 0;
                            while (index < static_cast<std::size_t>(parameter_names.size())
                                && pybind11::cast<std::string>(parameter_names[index]) != key) {
                                ++index;
                            }
                            if (index == static_cast<std::size_t>(parameter_names.size())) {
                                if (!has_kwargs) {
                                    raise_space_error("TypeError", "unexpected keyword argument '" + key + "'", instr.line);
                                }
                                extra_keywords[item.first] =
                                    pybind11::reinterpret_borrow<pybind11::object>(item.second);
                                continue;
                            }
                            if (index < static_cast<std::size_t>(positional_only_count)) {
                                if (!has_kwargs) {
                                    raise_space_error(
                                        "TypeError",
                                        "positional-only argument '" + key + "' passed as a keyword",
                                        instr.line
                                    );
                                }
                                extra_keywords[item.first] =
                                    pybind11::reinterpret_borrow<pybind11::object>(item.second);
                                continue;
                            }
                            if (assigned[index]) {
                                raise_space_error("TypeError", "multiple values for argument '" + key + "'", instr.line);
                            }
                            bound[index] = pybind11::reinterpret_borrow<pybind11::object>(item.second);
                            assigned[index] = true;
                        }
                        Frame frame{
                            func_id_value,
                            ip + 1,
                            {},
                            {},
                            callable.attr("cells").cast<pybind11::list>(),
                        };
                        frame.locals.resize(bound.size() + (has_varargs ? 1 : 0) + (has_kwargs ? 1 : 0));
                        frame.initialized.assign(frame.locals.size(), true);
                        for (std::size_t index = 0; index < bound.size(); ++index) {
                            if (!assigned[index]) {
                                const auto parameter_name = pybind11::reinterpret_borrow<pybind11::object>(parameter_names[index]);
                                const auto key = pybind11::str(parameter_name);
                                if (!defaults.contains(key)) {
                                    raise_space_error(
                                        "TypeError",
                                        "missing required argument '" + pybind11::cast<std::string>(parameter_name) + "'",
                                        instr.line
                                    );
                                }
                                bound[index] = pybind11::reinterpret_borrow<pybind11::object>(defaults[key]);
                            }
                            frame.locals[index] = Value::from_python(bound[index]);
                        }
                        if (has_varargs) {
                            pybind11::tuple varargs(
                                positional_values.size() - assigned_positional_count
                            );
                            for (std::size_t index = assigned_positional_count;
                                index < positional_values.size();
                                ++index) {
                                const auto tuple_index = index - assigned_positional_count;
                                Py_INCREF(positional_values[index].ptr());
                                PyTuple_SET_ITEM(
                                    varargs.ptr(),
                                    static_cast<Py_ssize_t>(tuple_index),
                                    positional_values[index].ptr()
                                );
                            }
                            frame.locals[bound.size()] = Value::from_python(varargs);
                        }
                        if (has_kwargs) {
                            frame.locals[bound.size() + (has_varargs ? 1 : 0)] =
                                Value::from_python(extra_keywords);
                        }
                        call_stack_.push_back(std::move(frame));
                        ip = function->second.first;
                        break;
                    }
                } else if (instr.op == CALL_METHOD) {
                    callable = pop("method object").to_python().attr(name(instr.args[0]).c_str());
                }
                auto result = callable(*positional, **keywords);
                stack_.push_back(Value::from_python(result));
                ++ip;
                break;
            }
            case IMPORT: {
#if defined(__GNUC__) || defined(__clang__)
            op_import:
#endif
                const auto modules = pybind11::module_::import("spacelang.modules");
                const auto result = modules.attr("do_import")(instr.args[0], globals_);
                stack_.push_back(Value::from_python(result));
                ++ip;
                break;
            }
            case INDEX: {
#if defined(__GNUC__) || defined(__clang__)
            op_index:
#endif
                const auto key = pop("index key").to_python();
                const auto object = pop("index object").to_python();
                stack_.push_back(Value::from_python(object[key]));
                ++ip;
                break;
            }
            case BUILD_SLICE: {
#if defined(__GNUC__) || defined(__clang__)
            op_build_slice:
#endif
                const auto step = pop("slice step").to_python();
                const auto upper = pop("slice upper bound").to_python();
                const auto lower = pop("slice lower bound").to_python();
                PyObject* raw_slice = PySlice_New(
                    lower.ptr(),
                    upper.ptr(),
                    step.ptr()
                );
                if (raw_slice == nullptr) {
                    throw pybind11::error_already_set();
                }
                stack_.push_back(Value::from_python(
                    pybind11::reinterpret_steal<pybind11::object>(raw_slice)
                ));
                ++ip;
                break;
            }
            case STORE_ATTR: {
#if defined(__GNUC__) || defined(__clang__)
            op_store_attr:
#endif
                const auto object = pop("attribute object").to_python();
                const auto value = pop("attribute value").to_python();
                if (PyObject_SetAttrString(object.ptr(), name(instr.args[0]).c_str(), value.ptr()) < 0) {
                    throw pybind11::error_already_set();
                }
                ++ip;
                break;
            }
            case STORE_INDEX: {
#if defined(__GNUC__) || defined(__clang__)
            op_store_index:
#endif
                const auto key = pop("index key").to_python();
                const auto object = pop("index object").to_python();
                const auto value = pop("index value").to_python();
                if (PyObject_SetItem(object.ptr(), key.ptr(), value.ptr()) < 0) {
                    throw pybind11::error_already_set();
                }
                ++ip;
                break;
            }
            case UNPACK_SEQUENCE: {
#if defined(__GNUC__) || defined(__clang__)
            op_unpack_sequence:
#endif
                const auto count = instr.args[0];
                const auto iterable = pop("unpack value").to_python();
                PyObject* iterator = PyObject_GetIter(iterable.ptr());
                if (iterator == nullptr) {
                    throw pybind11::error_already_set();
                }
                auto owned_iterator = pybind11::reinterpret_steal<pybind11::object>(iterator);
                std::vector<pybind11::object> values;
                values.reserve(static_cast<std::size_t>(count));
                for (std::int64_t index = 0; index < count; ++index) {
                    PyObject* item = PyIter_Next(owned_iterator.ptr());
                    if (item == nullptr) {
                        if (PyErr_Occurred()) {
                            throw pybind11::error_already_set();
                        }
                        raise_space_error(
                            "RuntimeError",
                            "not enough values to unpack (expected " + std::to_string(count)
                                + ", got " + std::to_string(values.size()) + ")",
                            instr.line
                        );
                    }
                    values.push_back(pybind11::reinterpret_steal<pybind11::object>(item));
                }
                PyObject* extra = PyIter_Next(owned_iterator.ptr());
                if (extra != nullptr) {
                    Py_DECREF(extra);
                    raise_space_error(
                        "RuntimeError",
                        "too many values to unpack (expected " + std::to_string(count) + ")",
                        instr.line
                    );
                }
                if (PyErr_Occurred()) {
                    throw pybind11::error_already_set();
                }
                for (auto value = values.rbegin(); value != values.rend(); ++value) {
                    stack_.push_back(Value::from_python(*value));
                }
                ++ip;
                break;
            }
            case GET_ITER: {
#if defined(__GNUC__) || defined(__clang__)
            op_get_iter:
#endif
                const auto iterable = pop("iterable").to_python();
                PyObject* iterator = PyObject_GetIter(iterable.ptr());
                if (iterator == nullptr) {
                    throw pybind11::error_already_set();
                }
                stack_.push_back(Value::from_python(pybind11::reinterpret_steal<pybind11::object>(iterator)));
                ++ip;
                break;
            }
            case FOR_ITER: {
#if defined(__GNUC__) || defined(__clang__)
            op_for_iter:
#endif
                const auto target = instr.args[0];
                if (target < 0 || target >= static_cast<std::int64_t>(instrs_.size())) {
                    raise_space_error(
                        "JumpOutOfRange",
                        "jump target " + std::to_string(target) + " out of range",
                        instr.line
                    );
                }
                if (stack_.empty()) {
                    raise_space_error("StackUnderflow", "stack underflow while iterating", instr.line);
                }
                PyObject* item = PyIter_Next(stack_.back().to_python().ptr());
                if (item == nullptr) {
                    if (PyErr_Occurred()) {
                        throw pybind11::error_already_set();
                    }
                    stack_.pop_back();
                    ip = target;
                } else {
                    stack_.push_back(Value::from_python(pybind11::reinterpret_steal<pybind11::object>(item)));
                    ++ip;
                }
                break;
            }
            case BUILD_LIST:
            case BUILD_TUPLE: {
#if defined(__GNUC__) || defined(__clang__)
            op_build_list:
            op_build_tuple:
#endif
                std::vector<pybind11::object> values;
                for (std::int64_t index = 0; index < instr.args[0]; ++index) {
                    values.push_back(pop("container element").to_python());
                }
                std::reverse(values.begin(), values.end());
                pybind11::object result;
                if (instr.op == BUILD_LIST) {
                    pybind11::list list;
                    for (const auto& value : values) {
                        list.append(value);
                    }
                    result = std::move(list);
                } else {
                    result = pybind11::tuple(values.size());
                    for (std::size_t index = 0; index < values.size(); ++index) {
                        Py_INCREF(values[index].ptr());
                        PyTuple_SET_ITEM(result.ptr(), static_cast<Py_ssize_t>(index), values[index].ptr());
                    }
                }
                stack_.push_back(Value::from_python(result));
                ++ip;
                break;
            }
            case BUILD_DICT: {
#if defined(__GNUC__) || defined(__clang__)
            op_build_dict:
#endif
                std::vector<std::pair<pybind11::object, pybind11::object>> items;
                for (std::int64_t index = 0; index < instr.args[0]; ++index) {
                    auto value = pop("dict value").to_python();
                    auto key = pop("dict key").to_python();
                    items.emplace_back(std::move(key), std::move(value));
                }
                std::reverse(items.begin(), items.end());
                pybind11::dict result;
                for (const auto& item : items) {
                    result[item.first] = item.second;
                }
                stack_.push_back(Value::from_python(result));
                ++ip;
                break;
            }
            case BUILD_SET: {
#if defined(__GNUC__) || defined(__clang__)
            op_build_set:
#endif
                std::vector<pybind11::object> values;
                for (std::int64_t index = 0; index < instr.args[0]; ++index) {
                    values.push_back(pop("set element").to_python());
                }
                std::reverse(values.begin(), values.end());
                PyObject* raw_set = PySet_New(nullptr);
                if (raw_set == nullptr) {
                    throw pybind11::error_already_set();
                }
                auto result = pybind11::reinterpret_steal<pybind11::set>(raw_set);
                for (const auto& value : values) {
                    if (PySet_Add(result.ptr(), value.ptr()) < 0) {
                        throw pybind11::error_already_set();
                    }
                }
                stack_.push_back(Value::from_python(result));
                ++ip;
                break;
            }
            case LIST_EXTEND: {
#if defined(__GNUC__) || defined(__clang__)
            op_list_extend:
#endif
                const auto iterable = pop("list iterable").to_python();
                const auto target = pop("list").to_python();
                if (!PyList_Check(target.ptr())) {
                    raise_space_error("TypeError", "LIST_EXTEND target must be a list", instr.line);
                }
                PyObject* extend_result = PyObject_CallMethod(target.ptr(), "extend", "O", iterable.ptr());
                if (extend_result == nullptr) {
                    throw pybind11::error_already_set();
                }
                Py_DECREF(extend_result);
                stack_.push_back(Value::from_python(target));
                ++ip;
                break;
            }
            case DICT_MERGE: {
#if defined(__GNUC__) || defined(__clang__)
            op_dict_merge:
#endif
                const auto mapping = pop("keyword mapping").to_python();
                const auto target_object = pop("keyword arguments").to_python();
                if (!PyDict_Check(target_object.ptr())) {
                    raise_space_error("TypeError", "DICT_MERGE target must be a dictionary", instr.line);
                }
                const int has_keys = PyObject_HasAttrString(mapping.ptr(), "keys");
                if (has_keys < 0) {
                    throw pybind11::error_already_set();
                }
                if (has_keys == 0) {
                    raise_space_error("TypeError", "argument after ** must be a mapping", instr.line);
                }
                PyObject* keys_raw = PyMapping_Keys(mapping.ptr());
                if (keys_raw == nullptr) {
                    throw pybind11::error_already_set();
                }
                auto keys = pybind11::reinterpret_steal<pybind11::object>(keys_raw);
                auto target = pybind11::reinterpret_borrow<pybind11::dict>(target_object);
                for (const auto& key_handle : keys) {
                    const auto key = pybind11::reinterpret_borrow<pybind11::object>(key_handle);
                    if (!PyUnicode_Check(key.ptr())) {
                        raise_space_error("TypeError", "keywords must be strings", instr.line);
                    }
                    if (target.contains(key)) {
                        raise_space_error(
                            "TypeError",
                            "got multiple values for keyword argument '" + key.cast<std::string>() + "'",
                            instr.line
                        );
                    }
                    target[key] = mapping[key];
                }
                stack_.push_back(Value::from_python(target));
                ++ip;
                break;
            }
            case DICT_UPDATE: {
#if defined(__GNUC__) || defined(__clang__)
            op_dict_update:
#endif
                const auto mapping = pop("dictionary mapping").to_python();
                const auto target_object = pop("dictionary").to_python();
                if (!PyDict_Check(target_object.ptr())) {
                    raise_space_error("TypeError", "DICT_UPDATE target must be a dictionary", instr.line);
                }
                const int has_keys = PyObject_HasAttrString(mapping.ptr(), "keys");
                if (has_keys < 0) {
                    throw pybind11::error_already_set();
                }
                if (has_keys == 0) {
                    raise_space_error(
                        "TypeError",
                        "argument after ** must be a mapping",
                        instr.line
                    );
                }
                PyObject* keys_raw = PyMapping_Keys(mapping.ptr());
                if (keys_raw == nullptr) {
                    throw pybind11::error_already_set();
                }
                auto keys = pybind11::reinterpret_steal<pybind11::object>(keys_raw);
                auto target = pybind11::reinterpret_borrow<pybind11::dict>(target_object);
                for (const auto& key_handle : keys) {
                    const auto key = pybind11::reinterpret_borrow<pybind11::object>(key_handle);
                    target[key] = mapping[key];
                }
                stack_.push_back(Value::from_python(target));
                ++ip;
                break;
            }
            case CONCAT: {
#if defined(__GNUC__) || defined(__clang__)
            op_concat:
#endif
                const auto count = instr.args[0];
                std::vector<pybind11::object> values;
                for (std::int64_t index = 0; index < count; ++index) {
                    values.push_back(pop("concat operand").to_python());
                }
                std::reverse(values.begin(), values.end());
                pybind11::object result = pybind11::str("");
                if (count > 0) {
                    const auto category = [](PyObject* value) {
                        if (PyUnicode_Check(value)) {
                            return 1;
                        }
                        if (PyBytes_Check(value) || PyByteArray_Check(value)) {
                            return 2;
                        }
                        if (PyList_Check(value)) {
                            return 3;
                        }
                        if (PyTuple_Check(value)) {
                            return 4;
                        }
                        return 0;
                    };
                    const auto kind = category(values.front().ptr());
                    if (kind == 0 || std::any_of(values.begin(), values.end(), [&](const auto& value) {
                        return category(value.ptr()) != kind;
                    })) {
                        raise_space_error("TypeError", "Concat requires homogeneous types");
                    }

                    if (kind == 1 || kind == 2) {
                        pybind11::list sequence;
                        for (const auto& value : values) {
                            sequence.append(kind == 2 && PyByteArray_Check(value.ptr())
                                ? pybind11::module_::import("builtins").attr("bytes")(value)
                                : value);
                        }
                        pybind11::object separator = kind == 1
                            ? pybind11::object(pybind11::str(""))
                            : pybind11::object(pybind11::bytes(""));
                        result = separator.attr("join")(sequence);
                    } else {
                        pybind11::list sequence;
                        for (const auto& value : values) {
                            for (const auto item : pybind11::reinterpret_borrow<pybind11::iterable>(value)) {
                                sequence.append(item);
                            }
                        }
                        result = kind == 3 ? pybind11::object(std::move(sequence))
                                           : pybind11::object(pybind11::tuple(sequence));
                    }
                }
                stack_.push_back(Value::from_python(result));
                ++ip;
                break;
            }
            case DEF: {
#if defined(__GNUC__) || defined(__clang__)
            op_def:
#endif
                const auto function = funcs_.find(instr.args[0]);
                ip = function == funcs_.end() ? ip + 1 : function->second.second;
                break;
            }
            case LOAD_ARG:
            case LOAD_LOCAL: {
#if defined(__GNUC__) || defined(__clang__)
            op_load_arg:
            op_load_local:
#endif
                if (call_stack_.empty()) {
                    raise_space_error(
                        "UndefinedName",
                        instr.op == LOAD_ARG ? "LOAD_ARG outside function" : "LOAD_LOCAL outside function"
                    );
                }
                const auto slot = instr.args[0];
                const auto& frame = call_stack_.back();
                if (slot < 0 || slot >= static_cast<std::int64_t>(frame.locals.size())
                    || !frame.initialized[static_cast<std::size_t>(slot)]) {
                    const auto message = std::string(instr.op == LOAD_ARG ? "undefined arg slot " : "undefined local slot ")
                        + std::to_string(slot);
                    raise_space_error("UndefinedName", message, instr.line);
                }
                const auto& local = frame.locals[static_cast<std::size_t>(slot)];
                if (instr.op == LOAD_LOCAL) {
                    const auto value = local.to_python();
                    const auto cell_type = pybind11::module_::import("spacelang.vm_py").attr("Cell");
                    if (pybind11::isinstance(value, cell_type)) {
                        if (!value.attr("initialized").cast<bool>()) {
                            raise_space_error("UndefinedName", "undefined local slot " + std::to_string(slot), instr.line);
                        }
                        stack_.push_back(Value::from_python(value.attr("value")));
                        ++ip;
                        break;
                    }
                }
                stack_.push_back(local);
                ++ip;
                break;
            }
            case STORE_LOCAL: {
#if defined(__GNUC__) || defined(__clang__)
            op_store_local:
#endif
                if (call_stack_.empty() || instr.args[0] < 0) {
                    raise_space_error("UndefinedName", "STORE_LOCAL outside function");
                }
                auto& frame = call_stack_.back();
                const auto slot = static_cast<std::size_t>(instr.args[0]);
                if (frame.locals.size() <= slot) {
                    frame.locals.resize(slot + 1);
                    frame.initialized.resize(slot + 1, false);
                }
                auto value = pop("local value");
                if (frame.initialized[slot]) {
                    const auto local = frame.locals[slot].to_python();
                    const auto cell_type = pybind11::module_::import("spacelang.vm_py").attr("Cell");
                    if (pybind11::isinstance(local, cell_type)) {
                        local.attr("value") = value.to_python();
                        local.attr("initialized") = true;
                        frame.initialized[slot] = true;
                        ++ip;
                        break;
                    }
                }
                frame.locals[slot] = std::move(value);
                frame.initialized[slot] = true;
                ++ip;
                break;
            }
            case CELLIFY: {
#if defined(__GNUC__) || defined(__clang__)
            op_cellify:
#endif
                if (call_stack_.empty() || instr.args[0] < 0) {
                    raise_space_error("UndefinedName", "CELLIFY outside function", instr.line);
                }
                auto& frame = call_stack_.back();
                const auto slot = static_cast<std::size_t>(instr.args[0]);
                if (frame.locals.size() <= slot) {
                    frame.locals.resize(slot + 1);
                    frame.initialized.resize(slot + 1, false);
                }
                const auto cell_type = pybind11::module_::import("spacelang.vm_py").attr("Cell");
                if (!frame.initialized[slot]
                    || !pybind11::isinstance(frame.locals[slot].to_python(), cell_type)) {
                    const bool initialized = frame.initialized[slot];
                    const auto value = initialized
                        ? frame.locals[slot].to_python()
                        : pybind11::none();
                    frame.locals[slot] = Value::from_python(cell_type(value, initialized));
                }
                frame.initialized[slot] = true;
                ++ip;
                break;
            }
            case LOAD_CELL_REF: {
#if defined(__GNUC__) || defined(__clang__)
            op_load_cell_ref:
#endif
                if (call_stack_.empty() || instr.args[0] < 0) {
                    raise_space_error("UndefinedName", "LOAD_CELL_REF outside function", instr.line);
                }
                const auto slot = static_cast<std::size_t>(instr.args[0]);
                const auto& frame = call_stack_.back();
                if (slot >= frame.locals.size() || !frame.initialized[slot]) {
                    raise_space_error("UndefinedName", "local slot is not a cell", instr.line);
                }
                const auto cell = frame.locals[slot].to_python();
                const auto cell_type = pybind11::module_::import("spacelang.vm_py").attr("Cell");
                if (!pybind11::isinstance(cell, cell_type)) {
                    raise_space_error("UndefinedName", "local slot is not a cell", instr.line);
                }
                stack_.push_back(frame.locals[slot]);
                ++ip;
                break;
            }
            case LOAD_DEREF: {
#if defined(__GNUC__) || defined(__clang__)
            op_load_deref:
#endif
                if (call_stack_.empty() || instr.args[0] < 0) {
                    raise_space_error("UndefinedName", "LOAD_DEREF outside function", instr.line);
                }
                const auto index = static_cast<std::size_t>(instr.args[0]);
                const auto& cells = call_stack_.back().closure_cells;
                if (index >= static_cast<std::size_t>(cells.size())) {
                    raise_space_error("UndefinedName", "undefined closure cell", instr.line);
                }
                stack_.push_back(Value::from_python(cells[index]));
                ++ip;
                break;
            }
            case MAKE_CLOSURE:
            case MAKE_CLOSURE_SIG:
            case MAKE_CLOSURE_KWONLY:
            case MAKE_CLOSURE_ARGS:
            case MAKE_CLOSURE_POSONLY:
            {
#if defined(__GNUC__) || defined(__clang__)
            op_make_closure:
            op_make_closure_sig:
            op_make_closure_kwonly:
            op_make_closure_args:
            op_make_closure_posonly:
#endif
                const auto func_id = instr.args[0];
                if (funcs_.find(func_id) == funcs_.end()) {
                    raise_space_error("UndefinedFunc", "undefined user function " + std::to_string(func_id), instr.line);
                }
                const auto cell_count = static_cast<std::size_t>(instr.args[1]);
                if (instr.op == MAKE_CLOSURE) {
                    pybind11::list cells(cell_count);
                    for (std::size_t index = cell_count; index > 0; --index) {
                        cells[index - 1] = pop("closure cell").to_python();
                    }
                    const auto closure_type = pybind11::module_::import("spacelang.vm_py").attr("Closure");
                    stack_.push_back(Value::from_python(closure_type(func_id, cells, instr.args[2])));
                    ++ip;
                    break;
                }
                if (instr.op == MAKE_CLOSURE_KWONLY) {
                    const auto positional_count = static_cast<std::size_t>(instr.args[2]);
                    const auto keyword_only_count = static_cast<std::size_t>(instr.args[3]);
                    const auto positional_default_count = static_cast<std::size_t>(instr.args[4]);
                    const auto keyword_default_count = static_cast<std::size_t>(instr.args[5]);
                    if (positional_default_count > positional_count) {
                        raise_space_error("RuntimeError", "closure positional defaults exceed parameter count", instr.line);
                    }
                    std::vector<std::pair<std::int64_t, pybind11::object>> keyword_defaults(keyword_default_count);
                    for (std::size_t index = keyword_default_count; index > 0; --index) {
                        auto value = pop("keyword-only default value").to_python();
                        const auto name_id = pop("keyword-only default name").to_python().cast<std::int64_t>();
                        keyword_defaults[index - 1] = {name_id, value};
                    }
                    std::vector<pybind11::object> positional_defaults(positional_default_count);
                    for (std::size_t index = positional_default_count; index > 0; --index) {
                        positional_defaults[index - 1] = pop("closure default").to_python();
                    }
                    pybind11::list parameter_names(positional_count + keyword_only_count);
                    for (std::size_t index = static_cast<std::size_t>(parameter_names.size()); index > 0; --index) {
                        const auto name_id = pop("closure parameter name").to_python().cast<std::int64_t>();
                        parameter_names[index - 1] = pybind11::str(name(name_id));
                    }
                    pybind11::dict defaults;
                    for (std::size_t index = 0; index < positional_default_count; ++index) {
                        const auto parameter_index = positional_count - positional_default_count + index;
                        defaults[pybind11::reinterpret_borrow<pybind11::object>(parameter_names[parameter_index])] =
                            positional_defaults[index];
                    }
                    for (const auto& entry : keyword_defaults) {
                        defaults[pybind11::str(name(entry.first))] = entry.second;
                    }
                    pybind11::list cells(cell_count);
                    for (std::size_t index = cell_count; index > 0; --index) {
                        cells[index - 1] = pop("closure cell").to_python();
                    }
                    const auto closure_type = pybind11::module_::import("spacelang.vm_py").attr("Closure");
                    stack_.push_back(
                        Value::from_python(closure_type(func_id, cells, parameter_names, defaults, positional_count))
                    );
                    ++ip;
                    break;
                }
                if (instr.op == MAKE_CLOSURE_ARGS || instr.op == MAKE_CLOSURE_POSONLY) {
                    const bool has_posonly = instr.op == MAKE_CLOSURE_POSONLY;
                    const auto positional_only_count =
                        has_posonly ? static_cast<std::size_t>(instr.args[2]) : 0;
                    const auto positional_count =
                        static_cast<std::size_t>(instr.args[has_posonly ? 3 : 2]);
                    const auto keyword_only_count =
                        static_cast<std::size_t>(instr.args[has_posonly ? 4 : 3]);
                    const auto positional_default_count =
                        static_cast<std::size_t>(instr.args[has_posonly ? 5 : 4]);
                    const auto keyword_default_count =
                        static_cast<std::size_t>(instr.args[has_posonly ? 6 : 5]);
                    const auto varargs_index = has_posonly ? 7 : 6;
                    const auto kwargs_index = has_posonly ? 8 : 7;
                    const bool has_varargs = instr.args[varargs_index] == 1;
                    const bool has_kwargs = instr.args[kwargs_index] == 1;
                    if (instr.args[varargs_index] > 1 || instr.args[kwargs_index] > 1
                        || positional_only_count > positional_count
                        || positional_default_count > positional_count
                        || keyword_default_count > keyword_only_count) {
                        raise_space_error("RuntimeError", "invalid variadic closure signature", instr.line);
                    }
                    std::int64_t kwarg_name_id = -1;
                    std::int64_t vararg_name_id = -1;
                    if (has_kwargs) {
                        kwarg_name_id = pop("kwarg name").to_python().cast<std::int64_t>();
                    }
                    if (has_varargs) {
                        vararg_name_id = pop("vararg name").to_python().cast<std::int64_t>();
                    }
                    std::vector<std::pair<std::int64_t, pybind11::object>> keyword_defaults(keyword_default_count);
                    for (std::size_t index = keyword_default_count; index > 0; --index) {
                        auto value = pop("keyword-only default value").to_python();
                        const auto name_id = pop("keyword-only default name").to_python().cast<std::int64_t>();
                        keyword_defaults[index - 1] = {name_id, value};
                    }
                    std::vector<pybind11::object> positional_defaults(positional_default_count);
                    for (std::size_t index = positional_default_count; index > 0; --index) {
                        positional_defaults[index - 1] = pop("closure default").to_python();
                    }
                    pybind11::list parameter_names(positional_count + keyword_only_count);
                    for (std::size_t index = static_cast<std::size_t>(parameter_names.size()); index > 0; --index) {
                        const auto name_id = pop("closure parameter name").to_python().cast<std::int64_t>();
                        parameter_names[index - 1] = pybind11::str(name(name_id));
                    }
                    pybind11::dict defaults;
                    for (std::size_t index = 0; index < positional_default_count; ++index) {
                        const auto parameter_index = positional_count - positional_default_count + index;
                        defaults[pybind11::reinterpret_borrow<pybind11::object>(parameter_names[parameter_index])] =
                            positional_defaults[index];
                    }
                    for (const auto& entry : keyword_defaults) {
                        defaults[pybind11::str(name(entry.first))] = entry.second;
                    }
                    pybind11::list cells(cell_count);
                    for (std::size_t index = cell_count; index > 0; --index) {
                        cells[index - 1] = pop("closure cell").to_python();
                    }
                    const auto closure_type = pybind11::module_::import("spacelang.vm_py").attr("Closure");
                    stack_.push_back(Value::from_python(
                        closure_type(
                            func_id,
                            cells,
                            parameter_names,
                            defaults,
                            positional_count,
                            has_varargs ? pybind11::cast(name(vararg_name_id)) : pybind11::none(),
                            has_kwargs ? pybind11::cast(name(kwarg_name_id)) : pybind11::none(),
                            positional_only_count
                        )
                    ));
                    ++ip;
                    break;
                }
                const auto parameter_count = static_cast<std::size_t>(instr.args[2]);
                const auto default_count = static_cast<std::size_t>(instr.args[3]);
                if (default_count > parameter_count) {
                    raise_space_error("RuntimeError", "closure default count exceeds parameter count", instr.line);
                }
                std::vector<pybind11::object> default_values(default_count);
                for (std::size_t index = default_count; index > 0; --index) {
                    default_values[index - 1] = pop("closure default").to_python();
                }
                pybind11::list parameter_names(parameter_count);
                for (std::size_t index = parameter_count; index > 0; --index) {
                    parameter_names[index - 1] = pybind11::str(name(pop("closure parameter name").to_python().cast<std::int64_t>()));
                }
                pybind11::dict defaults;
                for (std::size_t index = 0; index < default_count; ++index) {
                    const auto parameter_index = parameter_count - default_count + index;
                    defaults[pybind11::reinterpret_borrow<pybind11::object>(parameter_names[parameter_index])] =
                        default_values[index];
                }
                pybind11::list cells(cell_count);
                for (std::size_t index = cell_count; index > 0; --index) {
                    cells[index - 1] = pop("closure cell").to_python();
                }
                const auto closure_type = pybind11::module_::import("spacelang.vm_py").attr("Closure");
                stack_.push_back(Value::from_python(closure_type(func_id, cells, parameter_names, defaults)));
                ++ip;
                break;
            }
            case RET: {
#if defined(__GNUC__) || defined(__clang__)
            op_ret:
#endif
                auto value = pop("return value");
                if (call_stack_.empty()) {
                    return value.to_python();
                }
                const auto return_ip = call_stack_.back().return_ip;
                call_stack_.pop_back();
                stack_.push_back(std::move(value));
                ip = return_ip;
                break;
            }
            case PUSH_INT:
#if defined(__GNUC__) || defined(__clang__)
            op_push_int:
#endif
                stack_.emplace_back(instr.args[0]);
                ++ip;
                break;
            case PUSH_NONE:
#if defined(__GNUC__) || defined(__clang__)
            op_push_none:
#endif
                stack_.emplace_back();
                ++ip;
                break;
            case OP: {
#if defined(__GNUC__) || defined(__clang__)
            op_operation:
#endif
                const auto right = pop("rhs");
                const auto left = pop("lhs");
                if (instr.args[0] < 1 || instr.args[0] > 15) {
                    raise_space_error("ParseError", "unsupported op_id " + std::to_string(instr.args[0]));
                }
                stack_.push_back(numeric_binary(instr.args[0], left, right));
                ++ip;
                break;
            }
            case STACK:
#if defined(__GNUC__) || defined(__clang__)
            op_stack:
#endif
                switch (instr.args[0]) {
                    case 1:
                        if (stack_.empty()) {
                            raise_space_error("StackUnderflow", "dup requires 1 value");
                        }
                        stack_.push_back(stack_.back());
                        break;
                    case 2: {
                        if (stack_.size() < 2) {
                            raise_space_error("StackUnderflow", "swap requires 2 values");
                        }
                        const auto first = pop("swap");
                        const auto second = pop("swap");
                        stack_.push_back(first);
                        stack_.push_back(second);
                        break;
                    }
                    case 3:
                        if (stack_.empty()) {
                            raise_space_error("StackUnderflow", "drop requires 1 value");
                        }
                        stack_.pop_back();
                        break;
                    case 4:
                        if (stack_.size() < 2) {
                            raise_space_error("StackUnderflow", "over requires 2 values");
                        }
                        stack_.push_back(stack_[stack_.size() - 2]);
                        break;
                    case 5: {
                        if (stack_.size() < 3) {
                            raise_space_error("StackUnderflow", "rot requires 3 values");
                        }
                        const auto c = pop("rot");
                        const auto b = pop("rot");
                        const auto a = pop("rot");
                        stack_.push_back(b);
                        stack_.push_back(c);
                        stack_.push_back(a);
                        break;
                    }
                    default:
                        raise_space_error("ParseError", "unsupported stack op " + std::to_string(instr.args[0]));
                }
                ++ip;
                break;
            case JMP:
#if defined(__GNUC__) || defined(__clang__)
            op_jmp:
#endif
                if (instr.args[0] < 0 || instr.args[0] >= static_cast<std::int64_t>(instrs_.size())) {
                    raise_space_error(
                        "JumpOutOfRange",
                        "jump target " + std::to_string(instr.args[0]) + " out of range"
                    );
                }
                ip = instr.args[0];
                break;
            case JZ:
            case JNZ: {
#if defined(__GNUC__) || defined(__clang__)
            op_jz:
            op_jnz:
#endif
                if (instr.args[0] < 0 || instr.args[0] >= static_cast<std::int64_t>(instrs_.size())) {
                    raise_space_error(
                        "JumpOutOfRange",
                        "jump target " + std::to_string(instr.args[0]) + " out of range"
                    );
                }
                const Value condition_value = pop("condition");
                bool condition = false;
                if (condition_value.tag == Value::Tag::INT) {
                    condition = condition_value.data.i != 0;
                } else {
                    condition = condition_value.truthy();
                }
                const bool jump = instr.op == JZ ? !condition : condition;
                ip = jump ? instr.args[0] : ip + 1;
                break;
            }
            case SETUP_WITH:
#if defined(__GNUC__) || defined(__clang__)
            op_setup_with:
#endif
                with_stack_.push_back(pop("context manager"));
                ++ip;
                break;
            case RAISE: {
#if defined(__GNUC__) || defined(__clang__)
            op_raise:
#endif
                auto exception = pop("exception").to_python();
                if (!PyExceptionInstance_Check(exception.ptr())) {
                    PyErr_SetString(PyExc_RuntimeError, pybind11::str(exception).cast<std::string>().c_str());
                } else {
                    PyErr_SetObject(
                        reinterpret_cast<PyObject*>(Py_TYPE(exception.ptr())),
                        exception.ptr()
                    );
                }
                throw pybind11::error_already_set();
            }
            case TRY: {
#if defined(__GNUC__) || defined(__clang__)
            op_try:
#endif
                const auto catch_ip = instr.args[0];
                const auto finally_ip = instr.args[1];
                for (const auto target : {catch_ip, finally_ip}) {
                    if (target != 0 && (target < 0 || target >= static_cast<std::int64_t>(instrs_.size()))) {
                        raise_space_error(
                            "JumpOutOfRange",
                            "try target " + std::to_string(target) + " out of range",
                            instr.line
                        );
                    }
                }
                auto end_ip = ip + 1;
                for (const auto& entry : try_table_) {
                    if (std::get<0>(entry) == ip) {
                        end_ip = std::get<1>(entry);
                        break;
                    }
                }
                try_stack_.push_back(TryFrame{
                    catch_ip,
                    finally_ip,
                    end_ip,
                    end_ip,
                    call_stack_.size(),
                    stack_.size(),
                });
                ++ip;
                break;
            }
            case END_TRY: {
#if defined(__GNUC__) || defined(__clang__)
            op_end_try:
#endif
                if (try_stack_.empty()) {
                    raise_space_error("ParseError", "END_TRY without TRY");
                }
                auto& frame = try_stack_.back();
                if (frame.stage == TryFrame::Stage::BODY || frame.stage == TryFrame::Stage::CATCH) {
                    if (frame.stage == TryFrame::Stage::CATCH) {
                        frame.exception = pybind11::none();
                    }
                    if (frame.finally_ip != 0) {
                        frame.stage = TryFrame::Stage::FINALLY;
                        frame.saved_ip = frame.end_ip;
                        ip = frame.finally_ip;
                    } else {
                        ip = frame.end_ip;
                        try_stack_.pop_back();
                    }
                } else {
                    const auto exception = frame.exception;
                    const auto saved_ip = frame.saved_ip;
                    try_stack_.pop_back();
                    if (!exception.is_none()) {
                        raise_exception(exception);
                    }
                    ip = saved_ip;
                }
                break;
            }
            case HALT:
#if defined(__GNUC__) || defined(__clang__)
            op_halt:
#endif
                if (stack_.empty()) {
                    return pybind11::none();
                }
                return pop("halt result").to_python();
            default:
                throw pybind11::value_error("opcode is not implemented by the native VM yet");
        }
        } catch (pybind11::error_already_set& exception) {
            const auto value = pybind11::reinterpret_borrow<pybind11::object>(exception.value());
            dispatch_exception(value);
        } catch (const pybind11::builtin_exception& exception) {
            exception.set_error();
            pybind11::error_already_set python_exception;
            const auto value = pybind11::reinterpret_borrow<pybind11::object>(python_exception.value());
            dispatch_exception(value);
        }
    }
    if (ip < 0) {
        throw pybind11::value_error("instruction pointer out of range");
    }
    return pybind11::none();
}

pybind11::list VM::stack() const {
    pybind11::list result;
    for (const auto& value : stack_) {
        result.append(value.to_python());
    }
    return result;
}

pybind11::dict VM::globals() const {
    return globals_;
}

}  // namespace spacelang
