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
import { HEALTH } from "../script";
import type { SceneProps } from "./types";

/** Scene 09 (1080-1200): the static-asset health check, three green panels. */
export const Scene09Health: React.FC<SceneProps> = ({ frame }) => {
  const typed = Math.floor(ramp(frame, 2, 22) * HEALTH.url.length);
  const jsonReveal = ramp(frame, 28, 40);
  const noteReveal = ramp(frame, 88, 100);

  return (
    <AbsoluteFill
      style={{
        alignItems: "center",
        boxSizing: "border-box",
        display: "flex",
        padding: `${GUTTER + 6}px ${GUTTER}px 224px`,
      }}
    >
      <Terminal
        title="OPT_SP — static assets"
        subtitle="GET /__opt_sp/health"
        right={
          <>
            <Badge tone="green">loopback only</Badge>
            <Badge tone="muted">assets 4 / 4</Badge>
          </>
        }
        style={{ height: "100%", width: "100%" }}
        bodyStyle={{
          display: "flex",
          flexDirection: "column",
          gap: 18,
          padding: 22,
        }}
      >
        <div
          style={{
            alignItems: "center",
            backgroundColor: colors.panel,
            border: `1px solid ${colors.edge}`,
            borderRadius: 12,
            display: "flex",
            gap: 14,
            height: 54,
            padding: "0 18px",
          }}
        >
          <Badge tone="muted">GET</Badge>
          <span
            style={{
              color: colors.cyan,
              fontFamily: MONO_FAMILY,
              fontSize: 22,
            }}
          >
            http://{HEALTH.url.slice(0, typed)}
            {typed < HEALTH.url.length ? (
              <span style={{ color: colors.text }}>▌</span>
            ) : null}
          </span>
          <span style={{ flex: 1 }} />
          <span
            style={{
              color: colors.green,
              fontFamily: MONO_FAMILY,
              fontSize: 20,
              opacity: jsonReveal,
            }}
          >
            {"{ "}ok: true{" }"}
          </span>
        </div>

        <div style={{ display: "flex", flex: 1, gap: 18, minHeight: 0 }}>
          {HEALTH.panels.map((panel, index) => {
            const pending = ramp(frame, 8 + index * 4, 18 + index * 4);
            const green = frame >= 36 + index * 16;
            return (
              <div
                key={panel.title}
                style={{
                  backgroundColor: green ? `${colors.green}0E` : colors.panel,
                  border: `1px solid ${green ? `${colors.green}AA` : colors.edge}`,
                  borderRadius: 18,
                  boxSizing: "border-box",
                  display: "flex",
                  flex: 1,
                  flexDirection: "column",
                  gap: 14,
                  opacity: pending,
                  padding: "22px 22px",
                  transform: `translateY(${lerp(14, 0, easeOut(pending))}px)`,
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
                      fontFamily: MONO_FAMILY,
                      fontSize: 22,
                      fontWeight: 700,
                    }}
                  >
                    {panel.title}
                  </span>
                  <Badge tone={green ? "green" : "gold"}>
                    {green ? "present" : "checking"}
                  </Badge>
                </div>
                <div style={{ flex: 1 }}>
                  {panel.files.map((file) => (
                    <div
                      key={file}
                      style={{
                        color: green ? colors.green : colors.muted,
                        fontFamily: MONO_FAMILY,
                        fontSize: 17,
                        lineHeight: 1.7,
                        whiteSpace: "pre-wrap",
                        wordBreak: "break-all",
                      }}
                    >
                      {green ? "✓ " : "· "}
                      {file}
                    </div>
                  ))}
                  <div
                    style={{
                      color: colors.muted,
                      fontFamily: FONT_FAMILY,
                      fontSize: 18,
                      marginTop: 12,
                    }}
                  >
                    {panel.meta}
                  </div>
                </div>
                <div
                  style={{
                    borderTop: `1px solid ${colors.edge}55`,
                    color: colors.muted,
                    fontFamily: MONO_FAMILY,
                    fontSize: 15,
                    paddingTop: 12,
                  }}
                >
                  {green ? "served as a plain static file" : "asset self-check"}
                </div>
              </div>
            );
          })}
        </div>

        <div
          style={{
            alignItems: "center",
            display: "flex",
            gap: 14,
            opacity: noteReveal,
          }}
        >
          <Badge tone="green">browser side</Badge>
          <span
            style={{
              color: colors.muted,
              fontFamily: FONT_FAMILY,
              fontSize: 22,
            }}
          >
            {HEALTH.note}
          </span>
          <span style={{ flex: 1 }} />
          <span
            style={{
              color: colors.muted,
              fontFamily: MONO_FAMILY,
              fontSize: 17,
            }}
          >
            python tools/build_static.py
          </span>
        </div>
      </Terminal>
    </AbsoluteFill>
  );
};
