"""Produce cleaning variants of one cell so a RENDER can decide between them.

Every measurement I have tried on this problem has been misleading in a way that
only a picture catches:

  - face counts say how much went, never whether it was visible
  - silhouette occupancy projected interior vertices too, so hidden geometry
    counted toward the "before" outline and its removal scored as damage
  - the first ambient occlusion sweep ran thresholds from 0 to 0.002 on a scale
    that actually spans 0 to 16, so every threshold meant "exactly zero" and all
    of them agreed with each other for the wrong reason

So this writes variants and stops. Nothing here decides anything. The decision is
made by looking at the renders, which is the one instrument that has not lied yet.

  python mesh_clean_variants.py --cell 720575940550200928 [--src staged|full]
"""
import argparse
import os
import time

import numpy as np
import pymeshlab

AP = argparse.ArgumentParser()
AP.add_argument("--cell", default="720575940550200928")
AP.add_argument("--src", default="staged", choices=["staged", "full"])
AP.add_argument("--out", default=r"D:\Meshes\retina\clean_test")
AP.add_argument("--minfaces", type=int, default=250)
A = AP.parse_args()

SRC = (r"D:\Meshes\retina\meshes" if A.src == "staged"
       else r"D:\Meshes\retina\meshes_full")
path = os.path.join(SRC, f"{A.cell}.obj")
os.makedirs(A.out, exist_ok=True)


def stats(ms, label):
    m = ms.current_mesh()
    bb = m.bounding_box()
    ext = np.array([bb.dim_x(), bb.dim_y(), bb.dim_z()])
    print(f"  {label:<26} {m.face_number():>10,} faces  {m.vertex_number():>9,} verts  "
          f"extent {ext[0]:.0f} x {ext[1]:.0f} x {ext[2]:.0f}", flush=True)
    return m.face_number(), ext


print(f"[v] {A.src} mesh for {A.cell}: {os.path.getsize(path)/1e6:.1f} MB", flush=True)
t0 = time.time()

# --- A: untouched -------------------------------------------------------------
ms = pymeshlab.MeshSet()
ms.load_new_mesh(path)
f_a, ext_a = stats(ms, "A original")
ms.save_current_mesh(os.path.join(A.out, f"{A.cell}_A_original.obj"),
                     save_vertex_normal=False)

# --- B: detached debris removed -----------------------------------------------
# A neuron is ONE object. Anything not joined to the main body is a fragment the
# segmentation left behind. This step is uncontroversial and was already measured
# as safe; it is here so the render can confirm that rather than assume it.
ms = pymeshlab.MeshSet()
ms.load_new_mesh(path)
ms.meshing_remove_connected_component_by_face_number(mincomponentsize=A.minfaces)
f_b, ext_b = stats(ms, "B debris removed")
ms.save_current_mesh(os.path.join(A.out, f"{A.cell}_B_debris.obj"),
                     save_vertex_normal=False)

# --- C: plus geometry that sees no light at all -------------------------------
# Ambient occlusion on THIS build spans 0 to about 16, not 0 to 1. Exactly zero
# means the vertex received no ray from any direction, which is what being sealed
# inside a soma looks like. It is also what being buried deep in a dense arbor can
# look like, and that is the risk the render has to rule out.
ms = pymeshlab.MeshSet()
ms.load_new_mesh(path)
ms.meshing_remove_connected_component_by_face_number(mincomponentsize=A.minfaces)
ms.compute_scalar_ambient_occlusion()
q = np.asarray(ms.current_mesh().vertex_scalar_array(), dtype=float)
print(f"  AO on this cell: max {q.max():.2f}, exactly zero on {100*(q<=1e-9).mean():.1f}% of verts",
      flush=True)
ms.compute_selection_by_scalar_per_vertex(minq=-1e9, maxq=1e-9)
ms.meshing_remove_selected_vertices()
f_c, ext_c = stats(ms, "C debris + interior")
ms.save_current_mesh(os.path.join(A.out, f"{A.cell}_C_interior.obj"),
                     save_vertex_normal=False)

# --- D: decimate C back to the same face count B would need -------------------
# The real question is not "is C smaller" but "does the SAME face budget buy more
# surviving dendrite when it is not being spent on invisible geometry". So C is
# decimated to whatever B decimates to, and the two are compared at equal cost.
TARGET = int(f_b * 0.18)          # about the 5.8 MB staged average from a full cell
for tag, srcfile, base in (("B", f"{A.cell}_B_debris.obj", f_b),
                           ("C", f"{A.cell}_C_interior.obj", f_c)):
    ms = pymeshlab.MeshSet()
    ms.load_new_mesh(os.path.join(A.out, srcfile))
    if TARGET < base:
        # preservetopology MUST be False. These meshes are fragmented and the
        # topology-preserving path silently refuses most collapses on them, so the
        # target is never reached and the result is a mesh that is still huge.
        ms.meshing_decimation_quadric_edge_collapse(
            targetfacenum=TARGET, preservenormal=True,
            preservetopology=False, planarquadric=True)
    stats(ms, f"{tag}+decimate to {TARGET:,}")
    ms.save_current_mesh(os.path.join(A.out, f"{A.cell}_{tag}D_decimated.obj"),
                         save_vertex_normal=False)

print(f"\n[v] debris was {100*(f_a-f_b)/f_a:.1f}% of faces, "
      f"interior a further {100*(f_b-f_c)/f_a:.1f}%", flush=True)
print(f"[v] extent change after interior removal: "
      f"{100*np.max((ext_b-ext_c)/np.maximum(ext_b,1e-9)):.3f}% "
      f"(a real dendrite going missing would show here)", flush=True)
print(f"[v] variants in {A.out}, {time.time()-t0:.0f}s", flush=True)
