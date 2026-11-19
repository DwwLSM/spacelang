cmake_minimum_required(VERSION 3.18)
project(spacelang_cpp LANGUAGES CXX)

find_package(Python REQUIRED COMPONENTS Interpreter Development.Module)
find_package(pybind11 CONFIG REQUIRED)

pybind11_add_module(_spacelang_cpp MODULE
    csrc/binding.cpp
    csrc/vm.cpp
)
target_compile_features(_spacelang_cpp PRIVATE cxx_std_17)
target_include_directories(_spacelang_cpp PRIVATE csrc)
install(TARGETS _spacelang_cpp LIBRARY DESTINATION spacelang)
