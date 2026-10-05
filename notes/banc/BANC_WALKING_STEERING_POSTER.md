# BANC walking + steering poster

A single still for the right-hand panel of
[banc-explorer](https://amyleesterling.github.io/banc-explorer/), replacing the
live Neuroglancer iframe with a static image that can be clicked to mount the
interactive viewer.

Built 31 July 2026.

---

## The spec, as it ended up

```
1600 x 1200 WebP
transparent background
straight alpha, no black matte
sRGB
81 neurons: 52 descending #ff1493, 29 ascending #089c39
lossless or near-lossless alpha
<= 1 MB
```

The first version of this spec asked for an opaque black background captured with
Neuroglancer's screenshot function. That is no longer possible under the
transparency requirement, for a measured reason (below).

## Why this is a Blender render and not a Neuroglancer screenshot

Neuroglancer's 3D panel **clears to opaque black**. Measured, not assumed:
`gl.readPixels` at three background points of the live viewer returned
`[0, 0, 0, 255]`, and the composited 1600x1200 frame contained zero pixels with
alpha below 255.

Keying that black out is exactly the black matte the spec forbids, and it would
eat both the antialiased edges and the genuinely dark shaded interiors of the
neurons. The usual escape, rendering over black and again over white and solving
for alpha, is unavailable too: the spelunker build strips
`projectionBackgroundColor` out of the URL state, so the background colour cannot
be changed.

Blender produces straight alpha natively with `film_transparent`, and brings the
shading the rest of the site's renders use.

## The 81 neurons

73 come from `banc-explorer/app/data/walking-steering-neuroglancer.json`. Eight
named cells were added:

| id | cell | class |
|---|---|---|
| 720575941626500746 | DNg100 left | descending |
| 720575941500851362 | DNg100 right | descending |
| 720575941535862506 | DNa01 left | descending |
| 720575941432123640 | DNa01 right | descending |
| 720575941594293032 | AN09B029_b left | ascending |
| 720575941484372221 | AN09B029_b right | ascending |
| 720575941474101344 | AN02A002 | ascending |
| 720575941483106243 | AN02A002 | ascending |

DNa02 left/right were already among the 73. All 81 meshes were confirmed to exist
in the public bucket before anything was built, with a bogus control id that
correctly 404'd so the check could not pass vacuously.

Meshes come from the **public precomputed** source, not the graphene source that
`banc_download.py` uses:

```
precomputed://gs://lee-lab_brain-and-nerve-cord-fly-connectome/neuron_meshes
```

That is the source the banc-explorer scene itself renders, which is what makes the
camera check below meaningful rather than approximate. No auth required.

## Coordinates

Verified rather than assumed:

| space | definition |
|---|---|
| OBJ vertices | nanometres, isotropic |
| Neuroglancer world | voxels, `(x/4, y/4, z/45)` |
| canonical | 4 nm units, `nm/4` = voxel * `diag(1, 1, 11.25)` |
| Blender world | **micrometres**, `nm/1000` |

The meshes are in nanometres, confirmed by bounding box: a cell spanned
x 380,926 to 619,735 nm, and the scene's navigation position converts to
(500,390, 490,358, 127,238) nm, which falls inside it.

## The camera

Not guessed from `projectionScale`. Read straight off the live perspective panel
sized to exactly 1600x1200, then reconstructed and **proved** by
`banc_walkingsteering_camera.py`:

```
[PASS] invView columns share a scale        norms = [364823.3, 364823.3, 364823.3]
[PASS] camera basis orthonormal             max off-diag 4.25e-09
[PASS] recovered target == state position   [125097.509, 122589.503, 2827.499]
[PASS] projectionScale == visible height    implied 302229.483 vs state 302229.5051
[PASS] vertical fov is 45 deg               44.999998
[PASS] matches Neuroglancer to <0.01 px     max error 0.000085 px over 400 points
[PASS] CONTROL: camera nudged 20um fails    max error 8.553 px
```

The control matters: without it, a projection check that compares a formula
against itself would pass no matter what.

Result, in micrometres:

```
location   (649.157, 326.517, -1315.177)
looking at (500.390, 490.358,   127.237)
distance    1459.293 um
visible height at the target plane 1208.918 um   -> 1.007 um per pixel
sensor_fit VERTICAL, angle_y 45 deg
```

**`sensor_fit` must be VERTICAL.** Blender's default AUTO fits the larger axis,
which on a 4:3 landscape frame is the width, and the framing would silently be
solved on the wrong axis.

## Decimation

Native is ~3.1M faces per cell, so 81 cells is roughly 250M faces. This machine is
proven to 124M and gets steep past ~80M. At 1.007 um per pixel there is no point
carrying sub-micrometre detail, so the target is 10 faces/um2 by surface area,
per the playbook rather than one global face count.

## Files

| file | what |
|---|---|
| `banc_walkingsteering_download.py` | fetch the 81 from the public bucket, resumable, `probe` prints units |
| `banc_walkingsteering_decimate.py` | area-based decimation, `plan` prints targets without doing it |
| `banc_walkingsteering_camera.py` | derive the Blender camera from the NG matrices and prove it |
| `banc_walkingsteering_poster.py` | the Blender render, `dryrun` builds the scene without rendering |
| `banc_walkingsteering_webp.py` | WebP encode plus the straight-alpha audit |
| `banc_walkingsteering_go.ps1` | runs all of it in order |
| `banc/walking_steering_ids.json` | the 81 ids and their colours |
| `banc/walking_steering_camera.json` | the solved camera |

Output goes to `banc-explorer/public/banc-walking-steering-poster.webp`.

## Running it

```powershell
D:\Meshes\banc_walkingsteering_go.ps1 -DryRun    # scene + asserts, no render
D:\Meshes\banc_walkingsteering_go.ps1 -Test      # 400x300, LOOK at it first
D:\Meshes\banc_walkingsteering_go.ps1            # full 1600x1200 + webp
```

Decimation runs at BelowNormal priority because there is one GPU on this machine
and usually another session's animation on it.

## Exposure

The first rig guess was wrong by more than an order of magnitude: it blew
**99.7%** of lit pixels to 255, so the neurons rendered as white string with no
colour. This is exactly what the test-frame rule exists to catch.

Fixed by sweeping a light multiplier and measuring clipping and saturation on
solid pixels, then looking at the four candidates tiled side by side:

| light | mean luminance | clipped | mean saturation |
|---|---|---|---|
| 0.010 | 96 | 0.0% | 0.695 |
| 0.022 | 122 | 0.1% | 0.676 |
| **0.038** | **149** | **0.8%** | **0.666** |
| 0.050 | 165 | 1.8% | 0.655 |

`light=0.038` is the default: bright enough to read on a dark panel with the dense
brain arbor still holding detail. Emission dropped from 0.10 to 0.03, since
emission is a lift and not a substitute for the rig.

## Result, rendered 31 July 2026

```
banc-explorer/public/banc-walking-steering-poster.webp
1600x1200  RGBA  lossless WebP  324.3 KB  (budget 1000 KB)
81 neurons imported: 52 magenta, 29 green.  9.1M faces.  5.6 s on the 3090.
```

Audited rather than asserted:

| check | result |
|---|---|
| straight alpha (edge/solid brightness) | **0.958** |
| CONTROL, same image premultiplied | 0.223 |
| alpha round-trip through the encoder | max delta **0/255**, mean 0.000 |
| distinct alpha values | 256, full range 0 to 255 |
| transparent / partial / opaque px | 94.61% / 88,765 / 0.76% |

Decimation came out at 120.2M -> 9.6M faces, keep fraction median 8.0% and max
18.4%, so no keep-floor was quietly winning.

Content bbox is x 587-981, y 168-1029: **71.8% height fill, 24.7% width fill**.
Under a square `object-fit: cover` crop the content keeps x 387-781 of 1200 with
nothing clipped, so a near-square panel can cover-fit this safely.

## The four stacked layers (what the panel actually uses)

Four separate transparent WebPs on the identical camera, never flattened together.
Config in `banc/walking_steering_layers.json`, rendered with `layer=<name>`.

| file | cells | colour | size |
|---|---|---|---|
| `banc-context-base.webp` | all 81 | `#52675E` gray | 255.0 KB |
| `banc-forward.webp` | 6: DNg100 pair, AN09B029_b pair, AN02A002 pair | scene | 205.9 KB |
| `banc-turn-left.webp` | left DNa01 + DNa02 | `#ff1493` | 57.1 KB |
| `banc-turn-right.webp` | right DNa01 + DNa02 | `#ff1493` | 58.8 KB |

All four: 1600x1200, alpha 0 to 255, lossless, alpha delta 0/255 through the
encoder, full canvas preserved. 576.8 KB for the set.

### DNa02 sides were not given anywhere, they were derived

Not in the repo and not in the spec. Resolved from CAVE `cell_info` (datastack
`brain_and_nerve_cord`, mat 896), which yielded two DNa02 root ids but positioned
them at the **neck connective plane** (y=92500), not at the somata, so side could
not be read off directly. Sided instead by mesh geometry, calibrated on the DNa01
pair whose sides were given:

```
DNa01 left  (given)  brain-end centroid x = 563857 nm
DNa01 right (given)  brain-end centroid x = 411099 nm   -> midline 487478 nm
DNa02 720575941510475536  x = 576095  -> LEFT   (12238 nm from DNa01 left)
DNa02 720575941456897005  x = 406937  -> RIGHT  ( 4162 nm from DNa01 right)
```

Each DNa02 landed beside its same-side DNa01, which is the check that this is
right rather than a coin flip.

### Eating and threat-response layers: the id provenance check

11 exemplar ids were supplied for two further layers. All 11 meshes exist in the
public bucket (control id 404'd correctly). Cross-checking the *identities*
against CAVE `cell_info` at mat 896, and then against the chunkedgraph, gave three
different outcomes:

**Confirmed by direct tag match (4):** DNg55 right, DNge053 left, DNge053 right,
DNp44 left.

**Confirmed by lineage (4).** These ids are stale, i.e. the segment has been
edited since, but mapping them forward lands on the cell CAVE names:

```
DNp62 left  720575941652883477 -> 720575941473533707 / 720575941541317106  = CAVE DNp62
DNp62 right 720575941492125902 -> 720575941479268913                       = CAVE DNp62
DNp42 right 720575941394119830 -> 720575941451785053                       = CAVE DNp42
DNp44 right 720575941554172807 -> 720575941482248160                       = CAVE DNp44
```

Stale is not wrong here: the precomputed mesh bucket is a frozen snapshot, so
these ids still render, and they are the right neurons at an earlier state.

**Unconfirmable, not contradicted (1):** DNp42 left. CAVE holds only one DNp42
and it is the right-side cell, so there is nothing to compare against.

**Contradicted (2): the DNg70 pair.** This one does not resolve, and it is not a
case of missing annotation:

```
supplied DNg70 left  720575941352918576  -> tagged DNxn180, is CURRENT
supplied DNg70 right 720575941478429802  -> no type tag,    is CURRENT
CAVE cells tagged DNg70: 720575941448018196, 720575941482814371, both CURRENT
```

Both sets are current, and neither maps onto the other, so proofreading drift does
not explain it. Rendered as supplied rather than substituted, because the ids were
given explicitly and the official cluster states may be the better authority than
`cell_info`, whose type tags are known to be patchy. Flagged for a decision.

### Alignment was measured, not assumed

Every action layer draws a subset of the base's cells, so its lit pixels must fall
inside the base's. A 3 px shifted copy is scored the same way as a control:

| layer | lit px | inside base | CONTROL shifted 3 px |
|---|---|---|---|
| forward | 49,174 | **99.90%** | 86.66% |
| turn-left | 13,098 | **99.99%** | 93.45% |
| turn-right | 13,489 | **100.00%** | 94.91% |

`turn-left` and `turn-right` overlap by **0.00%** of their union, as two opposite
sides of the animal should.

**Handedness note.** The camera's right vector is dominated by +x, and the
animal's left is the higher-x side, so the *left* layer lights up on the *right*
of the frame. That follows from the DNa01 labels supplied and is self consistent,
but it is worth confirming against the app's steering controls.

## Open, for when the render exists

- At the Neuroglancer camera the cast covers only **3.58%** of the 4:3 frame and
  sits in a narrow vertical column: measured content bbox on a test frame was
  20.6% of the width against 70.5% of the height. If the panel crops rather than
  letterboxes, a tighter crop may be wanted; the WebP script prints the content
  bounding box and height fill so that can be decided from measurement.
