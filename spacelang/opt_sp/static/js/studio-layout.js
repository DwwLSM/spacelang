/**
 * Layout for the studio's three editor panes.
 *
 * The orientation is a user setting (stacked or side by side) and the split
 * between panes is draggable, mirroring the state-panel resizers on the right.
 * Both are persisted so the workspace survives a reload.
 */

const KEY = "opt-sp-studio-layout";
const MIN_PANE_PX = 80;
const MIN_LHS_PX = 300;
const MIN_RHS_PX = 320;
const VARS = ["--pane-a", "--pane-b", "--pane-c"];
const DEFAULTS = { orientation: "vertical", sizes: [1, 1, 1], columns: [0.58, 0.42] };

function normalise(values, fallback) {
  const source = Array.isArray(values) && values.length === fallback.length ? values : fallback;
  const clean = source.map((value) => (Number.isFinite(value) && value > 0 ? value : 1));
  const total = clean.reduce((sum, value) => sum + value, 0) || 1;
  return clean.map((value) => value / total);
}

function load() {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) {
      return {
        orientation: DEFAULTS.orientation,
        sizes: [...DEFAULTS.sizes],
        columns: [...DEFAULTS.columns],
      };
    }
    const value = JSON.parse(raw);
    return {
      orientation: value?.orientation === "horizontal" ? "horizontal" : "vertical",
      sizes: normalise(value?.sizes, DEFAULTS.sizes),
      columns: normalise(value?.columns, DEFAULTS.columns),
    };
  } catch {
    return {
      orientation: DEFAULTS.orientation,
      sizes: [...DEFAULTS.sizes],
      columns: [...DEFAULTS.columns],
    };
  }
}

export function initStudioLayout({ layout, container, toggleButton }) {
  if (!container) return null;
  const paneEls = [...container.querySelectorAll(".editor-pane")];
  const splitters = [...container.querySelectorAll(".pane-splitter")];
  const columnSplitter = layout?.querySelector(".studio-column-splitter");
  const editorsColumn = layout?.querySelector(".studio-editors");
  const traceColumn = layout?.querySelector(".trace-column");
  const state = load();

  const apply = () => {
    container.dataset.orientation = state.orientation;
    state.sizes.forEach((size, index) => {
      container.style.setProperty(VARS[index], `${size.toFixed(4)}fr`);
    });
    if (layout) {
      layout.style.setProperty("--lhs", `${state.columns[0].toFixed(4)}fr`);
      layout.style.setProperty("--rhs", `${state.columns[1].toFixed(4)}fr`);
    }
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

  columnSplitter?.addEventListener("pointerdown", (event) => {
    if (event.button !== 0) return;
    if (!editorsColumn || !traceColumn) return;
    event.preventDefault();
    const left = editorsColumn.getBoundingClientRect().width;
    const right = traceColumn.getBoundingClientRect().width;
    const pair = left + right;
    if (pair <= MIN_LHS_PX + MIN_RHS_PX) return;
    const start = event.clientX;
    columnSplitter.classList.add("active");
    columnSplitter.setPointerCapture(event.pointerId);

    const onMove = (moveEvent) => {
      const delta = moveEvent.clientX - start;
      const first = Math.min(
        Math.max(MIN_LHS_PX, left + delta),
        pair - MIN_RHS_PX,
      );
      state.columns = [first / pair, (pair - first) / pair];
      apply();
    };
    const onEnd = () => {
      columnSplitter.classList.remove("active");
      columnSplitter.removeEventListener("pointermove", onMove);
      columnSplitter.removeEventListener("pointerup", onEnd);
      columnSplitter.removeEventListener("pointercancel", onEnd);
      persist();
    };
    columnSplitter.addEventListener("pointermove", onMove);
    columnSplitter.addEventListener("pointerup", onEnd);
    columnSplitter.addEventListener("pointercancel", onEnd);
  });

  apply();
  return { state, apply };
}
