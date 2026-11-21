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
import { BOOTSTRAP, bootstrap } from "../script";
import type { SceneProps } from "./types";

const toneColor = (): string => {
  if (bootstrap.tone === "green") {
    return colors.green;
  }
  if (bootstrap.tone === "gold") {
    return colors.gold;
  }
  return colors.red;
};

/** Scene 11 (1320-1440): the native compiler bootstrap chain. */
export const Scene11Bootstrap: React.FC<SceneProps> = ({ frame }) => {
  const chainReveal = ramp(frame, -8, 4);
  const equationReveal = ramp(frame, 2, 16);
  const statusReveal = ramp(frame, 44, 58);
  const accent = toneColor();

  return (
    <AbsoluteFill
      style={{
        boxSizing: "border-box",
        display: "flex",
        flexDirection: "column",
        gap: 20,
        padding: `${GUTTER - 12}px ${GUTTER}px 224px`,
      }}
    >
      <div
        style={{
          alignItems: "center",
          display: "flex",
          gap: 16,
          justifyContent: "center",
          opacity: chainReveal,
          transform: `translateY(${lerp(12, 0, easeOut(chainReveal))}px)`,
        }}
      >
        {BOOTSTRAP.chain.map((item, index) => (
          <div key={item} style={{ alignItems: "center", display: "flex", gap: 16 }}>
            {index > 0 ? (
              <span style={{ color: colors.edge, fontSize: 30 }}>→</span>
            ) : null}
            <span
              style={{
                backgroundColor: index === 2 ? `${accent}1A` : colors.panel,
                border: `1px solid ${index === 2 ? accent : colors.edge}`,
                borderRadius: 14,
                color: index === 2 ? accent : colors.text,
                fontFamily: MONO_FAMILY,
                fontSize: 28,
                fontWeight: 700,
                padding: "12px 22px",
              }}
            >
              {item}
            </span>
          </div>
        ))}
      </div>

      <div style={{ display: "flex", flex: 1, gap: 20, minHeight: 0 }}>
        {BOOTSTRAP.stages.map((stage, index) => {
          const appear = 0.5 + 0.5 * ramp(frame, index * 8 - 6, index * 8 + 6);
          const isFixedPoint = index === 2;
          return (
            <div
              key={stage.tag}
              style={{
                backgroundColor: colors.panel,
                border: `1px solid ${
                  isFixedPoint ? `${accent}88` : colors.edge
                }`,
                borderRadius: 18,
                boxSizing: "border-box",
                display: "flex",
                flex: 1,
                flexDirection: "column",
                gap: 10,
                opacity: appear,
                padding: "20px 22px",
              }}
            >
              <div style={{ alignItems: "center", display: "flex", gap: 10 }}>
                <Badge tone={isFixedPoint ? bootstrap.tone : "muted"}>
                  {stage.tag}
                </Badge>
                {isFixedPoint ? (
                  <span
                    style={{
                      color: accent,
                      fontFamily: MONO_FAMILY,
                      fontSize: 15,
                      opacity: statusReveal,
                    }}
                  >
                    self-compiled
                  </span>
                ) : null}
              </div>
              <div
                style={{
                  color: colors.text,
                  fontFamily: FONT_FAMILY,
                  fontSize: 30,
                  fontWeight: 650,
                }}
              >
                {stage.title}
              </div>
              <div
                style={{
                  color: colors.cyan,
                  fontFamily: MONO_FAMILY,
                  fontSize: 18,
                  lineHeight: 1.5,
                }}
              >
                {stage.command}
              </div>
              <div style={{ flex: 1 }} />
              <div
                style={{
                  backgroundColor: colors.panelDark,
                  border: `1px solid ${colors.edge}`,
                  borderRadius: 10,
                  padding: "10px 12px",
                }}
              >
                <div
                  style={{
                    color: colors.muted,
                    fontFamily: MONO_FAMILY,
                    fontSize: 16,
                  }}
                >
                  {stage.artifact}
                </div>
                <div
                  style={{
                    color: isFixedPoint ? accent : colors.text,
                    fontFamily: MONO_FAMILY,
                    fontSize: 15,
                    marginTop: 4,
                  }}
                >
                  {stage.size}
                </div>
              </div>
              <div
                style={{
                  borderTop: `1px solid ${colors.edge}55`,
                  color: colors.muted,
                  fontFamily: MONO_FAMILY,
                  fontSize: 16,
                  paddingTop: 10,
                }}
              >
                {stage.note}
              </div>
            </div>
          );
        })}
      </div>

      <div
        style={{
          alignItems: "center",
          backgroundColor: colors.panelDark,
          border: `1px solid ${accent}66`,
          borderRadius: 18,
          boxSizing: "border-box",
          display: "flex",
          gap: 22,
          opacity: equationReveal,
          padding: "16px 26px",
          transform: `translateY(${lerp(12, 0, easeOut(equationReveal))}px)`,
        }}
      >
        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          {BOOTSTRAP.equation.map((line) => (
            <span
              key={line}
              style={{
                color: accent,
                fontFamily: MONO_FAMILY,
                fontSize: 22,
                fontWeight: 700,
              }}
            >
              {line}
            </span>
          ))}
        </div>
        <span style={{ flex: 1 }} />
        <div
          style={{
            alignItems: "center",
            display: "flex",
            gap: 14,
            opacity: statusReveal,
          }}
        >
          <Badge solid tone={bootstrap.tone}>
            {bootstrap.tone === "green"
              ? "fixed point"
              : bootstrap.tone === "gold"
                ? "self-hosting"
                : "partial"}
          </Badge>
          <span
            style={{
              color: colors.text,
              fontFamily: MONO_FAMILY,
              fontSize: 22,
            }}
          >
            {bootstrap.small}
          </span>
        </div>
      </div>
    </AbsoluteFill>
  );
};
