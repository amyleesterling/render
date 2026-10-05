import numpy as np
Z = np.load(r'D:\Meshes\skeletons\axon_mask.npz', allow_pickle=True)
d = {k: Z[k] for k in Z.files}
d['crosscheck'] = np.array(
    "CROSS CHECKS RUN (not assumed). "
    "(1) AXIS CONFIRMED: all 165 mossy-fibre INPUT synapses onto this cell sit ABOVE the soma "
    "in OBJ y (dy +8.9 to +52.2 um, 165/165). Mossy fibres innervate the proximal apical dendrite, "
    "so +y is apical/up in frame and the descending set is the correct half. "
    "(2) OUTGOING-SYNAPSE CHECK FAILED, and the synapse data is the reason: of the 128 rows with "
    "pre_pt_root_id==648518346438632877 in synapses_ca3_v1 (mat 671), 88 are AUTAPSES "
    "(post_pt_root_id is the same cell) i.e. merge artefacts, and 88/128 have coordinates identical "
    "to an incoming synapse. Of the 40 genuine outgoing, only 9 land on the descending set and 30 on "
    "the ascending set. Their split across the two arbors is statistically indistinguishable from "
    "that of the 6293 INCOMING synapses (chi2 p=0.77), the signature of segmentation merge artefacts "
    "rather than axonal output. "
    "(3) CALIBRE CHECK PARTLY SUPPORTS: descending shaft radius median 0.477 um vs ascending 0.700 um; "
    "spininess (slab p90/p20) 2.78 vs 3.54; surface area per um cable 5.09 vs 8.48 um2/um. Descending "
    "is measurably thinner and smoother, but it still carries 1616 postsynaptic inputs at 0.99/um and "
    "is spiny, which is basal-dendrite-like, not axon-like (a real axon carries ~0). "
    "CONCLUSION: the descending/ascending split is solid and matches the hand markup, but the "
    "descending arbor is not pure axon. Use is_axon as 'the arbor the AP travels down' per the "
    "co-author, not as a verified anatomical axon.")
d['caveat_long_edges'] = np.array(
    "51 percent of the axon-mask cable lies in 96 skeleton edges longer than 5 um (longest 22.0 um). "
    "Verified these are genuine straight shaft runs, not gap jumps: sampling the 12 longest edges, "
    "the straight line stays within 0.1-2.7 um of the mesh surface everywhere. Linear interpolation "
    "along them is safe, but the pulse will have few intermediate nodes there.")
d['summary_numbers'] = np.array(
    "is_axon 1204 nodes / 1631.4 um cable; is_dendrite 1534 / 1663.4 um; is_soma 299 / 436.0 um; "
    "off-cell fragments 166 nodes / 48.0 um (excluded). Axon mean unit direction from soma, "
    "cable-weighted, OBJ (x,y,z) = (+0.816, -0.567, +0.110), coherence |mean|=0.851; centroid offset "
    "(+47.6, -31.4, +9.1) um; max euclid extent 195.8 um. The descending arbor emerges DIRECTLY FROM "
    "THE SOMA (first mask node at 9.0 um euclid, soma radius 6.83 um), not from a proximal dendrite.")
np.savez_compressed(r'D:\Meshes\skeletons\axon_mask.npz', **d)
Z2 = np.load(r'D:\Meshes\skeletons\axon_mask.npz', allow_pickle=True)
print('keys (%d):' % len(Z2.files), sorted(Z2.files))
print('is_axon', Z2['is_axon'].dtype, Z2['is_axon'].shape, int(Z2['is_axon'].sum()))
print('method:', str(Z2['method'])[:100], '...')
