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
window.__err = [];
window.addEventListener('error', e => window.__err.push(e.message + ' @' + e.lineno));
const sleep = ms => new Promise(r => setTimeout(r, ms));
// headless produces no frames, so rAF never fires -- pump draw() to advance animation
const pump = async (frames, gap) => { for (let i = 0; i < frames; i++)
  { window.__fs.draw(); await sleep(gap || 8); } };
window.addEventListener('load', async () => {
 try {
  await sleep(700);
  const F = window.__fs, $ = id => document.getElementById(id), cv = $('game');
  const fails = [];
  const chk = (name, got, want) => { if (JSON.stringify(got) !== JSON.stringify(want))
                                       fails.push({ check: name, got, want }); };
  const over = () => !$('gameover').classList.contains('hidden');
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

  // ---- every way a brick can break has to make the brick sound ----
  // A bird eating one was silent: that path mutates the grid directly instead of going
  // through the chain, so it never reached SFX.play('brick').
  const heard = [];
  const realPlay = F.SFX.play;
  F.SFX.play = (n, a) => { heard.push(n); return realPlay.call(F.SFX, n, a); };

  clearBoard();
  F.busy = false; F.birds.length = 0;
  F.grid[0][0] = F.BRICK; F.hp[0][0] = 1;         // one hit and it is gone
  F.grid[7][7] = 2;
  F.birds.push({ sr: 7, sc: 7, tr: 0, tc: 0, t: 0.99, curve: 1 });
  heard.length = 0;
  await pump(30);
  chk('a bird breaking a brick makes the brick sound', heard.includes('brick'), true);
  chk('and the brick is actually gone', F.grid[0][0], -1);

  // the chain path, which did work, must keep working
  clearBoard();
  F.birds.length = 0;
  F.grid[3][3] = F.BRICK; F.hp[3][3] = 1;
  F.grid[3][4] = 1; F.special[3][4] = 'bomb';     // blast it from next door
  heard.length = 0;
  F.tapItem(3, 4);
  await pump(80, 12);
  chk('a blast next to a brick makes it too', heard.includes('brick'), true);
  chk('and that brick is gone as well', F.grid[3][3], -1);

  // a brick CHIPPED by an adjacent colour pop is a third path again: it survives the hit, so
  // it never reaches the frontier and never reaches the bird. Give it 3 HP so it cannot be
  // confused with a brick that broke.
  F.resetEffects();
  clearBoard();
  F.busy = false;
  F.grid[2][4] = F.BRICK; F.hp[2][4] = 3;
  for (const [r, c] of [[3,5],[4,4],[4,5]]) F.grid[r][c] = 5;   // a cluster to set off
  F.nextColor = 5; F.nextColor2 = 5;
  const r3 = cv.getBoundingClientRect(), cw3 = r3.width / F.COLS, ch3 = r3.height / F.ROWS;
  const x3 = r3.left + 4.5 * cw3, y3 = r3.top + 3.5 * ch3;      // place into (3,4)
  heard.length = 0;
  cv.dispatchEvent(new PointerEvent('pointerdown', {clientX:x3, clientY:y3, bubbles:true}));
  cv.dispatchEvent(new PointerEvent('pointerup',   {clientX:x3, clientY:y3, bubbles:true}));
  await pump(90, 12);
  chk('a brick merely chipped still makes the sound', heard.includes('brick'), true);
  chk('and it survived the chip', F.grid[2][4], F.BRICK);
  chk('but it did lose health', F.hp[2][4] < 3, true);

  // and a blast with no brick anywhere near must not
  clearBoard();
  F.grid[3][4] = 1; F.special[3][4] = 'bomb';
  heard.length = 0;
  F.tapItem(3, 4);
  await pump(80, 12);
  chk('but a blast with no brick near it does not', heard.includes('brick'), false);
  F.SFX.play = realPlay;

  // the brick sound is granular, not one filtered sweep -- a sweep only ever says "shh"
  chk('the brick sound has alternatives to pick from', F.SFX.BRICK_KEYS.length >= 3, true);
  chk('and the chosen one is not the old sweep', F.SFX.brickStyle !== 'old', true);

  // ---- the swoop is paced by the clock, not by the frame rate ----
  // It used to step a fixed amount per FRAME, so it ran at double speed on a 120Hz phone and
  // read as a dart. Two pumps of the SAME wall-clock length, one with many frames and one
  // with few, have to leave the bird in the same place.
  clearBoard();
  F.busy = false;
  const flyFor = async (ms, frames) => {
    F.birds.length = 0;
    F.grid[0][0] = 1;                                    // a target, so it does not retarget
    F.birds.push({ sr: 7, sc: 7, tr: 0, tc: 0, t: 0, curve: 1 });
    const b = F.birds[0], gap = Math.max(1, Math.round(ms / frames));
    await pump(frames, gap);
    return b.t;
  };
  const many = await flyFor(400, 40);      // 40 frames over ~400ms
  const few  = await flyFor(400, 5);       //  5 frames over ~400ms
  chk('frame count does not change how far the bird gets', Math.abs(many - few) < 0.12, true);
  chk('and it does get somewhere in 400ms', many > 0.1 && many < 0.9, true);

  // the swoop is slow enough to read: 400ms must be well short of the whole flight
  chk('the swoop is not over in 400ms', many < 0.5, true);
  // the per-frame version was ~880ms at 60Hz; this is the floor below which it is a dart again
  chk('the flight is a swoop, not a dart', F.BIRD_FLY_MS >= 1000, true);

  // and it does finish, rather than hanging around forever
  F.birds.length = 0;
  F.grid[0][0] = 1;
  F.birds.push({ sr: 7, sc: 7, tr: 0, tc: 0, t: 0, curve: 1 });
  await pump(60, Math.round(F.BIRD_FLY_MS / 50));
  chk('the bird lands', F.birds.length, 0);

  // ---- bird whose target vanishes mid-flight gets one more hop ----
  // settle everything the previous phase left in flight before setting this one up, or the
  // board can be mutated out from under it and the bird finds no target
  await pump(60);
  await sleep(400);
  await pump(20);
  clearBoard();
  F.birds.length = 0;
  F.busy = false;
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

  // ---- the constellation stroke is clock-paced, and a LONG one is not cut short ----
  // prog used to advance 0.19 nodes per FRAME, so the flourish ran at double speed on a
  // 120Hz phone. And the turn-end wait was a flat 1500ms, which a long path outruns -- the
  // exact situation the wait exists to prevent.
  F.resetEffects();
  clearBoard();
  const row = [];
  for (let c = 0; c < 8; c++) row.push([2, c, 0]);
  const strokeProg = async (ms, frames) => {
    F.links.length = 0;
    F.links.push({ nodes: row, color: 1, prog: 0, reached: 0, done: false });
    const L = F.links[0];
    await pump(frames, Math.max(1, Math.round(ms / frames)));
    return L.prog;
  };
  const sMany = await strokeProg(400, 40);
  const sFew  = await strokeProg(400, 5);
  chk('frame count does not change how far the stroke gets', Math.abs(sMany - sFew) < 1.2, true);
  chk('and the stroke does move', sMany > 0.5, true);
  chk('the stroke is a flourish, not a flick', F.STAR_NODE_MS >= 100, true);
  F.resetEffects();

  // a constellation long enough to outrun the old flat 1500ms wait
  await pump(20);
  clearBoard();
  const LONG = 20;
  for (let c = 0; c < 8; c++) F.grid[7][c] = 3;
  for (let c = 0; c < 8; c++) F.grid[6][c] = 3;
  for (let c = 0; c < LONG - 16; c++) F.grid[5][c] = 3;
  F.grid[3][3] = 3; F.special[3][3] = 'star';
  F.nextColor = 6; F.nextColor2 = 6;
  F.busy = false;
  const r2 = cv.getBoundingClientRect(), cw2 = r2.width / F.COLS, ch2 = r2.height / F.ROWS;
  const x2 = r2.left + 4.5 * cw2, y2 = r2.top + 3.5 * ch2;
  cv.dispatchEvent(new PointerEvent('pointerdown', {clientX:x2, clientY:y2, bubbles:true}));
  cv.dispatchEvent(new PointerEvent('pointerup',   {clientX:x2, clientY:y2, bubbles:true}));
  let sawLong = false, floor2 = Infinity, grew2 = false, nodes2 = 0;
  for (let i = 0; i < 400; i++) {
    F.draw();
    const filled = F.grid.flat().filter(v => v !== -1).length;
    if (F.links.length) {
      sawLong = true;
      nodes2 = Math.max(nodes2, F.links[0].nodes.length);
      if (filled < floor2) floor2 = filled;
      else if (filled > floor2) grew2 = true;
    }
    await sleep(16);
  }
  chk('long star: the constellation ran', sawLong, true);
  chk('long star: and it really was long', nodes2 * F.STAR_NODE_MS > 1500, true);
  chk('long star: no fruit spawned mid-draw', grew2, false);
  F.resetEffects();

  // The constellation's coins must be banked when the fruit is CLEARED, not paid out frame by
  // frame as the stroke draws. takeCoin() lifts carried coins off those cells at clear time,
  // so an interrupted stroke used to destroy them -- and the star's own cell never paid.
  F.mode = 'rush'; F.start('rush');
  for (let r = 0; r < F.ROWS; r++) for (let c = 0; c < F.COLS; c++) {
    F.grid[r][c] = (r + c) % 2 === 0 ? 2 : -1; F.special[r][c] = null; F.coinCell[r][c] = 0;
  }
  F.special[4][4] = 'star'; F.grid[4][4] = 2;
  const targets = F.grid.flat().filter(v => v === 2).length;
  F.coins = 0;
  F.tapItem(4, 4);
  for (let i = 0; i < 3; i++) { F.draw(); await sleep(16); }     // barely any animation yet
  const banked = F.coins;
  chk('star: coins are banked at once, not as the stroke draws', banked, targets);
  F.resetEffects();                                             // what a stage change does
  for (let i = 0; i < 60; i++) { F.draw(); await sleep(16); }
  chk('star: cutting the animation short loses none of them', F.coins, banked);

  // ---- the reported bug: a bird landing after the last touch still counts ----
  // BIRD_SCORE lands the quota exactly, and it arrives ~880ms after the turn ended -- later
  // than the 750ms the loss used to be scheduled at.
  await pump(40);
  F.mode = 'rush'; F.resetRun(); F.mode = 'rush'; F.running = true;
  clearBoard();
  F.birds.length = 0;
  F.grid[0][0] = 1;                       // the bird's snack
  F.grid[7][7] = 2;
  const q = F.MODES.rush.quota(1);
  F.stageScore = q - 2;                   // 2 short: exactly one bird snack
  F.touchesLeft = 0;
  F.stage = 1;
  F.birds.push({ sr: 7, sc: 7, tr: 0, tc: 0, t: 0.5, curve: 1 });
  F.busy = true;
  F.closeStage('touches');
  await pump(120, 16);
  chk('last-touch bird: not a game over', over(), false);
  chk('last-touch bird: stage advanced',  F.stage, 2);

  // and the same for a board that a bird empties a cell in
  await pump(40);
  document.getElementById('shop').classList.add('hidden');
  F.resetRun(); F.mode = 'rush'; F.running = true; F.busy = true;
  for (let r = 0; r < F.ROWS; r++) for (let c = 0; c < F.COLS; c++) F.grid[r][c] = 1;
  F.birds.length = 0;
  F.birds.push({ sr: 7, sc: 7, tr: 0, tc: 0, t: 0.5, curve: 1 });
  F.touchesLeft = 5; F.stageScore = 0;
  F.closeStage('board');
  await pump(120, 16);
  chk('bird frees a cell: not a game over', over(), false);

  document.title = 'RESULT ' + JSON.stringify({ fails, err: window.__err.slice(0, 3) });
 } catch (e) {
  document.title = 'RESULT ' + JSON.stringify({ fails: [{check:'threw', got: String(e && e.message), want:'no throw'}], err: [String(e && e.stack || e).slice(0,300)] });
 }
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
if res.get('err'): print('  JS errors:', res['err'])
for f in res['fails']: print('  ', f)
print('PASS' if not res['fails'] else 'FAIL')
sys.exit(0 if not res['fails'] else 1)
