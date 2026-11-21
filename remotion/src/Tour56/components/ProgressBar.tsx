import { VIDEO } from "../script";
import { clamp01, colors, MONO_FAMILY } from "../theme";

const FIRST_SCENE_START = VIDEO.sceneFrames;
const TRACK_FRAMES = VIDEO.frames - FIRST_SCENE_START;
const SEGMENTS = VIDEO.sceneCount;

/**
 * Bottom progress bar: 0% at frame 120, 100% at frame 1680. Scene boundaries
 * are drawn as small ticks so the bar also reads as a timeline.
 */
export const ProgressBar: React.FC<{ frame: number }> = ({ frame }) => {
  const progress = clamp01((frame - FIRST_SCENE_START) / TRACK_FRAMES);
  const ticks = Array.from({ length: SEGMENTS + 1 }, (_, index) => index / SEGMENTS);

  return (
    <div
      style={{
        backgroundColor: "#183139",
        bottom: 0,
        height: 7,
        left: 0,
        overflow: "hidden",
        position: "absolute",
        right: 0,
      }}
    >
      <div
        style={{
          background: `linear-gradient(90deg, ${colors.cyan}, ${colors.green})`,
          bottom: 0,
          height: "100%",
          left: 0,
          position: "absolute",
          width: `${progress * 100}%`,
        }}
      />
      {ticks.map((tick) => (
        <div
          key={tick}
          style={{
            backgroundColor: "rgba(237, 245, 244, 0.28)",
            bottom: 0,
            height: 7,
            left: `${tick * 100}%`,
            position: "absolute",
            width: 1,
          }}
        />
      ))}
      <div
        style={{
          bottom: 10,
          color: colors.muted,
          fontFamily: MONO_FAMILY,
          fontSize: 13,
          letterSpacing: 1,
          position: "absolute",
          right: 10,
        }}
      >
        {Math.round(progress * 100)}%
      </div>
    </div>
  );
};
