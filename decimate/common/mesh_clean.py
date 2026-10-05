"""Clean a connectomics mesh before decimating it. Debris, then interior, then decimate.

WHY THE ORDER MATTERS. Measured on the EyeWire II retina cells, 31 July 2026:
  - a single cell carries 279 to 1018 CONNECTED COMPONENTS. A neuron is one object,
    so all but a few are detached debris: 1.9% to 17.8% of faces.
  - on some cells MORE THAN HALF the vertices are fully enclosed, invisible from
    every direction. Those are the nested inner shells marching cubes leaves inside
    a soma. They are not detached, so component removal never touches them, which
    is why they are so hard to get rid of.
Decimating first spends the face budget on surfaces nobody can see and pays for it
by collapsing thin processes, which is exactly how branches break.

THE GUARD. Interior removal is only accepted if the mesh's visible extent barely
changes. If the bounding box shrinks by more than a hair, we deleted real surface
rather than hidden surface, so the step is rolled back. A cleanup that silently
eats a dendrite is worse than no cleanup.

  python mesh_clean.py --dir D:\\Meshes\\retina\\meshes [--apply] [--n 6]
                       [--target-mb 6] [--no-decimate]
"""
import argparse
import glob
import os
import shutil

import numpy as np
import pymeshlab

AP = argparse.ArgumentParser()
AP.add_argument("--dir", default=r"D:\Meshes\retina\meshes")
AP.add_argument("--apply", action="store_true")
AP.add_argument("--n", type=int, default=0, help="0 = all files")
AP.add_argument("--minfaces", type=int, default=250)
AP.add_argument("--debris", action="store_true",
                help="remove small connected components. UNSAFE, see the note below")
# Ambient occlusion on this build spans 0 to about 16, NOT 0 to 1. The old default
# of 0.002 was not a small threshold, it was zero, and every value swept from 0 to
# 0.002 meant the same thing and agreed for the wrong reason. Exactly zero is the
# meaningful cut: the vertex received no ray from any direction.
AP.add_argument("--ao", type=float, default=1e-9,
                help="AO at or below this is enclosed (scale is 0..16)")
AP.add_argument("--bbox-tol", type=float, default=0.01, help="allowed extent loss")
AP.add_argument("--target-mb", type=float, default=0.0, help="0 = do not decimate")
AP.add_argument("--min-keep", type=float, default=0.25,
                help="never decimate below this fraction of faces")
A = AP.parse_args()

RAW = os.path.join(os.path.dirname(A.dir.rstrip("\\/")), "meshes_raw")


def extent(ms):
    bb = ms.current_mesh().bounding_box()
    return np.array([bb.dim_x(), bb.dim_y(), bb.dim_z()], dtype=float)


def clean_one(path, apply_it):
    ms = pymeshlab.MeshSet()
    ms.load_new_mesh(path)
    f0 = ms.current_mesh().face_number()
    ext0 = extent(ms)
    steps = {}

    # 1. detached debris. OFF BY DEFAULT, and it must stay off until someone can
    # tell a fragment from a dendrite tip.
    #
    # The premise was that a neuron is one object and small components are
    # segmentation litter. On the staged retina meshes that is simply false.
    # Cell 720575940550200928 has 10,122 components and the largest is 6.5% of the
    # mesh, so mincomponentsize=250 deleted 58.1% of faces and took 14% off the
    # bounding box. The pieces it dropped reach 49.5% of the bbox diagonal from
    # centre against 49.6% for the pieces it kept: they are spread to the
    # periphery exactly like the rest of the cell, because they ARE the cell.
    #
    # Not an unwelded-vertex artefact either. Merging close vertices moved the
    # vertex count by 0.0% and left the component count unchanged.
    #
    # The safe threshold depends on the dataset and on whether the mesh has
    # already been downsampled, so this needs a per-dataset rule rather than one
    # constant. Amy's call, 31 July 2026: skip the step for now.
    if A.debris:
        try:
            ms.meshing_remove_connected_component_by_face_number(mincomponentsize=A.minfaces)
            steps["debris"] = f0 - ms.current_mesh().face_number()
        except Exception as e:
            steps["debris_error"] = type(e).__name__
    else:
        steps["debris"] = 0
    f1 = ms.current_mesh().face_number()

    # 2. enclosed interior, by ambient occlusion, with a rollback guard
    guarded = False
    try:
        ms.compute_scalar_ambient_occlusion()
        ms.compute_selection_by_scalar_per_vertex(minq=-1e9, maxq=A.ao)
        ms.meshing_remove_selected_vertices()
        ext1 = extent(ms)
        loss = float(np.max((ext0 - ext1) / np.maximum(ext0, 1e-9)))
        if loss > A.bbox_tol:
            # took real surface: start again and skip this step
            ms = pymeshlab.MeshSet()
            ms.load_new_mesh(path)
            ms.meshing_remove_connected_component_by_face_number(mincomponentsize=A.minfaces)
            steps["interior"] = 0
            steps["interior_rolled_back"] = round(loss, 4)
            guarded = True
        else:
            steps["interior"] = f1 - ms.current_mesh().face_number()
            steps["extent_loss"] = round(loss, 5)
    except Exception as e:
        steps["interior_error"] = type(e).__name__
    f2 = ms.current_mesh().face_number()

    # 3. decimate what is left, proportionally, with a floor
    if A.target_mb > 0:
        mb = os.path.getsize(path) / 1e6
        ratio = min(1.0, A.target_mb / mb) if mb > 0 else 1.0
        target = int(max(f2 * A.min_keep, f2 * ratio))
        if target < f2:
            try:
                ms.meshing_decimation_quadric_edge_collapse(
                    targetfacenum=target, preservenormal=True,
                    preservetopology=False, planarquadric=True)
                steps["decimate"] = f2 - ms.current_mesh().face_number()
            except Exception as e:
                steps["decimate_error"] = type(e).__name__
    f3 = ms.current_mesh().face_number()

    if apply_it:
        os.makedirs(RAW, exist_ok=True)
        keep = os.path.join(RAW, os.path.basename(path))
        if not os.path.exists(keep):
            shutil.copy2(path, keep)
        ms.save_current_mesh(path, save_vertex_normal=False, save_face_color=False)
    return f0, f1, f2, f3, steps, guarded


files = sorted(glob.glob(os.path.join(A.dir, "*.obj")), key=os.path.getsize)
if A.n:
    step = max(1, len(files) // A.n)
    files = files[::step][:A.n]
print(f"[clean] {len(files)} meshes, apply={A.apply}, "
      f"decimate={'off' if A.target_mb <= 0 else f'{A.target_mb} MB target'}", flush=True)

T = [0, 0, 0, 0]
rolled = 0
for i, p in enumerate(files, 1):
    f0, f1, f2, f3, st, guard = clean_one(p, A.apply)
    T[0] += f0; T[1] += f1; T[2] += f2; T[3] += f3
    rolled += 1 if guard else 0
    if i <= 8 or i % 25 == 0 or i == len(files):
        print(f"  {os.path.basename(p)[:19]:<19} {f0:>8,} -> debris {f0-f1:>6,}"
              f" -> interior {f1-f2:>6,} -> final {f3:>8,}"
              f"{'   [interior ROLLED BACK]' if guard else ''}", flush=True)

if T[0]:
    print(f"\n[clean] totals: {T[0]:,} faces")
    print(f"         debris removed:   {T[0]-T[1]:>9,}  ({100*(T[0]-T[1])/T[0]:5.1f}%)")
    print(f"         interior removed: {T[1]-T[2]:>9,}  ({100*(T[1]-T[2])/T[0]:5.1f}%)")
    print(f"         decimated away:   {T[2]-T[3]:>9,}  ({100*(T[2]-T[3])/T[0]:5.1f}%)")
    print(f"         final:            {T[3]:>9,}  ({100*T[3]/T[0]:5.1f}% of original)")
    if rolled:
        print(f"         interior step rolled back on {rolled} mesh(es) to protect real surface")
print("[clean] dry run, nothing written" if not A.apply else f"[clean] written; originals in {RAW}")
