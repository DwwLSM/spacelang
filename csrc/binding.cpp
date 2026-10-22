#include <pybind11/pybind11.h>

#include "vm.hpp"

PYBIND11_MODULE(_spacelang_cpp, module) {
    pybind11::class_<spacelang::VM>(module, "VM")
        .def(pybind11::init<pybind11::object>())
        .def("run", &spacelang::VM::run)
        .def_property_readonly("stack", &spacelang::VM::stack)
        .def_property_readonly("globals", &spacelang::VM::globals);
}
