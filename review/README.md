# Review

The approval shelf is its own repo:
**[github.com/amyleesterling/review](https://github.com/amyleesterling/review)**,
cloned on Aurelius at `C:\Users\amyle\review`.

A finished render is not a wanted render. The queue puts each finished job on the
shelf, Ames watches it, and only an approved render is copied into a site repo.

```powershell
.\review.ps1 status
.\review.ps1 add     -Job 12                       # a finished queue job (the runner does this itself)
.\review.ps1 add     -File D:\Meshes\renders\shot.mp4 -Project retina -Name mosaic
                                                   # a render made outside the queue
.\review.ps1 approve -Id 1
.\review.ps1 reject  -Id 1 -Note "too fast through the neck"
.\review.ps1 publish -Id 1
.\review.ps1 page                                  # regenerate index.html
```

- The shelf holds the small web encode and a poster, not the master, because it
  is watched on a phone.
- Approval is conversational. Ames looks at the page and tells a session
  "approve the BANC one". Do not approve on your own judgement.
- `publish` copies the video and poster into the project's site repo and prints
  the markup to paste. It does not write page copy and it does not commit. Where
  a render goes and what it is captioned are editorial decisions.
- After `publish`, the site repo still has to be committed, pushed and checked
  from the live URL. A push is not a deploy.
