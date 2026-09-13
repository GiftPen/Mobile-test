#!/usr/bin/env python3
"""The menu's drifting fruit must move at the same speed on any display.

It was paced by the FRAME: twice as fast on a 120Hz panel, and lurching whenever the refresh
rate changed -- which is what a phone does when it drops back to 60Hz after a game, and is
what the player saw as "it speeds up for a second when I come back to the menu".

rAF does not fire under virtual time, so it is replaced with a timer the test controls. That
is the point: the same wall-clock second is run at two different frame rates and the fruit
has to end up in the same place."""
import subprocess, os, re, json, sys

SHIM = """<script>
(() => {
  // rAF, but at a frame interval the test picks. Same contract.
  let next = 1; const live = new Map();
  window.__hz = 16.7;
  window.requestAnimationFrame = cb => {
    const id = next++;
    const t = setTimeout(() => { live.delete(id); cb(performance.now()); }, window.__hz);
    live.set(id, t);
    return id;
  };
  window.cancelAnimationFrame = id => { const t = live.get(id); if (t) { clearTimeout(t); live.delete(id); } };
})();
</script>"""

TEST = """<script>
const sleep = ms => new Promise(r => setTimeout(r, ms));
window.addEventListener('load', () => setTimeout(async () => {
 try {
  const F = window.__fs, fails = [];
  const chk = (c, got, want) => { if (JSON.stringify(got) !== JSON.stringify(want))
                                    fails.push({case: c, got, want}); };

  // one fruit, no wrapping, no popping: pure distance over time
  const travel = async (hz, ms) => {
    F.mfxStop();
    window.__hz = hz;
    F.mfxStart();
    await sleep(30);
    const fr = F.mfxFruits;
    fr.length = 1;
    const f = fr[0];
    f.x = 200; f.y = 200; f.vx = 1; f.vy = 0; f.vr = 0; f.age = 0; f.life = 1e9; f.size = 20;
    await sleep(ms);
    const d = f.x - 200;
    F.mfxStop();
    return d;
  };
  const slow = await travel(16.7, 1000);     // ~60Hz
  const fast = await travel(8.3, 1000);      // ~120Hz
  chk('the fruit drifts at all', slow > 20, true);
  chk('a 120Hz display does not double the speed',
      Math.abs(fast / slow - 1) < 0.15, true);

  // and a long gap must not fling everything across the screen at once
  F.mfxStop(); window.__hz = 16.7; F.mfxStart();
  await sleep(30);
  F.mfxFruits.length = 1;
  const g = F.mfxFruits[0];
  g.x = 200; g.y = 200; g.vx = 1; g.vy = 0; g.vr = 0; g.age = 0; g.life = 1e9; g.size = 20;
  F.mfxFrame(performance.now());                 // establish the clock
  const before = g.x;
  F.mfxFrame(performance.now() + 5000);          // five seconds in one frame
  chk('a long gap is capped, not replayed', g.x - before <= F.MFX_MAX_K + 0.01, true);
  chk('but it still advances', g.x - before > 0, true);
  F.mfxStop();

  // Resuming must not count the time the menu was hidden as one enormous frame. Measured on
  // the FIRST frame after resuming, because the catch-up cap would otherwise hide it: a
  // resumed clock costs the full cap, a reset one costs a single frame.
  F.mfxStart(); await sleep(30);
  F.mfxFruits.length = 1;
  const h = F.mfxFruits[0];
  h.x = 200; h.vx = 1; h.vy = 0; h.vr = 0; h.age = 0; h.life = 1e9; h.size = 20;
  F.mfxStop();
  await sleep(900);                              // "in a game" for a while
  F.mfxStart();                                  // schedules, but has not stepped yet
  h.x = 200;
  F.mfxFrame(performance.now());                 // the first frame back
  const jump = h.x - 200;
  chk('the first frame back is one frame, not the whole absence', jump < 1.6, true);
  chk('and it does step', jump > 0.4, true);
  F.mfxStop();

  // and only one loop may ever be running: two is what "twice as fast" actually looks like
  F.mfxStop();
  F.mfxStart(); F.mfxStart(); F.mfxStart();
  await sleep(30);
  F.mfxFruits.length = 1;
  const q = F.mfxFruits[0];
  q.x = 200; q.vx = 1; q.vy = 0; q.vr = 0; q.age = 0; q.life = 1e9; q.size = 20;
  await sleep(500);
  const many = q.x - 200;
  F.mfxStop();
  await sleep(200);
  // Duplicate loops cannot speed the drift up once it is clock-paced -- the second call in a
  // frame sees no elapsed time. This pins that: the old frame-paced code would have tripled.
  chk('three loops do not make it three times as fast', Math.abs(many - 30) < 9, true);
  chk('and stopping once really stops it', F.mfxOn, false);
  const parked = q.x;
  await sleep(300);
  chk('nothing moves while stopped', q.x, parked);

  document.title = 'RESULT ' + JSON.stringify({ fails, slow: +slow.toFixed(1), fast: +fast.toFixed(1), jump: +jump.toFixed(1), many: +many.toFixed(1) });
 } catch (e) { document.title = 'THREW ' + e.message + ' | ' + (e.stack || '').slice(0, 160); }
}, 800));
</script>"""

os.chdir(os.path.dirname(os.path.abspath(__file__)) + '/..')
src = open('index.html', encoding='utf-8').read()
open('_mfx.html','w',encoding='utf-8').write(
    src.replace('<head>', '<head>' + SHIM, 1).replace('</body>', TEST + '</body>'))
try:
    out = subprocess.run(['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
        '--headless','--disable-gpu','--no-first-run','--window-size=430,932',
        '--virtual-time-budget=40000','--dump-dom','http://localhost:8899/_mfx.html?test=1'],
        capture_output=True, text=True, timeout=180).stdout
finally:
    os.remove('_mfx.html')

m = re.search(r'RESULT (\{.*\})</title>', out, re.S)
if not m:
    t = re.search(r'<title>(.*?)</title>', out, re.S)
    print('NO RESULT', t.group(1)[:250] if t else ''); sys.exit(1)
r = json.loads(m.group(1))
print(f"menufx: 1초 이동 60Hz {r['slow']}px · 120Hz {r['fast']}px · 복귀 점프 {r['jump']}px · {len(r['fails'])} fail")
for f in r['fails']: print('  ', json.dumps(f, ensure_ascii=False)[:200])
print('PASS' if not r['fails'] else 'FAIL')
sys.exit(0 if not r['fails'] else 1)
