"""Beats 1 to 7 of the selective feedforward inhibition shot.

Driven from hero_full.py as `scope=inhibition`, which opens ca3_scene.blend and
hands this module the ca3_animation globals. Nothing here runs on its own.

  blender --background --python hero_full.py -- scope=inhibition [key=val]
      frames=432  res=1920x1080  samples=64  out=path
      still=N            one frame
      beats=1,4,5        one frame at the middle of each named beat, to
                         <out stem>_b<N>.png, all from a single scene build
      at=28,142,432      stills at explicit frame numbers, same single build.
                         The wide beats settle at their END frame, not their
                         midpoint, so this is what they have to be checked with.
      far= open= mid= near= fill= margin= aimdrop= shifty= arc= lens= dimmf=
                         framing and brightness controls, all with solved or
                         measured defaults

Everything on screen is measured. The 333 synapses onto 87 thorny cells and the
50 onto 21 sparsely thorny cells come from renders/_out_648518346437066458.csv,
already filtered for autapses, and the arrival time of every one of those cells
is its real path distance from the interneuron's soma, out of
skeletons/inhib_fields.npz. See inhib_fields.py for how that field is built and
for the three things that had to be measured rather than assumed.

Two departures from STORYBOARD_inhibition.md, both forced by measurement and both
written up in the report:

  * Beat 4. The storyboard says the two subtypes separate in z, superficial blue
    over deeper purple, at mean z 60,927 against 67,409 nm. That does not
    reproduce. Measured from renders/soma.parquet, the project's own soma table:
    182 thorny somata sit at mean z 74,070 nm (sd 4,835) and 68 sparsely thorny
    at 73,190 nm (sd 5,561). That is 0.9 um apart against a 5.2 um pooled spread,
    Cohen's d = 0.17, and the sign is the other way round. There is no z sublayer
    here and a side on camera would show nothing.
    What DOES separate them is the radial axis of the curved CA3 layer, from
    renders/soma3d.parquet: thorny at radial -2.8 um (sd 33.9), sparsely thorny
    at +61.6 um (sd 50.5), a 64 um offset at Cohen's d = 1.50. That axis lies in
    the xy plane, so the camera holds a FACE ON view of the slab and the purple
    population reads as sitting outside the blue arc.

  * Beat 5 runs the wave along a surface path field, not a skeleton. meshparty's
    skeleton of this cell misses the axon: only 8 percent of its outgoing
    synapses land within 2 um of it, median 19 um away. See inhib_fields.py.
"""
import math
import os
import time

import bpy
import numpy as np
from mathutils import Vector

INTER_ID = "648518346437066458"
HERO_MF = "648518346430566932"
# The other six mossy fibres that contact this interneuron. Verified against
# renders/mf_synapses.csv: seven fibres, one synapse each, seven in total.
SUPPORT_MF = ["648518346464178392", "648518346442262773", "648518346446894282",
              "648518346438632308", "648518346445589428", "648518346446219982"]
SEVEN = [HERO_MF] + SUPPORT_MF
FIELDS = r"D:/Meshes/skeletons/inhib_fields.npz"

# House palette, now also the values in ca3_animation.GROUPS. See the report and
# the comment on GROUPS["mossy_fibers"].
GOLD = "#E8A93A"
BLUE = "#2E8BE0"
PURPLE = "#9F72EC"
EMERALD = "#17A06B"
GLOW = "#CFFFE8"           # the emerald's own hue pushed to near white
# Brightness levels, as fractions of the full colour. Fading by brightness rather
# than by alpha keeps every material opaque, which renders about 50x faster, and
# against a near black background it reads the same.
DIM_MF = 0.05              # the field once the hero fibre takes over. The storyboard
                           # asks for "about 12 percent opacity"; this is 12 percent
                           # of a BRIGHTNESS fade, which is not the same quantity, and
                           # at 0.12 the 688 dimmed fibres still summed to a solid gold
                           # wall that the one hero fibre at full brightness could not
                           # be picked out of. Looked at 0.05 and 0.08 and took 0.05.
HOLD_MF = 0.55             # the six supporting fibres
REST_MF = 0.34             # gold restored for the final wide
# Measured, not guessed. At 0.30 and 0.22 the 87 lit cells were not separable
# from the 95 unlit ones in a beat 6 frame, and 250 pyramidal cells at that
# brightness buried the emerald interneuron they are supposed to be surrounding.
MUTED = 0.20               # both pyramidal populations in beat 4, equal
UNLIT = 0.10               # the thorny cells that never receive a contact


def build(opts, g, scene):
    t_start = time.time()
    hexcol = g["hexcol"]
    emissive_material = g["emissive_material"]

    FRAMES = int(opts.get("frames", 432))
    F = FRAMES / 432.0

    def b(x):
        return max(1, int(round(x * F)))

    # The seven beats, frame for frame from the storyboard.
    B1 = (b(1), b(54))         # the field
    B2 = (b(55), b(114))       # one fibre, one interneuron
    B3 = (b(115), b(168))      # the first synapse
    B4 = (b(169), b(228))      # both subtypes arrive
    B5 = (b(229), b(306))      # the axon spreads
    B6 = (b(307), b(384))      # the selectivity reveal
    B7 = (b(385), FRAMES)      # the motif
    print(f"[inh] beats {B1} {B2} {B3} {B4} {B5} {B6} {B7} of {FRAMES}", flush=True)

    z = np.load(FIELDS)
    span = float(z["span"])
    th_ids = [str(i) for i in z["thorny_ids"]]
    th_arr = z["thorny_arrival_um"]
    sp_ids = [str(i) for i in z["sparse_ids"]]
    mf_nm = z["mf_syn_nm"]
    mf_pre = [str(i) for i in z["mf_pre"]]
    soma_nm = z["soma_nm"]
    print(f"[inh] field span {span:.0f} um, {len(th_ids)} thorny targets arriving "
          f"{th_arr.min():.0f} to {th_arr.max():.0f} um, {len(sp_ids)} sparsely "
          f"thorny targets", flush=True)

    # ------------------------------------------------------------------ objects
    def coll(name):
        return sorted(bpy.data.collections[name].objects, key=lambda o: o.name)

    mf_objs = coll("mossy_fibers")
    th_objs = coll("thorny_pyramidals")
    sp_objs = coll("sparsely_thorny")
    inter = next(o for o in bpy.data.collections["inhibitory"].objects
                 if INTER_ID in o.name)

    def seg_of(o):
        return o.name.rsplit("_", 1)[-1]

    # Everything starts hidden and at unit scale. The cache leaves every object
    # at scale 0 with reveal keyframes on it, and the playbook is explicit that
    # scaling from zero drags objects in from somewhere else entirely, because
    # their centring is carried on location.
    # MESH only. CA3_ROOT and the pivot empties live in these same collections
    # and CA3_ROOT carries the 1.186e-5 scale that puts the whole 700 um volume
    # inside 10 Blender units. Setting it to 1 alongside the cells silently
    # multiplied every scene coordinate by 84,000, which showed up as a soma
    # eleven units off the origin.
    for c in scene.collection.children:
        for o in c.objects:
            if o.type != "MESH":
                continue
            o.animation_data_clear()
            o.scale = (1, 1, 1)
            o.hide_render = o.hide_viewport = True
    cloud = bpy.data.objects.get("SYNAPSES")
    if cloud:
        cloud.hide_render = cloud.hide_viewport = True
    print(f"[inh] {len(mf_objs)} mossy fibres, {len(th_objs)} thorny, "
          f"{len(sp_objs)} sparsely thorny, 1 interneuron "
          f"({len(inter.data.vertices):,} verts, {len(inter.data.polygons):,} faces)",
          flush=True)

    def show_from(o, frame):
        """Absent, not merely dark, until its beat. Booleans must be CONSTANT or
        Blender interpolates them into a half hidden state."""
        o.hide_render = o.hide_viewport = True
        o.keyframe_insert("hide_render", frame=1)
        o.keyframe_insert("hide_viewport", frame=1)
        o.hide_render = o.hide_viewport = False
        o.keyframe_insert("hide_render", frame=max(1, int(frame)))
        o.keyframe_insert("hide_viewport", frame=max(1, int(frame)))
        for fc in o.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "CONSTANT"

    # ------------------------------------------------------------------ colour
    def level_material(name, hex_colour, stops):
        """One opaque material whose brightness is keyed over time.

        stops is [(frame, fraction)]. Base Color and Emission Color are both
        driven from black up to `fraction` of the colour, which against a near
        black background reads exactly like an opacity fade while keeping the
        material on EEVEE's opaque path.
        """
        col = hexcol(hex_colour)
        mat = emissive_material(name, col, 1.0)
        try:
            mat.blend_method = "OPAQUE"
        except TypeError:
            pass
        bsdf = mat.node_tree.nodes["Principled BSDF"]
        for socket in ("Base Color", "Emission Color"):
            if socket not in bsdf.inputs:
                continue
            idx = list(bsdf.inputs).index(bsdf.inputs[socket])
            dp = f'nodes["Principled BSDF"].inputs[{idx}].default_value'
            for fr, k in stops:
                bsdf.inputs[socket].default_value = (col[0] * k, col[1] * k,
                                                     col[2] * k, 1.0)
                mat.node_tree.keyframe_insert(data_path=dp, frame=max(1, int(fr)))
        for fc in mat.node_tree.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "SINE"
                kp.easing = "EASE_IN_OUT"
        return mat

    def wear(objs, mat):
        for o in objs:
            o.data.materials.clear()
            o.data.materials.append(mat)

    # ---- beat 1 and 2: the mossy fibre field --------------------------------
    # One shared material for the 681 background fibres rather than 681 of them.
    # They all do the same thing and a material each costs build time for nothing.
    bg_mf = [o for o in mf_objs if seg_of(o) not in SEVEN]
    six = [o for o in mf_objs if seg_of(o) in SUPPORT_MF]
    hero = [o for o in mf_objs if seg_of(o) == HERO_MF]
    assert len(hero) == 1, f"hero mossy fibre {HERO_MF} not in the scene"
    assert len(six) == 6, f"expected 6 supporting fibres, found {len(six)}"

    dim_mf = float(opts.get("dimmf", DIM_MF))
    fade_in = B1[0] + b(20)
    wear(bg_mf, level_material("inh_mf_field", GOLD, [
        (B1[0], 0.0), (fade_in, 1.0), (B2[0], 1.0), (B2[0] + b(24), dim_mf),
        (B7[0], dim_mf), (B7[0] + b(24), REST_MF), (FRAMES, REST_MF)]))
    wear(six, level_material("inh_mf_six", GOLD, [
        (B1[0], 0.0), (fade_in, 1.0), (B2[0], 1.0), (B2[0] + b(24), HOLD_MF),
        (FRAMES, HOLD_MF)]))
    wear(hero, level_material("inh_mf_hero", GOLD, [
        (B1[0], 0.0), (fade_in, 1.0), (FRAMES, 1.0)]))
    for o in mf_objs:
        show_from(o, B1[0])

    # ---- the interneuron: base colour plus a travelling band -----------------
    inh_mat, head, amp, base_key = pulse_material(
        g, "inh_interneuron", EMERALD, GLOW,
        float(opts.get("width", 0.05)), float(opts.get("peak", 30.0)))
    paint(inter, z, span)
    inter.data.materials.clear()
    inter.data.materials.append(inh_mat)
    show_from(inter, B2[0])

    # emerald arrives over beat 2, brightens as the seven contacts land in beat 3
    key_socket(base_key, hexcol(EMERALD), [
        (B2[0], 0.0), (B2[0] + b(30), 0.62), (B3[0], 0.70), (B3[1], 1.0),
        (FRAMES, 1.0)])

    # ---- beat 3: seven synapse markers at their real coordinates -------------
    # Placed through the interneuron's own matrix_world. The importer's 90 degree
    # X flip lives on the OBJECT, not in the vertices, so a hand written
    # conversion here would be wrong in a way that still renders.
    # matrix_world is not usable here. The cache was saved with every cell at
    # scale 0, so the cached 3x3 is all zeros, and the depsgraph will not refresh
    # it for an object that is hidden at the current frame, which this one is,
    # because it does not arrive until beat 2. view_layer.update() and frame_set
    # both leave it degenerate. So the transform is composed from the parent
    # chain, which is static data and needs no evaluation at all.
    M = np.array(world_matrix(inter))
    assert abs(np.linalg.det(M[:3, :3])) > 1e-20, "degenerate object transform"

    def to_scene(nm):
        p = np.atleast_2d(np.asarray(nm, dtype=float))
        return p @ M[:3, :3].T + M[:3, 3]

    syn_s = to_scene(mf_nm)
    soma_s = Vector(to_scene(soma_nm)[0])
    size = float(g["TARGET_SIZE"])
    assert max(abs(v) for v in soma_s) < size, \
        f"the soma landed at {tuple(soma_s)}, outside a scene {size} units across"
    print(f"[inh] interneuron soma at scene {tuple(round(v,3) for v in soma_s)}, "
          f"7 contacts within "
          f"{np.linalg.norm(syn_s - np.array(soma_s), axis=1).max():.3f} units",
          flush=True)

    # The hero contact flares first, as storyboarded, then the rest in order of
    # their real distance from the soma.
    order = [k for k in range(7) if mf_pre[k] == HERO_MF]
    order += [k for k in range(7) if mf_pre[k] != HERO_MF]
    flare_span = B3[1] - B3[0] - b(10)
    markers = []
    for slot, k in enumerate(order):
        at = B3[0] + int(flare_span * slot / 6.0)
        bpy.ops.mesh.primitive_uv_sphere_add(
            radius=size * 0.0045, segments=16, ring_count=10,
            location=tuple(syn_s[k]))
        mk = bpy.context.active_object
        mk.name = f"INH_SYN_{slot}"
        m = bpy.data.materials.new(f"inh_syn_{slot}")
        m.use_nodes = True
        nt = m.node_tree
        nt.nodes.clear()
        out = nt.nodes.new("ShaderNodeOutputMaterial")
        em = nt.nodes.new("ShaderNodeEmission")
        em.inputs["Color"].default_value = (1.0, 0.94, 0.74, 1.0)
        nt.links.new(em.outputs["Emission"], out.inputs["Surface"])
        mk.data.materials.append(m)
        for fr, v in ((1, 0.0), (at - b(3), 0.0), (at, 40.0), (at + b(9), 9.0),
                      (B5[0], 3.0), (B6[0], 2.2), (FRAMES, 2.0)):
            em.inputs["Strength"].default_value = v
            em.inputs["Strength"].keyframe_insert("default_value",
                                                  frame=max(1, int(fr)))
        show_from(mk, max(1, B3[0] - b(3)))
        markers.append(mk)
        print(f"[inh] contact {mf_pre[k]} flares at frame {at}", flush=True)

    # ---- beat 4: both pyramidal populations, equally muted -------------------
    th_map = {seg_of(o): o for o in th_objs}
    sp_map = {seg_of(o): o for o in sp_objs}
    hit_th = [th_map[s] for s in th_ids if s in th_map]
    rest_th = [o for o in th_objs if seg_of(o) not in set(th_ids)]
    hit_sp = [sp_map[s] for s in sp_ids if s in sp_map]
    rest_sp = [o for o in sp_objs if seg_of(o) not in set(sp_ids)]
    assert len(hit_th) == 87, f"{len(hit_th)} thorny target meshes, expected 87"
    assert len(hit_sp) == 21, f"{len(hit_sp)} sparsely thorny target meshes, expected 21"

    arrive = B4[0], B4[1] - b(6)
    # The 95 thorny cells this interneuron never contacts sink as the 87 it does
    # contact light, so the contrast builds across beat 5 rather than switching at
    # the end of it.
    wear(rest_th, level_material("inh_thorny_rest", BLUE, [
        (arrive[0], 0.0), (arrive[1], MUTED), (B5[0], MUTED),
        (B5[1], UNLIT), (FRAMES, UNLIT)]))
    # The 47 sparsely thorny cells with no contact sink on exactly the same curve
    # as the 95 thorny cells with no contact. Leaving them brighter, which the
    # first version did, made the purple population read as lit when it is not.
    # In beat 6 there has to be one rule: dim means not contacted, whichever
    # subtype the cell belongs to.
    wear(rest_sp, level_material("inh_sparse_rest", PURPLE, [
        (arrive[0], 0.0), (arrive[1], MUTED), (B5[0], MUTED),
        (B5[1], UNLIT), (FRAMES, UNLIT)]))
    # The 21 sparsely thorny cells that DO receive a contact pulse once in beat 6,
    # so the shot stays honest that the preference is strong and not absolute.
    pulse_at = B6[0] + b(26)
    wear(hit_sp, level_material("inh_sparse_hit", PURPLE, [
        (arrive[0], 0.0), (arrive[1], MUTED), (B5[0], MUTED), (B5[1], UNLIT),
        (pulse_at - b(10), UNLIT), (pulse_at, 0.85),
        (pulse_at + b(22), 0.30), (FRAMES, 0.30)]))

    # ---- beat 5: 87 cells light, each at its own real path distance ----------
    # The wave head runs LINEARLY, which is what a constant conduction velocity
    # means, so a cell's frame is set by its cable distance and nothing else.
    head_lo, head_hi = -0.06, 1.02
    key_socket(head, None, [(1, head_lo), (B5[0], head_lo), (B5[1], head_hi),
                            (FRAMES, head_hi)], linear=True)
    key_socket(amp, None, [(1, 0.0), (B5[0] - b(6), 0.0),
                           (B5[0], float(opts.get("peak", 30.0))),
                           (B5[1], float(opts.get("peak", 30.0))),
                           (B5[1] + b(26), 0.0), (FRAMES, 0.0)], linear=True)

    lit_frames = []
    for o, arr in zip([th_map[s] for s in th_ids], th_arr):
        frac = float(arr) / span
        at = B5[0] + frac * (B5[1] - B5[0])
        lit_frames.append(at)
        wear([o], level_material(f"inh_th_{seg_of(o)}", BLUE, [
            (arrive[0], 0.0), (arrive[1], MUTED), (max(arrive[1], at - b(4)), MUTED),
            (at + b(10), 1.0), (FRAMES, 1.0)]))
    lit_frames = np.array(lit_frames)
    print(f"[inh] 87 thorny targets light between frames {lit_frames.min():.0f} "
          f"and {lit_frames.max():.0f}, median {np.median(lit_frames):.0f}", flush=True)

    for o in th_objs + sp_objs:
        show_from(o, arrive[0])

    # ------------------------------------------------------------------ camera
    for o in list(bpy.data.objects):
        if o.type in {"LIGHT", "CAMERA"}:
            bpy.data.objects.remove(o, do_unlink=True)

    mf_centre, mf_extent = population_bounds(g, mf_objs[::4])
    pop_centre, pop_extent = population_bounds(g, mf_objs[::4] + th_objs + sp_objs)
    pyr_centre, pyr_extent = population_bounds(g, th_objs + sp_objs)
    inh_centre, inh_extent = population_bounds(g, [inter])
    for nm, c, ex in (("mossy fibres", mf_centre, mf_extent),
                      ("everything", pop_centre, pop_extent),
                      ("pyramidals", pyr_centre, pyr_extent),
                      ("interneuron", inh_centre, inh_extent)):
        print(f"[inh] {nm:13s} centre {tuple(round(v,2) for v in c)} "
              f"extent {tuple(round(v,2) for v in ex)} units", flush=True)

    target = bpy.data.objects.new("INH_TARGET", None)
    scene.collection.objects.link(target)
    cam_data = bpy.data.cameras.new("INH_CAM")
    cam = bpy.data.objects.new("INH_CAM", cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam
    cam_data.lens = float(opts.get("lens", 45.0))
    # Measured at 0 and left there. On the opening frame the content came out
    # top 67 / bottom 88 px on a 720 px frame, which is 10 px off centre and not
    # worth correcting. A -0.030 shift was tried and it threw the opening frame
    # 45 px the other way, because the mossy fibre field and the pyramidal sheets
    # are not biased in the same direction. shift_y is a fraction of the sensor's
    # LARGER dimension, its width on a landscape render.
    cam_data.shift_y = float(opts.get("shifty", 0.0))
    cam_data.clip_start, cam_data.clip_end = 0.01, 4000.0
    trk = cam.constraints.new("TRACK_TO")
    trk.target = target
    trk.track_axis, trk.up_axis = "TRACK_NEGATIVE_Z", "UP_Y"

    # Solve the framing, do not guess it. Distances come from the measured extent
    # of whatever is actually on screen in that beat and the camera's real field
    # of view, not from trying numbers. Blender's sensor fit is AUTO, which fits
    # the LARGER render dimension, so on a 1920x1080 frame the sensor width sets
    # the horizontal angle and the vertical angle is that scaled by 1080/1920.
    sw = cam_data.sensor_width
    resx, resy = scene.render.resolution_x, scene.render.resolution_y
    half_h = math.atan(0.5 * sw / cam_data.lens)
    half_v = math.atan(0.5 * sw * min(1.0, resy / resx) / cam_data.lens)

    def solve(extent, fill):
        """Distance at which `extent` fills `fill` of the frame.

        Screen horizontal is mostly Blender X and screen vertical mostly Z, since
        the camera sits on the -Y side of a slab that is thin in Y. The Y depth is
        added to both as a margin, because the near face of the slab projects
        larger than the middle.
        """
        wx, wz = extent[0] + extent[1] * 0.5, extent[2] + extent[1] * 0.5
        return max(0.5 * wx / fill / math.tan(half_h),
                   0.5 * wz / fill / math.tan(half_v))

    FILL = float(opts.get("fill", 0.86))
    # The seven contacts sit inside a box this wide around the soma; beat 3 wants
    # that box, not the whole cell.
    zone = 2.0 * float(np.abs(syn_s - np.array(soma_s)).max()) * 1.35
    # Measured correction. solve() works off a p0.1 / p99.9 box, and against a
    # rendered frame that box under-reads the lit extent by about 12 percent:
    # the tails it trims are real geometry, and the glare pass spreads the
    # brightest edges further still. Predicted 0.86 fill, measured 0.93 to 1.00
    # with the bottom clipped on every wide frame. The fibre field is sparser and
    # does not need it, and measured 0.85 without.
    MARGIN = float(opts.get("margin", 1.12))
    FAR = float(opts.get("far", solve(pop_extent, FILL) * MARGIN))
    OPEN = float(opts.get("open", solve(mf_extent, FILL) * 0.94))
    MID = float(opts.get("mid", solve(pyr_extent, FILL) * MARGIN))
    AXON = float(opts.get("axon", solve(inh_extent, FILL)))
    NEAR = float(opts.get("near", solve((zone, zone * 0.3, zone), 0.80)))
    ARC = math.radians(float(opts.get("arc", 18.0)))
    print(f"[inh] solved distances at {FILL:.2f} fill: open {OPEN:.2f}, "
          f"near {NEAR:.2f}, axon {AXON:.2f}, mid {MID:.2f}, far {FAR:.2f}; "
          f"fov {math.degrees(2*half_h):.1f} by {math.degrees(2*half_v):.1f} deg",
          flush=True)
    base_dir = np.array([0.16, -1.0, 0.13])
    base_dir /= np.linalg.norm(base_dir)

    def at(theta, dist, aim):
        c, s = math.cos(theta), math.sin(theta)
        d = np.array([base_dir[0] * c - base_dir[1] * s,
                      base_dir[0] * s + base_dir[1] * c,
                      base_dir[2]])
        return Vector(np.asarray(aim) + d * dist)

    # One push in, one opening out. The playbook's note from a real viewer is
    # that a camera which goes in and out repeatedly reads as pumping, so the
    # only reversal in the whole shot is at the closest point, frame B3[1], where
    # the storyboard asks it to settle anyway.
    # Measured. With the camera aimed straight at the pyramidal centre the wide
    # frames came out 71 to 117 px empty at the top and hard against the bottom
    # edge on a 720 px frame, about 35 px low. The fix is a DROP applied to the
    # look-at point only, not to the camera position: moving both together just
    # slides the whole rig down and changes nothing, which is what happened when
    # it was tried that way first. Tilting the camera down while it stays put is
    # what lifts the content. Applied to beats 4 to 7 only, since the opening
    # fibre frame was already balanced at 49 / 61.
    DROP = Vector((0.0, 0.0, -float(opts.get("aimdrop", 0.25))))
    mid_aim = (Vector(inh_centre) + soma_s) * 0.5
    keys = [
        (1,     -ARC * 0.50, OPEN * 1.06, Vector(mf_centre), Vector((0, 0, 0))),
        (B1[1], -ARC * 0.36, OPEN * 0.94, Vector(mf_centre), Vector((0, 0, 0))),
        (B2[1], -ARC * 0.20, NEAR * 2.2, soma_s, Vector((0, 0, 0))),
        (B3[1], -ARC * 0.05, NEAR, soma_s, Vector((0, 0, 0))),
        # From beat 4 the pyramidal populations are on screen and they are wider
        # than the interneuron's own arbor, so the distance is set by them. Beat 5
        # framed on the axonal territory alone (AXON, 16.2) clipped the blue and
        # purple off the top and bottom of the frame; measured, then fixed.
        (B4[1],  ARC * 0.14, MID * 0.98, (soma_s + Vector(pyr_centre)) * 0.5, DROP),
        (B5[1],  ARC * 0.32, MID * 1.05, mid_aim, DROP),
        (B6[1],  ARC * 0.41, MID * 1.09, Vector(pyr_centre), DROP),
        (FRAMES, ARC * 0.50, max(FAR, MID * 1.06), Vector(pop_centre), DROP),
    ]
    for fr, th, d, aim, drop in keys:
        target.location = aim + drop
        target.keyframe_insert("location", frame=max(1, int(fr)))
        cam.location = at(th, d, aim)
        cam.keyframe_insert("location", frame=max(1, int(fr)))
    for o in (cam, target):
        for fc in o.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "BEZIER"
                kp.handle_left_type = kp.handle_right_type = "AUTO_CLAMPED"
            fc.update()
    print("[inh] camera: " + ", ".join(f"f{fr}@{d:.2f}" for fr, _, d, _, _ in keys),
          flush=True)

    if opts.get("dof", "1") not in ("0", "false", "no"):
        cam_data.dof.use_dof = True
        cam_data.dof.focus_object = target
        cam_data.dof.aperture_fstop = float(opts.get("fstop", 3.2))
        cam_data.dof.aperture_blades = 6

    # velocity check: a mid shot near stop is a visible stutter
    # Read straight off the f-curves rather than stepping the frame. frame_set
    # would re-evaluate a 44M face depsgraph 432 times to measure a curve that is
    # already stored, and matrix_world is unreliable in this file anyway.
    fcs = {fc.array_index: fc for fc in cam.animation_data.action.fcurves
           if fc.data_path == "location"}
    pos = np.array([[fcs[i].evaluate(fr) for i in range(3)]
                    for fr in range(1, FRAMES + 1)])
    vel = np.linalg.norm(np.diff(pos, axis=0), axis=1)

    # dumpcam=a-b prints the interpolated path frame by frame. Added while chasing
    # a jump Amy reported at 1.8 s: the encoded frames drift steadily up to frame 43
    # and then reverse for ten frames, and the only way to tell a real kink in the
    # curve from an artefact of measuring the image is to read the curve itself.
    if "dumpcam" in opts:
        _a, _b = (int(x) for x in opts["dumpcam"].split("-"))
        print("[inh] frame        x         y         z      step    d(step)",
              flush=True)
        for fr in range(max(2, _a), min(FRAMES, _b) + 1):
            p = pos[fr - 1]
            st = vel[fr - 2]
            dst = st - vel[fr - 3] if fr >= 3 else 0.0
            print("[inh] %5d %9.4f %9.4f %9.4f %9.5f %9.5f"
                  % (fr, p[0], p[1], p[2], st, dst), flush=True)

    interior = vel[3:-3]
    at_min = int(np.argmin(interior)) + 4
    print(f"[inh] camera speed: peak {vel.max():.4f}, slowest interior "
          f"{interior.min():.4f} ({100*interior.min()/vel.max():.0f}% of peak) at "
          f"frame {at_min}"
          + (", the settle at the closest point, which is deliberate"
             if abs(at_min - B3[1]) <= 12 else ""), flush=True)
    # Per beat, because the shot deliberately reverses once and deliberately
    # holds in beat 6, so a single global minimum says nothing on its own.
    for n, (a, bb) in enumerate([B1, B2, B3, B4, B5, B6, B7], 1):
        seg = vel[max(0, a - 1):bb - 1]
        if len(seg):
            print(f"[inh]   beat {n} f{a}-{bb}: speed {seg.min():.4f} to "
                  f"{seg.max():.4f} units/frame", flush=True)

    g["build_world"](scene)
    g["build_lights"](scene, size, target=target)
    g["apply_render_settings"](scene)
    print(f"[inh] scene built in {time.time()-t_start:.0f}s", flush=True)
    return dict(beats=[B1, B2, B3, B4, B5, B6, B7], frames=FRAMES)


# ---------------------------------------------------------------------- helpers
def world_matrix(o):
    """matrix_world composed from the parent chain, without the depsgraph.

    Blender's own rule: world = parent.world @ matrix_parent_inverse @
    matrix_basis. All three are stored data, so this is exact and works on
    objects that are hidden, unevaluated, or freshly edited, none of which
    matrix_world survives.
    """
    m = o.matrix_basis.copy()
    if o.parent is not None:
        m = world_matrix(o.parent) @ o.matrix_parent_inverse @ m
    return m


def key_socket(sock, colour, stops, linear=False):
    """Keyframe a shader socket. colour is None for a scalar socket, or an RGB
    triple whose value is scaled by each stop."""
    for fr, v in stops:
        sock.default_value = ((colour[0] * v, colour[1] * v, colour[2] * v, 1.0)
                              if colour is not None else v)
        sock.keyframe_insert("default_value", frame=max(1, int(fr)))
    nt = sock.id_data
    if nt.animation_data:
        for fc in nt.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = "LINEAR" if linear else "SINE"
                if not linear:
                    kp.easing = "EASE_IN_OUT"


def pulse_material(g, name, base_hex, glow_hex, width, peak):
    """Lifted from ap_six.py, which is the one thing the storyboard says to take
    from it. A band around an animated head value drives Emission Strength:
    band = clamp(1 - |d - t| / width)^2 * peak.

    Returns the material plus three sockets: where the wavefront is, how hard it
    burns, and the base colour, which this shot has to fade up separately because
    the cell arrives on screen a beat before it fires.
    """
    hexcol = g["hexcol"]
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = hexcol(base_hex) + (1.0,)
    bsdf.inputs["Roughness"].default_value = g["SURFACE_ROUGHNESS"]
    bsdf.inputs["IOR"].default_value = g["TISSUE_IOR_IN_WATER"]   # submerged
    bsdf.inputs["Specular IOR Level"].default_value = g["SPECULAR_LEVEL"]
    bsdf.inputs["Subsurface Weight"].default_value = g["SUBSURFACE_WEIGHT"]
    bsdf.inputs["Subsurface Scale"].default_value = g["SUBSURFACE_SCALE"]
    bsdf.inputs["Emission Color"].default_value = hexcol(glow_hex) + (1.0,)
    attr = nt.nodes.new("ShaderNodeAttribute")
    attr.attribute_name = "inhdist"
    sub = nt.nodes.new("ShaderNodeMath"); sub.operation = "SUBTRACT"
    absn = nt.nodes.new("ShaderNodeMath"); absn.operation = "ABSOLUTE"
    div = nt.nodes.new("ShaderNodeMath"); div.operation = "DIVIDE"
    div.inputs[1].default_value = width
    inv = nt.nodes.new("ShaderNodeMath"); inv.operation = "SUBTRACT"
    inv.inputs[0].default_value = 1.0
    inv.use_clamp = True
    shp = nt.nodes.new("ShaderNodeMath"); shp.operation = "POWER"
    shp.inputs[1].default_value = 2.0
    amp = nt.nodes.new("ShaderNodeMath"); amp.operation = "MULTIPLY"
    amp.inputs[1].default_value = peak
    for a, bb in ((attr.outputs["Color"], sub.inputs[0]), (sub.outputs[0], absn.inputs[0]),
                  (absn.outputs[0], div.inputs[0]), (div.outputs[0], inv.inputs[1]),
                  (inv.outputs[0], shp.inputs[0]), (shp.outputs[0], amp.inputs[0]),
                  (amp.outputs[0], bsdf.inputs["Emission Strength"]),
                  (bsdf.outputs["BSDF"], out.inputs["Surface"])):
        nt.links.new(a, bb)
    return mat, sub.inputs[1], amp.inputs[1], bsdf.inputs["Base Color"]


def paint(obj, z, span):
    """Write the per vertex path distance onto the mesh as a FLOAT_COLOR.

    No nearest node search and no cache, because the field was computed on this
    exact mesh, vertex for vertex. That is asserted here rather than trusted:
    Blender's OBJ importer can split vertices, and if it had, every value would
    land on the wrong point while still rendering.
    """
    n = len(obj.data.vertices)
    assert n == int(z["n_verts"]), \
        f"{obj.name} has {n:,} vertices, the field was built on {int(z['n_verts']):,}"
    co = np.empty(n * 3, dtype=np.float64)
    obj.data.vertices.foreach_get("co", co)
    co = co.reshape(-1, 3)
    d0 = np.abs(co[:64] - z["vert0"]).max()
    dN = np.abs(co[-64:] - z["vertN"]).max()
    assert d0 < 1.0 and dN < 1.0, \
        (f"vertex order differs from the OBJ the field was built on "
         f"(first block off by {d0:.1f} nm, last by {dN:.1f} nm)")

    # Never clip to 1. Anything the wave should not reach has to stay parked past
    # the end of the sweep, and normalising by values.max() would drag it to
    # exactly 1.0 and flash it on the last frame.
    norm = np.minimum(z["field"].astype(np.float64) / span, 4.0)
    for a in list(obj.data.color_attributes):
        if a.name == "inhdist":
            obj.data.color_attributes.remove(a)
    attr = obj.data.color_attributes.new(name="inhdist", type="FLOAT_COLOR",
                                         domain="POINT")
    flat = np.empty(n * 4, dtype=np.float32)
    flat[0::4] = flat[1::4] = flat[2::4] = norm
    flat[3::4] = 1.0
    attr.data.foreach_set("color", flat)
    print(f"[inh] painted {n:,} vertices, field 0 to {norm.max():.2f} normalised, "
          f"{100*(norm<=1).mean():.1f}% inside the sweep", flush=True)


def population_bounds(g, objs, pct=0.1):
    """Outlier robust centre and extent, in scene units.

    Percentile bounds, not min/max: these meshes carry a handful of stray
    vertices hundreds of micrometres outside the volume and a raw bounding box
    follows them straight off the edge of the frame.
    """
    chunks = []
    for o in objs:
        n = len(o.data.vertices)
        if not n:
            continue
        co = np.empty(n * 3, dtype=np.float64)
        o.data.vertices.foreach_get("co", co)
        co = co.reshape(-1, 3)
        if n > 4000:
            co = co[np.linspace(0, n - 1, 4000).astype(int)]
        # world_matrix, not matrix_world: these objects are hidden at the current
        # frame, so the depsgraph will not refresh their cached transform.
        m = np.array(world_matrix(o))
        chunks.append(co @ m[:3, :3].T + m[:3, 3])
    allv = np.vstack(chunks)
    lo = np.percentile(allv, pct, axis=0)
    hi = np.percentile(allv, 100 - pct, axis=0)
    return (lo + hi) / 2.0, hi - lo
