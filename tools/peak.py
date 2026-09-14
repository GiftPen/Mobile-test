#!/usr/bin/env python3
"""빌드별 고점을 스테이지 목표 점수와 나란히 잰다.

bot.py 는 봇이 상점에서 우연히 뽑는 것에 맡기므로, 어떤 빌드가 '완성되면' 얼마나 세지는지는
영영 안 나온다 (코인 빌드 6판 중 2판만 전환 유물을 봤다). 이건 반대로 간다: 빌드를 처음부터
통째로 쥐어주고 라운드 10까지 실제로 플레이시킨 뒤, 매 스테이지 낸 점수를 그 스테이지의
목표와 나눈다. 1.0 이면 딱 목표, 3.0 이면 목표의 3배를 낼 여유가 있다는 뜻.

두 가지를 일부러 이렇게 뒀다:
  * 유물은 1스테이지에 전부 지급한다. 현실의 진행이 아니라 '완성된 빌드의 상한'을 재는 게
    목적이라서다. 그래서 나온 숫자는 상한이지 기대값이 아니다.
  * 목표를 채워도 다음으로 넘어가지 않고 터치를 끝까지 쓴다. 목표를 채우자마자 넘기면 모든
    빌드가 1.0 근처로 나와서 아무것도 구분하지 못한다. 엔진은 스테이지를 닫을 때 목표 달성을
    먼저 보므로 이렇게 해도 진행은 정상이다.

Usage:  python3 -m http.server 8899 &   그리고
        python3 tools/peak.py [--stages 30] [--repeat 2] [빌드이름 ...]
"""
import subprocess, os, re, json, sys, statistics

os.chdir(os.path.dirname(os.path.abspath(__file__)) + '/..')
ARGS = sys.argv[1:]
def opt(name, dflt):
    return int(ARGS[ARGS.index(name) + 1]) if name in ARGS else dflt
STAGES = opt('--stages', 30)
REPEAT = opt('--repeat', 2)
# one build per process: a sweep of thirteen in series is an hour, and they are independent
OUT = ARGS[ARGS.index('--out') + 1] if '--out' in ARGS else '/tmp/peak-last.json'
SKIP = ARGS[ARGS.index('--out') + 1:ARGS.index('--out') + 2] if '--out' in ARGS else []
ONLY = [a for a in ARGS if not a.startswith('--') and not a.isdigit() and a not in SKIP]

TEST = r"""<script>
const sleep = ms => new Promise(r => setTimeout(r, ms));
window.addEventListener('load', () => setTimeout(async () => {
 try {
  const F = window.__fs, $ = id => document.getElementById(id), cv = $('game');
  const STAGES = window.__STAGES, ONLY = window.__ONLY;
  const shown = id => !$(id).classList.contains('hidden');

  // ---- who belongs to which build -------------------------------------------------
  // relicCats() only ever says "score", which cannot tell a cherry build from a banana one,
  // so per-fruit membership is derived the same way categories are: run the relic's own
  // apply() and see which fruit index moved. The seven fruit legendaries move a scalar
  // (peachBurst, kiwiSeed, ...) rather than an array slot, so those are named directly.
  const SCALAR_FRUIT = { cherryPile: 0, citrusFuse: 1, kiwiSeed: 2, lemonFree: 3,
                         grapeBulk: 4, peachBurst: 5, bananaSpread: 6 };
  const ARRAYS = ['oddsMult', 'fruitMult', 'fruitFlat', 'fruitCrown', 'stackOnPop'];
  const snap = () => [ARRAYS.map(k => (F[k] || []).slice()),
                      Object.keys(SCALAR_FRUIT).map(k => String(F[k]))];
  F.mode = 'rush'; F.resetRun(); F.relics = []; F.traits = []; F.applyRelics();
  const tagOf = {};
  for (const id of Object.keys(F.RELICS)) {
    F.relics = []; F.applyRelics(); const a = snap();
    F.relics = [id]; F.applyRelics(); const b = snap();
    const t = new Set(F.relicCats(id));
    for (let i = 0; i < 7; i++)
      for (let k = 0; k < ARRAYS.length; k++)
        if (a[0][k][i] !== b[0][k][i]) t.add('fruit' + i);
    Object.keys(SCALAR_FRUIT).forEach((k, i) => {
      if (a[1][i] !== b[1][i]) t.add('fruit' + SCALAR_FRUIT[k]);
    });
    tagOf[id] = t;
  }
  const traitTag = {};
  for (const id of Object.keys(F.TRAITS)) {
    const t = new Set();
    for (const e of (F.TRAITS[id].effects || [])) {
      t.add(e.stat);
      if (e.target != null) t.add('fruit' + e.target);
      if (/crackerBonus|crackerCoin|crackerChance|crackerMult/.test(e.stat)) t.add('risk');
      if (/coin|payout|interest|discount/i.test(e.stat)) t.add('coin');
      if (/chain|streak/i.test(e.stat)) t.add('combo');
      if (/zone/i.test(e.stat)) t.add('board');
      if (/fruit|odds|stack|score/i.test(e.stat)) t.add('score');
    }
    traitTag[id] = t;
  }
  const price = id => F.priceOf(F.RELICS[id]);
  const has = (t, tag) => t && t.has(tag);
  // a fruit build takes its OWN relics first, then spends what is left on the all-fruit ones
  // (풍요의뿔, 프리즘) -- sorting purely by price would hand all seven builds the same list
  const forTag = (tag, isFruit) => {
    const mine = Object.keys(F.RELICS).filter(id => has(tagOf[id], tag));
    const own = id => !isFruit || [...tagOf[id]].filter(x => /^fruit\d$/.test(x)).length <= 2;
    return mine.sort((a, b) => (own(b) - own(a)) || (price(b) - price(a)));
  };
  const traitsFor = tag => Object.keys(F.TRAITS)
      .filter(id => has(traitTag[id], tag))
      .sort((a, b) => (F.TRAITS[b].tier === 'legend') - (F.TRAITS[a].tier === 'legend'));

  const BUILD_TAGS = { '체리': 'fruit0', '오렌지': 'fruit1', '키위': 'fruit2', '레몬': 'fruit3',
                       '포도': 'fruit4', '복숭아': 'fruit5', '바나나': 'fruit6',
                       '크래커': 'risk', '코인': 'coin', '콤보': 'combo', '보드': 'board',
                       '점수': 'score', '없음': null };

  // ---- the same greedy placement bot.py uses, so the play policy is not a variable -----
  // Every poll costs 8ms of Chrome's VIRTUAL time budget, so patience is not free: at 1500
  // tries a single stuck settle eats twelve seconds of budget and a run dies before it
  // finishes. 600 covers the longest real chain (a 3x3 cracker cascade) with room to spare;
  // anything past that is handled by the spin check below, which waits without tapping.
  const settle = async (max = 600) => {
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

  const out = [];
  for (const name of Object.keys(BUILD_TAGS)) {
    if (ONLY.length && !ONLY.includes(name)) continue;
    const tag = BUILD_TAGS[name];
    F.start('rush');
    await sleep(60); await settle();
    // hand over the whole build at once -- this is a ceiling, not a progression
    const want = tag ? forTag(tag, /^fruit/.test(tag)) : [];
    F.relics = want.slice(0, 10); F.applyRelics();
    F.relics = want.slice(0, F.relicCap()); F.applyRelics();
    const held = F.relics.slice();
    const traitPool = tag ? traitsFor(tag) : [];
    let traitN = 0;
    const rows = [];
    let seenStage = F.stage, best = 0, taps = 0, guard = 0, spin = 0, stuck = null;
    while (F.running && F.stage <= STAGES && guard++ < 2200) {
      if (shown('traits')) {                      // forced, not drawn: a ceiling needs its traits
        const pick = traitPool[traitN++] || F.traitOffers[0];
        F.pickTrait(pick);
        await sleep(20);
        if (shown('traits')) $('traits').classList.add('hidden');
        continue;
      }
      if (shown('shop')) { F.closeShop(); await sleep(40); await settle(); continue; }
      if (F.stage !== seenStage) {                // the engine closed it for us
        rows.push({ st: seenStage, quota: F.rules().quota(seenStage), got: best, taps });
        seenStage = F.stage; best = 0; taps = 0;
        continue;
      }
      best = Math.max(best, F.stageScore);
      const cell = bestCell();
      if (!cell) break;
      // a tap that neither spends a touch nor closes the stage did not land: wait, do not
      // count it, and give up on the run rather than record a stage that never really played
      const before = F.touchesLeft, atStage = F.stage;
      await tap(cell[0], cell[1]);
      if (F.touchesLeft === before && F.stage === atStage && !F.modalOpen()) {
        if (++spin > 40) { stuck = { st: F.stage, busy: F.busy, paused: F.paused,
                                     touchesLeft: F.touchesLeft, empty: F.emptyCells().length }; break; }
        await settle();
        continue;
      }
      spin = 0; taps++;
    }
    rows.push({ st: seenStage, quota: F.rules().quota(seenStage), got: Math.max(best, F.stageScore), taps });
    out.push({ name, reached: F.stage, label: F.stageLabel(F.stage), score: F.score,
               alive: !!F.running, stuck, relics: held, traits: F.traits.map(t => t.id), rows });
    F.gameOver('bot'); await sleep(60); F.showMenu(); await sleep(40);
  }
  document.title = 'RESULT ' + JSON.stringify(out);
 } catch (e) { document.title = 'THREW ' + (e && e.message) + ' | ' + String(e && e.stack || '').slice(0, 250); }
}, 700));
</script>"""


def play(build, stages):
    # the page name carries the pid: thirteen builds run at once and a shared _peak.html had
    # each process deleting the page the others were still loading -- twelve of thirteen runs
    # came back empty before this
    page = f'_peak-{os.getpid()}.html'
    head = (f"<script>window.__STAGES={stages};"
            f"window.__ONLY={json.dumps([build] if build else [])};</script>")
    open(page, 'w', encoding='utf-8').write(
        open('index.html', encoding='utf-8').read().replace('</body>', head + TEST + '</body>'))
    try:
        out = subprocess.run(['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
            '--headless', '--disable-gpu', '--no-first-run', '--window-size=430,932',
            '--virtual-time-budget=2400000', '--dump-dom',
            f'http://localhost:8899/{page}?test=1'],
            capture_output=True, text=True, timeout=2700).stdout
    except subprocess.TimeoutExpired:
        return None
    finally:
        try: os.remove(page)
        except OSError: pass
    m = re.search(r'RESULT (\[.*\])</title>', out, re.S)
    if not m:
        t = re.search(r'<title>(.*?)</title>', out, re.S)
        print(f'  {build}: 결과 없음 — ' + (t.group(1)[:200] if t else ''))
        return None
    return json.loads(m.group(1))


BUILDS = ['체리', '오렌지', '키위', '레몬', '포도', '복숭아', '바나나',
          '크래커', '코인', '콤보', '보드', '점수', '없음']

if '--report' in ARGS:                      # 병렬로 돌린 결과 파일들을 한 표로
    import glob
    runs = []
    for f in sorted(glob.glob(ARGS[ARGS.index('--report') + 1])):
        runs += json.load(open(f))
    todo = [b for b in BUILDS if any(r['name'] == b for r in runs)]
else:
    todo = ONLY or BUILDS
if '--report' not in ARGS:
    print(f'빌드 {len(todo)}종 × {REPEAT}판 · 최대 {STAGES}스테이지 (라운드 {STAGES//3})')
runs = runs if '--report' in ARGS else []
for b in (todo if '--report' not in ARGS else []):
    for i in range(REPEAT):
        r = play(b, STAGES)
        if r: runs += r
        else: print(f'  {b} {i+1}번째: 실패')
if not runs:
    sys.exit('측정 실패')
if '--report' not in ARGS: json.dump(runs, open(OUT, 'w'))

BUCKETS = [(8, 12), (13, 18), (19, 24), (25, 30)]
def lab(a, b): return f'{(a-1)//3+1}~{(b-1)//3+1}R'
print(f"\n{'빌드':<8}{'도달':>7}{'생존':>5}", end='')
for a, b in BUCKETS: print(f'{lab(a,b):>9}', end='')
print(f"{'최종점수':>14}")
print('  ' + '-' * 72)
print('  (숫자 = 그 구간 스테이지에서 낸 점수 ÷ 그 스테이지 목표. 1.0 = 딱 맞춤)')
for name in todo:
    mine = [r for r in runs if r['name'] == name]
    if not mine: continue
    reach = statistics.median([r['reached'] for r in mine])
    alive = sum(1 for r in mine if r['alive'])
    print(f"{name:<8}{reach:>7.0f}{alive:>4}/{len(mine)}", end='')
    for a, b in BUCKETS:
        rat = [x['got'] / x['quota'] for r in mine for x in r['rows']
               if a <= x['st'] <= b and x['quota']]
        print(f"{(f'{statistics.median(rat):.2f}' if rat else '-'):>9}", end='')
    print(f"{statistics.median([r['score'] for r in mine]):>14,.0f}")
print(f"\n원자료 -> {OUT}")
