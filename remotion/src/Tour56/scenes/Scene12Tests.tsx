import { AbsoluteFill } from "remotion";
import { Badge } from "../components/Badge";
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
import { CI } from "../script";
import type { SceneProps } from "./types";

/** Show the checked-in CI matrix without implying every cell has passed. */
export const Scene12Tests: React.FC<SceneProps> = ({ frame }) => {
  const matrixReveal = ramp(frame, 18, 32);
  const differential = ramp(frame, 46, 60);

  return (
    <AbsoluteFill
      style={{
        boxSizing: "border-box",
        display: "flex",
        flexDirection: "row",
        gap: 22,
        padding: `${GUTTER - 2}px ${GUTTER}px 112px`,
      }}
    >
      <div
        style={{
          backgroundColor: colors.panel,
          border: `1px solid ${colors.green}66`,
          borderRadius: 20,
          boxSizing: "border-box",
          display: "flex",
          flex: 0.82,
          flexDirection: "column",
          gap: 14,
          justifyContent: "center",
          padding: "24px 26px",
        }}
      >
        <NumberPop
          color={colors.cyan}
          enterAt={2}
          frame={frame}
          label="differential checks"
          size={60}
          sub="same output and result required"
          value="py ↔ C++"
        />
        <div
          style={{
            borderTop: `1px solid ${colors.edge}66`,
            color: colors.muted,
            fontFamily: MONO_FAMILY,
            fontSize: 18,
            paddingTop: 12,
          }}
        >
          tests/test_differential.py
        </div>
        <div style={{ flex: 1 }} />
        <div
          style={{
            alignItems: "center",
            backgroundColor: `${colors.cyan}10`,
            border: `1px solid ${colors.cyan}55`,
            borderRadius: 12,
            display: "flex",
            gap: 10,
            opacity: differential,
            padding: "12px 14px",
            transform: `translateY(${lerp(10, 0, easeOut(differential))}px)`,
          }}
        >
          <Badge tone="cyan">parity</Badge>
          <span
            style={{
              color: colors.text,
              fontFamily: MONO_FAMILY,
              fontSize: 19,
            }}
          >
            selected programs compared
          </span>
        </div>
      </div>

      <div
        style={{
          backgroundColor: colors.panel,
          border: `1px solid ${colors.edge}`,
          borderRadius: 20,
          boxSizing: "border-box",
          display: "flex",
          flex: 1.18,
          flexDirection: "column",
          gap: 14,
          opacity: matrixReveal,
          padding: "22px 26px",
          transform: `translateY(${lerp(16, 0, easeOut(matrixReveal))}px)`,
        }}
      >
        <div
          style={{
            alignItems: "center",
            display: "flex",
            justifyContent: "space-between",
          }}
        >
          <span
            style={{
              color: colors.text,
              fontFamily: FONT_FAMILY,
              fontSize: 30,
              fontWeight: 650,
            }}
          >
            {CI.matrix}
          </span>
          <Badge tone="cyan">checked-in workflow</Badge>
        </div>

        <div
          style={{
            alignContent: "center",
            display: "grid",
            flex: 1,
            gap: 8,
            gridTemplateColumns: `150px repeat(${CI.pythons.length}, 1fr)`,
          }}
        >
          <span />
          {CI.pythons.map((version) => (
            <span
              key={version}
              style={{
                color: colors.muted,
                fontFamily: MONO_FAMILY,
                fontSize: 16,
                textAlign: "center",
              }}
            >
              {version}
            </span>
          ))}
          {CI.os.map((osName, row) => (
            <div key={osName} style={{ display: "contents" }}>
              <span
                style={{
                  alignItems: "center",
                  color: colors.text,
                  display: "flex",
                  fontFamily: MONO_FAMILY,
                  fontSize: 18,
                }}
              >
                {osName}
              </span>
              {CI.pythons.map((version, column) => {
                const cell = ramp(
                  frame,
                  20 + (row * CI.pythons.length + column) * 1.4,
                  26 + (row * CI.pythons.length + column) * 1.4,
                );
                const complete = cell >= 0.92;
                return (
                  <div
                    key={`${osName}-${version}`}
                    style={{
                      alignItems: "center",
                      backgroundColor: `${colors.cyan}${Math.round(cell * 18)
                        .toString(16)
                        .padStart(2, "0")}`,
                      border: `1px solid ${colors.cyan}${Math.round(
                        cell * 90,
                      )
                        .toString(16)
                        .padStart(2, "0")}`,
                      borderRadius: 8,
                      color: colors.cyan,
                      display: "flex",
                      fontFamily: MONO_FAMILY,
                      fontSize: 18,
                      height: 40,
                      justifyContent: "center",
                      opacity: 0.35 + 0.65 * cell,
                    }}
                  >
                    {complete ? "✓" : "•"}
                  </div>
                );
              })}
            </div>
          ))}
        </div>

        <div
          style={{
            borderTop: `1px solid ${colors.edge}55`,
            height: 1,
            marginTop: 6,
          }}
        />

        <div
          style={{
            alignItems: "center",
            display: "flex",
            gap: 14,
            opacity: differential,
          }}
        >
          <span
            style={{
              color: colors.green,
              fontFamily: MONO_FAMILY,
              fontSize: 20,
            }}
          >
            configured for pushes and pull requests
          </span>
          <span style={{ flex: 1 }} />
          <span
            style={{
              color: colors.muted,
              fontFamily: MONO_FAMILY,
              fontSize: 16,
            }}
          >
            .github/workflows/tests.yml
          </span>
        </div>

        <div
          style={{
            color: colors.muted,
            fontFamily: FONT_FAMILY,
            fontSize: 21,
            lineHeight: 1.4,
            opacity: differential,
          }}
        >
          CI runs the test suite across every configured operating-system and
          Python-version combination.
        </div>

        <div style={{ flex: 1 }} />

        <div
          style={{
            alignItems: "center",
            backgroundColor: colors.panelDark,
            border: `1px solid ${colors.edge}`,
            borderRadius: 12,
            display: "flex",
            gap: 12,
            padding: "12px 16px",
          }}
        >
          <Badge tone="cyan">configured</Badge>
          <span
            style={{
              color: colors.muted,
              fontFamily: MONO_FAMILY,
              fontSize: 17,
            }}
          >
            {CI.command} · {CI.matrix}
          </span>
        </div>
      </div>
    </AbsoluteFill>
  );
};
