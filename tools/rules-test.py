"""Headless check for the rule chokepoints in index.html.

Run:  python3 -m http.server 8899 &   then   python3 tools/rules-test.py

Asserts the scoring formula against a reference copy of the pre-chokepoint inline
maths, and that pickColor() stays uniform while every colorWeight is 1. Uses the
?test=1 hook in index.html.

End-to-end replay is NOT usable here: draw() consumes Math.random() for screen-shake
on every frame, so a seeded playthrough desyncs with frame timing (verified: the same
revision scored 780 and 687 on two runs).
"""
import subprocess, re, os, json, sys
os.chdir('/Users/kimjaehoon/Mobile-test')
TEST = """<script>
window.addEventListener('load', () => setTimeout(() => {
  const F = window.__fs;
  if (!F) { document.title = 'RESULT {"fatal":"no test hook"}'; return; }
  const fails = []; let n = 0;
  F.score = 0;                        // score is undefined until start(); seed it
  // reference = the inline formula as it stood BEFORE the addScore/scorePop chokepoint
  const refStreak = s => Math.min(1 + s * 0.2, 2.0);
  const refPop = (base, cleared, s) => Math.round(base * (1 + (cleared - 1) * 0.15) * refStreak(s));
  for (let s = 0; s <= 12; s++) {
    F.streak = s;
    for (let base = 0; base <= 60; base++) {
      for (let cleared = 1; cleared <= 16; cleared++) {
        F.score = 0;
        const before = F.score;
        F.scorePop(base, cleared);
        const got = F.score - before, want = refPop(base, cleared, s);
        n++;
        if (got !== want && fails.length < 8) fails.push({s, base, cleared, got, want});
      }
    }
  }
  // fruitScore must equal the old raw FRUIT_POINTS while every multiplier is 1.0
  const fsFails = [];
  for (let c = 0; c < 7; c++)
    if (F.fruitScore(c) !== F.FRUIT_POINTS[c]) fsFails.push({c, got: F.fruitScore(c), want: F.FRUIT_POINTS[c]});
  // pickColor must stay uniform while every weight is 1
  const hist = new Array(7).fill(0);
  F.score = 0;                       // score 0 -> the 4 starting colours are active
  for (let i = 0; i < 70000; i++) hist[F.pickColor()]++;
  // ---- run-state round trip ----
  // This list is the TEST's own idea of what belongs to a run. If serializeRun()
  // forgets a field, restore leaves it at its reset value and the compare fails.
  const runFails = [];
  const grid10 = () => Array.from({length:10}, (_,r) => Array.from({length:8}, (_,c) => (r*8+c) % 7));
  F.resetRun();
  F.ROWS = 10;
  F.grid = grid10();
  F.special = Array.from({length:10}, (_,r) => Array.from({length:8}, (_,c) => (r+c)%5 ? null : 'bomb'));
  F.hp = Array.from({length:10}, (_,r) => Array(8).fill(r));
  F.nextColor = 5; F.nextColor2 = 2;
  F.score = 1234; F.streak = 3; F.touchCount = 77;
  F.colorWeight = [1,2,3,4,5,6,7];
  F.fruitMult = [1,1.5,2,1,1,1,3];
  const want = {ROWS:10, grid:F.grid, special:F.special, hp:F.hp, nextColor:5, nextColor2:2,
                score:1234, streak:3, touchCount:77, colorWeight:[1,2,3,4,5,6,7],
                fruitMult:[1,1.5,2,1,1,1,3]};
  const snap = JSON.parse(JSON.stringify(F.serializeRun()));

  F.resetRun();                                   // reset must wipe it all
  const resetLeaks = [];
  if (F.score !== 0) resetLeaks.push('score');
  if (F.streak !== 0) resetLeaks.push('streak');
  if (F.touchCount !== 0) resetLeaks.push('touchCount');
  if (F.ROWS !== 8) resetLeaks.push('ROWS');
  if (F.grid.length !== 8) resetLeaks.push('grid.rows');
  if (F.nextColor !== null) resetLeaks.push('nextColor');
  if (JSON.stringify(F.colorWeight) !== '[1,1,1,1,1,1,1]') resetLeaks.push('colorWeight');
  if (JSON.stringify(F.fruitMult) !== '[1,1,1,1,1,1,1]') resetLeaks.push('fruitMult');

  const restored = F.restoreRun(snap);
  if (!restored) runFails.push({field:'restoreRun', got:'returned false'});
  for (const k in want) {
    const a = JSON.stringify(F[k]), b = JSON.stringify(want[k]);
    if (a !== b) runFails.push({field:k, got:String(a).slice(0,60), want:String(b).slice(0,60)});
  }
  // the decay-only layers must be rebuilt clean at the restored size
  if (F.glow.length !== 10 || F.glow.some(row => row.length !== 8 || row.some(v => v !== null)))
    runFails.push({field:'glow', got:'not a clean 10x8 layer'});
  if (F.appear.length !== 10 || F.appear.some(row => row.some(v => v !== 0)))
    runFails.push({field:'appear', got:'not a clean 10x8 layer'});
  // an unknown save version must be refused rather than half-applied
  if (F.restoreRun({v:99, rows:8}) !== false) runFails.push({field:'version guard', got:'accepted v99'});
  if (F.restoreRun(null) !== false) runFails.push({field:'null guard', got:'accepted null'});
  F.resetRun();

  document.title = 'RESULT ' + JSON.stringify({
    cases: n, fails, fsFails, hist, runFails, resetLeaks,
    fatal: null
  });
}, 900));
</script>
"""
open('_ut.html','w',encoding='utf-8').write(
    open('index.html',encoding='utf-8').read().replace('</body>', TEST + '</body>'))
out = subprocess.run(['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '--headless','--disable-gpu','--no-first-run','--window-size=430,932',
    '--virtual-time-budget=30000','--dump-dom','http://localhost:8899/_ut.html?test=1'],
    capture_output=True, text=True, timeout=120).stdout
os.remove('_ut.html')
m = re.search(r'RESULT (\{.*?\})</title>', out, re.S)
if not m:
    print('NO RESULT'); sys.exit(1)
res = json.loads(m.group(1))
ok = (not res['fails'] and not res['fsFails'] and res['cases'] > 0
      and not res['runFails'] and not res['resetLeaks'])
active = sum(1 for h in res['hist'] if h > 0)
spread = (max(res['hist']) - min(h for h in res['hist'] if h > 0)) / max(res['hist'])
print(f"scoring : {res['cases']} cases, {len(res['fails'])} fail")
print(f"fruit   : {len(res['fsFails'])} fail")
print(f"pickColor: {active} active colours, max spread {spread:.1%}")
print(f"run state: {len(res['runFails'])} round-trip fail, {len(res['resetLeaks'])} reset leak")
if res['runFails']: print('  ', res['runFails'][:4])
if res['resetLeaks']: print('   leaked:', res['resetLeaks'])
if res['fails']: print('  e.g.', res['fails'][:3])
print('PASS' if ok and spread < 0.05 else 'FAIL')
sys.exit(0 if ok and spread < 0.05 else 1)
