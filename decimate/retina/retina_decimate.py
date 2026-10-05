"""Bring the freshly downloaded retina meshes down to the weight of the ones that
were already downsampled.

The 184 cells pulled from CAVE came at full resolution: 17.3 GB against 1.0 GB
for the 181 that were already in the meshparty library. In a mosaic view each
cell occupies a few hundred pixels, so full resolution buys nothing and costs an
import that had not finished after 11 minutes.

preservetopology is False, deliberately. The CA3 playbook records that True
blocks decimation entirely on meshes with thousands of connected components: one
cell kept 95% of its faces instead of 40%.

Originals are moved to meshes_full/ rather than deleted, so this is reversible.
"""
import glob
import os
import shutil
import sys
import time

import pymeshlab

SRC = r"D:\Meshes\retina\meshes"
KEEP = r"D:\Meshes\retina\meshes_full"
THRESH_MB = 20.0          # anything bigger is a fresh full-res download
TARGET_MB = 6.0           # roughly the median of the already-downsampled set
os.makedirs(KEEP, exist_ok=True)

files = [f for f in glob.glob(os.path.join(SRC, "*.obj"))
         if os.path.getsize(f) / 1e6 > THRESH_MB]
files.sort(key=os.path.getsize, reverse=True)
print(f"[dec] {len(files)} meshes over {THRESH_MB:.0f} MB to decimate", flush=True)

t0 = time.time()
before = after = 0.0
for i, f in enumerate(files, 1):
    mb = os.path.getsize(f) / 1e6
    before += mb
    try:
        ms = pymeshlab.MeshSet()
        ms.load_new_mesh(f)
        n = ms.current_mesh().face_number()
        target = max(20000, int(n * min(1.0, TARGET_MB / mb)))
        ms.meshing_decimation_quadric_edge_collapse(
            targetfacenum=target,
            preservenormal=True,
            preservetopology=False,      # True blocks decimation on fragmented meshes
            planarquadric=True,
        )
        shutil.move(f, os.path.join(KEEP, os.path.basename(f)))
        ms.save_current_mesh(f, save_vertex_normal=False, save_face_color=False)
        after += os.path.getsize(f) / 1e6
        if i % 10 == 0 or i == len(files):
            el = time.time() - t0
            print(f"[dec] {i}/{len(files)}  {before/1000:.1f} -> {after/1000:.2f} GB  "
                  f"{el/60:.1f} min  eta {(el/i)*(len(files)-i)/60:.0f} min", flush=True)
    except Exception as e:
        print(f"[dec] FAIL {os.path.basename(f)}: {type(e).__name__} {str(e)[:90]}",
              flush=True)
        keep = os.path.join(KEEP, os.path.basename(f))
        if os.path.exists(keep) and not os.path.exists(f):
            shutil.move(keep, f)          # put it back rather than lose the cell

total = sum(os.path.getsize(x) for x in glob.glob(os.path.join(SRC, "*.obj"))) / 1e9
print(f"[dec] DONE in {(time.time()-t0)/60:.1f} min. "
      f"meshes dir now {total:.2f} GB", flush=True)
