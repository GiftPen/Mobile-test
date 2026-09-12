#!/usr/bin/env python3
"""Turn a flat-background AI image into a transparent PNG.

Image models cannot output alpha. Asking for "transparent background" makes them DRAW the
checkerboard that represents transparency, which is worse than useless. So the prompts ask for
a flat solid background instead and this removes it afterwards.

Works by flooding inward from the border: only background connected to the edge is cleared, so
a white highlight inside the object survives. The thick dark outline the art style already
calls for is what stops the flood getting in.

  python3 tools/cutout.py in.png out.png [--bg auto|RRGGBB] [--tol 60] [--size 512]

No third-party libraries; pure zlib.
"""
import sys, zlib, struct, os, json, unicodedata
from collections import deque

# ---------- PNG ----------
def read_png(path):
    d = open(path, 'rb').read()
    if d[:8] != b'\x89PNG\r\n\x1a\n': raise SystemExit(f'{path}: PNG 파일이 아닙니다')
    pos, idat, pal, trns = 8, bytearray(), None, None
    w = h = bitd = ct = interlace = None
    while pos < len(d):
        ln = struct.unpack('>I', d[pos:pos+4])[0]; typ = d[pos+4:pos+8]
        body = d[pos+8:pos+8+ln]; pos += 12 + ln
        if   typ == b'IHDR':
            w, h, bitd, ct, _, _, interlace = struct.unpack('>IIBBBBB', body)
        elif typ == b'PLTE': pal = body
        elif typ == b'tRNS': trns = body
        elif typ == b'IDAT': idat += body
        elif typ == b'IEND': break
    if bitd != 8:      raise SystemExit('8비트 PNG만 지원합니다')
    if interlace:      raise SystemExit('인터레이스 PNG는 지원하지 않습니다')
    ch = {0:1, 2:3, 3:1, 4:2, 6:4}.get(ct)
    if ch is None:     raise SystemExit(f'지원하지 않는 컬러 타입 {ct}')
    raw = zlib.decompress(bytes(idat))
    stride = w * ch
    out = bytearray(h * stride)
    prev = bytearray(stride)
    p = 0
    for y in range(h):
        f = raw[p]; p += 1
        line = bytearray(raw[p:p+stride]); p += stride
        if f == 1:
            for i in range(ch, stride): line[i] = (line[i] + line[i-ch]) & 255
        elif f == 2:
            for i in range(stride): line[i] = (line[i] + prev[i]) & 255
        elif f == 3:
            for i in range(stride):
                a = line[i-ch] if i >= ch else 0
                line[i] = (line[i] + ((a + prev[i]) >> 1)) & 255
        elif f == 4:
            for i in range(stride):
                a = line[i-ch] if i >= ch else 0
                b = prev[i]; c = prev[i-ch] if i >= ch else 0
                pa, pb, pc = abs(b-c), abs(a-c), abs(a+b-2*c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pr) & 255
        out[y*stride:(y+1)*stride] = line
        prev = line
    # normalise to RGBA
    px = bytearray(w*h*4)
    for i in range(w*h):
        if   ct == 6: px[i*4:i*4+4] = out[i*4:i*4+4]
        elif ct == 2: px[i*4:i*4+3] = out[i*3:i*3+3]; px[i*4+3] = 255
        elif ct == 0: v = out[i]; px[i*4:i*4+3] = bytes((v,v,v)); px[i*4+3] = 255
        elif ct == 4: v = out[i*2]; px[i*4:i*4+3] = bytes((v,v,v)); px[i*4+3] = out[i*2+1]
        elif ct == 3:
            idx = out[i]; px[i*4:i*4+3] = pal[idx*3:idx*3+3]
            px[i*4+3] = trns[idx] if (trns and idx < len(trns)) else 255
    return w, h, px

def write_png(path, w, h, px):
    raw = bytearray()
    for y in range(h):
        raw.append(0)
        raw += px[y*w*4:(y+1)*w*4]
    def chunk(t, b):
        return struct.pack('>I', len(b)) + t + b + struct.pack('>I', zlib.crc32(t + b) & 0xffffffff)
    open(path, 'wb').write(
        b'\x89PNG\r\n\x1a\n'
        + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0))
        + chunk(b'IDAT', zlib.compress(bytes(raw), 9))
        + chunk(b'IEND', b''))

# ---------- cutout ----------
def downscale(w, h, px, target):
    """Box-filter down to `target` on the long edge. 1024x1024 is what the generators emit,
    but a relic icon draws at 48 CSS px -- shipping the full thing is ~800KB of art for a
    thumbnail, and 65 relics of that would be 50MB of mobile download.

    Averaged in PREMULTIPLIED space: the RGB under a fully transparent pixel is leftover
    garbage, so averaging it straight drags that garbage into every edge as a dark fringe."""
    if max(w, h) <= target: return w, h, px
    nw = max(1, round(w * target / max(w, h)))
    nh = max(1, round(h * target / max(w, h)))
    out = bytearray(nw * nh * 4)
    for y in range(nh):
        y0 = y * h // nh; y1 = max(y0 + 1, (y + 1) * h // nh)
        for x in range(nw):
            x0 = x * w // nw; x1 = max(x0 + 1, (x + 1) * w // nw)
            r = g = b = a = n = 0
            for yy in range(y0, y1):
                base = yy * w
                for xx in range(x0, x1):
                    i = (base + xx) * 4
                    al = px[i+3]
                    r += px[i] * al; g += px[i+1] * al; b += px[i+2] * al
                    a += al; n += 1
            d = (y * nw + x) * 4
            if a:
                out[d] = min(255, r // a); out[d+1] = min(255, g // a); out[d+2] = min(255, b // a)
            out[d+3] = a // n
    return nw, nh, out


HOLE_MIN  = 400    # smaller than this is a highlight, not a hole
# Colour is what actually separates a hole from pale art, and it separates them by a mile:
# measured across these icons, holes sit 1-3 off the background while the prism's glass body
# sits 26 off and a tractor window 19. Flatness is only a backstop against a SHADED pale
# shape -- at 6 it was rejecting half of 별자리 왕's gaps, whose thin crossing lines leave
# just enough anti-alias noise to push the deviation over.
HOLE_TOL  = 6      # how close to the background colour an enclosed region must be
HOLE_FLAT = 14     # ...and how flat, so shaded pale ART is not mistaken for background


def cutout(w, h, px, bg, tol, feather=True, holes_ok=True):
    """Clear background connected to the border. Interior pixels of the same colour survive."""
    d2 = tol * tol * 3
    def far(i):                                   # squared distance from the background colour
        r, g, b = px[i*4], px[i*4+1], px[i*4+2]
        return (r-bg[0])**2 + (g-bg[1])**2 + (b-bg[2])**2
    seen = bytearray(w*h)
    q = deque()
    for x in range(w):
        for y in (0, h-1):
            i = y*w + x
            if not seen[i] and far(i) <= d2: seen[i] = 1; q.append(i)
    for y in range(h):
        for x in (0, w-1):
            i = y*w + x
            if not seen[i] and far(i) <= d2: seen[i] = 1; q.append(i)
    while q:
        i = q.popleft()
        x, y = i % w, i // w
        for nx, ny in ((x-1,y),(x+1,y),(x,y-1),(x,y+1)):
            if 0 <= nx < w and 0 <= ny < h:
                j = ny*w + nx
                if not seen[j] and far(j) <= d2:
                    seen[j] = 1; q.append(j)
    # Holes. A crown's arches, a handle's loop: background the border flood cannot reach
    # because the drawing encloses it. Left alone they become white blobs on a dark board.
    # But an enclosed near-background region can also be the ART -- the prism's glass body is
    # a big pale shape too -- so only regions that are background-coloured to within HOLE_TOL
    # AND as FLAT as background (low deviation) are opened. Measured on these three: the
    # crown's arches sit 3 off the background with deviation 2.5; the prism's glass sits 26
    # off with a blue cast. Nothing in between, so the gap is where the line goes.
    holes = 0
    if holes_ok:
        done = bytearray(seen)
        for start in range(w*h):
            if done[start] or far(start) > d2: continue
            q = deque([start]); done[start] = 1; cells = [start]
            while q:
                i = q.popleft(); x, y = i % w, i // w
                for nx, ny in ((x-1,y),(x+1,y),(x,y-1),(x,y+1)):
                    if 0 <= nx < w and 0 <= ny < h:
                        j = ny*w + nx
                        if not done[j] and far(j) <= d2: done[j] = 1; q.append(j); cells.append(j)
            if len(cells) < HOLE_MIN: continue
            n = len(cells)
            mean = [sum(px[i*4+k] for i in cells) / n for k in range(3)]
            if max(abs(mean[k] - bg[k]) for k in range(3)) > HOLE_TOL: continue
            sd = [(sum((px[i*4+k] - mean[k])**2 for i in cells) / n) ** 0.5 for k in range(3)]
            if max(sd) > HOLE_FLAT: continue
            for i in cells: seen[i] = 1
            holes += 1

    cleared = 0
    for i in range(w*h):
        if seen[i]: px[i*4+3] = 0; cleared += 1
    if feather:
        # Decontaminate the rim. The source was drawn ON the background, so its anti-aliased
        # edge pixels are a BLEND of the object and the background -- lowering only their alpha
        # leaves a pale halo of background colour around everything. Recover the true colour by
        # solving  observed = a*object + (1-a)*background  for both a and the object colour.
        fringe = []
        for y in range(h):
            for x in range(w):
                i = y*w + x
                if seen[i]: continue
                touching = 0
                for nx, ny in ((x-1,y),(x+1,y),(x,y-1),(x,y+1)):
                    if 0 <= nx < w and 0 <= ny < h and seen[ny*w+nx]: touching = 1; break
                if touching: fringe.append((x, y, i))
        fset = {i for _, _, i in fringe}
        for x, y, i in fringe:
            # the object colour here = nearest kept pixel that is NOT itself on the rim
            best, bd = None, 1 << 30
            for r in (1, 2, 3):
                for dy in range(-r, r+1):
                    for dx in range(-r, r+1):
                        nx, ny = x+dx, y+dy
                        if not (0 <= nx < w and 0 <= ny < h): continue
                        j = ny*w + nx
                        if seen[j] or j in fset: continue
                        d = dx*dx + dy*dy
                        if d < bd: bd, best = d, j
                if best is not None: break
            if best is None:                     # a lone speck: just drop it
                px[i*4+3] = 0
                continue
            fr, fg, fb = px[best*4], px[best*4+1], px[best*4+2]
            # use whichever channel separates object from background most -- the others are noise
            ch = max(range(3), key=lambda k: abs((fr, fg, fb)[k] - bg[k]))
            den = (fr, fg, fb)[ch] - bg[ch]
            obs = px[i*4+ch]
            a = 1.0 if abs(den) < 8 else (obs - bg[ch]) / den
            a = max(0.0, min(1.0, a))
            px[i*4], px[i*4+1], px[i*4+2] = fr, fg, fb     # true colour, not the blend
            px[i*4+3] = int(round(a * 255))
    return cleared, holes

def corner_colour(w, h, px):
    """Average of the four corners -- what a flat background actually is."""
    pts = [0, w-1, (h-1)*w, h*w-1]
    r = sum(px[i*4] for i in pts) // 4
    g = sum(px[i*4+1] for i in pts) // 4
    b = sum(px[i*4+2] for i in pts) // 4
    return (r, g, b)

def looks_checkered(w, h, px):
    """The tell-tale failure: the model drew the transparency grid as actual pixels.

    Real alternating tiles, not just two grey samples -- sampling four corners caught ordinary
    soft-grey artwork too, so it walks a row and counts how often the shade flips."""
    y = max(2, h // 30)
    row = []
    for x in range(0, w // 3):
        i = (y*w + x) * 4
        r, g, b = px[i], px[i+1], px[i+2]
        if max(r, g, b) - min(r, g, b) > 18 or min(r, g, b) < 140: return False   # not grey
        row.append((r + g + b) // 3)
    if len(row) < 24: return False
    lo, hi = min(row), max(row)
    if hi - lo < 12 or hi - lo > 90: return False        # flat, or real artwork
    mid = (lo + hi) / 2
    flips = sum(1 for k in range(1, len(row)) if (row[k] > mid) != (row[k-1] > mid))
    return flips >= 2

HERE = os.path.dirname(os.path.abspath(__file__))
RAW  = os.path.join(HERE, '..', 'assets_raw')
OUT  = os.path.join(HERE, '..', 'assets_new')

def batch(tol, holes_ok=True, size=None):
    """Everything in assets_raw/ -> assets_new/, named by whatever the file is called.

    Files may be named by relic id (reclaim.png) or by the Korean name shown in 유물.md
    (개간.png), because those are the two things actually in front of whoever made the art."""
    # game pieces are not relics, so they are not in the generated map -- but they are exactly
    # the things most likely to be drawn next, so they get names too
    names = {
        'coin': 'coin', '동전': 'coin', 'bomb': 'bomb', '폭탄': 'bomb',
        'bird': 'bird', '참새': 'bird', 'star': 'star', '별': 'star',
        'line': 'line', '라인': 'line',
        'brick1': 'brick1', 'brick2': 'brick2', 'brick3': 'brick3',
        '벽돌1': 'brick1', '벽돌2': 'brick2', '벽돌3': 'brick3',
    }
    for i, n in enumerate(['체리', '오렌지', '키위', '레몬', '포도', '복숭아', '바나나']):
        names[n] = f'fruit{i}'; names[f'fruit{i}'] = f'fruit{i}'
    try:
        names.update(json.load(open(os.path.join(HERE, 'art-names.json'), encoding='utf-8')))
    except Exception:
        pass
    if not os.path.isdir(RAW):
        os.makedirs(RAW, exist_ok=True)
        print(f'assets_raw/ 를 만들었습니다. 여기에 PNG를 넣고 다시 실행하세요.')
        return
    # Match loosely. "바나나농장" and "바나나 농장" are the same name to a person, and macOS
    # hands back NFD Hangul where GitHub hands back NFC -- neither is the user's problem.
    def key(t):
        return unicodedata.normalize('NFC', t).replace(' ', '').replace('_', '').lower()
    names = {key(k): v for k, v in names.items()}
    files = sorted(f for f in os.listdir(RAW) if f.lower().endswith('.png'))
    if not files:
        print('assets_raw/ 가 비어 있습니다. 받은 PNG를 넣어주세요.')
        return
    done = skipped = unknown = 0
    for f in files:
        stem = os.path.splitext(f)[0].strip()
        target = names.get(key(stem))
        if not target:
            print(f'  ? {f:34} 이름을 못 알아봤습니다 — 유물 id 나 한글 이름으로 바꿔주세요')
            unknown += 1
            continue
        src = os.path.join(RAW, f)
        dst = os.path.join(OUT, target + '.png')
        w, h, px = read_png(src)
        clear = sum(1 for i in range(w*h) if px[i*4+3] < 8)
        if clear * 100 // (w*h) >= 5:
            print(f'  = {f:34} 이미 투명 — 그대로 복사')
            open(dst, 'wb').write(open(src, 'rb').read())
            skipped += 1
            continue
        if looks_checkered(w, h, px):
            print(f'  ! {f:34} 체크무늬 배경 (프롬프트에서 transparent 를 빼세요)')
        bg = corner_colour(w, h, px)
        n, holes = cutout(w, h, px, bg, tol, holes_ok=holes_ok)
        pct = n * 100 // (w*h)          # against the ORIGINAL size, before the downscale
        # a relic icon draws at 48px, a board piece at ~40px; 1024 is the generator's habit,
        # not a requirement, and it is the difference between a 50MB download and a 3MB one
        want = size or (256 if target.startswith(('relic_', 'trait_')) else 512)
        w, h, px = downscale(w, h, px, want)
        write_png(dst, w, h, px)
        flag = '  ⚠️ 확인 필요' if (pct < 5 or pct > 85) else ''
        hole = f' · 막힌 구멍 {holes}개 뚫음' if holes else ''
        print(f'  ✓ {f:34} → {target}.png  ({pct}% 제거{hole}){flag}')
        done += 1
    print(f'\n배경 제거 {done}개 · 그대로 {skipped}개 · 이름 불명 {unknown}개')

def main():
    a = sys.argv[1:]
    if a and a[0] in ('--all', '-a'):
        tol = 60
        for i, t in enumerate(a):
            if t == '--tol' and i+1 < len(a): tol = int(a[i+1])
        size = None
        for i, t in enumerate(a):
            if t == '--size' and i+1 < len(a): size = int(a[i+1])
        batch(tol, holes_ok='--keep-holes' not in a, size=size); return
    if len(a) < 2: print(__doc__); sys.exit(1)
    src, dst = a[0], a[1]
    bg_arg = 'auto'; tol = 60; size = None
    holes_ok = '--keep-holes' not in a      # a big flat white shape you WANT to keep
    for i, t in enumerate(a):
        if t == '--bg' and i+1 < len(a): bg_arg = a[i+1]
        if t == '--tol' and i+1 < len(a): tol = int(a[i+1])
        if t == '--size' and i+1 < len(a): size = int(a[i+1])
    w, h, px = read_png(src)

    # Already cut out? Running again is destructive: the RGB under a transparent pixel is
    # leftover garbage, so the corner sample is meaningless and the flood eats real artwork.
    clear = sum(1 for i in range(w*h) if px[i*4+3] < 8)
    if clear * 100 // (w*h) >= 5 and '--force' not in a:
        print(f'{os.path.basename(src)}: 이미 투명 배경입니다 '
              f'({clear*100//(w*h)}%가 투명) — 건너뜁니다.')
        print('   정말 다시 처리하려면 --force 를 붙이세요.')
        return

    if looks_checkered(w, h, px):
        print('⚠️  배경이 체크무늬로 "그려져" 있습니다 — 투명이 아니라 그림입니다.')
        print('   프롬프트에서 transparent background 를 빼고 단색 배경을 요구하세요.')
    bg = corner_colour(w, h, px) if bg_arg == 'auto' else tuple(
        int(bg_arg.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
    n, holes = cutout(w, h, px, bg, tol, holes_ok=holes_ok)
    pct = n * 100 // (w*h)
    if size: w, h, px = downscale(w, h, px, size)
    write_png(dst, w, h, px)
    print(f'{os.path.basename(src)} → {os.path.basename(dst)}  '
          f'{w}x{h} · 배경 #{bg[0]:02x}{bg[1]:02x}{bg[2]:02x} · {pct}% 제거'
          + (f' · 막힌 구멍 {holes}개 뚫음' if holes else ''))
    if pct < 5:  print('   ⚠️  거의 안 지워졌습니다 — --tol 을 올리거나 --bg 를 직접 지정하세요')
    if pct > 85: print('   ⚠️  너무 많이 지워졌습니다 — --tol 을 낮추세요')

main()
