#!/usr/bin/env python3
"""매턴 과일 +1 구매: coins buy a permanent per-turn spawn, outside the relic slots.

The trap this guards is the one that has bitten every accumulated stat here: applyRelics()
WIPES the derived channels (spawnBonus among them) and rebuilds them from the relic list, so
a purchase parked in spawnBonus vanishes the moment the next relic is taken. It must also
survive a save/restore round trip, must actually change how many fruit a turn drops, and must
stop at the cap instead of running the coin balance into the ground.

Nothing here hardcodes the price or the cap -- both are read from the game, so retuning them
is not a test failure."""
import subprocess, os, re, json, sys

TEST = """<script>
window.addEventListener('load', () => setTimeout(() => {
 try {
  const F = window.__fs; const fails = [];
  const chk = (c, got, want) => { if (JSON.stringify(got) !== JSON.stringify(want))
                                    fails.push({ case: c, got, want }); };
  const STEP = F.SPAWN_BUY_STEP, MAX = F.SPAWN_BUY_MAX;
  chk('the cap leaves something to buy', MAX >= 1, true);

  F.start('rush');
  const base = F.spawnCount();

  // ---- price ladder: 50, 100, 150 ... read off the game, not written down here
  F.coins = 0;
  const wantCosts = [], gotCosts = [];
  for (let i = 0; i < MAX; i++) {
    F.spawnBought = i;
    wantCosts.push(STEP * (i + 1));
    gotCosts.push(F.spawnBuyCost());
  }
  chk('price climbs by one step each time', gotCosts, wantCosts);

  // ---- no coins, no purchase
  F.spawnBought = 0; F.coins = F.spawnBuyCost() - 1;
  chk('cannot buy under price', F.canBuySpawn(), false);
  chk('a refused buy changes nothing', [F.buySpawn(), F.spawnBought], [false, 0]);

  // ---- a real purchase moves the count, the coins, and the 탕진 ledger
  F.coins = 10000; const spentBefore = F.coinsSpent, cost0 = F.spawnBuyCost();
  const coinsBefore = F.coins;
  chk('buy succeeds when affordable', F.buySpawn(), true);
  chk('+1 per turn', F.spawnCount(), base + 1);
  chk('coins paid', coinsBefore - F.coins, cost0);
  chk('counted as a spend', F.coinsSpent - spentBefore, cost0);

  // ---- THE regression: a relic arriving must not wipe what was bought
  F.applyRelics();
  chk('survives applyRelics', F.spawnCount(), base + 1);
  chk('purchase is not in spawnBonus', F.spawnBought, 1);

  // ...and a relic that also raises spawns must ADD to it, not replace it
  const spawnRelic = Object.keys(F.RELICS).find(id => {
    const before = F.spawnBonus; F.relics.push(id); F.applyRelics();
    const moved = F.spawnBonus > before; F.relics.pop(); F.applyRelics();
    return moved;
  });
  chk('a spawn relic exists to test against', !!spawnRelic, true);
  if (spawnRelic) {
    F.relics.push(spawnRelic); F.applyRelics();
    chk('relic stacks on top of the purchase', F.spawnCount(), base + 1 + F.spawnBonus);
    F.relics.pop(); F.applyRelics();
  }

  // ---- the count is not cosmetic: a turn really drops that many
  F.spawnBought = 0; F.applyRelics();
  const countFruit = () => { let n = 0;
    for (let r = 0; r < F.ROWS; r++) for (let c = 0; c < F.COLS; c++)
      if (F.grid[r][c] !== -1) n++;
    return n; };
  F.start('rush');
  const wipe = () => { for (let r = 0; r < F.ROWS; r++) for (let c = 0; c < F.COLS; c++) {
    F.grid[r][c] = -1; F.special[r][c] = null; F.hp[r][c] = 0; } };
  wipe(); F.spawnBuds(F.spawnCount()); const dropped0 = countFruit();
  F.coins = 10000; F.buySpawn();
  wipe(); F.spawnBuds(F.spawnCount()); const dropped1 = countFruit();
  chk('a bought +1 really drops one more fruit', dropped1 - dropped0, 1);

  // ---- save / restore round trip
  const saved = JSON.parse(JSON.stringify(F.serializeRun()));
  F.spawnBought = 0;
  F.restoreRun(saved); F.applyRelics();
  chk('restored from save', F.spawnBought, 1);

  // an older save has no such field at all -> 0, not NaN
  const old = JSON.parse(JSON.stringify(saved)); delete old.spawnBought;
  F.restoreRun(old); F.applyRelics();
  chk('older save defaults to 0', F.spawnBought, 0);

  // ---- a new run starts clean
  F.spawnBought = 3; F.start('rush');
  chk('a new run resets it', F.spawnBought, 0);

  // ---- the cap holds, and refuses past it even with money to burn
  F.coins = 1e9;
  let bought = 0;
  for (let i = 0; i < MAX + 5; i++) if (F.buySpawn()) bought++;
  chk('stops at the cap', bought, MAX);
  chk('cap reflected in the count', F.spawnBought, MAX);
  chk('nothing left to buy', F.canBuySpawn(), false);
  const coinsAtCap = F.coins;
  F.buySpawn();
  chk('a refused buy past the cap costs nothing', F.coins, coinsAtCap);

  document.title = 'RESULT ' + JSON.stringify({ fails });
 } catch (e) { document.title = 'THREW ' + (e && e.message) + ' | ' + String(e && e.stack || '').slice(0, 300); }
}, 700));
</script>"""

os.chdir(os.path.dirname(os.path.abspath(__file__)) + '/..')
open('_sb.html','w',encoding='utf-8').write(
    open('index.html',encoding='utf-8').read().replace('</body>', TEST + '</body>'))
try:
    out = subprocess.run(['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
        '--headless','--disable-gpu','--no-first-run','--window-size=430,932',
        '--virtual-time-budget=30000','--dump-dom','http://localhost:8899/_sb.html?test=1'],
        capture_output=True, text=True, timeout=180).stdout
finally:
    os.remove('_sb.html')

m = re.search(r'RESULT (\{.*\})</title>', out, re.S)
if not m:
    t = re.search(r'<title>([^<]*)</title>', out)
    print('NO RESULT', t.group(1) if t else '?'); sys.exit(1)
d = json.loads(m.group(1))
print(f"spawn-buy: {len(d['fails'])} fail")
for f in d['fails'][:8]: print('   ', json.dumps(f, ensure_ascii=False))
print('PASS' if not d['fails'] else 'FAIL')
sys.exit(1 if d['fails'] else 0)
