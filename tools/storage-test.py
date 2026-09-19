#!/usr/bin/env python3
"""The game must survive a browser that refuses storage.

Incognito, Safari private mode, locked-down enterprise profiles and sandboxed frames do not
return null from localStorage -- they THROW. One unguarded read during startup (loadBest) was
enough to leave Fruit Star a blank screen: it never booted at all.

Every access goes through the LS helper now. This drives the game with a localStorage that
throws on every call and checks it boots, starts, plays a turn and reaches the shop -- and
that the settings which are normally persisted still apply in-session."""
import subprocess, os, re, json, sys

BLOCK = """<script>
(function(){
  const boom = () => { throw new DOMException('The operation is insecure.', 'SecurityError'); };
  const fake = { getItem: boom, setItem: boom, removeItem: boom, clear: boom, key: boom,
                 get length() { boom(); } };
  try { Object.defineProperty(window, 'localStorage', { get: () => fake, configurable: true }); }
  catch (e) { document.title = 'SETUP-FAIL ' + e.message; }
  window.__errs = [];
  window.addEventListener('error', e => window.__errs.push(String(e.message)));
  window.addEventListener('unhandledrejection', e => window.__errs.push('promise: ' + e.reason));
})();
</script>"""

PROBE = """<script>
window.addEventListener('load', () => setTimeout(() => {
 try {
  const F = window.__fs; const fails = [];
  const chk = (c, got, want) => { if (JSON.stringify(got) !== JSON.stringify(want))
                                    fails.push({ case: c, got, want }); };
  // the storage really must be hostile, or this whole file proves nothing
  let threw = false;
  try { window.localStorage.getItem('x'); } catch (e) { threw = true; }
  chk('the fake storage throws', threw, true);

  chk('the game booted', !!F, true);
  if (F) {
    F.start('rush');
    chk('a run starts', F.running, true);
    // play a few turns through the real input path -- saveRun() fires on every one of them
    const cv = document.getElementById('game');   // not querySelector: the previews are canvases too
    const tap = (r, c) => {
      const b = cv.getBoundingClientRect();
      const x = b.left + (c + 0.5) * b.width / F.COLS;
      const y = b.top + (r + 0.5) * b.height / F.ROWS;
      cv.dispatchEvent(new PointerEvent('pointerdown', { clientX: x, clientY: y, bubbles: true }));
      cv.dispatchEvent(new PointerEvent('pointerup',   { clientX: x, clientY: y, bubbles: true }));
    };
    const before = F.touchCount;
    for (const [r, c] of F.emptyCells().slice(0, 3)) tap(r, c);
    chk('taps actually played turns', F.touchCount > before, true);
    chk('still running after turns', F.running, true);
    F.openShop();
    chk('the shop opens', document.getElementById('shop').classList.contains('hidden'), false);
    F.closeShop();

    // settings still take effect for the session even though they cannot be written down
    const ko = F.d('spawnBase');
    F.setLang('en');
    chk('language still switches without storage', F.d('spawnBase') !== ko, true);
    F.setLang('ko');
    chk('and switches back', F.d('spawnBase'), ko);
    // loadBest is the read that used to kill the boot; it must return a usable number
    let bestThrew = false;
    try { F.loadBest(); } catch (e) { bestThrew = true; }
    chk('loadBest does not throw', bestThrew, false);

    // saving is a no-op rather than a throw
    let saveThrew = false;
    try { F.saveRun(); } catch (e) { saveThrew = true; }
    chk('saveRun does not throw', saveThrew, false);
    // ...and a restore attempt simply finds nothing
    let loadThrew = false, resumed = null;
    try { resumed = F.resumeSavedRun(); } catch (e) { loadThrew = true; }
    chk('resume does not throw', loadThrew, false);
    chk('resume reports no save', !!resumed, false);
  }
  chk('no uncaught errors', (window.__errs || []).slice(0, 4), []);
  document.title = 'RESULT ' + JSON.stringify({ fails });
 } catch (e) { document.title = 'THREW ' + (e && e.message) + ' | ' + String(e && e.stack || '').slice(0, 300); }
}, 700));
</script>"""

LIVE = """<script>
window.addEventListener('load', () => setTimeout(() => {
 try {
  const F = window.__fs; const fails = [];
  const chk = (c, got, want) => { if (JSON.stringify(got) !== JSON.stringify(want))
                                    fails.push({ case: c, got, want }); };
  // The helper must READ AND WRITE real storage, not just swallow errors. A wrapper that
  // recurses into itself (or drops the call) still "passes" a no-storage test while quietly
  // throwing away every save -- best scores, settings, the run itself.
  chk('LS writes reach the real store', (F.LS.set('fs_probe', 'v1'),
      window.localStorage.getItem('fs_probe')), 'v1');
  window.localStorage.setItem('fs_probe2', 'v2');
  chk('LS reads come from the real store', F.LS.get('fs_probe2'), 'v2');
  F.LS.del('fs_probe2');
  chk('LS deletes reach the real store', window.localStorage.getItem('fs_probe2'), null);
  chk('a missing key is null, not a throw', F.LS.get('fs_definitely_absent'), null);

  // and end to end: a real run must survive a save/restore through storage
  F.start('rush');
  F.coins = 4321; F.stage = 5;
  F.saveRun();
  const raw = window.localStorage.getItem(F.SAVE_KEY);
  chk('saveRun actually wrote something', typeof raw === 'string' && raw.length > 20, true);
  F.coins = 0; F.stage = 1;
  chk('resume finds the save', !!F.resumeSavedRun(), true);
  chk('coins came back', F.coins, 4321);
  chk('stage came back', F.stage, 5);
  document.title = 'RESULT ' + JSON.stringify({ fails });
 } catch (e) { document.title = 'THREW ' + (e && e.message) + ' | ' + String(e && e.stack || '').slice(0, 300); }
}, 700));
</script>"""

os.chdir(os.path.dirname(os.path.abspath(__file__)) + '/..')
src = open('index.html', encoding='utf-8').read()
assert '<body>' in src, 'no <body> to inject the storage block before the game'
src = src.replace('<body>', '<body>' + BLOCK, 1)
open('_st.html','w',encoding='utf-8').write(src.replace('</body>', PROBE + '</body>'))
try:
    out = subprocess.run(['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
        '--headless','--disable-gpu','--no-first-run','--window-size=430,932',
        '--virtual-time-budget=30000','--dump-dom','http://localhost:8899/_st.html?test=1'],
        capture_output=True, text=True, timeout=180).stdout
finally:
    os.remove('_st.html')

m = re.search(r'RESULT (\{.*\})</title>', out, re.S)
if not m:
    t = re.search(r'<title>([^<]*)</title>', out)
    print('NO RESULT', t.group(1) if t else '?'); sys.exit(1)
d = json.loads(m.group(1))
print(f"storage(차단): {len(d['fails'])} fail")
for f in d['fails'][:8]: print('   ', json.dumps(f, ensure_ascii=False))
for f in d['fails'][:8]: pass

def run(page, inject, label):
    open(page, 'w', encoding='utf-8').write(
        open('index.html', encoding='utf-8').read().replace('</body>', inject + '</body>'))
    try:
        o = subprocess.run(['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
            '--headless','--disable-gpu','--no-first-run','--window-size=430,932',
            '--virtual-time-budget=30000','--dump-dom',
            f'http://localhost:8899/{page}?test=1'],
            capture_output=True, text=True, timeout=180).stdout
    finally:
        os.remove(page)
    mm = re.search(r'RESULT (\{.*\})</title>', o, re.S)
    if not mm:
        tt = re.search(r'<title>([^<]*)</title>', o)
        print(f'{label}: NO RESULT', tt.group(1) if tt else '?'); return None
    return json.loads(mm.group(1))

live = run('_st2.html', LIVE, 'storage(정상)')
if live is None: sys.exit(1)
print(f"storage(정상): {len(live['fails'])} fail")
for f in live['fails'][:8]: print('   ', json.dumps(f, ensure_ascii=False))
bad = bool(d['fails']) or bool(live['fails'])
print('PASS' if not bad else 'FAIL')
sys.exit(1 if bad else 0)
