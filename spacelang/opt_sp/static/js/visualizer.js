import { bindAutoCompletion, bindDragMove, bindUndoRedo } from "./editor.js";
import { TracePanel } from "./trace-panel.js";

/**
 * The classic trace page: a code panel with live editing, plus a TracePanel.
 *
 * Rendering and the step controls live in TracePanel so the studio page can
 * reuse them; this class only adds the page-specific live-edit behaviour and
 * the editor/trace column resizer.
 */
export class Visualizer {
  constructor(rootElement, trace, sourceText, mode = "asm", overwriteTarget = {}) {
    this.root = rootElement;
    this.trace = trace;
    this.sourceText = sourceText ?? "";
    this.mode = mode ?? "asm";
    this.projectFilePath = overwriteTarget.projectFilePath ?? null;
    this.localFileHandleId = overwriteTarget.localFileHandleId ?? null;
    this.localFileName = overwriteTarget.localFileName ?? null;
    this.liveMode = false;
    this.liveRevision = 0;
    this.liveTimer = null;
    this.kernelPromise = null;
    this.liveToggle = this.root.querySelector("#live-edit-toggle");
    this.liveEditor = this.root.querySelector("#live-editor");
    this.liveStatus = this.root.querySelector("#live-status");

    this.panel = new TracePanel({
      root: this.root,
      codeRoot: this.root.querySelector("#code-view"),
      trace: this.trace,
      sourceText: this.sourceText,
    });
    this.liveEditor.value = this.sourceText;
  }

  get stepIndex() {
    return this.panel.stepIndex;
  }

  render(stepIndex) {
    this.panel.render(stepIndex);
  }

  bindControls() {
    this.panel.bindControls();
    if (this.root.querySelector(".column-resizer")) this.bindColumnResizer();
    this.bindLiveEditing();
  }

  bindColumnResizer() {
    const handle = this.root.querySelector(".column-resizer");
    const minWidth = 240;

    const availableWidth = () => {
      const styles = getComputedStyle(this.root);
      const gap = parseFloat(styles.columnGap);
      const padding = parseFloat(styles.paddingLeft) + parseFloat(styles.paddingRight);
      return this.root.clientWidth - padding - gap * 2 - 6;
    };

    window.addEventListener("resize", () => {
      if (window.innerWidth <= 760) this.root.style.removeProperty("--program-width");
    });

    const setProgramWidth = (width) => {
      const available = availableWidth();
      const programWidth = Math.max(
        minWidth,
        Math.min(available - minWidth, width),
      );
      this.root.style.setProperty("--program-width", `${programWidth}px`);
      handle.setAttribute("aria-valuemax", String(Math.round(available - minWidth)));
      handle.setAttribute("aria-valuenow", String(Math.round(programWidth)));
    };

    const initialWidth = this.root.querySelector(".code-panel").getBoundingClientRect().width;
    handle.setAttribute("aria-valuemax", String(Math.round(availableWidth() - minWidth)));
    handle.setAttribute("aria-valuenow", String(Math.round(initialWidth)));

    handle.addEventListener("pointerdown", (event) => {
      if (event.button !== 0 || this.root.clientWidth < 761) return;
      event.preventDefault();
      const startX = event.clientX;
      const startWidth = this.root.querySelector(".code-panel").getBoundingClientRect().width;
      handle.setPointerCapture(event.pointerId);
      const move = (moveEvent) => setProgramWidth(startWidth + moveEvent.clientX - startX);
      const stop = () => {
        handle.removeEventListener("pointermove", move);
        handle.removeEventListener("pointerup", stop);
        handle.removeEventListener("pointercancel", stop);
      };
      handle.addEventListener("pointermove", move);
      handle.addEventListener("pointerup", stop);
      handle.addEventListener("pointercancel", stop);
    });

    handle.addEventListener("keydown", (event) => {
      const delta = event.key === "ArrowRight" ? 16 : event.key === "ArrowLeft" ? -16 : 0;
      if (!delta) return;
      event.preventDefault();
      event.stopPropagation();
      const width = this.root.querySelector(".code-panel").getBoundingClientRect().width;
      setProgramWidth(width + delta);
    });
  }

  bindLiveEditing() {
    bindUndoRedo(this.liveEditor);
    bindAutoCompletion(this.liveEditor);
    bindDragMove(this.liveEditor);
    this.liveToggle.addEventListener("click", () => {
      this.liveMode = !this.liveMode;
      this.liveToggle.setAttribute("aria-pressed", String(this.liveMode));
      this.liveToggle.textContent = this.liveMode ? "Exit live edit" : "Live edit";
      this.liveEditor.hidden = !this.liveMode;
      this.root.querySelector("#code-view").hidden = this.liveMode;
      this.liveStatus.hidden = !this.liveMode;
      if (this.liveMode) {
        this.liveStatus.textContent = "Live mode: edits update the trace automatically.";
        this.liveEditor.focus();
      } else {
        this.liveRevision += 1;
        clearTimeout(this.liveTimer);
      }
    });

    this.liveEditor.addEventListener("input", () => {
      this.liveRevision += 1;
      const revision = this.liveRevision;
      clearTimeout(this.liveTimer);
      this.liveStatus.classList.remove("error");
      this.liveStatus.textContent = "Waiting to update preview…";
      this.liveTimer = setTimeout(() => this.updateLiveTrace(revision), 300);
    });
  }

  async updateLiveTrace(revision) {
    if (!this.liveMode || revision !== this.liveRevision) return;
    this.liveStatus.textContent = "Updating preview…";
    try {
      this.kernelPromise ??= import("./spacelang-kernel.js");
      const { kernel } = await this.kernelPromise;
      if (!this.liveMode || revision !== this.liveRevision) return;
      const source = this.liveEditor.value;
      const result = await kernel.trace(source, this.mode);
      if (!this.liveMode || revision !== this.liveRevision) return;
      if (!result.ok || !result.trace.length) {
        this.liveStatus.classList.add("error");
        this.liveStatus.textContent = result.error
          ? `Preview not updated; showing the last successful trace.\n${result.error}`
          : "No execution trace was produced.";
        return;
      }

      this.liveStatus.classList.remove("error");
      this.liveStatus.textContent = "Preview updated.";
      this.trace = result.trace;
      this.sourceText = source;
      this.liveEditor.value = source;
      this.panel.setTrace(result.trace, source);
      this.panel.render(this.trace.length - 1);
    } catch (error) {
      if (revision !== this.liveRevision) return;
      this.liveStatus.classList.add("error");
      this.liveStatus.textContent = `Live update failed: ${error.message || String(error)}`;
    }
  }
}
