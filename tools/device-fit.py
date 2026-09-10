#!/usr/bin/env python3
"""Nothing may run off the bottom of a phone, at any size, with any board height.
Runs the real page inside an iframe of each device's CSS pixel size (headless Chrome ignores
--window-size for innerWidth, so an iframe is the only way to get a true viewport)."""
import subprocess, os, re, json, sys

DEVICES = [
 ("iPhone SE1",     320, 568), ("Galaxy A",     360, 640), ("iPhone SE2/3", 375, 667),
 ("iPhone 14/15",   390, 844), ("Pixel 4a",     393, 851), ("Pixel 8 Pro",  412, 915),
 ("15 Pro Max",     430, 932), ("Fold 접힘",     344, 882), ("Fold 펼침",    673, 841),
 ("iPad mini",      744,1133), ("iPad Air",     820,1180),
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
      const de = D2.documentElement;
      const cv = D2.getElementById('game').getBoundingClientRect();
      const bar = D2.getElementById('ishop').getBoundingClientRect();
      F.coins = 999; F.openShop();
      setTimeout(() => {
        const card = D2.querySelector('#shop .shop-card').getBoundingClientRect();
        out.push({ name, w, h, rows: F.ROWS,
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
print(f'{"기기":<13}{"화면":>10}{"줄":>4}{"셀":>7}{"세로넘침":>9}{"가로넘침":>9}{"바밖":>6}{"상점밖":>7}')
for r in rows:
    if 'err' in r:
        fails.append(f"{r['name']} {r['rows']}줄: {r['err'][:60]}"); continue
    print(f"{r['name']:<13}{r['w']}x{r['h']:<5}{r['rows']:>4}{r['cell']:>7}"
          f"{r['vScroll']:>9}{r['hScroll']:>9}{r['barOff']:>6}{r['shopOff']:>7}")
    tag = f"{r['name']} {r['w']}x{r['h']} {r['rows']}줄"
    if r['barOff']:   fails.append(f"{tag}: 아이템 바가 {r['barOff']}px 화면 밖")
    if r['boardOff']: fails.append(f"{tag}: 보드가 {r['boardOff']}px 화면 밖")
    if r['shopOff']:  fails.append(f"{tag}: 상점 창이 {r['shopOff']}px 화면 밖")
    if r['vScroll'] > 0: fails.append(f"{tag}: 세로 스크롤 {r['vScroll']}px")
    if r['hScroll'] > 0: fails.append(f"{tag}: 가로 스크롤 {r['hScroll']}px")
    if r['cell'] < MIN_CELL: fails.append(f"{tag}: 셀 {r['cell']}px < {MIN_CELL}px")
print()
if fails:
    print(f'device-fit: {len(fails)} fail')
    for f in fails: print('  ' + f)
    sys.exit(1)
print(f'device-fit: {len(rows)} cases, 0 fail'); print('PASS')
