# Words go on in post, never in the render

For the render guide (amyleesterling/render, RENDERING.md) and the render
protocol (amyleesterling/render-queue, RENDER_PROTOCOL.md). Add this section to
both, as written.

---

Render the picture and the words as separate layers, and put them together
afterwards. Captions, titles, counters, legends, watermarks, fades and end
cards are never baked into the 3D frames.

- **Plate**: the 3D scene alone, no text. The slow render, done once.
- **Overlay**: every word and graphic on a transparent background (PNG-in-MOV
  or ProRes 4444, keeping alpha). No 3D drawn, so it renders in minutes.
- **Composite**: ffmpeg lays the overlay on the plate.

All on-screen text lives in one file with its timing (for example
`captions.json`). Changing a word means editing that file, re-rendering the
overlay and re-compositing. The plate is never touched.

A legend synced to the picture, such as colour keys that light up as each cell
type arrives, still belongs in the overlay. The overlay is driven by the same
timeline as the plate, so it stays in sync without being baked in. Bake text
into the plate only if there is truly no way to drive it from that timeline.

Effects that depend on the picture behind them, such as a background blur
behind a card, are rebuilt in the composite from the plate.

Holds and freezes are also post: end the plate where the action stops and hold
its last frame in the composite. Don't render identical frames.

Render long plates in resumable chunks, so a machine restart costs one chunk,
not the whole render.

## Reference implementation

amyleesterling/ca3, `eyewire2/`:

- `captions.json`: every word on screen and when it shows
- `col3d.html?layer=plate` and `?layer=overlay`: the two layers from one page
  and one timeline
- `cap.js`: frame-by-frame capture; `ALPHA=1` keeps transparency, `FROM=`/`TO=`
  render a frame range
- `render.sh`: resumable chunked renders
- `compose.py`: the composite, including the rebuilt backdrop blur and the held
  last frame

In Blender the same split applies: render the scene with no text objects, and
add every word in the compositor or in ffmpeg afterwards, from a text file with
timings.
