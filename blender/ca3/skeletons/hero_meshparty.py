"""Dense skeleton of the hero cell with meshparty, from the NATIVE mesh.

The CAVE pcg_skel skeleton has only 392 nodes (~6.6 um spacing), too coarse
for a smooth travelling-pulse animation. This produces a dense centreline in
exactly the same coordinate space (nanometres, OBJ file space).
"""
import time, json, os
import numpy as np
import trimesh
from meshparty import trimesh_io, skeletonize

t0 = time.time()
soma = np.array(json.load(open(r"D:\Meshes\skeletons\_soma.json"))["soma_centre_nm"])
print("soma", soma, flush=True)

src = r"D:\Meshes\hero\hero_648518346438632877.obj"
tm = trimesh.load(src, process=False)
print(f"loaded native {len(tm.vertices):,} v {len(tm.faces):,} f [{time.time()-t0:.0f}s]", flush=True)
m = trimesh_io.Mesh(vertices=np.asarray(tm.vertices), faces=np.asarray(tm.faces),
                    process=False)
del tm

for inval, tag in ((3000, "inval3000"),):
    t1 = time.time()
    try:
        sk = skeletonize.skeletonize_mesh(m, soma_pt=soma, soma_radius=7000,
                                          invalidation_d=inval,
                                          collapse_soma=True, compute_radius=False)
        v, e = np.asarray(sk.vertices), np.asarray(sk.edges)
        cable = float(np.linalg.norm(v[e[:, 0]] - v[e[:, 1]], axis=1).sum() / 1000.)
        np.savez_compressed(r"D:\Meshes\skeletons\648518346438632877_meshparty.npz",
                            vertices=v, edges=e, root=int(sk.root),
                            source=f"meshparty.skeletonize_mesh invalidation_d={inval} on native mesh",
                            seg_id="648518346438632877")
        print(f"HERO meshparty {tag}: V={len(v)} E={len(e)} cable={cable:,.1f} um "
              f"root={sk.root} [{time.time()-t1:.0f}s]", flush=True)
    except Exception as ex:
        print(f"HERO meshparty {tag} FAILED: {type(ex).__name__} {str(ex)[:400]}", flush=True)
print("HERO_MESHPARTY DONE", f"{time.time()-t0:.0f}s", flush=True)
