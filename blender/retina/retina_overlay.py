"""Composite the readout overlays onto the retina frames.

Three things the render alone cannot say:
  1. a colour key, because hue means preferred direction and that is not guessable
  2. a compass showing which way the bar is moving right now
  3. a live count of how many cells are responding

The compass arrow is drawn in the SAME colour as the cells that should respond to
it. That ties the key, the compass and the population together without a caption.

Design follows scifi-ui: panel 15/18/24, hairline corner brackets, small uppercase
eyebrow type in pale blue, and gold used once as the single warm accent.

  python retina_overlay.py [--frames DIR] [--out DIR]
"""
import argparse
import csv
import json
import math
import os

from PIL import Image, ImageDraw, ImageFont

AP = argparse.ArgumentParser()
AP.add_argument("--frames", default=r"D:\Meshes\renders\retina_ds2_frames")
AP.add_argument("--out", default=r"D:\Meshes\renders\retina_ds2_overlay")
AP.add_argument("--total", type=int, default=576)
A = AP.parse_args()
os.makedirs(A.out, exist_ok=True)

# scifi-ui tokens
INK = (239, 244, 251)
DIM = (154, 162, 177)
LINE = (196, 228, 255)
WARM = (232, 169, 58)
PANEL = (15, 18, 24)

# must match retina_ds_anim.py exactly
NBINS = 8
HOLD = int(A.total * 0.10)
PER = (A.total - HOLD) / NBINS

DIR_ANCHORS = [(0, "#2E8BE0"), (90, "#8B5CE0"), (180, "#E8A93A"),
               (270, "#17A06B"), (360, "#2E8BE0")]


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
            return (int(r0 + (r1 - r0) * t), int(g0 + (g1 - g0) * t),
                    int(b0 + (b1 - b0) * t))
    return hexrgb("#2E8BE0")


cells = []
# The readout used to say "64 DIRECTION SELECTIVE" full stop. That is true of what
# is on screen and false about the experiment: 106 of the 364 joined cells are
# direction selective, and 42 of them have no mesh staged, so they are not dim in
# the background, they are absent. A number with no denominator invites the reader
# to take it as the population. Both totals are counted here so the panel can show
# the fraction instead.
ALL_N = ALL_DS = 0
# Must match the render's rule exactly, so ask the same directory it asks. The
# has_mesh column in the CSV is a cached fact about the filesystem and is now
# stale: it says 202 while the rebuilt library holds all 364.
MESHDIR = os.environ.get("RETINA_MESHDIR", r"D:\Meshes\retina\meshes_clean")
with open(r"D:\Meshes\retina\functional_cells.csv", encoding="utf-8") as fh:
    for row in csv.DictReader(fh):
        if row.get("dir_tuning"):
            ALL_N += 1
            if row["is_ds"] in ("True", "true", "1"):
                ALL_DS += 1
        if not os.path.exists(os.path.join(MESHDIR, f"{int(row['root_id'])}.obj")):
            continue
        try:
            tune = json.loads(row["dir_tuning"]) if row["dir_tuning"] else []
        except Exception:
            tune = []
        if not tune:
            continue
        cells.append({"ds": row["is_ds"] in ("True", "true", "1"), "tune": tune,
                      "pref": float(row["pref_dir_deg"]) if row["pref_dir_deg"] else 0.0})
N_DS = sum(c["ds"] for c in cells)
print(f"[ov] {len(cells)} cells, {N_DS} direction selective", flush=True)


def font(sz, bold=False):
    for n in (("seguisb.ttf", "segoeuib.ttf") if bold else ("segoeui.ttf",)):
        try:
            return ImageFont.truetype(n, sz)
        except OSError:
            pass
    return ImageFont.load_default()


def state(fr):
    """Which direction is sweeping, and how strongly, at this frame."""
    if fr < HOLD:
        return None, 0.0
    b = min(NBINS - 1, int((fr - HOLD) // PER))
    t = ((fr - HOLD) % PER) / PER          # 0..1 through this direction
    env = math.sin(math.pi * min(1.0, max(0.0, (t - 0.12) / 0.76))) if 0.12 < t < 0.88 else 0.0
    return b, env


def n_active(b, env):
    """How many cells the render is actually lighting right now.

    Must use the SAME rule as retina_ds_anim.py or the readout contradicts the
    picture. The first version thresholded response times envelope and so read
    0 CELLS RESPONDING mid-sweep while cells were visibly lit. A cell fires at its
    own preferred direction only; the envelope decides whether the pulse is up.

    The rule is the REPORTED preferred angle binned, not argmax of the tuning
    curve. Those are different estimates and they disagreed for 29 of the 64
    cells. See the long note in retina_ds_anim.py.
    """
    if b is None or env <= 0.05:
        return 0
    return sum(1 for c in cells if c["ds"]
               and int(round(c["pref"] / (360.0 / NBINS))) % NBINS == b)


def brackets(d, x, y, w, h, col, ln=14, wd=1):
    for (cx, cy, dx, dy) in ((x, y, 1, 1), (x + w, y, -1, 1),
                             (x, y + h, 1, -1), (x + w, y + h, -1, -1)):
        d.line([cx, cy, cx + dx * ln, cy], fill=col, width=wd)
        d.line([cx, cy, cx, cy + dy * ln], fill=col, width=wd)


def panel(d, x, y, w, h, alpha=170):
    d.rectangle([x, y, x + w, y + h], fill=PANEL + (alpha,))
    brackets(d, x, y, w, h, LINE + (150,))


files = sorted(f for f in os.listdir(A.frames) if f.endswith(".png"))
print(f"[ov] {len(files)} frames", flush=True)

for i, fn in enumerate(files, 1):
    fr = int(fn[1:6])
    im = Image.open(os.path.join(A.frames, fn)).convert("RGBA")
    W, H = im.size
    ov = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    S = W / 1920.0
    f_eyebrow = font(int(15 * S), True)
    f_val = font(int(30 * S), True)
    f_lab = font(int(16 * S))

    b, env = state(fr)
    ang = (360.0 / NBINS) * b if b is not None else 0.0
    col = dir_colour(ang)
    act = n_active(b, env)

    # ---- colour key, lower left: the direction wheel -------------------------
    # The panel is sized from the TEXT, not from the wheel. Sizing it to the wheel
    # left the title and the LEFT/RIGHT labels running under the corner brackets,
    # because both are wider than the dial they annotate.
    KEY_TITLE = "COLOUR = PREFERRED DIRECTION"
    ks = int(210 * S)
    pad = int(20 * S)
    r_k = int(ks * 0.40)
    w_title = d.textlength(KEY_TITLE, font=f_eyebrow)
    w_side = max(d.textlength("LEFT", font=f_lab), d.textlength("RIGHT", font=f_lab))
    # The side labels are drawn CENTRED on a point r + 22 out from the wheel
    # centre, so half the word extends past it. The first fix used the whole word
    # width as if the label started there, which still let LEFT and RIGHT touch
    # the brackets. Half the width is the correct term.
    lab_reach = ks * 0.5 + r_k + int(22 * S) + w_side / 2.0
    inner = max(w_title, lab_reach)
    pw = int(inner + 2 * pad)
    kx = int(56 * S) + pad
    ky = H - int(300 * S)
    panel(d, kx - pad, ky - int(46 * S), pw, ks + int(78 * S))
    d.text((kx, ky - int(34 * S)), KEY_TITLE, font=f_eyebrow, fill=DIM)
    # ONE angle convention everywhere: 0 degrees is to the RIGHT and angles
    # increase anticlockwise, which is how bar_pref_dir is reported. PIL measures
    # its own angles clockwise from 3 o'clock, so a data angle `a` becomes a PIL
    # angle of `-a`, and a screen offset of (cos a, -sin a). Mixing the two is
    # what first put RIGHT at the top of the wheel.
    cx, cy, r = kx + ks // 2, ky + ks // 2, r_k
    for a in range(0, 360, 4):
        d.pieslice([cx - r, cy - r, cx + r, cy + r], -a - 4, -a,
                   fill=dir_colour(a) + (235,))
    d.ellipse([cx - int(r * .52), cy - int(r * .52), cx + int(r * .52), cy + int(r * .52)],
              fill=(7, 8, 11, 255))
    for lab, a in (("UP", 90), ("RIGHT", 0), ("DOWN", 270), ("LEFT", 180)):
        rad = math.radians(a)
        tx = cx + math.cos(rad) * (r + int(22 * S))
        ty = cy - math.sin(rad) * (r + int(22 * S))
        d.text((tx, ty), lab, font=f_lab, fill=DIM, anchor="mm")

    # ---- compass, upper right: which way the bar is moving now ---------------
    bx, by, bs = W - int(250 * S), int(56 * S), int(180 * S)
    panel(d, bx - int(18 * S), by - int(46 * S), bs + int(36 * S), bs + int(56 * S))
    d.text((bx, by - int(34 * S)), "BAR DIRECTION", font=f_eyebrow, fill=DIM)
    mx, my, mr = bx + bs // 2, by + bs // 2, int(bs * 0.38)
    d.ellipse([mx - mr, my - mr, mx + mr, my + mr], outline=LINE + (90,), width=1)
    for k in range(NBINS):
        a = math.radians((360.0 / NBINS) * k)
        x0, y0 = mx + math.cos(a) * mr * 0.86, my - math.sin(a) * mr * 0.86
        x1, y1 = mx + math.cos(a) * mr, my - math.sin(a) * mr
        on = (b is not None and k == b)
        d.line([x0, y0, x1, y1], fill=(col + (255,)) if on else (LINE + (70,)),
               width=2 if on else 1)
    if b is not None:
        a = math.radians(ang)
        hx, hy = mx + math.cos(a) * mr * 0.78, my - math.sin(a) * mr * 0.78
        d.line([mx, my, hx, hy], fill=col + (255,), width=max(2, int(3 * S)))
        for s in (-1, 1):
            aa = a + s * 0.42
            d.line([hx, hy, hx - math.cos(aa) * mr * 0.24,
                    hy + math.sin(aa) * mr * 0.24], fill=col + (255,),
                   width=max(2, int(3 * S)))
        d.text((mx, my + mr + int(20 * S)), f"{int(ang)}\u00B0", font=f_lab,
               fill=INK, anchor="mm")
    else:
        d.text((mx, my + mr + int(20 * S)), "STIMULUS OFF", font=f_lab, fill=DIM,
               anchor="mm")

    # ---- readout, upper left -------------------------------------------------
    # Sized from the STRINGS, not from a constant. The panel was a flat 300 units
    # wide, which fitted "DIRECTION SELECTIVE" and stopped fitting the moment the
    # label grew a denominator. Same failure as the colour key, whose corner
    # brackets cut through LEFT and RIGHT because it was sized to its dial rather
    # than to its text: a hard coded panel width is a caption bug waiting for
    # someone to edit the caption.
    rx, ry = int(56 * S), int(56 * S)
    L_TITLE = "EYEWIRE II  \u00B7  CALCIUM IMAGED"
    L_RESP = "CELLS RESPONDING"
    # Drop the denominator once the film covers everything. "106 OF 106" reads as
    # a hedge and invites the question of what is missing, when the answer is
    # nothing. The fraction earned its place when 42 direction selective cells had
    # no mesh; now that they all do, the plain number is the honest form.
    L_DS = ("DIRECTION SELECTIVE" if N_DS >= ALL_DS
            else f"OF {ALL_DS} DIRECTION SELECTIVE")
    L_TOT = (f"ALL {ALL_N} IMAGED CELLS RECONSTRUCTED" if len(cells) >= ALL_N
             else f"{len(cells)} OF {ALL_N} IMAGED CELLS RECONSTRUCTED")
    # The value and its label sit on one line, so the pair has to be measured
    # together. The count is per frame, so the widest it can ever be is measured
    # rather than the current one, or the panel would breathe frame to frame.
    w_num = max(d.textlength(str(v), font=f_val) for v in (act, N_DS, ALL_DS))
    rw = int(max(d.textlength(L_TITLE, font=f_eyebrow),
                 d.textlength(L_TOT, font=f_lab),
                 w_num + int(10 * S) + max(d.textlength(L_RESP, font=f_lab),
                                           d.textlength(L_DS, font=f_lab)))
             + int(36 * S))
    panel(d, rx - int(18 * S), ry - int(18 * S), rw, int(180 * S))
    d.text((rx, ry), L_TITLE, font=f_eyebrow, fill=DIM)
    d.text((rx, ry + int(26 * S)), f"{act}", font=f_val, fill=WARM)
    wv = d.textlength(f"{act}", font=f_val)
    d.text((rx + wv + int(10 * S), ry + int(38 * S)), L_RESP, font=f_lab, fill=DIM)
    ds_txt = f"{N_DS}"
    d.text((rx, ry + int(76 * S)), ds_txt, font=f_val, fill=INK)
    wv = d.textlength(ds_txt, font=f_val)
    d.text((rx + wv + int(10 * S), ry + int(88 * S)), L_DS, font=f_lab, fill=DIM)
    d.text((rx, ry + int(126 * S)), L_TOT, font=f_lab, fill=DIM)

    Image.alpha_composite(im, ov).convert("RGB").save(
        os.path.join(A.out, fn), quality=95)
    if i % 60 == 0 or i == len(files):
        print(f"[ov] {i}/{len(files)}", flush=True)

print("[ov] DONE", flush=True)
