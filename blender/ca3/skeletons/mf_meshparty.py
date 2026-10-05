"""Fallback: skeletonize the 6 mossy-fibre meshes locally with meshparty.

Written to <segid>_meshparty.npz so it never collides with the CAVE fetch.
"""
import time, os
import numpy as np
import trimesh
from meshparty import trimesh_io, skeletonize

OUT = r"D:\Meshes\skeletons"
MFS = [648518346432881590, 648518346440660317, 648518346448994107,
       648518346450631673, 648518346452106477, 648518346460875907]

for seg in MFS:
    dst = os.path.join(OUT, f"{seg}_meshparty.npz")
    if os.path.exists(dst):
        print(f"{seg} meshparty already done", flush=True)
        continue
    t0 = time.time()
    try:
        src = rf"D:\Meshes\hero\fibre_{seg}.obj"
        tm = trimesh.load(src, process=False)
        m = trimesh_io.Mesh(vertices=np.asarray(tm.vertices),
                            faces=np.asarray(tm.faces), process=False)
        del tm
        sk = skeletonize.skeletonize_mesh(m, soma_pt=None, invalidation_d=2000,
                                          collapse_soma=False, compute_radius=False)
        v, e = np.asarray(sk.vertices), np.asarray(sk.edges)
        cable = float(np.linalg.norm(v[e[:, 0]] - v[e[:, 1]], axis=1).sum() / 1000.)
        np.savez_compressed(dst, vertices=v, edges=e, root=int(sk.root),
                            source="meshparty.skeletonize_mesh invalidation_d=2000",
                            seg_id=str(seg))
        print(f"{seg}: V={len(v)} E={len(e)} cable={cable:,.1f} um "
              f"root={sk.root} [{time.time()-t0:.0f}s]", flush=True)
    except Exception as ex:
        print(f"{seg} FAILED: {type(ex).__name__} {str(ex)[:300]} "
              f"[{time.time()-t0:.0f}s]", flush=True)
print("MF_MESHPARTY DONE", flush=True)
