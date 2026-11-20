/**
 * One-shot handoff between tabs.
 *
 * `sessionStorage` is per-tab, so the studio (which opens in a new tab) cannot
 * read the source the launching page was showing. The launcher writes a short
 * lived record here; the studio consumes and deletes it, so a later direct visit
 * to /studio always starts empty.
 */

const KEY = "opt-sp-handout";
const TTL_MS = 5 * 60 * 1000;
const MODES = ["python", "asm", "sp"];

export function writeHandout(mode, source) {
  try {
    localStorage.setItem(KEY, JSON.stringify({ mode, source, at: Date.now() }));
  } catch {
    // Storage may be unavailable; the studio then simply opens empty.
  }
}

export function takeHandout() {
  let raw = null;
  try {
    raw = localStorage.getItem(KEY);
    localStorage.removeItem(KEY);
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
