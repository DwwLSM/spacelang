import { colors, FONT_FAMILY, MONO_FAMILY } from "../theme";

export type CaptionCue = {
  from: number;
  to: number;
  lines: readonly string[];
  small?: string;
};

/** Burned-in caption band anchored low in the 1080p composition. */
export const Caption: React.FC<{
  frame: number;
  cues: readonly CaptionCue[];
  opacity?: number;
  bottom?: number;
}> = ({ frame, cues, opacity = 1, bottom = 24 }) => {
  const cue = cues.find((item) => frame >= item.from && frame < item.to);
  if (!cue) {
    return null;
  }
  const localFrame = frame - cue.from;
  const entrance = Math.min(1, localFrame / 6);
  const exit = Math.min(1, (cue.to - frame) / 6);
  const cueOpacity = Math.min(entrance, exit);
  const combinedOpacity = opacity * cueOpacity;

  return (
    <div
      style={{
        alignItems: "center",
        background:
          "linear-gradient(135deg, rgba(10, 30, 35, 0.98), rgba(4, 13, 16, 0.96))",
        border: "1px solid rgba(99, 216, 232, 0.48)",
        borderRadius: 12,
        bottom,
        boxSizing: "border-box",
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
        left: "50%",
        maxWidth: 1480,
        minWidth: 420,
        opacity: combinedOpacity,
        overflow: "hidden",
        padding: cue.small ? "8px 30px 9px" : "9px 32px",
        position: "absolute",
        transform: `translate(-50%, ${Math.round((1 - cueOpacity) * 8 + (1 - opacity) * 5)}px)`,
        boxShadow: "0 10px 28px rgba(0, 0, 0, 0.72), 0 0 20px rgba(99, 216, 232, 0.08)",
      }}
    >
      <div
        style={{
          background: "linear-gradient(90deg, transparent, rgba(99, 216, 232, 0.8), transparent)",
          height: 1,
          left: 18,
          opacity: 0.8,
          position: "absolute",
          right: 18,
          top: 0,
        }}
      />
      {cue.lines.map((line) => (
        <div
          key={line}
          style={{
            color: colors.text,
            fontFamily: FONT_FAMILY,
            fontSize: 32,
            fontWeight: 650,
            lineHeight: 1.18,
            maxWidth: 1400,
            textAlign: "center",
            textShadow: "0 2px 8px #000",
            whiteSpace: "nowrap",
          }}
        >
          {line}
        </div>
      ))}
      {cue.small ? (
        <div
          style={{
            color: colors.cyan,
            fontFamily: MONO_FAMILY,
            fontSize: 18,
            fontWeight: 700,
            letterSpacing: 0.8,
            marginTop: 4,
            textAlign: "center",
            whiteSpace: "nowrap",
          }}
        >
          {cue.small}
        </div>
      ) : null}
    </div>
  );
};
