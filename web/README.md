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
The files in `eyewire2/` here are a snapshot taken 4 October 2026.

| file | from | what |
|---|---|---|
| `eyewire2/fetch_meshes.py` | ca3 `main` | pulls meshes through CAVE, decimates, writes `<segid>.glb` and `index.json` |
| `eyewire2/col3d.html` | ca3 branch `claude/volume-page-content-review-robkz4` | the 3D column of cells in three.js. On `main` of ca3 since 5 October; this copy is the branch version from the day before |
| `eyewire2/index.html` | ca3 `main` | the earlier film, one dot per soma, from `cells.json` |
| `eyewire2/cap.js` | ca3 `main` | frame capture: Playwright screenshots piped into ffmpeg |
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

It expects three things beside it that are not in this snapshot: `meshes/`,
`fonts/inter-latin.woff2`, and three.js at `../web/vendor/` (`three.module.min.js`
and `loaders/GLTFLoader.js`, which live in the ca3 repo under `web/vendor/`).

Lighting is a hemisphere light plus a key and a rim directional light, ACES
filmic tone mapping. That is a different look from the Blender house style and
it is deliberate: this path trades the subsurface look for reach.

## 3. Capture

```bash
python -m http.server 8765 --directory <the folder that contains eyewire2/ and web/>
ANIM_URL=http://127.0.0.1:8765/eyewire2/col3d.html node eyewire2/cap.js probe 2 10 20
ANIM_URL=http://127.0.0.1:8765/eyewire2/col3d.html node eyewire2/cap.js full column.mp4
```

- `probe <seconds...>` writes one PNG per time. **This is the beat check for this
  path. Look at the stills before running `full`.**
- `full out.mp4` steps every frame, screenshots it and pipes PNGs into ffmpeg:
  H.264, `crf 17`, `yuv420p`, `+faststart`, 1920x1080 at 30 fps.
- Chromium runs with SwiftShader (`--use-angle=swiftshader`), so WebGL renders on
  the CPU. Slow per frame, and it needs no GPU at all.
- `cap.js` requires Playwright from `/opt/node22/lib/node_modules/playwright`,
  the path in the cloud sandbox it was written in. Elsewhere, change that line to
  `require('playwright')` after `npm install playwright`.
- Its default URL is `http://127.0.0.1:8765/anim.html`. Always set `ANIM_URL`.
  `FFMPEG` overrides the ffmpeg binary.

## 4. After capture

The mp4 goes through the same review and publish steps as a Blender render.
See RENDERING.md, sections 10 and 11.
