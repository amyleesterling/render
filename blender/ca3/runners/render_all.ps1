# Render the two remaining animations back to back, then encode both for web.
$blender = "C:\Program Files\Blender Foundation\Blender 4.4\blender.exe"
$R = "D:\Meshes\renders"
$V = "C:\Users\amyle\ca3\video"
New-Item -ItemType Directory -Force -Path $V | Out-Null

Write-Output "=== 1/2 hero shot: 600 frames ==="
& $blender --background --python "D:\Meshes\hero_shot.py" -- `
    frames=600 res=1080x1920 samples=64 "out=$R\hero_shot.mp4" 2>&1 |
  Select-String -Pattern "^\[hero\] (aiming|rendered|DONE)"

Write-Output "=== 2/2 synapse story: 900 frames ==="
& $blender --background --python "D:\Meshes\synapse_story.py" -- `
    frames=900 res=1080x1920 samples=64 "out=$R\synapse_story.mp4" 2>&1 |
  Select-String -Pattern "^\[story\] (presynaptic|synapse cloud|rendered|DONE)"

Write-Output "=== encoding for web ==="
foreach ($j in @(
    @{ src = "$R\hero_shot.mp4";      out = "$V\hero_shot.mp4" },
    @{ src = "$R\synapse_story.mp4";  out = "$V\synapse_story.mp4" })) {
  if (Test-Path $j.src) {
    & ffmpeg -y -v error -i $j.src -vf "scale=720:-2" `
      -c:v libx264 -profile:v main -level 4.0 -pix_fmt yuv420p -crf 26 -preset slow `
      -movflags +faststart -an $j.out
    $mb = [math]::Round((Get-Item $j.out).Length / 1MB, 1)
    Write-Output ("encoded {0}  {1} MB" -f (Split-Path $j.out -Leaf), $mb)
  } else {
    Write-Output ("MISSING {0}" -f $j.src)
  }
}
Write-Output "=== ALL RENDERS DONE ==="
