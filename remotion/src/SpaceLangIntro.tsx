import type { CSSProperties, ReactNode } from "react";
import {
  AbsoluteFill,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";

const colors = {
  background: "#071318",
  panel: "#10232A",
  panelDark: "#0B171C",
  edge: "#28505A",
  cyan: "#63D8E8",
  green: "#75E0A2",
  gold: "#F4C66A",
  purple: "#B9A1FF",
  text: "#EDF5F4",
  muted: "#9AB1B5",
  red: "#FF7180",
};

const fontFamily =
  '"Inter", "Noto Sans CJK SC", "PingFang SC", "Microsoft YaHei", sans-serif';
const monoFamily =
  '"SFMono-Regular", "Cascadia Code", "Noto Sans Mono CJK SC", monospace';
const subtitles = [
  { start: 0, end: 5.4, text: "SpaceLang is a small experimental language that compiles a documented Python subset into executable stack machine instructions." },
  { start: 5.4, end: 10.8, text: "For example, print(add(a, b)) enters as readable source code and becomes ordered operations for a virtual machine." },
  { start: 10.8, end: 16.2, text: "LOAD_LOCAL 0 pushes argument a onto the operand stack, then LOAD_LOCAL 1 places argument b above it." },
  { start: 16.2, end: 21.6, text: "OP 1 removes both arguments, calculates their sum, and pushes the result back onto the stack." },
  { start: 21.6, end: 27, text: "RET returns the value, allowing print(add(a, b)) to display five when the program completes." },
  { start: 27, end: 32.4, text: "SpaceLang also saves programs in compact .sp files, representing each integer token as a count of spaces." },
  { start: 32.4, end: 37.8, text: "Newlines separate encoded tokens, empty lines represent zero, and assembly and optimization happen before encoding." },
  { start: 37.8, end: 43.2, text: "OPT_SP displays source beside compiled instructions, letting you step through traces and inspect each operation." },
  { start: 43.2, end: 48.6, text: "Watch the instruction pointer advance as operands enter the stack and program state updates during execution." },
  { start: 48.6, end: 54, text: "SpaceLang has two interpreters: a clear Python reference VM and an experimental C++ VM for native execution." },
  { start: 54, end: 60, text: "Both VMs run equivalent stack instructions; follow the source, compiled code, live stack, and matching results in this example." },
] as const;

const clamp = (value: number, input: number[], output: number[]) =>
  interpolate(value, input, output, {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

const panel: CSSProperties = {
  backgroundColor: colors.panel,
  border: `1px solid ${colors.edge}`,
  borderRadius: 18,
  boxSizing: "border-box",
};

const eyebrow: CSSProperties = {
  color: colors.muted,
  fontFamily: monoFamily,
  fontSize: 18,
  fontWeight: 700,
  letterSpacing: 2,
};

const Panel: React.FC<{
  label: string;
  color: string;
  children: ReactNode;
  style?: CSSProperties;
}> = ({ label, color, children, style }) => (
  <div style={{ ...panel, borderColor: `${color}66`, padding: 26, ...style }}>
    <div style={{ ...eyebrow, color, fontSize: 16, marginBottom: 22 }}>{label}</div>
    {children}
  </div>
);

const CodeLine: React.FC<{
  children: ReactNode;
  active?: boolean;
  color?: string;
  size?: number;
}> = ({ children, active = false, color = colors.text, size = 25 }) => (
  <div
    style={{
      backgroundColor: active ? "rgba(244, 198, 106, 0.13)" : "transparent",
      borderLeft: `3px solid ${active ? colors.gold : "transparent"}`,
      borderRadius: 4,
      boxSizing: "border-box",
      color: active ? colors.gold : color,
      fontFamily: monoFamily,
      fontSize: size,
      lineHeight: 1.55,
      padding: "5px 12px",
      whiteSpace: "pre",
    }}
  >
    {children}
  </div>
);

const Meter: React.FC<{ frame: number; duration: number }> = ({ frame, duration }) => {
  const progress = clamp(frame, [0, duration], [0, 100]);

  return (
    <div
      style={{
        backgroundColor: "#183139",
        borderRadius: 99,
        height: 5,
        left: 0,
        overflow: "hidden",
        position: "absolute",
        right: 0,
        top: 0,
      }}
    >
      <div
        style={{
          backgroundColor: colors.cyan,
          borderRadius: 99,
          height: "100%",
          width: `${progress}%`,
        }}
      />
    </div>
  );
};

const Subtitle: React.FC<{ frame: number }> = ({ frame }) => {
  const { fps } = useVideoConfig();
  const seconds = frame / fps;
  const cue = subtitles.find((item) => seconds >= item.start && seconds < item.end);
  const cueIndex = cue ? subtitles.indexOf(cue) : -1;
  const cueStart = cue ? cue.start * fps : 0;
  const enter = clamp(frame - cueStart, [0, 5], [12, 0]);

  return (
    <div
      style={{
        alignItems: "center",
        backgroundColor: "rgba(3, 10, 13, 0.91)",
        border: "1px solid rgba(99, 216, 232, 0.25)",
        borderRadius: 14,
        bottom: 34,
        boxSizing: "border-box",
        display: "flex",
        justifyContent: "center",
        left: 110,
        minHeight: 108,
        opacity: cue ? 1 : 0,
        padding: "18px 34px",
        position: "absolute",
        right: 110,
        transform: `translateY(${enter}px)`,
      }}
    >
      <div
        key={cueIndex}
        style={{
          color: colors.text,
          fontFamily,
          fontSize: 31,
          fontWeight: 550,
          lineHeight: 1.38,
          maxWidth: 1680,
          textAlign: "center",
          textShadow: "0 2px 8px #000",
        }}
      >
        {cue?.text}
      </div>
    </div>
  );
};

const Header: React.FC<{ section: string; titleText: string; frame: number; duration: number }> = ({
  section,
  titleText,
  frame,
  duration,
}) => (
  <>
    <Meter frame={frame} duration={duration} />
    <div
      style={{
        alignItems: "center",
        display: "flex",
        justifyContent: "space-between",
        left: 100,
        position: "absolute",
        right: 100,
        top: 54,
      }}
    >
      <div style={eyebrow}>SPACELANG&nbsp; / &nbsp;{section}</div>
      <div style={{ color: colors.text, fontFamily, fontSize: 24, fontWeight: 600 }}>
        {titleText}
      </div>
    </div>
  </>
);

const DataChip: React.FC<{ children: ReactNode; color: string; active?: boolean }> = ({
  children,
  color,
  active = true,
}) => (
  <div
    style={{
      backgroundColor: active ? `${color}18` : colors.panelDark,
      border: `1px solid ${active ? `${color}99` : colors.edge}`,
      borderRadius: 10,
      color: active ? color : colors.muted,
      fontFamily: monoFamily,
      fontSize: 24,
      fontWeight: 700,
      padding: "13px 20px",
    }}
  >
    {children}
  </div>
);

const CompilerScene: React.FC<{ frame: number }> = ({ frame }) => {
  const stage = Math.min(3, Math.floor(frame / 90));
  const stages = ["PYTHON", "FRONTEND", "IR", "OPTIMIZER"];
  const instructions = ["LOAD_LOCAL 0", "LOAD_LOCAL 1", "OP 1", "RET"];

  return (
    <AbsoluteFill>
      <Header section="01 / THE STACK" titleText="Source becomes instructions" frame={frame} duration={360} />
      <div
        style={{
          display: "grid",
          gap: 20,
          gridTemplateColumns: "1fr 1.08fr 0.82fr",
          left: 100,
          position: "absolute",
          right: 100,
          top: 160,
        }}
      >
        <Panel label="PYTHON SUBSET" color={colors.cyan} style={{ height: 465 }}>
          <CodeLine active={stage === 0} color={colors.cyan}>def add(a, b):</CodeLine>
          <CodeLine active={stage === 0}>    return a + b</CodeLine>
          <CodeLine size={19}>print(add(a, b))</CodeLine>
          <div
            style={{
              color: colors.cyan,
              fontFamily: monoFamily,
              fontSize: 18,
              marginTop: 22,
            }}
          >
            DOCUMENTED PYTHON SUBSET
          </div>
          <div
            style={{
              color: colors.muted,
              fontFamily,
              fontSize: 19,
              lineHeight: 1.5,
              marginTop: 10,
            }}
          >
            A small, explicit subset—not all of Python.
          </div>
        </Panel>

        <Panel label="STACK INSTRUCTIONS" color={colors.gold} style={{ height: 465 }}>
          {instructions.map((instruction, index) => (
            <CodeLine key={instruction} active={stage === index} size={23}>
              {String(index).padStart(2, "0")} &nbsp; {instruction}
            </CodeLine>
          ))}
          <div
            style={{
              backgroundColor: colors.panelDark,
              border: `1px solid ${colors.edge}`,
              borderRadius: 10,
              color: colors.muted,
              fontFamily: monoFamily,
              fontSize: 17,
              lineHeight: 1.7,
              marginTop: 28,
              padding: 16,
            }}
          >
            IR → readable assembly → optimized instructions
          </div>
          <div style={{ color: colors.gold, fontFamily: monoFamily, fontSize: 17, marginTop: 16 }}>
            OP 1 = integer addition
          </div>
        </Panel>

        <Panel label="STACK MACHINE" color={colors.green} style={{ height: 465 }}>
          <div
            style={{
              alignItems: "flex-end",
              backgroundColor: colors.panelDark,
              border: `1px solid ${colors.edge}`,
              borderRadius: 12,
              display: "flex",
              gap: 12,
              height: 214,
              justifyContent: "center",
              padding: 18,
            }}
          >
            {[0, 1, 2].map((slot) => (
              <div
                key={slot}
                style={{
                  border: `2px solid ${slot === 2 ? colors.green : colors.edge}`,
                  borderRadius: 8,
                  height: 70 + slot * 12,
                  width: 72,
                }}
              />
            ))}
          </div>
          <div style={{ color: colors.green, fontFamily: monoFamily, fontSize: 18, marginTop: 20, textAlign: "center" }}>
            OPERANDS · TOP · RESULT
          </div>
          <div
            style={{
              color: colors.muted,
              fontFamily,
              fontSize: 19,
              lineHeight: 1.5,
              marginTop: 20,
              textAlign: "center",
            }}
          >
            Instructions read values from the stack and leave results on top.
          </div>
        </Panel>
      </div>

      <div
        style={{
          alignItems: "center",
          display: "flex",
          gap: 16,
          justifyContent: "center",
          left: 100,
          position: "absolute",
          right: 100,
          top: 690,
        }}
      >
        {stages.map((stageName, index) => (
          <div key={stageName} style={{ alignItems: "center", display: "flex", gap: 16 }}>
            <div
              style={{
                backgroundColor: index === stage ? `${colors.cyan}18` : colors.panel,
                border: `1px solid ${index === stage ? colors.cyan : colors.edge}`,
                borderRadius: 10,
                color: index === stage ? colors.cyan : colors.muted,
                fontFamily: monoFamily,
                fontSize: 18,
                fontWeight: 700,
                padding: "13px 20px",
              }}
            >
              {stageName}
            </div>
            {index < stages.length - 1 && (
              <span style={{ color: colors.edge, fontSize: 23 }}>→</span>
            )}
          </div>
        ))}
      </div>
      <div
        style={{
          color: colors.muted,
          fontFamily: monoFamily,
          fontSize: 17,
          left: 100,
          position: "absolute",
          right: 100,
          textAlign: "center",
          top: 758,
        }}
      >
        LOAD_LOCAL 0&nbsp;&nbsp; · &nbsp;&nbsp;LOAD_LOCAL 1&nbsp;&nbsp; · &nbsp;&nbsp;OP 1&nbsp;&nbsp; · &nbsp;&nbsp;RET
      </div>
    </AbsoluteFill>
  );
};

const ExecutionScene: React.FC<{ frame: number }> = ({ frame }) => {
  const step = Math.min(3, Math.floor(frame / 112.5));
  const states = [["2"], ["2", "3"], ["5"], ["5"]];
  const instructions = ["LOAD_LOCAL 0", "LOAD_LOCAL 1", "OP 1 · ADD", "RET · RETURN"];
  const effects = [
    "push argument a",
    "push argument b",
    "pop 2 and 3 · push 5",
    "return 5 to caller",
  ];

  return (
    <AbsoluteFill>
      <Header section="01 / EXECUTION" titleText="Follow one call through the stack" frame={frame} duration={450} />
      <div
        style={{
          display: "grid",
          gap: 26,
          gridTemplateColumns: "0.9fr 1.25fr 0.9fr",
          left: 120,
          position: "absolute",
          right: 120,
          top: 190,
        }}
      >
        <Panel label="FUNCTION FRAME" color={colors.cyan} style={{ height: 460 }}>
          <CodeLine active={step < 2} color={colors.cyan}>def add(a, b):</CodeLine>
          <CodeLine active={step === 2}>    return a + b</CodeLine>
          <div
            style={{
              backgroundColor: colors.panelDark,
              border: `1px solid ${colors.edge}`,
              borderRadius: 10,
              color: colors.text,
              fontFamily: monoFamily,
              fontSize: 23,
              marginTop: 35,
              padding: 18,
            }}
          >
            locals: a = 2, b = 3
          </div>
          <div style={{ color: colors.cyan, fontFamily: monoFamily, fontSize: 18, marginTop: 22 }}>
            CALL add(2, 3)
          </div>
        </Panel>

        <Panel label="INSTRUCTION POINTER" color={colors.gold} style={{ height: 460 }}>
          {instructions.map((instruction, index) => (
            <CodeLine key={instruction} active={step === index} size={25}>
              {String(index).padStart(2, "0")} &nbsp; {instruction}
            </CodeLine>
          ))}
          <div
            style={{
              backgroundColor: `${colors.gold}12`,
              border: `1px solid ${colors.gold}55`,
              borderRadius: 10,
              color: colors.gold,
              fontFamily: monoFamily,
              fontSize: 20,
              marginTop: 28,
              padding: 16,
            }}
          >
            {effects[step]}
          </div>
          <div style={{ color: colors.muted, fontFamily: monoFamily, fontSize: 17, marginTop: 18 }}>
            IP {step} / 3
          </div>
        </Panel>

        <Panel label="OPERAND STACK" color={colors.green} style={{ height: 460 }}>
          <div
            style={{
              alignItems: "center",
              backgroundColor: colors.panelDark,
              border: `1px solid ${colors.edge}`,
              borderRadius: 12,
              display: "flex",
              flexDirection: "column-reverse",
              gap: 12,
              height: 290,
              justifyContent: "flex-start",
              overflow: "hidden",
              padding: 16,
            }}
          >
            {states[step].map((value, index) => (
              <div
                key={`${value}-${index}`}
                style={{
                  alignItems: "center",
                  backgroundColor: `${colors.green}18`,
                  border: `2px solid ${colors.green}88`,
                  borderRadius: 9,
                  color: colors.green,
                  display: "flex",
                  fontFamily: monoFamily,
                  fontSize: 34,
                  fontWeight: 700,
                  height: 60,
                  justifyContent: "center",
                  width: 180,
                }}
              >
                {value}
              </div>
            ))}
          </div>
          <div style={{ color: colors.green, fontFamily: monoFamily, fontSize: 22, marginTop: 18, textAlign: "center" }}>
            {step >= 2
              ? "RETURN VALUE · 5"
              : `TOP · ${states[step][states[step].length - 1]}`}
          </div>
        </Panel>
      </div>
      <div
        style={{
          alignItems: "center",
          display: "flex",
          gap: 15,
          justifyContent: "center",
          left: 120,
          position: "absolute",
          right: 120,
          top: 705,
        }}
      >
        {["LOAD a", "LOAD b", "ADD", "RETURN 5"].map((label, index) => (
          <div
            key={label}
            style={{
              backgroundColor: index === step ? `${colors.green}20` : colors.panel,
              border: `1px solid ${index === step ? colors.green : colors.edge}`,
              borderRadius: 9,
              color: index === step ? colors.green : colors.muted,
              fontFamily: monoFamily,
              fontSize: 20,
              padding: "13px 20px",
            }}
          >
            {label}
          </div>
        ))}
      </div>
    </AbsoluteFill>
  );
};

const SpaceEncodingScene: React.FC<{ frame: number }> = ({ frame }) => {
  const tokens = [20, 0, 20, 1, 5, 1, 18];
  const labels = ["LOAD_LOCAL", "slot 0", "LOAD_LOCAL", "slot 1", "OP", "add", "RET"];

  return (
    <AbsoluteFill>
      <Header section="01 / THE .SP FORMAT" titleText="Instructions become space counts" frame={frame} duration={240} />
      <div
        style={{
          display: "grid",
          gap: 26,
          gridTemplateColumns: "0.85fr 1.15fr",
          left: 170,
          position: "absolute",
          right: 170,
          top: 180,
        }}
      >
        <Panel label="READABLE ASSEMBLY" color={colors.cyan} style={{ height: 480 }}>
          {[
            ["LOAD_LOCAL 0", "20 spaces · newline · 0 spaces · newline"],
            ["LOAD_LOCAL 1", "20 spaces · newline · 1 space · newline"],
            ["OP 1", "5 spaces · newline · 1 space · newline"],
            ["RET", "18 spaces · newline"],
          ].map(([instruction, explanation], index) => (
            <div key={instruction} style={{ marginBottom: 16 }}>
              <CodeLine active={Math.min(3, Math.floor(frame / 60)) === index} size={21}>
                {instruction}
              </CodeLine>
              <div style={{ color: colors.muted, fontFamily: monoFamily, fontSize: 14, marginLeft: 16 }}>
                {explanation}
              </div>
            </div>
          ))}
          <div style={{ color: colors.cyan, fontFamily: monoFamily, fontSize: 17, marginTop: 15 }}>
            Opcode + operands · one token per line
          </div>
        </Panel>
        <Panel label="SPACELANG TOKEN STREAM" color={colors.gold} style={{ height: 480 }}>
          <div
            style={{
              backgroundColor: colors.panelDark,
              border: `1px solid ${colors.edge}`,
              borderRadius: 12,
              display: "flex",
              flexDirection: "column",
              gap: 5,
              minHeight: 290,
              padding: 16,
            }}
          >
            {tokens.map((count, index) => {
              const visible = frame >= index * 24;
              return (
                <div
                  key={index}
                  style={{
                    alignItems: "center",
                    color: visible ? colors.gold : "#4D656A",
                    display: "flex",
                    fontFamily: monoFamily,
                    fontSize: 17,
                    height: 29,
                    opacity: visible ? 1 : 0.16,
                    whiteSpace: "pre",
                  }}
                >
                  <span style={{ color: colors.muted, width: 30 }}>{index}</span>
                  <span style={{ letterSpacing: 0.5 }}>
                    {count === 0 ? "(empty)" : "·".repeat(count)}
                  </span>
                  <span style={{ color: colors.text, marginLeft: "auto", paddingLeft: 12 }}>
                    {count} · {labels[index]}
                  </span>
                </div>
              );
            })}
          </div>
          <div style={{ color: colors.gold, fontFamily: monoFamily, fontSize: 20, marginTop: 18 }}>
            Each dot = one literal space · newline terminates token
          </div>
          <div style={{ color: colors.muted, fontFamily, fontSize: 19, marginTop: 12 }}>
            The lexer counts spaces to recover integer values, then the parser rebuilds instructions.
          </div>
        </Panel>
      </div>
      <div style={{ ...eyebrow, color: colors.green, left: 170, position: "absolute", top: 720 }}>
        SOURCE CODE → COMPILER → ASSEMBLY → OPTIMIZER → .SP → VIRTUAL MACHINE
      </div>
    </AbsoluteFill>
  );
};

const DebuggerScene: React.FC<{ frame: number }> = ({ frame }) => {
  const step = Math.min(3, Math.floor(frame / 82.5));
  const stackStates = ["[2]", "[2, 3]", "[5]", "[5]"];
  const trace = ["LOAD_LOCAL 0", "LOAD_LOCAL 1", "OP 1", "RET"];

  return (
    <AbsoluteFill>
      <Header section="02 / OPT_SP" titleText="Step through the program" frame={frame} duration={330} />
      <div
        style={{
          ...panel,
          borderColor: `${colors.cyan}66`,
          left: 115,
          overflow: "hidden",
          position: "absolute",
          right: 115,
          top: 150,
        }}
      >
        <div
          style={{
            alignItems: "center",
            backgroundColor: "#152A31",
            borderBottom: `1px solid ${colors.edge}`,
            display: "flex",
            height: 62,
            justifyContent: "space-between",
            padding: "0 24px",
          }}
        >
          <div style={{ alignItems: "center", display: "flex", gap: 11 }}>
            {[colors.red, colors.gold, colors.green].map((color) => (
              <div key={color} style={{ backgroundColor: color, borderRadius: 99, height: 10, width: 10 }} />
            ))}
            <span style={{ color: colors.text, fontFamily: monoFamily, fontSize: 18, marginLeft: 10 }}>
              OPT_SP · program.sp
            </span>
          </div>
          <DataChip color={colors.green}>▶ RUNNING</DataChip>
        </div>

        <div
          style={{
            display: "grid",
            gap: 16,
            gridTemplateColumns: "1.1fr 1fr 0.92fr",
            minHeight: 440,
            padding: 24,
          }}
        >
          <Panel label="SOURCE" color={colors.cyan}>
            {["def add(a, b):", "    return a + b", "", "print(add(a, b))"].map((line, index) => (
              <CodeLine
                key={index}
                active={index === 0 ? step === 0 : index === 1 ? step < 3 : index === 3 && step === 3}
                size={20}
              >
                {line || " "}
              </CodeLine>
            ))}
            <div
              style={{
                borderTop: `1px solid ${colors.edge}`,
                color: colors.muted,
                fontFamily: monoFamily,
                fontSize: 17,
                marginTop: 22,
                paddingTop: 18,
              }}
            >
              source → compiled program
            </div>
          </Panel>

          <Panel label="INSTRUCTION TRACE" color={colors.gold}>
            {trace.map((line, index) => (
              <CodeLine key={line} active={index === step} size={21}>
                {String(index).padStart(2, "0")} &nbsp; {line}
              </CodeLine>
            ))}
            <div style={{ alignItems: "center", display: "flex", gap: 12, marginTop: 27 }}>
              <div
                style={{
                  backgroundColor: `${colors.gold}20`,
                  border: `1px solid ${colors.gold}66`,
                  borderRadius: 9,
                  color: colors.gold,
                  fontFamily: monoFamily,
                  fontSize: 19,
                  padding: "10px 15px",
                }}
              >
                STEP ▶
              </div>
              <span style={{ color: colors.muted, fontFamily: monoFamily, fontSize: 17 }}>
                IP = {step}
              </span>
            </div>
          </Panel>

          <Panel label="LIVE STATE" color={colors.green}>
            <div style={{ color: colors.muted, fontFamily: monoFamily, fontSize: 16 }}>
              OPERAND STACK
            </div>
            <div
              style={{
                ...panel,
                ...{ alignItems: "center", display: "flex", justifyContent: "center" },
                backgroundColor: colors.panelDark,
                borderColor: `${colors.green}55`,
                color: colors.green,
                fontFamily: monoFamily,
                fontSize: 32,
                height: 82,
                marginTop: 9,
              }}
            >
              {stackStates[step]}
            </div>
            <div style={{ color: colors.muted, fontFamily: monoFamily, fontSize: 16, marginTop: 20 }}>
              STDOUT
            </div>
            <div
              style={{
                color: step === 3 ? colors.green : "#527069",
                fontFamily: monoFamily,
                fontSize: 27,
                fontWeight: 700,
                marginTop: 10,
              }}
            >
              {step === 3 ? "> 5" : "> _"}
            </div>
            <div style={{ color: colors.muted, fontFamily: monoFamily, fontSize: 16, marginTop: 18 }}>
              GLOBALS&nbsp; {"{}"} &nbsp; HEAP&nbsp; {"{}"}
            </div>
          </Panel>
        </div>

        <div
          style={{
            alignItems: "center",
            borderTop: `1px solid ${colors.edge}`,
            color: colors.muted,
            display: "flex",
            fontFamily: monoFamily,
            fontSize: 17,
            justifyContent: "space-between",
            padding: "15px 26px",
          }}
        >
          <span>INSTRUCTIONS&nbsp; · &nbsp;OPERAND STACK&nbsp; · &nbsp;PROGRAM STATE</span>
          <span style={{ color: colors.cyan }}>TRACE STEP {step + 1} / 4</span>
        </div>
      </div>
    </AbsoluteFill>
  );
};

const VirtualMachinesScene: React.FC<{ frame: number }> = ({ frame }) => {
  const beat = Math.min(4, Math.floor(frame / 90));
  const step = Math.min(3, beat);
  const instructions = ["LOAD_LOCAL 0", "LOAD_LOCAL 1", "OP 1", "RET"];
  const stackStates = ["[2]", "[2, 3]", "[5]", "[5]"];
  const stages = ["Python reference VM", "Experimental C++ VM"];

  return (
    <AbsoluteFill>
      <Header section="03 / TWO INTERPRETERS" titleText="Same instructions. Same program." frame={frame} duration={420} />
      <div
        style={{
          ...panel,
          alignItems: "center",
          borderColor: `${colors.gold}66`,
          display: "flex",
          gap: 16,
          justifyContent: "center",
          left: 250,
          padding: 18,
          position: "absolute",
          right: 250,
          top: 155,
        }}
      >
        <span style={{ ...eyebrow, color: colors.gold }}>ONE PROGRAM</span>
        {instructions.map((line, index) => (
          <div
            key={line}
            style={{
              backgroundColor: step === index ? `${colors.gold}20` : colors.panelDark,
              border: `1px solid ${step === index ? colors.gold : colors.edge}`,
              borderRadius: 7,
              color: step === index ? colors.gold : colors.text,
              fontFamily: monoFamily,
              fontSize: 18,
              padding: "10px 13px",
            }}
          >
            {line}
          </div>
        ))}
      </div>

      <div
        style={{
          display: "grid",
          gap: 28,
          gridTemplateColumns: "1fr 1fr",
          left: 190,
          position: "absolute",
          right: 190,
          top: 315,
        }}
      >
        {stages.map((name, index) => {
          const color = index === 0 ? colors.cyan : colors.green;
          return (
            <Panel key={name} label={`INTERPRETER 0${index + 1}`} color={color} style={{ height: 345 }}>
              <div style={{ color: colors.text, fontFamily, fontSize: 30, fontWeight: 650 }}>
                {name}
              </div>
              <div style={{ color, fontFamily: monoFamily, fontSize: 19, marginTop: 10 }}>
                {index === 0 ? "Python · inspectable reference" : "C++ · native execution"}
              </div>
              <div
                style={{
                  ...panel,
                  alignItems: "center",
                  backgroundColor: colors.panelDark,
                  borderColor: `${color}55`,
                  display: "flex",
                  height: 96,
                  justifyContent: "center",
                  marginTop: 25,
                }}
              >
                <span style={{ color: colors.muted, fontFamily: monoFamily, fontSize: 20 }}>
                  STACK
                </span>
                <span style={{ color, fontFamily: monoFamily, fontSize: 34, fontWeight: 700, marginLeft: 20 }}>
                  {stackStates[step]}
                </span>
              </div>
              <div
                style={{
                  alignItems: "center",
                  color: step === 3 ? color : colors.muted,
                  display: "flex",
                  fontFamily: monoFamily,
                  fontSize: 21,
                  justifyContent: "space-between",
                  marginTop: 22,
                }}
              >
                <span>{beat === 4 ? "RETURNED: 5" : `STEP ${step + 1} / 4`}</span>
                <span>{beat === 4 ? "✓ COMPLETE" : "RUNNING →"}</span>
              </div>
            </Panel>
          );
        })}
      </div>

      <div
        style={{
          alignItems: "center",
          color: colors.purple,
          display: "flex",
          fontFamily,
          fontSize: 27,
          fontWeight: 650,
          gap: 14,
          justifyContent: "center",
          left: 190,
          position: "absolute",
          right: 190,
          top: 700,
        }}
      >
        <span>Same stack-based program</span>
        <span style={{ color: colors.muted }}>→</span>
        <span>matching result</span>
        <span style={{ color: colors.green, fontFamily: monoFamily }}>
          {beat === 4 ? "✓ 5 = 5" : "Python   C++"}
        </span>
      </div>
    </AbsoluteFill>
  );
};

export const SpaceLangIntro: React.FC = () => {
  const frame = useCurrentFrame();
  const section = frame < 1050 ? 0 : frame < 1380 ? 1 : 2;
  const localFrame = section === 0 ? frame : section === 1 ? frame - 1050 : frame - 1380;
  const sectionTitle = section === 0
    ? frame < 360
      ? "Source → bytecode"
      : frame < 810
        ? "Function call → return"
        : "Whitespace tokens → integers"
    : section === 1
      ? "Live trace · stack · program state"
      : "One instruction stream · two engines";
  const opacity = clamp(localFrame, [0, 12, section === 0 ? 1050 : section === 1 ? 330 : 420], [0, 1, 1]);

  return (
    <AbsoluteFill
      style={{
        backgroundColor: colors.background,
        color: colors.text,
        fontFamily,
        overflow: "hidden",
      }}
    >
      <div
        style={{
          background:
            "radial-gradient(ellipse at 50% 38%, rgba(35, 91, 98, 0.23), transparent 66%)",
          inset: 0,
          position: "absolute",
        }}
      />
      <div style={{ height: "100%", opacity }}>
        {section === 0 ? (
          frame < 360 ? (
            <CompilerScene frame={frame} />
          ) : frame < 810 ? (
            <ExecutionScene frame={frame - 360} />
          ) : (
            <SpaceEncodingScene frame={frame - 810} />
          )
        ) : section === 1 ? (
          <DebuggerScene frame={localFrame} />
        ) : (
          <VirtualMachinesScene frame={localFrame} />
        )}
      </div>
      <div
        style={{
          color: colors.muted,
          fontFamily: monoFamily,
          fontSize: 17,
          left: 100,
          position: "absolute",
          top: 112,
        }}
      >
        {sectionTitle}
      </div>
      <Subtitle frame={frame} />
    </AbsoluteFill>
  );
};
