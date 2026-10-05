"""How far can a cell be decimated before its dendrites break? Measure, do not guess.

The control render settled what cleaning does and does not do. At 350k faces both
the cleaned and uncleaned variants show the same broken, beaded dendrites, while
the undecimated 5.7M face original shows continuous ones. So:

  - decimation to 350k is what breaks branches
  - removing invisible geometry first does NOT prevent it

Cleaning is still worth doing, because 30.5% of this mesh is geometry no ray can
reach, so at any given file size a cleaned mesh spends all of it on surface you can
actually see. But it buys a better exchange rate, not immunity. The breaking point
is set by the face budget, and nobody has measured where it is.

This writes a ladder of budgets so the renders can find it. The measurement it
reports alongside is the one that should generalise: faces per micrometre of
dendrite is a density, so a threshold in those units should transfer to a cell of a
different size, which a raw face count never will.

  python mesh_budget_ladder.py --cell ID
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
AP.add_argument("--budgets", default="350000,700000,1400000,2800000")
A = AP.parse_args()

os.makedirs(A.out, exist_ok=True)
src = os.path.join(A.dir, f"{A.cell}.obj")

# Clean ONCE, then decimate the cleaned mesh to each budget. Re-cleaning per budget
# would waste minutes and, worse, let the variants differ by more than the budget.
t0 = time.time()
base = pymeshlab.MeshSet()
base.load_new_mesh(src)
f_raw = base.current_mesh().face_number()
base.compute_scalar_ambient_occlusion()
q = np.asarray(base.current_mesh().vertex_scalar_array(), dtype=float)
base.compute_selection_by_scalar_per_vertex(minq=-1e9, maxq=1e-9)
base.meshing_remove_selected_vertices()
f_clean = base.current_mesh().face_number()
clean_path = os.path.join(A.out, f"{A.cell}_L_clean.obj")
base.save_current_mesh(clean_path, save_vertex_normal=False)
print(f"[L] {f_raw:,} -> {f_clean:,} after removing invisible "
      f"({100*(f_raw-f_clean)/f_raw:.1f}%), {time.time()-t0:.0f}s", flush=True)

# Total dendrite length, so a budget can be expressed as a density rather than a
# count. Surface area over a mean process radius is a crude cable estimate, but it
# is measured from this cell rather than assumed, and it is the same estimate for
# every budget so the comparison between them is exact.
geo = base.get_geometric_measures()
area_nm2 = float(geo["surface_area"])
area_um2 = area_nm2 / 1e6
print(f"[L] surface area {area_um2:,.0f} um2", flush=True)

for target in [int(x) for x in A.budgets.split(",")]:
    ms = pymeshlab.MeshSet()
    ms.load_new_mesh(clean_path)
    t0 = time.time()
    if target < f_clean:
        ms.meshing_decimation_quadric_edge_collapse(
            targetfacenum=target, preservenormal=True,
            preservetopology=False, planarquadric=True)
    got = ms.current_mesh().face_number()
    p = os.path.join(A.out, f"{A.cell}_L_{target}.obj")
    ms.save_current_mesh(p, save_vertex_normal=False)
    mb = os.path.getsize(p) / 1e6
    print(f"[L] {target:>9,} -> {got:>9,} faces  {mb:>6.1f} MB  "
          f"{got/area_um2:>7.2f} faces per um2  ({time.time()-t0:.0f}s)", flush=True)

print(f"[L] originals for reference: raw {f_raw:,} = {f_raw/area_um2:.2f} faces per um2",
      flush=True)
print("[L] now render the ladder and find where the dendrites start to bead.", flush=True)
