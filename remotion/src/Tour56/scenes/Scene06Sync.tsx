import { AbsoluteFill } from "remotion";
import { Badge } from "../components/Badge";
import { Pane } from "../components/Pane";
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
import { STALE, SYNC, STUDIO } from "../script";
import type { SceneProps } from "./types";

/** The model proposes a mirror; local verification decides whether to accept it. */
export const Scene06Sync: React.FC<SceneProps> = ({ frame }) => {
  const request = ramp(frame, -10, 2);
  const waiting = frame >= 26 && frame < 48;
  const verified = frame >= 70;
  const syncBadge = frame >= 78;
  const typed = Math.floor(ramp(frame, 48, 70) * STALE.modelMirror[1].length);
  const verifiedReveal = ramp(frame, 70, 82);
  const successEase = easeOut(verifiedReveal);

  return (
    <AbsoluteFill
      style={{
        boxSizing: "border-box",
        padding: `${GUTTER - 8}px ${GUTTER}px 112px`,
      }}
    >
      <Terminal
        title={SYNC.title}
        subtitle={STUDIO.url}
        accent={colors.purple}
        right={
          <>
            <Badge tone={syncBadge ? "green" : "muted"}>
              {syncBadge ? STUDIO.badgeSynced : "manual mode"}
            </Badge>
            <Badge tone="purple">{SYNC.model}</Badge>
          </>
        }
        style={{ height: "100%" }}
        bodyStyle={{
          backgroundColor: colors.background,
          display: "flex",
          gap: 16,
          padding: 16,
        }}
      >
        <div
          style={{
            display: "flex",
            flex: 0.9,
            flexDirection: "column",
            gap: 12,
            minHeight: 0,
            minWidth: 0,
          }}
        >
          <Pane
            accent={colors.cyan}
            bodyStyle={{ padding: "16px 18px" }}
            badge={
              <Badge tone={syncBadge ? "green" : "gold"}>
                {syncBadge ? STUDIO.badgeSynced : STUDIO.badgeStale}
              </Badge>
            }
            label="py"
            style={{
              flex: 1,
              opacity: lerp(0.42, 1, syncBadge ? successEase : 0),
              transform: `translateY(${lerp(8, 0, successEase)}px)`,
              boxShadow: syncBadge ? `0 0 ${24 * successEase}px ${colors.green}22` : "none",
            }}
          >
            {(syncBadge ? STALE.modelMirror : STALE.mirror).map((line) => (
              <div
                key={line}
                style={{
                  color: colors.text,
                  fontFamily: MONO_FAMILY,
                  fontSize: 24,
                  lineHeight: 1.6,
                  whiteSpace: "pre",
                }}
              >
                {line}
              </div>
            ))}
            <div
              style={{
                color: colors.muted,
                fontFamily: MONO_FAMILY,
                fontSize: 16,
                marginTop: 14,
              }}
            >
              {syncBadge ? "mirror restored by the model" : "stale · waiting for a rewrite"}
            </div>
          </Pane>

          <div
            style={{
              backgroundColor: colors.panel,
              border: `1px solid ${colors.edge}`,
              borderRadius: 16,
              boxSizing: "border-box",
              padding: "14px 18px",
            }}
          >
            <div
              style={{
                color: colors.muted,
                fontFamily: MONO_FAMILY,
                fontSize: 15,
                letterSpacing: 1.5,
                marginBottom: 10,
                textTransform: "uppercase",
              }}
            >
              request payload
            </div>
            <div style={{ alignItems: "center", display: "flex", gap: 8 }}>
              {SYNC.sent.map((item, index) => (
                <Badge key={item} tone={index === 0 ? "cyan" : "purple"}>
                  {item}
                </Badge>
              ))}
            </div>
            <div
              style={{
                color: colors.gold,
                fontFamily: MONO_FAMILY,
                fontSize: 16,
                marginTop: 10,
              }}
            >
              {SYNC.kept}
            </div>
          </div>
        </div>

        <div
          style={{
            display: "flex",
            flex: 1.25,
            flexDirection: "column",
            gap: 14,
            minHeight: 0,
            minWidth: 0,
          }}
        >
          <div
            style={{
              alignItems: "center",
              display: "flex",
              gap: 14,
              opacity: request,
              transform: `translateY(${lerp(12, 0, easeOut(request))}px)`,
            }}
          >
            <span
              style={{
                backgroundColor: `${colors.cyan}22`,
                border: `1px solid ${colors.cyan}`,
                borderRadius: 10,
                color: colors.cyan,
                fontFamily: MONO_FAMILY,
                fontSize: 20,
                fontWeight: 700,
                padding: "10px 18px",
              }}
            >
              {STALE.syncButton}
            </span>
            {waiting ? (
              <>
                <span
                  style={{
                    border: `3px solid ${colors.edge}`,
                    borderTopColor: colors.cyan,
                    borderRadius: 99,
                    display: "inline-block",
                    height: 22,
                    transform: `rotate(${(frame * 22) % 360}deg)`,
                    width: 22,
                  }}
                />
                <span
                  style={{
                    color: colors.cyan,
                    fontFamily: MONO_FAMILY,
                    fontSize: 18,
                  }}
                >
                  request sent · waiting for response
                </span>
              </>
            ) : null}
          </div>

          <div
            style={{
              backgroundColor: colors.panelDark,
              border: `1px solid ${colors.purple}66`,
              borderRadius: 16,
              boxSizing: "border-box",
              flex: 1,
              opacity: ramp(frame, -6, 2),
              padding: "18px 20px",
              transform: `translateY(${lerp(16, 0, easeOut(ramp(frame, -6, 2)))}px)`,
            }}
          >
            <div
              style={{
                alignItems: "center",
                display: "flex",
                gap: 10,
                marginBottom: 12,
              }}
            >
              <Badge tone="purple">assistant</Badge>
              <span
                style={{
                  color: colors.muted,
                  fontFamily: MONO_FAMILY,
                  fontSize: 16,
                }}
              >
                rewrites py to match the edited assembly
              </span>
            </div>
            {frame < 46 ? (
              <div
                style={{
                  color: colors.muted,
                  fontFamily: MONO_FAMILY,
                  fontSize: 24,
                  paddingTop: 8,
                }}
              >
                waiting for the model…
              </div>
            ) : (
              <div
                style={{
                  color: colors.text,
                  fontFamily: MONO_FAMILY,
                  fontSize: 30,
                  lineHeight: 1.7,
                  whiteSpace: "pre",
                }}
              >
                {STALE.modelMirror[0]}
                {"\n"}
                {STALE.modelMirror[1].slice(0, typed)}
                <span style={{ color: colors.cyan }}>▌</span>
              </div>
            )}
          </div>

          <div
            style={{
              alignItems: "center",
              display: "flex",
              gap: 14,
              justifyContent: "space-between",
            }}
          >
            <span
              style={{
                color: colors.muted,
                fontFamily: MONO_FAMILY,
                fontSize: 16,
              }}
            >
              the answer is not trusted yet
            </span>
            <span
              style={{
                backgroundColor: verified ? `${colors.green}1C` : "transparent",
                border: `1px solid ${verified ? colors.green : colors.edge}`,
                borderRadius: 12,
                boxShadow: verified ? `0 0 34px ${colors.green}33` : "none",
                color: verified ? colors.green : colors.edge,
                fontFamily: FONT_FAMILY,
                fontSize: 26,
                fontWeight: 650,
                opacity: verified ? 1 : 0.45,
                padding: "12px 20px",
                transform: `scale(${verified ? lerp(0.82, 1, successEase) : 0.94})`,
              }}
            >
              {verified ? `✓ ${SYNC.verified}` : SYNC.verified}
            </span>
          </div>
        </div>
      </Terminal>
    </AbsoluteFill>
  );
};
