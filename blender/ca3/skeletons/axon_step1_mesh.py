"""Step 1: parse hero OBJ vertices + faces, cache as npy. Also compute
nearest-skeleton-node assignment for every mesh vertex."""
import numpy as np, os, time

OBJ = r'D:\Meshes\hero\hero_648518346438632877.obj'
CACHE = r'D:\Meshes\skeletons\_hero_verts.npy'
FCACHE = r'D:\Meshes\skeletons\_hero_faces.npy'
NV = 2278184
NF = 4471568

t0 = time.time()
if os.path.exists(CACHE) and os.path.exists(FCACHE):
    V = np.load(CACHE)
    F = np.load(FCACHE)
else:
    V = np.empty((NV, 3), np.float32)
    F = np.empty((NF, 3), np.int32)
    iv = 0
    iff = 0
    with open(OBJ, 'r') as f:
        for line in f:
            c = line[0]
            if c == 'v' and line[1] == ' ':
                a = line.split()
                V[iv, 0] = a[1]; V[iv, 1] = a[2]; V[iv, 2] = a[3]
                iv += 1
            elif c == 'f':
                a = line.split()
                # assume simple 'f i j k' (no slashes) -- verify below
                F[iff, 0] = a[1]; F[iff, 1] = a[2]; F[iff, 2] = a[3]
                iff += 1
    print('parsed verts', iv, 'faces', iff, 'in', time.time() - t0)
    assert iv == NV and iff == NF
    F -= 1
    np.save(CACHE, V); np.save(FCACHE, F)
print('V', V.shape, V.dtype, 'F', F.shape, time.time() - t0)
print('V bbox', V.min(0), V.max(0))

# nearest skeleton node for each mesh vertex
sk = np.load(r'D:\Meshes\skeletons\648518346438632877.npz', allow_pickle=True)
S = sk['vertices'].astype(np.float64)
from scipy.spatial import cKDTree
tree = cKDTree(S)
d, idx = tree.query(V.astype(np.float64), k=1, workers=-1)
print('assign done', time.time() - t0)
np.savez_compressed(r'D:\Meshes\skeletons\_hero_vert2node.npz',
                    node=idx.astype(np.int32), dist=d.astype(np.float32))
print('dist to skeleton nm: p50 %.0f p90 %.0f p99 %.0f max %.0f' %
      tuple(np.percentile(d, [50, 90, 99, 100])))
