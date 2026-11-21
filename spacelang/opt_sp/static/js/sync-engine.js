/**
 * Keeps the three studio panes consistent.
 *
 * Only the forward direction has a rule: `py` compiles to a program, which
 * disassembles to `spasm` and encodes to `sp`; `spasm` and `sp` convert into
 * each other. Nothing converts back to `py`, so the mirror can only be rebuilt
 * by the model -- the engine marks it `stale` and leaves the text alone.
 */

import { kernel } from "./spacelang-kernel.js";

const DEBOUNCE_MS = 250;
const DERIVATIONS = { py: ["spasm", "sp"], spasm: ["sp"], sp: ["spasm"] };
const NAMES = ["py", "spasm", "sp"];
// disassemble() ends every instruction with "; line=4 spaces=17,10".
const ANNOTATION = /\s*; line=\d+ spaces=[0-9,]*$/;

/** Drop the encoder debug comments from an assembly listing. */
export function stripAnnotations(text) {
  return text
    .split("\n")
    .map((line) => line.replace(ANNOTATION, ""))
    .join("\n");
}

export class SyncEngine {
  constructor({ panes, onStateChange, onWrite, onDerived, annotations = true }) {
    this.panes = panes;
    this.onStateChange = onStateChange ?? (() => {});
    this.onWrite = onWrite ?? (() => {});
    this.onDerived = onDerived ?? (() => {});
    this.annotations = annotations;
    this.revision = { py: 0, spasm: 0, sp: 0 };
    this.timer = { py: null, spasm: null, sp: null };
    this.applying = { py: false, spasm: false, sp: false };
    this.state = { py: "synced", spasm: "synced", sp: "synced" };
    this.authoritative = null;
    for (const name of NAMES) {
      panes[name].addEventListener("input", () => this.onInput(name));
    }
  }

  /** Seed the workspace from a pane and derive from it immediately. */
  start(name) {
    this.authoritative = name;
    this.revision[name] += 1;
    return this.derive(name, this.revision[name]);
  }

  onInput(name) {
    if (this.applying[name]) return;
    this.authoritative = name;
    this.revision[name] += 1;
    this.setState(name, "editing");
    clearTimeout(this.timer[name]);
    this.timer[name] = setTimeout(
      () => void this.derive(name, this.revision[name]),
      DEBOUNCE_MS,
    );
  }

  async derive(name, revision) {
    if (revision !== this.revision[name]) return;
    // Snapshot before awaiting: a pane edited during the conversion must not
    // be overwritten when the result lands.
    const stamps = {};
    for (const target of DERIVATIONS[name]) stamps[target] = this.revision[target];

    let result;
    try {
      result = await kernel.convert(this.panes[name].value, name);
    } catch (error) {
      result = { ok: false, error: error?.message || String(error), texts: {} };
    }
    if (revision !== this.revision[name]) return;
    if (!result.ok) {
      this.setState(name, "error");
      return;
    }
    this.setState(name, "synced");
    for (const target of DERIVATIONS[name]) {
      if (this.revision[target] !== stamps[target]) continue;
      let text = result.texts?.[target];
      if (typeof text !== "string") continue;
      if (target === "spasm" && !this.annotations) text = stripAnnotations(text);
      this.write(target, text);
      this.setState(target, "synced");
    }
    if (name !== "py") this.setState("py", "stale");
    // Fires on every completed derivation, not only when the badge changes:
    // auto-sync must run again after each edit, even while py stays stale.
    this.onDerived(name);
  }

  /**
   * Show or hide the encoder comments in the assembly pane.
   *
   * Hiding is a pure text transform, and the annotated form is cached so a
   * toggle round-trip that changes nothing restores the exact original listing
   * (regenerating from the plain text would renumber the `line=` fields).
   * Restoring after an edit falls back to regenerating from the program.
   */
  async setAnnotations(annotations) {
    this.annotations = annotations;
    const pane = this.panes.spasm;
    if (!annotations) {
      this.annotated = pane.value;
      this.write("spasm", stripAnnotations(pane.value));
      return;
    }
    if (typeof this.annotated === "string" && stripAnnotations(this.annotated) === pane.value) {
      this.write("spasm", this.annotated);
      return;
    }
    let result;
    try {
      result = await kernel.annotate(pane.value);
    } catch {
      return;
    }
    if (result?.ok && typeof result.text === "string") {
      this.write("spasm", result.text);
    }
  }

  write(name, text) {
    const pane = this.panes[name];
    if (pane.value === text) return;
    const start = pane.selectionStart ?? 0;
    const end = pane.selectionEnd ?? start;
    this.applying[name] = true;
    pane.value = text;
    const limit = text.length;
    pane.selectionStart = Math.min(start, limit);
    pane.selectionEnd = Math.min(end, limit);
    this.applying[name] = false;
    // Any derivation still in flight for this pane is now out of date.
    this.revision[name] += 1;
    this.onWrite(name, text);
  }

  setState(name, state) {
    if (this.state[name] === state) return;
    this.state[name] = state;
    this.onStateChange(name, state);
  }
}
