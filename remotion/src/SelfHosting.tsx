import {
  AbsoluteFill,
  interpolate,
  Sequence,
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
};

const sans =
  '"Inter", "Noto Sans CJK SC", "PingFang SC", "Microsoft YaHei", sans-serif';
const mono =
  '"SFMono-Regular", "Cascadia Code", "Noto Sans Mono CJK SC", monospace';

const clamp = (value: number) => Math.min(1, Math.max(0, value));

const ease = (value: number) => {
  const clamped = clamp(value);
  return 1 - Math.pow(1 - clamped, 3);
};

const entrance = (frame: number, from = 0) => {
  const progress = ease(interpolate(frame, [from, from + 18], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  }));
  return {
    opacity: progress,
    transform: `translateY(${24 * (1 - progress)}px)`,
  };
};

const Panel: React.FC<{
  children: React.ReactNode;
  accent?: string;
  style?: React.CSSProperties;
}> = ({ children, accent = colors.edge, style }) => (
  <div
    style={{
      backgroundColor: colors.panel,
      border: `1px solid ${accent}`,
      borderRadius: 20,
      boxSizing: "border-box",
      ...style,
    }}
  >
    {children}
  </div>
);

const Eyebrow: React.FC<{ children: React.ReactNode; color?: string }> = ({
  children,
  color = colors.cyan,
}) => (
  <div
    style={{
      color,
      fontFamily: mono,
      fontSize: 18,
      fontWeight: 700,
      letterSpacing: 3,
      textTransform: "uppercase",
    }}
  >
    {children}
  </div>
);

const Title: React.FC<{ children: React.ReactNode; small?: boolean }> = ({
  children,
  small = false,
}) => (
  <div
    style={{
      color: colors.text,
      fontFamily: sans,
      fontSize: small ? 44 : 62,
      fontWeight: 760,
      letterSpacing: -1,
      lineHeight: 1.04,
    }}
  >
    {children}
  </div>
);

const Caption: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <div
    style={{
      alignItems: "center",
      bottom: 64,
      display: "flex",
      height: 82,
      justifyContent: "center",
      left: 96,
      position: "absolute",
      right: 96,
    }}
  >
    <div
      style={{
        backgroundColor: "rgba(7, 19, 24, 0.92)",
        border: `1px solid ${colors.edge}`,
        borderRadius: 12,
        boxSizing: "border-box",
        color: colors.text,
        fontFamily: sans,
        fontSize: 27,
        fontWeight: 650,
        padding: "16px 28px",
        textAlign: "center",
      }}
    >
      {children}
    </div>
  </div>
);

const Header: React.FC<{
  index: number;
  title: string;
  accent?: string;
}> = ({ index, title, accent = colors.cyan }) => (
  <>
    <div
      style={{
        alignItems: "center",
        display: "flex",
        left: 96,
        position: "absolute",
        right: 96,
        top: 40,
      }}
    >
      <span
        style={{
          color: accent,
          fontFamily: mono,
          fontSize: 16,
          fontWeight: 700,
          letterSpacing: 3,
        }}
      >
        SPACELANG / SELF-HOSTING
      </span>
      <span
        style={{
          backgroundColor: colors.edge,
          height: 1,
          marginLeft: 18,
          width: 46,
        }}
      />
      <span
        style={{
          color: colors.muted,
          fontFamily: mono,
          fontSize: 16,
          letterSpacing: 2,
          marginLeft: 18,
        }}
      >
        {title}
      </span>
      <span style={{ flex: 1 }} />
      <span
        style={{
          color: colors.text,
          fontFamily: mono,
          fontSize: 22,
          fontWeight: 700,
        }}
      >
        {String(index).padStart(2, "0")} / 10
      </span>
    </div>
  </>
);

const SceneShell: React.FC<{
  frame: number;
  index: number;
  title: string;
  caption: string;
  children: React.ReactNode;
  accent?: string;
}> = ({ frame, index, title, caption, children, accent }) => (
  <AbsoluteFill
    style={{
      backgroundColor: colors.background,
      backgroundImage:
        "radial-gradient(circle at 18% 5%, rgba(99, 216, 232, 0.11), transparent 42%), linear-gradient(rgba(40, 80, 90, 0.12) 1px, transparent 1px), linear-gradient(90deg, rgba(40, 80, 90, 0.12) 1px, transparent 1px)",
      backgroundSize: "auto, 96px 96px, 96px 96px",
      boxSizing: "border-box",
      fontFamily: sans,
      overflow: "hidden",
      padding: "118px 96px 176px",
    }}
  >
    <Header index={index} title={title} accent={accent} />
    <div style={{ height: "100%", ...entrance(frame) }}>{children}</div>
    <Caption>{caption}</Caption>
  </AbsoluteFill>
);

const Arrow: React.FC = () => (
  <span
    style={{
      color: colors.edge,
      fontFamily: mono,
      fontSize: 38,
      fontWeight: 700,
    }}
  >
    →
  </span>
);

const SceneOne: React.FC<{ frame: number }> = ({ frame }) => (
  <SceneShell
    frame={frame}
    index={1}
    title="one language"
    caption="A SpaceLang runtime is written in SpaceLang."
  >
    <div
      style={{
        alignItems: "center",
        display: "flex",
        gap: 24,
        height: "100%",
        justifyContent: "center",
      }}
    >
      <Panel accent={colors.cyan} style={{ padding: "34px 42px", width: 430 }}>
        <Eyebrow>engine source</Eyebrow>
        <div style={{ marginTop: 22 }}>
          <Title small>sp_vm.sp</Title>
        </div>
        <div
          style={{
            color: colors.muted,
            fontFamily: mono,
            fontSize: 24,
            lineHeight: 1.6,
            marginTop: 18,
          }}
        >
          {"FETCH  →  DECODE\nNEXT  →  EXECUTE\nSTACK →  OUTPUT"}
        </div>
      </Panel>
      <Arrow />
      <Panel accent={colors.green} style={{ padding: "34px 42px", width: 430 }}>
        <Eyebrow color={colors.green}>target program</Eyebrow>
        <div style={{ marginTop: 22 }}>
          <Title small>demo.sp</Title>
        </div>
        <div
          style={{
            color: colors.muted,
            fontFamily: mono,
            fontSize: 24,
            lineHeight: 1.6,
            marginTop: 18,
          }}
        >
          {"PUSH_INT 20\nPUSH_INT 22\nOP 1\nCALL print"}
        </div>
      </Panel>
      <div
        style={{
          backgroundColor: colors.green,
          borderRadius: 999,
          color: colors.background,
          fontFamily: mono,
          fontSize: 30,
          fontWeight: 800,
          padding: "18px 24px",
        }}
      >
        42
      </div>
    </div>
  </SceneShell>
);

const SceneTwo: React.FC<{ frame: number }> = ({ frame }) => (
  <SceneShell
    frame={frame}
    index={2}
    title="runtime self-hosting"
    caption="The interpreter executes another .sp program."
  >
    <div
      style={{
        alignItems: "center",
        display: "flex",
        flexDirection: "column",
        gap: 32,
        height: "100%",
        justifyContent: "center",
      }}
    >
      <div
        style={{
          alignItems: "center",
          display: "flex",
          gap: 24,
        }}
      >
        {["CPython VM", "sp_vm.sp", "demo.sp", "output"].map(
          (item, index) => (
            <div key={item} style={{ alignItems: "center", display: "flex", gap: 24 }}>
              {index > 0 ? <Arrow /> : null}
              <Panel
                accent={index === 3 ? colors.green : colors.cyan}
                style={{
                  color: index === 3 ? colors.green : colors.text,
                  fontFamily: mono,
                  fontSize: 27,
                  fontWeight: 750,
                  padding: "22px 26px",
                  textAlign: "center",
                }}
              >
                {item}
              </Panel>
            </div>
          ),
        )}
      </div>
      <div
        style={{
          color: colors.muted,
          fontFamily: mono,
          fontSize: 24,
        }}
      >
        spacelang run sp_vm.sp demo.sp
      </div>
    </div>
  </SceneShell>
);

const SceneThree: React.FC<{ frame: number }> = ({ frame }) => (
  <SceneShell
    frame={frame}
    index={3}
    title="the bootstrap chain"
    caption="Python is needed for one stage, not for every run."
  >
    <div
      style={{
        display: "grid",
        gap: 24,
        gridTemplateColumns: "1fr 1fr 1fr",
        height: "100%",
      }}
    >
      {[
        ["stage 0", "Python toolchain", "spc.py → spc1.sp", "needs Python once", colors.gold],
        ["stage 1", "compiler1.exe", "spc1.sp → spc2.sp", "no Python at runtime", colors.cyan],
        ["stage 2", "compiler2.exe", "spc2.sp → spc3.sp", "compiles itself", colors.green],
      ].map(([tag, title, command, note, accent], index) => (
        <Panel
          key={String(tag)}
          accent={String(accent)}
          style={{
            display: "flex",
            flexDirection: "column",
            padding: "30px",
            opacity: entrance(frame, index * 20).opacity,
            transform: entrance(frame, index * 20).transform,
          }}
        >
          <Eyebrow color={String(accent)}>{String(tag)}</Eyebrow>
          <div style={{ marginTop: 24 }}>
            <Title small>{title}</Title>
          </div>
          <div
            style={{
              color: colors.cyan,
              fontFamily: mono,
              fontSize: 22,
              lineHeight: 1.5,
              marginTop: 28,
            }}
          >
            {command}
          </div>
          <div style={{ flex: 1 }} />
          <div
            style={{
              borderTop: `1px solid ${colors.edge}`,
              color: String(accent),
              fontFamily: mono,
              fontSize: 20,
              paddingTop: 18,
            }}
          >
            {note}
          </div>
        </Panel>
      ))}
    </div>
  </SceneShell>
);

const SceneFour: React.FC<{ frame: number }> = ({ frame }) => (
  <SceneShell
    frame={frame}
    index={4}
    title="build the runner"
    caption="A C++17 executable runs .sp with no Python dependency."
  >
    <div style={{ display: "grid", gap: 24, gridTemplateColumns: "1.2fr 0.8fr", height: "100%" }}>
      <Panel style={{ padding: "34px", backgroundColor: colors.panelDark }}>
        <Eyebrow>native/build.ps1</Eyebrow>
        <div
          style={{
            color: colors.text,
            fontFamily: mono,
            fontSize: 34,
            lineHeight: 1.7,
            marginTop: 30,
          }}
        >
          <span style={{ color: colors.green }}>{"$ "}</span>
          {"powershell -ExecutionPolicy Bypass \\\n  -File native/build.ps1"}
          <br />
          <span style={{ color: colors.green }}>{"$ "}</span>
          {"native\\spvm.exe bootstrap\\demos\\fib.sp"}
        </div>
      </Panel>
      <Panel accent={colors.green} style={{ alignItems: "center", display: "flex", flexDirection: "column", justifyContent: "center", padding: 30 }}>
        <Eyebrow color={colors.green}>Python-free</Eyebrow>
        <div
          style={{
            color: colors.green,
            fontFamily: mono,
            fontSize: 46,
            fontWeight: 800,
            marginTop: 26,
            textAlign: "center",
          }}
        >
          spvm.exe
        </div>
        <div
          style={{
            color: colors.muted,
            fontFamily: sans,
            fontSize: 24,
            marginTop: 18,
            textAlign: "center",
          }}
        >
          C++17
          <br />
          runs .sp directly
        </div>
      </Panel>
    </div>
  </SceneShell>
);

const SceneFive: React.FC<{ frame: number }> = ({ frame }) => (
  <SceneShell
    frame={frame}
    index={5}
    title="build the compiler"
    caption="The native compiler can lower Python surface syntax and emit or run .sp."
  >
    <div
      style={{
        alignItems: "center",
        display: "flex",
        gap: 20,
        height: "100%",
        justifyContent: "center",
      }}
    >
      {[
        ["native examples", "tour.py", colors.gold],
        ["compiler.exe", "spc.py", colors.cyan],
        [".sp artifact", "tour.sp", colors.purple],
        ["native result", "runs", colors.green],
      ].map(([title, detail, accent], index) => (
        <div
          key={String(title)}
          style={{ alignItems: "center", display: "flex", gap: 20 }}
        >
          {index > 0 ? <Arrow /> : null}
          <Panel
            accent={String(accent)}
            style={{
              alignItems: "center",
              display: "flex",
              flexDirection: "column",
              justifyContent: "center",
              minHeight: 250,
              opacity: entrance(frame, index * 18).opacity,
              padding: "24px",
              textAlign: "center",
              width: 245,
            }}
          >
            <Eyebrow color={String(accent)}>{title}</Eyebrow>
            <div
              style={{
                color: colors.text,
                fontFamily: mono,
                fontSize: 29,
                fontWeight: 800,
                marginTop: 30,
              }}
            >
              {detail}
            </div>
          </Panel>
        </div>
      ))}
    </div>
  </SceneShell>
);

const SceneSix: React.FC<{ frame: number }> = ({ frame }) => (
  <SceneShell
    frame={frame}
    index={6}
    title="compiler fixed point"
    caption="The compiler is proved self-hosting when two stages produce identical bytes."
    accent={colors.green}
  >
    <div
      style={{
        alignItems: "center",
        display: "flex",
        height: "100%",
        justifyContent: "center",
      }}
    >
      <Panel
        accent={colors.green}
        style={{
          alignItems: "center",
          display: "flex",
          flexDirection: "column",
          padding: "38px 60px",
        }}
      >
        <Eyebrow color={colors.green}>fixed-point check</Eyebrow>
        <div
          style={{
            color: colors.text,
            fontFamily: mono,
            fontSize: 58,
            fontWeight: 800,
            marginTop: 28,
          }}
        >
          spc2.sp == spc3.sp
        </div>
        <div
          style={{
            color: colors.green,
            fontFamily: mono,
            fontSize: 28,
            marginTop: 24,
          }}
        >
          stage2 == stage3
        </div>
        <div
          style={{
            color: colors.muted,
            fontFamily: mono,
            fontSize: 22,
            marginTop: 26,
          }}
        >
          byte-identical compiler artifacts
        </div>
      </Panel>
    </div>
  </SceneShell>
);

const SceneSeven: React.FC<{ frame: number }> = ({ frame }) => (
  <SceneShell
    frame={frame}
    index={7}
    title="three programs"
    caption="Runtime hosting and compiler hosting are verified in the repository."
  >
    <div
      style={{
        display: "grid",
        gap: 24,
        gridTemplateColumns: "1fr 1fr",
        height: "100%",
      }}
    >
      {[
        ["1", "sp runs sp", "sp_vm.sp executes another .sp program.", colors.cyan],
        ["2", "sp runs sp runs sp", "The self-hosted VM executes itself.", colors.purple],
        ["3", "compiler.exe", "A native executable compiles .sp source.", colors.gold],
        ["4", "fixed point", "Compiling the compiler reproduces identical bytes.", colors.green],
      ].map(([number, title, detail, accent], index) => (
        <Panel
          key={String(number)}
          accent={String(accent)}
          style={{
            alignItems: "center",
            display: "flex",
            gap: 22,
            padding: "24px 28px",
            opacity: entrance(frame, index * 12).opacity,
          }}
        >
          <div
            style={{
              alignItems: "center",
              backgroundColor: `${accent as string}22`,
              border: `1px solid ${accent as string}`,
              borderRadius: 999,
              color: accent as string,
              display: "flex",
              fontFamily: mono,
              fontSize: 28,
              fontWeight: 800,
              height: 64,
              justifyContent: "center",
              width: 64,
            }}
          >
            {number}
          </div>
          <div>
            <div
              style={{
                color: colors.text,
                fontFamily: mono,
                fontSize: 25,
                fontWeight: 800,
              }}
            >
              {title}
            </div>
            <div
              style={{
                color: colors.muted,
                fontFamily: sans,
                fontSize: 20,
                marginTop: 8,
              }}
            >
              {detail}
            </div>
          </div>
        </Panel>
      ))}
    </div>
  </SceneShell>
);

const SceneEight: React.FC<{ frame: number }> = ({ frame }) => (
  <SceneShell
    frame={frame}
    index={8}
    title="quick start"
    caption="Build the artifacts in order, then verify the fixed point."
  >
    <Panel style={{ backgroundColor: colors.panelDark, height: "100%", padding: "32px 38px" }}>
      {[
        ["01", "Build the self-hosted VM", "py bootstrap/bootstrap.py all"],
        ["02", "Build the Python-free runner", "powershell native/build.ps1"],
        ["03", "Build the native compiler", "powershell native/build_compiler.ps1"],
        ["04", "Check the fixed point", "py -S tools/bootstrap_check.py"],
      ].map(([number, label, command], index) => (
        <div
          key={number}
          style={{
            alignItems: "center",
            borderBottom: index === 3 ? "none" : `1px solid ${colors.edge}`,
            display: "grid",
            gap: 24,
            gridTemplateColumns: "90px 420px 1fr",
            height: "25%",
            opacity: entrance(frame, index * 18).opacity,
          }}
        >
          <div
            style={{
              color: colors.cyan,
              fontFamily: mono,
              fontSize: 24,
              fontWeight: 800,
            }}
          >
            {number}
          </div>
          <div
            style={{
              color: colors.text,
              fontFamily: sans,
              fontSize: 27,
              fontWeight: 700,
            }}
          >
            {label}
          </div>
          <div
            style={{
              color: colors.green,
              fontFamily: mono,
              fontSize: 21,
              textAlign: "right",
            }}
          >
            {command}
          </div>
        </div>
      ))}
    </Panel>
  </SceneShell>
);

const SceneNine: React.FC<{ frame: number }> = ({ frame }) => (
  <SceneShell
    frame={frame}
    index={9}
    title="verification"
    caption="The suite checks parity across Python and native engines."
  >
    <div
      style={{
        alignItems: "center",
        display: "flex",
        gap: 26,
        height: "100%",
        justifyContent: "center",
      }}
    >
      <Panel accent={colors.green} style={{ padding: "34px 40px", width: 430 }}>
        <Eyebrow color={colors.green}>test suite</Eyebrow>
        <div
          style={{
            color: colors.green,
            fontFamily: mono,
            fontSize: 82,
            fontWeight: 850,
            marginTop: 22,
          }}
        >
          pytest
        </div>
        <div
          style={{
            color: colors.muted,
            fontFamily: mono,
            fontSize: 22,
            marginTop: 16,
          }}
        >
          bootstrap · native · compiler · VM parity
        </div>
      </Panel>
      <Panel style={{ padding: "34px 40px", width: 520 }}>
        <Eyebrow>what must agree</Eyebrow>
        {["same output", "same stack trace", "same compiled bytes", "same fixed point"].map(
          (item, index) => (
            <div
              key={item}
              style={{
                alignItems: "center",
                borderTop: index === 0 ? "none" : `1px solid ${colors.edge}`,
                color: colors.text,
                display: "flex",
                fontFamily: mono,
                fontSize: 24,
                height: 64,
                opacity: entrance(frame, index * 14).opacity,
              }}
            >
              <span style={{ color: colors.green, marginRight: 16 }}>✓</span>
              {item}
            </div>
          ),
        )}
      </Panel>
    </div>
  </SceneShell>
);

const SceneTen: React.FC<{ frame: number }> = ({ frame }) => (
  <SceneShell
    frame={frame}
    index={10}
    title="DwwLSM/spacelang"
    caption="Read SELFHOSTING.md for the complete pipeline."
    accent={colors.green}
  >
    <div
      style={{
        alignItems: "center",
        display: "flex",
        flexDirection: "column",
        height: "100%",
        justifyContent: "center",
        textAlign: "center",
      }}
    >
      <Eyebrow color={colors.green}>SpaceLang</Eyebrow>
      <div
        style={{
          color: colors.text,
          fontFamily: sans,
          fontSize: 74,
          fontWeight: 820,
          letterSpacing: -2,
          marginTop: 24,
        }}
      >
        A language that can run itself.
      </div>
      <Panel
        accent={colors.green}
        style={{
          marginTop: 38,
          padding: "18px 30px",
        }}
      >
        <span
          style={{
            color: colors.green,
            fontFamily: mono,
            fontSize: 28,
            fontWeight: 800,
          }}
        >
          SELFHOSTING.md
        </span>
      </Panel>
    </div>
  </SceneShell>
);

const SCENES = [
  SceneOne,
  SceneTwo,
  SceneThree,
  SceneFour,
  SceneFive,
  SceneSix,
  SceneSeven,
  SceneEight,
  SceneNine,
  SceneTen,
] as const;

export const SpaceLangSelfHosting: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const sceneDuration = 180;

  return (
    <AbsoluteFill>
      {SCENES.map((Scene, index) => (
        <Sequence
          key={index}
          from={index * sceneDuration}
          durationInFrames={sceneDuration}
        >
          <Scene frame={frame - index * sceneDuration} />
        </Sequence>
      ))}
      <div
        style={{
          backgroundColor: colors.cyan,
          bottom: 32,
          height: 4,
          left: 96,
          position: "absolute",
          transformOrigin: "left",
          width:
            interpolate(frame, [0, fps * 60], [0, 1728], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            }) + "px",
        }}
      />
    </AbsoluteFill>
  );
};
