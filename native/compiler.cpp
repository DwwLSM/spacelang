// compiler.cpp -- `compiler.exe program.py`
//
// A self-contained Python-subset compiler with no Python dependency.  It embeds
// `spc.sp` (a compiler written in SpaceLang, itself compiled from native/spc.py
// by the ordinary toolchain) plus the native VM from spvm.cpp:
//
//   1. run the embedded SpaceLang compiler on the .py source -> <name>.sp
//   2. decode and execute that .sp program on the embedded VM
//
// So the chain is: compiler.exe -> spc.sp -> program.sp -> results.
//
// Usage:
//   compiler.exe program.py            compile to program.sp, then run it
//   compiler.exe program.py out.sp     compile only

#define SPVM_NO_MAIN
#include "spvm.cpp"
#include "spc_blob.h"

namespace {

std::string replace_suffix(const std::string& path, const std::string& suffix) {
    const std::size_t slash = path.find_last_of("/\\");
    const std::size_t dot = path.find_last_of('.');
    if (dot != std::string::npos && (slash == std::string::npos || dot > slash)) {
        return path.substr(0, dot) + suffix;
    }
    return path + suffix;
}

}  // namespace

int main(int argc, char** argv) {
    if (argc < 2) {
        std::fprintf(stderr, "usage: compiler PROGRAM.py [OUTPUT.sp]\n");
        return 2;
    }
    const std::string source = argv[1];
    const bool compile_only = argc > 2;
    const std::string output = compile_only ? argv[2] : replace_suffix(source, ".sp");

    // Stage 1: the SpaceLang compiler turns source into bytecode.
    std::vector<std::string> arguments{source, output};
    const std::string compiler_text(
        reinterpret_cast<const char*>(kCompilerBlob), kCompilerBlobSize);
    const int compiled = spvm_run_text(compiler_text, "spc.sp", arguments);
    if (compiled != 0) {
        std::fprintf(stderr, "compiler: could not compile %s\n", source.c_str());
        return compiled;
    }

    std::ifstream check(output, std::ios::binary);
    if (!check) {
        std::fprintf(stderr, "compiler: %s was not written\n", output.c_str());
        return 1;
    }
    check.close();
    if (compile_only) {
        std::printf("wrote %s\n", output.c_str());
        return 0;
    }

    // Stage 2: run the freshly compiled program on the same VM.
    try {
        return spvm_run_text(read_file(output), output, {});
    } catch (const std::exception& error) {
        std::fprintf(stderr, "compiler: %s\n", error.what());
        return 1;
    }
}
