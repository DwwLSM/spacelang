import { AbsoluteFill } from "remotion";
import { Badge } from "../components/Badge";
import { Terminal } from "../components/Terminal";
import { colors, GUTTER, lerp, MONO_FAMILY, ramp } from "../theme";
import { PIPELINE } from "../script";
import type { SceneProps } from "./types";

const smoothstep = (value: number): number => value * value * (3 - 2 * value);

/** Follow source through the compiler pipeline with deliberate stage crossfades. */
export const Scene02Pipeline: React.FC<SceneProps> = ({ frame }) => {
  const stagePosition = ramp(frame, 8, 112) * (PIPELINE.length - 1);
  const lowerIndex = Math.min(
    PIPELINE.length - 2,
    Math.floor(stagePosition),
  );
  const stageFraction = stagePosition - lowerIndex;
  const transitionProgress = Math.max(
    0,
    Math.min(1, (stageFraction - 0.25) / 0.5),
  );
  const easedTransition = smoothstep(transitionProgress);
  const stageFocus = PIPELINE.map((_, index) => {
    if (stagePosition <= 0) return index === 0 ? 1 : 0;
    if (stagePosition >= PIPELINE.length - 1) {
      return index === PIPELINE.length - 1 ? 1 : 0;
    }
    if (index === lowerIndex) {
      if (stageFraction <= 0.25) return 1;
      if (stageFraction >= 0.75) return 0;
      return 1 - easedTransition;
    }
    if (index === lowerIndex + 1) {
      if (stageFraction <= 0.25) return 0;
      if (stageFraction >= 0.75) return 1;
      return easedTransition;
    }
    return 0;
  });
  const detailFocus = PIPELINE.map((_, index) => {
    if (stagePosition <= 0) return index === 0 ? 1 : 0;
    if (stagePosition >= PIPELINE.length - 1) {
      return index === PIPELINE.length - 1 ? 1 : 0;
    }
    if (index === lowerIndex) {
      if (stageFraction <= 0.25) return 1;
      if (stageFraction >= 0.5) return 0;
      return 1 - smoothstep((stageFraction - 0.25) / 0.25);
    }
    if (index === lowerIndex + 1) {
      if (stageFraction <= 0.5) return 0;
      if (stageFraction >= 0.75) return 1;
      return smoothstep((stageFraction - 0.5) / 0.25);
    }
    return 0;
  });
  const codeReveal = ramp(frame, 8, 18);

  return (
    <AbsoluteFill
      style={{
        boxSizing: "border-box",
        display: "flex",
        flexDirection: "column",
        gap: 26,
        padding: `${GUTTER}px ${GUTTER}px 112px`,
      }}
    >
      <div style={{ display: "flex", alignItems: "stretch", gap: 10 }}>
        {PIPELINE.map((stage, index) => {
          const activeAmount = stageFocus[index];
          const appear = ramp(frame, 2 + index * 4, 14 + index * 4);
          const activeAlpha = Math.round(activeAmount * 170)
            .toString(16)
            .padStart(2, "0");
          return (
            <div
              key={stage.name}
              style={{
                alignItems: "center",
                display: "flex",
                flex: 1,
                gap: 10,
                minWidth: 0,
              }}
            >
              {index > 0 ? (
                <span
                  style={{
                    color: colors.edge,
                    fontSize: 30,
                    fontWeight: 700,
                    lineHeight: 1,
                  }}
                >
                  →
                </span>
              ) : null}
              <div
                style={{
                  background: `linear-gradient(135deg, ${colors.panel}, ${colors.cyan}${Math.round(activeAmount * 22).toString(16).padStart(2, "0")})`,
                  border: `1px solid ${colors.cyan}${activeAlpha}`,
                  borderRadius: 16,
                  boxShadow: `0 8px 26px #0004, 0 0 ${Math.round(activeAmount * 42)}px ${colors.cyan}${Math.round(activeAmount * 34).toString(16).padStart(2, "0")}`,
                  boxSizing: "border-box",
                  flex: 1,
                  minWidth: 0,
                  opacity: appear * (0.56 + activeAmount * 0.44),
                  padding: "18px 18px 16px",
                  position: "relative",
                  transform: `translateY(${-4 * activeAmount}px) scale(${1 + activeAmount * 0.018})`,
                }}
              >
                <div
                  style={{
                    background: `linear-gradient(90deg, ${colors.cyan}, ${colors.green})`,
                    borderRadius: 99,
                    height: 2,
                    left: "12%",
                    opacity: activeAmount,
                    position: "absolute",
                    right: "12%",
                    top: 0,
                    transform: `scaleX(${activeAmount})`,
                  }}
                />
                <div
                  style={{
                    color: activeAmount > 0 ? colors.cyan : colors.muted,
                    fontFamily: MONO_FAMILY,
                    fontSize: 15,
                    fontWeight: 700,
                    letterSpacing: 1.5,
                    marginBottom: 6,
                    textTransform: "uppercase",
                  }}
                >
                  {stage.step}
                </div>
                <div
                  style={{
                    color: colors.text,
                    fontFamily: MONO_FAMILY,
                    fontSize: 30,
                    fontWeight: 700,
                    whiteSpace: "nowrap",
                  }}
                >
                  {stage.name}
                </div>
              </div>
            </div>
          );
        })}
      </div>

      <Terminal
        title="compiler pipeline"
        subtitle="bounded optional .py frontend → AST → IR → .sp"
        right={<Badge tone="cyan">illustrative .py example</Badge>}
        style={{ flex: 1, minHeight: 0 }}
        bodyStyle={{
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
        }}
      >
        <div
          style={{
            height: 230,
            position: "relative",
          }}
        >
          {PIPELINE.map((stage, stageIndex) => {
            const focus = detailFocus[stageIndex];
            return (
              <div
                key={stage.name}
                style={{
                  display: "flex",
                  flexDirection: "column",
                  height: "100%",
                  justifyContent: "center",
                  left: 0,
                  opacity: codeReveal * focus,
                  position: "absolute",
                  right: 0,
                  top: 0,
                  transform: `translateY(${lerp(8, 0, focus)}px)`,
                }}
              >
                {stage.detail.map((line, lineIndex) => (
                  <div
                    key={`${stage.name}-${line}`}
                    style={{
                      color:
                        lineIndex === 0 && stage.name === "peephole"
                          ? colors.green
                          : colors.text,
                      fontFamily: MONO_FAMILY,
                      fontSize: 30,
                      lineHeight: 1.55,
                      whiteSpace: "pre",
                    }}
                  >
                    {line}
                  </div>
                ))}
              </div>
            );
          })}
        </div>
        <div
          style={{
            alignItems: "center",
            borderTop: `1px solid ${colors.edge}55`,
            display: "flex",
            gap: 14,
            marginTop: 22,
            opacity: detailFocus[3],
            paddingTop: 16,
          }}
        >
          <Badge tone="gold">illustrative example</Badge>
          <span
            style={{
              color: colors.muted,
              fontFamily: MONO_FAMILY,
              fontSize: 18,
            }}
          >
            peephole folds 20 + 22 into PUSH_INT 42 before encoding
          </span>
        </div>
      </Terminal>
    </AbsoluteFill>
  );
};
