# Where does a class lie on the sheet? (a key '#N' selects object N of inst_final.pkl) Faded source; primitives of the chosen object keys in colour (each object its own
#   shade, its index at the top-left of its bbox, bbox dotted); everything else as in the source, faded.
#   python3 classview.py run_dir key1[,key2..] out_prefix [zoom=3] [cols=3] [rows=2] [x0 y0 x1 y1]
#   Without a box: tiles over cfg.WIN (as cfgcheck.py) -> <prefix>_<r><c>.png; with a box: one picture <prefix>.png
import sys, os, pickle, colorsys, importlib.util
import pymupdf as fitz
from PIL import Image, ImageDraw, ImageFont
d = sys.argv[1]; keys = sys.argv[2].split(','); pref = sys.argv[3]
Z = float(sys.argv[4]) if len(sys.argv) > 4 else 3.0
C = int(sys.argv[5]) if len(sys.argv) > 5 else 3; R = int(sys.argv[6]) if len(sys.argv) > 6 else 2
BOX = tuple(map(float, sys.argv[7:11])) if len(sys.argv) > 10 else None
spec = importlib.util.spec_from_file_location('cfg', os.path.join(d, 'cfg.py')); cfg = importlib.util.module_from_spec(spec)
sys.path.insert(0, d); spec.loader.exec_module(cfg)
P = pickle.load(open(os.path.join(d, 'seq.pkl'), 'rb'))[0]
I = pickle.load(open(os.path.join(d, 'inst_final.pkl'), 'rb'))
WP = pickle.load(open(os.path.join(d, 'wallprims.pkl'), 'rb')) if 'wall' in keys else set()
def bez(g, n=10):
    return [((1-t)**3*g[0][0]+3*(1-t)**2*t*g[1][0]+3*(1-t)*t*t*g[2][0]+t**3*g[3][0],(1-t)**3*g[0][1]+3*(1-t)**2*t*g[1][1]+3*(1-t)*t*t*g[2][1]+t**3*g[3][1]) for t in [k/(n-1) for k in range(n)]]
def pts(p): return list(p[4]) if p[0] == 'l' else (bez(p[4]) if p[0] == 'c' else list(p[4]) + [p[4][0]])
BASE = [(230, 0, 0), (0, 90, 230), (0, 160, 0), (200, 0, 200), (230, 130, 0), (0, 170, 170), (120, 60, 0), (90, 0, 160)]
sel = []  # (obj index, key, colour, prims)
for n, q in enumerate(I):
    tag = '#%d' % n
    if q['key'] in keys or tag in keys:
        kb = BASE[keys.index(tag if tag in keys else q['key']) % len(BASE)]
        h, s, v = colorsys.rgb_to_hsv(*[c / 255 for c in kb]); j = (len([1 for t in sel if t[1] == q['key']]) % 5) * 0.035
        r, g, b = colorsys.hsv_to_rgb((h + j) % 1, s, max(0.45, v - j * 3)); sel.append((n, q['key'], (int(r * 255), int(g * 255), int(b * 255)), q['prims']))
if 'wall' in keys: sel.append((-1, 'wall', (0, 0, 0), sorted(WP)))
pdf = os.path.join(d, cfg.PDF); pg = fitz.open(pdf)[0]
F = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 12)
def tile(x0, y0, x1, y1, out):
    pix = pg.get_pixmap(matrix=fitz.Matrix(Z, Z), clip=fitz.Rect(x0, y0, x1, y1))
    im = Image.frombytes('RGB', (pix.width, pix.height), pix.samples)
    im = Image.blend(im, Image.new('RGB', im.size, 'white'), 0.72); dr = ImageDraw.Draw(im)
    T = lambda x, y: ((x - x0) * Z, (y - y0) * Z)
    cnt = {}
    for n, k, col, prims in sel:
        bb = [1e9, 1e9, -1e9, -1e9]; hit = False
        for i in prims:
            p = P[i]; q = pts(p)
            xs = [a for a, b in q]; ys = [b for a, b in q]
            bb = [min(bb[0], min(xs)), min(bb[1], min(ys)), max(bb[2], max(xs)), max(bb[3], max(ys))]
            if max(xs) < x0 or min(xs) > x1 or max(ys) < y0 or min(ys) > y1: continue
            hit = True; xy = [T(a, b) for a, b in q]
            if p[0] == 'qu' and p[3] is not None and p[2] is None:
                if len(xy) >= 3: dr.polygon(xy, outline=col)
            elif len(xy) > 1: dr.line(xy, fill=col, width=2)
        if hit:
            cnt[k] = cnt.get(k, 0) + 1
            if n >= 0:
                a = T(bb[0], bb[1]); b = T(bb[2], bb[3])
                for t in range(int(a[0]), int(b[0]), 6): dr.point([(t, a[1]), (t, b[1])], fill=col)
                for t in range(int(a[1]), int(b[1]), 6): dr.point([(a[0], t), (b[0], t)], fill=col)
                dr.text((a[0] + 1, a[1] - 13), str(n), fill=col, font=F)
    im.save(out); return im.size, cnt
if BOX:
    print(pref + '.png', tile(*BOX, pref + '.png'))
else:
    X0, Y0, X1, Y1 = cfg.WIN; wx = (X1 - X0) / C; wy = (Y1 - Y0) / R
    for r in range(R):
        for c in range(C):
            a = (X0 + c * wx - 8, Y0 + r * wy - 8, X0 + (c + 1) * wx + 8, Y0 + (r + 1) * wy + 8)
            print(r, c, [round(v) for v in a], tile(*a, f'{pref}_{r}{c}.png'))
