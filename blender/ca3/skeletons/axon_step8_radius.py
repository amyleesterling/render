"""Step 8: proper cross-sectional radius (slab method) + hunt for the true axon:
thin, input-free, emerging near the soma."""
import numpy as np
from scipy.spatial import cKDTree
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components, dijkstra

sk = np.load(r'D:\Meshes\skeletons\648518346438632877.npz', allow_pickle=True)
S = sk['vertices'].astype(np.float64); E = sk['edges']; ROOT = int(sk['root'])
N = len(S); SOMA = S[ROOT]
V = np.load(r'D:\Meshes\skeletons\_hero_verts.npy').astype(np.float64)
MA = np.load(r'D:\Meshes\skeletons\_mesh_assign.npz')
in_dens = MA['in_dens']; inmain = MA['inmain']; de = MA['de']; dy = MA['dy']
n_in = MA['n_in']; n_out = MA['n_out']
M = np.load(r'D:\Meshes\skeletons\_node_metrics.npz'); cable = M['cable']

w = np.linalg.norm(S[E[:, 0]] - S[E[:, 1]], axis=1) / 1000.
A = coo_matrix((np.r_[w, w], (np.r_[E[:, 0], E[:, 1]], np.r_[E[:, 1], E[:, 0]])),
               shape=(N, N)).tocsr()

# ---- local tangent from skeleton neighbours within 2 um geodesic ----
D2 = dijkstra(A, directed=False, limit=2.5)
tang = np.zeros((N, 3))
for i in range(N):
    nb = np.where(np.isfinite(D2[i]))[0]
    if len(nb) < 3:
        nb = np.r_[nb, i]
    P = S[nb] - S[nb].mean(0)
    if len(nb) >= 2:
        u, s, vt = np.linalg.svd(P, full_matrices=False)
        tang[i] = vt[0]
    else:
        tang[i] = [0, 0, 1]

# ---- slab cross-section radius ----
tv = cKDTree(V)
SLAB = 400.        # nm half-thickness
BALL = 5000.       # nm search radius
rad_x = np.full(N, np.nan)     # p20 of in-plane distance  (shaft radius)
rad_x50 = np.full(N, np.nan)
rad_x90 = np.full(N, np.nan)
nslab = np.zeros(N, int)
for i in range(N):
    idx = tv.query_ball_point(S[i], BALL)
    if not idx: continue
    rel = V[idx] - S[i]
    ax = rel @ tang[i]
    m = np.abs(ax) < SLAB
    if m.sum() < 8: continue
    rr = np.linalg.norm(rel[m] - np.outer(ax[m], tang[i]), axis=1) / 1000.
    nslab[i] = m.sum()
    rad_x[i], rad_x50[i], rad_x90[i] = np.percentile(rr, [20, 50, 90])
print('slab radius computed for %d / %d nodes' % (np.isfinite(rad_x).sum(), N))
np.savez(r'D:\Meshes\skeletons\_radius_slab.npz', rad_x=rad_x, rad_x50=rad_x50,
         rad_x90=rad_x90, tang=tang, nslab=nslab)

def pct(nm, x, m):
    v = x[m]; v = v[np.isfinite(v)]
    if len(v) == 0: print(nm, 'empty'); return
    print('%-26s n=%5d  p5 %.3f p25 %.3f p50 %.3f p75 %.3f p95 %.3f' %
          ((nm, len(v)) + tuple(np.percentile(v, [5, 25, 50, 75, 95]))))

P = np.load(r'D:\Meshes\skeletons\_partition.npz')
is_desc = P['is_axon']; is_asc = P['is_dend']
print('\n--- cross-sectional SHAFT radius (um), slab p20 ---')
pct('DESCENDING arbor', rad_x, is_desc)
pct('ASCENDING arbor', rad_x, is_asc)
pct('  ascending, MF zone (<60um)', rad_x, is_asc & (de < 60))
print('--- spininess: slab p90/p20 ---')
sp = rad_x90 / rad_x
pct('DESCENDING arbor', sp, is_desc)
pct('ASCENDING arbor', sp, is_asc)

# ---------------- axon hunt ----------------
print('\n' + '=' * 88)
print('L. AXON HUNT: connected pieces that are thin AND input-free')
print('=' * 88)
for rthr, ithr in [(0.45, 0.30), (0.5, 0.5), (0.55, 0.75), (0.6, 1.0)]:
    m = inmain & (de > 7) & (rad_x < rthr) & (in_dens < ithr)
    if m.sum() < 3: continue
    idx = np.where(m)[0]
    nc, l = connected_components(A[m][:, m], directed=False)
    rows = []
    for k in range(nc):
        mm = np.zeros(N, bool); mm[idx[l == k]] = True
        rows.append((cable[mm].sum(), int(mm.sum()), float(dy[mm].mean()),
                     float(np.nanmedian(rad_x[mm])), float(n_in[mm].sum()),
                     float(n_out[mm].sum()), float(de[mm].min()), float(de[mm].max())))
    rows.sort(reverse=True)
    print('\nrad<%.2f & in_dens<%.2f : %.1f um total, %d pieces. Top:' % (rthr, ithr, cable[m].sum(), nc))
    print('   %8s %6s %8s %7s %6s %6s %7s %7s' %
          ('cable', 'nodes', 'mean_dy', 'rad', 'n_in', 'n_out', 'minR', 'maxR'))
    for r in rows[:5]:
        print('   %8.1f %6d %+8.1f %7.3f %6.0f %6.0f %7.1f %7.1f' % r)

# ---- the single best axon candidate, traced back to the soma ----
print('\n' + '=' * 88)
print('M. BEST CANDIDATE traced back toward the soma')
print('=' * 88)
m = inmain & (de > 7) & (rad_x < 0.5) & (in_dens < 0.5)
idx = np.where(m)[0]; nc, l = connected_components(A[m][:, m], directed=False)
sizes = [(cable[idx[l == k]].sum(), k) for k in range(nc)]
sizes.sort(reverse=True)
gdist, pred = dijkstra(A, indices=ROOT, directed=False, return_predecessors=True)
for cab, k in sizes[:3]:
    piece = idx[l == k]
    tip = piece[np.argmax(gdist[piece])]
    near = piece[np.argmin(gdist[piece])]
    print('\npiece cable %.1f um, %d nodes, nearest node geo %.1f um / euclid %.1f um, dy %+.1f'
          % (cab, len(piece), gdist[near], de[near], dy[near]))
    path = []; j = int(near)
    while j != ROOT and j >= 0:
        path.append(j); j = int(pred[j])
    path.append(ROOT); path = path[::-1]
    print('  path soma -> piece (%d nodes):  idx  euclidR  dy   rad_x  in_dens' % len(path))
    for j in path[::max(1, len(path) // 25)]:
        print('     %5d %7.2f %+7.2f  %6.3f %8.2f' % (j, de[j], dy[j], rad_x[j], in_dens[j]))
