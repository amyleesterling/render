"""Step 6: mesh-accurate synapse assignment, primary-process characterisation,
and a direct hunt for a smooth low-input branch (the real axon)."""
import numpy as np
from scipy.spatial import cKDTree
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components, dijkstra

sk = np.load(r'D:\Meshes\skeletons\648518346438632877.npz', allow_pickle=True)
S = sk['vertices'].astype(np.float64); E = sk['edges']; ROOT = int(sk['root'])
N = len(S); SOMA = S[ROOT]
M = np.load(r'D:\Meshes\skeletons\_node_metrics.npz')
cable = M['cable']; r_p25 = M['r_p25']; r_p50 = M['r_p50']
V = np.load(r'D:\Meshes\skeletons\_hero_verts.npy').astype(np.float64)
vn = np.load(r'D:\Meshes\skeletons\_hero_vert2node.npz'); node_of_vert = vn['node']
inc = np.load(r'D:\Meshes\renders\hero_incoming_raw.npy')
out = np.load(r'D:\Meshes\renders\hero_outgoing.npy')
mf = np.load(r'D:\Meshes\renders\hero_synapses.npy')

tv = cKDTree(V)
def mesh_assign(pts, nm):
    d, iv = tv.query(pts, k=1, workers=-1); d /= 1000.
    node = node_of_vert[iv]
    print('%-9s n=%5d  dist to hero MESH um: p50 %.3f p90 %.3f p99 %.3f max %.3f  (>1um: %d)'
          % (nm, len(pts), *np.percentile(d, [50, 90, 99, 100]), int((d > 1).sum())))
    return d, node
print('=' * 88)
print('H. MESH-ACCURATE ASSIGNMENT (synapse -> nearest hero mesh vertex -> its skeleton node)')
print('=' * 88)
d_in, nd_in = mesh_assign(inc, 'INCOMING')
d_out, nd_out = mesh_assign(out, 'OUTGOING')
d_mf, nd_mf = mesh_assign(mf, 'MF-INPUT')

# per-node synapse counts, mesh-accurate
n_in = np.bincount(nd_in, minlength=N).astype(float)
n_out = np.bincount(nd_out, minlength=N).astype(float)
n_mf = np.bincount(nd_mf, minlength=N).astype(float)

w = np.linalg.norm(S[E[:, 0]] - S[E[:, 1]], axis=1) / 1000.
A = coo_matrix((np.r_[w, w], (np.r_[E[:, 0], E[:, 1]], np.r_[E[:, 1], E[:, 0]])),
               shape=(N, N)).tocsr()
gd = dijkstra(A, indices=ROOT, directed=False); inmain = np.isfinite(gd)
de = np.linalg.norm(S - SOMA, axis=1) / 1000.
dy = (S[:, 1] - SOMA[1]) / 1000.

WIN = 8.0
D = dijkstra(A, directed=False, limit=WIN); win = np.isfinite(D)
cab_win = win @ cable
in_dens = (win @ n_in) / np.maximum(cab_win, 1.0)
out_dens = (win @ n_out) / np.maximum(cab_win, 1.0)

print('\n' + '=' * 88)
print('I. PRIMARY PROCESSES OFF THE SOMA (sphere cut R=10 um), with INPUT density')
print('=' * 88)
for R in (10., 14.):
    keep = (de >= R) & inmain
    nc, l2 = connected_components(A[keep][:, keep], directed=False)
    lab = np.full(N, -1); lab[np.where(keep)[0]] = l2
    rows = []
    for k in range(nc):
        m = lab == k
        cab = cable[m].sum()
        if cab < 3: continue
        rows.append((k, int(m.sum()), cab, float((dy[m] * cable[m]).sum() / cab),
                     n_in[m].sum(), n_in[m].sum() / cab, n_out[m].sum(), n_mf[m].sum(),
                     float(np.nanmedian(r_p25[m])), float(de[m].max())))
    rows.sort(key=lambda r: -r[2])
    print('\n-- R=%.0f um --' % R)
    print(' %4s %6s %9s %8s %7s %9s %6s %5s %7s %7s' %
          ('id', 'nodes', 'cable_um', 'mean_dy', 'n_in', 'in/um', 'n_out', 'n_mf', 'r25med', 'maxext'))
    for r in rows:
        print(' %4d %6d %9.1f %8.2f %7.0f %9.3f %6.0f %5.0f %7.3f %7.1f' % r)

print('\n' + '=' * 88)
print('J. HUNT: connected stretches of cable with essentially NO input synapses')
print('=' * 88)
for thr in (0.02, 0.05, 0.1, 0.25, 0.5):
    m = inmain & (in_dens < thr) & (de > 8)
    if m.sum() < 2: continue
    ncq, lq = connected_components(A[m][:, m], directed=False)
    idx = np.where(m)[0]
    best = []
    for k in range(ncq):
        mm = np.zeros(N, bool); mm[idx[lq == k]] = True
        best.append((cable[mm].sum(), int(mm.sum()), float(dy[mm].mean()),
                     float(np.nanmedian(r_p25[mm])), float(n_out[mm].sum()),
                     float(de[mm].min()), float(de[mm].max())))
    best.sort(reverse=True)
    print('in_dens<%-5.2f total %6.1f um in %3d pieces; largest pieces '
          '(cable, nodes, meandy, r25, n_out, minR, maxR):' % (thr, cable[m].sum(), ncq))
    for b in best[:4]:
        print('      %7.1f %5d %+8.1f %6.3f %5.0f %7.1f %7.1f' % b)

print('\n' + '=' * 88)
print('K. ARE THE 128 "OUTGOING" JUST POLARITY-FLIPPED INPUTS?')
print('=' * 88)
# spatial similarity of the two point clouds
for nm, arr, nd in [('INCOMING', inc, nd_in), ('OUTGOING', out, nd_out)]:
    v = in_dens[nd]
    print('%-9s in_dens(8um window) at own location: p10 %.2f p25 %.2f p50 %.2f p75 %.2f p90 %.2f'
          % ((nm,) + tuple(np.percentile(v, [10, 25, 50, 75, 90]))))
    print('%-9s local shaft radius r_p25 at own location: p25 %.3f p50 %.3f p75 %.3f'
          % ((nm,) + tuple(np.nanpercentile(r_p25[nd], [25, 50, 75]))))
# nearest-neighbour distance from each outgoing to the nearest incoming
ti = cKDTree(inc)
dd, _ = ti.query(out, k=1); dd /= 1000.
print('outgoing -> nearest INCOMING synapse (um): p10 %.2f p25 %.2f p50 %.2f p75 %.2f max %.2f'
      % tuple(np.percentile(dd, [10, 25, 50, 75, 100])))
# control: incoming -> nearest other incoming
dd2, _ = ti.query(inc, k=2); dd2 = dd2[:, 1] / 1000.
print('incoming -> nearest other INCOMING (um):  p10 %.2f p25 %.2f p50 %.2f p75 %.2f'
      % tuple(np.percentile(dd2, [10, 25, 50, 75])))
print('outgoing within 1 um of an incoming synapse: %d / 128' % int((dd < 1).sum()))
print('outgoing within 0.3 um of an incoming synapse: %d / 128' % int((dd < 0.3).sum()))

np.savez(r'D:\Meshes\skeletons\_mesh_assign.npz', n_in=n_in, n_out=n_out, n_mf=n_mf,
         in_dens=in_dens, out_dens=out_dens, cab_win=cab_win, gd=gd, de=de, dy=dy,
         inmain=inmain, nd_in=nd_in, nd_out=nd_out, nd_mf=nd_mf)
