import { Composition } from "remotion";
import { SpaceLangIntro } from "./SpaceLangIntro";

const durationInFrames = 1800;

export const MyComposition = () => (
  <Composition
    id="SpaceLangIntro"
    component={SpaceLangIntro}
    durationInFrames={durationInFrames}
    fps={30}
    width={1920}
    height={1080}
  />
);
