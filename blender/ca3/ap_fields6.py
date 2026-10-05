"""Distance fields for all six mossy fibres onto the hero cell.

The story the literature actually supports: one mossy fibre spike lands hard and
still usually fails to fire the cell. It takes a burst, or several fibres, before
the cell sends anything of its own. So this builds the same per-fibre fields as
the single-fibre version, plus the cell's own field, and the animation runs them
as two attempts: one fibre alone, then all six.
"""
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

SKEL = r"D:\Meshes\skeletons"
HERO = 648518346438632877
OUT = rf"{SKEL}\ap_fields6.npz"

syn = pd.read_csv(r"D:\Meshes\renders\mf_synapses.csv")
mine = syn[syn.post_pt_root_id == HERO]
fibres = sorted(mine.pre_pt_root_id.unique())
print(f"{len(fibres)} mossy fibres contact the hero, {len(mine)} synapses in total\n")

# the single-fibre cut already solved the cell side; reuse it verbatim
base = np.load(rf"{SKEL}\ap_fields.npz")
fields = {
    f"cell_{HERO}_verts": base[f"cell_{HERO}_verts"],
    f"cell_{HERO}_dist": base[f"cell_{HERO}_dist"],
    f"cell_{HERO}_span": base[f"cell_{HERO}_span"],
    "soma_dist": base["soma_dist"],
    "cell_span": base["cell_span"],
    "cell_id": np.array(HERO),
}

order, rows = [], []
for seg in fibres:
    z = np.load(rf"{SKEL}\{seg}.npz")
    fv = z["vertices"]
    fd = z["dist_from_root_um"].astype(np.float64)
    fin = np.isfinite(fd)
    fd[~fin] = fd[fin].max()

    pair = syn[(syn.pre_pt_root_id == seg) & (syn.post_pt_root_id == HERO)]
    pts = np.array([np.fromstring(s.strip("[]"), sep=" ")
                    for s in pair["ctr_pt_position"]], dtype=float)
    lo, hi = fv.min(0) - 5000, fv.max(0) + 5000
    assert np.all((pts >= lo) & (pts <= hi)), f"{seg}: synapses outside the fibre bbox"

    d_syn, i_syn = cKDTree(fv).query(pts)
    arc = fd[i_syn]
    fields[f"fibre_{seg}_verts"] = fv
    fields[f"fibre_{seg}_dist"] = fd
    fields[f"fibre_{seg}_span"] = np.array(float(fd.max()))
    fields[f"fibre_{seg}_syn"] = pts
    fields[f"fibre_{seg}_arc"] = arc
    order.append(seg)
    rows.append((seg, len(pts), float(fd.max()), float(np.median(arc)),
                 float(d_syn.mean() / 1000)))

# Order by how far along its own cable each fibre's contacts sit, expressed as a
# fraction. Fibres whose boutons are near the far end of the traced segment need
# the whole sweep; ones that contact early would otherwise arrive long before the
# rest. The animation uses this to make all six land together.
frac = np.array([r[3] / r[2] for r in rows])
fields["fibre_ids"] = np.array(order, dtype=np.int64)
fields["fibre_syn_frac"] = frac

print(f"{'fibre':>20}  {'syn':>4}  {'cable um':>9}  {'contact at':>11}  {'off cable um':>12}")
for (seg, n, span, med, off), fr in zip(rows, frac):
    print(f"{seg:>20}  {n:>4}  {span:>9.1f}  {med:>7.1f} ({fr:.2f})  {off:>12.2f}")

tot = sum(r[1] for r in rows)
print(f"\n{tot} synapses from {len(order)} fibres onto one cell")
np.savez_compressed(OUT, **fields)
print(f"wrote {OUT}")
