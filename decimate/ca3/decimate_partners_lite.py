"""Re-decimate the 56 partner cells down to the density the rest of the
populations already use.

download_partners.py set

    target = max(MIN_FACES, int(area * 5.0), int(faces * 0.40))

and for these cells the 0.40 keep-floor won every time, so the folder came out
at 21.0M faces, 375k per cell. The comparable population, hq/thorny pyramidals
ca3 250, runs 182 cells in 7.2M faces, i.e. 40k per cell at the same 5 faces
per um2 target. The partners are background context seen at whole-cell scale,
so 9x the polygon budget of the hero's own neighbours buys nothing and costs
about 2 minutes a frame.

This drops the keep-floor and targets the density alone. Source folder is left
untouched; output goes to partners_lite.

  D:\\Meshes\\.venv\\Scripts\\python.exe decimate_partners_lite.py
"""
import time
from pathlib import Path

import pymeshlab

SRC = Path(r"D:\Meshes\partners")
DST = Path(r"D:\Meshes\partners_lite")
DST.mkdir(parents=True, exist_ok=True)

TARGET_DENSITY = 5.0   # faces per um2, same as the hq cell-body populations
MIN_FACES = 2000       # floor so the tiny fragments stay renderable

files = [p for p in sorted(SRC.glob("*.obj"))
         if not p.name.endswith((".raw.obj", ".tmp.obj"))]
print(f"[lite] {len(files)} partner meshes", flush=True)

tot_before = tot_after = 0
t0all = time.time()
for i, p in enumerate(files, 1):
    dst = DST / p.name
    if dst.exists():
        print(f"[lite] [{i}/{len(files)}] {p.stem} already done", flush=True)
        continue
    t0 = time.time()
    ms = pymeshlab.MeshSet()
    ms.load_new_mesh(str(p))
    before = ms.current_mesh().face_number()
    # already component-cleaned and smoothed by download_partners.py; the only
    # thing that needs redoing is the face budget
    area = ms.get_geometric_measures()["surface_area"] / 1e6      # um2
    target = max(MIN_FACES, int(area * TARGET_DENSITY))
    if before > target:
        ms.meshing_decimation_quadric_edge_collapse(
            targetfacenum=target, qualitythr=0.3, preserveboundary=True,
            boundaryweight=1.0, preservenormal=False,
            # MUST stay False. On meshes with thousands of connected components
            # preservetopology blocks the collapse entirely and the mesh keeps
            # 95% of its faces.
            preservetopology=False,
            optimalplacement=True, planarquadric=False, planarweight=0.001,
            qualityweight=False, autoclean=True, selected=False)
    after = ms.current_mesh().face_number()
    tmp = DST / (p.stem + ".tmp.obj")
    ms.save_current_mesh(str(tmp))
    tmp.replace(dst)
    tot_before += before
    tot_after += after
    print(f"[lite] [{i}/{len(files)}] {p.stem}: {before:,} -> {after:,} "
          f"({area:,.0f} um2, {time.time()-t0:.0f}s)", flush=True)

mb = sum(q.stat().st_size for q in DST.glob("*.obj")) / 1024 ** 2
print(f"\n[lite] {tot_before:,} -> {tot_after:,} faces, {mb:,.0f} MB, "
      f"{(time.time()-t0all)/60:.1f} min", flush=True)
print("[lite] DONE", flush=True)
