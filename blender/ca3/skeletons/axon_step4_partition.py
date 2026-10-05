"""Step 4: build the axon mask from the descending/ascending partition
(co-author hand markup) and cross-check it against independent measurements."""
import numpy as np
from scipy.spatial import cKDTree
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components, dijkstra

sk = np.load(r'D:\Meshes\skeletons\648518346438632877.npz', allow_pickle=True)
S = sk['vertices'].astype(np.float64); E = sk['edges']; ROOT = int(sk['root'])
N = len(S); SOMA = S[ROOT]
M = np.load(r'D:\Meshes\skeletons\_node_metrics.npz')
cable = M['cable']; r_p50 = M['r_p50']; r_p25 = M['r_p25']; r_p90 = M['r_p90']
vdens = M['vdens']; adens = M['adens']; adens_ratio = M['adens_ratio']; nvert = M['nvert']
syn = np.load(r'D:\Meshes\renders\hero_outgoing.npy')

w = np.linalg.norm(S[E[:, 0]] - S[E[:, 1]], axis=1) / 1000.
A = coo_matrix((np.r_[w, w], (np.r_[E[:, 0], E[:, 1]], np.r_[E[:, 1], E[:, 0]])),
               shape=(N, N)).tocsr()
gd = dijkstra(A, indices=ROOT, directed=False)
inmain = np.isfinite(gd)
de = np.linalg.norm(S - SOMA, axis=1) / 1000.
dy = (S[:, 1] - SOMA[1]) / 1000.       # +ve = above soma in frame

print('=' * 78)
print('A. AXIS CHECK -- is the arbor really split into a low-y and a high-y half?')
print('=' * 78)
print('node dy (um) percentiles: ' + ' '.join(
    '%s=%.1f' % (p, v) for p, v in zip([0, 5, 25, 50, 75, 95, 100],
                                       np.percentile(dy, [0, 5, 25, 50, 75, 95, 100]))))
print('cable below soma-y: %.1f um   above: %.1f um' %
      (cable[dy < 0].sum(), cable[dy >= 0].sum()))
for ax, nm in [(0, 'x'), (1, 'y'), (2, 'z')]:
    d = (S[:, ax] - SOMA[ax]) / 1000.
    print('  axis %s: extent below soma %.1f um, above %.1f um, cable-wtd mean %.1f' %
          (nm, -d.min(), d.max(), (d * cable).sum() / cable.sum()))

# --- soma-shell component enumeration at several radii ---
print()
print('=' * 78)
print('B. PRIMARY PROCESSES: components after cutting a sphere around the soma')
print('=' * 78)
comps_by_R = {}
for R in (10., 15., 20., 25., 30.):
    keep = (de >= R) & inmain
    nc, l2 = connected_components(A[keep][:, keep], directed=False)
    lab = np.full(N, -1); lab[np.where(keep)[0]] = l2
    info = []
    for k in range(nc):
        m = lab == k
        if m.sum() < 5: continue
        cab = cable[m].sum()
        if cab < 5: continue
        t = cKDTree(S[m]); dsy, _ = t.query(syn, k=1)
        info.append((k, int(m.sum()), cab,
                     float((dy[m] * cable[m]).sum() / cable[m].sum()),
                     float(dy[m].min()), float(dy[m].max()),
                     int((dsy / 1000. < 3).sum()),
                     float(np.nanmedian(r_p50[m]))))
    info.sort(key=lambda r: -r[2])
    comps_by_R[R] = (lab, info)
    print('\n-- R = %.0f um --  %d significant processes' % (R, len(info)))
    print('  %4s %6s %9s %8s %8s %8s %6s %7s' %
          ('id', 'nodes', 'cable_um', 'mean_dy', 'min_dy', 'max_dy', 'syn3', 'r_med'))
    for k, n, cab, mdy, mn, mx, ns, rm in info:
        print('  %4d %6d %9.1f %8.2f %8.1f %8.1f %6d %7.3f' % (k, n, cab, mdy, mn, mx, ns, rm))

# ================= build the mask =================
# Amy's partition: descending arbor = axon. Implement robustly:
# 1. seed = nodes strictly below the soma in y AND on the soma's graph component
# 2. take connected components of that descending sub-graph
# 3. keep components that attach near the soma (contain a node within ATTACH um
#    of the soma) or that are contiguous with a kept component
# 4. drop stray fragments (small cable)
print()
print('=' * 78)
print('C. MASK CONSTRUCTION')
print('=' * 78)
Y0 = 0.0          # soma y
desc = (dy < Y0) & inmain
ncd, ld = connected_components(A[desc][:, desc], directed=False)
labd = np.full(N, -1); labd[np.where(desc)[0]] = ld
print('descending (dy<0, on soma component) raw: %d nodes, %.1f um cable, %d pieces'
      % (desc.sum(), cable[desc].sum(), ncd))
pieces = []
for k in range(ncd):
    m = labd == k
    pieces.append((k, int(m.sum()), float(cable[m].sum()), float(de[m].min())))
pieces.sort(key=lambda r: -r[2])
print('  top descending pieces (id, nodes, cable_um, min_dist_to_soma_um):')
for p in pieces[:12]:
    print('    %4d %6d %9.1f %8.2f' % p)
ATTACH = 12.0
keep_k = [p[0] for p in pieces if p[3] <= ATTACH and p[2] >= 5.0]
print('  kept pieces (attach within %.0f um of soma AND >=5 um cable): %s' % (ATTACH, keep_k))
is_axon = np.isin(labd, keep_k)
print('AXON MASK: %d nodes, %.1f um cable' % (is_axon.sum(), cable[is_axon].sum()))

is_dend = inmain & ~is_axon & (de > 6.83)
print('DENDRITE (rest of soma component, outside soma sphere): %d nodes, %.1f um cable'
      % (is_dend.sum(), cable[is_dend].sum()))

# mean direction from soma, cable weighted, of the axon
vec = S[is_axon] - SOMA
u = vec / np.linalg.norm(vec, axis=1, keepdims=True)
mdir = (u * cable[is_axon][:, None]).sum(0) / cable[is_axon].sum()
mdir_n = mdir / np.linalg.norm(mdir)
print('axon mean unit direction from soma (OBJ x,y,z): [%.3f %.3f %.3f] (|.|=%.3f)'
      % (mdir_n[0], mdir_n[1], mdir_n[2], np.linalg.norm(mdir)))
print('axon centroid offset from soma (um): ', np.round((S[is_axon].mean(0) - SOMA) / 1000, 1))
print('axon max euclid extent from soma: %.1f um; max geodesic: %.1f um'
      % (de[is_axon].max(), gd[is_axon].max()))

# where does the axon attach?  walk from the nearest axon node toward the soma
ax_idx = np.where(is_axon)[0]
seed = ax_idx[np.argmin(de[ax_idx])]
print('closest axon node to soma: idx %d at %.2f um euclid, %.2f um geodesic, dy=%.2f'
      % (seed, de[seed], gd[seed], dy[seed]))
print('  local radius there r_p50=%.3f um' % r_p50[seed])
# nodes on the path soma->seed
dist2, pred2 = dijkstra(A, indices=ROOT, directed=False, return_predecessors=True)
path = []; j = seed
while j != ROOT and j >= 0:
    path.append(j); j = pred2[j]
path.append(ROOT); path = path[::-1]
print('  soma->axon path (%d nodes): idx / euclid_um / dy_um / r_p50_um' % len(path))
for j in path[:20]:
    print('     %5d  %6.2f  %7.2f  %6.3f' % (j, de[j], dy[j], r_p50[j]))

# ================= cross checks =================
print()
print('=' * 78)
print('D. CROSS CHECK 1 -- 128 outgoing synapses vs the partition')
print('=' * 78)
t_ax = cKDTree(S[is_axon]); t_de = cKDTree(S[is_dend])
d_ax, _ = t_ax.query(syn, k=1); d_ax /= 1000.
d_de, _ = t_de.query(syn, k=1); d_de /= 1000.
syn_dy = (syn[:, 1] - SOMA[1]) / 1000.
print('synapse dy (um) vs soma: below soma %d / 128, above %d / 128'
      % ((syn_dy < 0).sum(), (syn_dy >= 0).sum()))
print('nearer to an AXON node: %d / 128   nearer to a DENDRITE node: %d / 128'
      % ((d_ax < d_de).sum(), (d_ax >= d_de).sum()))
for thr in (1., 2., 3., 5.):
    a = (d_ax < thr).sum(); b = (d_de < thr).sum()
    both = ((d_ax < thr) & (d_de < thr)).sum()
    print('  within %.0f um: axon %3d, dendrite %3d, both %3d, neither %3d'
          % (thr, a, b, both, int(((d_ax >= thr) & (d_de >= thr)).sum())))
# unambiguous assignment: nearest node overall
tree_all = cKDTree(S); dall, iall = tree_all.query(syn, k=1); dall /= 1000.
n_ax = int(is_axon[iall].sum()); n_de = int(is_dend[iall].sum())
n_soma = int((~is_axon[iall] & ~is_dend[iall]).sum())
print('nearest-node assignment: axon %d, dendrite %d, soma/other %d (of 128)'
      % (n_ax, n_de, n_soma))
print('  of the %d dendrite-assigned: median dist %.2f um, their dy: %s'
      % (n_de, np.median(dall[is_dend[iall]]),
         np.array2string(np.sort(syn_dy[is_dend[iall]]), precision=1, max_line_width=200)))

print()
print('=' * 78)
print('E. CROSS CHECK 2 -- calibre / spininess distributions')
print('=' * 78)
from scipy.stats import mannwhitneyu
FMT = '%-11s %-4s n=%4d p10 %9.3f p25 %9.3f p50 %9.3f p75 %9.3f p90 %9.3f mean %10.3f'
for nm, x in [('r_p25', r_p25), ('r_p50', r_p50), ('r_p90', r_p90),
              ('vdens', vdens), ('adens', adens), ('adens_ratio', adens_ratio)]:
    a = x[is_axon]; a = a[np.isfinite(a)]
    b = x[is_dend]; b = b[np.isfinite(b)]
    print(FMT % ((nm, 'AXON', len(a)) + tuple(np.percentile(a, [10, 25, 50, 75, 90])) + (a.mean(),)))
    print(FMT % (('', 'DEND', len(b)) + tuple(np.percentile(b, [10, 25, 50, 75, 90])) + (b.mean(),)))
    u, pv = mannwhitneyu(a, b)
    print('%-11s %-4s AUC(dend > axon) %.3f   p=%.2e' % ('', '', 1 - u / (len(a) * len(b)), pv))

np.savez(r'D:\Meshes\skeletons\_partition.npz', is_axon=is_axon, is_dend=is_dend,
         dy=dy, de=de, gd=gd, labd=labd, inmain=inmain)
