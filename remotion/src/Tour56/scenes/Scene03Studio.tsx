import { AbsoluteFill } from "remotion";
import { Badge } from "../components/Badge";
import { Pane, PaneButton } from "../components/Pane";
import { Terminal } from "../components/Terminal";
import { colors, FONT_FAMILY, GUTTER, MONO_FAMILY, ramp } from "../theme";
import { PROGRAM, SPASM_ANNOTATED, STUDIO, TOKEN_RUNS } from "../script";
import type { SceneProps } from "./types";

const DOT_LIMIT = 20;

const CodeRow: React.FC<{
  text: string;
  active?: boolean;
  typedChars?: number;
  showCaret?: boolean;
  dim?: boolean;
}> = ({ text, active = false, typedChars, showCaret = false, dim = false }) => {
  const visible = typeof typedChars === "number" ? text.slice(0, typedChars) : text;

  return (
    <div
      style={{
        backgroundColor: active ? "rgba(244, 198, 106, 0.12)" : "transparent",
        borderLeft: `3px solid ${active ? colors.gold : "transparent"}`,
        boxSizing: "border-box",
        color: active ? colors.gold : dim ? colors.muted : colors.text,
        fontFamily: MONO_FAMILY,
        fontSize: 20,
        lineHeight: 1.55,
        minHeight: 31,
        padding: "0 10px",
        whiteSpace: "pre",
      }}
    >
      {visible}
      {showCaret ? <span style={{ color: colors.cyan }}>▌</span> : null}
    </div>
  );
};

/** Scene 03 (360-480): one program, three synchronised views. */
export const Scene03Studio: React.FC<SceneProps> = ({ frame }) => {
  const typeLine = PROGRAM.py[3];
  const typedCount = Math.floor(ramp(frame, 4, 30) * typeLine.length);
  const pySynced = frame >= 34;
  const spasmSynced = frame >= 56;
  const spSynced = frame >= 74;
  const dotsReveal = ramp(frame, 48, 80);
  const trackReveal = ramp(frame, 64, 82);

  return (
    <AbsoluteFill
      style={{
        boxSizing: "border-box",
        padding: `${GUTTER - 8}px ${GUTTER}px 224px`,
      }}
    >
      <Terminal
        title={STUDIO.title}
        subtitle={STUDIO.url}
        right={
          <>
            <Badge tone="purple">studio</Badge>
            <PaneButton>Settings</PaneButton>
          </>
        }
        style={{ height: "100%" }}
        bodyStyle={{
          backgroundColor: colors.background,
          display: "flex",
          gap: 16,
          padding: 16,
        }}
      >
        <div
          style={{
            display: "flex",
            flex: 1.42,
            flexDirection: "column",
            gap: 12,
            minHeight: 0,
            minWidth: 0,
          }}
        >
          <Pane
            bodyStyle={{ padding: "10px 14px" }}
            badge={
              <Badge tone={pySynced ? "green" : "muted"}>
                {pySynced ? STUDIO.badgeSynced : "typing"}
              </Badge>
            }
            actions={<PaneButton active>Run</PaneButton>}
            label="py"
            style={{ flex: 1.05 }}
          >
            {PROGRAM.py.map((line, index) => (
              <CodeRow
                key={line}
                active={index === 3}
                showCaret={index === 3 && frame < 36}
                text={line}
                typedChars={index === 3 ? typedCount : undefined}
              />
            ))}
          </Pane>

          <Pane
            bodyStyle={{ padding: "10px 14px" }}
            accent={colors.purple}
            badge={
              <Badge tone={spasmSynced ? "green" : "muted"}>
                {spasmSynced ? STUDIO.badgeSynced : "deriving"}
              </Badge>
            }
            actions={
              <>
                <PaneButton>annotations</PaneButton>
                <PaneButton active>Run</PaneButton>
              </>
            }
            label="spasm"
            style={{ flex: 0.95 }}
          >
            {SPASM_ANNOTATED.map((line, index) => {
              const reveal = ramp(frame, 26 + index * 4, 38 + index * 4);
              return (
                <div
                  key={line}
                  style={{
                    color: colors.text,
                    fontFamily: MONO_FAMILY,
                    fontSize: 17,
                    lineHeight: 1.6,
                    opacity: reveal,
                    whiteSpace: "pre",
                  }}
                >
                  {line}
                </div>
              );
            })}
          </Pane>

          <Pane
            bodyStyle={{ padding: "8px 14px" }}
            accent={colors.gold}
            badge={
              <Badge tone={spSynced ? "green" : "muted"}>
                {spSynced ? STUDIO.badgeSynced : "encoding"}
              </Badge>
            }
            actions={
              <>
                <PaneButton active={frame > 62}>{STUDIO.spacesButton}</PaneButton>
                <PaneButton>Copy raw</PaneButton>
                <PaneButton active>Run</PaneButton>
              </>
            }
            label="sp"
            style={{ flex: 1.15 }}
          >
            {TOKEN_RUNS.map((run, index) => {
              const reveal = ramp(frame, 46 + index * 3, 56 + index * 3);
              const dots = Math.min(run.spaces, DOT_LIMIT);
              return (
                <div
                  key={run.token}
                  style={{
                    alignItems: "center",
                    display: "flex",
                    gap: 10,
                    opacity: reveal,
                    padding: "0",
                  }}
                >
                  <span
                    style={{
                      color: colors.muted,
                      fontFamily: MONO_FAMILY,
                      fontSize: 12,
                      textAlign: "right",
                      width: 30,
                    }}
                  >
                    {String(index + 1).padStart(2, "0")}
                  </span>
                  <div style={{ display: "flex", gap: 2 }}>
                    {Array.from({ length: dots }, (_, dot) => (
                      <span
                        key={dot}
                        style={{
                          backgroundColor: colors.gold,
                          borderRadius: 1,
                          height: 6,
                          opacity: 0.35 + 0.65 * dotsReveal,
                          width: 6,
                        }}
                      />
                    ))}
                    {run.spaces > DOT_LIMIT ? (
                      <span
                        style={{
                          color: colors.gold,
                          fontFamily: MONO_FAMILY,
                          fontSize: 12,
                          marginLeft: 5,
                        }}
                      >
                        +{(run.spaces - DOT_LIMIT).toLocaleString("en-US")}
                      </span>
                    ) : null}
                  </div>
                  <span
                    style={{
                      color: colors.muted,
                      fontFamily: MONO_FAMILY,
                      fontSize: 12,
                      marginLeft: "auto",
                    }}
                  >
                    {run.token}
                  </span>
                </div>
              );
            })}
          </Pane>
        </div>

        <div
          style={{
            display: "flex",
            flex: 1,
            flexDirection: "column",
            gap: 12,
            minHeight: 0,
            minWidth: 0,
            opacity: 0.4 + 0.6 * trackReveal,
          }}
        >
          <Pane
            accent={colors.green}
            actions={<PaneButton active={frame > 90}>follow</PaneButton>}
            label="track"
            style={{ flex: 1 }}
          >
            {PROGRAM.py.map((line, index) => (
              <div
                key={line}
                style={{
                  backgroundColor:
                    index === 3 ? "rgba(244, 198, 106, 0.14)" : "transparent",
                  borderLeft: `2px solid ${index === 3 ? colors.gold : "transparent"}`,
                  color: index === 3 ? colors.gold : colors.muted,
                  fontFamily: MONO_FAMILY,
                  fontSize: 16,
                  lineHeight: 1.6,
                  padding: "1px 8px",
                  whiteSpace: "pre",
                }}
              >
                <span style={{ color: colors.edge, marginRight: 12 }}>
                  {String(index + 1).padStart(2, "0")}
                </span>
                {line}
              </div>
            ))}
          </Pane>

          <div
            style={{
              backgroundColor: colors.panel,
              border: `1px solid ${colors.edge}`,
              borderRadius: 14,
              boxSizing: "border-box",
              padding: "14px 16px",
            }}
          >
            <div
              style={{
                color: colors.muted,
                fontFamily: MONO_FAMILY,
                fontSize: 14,
                letterSpacing: 1.5,
                marginBottom: 8,
                textTransform: "uppercase",
              }}
            >
              sync
            </div>
            <div
              style={{
                color: colors.text,
                fontFamily: FONT_FAMILY,
                fontSize: 20,
                lineHeight: 1.35,
              }}
            >
              Edit one pane; the other two derive after {STUDIO.debounce}.
            </div>
          </div>
        </div>
      </Terminal>
    </AbsoluteFill>
  );
};
