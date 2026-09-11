#!/usr/bin/env python3
"""Ads must never be able to take something the player did not offer. What is checked here is
restraint, not delivery: the revive is once per run, the interstitial is rate limited and can
never block a retry, the banner never covers the board, and a paid removal removes everything."""
import subprocess, os, re, json, sys

TEST = """<script>
const sleep = ms => new Promise(r => setTimeout(r, ms));
window.addEventListener('load', () => setTimeout(async () => {
 try {
  const F = window.__fs, fails = [];
  const chk = (c, got, want) => { if (JSON.stringify(got) !== JSON.stringify(want))
                                    fails.push({case: c, got, want}); };
  const A = F.Ads;
  const shown = id => !document.getElementById(id).classList.contains('hidden');
  try { localStorage.removeItem('fs_noads'); localStorage.removeItem('fs_games'); } catch (e) {}
  A.setRemoved(false); A.resetForTest();

  // --- the first runs are never interrupted ---
  const early = [];
  for (let i = 0; i < A.FREE_GAMES; i++) { A.countGame(); if (A.interstitialDue()) early.push(i + 1); }
  chk('the first runs are never interrupted', early, []);

  // --- and after that it is still rate limited. Driven the way the game drives it: ask, and
  //     if the answer is yes actually show one, because showing is what resets the counter.
  let shownCount = 0;
  for (let i = 0; i < 12; i++) {
    A.countGame();
    if (A.interstitialDue()) { await A.show('interstitial'); shownCount++; }
  }
  chk('an interstitial is not shown every game', shownCount <= 2, true);
  chk('but it does eventually appear', shownCount >= 1, true);
  // asking without showing must not silently consume the allowance either
  const before = A.sinceAd;
  A.interstitialDue(); A.interstitialDue();
  chk('merely asking consumes nothing', A.sinceAd, before);

  // --- revive: offered once, then gone ---
  F.mode = 'rush'; F.resetRun(); F.running = true;
  F.revivedThisRun = false;
  F.gameOver('test');
  await sleep(120);
  chk('a revive is offered on game over', shown('btn-revive'), true);
  F.revivedThisRun = true;
  F.gameOver('test');
  await sleep(120);
  chk('but only once per run', shown('btn-revive'), false);
  // a new run gets its offer back
  F.start('rush');
  chk('a new run restores it', F.revivedThisRun, false);

  // --- reviving keeps the run, it does not restart it ---
  F.mode = 'rush'; F.resetRun(); F.running = true;
  F.score = 4321; F.stage = 5; F.relics.push('one_cherry'); F.applyRelics();
  for (let r = 0; r < F.ROWS; r++) for (let c = 0; c < F.COLS; c++) F.grid[r][c] = 0;
  F.touchesLeft = 0;
  F.reviveRun();
  await sleep(120);
  chk('the score survives a revive', F.score, 4321);
  chk('the stage survives', F.stage, 5);
  chk('the relics survive', F.relics.includes('one_cherry'), true);
  chk('there is room to play again', F.grid.flat().filter(v => v === -1).length > 0, true);
  chk('and touches to play with', F.touchesLeft > 0, true);
  chk('the run is live', F.running, true);

  // --- the banner never covers the board ---
  F.start('rush');
  await sleep(120);
  chk('no banner during play', shown('banner'), false);
  F.coins = 999; F.openShop();
  await sleep(60);
  chk('banner in the shop', shown('banner'), true);
  F.closeShop();
  await sleep(60);
  chk('gone again once playing', shown('banner'), false);

  // --- paying removes all of it ---
  // checked in the SHOP, where the banner would otherwise be showing: asserting it is hidden
  // while playing proves nothing, since it is hidden there anyway
  A.setRemoved(true);
  F.openShop();
  await sleep(60);
  chk('no banner in the shop once removed', shown('banner'), false);
  F.closeShop();
  await sleep(60);
  chk('no interstitial once removed', A.interstitialDue(), false);
  const res = await A.show('interstitial');
  chk('and showing one is a no-op', res.skipped, 'removed');
  chk('the stub never appeared', shown('adstub'), false);
  A.setRemoved(false);

  // --- the stub really blocks while it is up, and clears afterwards ---
  const p = A.show('rewarded');
  await sleep(60);
  chk('the ad surface is up', shown('adstub'), true);
  document.getElementById('adstub-x').click();
  const r2 = await p;
  chk('closing it resolves', r2.ok, true);
  chk('and it goes away', shown('adstub'), false);

  try { localStorage.removeItem('fs_noads'); localStorage.removeItem('fs_games'); } catch (e) {}
  document.title = 'RESULT ' + JSON.stringify({ fails, free: A.FREE_GAMES, every: A.RETRY_EVERY });
 } catch (e) { document.title = 'THREW ' + e.message; }
}, 800));
</script>"""

os.chdir(os.path.dirname(os.path.abspath(__file__)) + '/..')
open('_ads.html','w',encoding='utf-8').write(
    open('index.html',encoding='utf-8').read().replace('</body>', TEST + '</body>'))
try:
    out = subprocess.run(['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
        '--headless','--disable-gpu','--no-first-run','--window-size=430,932',
        '--virtual-time-budget=40000','--dump-dom','http://localhost:8899/_ads.html?test=1'],
        capture_output=True, text=True, timeout=180).stdout
finally:
    os.remove('_ads.html')

m = re.search(r'RESULT (\{.*\})</title>', out, re.S)
if not m:
    t = re.search(r'<title>(.*?)</title>', out, re.S)
    print('NO RESULT', t.group(1)[:200] if t else ''); sys.exit(1)
r = json.loads(m.group(1))
print(f"ads: 첫 {r['free']}판 무광고 · 이후 {r['every']}판마다 최대 1회, {len(r['fails'])} fail")
for f in r['fails']: print('  ', json.dumps(f, ensure_ascii=False)[:200])
print('PASS' if not r['fails'] else 'FAIL')
sys.exit(0 if not r['fails'] else 1)
