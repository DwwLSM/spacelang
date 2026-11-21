import { Visualizer } from "./visualizer.js";
import { bindAutoCompletion, bindDragMove, bindUndoRedo } from "./editor.js";
import { downloadSource } from "./download.js";
import { initDocNavigation } from "./docs.js";
import { getFileHandle, storeFileHandle } from "./file-handles.js";
import { checkAssets } from "./health.js";
import { takeHandout, writeHandout } from "./handout.js";
import { SyncEngine, stripAnnotations } from "./sync-engine.js";
import { initStudioLayout } from "./studio-layout.js";
import { TracePanel } from "./trace-panel.js";
import { describeError, refinePy } from "./llm-bridge.js";
import { initLLMSettings, llmHeaders } from "./llm-settings.js";
import { createWorkspaceSaver, loadWorkspace } from "./workspace.js";

const page = document.body.dataset.page;

/**
 * Read a JSON reply, but name the real problem when the body is not JSON.
 *
 * A server build that predates an endpoint answers with its HTML error page;
 * `response.json()` then throws a JSON syntax error that points at the page
 * prologue instead of at the missing endpoint.
 */
async function readJsonResponse(response) {
  const text = await response.text();
  try {
    return JSON.parse(text);
  } catch {
    throw new Error(
      response.status === 404 || response.status === 405
        ? "The running server does not serve this endpoint. Restart the OPT_SP server."
        : `The server answered ${response.status} with a page instead of JSON.`,
    );
  }
}

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
  // Assigned once the workspace saver exists; earlier loaders call it safely.
  let scheduleWorkspaceSave = () => {};
  const resetUndoHistory = bindUndoRedo(editor);
  bindAutoCompletion(editor);
  bindDragMove(editor);

  const MODE_LABELS = { python: "Python", asm: "Assembly", sp: "Encoded" };
  const MODE_EXTENSIONS = { python: ".py", asm: ".spasm", sp: ".sp" };

  /** The file this buffer belongs to, or "" while it is still unsaved. */
  function currentFileName() {
    return projectFilePath || localFileName || "";
  }

  /**
   * Both file actions follow the buffer state: a buffer that belongs to a file
   * can be overwritten, an unsaved one can only be written somewhere new. The
   * button therefore reads "Overwrite" or "New file" instead of going dead.
   */
  function updateFileActions() {
    const unsaved = !currentFileName();
    const title = unsaved
      ? "Write these contents to a new file in the project folder"
      : "Overwrite the loaded source file";
    overwriteButton.textContent = unsaved ? "New file" : "Overwrite";
    overwriteButton.title = title;
    overwriteButton.setAttribute("aria-label", title);
    overwriteButton.disabled = false;
  }

  function updateFileButtonLabel() {
    const name = currentFileName();
    const label = name || `New ${MODE_LABELS[sourceModeSelect.value]} file`;
    openProjectFileBrowserButton.textContent = label;
    openProjectFileBrowserButton.title = name
      ? `Currently open: ${name}. Click to search project files.`
      : "This buffer is not saved yet. Click to open a project file.";
    openProjectFileBrowserButton.setAttribute(
      "aria-label",
      name ? `Currently open: ${name}. Search project files` : "Open a project file",
    );
  }

  function setSourceMode(mode) {
    if ([...sourceModeSelect.options].some((option) => option.value === mode)) {
      sourceModeSelect.value = mode;
    }
  }

  function selectProjectFileInList(path) {
    if (!path) {
      projectFileSelect.selectedIndex = -1;
      return;
    }
    const option = [...projectFileSelect.options].find((item) => item.value === path);
    projectFileSelect.value = option ? path : "";
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
    selectProjectFileInList(projectFilePath);
    projectFileSelect.disabled = isProjectFileLoading;
  }

  async function loadProjectFile(path) {
    isProjectFileLoading = true;
    projectFileSelect.disabled = true;
    projectFilePath = null;
    localFileHandle = null;
    localFileHandleId = null;
    localFileName = null;
    updateFileActions();
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
      updateFileButtonLabel();
      updateFileActions();
      scheduleWorkspaceSave();
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
        updateFileButtonLabel();
        projectFileStatus.classList.add("empty");
        projectFileStatus.textContent = `No .py, .sp, or .spasm files in ${result.root}.`;
        return;
      }

      projectFileSearch.disabled = false;
      openProjectFileBrowserButton.disabled = false;
      updateFileButtonLabel();
      projectFileSummary = `${projectFiles.length} source file${projectFiles.length === 1 ? "" : "s"} in ${result.root}`;
      renderProjectFileOptions();
      projectFileStatus.classList.remove("empty", "error");
      projectFileStatus.textContent = projectFileSummary;
      // Do not open a file here: the editor already shows the restored workspace
      // (or the start-a-file dialog), and auto-loading the first entry used to
      // replace both with whatever sorted first.
      selectProjectFileInList(projectFilePath);
    } catch (error) {
      projectFileSelect.replaceChildren(new Option("Project files unavailable", ""));
      projectFileSelect.disabled = true;
      projectFileSearch.disabled = true;
      openProjectFileBrowserButton.disabled = true;
      updateFileButtonLabel();
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
      updateFileButtonLabel();
      const extension = file.name.split(".").pop().toLowerCase();
      setSourceMode(extension === "sp" ? "sp" : extension === "spasm" ? "asm" : "python");
      updateFileActions();
      scheduleWorkspaceSave();
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
      updateFileButtonLabel();
      const extension = file.name.split(".").pop().toLowerCase();
      setSourceMode(extension === "sp" ? "sp" : extension === "spasm" ? "asm" : "python");
      updateFileActions();
      scheduleWorkspaceSave();
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
      updateFileButtonLabel();
      updateFileActions();
      suggestedFilename = "example.spasm";
      setSourceMode("asm");
    } else if (event.target.value === "python") {
      editor.value = "answer = 2 + 3\nprint(answer)";
      resetUndoHistory();
      projectFilePath = null;
      localFileHandle = null;
      localFileHandleId = null;
      localFileName = null;
      updateFileButtonLabel();
      updateFileActions();
      suggestedFilename = "example.py";
      setSourceMode("python");
    }
  });
  downloadButton.addEventListener("click", () => {
    const mode = sourceModeSelect.value;
    downloadSource(editor.value, mode, suggestedFilename);
  });
  overwriteButton.addEventListener("click", async () => {
    // A buffer that belongs to no file cannot be overwritten; the same button
    // writes it to a new file instead.
    if (!currentFileName()) {
      openCreateFileDialog();
      return;
    }
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
        const result = await readJsonResponse(response);
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
        updateFileButtonLabel();
        showStatus(message, `Overwrote ${localFileName}.`);
      }
    } catch (error) {
      if (error.name !== "AbortError") {
        showError(message, `Could not overwrite the source file: ${error.message || String(error)}`);
      }
    } finally {
      updateFileActions();
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

  for (const entry of document.querySelectorAll(".studio-entry")) {
    entry.addEventListener("click", () => {
      saver.flush();
      writeHandout(sourceModeSelect.value, editor.value);
    });
  }

  // --- workspace: keep the file and the content across Run and Back ---------
  const saver = createWorkspaceSaver(() => ({
    code: editor.value,
    mode: sourceModeSelect.value,
    suggestedFilename,
    projectFilePath,
    localFileHandleId,
    localFileName,
    caret: editor.selectionStart ?? 0,
  }));
  scheduleWorkspaceSave = saver.schedule;
  editor.addEventListener("input", saver.schedule);
  sourceModeSelect.addEventListener("change", saver.schedule);

  const defaultAsm = editor.defaultValue;
  const SAMPLES = {
    python: "def add(a, b):\n    return a + b\n\n\nprint(add(2, 3))\n",
    asm: defaultAsm,
    sp: "",
  };
  const newFileDialog = document.querySelector("#new-file-dialog");
  const newFileButton = document.querySelector("#new-file-button");
  if (newFileButton) newFileButton.hidden = false;

  function updateEditorPlaceholder() {
    editor.placeholder = sourceModeSelect.value === "sp"
      ? "Paste an encoded .sp program here."
      : "";
  }

  /** Blank buffer: it belongs to no file, so saving it is the New file action. */
  function startBlankBuffer(mode) {
    sourceModeSelect.value = mode in SAMPLES ? mode : "asm";
    editor.value = SAMPLES[sourceModeSelect.value] ?? "";
    suggestedFilename = "program";
    projectFilePath = null;
    localFileHandle = null;
    localFileHandleId = null;
    localFileName = null;
    updateFileButtonLabel();
    resetUndoHistory();
    updateFileActions();
    updateEditorPlaceholder();
    projectFileStatus.classList.remove("empty", "error");
    projectFileStatus.textContent = `New ${MODE_LABELS[sourceModeSelect.value]} file · not saved yet`;
    saver.flush();
    newFileDialog?.close();
    editor.focus();
  }

  function openNewFileDialog() {
    if (!newFileDialog) return;
    if (typeof newFileDialog.showModal === "function") newFileDialog.showModal();
    else newFileDialog.setAttribute("open", "");
  }

  for (const button of newFileDialog?.querySelectorAll("button[data-mode]") ?? []) {
    button.addEventListener("click", () => startBlankBuffer(button.dataset.mode));
  }
  newFileDialog?.querySelector("#new-file-open")?.addEventListener("click", () => {
    newFileDialog.close();
    openProjectFileBrowserButton.click();
  });
  newFileButton?.addEventListener("click", openNewFileDialog);

  // --- write the current buffer to a new project file ----------------------
  const createFileDialog = document.querySelector("#create-file-dialog");
  const createFileName = document.querySelector("#create-file-name");
  const createFileError = document.querySelector("#create-file-error");
  const createFileSubmit = document.querySelector("#create-file-submit");

  function showCreateFileError(text) {
    if (!createFileError) return;
    createFileError.textContent = text;
    createFileError.hidden = false;
  }

  function clearCreateFileError() {
    if (!createFileError) return;
    createFileError.textContent = "";
    createFileError.hidden = true;
  }

  function openCreateFileDialog() {
    if (!createFileDialog) return;
    const stem = (suggestedFilename || "program").replace(/\.[^./\\]+$/, "") || "program";
    if (createFileName) {
      createFileName.value = `${stem}${MODE_EXTENSIONS[sourceModeSelect.value] ?? ".py"}`;
    }
    clearCreateFileError();
    if (typeof createFileDialog.showModal === "function") createFileDialog.showModal();
    else createFileDialog.setAttribute("open", "");
    createFileName?.focus();
    createFileName?.select();
  }

  async function createProjectFile() {
    const name = createFileName?.value.trim() ?? "";
    if (!name) {
      showCreateFileError("Enter a file name.");
      return;
    }
    if (createFileSubmit) createFileSubmit.disabled = true;
    try {
      const response = await fetch("api/file/new", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path: name, code: editor.value }),
      });
      const result = await readJsonResponse(response);
      if (!response.ok) {
        throw new Error(result.message || result.error || `Request failed (${response.status}).`);
      }
      projectFilePath = result.path;
      suggestedFilename = result.path;
      localFileHandle = null;
      localFileHandleId = null;
      localFileName = null;
      // The file suffix decides the representation, exactly as when loading one.
      if (result.mode) setSourceMode(result.mode);
      updateFileButtonLabel();
      updateFileActions();
      updateEditorPlaceholder();
      createFileDialog?.close();
      scheduleWorkspaceSave();
      await loadProjectFileList();
      projectFileStatus.classList.remove("empty", "error");
      projectFileStatus.textContent = `Created ${result.path}.`;
      showStatus(message, `Created ${result.path}.`);
    } catch (error) {
      showCreateFileError(error.message || String(error));
    } finally {
      if (createFileSubmit) createFileSubmit.disabled = false;
    }
  }

  createFileSubmit?.addEventListener("click", () => void createProjectFile());
  createFileName?.addEventListener("keydown", (event) => {
    if (event.key !== "Enter") return;
    event.preventDefault();
    void createProjectFile();
  });
  createFileDialog?.querySelector("#create-file-cancel")?.addEventListener("click", () => {
    createFileDialog.close();
  });

  sourceModeSelect.addEventListener("change", () => {
    updateEditorPlaceholder();
    updateFileButtonLabel();
  });
  window.addEventListener("beforeunload", () => saver.flush());

  let bootstrapped = false;

  function applyWorkspace() {
    const restored = loadWorkspace();
    if (!restored) return false;
    editor.value = restored.code;
    if (restored.mode) sourceModeSelect.value = restored.mode;
    suggestedFilename = restored.suggestedFilename || "program";
    projectFilePath = restored.projectFilePath ?? null;
    localFileName = restored.localFileName ?? null;
    localFileHandleId = restored.localFileHandleId ?? null;
    updateFileButtonLabel();
    resetUndoHistory();
    updateFileActions();
    updateEditorPlaceholder();
    if (Number.isInteger(restored.caret)) {
      const caret = Math.min(restored.caret, editor.value.length);
      editor.setSelectionRange(caret, caret);
    }
    if (localFileHandleId) {
      // The handle survives in IndexedDB; permission may need re-granting when
      // the user next overwrites, which the existing flow already handles.
      getFileHandle(localFileHandleId).then((handle) => {
        if (!handle || localFileHandleId !== restored.localFileHandleId) return;
        localFileHandle = handle;
        localFileName = handle.name;
        updateFileActions();
      }).catch(() => {});
    }
    return true;
  }

  /**
   * Chrome restores textarea and select values around page load and can emit
   * input events while doing it. The workspace (or the template default) is the
   * source of truth, so the saver is paused over that window and the values are
   * asserted again a moment later.
   */
  /**
   * A buffer carried back from the Studio belongs to no file: the editor shows
   * it as a new file, and "New file" is what saves it.
   */
  function applyCarriedBuffer(carried) {
    editor.value = carried.source;
    sourceModeSelect.value = carried.mode;
    suggestedFilename = `program${MODE_EXTENSIONS[carried.mode] ?? ""}`;
    projectFilePath = null;
    localFileHandle = null;
    localFileHandleId = null;
    localFileName = null;
    resetUndoHistory();
    updateFileButtonLabel();
    updateFileActions();
    updateEditorPlaceholder();
    showStatus(message, "Carried over from the Studio · not saved yet");
    saver.flush();
  }

  function bootstrapWorkspace() {
    saver.setPaused(true);
    const carried = takeHandout("editor");
    if (carried) {
      applyCarriedBuffer(carried);
      const expectedCode = editor.value;
      const expectedMode = sourceModeSelect.value;
      requestAnimationFrame(() => {
        setTimeout(() => {
          saver.setPaused(false);
          guardAgainstBrowserRestore(expectedCode, expectedMode, null);
        }, 300);
      });
      bootstrapped = true;
      return;
    }
    const restored = applyWorkspace();
    const expectedCode = restored ? editor.value : defaultAsm;
    const expectedMode = restored ? sourceModeSelect.value : "asm";
    const caret = restored && Number.isInteger(loadWorkspace()?.caret)
      ? loadWorkspace().caret
      : null;
    if (!restored) {
      editor.value = defaultAsm;
      sourceModeSelect.value = "asm";
      updateEditorPlaceholder();
      updateFileButtonLabel();
      updateFileActions();
      openNewFileDialog();
    }
    requestAnimationFrame(() => {
      if (restored) applyWorkspace();
      setTimeout(() => {
        saver.setPaused(false);
        guardAgainstBrowserRestore(expectedCode, expectedMode, caret);
      }, 300);
    });
    bootstrapped = true;
  }

  if (document.readyState === "complete") {
    setTimeout(bootstrapWorkspace, 0);
  } else {
    window.addEventListener("load", () => setTimeout(bootstrapWorkspace, 0), { once: true });
  }

  // Back/forward cache restores the DOM wholesale; re-apply the saved state.
  window.addEventListener("pageshow", (event) => {
    if (!event.persisted || !bootstrapped) return;
    saver.setPaused(true);
    applyWorkspace();
    setTimeout(() => saver.setPaused(false), 300);
  });

  /**
   * Chrome's form-state restoration can land a second late, putting the previous
   * session's text back into the textarea. Watch the value for a moment and put
   * the expected text back; any real keystroke or paste ends the guard, because
   * from then on the visible text belongs to the user.
   */
  function guardAgainstBrowserRestore(expectedCode, expectedMode, caret) {
    let timer = null;
    const stop = () => {
      if (timer !== null) clearInterval(timer);
      timer = null;
    };
    let attempts = 0;
    timer = setInterval(() => {
      if (attempts++ > 30) return stop();
      let changed = false;
      if (editor.value !== expectedCode) {
        editor.value = expectedCode;
        if (caret !== null) {
          const limit = Math.min(caret, editor.value.length);
          editor.setSelectionRange(limit, limit);
        }
        changed = true;
      }
      if (expectedMode && sourceModeSelect.value !== expectedMode) {
        sourceModeSelect.value = expectedMode;
        changed = true;
      }
      if (!changed) stop();
    }, 100);
    editor.addEventListener("keydown", stop, { once: true });
    editor.addEventListener("paste", stop, { once: true });
  }
} else if (page === "visualize") {
  const root = document.querySelector("#viz-root");
  let raw = sessionStorage.getItem("opt-sp-trace");
  if (!raw) {
    // Handed over by the studio, whose new tab cannot inherit sessionStorage.
    raw = localStorage.getItem("opt-sp-visualize-trace");
    if (raw) localStorage.removeItem("opt-sp-visualize-trace");
  }
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
      for (const entry of document.querySelectorAll(".studio-entry")) {
        entry.addEventListener("click", () => {
          const source = visualizer.liveMode
            ? visualizer.liveEditor.value
            : visualizer.sourceText;
          writeHandout(visualizer.mode, source);
        });
      }
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
      if (badge) {
        badge.dataset.state = state;
        badge.textContent = state;
      }
      if (name === "py") {
        updateSyncButton();
      }
    },
    onWrite: (name) => {
      if (name === "sp") renderPreview();
    },
    onDerived: (name) => {
      if (name !== "py") scheduleAutoSync();
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
    layout: document.querySelector(".studio-layout"),
    container: document.querySelector(".studio-editors"),
    toggleButton: document.querySelector("#pane-layout-toggle"),
  });

  // "Back to editor" asks which representation to carry. The pane being edited
  // is preselected, because that is usually the one the user means; the other
  // two stay one click away. An empty studio has nothing to carry, so the link
  // simply navigates and the editor keeps its own workspace.
  const modeByPane = { py: "python", spasm: "asm", sp: "sp" };
  const carryDialog = document.querySelector("#carry-dialog");

  const paneText = (pane) =>
    pane === "spasm" ? stripAnnotations(panes[pane].value) : panes[pane].value;

  function carryToEditor(pane) {
    const text = paneText(pane);
    if (text.trim()) writeHandout(modeByPane[pane], text, "editor");
    location.href = "/editor";
  }

  for (const link of document.querySelectorAll(".back-link")) {
    link.addEventListener("click", (event) => {
      const active = engine.authoritative ?? "py";
      if (!carryDialog || !paneText(active).trim()) return;
      event.preventDefault();
      if (typeof carryDialog.showModal === "function") carryDialog.showModal();
      else carryDialog.setAttribute("open", "");
      carryDialog.querySelector(`button[data-pane="${active}"]`)?.focus();
    });
  }
  for (const button of carryDialog?.querySelectorAll("button[data-pane]") ?? []) {
    button.addEventListener("click", () => carryToEditor(button.dataset.pane));
  }
  carryDialog?.querySelector("#carry-cancel")?.addEventListener("click", () => {
    carryDialog.close();
  });

  // --- AI mirror sync -----------------------------------------------------
  const llmButton = document.querySelector("#llm-settings-button");
  if (llmButton) llmButton.hidden = false;
  const llmDialog = document.querySelector("#llm-settings");
  const llmSettings = initLLMSettings({ dialog: llmDialog, openers: [llmButton] });
  const syncButton = document.querySelector("#py-sync-button");
  const syncStatus = document.querySelector("#py-sync-status");
  let syncing = false;
  let lastSyncAt = 0;
  let autoTimer = null;
  let lastAttempt = null;

  function setSyncStatus(text, isError = false) {
    if (!syncStatus) return;
    syncStatus.hidden = !text;
    syncStatus.textContent = text;
    syncStatus.classList.toggle("error", Boolean(text) && Boolean(isError));
  }

  function updateSyncButton() {
    if (!syncButton) return;
    const mode = llmSettings.get().mode;
    syncButton.hidden = mode === "off" || syncing || engine.state.py !== "stale";
  }

  /**
   * Arm the auto sync. Called after every completed derivation, so repeated
   * edits keep re-arming it; the cooldown delays the call instead of dropping
   * it, and an identical retry after a failure is skipped so a hopeless request
   * cannot loop forever.
   */
  function scheduleAutoSync() {
    if (llmSettings.get().mode !== "auto" || syncing) return;
    if (!panes.py.value.trim()) return;
    clearTimeout(autoTimer);
    if (lastAttempt
      && lastAttempt.py === panes.py.value
      && lastAttempt.spasm === panes.spasm.value) {
      return;
    }
    const cooldownLeft = Math.max(0, 5000 - (Date.now() - lastSyncAt));
    autoTimer = setTimeout(() => { void syncPy(); }, Math.max(1500, cooldownLeft));
  }

  async function syncPy() {
    if (syncing) return;
    const spasm = panes.spasm.value;
    if (!spasm.trim()) {
      setSyncStatus("Nothing to sync: the assembly pane is empty.", true);
      return;
    }
    syncing = true;
    lastAttempt = { py: panes.py.value, spasm };
    if (syncButton) syncButton.disabled = true;
    updateSyncButton();
    setSyncStatus("asking the model\u2026");
    try {
      const result = await refinePy({
        py: panes.py.value,
        spasm,
        headers: llmHeaders(llmSettings.get()),
      });
      if (!result.ok) {
        setSyncStatus(describeError(result), true);
        return;
      }
      if (panes.spasm.value !== spasm) {
        // The assembly moved while the model was working: this answer describes
        // the previous program, so it must not be written.
        setSyncStatus("the assembly changed while syncing; the answer was discarded", true);
        return;
      }
      engine.write("py", result.py);
      engine.setState("py", "synced");
      const tokens = result.usage?.completion_tokens;
      setSyncStatus(tokens ? `mirror verified \u00b7 ${tokens} output tokens` : "mirror verified");
    } finally {
      syncing = false;
      lastSyncAt = Date.now();
      if (syncButton) syncButton.disabled = false;
      updateSyncButton();
      if (engine.state.py === "stale") scheduleAutoSync();
    }
  }

  syncButton?.addEventListener("click", () => void syncPy());
  llmDialog?.addEventListener("close", () => {
    updateSyncButton();
    if (llmSettings.get().mode !== "auto") clearTimeout(autoTimer);
    else scheduleAutoSync();
  });
  updateSyncButton();

  const optSpLink = document.querySelector("#opt-sp-link");
  if (optSpLink) optSpLink.hidden = false;

  // Already inside the studio: the header shortcut would open a second one.
  const headerStudioLink = document.querySelector("#studio-link");
  if (headerStudioLink) headerStudioLink.hidden = true;
  const studioMenuLink = document.querySelector("#studio-menu-link");
  if (studioMenuLink) studioMenuLink.hidden = true;

  const MODES = { py: "python", spasm: "asm", sp: "sp" };
  const panel = new TracePanel({
    root: document.querySelector(".studio-layout"),
    codeRoot: document.querySelector("#trace-code"),
    trace: [],
    sourceText: "",
  });
  let controlsBound = false;
  let tracedPane = "py";

  window.addEventListener("keydown", (event) => {
    if (event.target instanceof HTMLElement &&
      event.target.closest("input, textarea, select, [contenteditable='true']")) return;
    if (event.key === "ArrowLeft") panel.render(panel.stepIndex - 1);
    if (event.key === "ArrowRight") panel.render(panel.stepIndex + 1);
  });

  const followToggle = document.querySelector("#trace-follow-toggle");
  const FOLLOW_KEY = "opt-sp-trace-follow";
  let follow = localStorage.getItem(FOLLOW_KEY) !== "0";
  const applyFollow = () => {
    panel.setFollow(follow);
    if (!followToggle) return;
    followToggle.setAttribute("aria-pressed", String(follow));
    followToggle.title = follow
      ? "Following the active line: scrolls the code view"
      : "Not following: the code view stays where you put it";
  };
  applyFollow();
  followToggle?.addEventListener("click", () => {
    follow = !follow;
    localStorage.setItem(FOLLOW_KEY, follow ? "1" : "0");
    applyFollow();
  });

  const markTracedPane = (name) => {
    for (const element of document.querySelectorAll(".editor-pane")) {
      element.classList.toggle("traced", element.dataset.pane === name);
    }
  };

  const tracePane = async (name) => {
    tracedPane = name;
    const source = panes[name].value;
    const traceCode = document.querySelector("#trace-code");
    if (!source) {
      traceCode.textContent = "Nothing to run: this pane is empty.";
      return null;
    }
    traceCode.textContent = "Running…";
    let result;
    try {
      const { kernel } = await import("./spacelang-kernel.js");
      result = await kernel.trace(source, MODES[name]);
    } catch (error) {
      result = { ok: false, trace: [], error: error?.message || String(error) };
    }
    if (!result.ok || !result.trace?.length) {
      traceCode.textContent = result.error || "No execution trace was produced.";
      return null;
    }
    markTracedPane(name);
    panel.setTrace(result.trace, source);
    panel.render(0);
    if (!controlsBound) {
      panel.bindControls();
      controlsBound = true;
    }
    return result;
  };

  document.querySelector("#py-run-button")?.addEventListener("click", () => void tracePane("py"));
  document.querySelector("#spasm-run-button")?.addEventListener("click", () => void tracePane("spasm"));
  document.querySelector("#sp-run-button")?.addEventListener("click", () => void tracePane("sp"));

  const visualizeLink = document.querySelector("#visualize-link");
  if (visualizeLink) {
    visualizeLink.hidden = false;
    visualizeLink.addEventListener("click", async (event) => {
      event.preventDefault();
      const source = panes[tracedPane].value;
      const mode = MODES[tracedPane];
      let result;
      try {
        const { kernel } = await import("./spacelang-kernel.js");
        result = await kernel.trace(source, mode);
      } catch (error) {
        result = { ok: false, trace: [], error: error?.message || String(error) };
      }
      // A new tab opened with noopener does not inherit sessionStorage, so the
      // payload travels through localStorage and is consumed on arrival.
      localStorage.setItem("opt-sp-visualize-trace", JSON.stringify({
        trace: result.trace ?? [],
        error: result.ok ? null : result.error,
        code: source,
        mode,
        filename: tracedPane,
        projectFilePath: null,
        localFileHandleId: null,
        localFileName: null,
      }));
      window.open("visualize.html", "_blank", "noopener");
    });
  }

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
} else if (page === "docs" || page === "tutorial") {
  initDocNavigation();
} else if (page === "home") {
  // The scene (3D point cloud + styles) is only fetched on the home page.
  import("./home.js")
    .then((module) => module.initHomeScene())
    .catch((error) => console.error("Home scene module failed to load:", error));
}

// The settings menu is shared by every page. Entries that only make sense
// somewhere specific are unhidden there (the studio and the editor branch do
// that for their own items); these two are global.
const homeMenuLink = document.querySelector("#home-menu-link");
if (homeMenuLink) homeMenuLink.hidden = page === "home";

const llmMenuButton = document.querySelector("#llm-settings-button");
if (llmMenuButton) llmMenuButton.hidden = false;
const llmMenuDialog = document.querySelector("#llm-settings");
// The studio already wired this dialog for its sync engine.
if (page !== "studio" && llmMenuButton && llmMenuDialog) {
  initLLMSettings({ dialog: llmMenuDialog, openers: [llmMenuButton] });
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

  // Choosing an entry ends the menu's job, including when the entry opens a
  // dialog (the dialog then owns the screen, not the menu).
  settingsMenu.addEventListener("click", (event) => {
    if (event.target.closest(".settings-menu-item")) closeSettingsMenu();
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

// The assistant lives on the pages that have something to talk about. It is
// loaded on demand so documentation pages never download it.
const chatPanel = document.querySelector("#chat-panel");
if (chatPanel) {
  chatPanel.dataset.page = page;
  import("./chat-panel.js")
    .then((module) =>
      module.initChatPanel({ root: chatPanel, page, drawer: page !== "home" })
    )
    .catch((error) => console.error("Assistant failed to load:", error));
}

void checkAssets();
