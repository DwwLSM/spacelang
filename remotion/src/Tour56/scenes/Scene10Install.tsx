import { AbsoluteFill } from "remotion";
import { Badge } from "../components/Badge";
import { Terminal } from "../components/Terminal";
import {
  colors,
  easeOut,
  FONT_FAMILY,
  GUTTER,
  lerp,
  MONO_FAMILY,
  ramp,
} from "../theme";
import { INSTALL } from "../script";
import type { SceneProps } from "./types";

const Prompt: React.FC<{ command: string; chars: number; suffix?: string }> = ({
  command,
  chars,
  suffix,
}) => (
  <div
    style={{
      color: colors.text,
      fontFamily: MONO_FAMILY,
      fontSize: 30,
      lineHeight: 1.5,
      whiteSpace: "pre",
    }}
  >
    <span style={{ color: colors.green }}>$ </span>
    {command.slice(0, chars)}
    {chars < command.length ? <span style={{ color: colors.cyan }}>▌</span> : null}
    {suffix ? <span style={{ color: colors.muted }}>{suffix}</span> : null}
  </div>
);

const OutputLine: React.FC<{ text: string; tone?: string; style?: React.CSSProperties }> = ({
  text,
  tone = colors.muted,
  style,
}) => (
  <div
    style={{
      color: tone,
      fontFamily: MONO_FAMILY,
      fontSize: 22,
      lineHeight: 1.55,
      whiteSpace: "pre",
      ...style,
    }}
  >
    {text}
  </div>
);

/** Scene 10 (1200-1320): pip install, then start the local studio server. */
export const Scene10Install: React.FC<SceneProps> = ({ frame }) => {
  const pipChars = Math.floor(ramp(frame, 2, 26) * INSTALL.pip.length);
  const pipOutput = ramp(frame, 26, 40);
  const serveChars = Math.floor(ramp(frame, 46, 68) * INSTALL.serve.length);
  const serveOutput = ramp(frame, 68, 82);
  const urlReveal = ramp(frame, 88, 100);

  return (
    <AbsoluteFill
      style={{
        alignItems: "center",
        boxSizing: "border-box",
        display: "flex",
        padding: `${GUTTER + 4}px ${GUTTER}px 224px`,
      }}
    >
      <Terminal
        title="spacelang-opt-sp"
        subtitle="pip · install and serve"
        right={<Badge tone="green">Python 3.10+</Badge>}
        style={{ height: "100%", width: "100%" }}
        bodyStyle={{
          display: "flex",
          flexDirection: "column",
          gap: 10,
          padding: 26,
        }}
      >
        <Prompt chars={pipChars} command={INSTALL.pip} />
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: 2,
            marginBottom: 16,
            opacity: pipOutput,
            transform: `translateY(${lerp(10, 0, easeOut(pipOutput))}px)`,
          }}
        >
          {INSTALL.pipOutput.map((line, index) => (
            <OutputLine
              key={line}
              style={{ opacity: ramp(frame, 26 + index * 4, 34 + index * 4) }}
              text={line}
              tone={line.startsWith("Successfully") ? colors.green : colors.muted}
            />
          ))}
        </div>

        <Prompt chars={serveChars} command={INSTALL.serve} />
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: 2,
            opacity: serveOutput,
            transform: `translateY(${lerp(10, 0, easeOut(serveOutput))}px)`,
          }}
        >
          {INSTALL.serveOutput.map((line, index) => (
            <OutputLine
              key={line}
              style={{ opacity: ramp(frame, 68 + index * 4, 76 + index * 4) }}
              text={line}
              tone={
                index === 0
                  ? colors.cyan
                  : index === 1
                    ? colors.green
                    : colors.muted
              }
            />
          ))}
        </div>

        <div style={{ flex: 1 }} />

        <div
          style={{
            alignItems: "center",
            backgroundColor: colors.panel,
            border: `1px solid ${colors.green}88`,
            borderRadius: 14,
            boxSizing: "border-box",
            display: "flex",
            gap: 16,
            opacity: urlReveal,
            padding: "16px 20px",
            transform: `translateY(${lerp(12, 0, easeOut(urlReveal))}px)`,
          }}
        >
          <Badge tone="green">serving</Badge>
          <span
            style={{
              color: colors.green,
              fontFamily: MONO_FAMILY,
              fontSize: 28,
              fontWeight: 700,
            }}
          >
            http://127.0.0.1:8000
          </span>
          <span style={{ flex: 1 }} />
          <span
            style={{
              color: colors.muted,
              fontFamily: FONT_FAMILY,
              fontSize: 20,
            }}
          >
            a local server, a browser, no accounts
          </span>
        </div>
      </Terminal>
    </AbsoluteFill>
  );
};
