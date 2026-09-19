#!/usr/bin/env python3
"""No external requests, and the bundled font actually loads.

Poki blocks outgoing requests by default -- "bundle fonts, assets, and libraries into your
build". Two @font-face rules pointed at jsDelivr, which on Poki means the game renders in a
fallback face, reflowing the layout under the player.

Checks that every resource the page fetches comes from our own origin, and that the Maplestory
face really resolved (document.fonts) rather than silently falling back."""
import subprocess, os, re, json, sys

PROBE = """<script>
window.addEventListener('load', () => setTimeout(async () => {
 try {
  const fails = [];
  const rs = performance.getEntriesByType('resource');
  const here = location.origin;
  const foreign = rs.map(r => r.name).filter(n => !n.startsWith(here) && !n.startsWith('data:')
                                                  && !n.startsWith('blob:'));
  if (foreign.length) fails.push({ case: 'external requests', got: foreign.slice(0, 6) });

  // the test must actually have seen traffic, or "no external requests" is vacuous
  if (rs.length < 3) fails.push({ case: 'no resources observed at all', got: rs.length });

  // the bundled font has to resolve, not fall back
  try { await document.fonts.ready; } catch (e) {}
  const loaded = [...document.fonts].filter(f => f.family === 'Maplestory' && f.status === 'loaded');
  if (!loaded.length)
    fails.push({ case: 'Maplestory did not load',
                 got: [...document.fonts].map(f => f.family + ':' + f.status).slice(0, 6) });
  // both weights are used (700 for headings, 400 for body)
  const weights = loaded.map(f => String(f.weight)).sort();
  if (!(weights.includes('400') && weights.includes('700')))
    fails.push({ case: 'both weights must load', got: weights });

  // and the page is really rendering in it
  const fam = getComputedStyle(document.body).fontFamily || '';
  if (!/Maplestory/.test(fam)) fails.push({ case: 'body is not set in Maplestory', got: fam });

  document.title = 'RESULT ' + JSON.stringify({ fails, reqs: rs.length });
 } catch (e) { document.title = 'THREW ' + (e && e.message); }
}, 1500));
</script>"""

os.chdir(os.path.dirname(os.path.abspath(__file__)) + '/..')
open('_of.html','w',encoding='utf-8').write(
    open('index.html',encoding='utf-8').read().replace('</body>', PROBE + '</body>'))
try:
    out = subprocess.run(['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
        '--headless','--disable-gpu','--no-first-run','--window-size=430,932',
        '--virtual-time-budget=25000','--dump-dom','http://localhost:8899/_of.html?test=1'],
        capture_output=True, text=True, timeout=180).stdout
finally:
    os.remove('_of.html')

m = re.search(r'RESULT (\{.*\})</title>', out, re.S)
if not m:
    t = re.search(r'<title>([^<]*)</title>', out)
    print('NO RESULT', t.group(1) if t else '?'); sys.exit(1)
d = json.loads(m.group(1))
print(f"offline: {len(d['fails'])} fail ({d['reqs']} requests, all same-origin)")
for f in d['fails'][:6]: print('   ', json.dumps(f, ensure_ascii=False))
print('PASS' if not d['fails'] else 'FAIL')
sys.exit(1 if d['fails'] else 0)
