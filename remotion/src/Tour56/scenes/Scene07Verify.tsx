import { AbsoluteFill } from "remotion";
import { Badge } from "../components/Badge";
import {
  colors,
  easeOut,
  FONT_FAMILY,
  GUTTER,
  lerp,
  MONO_FAMILY,
  ramp,
} from "../theme";
import { STALE, SYNC } from "../script";
import type { SceneProps } from "./types";

const CodeCard: React.FC<{
  title: string;
  lines: readonly string[];
  highlight: string;
  tone: string;
  appear: number;
}> = ({ title, lines, highlight, tone, appear }) => (
  <div
    style={{
      backgroundColor: colors.panelDark,
      border: `1px solid ${tone}88`,
      borderRadius: 18,
      boxSizing: "border-box",
      flex: 1,
      opacity: appear,
      padding: "20px 24px",
      transform: `translateY(${lerp(16, 0, easeOut(appear))}px)`,
    }}
  >
    <div
      style={{
        color: tone,
        fontFamily: MONO_FAMILY,
        fontSize: 17,
        fontWeight: 700,
        letterSpacing: 2,
        marginBottom: 14,
        textTransform: "uppercase",
      }}
    >
      {title}
    </div>
    {lines.map((line) => (
      <div
        key={line}
        style={{
          backgroundColor: line === highlight ? `${tone}26` : "transparent",
          borderLeft: `3px solid ${line === highlight ? tone : "transparent"}`,
          color: line === highlight ? tone : colors.text,
          fontFamily: MONO_FAMILY,
          fontSize: 26,
          lineHeight: 1.6,
          padding: "0 12px",
          whiteSpace: "pre",
        }}
      >
        {line}
      </div>
    ))}
  </div>
);

const flashAt = (frame: number, start: number): number => {
  if (frame < start || frame > start + 5) {
    return 0;
  }
  return 1 - ramp(frame, start, start + 5);
};

/** Scene 07 (840-960): the compiler rejects the answer, flash frames included. */
export const Scene07Verify: React.FC<SceneProps> = ({ frame }) => {
  const left = ramp(frame, -12, 2);
  const right = ramp(frame, -10, 6);
  const banner = ramp(frame, -12, 0);
  const firstVerdict = frame >= 40;
  const secondAnswer = ramp(frame, 62, 74);
  const accepted = frame >= 82;
  const flash = Math.max(
    flashAt(frame, 8),
    flashAt(frame, 28),
    flashAt(frame, 50),
  );

  return (
    <>
      <AbsoluteFill
        style={{
          boxSizing: "border-box",
          display: "flex",
          flexDirection: "column",
          gap: 20,
          padding: `${GUTTER - 4}px ${GUTTER}px 224px`,
        }}
      >
        <div style={{ display: "flex", gap: 20 }}>
          <CodeCard
            appear={left}
            highlight="OP 2"
            lines={STALE.asmAfter}
            title="assembly needs"
            tone={colors.gold}
          />
          <CodeCard
            appear={right}
            highlight="OP 3"
            lines={STALE.asmBefore.map((line) =>
              line === "OP 1" ? "OP 3" : line,
            )}
            title="answer compiles to"
            tone={colors.red}
          />
        </div>

        <div
          style={{
            alignItems: "center",
            backgroundColor: colors.panel,
            border: `1px solid ${colors.red}77`,
            borderRadius: 16,
            boxSizing: "border-box",
            display: "flex",
            gap: 16,
            opacity: banner,
            padding: "16px 22px",
            transform: `translateY(${lerp(12, 0, easeOut(banner))}px)`,
          }}
        >
          <Badge solid tone="red">
            rejected
          </Badge>
          <span
            style={{
              color: colors.text,
              fontFamily: FONT_FAMILY,
              fontSize: 30,
              fontWeight: 600,
            }}
          >
            {SYNC.rejected}
          </span>
          <span style={{ flex: 1 }} />
          <Badge tone="gold">{SYNC.needs}</Badge>
          <Badge tone="red">{SYNC.got}</Badge>
        </div>

        <div
          style={{
            alignItems: "center",
            backgroundColor: colors.panelDark,
            border: `1px solid ${
              accepted ? colors.green : firstVerdict ? colors.red : colors.edge
            }88`,
            borderRadius: 18,
            boxSizing: "border-box",
            display: "flex",
            flex: 1,
            gap: 24,
            opacity: ramp(frame, -8, 6),
            padding: "22px 28px",
          }}
        >
          <div style={{ flex: 1 }}>
            <div
              style={{
                color: colors.muted,
                fontFamily: MONO_FAMILY,
                fontSize: 16,
                letterSpacing: 2,
                marginBottom: 12,
                textTransform: "uppercase",
              }}
            >
              verification · run in the browser, microseconds
            </div>
            <div
              style={{
                color: colors.text,
                fontFamily: MONO_FAMILY,
                fontSize: 40,
                whiteSpace: "pre",
              }}
            >
              {SYNC.formula}
            </div>
            <div
              style={{
                color: colors.muted,
                fontFamily: MONO_FAMILY,
                fontSize: 17,
                marginTop: 14,
              }}
            >
              {STALE.pyfrontNote} · the answer is only accepted when it
              reproduces the assembly instruction for instruction
            </div>
          </div>
          <div
            style={{
              alignItems: "center",
              display: "flex",
              flexDirection: "column",
              gap: 8,
              minWidth: 230,
            }}
          >
            <div
              style={{
                color: accepted
                  ? colors.green
                  : firstVerdict
                    ? colors.red
                    : colors.muted,
                fontFamily: MONO_FAMILY,
                fontSize: 54,
                fontWeight: 700,
                letterSpacing: 1,
              }}
            >
              {accepted ? "true" : firstVerdict ? "false" : "…"}
            </div>
            <Badge
              tone={accepted ? "green" : firstVerdict ? "red" : "muted"}
            >
              {accepted ? SYNC.accepted : firstVerdict ? SYNC.refused : "checking"}
            </Badge>
            <div
              style={{
                color: colors.muted,
                fontFamily: MONO_FAMILY,
                fontSize: 15,
                opacity: secondAnswer,
                textAlign: "center",
              }}
            >
              answer 2 · return a - b
            </div>
          </div>
        </div>
      </AbsoluteFill>
      <AbsoluteFill
        style={{
          backgroundColor: `rgba(255, 113, 128, ${0.2 * flash})`,
          pointerEvents: "none",
          zIndex: 10,
        }}
      />
    </>
  );
};
