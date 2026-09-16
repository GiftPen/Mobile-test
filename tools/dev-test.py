#!/usr/bin/env python3
"""The dev mode must be invisible to the people testing the build.

Friends are playing this. So: the way in is a corner tap that asks for a code, the code has to
be right, nothing dev-shaped appears until it is, and locking puts the board back exactly the
way a player sees it. The one that would really hurt is the dot stealing a tap meant for the
bottom-left cell, so that is checked at three phone widths with a real layout."""
import subprocess, os, re, json, sys

WIDTHS = [320, 390, 440]

HOST = """<!doctype html><meta charset=utf-8><body style="margin:0">
<script>
const sleep = ms => new Promise(r => setTimeout(r, ms));
// NOT offsetParent: it is null for every position:fixed element, so the first version of this
// check called the panel "closed" while it was on screen, and would have called it closed no
// matter what. Ask for the box the element actually occupies.
const visible = (win, el) => {
  if (!el) return false;
  const cs = win.getComputedStyle(el);
  if (cs.display === 'none' || cs.visibility === 'hidden' || +cs.opacity === 0) return false;
  const b = el.getBoundingClientRect();
  return b.width > 0 && b.height > 0;
};
const widths = %s;
const out = { hits: [], fails: [] };
function frame(w) {
  return new Promise(res => {
    const f = document.createElement('iframe');
    f.style.cssText = 'width:' + w + 'px;height:844px;border:0;position:absolute;left:0;top:0';
    f.src = 'index.html?test=1';
    f.onload = () => setTimeout(() => res(f), 500);
    document.body.appendChild(f);
  });
}
(async () => {
 try {
  // --- 1. the dot must never sit on the board, at any phone width ---
  for (const w of widths) {
    const f = await frame(w);
    const D = f.contentDocument, F = f.contentWindow.__fs;
    try { f.contentWindow.localStorage.removeItem('fs_dev'); } catch (e) {}
    F.start('rush');
    await sleep(350);
    const cv = D.getElementById('game').getBoundingClientRect();
    const dot = D.getElementById('devdot').getBoundingClientRect();
    const hits = (a, b) => !(a.right <= b.left || a.left >= b.right ||
                             a.bottom <= b.top || a.top >= b.bottom);
    // the board is not the only thing worth a tap down there: the item bar and the
    // next-stage button live between it and the corner
    const covered = [];
    for (const id of ['game', 'ishop', 'rush-next', 'dock', 'hint']) {
      const el = D.getElementById(id);
      if (!el || el.classList.contains('hidden')) continue;
      const b = el.getBoundingClientRect();
      if (b.width && hits(dot, b)) covered.push(id);
    }
    out.hits.push({ w, over: !!covered.length, covered, dotW: Math.round(dot.width),
                    gap: Math.round(cv.bottom <= dot.top ? dot.top - cv.bottom : -1) });
    // and a player who never types the code sees nothing of it
    if (visible(f.contentWindow, D.getElementById('dock'))) out.fails.push(w + 'px: 도크가 그냥 보임');
    if (D.getElementById('devdot').classList.contains('on')) out.fails.push(w + 'px: 점이 켜져 있음');
    if (visible(f.contentWindow, D.getElementById('devpanel'))) out.fails.push(w + 'px: 패널이 열려 있음');
    if (+getComputedStyle(D.getElementById('devdot')).opacity > 0.12)
      out.fails.push(w + 'px: 점이 너무 잘 보임');
    f.remove();
  }

  // --- 2. the gate itself ---
  const f = await frame(390);
  const D = f.contentDocument, F = f.contentWindow.__fs;
  const $ = id => D.getElementById(id);
  try { f.contentWindow.localStorage.removeItem('fs_dev'); } catch (e) {}
  F.start('rush'); await sleep(300);
  const seen = id => visible(f.contentWindow, $(id));
  $('devdot').click(); await sleep(60);
  if (!seen('devpanel')) out.fails.push('점을 눌러도 안 열림');
  if (!seen('dev-locked')) out.fails.push('잠긴 상태인데 코드 입력칸이 안 보임');
  $('dev-code').value = 'masterr'; $('dev-ok').click(); await sleep(40);
  if (seen('dev-open')) out.fails.push('틀린 코드로 열림');
  if (!$('dev-msg').textContent) out.fails.push('틀렸다고 말해주지 않음');
  $('dev-code').value = 'MASTER'; $('dev-ok').click(); await sleep(40);
  if (!seen('dev-open')) out.fails.push('맞는 코드로 안 열림');
  if (seen('dev-locked')) out.fails.push('열렸는데 코드 입력칸이 그대로 보임');
  if (f.contentWindow.localStorage.getItem('fs_dev') !== '1') out.fails.push('기억하지 않음');

  // --- 3. what it gives you ---
  $('dev-dock').click(); await sleep(40);
  if (!seen('dock')) out.fails.push('테스트 도크가 안 나옴');
  $('devdot').click(); await sleep(40);
  $('dev-relics').click(); await sleep(120);
  const picks = D.querySelectorAll('#dev-open .dev-pick button');
  out.picks = picks.length;
  out.relicTotal = Object.keys(F.RELICS).length;
  const before = F.relics.length;
  picks[0].click(); await sleep(40);
  if (F.relics.length !== before + 1) out.fails.push('유물이 주어지지 않음');
  picks[0].click(); await sleep(40);
  if (F.relics.length !== before + 1) out.fails.push('같은 유물이 두 번 들어감');

  // --- 4. locking puts the board back ---
  $('dev-lock').click(); await sleep(60);
  if (seen('dock')) out.fails.push('잠갔는데 도크가 남음');
  if ($('devdot').classList.contains('on')) out.fails.push('잠갔는데 점이 켜져 있음');
  if (f.contentWindow.localStorage.getItem('fs_dev') === '1') out.fails.push('잠갔는데 기억이 남음');
  if (seen('devpanel')) out.fails.push('잠갔는데 패널이 안 닫힘');
  try { f.contentWindow.localStorage.removeItem('fs_dev'); } catch (e) {}

  document.title = 'RESULT ' + JSON.stringify(out);
 } catch (e) { document.title = 'THREW ' + e.message; }
})();
</script>""" % json.dumps(WIDTHS)

os.chdir(os.path.dirname(os.path.abspath(__file__)) + '/..')
open('_dev.html','w',encoding='utf-8').write(HOST)
try:
    out = subprocess.run(['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
        '--headless','--disable-gpu','--no-first-run','--window-size=460,900',
        '--virtual-time-budget=40000','--dump-dom','http://localhost:8899/_dev.html'],
        capture_output=True, text=True, timeout=180).stdout
finally:
    os.remove('_dev.html')

m = re.search(r'RESULT (\{.*?\})</title>', out, re.S)
if not m:
    t = re.search(r'<title>([^<]*)</title>', out)
    print('NO RESULT', t.group(1) if t else '?'); sys.exit(1)
d = json.loads(m.group(1))
fails = list(d['fails'])
for h in d['hits']:
    if h['over']:
        fails.append(f"{h['w']}px: 개발자 점이 {', '.join(h['covered'])} 위에 올라감")
if d.get('picks') != d.get('relicTotal'):
    fails.append(f"유물 선택기 {d.get('picks')}개 · 전체 {d.get('relicTotal')}개")
for h in d['hits']:
    print(f"  {h['w']}px · 점 {h['dotW']}px · 판과 {h['gap']}px 떨어짐")
print(f"  유물 선택기 {d.get('picks')}/{d.get('relicTotal')}")
print(f"dev: {len(fails)} fail")
for f_ in fails[:8]: print('   ', f_)
print('PASS' if not fails else 'FAIL')
sys.exit(1 if fails else 0)
