import json, time, os, threading
import numpy as np
from caveclient import CAVEclient

OUT = r"D:\Meshes\skeletons"
ALL = [648518346438632877, 648518346432881590, 648518346440660317,
       648518346448994107, 648518346450631673, 648518346452106477,
       648518346460875907]
lock = threading.Lock()

def save(seg, s):
    v = np.asarray(s['vertices'], dtype=np.float64)
    e = np.asarray(s['edges'], dtype=np.int64)
    tmp = os.path.join(OUT, f".{seg}.tmp.npz")
    np.savez_compressed(tmp, vertices=v, edges=e, root=int(s.get('root', 0)),
        radius=np.asarray(s.get('radius', []), dtype=np.float64),
        compartment=np.asarray(s.get('compartment', []), dtype=np.int64),
        mesh_to_skel_map=np.asarray(s.get('mesh_to_skel_map', []), dtype=np.int64),
        lvl2_ids=np.asarray(s.get('lvl2_ids', []), dtype=np.int64),
        meta_json=json.dumps({k: str(x) for k, x in dict(s.get('meta', {})).items()}),
        seg_id=str(seg))
    os.replace(tmp, os.path.join(OUT, f"{seg}_cave.npz"))
    with lock:
        print(f"SAVED {seg}: V={v.shape} E={e.shape}", flush=True)

def worker(seg):
    dst = os.path.join(OUT, f"{seg}_cave.npz")
    for attempt in range(6):
        if os.path.exists(dst): return
        t0 = time.time()
        try:
            c = CAVEclient('zheng_ca3')
            s = c.skeleton.get_skeleton(seg, output_format='dict')
            save(seg, s)
            with lock: print(f"  {seg} ok in {time.time()-t0:.0f}s (attempt {attempt+1})", flush=True)
            return
        except Exception as e:
            with lock:
                print(f"  {seg} attempt {attempt+1} failed after {time.time()-t0:.0f}s: "
                      f"{type(e).__name__} {str(e)[:180]}", flush=True)
            time.sleep(20)
    with lock: print(f"  {seg} GAVE UP", flush=True)

missing = [s for s in ALL if not os.path.exists(os.path.join(OUT, f"{s}.npz"))]
print("missing:", missing, flush=True)
ts = [threading.Thread(target=worker, args=(s,)) for s in missing]
for t in ts: t.start()
for t in ts: t.join()
still = [s for s in ALL if not os.path.exists(os.path.join(OUT, f"{s}.npz"))]
print("STILL MISSING:", still, flush=True)
print("FETCH4 DONE", flush=True)
