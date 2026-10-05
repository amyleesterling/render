# render

A guide to rendering neurons with AI.

This is the code and the written procedure behind every neuron render made on
Aurelius, the Windows machine with the RTX 3090: mouse hippocampus (CA3), the fly
brain and nerve cord (BANC), mouse visual cortex (MICrONS) and mouse retina
(Eyewire II). It exists so that a session on any machine can find how cells get
downloaded, downsampled, rendered, queued, reviewed and published.

**Start with [RENDERING.md](RENDERING.md).** It is one section per stage and
assumes you have never seen the machine.

## What is here

| path | what |
|---|---|
| [RENDERING.md](RENDERING.md) | the guide: download, decimate, import, light, animate, beat check, queue, encode, review, publish |
| [INVENTORY.md](INVENTORY.md) | every script, with its project, stage, arguments, what it expects and whether it is current |
| [MANIFEST.csv](MANIFEST.csv) | the same list as data, with the original path of each file on Aurelius |
| `download/` | mesh and table downloads, per project |
| `decimate/` | cleaning and decimation, common tools and per project passes |
| `blender/common/` | `ca3_animation.py`, the one module every Blender script loads |
| `blender/<project>/` | the Blender scripts, their post passes and small input files |
| `queue/` | how the overnight render queue works. The queue itself is [render-queue](https://github.com/amyleesterling/render-queue) |
| `review/` | the approval shelf. The shelf itself is [review](https://github.com/amyleesterling/review) |
| `web/eyewire2/` | the path with no Blender and no GPU: CAVE to GLB to three.js to ffmpeg |
| `notes/` | the playbook and the handoff documents, moved here as written |
| `requirements-aurelius.txt` | `pip freeze` of the production Python environment |

## What is not here

Meshes, renders, `.blend` scene caches, logs and tokens. They stay on Aurelius
under `D:\Meshes`. The CAVE token lives in `~/.cloudvolume/secrets/cave-secret.json`
on each machine and is never committed.

## One thing to know before running anything

Production is a flat directory, `D:\Meshes`, and the scripts were written there.
Most of them carry absolute paths such as `D:\Meshes\ca3_animation.py` and
`D:\Meshes\renders\`. They are copied here unmodified and sorted into folders by
stage, so **they run as is on Aurelius from `D:\Meshes`, and need their paths
changed anywhere else.** RENDERING.md section 1 says how.

## The three rules that cost the most to learn

1. If you built an animation, add it to the queue and stop. Do not render it.
2. Render stills at each beat and look at them before you queue anything.
3. Neurons are submerged in fluid. They are never glossy.
