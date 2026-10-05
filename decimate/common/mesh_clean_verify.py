"""Does cleaning change what you can SEE? Silhouette test, no GPU needed.

The bounding-box guard inside mesh_clean.py only catches gross loss. This is the
stricter check: project the vertices onto each of the three axis planes, rasterise
to a grid, and compare occupancy before and after. If the cleanup only removed
enclosed and detached geometry, the silhouette from every direction is unchanged.
Any real surface loss shows up immediately as missing pixels.

This is the same discipline as looking at a test frame, but it can run while the
GPU is busy with something else.
"""
import glob
import os

import numpy as np
import pymeshlab

GRID = 420


def verts(path, cleaned):
    ms = pymeshlab.MeshSet()
    ms.load_new_mesh(path)
    if cleaned:
        ms.meshing_remove_connected_component_by_face_number(mincomponentsize=250)
        ms.compute_scalar_ambient_occlusion()
        ms.compute_selection_by_scalar_per_vertex(minq=-1e9, maxq=0.002)
        ms.meshing_remove_selected_vertices()
    return np.asarray(ms.current_mesh().vertex_matrix(), dtype=float)


def silhouette(v, lo, hi, ax):
    keep = [i for i in range(3) if i != ax]
    a = v[:, keep]
    l, h = lo[keep], hi[keep]
    idx = np.floor((a - l) / np.maximum(h - l, 1e-9) * (GRID - 1)).astype(int)
    idx = np.clip(idx, 0, GRID - 1)
    g = np.zeros((GRID, GRID), dtype=bool)
    g[idx[:, 0], idx[:, 1]] = True
    return g


files = sorted(glob.glob(r"D:\Meshes\retina\meshes\*.obj"), key=os.path.getsize)
sample = files[::max(1, len(files) // 6)][:6]

print(f"  {'cell':<21} {'verts kept':>11}  silhouette kept, per view")
worst = 1.0
for p in sample:
    v0 = verts(p, False)
    v1 = verts(p, True)
    lo, hi = v0.min(axis=0), v0.max(axis=0)
    keeps = []
    for ax in range(3):
        s0 = silhouette(v0, lo, hi, ax)
        s1 = silhouette(v1, lo, hi, ax)
        keeps.append(float((s0 & s1).sum()) / max(1, s0.sum()))
    worst = min(worst, min(keeps))
    print(f"  {os.path.basename(p)[:20]:<21} {100*len(v1)/len(v0):9.1f}%   "
          + "  ".join(f"{k*100:5.1f}%" for k in keeps), flush=True)

print(f"\n  worst silhouette retention across all views: {worst*100:.1f}%")
print("  VERDICT:", "visible shape preserved" if worst > 0.97
      else "REAL SURFACE LOST, do not apply")
