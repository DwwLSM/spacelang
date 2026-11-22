import { AbsoluteFill } from "remotion";
import { StudioMock, studioColors } from "../components/StudioMock";
import { PROGRAM, TOKEN_RUNS } from "../script";
import { ramp } from "../theme";
import type { SceneProps } from "./types";

const editorTextStyle: React.CSSProperties = {
  color: studioColors.text,
  font: '13px/1.45 ui-monospace, "JetBrains Mono", monospace',
  whiteSpace: "pre",
};

const SpacePreview: React.FC<{ frame: number }> = ({ frame }) => {
  if (frame < 70) return null;
  return (
    <div
      style={{
        borderTop: "1px solid #303943",
        color: "#9daab7",
        font: '12px/1.45 ui-monospace, "JetBrains Mono", monospace',
        margin: "5px -10px 0",
        maxHeight: "45%",
        overflow: "hidden",
        padding: "5px 10px",
      }}
    >
      {TOKEN_RUNS.slice(0, 7).map((token, index) => {
        const count = token.spaces;
        const dots = "·".repeat(Math.min(count, 480));
        const opacity = ramp(frame, 70 + index * 3, 78 + index * 3);
        return (
          <div
            key={`${index}-${token.token}`}
            style={{
              color: index === 1 ? "#f0a020" : "#9daab7",
              opacity,
              overflow: "hidden",
              whiteSpace: "pre",
            }}
          >
            {dots || " "}
          </div>
        );
      })}
    </div>
  );
};

/** Reproduce the actual stacked-editor and trace-column DOM/CSS layout. */
export const Scene03Studio: React.FC<SceneProps> = ({ frame }) => {
  const typed = Math.floor(ramp(frame, 4, 30) * PROGRAM.py[3].length);
  const pyLines = PROGRAM.py.map((line, index) =>
    index === 3 ? line.slice(0, typed) : line,
  );
  const assemblyLines = PROGRAM.spasm;

  return (
    <AbsoluteFill
      style={{ boxSizing: "border-box", padding: "80px 16px 112px" }}
    >
      <StudioMock
        editors={[
          <div key="py" style={editorTextStyle}>
            {pyLines.map((line, index) => (
              <div key={index}>{line || "\u00a0"}</div>
            ))}
            {typed < PROGRAM.py[3].length ? (
              <span style={{ color: "#58a6ff" }}>▌</span>
            ) : null}
          </div>,
          <div key="spasm" style={editorTextStyle}>
            {assemblyLines.map((line) => (
              <div key={line}>{line}</div>
            ))}
          </div>,
          <div
            key="sp"
            style={{
              ...editorTextStyle,
              color: "#0e1116",
              display: "flex",
              flexDirection: "column",
              height: "100%",
            }}
          >
            <div style={{ flex: 1, overflow: "hidden" }}>{" ".repeat(120)}</div>
            <SpacePreview frame={frame} />
          </div>,
        ]}
        spPreview={frame >= 70}
        statePanels={[
          <span key="call-empty" style={{ color: "#9daab7" }} />,
          <span key="stack-empty" style={{ color: "#9daab7" }} />,
          <span key="heap-empty" style={{ color: "#9daab7" }} />,
          <span key="output-empty" style={{ color: "#9daab7" }} />,
        ]}
        stepLabel="Step 0 / 0"
        traceCode={
          <span style={{ color: "#9daab7", fontStyle: "italic" }}>
            Run to see the trace
          </span>
        }
      />
    </AbsoluteFill>
  );
};
