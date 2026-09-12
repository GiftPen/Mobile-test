#!/usr/bin/env python3
"""A coin you earn has to be seen arriving. Two things were wrong: the coin was drawn on the
game canvas, which is exactly the board, so it vanished at the top edge -- the very direction
it was flying; and its speed was a per-frame step, so it was a ~0.6s flick that ran faster
still on a 120Hz phone. What is checked here is that a flying coin leaves the board, reaches
the chip, takes its time getting there, and that the counter waits for it to land."""
import subprocess, os, re, json, sys

TEST = """<script>
const sleep = ms => new Promise(r => setTimeout(r, ms));
window.addEventListener('load', () => setTimeout(async () => {
 try {
  const F = window.__fs, fails = [];
  const chk = (c, got, want) => { if (JSON.stringify(got) !== JSON.stringify(want))
                                    fails.push({case: c, got, want}); };
  const fx = document.getElementById('coinfx');
  const cv = document.getElementById('game');

  F.start('rush');
  await sleep(200);
  F.clearCoinFly();

  // fly from the BOTTOM row: the longest trip, and the one the old code clipped most
  F.coins += 5;
  F.flyCoins(5, F.ROWS - 1, 3);
  await sleep(60);
  chk('the coins exist as their own layer', fx.childElementCount, 5);

  const board = cv.getBoundingClientRect();
  const chip = document.getElementById('rs-coin').getBoundingClientRect();
  chk('the chip really is above the board', chip.bottom <= board.top + 1, true);

  // Headless runs on virtual time, so neither rAF nor the animation clock advances on its
  // own. Scrub the animation by hand instead -- which is stricter anyway: it samples the real
  // path rather than whatever frames happened to land.
  const first = fx.firstElementChild;
  const an = first.getAnimations()[0];
  const dur = an.effect.getTiming().duration, delay = an.effect.getTiming().delay || 0;
  chk('the flight is slow enough to read', dur >= 700, true);
  chk('and is wall-clock, not per-frame', typeof dur, 'number');

  let aboveBoard = 0, nearChip = 1e9, samples = 0;
  for (let k = 0; k <= 40; k++) {
    an.currentTime = delay + dur * k / 40;
    const r = first.getBoundingClientRect();
    if (!r.width) continue;
    samples++;
    if (r.bottom < board.top) aboveBoard++;
    nearChip = Math.min(nearChip, Math.hypot(r.left + r.width/2 - (chip.left + chip.width/2),
                                             r.top + r.height/2 - (chip.top + chip.height/2)));
  }
  chk('the coin leaves the board instead of being clipped at its edge', aboveBoard > 0, true);
  chk('it spends real time off the board, not one frame', aboveBoard >= 4, true);
  chk('and it arrives at the chip', nearChip < 40, true);

  // it must still be on screen up there -- above the board is only useful if it is visible
  an.currentTime = delay + dur;
  const end = first.getBoundingClientRect();
  chk('and it is on screen the whole way, not off the top', end.top > -1, true);

  // --- they clean themselves up once each has run its course ---
  // a finished animation with no forward fill drops out of getAnimations(), so skip those
  const finishAll = () => { for (const el of [...fx.children]) {
    const a2 = el.getAnimations()[0]; if (!a2) { el.remove(); continue; }
    const t = a2.effect.getTiming();
    a2.currentTime = (t.delay || 0) + t.duration;
  } };
  // long enough for the slowest coin's wall-clock fallback, which is what actually lands
  // them here: a frozen timeline never fires onfinish
  // rAF never fires under virtual time, so draw() -- and with it tickCoins() -- has to be
  // pumped by hand, the same way items-test drives the board
  const allDone = async () => {
    for (let i = 0; i < 40; i++) { F.draw(); await sleep(80); }
  };
  finishAll();
  await allDone();
  chk('the coins clean themselves up', fx.childElementCount, 0);
  chk('nothing is left pending', F.coinFlyPending, 0);

  // --- the counter waits for the coins, it does not jump ahead ---
  F.clearCoinFly();
  const shownNow = () => +document.getElementById('rs-coin-v').textContent;
  const pump = async n => { for (let i = 0; i < n; i++) { F.draw(); await sleep(20); } };
  F.coins = 0; await pump(25);                   // let the chip settle, so 0 means 0
  chk('the chip starts from a settled 0', shownNow(), 0);
  F.addCoins(6, F.ROWS - 1, 2);
  await pump(10);                                // ticks aplenty, but nothing has landed yet
  chk('the chip does not bank coins that are still in the air', shownNow(), 0);
  chk('the coins were counted as owed, though', F.coins, 6);
  finishAll();
  await allDone();
  chk('but it does once they land', shownNow(), 6);

  // --- a reset takes them with it ---
  F.addCoins(4, 3, 3);
  await sleep(40);
  F.resetEffects();
  chk('a reset clears the coins in flight', fx.childElementCount, 0);
  chk('and the pending count with them', F.coinFlyPending, 0);

  document.title = 'RESULT ' + JSON.stringify(
    { fails, ms: dur, above: aboveBoard, of: samples, near: Math.round(nearChip) });
 } catch (e) { document.title = 'THREW ' + e.message + ' | ' + (e.stack || '').slice(0, 200); }
}, 800));
</script>"""

os.chdir(os.path.dirname(os.path.abspath(__file__)) + '/..')
open('_coinfly.html','w',encoding='utf-8').write(
    open('index.html',encoding='utf-8').read().replace('</body>', TEST + '</body>'))
try:
    out = subprocess.run(['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
        '--headless','--disable-gpu','--no-first-run','--window-size=430,932',
        '--virtual-time-budget=60000','--dump-dom','http://localhost:8899/_coinfly.html?test=1'],
        capture_output=True, text=True, timeout=180).stdout
finally:
    os.remove('_coinfly.html')

m = re.search(r'RESULT (\{.*\})</title>', out, re.S)
if not m:
    t = re.search(r'<title>(.*?)</title>', out, re.S)
    print('NO RESULT', t.group(1)[:300] if t else ''); sys.exit(1)
r = json.loads(m.group(1))
print(f"coinfly: 비행 {r['ms']}ms · 판 밖 {r['above']}/{r['of']} 지점 · 칩까지 {r['near']}px · {len(r['fails'])} fail")
for f in r['fails']: print('  ', json.dumps(f, ensure_ascii=False)[:240])
print('PASS' if not r['fails'] else 'FAIL')
sys.exit(0 if not r['fails'] else 1)
