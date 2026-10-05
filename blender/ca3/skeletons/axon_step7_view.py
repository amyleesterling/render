"""Step 7: look at the cell. Project the skeleton in OBJ x-y (frame axes) and
colour by the quantities that matter."""
import numpy as np, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd

sk = np.load(r'D:\Meshes\skeletons\648518346438632877.npz', allow_pickle=True)
S = sk['vertices'].astype(np.float64); E = sk['edges']; ROOT = int(sk['root']); SOMA = S[ROOT]
MA = np.load(r'D:\Meshes\skeletons\_mesh_assign.npz')
in_dens = MA['in_dens']; inmain = MA['inmain']; de = MA['de']
M = np.load(r'D:\Meshes\skeletons\_node_metrics.npz'); r_p25 = M['r_p25']
P = np.load(r'D:\Meshes\skeletons\_partition.npz'); is_axon = P['is_axon']

X = (S[:, 0] - SOMA[0]) / 1000.; Y = (S[:, 1] - SOMA[1]) / 1000.
inc = (np.load(r'D:\Meshes\renders\hero_incoming_raw.npy') - SOMA) / 1000.
mf = (np.load(r'D:\Meshes\renders\hero_synapses.npy') - SOMA) / 1000.
df = pd.read_pickle(r'D:\Meshes\renders\hero_outgoing_requery.pkl')
HERO = 648518346438632877
real = (np.vstack(df[df.post_pt_root_id != HERO]['ctr_pt_position'].values).astype(float) - SOMA) / 1000.
auto = (np.vstack(df[df.post_pt_root_id == HERO]['ctr_pt_position'].values).astype(float) - SOMA) / 1000.

seg = np.stack([np.c_[X[E[:, 0]], Y[E[:, 0]]], np.c_[X[E[:, 1]], Y[E[:, 1]]]], axis=1)
from matplotlib.collections import LineCollection

fig, axs = plt.subplots(1, 4, figsize=(26, 8), sharex=True, sharey=True)
def base(ax, c, title, **kw):
    lc = LineCollection(seg, colors=c, linewidths=0.8, **kw)
    ax.add_collection(lc)
    ax.plot(0, 0, 'k*', ms=22, zorder=5)
    ax.set_title(title, fontsize=11); ax.set_aspect('equal')
    ax.set_xlim(X[inmain].min() - 5, X[inmain].max() + 5)
    ax.set_ylim(Y[inmain].min() - 5, Y[inmain].max() + 5)
    ax.axhline(0, color='k', lw=0.5, ls='--')
    ax.set_xlabel('OBJ x - soma (um)'); ax.set_ylabel('OBJ y - soma (um)  [up in frame]')

# 1: descending/ascending
c1 = np.where(is_axon[E[:, 0]] | is_axon[E[:, 1]], '#d62728', '#1f77b4')
base(axs[0], c1, 'descending (red) vs ascending (blue)')

# 2: input synapse density (log)
v = np.log10(np.maximum((in_dens[E[:, 0]] + in_dens[E[:, 1]]) / 2, 0.02))
cm = plt.cm.viridis((v - v.min()) / (v.max() - v.min()))
base(axs[1], cm, 'log10 INPUT synapse density (dark = no inputs)')
axs[1].scatter(mf[:, 0], mf[:, 1], s=8, c='magenta', zorder=4, label='165 mossy-fibre inputs')
axs[1].legend(fontsize=8, loc='lower left')

# 3: shaft radius
rr = np.nan_to_num((r_p25[E[:, 0]] + r_p25[E[:, 1]]) / 2, nan=0.6)
cm3 = plt.cm.plasma(np.clip(rr / 1.5, 0, 1))
base(axs[2], cm3, 'local shaft radius r_p25 (dark = thin)')

# 4: synapses
base(axs[3], '#cccccc', 'synapses: 40 true outgoing (red) vs 88 autapse artefacts (orange)')
axs[3].scatter(inc[:, 0], inc[:, 1], s=1, c='#88aacc', alpha=.3, zorder=2, label='6293 inputs')
axs[3].scatter(auto[:, 0], auto[:, 1], s=22, c='orange', zorder=3, label='88 "outgoing" = autapse')
axs[3].scatter(real[:, 0], real[:, 1], s=45, c='red', marker='v', zorder=4, label='40 true outgoing')
axs[3].legend(fontsize=8, loc='lower left')
plt.tight_layout()
plt.savefig(r'D:\Meshes\skeletons\_axon_view_xy.png', dpi=95)
print('saved _axon_view_xy.png')
