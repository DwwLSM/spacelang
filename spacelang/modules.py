from __future__ import annotations

import importlib
import os
import random
import re
import sys

from .errors import UndefinedModule

MODULES = {
    0: "math",
    1: "random",
    2: "os",
    3: "re",
    4: "sys",
}


def do_import(mid: int, globals_: dict) -> object:
    name = MODULES.get(mid)
    if name is None:
        raise UndefinedModule(line=0, ip=mid, msg=f"undefined module id {mid}")
    if name not in sys.modules:
        sys.modules[name] = importlib.import_module(name)
    globals_.setdefault(name, sys.modules[name])
    return sys.modules[name]


__all__ = ["MODULES", "do_import"]
