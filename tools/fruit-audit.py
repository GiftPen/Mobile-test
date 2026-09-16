#!/usr/bin/env python3
"""Which fruits have a score card, and which were left out.

Seven fruits should each be able to start a build, so each needs a rung on every ladder:
a cheap flat +N, a per-pop pile, and a multiplier. This owns every relic ALONE and diffs the
per-fruit channels, so the answer comes from what the relic actually does, not from its name."""
import subprocess, json, re, os, sys

TEST = """<script>
window.addEventListener('load', () => setTimeout(() => {
  const F = window.__fs;
  const FR = ['체리','오렌지','키위','레몬','포도','복숭아','바나나'];
  const base = () => ({ flat: F.fruitFlat.slice(), mult: F.fruitMult.slice(),
                        crown: F.fruitCrown.slice(), boost: F.fruitBoost.slice(),
                        odds: F.oddsMult.slice() });
  F.mode = 'rush'; F.resetRun(); F.relics = []; F.applyRelics();
  const zero = base();
  const out = [];
  for (const id of Object.keys(F.RELICS)) {
    const R = F.RELICS[id];
    F.mode = 'rush'; F.resetRun(); F.relics = [id]; F.applyRelics();
    const now = base(), hit = {};
    for (const ch of ['flat','mult','crown','boost','odds'])
      for (let i = 0; i < 7; i++)
        if (now[ch][i] !== zero[ch][i]) (hit[ch] = hit[ch] || {})[i] = +(now[ch][i] - zero[ch][i]).toFixed(2);
    // a per-pop pile is a hook, not a channel: ask the relic whether it reacts to a pop
    let pile = null;
    if (R.onFruitPop) {
      const before = F.fruitStack.slice();
      for (let c = 0; c < 7; c++) R.onFruitPop({ color: c, cleared: 3, score: 100 });
      pile = {};
      for (let i = 0; i < 7; i++) if (F.fruitStack[i] !== before[i]) pile[i] = F.fruitStack[i] - before[i];
      if (!Object.keys(pile).length) pile = null;
    }
    out.push({ id, tier: F.relicTier(R), price: R.price,
               name: F.nameOf(id), hit, pile });
  }
  document.title = 'RESULT ' + JSON.stringify(out);
}, 600));
</script>"""

os.chdir(os.path.dirname(os.path.abspath(__file__)) + '/..')
open('_fa.html','w',encoding='utf-8').write(
    open('index.html',encoding='utf-8').read().replace('</body>', TEST + '</body>'))
try:
    out = subprocess.run(['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
        '--headless','--disable-gpu','--no-first-run','--virtual-time-budget=20000',
        '--dump-dom','http://localhost:8899/_fa.html?test=1'],
        capture_output=True, text=True, timeout=180).stdout
finally:
    os.remove('_fa.html')
m = re.search(r'RESULT (\[.*?\])</title>', out, re.S)
if not m: print('NO RESULT'); sys.exit(1)
rows = json.loads(m.group(1))
json.dump(rows, open('/tmp/fruit-audit.json','w'), ensure_ascii=False)

FR = ['체리','오렌지','키위','레몬','포도','복숭아','바나나']
LAD = [('flat','고정 +점수'), ('pile','쌓이는 점수'), ('mult','배율'),
       ('crown','왕관 배율'), ('boost','뻥튀기'), ('odds','확률')]
print(f"유물 {len(rows)}종\n")
for li, (ch, lab) in enumerate(LAD):
    print(f'== {lab} ==')
    for i, f in enumerate(FR):
        got = []
        for r in rows:
            d = r['pile'] if ch == 'pile' else r['hit'].get(ch)
            if d and str(i) in {str(k) for k in d}:
                v = d.get(str(i), d.get(i))
                got.append(f"{r['name']}({r['tier'][:3]},{r['price']}c,+{v})")
        print(f"  {f:<4} {len(got)}  " + (', '.join(got) if got else '— 없음'))
    print()
