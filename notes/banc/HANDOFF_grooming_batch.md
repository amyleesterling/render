# Handoff: grooming batch (DNg12)

**For the app agent. Covers only this batch. Nothing else changed.**

---

## What is new

| file | what |
|---|---|
| `public/banc-groom-head-dng12.webp` | static layer, 28 cells, `#C7A6F3`, 69.9 KB |
| `public/banc-groom-head-dng12/frame-00.webp` … `frame-15.webp` | 16-frame signal sequence, 1.0 MB total |
| `public/banc-context-base.webp` | **REGENERATED, re-fetch it** |

## The context base changed. This is the one thing that can bite you.

It went from 94 to **122 cells** because the 28 DNg12 cells were added to it in the
same `#52675E` gray. Same filename, same camera, same registration, so nothing
breaks structurally, but a cached copy will be missing 28 gray neurons and the
grooming layer will appear to light up cells that were never there at rest.
Bust the cache.

## Using it

Same rule as the existing layers: the base is always visible, the action layer
composites on top. The grooming layer is a subset of the base, so its lit pixels
fall inside the base's. Measured 99.99% for the static.

**Sequence:** 16 frames, **24 fps**, **667 ms**, **non-looping**.
`frame-00` and `frame-15` are **fully transparent** by design, so the sequence
begins and ends clean and you do not need to fade it in or out. Do not loop it.
Add a cooldown if it is player-triggered.

1600 x 1200, transparent, straight alpha, lossless WebP, same camera as every
other `banc-*` asset.

**Body behaviour to animate alongside it:** the fly stops, raises its front legs,
and alternates head sweeps with front-leg rubbing.

## Wording that is not optional

Label: **"BANC DNg12-annotated population — anterior grooming"**

Qualifier, if you surface any explanation: *"This is the BANC-native DNg12
annotation population. It does not imply that every rendered cell was
independently function-tested."*

Animation disclaimer: *"Explanatory signal animation derived from skeleton geometry
and synapse-polarity distributions; not recorded action potentials or measured
conduction timing."*

It is **28 cells, not a bilateral pair**. Do not describe it as a pair or as "the
grooming neuron".

## What the animation actually shows

A pulse travelling along each cell's own CAVE skeleton by geodesic path distance,
starting from that cell's input-dominant region, which was located from real
synapse polarity. Branches light up by path distance, so the signal forks where
the arbor forks. The mesh sits at 13% opacity underneath and the skeleton at 22%.

Because each cell runs on its **own** normalised path, the 28 cells do not flash in
unison. Mid-sequence frames read as a broad glow rather than one travelling front.
That is the honest behaviour of per-cell geodesics. Say so if you need to, or ask
for a shared-axis version if you want a more dramatic read.

## Do not build for wing grooming

`wPN1` is **not coming** and there is no asset for it. It does not exist as a cell
type in BANC: all 380,392 annotation rows and all 11,029 distinct type labels were
scanned and none contain "wpn". The authorized MANC crosswalk fallback was also
impossible, because those crosswalk tables contain zero annotations. Do not add a
wing-grooming trigger, button or slot that has nothing behind it.

## One known imperfection

The grooming **sequence** frames register at 99.37% to 99.56% inside the context
base, not 100%. The static is 99.99%. The cause is the skeleton overlay: it is
drawn as a 0.45 µm tube and on the thinnest neurites that tube extends slightly
past the mesh silhouette the context base is built from. Shrinking it further would
make the skeleton invisible at 0.76 µm per pixel. If you see a hairline of lavender
just outside a gray neurite, that is this, and it is expected rather than a
compositing bug.

## Audits, if you want them

`D:\Meshes\renders\layers\groom-head-dng12\qc\`

- `banc-grooming-manifest.json`
- `grooming-cell-identification-audit.csv`
- `grooming-skeleton-polarity-audit.csv`
- `grooming-alignment-audit.csv`
- `grooming-contact-sheet.png`
