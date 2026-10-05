# Storyboard: selective feedforward inhibition in CA3

Target cut: **432 frames at 24 fps, 18.0 seconds.**
Source: Zheng et al. 2025, *Connectomic reconstruction from hippocampal CA3 reveals spatially graded mossy fiber inputs and selective feedforward inhibition to pyramidal cells* (bioRxiv, PMC12338526), Fig. 6 and Fig. 7.

Every number below is verified against `D:\Meshes\renders\mf_synapses.csv` and CAVE datastack `zheng_ca3` materialization 671, table `synapses_ca3_v1`. Nothing here is taken on trust from the abstract.

---

## The verified chain

All meshes named below are already on disk. No download needed.

| Step | Segment ID | Synapses | Mesh location |
|---|---|---|---|
| Mossy fiber (hero) | `648518346430566932` | 1 onto the interneuron, the closest of 7 at 14.4 um from its soma | `D:\Meshes\MF 700\` |
| 6 supporting mossy fibers | `648518346464178392`, `648518346442262773`, `648518346446894282`, `648518346438632308`, `648518346445589428`, `648518346446219982` | 1 each, 7 MF synapses total | `D:\Meshes\MF 700\` |
| Interneuron | `648518346437066458` | receives 7 MF synapses, 3,171 inputs total, 2,025 clean outputs | `D:\Meshes\inhibitory ca3 28\` |
| Thorny pyramidal targets | 87 cells, top 5 are `648518346440884391` (19), `648518346455289164` (13), `648518346432746039` (11), `648518346445408345` (10), `648518346448761921` (10) | **333 synapses onto 87 cells** | `D:\Meshes\thorny pyramidals ca3 250\` |
| Sparsely thorny targets | 21 cells, top is `648518346439923632` (9) | **50 synapses onto 21 cells** | `D:\Meshes\sparsely thorny pyramidals ca3 68\` |

**Selectivity, as measured:** 333 synapses onto 87 of 182 available thorny cells versus 50 synapses onto 21 of 68 available sparsely thorny cells. Normalised by how many cells of each subtype we hold meshes for, that is **2.49 times more inhibition per thorny cell**. Raw synapse ratio is 6.7 to 1.

**Perisomatic check:** median straight line distance from this interneuron's output synapses to the postsynaptic nucleus centre is **36.5 um**, with 80 percent under 50 um. The paper's own dendrite targeting threshold is a mode beyond 50 um, so this cell sits on the perisomatic side.

**Sublayer separation, which the shot can exploit:** the 87 thorny targets have a mean soma depth of z = 60,927 nm, the 21 sparsely thorny targets sit deeper at z = 67,409 nm. The two subtypes really do occupy different sheets, so a side on camera will separate them without any cheating.

**Caution to respect while animating.** The two interneurons with by far the most mossy fiber input, `648518346443611459` with 94 MF synapses and `648518346449783368` with 66, are **unusable**. Each has roughly 9,900 incoming synapses but only 139 and 81 clean outgoing ones, and zero onto any pyramidal cell we hold a mesh for. They are dendrite only fragments whose axons were never reconstructed or leave the volume. Do not build the shot on them.

Raw CAVE outputs are polluted by autapses exactly as the earlier analysis on this project warned. For the hero interneuron, 182 of 2,207 raw outgoing synapses were self edges. All counts above are after filtering `post_pt_root_id != pre_pt_root_id` and dropping any row whose synapse `id` also appears in the incoming set.

## Palette

| Element | Hex | Source |
|---|---|---|
| Mossy fibers | `#E8A93A` | house style |
| Thorny pyramidal | `#2E8BE0` | house style |
| Sparsely thorny pyramidal | `#9F72EC` | `GROUPS["sparsely_thorny"]` in `ca3_animation.py` |
| Interneuron | `#17A06B` | `GROUPS["inhibitory"]` in `ca3_animation.py` |

Note a small inconsistency to resolve before rendering: `GROUPS` in `ca3_animation.py` currently carries `#E2AF5E` for mossy fibers and a per cell blue ramp of `#1858C7` to `#2586F5` for thorny cells, neither of which is exactly the house value. Pick one and make them agree.

All neurons are submerged in tissue. **IOR 1.04, never glossy.** Let subsurface carry the read, not specular.

---

## Beats

### Beat 1. The field
**Frames 1 to 54, 0.00 to 2.25 s**
On screen: the full gold mossy fiber population, several hundred fibers, drifting. Nothing else visible. Deep near black background.
Change: fibers fade up from zero over the first 20 frames.
Camera: slow push along the fiber bundle, slight parallax, no cuts.
Caption: `Mossy fibers carry the dentate signal into CA3.`

### Beat 2. One fiber, one interneuron
**Frames 55 to 114, 2.25 to 4.75 s**
On screen: the field dims to about 12 percent opacity. Hero mossy fiber `648518346430566932` stays at full gold. The emerald interneuron `648518346437066458` fades up.
Change: six more gold fibers hold at partial brightness, the ones that also contact this interneuron.
Camera: settle toward the interneuron soma at approximately `[838924, 989815, 56640]` nm.
Caption: `Seven mossy fibers converge on one interneuron.`

### Beat 3. The first synapse
**Frames 115 to 168, 4.75 to 7.00 s**
On screen: same two cells, close.
Change: seven synapse markers flare in sequence at their real coordinates, the hero contact first at `[829314, 980190, 52065]` nm, 14.4 um from the soma. Emerald brightens as each lands.
Camera: tight, slight orbit around the contact zone.
Caption: `Only nine of twenty eight interneurons receive mossy fiber input at all.`

### Beat 4. Both subtypes arrive
**Frames 169 to 228, 7.00 to 9.50 s**
On screen: interneuron holds emerald. Camera pulls back.
Change: **both** pyramidal populations fade up together, 182 thorny in blue and 68 sparsely thorny in purple, all at equal muted brightness so neither is favoured yet. This is the beat that makes selectivity legible later, so both must be plainly present.
Camera: pull back and roll to a side on view so the superficial blue sheet and the deeper purple sheet separate vertically.
Caption: `Two pyramidal subtypes sit in two sublayers.`

### Beat 5. The axon spreads
**Frames 229 to 306, 9.50 to 12.75 s**
On screen: full three population field, interneuron centred.
Change: a signal travels out along the interneuron's real axonal cable. As it reaches each of the 333 verified contact sites, that thorny cell lights to full blue `#2E8BE0`. 87 cells light in total, staggered by their real path distance.
Camera: slow arc, holding the whole axonal territory in frame.
Caption: `Its axon makes 333 synapses onto 87 thorny cells.`

### Beat 6. The selectivity reveal
**Frames 307 to 384, 12.75 to 16.00 s**
On screen: 87 thorny cells now bright blue. The 68 sparsely thorny cells remain in the frame, unlit, dim purple.
Change: hold. Let the imbalance sit. Optionally pulse the 21 sparsely thorny cells that do receive contact, so the shot stays honest that the preference is strong and not absolute.
Camera: static or barely drifting. The stillness is the point.
Caption: `Only fifty synapses reach the sparsely thorny cells. Roughly two and a half times more inhibition lands on each thorny cell.`

### Beat 7. The motif
**Frames 385 to 432, 16.00 to 18.00 s**
On screen: pull back to the whole volume, gold fibers restored to partial brightness, the emerald interneuron and its blue targets still bright.
Change: the three node chain resolves into a clean schematic overlay, gold to emerald to blue, with the purple population sitting beside it untouched.
Camera: final wide, slow settle to rest.
Caption: `Mossy fiber, to perisomatic interneuron, to thorny cell. A feedforward inhibition circuit selective for one subtype.`

---

## Which script to extend

**Extend `hero_full.py`.** It is the right base for three reasons.

1. It already has the exact scope architecture this shot needs. `scope=cell|all|partners` is the same escalation the storyboard performs, one cell, then its partners, then the whole population. Beats 2, 5 and 7 map onto those three scopes almost directly.
2. It opens the 6.9 GB scene cache in about 6 seconds and drops native resolution hero geometry on top of the decimated population, hiding the decimated duplicate. That is precisely what is needed here, a native interneuron and 7 native mossy fibers over a decimated field of 250 pyramidal cells.
3. Its partner fade machinery already fades a named subset up in a separate colour over a held camera move. Beat 6 is that mechanism with the subset swapped for the 87 verified thorny targets.

`ap_six.py` is the wrong base despite handling signal propagation well. It is built around one hero pyramidal cell and six converging fibers with a two attempt firing narrative, it hardcodes `HERO_ID` and loads precomputed fields from `ap_fields6.npz`, and it has no population level scope control or pull back. It cannot reach beats 4 through 7.

**Borrow one thing from `ap_six.py`:** its along the cable signal travel, which beat 5 needs. Lift that routine and drive it from a new skeleton field file for interneuron `648518346437066458`, built the same way `ap_fields6.py` builds its own. Everything else should come from `hero_full.py`.

Suggested new scope value: `scope=inhibition`, added alongside the existing three, with a second partner cache holding the interneuron, its 7 mossy fibers and the 87 thorny targets at native resolution.
