import { VIDEO } from "../script";
import { clamp01, colors } from "../theme";

const FIRST_SCENE_START = VIDEO.sceneDurations[0];
const TRACK_FRAMES = VIDEO.frames - FIRST_SCENE_START;
const SCENE_STARTS = VIDEO.sceneDurations.map((_, index) =>
  VIDEO.sceneDurations.slice(0, index).reduce((total, duration) => total + duration, 0),
);

/**
 * The timeline follows scene durations, with a bright playhead and a tick at
 * each real scene boundary.
 */
export const ProgressBar: React.FC<{ frame: number }> = ({ frame }) => {
  const progress = clamp01((frame - FIRST_SCENE_START) / TRACK_FRAMES);
  const playheadPosition = `${progress * 100}%`;

  return (
    <div
      style={{
        background: "linear-gradient(90deg, #10232a, #183139)",
        bottom: 0,
        height: 8,
        left: 0,
        overflow: "hidden",
        position: "absolute",
        right: 0,
        boxShadow: "0 -1px 12px #63d8e81a",
      }}
    >
      <div
        style={{
          background: `linear-gradient(90deg, ${colors.cyan}, #91f0ca)`,
          bottom: 0,
          height: "100%",
          left: 0,
          position: "absolute",
          width: playheadPosition,
          boxShadow: `0 0 14px ${colors.cyan}88`,
        }}
      />
      {SCENE_STARTS.slice(2).map((sceneStart, index) => {
        const tick = clamp01((sceneStart - FIRST_SCENE_START) / TRACK_FRAMES);
        const passed = progress >= tick;
        return (
          <div
            key={index}
            style={{
              backgroundColor: passed ? "#e5fff2aa" : "rgba(237, 245, 244, 0.24)",
              bottom: 0,
              height: 8,
              left: `${tick * 100}%`,
              position: "absolute",
              width: 2,
            }}
          />
        );
      })}
      <div
        style={{
          background: "#effff8",
          border: `2px solid ${colors.cyan}`,
          borderRadius: "50%",
          boxShadow: `0 0 12px ${colors.cyan}`,
          height: 10,
          left: playheadPosition,
          marginLeft: -5,
          position: "absolute",
          top: -1,
          width: 10,
        }}
      />
    </div>
  );
};
