# BANC animation ideas

Written 30 July 2026, from the preprint rather than from memory.

## The paper

**Distributed control circuits across a brain-and-cord connectome.**
Bates, Phelps, Kim, Yang, Matsliah, Ajabi, Perlman, ... **Amy R. Sterling** ...
Seung, de Bivort, Murthy, Drugowitsch, Wilson, Lee.
*Nature* (2026), doi:10.1038/s41586-026-10735-w
Preprint: bioRxiv 2 August 2025, doi:10.1101/2025.07.31.667571

Amy is an author, as on the CA3 paper. Data is public at flywire.ai and in Codex.

The first adult fly connectome uniting brain and ventral nerve cord: about
**188,000 neurons** and **199 million predicted synapses** across the brain,
suboesophageal zone, cervical connective and the whole VNC, from one adult female
*Drosophila*.

### What it actually claims, in the abstract's own terms

1. **Effector cells** (motor neurons, endocrine cells, efferent neurons targeting
   the viscera) are primarily influenced by **local sensory cells in the same body
   part**, forming **local feedback loops**.
2. Those local loops are **linked by long range circuits** of **ascending and
   descending neurons** organised into **behaviour centric modules**.
3. **Single ascending or descending neurons** are often positioned to influence
   the voluntary movements of **multiple body parts**, together with the endocrine
   cells or visceral organs that support those movements.
4. Brain regions for **learning and navigation supervise** these circuits.
5. The architecture is **distributed, parallelised and embodied**, likened to
   distributed control architectures in engineering.

The framing beat: the only other species with complete connectomes are worms and
sea squirts, at 10^3 to 10^4 synapses. The fly is at 10^8.

---

## Ideas, strongest first

### 1. The neck, as a bottleneck
The single most BANC-specific shot, and impossible in FlyWire or MANC alone,
because neither dataset crosses the neck.

Open on the whole CNS. Dissolve everything except the neurons that pass through
the **cervical connective**, then push the camera slowly through it. Ascending
one colour, descending another, held long enough to count. The whole point of
this dataset is that these two halves were previously separate volumes, so the
shot is the thesis: here is every wire between brain and body, and here is how
few of them there are relative to 188,000 cells.

Ends on the reveal that this narrow bundle is the entire conversation.

### 2. Local loop, then the long range link
Animates claim 1 and 2 directly, which is the paper's core.

Pick one body part, a front leg. Light the **sensory** neurons from that leg, then
the **motor** neurons of the same neuromere, then the local interneurons that
close the loop between them. Hold. The viewer sees a complete controller that
never leaves the segment.

Then widen: the other legs light as their own separate loops, structurally
identical, not talking to each other. Only then do the ascending and descending
neurons arrive and stitch them together. The order is the argument.

### 3. One descending neuron, many body parts
Claim 3, and the most emotionally legible of the set.

Follow a single DN from its soma in the brain, down through the connective, and
light every effector it reaches as the camera travels: leg motor neurons, wing,
and the endocrine or visceral target that supports the same movement. One cell,
several body segments, plus the glands that back them up. Slow, one arrival at a
time, in the pacing of the CA3 six fibre cut.

### 4. Colour the nervous system by module, not by anatomy
Claim 2's modules. A slow rotation of the whole CNS where colour encodes
**behaviour centric module membership** rather than region. Satisfies the
playbook's rule that a ramp has to carry a measurement, and it produces an image
nobody has seen: a fly nervous system partitioned by what it does rather than
where it is.

### 5. The supervisory layer
Claim 4. Start tight on the **central complex** and **mushroom body**, the
learning and navigation structures, then follow their outputs downward and outward
until the modules below light up underneath them. Establishes hierarchy without a
diagram.

### 6. Three connectomes, one scale bar
Outreach rather than figure. *C. elegans* at 302 neurons, then the CA3 block, then
the BANC at 188,000, at true relative scale in one continuous zoom. Reuses the
scale ladder camera work already built for CA3. This is the shot that travels
furthest outside the field.

### 7. A spike that takes the long way
Reuses the CA3 machinery directly: every mesh vertex already can carry its own
path distance along the skeleton, so a wavefront follows real branching. Send one
from a leg sensory ending, up the connective, into the brain, with delay
proportional to **measured cable length**.

**Caveat that must go in the caption:** as with CA3, this paper contains no
physiology. Conduction velocity would come from the literature, not from this
dataset. Show path length honestly and do not imply measured timing.

### 8. Embodied
The abstract's own word. Place the CNS inside a fly body outline at true scale and
position, so the tightness of the coupling between effectors and the periphery is
visible rather than asserted.

---

## CAST, selected from the data on 30 July 2026

Datastack `brain_and_nerve_cord`, **materialization 896**. Amy has access to the
full stack, 42 tables. A public mirror `brain_and_nerve_cord_public` has 17.
Selection scripts wrote `D:\Meshes\banc\cast.json`, `descending_ranked.csv`,
`dn_targets.json`, `dn_endocrine.json`.

### Shot A, the local loop

**The front leg is not a preference, it is the only option**: sensory axons are
annotated for T1 only.

| | left T1 | right T1 |
|---|---|---|
| mechanosensory axons | **654** | 624 |
| campaniform sensilla | **34** | 17 |
| leg motor neurons | 69 | 70 |
| behaviour modules among them | 13 | 14 |

Go with **left T1**: 688 sensory in, 69 motor out, 13 modules.

Tables: `leg_mechanosensory_axons` and `legcs_axons` for the sensory side,
`leg_mn_cell_type_table_v0` for motor, `leg_mn_neuropil_reftable_v2` for the
neuromere (tags read `left_t1`, `right_t2` and so on), and
`leg_mn_module_reftable_v0` for the behaviour module. **Colour the motor neurons
by module**, since that is the paper's own grouping and it satisfies the rule that
a ramp must carry a measurement.

Note: `leg_mn_segment_reftable_v0` tags the **leg** segment a muscle originates
from, coxa and femur and tibia. It is not the body neuromere. Use the neuropil
table for T1 versus T2 versus T3.

### Shot B, one descending neuron

Definition used, entirely from the data: a neuron that **crosses the neck
connective** and has its **soma in the brain**. That gives **1,266 descending
candidates** out of 3,832 neck crossers and 132,406 brain somas.

There is a genuine choice, and it is an editorial one.

**Option 1, `720575941535975873`.** The biggest reach: 6,522 synapses onto 131
motor neurons. Its targets report innervating **T1 leg (41), T2 leg (32), T3 leg
(40), neck (8), wing (3), haltere (1), abdomen (1)**, so six body parts. And it is
almost perfectly lateralised, **123 targets on the left against 2 on the right**,
which is a striking honest detail. **It reaches no endocrine cell**, so the
storyboard's endocrine beat is impossible with it.

**Option 2, `720575941662506040`.** Smaller but complete: **34 motor neurons
across leg, neck and wing, plus 15 endocrine cells**. This is the paper's sentence
rendered literally, movement of several body parts together with the endocrine
cells that support those movements.

Only **74 of the 1,266 descending neurons touch an endocrine cell at all**, and
only **nine** of those also reach all three motor classes. That scarcity is itself
worth a caption.

**Recommendation: Option 2 for the storyboarded shot**, because Amy's chosen beat
list ends on the visceral or endocrine target and Option 2 is the only kind of
neuron that can deliver it. Option 1 is a strong second shot on its own terms,
the laterality being the hook.

## Practical notes

- **Scale is the blocker.** 188,000 neurons is far beyond the RTX 3090. The CA3
  measurement of 8,858 faces per MB of OBJ puts a 30,000 to 50,000 cell subset at
  roughly 150 GB and 1.3 billion faces, which is the figure already in the Della
  proposal. Every idea above should be built on a **named subset**, not the whole
  volume.
- Ideas 1, 2, 3 and 5 are all naturally subsets, which is why they are ranked
  first. Idea 4 wants the whole thing and is the one that genuinely needs cluster
  scale.
- The pipeline transfers unchanged: CAVE for meshes and synapses, meshparty for
  skeletons, Blender EEVEE for the look. BANC is a CAVE datastack like `zheng_ca3`.
- Keep the house rules: submerged not glossy, IOR 1.04, pure black, fade in rather
  than scale up from a point, long holds.
- **Say the subset size in every caption.** The CA3 corrections list is mostly
  captions that implied more cells than were on screen.
