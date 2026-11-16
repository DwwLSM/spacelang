export async function loadPyodide(options) {
  await import("/pyodide/pyodide.js");
  if (typeof globalThis.loadPyodide !== "function") {
    throw new Error("The Pyodide bundle did not expose globalThis.loadPyodide.");
  }
  return globalThis.loadPyodide(options);
}
