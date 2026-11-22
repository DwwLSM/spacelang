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

const InfoRow: React.FC<{
  label: string;
  value: string;
  delay: number;
  frame: number;
}> = ({ label, value, delay, frame }) => {
  const reveal = ramp(frame, delay, delay + 12);
  return (
    <div
      style={{
        alignItems: "baseline",
        borderBottom: `1px solid ${colors.edge}88`,
        display: "flex",
        gap: 16,
        opacity: reveal,
        padding: "9px 0",
        transform: `translateY(${lerp(8, 0, easeOut(reveal))}px)`,
      }}
    >
      <span
        style={{
          color: colors.muted,
          flex: "0 0 118px",
          fontFamily: FONT_FAMILY,
          fontSize: 17,
        }}
      >
        {label}
      </span>
      <span
        style={{
          color: colors.text,
          fontFamily: MONO_FAMILY,
          fontSize: 18,
        }}
      >
        {value}
      </span>
    </div>
  );
};

/** Show the real server command, page route, and browser-side execution path. */
export const Scene10Install: React.FC<SceneProps> = ({ frame }) => {
  const chars = Math.floor(ramp(frame, 0, 16) * INSTALL.serve.length);
  const commandReveal = ramp(frame, 0, 16);
  const routeReveal = ramp(frame, 12, 26);
  const filesReveal = ramp(frame, 24, 38);
  const executionReveal = ramp(frame, 48, 60);
  const flowProgress = ramp(frame, 18, 68);
  const flowEase = easeOut(flowProgress);

  return (
    <AbsoluteFill
      style={{
        alignItems: "center",
        boxSizing: "border-box",
        display: "flex",
        padding: `${GUTTER + 4}px ${GUTTER}px 112px`,
      }}
    >
      <Terminal
        title="OPT_SP — local debugger"
        subtitle="server and browser request flow"
        right={<Badge tone="green">{INSTALL.host}</Badge>}
        style={{ height: "100%", width: "100%" }}
        bodyStyle={{
          display: "flex",
          flexDirection: "column",
          gap: 18,
          padding: 24,
        }}
      >
        <div
          style={{
            background: colors.panelDark,
            border: `1px solid ${colors.edge}`,
            borderRadius: 12,
            opacity: commandReveal,
            padding: "16px 20px",
          }}
        >
          <div
            style={{
              color: colors.text,
              fontFamily: MONO_FAMILY,
              fontSize: 26,
              lineHeight: 1.5,
              whiteSpace: "pre",
            }}
          >
            <span style={{ color: colors.green }}>$ </span>
            {INSTALL.serve.slice(0, chars)}
            {chars < INSTALL.serve.length ? (
              <span style={{ color: colors.cyan }}>▌</span>
            ) : null}
          </div>
          <div
            style={{
              color: colors.muted,
              fontFamily: FONT_FAMILY,
              fontSize: 17,
              marginTop: 7,
            }}
          >
            {INSTALL.server} · {INSTALL.host} · {INSTALL.launch}
          </div>
        </div>

        <div
          style={{
            display: "flex",
            flex: 1,
            gap: 20,
            minHeight: 0,
            position: "relative",
          }}
        >
          <div
            style={{
              background: `linear-gradient(180deg, transparent, ${colors.cyan}, transparent)`,
              borderRadius: 99,
              height: `${flowEase * 100}%`,
              left: "calc(42% - 10px)",
              opacity: flowProgress,
              position: "absolute",
              top: `${(1 - flowEase) * 18}%`,
              width: 3,
            }}
          />
          <section
            style={{
              background: colors.panel,
              border: `1px solid ${colors.edge}`,
              borderRadius: 14,
              boxSizing: "border-box",
              flex: "0 0 42%",
              opacity: routeReveal,
              padding: "18px 22px",
              transform: `translateY(${lerp(10, 0, easeOut(routeReveal))}px)`,
            }}
          >
            <div
              style={{
                color: colors.cyan,
                fontFamily: MONO_FAMILY,
                fontSize: 19,
                fontWeight: 700,
                marginBottom: 8,
              }}
            >
              HTTP routes
            </div>
            <InfoRow frame={frame} delay={22} label="Browser" value={INSTALL.launch} />
            <InfoRow frame={frame} delay={26} label="Studio" value={INSTALL.studio} />
            <div
              style={{
                color: colors.muted,
                fontFamily: FONT_FAMILY,
                fontSize: 16,
                marginTop: 12,
              }}
            >
              The studio page includes its HTML partials.
            </div>
          </section>

          <section
            style={{
              background: colors.panel,
              border: `1px solid ${colors.edge}`,
              borderRadius: 14,
              boxSizing: "border-box",
              display: "flex",
              flex: 1,
              flexDirection: "column",
              minWidth: 0,
              opacity: filesReveal,
              padding: "18px 22px",
              transform: `translateY(${lerp(10, 0, easeOut(filesReveal))}px)`,
            }}
          >
            <div
              style={{
                color: colors.cyan,
                fontFamily: MONO_FAMILY,
                fontSize: 19,
                fontWeight: 700,
                marginBottom: 8,
              }}
            >
              Browser loads
            </div>
            {INSTALL.files.map((file, index) => (
              <InfoRow
                key={file}
                delay={30 + index * 2}
                frame={frame}
                label={index === 0 ? "CSS" : index === 1 ? "CSS" : "JavaScript"}
                value={file}
              />
            ))}
            {INSTALL.kernel.map((file) => (
              <InfoRow
                key={file}
                delay={38}
                frame={frame}
                label="Runtime"
                value={file}
              />
            ))}
            <div
              style={{
                alignItems: "center",
                borderTop: `1px solid ${colors.edge}88`,
                display: "flex",
                gap: 12,
                marginTop: "auto",
                opacity: executionReveal,
                paddingTop: 14,
              }}
            >
              <Badge tone="green">in browser</Badge>
              <span
                style={{
                  color: colors.text,
                  fontFamily: FONT_FAMILY,
                  fontSize: 18,
                }}
              >
                {INSTALL.behavior}
              </span>
            </div>
          </section>
        </div>
      </Terminal>
    </AbsoluteFill>
  );
};
