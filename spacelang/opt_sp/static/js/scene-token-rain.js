/**
 * `token-rain`: the cheap second style, and the proof that the scene factory is
 * not tied to the tree's 3D pipeline.
 *
 * Columns of SpaceLang tokens fall, land, and stack into a skyline of
 * instructions; a column collapses once its pile gets tall enough. Everything
 * is a write into the shared character grid, so the surface's run merging keeps
 * a full screen of text down to a few hundred fillText calls.
 *
 * The glyph table is built from the token alphabet, so multi-character tokens
 * and non-ASCII sprinkles ("·") both work without a second rasteriser.
 */

import { registerSceneStyle } from "./ascii-scene.js";

const TOKENS = [
  { text: "PUSH_INT", colour: [255, 214, 140] },
  { text: "PUSH_STR", colour: [255, 214, 140] },
  { text: "OP 1", colour: [124, 190, 255] },
  { text: "OP 2", colour: [124, 190, 255] },
  { text: "LOAD_GLOBAL", colour: [118, 255, 168] },
  { text: "STORE_GLOBAL", colour: [118, 255, 168] },
  { text: "CALL", colour: [255, 198, 84] },
  { text: "RET", colour: [255, 198, 84] },
  { text: "JUMP_IF", colour: [255, 126, 204] },
  { text: "HALT", colour: [255, 240, 178] },
  { text: "STACK 1", colour: [112, 240, 255] },
  { text: "0", colour: [150, 170, 210] },
  { text: "1", colour: [150, 170, 210] },
  { text: "· · ·", colour: [86, 104, 150] },
  { text: "· ·", colour: [86, 104, 150] },
  { text: "·", colour: [86, 104, 150] },
];

const random = (low, high) => low + Math.random() * (high - low);
const pick = (list) => list[(Math.random() * list.length) | 0];

function buildGlyphTable() {
  const glyphs = [" "];
  const index = new Map();
  for (const token of TOKENS) {
    for (const character of token.text) {
      if (!index.has(character)) {
        index.set(character, glyphs.length);
        glyphs.push(character);
      }
    }
  }
  return { glyphs, index };
}

function createTokenRainStyle({ reducedMotion = false, speed = 1, density = 0.55 } = {}) {
  const { glyphs, index } = buildGlyphTable();
  let rate = (reducedMotion ? 0.45 : 1) * speed;
  const densityRatio = Math.max(0.05, Math.min(1, density));

  let columns = [];
  let backdrop = null;
  let maxPile = 8;

  function makeColumn() {
    return { pile: [], falling: null, cooldown: random(0, 2.5), cap: 4 };
  }

  function spawn(column) {
    const token = pick(TOKENS);
    const cells = [...token.text].map((character) => ({
      glyph: index.get(character),
      colour: token.colour,
    }));
    column.falling = {
      cells,
      row: -cells.length - random(0, 6),
      speed: random(5.5, 11) * rate,
    };
  }

  function pushCells(column, cells, rows) {
    // Stack bottom-up; the pile can never exceed the column, so collapse early
    // instead of silently overwriting the oldest rows.
    const room = rows - column.pile.length - 1;
    const count = Math.min(cells.length, Math.max(0, room));
    for (let i = 0; i < count; i++) {
      const cell = cells[i];
      const fade = 0.62 + 0.38 * (column.pile.length / Math.max(1, maxPile));
      column.pile.push({
        glyph: cell.glyph,
        colour: [cell.colour[0] * fade, cell.colour[1] * fade, cell.colour[2] * fade],
      });
    }
  }

  function land(column, falling, rows) {
    // A column keeps its own cap, so the skyline sits at uneven heights instead
    // of every column resetting together. A token that would overflow shears the
    // pile back to a third of its height: the skyline keeps its shape, and the
    // column reads as settling rather than blinking out.
    if (column.pile.length + falling.cells.length > column.cap) {
      column.pile.length = Math.round(column.pile.length * 0.34);
      column.cooldown = random(0.8, 2.2);
      return;
    }
    pushCells(column, [...falling.cells].reverse(), rows);
    column.cooldown = random(0.25, 1.6);
  }

  /**
   * Start with a partially built skyline: empty columns make the scene look
   * broken for the first ten seconds, before anything has landed. Seeded piles
   * stay well below the cap so the first few landings do not shear them.
   */
  function seedPiles(rows) {
    for (const column of columns) {
      // Keep the skyline low: piles that reach halfway up turn the panel into a
      // wall of text, and the falling tokens stop reading as movement.
      column.cap = Math.max(4, Math.round(maxPile * random(0.16, 0.5)));
      if (Math.random() > 0.6) continue;
      const target = Math.round(column.cap * random(0.35, 0.8));
      let guard = 0;
      while (column.pile.length < target && guard++ < 24) {
        const token = pick(TOKENS);
        const cells = [...token.text].reverse().map((character) => ({
          glyph: index.get(character),
          colour: token.colour,
        }));
        pushCells(column, cells.slice(0, target - column.pile.length), rows);
      }
    }
  }

  function buildBackdrop(view) {
    const canvas = document.createElement("canvas");
    canvas.width = Math.max(1, Math.round(view.width * view.dpr));
    canvas.height = Math.max(1, Math.round(view.height * view.dpr));
    const ctx = canvas.getContext("2d");
    ctx.scale(view.dpr, view.dpr);
    const glow = ctx.createRadialGradient(
      view.width * 0.5, view.height * 1.02, 0,
      view.width * 0.5, view.height * 1.02, view.height * 0.9
    );
    glow.addColorStop(0, "#111a36");
    glow.addColorStop(0.55, "#080d1c");
    glow.addColorStop(1, "#04060e");
    ctx.fillStyle = glow;
    ctx.fillRect(0, 0, view.width, view.height);
    return canvas;
  }

  function resize(view) {
    maxPile = Math.max(4, Math.round(view.rows * 0.42));
    backdrop = buildBackdrop(view);
    if (columns.length !== view.cols) {
      columns = Array.from({ length: view.cols }, makeColumn);
      seedPiles(view.rows);
    }
  }

  function frame(dt, _time, view) {
    const { ctx, cols, rows, cellCh, cellR, cellG, cellB } = view;
    ctx.drawImage(backdrop, 0, 0, view.width, view.height);

    const active = Math.max(1, Math.round(cols * densityRatio));
    for (let c = 0; c < cols; c++) {
      const column = columns[c];
      if (!column) continue;
      if (!column.falling) {
        column.cooldown -= dt;
        if (column.cooldown <= 0 && c < active) spawn(column);
      }

      /* pile, bottom-up, with a per-row dimming so the skyline reads */
      for (let i = 0; i < column.pile.length; i++) {
        const row = rows - 1 - i;
        if (row < 0) break;
        const cellIndex = row * cols + c;
        const cell = column.pile[i];
        cellCh[cellIndex] = cell.glyph;
        cellR[cellIndex] = cell.colour[0];
        cellG[cellIndex] = cell.colour[1];
        cellB[cellIndex] = cell.colour[2];
      }

      const falling = column.falling;
      if (!falling) continue;
      falling.row += falling.speed * dt;
      const floor = rows - column.pile.length - falling.cells.length;
      if (falling.row >= floor) {
        land(column, falling, rows);
        column.falling = null;
        continue;
      }
      const baseRow = Math.round(falling.row);
      for (let i = 0; i < falling.cells.length; i++) {
        const row = baseRow + i;
        if (row < 0 || row >= rows) continue;
        const cellIndex = row * cols + c;
        const cell = falling.cells[i];
        /* the trailing edge is brightest, so movement reads at a glance */
        const head = i === falling.cells.length - 1 ? 1.25 : 0.55 + (0.5 * i) / falling.cells.length;
        cellCh[cellIndex] = cell.glyph;
        cellR[cellIndex] = Math.min(255, cell.colour[0] * head);
        cellG[cellIndex] = Math.min(255, cell.colour[1] * head);
        cellB[cellIndex] = Math.min(255, cell.colour[2] * head);
      }
    }

    view.drawText(glyphs);
  }

  return {
    resize,
    frame,
    setOption(name, value) {
      if (name === "speed") {
        // Re-derive the rate without rebuilding the columns.
        rate = Math.max(0.1, (reducedMotion ? 0.45 : 1) * value);
      }
    },
  };
}

registerSceneStyle("token-rain", createTokenRainStyle);
export { createTokenRainStyle };
