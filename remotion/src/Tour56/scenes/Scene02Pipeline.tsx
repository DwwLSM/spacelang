import { AbsoluteFill } from "remotion";
import { Badge } from "../components/Badge";
import { Terminal } from "../components/Terminal";
import { colors, easeOut, GUTTER, lerp, MONO_FAMILY, ramp } from "../theme";
import { PIPELINE } from "../script";
import type { SceneProps } from "./types";

/** Scene 02 (240-360): the compiler pipeline, one stage at a time. */
export const Scene02Pipeline: React.FC<SceneProps> = ({ frame }) => {
  const stageProgress = ramp(frame, 10, 104);
  const rawStage = Math.floor(stageProgress * PIPELINE.length);
  const stageIndex = Math.min(PIPELINE.length - 1, Math.max(0, rawStage));
  const active = PIPELINE[stageIndex];
  const codeReveal = ramp(frame, 12, 24);

  return (
    <AbsoluteFill
      style={{
        boxSizing: "border-box",
        display: "flex",
        flexDirection: "column",
        gap: 26,
        padding: `${GUTTER}px ${GUTTER}px 232px`,
      }}
    >
      <div style={{ display: "flex", alignItems: "stretch", gap: 10 }}>
        {PIPELINE.map((stage, index) => {
          const isActive = index === stageIndex;
          const appear = ramp(frame, 2 + index * 4, 14 + index * 4);
          return (
            <div
              key={stage.name}
              style={{ alignItems: "center", display: "flex", flex: 1, gap: 10, minWidth: 0 }}
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
                  backgroundColor: isActive ? `${colors.cyan}16` : colors.panel,
                  border: `1px solid ${isActive ? `${colors.cyan}AA` : colors.edge}`,
                  borderRadius: 16,
                  boxShadow: isActive ? `0 0 42px ${colors.cyan}22` : "none",
                  boxSizing: "border-box",
                  flex: 1,
                  minWidth: 0,
                  opacity: appear * (isActive ? 1 : 0.62),
                  padding: "18px 18px 16px",
                  transform: isActive ? "translateY(-4px)" : "none",
                }}
              >
                <div
                  style={{
                    color: isActive ? colors.cyan : colors.muted,
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
        title={active.name}
        subtitle={`stage ${stageIndex + 1} / ${PIPELINE.length} · ${active.step}`}
        right={
          <Badge tone={active.name === ".sp" ? "green" : "cyan"}>
            {active.name === ".sp" ? "spaces" : "deterministic"}
          </Badge>
        }
        style={{ flex: 1, minHeight: 0 }}
        accent={active.name === ".sp" ? colors.green : colors.cyan}
        bodyStyle={{ display: "flex", flexDirection: "column", justifyContent: "center" }}
      >
        <div
          style={{
            opacity: codeReveal,
            transform: `translateY(${lerp(14, 0, easeOut(codeReveal))}px)`,
          }}
        >
          {active.detail.map((line, index) => (
            <div
              key={`${active.name}-${line}`}
              style={{
                color:
                  index === 0 && active.name === "peephole"
                    ? colors.green
                    : colors.text,
                fontFamily: MONO_FAMILY,
                fontSize: 30,
                lineHeight: 1.55,
                opacity: ramp(frame, 8 + index * 2, 18 + index * 2),
                whiteSpace: "pre",
              }}
            >
              {line}
            </div>
          ))}
        </div>
        <div
          style={{
            alignItems: "center",
            borderTop: `1px solid ${colors.edge}55`,
            display: "flex",
            gap: 14,
            marginTop: 22,
            opacity: ramp(frame, 88, 100),
            paddingTop: 16,
          }}
        >
          <Badge tone="gold">print(20 + 22)</Badge>
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
