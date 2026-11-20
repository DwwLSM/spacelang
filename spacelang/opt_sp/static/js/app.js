import { Visualizer } from "./visualizer.js";
import { bindAutoCompletion, bindDragMove, bindUndoRedo } from "./editor.js";
import { downloadSource } from "./download.js";
import { getFileHandle, storeFileHandle } from "./file-handles.js";
import { checkAssets } from "./health.js";
import { takeHandout, writeHandout } from "./handout.js";
import { SyncEngine } from "./sync-engine.js";
import { initStudioLayout } from "./studio-layout.js";

const page = document.body.dataset.page;

const stopServerButton = document.querySelector("#stop-server-button");
if (stopServerButton) {
  const controlToken = document.querySelector(
    'meta[name="opt-sp-control-token"]',
  )?.content;
  const stopServer = async () => {
    if (!controlToken) {
      stopServerButton.disabled = true;
      return;
    }
    if (!window.confirm(
      "Stop the OPT_SP server? This will disconnect all open debugger tabs."
    )) {
      return;
    }
    stopServerButton.disabled = true;
    try {
      const response = await fetch("__opt_sp/stop", {
        method: "POST",
        headers: { Authorization: `Bearer ${controlToken}` },
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || `Request failed (${response.status}).`);
      stopServerButton.textContent = "Server stopped";
      document.querySelector("#server-status").textContent = "You can close this tab.";
    } catch (error) {
      stopServerButton.disabled = false;
      window.alert(`Could not stop the OPT_SP server: ${error.message || String(error)}`);
    }
  };
  if (!controlToken) {
    stopServerButton.disabled = true;
    stopServerButton.title = "Server control is unavailable for this page.";
  } else {
    stopServerButton.addEventListener("click", stopServer);
    window.addEventListener("keydown", (event) => {
      const isStopShortcut = event.key.toLowerCase() === "q" &&
        event.altKey &&
        (event.ctrlKey || event.metaKey) &&
        !event.shiftKey &&
        !event.repeat &&
        !event.isComposing;
      if (!isStopShortcut) return;
      event.preventDefault();
      stopServer();
    });
  }
}

function showError(target, message) {
  const banner = document.createElement("div");
  banner.className = "error-banner";
  banner.textContent = message;
  target.replaceChildren(banner);
}

function showStatus(target, text) {
  target.classList.remove("error");
  const status = document.createElement("div");
  status.className = "save-status";
  status.textContent = text;
  target.replaceChildren(status);
}

if (page === "editor") {
  const runButton = document.querySelector("#run-button");
  const editor = document.querySelector("#code-editor");
  const message = document.querySelector("#editor-message");
  const projectFileSelect = document.querySelector("#project-file-select");
  const projectFileSearch = document.querySelector("#project-file-search");
  const projectFileBrowser = document.querySelector("#project-file-browser");
  const openProjectFileBrowserButton = document.querySelector("#open-project-file-browser");
  const closeProjectFileBrowserButton = document.querySelector("#close-project-file-browser");
  const projectFileStatus = document.querySelector("#project-file-status");
  const editorPanel = document.querySelector(".editor-panel");
  const sourceModeSelect = document.querySelector("#source-mode");
  const downloadButton = document.querySelector("#download-button");
  const overwriteButton = document.querySelector("#overwrite-button");
  const localFileInput = document.querySelector("#sp-file");
  const openLocalFileButton = document.querySelector("#open-local-file");
  let projectFileSummary = "";
  let projectFiles = [];
  let selectedProjectFilePath = null;
  let isProjectFileLoading = false;
  let suggestedFilename = "program";
  let projectFilePath = null;
  let localFileHandle = null;
  let localFileHandleId = null;
  let localFileName = null;
  const resetUndoHistory = bindUndoRedo(editor);
  bindAutoCompletion(editor);
  bindDragMove(editor);

  function updateOverwriteButton() {
    overwriteButton.disabled = !projectFilePath &&
      !localFileHandle &&
      !(localFileName && typeof window.showSaveFilePicker === "function");
  }

  function setSourceMode(mode) {
    if ([...sourceModeSelect.options].some((option) => option.value === mode)) {
      sourceModeSelect.value = mode;
    }
  }

  function setProjectFileButtonLabel(filename = "") {
    const label = filename || "Search files";
    openProjectFileBrowserButton.textContent = label;
    openProjectFileBrowserButton.title = filename
      ? `Currently open: ${filename}. Click to search project files.`
      : "Search project files";
    openProjectFileBrowserButton.setAttribute(
      "aria-label",
      filename ? `Currently open: ${filename}. Search project files` : "Search project files",
    );
  }

  function renderProjectFileOptions() {
    const query = projectFileSearch.value.trim().toLowerCase();
    const files = projectFiles.filter((file) => file.path.toLowerCase().includes(query));
    projectFileSelect.replaceChildren();

    if (!files.length) {
      const option = new Option(
        query ? "No matching files" : "No supported source files found",
        "",
      );
      option.disabled = true;
      projectFileSelect.add(option);
      projectFileSelect.disabled = true;
      return;
    }

    for (const file of files) {
      projectFileSelect.add(new Option(file.path, file.path));
    }
    projectFileSelect.selectedIndex = -1;
    projectFileSelect.disabled = isProjectFileLoading;
  }

  async function loadProjectFile(path) {
    isProjectFileLoading = true;
    projectFileSelect.disabled = true;
    projectFilePath = null;
    localFileHandle = null;
    localFileHandleId = null;
    localFileName = null;
    updateOverwriteButton();
    projectFileStatus.classList.remove("empty", "error");
    projectFileStatus.removeAttribute("title");
    projectFileStatus.textContent = `Loading ${path}…`;
    try {
      const response = await fetch(`api/file?path=${encodeURIComponent(path)}`);
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || `Request failed (${response.status}).`);
      editor.value = result.code;
      resetUndoHistory();
      suggestedFilename = result.path;
      projectFilePath = result.path;
      setSourceMode(result.mode);
      setProjectFileButtonLabel(result.path);
      updateOverwriteButton();
      message.replaceChildren();
      projectFileStatus.textContent = `Loaded ${result.path} · ${projectFileSummary}`;
    } catch (error) {
      projectFileStatus.classList.add("error");
      projectFileStatus.textContent = "Could not load file.";
      projectFileStatus.title = error.message || String(error);
    } finally {
      isProjectFileLoading = false;
      renderProjectFileOptions();
    }
  }

  async function loadProjectFileList() {
    try {
      const response = await fetch("api/files");
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || `Request failed (${response.status}).`);
      projectFiles = result.files;
      if (!projectFiles.length) {
        renderProjectFileOptions();
        projectFileSearch.disabled = true;
        openProjectFileBrowserButton.disabled = true;
        setProjectFileButtonLabel();
        projectFileStatus.classList.add("empty");
        projectFileStatus.textContent = `No .py, .sp, or .spasm files in ${result.root}.`;
        return;
      }

      projectFileSearch.disabled = false;
      openProjectFileBrowserButton.disabled = false;
      setProjectFileButtonLabel();
      projectFileSummary = `${projectFiles.length} source file${projectFiles.length === 1 ? "" : "s"} in ${result.root}`;
      selectedProjectFilePath = projectFiles[0].path;
      renderProjectFileOptions();
      await loadProjectFile(selectedProjectFilePath);
    } catch (error) {
      projectFileSelect.replaceChildren(new Option("Project files unavailable", ""));
      projectFileSelect.disabled = true;
      projectFileSearch.disabled = true;
      openProjectFileBrowserButton.disabled = true;
      setProjectFileButtonLabel();
      projectFileStatus.classList.add("error");
      projectFileStatus.textContent = "Project file list unavailable.";
      projectFileStatus.title = error.message || String(error);
    }
  }

  function closeProjectFileBrowser() {
    projectFileSearch.value = "";
    renderProjectFileOptions();
    projectFileBrowser.hidden = true;
    editorPanel.hidden = false;
    (openProjectFileBrowserButton.disabled ? editor : openProjectFileBrowserButton).focus();
  }

  openProjectFileBrowserButton.addEventListener("click", () => {
    projectFileSearch.value = "";
    renderProjectFileOptions();
    projectFileBrowser.hidden = false;
    editorPanel.hidden = true;
    projectFileSearch.focus();
  });
  closeProjectFileBrowserButton.addEventListener("click", closeProjectFileBrowser);
  projectFileSelect.addEventListener("change", async () => {
    if (!projectFileSelect.value) return;
    selectedProjectFilePath = projectFileSelect.value;
    await loadProjectFile(selectedProjectFilePath);
    if (projectFilePath) closeProjectFileBrowser();
  });
  projectFileSearch.addEventListener("input", renderProjectFileOptions);
  loadProjectFileList();

  openLocalFileButton.addEventListener("click", async () => {
    if (typeof window.showOpenFilePicker !== "function") {
      localFileInput.click();
      return;
    }
    try {
      const [handle] = await window.showOpenFilePicker({
        multiple: false,
        types: [{
          description: "SpaceLang and source files",
          accept: { "text/plain": [".py", ".sp", ".spasm"] },
        }],
      });
      const file = await handle.getFile();
      editor.value = await file.text();
      resetUndoHistory();
      message.replaceChildren();
      projectFilePath = null;
      localFileHandle = handle;
      try {
        localFileHandleId = await storeFileHandle(handle);
      } catch (error) {
        localFileHandleId = null;
        showStatus(
          message,
          `Opened ${file.name}. Live edit may ask you to choose the file when overwriting: ${error.message || String(error)}`,
        );
      }
      localFileName = file.name;
      suggestedFilename = file.name;
      setProjectFileButtonLabel(file.name);
      const extension = file.name.split(".").pop().toLowerCase();
      setSourceMode(extension === "sp" ? "sp" : extension === "spasm" ? "asm" : "python");
      updateOverwriteButton();
    } catch (error) {
      if (error.name !== "AbortError") {
        showError(message, `Could not open the selected file: ${error.message || String(error)}`);
      }
    }
  });

  localFileInput.addEventListener("change", async (event) => {
    const [file] = event.target.files;
    if (!file) return;
    try {
      editor.value = await file.text();
      resetUndoHistory();
      projectFilePath = null;
      localFileHandle = null;
      localFileHandleId = null;
      localFileName = file.name;
      suggestedFilename = file.name;
      setProjectFileButtonLabel(file.name);
      const extension = file.name.split(".").pop().toLowerCase();
      setSourceMode(extension === "sp" ? "sp" : extension === "spasm" ? "asm" : "python");
      updateOverwriteButton();
      message.replaceChildren();
    } catch (error) {
      showError(message, `Could not read the selected file: ${error.message || String(error)}`);
    } finally {
      localFileInput.value = "";
    }
  });
  document.querySelector("#example-select").addEventListener("change", (event) => {
    if (event.target.value === "asm") {
      editor.value = "PUSH_INT 2\nPUSH_INT 3\nOP 1\nHALT";
      resetUndoHistory();
      projectFilePath = null;
      localFileHandle = null;
      localFileHandleId = null;
      localFileName = null;
      setProjectFileButtonLabel("example.spasm");
      updateOverwriteButton();
      suggestedFilename = "example.spasm";
      setSourceMode("asm");
    } else if (event.target.value === "python") {
      editor.value = "answer = 2 + 3\nprint(answer)";
      resetUndoHistory();
      projectFilePath = null;
      localFileHandle = null;
      localFileHandleId = null;
      localFileName = null;
      setProjectFileButtonLabel("example.py");
      updateOverwriteButton();
      suggestedFilename = "example.py";
      setSourceMode("python");
    }
  });
  downloadButton.addEventListener("click", () => {
    const mode = sourceModeSelect.value;
    downloadSource(editor.value, mode, suggestedFilename);
  });
  overwriteButton.addEventListener("click", async () => {
    const targetName = projectFilePath || localFileName;
    if (!targetName || !window.confirm(`Overwrite "${targetName}" with the current editor contents?`)) {
      return;
    }

    overwriteButton.disabled = true;
    try {
      if (projectFilePath) {
        const response = await fetch("api/file", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ path: projectFilePath, code: editor.value }),
        });
        const result = await response.json();
        if (!response.ok) throw new Error(result.error || `Request failed (${response.status}).`);
        projectFileStatus.classList.remove("error");
        projectFileStatus.textContent = `Overwrote ${result.path}.`;
        showStatus(message, `Overwrote ${result.path}.`);
      } else {
        let handle = localFileHandle;
        if (!handle) {
          handle = await window.showSaveFilePicker({ suggestedName: localFileName });
        } else if (await handle.queryPermission({ mode: "readwrite" }) !== "granted" &&
            await handle.requestPermission({ mode: "readwrite" }) !== "granted") {
          throw new Error("Write permission was not granted.");
        }
        const writable = await handle.createWritable();
        try {
          await writable.write(editor.value);
          await writable.close();
        } catch (error) {
          await writable.abort();
          throw error;
        }
        localFileHandle = handle;
        localFileName = handle.name;
        setProjectFileButtonLabel(handle.name);
        showStatus(message, `Overwrote ${localFileName}.`);
      }
    } catch (error) {
      if (error.name !== "AbortError") {
        showError(message, `Could not overwrite the source file: ${error.message || String(error)}`);
      }
    } finally {
      updateOverwriteButton();
    }
  });
  runButton.addEventListener("click", async () => {
    runButton.disabled = true;
    runButton.classList.add("loading");
    runButton.textContent = "Loading…";
    message.replaceChildren();
    try {
      const { kernel } = await import("./spacelang-kernel.js");
      const mode = sourceModeSelect.value;
      const result = await kernel.trace(editor.value, mode);
      sessionStorage.setItem("opt-sp-trace", JSON.stringify({
        trace: result.trace,
        error: result.ok ? null : result.error,
        code: editor.value,
        mode,
        filename: suggestedFilename,
        projectFilePath,
        localFileHandleId,
        localFileName,
      }));
      location.href = "visualize.html";
    } catch (error) {
      const details = error.message || String(error);
      showError(message, `Pyodide failed to load. Run tools/build_static.py.\n${details}`);
      runButton.textContent = "Run";
      runButton.disabled = true;
    } finally {
      runButton.classList.remove("loading");
    }
  });

  document.querySelector("#studio-link")?.addEventListener("click", () => {
    writeHandout(sourceModeSelect.value, editor.value);
  });
} else if (page === "visualize") {
  const root = document.querySelector("#viz-root");
  const raw = sessionStorage.getItem("opt-sp-trace");
  if (!raw) {
    location.href = "./";
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
      const visualizer = new Visualizer(root, payload.trace, payload.code, payload.mode, {
        projectFilePath: payload.projectFilePath ?? null,
        localFileHandleId: payload.localFileHandleId ?? null,
        localFileName: payload.localFileName ?? null,
      });
      document.querySelector("#download-button").addEventListener("click", () => {
        const source = visualizer.liveMode ? visualizer.liveEditor.value : visualizer.sourceText;
        downloadSource(source, visualizer.mode, payload.filename);
      });
      const overwriteButton = document.querySelector("#overwrite-button");
      const updateOverwriteButton = () => {
        const hasTarget = visualizer.projectFilePath ||
          visualizer.localFileHandleId ||
          (visualizer.localFileName && typeof window.showSaveFilePicker === "function");
        overwriteButton.disabled = !visualizer.liveMode || !hasTarget;
      };
      overwriteButton.addEventListener("click", async () => {
        const targetName = visualizer.projectFilePath || visualizer.localFileName;
        if (!targetName || !window.confirm(`Overwrite "${targetName}" with the live editor contents?`)) {
          return;
        }

        overwriteButton.disabled = true;
        try {
          if (visualizer.projectFilePath) {
            const response = await fetch("api/file", {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                path: visualizer.projectFilePath,
                code: visualizer.liveEditor.value,
              }),
            });
            const result = await response.json();
            if (!response.ok) throw new Error(result.error || `Request failed (${response.status}).`);
            showStatus(visualizer.liveStatus, `Overwrote ${result.path}.`);
          } else {
            let handle = visualizer.localFileHandleId
              ? await getFileHandle(visualizer.localFileHandleId)
              : null;
            if (!handle) {
              handle = await window.showSaveFilePicker({
                suggestedName: visualizer.localFileName,
              });
            } else if (await handle.queryPermission({ mode: "readwrite" }) !== "granted" &&
                await handle.requestPermission({ mode: "readwrite" }) !== "granted") {
              throw new Error("Write permission was not granted.");
            }
            const writable = await handle.createWritable();
            try {
              await writable.write(visualizer.liveEditor.value);
              await writable.close();
            } catch (error) {
              await writable.abort();
              throw error;
            }
            showStatus(visualizer.liveStatus, `Overwrote ${handle.name}.`);
          }
        } catch (error) {
          if (error.name !== "AbortError") {
            showError(
              visualizer.liveStatus,
              `Could not overwrite the source file: ${error.message || String(error)}`,
            );
          }
        } finally {
          updateOverwriteButton();
        }
      });
      visualizer.render(0);
      visualizer.bindControls();
      visualizer.liveToggle.addEventListener("click", updateOverwriteButton);
      updateOverwriteButton();
      document.querySelector("#studio-link")?.addEventListener("click", () => {
        const source = visualizer.liveMode
          ? visualizer.liveEditor.value
          : visualizer.sourceText;
        writeHandout(visualizer.mode, source);
      });
      window.addEventListener("keydown", (event) => {
        if (event.target instanceof HTMLElement &&
          event.target.closest("input, textarea, select, [contenteditable='true']")) return;
        if (event.key === "ArrowLeft") visualizer.render(visualizer.stepIndex - 1);
        if (event.key === "ArrowRight") visualizer.render(visualizer.stepIndex + 1);
      });
    }
  }
} else if (page === "studio") {
  const paneByMode = { python: "py", asm: "spasm", sp: "sp" };
  const panes = {
    py: document.querySelector("#py-editor"),
    spasm: document.querySelector("#spasm-editor"),
    sp: document.querySelector("#sp-editor"),
  };
  const badges = {
    py: document.querySelector("#py-badge"),
    spasm: document.querySelector("#spasm-badge"),
    sp: document.querySelector("#sp-badge"),
  };
  const preview = document.querySelector("#sp-preview");
  const spacesToggle = document.querySelector("#show-spaces-toggle");
  const copyButton = document.querySelector("#copy-sp-button");

  const renderPreview = () => {
    if (!preview || preview.hidden) return;
    preview.textContent = panes.sp.value.replace(/ /g, "\u00b7");
  };

  const engine = new SyncEngine({
    panes,
    onStateChange: (name, state) => {
      const badge = badges[name];
      if (!badge) return;
      badge.dataset.state = state;
      badge.textContent = state;
    },
    onWrite: (name) => {
      if (name === "sp") renderPreview();
    },
  });

  spacesToggle?.addEventListener("click", () => {
    const next = spacesToggle.getAttribute("aria-pressed") !== "true";
    spacesToggle.setAttribute("aria-pressed", String(next));
    preview.hidden = !next;
    renderPreview();
  });

  const annotationsToggle = document.querySelector("#spasm-annotations-toggle");
  annotationsToggle?.addEventListener("click", () => {
    const next = annotationsToggle.getAttribute("aria-pressed") !== "true";
    annotationsToggle.setAttribute("aria-pressed", String(next));
    void engine.setAnnotations(next);
  });

  initStudioLayout({
    container: document.querySelector(".studio-editors"),
    toggleButton: document.querySelector("#pane-layout-toggle"),
  });

  copyButton?.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(panes.sp.value);
      copyButton.textContent = "Copied";
    } catch {
      copyButton.textContent = "Copy failed";
    }
    setTimeout(() => { copyButton.textContent = "Copy raw"; }, 1200);
  });

  panes.sp.addEventListener("input", renderPreview);

  const handoff = takeHandout();
  if (handoff) {
    const name = paneByMode[handoff.mode];
    panes[name].value = handoff.source;
    renderPreview();
    void engine.start(name);
  }
}

const settingsButton = document.querySelector("#settings-button");
const settingsMenu = document.querySelector("#settings-menu");
if (settingsButton && settingsMenu) {
  const closeSettingsMenu = () => {
    settingsMenu.hidden = true;
    settingsButton.setAttribute("aria-expanded", "false");
  };

  settingsButton.addEventListener("click", (event) => {
    event.stopPropagation();
    const willOpen = settingsMenu.hidden;
    settingsMenu.hidden = !willOpen;
    settingsButton.setAttribute("aria-expanded", String(willOpen));
    if (willOpen) {
      settingsMenu.querySelector("[role='menuitem']")?.focus();
    }
  });

  document.addEventListener("click", (event) => {
    if (!settingsMenu.hidden && !event.target.closest(".settings-menu-wrapper")) {
      closeSettingsMenu();
    }
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !settingsMenu.hidden) {
      closeSettingsMenu();
      settingsButton.focus();
    }
  });

  document.querySelector("#reload-page-button")?.addEventListener("click", () => {
    window.location.reload();
  });
}

void checkAssets();
