# Owner's view of a group of unclassified objects (29.09.2026, check 3.7): the catalogue tile alone showed the object
#   too close to tell what it is and where it stands. One tile per group: where on the floor (the whole sheet, the example
#   circled, the other members of the group dotted), the surroundings (the example red, the other members orange) and the
#   source close up without any overlay (a thin red frame around the object).
#   Members of a group: the same drawing (primitives relative to the bbox, 0.1 pt) or the same make-up and the same
#   minimum rotated rectangle (+-3 %, >= 15 mm) - a turned copy counts.
# Run in a floor folder: python3 misc_group_view.py spec.json out_dir
#   spec: [[num, floor, x_pt, y_pt, "title", "count text", "guess", {opts}], ...] - only the entries of this floor are
#   drawn. opts (optional): "box": [x0, y0, x1, y1] - the example is every misc object inside the box (a pattern drawn
#   as many single lines: a wardrobe's hangers); "cluster": gap_pt - the example is the members chained to it within the
#   gap (a grid of dots). Either way the other places are counted as chains of the same drawings.
#   A single line or a pair of lines is grouped by the same drawing only: a line of the same length says nothing.
#   Out: out_dir/tile_<num>.png; review/misc_group_sheet.py puts the tiles on sheets.
import pickle, sys, os, json, math, hashlib, collections, textwrap
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from common import load, pts, PDF, MM_PER_PT
import pymupdf as fitz
from PIL import Image, ImageDraw, ImageFont
from shapely.geometry import MultiPoint
spec = [r for r in json.load(open(sys.argv[1])) if r[1] == os.path.basename(os.getcwd())]
out = sys.argv[2]; os.makedirs(out, exist_ok=True)
P = load(); I = pickle.load(open('inst_final.pkl', 'rb')); pg = fitz.open(PDF)[0]
FD = '/usr/share/fonts/truetype/dejavu/'
fb = ImageFont.truetype(FD + 'DejaVuSans-Bold.ttf', 17); f = ImageFont.truetype(FD + 'DejaVuSans.ttf', 14); fs = ImageFont.truetype(FD + 'DejaVuSans.ttf', 12)
MISC = [n for n, q in enumerate(I) if q['key'] == 'misc' and q['prims']]
def bbox(ids):
    q = [p for i in ids for p in pts(P[i])]
    return (min(x for x, y in q), min(y for x, y in q), max(x for x, y in q), max(y for x, y in q))
def sig(ids, b):
    rows = sorted((P[i][0], round(P[i][1] or 0, 2), tuple((round(x - b[0], 1), round(y - b[1], 1)) for x, y in pts(P[i]))) for i in ids)
    return hashlib.md5(repr(rows).encode()).hexdigest()[:10]
def makeup(ids): return tuple(sorted(collections.Counter(P[i][0] for i in ids).items()))
def mrr(ids):
    g = MultiPoint([p for i in ids for p in pts(P[i])]).minimum_rotated_rectangle
    if g.geom_type != 'Polygon': return [g.length, 0.0]                  # a straight line: its length and no width
    c = list(g.exterior.coords); a, b = math.dist(c[0], c[1]), math.dist(c[1], c[2]); return sorted([a, b], reverse=True)
INFO = {}
for n in MISC:
    ids = I[n]['prims']; b = bbox(ids); INFO[n] = dict(b=b, sig=sig(ids, b), mk=makeup(ids), np=len(ids), mrr=mrr(ids))
def shape2(ids):
    # one or two lines: their lengths (3 %) and the angle between them (5 deg) - the same cross or tick at any place
    ls = [(math.dist(*P[i][4]), math.atan2(P[i][4][1][1] - P[i][4][0][1], P[i][4][1][0] - P[i][4][0][0])) for i in ids if P[i][0] == 'l']
    if len(ls) != len(ids): return None
    L = tuple(sorted(round(math.log(max(l, 1e-3)) / 0.03) for l, _ in ls))
    A = round(abs(math.degrees(ls[0][1] - ls[1][1])) % 180 / 5) if len(ls) == 2 else None
    return (L, A)
def members(n0):
    a = INFO[n0]; res = []; s0 = shape2(I[n0]['prims']) if a['np'] < 3 else None
    for n, r in INFO.items():
        if r['sig'] == a['sig']: res.append(n); continue
        if s0 is not None and r['np'] == a['np'] and shape2(I[n]['prims']) == s0: res.append(n); continue
        if a['np'] < 3 or r['mk'] != a['mk'] or r['np'] != a['np']: continue
        if all(abs(u - v) <= max(0.03 * v, 15 / MM_PER_PT) for u, v in zip(r['mrr'], a['mrr'])): res.append(n)
    return res
def centre(b): return ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)
def render(cx, cy, h, T, fade):
    Z = T / (2 * h)
    pix = pg.get_pixmap(matrix=fitz.Matrix(Z, Z), clip=fitz.Rect(cx - h, cy - h, cx + h, cy + h))
    im = Image.frombytes('RGB', (pix.width, pix.height), pix.samples).resize((T, T))
    if fade: im = Image.blend(im, Image.new('RGB', im.size, 'white'), fade)
    return im, Z
def draw_obj(dr, n, cx, cy, h, Z, col, w):
    for i in I[n]['prims']:
        q = [((x - cx + h) * Z, (y - cy + h) * Z) for x, y in pts(P[i])]
        if len(q) > 1: dr.line(q + ([q[0]] if P[i][0] not in ('l', 'c') else []), fill=col, width=w)
def scalebar(dr, Z, T, mm):
    L = mm / MM_PER_PT * Z; x0, y0 = 12, T - 16
    dr.rectangle([x0 - 4, y0 - 18, x0 + L + 40, y0 + 8], fill=(255, 255, 255))
    dr.line([(x0, y0), (x0 + L, y0)], fill=(0, 0, 0), width=3)
    dr.text((x0 + L + 6, y0 - 9), (f'{mm // 1000} м' if mm >= 1000 else f'{mm} мм'), fill=(0, 0, 0), font=fs)
T = 380; GAP = 8; HEAD = 92; CAP = 22; W = 3 * T + 4 * GAP
def chains(ns, gap):
    ns = list(ns); seen = set(); out = []
    for n in ns:
        if n in seen: continue
        st = [n]; seen.add(n); cur = []
        while st:
            m = st.pop(); cur.append(m); bm = INFO[m]['b']
            for k in ns:
                if k in seen: continue
                bk = INFO[k]['b']
                if bk[0] - gap <= bm[2] and bm[0] - gap <= bk[2] and bk[1] - gap <= bm[3] and bm[1] - gap <= bk[3]: seen.add(k); st.append(k)
        out.append(cur)
    return out
def ubox(ns):
    bs = [INFO[n]['b'] for n in ns]; return (min(b[0] for b in bs), min(b[1] for b in bs), max(b[2] for b in bs), max(b[3] for b in bs))
for row in spec:
    num, fl, x, y, title, cnt, guess = row[:7]; opt = row[7] if len(row) > 7 else {}
    n0 = min(MISC, key=lambda n: math.dist(centre(INFO[n]['b']), (x, y)))
    if 'box' in opt:
        B = opt['box']; ex = [n for n in MISC if B[0] <= INFO[n]['b'][0] and INFO[n]['b'][2] <= B[2] and B[1] <= INFO[n]['b'][1] and INFO[n]['b'][3] <= B[3]]
        sigs = set(INFO[n]['sig'] for n in ex); others = [n for n in MISC if INFO[n]['sig'] in sigs and n not in ex]
        places = [c for c in chains(others, 3.0) if len(c) >= max(3, len(ex) // 3)]
    elif 'cluster' in opt:
        allm = members(n0); ch = chains(allm, opt['cluster']); ex = next(c for c in ch if n0 in c); places = [c for c in ch if c is not ex]
    else:
        ex = [n0]; places = [[n] for n in members(n0) if n != n0]
    b0 = ubox(ex); cx, cy = centre(b0); size = max(b0[2] - b0[0], b0[3] - b0[1])
    mem = [n for c in places for n in c]; nplaces = len(places) + 1
    tile = Image.new('RGB', (W, HEAD + CAP + T + GAP), 'white'); d = ImageDraw.Draw(tile)
    d.text((GAP, 6), f'{num}. {title}', fill=(0, 0, 0), font=fb)
    wmm, hmm = [round(v * MM_PER_PT / 10) * 10 for v in (INFO[n0]['mrr'] if len(ex) == 1 else sorted([b0[2] - b0[0], b0[3] - b0[1]], reverse=True))]
    d.text((GAP, 32), f'Пример: {fl[1]} этаж, размер {wmm} × {hmm} мм. Всего: {cnt.rstrip(".")}. Мест на этом этаже: {nplaces}.', fill=(40, 40, 40), font=f)
    for k, line in enumerate(textwrap.wrap(guess, 125)[:2]): d.text((GAP, 54 + k * 18), line, fill=(20, 70, 160), font=f)
    # 1. the whole sheet
    R = pg.rect; s = T / max(R.width, R.height)
    pix = pg.get_pixmap(matrix=fitz.Matrix(s * 1.0, s * 1.0)); im = Image.frombytes('RGB', (pix.width, pix.height), pix.samples)
    im = Image.blend(im, Image.new('RGB', im.size, 'white'), 0.35); box1 = Image.new('RGB', (T, T), 'white'); box1.paste(im, (0, (T - im.height) // 2))
    dr = ImageDraw.Draw(box1); oy = (T - im.height) // 2
    for c in places:
        u, v = centre(ubox(c)); dr.ellipse([u * s - 4, v * s - 4 + oy, u * s + 4, v * s + 4 + oy], fill=(255, 140, 0))
    dr.ellipse([cx * s - 13, cy * s - 13 + oy, cx * s + 13, cy * s + 13 + oy], outline=(230, 0, 0), width=3)
    # 2. surroundings: about 8 m, or 6 sizes of the object
    h2 = max(4000 / MM_PER_PT, 3 * size); im2, Z2 = render(cx, cy, h2, T, 0.45); dr2 = ImageDraw.Draw(im2)
    for n in mem:
        if n != n0 and abs(centre(INFO[n]['b'])[0] - cx) < h2 * 1.2 and abs(centre(INFO[n]['b'])[1] - cy) < h2 * 1.2: draw_obj(dr2, n, cx, cy, h2, Z2, (255, 140, 0), 2)
    for n in ex: draw_obj(dr2, n, cx, cy, h2, Z2, (230, 0, 0), 2)
    m = 6; dr2.rectangle([(b0[0] - cx + h2) * Z2 - m, (b0[1] - cy + h2) * Z2 - m, (b0[2] - cx + h2) * Z2 + m, (b0[3] - cy + h2) * Z2 + m], outline=(230, 0, 0), width=1)
    scalebar(dr2, Z2, T, 1000)
    # the window of panel 2 on panel 1
    dr.rectangle([(cx - h2) * s, (cy - h2) * s + oy, (cx + h2) * s, (cy + h2) * s + oy], outline=(0, 120, 220), width=2)
    # 3. close up, the source as it is
    h3 = max(0.8 * size, 500 / MM_PER_PT); im3, Z3 = render(cx, cy, h3, T, 0); dr3 = ImageDraw.Draw(im3)
    m = 8; dr3.rectangle([(b0[0] - cx + h3) * Z3 - m, (b0[1] - cy + h3) * Z3 - m, (b0[2] - cx + h3) * Z3 + m, (b0[3] - cy + h3) * Z3 + m], outline=(230, 0, 0), width=1)
    scalebar(dr3, Z3, T, 100 if h3 * MM_PER_PT < 400 else (500 if h3 * MM_PER_PT < 2500 else 1000))
    for k, (im_, cap) in enumerate([(box1, 'Где на этаже: красный — пример, оранжевые — ещё места'),
                                     (im2, f'Окружение, {round(2 * h2 * MM_PER_PT / 1000, 1)} м (красный — пример)'),
                                     (im3, 'Крупно — исходник без наложения')]):
        x0 = GAP + k * (T + GAP); tile.paste(im_, (x0, HEAD + CAP)); d.rectangle([x0, HEAD + CAP, x0 + T - 1, HEAD + CAP + T - 1], outline=(170, 170, 170))
        d.text((x0, HEAD + 3), textwrap.shorten(cap, 58, placeholder='…'), fill=(90, 90, 90), font=fs)
    tile.save(os.path.join(out, f'tile_{num:02d}.png')); print(num, fl, 'example objects', len(ex), 'places on the floor', nplaces, 'size mm', wmm, hmm)
