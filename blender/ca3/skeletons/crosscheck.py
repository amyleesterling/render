"""Independent checks on how much cable the hero mesh actually contains.

1. Membrane surface area of the native mesh (trimesh).
2. A denser meshparty skeleton from the decimated mesh, for comparison with
   the 6.6 um-spaced pcg_skel skeleton served by CAVE.
"""
import time, json
import numpy as np
import trimesh

t0 = time.time()

dec = trimesh.load(r"D:\Meshes\thorny pyramidals ca3 250\648518346438632877.obj",
                   process=False)
print(f"decimated: {len(dec.vertices):,} v  {len(dec.faces):,} f  "
      f"area {dec.area/1e6:,.0f} um^2  [{time.time()-t0:.0f}s]", flush=True)

nat = trimesh.load(r"D:\Meshes\hero\hero_648518346438632877.obj", process=False)
print(f"native:    {len(nat.vertices):,} v  {len(nat.faces):,} f  "
      f"area {nat.area/1e6:,.0f} um^2  [{time.time()-t0:.0f}s]", flush=True)
try:
    print(f"native volume (may be unreliable if not watertight): "
          f"{abs(nat.volume)/1e9:,.0f} um^3  watertight={nat.is_watertight}", flush=True)
except Exception as e:
    print("volume failed:", e, flush=True)
del nat

# ---- denser skeleton via meshparty on the decimated mesh ----
try:
    from meshparty import trimesh_io, skeletonize
    m = trimesh_io.Mesh(vertices=np.asarray(dec.vertices),
                        faces=np.asarray(dec.faces), process=False)
    soma = np.array(json.load(open(r"D:\Meshes\skeletons\_soma.json"))["soma_centre_nm"])
    for inval in (4000, 2000):
        try:
            t1 = time.time()
            sk = skeletonize.skeletonize_mesh(m, soma_pt=soma, soma_radius=7000,
                                              invalidation_d=inval,
                                              collapse_soma=True,
                                              compute_radius=False)
            cable = float(np.linalg.norm(sk.vertices[sk.edges[:, 0]] -
                                         sk.vertices[sk.edges[:, 1]], axis=1).sum() / 1000.)
            print(f"meshparty invalidation_d={inval}: V={len(sk.vertices)} "
                  f"E={len(sk.edges)} cable={cable:,.0f} um  root={sk.root} "
                  f"[{time.time()-t1:.0f}s]", flush=True)
            np.savez_compressed(rf"D:\Meshes\skeletons\_meshparty_hero_inval{inval}.npz",
                                vertices=sk.vertices, edges=sk.edges, root=int(sk.root))
        except Exception as e:
            print(f"meshparty invalidation_d={inval} FAILED: {type(e).__name__} {e}",
                  flush=True)
except Exception as e:
    print("meshparty import/setup failed:", type(e).__name__, e, flush=True)

print("CROSSCHECK DONE", f"{time.time()-t0:.0f}s", flush=True)
