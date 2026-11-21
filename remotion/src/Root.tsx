import { Composition } from "remotion";
import { MyComposition } from "./Composition";
import { SpaceLangTour56 } from "./Tour56/SpaceLangTour56";
import { TOTAL_FRAMES } from "./Tour56";
import { VIDEO } from "./Tour56/script";

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <MyComposition />
      <Composition
        id="SpaceLangTour56"
        component={SpaceLangTour56}
        durationInFrames={TOTAL_FRAMES}
        fps={VIDEO.fps}
        width={VIDEO.width}
        height={VIDEO.height}
      />
    </>
  );
};
