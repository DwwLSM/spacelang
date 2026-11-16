import { loadPyodide } from "./pyodide-loader.js";

let py;
let initialization;

async function initialize() {
  py = await loadPyodide({ indexURL: "/pyodide/" });
  if (!py.FS.analyzePath("/spacelang_pkg").exists) {
    py.FS.mkdirTree("/spacelang_pkg");
  }
  const response = await fetch("/spacelang_pkg/manifest.json");
  if (!response.ok) {
    throw new Error(`Could not load SpaceLang module manifest (${response.status}).`);
  }
  const manifest = await response.json();
  for (const entry of manifest) {
    const file = await fetch(entry.url);
    if (!file.ok) throw new Error(`Could not load SpaceLang module ${entry.path}.`);
    const buffer = await file.arrayBuffer();
    const target = `/spacelang_pkg/${entry.path}`;
    py.FS.mkdirTree(target.slice(0, target.lastIndexOf("/")));
    py.FS.writeFile(target, new Uint8Array(buffer));
  }
  py.runPython('import sys; sys.path.insert(0, "/spacelang_pkg")');
  py.runPython("from spacelang.web_bridge import trace_program");
  return py;
}

export const kernel = {
  get ready() {
    return this.init();
  },
  init() {
    if (document.readyState === "loading") {
      throw new Error("Initialize the SpaceLang kernel after the document is ready.");
    }
    if (!initialization) initialization = initialize();
    return initialization;
  },
  async trace(code, mode) {
    const runtime = await this.init();
    const result = await runtime.runPythonAsync(
      `trace_program(${JSON.stringify(code)}, ${mode === "asm" ? "True" : "False"}, ${mode === "sp" ? "True" : "False"})`,
    );
    try {
      return result.toJs({ dict_converter: Object.fromEntries });
    } finally {
      result.destroy();
    }
  },
};
