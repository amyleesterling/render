# Web path: no Blender, no GPU

A complete pipeline that runs anywhere Python, Node and ffmpeg run, including a
cloud session with no graphics card. Use it when Aurelius is busy, when the shot
is a population of small cells rather than a close up, or when the result should
also be a live page.

```
CAVE  ->  fetch_meshes.py  ->  one GLB per cell, in micrometres, plus index.json
      ->  col3d.html (three.js)  ->  cap.js (Playwright, headless Chromium)
      ->  ffmpeg  ->  mp4
```

It was built for Eyewire II in the ca3 site repo, and that repo is still where it
is developed: [amyleesterling/ca3, `eyewire2/`](https://github.com/amyleesterling/ca3/tree/main/eyewire2).
The files in `eyewire2/` here are a snapshot of its `main` taken 5 October 2026.

| file | from | what |
|---|---|---|
| `eyewire2/fetch_meshes.py` | ca3 `main` | pulls meshes through CAVE, decimates, writes `<segid>.glb` and `index.json` |
| `eyewire2/col3d.html` | ca3 `main` | the 3D column of cells in three.js. `?layer=plate` draws the cells alone, `?layer=overlay` draws every word on a transparent page |
| `eyewire2/captions.json` | ca3 `main` | every word on screen and when it shows |
| `eyewire2/render.sh` | ca3 `main` | renders a layer in resumable chunks and joins them |
| `eyewire2/compose.py` | ca3 `main` | lays the overlay on the plate, rebuilds the backdrop blur, holds the last frame |
| `eyewire2/index.html` | ca3 `main` | the earlier film, one dot per soma, from `cells.json` |
| `eyewire2/cap.js` | ca3 `main` | frame capture: Playwright screenshots piped into ffmpeg. `ALPHA=1` keeps transparency, `FROM=` and `TO=` render a frame range |
| `eyewire2/upstream/README.md` | ca3 `main` | the original README for the dot film |

## 1. Meshes

```bash
pip install caveclient cloud-volume trimesh fast-simplification
python eyewire2/fetch_meshes.py --datastack stroeh_mouse_retina \
    --center 42900 43384 2007 --radius-um 45 --faces 40000 --out eyewire2/meshes
```

- Datastack `stroeh_mouse_retina`. Voxels are 16 x 16 x 40 nm. `--center` is in
  voxels and the radius is measured in the plane.
- The token is read from the `CAVE_TOKEN` environment variable or from
  `~/.cloudvolume/secrets/cave-secret.json`. Never pass it on the command line
  and never commit it.
- Cells are chosen from `manifest.csv` (in the ca3 repo, 671 KB, not copied
  here): every completed cell whose soma lies inside the radius, nearest first,
  up to `--limit` (default 200). Or give `--ids`.
- Each mesh is converted from nanometres to micrometres and quadric decimated
  with trimesh and fast-simplification. **40,000 triangles per cell is the target
  that has worked. The script's own default is `--faces 60000`, so pass
  `--faces 40000`.**
- A cell already on disk is skipped, so it is resumable.
- `index.json` records the datastack, the resolution, and for each cell its
  segment id, proofreader, type, completion date and soma in micrometres.

Meshes are never committed. `*.glb` and `meshes/` are ignored.

## 2. The page

`col3d.html` loads `meshes/index.json` and each GLB (or another folder with
`?meshes=path`), builds one `MeshStandardMaterial` per cell, and exposes the
contract `cap.js` needs:

```js
window.READY          // true once every mesh and the fonts have loaded
window.TOTAL_FRAMES   // length of the film at 30 fps
window.setFrame(i)    // draw frame i, deterministically
```

Everything is a pure function of the frame number. That is what makes a headless
capture identical to what plays in a browser, and it is the one design rule for
any new page on this path.

It expects four things beside it that are not in this snapshot: `meshes/`,
`fonts/inter-latin.woff2`, the `scifi/` components (in the ca3 repo under
`eyewire2/scifi/`), and three.js at `../web/vendor/` (`three.module.min.js`
and `loaders/GLTFLoader.js`, which live in the ca3 repo under `web/vendor/`).

Lighting is a hemisphere light plus a key and a rim directional light, ACES
filmic tone mapping. That is a different look from the Blender house style and
it is deliberate: this path trades the subsurface look for reach.

## 3. Capture, as two layers

Words go on in post, never in the render. RENDERING.md section 9 has the rule.
The picture and the words are captured separately and put together afterwards.

```bash
python -m http.server 8766 --directory <the folder that contains eyewire2/ and web/>
export FFMPEG=...   # an ffmpeg with libx264

# beat check first
ANIM_URL=http://127.0.0.1:8766/eyewire2/col3d.html node eyewire2/cap.js probe 2 10 20

# plate: the cells alone. The slow part, done once
eyewire2/render.sh 'col3d.html?meshes=meshes&layer=plate' plate.mp4
# overlay: every word on a transparent background. Minutes
ALPHA=1 eyewire2/render.sh 'col3d.html?meshes=meshes&layer=overlay' overlay.mov
# composite
python3 eyewire2/compose.py plate.mp4 overlay.mov film.mp4
```

- `probe <seconds...>` writes one PNG per time. **This is the beat check for this
  path.** With no `layer` the page draws both layers, so the stills show the
  words on the picture. Look at them before rendering.
- `render.sh` renders in chunks of 240 frames (`CHUNK=`) and keeps the finished
  ones, so after a restart the same command picks up where it stopped. It
  expects the site on port 8766 and `FFMPEG` set. The plate stops where the
  action freezes; the overlay runs to the end.
- To change a word: edit `captions.json`, capture the overlay again, run
  `compose.py`. The plate is not touched.
- `compose.py` holds the plate's last frame for as long as the overlay runs, and
  rebuilds the blur behind the closing card from the plate. It needs the
  `imageio-ffmpeg` package unless `FFMPEG` is set.
- The plate is H.264, `crf 17`, `yuv420p`, 1920x1080 at 30 fps. The overlay is
  PNG frames in a MOV, straight alpha.
- Chromium runs with SwiftShader (`--use-angle=swiftshader`), so WebGL renders on
  the CPU. Slow per frame, and it needs no GPU at all.
- `cap.js` requires Playwright from `/opt/node22/lib/node_modules/playwright`,
  the path in the cloud sandbox it was written in. Elsewhere, change that line to
  `require('playwright')` after `npm install playwright`.

## 4. After capture

The mp4 goes through the same review and publish steps as a Blender render.
See RENDERING.md, sections 10 and 11.
