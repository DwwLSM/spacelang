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

/** Reject a mirror that fails instruction-by-instruction verification. */
export const Scene07Verify: React.FC<SceneProps> = ({ frame }) => {
  const left = ramp(frame, -12, 2);
  const right = ramp(frame, -10, 6);
  const banner = ramp(frame, -12, 0);
  const firstVerdict = frame >= 40;
  const secondAnswer = ramp(frame, 62, 74);
  const accepted = frame >= 82;
  const resultReveal = ramp(frame, 82, 94);
  const resultEase = easeOut(resultReveal);
  const answerSize = accepted ? lerp(54, 68, resultEase) : 54;
  const answerScale = accepted ? lerp(0.72, 1, resultEase) : 1;
  return (
    <AbsoluteFill
        style={{
          boxSizing: "border-box",
          display: "flex",
          flexDirection: "column",
          gap: 20,
          padding: `${GUTTER - 4}px ${GUTTER}px 112px`,
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
            highlight={accepted ? "OP 2" : "OP 3"}
            lines={
              accepted
                ? STALE.asmAfter
                : STALE.asmBefore.map((line) =>
                    line === "OP 1" ? "OP 3" : line,
                  )
            }
            title={accepted ? "answer now compiles to" : "answer compiles to"}
            tone={accepted ? colors.green : colors.red}
          />
        </div>

        <div
          style={{
            alignItems: "center",
            backgroundColor: accepted
              ? `${colors.green}12`
              : colors.panel,
            border: `1px solid ${
              accepted ? colors.green : colors.red
            }77`,
            borderRadius: 16,
            boxSizing: "border-box",
            display: "flex",
            gap: 16,
            opacity: banner,
            padding: "16px 22px",
            transform: `translateY(${lerp(12, 0, easeOut(banner))}px)`,
          }}
        >
          <Badge solid tone={accepted ? "green" : "red"}>
            {accepted ? "accepted" : "rejected"}
          </Badge>
          <span
            style={{
              color: colors.text,
              fontFamily: FONT_FAMILY,
              fontSize: 30,
              fontWeight: 600,
            }}
          >
            {accepted ? "Mirror accepted: instructions match" : SYNC.rejected}
          </span>
          <span style={{ flex: 1 }} />
          {accepted ? (
            <Badge tone="green">OP 2 matched</Badge>
          ) : (
            <>
              <Badge tone="gold">{SYNC.needs}</Badge>
              <Badge tone="red">{SYNC.got}</Badge>
            </>
          )}
        </div>

        <div
          style={{
            alignItems: "center",
            backgroundColor: accepted
              ? `rgba(117, 224, 162, ${0.12 * resultEase + 0.06})`
              : colors.panelDark,
            border: `1px solid ${
              accepted ? colors.green : firstVerdict ? colors.red : colors.edge
            }${accepted ? "dd" : "88"}`,
            borderRadius: 18,
            boxSizing: "border-box",
            display: "flex",
            flex: 1,
            gap: 24,
            opacity: ramp(frame, -8, 6),
            padding: "22px 28px",
            boxShadow: accepted
              ? `0 0 ${28 * resultEase}px ${colors.green}33, inset 0 0 ${18 * resultEase}px ${colors.green}12`
              : "none",
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
              verification · compile and compare locally
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
              backgroundColor: accepted
                ? `${colors.green}${Math.round(18 + resultEase * 24).toString(16).padStart(2, "0")}`
                : "transparent",
              border: accepted
                ? `2px solid ${colors.green}`
                : "2px solid transparent",
              borderRadius: 18,
              display: "flex",
              flexDirection: "column",
              gap: 8,
              minWidth: 260,
              minHeight: 150,
              justifyContent: "center",
              opacity: accepted ? lerp(0.82, 1, resultEase) : 1,
              padding: "14px 18px",
              transform: `scale(${answerScale})`,
            }}
          >
            {accepted ? (
              <div
                style={{
                  alignItems: "center",
                  backgroundColor: colors.green,
                  borderRadius: 999,
                  color: colors.panelDark,
                  display: "flex",
                  fontFamily: MONO_FAMILY,
                  fontSize: 22,
                  fontWeight: 900,
                  height: 34,
                  justifyContent: "center",
                  opacity: resultEase,
                  transform: `scale(${lerp(0.5, 1, resultEase)})`,
                  width: 34,
                }}
              >
                ✓
              </div>
            ) : null}
            <div
              style={{
                color: accepted
                  ? colors.green
                  : firstVerdict
                    ? colors.red
                    : colors.muted,
                fontFamily: MONO_FAMILY,
                fontSize: answerSize,
                fontWeight: 700,
                letterSpacing: 1,
                lineHeight: 1,
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
  );
};
