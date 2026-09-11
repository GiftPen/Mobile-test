#!/usr/bin/env python3
"""A Star Rush run is five to ten minutes of relics and score. Mobile browsers discard
backgrounded tabs whenever they like, so the run has to survive being killed -- and come back
in a state the player can look at before touching anything."""
import subprocess, os, re, json, sys

TEST = """<script>
const sleep = ms => new Promise(r => setTimeout(r, ms));
window.addEventListener('load', () => setTimeout(async () => {
 try {
  const F = window.__fs, fails = [];
  const chk = (c, got, want) => { if (JSON.stringify(got) !== JSON.stringify(want))
                                    fails.push({case: c, got, want}); };
  const settle = async ms => { for (let i = 0; i < Math.ceil(ms/16); i++) { F.draw(); await sleep(16); } };
  const hidden = v => Object.defineProperty(document, 'hidden', { configurable: true, get: () => v });
  const shown = id => !document.getElementById(id).classList.contains('hidden');

  F.clearSave();
  chk('nothing saved to begin with', F.loadSave(), null);

  // --- a run in progress is written down ---
  F.start('rush'); await settle(150);
  F.score = 7777; F.stage = 5; F.coins = 99; F.touchesLeft = 9;
  F.relics.push('one_cherry', 'clover'); F.applyRelics();
  F.grid[0][0] = 3; F.grid[2][5] = 6;
  F.saveRun();
  const saved = F.loadSave();
  chk('the run is saved', !!saved, true);

  // --- killed and reopened ---
  F.resetRun(); F.running = false;
  chk('memory really was wiped', [F.score, F.relics.length], [0, 0]);
  const ok = F.resumeSavedRun();
  await settle(150);
  chk('it comes back', ok, true);
  chk('score, stage and coins survive', [F.score, F.stage, F.coins], [7777, 5, 99]);
  chk('the board is exactly as it was', [F.grid[0][0], F.grid[2][5]], [3, 6]);
  chk('the touch budget survives', F.touchesLeft, 9);
  chk('the relics survive', F.relics.length, 2);
  // derived state is NOT serialised, so it has to be recomputed or the relics do nothing
  chk('and their effects are recomputed', F.fruitScore(0), F.FRUIT_POINTS[0] + 8);
  // paused, so returning never lands on a live board mid-thought
  chk('it comes back paused', [F.running, F.paused], [true, true]);
  chk('with the pause panel up', shown('pause'), true);
  chk('and not on the menu', shown('overlay'), false);

  // --- going to the background saves AND pauses ---
  F.clearSave();
  F.start('rush'); await settle(120);
  F.score = 1234;
  hidden(true);
  document.dispatchEvent(new Event('visibilitychange'));
  await settle(80);
  chk('backgrounding saves the run', !!F.loadSave(), true);
  chk('and pauses it', F.paused, true);
  hidden(false);
  document.dispatchEvent(new Event('visibilitychange'));

  // --- the save is cleared when there is nothing to come back to ---
  F.running = true; F.gameOver('t'); await settle(80);
  chk('a finished run leaves nothing behind', F.loadSave(), null);

  F.start('rush'); await settle(100); F.saveRun();
  chk('a live run is saved again', !!F.loadSave(), true);
  F.start('rush');
  chk('starting a new run replaces it', (F.saveRun(), !!F.loadSave()), true);
  document.getElementById('btn-tomain').click(); await settle(80);
  chk('leaving for the menu on purpose clears it', F.loadSave(), null);

  // --- a tutorial is not a run ---
  try { localStorage.removeItem(F.TUT_KEY); } catch (e) {}
  F.startTutorial('rush'); await settle(150);
  F.saveRun();
  chk('the tutorial is never saved', F.loadSave(), null);
  F.finishTutorial(true); await settle(150);

  // --- a save from an older build must not be loaded ---
  F.start('rush'); await settle(100); F.saveRun();
  try {
    const o = JSON.parse(localStorage.getItem(F.SAVE_KEY));
    o.v = 'ancient';
    localStorage.setItem(F.SAVE_KEY, JSON.stringify(o));
  } catch (e) {}
  chk('an old save is refused', F.loadSave(), null);
  try { localStorage.setItem(F.SAVE_KEY, '{not json'); } catch (e) {}
  chk('a corrupt save is refused, not thrown', F.loadSave(), null);
  chk('and resuming from it just declines', F.resumeSavedRun(), false);

  F.clearSave();
  document.title = 'RESULT ' + JSON.stringify({ fails });
 } catch (e) { document.title = 'THREW ' + e.message; }
}, 800));
</script>"""

os.chdir(os.path.dirname(os.path.abspath(__file__)) + '/..')
open('_sv.html','w',encoding='utf-8').write(
    open('index.html',encoding='utf-8').read().replace('</body>', TEST + '</body>'))
try:
    out = subprocess.run(['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
        '--headless','--disable-gpu','--no-first-run','--window-size=430,932',
        '--virtual-time-budget=40000','--dump-dom','http://localhost:8899/_sv.html?test=1'],
        capture_output=True, text=True, timeout=180).stdout
finally:
    os.remove('_sv.html')

m = re.search(r'RESULT (\{.*\})</title>', out, re.S)
if not m:
    t = re.search(r'<title>(.*?)</title>', out, re.S)
    print('NO RESULT', t.group(1)[:200] if t else ''); sys.exit(1)
r = json.loads(m.group(1))
print(f"save: 중단된 런 복원, {len(r['fails'])} fail")
for f in r['fails']: print('  ', json.dumps(f, ensure_ascii=False)[:200])
print('PASS' if not r['fails'] else 'FAIL')
sys.exit(0 if not r['fails'] else 1)
