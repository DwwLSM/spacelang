import { AbsoluteFill } from "remotion";
import { Badge } from "../components/Badge";
import { Terminal } from "../components/Terminal";
import {
  colors,
  easeOut,
  enter,
  lerp,
  MONO_FAMILY,
  ramp,
} from "../theme";
import { SP_TOKEN_NOTE, TOKEN_RUNS } from "../script";
import type { SceneProps } from "./types";

const formatCount = (count: number): string =>
  count >= 1000 ? count.toLocaleString("en-US") : String(count);

const runWidth = (spaces: number): number => {
  if (spaces === 0) {
    return 0;
  }
  return Math.max(
    2,
    (Math.log10(spaces + 1) / Math.log10(10001)) * 100,
  );
};

/** Show whitespace-encoded tokens in the source artifact. */
export const Scene01Source: React.FC<SceneProps> = ({ frame }) => {
  const scroll = lerp(44, -6, easeOut(ramp(frame, 0, 46)));
  const tokenPanel = enter(frame, 30);
  const highlightReveal = ramp(frame, 74, 88);
  const activeToken = Math.min(
    TOKEN_RUNS.length - 1,
    Math.floor(ramp(frame, 12, 72) * TOKEN_RUNS.length),
  );

  return (
    <AbsoluteFill
      style={{
        boxSizing: "border-box",
        display: "flex",
        flexDirection: "row",
        gap: 30,
        padding: "96px 96px 112px",
      }}
    >
      <Terminal
        title="hello.sp"
        subtitle="the artifact"
        right={<Badge tone="muted">whitespace only</Badge>}
        style={{ flex: 1.08, minWidth: 0 }}
        bodyStyle={{ display: "flex", flexDirection: "column" }}
      >
        <div style={{ flex: 1, minHeight: 0, overflow: "hidden", position: "relative" }}>
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              transform: `translateY(${scroll}px)`,
            }}
          >
            {TOKEN_RUNS.map((run, index) => {
              const rowReveal = easeOut(ramp(frame, 4 + index * 3, 17 + index * 3));
              const barReveal = easeOut(ramp(frame, 8 + index * 4, 25 + index * 4));
              const isActive = index === activeToken && frame < 78;
              return (
              <div
                key={run.token}
                style={{
                  alignItems: "center",
                  background: isActive ? `${colors.cyan}0A` : "transparent",
                  borderRadius: 6,
                  display: "flex",
                  gap: 18,
                  opacity: rowReveal,
                  padding: "7px 0",
                  transform: `translateX(${lerp(-8, 0, rowReveal)}px)`,
                }}
              >
                <span
                  style={{
                    color: colors.muted,
                    fontFamily: MONO_FAMILY,
                    fontSize: 16,
                    width: 34,
                  }}
                >
                  {String(index + 1).padStart(2, "0")}
                </span>
                <div style={{ flex: 1, height: 14, position: "relative" }}>
                  <div
                    style={{
                      backgroundColor:
                        run.spaces === 0 ? "transparent" : `${colors.cyan}10`,
                      backgroundImage: `radial-gradient(circle, ${colors.cyan}CC 1.5px, transparent 1.6px)`,
                      backgroundSize: "9px 9px",
                      border:
                        run.spaces === 0
                          ? `1px dashed ${colors.edge}`
                          : `1px solid ${colors.cyan}33`,
                      borderRadius: 4,
                      boxSizing: "border-box",
                      height: 14,
                      width: `${runWidth(run.spaces) * barReveal}%`,
                      boxShadow: isActive ? `0 0 12px ${colors.cyan}44` : "none",
                    }}
                  />
                </div>
                <span
                  style={{
                    color: run.spaces === 10000 ? colors.gold : colors.cyan,
                    fontFamily: MONO_FAMILY,
                    fontSize: 17,
                    textAlign: "right",
                    width: 112,
                  }}
                >
                  {run.spaces === 0 ? "empty" : `${formatCount(run.spaces)} sp`}
                </span>
                <span
                  style={{
                    color: colors.muted,
                    fontFamily: MONO_FAMILY,
                    fontSize: 15,
                    width: 96,
                  }}
                >
                  {run.token}
                </span>
              </div>
              );
            })}
          </div>
        </div>
        <div
          style={{
            alignItems: "center",
            borderTop: `1px solid ${colors.edge}55`,
            display: "flex",
            gap: 10,
            opacity: highlightReveal,
            paddingTop: 12,
          }}
        >
          <Badge tone="gold">decoded</Badge>
          <span
            style={{
              color: colors.muted,
              fontFamily: MONO_FAMILY,
              fontSize: 17,
            }}
          >
            {SP_TOKEN_NOTE} · 10,000 spaces is one function id
          </span>
        </div>
      </Terminal>

      <div
        style={{
          flex: 1,
          minWidth: 0,
          opacity: tokenPanel.opacity,
          transform: tokenPanel.transform,
        }}
      >
        <Terminal
          title="decoder"
          subtitle="count spaces per line → integer tokens"
          right={<Badge tone="green">decoder.py</Badge>}
          style={{ height: "100%" }}
          bodyStyle={{ display: "flex", flexDirection: "column", gap: 0 }}
        >
          <div
            style={{
              color: colors.muted,
              fontFamily: MONO_FAMILY,
              fontSize: 15,
              letterSpacing: 1,
              marginBottom: 8,
            }}
          >
            line · spaces → token
          </div>
          {TOKEN_RUNS.map((run, index) => {
            const reveal = ramp(frame, 34 + index * 4, 44 + index * 4);
            return (
              <div
                key={run.token}
                style={{
                  alignItems: "baseline",
                  borderBottom: `1px solid ${colors.edge}33`,
                  display: "flex",
                  gap: 12,
                  opacity: reveal,
                  padding: "6px 0",
                }}
              >
                <span
                  style={{
                    color: colors.muted,
                    fontFamily: MONO_FAMILY,
                    fontSize: 14,
                    width: 26,
                  }}
                >
                  {String(index + 1).padStart(2, "0")}
                </span>
                <span
                  style={{
                    color: colors.gold,
                    fontFamily: MONO_FAMILY,
                    fontSize: 20,
                    width: 128,
                  }}
                >
                  {formatCount(run.spaces)} spaces
                </span>
                <span style={{ color: colors.muted, fontSize: 18 }}>→</span>
                <span
                  style={{
                    color: colors.text,
                    fontFamily: MONO_FAMILY,
                    fontSize: 21,
                    fontWeight: 700,
                  }}
                >
                  {run.token}
                </span>
                <span
                  style={{
                    color: colors.muted,
                    fontFamily: MONO_FAMILY,
                    fontSize: 14,
                    marginLeft: "auto",
                  }}
                >
                  {run.note}
                </span>
              </div>
            );
          })}
        </Terminal>
      </div>
    </AbsoluteFill>
  );
};
