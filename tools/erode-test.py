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

    // ---- every other thing that writes to a cell has to respect the lock ----
    // The wall behaviour is inherited rather than declared -- a locked cell holds grid === -1
    // and the collectors all want grid !== -1 -- which is cheap but means any NEW path that
    // writes to the board is a hole until someone checks. rollZones was exactly that: it
    // offered every cell and put bonus zones on ground nobody could reach.
    const lockedCells = () => { const o = [];
      for (let r = 0; r < F.ERODE_ROWS; r++) for (let c = 0; c < F.COLS; c++)
        if (F.eroded[r][c]) o.push([r, c]);
      return o; };
    const lockedTouched = () => lockedCells()
      .filter(([r, c]) => F.grid[r][c] !== -1 || F.special[r][c])
      .map(([r, c]) => r + ',' + c);
    const clearFree = () => { for (let r = 0; r < F.ROWS; r++) for (let c = 0; c < F.COLS; c++)
      if (!F.eroded[r][c]) { F.grid[r][c] = -1; F.special[r][c] = null; F.hp[r][c] = 0; } };
    const setUp = () => { atRound10(); for (let i = 0; i < 3; i++) F.erodeStage();
                          F.busy = false; clearFree(); };

    setUp();
    for (let i = 0; i < 12; i++) F.spawnBuds(6);
    chk('매턴 스폰이 잠긴 칸을 피한다', lockedTouched(), []);

    setUp();
    for (let i = 0; i < 30; i++) F.spawnCracker(1);
    chk('크래커가 잠긴 칸에 생기지 않는다', lockedTouched(), []);

    setUp();
    F.coins = 999; F.armItem('basket');
    { const free = F.emptyCells()[0]; F.placeBoughtItem(free[0], free[1]); }
    chk('과일 바구니가 잠긴 칸을 채우지 않는다', lockedTouched(), []);

    // 바나나 군락 converts NEIGHBOURS, which is a write the flood does not make
    setUp();
    F.relics = ['banana_grove2']; F.applyRelics();
    { const L = lockedCells()[2];
      const nb = [[L[0], L[1]+1], [L[0], L[1]-1], [L[0]+1, L[1]], [L[0]-1, L[1]]]
        .filter(([r, c]) => r >= 0 && r < F.ROWS && c >= 0 && c < F.COLS && !F.eroded[r][c]);
      for (const [r, c] of nb) F.grid[r][c] = 6;
      const vis = Array.from({ length: F.ROWS }, () => Array(F.COLS).fill(false));
      if (nb.length) F.fruitSignature(nb[0][0], nb[0][1], 6, vis, []);
      chk('바나나 군락이 잠긴 칸을 바꾸지 않는다', lockedTouched(), []);
    }

    // a bird flies over walls, but it must not aim AT one
    setUp();
    for (const [r, c] of F.emptyCells().slice(0, 6)) F.grid[r][c] = 1;
    { const aims = [];
      for (let i = 0; i < 30; i++) { const t = F.chooseBirdTarget({}); if (t) aims.push(t); }
      chk('참새가 잠긴 칸을 노리지 않는다',
          aims.filter(([r, c]) => F.eroded[r][c]).length, 0);
      chk('그래도 노릴 과일은 찾는다', aims.length > 0, true);
    }

    // ---- and a bonus zone never lands on ground you cannot use ----
    // rollZones offered every cell on the board; the erosion arrived afterwards. A zone on a
    // locked cell is a bonus that cannot be reached.
    atRound10();
    for (let i = 0; i < F.ERODE_ROWS; i++) F.erodeStage();
    F.relics = ['golden_city']; F.applyRelics();
    let onLocked = 0;
    for (let n = 0; n < 40; n++) {
      F.rollZones();
      for (const k of F.zoneCells) if (F.eroded[(k / F.COLS) | 0][k % F.COLS]) onLocked++;
    }
    chk('보너스 칸이 잠긴 땅에 생기지 않는다', onLocked, 0);
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
