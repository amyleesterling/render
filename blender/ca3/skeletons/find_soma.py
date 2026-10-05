import numpy as np, collections, ast
import pandas as pd
from scipy.spatial import cKDTree

d = np.load(r'D:\Meshes\skeletons\648518346438632877.npz', allow_pickle=True)
v = d['vertices']; r = d['radius']; e = d['edges']
deg = collections.Counter()
for a, b in e: deg[int(a)] += 1; deg[int(b)] += 1

# decimated hero mesh vertices (uniform decimation -> vertex count ~ surface area)
mv = []
with open(r"D:\Meshes\thorny pyramidals ca3 250\648518346438632877.obj") as f:
    for line in f:
        if line[:2] == 'v ':
            mv.append(np.fromstring(line[2:], sep=' ', count=3))
mv = np.array(mv)
print("decimated mesh verts:", mv.shape, flush=True)
tree = cKDTree(mv)
R = 7500.0
cnt = np.array([len(tree.query_ball_point(p, R)) for p in v])
top = np.argsort(-cnt)[:10]
print("\nmesh-vertex count within 7.5um of each skeleton node (soma should dominate):")
for i in top:
    print(f"  idx {i:4d}  count {cnt[i]:6d}  deg {deg[i]:3d}  radius {r[i]:7.0f}  pos {v[i].round(0)}")

# cross-check: where are the 165 mossy-fibre synapses onto the hero?
df = pd.read_csv(r'D:\Meshes\renders\mf_synapses.csv')
s = df[df.post_pt_root_id == 648518346438632877]
def parse(x):
    return np.array([float(t) for t in str(x).strip('[]').split()])
pos = np.stack([parse(x) for x in s.ctr_pt_position])  # voxel coords
# viewer resolution from datastack info: 18,18,45 nm  -> but synapse table is usually 4x4x40 or similar
for scale in [np.array([18,18,45]), np.array([9,9,45]), np.array([4,4,40])]:
    p = pos * scale
    print(f"\nsyn ctr * {scale}: min {p.min(0).round(0)} max {p.max(0).round(0)} mean {p.mean(0).round(0)}")
