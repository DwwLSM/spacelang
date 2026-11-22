import { AbsoluteFill } from "remotion";
import { Badge, type BadgeTone } from "../components/Badge";
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

/** Four runtime implementations, with their roles instead of ungrounded speedups. */
export const Scene08Engines: React.FC<SceneProps> = ({ frame }) => {
  const footer = ramp(frame, 36, 48);

  return (
    <AbsoluteFill
      style={{
        boxSizing: "border-box",
        display: "flex",
        flexDirection: "column",
        gap: 22,
        padding: `${GUTTER - 4}px ${GUTTER}px 96px`,
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
          Four runtime paths. One language.
        </span>
        <span
          style={{
            color: colors.muted,
            fontFamily: MONO_FAMILY,
            fontSize: 19,
          }}
        >
          shared instruction set · experimental native implementations
        </span>
      </div>

      <div style={{ display: "flex", flex: 1, gap: 20, minHeight: 0 }}>
        {ENGINES.map((engine, index) => {
          const appear = ramp(frame, 4 + index * 5, 18 + index * 5);
          const roleReveal = ramp(frame, 34 + index * 8, 48 + index * 8);
          const roleEase = easeOut(roleReveal);
          const popFrame = frame - (34 + index * 8);
          const popProgress = Math.min(1, Math.max(0, popFrame / 14));
          const popEase = popProgress * popProgress * (3 - 2 * popProgress);
          const settleProgress = Math.min(
            1,
            Math.max(0, (popFrame - 14) / 14),
          );
          const settleEase =
            settleProgress * settleProgress * (3 - 2 * settleProgress);
          const popScale =
            popFrame < 0
              ? 0.58
              : popFrame <= 14
                ? lerp(0.58, 1.22, popEase)
                : lerp(1.22, 1, settleEase);
          const popFlash =
            popFrame >= 0 && popFrame <= 14
              ? Math.sin((popFrame / 14) * Math.PI)
              : 0;
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
                  overflowWrap: "anywhere",
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
              <div
                style={{
                  alignItems: "center",
                  display: "flex",
                  flexDirection: "column",
                  gap: 7,
                  opacity: roleReveal,
                  transform: `scale(${popScale}) translateY(${lerp(18, 0, roleEase)}px)`,
                  width: "100%",
                }}
              >
                <div
                  style={{
                    color,
                    fontFamily: FONT_FAMILY,
                    fontSize: engine.role.length > 8 ? 42 : 50,
                    fontWeight: 750,
                    letterSpacing: 0,
                    lineHeight: 1,
                    textAlign: "center",
                    filter: `brightness(${1 + popFlash * 1.8})`,
                    textShadow: `0 0 ${24 * roleEase + 32 * popFlash}px ${color}ff, 0 0 ${70 * popFlash}px ${color}99, 0 5px 22px #000b`,
                  }}
                >
                  {engine.role}
                </div>
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
          one instruction set · independent runtime implementations
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
