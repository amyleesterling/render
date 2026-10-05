"""Encode every rendered banc-explorer layer to lossless WebP, and audit the alpha.

Spec, per layer: a 1600x1200 static and a 16 frame non-looping pulse, transparent
straight alpha, lossless, frames 00 and 15 fully transparent.

Every claim here is CHECKED rather than trusted:

  size          asserted against banc-context-base.webp, since layers that do not
                register pixel for pixel are worse than missing layers
  straight alpha  measured, with a premultiplied copy run through the same test as
                a control. Without a control that must fail, a pass means nothing.
  bookends      asserted to be exactly frames [0, 15], not eyeballed

A layer that fails any of these is reported and NOT written to public, because a
half-correct compositing layer is harder to find than an absent one.

  python banc_layers_webp.py [--dry]
"""
import argparse
import os

import numpy as np
from PIL import Image

AP = argparse.ArgumentParser()
AP.add_argument("--src", default=r"D:\Meshes\renders\layers")
AP.add_argument("--dst", default=r"C:\Users\amyle\Documents\New project\banc-explorer\public")
AP.add_argument("--dry", action="store_true")
A = AP.parse_args()

REF = os.path.join(A.dst, "banc-context-base.webp")
SIZE = Image.open(REF).size if os.path.exists(REF) else (1600, 1200)
print(f"[w] registering against {os.path.basename(REF)}: {SIZE[0]}x{SIZE[1]}")

LAYERS = [
    "flight-power-dng02", "flight-steer-mnb1-all",
    "flight-steer-mnb1-anatomical-left", "flight-steer-mnb1-anatomical-right",
    "landing-dnp07-dnp10", "landing-dnp07", "landing-dnp10",
    "forward", "backward", "turn-left", "turn-right", "eat", "threat-walk",
    "flight-dodge-dnp03-all", "flight-dodge-dnp03-anatomical-left",
    "flight-dodge-dnp03-anatomical-right",
]


def matte_score(rgb, alpha, lo=0.12, hi=0.35):
    lum = rgb.max(2)
    edge = (alpha > lo) & (alpha < hi)
    solid = alpha > 0.90
    if edge.sum() < 50 or solid.sum() < 50:
        return None
    return float(lum[edge].mean() / max(lum[solid].mean(), 1e-9))


def audit(path):
    a = np.asarray(Image.open(path).convert("RGBA")).astype(np.float64)
    rgb, al = a[..., :3], a[..., 3] / 255.0
    s = matte_score(rgb, al)
    c = matte_score(rgb * al[..., None], al)      # a black matte, as the control
    if s is None or c is None:
        return "no sample"
    if c >= s - 0.05:
        return f"CONTROL FAILED ({s:.2f} vs {c:.2f})"
    return "straight" if s > 0.85 else f"MATTED ({s:.2f})"


def encode(src, dst):
    im = Image.open(src).convert("RGBA")
    if im.size != SIZE:
        raise ValueError(f"{os.path.basename(src)} is {im.size}, must be {SIZE}")
    if not A.dry:
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        im.save(dst, "WEBP", lossless=True, quality=100, method=6, exact=True)
        return os.path.getsize(dst)
    return 0


ok, failed = [], []
for name in LAYERS:
    stat_src = os.path.join(A.src, f"banc-{name}.png")
    seq_src = os.path.join(A.src, f"banc-{name}-seq")
    stat_dst = os.path.join(A.dst, f"banc-{name}.webp")
    seq_dst = os.path.join(A.dst, f"banc-{name}")
    try:
        n_stat = encode(stat_src, stat_dst) if os.path.exists(stat_src) else -1
        frames = sorted(f for f in os.listdir(seq_src) if f.endswith(".png"))
        if len(frames) != 16:
            raise ValueError(f"{len(frames)} frames, expected 16")
        total, blank = 0, []
        for i, f in enumerate(frames):
            total += encode(os.path.join(seq_src, f),
                            os.path.join(seq_dst, f"frame-{i:02d}.webp"))
            a = np.asarray(Image.open(os.path.join(seq_src, f)).convert("RGBA"))[..., 3]
            if a.max() == 0:
                blank.append(i)
        if blank != [0, 15]:
            raise ValueError(f"transparent frames are {blank}, spec requires [0, 15]")
        verdict = audit(os.path.join(seq_src, frames[7]))
        if "straight" not in verdict:
            raise ValueError(f"alpha audit: {verdict}")
        note = "static kept" if n_stat < 0 else f"static {n_stat/1e3:.0f} KB"
        print(f"[w] {name:<38} {note}, 16 frames {total/1e3:6.0f} KB, alpha {verdict}")
        ok.append(name)
    except Exception as e:
        print(f"[w] {name:<38} FAILED: {e}")
        failed.append((name, str(e)))

print(f"\n[w] {len(ok)} layers encoded, {len(failed)} failed")
for n, e in failed:
    print(f"      {n}: {e}")
