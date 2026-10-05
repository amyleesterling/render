"""Step 2: per-node geometric metrics, graph structure, synapse diagnostics."""
import numpy as np, json
from scipy.spatial import cKDTree
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components, dijkstra

SK = r'D:\Meshes\skeletons\648518346438632877.npz'
sk = np.load(SK, allow_pickle=True)
S = sk['vertices'].astype(np.float64)      # nm
E = sk['edges']
PAR = sk['parent'].copy()
ROOT = int(sk['root'])
N = len(S)
SOMA = S[ROOT]
print('N nodes', N, 'edges', len(E), 'root', ROOT, 'soma', SOMA)

# ---------- graph ----------
w = np.linalg.norm(S[E[:, 0]] - S[E[:, 1]], axis=1) / 1000.0   # um
A = coo_matrix((np.r_[w, w], (np.r_[E[:, 0], E[:, 1]], np.r_[E[:, 1], E[:, 0]])),
               shape=(N, N)).tocsr()
ncomp, lab = connected_components(A, directed=False)
sizes = np.bincount(lab)
soma_comp = lab[ROOT]
print('components', ncomp, 'soma comp size', sizes[soma_comp],
      '(%.1f%%)' % (100 * sizes[soma_comp] / N))
print('top 10 comp sizes', np.sort(sizes)[::-1][:10])
print('total cable um %.1f  soma-comp cable %.1f' %
      (w.sum(), w[lab[E[:, 0]] == soma_comp].sum()))

# geodesic distance from soma inside its component
gdist = dijkstra(A, indices=ROOT, directed=False)          # um, inf off-component
inmain = np.isfinite(gdist)

# degree
deg = np.bincount(np.r_[E[:, 0], E[:, 1]], minlength=N)

# cable length attributed to each node (half of incident edges)
cable = np.zeros(N)
np.add.at(cable, E[:, 0], w / 2)
np.add.at(cable, E[:, 1], w / 2)

# ---------- mesh-derived metrics ----------
V = np.load(r'D:\Meshes\skeletons\_hero_verts.npy')
vn = np.load(r'D:\Meshes\skeletons\_hero_vert2node.npz')
node_of_vert = vn['node']; dist_of_vert = vn['dist'].astype(np.float64) / 1000.0  # um

order = np.argsort(node_of_vert, kind='stable')
nv_sorted = node_of_vert[order]
dv_sorted = dist_of_vert[order]
starts = np.searchsorted(nv_sorted, np.arange(N))
ends = np.searchsorted(nv_sorted, np.arange(N), side='right')
nvert = ends - starts

r_p25 = np.full(N, np.nan); r_p50 = np.full(N, np.nan)
r_p75 = np.full(N, np.nan); r_p90 = np.full(N, np.nan); r_mean = np.full(N, np.nan)
for i in range(N):
    s, e = starts[i], ends[i]
    if e > s:
        seg = dv_sorted[s:e]
        r_p25[i], r_p50[i], r_p75[i], r_p90[i] = np.percentile(seg, [25, 50, 75, 90])
        r_mean[i] = seg.mean()

# surface area per node from faces
F = np.load(r'D:\Meshes\skeletons\_hero_faces.npy')
p0, p1, p2 = V[F[:, 0]].astype(np.float64), V[F[:, 1]].astype(np.float64), V[F[:, 2]].astype(np.float64)
area = 0.5 * np.linalg.norm(np.cross(p1 - p0, p2 - p0), axis=1) / 1e6   # um^2
fnode = node_of_vert[F[:, 0]]
area_node = np.zeros(N)
np.add.at(area_node, fnode, area)
print('total surface area um^2 %.0f' % area_node.sum())

# densities per um cable (guard tiny cable)
c = np.maximum(cable, 1e-3)
vdens = nvert / c
adens = area_node / c
# expected area per um for a smooth cylinder of radius r_p50: 2*pi*r
adens_ratio = adens / np.maximum(2 * np.pi * r_p50, 1e-6)

np.savez_compressed(r'D:\Meshes\skeletons\_node_metrics.npz',
                    gdist=gdist, deg=deg, cable=cable, lab=lab, soma_comp=soma_comp,
                    nvert=nvert, r_p25=r_p25, r_p50=r_p50, r_p75=r_p75, r_p90=r_p90,
                    r_mean=r_mean, area_node=area_node, vdens=vdens, adens=adens,
                    adens_ratio=adens_ratio)

def q(name, x, m=None):
    x = x[m] if m is not None else x
    x = x[np.isfinite(x)]
    print('%-12s n=%5d  p1 %.3f p10 %.3f p25 %.3f p50 %.3f p75 %.3f p90 %.3f p99 %.3f' %
          ((name, len(x)) + tuple(np.percentile(x, [1, 10, 25, 50, 75, 90, 99]))))

print('\n--- distributions over ALL nodes ---')
for nm, x in [('r_p25', r_p25), ('r_p50', r_p50), ('r_p90', r_p90),
              ('vdens', vdens), ('adens', adens), ('adens_ratio', adens_ratio),
              ('cable', cable)]:
    q(nm, x)

# ---------- synapses ----------
syn = np.load(r'D:\Meshes\renders\hero_outgoing.npy')
tree_s = cKDTree(S)
ds, isyn = tree_s.query(syn, k=1)
ds /= 1000.0
print('\n--- 128 outgoing synapses: distance to nearest skeleton node (um) ---')
print('p10 %.2f p25 %.2f p50 %.2f p75 %.2f p90 %.2f max %.2f' %
      tuple(np.percentile(ds, [10, 25, 50, 75, 90, 100])))
print('within 1um: %d  2um: %d  3um: %d  5um: %d' %
      ((ds < 1).sum(), (ds < 2).sum(), (ds < 3).sum(), (ds < 5).sum()))
print('nearest node on soma component: %d / 128' % inmain[isyn].sum())
# mesh distance: are synapses even on this cell's surface?
tree_v = cKDTree(V.astype(np.float64))
dv, _ = tree_v.query(syn, k=1)
dv /= 1000.0
print('synapse -> nearest MESH vertex (um): p50 %.2f p90 %.2f max %.2f; within 1um %d/128' %
      (np.median(dv), np.percentile(dv, 90), dv.max(), (dv < 1).sum()))
print('geodesic soma-dist of nearest node (um): ',
      np.array2string(np.sort(gdist[isyn][np.isfinite(gdist[isyn])]), precision=1, threshold=200))
np.savez(r'D:\Meshes\skeletons\_syn_diag.npz', ds=ds, isyn=isyn, dv=dv)
