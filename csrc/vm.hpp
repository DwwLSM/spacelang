#pragma once

#include <cstdint>
#include <string>
#include <tuple>
#include <unordered_map>
#include <utility>
#include <vector>

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include "ir.hpp"
#include "value.hpp"

namespace spacelang {

class VM {
public:
    explicit VM(pybind11::object program);
    ~VM();

    // The cached PyObject* members below are owned, so copying or moving the
    // interpreter would double-free them.
    VM(const VM&) = delete;
    VM& operator=(const VM&) = delete;
    VM(VM&&) = delete;
    VM& operator=(VM&&) = delete;

    pybind11::object run();
    pybind11::list stack() const;
    pybind11::dict globals() const;

private:
    struct Frame {
        std::int64_t func_id;
        std::int64_t return_ip;
        std::vector<Value> locals;
        std::vector<bool> initialized;
        // A list of cells, created on demand: most functions never close over
        // anything, and pybind11::list default-constructs an empty list.
        pybind11::object closure_cells;
    };

    struct TryFrame {
        enum class Stage { BODY, CATCH, FINALLY };
        std::int64_t catch_ip;
        std::int64_t finally_ip;
        std::int64_t end_ip;
        std::int64_t saved_ip;
        std::size_t call_depth;
        std::size_t stack_depth;
        Stage stage = Stage::BODY;
        pybind11::object exception = pybind11::none();
    };

    std::vector<Instr> instrs_;
    std::vector<Value> stack_;
    std::unordered_map<std::int64_t, std::string> names_;
    std::unordered_map<std::int64_t, std::pair<std::int64_t, std::int64_t>> funcs_;
    std::vector<std::tuple<std::int64_t, std::int64_t, std::int64_t, std::int64_t>> try_table_;
    std::vector<Frame> call_stack_;
    std::vector<TryFrame> try_stack_;
    std::vector<Value> with_stack_;
    pybind11::dict globals_;
    std::int64_t current_ip_ = 0;

    // Python objects the instruction handlers need. Resolved once in the
    // constructor and held as strong references: importing a module inside the
    // dispatch loop cost about 250 ns per LOAD_LOCAL/STORE_LOCAL, which made
    // local variable access five times slower than global access.
    PyObject* cell_type_ = nullptr;
    PyObject* closure_type_ = nullptr;
    PyObject* bytes_type_ = nullptr;
    PyObject* do_import_ = nullptr;
    PyObject* errors_module_ = nullptr;
    PyObject* space_error_type_ = nullptr;
    PyObject* runtime_error_type_ = nullptr;
    std::vector<PyObject*> builtins_;
    std::unordered_map<std::int64_t, PyObject*> extra_builtins_;
    // Interned names for the global table, for attribute access and for the
    // three Cell attributes, so handlers never build a Python string.
    std::unordered_map<std::int64_t, PyObject*> name_objects_;
    PyObject* cell_value_name_ = nullptr;
    PyObject* cell_initialized_name_ = nullptr;

    void cache_python_objects();
    bool is_cell(const Value& value) const;
    PyObject* name_object(std::int64_t name_id) const;
    Value pop(const char* name);
    const std::string& name(std::int64_t name_id) const;
    [[noreturn]] void raise_space_error(
        const char* type,
        const std::string& message,
        std::int32_t line = 0
    ) const;
    pybind11::object builtin(std::int64_t func_id);
    bool route_exception(const pybind11::object& exception, std::int64_t& ip);
    void raise_exception(const pybind11::object& exception);
};

}  // namespace spacelang
