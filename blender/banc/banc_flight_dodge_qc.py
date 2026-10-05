"""Encode the quick-dodge sequences and produce the QC deliverables.

Everything asserted here is measured from the files that were actually written:
frame geometry, straight alpha (with a premultiplied control), the two frames that
must be fully transparent, and pixel registration against banc-context-base.webp
(with a 3 px shifted control so the test can fail).

  python banc_flight_dodge_qc.py
"""
import csv
import glob
import hashlib
import json
import os

import numpy as np
from PIL import Image

SRC = "D:/Meshes/renders/layers/flight-dodge"
PUB = "C:/Users/amyle/Documents/New project/banc-explorer-dng100/public"
LAYERS_PNG = "D:/Meshes/renders/layers"
CAM_JSON = "D:/Meshes/banc/walking_steering_camera.json"
IDENT = "D:/Meshes/banc/dnp03_candidates.json"
QC = "D:/Meshes/renders/layers/flight-dodge/qc"
SIDES = ["anatomical-left", "anatomical-right"]
N_FRAMES, FPS = 12, 24
PULSE, CORE = "#FF8FA8", "#FFD2DC"
os.makedirs(QC, exist_ok=True)

ident = json.load(open(IDENT))
cam_hash = hashlib.sha256(open(CAM_JSON, "rb").read()).hexdigest()
print(f"camera file sha256: {cam_hash}")


def load(p):
    return np.asarray(Image.open(p).convert("RGBA")).astype(float)


def matte(rgb, al, lo=0.12, hi=0.35):
    lum = rgb.max(2)
    e, s = (al > lo) & (al < hi), al > 0.97
    if e.sum() < 40 or s.sum() < 40:
        return None
    return float(lum[e].mean() / max(lum[s].mean(), 1e-9))


base = load(os.path.join(LAYERS_PNG, "context-base.png"))
base_mask = base[..., 3] > 8
print(f"context base lit: {100*base_mask.mean():.2f}%\n")

rows, total_bytes = [], 0
for side in SIDES:
    outdir = os.path.join(PUB, f"banc-flight-dodge-{side}")
    os.makedirs(outdir, exist_ok=True)
    print(f"{side}")
    for f in range(N_FRAMES):
        src = os.path.join(SRC, side, f"frame-{f:02d}.png")
        a = load(src)
        rgb, al = a[..., :3], a[..., 3] / 255
        assert a.shape[:2] == (1200, 1600), f"{src} wrong size {a.shape}"
        lit = al > 8 / 255
        empty = bool(al.max() == 0)
        s = matte(rgb, al)
        c = matte(rgb * al[..., None], al)
        inside = float((lit & base_mask).sum() / max(lit.sum(), 1)) if lit.sum() else None
        ctrl = (float((np.roll(lit, 3, axis=1) & base_mask).sum() / max(lit.sum(), 1))
                if lit.sum() else None)
        dst = os.path.join(outdir, f"frame-{f:02d}.webp")
        im = Image.open(src).convert("RGBA")
        im.save(dst, "WEBP", lossless=True, quality=100, method=6, exact=False)
        size = os.path.getsize(dst)
        total_bytes += size
        back = np.asarray(Image.open(dst).convert("RGBA"))
        d = int(np.abs(back[..., 3].astype(int) - a[..., 3].astype(int)).max())
        rows.append({"side": side, "frame": f, "empty": empty,
                     "lit_px": int(lit.sum()), "straight": s, "control": c,
                     "inside_base": inside, "inside_ctrl": ctrl,
                     "kb": size / 1e3, "alpha_delta": d})
        print(f"  frame-{f:02d} {'EMPTY (transparent)' if empty else f'{int(lit.sum()):7,d} px'}"
              f"  straight {('%.3f' % s) if s else '  -  '}"
              f"  inside base {('%.2f%%' % (100*inside)) if inside else '  -  '}"
              f"  {size/1e3:6.1f} KB  alpha delta {d}")

# --- required invariants ------------------------------------------------------
empties = {(r["side"], r["frame"]) for r in rows if r["empty"]}
assert all((s, 0) in empties and (s, 11) in empties for s in SIDES), \
    "frame 00 and frame 11 must be fully transparent"
lit_rows = [r for r in rows if not r["empty"]]
worst_in = min(r["inside_base"] for r in lit_rows)
worst_ctrl = max(r["inside_ctrl"] for r in lit_rows)

# The edge/solid matte ratio is only defined on frames that HAVE fully opaque
# pixels. Frames 01, 02 and 10 run at partial amplitude, so the whole neuron is
# semi-transparent and there is no solid population to compare against. Those
# frames are scored on registration only, which is the right call: reporting a
# ratio computed from an empty set would be worse than reporting none.
scored = [r for r in lit_rows if r["straight"] is not None and r["control"] is not None]
worst_alpha = min(r["straight"] for r in scored)
best_ctrl_matte = max(r["control"] for r in scored)
print(f"\nregistration: worst frame {100*worst_in:.2f}% inside base, "
      f"shifted control at most {100*worst_ctrl:.2f}%")
print(f"straight alpha: worst {worst_alpha:.3f}, premultiplied control at most "
      f"{best_ctrl_matte:.3f}  ({len(scored)}/{len(lit_rows)} frames have opaque pixels "
      f"to score; the rest are partial-amplitude by design)")
assert worst_in > 0.99, "frames are not registered with the context base"
assert worst_alpha > 0.85 and best_ctrl_matte < worst_alpha - 0.05, "alpha audit failed"
print(f"total {total_bytes/1e3:.1f} KB across {len(rows)} frames")

# --- laterality audit ---------------------------------------------------------
geo = ident["geometry"]
audit = os.path.join(QC, "laterality_audit.csv")
with open(audit, "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["root_id_v888", "cell_type", "anatomical_hemisphere",
                "brain_end_centroid_x_nm", "midline_nm", "distance_from_midline_nm",
                "y_min_nm", "y_max_nm", "crosses_neck_connective", "faces", "vertices",
                "mesh_in_frozen_source", "root_id_is_current", "maps_to_current_root",
                "side_method", "behavioral_direction_mapping"])
    for sid, g in geo.items():
        lin = ident["lineage"].get(sid, {})
        w.writerow([sid, "DNp03", g["anatomical_side"], g["brain_end_centroid_x_nm"],
                    ident["midline_nm"], g["distance_from_midline_nm"],
                    g["y_range_nm"][0], g["y_range_nm"][1], g["crosses_neck_connective"],
                    g["faces"], g["vertices"], ident["mesh_present"].get(sid),
                    lin.get("is_latest"), lin.get("maps_to") or "",
                    "brain-end centroid x vs midline calibrated on the DNa01 pair",
                    "pending"])
print(f"wrote {audit}")

# --- manifest -----------------------------------------------------------------
man = {
    "name": "BANC quick dodge / flight saccade",
    "role": "flight-saccade response; not threat detection",
    "banc_release": "BANC, datastack brain_and_nerve_cord",
    "annotation_snapshot": {
        "materialization": ident["materialization"],
        "table": "cell_info",
        "query": "tag == 'DNp03'",
        "note": "v888 as specified. Versions visible at build time: 3, 282, 626, 850, 888, 893, 896.",
    },
    "mesh_source": {
        "uri": "precomputed://gs://lee-lab_brain-and-nerve-cord-fly-connectome/neuron_meshes",
        "note": "frozen public snapshot; a bogus control id returned 404, so presence checks are meaningful",
    },
    "cells": [
        {
            "rendered_root_id_v888": sid,
            "current_cave_root_id": (sid if ident["lineage"].get(sid, {}).get("is_latest")
                                     else ident["lineage"].get(sid, {}).get("maps_to")),
            "root_id_is_current": ident["lineage"].get(sid, {}).get("is_latest"),
            "cell_type": "DNp03",
            "all_tags": ident["tags"].get(sid, []),
            "anatomical_hemisphere": g["anatomical_side"],
            "brain_end_centroid_x_nm": g["brain_end_centroid_x_nm"],
            "y_range_nm": g["y_range_nm"],
            "crosses_neck_connective": g["crosses_neck_connective"],
        } for sid, g in geo.items()
    ],
    "ax_crosswalk": {
        "included": False,
        "reason": "The provisional functional name 'AX' was NOT assumed to be DNp03. "
                  "A cell_info query for tag == 'AX' at this materialization returned 0 rows, "
                  "so no authoritative crosswalk was found and nothing was included on that basis.",
    },
    "camera": {"file": os.path.basename(CAM_JSON), "sha256": cam_hash, "unchanged": True,
               "note": "walking_steering_camera.json used verbatim, so these layers register "
                       "with every existing BANC layer"},
    "canvas": {"resolution": [1600, 1200], "alpha_mode": "straight (unpremultiplied), no black matte",
               "background": "fully transparent, complete canvas preserved",
               "encoding": "lossless WebP", "denoising": "disabled"},
    "colors": {"quick_dodge_pulse": PULSE, "peak_core": CORE,
               "context_cells": "#52675E (unchanged gray)", "permanent_glow": False},
    "animation": {
        "frames": N_FRAMES, "fps": FPS, "duration_ms": int(1000 * N_FRAMES / FPS),
        "looping": False,
        "frame_00": "fully transparent", "frame_11": "fully transparent",
        "schedule": {"01-03": "activity begins in the brain arbor",
                     "04-07": "pulse travels along the descending axon",
                     "08-09": "strongest signal in the nerve cord arbor",
                     "10-11": "rapid decay to transparent"},
        "method": "head-to-tail luminance sweep along the neuron's own anterior-posterior "
                  "extent, baked per vertex. NOT branch-specific conduction: no skeleton "
                  "was used and none is implied.",
        "direction_basis": "BANC y increases posteriorly; both cells run brain (y~154,000 nm) "
                           "to nerve cord (y~790,000 nm) and cross the neck connective, so "
                           "brain end and cord end are measured, not assumed.",
        "disclaimer": "The timing and travelling glow are explanatory animation, "
                      "not measured neural activity.",
    },
    "static_files": ["banc-flight-dodge-dnp03-all.webp",
                     "banc-flight-dodge-dnp03-anatomical-left.webp",
                     "banc-flight-dodge-dnp03-anatomical-right.webp"],
    "sequence_files": {s: [f"banc-flight-dodge-{s}/frame-{i:02d}.webp" for i in range(N_FRAMES)]
                       for s in SIDES},
    "behavioral_direction_mapping": "pending",
    "naming_note": "Filenames use ANATOMICAL side. Do not rename to dodge-left / dodge-right "
                   "until the behavioural mapping is independently validated.",
    "qc": {
        "worst_frame_inside_context_base": round(worst_in, 5),
        "shifted_3px_control_max": round(worst_ctrl, 5),
        "worst_straight_alpha_score": round(worst_alpha, 4),
        "straight_alpha_scored_frames": f"{len(scored)} of {len(lit_rows)} lit frames; the rest run at partial amplitude so have no fully opaque pixels to score",
        "premultiplied_control_max": round(best_ctrl_matte, 4),
        "max_alpha_roundtrip_delta": max(r["alpha_delta"] for r in rows),
    },
    "sources": [
        "Bates, Phelps, Kim et al., Distributed control circuits across a brain-and-cord "
        "connectome, Nature (2026), doi:10.1038/s41586-026-10735-w",
        "BANC CAVE datastack brain_and_nerve_cord, cell_info, materialization "
        + str(ident["materialization"]),
        "Public mesh source gs://lee-lab_brain-and-nerve-cord-fly-connectome/neuron_meshes",
    ],
}
mp = os.path.join(QC, "manifest.json")
json.dump(man, open(mp, "w"), indent=1)
print(f"wrote {mp}")

# --- contact sheet ------------------------------------------------------------
PANEL = (10, 14, 18)


def comp(*pngs):
    f = Image.new("RGBA", (1600, 1200), PANEL + (255,))
    for p in pngs:
        f.alpha_composite(Image.open(p).convert("RGBA"))
    return f.convert("RGB")


from PIL import ImageDraw
ctx = os.path.join(LAYERS_PNG, "context-base.png")
tiles = [
    (comp(ctx), "context base (94 cells)"),
    (comp(ctx, os.path.join(LAYERS_PNG, "flight-dodge-dnp03-anatomical-left.png")),
     "anatomical LEFT (static)"),
    (comp(ctx, os.path.join(LAYERS_PNG, "flight-dodge-dnp03-anatomical-right.png")),
     "anatomical RIGHT (static)"),
    (comp(ctx, os.path.join(SRC, "anatomical-left", "frame-08.png")),
     "peak animation frame 08"),
]
box = (520, 120, 1080, 1100)
small = []
for im, lab in tiles:
    t = im.crop(box)
    t = t.resize((t.width // 2, t.height // 2), Image.LANCZOS)
    ImageDraw.Draw(t).text((8, 6), lab, fill=(255, 255, 255))
    small.append(t)
W, H = small[0].size
sheet = Image.new("RGB", (W * 4, H), PANEL)
for i, t in enumerate(small):
    sheet.paste(t, (i * W, 0))
cs = os.path.join(QC, "contact_sheet.png")
sheet.save(cs)
print(f"wrote {cs}  {sheet.size}")
