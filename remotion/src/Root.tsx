import { Composition } from "remotion";
import { MyComposition } from "./Composition";
import { SpaceLangTour56 } from "./Tour56/SpaceLangTour56";
import { TOTAL_FRAMES } from "./Tour56";
import { VIDEO } from "./Tour56/script";
import { SpaceLangSelfHosting } from "./SelfHosting";

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
      <Composition
        id="SpaceLangSelfHosting"
        component={SpaceLangSelfHosting}
        durationInFrames={1800}
        fps={30}
        width={1920}
        height={1080}
      />
    </>
  );
};
