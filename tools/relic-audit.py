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
  const report = { dead: [], badHook: [], capped: [], dupes: [], noDesc: [], gated: [], inert: [] };

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
    F.crackerChance, F.coinFruitBonus, F.payoutMult,
    F.coinFlat, F.interestPer, F.interestPct, F.interestCap, F.starEverything, F.interestDue(),
    F.spendFlat, F.priceOf(F.RELICS.crown), F.itemPrice('bomb'),
    F.resonance, F.offerWeight('one_cherry'),
    F.crackerValue(), F.crackerCoin, +F.crackerBoom, +F.crackerDouble, +F.crackerEvery,
    F.cherryPile, F.grapeBulk, +F.lemonFree, F.bananaSpread, F.coinFruitMult, F.coinToScore,
    +F.peachBurst, +F.citrusFuse, +F.kiwiSeed, +F.fieldOn,
    F.crackerTouch, +F.comboKeep,
  ]);
  // A coin-scaled relic is invisible at zero coins, so the audit would call it dead. Hold
  // money while auditing -- which is also the only state in which such a relic means anything.
  // hold money AND have spent some: both are invisible at zero, and a relic that scales
  // with either would be reported dead purely because the audit started broke
  const fresh = () => { F.mode = 'rush'; F.resetRun(); F.streak = 3; F.coins = 40; F.coinsSpent = 40; };

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
      // A gated relic is not excused: it has to DO something once its gate is open, or it is
      // a dead card you can only buy after working for the right to buy it. Open the gate
      // with whatever relic opens it, then look again.
      if (R.requires) {
        let alive = false;
        for (const other of Object.keys(F.RELICS)) {
          if (other === id) continue;
          fresh(); F.relics = [other]; F.applyRelics(); F.rollZones();
          if (!R.requires()) continue;
          const gatedBefore = snap();
          F.relics = [other, id]; F.applyRelics();
          if (snap() !== gatedBefore) { alive = true; break; }
        }
        (alive ? report.gated : report.dead).push(id);
      } else report.dead.push(id);
    }
  }

  // ---- a cracker payoff card has to make crackers ----
  // "크래커를 부수면 점수 +300" is not a dead card by the test above -- it moves a channel --
  // but the channel does nothing unless crackers exist, and in 스타 러시 they only exist
  // because a relic makes them. Measured: 57% of runs were offered a payoff card before
  // anything that spawns one, at a median of stage 3. Owning it alone must produce crackers.
  for (const id of Object.keys(F.RELICS)) {
    fresh();
    F.relics = [id]; F.applyRelics();
    const pays = F.crackerBonus > 0 || F.crackerMult > 1 || F.crackerCoin > 0 ||
                 F.crackerTouch > 0;
    if (!pays) continue;
    const makes = F.crackerChance > 0 || F.crackerEvery;
    if (!makes) report.inert.push(id + ': 크래커 보상만 있고 등장이 없음');
    // and the card must not lie about the number. Changing the two together is two edits, and
    // the first pass at 2/3/4/5 moved the descriptions and left the values at 4/5/6/8 -- every
    // card promising a rate it did not deliver, and nothing to notice it.
    const said = String(F.RELICS[id].desc).match(/(\d+)\s*%/);
    if (said) {
      const promised = +said[1] / 100;
      if (Math.abs(promised - F.crackerChance) > 1e-9)
        report.inert.push(`${id}: 카드는 ${said[1]}%, 실제 ${(F.crackerChance*100).toFixed(0)}%`);
    }
    // ...and the guarantee is a FLOOR, not a contribution. Summed, the forced cracker build
    // hit a 77% spawn rate, filled the board with pieces nothing could clear, and a tree that
    // ran to stage 31 died at stage 4. Owning every payoff card must not raise the rate above
    // what the single most generous one promises.
    if (makes && !F.crackerEvery) {
      fresh();
      F.relics = ['crumb_plate','cracker_score','mill','cracker_coin','oven'].filter(x => F.RELICS[x]);
      F.applyRelics();
      const all = F.crackerChance;
      let solo = 0;
      for (const one of F.relics.slice()) {
        fresh(); F.relics = [one]; F.applyRelics();
        if (F.crackerChance > solo) solo = F.crackerChance;
      }
      if (all > solo + 1e-9 && !report.inert.some(x => x.startsWith('합산')))
        report.inert.push(`합산됨: 보상 카드 전부 = ${(all*100).toFixed(0)}%, 가장 큰 한 장 = ${(solo*100).toFixed(0)}%`);
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
         'inert': '보상만 있고 조건을 못 만듦',
         'capped': '상한에 먹혀 의미 없음', 'dupes': '설명이 같은 유물',
         'noDesc': '설명 없음', 'gated': '선행 조건 있음 (의도됨)'}
bad = 0
print(f"유물 {r['total']}종 감사")
for k in ['dead','badHook','capped','inert','noDesc','dupes','gated']:
    v = rep[k]
    mark = 'ok' if not v else ('참고' if k in ('dupes','gated') else '■')
    print(f"  {LABEL[k]:<26}{len(v):>3}건  {mark}")
    for x in v: print(f'      {x}')
    if v and k not in ('dupes','gated'): bad += len(v)
print()
print('PASS' if not bad else 'FAIL')
sys.exit(0 if not bad else 1)
