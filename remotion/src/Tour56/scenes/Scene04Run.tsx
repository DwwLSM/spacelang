import { AbsoluteFill } from "remotion";
import { Badge } from "../components/Badge";
import { Pane, PaneButton } from "../components/Pane";
import { Terminal } from "../components/Terminal";
import { colors, GUTTER, MONO_FAMILY, ramp } from "../theme";
import { PROGRAM, STUDIO, TRACE } from "../script";
import type { SceneProps } from "./types";

const SLIDER_WIDTH = 260;

const PanelBody: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <div
    style={{
      color: colors.text,
      fontFamily: MONO_FAMILY,
      fontSize: 17,
      lineHeight: 1.5,
    }}
  >
    {children}
  </div>
);

const EmptyLine: React.FC<{ text: string }> = ({ text }) => (
  <span style={{ color: colors.edge, fontFamily: MONO_FAMILY, fontSize: 16 }}>
    {text}
  </span>
);

/** Scene 04 (480-600): run and step, with the debugger's state panels. */
export const Scene04Run: React.FC<SceneProps> = ({ frame }) => {
  const step = Math.min(
    TRACE.length - 1,
    Math.max(0, Math.floor(ramp(frame, 6, 96) * TRACE.length)),
  );
  const state = TRACE[step];
  const progress = step / (TRACE.length - 1);
  const running = frame < 100;

  const activeSpasm = PROGRAM.spasm.findIndex((line) => line === state.ip);
  const activePy = step >= 3 && step <= 7 ? 1 : 3;

  return (
    <AbsoluteFill
      style={{
        boxSizing: "border-box",
        padding: `${GUTTER - 8}px ${GUTTER}px 224px`,
      }}
    >
      <Terminal
        title={STUDIO.title}
        subtitle={`${STUDIO.url} · running in the browser`}
        right={
          <>
            <Badge tone="green">Pyodide</Badge>
            <PaneButton active>Run</PaneButton>
          </>
        }
        style={{ height: "100%" }}
        bodyStyle={{
          backgroundColor: colors.background,
          display: "flex",
          flexDirection: "column",
          gap: 12,
          padding: 14,
        }}
      >
        <div style={{ display: "flex", flex: 1, gap: 12, minHeight: 0 }}>
          <div
            style={{
              display: "flex",
              flex: 1,
              flexDirection: "column",
              gap: 12,
              minHeight: 0,
              minWidth: 0,
            }}
          >
            <Pane
              bodyStyle={{ padding: "8px 12px" }}
              badge={<Badge tone="green">running</Badge>}
              label="py"
              style={{ flex: 1 }}
            >
              {PROGRAM.py.map((line, index) => (
                <div
                  key={line}
                  style={{
                    backgroundColor:
                      index === activePy ? "rgba(244, 198, 106, 0.13)" : "transparent",
                    borderLeft: `3px solid ${
                      index === activePy ? colors.gold : "transparent"
                    }`,
                    color: index === activePy ? colors.gold : colors.muted,
                    fontFamily: MONO_FAMILY,
                    fontSize: 18,
                    lineHeight: 1.55,
                    padding: "0 8px",
                    whiteSpace: "pre",
                  }}
                >
                  {line}
                </div>
              ))}
            </Pane>

            <Pane
              accent={colors.purple}
              bodyStyle={{ padding: "8px 12px" }}
              badge={<Badge tone="purple">ip {step + 1}</Badge>}
              label="spasm"
              style={{ flex: 1.1 }}
            >
              {PROGRAM.spasm.map((line, index) => (
                <div
                  key={line}
                  style={{
                    backgroundColor:
                      index === activeSpasm ? "rgba(185, 161, 255, 0.14)" : "transparent",
                    borderLeft: `3px solid ${
                      index === activeSpasm ? colors.purple : "transparent"
                    }`,
                    color: index === activeSpasm ? colors.purple : colors.muted,
                    fontFamily: MONO_FAMILY,
                    fontSize: 15,
                    lineHeight: 1.35,
                    padding: "0 8px",
                    whiteSpace: "pre",
                  }}
                >
                  {line}
                </div>
              ))}
            </Pane>
          </div>

          <div
            style={{
              display: "flex",
              flex: 1.18,
              flexDirection: "column",
              gap: 12,
              minHeight: 0,
              minWidth: 0,
            }}
          >
            <Pane
              accent={colors.green}
              bodyStyle={{ padding: "6px 12px" }}
              actions={<PaneButton>follow</PaneButton>}
              label="track"
              style={{ flex: 1.05 }}
            >
              {PROGRAM.spasm.map((line, index) => (
                <div
                  key={line}
                  style={{
                    backgroundColor:
                      index === activeSpasm ? "rgba(244, 198, 106, 0.14)" : "transparent",
                    borderLeft: `2px solid ${
                      index === activeSpasm ? colors.gold : "transparent"
                    }`,
                    color: index === activeSpasm ? colors.gold : colors.muted,
                    fontFamily: MONO_FAMILY,
                    fontSize: 15,
                    lineHeight: 1.45,
                    padding: "0 8px",
                    whiteSpace: "pre",
                  }}
                >
                  <span style={{ color: colors.edge, marginRight: 10 }}>
                    {String(index + 1).padStart(2, "0")}
                  </span>
                  {line}
                </div>
              ))}
            </Pane>

            <div
              style={{
                display: "grid",
                flex: 1.35,
                gap: 12,
                gridTemplateColumns: "1fr 1fr",
                gridTemplateRows: "1fr 1fr",
                minHeight: 0,
              }}
            >
              <Pane accent={colors.cyan} bodyStyle={{ padding: "8px 12px" }} label="Call Stack">
                <PanelBody>
                  {state.call.length > 0 ? (
                    <div style={{ color: colors.cyan }}>double(value=22)</div>
                  ) : (
                    <EmptyLine text="&lt;empty&gt;" />
                  )}
                </PanelBody>
              </Pane>
              <Pane accent={colors.gold} bodyStyle={{ padding: "8px 12px" }} label="Operand Stack">
                <PanelBody>
                  {state.stack.length > 0 ? (
                    <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                      {[...state.stack].reverse().map((value, index) => (
                        <span
                          key={`${value}-${index}`}
                          style={{
                            backgroundColor: `${colors.gold}18`,
                            border: `1px solid ${colors.gold}88`,
                            borderRadius: 6,
                            color: colors.gold,
                            fontSize: 16,
                            padding: "2px 8px",
                            width: "fit-content",
                          }}
                        >
                          int {value}
                        </span>
                      ))}
                    </div>
                  ) : (
                    <EmptyLine text="&lt;empty&gt;" />
                  )}
                </PanelBody>
              </Pane>
              <Pane accent={colors.purple} bodyStyle={{ padding: "8px 12px" }} label="Heap / Objects">
                <PanelBody>
                  <div style={{ color: colors.muted, fontSize: 16 }}>double</div>
                  <div style={{ color: colors.purple, fontSize: 16 }}>&lt;function&gt;</div>
                </PanelBody>
              </Pane>
              <Pane accent={colors.green} bodyStyle={{ padding: "8px 12px" }} label="Printed Output">
                <PanelBody>
                  {state.printed.length > 0 ? (
                    <div style={{ color: colors.green }}>{state.printed.join("\n")}</div>
                  ) : (
                    <EmptyLine text="—" />
                  )}
                </PanelBody>
              </Pane>
            </div>
          </div>
        </div>

        <div
          style={{
            alignItems: "center",
            backgroundColor: colors.panelDark,
            border: `1px solid ${colors.edge}`,
            borderRadius: 12,
            boxSizing: "border-box",
            display: "flex",
            flexShrink: 0,
            gap: 12,
            height: 52,
            padding: "0 16px",
          }}
        >
          {["|<", "<", running ? "Pause" : "Play", ">", ">|"].map((button) => (
            <span
              key={button}
              style={{
                backgroundColor:
                  button === (running ? "Pause" : "Play")
                    ? `${colors.green}22`
                    : colors.panel,
                border: `1px solid ${
                  button === (running ? "Pause" : "Play")
                    ? colors.green
                    : colors.edge
                }`,
                borderRadius: 6,
                color:
                  button === (running ? "Pause" : "Play")
                    ? colors.green
                    : colors.muted,
                fontFamily: MONO_FAMILY,
                fontSize: 14,
                fontWeight: 700,
                minWidth: 46,
                padding: "6px 10px",
                textAlign: "center",
              }}
            >
              {button}
            </span>
          ))}
          <span
            style={{
              color: colors.muted,
              fontFamily: MONO_FAMILY,
              fontSize: 15,
              marginLeft: 14,
            }}
          >
            Speed
          </span>
          <div
            style={{
              backgroundColor: "#183139",
              borderRadius: 99,
              height: 5,
              overflow: "hidden",
              width: SLIDER_WIDTH,
            }}
          >
            <div
              style={{
                backgroundColor: colors.cyan,
                height: "100%",
                width: `${progress * 100}%`,
              }}
            />
          </div>
          <span
            style={{
              color: colors.text,
              fontFamily: MONO_FAMILY,
              fontSize: 16,
              marginLeft: "auto",
            }}
          >
            {STUDIO.stepLabel(step + 1, TRACE.length)}
          </span>
          <Badge tone="gold">follow</Badge>
          <span
            style={{
              color: colors.muted,
              fontFamily: MONO_FAMILY,
              fontSize: 15,
            }}
          >
            autoplay
          </span>
        </div>
      </Terminal>
    </AbsoluteFill>
  );
};
