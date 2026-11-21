import { AbsoluteFill } from "remotion";
import { Badge, type BadgeTone } from "../components/Badge";
import { NumberPop } from "../components/NumberPop";
import {
  colors,
  easeOut,
  FONT_FAMILY,
  GUTTER,
  lerp,
  MONO_FAMILY,
  ramp,
} from "../theme";
import { ENGINES } from "../script";
import type { SceneProps } from "./types";

const barShare = (figure: string): number => {
  if (figure === "32×") {
    return 100;
  }
  if (figure === "8×") {
    return 34;
  }
  if (figure === "1×") {
    return 8;
  }
  return 3;
};

/** Scene 08 (960-1080): four engines side by side. */
export const Scene08Engines: React.FC<SceneProps> = ({ frame }) => {
  const bars = ramp(frame, 34, 78);
  const footer = ramp(frame, 88, 100);

  return (
    <AbsoluteFill
      style={{
        boxSizing: "border-box",
        display: "flex",
        flexDirection: "column",
        gap: 22,
        padding: `${GUTTER - 4}px ${GUTTER}px 224px`,
      }}
    >
      <div
        style={{
          alignItems: "baseline",
          display: "flex",
          gap: 18,
          opacity: ramp(frame, 0, 12),
        }}
      >
        <span
          style={{
            color: colors.text,
            fontFamily: FONT_FAMILY,
            fontSize: 34,
            fontWeight: 650,
          }}
        >
          Four runtimes execute .sp artifacts.
        </span>
        <span
          style={{
            color: colors.muted,
            fontFamily: MONO_FAMILY,
            fontSize: 19,
          }}
        >
          one instruction stream, independent implementations
        </span>
      </div>

      <div style={{ display: "flex", flex: 1, gap: 20, minHeight: 0 }}>
        {ENGINES.map((engine, index) => {
          const appear = ramp(frame, 4 + index * 5, 18 + index * 5);
          const tone = engine.tone as BadgeTone;
          const color = colors[tone];
          return (
            <div
              key={engine.name}
              style={{
                backgroundColor: colors.panel,
                border: `1px solid ${color}66`,
                borderRadius: 20,
                boxSizing: "border-box",
                display: "flex",
                flex: 1,
                flexDirection: "column",
                gap: 12,
                justifyContent: "space-between",
                opacity: appear,
                padding: "22px 22px 20px",
                transform: `translateY(${lerp(24, 0, easeOut(appear))}px)`,
              }}
            >
              <div
                style={{
                  alignItems: "center",
                  display: "flex",
                  height: 30,
                }}
              >
                <Badge tone={tone}>{`engine ${index + 1}`}</Badge>
              </div>
              <div
                style={{
                  color: colors.text,
                  fontFamily: MONO_FAMILY,
                  fontSize: 22,
                  fontWeight: 700,
                  lineHeight: 1.3,
                  minHeight: 58,
                  wordBreak: "break-all",
                }}
              >
                {engine.name}
              </div>
              <div
                style={{
                  color: colors.muted,
                  fontFamily: FONT_FAMILY,
                  fontSize: 20,
                }}
              >
                {engine.kind}
              </div>
              <Badge tone="muted" style={{ alignSelf: "flex-start" }}>
                {engine.tag}
              </Badge>
              <NumberPop
                color={color}
                enterAt={34 + index * 8}
                frame={frame}
                size={engine.figure.length > 3 ? 62 : 96}
                sub={engine.figureNote}
                value={engine.figure}
              />
              <div
                style={{
                  backgroundColor: "#183139",
                  borderRadius: 99,
                  height: 8,
                  overflow: "hidden",
                }}
              >
                <div
                  style={{
                    backgroundColor: color,
                    borderRadius: 99,
                    height: "100%",
                    width: `${barShare(engine.figure) * bars}%`,
                  }}
                />
              </div>
              <div
                style={{
                  color: colors.muted,
                  fontFamily: MONO_FAMILY,
                  fontSize: 15,
                }}
              >
                {engine.detail}
              </div>
            </div>
          );
        })}
      </div>

      <div
        style={{
          alignItems: "center",
          backgroundColor: colors.panelDark,
          border: `1px solid ${colors.edge}`,
          borderRadius: 14,
          display: "flex",
          gap: 16,
          height: 62,
          opacity: footer,
          padding: "0 20px",
        }}
      >
        <Badge tone="cyan">53 opcodes</Badge>
        <span
          style={{
            color: colors.muted,
            fontFamily: MONO_FAMILY,
            fontSize: 18,
          }}
        >
          every runtime executes the same deterministic instruction stream
        </span>
        <span style={{ flex: 1 }} />
        <span
          style={{
            color: colors.muted,
            fontFamily: MONO_FAMILY,
            fontSize: 17,
          }}
        >
          spacelang/ir.py
        </span>
      </div>
    </AbsoluteFill>
  );
};
