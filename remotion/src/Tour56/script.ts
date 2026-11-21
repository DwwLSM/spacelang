/**
 * Single source of truth for every string, code listing and number that
 * appears in the 56-second SpaceLang tour (`SpaceLangTour56`).
 *
 * Nothing in `scenes/` should hard-code copy: if a word or figure is on
 * screen, it lives here. Caption lines are kept short so the burned-in
 * subtitle band never wraps past `MAX_CAPTION_CHARS`.
 */

export const VIDEO = {
  width: 1920,
  height: 1080,
  fps: 30,
  frames: 1680,
  sceneFrames: 120,
  sceneCount: 13,
} as const;

/** Hard limit for one burned-in caption line at 1920x1080. */
export const MAX_CAPTION_CHARS = 42;

/** Frames the incoming scene fades in for 00 -> 01 and 10 -> 11. */
export const FADE_FRAMES = 6;

export type RelativeCaptionCue = {
  /** First frame of the cue, relative to the scene start. */
  from: number;
  /** End frame of the cue, relative to the scene start (exclusive). */
  to: number;
  lines: readonly string[];
  /** Optional smaller second line, e.g. a status tag. */
  small?: string;
};

/* ------------------------------------------------------------------ */
/* Scene 11 gate: self-hosting status                                  */
/* ------------------------------------------------------------------ */

export type BootstrapStatus = "fixed-point" | "self-hosting" | "none";

/**
 * Flip this one constant when the native self-hosting work changes state.
 * Everything scene 11 says is data-driven from `BOOTSTRAP_COPY`.
 */
export const BOOTSTRAP_STATUS: BootstrapStatus = "fixed-point";

type BootstrapCopy = {
  main: readonly string[];
  small: string;
  tone: "green" | "gold" | "red";
};

export const BOOTSTRAP_COPY: Record<BootstrapStatus, BootstrapCopy> = {
  "fixed-point": {
    main: ["compiler.exe compiles its own source.", "No Python at runtime."],
    small: "stage2 == stage3",
    tone: "green",
  },
  "self-hosting": {
    main: ["compiler.exe compiles its own source.", "No Python at runtime."],
    small: "not yet fixed point",
    tone: "gold",
  },
  none: {
    main: ["compiler.exe compiles a Python subset.", "No Python at runtime."],
    small: "not yet self-compiling",
    tone: "red",
  },
};

export const bootstrap = BOOTSTRAP_COPY[BOOTSTRAP_STATUS];

/* ------------------------------------------------------------------ */
/* The one program the studio scenes follow                            */
/* ------------------------------------------------------------------ */

export const PROGRAM = {
  file: "hello.py",
  py: [
    "def double(value):",
    "    return value * 2",
    "",
    "print(double(22))",
  ],
  spasm: [
    "DEF 10000 1",
    "LOAD_LOCAL 0",
    "PUSH_INT 2",
    "OP 3",
    "RET",
    "PUSH_INT 22",
    "STORE_GLOBAL __spacelang_temp_0",
    "LOAD_GLOBAL __spacelang_temp_0",
    "CALL 10000 1",
    "CALL 0 1",
    "STACK 3",
    "HALT",
  ],
  /** Printed output of `print(double(22))`. */
  output: "44",
} as const;

/** One trace step of the program above, as the studio panels show it. */
export const TRACE = [
  { ip: "PUSH_INT 22", stack: ["22"], call: [], printed: [] },
  { ip: "STORE_GLOBAL __spacelang_temp_0", stack: [], call: [], printed: [] },
  { ip: "LOAD_GLOBAL __spacelang_temp_0", stack: ["22"], call: [], printed: [] },
  { ip: "CALL 10000 1", stack: [], call: ["double(value=22)"], printed: [] },
  { ip: "LOAD_LOCAL 0", stack: ["22"], call: ["double(value=22)"], printed: [] },
  { ip: "PUSH_INT 2", stack: ["22", "2"], call: ["double(value=22)"], printed: [] },
  { ip: "OP 3", stack: ["44"], call: ["double(value=22)"], printed: [] },
  { ip: "RET", stack: ["44"], call: [], printed: [] },
  { ip: "CALL 0 1", stack: [], call: [], printed: ["44"] },
  { ip: "HALT", stack: [], call: [], printed: ["44"] },
] as const;

/** Decoded token stream of the `.sp` format, from the worked example. */
export const TOKEN_RUNS = [
  { spaces: 17, token: "DEF", note: "opcode" },
  { spaces: 10000, token: "10000", note: "function id" },
  { spaces: 1, token: "1", note: "argument count" },
  { spaces: 20, token: "LOAD_LOCAL", note: "opcode" },
  { spaces: 0, token: "0", note: "slot 0" },
  { spaces: 7, token: "PUSH_INT", note: "opcode" },
  { spaces: 4, token: "2", note: "zig-zag: 2 is stored as 4" },
  { spaces: 5, token: "OP", note: "opcode" },
  { spaces: 3, token: "3", note: "multiply" },
  { spaces: 18, token: "RET", note: "opcode" },
] as const;

export const SP_TOKEN_NOTE = "empty line = token 0";

/* ------------------------------------------------------------------ */
/* Scene 02: compiler pipeline                                         */
/* ------------------------------------------------------------------ */

export const PIPELINE = [
  {
    name: ".py",
    step: "surface syntax",
    detail: ["print(20 + 22)"],
  },
  {
    name: "AST",
    step: "parse",
    detail: [
      '{"k": "call", "fn": "print",',
      ' "args": [{"k": "bin",',
      '           "op": "+", ...}]}',
    ],
  },
  {
    name: "IR",
    step: "lower",
    detail: [
      "PUSH_INT 20",
      "PUSH_INT 22",
      "OP 1",
      "CALL 0 1",
      "STACK 1",
      "HALT",
    ],
  },
  {
    name: "peephole",
    step: "fold",
    detail: ["PUSH_INT 42", "CALL 0 1", "STACK 1", "HALT"],
  },
  {
    name: ".sp",
    step: "encode",
    detail: ["7, 84, 1, 0, 1, 6, 1, 29"],
  },
] as const;

/* ------------------------------------------------------------------ */
/* Scenes 03-04: the studio workspace                                  */
/* ------------------------------------------------------------------ */

export const STUDIO = {
  title: "OPT_SP — SpaceLang Visual Debugger",
  url: "127.0.0.1:8000/studio",
  panes: ["py", "spasm", "sp"],
  badgeSynced: "synced",
  badgeStale: "stale",
  debounce: "250 ms debounce",
  spacesButton: "show spaces",
  stepLabel: (step: number, total: number) => `Step ${step} / ${total}`,
} as const;

/** `spasm` pane lines annotated the way the studio prints them. */
export const SPASM_ANNOTATED = [
  "DEF 10000 1  line=1 spaces=17,10000,1",
  "LOAD_LOCAL 0  line=2 spaces=20,0",
  "PUSH_INT 2  line=2 spaces=7,4",
  "OP 3  line=2 spaces=5,3",
  "RET  line=2 spaces=18",
] as const;

/* ------------------------------------------------------------------ */
/* Scenes 05-07: stale mirror, AI rewrite, compiler verification        */
/* ------------------------------------------------------------------ */

export const STALE = {
  mirror: ["def combine(a, b):", "    return a + b"],
  asmBefore: [
    "DEF 10000 2",
    "LOAD_LOCAL 0",
    "LOAD_LOCAL 1",
    "OP 1",
    "RET",
  ],
  asmAfter: [
    "DEF 10000 2",
    "LOAD_LOCAL 0",
    "LOAD_LOCAL 1",
    "OP 2",
    "RET",
  ],
  modelMirror: ["def combine(a, b):", "    return a - b"],
  wrongMirror: ["def combine(a, b):", "    return a * b"],
  noRule: "Program → py has no deterministic implementation",
  pyfrontNote: "pyfront.py only implements compile_py",
  syncButton: "Sync with AI",
} as const;

export const SYNC = {
  model: "DeepSeek",
  title: "Sync with AI",
  sent: ["py", "spasm"],
  kept: ".sp never leaves the machine",
  latency: "0.4 s",
  verified: "mirror verified · 20 output tokens",
  rejected: "Mirror rejected at instruction 7",
  needs: 'needs "OP 2"',
  got: 'got "OP 3"',
  formula: "compile_py(answer) == decode(sp)",
  accepted: "accepted",
  refused: "refused",
} as const;

/* ------------------------------------------------------------------ */
/* Scene 08: the four runtimes                                         */
/* ------------------------------------------------------------------ */

export const ENGINES = [
  {
    name: "spacelang.vm_py.VM",
    kind: "Python reference VM",
    tag: "CPython",
    figure: "1×",
    figureNote: "baseline",
    detail: "reference semantics",
    tone: "cyan",
  },
  {
    name: "native/spvm.exe",
    kind: "Native runner",
    tag: "C++17 · no Python",
    figure: "32×",
    figureNote: "vs Python VM",
    detail: "runs .sp directly",
    tone: "green",
  },
  {
    name: "bootstrap/sp_vm.sp",
    kind: "Self-hosted VM",
    tag: "SpaceLang",
    figure: "depth 2",
    figureNote: "2.8 MB of spaces",
    detail: "a VM written in .sp",
    tone: "purple",
  },
  {
    name: "csrc/vm.cpp",
    kind: "C++ engine",
    tag: "pybind11",
    figure: "8×",
    figureNote: "on call-heavy code",
    detail: "CPython C-API dispatch",
    tone: "gold",
  },
] as const;

/* ------------------------------------------------------------------ */
/* Scene 09: static-asset health                                       */
/* ------------------------------------------------------------------ */

export const HEALTH = {
  url: "127.0.0.1:8000/__opt_sp/health",
  endpoint: "GET /__opt_sp/health",
  checks: ["ok: true", "assets: 4 / 4"],
  panels: [
    {
      title: "Pyodide runtime",
      files: ["pyodide/pyodide.js", "pyodide/python_stdlib.zip"],
      meta: "loaded once, then cached by the browser",
    },
    {
      title: "SpaceLang package",
      files: ["spacelang_pkg/manifest.json"],
      meta: "pinned to the installed package",
    },
    {
      title: "Studio page",
      files: ["studio.html"],
      meta: "the three-pane debugger page",
    },
  ],
  note: "static files only · execution happens in the browser",
} as const;

/* ------------------------------------------------------------------ */
/* Scenes 10 and 13: install and serve                                 */
/* ------------------------------------------------------------------ */

export const INSTALL = {
  pip: "pip install spacelanguage",
  pipOutput: [
    "Collecting spacelanguage",
    "Downloading spacelanguage-0.2.3-cp313-cp313-win_amd64.whl",
    "Installing collected packages: spacelanguage",
    "Successfully installed spacelanguage-0.2.3",
  ],
  serve: "spacelang-opt-sp --port 8000",
  serveOutput: [
    "OPT_SP running at http://127.0.0.1:8000",
    "health ok · all browser assets present",
    "Stop with Ctrl+Alt+Q",
  ],
  python: "Python 3.10+",
} as const;

/* ------------------------------------------------------------------ */
/* Scene 11: native bootstrap                                          */
/* ------------------------------------------------------------------ */

export const BOOTSTRAP = {
  chain: ["spc.py", "spc.sp", "compiler.exe"],
  stages: [
    {
      tag: "stage 0",
      title: "Python toolchain",
      command: "native/spc.py → spc1.sp",
      note: "needs Python once",
      artifact: "build/spc1.sp",
      size: "5,313,084 bytes",
    },
    {
      tag: "stage 1",
      title: "compiler1.exe",
      command: "spc1.sp compiles spc.py → spc2.sp",
      note: "no Python at runtime",
      artifact: "build/spc2.sp",
      size: "5,059,599 bytes",
    },
    {
      tag: "stage 2",
      title: "compiler2.exe",
      command: "spc2.sp compiles spc.py → spc3.sp",
      note: "the compiler compiles itself",
      artifact: "build/spc3.sp",
      size: "5,059,599 bytes · same sha256",
    },
  ],
  equation: ["stage2 == stage3", "spc2.sp == spc3.sp"],
} as const;

/* ------------------------------------------------------------------ */
/* Scene 12: CI matrix                                                 */
/* ------------------------------------------------------------------ */

export const CI = {
  tests: 297,
  testsLabel: "tests on CI",
  os: ["Linux", "macOS", "Windows"],
  runners: ["ubuntu-latest", "macos-latest", "windows-latest"],
  pythons: ["3.10", "3.11", "3.12", "3.13", "3.14"],
  matrix: "3 OS × 5 Python",
  differential: "differential: py vs cpp",
  command: "python -m pytest -q",
} as const;

/* ------------------------------------------------------------------ */
/* Scene 13: the repository                                            */
/* ------------------------------------------------------------------ */

export const REPO = {
  owner: "DwwLSM",
  name: "spacelang",
  branch: "main",
  files: [
    { name: "spacelang/", kind: "dir" },
    { name: "bootstrap/", kind: "dir" },
    { name: "native/", kind: "dir" },
    { name: "csrc/", kind: "dir" },
    { name: "tests/", kind: "dir" },
    { name: "remotion/", kind: "dir" },
    { name: "tools/", kind: "dir" },
    { name: "benchmarks/", kind: "dir" },
    { name: "design/", kind: "dir" },
    { name: ".github/", kind: "dir" },
    { name: "README.md", kind: "file" },
    { name: "documentation.md", kind: "file" },
    { name: "SELFHOSTING.md", kind: "file" },
    { name: "pyproject.toml", kind: "file" },
    { name: "CMakeLists.txt", kind: "file" },
    { name: "scene.py", kind: "file" },
  ],
} as const;

/* ------------------------------------------------------------------ */
/* Captions, relative to each scene start                              */
/* ------------------------------------------------------------------ */

export const CAPTIONS: Readonly<Record<number, readonly RelativeCaptionCue[]>> = {
  1: [
    { from: 0, to: 62, lines: ["This is the source code."] },
    { from: 62, to: 118, lines: ["Every token is a run of spaces."] },
  ],
  2: [{ from: 0, to: 118, lines: ["Python → IR → assembly → .sp"] }],
  3: [{ from: 0, to: 118, lines: ["One program. Three views."] }],
  4: [{ from: 0, to: 118, lines: ["It runs in your browser."] }],
  5: [{ from: 0, to: 118, lines: ["Python cannot follow by rule."] }],
  6: [{ from: 0, to: 118, lines: ["A model rewrites the mirror."] }],
  7: [{ from: 0, to: 118, lines: ["The compiler checks it."] }],
  8: [{ from: 0, to: 118, lines: ["Four runtimes."] }],
  9: [{ from: 0, to: 118, lines: ["Nothing executes on the server."] }],
  10: [{ from: 0, to: 118, lines: ["pip install spacelanguage"] }],
  11: [{ from: 0, to: 118, lines: bootstrap.main, small: bootstrap.small }],
  12: [{ from: 0, to: 118, lines: ["Tested by running every program twice."] }],
};
