"""Sweep ambient occlusion on its ACTUAL scale, and verify by rendering.

Two corrections to the first attempt:
  1. pymeshlab's AO here spans 0..16, not 0..1. Every threshold I swept (0 to
     0.002) therefore meant "exactly zero" and all gave the same answer.
  2. My silhouette check projected every vertex including interior ones, so hidden
     geometry counted toward the "before" outline and its removal looked like
     damage. Point-cloud occupancy is not visibility.

This sweeps real thresholds and reports faces removed. Visual verification is a
separate render step, because only a render answers "does it look the same".
"""
import glob
import os

import numpy as np
import pymeshlab

files = sorted(glob.glob(r"D:\Meshes\retina\meshes\*.obj"), key=os.path.getsize)
sample = files[::max(1, len(files) // 5)][:5]

print("=== AO distribution, after debris removal ===")
dists = []
for p in sample:
    ms = pymeshlab.MeshSet()
    ms.load_new_mesh(p)
    ms.meshing_remove_connected_component_by_face_number(mincomponentsize=250)
    ms.compute_scalar_ambient_occlusion()
    q = np.asarray(ms.current_mesh().vertex_scalar_array(), dtype=float)
    dists.append(q)
    pc = np.percentile(q, [1, 5, 10, 25, 50, 75])
    print(f"  {os.path.basename(p)[:20]:<21} max {q.max():6.2f}  "
          f"p1 {pc[0]:5.2f} p5 {pc[1]:5.2f} p10 {pc[2]:5.2f} "
          f"p25 {pc[3]:5.2f} p50 {pc[4]:5.2f}  zero {100*(q<=1e-9).mean():4.1f}%")

print("\n=== how much geometry each threshold removes ===")
print(f"  {'threshold':>10}  {'faces kept':>11}   meaning")
for t in (0.0, 1e-9, 0.05, 0.2, 0.5, 1.0):
    kept = []
    for p in sample:
        ms = pymeshlab.MeshSet()
        ms.load_new_mesh(p)
        ms.meshing_remove_connected_component_by_face_number(mincomponentsize=250)
        f0 = ms.current_mesh().face_number()
        ms.compute_scalar_ambient_occlusion()
        ms.compute_selection_by_scalar_per_vertex(minq=-1e9, maxq=t)
        try:
            ms.meshing_remove_selected_vertices()
        except Exception:
            pass
        kept.append(ms.current_mesh().face_number() / max(1, f0))
    note = "sees no light at all" if t <= 1e-9 else f"sees less than {t/16*100:.1f}% of the sky"
    print(f"  {t:>10.4g}  {100*np.mean(kept):10.1f}%   {note}")
