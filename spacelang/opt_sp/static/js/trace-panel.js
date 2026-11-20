/**
 * Renders one execution trace: the source listing, the four state panels and
 * the step controls.
 *
 * Extracted from the visualizer so the studio page can drive the same widgets
 * without duplicating any of the rendering logic. The panel knows nothing about
 * where the trace came from -- the caller passes a trace and its source text.
 */

export class TracePanel {
  constructor({ root, codeRoot, trace = [], sourceText = "" }) {
    this.root = root;
    this.codeRoot = codeRoot;
    this.trace = trace;
    this.sourceText = sourceText;
    this.stepIndex = 0;
    this.autoplayTimer = null;
    this.slider = root.querySelector("#step-slider");
    this.label = root.querySelector("#step-label");
    this.autoplayButton = root.querySelector("#autoplay-button");
    this.autoplaySpeed = root.querySelector("#autoplay-speed");
    this.autoplaySpeedLabel = root.querySelector("#autoplay-speed-label");
    this.syncSlider();
  }

  setTrace(trace, sourceText) {
    this.trace = trace ?? [];
    if (typeof sourceText === "string") this.sourceText = sourceText;
    this.stepIndex = 0;
    this.syncSlider();
  }

  syncSlider() {
    if (this.slider) this.slider.max = String(Math.max(0, this.trace.length - 1));
  }

  _panel(id) {
    return this.root.querySelector(`#${id} .panel-content`);
  }

  _element(tag, className, text) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined) element.textContent = text;
    return element;
  }

  _renderCode(step) {
    if (!this.codeRoot) return;
    this.codeRoot.replaceChildren();
    const lines = this.sourceText.split("\n");
    const activeLine = Number.isInteger(step.source_line) && step.source_line > 0
      ? step.source_line - 1
      : step.ip;
    lines.forEach((text, index) => {
      const line = this._element("span", "code-line");
      if (index === activeLine) line.classList.add("active");
      line.append(this._element("span", "line-number", String(index + 1)));
      line.append(document.createTextNode(text));
      this.codeRoot.append(line);
    });
  }

  _renderCallStack(frames) {
    const target = this._panel("call-stack");
    target.replaceChildren();
    [...frames].reverse().forEach((frame, index) => {
      const card = this._element("article", "frame");
      if (index === 0) card.classList.add("active");
      card.append(this._element("div", "frame-title", frame.func));
      const table = this._element("table", "locals-table");
      const body = this._element("tbody");
      for (const [name, value] of Object.entries(frame.locals)) {
        const row = this._element("tr");
        row.append(this._element("td", "", name));
        row.append(this._element("td", "", value.repr));
        body.append(row);
      }
      table.append(body);
      card.append(table);
      target.append(card);
    });
  }

  _renderOperandStack(values) {
    const target = this._panel("operand-stack");
    target.replaceChildren();
    const list = this._element("div", "stack-list");
    [...values].reverse().forEach((value) => {
      const pill = this._element("div", "value-pill");
      pill.append(this._element("span", "value-type", value.type));
      pill.append(this._element("span", "", value.repr));
      list.append(pill);
    });
    target.append(list);
  }

  _renderHeap(heap) {
    const target = this._panel("heap");
    target.replaceChildren();
    for (const [id, object] of Object.entries(heap)) {
      const node = this._element("article", "heap-node");
      node.append(this._element("span", "heap-type", object.type));
      node.append(this._element("span", "ref-chip", `#${id}`));
      node.append(this._element("span", "heap-repr", object.repr));
      for (const ref of object.refs) {
        node.append(this._element("span", "ref-chip", `→ #${ref}`));
      }
      target.append(node);
    }
  }

  render(stepIndex) {
    if (!this.trace.length) return;
    this.stepIndex = Math.max(0, Math.min(stepIndex, this.trace.length - 1));
    const step = this.trace[this.stepIndex];
    this._renderCode(step);
    this._renderCallStack(step.call_stack);
    this._renderOperandStack(step.operand_stack);
    this._renderHeap(step.heap);
    const outputPanel = this._panel("output");
    const previousScrollTop = outputPanel.scrollTop;
    const output = this._element("pre", "output-text", step.output);
    outputPanel.replaceChildren(output);
    outputPanel.scrollTop = previousScrollTop;
    if (this.slider) this.slider.value = String(this.stepIndex);
    if (this.label) this.label.textContent = `Step ${this.stepIndex + 1} / ${this.trace.length}`;
    if (this.autoplayButton) {
      this.autoplayButton.disabled = this.stepIndex === this.trace.length - 1;
      if (this.autoplayButton.disabled && this.autoplayTimer !== null) {
        this.stopAutoplay();
      }
    }
    const previousError = this.root.querySelector(".trace-error");
    if (previousError) previousError.remove();
    if (step.error) {
      const banner = this._element("div", "error-banner trace-error", step.error);
      this.root.prepend(banner);
    }
  }

  bindControls() {
    this.root.querySelector('[data-step="first"]')?.addEventListener("click", () => this.render(0));
    this.root.querySelector('[data-step="back"]')?.addEventListener("click", () => this.render(this.stepIndex - 1));
    this.root.querySelector('[data-step="forward"]')?.addEventListener("click", () => this.render(this.stepIndex + 1));
    this.root.querySelector('[data-step="last"]')?.addEventListener("click", () => this.render(this.trace.length - 1));
    this.slider?.addEventListener("input", () => this.render(Number(this.slider.value)));
    this.autoplayButton?.addEventListener("click", () => {
      if (this.autoplayTimer === null) this.startAutoplay();
      else this.stopAutoplay();
    });
    this.autoplaySpeed?.addEventListener("input", () => {
      const seconds = Number(this.autoplaySpeed.value) / 1000;
      this.autoplaySpeedLabel.textContent = `${seconds.toFixed(2)} s / step`;
    });
    this.bindPanelResizers();
    this.bindPanelReordering();
  }

  startAutoplay() {
    if (!this.autoplayButton) return;
    if (this.stepIndex >= this.trace.length - 1) return;
    this.autoplayButton.textContent = "⏸";
    this.autoplayButton.setAttribute("aria-label", "Stop autoplay");
    this.autoplayButton.title = "Stop autoplay";
    this.autoplayButton.setAttribute("aria-pressed", "true");
    this.scheduleAutoplayStep();
  }

  scheduleAutoplayStep() {
    const interval = Number(this.autoplaySpeed.value);
    this.autoplayTimer = setTimeout(() => {
      this.autoplayTimer = null;
      if (this.stepIndex >= this.trace.length - 1) {
        this.stopAutoplay();
        return;
      }
      this.render(this.stepIndex + 1);
      if (this.stepIndex < this.trace.length - 1) this.scheduleAutoplayStep();
      else this.stopAutoplay();
    }, interval);
  }

  stopAutoplay() {
    if (this.autoplayTimer !== null) clearTimeout(this.autoplayTimer);
    this.autoplayTimer = null;
    if (!this.autoplayButton) return;
    this.autoplayButton.textContent = "▶";
    this.autoplayButton.setAttribute("aria-label", "Autoplay");
    this.autoplayButton.title = "Autoplay";
    this.autoplayButton.setAttribute("aria-pressed", "false");
  }

  bindPanelResizers() {
    const minHeight = 120;
    const resizers = [...this.root.querySelectorAll(".panel-resizer")];
    const syncResizerAvailability = () => {
      resizers.forEach((handle) => {
        const upper = handle.previousElementSibling;
        const lower = handle.nextElementSibling;
        const available = upper?.open && lower?.open;
        handle.classList.toggle("disabled", !available);
        handle.setAttribute("aria-disabled", String(!available));
      });
    };

    this.root.querySelectorAll(".state-panels .panel").forEach((panel) => {
      panel.addEventListener("toggle", syncResizerAvailability);
    });

    resizers.forEach((handle) => {
      const setUpperHeight = (upper, lower, height, total) => {
        const upperHeight = Math.max(minHeight, Math.min(total - minHeight, height));
        upper.style.height = `${upperHeight}px`;
        lower.style.height = `${total - upperHeight}px`;
        handle.setAttribute("aria-valuemin", String(minHeight));
        handle.setAttribute("aria-valuemax", String(total - minHeight));
        handle.setAttribute("aria-valuenow", String(Math.round(upperHeight)));
      };

      handle.addEventListener("pointerdown", (event) => {
        if (event.button !== 0 || handle.getAttribute("aria-disabled") === "true") return;
        event.preventDefault();
        const upper = handle.previousElementSibling;
        const lower = handle.nextElementSibling;
        const startY = event.clientY;
        const upperHeight = upper.getBoundingClientRect().height;
        const total = upperHeight + lower.getBoundingClientRect().height;
        handle.setPointerCapture(event.pointerId);
        const move = (moveEvent) => setUpperHeight(
          upper,
          lower,
          upperHeight + moveEvent.clientY - startY,
          total,
        );
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
        if (handle.getAttribute("aria-disabled") === "true") return;
        const delta = event.key === "ArrowDown" ? 16 : event.key === "ArrowUp" ? -16 : 0;
        if (!delta) return;
        event.preventDefault();
        event.stopPropagation();
        const upper = handle.previousElementSibling;
        const lower = handle.nextElementSibling;
        const upperHeight = upper.getBoundingClientRect().height;
        const total = upperHeight + lower.getBoundingClientRect().height;
        setUpperHeight(upper, lower, upperHeight + delta, total);
      });
    });
    syncResizerAvailability();
  }

  bindPanelReordering() {
    const container = this.root.querySelector(".state-panels");
    if (!container) return;
    const panels = () => [...container.querySelectorAll(":scope > .panel")];
    const resizers = [...container.querySelectorAll(":scope > .panel-resizer")];
    let activeDrag = null;
    let suppressToggle = false;

    const updateResizerLabels = () => {
      resizers.forEach((handle) => {
        const upper = handle.previousElementSibling.querySelector("summary").textContent;
        const lower = handle.nextElementSibling.querySelector("summary").textContent;
        handle.setAttribute("aria-label", `Resize ${upper} and ${lower} panels`);
        const available = handle.previousElementSibling.open && handle.nextElementSibling.open;
        handle.classList.toggle("disabled", !available);
        handle.setAttribute("aria-disabled", String(!available));
      });
    };

    const placePanels = (orderedPanels) => {
      const children = orderedPanels.flatMap((panel, index) => (
        index < resizers.length ? [panel, resizers[index]] : [panel]
      ));
      container.append(...children);
      updateResizerLabels();
    };

    const reorderAt = (panel, clientX, clientY) => {
      const target = document.elementFromPoint(clientX, clientY)?.closest(".panel");
      if (!target || target === panel || target.parentElement !== container) return;

      const currentPanels = panels();
      const orderedPanels = currentPanels.filter((item) => item !== panel);
      const targetIndex = orderedPanels.indexOf(target);
      const targetBounds = target.getBoundingClientRect();
      const insertAfter = clientY >= targetBounds.top + targetBounds.height / 2;
      orderedPanels.splice(targetIndex + Number(insertAfter), 0, panel);
      if (currentPanels.some((item, index) => item !== orderedPanels[index])) {
        const previousTops = new Map(
          currentPanels.map((item) => [item, item.getBoundingClientRect().top]),
        );
        placePanels(orderedPanels);
        if (!window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
          panels().forEach((item) => {
            if (item === panel) return;
            const offset = previousTops.get(item) - item.getBoundingClientRect().top;
            if (Math.abs(offset) < 1) return;
            item.animate(
              [{ transform: `translateY(${offset}px)` }, { transform: "translateY(0)" }],
              { duration: 180, easing: "cubic-bezier(.2, .75, .3, 1)" },
            );
          });
        }
      }
    };

    const stopDragging = (event) => {
      if (!activeDrag || event.pointerId !== activeDrag.pointerId) return;
      activeDrag.panel.classList.remove("drag-placeholder");
      activeDrag.preview?.remove();
      container.classList.remove("reordering");
      if (activeDrag.moved) {
        event.preventDefault();
        setTimeout(() => { suppressToggle = false; }, 0);
      }
      activeDrag = null;
    };

    window.addEventListener("pointermove", (event) => {
      if (!activeDrag || event.pointerId !== activeDrag.pointerId) return;
      if (!activeDrag.moved
        && Math.hypot(event.clientX - activeDrag.startX, event.clientY - activeDrag.startY) < 6) return;
      activeDrag.moved = true;
      suppressToggle = true;
      event.preventDefault();
      container.classList.add("reordering");
      if (!activeDrag.preview) {
        const bounds = activeDrag.panel.getBoundingClientRect();
        const preview = activeDrag.panel.cloneNode(true);
        preview.removeAttribute("id");
        preview.querySelectorAll("[id]").forEach((element) => element.removeAttribute("id"));
        preview.setAttribute("aria-hidden", "true");
        preview.inert = true;
        preview.classList.add("drag-preview");
        Object.assign(preview.style, {
          left: `${bounds.left}px`,
          top: `${bounds.top}px`,
          width: `${bounds.width}px`,
          height: `${bounds.height}px`,
          margin: "0",
        });
        document.body.append(preview);
        activeDrag.preview = preview;
        activeDrag.panel.classList.add("drag-placeholder");
      }
      activeDrag.preview.style.left = `${event.clientX - activeDrag.grabOffsetX}px`;
      activeDrag.preview.style.top = `${event.clientY - activeDrag.grabOffsetY}px`;
      reorderAt(activeDrag.panel, event.clientX, event.clientY);
    });
    window.addEventListener("pointerup", stopDragging);
    window.addEventListener("pointercancel", stopDragging);

    container.querySelectorAll(":scope > .panel > summary").forEach((summary) => {
      const panel = summary.parentElement;
      summary.setAttribute("aria-keyshortcuts", "Alt+ArrowUp Alt+ArrowDown");

      summary.addEventListener("pointerdown", (event) => {
        if (event.button !== 0 || activeDrag) return;
        const bounds = panel.getBoundingClientRect();
        activeDrag = {
          panel,
          pointerId: event.pointerId,
          startX: event.clientX,
          startY: event.clientY,
          grabOffsetX: event.clientX - bounds.left,
          grabOffsetY: event.clientY - bounds.top,
          moved: false,
        };
      });

      summary.addEventListener("keydown", (event) => {
        if (!event.altKey || !["ArrowUp", "ArrowDown"].includes(event.key)) return;
        const orderedPanels = panels();
        const index = orderedPanels.indexOf(panel);
        const destination = Math.max(
          0,
          Math.min(orderedPanels.length - 1, index + (event.key === "ArrowUp" ? -1 : 1)),
        );
        if (destination === index) return;
        event.preventDefault();
        orderedPanels.splice(index, 1);
        orderedPanels.splice(destination, 0, panel);
        placePanels(orderedPanels);
        summary.focus({ preventScroll: true });
      });
    });

    container.addEventListener("click", (event) => {
      if (!suppressToggle) return;
      event.preventDefault();
      event.stopPropagation();
      suppressToggle = false;
    }, true);
  }
}
