import numpy as np, time, trimesh, pandas as pd
from scipy.spatial import cKDTree
t0=time.time()
d=np.load(r'D:\Meshes\skeletons\648518346438632877.npz',allow_pickle=True)
sv=d['vertices']

# --- where do the 165 MF synapses land? (raw CSV coords) ---
df=pd.read_csv(r'D:\Meshes\renders\mf_synapses.csv')
s=df[df.post_pt_root_id==648518346438632877]
pos=np.stack([np.array([float(t) for t in str(x).strip('[]').split()]) for x in s.ctr_pt_position])
print("synapse RAW ctr: min",pos.min(0).round(0),"max",pos.max(0).round(0),"mean",pos.mean(0).round(0))
print("hero SKEL bbox : min",sv.min(0).round(0),"max",sv.max(0).round(0))
# figure out scale by matching bbox
for name,sc in [("raw(nm)",np.array([1,1,1])),("x9y9z45",np.array([9,9,45])),("x8y8z40",np.array([8,8,40]))]:
    p=pos*sc
    inside = ((p>=sv.min(0)-20000).all(1)&(p<=sv.max(0)+20000).all(1)).mean()
    print(f"  scale {name}: frac within skel bbox+20um = {inside:.2f}")
t=cKDTree(sv)
for name,sc in [("raw(nm)",np.array([1,1,1])),("x9y9z45",np.array([9,9,45]))]:
    dd,_=t.query(pos*sc,k=1)
    print(f"  scale {name}: median dist to nearest skeleton node = {np.median(dd)/1000:.2f} um")

# --- authoritative inscribed-sphere: trimesh containment on decimated hero ---
m=trimesh.load(r"D:\Meshes\thorny pyramidals ca3 250\648518346438632877.obj", process=False)
print("\ndecimated mesh", m.vertices.shape, m.faces.shape, "watertight", m.is_watertight, f"{time.time()-t0:.0f}s", flush=True)
mvfull=[]
with open(r"D:\Meshes\hero\hero_648518346438632877.obj") as f:
    for line in f:
        if line[0]=='v' and line[1]==' ': mvfull.append(line[2:])
mvfull=np.fromstring(" ".join(mvfull),sep=' ').reshape(-1,3)
ftree=cKDTree(mvfull)
# fine grid near the arbor only
mn,mx=sv.min(0)-10000, sv.max(0)+10000
step=2000.
G=np.stack(np.meshgrid(*[np.arange(mn[k],mx[k],step) for k in range(3)],indexing='ij'),-1).reshape(-1,3)
near=t.query(G,k=1)[0]<12000
G=G[near]
clear,_=ftree.query(G,k=1)
sel=np.argsort(-clear)[:4000]
G,clear=G[sel],clear[sel]
print("testing containment on",len(G),"high-clearance pts near arbor",f"{time.time()-t0:.0f}s",flush=True)
cont=m.contains(G)
print("contained:",int(cont.sum()),f"{time.time()-t0:.0f}s",flush=True)
if cont.sum():
    Gi,Ci=G[cont],clear[cont]
    for j in np.argsort(-Ci)[:10]:
        print(f"  inscribed R {Ci[j]/1000:6.2f} um at {Gi[j].round(0)}  nearest_skel_node={t.query(Gi[j])[1]}")
