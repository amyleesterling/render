# CA3 rendering handoff, rendering sections

> Excerpted on 4 October 2026 from `D:\Meshes\HANDOFF.md` (written 29 July 2026).
> The text below is unchanged. Three stretches were left out because they are
> connectivity analysis rather than rendering, and the original lives in a
> private repo: the findings reproduced from the subset, the whole-volume
> convergence and gradient analysis, and the bouton size comparison. A line of
> three dots marks each cut. Paths are as they were on that date; where this
> disagrees with RENDERING.md, RENDERING.md is newer.

# CA3 rendering project — handoff

Everything a future session needs to pick this up cold. Written 2026-07-29.

## What this is

3D renderings of mouse hippocampal CA3 for Amy Sterling, who is an author on the
paper being illustrated:

> **Connectomic reconstruction from hippocampal CA3 reveals spatially graded mossy
> fiber inputs and selective feedforward inhibition to pyramidal cells**
> Zheng, Park, Hammerschmith, Lu, Yu, Sorek, Silverman, Jordan, Sterling,
> Silversmith, Collman, Seung, Tank. bioRxiv, 15 July 2025.
> doi:10.1101/2025.07.09.663979 · PubMed 40791329

**Published site:** https://amyleesterling.github.io/ca3/
**Repo:** `C:\Users\amyle\ca3` (public, `amyleesterling/ca3`, GitHub Pages on `main`)

## Where things live

| path | what |
|---|---|
| `D:\Meshes\` | all working files, scripts, renders. **Not** on C: — C: only had 31 GB free |
| `D:\Meshes\ca3_scene.blend` | **6.91 GB scene cache**, 984 objects, 124M faces. Opens in 6s |
| `D:\Meshes\hq\` | re-decimated meshparty populations (see below) |
| `D:\Meshes\hero\` | hero cell + its 6 mossy fibres, native resolution |
| `D:\Meshes\_cache_zheng_ca3\` | meshparty `.h5` download cache |
| `D:\Meshes\renders\` | every render, plus logs and intermediate CSV/npy |
| `D:\Meshes\.venv\` | python 3.10 venv: caveclient, meshparty, pymeshlab, numpy, pandas, h5py, pillow |
| `C:\Users\amyle\meshparty\` | Amy's original mesh library, **read-only, never write here** |

## The scripts

| script | purpose |
|---|---|
| `ca3_animation.py` | the core module. Config, GROUPS palette, materials, lights, camera, world, compositor. Every other script imports it via `exec` and pokes its globals |
| `build_cache.py` | imports all populations once and saves `ca3_scene.blend` |
| `render_from_cache.py` | opens the cache and rebuilds materials/lights/camera/keyframes. **Use this for anything involving the full population** |
| `hero_shot.py` | the single-cell dolly shot, builds its own scene from `D:\Meshes\hero\` |
| `synapse_story.py` | the paced 5-beat synapse sequence |
| `meshparty_decimate_hq.py` | the good decimation pass |
| `redownload_population.py` | pulls a population from CAVE at full resolution |
| `download_hero.py` | pulls the hero cell + its fibres |
| `patch_cloud.py` | rebuilds only the synapse cloud inside the cache |
| `render_all.ps1`, `framing_sweep.ps1`, `render_ab.ps1` | batch runners |

## THE RULE

**Always render one still and LOOK AT IT before launching an animation.**
Use `still=<frame>` on `render_from_cache.py`, `hero_shot.py` or
`synapse_story.py`. Amy asked for this explicitly after a 300-frame render came
out wrong. A frame costs seconds; an animation costs 5 to 160 minutes.

**Numeric checks are not enough.** `matrix_world` and `bound_box` read STALE in a
script unless you call `bpy.context.view_layer.update()`. Twice a printed
diagnostic looked correct while the image was completely wrong.

## Bugs already found and fixed (do not reintroduce)

1. **OBJ axis conversion.** Blender's OBJ importer maps file `(x, y, z)` to
   `(x, -z, y)`, and it stores that conversion in the **object's rotation**, not
   baked into vertices. So `o.data.vertices` gives raw file coordinates while
   `matrix_world` gives converted ones. Mixing them put the synapse cloud in a
   different part of the scene and the hero camera 50 units off target. Any point
   data from CAVE must go through the same conversion, or through an object's
   `matrix_world`.
2. **Depsgraph staleness.** After reparenting, call `view_layer.update()` before
   reading any world matrix.
3. **`preservetopology=True` blocks decimation** on fragmented meshes. A cell with
   6,200 connected components kept 95% of its faces instead of 40%. Must be False
   for the meshparty meshes; the CAVE meshes are clean and work either way.
4. **Density targets are per-morphology.** Cell bodies run 4-8 faces/µm²; thin
   axons run 146-174. A single global target cut the fibre sets to 4% of their
   faces. There is now a `MIN_KEEP_FRACTION` floor.
5. **Stray vertices.** Most meshparty meshes carry 2-8 junk vertices sitting
   hundreds of thousands of nm outside the volume, referenced by real faces, so
   each drags a huge triangle across the scene. `world_bounds()` uses percentiles,
   and `strip_stray_faces()` deletes faces with edges over `MAX_EDGE_NM`.
6. **Glob catches scratch files.** `collect_sources()` skips `*.raw.obj` and
   `*.tmp.obj`; a render started mid-download died on a vanished file.
7. **Blender 4.4 Glare node** moved its controls from RNA properties onto input
   sockets. Setting `glare.threshold` writes to a dead property.
8. **AgX view transform** desaturates. Use `Standard`.

## Look decisions, and why

- **No gloss.** Neurons are submerged in extracellular fluid, so Fresnel
  reflectance is ~0.034%, not the 2.6% of tissue in air. `IOR = 1.04` (1.38/1.33),
  no Coat layer, subsurface carries the look. Amy's rule.
- **Pure black background**, `film_transparent` + black plate in the compositor,
  so the world lights the scene without appearing.
- **HDRI:** `C:\Users\amyle\Documents\cyclorama_hard_light_4k.hdr`.
- **Palette** (all in `GROUPS` in `ca3_animation.py`):

| population | colour | note |
|---|---|---|
| thorny pyramidal (182) | `#1858C7 → #2586F5` | saturation pinned high; pale blues read as grey |
| sparsely thorny (68) | `#8B5CE0 → #B78CF7` | purple |
| inhibitory (28) | `#17A06B` | emerald, pushed green to separate from blue |
| mossy fibres (688) | `#E2AF5E` | gold, Amy's convention |
| presynaptic deep (7) | `#C43F92 → #E86FB8` | pink, hue ~325, never let it drift toward red |
| presynaptic superficial (9) | `#F075BF → #F189C6` | light end clipped so it stops reading like the gold |

- Amy dislikes: pale desaturated colour, glossy surfaces, boxes around labels,
  labels with large type, anything that moves too fast to absorb.
- She wants: things to fade in rather than scale up from a point, long holds,
  time to "see, process, discover and contemplate".

## Data

- CAVE datastack `zheng_ca3`, materialization version 671.
- **`synapses_ca3_v1`** is the real synapse table. Columns include `size`,
  `pre_pt_root_id`, `post_pt_root_id`, and three positions. Positions are stored
  as `"[948762 876690  72000]"`, bracketed and **space** separated, in the same
  nanometre space as the meshes (verified).
- CAVE **skeleton service exists but 504s** on these cells. Local
  `meshparty.skeletonize.skeletonize_mesh` works, ~60s for a 1.1M face cell, but
  the root lands at vertex 0 rather than the soma and `distance_to_root` returns
  `inf` for disconnected pieces. Both fixable, neither done.


. . .

## Hero cell

`648518346438632877` — 165 mossy fibre synapses from **6** distinct fibres. The
camera aims at the **centroid of those 165 synapse coordinates**, because that is
where the thorny excrescences are; aiming at the soma pushes them out of frame.

## Rendering cost

- Cache opens in **6s**; building from OBJ takes **9 minutes**. Always use the cache.
- Opaque materials: ~1-3s per frame at 1080x1920, 64 samples.
- **Alpha-blended materials: ~10.6s per frame.** The fade-in story took 159 min.
  If speed matters, animate emission rather than alpha.
- Raytracing on was *faster* than off in one controlled test (12s vs 53s) because
  EEVEE switches shadow methods. Currently off. Unexplained, noted in the config.

## State (updated 2026-07-29 morning)

### Live on the site
Full-width banner, build sequence video, plain-language findings, "182 thorny
pyramidal cells" badge, single-cell closeup video, synapse story video (2x speed,
3 beat captions), classification table, colour key.

### Videos, and what each is
| file in `ca3/video/` | what |
|---|---|
| `build_sequence.mp4` | 20s, populations arrive in circuit order, dot labels burned in |
| `synapse_story.mp4` | 18.8s, 2x speed, 3 captions. Cells fade up, synapses bloom, partners arrive |
| `hero_shot.mp4` | 25s, ONE cell (`648518346438632877`) + its 6 fibres only. Superseded by hero_full |
| `synapse_cloud.mp4` | older, superseded by synapse_story |

**"Hero" just means the featured single cell**, `648518346438632877`, chosen
because it receives the most mossy fibre input (165 synapses from 6 fibres). It
was downloaded at NATIVE resolution (4.47M faces) so the thorns resolve.
Rename these to plainer names when convenient; Amy found "hero" confusing.

### hero_full.py — the corrected zoom-out, NOT yet rendered
Opens the cache, drops the native hero in, hides its decimated twin, and pulls
back through: thorns → its own 6 fibres → all 688 mossy fibres → every cell.
Now retimed to **480 frames / 20s** per Amy: brief hold, fibres from 3s, faster
pull-back. Fibres arrive **nearest-first** using `renders/fibre_order.txt`;
alphabetical order had put the most distant fibre (46.7um, off screen) first.

**Cost: ~28-39s per frame at 64 samples, so 480 frames is roughly 4 hours.**
That is dominated by alpha-blend materials on 965 cells. If that is too slow,
fade with emission instead of alpha, which is far cheaper (opaque frames run
0.5-3s).


. . .

### Open items
- **57 partner cells not downloaded.** The hero's 6 fibres make 291 synapses onto
  57 other cells and we have meshes for NONE. ~2 hours to fetch. Would let the
  boutons connect to real partners instead of vanishing.
- Trim the ~0.9s black lead-in from `synapse_story.mp4`.
- Rebuild the scrubable artifact viewer, it still holds the OLD synapse cloud
  frames with 3.2s of black at the start.
- Proximodistal gradient map; action potential along skeletons; AE titling.

### Scaling to all 1,815 pyramidal cells
- **Cell typing is NOT in the public materialization.** `ca3_cell_type` and
  `ca3_cell_id` have 1 row each. `c3_nuclei_v1` has 13,725 distinct cells with
  nucleus volume, which is the only enumeration available. Amy would need to
  supply the typed segment id list.
- `lod=` on `MeshMeta.mesh()` **does nothing here** — measured identical face
  counts at lod 0/1/2/3. Not multi-resolution.
- Storage is NOT the problem if you decimate at download time:
  native 225 MB/cell vs **5.3 MB/cell** at the hq density target. 1,815 cells is
  therefore ~10 GB, not 400 GB. Face count ~100M, which renders fine.
- **Download time is the bottleneck: ~2.4 min/cell, so ~73 hours serial.**
  Network-bound, so it parallelises well across workers.


. . .

### Recurring instruction
**ALWAYS crop images before putting them on the site.** Full renders are mostly
black; Amy has flagged uncropped images three times. Measure the lit bounding
box, crop with a small margin, then scale.

## Mobile

Amy reviews on an iPhone. **The Claude app will not play video attachments.**
Send stills, or publish to the GitHub page and send the link. Videos on the page
work because Pages serves `video/mp4` with HTTP 206 range support; every `<video>`
needs `controls playsinline muted loop` plus a poster.

## Action potential (added 29 July)

`ap_fields.py` then `ap_test.py`. The pulse is not a sweep across the screen:
every mesh vertex carries its own path distance measured along the skeleton, so
the wavefront follows the real branching of the arbor and splits when the
dendrite splits.

### Skeletons
`D:\Meshes\skeletons\<segid>.npz` with `vertices`, `edges`, `root`, `parent`,
`dist_from_root_um`. **In raw OBJ file space, nanometres, no transform applied.**
Hero 3,203 nodes / 3,779 um cable; the 6 fibres 1,505 to 2,536 nodes.

CAVE *does* serve precomputed skeletons for `zheng_ca3`
(`client.skeleton.get_skeleton(id, output_format='dict')`) but they are `pcg_skel`
at `invalidation_d=7500`, so the hero gets **392 nodes for a whole pyramidal
cell**. Mesh coverage within 3 um: CAVE 59%, meshparty 95%. Use meshparty.
Three CAVE fields are traps: `root` is an arbitrary tip (no soma table in this
datastack), `compartment` holds only 1 and 3 so it cannot label axon vs dendrite,
and `mesh_to_skel_map` indexes L2 chunkedgraph nodes, **not** mesh vertices.

Cable length is honest-but-short: 3,779 um against a textbook 8,000 to 16,000.
Two real reasons, both worth stating rather than hiding: every arbor is cut off
at the tissue block boundary (z 4324 to 96439 nm for the hero *and* all six
fibres, to the nanometre), and the hero pass ran on a decimated copy. Do not put
this number in a caption as the cell's dendritic length.

### The two distance fields
`ap_fields.npz`, built by `ap_fields.py`:
- **fibre** — distance from the end farthest from its synapses, so a pulse
  launched at the root travels toward the boutons.
- **cell** — geodesic distance *outward from the 53 synapses*, multi-source
  Dijkstra, so depolarisation leaves the thorn rather than the soma.
Soma sits 130.5 um of cable from the contacts (76 um straight line, tortuosity
1.72), which is what sets the moment the soma lights.

### Numbers worth keeping
Fibre `648518346448994107` makes **53 synapses onto the hero, all inside a
4.7 x 5.2 x 6.4 um box**. That is one mossy fibre bouton wrapped around one
thorny excrescence, and it is the single best illustration of the paper's point.
Hero-side synapses sit 1.19 um off the centreline while fibre-side sit 0.24 to
0.88 um: the gap *is* the thorny excrescence.

### Gotchas hit while building it
- **The OBJ importer's axis flip lives in the object's rotation, not the
  vertices.** Compare raw against raw when mapping skeleton to mesh; convert only
  when placing something in the scene. Got this wrong once and the paint was
  silently wrong while still rendering fine. `ap_test.py` now asserts the synapse
  centroid lands inside the scene bounds.
- Nearest-node lookup is 2.3M verts against 3.2k nodes. Blender ships numpy but
  no scipy, and the 3D broadcast allocates over a gigabyte per chunk. Use
  `|a-b|^2 = |a|^2 - 2a.b + |b|^2` so it is a matmul, ~90 s, then cache it to
  `_paint_<segid>_<nverts>.npy` keyed on vertex count.
- `hexcol()` returns 3 floats; Blender colour sockets want 4. Append `(1.0,)`.
- `build_world(scene)` and `build_lights(scene, size, target=)` both take args.

### Options
`aim=follow|synapse|cell`, `camdist=`, `arc=` (degrees of parallax drift),
`push=`, `dof=0|1`, `fstop=`, `flash=`, `frames=`, `res=`, `samples=`, `still=N`.
Beats are fractions of `FRAMES`, so any running time recuts cleanly.

## Six fibres, and the physiology (29 July)

`ap_fields6.py` then `ap_six.py`. 18 s, 432 frames, ~0.6 s/frame.

**Why two attempts.** A lone mossy fibre spike discharges its target only about
**12%** of the time (Vyleta 2016; Henze 2002 found 54 of 58 pairs failed in vivo).
By the **third spike of a 50 Hz burst it is ~82%**, and after recent potentiation a
single spike reaches ~71% for tens of seconds. So showing one spike fire the cell
is the less likely outcome by roughly 8 to 1. The cut runs the honest version:
one fibre lands, the thorn depolarises, it fades, nothing happens; the other five
arrive; all six fire and the cell answers.

**The paper says nothing about this.** Pure connectomics. "detonator" appears once
in the whole manuscript, in a reference title; "action potential" and "firing
threshold" appear zero times in the body.

**Our 53 contacts from one fibre** sits just above the published per-bouton range
(7 to 45 active zones, Rollenhagen 2007). Not anomalous: one *fibre* is not one
*bouton*, and the paper itself notes each MF has 1 to 3 boutons plus satellites.
Safe caption wording is "dozens of release sites".

### Gotchas
- **Never fade a fibre in by scaling from zero.** These objects sit at raw file
  coordinates with the centring carried on `location`, so scaling toward the
  object origin drags them in from somewhere else. Key `hide_render` instead,
  staggered. Amy rejected the flying-in look once already.
- **Never derive the sweep span from `values.max()`.** Dark nodes are parked at
  10x the span, so max() normalises them to exactly 1.0 and every dark node lights
  on the final frame. That was the stray end flash. Store the true span in the npz.
- Detached arbor pieces have no honest arrival time. Leave them dark rather than
  timing them by straight-line distance, which bunches them into one flare.

### The axon, honestly
Amy marked the descending arbor by hand as the axon and that is what the
animation follows. Two caveats recorded rather than hidden: the cell's 128 CAVE
"outgoing" synapses are **88 autapses** with coordinates identical to incoming
ones, and the 40 genuine ones split across the arbors indistinguishably from the
incoming set, so they carry **no axon signal**. And the descending arbor carries
1,616 postsynaptic inputs at ~1/um, so it is mostly **basal dendrite with the axon
embedded**, not separable at this skeleton's resolution. `/ap.html` says so.

### Tonight's widescreen queue
`render_tonight.ps1`, verified framing, not yet launched (~8 h total):
- build sequence: `camdist=4.1 shifty=-0.066` (3.4 and 3.7 both clipped the green
  inhibitory cells; frame **340** is the fullest, not 400)
- synapse story: `camdist=4.0 shifty=0.0` (2.9 and 3.5 both clipped the top)
