# Hairy brain: the recipe

Everything needed to reproduce the furry brain renders from 4 September 2026,
in case the chat is lost. Copy any command into a terminal on Aurelius.

## What it is

A real human brain surface covered in short hair strands, coloured by which
way each patch of cortex faces, rendered in Cycles on a white studio floor.

- Script: `D:\Meshes\hairy_brain_360.py` (turntable, anatomical stills, every
  palette and style). Cutaway companion: `D:\Meshes\hairy_brain_cutaway.py`.
- Meshes: `C:\Users\amyle\Downloads\pial_Full_obj\pial_Full_obj\` (left and
  right pial) and `C:\Users\amyle\Downloads\human brain subcortical_obj\subcortical_obj\`
  (cerebellum, brainstem, deep structures). Anderson Winkler, "Brain for
  Blender", brainder.org, FreeSurfer 5.2, CC BY-SA 3.0. Credit him on anything
  public.
- Blender: `C:\Program Files\Blender Foundation\Blender 4.4\blender.exe`
- Output: `D:\Meshes\renders\`

## The keeper looks

Blue-gold fur, three views (purples, blues, teal, golden yellow; the pink
version is `palette=amy` with the same flags):

```
"C:\Program Files\Blender Foundation\Blender 4.4\blender.exe" --background --python D:\Meshes\hairy_brain_360.py -- views=hero,sagittal,axial palette=bluegold gold=1.0,0.82,0.18 length=0.02 out=D:\Meshes\renders\hairy_brain_bluegold.mp4
```

Golden dot hologram (tiny emissive strands on an opaque dark cortex):

```
"C:\Program Files\Blender Foundation\Blender 4.4\blender.exe" --background --python D:\Meshes\hairy_brain_360.py -- views=hero,coronal style=holo_dots holocol=gold strands=2000000 dotglow=1.8 out=D:\Meshes\renders\hairy_brain_holo_dots_gold.mp4
```

Vivid fur (hot pink, orange, yellow, teal, turquoise, blues, purples):

```
"C:\Program Files\Blender Foundation\Blender 4.4\blender.exe" --background --python D:\Meshes\hairy_brain_360.py -- views=coronal,sagittal,axial palette=vivid out=D:\Meshes\renders\hairy_brain.mp4
```

Cutaway (left cortex off, left deep structures coloured per structure):

```
"C:\Program Files\Blender Foundation\Blender 4.4\blender.exe" --background --python D:\Meshes\hairy_brain_cutaway.py --
```

360 turntable, 15 s at 24 fps, queue it rather than run it:

```
D:\Meshes\queue.ps1 add -Project brain -Name hairy_brain_360 -Script D:\Meshes\hairy_brain_360.py -Arguments "frames=360","palette=bluegold","gold=1.0,0.82,0.18","length=0.02","out=D:\Meshes\renders\hairy_brain_360.mp4" -Minutes 110 -Note "beats checked" -AddedBy "me"
```

Studio HDRI version, 0.8 mm fur (Amy: "the lighting doesn't look good,
studio light" and "20% current length"). The map replaces the four area
lights; the camera still sees the flat grey backdrop:

```
"C:\Program Files\Blender Foundation\Blender 4.4\blender.exe" --background --python D:\Meshes\hairy_brain_360.py -- views=hero,sagittal,axial palette=bluegold gold=1.0,0.82,0.18 length=0.004 radius=0.0009 strands=4000000 surfdark=0.55 curvepts=2 hairsubdiv=0 hdri=C:/Users/amyle/Documents/cyclorama_hard_light_4k.hdr hdristrength=1.8 hdrirot=90 out=D:\Meshes\renders\hairy_brain_bluegold_velvet.mp4
```

HDRIs tried: Poly Haven `cyclorama_hard_light_4k.hdr` (C:\Users\amyle\Documents,
the keeper: strength 1.8, hdrirot=90 so the key comes from the camera side and the front is lit; 2.8 at rot 0 blew out the crown and left the face in shadow), Blender's bundled `studio.exr` (dim,
blue-heavy), `je_gray_02_2k.exr` (hard sun shadow, not a studio). Very short
hair needs many more strands (coverage goes with length squared) and a matte
surface under it, or the pial mesh shows through as glossy plastic.

## Arguments

| flag | meaning | default |
|---|---|---|
| `views=` | `coronal,sagittal,axial,threequarter,hero`, straight stills | turntable instead |
| `stills=` | frame numbers from the turntable as PNG beats | |
| `frames=` | turntable length | 360 |
| `palette=` | `vivid, bluegold, amy, blue, september, pastel, rainbow` | vivid |
| `style=` | `fur, holo_dots, crystal, holo_blue, holo_amber` | fur |
| `holocol=` | `gold, warm, amber, blue` for holo_dots | blue |
| `length=` | strand length, scene units (1 unit = 100 mm) | 0.010 |
| `strands=` | strands per hemisphere | 1200000 |
| `gold=` | r,g,b of the gold channel (amy, bluegold) | 1.0,0.86,0.42 |
| `light=` | multiplier on the whole light rig | 0.6 (0.8 for bluegold) |
| `huetilt=` | how much up/down tilt shifts the colour | 0.3 |
| `camh=` | camera height, % of brain height above the floor (50 = level with centre); unset = old 14 deg look-down | unset |
| `camdist=` | farther back with a longer lens, framing unchanged | 1.0 |
| `sweep=` | comma list of camh values, one still each, from the hero bearing | |
| `lightfollow=1` | area lights parented to the camera rig so they travel with it on the turntable | off |
| `hdri=`, `hdristrength=`, `hdrirot=` | studio HDRI instead of the area lights | off |
| `res=` | WxH | 1920x1080 |
| `samples=` | Cycles samples | 128 |

## The blue-gold palette

Ramp by facing direction (no gold in the ramp, gold is its own channel so it
never blends to khaki):

| pos | colour | rgb |
|---|---|---|
| 0.00 | light bright blue | 0.45 0.80 1.00 |
| 0.20 | deep purple | 0.42 0.15 0.75 |
| 0.38 | royal blue | 0.15 0.28 0.95 |
| 0.55 | sky blue | 0.55 0.85 1.00 |
| 0.72 | teal | 0.05 0.62 0.60 |
| 0.86 | light purple | 0.68 0.55 0.95 |
| 1.00 | cobalt | 0.10 0.45 0.98 |

Gold channel: `1.00 0.82 0.18`. Since "yellow should be at the peaks/top"
(Amy, 4 Sept) it goes on the gyral CROWNS: each vertex gets a "peak" value
(how far the surface sits outside a 60-pass Laplacian-smoothed copy of
itself, normalised by percentiles), sampled onto each strand root, and gold
is a steep smoothstep from `peaklo=0.86` to `peakhi=0.97`. Lower peaklo for
more gold. `goldmode=facing` gives the old front-and-back placement.
Ambient occlusion cannot do this on dense fur: neighbouring strands shade
every point equally.

Final command for that look:

```
"C:\Program Files\Blender Foundation\Blender 4.4\blender.exe" --background --python D:\Meshes\hairy_brain_360.py -- views=hero,sagittal,axial palette=bluegold gold=1.0,0.82,0.18 length=0.004 radius=0.0009 strands=4000000 surfdark=0.55 curvepts=2 hairsubdiv=0 hdri=C:/Users/amyle/Documents/cyclorama_hard_light_4k.hdr hdristrength=1.8 hdrirot=90 out=D:\Meshes\renders\hairy_brain_bluegold_peaks.mp4
```

## Things that cost time, so you do not repeat them

- Geometry-node fur inside a MESH object never reached Cycles. Host strands
  on a Curves object (`bpy.data.hair_curves`) that reads the mesh via Object
  Info.
- Emissive strands need `mat.cycles.emission_sampling = "NONE"`, or Cycles
  builds a light tree over millions of them (3 hours a frame).
- Never put haze in the world volume with hair in the scene (40 s per
  sample). Use a bounded box with the same density (7 s a frame).
- Colour by the clean surface normal, not the jittered strand direction, or
  palette boundaries scatter.
- Gold blended along a ramp into teal or blue goes olive or khaki. Keep gold a
  separate sharp channel.
- Desaturating a rainbow gives flesh tones. Pastels need real chroma or they
  merge into lilac grey.
- With 8M strands, 4 points per strand plus hair subdivision 2 blew the OptiX
  BVH build out of GPU memory ("out of GPU and shared host memory"), even
  though the same scene had rendered once before. Straight sub-millimetre
  bristles need `curvepts=2 hairsubdiv=0`; the render is identical and fits.
- Hair shorter than about 0.5 mm is under a pixel at 1080p: at 0.1 mm you are
  looking at the surface material, not fur.
- Motion blur off. Never render during the day, queue it.
