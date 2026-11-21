import { colors, FONT_FAMILY, MONO_FAMILY } from "../theme";

export type CaptionCue = {
  from: number;
  to: number;
  lines: readonly string[];
  small?: string;
};

/** Burned-in caption band. One cue at a time; cues land on the hard cut. */
export const Caption: React.FC<{
  frame: number;
  cues: readonly CaptionCue[];
}> = ({ frame, cues }) => {
  const cue = cues.find((item) => frame >= item.from && frame < item.to);
  if (!cue) {
    return null;
  }

  return (
    <div
      style={{
        alignItems: "center",
        backgroundColor: "rgba(3, 10, 13, 0.91)",
        border: "1px solid rgba(99, 216, 232, 0.25)",
        borderRadius: 16,
        bottom: 26,
        boxSizing: "border-box",
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
        left: "50%",
        maxWidth: 1560,
        padding: "16px 38px",
        position: "absolute",
        transform: "translateX(-50%)",
      }}
    >
      {cue.lines.map((line) => (
        <div
          key={line}
          style={{
            color: colors.text,
            fontFamily: FONT_FAMILY,
            fontSize: 40,
            fontWeight: 600,
            lineHeight: 1.28,
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
            fontSize: 22,
            fontWeight: 700,
            letterSpacing: 1,
            marginTop: 6,
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
