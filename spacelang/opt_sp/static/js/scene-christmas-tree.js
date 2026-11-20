/**
 * `christmas-tree`: the software 3D point cloud, as an embedded scene style.
 *
 * Ported from `design/ascii-christmas-tree.html`. The geometry, shading, camera
 * and snow are unchanged; what changed is the frame around it: it renders into a
 * container-sized surface instead of a full window, the ASCII raster and glow
 * buffers follow the surface grid, and the standalone page's HUD is gone (the
 * host page decides which options to expose).
 *
 * Per frame the style projects every point, resolves depth per character cell,
 * shades it (Lambert, ray-marched soft shadows, twinkling bulb light), and then
 * lets the surface merge horizontal runs into fillText calls.
 */

import { FONT_FAMILY, registerSceneStyle } from "./ascii-scene.js";

const TAU = Math.PI * 2;
const APEX = 34;
const BASEY = -26;
const RAD = 22.5;
const GROUND = -31.6;
const PERSP = 100;
const K_BRANCH = 0;
const K_TRUNK = 1;
const K_ORN = 2;
const K_BULB = 3;
const K_STAR = 4;
const K_PRES = 5;
const K_GROUND = 6;
const K_SNOW = 7;
const K_GAR = 8;
const K_CANE = 9;
const RAMP = " .':;~=+*xz%#@$&";
const GLYPHS = RAMP.split("").concat(["o", "O", "0"]);
const FOGR = 10;
const FOGG = 13;
const FOGB = 30;

const clamp = (value, low, high) => (value < low ? low : value > high ? high : value);

function mulberry32(seed) {
  return function random() {
    seed |= 0;
    seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const PAL = [
  [255, 214, 140], [255, 92, 102], [255, 198, 84], [118, 255, 168],
  [124, 190, 255], [255, 126, 204], [112, 240, 255], [255, 240, 178],
];
const ORN = [
  [226, 60, 72], [240, 186, 70], [92, 150, 238],
  [235, 240, 250], [178, 104, 224], [70, 215, 150],
];

function coneR(y) {
  const u = clamp((APEX - y) / (APEX - BASEY), 0, 1);
  return Math.max(0.5, RAD * Math.pow(u, 1.3) + 0.6);
}

/** Build the model-space point cloud once; the style keeps it for every frame. */
function buildScene() {
  const rnd = mulberry32(1337);
  const PX = [], PY = [], PZ = [], NX = [], NY = [], NZ = [], CR = [], CG = [], CB = [];
  const KIND = [], CHO = [], CHJ = [], PH = [], SP = [], UU = [], CI = [], BIDX = [], LAM = [];

  function add(x, y, z, xn, yn, zn, r, g, b, kind, extra) {
    const o = extra || {};
    const invLength = 1 / Math.hypot(xn, yn, zn);
    PX.push(x); PY.push(y); PZ.push(z);
    NX.push(xn * invLength); NY.push(yn * invLength); NZ.push(zn * invLength);
    CR.push(r); CG.push(g); CB.push(b);
    KIND.push(kind);
    CHO.push(o.ch || 0);
    CHJ.push(o.chj === undefined ? (rnd() * 4 - 2) | 0 : o.chj);
    PH.push(o.ph || 0);
    SP.push(o.sp || 0);
    UU.push(o.u || 0);
    CI.push(o.ci || 0);
    BIDX.push(o.bi === undefined ? -1 : o.bi);
    LAM.push(0);
  }

  /* branch tiers */
  const TIERS = 9;
  function needle(x, y, z) {
    const nr = Math.hypot(x, z) + 1e-4;
    const jx = rnd() - 0.5, jy = rnd() - 0.5, jz = rnd() - 0.5;
    const nx = (x / nr) * 0.82 + jx, ny = 0.42 + jy, nz = (z / nr) * 0.82 + jz;
    const gv = rnd();
    let r = 26 + gv * 30, g = 104 + gv * 52, b = 52 + gv * 34;
    if (ny > 0.62 && rnd() < 0.38) {
      r = 150 + gv * 50; g = 178 + gv * 44; b = 214;
    }
    add(x, y, z, nx, ny, nz, r, g, b, K_BRANCH);
  }
  for (let i = 0; i < TIERS; i++) {
    const u = 0.08 + (0.86 * i) / (TIERS - 1);
    const y = APEX - u * (APEX - BASEY - 8);
    const r0 = coneR(y);
    const branches = Math.round(5 + 11 * u);
    for (let b = 0; b < branches; b++) {
      const angle = ((b + i * 0.37) / branches) * TAU + rnd() * 0.22;
      const length = r0 * (0.9 + rnd() * 0.22);
      const steps = 6 + Math.round(4 * u);
      const droop = 2.2 + 3.6 * u;
      const ca = Math.cos(angle), sa = Math.sin(angle);
      for (let s = 0; s <= steps; s++) {
        const tt = s / steps;
        const bx = ca * length * tt, bz = sa * length * tt;
        const by = y - tt * tt * droop - s * 0.1;
        needle(bx, by, bz);
        const needles = s === 0 ? 1 : 3 + Math.round(2 * u);
        for (let f = 0; f < needles; f++) {
          needle(
            bx + (rnd() - 0.5) * 1.55,
            by + (rnd() - 0.5) * 1.15 + 0.3,
            bz + (rnd() - 0.5) * 1.55
          );
        }
      }
    }
  }
  /* inner body filler */
  for (let i = 0; i < 2000; i++) {
    const u = 0.05 + Math.pow(rnd(), 0.85) * 0.9;
    const y = APEX - u * (APEX - BASEY - 8);
    const radius = coneR(y) * (0.25 + 0.62 * rnd());
    const angle = rnd() * TAU;
    const gv = rnd();
    add(
      Math.cos(angle) * radius,
      y + (-1 + 2 * rnd()),
      Math.sin(angle) * radius,
      Math.cos(angle), 0.25, Math.sin(angle),
      24 + gv * 26, 80 + gv * 40, 42 + gv * 26, K_BRANCH
    );
  }
  /* trunk */
  for (let i = 0; i < 150; i++) {
    const y = GROUND + 1 + rnd() * 9.5;
    const angle = rnd() * TAU;
    const radius = 2.3 * (0.9 + rnd() * 0.1);
    add(
      Math.cos(angle) * radius, y, Math.sin(angle) * radius,
      Math.cos(angle), 0.06, Math.sin(angle), 88, 56, 33, K_TRUNK
    );
  }
  /* garlands */
  for (let s = 0; s < 3; s++) {
    const turns = 4.6 + s * 0.5;
    const n = 230;
    for (let j = 0; j <= n; j++) {
      const tt = j / n;
      const y = APEX - 4 - tt * (APEX - 4 - (BASEY + 4));
      const radius = coneR(y) + 1.15 + Math.sin(tt * 40 + s) * 0.28;
      const angle = tt * turns * TAU + s * 2.094 + Math.sin(tt * 20) * 0.12;
      const v = 0.7 + 0.3 * rnd();
      add(
        Math.cos(angle) * radius, y + Math.sin(tt * 57) * 0.5, Math.sin(angle) * radius,
        Math.cos(angle), 0.1, Math.sin(angle), 255 * v, 196 * v, 110 * v, K_GAR
      );
    }
  }
  /* ornaments */
  for (let i = 0; i < 36; i++) {
    const u = 0.14 + 0.8 * rnd();
    const y = APEX - u * (APEX - BASEY - 8);
    const radius = coneR(y) + 0.8;
    const angle = rnd() * TAU;
    const cx = Math.cos(angle) * radius, cy = y + 0.4, cz = Math.sin(angle) * radius;
    const rad = 1.5 + rnd() * 0.9;
    const colour = ORN[(rnd() * ORN.length) | 0];
    for (let f = 0; f < 30; f++) {
      const z2 = 1 - (2 * (f + 0.5)) / 26;
      const rr2 = Math.sqrt(1 - z2 * z2);
      const a2 = f * 2.39996;
      add(
        cx + Math.cos(a2) * rr2 * rad, cy + z2 * rad, cz + Math.sin(a2) * rr2 * rad,
        Math.cos(a2) * rr2, z2, Math.sin(a2) * rr2, colour[0], colour[1], colour[2], K_ORN
      );
    }
  }
  /* twinkling bulbs */
  const bulbs = [];
  for (let i = 0; i < 96; i++) {
    const u = 0.06 + 0.86 * rnd();
    const y = APEX - u * (APEX - BASEY - 8);
    const radius = coneR(y) + 1.3;
    const angle = rnd() * TAU;
    const ci = rnd() < 0.3 ? 0 : 1 + ((rnd() * 6) | 0);
    const steady = rnd() < 0.12;
    bulbs.push({
      x: Math.cos(angle) * radius,
      y: y + 0.3,
      z: Math.sin(angle) * radius,
      ci,
      u,
      ph: rnd() * TAU,
      sp: steady ? 0.4 : 1.5 + rnd() * 2.5,
    });
    add(
      bulbs[i].x, bulbs[i].y, bulbs[i].z,
      Math.cos(angle), 0.3, Math.sin(angle),
      PAL[ci][0], PAL[ci][1], PAL[ci][2], K_BULB, { ci, bi: i }
    );
    add(
      bulbs[i].x + (rnd() - 0.5) * 0.5,
      bulbs[i].y + (rnd() - 0.5) * 0.5,
      bulbs[i].z + (rnd() - 0.5) * 0.5,
      Math.cos(angle), 0.3, Math.sin(angle),
      PAL[ci][0], PAL[ci][1], PAL[ci][2], K_BULB, { ci, bi: i }
    );
  }
  /* star: five points, extruded, outline-traced so the shape reads in ascii */
  {
    const scx = 0, scy = APEX + 3.4, scz = 0, RO = 7.5, RI = 3.2, TH = 1.4;
    const poly = [];
    for (let i = 0; i < 10; i++) {
      const angle = Math.PI / 2 + (i * TAU) / 10;
      const radius = i % 2 ? RI : RO;
      poly.push([Math.cos(angle) * radius, Math.sin(angle) * radius]);
    }
    for (let i = 0; i < 10; i++) {
      const A = poly[i], B = poly[(i + 1) % 10];
      const length = Math.hypot(B[0] - A[0], B[1] - A[1]);
      const n = Math.max(2, Math.round(length * 2.6));
      for (let j = 0; j <= n; j++) {
        const tt = j / n;
        const x = A[0] + (B[0] - A[0]) * tt;
        const y = A[1] + (B[1] - A[1]) * tt;
        const z = (rnd() - 0.5) * TH;
        const inv = 1 / Math.hypot(x, y, z);
        add(scx + x, scy + y, scz + z, x * inv, y * inv, z * inv, 255, 236, 168, K_STAR, { chj: 0 });
      }
    }
    let placed = 0, guard = 0;
    while (placed < 42 && guard++ < 2000) {
      const x = (rnd() * 2 - 1) * RO, y = (rnd() * 2 - 1) * RO;
      let inside = false;
      for (let i = 0, j = 9; i < 10; j = i++) {
        if (
          (poly[i][1] > y) !== (poly[j][1] > y) &&
          x < ((poly[j][0] - poly[i][0]) * (y - poly[i][1])) / (poly[j][1] - poly[i][1]) + poly[i][0]
        ) {
          inside = !inside;
        }
      }
      if (!inside) continue;
      placed++;
      const z = (rnd() - 0.5) * TH;
      const inv = 1 / Math.hypot(x, y, z);
      add(scx + x, scy + y, scz + z, x * inv, y * inv, z * inv, 196, 172, 116, K_STAR, { chj: 0 });
    }
  }
  /* presents */
  const RIBG = [250, 200, 100];
  const RIBI = [210, 235, 255];
  function present(cx, cz, w, h, d, yaw, face, ribbon, y0) {
    const base = y0 === undefined ? GROUND : y0;
    const ca = Math.cos(yaw), sa = Math.sin(yaw);
    const hw = w / 2, hd = d / 2, y1 = base + h;
    const rot = (x, z) => [cx + x * ca - z * sa, cz + x * sa + z * ca];
    const rotN = (x, z) => [x * ca - z * sa, x * sa + z * ca];
    function put(x, y, z, xn, yn, zn, r, g, b, alpha) {
      const p = rot(x, z);
      const n = rotN(xn, zn);
      add(p[0], y, p[1], n[0], yn, n[1], r * alpha, g * alpha, b * alpha, K_PRES);
    }
    const step = 1;
    const snowTop = rnd() < 0.4;
    for (let s = 0; s < 2; s++) {
      const zf = s ? -hd : hd;
      const nz = s ? -1 : 1;
      for (let xx = -hw; xx <= hw; xx += step)
        for (let yy = base; yy <= y1; yy += step)
          put(xx, yy, zf, 0, 0, nz, face[0], face[1], face[2], 0.85 + (0.15 * (yy - base)) / h);
    }
    for (let s = 0; s < 2; s++) {
      const xf = s ? -hw : hw;
      const nx = s ? -1 : 1;
      for (let zz = -hd; zz <= hd; zz += step)
        for (let yy = base; yy <= y1; yy += step)
          put(xf, yy, zz, nx, 0, 0, face[0], face[1], face[2], 0.85 + (0.15 * (yy - base)) / h);
    }
    for (let xx = -hw; xx <= hw; xx += step) {
      for (let zz = -hd; zz <= hd; zz += step) {
        const p = rot(xx, zz);
        const snowy = snowTop && rnd() < 0.5;
        const colour = snowy ? [225, 233, 252] : face;
        add(p[0], y1 + 0.02, p[1], 0, 1, 0, colour[0], colour[1], colour[2], K_PRES);
      }
    }
    const rc = ribbon ? RIBG : RIBI;
    const rw = 0.62;
    for (let zz = -hd; zz <= hd; zz += step * 0.8)
      for (let xx = -rw; xx <= rw; xx += step * 0.8)
        put(xx, y1 + 0.1, zz, 0, 1, 0, rc[0], rc[1], rc[2], 1);
    for (let xx = -hw; xx <= hw; xx += step * 0.8) {
      for (let zz = -rw; zz <= rw; zz += step * 0.8) {
        const p = rot(xx, zz);
        add(p[0], y1 + 0.08, p[1], 0, 1, 0, rc[0], rc[1], rc[2], K_PRES);
      }
    }
    for (let yy = base; yy <= y1; yy += step * 0.9) {
      for (let s = 0; s < 2; s++) {
        const zf = s ? -hd : hd;
        put(0, yy, zf, 0, 0, 1, rc[0], rc[1], rc[2], 0.9);
        const xf = s ? -hw : hw;
        put(xf, yy, 0, 1, 0, 0, rc[0], rc[1], rc[2], 0.9);
      }
    }
    for (let e = 0; e < 2; e++) {
      for (let j = 0; j < 14; j++) {
        const a = (j / 14) * TAU;
        const lx = Math.cos(a) * 1.9, ly = Math.sin(a) * 1.15;
        const bx = e ? lx : 0, bz = e ? 0 : lx, by = ly * 0.9 + 0.4;
        const p = rot(bx, bz);
        add(
          p[0], y1 + 0.45 + by, p[1], 0, 1, 0,
          Math.min(255, rc[0] * 1.25), Math.min(255, rc[1] * 1.25), Math.min(255, rc[2] * 1.25),
          K_PRES
        );
      }
    }
    for (let j = 0; j < 4; j++) {
      const p = rot((rnd() - 0.5) * 0.7, (rnd() - 0.5) * 0.7);
      add(p[0], y1 + 0.5, p[1], 0, 1, 0, rc[0], rc[1], rc[2], K_PRES);
    }
  }
  const PDEF = [
    [15, 20, 8.5, 6, 7, 0.5, 0, 1], [-60, 22, 7, 5, 7, 0.9, 1, 0],
    [105, 21, 9, 7, 8, 0.2, 3, 1], [150, 22, 6.5, 5, 6.5, 0.7, 5, 1],
    [195, 20, 8, 6.5, 7, 0.15, 2, 0], [240, 23, 10, 7.5, 9, 1.05, 0, 0],
    [285, 21, 6, 4.5, 6, 0.4, 4, 1], [325, 22, 7.5, 6, 7.5, 0.8, 5, 1],
  ];
  const pTops = [];
  for (const pd of PDEF) {
    const angle = (pd[0] * Math.PI) / 180;
    const dist = pd[1];
    present(
      Math.cos(angle) * dist, Math.sin(angle) * dist,
      pd[2], pd[3], pd[4], pd[5], ORN[pd[6]], pd[7]
    );
    pTops.push([Math.cos(angle) * dist, Math.sin(angle) * dist, pd[3]]);
  }
  present(pTops[0][0] + 1.2, pTops[0][1] - 0.8, 4.2, 3.2, 4.2, 0.3, ORN[2], 0, GROUND + pTops[0][2]);
  present(pTops[2][0] - 1.0, pTops[2][1] + 1.1, 4.6, 3.6, 4.6, 0.9, ORN[4], 1, GROUND + pTops[2][2]);

  /* candy canes */
  function cane(bx, bz, dirX, dirZ) {
    const n = Math.hypot(dirX, dirZ);
    dirX /= n; dirZ /= n;
    for (let j = 0; j <= 26; j++) {
      let x, y, z, arc;
      const tt = j / 26;
      if (tt < 0.62) {
        const h = (tt / 0.62) * 5;
        y = h; x = bx; z = bz; arc = h;
      } else {
        const a = ((tt - 0.62) / 0.38) * Math.PI;
        const cx2 = bx + dirX * 1.9, cz2 = bz + dirZ * 1.9;
        x = cx2 - dirX * 1.9 * Math.cos(a);
        z = cz2 - dirZ * 1.9 * Math.cos(a);
        y = 5 + 1.9 * Math.sin(a);
        arc = 5 + 1.9 * a;
      }
      const red = arc % 1.6 < 0.8;
      const colour = red ? [235, 62, 74] : [238, 242, 252];
      const nr = Math.hypot(x - (bx + dirX * Math.max(0, arc - 5) * 0.5),
                            z - (bz + dirZ * Math.max(0, arc - 5) * 0.5)) + 1e-4;
      add(
        x + (rnd() - 0.5) * 0.55, y + (rnd() - 0.5) * 0.55, z + (rnd() - 0.5) * 0.55,
        (x - bx) / nr, 0.2, (z - bz) / nr, colour[0], colour[1], colour[2], K_CANE
      );
    }
  }
  cane(Math.cos((15 * Math.PI) / 180) * 20 + 3.2, Math.sin((15 * Math.PI) / 180) * 20 + 1.4, 1, -0.3);
  cane(Math.cos((240 * Math.PI) / 180) * 23 - 2.6, Math.sin((240 * Math.PI) / 180) * 23 + 2.2, -0.8, 0.6);

  /* snowy ground */
  for (let i = 0; i < 1900; i++) {
    const rr = 58 * Math.pow(rnd(), 0.72);
    const angle = rnd() * TAU;
    const x = Math.cos(angle) * rr, z = Math.sin(angle) * rr;
    const y = GROUND + (rnd() - 0.5) * 0.8 + Math.sin(x * 0.35) * Math.cos(z * 0.3) * 0.5;
    const spark = rnd() < 0.09;
    const v = 0.62 + 0.2 * rnd();
    const fade = clamp(1.18 - rr / 52, 0, 1);
    const colour = spark
      ? [190 * fade, 204 * fade, 236 * fade]
      : [132 * v * fade, 146 * v * fade, 180 * v * fade];
    add(x, y, z, 0, 1, 0, colour[0], colour[1], colour[2], K_GROUND, { ph: spark ? rnd() : 0, ci: 0 });
  }

  /* falling snow particles */
  const snowIdx = [];
  for (let i = 0; i < 360; i++) {
    snowIdx.push(PX.length);
    const ci = rnd() < 0.7 ? 1 : rnd() < 0.5 ? 4 : 8;
    add(
      (rnd() * 2 - 1) * 48, -30 + rnd() * 74, (rnd() * 2 - 1) * 48,
      0, 1, 0, 140, 150, 178, K_SNOW, { ch: ci, ph: rnd() * TAU }
    );
  }

  const N = PX.length;
  const kind = Uint8Array.from(KIND);
  const lam0 = Float32Array.from(LAM);
  const lights = [];
  for (const bulb of bulbs) {
    lights.push({
      x: bulb.x, y: bulb.y, z: bulb.z,
      r: PAL[bulb.ci][0] / 255, g: PAL[bulb.ci][1] / 255, b: PAL[bulb.ci][2] / 255,
      rad: 13, gain: 0.38,
    });
  }
  lights.push({ x: 0, y: APEX + 2.6, z: 0, r: 1, g: 0.93, b: 0.66, rad: 16, gain: 0.6 });

  /* key light, normalised once */
  const Lw = { x: -0.45, y: 0.75, z: 0.5 };
  {
    const inv = 1 / Math.hypot(Lw.x, Lw.y, Lw.z);
    Lw.x *= inv; Lw.y *= inv; Lw.z *= inv;
  }
  for (let i = 0; i < N; i++) {
    const k = kind[i];
    if (k === K_PRES || k === K_GROUND || k === K_CANE) {
      let d = NX[i] * Lw.x + NY[i] * Lw.y + NZ[i] * Lw.z;
      if (d < 0) d = 0;
      lam0[i] = d;
    }
  }

  /* warm light pool under the tree, cached per ground point */
  const poolR = new Float32Array(N), poolG = new Float32Array(N), poolB = new Float32Array(N);
  for (let i = 0; i < N; i++) {
    if (kind[i] === K_GROUND) {
      const d = Math.hypot(PX[i], PZ[i]);
      const w = Math.exp(-(d * d) / (15 * 15));
      poolR[i] = 255 * w * 0.42;
      poolG[i] = 150 * w * 0.32;
      poolB[i] = 60 * w * 0.22;
    }
  }

  /* cached bulb glow per tree point, plus its dominant light */
  const gr = new Float32Array(N), gg = new Float32Array(N), gb = new Float32Array(N);
  const dom = new Int16Array(N);
  const LN = lights.length;
  for (let i = 0; i < N; i++) {
    const k = kind[i];
    if (k === K_PRES || k === K_GROUND || k === K_CANE || k === K_SNOW || k === K_BULB) {
      dom[i] = -1;
      continue;
    }
    let sr = 0, sg = 0, sb = 0, best = 0, bestIndex = -1;
    const ox = PX[i], oy = PY[i], oz = PZ[i];
    for (let l = 0; l < LN; l++) {
      const light = lights[l];
      const dx = light.x - ox, dy = light.y - oy, dz = light.z - oz;
      const d2 = dx * dx + dy * dy + dz * dz;
      if (d2 > light.rad * light.rad) continue;
      const d = Math.sqrt(d2);
      const w = 1 - d / light.rad;
      const w2 = w * w;
      const dl = d > 1e-4 ? 1 / d : 0;
      let f = (NX[i] * dx + NY[i] * dy + NZ[i] * dz) * dl * 0.55 + 0.45;
      if (f < 0) f = 0;
      const q = w2 * f * light.gain;
      sr += light.r * q * 255;
      sg += light.g * q * 255;
      sb += light.b * q * 255;
      if (w2 > best) {
        best = w2;
        bestIndex = l;
      }
    }
    gr[i] = sr; gg[i] = sg; gb[i] = sb;
    dom[i] = bestIndex;
  }

  return {
    N,
    px: Float32Array.from(PX), py: Float32Array.from(PY), pz: Float32Array.from(PZ),
    nx: Float32Array.from(NX), ny: Float32Array.from(NY), nz: Float32Array.from(NZ),
    cr: Float32Array.from(CR), cg: Float32Array.from(CG), cb: Float32Array.from(CB),
    kind, cho: Uint8Array.from(CHO), chj: Float32Array.from(CHJ),
    ph: Float32Array.from(PH), sp: Float32Array.from(SP),
    ci: Uint8Array.from(CI), bidx: Int16Array.from(BIDX),
    lam0, poolR, poolG, poolB, gr, gg, gb, dom,
    bulbs, lights, Lw, snowIdx, LN,
  };
}

/** Glow sprites, one per palette entry, drawn once into offscreen canvases. */
function buildSprites() {
  return PAL.map((colour) => {
    const canvas = document.createElement("canvas");
    canvas.width = canvas.height = 128;
    const ctx = canvas.getContext("2d");
    const gradient = ctx.createRadialGradient(64, 64, 2, 64, 64, 62);
    gradient.addColorStop(0, "rgba(255,255,255,.95)");
    gradient.addColorStop(0.22, `rgba(${colour[0]},${colour[1]},${colour[2]},.62)`);
    gradient.addColorStop(0.55, `rgba(${colour[0]},${colour[1]},${colour[2]},.18)`);
    gradient.addColorStop(1, "rgba(0,0,0,0)");
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, 128, 128);
    return canvas;
  });
}

function createChristmasTreeStyle({ reducedMotion = false, ...initialOptions } = {}) {
  const data = buildScene();
  const sprites = buildSprites();
  const options = {
    spin: true,
    lights: true,
    snow: true,
    glow: true,
    shadows: true,
    ...initialOptions,
  };

  let yaw = 0.6;
  let pitch = 0.17;
  let pitchTarget = 0.17;
  let camDist = 118;
  let camDistTarget = 118;
  let yawVelocity = 0;
  let backdrop = null;
  let litB = new Float32Array(0);
  let sprB = new Uint8Array(0);
  let unit = 10;
  let glowScale = 1;
  let sprFrame = true;
  let star = { seen: false, x: 0, y: 0 };
  let shooting = { countdown: 4, remaining: 0, x0: 0, y0: 0, dx: 0, dy: 0 };
  const rotSpeed = reducedMotion ? 0.12 : 0.3;
  const jitter = Math.cos(0.07);
  const jitterSin = Math.sin(0.07);

  /* world-space bulb light positions and twinkle brightness */
  const LWX = new Float32Array(data.LN);
  const LWY = new Float32Array(data.LN);
  const LWZ = new Float32Array(data.LN);
  const TW = new Float32Array(data.LN);

  function buildBackdrop(view) {
    const canvas = document.createElement("canvas");
    canvas.width = Math.max(1, Math.round(view.width * view.dpr));
    canvas.height = Math.max(1, Math.round(view.height * view.dpr));
    const ctx = canvas.getContext("2d");
    ctx.scale(view.dpr, view.dpr);
    const sky = ctx.createRadialGradient(
      view.width * 0.5, view.height * 0.18, 0,
      view.width * 0.5, view.height * 0.18, view.height * 1.15
    );
    sky.addColorStop(0, "#101a3c");
    sky.addColorStop(0.42, "#0a1128");
    sky.addColorStop(0.78, "#05070f");
    sky.addColorStop(1, "#020309");
    ctx.fillStyle = sky;
    ctx.fillRect(0, 0, view.width, view.height);
    const horizon = ctx.createRadialGradient(
      view.width * 0.5, view.height * 0.74, 0,
      view.width * 0.5, view.height * 0.74, view.width * 0.55
    );
    horizon.addColorStop(0, "rgba(70,105,205,.17)");
    horizon.addColorStop(0.7, "rgba(70,105,205,0)");
    ctx.fillStyle = horizon;
    ctx.fillRect(0, 0, view.width, view.height);
    const rnd = mulberry32(99);
    const glyphs = [".", "'", '"', "+", "*"];
    for (let i = 0; i < 150; i++) {
      const x = rnd() * view.width;
      const y = rnd() * view.height * 0.78;
      const alpha = 0.12 + rnd() * 0.45;
      ctx.font = `bold ${6 + rnd() * 7}px ${FONT_FAMILY}`;
      ctx.fillStyle = `rgba(${(170 + rnd() * 60) | 0},${(185 + rnd() * 55) | 0},255,${alpha})`;
      ctx.fillText(glyphs[(rnd() * 5) | 0], x, y);
    }
    return canvas;
  }

  /** Ray-marched tree silhouette shadow in model space. */
  function march(ox, oy, oz, dx, dy, dz, tmin) {
    if (oy > APEX + 1.5) return 1;
    if (dy <= 0.05) return 1;
    const maxT = Math.min(80, (APEX + 2 - oy) / dy);
    for (let tt = tmin; tt < maxT; tt += 6) {
      const qx = ox + dx * tt, qy = oy + dy * tt, qz = oz + dz * tt;
      if (qy < BASEY) continue;
      const rr = qx * qx + qz * qz;
      if (rr > 1600) return 1;
      const cone = coneR(qy);
      const cone2 = cone * cone;
      if (rr < cone2 * 0.64) return 0;
      if (rr > cone2 * 1.44) continue;
      const angle = Math.atan2(qz, qx);
      const rs = cone * (1 + 0.15 * Math.sin(3 * angle + qy * 0.22));
      if (rr < rs * rs) return 0;
    }
    return 1;
  }

  function resize(view) {
    // Fit by height, but never wider than the tree's own footprint: the original
    // page filled a whole window, while this surface is usually a narrow column.
    // 0.0245 is the width that puts the cone's 2 * RAD base at the edge.
    unit = Math.min(view.rows * view.cellH * 0.01397, view.width * 0.0245);
    glowScale = clamp(view.height / 820, 0.65, 1.25);
    backdrop = buildBackdrop(view);
    if (litB.length !== view.cells) {
      litB = new Float32Array(view.cells);
      sprB = new Uint8Array(view.cells);
    }
  }

  function frame(dt, time, view) {
    const { ctx, cols, rows, cellW, cellH, depth, cellR, cellG, cellB, cellCh } = view;
    const t = time;
    const { N, px, py, pz, nx, ny, nz, cr, cg, cb, kind, cho, chj, ph, bidx } = data;
    const { bulbs, lights, Lw, snowIdx, LN } = data;
    const { lam0, poolR, poolG, poolB, gr, gg, gb, dom } = data;

    if (options.spin) yaw += rotSpeed * dt;
    yaw += yawVelocity * dt;
    yawVelocity *= Math.exp(-3.2 * dt);
    pitch += (pitchTarget - pitch) * Math.min(1, dt * 7);
    camDist += (camDistTarget - camDist) * Math.min(1, dt * 6);

    const sway = pitch + Math.sin(t * 0.21) * 0.012;
    const pC = Math.cos(sway);
    const pS = Math.sin(sway);
    const cY = Math.cos(yaw);
    const sY = Math.sin(yaw);

    /* model-space key light and its two jittered copies (soft shadows) */
    const Lmx = Lw.x * cY + Lw.z * sY;
    const Lmy = Lw.y;
    const Lmz = -Lw.x * sY + Lw.z * cY;
    const L1x = Lmx * jitter - Lmz * jitterSin;
    const L1z = Lmx * jitterSin + Lmz * jitter;
    const L2x = Lmx * jitter + Lmz * jitterSin;
    const L2z = -Lmx * jitterSin + Lmz * jitter;

    for (let i = 0; i < LN; i++) {
      const light = lights[i];
      LWX[i] = light.x * cY + light.z * sY;
      LWY[i] = light.y;
      LWZ[i] = -light.x * sY + light.z * cY;
      if (!options.lights) {
        TW[i] = 0.08;
        continue;
      }
      const u = i < LN - 1 ? bulbs[i].u : 1;
      const speed = i < LN - 1 ? bulbs[i].sp : 2.3;
      const phase = i < LN - 1 ? bulbs[i].ph : 0;
      TW[i] = clamp(
        0.55 + 0.5 * Math.sin(t * speed + phase) * (0.72 + 0.4 * Math.sin(t * 1.2 - u * 6.5)),
        0.12,
        1.5
      );
    }

    if (options.snow) {
      for (let q = 0; q < snowIdx.length; q++) {
        const index = snowIdx[q];
        py[index] += -(2 + ph[index] * 2.6) * dt;
        px[index] += Math.sin(t * 0.9 + ph[index] * 7) * dt * 1.6;
        if (py[index] < GROUND - 1) {
          py[index] = 42;
          px[index] = (Math.random() * 2 - 1) * 48;
          pz[index] = (Math.random() * 2 - 1) * 48;
        }
      }
    }

    litB.fill(0);
    star.seen = false;
    const cam = camDist;
    const cxp = cols * cellW / 2;
    const cyp = rows * cellH * 0.555;

    for (let i = 0; i < N; i++) {
      const k = kind[i];
      if (k === K_SNOW && !options.snow) continue;
      const x = px[i], y = py[i], z = pz[i];
      let xw, zw;
      if (k === K_PRES || k === K_GROUND || k === K_CANE) {
        xw = x;
        zw = z;
      } else {
        xw = x * cY - z * sY;
        zw = x * sY + z * cY;
      }
      const yp = y * pC + zw * pS;
      const zp = zw * pC - y * pS;
      const dep = zp + cam;
      if (dep < 24) continue;
      const pr = (PERSP / dep) * unit;
      const sx = cxp + xw * pr;
      const sy = cyp - yp * pr;
      const col = (sx / cellW) | 0;
      const row = (sy / cellH) | 0;
      if (col < 0 || col >= cols || row < 0 || row >= rows) continue;
      const di = row * cols + col;
      if (dep >= depth[di]) continue;
      depth[di] = dep;

      let fr = 0, fg = 0, fb = 0, chi = 0, lit = 0, spr = 255;
      let fog = clamp((dep - 95) / 140, 0, 1) * 0.42;

      if (k === K_BULB) {
        const bi = bidx[i];
        const tw = TW[bi];
        fr = cr[i] * (0.3 + 1.35 * tw);
        fg = cg[i] * (0.3 + 1.35 * tw);
        fb = cb[i] * (0.3 + 1.35 * tw);
        chi = tw > 1.02 ? 18 : tw > 0.78 ? 17 : tw > 0.5 ? 16 : 7;
        lit = Math.min(1.5, 0.2 + tw * 0.8);
        spr = bulbs[bi].ci;
        fog *= 0.3;
      } else if (k === K_STAR) {
        const pulse = 0.72 + 0.38 * Math.sin(t * 2.3) + 0.12 * Math.sin(t * 5.7);
        const brightness = 0.42 + 0.75 * pulse;
        fr = 255 * brightness;
        fg = 238 * brightness;
        fb = 170 * brightness;
        chi = pulse > 0.92 ? 13 : 14;
        lit = 0.14 + 0.1 * pulse;
        spr = 7;
        fog = 0;
        star.x = sx;
        star.y = sy;
        star.seen = true;
      } else if (k === K_SNOW) {
        fr = 138;
        fg = 148;
        fb = 180;
        chi = cho[i];
        fog = 0.5;
      } else if (k === K_GROUND || k === K_PRES || k === K_CANE) {
        const ox = x * cY + z * sY;
        const oz = -x * sY + z * cY;
        const shadow = options.shadows
          ? (march(ox, y, oz, L1x, Lmy, L1z, 2) + march(ox, y, oz, L2x, Lmy, L2z, 2)) * 0.5
          : 1;
        const kf = k === K_GROUND ? 0.36 : 0.5;
        const key = lam0[i] * (kf + 0.62 * shadow);
        fr = cr[i] * (0.3 + 0.95 * key) + poolR[i] * (0.85 + 0.15 * Math.sin(t * 1.3 + ph[i] * 20));
        fg = cg[i] * (0.34 + 0.95 * key) + poolG[i];
        fb = cb[i] * (0.5 + 0.9 * key) + poolB[i];
        if (k === K_GROUND && ph[i] > 0) {
          const s3 = 0.75 + 0.45 * Math.sin(t * 2.1 + ph[i] * TAU);
          fr *= s3;
          fg *= s3;
          fb *= s3;
        }
        for (let l = 0; l < LN; l += 4) {
          const dx = LWX[l] - x;
          if (dx > 15 || dx < -15) continue;
          const dz = LWZ[l] - z;
          if (dz > 15 || dz < -15) continue;
          const dy = LWY[l] - y;
          const d2 = dx * dx + dy * dy + dz * dz;
          if (d2 > 225) continue;
          const d = Math.sqrt(d2);
          const w = 1 - d / 15;
          const w2 = w * w;
          const dot = dy > 0 ? dy / d : 0;
          const f = w2 * dot * 0.9 * TW[l];
          fr += lights[l].r * f * 255;
          fg += lights[l].g * f * 255;
          fb += lights[l].b * f * 255;
        }
      } else {
        let lam = nx[i] * Lmx + ny[i] * Lmy + nz[i] * Lmz;
        if (lam < 0) lam = 0;
        let fil = nx[i] * sY + ny[i] * 0.15 + nz[i] * cY;
        if (fil < 0) fil = 0;
        const shadow = options.shadows ? march(x, y, z, Lmx, Lmy, Lmz, 2.5) : 1;
        const ao = 0.55 + 0.45 * Math.min(1, Math.hypot(x, z) / (coneR(y) + 0.001));
        const key = 1.25 * lam * shadow * ao + 0.4 * fil * ao;
        const twinkle = dom[i] >= 0 ? 0.3 + 0.45 * TW[dom[i]] : 0.5;
        fr = cr[i] * (0.38 + key) + Math.min(gr[i], 170) * twinkle;
        fg = cg[i] * (0.44 + key * 0.97) + Math.min(gg[i], 170) * twinkle;
        fb = cb[i] * (0.6 + key * 0.88) + Math.min(gb[i], 170) * twinkle;
      }

      fr += (FOGR - fr) * fog;
      fg += (FOGG - fg) * fog;
      fb += (FOGB - fb) * fog;
      if (fr > 255) fr = 255;
      if (fg > 255) fg = 255;
      if (fb > 255) fb = 255;

      if (!chi) {
        const lum = (0.2126 * fr + 0.7152 * fg + 0.0722 * fb) / 255;
        let index = Math.pow(lum < 0 ? 0 : lum > 1 ? 1 : lum, 0.72) * 15.999 + chj[i];
        index |= 0;
        if (index < 1) index = 1;
        if (index > 15) index = 15;
        chi = index;
      }
      cellR[di] = fr;
      cellG[di] = fg;
      cellB[di] = fb;
      cellCh[di] = chi;
      litB[di] = lit;
      sprB[di] = spr;
    }

    /* backdrop replaces clearRect */
    ctx.drawImage(backdrop, 0, 0, view.width, view.height);

    /* shooting star */
    shooting.countdown -= dt;
    if (shooting.countdown < 0 && shooting.remaining <= 0) {
      shooting.remaining = 0.85;
      shooting.x0 = view.width * (0.15 + Math.random() * 0.6);
      shooting.y0 = view.height * (0.05 + Math.random() * 0.22);
      shooting.dx = -(300 + Math.random() * 260);
      shooting.dy = 110 + Math.random() * 110;
    }
    if (shooting.remaining > 0) {
      shooting.remaining -= dt;
      const progress = 1 - shooting.remaining / 0.85;
      for (let k = 0; k < 7; k++) {
        const q = progress - k * 0.014;
        if (q < 0) break;
        const alpha = (1 - k / 7) * (shooting.remaining / 0.85) * 0.85;
        ctx.fillStyle = `rgba(205,225,255,${alpha})`;
        ctx.fillText(k ? "-" : "*", shooting.x0 + shooting.dx * q, shooting.y0 + shooting.dy * q);
      }
      if (shooting.remaining <= 0) shooting.countdown = 7 + Math.random() * 8;
    }

    view.drawText(GLYPHS, (index, ch, r, g, b) =>
      ch === 1 ? r + g + b >= 85 : true
    );

    if (options.glow) {
      ctx.globalCompositeOperation = "lighter";
      sprFrame = !sprFrame;
      if (sprFrame) {
        for (let di = 0; di < litB.length; di++) {
          const power = litB[di];
          if (power <= 0) continue;
          const size = Math.min(64, 10 + power * 46 * glowScale);
          ctx.globalAlpha = Math.min(0.6, 0.1 + 0.38 * power);
          ctx.drawImage(
            sprites[sprB[di]],
            (di % cols) * cellW + cellW * 0.5 - size / 2,
            ((di / cols) | 0) * cellH + cellH * 0.5 - size / 2,
            size,
            size
          );
        }
      }
      if (star.seen) {
        ctx.globalAlpha = 0.1;
        ctx.drawImage(sprites[7], star.x - 45 * glowScale, star.y - 45 * glowScale, 90 * glowScale, 90 * glowScale);
        ctx.drawImage(sprites[7], star.x - 130 * glowScale, star.y - 5, 260 * glowScale, 10);
        ctx.globalAlpha = 0.05;
        ctx.drawImage(sprites[7], star.x - 5, star.y - 60 * glowScale, 10, 120 * glowScale);
      }
      ctx.globalAlpha = 1;
      ctx.globalCompositeOperation = "source-over";
    }
  }

  return {
    resize,
    frame,
    onDrag(dx, dy) {
      yaw += dx * 0.005;
      yawVelocity = dx * 0.3;
      pitchTarget = clamp(pitchTarget + dy * 0.004, -0.06, 0.55);
    },
    onDragStart() {
      yawVelocity = 0;
    },
    onZoom(deltaY) {
      camDistTarget = clamp(camDistTarget * (1 + deltaY * 0.0012), 75, 220);
    },
    setOption(name, value) {
      if (name in options) options[name] = value;
    },
    get options() {
      return { ...options };
    },
  };
}

registerSceneStyle("christmas-tree", createChristmasTreeStyle);
export { createChristmasTreeStyle };
