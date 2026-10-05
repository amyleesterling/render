"""The cleaning pipeline, and the variants that let a render judge it.

THE PIPELINE, in one line: delete what no ray can reach, then decimate.

How it got here, because every earlier idea was wrong in a way worth recording:

  1. "A neuron is one object, so small components are litter." False on this data.
     On full resolution meshes every one of the 4,627 small pieces sits within
     4 um of the main body, median 127 nm, which at this voxel size is touching.
     There is no litter to separate, so no component-size threshold can work.
  2. "Then decimate first and clean after." Backwards. The budget gets spent on
     surfaces nobody can see, and it is the thin processes that get collapsed to
     pay for them. That is how branches break.
  3. "Use ambient occlusion at 0.002." That was not a small threshold, it was
     zero: AO on this build spans 0 to about 16, so every value swept from 0 to
     0.002 meant the same thing and they agreed for the wrong reason.

What survived: 99.6% of small-piece vertices receive no ray from any direction,
against 25.6% of main-component vertices. The dust and the polygons sealed inside
somas are the same phenomenon, marching cubes inner shells, and visibility catches
both without knowing anything about either.

Visibility is also the RIGHT criterion here specifically because the output is a
render. Geometry no ray can reach cannot change a frame, so removing it is free by
construction. That argument does not hold for analysis meshes, where surface area
and volume are the point, so this pipeline is for rendering only.

  python mesh_pipeline_test.py --cell ID [--target 350000]
"""
import argparse
import os
import time

import numpy as np
import pymeshlab

AP = argparse.ArgumentParser()
AP.add_argument("--cell", default="720575940550200928")
AP.add_argument("--dir", default=r"D:\Meshes\retina\meshes_full")
AP.add_argument("--out", default=r"D:\Meshes\retina\clean_test")
AP.add_argument("--target", type=int, default=350_000,
                help="face budget both variants are decimated to")
A = AP.parse_args()

os.makedirs(A.out, exist_ok=True)
src = os.path.join(A.dir, f"{A.cell}.obj")


def ext(ms):
    bb = ms.current_mesh().bounding_box()
    return np.array([bb.dim_x(), bb.dim_y(), bb.dim_z()], dtype=float)


def report(ms, label):
    m = ms.current_mesh()
    e = ext(ms)
    print(f"  {label:<34} {m.face_number():>10,} faces   "
          f"extent {e[0]:>8.0f} {e[1]:>8.0f} {e[2]:>8.0f}", flush=True)
    return m.face_number(), e


def decimate(ms, target):
    # preservetopology MUST be False. These meshes carry thousands of components
    # and boundary loops, and the topology-preserving path refuses most collapses
    # on them, so the target is never reached and the "decimated" mesh is still
    # huge. preservenormal keeps the shading from flipping on thin processes.
    if target < ms.current_mesh().face_number():
        ms.meshing_decimation_quadric_edge_collapse(
            targetfacenum=target, preservenormal=True,
            preservetopology=False, planarquadric=True)
    return ms


print(f"[p] {A.cell}, {os.path.getsize(src)/1e6:.0f} MB", flush=True)

# --- variant RAW: decimate straight to the budget, no cleaning -----------------
# This is what the current library does, and the control the other variant has to
# beat. Without it there is no way to tell an improvement from a change.
t0 = time.time()
ms = pymeshlab.MeshSet()
ms.load_new_mesh(src)
f0, e0 = report(ms, "0 original")
decimate(ms, A.target)
f_raw, e_raw = report(ms, f"RAW decimated to {A.target:,}")
ms.save_current_mesh(os.path.join(A.out, f"{A.cell}_RAW.obj"), save_vertex_normal=False)
print(f"  ({time.time()-t0:.0f}s)", flush=True)

# --- variant CLEAN: strip invisible geometry, then decimate to the SAME budget --
t0 = time.time()
ms = pymeshlab.MeshSet()
ms.load_new_mesh(src)
ms.compute_scalar_ambient_occlusion()
q = np.asarray(ms.current_mesh().vertex_scalar_array(), dtype=float)
print(f"  AO 0 to {q.max():.1f}; {100*(q<=1e-9).mean():.1f}% of vertices see nothing",
      flush=True)
ms.compute_selection_by_scalar_per_vertex(minq=-1e9, maxq=1e-9)
ms.meshing_remove_selected_vertices()
f_c, e_c = report(ms, "CLEAN invisible removed")
loss = float(np.max((e0 - e_c) / np.maximum(e0, 1e-9)))
print(f"  extent lost to cleaning: {100*loss:.3f}%   "
      f"(a real branch going missing shows up here first)", flush=True)
decimate(ms, A.target)
f_cd, e_cd = report(ms, f"CLEAN decimated to {A.target:,}")
ms.save_current_mesh(os.path.join(A.out, f"{A.cell}_CLEAN.obj"), save_vertex_normal=False)
print(f"  ({time.time()-t0:.0f}s)", flush=True)

print(f"\n[p] at an identical budget of {A.target:,} faces:")
print(f"    cleaning first removed {100*(f0-f_c)/f0:.1f}% of the mesh as invisible")
for i, ax in enumerate("xyz"):
    print(f"    extent {ax}: original {e0[i]:>9.0f}   raw {e_raw[i]:>9.0f}   "
          f"clean {e_cd[i]:>9.0f}   clean keeps {100*(e_cd[i]-e_raw[i])/e0[i]:+.2f}% more")
print("\n[p] extent is a hint, not the verdict. Render both and look.")
