#!/usr/bin/env python3
"""The goal chip holds a number that grows by orders of magnitude during a run. Before this
was pinned, the 남은 터치 cell slid 149.7 -> 278.3px as digits piled up -- live, on every
touch -- and by round 10 the chips collided and the row was one ⚠️ away from wrapping the
board down. These assert the row is immovable and the text stays readable, at three widths."""
import subprocess, json, re, os, sys

# 1-1 through 12-3 on the real quota curve
CASES = [("1-1",682,1100),("3-2",2800,4516),("5-2",13641,22001),("7-3",99994,161280),
         ("9-1",610809,985175),("10-3",2489158,4014771),("12-3",1626000000,9999999999)]
WIDTHS = [320, 390, 440]
MIN_PX = 16          # below this the goal is not readable at arm's length on a phone

TEST = """<script>
window.addEventListener('load', () => setTimeout(() => {
  const F = window.__fs; F.mode = 'rush';
  document.getElementById('rush').classList.remove('hidden');
  document.getElementById('stats').classList.add('hidden');
  document.getElementById('rs-coin-v').textContent = '128';   // a realistic mid-run purse
  const row = document.querySelector('.rb-row'), q = document.getElementById('rb-quota');
  const out = [];
  for (const w of %s) {
    document.getElementById('rush').style.maxWidth = w + 'px';
    for (const [lab, cur, goal] of %s) {
      F.setQuota(q, cur, goal);
      const r = row.getBoundingClientRect();
      const t = document.getElementById('rb-touch-cell').getBoundingClientRect();
      const c = document.querySelector('.rb-chips').getBoundingClientRect();
      out.push({ w, lab, txt: q.textContent,
                 fs: +parseFloat(getComputedStyle(q).fontSize).toFixed(1),
                 touchX: +(t.left - r.left).toFixed(1), chipX: +(c.left - r.left).toFixed(1),
                 rowH: +r.height.toFixed(1),
                 clip: q.scrollWidth > q.parentElement.clientWidth + 1 });
    }
  }
  document.title = 'RESULT ' + JSON.stringify(out);
}, 700));
</script>"""  % (json.dumps(WIDTHS), json.dumps(CASES))

os.chdir(os.path.dirname(os.path.abspath(__file__)) + '/..')
open('_hf.html','w',encoding='utf-8').write(
    open('index.html',encoding='utf-8').read().replace('</body>', TEST + '</body>'))
try:
    out = subprocess.run(['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
        '--headless','--disable-gpu','--no-first-run','--window-size=430,900',
        '--virtual-time-budget=12000','--dump-dom','http://localhost:8899/_hf.html?test=1'],
        capture_output=True, text=True, timeout=120).stdout
finally:
    os.remove('_hf.html')

m = re.search(r'RESULT (\[.*?\])</title>', out, re.S)
if not m:
    print('NO RESULT'); sys.exit(1)
rows, fails = json.loads(m.group(1)), []

for w in WIDTHS:
    g = [r for r in rows if r['w'] == w]
    # the whole point: neighbours must not care how many digits the goal has
    for key, what in (('touchX','남은 터치 칸'), ('chipX','칩'), ('rowH','행 높이')):
        seen = sorted({r[key] for r in g})
        if len(seen) > 1:
            fails.append(f'{w}px: {what}이(가) 목표 자릿수에 따라 움직임 {seen}')
    for r in g:
        if r['clip']:      fails.append(f"{w}px {r['lab']}: 목표 글자가 칸 밖으로 잘림")
        if r['fs'] < MIN_PX: fails.append(f"{w}px {r['lab']}: {r['fs']}px, {MIN_PX}px 미만 ({r['txt']})")
        if '/' not in r['txt']: fails.append(f"{w}px {r['lab']}: 진행/목표 형태가 아님 ({r['txt']})")
    print(f"--- {w}px --- 터치칸X {g[0]['touchX']} · 칩X {g[0]['chipX']} · 높이 {g[0]['rowH']} 고정")
    for r in g: print(f"   {r['lab']:<5}{r['txt']:<24}{r['fs']:>5}px")

print()
if fails:
    print(f'hud-fit: {len(fails)} fail')
    for f in fails: print('  ' + f)
    sys.exit(1)
print(f'hud-fit: {len(rows)} cases, 0 fail'); print('PASS')
