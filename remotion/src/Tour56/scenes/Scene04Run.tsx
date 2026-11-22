import type { ReactNode } from "react";
import { AbsoluteFill } from "remotion";
import { StudioMock, studioColors } from "../components/StudioMock";
import { PROGRAM, STUDIO, TRACE } from "../script";
import { ramp } from "../theme";
import type { SceneProps } from "./types";

const mono: React.CSSProperties = {
  color: studioColors.text,
  font: '12px/1.45 ui-monospace, "JetBrains Mono", monospace',
  whiteSpace: "pre",
};

const Empty: React.FC = () => <span style={{ color: studioColors.muted }} />;

const ValueList: React.FC<{
  values: readonly { type: string; repr: string }[];
}> = ({ values }) => (
  <div style={{ display: "flex", flexDirection: "column", gap: 3 }}>
    {[...values].reverse().map((value, index) => (
      <div
        key={`${value.type}-${value.repr}-${index}`}
        style={{
          background: "#58a6ff18",
          border: "1px solid #58a6ff55",
          borderRadius: 4,
          display: "flex",
          gap: 8,
          padding: "2px 6px",
          width: "fit-content",
        }}
      >
        <span style={{ color: studioColors.accent }}>{value.type}</span>
        <span>{value.repr}</span>
      </div>
    ))}
  </div>
);

/** Step through the exact VM trace for the sample shown in the studio. */
export const Scene04Run: React.FC<SceneProps> = ({ frame }) => {
  const step = Math.min(
    TRACE.length - 1,
    Math.floor(ramp(frame, 6, 96) * TRACE.length),
  );
  const state = TRACE[step];
  const progress = step / (TRACE.length - 1);
  const activeLine = state.sourceLine;
  const stepReveal = ramp(frame, 6, 18);

  const editors: [ReactNode, ReactNode, ReactNode] = [
    <div key="py" style={mono}>
      {PROGRAM.py.map((line, index) => (
        <div key={index}>{line || "\u00a0"}</div>
      ))}
    </div>,
    <div key="spasm" style={mono}>
      {PROGRAM.spasm.map((line) => (
        <div key={line}>{line}</div>
      ))}
    </div>,
    <div
      key="sp"
      style={{ ...mono, color: studioColors.background, overflow: "hidden" }}
    >
      {" ".repeat(120)}
    </div>,
  ];

  const traceCode = (
    <div style={mono}>
      {PROGRAM.py.map((line, index) => {
        const isActive = activeLine === index + 1;
        return (
          <div
            key={index}
            style={{
              background: isActive ? "#3a2a00" : "transparent",
              color: isActive ? "#ffd479" : studioColors.text,
              lineHeight: "1.6em",
              padding: "0 10px",
            }}
          >
            <span
              style={{
                color: studioColors.muted,
                display: "inline-block",
                width: "3em",
              }}
            >
              {String(index + 1).padStart(2, " ")}
            </span>
            {line || "\u00a0"}
          </div>
        );
      })}
    </div>
  );

  const statePanels: [ReactNode, ReactNode, ReactNode, ReactNode] = [
    state.call.length ? (
    state.call.map((frame, index) => (
      <article
        key={`${frame.func}-${index}`}
        style={{
          background: "#58a6ff12",
          border: "1px solid #303943",
          borderRadius: 5,
          padding: "4px 7px",
        }}
      >
        <div style={{ color: studioColors.accent }}>{frame.func}</div>
        {frame.locals.map((local) => (
          <div
            key={local.name}
            style={{ color: studioColors.muted, paddingLeft: 10 }}
          >
            {local.name} <span style={{ color: studioColors.text }}>{local.repr}</span>
          </div>
        ))}
      </article>
    ))
    ) : (
      <Empty key="call-empty" />
    ),
    state.stack.length ? (
      <ValueList key="stack" values={state.stack} />
    ) : (
      <Empty key="stack-empty" />
    ),
    <Empty key="heap-empty" />,
    state.output ? (
      <pre
        key="output"
        style={{
          color: "#7ee787",
          font: '12px/1.45 ui-monospace, "JetBrains Mono", monospace',
          margin: 0,
          whiteSpace: "pre-wrap",
        }}
      >
        {state.output}
      </pre>
    ) : (
      <Empty key="output-empty" />
    ),
  ];

  return (
    <AbsoluteFill
      style={{
        boxSizing: "border-box",
        padding: "80px 16px 112px",
        filter: `brightness(${1 + stepReveal * 0.03})`,
      }}
    >
      <StudioMock
        activePane="py"
        editors={editors}
        statePanels={statePanels}
        stepLabel={STUDIO.stepLabel(step + 1, TRACE.length)}
        traceCode={traceCode}
        traceProgress={progress}
      />
    </AbsoluteFill>
  );
};
