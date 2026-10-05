"""Distance fields that an action potential can travel along.

Two of them, for one mossy fibre and the pyramidal cell it contacts:

  fibre  -> path distance from the fibre's far end, so a pulse launched at the
            root runs down the axon and arrives at the boutons.
  cell   -> path distance from the synapse contacts themselves, so the
            depolarisation spreads out of the thorns rather than out of the soma.

Both are per skeleton node. Blender maps them onto mesh vertices with a KD tree,
which keeps this file free of any bpy dependency.
"""
import json
from collections import defaultdict, deque
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra
from scipy.spatial import cKDTree

SKEL = Path(r"D:\Meshes\skeletons")
HERO = 648518346438632877
FIBRE = 648518346448994107          # the fibre making the most contacts, 53
OUT = SKEL / "ap_fields.npz"


def load(seg):
    z = np.load(SKEL / f"{seg}.npz")
    return z["vertices"], z["edges"], z


def graph(verts, edges):
    """Undirected weighted graph, edge weight = euclidean length in micrometres."""
    d = np.linalg.norm(verts[edges[:, 0]] - verts[edges[:, 1]], axis=1) / 1000.0
    n = len(verts)
    m = coo_matrix((d, (edges[:, 0], edges[:, 1])), shape=(n, n))
    return (m + m.T).tocsr()


# ---- the synapses this fibre makes onto this cell ---------------------------------
syn = pd.read_csv(r"D:\Meshes\renders\mf_synapses.csv")
pair = syn[(syn.pre_pt_root_id == FIBRE) & (syn.post_pt_root_id == HERO)]
# stored as "[ 959220 1122966   36675]", whitespace separated, so not json
syn_nm = np.array([np.fromstring(s.strip("[]"), sep=" ")
                   for s in pair["ctr_pt_position"]], dtype=float)
print(f"{len(pair)} synapses from fibre {FIBRE} onto cell {HERO}")

# These are ALREADY nanometres, not voxels. Scaling by the 4/4/40 resolution
# would throw them a thousand micrometres out of the volume. Asserted below
# against the cell's own bounding box rather than taken on trust.
print(f"synapse bbox nm  min {syn_nm.min(0).round(0)}  max {syn_nm.max(0).round(0)}")

fields = {}

# ---- the fibre: distance from its far end ----------------------------------------
fv, fe, fz = load(FIBRE)

# guard the units before anything downstream depends on them
lo, hi = fv.min(0) - 5000, fv.max(0) + 5000
inside = np.all((syn_nm >= lo) & (syn_nm <= hi), axis=1)
assert inside.all(), (f"{(~inside).sum()} of {len(syn_nm)} synapses fall outside the "
                      f"fibre bbox; the coordinates are not in the space assumed")
print(f"units check: all {len(syn_nm)} synapses lie inside the fibre bounding box")
f_field = fz["dist_from_root_um"].astype(np.float64)
finite = np.isfinite(f_field)
f_field[~finite] = np.nanmax(f_field[finite])       # stranded fragments light last
fields[f"fibre_{FIBRE}_verts"] = fv
fields[f"fibre_{FIBRE}_dist"] = f_field
# Store the true span explicitly. Deriving it from the array maximum is a trap,
# because dark nodes are parked far past the end; taking max() over them
# normalises the parked value to exactly 1.0 and lights every dark node at the
# close of the sweep. That was the stray flash at the end of the shot.
fields[f"fibre_{FIBRE}_span"] = np.array(float(f_field.max()))
print(f"\nfibre: {len(fv)} nodes, pulse travels 0 to {f_field.max():.1f} um")

# where along that run do the boutons sit?
ftree = cKDTree(fv)
d_syn, i_syn = ftree.query(syn_nm)
arc_at_syn = f_field[i_syn]
print(f"  synapses sit {d_syn.mean()/1000:.2f} um from the fibre cable on average")
print(f"  their arc positions span {arc_at_syn.min():.1f} to {arc_at_syn.max():.1f} um"
      f" (median {np.median(arc_at_syn):.1f})")

# ---- the cell: in at the spine, down to the soma, out along the axon ----------------
# NOT a spread in all directions. Amy's correction, and she is right: the signal
# runs from the spine toward the soma and then out that cell's own axon. It does
# not travel back up the other dendrites. So only two sets of nodes ever light,
# the path in and the axon, and everything else stays dark.
hv, he, hz = load(HERO)
htree = cKDTree(hv)
d_h, i_h = htree.query(syn_nm)
seeds = np.unique(i_h)
soma = int(hz["root"])
parent = hz["parent"]
from_soma = hz["dist_from_root_um"]        # the skeleton is rooted at the soma
print(f"\ncell: {len(hv)} nodes; input synapses land on {len(seeds)} distinct nodes, "
      f"{d_h.mean()/1000:.2f} um from cable on average")


def path_to_soma(i):
    """Walk parents up to the root. Returns [] if the node is on a fragment."""
    out, seen = [], set()
    while i != -1 and i not in seen:
        seen.add(i)
        out.append(i)
        if i == soma:
            return out
        i = int(parent[i])
    return []


# the way in: union of the paths from each contact down to the soma
inbound = set()
for s in seeds:
    inbound.update(path_to_soma(int(s)))
print(f"  path in to the soma: {len(inbound)} nodes")

# The way out: the descending arbor, which Amy marked by hand on a render as the
# axon, with the ascending branches crossed out. That markup is the authority
# here. Two earlier attempts failed and it is worth recording why: paths from the
# cell's own outgoing synapses smeared over the entire cell, and soma child
# subtrees do not separate anything because the soma node is degree 1 in this
# skeleton, a tip rather than a hub, so nothing is rooted through it.
adj = defaultdict(list)
for a, b in he:
    adj[int(a)].append(int(b))
    adj[int(b)].append(int(a))

soma_y = hv[soma][1]                     # render vertical is OBJ y, up is +y
below = set(np.where(hv[:, 1] < soma_y)[0].tolist())
seen_b, comps = set(), []
for s in sorted(below):
    if s in seen_b:
        continue
    comp, q = {s}, deque([s])
    seen_b.add(s)
    while q:
        n = q.popleft()
        for k in adj[n]:
            if k in below and k not in seen_b:
                seen_b.add(k)
                comp.add(k)
                q.append(k)
    comps.append(comp)
# keep only what actually attaches near the soma, so strays elsewhere stay dark
axon = set()
for c in comps:
    if np.linalg.norm(hv[list(c)] - hv[soma], axis=1).min() / 1000.0 < 25.0:
        axon |= c
axon -= inbound
print(f"  descending arbor: {len(axon)} nodes across "
      f"{sum(1 for c in comps if c & axon)} connected pieces")

# Honest cross check, reported whether or not it agrees. Output synapses ought to
# sit on the axon, so this should come out lopsided toward the descending set.
out_nm = np.load(r"D:\Meshes\renders\hero_outgoing.npy")
d_o, i_o = htree.query(out_nm)
near = d_o < 3000.0
on_ax = sum(1 for k, gd in zip(i_o, near) if gd and int(k) in axon)
print(f"  cross check: of {near.sum()} outgoing synapses on cable, {on_ax} "
      f"({100*on_ax/max(near.sum(),1):.0f}%) sit on the descending arbor")
if on_ax < 0.5 * near.sum():
    print("  NOTE: most output synapses fall OUTSIDE the marked axon. Either this "
          "cell's collaterals ascend, or the presynaptic assignments are noisy. "
          "Following the markup regardless, since that is what was asked for.")

# All 53 synapses are on ONE thorn, inside a box under 7 um across, but the
# skeleton wanders 36 um of cable through that cauliflower of a spine. That
# wandering is not distance to the soma and must not be timed as though it were.
# So the clock is anchored where the thorn meets the dendrite, and the thorn
# itself is clamped to zero, meaning it lights as one thing, which is what a
# structure that small does.
idx_in_all = np.fromiter(inbound, dtype=int)
soma_dist = float(from_soma[list(seeds)].min())
inner = float(from_soma[idx_in_all].max()) - soma_dist
print(f"  the thorn holds {inner:.1f} um of cable inside a box under 7 um across, "
      f"clamped so it lights as one")

h_field = np.full(len(hv), np.inf)
# inbound counts down toward the soma, so distance travelled is what is left behind
idx_in = idx_in_all
h_field[idx_in] = np.maximum(0.0, soma_dist - from_soma[idx_in])
# Outbound continues past the soma. Distance comes from a Dijkstra out of the
# soma rather than the skeleton's own dist_from_root, because that field is
# rooted through a degree-1 soma and is not trustworthy out here.
idx_ax = np.fromiter(sorted(axon), dtype=int) if axon else np.empty(0, dtype=int)
if len(idx_ax):
    gh = graph(hv, he)
    d_from_soma = dijkstra(gh, directed=False, indices=soma)
    reach = np.isfinite(d_from_soma[idx_ax])
    h_field[idx_ax[reach]] = soma_dist + d_from_soma[idx_ax[reach]]
    if (~reach).any():
        # Pieces of the arbor the cable never reaches. An earlier version timed
        # these by straight line distance, which bunched them all into the last
        # moment and produced a 24,000 pixel flare at the end of the shot. There
        # is no honest arrival time for cable that is not connected, so they stay
        # dark. Better a gap than a made up number that reads as a signal.
        print(f"  {(~reach).sum()} axon nodes sit on detached pieces and stay dark, "
              f"no cable path to the soma exists for them")
h_field[soma] = soma_dist

# The soma is a degree-1 TIP in this skeleton rather than a hub, so cable paths
# route around it instead of through it. Measured along that cable, nodes sitting
# physically inside the soma carry values from 81 to 265 um, a spread of 184 um
# across a structure 13.7 um wide, and the wavefront visibly loops round the soma
# before carrying on. It is an artefact of the skeleton, not biology.
#
# A soma that size depolarises essentially as one unit, so every node inside it is
# clamped to the same value. The wave then flows through rather than around.
SOMA_R = float(9.0)          # measured soma radius is 6.83 um
r_soma = np.linalg.norm(hv - hv[soma], axis=1) / 1000.0
inside = r_soma < SOMA_R
before = h_field[inside & np.isfinite(h_field)]
h_field[inside] = soma_dist
if len(before):
    print(f"  soma: {inside.sum()} nodes within {SOMA_R:.0f} um clamped to one value; "
          f"they spanned {before.min():.1f} to {before.max():.1f} um beforehand")

lit = np.isfinite(h_field)
span_cell = float(h_field[lit].max())
print(f"  soma sits {soma_dist:.1f} um of cable from the contacts")
print(f"  axon runs a further {span_cell - soma_dist:.1f} um")
print(f"  {lit.sum()} of {len(hv)} nodes ever light ({100*lit.mean():.1f}%), "
      f"the rest stay dark on purpose")
# dark nodes are pushed far past the end of the sweep so the band never reaches them
h_field[~lit] = span_cell * 10.0
assert h_field[idx_in].min() >= -1e-6, "inbound leg went negative"

fields[f"cell_{HERO}_verts"] = hv
fields[f"cell_{HERO}_dist"] = h_field
fields[f"cell_{HERO}_span"] = np.array(span_cell)
fields["syn_nm"] = syn_nm
fields["arc_at_syn"] = arc_at_syn
fields["soma_dist"] = np.array(soma_dist)
fields["cell_span"] = np.array(span_cell)
fields["soma_nm"] = hv[soma]
fields["fibre_id"] = np.array(FIBRE)
fields["cell_id"] = np.array(HERO)

np.savez_compressed(OUT, **fields)
print(f"\nwrote {OUT}")
