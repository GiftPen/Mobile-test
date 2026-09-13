"""Erase an image generator's corner watermark (the pale ✦ sparkle) from flat-colour art.

The generators stamp a small light sparkle into a corner. Over the white background it is
invisible and cutout.py takes it away with everything else, but when it lands ON the artwork
it survives into the game. 크래커 is the one piece that hit this.

It finds the mark by its MIN channel: this art style is saturated (the cracker body sits at
blue 40-60) while a whitish overlay lifts every channel at once, so min(r,g,b) separates the
mark from the art far more cleanly than brightness does. Whatever it covers is then rebuilt by
diffusion from the hole's rim -- fine here because the sparkle sits on a smooth field, and a
mirror pass first rebuilds anything with a symmetric twin.

  python3 tools/unmark.py assets_raw/크래커.png --box 868,865,945,935 [--mirror-x 885.5]
  python3 tools/unmark.py assets_raw/크래커.png --box ... --preview /tmp/before-after.png

Writes in place unless -o is given. No third-party libraries; pure zlib.
"""
import sys, os, types

HERE = os.path.dirname(os.path.abspath(__file__))
_src = open(os.path.join(HERE, 'cutout.py'), encoding='utf-8').read().rsplit('\nmain()', 1)[0]
_cut = types.ModuleType('cut')
_cut.__dict__.update(__name__='cut', __file__=os.path.join(HERE, 'cutout.py'))
exec(compile(_src, 'cutout.py', 'exec'), _cut.__dict__)
read_png, write_png = _cut.read_png, _cut.write_png

DELTA = 28      # how far above the box's own min-channel median counts as "whitened"
GROW  = 2       # the mark fades out softly; take a little more than the threshold finds
MIN_BLOB = 40   # smaller than this is art, not a stamp


def find_mark(w, px, box, delta=DELTA, grow=GROW):
    """-> set of indices covered by the watermark."""
    x0, y0, x1, y1 = box
    mins = []
    for y in range(y0, y1):
        for x in range(x0, x1):
            i = (y * w + x) * 4
            if px[i + 3] > 8:
                mins.append(min(px[i], px[i + 1], px[i + 2]))
    if not mins:
        return set()
    mins.sort()
    cut = mins[len(mins) // 2] + delta
    hot = set()
    for y in range(y0, y1):
        for x in range(x0, x1):
            i = (y * w + x) * 4
            if px[i + 3] > 8 and min(px[i], px[i + 1], px[i + 2]) > cut:
                hot.add((x, y))
    # drop specks: a real stamp is one connected blob, a stray bright pixel of art is not
    mark, seen = set(), set()
    for p in hot:
        if p in seen:
            continue
        blob, stack = [], [p]
        seen.add(p)
        while stack:
            cx, cy = stack.pop()
            blob.append((cx, cy))
            for q in ((cx+1, cy), (cx-1, cy), (cx, cy+1), (cx, cy-1)):
                if q in hot and q not in seen:
                    seen.add(q); stack.append(q)
        if len(blob) >= MIN_BLOB:
            mark.update(blob)
    for _ in range(grow):
        mark |= {(x+dx, y+dy) for (x, y) in mark
                 for dx, dy in ((1,0),(-1,0),(0,1),(0,-1))
                 if x0 <= x+dx < x1 and y0 <= y+dy < y1}
    return mark


def repair(w, h, px, mark, mirror_x=None, mirror_y=None, iters=900):
    """Mirror in what has a clean twin, then diffuse the rim inwards over the rest."""
    out = bytearray(px)
    todo = set(mark)
    for axis, horiz in ((mirror_x, True), (mirror_y, False)):
        if axis is None:
            continue
        for (x, y) in sorted(todo):
            sx, sy = (int(round(2 * axis - x)), y) if horiz else (x, int(round(2 * axis - y)))
            if not (0 <= sx < w and 0 <= sy < h) or (sx, sy) in mark:
                continue
            d, s = (y * w + x) * 4, (sy * w + sx) * 4
            out[d:d+3] = px[s:s+3]
            todo.discard((x, y))
    if not todo:
        return out
    # Jacobi on the remaining hole: every pass pulls the rim one pixel further in
    for _ in range(iters):
        nxt = bytearray(out)
        for (x, y) in todo:
            acc = [0, 0, 0]; n = 0
            for dx, dy in ((1,0),(-1,0),(0,1),(0,-1)):
                sx, sy = x+dx, y+dy
                if not (0 <= sx < w and 0 <= sy < h):
                    continue
                s = (sy * w + sx) * 4
                if out[s+3] < 8:
                    continue
                for k in range(3):
                    acc[k] += out[s+k]
                n += 1
            if n:
                d = (y * w + x) * 4
                for k in range(3):
                    nxt[d+k] = acc[k] // n
        out = nxt
    return out


def main():
    a = sys.argv[1:]
    if not a or a[0].startswith('-'):
        print(__doc__); return
    path = a[0]
    box = mirror_x = mirror_y = None
    dst = path
    preview = None
    delta = DELTA
    for i, t in enumerate(a):
        if t == '--box' and i+1 < len(a):      box = tuple(int(v) for v in a[i+1].split(','))
        if t == '--mirror-x' and i+1 < len(a): mirror_x = float(a[i+1])
        if t == '--mirror-y' and i+1 < len(a): mirror_y = float(a[i+1])
        if t == '--delta' and i+1 < len(a):    delta = int(a[i+1])
        if t in ('-o', '--out') and i+1 < len(a): dst = a[i+1]
        if t == '--preview' and i+1 < len(a):  preview = a[i+1]
    w, h, px = read_png(path)
    if not box:
        box = (int(w*0.78), int(h*0.78), w, h)
    box = (max(0, box[0]), max(0, box[1]), min(w, box[2]), min(h, box[3]))
    mark = find_mark(w, px, box, delta=delta)
    if not mark:
        print('워터마크를 못 찾았습니다 — --box 를 조정하거나 --delta 를 낮춰보세요'); return
    xs = [p[0] for p in mark]; ys = [p[1] for p in mark]
    out = repair(w, h, px, mark, mirror_x, mirror_y)
    write_png(dst, w, h, out)
    print(f'  ✓ {os.path.basename(path)} → {os.path.basename(dst)}  '
          f'{len(mark)}px 지움 (x{min(xs)}-{max(xs)} y{min(ys)}-{max(ys)})')
    if preview:
        pad, zoom = 12, 3
        x0, y0 = max(0, min(xs)-pad), max(0, min(ys)-pad)
        cw, chh = min(w, max(xs)+pad) - x0, min(h, max(ys)+pad) - y0
        W, H = cw*zoom*2 + 8, chh*zoom
        sheet = bytearray([255, 0, 255, 255] * (W*H))
        for half, buf in ((0, px), (1, out)):
            for y in range(chh*zoom):
                for x in range(cw*zoom):
                    s = ((y0 + y//zoom) * w + x0 + x//zoom) * 4
                    d = (y * W + half*(cw*zoom+8) + x) * 4
                    sheet[d:d+4] = buf[s:s+4]
        write_png(preview, W, H, sheet)
        print(f'  비교 이미지 → {preview}  (왼쪽 원본 / 오른쪽 수정)')

main()
