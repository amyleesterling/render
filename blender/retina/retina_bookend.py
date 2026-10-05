"""Assemble the retina film: the opening stages, the sweeps, and a closing fade.

Amy's sequence, 3 August 2026:

  black
  -> the five calcium imaged fields, coloured by field
  -> recoloured to cell type
  -> everything that is not direction selective falls away
  -> the bar sweeps          (the existing 576 frames, unchanged)
  -> back to the population
  -> black

Each stage carries an argument, and each is labelled with the key that is TRUE of
it: colour means recording field, then cell type, then preferred direction. The
sweep overlay's direction key would be a lie over the first two.

WHY THESE ARE DISSOLVES AND NOT RENDERED FRAMES. The camera never moves in this
film and no geometry moves; only material colour changes between stages. So a
dissolve between two stage renders is pixel-identical to rendering the frames
between them, at no GPU cost. 324 handle frames at 52 s each would be nearly five
hours to produce exactly this. Anything that MOVED would have to be rendered.

The dissolve is done in LINEAR light. Cross-fading 8-bit sRGB darkens the midpoint,
which on a black field reads as the arbor dipping halfway through every transition.

  python retina_bookend.py
"""
import argparse
import os
import shutil

import numpy as np
from PIL import Image

AP = argparse.ArgumentParser()
AP.add_argument("--seq", default=r"D:\Meshes\renders\retina_ds364_overlay")
AP.add_argument("--out", default=r"D:\Meshes\renders\retina_ds364_final")
AP.add_argument("--fade", type=int, default=36)      # black <-> first stage
AP.add_argument("--hold", type=int, default=42)      # each stage, long enough to read
AP.add_argument("--dissolve", type=int, default=30)  # stage <-> stage
A = AP.parse_args()

R = r"D:\Meshes\renders"
STAGES = [os.path.join(R, f"retina_stage_{s}_ov.png") for s in ("cluster", "type", "dsonly")]
for p in STAGES:
    if not os.path.exists(p):
        raise SystemExit(f"missing {p}: run retina_stage_overlay.py first")

if os.path.isdir(A.out):
    shutil.rmtree(A.out)
os.makedirs(A.out)

frames = sorted(f for f in os.listdir(A.seq) if f.endswith(".png"))
if not frames:
    raise SystemExit(f"no frames in {A.seq}")


def lin(path):
    x = np.asarray(Image.open(path).convert("RGB")).astype(np.float64) / 255.0
    return np.where(x <= 0.04045, x / 12.92, ((x + 0.055) / 1.055) ** 2.4)


L = [lin(p) for p in STAGES]
L_first = lin(os.path.join(A.seq, frames[0]))
L_last = lin(os.path.join(A.seq, frames[-1]))
L_black = np.zeros_like(L[0])
for i, p in enumerate(STAGES):
    if L[i].shape != L_first.shape:
        raise SystemExit(f"{p} is {L[i].shape[:2]}, sequence is {L_first.shape[:2]}")
print(f"[bk] {len(frames)} sweep frames, {L_first.shape[1]}x{L_first.shape[0]}, "
      f"{len(STAGES)} stages")


def to_srgb(x):
    x = np.clip(x, 0.0, 1.0)
    return np.where(x <= 0.0031308, x * 12.92, 1.055 * x ** (1 / 2.4) - 0.055)


def smooth(t):
    return t * t * (3.0 - 2.0 * t)


n = 0


def write(img):
    global n
    Image.fromarray((to_srgb(img) * 255.0 + 0.5).astype(np.uint8)).save(
        os.path.join(A.out, f"f{n:05d}.png"))
    n += 1


def blend(a, b, count, include_end=False):
    # include_end off by default so segments meeting at the same image do not emit
    # it twice, which shows as a one frame stall at every junction.
    for i in range(count + (1 if include_end else 0)):
        write(a + (b - a) * smooth(i / max(1, count)))


def hold(img, count):
    for _ in range(count):
        write(img)


print("[bk] opening")
blend(L_black, L[0], A.fade)          # rise out of black into the five fields
hold(L[0], A.hold)
blend(L[0], L[1], A.dissolve)         # recolour to cell type
hold(L[1], A.hold)
blend(L[1], L[2], A.dissolve)         # the non selective cells fall away
hold(L[2], A.hold)
blend(L[2], L_first, A.dissolve)      # settle into the state the sweeps start in
intro = n
print(f"[bk]   {intro} frames")

print("[bk] sweeps")
for f in frames:
    shutil.copyfile(os.path.join(A.seq, f), os.path.join(A.out, f"f{n:05d}.png"))
    n += 1

print("[bk] closing")
blend(L_last, L[2], A.dissolve)       # back to the direction selective population
hold(L[2], A.hold)
blend(L[2], L_black, A.fade, include_end=True)

print(f"\n[bk] {n} frames ({n/24:.1f} s at 24 fps) -> {A.out}")
got = len([x for x in os.listdir(A.out) if x.endswith(".png")])
assert got == n, f"wrote {n} but {got} are on disk"
print(f"[bk] verified {got} on disk, f00000..f{n-1:05d}")
