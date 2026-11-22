import type { CSSProperties, ReactNode } from "react";
import { colors, MONO_FAMILY, panelStyle } from "../theme";

/** Dark window chrome used for terminals, editors and browser mocks. */
export const Terminal: React.FC<{
  title: string;
  subtitle?: string;
  right?: ReactNode;
  children: ReactNode;
  accent?: string;
  style?: CSSProperties;
  bodyStyle?: CSSProperties;
}> = ({
  title,
  subtitle,
  right,
  children,
  accent = colors.cyan,
  style,
  bodyStyle,
}) => (
  <div
    style={{
      ...panelStyle,
      border: `1px solid ${accent}55`,
      boxShadow: `0 24px 80px rgba(0, 0, 0, 0.45)`,
      display: "flex",
      flexDirection: "column",
      minHeight: 0,
      minWidth: 0,
      overflow: "hidden",
      ...style,
    }}
  >
    <div
      style={{
        alignItems: "center",
        background:
          "linear-gradient(110deg, #1a3037 0%, #172a30 52%, #14252b 100%)",
        borderBottom: `1px solid ${colors.edge}AA`,
        boxSizing: "border-box",
        display: "flex",
        flexShrink: 0,
        gap: 9,
        height: 48,
        padding: "0 18px",
        boxShadow: "inset 0 1px #ffffff08",
      }}
    >
      <span style={{ backgroundColor: "#FF7180", borderRadius: 99, height: 10, width: 10 }} />
      <span style={{ backgroundColor: "#F4C66A", borderRadius: 99, height: 10, width: 10 }} />
      <span style={{ backgroundColor: "#75E0A2", borderRadius: 99, height: 10, width: 10 }} />
      <span
        style={{
          color: colors.text,
          fontFamily: MONO_FAMILY,
          fontSize: 14,
          fontWeight: 700,
          letterSpacing: 0.5,
          marginLeft: 10,
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
        }}
      >
        {title}
      </span>
      {subtitle ? (
        <span
          style={{
            color: colors.muted,
            fontFamily: MONO_FAMILY,
            fontSize: 13,
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}
        >
          {subtitle}
        </span>
      ) : null}
      <div style={{ flex: 1 }} />
      {right}
    </div>
    <div
      style={{
        backgroundColor: colors.panelDark,
        boxShadow: "inset 0 1px 0 #ffffff04",
        flex: 1,
        minHeight: 0,
        overflow: "hidden",
        padding: "18px 22px",
        ...bodyStyle,
      }}
    >
      {children}
    </div>
  </div>
);
