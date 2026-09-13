#!/usr/bin/env python3
"""Plays Star Rush headless and reports where runs actually end up.

Every balance decision so far has been argued from the relic table. The table is now 111
relics and 57 traits with multiplying channels in it, and nothing has measured a real run
since. This drives the actual game -- placements, shop, traits, stage transitions -- and
reports the distribution, with the coin economy broken out because a coin build is the one
that compounds in two directions at once.

Usage:  python3 tools/bot.py [runs] [strategy ...]
        strategies: none greedy coin fruit cracker combo   (default: all of them)
"""
import subprocess, os, re, json, sys, statistics

RUNS = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 12
STRATS = sys.argv[2:] or ['none', 'greedy', 'coin', 'fruit', 'cracker', 'combo']

TEST = r"""<script>
const sleep = ms => new Promise(r => setTimeout(r, ms));
window.addEventListener('load', () => setTimeout(async () => {
 try {
  const F = window.__fs, $ = id => document.getElementById(id), cv = $('game');
  const RUNS = window.__RUNS, STRATS = window.__STRATS, MAX_STAGE = 20;
  const shown = id => !$(id).classList.contains('hidden');

  // rAF never fires here, so the board is advanced by hand and then waited on
  // draw() only when something needs frames. The chain itself advances on timers, and a
  // canvas render per poll is what made a three-run sweep miss a thirty-minute deadline.
  const settle = async (max = 150) => {
    for (let i = 0; i < max; i++) {
      if (F.links.length || F.birds.length) F.draw();
      if (!F.busy && !F.links.length && !F.birds.length) return true;
      await sleep(8);
    }
    return false;
  };
  const tap = async (r, c) => {
    const b = cv.getBoundingClientRect();
    const x = b.left + (c + 0.5) * b.width / F.COLS, y = b.top + (r + 0.5) * b.height / F.ROWS;
    cv.dispatchEvent(new PointerEvent('pointerdown', {clientX:x, clientY:y, bubbles:true}));
    cv.dispatchEvent(new PointerEvent('pointerup',   {clientX:x, clientY:y, bubbles:true}));
    await settle();
  };

  // where to put the next fruit: as many same-colour neighbours as possible, and away from
  // the edges of a filling board so the run does not choke itself
  const bestCell = () => {
    const want = F.nextColor, R = 2;
    let best = null, bestScore = -1e9;
    for (let r = 0; r < F.ROWS; r++) for (let c = 0; c < F.COLS; c++) {
      if (F.grid[r][c] !== -1) continue;
      let same = 0, near = 0;
      for (let dr = -R; dr <= R; dr++) for (let dc = -R; dc <= R; dc++) {
        const nr = r + dr, nc = c + dc;
        if ((!dr && !dc) || nr < 0 || nr >= F.ROWS || nc < 0 || nc >= F.COLS) continue;
        if (F.grid[nr][nc] !== want) continue;
        if (Math.max(Math.abs(dr), Math.abs(dc)) <= 1) same += 2; else near++;
      }
      const s = same * 3 + near;
      if (s > bestScore) { bestScore = s; best = [r, c]; }
    }
    return best;
  };

  // what a strategy wants out of the shop and the trait screen
  const WANT = {
    none:    () => [],
    greedy:  () => null,                       // anything, dearest first
    coin:    () => ['coin'],
    fruit:   () => ['fruit0', 'fruit3'],       // cherry/lemon: the cheap ones you can farm
    cracker: () => ['risk'],
    combo:   () => ['combo'],
  };
  const wants = (id, tags, isTrait) => {
    if (!tags) return true;
    if (!tags.length) return false;
    const cats = isTrait
      ? (F.TRAITS[id].effects || []).map(e => e.stat === 'oddsMult' || e.stat === 'fruitMult'
          || e.stat === 'fruitCrown' || e.stat === 'stackOnPop' ? 'fruit' + e.target : e.stat)
      : F.identity(id);
    return tags.some(t => cats.some(c => c === t
      || (t === 'coin' && /coin|payout|interest|discount/i.test(c))
      || (t === 'risk' && /risk|cracker|brick/i.test(c))
      || (t === 'combo' && /combo|streak|chain/i.test(c))));
  };

  const out = [];
  for (const strat of STRATS) {
    const tags = WANT[strat]();
    for (let run = 0; run < RUNS; run++) {
      F.start('rush');
      await sleep(60);
      await settle();
      let coinsPeak = 0, coinsEarned = 0, lastCoins = 0, spent = 0, bought = 0, shops = 0;
      const perStage = [];
      let guard = 0;
      while (F.running && F.stage <= MAX_STAGE && guard++ < 700) {
        if (F.coins > lastCoins) coinsEarned += F.coins - lastCoins;
        else spent += lastCoins - F.coins;
        lastCoins = F.coins;
        coinsPeak = Math.max(coinsPeak, F.coins);

        if (shown('traits')) {
          const offer = F.traitOffers.slice();
          const pick = offer.find(id => wants(id, tags, true)) || offer[0];
          F.pickTrait(pick);
          await sleep(20);
          continue;
        }
        if (shown('shop')) {
          shops++;
          for (let k = 0; k < 6; k++) {
            const buyable = F.shopOffers.filter(id => !F.shopSold.has(id)
              && F.coins >= F.priceOf(F.RELICS[id]) && F.relics.length < F.relicCap());
            if (!buyable.length) break;
            const pref = buyable.filter(id => wants(id, tags, false));
            // null = "anything, dearest first"; an empty list = "buy nothing at all".
            // Treating both as falsy made the buy-nothing control buy everything.
            const list = pref.length ? pref : (tags === null ? buyable : []);
            if (!list.length) break;
            list.sort((a, b) => F.RELICS[b].price - F.RELICS[a].price);
            F.buyRelic(list[0]); bought++;
            await sleep(10);
          }
          F.closeShop();
          await sleep(40);
          await settle();
          continue;
        }
        // stage cleared? bank it and move on
        const rn = $('rush-next');
        if (!rn.classList.contains('hidden') && !rn.disabled) {
          perStage.push({ st: F.stageLabel(F.stage), score: F.score, coins: F.coins });
          rn.click();
          await sleep(700);
          await settle();
          continue;
        }
        const cell = bestCell();
        if (!cell) break;
        await tap(cell[0], cell[1]);
      }
      out.push({ strat, stage: F.stage, label: F.stageLabel(F.stage), score: F.score,
                 coins: F.coins, coinsPeak, coinsEarned, spent, bought, shops,
                 relics: F.relics.length, traits: F.traits.length,
                 perStage: perStage.slice(0, 12) });
      F.gameOver('bot');
      await sleep(60);
      F.showMenu();
      await sleep(40);
    }
  }
  document.title = 'RESULT ' + JSON.stringify(out);
 } catch (e) { document.title = 'THREW ' + e.message + ' | ' + (e.stack || '').slice(0, 200); }
}, 700));
</script>"""

os.chdir(os.path.dirname(os.path.abspath(__file__)) + '/..')

def play(strat, runs):
    """One Chrome per strategy. A single sweep that overruns yields nothing at all, and
    --dump-dom has no way to stream partial results out."""
    head = f"<script>window.__RUNS={runs};window.__STRATS={json.dumps([strat])};</script>"
    open('_bot.html','w',encoding='utf-8').write(
        open('index.html',encoding='utf-8').read().replace('</body>', head + TEST + '</body>'))
    try:
        out = subprocess.run(['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
            '--headless','--disable-gpu','--no-first-run','--window-size=430,932',
            '--virtual-time-budget=600000','--dump-dom','http://localhost:8899/_bot.html?test=1'],
            capture_output=True, text=True, timeout=900).stdout
    except subprocess.TimeoutExpired:
        return None
    finally:
        os.remove('_bot.html')
    m = re.search(r'RESULT (\[.*\])</title>', out, re.S)
    if not m:
        t = re.search(r'<title>(.*?)</title>', out, re.S)
        print(f'  {strat}: 결과 없음 — ' + (t.group(1)[:120] if t else ''))
        return None
    return json.loads(m.group(1))

def med(v): return round(statistics.median(v), 1) if v else 0

print(f"봇 {RUNS}판 × 전략 {len(STRATS)}종")
print(f"\n{'전략':<9}{'도달(중앙)':>10}{'최고':>7}{'점수(중앙)':>12}{'코인최대':>10}{'번코인':>8}{'쓴코인':>8}{'유물':>6}{'특성':>6}")
rows = []
for s in STRATS:
    r = play(s, RUNS)
    if not r:
        print(f"{s:<9}{'(시간 초과)':>10}")
        continue
    rows += r
    print(f"{s:<9}{med([x['stage'] for x in r]):>10}{max(x['stage'] for x in r):>7}"
          f"{med([x['score'] for x in r]):>12}{med([x['coinsPeak'] for x in r]):>10}"
          f"{med([x['coinsEarned'] for x in r]):>8}{med([x['spent'] for x in r]):>8}"
          f"{med([x['relics'] for x in r]):>6}{med([x['traits'] for x in r]):>6}")

coin = [x for x in rows if x['strat'] == 'coin']
if coin:
    print("\n코인 빌드, 스테이지별 보유 코인:")
    for x in coin[:5]:
        line = ' · '.join(f"{p['st']} {p['coins']}" for p in x['perStage'][:8])
        print(f"  {x['label']}까지 · {line}")
if rows:
    json.dump(rows, open('/tmp/bot-last.json','w'))
    print(f"\n원자료 {len(rows)}판 -> /tmp/bot-last.json")
