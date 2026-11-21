import type { FC } from "react";
import { AbsoluteFill, useCurrentFrame } from "remotion";
import { CAPTIONS, FADE_FRAMES, VIDEO, type RelativeCaptionCue } from "./script";
import { ramp } from "./theme";
import { Scene00Handoff } from "./scenes/Scene00Handoff";
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
  /** 0 for the reserved handoff, 1-13 for the storyboard scenes. */
  index: number;
  start: number;
  duration: number;
  /** 00 -> 01 and 10 -> 11 fade in instead of hard-cutting. */
  fadeIn: boolean;
  component: FC<SceneProps>;
  captions: readonly RelativeCaptionCue[];
};

const sceneStart = (index: number): number => index * VIDEO.sceneFrames;

export const SCENES: readonly SceneSpec[] = [
  {
    name: "handoff",
    index: 0,
    start: sceneStart(0),
    duration: VIDEO.sceneFrames,
    fadeIn: false,
    component: Scene00Handoff,
    captions: [],
  },
  {
    name: "source",
    index: 1,
    start: sceneStart(1),
    duration: VIDEO.sceneFrames,
    fadeIn: true,
    component: Scene01Source,
    captions: CAPTIONS[1],
  },
  {
    name: "pipeline",
    index: 2,
    start: sceneStart(2),
    duration: VIDEO.sceneFrames,
    fadeIn: false,
    component: Scene02Pipeline,
    captions: CAPTIONS[2],
  },
  {
    name: "studio",
    index: 3,
    start: sceneStart(3),
    duration: VIDEO.sceneFrames,
    fadeIn: false,
    component: Scene03Studio,
    captions: CAPTIONS[3],
  },
  {
    name: "run",
    index: 4,
    start: sceneStart(4),
    duration: VIDEO.sceneFrames,
    fadeIn: false,
    component: Scene04Run,
    captions: CAPTIONS[4],
  },
  {
    name: "stale",
    index: 5,
    start: sceneStart(5),
    duration: VIDEO.sceneFrames,
    fadeIn: false,
    component: Scene05Stale,
    captions: CAPTIONS[5],
  },
  {
    name: "sync",
    index: 6,
    start: sceneStart(6),
    duration: VIDEO.sceneFrames,
    fadeIn: false,
    component: Scene06Sync,
    captions: CAPTIONS[6],
  },
  {
    name: "verify",
    index: 7,
    start: sceneStart(7),
    duration: VIDEO.sceneFrames,
    fadeIn: false,
    component: Scene07Verify,
    captions: CAPTIONS[7],
  },
  {
    name: "engines",
    index: 8,
    start: sceneStart(8),
    duration: VIDEO.sceneFrames,
    fadeIn: false,
    component: Scene08Engines,
    captions: CAPTIONS[8],
  },
  {
    name: "health",
    index: 9,
    start: sceneStart(9),
    duration: VIDEO.sceneFrames,
    fadeIn: false,
    component: Scene09Health,
    captions: CAPTIONS[9],
  },
  {
    name: "install",
    index: 10,
    start: sceneStart(10),
    duration: VIDEO.sceneFrames,
    fadeIn: false,
    component: Scene10Install,
    captions: CAPTIONS[10],
  },
  {
    name: "bootstrap",
    index: 11,
    start: sceneStart(11),
    duration: VIDEO.sceneFrames,
    fadeIn: true,
    component: Scene11Bootstrap,
    captions: CAPTIONS[11],
  },
  {
    name: "tests",
    index: 12,
    start: sceneStart(12),
    duration: VIDEO.sceneFrames,
    fadeIn: false,
    component: Scene12Tests,
    captions: CAPTIONS[12],
  },
  {
    name: "close",
    index: 13,
    start: sceneStart(13),
    duration: VIDEO.sceneFrames,
    fadeIn: false,
    component: Scene13Close,
    captions: CAPTIONS[13] ?? [],
  },
];

export const TOTAL_FRAMES = VIDEO.frames;

/** Absolute caption cues for the burned-in subtitle band. */
export const CAPTION_CUES = SCENES.flatMap((scene) =>
  scene.captions.map((cue) => ({
    from: scene.start + cue.from,
    to: scene.start + cue.to,
    lines: cue.lines,
    small: cue.small,
  })),
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

/**
 * Scene assembly: one full-frame layer per scene. Frames 0-119 render the
 * black handoff placeholder; 120-1680 walk the 13 storyboard scenes.
 *
 * Scenes 01 and 11 fade in over FADE_FRAMES. The fade starts at
 * FADE_FLOOR (not 0) so the incoming scene is already readable on its first
 * frame -- frame 120 and frame 1320 stay useful review stills -- while
 * frames 0-119 remain pure black.
 */
const FADE_FLOOR = 0.8;

export const TourSceneLayer: React.FC = () => {
  const frame = useCurrentFrame();
  const index = sceneIndexAt(frame);
  const scene = SCENES[index];
  const rel = frame - scene.start;
  const fade = scene.fadeIn
    ? FADE_FLOOR + (1 - FADE_FLOOR) * ramp(rel, 0, FADE_FRAMES)
    : 1;
  const Current = scene.component;

  return (
    <AbsoluteFill style={{ opacity: fade }}>
      <Current frame={Math.max(0, Math.min(scene.duration - 1, rel))} />
    </AbsoluteFill>
  );
};
