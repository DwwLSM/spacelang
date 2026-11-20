/**
 * Layout for the studio's three editor panes.
 *
 * The orientation is a user setting (stacked or side by side) and the split
 * between panes is draggable, mirroring the state-panel resizers on the right.
 * Both are persisted so the workspace survives a reload.
 */

const KEY = "opt-sp-studio-layout";
const MIN_PANE_PX = 80;
const VARS = ["--pane-a", "--pane-b", "--pane-c"];
const DEFAULTS = { orientation: "vertical", sizes: [1, 1, 1] };

function load() {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return { ...DEFAULTS, sizes: [...DEFAULTS.sizes] };
    const value = JSON.parse(raw);
    const orientation = value?.orientation === "horizontal" ? "horizontal" : "vertical";
    const sizes =
      Array.isArray(value?.sizes) && value.sizes.length === 3
        ? value.sizes.map((size) => (Number.isFinite(size) && size > 0 ? size : 1))
        : [1, 1, 1];
    const total = sizes.reduce((sum, size) => sum + size, 0) || 1;
    return { orientation, sizes: sizes.map((size) => size / total) };
  } catch {
    return { ...DEFAULTS, sizes: [...DEFAULTS.sizes] };
  }
}

export function initStudioLayout({ container, toggleButton }) {
  if (!container) return null;
  const paneEls = [...container.querySelectorAll(".editor-pane")];
  const splitters = [...container.querySelectorAll(".pane-splitter")];
  const state = load();

  const apply = () => {
    container.dataset.orientation = state.orientation;
    state.sizes.forEach((size, index) => {
      container.style.setProperty(VARS[index], `${size.toFixed(4)}fr`);
    });
    for (const splitter of splitters) {
      splitter.setAttribute(
        "aria-orientation",
        state.orientation === "vertical" ? "horizontal" : "vertical",
      );
    }
    if (toggleButton) {
      toggleButton.hidden = false;
      toggleButton.textContent = state.orientation === "vertical"
        ? "Panes: stacked"
        : "Panes: side by side";
    }
  };

  const persist = () => {
    try {
      localStorage.setItem(KEY, JSON.stringify(state));
    } catch {
      // Layout persistence is a convenience; ignore storage failures.
    }
  };

  splitters.forEach((splitter, index) => {
    splitter.addEventListener("pointerdown", (event) => {
      if (event.button !== 0) return;
      event.preventDefault();
      const horizontal = state.orientation === "horizontal";
      const sizes = paneEls.map((element) => {
        const rect = element.getBoundingClientRect();
        return horizontal ? rect.width : rect.height;
      });
      const pair = sizes[index] + sizes[index + 1];
      if (pair <= MIN_PANE_PX * 2) return;
      const start = horizontal ? event.clientX : event.clientY;
      splitter.classList.add("active");
      splitter.setPointerCapture(event.pointerId);

      const onMove = (moveEvent) => {
        const delta = (horizontal ? moveEvent.clientX : moveEvent.clientY) - start;
        const first = Math.min(
          Math.max(MIN_PANE_PX, sizes[index] + delta),
          pair - MIN_PANE_PX,
        );
        const next = [...sizes];
        next[index] = first;
        next[index + 1] = pair - first;
        const total = next.reduce((sum, value) => sum + value, 0) || 1;
        state.sizes = next.map((value) => value / total);
        apply();
      };
      const onEnd = () => {
        splitter.classList.remove("active");
        splitter.removeEventListener("pointermove", onMove);
        splitter.removeEventListener("pointerup", onEnd);
        splitter.removeEventListener("pointercancel", onEnd);
        persist();
      };
      splitter.addEventListener("pointermove", onMove);
      splitter.addEventListener("pointerup", onEnd);
      splitter.addEventListener("pointercancel", onEnd);
    });
  });

  toggleButton?.addEventListener("click", () => {
    state.orientation = state.orientation === "vertical" ? "horizontal" : "vertical";
    apply();
    persist();
  });

  apply();
  return { state, apply };
}
