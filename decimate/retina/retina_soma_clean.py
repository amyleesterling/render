"""Find and remove the hidden geometry inside these cells.

The probe found 279 to 1018 CONNECTED COMPONENTS in a single cell. A neuron is one
object, so all but a handful of those are debris: detached shells, specks, and the
nested inner surfaces that marching cubes leaves inside a soma. They are invisible
from outside, they inflate the file, and they are a large part of why decimation
breaks branches, because the decimator spends its face budget on geometry nobody
can see.

Two measurements per cell, before touching anything:
  - how many faces live in components below a size threshold
  - how many faces are enclosed, tested by ambient occlusion

Then a dry run of the removal, reporting what would go.

  python retina_soma_clean.py [--apply] [--n 6]
"""
import argparse
import glob
import os

import numpy as np
import pymeshlab

AP = argparse.ArgumentParser()
AP.add_argument("--apply", action="store_true", help="write cleaned meshes")
AP.add_argument("--n", type=int, default=6, help="how many cells to measure")
AP.add_argument("--minfaces", type=int, default=250,
                help="components smaller than this are debris")
A = AP.parse_args()

files = sorted(glob.glob(r"D:\Meshes\retina\meshes\*.obj"), key=os.path.getsize)
step = max(1, len(files) // A.n)
sample = files[::step][:A.n]

tot_before = tot_after = 0
for p in sample:
    mb = os.path.getsize(p) / 1e6
    ms = pymeshlab.MeshSet()
    ms.load_new_mesh(p)
    nf0 = ms.current_mesh().face_number()

    # 1. how enclosed is this mesh? AO of 0 means invisible from every direction
    ao_frac = None
    try:
        ms.compute_scalar_ambient_occlusion()
        q = np.asarray(ms.current_mesh().vertex_scalar_array(), dtype=float)
        ao_frac = float((q <= 0.002).sum()) / max(1, len(q))
    except Exception as e:
        ao_note = f"{type(e).__name__}"

    # 2. strip components smaller than the threshold
    ms2 = pymeshlab.MeshSet()
    ms2.load_new_mesh(p)
    try:
        ms2.meshing_remove_connected_component_by_face_number(mincomponentsize=A.minfaces)
    except Exception as e:
        print(f"  {os.path.basename(p)}: component removal failed {type(e).__name__}")
        continue
    nf1 = ms2.current_mesh().face_number()
    tot_before += nf0
    tot_after += nf1

    aos = f"{ao_frac*100:5.1f}%" if ao_frac is not None else "  n/a"
    print(f"  {os.path.basename(p)[:20]:<20} {mb:6.1f} MB  "
          f"{nf0:>8,} -> {nf1:>8,} faces  ({100*(nf0-nf1)/nf0:4.1f}% debris)   "
          f"fully enclosed verts {aos}", flush=True)

    if A.apply:
        keep = os.path.join(r"D:\Meshes\retina\meshes_raw", os.path.basename(p))
        os.makedirs(os.path.dirname(keep), exist_ok=True)
        if not os.path.exists(keep):
            import shutil
            shutil.copy2(p, keep)
        ms2.save_current_mesh(p, save_vertex_normal=False, save_face_color=False)

if tot_before:
    print(f"\n  across the sample: {tot_before:,} -> {tot_after:,} faces, "
          f"{100*(tot_before-tot_after)/tot_before:.1f}% removed as debris")
    print("  (dry run; pass --apply to write)" if not A.apply else "  (written; originals in meshes_raw)")
