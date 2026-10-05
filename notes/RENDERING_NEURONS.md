# Rendering neurons: procedures that actually worked

Written from the CA3 connectome project (July 2026). Everything here was learned
by getting it wrong first. Numbers are from Blender 4.4 / EEVEE Next on a single
consumer GPU, meshes from CAVE via meshparty.

---

## 1. Shading: the one rule that matters most

**Neurons are submerged. Submerged tissue is not glossy.**

Wet things only *look* wet once they are out of water. A neuron sitting in
extracellular fluid has almost no refractive index step at its surface, so it
should read as soft and translucent, never as painted plastic with a highlight.

```python
bsdf.inputs["IOR"].default_value = 1.04       # tissue in water, NOT 1.38 (tissue in air)
bsdf.inputs["Roughness"].default_value = 0.62
# let subsurface carry the softness; SUBSURFACE_SCALE ~0.012 Blender units at TARGET_SIZE 10
```

Getting this wrong is the single most common reason a neuron render looks fake.
A diffuse-only shader is not the answer either: it goes flat and dead. Keep the
BSDF, kill the Fresnel.

### Emission is not a substitute for lighting
Pushing emission to ~0.55 across the board flattens everything and removes every
shadow. If a render looks flat, check there is an actual light rig and an HDRI
world, not more emission. Three-point area lights scaled to the subject plus a
world HDRI is the baseline.

### View transform
**Standard, not AgX.** AgX desaturates hard, and these palettes depend on
saturated blues and golds staying saturated. If colours look washed out, check
this before touching the palette.

---

## 2. Colour: pick it in the render, not the picker

A hex that looks right in a colour picker will not look right through a 5200 W
key light with a Standard view transform and no highlight roll-off.

**Procedure:** render the same frame at 3 to 4 candidate hexes, tile them side by
side, and look. Every time this was skipped the colour had to be redone.

Real example: "gentle imperial purple". The arithmetically gentle version
(`#A651C2`, sat 0.58 / val 0.76) rendered as hot electric orchid. `#9B7FC4` went
pale lilac. The one that *reads* gentle in this rig is `#5D2E8C`, sat 0.79 /
val 0.55, which looks almost black in a picker. **Gentle in the render, not in
the swatch.**

Also check new colours against every colour already in the scene, in hue AND in
saturation/value. Two hues 7° apart can still read as clearly different if one is
deep and one is pale.

### Encoding a measurement as colour

Different problem from picking a palette. Here the colour *is* data, so the ramp
has to be ordered and readable where meshes overlap.

**Never interpolate a ramp in HSV.** Walking hue from blue to gold takes the long
way round the wheel, through cyan and green, and produces a rainbow. The first
convergence-gradient frame came back a **green thicket**: green carried no
meaning, and the low end was indistinguishable from the middle. Cost: one render
plus the time to work out why a two-stop "cool to warm" ramp had a third colour in
it that neither stop contained.

**Use explicit stops, lerped in sRGB, chosen to rise monotonically in lightness.**
Deep blue `#1D358F` to violet `#8E46C0` to gold `#FFC24A` works: it never touches
green, and because lightness climbs with the value, the ordering survives in
dense regions where a hundred arbors overlap and no single cell is separable.

**Log-scale a heavy-tailed quantity.** Mossy fibre input count runs 0 to 235 with
a median of 41. On a linear ramp most of the range is spent on a handful of
outliers and the bulk of the population renders as one flat shade. `log10(n+1)`
fixes it. Bonus: use the same transform the analysis figure uses and the render
and the figure agree by construction rather than by luck.

**Then look at it.** Both of the above were caught by rendering a cheap frame at
1600x900 and 40 samples, which took 10 seconds because the scene was cached.
There is no excuse for guessing.

---

## 3. Downsampling / decimation

### Never use `preservetopology=True`
These meshes have thousands of connected components (one had 6,200). Topology
preservation then blocks almost all collapses: a run targeting 40% kept 95.4%.

```python
ms.meshing_decimation_quadric_edge_collapse(
    targetfacenum=target, qualitythr=0.3,
    preserveboundary=True, preservenormal=False,
    preservetopology=False,          # <-- the important one
    optimalplacement=True, autoclean=True)
```

### Target density per unit AREA, not a global face count
Face density varies enormously by cell class. Measured, in faces/µm²:

| population | density |
|---|---|
| cell bodies, dendrites | 4 to 8 |
| axon fibre sets | 146 to 174 |

A single global target destroys the fibres, cutting them to 4-5% of their faces
while *bloating* others 14 to 20x. Use `target = area_um2 * DENSITY` with a
per-folder override where needed.

### But watch the keep-floor
A `max(MIN_FACES, area*density, faces*0.40)` guard is sensible until the 0.40
floor silently wins on every cell. That happened here: a folder came out at 21.0M
faces, 375k per cell against 40k for comparable cells, and pushed a render from
under 6 s/frame to **128 s/frame**. Always print the before/after face totals for
the whole folder and sanity-check them against a known-good set.

### Clean before decimating
```python
ms.meshing_remove_connected_component_by_face_number(mincomponentsize=25)
ms.apply_coord_hc_laplacian_smoothing()
```
HC Laplacian preserves volume far better than plain Laplacian on spiny dendrite.

### Stray vertices wreck auto-framing
Meshes routinely carry 2 to 8 vertices thousands of µm from the rest. A raw
min/max bounding box then collapses your auto-scale. Use **percentile bounds**
(0.5 / 99.5) everywhere you compute extents, and strip stray faces explicitly.

### Storage reality check
Native ~225 MB/cell vs ~5.3 MB/cell decimated at a sane density target. 1,815
cells is therefore ~10 GB, not 400 GB. **Download time is the bottleneck**, around
2.4 min/cell and network-bound, so it parallelises well.

---

## 4. Scene caching: the single biggest speedup

Rebuilding a large scene from OBJ took **554 s**. Saving it as a `.blend` and
reopening took **6 s**. That is a 92x speedup and it changes how you work: you go
from two iterations an hour to two a minute.

Build the cache once, then have every render script open it and only rebuild
materials, lights, camera and keyframes. Never re-import OBJs in an iteration
loop.

---

## 5. Coordinates: the trap that will cost you a day

**Blender's OBJ importer maps file `(x,y,z)` to `(x,-z,y)` but does NOT bake it
into the vertices.** It leaves them in file coordinates and puts a 90° X rotation
on the *object*.

Consequences, and both directions bite:

- **Comparing external data against mesh vertices: do NOT convert.** Skeleton
  nodes, synapse coordinates and OBJ vertices are all already in the same raw
  space. Converting one side produces a wrong nearest-neighbour mapping that
  still runs and still looks plausible.
- **Placing an object in the scene: DO convert.** The object's rotation runs
  before its location, so `obj.location = -centre` with a raw-space centre shifts
  by an unrotated vector in rotated space.

```python
print(o.rotation_euler)     # (1.5708, 0, 0) => the flip is on the object
```

**Always assert.** One cheap check catches every version of this:

```python
assert max(abs(v) for v in point_in_scene) < TARGET_SIZE, "coordinate spaces disagree"
```

Related: `matrix_world` reads **stale** until `bpy.context.view_layer.update()`.
A soma once came out computed in millions of scene units because of this.

### Check units, do not assume them
CAVE synapse tables here store `ctr_pt_position` in **nanometres**, not voxels.
Scaling by the 4/4/40 resolution would have thrown every synapse a millimetre out
of the volume. Verify by asserting the points fall inside the mesh bounding box.

---

## 6. Camera paths

### Solve the framing, do not guess it
Render a few stills, measure the lit content bounding box, and compute the
distance. Guessing costs a whole animation.

```python
lit = luminance > 10
rows = np.where(lit.sum(1) > 0)[0]
fill = (rows[-1] - rows[0]) / H
clipped = rows[0] <= 1 or rows[-1] >= H - 2
new_distance = old_distance * fill / target_fill      # inverse relation holds well
```

**Find the fullest frame first.** In one orbit, frame 340 of 480 was the widest
projection, not 400 as assumed, and settings tuned on 400 clipped at 340. Sample
across the whole move.

Target roughly **85 to 90% height fill** with visible margin. 100% means clipped.

### Portrait to widescreen is not just a resolution change
Blender's default sensor fit is AUTO, which fits the *larger* dimension. Switching
1080x1920 to 1920x1080 changes which axis the camera fits, so a tall subject that
framed perfectly in portrait overflows vertically in landscape. Expect to pull
back roughly 1.5 to 1.8x, and to need a vertical shift as well, because subjects
are rarely centred on the origin.

`shift_y` is expressed as a fraction of the sensor's **larger** dimension.

### One move, not four
The most common note from a real viewer is "the camera goes in and out too much."
A path that pushes in, backs off, pulls wide and comes back reads as pumping.
Pick one intention per shot: hold where the action is, then open out once when the
subject grows. 16 to 20° of orbit across a whole shot is plenty; it gives parallax
without announcing itself.

### Smoothness
Use BEZIER with `AUTO_CLAMPED` handles for camera position and targets. Verify by
sampling positions per frame and looking at the velocity: a mid-shot local minimum
in speed is a visible stutter.

```python
vel = np.linalg.norm(np.diff(positions, axis=0), axis=1)
# any interior frame with vel < 12% of peak is a near-stop the eye will catch
```

Use **LINEAR** for anything representing constant physical velocity, like a
travelling action potential.

### Depth of field
Focus on a target empty that follows the subject of interest. f/2.2 to f/2.6 at
`TARGET_SIZE = 10` is a good starting point. It costs almost nothing and does more
for the "cinematic" feeling than any amount of extra emission.

---

### A shot that changes scale has to rescale its rig, not just its camera

Any shot that crosses more than about one decade of magnification, a scale ladder,
a deep zoom, a pull back from a population to a synapse, breaks in two specific
ways that look like completely different bugs.

**Clip planes must follow the framing distance.** Blender's default `clip_start`
is 0.1 units. Once the camera is 4 units from its target that plane sits inside
the subject and the close rungs render black or hollow. Set them every frame from
the distance you just computed:

```python
cam_data.clip_start = max(dist * 0.002, 0.0005)
cam_data.clip_end   = dist * 12.0
```

**Light energy scales with the SQUARE of the distance, not the distance.** A rig
positioned relative to the framing radius keeps its geometry but not its exposure:
move the key from 620 um out to 4 um out and it is roughly four orders of
magnitude too dim. Scale each lamp's energy by `(radius / radius_reference) ** 2`
or the last rung of the ladder arrives correctly framed and completely black. This
one reads as a render failure rather than a lighting one, which is why it costs an
afternoon.

**Interpolate the framing radius in LOG space.** Linearly, a 620 to 1.6 move spends
almost all of its frames already deep in the final decade and the first rungs blur
past in a handful of frames. `exp(lerp(log(a), log(b), u))` gives every decade the
same number of frames, which is what "constant rate of zoom" actually means.

### TARGET_SIZE is not free: do not squeeze a population into 10 units

This project normalises populations to `TARGET_SIZE = 10` Blender units, which is
fine for CA3 at about 1000 um across because the dendrites there are thick enough
to survive it. It is **not** universally safe, and when it fails it does not look
like a scale problem.

MICrONS cortical cells, 1091 um of tissue squeezed into 10 units, rendered as
**disconnected coloured specks**: the morphology was in the right places, the
depth colouring was correct, and the surfaces were simply not there. The scale
factor was 9.2e-6, so a half micrometre dendrite became **0.0046 units** and EEVEE
could not resolve it.

Three wrong diagnoses were paid for before the right one, and each looked
convincing:

1. **Decimation shattered it.** Plausible: 400k faces from 9.8M took 852 mesh
   components to 10,246. Re-decimating at 1.5M, a 2.4x reduction, changed the
   picture not at all.
2. **It is aliasing.** Plausible: 0.38 um per pixel with sub pixel neurites.
   Rendering at 7680x4320 and downsampling changed the picture not at all.
3. **The meshes are bad.** Wrong. A single cell rendered on its own, in
   micrometres, is a flawless pyramidal neuron: 4.84M triangles, zero degenerate
   faces, median edge 163 nm.

**The test that settles it in one step:** render ONE cell, alone, in a scene where
one unit is one micrometre. If it looks right, the geometry is innocent and the
fault is in the scene scale. Do that before re-decimating anything.

**So: pick the unit to suit the subject.** One Blender unit per micrometre works
from a whole block down to a synapse and keeps every number in the file checkable
against the paper. If you do use a normalised size, verify the smallest feature
you care about is still bigger than about 0.01 units, and remember that clip
planes and light energy both have to follow (see above).

A related trap in the same family: the default camera `clip_end` is **100 units**.
A subject 700 units across renders as an empty frame, and an empty frame reads as
a broken script rather than a clipped camera. That cost a diagnostic round here
too.

### Portrait is not landscape with a different number

Blender's default sensor fit is AUTO, which fits the 36 mm sensor across the
**larger** output dimension. So the field of view you are actually working with
changes meaning when you rotate the frame:

- At 1920x1080 the sensor fits the width. Horizontal half angle 19.8 degrees,
  vertical only 11.4. If your framing radius is a half HEIGHT, using the
  horizontal angle puts the camera twice as close as intended.
- At 1080x1920 the sensor fits the height, so the horizontal field narrows by
  1080/1920, about 56 percent. A camera distance solved in landscape crops the
  subject left and right.

Measured on the gradient arch: `camdist 1.52` frames it correctly at 1920x1080 and
clips both sides at 1080x1920. The portrait value is `2.70`, which is 1.78x, and
1/0.5625 is 1.78. The correction is exactly the aspect ratio, so it can be
computed rather than searched for.

Do not treat the leftover space as a defect. A tall frame around a wide subject
leaves real bands above and below, and a readout belongs in them. Shrinking a
landscape layout to 56 percent instead is how a vertical cut ends up unreadable
on the device it was made for.

## 7. Skeletons

### Get them from CAVE only if they are dense enough
`client.skeleton.get_skeleton(root_id, output_format='dict')` returns
`meta, edges, mesh_to_skel_map, root, vertices, compartment, radius, lvl2_ids`.

But they are `pcg_skel` built on the level-2 graph at `invalidation_d = 7500 nm`,
which gave **392 nodes for an entire pyramidal cell**. Mesh coverage within 3 µm:
**CAVE 59%, meshparty at `invalidation_d=2000` 95%**. For animation, skeletonize
locally.

**Three CAVE fields are traps:**
- `root` is an arbitrary degree-1 tip when the datastack has no soma table.
- `compartment` may carry no usable information (here: only values 1 and 3, no
  axon label).
- `mesh_to_skel_map` indexes **L2 chunkedgraph nodes, not mesh vertices**. Its
  length is `len(lvl2_ids)`, not the vertex count. It cannot drive per-vertex
  emission.

### Skeletonize a decimated copy
The centreline barely moves and it is dramatically faster. Note the tradeoff: it
drops the thinnest terminals, so recovered cable length runs short.

### Sanity-check cable length out loud
A complete CA3 pyramidal cell carries roughly 8,000 to 16,000 µm of dendrite.
This reconstruction gave **3,779 µm**. Two honest reasons: every arbor is cut off
at the tissue block boundary, and the pass ran on a decimated copy. An independent
estimate from membrane area (surface area / measured local radius) put the true
figure at 5,700 to 8,500 µm.

**Do not put a number like that in a caption without the caveat.**

### The soma is often not a hub
Check `degree(soma)` in the **edge graph**, not the parent array. Here the soma
came back **degree 1**: a tip, not a hub. Consequences:
- Every parent-walk "path to the soma" funnels down one chain.
- Cable paths route *around* the soma rather than through it. Nodes physically
  inside the soma carried field values spanning 184 µm across a structure 13.7 µm
  wide, and the animated wave visibly **looped around the soma**.

Fix: clamp every node within the soma radius to one value. A soma that size
depolarises as a unit anyway, so it is both the correct fix and the honest one.

### Identifying the axon is harder than it looks
Things that did **not** work here:
- **Paths from the cell's own outgoing synapses.** 88 of 128 turned out to be
  autapses with coordinates byte-identical to incoming synapses, and the 40
  genuine ones split across the arbors indistinguishably from the incoming set.
  Always check `post_pt_root_id != pre_pt_root_id` and dedupe against incoming.
- **Soma child subtrees**, because of the degree-1 soma above.

What did work: calibre and spine load measured off the native mesh (axon median
radius 0.48 µm vs dendrite 0.70; surface area per µm of cable 5.09 vs 8.48), plus
**asking the domain expert to circle it on a render**. That took two minutes and
beat an hour of heuristics. Do it early.

Be honest in the caption about what the mask actually is. Here the "axon" is
predominantly basal dendrite with the axon embedded, not separable at this
skeleton's resolution.

---

## 8. Animating a signal along real cable

The goal is a wavefront that follows real branching, not a gradient sweeping
across the screen.

1. Compute a **per-node distance field** along the skeleton graph (Dijkstra, or
   cumulative path length).
2. Map it to **mesh vertices** and store as a `FLOAT_COLOR` attribute.
3. In the shader, build a band around an animated value:
   `band = clamp(1 - |d - t| / width)² * peak` into Emission Strength.
4. Animate `t` LINEARLY for constant conduction velocity.

### Mapping the field to 2M+ vertices
Blender ships numpy but **not scipy**. A 3D broadcast
`(verts[:,None,:] - nodes[None,:,:])**2` allocates over a gigabyte per chunk. Use
the expansion instead, which BLAS threads:

```python
d2 = (nodes**2).sum(1)[None,:] - 2.0 * (block @ nodes.T)   # |a|^2 is constant per row
```
2.3M verts against 3.2k nodes takes about 90 s. **Cache it to disk**, keyed on
vertex count.

### Two normalisation traps
- **Never derive the span from `values.max()`** if you park dark nodes at a large
  sentinel. The sentinel normalises to exactly 1.0 and every dark node lights on
  the final frame. Store the true span alongside the field. This produced a
  53,000-pixel flash at the end of every cut before it was found.
- **Never clip normalised values to 1.** Dark nodes must stay past the end of the
  sweep, so clamp to something like 4.0.

### Nearest-node lookup breaks continuity
If lit and dark nodes are spatially interleaved (they will be: branches, spines),
a plain nearest-node lookup along a dendrite alternates between them and the wave
breaks into blobs. **Search only the lit nodes, and park anything further than a
threshold** (about 5.5 µm worked). That gives a continuous corridor.

### A pulse that resets must go dark first
If a wavefront rewinds from the far end back to the start while still lit, a
second pulse visibly runs **backwards** along the structure. Key the amplitude to
zero across the rewind.

### Do not invent arrival times
Detached fragments have no honest cable distance. Timing them by straight-line
distance bunches them into one 24,000-pixel flare. Leave them dark and say so.

---

## 9. Fading things in and out

### Do not scale from zero
If objects carry their centring on `location` (which they do when meshes stay in
file coordinates), scaling toward the object origin **drags them in from
somewhere else entirely**. It reads as objects flying in from a corner, and it is
the note you will get back.

Use keyed `hide_render` / `hide_viewport`, staggered across a second or so. Five
staggered appearances read as convergence; one simultaneous pop does not.

### Alpha fading is expensive
Opaque frames render roughly **50x faster** than alpha-blended ones. Reserve real
alpha fades for a handful of objects, never a whole population.

### Fading by darkening base colour does not work for interleaved cells
A "black" cell still occludes, still scatters subsurface, and still casts shadow.
It works for a wide population shot; for cells interleaved with your subject it
buries the subject in dark tissue.

### EEVEE Next gotcha
`Material.blend_method` still exists in Blender 4.4 but **does nothing** under
EEVEE Next. The live property is `surface_render_method`
(`'DITHERED'` / `'BLENDED'`).

---

## 10. Compositor

Blender 4.4 moved Glare controls to input **sockets**. Writing `glare.threshold`
silently sets a dead RNA property and reads back 0.0. Set the socket.

For a transparent still, set `film_transparent = True`, `color_mode = 'RGBA'`,
**and** remove any Alpha Over node compositing a black plate underneath, or the
alpha is thrown away at the last step.

---

## 11. Delivery

- **H.264, yuv420p, `-movflags +faststart`.** Non-negotiable for inline playback
  on iOS from static hosting.
- Even dimensions are required for yuv420p.
- Verify the host serves **HTTP 206** on a range request. Without it, iOS Safari
  will not play the file.
- **Look at the finished file**, not just the render log. Extract frames from the
  encoded video and read them as images.
- Serve vertical to phones and widescreen to desktop by swapping the `<source>`
  at load time. Keep vertical as the markup default so phones never begin
  downloading the wide file.

---

## 12. Process rules, the expensive ones

1. **Render and LOOK AT a test frame before launching any full animation.** Every
   long render started without this had to be redone.
2. **Measure, do not guess.** Framing, colour, face counts, arrival times: all of
   them were wrong at least once when estimated and right when measured.
3. **Verify before reporting.** A job can exit in 6 seconds with a
   ZeroDivisionError and still look like it launched fine. Check the output
   exists and has the frame count you expect.
4. **Assert coordinate assumptions in code.** They are silent when wrong, and
   wrong output still renders and still looks plausible.
5. **Ask the domain expert to mark up a render** when a classification is hard.
   Two minutes of their time beat an hour of heuristics, twice.
6. **State the limits in the caption.** Cut-off arbors, incomplete cable,
   inseparable compartments. The work is more credible with them, not less.

---

## 13. Decimation: budget in faces per micrometre squared, and clean first

Added 31 July 2026 after Amy reported decimation breaking branches. Every number
below is from rendering a ladder on retina cell 720575940550200928 (18,879 um2 of
surface, 5.7M faces at full resolution) from an identical camera.

| faces | per um2 | dendrites |
|---|---|---|
| 5,732,679 | 304 | original, continuous |
| 1,400,000 | **74** | indistinguishable from the original |
| 700,000 | 37 | mostly continuous, thin processes begin to bead |
| 350,000 | 18.5 | **broken into dotted strings** |
| 148,676 | 7.9 | the staged meshparty library. Far past broken |

**Never budget in MB or in a fixed face count.** Cells differ in size by more than
ten times, so only a density transfers. 75 faces/um2 for a close up, 37 as the hard
floor for anything looked at directly, and match the density to how large the cell
will actually be ON SCREEN: in a 364 cell mosaic each cell is a few pixels wide and
18 is fine, while the same mesh in a hero shot is unusable.

### Clean before decimating

**30.5% of a full resolution mesh is geometry no ray can reach.** Strip it first
and the entire budget buys visible surface:

```python
ms.compute_scalar_ambient_occlusion()
ms.compute_selection_by_scalar_per_vertex(minq=-1e9, maxq=1e-9)
ms.meshing_remove_selected_vertices()
```

**Ambient occlusion on this build spans 0 to about 16, not 0 to 1.** Sweeping
thresholds from 0 to 0.002 is sweeping zero four times, which is how an entire
afternoon went into a measurement that could only ever return one answer.

This is also the fix for the polygons hidden inside somas and for the "dust". They
are the same thing, marching cubes inner shells: 99.6% of small component vertices
receive no ray from any direction, against 25.6% of main component vertices.

**Cleaning does not prevent branch breaking.** Verified by render: at 350k faces
the cleaned and uncleaned meshes bead identically. It buys about 44% more visible
surface per byte. Only the density rule prevents breaking.

### Two things that do not work

**Removing small connected components.** There is no litter to remove. On full
resolution meshes every one of 4,627 small pieces sits within 4 um of the main
body, median 127 nm, which at this voxel size is touching. On the already
downsampled library the same filter deletes 58% of the cell and 14% of its
bounding box. Disabled in `mesh_clean.py`; needs a per dataset rule first.

**`preservetopology=True`.** These meshes carry thousands of components, so the
topology preserving path refuses most collapses, never reaches the target, and
hands back a mesh still near full size. Always `preservetopology=False`.

### Do not re-decimate the staged library

Same cell, full resolution: 4,876 components, largest is **94.9%** of the mesh, one
intact object. The meshparty downsample: 10,122 components, largest is **6.5%**.
Whatever produced it destroyed the connectivity, and quadric edge collapse cannot
preserve a branch when there is no continuous surface left to collapse along.
Rebuild from `meshes_full\`, never from `meshes\`.

Scripts: `mesh_pipeline_test.py`, `mesh_budget_ladder.py`, `mesh_compare_render.py`,
`mesh_dust_probe.py`, `mesh_dust_ao.py`.

---

## 14. Motion blur: OFF, always, unless Amy asks for it

**Amy's standing instruction, 2 August 2026: never render motion blur unless she
directs it.** Not a judgement call. If a shot seems to want it, ask.

It is enforced in `apply_render_settings` in `ca3_animation.py`, which every render
script in this project loads, so CA3, BANC, MICrONS and retina are covered by the
one setting:

```python
scene.render.use_motion_blur = False
if hasattr(scene.eevee, "use_motion_blur"):
    scene.eevee.use_motion_blur = False
for vl in scene.view_layers:          # the vector pass allocates it too
    if hasattr(vl, "use_pass_vector"):
        vl.use_pass_vector = False
```

**Why it matters beyond taste.** EEVEE's `VelocityModule` keeps a full copy of the
scene geometry for the previous and next frame to compute motion vectors. Three
copies of the mesh, marshalled every frame.

Past roughly 40M faces it crashes. On 1 August 2026 the 364 cell retina job
(43.1M faces) died at frame 152 of 576 and the BANC job died during its import,
both with:

```
EXCEPTION_ACCESS_VIOLATION
blender::eevee::VelocityModule::geometry_steps_fill   <- inside memcpy
blender::eevee::Instance::render_sync
```

Not VRAM. The card reported 1.7 GB in use and the driver was healthy.

With it off, the same retina job ran to frame 319 without an access violation.

**What it did NOT fix, so nobody re-diagnoses this from the wrong end.** The 364
cell scene is still far slower than it should be, and motion blur was not the
cause of that:

| library | cells | faces | s/frame |
|---|---|---|---|
| old staged | 202 | 17.3M | **2.2** |
| cleaned | 364 | 43.7M | **51.3** |

2.5x the geometry, 23x the time, and worse than this project's own CA3 benchmark
of 53M faces at 6.6 s/frame. That nonlinearity is still unexplained. Do not
attribute it to motion blur.

---

## 15. Always light the scene

**Amy's standing instruction, 3 August 2026: ALWAYS NEED AN ENVIRONMENT.**

An "all cells" anatomy frame for the retina film was rendered with pure emission
materials and no lighting contribution. Emission is flat, so nothing in the frame
had form and a soma read as a slightly denser lump of the same brightness as the
dendrites. The first conclusion drawn from it was that the render was showing the
wrong side of the dataset. It was not. The camera was correct and the lighting was
absent, and settling that took a unit-corrected measurement of soma depth against
mesh geometry, when a lit frame would have answered it at a glance.

- **Structure and anatomy are SHADED**: Principled BSDF, IOR 1.04, subsurface on,
  plus `build_world` and `build_lights` from `ca3_animation.py`.
- **Emission is for SIGNAL**, where brightness carries a measurement. The retina
  direction sweeps animate emission because brightness IS the calcium response.
  Even there, the world and the lights stay in the scene.
- **Never ship a frame whose only light source is the material's own emission.**

The tell: if you cannot find a soma in a frame full of cells, the scene is not lit,
whatever the camera is doing.
