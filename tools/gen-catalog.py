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
  // Which fruit a relic is ABOUT, derived by applying it and seeing what moved. Written out
  // by hand this list would be wrong the first time a relic is renamed or added.
  const fruitsTouched = (setup) => {
    F.mode = 'rush'; F.resetRun();
    const base = [F.oddsMult.slice(), F.fruitMult.slice(), F.fruitFlat.slice(), F.fruitBoost.slice()];
    setup();
    const now = [F.oddsMult, F.fruitMult, F.fruitFlat, F.fruitBoost];
    const hit = new Set();
    for (let a = 0; a < 4; a++) for (let i = 0; i < 7; i++) if (now[a][i] !== base[a][i]) hit.add(i);
    // stacking relics only move when a fruit actually pops, so poke each colour
    for (let i = 0; i < 7; i++) {
      const before = F.fruitStack[i];
      F.notify('onFruitPop', { r: 0, c: 0, color: i });
      if (F.fruitStack[i] !== before) hit.add(i);
    }
    F.relics = []; F.traits = []; F.applyRelics();
    return [...hit].sort((a, b) => a - b);
  };
  const relics = Object.keys(F.RELICS).map(id => {
    const R = F.RELICS[id];
    return { id, name: R.name, icon: R.icon, price: R.price, desc: R.desc,
             tier: F.relicTier(R), slots: R.slots || 0,
             life: R.life ? (R.life.amount + F.lifeUnitLabel(R.life.unit)) : "",
             fruits: fruitsTouched(() => { F.relics = [id]; F.applyRelics(); }),
             hooks: ["apply","modify","onFruitPop","onPop","onSpawn","onTurn","onStageStart","onRunStart"]
                      .filter(k => R[k]).join(", ") };
  });
  const traits = Object.keys(F.TRAITS).map(id => {
    const T = F.TRAITS[id];
    return { id, name: T.name, icon: T.icon, desc: T.desc(F.traitEffects(T, 1)),
             doubled: T.scalable ? T.desc(F.traitEffects(T, 2)) : "",
             scalable: !!T.scalable, once: !!T.once, tier: F.traitTier(T),
             fruits: fruitsTouched(() => { F.traits = [{ id, amount: 1 }]; F.applyRelics(); }),
             stats: T.effects.map(e => e.stat).join(", ") };
  });
  document.title = 'RESULT ' + JSON.stringify({ relics, traits, colors: F.COLORS,
    traitOdds: F.TRAIT_ODDS,
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

# ---- fruit colour, taken from the game rather than from a copy of it ----
# The palette in art-prompts.json had already drifted (peach #ffc0cb vs the game's #ffab8f),
# which is what a hand-kept copy does. The game is the source; the file has to agree.
FRUIT_EN = ['cherry', 'orange', 'kiwi', 'lemon', 'grape', 'peach', 'banana']
GAME_COLORS = [c.lower() for c in d['colors']]
_stale_cols = [f'{FRUIT_EN[i]}: {ST["colors"].get(FRUIT_EN[i])} -> {GAME_COLORS[i]}'
               for i in range(7) if (ST['colors'].get(FRUIT_EN[i]) or '').lower() != GAME_COLORS[i]]
if _stale_cols:
    print('art-prompts.json 의 _style.colors 가 게임과 다릅니다:')
    for t in _stale_cols: print('   ', t)
    sys.exit(1)

# A generator draws a yellow banana and a pink peach unless told otherwise, so every prompt
# that is ABOUT a fruit says which colour that fruit is here -- and the odd ones say so twice.
ODD = {6: 'BLUE (not yellow)', 2: 'green', 5: 'soft coral'}
OWN_COLOUR = set(ST.get('own_colour', []))   # art whose concept overrides the fruit colour
WITH_FACE  = set(ST.get('with_face', []))    # the few subjects that are SUPPOSED to have one
PALETTE = ', use this game\'s fruit palette: ' + ', '.join(
    f'{FRUIT_EN[i]} {GAME_COLORS[i]}' + (f' ({ODD[i]})' if i in ODD else '') for i in range(7))
# "a fruit" in a prompt, not the word orange used as a colour. 십자로 is "glossy golden-orange"
# and 불꽃 증폭 is "an orange flame" -- neither is about fruit, and neither should be told
# what colour oranges are.
# 'orange' is left out on purpose: it is a colour word as often as a fruit here (십자로 is
# "glossy golden-orange", 불꽃 증폭 is "an orange flame"), and neither should be told what
# colour oranges are. An orange-only prompt is caught by its effect instead.
GENERIC = re.compile(r'\bfruits?\b|\bcherr(y|ies)\b|\bkiwis?\b|\blemons?\b'
                     r'|\bgrapes?\b|\bpeach(es)?\b|\bbananas?\b', re.I)
# Which fruit the PICTURE contains, which is not the same as which fruit the effect touches.
# 바나나 군락 converts anything into banana, so its effect lists all seven -- and the prompt
# then carried all seven colours for a drawing of one bunch of bananas, which is exactly the
# noise that makes a generator start adding fruit nobody asked for.
FRUIT_WORD = [re.compile(r'\bcherr(y|ies)\b', re.I), re.compile(r'\boranges?\b', re.I),
              re.compile(r'\bkiwis?\b', re.I), re.compile(r'\blemons?\b', re.I),
              re.compile(r'\bgrapes?\b', re.I), re.compile(r'\bpeach(es)?\b', re.I),
              re.compile(r'\bbananas?\b', re.I)]
def fruits_drawn(subject, fruits):
    # 'orange' is a colour word as often as a fruit, so it counts only when the effect agrees
    return [i for i, rx in enumerate(FRUIT_WORD)
            if rx.search(subject or '') and (i != 1 or 1 in (fruits or []))]

def _emit_traits(ts, L):
    for tr in ts:
        notes = []
        if tr['once']: notes.append('한 게임에 1회 등장')
        if not tr['scalable']: notes.append('2배 불가')
        L.append(f"| {tr['icon']} | {tr['name']} | {art_mark('trait_' + tr['id'])} | {tr['desc']} | "
                 f"{tr['doubled'] or '—'} | {' · '.join(notes) or ''} | "
                 f"`{full_prompt('traits', tr['id'], tr['fruits'])}` |")


def colour_clause(fruits, rid, prompt):
    """What to tell the generator about colour. Named fruit gets named colours; a picture of
    fruit in general gets the palette; anything else gets nothing.

    Phrased as a correction to a default the generator already has, and fenced so it cannot be
    read as a list of things to draw -- appending a bare palette made it add fruit that the
    subject never mentioned."""
    if rid in OWN_COLOUR: return ''
    named = fruits_drawn(prompt, fruits)
    if named:
        return ' Colour: ' + ', '.join(
            f'the {FRUIT_EN[i]} here is ' + (f'{ODD[i]} ' if i in ODD else '') + GAME_COLORS[i]
            for i in named) + '.'
    # nothing named but the picture is "fruit" in general -- then the whole palette is the
    # point, and it is fenced so it cannot be read as a shopping list
    if GENERIC.search(prompt or ''):
        return (' Colour (this is the palette to pick from, do not add every fruit listed): '
                + ', '.join(f'{FRUIT_EN[i]} ' + (f'{ODD[i]} ' if i in ODD else '')
                            + GAME_COLORS[i] for i in range(7)) + '.')
    return ''


def full_prompt(kind, rid, fruits):
    """The whole thing, ready to paste once.

    The subject and the style used to live in two places and every image cost two copies. They
    are one string now, in the order a generator reads best: what to draw, then what colour it
    is, then how to draw it."""
    subject = (PROMPTS[kind].get(rid) or '').strip().rstrip('.')
    if not subject: return '—'
    key = rid if kind == 'relics' else 'trait_' + rid
    style = ST['trait_suffix' if kind == 'traits' else 'suffix'].lstrip(', ')
    face = '' if key in WITH_FACE else ' ' + ST['no_face'] + ','
    return f"{subject}.{colour_clause(fruits, rid, subject)} Style:{face} {style}."

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

# ---- which art actually exists, read off disk and off the game's list ----
# Not a hand-kept checklist: a hand-kept one goes stale the first time art lands and nobody
# remembers to tick it. ✅ means the file is there AND the game is using it, which is the
# only state that means anything to a player.
import glob
_files = {os.path.basename(f)[:-4] for d_ in ('assets_new', 'assets')
          for f in glob.glob(d_ + '/*.png')}
_listed = set(re.findall(r'"((?:relic|trait)_[a-z0-9_]+)"',
                         re.search(r'const ART_IDS = new Set\(\[(.*?)\]\)',
                                   open('index.html', encoding='utf-8').read(), re.S).group(1)))
def art_mark(key):
    if key in _files and key in _listed: return '✅'
    if key in _files:                    return '⚠️ 미연결'
    return ''
_done_r = sum(1 for r in d['relics'] if art_mark('relic_' + r['id']) == '✅')
_done_t = sum(1 for t in d['traits'] if art_mark('trait_' + t['id']) == '✅')

# A fruit prompt that also spells its own hex is a second source of truth, and the one that
# goes stale. The colour comes from the game now; the subject must not repeat it.
_byid = {x['id']: x for x in d['relics']}
_tbyid = {x['id']: x for x in d['traits']}
_hexed = ([f"relic {k}" for k, v in PROMPTS['relics'].items()
           if _byid.get(k, {}).get('fruits') and re.search(r'#[0-9a-fA-F]{6}', v)] +
          [f"trait {k}" for k, v in PROMPTS['traits'].items()
           if _tbyid.get(k, {}).get('fruits') and re.search(r'#[0-9a-fA-F]{6}', v)])
if _hexed:
    print('과일 색은 게임에서 붙습니다 — 프롬프트에 직접 쓴 색을 지우세요:', ', '.join(_hexed))
    sys.exit(1)

# A subject that talks about a face while the no-face line is being appended to it is a
# contradiction the generator resolves at random, so it is an error here rather than a surprise
# in the image.
_FACEWORD = re.compile(r'\b(face|eyes?|eyebrows?|mouth|smil\w*|beak|muzzle)\b', re.I)
_face_bad = ([k for k, v in PROMPTS['relics'].items()
              if _FACEWORD.search(v) and k not in WITH_FACE] +
             ['trait_' + k for k, v in PROMPTS['traits'].items()
              if _FACEWORD.search(v) and 'trait_' + k not in WITH_FACE])
if _face_bad:
    print('프롬프트가 얼굴을 말하는데 _style.with_face 에 없습니다 (얼굴 금지 문구와 충돌):',
          ', '.join(_face_bad))
    sys.exit(1)
_face_unused = [k for k in WITH_FACE
                if k not in PROMPTS['relics'] and k.replace('trait_', '', 1) not in PROMPTS['traits']]
if _face_unused:
    print('_style.with_face 에 존재하지 않는 항목:', ', '.join(_face_unused))
    sys.exit(1)

# Two cards with the same name is not a cosmetic problem: art-names.json is keyed by name, so
# the second one silently overwrites the first and an image lands on the wrong relic. 명당 was
# both sweet_spot and hotspot, and the clover drawn for one of them ended up on the other.
_by_name = {}
for _x in d['relics'] + d['traits']:
    _by_name.setdefault(_x['name'], []).append(_x['id'])
_dupe_names = {n: ids for n, ids in _by_name.items() if len(ids) > 1}
if _dupe_names:
    print('이름이 겹칩니다 — 이미지가 엉뚱한 곳에 붙습니다:')
    for n, ids in _dupe_names.items():
        print(f'  "{n}" = {", ".join(ids)}')
    sys.exit(1)

_own_bad = [k for k in OWN_COLOUR
            if not (_byid.get(k, {}).get('fruits') or _tbyid.get(k, {}).get('fruits'))]
if _own_bad:
    print('_style.own_colour 에 과일과 무관하거나 존재하지 않는 항목:', ', '.join(_own_bad))
    sys.exit(1)

L.append('# 유물 · 특성 도감\n')
L.append(f"> `tools/gen-catalog.py`가 **게임 코드에서 자동 생성**합니다. 직접 고치지 마세요 — 유물이나 특성을 추가한 뒤 다시 돌리면 됩니다.\n>\n> 생성: {datetime.date.today()} · 유물 {len(d['relics'])}종 · 특성 {len(d['traits'])}종\n>\n> **이미지 진행: 유물 {_done_r}/{len(d['relics'])} · 특성 {_done_t}/{len(d['traits'])}** — ✅ 는 게임에 실제로 적용된 것만 표시됩니다.\n")

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
L.append('아래 표의 프롬프트 칸은 **그대로 한 번만 복사**하면 되는 완성된 프롬프트입니다.')
L.append('주제 → 색 지시 → 스타일이 이미 하나로 합쳐져 있으니 **접미사를 따로 붙이지 마세요.**\n')
L.append('대부분의 유물은 물건이라 얼굴이 있으면 안 되므로 "눈·코·입을 그리지 말라"가 자동으로 붙습니다.')
L.append('얼굴이 주제인 것들(`_style.with_face`: ' + ', '.join(sorted(WITH_FACE)) + ')만 예외입니다.\n')
L.append('아래 두 블록은 무엇이 붙는지 확인용입니다 — 복사할 필요 없습니다.\n')
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
    L.append('| | 이름 | 이미지 | 가격 | 지속 | 효과 | AI 이미지 프롬프트 |')
    L.append('|---|---|---|---|---|---|---|')
    for r in rs:
        L.append(f"| {r['icon']} | {r['name']} | {art_mark('relic_' + r['id'])} | {r['price']} | "
                 f"{r['life'] or '영구'} | {r['desc']} | "
                 f"`{full_prompt('relics', r['id'], r['fruits'])}` |")
    L.append('')

L.append('## 특성\n')
L.append('라운드가 끝날 때 3개 중 1개를 고릅니다. 화면마다 **무료 리롤 1회**.\n')
for t in d['tiers']:
    ts = sorted([x for x in d['traits'] if x['tier'] == t['key']], key=lambda x: x['name'])
    if not ts: continue
    L.append(f"### {t['name']} · {d['traitOdds'][t['key']]}% · {len(ts)}종\n")
    L.append('| | 이름 | 이미지 | 효과 | ✨2배 | 비고 | AI 이미지 프롬프트 |')
    L.append('|---|---|---|---|---|---|---|')
    _emit_traits(ts, L)
    L.append('')



open('유물.md', 'w', encoding='utf-8').write('\n'.join(L))

# a name -> id map so art files can be dropped in named either way (개간.png or reclaim.png)
NAMES = {}
for r in d['relics']: NAMES[r['name']] = 'relic_' + r['id']; NAMES[r['id']] = 'relic_' + r['id']
for t in d['traits']: NAMES[t['name']] = 'trait_' + t['id']; NAMES[t['id']] = 'trait_' + t['id']
json.dump(NAMES, open(os.path.join('tools', 'art-names.json'), 'w', encoding='utf-8'),
          ensure_ascii=False, indent=0)
print(f"유물.md 생성 — 유물 {len(d['relics'])}종 / 특성 {len(d['traits'])}종")
