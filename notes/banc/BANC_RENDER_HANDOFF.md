# BANC neuron rendering: project overview and handoff

**For an agent adding a new neuron layer to the Be the Fly experience.**
Read this before rendering anything. It is the accumulated cost of getting several
of these wrong first.

Live: https://amyleesterling.github.io/banc-explorer/
Paper: Bates, Phelps, Kim et al., *Nature* (2026), doi:10.1038/s41586-026-10735-w

---

## 1. What the project is

Be the Fly is a browser game driven by the **BANC** connectome, the first fly
connectome covering brain **and** ventral nerve cord together. The player moves a
fly with WASD: forage for fruit, escape a spider, fly a course, land on a flower.

Beside the game sits a neural HUD: a fixed view of the whole central nervous
system, brain at top, neck connective in the middle, nerve cord below. Every
neuron in the cast is drawn once in dim gray. When the player acts, the cells for
that behaviour light up in colour, in register, on the same camera.

Your job is to add a behaviour to that HUD: identify the cells, render a coloured
layer, and audit it.

**The site's standard, printed on the page:** *"Structure suggests pathways; it
does not record neural activity."* Everything below serves keeping that true.

---

## 2. The non-negotiable spec

| property | value |
|---|---|
| resolution | **1600 x 1200**, always, full canvas preserved |
| background | fully transparent |
| alpha | **straight (unpremultiplied)**, no black matte |
| encoding | **lossless WebP** |
| camera | `banc/walking_steering_camera.json`, **unchanged** |
| denoising | **off** |
| context neurons | **never** baked into an action layer |

**The stacking contract.** Layers are composited, not swapped:

```
banc-context-base.webp     always visible, bottom, #52675E gray
  + one action layer       fades in on top
```

Because an action layer draws a **subset** of the cells the base draws, its lit
pixels must fall **inside** the base's. That is the invariant to test.

**Adding cells means regenerating the base.** If your behaviour uses cells not
already in the cast, add them to `banc/walking_steering_ids.json` and re-render
`context-base`. Otherwise your neurons appear from nothing, with no resting state.
Tell the app agent the base changed, since the filename does not.

---

## 3. Pipeline: the whole procedure

### 3.0 Environment

```
python      D:\Meshes\.venv\Scripts\python.exe        (caveclient, cloudvolume, pymeshlab, trimesh, numpy, scipy, Pillow)
blender     C:\Program Files\Blender Foundation\Blender 4.4\blender.exe
work dir    D:\Meshes\
meshes      D:\Meshes\banc\walking_steering\          (native, ~60-190 MB/cell)
decimated   D:\Meshes\banc\walking_steering_dec\      (~5 MB/cell, what renders)
```

Blender ships **numpy but not scipy**. Anything needing scipy (Dijkstra, KD-trees)
must run in the venv and be handed to Blender as a `.npz`.

### 3.1 One command, once the cast is on disk

```powershell
D:\Meshes\banc_walkingsteering_go.ps1 -Layers          # every layer + audit
D:\Meshes\banc_walkingsteering_go.ps1 -Only <layer>    # just one
D:\Meshes\banc_walkingsteering_go.ps1 -DryRun          # build the scene, render nothing
```

### 3.2 Downloading meshes

Add the root IDs to `banc/walking_steering_ids.json`, then run
`banc_walkingsteering_download.py`. It is resumable: it skips what is already on
disk, so re-running after adding IDs fetches only the new ones.

The source is the **public precomputed** bucket, no auth:

```python
from cloudvolume import CloudVolume
cv = CloudVolume("precomputed://gs://lee-lab_brain-and-nerve-cord-fly-connectome/neuron_meshes",
                 use_https=True, progress=False)
mesh = cv.mesh.get(int(segment_id))          # NO lod argument on this source
mesh = mesh[int(segment_id)] if isinstance(mesh, dict) else mesh
verts, faces = mesh.vertices, mesh.faces      # nanometres
```

Three things that matter:

- **Cap workers at 4.** Eight blew resident memory to 40 GB on a comparable cast.
- **Write atomically.** Write `<id>.obj.tmp.obj`, then `os.replace`. A partial file
  otherwise gets globbed into a render and fails at import, or worse, renders
  short. Note that a `*.tmp.obj` name still matches `*.obj`, so exclude it
  explicitly when counting.
- **Check the bucket before downloading.** `HEAD <mesh_dir>/<id>:0` returns 200 or
  404, and a bogus control ID must 404 in the same run.

### 3.3 Coordinates, verified rather than assumed

| space | definition |
|---|---|
| OBJ vertices | **nanometres**, isotropic |
| Neuroglancer world | voxels, `(x/4, y/4, z/45)` |
| canonical | 4 nm units, `nm/4` |
| **Blender world** | **micrometres**, `nm/1000`, so import then `scale = 0.001` |
| synapse tables | **read `voxel_resolution` from metadata**, it differs per version |

BANC **y increases posteriorly**: brain around y = 150,000 nm, neck connective at
y = 370,000 nm, nerve cord beyond. Midline is **x = 487,478 nm**, left is higher x.

### 3.4 Decimation

```python
ms.meshing_remove_connected_component_by_face_number(mincomponentsize=25)
ms.meshing_decimation_quadric_edge_collapse(
    targetfacenum=int(area_um2 * 10),   # a DENSITY, not a global count
    qualitythr=0.3, preserveboundary=True, preservenormal=False,
    preservetopology=False,             # <-- the important one
    optimalplacement=True, autoclean=True)
```

`preservetopology=True` blocks almost every collapse on meshes with thousands of
components: a run targeting 40% once kept 95.4%. Print before/after totals for the
whole folder, because a keep-floor can silently win on every cell.

Run decimation at **BelowNormal** priority. There is one GPU on this machine and
usually another session's animation on it, and this is the CPU-heavy step.

### 3.5 Building the Blender scene

```python
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.wm.obj_import(filepath=p, forward_axis="Y", up_axis="Z")
```

**The import axis trap.** Blender's OBJ importer puts its axis flip in the
object's **rotation**, not in the vertices. With the default settings a descending
neuron appears to ascend and the brain sits at the bottom. `forward_axis="Y",
up_axis="Z"` leaves the vertices alone, and then assert it:

```python
assert max(abs(a) for a in obj.rotation_euler) < 1e-6
obj.scale = (0.001,) * 3                      # nm -> um
for poly in obj.data.polygons: poly.use_smooth = True
```

Material, the house look. Neurons are submerged, so never glossy:

```python
b.inputs["Roughness"].default_value = 0.62
b.inputs["IOR"].default_value = 1.04          # tissue in water, NOT 1.38
b.inputs["Subsurface Weight"].default_value = 0.22
b.inputs["Subsurface Radius"].default_value = (6.0, 3.0, 2.4)   # um
b.inputs["Emission Strength"].default_value = 0.03              # a lift, not the lighting
```

Camera, loaded from JSON and never hand-tuned:

```python
cam_data.sensor_fit = "VERTICAL"              # AUTO fits the WIDER axis on 4:3
cam_data.angle_y = radians(45.0)
cam.matrix_world = Matrix(cam_cfg["matrix_world"])
bpy.context.view_layer.update()               # matrix_world reads stale without this
```

Lights: a three-point area rig scaled to the subject, plus a dim world. Energy
scales with distance squared, so a rig transfers between scenes as
`energy * (dist / reference_dist) ** 2`.

Render settings that the spec depends on:

```python
scene.render.engine = "CYCLES";  scene.cycles.samples = 256
scene.cycles.use_denoising = False            # never filter across the alpha edge
scene.render.film_transparent = True
scene.render.image_settings.color_mode = "RGBA"
scene.view_settings.view_transform = "Standard"   # NOT AgX
scene.render.use_compositing = False          # no Alpha Over black plate
```

**Render several looks from one import.** Re-importing the cast per candidate is
what makes people skip the comparison, and the comparison is the point. Import
once, then loop: recolour, re-render, next.

### 3.6 The shared GPU

One GPU, several agents. Check for a running Blender before starting, and if you
built an **animation**, add it to `D:\Meshes\queue.ps1` and stop rather than
competing. Single stills are fine to render interactively. Never render during the
day without asking: the machine is loud and it is in Amy's home.

| script | does |
|---|---|
| `banc_walkingsteering_download.py` | fetch meshes from the public bucket, resumable |
| `banc_walkingsteering_decimate.py` | area-based decimation, `plan` shows targets first |
| `banc_walkingsteering_camera.py` | derives the camera and **proves** it |
| `banc_walkingsteering_poster.py` | the Blender render, `dryrun` builds without rendering |
| `banc_walkingsteering_layers_webp.py` | encode + alignment audit |

**Adding a layer is one JSON entry.** In `banc/walking_steering_layers.json`:

```json
"my-behaviour": {
  "out": "banc-my-behaviour.webp",
  "label": "WHAT THE PLAYER SEES",
  "color": "#RRGGBB",
  "description": "which cells and how they were resolved",
  "ids": [["720575941...", "CellType side", "#RRGGBB"]]
}
```

Then `-Only my-behaviour`. Because the camera is loaded from the solved JSON
rather than set per run, anything new is automatically registered with everything
that already exists.

Meshes come from the **public precomputed** source, no auth:
`precomputed://gs://lee-lab_brain-and-nerve-cord-fly-connectome/neuron_meshes`

---

## 4. The identification gate. This is where the real work is.

**Never render a neuron you have not resolved.** Two of these jobs were stopped at
this gate and both were right to stop.

For every candidate, verify: exact type tag, root ID and lineage, anatomical
hemisphere, soma and arbor positions, mesh present in the frozen source, and
agreement with published morphology. Query `cell_info` at the project's
materialization (**v888**) on datastack `brain_and_nerve_cord`.

**Always run a control.** A presence check that returns "all present" means
nothing unless a deliberately bogus ID returns 404 in the same run. Every check in
this project carries one.

### What has actually gone wrong

- **DNg70.** Two IDs were supplied as a bilateral pair. BANC puts the `DNg70` label
  on two *different* current cells, and tags one of the supplied cells `DNxn180`.
  Rendered as supplied but flagged, not silently accepted.
- **wPN1.** Named in the wing-grooming literature. All 380,392 `cell_info` rows and
  all 11,029 distinct type labels scanned: **zero** contain "wpn". The cell has no
  EM identity anywhere; it was defined by light microscopy. The authorized MANC
  crosswalk was also impossible, since those tables hold **0 annotations**. Job
  stopped, nothing rendered.
- **DNg12.** 28 cells carry the bare tag; 16 more carry only `DNg12_a` or `_b` and
  are **disjoint** from the bare set, so "the population" is 28 or 44 depending on
  reading. Two cells carry both mutually exclusive subtypes. Stopped and asked.

**Stale root IDs are not automatically wrong.** The mesh bucket is a frozen
snapshot, so an old ID still renders. Map it forward with the chunkedgraph: if it
lands on the cell CAVE names, it is the right neuron at an earlier proofreading
state. That rescued four of eleven IDs in the feeding and threat batches.

### Laterality

Determine anatomical side from **mesh geometry**, never from screen position.
Midline is **x = 487,478 nm**, calibrated on the DNa01 pair; **left is the higher-x
side**. Because the camera's right vector is dominated by +x, the animal's left
appears on the **right** of the frame. That is correct and counter-intuitive.

**Anatomical side is not behavioural direction.** Name files
`anatomical-left` / `anatomical-right` and keep `behavioral_direction_mapping`
as `pending` until someone validates it.

---

## 5. Rendering craft

**Shading.** Neurons are submerged, so never glossy: `IOR 1.04` (tissue in water,
not 1.38), roughness 0.62, subsurface carries the softness. View transform
**Standard**, never AgX, which desaturates these palettes.

**Sensor fit must be VERTICAL.** Blender's AUTO fits the *larger* axis, which on a
4:3 landscape frame is the width, and the framing silently solves on the wrong
axis.

**Decimation is a density, not a count.** Target faces per µm² of surface area.
At this camera the frame is ~0.76 µm per pixel, so 10 faces/µm² is ample: it took
the 122-cell cast from 120M faces to 9.6M with no visible loss. Use
`preservetopology=False`, or topology preservation blocks almost every collapse.
Always print before/after totals: a keep-floor can silently win on every cell.

**Exposure is measured, not eyeballed.** The first light rig on this project blew
**99.7%** of lit pixels to pure white and the neurons rendered as white string.
Sweep a light multiplier, measure clipping and saturation on solid pixels, tile the
candidates and look. Current default `light=0.038` gives mean luminance 149 with
0.8% clipped.

**Always render one test frame and look at it.** That is what caught the above.

---

## 6. Auditing. Every claim gets a control.

The encode step measures four things and fails loudly:

**Straight alpha.** Compare the brightness of semi-transparent edge pixels against
fully opaque interior pixels. Straight alpha scores ~1.0. Run the same test on a
deliberately premultiplied copy as the control: it scores ~0.22. If the control
does not separate, the test proves nothing.

**Registration.** Every action layer's lit pixels inside the base: expect 99.9%+.
Control: shift the mask 3 px sideways, which should drop to 89 to 98%.

**Alpha round-trip.** Max delta through the encoder must be **0/255**.

**Transparent-pixel cleanliness.** With denoising off, max RGB under a fully
transparent pixel is **0**. Denoising filters across the alpha boundary and puts a
colour fringe there, which is why it is disabled.

---

## 7. Animated layers

Two sequences exist, built two different ways. **Pick the honest one.**

**Head-to-tail luminance sweep** (`banc_flight_dodge_anim.py`). A pulse along the
neuron's own anterior-posterior extent. Use when there is no skeleton, and say so:
it is not branch-specific conduction and must not be described as such.

**Geodesic skeleton propagation** (`banc_dng12_anim.py`). The real method. Fetch
the CAVE skeleton, pull synapses both polarities, map them to skeleton nodes, find
the input-dominant region from the post-minus-pre balance, then Dijkstra outward.
Branches light by path distance, so the signal forks where the arbor forks.

**The trap that will cost you the whole result:** `synapses_v3` positions are in
**[16, 16, 45] nm** units while `v1`/`v2` are already nanometres. Read
`voxel_resolution` from table metadata, never hardcode it. Hardcoding maps every
synapse to the wrong node **silently**. Control: the three tables should agree at
~1.4 µm median synapse-to-skeleton distance. Use **`synapses_v2`**: `v1` is
deprecated by its owner, `v3` is flagged still-in-testing.

Conventions: 24 fps, non-looping, **first and last frames fully transparent** so
the sequence starts and ends clean. Required disclaimer: *"Explanatory signal
animation derived from skeleton geometry and synapse-polarity distributions; not
recorded action potentials or measured conduction timing."*

---

## 8. Past renders, as worked examples

All 1600x1200 lossless WebP, same camera, in `banc-explorer/public/`.

| layer | cells | colour | notes |
|---|---|---|---|
| `banc-context-base` | **122** | `#52675E` | the gray bed everything composites onto |
| `banc-forward` | 6 | scene | DNg100, AN09B029_b, AN02A002 pairs |
| `banc-backward` | 4 | `#ff1493` | MDN |
| `banc-turn-left` / `-right` | 2 each | `#ff1493` | DNa01 + DNa02 per hemisphere. DNa02 sides were **derived**, not given: CAVE put them at the neck connective, so side came from mesh geometry calibrated on DNa01 |
| `banc-eat` | 6 | `#FFC857` | DNg70, DNp44, DNp62. DNg70 pair flagged |
| `banc-threat-walk` | 5 | `#FF6B5F` | DNp42, DNg55, DNge053. **THREAT RESPONSE**, never "detection" |
| `banc-flight-dodge-dnp03-*` | 2 / 1 / 1 | `#FF8FA8` | plus two 12-frame sequences |
| `banc-groom-head-dng12` | 28 | `#C7A6F3` | plus a 16-frame geodesic sequence |

**The EPG set is different and must not be mixed in.** 53 FAFB ellipsoid-body
cells, a base plus 16 heading overlays, shipped in `public/epg/` and wired into the
app, with the 53 per-cell masters kept in `D:\Meshes\renders\epg\cells\`. Different
dataset, **different camera**, internally registered but **not** registered with
any `banc-*` layer. Never composite one over the BANC base.

### Known gaps, as of this writing

| gap | detail |
|---|---|
| **DNg02 flight throttle** | `flight-forward` and `flight-reverse` have **no `src` at all**. 26 root IDs already resolved in `app/data/flight-dng02.json` |
| **MNb1 wing steering** | not rendered. Left `720575941521196211`, right `720575941549822781`, both exact `b1 MN` matches in v888 |
| **DNp07 + DNp10 landing** | not rendered, and `banc-landing-pathway.webp` is **referenced but missing** behind a silent `onError`. Four roots resolved in `app/data/flight-landing-dnp07-dnp10.json` |
| **DNg12 24-frame** | the 16-frame version ships; a longer one would read the brain to connective to T1 progression more clearly |

Full specs for the first three are in
`docs/handoffs/v2/RENDER_GUIDE_MISSING_FLIGHT_CELLS_V2.md`, including the
labelling constraints. The identification gate is already passed for all of them,
so those three are render work, not research work.

**Rendered but not wired into the app:** the three `banc-flight-dodge-dnp03-*`
statics (the two 12-frame sequences *are* used) and `banc-walking-steering-poster.webp`,
which is a standalone 81-cell poster in the older magenta/green scene colours and
is not part of the layer stack.

---

## 9. Wording rules that outlive any one render

1. **Never call a response circuit a detector.** "THREAT RESPONSE", not "threat
   detection". Those cells produce an escape; they are not the visual detection
   circuit.
2. **Anatomical side is not behavioural direction.**
3. **Separate measured from inferred.** If direction comes from synapse polarity
   rather than recording, say so.
4. **Populations are populations.** DNg12 is 28 cells, not "the grooming neuron".
   Carry the qualifier: *"does not imply that every rendered cell was
   independently function-tested."*
5. **No invented IDs, ever.** Names and citations in, resolution against the live
   database, never a guessed segment ID.

---

## 10. Where things live

| path | what |
|---|---|
| `D:\Meshes\banc\walking_steering_ids.json` | the cast and its colours |
| `D:\Meshes\banc\walking_steering_layers.json` | layer definitions |
| `D:\Meshes\banc\walking_steering_camera.json` | the solved camera, sha256 `fd935462…cb469b` |
| `D:\Meshes\banc\walking_steering_dec\` | decimated meshes |
| `D:\Meshes\BANC_PENDING_JOBS.md` | approved but unrun work |
| `banc-explorer/public/` | delivered assets |

**Note:** there are two working copies of the app, `banc-explorer` and
`banc-explorer-dng100`. Confirm which one you are delivering into before you
assume.

Related: `BANC_WALKING_STEERING_POSTER.md` (the camera derivation in full),
`RENDERING_NEURONS.md` (the general neuron-rendering playbook),
`RENDER_PROTOCOL.md` (the shared GPU queue: one GPU, add a job and stop).
