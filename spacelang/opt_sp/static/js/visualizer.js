export class Visualizer {
  constructor(rootElement, trace, sourceText) {
    this.root = rootElement;
    this.trace = trace;
    this.sourceText = sourceText;
    this.stepIndex = 0;
    this.slider = this.root.querySelector("#step-slider");
    this.label = this.root.querySelector("#step-label");
    this.slider.max = String(Math.max(0, trace.length - 1));
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
    const code = this.root.querySelector("#code-view");
    code.replaceChildren();
    const lines = this.sourceText.split("\n");
    const activeLine = Number.isInteger(step.source_line) && step.source_line > 0
      ? step.source_line - 1
      : step.ip;
    lines.forEach((text, index) => {
      const line = this._element("span", "code-line");
      if (index === activeLine) line.classList.add("active");
      line.append(this._element("span", "line-number", String(index + 1)));
      line.append(document.createTextNode(text));
      code.append(line);
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
    const output = this._element("pre", "output-text", step.output);
    this._panel("output").replaceChildren(output);
    output.scrollTop = output.scrollHeight;
    this.slider.value = String(this.stepIndex);
    this.label.textContent = `Step ${this.stepIndex + 1} / ${this.trace.length}`;
    const previousError = this.root.querySelector(".error-banner");
    if (previousError) previousError.remove();
    if (step.error) {
      const banner = this._element("div", "error-banner", step.error);
      this.root.prepend(banner);
    }
  }

  bindControls() {
    this.root.querySelector('[data-step="first"]').addEventListener("click", () => this.render(0));
    this.root.querySelector('[data-step="back"]').addEventListener("click", () => this.render(this.stepIndex - 1));
    this.root.querySelector('[data-step="forward"]').addEventListener("click", () => this.render(this.stepIndex + 1));
    this.root.querySelector('[data-step="last"]').addEventListener("click", () => this.render(this.trace.length - 1));
    this.slider.addEventListener("input", () => this.render(Number(this.slider.value)));
  }
}
