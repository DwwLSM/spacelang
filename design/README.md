# Design references

Source artwork kept out of the served application. Nothing here is packaged into
the wheel or served by the debugger; `spacelang/opt_sp/static/` is the shipped
tree.

## `ascii-christmas-tree.html`

A standalone, full-window page: a software 3D point cloud (about 11,500 points)
built in model space, perspective-projected, z-buffered and rasterised into
monospace text with a per-character ASCII ramp, plus ray-marched soft shadows,
a snow particle system and bloom sprites. No WebGL, no dependencies.

It is the reference for the `christmas-tree` scene style in
`spacelang/opt_sp/static/js/scene-christmas-tree.js`. That module keeps the
geometry, shading and camera behaviour but turns the page into a component: the
canvas fills its container instead of the window, a `ResizeObserver` replaces the
window resize handler, the render loop stops while the tab is hidden or the
canvas is off screen, and every listener and buffer is released by `destroy()`.

Open the file directly in a browser to compare behaviour:

```bash
start design/ascii-christmas-tree.html     # Windows
xdg-open design/ascii-christmas-tree.html  # Linux
open design/ascii-christmas-tree.html      # macOS
```

Its HUD (title, lights/snow/glow/spin buttons, help overlay, fps counter) is
specific to the standalone page and is not part of the embedded scene.
