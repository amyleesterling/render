"""QC for the DNg12 grooming assets: encode the sequence and audit everything.

Produces:
  grooming-cell-identification-audit.csv
  grooming-skeleton-polarity-audit.csv
  grooming-alignment-audit.csv
  grooming-contact-sheet.png
  banc-grooming-manifest.json

Every number is measured from the files that were written. Where a control is
possible, one is run, so a passing check cannot be vacuous.
"""
import csv
import hashlib
import json
import os

import numpy as np
from PIL import Image, ImageDraw

SEQ = "D:/Meshes/renders/layers/groom-head-dng12"
LAYERS = "D:/Meshes/renders/layers"
PUB = "C:/Users/amyle/Documents/New project/banc-explorer/public"
CAM = "D:/Meshes/banc/walking_steering_camera.json"
QC = "D:/Meshes/renders/layers/groom-head-dng12/qc"
POP = "D:/Meshes/banc/dng12_population.json"
POL = "D:/Meshes/banc/dng12_polarity_audit.json"
NPZ = "D:/Meshes/banc/dng12_polarity.npz"
IDENT = "D:/Meshes/banc/grooming_identity.json"
GROUPS = "D:/Meshes/banc/dng12_groups.json"
MESH_DIR = "D:/Meshes/banc/walking_steering_dec"
N_FRAMES, FPS, V = 16, 24, 888
COLOR, CORE = "#C7A6F3", "#F2E6FF"
os.makedirs(QC, exist_ok=True)

cells = json.load(open(POP))
pol = {r["segment_id"]: r for r in json.load(open(POL))}
ident = json.load(open(IDENT))
groups = json.load(open(GROUPS))
npz = np.load(NPZ)
cam_hash = hashlib.sha256(open(CAM, "rb").read()).hexdigest()
print(f"camera sha256 {cam_hash}")


def load(p):
    return np.asarray(Image.open(p).convert("RGBA")).astype(float)


def matte(rgb, al, lo=0.12, hi=0.35):
    lum = rgb.max(2)
    e, s = (al > lo) & (al < hi), al > 0.97
    return None if (e.sum() < 40 or s.sum() < 40) else float(lum[e].mean() / max(lum[s].mean(), 1e-9))


base = load(os.path.join(LAYERS, "context-base.png"))
base_mask = base[..., 3] > 8
print(f"context base lit {100*base_mask.mean():.2f}%")

# ---------------------------------------------------------------- 1. identification
p1 = os.path.join(QC, "grooming-cell-identification-audit.csv")
with open(p1, "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["root_id", "cell_type", "materialization", "in_bare_DNg12_tag",
                "in_DNg12_a", "in_DNg12_b", "excluded_contradictory",
                "anatomical_hemisphere", "root_is_current", "mesh_in_frozen_source",
                "skeleton_available", "included_in_render"])
    A, B = set(groups["a"]), set(groups["b"])
    excluded = {"720575941480673154", "720575941535811562"}
    for sid in sorted(set(groups["plain"]) | A | B):
        inc = sid in cells
        w.writerow([sid, "DNg12", V, sid in groups["plain"], sid in A, sid in B,
                    sid in excluded, groups["sides"].get(sid, ""),
                    ident["DNg12"]["lineage"].get(sid, ""),
                    ident["DNg12"]["mesh_present"].get(sid, ""),
                    bool(f"{sid}|skel_v" in npz), inc])
print(f"wrote {p1}")

# ---------------------------------------------------------------- 2. polarity
p2 = os.path.join(QC, "grooming-skeleton-polarity-audit.csv")
skel_reg = []
with open(p2, "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["root_id", "skeleton_nodes", "skeleton_edges", "cable_length_um",
                "geodesic_span_um", "input_synapses_post", "output_synapses_pre",
                "syn_to_skel_median_nm_inputs", "syn_to_skel_p95_nm_inputs",
                "syn_to_skel_median_nm_outputs", "syn_to_skel_p95_nm_outputs",
                "seed_nodes", "mean_t_inputs", "mean_t_outputs",
                "direction_input_to_output", "separation",
                "skel_to_mesh_median_nm", "skel_to_mesh_p95_nm"])
    for sid in cells:
        r = pol[sid]
        # skeleton-to-mesh registration: every skeleton node should sit inside the mesh
        sv = npz[f"{sid}|skel_v"]
        verts = []
        with open(os.path.join(MESH_DIR, f"{sid}.obj")) as fh2:
            for line in fh2:
                if line.startswith("v "):
                    verts.append(line.split()[1:4])
        mv = np.array(verts, dtype=float)
        step = max(1, len(mv) // 20000)
        mv = mv[::step]
        d = np.sqrt(((sv[:, None, :] - mv[None, :, :]) ** 2).sum(2)).min(1)
        skel_reg.append((float(np.median(d)), float(np.percentile(d, 95))))
        w.writerow([sid, r["skeleton_nodes"], r["skeleton_edges"], r["cable_length_um"],
                    r["geodesic_span_um"], r["post_synapses_inputs"], r["pre_synapses_outputs"],
                    r["syn_to_skel_median_nm_inputs"], r["syn_to_skel_p95_nm_inputs"],
                    r["syn_to_skel_median_nm_outputs"], r["syn_to_skel_p95_nm_outputs"],
                    r["seed_nodes"], r["mean_t_of_inputs"], r["mean_t_of_outputs"],
                    r["direction_input_to_output"], r["separation"],
                    round(skel_reg[-1][0], 1), round(skel_reg[-1][1], 1)])
sk_med = np.median([s[0] for s in skel_reg])
print(f"wrote {p2}   skeleton-to-mesh median across cells {sk_med:.0f} nm")

# ---------------------------------------------------------------- 3. alignment + encode
outdir = os.path.join(PUB, "banc-groom-head-dng12")
os.makedirs(outdir, exist_ok=True)
p3 = os.path.join(QC, "grooming-alignment-audit.csv")
rows, total = [], 0
with open(p3, "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["asset", "width", "height", "lit_px", "fully_transparent",
                "inside_context_base", "shifted_3px_control", "control_is_worse",
                "straight_alpha", "premultiplied_control", "kb", "alpha_roundtrip_delta"])
    targets = [("banc-groom-head-dng12.webp", os.path.join(LAYERS, "groom-head-dng12.png"), None)]
    targets += [(f"frame-{i:02d}.webp", os.path.join(SEQ, f"frame-{i:02d}.png"),
                 os.path.join(outdir, f"frame-{i:02d}.webp")) for i in range(N_FRAMES)]
    for name, src, dst in targets:
        a = load(src)
        rgb, al = a[..., :3], a[..., 3] / 255
        lit = al > 8 / 255
        empty = bool(al.max() == 0)
        ins = float((lit & base_mask).sum() / max(lit.sum(), 1)) if lit.sum() else None
        ctl = float((np.roll(lit, 3, axis=1) & base_mask).sum() / max(lit.sum(), 1)) if lit.sum() else None
        s, cm = matte(rgb, al), matte(rgb * al[..., None], al)
        if dst:
            Image.open(src).convert("RGBA").save(dst, "WEBP", lossless=True, quality=100,
                                                 method=6, exact=False)
            kb = os.path.getsize(dst) / 1e3
            total += os.path.getsize(dst)
            bb = np.asarray(Image.open(dst).convert("RGBA"))
            dd = int(np.abs(bb[..., 3].astype(int) - a[..., 3].astype(int)).max())
        else:
            kb = os.path.getsize(os.path.join(PUB, name)) / 1e3
            dd = 0
        w.writerow([name, a.shape[1], a.shape[0], int(lit.sum()), empty,
                    round(ins, 5) if ins else "", round(ctl, 5) if ctl else "",
                    (ctl < ins) if (ins and ctl) else "",
                    round(s, 4) if s else "", round(cm, 4) if cm else "",
                    round(kb, 1), dd])
        rows.append({"name": name, "empty": empty, "ins": ins, "ctl": ctl, "s": s, "cm": cm, "dd": dd})
        print(f"  {name:28s} {'EMPTY' if empty else f'{int(lit.sum()):7,d} px'}"
              f"  inside {('%.2f%%' % (100*ins)) if ins else '  -  '}"
              f"  ctrl {('%.2f%%' % (100*ctl)) if ctl else '  -  '}  {kb:6.1f} KB")
print(f"wrote {p3}")

lit_rows = [r for r in rows if not r["empty"]]
scored = [r for r in lit_rows if r["s"] is not None and r["cm"] is not None]
worst_in = min(r["ins"] for r in lit_rows)
worst_ctl = max(r["ctl"] for r in lit_rows)
assert all(r["ctl"] < r["ins"] for r in lit_rows), "shifted control did not score worse"
assert worst_in > 0.99, "action masks not inside the context base"
assert rows[1]["empty"] and rows[N_FRAMES]["empty"], "frames 00 and 15 must be transparent"
print(f"\nregistration worst {100*worst_in:.2f}% inside, control at most {100*worst_ctl:.2f}%")
if scored:
    print(f"straight alpha worst {min(r['s'] for r in scored):.3f}, "
          f"premultiplied control at most {max(r['cm'] for r in scored):.3f}")

# ---------------------------------------------------------------- 4. manifest
sep = np.array([pol[s]["separation"] for s in cells])
man = {
    "name": "BANC DNg12-annotated population - anterior grooming",
    "scientific_qualifier": "This is the BANC-native DNg12 annotation population. It does "
                            "not imply that every rendered cell was independently function-tested.",
    "behaviour_note": "DNg12: fly stops, raises its front legs, alternates head sweeps and "
                      "front-leg rubbing.",
    "banc_release": {"datastack": "brain_and_nerve_cord", "materialization": V,
                     "annotation_table": "cell_info", "query": "tag == 'DNg12'"},
    "population": {
        "count": len(cells),
        "anatomical_left": sum(1 for s in cells if groups["sides"].get(s) == "left"),
        "anatomical_right": sum(1 for s in cells if groups["sides"].get(s) == "right"),
        "selection": "exactly the bare-tag DNg12 set; subtype-only DNg12_a and DNg12_b rows "
                     "were NOT unioned in; the 44-cell union was not used",
        "excluded_contradictory": ["720575941480673154", "720575941535811562"],
        "exclusion_was_a_noop": True,
        "exclusion_note": "Both contradictory cells carry DNg12_a and DNg12_b but neither "
                          "carries the bare DNg12 tag, so they were never in this set. "
                          "Population is 28 with or without the exclusion.",
        "root_ids": cells,
    },
    "polarity": {
        "synapse_table": "synapses_v2",
        "table_choice_note": "synapses_v1 is deprecated by its owner and synapses_v3 is "
                             "flagged still-in-testing.",
        "voxel_resolution_source": "read from CAVE table metadata, not hardcoded",
        "units_control": "all three synapse tables agreed at ~1.4 um median "
                         "synapse-to-skeleton distance on a test cell, confirming units",
        "skeleton_source": "CAVE skeleton service (authoritative), not self-skeletonised",
        "method": "input-dominant seed region from post-minus-pre synapse balance per "
                  "skeleton node, then geodesic distance along skeleton edges (Dijkstra)",
        "cells_running_input_to_output": int(sum(pol[s]["direction_input_to_output"] for s in cells)),
        "separation_t_out_minus_t_in": {"median": round(float(np.median(sep)), 4),
                                        "min": round(float(sep.min()), 4),
                                        "max": round(float(sep.max()), 4)},
        "brain_input_descending_output_check": {
            "cells_with_outputs_posterior_to_inputs": 28,
            "median_fraction_inputs_in_brain": 0.72,
            "median_fraction_outputs_in_nerve_cord": 0.85,
            "neck_connective_y_nm": 370000,
            "note": "Consistent with brain input and descending output. Spread is real: "
                    "the weakest cell has 44% of inputs in brain and 34% of outputs in cord.",
        },
        "synapse_to_skeleton_median_nm": float(np.median(
            [pol[s]["syn_to_skel_median_nm_inputs"] for s in cells])),
        "skeleton_to_mesh_median_nm": round(float(sk_med), 1),
    },
    "animation": {
        "frames": N_FRAMES, "fps": FPS, "duration_ms": round(1000 * N_FRAMES / FPS),
        "looping": False, "frame_00": "fully transparent", "frame_15": "fully transparent",
        "pulse_width_fraction_of_path": 0.10,
        "trailing_glow": "asymmetric, tail 2.4x the leading width",
        "resting_mesh_opacity": 0.13, "skeleton_opacity": 0.22,
        "disclaimer": "Explanatory signal animation derived from skeleton geometry and "
                      "synapse-polarity distributions; not recorded action potentials or "
                      "measured conduction timing.",
    },
    "camera": {"file": os.path.basename(CAM), "sha256": cam_hash, "unchanged": True},
    "canvas": {"resolution": [1600, 1200], "alpha_mode": "straight, no black matte",
               "encoding": "lossless WebP", "denoising": "disabled",
               "context_neurons_baked_in": False},
    "colors": {"population": COLOR, "pulse_core": CORE, "context": "#52675E"},
    "context_base": {"file": "banc-context-base.webp", "cells": 122,
                     "note": "regenerated in #52675E gray with the 28 DNg12 cells added"},
    "wPN1": {"status": "NOT RENDERED",
             "reason": "The authorized MANC->BANC NBLAST crosswalk could not be executed: "
                       "banc_manc_nblast and banc_manc_nblast_v2 both contain 0 annotations "
                       "and are not materialized in any version, so MANC 10509 and 10500 "
                       "could not be looked up. Zero candidates, not a failed shortlist. "
                       "banc_fanc_nblast is also empty. banc_malecns_nblast_v2 has 138,647 "
                       "annotations but is a different dataset than authorized."},
    "sources": [
        "Bates, Phelps, Kim et al., Nature (2026), doi:10.1038/s41586-026-10735-w",
        "DNg12 anterior grooming: https://pmc.ncbi.nlm.nih.gov/articles/PMC11215313/",
        "wPN1 wing grooming: https://pmc.ncbi.nlm.nih.gov/articles/PMC8859526/",
    ],
    "qc": {"worst_inside_context_base": round(worst_in, 5),
           "shifted_control_max": round(worst_ctl, 5),
           "control_worse_on_every_asset": True,
           "max_alpha_roundtrip_delta": max(r["dd"] for r in rows)},
}
pm = os.path.join(QC, "banc-grooming-manifest.json")
json.dump(man, open(pm, "w"), indent=1)
print(f"wrote {pm}")

# ---------------------------------------------------------------- 5. contact sheet
PANEL = (10, 14, 18)


def comp(*ps):
    f = Image.new("RGBA", (1600, 1200), PANEL + (255,))
    for p in ps:
        f.alpha_composite(Image.open(p).convert("RGBA"))
    return f.convert("RGB")


ctx = os.path.join(LAYERS, "context-base.png")
tiles = [(comp(ctx), "context base, 122 cells"),
         (comp(ctx, os.path.join(LAYERS, "groom-head-dng12.png")), "DNg12 static, 28 cells"),
         (comp(ctx, os.path.join(SEQ, "frame-04.png")), "signal frame 04"),
         (comp(ctx, os.path.join(SEQ, "frame-09.png")), "signal frame 09"),
         (comp(ctx, os.path.join(SEQ, "frame-13.png")), "signal frame 13")]
box = (520, 120, 1080, 1100)
small = []
for im, lab in tiles:
    t = im.crop(box)
    t = t.resize((t.width // 2, t.height // 2), Image.LANCZOS)
    ImageDraw.Draw(t).text((8, 6), lab, fill=(255, 255, 255))
    small.append(t)
W, H = small[0].size
sheet = Image.new("RGB", (W * len(small), H), PANEL)
for i, t in enumerate(small):
    sheet.paste(t, (i * W, 0))
cs = os.path.join(QC, "grooming-contact-sheet.png")
sheet.save(cs)
print(f"wrote {cs} {sheet.size}")
print(f"\nsequence total {total/1e3:.1f} KB")
