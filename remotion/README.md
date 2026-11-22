# SpaceLang project video

This Remotion project is an additional video workflow; the existing Manim
scenes in [`../scene.py`](../scene.py) remain unchanged. It includes two
English compositions: a 60-second introduction and a 56-second engineering
tour. The tour opens on the whitespace encoding, follows compilation and
debugging, then closes on runtime implementations, self-hosting, and CI. The
tour uses an eased circular reveal between scenes, and its captions are burned in.
The studio and server scenes follow the checked-in OPT_SP HTML, CSS, JavaScript,
and Python server. The debugger sample and trace snapshots are kept in
`src/Tour56/script.ts`.

## Requirements

- Node.js 20.19+, 22.13+, or 24+
- npm

Install dependencies from this directory and open Remotion Studio:

```bash
npm ci
npm run dev
```

In Studio, select `SpaceLangIntro` (60 seconds) or `SpaceLangTour56` (56
seconds). Both are 1080p at 30 fps.

## Render

Run from this directory:

```bash
npm run render
npm run render:tour
```

The first command writes `out/spacelang-intro-en.mp4`; the second writes
`out/spacelang-tour-56.mp4`. The introduction includes burned-in subtitles and
has a matching SRT sidecar at `subtitles/spacelang-intro-en.srt`. To render a
different format or quality, use Remotion's CLI options, for example:

```bash
npx remotion render src/index.ts SpaceLangIntro out/preview.mp4 --codec=h264 --crf=23
```

The video is a visual introduction, not a performance benchmark. See the
[Remotion documentation](https://www.remotion.dev/docs) for Studio and rendering
options.
