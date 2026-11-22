import { AbsoluteFill, useCurrentFrame } from "remotion";
import { Caption } from "./components/Caption";
import { ProgressBar } from "./components/ProgressBar";
import {
  CAPTION_CUES,
  SCENES,
  sceneLayerOpacity,
  TOTAL_FRAMES,
  TourSceneLayer,
} from "./index";
import { colors, FONT_FAMILY, MONO_FAMILY } from "./theme";

const Backdrop: React.FC<{ frame: number }> = ({ frame }) => {
  const drift = Math.sin(frame / 180) * 3;
  const counterDrift = Math.cos(frame / 220) * 3;
  return (
  <AbsoluteFill
    style={{
      backgroundColor: colors.background,
      backgroundImage: [
        `radial-gradient(circle at ${18 + drift}% ${6 + counterDrift}%, rgba(99, 216, 232, 0.1), transparent 52%)`,
        `radial-gradient(circle at ${88 - counterDrift}% ${96 - drift}%, rgba(185, 161, 255, 0.08), transparent 48%)`,
        "linear-gradient(rgba(40, 80, 90, 0.14) 1px, transparent 1px)",
        "linear-gradient(90deg, rgba(40, 80, 90, 0.14) 1px, transparent 1px)",
        "radial-gradient(circle at 50% 45%, transparent 35%, rgba(0, 0, 0, 0.42) 100%)",
      ].join(", "),
      backgroundSize: "auto, auto, 96px 96px, 96px 96px, auto",
    }}
  />
  );
};

const Header: React.FC<{ frame: number }> = ({ frame }) => {
  if (frame < SCENES[0].duration) {
    return null;
  }
  const fade = sceneLayerOpacity(frame);

  return (
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
  );
};

const Footer: React.FC<{ frame: number }> = ({ frame }) => {
  return (
    <>
      <ProgressBar frame={frame} />
      <Caption
        cues={CAPTION_CUES}
        frame={frame}
        opacity={sceneLayerOpacity(frame)}
        bottom={24}
      />
    </>
  );
};

/**
 * `SpaceLangTour56`: 1920x1080, 30 fps, 1680 frames (56.0 s).
 * Fourteen scenes use varied durations, with normalized animations.
 */
export const SpaceLangTour56: React.FC = () => {
  const frame = useCurrentFrame();
  const opening = frame < SCENES[0].duration;

  return (
    <AbsoluteFill
      style={{
        color: colors.text,
        fontFamily: FONT_FAMILY,
        overflow: "hidden",
      }}
    >
      <Backdrop frame={frame} />
      <TourSceneLayer />
      {opening ? null : <Header frame={frame} />}
      <Footer frame={frame} />
    </AbsoluteFill>
  );
};

export { TOTAL_FRAMES };
