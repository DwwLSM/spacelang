/**
 * One-shot handoff between tabs.
 *
 * `sessionStorage` is per-tab, so a page that opens another one cannot read the
 * source it was showing. The launcher writes a short lived record here; the
 * receiving page consumes and deletes it, so a later direct visit starts empty.
 *
 * Two directions share this module:
 *   - editor -> studio, when a "Studio" link is clicked;
 *   - studio -> editor, when "Back to editor" carries the active pane back.
 * They use separate keys, because the two tabs can be open at the same time.
 */

const KEYS = {
  studio: "opt-sp-handout",
  editor: "opt-sp-editor-handout",
};
const TTL_MS = 5 * 60 * 1000;
const MODES = ["python", "asm", "sp"];

export function writeHandout(mode, source, target = "studio") {
  const key = KEYS[target];
  if (!key) return;
  try {
    localStorage.setItem(key, JSON.stringify({ mode, source, at: Date.now() }));
  } catch {
    // Storage may be unavailable; the receiving page then simply opens empty.
  }
}

export function takeHandout(target = "studio") {
  const key = KEYS[target];
  if (!key) return null;
  let raw = null;
  try {
    raw = localStorage.getItem(key);
    localStorage.removeItem(key);
  } catch {
    return null;
  }
  if (!raw) return null;
  try {
    const value = JSON.parse(raw);
    if (typeof value?.source !== "string") return null;
    if (!MODES.includes(value.mode)) return null;
    if (!(Date.now() - value.at < TTL_MS)) return null;
    return value;
  } catch {
    return null;
  }
}
