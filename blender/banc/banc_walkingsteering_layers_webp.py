"""Encode the four stacked layers to WebP and prove they are pixel aligned.

Alignment is the property the whole stack depends on, so it is measured rather
than assumed. Every action layer draws a subset of the cells the gray base draws,
so with an identical camera each action layer's lit pixels must fall inside the
base's lit pixels. Anything less means the layers would ghost when stacked.

A shifted copy of the same layer is scored the same way as a control. If a 3 px
shift does not drop the score, the test cannot detect misalignment and proves
nothing.

  python banc_walkingsteering_layers_webp.py
"""
import json
import os

import numpy as np
from PIL import Image

SRC = r"D:\Meshes\renders\layers"
DST = r"C:\Users\amyle\Documents\New project\banc-explorer\public"
PREVIEW = r"D:\Meshes\renders\layers\preview"
LAYERS_JSON = r"D:\Meshes\banc\walking_steering_layers.json"
PANEL_BG = (10, 14, 18)
MAX_BYTES = 1_000_000

# Read the layer list from the config, never a hardcoded copy of it: a hardcoded
# list silently skipped two new layers once already.
_cfg = json.load(open(LAYERS_JSON))["layers"]
LAYERS = ["context-base"] + [k for k in _cfg if k != "context-base"]

os.makedirs(DST, exist_ok=True)
os.makedirs(PREVIEW, exist_ok=True)

ims = {}
for name in LAYERS:
    p = os.path.join(SRC, f"{name}.png")
    if not os.path.exists(p):
        raise SystemExit(f"missing {p}")
    ims[name] = Image.open(p).convert("RGBA")

print("geometry")
for name, im in ims.items():
    a = np.asarray(im)
    print(f"  {name:14s} {im.size[0]}x{im.size[1]}  alpha {a[...,3].min()}-{a[...,3].max()}  "
          f"lit {100*(a[...,3]>8).mean():5.2f}%")
sizes = {im.size for im in ims.values()}
assert sizes == {(1600, 1200)}, f"layers differ in size: {sizes}"

base = np.asarray(ims["context-base"])[..., 3] > 8
print(f"\nalignment: action-layer pixels must fall inside the gray base")
worst = 1.0
for name in LAYERS[1:]:
    m = np.asarray(ims[name])[..., 3] > 8
    inside = (m & base).sum() / max(m.sum(), 1)
    shifted = np.roll(m, 3, axis=1)                      # control: 3 px sideways
    ctrl = (shifted & base).sum() / max(shifted.sum(), 1)
    worst = min(worst, inside)
    print(f"  {name:14s} {m.sum():7,d} lit px   inside base {100*inside:6.2f}%   "
          f"CONTROL shifted 3px {100*ctrl:6.2f}%")
    if ctrl > inside - 0.01:
        print("    !! control did not separate, this alignment check is void")
assert worst > 0.995, f"layers are not aligned (worst {worst:.4f})"
print("  -> aligned")

l = np.asarray(ims["turn-left"])[..., 3] > 8
r = np.asarray(ims["turn-right"])[..., 3] > 8
print(f"\nturn-left / turn-right overlap: {100*(l&r).sum()/max((l|r).sum(),1):.2f}% "
      f"of their union (should be small: opposite sides of the animal)")

print("\nencode")
total = 0
for name, im in ims.items():
    out = os.path.join(DST, f"banc-{name}.webp")
    chosen = None
    for label, kw in [("lossless", dict(lossless=True, quality=100, method=6, exact=False))] + \
                     [(f"q{q}", dict(lossless=False, quality=q, method=6, exact=False))
                      for q in (95, 92, 90)]:
        im.save(out, "WEBP", **kw)
        if os.path.getsize(out) <= MAX_BYTES:
            chosen = (label, os.path.getsize(out))
            break
    if chosen is None:
        raise SystemExit(f"{name} could not hit the size budget")
    back = Image.open(out).convert("RGBA")
    b = np.asarray(back)
    a = np.asarray(im)
    assert back.size == (1600, 1200), f"{name} wrong size"
    assert b[..., 3].min() == 0, f"{name} has no transparent pixels"
    d = int(np.abs(b[..., 3].astype(int) - a[..., 3].astype(int)).max())
    total += chosen[1]
    print(f"  banc-{name+'.webp':24s} {chosen[0]:8s} {chosen[1]/1e3:7.1f} KB  "
          f"alpha delta {d}/255")

    f = Image.new("RGBA", back.size, PANEL_BG + (255,))
    f.alpha_composite(back)
    f.convert("RGB").save(os.path.join(PREVIEW, f"{name}_on_panel.png"))

print(f"\n  {len(LAYERS)} files, {total/1e3:.1f} KB total -> {DST}")

# What the app will actually show: base plus one action on top.
for act in LAYERS[1:]:
    f = Image.new("RGBA", (1600, 1200), PANEL_BG + (255,))
    f.alpha_composite(ims["context-base"])
    f.alpha_composite(ims[act])
    f.convert("RGB").save(os.path.join(PREVIEW, f"stacked_{act}.png"))
print(f"  stacked previews -> {PREVIEW}")
