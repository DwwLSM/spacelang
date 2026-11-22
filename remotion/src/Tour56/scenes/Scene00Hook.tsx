import { AbsoluteFill } from "remotion";
import { Badge } from "../components/Badge";
import {
  colors,
  easeOut,
  FONT_FAMILY,
  lerp,
  MONO_FAMILY,
  ramp,
} from "../theme";
import type { SceneProps } from "./types";

const SPACE_COUNT = 17;

/** Opening hook: one whitespace token becomes an instruction and a result. */
export const Scene00Hook: React.FC<SceneProps> = ({ frame }) => {
  const tokenReveal = ramp(frame, 18, 30);
  const resultReveal = ramp(frame, 30, 44);
  const flowReveal = ramp(frame, 24, 44);
  const flowEase = easeOut(flowReveal);
  const headline = "The spaces are the code.".split(" ");

  return (
    <AbsoluteFill
      style={{
        alignItems: "center",
        boxSizing: "border-box",
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
        padding: "52px 96px 112px",
      }}
    >
      <div
        style={{
          color: colors.cyan,
          fontFamily: MONO_FAMILY,
          fontSize: 18,
          fontWeight: 700,
          letterSpacing: 4,
          marginBottom: 18,
          textTransform: "uppercase",
        }}
      >
        SpaceLang · hello.sp
      </div>
      <div
        style={{
          alignItems: "center",
          color: colors.text,
          display: "flex",
          flexWrap: "wrap",
          fontFamily: FONT_FAMILY,
          fontSize: 72,
          fontWeight: 750,
          gap: "0 16px",
          justifyContent: "center",
          letterSpacing: -2,
          lineHeight: 1.08,
          textAlign: "center",
        }}
      >
        {headline.map((word, index) => {
          const reveal = easeOut(ramp(frame, 7 + index * 5, 20 + index * 5));
          return (
            <span
              key={word}
              style={{
                display: "inline-block",
                opacity: reveal,
                transform: `translateY(${lerp(22, 0, reveal)}px)`,
              }}
            >
              {word}
            </span>
          );
        })}
      </div>
      <div
        style={{
          background: `linear-gradient(90deg, transparent, ${colors.cyan}, ${colors.green}, transparent)`,
          borderRadius: 99,
          height: 2,
          marginTop: 22,
          opacity: ramp(frame, 30, 44),
          width: `${ramp(frame, 30, 44) * 280}px`,
        }}
      />

      <div
        style={{
          alignItems: "center",
          backgroundColor: `rgba(16, 35, 42, ${0.92 + flowEase * 0.08})`,
          border: `1px solid ${colors.cyan}${Math.round(70 + flowEase * 70).toString(16).padStart(2, "0")}`,
          borderRadius: 22,
          boxSizing: "border-box",
          display: "flex",
          gap: 30,
          justifyContent: "center",
          marginTop: 24,
          maxWidth: 1320,
          opacity: easeOut(ramp(frame, 24, 42)),
          padding: "28px 42px",
          transform: `translateY(${lerp(18, 0, easeOut(ramp(frame, 24, 42)))}px)`,
          width: "100%",
          boxShadow: `0 24px 70px #0005, 0 0 ${28 * flowEase}px ${colors.cyan}18`,
        }}
      >
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <Badge tone="cyan">17 spaces</Badge>
          <div style={{ display: "flex", gap: 7 }}>
            {Array.from({ length: SPACE_COUNT }, (_, index) => {
              const appear = ramp(frame, 4 + index * 0.8, 12 + index * 0.8);
              return (
                <span
                  key={index}
                  style={{
                    backgroundColor: colors.cyan,
                    borderRadius: 99,
                    height: 12,
                    opacity: appear,
                    transform: `scale(${0.5 + 0.5 * appear})`,
                    width: 12,
                  }}
                />
              );
            })}
          </div>
          <span
            style={{
              color: colors.muted,
              fontFamily: MONO_FAMILY,
              fontSize: 16,
            }}
          >
            one encoded integer
          </span>
        </div>

        <span
          style={{
            color: colors.edge,
            fontFamily: FONT_FAMILY,
            fontSize: 48,
            opacity: tokenReveal,
            transform: `translateX(${lerp(-8, 0, easeOut(tokenReveal))}px)`,
          }}
        >
          →
        </span>

        <div
          style={{
            alignItems: "center",
            display: "flex",
            flexDirection: "column",
            gap: 10,
            opacity: tokenReveal,
            transform: `translateY(${lerp(10, 0, easeOut(tokenReveal))}px)`,
          }}
        >
          <span
            style={{
              color: colors.gold,
              fontFamily: MONO_FAMILY,
              fontSize: 58,
              fontWeight: 750,
            }}
          >
            DEF
          </span>
          <span
            style={{
              color: colors.muted,
              fontFamily: MONO_FAMILY,
              fontSize: 16,
            }}
          >
            instruction
          </span>
        </div>

        <div
          style={{
            borderLeft: `1px solid ${colors.edge}`,
            height: 80,
            margin: "0 6px",
          }}
        />

        <div
          style={{
            alignItems: "center",
            display: "flex",
            flexDirection: "column",
            gap: 8,
            minWidth: 170,
            opacity: resultReveal,
            transform: `translateY(${lerp(12, 0, easeOut(resultReveal))}px)`,
          }}
        >
          <span
            style={{
              color: colors.muted,
              fontFamily: MONO_FAMILY,
              fontSize: 17,
            }}
          >
            22 × 2
          </span>
          <span
            style={{
              color: colors.green,
              fontFamily: MONO_FAMILY,
              fontSize: 64,
              fontWeight: 750,
              lineHeight: 1,
            }}
          >
            44
          </span>
        </div>
      </div>
    </AbsoluteFill>
  );
};
