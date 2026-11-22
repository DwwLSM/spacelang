/**
 * Single source of truth for every string, code listing and number that
 * appears in the 56-second SpaceLang tour (`SpaceLangTour56`).
 *
 * Nothing in `scenes/` should hard-code copy: if a word or figure is on
 * screen, it lives here. Caption lines are kept short so the burned-in
 * subtitle band never wraps past `MAX_CAPTION_CHARS`.
 */

const SCENE_DURATIONS = [
  90, 120, 180, 120, 120, 120, 120, 150, 120, 90, 90, 120, 120, 120,
] as const;

export const VIDEO = {
  width: 1920,
  height: 1080,
  fps: 30,
  frames: SCENE_DURATIONS.reduce((total, duration) => total + duration, 0),
  sceneDurations: SCENE_DURATIONS,
  /** Scene components animate against this normalized frame count. */
  sceneFrames: 120,
  sceneCount: 13,
} as const;

/** Hard limit for one burned-in caption line at 1920x1080. */
export const MAX_CAPTION_CHARS = 42;

/** Duration of each eased dissolve transition at 30 fps. */
export const TRANSITION_FRAMES = 16;

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
    main: ["compiler.exe compiles itself. Verified fixed point. No Python."],
    small: "verified fixed point · experimental",
    tone: "green",
  },
  "self-hosting": {
    main: ["compiler.exe compiles itself. Fixed point pending. No Python."],
    small: "not yet fixed point",
    tone: "gold",
  },
  none: {
    main: ["compiler.exe compiles a Python subset. Not yet self-compiling."],
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
    ".name __spacelang_temp_0=0",
    "DEF 10000 1 ; line=1 spaces=17,10000,1",
    "LOAD_LOCAL 0 ; line=2 spaces=20,0",
    "PUSH_INT 2 ; line=2 spaces=7,4",
    "OP 3 ; line=2 spaces=5,3",
    "RET ; line=2 spaces=18",
    "PUSH_INT 0 ; line=1 spaces=7,0",
    "RET ; line=1 spaces=18",
    "PUSH_INT 22 ; line=4 spaces=7,44",
    "STORE_GLOBAL __spacelang_temp_0 ; line=4 spaces=10,0",
    "LOAD_GLOBAL __spacelang_temp_0 ; line=4 spaces=9,0",
    "CALL 10000 1 ; line=4 spaces=1,10000,1",
    "CALL 0 1 ; line=4 spaces=1,0,1",
    "STACK 3 ; line=4 spaces=6,3",
    "HALT ; line=0 spaces=29",
  ],
  /** Printed output of `print(double(22))`. */
  output: "44",
} as const;

/** State snapshots from tracing PROGRAM.py with the in-browser VM. */
export const TRACE = [
  { instruction: "DEF 10000", sourceLine: 1, stack: [], call: [], output: "" },
  {
    instruction: "PUSH_INT 22",
    sourceLine: 4,
    stack: [{ type: "int", repr: "22" }],
    call: [],
    output: "",
  },
  { instruction: "STORE_GLOBAL 0", sourceLine: 4, stack: [], call: [], output: "" },
  {
    instruction: "LOAD_GLOBAL 0",
    sourceLine: 4,
    stack: [{ type: "int", repr: "22" }],
    call: [],
    output: "",
  },
  {
    instruction: "CALL 10000",
    sourceLine: 4,
    stack: [],
    call: [{ func: "func_10000", locals: [{ name: "local_0", repr: "22" }] }],
    output: "",
  },
  {
    instruction: "LOAD_LOCAL 0",
    sourceLine: 2,
    stack: [{ type: "int", repr: "22" }],
    call: [{ func: "func_10000", locals: [{ name: "local_0", repr: "22" }] }],
    output: "",
  },
  {
    instruction: "PUSH_INT 2",
    sourceLine: 2,
    stack: [
      { type: "int", repr: "22" },
      { type: "int", repr: "2" },
    ],
    call: [{ func: "func_10000", locals: [{ name: "local_0", repr: "22" }] }],
    output: "",
  },
  {
    instruction: "OP 3",
    sourceLine: 2,
    stack: [{ type: "int", repr: "44" }],
    call: [{ func: "func_10000", locals: [{ name: "local_0", repr: "22" }] }],
    output: "",
  },
  {
    instruction: "RET",
    sourceLine: 2,
    stack: [{ type: "int", repr: "44" }],
    call: [],
    output: "",
  },
  {
    instruction: "CALL 0",
    sourceLine: 4,
    stack: [{ type: "NoneType", repr: "None" }],
    call: [],
    output: "44\n",
  },
  { instruction: "STACK 3", sourceLine: 4, stack: [], call: [], output: "44\n" },
  { instruction: "HALT", sourceLine: null, stack: [], call: [], output: "44\n" },
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
  model: "Socrates · default",
  title: "Sync with AI",
  sent: ["Python mirror", "edited assembly"],
  kept: ".sp never leaves the machine",
  verified: "verified locally",
  rejected: "Mirror rejected: instruction mismatch",
  needs: 'needs "OP 2"',
  got: 'got "OP 3"',
  formula: "compile_py(answer) == assemble(spasm)",
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
    tag: "CPython · reference",
    role: "Reference",
    detail: "readable Python implementation",
    tone: "cyan",
  },
  {
    name: "native/spvm.exe",
    kind: "Native runner",
    tag: "C++17 · experimental",
    role: "Native",
    detail: "Python-free .sp runner",
    tone: "green",
  },
  {
    name: "bootstrap/sp_vm.sp",
    kind: "Self-hosted VM",
    tag: "SpaceLang · experimental",
    role: "Self-hosted",
    detail: "VM written in .sp",
    tone: "purple",
  },
  {
    name: "csrc/vm.cpp",
    kind: "C++ extension",
    tag: "pybind11 · experimental",
    role: "Extension",
    detail: "native engine exposed to CPython",
    tone: "gold",
  },
] as const;

/* ------------------------------------------------------------------ */
/* Scene 09: static-asset health                                       */
/* ------------------------------------------------------------------ */

export const HEALTH = {
  url: "127.0.0.1:8000/__opt_sp/health",
  endpoint: "GET /__opt_sp/health",
  checks: [
    ["pyodide_js", true],
    ["python_stdlib", true],
    ["spacelang_pkg", true],
    ["studio_page", true],
  ],
  hint: null,
  policy: "loopback clients only",
  note: "static-file checks only · Python executes in the browser via Pyodide",
} as const;

/* ------------------------------------------------------------------ */
/* Scenes 10 and 13: install and serve                                 */
/* ------------------------------------------------------------------ */

export const INSTALL = {
  pip: "python -m pip install spacelanguage",
  python: "Python 3.10+",
  serve: "spacelang-opt-sp --port 8000",
  host: "127.0.0.1:8000",
  server: "ThreadingHTTPServer",
  launch: "opens http://127.0.0.1:8000/",
  studio: "GET /studio → studio.html",
  files: ["css/opt-sp.css?v=10", "css/studio.css?v=10", "js/app.js?v=10"],
  kernel: [
    "js/spacelang-kernel.js",
    "pyodide/pyodide.js",
    "spacelang_pkg/manifest.json",
  ],
  behavior: "Python executes in the browser via Pyodide",
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
  os: ["Linux", "macOS", "Windows"],
  runners: ["ubuntu-latest", "macos-latest", "windows-latest"],
  pythons: ["3.10", "3.11", "3.12", "3.13", "3.14"],
  matrix: "3 OS × 5 Python",
  differential: "Python VM ↔ C++ VM",
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
  0: [{ from: 0, to: 118, lines: ["A program encoded as spaces."] }],
  1: [
    { from: 0, to: 62, lines: ["Every token is stored as spaces."] },
    { from: 62, to: 118, lines: ["Space counts encode integer tokens."] },
  ],
  2: [{ from: 0, to: 118, lines: ["Source becomes executable instructions."] }],
  3: [{ from: 0, to: 118, lines: ["One program. Three views."] }],
  4: [{ from: 0, to: 118, lines: ["Step through execution in your browser."] }],
  5: [{ from: 0, to: 118, lines: ["An assembly edit makes the mirror stale."] }],
  6: [{ from: 0, to: 118, lines: ["A model proposes; local code verifies."] }],
  7: [{ from: 0, to: 118, lines: ["Only matching instructions are accepted."] }],
  8: [{ from: 0, to: 118, lines: ["Four runtimes. One language."] }],
  9: [{ from: 0, to: 118, lines: ["Browser executes; server serves files."] }],
  10: [{ from: 0, to: 118, lines: ["Install the CLI and run locally."] }],
  11: [{ from: 0, to: 118, lines: bootstrap.main }],
  12: [
    {
      from: 0,
      to: 118,
      lines: ["CI spans Linux, macOS, Windows; Python 3.10–3.14."],
    },
  ],
  13: [{ from: 0, to: 118, lines: ["Read the code. Try SpaceLang."] }],
};
