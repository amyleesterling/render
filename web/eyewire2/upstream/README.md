# 10,000 bipolar cells

An animation for the moment Eyewire II's citizen scientists passed 10,000
proofread bipolar cells, built from the lab's tracking spreadsheet alone: every
completed row's soma coordinate, completion date, proofreader and predicted
type. Each dot is one soma, lit on the day its proofreading was finished.

- `index.html` plays the animation live in a browser (it loops), and is also
  what the film is captured from: https://amyleesterling.github.io/ca3/eyewire2/
- `10k_cells.mp4` is the film, 1920x1080, 30 fps, 53 s, watermarked eyewire.ai
- `cells.json` is the data behind it, one row per cell: voxel x, y, z, days
  since the first completion, proofreader index, type index
- `manifest.csv` is the same set in completion order with each cell's final
  segment id, for a proper mesh render of the cells themselves

## Rebuilding

The data comes from the "Focused BCs" tab, exported as CSV; a row counts when
its status starts with "Complete". Within a day the sheet's order means
nothing, so cells are shuffled inside each day with a fixed seed.

    node eyewire2/cap.js probe 12 30 40      # still frames, to check a change
    node eyewire2/cap.js full 10k_cells.mp4  # the film

`cap.js` drives headless Chromium through Playwright, calls `setFrame(i)` for
every frame and pipes the screenshots into ffmpeg. It expects the site served
at `http://127.0.0.1:8766/` (set `ANIM_URL` otherwise) and `FFMPEG` pointing at
an ffmpeg with libx264.

Geometry: coordinates are in voxels, drawn at 16 nm in x and y and 40 nm in z
with z stretched 2.5x so the slab reads as a slab; the cloud is rotated in the
plane so its long axis is horizontal. None of that changes which cell is where
relative to its neighbours.
