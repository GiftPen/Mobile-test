"""Regenerates 유물.md from the game itself.

Run:  python3 -m http.server 8899 &   then   python3 tools/gen-catalog.py

Reads RELICS/TRAITS out of a running index.html through the ?test=1 hook rather than
parsing the source, so the catalogue cannot drift from the code. Re-run it after touching
either table.
"""
import subprocess, re, os, json, sys, datetime
os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

DUMP = r"""<script>
window.addEventListener('load', () => setTimeout(() => {
  const F = window.__fs;
  F.setLang('ko');   // 유물.md is the Korean reference; do not follow the browser locale
  if (!F) { document.title = 'RESULT {"err":"no hook"}'; return; }
  const relics = Object.keys(F.RELICS).map(id => {
    const R = F.RELICS[id];
    return { id, name: R.name, icon: R.icon, price: R.price, desc: R.desc,
             tier: F.relicTier(R), slots: R.slots || 0,
             life: R.life ? (R.life.amount + F.lifeUnitLabel(R.life.unit)) : "",
             hooks: ["apply","modify","onFruitPop","onPop","onSpawn","onTurn","onStageStart","onRunStart"]
                      .filter(k => R[k]).join(", ") };
  });
  const traits = Object.keys(F.TRAITS).map(id => {
    const T = F.TRAITS[id];
    return { id, name: T.name, icon: T.icon, desc: T.desc(F.traitEffects(T, 1)),
             doubled: T.scalable ? T.desc(F.traitEffects(T, 2)) : "",
             scalable: !!T.scalable, once: !!T.once,
             stats: T.effects.map(e => e.stat).join(", ") };
  });
  document.title = 'RESULT ' + JSON.stringify({ relics, traits,
    tiers: F.TIER_KEYS.map(t => ({ key: t, name: F.TIERS[t].name, odds: F.TIERS[t].odds })),
    shopOffers: F.SHOP_OFFERS, slots: F.RELIC_SLOTS });
}, 900));
</script>"""

open('_cat.html', 'w', encoding='utf-8').write(
    open('index.html', encoding='utf-8').read().replace('</body>', DUMP + '</body>'))
out = subprocess.run(['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '--headless', '--disable-gpu', '--no-first-run', '--virtual-time-budget=20000',
    '--dump-dom', 'http://localhost:8899/_cat.html?test=1'],
    capture_output=True, text=True, timeout=120).stdout
os.remove('_cat.html')
m = re.search(r'RESULT (\{.*?\})</title>', out, re.S)
if not m:
    print('생성 실패: 게임에서 데이터를 못 읽었습니다 (서버가 떠 있나요?)'); sys.exit(1)
d = json.loads(m.group(1))

TIER_ORDER = {t['key']: i for i, t in enumerate(d['tiers'])}
NAMES = {t['key']: t['name'] for t in d['tiers']}
L = []
PROMPTS = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                      'art-prompts.json'), encoding='utf-8'))
ST = PROMPTS['_style']

# A relic added without an art prompt would silently print "—" in the catalogue and be
# forgotten, so the generator refuses instead.
_missing = ([r['id'] for r in d['relics'] if r['id'] not in PROMPTS['relics']] +
            [t['id'] for t in d['traits'] if t['id'] not in PROMPTS['traits']])
_stale   = ([k for k in PROMPTS['relics'] if k not in {r['id'] for r in d['relics']}] +
            [k for k in PROMPTS['traits'] if k not in {t['id'] for t in d['traits']}])
if _missing or _stale:
    if _missing: print('art-prompts.json 에 없는 항목:', ', '.join(_missing))
    if _stale:   print('게임에 없는데 남아있는 프롬프트:', ', '.join(_stale))
    sys.exit(1)

L.append('# 유물 · 특성 도감\n')
L.append(f"> `tools/gen-catalog.py`가 **게임 코드에서 자동 생성**합니다. 직접 고치지 마세요 — 유물이나 특성을 추가한 뒤 다시 돌리면 됩니다.\n>\n> 생성: {datetime.date.today()} · 유물 {len(d['relics'])}종 · 특성 {len(d['traits'])}종\n")

L.append('## 등급과 출현율\n')
L.append('상점 진열은 **' + str(d['shopOffers']) + '장**, 유물 칸은 기본 **' + str(d['slots']) + '개**.\n')
L.append('등급을 먼저 뽑고 그 안에서 균등하게 고르므로, **유물을 아무리 늘려도 아래 확률은 변하지 않습니다.**\n')
L.append('| 등급 | 슬롯당 확률 | 종수 | 상점 1회에 1개 이상 |')
L.append('|---|---|---|---|')
for t in d['tiers']:
    n = sum(1 for r in d['relics'] if r['tier'] == t['key'])
    p = t['odds'] / 100
    L.append(f"| {t['name']} | {t['odds']}% | {n} | {(1 - (1 - p) ** d['shopOffers']) * 100:.1f}% |")
L.append('')

L.append('## AI 이미지 프롬프트 사용법\n')
L.append('아래 표의 프롬프트는 **주제 부분만** 적혀 있습니다. 실제로 생성할 때는 뒤에 공통 스타일을')
L.append('반드시 붙이세요 — 그래야 기존 과일·아이템 에셋과 한 세트로 보입니다.\n')
L.append('**유물용 접미사**\n')
L.append('```')
L.append(ST['suffix'].lstrip(', '))
L.append('```\n')
L.append('**특성용 접미사** (특성은 물건이 아니라 휘장으로 통일)\n')
L.append('```')
L.append(ST['trait_suffix'].lstrip(', '))
L.append('```\n')
L.append('> ' + ST['note'] + '\n')
L.append('### 투명 배경은 프롬프트로 안 됩니다\n')
L.append(ST['bg_note'] + '\n')
L.append('```')
L.append('python3 tools/cutout.py 받은이미지.png assets_new/relic_개간.png')
L.append('```\n')
L.append('| 슬롯 | 색 |')
L.append('|---|---|')
for k, v in ST['colors'].items():
    L.append(f'| {k} | `{v}` |')
L.append('')
L.append('출력 규격은 기존과 동일합니다 — **정사각 투명 PNG 512×512, 오브젝트 가운데 80%,')
L.append('바닥 그림자 없음, 글자 없음, 오브젝트 1개**. (`assets/README.md` 참고)\n')
L.append('## 유물\n')
for t in d['tiers']:
    rs = sorted([r for r in d['relics'] if r['tier'] == t['key']], key=lambda r: (r['price'], r['name']))
    if not rs: continue
    L.append(f"### {t['name']} · {t['odds']}% · {len(rs)}종\n")
    L.append('| | 이름 | 가격 | 지속 | 효과 | AI 이미지 프롬프트 |')
    L.append('|---|---|---|---|---|---|')
    for r in rs:
        L.append(f"| {r['icon']} | {r['name']} | {r['price']} | {r['life'] or '영구'} | {r['desc']} | "
                 f"`{PROMPTS['relics'].get(r['id'], '—')}` |")
    L.append('')

L.append('## 특성\n')
L.append('라운드가 끝날 때 3개 중 1개를 고릅니다. 화면마다 **무료 리롤 1회**.\n')
L.append('| | 이름 | 효과 | ✨2배 | 비고 | AI 이미지 프롬프트 |')
L.append('|---|---|---|---|---|---|')
for tr in sorted(d['traits'], key=lambda x: x['name']):
    notes = []
    if tr['once']: notes.append('런당 1회 등장')
    if not tr['scalable']: notes.append('2배 불가')
    L.append(f"| {tr['icon']} | {tr['name']} | {tr['desc']} | {tr['doubled'] or '—'} | {' · '.join(notes) or ''} | "
             f"`{PROMPTS['traits'].get(tr['id'], '—')}` |")
L.append('')

open('유물.md', 'w', encoding='utf-8').write('\n'.join(L))
print(f"유물.md 생성 — 유물 {len(d['relics'])}종 / 특성 {len(d['traits'])}종")
