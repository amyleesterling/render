"""Step 5: the decisive test. Incoming synapse density (dendritic marker)
vs outgoing synapse density (axonal marker) over the descending / ascending split."""
import numpy as np
from scipy.spatial import cKDTree
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components, dijkstra

sk = np.load(r'D:\Meshes\skeletons\648518346438632877.npz', allow_pickle=True)
S = sk['vertices'].astype(np.float64); E = sk['edges']; ROOT = int(sk['root'])
N = len(S); SOMA = S[ROOT]
M = np.load(r'D:\Meshes\skeletons\_node_metrics.npz')
cable = M['cable']; r_p25 = M['r_p25']; r_p50 = M['r_p50']
P = np.load(r'D:\Meshes\skeletons\_partition.npz')
is_axon = P['is_axon']; is_dend = P['is_dend']; dy = P['dy']; de = P['de']; inmain = P['inmain']

inc = np.load(r'D:\Meshes\renders\hero_incoming_raw.npy')      # 6293 postsynaptic
out = np.load(r'D:\Meshes\renders\hero_outgoing.npy')          # 128 presynaptic
mf = np.load(r'D:\Meshes\renders\hero_synapses.npy')           # 165 mossy fibre inputs

tree = cKDTree(S)
def assign(pts, name):
    d, i = tree.query(pts, k=1); d /= 1000.
    print('%-10s n=%5d  dist-to-skeleton um p50 %.2f p90 %.2f; below/above soma-y %d/%d'
          % (name, len(pts), np.median(d), np.percentile(d, 90),
             int((pts[:, 1] < SOMA[1]).sum()), int((pts[:, 1] >= SOMA[1]).sum())))
    return d, i

print('=' * 84)
print('F. DECISIVE TEST -- 6293 INCOMING (postsynaptic = must be dendrite) vs')
print('   128 OUTGOING (presynaptic = must be axon), over the descending/ascending split')
print('=' * 84)
d_in, i_in = assign(inc, 'INCOMING')
d_out, i_out = assign(out, 'OUTGOING')
d_mf, i_mf = assign(mf, 'MF-INPUT')

for nm, d, i in [('INCOMING (6293)', d_in, i_in), ('OUTGOING (128)', d_out, i_out),
                 ('MF INPUT (165)', d_mf, i_mf)]:
    ok = d < 3.0
    a = int(is_axon[i][ok].sum()); b = int(is_dend[i][ok].sum())
    o = int(ok.sum()) - a - b
    print('%-16s within 3um of skeleton: %5d | DESCENDING %5d (%5.1f%%) | ASCENDING %5d (%5.1f%%) | soma %d'
          % (nm, ok.sum(), a, 100 * a / max(ok.sum(), 1), b, 100 * b / max(ok.sum(), 1), o))

# --- density per um cable ---
cab_ax = cable[is_axon].sum(); cab_de = cable[is_dend].sum()
print('\ncable: descending %.0f um, ascending %.0f um' % (cab_ax, cab_de))
for nm, d, i in [('INCOMING', d_in, i_in), ('OUTGOING', d_out, i_out)]:
    ok = d < 3.0
    a = int(is_axon[i][ok].sum()); b = int(is_dend[i][ok].sum())
    print('%-9s density: descending %.3f /um   ascending %.3f /um   ratio asc/desc %.2f'
          % (nm, a / cab_ax, b / cab_de, (b / cab_de) / max(a / cab_ax, 1e-9)))

# ---------------- per-node synapse counts, then find the truly axonal cable ----------
def counts(pts, rad_um=2.0):
    t = cKDTree(pts)
    return np.array([len(t.query_ball_point(S[j], rad_um * 1000)) for j in range(N)])
n_in = counts(inc); n_out = counts(out)
np.savez(r'D:\Meshes\skeletons\_syncounts.npz', n_in=n_in, n_out=n_out)

print('\n' + '=' * 84)
print('G. IS THERE A SUB-BRANCH THAT IS SYNAPSE-FREE AND THIN?  (true axon signature)')
print('=' * 84)
# smooth the incoming count along cable: for each node sum incoming within 5 um cable window
w = np.linalg.norm(S[E[:, 0]] - S[E[:, 1]], axis=1) / 1000.
A = coo_matrix((np.r_[w, w], (np.r_[E[:, 0], E[:, 1]], np.r_[E[:, 1], E[:, 0]])),
               shape=(N, N)).tocsr()
D = dijkstra(A, directed=False, limit=5.0)
win = np.isfinite(D)
in_win = (win * n_in[None, :]).sum(1)
out_win = (win * n_out[None, :]).sum(1)
cab_win = (win * cable[None, :]).sum(1)
in_dens = in_win / np.maximum(cab_win, 0.5)
out_dens = out_win / np.maximum(cab_win, 0.5)
np.savez(r'D:\Meshes\skeletons\_dens.npz', in_dens=in_dens, out_dens=out_dens,
         in_win=in_win, out_win=out_win, cab_win=cab_win)

print('in_dens (incoming synapses per um cable, 5um window) percentiles over soma component:')
x = in_dens[inmain]
print('   ' + ' '.join('p%d=%.2f' % (p, v) for p, v in zip([1, 5, 10, 25, 50, 75, 90, 99],
                                                           np.percentile(x, [1, 5, 10, 25, 50, 75, 90, 99]))))
for thr in (0.05, 0.1, 0.2, 0.3, 0.5):
    m = inmain & (in_dens < thr) & (de > 8)
    if m.sum() == 0: continue
    o = int(n_out[m].sum())
    print('  in_dens < %.2f : %4d nodes, %7.1f um cable, outgoing syn on them %3d, median r_p25 %.3f, mean dy %+.1f'
          % (thr, m.sum(), cable[m].sum(), o, np.nanmedian(r_p25[m]), (dy[m] * cable[m]).sum() / max(cable[m].sum(), 1e-9)))

# split by descending / ascending
print('\nlow-input cable (in_dens<0.2) split by side:')
m = inmain & (in_dens < 0.2) & (de > 8)
print('  descending: %d nodes %.1f um; ascending: %d nodes %.1f um'
      % ((m & is_axon).sum(), cable[m & is_axon].sum(),
         (m & is_dend).sum(), cable[m & is_dend].sum()))

# where are the 128 outgoing, by in_dens of their nearest node?
print('\n128 outgoing synapses, in_dens at their nearest node:')
v = in_dens[i_out]
print('   ' + ' '.join('p%d=%.2f' % (p, q) for p, q in zip([0, 10, 25, 50, 75, 90, 100],
                                                           np.percentile(v, [0, 10, 25, 50, 75, 90, 100]))))
print('   outgoing on cable with in_dens<0.2: %d / 128' % int((v < 0.2).sum()))
print('   6293 incoming, in_dens at nearest node p50 %.2f' % np.median(in_dens[i_in]))
