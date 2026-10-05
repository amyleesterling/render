"""Derive a Blender camera from the live Neuroglancer camera, and PROVE it matches.

The poster has to keep the framing of the banc-explorer Neuroglancer scene. Rather
than eyeball it, the camera is reconstructed from the matrices read out of the
running viewer, then checked by projecting points through both paths and comparing
pixel positions. The check runs on synthetic points, so it needs no meshes and no
GPU.

Spaces, all verified rather than assumed (see `verify()`):

  mesh OBJ vertices : nanometres, isotropic
  neuroglancer world: voxels, v = (x/4, y/4, z/45)   <- what the NG matrices use
  canonical         : 4 nm units, c = nm/4 = v * diag(1,1,11.25)
  blender world     : micrometres, um = nm/1000 = c/250

  python banc_walkingsteering_camera.py          # run the checks, print the camera
"""
import json
import os

import numpy as np

CAM_JSON = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "banc", "walking_steering_camera.json")
W, H = 1600, 1200
ASPECT = W / H
NM_PER_UM = 1000.0
VOXEL = np.array([4.0, 4.0, 45.0])          # nm per voxel, from the layer dimensions
CANON = np.array([1.0, 1.0, 11.25])         # canonicalVoxelFactors, voxel -> 4nm units

# Read straight off the live perspective panel at 1600x1200. gl-matrix column-major.
INV_VIEW = np.array([
    362921.8125, 4935.68994140625, 3277.3583984375, 0,
    739.01025390625, -362482.96875, 3666.67041015625, 0,
    37191.8359375, -40960.36328125, -32053.6640625, 0,
    162289.34375, 81629.140625, -29226.1640625, 1,
]).reshape(4, 4, order="F")
VIEW_PROJ = np.array([
    4.9372479224985e-6, 1.3404816812112585e-8, -2.820221993715677e-7, -2.7943610803049523e-7,
    6.714594036338895e-8, -6.575038241862785e-6, 3.1059857974469196e-7, 3.077504402426712e-7,
    5.642880296363728e-6, 8.417586286668666e-6, 3.0762272217543796e-5, 3.048018697882071e-5,
    -0.6418240070343018, 0.7805529832839966, 0.7185530066490173, 0.9110470414161682,
]).reshape(4, 4, order="F")
NG_POSITION = np.array([125097.5, 122589.5, 2827.5])       # voxels
NG_PROJECTION_SCALE = 302229.5051


def ng_pixel(p_nm):
    """Project nanometre points the way Neuroglancer does. Returns (N,2) pixels."""
    p_nm = np.atleast_2d(np.asarray(p_nm, float))
    v = p_nm / VOXEL                                        # nm -> NG voxel world
    clip = np.c_[v, np.ones(len(v))] @ VIEW_PROJ.T
    ndc = clip[:, :3] / clip[:, 3:4]
    return np.c_[(ndc[:, 0] * 0.5 + 0.5) * W, (0.5 - ndc[:, 1] * 0.5) * H]


def build():
    """Camera basis + position in micrometres, from invViewMatrix."""
    # Columns of invViewMatrix are the camera axes (times a scale) in voxel space.
    # Convert each to canonical 4nm units, where the transform is a pure similarity.
    cols = INV_VIEW[:3, :3] * CANON[:, None]
    norms = np.linalg.norm(cols, axis=0)
    basis = cols / norms                       # [right | up | back], camera looks along -back
    pos_c = INV_VIEW[:3, 3] * CANON
    return basis, pos_c, norms


def verify():
    basis, pos_c, norms = build()
    ok = []

    # 1. The three columns must share one scale, else the space is not isotropic.
    ok.append(("invView columns share a scale (space is isotropic in canonical units)",
               np.allclose(norms, norms[0], rtol=1e-6), f"norms={norms.round(1)}"))

    # 2. Basis must be orthonormal and right-handed.
    ok.append(("camera basis orthonormal", np.allclose(basis.T @ basis, np.eye(3), atol=1e-5),
               f"max off-diag={np.abs(basis.T @ basis - np.eye(3)).max():.2e}"))
    ok.append(("camera basis right-handed", np.linalg.det(basis) > 0,
               f"det={np.linalg.det(basis):.6f}"))

    # 3. Walking from the camera along -back by the column scale must land on the
    #    navigation position. This is what pins the target, rather than assuming it.
    target_c = pos_c + (-basis[:, 2]) * norms[0]
    target_v = target_c / CANON
    ok.append(("recovered target == state position",
               np.allclose(target_v, NG_POSITION, atol=1e-2),
               f"recovered={target_v.round(3)} expected={NG_POSITION}"))

    # 4. projectionScale must be the visible height at the target plane.
    fovy = 2 * np.arctan(1.0 / 2.4142136573791504)
    implied = 2 * norms[0] * np.tan(fovy / 2)
    ok.append(("projectionScale == visible height at target",
               abs(implied - NG_PROJECTION_SCALE) < 1.0,
               f"implied={implied:.3f} state={NG_PROJECTION_SCALE}"))
    ok.append(("vertical fov is 45 deg", abs(np.degrees(fovy) - 45) < 1e-4,
               f"{np.degrees(fovy):.6f} deg"))

    # 5. The real test: project random points both ways and compare pixels.
    #    Control: a deliberately wrong camera must FAIL this, otherwise the test
    #    would pass no matter what and would prove nothing.
    rng = np.random.default_rng(0)
    pts_nm = np.c_[rng.uniform(3.8e5, 6.2e5, 400),
                   rng.uniform(1.3e5, 9.1e5, 400),
                   rng.uniform(1.4e4, 2.9e5, 400)]

    def mine(p_nm, b=basis, pc=pos_c):
        c = np.asarray(p_nm, float) / 4.0                   # nm -> canonical
        eye = (c - pc) @ b                                  # world -> camera
        t = np.tan(fovy / 2)
        ndc_x = (eye[:, 0] / -eye[:, 2]) / (t * ASPECT)
        ndc_y = (eye[:, 1] / -eye[:, 2]) / t
        return np.c_[(ndc_x * 0.5 + 0.5) * W, (0.5 - ndc_y * 0.5) * H]

    err = np.abs(mine(pts_nm) - ng_pixel(pts_nm)).max()
    ok.append(("reconstructed camera matches NG to <0.01 px", err < 0.01,
               f"max error {err:.6f} px over 400 points"))

    bad_basis = basis.copy()
    bad = mine(pts_nm, b=bad_basis, pc=pos_c + np.array([0, 0, 5000.0]))
    ctrl = np.abs(bad - ng_pixel(pts_nm)).max()
    ok.append(("CONTROL: camera nudged 20um fails the same test", ctrl > 1.0,
               f"max error {ctrl:.3f} px (must be large)"))

    print("camera checks")
    for name, passed, detail in ok:
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}\n         {detail}")
    assert all(p for _, p, _ in ok), "camera reconstruction is not trustworthy"
    return basis, pos_c


def main():
    basis, pos_c = verify()
    pos_um = pos_c / (NM_PER_UM / 4.0)          # canonical (4nm) -> micrometres
    m = np.eye(4)
    m[:3, :3] = basis
    m[:3, 3] = pos_um
    cam = {
        "_note": "Blender camera reproducing the banc-explorer Neuroglancer framing. "
                 "World units are MICROMETRES: import the nm OBJs and scale by 0.001. "
                 "matrix_world is row-major 4x4, ready for Matrix(...) in Blender.",
        "resolution": [W, H],
        "lens": {"type": "PERSP", "sensor_fit": "VERTICAL", "angle_y_deg": 45.0},
        "_lens_note": "sensor_fit MUST be VERTICAL. Blender's default AUTO fits the "
                      "LARGER axis, which on a 4:3 landscape frame is the width, and "
                      "the subject would be framed on the wrong axis.",
        "matrix_world": [[float(x) for x in row] for row in m],
        "location_um": [float(x) for x in pos_um],
        "look_at_um": [float(x) for x in (pos_c + (-basis[:, 2]) * np.linalg.norm(
            INV_VIEW[:3, 0] * np.array([1, 1, 11.25]))) / 250.0],
        "clip": {"start_um": 1.0, "end_um": 6000.0},
        "provenance": "invViewMatrix + viewProjectionMat read from the live "
                      "spelunker.cave-explorer.org perspective panel sized to 1600x1200",
    }
    os.makedirs(os.path.dirname(CAM_JSON), exist_ok=True)
    json.dump(cam, open(CAM_JSON, "w"), indent=1)
    print(f"\nwrote {CAM_JSON}")
    print("  location (um):", np.round(pos_um, 3))
    print("  look at  (um):", np.round(np.array(cam["look_at_um"]), 3))
    print("  distance (um):", round(float(np.linalg.norm(
        np.array(cam["look_at_um"]) - pos_um)), 3))
    print("  visible height at target (um):", round(NG_PROJECTION_SCALE / 250.0, 3))


if __name__ == "__main__":
    main()
