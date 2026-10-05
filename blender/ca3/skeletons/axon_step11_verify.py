import numpy as np, matplotlib, pandas as pd
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection

Z = np.load(r'D:\Meshes\skeletons\axon_mask.npz', allow_pickle=True)
print('keys:', sorted(Z.files))
is_axon = Z['is_axon']; is_dend = Z['is_dendrite']; is_soma = Z['is_soma']
print('is_axon dtype %s len %d True %d' % (is_axon.dtype, len(is_axon), is_axon.sum()))
sk = np.load(r'D:\Meshes\skeletons\648518346438632877.npz', allow_pickle=True)
S = sk['vertices']; E = sk['edges']; SOMA = S[int(sk['root'])]
X = (S[:, 0] - SOMA[0]) / 1000.; Y = (S[:, 1] - SOMA[1]) / 1000.; Zc = (S[:, 2] - SOMA[2]) / 1000.
inc = (np.load(r'D:\Meshes\renders\hero_incoming_raw.npy') - SOMA) / 1000.
mfp = (np.load(r'D:\Meshes\renders\hero_synapses.npy') - SOMA) / 1000.
HERO = 648518346438632877
df = pd.read_pickle(r'D:\Meshes\renders\hero_outgoing_requery.pkl')
to = (np.vstack(df[df.post_pt_root_id != HERO]['ctr_pt_position'].values).astype(float) - SOMA) / 1000.

col = np.where(is_axon[E[:, 0]] & is_axon[E[:, 1]], '#e31a1c',
      np.where(is_soma[E[:, 0]] | is_soma[E[:, 1]], '#33a02c', '#1f78b4'))
fig, axs = plt.subplots(1, 3, figsize=(21, 8))
for ax, (a, b, la, lb) in zip(axs, [(X, Y, 'OBJ x', 'OBJ y  (up in frame)'),
                                    (Zc, Y, 'OBJ z', 'OBJ y  (up in frame)'),
                                    (X, Zc, 'OBJ x', 'OBJ z')]):
    seg = np.stack([np.c_[a[E[:, 0]], b[E[:, 0]]], np.c_[a[E[:, 1]], b[E[:, 1]]]], axis=1)
    ax.add_collection(LineCollection(seg, colors=col, linewidths=0.9))
    ax.plot(0, 0, 'k*', ms=20, zorder=6)
    ax.set_aspect('equal'); ax.set_xlabel(la + ' - soma (um)'); ax.set_ylabel(lb + ' - soma (um)')
    ax.set_xlim(a.min() - 5, a.max() + 5); ax.set_ylim(b.min() - 5, b.max() + 5)
axs[0].scatter(mfp[:, 0], mfp[:, 1], s=10, c='magenta', zorder=5, label='165 mossy-fibre INPUTS')
axs[0].scatter(to[:, 0], to[:, 1], s=40, c='k', marker='v', zorder=5, label='40 genuine outgoing')
axs[0].legend(fontsize=9, loc='lower left')
axs[0].set_title('AXON MASK (red = is_axon, green = soma, blue = dendrite)')
axs[1].set_title('side view')
axs[2].set_title('top view')
plt.tight_layout(); plt.savefig(r'D:\Meshes\skeletons\_axon_mask_verify.png', dpi=95)
print('saved')
# fragment / continuity check
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
w = np.linalg.norm(S[E[:, 0]] - S[E[:, 1]], axis=1) / 1000.
N = len(S)
A = coo_matrix((np.r_[w, w], (np.r_[E[:, 0], E[:, 1]], np.r_[E[:, 1], E[:, 0]])), shape=(N, N)).tocsr()
nc, l = connected_components(A[is_axon][:, is_axon], directed=False)
idx = np.where(is_axon)[0]
cab = Z['cable_um']
print('axon mask internal pieces:', nc,
      sorted([round(cab[idx[l == k]].sum(), 1) for k in range(nc)], reverse=True))
print('longest single edges inside mask (um):',
      np.round(np.sort(w[is_axon[E[:, 0]] & is_axon[E[:, 1]]])[::-1][:6], 1))
