#pragma once

#include <vector>
#include <string>
#include <tuple>
#include <unordered_map>

#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include "ir.hpp"
#include "value.hpp"

namespace spacelang {

class VM {
public:
    explicit VM(pybind11::object program);

    pybind11::object run();
    pybind11::list stack() const;
    pybind11::dict globals() const;

private:
    struct Frame {
        std::int64_t func_id;
        std::int64_t return_ip;
        std::vector<Value> locals;
        std::vector<bool> initialized;
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

    Value pop(const char* name);
    const std::string& name(std::int64_t name_id) const;
    [[noreturn]] void raise_space_error(
        const char* type,
        const std::string& message,
        std::int32_t line = 0
    ) const;
    pybind11::object builtin(std::int64_t func_id) const;
    bool route_exception(const pybind11::object& exception, std::int64_t& ip);
    void raise_exception(const pybind11::object& exception);
};

}  // namespace spacelang
