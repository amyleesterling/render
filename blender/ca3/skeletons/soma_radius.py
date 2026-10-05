import numpy as np, collections, time
from scipy.spatial import cKDTree
t0=time.time()
d = np.load(r'D:\Meshes\skeletons\648518346438632877.npz', allow_pickle=True)
v = d['vertices']; rad = d['radius']; e = d['edges']
deg = collections.Counter()
for a,b in e: deg[int(a)]+=1; deg[int(b)]+=1

vs=[]
with open(r"D:\Meshes\hero\hero_648518346438632877.obj") as f:
    for line in f:
        if line[0]=='v' and line[1]==' ':
            vs.append(line[2:])
print("parsing", len(vs), "verts", f"{time.time()-t0:.0f}s", flush=True)
mv = np.fromstring(" ".join(vs), sep=' ').reshape(-1,3)
del vs
print("native mesh verts", mv.shape, f"{time.time()-t0:.0f}s", flush=True)
tree = cKDTree(mv)
dist,_ = tree.query(v, k=1)
print("\nlocal radius = distance from skeleton node to nearest NATIVE mesh vertex (nm)")
for i in np.argsort(-dist)[:12]:
    print(f"  idx {i:4d}  localR {dist[i]:7.0f} nm ({dist[i]/1000:.2f} um)  deg {deg[i]:3d}  cave_radius {rad[i]:7.0f}  pos {v[i].round(0)}")
print(f"\nmedian localR {np.median(dist):.0f} nm   p90 {np.percentile(dist,90):.0f} nm")
np.save(r'D:\Meshes\skeletons\_hero_localR.npy', dist)
print("done", f"{time.time()-t0:.0f}s", flush=True)
