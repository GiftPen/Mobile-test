"""Headless behaviour checks for the board items (bird / star / line).

Run:  python3 -m http.server 8899 &   then   python3 tools/items-test.py

Covers the two faults found in the 2026-09-08 item audit:
  bird  - landing on an item mid-chain must detonate it, never delete it
  star  - the turn must not spawn fruit into cells the constellation is still drawing
Uses the ?test=1 hook in index.html.
"""
import subprocess, re, os, json, sys
os.chdir('/Users/kimjaehoon/Mobile-test')
TEST = r"""<script>
window.__err = [];
window.addEventListener('error', e => window.__err.push(e.message + ' @' + e.lineno));
const sleep = ms => new Promise(r => setTimeout(r, ms));
// headless produces no frames, so rAF never fires -- pump draw() to advance animation
const pump = async (frames, gap) => { for (let i = 0; i < frames; i++)
  { window.__fs.draw(); await sleep(gap || 8); } };
window.addEventListener('load', async () => {
 try {
  await sleep(700);
  const F = window.__fs, $ = id => document.getElementById(id), cv = $('game');
  const fails = [];
  const chk = (name, got, want) => { if (JSON.stringify(got) !== JSON.stringify(want))
                                       fails.push({ check: name, got, want }); };
  const over = () => !$('gameover').classList.contains('hidden');
  const clearBoard = () => { for (let r=0;r<F.ROWS;r++) for (let c=0;c<F.COLS;c++)
    { F.grid[r][c] = -1; F.special[r][c] = null; F.appear[r][c] = 0; } };

  $('btn-arcade').click();
  await sleep(200);

  // ---- bird lands on an item while the board is busy ----
  clearBoard();
  F.grid[0][0] = 1; F.special[0][0] = 'bomb';       // a bomb waiting to be hit
  F.grid[7][7] = 2;                                  // somewhere for the bird to come from
  F.birds.push({ sr: 7, sc: 7, tr: 0, tc: 0, t: 0.99, curve: 1 });
  F.busy = true;                                     // a chain is still animating
  await pump(30);
  chk('busy: bomb survives',   F.special[0][0], 'bomb');
  chk('busy: bird waits',      F.birds.length > 0, true);
  F.busy = false;                                    // board settles
  await pump(40);
  chk('free: bomb detonated',  F.special[0][0], null);
  chk('free: bomb cell empty', F.grid[0][0], -1);
  chk('free: bird gone',       F.birds.length, 0);

  // ---- a bought item has to BE the item ----
  // "line" is the shop's word; the board's words are lineH/lineV/lineX. Writing the shop's
  // word into the cell left something nothing draws and nothing fires: an ordinary-looking
  // fruit that cost 15 coins. Checked by behaviour, not by the name it was given.
  const buyAndPlace = async (kind, relics) => {
    F.mode = 'rush'; F.resetRun(); F.relics = (relics || []).slice(); F.applyRelics();
    clearBoard();
    F.running = true; F.busy = false; F.paused = false;
    F.coins = 500;
    F.armItem(kind);
    const ok = F.placeBoughtItem(4, 4);
    await pump(10);
    return { ok, sp: F.special[4][4], col: F.grid[4][4] };
  };
  for (const kind of ['bird', 'lineH', 'lineV', 'bomb', 'star']) {
    const r = await buyAndPlace(kind);
    chk(kind + ': the purchase goes through', r.ok, true);
    chk(kind + ': the cell holds a fruit', r.col >= 0, true);
    chk(kind + ': and a special the board knows',
        ['bird', 'lineH', 'lineV', 'lineX', 'bomb', 'star'].includes(r.sp), true);
  }

  // the basket is not a cell item: it fills the BOARD
  {
    F.mode = 'rush'; F.resetRun(); F.relics = []; F.applyRelics();
    clearBoard();
    F.running = true; F.busy = false; F.paused = false; F.coins = 500;
    const before = F.filledCount();
    F.armItem('basket');
    const ok = F.placeBoughtItem(4, 4);
    await pump(20);
    chk('the basket purchase goes through', ok, true);
    chk('and it fills the board, not a cell', F.filledCount() - before >= F.BASKET_FRUIT, true);
    chk('the cell it was placed on holds a plain fruit', F.special[4][4], null);
    chk('and the fruit it drops obey the odds', F.grid.flat().filter(v => v >= 0).length > 0, true);
  }

  // and the bought line must actually sweep a row or a column when it goes off
  {
    await buyAndPlace('lineH');
    const row = [], col = [];
    for (let c = 0; c < F.COLS; c++) { if (c !== 4) { F.grid[4][c] = 2; row.push(c); } }
    for (let r = 0; r < F.ROWS; r++) { if (r !== 4) { F.grid[r][4] = 2; col.push(r); } }
    const sp = F.special[4][4];
    F.busy = false;
    F.tapItem(4, 4);
    await pump(90, 12);
    const rowGone = row.every(c => F.grid[4][c] === -1);
    const colGone = col.every(r => F.grid[r][4] === -1);
    chk('a bought line clears its line', sp === 'lineH' ? rowGone : sp === 'lineV' ? colGone
                                        : rowGone && colGone, true);
  }

  // a row is a row and a column is a column -- the shop sells them separately now
  chk('the row item is a row', (await buyAndPlace('lineH')).sp, 'lineH');
  chk('the column item is a column', (await buyAndPlace('lineV')).sp, 'lineV');

  // 십자로 must cover what you paid for, either one
  chk('십자로 turns a bought row into a cross', (await buyAndPlace('lineH', ['crossing'])).sp, 'lineX');
  chk('십자로 turns a bought column into a cross', (await buyAndPlace('lineV', ['crossing'])).sp, 'lineX');
  F.relics = []; F.applyRelics(); F.resetEffects();

  // ---- 금빛 수확: the coin-fruit bonus has to reach the SCORE, not just the modifier ----
  // Testing modify() with a hand-made ctx proves the relic; it does not prove that anything
  // ever counts the coin fruit and passes it in. This blows up a real cluster.
  const blastScore = async (withCoin, relics) => {
    F.mode = 'rush'; F.resetRun(); F.relics = relics.slice(); F.applyRelics();
    clearBoard();
    for (let r = 0; r < F.ROWS; r++) for (let c = 0; c < F.COLS; c++) F.coinCell[r][c] = 0;
    F.grid[3][3] = 1; F.special[3][3] = 'bomb';
    for (const [r, c] of [[3,4],[3,5],[4,4],[4,5],[2,3],[2,4]]) {
      F.grid[r][c] = 1;
      if (withCoin) F.coinCell[r][c] = 1;
    }
    F.score = 0; F.streak = 0; F.busy = false;
    F.tapItem(3, 3);
    await pump(90, 12);
    return F.score;
  };
  const noRelicPlain = await blastScore(false, []);
  const noRelicCoin  = await blastScore(true,  []);
  chk('without the relic, coin fruit changes nothing', noRelicCoin, noRelicPlain);
  const withPlain = await blastScore(false, ['golden_harvest']);
  const withCoin  = await blastScore(true,  ['golden_harvest']);
  chk('금빛 수확 is idle when no coin fruit was taken', withPlain, noRelicPlain);
  chk('and pays when one was', withCoin > withPlain, true);
  chk('by about half again', Math.abs(withCoin / withPlain - 1.5) < 0.02, true);

  // the same again through PLACEMENT, which scores on a different line entirely -- passing
  // the count on one path and not the other is the obvious way to half-fix this
  const placeScore = async withCoin => {
    F.mode = 'rush'; F.resetRun(); F.relics = ['golden_harvest']; F.applyRelics();
    clearBoard();
    for (let r = 0; r < F.ROWS; r++) for (let c = 0; c < F.COLS; c++) F.coinCell[r][c] = 0;
    for (const [r, c] of [[3,5],[4,4],[4,5],[2,4]]) {
      F.grid[r][c] = 5;
      if (withCoin) F.coinCell[r][c] = 1;
    }
    F.nextColor = 5; F.nextColor2 = 5;
    F.score = 0; F.streak = 0; F.busy = false;
    const rr = cv.getBoundingClientRect();
    const x = rr.left + 4.5 * rr.width / F.COLS, y = rr.top + 3.5 * rr.height / F.ROWS;
    cv.dispatchEvent(new PointerEvent('pointerdown', {clientX:x, clientY:y, bubbles:true}));
    cv.dispatchEvent(new PointerEvent('pointerup',   {clientX:x, clientY:y, bubbles:true}));
    await pump(90, 12);
    return F.score;
  };
  // and once more through the STAR, which collects its cells in a loop of its own
  const starScore = async withCoin => {
    F.mode = 'rush'; F.resetRun(); F.relics = ['golden_harvest']; F.applyRelics();
    clearBoard();
    for (let r = 0; r < F.ROWS; r++) for (let c = 0; c < F.COLS; c++) F.coinCell[r][c] = 0;
    for (const [r, c] of [[6,1],[6,2],[6,3],[6,4],[5,2]]) {
      F.grid[r][c] = 4;
      if (withCoin) F.coinCell[r][c] = 1;
    }
    F.grid[4][4] = 4; F.special[4][4] = 'star';
    F.score = 0; F.streak = 0; F.busy = false;
    F.tapItem(4, 4);
    await pump(120, 12);
    return F.score;
  };
  const starPlain = await starScore(false);
  const starCoin  = await starScore(true);
  chk('the star path counts its coin fruit too', starCoin > starPlain, true);

  const placedPlain = await placeScore(false);
  const placedCoin  = await placeScore(true);
  chk('placing into a plain cluster is unaffected', placedCoin > placedPlain, true);
  chk('and the placement path gets the same half again',
      Math.abs(placedCoin / placedPlain - 1.5) < 0.02, true);
  F.relics = []; F.applyRelics(); F.resetEffects();

  // ---- 전설 과일: seven rules, each driven on a real board ----
  // Wait for the board to go quiet before setting the next case up: a chain left running
  // from the previous one keeps mutating the grid underneath, which is how this suite
  // started failing one case in three.
  const settleBoard = async () => {
    for (let i = 0; i < 120 && (F.busy || F.links.length || F.birds.length); i++) {
      F.draw(); await sleep(12);
    }
  };
  // Watch a set of cells for the whole resolution: a cleared cell can be refilled by the
  // end-of-turn spawner, so asking "is it empty now" measures the spawner, not the blast.
  const watch = cells => {
    const seen = new Set();
    return { seen, tick: () => { for (const [r, c] of cells)
      if (F.grid[r][c] === -1) seen.add(r + ',' + c); } };
  };
  const pumpWatch = async (w, n, g) => {
    for (let i = 0; i < n; i++) { F.draw(); w.tick(); await sleep(g || 12); }
    w.tick();
  };
  const place = async (relics, build, cells) => {
    await settleBoard();
    F.mode = 'rush'; F.resetRun(); F.relics = relics.slice(); F.applyRelics();
    clearBoard();
    for (let r = 0; r < F.ROWS; r++) for (let c = 0; c < F.COLS; c++) F.coinCell[r][c] = 0;
    build();
    F.score = 0; F.streak = 0; F.busy = false;
    const rc = cv.getBoundingClientRect();
    const px = rc.left + 4.5 * rc.width / F.COLS, py = rc.top + 3.5 * rc.height / F.ROWS;
    cv.dispatchEvent(new PointerEvent('pointerdown', {clientX:px, clientY:py, bubbles:true}));
    cv.dispatchEvent(new PointerEvent('pointerup',   {clientX:px, clientY:py, bubbles:true}));
    const w = watch(cells || []);
    await pumpWatch(w, 120, 12);     // places into (3,4)
    await settleBoard();
    return w.seen;
  };
  const trio = col => () => {
    for (const [r, c] of [[3,5],[4,4],[4,5]]) F.grid[r][c] = col;
    F.nextColor = col; F.nextColor2 = col;
  };

  // 물렁 복숭아 — takes the ring, whatever colour it is
  const ring = [[2,3],[2,4],[2,5],[3,3]];
  const peachBuild = () => { trio(5)(); for (const [r,c] of ring) F.grid[r][c] = 6; };
  const plainRing = await place([], peachBuild, ring);
  chk('a plain peach leaves its neighbours', [...plainRing], []);
  const burstRing = await place(['peach_soft'], peachBuild, ring);
  chk('물렁 복숭아 takes the ring with it', burstRing.size, ring.length);

  // 감귤 한 접시 — orange and lemon are one colour to the chain
  const lemons = [[3,6],[4,6]];
  const citrusBuild = () => { trio(1)(); for (const [r,c] of lemons) F.grid[r][c] = 3; };
  const plainLem = await place([], citrusBuild, lemons);
  chk('lemons are not orange by default', [...plainLem], []);
  const fusedLem = await place(['citrus_plate'], citrusBuild, lemons);
  chk('감귤 한 접시 pops the lemons too', fusedLem.size, lemons.length);

  // 키위 씨앗 — the cell is not empty, it is counting down
  await place(['kiwi_seed'], trio(2));
  const seeds = [];
  for (let r = 0; r < F.ROWS; r++) for (let c = 0; c < F.COLS; c++)
    if (F.grid[r][c] === F.SEED) seeds.push([r, c]);
  chk('a popped kiwi leaves seeds', seeds.length > 0, true);
  chk('and a seed is not an empty cell',
      F.emptyCells().some(([r, c]) => F.grid[r][c] === F.SEED), false);
  // a missing seed must FAIL, not throw: a throw here aborts the suite and hides every
  // check after it
  const [sr, sc] = seeds[0] || [0, 0];
  chk('the seed starts with its full count', F.hp[sr][sc], F.SEED_TOUCHES);
  // ripen it: each touch ticks every seed down
  for (let i = 0; i < F.SEED_TOUCHES; i++) {
    const rc2 = cv.getBoundingClientRect();
    const fx = F.emptyCells()[0];
    const ex = rc2.left + (fx[1] + 0.5) * rc2.width / F.COLS;
    const ey = rc2.top + (fx[0] + 0.5) * rc2.height / F.ROWS;
    cv.dispatchEvent(new PointerEvent('pointerdown', {clientX:ex, clientY:ey, bubbles:true}));
    cv.dispatchEvent(new PointerEvent('pointerup',   {clientX:ex, clientY:ey, bubbles:true}));
    await pump(40, 12);
  }
  chk('and it grows back into a kiwi', F.grid[sr][sc], 2);

  // 바나나 군락 — converts what it did not take. Counted on NAMED cells: every turn spawns
  // fresh fruit, so a board-wide tally of bananas measures the spawner, not the relic.
  const nbrs = [[2,3],[2,4],[2,5],[3,3],[3,6]];
  const cherryNbrs = () => { trio(6)(); for (const [r, c] of nbrs) F.grid[r][c] = 0; };
  await place([], cherryNbrs);
  chk('a plain banana converts nothing', nbrs.filter(([r,c]) => F.grid[r][c] === 6), []);
  await place(['banana_grove2'], cherryNbrs);
  chk('바나나 군락 converts its neighbours',
      nbrs.filter(([r,c]) => F.grid[r][c] === 6).length >= 3, true);
  chk('and only as many as it says',
      nbrs.filter(([r,c]) => F.grid[r][c] === 6).length <= F.bananaSpread + 3, true);

  // 체리 더미 — each cherry popped raises cherries, for this stage only
  F.mode = 'rush'; F.resetRun(); F.relics = ['cherry_pile']; F.applyRelics();
  const cherry0 = F.fruitScore(0);
  await place(['cherry_pile'], trio(0));
  const cherry1 = F.fruitScore(0);
  chk('체리 더미 piles up as cherries pop', cherry1 > cherry0, true);
  F.stage = 3; F.stageScore = 99999; F.stageClear();
  await pump(20);
  chk('and the pile is a stage, not a run', F.fruitScore(0), cherry0);
  F.closeShop();

  F.relics = []; F.applyRelics(); F.resetEffects();

  // ---- the bonus zone pays what it says, and two zone-coin relics pay twice ----
  const zoneCoinsPaid = async relics => {
    F.mode = 'rush'; F.resetRun(); F.relics = relics.slice(); F.applyRelics();
    clearBoard();
    for (let r = 0; r < F.ROWS; r++) for (let c = 0; c < F.COLS; c++) F.coinCell[r][c] = 0;
    F.zoneCells.clear();
    // both payout sites: the cell we place into, and a cell the chain pops
    F.zoneCells.add(3 * F.COLS + 4);
    F.zoneCells.add(3 * F.COLS + 5);
    for (const [r, c] of [[3,5],[4,4],[4,5]]) F.grid[r][c] = 1;
    F.nextColor = 1; F.nextColor2 = 1;
    F.coins = 0; F.score = 0; F.streak = 0; F.busy = false;
    const rz = cv.getBoundingClientRect();
    const zx = rz.left + 4.5 * rz.width / F.COLS, zy = rz.top + 3.5 * rz.height / F.ROWS;
    cv.dispatchEvent(new PointerEvent('pointerdown', {clientX:zx, clientY:zy, bubbles:true}));
    cv.dispatchEvent(new PointerEvent('pointerup',   {clientX:zx, clientY:zy, bubbles:true}));
    await pump(90, 12);
    return { coins: F.coins, score: F.score };
  };
  const zNone = await zoneCoinsPaid([]);
  const zOne  = await zoneCoinsPaid(['gold_vein']);
  const zTwo  = await zoneCoinsPaid(['gold_vein', 'gold_mine']);
  chk('no zone relic, no zone coin', zNone.coins, 0);
  chk('금맥 pays inside the zone', zOne.coins > zNone.coins, true);
  chk('금맥 + 금광 pays more than 금맥 alone', zTwo.coins > zOne.coins, true);
  chk('and it pays for BOTH cells, not just one', zOne.coins >= 2, true);
  // the two payout sites are separate code: check the POPPED one on its own, or a correct
  // placed-cell payout hides a broken one
  const poppedOnly = async relics => {
    F.mode = 'rush'; F.resetRun(); F.relics = relics.slice(); F.applyRelics();
    clearBoard();
    for (let r = 0; r < F.ROWS; r++) for (let c = 0; c < F.COLS; c++) F.coinCell[r][c] = 0;
    F.zoneCells.clear(); F.zoneCells.add(3 * F.COLS + 5);   // a cell the chain pops
    for (const [r, c] of [[3,5],[4,4],[4,5]]) F.grid[r][c] = 1;
    F.nextColor = 1; F.nextColor2 = 1;
    F.coins = 0; F.busy = false;
    const rp = cv.getBoundingClientRect();
    const pxx = rp.left + 4.5 * rp.width / F.COLS, pyy = rp.top + 3.5 * rp.height / F.ROWS;
    cv.dispatchEvent(new PointerEvent('pointerdown', {clientX:pxx, clientY:pyy, bubbles:true}));
    cv.dispatchEvent(new PointerEvent('pointerup',   {clientX:pxx, clientY:pyy, bubbles:true}));
    await pump(90, 12);
    return F.coins;
  };
  const pOne = await poppedOnly(['gold_vein']);
  const pTwo = await poppedOnly(['gold_vein', 'gold_mine']);
  chk('a popped zone cell pays', pOne > 0, true);
  chk('and it stacks there too', pTwo > pOne, true);

  // 명당 scores the zone, and the ball you PLACE into it counts like anything else
  const zoneScore = async (relics, marked) => {
    F.mode = 'rush'; F.resetRun(); F.relics = relics.slice(); F.applyRelics();
    clearBoard();
    for (let r = 0; r < F.ROWS; r++) for (let c = 0; c < F.COLS; c++) F.coinCell[r][c] = 0;
    F.zoneCells.clear();
    if (marked) F.zoneCells.add(3 * F.COLS + 4);       // only the placed cell
    for (const [r, c] of [[3,5],[4,4],[4,5]]) F.grid[r][c] = 1;
    F.nextColor = 1; F.nextColor2 = 1;
    F.score = 0; F.streak = 0; F.busy = false;
    const rs = cv.getBoundingClientRect();
    const sx = rs.left + 4.5 * rs.width / F.COLS, sy = rs.top + 3.5 * rs.height / F.ROWS;
    cv.dispatchEvent(new PointerEvent('pointerdown', {clientX:sx, clientY:sy, bubbles:true}));
    cv.dispatchEvent(new PointerEvent('pointerup',   {clientX:sx, clientY:sy, bubbles:true}));
    await pump(90, 12);
    return F.score;
  };
  const sOff = await zoneScore(['hotspot'], false);
  const sOn  = await zoneScore(['hotspot'], true);
  chk('placing into the bonus zone scores more than placing outside it', sOn > sOff, true);
  F.relics = []; F.applyRelics(); F.resetEffects();

  // ---- 적립: popping a fruit has to actually raise that fruit, for good ----
  // Relics do this with a hook; traits are data and go through a channel instead, so the
  // channel has to be wired to the same pop.
  // place() resets the run, which clears traits, so the trait goes on inside the build step
  const withLedger = () => { F.traits = [{ id: 'cherry_ledger', amount: 1 }]; F.applyRelics(); trio(0)(); };
  F.mode = 'rush'; F.resetRun(); F.traits = [{ id: 'cherry_ledger', amount: 1 }]; F.applyRelics();
  const cherryBefore = F.fruitScore(0);
  await place([], withLedger);
  chk('체리 적립 raises cherry as cherries pop', F.fruitScore(0) > cherryBefore, true);
  chk('and it is banked, not derived', F.fruitStack[0] > 0, true);
  const ledgerBanked = F.fruitStack[0];
  F.applyRelics(); F.applyRelics();
  chk('so a recompute does not wipe it', F.fruitStack[0], ledgerBanked);
  chk('but the rule itself is rebuilt', F.stackOnPop[0], 1);
  // the other fruits are untouched by a cherry ledger
  chk('and only that fruit', F.fruitStack.filter((v, i) => i !== 0 && v !== 0), []);
  F.traits = []; F.applyRelics(); F.resetRun(); F.resetEffects();

  // ---- crackers: one hit, 100 points, and a whole economy on top ----
  const breakOne = async relics => {
    F.mode = 'rush'; F.resetRun(); F.relics = relics.slice(); F.applyRelics();
    clearBoard();
    for (let r = 0; r < F.ROWS; r++) for (let c = 0; c < F.COLS; c++) F.coinCell[r][c] = 0;
    F.grid[2][4] = F.CRACKER; F.hp[2][4] = 1;
    for (const [r, c] of [[3,5],[4,4],[4,5]]) F.grid[r][c] = 5;
    F.nextColor = 5; F.nextColor2 = 5;
    F.score = 0; F.streak = 0; F.coins = 0; F.busy = false;
    const rr = cv.getBoundingClientRect();
    const x = rr.left + 4.5 * rr.width / F.COLS, y = rr.top + 3.5 * rr.height / F.ROWS;
    cv.dispatchEvent(new PointerEvent('pointerdown', {clientX:x, clientY:y, bubbles:true}));
    cv.dispatchEvent(new PointerEvent('pointerup',   {clientX:x, clientY:y, bubbles:true}));
    await pump(100, 12);
    return { gone: F.grid[2][4] === -1, score: F.score, coins: F.coins };
  };
  const plainBreak = await breakOne([]);
  chk('one adjacent pop breaks a cracker', plainBreak.gone, true);
  chk('a cracker is worth its base score',
      plainBreak.score >= F.CRACKER_SCORE, true);

  const scored = await breakOne(['cracker_score']);
  chk('바삭한 한 입 adds its bonus', scored.score - plainBreak.score, 1000);
  const paid = await breakOne(['cracker_coin']);
  chk('과자 부스러기 pays coins', paid.coins, 2);
  chk('and does not pay without it', plainBreak.coins, 0);

  // the flat bonus is DERIVED: applyRelics runs again on every later purchase, and a bonus
  // that added to the accumulated score would add again each time
  F.mode = 'rush'; F.resetRun(); F.relics = ['cracker_score']; F.applyRelics();
  const v1 = F.crackerValue();
  F.applyRelics(); F.applyRelics();
  chk('the flat cracker bonus does not compound', F.crackerValue(), v1);

  // the legendary's doubling IS accumulated, and must survive a recompute
  F.mode = 'rush'; F.resetRun(); F.relics = ['cracker_king']; F.applyRelics();
  const ckBase = F.crackerValue();
  F.crackerBroken(); F.crackerBroken();
  const doubled = F.crackerValue();
  // It ADDS the base, it does not double. Doubling is an exponent, and no quota curve can
  // answer an exponent -- measured, it reached 1.1e14 a cracker by 40 breaks.
  chk('크래커 왕 adds its step per break', doubled, ckBase + 2 * F.CRACKER_KING_STEP);
  F.applyRelics();
  chk('and a recompute does not undo it', F.crackerValue(), doubled);
  chk('while it does rebuild the flat side', F.crackerBonus, 0);
  for (let i = 0; i < 38; i++) F.crackerBroken();
  const after40 = F.crackerValue();
  chk('forty breaks stays in the same universe as the quota',
      after40, F.CRACKER_SCORE + 40 * F.CRACKER_KING_STEP);
  chk('and that is far below what doubling would give',
      after40 < F.CRACKER_SCORE * Math.pow(2, 20), true);
  chk('the growth step is its own number, not the base',
      F.CRACKER_KING_STEP !== F.CRACKER_SCORE, true);
  F.resetRun();
  chk('a new run starts it over', F.crackerValue(), F.CRACKER_SCORE);

  // 가루 폭발 takes the neighbours with it
  F.mode = 'rush'; F.resetRun(); F.relics = ['crumb_blast']; F.applyRelics();
  clearBoard();
  F.grid[2][4] = F.CRACKER; F.hp[2][4] = 1;
  for (const [r, c] of [[3,5],[4,4],[4,5]]) F.grid[r][c] = 5;
  const bystanders = [[1,3],[1,4],[1,5],[2,3],[2,5]];
  for (const [r, c] of bystanders) F.grid[r][c] = 6;     // a colour nothing else touches
  F.nextColor = 5; F.nextColor2 = 5; F.busy = false;
  const r4 = cv.getBoundingClientRect();
  const x4 = r4.left + 4.5 * r4.width / F.COLS, y4 = r4.top + 3.5 * r4.height / F.ROWS;
  const wb = watch(bystanders);
  cv.dispatchEvent(new PointerEvent('pointerdown', {clientX:x4, clientY:y4, bubbles:true}));
  cv.dispatchEvent(new PointerEvent('pointerup',   {clientX:x4, clientY:y4, bubbles:true}));
  await pumpWatch(wb, 140, 12);
  chk('가루 폭발 clears the 3x3 around the cracker', wb.seen.size, bystanders.length);
  F.relics = []; F.applyRelics(); F.resetEffects();

  // ---- every way a cracker can break has to make the cracker sound ----
  // A bird eating one was silent: that path mutates the grid directly instead of going
  // through the chain, so it never reached SFX.play('cracker').
  const heard = [];
  const realPlay = F.SFX.play;
  F.SFX.play = (n, a) => { heard.push(n); return realPlay.call(F.SFX, n, a); };

  clearBoard();
  F.busy = false; F.birds.length = 0;
  F.grid[0][0] = F.CRACKER; F.hp[0][0] = 1;         // one hit and it is gone
  F.grid[7][7] = 2;
  F.birds.push({ sr: 7, sc: 7, tr: 0, tc: 0, t: 0.99, curve: 1 });
  heard.length = 0;
  await pump(30);
  chk('a bird breaking a cracker makes the cracker sound', heard.includes('cracker'), true);
  chk('and the cracker is actually gone', F.grid[0][0], -1);

  // the chain path, which did work, must keep working
  clearBoard();
  F.birds.length = 0;
  F.grid[3][3] = F.CRACKER; F.hp[3][3] = 1;
  F.grid[3][4] = 1; F.special[3][4] = 'bomb';     // blast it from next door
  heard.length = 0;
  F.tapItem(3, 4);
  await pump(80, 12);
  chk('a blast next to a cracker makes it too', heard.includes('cracker'), true);
  chk('and that cracker is gone as well', F.grid[3][3], -1);

  // a cracker CHIPPED by an adjacent colour pop is a third path again: it survives the hit, so
  // it never reaches the frontier and never reaches the bird. Give it 3 HP so it cannot be
  // confused with a cracker that broke.
  F.resetEffects();
  clearBoard();
  F.busy = false;
  F.grid[2][4] = F.CRACKER; F.hp[2][4] = 3;
  for (const [r, c] of [[3,5],[4,4],[4,5]]) F.grid[r][c] = 5;   // a cluster to set off
  F.nextColor = 5; F.nextColor2 = 5;
  const r3 = cv.getBoundingClientRect(), cw3 = r3.width / F.COLS, ch3 = r3.height / F.ROWS;
  const x3 = r3.left + 4.5 * cw3, y3 = r3.top + 3.5 * ch3;      // place into (3,4)
  heard.length = 0;
  cv.dispatchEvent(new PointerEvent('pointerdown', {clientX:x3, clientY:y3, bubbles:true}));
  cv.dispatchEvent(new PointerEvent('pointerup',   {clientX:x3, clientY:y3, bubbles:true}));
  await pump(90, 12);
  chk('a cracker merely chipped still makes the sound', heard.includes('cracker'), true);
  chk('and it survived the chip', F.grid[2][4], F.CRACKER);
  chk('but it did lose health', F.hp[2][4] < 3, true);

  // and a blast with no cracker anywhere near must not
  clearBoard();
  F.grid[3][4] = 1; F.special[3][4] = 'bomb';
  heard.length = 0;
  F.tapItem(3, 4);
  await pump(80, 12);
  chk('but a blast with no cracker near it does not', heard.includes('cracker'), false);
  F.SFX.play = realPlay;

  // the cracker sound is granular, not one filtered sweep -- a sweep only ever says "shh"
  chk('the cracker sound has alternatives to pick from', F.SFX.CRACKER_KEYS.length >= 3, true);
  chk('and the chosen one is not the old sweep', F.SFX.crackerStyle !== 'old', true);

  // ---- the swoop is paced by the clock, not by the frame rate ----
  // It used to step a fixed amount per FRAME, so it ran at double speed on a 120Hz phone and
  // read as a dart. Two pumps of the SAME wall-clock length, one with many frames and one
  // with few, have to leave the bird in the same place.
  clearBoard();
  F.busy = false;
  const flyFor = async (ms, frames) => {
    F.birds.length = 0;
    F.grid[0][0] = 1;                                    // a target, so it does not retarget
    F.birds.push({ sr: 7, sc: 7, tr: 0, tc: 0, t: 0, curve: 1 });
    const b = F.birds[0], gap = Math.max(1, Math.round(ms / frames));
    await pump(frames, gap);
    return b.t;
  };
  const many = await flyFor(400, 40);      // 40 frames over ~400ms
  const few  = await flyFor(400, 5);       //  5 frames over ~400ms
  chk('frame count does not change how far the bird gets', Math.abs(many - few) < 0.12, true);
  chk('and it does get somewhere in 400ms', many > 0.1 && many < 0.9, true);

  // the swoop is slow enough to read: 400ms must be well short of the whole flight
  chk('the swoop is not over in 400ms', many < 0.5, true);
  // the per-frame version was ~880ms at 60Hz; this is the floor below which it is a dart again
  chk('the flight is a swoop, not a dart', F.BIRD_FLY_MS >= 1000, true);

  // and it does finish, rather than hanging around forever
  F.birds.length = 0;
  F.grid[0][0] = 1;
  F.birds.push({ sr: 7, sc: 7, tr: 0, tc: 0, t: 0, curve: 1 });
  await pump(60, Math.round(F.BIRD_FLY_MS / 50));
  chk('the bird lands', F.birds.length, 0);

  // ---- bird whose target vanishes mid-flight gets one more hop ----
  // settle everything the previous phase left in flight before setting this one up, or the
  // board can be mutated out from under it and the bird finds no target
  await pump(60);
  await sleep(400);
  await pump(20);
  clearBoard();
  F.birds.length = 0;
  F.busy = false;
  F.grid[3][3] = 4; F.grid[6][6] = 5;
  F.birds.push({ sr: 6, sc: 6, tr: 0, tc: 0, t: 0.99, curve: 1 });   // target (0,0) is empty
  await pump(3);
  chk('stale target: retargeted, still flying', F.birds.length, 1);
  const b = F.birds[0];
  chk('stale target: aimed at a real cell', b && F.grid[b.tr][b.tc] !== -1, true);

  // ---- star: a PLACEMENT that sets off a star must not spawn into the constellation ----
  // (it has to be a placement -- a bare tapItem never spawns, so it cannot show the fault)
  await pump(60);
  clearBoard();
  for (let c = 0; c < 8; c++) F.grid[7][c] = 3;     // a row for the star to link
  F.grid[3][3] = 3; F.special[3][3] = 'star';       // star sits next to where we will place
  F.nextColor = 6; F.nextColor2 = 6;                // a colour with nothing to match
  F.busy = false;
  const rect = cv.getBoundingClientRect(), cw = rect.width / F.COLS, ch = rect.height / F.ROWS;
  const x = rect.left + 4.5 * cw, y = rect.top + 3.5 * ch;   // empty cell (3,4), adjacent to the star
  cv.dispatchEvent(new PointerEvent('pointerdown', {clientX:x, clientY:y, bubbles:true}));
  cv.dispatchEvent(new PointerEvent('pointerup',   {clientX:x, clientY:y, bubbles:true}));

  // Baseline is the LOW-WATER mark while the constellation is up, not the first reading:
  // the chain is still clearing cells for a few frames after the link appears, so an early
  // sample sits above the floor and would hide a spawn of the same size.
  let sawLink = false, floor = Infinity, grew = false;
  for (let i = 0; i < 200; i++) {
    F.draw();
    const filled = F.grid.flat().filter(v => v !== -1).length;
    if (F.links.length) {
      sawLink = true;
      if (filled < floor) floor = filled;
      else if (filled > floor) grew = true;          // fruit spawned under the constellation
    }
    await sleep(16);
  }
  chk('star: constellation actually ran', sawLink, true);
  chk('star: no fruit spawned mid-draw', grew, false);

  // ---- the constellation stroke is clock-paced, and a LONG one is not cut short ----
  // prog used to advance 0.19 nodes per FRAME, so the flourish ran at double speed on a
  // 120Hz phone. And the turn-end wait was a flat 1500ms, which a long path outruns -- the
  // exact situation the wait exists to prevent.
  F.resetEffects();
  clearBoard();
  const row = [];
  for (let c = 0; c < 8; c++) row.push([2, c, 0]);
  const strokeProg = async (ms, frames) => {
    F.links.length = 0;
    F.links.push({ nodes: row, color: 1, prog: 0, reached: 0, done: false });
    const L = F.links[0];
    await pump(frames, Math.max(1, Math.round(ms / frames)));
    return L.prog;
  };
  const sMany = await strokeProg(400, 40);
  const sFew  = await strokeProg(400, 5);
  chk('frame count does not change how far the stroke gets', Math.abs(sMany - sFew) < 1.2, true);
  chk('and the stroke does move', sMany > 0.5, true);
  chk('the stroke is a flourish, not a flick', F.STAR_NODE_MS >= 100, true);
  F.resetEffects();

  // a constellation long enough to outrun the old flat 1500ms wait
  await pump(20);
  clearBoard();
  const LONG = 20;
  for (let c = 0; c < 8; c++) F.grid[7][c] = 3;
  for (let c = 0; c < 8; c++) F.grid[6][c] = 3;
  for (let c = 0; c < LONG - 16; c++) F.grid[5][c] = 3;
  F.grid[3][3] = 3; F.special[3][3] = 'star';
  F.nextColor = 6; F.nextColor2 = 6;
  F.busy = false;
  const r2 = cv.getBoundingClientRect(), cw2 = r2.width / F.COLS, ch2 = r2.height / F.ROWS;
  const x2 = r2.left + 4.5 * cw2, y2 = r2.top + 3.5 * ch2;
  cv.dispatchEvent(new PointerEvent('pointerdown', {clientX:x2, clientY:y2, bubbles:true}));
  cv.dispatchEvent(new PointerEvent('pointerup',   {clientX:x2, clientY:y2, bubbles:true}));
  let sawLong = false, floor2 = Infinity, grew2 = false, nodes2 = 0;
  for (let i = 0; i < 400; i++) {
    F.draw();
    const filled = F.grid.flat().filter(v => v !== -1).length;
    if (F.links.length) {
      sawLong = true;
      nodes2 = Math.max(nodes2, F.links[0].nodes.length);
      if (filled < floor2) floor2 = filled;
      else if (filled > floor2) grew2 = true;
    }
    await sleep(16);
  }
  chk('long star: the constellation ran', sawLong, true);
  chk('long star: and it really was long', nodes2 * F.STAR_NODE_MS > 1500, true);
  chk('long star: no fruit spawned mid-draw', grew2, false);
  F.resetEffects();

  // The constellation's coins must be banked when the fruit is CLEARED, not paid out frame by
  // frame as the stroke draws. takeCoin() lifts carried coins off those cells at clear time,
  // so an interrupted stroke used to destroy them -- and the star's own cell never paid.
  F.mode = 'rush'; F.start('rush');
  for (let r = 0; r < F.ROWS; r++) for (let c = 0; c < F.COLS; c++) {
    F.grid[r][c] = (r + c) % 2 === 0 ? 2 : -1; F.special[r][c] = null; F.coinCell[r][c] = 0;
  }
  F.special[4][4] = 'star'; F.grid[4][4] = 2;
  const targets = F.grid.flat().filter(v => v === 2).length;
  F.coins = 0;
  F.tapItem(4, 4);
  for (let i = 0; i < 3; i++) { F.draw(); await sleep(16); }     // barely any animation yet
  const banked = F.coins;
  chk('star: coins are banked at once, not as the stroke draws', banked, targets);
  F.resetEffects();                                             // what a stage change does
  for (let i = 0; i < 60; i++) { F.draw(); await sleep(16); }
  chk('star: cutting the animation short loses none of them', F.coins, banked);

  // ---- the reported bug: a bird landing after the last touch still counts ----
  // BIRD_SCORE lands the quota exactly, and it arrives ~880ms after the turn ended -- later
  // than the 750ms the loss used to be scheduled at.
  await pump(40);
  F.mode = 'rush'; F.resetRun(); F.mode = 'rush'; F.running = true;
  clearBoard();
  F.birds.length = 0;
  F.grid[0][0] = 1;                       // the bird's snack
  F.grid[7][7] = 2;
  const q = F.MODES.rush.quota(1);
  F.stageScore = q - 2;                   // 2 short: exactly one bird snack
  F.touchesLeft = 0;
  F.stage = 1;
  F.birds.push({ sr: 7, sc: 7, tr: 0, tc: 0, t: 0.5, curve: 1 });
  F.busy = true;
  F.closeStage('touches');
  await pump(120, 16);
  chk('last-touch bird: not a game over', over(), false);
  chk('last-touch bird: stage advanced',  F.stage, 2);

  // and the same for a board that a bird empties a cell in
  await pump(40);
  document.getElementById('shop').classList.add('hidden');
  F.resetRun(); F.mode = 'rush'; F.running = true; F.busy = true;
  for (let r = 0; r < F.ROWS; r++) for (let c = 0; c < F.COLS; c++) F.grid[r][c] = 1;
  F.birds.length = 0;
  F.birds.push({ sr: 7, sc: 7, tr: 0, tc: 0, t: 0.5, curve: 1 });
  F.touchesLeft = 5; F.stageScore = 0;
  F.closeStage('board');
  await pump(120, 16);
  chk('bird frees a cell: not a game over', over(), false);

  document.title = 'RESULT ' + JSON.stringify({ fails, err: window.__err.slice(0, 3) });
 } catch (e) {
  document.title = 'RESULT ' + JSON.stringify({ fails: [{check:'threw', got: String(e && e.message), want:'no throw'}], err: [String(e && e.stack || e).slice(0,300)] });
 }
});
</script>"""
open('_it.html','w',encoding='utf-8').write(
    open('index.html',encoding='utf-8').read().replace('</body>', TEST + '</body>'))
out = subprocess.run(['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '--headless','--disable-gpu','--no-first-run','--window-size=430,932',
    '--virtual-time-budget=90000','--dump-dom','http://localhost:8899/_it.html?test=1'],
    capture_output=True, text=True, timeout=180).stdout
os.remove('_it.html')
m = re.search(r'RESULT (\{.*?\})</title>', out, re.S)
if not m:
    t = re.search(r'<title>(.*?)</title>', out, re.S)
    print('NO RESULT', (t.group(1)[:260] if t else ''))
    sys.exit(1)
res = json.loads(m.group(1))
print(f"items: {len(res['fails'])} fail")
if res.get('err'): print('  JS errors:', res['err'])
for f in res['fails']: print('  ', f)
print('PASS' if not res['fails'] else 'FAIL')
sys.exit(0 if not res['fails'] else 1)
