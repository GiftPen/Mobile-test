#!/usr/bin/env python3
"""오염된 땅: it only exists from round 10, which is where hand-testing does not reach.

What matters is the shape of the sequence, that the two permanent cells cannot be bought, that
paying buys time rather than an exit, and -- the part that is easy to get wrong -- that a
locked cell really is a wall: nothing spawns in it, nothing is placed in it, no blast takes it,
and the board-full check counts it as gone."""
import subprocess, os, re, json, sys

TEST = """<script>
window.addEventListener('load', () => setTimeout(() => {
  const F = window.__fs; const fails = [];
  const chk = (c, got, want) => { if (JSON.stringify(got) !== JSON.stringify(want))
                                    fails.push({ case: c, got, want }); };
  let shape = [];
  try {
    const show = () => { const g = [];
      for (let r = 0; r < F.ERODE_ROWS; r++) { let row = '';
        for (let c = 0; c < F.COLS; c++)
          row += F.eroded[r][c] === 2 ? '#' : (F.eroded[r][c] ? 'X' : '.');
        g.push(row); } return g; };
    const atRound10 = () => { F.mode = 'rush'; F.resetRun();
                              F.stage = (F.ERODE_FROM_ROUND - 1) * F.STAGES_PER_ROUND + 1; };

    // ---- it does not start before its round ----
    F.mode = 'rush'; F.resetRun(); F.stage = 1;
    F.erodeStage();
    chk('10라운드 전에는 잠기지 않는다', F.erodeStep, 0);

    // ---- the zigzag: one in from the wall on even rows, two in on odd ----
    atRound10();
    for (let i = 0; i < F.ERODE_ROWS; i++) F.erodeStage();
    shape = show();
    const want = [];
    for (let r = 0; r < F.ERODE_ROWS; r++) {
      const row = new Array(F.COLS).fill('.');
      const [a, b] = r % 2 === 0 ? [1, F.COLS - 2] : [2, F.COLS - 3];
      row[a] = r === 0 ? '#' : 'X'; row[b] = r === 0 ? '#' : 'X';
      want.push(row.join(''));
    }
    chk('지그재그 모양', shape, want);
    chk('행 수만큼 자라고 멈춘다', F.erodeStep, F.ERODE_ROWS);
    F.erodeStage();
    chk('더 자라지 않는다', F.erodeStep, F.ERODE_ROWS);

    // ---- the permanent pair ----
    F.coins = 9999;
    chk('영구 칸은 살 수 없다', F.unlockCell(0, 1), false);
    chk('영구 칸은 그대로 잠겨 있다', F.eroded[0][1], 2);

    // ---- paying, and the price ----
    const before = F.coins;
    chk('해제할 수 있다', F.unlockCell(2, 1), true);
    chk('값은 정해진 만큼만 나간다', before - F.coins, F.ERODE_COST);
    chk('그 칸은 열렸다', F.eroded[2][1], 0);
    F.coins = F.ERODE_COST - 1;
    chk('모자라면 못 산다', F.unlockCell(4, 1), false);

    // ---- and it comes back: paying buys time, not an exit ----
    F.coins = 9999;
    F.erodeStage();
    chk('비워둔 칸을 다시 잠근다', F.eroded[2][1], 1);
    const full = show().join('|');
    F.erodeStage();
    chk('빈 칸이 없으면 더 잠그지 않는다', show().join('|'), full);

    // ---- a locked cell is a wall ----
    atRound10();
    F.erodeStage(); F.erodeStage();          // rows 0 and 1
    const lockedAt = [1, 2];
    chk('빈 칸 목록에서 빠진다',
        F.emptyCells().some(p => F.eroded[p[0]][p[1]]), false);
    // nothing spawns into it, however many spawns are asked for
    for (let r = 0; r < F.ROWS; r++) for (let c = 0; c < F.COLS; c++)
      if (!F.eroded[r][c]) F.grid[r][c] = -1;
    F.spawnBuds(40);
    chk('과일이 그 안에 생기지 않는다', F.grid[lockedAt[0]][lockedAt[1]], -1);
    // and the board-full check counts it as gone rather than as space
    for (const [r, c] of F.emptyCells()) F.grid[r][c] = 0;
    chk('판이 찼다고 판정된다', F.emptyCells().length, 0);
  } catch (e) { fails.push({ case: 'threw', got: e.message, want: '' }); }
  document.title = 'RESULT ' + JSON.stringify({ fails, shape });
}, 700));
</script>"""

os.chdir(os.path.dirname(os.path.abspath(__file__)) + '/..')
open('_et.html','w',encoding='utf-8').write(
    open('index.html',encoding='utf-8').read().replace('</body>', TEST + '</body>'))
try:
    out = subprocess.run(['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
        '--headless','--disable-gpu','--no-first-run','--window-size=430,932',
        '--virtual-time-budget=30000','--dump-dom','http://localhost:8899/_et.html?test=1'],
        capture_output=True, text=True, timeout=180).stdout
finally:
    os.remove('_et.html')

m = re.search(r'RESULT (\{.*\})</title>', out, re.S)
if not m:
    t = re.search(r'<title>([^<]*)</title>', out)
    print('NO RESULT', t.group(1) if t else '?'); sys.exit(1)
d = json.loads(m.group(1))
for row in d.get('shape', []): print('   ' + row)
print(f"erode: {len(d['fails'])} fail")
for f in d['fails'][:6]: print('   ', json.dumps(f, ensure_ascii=False))
print('PASS' if not d['fails'] else 'FAIL')
sys.exit(1 if d['fails'] else 0)
