#!/usr/bin/env python3
"""Every relic must actually do the thing on its card. Two bugs of this shape have shipped --
a fruit driven to 0% killing the relics keyed to it, and 측량 widening a set of zones that did
not exist -- so this walks all 65 and reports the ones whose effect cannot be observed."""
import subprocess, os, re, json, sys

TEST = """<script>
window.addEventListener('load', () => setTimeout(() => {
 try {
  const F = window.__fs;
  const LIVE_MODIFY = ['pop'];
  const LIVE_EVENTS = ['onPop','onFruitPop','onTurn','onSpawn','onStageStart','onRunStart'];
  const report = { dead: [], badHook: [], capped: [], dupes: [], noDesc: [], gated: [] };

  // What a PLAYER can observe in one stage -- not internal variables. The first version of
  // this audit read zoneBonus directly, so 측량 looked fine: the variable moved while the
  // thing it feeds (zoneCount) stayed at 0. Internal state moving is not an effect.
  const zoneProbe = () => {
    F.rollZones();
    if (!F.zoneCells.size) return 'none';
    const i = [...F.zoneCells][0];
    const r = (i / F.COLS) | 0, c = i % F.COLS;
    return F.zoneCells.size + ':' + F.fruitScoreAt(r, c, 0);
  };
  const snap = () => JSON.stringify([
    F.colorOdds().map(v => +v.toFixed(3)),
    F.FRUIT_POINTS.map((_, i) => F.fruitScore(i)),
    F.stageTouches(), F.spawnCount(0), F.relicCap(), F.shelfSize(),
    F.bombRadius(), [4,5,7,10].map(t => F.itemNeed(t)), F.birdFlock, F.crossLine,
    F.starCoinMult, F.ROWS, zoneProbe(),
    [1,3,5,9].map(k => F.chainBonus(k)),
    F.STREAK_CAP, F.streakMult(),
    F.brickChance, F.coinFruitBonus, F.payoutMult,
    F.coinFlat, F.interestPer, F.interestPct, F.interestCap, F.starEverything, F.interestDue(),
  ]);
  // A coin-scaled relic is invisible at zero coins, so the audit would call it dead. Hold
  // money while auditing -- which is also the only state in which such a relic means anything.
  const fresh = () => { F.mode = 'rush'; F.resetRun(); F.streak = 3; F.coins = 40; };

  for (const id of Object.keys(F.RELICS)) {
    const R = F.RELICS[id];
    if (!R.desc) report.noDesc.push(id);

    for (const k of Object.keys(R.modify || {}))
      if (!LIVE_MODIFY.includes(k)) report.badHook.push(id + '.modify.' + k);
    for (const k of Object.keys(R))
      if (/^on[A-Z]/.test(k) && !LIVE_EVENTS.includes(k)) report.badHook.push(id + '.' + k);

    const hasHook = !!(R.modify && Object.keys(R.modify).length) ||
                    Object.keys(R).some(k => /^on[A-Z]/.test(k));

    fresh();
    const before = snap();
    F.relics.push(id); F.applyRelics();
    const after = snap();
    if (before === after && !hasHook) {
      if (R.requires) report.gated.push(id);          // intentional: needs a prerequisite
      else report.dead.push(id);
    }
  }

  // relics with identical descriptions at different prices are confusing, not broken
  const byDesc = {};
  for (const id of Object.keys(F.RELICS)) {
    const d2 = F.RELICS[id].desc;
    (byDesc[d2] = byDesc[d2] || []).push(id + '(' + F.RELICS[id].price + ')');
  }
  for (const d2 in byDesc) if (byDesc[d2].length > 1) report.dupes.push(d2 + ' -> ' + byDesc[d2].join(', '));

  // effects that a cap can swallow whole: buying a second one must still change something
  const CAP_FAMILIES = {
    'bomb radius': ['bomb_mod'], 'item threshold': ['tinkerer'],
    'relic slots': ['satchel'], 'shop width': [], 'board rows': ['reclaim','big_reclaim'],
  };
  for (const fam in CAP_FAMILIES) {
    const ids = CAP_FAMILIES[fam].filter(x => F.RELICS[x]);
    if (!ids.length) continue;
    fresh();
    let prev = snap(), stacked = 0;
    for (let k = 0; k < 4; k++) {
      for (const id of ids) if (!F.relics.includes(id)) F.relics.push(id);
      F.applyRelics();
      if (snap() !== prev) stacked++;
      prev = snap();
    }
    if (stacked === 0) report.capped.push(fam + ': owning them changes nothing');
  }

  fresh();
  document.title = 'RESULT ' + JSON.stringify({ report, total: Object.keys(F.RELICS).length });
 } catch (e) { document.title = 'THREW ' + e.message; }
}, 800));
</script>"""

os.chdir(os.path.dirname(os.path.abspath(__file__)) + '/..')
open('_ra.html','w',encoding='utf-8').write(
    open('index.html',encoding='utf-8').read().replace('</body>', TEST + '</body>'))
try:
    out = subprocess.run(['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
        '--headless','--disable-gpu','--no-first-run','--window-size=430,932',
        '--virtual-time-budget=40000','--dump-dom','http://localhost:8899/_ra.html?test=1'],
        capture_output=True, text=True, timeout=180).stdout
finally:
    os.remove('_ra.html')

m = re.search(r'RESULT (\{.*\})</title>', out, re.S)
if not m:
    t = re.search(r'<title>(.*?)</title>', out, re.S)
    print('NO RESULT', t.group(1)[:200] if t else ''); sys.exit(1)
r = json.loads(m.group(1)); rep = r['report']
LABEL = {'dead': '효과를 관찰할 수 없음', 'badHook': '엔진이 부르지 않는 훅',
         'capped': '상한에 먹혀 의미 없음', 'dupes': '설명이 같은 유물',
         'noDesc': '설명 없음', 'gated': '선행 조건 있음 (의도됨)'}
bad = 0
print(f"유물 {r['total']}종 감사")
for k in ['dead','badHook','capped','noDesc','dupes','gated']:
    v = rep[k]
    mark = 'ok' if not v else ('참고' if k in ('dupes','gated') else '■')
    print(f"  {LABEL[k]:<26}{len(v):>3}건  {mark}")
    for x in v: print(f'      {x}')
    if v and k not in ('dupes','gated'): bad += len(v)
print()
print('PASS' if not bad else 'FAIL')
sys.exit(0 if not bad else 1)
