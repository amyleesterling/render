"""Decimate the 81 walking+steering meshes to a density the poster can actually use.

Native is about 3.1M faces per cell, so 81 cells is roughly 250M faces. This
machine is measured good to 124M and gets steep past ~80M (see D:\\Meshes\\README.md),
so the full cast will not render as-is.

The poster is 1600x1200 with a visible height of 1208.9 um, i.e. **1.007 um per
pixel**. Detail finer than a micrometre cannot survive to the viewer, so a target
of ~10 faces/um2 is already several faces per pixel.

Follows the playbook: preservetopology=False (topology preservation blocks almost
every collapse on meshes with thousands of components), density per unit AREA
rather than one global face count, clean before decimating, and print before/after
totals for the whole folder so a silently-winning keep-floor cannot hide.

  python banc_walkingsteering_decimate.py plan    # areas + targets, decimates nothing
  python banc_walkingsteering_decimate.py         # do it, resumable
"""
import json
import os
import sys
import time

import numpy as np
import pymeshlab

SRC = r"D:\Meshes\banc\walking_steering"
OUT = r"D:\Meshes\banc\walking_steering_dec"
IDS_JSON = r"D:\Meshes\banc\walking_steering_ids.json"

DENSITY = 10.0        # faces per um^2
MIN_FACES = 2000      # a floor low enough that it cannot quietly win on real cells
NM2_PER_UM2 = 1e6     # vertices are in nanometres

os.makedirs(OUT, exist_ok=True)
ids = [int(x) for x in json.load(open(IDS_JSON))["segments"]]
plan_only = len(sys.argv) > 1 and sys.argv[1] == "plan"

present = [i for i in ids if os.path.exists(os.path.join(SRC, f"{i}.obj"))]
print(f"[dec] {len(present)}/{len(ids)} source meshes on disk, density {DENSITY} faces/um2")
if len(present) < len(ids) and not plan_only:
    print(f"[dec] WARNING: {len(ids)-len(present)} still downloading; rerun to pick them up")

rows, before_total, after_total = [], 0, 0
t0 = time.time()

for n, i in enumerate(present, 1):
    src = os.path.join(SRC, f"{i}.obj")
    dst = os.path.join(OUT, f"{i}.obj")
    if os.path.exists(dst) and not plan_only:
        continue
    ms = pymeshlab.MeshSet()
    ms.load_new_mesh(src)
    m = ms.current_mesh()
    f0 = m.face_number()
    area_um2 = ms.get_geometric_measures()["surface_area"] / NM2_PER_UM2
    target = int(max(MIN_FACES, area_um2 * DENSITY))
    rows.append((i, f0, area_um2, target))
    before_total += f0
    if plan_only:
        after_total += min(target, f0)
        print(f"[plan] {n}/{len(present)} {i}  {f0/1e6:.2f}M faces  "
              f"{area_um2:,.0f} um2  -> {target/1e3:.0f}k  ({100*target/f0:.1f}%)", flush=True)
        continue

    # Clean first: stray components wreck both decimation and any auto-framing.
    ms.meshing_remove_connected_component_by_face_number(mincomponentsize=25)
    if target < m.face_number():
        ms.meshing_decimation_quadric_edge_collapse(
            targetfacenum=target, qualitythr=0.3,
            preserveboundary=True, preservenormal=False,
            preservetopology=False,      # <-- the important one
            optimalplacement=True, autoclean=True)
    f1 = ms.current_mesh().face_number()
    after_total += f1
    ms.save_current_mesh(dst, save_vertex_normal=False, save_vertex_color=False)
    print(f"[dec] {n}/{len(present)} {i}  {f0/1e6:.2f}M -> {f1/1e3:.0f}k faces "
          f"({100*f1/f0:.1f}%)  {area_um2:,.0f} um2  {(time.time()-t0)/60:.1f} min", flush=True)

print(f"\n[dec] {'PLAN' if plan_only else 'DONE'}: {len(rows)} meshes, "
      f"{before_total/1e6:.1f}M -> {after_total/1e6:.1f}M faces "
      f"({100*after_total/max(before_total,1):.1f}%)")
if rows:
    fr = np.array([r[3] / r[1] for r in rows])
    print(f"[dec] keep fraction: min {fr.min()*100:.1f}%  median {np.median(fr)*100:.1f}%  "
          f"max {fr.max()*100:.1f}%")
    print(f"[dec] if max keep fraction is ~40% on many cells, a floor is winning - check it")
print(f"[dec] budget: machine is proven to 124M faces and gets steep past ~80M")
