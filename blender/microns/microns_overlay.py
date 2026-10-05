"""Burn a cell-type legend onto the cortex orbit frames.

Colour in this film is IDENTITY, not position, and nothing in the picture says so.
Without a key a viewer reads the vertical banding as a depth ramp, which is exactly
the wrong conclusion: the bands are there because each type lives at its own depth,
which is a stronger claim than a depth ramp could make and is lost if unlabelled.

Counts come from the same CSV the render coloured from, so the legend cannot drift
away from the picture. Types absent from the render are not listed.

Panels are sized from their own text. A hard coded width is a caption bug waiting
for someone to edit the caption, which has already happened twice on this project.

  python microns_overlay.py --frames DIR --out DIR
"""
import argparse
import csv
import os
from collections import Counter

from PIL import Image, ImageDraw, ImageFont

AP = argparse.ArgumentParser()
AP.add_argument("--frames", default=r"D:\Meshes\renders\microns_orbit_type_frames")
AP.add_argument("--out", default=r"D:\Meshes\renders\microns_orbit_type_ov")
AP.add_argument("--types", default=r"D:\Meshes\renders\microns_celltypes.csv")
A = AP.parse_args()
os.makedirs(A.out, exist_ok=True)

INK = (239, 244, 251)
DIM = (154, 162, 177)
LINE = (196, 228, 255)
PANEL = (15, 18, 24)

# Must match TYPE_COLOUR in microns_column.py exactly.
TYPE_COLOUR = {
    "23P":   ("#2E8BE0", "layer 2/3 pyramidal"),
    "4P":    ("#8B5CE0", "layer 4 pyramidal"),
    "5P-IT": ("#E8A93A", "layer 5 intratelencephalic"),
    "5P-ET": ("#17A06B", "layer 5 extratelencephalic"),
    "6P-IT": ("#7FC4F5", "layer 6 intratelencephalic"),
    "MC":    ("#E0559B", "Martinotti, inhibitory"),
    "oligo": ("#8A94A6", "oligodendrocyte, not a neuron"),
}
UNKNOWN = "#4A5568"


def hexrgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


rows = list(csv.DictReader(open(A.types, encoding="utf-8")))
counts = Counter(r["cell_type"] for r in rows if r.get("cell_type"))
n_untyped = sum(1 for r in rows if not r.get("cell_type"))
order = [t for t in TYPE_COLOUR if counts.get(t)]
print(f"[ov] {len(rows)} cells, {sum(counts.values())} typed, {n_untyped} not")


def font(sz, bold=False):
    for n in (("seguisb.ttf", "segoeuib.ttf") if bold else ("segoeui.ttf",)):
        try:
            return ImageFont.truetype(n, sz)
        except OSError:
            pass
    return ImageFont.load_default()


def brackets(d, x, y, w, h, col, ln=14, wd=1):
    for (cx, cy, dx, dy) in ((x, y, 1, 1), (x + w, y, -1, 1),
                             (x, y + h, 1, -1), (x + w, y + h, -1, -1)):
        d.line([cx, cy, cx + dx * ln, cy], fill=col, width=wd)
        d.line([cx, cy, cx, cy + dy * ln], fill=col, width=wd)


files = sorted(f for f in os.listdir(A.frames) if f.endswith(".png"))
print(f"[ov] {len(files)} frames", flush=True)

for i, fn in enumerate(files, 1):
    im = Image.open(os.path.join(A.frames, fn)).convert("RGBA")
    W, H = im.size
    S = W / 1920.0
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    f_eye = font(int(15 * S), True)
    f_lab = font(int(16 * S))
    f_sub = font(int(13 * S))
    f_val = font(int(30 * S), True)

    # ---- the key, lower left ------------------------------------------------
    TITLE = "COLOUR = PREDICTED CELL TYPE"
    pad = int(20 * S)
    sw = int(15 * S)                      # swatch
    gap = int(11 * S)
    row_h = int(30 * S)
    # MEASURE THE STRING THAT IS ACTUALLY DRAWN. Measuring the description alone
    # while drawing "description  xN" is the same bug that ran LEFT and RIGHT under
    # the retina colour key and then ran the readout past its panel: the row is
    # only as wide as the widest thing on it, counts included.
    desc_txt = {t: f"{TYPE_COLOUR[t][1]}   ×{counts[t]}" for t in order}
    w_name = max(d.textlength(t, font=f_lab) for t in order)
    w_desc = max(d.textlength(desc_txt[t], font=f_sub) for t in order)
    inner = max(d.textlength(TITLE, font=f_eye),
                sw + gap + w_name + gap * 2 + w_desc)
    pw = int(inner + 2 * pad)
    ph = int(row_h * len(order) + int(64 * S))
    x0 = int(56 * S)
    y0 = H - ph - int(56 * S)
    d.rectangle([x0, y0, x0 + pw, y0 + ph], fill=PANEL + (176,))
    brackets(d, x0, y0, pw, ph, LINE + (150,))
    d.text((x0 + pad, y0 + int(16 * S)), TITLE, font=f_eye, fill=DIM)
    yy = y0 + int(48 * S)
    for t in order:
        hexc, desc = TYPE_COLOUR[t]
        d.rectangle([x0 + pad, yy + int(4 * S), x0 + pad + sw, yy + int(4 * S) + sw],
                    fill=hexrgb(hexc) + (255,))
        d.text((x0 + pad + sw + gap, yy), f"{t}", font=f_lab, fill=INK)
        d.text((x0 + pad + sw + gap + w_name + gap * 2, yy + int(3 * S)),
               desc_txt[t], font=f_sub, fill=DIM)
        yy += row_h

    # ---- readout, upper left ------------------------------------------------
    rx, ry = int(56 * S), int(56 * S)
    L1 = "MICRONS MOUSE VISUAL CORTEX"
    L2 = f"OF {len(rows)} PROOFREAD CELLS TYPED"
    L3 = "COLOUR IS IDENTITY, NOT DEPTH"
    wv = d.textlength(str(sum(counts.values())), font=f_val)
    rw = int(max(d.textlength(L1, font=f_eye), d.textlength(L3, font=f_lab),
                 wv + int(10 * S) + d.textlength(L2, font=f_lab)) + int(36 * S))
    d.rectangle([rx - int(18 * S), ry - int(18 * S), rx - int(18 * S) + rw,
                 ry + int(132 * S)], fill=PANEL + (176,))
    brackets(d, rx - int(18 * S), ry - int(18 * S), rw, int(150 * S), LINE + (150,))
    d.text((rx, ry), L1, font=f_eye, fill=DIM)
    d.text((rx, ry + int(26 * S)), str(sum(counts.values())), font=f_val, fill=INK)
    d.text((rx + wv + int(10 * S), ry + int(38 * S)), L2, font=f_lab, fill=DIM)
    d.text((rx, ry + int(80 * S)), L3, font=f_lab, fill=DIM)

    Image.alpha_composite(im, ov).convert("RGB").save(os.path.join(A.out, fn))
    if i % 40 == 0 or i == len(files):
        print(f"[ov] {i}/{len(files)}", flush=True)
print("[ov] DONE", flush=True)
