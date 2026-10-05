# BANC neural asset handoff

**For the agent building the Be the Fly app. Written by the agent that rendered these.**

Everything below was rendered from the BANC connectome and audited. This document is
what the assets are, how they compose, and the few rules that must not be broken.
It does not tell you how to build the app.

---

## 1. The one thing to get right

**All BANC layers share one locked camera and are pixel-registered.** They are
designed to be stacked, not swapped. Composite them in this order:

```
banc-context-base.webp        always visible, bottom
  + one or more action layers  fade in and out on top
```

Every action layer is a subset of the cells drawn in the context base, so an
action layer's lit pixels fall **inside** the base's. Measured: 99.37% to 100.00%
inside, against a 3 px shifted control that scores 89% to 98%. That control exists
so the check can fail; it never did.

Do not scale, crop or letterbox the layers differently from one another. All are
**1600 x 1200**, full canvas preserved, transparent background, **straight
(unpremultiplied) alpha, no black matte**, lossless WebP. Alpha survives encoding
at **0/255 delta** on every file.

---

## 2. BANC layer inventory

Location: `banc-explorer/public/`

| file | cells | colour | what it is |
|---|---|---|---|
| `banc-context-base.webp` | **122** | `#52675E` gray | every cell, at rest. Always visible. |
| `banc-forward.webp` | 6 | scene | DNg100 pair, AN09B029_b pair, AN02A002 pair |
| `banc-backward.webp` | 4 | `#ff1493` | MDN, "moonwalk" |
| `banc-turn-left.webp` | 2 | `#ff1493` | DNa01 + DNa02, anatomical left |
| `banc-turn-right.webp` | 2 | `#ff1493` | DNa01 + DNa02, anatomical right |
| `banc-eat.webp` | 6 | `#FFC857` | DNg70, DNp44, DNp62 |
| `banc-threat-walk.webp` | 5 | `#FF6B5F` | DNp42, DNg55, DNge053 |
| `banc-flight-dodge-dnp03-all.webp` | 2 | `#FF8FA8` | DNp03, both hemispheres |
| `banc-flight-dodge-dnp03-anatomical-left.webp` | 1 | `#FF8FA8` | DNp03, anatomical left |
| `banc-flight-dodge-dnp03-anatomical-right.webp` | 1 | `#FF8FA8` | DNp03, anatomical right |
| `banc-groom-head-dng12.webp` | 28 | `#C7A6F3` | DNg12 population, anterior grooming |

`banc-walking-steering-poster.webp` is an earlier standalone 81-cell poster in the
original magenta/green scene colours. It is **not** part of the layer stack and is
not registered for compositing use. Ignore it unless you specifically want it.

---

## 3. Animated sequences

Non-looping, transparent, same camera, same registration rules.

| directory | frames | fps | duration | notes |
|---|---|---|---|---|
| `banc-flight-dodge-anatomical-left/` | 12 | 24 | 500 ms | `frame-00` … `frame-11` |
| `banc-flight-dodge-anatomical-right/` | 12 | 24 | 500 ms | independently triggerable |
| `banc-groom-head-dng12/` | 16 | 24 | 667 ms | `frame-00` … `frame-15` |

**Frame 00 and the final frame are fully transparent in every sequence.** That is
deliberate: these are one-shots that begin and end clean, so you do not need to
fade them in or out yourself. Do not loop them.

The dodge sequences carry a travelling glow down the descending axon. The grooming
sequence carries a pulse along each cell's own skeleton, plus a faintly visible
mesh at 13% opacity and the skeleton itself at 22%.

### Suggested dodge timing, from the render brief

Spider or loom cue appears → about **100 ms** later play the dodge pulse → begin
the bank or yaw shortly after pulse onset → finish the turn in about **500 ms** →
return to the sustained flight layer → **update the heading readout after the fly
has rotated, not before** → add a cooldown so the dodge cannot loop continuously.

### Body behaviour, for animating the fly itself

- **DNg12 grooming:** the fly stops, raises its front legs, and alternates head
  sweeps with front-leg rubbing.
- **DNp03 dodge:** a fast aerial flight saccade, not a takeoff.

---

## 4. The EPG set is a separate thing. Read this before using it.

Location: `D:\Meshes\renders\epg\` (**not** currently in `public/`)

| file | what |
|---|---|
| `epg-base.webp` | all 53 EPG cells, dim and desaturated |
| `epg-heading-00.webp` … `epg-heading-15.webp` | 16 directional activity-bump overlays |
| `cells/epg-cell-<segID>.png` | 53 per-cell transparent masters |
| `epg-manifest.json` | segID to angle, sector, colour, provenance |

**These use a DIFFERENT camera and a DIFFERENT dataset.** They are FAFB/FlyWire
ellipsoid-body neurons rendered head-on at the ellipsoid body, not BANC whole-CNS.
They are internally registered with each other but are **not** registered with any
`banc-*` layer. Never composite an EPG layer on top of the BANC context base.

Within the EPG set the same stacking rule applies: `epg-base` always visible, one
heading overlay on top. Headings are 16 sectors of 22.5 degrees, sector 0 centred
at 12 o'clock, advancing counter-clockwise. Adjacent headings are designed to
**crossfade**, which is what produces a smoothly rotating bump without loading
dozens of images. The bump is centre 100%, immediate neighbours 45%, next
neighbours 15%.

---

## 5. Rules that must not be broken

These are scientific-accuracy constraints, not style preferences. They came from
the person who commissioned the renders.

1. **Anatomical side is not behavioural direction.** Files say
   `anatomical-left` and `anatomical-right` because that is what was verified: which
   hemisphere the cell body sits in. Whether left DNp03 turns the fly left is
   **not** established. `behavioral_direction_mapping` is `pending` in the manifest.
   Do not rename these to `dodge-left` / `dodge-right` in UI copy or in code until
   someone validates the mapping.

2. **Never call a response circuit a detector.** The coral layer is
   **THREAT RESPONSE**, never "threat detection". Those cells produce an escape;
   they are not the visual detection circuit. DNp03 is a **flight-saccade
   response**, also not threat detection.

3. **The animations are explanatory, not recorded.** Required wording, from the
   render brief: *"Explanatory signal animation derived from skeleton geometry and
   synapse-polarity distributions; not recorded action potentials or measured
   conduction timing."* The dodge sequences carry the equivalent disclaimer. The
   travelling glow is an illustration of direction, not measured conduction speed.

4. **The site's existing standard still applies:** *"Structure suggests pathways;
   it does not record neural activity."*

5. **DNg12 wording.** The label is *"BANC DNg12-annotated population — anterior
   grooming"*, and the qualifier is: *"This is the BANC-native DNg12 annotation
   population. It does not imply that every rendered cell was independently
   function-tested."* It is 28 cells, not a bilateral pair.

---

## 6. Not delivered, and why

**wPN1 wing grooming.** Blocked, twice, and it is not a rendering problem.
`wPN1` does not exist as a cell type in BANC. All 380,392 `cell_info` rows and all
11,029 distinct type labels were scanned: zero contain "wpn" in any casing. The
authorized fallback, a MANC to BANC NBLAST crosswalk, then turned out to be
impossible too: `banc_manc_nblast` and `banc_manc_nblast_v2` both contain **0
annotations** and are not materialized in any version, so the published MANC IDs
could not be looked up at all. Do not build UI that expects a wing-grooming layer
until this is resolved.

**Directional takeoff (DNp02, DNp04, DNp11).** Superseded and explicitly cancelled
before rendering. Do not expect these.

---

## 7. Technical facts, if you need them

- Resolution **1600 x 1200** for every asset, BANC and EPG alike.
- **Straight alpha.** Verified by comparing the brightness of semi-transparent edge
  pixels against fully opaque interior pixels: scores 0.947 to 1.096 across the set,
  where a deliberately premultiplied copy of the same image scores 0.22 to 0.27.
- **Denoising disabled** on the EPG and grooming assets, so nothing is filtered
  across the alpha boundary. Maximum RGB under a fully transparent pixel is **0**.
- **Lossless WebP** everywhere. Largest single file is 285.6 KB. The heaviest
  sequence is grooming at 1.0 MB across 16 frames.
- The BANC camera is identical across every `banc-*` asset, sha256
  `fd935462956d98c57e248ae58498b9eee07bce11fcf0569bae216a1f05cb469b`.

## 8. One known imperfection, stated plainly

The grooming sequence frames register at **99.37% to 99.56%** inside the context
base rather than 100%. The cause is the skeleton overlay: it is drawn as a 0.45 µm
tube, and on the thinnest neurites that tube extends marginally past the mesh
silhouette the context base is built from. Shrinking it further would make the
skeleton invisible at 0.76 µm per pixel. Every other asset is 99.93% or better. If
you see a hairline of colour just outside a gray neurite in the grooming
animation, that is this, and it is expected.
