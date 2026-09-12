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
import sys, zlib, struct, os
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
def cutout(w, h, px, bg, tol, feather=True):
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
    cleared = 0
    for i in range(w*h):
        if seen[i]: px[i*4+3] = 0; cleared += 1
    if feather:
        # soften the rim: a kept pixel touching cleared ones gets partial alpha, so the cut
        # does not read as a hard jagged edge against the board
        edge = []
        for y in range(h):
            for x in range(w):
                i = y*w + x
                if seen[i] or px[i*4+3] == 0: continue
                n = 0
                for nx, ny in ((x-1,y),(x+1,y),(x,y-1),(x,y+1)):
                    if 0 <= nx < w and 0 <= ny < h and seen[ny*w+nx]: n += 1
                if n: edge.append((i, n))
        for i, n in edge:
            px[i*4+3] = max(0, min(255, int(255 * (1 - 0.22 * n))))
    return cleared

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

def main():
    a = sys.argv[1:]
    if len(a) < 2: print(__doc__); sys.exit(1)
    src, dst = a[0], a[1]
    bg_arg = 'auto'; tol = 60; size = None
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
    n = cutout(w, h, px, bg, tol)
    pct = n * 100 // (w*h)
    write_png(dst, w, h, px)
    print(f'{os.path.basename(src)} → {os.path.basename(dst)}  '
          f'{w}x{h} · 배경 #{bg[0]:02x}{bg[1]:02x}{bg[2]:02x} · {pct}% 제거')
    if pct < 5:  print('   ⚠️  거의 안 지워졌습니다 — --tol 을 올리거나 --bg 를 직접 지정하세요')
    if pct > 85: print('   ⚠️  너무 많이 지워졌습니다 — --tol 을 낮추세요')

main()
