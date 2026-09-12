#!/usr/bin/env python3
"""One coin, everywhere. The emoji was left behind in nine places when the art was wired in,
so what is checked here is that no coin site can drift again: after the art loads, the only
places a coin emoji may still survive are relic ICONS (mint/dust/gold_vein), which are emoji
like every other relic icon. Every other coin in the UI must be a .cn node carrying the art."""
import subprocess, os, re, json, sys

TEST = """<script>
const sleep = ms => new Promise(r => setTimeout(r, ms));
window.addEventListener('load', () => setTimeout(async () => {
 try {
  const F = window.__fs, fails = [];
  const chk = (c, got, want) => { if (JSON.stringify(got) !== JSON.stringify(want))
                                    fails.push({case: c, got, want}); };
  const COIN = '\\u{1FA99}';
  const ICON_OK = ['of-ic', 'inf-ic'];        // a relic's own icon may be a coin emoji
  // every text node still showing the emoji, by the class of the element holding it
  const strays = () => {
    const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT), out = [];
    for (let n; (n = w.nextNode());) {
      if (!n.data.includes(COIN)) continue;
      const el = n.parentElement;
      if (!el || /SCRIPT|STYLE|TITLE/.test(el.tagName)) continue;   // source text is not UI
      if (el.closest('.hidden') || ICON_OK.some(c => el.classList.contains(c))) continue;
      out.push((el.id || el.className || el.tagName) + ': ' + n.data.trim().slice(0, 24));
    }
    return out;
  };
  const coins = () => [...document.querySelectorAll('.cn')].filter(e => !e.closest('.hidden'));
  // the art actually reached the DOM, not just the canvas
  const painted = () => coins().filter(e => {
    const bg = getComputedStyle(e).backgroundImage;
    return bg && bg !== 'none' && bg.includes('coin');
  }).length;

  chk('the art loaded', !!F.coinReady(), true);
  chk('and the DOM was told', document.body.classList.contains('coin-art'), true);

  // --- in play: the HUD coin chip ---
  F.start('rush');
  await sleep(150);
  F.coins = 42; F.updateHUD();
  await sleep(60);
  chk('the HUD coin is art', painted() > 0, true);
  chk('no stray emoji in play', strays(), []);

  // --- the shop: chips, prices, reroll, and the item-shop buttons ---
  F.coins = 999; F.openShop();
  await sleep(200);
  const shopCoins = painted();
  chk('the shop is full of coin art', shopCoins >= 6, true);
  chk('no stray emoji in the shop', strays(), []);

  // --- full shelf: the "no slot" price line is a different string entirely ---
  while (F.relics.length < F.relicCap() + 1) F.relics.push('one_cherry');
  F.applyRelics(); F.renderShop();
  await sleep(120);
  chk('no stray emoji on a full shelf', strays(), []);

  // --- the info panel's sell buttons ---
  F.openInfo('relics');
  await sleep(150);
  chk('the sell buttons carry art', painted() > shopCoins, true);
  chk('no stray emoji in the relic list', strays(), []);
  F.closeInfo();

  // --- and in every language, since the strings come from the language packs ---
  const perLang = {};
  for (const lg of ['ko', 'en', 'ja', 'zh']) {
    F.setLang(lg); F.renderShop();
    await sleep(120);
    F.openInfo('relics');
    await sleep(120);
    perLang[lg] = strays();
    F.closeInfo();
  }
  F.setLang('ko');
  chk('no stray emoji in any language', perLang, {ko: [], en: [], ja: [], zh: []});

  // --- the round-clear payout ---
  F.closeShop();
  await sleep(80);
  F.coins = 7; F.updateHUD();          // updateHUD is what writes the payout line
  await sleep(80);
  chk('the payout line is art', document.querySelectorAll('#rn-coin .cn').length, 1);
  chk('no stray emoji on the payout line',
      document.getElementById('rn-coin').textContent.includes(COIN), false);

  document.title = 'RESULT ' + JSON.stringify({ fails, seen: painted() });
 } catch (e) { document.title = 'THREW ' + e.message + ' | ' + (e.stack || '').slice(0, 200); }
}, 800));
</script>"""

os.chdir(os.path.dirname(os.path.abspath(__file__)) + '/..')
open('_coin.html','w',encoding='utf-8').write(
    open('index.html',encoding='utf-8').read().replace('</body>', TEST + '</body>'))
try:
    out = subprocess.run(['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
        '--headless','--disable-gpu','--no-first-run','--window-size=430,932',
        '--virtual-time-budget=40000','--dump-dom','http://localhost:8899/_coin.html?test=1'],
        capture_output=True, text=True, timeout=180).stdout
finally:
    os.remove('_coin.html')

m = re.search(r'RESULT (\{.*\})</title>', out, re.S)
if not m:
    t = re.search(r'<title>(.*?)</title>', out, re.S)
    print('NO RESULT', t.group(1)[:300] if t else ''); sys.exit(1)
r = json.loads(m.group(1))
print(f"coin: 화면상 코인 아트 {r['seen']}곳 · {len(r['fails'])} fail")
for f in r['fails']: print('  ', json.dumps(f, ensure_ascii=False)[:240])
print('PASS' if not r['fails'] else 'FAIL')
sys.exit(0 if not r['fails'] else 1)
