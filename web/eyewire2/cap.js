// Frame capture for anim.html.
//   node cap.js probe 2 10 20 29.7 33 40 48     -> probe_<sec>.png
//   node cap.js full out.mp4                    -> h264 via ffmpeg on stdin (FROM=n, TO=n: a frame range)
//   node cap.js still random|players out.png    -> one 3840x2160 still
const { chromium } = require('/opt/node22/lib/node_modules/playwright');
const { spawn } = require('child_process');
const fs = require('fs');
const FF = process.env.FFMPEG || 'ffmpeg';
const URL = process.env.ANIM_URL || 'http://127.0.0.1:8765/anim.html';
const FPS = 30;
// ALPHA=1 captures with a transparent background (for ?layer=overlay) into a PNG-in-MOV
// that keeps the alpha channel, for compose.py to lay over the plate
const ALPHA = !!process.env.ALPHA;
const shot = (page, opts = {}) => page.screenshot({ type: 'png', omitBackground: ALPHA, ...opts });

(async () => {
  const browser = await chromium.launch({ headless: true, args: [
    '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist',
    '--disable-gpu-vsync', '--enable-webgl', '--font-render-hinting=none', '--hide-scrollbars'] });
  const mode = process.argv[2] || 'probe';
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: mode === 'still' ? 2 : 1 });
  page.setDefaultTimeout(15 * 60 * 1000);   // a thousand meshes take a while to load and parse
  page.on('console', m => console.error('[page]', m.text()));
  page.on('pageerror', e => console.error('[pageerror]', e.message));
  await page.goto(mode === 'still' ? `${URL}?still=${process.argv[3]}` : URL, { waitUntil: 'networkidle' });
  await page.waitForFunction(() => window.READY === true, null, { timeout: 60000 });
  const total = await page.evaluate(() => window.TOTAL_FRAMES);
  if (mode === 'still') {
    await page.evaluate(() => window.setStill());
    await page.screenshot({ path: process.argv[4] || `still_${process.argv[3]}.png`, type: 'png' });
    console.log('still', process.argv[3]);
  } else if (mode === 'probe') {
    for (const s of process.argv.slice(3)) {
      const f = Math.round(parseFloat(s) * FPS);
      await page.evaluate(f => window.setFrame(f), f);
      await shot(page, { path: `probe_${s}.png` });
      console.log('probe', s, 'frame', f, 'of', total);
    }
  } else {
    const out = process.argv[3] || 'out.mp4';
    const ff = spawn(FF, ['-y', '-hide_banner', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', String(FPS), '-c:v', 'png', '-i', '-',
      ...(ALPHA ? ['-c:v', 'png', '-pix_fmt', 'rgba'] : ['-c:v', 'libx264', '-preset', 'slow', '-crf', '17', '-pix_fmt', 'yuv420p', '-movflags', '+faststart']),
      '-r', String(FPS), out], { stdio: ['pipe', 'inherit', 'inherit'] });
    const t0 = Date.now();
    // FROM=n starts at frame n, for re-rendering the tail of a film and splicing it on
    const from = Math.max(0, parseInt(process.env.FROM || '0', 10));
    const to = Math.min(total, parseInt(process.env.TO || String(total), 10));   // TO=n stops before frame n
    for (let f = from; f < to; f++) {
      await page.evaluate(f => window.setFrame(f), f);
      const buf = await shot(page);
      if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once('drain', r));
      if (f % 150 === 0) console.log(`frame ${f}/${total}  ${((Date.now()-t0)/1000).toFixed(0)}s`);
    }
    ff.stdin.end();
    await new Promise(r => ff.on('close', r));
    console.log('wrote', out, 'frames', total, 'in', ((Date.now()-t0)/1000).toFixed(0), 's');
  }
  await browser.close();
})().catch(e => { console.error(e); process.exit(1); });
