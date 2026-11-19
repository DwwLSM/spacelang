# Build the standalone SpaceLang runner (no Python required at runtime).
#
#   powershell -ExecutionPolicy Bypass -File native/build.ps1
#
# Needs a C++17 compiler on PATH (g++/clang++/cl).  `-static` makes the result
# independent of the compiler's runtime DLLs; drop it if your toolchain lacks
# static libstdc++.
$ErrorActionPreference = "Stop"

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$compiler = if ($env:CXX) { $env:CXX } else { "g++" }
$output = Join-Path $here "spvm.exe"

& $compiler -O2 -std=c++17 -static -o $output (Join-Path $here "spvm.cpp")
if ($LASTEXITCODE -ne 0) {
    Write-Error "build failed ($compiler exited with $LASTEXITCODE)"
}

Write-Host ("built {0} ({1:N0} bytes)" -f $output, (Get-Item $output).Length)
