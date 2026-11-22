import { Fragment, type ReactNode } from "react";

const site = {
  background: "#0e1116",
  surface: "#161b22",
  raised: "#1d242d",
  border: "#303943",
  text: "#e6edf3",
  muted: "#9daab7",
  accent: "#58a6ff",
  accentBorder: "#58a6ff77",
  highlight: "#f0a020",
  synced: "#7ee787",
} as const;

const buttonStyle: React.CSSProperties = {
  background: "linear-gradient(180deg, #252e39, #1d242d)",
  border: `1px solid ${site.border}`,
  borderRadius: 5,
  color: site.text,
  font: '600 13px ui-monospace, "JetBrains Mono", monospace',
  lineHeight: 1.2,
  padding: "5px 8px",
  whiteSpace: "nowrap",
};

const EditorPane: React.FC<{
  label: string;
  actions: string[];
  children: ReactNode;
  active?: boolean;
  state?: string;
  pressedActions?: string[];
}> = ({
  label,
  actions,
  children,
  active = false,
  state = "synced",
  pressedActions = [],
}) => (
  <section
    style={{
      background: site.surface,
      border: `1px solid ${active ? site.accentBorder : site.border}`,
      borderRadius: 8,
      boxShadow: active ? "inset 0 0 0 1px #58a6ff33" : "none",
      display: "flex",
      flexDirection: "column",
      minHeight: 0,
      overflow: "hidden",
    }}
  >
    <header
      style={{
        alignItems: "center",
        background: site.raised,
        borderBottom: `1px solid ${site.border}`,
        color: site.muted,
        display: "flex",
        flexShrink: 0,
        gap: 8,
        minHeight: 30,
        padding: "4px 10px",
      }}
    >
      <strong style={{ color: site.text, fontSize: 14 }}>{label}</strong>
      <span
        style={{
          border: `1px solid ${site.synced}66`,
          borderRadius: 99,
          color: site.synced,
          fontSize: 9,
          padding: "1px 6px",
          textTransform: "uppercase",
        }}
      >
        {state}
      </span>
      <span style={{ flex: 1 }} />
      {actions.map((action) => (
        <span
          key={action}
          style={{
            ...buttonStyle,
            ...(action === "show spaces" && pressedActions.includes(action)
              ? { borderColor: site.accentBorder, color: site.accent }
              : {}),
          }}
        >
          {action}
        </span>
      ))}
    </header>
    <div
      style={{
        background: site.background,
        color: site.text,
        flex: 1,
        font: '13px/1.45 ui-monospace, "JetBrains Mono", monospace',
        minHeight: 0,
        overflow: "hidden",
        padding: "7px 10px",
      }}
    >
      {children}
    </div>
  </section>
);

const TracePanel: React.FC<{
  title: string;
  children: ReactNode;
  flex?: number;
}> = ({ title, children, flex = 1 }) => (
  <section
    style={{
      background: site.surface,
      border: "1px solid #35404b",
      borderRadius: 8,
      boxShadow: "inset 0 1px 0 #ffffff08, 0 5px 16px #0003",
      display: "flex",
      flex: `${flex} 1 0`,
      flexDirection: "column",
      minHeight: 0,
      overflow: "hidden",
    }}
  >
    <header
      style={{
        background: "linear-gradient(180deg, #252f3a, #202a35)",
        borderBottom: `1px solid ${site.border}`,
        color: site.muted,
        flexShrink: 0,
        fontSize: 13,
        fontWeight: 700,
        letterSpacing: 0.5,
        padding: "5px 9px",
      }}
    >
      {title}
    </header>
    <div
      style={{
        color: site.text,
        flex: 1,
        font: '12px/1.45 ui-monospace, "JetBrains Mono", monospace',
        minHeight: 0,
        overflow: "hidden",
        padding: "6px 9px",
      }}
    >
      {children}
    </div>
  </section>
);

export const StudioMock: React.FC<{
  editors: [ReactNode, ReactNode, ReactNode];
  traceCode: ReactNode;
  statePanels: [ReactNode, ReactNode, ReactNode, ReactNode];
  stepLabel: string;
  traceProgress?: number;
  activePane?: "py" | "spasm" | "sp";
  spPreview?: boolean;
}> = ({
  editors,
  traceCode,
  statePanels,
  stepLabel,
  traceProgress = 0,
  activePane,
  spPreview = false,
}) => (
  <div
    style={{
      background: site.background,
      border: `1px solid ${site.border}`,
      boxShadow: "0 8px 26px #0005",
      color: site.text,
      fontFamily: 'ui-monospace, "JetBrains Mono", monospace',
      height: 850,
      overflow: "hidden",
      width: "100%",
    }}
  >
    <header
      style={{
        alignItems: "center",
        background: site.surface,
        borderBottom: `1px solid ${site.border}`,
        display: "flex",
        height: 58,
        justifyContent: "space-between",
        padding: "0 22px",
      }}
    >
      <strong style={{ fontSize: 18 }}>OPT_SP — SpaceLang Visual Debugger</strong>
      <div style={{ alignItems: "center", display: "flex", gap: 10 }}>
        <span style={buttonStyle}>← Back to editor</span>
        <span style={buttonStyle}>Settings</span>
      </div>
    </header>

    <main
      style={{
        boxSizing: "border-box",
        display: "grid",
        gap: 8,
        gridTemplateColumns: "minmax(0, 58fr) 6px minmax(0, 42fr)",
        gridTemplateRows: "minmax(0, 1fr) 44px",
        height: 792,
        padding: 13,
      }}
    >
      <div
        style={{
          display: "grid",
          gap: 0,
          gridTemplateRows: "minmax(0, 1fr) 6px minmax(0, 1fr) 6px minmax(0, 1fr)",
          minHeight: 0,
        }}
      >
        <EditorPane
          actions={["Run"]}
          active={activePane === "py"}
          label="py"
        >
          {editors[0]}
        </EditorPane>
        <div />
        <EditorPane
          actions={["annotations", "Run"]}
          active={activePane === "spasm"}
          label="spasm"
          state={activePane === "spasm" ? "editing" : "synced"}
        >
          {editors[1]}
        </EditorPane>
        <div />
        <EditorPane
          actions={[
            "show spaces",
            "Copy raw",
            "Run",
          ]}
          active={activePane === "sp"}
          label="sp"
          pressedActions={spPreview ? ["show spaces"] : []}
          state={activePane === "sp" ? "editing" : "synced"}
        >
          {editors[2]}
        </EditorPane>
      </div>

      <div
        style={{
          background: site.border,
          borderRadius: 3,
          margin: "20px 2px",
        }}
      />

      <div
        style={{
          display: "grid",
          gap: 0,
          gridTemplateRows: "minmax(110px, 1fr) 6px minmax(160px, 2.2fr)",
          minHeight: 0,
        }}
      >
        <TracePanel title="Trace">
          <div
            style={{
              borderBottom: `1px solid ${site.border}`,
              color: site.muted,
              fontSize: 11,
              margin: "-6px -9px 5px",
              padding: "4px 9px",
              textAlign: "right",
            }}
          >
            <span style={{ ...buttonStyle, color: site.accent }}>follow</span>
          </div>
          {traceCode}
        </TracePanel>
        <div />
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: 3.2,
            minHeight: 0,
          }}
        >
          {statePanels.map((content, index) => (
            <Fragment key={["Call Stack", "Operand Stack", "Heap / Objects", "Printed Output"][index]}>
              {index > 0 ? (
                <div style={{ background: site.border, flexShrink: 0, height: 4 }} />
              ) : null}
              <TracePanel
                title={
                  ["Call Stack", "Operand Stack", "Heap / Objects", "Printed Output"][index]
                }
              >
                {content}
              </TracePanel>
            </Fragment>
          ))}
        </div>
      </div>

      <nav
        style={{
          alignItems: "center",
          background: site.surface,
          border: `1px solid ${site.border}`,
          borderRadius: 6,
          display: "flex",
          gap: 7,
          gridColumn: "1 / -1",
          minWidth: 0,
          padding: "5px 8px",
        }}
      >
        {["⏮", "⏪", "⏩", "▶"].map((item) => (
          <span key={item} style={{ ...buttonStyle, color: site.accent }}>
            {item}
          </span>
        ))}
        <span style={{ color: site.muted, fontSize: 11, marginLeft: 8 }}>Speed</span>
        <span
          style={{
            background: site.border,
            borderRadius: 99,
            height: 4,
            width: 110,
          }}
        >
          <span
            style={{
              background: site.accent,
              borderRadius: 99,
              display: "block",
              height: "100%",
              width: "67%",
            }}
          />
        </span>
        <span style={{ color: site.muted, fontSize: 11 }}>1 s / step</span>
        <span style={{ ...buttonStyle, color: site.accent }}>⏭</span>
        <span
          style={{
            background: site.border,
            borderRadius: 99,
            flex: "1 1 0%",
            height: 4,
            marginLeft: 8,
            minWidth: 80,
            position: "relative",
          }}
        >
          <span
            style={{
              background: site.accent,
              borderRadius: 99,
              display: "block",
              height: "100%",
              width: `${traceProgress * 100}%`,
            }}
          />
        </span>
        <span
          style={{
            background: site.background,
            border: `1px solid ${site.border}`,
            borderRadius: 4,
            color: site.text,
            fontSize: 12,
            marginLeft: 8,
            padding: "4px 8px",
            whiteSpace: "nowrap",
          }}
        >
          {stepLabel}
        </span>
      </nav>
    </main>
  </div>
);

export const studioColors = site;
