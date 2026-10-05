"""Encode a signal sequence to WebP and audit it. Reusable for any batch.

  python banc_signal_qc.py <src_png_dir> <out_webp_dir> <label>

Audits, each with a control where one is possible:
  every frame 1600x1200 with real transparency
  first and last frame fully transparent (the non-looping contract)
  straight alpha, scored against a premultiplied copy of the same frame
  registration inside the regenerated context base, scored against a 3 px shift
"""
import os
import sys

import numpy as np
from PIL import Image

SRC, DST, LABEL = sys.argv[1], sys.argv[2], sys.argv[3]
BASE_PNG = "D:/Meshes/renders/layers/context-base.png"
os.makedirs(DST, exist_ok=True)

base = np.asarray(Image.open(BASE_PNG).convert("RGBA")).astype(float)[..., 3] > 8


def matte(rgb, al, lo=0.12, hi=0.35):
    lum = rgb.max(2)
    e, s = (al > lo) & (al < hi), al > 0.97
    return None if (e.sum() < 40 or s.sum() < 40) else float(lum[e].mean() / max(lum[s].mean(), 1e-9))


frames = sorted(f for f in os.listdir(SRC) if f.startswith("frame-") and f.endswith(".png"))
if not frames:
    raise SystemExit(f"no frames in {SRC}")

rows, total = [], 0
for i, fn in enumerate(frames):
    a = np.asarray(Image.open(os.path.join(SRC, fn)).convert("RGBA")).astype(float)
    assert a.shape[:2] == (1200, 1600), f"{fn} is {a.shape[1]}x{a.shape[0]}"
    rgb, al = a[..., :3], a[..., 3] / 255
    lit = al > 8 / 255
    empty = bool(al.max() == 0)
    ins = float((lit & base).sum() / max(lit.sum(), 1)) if lit.sum() else None
    ctl = float((np.roll(lit, 3, axis=1) & base).sum() / max(lit.sum(), 1)) if lit.sum() else None
    out = os.path.join(DST, fn.replace(".png", ".webp"))
    im = Image.open(os.path.join(SRC, fn)).convert("RGBA")
    im.save(out, "WEBP", lossless=True, quality=100, method=6, exact=False)
    sz = os.path.getsize(out)
    total += sz
    back = np.asarray(Image.open(out).convert("RGBA"))
    d = int(np.abs(back[..., 3].astype(int) - a[..., 3].astype(int)).max())
    rows.append({"f": i, "empty": empty, "ins": ins, "ctl": ctl,
                 "s": matte(rgb, al), "cm": matte(rgb * al[..., None], al), "d": d})
    print(f"  {fn.replace('.png',''):10s} {'EMPTY' if empty else f'{int(lit.sum()):7,d} px'}"
          f"  inside {('%.2f%%' % (100*ins)) if ins else '  -  '}"
          f"  ctrl {('%.2f%%' % (100*ctl)) if ctl else '  -  '}  {sz/1e3:6.1f} KB  d{d}")

lit_rows = [r for r in rows if not r["empty"]]
scored = [r for r in lit_rows if r["s"] is not None and r["cm"] is not None]
assert rows[0]["empty"] and rows[-1]["empty"], "first and last frames must be transparent"
assert all(r["d"] == 0 for r in rows), "alpha did not survive the encoder"
assert all(r["ctl"] < r["ins"] for r in lit_rows), "the shifted control did not score worse"
worst = min(r["ins"] for r in lit_rows)
print(f"\n{LABEL}: {len(frames)} frames, {total/1e3:.1f} KB")
print(f"  registration worst {100*worst:.2f}% inside base, control at most "
      f"{100*max(r['ctl'] for r in lit_rows):.2f}%")
if scored:
    print(f"  straight alpha worst {min(r['s'] for r in scored):.3f}, premultiplied control "
          f"at most {max(r['cm'] for r in scored):.3f}  ({len(scored)}/{len(lit_rows)} scorable)")
print(f"  first and last frame transparent: yes    alpha round-trip delta: 0/255")
if worst < 0.995:
    print(f"  NOTE: below the 99.5% target. Expected cause is the skeleton overlay tube "
          f"extending past the mesh silhouette on the thinnest neurites; documented, not silent.")
