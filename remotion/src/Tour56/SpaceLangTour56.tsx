import { AbsoluteFill, useCurrentFrame } from "remotion";
import { Caption } from "./components/Caption";
import { ProgressBar } from "./components/ProgressBar";
import {
  CAPTION_CUES,
  SCENES,
  TOTAL_FRAMES,
  TourSceneLayer,
  sceneIndexAt,
} from "./index";
import { VIDEO } from "./script";
import { colors, FONT_FAMILY, MONO_FAMILY, ramp } from "./theme";

const Backdrop: React.FC = () => (
  <AbsoluteFill
    style={{
      backgroundColor: colors.background,
      backgroundImage: [
        "radial-gradient(circle at 18% 6%, rgba(99, 216, 232, 0.09), transparent 52%)",
        "radial-gradient(circle at 88% 96%, rgba(185, 161, 255, 0.08), transparent 48%)",
        "linear-gradient(rgba(40, 80, 90, 0.14) 1px, transparent 1px)",
        "linear-gradient(90deg, rgba(40, 80, 90, 0.14) 1px, transparent 1px)",
        "radial-gradient(circle at 50% 45%, transparent 35%, rgba(0, 0, 0, 0.42) 100%)",
      ].join(", "),
      backgroundSize: "auto, auto, 96px 96px, 96px 96px, auto",
    }}
  />
);

const Header: React.FC<{ frame: number }> = ({ frame }) => {
  if (frame < VIDEO.sceneFrames) {
    return null;
  }
  const index = sceneIndexAt(frame);
  const scene = SCENES[index];
  const corner = `${String(scene.index).padStart(2, "0")} / ${String(
    VIDEO.sceneCount,
  ).padStart(2, "0")}`;
  const fade = ramp(frame, VIDEO.sceneFrames, VIDEO.sceneFrames + 8);

  return (
    <>
      <div
        style={{
          alignItems: "center",
          display: "flex",
          gap: 14,
          left: 96,
          opacity: fade,
          position: "absolute",
          top: 40,
        }}
      >
        <span
          style={{
            color: colors.cyan,
            fontFamily: MONO_FAMILY,
            fontSize: 16,
            fontWeight: 700,
            letterSpacing: 3,
          }}
        >
          SPACELANG
        </span>
        <span style={{ backgroundColor: colors.edge, height: 1, width: 42 }} />
        <span
          style={{
            color: colors.muted,
            fontFamily: MONO_FAMILY,
            fontSize: 16,
            letterSpacing: 3,
          }}
        >
          THE TOUR
        </span>
      </div>

      <div
        style={{
          alignItems: "center",
          display: "flex",
          gap: 10,
          opacity: fade,
          position: "absolute",
          right: 96,
          top: 34,
        }}
      >
        <span
          style={{
            backgroundColor: colors.cyan,
            borderRadius: 99,
            height: 8,
            width: 8,
          }}
        />
        <span
          style={{
            color: colors.text,
            fontFamily: MONO_FAMILY,
            fontSize: 22,
            fontWeight: 700,
            letterSpacing: 2,
          }}
        >
          {corner}
        </span>
      </div>
    </>
  );
};

const Footer: React.FC<{ frame: number }> = ({ frame }) => (
  <>
    <Caption cues={CAPTION_CUES} frame={frame} />
    <ProgressBar frame={frame} />
  </>
);

/**
 * `SpaceLangTour56`: 1920x1080, 30 fps, 1680 frames (56.0 s).
 * Frames 0-119 are the black handoff placeholder; the storyboard runs
 * 120-1680 as 13 scenes of exactly 120 frames each.
 */
export const SpaceLangTour56: React.FC = () => {
  const frame = useCurrentFrame();
  const inHandoff = frame < VIDEO.sceneFrames;

  return (
    <AbsoluteFill
      style={{
        color: colors.text,
        fontFamily: FONT_FAMILY,
        overflow: "hidden",
      }}
    >
      {inHandoff ? null : <Backdrop />}
      <TourSceneLayer />
      <Header frame={frame} />
      {inHandoff ? null : <Footer frame={frame} />}
    </AbsoluteFill>
  );
};

export { TOTAL_FRAMES };
