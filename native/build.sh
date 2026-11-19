#!/bin/sh
# Build the standalone SpaceLang runner (no Python required at runtime).
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
${CXX:-g++} -O2 -std=c++17 -static -o "$here/spvm" "$here/spvm.cpp"
echo "built $here/spvm"
