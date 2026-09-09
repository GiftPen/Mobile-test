"""Headless check for the rule chokepoints in index.html.

Run:  python3 -m http.server 8899 &   then   python3 tools/rules-test.py

Asserts the scoring formula against a reference copy of the pre-chokepoint inline
maths, and that pickColor() stays uniform while every colorWeight is 1. Uses the
?test=1 hook in index.html.

End-to-end replay is NOT usable here: draw() consumes Math.random() for screen-shake
on every frame, so a seeded playthrough desyncs with frame timing (verified: the same
revision scored 780 and 687 on two runs).
"""
import subprocess, re, os, json, sys
os.chdir('/Users/kimjaehoon/Mobile-test')
TEST = """<script>
window.addEventListener('load', () => setTimeout(() => {
  const F = window.__fs;
  if (!F) { document.title = 'RESULT {"fatal":"no test hook"}'; return; }
  const fails = []; let n = 0;
  F.score = 0;                        // score is undefined until start(); seed it
  // reference = the inline formula as it stood BEFORE the addScore/scorePop chokepoint
  const refStreak = s => Math.min(1 + s * 0.2, 2.0);
  const refPop = (base, cleared, s) => Math.round(base * (1 + (cleared - 1) * 0.15) * refStreak(s));
  for (let s = 0; s <= 12; s++) {
    F.streak = s;
    for (let base = 0; base <= 60; base++) {
      for (let cleared = 1; cleared <= 16; cleared++) {
        F.score = 0;
        const before = F.score;
        F.scorePop(base, cleared);
        const got = F.score - before, want = refPop(base, cleared, s);
        n++;
        if (got !== want && fails.length < 8) fails.push({s, base, cleared, got, want});
      }
    }
  }
  // fruitScore must equal the old raw FRUIT_POINTS while every multiplier is 1.0
  const fsFails = [];
  for (let c = 0; c < 7; c++)
    if (F.fruitScore(c) !== F.FRUIT_POINTS[c]) fsFails.push({c, got: F.fruitScore(c), want: F.FRUIT_POINTS[c]});
  // pickColor must stay uniform while every weight is 1
  const hist = new Array(7).fill(0);
  F.score = 0;                       // score 0 -> the 4 starting colours are active
  for (let i = 0; i < 70000; i++) hist[F.pickColor()]++;
  // ---- mode rules ----
  // arcade knobs must still match the formulas they were hardcoded as before the table
  const modeFails = [];
  const refColors  = m => Math.min(7, 4 + Math.floor((m + 1) / 3));
  const refSpawns  = m => Math.min(4, 1 + Math.floor(m / 3));
  const refBrickHp = m => Math.min(3, Math.floor((m + 2) / 3));
  const A = F.MODES.arcade, R = F.MODES.rush;
  for (let m = 0; m <= 40; m++) {
    if (A.colors(m)  !== refColors(m))  modeFails.push({m, knob:'colors',  got:A.colors(m),  want:refColors(m)});
    if (A.spawns(m)  !== refSpawns(m))  modeFails.push({m, knob:'spawns',  got:A.spawns(m),  want:refSpawns(m)});
    if (A.brickHp(m) !== refBrickHp(m)) modeFails.push({m, knob:'brickHp', got:A.brickHp(m), want:refBrickHp(m)});
  }
  // rush: 7 colours from turn one, flat spawn, no score-driven bricks (design doc 10-4)
  for (let m = 0; m <= 40; m++) {
    if (R.colors(m)  !== 7) modeFails.push({m, knob:'rush.colors',  got:R.colors(m),  want:7});
    if (R.spawns(m)  !== F.RUSH_SPAWNS) modeFails.push({m, knob:'rush.spawns', got:R.spawns(m), want:F.RUSH_SPAWNS});
    if (R.brickHp(m) !== 0) modeFails.push({m, knob:'rush.brickHp', got:R.brickHp(m), want:0});
  }
  if (F.computeMaxLevel() !== 10) modeFails.push({knob:'MAX_LEVEL', got:F.computeMaxLevel(), want:10});
  // Verify the SHAPE of the quota curve, not the tuning: these numbers are meant to be
  // changed by feel, and a test that pins them just has to be edited every time.
  if (F.rushQuota(1) !== F.RUSH_QUOTA_1)
    modeFails.push({knob:'quota starts at RUSH_QUOTA_1', got:F.rushQuota(1), want:F.RUSH_QUOTA_1});
  for (let st = 2; st <= 12; st++) {
    const r = Math.floor((st-1)/F.STAGES_PER_ROUND), sub = (st-1)%F.STAGES_PER_ROUND;
    const want = Math.round(F.RUSH_QUOTA_1 * Math.pow(F.roundSpan(), r) * Math.pow(F.RUSH_STAGE_MUL, sub));
    if (F.rushQuota(st) !== want) modeFails.push({knob:'quota s'+st, got:F.rushQuota(st), want});
    if (F.rushQuota(st) <= F.rushQuota(st-1))
      modeFails.push({knob:'quota rises s'+st, got:F.rushQuota(st), want:'> '+F.rushQuota(st-1)});
  }
  // rounds are a display + pacing layer over the flat stage counter
  [[1,'1-1'],[2,'1-2'],[3,'1-3'],[4,'2-1'],[6,'2-3'],[7,'3-1'],[12,'4-3']].forEach(([st,want]) => {
    if (F.stageLabel(st) !== want) modeFails.push({knob:'label '+st, got:F.stageLabel(st), want});
  });
  // traits fire only when a round has just ended: entering 2-1, 3-1, 4-1 …
  for (let st = 1; st <= 13; st++) {
    const fires = st > 1 && (st - 1) % F.STAGES_PER_ROUND === 0;
    const want = st > 1 && F.stageLabel(st).endsWith('-1');
    if (fires !== want) modeFails.push({knob:'trait trigger at '+F.stageLabel(st), got:fires, want});
  }
  if (F.MODES.rush.startBuds !== F.RUSH_BUDS)
    modeFails.push({knob:'rush startBuds', got:F.MODES.rush.startBuds, want:F.RUSH_BUDS});
  if (F.MODES.rush.touches !== F.RUSH_TOUCHES) modeFails.push({knob:'rush touches', got:F.MODES.rush.touches, want:F.RUSH_TOUCHES});
  if (F.MODES.arcade.touchBudget !== false) modeFails.push({knob:'arcade has no budget', got:true, want:false});
  // the live knobs must follow the active mode
  F.mode = 'rush';
  if (F.activeColors(0) !== 7) modeFails.push({knob:'live colours in rush', got:F.activeColors(0), want:7});
  if (F.brickHpLevel(9) !== 0) modeFails.push({knob:'live bricks in rush', got:F.brickHpLevel(9), want:0});
  F.mode = 'arcade';
  if (F.activeColors(0) !== 4) modeFails.push({knob:'live colours in arcade', got:F.activeColors(0), want:4});

  // ---- spawn odds: real percentages that always total 100 ----
  const oddsFails = [];
  const near = (a, b, tol) => Math.abs(a - b) <= tol;
  const ochk = (c, got, want, tol) => { if (!near(got, want, tol === undefined ? 0.01 : tol))
                                          oddsFails.push({case: c, got: +got.toFixed(3), want}); };
  F.resetRun(); F.mode = 'rush';
  let p = F.colorOdds();
  ochk('rush: 7 colours', p.length, 7, 0);
  ochk('rush: totals 100', p.reduce((a, b) => a + b, 0), 100);
  for (let i = 0; i < 7; i++) ochk('rush: base slot ' + i, p[i], F.BASE_ODDS[i]);

  F.oddsMult = [0,0,0,0,0,0,1];                  // the banana relic: one more banana's worth
  p = F.colorOdds();
  ochk('boost: totals 100', p.reduce((a, b) => a + b, 0), 100);
  ochk('boost: banana 6 -> 12', p[6], 12);
  // the other six pay for it in proportion: they shared 94, now share 88
  for (let i = 0; i < 6; i++) ochk('boost: slot ' + i + ' shrinks', p[i], F.BASE_ODDS[i] * 88 / 94);

  F.oddsMult = [0,0,0,0,0,0,0];
  F.mode = 'arcade'; F.score = 0;
  p = F.colorOdds();
  ochk('arcade: still uniform', Math.max(...p) - Math.min(...p), 0);
  ochk('arcade: totals 100', p.reduce((a, b) => a + b, 0), 100);

  // what pickColor actually rolls has to match what colorOdds claims
  F.mode = 'rush'; F.oddsMult = [0,0,0,0,0,0,1];
  const want2 = F.colorOdds(), hist2 = new Array(7).fill(0), N = 120000;
  for (let i = 0; i < N; i++) hist2[F.pickColor()]++;
  for (let i = 0; i < 7; i++) ochk('rolled slot ' + i + ' matches', hist2[i] / N * 100, want2[i], 0.6);
  F.oddsMult = [0,0,0,0,0,0,0]; F.mode = 'arcade'; F.resetRun();

  // ---- relic hooks ----
  const relicFails = [];
  const chk = (c, got, want) => { if (JSON.stringify(got) !== JSON.stringify(want))
                                    relicFails.push({case:c, got, want}); };
  F.RELICS.t_double = { modify: { pop: v => v * 2 } };
  F.RELICS.t_plus10 = { modify: { pop: v => v + 10 } };
  let seen = null;
  F.RELICS.t_watch  = { onPop: p => { seen = p; } };
  let applied = 0;
  F.RELICS.t_apply  = { apply: () => { applied++; } };
  F.resetRun(); F.streak = 0;

  F.relics = []; F.score = 0; F.scorePop(10, 1);
  chk('no relics -> untouched', F.score, 10);
  F.relics = ['t_double','t_plus10']; F.score = 0; F.scorePop(10, 1);
  chk('modifiers stack in order', F.score, 30);          // (10 * 2) + 10
  F.relics = ['t_plus10','t_double']; F.score = 0; F.scorePop(10, 1);
  chk('order is significant', F.score, 40);              // (10 + 10) * 2

  F.relics = []; seen = null; F.notify('onPop', {x:1});
  chk('unowned relic stays silent', seen, null);
  F.relics = ['t_watch']; F.notify('onPop', {x:1});
  chk('owned relic is notified', seen && seen.x, 1);
  F.relics = ['t_apply']; applied = 0; F.applyRelics();
  chk('apply runs once per owned relic', applied, 1);
  F.relics = ['t_apply','t_apply']; applied = 0; F.applyRelics();
  chk('apply runs per entry', applied, 2);

  for (const k of ['t_double','t_plus10','t_watch','t_apply']) delete F.RELICS[k];
  F.relics = []; F.score = 0; F.streak = 0;

  // ---- starter relics + shop ----
  F.mode = 'rush'; F.resetRun(); F.mode = 'rush';
  const baseTouch = F.stageTouches(), baseSpawn = F.spawnCount(0);
  chk('cap starts at RELIC_SLOTS', F.relicCap(), F.RELIC_SLOTS);

  F.coins = 100;
  F.buyRelic('stamina');
  chk('buy: coins deducted',  F.coins, 100 - F.RELICS.stamina.price);
  chk('buy: relic owned',     F.relics, ['stamina']);
  chk('stamina: +3 touches',  F.stageTouches(), baseTouch + 3);
  F.applyRelics(); F.applyRelics();                 // recompute must be idempotent
  chk('stamina: not doubled by recompute', F.stageTouches(), baseTouch + 3);

  F.buyRelic('storm');
  chk('storm: +1 spawn', F.spawnCount(0), baseSpawn + 1);

  F.buyRelic('banana_hunter');
  chk('banana odds raised', F.oddsMult[6], 1);

  // score relic: 5+ cleared gets x1.5, fewer does not
  F.relics = ['big_pop']; F.applyRelics(); F.streak = 0;
  F.score = 0; F.scorePop(10, 1); const small = F.score;
  F.score = 0; F.scorePop(10, 5); const big = F.score;
  F.relics = []; F.applyRelics();
  F.score = 0; F.scorePop(10, 5); const bigPlain = F.score;
  chk('big_pop: under 5 cleared unaffected', small, 10);
  chk('big_pop: 5+ cleared x1.5', big, Math.round(bigPlain * 1.5));

  // the brick contract pays score and charges board space
  F.resetRun(); F.mode = 'rush'; F.coins = 100; F.streak = 0;
  F.relics = ['brick_deal']; F.applyRelics();
  chk('brick deal: bricks now spawn', F.brickChance > 0, true);
  F.score = 0; F.scorePop(10, 1); const withDeal = F.score;
  F.relics = []; F.applyRelics();
  chk('brick deal: no bricks without it', F.brickChance, 0);
  F.score = 0; F.scorePop(10, 1); const plain = F.score;
  chk('brick deal: +30% on pops', withDeal, Math.round(plain * 1.3));

  // discarding frees a slot and returns half, and only inside the shop
  F.resetRun(); F.mode = 'rush'; F.coins = 100;
  F.buyRelic('storm'); F.buyRelic('stamina');
  const beforeDrop = F.coins, price = F.RELICS.storm.price;
  F.discardRelic(0);
  chk('discard blocked outside the shop', F.relics.length, 2);
  F.openShop();
  F.discardRelic(0);
  chk('discard removes it', F.relics.map(x=>x), ['stamina']);
  chk('discard refunds half', F.coins, beforeDrop + Math.floor(price / 2));
  chk('discard undoes its effect', F.spawnCount(0), F.MODES.rush.spawns(0));
  F.closeShop(); F.resetRun(); F.mode = 'rush';

  // the satchel costs a slot and grants two
  F.resetRun(); F.mode = 'rush'; F.coins = 100;
  F.buyRelic('satchel');
  chk('satchel: cap 5 -> 7', F.relicCap(), F.RELIC_SLOTS + 2);
  chk('satchel: occupies a slot', F.relics.length, 1);

  // reported: 넓은 주머니 took slots to 6, then a satchel bought into that 6th slot cut
  // itself off and its +2 never applied -- the cap stayed at 6 instead of 8
  F.resetRun(); F.mode = 'rush'; F.coins = 500;
  F.traits = [{id:'big_pocket', amount:1}]; F.applyRelics();
  chk('trait: cap 5 -> 6', F.relicCap(), F.RELIC_SLOTS + 1);
  F.relics = ['storm','stamina','mint','tycoon','endurance'];   // fills all 5 base slots
  F.applyRelics();
  chk('five owned, cap still 6', [F.relics.length, F.relicCap()], [5, 6]);
  F.buyRelic('satchel');                       // lands in the 6th slot
  chk('satchel bought', F.relics.length, 6);
  chk('satchel in the last slot still grants +2', F.relicCap(), F.RELIC_SLOTS + 3);
  chk('so nothing is inert', F.activeRelics().length, 6);
  // a satchel beyond even the widened cap must NOT bootstrap itself in
  F.resetRun(); F.mode = 'rush';
  F.relics = ['storm','stamina','mint','tycoon','endurance','avalanche','satchel'];
  F.applyRelics();
  chk('satchel past the cap stays inert', F.relicCap(), F.RELIC_SLOTS);
  chk('only five active', F.activeRelics().length, 5);
  F.resetRun(); F.mode = 'rush';

  // cannot buy without the coins, or without a slot
  F.resetRun(); F.mode = 'rush'; F.coins = 0;
  F.buyRelic('storm');
  chk('too poor: nothing bought', F.relics.length, 0);
  F.coins = 500; F.relics = ['a','b','c','d','e']; F.applyRelics();
  F.buyRelic('storm');
  chk('slots full: nothing bought', F.relics.length, 5);

  // past the cap a relic is carried but inert (doc 6)
  F.resetRun(); F.mode = 'rush';
  F.relics = ['stamina','a','b','c','d','storm'];   // 6 owned, cap 5 -> storm is inert
  F.applyRelics();
  chk('over cap: only the first 5 are active', F.activeRelics().length, 5);
  chk('over cap: the inert one has no effect', F.spawnCount(0), baseSpawn);
  chk('over cap: it is still carried', F.relics.length, 6);

  // ---- traits: data-defined, and the x2 charge ----
  F.resetRun(); F.mode = 'rush';
  const base0 = F.fruitMult[0];
  F.pickTrait('cherry_taste');
  chk('trait applies its effect', +F.fruitMult[0].toFixed(2), +(base0 + 0.4).toFixed(2));
  chk('trait is recorded', F.traits.length, 1);
  F.applyRelics(); F.applyRelics();
  chk('trait survives recompute unchanged', +F.fruitMult[0].toFixed(2), +(base0 + 0.4).toFixed(2));

  // an armed graft charge doubles a scalable trait and is spent
  F.resetRun(); F.mode = 'rush'; F.doubles = 1;
  F.traitOffers = ['cherry_taste']; F.graftArmed = true;
  F.pickTrait('cherry_taste');
  chk('graft doubles the amount', +F.fruitMult[0].toFixed(2), +(base0 + 0.8).toFixed(2));
  chk('graft charge spent', F.doubles, 0);

  // ...but an unscalable trait cannot use it, so the charge is kept
  F.resetRun(); F.mode = 'rush'; F.doubles = 1;
  F.traitOffers = ['keen_eye']; F.graftArmed = true;
  F.pickTrait('keen_eye');
  chk('unscalable trait keeps the charge', F.doubles, 1);
  chk('keen_eye widens the shop', F.offerBonus, 1);
  chk('shop rolls one more', F.rollOffers(3 + F.offerBonus).length, 4);

  // graft grants a charge, and recomputing must not hand out another
  F.resetRun(); F.mode = 'rush';
  F.pickTrait('graft');
  chk('graft grants a charge', F.doubles, 1);
  F.applyRelics(); F.applyRelics();
  chk('recompute does not re-grant it', F.doubles, 1);

  // once-per-run traits stop being offered
  F.resetRun(); F.mode = 'rush';
  F.traits = [{id:'big_pocket', amount:1}];
  const t20 = []; for (let i = 0; i < 40; i++) t20.push(...F.rollTraits(3));
  chk('once-only trait not re-offered', t20.includes('big_pocket'), false);

  // multi-effect traits scale every part
  const cit = F.traitEffects(F.TRAITS.citrus, 2);
  chk('citrus doubles both fruits', cit.map(e => e.amount), [2, 2]);
  chk('unscalable ignores the multiplier', F.traitEffects(F.TRAITS.keen_eye, 2)[0].amount, 1);
  F.resetRun(); F.mode = 'arcade';

  // shop offers never repeat something already owned
  F.resetRun(); F.mode = 'rush';
  F.relics = ['storm','stamina']; F.applyRelics();
  const offers = F.rollOffers(9);
  chk('offers exclude owned', offers.some(id => F.relics.includes(id)), false);
  chk('offers are unique', new Set(offers).size, offers.length);
  F.resetRun(); F.mode = 'arcade';

  // ---- stacking value, and doubling what you already built ----
  const stackFails = [];
  const schk = (c, got, want) => { if (JSON.stringify(got) !== JSON.stringify(want))
                                     stackFails.push({case:c, got, want}); };
  F.resetRun(); F.mode = 'rush';
  schk('cherry starts at its base', F.fruitScore(0), F.FRUIT_POINTS[0]);

  // a stacking relic raises the base by playing, and a recompute must not wipe it
  F.relics = ['piggy_cherry']; F.applyRelics();
  for (let i = 0; i < 20; i++) F.notify('onFruitPop', {r:0, c:0, color:0});
  schk('20 cherries banked +1.0', +F.fruitScore(0).toFixed(2), +(F.FRUIT_POINTS[0] + 1).toFixed(2));
  F.applyRelics(); F.applyRelics();
  schk('recompute keeps the stack', +F.fruitScore(0).toFixed(2), +(F.FRUIT_POINTS[0] + 1).toFixed(2));
  // and only the fruit it names
  schk('other fruit untouched', F.fruitScore(1), F.FRUIT_POINTS[1]);

  // 농축 doubles whatever is worth most right now
  const beforeBest = F.fruitScore(6);
  F.traitOffers = ['concentrate']; F.graftArmed = false;
  F.pickTrait('concentrate');
  schk('doubles the priciest fruit', +F.fruitScore(6).toFixed(2), +(beforeBest * 2).toFixed(2));
  F.applyRelics();
  schk('the doubling survives a recompute', +F.fruitScore(6).toFixed(2), +(beforeBest * 2).toFixed(2));

  // 증류 adds to every fruit's base, and the graft charge scales it
  F.resetRun(); F.mode = 'rush';
  F.traitOffers = ['distill']; F.pickTrait('distill');
  schk('distill +0.5 on cherry', +F.fruitScore(0).toFixed(2), +(F.FRUIT_POINTS[0] + 0.5).toFixed(2));
  F.resetRun(); F.mode = 'rush'; F.doubles = 1; F.graftArmed = true;
  F.traitOffers = ['distill']; F.pickTrait('distill');
  schk('graft doubles distill to +1.0', +F.fruitScore(0).toFixed(2), +(F.FRUIT_POINTS[0] + 1).toFixed(2));

  // rare relics really are rarer
  F.resetRun(); F.mode = 'rush';
  let crowns = 0, common = 0;
  for (let i = 0; i < 400; i++) { const o = F.rollOffers(3);
    if (o.includes('crown')) crowns++; if (o.includes('storm')) common++; }
  schk('rare shows up less than common', crowns < common, true);
  F.resetRun(); F.mode = 'arcade';

  // ---- run-state round trip ----
  // This list is the TEST's own idea of what belongs to a run. If serializeRun()
  // forgets a field, restore leaves it at its reset value and the compare fails.
  const runFails = [];
  const grid10 = () => Array.from({length:10}, (_,r) => Array.from({length:8}, (_,c) => (r*8+c) % 7));
  F.resetRun();
  F.mode = 'rush';
  F.ROWS = 10;
  F.grid = grid10();
  F.special = Array.from({length:10}, (_,r) => Array.from({length:8}, (_,c) => (r+c)%5 ? null : 'bomb'));
  F.hp = Array.from({length:10}, (_,r) => Array(8).fill(r));
  F.coinCell = Array.from({length:10}, (_,r) => Array.from({length:8}, (_,c) => (r+c)%3 ? 0 : 1));
  F.nextColor = 5; F.nextColor2 = 2;
  F.relics = ['relic_a','relic_b'];
  F.traits = [{id:'cherry_taste', amount:2}];
  F.doubles = 3;
  F.fruitStack = [0.5,0,0,0,0,0,2.5];
  F.fruitBoost = [1,1,1,1,1,1,4];
  F.stage = 4; F.stageScore = 42; F.touchesLeft = 9; F.coins = 23;
  F.score = 1234; F.streak = 3; F.touchCount = 77;
  F.oddsMult = [0,0,0,2,0,0,3];
  F.fruitMult = [1,1.5,2,1,1,1,3];
  const want = {mode:'rush', ROWS:10, grid:F.grid, special:F.special, hp:F.hp, coinCell:F.coinCell, nextColor:5, nextColor2:2,
                score:1234, streak:3, touchCount:77, oddsMult:[0,0,0,2,0,0,3],
                fruitMult:[1,1.5,2,1,1,1,3], relics:['relic_a','relic_b'],
                stage:4, stageScore:42, touchesLeft:9, coins:23,
                traits:[{id:'cherry_taste', amount:2}], doubles:3,
                fruitStack:[0.5,0,0,0,0,0,2.5], fruitBoost:[1,1,1,1,1,1,4]};
  const snap = JSON.parse(JSON.stringify(F.serializeRun()));

  F.resetRun();                                   // reset must wipe it all
  const resetLeaks = [];
  if (F.score !== 0) resetLeaks.push('score');
  if (F.streak !== 0) resetLeaks.push('streak');
  if (F.touchCount !== 0) resetLeaks.push('touchCount');
  if (F.ROWS !== 8) resetLeaks.push('ROWS');
  F.mode = 'arcade';   // mode is chosen by start(), not by resetRun
  if (F.grid.length !== 8) resetLeaks.push('grid.rows');
  if (F.nextColor !== null) resetLeaks.push('nextColor');
  if (F.relics.length !== 0) resetLeaks.push('relics');
  if (F.stage !== 1) resetLeaks.push('stage');
  if (F.stageScore !== 0) resetLeaks.push('stageScore');
  if (F.touchesLeft !== F.RUSH_TOUCHES) resetLeaks.push('touchesLeft');
  if (F.coins !== 0) resetLeaks.push('coins');
  if (F.traits.length !== 0) resetLeaks.push('traits');
  if (F.doubles !== 0) resetLeaks.push('doubles');
  if (JSON.stringify(F.oddsMult) !== '[0,0,0,0,0,0,0]') resetLeaks.push('oddsMult');
  if (JSON.stringify(F.fruitMult) !== '[1,1,1,1,1,1,1]') resetLeaks.push('fruitMult');

  const restored = F.restoreRun(snap);
  if (!restored) runFails.push({field:'restoreRun', got:'returned false'});
  for (const k in want) {
    const a = JSON.stringify(F[k]), b = JSON.stringify(want[k]);
    if (a !== b) runFails.push({field:k, got:String(a).slice(0,60), want:String(b).slice(0,60)});
  }
  // the decay-only layers must be rebuilt clean at the restored size
  if (F.glow.length !== 10 || F.glow.some(row => row.length !== 8 || row.some(v => v !== null)))
    runFails.push({field:'glow', got:'not a clean 10x8 layer'});
  if (F.appear.length !== 10 || F.appear.some(row => row.some(v => v !== 0)))
    runFails.push({field:'appear', got:'not a clean 10x8 layer'});
  // an unknown save version must be refused rather than half-applied
  if (F.restoreRun({v:99, rows:8}) !== false) runFails.push({field:'version guard', got:'accepted v99'});
  if (F.restoreRun(null) !== false) runFails.push({field:'null guard', got:'accepted null'});
  F.resetRun();

  document.title = 'RESULT ' + JSON.stringify({
    cases: n, fails, fsFails, hist, runFails, resetLeaks, modeFails, relicFails, oddsFails, stackFails,
    fatal: null
  });
}, 900));
</script>
"""
open('_ut.html','w',encoding='utf-8').write(
    open('index.html',encoding='utf-8').read().replace('</body>', TEST + '</body>'))
out = subprocess.run(['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '--headless','--disable-gpu','--no-first-run','--window-size=430,932',
    '--virtual-time-budget=30000','--dump-dom','http://localhost:8899/_ut.html?test=1'],
    capture_output=True, text=True, timeout=120).stdout
os.remove('_ut.html')
m = re.search(r'RESULT (\{.*?\})</title>', out, re.S)
if not m:
    print('NO RESULT'); sys.exit(1)
res = json.loads(m.group(1))
ok = (not res['fails'] and not res['fsFails'] and res['cases'] > 0
      and not res['runFails'] and not res['resetLeaks'] and not res['modeFails'] and not res['relicFails'] and not res['oddsFails'] and not res['stackFails'])
active = sum(1 for h in res['hist'] if h > 0)
spread = (max(res['hist']) - min(h for h in res['hist'] if h > 0)) / max(res['hist'])
print(f"scoring : {res['cases']} cases, {len(res['fails'])} fail")
print(f"fruit   : {len(res['fsFails'])} fail")
print(f"pickColor: {active} active colours, max spread {spread:.1%}")
print(f"odds    : {len(res['oddsFails'])} fail")
if res['oddsFails']: print('  ', res['oddsFails'][:4])
print(f"modes   : {len(res['modeFails'])} fail")
if res['modeFails']: print('  ', res['modeFails'][:4])
print(f"stacking: {len(res['stackFails'])} fail")
if res['stackFails']: print('  ', res['stackFails'][:4])
print(f"relics  : {len(res['relicFails'])} fail")
if res['relicFails']: print('  ', res['relicFails'][:4])
print(f"run state: {len(res['runFails'])} round-trip fail, {len(res['resetLeaks'])} reset leak")
if res['runFails']: print('  ', res['runFails'][:4])
if res['resetLeaks']: print('   leaked:', res['resetLeaks'])
if res['fails']: print('  e.g.', res['fails'][:3])
print('PASS' if ok and spread < 0.05 else 'FAIL')
sys.exit(0 if ok and spread < 0.05 else 1)
