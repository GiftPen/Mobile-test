#!/usr/bin/env python3
"""ART_IDS in index.html and the files in assets_new/ have to agree, in BOTH directions.

Listed but missing -> the icon silently stays an emoji and nobody notices the art never
shipped. Present but unlisted -> art was made, cut out, committed, and is simply not being
used. The second is the one that actually happens, because adding the file is the step that
feels like finishing."""
import os, re, sys, glob, json, subprocess

os.chdir(os.path.dirname(os.path.abspath(__file__)) + '/..')
src = open('index.html', encoding='utf-8').read()

m = re.search(r'const ART_IDS = new Set\(\[(.*?)\]\)', src, re.S)
if not m:
    print('ART_IDS 를 찾을 수 없습니다'); sys.exit(1)
listed = set(re.findall(r'"([^"]+)"', m.group(1)))

on_disk = set()
for d in ('assets_new', 'assets'):
    for f in glob.glob(f'{d}/*.png'):
        n = os.path.basename(f)[:-4]
        if n.startswith(('relic_', 'trait_')): on_disk.add(n)

missing = sorted(listed - on_disk)
unused  = sorted(on_disk - listed)

# every listed id must also be a real relic/trait, or the art is named after nothing
# tolerate the alignment spacing in the table ("grape_farm:  {"): this check exists to catch
# art named after nothing, not to police whitespace, and it false-flagged a real relic
ids = set(re.findall(r'^    ([a-z0-9_]+):\s*\{', src, re.M))
unknown = sorted(k for k in listed if k.split('_', 1)[1] not in ids)

# and the art must be small enough to ship: 65 relics at a megabyte each is not a mobile game
MAX_KB = 200
heavy = sorted((os.path.basename(f), os.path.getsize(f) // 1024)
               for f in glob.glob('assets_new/relic_*.png') + glob.glob('assets_new/trait_*.png')
               if os.path.getsize(f) > MAX_KB * 1024)

print(f'art: 등록 {len(listed)}개 · 파일 {len(on_disk)}개')
for n in missing: print(f'   ! {n}: ART_IDS 에 있는데 파일이 없습니다')
for n in unused:  print(f'   ! {n}: 파일은 있는데 ART_IDS 에 없습니다 (게임에서 안 쓰임)')
for n in unknown: print(f'   ! {n}: 그런 유물/특성이 없습니다')
for n, kb in heavy: print(f'   ! {n}: {kb}KB — 아이콘 하나에 {MAX_KB}KB 를 넘습니다')
# ---- and it has to reach the screen. Listing a file proves nothing about rendering it. ----
TEST = """<script>
window.addEventListener('load', () => setTimeout(async () => {
 try {
  const F = window.__fs, fails = [];
  const chk = (c, got, want) => { if (JSON.stringify(got) !== JSON.stringify(want))
                                    fails.push({case: c, got, want}); };
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const ids = [...F.ART_IDS];
  // give every image a chance to load before asking whether any of them did
  for (const k of ids) F.iconEl(k, 'x', 'probe');
  await sleep(900);

  const painted = el => el.classList.contains('art-ic') &&
                        /url\(/.test(el.style.backgroundImage) && el.textContent === '';
  const built = {};
  for (const k of ids) {
    const id = k.replace(/^(relic|trait)_/, '');
    const el = k[0] === 'r' ? F.relicIcon(id, 'of-ic') : F.traitIcon(id, 'of-ic');
    built[k] = painted(el);
  }
  chk('every listed id renders as art, not emoji', Object.keys(built).filter(k => !built[k]), []);

  // an id with no art must still render -- as its emoji, never as a blank square
  const plain = F.relicIcon('stamina', 'of-ic');
  chk('a relic without art keeps its emoji', plain.textContent.length > 0, true);
  chk('and is not styled as art', plain.classList.contains('art-ic'), false);

  // and the art must actually be in the shop, which is where you decide what to buy
  F.start('rush'); await sleep(150);
  F.coins = 999; F.openShop(); await sleep(200);
  // legendaries are a 1% draw, so a natural shelf almost never holds one and the check would
  // pass without ever looking at art. Put them on the shelf.
  F.shopOffers = ids.filter(k => k[0] === 'r').map(k => k.slice(6));
  F.renderShop(); await sleep(600);
  const shopIcons = [...document.querySelectorAll('#shop .of-ic')];
  const shopArt = shopIcons.filter(painted).length;
  chk('the shop shows the art on the card', shopArt, shopIcons.length);
  chk('and there were cards to look at', shopIcons.length, ids.length);

  document.title = 'RESULT ' + JSON.stringify({ fails, ids: ids.length, shopArt, shopIcons: shopIcons.length });
 } catch (e) { document.title = 'THREW ' + e.message; }
}, 700));
</script>"""

open('_art.html','w',encoding='utf-8').write(src.replace('</body>', TEST + '</body>'))
try:
    out = subprocess.run(['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
        '--headless','--disable-gpu','--no-first-run','--window-size=430,932',
        '--virtual-time-budget=40000','--dump-dom','http://localhost:8899/_art.html?test=1'],
        capture_output=True, text=True, timeout=180).stdout
finally:
    os.remove('_art.html')
m = re.search(r'RESULT (\{.*\})</title>', out, re.S)
if not m:
    t = re.search(r'<title>(.*?)</title>', out, re.S)
    print('   ! 렌더 검사 실패:', t.group(1)[:200] if t else ''); sys.exit(1)
r = json.loads(m.group(1))
print(f"   렌더: 아트 {r['ids']}개 · 상점 아이콘 {r['shopIcons']}개 중 아트 {r['shopArt']}개")
for f in r['fails']: print('   !', json.dumps(f, ensure_ascii=False)[:200])

bad = missing or unused or unknown or heavy or r['fails']
print('FAIL' if bad else 'PASS')
sys.exit(1 if bad else 0)
