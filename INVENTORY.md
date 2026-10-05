# Inventory of D:\Meshes

Taken 4 October 2026 on Aurelius, without moving or changing anything there.
Every script, what project and stage it belongs to, what it runs in, the
arguments it reads, and whether it is current. [MANIFEST.csv](MANIFEST.csv) has
the same rows as data, plus the original path, the absolute paths each script
touches, the libraries it imports, its size, date and a short hash.

## How to read it

- **stage**: `download`, `decimate`, `import`, `light`, `animate`, `encode` as in
  RENDERING.md, plus `select` (choosing cells from connectivity), `fields`
  (skeletons and distance fields a signal travels along), `qc`, `run` (a
  launcher) and `data` (a small input file).
- **status**: `current` is what you would use today. `superseded` has a
  replacement named in the note. `one-off` did a single repair. `scratch` is a
  worked example.
- **runs in**: `Blender 4.4` means `blender --background --python <script> --
  key=value ...`. `venv` means `D:\Meshes\.venv\Scripts\python.exe`.
- **arguments** are the `key=value` names or `--flags` found in the source.
  Each script's header is the authority on what they mean.
- Every script expects the flat `D:\Meshes` layout. See RENDERING.md section 1.

## Environment

| | |
|---|---|
| machine | Aurelius, Windows 11, RTX 3090 24 GB, 63.7 GB RAM |
| Blender | 4.4, `C:\Program Files\Blender Foundation\Blender 4.4\blender.exe`. Also installed: 3.4, and 5.0.1 at `D:\Blender5` |
| Python | `D:\Meshes\.venv`, a plain venv on Python 3.10.5. Not conda |
| cloud-volume | 12.14.2, in the venv |
| caveclient | 8.2.1, in the venv |
| also in the venv | meshparty 2.0.3, pymeshlab 2025.7.post1, trimesh 4.12.2, fast-simplification 0.2.0, numpy 2.2.6, pandas 2.3.3, scipy 1.15.3, pillow 12.3.0, pyarrow 25.0.0, h5py 3.16.0 |
| full list | [requirements-aurelius.txt](requirements-aurelius.txt) |
| CAVE token | `~/.cloudvolume/secrets/cave-secret.json`. Present. Not opened, not copied |
| CAVE servers | `~/.cloudvolume/secrets/cave_datastack_to_server_map.json` maps `stroeh_mouse_retina`, `minnie65_public`, `pni_mec` and `pinky_sandbox` to `https://global.daf-apis.com` |
| ffmpeg | 8.0.1, on PATH |
| git | `D:\Meshes` is itself a git repo, remote `amyleesterling/ca3-rendering` (private), last pushed 30 July 2026, with uncommitted and untracked work since |
| queue | `D:\Meshes\queue.ps1` forwards to `C:\Users\amyle\render-queue\queue.ps1`. Scheduled task `MeshesRenderQueue`, state Ready |

## Blender: import, light, animate, encode

### `blender/banc/`

| script | project | stage | status | runs in | arguments | what it is |
|---|---|---|---|---|---|---|
| `banc_bodyparts.py` | banc | select | current | venv |  | Label each of the descending neuron's targets with the body part it innervates. **Note:** CAVE queries that choose or describe the cast; venv |
| `banc_dng100_webp.py` | banc | encode | current | venv |  | Encode the DNg100 walking-speed layer to lossless WebP, and audit the alpha. |
| `banc_dng12_anim.py` | banc | animate | superseded | Blender 4.4 | `device` `outdir` `rest` `samples` `sigma` `skelalpha` `skelr` `tail` | 16-frame explanatory signal sequence for the BANC DNg12 population. **Note:** generalised into banc_signal_anim.py |
| `banc_dng12_polarity.py` | banc | fields | superseded | venv |  | Skeletons, synapse polarity and geodesic path distance for the DNg12 population. **Note:** generalised into banc_signal_polarity.py |
| `banc_dnp03_identify.py` | banc | select | current | venv |  | Resolve DNp03 in BANC v888 before anything is rendered. **Note:** CAVE queries that choose or describe the cast; venv |
| `banc_flight_dodge_anim.py` | banc | animate | current | Blender 4.4 | `device` `outdir` `samples` `side` | 12-frame quick-dodge pulse for DNp03, one sequence per anatomical hemisphere. |
| `banc_flight_dodge_qc.py` | banc | qc | current | venv |  | Encode the quick-dodge sequences and produce the QC deliverables. |
| `banc_grooming_identify.py` | banc | select | current | venv |  | Identification gate for the grooming job: DNg12 and wPN1 in BANC v888. **Note:** CAVE queries that choose or describe the cast; venv |
| `banc_grooming_qc.py` | banc | qc | current | venv |  | QC for the DNg12 grooming assets: encode the sequence and audit everything. |
| `banc_label.py` | banc | encode | current | venv |  | Draw a colour key onto a BANC render. |
| `banc_layer_stats.py` | banc | select | current | venv |  | Count cells and synapses per app layer, so the HUD stats are measured. **Note:** CAVE queries that choose or describe the cast; venv |
| `banc_layers_backlog.ps1` | banc | run | current | PowerShell |  | Render every banc-explorer layer that is missing, static and pulse. **Note:** launch Blender directly for minutes-long layer stills; check the GPU is free first |
| `banc_layers_webp.py` | banc | encode | current | venv | `dry` `dst` `src` | Encode every rendered banc-explorer layer to lossless WebP, and audit the alpha. |
| `banc_render.py` | banc | animate | superseded | Blender 4.4 | `flip` `lens` `margin` `out` `res` `samples` `shot` | First look at a BANC cast in Blender, reusing the CA3 look. **Note:** first look still; the shot scripts replace it |
| `banc_shotA_cast.py` | banc | select | current | venv |  | Shot A cast: the T1 left local loop, chosen from connectivity. **Note:** CAVE queries that choose or describe the cast; venv |
| `banc_shotB_anim.py` | banc | animate | current | Blender 4.4 | `frames` `out` `overlay` `res` `samples` `still` `stills` | Shot B: one descending neuron, many body parts. **Note:** the model for frames= res= samples= out= stills= |
| `banc_shotB_overlay.py` | banc | encode | current | venv | `beats` `frames` `out` | Label the BANC descending neuron film, so it says what it is showing. |
| `banc_signal_anim.py` | banc | animate | current | Blender 4.4 | `color` `device` `frames` `outdir` `polarity` `pop` `rest` `samples` `sigma` `skelalpha` `skelr` `tail` | 16-frame explanatory signal sequence for the BANC DNg12 population. |
| `banc_signal_polarity.py` | banc | fields | current | venv |  | Skeletons, synapse polarity and geodesic path distance for any BANC cell set. **Note:** skeleton, synapse polarity and geodesic distance for any cell set; venv |
| `banc_signal_qc.py` | banc | qc | current | venv |  | Encode a signal sequence to WebP and audit it. Reusable for any batch. |
| `banc_walkingsteering_camera.py` | banc | import | current | venv |  | Derive a Blender camera from the live Neuroglancer camera, and PROVE it matches. **Note:** derives the Blender camera from the Neuroglancer matrices and proves it |
| `banc_walkingsteering_go.ps1` | banc | run | current | PowerShell |  | launch Blender directly for minutes-long layer stills; check the GPU is free first |
| `banc_walkingsteering_layers_webp.py` | banc | encode | current | venv |  | Encode the four stacked layers to WebP and prove they are pixel aligned. |
| `banc_walkingsteering_poster.py` | banc | animate | current | Blender 4.4 | `device` `emit` `frames` `layer` `light` `meshes` `out` `pulse` `pulse_axis` `pulse_base` `pulse_glow` `pulse_width` `samples` | Render the BANC walking+steering poster: 81 neurons, transparent background. **Note:** Cycles, 1600x1200 transparent layers; also renders the pulse sequences |
| `banc_walkingsteering_webp.py` | banc | encode | current | venv |  | Encode the poster PNG to spec WebP, and audit the alpha rather than trust it. |

### `blender/banc/data/`

| file | project | what |
|---|---|---|
| `cast.json` | banc | lives at D:\Meshes\banc\ in production |
| `descending_ranked.csv` | banc | lives at D:\Meshes\banc\ in production |
| `dn_endocrine.json` | banc | lives at D:\Meshes\banc\ in production |
| `dn_targets.json` | banc | lives at D:\Meshes\banc\ in production |
| `dng12_groups.json` | banc | lives at D:\Meshes\banc\ in production |
| `dng12_population.json` | banc | lives at D:\Meshes\banc\ in production |
| `dnp03_candidates.json` | banc | lives at D:\Meshes\banc\ in production |
| `epg_angles.json` | banc | lives at D:\Meshes\banc\ in production |
| `epg_camera.json` | banc | lives at D:\Meshes\banc\ in production |
| `epg_sectors.json` | banc | lives at D:\Meshes\banc\ in production |
| `flight_batch_ids.json` | banc | lives at D:\Meshes\banc\ in production |
| `leg_mn_with_neuromere_module.csv` | banc | lives at D:\Meshes\banc\ in production |
| `pop_dng02.json` | banc | lives at D:\Meshes\banc\ in production |
| `pop_landing.json` | banc | lives at D:\Meshes\banc\ in production |
| `pop_mnb1_left.json` | banc | lives at D:\Meshes\banc\ in production |
| `pop_mnb1_right.json` | banc | lives at D:\Meshes\banc\ in production |
| `shotA_groups.json` | banc | lives at D:\Meshes\banc\ in production |
| `shotA_ids.json` | banc | lives at D:\Meshes\banc\ in production |
| `shotB_beats.json` | banc | lives at D:\Meshes\renders\ in production |
| `shotB_bodyparts.json` | banc | lives at D:\Meshes\banc\ in production |
| `walking_steering_camera.json` | banc | lives at D:\Meshes\banc\ in production |
| `walking_steering_ids.json` | banc | lives at D:\Meshes\banc\ in production |
| `walking_steering_layers.json` | banc | lives at D:\Meshes\banc\ in production |

### `blender/brain/`

| script | project | stage | status | runs in | arguments | what it is |
|---|---|---|---|---|---|---|
| `hairy_brain_360.py` | brain | animate | current | Blender 4.4 | `camdist` `camh` `curvepts` `debug` `device` `dotglow` `frames` `gold` `goldmax` `goldmode` `hairsubdiv` `haze` `hdri` `hdrirot` `hdristrength` `holocol` `huetilt` `interior` `length` `light` `lightfollow` `motes` `out` `palette` | Hairy brain, 360 degree turntable. **Note:** human brain, Cycles; not a connectome project, here because it shares the queue |
| `hairy_brain_cutaway.py` | brain | animate | current | Blender 4.4 | `huetilt` `length` `light` `out` `radius` `res` `samples` `strands` | Hairy brain, cutaway: the left cortex lifted off to show what sits under it. **Note:** human brain, Cycles; not a connectome project, here because it shares the queue |

### `blender/ca3/`

| script | project | stage | status | runs in | arguments | what it is |
|---|---|---|---|---|---|---|
| `ap_fields.py` | ca3 | fields | current | venv |  | Distance fields that an action potential can travel along. **Note:** cable distance fields; run in the venv (scipy), handed to Blender as .npz |
| `ap_fields6.py` | ca3 | fields | current | venv |  | Distance fields for all six mossy fibres onto the hero cell. **Note:** cable distance fields; run in the venv (scipy), handed to Blender as .npz |
| `ap_six.py` | ca3 | animate | current | Blender 4.4 | `arc` `camdist` `corridor` `cpeak` `cwidth` `dof` `flash` `fpeak` `frames` `fstop` `fwidth` `out` `res` `samples` `still` `sub` `wide` | Six mossy fibres, two attempts, and only the second one fires the cell. |
| `ap_test.py` | ca3 | animate | current | Blender 4.4 | `aim` `arc` `camdist` `cpeak` `cwidth` `debug` `dof` `flash` `follow` `fpeak` `frames` `fstop` `fwidth` `out` `push` `res` `samples` `still` `wide` | An action potential travelling real cable. |
| `build_cache.py` | ca3 | import | current | Blender 4.4 | `out` `synapses` | Build the full scene once and save it as a .blend. **Note:** imports every population once, saves ca3_scene.blend |
| `build_partner_cache.py` | ca3 | import | one-off | Blender 4.4 |  | One-off: bake the native hero + its 6 fibres + the 56 partner cells into a |
| `export_web.py` | ca3 | encode | current | venv |  | Web-sized meshes with the action potential field baked into vertex colours. **Note:** GLB with the distance field packed into vertex colours, for the site |
| `gradient_sweep.py` | ca3 | animate | current | Blender 4.4 | `band` `camdist` `dim` `frames` `out` `peak` `png` `samples` `shifty` `still` | A band of light travels the cell layer, so the convergence result is watched, not asserted. |
| `hero_full.py` | ca3 | animate | current | Blender 4.4 | `at` `beats` `cellact` `far` `farcell` `frames` `out` `parthold` `partneralpha` `purple` `res` `samples` `scope` `still` `transparent` | The hero shot, but it actually pulls back to the whole population. **Note:** also the entry point for the inhibition shot, as scope=inhibition |
| `hero_shot.py` | ca3 | animate | superseded | Blender 4.4 | `frames` `out` `res` `samples` `still` | The hero shot: one thorny pyramidal cell, its mossy fibre boutons, then pull back. **Note:** builds its own scene from hero/ alone; hero_full.py replaces it |
| `inhib_fields.py` | ca3 | fields | current | venv | `rebuild` | Cable distance field for the feedforward inhibition shot. **Note:** cable distance fields; run in the venv (scipy), handed to Blender as .npz |
| `inhibition_shot.py` | ca3 | animate | current | Blender 4.4 | `aimdrop` `arc` `axon` `dimmf` `dof` `far` `fill` `frames` `fstop` `lens` `margin` `mid` `near` `open` `peak` `shifty` `width` | Beats 1 to 7 of the selective feedforward inhibition shot. **Note:** not run on its own; driven by hero_full.py |
| `label_volume.py` | ca3 | encode | current | venv |  | Dimension labels on the volume diagram. **Note:** post passes in Pillow |
| `ladder_measure.py` | ca3 | qc | current | venv |  | Measure the framing of the scale ladder test frames, instead of eyeballing it. |
| `patch_cloud.py` | ca3 | import | one-off | Blender 4.4 |  | Rebuild just the synapse cloud inside the existing .blend. |
| `render_360.py` | ca3 | animate | superseded | Blender 4.4 | `frames` `out` `reveal` `start` `turns` | Render the full 360 orbit as an mp4. **Note:** re-import 13 GB of OBJ on every run; render_from_cache.py replaces them |
| `render_from_cache.py` | ca3 | animate | current | Blender 4.4 | `blend` `frames` `out` `reveal` `start` `still` `synapses` `synreveal` `turns` | Render from the saved .blend instead of re-parsing 13 GB of OBJ. **Note:** use this for anything involving the full population |
| `render_gradient.py` | ca3 | animate | current | Blender 4.4 | `cache` `camdist` `frames` `out` `samples` `shifty` `still` `view` | The proximodistal convergence gradient, 304 real cells coloured by MF input count. |
| `render_still.py` | ca3 | animate | superseded | Blender 4.4 |  | Render one frame of the CA3 scene. **Note:** re-import 13 GB of OBJ on every run; render_from_cache.py replaces them |
| `scale_ladder.py` | ca3 | animate | current | Blender 4.4 | `blockshift` `cache` `cellshift` `cpeak` `cwidth` `flared` `flash` `fpeak` `fstop` `fwidth` `maxcells` `out` `rblock` `rcell` `rcontact` `res` `samples` `still` `stills` `sub` `syne` `synflash` `synr` | The scale ladder. One block, one cell, one contact, one spike. |
| `sweep_readout.py` | ca3 | encode | current | venv | `band` `frames` `src` | Composite the live readout onto the gradient sweep frames. **Note:** post passes in Pillow |
| `synapse_story.py` | ca3 | animate | current | Blender 4.4 | `camdist` `frames` `out` `res` `samples` `shifty` `start` `still` `synemit` `turns` | The synapse story, paced to be watched rather than skimmed. |
| `volume_diagram.py` | ca3 | animate | current | Blender 4.4 | `az` `camdist` `cellglow` `elev` `emstrength` `out` `res` `samples` | A scale diagram of the reconstructed volume. |

### `blender/ca3/data/`

| file | project | what |
|---|---|---|
| `captions_population.json` | ca3 |  |
| `captions_synapse.json` | ca3 |  |
| `em_registration.json` | ca3 | lives at D:\Meshes\renders\ in production |
| `fibre_order.txt` | ca3 | lives at D:\Meshes\renders\ in production |
| `hero_ids.txt` | ca3 | lives at D:\Meshes\renders\ in production |

### `blender/ca3/runners/`

| script | project | stage | status | runs in | arguments | what it is |
|---|---|---|---|---|---|---|
| `chain2.sh` | ca3 | run | superseded | bash |  | Fire the MICrONS render when decimation finishes OR at 07:35, whichever first. **Note:** launch Blender directly. The queue replaced all of these; kept for their measured camera values |
| `chain3.sh` | ca3 | run | superseded | bash |  | launch Blender directly. The queue replaced all of these; kept for their measured camera values |
| `chain_microns.sh` | ca3 | run | superseded | bash |  | wait for decimation, then render the column still **Note:** launch Blender directly. The queue replaced all of these; kept for their measured camera values |
| `framing_sweep.ps1` | ca3 | run | superseded | PowerShell |  | Dial in the vertical framing empirically. Cheap now that geometry comes from **Note:** launch Blender directly. The queue replaced all of these; kept for their measured camera values |
| `render_ab.ps1` | ca3 | run | superseded | PowerShell |  | Two full-population frames, identical except for the palette variant. **Note:** launch Blender directly. The queue replaced all of these; kept for their measured camera values |
| `render_all.ps1` | ca3 | run | superseded | PowerShell |  | Render the two remaining animations back to back, then encode both for web. **Note:** launch Blender directly. The queue replaced all of these; kept for their measured camera values |
| `render_ap_all.ps1` | ca3 | run | superseded | PowerShell |  | The three action potential cuts, then a web encode of each. **Note:** launch Blender directly. The queue replaced all of these; kept for their measured camera values |
| `render_morning.ps1` | ca3 | run | superseded | PowerShell |  | The two built shots, serially. Launched 05:30 against an 08:30 deadline. **Note:** launch Blender directly. The queue replaced all of these; kept for their measured camera values |
| `render_tonight.ps1` | ca3 | run | superseded | PowerShell |  | Overnight render queue. **Note:** launch Blender directly. The queue replaced all of these; kept for their measured camera values |
| `rt_shadow_matrix.ps1` | ca3 | run | superseded | PowerShell |  | Controlled 2x2: does raytracing interact with shadows to explain the timing? **Note:** launch Blender directly. The queue replaced all of these; kept for their measured camera values |
| `run_sweep.ps1` | ca3 | run | current | PowerShell |  | The arc sweep, in three passes, because the readout is composited rather than **Note:** the three pass pattern: PNG sequence, composite, encode. Queue the render pass rather than running this as is |

### `blender/ca3/skeletons/`

| script | project | stage | status | runs in | arguments | what it is |
|---|---|---|---|---|---|---|
| `README.md` | ca3 | notes | current |  |  |  |
| `axon_step10_final.py` | ca3 | fields | superseded | venv |  | Step 10: terminal-branch statistics inside the descending arbor, then write **Note:** axon and soma investigation for the hero cell |
| `axon_step11_verify.py` | ca3 | fields | superseded | venv |  | axon and soma investigation for the hero cell |
| `axon_step12_annotate.py` | ca3 | fields | superseded | venv |  | axon and soma investigation for the hero cell |
| `axon_step1_mesh.py` | ca3 | fields | superseded | venv |  | Step 1: parse hero OBJ vertices + faces, cache as npy. Also compute **Note:** axon and soma investigation for the hero cell |
| `axon_step2_metrics.py` | ca3 | fields | superseded | venv |  | Step 2: per-node geometric metrics, graph structure, synapse diagnostics. **Note:** axon and soma investigation for the hero cell |
| `axon_step3_topo.py` | ca3 | fields | superseded | venv |  | Step 3: diagnose the parent tree, build a clean BFS tree from soma, **Note:** axon and soma investigation for the hero cell |
| `axon_step4_partition.py` | ca3 | fields | superseded | venv |  | Step 4: build the axon mask from the descending/ascending partition **Note:** axon and soma investigation for the hero cell |
| `axon_step5_decisive.py` | ca3 | fields | superseded | venv |  | Step 5: the decisive test. Incoming synapse density (dendritic marker) **Note:** axon and soma investigation for the hero cell |
| `axon_step6_hunt.py` | ca3 | fields | superseded | venv |  | Step 6: mesh-accurate synapse assignment, primary-process characterisation, **Note:** axon and soma investigation for the hero cell |
| `axon_step7_view.py` | ca3 | fields | superseded | venv |  | Step 7: look at the cell. Project the skeleton in OBJ x-y (frame axes) and **Note:** axon and soma investigation for the hero cell |
| `axon_step8_radius.py` | ca3 | fields | superseded | venv |  | Step 8: proper cross-sectional radius (slab method) + hunt for the true axon: **Note:** axon and soma investigation for the hero cell |
| `axon_step9_trunks.py` | ca3 | fields | superseded | venv |  | Step 9: enumerate the trunks crossing a shell around the soma, and score each **Note:** axon and soma investigation for the hero cell |
| `bbox_check.py` | ca3 | fields | superseded | venv |  | axon and soma investigation for the hero cell |
| `blob_hunt.py` | ca3 | fields | superseded | venv |  | Find the largest inscribed sphere in the hero mesh -> locates a soma if one exists. **Note:** axon and soma investigation for the hero cell |
| `crosscheck.py` | ca3 | fields | superseded | venv |  | Independent checks on how much cable the hero mesh actually contains. **Note:** axon and soma investigation for the hero cell |
| `fetch2.py` | ca3 | fields | superseded | venv |  | axon and soma investigation for the hero cell |
| `fetch4.py` | ca3 | fields | superseded | venv |  | axon and soma investigation for the hero cell |
| `finalize.py` | ca3 | fields | current | venv |  | Assemble canonical skeletons + ap_paths.json + report.json. **Note:** builds the canonical skeleton .npz files |
| `find_soma.py` | ca3 | fields | superseded | venv |  | decimated hero mesh vertices (uniform decimation -> vertex count ~ surface area) **Note:** axon and soma investigation for the hero cell |
| `hero_meshparty.py` | ca3 | fields | current | venv |  | Dense skeleton of the hero cell with meshparty, from the NATIVE mesh. **Note:** builds the canonical skeleton .npz files |
| `mf_meshparty.py` | ca3 | fields | current | venv |  | Fallback: skeletonize the 6 mossy-fibre meshes locally with meshparty. **Note:** builds the canonical skeleton .npz files |
| `probe_cave.py` | ca3 | fields | superseded | venv |  | axon and soma investigation for the hero cell |
| `recenter.py` | ca3 | fields | current | venv |  | Move meshparty skeleton nodes onto the tube axis. **Note:** builds the canonical skeleton .npz files |
| `soma_center.py` | ca3 | fields | superseded | venv |  | axon and soma investigation for the hero cell |
| `soma_final.py` | ca3 | fields | superseded | venv |  | --- where do the 165 MF synapses land? (raw CSV coords) --- **Note:** axon and soma investigation for the hero cell |
| `soma_radius.py` | ca3 | fields | superseded | venv |  | axon and soma investigation for the hero cell |
| `validate.py` | ca3 | fields | current | venv |  | Final validation of ap_paths.json against the npz files. **Note:** builds the canonical skeleton .npz files |
| `verify_mf.py` | ca3 | fields | current | venv |  | Verify the meshparty MF skeletons: bbox agreement with the OBJ, connectivity, **Note:** builds the canonical skeleton .npz files |
| `vol_test.py` | ca3 | fields | superseded | venv |  | axon and soma investigation for the hero cell |

### `blender/common/`

| script | project | stage | status | runs in | arguments | what it is |
|---|---|---|---|---|---|---|
| `_purple_swatch.py` | all | light | scratch | Blender 4.4 | `out` | Colour check for the partner purple. **Note:** worked example of choosing a colour in the render rather than the picker |
| `ca3_animation.py` | all | import, light, encode | current | Blender 4.4 |  | CA3 connectivity animation: presynaptic deep/superficial pyramidal cells plus their **Note:** THE core module. Materials, world, lights, camera, render settings. Every project's scripts exec it from D:\Meshes\ca3_animation.py |
| `caption_video.py` | all | encode | current | venv | `crf` | Burn timed captions onto a rendered sequence, in the house HUD idiom. **Note:** burns timed captions from a JSON spec onto frames, then encodes |
| `framecheck.py` | all | qc | current | venv | `pct` `thresh` | Measure framing instead of eyeballing it. **Note:** measures height fill and clipping of a still; runs in the venv |

### `blender/fafb/`

| script | project | stage | status | runs in | arguments | what it is |
|---|---|---|---|---|---|---|
| `epg_layers_webp.py` | fafb | encode | current | venv |  | Encode the EPG base and heading overlays to WebP, and audit the whole set. |
| `epg_manifest.py` | fafb | encode | current | venv |  | Build the EPG manifest and verify it against the pixels that were actually rendered. |
| `epg_ring_poster.py` | fafb | animate | current | Blender 4.4 | `basesat` `baseval` `denoise` `device` `emit` `exclude` `fill` `huedir` `hueoffset` `light` `meshes` `out` `samples` `sat` `savecam` `val` `ydir` `zdir` | Render the 54 FAFB EPG compass neurons, frontal view, transparent background. **Note:** 54 FAFB EPG cells from the meshparty library; not one of the four projects |

### `blender/microns/data/`

| file | project | what |
|---|---|---|
| `microns_area.json` | microns | lives at D:\Meshes\renders\ in production |
| `microns_celltypes.csv` | microns | lives at D:\Meshes\renders\ in production |
| `microns_idmap.json` | microns | lives at D:\Meshes\renders\ in production |
| `microns_somas.csv` | microns | lives at D:\Meshes\renders\ in production |

### `blender/microns/`

| script | project | stage | status | runs in | arguments | what it is |
|---|---|---|---|---|---|---|
| `microns_column.py` | microns | animate | current | Blender 4.4 | `az0` `az1` `camdist` `camnear` `colour` `el0` `el1` `frames` `glow` `huejit` `litjit` `out` `samples` `shifty` `src` `view` | A core through cortex: proofread MICrONS neurons coloured by cortical depth. **Note:** stills and the orbit; one Blender unit per micrometre |
| `microns_overlay.py` | microns | encode | current | venv | `frames` `out` `types` | Burn a cell-type legend onto the cortex orbit frames. |

### `blender/retina/`

| script | project | stage | status | runs in | arguments | what it is |
|---|---|---|---|---|---|---|
| `retina_bookend.py` | retina | encode | current | venv | `dissolve` `fade` `hold` `out` `seq` | Assemble the retina film: the opening stages, the sweeps, and a closing fade. |
| `retina_ds_anim.py` | retina | animate | current | Blender 4.4 | `anat_glow` `anatomy` `bar` `frames` `meshdir` `out` `overlay` `res` `samples` `stages` `still` `stills` | Retina: direction selectivity, measured. |
| `retina_overlay.py` | retina | encode | current | venv | `frames` `out` `total` | Composite the readout overlays onto the retina frames. |
| `retina_stage_overlay.py` | retina | encode | current | venv |  | Label each opening stage with the key that is actually true of it. |
| `retina_strat_anim.py` | retina | animate | current | Blender 4.4 | `build` `colour` `frames` `glow` `mode` `out` `push` `res` `samples` `still` `stills` | Retina: where each cell puts its dendrites, and why that is the answer. |

## Decimate

### `decimate/banc/`

| script | project | stage | status | runs in | arguments | what it is |
|---|---|---|---|---|---|---|
| `banc_walkingsteering_decimate.py` | banc | decimate | current | venv |  | Decimate the 81 walking+steering meshes to a density the poster can actually use. **Note:** 10 faces per um2 for a 1 um per pixel poster; has a plan mode |

### `decimate/ca3/`

| script | project | stage | status | runs in | arguments | what it is |
|---|---|---|---|---|---|---|
| `ca3_layers_decimate.py` | ca3 | decimate | superseded | venv |  | Phase 2: smooth + decimate the CA3 meshes to 40% of their original face count. **Note:** flat 40 percent, bridged branches; replaced by the hq pass |
| `decimate_partners_lite.py` | ca3 | decimate | one-off | venv |  | Re-decimate the 56 partner cells down to the density the rest of the **Note:** repair for the keep-floor mistake in download_partners.py |
| `meshparty_decimate.py` | ca3 | decimate | superseded | venv |  | Smooth + decimate the meshparty hippocampal folders to 40% of their face count. **Note:** flat 40 percent, bridged branches; replaced by the hq pass |
| `meshparty_decimate_hq.py` | ca3 | decimate | current | venv |  | Higher-quality re-decimation of the meshparty hippocampal folders. **Note:** the good pass for the legacy CA3 folders: strip components, area density, keep floor |
| `smooth-decimate-40pct.mlx` | ca3 | decimate | superseded |  |  | flat 40 percent, bridged branches; replaced by the hq pass |

### `decimate/common/`

| script | project | stage | status | runs in | arguments | what it is |
|---|---|---|---|---|---|---|
| `mesh_budget_ladder.py` | any | decimate | current | venv | `budgets` `cell` `dir` `out` | How far can a cell be decimated before its dendrites break? Measure, do not guess. **Note:** the measurements behind the faces per um2 rule |
| `mesh_clean.py` | any | decimate | current | venv | `ao` `apply` `bbox-tol` `debris` `dir` `min-keep` `minfaces` `n` `target-mb` | Clean a connectomics mesh before decimating it. Debris, then interior, then decimate. **Note:** interior removal by ambient occlusion; component removal is OFF by default on purpose |
| `mesh_clean_normals.py` | any | decimate | superseded | venv |  | Test the hypothesis: ambient occlusion is useless here because the normals are wrong. **Note:** probes whose conclusions are folded into mesh_clean.py and the playbook |
| `mesh_clean_sweep.py` | any | decimate | superseded | venv |  | Find an ambient-occlusion threshold that removes interior without eating surface. **Note:** probes whose conclusions are folded into mesh_clean.py and the playbook |
| `mesh_clean_sweep2.py` | any | decimate | superseded | venv |  | Sweep ambient occlusion on its ACTUAL scale, and verify by rendering. **Note:** probes whose conclusions are folded into mesh_clean.py and the playbook |
| `mesh_clean_variants.py` | any | decimate | current | venv | `cell` `minfaces` `out` `src` | Produce cleaning variants of one cell so a RENDER can decide between them. **Note:** the measurements behind the faces per um2 rule |
| `mesh_clean_verify.py` | any | decimate | superseded | venv |  | Does cleaning change what you can SEE? Silhouette test, no GPU needed. **Note:** probes whose conclusions are folded into mesh_clean.py and the playbook |
| `mesh_compare_render.py` | any | qc | current | Blender 4.4 | `out` `res` `samples` `zoom` | Render two mesh variants from an IDENTICAL camera so a person can judge them. **Note:** renders two variants from one camera so a person can judge them |
| `mesh_dust_ao.py` | any | decimate | current | venv | `cell` `dir` `minfaces` | Are the dust pieces INSIDE the cell? Visibility, not topology, is the test. **Note:** evidence that the dust is enclosed inner shells, not litter |
| `mesh_dust_probe.py` | any | decimate | current | venv | `cell` `dir` `minfaces` | Is the small-component "dust" really dust, on FULL RESOLUTION meshes? **Note:** evidence that the dust is enclosed inner shells, not litter |
| `mesh_pipeline_test.py` | any | decimate | current | venv | `cell` `dir` `out` `target` | The cleaning pipeline, and the variants that let a render judge it. **Note:** the measurements behind the faces per um2 rule |

### `decimate/microns/`

| script | project | stage | status | runs in | arguments | what it is |
|---|---|---|---|---|---|---|
| `decimate_microns.py` | microns | decimate | superseded | venv | `faces` `workers` | Decimate the MICrONS cells to something renderable. **Note:** flat face count gave an 8x density spread |
| `decimate_microns_area.py` | microns | decimate | current | venv | `density` `dst` `workers` | Decimate the MICrONS cells to a constant face density, not a constant face count. **Note:** 100 faces per um2; reads renders/microns_area.json |

### `decimate/retina/`

| script | project | stage | status | runs in | arguments | what it is |
|---|---|---|---|---|---|---|
| `retina_build_library.py` | retina | decimate | current | venv | `ds-density` `ghost-density` `min-faces` `out` `src` `workers` | Build the render-ready retina mesh library from full resolution. **Note:** clean then decimate to a density, two budgets (35 and 6 faces per um2) |
| `retina_decimate.py` | retina | decimate | superseded | venv |  | Bring the freshly downloaded retina meshes down to the weight of the ones that **Note:** earlier attempts, kept for the reasoning in their headers |
| `retina_soma_clean.py` | retina | decimate | superseded | venv | `apply` `minfaces` `n` | Find and remove the hidden geometry inside these cells. **Note:** earlier attempts, kept for the reasoning in their headers |
| `retina_soma_probe.py` | retina | decimate | superseded | venv |  | Do these meshes really carry hidden polygons inside the somas, and how many? **Note:** earlier attempts, kept for the reasoning in their headers |

## Download

### `download/banc/`

| script | project | stage | status | runs in | arguments | what it is |
|---|---|---|---|---|---|---|
| `banc_download.py` | banc | download | current | venv |  | Download a BANC cast to OBJ, resumable, with the worker pool capped at 4. **Note:** CAVE graphene source, needs the token; OBJ in nanometres |
| `banc_walkingsteering_download.py` | banc | download | current | venv |  | Download the 81 BANC walking+steering neurons from the PUBLIC precomputed bucket. **Note:** public precomputed bucket, no token; OBJ in nanometres |

### `download/ca3/`

| script | project | stage | status | runs in | arguments | what it is |
|---|---|---|---|---|---|---|
| `ca3_layers_download.py` | ca3 | download | current | venv |  | Phase 1: download full-resolution CA3 pyramidal meshes from CAVE (zheng_ca3). **Note:** meshparty MeshMeta into an .h5 cache; decimation is a separate phase |
| `download_gradient.py` | ca3 | download | current | venv |  | Download + decimate the proximodistal-gradient sample into D:\Meshes\gradient\. **Note:** download and decimate in one pass, area-based target, no keep-floor. Reads renders/gradient_sample.csv, which is not in this repo |
| `download_hero.py` | ca3 | download | current | venv |  | Pull the hero thorny cell and its mossy fibres from CAVE at full resolution. **Note:** native resolution, no decimation, for close ups |
| `download_partners.py` | ca3 | download | superseded | venv |  | Download the cells that the hero's 6 mossy fibres also contact. **Note:** its 0.40 keep-floor won on every cell; use download_gradient.py as the pattern |
| `pull_em_slice.py` | ca3 | download | current | venv |  | One EM cross-section covering the reconstructed footprint. **Note:** one EM plane from the public precomputed image volume, for a background plate |
| `pull_synapses.py` | ca3 | download | current | venv |  | Pull the ENTIRE synapses_ca3_v1 table (36.8M rows) from CAVE mat 671. **Note:** whole synapse table by id-range chunks; the source of every synapse point cloud |
| `redownload_population.py` | ca3 | download | current | venv |  | Re-download a meshparty population from CAVE at full resolution. **Note:** re-pull a legacy population from CAVE at full resolution, decimate by area |

### `download/retina/`

| script | project | stage | status | runs in | arguments | what it is |
|---|---|---|---|---|---|---|
| `retina_download.py` | retina | download | current | venv |  | Download the calcium-imaged cells that have no mesh staged yet. **Note:** CAVE, full resolution, retries 502/503/504 |
| `retina_functional_table.py` | retina | select | current | venv |  | Build one row per cell: mesh, cell type, direction tuning, and the bar tuning curve. **Note:** builds functional_cells.csv, the table every retina script reads |
| `retina_stage_meshes.py` | retina | download | superseded | venv |  | Copy the calcium-imaged cell meshes out of the read-only meshparty library. **Note:** copied the meshparty downsampled library, which turned out unusable as a source |

## Notes

### `notes/`

| file | project | what |
|---|---|---|
| `ORGANISATION.md` | all |  |
| `RENDERING_NEURONS.md` | all |  |

### `notes/banc/`

| file | project | what |
|---|---|---|
| `BANC_ANIMATION_IDEAS.md` | banc |  |
| `BANC_ASSET_HANDOFF.md` | banc |  |
| `BANC_RENDER_HANDOFF.md` | banc |  |
| `BANC_WALKING_STEERING_POSTER.md` | banc |  |
| `BE_THE_FLY_NEURON_RESEARCH_BRIEF.md` | banc |  |
| `HANDOFF_grooming_batch.md` | banc |  |

### `notes/brain/`

| file | project | what |
|---|---|---|
| `HAIRY_BRAIN_RECIPE.md` | brain |  |

### `notes/ca3/`

| file | project | what |
|---|---|---|
| `STORYBOARD_inhibition.md` | ca3 |  |

## Web

`web/eyewire2/` was copied from the ca3 site repo, not from `D:\Meshes`. See [web/README.md](web/README.md).

| file | project | stage | status | runs in | what it is |
|---|---|---|---|---|---|
| `fetch_meshes.py` | retina | download, decimate | current | any Python with caveclient, cloud-volume, trimesh, fast-simplification | CAVE to one GLB per cell in micrometres, plus `index.json` |
| `col3d.html` | retina | import, light, animate | current, on a branch | a browser, three.js | the 3D column of cells; exposes `READY`, `TOTAL_FRAMES`, `setFrame(i)` |
| `index.html` | retina | animate | current | a browser | the earlier film, one dot per soma |
| `cap.js` | retina | encode | current | Node, Playwright, ffmpeg | steps frames in headless Chromium and pipes them to ffmpeg |

## In D:\Meshes and not copied

### Files in the root

| file | size | kind | why |
|---|---|---|---|
| `ca3_scene.blend` | 7.4 GB | scene cache | never committed. Rebuilt by the cache scripts in `blender/ca3/` |
| `ca3_scene.blend1` | 7.4 GB | scene cache | never committed. Rebuilt by the cache scripts in `blender/ca3/` |
| `ca3_scene_partners.blend` | 7.7 GB | scene cache | never committed. Rebuilt by the cache scripts in `blender/ca3/` |
| `ca3_scene_partners.blend1` | 9.0 GB | scene cache | never committed. Rebuilt by the cache scripts in `blender/ca3/` |
| `gradient_scene.blend` | 1.3 GB | scene cache | never committed. Rebuilt by the cache scripts in `blender/ca3/` |
| `ladder_scene.blend` | 6.8 GB | scene cache | never committed. Rebuilt by the cache scripts in `blender/ca3/` |
| `ladder_scene.blend1` | 6.4 GB | scene cache | never committed. Rebuilt by the cache scripts in `blender/ca3/` |
| `branch_map.py` | 3 KB | CA3 analysis | connectivity analysis, not a rendering stage. Tracked only in the private repo; left out of this public one. See RENDERING.md section 14 |
| `build_convergence.py` | 6 KB | CA3 analysis | connectivity analysis, not a rendering stage. Tracked only in the private repo; left out of this public one. See RENDERING.md section 14 |
| `dg_locate.py` | 2 KB | CA3 analysis | connectivity analysis, not a rendering stage. Tracked only in the private repo; left out of this public one. See RENDERING.md section 14 |
| `diagnose.py` | 4 KB | CA3 analysis | connectivity analysis, not a rendering stage. Tracked only in the private repo; left out of this public one. See RENDERING.md section 14 |
| `final_gradient.py` | 9 KB | CA3 analysis | connectivity analysis, not a rendering stage. Tracked only in the private repo; left out of this public one. See RENDERING.md section 14 |
| `fit_axis.py` | 3 KB | CA3 analysis | connectivity analysis, not a rendering stage. Tracked only in the private repo; left out of this public one. See RENDERING.md section 14 |
| `frag_by_z.py` | 4 KB | CA3 analysis | connectivity analysis, not a rendering stage. Tracked only in the private repo; left out of this public one. See RENDERING.md section 14 |
| `frag_test.py` | 3 KB | CA3 analysis | connectivity analysis, not a rendering stage. Tracked only in the private repo; left out of this public one. See RENDERING.md section 14 |
| `geom.py` | 3 KB | CA3 analysis | connectivity analysis, not a rendering stage. Tracked only in the private repo; left out of this public one. See RENDERING.md section 14 |
| `gradient.py` | 7 KB | CA3 analysis | connectivity analysis, not a rendering stage. Tracked only in the private repo; left out of this public one. See RENDERING.md section 14 |
| `gradient_figure.py` | 3 KB | CA3 analysis | connectivity analysis, not a rendering stage. Tracked only in the private repo; left out of this public one. See RENDERING.md section 14 |
| `layer3d.py` | 5 KB | CA3 analysis | connectivity analysis, not a rendering stage. Tracked only in the private repo; left out of this public one. See RENDERING.md section 14 |
| `mf_rule.py` | 5 KB | CA3 analysis | connectivity analysis, not a rendering stage. Tracked only in the private repo; left out of this public one. See RENDERING.md section 14 |
| `mf_validate.py` | 5 KB | CA3 analysis | connectivity analysis, not a rendering stage. Tracked only in the private repo; left out of this public one. See RENDERING.md section 14 |
| `probe2.py` | 2 KB | CA3 analysis | connectivity analysis, not a rendering stage. Tracked only in the private repo; left out of this public one. See RENDERING.md section 14 |
| `probe3.py` | 2 KB | CA3 analysis | connectivity analysis, not a rendering stage. Tracked only in the private repo; left out of this public one. See RENDERING.md section 14 |
| `probe_cave.py` | 887 B | CA3 analysis | connectivity analysis, not a rendering stage. Tracked only in the private repo; left out of this public one. See RENDERING.md section 14 |
| `proofread_test.py` | 4 KB | CA3 analysis | connectivity analysis, not a rendering stage. Tracked only in the private repo; left out of this public one. See RENDERING.md section 14 |
| `rule_scan.py` | 3 KB | CA3 analysis | connectivity analysis, not a rendering stage. Tracked only in the private repo; left out of this public one. See RENDERING.md section 14 |
| `sample_gradient.py` | 3 KB | CA3 analysis | connectivity analysis, not a rendering stage. Tracked only in the private repo; left out of this public one. See RENDERING.md section 14 |
| `spread_test.py` | 3 KB | CA3 analysis | connectivity analysis, not a rendering stage. Tracked only in the private repo; left out of this public one. See RENDERING.md section 14 |
| `type_partners.py` | 3 KB | CA3 analysis | connectivity analysis, not a rendering stage. Tracked only in the private repo; left out of this public one. See RENDERING.md section 14 |
| `zcheck.py` | 3 KB | CA3 analysis | connectivity analysis, not a rendering stage. Tracked only in the private repo; left out of this public one. See RENDERING.md section 14 |
| `BANC_PENDING_JOBS.md` | 5 KB | note | job state from 3 August, superseded by the queue |
| `CLUSTER_PLAN.md` | 14 KB | note | Princeton cluster planning and correspondence. Not a rendering procedure |
| `DELLA_PROPOSAL.docx` | 14 KB | note | Princeton cluster planning and correspondence. Not a rendering procedure |
| `DELLA_PROPOSAL.md` | 10 KB | note | Princeton cluster planning and correspondence. Not a rendering procedure |
| `DELLA_PROPOSAL.pdf` | 308 KB | note | Princeton cluster planning and correspondence. Not a rendering procedure |
| `EMAIL_visrc.md` | 2 KB | note | Princeton cluster planning and correspondence. Not a rendering procedure |
| `HANDOFF.md` | 25 KB | note | the rendering sections are in `notes/ca3/HANDOFF_rendering.md`. The analysis sections were left out |
| `QUEUE_NEXT.md` | 5 KB | note | dated state from 29 and 30 July, superseded by the queue |
| `QUEUE_TONIGHT.md` | 5 KB | note | dated state from 29 and 30 July, superseded by the queue |
| `RENDER_PROTOCOL.md` | 4 KB | note | the authoritative copy is in render-queue |
| `STATUS.md` | 8 KB | note | dated state from 29 and 30 July, superseded by the queue |
| `queue.ps1` | 278 B | queue | four line shim onto `C:\Users\amyle\render-queue\queue.ps1`. Not touched |
| `render_queue.json` | 2 KB | queue | a stale copy from 30 July. The live state is in render-queue. Not touched |
| `_min.py` | 843 B | scratch | minimal Blender probes from the MICrONS scale diagnosis |
| `_min2.py` | 2 KB | scratch | minimal Blender probes from the MICrONS scale diagnosis |
| `_one_cell.py` | 1 KB | scratch | minimal Blender probes from the MICrONS scale diagnosis |
| `.gitignore` | 1 KB | git | for the private repo |
| `pyr_mark.png` | 13 KB | image | a marked up render |
| 41 run logs (`*.log`, `*_log.txt`, `*_err.txt`, `*.err`) | 1.2 MB | log | real face counts, timings and failures. They stay on disk |

### Folders

Sizes measured 4 October 2026.

| folder | size | files | what |
|---|---|---|---|
| `hq` | 13.1 GB | 1697 | CA3 populations after `meshparty_decimate_hq.py`. What the CA3 cache was built from |
| `CA3 deep layer, CA3 superficial layer` | 2.9 GB | 16 | CA3 presynaptic cells from `ca3_layers_download.py` and the first 40 percent pass |
| `MF 700, pyr 600, pyr fibers, pyr MF pyc, pyr pyr 2, inhibitory ca3 28, sparsely thorny pyramidals ca3 68, thorny pyramidals ca3 250` | 5.6 GB | 1714 | CA3 legacy populations from the first flat 40 percent pass. Superseded by `hq` |
| `hero` | 0.2 GB | 7 | the featured CA3 cell and its six mossy fibres, native resolution |
| `partners, partners_lite` | 2.4 GB | 112 | 56 partner cells, as downloaded and after the repair pass |
| `gradient` | 2.3 GB | 304 | 304 cells for the convergence gradient |
| `_cache_zheng_ca3` | 4.3 GB | 101 | meshparty `.h5` download cache |
| `syn_chunks` | 1.0 GB | 93 | the whole CA3 synapse table as parquet |
| `skeletons` | 0.2 GB | 93 | skeleton `.npz` files and distance fields. Its scripts are in `blender/ca3/skeletons/` |
| `banc` | 22.3 GB | 1309 | BANC meshes (`shotA`, `shotB`, `walking_steering`, `walking_steering_dec`, `compass`, `light_exit`) and small cast files. The cast files are in `blender/banc/data/` |
| `microns, microns_hi, microns_area, _mic_one` | 8.7 GB | 115 | 38 MICrONS cells at three decimations. `microns_area` (100 faces/um2) is the current one |
| `retina` | 35.5 GB | 965 | `meshes_full` 364 cells at full resolution, `meshes_clean` 364 render ready, `meshes` 202 from the old library (do not use), `clean_test`, and `functional` (calcium recordings, parquet) |
| `renders` | 20.5 GB | 12822 | every render, frame sequence and log, plus small derived tables. `queue_log.txt` is here |
| `fafb` | 10.5 GB | 1374 | FAFB meshes. Other work; no scripts |
| `mouse-wiring` | 70.5 GB | 40561 | source data for whatisabrain.com/mouse. Its own pull scripts (`pull_mouselight.py`, `allen_to_glb.py`, `allen/pull_regions.py`, `ion/pull_ion.py`, `ion/pull_cortex.py`, `seu/pull_seu.sh`) were not copied. Another project |
| `cryoet, molecules` | 1.8 GB | 28 | other work; no scripts |
| `shiu` | 0.2 GB | 20 | a third party fly brain model (`Drosophila_brain_model`), with its own `environment.yml`. Not a rendering tool |
| `.venv` |  |  | the Python environment. Described above, frozen in `requirements-aurelius.txt` |

### Small files left behind on purpose

| file | why |
|---|---|
| `retina\functional_cells.csv`, `retina\caimgd_celltypes.csv`, `retina\caimgd_ids.json`, `retina\mesh_paths.json`, `retina\functional\*` | calcium imaging data from another lab. The retina scripts need `functional_cells.csv`. See RENDERING.md section 14 |
| `renders\gradient_sample.csv`, `renders\partner_types.csv` | outputs of the CA3 analysis that was left out |
| `banc\cell_info_tags_v888.json` | 138 KB cache of a CAVE table, regenerated by `banc_grooming_identify.py` |
| `banc\*_audit.json`, `banc\grooming_identity.json`, `banc\shotA_cast.csv` | outputs of the identify and polarity scripts |
| `finish_ds4.ps1` | a one-off that overlaid, encoded and shelved one retina film. Its commit command carries a personal email address, so it was left out of a public repo |
| `captions_*.json` | copied, in `blender/ca3/data/` |

## Counts

182 files copied from `D:\Meshes`: 84 current, 52 superseded, 3 one-off, 1 scratch scripts, the rest data files and notes.
