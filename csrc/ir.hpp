#pragma once

#include <cstdint>
#include <vector>

namespace spacelang {

struct Instr {
    std::uint8_t op = 0;
    std::vector<std::int64_t> args;
    std::int32_t line = 0;
};

}  // namespace spacelang
