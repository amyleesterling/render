# Research brief: which neurons drive which behaviours, for "BANC Be the Fly"

**For a literature-research session. You do not need database access.**
Your job is to produce well-cited, precisely-named candidates. A separate rendering
pipeline resolves those names against the BANC connectome and builds the assets.

Live prototype: https://amyleesterling.github.io/banc-explorer/
Paper: Bates, Phelps, Kim et al., "Distributed control circuits across a
brain-and-cord connectome", *Nature* (2026), doi:10.1038/s41586-026-10735-w

---

## 1. What the thing is

"Be the Fly" is a browser game driven by the BANC connectome, the first fly
connectome covering brain **and** ventral nerve cord together. The player moves a
fly with WASD through a foraging course and a flight course: find the fermenting
fruit, escape a spider, steer to a flower.

Alongside the game sits a neural HUD: a fixed 1600x1200 view of the whole central
nervous system, brain at top, neck connective in the middle, nerve cord below.
Every neuron sits in a dim gray context layer. When the player does something, the
cells for that behaviour light up in colour, in register, on the same camera.

The site's own standard is printed on it: *"Structure suggests pathways; it does
not record neural activity."* Keep every claim inside that line.

### Already built, do not re-research

| behaviour | cells |
|---|---|
| forward walk | DNg100 pair, AN09B029_b pair, AN02A002 pair |
| steering left / right | DNa01 and DNa02, per hemisphere |
| backward walk | MDN |
| feeding | DNg70, DNp44, DNp62 |
| escape on foot | DNp42, DNg55, DNge053 |
| flight saccade | DNp03 |
| heading | EPG compass population |
| grooming | DNg12 (blocked on count), wPN1 (blocked on identity) |

---

## 2. What "easy to show" actually means

A behaviour earns a place only if it clears all five. Please score every candidate
against these explicitly.

1. **Player-triggerable.** It maps to a key press or a game event (collision,
   scent gradient, predator approach), not to an internal state with no input.
2. **Legible at whole-CNS scale.** The cells must occupy a *distinguishable*
   region of a single frontal view. Something confined to one small neuropil reads
   as a dot. Something spanning brain to leg neuropil reads instantly. Say where
   in the CNS the arbors sit.
3. **Small, nameable population.** Roughly **1 to 30 cells**. A single bilateral
   pair is ideal. Above ~40 the layer turns into a smear and stops being about
   identified neurons.
4. **Visually distinct from what is built.** If it overlaps the descending
   steering set in both anatomy and colour, it adds nothing. Note which existing
   layer it would sit closest to.
5. **Causal evidence, not correlation.** Optogenetic or thermogenetic activation,
   silencing, or ablation. Say which. Calcium imaging alone is correlational and
   should be labelled as such.

**Bonus, and worth a lot:** behaviours that show off *why BANC exists*. The
strongest pairings contrast a **descending brain-to-cord** command with a **local
nerve-cord circuit** for a related act. That contrast is the whole argument for a
combined brain-and-cord connectome, and no brain-only or cord-only dataset can
make it.

---

## 3. The constraint that has actually blocked us: nomenclature

This is the most valuable part of your output. Two real failures:

- **wPN1.** Named in the wing-grooming literature. We pulled all 380,392 rows of
  BANC's `cell_info` and scanned all 11,029 distinct type labels. **Zero** contain
  "wpn" in any casing. The identity could not be resolved and the job stopped.
- **DNg70.** Supplied as a specific pair of IDs. BANC's annotations put the
  `DNg70` label on two *different* cells, and tagged one of the supplied cells
  `DNxn180` instead. Unresolved, and flagged rather than rendered.

Cell types are named differently across datasets, and a name that is standard in
one paper may not exist in BANC at all. So for **every** candidate, give the name
in **as many of these as you can find**, and say which paper establishes each:

- **BANC** (brain + nerve cord; the target)
- **FlyWire / FAFB** (brain)
- **hemibrain** (brain)
- **MANC** (male adult nerve cord)
- **FANC** (female adult nerve cord)
- **Provisional or functional names** (e.g. "AX", "DNxn###", hemilineage labels
  like 13B, or split-GAL4 line names)

If a type only has a functional or split-GAL4 name and no connectome-dataset name,
**say so explicitly**. That is a useful finding, not a failure, and it tells us the
identity will need a morphology crosswalk that someone has to sanction.

---

## 4. Deliverable, per candidate

One dossier each. Be terse; precision beats prose.

```
BEHAVIOUR:            e.g. "proboscis extension while feeding"
GAME TRIGGER:         which key press or event
CELL TYPE:            canonical name
NAMES BY DATASET:     BANC / FlyWire / hemibrain / MANC / FANC / provisional
EXPECTED COUNT:       how many cells, and per hemisphere
LATERALITY:           bilateral pair, unilateral, or unpaired midline
CNS SPAN:             brain only / descending / local VNC / ascending
ARBOR LOCATIONS:      input neuropil(s) and output neuropil(s), named
POLARITY:             where inputs are, where outputs are
EVIDENCE GRADE:       activation / silencing / ablation / imaging / anatomy only
KEY CITATIONS:        DOI or PMC, with one line on what each shows
CAUSAL CLAIM:         the strongest sentence the literature supports, verbatim-safe
DO NOT CLAIM:         the tempting overstatement to avoid
LEGIBILITY:           why it will or will not read at whole-CNS scale
SCORE:                the five criteria in section 2, pass/fail each
```

---

## 5. Where to look first

Seeds, not limits. Suggest better ones if you find them.

**Locomotion and posture:** stopping and freezing, turning gain, walking speed
control, landing, takeoff (note: takeoff giant-fibre cells are deliberately held
back for a flight layer).

**Flight:** wing steering muscles and their motor neurons, haltere feedback,
flight initiation and cessation, course correction.

**Feeding:** proboscis extension, sugar versus bitter decision, ingestion,
pharyngeal pumping.

**Grooming:** the anterior versus posterior grooming hierarchy is a strong target
because it is a *sequence*, which animates well. Antennal, eye, head, wing,
abdominal, hind-leg grooming.

**Escape and defence:** looming responses split by whether they end in a jump, a
walk, or a flight saccade. Also freezing versus fleeing.

**Courtship and song:** P1 and pIP10 are famously well characterised and highly
legible; song is a strong candidate if a game context exists for it.

**Navigation:** the central complex beyond the EPG compass, including PFL neurons
for goal-directed steering, which would pair beautifully with the heading layer
already built.

**Sensory to motor, whole-loop:** anything where a named sensory afferent, a named
ascending neuron, and a named motor neuron can all be shown together. Those make
the best BANC demonstrations.

---

## 6. Standards

- **Never label a response circuit a detector.** Cells that produce an escape are
  not the visual detection circuit. We use "threat response", never "threat
  detection". Apply the same care everywhere.
- **Anatomical side is not behavioural direction.** Say "anatomical left" unless a
  paper explicitly establishes which way the animal turns. Direction mapping stays
  "pending" until someone validates it.
- **Separate what is measured from what is inferred.** If conduction direction is
  inferred from synapse polarity rather than recorded, say so.
- **Flag disputes.** If two papers disagree on identity or function, give both.
  A flagged conflict is far more useful than a confident wrong answer.
- **No made-up IDs.** Do not invent or guess numeric segment IDs. Names and
  citations only. Resolution happens against the live database, by us.

---

## 7. Output

1. A ranked table of every candidate: behaviour, cell type, count, CNS span,
   evidence grade, and the five-criteria score.
2. Full dossiers for the top ~10.
3. A short list of "named in the literature but possibly absent from BANC
   annotations", so we know in advance which ones will need a crosswalk decision.
4. Anything you found that contradicts the already-built list above. We would
   rather fix a shipped layer than defend it.

## 8. Not in scope

Do not design game mechanics, write app code, propose colours or visual style, or
estimate render effort. Neuron identity, behavioural evidence, and naming only.
