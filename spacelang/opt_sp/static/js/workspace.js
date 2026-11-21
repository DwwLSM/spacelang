/**
 * The editor's working state.
 *
 * The editor and the visualizer are one workflow: running a program must not
 * lose the file you opened. The state lives in sessionStorage so two windows
 * stay independent, and it is written on a short debounce rather than on every
 * keystroke.
 */

const KEY = "opt-sp-workspace";
const SAVE_DELAY_MS = 400;

export function loadWorkspace() {
  try {
    const raw = sessionStorage.getItem(KEY);
    if (!raw) return null;
    const value = JSON.parse(raw);
    if (typeof value?.code !== "string") return null;
    if (typeof value?.mode !== "string") return null;
    return value;
  } catch {
    return null;
  }
}

export function saveWorkspace(state) {
  try {
    sessionStorage.setItem(KEY, JSON.stringify({ ...state, at: Date.now() }));
  } catch {
    // A full or disabled storage must never break editing.
  }
}

export function clearWorkspace() {
  try {
    sessionStorage.removeItem(KEY);
  } catch {
    // Ignore.
  }
}

/** Debounced writer; call schedule() on edits and flush() before leaving. */
export function createWorkspaceSaver(readState) {
  let timer = null;
  let paused = false;
  const flush = () => {
    clearTimeout(timer);
    timer = null;
    if (paused) return;
    saveWorkspace(readState());
  };
  const schedule = () => {
    if (paused) return;
    clearTimeout(timer);
    timer = setTimeout(flush, SAVE_DELAY_MS);
  };
  /**
   * Chrome restores textarea and select values around page load and can emit
   * input events while doing it; pausing keeps that restored value from being
   * persisted over the workspace we just applied.
   */
  const setPaused = (value) => {
    paused = Boolean(value);
    if (paused) clearTimeout(timer);
  };
  return { schedule, flush, setPaused };
}
