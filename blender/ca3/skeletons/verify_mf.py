"""Verify the meshparty MF skeletons: bbox agreement with the OBJ, connectivity,
and how far the real synapses sit from the computed centreline."""
import numpy as np, collections, os
import pandas as pd
from scipy.spatial import cKDTree

MFS = [648518346432881590, 648518346440660317, 648518346448994107,
       648518346450631673, 648518346452106477, 648518346460875907]
df = pd.read_csv(r"D:\Meshes\renders\mf_synapses.csv")
hs = df[df.post_pt_root_id == 648518346438632877]
syn = np.stack([np.array([float(t) for t in str(x).strip("[]").split()])
                for x in hs.ctr_pt_position])
pre = hs.pre_pt_root_id.values

for seg in MFS:
    d = np.load(rf"D:\Meshes\skeletons\{seg}_meshparty.npz", allow_pickle=True)
    v, e = d["vertices"], d["edges"]
    mv = []
    with open(rf"D:\Meshes\hero\fibre_{seg}.obj") as f:
        for line in f:
            if line[0] == "v" and line[1] == " ":
                mv.append(line[2:])
    mv = np.fromstring(" ".join(mv), sep=" ").reshape(-1, 3)
    # connectivity
    adj = collections.defaultdict(list)
    for a, b in e:
        adj[int(a)].append(int(b)); adj[int(b)].append(int(a))
    seen = set(); ncomp = 0; big = 0
    for s in range(len(v)):
        if s in seen: continue
        ncomp += 1; q = [s]; seen.add(s); c = 0
        while q:
            u = q.pop(); c += 1
            for w in adj[u]:
                if w not in seen: seen.add(w); q.append(w)
        big = max(big, c)
    # how far is each skeleton node from the mesh surface (should be sub-micron)
    dd, _ = cKDTree(mv).query(v, k=1)
    # synapse to centreline
    s = syn[pre == seg]
    sd, _ = cKDTree(v).query(s, k=1) if len(s) else (np.array([]), None)
    print(f"{seg}: V={len(v):5d} E={len(e):5d} components={ncomp} largest={big} "
          f"({100*big/len(v):.0f}%)")
    print(f"   OBJ bbox {mv.min(0).round(0).tolist()} .. {mv.max(0).round(0).tolist()}")
    print(f"   SKL bbox {v.min(0).round(0).tolist()} .. {v.max(0).round(0).tolist()}")
    print(f"   skel-node -> mesh-surface distance: median {np.median(dd):.0f} nm, max {dd.max():.0f} nm")
    print(f"   {len(s)} synapses, median {np.median(sd)/1000:.2f} um from centreline, "
          f"max {sd.max()/1000:.2f} um" if len(s) else "   no synapses")
