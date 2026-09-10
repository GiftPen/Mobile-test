#!/usr/bin/env python3
"""The point of this suite is that ADDING A RELIC CANNOT BREAK TRANSLATION.

Descriptions are calls into a language pack, so a relic reusing an existing pattern is
translated everywhere for free. The danger is a relic that needs a NEW pattern: if it is
added to ko only, the fallback quietly serves Korean inside English. That is what this
catches -- by rendering every relic and trait in every language and failing on any Korean
character that survives into a non-Korean pack."""
import subprocess, os, re, json, sys

TEST = """<script>
window.addEventListener('load', () => setTimeout(() => {
 try {
  const F = window.__fs, fails = [];
  const chk = (c, got, want) => { if (JSON.stringify(got) !== JSON.stringify(want))
                                    fails.push({case: c, got, want}); };
  // built from code points, not an escaped literal: this string travels through a Python
  // heredoc on the way here, and a regex escape that survives one layer and not the other
  // silently turns "any uppercase letter" into the test's idea of Korean
  const KO = { test: t => { for (const ch of String(t)) {
    const c = ch.codePointAt(0); if (c >= 0xAC00 && c <= 0xD7A3) return true; } return false; } };
  const langs = Object.keys(F.LANGS);
  chk('there is more than one language', langs.length > 1, true);

  // 1) every pattern the Korean pack defines must exist in every other pack
  const koKeys = Object.keys(F.PACKS.ko).filter(k => k[0] !== '_');
  for (const lg of langs) {
    if (lg === 'ko') continue;
    const missing = koKeys.filter(k => F.PACKS[lg][k] == null);
    chk('every pattern exists in ' + lg, missing, []);
  }

  // 1b) names have no pattern to share -- one per id -- so every id must be present in every
  //     pack, and the lookup must be lazy or the language at load time is baked in
  const koNames = Object.keys(F.PACKS.ko._names || {});
  chk('the Korean name table is populated', koNames.length >= 80, true);
  for (const lg of langs) {
    if (lg === 'ko') continue;
    const missing = koNames.filter(k => !(F.PACKS[lg]._names || {})[k]);
    chk('every name exists in ' + lg, missing, []);
  }
  const ids = Object.keys(F.RELICS).concat(Object.keys(F.TRAITS));
  const noName = ids.filter(id => !koNames.includes(id));
  chk('every relic and trait has a name entry', noName, []);
  F.setLang('ko'); const koFirst = ids.map(id => (F.RELICS[id] || F.TRAITS[id]).name);
  F.setLang('en'); const enFirst = ids.map(id => (F.RELICS[id] || F.TRAITS[id]).name);
  chk('names actually change with the language', koFirst.join() !== enFirst.join(), true);

  // 2) render EVERYTHING in EVERY language; no Korean may survive outside ko
  const leaks = {}, blanks = [];
  for (const lg of langs) {
    F.setLang(lg);
    const bad = [];
    for (const id of Object.keys(F.RELICS)) {
      for (const [what, t] of [['desc', F.RELICS[id].desc], ['name', F.RELICS[id].name]]) {
        if (!t) blanks.push(lg + '/' + id + '.' + what);
        else if (lg !== 'ko' && KO.test(t)) bad.push(id + '.' + what + ': ' + t);
      }
    }
    for (const id of Object.keys(F.TRAITS)) {
      const T = F.TRAITS[id];
      if (!T.name) blanks.push(lg + '/' + id + '.name');
      else if (lg !== 'ko' && KO.test(T.name)) bad.push(id + '.name: ' + T.name);
      for (const mult of [1, 2]) {
        const t = T.desc(F.traitEffects(T, mult));
        if (!t) blanks.push(lg + '/' + id);
        else if (lg !== 'ko' && KO.test(t)) bad.push(id + ' x' + mult + ': ' + t);
      }
    }
    if (bad.length) leaks[lg] = bad.slice(0, 6);
  }
  chk('no description is empty in any language', blanks, []);
  chk('no Korean leaks into another language', leaks, {});

  // 3) a genuinely missing key must fall back to Korean, never to blank or "undefined"
  F.setLang('en');
  const madeUp = F.d('a_pattern_that_does_not_exist');
  chk('an unknown key returns the key, not undefined', madeUp, 'a_pattern_that_does_not_exist');

  // 3b) the picker must be able to show every language, and every code must be real
  const picked = Object.keys(F.LANGS);
  chk('every language has a pack', picked.filter(c => !F.PACKS[c]), []);
  chk('every pack is offered in the picker', Object.keys(F.PACKS).filter(c => !F.LANGS[c]), []);
  chk('every language has a display name', picked.filter(c => !F.LANGS[c]), []);

  // 3c) SCREEN SCAN. Everything above tests the tables; this tests the screens. A string
  //     hardcoded in JS instead of routed through the pack passes every table check and then
  //     shows Korean to an English player -- which is exactly how the mute button slipped
  //     through. Open each panel in a non-Korean language and read what is actually rendered.
  const onScreen = [];
  F.setLang('en');
  F.mode = 'rush'; F.resetRun(); F.running = true; F.coins = 999;
  const panels = [
    ['menu',   () => {}],
    ['pause',  () => { F.renderSettings && F.renderSettings();
                       document.getElementById('pause').classList.remove('hidden'); }],
    ['shop',   () => F.openShop()],
    ['traits', () => F.openTraits()],
    ['info',   () => F.openInfo('relics')],
    ['odds',   () => F.openInfo('fruits')],
    ['over',   () => document.getElementById('overlay').classList.remove('hidden')],
  ];
  for (const [name, open] of panels) {
    try { open(); } catch (e) { onScreen.push(name + ': threw ' + e.message); continue; }
    for (const el of document.querySelectorAll('body *')) {
      if (el.children.length || el.offsetParent === null) continue;   // leaves that are visible
      const t = (el.textContent || '').trim();
      if (!t || !KO.test(t)) continue;
      if (t === '한국어') continue;                 // the language button names itself, correctly
      if (onScreen.length < 12) onScreen.push(name + ': ' + t.slice(0, 40));
    }
  }
  chk('no Korean is rendered on screen in English', onScreen, []);
  for (const id of ['pause', 'shop', 'traits', 'info', 'overlay'])
    document.getElementById(id).classList.add('hidden');
  F.running = false; F.resetRun();

  // 4) the language survives a reload
  F.setLang('en');
  let stored = null; try { stored = localStorage.getItem('fs_lang'); } catch (e) {}
  chk('language is remembered', stored, 'en');
  chk('html lang follows', document.documentElement.lang, 'en');

  // 5) switching back really switches back (descriptions are read, not baked at load)
  F.setLang('ko');
  const anyRelic = Object.keys(F.RELICS)[0];
  chk('switching back restores Korean', KO.test(F.RELICS[anyRelic].desc), true);

  try { localStorage.removeItem('fs_lang'); } catch (e) {}
  document.title = 'RESULT ' + JSON.stringify({ fails, langs, patterns: koKeys.length,
                                                relics: Object.keys(F.RELICS).length,
                                                traits: Object.keys(F.TRAITS).length });
 } catch (e) { document.title = 'THREW ' + e.message; }
}, 700));
</script>"""

os.chdir(os.path.dirname(os.path.abspath(__file__)) + '/..')
open('_i18n.html','w',encoding='utf-8').write(
    open('index.html',encoding='utf-8').read().replace('</body>', TEST + '</body>'))
try:
    out = subprocess.run(['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
        '--headless','--disable-gpu','--no-first-run','--window-size=430,932',
        '--virtual-time-budget=30000','--dump-dom','http://localhost:8899/_i18n.html?test=1'],
        capture_output=True, text=True, timeout=120).stdout
finally:
    os.remove('_i18n.html')

m = re.search(r'RESULT (\{.*\})</title>', out, re.S)
if not m:
    t = re.search(r'<title>(.*?)</title>', out, re.S)
    print('NO RESULT', t.group(1)[:200] if t else ''); sys.exit(1)
r = json.loads(m.group(1))
print(f"i18n: {'/'.join(r['langs'])} · 문형 {r['patterns']}개 · "
      f"유물 {r['relics']} + 특성 {r['traits']} 전수 검사, {len(r['fails'])} fail")
for f in r['fails']:
    print('  ', json.dumps(f, ensure_ascii=False)[:400])
print('PASS' if not r['fails'] else 'FAIL')
sys.exit(0 if not r['fails'] else 1)
