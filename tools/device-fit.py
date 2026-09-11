#!/usr/bin/env python3
"""Nothing may run off the bottom of a phone, at any size, with any board height.
Runs the real page inside an iframe of each device's CSS pixel size (headless Chrome ignores
--window-size for innerWidth, so an iframe is the only way to get a true viewport)."""
import subprocess, os, re, json, sys

DEVICES = [
 # 보통 폰
 ("iPhone SE1",     320, 568), ("Galaxy A",     360, 640), ("iPhone SE2/3", 375, 667),
 ("iPhone 14/15",   390, 844), ("Pixel 4a",     393, 851), ("Pixel 8 Pro",  412, 915),
 ("15 Pro Max",     430, 932),
 # 폴더블 — 접힘/펼침이 완전히 다른 기기처럼 동작한다
 ("Fold 커버",       344, 882), ("Fold 펼침",     673, 841),
 ("Flip 펼침",       360, 880), ("Flip 커버",     260, 272),
 ("Flip Flex모드",   412, 450),          # 반 접으면 앱 영역이 위쪽 절반만 남는다
 # 태블릿
 ("iPad mini",      744,1133), ("iPad Air",     820,1180),
 # 가로 모드 — 웹은 회전을 막을 수 없다
 ("폰 가로",         844, 390), ("작은 폰 가로",   640, 360),
]
ROWCASES = [8, 12]        # a fresh run, and one fully grown by 개간

HOST = """<!doctype html><meta charset=utf-8><body style="margin:0">
<script>
const D = %s, ROWS = %s; const out = []; const jobs = [];
for (const d of D) for (const r of ROWS) jobs.push([d, r]);
let i = 0;
function next() {
  if (i >= jobs.length) { document.title = 'R ' + JSON.stringify(out); return; }
  const [[name, w, h], rows] = jobs[i++];
  const f = document.createElement('iframe');
  f.style.cssText = `width:${w}px;height:${h}px;border:0;position:absolute;left:0;top:0`;
  f.src = 'index.html?test=1';
  document.body.appendChild(f);
  f.onload = () => setTimeout(() => { try {
    const W = f.contentWindow, D2 = f.contentDocument, F = W.__fs;
    F.mode = 'rush'; D2.getElementById('btn-challenge').click();
    setTimeout(() => {
      if (rows > F.ROWS_BASE) {
        while (F.ROWS < rows) { F.ROWS++; }
        F.layout();
      }
      const guarded = D2.getElementById('rotate').classList.contains('on');
      const de = D2.documentElement;
      const cv = D2.getElementById('game').getBoundingClientRect();
      const bar = D2.getElementById('ishop').getBoundingClientRect();
      F.coins = 999; F.openShop();
      setTimeout(() => {
        const card = D2.querySelector('#shop .shop-card').getBoundingClientRect();
        out.push({ name, w, h, rows: F.ROWS, guarded,
          cell: +(cv.width / 8).toFixed(1),
          vScroll: de.scrollHeight - de.clientHeight,
          hScroll: de.scrollWidth - de.clientWidth,
          barOff: Math.max(0, Math.round(bar.bottom - h)),
          boardOff: Math.max(0, Math.round(cv.bottom - h)),
          shopOff: Math.max(0, Math.round(card.bottom - h)) + Math.max(0, Math.round(-card.top)),
        });
        f.remove(); next();
      }, 220);
    }, 450);
  } catch (e) { out.push({ name, rows, err: String(e) }); f.remove(); next(); } }, 380);
}
next();
</script>""" % (json.dumps(DEVICES), json.dumps(ROWCASES))

os.chdir(os.path.dirname(os.path.abspath(__file__)) + '/..')
open('_dev.html','w',encoding='utf-8').write(HOST)
try:
    out = subprocess.run(['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
        '--headless','--disable-gpu','--no-first-run','--window-size=900,1300',
        '--virtual-time-budget=90000','--dump-dom','http://localhost:8899/_dev.html'],
        capture_output=True, text=True, timeout=300).stdout
finally:
    os.remove('_dev.html')

m = re.search(r'R (\[.*?\])</title>', out, re.S)
if not m: print('NO RESULT'); sys.exit(1)
rows, fails = json.loads(m.group(1)), []
MIN_CELL = 26     # below this a fruit is not a comfortable tap target
print(f'{"기기":<13}{"화면":>10}{"줄":>4}{"셀":>7}{"세로넘침":>9}{"가로넘침":>9}{"바밖":>6}{"상점밖":>7}{"안내":>6}')
for r in rows:
    if 'err' in r:
        fails.append(f"{r['name']} {r['rows']}줄: {r['err'][:60]}"); continue
    print(f"{r['name']:<13}{r['w']}x{r['h']:<5}{r['rows']:>4}{r['cell']:>7}"
          f"{r['vScroll']:>9}{r['hScroll']:>9}{r['barOff']:>6}{r['shopOff']:>7}"
          f"{('세로안내' if r.get('guarded') else '-'):>6}")
    tag = f"{r['name']} {r['w']}x{r['h']} {r['rows']}줄"
    if r.get('guarded'):
        # too short to play: the game must SAY so rather than lay out a broken board
        continue
    if r['barOff']:   fails.append(f"{tag}: 아이템 바가 {r['barOff']}px 화면 밖")
    if r['boardOff']: fails.append(f"{tag}: 보드가 {r['boardOff']}px 화면 밖")
    if r['shopOff']:  fails.append(f"{tag}: 상점 창이 {r['shopOff']}px 화면 밖")
    if r['vScroll'] > 0: fails.append(f"{tag}: 세로 스크롤 {r['vScroll']}px")
    if r['hScroll'] > 0: fails.append(f"{tag}: 가로 스크롤 {r['hScroll']}px")
    if r['cell'] < MIN_CELL: fails.append(f"{tag}: 셀 {r['cell']}px < {MIN_CELL}px")

# ---- phase 1b: notches. Headless resolves env() to 0, so the real insets are injected ----
# viewport-fit=cover means innerHeight includes the strip behind the notch and the home
# indicator. The test that matters is not "is the HUD below the notch" -- body padding does
# that on its own -- but "does layout() know", which only shows on a height-constrained board:
# the same viewport with insets must produce a SMALLER board than without.
NOTCHED = [
 ("iPhone 14",     390, 844, 47, 34), ("iPhone 14 Pro", 393, 852, 59, 34),
 ("15 Pro Max",    430, 932, 62, 34), ("iPhone SE2",    375, 667, 20,  0),
 ("Pixel 8",       412, 915, 24, 24), ("짧은 화면+큰노치", 390, 700, 60, 34),
]
NOTCH_HOST = """<!doctype html><meta charset=utf-8><body style="margin:0">
<script>
const D = %s; const out = []; let i = 0;
function next() {
  if (i >= D.length) { document.title = 'R ' + JSON.stringify(out); return; }
  const [name, w, h, top, bot] = D[i++];
  const f = document.createElement('iframe');
  f.style.cssText = `width:${w}px;height:${h}px;border:0;position:absolute;left:0;top:0`;
  f.src = 'index.html?test=1'; document.body.appendChild(f);
  f.onload = () => setTimeout(() => { try {
    const W = f.contentWindow, D2 = f.contentDocument, F = W.__fs;
    F.mode = 'rush'; D2.getElementById('btn-challenge').click();
    setTimeout(() => {
      // grow the board so HEIGHT is the binding constraint -- otherwise width decides and the
      // insets make no difference to the size, and the check proves nothing
      while (F.ROWS < F.ROWS_MAX) F.ROWS++;
      F.layout();
      const flat = F.boardPx !== undefined ? null : null;
      const noInset = D2.getElementById('game').getBoundingClientRect().width;
      const st = D2.createElement('style');
      st.textContent = `body { padding-top:${top}px !important; padding-bottom:${bot}px !important; }`;
      D2.head.appendChild(st);
      F.layout();
      const withInset = D2.getElementById('game').getBoundingClientRect().width;
      const t0  = D2.getElementById('top').getBoundingClientRect();
      const bar = D2.getElementById('ishop').getBoundingClientRect();
      const tutPad = parseFloat(getComputedStyle(D2.getElementById('tut')).paddingBottom) || 0;
      out.push({ name, w, h, top, bot,
        insetY: F.insets().y, usableH: F.usableH(),
        board0: Math.round(noInset), board1: Math.round(withInset),
        underNotch: Math.max(0, top - Math.round(t0.top)),
        underHome: Math.max(0, Math.round(bar.bottom) - (h - bot)),
        tutClears: tutPad >= bot });
      f.remove(); next();
    }, 420);
  } catch (e) { out.push({ name, err: String(e) }); f.remove(); next(); } }, 380);
}
next();
</script>""" % json.dumps(NOTCHED)
open('_notch.html','w',encoding='utf-8').write(NOTCH_HOST)
try:
    nout = subprocess.run(['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
        '--headless','--disable-gpu','--no-first-run','--window-size=900,1100',
        '--virtual-time-budget=45000','--dump-dom','http://localhost:8899/_notch.html'],
        capture_output=True, text=True, timeout=200).stdout
finally:
    os.remove('_notch.html')

print('--- 노치/홈 인디케이터 (인셋 주입 · 12줄로 높이 제약) ---')
shrank = []
nm = re.search(r'R (\[.*?\])</title>', nout, re.S)
if not nm:
    fails.append('노치 검사: 결과 없음')
else:
    for r in json.loads(nm.group(1)):
        if 'err' in r: fails.append(f"노치 {r['name']}: {r['err'][:70]}"); continue
        print(f"  {r['name']:<16} 인셋 {r['top']:>2}/{r['bot']:<2} · 쓸 높이 {r['usableH']:>4}"
              f" · 보드 {r['board0']}→{r['board1']} · 노치밑 {r['underNotch']} · 홈밑 {r['underHome']}")
        want = r['top'] + r['bot']
        if r['insetY'] != want:
            fails.append(f"노치 {r['name']}: 인셋 {r['insetY']} (기대 {want})")
        if r['usableH'] != r['h'] - want:
            fails.append(f"노치 {r['name']}: 쓸 높이 {r['usableH']} (기대 {r['h'] - want})")
        # THE check. Insets must never make the board bigger, and where HEIGHT is what limits
        # it they must make it smaller. On a tall phone width binds even at 12 rows, so the
        # size legitimately does not move there -- asserting it would fail for the right reason.
        widthLimit = min(r['w'] - 24, 520)
        heightBinds = r['board0'] < widthLimit - 1
        if r['board1'] > r['board0']:
            fails.append(f"노치 {r['name']}: 인셋을 넣었는데 보드가 커짐 ({r['board0']}→{r['board1']})")
        elif heightBinds and r['board1'] >= r['board0']:
            fails.append(f"노치 {r['name']}: 높이 제약인데 인셋을 넣어도 그대로 "
                         f"({r['board0']}→{r['board1']}) — layout()이 인셋을 모르고 있음")
        shrank.append(r['board1'] < r['board0'])
        if r['underNotch']: fails.append(f"노치 {r['name']}: HUD가 노치 밑으로 {r['underNotch']}px")
        if r['underHome']:  fails.append(f"노치 {r['name']}: 아이템 바가 홈 인디케이터를 {r['underHome']}px 침범")
        if not r['tutClears']:
            fails.append(f"노치 {r['name']}: 튜토리얼 바가 홈 인디케이터를 안 피함")
    # and at least one case must actually exercise the shrink, or the check proves nothing
    if not any(shrank):
        fails.append('노치 검사: 보드가 줄어드는 케이스가 하나도 없음 — 검사가 무의미함')

# ---- phase 2: a foldable resizes the viewport LIVE, mid-run, with no reload ----
FOLD_STEPS = [("Fold 커버",344,882),("Fold 펼침",673,841),("Fold 커버",344,882),
              ("가로 회전",841,673),("폰 가로",844,390),("Flip 펼침",360,880)]
FOLD_HOST = """<!doctype html><meta charset=utf-8><body style="margin:0">
<script>
const S = %s; const out = [];
const f = document.createElement('iframe');
f.style.cssText = 'width:344px;height:882px;border:0;position:absolute;left:0;top:0';
f.src = 'index.html?test=1'; document.body.appendChild(f);
f.onload = () => setTimeout(() => {
  const W = f.contentWindow, D = f.contentDocument, F = W.__fs;
  F.mode = 'rush'; D.getElementById('btn-challenge').click();
  setTimeout(() => {
    F.grid[0][0] = 3; F.grid[2][5] = 6; F.score = 12345;
    F.relics.push('reclaim'); F.applyRelics();          // and a board grown mid-run
    const sig = () => JSON.stringify([F.grid[0][0], F.grid[2][5], F.score, F.ROWS, F.grid.length]);
    const before = sig();
    let i = 0;
    (function step() {
      if (i >= S.length) {
        document.title = 'R ' + JSON.stringify({ out, kept: before === sig(), before, after: sig() });
        return;
      }
      const [name, w, h] = S[i++];
      f.style.width = w + 'px'; f.style.height = h + 'px';
      W.dispatchEvent(new Event('resize'));
      setTimeout(() => {
        try {
          for (let k = 0; k < 5; k++) F.draw();         // must survive drawing at the new size
          const de = D.documentElement;
          const cv = D.getElementById('game').getBoundingClientRect();
          const bar = D.getElementById('ishop').getBoundingClientRect();
          out.push({ name, w, h, guarded: D.getElementById('rotate').classList.contains('on'),
            cell: +(cv.width / 8).toFixed(1), vScroll: de.scrollHeight - de.clientHeight,
            barOff: Math.max(0, Math.round(bar.bottom - h)) });
        } catch (e) { out.push({ name, w, h, crash: String(e).slice(0, 70) }); }
        step();
      }, 260);
    })();
  }, 500);
}, 400);
</script>""" % json.dumps(FOLD_STEPS)

open('_fold.html','w',encoding='utf-8').write(FOLD_HOST)
try:
    fout = subprocess.run(['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
        '--headless','--disable-gpu','--no-first-run','--window-size=1000,1300',
        '--virtual-time-budget=45000','--dump-dom','http://localhost:8899/_fold.html'],
        capture_output=True, text=True, timeout=200).stdout
finally:
    os.remove('_fold.html')

fm = re.search(r'R (\{.*?\})</title>', fout, re.S)
print('\n--- 접었다 펴기 (재로드 없이 실시간) ---')
if not fm:
    fails.append('폴딩 시나리오: 결과 없음')
else:
    fd = json.loads(fm.group(1))
    for r in fd['out']:
        if 'crash' in r:
            print(f"  {r['name']:<12}{r['w']}x{r['h']:<6} CRASH {r['crash']}")
            fails.append(f"{r['name']} {r['w']}x{r['h']}: 리사이즈 중 예외 — {r['crash']}")
            continue
        print(f"  {r['name']:<12}{r['w']}x{r['h']:<6} 셀 {r['cell']:>5}"
              f"{('  세로안내' if r['guarded'] else '        ')}")
        tag = f"폴딩 {r['name']} {r['w']}x{r['h']}"
        if not r['guarded']:
            if r['barOff']:  fails.append(f"{tag}: 아이템 바가 {r['barOff']}px 화면 밖")
            if r['vScroll']: fails.append(f"{tag}: 세로 스크롤 {r['vScroll']}px")
    if not fd['kept']:
        fails.append(f"폴딩 중 게임 상태가 바뀜: {fd['before']} -> {fd['after']}")
    else:
        print(f"  상태 보존 OK {fd['after']}")
    # Not overflowing is not the same as adapting: a build that ignored resize entirely would
    # keep its old canvas and pass every overflow check. The board must actually grow.
    cells = {}
    for r in fd['out']:
        if 'crash' not in r: cells.setdefault(r['name'], []).append(r['cell'])
    folded, opened = cells.get('Fold 커버'), cells.get('Fold 펼침')
    if not folded or not opened:
        fails.append('폴딩 시나리오: 접힘/펼침 측정치 없음')
    else:
        if not (opened[0] > folded[0]):
            fails.append(f"펼쳤는데 보드가 안 커짐 (접힘 {folded[0]}px → 펼침 {opened[0]}px)")
        if len(folded) > 1 and folded[1] != folded[0]:
            fails.append(f"다시 접었을 때 원래 크기로 안 돌아옴 ({folded[0]} → {folded[1]})")
        print(f"  적응 OK 접힘 {folded[0]}px ↔ 펼침 {opened[0]}px")

print()
if fails:
    print(f'device-fit: {len(fails)} fail')
    for f in fails: print('  ' + f)
    sys.exit(1)
print(f'device-fit: {len(rows)} cases, 0 fail'); print('PASS')
