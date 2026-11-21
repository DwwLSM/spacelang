import type { CSSProperties, ReactNode } from "react";
import { colors, MONO_FAMILY } from "../theme";

const tones = {
  cyan: colors.cyan,
  green: colors.green,
  gold: colors.gold,
  red: colors.red,
  purple: colors.purple,
  muted: colors.muted,
} as const;

export type BadgeTone = keyof typeof tones;

export const toneColor = (tone: BadgeTone): string => tones[tone];

/** Small mono status chip used in pane headers, toasts and stage cards. */
export const Badge: React.FC<{
  children: ReactNode;
  tone?: BadgeTone;
  solid?: boolean;
  style?: CSSProperties;
}> = ({ children, tone = "cyan", solid = false, style }) => {
  const color = tones[tone];

  return (
    <span
      style={{
        alignItems: "center",
        backgroundColor: solid ? color : `${color}1A`,
        border: `1px solid ${color}99`,
        borderRadius: 8,
        boxSizing: "border-box",
        color: solid ? colors.background : color,
        display: "inline-flex",
        fontFamily: MONO_FAMILY,
        fontSize: 14,
        fontWeight: 700,
        letterSpacing: 1,
        lineHeight: 1,
        padding: "7px 11px",
        textTransform: "uppercase",
        whiteSpace: "nowrap",
        ...style,
      }}
    >
      {children}
    </span>
  );
};
