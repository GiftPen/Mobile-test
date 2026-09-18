#!/usr/bin/env python3
"""Frame-rate independence: the same wall-clock span must produce the same animation state
whether the phone runs at 60Hz or 120Hz.

Every effect constant in draw() was tuned by eye on a 60Hz screen and applied once per frame,
so on a 120Hz device the explosion, the pop-in and the screen shake all ran at double speed.
draw() now scales them by k = elapsed / (1000/60).

The test drives draw() with explicit timestamps -- 16.67ms steps against 8.33ms steps over
the same 200ms -- and compares what is left. The span is deliberately short: over a full
second every decay reaches zero at BOTH rates, so comparing them there passes no matter what
the code does. At 200ms nothing has saturated and a doubled rate is unmissable.

Nothing here hardcodes an effect constant: it reads the state the game itself produced."""
import subprocess, os, re, json, sys

TEST = """<script>
window.addEventListener('load', () => setTimeout(() => {
 try {
  const F = window.__fs; const fails = [];
  const near = (c, a, b, tol) => { const d = Math.abs(a - b);
    if (!(d <= tol)) fails.push({ case: c, hz60: a, hz120: b, diff: +d.toFixed(6), tol }); };

  // Frame COUNTS, not a time bound. `for (t = step; t <= SPAN; t += step)` accumulates
  // floating-point error, and the 120Hz loop quietly ran 23 steps instead of 24 -- the two
  // runs then covered different spans and disagreed for a reason that had nothing to do with
  // the code under test. Multiplying the index keeps both ending on exactly the same ms.
  // Short span, and it has to get shorter as FX_SPEED rises: at 2x over 200ms the decays
  // reach zero at BOTH rates and every comparison passes for free. The guard below measures
  // that rather than trusting this number.
  const STEP60 = 1000 / 60, STEP120 = 1000 / 120, N60 = 4, N120 = 8;

  // A fixed,randomness-free scene: values chosen here, not rolled, so the two runs differ only in
  // how the clock was sliced.
  function seed() {
    F.start('rush');
    F.shake = 20; F.flash = 0.9; F.frame = 0;
    F.particles.length = 0; F.waves.length = 0; F.flares.length = 0; F.floats.length = 0;
    F.particles.push({ type: 'ring', x: 100, y: 100, rad: 4, life: 1, color: '#fff' });
    F.particles.push({ x: 100, y: 100, vx: 2, vy: -3, r: 3, life: 1, color: '#fff' });
    F.waves.push({ x: 100, y: 100, t: 0, color: '#fff' });
    F.flares.push({ x: 100, y: 100, t: 0, color: '#fff' });
    F.floats.push({ x: 100, y: 100, t: 0, txt: '+1', color: '#fff' });
    for (let r = 0; r < F.ROWS; r++) for (let c = 0; c < F.COLS; c++) F.appear[r][c] = 0;
    F.appear[0][0] = 1;
    F.glow[0][1] = { c: 0, t: 1 };
    F.dirty = true;
  }
  // prime with one frame (k = 1 on the first call either way), then step the span
  function run(step, n) {
    seed();
    F.resetFrameClock();
    F.draw(0);
    for (let i = 1; i <= n; i++) F.draw(i * step);
    const steps = n;
    const ring = F.particles.find(p => p.type === 'ring');
    const dot  = F.particles.find(p => p.type !== 'ring');
    return { steps, shake: F.shake, flash: F.flash, frame: F.frame,
             appear: F.appear[0][0],
             glowT: F.glow[0][1] ? F.glow[0][1].t : null,
             ringLife: ring ? ring.life : null, ringRad: ring ? ring.rad : null,
             dotLife: dot ? dot.life : null, dotX: dot ? dot.x : null, dotY: dot ? dot.y : null,
             waveT: F.waves.length ? F.waves[0].t : null,
             flareT: F.flares.length ? F.flares[0].t : null,
             floatT: F.floats.length ? F.floats[0].t : null };
  }

  const a = run(STEP60, N60), b = run(STEP120, N120);
  // the two runs must cover the same wall-clock span, or nothing below means anything
  if (Math.abs(N60 * STEP60 - N120 * STEP120) > 1e-9)
    fails.push({ case: 'the two runs must span the same time',
                 hz60: N60 * STEP60, hz120: N120 * STEP120 });

  // the clock itself
  near('frame clock', a.frame, b.frame, 1e-9);

  // linear channels: these should land within a fraction of one 60Hz frame of each other
  // Tolerances are a fraction of ONE 60Hz step of each channel, not a round number: 'appear'
  // decays 0.071 per frame and saturates at 0, so a tolerance of 0.08 quietly swallowed a
  // completely unscaled channel (measured: it missed by 0.077, just under the bar).
  for (const [key, tol] of [['appear', 1e-9], ['waveT', 1e-9], ['flareT', 1e-9],
                            ['floatT', 1e-9], ['glowT', 1e-9]]) {
    if (a[key] === null && b[key] === null) continue;     // both expired: still agreement
    near(key, a[key], b[key], tol);
  }

  // exponential decays -- compared loosely, because a rate error shows up as orders of
  // magnitude, not as a third decimal place
  near('shake decay', a.shake, b.shake, 1e-9);
  near('flash decay', a.flash, b.flash, 1e-9);

  // particles either both survived the span or both expired
  const aliveA = [a.ringLife !== null, a.dotLife !== null];
  const aliveB = [b.ringLife !== null, b.dotLife !== null];
  if (JSON.stringify(aliveA) !== JSON.stringify(aliveB))
    fails.push({ case: 'particles expire together', hz60: aliveA, hz120: aliveB });
  if (a.dotX !== null && b.dotX !== null) {
    // Sub-pixel, not exact: a particle under gravity is integrated with explicit Euler
    // (v += g*k; p += v*k), which CONVERGES as the step shrinks rather than matching it. A
    // finer step is slightly more accurate by nature. Half a pixel over 200ms is invisible;
    // an unscaled channel misses this by 9-18px, so the bar still catches the real fault.
    near('particle x', a.dotX, b.dotX, 0.5);
    near('particle y', a.dotY, b.dotY, 0.5);
  }

  // ---- keep the test from being vacuous. If both runs stepped the same number of times
  // they are the same run, and every comparison above matches for free. The 120Hz pass must
  // really have drawn about twice as many frames.
  if (!(b.steps >= a.steps * 1.8))
    fails.push({ case: 'the two runs must differ in frame count', hz60: a.steps, hz120: b.steps });
  // ...and the channels must not all have decayed to nothing, which also matches for free.
  if (!(a.shake > 0.5 && a.flash > 0.02 && a.waveT > 0.05 && a.appear > 0.05 && a.glowT > 0.05))
    fails.push({ case: 'span too long: channels saturated before being compared',
                 hz60: { shake: a.shake, flash: a.flash, waveT: a.waveT,
                         appear: a.appear, glowT: a.glowT } });

  // FX_SPEED rebases the whole suite to the speed the game was actually judged at (120Hz).
  // It must scale the effects, not be a dead constant -- and it must not break the frame-rate
  // independence this file exists to prove.
  if (!(F.FX_SPEED > 0))
    fails.push({ case: 'FX_SPEED must be a positive multiplier', hz60: F.FX_SPEED });
  const oneFrameOfWave = a.waveT / (N60 + 1);          // k summed over prime + N60 steps
  if (Math.abs(oneFrameOfWave - 0.019 * F.FX_SPEED) > 1e-9)
    fails.push({ case: 'FX_SPEED does not reach the effect constants',
                 hz60: oneFrameOfWave, hz120: 0.019 * F.FX_SPEED });

  document.title = 'RESULT ' + JSON.stringify({ fails, a, b });
 } catch (e) { document.title = 'THREW ' + (e && e.message) + ' | ' + String(e && e.stack || '').slice(0, 300); }
}, 700));
</script>"""

os.chdir(os.path.dirname(os.path.abspath(__file__)) + '/..')
open('_dt.html','w',encoding='utf-8').write(
    open('index.html',encoding='utf-8').read().replace('</body>', TEST + '</body>'))
try:
    out = subprocess.run(['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
        '--headless','--disable-gpu','--no-first-run','--window-size=430,932',
        '--virtual-time-budget=30000','--dump-dom','http://localhost:8899/_dt.html?test=1'],
        capture_output=True, text=True, timeout=180).stdout
finally:
    os.remove('_dt.html')

m = re.search(r'RESULT (\{.*\})</title>', out, re.S)
if not m:
    t = re.search(r'<title>([^<]*)</title>', out)
    print('NO RESULT', t.group(1) if t else '?'); sys.exit(1)
d = json.loads(m.group(1))
print(f"dt: {len(d['fails'])} fail")
for f in d['fails'][:10]: print('   ', json.dumps(f, ensure_ascii=False))
print('PASS' if not d['fails'] else 'FAIL')
sys.exit(1 if d['fails'] else 0)
