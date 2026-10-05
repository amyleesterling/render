"""Find an ambient-occlusion threshold that removes interior without eating surface.

The first guess, AO <= 0.002, looked like "fully enclosed" but cost up to 25% of
the visible silhouette. Thin dendrites packed inside a dense arbor are heavily
occluded by their neighbours, so a low AO value does not by itself mean hidden.

Sweeps thresholds and reports both numbers that matter: how much geometry goes,
and how much of the silhouette survives. The right threshold is the largest one
that keeps silhouette retention above 99%.
"""
import glob
import os

import numpy as np
import pymeshlab

GRID = 420
THRESH = [0.0, 1e-6, 1e-5, 1e-4, 5e-4, 2e-3]


def load(path):
    ms = pymeshlab.MeshSet()
    ms.load_new_mesh(path)
    ms.meshing_remove_connected_component_by_face_number(mincomponentsize=250)
    ms.compute_scalar_ambient_occlusion()
    return ms


def sil(v, lo, hi, ax):
    keep = [i for i in range(3) if i != ax]
    a = v[:, keep]
    l, h = lo[keep], hi[keep]
    idx = np.clip(np.floor((a - l) / np.maximum(h - l, 1e-9) * (GRID - 1)).astype(int),
                  0, GRID - 1)
    g = np.zeros((GRID, GRID), dtype=bool)
    g[idx[:, 0], idx[:, 1]] = True
    return g


files = sorted(glob.glob(r"D:\Meshes\retina\meshes\*.obj"), key=os.path.getsize)
sample = files[::max(1, len(files) // 4)][:4]

print(f"  {'threshold':>10}  {'faces kept':>11}  {'silhouette kept':>16}")
agg = {t: [[], []] for t in THRESH}
for p in sample:
    base = load(p)
    v0 = np.asarray(base.current_mesh().vertex_matrix(), dtype=float)
    f0 = base.current_mesh().face_number()
    lo, hi = v0.min(axis=0), v0.max(axis=0)
    s0 = [sil(v0, lo, hi, a) for a in range(3)]
    q = np.asarray(base.current_mesh().vertex_scalar_array(), dtype=float)

    for t in THRESH:
        ms = load(p)
        if t > 0 or (q <= 0).any():
            ms.compute_selection_by_scalar_per_vertex(minq=-1e9, maxq=t)
            try:
                ms.meshing_remove_selected_vertices()
            except Exception:
                pass
        v1 = np.asarray(ms.current_mesh().vertex_matrix(), dtype=float)
        f1 = ms.current_mesh().face_number()
        if len(v1) == 0:
            agg[t][0].append(0.0); agg[t][1].append(0.0); continue
        keeps = [float((s0[a] & sil(v1, lo, hi, a)).sum()) / max(1, s0[a].sum())
                 for a in range(3)]
        agg[t][0].append(f1 / max(1, f0))
        agg[t][1].append(min(keeps))

for t in THRESH:
    fk = 100 * np.mean(agg[t][0])
    sk = 100 * np.min(agg[t][1])
    flag = "  <- safe" if sk >= 99.0 else ""
    print(f"  {t:>10.6g}  {fk:10.1f}%  {sk:15.1f}%{flag}")

print("\n  faces kept is after debris removal; silhouette is the worst view of any cell.")
print("  Pick the largest threshold that keeps silhouette at 99% or better.")
