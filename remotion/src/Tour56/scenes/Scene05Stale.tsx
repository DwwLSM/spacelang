import { AbsoluteFill } from "remotion";
import { Badge } from "../components/Badge";
import { Pane, PaneButton } from "../components/Pane";
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
import { STALE, STUDIO } from "../script";
import type { SceneProps } from "./types";

/** Scene 05 (600-720): an assembly edit turns the Python mirror stale. */
export const Scene05Stale: React.FC<SceneProps> = ({ frame }) => {
  const edited = frame >= 26;
  const stale = frame >= 44;
  const note = ramp(frame, 58, 72);
  const syncButton = ramp(frame, 92, 102);
  const flash = frame >= 26 && frame < 44 ? 1 - ramp(frame, 26, 44) : 0;
  const pulse = 0.65 + 0.35 * Math.sin(frame / 5);

  return (
    <AbsoluteFill
      style={{
        boxSizing: "border-box",
        padding: `${GUTTER - 8}px ${GUTTER}px 224px`,
      }}
    >
      <Terminal
        title={STUDIO.title}
        subtitle={STUDIO.url}
        right={
          <>
            <Badge tone={stale ? "gold" : "cyan"}>
              {stale ? STUDIO.badgeStale : "editing"}
            </Badge>
            <PaneButton>Settings</PaneButton>
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
        <Pane
          accent={colors.purple}
          bodyStyle={{ padding: "16px 18px" }}
          badge={<Badge tone="purple">edited</Badge>}
          actions={<PaneButton>annotations</PaneButton>}
          label="spasm"
          style={{ flex: 1.05 }}
        >
          <div
            style={{
              color: colors.muted,
              fontFamily: MONO_FAMILY,
              fontSize: 15,
              letterSpacing: 1,
              marginBottom: 10,
            }}
          >
            instruction 4 · edited by hand
          </div>
          {STALE.asmBefore.map((line, index) => {
            const isEditLine = index === 3;
            const text = isEditLine && edited ? "OP 2" : line;
            return (
              <div
                key={`${line}-${index}`}
                style={{
                  backgroundColor: isEditLine
                    ? `rgba(244, 198, 106, ${0.12 + 0.3 * flash})`
                    : "transparent",
                  borderLeft: `3px solid ${isEditLine ? colors.gold : "transparent"}`,
                  color: isEditLine ? colors.gold : colors.text,
                  fontFamily: MONO_FAMILY,
                  fontSize: 26,
                  lineHeight: 1.65,
                  padding: "1px 12px",
                  whiteSpace: "pre",
                }}
              >
                <span style={{ color: colors.edge, marginRight: 20 }}>
                  {String(index + 1).padStart(2, "0")}
                </span>
                {text}
                {isEditLine ? (
                  <span style={{ color: colors.muted, marginLeft: 22, fontSize: 18 }}>
                    ← was {line}
                  </span>
                ) : null}
              </div>
            );
          })}
          <div
            style={{
              color: colors.muted,
              fontFamily: MONO_FAMILY,
              fontSize: 18,
              marginTop: 18,
            }}
          >
            tokens: 17, 10000, 2, 20, 0, 20, 1, 5, {edited ? "2" : "1"}, 18
          </div>
        </Pane>

        <div
          style={{
            display: "flex",
            flex: 1,
            flexDirection: "column",
            gap: 14,
            minHeight: 0,
            minWidth: 0,
          }}
        >
          <Pane
            accent={colors.cyan}
            bodyStyle={{ padding: "16px 18px" }}
            badge={
              <Badge tone={stale ? "gold" : "green"}>
                {stale ? STUDIO.badgeStale : STUDIO.badgeSynced}
              </Badge>
            }
            actions={<PaneButton active={!stale}>Run</PaneButton>}
            label="py"
            style={{ flex: 1, opacity: stale ? 0.42 : 1 }}
          >
            {STALE.mirror.map((line) => (
              <div
                key={line}
                style={{
                  color: stale ? colors.muted : colors.text,
                  fontFamily: MONO_FAMILY,
                  fontSize: 26,
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
              stale mirror · left alone until a rewrite is asked for
            </div>
          </Pane>

          <div
            style={{
              backgroundColor: colors.panel,
              border: `1px solid ${colors.gold}66`,
              borderRadius: 16,
              boxSizing: "border-box",
              opacity: note,
              padding: "18px 20px",
              transform: `translateY(${lerp(14, 0, easeOut(note))}px)`,
            }}
          >
            <div
              style={{
                color: colors.gold,
                fontFamily: MONO_FAMILY,
                fontSize: 18,
                fontWeight: 700,
                letterSpacing: 1,
                marginBottom: 10,
                textTransform: "uppercase",
              }}
            >
              why the mirror went stale
            </div>
            <div
              style={{
                color: colors.text,
                fontFamily: FONT_FAMILY,
                fontSize: 26,
                lineHeight: 1.35,
              }}
            >
              {STALE.noRule}
            </div>
            <div
              style={{
                color: colors.muted,
                fontFamily: MONO_FAMILY,
                fontSize: 18,
                marginTop: 10,
              }}
            >
              {STALE.pyfrontNote} · the encoded .sp is never sent to a model
            </div>
          </div>

          <div
            style={{
              alignItems: "center",
              display: "flex",
              gap: 14,
              justifyContent: "flex-end",
              opacity: syncButton,
              transform: `translateY(${lerp(10, 0, easeOut(syncButton))}px)`,
            }}
          >
            <span
              style={{
                color: colors.muted,
                fontFamily: MONO_FAMILY,
                fontSize: 16,
              }}
            >
              rewrite the mirror
            </span>
            <span
              style={{
                backgroundColor: `${colors.cyan}${Math.round(pulse * 40)
                  .toString(16)
                  .padStart(2, "0")}`,
                border: `1px solid ${colors.cyan}`,
                borderRadius: 10,
                boxShadow: `0 0 ${18 + pulse * 22}px ${colors.cyan}44`,
                color: colors.cyan,
                fontFamily: MONO_FAMILY,
                fontSize: 22,
                fontWeight: 700,
                letterSpacing: 1,
                padding: "12px 22px",
              }}
            >
              {STALE.syncButton}
            </span>
          </div>
        </div>
      </Terminal>
    </AbsoluteFill>
  );
};
