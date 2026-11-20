"""The native engine must be built, not silently skipped.

``tests/test_vm_cpp.py`` and ``tests/test_differential.py`` both begin with
``pytest.importorskip("spacelang._spacelang_cpp")``. That keeps the suite usable
on machines without a compiler, but it also means a broken build turns 99 parity
tests into skips while ``pytest -q`` still reports success. This module has no
skip guard on purpose: if the extension is missing, collection fails.
"""

import spacelang._spacelang_cpp


def test_native_extension_is_present() -> None:
    assert spacelang._spacelang_cpp.VM is not None
