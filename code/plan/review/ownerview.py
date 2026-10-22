# Source + every primitive coloured by the key of the object that holds it, legend of the keys in view.
#   ownerview.py run_dir cx cy half zoom out.png [key1,key2,...]   (only these keys coloured; others grey)
import sys, os, pickle, colorsys, hashlib
import pymupdf as fitz
from PIL import Image, ImageDraw, ImageFont
d = sys.argv[1]; cx, cy, h, Z = map(float, sys.argv[2:6]); out = sys.argv[6]
only = set(sys.argv[7].split(',')) if len(sys.argv) > 7 and sys.argv[7] else None
P = pickle.load(open(os.path.join(d, 'seq.pkl'), 'rb'))[0]
I = pickle.load(open(os.path.join(d, 'inst_final.pkl'), 'rb'))
WP = pickle.load(open(os.path.join(d, 'wallprims.pkl'), 'rb')) if os.path.exists(os.path.join(d, 'wallprims.pkl')) else set()
cls = pickle.load(open(os.path.join(d, 'cls.pkl'), 'rb'))
own = {}
for q in I:
    for i in q['prims']: own[i] = q['key']
def bez(g, n=10):
    return [((1-t)**3*g[0][0]+3*(1-t)**2*t*g[1][0]+3*(1-t)*t*t*g[2][0]+t**3*g[3][0],(1-t)**3*g[0][1]+3*(1-t)**2*t*g[1][1]+3*(1-t)*t*t*g[2][1]+t**3*g[3][1]) for t in [k/(n-1) for k in range(n)]]
def pts(p): return list(p[4]) if p[0] == 'l' else (bez(p[4]) if p[0] == 'c' else list(p[4]) + [p[4][0]])
FIX = {'wall': (0, 0, 230), 'misc': (230, 0, 0), 'lpart': (230, 180, 0), 'lpartc': (240, 120, 0), 'facade': (0, 170, 170),
       'loose': (150, 0, 150), 'wcacc': (200, 0, 200), 'door': (0, 150, 0), 'axis': (255, 0, 255), 'sheet': (120, 120, 120), 'dim': (120, 120, 120)}
def col(k):
    if k in FIX: return FIX[k]
    hh = int(hashlib.md5(k.encode()).hexdigest()[:4], 16) / 65535.0
    r, g, b = colorsys.hsv_to_rgb(hh, 0.85, 0.75); return (int(r * 255), int(g * 255), int(b * 255))
pdf = [os.path.join(d, f) for f in os.listdir(d) if f.lower().endswith('.pdf')][0]
pg = fitz.open(pdf)[0]
pix = pg.get_pixmap(matrix=fitz.Matrix(Z, Z), clip=fitz.Rect(cx - h, cy - h, cx + h, cy + h))
im = Image.frombytes('RGB', (pix.width, pix.height), pix.samples)
src = im.copy()
im = Image.blend(im, Image.new('RGB', im.size, 'white'), 0.75); dr = ImageDraw.Draw(im)
seen = {}
for i, p in enumerate(P):
    q = pts(p); xs = [x for x, y in q]; ys = [y for x, y in q]
    if max(xs) < cx - h or min(xs) > cx + h or max(ys) < cy - h or min(ys) > cy + h: continue
    k = 'wall' if i in WP else own.get(i, cls[i] if cls[i] in ('axis', 'sheet', 'dim', 'tag') else 'FREE')
    if only is not None and k not in only: c = (180, 180, 180)
    else: c = col(k); seen[k] = seen.get(k, 0) + 1
    xy = [((x - cx + h) * Z, (y - cy + h) * Z) for x, y in q]
    if p[0] == 'qu' and p[3] is not None and p[2] is None:
        if len(xy) >= 3: dr.polygon(xy, outline=c)
    elif len(xy) > 1: dr.line(xy, fill=c, width=2)
f = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 13)
lg = sorted(seen.items(), key=lambda t: -t[1])
leg = Image.new('RGB', (230, 18 * len(lg) + 6), 'white'); dl = ImageDraw.Draw(leg)
for n, (k, v) in enumerate(lg): dl.rectangle([4, 4 + 18 * n, 16, 16 + 18 * n], fill=col(k)); dl.text((22, 3 + 18 * n), f'{k} {v}', fill=(0, 0, 0), font=f)
W = src.width * 2 + 10 + leg.width; Hh = max(src.height, leg.height)
sh = Image.new('RGB', (W, Hh), 'white'); sh.paste(src, (0, 0)); sh.paste(im, (src.width + 10, 0)); sh.paste(leg, (2 * src.width + 10, 0)); sh.save(out); print(out, sh.size, lg[:12])
