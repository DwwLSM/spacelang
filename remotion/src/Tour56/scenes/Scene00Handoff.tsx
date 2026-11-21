import { AbsoluteFill } from "remotion";
import type { SceneProps } from "./types";

/**
 * Scene 00 (frames 0-120): reserved for the author's own story. Pure black,
 * no content, no overlays.
 */
export const Scene00Handoff: React.FC<SceneProps> = () => (
  <AbsoluteFill style={{ backgroundColor: "#000000" }} />
);
