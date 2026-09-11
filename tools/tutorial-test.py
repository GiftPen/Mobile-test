#!/usr/bin/env python3
"""The tutorial is the first thing a new player touches. What matters: it cannot be got wrong
(one cell responds), it advances, it finishes into a real game, it never shows twice, and the
board it shows looks like the game rather than like a diagram."""
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
  const settle = async ms => { for (let i = 0; i < Math.ceil(ms/16); i++) { F.draw(); await sleep(16); } };
  const hidden = id => getComputedStyle(document.getElementById(id)).visibility === 'hidden';

  try { localStorage.removeItem(F.TUT_KEY); } catch (e) {}
  chk('a fresh player has not done it', F.tutorialDone(), false);

  F.startTutorial('rush');
  await settle(250);
  chk('it starts on the first step', !!F.tut && F.tut.i, 0);
  chk('the panel is showing', document.getElementById('tut').classList.contains('hidden'), false);
  chk('there is instruction text', (document.getElementById('tut-text').textContent||'').length > 5, true);
  // the run HUD belongs to a game that has not started; it must not compete with the lesson
  chk('the run HUD is out of the way', ['rush','ishop','rush-next'].filter(id => !hidden(id)), []);

  // a tap anywhere but the highlight does nothing at all -- the point of the spotlight
  const wrong = [(F.tut.target[0] + 4) % F.ROWS, (F.tut.target[1] + 4) % F.COLS];
  const before = F.grid.flat().filter(v => v !== -1).length;
  tapCell(wrong[0], wrong[1]);
  await settle(300);
  chk('a tap outside the highlight is ignored', F.grid.flat().filter(v => v !== -1).length, before);
  chk('and it has not advanced', F.tut.i, 0);

  // Walk every step. Two things are checked on each board before it is tapped:
  //  - previewShows is what drawNextPreview actually drew. Steps set nextColor by hand, so a
  //    stale preview ships easily, and the player watches a fruit that is not the one landing.
  //  - the board must be populated beyond the shape being taught, or it reads as a diagram.
  const SCRIPTED = [2, 8, 5];
  const mismatched = [], sparse = [], stepsSeen = [];
  for (let guard = 0; guard < 6 && F.tut; guard++) {
    const i = F.tut.i;
    stepsSeen.push(i);
    if (F.previewShows !== F.nextColor)
      mismatched.push('step ' + i + ': preview ' + F.previewShows + ' vs queued ' + F.nextColor);
    const filled = F.grid.flat().filter(v => v !== -1).length;
    if (filled <= SCRIPTED[i] + 2) sparse.push('step ' + i + ': only ' + filled + ' fruit');
    const t = F.tut.target.slice();
    tapCell(t[0], t[1]);
    for (let w = 0; w < 250 && F.tut && F.tut.i === i; w++) { F.draw(); await sleep(16); }
  }
  chk('every step was reached', stepsSeen, [0, 1, 2]);
  chk('the preview always shows the fruit that will land', mismatched, []);
  chk('every board looks like a real one, not a diagram', sparse, []);

  chk('it finishes', F.tut, null);
  chk('the panel is gone', document.getElementById('tut').classList.contains('hidden'), true);
  chk('the HUD comes back', ['rush','ishop'].filter(id => hidden(id)), []);
  chk('and it drops into a real run', F.running, true);
  chk('in the mode that was asked for', F.mode, 'rush');
  chk('it is marked done', F.tutorialDone(), true);
  chk('no cell is gated afterwards', [F.tutAllows(0,0), F.tutAllows(7,7)], [true, true]);

  // skipping counts as done too, and still starts the game
  try { localStorage.removeItem(F.TUT_KEY); } catch (e) {}
  F.startTutorial('arcade');
  await settle(250);
  F.finishTutorial(true);
  await settle(250);
  chk('skipping marks it done', F.tutorialDone(), true);
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
        '--virtual-time-budget=90000','--dump-dom','http://localhost:8899/_tut.html?test=1'],
        capture_output=True, text=True, timeout=240).stdout
finally:
    os.remove('_tut.html')

m = re.search(r'RESULT (\{.*\})</title>', out, re.S)
if not m:
    t = re.search(r'<title>(.*?)</title>', out, re.S)
    print('NO RESULT', t.group(1)[:200] if t else ''); sys.exit(1)
r = json.loads(m.group(1))
print(f"tutorial: {r['steps']}단계, {len(r['fails'])} fail")
for f in r['fails']: print('  ', json.dumps(f, ensure_ascii=False)[:220])
print('PASS' if not r['fails'] else 'FAIL')
sys.exit(0 if not r['fails'] else 1)
