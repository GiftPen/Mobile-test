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
  document.title = 'RESULT ' + JSON.stringify({
    cases: n, fails, fsFails, hist,
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
ok = not res['fails'] and not res['fsFails'] and res['cases'] > 0
active = sum(1 for h in res['hist'] if h > 0)
spread = (max(res['hist']) - min(h for h in res['hist'] if h > 0)) / max(res['hist'])
print(f"scoring : {res['cases']} cases, {len(res['fails'])} fail")
print(f"fruit   : {len(res['fsFails'])} fail")
print(f"pickColor: {active} active colours, max spread {spread:.1%}")
if res['fails']: print('  e.g.', res['fails'][:3])
print('PASS' if ok and spread < 0.05 else 'FAIL')
sys.exit(0 if ok and spread < 0.05 else 1)
