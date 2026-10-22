#pragma once

#include <cstdint>
#include <utility>

#include <Python.h>
#include <pybind11/pybind11.h>

namespace spacelang {

namespace py = pybind11;

struct Value {
    enum class Tag : std::uint8_t { INT, FLOAT, BOOL, NONE, PYOBJ };

    union Payload {
        std::int64_t i;
        double f;
        bool b;
        PyObject* obj;

        Payload() : i(0) {}
    };

    Tag tag = Tag::NONE;
    Payload data;

    Value() = default;
    explicit Value(std::int64_t value) : tag(Tag::INT) { data.i = value; }
    explicit Value(double value) : tag(Tag::FLOAT) { data.f = value; }
    explicit Value(bool value) : tag(Tag::BOOL) { data.b = value; }

    static Value from_python(py::handle value) {
        if (value.is_none()) {
            return Value();
        }
        if (PyBool_Check(value.ptr())) {
            return Value(value.ptr() == Py_True);
        }
        if (PyLong_Check(value.ptr())) {
            const auto integer = PyLong_AsLongLong(value.ptr());
            if (PyErr_Occurred()) {
                PyErr_Clear();
            } else {
                return Value(static_cast<std::int64_t>(integer));
            }
        }
        if (PyFloat_Check(value.ptr())) {
            return Value(PyFloat_AS_DOUBLE(value.ptr()));
        }
        Value result;
        result.tag = Tag::PYOBJ;
        result.data.obj = value.ptr();
        Py_INCREF(result.data.obj);
        return result;
    }

    Value(const Value& other) : tag(other.tag), data(other.data) {
        if (tag == Tag::PYOBJ) {
            Py_INCREF(data.obj);
        }
    }

    Value(Value&& other) noexcept : tag(other.tag), data(other.data) {
        other.tag = Tag::NONE;
    }

    Value& operator=(Value other) noexcept {
        swap(other);
        return *this;
    }

    ~Value() {
        if (tag == Tag::PYOBJ) {
            Py_DECREF(data.obj);
        }
    }

    void swap(Value& other) noexcept {
        const auto temporary = data;
        data = other.data;
        other.data = temporary;
        const auto previous_tag = tag;
        tag = other.tag;
        other.tag = previous_tag;
    }

    py::object to_python() const {
        switch (tag) {
            case Tag::INT:
                return py::int_(data.i);
            case Tag::FLOAT:
                return py::float_(data.f);
            case Tag::BOOL:
                return py::bool_(data.b);
            case Tag::NONE:
                return py::none();
            case Tag::PYOBJ:
                return py::reinterpret_borrow<py::object>(data.obj);
        }
        throw py::type_error("invalid SpaceLang Value tag");
    }

    bool truthy() const {
        switch (tag) {
            case Tag::INT:
                return data.i != 0;
            case Tag::FLOAT:
                return data.f != 0.0;
            case Tag::BOOL:
                return data.b;
            case Tag::NONE:
                return false;
            case Tag::PYOBJ: {
                const int result = PyObject_IsTrue(data.obj);
                if (result < 0) {
                    throw py::error_already_set();
                }
                return result != 0;
            }
        }
        return false;
    }
};

}  // namespace spacelang
