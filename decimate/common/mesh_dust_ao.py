"""Are the dust pieces INSIDE the cell? Visibility, not topology, is the test.

The component probe ruled out the litter hypothesis: on full resolution meshes not
one of the 4,627 small pieces sits more than 4 um from the main body and the median
is 127 nm, which at this voxel size is touching. So they are not junk floating in
the volume, and no threshold on component SIZE can ever separate them, because
there is nothing to separate them from.

That leaves one explanation that fits both the dust and the polygons Amy sees
inside somas: they are the nested inner shells marching cubes leaves behind when it
meets a membrane, sitting just inside the surface. If that is right they share one
property that matters more than any other for a renderer, and it is testable:

  YOU CANNOT SEE THEM.

So this measures ambient occlusion per component and asks whether the small pieces
are systematically darker than the main body. If they are, visibility is the
discriminator, and it is the correct one for a render pipeline: geometry no ray can
reach cannot affect a frame, so removing it is free, whatever it turns out to be.

Ambient occlusion here spans 0 to about 16, NOT 0 to 1.

  python mesh_dust_ao.py [--cell ID]
"""
import argparse
import os
import time

import numpy as np
import pymeshlab

AP = argparse.ArgumentParser()
AP.add_argument("--cell", default="720575940550200928")
AP.add_argument("--dir", default=r"D:\Meshes\retina\meshes_full")
AP.add_argument("--minfaces", type=int, default=250)
A = AP.parse_args()

p = os.path.join(A.dir, f"{A.cell}.obj")
t0 = time.time()
ms = pymeshlab.MeshSet()
ms.load_new_mesh(p)
print(f"[ao] {ms.current_mesh().face_number():,} faces loaded in {time.time()-t0:.0f}s",
      flush=True)

# Per-vertex component id, so AO can be split by component without a second load.
t0 = time.time()
ms.compute_scalar_by_geodesic_distance_from_shape_diameter_function_per_vertex() \
    if False else None
ms.compute_color_by_conntected_component_per_face()
print(f"[ao] components coloured in {time.time()-t0:.0f}s", flush=True)

t0 = time.time()
ms.compute_scalar_ambient_occlusion()
q = np.asarray(ms.current_mesh().vertex_scalar_array(), dtype=float)
print(f"[ao] ambient occlusion in {time.time()-t0:.0f}s, "
      f"range {q.min():.3f} to {q.max():.3f}", flush=True)

# Split vertices into main-component and small-component sets using trimesh, which
# gives component membership directly. Vertex order is preserved by both loaders
# because process=False disables trimesh's own merging.
import trimesh
t0 = time.time()
m = trimesh.load(p, process=False)
lab = trimesh.graph.connected_component_labels(m.face_adjacency, node_count=len(m.faces))
sizes = np.bincount(lab)
main_lab = int(np.argmax(sizes))
face_small = sizes[lab] < A.minfaces
vert_small = np.zeros(len(m.vertices), dtype=bool)
vert_small[np.unique(m.faces[face_small])] = True
vert_main = np.zeros(len(m.vertices), dtype=bool)
vert_main[np.unique(m.faces[lab == main_lab])] = True
vert_main &= ~vert_small
print(f"[ao] component labels in {time.time()-t0:.0f}s: "
      f"{int(vert_main.sum()):,} main verts, {int(vert_small.sum()):,} small-piece verts",
      flush=True)

if len(q) != len(m.vertices):
    print(f"[ao] WARNING vertex counts differ ({len(q)} vs {len(m.vertices)}), "
          f"cannot align. Stopping rather than reporting a wrong answer.", flush=True)
    raise SystemExit(1)


def describe(name, mask):
    if not mask.any():
        print(f"  {name:<22} (none)")
        return
    v = q[mask]
    print(f"  {name:<22} n={mask.sum():>9,}  zero {100*(v<=1e-9).mean():>5.1f}%  "
          f"median {np.median(v):>6.2f}  p90 {np.percentile(v,90):>6.2f}")


print("\n[ao] ambient occlusion by where the vertex lives:")
describe("main component", vert_main)
describe(f"pieces < {A.minfaces} faces", vert_small)

zs = float((q[vert_small] <= 1e-9).mean()) if vert_small.any() else 0.0
zm = float((q[vert_main] <= 1e-9).mean()) if vert_main.any() else 0.0
print(f"\n[ao] VERDICT")
print(f"     {100*zs:.1f}% of small-piece vertices are invisible from every direction")
print(f"     {100*zm:.1f}% of main-component vertices are")
if zs > 0.6 and zs > 2 * zm:
    print("     -> the dust is buried geometry. Visibility removes it, and removes the")
    print("        soma interiors in the same pass, without a component threshold.")
elif zs < 0.3:
    print("     -> the dust is VISIBLE. It is real surface and must not be deleted.")
else:
    print("     -> mixed. Visibility alone will not cleanly separate it; do not adopt yet.")
