import { AbsoluteFill } from "remotion";
import { Badge } from "../components/Badge";
import { Terminal } from "../components/Terminal";
import { colors, FONT_FAMILY, GUTTER, MONO_FAMILY, ramp } from "../theme";
import { INSTALL, REPO } from "../script";
import type { SceneProps } from "./types";

/** Scene 13 (1560-1680): the repository, then the install command. */
export const Scene13Close: React.FC<SceneProps> = ({ frame }) => {
  const typed = INSTALL.pip.length;
  const hints = ramp(frame, 24, 38);
  const caretOn = Math.floor(frame / 8) % 2 === 0;

  return (
    <AbsoluteFill
      style={{
        boxSizing: "border-box",
        display: "flex",
        flexDirection: "row",
        gap: 22,
        padding: `${GUTTER - 2}px ${GUTTER}px 224px`,
      }}
    >
      <div
        style={{
          backgroundColor: colors.panel,
          border: `1px solid ${colors.edge}`,
          borderRadius: 20,
          boxSizing: "border-box",
          display: "flex",
          flex: 1.08,
          flexDirection: "column",
          gap: 12,
          padding: "24px 26px",
        }}
      >
        <div style={{ alignItems: "center", display: "flex", gap: 10 }}>
          <span
            style={{
              color: colors.muted,
              fontFamily: MONO_FAMILY,
              fontSize: 22,
            }}
          >
            {REPO.owner} /
          </span>
          <span
            style={{
              color: colors.text,
              fontFamily: MONO_FAMILY,
              fontSize: 30,
              fontWeight: 700,
            }}
          >
            {REPO.name}
          </span>
          <Badge tone="muted">public</Badge>
          <span style={{ flex: 1 }} />
          <Badge tone="cyan">{REPO.branch}</Badge>
        </div>

        <div
          style={{
            color: colors.muted,
            fontFamily: MONO_FAMILY,
            fontSize: 17,
            paddingBottom: 6,
          }}
        >
          README.md · documentation.md · SELFHOSTING.md
        </div>

        <div
          style={{
            display: "grid",
            flex: 1,
            gap: "0 26px",
            gridTemplateColumns: "1fr 1fr",
            gridTemplateRows: "repeat(8, 1fr)",
            minHeight: 0,
          }}
        >
          {REPO.files.map((file, index) => {
            const appear = 0.55 + 0.45 * ramp(frame, index * 3 - 14, index * 3);
            return (
              <div
                key={file.name}
                style={{
                  alignItems: "center",
                  borderBottom: `1px solid ${colors.edge}33`,
                  color: file.kind === "dir" ? colors.cyan : colors.text,
                  display: "flex",
                  fontFamily: MONO_FAMILY,
                  fontSize: 19,
                  gap: 12,
                  opacity: appear,
                }}
              >
                <span style={{ color: colors.edge, fontSize: 15 }}>
                  {file.kind === "dir" ? "dir" : "file"}
                </span>
                {file.name}
              </div>
            );
          })}
        </div>

        <div
          style={{
            color: colors.muted,
            fontFamily: FONT_FAMILY,
            fontSize: 18,
            opacity: ramp(frame, 46, 60),
          }}
        >
          Python 3.10 or later · prebuilt wheels for Windows, Linux and macOS
        </div>
      </div>

      <Terminal
        title="install"
        subtitle="one command"
        accent={colors.green}
        right={<Badge tone="green">PyPI</Badge>}
        style={{ flex: 0.92 }}
        bodyStyle={{
          display: "flex",
          flexDirection: "column",
          gap: 14,
          padding: 26,
        }}
      >
        <div
          style={{
            color: colors.text,
            fontFamily: MONO_FAMILY,
            fontSize: 34,
            lineHeight: 1.5,
            whiteSpace: "pre",
          }}
        >
          <span style={{ color: colors.green }}>$ </span>
          {INSTALL.pip.slice(0, typed)}
          {typed < INSTALL.pip.length || caretOn ? (
            <span style={{ color: colors.cyan }}>▌</span>
          ) : null}
        </div>

        <div
          style={{
            color: colors.muted,
            fontFamily: MONO_FAMILY,
            fontSize: 18,
            lineHeight: 1.65,
            opacity: hints,
          }}
        >
          <div>installs the CLI and the OPT_SP browser assets</div>
          <div>spacelang-opt-sp --port 8000</div>
          <div>spacelang-opt-sp --background --port 8000</div>
        </div>

        <div style={{ flex: 1 }} />

        <div
          style={{
            alignItems: "center",
            backgroundColor: `${colors.cyan}10`,
            border: `1px solid ${colors.cyan}55`,
            borderRadius: 14,
            color: colors.cyan,
            display: "flex",
            fontFamily: MONO_FAMILY,
            fontSize: 20,
            gap: 12,
            opacity: ramp(frame, 40, 54),
            padding: "14px 18px",
          }}
        >
          <span>{INSTALL.python}</span>
          <span style={{ flex: 1 }} />
          <span style={{ color: colors.muted }}>
            {REPO.owner}/{REPO.name}
          </span>
        </div>
      </Terminal>
    </AbsoluteFill>
  );
};
