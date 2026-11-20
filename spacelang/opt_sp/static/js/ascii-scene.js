/**
 * Animated ASCII scenes for the OPT_SP pages.
 *
 * The artwork these come from was a full-window page: it built a software 3D
 * point cloud, projected it and rasterised it into monospace text with a
 * per-character ramp. This module turns that idea into a component:
 *
 *   - the canvas fills its container instead of the window;
 *   - a ResizeObserver replaces the window resize handler, so the scene follows
 *     layout changes (column widths, panels closing) without polling;
 *   - the render loop stops while the tab is hidden or the canvas is scrolled
 *     out of view, and resumes where it left off;
 *   - destroy() releases observers, listeners and the canvas.
 *
 * A style is a factory returning `{ resize(view), frame(dt, time, view) }` plus
 * optional `onDrag`, `onZoom`, `setOption` and `destroy` hooks. Styles register
 * themselves at import time so the home page only has to name one:
 *
 *   import "./scene-christmas-tree.js";
 *   const scene = createAsciiScene(container, { style: "christmas-tree" });
 *
 * `view` is the raster grid: canvas metrics plus per-cell depth and colour
 * buffers that the style fills and then flushes with `view.drawText(glyphs)`.
 */

export const FONT_FAMILY =
  '"Cascadia Mono","SF Mono",ui-monospace,Menlo,Consolas,"Liberation Mono",monospace';
const DEFAULT_ROWS = 96;
const MAX_DEPTH = 1e9;

const styles = new Map();
const FILL_CACHE = new Array(4096);
const REPEAT_CACHE = new Map();

export function registerSceneStyle(name, factory) {
  if (typeof name !== "string" || name === "") {
    throw new TypeError("a scene style needs a name");
  }
  if (typeof factory !== "function") {
    throw new TypeError(`scene style "${name}" needs a factory function`);
  }
  styles.set(name, factory);
}

export function sceneStyleNames() {
  return [...styles.keys()];
}

function fillStyleFor(key) {
  let style = FILL_CACHE[key];
  if (!style) {
    style = `rgb(${(key >> 8) << 4},${((key >> 4) & 15) << 4},${(key & 15) << 4})`;
    FILL_CACHE[key] = style;
  }
  return style;
}

function repeatOf(glyph, count) {
  let cache = REPEAT_CACHE.get(glyph);
  if (!cache) {
    cache = [];
    REPEAT_CACHE.set(glyph, cache);
  }
  return cache[count] ?? (cache[count] = glyph.repeat(count));
}

/** Canvas metrics plus the per-cell raster the styles write into. */
class AsciiSurface {
  constructor(container, { rows = DEFAULT_ROWS, maxDevicePixelRatio = 1.5 } = {}) {
    this.container = container;
    this.targetRows = rows;
    this.maxDevicePixelRatio = maxDevicePixelRatio;
    this.canvas = document.createElement("canvas");
    this.canvas.className = "ascii-scene-canvas";
    this.canvas.setAttribute("aria-hidden", "true");
    this.ctx = this.canvas.getContext("2d");
    this.width = 1;
    this.height = 1;
    this.dpr = 1;
    this.font = "";
    this.cols = 1;
    this.rows = 1;
    this.cellW = 8;
    this.cellH = 10;
    this.cells = 0;
    this.depth = new Float32Array(0);
    this.cellR = new Float32Array(0);
    this.cellG = new Float32Array(0);
    this.cellB = new Float32Array(0);
    this.cellCh = new Uint8Array(0);
  }

  resize() {
    const width = Math.max(1, Math.round(this.container.clientWidth));
    const height = Math.max(1, Math.round(this.container.clientHeight));
    const dpr = Math.min(this.maxDevicePixelRatio, window.devicePixelRatio || 1);
    this.width = width;
    this.height = height;
    this.dpr = dpr;
    this.canvas.width = Math.max(1, Math.round(width * dpr));
    this.canvas.height = Math.max(1, Math.round(height * dpr));
    this.canvas.style.width = `${width}px`;
    this.canvas.style.height = `${height}px`;
    this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    // The grid density follows the container height; the font floor keeps
    // glyphs legible in short panels, which then fit fewer rows.
    let fontSize = height / this.targetRows / 1.05;
    if (fontSize < 5) fontSize = 5;
    this.font = `bold ${fontSize}px ${FONT_FAMILY}`;
    this.ctx.font = this.font;
    this.cellW = Math.max(3, this.ctx.measureText("M").width);
    this.cellH = fontSize * 1.05;
    this.cols = Math.max(2, Math.floor(width / this.cellW));
    this.rows = Math.max(2, Math.round(height / this.cellH));

    const cells = this.cols * this.rows;
    if (cells !== this.cells) {
      this.cells = cells;
      this.depth = new Float32Array(cells);
      this.cellR = new Float32Array(cells);
      this.cellG = new Float32Array(cells);
      this.cellB = new Float32Array(cells);
      this.cellCh = new Uint8Array(cells);
    }
    return this;
  }

  beginFrame() {
    this.depth.fill(MAX_DEPTH);
    this.cellCh.fill(0);
  }

  view() {
    return {
      ctx: this.ctx,
      width: this.width,
      height: this.height,
      dpr: this.dpr,
      font: this.font,
      cols: this.cols,
      rows: this.rows,
      cellW: this.cellW,
      cellH: this.cellH,
      cells: this.cells,
      depth: this.depth,
      cellR: this.cellR,
      cellG: this.cellG,
      cellB: this.cellB,
      cellCh: this.cellCh,
      drawText: (glyphs, cull) => this.drawText(glyphs, cull),
    };
  }

  /**
   * Flush the cell grid, merging horizontal runs of one glyph and one colour
   * into a single fillText call. `glyphs` is indexed by cell value, so entry 0
   * is the blank cell; `cull` may drop a cell before it is drawn.
   */
  drawText(glyphs, cull) {
    const { ctx, cols, rows, cellW, cellH, font } = this;
    const { cellCh, cellR, cellG, cellB } = this;
    ctx.font = font;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    for (let row = 0; row < rows; row++) {
      const baseline = row * cellH + cellH * 0.54;
      const base = row * cols;
      let runCh = 0;
      let runKey = -1;
      let runLen = 0;
      let runCol = 0;
      for (let col = 0; col <= cols; col++) {
        let ch = 0;
        let key = -1;
        if (col < cols) {
          const index = base + col;
          ch = cellCh[index];
          if (ch) {
            const r = cellR[index];
            const g = cellG[index];
            const b = cellB[index];
            if (cull && !cull(index, ch, r, g, b)) {
              ch = 0;
            } else {
              key = ((r >> 4) << 8) | ((g >> 4) << 4) | (b >> 4);
            }
          }
        }
        if (ch && ch === runCh && key === runKey) {
          runLen++;
          continue;
        }
        if (runCh) {
          ctx.fillStyle = fillStyleFor(runKey);
          ctx.fillText(repeatOf(glyphs[runCh], runLen), (runCol + runLen * 0.5) * cellW, baseline);
        }
        runCh = ch;
        runKey = key;
        runLen = 1;
        runCol = col;
      }
    }
  }
}

export function createAsciiScene(container, options = {}) {
  if (!(container instanceof Element)) {
    throw new TypeError("createAsciiScene needs a container element");
  }
  const {
    style: initialStyle,
    rows = DEFAULT_ROWS,
    maxDevicePixelRatio = 1.5,
    reducedMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches ?? false,
    styleOptions = {},
  } = options;

  const surface = new AsciiSurface(container, { rows, maxDevicePixelRatio });
  const canvas = surface.canvas;
  container.classList.add("ascii-scene");
  container.appendChild(canvas);

  let styleName = "";
  let style = null;
  let view = surface.view();
  let frameHandle = 0;
  let running = false;
  let destroyed = false;
  let paused = false;
  let visible = true;
  let time = 0;
  let lastStamp = 0;
  let frames = 0;

  function applyStyle(name) {
    const factory = styles.get(name);
    if (!factory) {
      throw new Error(
        `unknown scene style "${name}"; registered: ${sceneStyleNames().join(", ") || "none"}`
      );
    }
    style?.destroy?.();
    style = factory({ reducedMotion, ...styleOptions });
    styleName = name;
    style.resize?.(view);
  }

  function tick(stamp) {
    if (!running) return;
    frameHandle = requestAnimationFrame(tick);
    const delta = Math.min(0.05, Math.max(0, (stamp - lastStamp) / 1000) || 0.016);
    lastStamp = stamp;
    time += delta;
    frames += 1;
    surface.beginFrame();
    style?.frame?.(delta, time, view);
  }

  function start() {
    if (destroyed || running || paused || document.hidden || !visible) return;
    running = true;
    lastStamp = performance.now();
    frameHandle = requestAnimationFrame(tick);
  }

  function stop() {
    running = false;
    if (frameHandle) cancelAnimationFrame(frameHandle);
    frameHandle = 0;
  }

  function sync() {
    if (destroyed) return;
    if (!paused && visible && !document.hidden) start();
    else stop();
  }

  /** Redraw a still frame after layout changes while the loop is stopped. */
  function settle() {
    if (destroyed || running) return;
    surface.beginFrame();
    style?.frame?.(0, time, view);
  }

  function relayout() {
    if (destroyed) return;
    surface.resize();
    view = surface.view();
    style?.resize?.(view);
    settle();
  }

  const resizeObserver = new ResizeObserver(relayout);
  resizeObserver.observe(container);

  const intersectionObserver = new IntersectionObserver((entries) => {
    visible = entries.some((entry) => entry.isIntersecting);
    sync();
  });
  intersectionObserver.observe(canvas);

  const onVisibilityChange = () => sync();
  document.addEventListener("visibilitychange", onVisibilityChange);

  let dragging = false;
  let lastX = 0;
  let lastY = 0;

  const onPointerDown = (event) => {
    if (event.pointerType === "mouse" && event.button !== 0) return;
    dragging = true;
    lastX = event.clientX;
    lastY = event.clientY;
    canvas.setPointerCapture?.(event.pointerId);
    canvas.classList.add("is-dragging");
    style?.onDragStart?.();
  };

  const onPointerMove = (event) => {
    if (!dragging) return;
    const dx = event.clientX - lastX;
    const dy = event.clientY - lastY;
    lastX = event.clientX;
    lastY = event.clientY;
    style?.onDrag?.(dx, dy);
  };

  const onPointerUp = (event) => {
    if (!dragging) return;
    dragging = false;
    canvas.classList.remove("is-dragging");
    try {
      canvas.releasePointerCapture?.(event.pointerId);
    } catch {
      /* the pointer was already released */
    }
    style?.onDragEnd?.();
  };

  const onWheel = (event) => {
    if (!style?.onZoom) return;
    event.preventDefault();
    style.onZoom(event.deltaY);
  };

  canvas.addEventListener("pointerdown", onPointerDown);
  canvas.addEventListener("pointermove", onPointerMove);
  canvas.addEventListener("pointerup", onPointerUp);
  canvas.addEventListener("pointercancel", onPointerUp);
  canvas.addEventListener("wheel", onWheel, { passive: false });

  // Web fonts can change the measured cell box after the first frame.
  document.fonts?.ready
    ?.then(() => {
      if (!destroyed) relayout();
    })
    .catch(() => {});

  const handle = {
    canvas,
    container,
    get style() {
      return styleName;
    },
    get running() {
      return running;
    },
    get frames() {
      return frames;
    },
    setStyle(name) {
      if (destroyed) return false;
      if (name === styleName) return true;
      applyStyle(name);
      if (running) {
        surface.beginFrame();
        style?.frame?.(0, time, view);
      }
      return true;
    },
    setOption(name, value) {
      style?.setOption?.(name, value);
    },
    pause() {
      paused = true;
      sync();
    },
    resume() {
      paused = false;
      sync();
    },
    destroy() {
      if (destroyed) return;
      destroyed = true;
      stop();
      resizeObserver.disconnect();
      intersectionObserver.disconnect();
      document.removeEventListener("visibilitychange", onVisibilityChange);
      canvas.removeEventListener("pointerdown", onPointerDown);
      canvas.removeEventListener("pointermove", onPointerMove);
      canvas.removeEventListener("pointerup", onPointerUp);
      canvas.removeEventListener("pointercancel", onPointerUp);
      canvas.removeEventListener("wheel", onWheel);
      style?.destroy?.();
      style = null;
      canvas.remove();
      container.classList.remove("ascii-scene");
    },
  };

  surface.resize();
  view = surface.view();
  applyStyle(initialStyle ?? sceneStyleNames()[0]);
  sync();
  return handle;
}
