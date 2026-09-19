#!/usr/bin/env python3
"""Desktop / landscape layout must fit the canvas Poki renders into.

Poki scales games to 640x360, 836x470 and 1031x580 and requires the game to cover the canvas.
The portrait stack does neither: it leaves two black gutters and, at 580px tall, pushed the
next-stage button off the bottom.

Wide mode moves the HUD into side rails. This checks, at every size Poki names plus two
ordinary desktop ones, that nothing lands outside the viewport, nothing is clipped, the board
actually uses the height, and the rails really hold the HUD.

The next-stage button is checked SHOWN as well as hidden: it is hidden mid-stage, and an
earlier attempt that sized the board against the measured (zero) height of a hidden button
passed everything and then overflowed the moment a stage ended.

Window size does not set innerWidth in headless Chrome, so the game runs in an iframe at the
target size -- what this measures is what a browser at that size shows."""
import subprocess, os, re, json, sys

SIZES = [(640, 360), (836, 470), (1031, 580), (1280, 720), (1920, 1080)]
PORTRAIT = [(390, 844), (320, 568)]      # wide mode must not steal these
CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'


def probe(w, h, show_next):
    host = f"""<!doctype html><meta charset=utf-8><body style="margin:0;background:#000">
<script>
const f = document.createElement('iframe');
f.style.cssText = 'width:{w}px;height:{h}px;border:0;position:absolute;left:0;top:0';
f.src = 'index.html?test=1'; document.body.appendChild(f);
f.onload = () => setTimeout(() => {{
  try {{
    const D = f.contentDocument, W = f.contentWindow, F = W.__fs;
    D.getElementById('btn-challenge').click();
    if ({str(show_next).lower()}) D.getElementById('rush-next').classList.remove('hidden');
    F.layout();
    setTimeout(() => {{
      const out = {{ wide: F.wideOn, vw: W.innerWidth, vh: W.innerHeight,
                    board: F.boardPx || 0, boardMax: F.BOARD_MAX, outside: [], clipped: [],
                    rails: {{}} }};
      const ids = ['rail-l','rail-r','top','rush','rush-bar','stage-wrap','ishop','hint',
                   'rush-next','rb-quota','rb-touch','rs-spawn-chip'];
      for (const id of ids) {{
        const e = D.getElementById(id);
        if (!e || e.offsetParent === null && getComputedStyle(e).display === 'none') continue;
        const r = e.getBoundingClientRect();
        if (r.width === 0 && r.height === 0) continue;
        if (r.right > W.innerWidth + 1 || r.bottom > W.innerHeight + 1 ||
            r.left < -1 || r.top < -1)
          out.outside.push([id, Math.round(r.left), Math.round(r.top),
                            Math.round(r.right), Math.round(r.bottom)]);
        if (e.scrollWidth > e.clientWidth + 1) out.clipped.push([id, e.scrollWidth, e.clientWidth]);
      }}
      for (const id of ['top','rush','rush-bar','ishop']) {{
        const e = D.getElementById(id);
        // body's id is '' -- report the tag so "did it go back to the stack?" is answerable
        out.rails[id] = e && e.parentElement
          ? (e.parentElement.id || e.parentElement.tagName.toLowerCase()) : null;
      }}
      const rot = D.getElementById('rotate');
      out.rotate = !!(rot && rot.classList.contains('on'));
      out.boardVisible = getComputedStyle(D.getElementById('game')).display !== 'none';
      const cv = D.getElementById('game').getBoundingClientRect();
      out.boardBox = [Math.round(cv.left), Math.round(cv.top), Math.round(cv.width), Math.round(cv.height)];
      document.title = 'RESULT ' + JSON.stringify(out);
    }}, 400);
  }} catch (e) {{ document.title = 'THREW ' + e.message; }}
}}, 400);
</script>"""
    page = f'_wf{os.getpid()}.html'
    open(page, 'w', encoding='utf-8').write(host)
    try:
        out = subprocess.run([CHROME, '--headless', '--disable-gpu', '--no-first-run',
            '--hide-scrollbars', f'--window-size={w},{h}', '--virtual-time-budget=20000',
            '--dump-dom', f'http://localhost:8899/{page}'],
            capture_output=True, text=True, timeout=180).stdout
    finally:
        os.remove(page)
    m = re.search(r'RESULT (\{.*?\})</title>', out, re.S)
    if not m:
        t = re.search(r'<title>([^<]*)</title>', out)
        return {'fatal': t.group(1)[:160] if t else 'no result'}
    return json.loads(m.group(1))


os.chdir(os.path.dirname(os.path.abspath(__file__)) + '/..')
fails = []
for (w, h) in SIZES:
    for show in (False, True):
        tag = f"{w}x{h}{' +버튼' if show else ''}"
        d = probe(w, h, show)
        if 'fatal' in d:
            fails.append(f"{tag}: {d['fatal']}"); continue
        if not d['wide']:
            fails.append(f"{tag}: 가로 모드로 전환되지 않음"); continue
        # the layout can be geometrically perfect and still be covered by the rotate panel
        if d.get('rotate'):
            fails.append(f"{tag}: '세로로 돌려주세요' 화면이 게임을 덮음"); continue
        if not d.get('boardVisible'):
            fails.append(f"{tag}: 보드가 표시되지 않음"); continue
        for o in d['outside']:
            fails.append(f"{tag}: {o[0]} 화면 밖 (l{o[1]} t{o[2]} r{o[3]} b{o[4]}, 뷰포트 {w}x{h})")
        for c in d['clipped']:
            fails.append(f"{tag}: {c[0]} 가로 잘림 ({c[1]}px 내용 / {c[2]}px 표시)")
        # the HUD really has to be in the rails, not just styled as if it were
        for k, want in (('top', 'rail-l'), ('rush', 'rail-l'),
                        ('rush-bar', 'rail-r'), ('ishop', 'rail-r')):
            if d['rails'].get(k) != want:
                fails.append(f"{tag}: {k} 가 {d['rails'].get(k)} 에 있음 (기대 {want})")
        # ...and the board must actually use the canvas, not sit in a thin column. BOARD_MAX
        # is a deliberate ceiling -- past it the cells get silly -- so the bar is whichever
        # of "the height on offer" and "the cap" is smaller.
        bw, bh = d['boardBox'][2], d['boardBox'][3]
        want = min(d['boardMax'], h - 92)
        if bh < want * 0.85:
            fails.append(f"{tag}: 보드가 높이를 못 씀 ({bh}px / 기대 {want}px 이상)")
        cx = d['boardBox'][0] + bw / 2
        if abs(cx - w / 2) > 6:
            fails.append(f"{tag}: 보드가 중앙에 없음 (중심 {cx:.0f} / 화면중심 {w/2:.0f})")
        print(f"  {tag:<16} 보드 {bw}x{bh}  레일 {d['rails']['top']}/{d['rails']['ishop']}")

# narrow screens must keep the portrait stack
for (w, h) in PORTRAIT:
    d = probe(w, h, False)
    if 'fatal' in d:
        fails.append(f"{w}x{h}: {d['fatal']}"); continue
    if d['wide']:
        fails.append(f"{w}x{h}: 세로 화면인데 가로 모드로 전환됨")
    if d['rails'].get('top') != 'body':
        fails.append(f"{w}x{h}: 세로 모드인데 top 이 {d['rails'].get('top')} 에 있음")
    for o in d['outside']:
        fails.append(f"{w}x{h}: {o[0]} 화면 밖")
    print(f"  {w}x{h:<11} 세로 유지 (wide={d['wide']})")

print(f"wide-fit: {len(fails)} fail")
for f in fails[:12]: print('   ', f)
print('PASS' if not fails else 'FAIL')
sys.exit(1 if fails else 0)
