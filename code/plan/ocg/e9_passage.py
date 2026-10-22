"""Э9 (owner 06.10.2026): the passage zone of an open space, where no walls mark it — schematic, no roundings.
The corridor is found by walls and doors; in an open space the passage is the free floor between the furniture groups:
 1. floor: the hull of the facade and the walls; obstacles: wall bodies, glass, columns, the core (its zone, shafts,
    lifts, counters), the facade and every piece of furniture (desks, chairs, tables, sofas, cabinets, kitchen, plants,
    equipment) — chairs as drawn (pulled out as the source shows them);
 2. rooms: the free floor with the door openings closed falls apart into rooms; an open space is a room with >= 4
    numbered desks; the corridor zone of the source (the «Помещения» fill) is a passage of its own;
 3. passage width W — the long side of the typical workplace desk (the most common size of the numbered desks,
    furniture.json; env WIDTH_MM overrides). Owner 06.10.2026: «Она должна быть шире, чем стол по длинной стороне.
    Стол в смысле рабочее место.» — a strip narrower than W is not a passage;
 4. passage: the opening of the open space's free floor by a disk of diameter W (where a strip of width W passes), joined
    to the doors and the corridor (a component that touches no door opening and no corridor and is < 6 m² is a pocket);
 5. schematic outline (owner 06.10.2026: «схематично… убери всякие скругления»): the passage is redrawn as straight strips
    along its centre lines — the skeleton of the region (raster 50 mm), spurs shorter than W dropped, each branch made
    straight (Douglas–Peucker, TOL_MM, 300 mm by default); straight pieces of one width (within 15 % or 150 mm) make one
    strip — the polyline buffered with flat ends and sharp joins, as wide as the passage there (25th percentile of the
    clearance along it, never narrower than W); dead ends carried to the boundary, strips overlapping at the joints; the union is clipped to the floor minus the hard obstacles (walls, glass, core,
    desks, tables, cabinets…) — seats (chairs, armchairs) move and do not notch the strip; wedges thinner than 300 mm go.
    Test 10: each side of a strip is straight — at the wall where a wall bounds it, else between the narrowest and the
    mean free width of that side and never on a place (side_offsets).
Writes passage.pkl (polygons, pt) and passage.json (areas m², by open space). usage: python3 e9_passage.py"""
import pickle, json, math, collections, re, sys, time, os
from scipy import ndimage
from skimage.morphology import skeletonize
from PIL import Image as _Im, ImageDraw as _Dr
import numpy as np, shapely
from shapely.geometry import Polygon, Point, LineString, box
from shapely.ops import unary_union
import os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import sheet; from e7_comp import geom, load_prims, load_walls
t0 = time.time(); K = sheet.K
_uu = unary_union
def unary_union(gs):
    gs = [g for g in gs if g is not None and not g.is_empty]
    try: return _uu(gs)
    except Exception: return shapely.union_all([shapely.make_valid(g) for g in gs], grid_size=0.001)
def T(): return f'{time.time() - t0:.1f} s'
def desk_long_mm():
    try:
        S_ = json.load(open('furniture.json')).get('typical_desk_sizes_mm') or []
        if S_: return float(max(S_, key=lambda r: r[2])[0])        # [long, short, count] of numbered desks
    except Exception: pass
    return None
DESK_MM = desk_long_mm()
WIDTH_MM = float(os.environ.get('WIDTH_MM') or DESK_MM or 1400.0); WIDTH = WIDTH_MM / K
TOL = float(os.environ.get('TOL_MM', '300')) / K
WIDTH_FROM = 'WIDTH_MM' if os.environ.get('WIDTH_MM') else ('длинная сторона типового рабочего стола' if DESK_MM else 'умолчание 1400 мм')
print('passage width', round(WIDTH_MM), 'mm —', WIDTH_FROM, '| outline tolerance', round(TOL * K), 'mm')
def open_round(g, r):
    """opening by a disk of radius r: the floor where a strip of width 2r passes"""
    return g.buffer(-r, join_style=1).buffer(r, join_style=1)
RES = 50 / K                                            # raster step of the skeleton, 50 mm
NB8 = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
def raster(G, x0, y0, nx, ny):
    im = _Im.new('L', (nx, ny), 0); d = _Dr.Draw(im)
    def Tr(cs): return [((x - x0) / RES, (y - y0) / RES) for x, y in cs]
    for q in getattr(G, 'geoms', [G]):
        if q.geom_type != 'Polygon' or q.is_empty: continue
        d.polygon(Tr(q.exterior.coords), fill=1)
        for h in q.interiors: d.polygon(Tr(h.coords), fill=0)
    return np.array(im, bool)
def branches(sk):
    """skeleton pixels -> branches (pixel paths between nodes: ends and junctions) and the degree of every pixel"""
    pts = set(zip(*np.nonzero(sk)))
    def nb(p): return [(p[0] + a, p[1] + b) for a, b in NB8 if (p[0] + a, p[1] + b) in pts]
    deg = {p: len(nb(p)) for p in pts}; nodes = {p for p, k in deg.items() if k != 2}
    used = set(); out = []; seen = set()
    for n in nodes:
        for q in nb(n):
            if (n, q) in used: continue
            path = [n, q]; used.update({(n, q), (q, n)}); prev, cur = n, q
            while cur not in nodes:
                nx_ = [r_ for r_ in nb(cur) if r_ != prev and (cur, r_) not in used]
                if not nx_: break
                nxt = nx_[0]; used.update({(cur, nxt), (nxt, cur)}); path.append(nxt); prev, cur = cur, nxt
            out.append(path); seen.update(path)
    rest = pts - seen                                   # rings without a node (a passage around an island)
    while rest:
        st = next(iter(rest)); path = [st]; rest.discard(st); cur = st
        while True:
            nx_ = [r_ for r_ in nb(cur) if r_ in rest]
            if not nx_: break
            cur = nx_[0]; path.append(cur); rest.discard(cur)
        if len(path) > 2: path.append(path[0])
        out.append(path)
    return out, deg
# test 10 (owner 07.10.2026: «там, где у тебя нет явной стены попробуй спрямлять линию прохода, чтобы она не была с разными
# выступами и выемками… с прохода срежь боковые края… можешь померить среднюю ширину прохода, или даже взять минимальную
# ширину прохода, и в диапазоне от минимальной ширины прохода до средней ширины прохода подобрать прямую линию, чтобы она не
# попадала на места»). Each side of a strip is a straight line parallel to its centre line. Rays across the centre line,
# every 100 mm on each side: the half-width of the passage there — up to the first place (any furniture: desks, seats,
# tables, cabinets…) or wall (bodies, glass, facade, core), at most the strip's half-width h. A side is a wall side when the
# wall comes first on at least half of the rays — the strip keeps h and the clip by the walls draws the edge along the wall;
# otherwise the side's line lies at the mean half-width, but no farther than the nearest place along the run — between the
# narrowest and the mean, never on a place; rays from a centre line that itself runs at a place (< 0.2 W: a corner of the
# simplified line) are not counted.
SIDES = []; DBG = bool(os.environ.get('PASS_DEBUG')); DBGS = []
def side_offsets(P_, h):
    if PLT is None: return h, h, 'симметрично'
    res = []; hows = []; step = 100 / K
    for sgn in (1, -1):                                  # +1: left of the run's direction (shapely's single-sided +), -1: right
        dp, dw = [], []
        for a, b in zip(P_[:-1], P_[1:]):
            L = float(np.linalg.norm(b - a))
            if L < 1e-6: continue
            t_ = (b - a) / L; nv = np.array([-t_[1], t_[0]]) * sgn
            xs = list(np.arange(0.5 * step, L, step)) or [L / 2]
            for x in xs:
                p = a + t_ * x
                dp.append(ray_hit(PLT, PLG, p, nv, h)); dw.append(ray_hit(WLT, WLG, p, nv, h))
        if not dp: res.append(h); hows.append('нет лучей'); continue
        dp, dw = np.array(dp), np.array(dw); e = np.minimum(dp, dw); ok = e >= 0.2 * WIDTH
        if not ok.any(): res.append(h); hows.append('у центра места'); continue
        if ((dw < dp) & (dw < h - 1e-6)).mean() >= 0.5: res.append(h); hows.append('до стены'); continue
        d = max(min(float(e[ok].mean()), float(dp[ok].min())), float(e[ok].min()))
        res.append(d); hows.append('прямая между мин. и средней')
    return res[0], res[1], ' / '.join(hows)
def ray_hit(tree, G, p, v, rmax):
    ray = LineString([tuple(p), tuple(p + v * rmax)]); best = rmax; P0 = Point(tuple(p))
    for j in tree.query(ray):
        x = G[j].intersection(ray)
        if not x.is_empty: best = min(best, P0.distance(x))
    return best
def merge_through(brs, deg):
    keep = []
    for path in brs:
        if len(path) < 2: continue
        leaf = [deg.get(path[0], 0) <= 1, deg.get(path[-1], 0) <= 1]
        if (leaf[0] or leaf[1]) and len(path) * RES < WIDTH: continue          # a spur toward a corner, not a corridor
        keep.append(list(path))
    changed = True
    while changed:
        changed = False; inc = collections.defaultdict(list)
        for x, p in enumerate(keep):
            if p[0] == p[-1]: continue                                          # a ring
            inc[p[0]].append((x, 0)); inc[p[-1]].append((x, 1))
        for nd, ends in inc.items():
            if len(ends) != 2 or ends[0][0] == ends[1][0]: continue
            (a, ea), (b, eb) = ends
            A = keep[a] if ea == 1 else keep[a][::-1]; B = keep[b] if eb == 0 else keep[b][::-1]
            keep[a] = A + B[1:]; keep.pop(b); changed = True; break
    return keep
def schematic(G, room):
    """the passage G as straight strips (rectangles along its centre lines), clipped to the free floor of the room"""
    x0, y0, x1, y1 = G.bounds; x0 -= 4 * RES; y0 -= 4 * RES
    nx = int((x1 - x0) / RES) + 9; ny = int((y1 - y0) / RES) + 9
    m = raster(G, x0, y0, nx, ny)
    if m.sum() < 10: return Polygon(), 0
    dist = ndimage.distance_transform_edt(m) * RES; sk = skeletonize(m)
    brs, deg = branches(sk); rects = []; nseg = 0
    # test 10: spurs toward corners (shorter than W) are dropped first, then the branches they cut are joined again through
    # the nodes left with two branches — a corridor along a row of desk ends is one path, not a branch per desk row
    brs = merge_through(brs, deg)
    for path in brs:
        if len(path) < 2: continue
        leaf = [deg.get(path[0], 0) <= 1, deg.get(path[-1], 0) <= 1]
        xy = np.array([(x0 + (c + 0.5) * RES, y0 + (r_ + 0.5) * RES) for r_, c in path]); dv = np.array([dist[r_, c] for r_, c in path])
        ls = LineString(xy).simplify(TOL, preserve_topology=False); V = np.array(ls.coords)
        if len(V) < 2: continue
        pr = np.array([ls.project(Point(p_)) for p_ in xy]); cum = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(V, axis=0), axis=1))])
        segs = []                                                               # (k, clearances of the skeleton pixels along segment k)
        for k in range(len(V) - 1):
            sel = dv[(pr >= cum[k] - 1e-9) & (pr <= cum[k + 1] + 1e-9)]
            if len(sel) and cum[k + 1] - cum[k] > 1e-6: segs.append((k, sel))
        if not segs: continue
        runs = [[sg] for sg in segs]                    # test 10: a strip per straight segment — its two sides straight lines
        for run in runs:
            k0, k1 = run[0][0], run[-1][0]
            # a short wiggle at a junction, or a short connector between two junctions (test 10: also alone — the pixels of a
            # junction cluster made squares across the corridor): the long strips, carried over the junction, cover it
            if cum[k1 + 1] - cum[k0] < 0.75 * WIDTH and not (len(runs) == 1 and (leaf[0] or leaf[1])): continue
            h = max(float(np.percentile(np.concatenate([x[1] for x in run]), 25)), WIDTH / 2)
            P_ = [np.array(v) for v in V[k0:k1 + 2]]
            # test 10: the two sides of the strip — straight where no wall bounds it (side_offsets)
            dl, dr, how = side_offsets(P_, h)
            u0 = (P_[1] - P_[0]) / max(np.linalg.norm(P_[1] - P_[0]), 1e-9); u1 = (P_[-1] - P_[-2]) / max(np.linalg.norm(P_[-1] - P_[-2]), 1e-9)
            e0 = float(dv[0]) if (k0 == 0 and leaf[0]) else max(dl, dr)         # a dead end reaches the boundary; a joint overlaps
            e1 = float(dv[-1]) if (k1 == len(V) - 2 and leaf[1]) else max(dl, dr)
            P_[0] = P_[0] - u0 * e0; P_[-1] = P_[-1] + u1 * e1
            ln = LineString([tuple(v) for v in P_])
            rects.append(unary_union([ln.buffer(dl, cap_style=2, join_style=2, mitre_limit=2.0, single_sided=True),
                                      ln.buffer(-dr, cap_style=2, join_style=2, mitre_limit=2.0, single_sided=True)])); nseg += 1
            SIDES.append(dict(at=[round(float(v), 1) for v in ln.interpolate(0.5, normalized=True).coords[0]], length_mm=round(ln.length * K),
                              left_mm=round(dl * K), right_mm=round(dr * K), how=how))
            if DBG: DBGS.append((ln, dl, dr, how, rects[-1]))
    if not rects: return Polygon(), 0
    clip = room.union(seats.intersection(room.buffer(1.0))).difference(hard)          # straight edges: seats do not notch the strip
    U = unary_union(rects).intersection(clip)
    U = U.buffer(-150 / K, join_style=2, mitre_limit=2.0).buffer(150 / K, join_style=2, mitre_limit=2.0)   # wedges thinner than 300 mm go
    return U.simplify(100 / K, preserve_topology=True), nseg
D = load_prims(); P = D['P']; TX = D['T']; O = pickle.load(open('objects.pkl', 'rb')); objs = O['objs']
W = load_walls()['bodies']
def ogeom(o, buf=0.0):
    gs = []
    for i in o.get('draw', o['ids']):
        if P[i]['kind'] == 'removed': continue
        g = geom(P[i])
        if g.is_empty: continue
        gs.append(g.buffer(max(buf, 0.12)) if g.geom_type in ('LineString', 'MultiLineString') else g.buffer(buf))
    return unary_union(gs) if gs else None
FURN = {'desk', 'chair', 'chairpart', 'armchair', 'sofa', 'round', 'rtable', 'mtable', 'dtable', 'ctable', 'storage', 'pedestal', 'kitchen',
        'table', 'group', 'furn', 'deskedge', 'booth', 'mfp', 'plant', 'counter', 'sink', 'san', 'equip', 'fire', 'conv'}
CORE = {'corezone', 'shaft', 'lift', 'counter'}
SOFT = {'chair', 'chairpart', 'armchair'}               # seats move: the passage is found around them, its schematic strip may cross them
_fk = [(o['key'], ogeom(o)) for o in objs if o['key'] in FURN and o['ids']]; _fk = [(k, g) for k, g in _fk if g is not None and not g.is_empty]
furn = [g for _, g in _fk]
# furniture of the source as drawn: a closed outline is the item's floor (its hull when it is small, e.g. a chair)
furn = [g.convex_hull if g.area < 60 else g for g in furn]
seats = unary_union([g.convex_hull for k, g in _fk if k in SOFT])
hard_furn = [g.convex_hull if g.area < 60 else g for k, g in _fk if k not in SOFT]
core_parts = [ogeom(o) for o in objs if o['key'] in CORE and o['ids']]
core = unary_union([g.convex_hull for g in core_parts if g is not None and not g.is_empty]) if core_parts else Polygon()
facade = unary_union([ogeom(o, 0.3) for o in objs if o['key'] == 'facade' and o['ids']])
glass = unary_union([ogeom(o, 0.05) for o in objs if o['key'] in ('glass', 'lpart', 'coreline') and o['ids']])
walls = unary_union([g for _, g in W])
floor = unary_union([facade, walls]).convex_hull.buffer(-0.5)
obst = unary_union([walls, glass, facade, core] + furn)
hard = unary_union([walls, glass, facade, core] + hard_furn)
PLG = [g for g in furn if g is not None and not g.is_empty and g.area > 0]; PLT = shapely.STRtree(PLG) if PLG else None
_wl = unary_union([walls, glass, facade, core]); WLG = [q for q in getattr(_wl, 'geoms', [_wl]) if not q.is_empty]; WLT = shapely.STRtree(WLG)
free = floor.difference(obst)
print('floor', round(floor.area * K * K / 1e6, 1), 'm² | free', round(free.area * K * K / 1e6, 1), 'm²', T())
# door openings from Э6г (geom_report.json frames) close the rooms
R = json.load(open('geom_report.json')); openings = []
for d in R['places'].get('doors', []):
    f = d.get('frame')
    if not f: continue
    o_, u_, n_ = np.array(f[0]), np.array(f[1]), np.array(f[2]); c0, c1, tl, th = f[3], f[4], f[5], f[6]
    openings.append(Polygon([tuple(o_ + u_ * a + n_ * b) for a, b in ((c0, tl - 0.3), (c1, tl - 0.3), (c1, th + 0.3), (c0, th + 0.3))]))
OP = unary_union(openings) if openings else Polygon()
rooms = [q for q in getattr(free.difference(OP.buffer(0.2)), 'geoms', [free.difference(OP.buffer(0.2))]) if q.geom_type == 'Polygon' and q.area > 20]
labels = [Point((t['bbox'][0] + t['bbox'][2]) / 2, (t['bbox'][1] + t['bbox'][3]) / 2) for t in TX
          if re.fullmatch(r'\s*\d{1,3}(-\d)?(\s+\d{1,3}(-\d)?)*\s*', t['text']) and t['size'] > 12]
desks = [ogeom(o) for o in objs if o['key'] == 'desk' and o['ids']]
corr = unary_union([ogeom(o) for o in objs if o['key'] == 'zone' and o['ids']] or [Polygon()])
open_spaces = []
for r in rooms:
    hull = r.buffer(1.0)                               # desks are obstacles: count the desks the room's floor wraps
    nd = sum(1 for g in desks if g is not None and hull.buffer(2.0).intersects(g) and r.convex_hull.contains(g.centroid))
    if nd >= 4: open_spaces.append((r, nd))
print('rooms (doors closed)', len(rooms), '| open spaces (>= 4 desks)', len(open_spaces), T())
res = []; PASS = []
for r, nd in open_spaces:
    op = open_round(r, WIDTH / 2).intersection(r)
    comps = [q for q in getattr(op, 'geoms', [op]) if q.geom_type == 'Polygon' and q.area > 4]
    keep = []
    for q in comps:
        touches = q.buffer(1.5).intersects(OP) or (not corr.is_empty and q.buffer(1.5).intersects(corr))
        if touches or q.area * K * K / 1e6 >= 6: keep.append(q)
    if not keep: continue
    pz, nseg = schematic(unary_union(keep), r)
    pz = unary_union([q for q in getattr(pz, 'geoms', [pz]) if q.geom_type == 'Polygon' and q.area * K * K / 1e6 >= 0.5]).simplify(0.02, preserve_topology=True)
    if pz.is_empty: continue
    PASS.append(pz)
    res.append(dict(at=[round(v, 1) for v in r.representative_point().coords[0]], desks=nd, open_space_free_m2=round(r.area * K * K / 1e6, 1),
                    passage_m2=round(pz.area * K * K / 1e6, 1), share=round(pz.area / r.area, 2), parts=len(getattr(pz, 'geoms', [pz])), strips=nseg,
                    vertices=sum(len(q.exterior.coords) - 1 + sum(len(h.coords) - 1 for h in q.interiors) for q in getattr(pz, 'geoms', [pz]))))
if DBG: pickle.dump(DBGS, open('passage_dbg.pkl', 'wb'))
pickle.dump(dict(passage=PASS, open_spaces=[r for r, _ in open_spaces], corridor=corr, width_mm=WIDTH * K, width_from=WIDTH_FROM, tol_mm=TOL * K), open('passage.pkl', 'wb'))
json.dump(dict(width_mm=round(WIDTH * K), width_from=WIDTH_FROM, tol_mm=round(TOL * K), open_spaces=res, strip_sides=SIDES), open('passage.json', 'w'), ensure_ascii=False, indent=1)
print('passage zones', len(PASS), '| area', round(sum(p.area for p in PASS) * K * K / 1e6, 1), 'm²', res, T())
