# Classification map of a run: every primitive drawn in the colour of the class of the object that holds it
#   (walls black, 'misc' red and thick, free primitives light grey), legend per tile. To read against the source.
#   python3 classmap.py run_dir out_prefix [zoom=4] [cols=4] [rows=2] [x0 y0 x1 y1]
import sys, os, pickle, colorsys, hashlib, importlib.util
from PIL import Image, ImageDraw, ImageFont
d = sys.argv[1]; pref = sys.argv[2]; Z = float(sys.argv[3]) if len(sys.argv) > 3 else 4.0
C = int(sys.argv[4]) if len(sys.argv) > 4 else 4; R = int(sys.argv[5]) if len(sys.argv) > 5 else 2
BOX = tuple(map(float, sys.argv[6:10])) if len(sys.argv) > 9 else None
spec = importlib.util.spec_from_file_location('cfg', os.path.join(d, 'cfg.py')); cfg = importlib.util.module_from_spec(spec)
sys.path.insert(0, d); spec.loader.exec_module(cfg)
P = pickle.load(open(os.path.join(d, 'seq.pkl'), 'rb'))[0]
I = pickle.load(open(os.path.join(d, 'inst_final.pkl'), 'rb'))
WP = pickle.load(open(os.path.join(d, 'wallprims.pkl'), 'rb'))
cls = pickle.load(open(os.path.join(d, 'cls.pkl'), 'rb'))
own = {}
for q in I:
    for i in q['prims']: own[i] = q['key']
PAL = {'wall': (0, 0, 0), 'facade': (0, 150, 150), 'glass': (0, 190, 255), 'lpart': (240, 150, 0), 'lpartc': (190, 95, 0),
       'wallline': (90, 90, 90), 'door': (0, 160, 0), 'door45': (0, 160, 0), 'chair': (40, 80, 220), 'desk': (0, 0, 140),
       'screen': (100, 150, 255), 'fscreen': (100, 150, 255), 'plant': (110, 160, 60), 'misc': (255, 0, 0), 'wcacc': (230, 0, 200),
       'wc': (140, 0, 200), 'sink': (140, 0, 200), 'sink_src': (140, 0, 200), 'zone': (215, 190, 100), 'roomsep': (150, 0, 150),
       'tag': (160, 160, 160), 'rack': (140, 80, 30), 'sofa': (240, 110, 160), 'mtable': (50, 50, 120), 'stair': (0, 110, 60),
       'lift': (0, 110, 210), 'column': (90, 45, 0), 'kitchen': (210, 80, 0), 'equip': (160, 0, 0), 'grey': (160, 0, 0),
       'convector': (80, 0, 140), 'loose': (200, 170, 0), 'desk_src': (0, 0, 140), 'furn_src': (240, 110, 160),
       'stool': (40, 80, 220), 'benchend': (0, 0, 140), 'axmark': (220, 220, 220), 'mark': (255, 0, 255), 'fire': (255, 60, 0)}
def colour(k):
    if k in PAL: return PAL[k]
    h = int(hashlib.md5(k.encode()).hexdigest()[:4], 16) / 65535.0
    r, g, b = colorsys.hsv_to_rgb(h, 0.8, 0.7); return (int(r * 255), int(g * 255), int(b * 255))
def bez(g, n=10):
    return [((1-t)**3*g[0][0]+3*(1-t)**2*t*g[1][0]+3*(1-t)*t*t*g[2][0]+t**3*g[3][0],(1-t)**3*g[0][1]+3*(1-t)**2*t*g[1][1]+3*(1-t)*t*t*g[2][1]+t**3*g[3][1]) for t in [k/(n-1) for k in range(n)]]
def pts(p): return list(p[4]) if p[0] == 'l' else (bez(p[4]) if p[0] == 'c' else list(p[4]) + [p[4][0]])
F = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 13)
LEGEND = True
def key_of(i):
    if i in WP: return 'wall'
    if i in own: return own[i]
    return cls[i] if cls[i] in ('axis', 'sheet', 'dim') else 'FREE'
def tile(x0, y0, x1, y1, out):
    W = int((x1 - x0) * Z); H = int((y1 - y0) * Z)
    im = Image.new('RGB', (W, H), 'white'); dr = ImageDraw.Draw(im); seen = {}
    order = []
    for i, p in enumerate(P):
        q = pts(p); xs = [a for a, b in q]; ys = [b for a, b in q]
        if max(xs) < x0 or min(xs) > x1 or max(ys) < y0 or min(ys) > y1: continue
        k = key_of(i); order.append((1 if k == 'misc' else 0, i, k, q, p))
    for _, i, k, q, p in sorted(order, key=lambda t: t[0]):
        if k in ('axis', 'sheet', 'dim'): c = (225, 225, 225)
        elif k == 'FREE': c = (200, 200, 200)
        else: c = colour(k); seen[k] = seen.get(k, 0) + 1
        xy = [((a - x0) * Z, (b - y0) * Z) for a, b in q]
        if p[0] == 'qu' and p[3] is not None and p[2] is None:
            if len(xy) >= 3:
                if min(p[3]) < 0.9 and k not in ('axis', 'sheet', 'dim', 'FREE'):
                    lc = tuple(int(v * 0.35 + 255 * 0.65) for v in c); dr.polygon(xy, fill=lc, outline=c)
                else: dr.polygon(xy, outline=c)
        elif len(xy) > 1: dr.line(xy, fill=c, width=3 if k == 'misc' else 1)
    lg = sorted(seen.items(), key=lambda t: -t[1]) if LEGEND else []
    y = 4
    for k, v in lg:
        dr.rectangle([4, y, 16, y + 12], fill=colour(k)); dr.text((20, y - 1), f'{k} {v}', fill=(0, 0, 0), font=F); y += 16
    im.save(out); return (W, H)
if BOX: print(pref + '.png', tile(*BOX, pref + '.png'))
else:
    X0, Y0, X1, Y1 = cfg.WIN; wx = (X1 - X0) / C; wy = (Y1 - Y0) / R
    for r in range(R):
        for c in range(C):
            a = (X0 + c * wx - 4, Y0 + r * wy - 4, X0 + (c + 1) * wx + 4, Y0 + (r + 1) * wy + 4)
            print(r, c, [round(v) for v in a], tile(*a, f'{pref}_{r}{c}.png'))
