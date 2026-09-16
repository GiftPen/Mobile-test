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
// Fixed frame counts are a load-dependent bet: 'one adjacent pop breaks a cracker' failed
// twice out of eight runs while a balance sweep was using the CPU, and passed alone. Wait for
// the board to actually be idle instead, with a cap far past any real chain.
const settle = async (max = 600) => {
  for (let i = 0; i < max; i++) {
    const F = window.__fs;
    F.draw();
    if (!F.busy && !F.links.length && !F.birds.length) return true;
    await sleep(8);
  }
  return false;
};
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
  // the bomb's own flat price rides along in F.score and is NOT multiplied -- it is the item's
  // fee, not fruit -- so the ratio is taken on the fruit part alone
  const fruitPart = total => total - F.ITEM_SCORE.bomb;
  const noRelicPlain = await blastScore(false, []);
  const noRelicCoin  = await blastScore(true,  []);
  chk('without the relic, coin fruit changes nothing', noRelicCoin, noRelicPlain);
  const withPlain = await blastScore(false, ['golden_harvest']);
  const withCoin  = await blastScore(true,  ['golden_harvest']);
  chk('금빛 수확 is idle when no coin fruit was taken', withPlain, noRelicPlain);
  chk('and pays when one was', withCoin > withPlain, true);
  chk('by about half again on the fruit it scored',
      Math.abs(fruitPart(withCoin) / fruitPart(withPlain) - 1.5) < 0.02, true);
  chk('and the bomb itself charged its flat fee once',
      noRelicPlain > F.ITEM_SCORE.bomb, true);

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

  // ---- the cracker ladder has a rung at every grade ----
  // 가루 폭발 moved up to 전설 so the build is a PAIR of legendaries; that must not leave a
  // hole where 유니크 was, or the build has nothing to buy between epic and legendary.
  {
    const rungs = {};
    for (const id of Object.keys(F.RELICS)) {
      if (!F.identity(id).includes('risk')) continue;
      (rungs[F.relicTier(F.RELICS[id])] = rungs[F.relicTier(F.RELICS[id])] || []).push(id);
    }
    chk('every grade has a cracker relic',
        F.TIER_KEYS.filter(t => !(rungs[t] || []).length), []);
    // 가루 폭발 is SHELVED (commented out in index.html), so the pair-of-legendaries checks
    // that named it are off with it. The rung check above still stands: the legendary rung is
    // 크래커 왕 on its own now.
    chk('크래커 왕 is legendary', F.relicTier(F.RELICS.cracker_king), 'legend');
    chk('and the shelved one really is gone from the table',
        F.RELICS.crumb_blast === undefined, true);
  }

  // 화덕 multiplies the whole cracker value, on top of the flat bonus and the growth
  F.mode = 'rush'; F.resetRun(); F.relics = []; F.applyRelics();
  const ckPlain = F.crackerValue();
  F.relics = ['oven']; F.applyRelics();
  chk('화덕 doubles what a cracker is worth', F.crackerValue(), ckPlain * 2);
  F.relics = ['oven', 'cracker_score']; F.applyRelics();
  chk('and it multiplies the flat bonus too',
      F.crackerValue(), (F.CRACKER_SCORE + F.crackerBonus) * 2);
  F.applyRelics(); F.applyRelics();
  chk('the multiplier does not compound across recomputes',
      F.crackerValue(), (F.CRACKER_SCORE + F.crackerBonus) * 2);
  F.relics = []; F.applyRelics(); F.resetRun();

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

  // 돌복숭아 — the card says 3x3, so check the whole 3x3. The old check named four cells of
  // the eight and passed on a relic that took half a ring.
  // The group that pops is the placed (3,4) plus the trio at (3,5),(4,4),(4,5); every cell
  // within one step of ANY of those is the blast the description promises.
  const popped = [[3,4],[3,5],[4,4],[4,5]];
  const ring = [];
  for (let r = 2; r <= 5; r++) for (let c = 2; c <= 6; c++) {
    if (popped.some(([pr, pc]) => pr === r && pc === c)) continue;
    if (!popped.some(([pr, pc]) => Math.abs(pr - r) <= 1 && Math.abs(pc - c) <= 1)) continue;
    ring.push([r, c]);
  }
  const peachBuild = () => { trio(5)(); for (const [r,c] of ring) F.grid[r][c] = 6; };
  const plainRing = await place([], peachBuild, ring);
  chk('a plain peach leaves its neighbours', [...plainRing], []);
  const burstRing = await place(['peach_stone'], peachBuild, ring);
  chk('돌복숭아 takes every cell around each popped peach', burstRing.size, ring.length);
  chk('...and that is a full 3x3 per peach, not a handful of cells', ring.length >= 10, true);

  // 감귤 한 접시 — orange and lemon are one colour to the chain
  const lemons = [[3,6],[4,6]];
  const citrusBuild = () => { trio(1)(); for (const [r,c] of lemons) F.grid[r][c] = 3; };
  const plainLem = await place([], citrusBuild, lemons);
  chk('lemons are not orange by default', [...plainLem], []);
  const fusedLem = await place(['citrus_plate'], citrusBuild, lemons);
  chk('감귤 한 접시 pops the lemons too', fusedLem.size, lemons.length);

  // ---- the nine cards added to fill the empty rungs ----
  const gradesOf = tag => {
    const out = {};
    for (const id of Object.keys(F.RELICS)) {
      F.mode='rush'; F.resetRun(); F.relics=[]; F.traits=[]; F.applyRelics();
      const cats = F.relicCats(id);
      if (cats.includes(tag)) (out[F.relicTier(F.RELICS[id])] ||= []).push(id);
    }
    return out;
  };
  // 콤보 was the worst trade in the game: every card cheap, no 유니크, no 전설, dead by round 6
  const combo = gradesOf('combo');
  chk('콤보 tree now reaches every grade',
      F.TIER_KEYS.filter(t => !combo[t]), []);
  // 보드 could not even start: zoneOn() needs zoneMult > 1 or zoneCoins, and nothing under
  // 14 coins turned it on, so the first three shops had nothing to sell a board build
  F.mode='rush'; F.resetRun(); F.relics=['sweet_spot']; F.applyRelics();
  chk('명당 turns the bonus zone on by itself', F.zoneCount() > 0, true);
  chk('and it is the cheapest card that does',
      Math.min(...Object.keys(F.RELICS)
        .filter(id => { F.relics=[id]; F.applyRelics(); return F.zoneCount() > 0; })
        .map(id => F.RELICS[id].price)), F.RELICS.sweet_spot.price);

  // 무아지경 — keeps the streak through a miss. Deliberately NOT "no cap": that is 레몬 한
  // 스푼's entire card, and the two are meant to stack rather than replace each other.
  F.mode='rush'; F.resetRun(); F.relics=[]; F.traits=[]; F.applyRelics();
  // high enough that the cap is actually what is binding: 1 + 40*STREAK_STEP is well past it
  F.streak = 40;
  F.relics=['trance']; F.applyRelics();
  chk('무아지경 does not touch the cap', F.streakMult(0), F.STREAK_CAP);
  chk('and 레몬 한 스푼 is still the only card that lifts it',
      (() => { F.relics=['lemon_spoon']; F.applyRelics(); return F.streakMult(3) > F.STREAK_CAP; })(),
      true);
  clearBoard();
  F.relics=['trance']; F.applyRelics();
  F.streak = 5; F.busy = false;
  const missAt = cv.getBoundingClientRect();
  const mx = missAt.left + 1.5 * missAt.width / F.COLS, my = missAt.top + 1.5 * missAt.height / F.ROWS;
  cv.dispatchEvent(new PointerEvent('pointerdown', {clientX:mx, clientY:my, bubbles:true}));
  cv.dispatchEvent(new PointerEvent('pointerup',   {clientX:mx, clientY:my, bubbles:true}));
  await settle();
  chk('a miss no longer resets the streak', F.streak >= 5, true);
  F.relics=[]; F.applyRelics();
  clearBoard(); F.streak = 5; F.busy = false;
  cv.dispatchEvent(new PointerEvent('pointerdown', {clientX:mx, clientY:my, bubbles:true}));
  cv.dispatchEvent(new PointerEvent('pointerup',   {clientX:mx, clientY:my, bubbles:true}));
  await settle();
  chk('...and without it a miss still does', F.streak, 0);

  // 제분소 — pays a touch per cracker, but only so many a stage. 크래커 왕 drops one every
  // touch and 가루 폭발 breaks them in threes, so an uncapped version buys more touches than
  // it spends and the stage never ends.
  F.mode='rush'; F.resetRun(); F.relics=['mill']; F.applyRelics();
  F.millPaid = 0;
  const t0 = F.touchesLeft;
  F.crackerBroken();
  chk('제분소 pays a touch per cracker broken', F.touchesLeft, t0 + 1);
  for (let i = 0; i < 20; i++) F.crackerBroken();
  chk('but never more than its allowance in one stage', F.touchesLeft, t0 + F.MILL_CAP);
  F.millPaid = 0;
  F.crackerBroken();
  chk('and the allowance comes back next stage', F.touchesLeft, t0 + F.MILL_CAP + 1);
  F.relics=[]; F.applyRelics();
  const t1 = F.touchesLeft;
  F.crackerBroken();
  chk('and nothing happens without it', F.touchesLeft, t1);

  // No relic may hand the board free fruit at a stage start. 키위 묘목 planted three seeds
  // and took the strongest tree from x10 to x28 of the round 9-10 quota -- material given to
  // the leader compounds through every multiplier it already holds.
  F.mode='rush'; F.resetRun(); F.relics=[]; F.traits=[]; F.applyRelics();
  const filled = () => {
    let n = 0;
    for (let r = 0; r < F.ROWS; r++) for (let c = 0; c < F.COLS; c++)
      if (F.grid[r][c] !== -1) n++;
    return n;
  };
  const freeFruit = [];
  for (const id of Object.keys(F.RELICS)) {
    if (!F.RELICS[id].onStageStart) continue;
    F.relics = [id]; F.applyRelics(); clearBoard();
    F.notify('onStageStart', { stage: 2 });
    const got = filled();
    // 과일 바구니 says so on the card and is priced for it; anything else is a surprise
    if (got > 0 && id !== 'basket') freeFruit.push(id + ':' + got);
  }
  chk('only the card that advertises it seeds the board', freeFruit, []);
  F.mode='rush'; F.resetRun(); F.relics=[]; F.traits=[]; F.applyRelics();

  // the bonus zone has to cover enough of the board to build around
  chk('the bonus zone is a real share of the board once it is on',
      (() => { F.relics=['sweet_spot']; F.applyRelics(); return F.zoneCount(); })() >= 5, true);
  chk('...but still a minority of it',
      F.zoneCount() < F.ROWS * F.COLS / 3, true);
  F.relics=[]; F.applyRelics();

  // 금본위 — the top of the hoarding ladder: 10 coins a point, then 3, then 1
  F.mode='rush'; F.resetRun(); F.relics=[]; F.applyRelics();
  F.coins = 12;
  const bare = F.fruitScore(0);
  F.relics=['rich_eye']; F.applyRelics();  const per10 = F.fruitScore(0);
  F.relics=['midas'];    F.applyRelics();  const per3  = F.fruitScore(0);
  F.relics=['gold_standard']; F.applyRelics();
  chk('the hoarding ladder still climbs', [per10 > bare, per3 > per10, F.fruitScore(0) > per3],
      [true, true, true]);
  F.mode='rush'; F.resetRun(); F.relics=[]; F.traits=[]; F.applyRelics();

  // 바나나 밭 — a 3x3 patch that grows its own fruit on a touch clock
  F.mode = 'rush'; F.resetRun(); F.relics = []; F.traits = []; F.applyRelics();
  chk('no patch without the relic', F.bananaField, null);
  F.relics = ['banana_field']; F.applyRelics(); F.rollField();
  chk('the relic puts a patch on the board', !!F.bananaField, true);
  // a missing patch must report as the one failed check above, not throw and take the rest
  // of the suite with it
  const fld = F.bananaField || { r0: 0, c0: 0 };
  chk('the patch is 3x3 and fits on the board',
      [fld.r0 >= 0, fld.c0 >= 0, fld.r0 + 3 <= F.ROWS, fld.c0 + 3 <= F.COLS], [true,true,true,true]);
  chk('a cell just outside it is not in it', F.fieldAt(fld.r0 + 3, fld.c0), false);
  clearBoard();
  F.busy = false;
  // place away from the patch so the count, not the placement, is what fills it
  const far = [];
  for (let r = 0; r < F.ROWS && far.length < 8; r++)
    for (let c = 0; c < F.COLS && far.length < 8; c++)
      if (!F.fieldAt(r, c)) far.push([r, c]);
  const inPatch = () => {
    let n = 0;
    for (let r = fld.r0; r < fld.r0 + 3; r++)
      for (let c = fld.c0; c < fld.c0 + 3; c++) if (F.grid[r][c] === 6) n++;
    return n;
  };
  // The turn's own spawns can fill all nine cells, and then there is nowhere left to grow --
  // which made this check fail about one run in six for a reason that had nothing to do with
  // the relic. Empty the patch before each touch so the only thing that can put a banana in
  // it is the patch itself.
  const clearPatch = () => {
    for (let r = fld.r0; r < fld.r0 + 3; r++)
      for (let c = fld.c0; c < fld.c0 + 3; c++) { F.grid[r][c] = -1; F.special[r][c] = null; }
  };
  const rcF = cv.getBoundingClientRect();
  let grownInPatch = 0, planted = 0;
  // A tap on a cell the turn's spawns have since filled does nothing and does not advance the
  // touch count, so counting TAPS instead of PLANTS could miss the one touch that was a
  // multiple of FIELD_EVERY. Clear the target first and confirm the touch landed.
  for (let tries = 0; tries < 12 && planted < F.FIELD_EVERY; tries++) {
    clearPatch();
    const [r, c] = far[tries % far.length];
    F.grid[r][c] = -1; F.special[r][c] = null;
    const was = F.touchCount;
    const fx = rcF.left + (c + 0.5) * rcF.width / F.COLS;
    const fy = rcF.top + (r + 0.5) * rcF.height / F.ROWS;
    cv.dispatchEvent(new PointerEvent('pointerdown', {clientX:fx, clientY:fy, bubbles:true}));
    cv.dispatchEvent(new PointerEvent('pointerup',   {clientX:fx, clientY:fy, bubbles:true}));
    await settle();
    if (F.touchCount > was) planted++;
    grownInPatch += inPatch();
  }
  chk('the touches the patch is clocked on actually happened', planted, F.FIELD_EVERY);
  chk("a banana grows in the patch on the clock", grownInPatch > 0, true);
  // and it is DERIVED: dropping the relic takes the patch away on the next roll
  F.relics = []; F.applyRelics(); F.rollField();
  chk('drop the relic and the patch goes', F.bananaField, null);
  chk('and the channel does not linger', F.fieldOn, false);
  F.mode = 'rush'; F.resetRun(); F.relics = []; F.traits = []; F.applyRelics();

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
  chk('the revived kiwi is marked as such', F.sprouted[sr][sc], 1);

  // ...and that is the END of the chain. The loop used to be endless: kiwi -> seed -> kiwi ->
  // seed, with the per-pop ledgers raising the value of each one, which put an assembled kiwi
  // build at thirty times any other fruit. One revival per kiwi makes the total finite.
  F.mode = 'rush'; F.resetRun(); F.relics = ['kiwi_seed']; F.applyRelics();
  F.busy = false;
  clearBoard();
  for (let r = 0; r < F.ROWS; r++) for (let c = 0; c < F.COLS; c++) F.sprouted[r][c] = 0;
  F.grid[4][4] = 2; F.sprouted[4][4] = 1;        // a kiwi that came from a seed
  F.grid[4][5] = 2; F.grid[5][4] = 2;            // ...and two ordinary ones beside it
  F.nextColor = 2; F.nextColor2 = 2;
  const rc3 = cv.getBoundingClientRect();
  const px3 = rc3.left + 5.5 * rc3.width / F.COLS, py3 = rc3.top + 5.5 * rc3.height / F.ROWS;
  cv.dispatchEvent(new PointerEvent('pointerdown', {clientX:px3, clientY:py3, bubbles:true}));
  cv.dispatchEvent(new PointerEvent('pointerup',   {clientX:px3, clientY:py3, bubbles:true}));
  await settle();
  chk('a kiwi grown from a seed leaves no second seed', F.grid[4][4] === F.SEED, false);
  chk('while an ordinary kiwi beside it still does', F.grid[4][5], F.SEED);
  chk('and the mark is cleared with the cell', F.sprouted[4][4], 0);

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

  // the ball you PLACE pops with the group, and is counted for the score and the item
  // threshold -- so a ledger that says "터뜨릴 때마다" has to count it too. It banked 3 of 4.
  F.mode = 'rush'; F.resetRun(); F.relics = []; F.traits = []; F.applyRelics();
  F.pickTrait('lemon_ledger'); F.applyRelics();
  clearBoard();
  F.fruitStack[3] = 0; F.busy = false;
  for (const [r, c] of [[3,5],[4,4],[4,5]]) F.grid[r][c] = 3;
  F.nextColor = 3; F.nextColor2 = 3;
  const rcL = cv.getBoundingClientRect();
  const lx = rcL.left + 4.5 * rcL.width / F.COLS, ly = rcL.top + 3.5 * rcL.height / F.ROWS;
  cv.dispatchEvent(new PointerEvent('pointerdown', {clientX:lx, clientY:ly, bubbles:true}));
  cv.dispatchEvent(new PointerEvent('pointerup',   {clientX:lx, clientY:ly, bubbles:true}));
  await settle();
  chk('four lemons popped bank four, not three', F.fruitStack[3], 4);
  F.traits = []; F.applyRelics(); F.resetRun(); F.resetEffects();
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
    await settle();
    // NOT "the cell is empty": the turn's spawn can drop a fresh fruit into the hole the
    // cracker left, which failed this check about one run in eight for eight months of
    // suspecting the engine. What matters is that the cracker is not there any more.
    return { gone: F.grid[2][4] !== F.CRACKER, score: F.score, coins: F.coins,
             why: { at24: F.grid[2][4], hp24: F.hp[2][4], placed: F.grid[3][4],
                    n35: F.grid[3][5], n44: F.grid[4][4], n45: F.grid[4][5],
                    busy: F.busy, touches: F.touchesLeft } };
  };
  const plainBreak = await breakOne([]);
  chk('one adjacent pop breaks a cracker',
      plainBreak.gone ? true : JSON.stringify(plainBreak.why), true);
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
  F.resetRun();
  chk('a new run starts it over', F.crackerValue(), F.CRACKER_SCORE);

  // ---- consumables: marked as temporary, and available at every grade ----
  const temp = Object.keys(F.RELICS).filter(id => F.RELICS[id].life);
  const tiersWithTemp = [...new Set(temp.map(id => F.relicTier(F.RELICS[id])))].sort();
  // the pool used to stop at 고급, so the "spend it now" decision vanished after round 2
  chk('every grade has a consumable',
      F.TIER_KEYS.filter(t => !tiersWithTemp.includes(t)), []);
  chk('and there are enough of them to choose between', temp.length >= 12, true);

  // it has to actually run out, and give its channel back when it does
  F.mode = 'rush'; F.resetRun(); F.relics = []; F.traits = []; F.applyRelics();
  const baseTouch = F.stageTouches();
  F.relics = ['teapot']; F.relicLife = { teapot: 2 }; F.applyRelics();
  chk('a consumable works while it lasts', F.stageTouches(), baseTouch + 5);
  F.tickRelicLife('stages');
  chk('and still works with one left', F.stageTouches(), baseTouch + 5);
  F.tickRelicLife('stages');
  chk('then expires and hands the channel back', F.stageTouches(), baseTouch);
  chk('and leaves the shelf', F.relics.includes('teapot'), false);

  // the shop card marks it where the GRADE is, not only in the price line
  F.mode = 'rush'; F.resetRun(); F.relics = []; F.traits = []; F.applyRelics();
  F.shopOffers = ['teapot', 'pinch']; F.shopSold = new Set(); F.coins = 99;
  F.renderShop();
  const cards = [...document.querySelectorAll('#sh-offers .offer')];
  const marked = cards.map(c => !!c.querySelector('.of-temp'));
  chk('the temporary one is marked on its grade, the permanent one is not', marked, [true, false]);

  // ---- selling asks, and the question can be answered "no" ----
  F.relics = ['pinch']; F.applyRelics();
  $('shop').classList.remove('hidden');
  F.dropArmed = null;
  F.openInfo('relics');
  const sellBtn = () => document.querySelector('#info-body .inf-drop:not(.inf-cancel)');
  // a missing button is a FAILURE, not a throw: clicking null aborts the whole suite and the
  // single 'threw' entry then hides every other check that was going to report
  const press = (el, what) => { if (el) el.click();
    else fails.push({ check: what, got: 'no such button', want: 'a button to press' }); };
  press(sellBtn(), 'sell button exists');
  chk('one tap arms the question', F.dropArmed, 'pinch');
  chk('and does not sell yet', F.relics.slice(), ['pinch']);
  const cancel = document.querySelector('#info-body .inf-cancel');
  chk('an armed question offers a way out', !!cancel, true);
  press(cancel, 'cancel button exists');
  chk('cancel disarms it', F.dropArmed, null);
  chk('and the relic is still there', F.relics.slice(), ['pinch']);
  press(sellBtn(), 'sell button after cancel');
  press(sellBtn(), 'sell button second tap');
  chk('two taps still sell it', F.relics.slice(), []);
  $('shop').classList.add('hidden');
  F.closeInfo ? F.closeInfo() : $('info').classList.add('hidden');

  // ---- the trait screen says what you can afford ----
  F.mode = 'rush'; F.resetRun(); F.relics = []; F.traits = []; F.applyRelics();
  F.coins = 47;
  F.traitOffers = F.rollTraits();
  F.renderTraits();
  chk('the trait screen shows the balance, not just the reroll price',
      $('tr-coin').textContent, '47');

  // ---- a multiplier is LIVE, not a snapshot taken the moment you bought it ----
  // The question: if you have already built a pile, does buying x2 double the pile, or only
  // what comes after? Every multiplier is read at use time -- crackerValue() on each break,
  // fruitScore() on each pop -- so it must be both retroactive and order-independent.
  const freshRun = () => { F.mode = 'rush'; F.resetRun(); F.relics = []; F.traits = []; F.applyRelics(); };
  const buy = id => { F.relics = F.relics.concat([id]); F.applyRelics(); };
  const breakN = n => { for (let i = 0; i < n; i++) F.crackerBroken(); };
  const ck20 = F.CRACKER_SCORE + 20 * F.CRACKER_KING_STEP;

  freshRun(); buy('cracker_king'); buy('oven'); breakN(20);
  chk('화덕: 먼저 사면 이후 부순 것에 배율', F.crackerValue(), ck20 * 2);
  freshRun(); buy('cracker_king'); breakN(20); buy('oven');
  chk('화덕: 나중에 사면 쌓아둔 더미에 소급', F.crackerValue(), ck20 * 2);
  const held = F.crackerValue(); breakN(1);
  chk('화덕 보유 중 1개 더 부순 증가분도 배율',
      F.crackerValue() - held, 2 * F.CRACKER_KING_STEP);

  // the same question on the fruit side, where the pile is fruitStack rather than crackerScore
  const pile40 = () => { for (let i = 0; i < 40; i++) F.fruitStack[0] += 1; };
  freshRun(); pile40(); const cherryBare = F.fruitScore(0);
  freshRun(); buy('cherry_crown'); pile40(); const crownFirst = F.fruitScore(0);
  freshRun(); pile40(); buy('cherry_crown');
  chk('체리 왕관: 사는 순서가 결과를 바꾸지 않는다', F.fruitScore(0), crownFirst);
  // Read the multipliers off the cards rather than pinning 2.5 and 2 here: both have already
  // been retuned once, and a test that has to be edited every time a number moves is a test
  // people edit without reading.
  // desc is a resolved STRING at runtime -- the () => d(...) thunks are unwrapped when the
  // language pack is applied -- so read it, do not call it
  const multOf = id => parseFloat((String(F.RELICS[id].desc).match(/[×x]\s*([\d.]+)/) || [])[1]);
  const crownMult = multOf('cherry_crown'), hornMult = multOf('cornucopia');
  chk('체리 왕관의 배율을 카드에서 읽을 수 있다', [crownMult > 1, hornMult > 1], [true, true]);
  chk('...그리고 쌓아둔 더미까지 곱한다', crownFirst, Math.round(cherryBare * crownMult));
  freshRun(); pile40(); buy('cherry_crown'); buy('cornucopia');
  // two multipliers must land on their PRODUCT -- not squared, and not one overwriting the other
  chk('배율 둘은 곱해진다 (제곱도 덮어쓰기도 아님)', F.fruitScore(0), Math.round(cherryBare * crownMult * hornMult));

  // and the sweep: EVERY relic, against every kind of pile, bought before vs after. This is
  // the standing guard -- a relic that writes ACCUMULATED state from apply() instead of its
  // own derived channel makes the two orders disagree, which is the trap that has now bitten
  // three separate times (fruitBoost, crackerScore, stackOnPop).
  const PILES = [
    { name: '크래커더미', pre: 'cracker_king', build: () => breakN(20), read: () => F.crackerValue() },
    { name: '체리더미',   build: pile40,                                read: () => F.fruitScore(0) },
    // += rather than = so a relic that hands out coins on pickup is not scored as a flip
    { name: '보유코인',   build: () => { F.coins += 200; },             read: () => F.fruitScore(0) },
  ];
  const flipped = [];
  for (const P of PILES) {
    for (const id of Object.keys(F.RELICS)) {
      freshRun(); if (P.pre) buy(P.pre); buy(id); P.build(); const first = P.read();
      freshRun(); if (P.pre) buy(P.pre); P.build(); buy(id); const last = P.read();
      if (first !== last) flipped.push(`${P.name}/${id} ${first}!=${last}`);
    }
  }
  chk('유물 구매 순서가 누적 더미의 값을 바꾸지 않는다', flipped.slice(0, 8), []);

  // 가루 폭발 SHELVED — its 3x3 checks are out with the relic; everything below is the
  // item and cracker-payment work, which is live and was switched off with it by mistake.

  // ---- every coin you spend counts as spent ----
  // 탕진 pays per coin spent, and the trait reroll counted while the SHOP reroll did not --
  // the same act, charged the same way, on two different ledgers.
  F.mode = 'rush'; F.resetRun(); F.relics = []; F.traits = []; F.applyRelics();
  F.coins = 999; F.coinsSpent = 0;
  F.shopOffers = ['pinch']; F.shopSold = new Set();
  F.buyRelic('pinch');
  const afterBuy = F.coinsSpent;
  chk('유물을 사면 쓴 코인에 잡힌다', afterBuy > 0, true);
  F.openShop();                      // a fresh shelf, so the reroll button is live
  const beforeRoll = F.coinsSpent, coinsBefore = F.coins;
  document.getElementById('sh-reroll').click();
  chk('상점 리롤도 코인을 쓴다', F.coins < coinsBefore, true);
  chk('...그리고 쓴 코인에 잡힌다', F.coinsSpent - beforeRoll, coinsBefore - F.coins);
  F.closeShop();
  F.mode = 'rush'; F.resetRun(); F.relics = []; F.traits = []; F.applyRelics();

  // ---- buying a relic and selling it again must leave nothing behind ----
  // Reported from a real run: 지구력 raised the stage's touches, was sold in the same shop,
  // and the touches stayed. Buying writes to live state (touchesLeft, ROWS) that applyRelics
  // does not own, so anything the purchase pushed has to be pulled back by the sale.
  F.mode = 'rush'; F.resetRun(); F.relics = []; F.traits = []; F.applyRelics();
  $('shop').classList.remove('hidden');
  const snapshot = () => [F.stageTouches(), F.touchesLeft, F.ROWS, F.relicCap(), F.shelfSize(),
                          F.spawnCount(0), F.bombRadius(), F.STREAK_CAP, F.crackerValue(),
                          F.fruitScore(0), F.fruitScore(6), F.zoneCount(), F.coins];
  const churn = [];
  for (const id of Object.keys(F.RELICS)) {
    F.mode = 'rush'; F.resetRun(); F.relics = []; F.traits = []; F.applyRelics();
    F.coins = 999; F.shopOffers = [id]; F.shopSold = new Set();
    const before = snapshot();
    F.buyRelic(id);
    if (!F.relics.includes(id)) continue;          // could not afford / no room: nothing to test
    F.dropArmed = null;
    F.discardRelic(0); F.discardRelic(0);          // arm, then confirm
    const after = snapshot();
    // coins are SUPPOSED to differ -- you get half back, that is the sale
    const diff = before.map((v, k) => (k === before.length - 1 ? null : (v === after[k] ? null : k)))
                       .filter(k => k !== null);
    if (F.relics.includes(id)) churn.push(id + ' (팔리지 않음)');
    else if (diff.length) churn.push(id + ' 남은칸:' + diff.join(','));
  }
  chk('샀다 되팔면 모든 파생 수치가 제자리로 돌아온다', churn.slice(0, 8), []);
  $('shop').classList.add('hidden');
  F.mode = 'rush'; F.resetRun(); F.relics = []; F.traits = []; F.applyRelics();

  // ---- 참새떼: a bird's meal feeds that fruit for the rest of the run ----
  // The card used to be three birds and nothing else, which measured BELOW the baseline: a
  // bird eats a fruit for a flat 20 and that is less than the fruit was worth, so more birds
  // meant less score. Now each mouthful banks.
  const birdEat = async (relics) => {
    F.mode = 'rush'; F.resetRun(); F.relics = relics.slice(); F.traits = []; F.applyRelics();
    clearBoard();
    for (let r = 0; r < F.ROWS; r++) for (let c = 0; c < F.COLS; c++) F.coinCell[r][c] = 0;
    F.fruitStack[4] = 0; F.score = 0; F.busy = false;
    F.grid[2][2] = 4;                               // one grape for the bird
    F.grid[7][7] = 1;
    F.birds.push({ sr: 7, sc: 7, tr: 2, tc: 2, t: 0.5, curve: 1 });
    await settle();
    return { eaten: F.grid[2][2] === -1, banked: F.fruitStack[4], score: F.score };
  };
  const plainBird = await birdEat([]);
  chk('a plain bird eats the fruit', plainBird.eaten, true);
  chk('and banks nothing', plainBird.banked, 0);
  chk('paying its flat fee', plainBird.score, F.BIRD_SCORE);
  const flockBird = await birdEat(['flock']);
  chk('참새떼: the fruit it ate is worth more for good', flockBird.banked, F.birdFeed);
  chk('...and that is a real number', F.birdFeed > 0, true);
  chk('the flat fee is unchanged', flockBird.score, F.BIRD_SCORE);
  // derived, not accumulated: recomputing must not feed it again
  const fedWas = F.fruitStack[4];
  F.applyRelics(); F.applyRelics();
  chk('a recompute does not feed it again', F.fruitStack[4], fedWas);
  F.relics = []; F.applyRelics();
  chk('and dropping the relic turns it off', F.birdFeed, 0);
  F.mode = 'rush'; F.resetRun(); F.relics = []; F.traits = []; F.applyRelics();

  // ---- an item is a tool, not a fruit ----
  // It used to be worth whatever fruit it was drawn on -- invisible under the art, so popping
  // "one lemon" with a line that happened to sit on a lemon banked two, with nothing on screen
  // to explain it. It pays its own flat price now and the fruit under it scores nothing.
  const itemOn = async (sp, fruit) => {
    F.mode = 'rush'; F.resetRun(); F.relics = []; F.traits = [];
    F.applyRelics(); F.pickTrait('lemon_ledger'); F.applyRelics();
    clearBoard();
    for (let r = 0; r < F.ROWS; r++) for (let c = 0; c < F.COLS; c++) F.coinCell[r][c] = 0;
    F.fruitStack[3] = 0; F.score = 0; F.busy = false;
    F.grid[4][4] = fruit; F.special[4][4] = sp;
    const b = cv.getBoundingClientRect();
    const x = b.left + 4.5 * b.width / F.COLS, y = b.top + 4.5 * b.height / F.ROWS;
    cv.dispatchEvent(new PointerEvent('pointerdown', {clientX:x, clientY:y, bubbles:true}));
    cv.dispatchEvent(new PointerEvent('pointerup',   {clientX:x, clientY:y, bubbles:true}));
    await settle();
    return { score: F.score, banked: F.fruitStack[3] };
  };
  for (const sp of ['bird', 'lineH', 'lineV', 'bomb', 'star']) {
    const onLemon = await itemOn(sp, 3);
    chk(`${sp}: the fruit it rides banks nothing`, onLemon.banked, 0);
    chk(`${sp}: it pays its own score`, onLemon.score >= F.ITEM_SCORE[sp], true);
  }
  // and the prices differ -- a star is not a sparrow
  chk('the item prices are graded, not one number',
      [F.ITEM_SCORE.bird < F.ITEM_SCORE.lineH, F.ITEM_SCORE.lineH < F.ITEM_SCORE.bomb,
       F.ITEM_SCORE.bomb < F.ITEM_SCORE.star], [true, true, true]);
  // an item on a lemon and the same item on a grape are worth exactly the same now
  const onGrape = await itemOn('lineH', 4), onLemon2 = await itemOn('lineH', 3);
  chk('what it rides on does not change what it pays', onGrape.score, onLemon2.score);
  F.mode = 'rush'; F.resetRun(); F.relics = []; F.traits = []; F.applyRelics();

  // ---- ...and every way a cracker can break has to PAY ----
  // The sound was wired through all of these; the economy was not. A cracker swallowed whole
  // by a bomb, a line, a star or 가루 폭발's own 3x3 went to the frontier and never touched
  // hitCrackers, so it died for 12 points against the 311 the same cracker pays when a
  // neighbour chips it -- no 소금통 coin and no 크래커 왕 growth either.
  const breakBy = async (how) => {
    F.mode = 'rush'; F.resetRun();
    F.relics = ['cracker_king', 'cracker_coin']; F.traits = []; F.applyRelics();
    clearBoard();
    for (let r = 0; r < F.ROWS; r++) for (let c = 0; c < F.COLS; c++) F.coinCell[r][c] = 0;
    F.score = 0; F.coins = 0; F.busy = false;
    const worth = F.crackerValue();
    F.grid[2][2] = F.CRACKER; F.hp[2][2] = 1;
    if (how === 'bird') {
      F.grid[7][7] = 1;
      F.birds.push({ sr: 7, sc: 7, tr: 2, tc: 2, t: 0.5, curve: 1 });
      await settle();
    } else if (how === 'neighbour') {
      // the one path that always worked: an adjacent colour pop chips it
      clearBoard();
      F.score = 0; F.coins = 0;
      F.grid[2][4] = F.CRACKER; F.hp[2][4] = 1;
      for (const [r, c] of [[3,5],[4,4],[4,5]]) F.grid[r][c] = 5;
      F.nextColor = 5; F.nextColor2 = 5;
      const b1 = cv.getBoundingClientRect();
      const x1 = b1.left + 4.5 * b1.width / F.COLS, y1 = b1.top + 3.5 * b1.height / F.ROWS;
      cv.dispatchEvent(new PointerEvent('pointerdown', {clientX:x1, clientY:y1, bubbles:true}));
      cv.dispatchEvent(new PointerEvent('pointerup',   {clientX:x1, clientY:y1, bubbles:true}));
      await settle();
      // not "the cell is empty": the turn's spawn can drop a fresh fruit into the hole
      return { gone: F.grid[2][4] !== F.CRACKER, paid: F.score >= worth, coins: F.coins, grew: F.crackerValue() > worth };
    } else {
      F.grid[4][4] = 0; F.special[4][4] = how;      // bomb / lineH / lineV / star on (4,4)
      const b2 = cv.getBoundingClientRect();
      const x2 = b2.left + 4.5 * b2.width / F.COLS, y2 = b2.top + 4.5 * b2.height / F.ROWS;
      if (how === 'lineH') { F.grid[4][4] = 0; F.grid[2][2] = -1; F.grid[4][1] = F.CRACKER; F.hp[4][1] = 1; }
      if (how === 'lineV') { F.grid[4][4] = 0; F.grid[2][2] = -1; F.grid[1][4] = F.CRACKER; F.hp[1][4] = 1; }
      cv.dispatchEvent(new PointerEvent('pointerdown', {clientX:x2, clientY:y2, bubbles:true}));
      cv.dispatchEvent(new PointerEvent('pointerup',   {clientX:x2, clientY:y2, bubbles:true}));
      await settle();
      const at = how === 'lineH' ? [4,1] : how === 'lineV' ? [1,4] : [2,2];
      return { gone: F.grid[at[0]][at[1]] !== F.CRACKER, paid: F.score >= worth,
               coins: F.coins, grew: F.crackerValue() > worth };
    }
    return { gone: F.grid[2][2] !== F.CRACKER, paid: F.score >= worth,
             coins: F.coins, grew: F.crackerValue() > worth };
  };
  for (const how of ['neighbour', 'bomb', 'lineH', 'lineV', 'bird']) {
    const r = await breakBy(how);
    chk(`${how}: the cracker is gone`, r.gone, true);
    chk(`${how}: it pays its score`, r.paid, true);
    chk(`${how}: 소금통 pays its coins`, r.coins >= 2, true);
    chk(`${how}: 크래커 왕 grows on it`, r.grew, true);
  }

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
# The step and the base are separate knobs on purpose, and tuning made them equal (both 100),
# so comparing the two VALUES no longer says anything. Read the source instead: what matters is
# that the growth is driven by its own constant and cannot be re-tuned by moving the base.
src = open('index.html', encoding='utf-8').read()
body = re.search(r'function crackerBroken\(\)\s*\{(.*?)\}', src, re.S)
if not body:
    res['fails'].append({'check': 'crackerBroken exists', 'got': None, 'want': 'a function'})
elif 'CRACKER_KING_STEP' not in body.group(1) or 'CRACKER_SCORE' in body.group(1):
    res['fails'].append({'check': 'the growth step is its own constant, not the base',
                         'got': body.group(1).strip()[:70], 'want': 'uses CRACKER_KING_STEP'})

print(f"items: {len(res['fails'])} fail")
if res.get('err'): print('  JS errors:', res['err'])
for f in res['fails']: print('  ', f)
print('PASS' if not res['fails'] else 'FAIL')
sys.exit(0 if not res['fails'] else 1)
