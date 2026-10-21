from __future__ import annotations

import builtins as _pybuiltins
import math
import random
import re
import sys


def _builtin_names():
    return {
        0: print,
        1: input,
        2: len,
        3: int,
        4: float,
        5: str,
        6: bool,
        7: abs,
        8: range,
        9: type,
        10: open,
        11: getattr,
        12: setattr,
        13: callable,
        14: repr,
        15: isinstance,
    }


BUILTINS = _builtin_names()
MATH_FUNCS = {
    1000: math.sqrt,
    1001: math.sin,
    1002: math.cos,
    1003: math.tan,
    1004: math.floor,
    1005: math.ceil,
    1006: math.fabs,
    1007: math.exp,
    1008: math.log,
}
RANDOM_FUNCS = {
    2000: random.random,
    2001: random.randint,
}
OS_FUNCS = {3000: __import__("os").system}
RE_FUNCS = {4000: re.compile}
SYS_FUNCS = {5000: sys.exit}

ALL_BUILTINS = {
    **BUILTINS,
    **MATH_FUNCS,
    **RANDOM_FUNCS,
    **OS_FUNCS,
    **RE_FUNCS,
    **SYS_FUNCS,
}


__all__ = ["BUILTINS", "MATH_FUNCS", "RANDOM_FUNCS", "OS_FUNCS", "RE_FUNCS", "SYS_FUNCS", "ALL_BUILTINS"]
