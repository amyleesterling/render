"""Test the hypothesis: ambient occlusion is useless here because the normals are wrong.

Every AO threshold from 0 to 0.002 gave an identical result, which cannot be true of
a real occlusion measurement. The likely cause is that these marching-cubes meshes
have incoherent face orientation, so AO reports 0 for faces whose normal points
into the volume regardless of whether anything is actually blocking them.

If that is right, re-orienting faces coherently first should make AO spread out
into a real distribution, and then a threshold can separate hidden from visible.
"""
import glob
import os

import numpy as np
import pymeshlab

reor = [n for n in dir(pymeshlab.MeshSet) if "orient" in n.lower()]
print("re-orientation filters:", reor)

p = sorted(glob.glob(r"D:\Meshes\retina\meshes\*.obj"), key=os.path.getsize)[len(
    sorted(glob.glob(r"D:\Meshes\retina\meshes\*.obj"))) // 2]
print(f"\ncell: {os.path.basename(p)}\n")


def ao_stats(label, fn):
    ms = pymeshlab.MeshSet()
    ms.load_new_mesh(p)
    ms.meshing_remove_connected_component_by_face_number(mincomponentsize=250)
    try:
        fn(ms)
    except Exception as e:
        print(f"  {label}: prep failed {type(e).__name__} {str(e)[:70]}")
        return
    try:
        ms.compute_scalar_ambient_occlusion()
    except Exception as e:
        print(f"  {label}: AO failed {type(e).__name__}")
        return
    q = np.asarray(ms.current_mesh().vertex_scalar_array(), dtype=float)
    zeros = float((q <= 1e-9).sum()) / len(q)
    print(f"  {label:<34} AO min {q.min():.4f} max {q.max():.4f} "
          f"median {np.median(q):.4f}  exactly-zero {zeros*100:5.1f}%")


ao_stats("as loaded", lambda ms: None)
ao_stats("normals recomputed", lambda ms: ms.compute_normal_per_face())
ao_stats("faces re-oriented coherently",
         lambda ms: ms.meshing_re_orient_faces_coherentely())
ao_stats("re-oriented + normals",
         lambda ms: (ms.meshing_re_orient_faces_coherentely(),
                     ms.compute_normal_per_face()))
