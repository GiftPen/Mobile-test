#!/usr/bin/env python3
"""The collection has one job beyond looking nice: show that a relic EXISTS without saying
what it does. A locked entry that leaks its name or its effect turns the screen into a
spoiler list, and the player never has the moment the screen is for. It also has to cover
everything -- a grade missing from the tabs is a set of relics nobody can learn about."""
import subprocess, os, re, json, sys

TEST = """<script>
const sleep = ms => new Promise(r => setTimeout(r, ms));
window.addEventListener('load', () => setTimeout(async () => {
 try {
  const F = window.__fs, fails = [];
  const chk = (c, got, want) => { if (JSON.stringify(got) !== JSON.stringify(want))
                                    fails.push({case: c, got, want}); };
  const $ = id => document.getElementById(id);
  const cells = () => [...document.querySelectorAll('#bk-cell, .bk-cell')];
  const text = () => $('bk-body').textContent;

  try { localStorage.removeItem(F.SEEN_KEY); } catch (e) {}
  F.seen = new Set();

  // --- everything that exists is in there, exactly once ---
  const all = F.bookAll();
  const ids = all.map(e => e.id);
  chk('no entry appears twice', ids.length, new Set(ids).size);
  const relicIds = Object.keys(F.RELICS);
  const missing = relicIds.filter(id => !ids.includes(id));
  chk('every relic is in the collection', missing, []);
  const traitIds = Object.keys(F.TRAITS).filter(id => !F.TRAITS[id].meta);
  chk('every standing trait is too', traitIds.filter(id => !ids.includes(id)), []);
  // and every grade has a tab, or a whole grade is unreachable
  F.openBook();
  await sleep(120);
  const tabs = [...document.querySelectorAll('.bktab')].length;
  chk('there is a tab per grade, plus traits', tabs, F.TIER_KEYS.length + 1);

  // --- locked: the shape, and nothing else ---
  const leaked = [], noSilhouette = [];
  for (const t of F.TIER_KEYS.concat('traits')) {
    F.bookTab = t; F.renderBook();
    await sleep(40);
    const body = text();
    for (const e of F.bookEntries(t)) {
      const name = e.o.name;
      const desc = e.trait ? e.o.desc(F.traitEffects(e.o, 1)) : e.o.desc;
      if (name && body.includes(name)) leaked.push(t + '/' + e.id + ' name');
      if (desc && desc.length > 6 && body.includes(desc)) leaked.push(t + '/' + e.id + ' desc');
    }
    const locked = [...document.querySelectorAll('.bk-cell.locked')];
    if (locked.length !== F.bookEntries(t).length) noSilhouette.push(t);
    // the shape must still be THERE -- a blank tile says nothing exists to find
    const ic = locked[0] && locked[0].querySelector('.bk-ic');
    if (ic && !(ic.textContent.length || /url\\(/.test(ic.style.backgroundImage)))
      noSilhouette.push(t + ':empty');
  }
  chk('nothing is known before anything is owned', leaked, []);
  chk('and every entry is drawn locked', noSilhouette, []);
  chk('the progress starts at zero', /\\b0 \\//.test($('bk-prog').textContent), true);

  // --- owning one reveals exactly one ---
  F.mode = 'rush'; F.resetRun(); F.coins = 9999;
  F.openShop();
  F.buyRelic('stamina');
  F.bookTab = F.relicTier(F.RELICS.stamina); F.renderBook();
  await sleep(60);
  chk('buying it reveals it', text().includes(F.RELICS.stamina.name), true);
  chk('and only it', F.seen.size, 1);
  chk('the counter moved', /\\b1 \\//.test($('bk-prog').textContent), true);
  const unlocked = [...document.querySelectorAll('.bk-cell:not(.locked)')].length;
  chk('one card is open', unlocked, 1);

  // --- and it outlives the run, which is the whole point ---
  let stored = null;
  try { stored = JSON.parse(localStorage.getItem(F.SEEN_KEY) || '[]'); } catch (e) {}
  chk('it is written down', stored, ['stamina']);
  F.closeShop(); F.resetRun();
  chk('a new run does not forget it', F.seen.has('stamina'), true);

  // --- a trait counts too ---
  const tid = traitIds[0];
  F.pickTrait(tid);
  chk('picking a trait records it', F.seen.has(tid), true);

  // --- the screen opens and closes from the menu button ---
  F.closeBook();
  await sleep(40);
  chk('closed', $('book').classList.contains('hidden'), true);
  $('btn-book').click();
  await sleep(80);
  chk('the menu button opens it', $('book').classList.contains('hidden'), false);
  $('bk-close').click();
  await sleep(80);
  chk('and the close button closes it', $('book').classList.contains('hidden'), true);

  try { localStorage.removeItem(F.SEEN_KEY); } catch (e) {}
  document.title = 'RESULT ' + JSON.stringify({ fails, total: all.length, tabs });
 } catch (e) { document.title = 'THREW ' + e.message + ' | ' + (e.stack || '').slice(0, 160); }
}, 800));
</script>"""

os.chdir(os.path.dirname(os.path.abspath(__file__)) + '/..')
open('_book.html','w',encoding='utf-8').write(
    open('index.html',encoding='utf-8').read().replace('</body>', TEST + '</body>'))
try:
    out = subprocess.run(['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
        '--headless','--disable-gpu','--no-first-run','--window-size=430,932',
        '--virtual-time-budget=40000','--dump-dom','http://localhost:8899/_book.html?test=1'],
        capture_output=True, text=True, timeout=180).stdout
finally:
    os.remove('_book.html')

m = re.search(r'RESULT (\{.*\})</title>', out, re.S)
if not m:
    t = re.search(r'<title>(.*?)</title>', out, re.S)
    print('NO RESULT', t.group(1)[:300] if t else ''); sys.exit(1)
r = json.loads(m.group(1))
print(f"book: {r['total']}종 · 탭 {r['tabs']}개 · {len(r['fails'])} fail")
for f in r['fails']: print('  ', json.dumps(f, ensure_ascii=False)[:200])
print('PASS' if not r['fails'] else 'FAIL')
sys.exit(0 if not r['fails'] else 1)
