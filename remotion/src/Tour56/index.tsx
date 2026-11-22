import type { FC } from "react";
import { AbsoluteFill, useCurrentFrame } from "remotion";
import {
  CAPTIONS,
  TRANSITION_FRAMES,
  VIDEO,
  type RelativeCaptionCue,
} from "./script";
import { Scene00Hook } from "./scenes/Scene00Hook";
import { Scene01Source } from "./scenes/Scene01Source";
import { Scene02Pipeline } from "./scenes/Scene02Pipeline";
import { Scene03Studio } from "./scenes/Scene03Studio";
import { Scene04Run } from "./scenes/Scene04Run";
import { Scene05Stale } from "./scenes/Scene05Stale";
import { Scene06Sync } from "./scenes/Scene06Sync";
import { Scene07Verify } from "./scenes/Scene07Verify";
import { Scene08Engines } from "./scenes/Scene08Engines";
import { Scene09Health } from "./scenes/Scene09Health";
import { Scene10Install } from "./scenes/Scene10Install";
import { Scene11Bootstrap } from "./scenes/Scene11Bootstrap";
import { Scene12Tests } from "./scenes/Scene12Tests";
import { Scene13Close } from "./scenes/Scene13Close";
import type { SceneProps } from "./scenes/types";

export type SceneSpec = {
  /** Stable name, used by the status notes. */
  name: string;
  /** 0 for the hook, 1-13 for the remaining storyboard scenes. */
  index: number;
  start: number;
  duration: number;
  component: FC<SceneProps>;
  captions: readonly RelativeCaptionCue[];
};

const sceneDuration = (index: number): number =>
  VIDEO.sceneDurations[index] ?? VIDEO.sceneFrames;

const sceneStart = (index: number): number =>
  VIDEO.sceneDurations
    .slice(0, index)
    .reduce((total, duration) => total + duration, 0);

export const SCENES: readonly SceneSpec[] = [
  {
    name: "hook",
    index: 0,
    start: sceneStart(0),
    duration: sceneDuration(0),
    component: Scene00Hook,
    captions: CAPTIONS[0],
  },
  {
    name: "source",
    index: 1,
    start: sceneStart(1),
    duration: sceneDuration(1),
    component: Scene01Source,
    captions: CAPTIONS[1],
  },
  {
    name: "pipeline",
    index: 2,
    start: sceneStart(2),
    duration: sceneDuration(2),
    component: Scene02Pipeline,
    captions: CAPTIONS[2],
  },
  {
    name: "studio",
    index: 3,
    start: sceneStart(3),
    duration: sceneDuration(3),
    component: Scene03Studio,
    captions: CAPTIONS[3],
  },
  {
    name: "run",
    index: 4,
    start: sceneStart(4),
    duration: sceneDuration(4),
    component: Scene04Run,
    captions: CAPTIONS[4],
  },
  {
    name: "stale",
    index: 5,
    start: sceneStart(5),
    duration: sceneDuration(5),
    component: Scene05Stale,
    captions: CAPTIONS[5],
  },
  {
    name: "sync",
    index: 6,
    start: sceneStart(6),
    duration: sceneDuration(6),
    component: Scene06Sync,
    captions: CAPTIONS[6],
  },
  {
    name: "verify",
    index: 7,
    start: sceneStart(7),
    duration: sceneDuration(7),
    component: Scene07Verify,
    captions: CAPTIONS[7],
  },
  {
    name: "engines",
    index: 8,
    start: sceneStart(8),
    duration: sceneDuration(8),
    component: Scene08Engines,
    captions: CAPTIONS[8],
  },
  {
    name: "health",
    index: 9,
    start: sceneStart(9),
    duration: sceneDuration(9),
    component: Scene09Health,
    captions: CAPTIONS[9],
  },
  {
    name: "install",
    index: 10,
    start: sceneStart(10),
    duration: sceneDuration(10),
    component: Scene10Install,
    captions: CAPTIONS[10],
  },
  {
    name: "bootstrap",
    index: 11,
    start: sceneStart(11),
    duration: sceneDuration(11),
    component: Scene11Bootstrap,
    captions: CAPTIONS[11],
  },
  {
    name: "tests",
    index: 12,
    start: sceneStart(12),
    duration: sceneDuration(12),
    component: Scene12Tests,
    captions: CAPTIONS[12],
  },
  {
    name: "close",
    index: 13,
    start: sceneStart(13),
    duration: sceneDuration(13),
    component: Scene13Close,
    captions: CAPTIONS[13] ?? [],
  },
];

export const TOTAL_FRAMES = VIDEO.frames;

/** Absolute caption cues for the burned-in subtitle band. */
export const CAPTION_CUES = SCENES.flatMap((scene) =>
  scene.captions.map((cue) => {
    const scale = scene.duration / VIDEO.sceneFrames;
    return {
      from: scene.start + cue.from * scale,
      to: scene.start + cue.to * scale,
      lines: cue.lines,
      small: cue.small,
    };
  }),
);

export const sceneIndexAt = (frame: number): number => {
  let index = 0;
  for (let candidate = 0; candidate < SCENES.length; candidate += 1) {
    if (frame >= SCENES[candidate].start) {
      index = candidate;
    }
  }
  return index;
};

const smoothstep = (value: number): number => value * value * (3 - 2 * value);

export const sceneLayerOpacity = (frame: number): number => {
  const index = sceneIndexAt(frame);
  const scene = SCENES[index];
  const fadeFrames = TRANSITION_FRAMES / 2;
  const elapsed = frame - scene.start;

  if (index > 0 && elapsed < fadeFrames) {
    return smoothstep(Math.max(0, elapsed / fadeFrames));
  }

  const next = SCENES[index + 1];
  if (next && frame >= next.start - fadeFrames) {
    const progress = (frame - (next.start - fadeFrames)) / fadeFrames;
    return 1 - smoothstep(Math.max(0, Math.min(1, progress)));
  }

  return 1;
};

/**
 * Dissolve adjacent scenes with a gentle scale settle rather than moving the
 * entire composition like a slide.
 */
export const TourSceneLayer: React.FC = () => {
  const frame = useCurrentFrame();
  const index = sceneIndexAt(frame);
  const scene = SCENES[index];
  const rel = frame - scene.start;
  const sceneFrame = (rel * VIDEO.sceneFrames) / scene.duration;
  const Current = scene.component;
  const currentFrame = Math.max(0, Math.min(VIDEO.sceneFrames - 1, sceneFrame));

  const halfTransition = TRANSITION_FRAMES / 2;
  const incoming =
    index > 0 && rel < halfTransition ? scene : SCENES[index + 1];
  const transitionStart = incoming
    ? incoming.start - halfTransition
    : Number.POSITIVE_INFINITY;
  const transitionEnd = incoming
    ? incoming.start + halfTransition
    : Number.NEGATIVE_INFINITY;

  if (incoming && frame >= transitionStart && frame < transitionEnd) {
    const linearProgress = Math.max(
      0,
      Math.min(1, (frame - transitionStart) / TRANSITION_FRAMES),
    );
    const progress = smoothstep(linearProgress);
    const Incoming = incoming.component;
    const incomingFrame = Math.max(
      0,
      Math.min(
        VIDEO.sceneFrames - 1,
        ((frame - incoming.start) * VIDEO.sceneFrames) / incoming.duration,
      ),
    );
    const Previous = SCENES[incoming.index - 1].component;
    const previousFrame = VIDEO.sceneFrames - 1;

    return (
      <AbsoluteFill>
        <AbsoluteFill
          style={{
            opacity: 1 - progress,
            transform: `scale(${1 + progress * 0.008})`,
          }}
        >
          <Previous frame={previousFrame} />
        </AbsoluteFill>
        <AbsoluteFill
          style={{
            opacity: progress,
            transform: `scale(${1.012 - progress * 0.012})`,
          }}
        >
          <Incoming frame={incomingFrame} />
        </AbsoluteFill>
      </AbsoluteFill>
    );
  }

  return (
    <AbsoluteFill style={{ opacity: sceneLayerOpacity(frame) }}>
      <Current frame={currentFrame} />
    </AbsoluteFill>
  );
};
