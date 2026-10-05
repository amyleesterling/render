"""Do these meshes really carry hidden polygons inside the somas, and how many?

Ambient occlusion is the test: a face on the outer surface sees the sky, a face on
an inner shell sees nothing. If a large share of faces have near-zero occlusion
value, they are enclosed and invisible from every direction, which is exactly the
geometry Amy cannot get rid of.

Measures before touching anything.
"""
import glob
import os
import sys

import numpy as np
import pymeshlab

print("pymeshlab", pymeshlab.__version__ if hasattr(pymeshlab, "__version__") else "?")

# which AO filter does this build expose?
names = [n for n in dir(pymeshlab.MeshSet) if "ambient" in n.lower() or "occl" in n.lower()]
print("AO filters available:", names)
conn = [n for n in dir(pymeshlab.MeshSet) if "connected" in n.lower()]
print("connected-component filters:", conn[:6])
sel = [n for n in dir(pymeshlab.MeshSet) if n.startswith("compute_selection")]
print("selection filters:", sel[:10])

files = sorted(glob.glob(r"D:\Meshes\retina\meshes\*.obj"), key=os.path.getsize)
sample = [files[len(files) // 4], files[len(files) // 2], files[-1]]

for p in sample:
    mb = os.path.getsize(p) / 1e6
    ms = pymeshlab.MeshSet()
    ms.load_new_mesh(p)
    m = ms.current_mesh()
    nf, nv = m.face_number(), m.vertex_number()
    print(f"\n=== {os.path.basename(p)}  {mb:.1f} MB  {nv:,} verts  {nf:,} faces ===")

    # connected components: an inner shell is often its own component
    try:
        ms.generate_splitting_by_connected_components(delete_source_mesh=False)
        print(f"  connected components: {ms.mesh_number() - 1}")
        while ms.mesh_number() > 1:
            ms.set_current_mesh(ms.mesh_number() - 1)
            ms.delete_current_mesh()
    except Exception as e:
        print("  component split failed:", type(e).__name__, str(e)[:80])

    ms.set_current_mesh(0)
    try:
        ms.compute_scalar_ambient_occlusion_per_vertex()
        q = ms.current_mesh().vertex_scalar_array()
        q = np.asarray(q, dtype=float)
        for t in (0.001, 0.01, 0.05):
            frac = float((q <= t).sum()) / len(q)
            print(f"  vertices with AO <= {t:<6}: {frac*100:5.1f}%")
        print(f"  AO range {q.min():.4f} .. {q.max():.4f}, median {np.median(q):.4f}")
    except Exception as e:
        print("  AO failed:", type(e).__name__, str(e)[:120])
