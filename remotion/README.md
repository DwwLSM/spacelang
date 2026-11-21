# SpaceLang project video

This Remotion project is an additional video workflow; the existing Manim
scenes in [`../scene.py`](../scene.py) remain unchanged. It creates a
60-second English introduction. The visuals tell one continuous story instead
of looping: source turns into bytecode, a function executes once on the stack,
the exact instruction tokens are decoded into `.sp`, OPT_SP steps one trace,
and two VMs independently reach the same result. Subtitle cues are complete
10–20-word sentences held for 5.4–6 seconds; the full video remains 60 seconds.

## Requirements

- Node.js 20.19+, 22.13+, or 24+
- npm

Install dependencies from this directory and open Remotion Studio:

```bash
npm ci
npm run dev
```

In Studio, select `SpaceLangIntro` to preview a 60-second, 1080p video at
30 fps.

## Render

Run from this directory:

```bash
npm run render
```

The MP4 is written to `out/spacelang-intro-en.mp4`; it includes burned-in
subtitles. The matching `subtitles/spacelang-intro-en.srt` can be loaded as a
separate subtitle track while editing or recording narration. To render a
different format or quality, use Remotion's CLI options, for example:

```bash
npx remotion render src/index.ts SpaceLangIntro out/preview.mp4 --codec=h264 --crf=23
```

The video is a visual introduction, not a performance benchmark. See the
[Remotion documentation](https://www.remotion.dev/docs) for Studio and rendering
options.
