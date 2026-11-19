export async function loadPyodide(options) {
  await import(new URL("../pyodide/pyodide.js", import.meta.url));
  if (typeof globalThis.loadPyodide !== "function") {
    throw new Error("The Pyodide bundle did not expose globalThis.loadPyodide.");
  }
  return globalThis.loadPyodide(options);
}
