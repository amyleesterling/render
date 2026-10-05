import numpy as np, sys
def obj_bbox(path, sample=1):
    mn = np.array([np.inf]*3); mx = np.array([-np.inf]*3); n = 0
    with open(path, 'r') as f:
        for line in f:
            if line[0] == 'v' and line[1] == ' ':
                p = np.fromstring(line[2:], sep=' ', count=3)
                mn = np.minimum(mn, p); mx = np.maximum(mx, p); n += 1
    return mn, mx, n

for label, obj, seg in [
    ("HERO native", r"D:\Meshes\hero\hero_648518346438632877.obj", 648518346438632877),
    ("HERO decim250", r"D:\Meshes\thorny pyramidals ca3 250\648518346438632877.obj", 648518346438632877),
    ("MF1 native", r"D:\Meshes\hero\fibre_648518346432881590.obj", 648518346432881590),
]:
    mn, mx, n = obj_bbox(obj)
    print(f"{label}: nverts={n:,}")
    print(f"   OBJ  min={mn.round(0).tolist()}  max={mx.round(0).tolist()}  extent={(mx-mn).round(0).tolist()}")
    try:
        d = np.load(rf"D:\Meshes\skeletons\{seg}.npz", allow_pickle=True)
        v = d['vertices']
        print(f"   SKEL min={v.min(0).round(0).tolist()}  max={v.max(0).round(0).tolist()}  extent={(v.max(0)-v.min(0)).round(0).tolist()}")
        print(f"   delta_min={(v.min(0)-mn).round(0).tolist()}  delta_max={(v.max(0)-mx).round(0).tolist()}")
        print(f"   ratio_extent={((v.max(0)-v.min(0))/(mx-mn)).round(4).tolist()}")
        print(f"   m2s_len={d['mesh_to_skel_map'].shape[0]}  vs obj_nverts={n}")
    except Exception as e:
        print("   skel not available:", e)
    sys.stdout.flush()
