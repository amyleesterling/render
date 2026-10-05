# CA3 skeletons for the action-potential animation

Produced 2026-07-29. Hero thorny pyramidal `648518346438632877` plus its 6 mossy
fibres. Everything here is centreline data plus ordered paths for driving a
travelling pulse. No Blender code, no renders.

## TL;DR for the Blender side

```python
import json, numpy as np
d = np.load(r"D:\Meshes\skeletons\648518346438632877.npz", allow_pickle=True)
pts = d["vertices"]                       # (N,3) float, NANOMETRES, OBJ file space

# REQUIRED axis conversion. Blender's OBJ importer maps file (x,y,z) -> (x,-z,y),
# so every OBJ in the scene already went through this. The skeletons did NOT.
pts = np.column_stack([pts[:, 0], -pts[:, 2], pts[:, 1]])

# then apply whatever object scale/offset the scene uses for the imported OBJs.

paths = json.load(open(r"D:\Meshes\skeletons\ap_paths.json"))
p = paths["cells"]["648518346438632877"]["paths"][0]
idx = p["indices"]     # ordered node indices, soma -> tip
arc = p["arc_um"]      # cumulative micrometres along that path, same length as idx
```

Pulse position at time `t` with conduction velocity `v` um/ms: find where
`arc_um` crosses `v*t` and interpolate between the two bracketing nodes.

## Units and coordinate space

- Vertices are in **nanometres**.
- They are in **OBJ file space**, byte-identical in convention to the `.obj`
  files in `D:\Meshes\hero\`. **No transform has been pre-applied.**
- Verified empirically, not assumed. The hero skeleton bounding box sits just
  inside the hero OBJ bounding box, as a centreline must:

  | | x | y | z |
  |---|---|---|---|
  | hero OBJ min | 879405 | 1019245 | 4324 |
  | hero skeleton min | 882306 | 1020366 | 4320 |
  | hero OBJ max | 1216355 | 1284780 | 96439 |
  | hero skeleton max | 1211670 | 1282500 | 96435 |

  Extent ratio 0.98 / 0.99 / 1.00. No scale factor, no origin offset, identity
  transform between the two.
- Cross-checked a second way: the 165 mossy-fibre synapses in
  `D:\Meshes\renders\mf_synapses.csv` land a median of **0.24 to 0.88 um** from
  the fibre centrelines. Those CSV coordinates turn out to be **already in
  nanometres** (no voxel scaling needed), same space as everything else.
- Every `*_um` field in the JSON is micrometres.

## Where the skeletons came from

CAVE **does** serve precomputed skeletons for `zheng_ca3`:

```
client.info.get_datastack_info()["skeleton_source"]
  precomputed://middleauth+https://minnie.microns-daf.com/skeletoncache/api/v1/zheng_ca3/precomputed/skeleton
client.skeleton.get_versions()  ->  [-1, 0, 1, 2, 3, 4]
client.skeleton.get_skeleton(root_id, output_format="dict")
  keys: meta, edges, mesh_to_skel_map, root, vertices, compartment, radius, lvl2_ids
```

They were fetched and kept, but they are **far too coarse to animate**. They are
`pcg_skel` skeletons built on the level-2 chunked graph with
`invalidation_d = 7500 nm`, so the hero gets 392 nodes for a whole pyramidal cell
and a mossy fibre gets 21 to 34 nodes. Node spacing is about 6.6 um.

So each cell was re-skeletonised locally with
`meshparty.skeletonize.skeletonize_mesh(invalidation_d=2000, smooth_vertices=True)`
and then recentred onto the tube axis. That is 40x to 100x denser.

Coverage comparison for the hero, measured as the fraction of native mesh
vertices lying within a given distance of the skeleton:

| within | CAVE pcg_skel | meshparty (used) |
|---|---|---|
| 1 um | 9.1% | 32.5% |
| 2 um | 33.1% | 78.2% |
| 3 um | **59.0%** | **95.2%** |
| 5 um | 93.4% | 98.4% |

### File layout

| file | what |
|---|---|
| `<segid>.npz` | **canonical, use this.** Densest skeleton, recentred, rooted, with `parent` and `dist_from_root_um` precomputed. |
| `<segid>_meshparty.npz` | the meshparty skeleton before rooting |
| `<segid>_cave.npz` | the raw CAVE precomputed skeleton, kept for its extra fields |
| `ap_paths.json` | ordered soma-to-tip and along-fibre paths. This is what the animation consumes. |
| `report.json` | all per-cell numbers in machine-readable form |
| `_soma.json` | measured soma centre, volume, radius |

Keys in `<segid>.npz`: `vertices` (N,3 float nm), `edges` (M,2 int), `root` (int),
`parent` (N int, -1 at root), `dist_from_root_um` (N float, NaN for nodes in
disconnected fragments), `source`, `seg_id`, `coordinate_space`.

## Per-cell counts

| segment | role | nodes | edges | cable um | tips | root to farthest tip um | node spacing um | CAVE nodes |
|---|---|---|---|---|---|---|---|---|
| 648518346438632877 | hero thorny pyramidal | 3203 | 3190 | 3779.0 | 517 | 284.3 | 1.19 | 392 |
| 648518346432881590 | mossy fibre | 2536 | 2531 | 248.7 | 22 | 220.6 | 0.10 | 34 |
| 648518346440660317 | mossy fibre | 1755 | 1751 | 181.5 | 15 | 163.4 | 0.10 | not served |
| 648518346448994107 | mossy fibre | 2486 | 2480 | 247.9 | 30 | 150.0 | 0.10 | 30 |
| 648518346450631673 | mossy fibre | 1505 | 1501 | 161.8 | 15 | 129.2 | 0.11 | 21 |
| 648518346452106477 | mossy fibre | 1956 | 1953 | 193.1 | 20 | 125.7 | 0.10 | 28 |
| 648518346460875907 | mossy fibre | 1567 | 1564 | 167.1 | 10 | 154.8 | 0.11 | not served |

Every skeleton has a few small disconnected fragments (holes in the EM
segmentation). The largest connected component holds 91% to 98% of nodes
(hero: 3037 of 3203). All paths in `ap_paths.json` live inside the component
containing the root, so the fragments never appear in an animation.

## Roots

`zheng_ca3` has **no soma table** (`soma_table: None` in the datastack info), so
`soma_pt` was `None` when CAVE built its skeletons and the `root` field it
returns is **an arbitrary degree-1 tip, not the soma**. For the hero, CAVE's
`root` is node 0, which sits at a dendrite tip 3.7 um wide. Do not trust it.

The soma was located empirically instead: voxelise the native mesh at 300 nm in
a box around each candidate, close and fill it, and measure the largest enclosed
interior blob.

- soma centre **[1041862, 1145798, 75977] nm** (OBJ file space)
- enclosed volume **1333 um^3**, equivalent radius **6.83 um**

That is a normal CA3 pyramidal soma. Every other candidate node returned an
interior blob under 20 um^3, i.e. dendrite calibre, so the identification is
unambiguous. The hero is rooted at the skeleton node nearest that centre.

Mossy fibres are rooted at **the end of the fibre farthest from its synapses
onto the hero**, so a pulse launched at the root travels toward the boutons,
which is the correct physiological direction.

## Cable-length sanity check, read this

**The hero's 3779 um of cable is below the textbook range and should not be
reported as this cell's true total dendritic length.** A complete CA3 pyramidal
cell carries roughly 8000 to 16000 um of dendrite in rat, less in mouse.

Independent cross-check from membrane area, which does not depend on the
skeleton at all:

- native hero mesh surface area **26693 um^2** (4471568 faces)
- same mesh decimated and smoothed, thorns removed: **14341 um^2**
- measured median local cable radius **0.27 um** (p90 0.61 um)
- for a cylinder, cable = area / (2 pi r), giving roughly **5700 to 8500 um**

So the true cable is probably around 6000 to 8500 um and the skeleton recovers
roughly half of it. Two reasons, both real:

1. **The cell is truncated by the EM volume.** The hero mesh spans z 4324 to
   96439 nm, and so does every single one of the 6 mossy fibres, to the
   nanometre. That is the tissue block boundary, not biology. These arbors are
   cut off top and bottom.
2. The meshparty pass ran on a 30216-vertex decimated copy of the hero, which
   drops the thinnest terminal branches. A run on the full 2.28M-vertex native
   mesh was launched and had not converged after 100 minutes; see "unfinished"
   below.

For an animation this does not matter much. The topology is right, the major
dendrites are all present, and node spacing is 1.19 um. But do not put "3779 um
of dendrite" in a figure caption as if it were the cell's anatomy.

The mossy fibres are truncated the same way: 162 to 249 um each, whereas a real
mossy fibre runs for hundreds of micrometres to millimetres. Fine for animation,
not a biological measurement.

Soma to farthest tip is **284.3 um**, which is reasonable for a CA3 pyramidal
apical dendrite inside a volume this size.

## What is in ap_paths.json

```
_doc          units, coordinate space, the Blender axis conversion
cells[segid]
  role                  "hero_thorny_pyramidal" or "mossy_fibre"
  root, root_note
  soma_centre_nm, soma_volume_um3, soma_equiv_radius_um   (hero only)
  paths[]
    kind        "soma_to_tip" | "main_axis" | "branch"
    indices     ordered node indices into <segid>.npz vertices
    arc_um      cumulative micrometres, same length as indices
    length_um, n_nodes
  synapse_nodes     nearest skeleton node for each synapse
  synapse_xyz_nm    synapse centres, nanometres, same space
```

Hero: 250 `soma_to_tip` paths, every one starting at the soma root, 127.8 to
284.3 um long. The cell has 517 tips; the 250 longest were kept, which covers
every major dendrite. Mossy fibres: one `main_axis` path end to end plus
branches over 3 um.

Validated: all path indices in range, **every consecutive pair in every path is
a real skeleton edge**, every `arc_um` step matches the geometric distance to
within 0.01 um, and every hero path starts at the root. See `validate.py`.

The 165 mossy-fibre synapses are attached to both sides, so the animation can
fire the hero's AP at the right place. Note the hero's synapses sit a median
1.19 um off the dendrite centreline while the fibre-side ones sit 0.24 to 0.88 um
off: that gap is the thorny excrescence itself, which is exactly where mossy
fibre boutons attach. That is a good sign, not an error.

## Fields in the CAVE skeletons, and which are useless here

Kept in `<segid>_cave.npz` for 5 of the 7 cells.

- `radius` (per node, nm). **Constant for several fibres**, because the CAVE
  metadata says `compute_radius: False`. Do not scale a pulse by it without
  checking `cave_radius_is_constant` in `report.json` first.
- `compartment`. **Carries no usable information in this dataset.** The only
  values present anywhere are 1 and 3, and 3 dominates. There is no axon label
  (2). It cannot separate axon from dendrite here, so it cannot be used to
  colour the two differently. That has to come from geometry instead.
- `mesh_to_skel_map`. **This is not a mesh-vertex map.** Its length equals
  `len(lvl2_ids)`, not the OBJ vertex count: 1073 vs 2278184 for the hero,
  40 vs 48999 for a fibre. It maps level-2 chunkedgraph nodes to skeleton nodes.
  It cannot be used to drive per-vertex emission on the imported OBJ. To light
  the mesh surface, query the nearest skeleton node per mesh vertex with a
  cKDTree at load time instead.

## What did not work

- `client.skeleton.skeletons_exist()` showed only the hero was cached. The 6
  fibres had to be generated on demand, and the service returned **HTTP 504
  Gateway Timeout** on nearly every request, after 240 to 724 seconds each.
  Four fibres eventually landed after repeated retries; two
  (`648518346440660317`, `648518346460875907`) never did. This is why the local
  meshparty route became the primary one rather than the fallback.
- `trimesh.contains()` on the hero returns 0 for every test point. The mesh is
  not watertight, so that test is meaningless here. The voxel fill-and-close
  method was used instead.
- `trimesh` reports a hero volume of 30713 um^3, which is not trustworthy on a
  non-watertight mesh and is inconsistent with the surface area. Ignore it.
- meshparty's `smooth_vertices=True` is a Laplacian smooth **along the path**,
  not a recentring. Skeleton vertices come back sitting exactly on mesh vertices
  (0 nm from the surface). `recenter.py` fixes this by moving each node to the
  centroid of nearby surface points. Verified: nodes move from 32 nm off the
  surface to about 104 nm, which matches the roughly 0.2 um shaft diameter of a
  mossy fibre axon, and total cable drops about 9% as surface zigzag is removed.

## Unfinished

A meshparty run on the **full 2.28M-vertex native hero mesh**
(`hero_meshparty.py`, `invalidation_d=3000`) was still running after 100 minutes
when this was written. If it completes it will write
`648518346438632877_meshparty.npz` and should recover more of the thin terminal
branches, pushing hero cable closer to the area-based 6000 to 8500 um estimate.
To adopt it:

```
python recenter.py     # recentres the new hero skeleton (skip the fibres, they are done)
python finalize.py     # rebuilds 648518346438632877.npz, ap_paths.json, report.json
python validate.py
```

Nothing else needs to change. Until then the hero comes from the 30216-vertex
decimated mesh, which is already good enough to animate.

## Timing

| step | time |
|---|---|
| CAVE probe and hero skeleton fetch | 7 s |
| CAVE fibre fetches (mostly 504s, 4 of 6 eventually landed) | about 50 min wall clock |
| soma localisation (voxel fill on native mesh) | about 12 min total across passes |
| meshparty on the 6 fibres | about 1 s each |
| meshparty on the decimated hero | 5 s |
| recentring all 7 | 30 s |
| native mesh surface area (trimesh load of 225 MB OBJ) | 89 s |
| finalize + validate | about 1 min |

## Scripts

`probe_cave.py` `fetch2.py` `fetch4.py` (CAVE), `find_soma.py` `blob_hunt.py`
`vol_test.py` `soma_center.py` (soma), `mf_meshparty.py` `hero_meshparty.py`
`crosscheck.py` `recenter.py` (skeletonisation), `finalize.py` `validate.py`
`verify_mf.py` (assembly and checks).
