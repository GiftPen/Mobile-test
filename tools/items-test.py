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
const sleep = ms => new Promise(r => setTimeout(r, ms));
// headless produces no frames, so rAF never fires -- pump draw() to advance animation
const pump = async (frames, gap) => { for (let i = 0; i < frames; i++)
  { window.__fs.draw(); await sleep(gap || 8); } };
window.addEventListener('load', async () => {
  await sleep(700);
  const F = window.__fs, $ = id => document.getElementById(id), cv = $('game');
  const fails = [];
  const chk = (name, got, want) => { if (JSON.stringify(got) !== JSON.stringify(want))
                                       fails.push({ check: name, got, want }); };
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

  // ---- bird whose target vanishes mid-flight gets one more hop ----
  await pump(20);
  clearBoard();
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

  document.title = 'RESULT ' + JSON.stringify({ fails });
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
    print('NO RESULT'); sys.exit(1)
res = json.loads(m.group(1))
print(f"items: {len(res['fails'])} fail")
for f in res['fails']: print('  ', f)
print('PASS' if not res['fails'] else 'FAIL')
sys.exit(0 if not res['fails'] else 1)
