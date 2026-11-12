import { Visualizer } from "./visualizer.js";

const page = document.body.dataset.page;

function showError(target, message) {
  const banner = document.createElement("div");
  banner.className = "error-banner";
  banner.textContent = message;
  target.replaceChildren(banner);
}

if (page === "editor") {
  const runButton = document.querySelector("#run-button");
  const editor = document.querySelector("#code-editor");
  const message = document.querySelector("#editor-message");
  document.querySelector("#sp-file").addEventListener("change", async (event) => {
    const [file] = event.target.files;
    if (!file) return;
    editor.value = await file.text();
    document.querySelector('[value="sp"]').checked = true;
    message.replaceChildren();
  });
  document.querySelector("#example-select").addEventListener("change", (event) => {
    if (event.target.value === "asm") {
      editor.value = "PUSH_INT 2\nPUSH_INT 3\nOP 1\nHALT";
      document.querySelector('[value="asm"]').checked = true;
    } else if (event.target.value === "python") {
      editor.value = "answer = 2 + 3\nprint(answer)";
      document.querySelector('[value="python"]').checked = true;
    }
  });
  runButton.addEventListener("click", async () => {
    runButton.disabled = true;
    runButton.classList.add("loading");
    runButton.textContent = "Loading Pyodide…";
    message.replaceChildren();
    try {
      const { kernel } = await import("./spacelang-kernel.js");
      const mode = document.querySelector('[name="source-mode"]:checked').value;
      const result = await kernel.trace(editor.value, mode);
      sessionStorage.setItem("opt-sp-trace", JSON.stringify({
        trace: result.trace,
        error: result.ok ? null : result.error,
        code: editor.value,
        mode,
      }));
      location.href = "/visualize.html";
    } catch (error) {
      const details = error.message || String(error);
      showError(message, `Pyodide failed to load. Run tools/build_static.py.\n${details}`);
      runButton.textContent = "Run and Visualize";
      runButton.disabled = true;
    } finally {
      runButton.classList.remove("loading");
    }
  });
} else if (page === "visualize") {
  const root = document.querySelector("#viz-root");
  const raw = sessionStorage.getItem("opt-sp-trace");
  if (!raw) {
    location.href = "/";
  } else {
    let payload;
    try {
      payload = JSON.parse(raw);
    } catch (error) {
      showError(root, `Could not read the trace: ${error.message}`);
    }
    if (payload?.error) {
      showError(root, payload.error);
    } else if (payload) {
      const visualizer = new Visualizer(root, payload.trace, payload.code);
      visualizer.render(0);
      visualizer.bindControls();
      window.addEventListener("keydown", (event) => {
        if (event.key === "ArrowLeft") visualizer.render(visualizer.stepIndex - 1);
        if (event.key === "ArrowRight") visualizer.render(visualizer.stepIndex + 1);
      });
    }
  }
}
