"""Step 3: diagnose the parent tree, build a clean BFS tree from soma,
enumerate soma child subtrees with per-subtree stats."""
import numpy as np
from scipy.spatial import cKDTree
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components, dijkstra, breadth_first_order

sk = np.load(r'D:\Meshes\skeletons\648518346438632877.npz', allow_pickle=True)
S = sk['vertices'].astype(np.float64); E = sk['edges']; PAR = sk['parent']
ROOT = int(sk['root']); N = len(S); SOMA = S[ROOT]
M = np.load(r'D:\Meshes\skeletons\_node_metrics.npz')
gdist = M['gdist']; cable = M['cable']; r_p50 = M['r_p50']; r_p25 = M['r_p25']
syn = np.load(r'D:\Meshes\renders\hero_outgoing.npy')

# ---------- 1. is the supplied parent array a valid tree rooted at ROOT? ----------
print('=== parent-array diagnosis ===')
print('parent == -1 count:', (PAR < 0).sum())
reach = np.zeros(N, bool)
steps = np.full(N, -1)
for i in range(N):
    path = []
    j = i; n = 0
    seen = set()
    while j >= 0 and j not in seen and n < 20000:
        seen.add(j); path.append(j)
        if j == ROOT:
            reach[i] = True; break
        j = PAR[j]; n += 1
    steps[i] = len(path)
print('nodes whose parent-walk reaches ROOT: %d / %d (%.1f%%)' %
      (reach.sum(), N, 100 * reach.mean()))
print('nodes in soma GRAPH component: %d (%.1f%%)' %
      (np.isfinite(gdist).sum(), 100 * np.isfinite(gdist).mean()))
print('=> in-component but NOT parent-reachable: %d' %
      int((np.isfinite(gdist) & ~reach).sum()))
# is parent consistent with edges?
ok = 0; bad = 0
eset = set(map(tuple, np.sort(E, axis=1)))
for i in range(N):
    if PAR[i] >= 0:
        if tuple(sorted((i, int(PAR[i])))) in eset: ok += 1
        else: bad += 1
print('parent links that are real edges: %d, that are NOT: %d' % (ok, bad))
# does parent point away from soma?
pv = PAR >= 0
mono = np.isfinite(gdist[np.where(pv)[0]]) & np.isfinite(gdist[PAR[pv]])
sel = np.where(pv)[0][mono]
print('parent-links where parent is FARTHER from soma (inverted): %d / %d' %
      int((gdist[PAR[sel]] > gdist[sel] + 1e-9).sum()), len(sel))

# ---------- 2. reproduce the failed method ----------
w = np.linalg.norm(S[E[:, 0]] - S[E[:, 1]], axis=1) / 1000.0
A = coo_matrix((np.r_[w, w], (np.r_[E[:, 0], E[:, 1]], np.r_[E[:, 1], E[:, 0]])),
               shape=(N, N)).tocsr()
tree_s = cKDTree(S)
ds, isyn = tree_s.query(syn, k=1); ds /= 1000.
union = set()
for s0 in isyn:
    j = int(s0); seen = set()
    while j >= 0 and j not in seen:
        seen.add(j); union.add(j)
        if j == ROOT: break
        j = int(PAR[j])
old = np.zeros(N, bool); old[list(union)] = True
print('\nold method (parent-walk union) node count:', old.sum())
print('  of those, fraction with r_p50 > 1um: %.2f' %
      np.nanmean(r_p50[old] > 1.0))
print('  bbox of old mask (um):',
      np.round((S[old].max(0) - S[old].min(0)) / 1000, 1))

# ---------- 3. clean BFS/geodesic tree from soma ----------
dist, pred = dijkstra(A, indices=ROOT, directed=False, return_predecessors=True)
inmain = np.isfinite(dist)
print('\n=== soma shell / subtree enumeration ===')
SOMA_R = 6.83
# children subtrees: remove all nodes with euclid dist to soma < SOMA_R,
# then connected components of the rest that touch the shell
de = np.linalg.norm(S - SOMA, axis=1) / 1000.
print('nodes inside soma sphere (%.2f um): %d' % (SOMA_R, (de < SOMA_R).sum()))
keep = (de >= SOMA_R) & inmain
sub = A[keep][:, keep]
nc, l2 = connected_components(sub, directed=False)
idxkeep = np.where(keep)[0]
lab_full = np.full(N, -1); lab_full[idxkeep] = l2
print('subtrees beyond soma shell:', nc)

rows = []
for k in range(nc):
    m = lab_full == k
    n = m.sum()
    cab = cable[m].sum()
    # synapses within 3 um of any node of this subtree
    t = cKDTree(S[m])
    dsy, _ = t.query(syn, k=1)
    nsyn3 = int((dsy / 1000. < 3).sum())
    # mean direction from soma weighted by cable
    vec = (S[m] - SOMA)
    u = vec / np.linalg.norm(vec, axis=1, keepdims=True)
    mdir = (u * cable[m][:, None]).sum(0) / max(cable[m].sum(), 1e-9)
    rr = r_p50[m]; rr = rr[np.isfinite(rr)]
    r25 = r_p25[m]; r25 = r25[np.isfinite(r25)]
    rows.append(dict(k=k, n=n, cable=cab,
                     r_mean=float(np.nanmean(rr)) if len(rr) else np.nan,
                     r_med=float(np.nanmedian(rr)) if len(rr) else np.nan,
                     r25_med=float(np.nanmedian(r25)) if len(r25) else np.nan,
                     nsyn3=nsyn3, dir=mdir,
                     maxd=float(dist[m].max()),
                     centroid=(S[m].mean(0) - SOMA) / 1000.))
rows.sort(key=lambda r: -r['cable'])
print('%3s %6s %9s %7s %7s %7s %6s  %-22s %-24s %7s' %
      ('id', 'nodes', 'cable_um', 'rmean', 'rmed', 'r25med', 'syn3', 'mean_dir(x,y,z)', 'centroid_off_um', 'maxgeo'))
for r in rows:
    print('%3d %6d %9.1f %7.3f %7.3f %7.3f %6d  [%6.2f %6.2f %6.2f]  [%7.1f %7.1f %7.1f] %7.1f' %
          (r['k'], r['n'], r['cable'], r['r_mean'], r['r_med'], r['r25_med'], r['nsyn3'],
           r['dir'][0], r['dir'][1], r['dir'][2],
           r['centroid'][0], r['centroid'][1], r['centroid'][2], r['maxd']))
np.savez(r'D:\Meshes\skeletons\_subtrees.npz', lab_full=lab_full, de=de,
         dist=dist, pred=pred, old=old, isyn=isyn, ds=ds)
