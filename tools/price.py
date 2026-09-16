#!/usr/bin/env python3
"""What each relic is actually WORTH, so its price can be argued from a number.

peak.py measures builds and bot.py measures runs; neither says what one relic contributes,
and run-to-run spread on those is about x2 -- useless for telling a 12-coin card from an
18-coin one. So this does not play a random game. It seeds Math.random BEFORE the game script
runs, plays a fixed number of touches with a fixed placement policy, and reads the score. Same
seed, same board, same taps: the only thing that differs between two measurements is the relic
under test, and the noise is whatever the relic itself does to the board.

Power is measured ON TOP of a small baseline rather than alone, because half the table is
multipliers and a multiplier with nothing to multiply measures zero.

Usage:  python3 -m http.server 8899 &   then
        python3 tools/price.py [--touches 60] [--seeds 3] [--out /tmp/price.json] [id ...]
"""
import subprocess, os, re, json, sys, statistics

os.chdir(os.path.dirname(os.path.abspath(__file__)) + '/..')
A = sys.argv[1:]
def opt(n, d, cast=int): return cast(A[A.index(n) + 1]) if n in A else d
TOUCHES = opt('--touches', 60)
SEEDS   = opt('--seeds', 3)
OUT     = A[A.index('--out') + 1] if '--out' in A else '/tmp/price.json'
SHOP    = '--shop' in A          # let the bot spend, so coin relics can show what money buys
WITH    = A[A.index('--with') + 1].split(',') if '--with' in A else []
_consumed = {OUT} | set(WITH) | ({A[A.index('--with') + 1]} if '--with' in A else set())
ONLY    = [a for a in A if not a.startswith('--') and not a.isdigit() and a not in _consumed]

SEED_JS = """<script>
// installed before the game script: every spawn, shop roll and odds draw comes from here, so
// two runs with the same seed see exactly the same board
window.__seed = function (s) {
  let x = (s || 1) >>> 0;
  Math.random = function () {
    x ^= x << 13; x >>>= 0; x ^= x >> 17; x ^= x << 5; x >>>= 0;
    return x / 4294967296;
  };
};
window.__seed(1);
</script>"""

TEST = r"""<script>
const sleep = ms => new Promise(r => setTimeout(r, ms));
window.addEventListener('load', () => setTimeout(async () => {
 try {
  const F = window.__fs, $ = id => document.getElementById(id), cv = $('game');
  const TOUCHES = window.__TOUCHES, SEEDS = window.__SEEDS, IDS = window.__IDS;
  const shown = id => !$(id).classList.contains('hidden');
  const settle = async (max = 600) => {
    for (let i = 0; i < max; i++) {
      if (F.links.length || F.birds.length) F.draw();
      if (!F.busy && !F.links.length && !F.birds.length) return true;
      await sleep(32);
    }
    return false;
  };
  const bestCell = () => {
    const want = F.nextColor, R = 2;
    let best = null, bs = -1e9;
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
      if (s > bs) { bs = s; best = [r, c]; }
    }
    return best;
  };
  // a small, deliberately bland base so multipliers have something to multiply and flat cards
  // are not compared against zero
  // --with adds to the baseline. Half the table only works in company: an odds relic on its
  // own just makes you pop MORE of a cheap fruit, which measured 레몬 농장 at x0.73 -- it is
  // not weak, it is one half of a pair. Measured beside its partner it says something true.
  const BASE = ['pinch', 'breather', 'whetstone'].concat(window.__WITH || []);

  const play = async (relics, seed) => {
    F.mfxStop && F.mfxStop();
    F.resetEffects && F.resetEffects();
    window.__seed(seed);
    F.start('rush');
    await sleep(40); await settle();
    F.relics = relics.slice(); F.traits = []; F.applyRelics();
    let taps = 0, guard = 0;
    while (F.running && taps < TOUCHES && guard++ < TOUCHES * 6) {
      if (shown('traits')) { F.pickTrait(F.traitOffers[0]); await sleep(15); continue; }
      if (shown('shop')) {
        // --shop: let the coins be SPENT. A coin relic is worth whatever the coins buy, and
        // nothing else in this bench can convert them -- without this, every coin card reads
        // x1.00 because the money just sits there. The shelf is fixed for a given seed, so
        // what changes between two runs is only what the extra money could reach.
        if (window.__SHOP) {
          for (let k = 0; k < 8; k++) {
            const can = F.shopOffers.filter(id => !F.shopSold.has(id)
              && F.coins >= F.priceOf(F.RELICS[id]) && F.relics.length < F.relicCap());
            if (!can.length) break;
            can.sort((a, b) => F.priceOf(F.RELICS[b]) - F.priceOf(F.RELICS[a]));
            F.buyRelic(can[0]);
            await sleep(8);
          }
        }
        F.closeShop(); await sleep(20); await settle();
        // ...and once the shelf is full, money has only one place left to go. Without this the
        // coin cards still read x1.00 after the eighth relic: the coins pile up and buy
        // nothing. Items are the sink a real run actually uses.
        if (window.__SHOP) {
          for (let k = 0; k < 12; k++) {
            const kinds = Object.keys(F.ITEM_PRICES)
              .filter(t => F.canBuyItem(t))
              .sort((a, b) => F.itemPrice(b) - F.itemPrice(a));
            if (!kinds.length) break;
            const free = F.emptyCells();
            if (!free.length) break;
            F.armItem(kinds[0]);
            if (!F.placeBoughtItem(free[0][0], free[0][1])) break;
            await sleep(8);
          }
        }
        continue;
      }
      if (shown('pause'))  { $('btn-resume').click(); await sleep(20); continue; }
      const cell = bestCell();
      if (!cell) break;
      const was = F.touchCount;
      const b = cv.getBoundingClientRect();
      const x = b.left + (cell[1] + 0.5) * b.width / F.COLS;
      const y = b.top + (cell[0] + 0.5) * b.height / F.ROWS;
      cv.dispatchEvent(new PointerEvent('pointerdown', {clientX:x, clientY:y, bubbles:true}));
      cv.dispatchEvent(new PointerEvent('pointerup',   {clientX:x, clientY:y, bubbles:true}));
      await settle();
      // No wait for the visuals here. It used to need one -- particles were drawn from the
      // game's own RNG on a timer, so tapping while they were pending shifted the stream --
      // but presentation has its own stream now, and 0.9s of virtual time per tap burned the
      // whole budget before a sweep could finish.
      if (F.touchCount > was) taps++;
    }
    const out = { score: F.score, coins: F.coins, stage: F.stage, taps, relics: F.relics.length };
    // NOT showMenu(): the menu's background animation runs on a timer and eats random numbers
    // between runs, which is the same leak by another route
    F.gameOver('bench'); await sleep(30);
    return out;
  };

  const rows = [];
  const base = [];
  for (let s = 1; s <= SEEDS; s++) base.push(await play(BASE, s));
  const med = v => { const a = v.slice().sort((p, q) => p - q); return a[a.length >> 1]; };
  const baseScore = med(base.map(r => r.score));
  const baseCoins = med(base.map(r => r.coins));
  rows.push({ id: '(기준선)', price: 0, score: baseScore, coins: baseCoins, gain: 1,
              bought: med(base.map(r => r.relics)) });

  for (const id of IDS) {
    const runs = [];
    for (let s = 1; s <= SEEDS; s++) runs.push(await play(BASE.concat([id]), s));
    const sc = med(runs.map(r => r.score)), co = med(runs.map(r => r.coins));
    rows.push({ id, price: F.priceOf(F.RELICS[id]), tier: F.relicTier(F.RELICS[id]),
                score: sc, coins: co, gain: baseScore ? sc / baseScore : 0,
                coinGain: co - baseCoins, bought: med(runs.map(r => r.relics)) });
  }
  document.title = 'RESULT ' + JSON.stringify(rows);
 } catch (e) { document.title = 'THREW ' + (e && e.message) + '|' + String(e && e.stack || '').slice(0, 200); }
}, 700));
</script>"""


def run(ids):
    page = f'_price-{os.getpid()}.html'
    src = open('index.html', encoding='utf-8').read()
    head = (f"<script>window.__TOUCHES={TOUCHES};window.__SEEDS={SEEDS};"
            f"window.__WITH={json.dumps(WITH)};window.__SHOP={'true' if SHOP else 'false'};"
            f"window.__IDS={json.dumps(ids)};</script>")
    # the seed has to be installed BEFORE the game's own script tag, not appended after it
    src = src.replace('<body', SEED_JS + '<body', 1)
    open(page, 'w', encoding='utf-8').write(src.replace('</body>', head + TEST + '</body>'))
    try:
        out = subprocess.run(['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
            '--headless', '--disable-gpu', '--no-first-run', '--window-size=430,932',
            '--disable-backgrounding-occluded-windows', '--disable-renderer-backgrounding',
            '--virtual-time-budget=60000000', '--dump-dom',
            f'http://localhost:8899/{page}?test=1'],
            capture_output=True, text=True, timeout=2700).stdout
    finally:
        try: os.remove(page)
        except OSError: pass
    m = re.search(r'RESULT (\[.*\])</title>', out, re.S)
    if not m:
        t = re.search(r'<title>(.*?)</title>', out, re.S)
        sys.exit('결과 없음 — ' + (t.group(1)[:300] if t else ''))
    return json.loads(m.group(1))


ids = ONLY
if not ids:
    sys.exit('유물 id 를 인자로 주세요')
# One Chrome for the whole list loses the whole list when it runs long: 45 relics timed out at
# 45 minutes and came back with nothing. Small batches, written out as they land.
BATCH = opt('--batch', 8)
rows, base_seen = [], None
for i in range(0, len(ids), BATCH):
    part = run(ids[i:i + BATCH])
    # the baseline is deterministic, so every batch must report the same one -- if it drifts,
    # something is leaking state between runs and the numbers cannot be compared
    if base_seen is None: base_seen = part[0]['score']; rows.append(part[0])
    elif part[0]['score'] != base_seen:
        print(f"  ! 기준선이 흔들립니다 {base_seen} -> {part[0]['score']} (배치 {i//BATCH})")
    rows += part[1:]
    json.dump(rows, open(OUT, 'w'), ensure_ascii=False)
    print(f"  {min(i+BATCH, len(ids))}/{len(ids)}", flush=True)
print(f"씨앗 {SEEDS}개 × {TOUCHES}터치 · 기준선 {rows[0]['score']:,}점")
print(f"\n{'유물':<18}{'등급':>7}{'가격':>5}{'점수':>11}{'배수':>7}{'코인':>6}{'보유':>5}")
for r in sorted(rows[1:], key=lambda r: -r['gain']):
    print(f"{r['id']:<18}{r.get('tier',''):>7}{r['price']:>5}{r['score']:>11,}"
          f"{r['gain']:>7.2f}{r.get('coinGain',0):>+6}{r.get('bought',0):>5.0f}")
print(f"\n원자료 -> {OUT}")
