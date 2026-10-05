# Where this all lives

Written 30 July 2026, answering "one repo per dataset?"

## The one distinction that matters

**Publishing and production are different problems and want opposite shapes.**

- **Publishing** is per dataset. Each reconstruction is its own story with its own
  citation, its own palette and its own audience. Splitting is right.
- **Production** is per *machine*. There is one GPU, one scene cache convention,
  one playbook, one set of measured machine limits. Splitting would fork the
  playbook and, worse, fork the render queue, and a forked queue is how two
  Blenders end up fighting over 63.7 GB. That has now happened twice, on 29 and
  30 July, and cost a whole overnight run.

So: **many site repos, one production directory, one queue.**

## Production, singular

`D:\Meshes\` stays the single production root. Per dataset subfolders:

```
D:\Meshes\
  ca3_scene.blend            hippocampus, the 6.9 GB cache
  banc\                      Drosophila brain and nerve cord
    shotA\  shotB\  cache\   meshes and cached CAVE queries
  renders\                   everything rendered, all datasets
  render_queue.json          THE queue. Any agent appends a job here.
  run_queue.ps1              the runner. Waits for a free GPU, logs, encodes.
  RENDERING_NEURONS.md       the playbook, dataset agnostic
```

**The queue is the coordination point Amy asked for.** An agent that has built an
animation does not render it. It appends a job to `render_queue.json` and stops.
A scheduled task runs `queue.ps1 run` at 02:00, which takes jobs in order, waits
for the GPU before each, logs to `renders\queue_log.txt`, moves any existing
output aside rather than overwriting, and web encodes each mp4 on completion.

Scheduled task name: `MeshesRenderQueue`. Change the time with Task Scheduler or
`Set-ScheduledTask`.

Still to add when a second agent starts using it: a lock file, so two runners
cannot start the same queue. Today there is one runner on a timer, so it cannot
collide with itself, but it can collide with an agent rendering by hand. The
runner already waits rather than fighting.

## Publishing, plural

Today: `amyleesterling.github.io/ca3/` and `/ca3/cortex.html`. The second is the
problem. **cortex.html is MICrONS content living inside the hippocampus repo**,
so the URL says CA3 for a page that is not about CA3.

Recommended:

| dataset | repo | URL |
|---|---|---|
| hippocampal CA3 | `ca3` (exists) | `/ca3/` |
| Drosophila BANC | `banc` (new) | `/banc/` |
| MICrONS cortex | `microns` (new) | `/microns/` |

Keep `ca3` exactly where it is. Its URL is public and may already be shared, so
moving it breaks links for no benefit. Move `cortex.html` into the new `microns`
repo and leave a redirecting stub at the old path so nothing 404s.

**Why not one umbrella monorepo**, which is the other honest option and is the
pattern whatisabrain.com already uses: it would give shared CSS and one deploy,
but it would move the live `/ca3/` URL. Separate repos keep deploys independent,
which matters when two agents are working at once, and the shared look can travel
as a copied stylesheet rather than a build dependency.

**The cost of separate repos is design drift.** The hologram panel, the black
ground, the holoframe hover treatment and the type scale are already shared and
will diverge. Mitigation: lift the common CSS into `scifi-ui`, which already
exists at `C:\Users\amyle\scifi-ui` with `hologram.css` and `hologram.js` and is
not yet pushed, and copy it into each site rather than reimplementing it.

## What is already true

- `render_queue.json` and `run_queue.ps1` exist and the nightly task is
  registered.
- BANC production lives at `D:\Meshes\banc\` with both casts downloaded, 930
  meshes and 361M faces total.
- No `banc` or `microns` site repo exists yet. Nothing is published for either.
