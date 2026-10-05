"""Cable distance field for the feedforward inhibition shot.

Builds, for interneuron 648518346437066458:

  skeletons/inhib_fields.npz    per vertex path distance from the soma, in
                                micrometres, measured along the cell's own
                                surface, plus the real arrival distance for each
                                of the 87 thorny targets.

  python inhib_fields.py [rebuild=1]

Why a surface path field and not a skeleton
-------------------------------------------
The first attempt did it the way ap_fields6.py does, with meshparty. It failed,
twice, and both failures are worth recording.

1. The decimated copy already on disk, D:/Meshes/inhibitory ca3 28/*.obj, is
   unusable: 37,345 vertices shattered into 4,721 connected components, the
   largest holding 1,148, the soma sitting in a component of FOUR vertices, and
   stray geometry out at z = 655,488 nm when the tissue block ends at 96,439.
   Measured before use, not assumed.

2. Re-decimating the clean hq copy to 250k faces and running
   meshparty.skeletonize_mesh(invalidation_d=2000) gave 14,006 nodes that cover
   the dendrites and miss the axon. Measured: only 8 percent of this cell's 2,025
   outgoing synapses land within 2 um of that skeleton, median 19.05 um away,
   while 100 percent of them land within 2 um of the mesh itself. A skeleton that
   does not pass through the cable carrying the output cannot time the output.

So the graph used here is the mesh's own edge graph, at full native resolution,
and the field is a Dijkstra out of the soma across it. On a process 0.2 to 0.5 um
across, the shortest path over the surface runs essentially axially, so this is
cable distance to within the tube radius plus the few percent that graph distance
on a triangulation always runs long. It is not a centreline and is not claimed to
be one. What it buys is that every render vertex carries its own value directly,
so there is no nearest node lookup, no parked-value interleaving and no corridor
threshold to tune.

Traps this file is written against, all from RENDERING_NEURONS.md:

  * Synapse coordinates from CAVE are ALREADY nanometres. Nothing is scaled here.
    Asserted against the mesh bounding box rather than taken on trust.
  * Mesh vertices, synapse coordinates and the nucleus table all share one raw
    file space. No axis conversion happens in this file at all. The Blender side
    does the conversion, and only when placing objects.
  * The soma is a degree two node in the skeleton, a tip rather than a hub, so
    cable paths route around it. Every vertex inside the soma radius is clamped
    to zero, which is also the honest description of a structure that size.
  * Never derive the span from values.max(). Dark vertices are parked far past
    the end of the sweep, so the true span is stored separately.
  * Autapses. The outgoing CSV is checked to be already filtered, and the check
    fails loudly if it is not.
  * Detached cable gets no invented arrival time. It stays dark and is counted.
"""
import os
import sys
import time

import numpy as np
import pandas as pd
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components, dijkstra
from scipy.spatial import cKDTree

opts = dict(t.split("=", 1) for t in sys.argv[1:] if "=" in t)

SKEL = r"D:/Meshes/skeletons"
RENDERS = r"D:/Meshes/renders"
INTER = 648518346437066458
# The copy that is actually in the scene cache: 1,557,883 vertices, 3,064,260
# faces, clean at the tissue boundary (z 4,326 to 96,436).
SRC = r"D:/Meshes/hq/inhibitory ca3 28/648518346437066458.obj"
OUT = f"{SKEL}/inhib_fields.npz"

# Nucleus centre. The nuclei table stores pt_position in VOXELS and the file does
# not say at what resolution, so it is solved against a known ground truth rather
# than assumed: the hero pyramidal's soma centre was measured empirically at
# [1041862, 1145798, 75977] nm by voxel fill, and its nucleus row sits at
# [57856, 63648, 1689], which gives 18.0 / 18.0 / 45.0 nm per voxel.
NUC_RES = np.array([18.0, 18.0, 45.0])
HERO = 648518346438632877
HERO_SOMA_NM = np.array([1041862.0, 1145798.0, 75977.0])
STORYBOARD_SOMA = np.array([838924.0, 989815.0, 56640.0])

SOMA_R_UM = 9.0          # nucleus equivalent radius is 6.68 um, measured below
# The mesh is shredded by the segmentation, so its edge graph is a forest and a
# Dijkstra out of the soma reaches almost nothing until the holes are bridged.
# Kept short on purpose: a long bridge can jump between two branches that merely
# pass close to one another and would then light a distant fragment far too early.
MAX_BRIDGE_NM = 2000.0
BRIDGE_K = 12


def log(*a):
    print(*a, flush=True)


def load_obj(path):
    """Vertices and triangles from an ASCII OBJ, without trimesh's processing.

    trimesh.load takes about 90 s on this 365 MB file and merges vertices, which
    would break the one thing the Blender side depends on: that vertex i here is
    vertex i in the imported object.
    """
    vs, fs = [], []
    with open(path) as fh:
        for line in fh:
            if line.startswith("v "):
                vs.append(line[2:])
            elif line.startswith("f "):
                fs.append(line[2:])
    v = np.fromstring(" ".join(vs), sep=" ").reshape(-1, 3)
    # faces may be "a b c" or "a/vt/vn b/vt/vn c/vt/vn"
    raw = " ".join(fs)
    if "/" in raw:
        raw = raw.replace("//", " ").replace("/", " ")
        f = np.fromstring(raw, sep=" ", dtype=np.int64)
        f = f.reshape(len(fs), -1)[:, ::(f.size // len(fs)) // 3]
    else:
        f = np.fromstring(raw, sep=" ", dtype=np.int64).reshape(-1, 3)
    return v, f - 1


# ---------------------------------------------------------------- 1. resolution
nu = pd.read_csv(f"{RENDERS}/_nuclei.csv")


def nucleus_nm(root_id):
    rows = nu[nu.pt_root_id == root_id].sort_values("volume", ascending=False)
    if not len(rows):
        return None, None
    p = np.array([float(t) for t in str(rows.pt_position.iloc[0]).strip("[]").split()])
    return p * NUC_RES, float(rows.volume.iloc[0])


check, _ = nucleus_nm(HERO)
err = float(np.linalg.norm(check - HERO_SOMA_NM))
log(f"nuclei resolution check: hero nucleus at {check.round(0)} nm against the "
    f"independently measured soma centre {HERO_SOMA_NM.round(0)}, "
    f"{err/1000:.2f} um apart")
assert err < 3000.0, "the nuclei voxel resolution assumption is wrong"

soma_nm, soma_vol = nucleus_nm(INTER)
d_story = float(np.linalg.norm(soma_nm - STORYBOARD_SOMA)) / 1000.0
log(f"interneuron nucleus at {soma_nm.round(0)} nm, volume {soma_vol:.0f} um^3, "
    f"equivalent radius {(3*soma_vol/(4*np.pi))**(1/3):.2f} um, {d_story:.1f} um "
    f"from the storyboard's stated soma [838924, 989815, 56640]")
assert d_story < 15.0, "nucleus and storyboard soma disagree by more than a soma width"

# ---------------------------------------------------------------- 2. mesh graph
MESH_CACHE = f"{SKEL}/_{INTER}_meshgraph.npz"
if os.path.exists(MESH_CACHE) and opts.get("rebuild") != "1":
    z = np.load(MESH_CACHE)
    v, e, nfaces = z["v"], z["e"], int(z["nfaces"])
    log(f"\nmesh graph from cache: {len(v):,} vertices, {len(e):,} edges")
else:
    t0 = time.time()
    v, f = load_obj(SRC)
    log(f"\nmesh: {len(v):,} vertices, {len(f):,} faces, loaded in "
        f"{time.time()-t0:.0f}s")
    e = np.vstack([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]])
    e = np.unique(np.sort(e, axis=1), axis=0)
    nfaces = len(f)
    np.savez(MESH_CACHE, v=v, e=e, nfaces=nfaces)
log(f"  bbox {v.min(0).round(0)} to {v.max(0).round(0)} nm")
assert np.all(soma_nm > v.min(0)) and np.all(soma_nm < v.max(0)), \
    "the nucleus centre falls outside the mesh bounding box"
w = np.linalg.norm(v[e[:, 0]] - v[e[:, 1]], axis=1) / 1000.0
log(f"  edge graph: {len(e):,} unique edges, median length "
    f"{np.median(w)*1000:.0f} nm, {int((w==0).sum()):,} of length exactly zero")

nv = len(v)


def comps(edges):
    m = coo_matrix((np.ones(len(edges)), (edges[:, 0], edges[:, 1])), shape=(nv, nv))
    return connected_components(m + m.T, directed=False)


ncomp, lab = comps(e)
log(f"  {ncomp:,} connected components, largest holds "
    f"{np.bincount(lab).max():,} of {nv:,} vertices")

# ------------------------------------------------- 3. bridge the segmentation holes
# The gaps are holes in the EM segmentation, not real breaks in the cable. Bridges
# are added shortest first and only when they MERGE two components, so no bridge
# ever creates a shortcut inside cable that is already connected.
t0 = time.time()
tree = cKDTree(v)
dd, ii = tree.query(v, k=BRIDGE_K, distance_upper_bound=MAX_BRIDGE_NM,
                    workers=-1)
cand = []
for col in range(1, dd.shape[1]):
    a = np.arange(nv)
    b = ii[:, col]
    ok = np.isfinite(dd[:, col]) & (b < nv)
    ok &= np.where(ok, lab[np.where(ok, b, 0)] != lab[a], False)
    if ok.any():
        cand.append(np.column_stack([dd[ok, col], a[ok], b[ok]]))
cand = np.vstack(cand) if cand else np.zeros((0, 3))
cand = cand[np.argsort(cand[:, 0])]
log(f"\n{len(cand):,} candidate bridges under {MAX_BRIDGE_NM/1000:.1f} um "
    f"in {time.time()-t0:.0f}s")

uf = np.arange(ncomp)


def find(x):
    r = x
    while uf[r] != r:
        r = uf[r]
    while uf[x] != r:
        uf[x], x = r, uf[x]
    return r


bridges = []
for d, x, y in cand:
    rx, ry = find(lab[int(x)]), find(lab[int(y)])
    if rx != ry:
        uf[rx] = ry
        bridges.append((d, int(x), int(y)))
if bridges:
    be = np.array([[x, y] for _, x, y in bridges], np.int64)
    bw = np.array([d for d, _, _ in bridges]) / 1000.0
    e = np.vstack([e, be])
    w = np.concatenate([w, bw])
    log(f"bridged {len(bridges):,} of {ncomp-1:,} gaps: median {np.median(bw):.2f} um, "
        f"p90 {np.percentile(bw,90):.2f} um, longest {bw.max():.2f} um")
ncomp2, lab = comps(e)
log(f"after the k nearest pass: {ncomp2:,} components, largest holds "
    f"{np.bincount(lab).max():,} of {nv:,} vertices "
    f"({100*np.bincount(lab).max()/nv:.1f}%)")

# A k nearest pass alone is not enough, and the way it fails is worth recording.
# In a dense region every one of a vertex's 12 nearest neighbours belongs to its
# own component, so no cross component candidate is ever generated there. The
# soma is the densest region on the cell, which is why the first run left it
# stranded in a component of 5,914 vertices with 153,234 vertices sitting within
# 9 um of it, and a Dijkstra that travelled 7 um in total.
#
# Second pass: each round, take the largest component, and for every other
# component find its single closest approach to it. Component to component, so
# density cannot hide the gap.
MAX_BRIDGE2_NM = 6000.0
for rnd in range(8):
    ncomp2, lab = comps(e)
    if ncomp2 == 1:
        break
    sizes = np.bincount(lab)
    big = int(np.argmax(sizes))
    idx_big = np.where(lab == big)[0]
    tb = cKDTree(v[idx_big])
    new, gaps = [], []
    for c in range(ncomp2):
        if c == big:
            continue
        idx_c = np.where(lab == c)[0]
        d, j = tb.query(v[idx_c], k=1, workers=-1)
        k = int(np.argmin(d))
        gaps.append(d[k])
        if d[k] <= MAX_BRIDGE2_NM:
            new.append((int(idx_c[k]), int(idx_big[j[k]]), float(d[k])))
    if not new:
        log(f"  round {rnd+1}: nothing left within {MAX_BRIDGE2_NM/1000:.0f} um, "
            f"closest remaining approach {min(gaps)/1000:.1f} um")
        break
    e = np.vstack([e, np.array([[a, b] for a, b, _ in new], np.int64)])
    w = np.concatenate([w, np.array([g for _, _, g in new]) / 1000.0])
    g2 = np.array([g for _, _, g in new]) / 1000.0
    log(f"  round {rnd+1}: joined {len(new)} components to the main body, gaps "
        f"median {np.median(g2):.2f} um, longest {g2.max():.2f} um")

ncomp2, lab = comps(e)
sizes = np.bincount(lab)
log(f"after bridging: {ncomp2:,} components, largest holds {sizes.max():,} of "
    f"{nv:,} vertices ({100*sizes.max()/nv:.1f}%)")

# ---------------------------------------------------------------- 4. the field
soma_v = int(np.argmin(np.linalg.norm(v - soma_nm, axis=1)))
log(f"\nsoma vertex {soma_v} at {v[soma_v].round(0)}, "
    f"{np.linalg.norm(v[soma_v]-soma_nm)/1000:.2f} um from the nucleus centre")

t0 = time.time()
# scipy's csgraph treats an EXPLICIT ZERO as a non-edge rather than as a
# zero-length edge, so a duplicated vertex pair would be silently deleted from
# the graph while connected_components, which reads the sparsity pattern, still
# counted it. A floor of one picometre makes the two agree. It is a guard, not a
# fix: this mesh measures 0 edges of length exactly zero, and the real cause of
# the first run's 5,914 node Dijkstra was the k nearest bridging pass below.
w = np.maximum(w, 1e-6)
g = coo_matrix((w, (e[:, 0], e[:, 1])), shape=(nv, nv))
g = (g + g.T).tocsr()
dist = dijkstra(g, directed=False, indices=soma_v)
reach = np.isfinite(dist)
log(f"Dijkstra out of the soma in {time.time()-t0:.0f}s: {reach.sum():,} of "
    f"{nv:,} vertices reachable ({100*reach.mean():.1f}%), farthest "
    f"{dist[reach].max():.0f} um of path")

# The soma depolarises as a unit. Clamping it is both the fix for a soma that is
# a tip rather than a hub, and the honest description of a structure that size.
r_soma = np.linalg.norm(v - v[soma_v], axis=1) / 1000.0
in_soma = r_soma < SOMA_R_UM
was = dist[in_soma & reach]
field = dist.copy()
field[in_soma] = 0.0
log(f"soma: {int(in_soma.sum()):,} vertices within {SOMA_R_UM:.0f} um clamped to "
    f"0; they spanned {was.min():.1f} to {was.max():.1f} um beforehand")

lit = np.isfinite(field)
span = float(field[lit].max())
field[~lit] = span * 10.0        # parked far past the end, never normalised by max()
log(f"field span 0 to {span:.0f} um, {int(lit.sum()):,} vertices ever light "
    f"({100*lit.mean():.1f}%)")

# ---------------------------------------------------------------- 5. synapses
out = pd.read_csv(f"{RENDERS}/_out_{INTER}.csv")
n_auto = int((out.post_pt_root_id == out.pre_pt_root_id).sum())
assert n_auto == 0, (f"{n_auto} autapses still in the outgoing set. Filter "
                     f"post_pt_root_id != pre_pt_root_id and drop ids that also "
                     f"appear in the incoming set before using these counts.")
assert out.id.is_unique, "duplicate synapse ids in the outgoing set"
assert (out.pre_pt_root_id == INTER).all(), "the outgoing set is not all this cell"
log(f"\noutgoing: {len(out):,} synapses, {n_auto} autapses, "
    f"{out.post_pt_root_id.nunique():,} distinct targets")

syn_nm = np.stack([np.fromstring(str(s).strip("[]"), sep=" ")
                   for s in out.ctr_pt_position]).astype(float)
lo, hi = v.min(0) - 20000, v.max(0) + 20000
assert np.all((syn_nm >= lo) & (syn_nm <= hi)), \
    "outgoing synapses fall outside the mesh bbox; the coordinates are not nanometres"
d_syn, i_syn = tree.query(syn_nm, k=1, workers=-1)
log(f"units check: all {len(syn_nm):,} outgoing synapses lie inside the mesh bbox "
    f"and a median {np.median(d_syn):.0f} nm off its surface, so they are "
    f"nanometres and are NOT scaled")


def seg_ids(folder):
    return {int(fn[:-4]) for fn in os.listdir(folder) if fn.endswith(".obj")}


thorny_all = seg_ids(r"D:/Meshes/thorny pyramidals ca3 250")
sparse_all = seg_ids(r"D:/Meshes/sparsely thorny pyramidals ca3 68")
vc = out.post_pt_root_id.value_counts()
th_hit = vc[vc.index.isin(thorny_all)]
sp_hit = vc[vc.index.isin(sparse_all)]
log(f"targets we hold meshes for: {len(th_hit)} thorny / {int(th_hit.sum())} "
    f"synapses, {len(sp_hit)} sparsely thorny / {int(sp_hit.sum())} synapses")
assert (len(th_hit), int(th_hit.sum())) == (87, 333), "thorny counts moved"
assert (len(sp_hit), int(sp_hit.sum())) == (21, 50), "sparsely thorny counts moved"
per_th = int(th_hit.sum()) / len(thorny_all)
per_sp = int(sp_hit.sum()) / len(sparse_all)
log(f"selectivity: {per_th:.2f} synapses per available thorny cell against "
    f"{per_sp:.2f} per sparsely thorny, a factor of {per_th/per_sp:.2f}")

# ---------------------------------------------------------------- 6. arrivals
post = out.post_pt_root_id.values
syn_d = np.where(reach[i_syn], dist[i_syn], np.nan)


def arrivals_for(index):
    ids, arr, miss = [], [], []
    for tid in index:
        d = syn_d[post == tid]
        d = d[np.isfinite(d)]
        if len(d):
            ids.append(int(tid))
            arr.append(float(d.min()))
        else:
            miss.append(int(tid))
    o = np.argsort(arr)
    return (np.array(ids, np.int64)[o], np.array(arr)[o], np.array(miss, np.int64))


th_ids, th_arr, th_miss = arrivals_for(th_hit.index)
sp_ids, sp_arr, sp_miss = arrivals_for(sp_hit.index)
log(f"\narrivals: {len(th_ids)} of 87 thorny targets sit on cable connected to "
    f"the soma, from {th_arr.min():.0f} to {th_arr.max():.0f} um of path "
    f"(median {np.median(th_arr):.0f}); {len(th_miss)} do not and stay unlit")
log(f"the 21 sparsely thorny targets: {len(sp_ids)} timed the same way, kept so "
    f"beat 6 can pulse them honestly")

# how much of the wave's run is spent reaching targets, which sets the beat 5 timing
q = np.percentile(th_arr, [10, 50, 90])
log(f"thorny arrival percentiles: p10 {q[0]:.0f} um, p50 {q[1]:.0f} um, "
    f"p90 {q[2]:.0f} um, against a {span:.0f} um span")

# ---------------------------------------------------------------- 7. the 7 inputs
mf = pd.read_csv(f"{RENDERS}/mf_synapses.csv")
inc = mf[mf.post_pt_root_id == INTER].copy()
assert len(inc) == 7 and inc.pre_pt_root_id.nunique() == 7, "the 7 MF inputs moved"
mf_nm = np.stack([np.fromstring(str(s).strip("[]"), sep=" ")
                  for s in inc.ctr_pt_position]).astype(float)
mf_pre = inc.pre_pt_root_id.values.astype(np.int64)
mf_d = np.linalg.norm(mf_nm - soma_nm, axis=1) / 1000.0
order = np.argsort(mf_d)
mf_nm, mf_pre, mf_d = mf_nm[order], mf_pre[order], mf_d[order]
log("\nmossy fibre contacts onto this interneuron, by straight line distance "
    "from the soma:")
for k in range(7):
    log(f"  {mf_pre[k]}  {mf_d[k]:6.1f} um  at {mf_nm[k].astype(int)}")

np.savez_compressed(
    OUT,
    seg_id=np.array(INTER),
    n_verts=np.array(nv),
    vert0=v[:64], vertN=v[-64:],      # fingerprint, so Blender can assert the order
    field=field.astype(np.float32), span=np.array(span),
    lit=lit,
    soma_nm=soma_nm, soma_vert=np.array(soma_v), soma_r_um=np.array(SOMA_R_UM),
    thorny_ids=th_ids, thorny_arrival_um=th_arr, thorny_unreached=th_miss,
    thorny_syn_counts=np.array([int(th_hit[i]) for i in th_ids], np.int64),
    sparse_ids=sp_ids, sparse_arrival_um=sp_arr, sparse_unreached=sp_miss,
    sparse_syn_counts=np.array([int(sp_hit[i]) for i in sp_ids], np.int64),
    out_syn_nm=syn_nm, out_syn_post=post.astype(np.int64), out_syn_dist_um=syn_d,
    mf_syn_nm=mf_nm, mf_pre=mf_pre, mf_soma_dist_um=mf_d,
)
log(f"\nwrote {OUT} ({os.path.getsize(OUT)/1e6:.1f} MB)")
