# 10,000 bipolar cells

An animation for the moment Eyewire II's citizen scientists passed 10,000
proofread bipolar cells, built from the lab's tracking spreadsheet alone: every
completed row's soma coordinate, completion date, proofreader and predicted
type. Each dot is one soma, lit on the day its proofreading was finished.

- `index.html` plays the animation live in a browser (it loops), and is also
  what the film is captured from: https://amyleesterling.github.io/ca3/eyewire2/
- `10k_cells.mp4` is the film, 1920x1080, 30 fps, 53 s, watermarked eyewire.ai
- `10k_column.mp4` is the 3D film: 170 real cell meshes from one column of the
  imaging box, arriving in completion order, turned to the side view as they
  are coloured by type, then recalled by proofreader. `col3d.html` is its page;
  it needs the GLBs from `fetch_meshes.py` in `meshes/`, which stay out of git
  (117 MB for the column, 40,000 triangles per cell)
- `10k_patch1000.mp4` is the same page on a wider patch: the 1,000 proofread
  cells nearest the same centre, 981 after strays are left out, at 10,000
  triangles each. It opens straight on the cells arriving, says up front that
  they are a 10% sample, colours them by type, runs the side view nearly edge
  to edge, recalls them by proofreader, and closes on EyeWire II's own
  achievement unlock from scifi-ui (see `scifi/`). This is the web encode; the
  master stayed out of git. It was spliced: the opening 9 s and the closing
  10 s were re-rendered with `cap.js` and `FROM=`/`TO=`, and the middle is the
  first render, checked frame for frame at both joins
- `cells.json` is the data behind it, one row per cell: voxel x, y, z, days
  since the first completion, proofreader index, type index
- `manifest.csv` is the same set in completion order with each cell's final
  segment id, for a proper mesh render of the cells themselves

## Captions are post-production

The patch film is two layers. The plate is the cells alone
(`col3d.html?layer=plate`), the slow part, rendered once. The overlay is every
word, the counter, the legend, the fades and the closing award on a transparent
background (`col3d.html?layer=overlay`, captured with `ALPHA=1`), which takes
minutes because nothing 3D is drawn. `compose.py` lays one on the other.

Every word on screen lives in `captions.json`, with the time it shows. To change
one: edit that file, re-capture the overlay, run `compose.py`. The plate is not
touched.

    export FFMPEG=...   # an ffmpeg with libx264
    eyewire2/render.sh 'col3d.html?meshes=meshes1000&layer=plate' plate.mp4
    ALPHA=1 CHUNK=1395 eyewire2/render.sh 'col3d.html?meshes=meshes1000&layer=overlay' overlay.mov
    python3 eyewire2/compose.py plate.mp4 overlay.mov film.mp4

`render.sh` renders in chunks and keeps the finished ones, so a render cut off
by a restart picks up where it stopped when run again.

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
