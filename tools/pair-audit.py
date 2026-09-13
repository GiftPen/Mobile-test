#!/usr/bin/env python3
"""Relics and traits move the same numbers. This checks that meeting does not break them.

Three things have gone wrong this way already, each time because a relic and a trait wrote
to state with different RESET rules -- a derived channel is rebuilt on every applyRelics(),
an accumulated one is not, and writing to the wrong kind means the effect multiplies once
per later purchase. So:

  1. recompute stability -- holding any relic, any trait, or any pair that shares a channel,
     recomputing must not change a single derived number. This is the one that catches the
     accumulated/derived mistake.
  2. additivity -- what a pair does must be what each does, combined. Where it is not, the
     difference has to be a declared cap and not a silent loss.
  3. caps -- pairs where the second one adds literally nothing are reported, because a relic
     that cannot do anything next to a trait you already hold is a dead purchase.
  4. wording -- a relic and its trait counterpart SHOULD read the same ("바나나 1만큼 더
     등장"): same effect, same words, and the ladder is easier to follow for it. Two cards in
     the SAME system saying the same thing is different -- that is two ways to buy one thing,
     and nothing tells them apart on the shelf.
"""
import subprocess, os, re, json, sys

TEST = """<script>
window.addEventListener('load', () => setTimeout(() => {
 try {
  const F = window.__fs;
  // every derived number a relic or a trait can move, by name so a mismatch says which
  const CH = {
    touch: () => F.stageTouches(), spawn: () => F.spawnCount(0), slots: () => F.relicCap(),
    shelf: () => F.shelfSize(), bombR: () => F.bombRadius(), birds: () => F.birdFlock,
    starCoin: () => F.starCoinMult, payout: () => F.payoutMult, coinOdds: () => F.coinFruitBonus,
    coinFlat: () => F.coinFlat, chain5: () => F.chainBonus(5), streakStep: () => F.STREAK_STEP,
    streakCap: () => F.STREAK_CAP, ckBonus: () => F.crackerBonus, ckCoin: () => F.crackerCoin,
    bulk: () => F.grapeBulk, cracker: () => F.crackerChance, res: () => F.resonance,
    ckValue: () => F.crackerValue(), interest: () => F.interestDue(),
    coinScore: () => F.coinToScore,
    ckMult: () => F.crackerMult,
    disc: () => F.shopDiscount, rows: () => F.ROWS, ease: () => F.itemEase,
    zoneMult: () => F.zoneMult, zones: () => F.zoneCount(),
  };
  for (let i = 0; i < 7; i++) {
    CH['score' + i] = () => F.fruitScore(i);
    CH['odds' + i]  = () => F.oddsMult[i];
    CH['crown' + i] = () => F.fruitCrown[i];
    CH['onPop' + i] = () => F.stackOnPop[i];
    CH['need' + i]  = () => F.itemNeed(4 + i);
  }
  const KEYS = Object.keys(CH);
  // Channels combine differently, so they cannot be checked by one rule. Saying "together
  // must not exceed the sum" about a MULTIPLIED channel is how this audit reported 151
  // false alarms on its first run -- x2.5 and x1.5 are supposed to reach x3.75.
  const MULT = KEYS.filter(k => /^crown/.test(k) || k === 'disc');
  // additive base through multipliers: fruitScore, and ckValue ever since 화덕 (x2 on the
  // whole thing) joined the flat +N cards -- 100 base +150 from a trait then doubled is 500,
  // which is neither the sum nor the product and is exactly right
  const COMPOSITE = KEYS.filter(k => /^score/.test(k) || k === 'ckValue');
  const snap = () => KEYS.map(k => { const v = CH[k](); return typeof v === 'number' ? +v.toFixed(5) : v; });
  const base = (() => { F.mode = 'rush'; F.resetRun(); F.relics = []; F.traits = []; F.applyRelics(); return snap(); })();

  const setRelic = id => { F.mode='rush'; F.resetRun(); F.relics = id ? [id] : []; F.traits = []; F.applyRelics(); };
  const setTrait = id => { F.mode='rush'; F.resetRun(); F.relics = []; F.traits = []; F.applyRelics();
                           F.graftArmed = false; F.doubles = 0; if (id) F.pickTrait(id); F.applyRelics(); };
  const setBoth  = (r, t) => { F.mode='rush'; F.resetRun(); F.relics = [r]; F.traits = []; F.applyRelics();
                               F.graftArmed = false; F.doubles = 0; F.pickTrait(t); F.applyRelics(); };
  const touched = s2 => KEYS.filter((k, i) => s2[i] !== base[i]);

  // ---- what each one moves, and 1) does a recompute change it ----
  const unstable = [], rMoves = {}, tMoves = {};
  for (const id of Object.keys(F.RELICS)) {
    setRelic(id); const a = snap();
    F.applyRelics(); F.applyRelics();
    if (JSON.stringify(snap()) !== JSON.stringify(a)) unstable.push('relic ' + id);
    rMoves[id] = touched(a);
  }
  for (const id of Object.keys(F.TRAITS)) {
    setTrait(id); const a = snap();
    F.applyRelics(); F.applyRelics();
    if (JSON.stringify(snap()) !== JSON.stringify(a)) unstable.push('trait ' + id);
    tMoves[id] = touched(a);
  }

  // ---- 2) and 3): every pair that shares a channel ----
  const drift = [], swallowed = [];
  let pairs = 0;
  for (const r of Object.keys(F.RELICS)) {
    if (!rMoves[r].length) continue;
    for (const t of Object.keys(F.TRAITS)) {
      const shared = tMoves[t].filter(k => rMoves[r].includes(k));
      if (!shared.length) continue;
      pairs++;
      setRelic(r); const A = snap();
      setTrait(t); const B = snap();
      setBoth(r, t); const AB = snap();
      // stable together, too
      F.applyRelics(); F.applyRelics();
      if (JSON.stringify(snap()) !== JSON.stringify(AB)) { unstable.push(r + '+' + t); continue; }
      let anyMove = false;
      for (const k of shared) {
        const i = KEYS.indexOf(k);
        const a0 = base[i], da = A[i] - a0, db = B[i] - a0, dab = AB[i] - a0;
        if (Math.abs(dab) > Math.abs(da) + 1e-9) anyMove = true;
        // together must never be WORSE than either alone -- that is a swallow whatever the
        // channel is, and it means one of the two cards bought you nothing
        if (Math.abs(dab) + 1e-6 < Math.max(Math.abs(da), Math.abs(db))) {
          swallowed.push(r + '+' + t + '.' + k); continue;
        }
        if (MULT.includes(k)) {
          // x2.5 and x1.5 must land on x3.75: the product, not the sum
          const want = a0 ? (A[i] * B[i]) / a0 : A[i] * B[i];
          if (Math.abs(AB[i] - want) > Math.abs(want) * 1e-4 + 1e-6)
            drift.push(r + '+' + t + '.' + k + ' ' + A[i] + '*' + B[i] + '->' + AB[i] + ' want ' + (+want.toFixed(4)));
        } else if (!COMPOSITE.includes(k)) {
          // additive: no further than both together, or something is counted twice
          if (Math.abs(dab) > Math.abs(da) + Math.abs(db) + 1e-6)
            drift.push(r + '+' + t + '.' + k + ' ' + da + '+' + db + '->' + dab);
        }
        // a composite (fruitScore: an additive base run through multipliers) is checked only
        // for not going backwards -- neither rule describes it, and a wrong rule is worse
        // than none
      }
      if (!anyMove) swallowed.push(r + '+' + t + ' (relic adds nothing)');
    }
  }

  // ---- 4) two cards that say the same thing ----
  F.mode='rush'; F.resetRun(); F.relics = []; F.traits = []; F.applyRelics();
  const rSaid = {}, tSaid = {}, dupes = [], sameSystem = [];
  for (const id of Object.keys(F.RELICS)) (rSaid[F.RELICS[id].desc] = rSaid[F.RELICS[id].desc] || []).push(id);
  for (const id of Object.keys(F.TRAITS)) {
    const t = F.TRAITS[id].desc(F.traitEffects(F.TRAITS[id], 1));
    (tSaid[t] = tSaid[t] || []).push(id);
  }
  // two cards in the same system reading alike is a real problem; a relic and its trait
  // counterpart reading alike is the point
  for (const k in rSaid) if (rSaid[k].length > 1) sameSystem.push('유물 ' + rSaid[k].join(', ') + ': ' + k);
  for (const k in tSaid) if (tSaid[k].length > 1) sameSystem.push('특성 ' + tSaid[k].join(', ') + ': ' + k);
  for (const k in rSaid) if (tSaid[k]) dupes.push(k + ' -> 유물 ' + rSaid[k][0] + ' / 특성 ' + tSaid[k][0]);

  F.relics = []; F.traits = []; F.applyRelics(); F.resetRun();
  document.title = 'RESULT ' + JSON.stringify({
    pairs, unstable, drift,
    swallowed: swallowed.slice(0, 40), swallowedN: swallowed.length,
    dupes, sameSystem, relics: Object.keys(F.RELICS).length, traits: Object.keys(F.TRAITS).length });
 } catch (e) { document.title = 'THREW ' + e.message + ' | ' + (e.stack || '').slice(0, 200); }
}, 800));
</script>"""

os.chdir(os.path.dirname(os.path.abspath(__file__)) + '/..')
open('_pair.html','w',encoding='utf-8').write(
    open('index.html',encoding='utf-8').read().replace('</body>', TEST + '</body>'))
try:
    out = subprocess.run(['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
        '--headless','--disable-gpu','--no-first-run','--window-size=430,932',
        '--virtual-time-budget=300000','--dump-dom','http://localhost:8899/_pair.html?test=1'],
        capture_output=True, text=True, timeout=600).stdout
finally:
    os.remove('_pair.html')

m = re.search(r'RESULT (\{.*\})</title>', out, re.S)
if not m:
    t = re.search(r'<title>(.*?)</title>', out, re.S)
    print('NO RESULT', t.group(1)[:300] if t else ''); sys.exit(1)
r = json.loads(m.group(1))
print(f"pair-audit: 유물 {r['relics']} × 특성 {r['traits']} · 채널 공유 조합 {r['pairs']}쌍")
def show(label, items, fatal=True, limit=8):
    tag = '■' if (items and fatal) else ('참고' if items else 'ok')
    print(f"  {label:<28}{len(items):>4}건  {tag}")
    for x in items[:limit]: print('      ', x)
show('재계산 불안정', r['unstable'])
show('효과 중복 계산', r['drift'])
print(f"  {'상한에 먹힘 (참고)':<26}{r['swallowedN']:>4}건  참고")
for x in r['swallowed'][:8]: print('      ', x)
print(f"  {'유물↔특성 같은 문구 (의도됨)':<24}{len(r['dupes']):>4}건  참고")
show('한쪽 안에서 문구 중복', r['sameSystem'])
bad = r['unstable'] or r['drift'] or r['sameSystem']
print('PASS' if not bad else 'FAIL')
sys.exit(1 if bad else 0)
