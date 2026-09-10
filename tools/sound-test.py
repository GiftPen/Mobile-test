#!/usr/bin/env python3
"""Sound must never be able to break the game. Headless Chrome has no audio device and never
gets a user gesture, so every play() here runs the not-armed path -- which is exactly the
path a muted player, an old WebView, or a browser that blocks autoplay takes."""
import subprocess, os, re, json, sys

TEST = """<script>
window.addEventListener('load', () => setTimeout(() => {
  const F = window.__fs, fails = [];
  const chk = (c, got, want) => { if (JSON.stringify(got) !== JSON.stringify(want))
                                    fails.push({case: c, got, want}); };
  const S = F.SFX;
  chk('every named sound exists', S.names.length > 0, true);

  // A fresh install must not boot silent. +null is 0 and 0 passes a 0..1 range check, so
  // reading an unset preference the obvious way sets the volume to zero for every new player.
  let fresh = null;
  try { fresh = localStorage.getItem('fs_vol'); } catch (e) {}
  if (fresh === null) chk('a fresh install has audible volume', S.volume > 0, true);
  else chk('(volume was already stored, freshness not testable)', true, true);

  // 1) locked (no gesture yet): every sound must be a silent no-op, not a throw
  const threw = [];
  for (const n of S.names) {
    try { S.play(n, 0); S.play(n, 12); } catch (e) { threw.push(n + ': ' + e.message); }
  }
  chk('nothing throws before the audio context is unlocked', threw, []);
  chk('an unknown sound is ignored', (() => { try { S.play('nope'); return 'ok'; }
                                              catch (e) { return e.message; } })(), 'ok');

  // 2) unlocked, then muted -- still silent, still no throw
  S.unlock();
  S.setMuted(true);
  const threw2 = [];
  for (const n of S.names) { try { S.play(n, 3); } catch (e) { threw2.push(n); } }
  chk('nothing throws while muted', threw2, []);
  chk('muted sticks', S.muted, true);

  // 3) the mute preference survives a reload (it is what a silent-phone player sets once)
  let stored = null;
  try { stored = localStorage.getItem('fs_mute'); } catch (e) {}
  chk('mute is remembered', stored, '1');
  S.setVolume(0.4);
  let sv = null; try { sv = localStorage.getItem('fs_vol'); } catch (e) {}
  chk('volume is remembered', +sv, 0.4);
  chk('volume is clamped low', (S.setVolume(-5), S.volume), 0);
  chk('volume is clamped high', (S.setVolume(9), S.volume), 1);
  S.setMuted(false); S.setVolume(0.7);

  // 4) the game itself still runs a full turn with sound wired in
  let gameThrew = null;
  try {
    F.mode = 'rush'; F.resetRun(); F.running = true;
    F.scorePop(10, 5);
    F.addCoins(3, 0, 0);
    F.applyRelics();
  } catch (e) { gameThrew = e.message; }
  chk('a scoring turn survives the sound layer', gameThrew, null);

  // 5) with a live context, every sound must really synthesise -- and the voice cap must
  //    hold. One star clearing 40 fruit fires 40 pops; without the cap that is 80 oscillators
  //    at once, which is where cheap phones start crackling.
  const live = S.state === 'running';
  let peak = 0, liveThrew = [];
  if (live) {
    for (const n of S.names) { try { S.play(n, 5); } catch (e) { liveThrew.push(n + ': ' + e.message); } }
    for (let i = 0; i < 120; i++) { S.play('pop', i % 7); peak = Math.max(peak, S.voices); }
    peak = Math.max(peak, S.voices);
  }
  chk('a live context plays every sound without throwing', liveThrew, []);
  chk('the audio context really ran', live, true);
  chk('the voice cap holds under a 120-pop burst', peak <= S.MAX_VOICES, true);

  // A cap that never releases is a cap that silences the game after the first big burst:
  // voices climb to the ceiling, nothing decrements, and every later sound is dropped. So
  // wait for the tails to finish and check the count actually came back down.
  setTimeout(() => {
    const settled = S.voices;
    chk('voices are released once they finish', settled <= 1, true);
    // NOTE: headless freezes the audio clock, so onended never fires here and only the timer
    // path runs. The double-release guard inside claim() is therefore NOT covered by this
    // suite -- it only matters in a real browser where both fire. This at least catches the
    // symptom if it ever does go wrong.
    chk('the voice count never goes negative', settled >= 0, true);
    if (live) { S.play('pop', 0); chk('and sound still works afterwards', S.voices > settled, true); }
      try { localStorage.removeItem('fs_vol'); localStorage.removeItem('fs_mute'); } catch (e) {}
    document.title = 'RESULT ' + JSON.stringify({ fails, sounds: S.names.length,
                                                  state: S.state, peakVoices: peak, settled });
  }, 1200);
}, 700));
</script>"""

os.chdir(os.path.dirname(os.path.abspath(__file__)) + '/..')
open('_snd.html','w',encoding='utf-8').write(
    open('index.html',encoding='utf-8').read().replace('</body>', TEST + '</body>'))
try:
    out = subprocess.run(['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
        '--headless','--disable-gpu','--no-first-run','--mute-audio','--window-size=430,932',
        '--autoplay-policy=no-user-gesture-required',   # lets the context actually run, so the
                                                        # real synthesis path is exercised
        '--virtual-time-budget=30000','--dump-dom','http://localhost:8899/_snd.html?test=1'],
        capture_output=True, text=True, timeout=120).stdout
finally:
    os.remove('_snd.html')

m = re.search(r'RESULT (\{.*?\})</title>', out, re.S)
if not m: print('NO RESULT'); sys.exit(1)
r = json.loads(m.group(1))
print(f"sound: {r['sounds']}종 · 컨텍스트 {r['state']} · 최대 보이스 {r['peakVoices']} → 잔여 {r['settled']}, {len(r['fails'])} fail")
for f in r['fails']: print('  ', f)
print('PASS' if not r['fails'] else 'FAIL')
sys.exit(0 if not r['fails'] else 1)
