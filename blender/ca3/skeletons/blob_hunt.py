"""Find the largest inscribed sphere in the hero mesh -> locates a soma if one exists."""
import numpy as np, time
from scipy.spatial import cKDTree
t0=time.time()
vs=[]
with open(r"D:\Meshes\hero\hero_648518346438632877.obj") as f:
    for line in f:
        if line[0]=='v' and line[1]==' ': vs.append(line[2:])
mv = np.fromstring(" ".join(vs), sep=' ').reshape(-1,3); del vs
tree = cKDTree(mv)
print("mesh", mv.shape, f"{time.time()-t0:.0f}s", flush=True)

# native-mesh surface-vertex count within 8 um of each skeleton node
d = np.load(r'D:\Meshes\skeletons\648518346438632877.npz', allow_pickle=True)
sv = d['vertices']
cnt = np.array([len(tree.query_ball_point(p, 8000.0)) for p in sv])
print("\nNATIVE mesh vertices within 8um of each skeleton node (top 8):", flush=True)
for i in np.argsort(-cnt)[:8]:
    print(f"  idx {i:4d} count {cnt[i]:7d} pos {sv[i].round(0)}", flush=True)
print("median count", int(np.median(cnt)), flush=True)

# grid search for largest inscribed sphere (isotropy test = inside)
mn, mx = mv.min(0), mv.max(0)
step = 3000.0
gs = [np.arange(mn[k]+step, mx[k], step) for k in range(3)]
G = np.stack(np.meshgrid(*gs, indexing='ij'), -1).reshape(-1,3)
print("\ngrid pts", G.shape, f"{time.time()-t0:.0f}s", flush=True)
dist,_ = tree.query(G, k=1)
keep = dist > 2500.0
G2, D2 = G[keep], dist[keep]
print("candidates with clearance >2.5um:", len(G2), flush=True)
# isotropy: mean unit direction to 64 nearest surface verts; ~0 => enclosed
res=[]
for p, dd in zip(G2, D2):
    idx = tree.query(p, k=64)[1]
    u = mv[idx]-p
    u = u/np.linalg.norm(u,axis=1,keepdims=True)
    res.append(np.linalg.norm(u.mean(0)))
res=np.array(res)
inside = res < 0.35
print("enclosed candidates:", int(inside.sum()), flush=True)
if inside.sum():
    Gi, Di = G2[inside], D2[inside]
    for j in np.argsort(-Di)[:10]:
        print(f"  inscribed R {Di[j]:7.0f} nm ({Di[j]/1000:.2f} um)  at {Gi[j].round(0)}  isotropy {res[inside][j]:.2f}", flush=True)
else:
    print("  none -> no enclosed volume larger than 2.5um radius anywhere in this mesh", flush=True)
print("done", f"{time.time()-t0:.0f}s", flush=True)
