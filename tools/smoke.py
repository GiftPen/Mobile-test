#!/usr/bin/env python3
"""Random taps at the real canvas for a while: catches anything that throws under input the
suites never think to send. Lived in /tmp and got lost; it belongs with the others."""
import subprocess, os, re, sys

TEST = """<script>
window.__err = [];
window.addEventListener('error', e => window.__err.push(String(e.message)));
window.addEventListener('unhandledrejection', e => window.__err.push('rej:' + e.reason));
(function(){ const oe = console.error; console.error = function(){
  window.__err.push([].join.call(arguments, ' ')); oe.apply(console, arguments); }; })();
const sleep = ms => new Promise(r => setTimeout(r, ms));
window.addEventListener('load', () => setTimeout(async () => {
  const F = window.__fs, cv = document.getElementById('game');
  document.getElementById('btn-arcade').click();
  const b = cv.getBoundingClientRect();
  for (let i = 0; i < 400; i++) {
    const x = b.left + Math.random() * b.width, y = b.top + Math.random() * b.height;
    cv.dispatchEvent(new PointerEvent('pointerdown', {clientX:x, clientY:y, bubbles:true}));
    // headless renders no frames, so pump draw() or nothing that waits on it advances
    if (i % 20 === 0) { for (let k = 0; k < 6; k++) F.draw(); await sleep(16); }
  }
  document.title = 'SMOKE ' + JSON.stringify({ nerr: window.__err.length,
                                               errs: window.__err.slice(0, 4), score: F.score });
}, 700));
</script>"""

os.chdir(os.path.dirname(os.path.abspath(__file__)) + '/..')
open('_sm.html','w',encoding='utf-8').write(
    open('index.html',encoding='utf-8').read().replace('</body>', TEST + '</body>'))
try:
    out = subprocess.run(['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
        '--headless','--disable-gpu','--no-first-run','--window-size=430,932',
        '--virtual-time-budget=30000','--dump-dom','http://localhost:8899/_sm.html?test=1'],
        capture_output=True, text=True, timeout=150).stdout
finally:
    os.remove('_sm.html')

m = re.search(r'SMOKE (\{.*\})</title>', out, re.S)
if not m: print('NO RESULT'); sys.exit(1)
import json
r = json.loads(m.group(1))
print(f"smoke: 400 random taps, {r['nerr']} error(s), score {r['score']}")
for e in r['errs']: print('  ', e[:160])
print('PASS' if not r['nerr'] else 'FAIL')
sys.exit(0 if not r['nerr'] else 1)
