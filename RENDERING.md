# Rendering neurons

For a session that has never seen the machine. One section per stage, in the
order the work happens. Each section says what to run, what has worked, and
where the longer reasoning lives.

Where an older document already says something, it is quoted and named. The
long form is in [notes/RENDERING_NEURONS.md](notes/RENDERING_NEURONS.md) (the
playbook, 15 sections, each written after something went wrong) and
[notes/ORGANISATION.md](notes/ORGANISATION.md).

Contents:
[1 Machine](#1-the-machine-and-the-environment) ·
[2 Download](#2-download) ·
[3 Decimate](#3-decimate) ·
[4 Import](#4-import) ·
[5 Material and light](#5-material-and-lighting) ·
[6 Animate](#6-animate) ·
[7 Beat check](#7-the-beat-check) ·
[8 Queue](#8-queue) ·
[9 Encode](#9-encode) ·
[10 Review](#10-review) ·
[11 Publish](#11-publish) ·
[12 No GPU](#12-the-path-with-no-gpu) ·
[13 Per project](#13-the-four-projects-end-to-end) ·
[14 Open questions](#14-open-questions)

---

## 1. The machine and the environment

**Aurelius.** Windows 11, NVIDIA RTX 3090 (24 GB), 63.7 GB RAM. It is the only
machine that renders. Everything else can read this repo, queue jobs and use the
web path in section 12.

From `ORGANISATION.md`:

> **Publishing and production are different problems and want opposite shapes.**
> Publishing is per dataset. Production is per *machine*. There is one GPU, one
> scene cache convention, one playbook, one set of measured machine limits.
> So: **many site repos, one production directory, one queue.**

| thing | where on Aurelius |
|---|---|
| production root | `D:\Meshes\` (flat: scripts, notes, mesh folders, scene caches) |
| renders | `D:\Meshes\renders\` |
| Python | `D:\Meshes\.venv\Scripts\python.exe`, Python 3.10.5 |
| Blender | `C:\Program Files\Blender Foundation\Blender 4.4\blender.exe` |
| ffmpeg | on PATH (8.0.1, installed with winget) |
| CAVE token | `~/.cloudvolume/secrets/cave-secret.json` |
| CAVE server map | `~/.cloudvolume/secrets/cave_datastack_to_server_map.json` |
| HDRI | `C:\Users\amyle\Documents\cyclorama_hard_light_4k.hdr` |
| legacy mesh library | `C:\Users\amyle\meshparty\` **read only, never write there** |
| queue | `D:\Meshes\queue.ps1`, a shim onto `C:\Users\amyle\render-queue\queue.ps1` |
| review shelf | `C:\Users\amyle\review\review.ps1` |

Blender 3.4 and a Blender 5.0.1 (`D:\Blender5`) are also installed. Every script
here targets **4.4** and the queue runs 4.4.

### The Python environment

A plain venv, not conda. The exact versions are in
[requirements-aurelius.txt](requirements-aurelius.txt). The ones that matter:

```
caveclient 8.2.1        cloud-volume 12.14.2     meshparty 2.0.3
pymeshlab 2025.7.post1  trimesh 4.12.2           fast-simplification 0.2.0
numpy 2.2.6             pandas 2.3.3             scipy 1.15.3
pillow 12.3.0           pyarrow 25.0.0           h5py 3.16.0
```

To rebuild it elsewhere:

```powershell
py -3.10 -m venv .venv
.venv\Scripts\python -m pip install caveclient cloud-volume meshparty pymeshlab trimesh fast-simplification pandas scipy pillow pyarrow h5py matplotlib
```

**Blender's own Python has numpy but not scipy or pandas.** Anything that needs
them (Dijkstra, KD trees, parquet) runs in the venv and hands Blender an `.npz`
or a CSV. That is why every project has "fields" scripts beside its Blender
scripts.

### The token

`caveclient` and `cloud-volume` both read `~/.cloudvolume/secrets/cave-secret.json`.
Create it once per machine with `client.auth.save_token(token=...)` after getting
a token from the CAVE site for the datastack. **Never put a token in a script, a
command line, a note or this repo.** `.gitignore` here refuses `*secret*.json`.

The scripts pass it like this, which is the pattern to copy:

```python
c = caveclient.CAVEclient("stroeh_mouse_retina")
cv = CloudVolume(c.info.segmentation_source(), use_https=True, progress=False,
                 secrets=c.auth.token)
```

### Running these scripts

The files in this repo are **copied unmodified** from the flat `D:\Meshes` and
sorted into folders. Most carry absolute paths, and every Blender script loads
the core module by path:

```python
PATH = r"D:\Meshes\ca3_animation.py"
exec(compile(open(PATH, encoding="utf-8").read(), PATH, "exec"), ns)
```

So:

- **On Aurelius**, run the originals in `D:\Meshes`. [MANIFEST.csv](MANIFEST.csv)
  maps each file here to its original path. If you change a script here, the
  change does nothing until the copy in `D:\Meshes` changes too.
- **On another machine**, put the scripts for your project and
  `blender/common/ca3_animation.py` in one flat folder and replace `D:\Meshes`
  with that folder. `ca3_animation.py` itself honours three environment
  variables, `CA3_ROOT`, `CA3_MESHPARTY` and `CA3_HDRI`. The other scripts do
  not, so their paths have to be edited. The `paths` column of
  [MANIFEST.csv](MANIFEST.csv) lists what each one touches.

### Before launching Blender for any reason

From the old front door of `D:\Meshes`:

> **One render at a time. Never start one if one is already running.** This
> includes a two frame probe, a single test still, anything.
>
> ```powershell
> Get-Process blender -ErrorAction SilentlyContinue   # must return nothing
> ```
>
> Two Blenders on one 24 GB card is how the 29 and 30 July overnight runs were
> lost.

And never render during the day unless Ames asks. Stills for a beat check are
the exception, when the GPU is free.

### Measured limits

> RTX 3090, 24 GB VRAM, 63.7 GB RAM: 8,858 faces per MB of OBJ. 124M faces
> proven. 81M faces renders at 27 s a frame at 1080p and 64 samples; 53M at
> 6.6 s. The jump is steep, so past about 80M expect trouble.

Add up the faces before you build a scene. It decides the decimation target.

---

## 2. Download

Two kinds of source. **CAVE** needs the token and gives the current
segmentation. A **public precomputed** bucket needs nothing and is frozen at a
release. Both return vertices in **nanometres**.

| project | datastack | voxel size (nm) | mesh source | script |
|---|---|---|---|---|
| CA3, mouse hippocampus | `zheng_ca3` | 18 x 18 x 45 (measured, see below) | CAVE | `download/ca3/` |
| BANC, fly brain and nerve cord | `brain_and_nerve_cord` | 4 x 4 x 45 | CAVE, or public `precomputed://gs://lee-lab_brain-and-nerve-cord-fly-connectome/neuron_meshes` | `download/banc/` |
| MICrONS, mouse visual cortex | `minnie65_phase3_v1` (nucleus table). `minnie65_public` is in the server map | 4 x 4 x 40 | Ames's meshparty library. No download script on disk, see section 14 | none |
| Eyewire II, mouse retina | `stroeh_mouse_retina` | 16 x 16 x 40 | CAVE | `download/retina/`, `web/eyewire2/fetch_meshes.py` |

Voxel size only matters when you convert a table position given in voxels.
Mesh vertices are already nanometres. **Check units, do not assume them**: the
CA3 synapse table stores `ctr_pt_position` in nanometres, and BANC synapse
tables differ per version, so read `voxel_resolution` from the table metadata.
The CA3 figure of 18 x 18 x 45 comes from `inhib_fields.py`, which compared a
nucleus row in voxels against the same soma in nanometres.

### The pattern that works

Every current downloader does the same five things. Copy
`download/retina/retina_download.py` when starting a new one.

1. **Cap the worker pool at 4.** "An 8 worker pool on the CA3 fetch hit 90
   processes and 40.7 GB resident and had to be killed."
2. **Skip anything already on disk**, so a restart loses nothing.
3. **Write atomically**: write `<id>.obj.tmp.obj`, then `os.replace`. A partial
   file otherwise gets globbed into a render. A `*.tmp.obj` name still matches
   `*.obj`, so exclude it when globbing.
4. **Retry 502, 503, 504 and timeouts with backoff** (3 s, 6 s, 12 s). They are
   the meshing service shedding load, not a bad id. Fail fast on anything else.
5. **Give CAVE calls a timeout.** "CAVE will leave sockets hanging forever", so
   `pull_synapses.py` patches a timeout onto `requests.Session.request`.

Downloads are network and disk bound. They are safe to run while a render is
going. Decimation is not, it is CPU and RAM heavy.

### CA3 (`zheng_ca3`)

```powershell
D:\Meshes\.venv\Scripts\python.exe D:\Meshes\ca3_layers_download.py     # into an .h5 cache
D:\Meshes\.venv\Scripts\python.exe D:\Meshes\download_hero.py           # native resolution
D:\Meshes\.venv\Scripts\python.exe D:\Meshes\download_gradient.py       # download and decimate in one pass
```

- These use meshparty: `trimesh_io.MeshMeta(cv_path=client.info.segmentation_source(),
  disk_cache_path=..., map_gs_to_https=True)`, then `mesh_meta.mesh(seg_id=...)`.
  The full resolution mesh lands in an `.h5` cache, so decimation can be rerun
  at another target without downloading again.
- **`lod=` does nothing here.** Identical face counts at lod 0, 1, 2 and 3.
- About 2.4 minutes and 225 MB per cell at native resolution. Decimate at
  download time (`download_gradient.py`) and it is about 5.3 MB per cell.
- The scripts pin **materialization 671**. A later note says 671 was retired and
  to use **673**. See section 14.
- Tables: `synapses_ca3_v1` (36.8M rows) and `c3_nuclei_v1`. `ca3_cell_type` and
  `ca3_cell_id` exist but are empty, so cell type is not readable from CAVE.
- `pull_synapses.py` pulls the whole synapse table in about 10 minutes:
  "id-range chunks hit the primary-key index and run 10x faster than `limit=`
  queries, and 6 threads give ~100k rows/s."
- EM imagery for a background plate is public:
  `precomputed://gs://zheng_mouse_hippocampus_production/v2/img_aligned_sharded_18nm`
  (`pull_em_slice.py`, mip 4).
- The legacy CA3 populations in `C:\Users\amyle\meshparty` are far coarser than
  the source (2.1 faces/um2 against 74 to 76). `redownload_population.py` pulls
  a population again from CAVE rather than trusting them.

### BANC (`brain_and_nerve_cord`)

```powershell
# public bucket, no token. The ids come from D:\Meshes\banc\walking_steering_ids.json
D:\Meshes\.venv\Scripts\python.exe D:\Meshes\banc_walkingsteering_download.py probe
D:\Meshes\.venv\Scripts\python.exe D:\Meshes\banc_walkingsteering_download.py

# CAVE graphene source, token needed. A cast named in D:\Meshes\banc\cast.json or <name>_ids.json
D:\Meshes\.venv\Scripts\python.exe D:\Meshes\banc_download.py shotB
```

- Public source: `CloudVolume("precomputed://gs://lee-lab_brain-and-nerve-cord-fly-connectome/neuron_meshes",
  use_https=True)`, then `cv.mesh.get(int(id))`. No `lod` argument on this source.
- Use the public bucket when the render has to register with a Neuroglancer
  scene, because it is the same source the scene draws.
- "Check the bucket before downloading. `HEAD <mesh_dir>/<id>:0` returns 200 or
  404, and a bogus control ID must 404 in the same run."
- The scripts query `cell_info` at **materialization 888**.
- Native is about 3.1M faces and 60 to 190 MB per cell.
- render-queue also carries `behavior_cells/download_behavior_cells.py`, which
  needs only the standard library and writes binary PLY in nanometres
  (`--scale 0.001` for micrometres) from the same public bucket.
- BANC y increases posteriorly. Read
  [notes/banc/BANC_RENDER_HANDOFF.md](notes/banc/BANC_RENDER_HANDOFF.md) section
  3.3 before trusting any coordinate.

### MICrONS

The 38 proofread cells on disk were not downloaded by anything in `D:\Meshes`.
`decimate_microns_area.py` reads them from four folders of Ames's meshparty
library: `giant proofread pycs`, `L1 cluster`, `L5 cluster`, `L5 cluster 2`, at
about 691 MB each. Soma positions came from `nucleus_detection_v0` on
`minnie65_phase3_v1`, in 4 x 4 x 40 nm voxels, and "root ids go stale as
proofreading proceeds, so resolve them forward through the chunkedgraph before
looking anything up". How to fetch new MICrONS cells is an open question.

### Eyewire II retina (`stroeh_mouse_retina`)

```powershell
D:\Meshes\.venv\Scripts\python.exe D:\Meshes\retina_download.py
```

- Reads root ids from `D:\Meshes\retina\functional_cells.csv` and writes full
  resolution OBJ into `D:\Meshes\retina\meshes_full\`.
- **Always pull full resolution.** The meshparty downsampled copies of the same
  cells are 10,122 fragments where the original is one object, and cannot be
  decimated further without breaking branches.
- The server is `https://global.daf-apis.com`, set in the server map file.
- For calcium data, "join 2P to EM on soma coordinates, not root ids".
- For a population of small cells with no GPU, `web/eyewire2/fetch_meshes.py`
  does download and decimation in one step. See section 12.

---

## 3. Decimate

The rule, from the playbook section 13:

> **Never budget in MB or in a fixed face count.** Cells differ in size by more
> than ten times, so only a density transfers.

Measure the surface area, multiply by a density in faces per square micrometre,
and choose the density by how large the cell will be on screen.

| faces/um2 | what it looks like |
|---|---|
| 304 | a full resolution retina cell |
| **74 to 75** | indistinguishable from the original. Use for close ups |
| **37** | thin processes begin to bead. The floor for anything looked at directly |
| 18.5 | broken into dotted strings. Fine only when a cell is a few pixels wide |
| 7.9 | the old downsampled library. Far past broken |

### Targets that have worked

| project | shot | target | result |
|---|---|---|---|
| CA3 | full population, cell bodies and dendrites | 5 faces/um2 (`max(MIN_FACES, area * 5.0)`) | about 5.3 MB a cell against 225 MB native |
| CA3 | legacy library folders | `meshparty_decimate_hq.py`: strip small components, per folder density, keep floor | `D:\Meshes\hq\`, 13 GB |
| CA3 | the featured single cell and its six fibres | none, native | 4.47M faces, so the thorns resolve |
| BANC | 81 cell poster, 1600 x 1200, about 1 um a pixel | 10 faces/um2 | about 5 MB a cell |
| MICrONS | 38 cells, cortex orbit | 100 faces/um2 | about 81M faces, at the edge of comfortable |
| retina | 364 cell mosaic, cells that light up | 35 faces/um2 | beading is sub pixel at mosaic scale |
| retina | 364 cell mosaic, dim background cells | 6 faces/um2 | invisible at that brightness |
| Eyewire II, web | column of cells in three.js | 40,000 triangles a cell | plays in a browser |

The last row is a face count, not a density, which breaks the rule above. It
works there because bipolar cells are close to one size. Do not carry it to a
dataset with mixed cell sizes.

### The settings

```python
ms.meshing_decimation_quadric_edge_collapse(
    targetfacenum=target, qualitythr=0.3,
    preserveboundary=True, preservenormal=False,
    preservetopology=False,          # <-- the important one
    optimalplacement=True, autoclean=True)
```

- **`preservetopology=False`, always.** These meshes carry thousands of
  connected components. With it on, "a run targeting 40% kept 95.4%".
- **Clean first, by visibility.** "30.5% of a full resolution mesh is geometry
  no ray can reach." Remove it with ambient occlusion, then decimate:

  ```python
  ms.compute_scalar_ambient_occlusion()
  ms.compute_selection_by_scalar_per_vertex(minq=-1e9, maxq=1e-9)
  ms.meshing_remove_selected_vertices()
  ```

  Ambient occlusion in this pymeshlab build "spans 0 to about 16, not 0 to 1".
  The enclosed set is exactly zero.
- **Do not remove small connected components** on retina meshes. They are not
  litter, they touch the cell. The CA3 and BANC passes do drop components
  under 25 faces. Decide per dataset, and look.
- **Measure area after cleaning**, so the budget is spent on surface that
  survives.
- **Watch any keep floor.** `max(MIN_FACES, area*density, faces*0.40)` looks
  safe until the 0.40 wins on every cell: that pushed a render from under 6 s a
  frame to 128 s. Print before and after face totals for the whole folder.
- **Strip stray vertices.** "Meshes routinely carry 2 to 8 vertices thousands of
  um from the rest." Use percentile bounds (0.5 and 99.5) for any extent.
- pymeshlab writes an `.mtl` beside each OBJ and an `mtllib` line into it.
  `retina_build_library.py` neutralises the line in place, or Blender logs an
  error per cell and real failures get buried.
- **Mesh building is memory bound past about 8 processes.** Twelve builders ran
  slower than six. Watch free RAM, not CPU.

### What to run

```powershell
# retina: clean, then decimate to a density, two budgets
D:\Meshes\.venv\Scripts\python.exe D:\Meshes\retina_build_library.py --workers 4 --ds-density 35 --ghost-density 6

# BANC: see the plan before doing it
D:\Meshes\.venv\Scripts\python.exe D:\Meshes\banc_walkingsteering_decimate.py plan
D:\Meshes\.venv\Scripts\python.exe D:\Meshes\banc_walkingsteering_decimate.py

# MICrONS
D:\Meshes\.venv\Scripts\python.exe D:\Meshes\decimate_microns_area.py workers=3 density=100

# any folder of OBJ: report first, then --apply
D:\Meshes\.venv\Scripts\python.exe D:\Meshes\mesh_clean.py --dir D:\Meshes\retina\meshes --n 6
```

When two variants disagree, do not argue from numbers.
`decimate/common/mesh_compare_render.py` renders both from one camera.

---

## 4. Import

```python
bpy.ops.wm.obj_import(filepath=p)
```

**The coordinate trap.** From the playbook section 5:

> **Blender's OBJ importer maps file `(x,y,z)` to `(x,-z,y)` but does NOT bake
> it into the vertices.** It leaves them in file coordinates and puts a 90° X
> rotation on the *object*.
>
> - **Comparing external data against mesh vertices: do NOT convert.**
> - **Placing an object in the scene: DO convert.**

Convert once, on the way in, and assert it:

```python
assert max(abs(v) for v in point_in_scene) < TARGET_SIZE, "coordinate spaces disagree"
```

`matrix_world` and `bound_box` read stale until
`bpy.context.view_layer.update()`.

**Units.** Vertices arrive in nanometres. Two conventions are in use:

- **CA3** normalises the whole population so its longest axis is
  `TARGET_SIZE = 10` Blender units. This is safe at about 1000 um across
  because the dendrites are thick.
- **BANC, MICrONS** use **one Blender unit per micrometre** (import, then scale
  by 0.001). MICrONS squeezed into 10 units "rendered as disconnected coloured
  specks", because a half micrometre dendrite became 0.0046 units.

For anything new, use micrometres. Then set the camera clip planes, because the
default `clip_end` is 100 units and "a subject 700 units across renders as an
empty frame".

**Cache the scene.** "Rebuilding a large scene from OBJ took 554 s. Saving it
as a `.blend` and reopening took 6 s." Import once (`build_cache.py`), save the
`.blend`, and have every render script open it and rebuild only materials,
lights, camera and keyframes. Caches live in `D:\Meshes` and are never committed:

| cache | size | what |
|---|---|---|
| `ca3_scene.blend` | 6.9 GB | the CA3 population, 984 objects, 124M faces |
| `ca3_scene_partners.blend` | 7.2 GB | plus the partner cells |
| `ladder_scene.blend` | 6.3 GB | the scale ladder |
| `gradient_scene.blend` | 1.2 GB | 304 cells for the convergence gradient |

**Other import rules**

- Skip `*.raw.obj` and `*.tmp.obj` when globbing.
- Clear imported materials and assign your own.
- Strip faces with an edge over 20,000 nm (`strip_stray_faces`).
- A glTF import sets `rotation_mode` to QUATERNION, so setting `rotation_euler`
  on it is silently ignored.
- Dense neuropil is opaque at every distance. To show one cell, draw fewer
  cells. Moving the camera only changes which wall you see.

---

## 5. Material and lighting

All of it lives in `blender/common/ca3_animation.py`. Every project's scripts
load that module and call three functions, so the look is one decision made once:

```python
g["build_world"](scene)                 # the HDRI
g["build_lights"](scene, TARGET, root)  # key, fill, rim, top, scaled to the subject
g["apply_render_settings"](scene)       # engine, colour management, bloom, motion blur off
```

### The one rule that matters most

> **Neurons are submerged. Submerged tissue is not glossy.**

```python
TISSUE_IOR_IN_WATER = 1.04   # 1.38 membrane / 1.33 extracellular fluid, NOT 1.38
SURFACE_ROUGHNESS   = 0.62
SUBSURFACE_WEIGHT   = 0.42   # scattering, not reflection, is what we should see
SUBSURFACE_SCALE    = 0.012  # Blender units, about 1 um of tissue at TARGET_SIZE 10
COAT_WEIGHT         = 0.0    # the clearcoat was the main source of gloss
TRANSMISSION_WEIGHT = 0.0    # full transmission reads as glass, not tissue
EMISSION_STRENGTH   = 0.04
```

A diffuse only shader is not the answer either, it goes flat. Keep the
Principled BSDF and remove the Fresnel.

### Always light the scene

> **Structure and anatomy are SHADED. Emission is for SIGNAL**, where
> brightness carries a measurement. **Never ship a frame whose only light
> source is the material's own emission.** The tell: if you cannot find a soma
> in a frame full of cells, the scene is not lit.

```python
WORLD_STRENGTH = 0.38     # HDRI, cyclorama_hard_light_4k.hdr, rotated 40 degrees
KEY_ENERGY  = 5200
FILL_ENERGY = 1500
RIM_ENERGY  = 2400
TOP_ENERGY  = 1800
```

The HDRI is the scene's only external file. If its path does not resolve the
world goes unlit and nothing reports it. Set `CA3_HDRI` on any other machine.

### Render settings

- **Engine: EEVEE Next** (`BLENDER_EEVEE_NEXT`), 64 samples for animation.
  Raytracing off.
- **View transform: Standard, not AgX.** "AgX desaturates hard, and these
  palettes depend on saturated blues and golds staying saturated."
- **Pure black background**: `film_transparent` with a black plate in the
  compositor, so the world lights the scene without appearing.
- **Motion blur off, always**, unless Ames asks. Beyond taste, EEVEE's velocity
  pass keeps three copies of the geometry and crashes past about 40M faces.
- Bloom through the compositor Glare node. In 4.4 its controls are input
  sockets, and writing `glare.threshold` sets a dead property.
- `Material.blend_method` does nothing under EEVEE Next. Use
  `surface_render_method`.
- **The BANC layer stills are the exception**: Cycles, 1600 x 1200, transparent
  with straight alpha, denoising off, because they are composited in a web app.
  The spec is in [notes/banc/BANC_RENDER_HANDOFF.md](notes/banc/BANC_RENDER_HANDOFF.md).

### Colour

- **Pick it in the render, not the picker.** Render one frame at three or four
  candidate hexes and look. `blender/common/_purple_swatch.py` is a worked example.
- The CA3 palette, in `GROUPS` in the core module: thorny pyramidal
  `#1858C7` to `#2586F5`, sparsely thorny `#8B5CE0` to `#B78CF7`, inhibitory
  `#17A06B`, mossy fibres `#E2AF5E`, presynaptic deep `#C43F92` to `#E86FB8`,
  presynaptic superficial `#F075BF` to `#F189C6`.
- **When colour encodes a measurement**, use explicit stops lerped in sRGB that
  rise in lightness: `#1D358F`, `#8E46C0`, `#FFC24A`. Never interpolate in HSV.
  Log scale a heavy tailed quantity.
- No colour jitter between cells of one population.
- Ames dislikes "pale desaturated colour, glossy surfaces, boxes around labels,
  labels with large type, anything that moves too fast to absorb."

---

## 6. Animate

### The script interface

Every animation script is run the same way and takes `key=value` arguments after
the `--`:

```powershell
& "C:\Program Files\Blender Foundation\Blender 4.4\blender.exe" --background `
    --python D:\Meshes\banc_shotB_anim.py -- frames=576 res=1080x1920 samples=64 `
    out=D:\Meshes\renders\banc_shotB.mp4
```

| argument | meaning |
|---|---|
| `frames=576` | length of the shot. 24 fps |
| `res=1920x1080` | resolution. Portrait is `1080x1920` |
| `samples=64` | render samples |
| `out=path` | the mp4, or the base name for stills |
| `stills=1,219,322` | render only these frames as PNG, from one import. The beat check |
| `still=N` | one frame. Older scripts have only this |

The parser is three lines, and a new script should copy it from
`blender/banc/banc_shotB_anim.py`:

```python
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
opts = dict(t.split("=", 1) for t in argv if "=" in t)
FRAMES = int(opts.get("frames", 576))
```

Shot specific arguments (`camdist=`, `shifty=`, `arc=`, `dof=`, `mode=`) are in
each script's header and in [INVENTORY.md](INVENTORY.md).

**Beats are fractions of `FRAMES`**, so any running time recuts cleanly.

### Rules for the motion

- **One move, not four.** "The most common note from a real viewer is 'the
  camera goes in and out too much.'" 16 to 20 degrees of orbit across a shot is
  plenty.
- **Fade, never scale from zero.** Objects carry their centring on `location`,
  so scaling "drags them in from somewhere else entirely". Key `hide_render`,
  staggered.
- **Alpha is expensive.** "Opaque frames render roughly 50x faster than
  alpha-blended ones." Fade a population with emission, not alpha.
- Long holds. Ames wants time to "see, process, discover and contemplate".
- BEZIER with `AUTO_CLAMPED` handles for the camera. LINEAR for anything that
  stands for constant physical velocity, such as a travelling spike.
- **Solve the framing.** Render stills, measure the lit bounding box
  (`blender/common/framecheck.py`), and compute the distance. Aim for 85 to 90
  percent height fill. Sample the whole move to find the fullest frame.
- **Portrait is not landscape with the numbers swapped.** The correction to
  camera distance is the aspect ratio, 1.78.
- **A shot that changes scale** must rescale its clip planes with distance and
  its light energy with the square of distance, and interpolate framing radius
  in log space.
- **A signal along real cable**: per vertex path distance along the skeleton,
  stored as a colour attribute, with an emission band animated across it. Built
  in the venv by the "fields" scripts. Detached pieces have no honest arrival
  time, so leave them dark.

### Rules for surviving a long render

- **Long renders write a PNG sequence, not an mp4.** "A BANC job died at 3.6
  hours and every frame was unrecoverable, because a partial mp4 has no moov
  atom." `retina_ds_anim.py` writes frames, skips ones already on disk, and
  encodes at the end.
- **Blender exits 0 even when the script raises.** Print a sentinel at the end
  (`[R] DONE`) and check the log for it. Never trust the exit code.
- **Labels are composited afterwards in Pillow**, never drawn in Blender. A text
  object that changes per frame needs a `frame_change` handler, "and handlers
  during a headless animation render are a known way to lose a whole run".
- Read the overlay's numbers from the same CSV the render read, so the caption
  cannot drift from the picture.
- Never put a Windows path inside a bash heredoc. `\r` and `\b` are eaten. Use
  forward slashes.

---

## 7. The beat check

**Stills at each beat, looked at, before queueing.** This is the rule with the
longest history of being skipped and paid for.

From the protocol:

> The queue will happily render 100 minutes of black. It has no idea what the
> picture should look like. So:
>
> 1. **Render single stills at each beat and LOOK at them.** Use the `stills=`
>    argument so several beats come from one import; checking them one at a time
>    costs a full re-import each, which is what makes people skip the check.
> 2. **A 2 second frame where 30 is normal means the scene is empty.** Check the
>    object or collection count in the log before believing a fast render.
> 3. Put the beat check in the `-Note`, so the next person knows it was done.

How to do it:

```powershell
Get-Process blender -ErrorAction SilentlyContinue      # must return nothing
& "C:\Program Files\Blender Foundation\Blender 4.4\blender.exe" --background `
    --python D:\Meshes\banc_shotB_anim.py -- stills=1,219,322,480 res=1080x1920 samples=64
```

Then **open the PNGs and look at them**. For each one, check:

- Is it lit? Can you find a soma?
- Is the subject in frame, with margin, at the fullest point of the move?
- Is everything that should be visible at this beat visible, and nothing else?
- Are the colours the ones intended, and saturated?
- Does the frame time match the face count?

"Numeric checks are not enough. Twice a printed diagnostic looked correct while
the image was completely wrong." And to prove an animation moves, compare two
frames. A still cannot show that a keyframe was ignored.

Keep the stills. Ames reviews them.

A subset render shows what a shot looks like. It does not show that the whole
population is covered. Say which one a still is.

---

## 8. Queue

**If you built an animation, add it to the queue and stop. Do not render it.**

```powershell
D:\Meshes\queue.ps1 status

D:\Meshes\queue.ps1 add -Project retina -Name ds_mosaic `
  -Script D:\Meshes\retina_ds_anim.py `
  -Arguments "frames=576","res=1920x1080","samples=64","out=D:\Meshes\renders\retina_ds.mp4" `
  -Minutes 120 -Note "beats 1,120,300,560 verified as stills" -AddedBy "chat: retina ds"
```

It runs at 02:00, waits for a free GPU, moves old output aside, encodes for the
web, logs, and puts the result on the review shelf. The rule set is
`RENDER_PROTOCOL.md` in [render-queue](https://github.com/amyleesterling/render-queue)
and it is authoritative. [queue/README.md](queue/README.md) is the summary.

Minutes long jobs that are not animations, such as the BANC layer stills, have
been run directly with `banc_walkingsteering_go.ps1` once the GPU was confirmed
free. Anything long goes through the queue.

---

## 9. Encode

The queue web encodes every mp4 on success, to `<name>_web.mp4`:

```
ffmpeg -y -v error -i <out> -c:v libx264 -preset slow -crf 23 -pix_fmt yuv420p -movflags +faststart <name>_web.mp4
```

From the playbook section 11:

> - **H.264, yuv420p, `-movflags +faststart`.** Non-negotiable for inline
>   playback on iOS from static hosting.
> - Even dimensions are required for yuv420p.
> - Verify the host serves **HTTP 206** on a range request.
> - **Look at the finished file**, not just the render log. Extract frames from
>   the encoded video and read them as images.

Overlays and captions go on between render and encode: `caption_video.py` for
timed captions from a JSON spec, and the per project `*_overlay.py` scripts for
keys and readouts. No box around labels, small type.

Web layers for the BANC app are lossless WebP with straight alpha, encoded and
audited by the `*_webp.py` and `*_qc.py` scripts. Each audit carries a control,
such as a copy shifted 3 px, so the test is able to fail.

---

## 10. Review

A finished render is not a wanted render. The queue puts each finished job on
the shelf at [github.com/amyleesterling/review](https://github.com/amyleesterling/review).

```powershell
C:\Users\amyle\review\review.ps1 status
C:\Users\amyle\review\review.ps1 approve -Id 1
C:\Users\amyle\review\review.ps1 reject  -Id 1 -Note "too fast through the neck"
```

Ames approves. A session does not approve on its own judgement. Before a render
reaches her, look at it yourself: extract frames from the encoded file and check
that it is lit, framed, populated and moving. Details in
[review/README.md](review/README.md).

---

## 11. Publish

```powershell
C:\Users\amyle\review\review.ps1 publish -Id 1
```

That copies the approved video and poster into the project's site repo and
prints the markup. It does not write copy and it does not commit.

| project | site repo on Aurelius | live |
|---|---|---|
| ca3 | `C:\Users\amyle\ca3` | amyleesterling.github.io/ca3/ |
| banc | `C:\Users\amyle\banc` | amyleesterling.github.io/banc/ |
| microns | `C:\Users\amyle\microns` | amyleesterling.github.io/microns/ |
| retina | `C:\Users\amyle\retina` | amyleesterling.github.io/retina/ |

Then, in the site repo:

- Every `<video>` needs `controls playsinline muted loop` and a poster.
- **Crop images before they go on a site.** "Full renders are mostly black."
  Measure the lit bounding box, crop with a small margin, then scale.
- State the limits in the caption: cut off arbors, incomplete cable,
  inseparable compartments.
- Copy has no em dashes or en dashes.
- Commit, push, and **verify from the live URL**. A push is not a deploy.

---

## 12. The path with no GPU

When there is no Aurelius, or it is busy: CAVE to GLB to three.js to headless
Chromium to ffmpeg. It ran end to end in a cloud sandbox for Eyewire II.

```bash
python web/eyewire2/fetch_meshes.py --datastack stroeh_mouse_retina \
    --center 42900 43384 2007 --radius-um 45 --faces 40000 --out meshes
ANIM_URL=http://127.0.0.1:8765/eyewire2/col3d.html node web/eyewire2/cap.js probe 2 10 20
ANIM_URL=http://127.0.0.1:8765/eyewire2/col3d.html node web/eyewire2/cap.js full column.mp4
```

The same stages apply: download, decimate (40,000 triangles a cell), a beat
check (`cap.js probe`), encode, review, publish. Only the queue is skipped,
because there is no shared GPU to protect. Everything is in
[web/README.md](web/README.md).

Choose it for many small cells and for anything that should also be a live
page. Choose Blender for close ups, subsurface, depth of field and signal
travelling along cable.

---

## 13. The four projects, end to end

Paths are the originals on Aurelius. `py` is `D:\Meshes\.venv\Scripts\python.exe`
and `blender` is Blender 4.4 with `--background --python <script> --`.

### CA3

```
py ca3_layers_download.py | redownload_population.py | download_hero.py | download_gradient.py
py meshparty_decimate_hq.py                       -> D:\Meshes\hq\
blender build_cache.py                            -> ca3_scene.blend, once
blender render_from_cache.py  still=120 ...       beat check
queue: render_from_cache.py | synapse_story.py | hero_full.py | ap_six.py | scale_ladder.py | render_gradient.py
```

History, palette and the bugs already fixed:
[notes/ca3/HANDOFF_rendering.md](notes/ca3/HANDOFF_rendering.md).

### BANC

```
py banc_shotA_cast.py | banc_bodyparts.py         choose the cast from connectivity
py banc_download.py shotB                         CAVE
py banc_walkingsteering_download.py               public bucket
py banc_walkingsteering_decimate.py               10 faces/um2
blender banc_shotB_anim.py  stills=1,219,322      beat check
queue: banc_shotB_anim.py                         then banc_shotB_overlay.py
banc_walkingsteering_go.ps1 -Layers               the 1600x1200 app layers, Cycles, with audit
```

Read [notes/banc/BANC_RENDER_HANDOFF.md](notes/banc/BANC_RENDER_HANDOFF.md) first.

### MICrONS

```
(meshes: 38 cells from the meshparty library, see section 14)
py decimate_microns_area.py density=100           -> D:\Meshes\microns_area\
blender microns_column.py  res=3840x2160 samples=128 view=side      a still
queue: microns_column.py with frames= and the orbit arguments       then microns_overlay.py
```

Inputs it reads from `D:\Meshes\renders\` are in `blender/microns/data/`.

### Eyewire II retina

```
py retina_functional_table.py                     -> retina\functional_cells.csv
py retina_download.py                             -> retina\meshes_full\
py retina_build_library.py                        -> retina\meshes_clean\
blender retina_ds_anim.py  stills=1,120           beat check
queue: retina_ds_anim.py | retina_strat_anim.py   then retina_overlay.py, retina_bookend.py
```

Or the web path in section 12.

---

## 14. Open questions

Things that could not be determined from `D:\Meshes` and the three repos on
4 October 2026. They are listed rather than guessed.

1. **How the MICrONS meshes were downloaded.** The 38 cells come from four
   folders of `C:\Users\amyle\meshparty`. No script in `D:\Meshes` fetches
   MICrONS meshes, and the downloader in that library (`get-meshes.py`) is
   written for `zheng_ca3`. Which datastack, which materialization and which
   tool produced those folders is not recorded. `minnie65_public` is in the
   server map, so it has been used from this machine, but nothing on disk shows
   a mesh download from it. Until this is answered, the guide does not let
   someone download a new MICrONS cell. A downloader modelled on
   `retina_download.py` with the right datastack name would be the likely shape,
   and that is untested.
2. **Which `zheng_ca3` materialization is live.** Scripts pin 671. The old
   front door says to use 673 because 671 was retired. Not checked against the
   server.
3. **The `zheng_ca3` voxel size** is taken from one measurement in
   `inhib_fields.py` (18 x 18 x 45 nm). It was not read from the datastack info.
4. **BANC materialization.** Scripts use 888. Another note on this machine
   mentions 896. Which one new work should pin is not stated anywhere.
5. **How the CAVE token was first set up** on Aurelius. The secret file exists
   and works. Whether one token covers all four datastacks, and which login
   issued it, is not recorded. The file was not opened.
6. **`functional_cells.csv` and the calcium data are not in this repo.** The
   retina scripts need `D:\Meshes\retina\functional_cells.csv`, built by
   `retina_functional_table.py` from parquet files of calcium recordings under
   `D:\Meshes\retina\functional\`. That is another lab's data and this repo is
   public, so it was left out. Whether it can be shared, and from where a new
   machine should get it, is for Ames to say.
7. **Material left out because this repo is public.** `D:\Meshes` is tracked by
   a private repo (`ca3-rendering`). Its CA3 connectivity analysis scripts, the
   analysis sections of `HANDOFF.md`, `STATUS.md`, the Princeton cluster notes,
   an email draft and `renders/gradient_sample.csv` were not copied. They are
   listed in [INVENTORY.md](INVENTORY.md). `download_gradient.py`,
   `render_gradient.py` and `gradient_sweep.py` read that CSV, so those three
   cannot run from this repo alone.
8. **`col3d.html` here is a snapshot of a branch.** It was copied on 4 October
   from `claude/volume-page-content-review-robkz4`. It reached `main` of the ca3
   repo the next day along with the film it made. The copy here was not
   refreshed, so treat the ca3 repo as current. Its three.js vendor files, font
   and `manifest.csv` stay there.
9. **`cap.js` targets a page called `anim.html`** by default, which exists in
   neither place. It works with `ANIM_URL` set. Whether `anim.html` was a
   working name for `col3d.html` is unknown.
10. **Whether the BANC shot B cast was decimated.** `banc_shotB_anim.py` reads
    `D:\Meshes\banc\shotB\`, which `banc_download.py` fills at native
    resolution. No decimation script targets that folder. It may render native.
11. **The 23x slowdown on the 364 cell retina scene** (2.5x the geometry for 23x
    the frame time) is recorded in the playbook as unexplained, and still is.
12. **The paths problem.** The scripts carry `D:\Meshes` in absolute paths, so
    this repo documents production rather than replacing it. Making the scripts
    relocatable (one root variable, honoured everywhere) would change files that
    queued jobs point at, so it was not done here.
13. **Two working trees had uncommitted edits** when this was written: the
    clone at `C:\Users\amyle\render-queue` (README and protocol, the retime
    example) and `D:\Meshes` itself. Both were left alone. The protocol quoted
    here is the one on `main` of render-queue.
14. **Folders in `D:\Meshes` that belong to other work** were inventoried and
    not copied: `mouse-wiring` (70 GB), `fafb`, `cryoet`, `molecules`, `shiu`.
    Whether any of them should join this repo is undecided.
