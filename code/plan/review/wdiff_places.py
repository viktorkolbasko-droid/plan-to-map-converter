# Places where two wall runs of one floor differ (plan/rules/60 §10, rule 17 of plan/rules/70: a threshold changes only after
# the pictures of all the places it moves). For each place: the source, the source with the walls of run A, the source
# with the walls of run B; walls filled by class colour, outline black.
#   python3 wdiff_places.py A_walls.pkl B_walls.pkl out.png [min_m2=0.002] [half_pt=14] [title]
# Run in the floor folder (cfg.py, the PDF). Places are the pieces of the per-class symmetric difference >= min_m2.
import pickle, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from common import PDF, kx
import pymupdf as fitz
from PIL import Image, ImageDraw, ImageFont
from shapely.ops import unary_union
A = pickle.load(open(sys.argv[1], 'rb'))['Wpt']; B = pickle.load(open(sys.argv[2], 'rb'))['Wpt']; out = sys.argv[3]
MIN = float(sys.argv[4]) if len(sys.argv) > 4 else 0.002; H = float(sys.argv[5]) if len(sys.argv) > 5 else 14.0
TITLE = sys.argv[6] if len(sys.argv) > 6 else 'Стены: A — B'
k = abs(kx[0]); m2 = lambda a: a * k * k / 1e6
COL = {'ext': (200, 40, 40), 'cap': (40, 70, 200), 'gkl': (40, 150, 60), 'blk': (220, 130, 0)}
FD = '/usr/share/fonts/truetype/dejavu/'; fb = ImageFont.truetype(FD + 'DejaVuSans-Bold.ttf', 15); f = ImageFont.truetype(FD + 'DejaVuSans.ttf', 13)
def parts(g):
    if g.is_empty: return []
    return [g] if g.geom_type == 'Polygon' else [p for p in getattr(g, 'geoms', []) if p.geom_type == 'Polygon']
places = []
for cls in sorted(set(A) | set(B)):
    ua = unary_union(A.get(cls, [])); ub = unary_union(B.get(cls, []))
    for kind, g in (('B adds', ub.difference(ua)), ('B removes', ua.difference(ub))):
        for p in parts(g):
            if m2(p.area) >= MIN: places.append((m2(p.area), cls, kind, p))
places.sort(key=lambda t: -t[0])
# merge places closer than one tile
tiles = []
for a, cls, kind, p in places:
    c = p.representative_point()
    for t in tiles:
        if abs(t['x'] - c.x) < H and abs(t['y'] - c.y) < H: t['items'].append((a, cls, kind)); break
    else: tiles.append(dict(x=c.x, y=c.y, items=[(a, cls, kind)]))
pg = fitz.open(PDF)[0]; T = 360; ims = []
def draw(W, im, x0, y0, Z):
    d = ImageDraw.Draw(im, 'RGBA')
    for cls, v in W.items():
        for g in v:
            for p in parts(g):
                b = p.bounds
                if b[2] < x0 or b[0] > x0 + 2 * H or b[3] < y0 or b[1] > y0 + 2 * H: continue
                pts = [((x - x0) * Z, (y - y0) * Z) for x, y in p.exterior.coords]
                d.polygon(pts, fill=COL.get(cls, (90, 90, 90)) + (90,), outline=(0, 0, 0))
for n, t in enumerate(tiles, 1):
    x0, y0 = t['x'] - H, t['y'] - H; Z = T / (2 * H)
    pix = pg.get_pixmap(matrix=fitz.Matrix(Z, Z), clip=fitz.Rect(x0, y0, x0 + 2 * H, y0 + 2 * H))
    src = Image.frombytes('RGB', (pix.width, pix.height), pix.samples).resize((T, T))
    a_ = Image.blend(src, Image.new('RGB', src.size, 'white'), 0.35); b_ = a_.copy()
    draw(A, a_, x0, y0, Z); draw(B, b_, x0, y0, Z)
    px = 1000 / k * Z
    for im in (src, a_, b_):
        dd = ImageDraw.Draw(im); dd.rectangle([8, T - 14, 8 + px, T - 9], fill=(0, 0, 0)); dd.text((14 + px, T - 26), '1 м', fill=(0, 0, 0), font=f)
    w = Image.new('RGB', (3 * T + 20, T + 46), 'white'); w.paste(src, (0, 46)); w.paste(a_, (T + 10, 46)); w.paste(b_, (2 * T + 20, 46))
    dw = ImageDraw.Draw(w)
    desc = '; '.join(f"{kind} {cls} {a:.3f} м²" for a, cls, kind in t['items'])
    dw.text((6, 4), f"#{n} ({t['x']:.0f}, {t['y']:.0f}) pt — {desc}", fill=(0, 0, 0), font=fb)
    dw.text((6, 25), 'исходник · стены A · стены B', fill=(80, 80, 80), font=f)
    ims.append(w)
if not ims: print('no places'); sys.exit(0)
sh = Image.new('RGB', (ims[0].width, sum(i.height + 10 for i in ims) + 40), (236, 236, 236)); ImageDraw.Draw(sh).text((8, 10), TITLE, fill=(0, 0, 0), font=fb)
y = 40
for i in ims: sh.paste(i, (0, y)); y += i.height + 10
sh.save(out, optimize=True); print(out, sh.size, len(tiles), 'places')
