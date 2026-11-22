import type { CSSProperties } from "react";
import { colors, easeOut, FONT_FAMILY, lerp, ramp } from "../theme";

/** Big figure that snaps in: used for the runtime multipliers and the CI count. */
export const NumberPop: React.FC<{
  value: string;
  label?: string;
  sub?: string;
  frame: number;
  enterAt: number;
  color?: string;
  size?: number;
  letterSpacing?: number;
  style?: CSSProperties;
}> = ({
  value,
  label,
  sub,
  frame,
  enterAt,
  color = colors.cyan,
  size = 116,
  letterSpacing = -3,
  style,
}) => {
  const t = ramp(frame, enterAt, enterAt + 14);
  const scale = lerp(0.68, 1, easeOut(t));
  const opacity = ramp(frame, enterAt, enterAt + 5);

  return (
    <div
      style={{
        alignItems: "center",
        display: "flex",
        flexDirection: "column",
        gap: 4,
        opacity,
        transform: `scale(${scale})`,
        ...style,
      }}
    >
      {label ? (
        <div
          style={{
            color: colors.muted,
            fontFamily: FONT_FAMILY,
            fontSize: 18,
            fontWeight: 600,
            letterSpacing: 3,
            textTransform: "uppercase",
          }}
        >
          {label}
        </div>
      ) : null}
      <div
        style={{
          color,
          fontFamily: FONT_FAMILY,
          fontSize: size,
          fontWeight: 750,
          letterSpacing,
          lineHeight: 1,
        }}
      >
        {value}
      </div>
      {sub ? (
        <div
          style={{
            color: colors.muted,
            fontFamily: FONT_FAMILY,
            fontSize: 20,
            fontWeight: 500,
          }}
        >
          {sub}
        </div>
      ) : null}
    </div>
  );
};
