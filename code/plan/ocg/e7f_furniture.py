"""Э7м v2 (owner 06.10.2026): furniture by type and by what stands next to it; one type — one shape, the fewest points.
Decisions of the owner (06.10.2026) this step carries out:
 - a desk is a rectangle of four points; its top, front band, edges and strokes are the desk's own and are not drawn;
 - one desk number — one desk; desks of one type have one size; a desk without a number is judged by what stands around;
 - a chair is one connected outline; chairs (seats, tables) of one shape are one type and get one shape;
 - a chair pushed under a desk is under it: seats are drawn first, the desk over them with an opaque top;
 - soft furniture drawn with hatching: the main contour only; repeated parts (sofa seats) get one shape;
 - pedestals, shelving, cabinets, coffee and dining tables are rectangles; kitchen sections along a wall are kitchen.
Stages:
 S1 desk rectangles: the light top + the thin band along a long side (<= 1.6 pt off, parallel) or the closed outline;
 S2 numbers: a desk number belongs to the desk its box overlaps most (>= 20 % of the box) or that holds its centre;
    typical desk sizes come from numbered desks; a free number gets a desk (face, cell of an outline, strips of a top);
 S3 desks without a number: two touching squares -> one table; by context — sofa (inner parts, no chair at it), dining
    or meeting table (>= 2 chairs within 3 pt), coffee table (soft seats within 12 pt), workplace (typical size next to
    numbered desks with a chair), shelving (narrow and long), otherwise «стол или тумба»;
 S4 what lies in a desk is the desk's own; S5 groups and pieces: bands (<= 3.2 pt thin) off, chairs by size;
 S6 kitchen: furniture holding a sink, then sections along the wall; S7 wrapped pieces -> one item;
 S8 rectangular leftovers by context (dining/meeting, coffee table, shelving, pedestal, «стол или тумба»);
 S9 round tables split from their chairs; S10 seat families (one shape — one type); S11 meeting tables and their parts;
 S12 soft furniture main contour, repeated parts unified; S13 chairs under desks restored from their family;
 S14 chairs as one outline with the family shape; S14e (test 10) the seats of numbered workplaces — one figure, square to
 the desk, centred, at the typical depth under it; a plain rectangle at a desk's end — a side pedestal;
 S15 edges and bits to the item they belong to; report.
Objects get 'draw' (drawn primitives; e8 draws only these); the rest stay the object's own for the record.
Reads objects_e7.pkl, prims_e7.pkl, walls (load_walls); writes objects.pkl, prims_f.pkl, furniture.json."""
import pickle, json, math, collections, re, sys, time, os
import numpy as np, shapely
from shapely.geometry import LineString, Polygon, Point, box
from shapely.ops import unary_union, polygonize
from scipy.spatial import cKDTree
import os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import sheet; from e7_comp import geom, load_walls
t0 = time.time(); K = sheet.K
def T(): return f'{time.time() - t0:.1f} s'
D0 = pickle.load(open('prims_e7.pkl', 'rb')); P = D0['P']; TX = D0['T']
O = pickle.load(open('objects_e7.pkl', 'rb')); objs = O['objs']; owner = O['owner']
rep = collections.Counter(); places = collections.defaultdict(list)
TOP = sheet.TOP_DRAW                 # cfg.OCG_TOP_DRAW: a light top as the source shows it (the top's grey at its opacity over white), opaque: hides what is under
FURN_LAYER = sheet.L1('furniture')   # synthetic furniture primitives go on the sheet's furniture layer
G = {}
def g_of(i):
    if i not in G: G[i] = geom(P[i])
    return G[i]
def live(i): return P[i]['kind'] != 'removed'
def mrr(g):
    if g is None or g.is_empty: return None
    r = g.minimum_rotated_rectangle
    if r.is_empty or r.geom_type != 'Polygon' or len(r.exterior.coords) < 4: return None
    c = np.array(r.exterior.coords)[:4]; e1 = c[1] - c[0]; e2 = c[2] - c[1]
    if np.linalg.norm(e2) > np.linalg.norm(e1): e1, e2 = e2, e1
    L = np.linalg.norm(e1)
    if L < 1e-9: return None
    return dict(c=c.mean(0), u=e1 / L, L=L, W=np.linalg.norm(e2), poly=r)
def perp(u): return np.array([-u[1], u[0]])
def rect(cen, u, L, W):
    u = np.asarray(u, float); u = u / np.linalg.norm(u); n = perp(u); c = np.asarray(cen, float)
    return [tuple(c + a * u * L / 2 + b * n * W / 2) for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
def new_prim(layer, kind, pts, col, alpha=1.0, seq=0, **kw):
    r = dict(id=len(P), layer=layer, kind=kind, col=col, p=[tuple(map(float, q)) for q in pts], w=0, seq=seq, alpha=alpha, synthetic=True)
    r.update(kw); P.append(r); return r['id']
def set_owner(ids, k):
    for i in ids: owner[i] = k
def mm(x): return round(x * K / 50) * 50
def parallel(u, v, tol=0.003): return abs(abs(u @ v) - 1) <= tol
def new_obj(key, name, ids, layer='A-82', **kw):
    k = len(objs); objs.append(dict(key=key, layer=layer, name=name, ids=list(ids), kind='obj', **kw)); set_owner(ids, k); return k
def as_rect(k, key, name, cen, u, L, W, layer='A-82'):
    """the object becomes a rectangle of four points: opaque light top + black outline; its primitives stay its own"""
    o = objs[k]; sq = P[o['ids'][0]]['seq'] if o['ids'] else 0; pts = rect(cen, u, L, W)
    f_id = new_prim(FURN_LAYER, 'fill', pts, TOP, alpha=1.0, seq=sq); l_id = new_prim(FURN_LAYER, 'line', pts + [pts[0]], (0.0, 0.0, 0.0), seq=sq)
    o.update(key=key, name=name, layer=layer); o['ids'] = [f_id, l_id] + [i for i in o['ids'] if i not in (f_id, l_id)]; o['draw'] = [f_id, l_id]
    owner[f_id] = owner[l_id] = k
    return Polygon(pts)
def comps(ids, tol=0.05):
    gs = [g_of(i) for i in ids]; t = shapely.STRtree(gs); par = list(range(len(ids)))
    def f(a):
        while par[a] != a: par[a] = par[par[a]]; a = par[a]
        return a
    for a, g in enumerate(gs):
        for b in t.query(g.buffer(tol)):
            if b > a and gs[b].distance(g) <= tol: par[f(a)] = f(b)
    out = collections.defaultdict(list)
    for a, i in enumerate(ids): out[f(a)].append(i)
    return list(out.values())
def safe_union(gs):
    try: return unary_union(gs)
    except Exception:                                      # GEOS precision trouble: snap to a 0.001 pt grid
        return shapely.union_all([shapely.make_valid(g) for g in gs], grid_size=0.001)
def fp_of(ids, simp=0.06):
    parts = []
    for i in ids:
        if not live(i): continue
        g = g_of(i)
        if g.is_empty: continue
        parts.append(g.buffer(0.12, cap_style=2, join_style=2) if g.geom_type in ('LineString', 'MultiLineString') else g.buffer(0.02))
    if not parts: return None
    u = safe_union(parts).buffer(0.25, join_style=2).buffer(-0.25, join_style=2)
    polys = [q for q in getattr(u, 'geoms', [u]) if q.geom_type == 'Polygon' and q.area > 1e-3]
    if not polys: return None
    return Polygon(max(polys, key=lambda x: x.area).exterior).simplify(simp, preserve_topology=True)
def obj_fp(k):
    o = objs[k]; return fp_of(o.get('draw', o['ids']))
FURN_L = sheet.L('furniture')
fi = [p['id'] for p in P if live(p['id']) and p['layer'] in FURN_L and len(p['p']) >= 2]
fg = [LineString(P[i]['p'] + ([P[i]['p'][0]] if P[i]['kind'] == 'fill' else [])) for i in fi]; ft = shapely.STRtree(fg)
_DT = sheet.DESK_TOP                 # cfg.OCG_DESK_TOP: the grey of a desk top
LIGHT = lambda c: c is not None and abs(c[0] - _DT[0]) <= 0.03 and abs(c[1] - _DT[1]) <= 0.03
# ---- v3 owner 06.10.2026: «нам важно распознать тип объекта и… габариты, внешний контур, чтобы его можно было потом изъять
# из плана и заменить другим объектом». The outer outline of a drawing that may be broken (an office chair drawn in short
# strokes with gaps): lines thickened 0.12 pt, gaps up to 2·rc closed, holes filled, the biggest piece.
def solid_fp(ids, rc=None):
    """rc=None: the smallest closing of 0.5, 0.9, 1.4 pt whose biggest piece holds >= 85 % of the ink (a drawing in broken
    strokes needs a wider one)"""
    parts = []
    for i in ids:
        if not live(i): continue
        g = g_of(i)
        if g.is_empty: continue
        parts.append(g.buffer(0.12, cap_style=2, join_style=2) if g.geom_type in ('LineString', 'MultiLineString') else g.buffer(0.02))
    if not parts: return None
    U = safe_union(parts); best = None
    for r_ in ((rc,) if rc else (0.5, 0.9, 1.4)):
        u = U.buffer(r_, join_style=2).buffer(-r_, join_style=2)
        polys = [q for q in getattr(u, 'geoms', [u]) if q.geom_type == 'Polygon' and q.area > 1e-3]
        if not polys: continue
        big = Polygon(max(polys, key=lambda x: x.area).exterior); best = big
        if U.area <= 0 or U.intersection(big.buffer(0.05)).area >= 0.85 * U.area: break
    return best
def roundness(poly):
    """the largest circle inside the hull over the smallest circle around it: a circle 1, an octagon 0.92, a square 0.71"""
    h = poly.convex_hull
    if h.is_empty or h.geom_type != 'Polygon': return 0.0
    try: rin = shapely.maximum_inscribed_circle(h, 0.01).length
    except Exception: return 0.0
    rout = shapely.minimum_bounding_radius(h)
    return rin / rout if rout > 0 else 0.0
def seat_hull(ids):
    """the габарит of a seat: the convex hull of its own source strokes (a chair is drawn convex; what is inside it — seat,
    back, arms — is its inner structure)"""
    gs = [g_of(i) for i in ids if live(i) and not P[i].get('synthetic')]
    if not gs: return None
    h = unary_union(gs).convex_hull
    return h if h.geom_type == 'Polygon' and h.area > 0.5 else None
# ---- F1 a round item is round (owner 06.10.2026: a square chair of a row of chairs was «Пуф или столик круглый ⌀600», and
# its two neighbours became «chairs at a table»): roundness >= 0.9, otherwise a seat (or a table) by its size
nrr = collections.Counter()
for k, o in enumerate(objs):
    if o['key'] != 'round' or not o['ids']: continue
    fp = solid_fp(o['ids'])
    if fp is None: continue
    rr = roundness(fp)
    if rr >= 0.9: continue
    m = mrr(fp); L_, W_ = m['L'] * K, m['W'] * K
    key = 'chair' if (350 <= L_ <= 1000 and 250 <= W_ <= 900) else 'table'
    o.update(key=key, name='Кресло офисное' if key == 'chair' else f'Стол или тумба {mm(m["L"])}×{mm(m["W"])}')
    nrr[key] += 1; places['round_not_round'].append(dict(at=[round(v, 1) for v in m['c']], roundness=round(rr, 2), to=key))
print('F1 round items that are not round -> by size', dict(nrr), T())
# ---- F2 items that one closed outline draws (owner 06.10.2026: «зона reception… угловую стол-стойку»; an L-shaped bench
# with seat cushions; a round table top at 40.20; a long top along a partition taken by the desk next to it).
# A closed outline (a closed polyline or a light fill) of a leftover piece of furniture, >= 0.5 m²:
#  - round (roundness >= 0.9), ⌀ 500–1600 mm: a round table (>= 2 seats within 3 pt) or a pouf / coffee table;
#  - an L or U (area <= 0.85 of its hull, arms 300–1300 mm wide, >= 1200 mm long): a counter («стойка»), or a corner
#    bench when it carries >= 2 seat cushions (closed squares 350–900 mm inside it);
# its pieces are those inside it (>= 90 % of their ink within 0.3 pt). Kitchens (a sink inside) are left to S6.
_seat0 = [unary_union([g_of(i) for i in o['ids']]) for o in objs if o['key'] in ('chair', 'armchair') and o['ids']]
_st0 = shapely.STRtree(_seat0) if _seat0 else None
_sinks0 = [unary_union([g_of(i) for i in o['ids']]).centroid for o in objs if o['key'] == 'sink' and o['ids']]
_desk0 = [g_of(o['ids'][0]) for o in objs if o['key'] == 'desk' and o['ids']]
_dt0 = shapely.STRtree(_desk0) if _desk0 else None
def _seats_near(g, d=3.0): return sum(1 for j in _st0.query(g.buffer(d)) if _seat0[j].distance(g) <= d) if _st0 is not None else 0
f2 = collections.Counter(); F2_KEYS = ('group', 'table', 'furn', 'deskedge', 'storage', 'chairpart')
for k in range(len(objs)):
    o = objs[k]
    if o['key'] not in F2_KEYS or not o['ids']: continue
    cands = []
    for i in o['ids']:
        p_ = P[i]
        if not live(i) or len(p_['p']) < 4: continue
        if p_['kind'] == 'line' and not np.allclose(p_['p'][0], p_['p'][-1], atol=0.05): continue
        if p_['kind'] == 'fill' and not LIGHT(p_['col']): continue
        pg_ = Polygon(p_['p']).buffer(0)
        if pg_.is_empty or pg_.geom_type != 'Polygon' or pg_.area * K * K / 1e6 < 0.5: continue
        cands.append((pg_.area, i, pg_))
    for _, i0, pg_ in sorted(cands, key=lambda t: -t[0]):
        if i0 not in o['ids']: continue
        if any(pg_.buffer(0.5).contains(s_) for s_ in _sinks0): continue
        if _dt0 is not None and sum(_desk0[j].intersection(pg_).area for j in _dt0.query(pg_)) > 0.2 * pg_.area: continue
        m = mrr(pg_); L_, W_ = m['L'] * K, m['W'] * K; rr = roundness(pg_)
        hull_r = pg_.area / max(pg_.convex_hull.area, 1e-9); arm = 2 * pg_.area / max(pg_.length, 1e-9) * K
        # a round top: what lies in its circle (+ 0.4 pt: the outline arcs bulge past the fill's polygon) is its own
        zone_ = shapely.minimum_bounding_circle(pg_).buffer(0.4) if rr >= 0.9 else pg_.buffer(0.3)
        inside = [j for j in o['ids'] if live(j) and (g_of(j).length if g_of(j).area == 0 else g_of(j).area) > 0
                  and (g_of(j).intersection(zone_).length >= 0.9 * g_of(j).length if g_of(j).area == 0
                       else g_of(j).intersection(zone_).area >= 0.9 * g_of(j).area)]
        if rr >= 0.9 and 500 <= L_ <= 1600:
            n_ = _seats_near(pg_)
            key, nm = ('rtable', f'Стол круглый ⌀{mm(m["L"])}') if n_ >= 2 else ('round', f'Пуф или столик круглый ⌀{mm(m["L"])}')
        elif hull_r <= 0.85 and 300 <= arm <= 1300 and L_ >= 1200:
            # seat cushions on it: closed squares 350–900 mm of any piece of furniture lying on it, or a sofa lying on it
            cush = 0; sofa_on = None
            for j in (fi[t] for t in ft.query(pg_)):
                q_ = P[j]['p']
                if j == i0 or len(q_) < 4 or not np.allclose(q_[0], q_[-1], atol=0.05): continue
                qg = Polygon(q_).buffer(0)
                if qg.is_empty or qg.intersection(pg_.buffer(0.3)).area < 0.9 * qg.area: continue
                mq = mrr(qg)
                if mq and 350 <= mq['L'] * K <= 900 and 350 <= mq['W'] * K <= 900: cush += 1
            for k2, o2 in enumerate(objs):
                if k2 == k or o2['key'] != 'sofa' or not o2['ids']: continue
                h2 = unary_union([g_of(j) for j in o2['ids']]).convex_hull; m2 = mrr(h2)
                if m2 is None or h2.distance(pg_) > 0.6: continue
                on_ = h2.intersection(pg_.buffer(0.5)).area >= 0.8 * h2.area                       # the sofa lies on it
                # or it is the sofa's back: a narrow band (<= 500 mm) along >= 60 % of the sofa's length
                back_ = arm <= 500 and h2.exterior.intersection(pg_.buffer(0.6)).length >= 0.6 * m2['L']
                if on_ or back_: sofa_on = k2; break
            if sofa_on is not None or cush >= 2:
                nm = f'Диван (банкетка) угловой {mm(m["L"])}×{mm(m["W"])}'
                if sofa_on is not None:                    # the L is the sofa's own: the sofa grows to it
                    o['ids'] = [j for j in o['ids'] if j not in set(inside)]; objs[sofa_on]['ids'] += inside; set_owner(inside, sofa_on)
                    objs[sofa_on]['name'] = nm
                    if not o['ids']: o['key'] = 'empty'
                    f2['sofa'] += 1; places['closed_outline_items'].append(dict(at=[round(v, 1) for v in m['c']], key='sofa (grown)', size_mm=[round(L_), round(W_)], cushions=cush))
                    continue
                key = 'sofa'
            else: key, nm = 'counter', f'Стойка угловая {mm(m["L"])}×{mm(m["W"])}'
        else: continue
        if set(inside) == set(o['ids']): o.update(key=key, name=nm)
        else:
            o['ids'] = [j for j in o['ids'] if j not in set(inside)]; new_obj(key, nm, inside)
            if not o['ids']: o['key'] = 'empty'
        f2[key] += 1; places['closed_outline_items'].append(dict(at=[round(v, 1) for v in m['c']], key=key, size_mm=[round(L_), round(W_)], roundness=round(rr, 2), hull=round(hull_r, 2)))
print('F2 items of one closed outline', dict(f2), T())
# ================================================================================================ S1 desk rectangles
DESKS = [k for k, o in enumerate(objs) if o['key'] == 'desk']
closed = [i for i in fi if P[i]['kind'] == 'line' and len(P[i]['p']) >= 4 and np.allclose(P[i]['p'][0], P[i]['p'][-1], atol=0.05) and max(P[i]['col']) < 0.05]
CLG = [Polygon(P[i]['p']).buffer(0) for i in closed]; CLT = shapely.STRtree(CLG) if CLG else None
DR = {}; DRM = {}; how_r = collections.Counter(); band_of = collections.defaultdict(list)
for k in DESKS:
    top = objs[k]['ids'][0]; f = g_of(top)
    # the top: all light fills of the object when together they make one rectangle (a top cut into pieces by a glare
    # line, two squares of a cafe table), else the first fill
    lf = [i for i in objs[k]['ids'] if P[i]['kind'] == 'fill' and LIGHT(P[i]['col']) and live(i)]
    if len(lf) > 1:
        U_ = unary_union([g_of(i).buffer(0.03) for i in lf]).buffer(-0.03); mU = mrr(U_)
        if mU and U_.geom_type == 'Polygon' and U_.area >= 0.95 * mU['poly'].area: f = U_
    m = mrr(f)
    if m is None: continue
    best = None
    if CLT is not None:
        for j in CLT.query(f):
            c = CLG[j]
            if c.area > 0 and c.buffer(0.6).contains(f) and c.area <= 1.3 * f.area:
                mc = mrr(c)
                if mc and c.area >= 0.95 * mc['poly'].area and (best is None or c.area < best[0].area): best = (c, mc)
    if best:
        mc = best[1]; DRM[k] = (mc['c'], mc['u'], mc['L'], mc['W']); how_r['контур'] += 1; continue
    # the band: a thin piece or a segment of a line (a desk group's outline, a divider) parallel to a long side,
    # <= 1.6 pt off it, along >= 70 % of the desk
    c, u, L, W = m['c'], m['u'], m['L'], m['W']; n = perp(u); lo, hi = -W / 2, W / 2
    for j in ft.query(m['poly'].buffer(2.0)):
        i = fi[j]
        if i in lf: continue
        q = np.array(fg[j].coords)
        segs = [(q[t], q[t + 1]) for t in range(len(q) - 1)] if P[i]['kind'] == 'line' else [(q.min(0), q.max(0))]
        if P[i]['kind'] != 'line':
            ss = (q - c) @ u; ts = (q - c) @ n
            if ts.max() - ts.min() > 2.2 or ss.max() - ss.min() < 0.7 * L or ss.min() < -L / 2 - 0.6 or ss.max() > L / 2 + 0.6: continue
            if ts.min() >= W / 2 - 0.3 and ts.max() <= W / 2 + 1.6: hi = max(hi, ts.max()); band_of[k].append(i)
            elif ts.max() <= -W / 2 + 0.3 and ts.min() >= -W / 2 - 1.6: lo = min(lo, ts.min()); band_of[k].append(i)
            continue
        for a_, b_ in segs:
            d = b_ - a_; Ld = np.linalg.norm(d)
            if Ld < 1e-6 or not parallel(d / Ld, u, 0.0005): continue
            s0, s1 = sorted(((a_ - c) @ u, (b_ - c) @ u)); ov = min(s1, L / 2) - max(s0, -L / 2)
            if ov < 0.7 * L: continue
            t_ = ((a_ + b_) / 2 - c) @ n
            if W / 2 - 0.3 <= t_ <= W / 2 + 1.6: hi = max(hi, t_)
            elif -W / 2 - 1.6 <= t_ <= -W / 2 + 0.3: lo = min(lo, t_)
    if hi - lo > W + 0.05: how_r['столешница и полоса'] += 1
    else: how_r['столешница'] += 1
    DRM[k] = (c + n * (lo + hi) / 2, u, L, hi - lo)
for k in DESKS:
    if k in DRM: DR[k] = Polygon(rect(*DRM[k]))
DESKS = [k for k in DESKS if k in DR]
print('desk rectangles', dict(how_r), T())
# ================================================================================================ S2 numbers
# desk numbers: magenta labels of size >= 12; a string of several numbers («127 128 129 130») is split — each number's place
# is found along the text by the advance of its characters (Arial: digit 0.556 em, space 0.278, hyphen 0.333)
ADV = {' ': 0.278, '-': 0.333}
labels, LB, LP = [], [], []
for t in TX:
    s_ = t['text']
    if t['size'] <= 12: continue
    if re.fullmatch(r'\d{1,3}(-\d)?', s_.strip()):
        labels.append(dict(text=s_.strip(), bbox=t['bbox'])); LB.append(box(*t['bbox'])); LP.append(Point((t['bbox'][0] + t['bbox'][2]) / 2, (t['bbox'][1] + t['bbox'][3]) / 2))
    elif re.fullmatch(r'\s*\d{1,3}(-\d)?(\s+\d{1,3}(-\d)?)+\s*', s_):
        adv = [ADV.get(ch, 0.556) for ch in s_]; d_ = np.array(t['dir'], float); d_ = d_ / np.linalg.norm(d_); up = np.array([d_[1], -d_[0]])
        o_ = np.array(t['origin'], float); sz_ = t['size']
        for m_ in re.finditer(r'\d{1,3}(-\d)?', s_):
            a0 = sum(adv[:m_.start()]) * sz_; w_ = sum(adv[m_.start():m_.end()]) * sz_
            cen = o_ + d_ * (a0 + w_ / 2) + up * 0.35 * sz_
            pts = [tuple(cen + d_ * sx * w_ / 2 + up * sy * 0.36 * sz_) for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
            labels.append(dict(text=m_.group(), bbox=Polygon(pts).bounds)); LB.append(Polygon(pts)); LP.append(Point(cen))
print('desk number labels', len(labels), '(of them from strings of several numbers', sum(1 for t in TX if t['size'] > 12 and re.fullmatch(r'\s*\d{1,3}(-\d)?(\s+\d{1,3}(-\d)?)+\s*', t['text'])), 'strings)')
def assign_labels():
    DL_ = list(DESKS); dt_ = shapely.STRtree([DR[k] for k in DL_]); score = []
    for n_, b in enumerate(LB):
        for j in dt_.query(b.buffer(0.5)):
            k = DL_[j]; s = DR[k].intersection(b).area / max(b.area, 1e-9)
            if DR[k].buffer(0.3).contains(LP[n_]): s += 1.0
            if s >= 0.2: score.append((s, n_, k))
    lab, taken = {}, set()
    for s, n_, k in sorted(score, reverse=True):
        if n_ in lab or k in taken: continue
        lab[n_] = k; taken.add(k)
    return lab
lab_desk = assign_labels()
NUMBERED = set(lab_desk.values())
sz = collections.Counter((mm(DRM[k][2]), mm(DRM[k][3])) for k in NUMBERED)
# a typical (familiar) workplace size is carried by >= 3 % of the numbered desks (>= 3 desks): owner 06.10.2026 — «рабочие
# места не имеют знакомого размера — их нужно перепроверить»; a rarer size is a desk cut short (S1b below)
TYP_MIN = max(3, round(0.03 * len(NUMBERED)))
FAM = [(L / K, W / K) for (L, W), n in sz.items() if n >= TYP_MIN]
print('desk numbers', len(LP), '| on a desk', len(lab_desk), '| typical desk sizes of numbered desks (mm, count):', sz.most_common(6), T())
def fam_of(L, W, tl=0.04, tw=0.07):
    best = None
    for Lf, Wf in FAM:
        dl, dw = abs(L - Lf) / Lf, abs(W - Wf) / Wf
        if dl <= tl and dw <= tw and (best is None or dl + dw < best[0]): best = (dl + dw, Lf, Wf)
    return best
free_lab = [n_ for n_ in range(len(LP)) if n_ not in lab_desk]
# a number placed next to its desk (at a corner, over a wall): the nearest desk without a number within 12 pt of its box
n2 = 0
for n_ in list(free_lab):
    cand = [(DR[k].distance(LB[n_]), k) for k in DESKS if k not in NUMBERED and DR[k].distance(LB[n_]) <= 12
            and 900 <= DRM[k][2] * K <= 2000 and 500 <= DRM[k][3] * K <= 1000]
    if cand:
        dmin, k = min(cand)
        if not any(DR[k2].distance(LB[n_]) < dmin for k2 in NUMBERED): lab_desk[n_] = k; NUMBERED.add(k); free_lab.remove(n_); n2 += 1
print('numbers next to their desk (<= 12 pt)', n2)
made = []
for n_ in free_lab:
    pt = LP[n_]; cand = []
    near = [fg[j] for j in ft.query(pt.buffer(25))]
    if not near: rep['место: у номера нет мебели'] += 1; continue
    for f in polygonize(unary_union(near)):
        if not f.buffer(0.2).contains(pt): continue
        m = mrr(f)
        if not m or f.area < 0.9 * m['poly'].area: continue
        fm = fam_of(m['L'], m['W'])
        if fm: cand.append((fm[0], 'грань', m['c'], m['u'], fm[1], fm[2]))
    for j in ft.query(pt.buffer(1)):
        i = fi[j]
        if P[i]['kind'] != 'line' or len(P[i]['p']) < 4: continue
        m = mrr(fg[j])
        if not m or not m['poly'].buffer(0.2).contains(pt): continue
        for Lf, Wf in FAM:
            for a, b, swap in ((m['L'] / Lf, m['W'] / Wf, False), (m['W'] / Lf, m['L'] / Wf, True)):
                ka, kb = round(a), round(b)
                if ka < 1 or kb < 1 or ka * kb > 12 or abs(a - ka) > 0.05 * ka or abs(b - kb) > 0.08 * kb: continue
                u = m['u'] if not swap else perp(m['u']); nrm = perp(u)
                d = np.array(pt.coords[0]) - m['c']; La, Lb = (m['L'], m['W']) if not swap else (m['W'], m['L'])
                ia = min(ka - 1, max(0, int((d @ u + La / 2) / (La / ka)))); ib = min(kb - 1, max(0, int((d @ nrm + Lb / 2) / (Lb / kb))))
                cc = m['c'] + u * (-La / 2 + (ia + 0.5) * La / ka) + nrm * (-Lb / 2 + (ib + 0.5) * Lb / kb)
                cand.append((abs(a - ka) + abs(b - kb) + 0.02, f'контур {ka}×{kb}', cc, u, La / ka, Lb / kb))
    fl = [fi[j] for j in ft.query(pt.buffer(20)) if P[fi[j]]['kind'] == 'fill' and LIGHT(P[fi[j]]['col'])]
    for s0 in [i for i in fl if g_of(i).buffer(0.3).contains(pt)]:
        acc = g_of(s0); grow = True
        while grow:
            grow = False
            for i in fl:
                x = g_of(i)
                if x.intersects(acc) and x.difference(acc).area > 0.05 * x.area:
                    u_ = acc.union(x); m = mrr(u_)
                    if m and u_.area >= 0.95 * m['poly'].area and m['L'] * K <= 2200 and m['W'] * K <= 1000: acc = u_; grow = True
        m = mrr(acc)
        if m:
            fm = fam_of(m['L'], m['W'], 0.04, 0.12)
            if fm: cand.append((fm[0] + 0.01, 'полосы столешницы', m['c'], m['u'], fm[1], fm[2]))
    if not cand:
        rep['место: стол не найден — на перепроверку'] += 1
        places['places_unresolved'].append(dict(label=labels[n_]['text'], at=[round(v, 1) for v in pt.coords[0]])); continue
    sc, how, cc, u, L, W = min(cand, key=lambda x: x[0])
    fm = fam_of(L, W, 0.06, 0.12)
    if fm: L, W = fm[1], fm[2]
    made.append(dict(n=n_, how=how, c=cc, u=u, L=L, W=W)); rep[f'место: стол по номеру ({how.split()[0]})'] += 1
FURN_KEYS = {'group', 'table', 'furn', 'chairpart', 'deskedge'}
for d in made:
    poly = Polygon(rect(d['c'], d['u'], d['L'], d['W'])); inner = poly.buffer(0.15)
    k = new_obj('desk', f'Стол рабочий {mm(d["L"])}×{mm(d["W"])}', [], how=d['how'], label=labels[d['n']]['text'])
    DESKS.append(k); DR[k] = poly; DRM[k] = (np.asarray(d['c']), d['u'], d['L'], d['W']); lab_desk[d['n']] = k; NUMBERED.add(k)
    for j in ft.query(poly):
        i = fi[j]; o = owner.get(i)
        if not isinstance(o, int) or objs[o]['key'] not in FURN_KEYS: continue
        g = g_of(i)
        if (g.length > 0 and g.intersection(inner).length >= 0.85 * g.length) or (P[i]['kind'] == 'fill' and g.intersection(inner).area >= 0.85 * g.area):
            objs[o]['ids'].remove(i); objs[k]['ids'].append(i); owner[i] = k
places['desks_from_numbers'] = [dict(label=labels[d['n']]['text'], how=d['how'], at=[round(v, 1) for v in d['c']], size_mm=[round(d['L'] * K), round(d['W'] * K)]) for d in made]
print('desks made from numbers', len(made), T())
# ================================================================================================ S3 desks without a number
CHAIRS0 = [k for k, o in enumerate(objs) if o['key'] in ('chair', 'chairpart') and o['ids']]
SOFT0 = [k for k, o in enumerate(objs) if o['key'] in ('armchair', 'round', 'sofa') and o['ids']]
CF = {k: fp_of(objs[k]['ids']) for k in CHAIRS0 + SOFT0}; CF = {k: v for k, v in CF.items() if v is not None}
cht = shapely.STRtree([CF[k] for k in CHAIRS0 if k in CF]); CHL = [k for k in CHAIRS0 if k in CF]
sft = shapely.STRtree([CF[k] for k in SOFT0 if k in CF]) if SOFT0 else None; SFL = [k for k in SOFT0 if k in CF]
KITCH0 = [unary_union([g_of(i) for i in o['ids']]) for o in objs if o['key'] in ('kitchen', 'sink') and o['ids']]
KU = unary_union(KITCH0) if KITCH0 else Polygon()
def n_chairs(poly, d=3.0): return sum(1 for j in cht.query(poly.buffer(d)) if CF[CHL[j]].distance(poly) <= d)
def n_soft(poly, d=12.0): return sum(1 for j in sft.query(poly.buffer(d)) if CF[SFL[j]].distance(poly) <= d) if sft is not None else 0
def n_inner_parallel(k, c, u, L, W):
    """straight interior lines parallel to a side (seat line, arms of a sofa), >= 30 % of the width, >= 0.4 pt off the outline"""
    n = perp(u); cnt = 0
    for i in objs[k]['ids']:
        if not live(i) or P[i]['kind'] != 'line' or len(P[i]['p']) < 2: continue
        q = np.asarray(P[i]['p'], float)
        for a_, b_ in zip(q[:-1], q[1:]):
            d = b_ - a_; Ld = np.linalg.norm(d)
            if Ld < 0.3 * W or not (parallel(d / Ld, u, 0.005) or parallel(d / Ld, n, 0.005)): continue
            mid = (a_ + b_) / 2 - c; x, y = abs(mid @ u), abs(mid @ n)
            if x <= L / 2 - 0.4 and y <= W / 2 - 0.4: cnt += 1
    return cnt
def n_faces(k, poly):
    ls = []
    for i in objs[k]['ids']:
        if not live(i): continue
        g = g_of(i)
        ls.append(g.boundary if g.geom_type == 'Polygon' else g)
    if not ls: return 0
    try: fs = list(polygonize(unary_union(ls + [poly.exterior])))
    except Exception: return 0
    return sum(1 for f in fs if f.area >= 0.04 * poly.area)
unnum = [k for k in DESKS if k not in NUMBERED]
# two touching squares (or rectangles) of one size side by side -> one table
dtu = shapely.STRtree([DR[k] for k in unnum]) if unnum else None; joined = set(); nj = 0
for a, k in enumerate(unnum):
    if k in joined: continue
    for b in dtu.query(DR[k].buffer(0.3)):
        k2 = unnum[b]
        if k2 == k or k2 in joined: continue
        c1, u1, L1, W1 = DRM[k]; c2, u2, L2, W2 = DRM[k2]
        if abs(L1 - L2) > 0.6 or abs(W1 - W2) > 0.6 or not (parallel(u1, u2, 0.01) or parallel(u1, perp(u2), 0.01)): continue
        if abs(L1 - W1) > 0.1 * L1 or L1 * K > 1000: continue                  # squares (cafe tables), not workplace desks
        un = DR[k].union(DR[k2]); m = mrr(un)
        if m and un.area >= 0.97 * m['poly'].area:
            objs[k]['ids'] += objs[k2]['ids']; set_owner(objs[k2]['ids'], k); objs[k2]['ids'] = []; objs[k2]['key'] = 'empty'
            DRM[k] = (m['c'], m['u'], m['L'], m['W']); DR[k] = Polygon(rect(m['c'], m['u'], m['L'], m['W'])); joined.add(k2); nj += 1; break
unnum = [k for k in unnum if k not in joined]; DESKS = [k for k in DESKS if k not in joined]
s3 = collections.Counter(); faces_dbg = collections.defaultdict(list)
for k in unnum:
    c, u, L, W = DRM[k]; poly = DR[k]; Lm, Wm = L * K, W * K
    nch = n_chairs(poly); nsf = n_soft(poly); nfa = n_faces(k, poly)
    nd = sum(1 for k2 in NUMBERED if DR[k2].distance(poly) <= 0.6)
    faces_dbg[(mm(L), mm(W))].append(nfa)
    npl = n_inner_parallel(k, c, u, L, W)
    if nch == 0 and (nfa >= 3 or npl >= 2) and Lm >= 1300 and Wm >= 600:
        objs[k].update(key='sofa', name=f'Диван {mm(L)}×{mm(W)}'); s3['диван (части внутри, у него нет кресел)'] += 1
    elif fam_of(L, W, 0.04, 0.1) and nch >= 1:
        objs[k]['name'] = f'Стол рабочий {mm(L)}×{mm(W)} (номера нет)'; s3['рабочий стол без номера (размер типовой, у него кресло)'] += 1
        places['desks_without_number'].append([round(v, 1) for v in c]); continue
    elif nch >= 2:
        kind = 'Стол обеденный' if KU.distance(poly) <= 60 else 'Стол переговорный'
        as_rect(k, 'dtable', f'{kind} {mm(L)}×{mm(W)} — мест {nch}', c, u, L, W); s3[kind.lower()] += 1
    elif nsf >= 1 and Lm <= 1600:
        as_rect(k, 'ctable', f'Столик журнальный {mm(L)}×{mm(W)}', c, u, L, W); s3['столик журнальный'] += 1
    elif Wm <= 750 and Lm >= 1500 and nch == 0:
        as_rect(k, 'storage', f'Стеллаж или шкаф {mm(L)}×{mm(W)}', c, u, L, W); s3['стеллаж или шкаф'] += 1
    else:
        as_rect(k, 'table', f'Стол или тумба {mm(L)}×{mm(W)}', c, u, L, W); s3['стол или тумба'] += 1
    DESKS.remove(k)
print('desks without a number:', len(unnum), '| joined pairs', nj, dict(s3), T())
print('   inner parts by size (for the sofa rule):', {k: sorted(v) for k, v in faces_dbg.items()})
# ================================================================================================ desks: the rectangle
snapped = 0
for k in DESKS:
    c, u, L, W = DRM[k]; fm = fam_of(L, W, 0.03, 0.08)
    if fm: L, W = fm[1], fm[2]; snapped += 1
    nm = objs[k]['name'] if 'номера нет' in objs[k]['name'] else f'Стол рабочий {mm(L)}×{mm(W)}'
    DR[k] = as_rect(k, 'desk', nm, c, u, L, W)
for k, ids in band_of.items():
    for i in ids:
        o = owner.get(i)
        if isinstance(o, int) and o != k and objs[o]['key'] in FURN_KEYS and i in objs[o]['ids']:
            objs[o]['ids'].remove(i); objs[k]['ids'].append(i); owner[i] = k
def build_dt():
    global dt, DL
    DL = list(DESKS); dt = shapely.STRtree([DR[k] for k in DL])
build_dt()
print('desks', len(DESKS), '| snapped to a typical size', snapped, T())
# ---- S1b owner 06.10.2026 («одно рабочее место обрезалось»): a numbered desk of an unfamiliar size is checked again. It grows
# to the nearest typical size that is not smaller (length within 5 %): the missing depth on the side that holds its own light
# pieces (v3: its front band), else away from its chair (the back), the missing length at its free end (not against a neighbour desk) — the side where it lines up with the neighbour
# desks of its row wins; a growth into a wall, a column or another desk (> 5 % of the added strip) is tried on the other side;
# a desk that cannot grow is listed for review.
WALLB = [g for _, g in load_walls()['bodies']]; wbt = shapely.STRtree(WALLB) if WALLB else None
CHC = [np.array(obj_fp(k).centroid.coords[0]) for k, o in enumerate(objs) if o['key'] in ('chair', 'chairpart') and o['ids'] and obj_fp(k) is not None]
grow_rows = []
def blocked(poly, k):
    a = poly.area
    if a <= 1e-6: return False
    hit = 0.0
    if wbt is not None: hit += sum(WALLB[j].intersection(poly).area for j in wbt.query(poly))
    hit += sum(DR[d].intersection(poly).area for d in DESKS if d != k and DR[d].intersects(poly))
    if hit > 0.05 * a: return True
    # v3: another item's light top (a long top along a partition) is not the desk's either
    fo = sum(g_of(fi[j]).intersection(poly).area for j in ft.query(poly) if P[fi[j]]['kind'] == 'fill' and LIGHT(P[fi[j]]['col'])
             and g_of(fi[j]).area * K * K / 1e6 >= 0.4 and owner.get(fi[j]) != k and isinstance(owner.get(fi[j]), int)
             and objs[owner[fi[j]]]['key'] not in ('chair', 'chairpart', 'armchair', 'desk'))
    return fo > 0.2 * a
for k in list(DESKS):
    if k not in NUMBERED: continue
    c, u, L, W = DRM[k]; u = np.asarray(u, float) / np.linalg.norm(u); n = perp(u); c = np.asarray(c, float)
    if fam_of(L, W, 0.03, 0.08): continue
    tg = [(Lt, Wt) for Lt, Wt in FAM if abs(Lt - L) <= 0.05 * Lt + 0.3 and Wt >= W - 0.3] or [(Lt, Wt) for Lt, Wt in FAM if Lt >= L - 0.3 and Wt >= W - 0.3]
    if not tg: grow_rows.append(dict(obj=k, at=[round(v, 1) for v in c], size_mm=[mm(L), mm(W)], result='нет типового размера крупнее')); continue
    Lt, Wt = min(tg, key=lambda t: (t[0] - L) + (t[1] - W)); dL, dW = max(Lt - L, 0), max(Wt - W, 0)
    ch = [q for q in CHC if np.linalg.norm(q - c) <= max(L, W)]; s_ch = np.sign(sum(((q - c) @ n) for q in ch)) if ch else 0
    nb = [d for d in DESKS if d != k and DR[d].distance(DR[k]) <= 0.5]
    def lines_up(poly):
        if not nb: return 0.0
        e = []
        for d in nb:
            cd, ud, Ld, Wd = DRM[d]; off = (np.asarray(cd) - c) @ n
            e += [off - Wd / 2, off + Wd / 2]
        pts = np.array(poly.exterior.coords)[:-1]; ys = sorted(set(round(float((q - c) @ n), 2) for q in pts))
        return min(abs(y - x) for y in (ys[0], ys[-1]) for x in e)
    best = None
    for sw in ((-s_ch or 1.0), (s_ch or -1.0)):                                 # depth: the back first
        for sl in (1.0, -1.0):
            c2 = c + n * sw * dW / 2 + u * sl * dL / 2
            poly = Polygon(rect(c2, u, Lt, Wt)); add = poly.difference(DR[k])
            if blocked(add, k): continue
            # v3: the side that holds the desk's own light pieces (its front band) first, then the back, then lining up
            own_ = sum(g_of(i).intersection(add).area for i in objs[k]['ids'] if P[i]['kind'] == 'fill' and LIGHT(P[i]['col']) and not P[i].get('synthetic'))
            sc = lines_up(poly) + (0.0 if sw == (-s_ch or 1.0) else 0.5) - 2.0 * min(1.0, own_ / max(add.area, 1e-9))
            if best is None or sc < best[0]: best = (sc, c2, poly)
    if best is None: grow_rows.append(dict(obj=k, at=[round(v, 1) for v in c], size_mm=[mm(L), mm(W)], result='не растёт: стена, колонна или стол')); continue
    _, c2, poly = best; DRM[k] = (c2, u, Lt, Wt)
    DR[k] = as_rect(k, 'desk', f'Стол рабочий {mm(Lt)}×{mm(Wt)} (достроен до типового, был {mm(L)}×{mm(W)})', c2, u, Lt, Wt)
    grow_rows.append(dict(obj=k, at=[round(v, 1) for v in c2], size_mm=[mm(L), mm(W)], to_mm=[mm(Lt), mm(Wt)], result='достроен до типового'))
build_dt()
places['desks_unfamiliar_size'] = grow_rows
print('desks of an unfamiliar size', len(grow_rows), collections.Counter(r['result'] for r in grow_rows), T())
# ================================================================================================ S4 inside a desk -> its own
moved = collections.Counter(); DUb = unary_union([DR[k] for k in DESKS]).buffer(0.6)
for k, o in enumerate(objs):
    if o['key'] not in FURN_KEYS: continue
    for i in list(o['ids']):
        g = g_of(i)
        # a fill is the desk's when >= 80 % of it lies in the desk (v3: a long top along a partition, 3750×650, was taken by
        # desk 293 because one inner point of it fell into the desk)
        js = [DL[j] for j in dt.query(g) if (DR[DL[j]].buffer(0.25).contains(g) if P[i]['kind'] != 'fill'
                                             else DR[DL[j]].buffer(0.25).intersection(g).area >= 0.8 * max(g.area, 1e-9))]
        if not js and g.geom_type in ('LineString', 'MultiLineString') and g.length >= 10 and g.intersection(DUb).length >= 0.85 * g.length:
            js = sorted([DL[j] for j in dt.query(g.buffer(0.6))], key=lambda d: -g.intersection(DR[d].buffer(0.6)).length)[:1]   # a desk row's outline
        if js: o['ids'].remove(i); objs[js[0]]['ids'].append(i); owner[i] = js[0]; moved[o['key']] += 1
print('pieces inside desks given to the desk', dict(moved), T())
# ================================================================================================ S5 groups and pieces -> chairs
def to_desk_or_edge(i):
    g = g_of(i); m = mrr(g)
    if m is None and g.geom_type == 'LineString' and g.length > 0:          # a straight line (also drawn there and back)
        q = np.array(g.coords); q = q - q.mean(0)
        if np.abs(q).max() < 1e-6: return None
        w_, v_ = np.linalg.eigh(q.T @ q); m = dict(u=v_[:, -1], poly=g)    # its main direction
    if m is None: return None
    if m.get('W', 0) * K > 200: return None             # v3: a band or a line, not a top (a 3750×650 top along a partition went to desk 293)
    js = [DL[j] for j in dt.query(m['poly'].buffer(2.5)) if DR[DL[j]].distance(m['poly']) <= 2.5 and DL[j] in DESKS]
    for d in js:
        if parallel(DRM[d][1], m['u'], 0.004) or parallel(perp(DRM[d][1]), m['u'], 0.004): return d
    return None
def extent(g):
    m = mrr(g)
    if m: return m['L']
    q = np.array(g.coords) if g.geom_type == 'LineString' else np.array(g.exterior.coords)
    return float(max(np.linalg.norm(a - b) for a in q for b in q)) if len(q) <= 40 else g.length
def split_seats(ids):
    """chairs out of a piece of furniture made of several chairs tied by bands and stripes: pieces longer than any seat
    (>= 16 pt) are left out; the rest join greedily — big pieces first — to the nearest cluster within 0.3 pt while the
    cluster stays seat-sized (<= 1000 x 900 mm); chair-sized clusters are chairs"""
    seat = [i for i in ids if extent(g_of(i)) < 16]; rest = [i for i in ids if i not in set(seat)]
    def size(i):
        g = g_of(i); return g.area if g.area > 0 else g.length * 0.05
    cl = []
    for i in sorted(seat, key=lambda i: -size(i)):
        g = g_of(i); best = None
        for c in cl:
            d = c['g'].distance(g)
            if d > 0.3: continue
            u = c['g'].union(g); m = mrr(u)
            if m is None or (m['L'] * K <= 1000 and m['W'] * K <= 900):
                if best is None or d < best[0]: best = (d, c, u)
        if best: best[1]['ids'].append(i); best[1]['g'] = best[2]
        else: cl.append(dict(ids=[i], g=g))
    chairs, left = [], list(rest)
    for c in cl:
        m = mrr(c['g'])
        if m and 350 <= m['L'] * K <= 1000 and 250 <= m['W'] * K <= 900 and len(c['ids']) >= 5: chairs.append(c['ids'])
        else: left += c['ids']
    return chairs, left
nband = nch = nedge = 0
for k in range(len(objs)):
    o = objs[k]
    if o['key'] not in ('group', 'table', 'furn', 'chairpart') or not o['ids']: continue
    thin = []
    for i in list(o['ids']):
        m = mrr(g_of(i))
        if not m or m['W'] > 3.2 or m['L'] < 16 or m['L'] < 4 * m['W']: continue      # longer than any seat (770 mm)
        o['ids'].remove(i); d = to_desk_or_edge(i)
        if d is not None: objs[d]['ids'].append(i); owner[i] = d; nband += 1
        else: thin.append(i)
    if thin: new_obj('deskedge', 'Кромка или экран группы столов (по исходнику)', thin); nedge += len(thin)
    mo = mrr(unary_union([g_of(i) for i in o['ids']])) if o['ids'] else None
    big_ = mo is not None and (mo['L'] * K > 1000 or mo['W'] * K > 900)
    rect_like = mo is not None and fp_of(o['ids']) is not None and fp_of(o['ids']).area >= 0.85 * mo['poly'].area
    if o['ids'] and (o['key'] == 'group' or (o['key'] == 'table' and big_ and not rect_like)):
        chs, keep = split_seats(o['ids'])
        for c_ in chs: new_obj('chair', 'Кресло офисное', c_); nch += 1
        for i in list(keep):                       # long lines along a desk (its band, the row's outline) — the desk's own
            d = to_desk_or_edge(i)
            if d is not None: keep.remove(i); objs[d]['ids'].append(i); owner[i] = d; nband += 1
        mk = mrr(unary_union([g_of(i) for i in keep])) if keep else None
        if mk and mk['W'] * K <= 520 and mk['L'] * K >= 1500:      # a strip along a desk row (band with chair stripes): to the nearest desk
            for i in list(keep):
                g = g_of(i); js = [DL[j] for j in dt.query(g.buffer(3.0)) if DL[j] in DESKS and DR[DL[j]].distance(g) <= 3.0]
                if js: d = min(js, key=lambda d: DR[d].distance(g)); keep.remove(i); objs[d]['ids'].append(i); owner[i] = d; nband += 1
        o['ids'] = keep
        if keep:                                   # what is left: thin pieces — edges; small bits — details for S15
            m = mrr(unary_union([g_of(i) for i in keep]))
            if all(extent(g_of(i)) >= 10 and (mrr(g_of(i)) is None or mrr(g_of(i))['W'] <= 3.2) for i in keep): o.update(key='deskedge', name='Кромка или экран группы столов (по исходнику)')
            elif m is None or m['L'] * K < 600: o.update(key='furn', name='Мебель — деталь (по исходнику)')
    if not o['ids']: o['key'] = 'empty'
    elif o['key'] in ('table', 'furn', 'chairpart'):
        m = mrr(unary_union([g_of(i) for i in o['ids']]))
        if m and 350 <= m['L'] * K <= 1000 and 250 <= m['W'] * K <= 900 and len(o['ids']) >= 8: o.update(key='chair', name='Кресло офисное'); nch += 1
print('bands to desks', nband, '| bands left as edges', nedge, '| chairs out of groups and pieces', nch, T())
# ================================================================================================ S6 kitchen
SINKS = [unary_union([g_of(i) for i in o['ids']]).centroid for o in objs if o['key'] == 'sink' and 'деталь' not in o['name'] and o['ids']]
nks = 0
for k, o in enumerate(objs):
    if o['key'] not in ('group', 'table', 'furn', 'storage', 'desk') or not o['ids'] or k in NUMBERED: continue
    hull = unary_union([g_of(i) for i in o['ids']]).convex_hull
    if any(hull.contains(s) for s in SINKS):
        m = mrr(hull)
        if o['key'] == 'desk': DESKS.remove(k)
        as_rect(k, 'kitchen', f'Кухня встроенная: столешница с мойкой {mm(m["L"])}×{mm(m["W"])} (по исходнику)', m['c'], m['u'], m['L'], m['W'], 'A-76'); nks += 1
BU = unary_union([g for _, g in load_walls()['bodies']])
run = [k for k, o in enumerate(objs) if o['key'] == 'kitchen']
nk = 0; changed = True
while changed:
    changed = False
    ru = [(k, mrr(obj_fp(k))) for k in run]
    for k, o in enumerate(objs):
        if k in run or o['key'] not in ('table', 'furn', 'san', 'chairpart', 'pedestal', 'group', 'storage') or not o['ids']: continue
        m = mrr(obj_fp(k))
        if not m or m['poly'].distance(BU) > 0.8: continue
        for k2, m2 in ru:
            if not m2 or m2['poly'].distance(m['poly']) > 0.6 or abs(m['W'] - m2['W']) > 0.25 * m2['W']: continue
            if not (parallel(m['u'], m2['u'], 0.01) or parallel(m['u'], perp(m2['u']), 0.01)): continue
            as_rect(k, 'kitchen', f'Кухня встроенная: секция {mm(m["L"])}×{mm(m["W"])} (по исходнику)', m['c'], m['u'], m['L'], m['W'], 'A-76')
            run.append(k); nk += 1; changed = True; break
build_dt()
print('kitchen worktops with a sink', nks, '| sections along the wall', nk, T())
# ================================================================================================ S7 wrapped pieces -> one item
PK = [k for k, o in enumerate(objs) if o['key'] in ('chair', 'chairpart', 'furn', 'table', 'armchair') and o['ids'] and 'draw' not in o]
PF = {k: fp_of(objs[k]['ids']) for k in PK}; PK = [k for k in PK if PF[k] is not None and PF[k].area > 0.2]
pt_ = shapely.STRtree([PF[k] for k in PK]) if PK else None; par = {k: k for k in PK}
def fnd(a):
    while par[a] != a: par[a] = par[par[a]]; a = par[a]
    return a
for k in PK:
    for b_ in pt_.query(PF[k].buffer(0.15)):
        k2 = PK[b_]
        if k2 <= k or fnd(k) == fnd(k2): continue
        A, B_ = PF[k], PF[k2]
        if A.distance(B_) > 0.15 or A.boundary.intersection(B_.buffer(0.15)).length < 0.25 * min(A.length, B_.length): continue
        m = mrr(A.union(B_))
        if not m or m['L'] * K > 1400 or m['W'] * K > 1300: continue
        par[fnd(k2)] = fnd(k); PF[fnd(k)] = A.union(B_)
nmg = 0
for k in PK:
    r = fnd(k)
    if r != k: objs[r]['ids'] += objs[k]['ids']; set_owner(objs[k]['ids'], r); objs[k]['ids'] = []; objs[k]['key'] = 'empty'; nmg += 1
for k in set(fnd(k) for k in PK):
    m = mrr(unary_union([g_of(i) for i in objs[k]['ids']]))
    if m and objs[k]['key'] in ('chairpart', 'furn', 'table') and 350 <= m['L'] * K <= 1000 and 250 <= m['W'] * K <= 900 and len(objs[k]['ids']) >= 8:
        objs[k].update(key='chair', name='Кресло офисное')
print('pieces that wrap each other merged into one item', nmg, T())
# ================================================================================================ S9 round tables off their chairs
# a round table is drawn as arcs of one centre and one radius (two half circles) that close a circle, ⌀ 500–1600 mm:
# what lies inside the circle is the table's, what is around — its chairs (by size)
def circ_fit(q):
    q = np.asarray(q, float)
    if len(q) < 8: return None
    A = np.c_[2 * q[:, 0], 2 * q[:, 1], np.ones(len(q))]; cc = np.linalg.lstsq(A, (q ** 2).sum(1), rcond=None)[0]
    r2 = cc[2] + cc[0] ** 2 + cc[1] ** 2
    if r2 <= 0: return None
    r = math.sqrt(r2)
    if np.abs(np.hypot(q[:, 0] - cc[0], q[:, 1] - cc[1]) - r).max() > 0.05: return None
    an = np.unwrap(np.arctan2(q[:, 1] - cc[1], q[:, 0] - cc[0]))
    return np.array([cc[0], cc[1]]), r, abs(math.degrees(an[-1] - an[0]))
nrt = 0
for k in range(len(objs)):
    o = objs[k]
    if o['key'] not in ('table', 'group', 'furn', 'chairpart') or not o['ids'] or 'draw' in o: continue
    arcs = [(i,) + cf for i in o['ids'] if P[i]['kind'] == 'line' and live(i) for cf in [circ_fit(P[i]['p'])] if cf and cf[2] >= 30]
    found = None
    for i, c0, r0, sw in arcs:
        if not (500 <= 2 * r0 * K <= 1600): continue
        tot = sum(sw_ for _, c_, r_, sw_ in arcs if np.linalg.norm(c_ - c0) <= 0.3 and abs(r_ - r0) <= 0.3)
        if tot >= 300: found = (c0, r0); break
    if found is None: continue
    c0, r0 = found; disk = Point(c0).buffer(r0 + 0.3)
    inside = [i for i in o['ids'] if disk.contains(g_of(i))]
    rest = [i for i in o['ids'] if i not in set(inside)]
    nm = f'Стол круглый ⌀{mm(2 * r0)}'
    if not rest: o.update(key='rtable', name=nm)
    else:
        o['ids'] = rest; new_obj('rtable', nm, inside)
        chs, keep = split_seats(rest)
        for c_ in chs: new_obj('chair', 'Кресло офисное', c_)
        keep2 = []
        for c_ in comps(keep, 0.05):
            m = mrr(unary_union([g_of(i) for i in c_]))
            if m and 350 <= m['L'] * K <= 1000 and 150 <= m['W'] * K < 250: new_obj('chairpart', 'Кресло офисное — видимая часть (задвинуто под стол, по исходнику)', c_)
            else: keep2 += c_
        o['ids'] = keep2; keep = keep2
        if not keep: o['key'] = 'empty'
    nrt += 1
print('round tables split from their chairs', nrt, T())
# ================================================================================================ S10 one shape — one type
POSES = [np.array([1, 1]), np.array([-1, -1]), np.array([-1, 1]), np.array([1, -1])]
def frame_pts(poly):
    m = mrr(poly); c, u = m['c'], m['u']; n = perp(u)
    X = np.array(poly.exterior.coords) - c
    return np.c_[X @ u, X @ n], m
def sample(Y, step=0.2):
    out = []
    for a, b in zip(Y[:-1], Y[1:]):
        k_ = max(1, int(np.linalg.norm(b - a) / step)); out.append(a + (b - a) * np.linspace(0, 1, k_ + 1)[:, None])
    return np.vstack(out)
def shape_dist(Sa, Sb):
    tb = cKDTree(Sb); best = (9e9, 0)
    for n_, ps in enumerate(POSES):
        Y = Sa * ps; d = max(tb.query(Y)[0].max(), cKDTree(Y).query(Sb)[0].max())
        if d < best[0]: best = (d, n_)
    return best
SEATK = ('chair', 'armchair', 'round', 'chairpart')
FP = {}
for k, o in enumerate(objs):
    if o['key'] in SEATK and o['ids']:
        fp = fp_of(o['ids'])
        if fp is not None and fp.area > 1: FP[k] = fp
SM = {k: sample(frame_pts(FP[k])[0]) for k in FP}; MM = {k: mrr(FP[k]) for k in FP}
fams = []
for k in sorted(FP, key=lambda k: -MM[k]['L']):
    for f in fams:
        r = f[0]
        if abs(MM[k]['L'] - MM[r]['L']) <= 0.06 * MM[r]['L'] and abs(MM[k]['W'] - MM[r]['W']) <= 0.08 * MM[r]['W'] and shape_dist(SM[k], SM[r])[0] <= 0.6:
            f.append(k); break
    else: fams.append([k])
retyped = collections.Counter()
NAMES = {'chair': 'Кресло офисное', 'armchair': 'Кресло мягкое', 'round': 'Пуф или столик круглый'}
for f in fams:
    if len(f) < 3: continue
    cnt = collections.Counter(objs[k]['key'] for k in f); top_, n_top = cnt.most_common(1)[0]
    if n_top < 0.6 * len(f) or top_ == 'chairpart': continue
    for k in f:
        if objs[k]['key'] != top_:
            retyped[(objs[k]['key'], top_)] += 1; objs[k]['key'] = top_; objs[k]['name'] = NAMES.get(top_, objs[k]['name'])
            places['retyped_by_family'].append(dict(at=[round(v, 1) for v in FP[k].centroid.coords[0]], to=top_, family=len(f)))
print('seat families', len(fams), '| retyped to the family type', dict(retyped), T())
# ================================================================================================ S8 rectangular leftovers by context
CHAIRS1 = [k for k in FP if objs[k]['key'] in ('chair', 'chairpart')]
cht = shapely.STRtree([FP[k] for k in CHAIRS1]) if CHAIRS1 else None; CHL = CHAIRS1; CF.update({k: FP[k] for k in FP})
SOFT1 = [k for k, o in enumerate(objs) if o['key'] in ('armchair', 'round', 'sofa') and o['ids']]
SFP = {k: fp_of(objs[k]['ids']) for k in SOFT1}; SOFT1 = [k for k in SOFT1 if SFP[k] is not None]; CF.update(SFP)
sft = shapely.STRtree([SFP[k] for k in SOFT1]) if SOFT1 else None; SFL = SOFT1
def n_chairs(poly, d=3.0): return sum(1 for j in cht.query(poly.buffer(d)) if CF[CHL[j]].distance(poly) <= d) if cht is not None else 0
s8 = collections.Counter()
for k, o in enumerate(objs):
    if o['key'] not in ('table', 'group', 'furn', 'storage', 'deskedge') or not o['ids'] or 'draw' in o: continue
    if o['key'] == 'deskedge' and len(o['ids']) < 2: continue
    fp = fp_of(o['ids']); m = mrr(fp)
    if m is None: continue
    if o['key'] == 'deskedge':                     # outline lines of a rectangle: their closed face
        try: fa_ = [f for f in polygonize(unary_union([g_of(i) for i in o['ids']])) if f.area >= 0.85 * m['poly'].area]
        except Exception: fa_ = []
        if not fa_: continue
        fp = fa_[0]
    rect_ = fp.area / m['poly'].area; Lm, Wm = m['L'] * K, m['W'] * K
    if rect_ < 0.85 or Lm < 500 or Wm < 250: continue
    nch = n_chairs(m['poly']); nsf = n_soft(m['poly']); near_d = any(DR[d].distance(m['poly']) <= 0.6 for d in DESKS)
    if nch >= 2:
        if Lm >= 1600 or nch >= 5: key, nm = 'mtable', f'Стол переговорный {mm(m["L"])}×{mm(m["W"])} — мест {nch}'
        else: key, nm = 'dtable', f'{"Стол обеденный" if KU.distance(m["poly"]) <= 60 else "Стол переговорный"} {mm(m["L"])}×{mm(m["W"])} — мест {nch}'
    elif nsf >= 1 and Lm <= 1600: key, nm = 'ctable', f'Столик журнальный {mm(m["L"])}×{mm(m["W"])}'
    elif near_d and 350 <= Wm <= 800 and Lm <= 1800: key, nm = 'pedestal', f'Тумба приставная {mm(m["L"])}×{mm(m["W"])}'
    elif Wm <= 750 and Lm >= 1500: key, nm = 'storage', f'Стеллаж или шкаф {mm(m["L"])}×{mm(m["W"])}'
    else: key, nm = 'table', f'Стол или тумба {mm(m["L"])}×{mm(m["W"])}'
    as_rect(k, key, nm, m['c'], m['u'], m['L'], m['W']); s8[key] += 1
    places['rect_by_context'].append(dict(at=[round(v, 1) for v in m['c']], key=key, size_mm=[round(Lm), round(Wm)], chairs=nch, soft=nsf))
# a big top of another shape (an L, a rounded corner) with a chair at it — a counter («стойка»): its main contour is drawn
for k, o in enumerate(objs):
    if o['key'] not in ('table', 'group', 'furn') or not o['ids'] or 'draw' in o: continue
    fp = fp_of(o['ids']); m = mrr(fp)
    if m is None or m['L'] * K < 1500: continue
    lf = sum(g_of(i).area for i in o['ids'] if P[i]['kind'] == 'fill' and LIGHT(P[i]['col']))
    seats_ = sum(1 for k2 in list(FP) + SOFT1 if objs[k2]['key'] in ('chair', 'chairpart', 'round', 'armchair') and CF.get(k2) is not None and CF[k2].distance(m['poly']) <= 6.0)
    if lf >= 0.4 * fp.area and seats_ >= 1:
        o.update(key='counter', name=f'Стойка (по исходнику) {mm(m["L"])}×{mm(m["W"])}'); s8['counter'] += 1
print('rectangular furniture by what stands next to it', dict(s8), T())
# ================================================================================================ S11 meeting tables and their parts
SEATS_ = [k for k in FP if objs[k]['key'] in ('chair', 'armchair')]; st_ = shapely.STRtree([FP[k] for k in SEATS_]) if SEATS_ else None
nmt = 0; TB = {}
for k, o in enumerate(objs):
    if o['key'] not in ('table', 'mtable', 'dtable') or not o['ids']: continue
    fp = fp_of(o.get('draw', o['ids'])) if 'draw' in o else fp_of(o['ids'])
    if fp is None: continue
    TB[k] = fp
    if o['key'] == 'table' and 'draw' not in o and st_ is not None:
        n_ = sum(1 for j in st_.query(fp.buffer(1.5)) if FP[SEATS_[j]].distance(fp) <= 1.5); m = mrr(fp)
        if n_ >= 3 and m['L'] * K >= 1200: o.update(key='mtable', name=f'Стол переговорный {mm(m["L"])}×{mm(m["W"])} — мест {n_}'); nmt += 1
mv_t = 0
for k, o in enumerate(objs):
    if o['key'] not in ('deskedge', 'furn', 'group') or not o['ids']: continue
    for i in list(o['ids']):
        g = g_of(i)
        if g.length <= 0: continue
        for t, fp in TB.items():
            if fp.distance(g) <= 0.6 and g.intersection(fp.boundary.buffer(0.6)).length >= 0.8 * g.length:
                o['ids'].remove(i); objs[t]['ids'].append(i); owner[i] = t; mv_t += 1; break
TBK = list(TB); tbt = shapely.STRtree([TB[k].buffer(0.3) for k in TBK]) if TBK else None; nin = 0
for k, o in enumerate(objs):
    if k in TB or o['key'] not in ('furn', 'deskedge', 'group', 'table', 'round') or not o['ids'] or tbt is None or 'draw' in o: continue   # seats never (a «round» inside a table is its detail)
    fp = fp_of(o['ids'])
    if fp is None or fp.area <= 0: continue
    for j in tbt.query(fp):
        t = TBK[j]
        if t != k and fp.intersection(TB[t].buffer(0.3)).area >= 0.9 * fp.area and fp.area <= 0.3 * TB[t].area:
            objs[t]['ids'] += o['ids']; set_owner(o['ids'], t); o['ids'] = []; o['key'] = 'empty'; nin += 1
            places['merged_into_tables'].append(dict(at=[round(v, 1) for v in fp.centroid.coords[0]], into=objs[t]['name'])); break
print('meeting tables (>= 3 seats around)', nmt, '| lines along tables given to them', mv_t, '| parts inside tables merged', nin, T())
# a meeting table drawn as one closed outline (a rounded rectangle) with seats around: the outline and everything inside it
# that is not a seat — strips, sockets, edges — is the table (owner 06.10: a table fell apart into parts of different types)
SEATF = {k: CF[k] for k in CF if objs[k]['key'] in ('chair', 'armchair', 'round')}
LOOSE = ('deskedge', 'furn', 'group', 'table', 'chairpart')
cand_ids = [i for o in objs if o['key'] in LOOSE and 'draw' not in o for i in o['ids'] if P[i]['kind'] == 'line' and live(i) and len(P[i]['p']) >= 2]
nmt2 = 0
# the outline may be drawn in pieces with small gaps at the corners (rounded corners drawn apart): free ends of the
# pieces within 3.5 pt of another piece's free end are joined by a straight connector before the faces are taken
ends = []
for i in cand_ids:
    q = P[i]['p']
    if len(q) >= 2 and math.dist(q[0], q[-1]) > 0.05: ends += [(i, np.array(q[0], float)), (i, np.array(q[-1], float))]
conn_ = []
if ends:
    E_ = np.array([e for _, e in ends]); et = cKDTree(E_)
    for a_, (i, e) in enumerate(ends):
        best = None
        for b_ in et.query_ball_point(e, 3.5):
            if b_ == a_ or ends[b_][0] == i: continue
            d = np.linalg.norm(E_[b_] - e)
            if best is None or d < best[0]: best = (d, b_)
        if best and best[0] > 1e-6: conn_.append(LineString([tuple(e), tuple(E_[best[1]])]))
try: tfaces = list(polygonize(safe_union([g_of(i) for i in cand_ids] + conn_))) if cand_ids else []
except Exception: tfaces = []
sft_ = shapely.STRtree(list(SEATF.values())) if SEATF else None; SK = list(SEATF)
for pl in tfaces:
    mp_ = mrr(pl)
    if mp_ is None or mp_['L'] * K < 1200 or mp_['W'] * K < 600 or pl.area < 0.8 * mp_['poly'].area or mp_['L'] * K > 8000: continue
    ns = sum(1 for j in sft_.query(pl.buffer(1.5)) if SEATF[SK[j]].distance(pl) <= 1.5 and SEATF[SK[j]].intersection(pl).area < 0.5 * SEATF[SK[j]].area) if sft_ is not None else 0
    if ns < 3: continue
    inner = pl.buffer(0.3); tk = new_obj('mtable', f'Стол переговорный {mm(mp_["L"])}×{mm(mp_["W"])} — мест {ns}', [])
    for k2, o2 in enumerate(objs):
        if k2 == tk or o2['key'] not in LOOSE + ('chair',) or not o2['ids']: continue
        if o2['key'] == 'chair':
            f2 = CF.get(k2) or fp_of(o2['ids'])
            if f2 is None or f2.area > 0.3 * 600 * 500 / K / K: continue      # real seats stay
        for i2 in list(o2['ids']):
            if inner.contains(g_of(i2)): o2['ids'].remove(i2); objs[tk]['ids'].append(i2); owner[i2] = tk
        if not o2['ids'] or ('draw' in o2 and not any(j in o2['ids'] for j in o2['draw'])): o2['key'] = 'empty'; o2.pop('draw', None)
    nmt2 += 1
print('meeting tables drawn as one closed outline', nmt2, T())
# one table — one object: a desk and a table found twice (by its top and by its outline) are one; the numbered desk keeps
# the number and takes the outer outline when the two make a rectangle together
ndd = 0
TFP = {t: obj_fp(t) for t, ot in enumerate(objs) if ot['key'] in ('mtable', 'dtable', 'table', 'ctable', 'storage', 'rtable') and ot['ids']}
TFP = {t: g for t, g in TFP.items() if g is not None}; TFK = list(TFP); tft = shapely.STRtree([TFP[t] for t in TFK]) if TFK else None
for d in list(DESKS):
    for j in (tft.query(DR[d]) if tft is not None else []):
        t = TFK[j]; ot = objs[t]
        if t == d or not ot['ids'] or ot['key'] == 'empty': continue
        g = TFP[t]
        if g.intersection(DR[d]).area < 0.5 * min(g.area, DR[d].area): continue
        U_ = DR[d].union(g); m = mrr(U_)
        objs[d]['ids'] += [i for i in ot['ids'] if i not in ot.get('draw', [])]; set_owner(objs[d]['ids'], d)
        ot['ids'] = []; ot['key'] = 'empty'; ot.pop('draw', None); ndd += 1
        if m and U_.area >= 0.9 * m['poly'].area:
            DRM[d] = (m['c'], m['u'], m['L'], m['W']); DR[d] = as_rect(d, 'desk', f'Стол рабочий {mm(m["L"])}×{mm(m["W"])}', m['c'], m['u'], m['L'], m['W'])
# a long rectangle drawn by its two long sides only (a cabinet along a window): two parallel lines of one length
nps = 0
LL = [(k, i) for k, o in enumerate(objs) if o['key'] in ('deskedge', 'furn') and 'draw' not in o for i in o['ids'] if P[i]['kind'] == 'line' and g_of(i).length >= 30]
used_ = set()
for a_ in range(len(LL)):
    ka, ia = LL[a_]
    if ka in used_: continue
    for b_ in range(len(LL)):
        kb, ib = LL[b_]
        if b_ == a_ or kb in used_: continue
        ga, gb = g_of(ia), g_of(ib)
        if abs(ga.length - gb.length) > 0.05 * max(ga.length, gb.length): continue
        u_ = np.array(ga.coords[-1]) - np.array(ga.coords[0]); v_ = np.array(gb.coords[-1]) - np.array(gb.coords[0])
        if np.linalg.norm(u_) < 1e-6 or np.linalg.norm(v_) < 1e-6 or not parallel(u_ / np.linalg.norm(u_), v_ / np.linalg.norm(v_), 0.002): continue
        if not (250 <= ga.distance(gb) * K <= 800): continue
        m = mrr(unary_union([ga, gb]).convex_hull)
        if m is None or m['L'] < 0.9 * ga.length: continue
        if kb != ka:
            objs[ka]['ids'] += objs[kb]['ids']; set_owner(objs[kb]['ids'], ka); objs[kb]['ids'] = []; objs[kb]['key'] = 'empty'
        as_rect(ka, 'storage', f'Стеллаж или шкаф {mm(m["L"])}×{mm(m["W"])}', m['c'], m['u'], m['L'], m['W']); nps += 1; used_ |= {ka, kb}; break
for k, o in []:
    ls = [i for i in o['ids'] if P[i]['kind'] == 'line']
    best = None
    for a_ in range(len(ls)):
        for b_ in range(a_ + 1, len(ls)):
            ga, gb = g_of(ls[a_]), g_of(ls[b_])
            if abs(ga.length - gb.length) > 0.05 * max(ga.length, gb.length) or ga.length < 30: continue
            u_ = np.array(ga.coords[-1]) - np.array(ga.coords[0]); v_ = np.array(gb.coords[-1]) - np.array(gb.coords[0])
            if np.linalg.norm(u_) < 1e-6 or np.linalg.norm(v_) < 1e-6 or not parallel(u_ / np.linalg.norm(u_), v_ / np.linalg.norm(v_), 0.002): continue
            dd = ga.distance(gb) * K
            if 250 <= dd <= 800: best = (ga, gb); break
        if best: break
    if best:
        m = mrr(unary_union(best).convex_hull)
        if m: as_rect(k, 'storage', f'Стеллаж или шкаф {mm(m["L"])}×{mm(m["W"])}', m['c'], m['u'], m['L'], m['W']); nps += 1
print('desks found twice merged', ndd, '| long cabinets by their two sides', nps, T())
# ---- F2b a table is its top (owner 06.10.2026: «выделить общий габарит»; the arms of chairs pushed to a table lay across
# its edge and were the table's): a table whose light top (its light fills) is >= 60 % of its outline keeps the lines that lie
# on the top (>= 50 % of the line within 0.3 pt of it); the others are loose pieces again (F4 gives them to their chair)
nf2b = 0
for k, o in enumerate(objs):
    if o['key'] not in ('mtable', 'dtable', 'table', 'ctable', 'rtable') or not o['ids']: continue
    lf = [g_of(i) for i in o['ids'] if P[i]['kind'] == 'fill' and LIGHT(P[i]['col']) and live(i) and not P[i].get('synthetic')]
    if not lf: continue
    top = safe_union([g.buffer(0.05) for g in lf]).buffer(0.25, join_style=2).buffer(-0.25, join_style=2)
    fp = fp_of([i for i in o['ids'] if not P[i].get('synthetic')])
    if fp is None or top.is_empty or top.area < 0.6 * fp.area: continue
    tz = top.buffer(0.3); off = []
    for i in o['ids']:
        if P[i]['kind'] != 'line' or P[i].get('synthetic') or not live(i) or i in o.get('draw', []): continue
        g = g_of(i)
        if g.length > 0 and g.intersection(tz).length < 0.5 * g.length: off.append(i)
    if off:
        o['ids'] = [i for i in o['ids'] if i not in set(off)]; nf2b += len(off)
        for c_ in comps(off, 0.05): new_obj('furn', 'Мебель — кромка или линия (по исходнику)', c_, not_of=k)
print('F2b lines off the table tops (their chairs\' arms)', nf2b, T())
# ---- F3 one seat — one object (owner 06.10.2026: «два кресла, которые не распознались каждый как один объект, разбились на
# разные типы»; the reception chairs drawn in broken strokes were two «chairs» and a «round pouf»). Pieces of seats and
# loose pieces (chairs, chair parts, edges, lines; components of groups), each <= 1200 mm, that touch (<= 0.6 pt) or whose
# hulls overlap by >= 30 % (a drawing in broken strokes) join, the closest first, while the seat stays seat-sized
# (<= 900 mm, or <= 1200 mm and squarish: across >= 0.7 of its length); a «seat» longer than 900 mm and narrow (two chairs
# of a row in one object) falls into its pieces first; two whole seats (>= 500 × 400 mm each) are one only when together they are one seat's size (<= 900 mm) or
# overlap by >= 25 %. Loose pieces that lie on a desk or a table are the desk's. A seat >= 800 mm long is soft («мягкое»).
F3_SEAT = ('chair', 'armchair', 'chairpart'); F3_LOOSE = ('furn', 'deskedge', 'group')
_tabs3 = [DR[d] for d in DESKS] + [obj_fp(t) for t, ot in enumerate(objs) if ot['key'] in ('mtable', 'dtable', 'rtable', 'ctable', 'table', 'counter') and ot['ids']]
_tabs3 = [g for g in _tabs3 if g is not None]; _tt3 = shapely.STRtree(_tabs3) if _tabs3 else None
def _on_table(g):
    if _tt3 is None: return False
    L_ = max(g.length, 1e-9) if g.area == 0 else max(g.area, 1e-9)
    for j in _tt3.query(g.buffer(0.3)):
        x = _tabs3[j].buffer(0.3).intersection(g)
        if (x.length if g.area == 0 else x.area) >= 0.2 * L_: return True
    return False
pieces = []                                   # (object, ids, geometry, is seat)
for k, o in enumerate(objs):
    if not o['ids'] or 'draw' in o: continue
    if o['key'] in F3_SEAT:
        grp_ = [list(o['ids'])]
        h0 = seat_hull(o['ids']); m0 = mrr(h0) if h0 is not None else None
        # a «seat» longer than one seat and narrow (two chairs of a row in one object: 1050×550) falls into its pieces,
        # which join again below by the closest-first rule
        if m0 is not None and m0['L'] * K > 900 and m0['W'] < 0.7 * m0['L'] and o['key'] != 'armchair': grp_ = comps(o['ids'], 0.05)
    elif o['key'] in F3_LOOSE: grp_ = comps(o['ids'], 0.05)
    else: continue
    for c_ in grp_:
        g = unary_union([g_of(i) for i in c_ if live(i)])
        if g.is_empty: continue
        m = mrr(g.buffer(0.01))
        if m is None or m['L'] * K > 1200: continue
        seat_ = o['key'] in F3_SEAT
        if not seat_ and _on_table(g): continue
        pieces.append((k, c_, g, seat_))
_pg = [p_[2] for p_ in pieces]; _pt = shapely.STRtree(_pg) if _pg else None
_ph = [g.convex_hull for g in _pg]
def _whole(a):                                 # a whole seat on its own: >= 500 × 400 mm
    if not pieces[a][3]: return False
    m_ = mrr(_ph[a]) if _ph[a].area > 0 else None
    return bool(m_ and m_['L'] * K >= 500 and m_['W'] * K >= 400)
WH = [_whole(a) for a in range(len(pieces))]
edges3 = []
for a, g in enumerate(_pg):
    for b in (_pt.query(g.buffer(0.6)) if _pt is not None else []):
        if b <= a or not (pieces[a][3] or pieces[b][3]): continue
        d = _pg[b].distance(g)
        ov = (_ph[a].intersection(_ph[b]).area / max(min(_ph[a].area, _ph[b].area), 1e-9)) if _ph[a].area > 0 and _ph[b].area > 0 else 0.0
        if d <= 0.6 or ov >= 0.3: edges3.append((-ov, d, a, b))
edges3.sort()
gid3 = list(range(len(pieces))); grp3 = {a: [a] for a in range(len(pieces))}
f3 = collections.Counter()
for _, d, a, b in edges3:              # the closest first; a merge keeps the seat seat-sized
    A, B = gid3[a], gid3[b]
    if A == B: continue
    ids_ = [i for x in grp3[A] + grp3[B] for i in pieces[x][1]]; h_ = seat_hull(ids_); m = mrr(h_) if h_ is not None else None
    if m is None: continue
    if any(WH[x] for x in grp3[A]) and any(WH[x] for x in grp3[B]):
        # two whole seats are one only when together they are one seat's size (<= 900 mm) or they overlap by >= 25 %
        hA = seat_hull([i for x in grp3[A] for i in pieces[x][1]]); hB = seat_hull([i for x in grp3[B] for i in pieces[x][1]])
        ovAB = hA is not None and hB is not None and hA.intersection(hB).area >= 0.25 * min(hA.area, hB.area)
        if not (m['L'] * K <= 900 or ovAB): f3['two whole seats side by side'] += 1; continue
    elif m['L'] * K > 1200 or (m['L'] * K > 900 and m['W'] < 0.7 * m['L']): f3['too big'] += 1; continue   # one seat: <= 900 mm, or <= 1200 mm and squarish
    for x in grp3[B]: gid3[x] = A
    grp3[A] += grp3.pop(B)
cl3 = grp3
for mem in cl3.values():
    if len(mem) < 2 or not any(pieces[a][3] for a in mem): continue
    ids_ = [i for a in mem for i in pieces[a][1]]; sf = seat_hull(ids_); m = mrr(sf) if sf is not None else None
    if m is None or m['W'] * K < 350: f3['too thin'] += 1; continue
    main = max((a for a in mem if pieces[a][3]), key=lambda a: pieces[a][2].convex_hull.area); km = pieces[main][0]
    soft = objs[km]['key'] == 'armchair' or m['L'] * K >= 800                 # an office chair is <= 800 mm long
    for a in mem:
        k2, c_, _, _ = pieces[a]
        if k2 == km: continue
        objs[k2]['ids'] = [i for i in objs[k2]['ids'] if i not in set(c_)]
        if not objs[k2]['ids']: objs[k2]['key'] = 'empty'
        for i in c_:
            if i not in objs[km]['ids']: objs[km]['ids'].append(i)
        set_owner(c_, km)
    objs[km].update(key='armchair' if soft else 'chair', name=f'Кресло мягкое {mm(m["L"])}×{mm(m["W"])}' if soft else 'Кресло офисное')
    f3['armchair' if soft else 'chair'] += 1
    places['seats_assembled'].append(dict(at=[round(v, 1) for v in m['c']], pieces=len(mem), size_mm=[round(m['L'] * K), round(m['W'] * K)], key='armchair' if soft else 'chair'))
print('F3 seats assembled from their pieces', dict(f3), T())
# ---- F3c chairs in a row at a table edge (owner 06.10.2026, 40.15: one «chair» held the arm of its neighbour and became a
# soft seat 850 mm long). The seats that stand at one edge of a rectangular table (centre <= 14 pt in front of it, within
# its length ± 3 pt) share their strokes anew: 1-D k-means of the strokes' centres along the edge, k = the number of seats,
# started at the seats' centres; applied when the new seats are of one width (widest <= 1.4 × narrowest).
nf3c = 0
HK3 = [k for k, o in enumerate(objs) if o['key'] in ('chair', 'armchair') and o['ids'] and 'draw' not in o]
HUL3 = {k: seat_hull(objs[k]['ids']) for k in HK3}; HK3 = [k for k in HK3 if HUL3[k] is not None]
CEN3 = np.array([HUL3[k].centroid.coords[0] for k in HK3]) if HK3 else np.zeros((0, 2)); tr3 = cKDTree(CEN3) if HK3 else None
for t, ot in enumerate(objs):
    if ot['key'] not in ('mtable', 'dtable', 'table', 'ctable') or not ot['ids'] or tr3 is None: continue
    gt = obj_fp(t); mt = mrr(gt) if gt is not None else None
    if mt is None: continue
    ct, ut = np.asarray(mt['c']), np.asarray(mt['u']); nt = perp(ut)
    for e_dir, half, ax_u, ax_len in ((nt, mt['W'] / 2, ut, mt['L']), (-nt, mt['W'] / 2, ut, mt['L']), (ut, mt['L'] / 2, nt, mt['W']), (-ut, mt['L'] / 2, nt, mt['W'])):
        row = []
        for j in tr3.query_ball_point(ct, max(mt['L'], mt['W']) / 2 + 22.0):
            k = HK3[j]
            if objs[k]['key'] not in ('chair', 'armchair') or not objs[k]['ids']: continue
            q = np.array(HUL3[k].centroid.coords[0]) - ct; dist = q @ e_dir - half; along = q @ ax_u
            if -3.0 <= dist <= 14.0 and abs(along) <= ax_len / 2 + 3.0: row.append((along, k))
        if len(row) < 2: continue
        row.sort(); ks = [k for _, k in row]
        st_ = [(i, k) for k in ks for i in objs[k]['ids'] if live(i) and not P[i].get('synthetic')]
        if not st_: continue
        xs = np.array([(np.array(g_of(i).centroid.coords[0]) - ct) @ ax_u for i, _ in st_])
        cen = np.array([a for a, _ in row], float)
        for _ in range(12):
            lab = np.argmin(np.abs(xs[:, None] - cen[None, :]), axis=1)
            new = np.array([xs[lab == j].mean() if (lab == j).any() else cen[j] for j in range(len(cen))])
            if np.allclose(new, cen, atol=1e-3): break
            cen = new
        wid = []
        for j in range(len(ks)):
            ids_j = [st_[a][0] for a in range(len(st_)) if lab[a] == j]
            h_ = seat_hull(ids_j) if ids_j else None
            wid.append(float(np.ptp(np.array(h_.exterior.coords) @ ax_u)) if h_ is not None else 0.0)
        if min(wid) <= 0 or max(wid) > 1.4 * min(wid): continue
        moved_ = 0
        for a, (i, k_old) in enumerate(st_):
            k_new = ks[lab[a]]
            if k_new != k_old:
                objs[k_old]['ids'].remove(i); objs[k_new]['ids'].append(i); owner[i] = k_new; moved_ += 1
        if moved_:
            nf3c += 1
            for k in ks:
                h_ = seat_hull(objs[k]['ids']); m_ = mrr(h_) if h_ is not None else None
                if h_ is not None: HUL3[k] = h_
                if m_ is not None and objs[k]['key'] == 'armchair' and m_['L'] * K < 800 and 'мягкое' in objs[k]['name']:
                    objs[k].update(key='chair', name='Кресло офисное')
            places['seat_rows_shared_anew'].append(dict(at=[round(v, 1) for v in (ct + e_dir * half)], seats=len(ks), strokes_moved=moved_))
print('F3c rows of seats at a table edge that shared their strokes anew', nf3c, T())
# ---- F3b a «seat» that lies on a table top by >= 50 % of its hull and is not a whole seat (< 500 × 400 mm) is the table's
# (owner 06.10.2026: a sliver of a round table at 40.20 was a chair)
_tb3 = [(t, obj_fp(t)) for t, ot in enumerate(objs) if ot['key'] in ('mtable', 'dtable', 'rtable', 'ctable', 'table', 'counter', 'round') and ot['ids']]
_tb3 = [(t, g) for t, g in _tb3 if g is not None and g.area > 1]; nf3b = 0
for k, o in enumerate(objs):
    if o['key'] not in ('chair', 'chairpart') or not o['ids'] or 'draw' in o: continue
    h_ = seat_hull(o['ids']); m_ = mrr(h_) if h_ is not None else None
    if m_ is None or (m_['L'] * K >= 500 and m_['W'] * K >= 400): continue
    on = [(g.intersection(h_).area, t) for t, g in _tb3 if g.intersects(h_)]
    if on and max(on)[0] >= 0.5 * h_.area:
        t = max(on)[1]; objs[t]['ids'] += o['ids']; set_owner(o['ids'], t); o['ids'] = []; o['key'] = 'empty'; nf3b += 1
        places['seat_on_table_to_table'].append(dict(at=[round(v, 1) for v in m_['c']], table=objs[t]['key']))
print('F3b part-seats lying on a table given to it', nf3b, T())
# ================================================================================================ S12 soft furniture
def is_straight(q):
    q = np.asarray(q, float)
    if len(q) < 2: return False
    a, b = q[0], q[-1]; L = np.linalg.norm(b - a)
    if L < 1e-6: return False
    n = perp((b - a) / L)
    return np.abs((q - a) @ n).max() <= 0.05
def hatch_set(o, Lobj):
    st = []
    for i in o['ids']:
        if P[i]['kind'] != 'line' or len(P[i]['p']) < 2: continue
        q = np.asarray(P[i]['p'], float)
        if is_straight(q) and np.linalg.norm(q[-1] - q[0]) <= 0.7 * Lobj: st.append((i, q[0], q[-1]))
    hatch = set()
    for a_ in range(len(st)):
        i, p0, p1 = st[a_]; u = (p1 - p0) / np.linalg.norm(p1 - p0); n = perp(u); near = 0
        for b_ in range(len(st)):
            if b_ == a_: continue
            j, q0, q1 = st[b_]; v = (q1 - q0) / np.linalg.norm(q1 - q0)
            if abs(u @ v) < math.cos(math.radians(4)): continue
            off = abs((q0 - p0) @ n)
            if off > 1.5 or off < 0.02: continue
            s0, s1 = sorted((0, (p1 - p0) @ u)); t0_, t1_ = sorted(((q0 - p0) @ u, (q1 - p0) @ u))
            if min(s1, t1_) - max(s0, t0_) >= 0.3 * min(s1 - s0, t1_ - t0_): near += 1
            if near >= 2: hatch.add(i); break
    return hatch
def main_contour(k):
    """outer outline; parts inside (faces >= 6 % of the footprint) — a part away from the outline (a seat cushion) as its
    own ring, repeated parts with one shape (the medoid of the parts of one size and shape); parts at the outline (arms,
    back) as their inner edge only"""
    o = objs[k]; fp = fp_of(o['ids'])
    if fp is None: return None
    m = mrr(fp); Lobj = m['L']; hatch = hatch_set(o, Lobj)
    keep = [LineString(P[i]['p']) for i in o['ids'] if P[i]['kind'] == 'line' and len(P[i]['p']) >= 2 and i not in hatch and live(i)]
    keep += [g_of(i).exterior for i in o['ids'] if P[i]['kind'] == 'fill' and live(i) and g_of(i).geom_type == 'Polygon' and g_of(i).area >= 0.04 * fp.area]
    try: faces = [f for f in polygonize(unary_union(keep + [fp.exterior])) if f.area >= 0.06 * fp.area and f.area <= 0.9 * fp.area] if keep else []
    except Exception: faces = []
    rings, inner_parts = [], []
    core = fp.buffer(-0.25)
    for f in faces:
        f = f.simplify(0.06, preserve_topology=True)
        if f.is_empty or f.geom_type != 'Polygon': continue
        if core.contains(f.representative_point()) and f.exterior.intersection(core).length >= 0.8 * f.exterior.length: rings.append(f)
        else: inner_parts.append(f)
    # one shape for repeated parts
    if len(rings) >= 2:
        S = [sample(frame_pts(f)[0]) for f in rings]; MMr = [mrr(f) for f in rings]; grp = []
        for a in range(len(rings)):
            for g_ in grp:
                b = g_[0]
                if abs(MMr[a]['L'] - MMr[b]['L']) <= 0.06 * MMr[b]['L'] and abs(MMr[a]['W'] - MMr[b]['W']) <= 0.08 * MMr[b]['W'] and shape_dist(S[a], S[b])[0] <= 0.5:
                    g_.append(a); break
            else: grp.append([a])
        for g_ in grp:
            if len(g_) < 2: continue
            med = min(g_, key=lambda a: sum(shape_dist(S[a], S[b])[0] for b in g_))
            Ym, _ = frame_pts(rings[med])
            for a in g_:
                if a == med: continue
                mr = MMr[a]; ps = POSES[shape_dist(S[a], S[med])[1]]; Y = Ym * ps
                rings[a] = Polygon([tuple(mr['c'] + x * mr['u'] + y * perp(mr['u'])) for x, y in Y]).buffer(0)
    lines = []
    if inner_parts:
        inner = unary_union([f.boundary for f in inner_parts]).difference(fp.exterior.buffer(0.15))
        if not inner.is_empty:
            mg = shapely.line_merge(inner) if inner.geom_type == 'MultiLineString' else inner
            for g in getattr(mg, 'geoms', [mg]):
                if g.geom_type == 'LineString' and g.length >= 0.15 * Lobj: lines.append(g.simplify(0.06))
    return fp, rings, lines, len(hatch)
nsoft = nh = nrg = 0
for k, o in enumerate(objs):
    if o['key'] not in ('armchair', 'round', 'sofa', 'mtable', 'rtable', 'dtable', 'counter') or not o['ids'] or 'draw' in o: continue   # + tables, counters
    r = main_contour(k)
    if r is None: continue
    fp, rings, lines, h = r; ring = list(fp.exterior.coords); sq = P[o['ids'][0]]['seq']
    f_id = new_prim(FURN_LAYER, 'fill', ring[:-1], TOP, alpha=1.0, seq=sq); l_id = new_prim(FURN_LAYER, 'line', ring, (0.0, 0.0, 0.0), seq=sq)
    rr = [new_prim(FURN_LAYER, 'line', list(f.exterior.coords), (0.0, 0.0, 0.0), seq=sq) for f in rings if f.geom_type == 'Polygon']
    ln = [new_prim(FURN_LAYER, 'line', list(g.coords), (0.0, 0.0, 0.0), seq=sq) for g in lines]
    o['ids'] = [f_id, l_id] + rr + ln + o['ids']; o['draw'] = [f_id, l_id] + rr + ln
    for i in [f_id, l_id] + rr + ln: owner[i] = k
    nsoft += 1; nh += h; nrg += len(rr)
print('soft furniture as main contour', nsoft, '| hatch strokes not drawn', nh, '| inner parts as one shape each', nrg, T())
# ---- F4 parts to their item (owner 06.10.2026: «почти все нераспознанные объекты — это части мебели, много частей офисных
# стульев, рабочих мест»): a leftover piece (an edge, a line, a component of a group, a chair part) goes to the item it lies
# on or next to: >= 50 % of its ink within 1 pt (48 mm) of the item's outline, the item with the most of it; the piece is
# not longer than the item (1.3 × its length + 1 pt). Chair backs, arm strokes, worktop corners, lines of a table top.
LEFT4 = ('furn', 'deskedge', 'group', 'table', 'chairpart')
ITEM4 = [k for k, o in enumerate(objs) if o['ids'] and o['key'] not in LEFT4 + ('empty', 'wall', 'glass', 'lpart', 'dim', 'axis', 'mark', 'measure', 'tagc', 'zone', 'corezone', 'shaft', 'coreline', 'roomsep', 'facade', 'wallline', 'door', 'lift', 'conv', 'fire')
         and (('draw' in o) or o['key'] in ('chair', 'armchair'))]
IF4 = {}
for k in ITEM4:
    g_ = seat_hull(objs[k]['ids']) if objs[k]['key'] in ('chair', 'armchair') else obj_fp(k)
    if g_ is not None and g_.area > 0.5: IF4[k] = g_
ITEM4 = list(IF4); it4 = shapely.STRtree([IF4[k] for k in ITEM4]) if ITEM4 else None
f4 = collections.Counter()
def _ext(g):
    m = mrr(g.buffer(0.01)); return m['L'] if m else 0.0
for k, o in enumerate(objs):
    if o['key'] not in LEFT4 or not o['ids'] or 'draw' in o or it4 is None: continue
    for c_ in comps(list(o['ids']), 0.05):
        g = unary_union([g_of(i) for i in c_ if live(i)])
        if g.is_empty: continue
        ink = g.area if g.area > 0 else g.length
        if ink <= 0: continue
        best = None
        for j in it4.query(g.buffer(1.0)):
            t = ITEM4[j]
            if t == o.get('not_of'): continue                    # F2b: off that table's top — not that table's
            fz = IF4[t].buffer(1.0); x = fz.intersection(g); cont = x.area if g.area > 0 else x.length
            if cont >= 0.5 * ink and _ext(g) <= 1.3 * _ext(IF4[t]) + 1.0 and (best is None or cont > best[0]): best = (cont, t)
        if best is None: continue
        t = best[1]; o['ids'] = [i for i in o['ids'] if i not in set(c_)]; objs[t]['ids'] += [i for i in c_ if i not in objs[t]['ids']]; set_owner(c_, t)
        f4[(o['key'], objs[t]['key'])] += 1
        places['parts_to_item'].append(dict(at=[round(v, 1) for v in g.centroid.coords[0]], part=o['key'], item=objs[t]['key'], obj=t))
    if not o['ids']: o['key'] = 'empty'
print('F4 leftover parts given to their item', dict(f4), T())
# ================================================================================================ S13 + S14 chairs
CH = [k for k, o in enumerate(objs) if o['key'] in ('chair', 'chairpart') and o['ids'] and 'draw' not in o]
FP = {k: fp_of(objs[k]['ids']) for k in CH}                # v3: anew — F3 and F4 gave chairs their pieces
FP = {k: v for k, v in FP.items() if v is not None and v.area > 1}
fam = collections.defaultdict(list)
for f in fams:
    for k in f:
        if k in FP and objs[k]['key'] == 'chair': fam[f[0]].append(k)
for k in FP:
    if objs[k]['key'] == 'chair' and not any(k in v for v in fam.values()): fam[('own', k)].append(k)
MED = {}
snap = own = 0; ch_rows = []
for key, mem in fam.items():
    S = {k: sample(frame_pts(FP[k])[0]) for k in mem}
    med = min(mem if len(mem) <= 60 else mem[:60], key=lambda a: np.median([shape_dist(S[a], S[b])[0] for b in mem[:60] if b != a] or [0])) if len(mem) >= 3 else None
    if med is not None: MED[key] = (med, FP[med])
    for k in mem:
        o = objs[k]; poly = FP[k]
        if med is not None and k != med:
            d = shape_dist(S[k], S[med])
            if d[0] <= 0.45:
                Ym, _ = frame_pts(FP[med]); m = mrr(FP[k]); Y = Ym * POSES[d[1]]
                poly = Polygon([tuple(m['c'] + x * m['u'] + y * perp(m['u'])) for x, y in Y]).buffer(0); snap += 1
            else: own += 1; ch_rows.append(dict(at=[round(v, 1) for v in poly.centroid.coords[0]], differs_pt=round(d[0], 2)))
        ring = list(poly.exterior.coords); sq = P[o['ids'][0]]['seq']
        f_id = new_prim(FURN_LAYER, 'fill', ring[:-1], TOP, alpha=1.0, seq=sq); l_id = new_prim(FURN_LAYER, 'line', ring, (0.0, 0.0, 0.0), seq=sq)
        o['ids'] = [f_id, l_id] + o['ids']; o['draw'] = [f_id, l_id]; owner[f_id] = owner[l_id] = k
# chairs pushed under a desk so that only their back shows (chair parts): the chair of the nearest family, under the desk —
# its back on the visible part, its seat towards the desk (the desk is drawn over it)
fulls = [k for k in FP if objs[k]['key'] == 'chair']; fct = cKDTree(np.array([FP[k].centroid.coords[0] for k in fulls])) if fulls else None
nunder = 0
for k in [k for k in FP if objs[k]['key'] == 'chairpart']:
    o = objs[k]; part = FP[k]; mp = mrr(part)
    TABS = {d: DR[d] for d in DESKS}
    TABS.update({t: obj_fp(t) for t, ot in enumerate(objs) if ot['key'] in ('rtable', 'mtable', 'dtable', 'ctable', 'table') and ot['ids']})
    ds = [d for d, g in TABS.items() if g is not None and g.distance(part) <= 1.2]
    if not ds or fct is None or mp is None:
        ring = list(part.exterior.coords); sq = P[o['ids'][0]]['seq']
        f_id = new_prim(FURN_LAYER, 'fill', ring[:-1], TOP, alpha=1.0, seq=sq); l_id = new_prim(FURN_LAYER, 'line', ring, (0.0, 0.0, 0.0), seq=sq)
        o['ids'] = [f_id, l_id] + o['ids']; o['draw'] = [f_id, l_id]; owner[f_id] = owner[l_id] = k; continue
    d = min(ds, key=lambda d: TABS[d].distance(part)); _, near_i = fct.query(np.array(part.centroid.coords[0]), k=min(8, len(fulls)))
    ref = None
    for j in np.atleast_1d(near_i):
        r = fulls[int(j)]; mr = mrr(FP[r])
        if mr and abs(mr['L'] - mp['L']) <= 0.25 * mr['L']: ref = (r, mr); break
    if ref is None: continue
    r, mr = ref; Yr, _ = frame_pts(FP[r])                    # reference chair in its frame: x along its long side
    dc = np.array(TABS[d].centroid.coords[0]); u = mp['u']; n = perp(u)
    if (dc - mp['c']) @ n < 0: n = -n                          # n points to the desk
    back = mp['c'] - n * mp['W'] / 2                           # the outer edge of the visible part
    cen = back + n * mr['W'] / 2
    # the reference outline turned so that its back side (the side away from its own desk, if any) is away from this desk
    best = None
    for ps in POSES:
        Y = Yr * ps; pts = [tuple(cen + x * u + y * n) for x, y in Y]; pl = Polygon(pts).buffer(0)
        sc = pl.symmetric_difference(part).intersection(part.buffer(0.5)).area
        if best is None or sc < best[0]: best = (sc, pl)
    poly = best[1]; ring = list(poly.exterior.coords); sq = P[o['ids'][0]]['seq']
    f_id = new_prim(FURN_LAYER, 'fill', ring[:-1], TOP, alpha=1.0, seq=sq); l_id = new_prim(FURN_LAYER, 'line', ring, (0.0, 0.0, 0.0), seq=sq)
    o.update(key='chair', name='Кресло офисное (задвинуто под стол)'); o['ids'] = [f_id, l_id] + o['ids']; o['draw'] = [f_id, l_id]
    owner[f_id] = owner[l_id] = k; nunder += 1; FP[k] = poly
# ---- S14b owner 06.10.2026: «В рабочих местах по-прежнему встречаются разные стулья… приводить результаты к одной форме,
# одной фигуре»; «Кресла у общего стола получились все равно разными полигонами… взять все шесть кресел одного стола… ложить
# друг на друга, и провести некоторую усредненную линию контура… где линии логически должны быть прямыми… сделать прямыми».
# Chairs come in groups: the chairs at numbered desks (workplace chairs, one group for the floor) and the chairs of each
# table (meeting, dining, round). Each chair is put in the frame of the table edge it stands at: x along the edge (centred
# on the chair), y from the chair's back (the side farthest from the table) towards the table. The full chairs of a group
# (not pushed under the table: depth and area >= 80 % / 70 % of the group's median) are laid on each other (raster 2 mm),
# averaged with their mirror image (a chair is symmetric) and cut at one half: the averaged outline. It is made straight
# where it is straight (Douglas–Peucker 0.08 pt ≈ 4 mm, a straight side — one least-squares line) — the group's figure,
# placed at every chair of the group: centred where the chair is centred along the edge, its back on the chair's back.
from skimage import measure as _ms
from PIL import Image as _Im, ImageDraw as _Dr
def _dp_idx(Q, tol):
    keep = {0, len(Q) - 1}; st = [(0, len(Q) - 1)]
    while st:
        i, j = st.pop()
        if j <= i + 1: continue
        a_, b_ = Q[i], Q[j]; ab = b_ - a_; L = np.linalg.norm(ab); seg = Q[i + 1:j]
        d = np.linalg.norm(seg - a_, axis=1) if L < 1e-9 else np.abs((seg[:, 0] - a_[0]) * ab[1] - (seg[:, 1] - a_[1]) * ab[0]) / L
        m = int(np.argmax(d))
        if d[m] > tol: keep.add(i + 1 + m); st += [(i, i + 1 + m), (i + 1 + m, j)]
    return sorted(keep)
def _fit(S):
    S = np.asarray(S); w = np.linalg.norm(S[1:] - S[:-1], axis=1)
    if w.sum() < 1e-9: return S.mean(0), np.array([1.0, 0.0])
    c = (((S[1:] + S[:-1]) / 2) * w[:, None]).sum(0) / w.sum(); C = np.zeros((2, 2))
    for a_, b_, wi in zip(S[:-1], S[1:], w):
        da, db = a_ - c, b_ - c; C += wi * (np.outer(da, da) + np.outer(db, db) + 0.5 * (np.outer(da, db) + np.outer(db, da))) / 3.0
    ev, evec = np.linalg.eigh(C); u = evec[:, int(np.argmax(ev))]; return c, u / np.linalg.norm(u)
def straight_ring(pts, tol):
    Pq = np.asarray(pts, float); n = len(Pq)
    if n < 4: return [tuple(q) for q in Pq]
    Q = np.vstack([Pq, Pq[:1]]); kp = _dp_idx(Q, tol)
    if len(kp) < 4: return [tuple(q) for q in Pq]
    lines = [_fit(Q[kp[k]:kp[k + 1] + 1]) for k in range(len(kp) - 1)]; out = []
    for k in range(len(lines)):
        (c1, u1), (c2, u2) = lines[k - 1], lines[k]; v0 = Q[kp[k]]
        if math.degrees(math.acos(min(1.0, abs(float(u1 @ u2))))) < 12: out.append(tuple(v0)); continue
        M = np.array([u1, -u2]).T; x = c1 + u1 * np.linalg.solve(M, c2 - c1)[0]
        out.append(tuple(x) if np.linalg.norm(x - v0) <= 3 * tol else tuple(v0))
    return out
def edge_frame(poly_t, is_round, pt):
    pt = np.asarray(pt, float)
    if is_round:
        c = np.array(poly_t.centroid.coords[0]); r = math.sqrt(poly_t.area / math.pi); nrm = (pt - c) / max(np.linalg.norm(pt - c), 1e-9)
        return c + nrm * r, perp(nrm), nrm
    m = mrr(poly_t)
    if m is None: return None
    c, u, L, W = m['c'], np.asarray(m['u'], float), m['L'], m['W']; u = u / np.linalg.norm(u); n = perp(u); best = None
    for (e, nrm, half) in ((u, n, W / 2), (u, -n, W / 2), (n, u, L / 2), (n, -u, L / 2)):
        q = c + nrm * half; side = (pt - q) @ nrm
        if side < -0.5: continue
        if best is None or side < best[0]: best = (side, q, e, nrm)
    return (best[1], best[2], best[3]) if best else None
# ---- S14c owner 06.10.2026: «127 кресел отличаются по форме… Если ты понимаешь, что это однотипные объекты, старайся
# приводить их к одной форме»; «есть еще группа одинаковых стульев… привести к общей фигуре» (rows without a table);
# «знаковый стул: выработать среднюю фигуру и её там использовать». Seats of one shape are one type and get one figure
# wherever they stand — at desks, at tables, in rows, alone:
# 1) a seat's outer outline: solid_fp of its own source strokes (the back and arms given to it in F4 included); a chair
#    restored under a desk (S13) takes part with the outline it was given — placed, not averaged;
# 2) its frame: the direction of its own straight strokes (mod 90°; else its minimum rotated rectangle) and the centre of
#    its box in these axes; raster 0.15 pt (7 mm);
# 3) shape groups: sides within 10 %, area within 15 %, and in the best of 8 poses (4 turns × mirror) it overlaps the
#    group's first seat by IoU >= 0.86 (the group it fits best); a seat left alone that is like a group (15 %, 25 %,
#    IoU >= 0.72) takes the group's figure; groups of one model drawn a little differently are one family (every pair:
#    hull IoU >= 0.89, length within 6 %, width within 10 %); a seat that stands at a table or a desk (<= 3 pt) is turned so that its front faces
#    it when two poses are equally good (IoU within 0.03) — the group's front is where most of its seats face their tables;
# 4) a group of >= 2: its whole seats (area >= 75 % of the group's median) laid on each other in the poses found, averaged
#    (raster 0.04 pt ≈ 2 mm), made symmetric left–right (about the axis towards the tables the group faces, else the axis
#    that fits better; when the mirror overlaps >= 0.85), cut at one
#    half, cleaned of notches and stubs below 0.8 pt (closing, opening 0.4 pt), the fewest points (Douglas–Peucker 0.08 pt) and
#    straight sides (straight_ring 0.1 pt): the group's figure, placed at every seat of the group in its pose;
# 5) a single seat keeps its own outline, cleaned and straightened the same way.
TABK = ('mtable', 'dtable', 'table', 'ctable', 'rtable', 'round', 'counter')
_tabg = [DR[d] for d in DESKS] + [g for t, ot in enumerate(objs) if ot['key'] in TABK and ot['ids'] for g in [obj_fp(t)] if g is not None]
_tabt = shapely.STRtree(_tabg) if _tabg else None
RS = 0.15; HG = 13.0
POSE8 = [(r, f) for f in (False, True) for r in range(4)]
_R90 = np.array([[0.0, -1.0], [1.0, 0.0]])
def _tp(Y, r, f):                       # local -> canonical: mirror x, then r quarter turns
    Z = np.asarray(Y, float) * (np.array([-1.0, 1.0]) if f else 1.0)
    for _ in range(r): Z = Z @ _R90.T
    return Z
def _tpi(Z, r, f):                      # canonical -> local
    Y = np.asarray(Z, float)
    for _ in range(r): Y = Y @ _R90
    return Y * (np.array([-1.0, 1.0]) if f else 1.0)
def _ras(Y, res=RS, hg=HG):
    N = int(round(2 * hg / res)); im = _Im.new('L', (N, N), 0)
    _Dr.Draw(im).polygon([((x + hg) / res, (y + hg) / res) for x, y in Y], fill=1); return np.array(im, bool)
def _iou(A, B):
    u_ = np.logical_or(A, B).sum(); return float(np.logical_and(A, B).sum()) / u_ if u_ else 0.0
def _clean(poly):
    q = poly.buffer(0.4, join_style=2).buffer(-0.4, join_style=2).buffer(-0.4, join_style=2).buffer(0.4, join_style=2)
    if q.is_empty: q = poly
    if q.geom_type != 'Polygon': q = max(getattr(q, 'geoms', [q]), key=lambda x: x.area)
    fig = straight_ring(list(q.simplify(0.08).exterior.coords)[:-1], 0.1); fp_ = Polygon(fig).buffer(0)
    if fp_.is_empty or fp_.geom_type != 'Polygon' or abs(fp_.area - q.area) > 0.12 * q.area: fp_ = q.simplify(0.06)
    return fp_
def dom_axis(ids):
    """the direction of a seat's own strokes (the angle mod 90° that most of their length has, 1° bins, ±3° mean): seats
    are drawn with straight edges along their axes; None when no direction holds >= 25 % of the length"""
    ang, wt = [], []
    for i in ids:
        if not live(i) or P[i].get('synthetic'): continue
        q = np.asarray(P[i]['p'], float)
        if P[i]['kind'] == 'fill': q = np.vstack([q, q[:1]])
        if len(q) < 2: continue
        d = q[1:] - q[:-1]; L_ = np.hypot(d[:, 0], d[:, 1]); ok = L_ >= 0.3
        ang += list(np.degrees(np.arctan2(d[ok, 1], d[ok, 0])) % 90.0); wt += list(L_[ok])
    if not wt: return None
    ang = np.array(ang); wt = np.array(wt); h = np.zeros(90)
    np.add.at(h, np.floor(ang).astype(int) % 90, wt)
    hs = sum(np.roll(h, s_) for s_ in (-1, 0, 1)); pk = int(np.argmax(hs))
    dd = (ang - pk + 45) % 90 - 45; sel = np.abs(dd) <= 3
    if wt[sel].sum() < 0.25 * wt.sum(): return None
    th = math.radians(pk + float((dd[sel] * wt[sel]).sum() / wt[sel].sum()))
    return np.array([math.cos(th), math.sin(th)])
SH = {}
for k, o in enumerate(objs):
    if o['key'] not in ('chair', 'armchair') or not o['ids']: continue
    restored = 'задвинуто' in o.get('name', '') and k in FP
    hull = Polygon(FP[k].exterior).convex_hull if restored else seat_hull(o['ids'])
    det = FP[k] if restored else solid_fp([i for i in o['ids'] if not P[i].get('synthetic')])
    if hull is None or det is None or det.is_empty or det.geom_type != 'Polygon' or hull.area < 2: continue
    det = Polygon(det.exterior).simplify(0.03)
    m = mrr(hull)
    if m is None or m['L'] * K > 1250: continue
    u = dom_axis(o['ids']) if not restored else None
    if u is None: u = m['u']
    n = perp(u); Hc = np.array(hull.exterior.coords)[:-1]; a_, b_ = Hc @ u, Hc @ n
    c = u * (a_.min() + a_.max()) / 2 + n * (b_.min() + b_.max()) / 2                  # the centre of its box in its axes
    m = dict(m, L=max(a_.max() - a_.min(), b_.max() - b_.min()), W=min(a_.max() - a_.min(), b_.max() - b_.min()))
    X = np.array(det.exterior.coords)[:-1] - c; Y = np.c_[X @ u, X @ n]                 # the drawing: for the pose
    Xh = np.array(hull.exterior.coords)[:-1] - c; Yh = np.c_[Xh @ u, Xh @ n]            # the габарит: for the figure
    poly = hull
    front = None
    if _tabt is not None:
        near = [j for j in _tabt.query(poly.buffer(3.0)) if _tabg[j].distance(poly) <= 3.0]
        if near:
            j = min(near, key=lambda j: _tabg[j].distance(poly)); pa, pb = shapely.ops.nearest_points(poly.centroid, _tabg[j])
            v = np.array(pb.coords[0]) - np.array(poly.centroid.coords[0])
            if np.linalg.norm(v) < 1e-6: v = np.array(_tabg[j].centroid.coords[0]) - np.array(poly.centroid.coords[0])
            if np.linalg.norm(v) > 1e-6: v = v / np.linalg.norm(v); front = np.array([v @ u, v @ n])
    SH[k] = dict(poly=poly, c=c, u=u, n=n, L=m['L'], W=m['W'], A=poly.area, Y=Y, Yh=Yh, avg=not restored, front=front,
                 R=[_ras(_tp(Y, r, f)) for r, f in POSE8])
clusters = []
def _cands(s, dl, da):
    for cl in clusters:
        r0 = SH[cl['rep']]
        if abs(s['L'] - r0['L']) > dl * r0['L'] or abs(s['W'] - r0['W']) > dl * r0['W'] or abs(s['A'] - r0['A']) > da * r0['A']: continue
        yield cl, [_iou(s['R'][p], r0['R'][0]) for p in range(8)]
for k in sorted(SH, key=lambda k: -SH[k]['A']):
    s = SH[k]; best = None
    for cl, ious in _cands(s, 0.1, 0.15):                     # the group it fits best, not the first that fits
        if max(ious) >= 0.86 and (best is None or max(ious) > max(best[1])): best = (cl, ious)
    if best: best[0]['mem'].append((k, best[1]))
    else: clusters.append(dict(rep=k, mem=[(k, [1.0] + [0.0] * 7)]))
# a seat left alone that is like a group (sides within 15 %, area within 25 %, overlap >= 0.72) is of that group: it takes
# the group's figure (owner: «если ты понимаешь, что это однотипные объекты, старайся приводить их к одной форме»), it is
# not averaged into it
nadopt = 0
for cl in [c_ for c_ in clusters if len(c_['mem']) == 1]:
    k = cl['rep']; s = SH[k]; best = None
    for cl2, ious in _cands(s, 0.15, 0.25):
        if cl2 is cl or len(cl2['mem']) < 2: continue
        if max(ious) >= 0.72 and (best is None or max(ious) > max(best[1])): best = (cl2, ious)
    if best: best[0]['mem'].append((k, best[1])); best[0].setdefault('adopted', set()).add(k); cl['mem'] = []; nadopt += 1
clusters = [c_ for c_ in clusters if c_['mem']]
# families: one model drawn a little differently (a back strip given or not) — groups whose first seats are alike in the
# габарит (every pair between two families: IoU of the hulls >= 0.89 in the best pose, length within 6 %, width within
# 10 %; complete linkage, so that like-to-like chains do not join unlike seats) are one group
_RH = {}
def _rh(k):
    if k not in _RH: _RH[k] = [_ras(_tp(SH[k]['Yh'], r, f)) for r, f in POSE8]
    return _RH[k]
def _like(a, b):
    ra, rb = SH[a], SH[b]
    if abs(ra['L'] - rb['L']) > 0.06 * max(ra['L'], rb['L']) or abs(ra['W'] - rb['W']) > 0.10 * max(ra['W'], rb['W']): return 0.0
    A0 = _rh(a)[0]; return max(_iou(A0, R_) for R_ in _rh(b))
GRP = [c_ for c_ in clusters if len(c_['mem']) >= 2]; famof = {id(c_): [c_] for c_ in GRP}
pairs = sorted(((_like(GRP[i]['rep'], GRP[j]['rep']), i, j) for i in range(len(GRP)) for j in range(i + 1, len(GRP))), key=lambda t: -t[0])
nfam = 0
for v, i, j in pairs:
    if v < 0.89: break
    Fi, Fj = famof[id(GRP[i])], famof[id(GRP[j])]
    if Fi is Fj or not all(_like(a['rep'], b['rep']) >= 0.89 for a in Fi for b in Fj): continue
    Fi += Fj
    for c_ in Fj: famof[id(c_)] = Fi
    nfam += 1
seen_ = set(); merged_ = []
for c_ in GRP:
    F_ = famof[id(c_)]
    if id(F_) in seen_ or len(F_) < 2: continue
    seen_.add(id(F_)); head = max(F_, key=lambda x: len(x['mem'])); r0 = SH[head['rep']]
    for x in F_:
        if x is head: continue
        for k, _ in x['mem']: head['mem'].append((k, [_iou(SH[k]['R'][p_], r0['R'][0]) for p_ in range(8)]))
        head.setdefault('adopted', set()).update(x.get('adopted', ())); x['mem'] = []
    merged_.append(len(head['mem']))
clusters = [c_ for c_ in clusters if c_['mem']]
print('S14c families of one model (groups joined):', nfam, '| family sizes', merged_, T())
# ---- S14d test 9 (owner 06.10.2026: «Если ты понимаешь, что это однотипные объекты, старайся приводить их к одной форме»;
# the chair of 40.26 that the table top cut; three chairs of a row whose strokes were shared wrongly; seats alike in their
# габарит but drawn differently inside). Two rules, after the groups and families:
# (a) a seat left alone whose габарит is like a seat of a group (the family test: hull IoU >= 0.89 in the best of 8 poses,
#     length within 6 %, width within 10 %) takes that group's figure;
# (b) seats of one table are one model: at a table or desk where one group holds >= 2 seats, the seats left alone stand in
#     slots of their side. A run of such seats (consecutive along the side) is measured at its back — the third of the
#     group's seat depth farthest from the table, where the top does not cut them and the arms of neighbours do not reach;
#     it holds n seats (n = round(width ÷ the group's seat width), or by the pitch of the group's seats at this table when
#     they stand with gaps; the width fits within 30 % of a seat); the group's figure is placed in each slot, back to the
#     run's back line, front to the table; the run's strokes go to the slot nearest to them.
def _gfront(k):
    s = SH[k]
    if s.get('front') is None: return None
    v = s['front'][0] * s['u'] + s['front'][1] * s['n']; nv = float(np.linalg.norm(v))
    return v / nv if nv > 1e-9 else None
_clid = {id(c_): c_ for c_ in clusters}; _clof = {k_: id(c_) for c_ in clusters for k_, _ in c_['mem']}
GRP2 = [c_ for c_ in clusters if len(c_['mem']) >= 2]; nadopt_h = 0
for c_ in [c_ for c_ in clusters if len(c_['mem']) == 1]:
    k = c_['rep']; best = None
    for g_ in GRP2:
        if objs[g_['rep']]['key'] != objs[k]['key']: continue
        cand = sorted((m_ for m_, _ in g_['mem']), key=lambda m_: abs(SH[m_]['L'] - SH[k]['L']) + abs(SH[m_]['W'] - SH[k]['W']))[:25]
        v = max((_like(k, m_) for m_ in cand), default=0.0)
        if v >= 0.89 and (best is None or v > best[0]): best = (v, g_)
    if best:
        g_ = best[1]; r0 = g_['rep']
        g_['mem'].append((k, [_iou(_rh(k)[p_], _rh(r0)[0]) for p_ in range(8)])); g_.setdefault('adopted', set()).add(k)
        c_['mem'] = []; nadopt_h += 1; _clof[k] = id(g_)
clusters = [c_ for c_ in clusters if c_['mem']]
clusters = [c_ for c_ in clusters if c_['mem']]; _clid = {id(c_): c_ for c_ in clusters}
_clof = {k_: id(c_) for c_ in clusters for k_, _ in c_['mem']}
attab = collections.defaultdict(list)
for k in SH:
    if k not in _clof or _clof[k] not in _clid or _gfront(k) is None or _tabt is None: continue
    pl_ = SH[k]['poly']; near = [j for j in _tabt.query(pl_.buffer(3.0)) if _tabg[j].distance(pl_) <= 3.0]
    if near: attab[min(near, key=lambda j: _tabg[j].distance(pl_))].append(k)
nslot = collections.Counter(); _dbg = bool(os.environ.get('S14D_DEBUG'))
def _lat(k, Gg): return float(np.asarray(SH[k]['poly'].centroid.coords[0]) @ Gg)
for j, ks in attab.items():
    cnt = collections.Counter(_clof[k] for k in ks if len(_clid[_clof[k]]['mem']) >= 2)
    if not cnt: continue
    gid, gn = cnt.most_common(1)[0]
    singles = [k for k in ks if len(_clid[_clof[k]]['mem']) == 1]
    if gn < 2 or not singles: continue
    mt_ = mrr(_tabg[j])
    if mt_ is None: continue
    ct_, ut_ = np.asarray(mt_['c']), np.asarray(mt_['u']); nt_ = perp(ut_)
    def _side(k):                     # the normal of the table side the seat stands at, pointing from the seat to the table
        q = np.asarray(SH[k]['poly'].centroid.coords[0]) - ct_; a_ = (q @ ut_) / (mt_['L'] / 2); b_ = (q @ nt_) / (mt_['W'] / 2)
        return -(np.sign(a_) * ut_ if abs(a_) >= abs(b_) else np.sign(b_) * nt_)
    G_ = _clid[gid]; refs = [k for k in ks if _clof[k] == gid]
    fw = []
    for k in refs:
        Fg = _side(k); H_ = np.asarray(SH[k]['poly'].exterior.coords)[:-1]; fw.append((float(np.ptp(H_ @ Fg)), float(np.ptp(H_ @ perp(Fg))), SH[k]['poly'].area))
    dep = float(np.median([a for a, _, _ in fw])); wid = float(np.median([b for _, b, _ in fw])); area_ = float(np.median([c for _, _, c in fw]))
    sides = collections.defaultdict(list)
    for k in ks: sides[tuple(np.round(_side(k), 6))].append(k)
    pitches = []
    for Fk, kk_ in sides.items():
        rc = sorted(_lat(k, perp(np.array(Fk))) for k in kk_ if _clof[k] == gid)
        pitches += [b - a for a, b in zip(rc, rc[1:]) if b - a <= 2.5 * wid]
    pitch = max(float(np.median(pitches)), wid) if pitches else wid
    for Fk, kk_ in sides.items():
        Fg = np.array(Fk) / np.linalg.norm(Fk); Gg = perp(Fg)
        runs, cur = [], []
        for k in sorted(kk_, key=lambda k: _lat(k, Gg)):
            if len(_clid[_clof[k]]['mem']) == 1: cur.append(k)
            elif cur: runs.append(cur); cur = []
        if cur: runs.append(cur)
        for run in runs:
            strokes = [(i, k) for k in run for i in objs[k]['ids'] if live(i) and not P[i].get('synthetic') and len(P[i]['p']) >= 1]
            if not strokes: continue
            pts = np.vstack([np.asarray(P[i]['p'], float) for i, _ in strokes]); f_ = pts @ Fg; g_ = pts @ Gg
            back = float(np.percentile(f_, 1)); sel = f_ <= back + dep / 3.0
            ga, gb = (float(np.percentile(g_[sel], 1)), float(np.percentile(g_[sel], 99))) if sel.sum() >= 4 else (0.0, 0.0); W_ = gb - ga
            n_ = max(1, int(round((W_ - wid) / pitch)) + 1)
            n_whole = sum(1 for k in run if SH[k]['poly'].area >= 0.6 * area_)
            why_ = None
            if sel.sum() < 4 or float(np.percentile(f_, 99)) - back > 1.5 * dep: why_ = 'run too deep or empty'
            elif abs(W_ - (wid + (n_ - 1) * pitch)) > 0.3 * wid: why_ = 'run width does not fit the group'
            elif n_ > len(run) + 1 or n_ < n_whole: why_ = 'slots and whole seats disagree'
            if _dbg: print('S14D run', run, 'table', j, 'Fg', np.round(Fg, 3), 'back', round(back, 1), 'W mm', round(W_ * K), 'wid mm', round(wid * K), 'pitch mm', round(pitch * K), 'n', n_, 'whole', n_whole, 'depth mm', round((float(np.percentile(f_, 99)) - back) * K), 'dep mm', round(dep * K), '->', why_ or 'ok')
            if why_: nslot[why_] += 1; continue
            cen_ = [(ga + gb) / 2] if n_ == 1 else list(np.linspace(ga + wid / 2, gb - wid / 2, n_))
            # the slot objects: the seat of the run nearest to each slot; a slot without one — a new seat
            free = list(run); sk = []
            for cc in cen_:
                if free:
                    k_ = min(free, key=lambda k: abs(_lat(k, Gg) - cc)); free.remove(k_); sk.append(k_)
                else: sk.append(None)
            lab = [int(np.argmin([abs(float(np.asarray(g_of(i).centroid.coords[0]) @ Gg) - cc) for cc in cen_])) for i, _ in strokes]
            if any(sum(1 for l_ in lab if l_ == s_) == 0 for s_ in range(n_)): nslot['a slot without strokes'] += 1; continue
            for s_ in range(n_):
                if sk[s_] is None:
                    sk[s_] = new_obj(objs[G_['rep']]['key'], 'Кресло офисное', [], layer=objs[G_['rep']].get('layer', 'A-82'))
            for (i, k_old), l_ in zip(strokes, lab):
                k_new = sk[l_]
                if k_new != k_old: objs[k_old]['ids'].remove(i); objs[k_new]['ids'].append(i); owner[i] = k_new
            for k in free:                                    # a seat of the run left without a slot: its strokes went
                objs[k]['ids'] = [i for i in objs[k]['ids'] if not P[i].get('synthetic')]
                if not objs[k]['ids']: objs[k]['key'] = 'empty'; objs[k].pop('draw', None)
                _clid[_clof[k]]['mem'] = []
            for s_, k in enumerate(sk):
                if k in _clof and _clof[k] in _clid and _clid[_clof[k]] is not G_: _clid[_clof[k]]['mem'] = []
                objs[k]['key'] = objs[G_['rep']]['key']
                G_.setdefault('slots', []).append(dict(k=k, F=Fg, back=back, lat=float(cen_[s_])))
            nslot['seats in slots'] += n_; nslot['runs'] += 1
            places['seats_in_table_slots'].append(dict(at=[round(v, 1) for v in (Fg * back + Gg * (ga + gb) / 2)], seats=n_, objects_before=len(run),
                                                       width_mm=round(W_ * K), seat_width_mm=round(wid * K), pitch_mm=round(pitch * K)))
clusters = [c_ for c_ in clusters if c_['mem']]
# (a') seats left alone that are alike in their габарит among themselves (the same family test, complete linkage) are a group
_sg = [c_['rep'] for c_ in clusters if len(c_['mem']) == 1]; _sgrp = {k: [k] for k in _sg}; nalike = 0
for v, a, b in sorted(((_like(a, b), a, b) for x_, a in enumerate(_sg) for b in _sg[x_ + 1:] if objs[a]['key'] == objs[b]['key']), key=lambda t: -t[0]):
    if v < 0.89: break
    A_, B_ = _sgrp[a], _sgrp[b]
    if A_ is B_ or not all(_like(x, y) >= 0.89 for x in A_ for y in B_): continue
    A_ += B_
    for y in B_: _sgrp[y] = A_
seen_ = set()
for k in _sg:
    A_ = _sgrp[k]
    if len(A_) < 2 or id(A_) in seen_: continue
    seen_.add(id(A_)); r0 = max(A_, key=lambda x: SH[x]['A'])
    for c_ in clusters:
        if len(c_['mem']) == 1 and c_['rep'] in A_ and c_['rep'] != r0: c_['mem'] = []
    for c_ in clusters:
        if c_['rep'] == r0 and len(c_['mem']) == 1:
            c_['mem'] = [(x, [_iou(_rh(x)[p_], _rh(r0)[0]) for p_ in range(8)]) for x in A_]; nalike += len(A_)
clusters = [c_ for c_ in clusters if c_['mem']]
print('S14d seats alike in their габарит taken into a group', nadopt_h, '| seats alone alike among themselves, now groups', nalike,
      '| seats of one table in slots of its group', dict(nslot), T())
nfig = collections.Counter(); figs = []; FIGS = {}
def _place(k, figY, pose, keep_inner):
    s = SH[k]; o = objs[k]; Yl = _tpi(figY, *POSE8[pose])
    pts = [tuple(s['c'] + x * s['u'] + y * s['n']) for x, y in Yl]; poly = Polygon(pts).buffer(0)
    if poly.is_empty or poly.geom_type != 'Polygon': return False
    ring = list(poly.exterior.coords); sq = P[o['ids'][0]]['seq']
    f_id = new_prim(FURN_LAYER, 'fill', ring[:-1], TOP, alpha=1.0, seq=sq); l_id = new_prim(FURN_LAYER, 'line', ring, (0.0, 0.0, 0.0), seq=sq)
    inner = [i for i in o.get('draw', [])[2:]] if keep_inner else []
    o['ids'] = [f_id, l_id] + [i for i in o['ids'] if i not in o.get('draw', [])] + inner; o['draw'] = [f_id, l_id] + inner
    owner[f_id] = owner[l_id] = k; FP[k] = poly; return True
for cl in clusters:
    mem = cl['mem']; rep_k = cl['rep']
    if len(mem) == 1:                                         # a seat of its own shape: its outline, clean and straight
        s = SH[rep_k]; q = _clean(Polygon(s['Yh']).buffer(0))
        if _place(rep_k, np.array(q.exterior.coords)[:-1], 0, objs[rep_k]['key'] == 'armchair'): nfig['own outline'] += 1
        continue
    pose = {k: int(np.argmax(ious)) for k, ious in mem}; cl['pose'] = pose
    fr = [_tp(SH[k]['front'][None, :], *POSE8[pose[k]])[0] for k, _ in mem if SH[k]['front'] is not None]
    F = np.mean(fr, axis=0) if fr else None
    if F is not None and np.linalg.norm(F) >= 0.5:
        F = F / np.linalg.norm(F)
        for k, ious in mem:
            if SH[k]['front'] is None: continue
            best = max(ious)
            ok_ = [p for p in range(8) if ious[p] >= best - 0.03]
            pose[k] = max(ok_, key=lambda p: (_tp(SH[k]['front'][None, :], *POSE8[p])[0] @ F, ious[p]))
    whole = [k for k, _ in mem if SH[k]['avg'] and k not in cl.get('adopted', ())]
    if whole:
        mA = np.median([SH[k]['A'] for k in whole]); whole = [k for k in whole if SH[k]['A'] >= 0.75 * mA] or whole
    else: whole = [k for k, _ in mem]
    hgf = max(max(SH[k]['L'] for k in whole) / 2 + 1.0, 3.0); rf = 0.04; acc = None
    for k in whole:
        A_ = _ras(_tp(SH[k]['Yh'], *POSE8[pose[k]]), rf, hgf).astype(float); acc = A_ if acc is None else acc + A_
    acc /= len(whole); B = acc >= 0.5
    sx, sy = _iou(B, B[:, ::-1]), _iou(B, B[::-1, :])
    # a seat is symmetric left–right: about its front axis when the group faces tables (F), else about the axis that fits
    if F is not None and np.linalg.norm(F) > 0.5: use_x = abs(F[1]) >= abs(F[0])
    else: use_x = sx >= sy
    if (sx if use_x else sy) >= 0.85: acc = (acc + (acc[:, ::-1] if use_x else acc[::-1, :])) / 2
    cs = _ms.find_contours(np.pad(acc, 1), 0.5)
    if not cs: continue
    cmax = max(cs, key=len); fp_ = Polygon([((c_ - 1) * rf - hgf, (r_ - 1) * rf - hgf) for r_, c_ in cmax]).buffer(0)
    if fp_.is_empty: continue
    if fp_.geom_type != 'Polygon': fp_ = max(fp_.geoms, key=lambda x: x.area)
    q = _clean(fp_.convex_hull); figY = np.array(q.exterior.coords)[:-1]
    FIGS[rep_k] = (figY, F, [k for k, _ in mem])
    xs, ys = figY[:, 0], figY[:, 1]
    n_ok = sum(1 for k, _ in mem if _place(k, figY, pose[k], objs[k]['key'] == 'armchair'))
    nfig['in groups'] += n_ok
    # S14d (b): the seats of the group's tables in slots — the figure back to the run's back line, front to the table
    slots_ = cl.get('slots', [])
    for sl in slots_:
        k = sl['k']; Fg = sl['F']; Gg = perp(Fg)
        if F is not None and np.linalg.norm(F) > 0.5:
            p_best = max(range(8), key=lambda p_: float(_tp(np.array([[1.0, 0.0]]), *POSE8[p_])[0] @ F))
        else: p_best = 0
        Yl = _tpi(figY, *POSE8[p_best]); back_l = float(Yl[:, 0].min()); lat_l = float((Yl[:, 1].min() + Yl[:, 1].max()) / 2)
        SH.setdefault(k, {}).update(c=Fg * (sl['back'] - back_l) + Gg * (sl['lat'] - lat_l), u=Fg, n=Gg)
        if _place(k, figY, p_best, False): nfig['in table slots'] += 1
    figs.append(dict(seats=len(mem) + len(slots_), averaged=len(whole), points=len(figY), size_mm=[round((xs.max() - xs.min()) * K), round((ys.max() - ys.min()) * K)],
                     symmetric=('x' if use_x else 'y') if (sx if use_x else sy) >= 0.85 else 'нет',
                     key=objs[rep_k]['key'], at=[[round(v, 1) for v in SH[k]['c']] for k, _ in mem[:6]]))
    for k in [k for k, _ in mem] + [sl['k'] for sl in slots_]:
        objs[k]['name'] = ('Кресло мягкое' if objs[k]['key'] == 'armchair' else 'Кресло офисное') + f' (фигура группы из {len(mem) + len(slots_)})'
if os.environ.get('S14C_DUMP'):
    pickle.dump(dict(SH={k: {kk: vv for kk, vv in v.items() if kk != 'R'} for k, v in SH.items()}, clusters=clusters, figs=figs), open('s14c_dump.pkl', 'wb'))
places['seat_figures'] = sorted(figs, key=lambda f: -f['seats'])
print('S14c seats of one shape -> one figure:', dict(nfig), '| single seats taken into a like group', nadopt, '| groups of >= 2:', len(figs), '| seats in them', sum(f['seats'] for f in figs),
      '| largest groups', [(f['seats'], f['size_mm'], f['points']) for f in places['seat_figures'][:6]], T())
print('chairs as one outline', sum(1 for k in FP if objs[k]['key'] == 'chair'), '| took the shape of their family', snap,
      '| differ from it (kept, listed)', own, '| chairs under desks restored', nunder, T())
places['chairs_differing'] = ch_rows[:200]
# ---- S14e test 10 (owner 07.10.2026: «на карте много рабочих мест. Они все с номерами. У них у всех есть стул, и там
# небольшое количество стульев у тебя немножко других габаритных размеров, либо немножко смещены, повернуты относительно
# стола (то есть не перпендикулярно приставлены к столу), либо наезжают на него… поищи, попробуй исправить»; «если ты эти
# объекты классифицировал одинаково, то с большой вероятностью у них одна и та же форма, габариты и должна быть одна и та
# же фигура»). The seat of a numbered workplace — the seat at the desk's long side (its centre within a quarter of the
# desk's length from the desk's middle, beyond the long side, ≤ 300 mm from the desk; the nearest one) — is one kind of
# object: one figure for all of them (that of the group most of them belong to), square to the desk, its front at the
# typical depth under the desk (the median of that group's workplace seats), centred on the desk when it is off by ≤ 15 %
# of the desk's length. A seat of another width along the desk (its own source strokes, more than 6 % off) is another
# kind and is left. A «seat» that is a plain rectangle at a desk's short end (a quarter or more of the desk's length off its
# middle) is a side pedestal, not a seat.
SEATK = ('chair',)
_seats = [k for k in FP if objs[k]['key'] in SEATK and objs[k]['ids']]
_sst = shapely.STRtree([FP[k] for k in _seats]) if _seats else None
wp = {}; nped = 0; ped_at = []
def _src_ext(k, u):
    pts = [q for i in objs[k]['ids'] if not P[i].get('synthetic') and live(i) for q in P[i]['p']]
    if not pts: return None
    a = np.asarray(pts, float) @ u; return float(a.max() - a.min())
for d in sorted(NUMBERED):
    if d not in DRM or d not in DR or _sst is None: continue
    c_, u_, L_, W_ = DRM[d]; c_ = np.asarray(c_, float); u_ = np.asarray(u_, float) / np.linalg.norm(u_); n_ = perp(u_)
    for j in _sst.query(DR[d].buffer(300 / K)):
        k = _seats[j]; g = FP[k]
        if g.distance(DR[d]) > 300 / K: continue
        v = np.asarray(g.centroid.coords[0]) - c_; lat, dep = float(v @ u_), float(v @ n_)
        mrr_ = g.minimum_rotated_rectangle
        if abs(lat) >= 0.25 * L_ and mrr_.geom_type == 'Polygon' and g.area >= 0.95 * mrr_.area and len(g.exterior.coords) <= 6:
            o = objs[k]; cc_ = np.array(mrr_.exterior.coords)[:4]; e1_, e2_ = np.linalg.norm(cc_[1] - cc_[0]), np.linalg.norm(cc_[2] - cc_[1])
            o['key'] = 'pedestal'; o['layer'] = 'A-82'; o['name'] = f'Тумба приставная {mm(max(e1_, e2_))}×{mm(min(e1_, e2_))} (у торца стола)'
            nped += 1; ped_at.append([round(float(x), 1) for x in g.centroid.coords[0]]); continue
        if abs(lat) > 0.25 * L_ or abs(dep) < W_ / 2: continue
        prev = wp.get(k)
        dd = g.distance(DR[d])
        if prev is None or dd < prev[1]: wp[k] = (d, dd, lat)
_seats_wp = [k for k in wp if objs[k]['key'] in SEATK]
cnt_rep = collections.Counter(rep for rep, (_, _, mem) in FIGS.items() for k in mem if k in wp)
nwp = collections.Counter(); wp_rows = []
if cnt_rep and _seats_wp:
    rep0 = cnt_rep.most_common(1)[0][0]; figM, FM, memM = FIGS[rep0]; memM = set(memM)
    if FM is None or np.linalg.norm(FM) < 0.5: FM = np.array([1.0, 0.0])
    p_best = max(range(8), key=lambda p_: float(_tp(np.array([[1.0, 0.0]]), *POSE8[p_])[0] @ FM))
    Yl = _tpi(figM, *POSE8[p_best]); front_l = float(Yl[:, 0].max()); lat_l = float((Yl[:, 1].min() + Yl[:, 1].max()) / 2)
    wM = float(Yl[:, 1].max() - Yl[:, 1].min())
    def _pen(k, d, Fg):                       # how deep the seat's front runs under the desk (negative: a gap)
        return float(max(np.asarray(FP[k].exterior.coords) @ Fg) - min(np.asarray(DR[d].exterior.coords) @ Fg))
    def _fg(k, d):
        c_ = np.asarray(DRM[d][0], float); u_ = np.asarray(DRM[d][1], float) / np.linalg.norm(DRM[d][1]); n_ = perp(u_)
        Fg = n_ if float((c_ - np.asarray(FP[k].centroid.coords[0])) @ n_) > 0 else -n_
        return Fg, u_, c_
    pens = [_pen(k, wp[k][0], _fg(k, wp[k][0])[0]) for k in _seats_wp if k in memM]
    penM = float(np.median(pens)) if pens else 0.0
    for k in _seats_wp:
        d, dd, lat = wp[k]; Fg, u_, c_ = _fg(k, d); Gg = perp(Fg); L_ = DRM[d][2]
        ws = _src_ext(k, u_)
        if ws is None or abs(ws - wM) > 0.06 * wM: nwp['другой ширины — оставлено'] += 1; continue
        pen = _pen(k, d, Fg)
        # the seat's own axes: its figure's minimum rotated rectangle against the desk's
        mr_ = FP[k].minimum_rotated_rectangle; cc_ = np.array(mr_.exterior.coords)[:4]
        ax_ = cc_[1] - cc_[0]; ang = math.degrees(math.atan2(ax_[1], ax_[0]) - math.atan2(u_[1], u_[0])) % 90; ang = min(ang, 90 - ang)
        why = []
        if k not in memM: why.append('другая фигура')
        if abs(pen - penM) > 30 / K: why.append('глубина под столом')
        if abs(lat) > 30 / K and abs(lat) <= 0.15 * L_: why.append('смещено вдоль стола')
        if ang > 1.0: why.append('повёрнуто')
        if not why: nwp['как у всех — без изменений'] += 1; continue
        lat_t = float(c_ @ Gg) if abs(lat) <= 0.15 * L_ else float(np.asarray(FP[k].centroid.coords[0]) @ Gg)
        front_t = float(min(np.asarray(DR[d].exterior.coords) @ Fg)) + penM
        SH.setdefault(k, {}).update(c=Fg * (front_t - front_l) + Gg * (lat_t - lat_l), u=Fg, n=Gg)
        if _place(k, figM, p_best, False):
            objs[k]['name'] = f'Кресло офисное (фигура рабочего места, {len(memM)} в группе)'
            for w_ in why: nwp[w_] += 1
            nwp['исправлено'] += 1
            wp_rows.append(dict(at=[round(float(x), 1) for x in FP[k].centroid.coords[0]], why=why, depth_mm=round(pen * K), angle_deg=round(ang, 1), lat_mm=round(lat * K)))
    places['workplace_seats'] = dict(typical_depth_under_desk_mm=round(penM * K), figure_width_mm=round(wM * K), fixed=wp_rows[:200], counts=dict(nwp))
places['side_pedestals'] = ped_at
print('S14e workplace seats:', len(_seats_wp), dict(nwp), '| plain rectangles at a desk end -> side pedestals', nped, T())
# ================================================================================================ S15 edges and bits
KF = [k for k in FP if 'draw' in objs[k]]; ct = shapely.STRtree([FP[k] for k in KF]) if KF else None
ITEMS = [k for k, o in enumerate(objs) if 'draw' in o and o['key'] not in ('chair',) and o['ids']]
IF = {k: obj_fp(k) for k in ITEMS}; ITEMS = [k for k in ITEMS if IF[k] is not None]; itt = shapely.STRtree([IF[k] for k in ITEMS]) if ITEMS else None
mv = collections.Counter()
for k, o in enumerate(objs):
    if o['key'] not in ('deskedge', 'furn') or not o['ids']: continue
    for i in list(o['ids']):
        g = g_of(i); L_ = max(g.length, 1e-9); dest = None
        d = to_desk_or_edge(i) if o['key'] == 'deskedge' else None
        if d is not None: dest = d
        elif ct is not None:
            js = [KF[j] for j in ct.query(g) if FP[KF[j]].buffer(0.2).intersection(g).length >= 0.8 * L_]
            if js: dest = js[0]
        if dest is None and itt is not None:
            js = [ITEMS[j] for j in itt.query(g.buffer(0.3)) if IF[ITEMS[j]].buffer(0.3).intersection(g).length >= 0.8 * L_]
            if js: dest = js[0]
        if dest is not None and dest != k:
            o['ids'].remove(i); objs[dest]['ids'].append(i); owner[i] = dest; mv[o['key']] += 1
    if not o['ids']: o['key'] = 'empty'
print('edges and bits given to the item they lie in or along', dict(mv), T())
# ---- S15b test 9 (owner 06.10.2026: «почти все нераспознанные объекты — это части мебели… Нераспознано»). What is still
# without a type after S15:
# (1) a polyline that traces the outlines of desks (>= 80 % of its length within 0.3 pt of desk rectangles) is the desks'
#     own — of the desk that holds most of it; it is not drawn: the desk is its rectangle;
# (2) a piece <= 1200 mm with an end within 0.6 pt of an item that lies on the line of an edge of it (<= 3°, both ends
#     within 0.6 pt of that line) continues that edge — the item's own, drawn with it in the detailed result;
# (2b) a piece next to a seat (<= 0.6 pt) lying >= 80 % within its figure widened by 0.8 pt — its arm drawn just outside
#     the average figure — is the seat's own;
# (2c) a line between two items of one kind, on the line of their edges (<= 3°, <= 0.8 pt of their outlines), its ends
#     within 1.5 pt of each, bridges them — the nearer one's own, drawn with it;
# (3) a crumb <= 30 mm within 0.6 pt of an item is the item's own.
_NOT_ITEM = {'empty', 'wall', 'glass', 'lpart', 'dim', 'axis', 'mark', 'measure', 'tagc', 'zone', 'corezone', 'shaft', 'coreline',
             'roomsep', 'facade', 'wallline', 'door', 'lift', 'fire', 'furn', 'deskedge', 'group', 'chairpart', 'passage', 'text'}
_LEFT_K = ('group', 'furn', 'deskedge', 'chairpart')
_left = [(k, i) for k, o in enumerate(objs) if o['key'] in _LEFT_K and o['ids'] for i in list(o['ids']) if live(i) and not P[i].get('synthetic')]
m15b = collections.Counter()
if _left:
    _dk = [d for d in DESKS if d in DR]; _dt = shapely.STRtree([DR[d] for d in _dk]) if _dk else None
    _its, _ibx = [], []
    for k, o in enumerate(objs):
        if not o['ids'] or o['key'] in _NOT_ITEM: continue
        q_ = [np.asarray(P[i]['p'], float) for i in o.get('draw', o['ids']) if live(i) and len(P[i]['p'])]
        if not q_: continue
        q_ = np.vstack(q_); _its.append(k); _ibx.append(box(*q_.min(0), *q_.max(0)))
    _itt = shapely.STRtree(_ibx) if _ibx else None; _itf = {}
    def _fp15(kk):
        if kk not in _itf: _itf[kk] = obj_fp(kk)
        return _itf[kk]
    def _edge_dirs(poly):
        q = np.asarray(poly.exterior.coords); d = q[1:] - q[:-1]; L_ = np.hypot(d[:, 0], d[:, 1])
        return [(d[a] / L_[a], LineString([q[a], q[a + 1]])) for a in range(len(d)) if L_[a] >= 0.5]
    for k, i in _left:
        o = objs[k]
        if i not in o['ids']: continue
        g = g_of(i); L_ = max(g.length, 1e-9); dest = None; how_ = None
        if _dt is not None:
            qs_ = [_dk[a] for a in _dt.query(g.buffer(0.3))]
            if qs_ and g.intersection(unary_union([DR[d].buffer(0.3) for d in qs_])).length >= 0.8 * L_:
                dest = max(qs_, key=lambda d: DR[d].buffer(0.3).intersection(g).length); how_ = 'desk outlines'
        if dest is None and _itt is not None and L_ * K <= 1200 and g.geom_type == 'LineString':
            q = np.asarray(g.coords); a_, b_ = Point(q[0]), Point(q[-1]); v = q[-1] - q[0]
            if np.linalg.norm(v) > 1e-6:
                v = v / np.linalg.norm(v); best_ = None
                def _on_edge_line(fp_, tol_off):
                    for u_, ln in _edge_dirs(fp_):
                        if abs(float(u_ @ v)) < math.cos(math.radians(3)): continue
                        p0 = np.asarray(ln.coords[0]); nn = np.array([-u_[1], u_[0]])
                        if abs(float((q[0] - p0) @ nn)) <= tol_off and abs(float((q[-1] - p0) @ nn)) <= tol_off: return True
                    return False
                bridge_ = collections.defaultdict(list)
                for a in _itt.query(g.buffer(1.5)):
                    kk = _its[a]
                    if kk == k: continue
                    fp_ = _fp15(kk)
                    if fp_ is None: continue
                    dA, dB = fp_.distance(a_), fp_.distance(b_); dE = min(dA, dB)
                    if dE <= 1.5 and _on_edge_line(fp_, 0.8): bridge_[objs[kk]['key']].append((dA, dB, kk))   # the outline lies 0.12 pt out of the strokes
                    if dE > 0.6: continue
                    if L_ * K <= 30: how2 = 'crumb next to an item'              # (3) a crumb (<= 30 mm) next to an item
                    elif objs[kk]['key'] in ('chair', 'armchair') and g.intersection(fp_.buffer(0.8)).length >= 0.8 * L_:
                        how2 = 'arm or edge of a seat'                         # (2b) a seat's arm drawn just outside its figure
                    elif _on_edge_line(fp_, 0.6): how2 = 'continues an edge'  # (2) on the line of an edge (both ends <= 0.6 pt)
                    else: continue
                    if best_ is None or dE < best_[0]: best_ = (dE, kk, how2)
                if best_ is None:
                    # (2c) a line between two items of one kind, on the line of their edges, ends within 1.5 pt of each:
                    # it bridges them — the nearer one's own
                    for key_, lst in bridge_.items():
                        ka = [x for x in lst if x[0] <= 1.5]; kb = [x for x in lst if x[1] <= 1.5]
                        pairs_ = [(min(x[0], y[1]), x[2]) for x in ka for y in kb if x[2] != y[2]]
                        if pairs_: best_ = (0, min(pairs_)[1], 'bridges two items of one kind'); break
                if best_ is not None: dest = best_[1]; how_ = best_[2]
        if dest is not None and dest != k:
            o['ids'].remove(i); objs[dest]['ids'].append(i); owner[i] = dest; m15b[how_] += 1
            if how_ in ('continues an edge', 'bridges two items of one kind') and 'draw' in objs[dest]: objs[dest]['draw'].append(i)
            places['pieces_to_item_s15b'].append(dict(at=[round(v_, 1) for v_ in g.centroid.coords[0]], length_mm=round(L_ * K), to=objs[dest]['key'], how=how_))
    for k, o in enumerate(objs):
        if o['key'] in _LEFT_K and not [i for i in o['ids'] if not P[i].get('synthetic')]: o['key'] = 'empty'
print('S15b pieces without a type given to desks they trace or to the item whose edge they continue', dict(m15b), T())
# ================================================================================================ F6 the габаритный result
# owner 06.10.2026: «нам важно распознать тип объекта и распознать его габариты, внешний контур, чтобы его можно было потом
# изъять из плана и заменить другим объектом… два результата: 1) где мы установили и внутреннюю структуру… 2) …только
# габаритный внешний контур». Every object of furniture and equipment gets 'outline' — one closed outline (opaque light top
# and a black line); the detailed result keeps 'draw'. Seats — their figure; desks, cabinets, pedestals, kitchen sections,
# tables made rectangles — their rectangle; a table with a light top (>= 60 % of it) — the top's rectangle when the top is
# one (>= 90 % of its rectangle); round items — the smallest circle around them (48 points); the rest — the outer outline
# of its strokes (closed over gaps, holes filled), the fewest points (Douglas–Peucker 0.06 pt), straight sides (0.1 pt).
OUT_SKIP = {'empty', 'wall', 'glass', 'lpart', 'dim', 'axis', 'mark', 'measure', 'tagc', 'zone', 'corezone', 'shaft', 'coreline',
            'roomsep', 'facade', 'wallline', 'door', 'lift', 'conv', 'fire', 'furn', 'deskedge', 'group', 'chairpart', 'passage'}
def _ol_new(k, poly):
    o = objs[k]; ring = list(poly.exterior.coords); sq = P[o['ids'][0]]['seq'] if o['ids'] else 0
    f_id = new_prim(FURN_LAYER, 'fill', ring[:-1], TOP, alpha=1.0, seq=sq); l_id = new_prim(FURN_LAYER, 'line', ring, (0.0, 0.0, 0.0), seq=sq)
    owner[f_id] = owner[l_id] = k; o['ids'] += [f_id, l_id]; return [f_id, l_id]
def _syn_ring(i): return P[i].get('synthetic') and P[i]['kind'] == 'fill' and len(P[i]['p']) >= 3
how6 = collections.Counter()
for k, o in enumerate(objs):
    if o['key'] in OUT_SKIP or not o['ids']: continue
    dr = o.get('draw')
    src_ = [i for i in o['ids'] if not P[i].get('synthetic') and live(i)]
    if o['key'] in ('chair', 'armchair') and dr and _syn_ring(dr[0]):
        o['outline'] = dr[:2]; how6['фигура места'] += 1; continue
    if o['key'] in ('rtable', 'round'):
        g_ = solid_fp(src_) if src_ else None
        if g_ is not None:
            cc = shapely.minimum_bounding_circle(g_); ctr = np.array(cc.centroid.coords[0]); r_ = shapely.minimum_bounding_radius(g_)
            circ = Polygon([tuple(ctr + r_ * np.array([math.cos(a), math.sin(a)])) for a in np.linspace(0, 2 * math.pi, 49)[:-1]])
            o['outline'] = _ol_new(k, circ); how6['круг'] += 1; continue
    if o['key'] in ('mtable', 'dtable', 'table', 'ctable', 'counter') and src_:
        lf = [g_of(i) for i in src_ if P[i]['kind'] == 'fill' and LIGHT(P[i]['col'])]
        fpa = solid_fp(src_)
        if lf and fpa is not None:
            top = safe_union([g.buffer(0.05) for g in lf]).buffer(0.25, join_style=2).buffer(-0.25, join_style=2)
            mt_ = mrr(top) if not top.is_empty else None
            if mt_ and top.area >= 0.6 * fpa.area and top.area >= 0.9 * mt_['poly'].area:
                o['outline'] = _ol_new(k, Polygon(rect(mt_['c'], mt_['u'], mt_['L'], mt_['W']))); how6['стол: прямоугольник столешницы'] += 1; continue
    if dr and _syn_ring(dr[0]) and len(P[dr[0]]['p']) == 4 and o['key'] in ('desk', 'storage', 'pedestal', 'kitchen', 'ctable', 'dtable', 'table', 'mtable'):
        o['outline'] = dr[:2]; how6['прямоугольник'] += 1; continue
    if dr and _syn_ring(dr[0]) and o['key'] in ('sofa', 'counter', 'mtable', 'dtable', 'rtable', 'armchair'):
        o['outline'] = dr[:2]; how6['главный контур'] += 1; continue
    g_ = solid_fp(src_) if src_ else None
    if g_ is None or g_.area < 0.05: how6['нет контура'] += 1; continue
    q_ = g_.simplify(0.06)
    try:
        sr_ = Polygon(straight_ring(list(q_.exterior.coords)[:-1], 0.1)).buffer(0)
        if not sr_.is_empty and sr_.geom_type == 'Polygon' and abs(sr_.area - q_.area) <= 0.1 * q_.area: q_ = sr_
    except Exception: pass
    o['outline'] = _ol_new(k, q_); how6['внешний контур штрихов'] += 1
print('F6 габаритный result: outlines', dict(how6), T())
# ================================================================================================ report and write
lab_on = collections.Counter(lab_desk.values())
left = collections.Counter(o['key'] for o in objs if o['key'] in ('table', 'group', 'furn', 'chairpart', 'deskedge') and o['ids'] and 'draw' not in o)
res = dict(counts=dict(rep), typical_desk_sizes_mm=[[k[0], k[1], v] for k, v in sz.most_common()], desk_numbers=len(LP),
           desks=len(DESKS), numbers_on_desks=len(lab_desk), desks_without_number=places.get('desks_without_number', []),
           left_for_review=dict(left), places=places)
json.dump(res, open('furniture.json', 'w'), ensure_ascii=False, indent=1, default=str)
pickle.dump(dict(objs=objs, owner=owner, wall_in=O.get('wall_in', {})), open('objects.pkl', 'wb'))
D1 = dict(D0); D1['P'] = P; pickle.dump(D1, open('prims_f.pkl', 'wb'))
print('numbers on desks', len(lab_desk), 'of', len(LP), '| desks', len(DESKS), '| left for review', dict(left),
      collections.Counter(o['key'] for o in objs if o['key'] in ('desk', 'chair', 'armchair', 'sofa', 'round', 'rtable', 'mtable', 'dtable', 'ctable', 'storage', 'pedestal', 'kitchen', 'table')), T())
