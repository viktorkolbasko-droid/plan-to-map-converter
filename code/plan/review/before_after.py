# "Было — стало" for the owner's places: the source, the result of one run and of another, crops side by side, every
# class in its colour (the same colours as the layer sheets). Both runs must come from the same source extraction.
#   python3 review/before_after.py OLD_FOLDER NEW_FOLDER places.json out.png [Z=7]
#   places.json: [{"n": 1, "title": "...", "box": [x0, y0, x1, y1], "note": "..."}, ...]   (pt, PDF display space)
import os, sys, json, pickle, math, collections
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np, pymupdf
from PIL import Image, ImageDraw, ImageFont
OLD, NEW, PL, OUT = sys.argv[1:5]; Z = float(sys.argv[5]) if len(sys.argv) > 5 else 7.0
os.chdir(NEW)
from common import cfg, pts, walls_file
FB = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 17)
FR = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 14)
WCOL = {'ext': (214, 39, 40), 'cap': (31, 119, 180), 'gkl': (44, 160, 44), 'blk': (255, 127, 14)}
KCOL = {'lpart': (148, 103, 189), 'lpartc': (148, 103, 189), 'gklpart': (0, 160, 80), 'glasspart': (0, 96, 255), 'railing': (0, 181, 181),
        'glass': (227, 119, 194), 'facade': (23, 190, 207), 'wallline': (140, 86, 75), 'column': (188, 189, 34), 'opening': (106, 0, 170),
        'door': (214, 39, 40), 'door45': (255, 127, 14), 'doorhw': (44, 160, 44), 'stair': (31, 119, 180), 'lift': (227, 119, 194),
        'chair': (31, 119, 180), 'armchair': (214, 39, 40), 'sofa': (214, 39, 40), 'desk': (255, 127, 14), 'desk_o': (140, 86, 75),
        'desk_src': (140, 86, 75), 'benchend': (140, 86, 75), 'mtable': (148, 103, 189), 'rtable': (148, 103, 189), 'monitor': (255, 20, 147),
        'screen': (23, 190, 207), 'fscreen': (23, 190, 207), 'furn_src': (227, 119, 194), 'rack': (188, 189, 34), 'wardrobe': (188, 189, 34),
        'reception': (0, 100, 0), 'plant': (44, 160, 44), 'fire': (255, 127, 14), 'wc': (31, 119, 180), 'sink': (148, 103, 189),
        'wcsink': (148, 103, 189), 'wcacc': (44, 160, 44), 'convector': (214, 39, 40), 'roomsep': (148, 103, 189), 'sign': (44, 160, 44),
        'mark': (120, 120, 120), 'axmark': (23, 190, 207), 'misc': (0, 0, 0), 'loose': (0, 0, 0), 'equip': (0, 0, 0)}
def load_run(folder):
    P = pickle.load(open(os.path.join(folder, 'seq.pkl'), 'rb'))[0]
    I = pickle.load(open(os.path.join(folder, 'inst_final.pkl'), 'rb'))
    WP = pickle.load(open(os.path.join(folder, 'wallprims.pkl'), 'rb'))
    wf = os.path.join(folder, 'walls_fixed.pkl'); wf = wf if os.path.exists(wf) else os.path.join(folder, 'walls.pkl')
    W = pickle.load(open(wf, 'rb'))['Wpt']
    own = {}; sh = collections.defaultdict(list)
    for k, q in enumerate(I):
        for i in q['prims']: own[i] = q['key']
        for i in q.get('shared', []): sh[i].append(q['key'])
    return dict(P=P, I=I, WP=WP, W=W, own=own, sh=sh)
R0 = load_run(OLD); R1 = load_run(NEW)
P = R1['P']
cls = pickle.load(open('cls.pkl', 'rb'))
idx = collections.defaultdict(list)
for i, p in enumerate(P):
    q = pts(p)
    if q and cls[i] not in ('sheet', 'axis', 'dim'): idx[(int(q[0][0] // 20), int(q[0][1] // 20))].append(i)
pg = pymupdf.open(cfg.PDF)[0]
def grey(b):
    pix = pg.get_pixmap(matrix=pymupdf.Matrix(Z, Z), clip=pymupdf.Rect(*b), alpha=False)
    A = Image.frombytes('RGB', (pix.width, pix.height), pix.samples)
    g = np.asarray(A).astype(np.float32) @ np.array([0.299, 0.587, 0.114], dtype=np.float32); g = 255 - (255 - g) * 0.22
    return A, Image.fromarray(np.repeat(g[..., None], 3, axis=2).astype(np.uint8))
def panel(R, b, base):
    x0, y0, x1, y1 = b
    im = base.convert('RGBA'); ov = Image.new('RGBA', im.size, (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
    def tr(v): return ((v[0] - x0) * Z, (v[1] - y0) * Z)
    from shapely.geometry import box as _b
    bx = _b(*b)
    for c, v in R['W'].items():
        for p in v:
            for g in getattr(p, 'geoms', [p]):
                if not g.intersects(bx): continue
                d.polygon([tr(t) for t in g.exterior.coords], fill=WCOL.get(c, (90, 90, 90)) + (80,), outline=WCOL.get(c, (90, 90, 90)) + (255,))
                for r in g.interiors: d.polygon([tr(t) for t in r.coords], fill=(255, 255, 255, 0), outline=WCOL.get(c, (90, 90, 90)) + (255,))
    for q in R['I']:
        if q['key'] == 'opening' and q.get('poly'):
            pp = [tr(t) for t in q['poly']]; d.line(pp, fill=KCOL['opening'] + (255,), width=4)
    for gx in range(int(x0 // 20) - 1, int(x1 // 20) + 2):
        for gy in range(int(y0 // 20) - 1, int(y1 // 20) + 2):
            for i in idx.get((gx, gy), []):
                p = P[i]; q = pts(p)
                if not any(x0 - 1 <= v[0] <= x1 + 1 and y0 - 1 <= v[1] <= y1 + 1 for v in q): continue
                k = R['own'].get(i)
                if k is None: continue
                col = KCOL.get(k, (60, 60, 60))
                Q = [tr(v) for v in q]
                if p[0] == 'qu':
                    if p[3] is not None and len(Q) > 2: d.polygon(Q, fill=col + (70,))
                    continue
                d.line(Q, fill=col + (255,), width=max(2, int((p[1] or 0.24) * Z * 0.45)))
                for k2 in R['sh'].get(i, []):
                    d.line(Q, fill=KCOL.get(k2, (60, 60, 60)) + (255,), width=1)
    return Image.alpha_composite(im, ov).convert('RGB')
places = json.load(open(PL))
tiles = []
for pl in places:
    b = pl['box']; A, base = grey(b)
    p0 = panel(R0, b, base); p1 = panel(R1, b, base)
    w = A.width; h = A.height
    head = 48 + 18 * len(pl.get('note', '').split('\n'))
    tw = max([3 * w + 40, int(FB.getlength(f"{pl['n']}. {pl['title']}")) + 20] + [int(FR.getlength(l_)) + 20 for l_ in pl.get('note', '').split('\n')])
    t = Image.new('RGB', (tw, h + head + 26), 'white'); d = ImageDraw.Draw(t)
    d.text((6, 4), f"{pl['n']}. {pl['title']}", font=FB, fill=(0, 0, 0))
    for k_, line in enumerate(pl.get('note', '').split('\n')): d.text((6, 28 + 18 * k_), line, font=FR, fill=(70, 70, 70))
    for k_, (im, lab) in enumerate(((A, 'исходник'), (p0, 'было: тест 2'), (p1, 'стало: код 007'))):
        t.paste(im, (6 + k_ * (w + 14), head)); d.text((6 + k_ * (w + 14), head + h + 4), lab, font=FR, fill=(0, 0, 0))
    tiles.append(t)
Wt = max([t.width for t in tiles] + [int(FR.getlength('оливковый колонны и шкафы, коричневый столы-контуры, оранжевый столы, малиновый мониторы, тёмно-фиолетовый — проёмы A-23. Тонкая линия поверх — общая граница двух объектов.')) + 20]); Ht = sum(t.height + 14 for t in tiles) + 94
S = Image.new('RGB', (Wt, Ht), 'white'); d = ImageDraw.Draw(S)
d.text((8, 10), 'клиент А, 4 этаж — ваши места: исходник, тест 2, перерисовка по правилам 03.10.2026 (код 007-черновик)', font=FB, fill=(0, 0, 0))
d.text((8, 36), 'Цвета: тела стен — по классу (красный наружные, синий капитальные, зелёный ГКЛ); линии — по классу: зелёный ГКЛ без штриховки, синий стекло, '
               'бирюзовый ограждение, фиолетовый — перегородка без типа,', font=FR, fill=(70, 70, 70))
d.text((8, 54), 'оливковый колонны и шкафы, коричневый столы-контуры, оранжевый столы, малиновый мониторы, тёмно-фиолетовый — проёмы A-23. '
               'Тонкая линия поверх — общая граница двух объектов.', font=FR, fill=(70, 70, 70))
y = 84
for t in tiles: S.paste(t, (0, y)); y += t.height + 14
S.save(OUT, optimize=True); print(OUT, S.size)
