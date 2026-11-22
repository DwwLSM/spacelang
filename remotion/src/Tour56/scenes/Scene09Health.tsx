import { AbsoluteFill } from "remotion";
import { Badge } from "../components/Badge";
import { Terminal } from "../components/Terminal";
import { colors, easeOut, FONT_FAMILY, GUTTER, MONO_FAMILY, ramp } from "../theme";
import { HEALTH } from "../script";
import type { SceneProps } from "./types";

const jsonLines = [
  "{",
  '  "ok": true,',
  '  "checks": {',
  ...HEALTH.checks.map(
    ([name, value], index) =>
      `    "${name}": ${value}${index < HEALTH.checks.length - 1 ? "," : ""}`,
  ),
  "  },",
  '  "hint": null',
  "}",
];

/** Show the actual loopback-only static-file health response shape. */
export const Scene09Health: React.FC<SceneProps> = ({ frame }) => {
  const typed = Math.floor(ramp(frame, 2, 22) * HEALTH.url.length);
  const responseReveal = ramp(frame, 14, 28);
  const noteReveal = ramp(frame, 58, 70);
  const healthReveal = ramp(frame, 28, 48);
  const healthEase = easeOut(healthReveal);

  return (
    <AbsoluteFill
      style={{
        alignItems: "center",
        boxSizing: "border-box",
        display: "flex",
        padding: `${GUTTER + 6}px ${GUTTER}px 112px`,
      }}
    >
      <Terminal
        title="OPT_SP — health endpoint"
        subtitle={HEALTH.endpoint}
        right={<Badge tone="green">{HEALTH.policy}</Badge>}
        style={{
          height: "100%",
          width: "100%",
          boxShadow: `0 24px 80px rgba(0, 0, 0, 0.45), 0 0 ${32 * healthEase}px ${colors.green}18`,
        }}
        bodyStyle={{
          display: "flex",
          flexDirection: "column",
          gap: 18,
          padding: 22,
        }}
      >
        <div
          style={{
            alignItems: "center",
            backgroundColor: colors.panel,
            border: `1px solid ${colors.green}${Math.round(60 + healthEase * 90).toString(16).padStart(2, "0")}`,
            borderRadius: 12,
            display: "flex",
            gap: 14,
            height: 54,
            padding: "0 18px",
          }}
        >
          <Badge tone="muted">GET</Badge>
          <span
            style={{
              color: colors.cyan,
              fontFamily: MONO_FAMILY,
              fontSize: 22,
            }}
          >
            http://{HEALTH.url.slice(0, typed)}
            {typed < HEALTH.url.length ? (
              <span style={{ color: colors.text }}>▌</span>
            ) : null}
          </span>
        </div>

        <pre
          style={{
            backgroundColor: colors.panelDark,
            border: `1px solid ${colors.edge}`,
            borderRadius: 12,
            boxSizing: "border-box",
            color: colors.text,
            display: "flex",
            flexDirection: "column",
            flex: 1,
            fontFamily: MONO_FAMILY,
            fontSize: 23,
            justifyContent: "center",
            lineHeight: 1.55,
            margin: 0,
            opacity: responseReveal,
            overflow: "hidden",
            padding: "22px 28px",
          }}
        >
          {jsonLines.map((line, index) => (
            <div
              key={`${index}-${line}`}
              style={{
                color: line.includes("true")
                  ? colors.green
                  : line.includes("null")
                    ? colors.muted
                    : colors.text,
                opacity: ramp(frame, 18 + index * 1.5, 25 + index * 1.5),
              }}
            >
              {line}
            </div>
          ))}
        </pre>

        <div
          style={{
            alignItems: "center",
            display: "flex",
            gap: 14,
            opacity: noteReveal,
          }}
        >
          <Badge tone="green">browser side</Badge>
          <span
            style={{
              color: colors.muted,
              fontFamily: FONT_FAMILY,
              fontSize: 22,
            }}
          >
            {HEALTH.note}
          </span>
        </div>
      </Terminal>
    </AbsoluteFill>
  );
};
