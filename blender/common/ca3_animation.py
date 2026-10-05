"""
CA3 connectivity animation: presynaptic deep/superficial pyramidal cells plus their
postsynaptic partners.

Designed to run two ways from the SAME source:
  1. Headless:  blender --background --python ca3_animation.py
  2. Through the Blender MCP, by handing this file's contents to execute_blender_code,
     which runs it inside your live Blender session so you can see it and iterate.

Coordinate note: the newly downloaded cells and the zhihao meshes were verified to
occupy the same nanometre space (Z bounds 4,324..96,439 vs 4,313..96,480), so they
are imported with no transform and land in correct relative position.

Nothing renders unless RENDER = True. Building the scene is CPU only and safe next to
a GPU render; rendering is NOT, since EEVEE will want VRAM.
"""
import math
import os
from pathlib import Path

import bpy
from mathutils import Matrix, Vector


def hexcol(s):
    """'#2477EE' -> linear RGB, which is what Principled BSDF expects."""
    s = s.lstrip("#")
    return tuple((int(s[i:i + 2], 16) / 255.0) ** 2.2 for i in (0, 2, 4))


def shade_ramp(hex_a, hex_b, n):
    """n colours stepping from hex_a to hex_b, interpolated in HSV.

    HSV rather than RGB so the hue walks evenly and the steps stay equally
    saturated, which keeps every cell a distinct shade instead of some going muddy.
    """
    import colorsys

    def to_hsv(h):
        h = h.lstrip("#")
        r, g, b = (int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
        return colorsys.rgb_to_hsv(r, g, b)

    ha, sa, va = to_hsv(hex_a)
    hb, sb, vb = to_hsv(hex_b)
    out = []
    for i in range(max(1, n)):
        t = i / max(1, n - 1) if n > 1 else 0.0
        r, g, b = colorsys.hsv_to_rgb(ha + (hb - ha) * t,
                                      sa + (sb - sa) * t,
                                      va + (vb - va) * t)
        out.append((r ** 2.2, g ** 2.2, b ** 2.2))
    return out

# ----------------------------------------------------------------------------- config
# Every path below is derived from these three roots, and each can be overridden
# by an environment variable so the same source runs on Linux (the cluster)
# without edits. Defaults are the Windows workstation, so local runs are
# unchanged and need no setup.
ROOT = Path(os.environ.get("CA3_ROOT", r"D:\Meshes"))
MESHPARTY = Path(os.environ.get("CA3_MESHPARTY", r"C:\Users\amyle\meshparty"))
# Re-decimated set: soma debris stripped, per-morphology targets,
# median p99 face-area bloat 1.12x instead of 1.65x-2.12x.
HQ = ROOT / "hq"

# Every population lives here. Turn them on and off with ENABLED below.
# "sublayer" groups separate from each other when SEPARATE_LAYERS is on.
# Face counts are measured, so you can budget before you load.
GROUPS = {
    "CA3_deep": {
        "dirs": [ROOT / "CA3 deep layer"],
        "color": hexcol("#D657A5"),       # fallback if per_cell_range is removed
        # every cell its own shade, deep navy through royal
        "per_cell_range": ("#C43F92", "#E86FB8"),   # deep layer: rich pink, hue ~325 so it
        # never drifts toward red
        "sublayer": True,
        "reveal": (80, 165),
        "note": "7 cells, presynaptic target set, deep layer",
    },
    "CA3_superficial": {
        "dirs": [ROOT / "CA3 superficial layer"],
        "color": hexcol("#F388CA"),       # fallback if per_cell_range is removed
        # continues the ramp upward, azure through pale ice
        "per_cell_range": ("#EC63B4", "#F189C6"),   # superficial layer: pink, light end clipped
        # again so it never drifts pale enough to read like the gold mossy fibres
        "sublayer": True,
        "reveal": (80, 165),
        "note": "9 cells, presynaptic target set, superficial layer",
    },
    "CA3_postsynaptic": {
        "dirs": [MESHPARTY / "CA3 zhihao", MESHPARTY / "CA3 zhihao 2"],
        "color": hexcol("#7B6FE8"),       # purple-blue / periwinkle
        "sublayer": False,
        "reveal": (110, 200),
        "note": "23 unique cells, ~10.8M faces, one is 336 MB",
    },
    # These now point at the decimated copies on D:, not the originals on C:.
    # Face counts below are post-decimation and measured.
    "thorny_pyramidals": {
        "dirs": [HQ / "thorny pyramidals ca3 250"],
        # The house blue, and now the only blue. This used to be #1E6FDE with a
        # per-cell ramp #1858C7 to #2586F5, which disagreed with the #2E8BE0 that
        # ships in the action potential cuts. Resolved in favour of the house
        # value, for two reasons. The ramp encodes nothing: it walks with cell
        # index, not with any measurement, and the playbook's rule for colour as
        # data is that a ramp has to carry something. And in the inhibition shot
        # blue is a STATE, contacted or not, so a per-cell ramp makes a bright
        # unlit cell indistinguishable from a lit one.
        #
        # The old ramp is one line away if a population shot ever wants it back:
        #   "per_cell_range": ("#1858C7", "#2586F5"),
        # Its note is worth keeping either way: saturation was pinned high across
        # the whole ramp, 0.88 down to 0.85, because a blue at 0.74 saturation
        # starts reading pale. #2E8BE0 sits at 0.80, inside that band.
        "color": hexcol("#2E8BE0"),
        "per_cell_range": None,
        "sublayer": False,
        "reveal": (160, 250),
        "note": "182 cells, 7.2M faces",
    },
    "sparsely_thorny": {
        "dirs": [HQ / "sparsely thorny pyramidals ca3 68"],
        "color": hexcol("#9F72EC"),       # fallback if per_cell_range is removed
        "per_cell_range": ("#8B5CE0", "#B78CF7"),   # light but rich purple, replacing the
        # dark blue that was reading as holes
        "sublayer": False,
        "reveal": (245, 335),
        "note": "68 cells, 2.4M faces",
    },
    "inhibitory": {
        "dirs": [HQ / "inhibitory ca3 28"],
        "color": hexcol("#17A06B"),       # emerald: pushed green, away from the blues. Darker
        # and less saturated than the old mint so it separates without shouting
        "sublayer": False,
        "reveal": (330, 420),
        "note": "28 cells, 1.9M faces",
    },
    "mossy_fibers": {
        "dirs": [HQ / "MF 700"],
        # The house gold, and now the only gold. Was #E2AF5E here while the
        # action potential cuts shipped #E8A93A. Resolved in favour of the house
        # value: it is 0.75 saturated against 0.58, and under a Standard view
        # transform with a 5200 W key the less saturated one lifts toward cream.
        # The playbook's first rule about colour is that a hex has to be picked
        # in the render, and #E8A93A is the one that has been.
        "color": hexcol("#E8A93A"),       # warm gold, matching your MF convention
        "sublayer": False,
        "reveal": (1, 85),
        "note": "688 cells, 15.5M faces, still the heaviest set",
    },
    "pyr_600": {
        "dirs": [HQ / "pyr 600"],
        "color": hexcol("#B84DD8"),       # magenta-purple
        "sublayer": False,
        "reveal": (110, 200),
        "note": "163 cells, 5.7M faces",
    },
    "pyr_fibers": {
        "dirs": [HQ / "pyr fibers"],
        "color": hexcol("#3D68DE"),       # deep blue-violet
        "sublayer": False,
        "reveal": (150, 225),
        "note": "279 cells, 4.6M faces",
    },
    "pyr_pyr_2": {
        "dirs": [HQ / "pyr pyr 2"],
        "color": hexcol("#35D0E0"),       # cyan-teal
        "sublayer": False,
        "reveal": (110, 200),
        "note": "88 cells, 3.0M faces",
    },
    "pyr_MF_pyc": {
        "dirs": [HQ / "pyr MF pyc"],
        "color": hexcol("#F0D060"),       # warm yellow
        "sublayer": False,
        "reveal": (110, 200),
        "note": "201 cells, 6.8M faces",
    },
}

# Loading everything at once is ~108M faces, which Blender will not enjoy.
# Start small and add. Every group is in the same nanometre space, so any
# combination lands in correct relative position with no transform.
ENABLED = ["CA3_deep", "CA3_superficial", "CA3_postsynaptic"]

MAX_MB_PER_CELL = None    # set e.g. 100 to skip the heaviest cells while iterating

TARGET_SIZE = 10.0        # longest axis of the whole population, in Blender units
FPS = 24
FRAME_START = 1
FRAME_END = 240           # 10 seconds

REVEAL_LEN = 26           # frames each individual cell takes to grow in
ORBIT_TURNS = 1.0         # camera revolutions across the whole shot
# Start angle in degrees. The volume is a flat slab, so a sweep centred on
# face-on (e.g. start -36 with 0.2 turns) keeps it readable the whole way,
# where a full revolution spends seconds looking at its edge.
ORBIT_START_DEG = 0.0
CAM_LENS_MM = 50
CAM_DISTANCE_MULT = 2.6   # camera distance as a multiple of TARGET_SIZE
# Lens shift, in fractions of the larger sensor dimension. Negative lifts the
# subject up the frame, which is how the population sits in the top two thirds
# of a vertical render while the bottom third carries the labels.
CAM_SHIFT_Y = 0.0

# Off by default while the postsynaptic partners are in the scene: pulling the
# presynaptic layers apart would break the true spatial relationship that makes
# the connectivity readable. Turn on for a sublayer-only shot.
SEPARATE_LAYERS = False
SEPARATION = 3.0
SEP_START, SEP_END = 95, 150

# Emission is a faint rim-fill only. At 0.55 it flattened everything, because a
# surface that emits its own colour cannot show form shading. Shape now comes
# from the light rig below.
EMISSION_STRENGTH = 0.04
SURFACE_ROUGHNESS = 0.62  # with specular this weak, roughness barely matters
SPECULAR_LEVEL = 0.5    # 0.5 means "use the IOR as given", which is the point
TISSUE_IOR_IN_WATER = 1.04  # 1.38 membrane / 1.33 extracellular fluid
# Translucency. Thin dendrites should let light through, not stop it dead.
SUBSURFACE_WEIGHT = 0.42  # scattering, not reflection, is what we should see
SUBSURFACE_SCALE = 0.012  # Blender units; ~1um of tissue at TARGET_SIZE=10
COAT_WEIGHT = 0.0         # the clearcoat was the main source of gloss
TRANSMISSION_WEIGHT = 0.0 # full transmission reads as glass, not tissue
# Off by request. Note the measured oddity: with raytracing OFF the same frame
# took 53s vs 12s ON, which is backwards and still unexplained. The shadow
# mushiness that prompted turning it off was actually SHADOW_SOFTNESS at 0.5,
# now 0.15, so crisp shadows no longer depend on this setting either way.
USE_RAYTRACING = False
POST_ALPHA = 0.55         # postsynaptic cells sit back visually

# Environment. A real HDRI gives discrete bright sources, so curvature catches
# specular highlights that read as shape; the gradient fallback cannot do that.
# The background stays black regardless (transparent film, black plate behind),
# so the HDRI is purely a light probe and never appears in frame.
#
# Available on this machine:
#   Blender bundled (small, clean, purpose-built for showing form):
#     .../Blender 4.4/4.4/datafiles/studiolights/world/{studio,courtyard,city,
#       forest,interior,night,sunrise,sunset}.exr
#   Yours, including the set Cinema 4D uses in D:\C4D\tex:
#     cyclorama_hard_light_4k.hdr, kloppenheim_06_4k.hdr, bell_park_pier_4k.hdr,
#     kloofendal_48d_partly_cloudy_puresky_2k.exr, meadow_2_4k.hdr,
#     the_sky_is_on_fire_2k.exr, golden_gate_hills_2k.exr
# Poly Haven's hard-light cyclorama: a studio probe built for form definition,
# neutral so it will not tint the palette, and 4K so the highlights stay crisp.
# Blender's bundled studio.exr is only 98 KB and too low-res for sharp specular.
# NOTE: this file is LINKED, not packed, into ca3_scene.blend. Verified 29 Jul
# 2026: it is the cache's only external dependency. On any other machine the
# world goes unlit unless this resolves, and an unlit world fails silently.
HDRI_PATH = os.environ.get(
    "CA3_HDRI", r"C:\Users\amyle\Documents\cyclorama_hard_light_4k.hdr")
HDRI_ROTATION = 40.0      # degrees about Z, to place the highlights

# Direct lighting only, no raytraced GI. Energies are watts; area size scales
# with the population so the rig stays proportional at any TARGET_SIZE.
WORLD_STRENGTH = 0.38     # environment contribution, ambient + specular
KEY_ENERGY = 5200
FILL_ENERGY = 1500
RIM_ENERGY = 2400
TOP_ENERGY = 1800
USE_SHADOWS = True
SHADOW_SOFTNESS = 0.15    # fraction of light size; lower = crisper terminator

# Synapse cloud. 25,723 real synapses made by the 16 presynaptic cells, taken
# from CAVE's synapses_ca3_v1 table. Their coordinates were checked against the
# meshes (X 450,810..1,240,020 vs the meshes' 443,693..1,241,885), so they sit in
# the same nanometre space and need no transform.
SHOW_SYNAPSES = False
SYNAPSE_NPY = ROOT / "renders" / "synapse_points.npy"
SYNAPSE_COLOR = "#FFD54A"     # warm bright, unlike any cell population
SYNAPSE_RADIUS_NM = 900       # marker size, not true synapse size
SYNAPSE_EMISSION = 0.9        # 4.5 flooded the frame; the bloom multiplies this
SYNAPSE_REVEAL = (1, 60)

# Bloom. mix runs -1 (none) to +1 (glare only); threshold sets how bright a pixel
# must be before it blooms, so a high value keeps the glow on lit highlights.
# 4.4 socket values. Threshold is an absolute luminance cutoff, so above 1.0
# only genuinely blown highlights bloom; Size is 0..1 here, not the old 0..9.
BLOOM_THRESHOLD = 0.84
BLOOM_STRENGTH = 0.62
BLOOM_SIZE = 0.62
BLOOM_SMOOTHNESS = 0.20
BLOOM_SATURATION = 1.15
BLOOM_MIX = -0.68         # legacy fallback for Blender < 4.4

# Blender 4.x defaults to the AgX view transform, which rolls saturated colour
# toward white as it brightens. That is the washed-out look; C4D applies no such
# tonemap, which is why the reference frame reads vivid. "Standard" is plain sRGB.
# Highlights clip harder under Standard, so the light energies above are set
# lower than they would be under AgX.
VIEW_TRANSFORM = "Standard"
VIEW_LOOK = "None"
VIEW_EXPOSURE = 0.0

# Faces with an edge longer than this are artifacts reaching to stray vertices,
# not anatomy. Real faces in these meshes are sub-micron.
MAX_EDGE_NM = 20000
STRIP_STRAY_FACES = True
RESOLUTION = (1920, 1080)
SAMPLES = 64

RENDER = False            # leave False while anything else is using the GPU
OUTPUT_DIR = ROOT / "renders" / "ca3_anim"

CLEAR_SCENE = True
TEST_WITH_PRIMITIVES = False


# ------------------------------------------------------------------------------ helpers
def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)
    for block in (bpy.data.meshes, bpy.data.materials, bpy.data.objects):
        for item in list(block):
            if item.users == 0:
                block.remove(item)


def make_collection(name):
    coll = bpy.data.collections.get(name) or bpy.data.collections.new(name)
    if name not in {c.name for c in bpy.context.scene.collection.children}:
        bpy.context.scene.collection.children.link(coll)
    return coll


def emissive_material(name, color, alpha=1.0):
    """Lit surface, not a glowing one.

    Emission was the reason the earlier renders read flat: every face emitted its
    own colour regardless of its normal, so form shading was mathematically
    impossible. Emission is now a faint rim-fill only, and shape comes from the
    lights plus the environment.
    """
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    inp = bsdf.inputs

    def put(socket, value):
        if socket in inp:
            inp[socket].default_value = value

    put("Base Color", (*color, 1.0))
    put("Roughness", SURFACE_ROUGHNESS)
    put("Metallic", 0.0)
    # Neurons live in extracellular fluid, not air. Specular strength is set by
    # the index contrast at the interface, so what matters is tissue RELATIVE to
    # water: 1.38 / 1.33 = 1.04. Fresnel reflectance at normal incidence is
    # ((n-1)/(n+1))^2, giving 0.034% here against 2.6% for tissue in air. Wet
    # things only look wet once they leave the water, and these never do.
    put("IOR", TISSUE_IOR_IN_WATER)
    put("Specular IOR Level", SPECULAR_LEVEL)

    # Subsurface, so light entering a thin dendrite scatters through it instead
    # of stopping at the surface. This is what makes biological tissue read as
    # translucent rather than as painted plastic. The scale is in Blender units,
    # and at TARGET_SIZE=10 across a ~700um population, 1um of tissue is about
    # 0.014 units, so the radius has to be small or everything turns to wax.
    put("Subsurface Weight", SUBSURFACE_WEIGHT)
    put("Subsurface Scale", SUBSURFACE_SCALE)
    if "Subsurface Radius" in inp:
        # tint the scatter toward the cell's own hue so it deepens rather than
        # washing everything to pink the way default flesh-toned SSS would
        inp["Subsurface Radius"].default_value = tuple(
            max(0.15, min(1.0, c * 1.6 + 0.15)) for c in color)

    put("Coat Weight", COAT_WEIGHT)      # thin wet sheen over the membrane
    put("Coat Roughness", 0.25)
    put("Transmission Weight", TRANSMISSION_WEIGHT)
    if "Emission Color" in bsdf.inputs:
        bsdf.inputs["Emission Color"].default_value = (*color, 1.0)
        bsdf.inputs["Emission Strength"].default_value = EMISSION_STRENGTH
    if alpha < 1.0:
        bsdf.inputs["Alpha"].default_value = alpha
        mat.blend_method = "BLEND"
    else:
        # Explicitly opaque. The default HASHED still runs the alpha-test path
        # for nothing at full opacity.
        bsdf.inputs["Alpha"].default_value = 1.0
        try:
            mat.blend_method = "OPAQUE"
        except TypeError:
            pass
    return mat


def build_world(scene):
    """Environment light, with a black camera background.

    Uses a real HDRI when HDRI_PATH points at one, which gives high-frequency
    detail and discrete bright sources, so curved surfaces catch specular
    highlights that read as shape. Falls back to a vertical gradient otherwise.

    Either way film_transparent keeps the camera background black while the world
    still lights the scene, so there is environment light without a grey backdrop.
    """
    world = scene.world or bpy.data.worlds.new("CA3_World")
    scene.world = world
    world.use_nodes = True
    nt = world.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)

    if HDRI_PATH and Path(HDRI_PATH).exists():
        out = nt.nodes.new("ShaderNodeOutputWorld")
        bg = nt.nodes.new("ShaderNodeBackground")
        env = nt.nodes.new("ShaderNodeTexEnvironment")
        mapping = nt.nodes.new("ShaderNodeMapping")
        tc = nt.nodes.new("ShaderNodeTexCoord")
        env.image = bpy.data.images.load(str(HDRI_PATH), check_existing=True)
        mapping.inputs["Rotation"].default_value[2] = math.radians(HDRI_ROTATION)
        bg.inputs["Strength"].default_value = WORLD_STRENGTH
        nt.links.new(tc.outputs["Generated"], mapping.inputs["Vector"])
        nt.links.new(mapping.outputs["Vector"], env.inputs["Vector"])
        nt.links.new(env.outputs["Color"], bg.inputs["Color"])
        nt.links.new(bg.outputs["Background"], out.inputs["Surface"])
        for node, x in ((tc, -900), (mapping, -700), (env, -450), (bg, -180), (out, 60)):
            node.location = (x, 0)
        print(f"[ca3] HDRI: {Path(HDRI_PATH).name} at strength {WORLD_STRENGTH}")
        return world

    print("[ca3] no HDRI found, using procedural gradient environment")
    out = nt.nodes.new("ShaderNodeOutputWorld")
    bg = nt.nodes.new("ShaderNodeBackground")
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    tex = nt.nodes.new("ShaderNodeTexCoord")

    # map world Z (-1..1) into the ramp
    mapr = nt.nodes.new("ShaderNodeMapRange")
    mapr.inputs["From Min"].default_value = -1.0
    mapr.inputs["From Max"].default_value = 1.0

    ramp.color_ramp.elements[0].position = 0.0
    ramp.color_ramp.elements[0].color = (0.045, 0.035, 0.028, 1.0)   # warm floor bounce
    ramp.color_ramp.elements[1].position = 1.0
    ramp.color_ramp.elements[1].color = (0.10, 0.13, 0.20, 1.0)      # cool sky
    mid = ramp.color_ramp.elements.new(0.5)
    mid.color = (0.05, 0.055, 0.075, 1.0)

    bg.inputs["Strength"].default_value = WORLD_STRENGTH

    nt.links.new(tex.outputs["Generated"], sep.inputs["Vector"])
    nt.links.new(sep.outputs["Z"], mapr.inputs["Value"])
    nt.links.new(mapr.outputs["Result"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bg.inputs["Color"])
    nt.links.new(bg.outputs["Background"], out.inputs["Surface"])
    for node, x in ((tex, -900), (sep, -700), (mapr, -520), (ramp, -330),
                    (bg, -120), (out, 80)):
        node.location = (x, 0)
    return world


def apply_render_settings(scene):
    """Engine, colour management, output and compositor.

    Split out of build() so render_from_cache.py can reapply it after loading
    the saved .blend, keeping bloom, exposure and view transform editable.
    """
    scene.render.engine = "BLENDER_EEVEE_NEXT"
    scene.eevee.taa_render_samples = SAMPLES

    # MOTION BLUR OFF. Not a look choice: it is what stops the renderer crashing.
    #
    # EEVEE's VelocityModule keeps a full copy of the scene geometry for the
    # previous and next frames so it can compute motion vectors. At 43.1M faces
    # that buffer overflows. On 1 Aug 2026 both the 364 cell retina job and the
    # BANC job died with EXCEPTION_ACCESS_VIOLATION inside
    # blender::eevee::VelocityModule::geometry_steps_fill, in a memcpy. Retina
    # reached frame 152 of 576; BANC did not survive its import.
    #
    # It also explains a slowdown I could not account for: that job ran at
    # 68 s/frame where 33.5M faces had run at 2.3. A 25x cost for 29% more
    # geometry was never a scaling curve. It was three copies of the mesh being
    # marshalled every frame for a blur nothing here asks for.
    #
    # Nothing in this project wants motion blur: subjects are static and cameras
    # move slowly. The vector pass goes too, since that is the other thing that
    # makes VelocityModule allocate.
    scene.render.use_motion_blur = False
    if hasattr(scene.eevee, "use_motion_blur"):
        scene.eevee.use_motion_blur = False
    for vl in scene.view_layers:
        if hasattr(vl, "use_pass_vector"):
            vl.use_pass_vector = False

    if hasattr(scene.eevee, "use_shadows"):
        scene.eevee.use_shadows = USE_SHADOWS
    # Direct lighting only. Raytraced GI costs a lot on 70M faces and the
    # gradient world already supplies the ambient.
    if hasattr(scene.eevee, "use_raytracing"):
        scene.eevee.use_raytracing = USE_RAYTRACING
        print(f"[ca3] raytracing: {scene.eevee.use_raytracing}")
    # Let the world light the scene while the camera still sees black: render
    # with a transparent film and lay black in behind it in the compositor.
    scene.render.film_transparent = True
    # AgX (the 4.x default) rolls saturated colour toward white as it brightens.
    # Standard is plain sRGB and keeps hues vivid, matching how C4D renders.
    try:
        scene.view_settings.view_transform = VIEW_TRANSFORM
        scene.view_settings.look = VIEW_LOOK
        scene.view_settings.exposure = VIEW_EXPOSURE
        print(f"[ca3] view transform: {scene.view_settings.view_transform}")
    except TypeError as exc:
        print(f"[ca3] could not set view transform ({exc}), staying on "
              f"{scene.view_settings.view_transform}")
    scene.render.resolution_x, scene.render.resolution_y = RESOLUTION
    scene.render.image_settings.file_format = "PNG"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    scene.render.filepath = str(OUTPUT_DIR) + "\\ca3_"

    # bloom lives in the compositor in 4.2+, not in EEVEE
    scene.use_nodes = True
    nt = scene.node_tree
    for node in list(nt.nodes):
        nt.nodes.remove(node)
    rl = nt.nodes.new("CompositorNodeRLayers")
    glare = nt.nodes.new("CompositorNodeGlare")
    glare.glare_type = "BLOOM"
    if hasattr(glare, "quality"):
        glare.quality = "HIGH"

    # Blender 4.4 reworked this node: its controls moved from RNA properties onto
    # input sockets. Assigning glare.threshold / glare.mix there writes to dead
    # legacy properties, reads back as 0.0, and blooms the whole frame instead of
    # the highlights. Drive the sockets when they exist.
    sock = {s.name: s for s in glare.inputs}
    if "Threshold" in sock and "Strength" in sock:
        sock["Threshold"].default_value = BLOOM_THRESHOLD
        sock["Strength"].default_value = BLOOM_STRENGTH
        if "Smoothness" in sock:
            sock["Smoothness"].default_value = BLOOM_SMOOTHNESS
        if "Size" in sock:
            sock["Size"].default_value = BLOOM_SIZE
        if "Saturation" in sock:
            sock["Saturation"].default_value = BLOOM_SATURATION
        print(f"[ca3] bloom (4.4 sockets): threshold={sock['Threshold'].default_value} "
              f"strength={sock['Strength'].default_value} "
              f"size={sock['Size'].default_value if 'Size' in sock else 'n/a'}")
    else:
        glare.mix = BLOOM_MIX
        glare.threshold = BLOOM_THRESHOLD
        if hasattr(glare, "size"):
            glare.size = 8
        print(f"[ca3] bloom (legacy props): mix={glare.mix} "
              f"threshold={glare.threshold}")
    # black plate under the transparent film, so the world lights but never shows
    black = nt.nodes.new("CompositorNodeRGB")
    black.outputs[0].default_value = (0.0, 0.0, 0.0, 1.0)
    over = nt.nodes.new("CompositorNodeAlphaOver")
    comp = nt.nodes.new("CompositorNodeComposite")
    nt.links.new(rl.outputs["Image"], glare.inputs["Image"])
    nt.links.new(black.outputs["RGBA"], over.inputs[1])
    nt.links.new(glare.outputs["Image"], over.inputs[2])
    nt.links.new(over.outputs["Image"], comp.inputs["Image"])
    for node, loc in ((rl, (-600, 0)), (glare, (-380, 0)), (black, (-380, -220)),
                      (over, (-120, 0)), (comp, (140, 0))):
        node.location = loc



def build_camera_and_orbit(scene, root):
    """Camera on an orbiting empty, tracking the population root.

    Split out of build() so render_from_cache.py can rebuild it after loading the
    saved .blend, which lets framing and sweep stay editable without re-importing.

    Framing: TARGET_SIZE is the longest axis, so the bounding sphere can reach
    about 0.87 * TARGET_SIZE. Pull back far enough that the whole population stays
    inside the field of view across the sweep, and further still for a portrait
    frame, which is narrower horizontally.
    """
    bpy.ops.object.empty_add(type="PLAIN_AXES", location=(0, 0, 0))
    orbit = bpy.context.active_object
    orbit.name = "CAM_ORBIT"

    cam_dist = TARGET_SIZE * CAM_DISTANCE_MULT
    bpy.ops.object.camera_add(location=(0.0, -cam_dist, TARGET_SIZE * 0.35))
    cam = bpy.context.active_object
    cam.name = "CAM"
    cam.data.lens = CAM_LENS_MM
    cam.data.shift_y = CAM_SHIFT_Y
    cam.parent = orbit

    track = cam.constraints.new(type="TRACK_TO")
    track.target = root
    track.track_axis = "TRACK_NEGATIVE_Z"
    track.up_axis = "UP_Y"
    scene.camera = cam

    start_rot = math.radians(ORBIT_START_DEG)
    orbit.rotation_euler = (0.0, 0.0, start_rot)
    orbit.keyframe_insert(data_path="rotation_euler", frame=FRAME_START)
    orbit.rotation_euler = (0.0, 0.0, start_rot + ORBIT_TURNS * 2.0 * math.pi)
    orbit.keyframe_insert(data_path="rotation_euler", frame=scene.frame_end)
    for fc in orbit.animation_data.action.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"
    return cam, orbit


def build_synapse_cloud(parent, factor):
    """One vertex per real synapse, each instancing a small emissive sphere.

    Vertex instancing rather than 25,723 separate objects: Blender would crawl
    with that many objects, but a single mesh instancing one sphere is cheap.
    The sphere is sized in nanometres and then carried down by the root's scale
    along with everything else, so it stays correct at any TARGET_SIZE.
    """
    import numpy as np

    pts = np.load(str(SYNAPSE_NPY))

    # Blender's OBJ importer converts axes on the way in, mapping the file's
    # (x, y, z) onto (x, -z, y). Every cell arrived through that importer, so
    # these points need the same conversion or the cloud lands in a different
    # part of the scene entirely. Which is exactly what happened the first time.
    pts = np.column_stack([pts[:, 0], -pts[:, 2], pts[:, 1]])
    print(f"[ca3] synapse cloud: {len(pts):,} points, axes matched to the meshes")

    mesh = bpy.data.meshes.new("synapse_points")
    mesh.from_pydata([tuple(p) for p in pts], [], [])
    mesh.update()
    cloud = bpy.data.objects.new("SYNAPSES", mesh)
    bpy.context.scene.collection.objects.link(cloud)

    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=SYNAPSE_RADIUS_NM)
    dot = bpy.context.active_object
    dot.name = "synapse_dot"
    bpy.ops.object.shade_smooth()

    mat = bpy.data.materials.new("mat_synapse")
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    col = hexcol(SYNAPSE_COLOR)
    bsdf.inputs["Base Color"].default_value = (*col, 1.0)
    if "Emission Color" in bsdf.inputs:
        bsdf.inputs["Emission Color"].default_value = (*col, 1.0)
        bsdf.inputs["Emission Strength"].default_value = SYNAPSE_EMISSION
    dot.data.materials.append(mat)

    dot.parent = cloud
    dot.matrix_parent_inverse = Matrix.Identity(4)
    cloud.instance_type = "VERTS"
    dot.hide_render = False

    cloud.parent = parent
    cloud.matrix_parent_inverse = Matrix.Identity(4)

    # bloom the whole cloud in over its reveal window
    a, b = SYNAPSE_REVEAL
    dot.scale = (0.0, 0.0, 0.0)
    dot.keyframe_insert(data_path="scale", frame=int(a))
    dot.scale = (1.0, 1.0, 1.0)
    dot.keyframe_insert(data_path="scale", frame=int(b))
    set_interp(dot, "CUBIC", "EASE_OUT")
    return cloud


def build_lights(scene, size, target=None):
    """Three-point rig scaled to the population, with soft area lights."""
    specs = [
        ("KEY",  ( 1.15, -1.05,  0.85), KEY_ENERGY,  size * 1.1, (1.00, 0.97, 0.92)),
        ("FILL", (-1.30, -0.55,  0.10), FILL_ENERGY, size * 1.6, (0.72, 0.82, 1.00)),
        ("RIM",  (-0.35,  1.25,  0.75), RIM_ENERGY,  size * 1.2, (0.85, 0.90, 1.00)),
        ("TOP",  ( 0.05,  0.10,  1.60), TOP_ENERGY,  size * 1.4, (0.95, 0.95, 1.00)),
    ]
    for name, dirv, energy, lsize, colour in specs:
        loc = tuple(d * size for d in dirv)
        bpy.ops.object.light_add(type="AREA", location=loc)
        lt = bpy.context.active_object
        lt.name = name
        lt.data.energy = energy
        lt.data.size = lsize
        lt.data.color = colour
        # Smaller emitter = crisper shadow terminator. At 0.5 the branches
        # lost their separation in the dense regions.
        lt.data.shadow_soft_size = lsize * SHADOW_SOFTNESS
        con = lt.constraints.new(type="TRACK_TO")
        # caller may pass its own root; falling back to a hard-coded name meant
        # the lights had no target at all in the hero scene
        con.target = target or bpy.data.objects.get("CA3_ROOT")
        con.track_axis = "TRACK_NEGATIVE_Z"
        con.up_axis = "UP_Y"


def world_bounds(objects, pct=0.1, max_samples=20000):
    """Outlier-robust bounds.

    These meshes carry a handful of stray vertices per cell, typically 2 to 8 out of
    ~40,000, sitting hundreds of thousands of nanometres outside the dataset volume.
    A raw min/max bounding box follows those strays and collapses the auto-scale, so
    bounds come from percentiles instead. Measured on this data, p0.1 and p99.9 land
    exactly on the true volume edges (Z 4,324 and 96,439).
    """
    import numpy as np

    chunks = []
    for obj in objects:
        n = len(obj.data.vertices)
        if not n:
            continue
        co = np.empty(n * 3, dtype=np.float64)
        obj.data.vertices.foreach_get("co", co)
        co = co.reshape(-1, 3)
        if n > max_samples:
            co = co[np.linspace(0, n - 1, max_samples).astype(int)]
        m = np.array(obj.matrix_world)
        chunks.append(co @ m[:3, :3].T + m[:3, 3])

    if not chunks:
        return Vector((0, 0, 0)), Vector((0, 0, 0))

    allv = np.vstack(chunks)
    lo = np.percentile(allv, pct, axis=0)
    hi = np.percentile(allv, 100 - pct, axis=0)
    dropped = int((~((allv >= lo) & (allv <= hi)).all(axis=1)).sum())
    print(f"[ca3] robust bounds from {len(allv):,} sampled verts "
          f"({dropped:,} outside p{pct}/p{100 - pct} ignored)")
    return Vector(lo), Vector(hi)


def collect_sources(spec):
    """Gather .obj paths across a group's folders, deduplicated by segment id."""
    by_seg = {}
    for folder in spec["dirs"]:
        if not folder.exists():
            continue
        for path in sorted(folder.glob("*.obj")):
            # Skip the scratch files the download and decimate scripts write
            # while they work. "*.obj" also matches "<id>.raw.obj" and
            # "<id>.tmp.obj", and those are deleted underneath us, so a render
            # started mid-download dies on a file that vanished between the
            # glob and the import.
            if path.name.endswith((".raw.obj", ".tmp.obj")):
                continue
            seg = path.stem.replace("-meshlab", "")
            if MAX_MB_PER_CELL and path.stat().st_size > MAX_MB_PER_CELL * 1024 * 1024:
                continue
            # keep the larger file when the same cell appears in two folders
            if seg not in by_seg or path.stat().st_size > by_seg[seg].stat().st_size:
                by_seg[seg] = path
    return by_seg


def strip_stray_faces(obj, max_edge_nm=MAX_EDGE_NM):
    """Delete faces stretched to the stray vertices.

    Each mesh carries a few junk vertices sitting hundreds of thousands of nm
    outside the volume, and they ARE referenced by faces, so every one drags a
    huge thin triangle across the scene. Real faces here are sub-micron, so any
    face with an edge longer than max_edge_nm is an artifact, not anatomy.
    """
    import bmesh

    bm = bmesh.new()
    bm.from_mesh(obj.data)
    limit = max_edge_nm * max_edge_nm
    doomed = set()
    for face in bm.faces:
        for edge in face.edges:
            a, b = edge.verts
            if (a.co - b.co).length_squared > limit:
                doomed.add(face)
                break
    n = len(doomed)
    if n:
        bmesh.ops.delete(bm, geom=list(doomed), context="FACES")
        bmesh.ops.delete(
            bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
        bm.to_mesh(obj.data)
        obj.data.update()
    bm.free()
    return n


def set_interp(obj, interp, easing):
    if obj.animation_data and obj.animation_data.action:
        for fc in obj.animation_data.action.fcurves:
            for kp in fc.keyframe_points:
                kp.interpolation = interp
                kp.easing = easing


# -------------------------------------------------------------------------------- build
def build():
    if CLEAR_SCENE:
        clear_scene()

    scene = bpy.context.scene
    scene.render.fps = FPS
    scene.frame_start = FRAME_START
    scene.frame_end = FRAME_END

    all_cells = []
    group_objects = {}

    unknown = [g for g in ENABLED if g not in GROUPS]
    if unknown:
        raise SystemExit(f"ENABLED names not in GROUPS: {unknown}")

    for group_name in ENABLED:
        spec = GROUPS[group_name]
        coll = make_collection(group_name)
        # Opaque unless a group explicitly asks otherwise. This used to key off
        # "sublayer", which silently made nine of the eleven populations 55%
        # transparent and broke depth sorting and shadow receiving in EEVEE.
        alpha = spec.get("alpha", 1.0)
        mat = emissive_material(f"mat_{group_name}", spec["color"], alpha)
        per_cell = spec.get("per_cell_range")
        objs = []

        if TEST_WITH_PRIMITIVES:
            for i in range(6):
                bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=40000)
                o = bpy.context.active_object
                o.location = (i * 90000, (hash(group_name) % 3) * 60000, 0)
                objs.append(o)
        else:
            sources = collect_sources(spec)
            if not sources:
                where = ", ".join(str(d) for d in spec["dirs"])
                raise SystemExit(
                    f"No .obj files found for {group_name} in {where}. "
                    "Run ca3_layers_decimate.py first, or set TEST_WITH_PRIMITIVES = True."
                )
            for seg, path in sorted(sources.items()):
                before = set(bpy.data.objects)
                bpy.ops.wm.obj_import(filepath=str(path))
                new = [o for o in bpy.data.objects if o not in before and o.type == "MESH"]
                for o in new:
                    o.name = f"{group_name}_{seg}"
                objs.extend(new)

        shades = (shade_ramp(per_cell[0], per_cell[1], len(objs))
                  if per_cell else None)
        stripped = 0
        for idx, o in enumerate(objs):
            for c in list(o.users_collection):
                c.objects.unlink(o)
            coll.objects.link(o)
            if STRIP_STRAY_FACES and not TEST_WITH_PRIMITIVES:
                stripped += strip_stray_faces(o)
            o.data.materials.clear()
            if shades:
                o.data.materials.append(
                    emissive_material(f"mat_{group_name}_{idx:02d}",
                                      shades[idx], alpha))
            else:
                o.data.materials.append(mat)
            bpy.ops.object.select_all(action="DESELECT")
            o.select_set(True)
            bpy.context.view_layer.objects.active = o
            bpy.ops.object.shade_smooth()

        group_objects[group_name] = objs
        all_cells.extend(objs)
        print(f"[ca3] {group_name}: {len(objs)} cells"
              + (f", stripped {stripped:,} stray faces" if stripped else ""))

    total_faces = sum(len(o.data.polygons) for o in all_cells)
    print(f"[ca3] {len(all_cells)} cells total, {total_faces:,} faces")

    # --- normalise position and scale via a root empty -----------------------------
    # Hierarchy is root -> per-group pivot -> cells, and every matrix_parent_inverse
    # stays identity. The pivots sit at -center in pre-scale units, so the root's
    # scale is what carries the population down to TARGET_SIZE. Setting a parent
    # inverse at any level here would cancel that scale back out.
    lo, hi = world_bounds(all_cells)
    center = (lo + hi) / 2.0
    span = max((hi - lo)[i] for i in range(3))
    factor = TARGET_SIZE / span if span else 1.0
    print(f"[ca3] bounds span {span:,.0f} nm -> scale {factor:.3e}")

    bpy.ops.object.empty_add(type="PLAIN_AXES", location=(0.0, 0.0, 0.0))
    root = bpy.context.active_object
    root.name = "CA3_ROOT"
    root.scale = (factor, factor, factor)

    base = -center
    pivots = {}
    for group_name, objs in group_objects.items():
        bpy.ops.object.empty_add(type="PLAIN_AXES", location=base)
        pivot = bpy.context.active_object
        pivot.name = f"pivot_{group_name}"
        pivot.parent = root
        pivot.matrix_parent_inverse = Matrix.Identity(4)
        for o in objs:
            o.parent = pivot
            o.matrix_parent_inverse = Matrix.Identity(4)
        pivots[group_name] = pivot

    # --- real synapse locations, on their own pivot so they centre like the cells ------
    if SHOW_SYNAPSES:
        bpy.ops.object.empty_add(type="PLAIN_AXES", location=base)
        syn_pivot = bpy.context.active_object
        syn_pivot.name = "pivot_synapses"
        syn_pivot.parent = root
        syn_pivot.matrix_parent_inverse = Matrix.Identity(4)
        build_synapse_cloud(syn_pivot, factor)

    # --- staggered build-on reveal, per group ----------------------------------------
    for group_name, objs in group_objects.items():
        r_start, r_end = GROUPS[group_name]["reveal"]
        last_start = max(r_start, r_end - REVEAL_LEN)
        n = len(objs)
        for i, o in enumerate(objs):
            t = i / max(1, n - 1)
            start = r_start + t * (last_start - r_start)
            o.scale = (0.0, 0.0, 0.0)
            o.keyframe_insert(data_path="scale", frame=int(start))
            o.scale = (1.0, 1.0, 1.0)
            o.keyframe_insert(data_path="scale", frame=int(start + REVEAL_LEN))
            set_interp(o, "CUBIC", "EASE_OUT")

    # --- optional sublayer separation --------------------------------------------------
    if SEPARATE_LAYERS:
        extent = hi - lo
        axis = min(range(3), key=lambda i: extent[i])
        sublayers = [g for g in group_objects if GROUPS[g]["sublayer"]]
        print(f"[ca3] separating {len(sublayers)} sublayers along axis {'XYZ'[axis]}")
        for i, group_name in enumerate(sublayers):
            pivot = pivots[group_name]
            sign = 1.0 if i == 0 else -1.0
            offset = list(base)
            pivot.location = offset
            pivot.keyframe_insert(data_path="location", frame=SEP_START)
            offset[axis] += sign * (SEPARATION / 2.0) / factor
            pivot.location = offset
            pivot.keyframe_insert(data_path="location", frame=SEP_END)
            set_interp(pivot, "SINE", "EASE_IN_OUT")

    # --- camera on an orbiting empty ------------------------------------------------------
    build_camera_and_orbit(scene, root)

    # --- lighting and world ------------------------------------------------------------
    build_world(scene)
    build_lights(scene, TARGET_SIZE)

    apply_render_settings(scene)

    print(f"[ca3] scene built: {FRAME_END - FRAME_START + 1} frames @ {FPS}fps, "
          f"{RESOLUTION[0]}x{RESOLUTION[1]}, {SAMPLES} samples")
    print(f"[ca3] output -> {scene.render.filepath}")

    if RENDER:
        print("[ca3] rendering animation (this uses the GPU)")
        bpy.ops.render.render(animation=True)
    else:
        print("[ca3] RENDER = False, scene built but not rendered")


if __name__ == "__main__":
    build()
