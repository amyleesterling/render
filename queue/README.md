# Queue

The queue is its own repo and it stays that way:
**[github.com/amyleesterling/render-queue](https://github.com/amyleesterling/render-queue)**.

| file there | what |
|---|---|
| `RENDER_PROTOCOL.md` | the rule set. **Authoritative.** If this page and the protocol disagree, the protocol wins |
| `queue.ps1` | the only tool: `status`, `add`, `remove`, `run`, `resume`, `pause` |
| `render_queue.json` | the state, readable from any device |
| `behavior_cells/` | BANC behaviour cell list and a mesh downloader that needs no token |

## Why it was not moved into this repo

`queue.ps1` pulls before every write and commits and pushes `render_queue.json`
after, so the queue state lives in git history on purpose. Moving it here would
mix a state file that changes every night into a repo of code and notes, and it
would mean changing three things that work and that other sessions depend on:
the shim at `D:\Meshes\queue.ps1`, the clone at `C:\Users\amyle\render-queue`,
and the `MeshesRenderQueue` scheduled task. Pointing is cleaner.

## The one rule

> If you built an animation, add it to the queue and stop. Do not render it.

There is one GPU and several sessions. Rendering is the queue's job, at 02:00 on
Aurelius, when nothing else is competing for the card.

## The commands

On Aurelius `D:\Meshes\queue.ps1` is a four line shim that forwards to
`C:\Users\amyle\render-queue\queue.ps1`. On any other machine, clone render-queue
and run `.\queue.ps1` from the clone. A job added anywhere is picked up by
Aurelius.

```powershell
# what is queued, running, done, across every project, and whether the GPU is free
D:\Meshes\queue.ps1 status

# add a job
D:\Meshes\queue.ps1 add -Project banc -Name shotA_loop `
  -Script D:\Meshes\banc_shotA_anim.py `
  -Arguments "frames=576","res=1080x1920","samples=64","out=D:\Meshes\renders\banc_shotA.mp4" `
  -Minutes 90 -Note "beats verified as stills" -AddedBy "chat: shot A"

# take one back out
D:\Meshes\queue.ps1 remove -Id 3
```

`-Script` is a path on Aurelius. The runner calls
`blender --background --python <Script> -- <Arguments>` with Blender 4.4.

`queue.ps1 run` is what the scheduled task calls. Do not call it by hand unless
you mean to start rendering now.

## What the runner does

Quoted from the protocol:

- **Waits for a free GPU** before every job, up to four hours, then skips rather
  than fighting.
- **Moves any existing output aside** with a timestamp instead of overwriting it.
- **Web encodes** every mp4 on success, same treatment as the CA3 masters.
- **Logs everything** to `D:\Meshes\renders\queue_log.txt` with timestamps.
- **Writes status back** into `render_queue.json`, so `status` is always true:
  `queued` to `running` to `done` or `failed`.
- **Locks** while writing, so two sessions adding at the same moment cannot
  clobber each other.

When a job succeeds the runner also hands it to the review shelf
(`review.ps1 add -Job <id>`). See [../review/README.md](../review/README.md).

## Projects the queue knows

`ca3`, `banc`, `microns`, `retina`, in the `$Projects` table near the top of
`queue.ps1`. Adding a project means adding a row there and a row in the protocol.
Jobs for other project names have been queued (`brain`, `perch`); the tool warns
and accepts them.

## The nightly task

`MeshesRenderQueue`, daily at 02:00, ten hour limit, starts late if the machine
was asleep. Do not retime or edit it from a session unless Ames asks.
