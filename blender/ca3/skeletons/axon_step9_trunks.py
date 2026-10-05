"""Step 9: enumerate the trunks crossing a shell around the soma, and score each
downstream subtree for axon-ness (calibre, input density, spininess)."""
import numpy as np
from scipy.spatial import cKDTree
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components, dijkstra

sk = np.load(r'D:\Meshes\skeletons\648518346438632877.npz', allow_pickle=True)
S = sk['vertices'].astype(np.float64); E = sk['edges']; ROOT = int(sk['root'])
N = len(S); SOMA = S[ROOT]
MA = np.load(r'D:\Meshes\skeletons\_mesh_assign.npz')
in_dens = MA['in_dens']; inmain = MA['inmain']; de = MA['de']; dy = MA['dy']
n_in = MA['n_in']; n_out = MA['n_out']; n_mf = MA['n_mf']
M = np.load(r'D:\Meshes\skeletons\_node_metrics.npz'); cable = M['cable']
R = np.load(r'D:\Meshes\skeletons\_radius_slab.npz')
rad = R['rad_x']; rad90 = R['rad_x90']
import pandas as pd
HERO = 648518346438632877
df = pd.read_pickle(r'D:\Meshes\renders\hero_outgoing_requery.pkl')
true_out = np.vstack(df[df.post_pt_root_id != HERO]['ctr_pt_position'].values).astype(float)

w = np.linalg.norm(S[E[:, 0]] - S[E[:, 1]], axis=1) / 1000.
A = coo_matrix((np.r_[w, w], (np.r_[E[:, 0], E[:, 1]], np.r_[E[:, 1], E[:, 0]])),
               shape=(N, N)).tocsr()
V = np.load(r'D:\Meshes\skeletons\_hero_verts.npy').astype(np.float64)
vn = np.load(r'D:\Meshes\skeletons\_hero_vert2node.npz'); nov = vn['node']
tv = cKDTree(V)
_, iv = tv.query(true_out, k=1, workers=-1); nd_true = nov[iv]
n_true = np.bincount(nd_true, minlength=N).astype(float)

SH = 9.0
print('=' * 100)
print('N. TRUNKS CROSSING THE SHELL AT R = %.1f um (soma radius 6.83 um)' % SH)
print('=' * 100)
keep = (de >= SH) & inmain
idx = np.where(keep)[0]
nc, l = connected_components(A[keep][:, keep], directed=False)
lab = np.full(N, -1); lab[idx] = l
rows = []
for k in range(nc):
    m = lab == k
    cab = cable[m].sum()
    if cab < 2: continue
    prox = np.where(m)[0][np.argmin(de[m])]        # node closest to soma = trunk origin
    v = S[prox] - SOMA; v /= np.linalg.norm(v)
    rows.append(dict(k=k, n=int(m.sum()), cab=cab, prox=int(prox),
                     rad_prox=float(np.nanmedian(rad[m & (de < 15)])) if (m & (de < 15)).sum() else np.nan,
                     rad=float(np.nanmedian(rad[m])),
                     spin=float(np.nanmedian(rad90[m] / rad[m])),
                     nin=n_in[m].sum(), indens=n_in[m].sum() / cab,
                     nmf=n_mf[m].sum(), ntrue=n_true[m].sum(),
                     dyv=float((dy[m] * cable[m]).sum() / cab), dirv=v,
                     maxR=float(de[m].max())))
rows.sort(key=lambda r: -r['cab'])
print('%3s %6s %9s %8s %8s %8s %7s %8s %6s %6s %7s  %-20s' %
      ('id', 'nodes', 'cable_um', 'rad_prox', 'rad_med', 'spinines', 'n_in', 'in/um',
       'n_mf', 'n_out', 'mean_dy', 'unit dir from soma'))
for r in rows:
    print('%3d %6d %9.1f %8.3f %8.3f %8.2f %7.0f %8.3f %6.0f %6.0f %+7.1f  [%+.2f %+.2f %+.2f]' %
          (r['k'], r['n'], r['cab'], r['rad_prox'], r['rad'], r['spin'], r['nin'],
           r['indens'], r['nmf'], r['ntrue'], r['dyv'],
           r['dirv'][0], r['dirv'][1], r['dirv'][2]))

# split the big descending trunk into its own sub-branches at R=25
print('\n' + '=' * 100)
print('O. INSIDE THE DESCENDING ARBOR: sub-branches at R = 25 um')
print('=' * 100)
big = max([r for r in rows if r['dyv'] < 0], key=lambda r: r['cab'])
mbig = lab == big['k']
keep2 = mbig & (de >= 25)
idx2 = np.where(keep2)[0]
nc2, l2 = connected_components(A[keep2][:, keep2], directed=False)
rows2 = []
for k in range(nc2):
    m = np.zeros(N, bool); m[idx2[l2 == k]] = True
    cab = cable[m].sum()
    if cab < 5: continue
    rows2.append((cab, int(m.sum()), float(np.nanmedian(rad[m])),
                  float(np.nanmedian(rad90[m] / rad[m])), n_in[m].sum(),
                  n_in[m].sum() / cab, n_true[m].sum(), float(dy[m].mean()), float(de[m].max())))
rows2.sort(reverse=True)
print('%9s %6s %8s %8s %7s %8s %6s %8s %7s' %
      ('cable_um', 'nodes', 'rad_med', 'spinines', 'n_in', 'in/um', 'n_out', 'mean_dy', 'maxR'))
for r in rows2:
    print('%9.1f %6d %8.3f %8.2f %7.0f %8.3f %6.0f %+8.1f %7.1f' % r)

print('\n' + '=' * 100)
print('P. REFERENCE: what an axon should look like -- the 6 mossy fibres in this folder')
print('=' * 100)
import glob, os
for f in sorted(glob.glob(r'D:\Meshes\skeletons\6485*.npz')):
    if '_cave' in f or '_meshparty' in f: continue
    zz = np.load(f, allow_pickle=True)
    sv = zz['vertices']; se = zz['edges']
    L = (np.linalg.norm(sv[se[:, 0]] - sv[se[:, 1]], axis=1) / 1000.).sum()
    print('  %-22s %5d nodes, %7.1f um cable' % (os.path.basename(f)[:18], len(sv), L))
