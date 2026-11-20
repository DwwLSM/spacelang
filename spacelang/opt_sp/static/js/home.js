/**
 * Home page: start the ASCII scene in the art column and keep a fallback.
 *
 * The static tree in `home.html` stays in the DOM until the scene has drawn its
 * first frame, so a browser without ES modules (or a broken import) still shows
 * something instead of an empty panel. The chosen style is remembered locally.
 */

import { createAsciiScene, sceneStyleNames } from "./ascii-scene.js";
import "./scene-christmas-tree.js";
import "./scene-token-rain.js";

const STORAGE_KEY = "opt-sp-scene-style";
const DEFAULT_STYLE = "christmas-tree";

function storedStyle() {
  try {
    return localStorage.getItem(STORAGE_KEY) || DEFAULT_STYLE;
  } catch {
    return DEFAULT_STYLE;
  }
}

function rememberStyle(name) {
  try {
    localStorage.setItem(STORAGE_KEY, name);
  } catch {
    /* private mode: the choice just does not survive a reload */
  }
}

export function initHomeScene() {
  const container = document.querySelector(".home-art");
  if (!container) return null;

  const switcher = document.querySelector("#scene-styles");
  const available = new Set(sceneStyleNames());
  const stored = storedStyle();
  const initial = available.has(stored)
    ? stored
    : available.has(DEFAULT_STYLE)
      ? DEFAULT_STYLE
      : [...available][0];

  let scene;
  try {
    scene = createAsciiScene(container, { style: initial, rows: 96 });
  } catch (error) {
    // Keep the static artwork and say why nothing animated.
    console.error("ASCII scene failed to start:", error);
    return null;
  }

  container.classList.add("home-art-live");

  const buttons = [...(switcher?.querySelectorAll("button[data-style]") ?? [])];
  const syncButtons = (active) => {
    for (const button of buttons) {
      const on = button.dataset.style === active;
      button.setAttribute("aria-pressed", String(on));
    }
  };

  for (const button of buttons) {
    const name = button.dataset.style;
    if (!available.has(name)) {
      button.hidden = true;
      continue;
    }
    button.addEventListener("click", () => {
      if (!available.has(name)) return;
      scene.setStyle(name);
      rememberStyle(name);
      syncButtons(name);
    });
  }
  syncButtons(scene.style);

  return scene;
}
