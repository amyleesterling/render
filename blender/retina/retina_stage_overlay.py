"""Label each opening stage with the key that is actually true of it.

The sweep overlay says COLOUR = PREFERRED DIRECTION. That is true of the sweeps and
FALSE of the two stages before them: in the first, colour is which recording field
a cell came from, and in the second it is what kind of cell it is. Carrying the
direction key over those frames would be a caption that contradicts its own
picture, which is the exact failure this film has already been corrected for twice.

So each stage gets its own key, and the direction wheel appears only when direction
is what the colour means.

  python retina_stage_overlay.py
"""
import csv
import math
import os
from collections import Counter

from PIL import Image, ImageDraw, ImageFont

R = r"D:\Meshes\renders"
CSV = r"D:\Meshes\retina\functional_cells.csv"
MESHDIR = r"D:\Meshes\retina\meshes_clean"

INK = (239, 244, 251)
DIM = (154, 162, 177)
LINE = (196, 228, 255)
PANEL = (15, 18, 24)

CLUSTER = [("GCL0", "#2E8BE0"), ("GCL1", "#8B5CE0"), ("GCL2", "#E8A93A"),
           ("GCL3", "#17A06B"), ("GCL4", "#7FC4F5")]
TYPE = [("SAC", "#E8A93A", "starburst amacrine"), ("WFAC", "#8B5CE0", "wide field amacrine"),
        ("A1", "#17A06B", "A1 amacrine"), ("Fmini OFF", "#2E8BE0", "F-mini OFF"),
        ("UHD", "#E0559B", "ultra high density"), ("ON OS", "#7FC4F5", "ON orientation sel.")]
DIR_ANCHORS = [(0, "#2E8BE0"), (90, "#8B5CE0"), (180, "#E8A93A"),
               (270, "#17A06B"), (360, "#2E8BE0")]

rows = [r for r in csv.DictReader(open(CSV, encoding="utf-8"))
        if os.path.exists(os.path.join(MESHDIR, f"{int(r['root_id'])}.obj"))]
N = len(rows)
N_DS = sum(1 for r in rows if r["is_ds"] in ("True", "true", "1"))
by_field = Counter(r["field"] for r in rows)
by_type = Counter(r["cell_type"] for r in rows if r.get("cell_type"))
named = sum(by_type[t] for t, _, _ in TYPE)
print(f"[sv] {N} cells, {N_DS} direction selective, {named} in the six named types")


def hexrgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def dir_colour(deg):
    d = deg % 360
    for i in range(len(DIR_ANCHORS) - 1):
        a0, c0 = DIR_ANCHORS[i]
        a1, c1 = DIR_ANCHORS[i + 1]
        if a0 <= d <= a1:
            t = (d - a0) / (a1 - a0)
            r0, g0, b0 = hexrgb(c0)
            r1, g1, b1 = hexrgb(c1)
            return (int(r0 + (r1 - r0) * t), int(g0 + (g1 - g0) * t), int(b0 + (b1 - b0) * t))
    return hexrgb("#2E8BE0")


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


STAGES = {
    "cluster": ("COLOUR = RECORDING FIELD",
                "Five fields of view were calcium imaged in this retina.",
                [(f"{k}", h, f"{by_field.get(k, 0)} cells") for k, h in CLUSTER]),
    "type": ("COLOUR = CELL TYPE",
             f"The six most numerous named types. {N - named} of {N} cells "
             f"carry another of the 83 labels and sit back in grey.",
             [(k, h, f"{by_type.get(k, 0)}  {d}") for k, h, d in TYPE]),
    "dsonly": ("COLOUR = PREFERRED DIRECTION",
               f"The {N_DS} cells whose responses are direction selective, each in "
               f"the hue of the direction it prefers.", None),
}

for stage, (title, blurb, entries) in STAGES.items():
    src = os.path.join(R, f"retina_stage_{stage}.png")
    im = Image.open(src).convert("RGBA")
    W, H = im.size
    S = W / 1920.0
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    f_eye = font(int(15 * S), True)
    f_val = font(int(30 * S), True)
    f_lab = font(int(16 * S))
    f_sub = font(int(14 * S))
    pad = int(20 * S)

    # readout, upper left, same position and language as the sweeps
    rx, ry = int(56 * S), int(56 * S)
    L1 = "EYEWIRE II  \u00b7  CALCIUM IMAGED"
    L2 = f"ALL {N} IMAGED CELLS RECONSTRUCTED"
    big = str(N_DS if stage == "dsonly" else N)
    L3 = "DIRECTION SELECTIVE" if stage == "dsonly" else "CELLS"
    wv = d.textlength(big, font=f_val)
    rw = int(max(d.textlength(L1, font=f_eye), d.textlength(L2, font=f_lab),
                 wv + int(10 * S) + d.textlength(L3, font=f_lab)) + int(36 * S))
    d.rectangle([rx - int(18 * S), ry - int(18 * S), rx - int(18 * S) + rw, ry + int(112 * S)],
                fill=PANEL + (176,))
    brackets(d, rx - int(18 * S), ry - int(18 * S), rw, int(130 * S), LINE + (150,))
    d.text((rx, ry), L1, font=f_eye, fill=DIM)
    d.text((rx, ry + int(26 * S)), big, font=f_val, fill=INK)
    d.text((rx + wv + int(10 * S), ry + int(38 * S)), L3, font=f_lab, fill=DIM)
    d.text((rx, ry + int(78 * S)), L2, font=f_lab, fill=DIM)

    # the key, lower left
    if entries is not None:
        sw, gap, row_h = int(15 * S), int(11 * S), int(30 * S)
        w_nm = max(d.textlength(e[0], font=f_lab) for e in entries)
        w_ds = max(d.textlength(e[2], font=f_sub) for e in entries)
        inner = max(d.textlength(title, font=f_eye), sw + gap + w_nm + gap * 2 + w_ds)
        # the blurb wraps to the panel width rather than setting it
        pw = int(inner + 2 * pad)
        lines = []
        cur = ""
        for word in blurb.split():
            t = (cur + " " + word).strip()
            if d.textlength(t, font=f_sub) > inner and cur:
                lines.append(cur); cur = word
            else:
                cur = t
        lines.append(cur)
        ph = int(row_h * len(entries) + int(56 * S) + len(lines) * int(20 * S))
        x0, y0 = int(56 * S), H - ph - int(56 * S)
        d.rectangle([x0, y0, x0 + pw, y0 + ph], fill=PANEL + (176,))
        brackets(d, x0, y0, pw, ph, LINE + (150,))
        d.text((x0 + pad, y0 + int(16 * S)), title, font=f_eye, fill=DIM)
        yy = y0 + int(46 * S)
        for nm, hx, ds in entries:
            d.rectangle([x0 + pad, yy + int(4 * S), x0 + pad + sw, yy + int(4 * S) + sw],
                        fill=hexrgb(hx) + (255,))
            d.text((x0 + pad + sw + gap, yy), nm, font=f_lab, fill=INK)
            d.text((x0 + pad + sw + gap + w_nm + gap * 2, yy + int(2 * S)), ds, font=f_sub, fill=DIM)
            yy += row_h
        yy += int(6 * S)
        for ln in lines:
            d.text((x0 + pad, yy), ln, font=f_sub, fill=DIM)
            yy += int(20 * S)
    else:
        # the direction wheel, identical in construction to the sweep overlay so the
        # key the viewer learns here is the key the animation then uses
        ks = int(210 * S)
        r_k = int(ks * 0.40)
        w_title = d.textlength(title, font=f_eye)
        w_side = max(d.textlength("LEFT", font=f_lab), d.textlength("RIGHT", font=f_lab))
        lab_reach = ks * 0.5 + r_k + int(22 * S) + w_side / 2.0
        pw = int(max(w_title, lab_reach) + 2 * pad)
        kx, ky = int(56 * S) + pad, H - int(300 * S)
        d.rectangle([kx - pad, ky - int(46 * S), kx - pad + pw, ky - int(46 * S) + ks + int(78 * S)],
                    fill=PANEL + (176,))
        brackets(d, kx - pad, ky - int(46 * S), pw, ks + int(78 * S), LINE + (150,))
        d.text((kx, ky - int(34 * S)), title, font=f_eye, fill=DIM)
        cx, cy = kx + ks // 2, ky + ks // 2
        for a in range(0, 360, 4):
            d.pieslice([cx - r_k, cy - r_k, cx + r_k, cy + r_k], -a - 4, -a,
                       fill=dir_colour(a) + (235,))
        d.ellipse([cx - int(r_k * .52), cy - int(r_k * .52), cx + int(r_k * .52), cy + int(r_k * .52)],
                  fill=(7, 8, 11, 255))
        for lab, a in (("UP", 90), ("RIGHT", 0), ("DOWN", 270), ("LEFT", 180)):
            rad = math.radians(a)
            d.text((cx + math.cos(rad) * (r_k + int(22 * S)),
                    cy - math.sin(rad) * (r_k + int(22 * S))), lab, font=f_lab, fill=DIM, anchor="mm")

    out = os.path.join(R, f"retina_stage_{stage}_ov.png")
    Image.alpha_composite(im, ov).convert("RGB").save(out)
    print(f"[sv] {stage} -> {out}", flush=True)
print("[sv] DONE")
