#!/usr/bin/env python3
"""빌드를 '완성할 수 있는가'를 잰다. peak.py 가 '완성하면 얼마나 센가'를 재는 것과 짝이다.

peak.py 는 유물을 공짜로 쥐어주므로 어떤 빌드든 완성된다. 실제로는 상점이 그 유물을 보여줘야
하고(등급별 확률), 살 돈이 있어야 한다. 그래서 '콤보가 약하다'는 결론과 '콤보는 애초에 모을 수
없다'는 결론이 섞여 버린다 -- 둘은 전혀 다른 처방을 부른다.

판은 플레이하지 않는다. 게임의 진짜 rollOffers() 를 그대로 돌려 매 스테이지 상점을 굴리고,
그 트리의 유물만 사면서 언제 몇 개가 모이는지 본다. 그래서 여기 나오는 숫자는 손기술이나
생존력과 무관한, 순수한 '뽑기 + 비용' 난이도다.

코인 수입은 스테이지 정산(3+스테이지)만 센다. 실제로는 코인 과일과 남은 터치가 더 들어오므로
이건 하한선이다 -- --income 2.0 으로 배수를 줘서 민감도를 볼 수 있다.

Usage:  python3 tools/reach.py [--runs 400] [--stages 30] [--income 1.0] [--no-reroll]
"""
import subprocess, os, re, json, sys

os.chdir(os.path.dirname(os.path.abspath(__file__)) + '/..')
A = sys.argv[1:]
def opt(n, d, cast=int):
    return cast(A[A.index(n) + 1]) if n in A else d
RUNS   = opt('--runs', 400)
STAGES = opt('--stages', 30)
INCOME = opt('--income', 1.0, float)
REROLL = '--no-reroll' not in A

TEST = r"""<script>
window.addEventListener('load', () => setTimeout(() => {
 try {
  const F = window.__fs;
  const RUNS = window.__RUNS, STAGES = window.__STAGES,
        INCOME = window.__INCOME, REROLL = window.__REROLL;

  // ---- same membership rule peak.py uses, so the two tables talk about the same builds ----
  const SCALAR_FRUIT = { cherryPile: 0, citrusFuse: 1, kiwiSeed: 2, lemonFree: 3,
                         grapeBulk: 4, peachBurst: 5, bananaSpread: 6, fieldOn: 6 };
  const ARRAYS = ['oddsMult', 'fruitMult', 'fruitFlat', 'fruitCrown', 'stackOnPop'];
  const snap = () => [ARRAYS.map(k => (F[k] || []).slice()),
                      Object.keys(SCALAR_FRUIT).map(k => String(F[k]))];
  F.mode = 'rush'; F.resetRun(); F.relics = []; F.traits = []; F.applyRelics();
  const tagOf = {};
  for (const id of Object.keys(F.RELICS)) {
    F.relics = []; F.applyRelics(); const a = snap();
    F.relics = [id]; F.applyRelics(); const b = snap();
    const t = new Set(F.relicCats(id));
    for (let i = 0; i < 7; i++)
      for (let k = 0; k < ARRAYS.length; k++)
        if (a[0][k][i] !== b[0][k][i]) t.add('fruit' + i);
    Object.keys(SCALAR_FRUIT).forEach((k, i) => {
      if (a[1][i] !== b[1][i]) t.add('fruit' + SCALAR_FRUIT[k]);
    });
    tagOf[id] = t;
  }
  const price = id => F.priceOf(F.RELICS[id]);
  const forTag = (tag, isFruit) => {
    const mine = Object.keys(F.RELICS).filter(id => tagOf[id].has(tag) && !F.RELICS[id].life);
    const own = id => !isFruit || [...tagOf[id]].filter(x => /^fruit\d$/.test(x)).length <= 2;
    return mine.sort((a, b) => (own(b) - own(a)) || (price(b) - price(a)));
  };
  const TAGS = { '체리': 'fruit0', '오렌지': 'fruit1', '키위': 'fruit2', '레몬': 'fruit3',
                 '포도': 'fruit4', '복숭아': 'fruit5', '바나나': 'fruit6',
                 '크래커': 'risk', '코인': 'coin', '콤보': 'combo', '보드': 'board',
                 '점수': 'score' };

  const out = [];
  for (const name of Object.keys(TAGS)) {
    const tag = TAGS[name];
    // the whole tree is buyable, not just its dearest ten: a player chasing 포도 takes the
    // 12-coin vine as readily as the 40-coin cornucopia, and pricing the cheap half out of
    // the simulation made a tree of legendaries look unreachable for the wrong reason
    const tree = forTag(tag, /^fruit/.test(tag));
    const coreSet = new Set(tree);
    const peak8 = new Set(tree.slice(0, 8));   // exactly what peak.py hands over for free
    const legends = tree.filter(id => F.relicTier(F.RELICS[id]) === 'legend');
    const keyLegend = legends[0];    // the dearest one: the card the build is actually named after
    const runs = [];
    for (let r = 0; r < RUNS; r++) {
      F.mode = 'rush'; F.resetRun(); F.relics = []; F.traits = []; F.applyRelics();
      let coins = 0, spent = 0;
      const gotAt = {};                       // owned-count -> stage it was first reached
      let gotLegend = 0;
      let mark10 = 0, mark20 = 0;
      for (let st = 1; st <= STAGES; st++) {
        if (st === 11) mark10 = F.relics.length;
        if (st === 21) mark20 = F.relics.length;
        coins += Math.round((3 + st) * INCOME);     // the stage payout, the one certain income
        // the shop rolls with what you already hold, so resonance is live here too
        let offers = F.rollOffers(F.shelfSize());
        let tries = 0;
        while (tries < 2) {
          let bought = false;
          for (const id of offers.slice().sort((a, b) => price(b) - price(a))) {
            if (!coreSet.has(id) || F.relics.includes(id)) continue;
            if (F.relics.length >= F.relicCap()) break;
            if (coins < F.priceOf(F.RELICS[id])) continue;
            // Keep the last two slots for something worth having. Filling them with 5-coin
            // commons is what made a 41-relic tree own its legendary 0% of the time: the
            // shelf was full long before one ever showed up.
            const tier = F.relicTier(F.RELICS[id]);
            if (F.relics.length >= F.relicCap() - 2
                && !['epic', 'unique', 'legend'].includes(tier)) continue;
            coins -= F.priceOf(F.RELICS[id]); spent += F.priceOf(F.RELICS[id]);
            F.relics = F.relics.concat([id]); F.applyRelics();
            offers = offers.filter(x => x !== id);
            bought = true;
            if (!gotAt[F.relics.length]) gotAt[F.relics.length] = st;
            if (F.relicTier(F.RELICS[id]) === 'legend') gotLegend = gotLegend || st;
          }
          // nothing here for this build: pay 3 to look again rather than bank money you are
          // not going to spend -- which is what a player chasing one tree actually does
          if (bought || !REROLL || coins < 3 + 8) break;
          coins -= 3; spent += 3;
          offers = F.rollOffers(F.shelfSize());
          tries++;
        }
      }
      runs.push({ owned: F.relics.length, gotAt, legend: gotLegend, spent, left: coins,
                  at10: mark10, at20: mark20,
                  peak8: F.relics.filter(id => peak8.has(id)).length,
                  key: keyLegend ? F.relics.includes(keyLegend) : null });
    }
    out.push({ name, coreSize: tree.length, legends: legends.length,
               keyLegend: keyLegend ? F.RELICS[keyLegend].name : null,
               corePrice: tree.slice(0, 8).reduce((s, id) => s + price(id), 0), runs });
  }
  document.title = 'RESULT ' + JSON.stringify(out);
 } catch (e) { document.title = 'THREW ' + (e && e.message) + '|' + String(e && e.stack || '').slice(0, 200); }
}, 700));
</script>"""

page = f'_reach-{os.getpid()}.html'
head = (f"<script>window.__RUNS={RUNS};window.__STAGES={STAGES};"
        f"window.__INCOME={INCOME};window.__REROLL={'true' if REROLL else 'false'};</script>")
open(page, 'w', encoding='utf-8').write(
    open('index.html', encoding='utf-8').read().replace('</body>', head + TEST + '</body>'))
try:
    out = subprocess.run(['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
        '--headless', '--disable-gpu', '--no-first-run', '--virtual-time-budget=600000',
        '--dump-dom', f'http://localhost:8899/{page}?test=1'],
        capture_output=True, text=True, timeout=1800).stdout
finally:
    try: os.remove(page)
    except OSError: pass
m = re.search(r'RESULT (\[.*\])</title>', out, re.S)
if not m:
    t = re.search(r'<title>(.*?)</title>', out, re.S)
    sys.exit('결과 없음 — ' + (t.group(1)[:300] if t else ''))
data = json.loads(m.group(1))

import statistics
def med(v): return statistics.median(v) if v else None
print(f"상점 {RUNS}판 시뮬 · {STAGES}스테이지 · 수입 정산×{INCOME}"
      f" · 리롤 {'함' if REROLL else '안함'}")
print(f"\n{'빌드':<7}{'트리':>5}{'전설':>5}{'10st':>6}{'20st':>6}{'30st':>6}"
      f"{'전설보유':>8}{'핵심전설':>8}{'고점8중':>8}")
print('  ' + '-' * 62)
for b in data:
    rs = b['runs']
    legend = sum(1 for r in rs if r['legend']) * 100 // len(rs)
    print(f"{b['name']:<7}{b['coreSize']:>5}{b['legends']:>5}"
          f"{med([r['at10'] for r in rs]):>6.0f}{med([r['at20'] for r in rs]):>6.0f}"
          f"{med([r['owned'] for r in rs]):>6.0f}"
          f"{(str(legend) + '%' if b['legends'] else '-'):>8}"
          f"{((str(sum(1 for r in rs if r['key']) * 100 // len(rs)) + '%') if b['keyLegend'] else '-'):>8}"
          f"{med([r['peak8'] for r in rs]):>8.0f}")
print("\n  10st/20st/30st = 그 시점에 보유한 그 트리 유물 수 (중앙값, 슬롯 상한 10)")
print("  전설보유 = 30스테이지까지 그 트리의 전설을 하나라도 가진 판의 비율")
print("  핵심전설 = 그 트리에서 가장 비싼 전설(빌드의 이름값을 하는 카드)을 쥔 판의 비율")
print("  고점8중 = peak.py 가 공짜로 쥐어주는 상위 8개 중 실제로 가진 개수")
for b in data:
    if b['keyLegend']: print(f"    {b['name']}: {b['keyLegend']}")
json.dump(data, open('/tmp/reach-last.json', 'w'))
