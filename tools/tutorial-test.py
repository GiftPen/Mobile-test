#!/usr/bin/env python3
"""The tutorial is the first thing a new player touches, so the things that matter are that
it cannot be got wrong (only one cell responds), that it advances, that it finishes into a
real game, and that it never shows twice."""
import subprocess, os, re, json, sys

TEST = """<script>
const sleep = ms => new Promise(r => setTimeout(r, ms));
window.addEventListener('load', () => setTimeout(async () => {
 try {
  const F = window.__fs, fails = [];
  const chk = (c, got, want) => { if (JSON.stringify(got) !== JSON.stringify(want))
                                    fails.push({case: c, got, want}); };
  const cv = document.getElementById('game');
  const tapCell = (r, c) => {
    const b = cv.getBoundingClientRect();
    const x = b.left + (c + 0.5) * (b.width / F.COLS);
    const y = b.top  + (r + 0.5) * (b.height / F.ROWS);
    cv.dispatchEvent(new PointerEvent('pointerdown', {clientX:x, clientY:y, bubbles:true}));
    cv.dispatchEvent(new PointerEvent('pointerup',   {clientX:x, clientY:y, bubbles:true}));
  };
  const settle = async ms => { const n = Math.ceil(ms/16); for (let i=0;i<n;i++){ F.draw(); await sleep(16); } };

  try { localStorage.removeItem(F.TUT_KEY); } catch (e) {}
  chk('a fresh player has not done it', F.tutorialDone(), false);

  F.startTutorial('rush');
  await settle(200);
  chk('it starts on the first step', !!F.tut && F.tut.i, 0);
  chk('the panel is showing', document.getElementById('tut').classList.contains('hidden'), false);
  chk('there is instruction text', (document.getElementById('tut-text').textContent||'').length > 5, true);
  // the run HUD belongs to a game that has not started; it must not compete with the lesson
  const hidden = id => getComputedStyle(document.getElementById(id)).visibility === 'hidden';
  chk('the run HUD is out of the way', ['rush','ishop','rush-next'].filter(id => !hidden(id)), []);
  chk('every step has a target cell', F.TUT_STEPS.length > 0, true);

  // 1) the wrong cell does nothing at all -- this is the whole point of the spotlight
  const target = F.tut.target.slice();
  const wrong = [0, 0];
  const before = F.grid.flat().filter(v => v !== -1).length;
  tapCell(wrong[0], wrong[1]);
  await settle(200);
  chk('a tap outside the highlight is ignored', F.grid.flat().filter(v => v !== -1).length, before);
  chk('and it has not advanced', F.tut.i, 0);

  // 2) the right cell advances it
  tapCell(target[0], target[1]);
  await settle(1600);
  chk('the highlighted cell advances the tutorial', F.tut && F.tut.i, 1);
  chk('and the next step has its own target', !!(F.tut && F.tut.target), true);

  // 3) walk the rest of the way through, tapping only what is asked
  for (let guard = 0; guard < 8 && F.tut; guard++) {
    const t = F.tut.target; if (!t) break;
    tapCell(t[0], t[1]);
    await settle(1600);
  }
  chk('it finishes', F.tut, null);
  chk('the panel is gone', document.getElementById('tut').classList.contains('hidden'), true);
  chk('and the HUD comes back', ['rush','ishop'].filter(id => hidden(id)), []);
  chk('and drops into a real run', F.running, true);
  chk('in the mode that was asked for', F.mode, 'rush');
  chk('it is marked done', F.tutorialDone(), true);

  // 4) once done, the board is free again
  chk('no cell is gated afterwards', [F.tutAllows(0,0), F.tutAllows(7,7)], [true, true]);

  // 5) skipping also counts as done
  try { localStorage.removeItem(F.TUT_KEY); } catch (e) {}
  F.startTutorial('arcade');
  await settle(200);
  F.finishTutorial(true);
  await settle(200);
  chk('skipping marks it done too', F.tutorialDone(), true);
  chk('and still starts the game', F.running, true);

  try { localStorage.removeItem(F.TUT_KEY); } catch (e) {}
  document.title = 'RESULT ' + JSON.stringify({ fails, steps: F.TUT_STEPS.length });
 } catch (e) { document.title = 'THREW ' + e.message; }
}, 800));
</script>"""

os.chdir(os.path.dirname(os.path.abspath(__file__)) + '/..')
open('_tut.html','w',encoding='utf-8').write(
    open('index.html',encoding='utf-8').read().replace('</body>', TEST + '</body>'))
try:
    out = subprocess.run(['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
        '--headless','--disable-gpu','--no-first-run','--window-size=430,932',
        '--virtual-time-budget=60000','--dump-dom','http://localhost:8899/_tut.html?test=1'],
        capture_output=True, text=True, timeout=180).stdout
finally:
    os.remove('_tut.html')

m = re.search(r'RESULT (\{.*\})</title>', out, re.S)
if not m:
    t = re.search(r'<title>(.*?)</title>', out, re.S)
    print('NO RESULT', t.group(1)[:200] if t else ''); sys.exit(1)
r = json.loads(m.group(1))
print(f"tutorial: {r['steps']}단계, {len(r['fails'])} fail")
for f in r['fails']: print('  ', json.dumps(f, ensure_ascii=False)[:200])
print('PASS' if not r['fails'] else 'FAIL')
sys.exit(0 if not r['fails'] else 1)
