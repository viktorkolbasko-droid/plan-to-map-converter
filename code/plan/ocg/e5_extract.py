"""Э5: primitives of the AutoCAD sheet with their OCG layer.
 - zero-length segments dropped (PDF_FLATTENED); geometry outside the viewport clip dropped;
 - a filled path = AutoCAD triangle mesh -> union per drawing (one drawing = one source entity), keeps fill opacity;
   a thin filled rectangle (<= 0.75 pt) = a lineweight line -> centre line with width;
 - Bezier curves sampled every <= 0.25 pt; polylines kept as polylines (one source path = one primitive);
 - raster patches (1-5 px images with soft masks): visible colour with the mask, layer = the OCG whose toggling removes them;
 - texts with size, angle, colour.
Writes prims.pkl: list of dict(id, layer, kind fill|line|wline, p, holes, w, col, alpha, seq, src)."""
import pymupdf, numpy as np, pickle, math, collections, sys, time
import os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import sheet
import shapely
from shapely.geometry import Polygon, LineString, box
from shapely.ops import unary_union
t0 = time.time()
d = pymupdf.open(sheet.PDF); pg = d[0]
dr = pickle.load(open('drawings_ext.pkl', 'rb'))
def bez(P, n):
    t = np.linspace(0, 1, n)[:, None]; Q = np.array([[p.x, p.y] for p in P])
    return (1 - t) ** 3 * Q[0] + 3 * (1 - t) ** 2 * t * Q[1] + 3 * (1 - t) * t ** 2 * Q[2] + t ** 3 * Q[3]
def subpaths(items):
    """items -> list of point lists (consecutive items that share ends are one subpath)"""
    out = []; cur = []
    for it in items:
        k = it[0]
        if k == 'l':
            a, b = it[1], it[2]
            if math.hypot(b.x - a.x, b.y - a.y) < 0.01: continue          # zero-length (PDF_FLATTENED)
            seg = [(a.x, a.y), (b.x, b.y)]
        elif k == 'c':
            L = abs(it[2] - it[1]) + abs(it[3] - it[2]) + abs(it[4] - it[3])
            if L < 0.01: continue
            seg = [tuple(p) for p in bez(it[1:5], int(min(200, max(4, L / 0.25))))]
        elif k == 're':
            r = it[1]; seg = [(r.x0, r.y0), (r.x1, r.y0), (r.x1, r.y1), (r.x0, r.y1), (r.x0, r.y0)]
        elif k == 'qu':
            q = it[1]; seg = [(q.ul.x, q.ul.y), (q.ur.x, q.ur.y), (q.lr.x, q.lr.y), (q.ll.x, q.ll.y), (q.ul.x, q.ul.y)]
        else: continue
        if cur and abs(cur[-1][0] - seg[0][0]) < 1e-3 and abs(cur[-1][1] - seg[0][1]) < 1e-3: cur += seg[1:]
        else:
            if cur: out.append(cur)
            cur = list(seg)
    if cur: out.append(cur)
    return out
clip = None; P = []; stats = collections.Counter(); ZONE_L = sheet.L('zone')   # room fills are never lineweight lines
def add(**k): k['id'] = len(P); P.append(k)
for x in dr:
    t = x['type']
    if t == 'clip':
        clip = box(*x['scissor']); continue
    if t == 'group': continue
    L = sheet.strip(x.get('layer'))
    fo = x.get('fill_opacity'); fo = 1.0 if fo is None else round(fo, 3)
    fill = tuple(round(v, 3) for v in x['fill']) if x.get('fill') else None
    col = tuple(round(v, 3) for v in x['color']) if x.get('color') else None
    sp = subpaths(x['items'])
    if not sp: stats['empty'] += 1; continue
    if 'f' in t and fill is not None:
        polys = []
        for pl in sp:
            if len(pl) >= 3:
                g = Polygon(pl)
                if not g.is_valid: g = shapely.make_valid(g)
                if g.area > 1e-6: polys.append(g)
        if polys:
            U = unary_union(polys)
            if clip is not None: U = U.intersection(clip)
            parts = [g for g in getattr(U, 'geoms', [U]) if g.geom_type == 'Polygon' and g.area > 1e-5]
            for g in parts:
                g = g.simplify(0.01)
                rr = g.minimum_rotated_rectangle; xy = np.array(rr.exterior.coords)[:4]
                e = [np.hypot(*(xy[(i + 1) % 4] - xy[i])) for i in range(4)]
                w = min(e[0], e[1]); Lg = max(e[0], e[1])
                if L not in ZONE_L and not g.interiors and w <= 0.75 and Lg >= 1.5 * w and g.area >= 0.85 * rr.area:
                    a, b = ((xy[1] + xy[2]) / 2, (xy[0] + xy[3]) / 2) if e[0] >= e[1] else ((xy[0] + xy[1]) / 2, (xy[2] + xy[3]) / 2)
                    add(layer=L, kind='wline', p=[tuple(a), tuple(b)], w=round(float(w), 3), col=fill, alpha=fo, seq=x['seqno']); stats['wline'] += 1
                else:
                    add(layer=L, kind='fill', p=list(g.exterior.coords), holes=[list(h.coords) for h in g.interiors], col=fill, alpha=fo, seq=x['seqno']); stats['fill'] += 1
        if 's' in t and col is not None:
            for pl in sp:
                add(layer=L, kind='line', p=pl, w=round(x.get('width') or 0, 3), col=col, alpha=1.0, seq=x['seqno']); stats['outline'] += 1
    elif 's' in t and col is not None:
        for pl in sp:
            if clip is not None and not clip.intersects(LineString(pl) if len(pl) > 1 else box(*pl[0], *pl[0])): stats['outside_clip'] += 1; continue
            add(layer=L, kind='line', p=pl, w=round(x.get('width') or 0, 3), col=col, alpha=1.0, seq=x['seqno'], dash=bool(x.get('dashes') and x['dashes'] not in ('[] 0',)))
            stats['line'] += 1
print('drawings ->', len(P), dict(stats), round(time.time() - t0, 1), 's')
# raster patches: colour with soft mask; layer by toggling (render with one layer off, look at the patch)
imgs = pg.get_image_info(xrefs=True)
uis = d.layer_ui_configs(); Z = 3.0
def render(off=None):
    for u in uis: d.set_layer_ui_config(u['number'], 2 if (off is not None and u['number'] == off) else 0)
    p = pg.get_pixmap(matrix=pymupdf.Matrix(Z, Z)); return np.frombuffer(p.samples, np.uint8).reshape(p.height, p.width, 3)
full = render()
_rl = sheet.full(*sheet.RASTER_ROLES)                 # cfg.OCG_RASTER_ROLES: the layers that may hold raster patches
cand = [u for u in uis if u['text'] in _rl]
layer_of = {}
renders = {u['text']: render(u['number']) for u in cand}
for u in uis: d.set_layer_ui_config(u['number'], 0)
for i, im in enumerate(imgs):
    b = im['bbox']; x0, y0, x1, y1 = [int(v * Z) for v in b]
    x1 = max(x1, x0 + 1); y1 = max(y1, y0 + 1)
    base = full[y0:y1, x0:x1].astype(int)
    best = None
    for name, r in renders.items():
        diff = np.abs(r[y0:y1, x0:x1].astype(int) - base).sum()
        if best is None or diff > best[1]: best = (name, diff)
    layer_of[i] = sheet.strip(best[0]) if best and best[1] > 0 else '?'
nimg = collections.Counter()
for i, im in enumerate(imgs):
    pix = pymupdf.Pixmap(d, im['xref']); a = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, pix.n)[:, :, :3].reshape(-1, 3).astype(float) / 255
    sm = d.extract_image(im['xref']).get('smask')
    al = np.frombuffer(pymupdf.Pixmap(d, sm).samples, np.uint8).astype(float) / 255 if sm else np.ones(len(a))
    if al.mean() < 0.05: nimg['transparent'] += 1; continue
    colr = (a * al[:, None]).sum(0) / max(al.sum(), 1e-9)
    b = im['bbox']
    add(layer=layer_of[i], kind='fill', p=[(b[0], b[1]), (b[2], b[1]), (b[2], b[3]), (b[0], b[3]), (b[0], b[1])], holes=[], col=tuple(round(float(v), 3) for v in colr),
        alpha=round(float(al.mean()), 3), seq=-1, src='image'); nimg[layer_of[i]] += 1
print('images', dict(nimg))
T = []
for blk in pg.get_text('dict')['blocks']:
    for l in blk.get('lines', []):
        for s in l['spans']:
            if s['text'].strip(): T.append(dict(text=s['text'], bbox=s['bbox'], size=s['size'], dir=l['dir'], origin=s['origin'], color=s['color'], font=s['font']))
pickle.dump(dict(P=P, T=T), open('prims.pkl', 'wb'))
c = collections.Counter((p['layer'], p['kind']) for p in P)
print('texts', len(T), 'prims', len(P), round(time.time() - t0, 1), 's'); print(sorted(c.items(), key=lambda kv: -kv[1])[:30])
