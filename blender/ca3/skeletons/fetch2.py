import json, time, sys, os
import numpy as np
from caveclient import CAVEclient

OUT = r"D:\Meshes\skeletons"
HERO = 648518346438632877
MFS = [648518346432881590, 648518346440660317, 648518346448994107,
       648518346450631673, 648518346452106477, 648518346460875907]
ALL = [HERO] + MFS

c = CAVEclient('zheng_ca3')
sk = c.skeleton

try:
    ex = sk.skeletons_exist(root_ids=ALL)
    print("skeletons_exist:", ex, flush=True)
except Exception as e:
    print("skeletons_exist FAILED:", type(e).__name__, e, flush=True)

for seg in ALL:
    dst = os.path.join(OUT, f"{seg}.npz")
    if os.path.exists(dst):
        print(f"{seg} already saved", flush=True); continue
    t0 = time.time()
    try:
        s = sk.get_skeleton(seg, output_format='dict')
        v = np.asarray(s['vertices'], dtype=np.float64)
        e = np.asarray(s['edges'], dtype=np.int64)
        m2s = np.asarray(s.get('mesh_to_skel_map', []), dtype=np.int64)
        rad = np.asarray(s.get('radius', []), dtype=np.float64)
        comp = np.asarray(s.get('compartment', []), dtype=np.int64)
        lvl2 = np.asarray(s.get('lvl2_ids', []), dtype=np.int64)
        root = int(s.get('root', 0))
        meta = {k: str(val) for k, val in dict(s.get('meta', {})).items()}
        np.savez_compressed(dst, vertices=v, edges=e, root=root,
                            radius=rad, compartment=comp,
                            mesh_to_skel_map=m2s, lvl2_ids=lvl2,
                            meta_json=json.dumps(meta), seg_id=str(seg))
        print(f"{seg}: V={v.shape} E={e.shape} root={root} "
              f"m2s={m2s.shape} lvl2={lvl2.shape} rad_n={rad.shape} "
              f"comp_uniq={np.unique(comp).tolist() if comp.size else 'EMPTY'} "
              f"radius_range={(round(float(rad.min()),1), round(float(rad.max()),1)) if rad.size else 'EMPTY'} "
              f"[{time.time()-t0:.1f}s]", flush=True)
        print(f"   bbox_min={v.min(0).round(0).tolist()} bbox_max={v.max(0).round(0).tolist()}", flush=True)
    except Exception as ex2:
        print(f"{seg} FAILED: {type(ex2).__name__} {str(ex2)[:400]}", flush=True)
print("FETCH DONE", flush=True)
