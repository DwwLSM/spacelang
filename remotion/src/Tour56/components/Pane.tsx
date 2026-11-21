import type { CSSProperties, ReactNode } from "react";
import { colors, MONO_FAMILY, panelStyle } from "../theme";

/** One editor pane of the OPT_SP studio window. */
export const Pane: React.FC<{
  label: string;
  badge?: ReactNode;
  actions?: ReactNode;
  accent?: string;
  children: ReactNode;
  style?: CSSProperties;
  bodyStyle?: CSSProperties;
}> = ({ label, badge, actions, accent = colors.cyan, children, style, bodyStyle }) => (
  <div
    style={{
      ...panelStyle,
      border: `1px solid ${accent}55`,
      display: "flex",
      flexDirection: "column",
      minHeight: 0,
      minWidth: 0,
      ...style,
    }}
  >
    <div
      style={{
        alignItems: "center",
        borderBottom: `1px solid ${colors.edge}66`,
        boxSizing: "border-box",
        display: "flex",
        flexShrink: 0,
        gap: 12,
        padding: "9px 16px",
      }}
    >
      <span
        style={{
          color: accent,
          fontFamily: MONO_FAMILY,
          fontSize: 15,
          fontWeight: 700,
          letterSpacing: 2,
        }}
      >
        {label}
      </span>
      {badge}
      <div style={{ flex: 1 }} />
      {actions}
    </div>
    <div
      style={{
        flex: 1,
        minHeight: 0,
        overflow: "hidden",
        padding: "12px 16px",
        ...bodyStyle,
      }}
    >
      {children}
    </div>
  </div>
);

/** Tiny mock button in a studio pane header. */
export const PaneButton: React.FC<{
  children: ReactNode;
  active?: boolean;
  tone?: string;
}> = ({ children, active = false, tone = colors.cyan }) => (
  <span
    style={{
      backgroundColor: active ? `${tone}22` : colors.panelDark,
      border: `1px solid ${active ? `${tone}AA` : colors.edge}`,
      borderRadius: 6,
      color: active ? tone : colors.muted,
      fontFamily: MONO_FAMILY,
      fontSize: 13,
      fontWeight: 700,
      letterSpacing: 0.5,
      padding: "5px 9px",
      whiteSpace: "nowrap",
    }}
  >
    {children}
  </span>
);
