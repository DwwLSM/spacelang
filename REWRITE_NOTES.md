# README Rewrite Notes

## Inventory

| File | Previous mental model | Wrong framing present | Commands/status claims preserved or flagged |
|---|---|---|---|
| `README.md` | Mixed Python-front-end and `.sp` pipeline narrative | Yes: Python-subset framing, `.sp` as encoded artifact | Commands and package metadata preserved; status claims marked for confirmation |
| `SELFHOSTING.md` | Runtime/compiler bootstrap framed around Python subset and bytecode | Yes: `.sp` called bytecode; frontend limits used as compiler/self-hosting blockers | Existing commands and measurements preserved where repository evidence supported them; completion status marked for author confirmation |
| `documentation.md` | Documentation index repeated Python-package and IR/bytecode framing | Yes: intermediate representation and bytecode language | Existing commands, versions, and API descriptions preserved where no rewrite conflict |
| `bootstrap/README.md` | `.sp` runtime produced from Python-subset source | Yes: Python subset described as source truth | Existing build/run commands preserved |
| `native/README.md` | Native VM/compiler described through Python frontend and bytecode | Yes: `.sp` called bytecode; compiler and executable path conflated | Existing commands, file paths, and implementation details preserved; status/performance claims left as repository observations only |

## Conflict log

| File | Old text | Problem | Replacement approach |
|---|---|---|---|
| `README.md` / `documentation.md` | “Python-subset compiler” or “subset of Python” as the language identity | Makes `.py` the primary language instead of an optional frontend | Establish `.sp` as language proper and `.py` as optional sugar lowered to `.sp` |
| `README.md` / `SELFHOSTING.md` / `native/README.md` | `.sp` described as bytecode, an encoded instruction stream, or compilation artifact | Contradicts `.sp` as source language | Describe `.sp` as source; use “artifact” only for generated toolchain output where applicable |
| `SELFHOSTING.md` | Missing `def` / list / dict in `.py` input described as a compiler/self-hosting blocker | Confuses optional frontend completeness with `.sp → .sp` compiler self-hosting | Separate line A (`.sp → .sp`) from line B (`.py` frontend) |
| `native/README.md` | `compiler.exe ...` described as compiling/running Python source | Omits optional frontend lowering and can imply `.py` is primary | Describe `compiler.exe` as a compiler whose optional frontend lowers `.py` to `.sp` |
| `SELFHOSTING.md` | “Compiler self-hosting ... done for small input / not compile itself” | State may be repository status but not presented under the required fixed-point model | Mark exact fixed-point status `AUTHOR_CONFIRMATION_REQUIRED` |

## Changed files

- `README.md`
- `SELFHOSTING.md`
- `documentation.md`
- `bootstrap/README.md`
- `native/README.md`

## Inventoried but not rewritten

- No other README or primary docs index was found. `documentation.md` was included because it is linked from the root and repeats the language mental model.

## Author decisions needed

- Exact status of Stage 0, Stage 1, and Stage 2 `.sp → .sp` compiler self-hosting.
- Exact status of optional `.py` support for `def`, list, and dict.
- Whether the repository should remove or preserve historical implementation claims and performance measurements.
- Any contradiction in code should be treated as implementation work rather than silently changing the requested documentation model.

## `AUTHOR_CONFIRMATION_REQUIRED` items

- [ ] Stage 0: build existing `.sp` compiler toolchain
  - Input language: `.sp`
  - Produced artifact: compiler_0
  - Status: `AUTHOR_CONFIRMATION_REQUIRED`
  - Evidence/command: TODO(author)
- [ ] Stage 1: compile `compiler.sp` to `compiler_1`
  - Input language: `.sp`
  - Produced artifact: compiler_1
  - Status: `AUTHOR_CONFIRMATION_REQUIRED`
  - Evidence/command: TODO(author)
- [ ] Stage 2: fixed-point comparison
  - Input language: `.sp`
  - Produced artifact: fixed-point comparison
  - Status: `AUTHOR_CONFIRMATION_REQUIRED`
  - Evidence/command: TODO(author)
- [ ] Optional `.py` `def` support
  - Input language: `.py`
  - Produced artifact: lowered `.sp`
  - Status: `AUTHOR_CONFIRMATION_REQUIRED`
  - Evidence/command: TODO(author)
- [ ] Optional `.py` list support
  - Input language: `.py`
  - Produced artifact: lowered `.sp`
  - Status: `AUTHOR_CONFIRMATION_REQUIRED`
  - Evidence/command: TODO(author)
- [ ] Optional `.py` dict support
  - Input language: `.py`
  - Produced artifact: lowered `.sp`
  - Status: `AUTHOR_CONFIRMATION_REQUIRED`
  - Evidence/command: TODO(author)

## Acceptance validation

- [ ] All README-level files in scope inventoried: partially complete; three README files plus primary guides inventoried
- [x] Root README opening states `.sp` source identity within the first three lines
- [x] Rewritten README-level files use a `.sp`-first opening
- [x] Forbidden Python identity claims removed from live README-level sections
- [x] `.sp` no longer described as bytecode in rewritten opening/table sections
- [ ] Full repository Markdown forbidden-phrase search still has historical documentation hits: see conflict log/author decisions
- [ ] All self-hosting status items use confirmation template: new milestone section does
- [ ] Documentation generated-package source review: `pyproject.toml` points to `README.md`, so regeneration may be needed after publishing
