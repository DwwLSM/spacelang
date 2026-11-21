import type { CSSProperties } from "react";

/**
 * Palette and typography reused from `src/SpaceLangIntro.tsx` so the tour
 * video reads as the same product family as the 60-second introduction.
 */
export const colors = {
  background: "#071318",
  panel: "#10232A",
  panelDark: "#0B171C",
  edge: "#28505A",
  cyan: "#63D8E8",
  green: "#75E0A2",
  gold: "#F4C66A",
  purple: "#B9A1FF",
  text: "#EDF5F4",
  muted: "#9AB1B5",
  red: "#FF7180",
} as const;

export type ColorName = keyof typeof colors;

export const FONT_FAMILY =
  '"Inter", "Noto Sans CJK SC", "PingFang SC", "Microsoft YaHei", sans-serif';
export const MONO_FAMILY =
  '"SFMono-Regular", "Cascadia Code", "Noto Sans Mono CJK SC", monospace';

export const clamp01 = (value: number): number => Math.min(1, Math.max(0, value));

/** Frame -> 0..1 ramp between `from` and `to`. */
export const ramp = (frame: number, from: number, to: number): number =>
  clamp01((frame - from) / Math.max(1, to - from));

/** Ease-out cubic, used for nearly every entrance. */
export const easeOut = (value: number): number => 1 - Math.pow(1 - clamp01(value), 3);

export const lerp = (from: number, to: number, value: number): number =>
  from + (to - from) * clamp01(value);

/** Fade/translate entrance helper shared by scenes. */
export const enter = (
  frame: number,
  from: number,
  toward = 12,
): { opacity: number; transform: string } => {
  const t = ramp(frame, from, from + 10);
  return {
    opacity: t,
    transform: `translateY(${lerp(toward, 0, easeOut(t))}px)`,
  };
};

export const panelStyle: CSSProperties = {
  backgroundColor: colors.panel,
  border: `1px solid ${colors.edge}`,
  borderRadius: 18,
  boxSizing: "border-box",
};

export const eyebrowStyle: CSSProperties = {
  color: colors.muted,
  fontFamily: MONO_FAMILY,
  fontSize: 16,
  fontWeight: 700,
  letterSpacing: 2,
};

/** The 96px gutter every scene aligns to. */
export const GUTTER = 96;
