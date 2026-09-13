#!/usr/bin/env python3
"""Do the score channels compose, or do they fight?

A fruit's score now passes through several independent multipliers and several independent
additions, from relics written at different times: flat points, the epic +1.2, the unique
crown, the coin-fruit ×10, the marked-cell ×2, a per-stage pile. Board growth and the map
move underneath all of it. The risk is not that one of them is wrong -- each has its own
test -- but that together they round each other away, double-count, or produce a number that
is not a number. Everything here is checked against the game's OWN getters, so it keeps
holding when the values are retuned."""
import subprocess, os, re, json, sys

TEST = """<script>
const sleep = ms => new Promise(r => setTimeout(r, ms));
window.addEventListener('load', () => setTimeout(async () => {
 try {
  const F = window.__fs, fails = [];
  const chk = (c, got, want) => { if (JSON.stringify(got) !== JSON.stringify(want))
                                    fails.push({case: c, got, want}); };
  const finite = v => typeof v === 'number' && isFinite(v) && !isNaN(v);
  const fresh = rel => { F.mode = 'rush'; F.resetRun(); F.relics = rel.slice(); F.applyRelics(); };

  // a cell that is BOTH marked and carrying a coin: the one place every multiplier meets
  const markCell = (r, c) => { F.zoneCells.add(r * F.COLS + c); };
  const setup = rel => {
    fresh(rel);
    F.zoneCells.clear(); markCell(2, 2);
    for (let r = 0; r < F.ROWS; r++) for (let c = 0; c < F.COLS; c++) F.coinCell[r][c] = 0;
    F.coinCell[2][2] = 1;
  };

  // ---- 1. every channel still moves the number when the others are present ----
  const ALL = ['one_cherry', 'cherry_ruby', 'cherry_crown', 'golden_reap', 'hotspot', 'cherry_pile'];
  // 체리 더미 only shows once cherries have popped, so give it something to have piled up
  const setupAll = rel => { setup(rel); F.stageStack[0] = 10; };
  setupAll(ALL);
  const full = F.fruitScoreAt(2, 2, 0);
  chk('the stacked score is a number', finite(full) && full > 0, true);
  for (const drop of ALL) {
    setupAll(ALL.filter(x => x !== drop));
    // 체리 더미 is what PUTS points in stageStack; dropping it leaves the pile we planted,
    // so it is checked by its own effect rather than by its absence
    if (drop === 'cherry_pile') { chk('the pile relic exists', !!F.RELICS.cherry_pile, true); continue; }
    chk('dropping ' + drop + ' changes the total', F.fruitScoreAt(2, 2, 0) !== full, true);
  }
  // the pile feeds the same additive base as the flats, so the multipliers apply to it
  setupAll(ALL); F.stageStack[0] = 0;
  const noPile = F.fruitScoreAt(2, 2, 0);
  F.stageStack[0] = 10;
  chk('a pile of 10 is worth more than 10 once multiplied',
      F.fruitScoreAt(2, 2, 0) - noPile > 10, true);

  // ---- 2. and it composes the way the parts say it does ----
  setupAll(ALL);
  const plainCell = F.fruitScoreAt(3, 3, 0);          // no coin, no mark
  chk('a plain cell is just the fruit', plainCell, F.fruitScore(0));
  chk('a coin+marked cell is the fruit through both multipliers',
      F.fruitScoreAt(2, 2, 0),
      Math.round(Math.round(F.fruitScore(0) * F.coinFruitMult) * F.zoneMult));
  // the two multipliers must not swallow one another
  setup(['golden_reap']);
  const coinOnly = F.fruitScoreAt(2, 2, 0) / F.fruitScore(0);
  setup(['hotspot']);
  const zoneOnly = F.fruitScoreAt(2, 2, 0) / F.fruitScore(0);
  setup(['golden_reap', 'hotspot']);
  const both = F.fruitScoreAt(2, 2, 0) / F.fruitScore(0);
  chk('coin and marked-cell multiply together',
      Math.abs(both - coinOnly * zoneOnly) < 0.05, true);

  // ---- 3. 금맥 pays on the mark, and that is separate from what the cell SCORES ----
  setup(['gold_vein', 'golden_reap']);
  chk('금맥 is a coin effect, not a score one', F.zoneCoin, true);
  chk('and it does not change the score',
      F.fruitScoreAt(2, 2, 0), Math.round(F.fruitScore(0) * F.coinFruitMult));

  // ---- 4. the board growing does not strand the map ----
  fresh(['big_reclaim', 'hotspot', 'survey']);
  F.rollZones();
  const rows = F.ROWS;
  chk('개간 grew the board', rows > F.ROWS_BASE, true);
  const stray = [...F.zoneCells].filter(i => (i / F.COLS | 0) >= rows || i % F.COLS >= F.COLS);
  chk('every marked cell is on the board', stray, []);
  chk('marked cells still score', finite(F.fruitScoreAt(rows - 1, 0, 0)), true);
  chk('and there are some', F.zoneCount() > 0, true);

  // ---- 5. no combination produces a non-number ----
  // Only relicCap() relics are ACTIVE, so "hold everything" would really test eight of them
  // and quietly pass. Walk the table a capful at a time instead.
  const EVERY = Object.keys(F.RELICS);
  const bad = [];
  fresh([]);
  const step = F.relicCap();
  chk('a capful is a real number of relics', step >= 4, true);
  for (let i = 0; i < EVERY.length; i += step) {
    fresh(EVERY.slice(i, i + step));
    F.coins = 9999; F.coinsSpent = 9999; F.streak = 400;
    F.zoneCells.clear(); markCell(2, 2);
    for (let k = 0; k < 7; k++) {
      if (!finite(F.fruitScore(k))) bad.push('fruitScore ' + k + ' @' + i);
      if (!finite(F.fruitScoreAt(2, 2, k))) bad.push('fruitScoreAt ' + k + ' @' + i);
      if (!finite(F.streakMult(k))) bad.push('streakMult ' + k + ' @' + i);
    }
    for (const n of [1, 5, 20, 100]) if (!finite(F.chainBonus(n))) bad.push('chainBonus ' + n + ' @' + i);
    if (!finite(F.crackerValue())) bad.push('crackerValue @' + i);
    if (!finite(F.interestDue())) bad.push('interestDue @' + i);
  }
  chk('no capful of relics yields a non-number', bad, []);

  // 레몬 한 스푼 removes a CAP; it must not remove the number
  fresh(['lemon_spoon']); F.streak = 400;
  chk('lemon really is uncapped', F.lemonFree, true);
  chk('an uncapped lemon combo is still finite', finite(F.streakMult(3)), true);
  chk('and it really is above the cap', F.streakMult(3) > F.STREAK_CAP, true);
  chk('while every other fruit still obeys it', F.streakMult(0) <= F.STREAK_CAP, true);

  // ---- 6. 포도 송이 reaches items sooner without breaking the curve ----
  fresh(['grape_bunch2']);
  chk('the cluster bonus grows with the bulk',
      F.chainBonus(5 + F.grapeBulk) > F.chainBonus(5), true);
  chk('and stays a number at size zero', finite(F.chainBonus(0)), true);

  F.relics = []; F.applyRelics(); F.resetRun();
  document.title = 'RESULT ' + JSON.stringify({ fails, full, rows });
 } catch (e) { document.title = 'THREW ' + e.message + ' | ' + (e.stack || '').slice(0, 160); }
}, 800));
</script>"""

os.chdir(os.path.dirname(os.path.abspath(__file__)) + '/..')
open('_stack.html','w',encoding='utf-8').write(
    open('index.html',encoding='utf-8').read().replace('</body>', TEST + '</body>'))
try:
    out = subprocess.run(['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
        '--headless','--disable-gpu','--no-first-run','--window-size=430,932',
        '--virtual-time-budget=40000','--dump-dom','http://localhost:8899/_stack.html?test=1'],
        capture_output=True, text=True, timeout=180).stdout
finally:
    os.remove('_stack.html')

m = re.search(r'RESULT (\{.*\})</title>', out, re.S)
if not m:
    t = re.search(r'<title>(.*?)</title>', out, re.S)
    print('NO RESULT', t.group(1)[:280] if t else ''); sys.exit(1)
r = json.loads(m.group(1))
print(f"stack: 합성 점수 {r['full']} · 판 {r['rows']}줄 · {len(r['fails'])} fail")
for f in r['fails']: print('  ', json.dumps(f, ensure_ascii=False)[:200])
print('PASS' if not r['fails'] else 'FAIL')
sys.exit(0 if not r['fails'] else 1)
