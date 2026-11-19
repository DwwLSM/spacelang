# Build compiler.exe: the SpaceLang compiler + native VM, no Python at runtime.
#
#   powershell -ExecutionPolicy Bypass -File native/build_compiler.ps1
#
# Stage 0 uses Python once (the ordinary toolchain) to compile native/spc.py
# into native/spc.sp.  After that, compiler.exe is self-contained.
#
# Environment overrides: CXX (default g++), PYTHON (default py, then python).
$ErrorActionPreference = "Stop"

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Split-Path -Parent $here
$compiler = if ($env:CXX) { $env:CXX } else { "g++" }

$python = $env:PYTHON
if (-not $python) {
    $python = if (Get-Command py -ErrorAction SilentlyContinue) { "py" } else { "python" }
}

# -S keeps an unrelated editable install from shadowing this checkout.
$env:PYTHONPATH = $root

Push-Location $root
try {
    & $python -S -m spacelang.main compile-py "$here/spc.py" "$here/spc.sp"
    if ($LASTEXITCODE -ne 0) { throw "compile-py failed" }
    & $python -S "$here/make_blob.py" "$here/spc.sp" "$here/spc_blob.h"
    if ($LASTEXITCODE -ne 0) { throw "make_blob failed" }
    & $compiler -O2 -std=c++17 -static -o "$here/compiler.exe" "$here/compiler.cpp"
    if ($LASTEXITCODE -ne 0) { throw "g++ failed" }
} finally {
    Pop-Location
}

Write-Host ("built {0} ({1:N0} bytes)" -f "$here/compiler.exe", (Get-Item "$here/compiler.exe").Length)
