# Sheet of the doors 'leaf in the opening + open leaf and chord' found by doors45.py (01.10.2026, test of floor 5, T4):
#   per door - the source with the hinge H, leaf end E, chord end J, the no-hatch band (red) and the door box (blue);
#   the walls of the run by class over the faded source (a wall across the opening is the false wall the rule removes);
#   the primitives in the colour of their owner class. Run from the floor folder:
#   python3 review/door45_sheet.py doors45.json out.png [half_pt=16] [walls.pkl] [title]
import sys, os, json, pickle, colorsys, hashlib
import pymupdf
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, os.getcwd()); sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import cfg, load
D = json.load(open(sys.argv[1])); out = sys.argv[2]
HALF = float(sys.argv[3]) if len(sys.argv) > 3 else 16.0
WF = sys.argv[4] if len(sys.argv) > 4 else ('walls_fixed.pkl' if os.path.exists('walls_fixed.pkl') else 'walls.pkl')
TITLE = sys.argv[5] if len(sys.argv) > 5 else os.path.basename(os.getcwd())
PX = 300; Z = PX / (2 * HALF)
pg = pymupdf.open(cfg.PDF)[0]
P = load()
W = pickle.load(open(WF, 'rb'))['Wpt'] if os.path.exists(WF) else {}
I = pickle.load(open('inst_final.pkl', 'rb')) if os.path.exists('inst_final.pkl') else []
WP = pickle.load(open('wallprims.pkl', 'rb')) if os.path.exists('wallprims.pkl') else set()
own = {i: q['key'] for q in I for i in q['prims']}
WC = {'ext': (220, 40, 40), 'cap': (40, 90, 220), 'gkl': (30, 160, 60), 'blk': (240, 140, 0)}
def col(k):
    if k == 'wall': return (0, 0, 0)
    if k == 'misc': return (255, 0, 0)
    if k in ('door', 'door45'): return (0, 160, 0)
    if k in ('lpart', 'lpartc'): return (240, 150, 0)
    if k == 'FREE': return (190, 190, 190)
    h = int(hashlib.md5(k.encode()).hexdigest()[:4], 16) / 65535.0
    r, g, b = colorsys.hsv_to_rgb(h, 0.8, 0.7); return (int(r * 255), int(g * 255), int(b * 255))
FB = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 14)
FS = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 12)
def src(b, fade=False):
    pix = pg.get_pixmap(matrix=pymupdf.Matrix(Z, Z), clip=pymupdf.Rect(*b))
    im = Image.frombytes('RGB', (pix.width, pix.height), pix.samples).resize((PX, PX))
    if fade: im = Image.blend(im, Image.new('RGB', im.size, 'white'), 0.6)
    return im
def xy(p, b): return ((p[0] - b[0]) * Z, (p[1] - b[1]) * Z)
rows = []
for n, d in enumerate(D):
    cx = (d['box'][0] + d['box'][2]) / 2; cy = (d['box'][1] + d['box'][3]) / 2
    b = (cx - HALF, cy - HALF, cx + HALF, cy + HALF)
    a = src(b); da = ImageDraw.Draw(a)
    nh = d['nohatch']; bx = d['box']
    da.rectangle([*xy(nh[:2], b), *xy(nh[2:], b)], outline=(230, 0, 0), width=2)
    da.rectangle([*xy(bx[:2], b), *xy(bx[2:], b)], outline=(0, 90, 255), width=1)
    for p, c in ((d['H'], (230, 0, 0)), (d['E'], (0, 150, 0)), (d['J'], (0, 90, 255))):
        x, y = xy(p, b); da.ellipse([x - 4, y - 4, x + 4, y + 4], outline=c, width=2)
    w = src(b, True); dw = ImageDraw.Draw(w, 'RGBA')
    for k, polys in W.items():
        c = WC.get(k, (120, 120, 120))
        for g in polys:
            for q in (getattr(g, 'geoms', None) or [g]):
                if q.is_empty or q.geom_type != 'Polygon': continue
                bb = q.bounds
                if bb[2] < b[0] or bb[0] > b[2] or bb[3] < b[1] or bb[1] > b[3]: continue
                dw.polygon([xy(v, b) for v in q.exterior.coords], fill=c + (110,), outline=c + (255,))
    o = Image.new('RGB', (PX, PX), 'white'); do = ImageDraw.Draw(o); seen = {}
    for i, p in enumerate(P):
        g = p[4] if p[0] != 'c' else [p[4][0], p[4][3]]
        xs = [v[0] for v in g]; ys = [v[1] for v in g]
        if max(xs) < b[0] or min(xs) > b[2] or max(ys) < b[1] or min(ys) > b[3]: continue
        k = 'wall' if i in WP else own.get(i, 'FREE'); c = col(k); seen[k] = seen.get(k, 0) + 1
        pts = [xy(v, b) for v in g]
        if p[0] == 'qu' and len(pts) >= 3: do.polygon(pts, outline=c)
        elif len(pts) > 1: do.line(pts, fill=c, width=2 if k == 'misc' else 1)
    yy = 3
    for k, v in sorted(seen.items(), key=lambda t: -t[1])[:9]:
        do.rectangle([3, yy, 13, yy + 10], fill=col(k)); do.text((17, yy - 2), f'{k} {v}', fill=(0, 0, 0), font=FS); yy += 13
    r = Image.new('RGB', (3 * PX + 20, PX + 40), 'white'); dr = ImageDraw.Draw(r)
    cap = f"{TITLE} #{n + 1}: H ({d['H'][0]:.1f}; {d['H'][1]:.1f}) pt, полотно {d['L_mm']} мм" + (', красное' if d.get('red') else '')
    dr.text((4, 2), cap, fill=(0, 0, 0), font=FB)
    for k, (im, lab) in enumerate(((a, 'исходник: H, E, J; полоса «не штриховка»'),
                                   (w, 'стены прогона по классам'), (o, 'примитивы цветом класса владельца'))):
        r.paste(im, (k * (PX + 10), 38)); dr.text((k * (PX + 10) + 2, 20), lab[:48], fill=(90, 90, 90), font=FS)
    rows.append(r)
if not rows: print('no doors'); sys.exit(0)
Sh = Image.new('RGB', (rows[0].width, sum(r.height + 6 for r in rows)), (225, 225, 225)); y = 0
for r in rows: Sh.paste(r, (0, y)); y += r.height + 6
Sh.save(out); print(out, Sh.size, len(rows))
