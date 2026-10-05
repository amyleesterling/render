"""Step 10: terminal-branch statistics inside the descending arbor, then write
D:\\Meshes\\skeletons\\axon_mask.npz."""
import numpy as np, pandas as pd
from scipy.spatial import cKDTree
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components, dijkstra

sk = np.load(r'D:\Meshes\skeletons\648518346438632877.npz', allow_pickle=True)
S = sk['vertices'].astype(np.float64); E = sk['edges']; ROOT = int(sk['root'])
N = len(S); SOMA = S[ROOT]
MA = np.load(r'D:\Meshes\skeletons\_mesh_assign.npz')
in_dens = MA['in_dens']; inmain = MA['inmain']; de = MA['de']; dy = MA['dy']
n_in = MA['n_in']; n_mf = MA['n_mf']
M = np.load(r'D:\Meshes\skeletons\_node_metrics.npz')
cable = M['cable']; nvert = M['nvert']; area_node = M['area_node']
R = np.load(r'D:\Meshes\skeletons\_radius_slab.npz'); rad = R['rad_x']; rad90 = R['rad_x90']
HERO = 648518346438632877
df = pd.read_pickle(r'D:\Meshes\renders\hero_outgoing_requery.pkl')
true_out = np.vstack(df[df.post_pt_root_id != HERO]['ctr_pt_position'].values).astype(float)
auto_out = np.vstack(df[df.post_pt_root_id == HERO]['ctr_pt_position'].values).astype(float)
inc = np.load(r'D:\Meshes\renders\hero_incoming_raw.npy')
mfp = np.load(r'D:\Meshes\renders\hero_synapses.npy')

w = np.linalg.norm(S[E[:, 0]] - S[E[:, 1]], axis=1) / 1000.
A = coo_matrix((np.r_[w, w], (np.r_[E[:, 0], E[:, 1]], np.r_[E[:, 1], E[:, 0]])),
               shape=(N, N)).tocsr()
V = np.load(r'D:\Meshes\skeletons\_hero_verts.npy').astype(np.float64)
nov = np.load(r'D:\Meshes\skeletons\_hero_vert2node.npz')['node']
tv = cKDTree(V)
def to_node(p):
    _, i = tv.query(p, k=1, workers=-1); return nov[i]
nd_true = to_node(true_out); n_true = np.bincount(nd_true, minlength=N).astype(float)

# ---------- build the mask: topological descending arbor ----------
SH = 9.0
keep = (de >= SH) & inmain
idx = np.where(keep)[0]
nc, l = connected_components(A[keep][:, keep], directed=False)
lab = np.full(N, -1); lab[idx] = l
is_axon = np.zeros(N, bool)
kept, dropped = [], []
for k in range(nc):
    m = lab == k
    cab = cable[m].sum()
    if cab < 5: continue
    mdy = (dy[m] * cable[m]).sum() / cab
    (kept if mdy < 0 else dropped).append((k, int(m.sum()), cab, mdy))
    if mdy < 0: is_axon |= m
is_soma = inmain & (de < SH)
is_dend = inmain & ~is_axon & ~is_soma
print('=' * 96)
print('MASK: descending (Amy) arbor = union of soma-shell(R=9um) components with cable-weighted dy<0')
print('=' * 96)
print(' kept   (id, nodes, cable_um, mean_dy):', [(k, n, round(c, 1), round(d, 1)) for k, n, c, d in kept])
print(' dropped ascending:', [(k, n, round(c, 1), round(d, 1)) for k, n, c, d in dropped])
print('is_axon  : %4d nodes  %8.1f um cable' % (is_axon.sum(), cable[is_axon].sum()))
print('is_dend  : %4d nodes  %8.1f um cable' % (is_dend.sum(), cable[is_dend].sum()))
print('is_soma  : %4d nodes  %8.1f um cable' % (is_soma.sum(), cable[is_soma].sum()))
print('off-cell fragments (not on soma component): %d nodes %.1f um'
      % ((~inmain).sum(), cable[~inmain].sum()))
# agreement with the bare y-threshold
bare = inmain & (dy < 0) & (de >= SH)
print('agreement with bare y<0 threshold: %.1f%% of soma-component nodes (%d disagree)'
      % (100 * (is_axon[inmain & (de >= SH)] == bare[inmain & (de >= SH)]).mean(),
         int((is_axon != bare)[inmain & (de >= SH)].sum())))

# ---------- attachment ----------
gd, pred = dijkstra(A, indices=ROOT, directed=False, return_predecessors=True)
ax = np.where(is_axon)[0]
seed = ax[np.argmin(gd[ax])]
print('\nATTACHMENT: closest axon-mask node to soma = idx %d, geodesic %.2f um, euclid %.2f um, '
      'dy %+.2f, shaft radius %.3f um' % (seed, gd[seed], de[seed], dy[seed], rad[seed]))
print('  it is reached from the soma through nodes:',
      [int(x) for x in np.array([seed] + [])], '<- parent chain:',
      [int(pred[seed])], 'euclid %.2f um' % de[pred[seed]])
print('  => the descending arbor leaves the SOMA directly (its first node sits at %.1f um, '
      'i.e. just outside the %.2f um soma radius)' % (de[seed], 6.83))

# ---------- direction ----------
vec = S[is_axon] - SOMA
u = vec / np.linalg.norm(vec, axis=1, keepdims=True)
mdir = (u * cable[is_axon][:, None]).sum(0) / cable[is_axon].sum()
mdn = mdir / np.linalg.norm(mdir)
print('\nAXON mean direction from soma (cable-weighted unit vectors), OBJ (x,y,z):')
print('   raw mean [%+.3f %+.3f %+.3f]  |.|=%.3f   normalised [%+.3f %+.3f %+.3f]'
      % (*mdir, np.linalg.norm(mdir), *mdn))
print('   centroid offset from soma: [%+.1f %+.1f %+.1f] um' % tuple((S[is_axon].mean(0) - SOMA) / 1000))
print('   max euclid extent %.1f um, max geodesic %.1f um' % (de[is_axon].max(), gd[is_axon].max()))
vd = S[is_dend] - SOMA; ud = vd / np.linalg.norm(vd, axis=1, keepdims=True)
md2 = (ud * cable[is_dend][:, None]).sum(0) / cable[is_dend].sum()
print('   (dendrite arbor for contrast: [%+.3f %+.3f %+.3f])' % tuple(md2 / np.linalg.norm(md2)))

# ---------- cross checks ----------
print('\n' + '=' * 96)
print('CROSS CHECKS')
print('=' * 96)
def split(pts, nm):
    nd = to_node(pts)
    a = int(is_axon[nd].sum()); b = int(is_dend[nd].sum()); s = int(is_soma[nd].sum())
    o = len(pts) - a - b - s
    print('%-34s n=%5d | AXON(desc) %5d (%5.1f%%) | DEND(asc) %5d (%5.1f%%) | soma %4d | frag %d'
          % (nm, len(pts), a, 100 * a / len(pts), b, 100 * b / len(pts), s, o))
    return a, b
split(np.vstack([true_out, auto_out]), 'all 128 CAVE "outgoing"')
a1, b1 = split(true_out, '  40 genuine outgoing (post!=hero)')
split(auto_out, '  88 autapse rows (post==hero)')
split(inc, '6293 incoming (postsynaptic)')
split(mfp, '165 mossy-fibre inputs')
print('\nDensity per um cable: axon %.0f um, dendrite %.0f um' % (cable[is_axon].sum(), cable[is_dend].sum()))
print('  genuine outgoing: axon %.4f /um   dendrite %.4f /um' % (a1 / cable[is_axon].sum(), b1 / cable[is_dend].sum()))
print('  incoming        : axon %.3f /um   dendrite %.3f /um'
      % (n_in[is_axon].sum() / cable[is_axon].sum(), n_in[is_dend].sum() / cable[is_dend].sum()))

print('\nCALIBRE (slab cross-section, p20 of in-plane mesh distance) um:')
for nm, m in [('AXON (descending)', is_axon), ('DEND (ascending)', is_dend)]:
    v = rad[m]; v = v[np.isfinite(v)]
    print('  %-20s n=%4d  p5 %.3f p10 %.3f p25 %.3f p50 %.3f p75 %.3f p90 %.3f p95 %.3f mean %.3f'
          % ((nm, len(v)) + tuple(np.percentile(v, [5, 10, 25, 50, 75, 90, 95])) + (v.mean(),)))
print('SPININESS (slab p90 / slab p20):')
for nm, m in [('AXON (descending)', is_axon), ('DEND (ascending)', is_dend)]:
    v = (rad90 / rad)[m]; v = v[np.isfinite(v)]
    print('  %-20s n=%4d  p10 %.2f p25 %.2f p50 %.2f p75 %.2f p90 %.2f'
          % ((nm, len(v)) + tuple(np.percentile(v, [10, 25, 50, 75, 90]))))
print('SURFACE AREA per um cable (um^2/um):')
for nm, m in [('AXON (descending)', is_axon), ('DEND (ascending)', is_dend)]:
    print('  %-20s %.2f' % (nm, area_node[m].sum() / cable[m].sum()))

# ---------- terminal-branch table inside each arbor ----------
print('\n' + '=' * 96)
print('TERMINAL-BRANCH INPUT DENSITY: is any descending branch a genuine (input-free) axon?')
print('=' * 96)
deg = np.bincount(np.r_[E[:, 0], E[:, 1]], minlength=N)
bp = (deg >= 3) | (de < SH)
for nm, mask in [('DESCENDING', is_axon), ('ASCENDING', is_dend)]:
    mm = mask & ~bp
    idx3 = np.where(mm)[0]
    nc3, l3 = connected_components(A[mm][:, mm], directed=False)
    rec = []
    for k in range(nc3):
        b = np.zeros(N, bool); b[idx3[l3 == k]] = True
        cab = cable[b].sum()
        if cab < 8: continue
        rec.append((n_in[b].sum() / cab, cab, float(np.nanmedian(rad[b])),
                    float(np.nanmedian((rad90 / rad)[b])), n_true[b].sum(), float(dy[b].mean())))
    rec.sort()
    d = np.array([r[0] for r in rec])
    print('%s: %d branches >=8um. in/um: min %.3f p10 %.2f p25 %.2f p50 %.2f p75 %.2f max %.2f'
          % (nm, len(rec), d.min(), *np.percentile(d, [10, 25, 50, 75]), d.max()))
    print('   3 quietest branches (in/um, cable, rad, spininess, n_out, mean_dy):')
    for r in rec[:3]:
        print('      %.3f  %6.1f um  %.3f  %.2f  %.0f  %+.1f' % r)

# ---------- write ----------
strict = is_axon & (rad < 0.5) & (in_dens < 0.5)
np.savez_compressed(
    r'D:\Meshes\skeletons\axon_mask.npz',
    is_axon=is_axon, is_dendrite=is_dend, is_soma=is_soma, on_soma_component=inmain,
    is_axon_strict_thin_inputfree=strict,
    method=np.array(
        'PARTITION FROM CO-AUTHOR HAND MARKUP (Amy Sterling): the entire descending arbor '
        'below the soma = axon for the action-potential animation; the ascending apical arbor '
        'is excluded. Implemented topologically, not as a bare y threshold: cut a sphere of '
        'R=9um around the soma node 3202 (soma radius 6.83um), take connected components of the '
        'remainder on the soma graph component, keep every component with >=5um cable whose '
        'cable-weighted mean (y - soma_y) is negative. My own measurements were the CROSS CHECK, '
        'not the decision. They CONFIRM the axis (all 165 mossy-fibre inputs are above the soma) '
        'and confirm the descending set is thinner and smoother, but they CONTRADICT the claim '
        'that this set is pure axon: it carries 1573 postsynaptic inputs at 1.02/um and is spiny. '
        'The genuinely axonal-looking cable is a ~71um sub-branch inside it (see '
        'is_axon_strict_thin_inputfree). Treat is_axon as "the descending arbor the AP should '
        'travel down", not as a verified anatomical axon.'),
    method_short=np.array('hand-markup descending/ascending partition, topological soma-shell implementation'),
    seg_id=np.array('648518346438632877'),
    soma_node=np.array(ROOT), soma_xyz_nm=SOMA, soma_radius_um=np.array(6.83),
    coordinate_space=np.array('OBJ file space, nanometres, no transform applied'),
    # per-node quantities
    cable_um=cable, dist_soma_um=de, geodesic_soma_um=gd, dy_um=dy, degree=deg,
    radius_um=rad, radius_p50_um=R['rad_x50'], radius_p90_um=rad90,
    spininess=rad90 / rad,
    radius_nn_p25_um=M['r_p25'], radius_nn_p50_um=M['r_p50'],
    vertex_count=nvert, vertex_density_per_um=nvert / np.maximum(cable, 1e-3),
    surface_area_um2=area_node, area_density_um2_per_um=area_node / np.maximum(cable, 1e-3),
    n_incoming_syn=n_in, n_mf_syn=n_mf, n_true_outgoing_syn=n_true,
    incoming_density_per_um_8um_window=in_dens,
)
print('\nWROTE D:\\Meshes\\skeletons\\axon_mask.npz  (is_axon: %d True / %d)'
      % (is_axon.sum(), N))
