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
 try {
  const F = window.__fs;
  if (!F) { document.title = 'RESULT {"fatal":"no test hook"}'; return; }
  const fails = []; let n = 0;
  F.score = 0;                        // score is undefined until start(); seed it
  // Reference for the chokepoint. It reads the STEP constants (they are tuning, and pinning
  // them here just means retuning breaks the suite) but re-implements the 0.1 grid rounding
  // independently -- so forgetting to round, or applying chain and streak in the wrong order,
  // still fails.
  const grid1 = v => Math.round(v * 10) / 10;
  const refStreak = s => grid1(Math.min(1 + s * F.STREAK_STEP_BASE, 2.0));
  const refPop = (base, cleared, s) =>
    Math.round(base * grid1(1 + (cleared - 1) * F.CHAIN_STEP) * refStreak(s));
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
  // Multipliers must live on a 0.1 grid -- the value, not just the printed form. This is the
  // whole point of the change, so it is asserted directly rather than inferred from scores.
  const offGrid = [];
  for (let cleared = 1; cleared <= 30; cleared++) {
    const v = F.chainBonus(cleared);
    if (Math.abs(v * 10 - Math.round(v * 10)) > 1e-9) offGrid.push({ kind: 'chain', cleared, v });
  }
  for (let s2 = 0; s2 <= 30; s2++) {
    F.streak = s2;
    const v = F.streakMult();
    if (Math.abs(v * 10 - Math.round(v * 10)) > 1e-9) offGrid.push({ kind: 'combo', streak: s2, v });
  }
  // ...and with every relic that moves those steps stacked on top
  F.mode = 'rush'; F.resetRun();
  F.relics.push('whetstone', 'chain_fan', 'first_step', 'elastic', 'bell', 'frenzy', 'streak_step');
  F.applyRelics();
  for (let cleared = 1; cleared <= 30; cleared++) {
    const v = F.chainBonus(cleared);
    if (Math.abs(v * 10 - Math.round(v * 10)) > 1e-9) offGrid.push({ kind: 'chain+relics', cleared, v });
  }
  for (let s2 = 0; s2 <= 40; s2++) {
    F.streak = s2;
    const v = F.streakMult();
    if (Math.abs(v * 10 - Math.round(v * 10)) > 1e-9) offGrid.push({ kind: 'combo+relics', streak: s2, v });
  }
  if (offGrid.length) fails.push({ case: 'a multiplier left the 0.1 grid', e: offGrid.slice(0, 4) });

  // combo must climb in 0.1 steps, not 0.2
  F.resetRun(); F.mode = 'rush';
  F.streak = 1; const c1 = F.streakMult();
  F.streak = 2; const c2 = F.streakMult();
  if (+(c1).toFixed(4) !== 1.1 || +(c2).toFixed(4) !== 1.2)
    fails.push({ case: 'combo climbs by 0.1', got: [c1, c2], want: [1.1, 1.2] });

  // gridMult must actually round. The grid check above cannot see this: it reads values that
  // have already been through gridMult, so it holds even if gridMult is the identity.
  if (F.gridMult(1.24) !== 1.2 || F.gridMult(1.26) !== 1.3 || F.gridMult(1.25) !== 1.3)
    fails.push({ case: 'gridMult does not snap to 0.1',
                 got: [F.gridMult(1.24), F.gridMult(1.26), F.gridMult(1.25)] });

  // and the label must clamp too -- fed an off-grid value it still prints one decimal
  const lbl = F.multLabel(1.25, 1.25).map(x => x[1]).join(' ');
  if (/\d\.\d\d/.test(lbl)) fails.push({ case: 'label shows two decimals', got: lbl });

  // Every relic that moves a step must move it by a multiple of 0.1. Rounding the OUTPUT
  // hides a 0.05 step, but it still makes two purchases land unevenly -- one does nothing
  // visible, the next jumps 0.1.
  const stepOff = [];
  for (const id of Object.keys(F.RELICS)) {
    F.resetRun(); F.mode = 'rush';
    const step0 = F.STREAK_STEP, chain0 = F.chainStep, cap0 = F.STREAK_CAP;
    F.relics.push(id); F.applyRelics();
    for (const [what, before, after] of [['combo step', step0, F.STREAK_STEP],
                                        ['chain step', chain0, F.chainStep],
                                        ['combo cap', cap0, F.STREAK_CAP]]) {
      const d = Math.abs(after - before);
      if (d > 1e-9 && Math.abs(d * 10 - Math.round(d * 10)) > 1e-9)
        stepOff.push({ id, what, delta: +d.toFixed(4) });
    }
  }
  if (stepOff.length) fails.push({ case: 'a relic moves a step off the 0.1 grid', e: stepOff });
  F.resetRun(); F.mode = 'arcade'; F.streak = 0; F.score = 0;

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
    let q = F.RUSH_QUOTA_1;
    for (let k = 0; k < r; k++) q *= F.roundSpan(k);
    const want = Math.round(q * Math.pow(F.RUSH_STAGE_MUL, sub));
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

  // No fruit may ever reach 0%. A fruit that never spawns silently kills every relic keyed
  // to it, and the odds table stops describing a game you can actually build in.
  const floorCases = [
    ['banana +3',      [0,0,0,0,0,0,3]],
    ['banana +9',      [0,0,0,0,0,0,9]],
    ['banana +40',     [0,0,0,0,0,0,40]],
    ['banana +200',    [0,0,0,0,0,0,200]],
    ['two stacks',     [5,0,0,5,0,0,20]],
    ['everything +9',  [9,9,9,9,9,9,9]],
  ];
  const zeroed = [], offTotal = [];
  for (const [label, mult] of floorCases) {
    F.oddsMult = mult.slice();
    const q = F.colorOdds();
    const lo = Math.min.apply(null, q);
    // compared against an absolute figure, NOT against MIN_ODDS: keying the assertion to the
    // constant means lowering the constant lowers the assertion with it and proves nothing
    if (lo < 1) zeroed.push(label + ': ' + lo.toFixed(2) + '%');
    const tot = q.reduce((a, b) => a + b, 0);
    if (Math.abs(tot - 100) > 0.01) offTotal.push(label + ': ' + tot.toFixed(2));
  }
  ochk('the floor itself is a usable share', F.MIN_ODDS >= 1 ? 1 : 0, 1, 0);
  ochk('no boost can starve a fruit below 1%', zeroed.length, 0, 0);
  if (zeroed.length) oddsFails.push({case: 'starved', got: zeroed, want: []});
  ochk('and every boosted table still totals 100', offTotal.length, 0, 0);
  if (offTotal.length) oddsFails.push({case: 'totals', got: offTotal, want: []});
  // boosting every fruit equally changes nothing -- it is a share, not an absolute
  F.oddsMult = [9,9,9,9,9,9,9];
  const flat = F.colorOdds();
  for (let i = 0; i < 7; i++) ochk('uniform boost is a no-op, slot ' + i, flat[i], F.BASE_ODDS[i]);
  F.oddsMult = [0,0,0,0,0,0,0];

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
  // filler that grants no slots, sized from RELIC_SLOTS so tuning the cap can't break this
  const filler = (n, except) => Object.keys(F.RELICS)
    .filter(id => !F.RELICS[id].slots && !F.RELICS[id].life && id !== except).slice(0, n);
  const capWithTrait = F.RELIC_SLOTS + 1;
  F.relics = filler(capWithTrait - 1);          // one short of the widened cap
  F.applyRelics();
  chk('cap unchanged by filler', F.relicCap(), capWithTrait);
  F.buyRelic('satchel');                        // lands in the last slot
  chk('satchel bought', F.relics.length, capWithTrait);
  chk('satchel in the last slot still grants +2', F.relicCap(), F.RELIC_SLOTS + 3);
  chk('so nothing is inert', F.activeRelics().length, capWithTrait);
  // a satchel beyond even the widened cap must NOT bootstrap itself in
  F.resetRun(); F.mode = 'rush';
  F.relics = filler(F.RELIC_SLOTS + 1).concat('satchel');
  F.applyRelics();
  chk('satchel past the cap stays inert', F.relicCap(), F.RELIC_SLOTS);
  chk('only the cap is active', F.activeRelics().length, F.RELIC_SLOTS);
  F.resetRun(); F.mode = 'rush';

  // cannot buy without the coins, or without a slot
  F.resetRun(); F.mode = 'rush'; F.coins = 0;
  F.buyRelic('storm');
  chk('too poor: nothing bought', F.relics.length, 0);
  F.coins = 500; F.relics = filler(F.RELIC_SLOTS); F.applyRelics();
  const heldWhenFull = F.relics.length;
  F.buyRelic('crown');
  chk('slots full: nothing bought', F.relics.length, heldWhenFull);

  // past the cap a relic is carried but inert (doc 6)
  F.resetRun(); F.mode = 'rush';
  F.relics = filler(F.RELIC_SLOTS, 'storm').concat('storm');   // storm sits one past the cap
  F.applyRelics();
  chk('over cap: only the cap is active', F.activeRelics().length, F.RELIC_SLOTS);
  chk('over cap: the inert one has no effect', F.spawnCount(0), baseSpawn);
  chk('over cap: it is still carried', F.relics.length, F.RELIC_SLOTS + 1);

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

  // graft is the high-ceiling pick, so anything a doubling MEANS something for must take it.
  // 넓은 주머니 and 안목 were marked unscalable and silently ignored an armed charge.
  F.resetRun(); F.mode = 'rush'; F.doubles = 1;
  F.traitOffers = ['keen_eye']; F.graftArmed = true;
  F.pickTrait('keen_eye');
  chk('graft doubles 안목', F.offerBonus, 2);
  chk('and is spent on it', F.doubles, 0);

  // the shelf has an intended ceiling of 6: base 4, +1 안목, +1 more if that 안목 was grafted
  chk('a bare shelf is the base', (() => { F.resetRun(); F.mode='rush'; return F.shelfSize(); })(), 4);
  F.resetRun(); F.mode='rush'; F.graftArmed = false; F.pickTrait('keen_eye');
  chk('안목 widens it by one', F.shelfSize(), 5);
  chk('and the shop really rolls that many', F.rollOffers(F.shelfSize()).length, 5);
  F.resetRun(); F.mode='rush'; F.doubles = 1; F.graftArmed = true; F.pickTrait('keen_eye');
  chk('a grafted 안목 reaches the ceiling', F.shelfSize(), F.SHOP_OFFERS_MAX);
  chk('which is 6', F.SHOP_OFFERS_MAX, 6);
  // 안목 was the one unbounded stat: not once-per-run, so a long run could stack it forever
  F.resetRun(); F.mode='rush'; F.graftArmed = false;
  F.pickTrait('keen_eye');
  const seenKE = []; for (let i = 0; i < 60; i++) seenKE.push(...F.rollTraits(3));
  chk('안목 is once per run', seenKE.includes('keen_eye'), false);
  // and even if something else ever feeds offerBonus, the shelf still cannot pass the cap
  F.resetRun(); F.mode='rush'; F.traits = [{id:'keen_eye', amount:9}]; F.applyRelics();
  chk('the ceiling holds against anything', F.shelfSize(), F.SHOP_OFFERS_MAX);
  F.resetRun(); F.mode='rush'; F.graftArmed = false;

  const capBase = (() => { F.resetRun(); F.mode = 'rush'; return F.relicCap(); })();
  F.resetRun(); F.mode = 'rush'; F.graftArmed = false;
  F.pickTrait('big_pocket');
  chk('넓은 주머니 adds a slot', F.relicCap(), capBase + 1);
  F.resetRun(); F.mode = 'rush'; F.doubles = 1; F.graftArmed = true;
  F.pickTrait('big_pocket');
  chk('graft doubles 넓은 주머니', F.relicCap(), capBase + 2);
  chk('and is spent on it too', F.doubles, 0);

  // a charge with nothing scalable to spend it on is kept, not burned
  F.resetRun(); F.mode = 'rush'; F.doubles = 1; F.graftArmed = true;
  F.pickTrait('graft');
  chk('an unscalable pick keeps the charge', F.doubles, 2);

  // an armed flag with no charge behind it must not double anything for free
  F.resetRun(); F.mode = 'rush'; F.graftArmed = true;   // doubles is 0 after a reset
  F.pickTrait('cherry_taste');
  chk('armed without a charge does nothing', +F.fruitMult[0].toFixed(2), +(base0 + 0.4).toFixed(2));
  F.graftArmed = false;

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
  chk('unscalable ignores the multiplier', F.traitEffects(F.TRAITS.graft, 2)[0].amount, 1);
  // every trait a player can carry should be doublable -- graft is the charge itself
  chk('only the charge is unscalable',
      Object.keys(F.TRAITS).filter(id => !F.TRAITS[id].scalable), ['graft']);
  // ...and the charge does not sit in the carried list pretending to be one
  chk('graft is marked as a charge', !!F.TRAITS.graft.meta, true);
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
  // asserted as a relationship, not a number: tuning the increment must not break the test
  F.relics = ['piggy_cherry']; F.applyRelics();
  const cherry0 = F.fruitScore(0);
  F.notify('onFruitPop', {r:0, c:0, color:0});
  const perPop = F.fruitScore(0) - cherry0;
  schk('one cherry banks a whole number', perPop === Math.round(perPop) && perPop > 0, true);
  for (let i = 0; i < 19; i++) F.notify('onFruitPop', {r:0, c:0, color:0});
  schk('20 cherries bank 20x that', F.fruitScore(0), cherry0 + perPop * 20);
  F.applyRelics(); F.applyRelics();
  schk('recompute keeps the stack', F.fruitScore(0), cherry0 + perPop * 20);
  // and only the fruit it names
  schk('other fruit untouched', F.fruitScore(1), F.FRUIT_POINTS[1]);

  // 농축 doubles whatever is worth most right now
  const beforeBest = F.fruitScore(6);
  F.traitOffers = ['concentrate']; F.graftArmed = false;
  F.pickTrait('concentrate');
  schk('doubles the priciest fruit', F.fruitScore(6), beforeBest * 2);
  F.applyRelics();
  schk('the doubling survives a recompute', F.fruitScore(6), beforeBest * 2);

  // 증류 adds to every fruit's base, and the graft charge scales it
  F.resetRun(); F.mode = 'rush';
  const distillAmt = F.TRAITS.distill.effects[0].amount;
  F.traitOffers = ['distill']; F.pickTrait('distill');
  schk('distill adds its amount', F.fruitScore(0), F.FRUIT_POINTS[0] + distillAmt);
  F.resetRun(); F.mode = 'rush'; F.doubles = 1; F.graftArmed = true;
  F.traitOffers = ['distill']; F.pickTrait('distill');
  schk('graft doubles distill', F.fruitScore(0), F.FRUIT_POINTS[0] + distillAmt * 2);

  // nothing on screen may show a decimal
  F.resetRun(); F.mode = 'rush';
  F.relics = ['piggy_cherry','prism']; F.traits = [{id:'cherry_taste', amount:2}];
  F.applyRelics();
  for (let i = 0; i < 7; i++) F.notify('onFruitPop', {r:0, c:0, color:0});
  for (let i = 0; i < 7; i++)
    if (F.fruitScore(i) !== Math.round(F.fruitScore(i)))
      stackFails.push({case:'fruit ' + i + ' is a whole number', got:F.fruitScore(i), want:'integer'});
  F.relics = []; F.traits = []; F.resetRun(); F.mode = 'rush';

  // ---- temporary relics run out ----
  F.resetRun(); F.mode = 'rush'; F.coins = 200;
  const spawn0 = F.spawnCount(0);
  F.buyRelic('frenzy');                      // 1 stage of +3 spawns
  schk('temp relic works while it lasts', F.spawnCount(0), spawn0 + 3);
  schk('its clock is set', F.relicLife.frenzy, F.RELICS.frenzy.life.amount);
  F.tickRelicLife('touches');                // wrong unit: must not touch it
  schk('the wrong unit does not tick it', F.relicLife.frenzy, F.RELICS.frenzy.life.amount);
  F.tickRelicLife('stages');
  schk('expired: gone from the list', F.relics.includes('frenzy'), false);
  schk('expired: effect withdrawn', F.spawnCount(0), spawn0);
  schk('expired: clock cleared', F.relicLife.frenzy, undefined);

  // a timed relic lasts exactly as long as it says. Read the duration off the relic rather
  // than pinning it: retuning 단기 집중 from 2 stages to 1 should not break this.
  F.resetRun(); F.mode = 'rush'; F.coins = 200; F.streak = 0;
  const focusLife = F.RELICS.focus.life.amount;
  F.buyRelic('focus');
  F.score = 0; F.scorePop(10, 1); const withFocus = F.score;
  for (let i = 1; i < focusLife; i++) {
    F.tickRelicLife('stages');
    schk(`still held after stage ${i} of ${focusLife}`, F.relics.includes('focus'), true);
  }
  F.tickRelicLife('stages');
  schk('gone once its stages are used up', F.relics.includes('focus'), false);
  F.score = 0; F.scorePop(10, 1); const without = F.score;
  schk('and its boost went with it', withFocus > without, true);
  // ...by exactly what the relic itself says it does, whatever that is tuned to
  schk('the boost matched the relic while held', withFocus, F.RELICS.focus.modify.pop(without));

  // selling one stops its clock too
  F.resetRun(); F.mode = 'rush'; F.coins = 200;
  F.buyRelic('bonanza'); F.openShop(); F.discardRelic(0); F.closeShop();
  schk('sold: clock cleared', F.relicLife.bonanza, undefined);

  // flat points from a relic are derived, so they leave with it
  F.resetRun(); F.mode = 'rush'; F.coins = 200;
  const cherryBase = F.fruitScore(0);
  F.buyRelic('one_cherry');
  const withFlat = F.fruitScore(0);
  schk('flat points apply', withFlat > cherryBase, true);
  F.openShop(); F.discardRelic(0); F.closeShop();
  schk('flat points leave with it', F.fruitScore(0), cherryBase);

  // the first shop has to be affordable on a first-stage payout
  const firstPayout = F.COIN_PAYOUT(1);
  const cheapest = Math.min(...Object.keys(F.RELICS).map(id => F.RELICS[id].price));
  schk('something is buyable on the first payout', cheapest <= firstPayout + 2, true);
  F.resetRun(); F.mode = 'arcade';

  // ---- shop shelf, sold-in-place, and the free trait reroll ----
  F.resetRun(); F.mode = 'rush'; F.coins = 500;
  F.openShop();
  schk('shelf is SHOP_OFFERS wide', F.shopOffers.length, F.SHOP_OFFERS);
  const shelf = F.shopOffers.slice();
  const buyMe = shelf.find(id => F.RELICS[id].price <= 500);
  F.buyRelic(buyMe);
  schk('bought relic stays on the shelf', F.shopOffers.length, F.SHOP_OFFERS);
  schk('same cards, same order', F.shopOffers, shelf);
  schk('and it is marked sold', F.shopSold.has(buyMe), true);
  schk('buying it twice does nothing', (F.buyRelic(buyMe), F.relics.filter(x => x === buyMe).length), 1);
  F.closeShop();

  // the 안목 trait widens the shelf further
  F.resetRun(); F.mode = 'rush';
  F.traits = [{id:'keen_eye', amount:1}]; F.applyRelics();
  F.openShop();
  schk('keen eye adds one', F.shopOffers.length, F.SHOP_OFFERS + 1);
  F.closeShop();

  // one free trait reroll per screen
  F.resetRun(); F.mode = 'rush';
  F.openTraits();
  schk('a free reroll is granted', F.traitRerolls, 1);
  const before = F.traitOffers.slice();
  document.getElementById('tr-reroll').click();
  schk('reroll spent', F.traitRerolls, 0);
  schk('and it is disabled after', document.getElementById('tr-reroll').disabled, true);
  document.getElementById('tr-reroll').click();
  schk('a second click does nothing', F.traitRerolls, 0);
  F.pickTrait(F.traitOffers[0]);
  F.openTraits();
  schk('the next screen grants a fresh one', F.traitRerolls, 1);
  document.getElementById('traits').classList.add('hidden');
  F.resetRun(); F.mode = 'arcade';

  // ---- graft must mean exactly "pick that trait twice", for EVERY trait ----
  // asserted over the whole table rather than case by case, so a trait added later cannot
  // quietly break the rule
  (() => {
    const snap = () => JSON.stringify({
      mult: F.fruitMult.map(v => +v.toFixed(4)), odds: F.oddsMult.slice(),
      prob: F.colorOdds().map(v => +v.toFixed(4)), stack: F.fruitStack.slice(),
      boost: F.fruitBoost.map(v => +v.toFixed(4)),
      score: F.FRUIT_POINTS.map((_, i) => F.fruitScore(i)),
      touch: F.touchBonus, spawn: F.spawnBonus, offer: F.offerBonus,
      cap: F.relicCap(), st: F.stageTouches(),
      // the item knobs too, or the traits that move them sit outside the invariant
      bombR: F.bombRadius(), ease: F.itemEase, birds: F.birdFlock, starC: F.starCoinMult,
    });
    const fresh = () => { F.resetRun(); F.mode = 'rush'; F.graftArmed = false; F.doubles = 0; };
    const mismatched = [];
    for (const id of Object.keys(F.TRAITS)) {
      if (!F.TRAITS[id].scalable) continue;             // the charge itself is not doublable
      fresh(); F.doubles = 1; F.graftArmed = true; F.pickTrait(id);
      const grafted = snap(), charge = F.doubles;
      fresh(); F.pickTrait(id); F.pickTrait(id);
      if (grafted !== snap() || charge !== 0) mismatched.push(id);
    }
    schk('grafted once == picked twice, every trait', mismatched, []);
    // and the invariant is only worth anything if it covers every trait there is
    schk('every trait was actually compared',
         Object.keys(F.TRAITS).filter(id => F.TRAITS[id].scalable).length,
         Object.keys(F.TRAITS).length - 1);   // all but the charge itself

    // item knobs stay inside their guards no matter how much is stacked on them
    fresh(); F.traits = [{id:'blast', amount:9}]; F.applyRelics();
    schk('bomb radius is capped', F.bombRadius() <= 4, true);
    fresh(); F.traits = [{id:'knack', amount:9}]; F.applyRelics();
    schk('easing really moves the threshold', F.itemNeed(F.STAR_THRESHOLD) < F.STAR_THRESHOLD, true);
    schk('but no threshold drops below the floor',
         [F.BIRD_THRESHOLD, F.LINE_THRESHOLD, F.BOMB_THRESHOLD, F.STAR_THRESHOLD]
           .filter(t => F.itemNeed(t) < F.ITEM_NEED_MIN), []);
    fresh();
    schk('unmodified thresholds are untouched', F.itemNeed(F.BIRD_THRESHOLD), F.BIRD_THRESHOLD);

    // a charge arrives armed: the description promises it just happens
    fresh(); F.doubles = 1; F.openTraits();
    schk('a charge opens armed', F.graftArmed, true);
    F.traitRerolls = 1; document.getElementById('tr-reroll').click();
    schk('rerolling is not opting out', F.graftArmed, true);
    schk('and does not eat the charge', F.doubles, 1);
    fresh(); F.openTraits();
    schk('no charge, nothing armed', F.graftArmed, false);

    // one pick spends exactly one charge
    fresh(); F.doubles = 2; F.graftArmed = true; F.pickTrait('leisure');
    schk('one pick spends one charge', F.doubles, 1);

    // stacking onto a trait you already carry is still just "one more copy"
    fresh(); F.pickTrait('cherry_taste');
    F.doubles = 1; F.graftArmed = true; F.pickTrait('cherry_taste');
    const stacked = +F.fruitMult[0].toFixed(4);
    fresh(); F.pickTrait('cherry_taste'); F.pickTrait('cherry_taste'); F.pickTrait('cherry_taste');
    schk('graft on an owned trait == a third copy', stacked, +F.fruitMult[0].toFixed(4));

    // a doubled once-only trait is still once-only
    fresh(); F.doubles = 1; F.graftArmed = true; F.pickTrait('big_pocket');
    const seen = []; for (let i = 0; i < 60; i++) seen.push(...F.rollTraits(3));
    schk('a grafted once-trait is not re-offered', seen.includes('big_pocket'), false);

    // the doubled amount and the unspent charge both survive a save/load
    fresh(); F.doubles = 2; F.graftArmed = true; F.pickTrait('big_pocket');
    const was = [F.relicCap(), F.doubles, F.traits.map(t => t.id + ':' + t.amount).join()];
    const blob = JSON.parse(JSON.stringify(F.serializeRun()));
    fresh(); F.restoreRun(blob); F.applyRelics();
    schk('a doubled trait survives a round trip',
         [F.relicCap(), F.doubles, F.traits.map(t => t.id + ':' + t.amount).join()], was);
    fresh();
  })();

  // ---- item shop: coins in, an item on the board, and NOTHING else moved ----
  (() => {
    F.mode = 'rush'; F.resetRun();
    const emptyRC = () => { for (let r=0;r<F.ROWS;r++) for (let c=0;c<F.COLS;c++)
                              if (F.grid[r][c] === -1) return [r,c]; return null; };
    F.running = true; F.busy = false; F.paused = false;
    F.coins = 0;
    schk('broke, so nothing is buyable', F.canBuyItem('bird'), false);
    F.coins = F.ITEM_PRICES.bird;
    schk('exactly enough is enough', F.canBuyItem('bird'), true);
    schk('but the dearer one is still out of reach', F.canBuyItem('star'), false);
    F.coins = F.ITEM_PRICES.star - 1;
    schk('one coin short is short', F.canBuyItem('star'), false);
    F.coins = 200;

    // arming is a toggle and does not spend anything
    F.armItem('bomb');
    schk('arming selects', F.armedItem, 'bomb');
    schk('and costs nothing yet', F.coins, 200);
    F.armItem('bomb');
    schk('tapping it again cancels', F.armedItem, null);

    // buying deducts exactly the price and leaves the turn untouched
    F.armItem('bomb');
    const [r0, c0] = emptyRC();
    const before = { coins: F.coins, touch: F.touchCount, left: F.touchesLeft,
                     next: F.nextColor, filled: F.filledCount() };
    schk('the cell is empty first', F.grid[r0][c0], -1);
    F.placeBoughtItem(r0, c0);
    schk('an item is now there', F.special[r0][c0], 'bomb');
    schk('and it cost exactly its price', before.coins - F.coins, F.ITEM_PRICES.bomb);
    schk('no touch was spent', [F.touchCount, F.touchesLeft], [before.touch, before.left]);
    // the old dock bug: buying must not disturb the queued fruit
    schk('the queued fruit is untouched', F.nextColor, before.next);
    schk('exactly one cell was filled', F.filledCount(), before.filled + 1);
    schk('and the arm is cleared', F.armedItem, null);

    // A tap on an occupied cell is a MISS, not a cancel. Disarming there threw the purchase
    // away silently and the NEXT tap planted an ordinary fruit, spending a turn the player
    // never meant to spend -- which is exactly how it was reported.
    F.armItem('bird');
    const coinsWas = F.coins, turnWas = F.touchCount;
    F.placeBoughtItem(r0, c0);                    // still holds the bomb
    schk('a blocked placement spends nothing', F.coins, coinsWas);
    schk('and costs no turn', F.touchCount, turnWas);
    schk('and stays armed for the next tap', F.armedItem, 'bird');
    const [r2, c2] = emptyRC();
    F.placeBoughtItem(r2, c2);
    schk('so the next tap places the item, not a fruit', F.special[r2][c2], 'bird');
    schk('now it disarms', F.armedItem, null);
    schk('and only now was it paid for', coinsWas - F.coins, F.ITEM_PRICES.bird);

    // cannot arm what you cannot afford
    F.coins = 5;
    F.armItem('star');
    schk('too poor to arm', F.armedItem, null);

    // a full board has nowhere to put one
    F.resetRun(); F.running = true; F.coins = 500;
    for (let r=0;r<F.ROWS;r++) for (let c=0;c<F.COLS;c++) F.grid[r][c] = 0;
    schk('a full board blocks the purchase', F.canBuyItem('bird'), false);

    // arcade gets the same sink -- that was the whole point
    F.resetRun(); F.mode = 'arcade'; F.running = true; F.coins = 100;
    schk('arcade can buy too', F.canBuyItem('bird'), true);
    F.armItem('bird');
    const [r1, c1] = emptyRC();
    F.placeBoughtItem(r1, c1);
    schk('and it lands', F.special[r1][c1], 'bird');
    F.running = false; F.resetRun(); F.mode = 'rush';
  })();

  // ---- the shop must never offer a relic that cannot do anything yet ----
  (() => {
    F.mode = 'rush'; F.resetRun();
    // 측량 widens the marked cells; with no 명당/금맥 there are none, so it is a dead purchase
    schk('측량 alone marks nothing', (() => {
      F.resetRun(); F.relics.push('survey'); F.applyRelics(); F.rollZones();
      return F.zoneCells.size;
    })(), 0);
    F.resetRun();
    const seen = new Set();
    for (let i = 0; i < 300; i++) for (const id of F.rollOffers(5)) seen.add(id);
    schk('so it is not offered', seen.has('survey'), false);

    // once a zone relic is owned it becomes useful, and becomes purchasable
    F.resetRun(); F.relics.push('hotspot'); F.applyRelics();
    const seen2 = new Set();
    for (let i = 0; i < 300; i++) for (const id of F.rollOffers(5)) seen2.add(id);
    schk('and is offered once it can work', seen2.has('survey'), true);
    F.relics.push('survey'); F.applyRelics(); F.rollZones();
    schk('and then really widens the map', F.zoneCells.size, F.ZONE_BASE + 3);

    // The gate must not quietly swallow anything else. Checked as a PROPERTY rather than
    // against a list of names: a list has to be edited every time a gated relic is added,
    // and the edit is what gets forgotten. Every gate must be shut on a fresh run (or it is
    // pointless) and must open for something (or the relic is unreachable).
    F.resetRun();
    const gated = Object.keys(F.RELICS).filter(id => F.RELICS[id].requires);
    schk('there are gated relics to check', gated.length > 0, true);
    const openAtStart = gated.filter(id => F.RELICS[id].requires());
    schk('no gate is already open on a fresh run', openAtStart, []);
    const neverOpens = gated.filter(id => {
      F.resetRun();
      for (const other of Object.keys(F.RELICS)) {
        if (other === id) continue;
        F.relics = [other]; F.applyRelics(); F.rollZones();
        if (F.RELICS[id].requires()) { F.relics = []; F.applyRelics(); return false; }
      }
      F.relics = []; F.applyRelics();
      return true;
    });
    schk('every gate can be opened by some relic', neverOpens, []);
    F.resetRun();
    F.resetRun();
  })();

  // ---- bonus zones ----
  (() => {
    F.mode = 'rush'; F.resetRun();
    F.rollZones();
    schk('no zone relic, no zones', [F.zoneCount(), F.zoneCells.size], [0, 0]);
    schk('and scoring is untouched', F.fruitScoreAt(0, 0, 0), F.fruitScore(0));

    F.relics.push('hotspot'); F.applyRelics(); F.rollZones();
    schk('명당 puts zones on the board', F.zoneCells.size, F.ZONE_BASE);
    // find one marked cell and one plain one, then compare what a pop is worth
    let inZone = null, outZone = null;
    for (let r = 0; r < F.ROWS && (!inZone || !outZone); r++)
      for (let c = 0; c < F.COLS; c++) {
        if (F.zoneAt(r, c)) inZone = inZone || [r, c]; else outZone = outZone || [r, c];
      }
    schk('there is a marked and an unmarked cell', !!inZone && !!outZone, true);
    schk('a marked cell pays double',
         F.fruitScoreAt(inZone[0], inZone[1], 0), F.fruitScore(0) * 2);
    schk('an unmarked one pays normally',
         F.fruitScoreAt(outZone[0], outZone[1], 0), F.fruitScore(0));
    schk('and the score stays an integer',
         Number.isInteger(F.fruitScoreAt(inZone[0], inZone[1], 4)), true);

    F.relics.push('survey'); F.applyRelics(); F.rollZones();
    schk('측량 marks more of them', F.zoneCells.size, F.ZONE_BASE + 3);
    schk('every marked cell is on the board',
         [...F.zoneCells].filter(i => i < 0 || i >= F.ROWS * F.COLS), []);
    schk('and they are distinct', F.zoneCells.size, new Set([...F.zoneCells]).size);

    // 금맥 alone is enough to put zones out, even with no multiplier
    F.resetRun(); F.relics.push('gold_vein'); F.applyRelics(); F.rollZones();
    schk('금맥 alone still marks the board', F.zoneCells.size, F.ZONE_BASE);
    schk('but does not change what a fruit is worth',
         F.fruitScoreAt([...F.zoneCells][0] / F.COLS | 0, [...F.zoneCells][0] % F.COLS, 0),
         F.fruitScore(0));

    // a grown board can be marked anywhere on it
    F.resetRun(); F.relics.push('hotspot', 'big_reclaim', 'survey');
    F.applyRelics(); F.rollZones();
    schk('zones can land on rows 개간 added',
         [...F.zoneCells].filter(i => i >= F.ROWS * F.COLS), []);
    F.resetRun();
    schk('a new run clears the map', F.zoneCells.size, 0);
  })();

  // ---- board growth: the one derived stat that must never run backwards ----
  (() => {
    const rowsOf = () => [F.ROWS, F.grid.length, F.special.length, F.hp.length, F.coinCell.length];
    F.mode = 'rush'; F.resetRun();
    schk('a run starts at the base size', rowsOf(), [F.ROWS_BASE, F.ROWS_BASE, F.ROWS_BASE, F.ROWS_BASE, F.ROWS_BASE]);
    F.grid[F.ROWS - 1][3] = 2; F.grid[0][0] = 5;      // something on the bottom row and the top
    F.relics.push('reclaim'); F.applyRelics();
    schk('개간 grows every layer together', rowsOf(),
         [F.ROWS_BASE + 1, F.ROWS_BASE + 1, F.ROWS_BASE + 1, F.ROWS_BASE + 1, F.ROWS_BASE + 1]);
    schk('the row width never changes', F.grid[F.ROWS - 1].length, F.COLS);
    schk('what was on the board stays put', [F.grid[F.ROWS_BASE - 1][3], F.grid[0][0]], [2, 5]);
    schk('and the new row comes up empty', F.grid[F.ROWS - 1].every(v => v === -1), true);
    const grown = F.ROWS;
    F.applyRelics(); F.applyRelics();
    schk('recomputing does not grow it again', F.ROWS, grown);
    // losing the relic to the slot cap must not delete the rows it bought
    F.relics = []; F.applyRelics();
    schk('the board never shrinks', F.ROWS, grown);
    F.resetRun();
    schk('but a new run starts over', F.ROWS, F.ROWS_BASE);
    F.relics.push('reclaim'); F.relics.push('big_reclaim'); F.applyRelics();
    schk('they stack', F.ROWS, F.ROWS_BASE + 3);
    F.resetRun(); F.relics.push('big_reclaim','big_reclaim','big_reclaim'); F.applyRelics();
    schk('and stop at the ceiling', F.ROWS, F.ROWS_MAX);
    // a grown board survives a save/load with its contents
    F.resetRun(); F.relics.push('big_reclaim'); F.applyRelics();
    F.grid[F.ROWS - 1][2] = 4;
    const blob = JSON.parse(JSON.stringify(F.serializeRun()));
    F.resetRun(); F.restoreRun(blob); F.applyRelics();
    schk('a grown board round-trips', [F.ROWS, F.grid.length, F.grid[F.ROWS - 1][2]],
         [F.ROWS_BASE + 2, F.ROWS_BASE + 2, 4]);
    schk('and the extra room is really usable', F.emptyCells().length, F.ROWS * F.COLS - 1);
    F.resetRun();
  })();

  // ---- the info panel has to show what the shop was the only place to see ----
  (() => {
    F.mode = 'rush'; F.resetRun(); F.graftArmed = false;
    const ids = Object.keys(F.RELICS).slice(0, 2);
    for (const id of ids) F.relics.push(id);
    F.pickTrait('big_pocket');                 // widens the shelf after the shop has closed
    F.openInfo('relics');
    const cnt = document.querySelector('.inf-count');
    schk('the relic tab states the shelf', !!cnt, true);
    schk('and counts what is on it', /2/.test(cnt.textContent), true);
    schk('and the cap the trait just widened',
         cnt.textContent.includes(String(F.relicCap())), true);

    // graft is a charge; having TAKEN it must not also put it in the standing list
    F.pickTrait('graft');                      // now it really is in `traits`
    schk('graft was taken', F.traits.some(t => t.id === 'graft'), true);
    const listed = () => { F.openInfo('traits');
      return [...document.querySelectorAll('#info-body .inf-body b')].map(b => b.textContent); };
    const withCharge = listed();
    schk('넓은 주머니 is listed', withCharge.some(n => n.startsWith('넓은 주머니')), true);
    schk('an unspent charge shows exactly once',
         withCharge.filter(n => n.startsWith('접붙이기')).length, 1);
    F.doubles = 0;                             // spent it
    schk('and vanishes once spent',
         listed().filter(n => n.startsWith('접붙이기')).length, 0);
    F.closeInfo(); F.resetRun();
  })();

  // ---- a legendary announces itself, and only when one actually turns up ----
  (() => {
    const byTier = {};
    for (const id of Object.keys(F.RELICS)) {
      const t = F.relicTier(F.RELICS[id]);
      (byTier[t] = byTier[t] || []).push(id);
    }
    F.mode = 'rush'; F.resetRun(); F.coins = 9999;
    F.openShop();
    schk('the chime is a real sound, not a typo', F.SFX.names.includes('legend'), true);

    F.shopOffers = (byTier.common || []).slice(0, 3);
    schk('a plain shelf stays quiet', F.announceOffers(), false);

    F.shopOffers = (byTier.uncommon || []).concat(byTier.epic || []).slice(0, 4);
    schk('epic is not legendary', F.announceOffers(), false);
    // unique wears the gold that used to mean legendary, so this is the one most likely to
    // start chiming by accident
    F.shopOffers = (byTier.unique || []).slice(0, 3);
    schk('unique is not legendary either', F.announceOffers(), false);

    F.shopOffers = (byTier.common || []).slice(0, 2).concat([(byTier.legend || [])[0]]);
    schk('a legendary on the shelf announces itself', F.announceOffers(), true);

    // it is tied to the draw, not to the render: buying redraws nothing and must stay silent
    const before = F.shopOffers.slice();
    F.renderShop();
    schk('rendering does not redraw the shelf', F.shopOffers, before);
    F.closeShop(); F.resetRun();
  })();


  // ---- five grades must read as five grades, not as three plus two recolours ----
  (() => {
    const byTier = {};
    for (const id of Object.keys(F.RELICS)) {
      const t = F.relicTier(F.RELICS[id]);
      (byTier[t] = byTier[t] || []).push(id);
    }
    for (const t of F.TIER_KEYS) schk('grade ' + t + ' has relics', (byTier[t] || []).length > 0, true);
    schk('the grades add up to 100%',
         F.TIER_KEYS.reduce((a, t) => a + F.TIERS[t].odds, 0), 100);
    schk('rarer means rarer, all the way down',
         F.TIER_KEYS.every((t, i) => !i || F.TIERS[F.TIER_KEYS[i-1]].odds > F.TIERS[t].odds), true);
    // price IS the grade -- an epic priced like a unique would shine wrong
    schk('every grade owns a price band above the one below it',
         F.TIER_KEYS.every((t, i) => !i ||
           Math.min(...(byTier[t]).map(id => F.RELICS[id].price)) >
           Math.max(...(byTier[F.TIER_KEYS[i-1]]).map(id => F.RELICS[id].price))), true);

    F.mode = 'rush'; F.resetRun(); F.coins = 9999;
    F.openShop();
    F.shopOffers = [byTier.epic[0], byTier.unique[0], byTier.legend[0], byTier.legend[1]];
    F.shopSold.add(byTier.legend[1]);          // getter-only: mutate, do not reassign
    F.renderShop();
    const cards = [...document.querySelectorAll('.offer')];
    const [epic, uniq, leg] = cards;
    const soldLeg = cards[3];
    const cs = (el, pseudo) => getComputedStyle(el, pseudo || null);
    schk('epic is tagged epic',     epic.classList.contains('shine-epic'), true);
    schk('unique is tagged unique', uniq.classList.contains('shine-unique'), true);
    schk('legend is tagged legend', leg.classList.contains('shine-legend'), true);

    // the top two differ from epic STRUCTURALLY, not just in hue
    for (const [what, top] of [['unique', uniq], ['legend', leg]]) {
      schk(what + ' has a tinted body, epic does not',
           cs(top).backgroundImage !== 'none' && cs(epic).backgroundImage === 'none', true);
      schk(what + ' has the thicker rim',
           parseFloat(cs(top).borderTopWidth) > parseFloat(cs(epic).borderTopWidth), true);
      schk(what + ' sweeps faster than epic',
           parseFloat(cs(top, '::after').animationDuration) < parseFloat(cs(epic, '::after').animationDuration), true);
      schk(what + ' sweeps brighter',
           parseFloat(cs(top, '::after').opacity) > parseFloat(cs(epic, '::after').opacity), true);
      schk('only ' + what + ' animates its icon',
           cs(top.querySelector('.of-ic')).animationName !== 'none' &&
           cs(epic.querySelector('.of-ic')).animationName === 'none', true);
    }
    // ...and from EACH OTHER, which is the new risk: one treatment driven by a colour var
    schk('unique and legend are not the same colour',
         cs(uniq).boxShadow !== cs(leg).boxShadow && cs(uniq).backgroundImage !== cs(leg).backgroundImage, true);
    schk('legend breathes faster than unique',
         parseFloat(cs(leg).animationDuration) < parseFloat(cs(uniq).animationDuration), true);
    schk('the three grade labels are three colours',
         new Set(['epic', 'unique', 'legend'].map(t => F.TIERS[t].color)).size, 3);

    schk('a sold legendary stops shouting',
         cs(soldLeg).animationName === 'none' &&
         cs(soldLeg.querySelector('.of-ic')).animationName === 'none' &&
         cs(soldLeg.querySelector('.of-tier')).animationName === 'none' &&
         cs(soldLeg).backgroundImage === 'none', true);
    F.closeShop();
  })();

  // ---- every fruit gets the same ladder ----
  // Banana used to be the only fruit you could actually build around: it had a +1, a +3 and
  // a multiplier, while orange had nothing at all. Measured by APPLYING each relic and
  // reading the state, not by reading its description -- a description can lie.
  (() => {
    F.mode = 'rush'; F.resetRun();
    const solo = { odds: {}, mult: {} };     // fruit -> { amount -> [ids] }
    for (const id of Object.keys(F.RELICS)) {
      F.relics = [id]; F.applyRelics();
      const od = F.oddsMult.map((v, i) => [i, v]).filter(([, v]) => v);
      const mu = F.fruitMult.map((v, i) => [i, +(v - 1).toFixed(2)]).filter(([, v]) => v);
      if (od.length === 1 && !mu.length) {
        const [f, v] = od[0];
        ((solo.odds[f] = solo.odds[f] || {})[v] = (solo.odds[f][v] || [])).push(id);
      }
      if (mu.length === 1 && !od.length) {
        const [f, v] = mu[0];
        ((solo.mult[f] = solo.mult[f] || {})[v] = (solo.mult[f][v] || [])).push(id);
      }
    }
    F.relics = []; F.applyRelics();

    const grade = id => F.relicTier(F.RELICS[id]);
    const missing = { plus1: [], plus3: [], mult: [] }, wrongGrade = [], wrongMult = [];
    for (let f = 0; f < 7; f++) {
      const o = solo.odds[f] || {}, m = solo.mult[f] || {};
      if (!(o[1] || []).length) missing.plus1.push(f); else
        (o[1] || []).forEach(id => { if (grade(id) !== 'uncommon') wrongGrade.push(id + ':+1@' + grade(id)); });
      if (!(o[3] || []).length) missing.plus3.push(f); else
        (o[3] || []).forEach(id => { if (grade(id) !== 'unique') wrongGrade.push(id + ':+3@' + grade(id)); });
      const amounts = Object.keys(m).map(Number);
      if (!amounts.length) missing.mult.push(f);
      else {
        if (!amounts.includes(1.2)) wrongMult.push(f + ':' + amounts.join('/'));
        (m[1.2] || []).forEach(id => { if (grade(id) !== 'epic') wrongGrade.push(id + ':x@' + grade(id)); });
      }
    }
    schk('every fruit has a +1 등장 relic', missing.plus1, []);
    schk('every fruit has a +3 등장 relic', missing.plus3, []);
    schk('every fruit has a score-multiplier relic', missing.mult, []);
    schk('every solo multiplier is the same +1.2', wrongMult, []);
    schk('each rung sits in its own grade', wrongGrade, []);

    // the promotions the design asked for, pinned by name rather than by price band
    schk('손재주 is unique', F.relicTier(F.RELICS.tinkerer), 'unique');
    schk('바나나 농장 is unique', F.relicTier(F.RELICS.banana_grove), 'unique');

    // combo cap
    F.relics = ['streak_amp']; F.applyRelics();
    schk('불꽃 증폭 lifts the combo cap to 3.0', F.STREAK_CAP, 3.0);
    F.relics = []; F.applyRelics();
  })();

  // ---- the coin build ----
  (() => {
    F.mode = 'rush'; F.resetRun();
    const withRelics = (ids, coins) => { F.relics = ids.slice(); F.applyRelics(); F.coins = coins; };

    // 1. coins are worth score, and it tracks the balance LIVE -- applyRelics only runs when
    //    the relic list changes, so baking this in would freeze it at whatever you held then
    withRelics([], 100);
    const plain = F.fruitScore(0);
    withRelics(['rich_eye'], 0);
    schk('broke, the coin relic adds nothing', F.fruitScore(0), plain);
    F.coins = 30;
    schk('30 coins is +3 a fruit', F.fruitScore(0), plain + 3);
    F.coins = 35;
    schk('and it rounds down, per 10', F.fruitScore(0), plain + 3);
    F.coins = 100;
    schk('it follows the balance without re-applying', F.fruitScore(0), plain + 10);

    // 2. interest is capped -- uncapped it compounds into "never buy anything"
    withRelics(['interest'], 20);
    schk('interest pays 1 per 5 held', F.interestDue(), 4);
    F.coins = 1000;
    schk('but never more than the cap', F.interestDue(), F.INTEREST_CAP);
    withRelics(['compound'], 1000);
    schk('the percentage one is capped too', F.interestDue(), F.INTEREST_CAP);
    withRelics([], 1000);
    schk('and with no interest relic there is none', F.interestDue(), 0);

    // 3. the vault is what makes hoarding a real decision, and it is not sold on its own
    withRelics(['interest', 'vault'], 1000);
    schk('the vault lifts the cap', F.interestDue(), F.INTEREST_CAP + 10);
    F.resetRun();
    schk('the vault is not offered with no interest to cap', F.RELICS.vault.requires(), false);
    F.relics = ['compound']; F.applyRelics();
    schk('either interest relic unlocks it', F.RELICS.vault.requires(), true);
    F.relics = []; F.applyRelics();

    // 4. interest is paid on the ROUND, not on every stage, and it really lands
    F.mode = 'rush'; F.resetRun();
    F.relics = ['interest']; F.applyRelics();
    F.coins = 20;
    const paid = F.payInterest();
    schk('paying hands over exactly what was due', F.coins, 24);
    schk('and reports it, so the hint can say so', paid, 4);

    // 4b. ...and stageClear is what has to call it. Testing payInterest() alone leaves the
    //     wiring untested, and the wiring is the whole feature: interest nobody pays is not
    //     a strategy. Driven through a real stage clear, on and off a round boundary.
    const clearAt = (st, held) => {
      F.mode = 'rush'; F.resetRun();
      F.relics = ['interest']; F.applyRelics();
      F.stage = st; F.coins = held;
      F.stageClear();
      return F.coins - held;
    };
    const payoutAt = st => Math.round(F.COIN_PAYOUT(st));
    schk('mid-round pays the stage payout only', clearAt(1, 20), payoutAt(1));
    schk('the round boundary adds interest on top', clearAt(3, 20), payoutAt(3) + 4);
    schk('and interest scales with what was kept', clearAt(3, 5), payoutAt(3) + 1);
    F.closeShop(); F.mode = 'rush'; F.resetRun(); F.relics = []; F.applyRelics();

    // 5. 별자리 왕 takes the whole board, not one colour
    F.resetRun(); F.relics = []; F.applyRelics();
    const fillBoard = () => { for (let r = 0; r < F.ROWS; r++) for (let c = 0; c < F.COLS; c++)
      { F.grid[r][c] = (r + c) % 3; F.special[r][c] = null; F.coinCell[r][c] = 0; } };
    fillBoard();
    const total = F.grid.flat().filter(v => v >= 0).length;
    const onlyOne = F.grid.flat().filter(v => v === 0).length;
    schk('the board holds more than one colour', onlyOne < total, true);
    F.grid[4][4] = 0; F.special[4][4] = 'star';
    F.coins = 0; F.tapItem(4, 4);
    const leftPlain = F.grid.flat().filter(v => v >= 0).length;
    schk('a plain star leaves the other colours', leftPlain > 0, true);

    F.resetRun(); F.relics = ['star_king']; F.applyRelics();
    fillBoard();
    F.grid[4][4] = 0; F.special[4][4] = 'star';
    F.coins = 0; F.tapItem(4, 4);
    schk('별자리 왕 clears the board', F.grid.flat().filter(v => v >= 0).length, 0);
    schk('and pays for every fruit it took', F.coins >= total - 1, true);
    F.resetEffects(); F.relics = []; F.applyRelics(); F.resetRun();
  })();

  // ---- number display: compact only where precision is decoration ----
  schk('full digits get separators',        F.fmtNum(1234567).replace(/\u00a0/g,','), '1,234,567');
  schk('fmtNum rounds',                     F.fmtNum(1234.6), '1,235');
  schk('below the threshold stays exact',   F.fmtShort(9999), F.fmtNum(9999));
  schk('threshold is 10,000, not 1,000',    F.fmtShort(1100), F.fmtNum(1100));
  schk('at the threshold it compacts',      F.fmtShort(10000) !== F.fmtNum(10000), true);
  schk('and stays compacted above it',      F.fmtShort(2489158).length < F.fmtNum(2489158).length, true);
  schk('no 천: 1,100 never shortens',       !/\uCC9C|K/.test(F.fmtShort(1100)), true);
  schk('COMPACT_FROM is the only knob',     F.COMPACT_FROM, 10000);

  // the goal chip trades digits for legibility, never the other way round
  (() => {
    const q = document.getElementById('rb-quota');
    const cellW = () => q.parentElement.clientWidth;
    document.getElementById('rush').classList.remove('hidden');
    F.setQuota(q, 682, 1100);
    schk('a small goal keeps every digit', q.textContent, F.fmtNum(682) + '/' + F.fmtNum(1100));
    F.setQuota(q, 2489158, 4014771);
    schk('a big goal still shows both sides', q.textContent.split('/').length === 2, true);
    schk('and never overflows its box', q.scrollWidth <= cellW() + 1, true);
    schk('nor shrinks past legible', parseFloat(getComputedStyle(q).fontSize) >= 13, true);
    document.getElementById('rush').classList.add('hidden');
  })();

  // ---- how far you got is a record too ----
  try { localStorage.removeItem(F.BEST_STAGE_KEY); } catch (e) {}
  F.resetRun(); F.mode = 'rush'; F.bestStage = 0;
  F.stage = 4; F.recordStage();
  schk('reaching a new best records it', F.bestStage, 4);
  F.stage = 2; F.recordStage();
  schk('a worse run does not overwrite it', F.bestStage, 4);
  F.stage = 9; F.recordStage();
  schk('a better one does', F.bestStage, 9);
  schk('and it persists', +localStorage.getItem(F.BEST_STAGE_KEY), 9);
  F.mode = 'arcade'; F.stage = 30; F.recordStage();
  schk('arcade has no stages to record', F.bestStage, 9);
  F.mode = 'rush'; F.resetRun(); F.mode = 'arcade';

  // ---- grades: rarer tiers really do show up less ----
  F.resetRun(); F.mode = 'rush';
  // built from TIER_KEYS, not written out: a hardcoded list silently stops covering the
  // moment a grade is added, which is exactly what happened when 유니크 went in
  const tierSeen = Object.fromEntries(F.TIER_KEYS.map(t => [t, 0]));
  const tierPool = Object.fromEntries(F.TIER_KEYS.map(t => [t, 0]));
  for (const id of Object.keys(F.RELICS)) tierPool[F.relicTier(F.RELICS[id])]++;
  const SHOPS = 4000;
  for (let i = 0; i < SHOPS; i++)
    for (const id of F.rollOffers(F.SHOP_OFFERS)) tierSeen[F.relicTier(F.RELICS[id])]++;
  // per-relic appearance rate has to fall as the grade rises
  // grade odds are declared, so the measured slot share must match TIERS[t].odds -- and must
  // NOT depend on how many relics that grade holds
  const slots = SHOPS * F.SHOP_OFFERS;
  for (const t of F.TIER_KEYS) {
    const got = tierSeen[t] / slots * 100, want = F.TIERS[t].odds;
    if (Math.abs(got - want) > Math.max(0.6, want * 0.08))
      stackFails.push({case: 'grade share ' + t, got: +got.toFixed(2), want});
  }
  schk('every grade is reachable', Math.min(...Object.values(tierSeen)) > 0, true);

  // the point of drawing grade-first: growing the pool must NOT move the grade odds
  const legendShare = () => {
    let hits = 0, N = 4000;
    for (let i = 0; i < N; i++)
      for (const id of F.rollOffers(F.SHOP_OFFERS))
        if (F.relicTier(F.RELICS[id]) === 'legend') hits++;
    return hits / (N * F.SHOP_OFFERS) * 100;
  };
  const beforePool = legendShare();
  for (let i = 0; i < 40; i++)            // forty more commons, as the pool keeps growing
    F.RELICS['pad_' + i] = { name: 'pad' + i, icon: '·', price: 5, desc: 'x' };
  const afterPool = legendShare();
  for (let i = 0; i < 40; i++) delete F.RELICS['pad_' + i];
  if (Math.abs(afterPool - beforePool) > 0.5)
    stackFails.push({case: 'grade odds survive a bigger pool',
                     got: +afterPool.toFixed(2), want: +beforePool.toFixed(2)});

  // ---- the item-effect relics ----
  F.resetRun(); F.mode = 'rush';
  schk('one bird by default', F.birdFlock, 1);
  schk('straight lines by default', F.crossLine, false);
  F.relics = ['flock','crossing']; F.applyRelics();
  schk('flock sends three', F.birdFlock, 3);
  schk('crossing makes a cross', F.crossLine, true);
  F.relics = []; F.applyRelics();
  schk('and both revert when sold', [F.birdFlock, F.crossLine], [1, false]);

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
 } catch (e) {
  document.title = 'RESULT ' + JSON.stringify({ cases: 0, fails: [], fsFails: [], hist: [1],
    runFails: [], resetLeaks: [], modeFails: [], relicFails: [], oddsFails: [],
    stackFails: [{case: 'threw', got: String(e && e.message), want: 'no throw'}],
    fatal: String((e && e.stack) || e).slice(0, 300) });
 }
}, 900));
</script>
"""
# A duplicate declaration in TEST used to surface only as a bare "NO RESULT" -- the script
# fails to parse, so the load listener never registers and nothing ever sets the title.
_body = TEST.replace('<script>', '').replace('</script>', '')
open('/tmp/_rt_syntax.js', 'w', encoding='utf-8').write(_body)
try:
    _chk = subprocess.run(['node', '--check', '/tmp/_rt_syntax.js'],
                          capture_output=True, text=True, timeout=20)
    if _chk.returncode:
        print('TEST SCRIPT SYNTAX ERROR:'); print(_chk.stderr.strip()[:600]); sys.exit(2)
except (FileNotFoundError, subprocess.TimeoutExpired):
    pass                      # no node available: let the browser be the judge
finally:
    if os.path.exists('/tmp/_rt_syntax.js'): os.remove('/tmp/_rt_syntax.js')

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
if res.get('fatal'): print('  FATAL:', res['fatal'])
print(f"relics  : {len(res['relicFails'])} fail")
if res['relicFails']: print('  ', res['relicFails'][:4])
print(f"run state: {len(res['runFails'])} round-trip fail, {len(res['resetLeaks'])} reset leak")
if res['runFails']: print('  ', res['runFails'][:4])
if res['resetLeaks']: print('   leaked:', res['resetLeaks'])
if res['fails']: print('  e.g.', res['fails'][:3])
print('PASS' if ok and spread < 0.05 else 'FAIL')
sys.exit(0 if ok and spread < 0.05 else 1)
