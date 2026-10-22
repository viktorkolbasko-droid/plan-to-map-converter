"""Э7р (owner 09.10.2026, remarks З-1, З-2, З-3, З-9; extra points ЛТ-1…ЛТ-3): one straight wall — one type, four points.

Owner: «1. Это опять же разные типы в одной стене… 2. Вторая проблема: это избыточное количество точек. Это прямая стена, и
каждый из участков должен быть в 4 точках… Нужно эти изломы перепроверять на оправданность. И если неоправданно, то спрямлять
стену и упрощать полигон.» «Массивной мебели, такой как столы, стеллажи, тоже нужно проверять на наличие лишних точек, на наличие
микроизгибов… Стол: он часто либо квадратный, прямоугольный, либо круглый.»

Runs after Э7о, before Э9 (the passage and the rooms are built on the cleaned walls):
 1. glass bands — every glass partition object becomes bands: one band per straight piece, its smallest rotated rectangle when
    the piece is one (no point farther than TOL), else its outline cleaned on the face lines; the band is drawn as one fill and
    one closed outline of the same points (one type: A-22G) instead of the source fill and its open lines;
 2. one wall — one type: the wall bodies lose what lies in a glass band, and every thin piece left (narrower than SLIVER, 24 mm —
    no wall is that thin) is dropped: the GKL sliver along the glass of 40.23 «архив» (З-1);
 3. face lines (regular.py) of all walls, glass bands, core blocks and the source lines of the glass; every wall body, band and
    core block is put on them: points on a straight line, jogs, steps and kinks under TOL (30 mm) and notches at junctions
    (≤ 120 mm from the corner they become) disappear; curved runs stay (arcs, written as arcs at the export);
 4. columns — their rectangle when they are one; massive furniture (tables, cabinets, counters, kitchens, sofas, МФУ) — the
    габарит outline cleaned on its own face lines (TOL_F, 15 mm), its rectangle when it is one, right angles when it is
    rectilinear within 3°.
Writes walls_r.pkl, prims_r.pkl, objects.pkl (glass ids), regular.json (counts before/after, every place changed).
Code 012 (stage 2 of the merge of v010 into ocg/; the code of pass v010, route/e7r_regular.py) — the step of the layer route
after Э7к (ocg/run_ocg.sh): the scale of the sheet from cfg through regular.py (ocg/sheet.py, cfg.MM_PER_PT; v010: K = 48.04 in
the code); every threshold in mm through it — v010 set the merge and area tolerances in pt (0.01–0.1 pt, 0.01–0.2 pt², a cut
line of 10 pt) at 48.04 mm/pt <one example: client-b, floor 40>; the mm here are those pt × 48.04 (the same numbers on that
sheet); no scale — a stop (regular.py)."""
import pickle, json, sys, time, collections, math, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np, shapely
from shapely.geometry import Polygon, MultiPolygon, LineString
from shapely.ops import unary_union
from e7_comp import load_prims, load_walls, geom
import regular as RG
t0 = time.time()
def T(): return f'{time.time() - t0:.1f} s'
K = RG.K; MM = RG.MM
def mm(v): return v / K                    # a threshold in mm -> pt of the sheet
def mm2(v): return v / (K * K)             # an area in mm² -> pt² of the sheet
# thresholds in mm (v010 in pt at 48.04 mm/pt): a cut line across a glass band CUT_HALF_MM each way; pieces of glass and bands
# from PIECE_MM2; pieces closed by JOIN_MM (JOIN_SMALL_MM for a small piece); bits of a wall body from BIT_MM2; a neighbour within
# NEAR_MM, a common boundary measured in TOUCH_MM; the outline of a piece of furniture: its rectangle grown by BOX_MM
CUT_HALF_MM = 480.4                                    # 10 pt
PIECE_MM2, BIT_MM2 = 46.156832, 23.078416              # 0.02 pt², 0.01 pt²
JOIN_MM, JOIN_SMALL_MM, NEAR_MM, TOUCH_MM, BOX_MM = 0.9608, 0.4804, 2.402, 1.4412, 4.804    # 0.02, 0.01, 0.05, 0.03, 0.1 pt
TOL_F = 15.0 * MM                     # furniture: jogs and kinks under 15 mm
MASSIVE = {'desk', 'table', 'mtable', 'dtable', 'ctable', 'storage', 'pedestal', 'counter', 'kitchen', 'sofa', 'mfp', 'equip',
           'booth'}
D = load_prims(skip=('prims_r.pkl',)); P = D['P']; TX = D['T']          # a rerun starts from Э7к, not from its own output
WD = load_walls(skip=('walls_r.pkl',)); W = WD['bodies']
O = pickle.load(open('objects.pkl', 'rb')); objs = O['objs']
rep = collections.Counter(); places = collections.defaultdict(list)
def nverts(g):
    return sum(len(r.coords) - 1 for q in getattr(g, 'geoms', [g]) for r in [q.exterior] + list(q.interiors))
def new_prim(layer, kind, pts, col, alpha=1.0, seq=0, **kw):
    p = dict(id=len(P), layer=layer, kind=kind, p=[tuple(map(float, v)) for v in pts], col=col, alpha=alpha, seq=seq, synthetic=True)
    if kind == 'fill': p['holes'] = []
    else: p['w'] = 0
    p.update(kw); P.append(p); return p['id']
# ------------------------------------------------------------------------------------------------ 1. glass bands
def obj_geoms(o):
    out = []
    for i in o['ids']:
        p = P[i]
        if p['kind'] == 'fill':
            g = Polygon(p['p'], p.get('holes', [])).buffer(0)
            if not g.is_empty: out.append(('fill', i, g))
        elif p['kind'] == 'wline': out.append(('fill', i, geom(p)))
        elif len(p['p']) >= 2: out.append(('line', i, LineString(p['p'])))
    return out
GB = {}                               # glass object -> [band polygons]
GKEEP = {}                            # glass object -> source line prims not covered by its bands (kept as lines)
TOL_G = 70.0 * MM                     # a glass piece is a band when its rectangle is that close (the source fills end in rounded
                                      # or skewed caps up to ≈ 70 mm long, З-1)
def band_of(q):
    """a glass piece that is a band: a rectangle along its long axis, as thick as the band is along most of its length — the
    median cross-section between 15 % and 85 % of the length (v010: the smallest rotated rectangle took the thickness of a wider
    post at an end, 130 mm for a 68 mm glass, and put the door next to it off its opening)"""
    m = q.minimum_rotated_rectangle
    if m.geom_type != 'Polygon': return None
    xs = list(m.exterior.coords); a_, b_ = RG.dist(xs[0], xs[1]), RG.dist(xs[1], xs[2])
    if min(a_, b_) > 200 * MM or q.exterior.hausdorff_distance(m.exterior) > TOL_G or q.interiors: return None
    p0, p1 = (xs[0], xs[1]) if a_ >= b_ else (xs[1], xs[2])
    L = RG.dist(p0, p1); u = ((p1[0] - p0[0]) / L, (p1[1] - p0[1]) / L); n = (-u[1], u[0])
    lo, hi = [], []
    for t in np.linspace(0.15, 0.85, 15):
        c = (p0[0] + u[0] * t * L, p0[1] + u[1] * t * L)
        cut = LineString([(c[0] - n[0] * mm(CUT_HALF_MM), c[1] - n[1] * mm(CUT_HALF_MM)), (c[0] + n[0] * mm(CUT_HALF_MM), c[1] + n[1] * mm(CUT_HALF_MM))]).intersection(q)
        if cut.is_empty: continue
        ds = [(x - c[0]) * n[0] + (y - c[1]) * n[1] for g_ in getattr(cut, 'geoms', [cut]) for x, y in g_.coords]
        lo.append(min(ds)); hi.append(max(ds))
    if len(lo) < 5: return Polygon(xs[:-1])
    a0, a1 = float(np.median(lo)), float(np.median(hi))
    if a1 - a0 <= 0 or min(a_, b_) <= 1.3 * (a1 - a0): return Polygon(xs[:-1])     # no wider post at an end: the rectangle
    return Polygon([(p0[0] + n[0] * a0, p0[1] + n[1] * a0), (p1[0] + n[0] * a0, p1[1] + n[1] * a0),
                    (p1[0] + n[0] * a1, p1[1] + n[1] * a1), (p0[0] + n[0] * a1, p0[1] + n[1] * a1)])
for k, o in enumerate(objs):
    if o['key'] != 'glass' or not o['ids']: continue
    G = obj_geoms(o)
    fills = [g for t, i, g in G if t == 'fill']
    if not fills: rep['glass without fill (lines kept)'] += 1; continue
    pieces = []
    for f in fills:
        for q in getattr(f, 'geoms', [f]):
            if q.geom_type != 'Polygon' or q.area < mm2(PIECE_MM2): continue
            r = band_of(q); pieces.append(r if r is not None else q)
    U = unary_union([q.buffer(mm(JOIN_MM), join_style=2) for q in pieces]).buffer(-mm(JOIN_MM), join_style=2)
    bands = []
    for q in getattr(U, 'geoms', [U]):
        if q.geom_type != 'Polygon' or q.area < mm2(PIECE_MM2): continue
        r = band_of(q); bands.append(r if r is not None else q)
    GB[k] = bands
    rep['glass: one band' if len(bands) == 1 and band_of(bands[0]) is not None else 'glass: bands of several pieces'] += 1
    BU = unary_union(bands).buffer(50 * MM)
    GKEEP[k] = [i for t, i, g in G if t == 'line' and not BU.covers(g)]
print('glass bands', sum(len(v) for v in GB.values()), 'of', len(GB), 'objects', T())
# ------------------------------------------------------------------------------------------------ 2. one wall — one type
# a) slivers: a piece narrower than SLIVER everywhere (8 mm — a hair, a wedge along the glass, З-1) is dropped;
# b) a thin strip (narrower than THIN, 30 mm: a lining, a second line of the same wall) joins the wall it lies along — its class
#    is that wall's; along a glass band only — it is dropped (the glass is the wall there);
# c) the glass bands end where the walls are (walls first: a band never cuts a wall).
SLIVER = 8.0 * MM; THIN = 30.0 * MM
COLS = unary_union([g for c, g in W if c == 'column'])
W1 = []
for c, g in W:
    if c == 'column': W1.append([c, g]); continue
    if g.intersects(COLS) and g.intersection(COLS).area > mm2(BIT_MM2):          # a GKL casing around a column: the casing is a ring,
        g = g.difference(COLS); rep['wall bodies cut by columns'] += 1   # the column is the column (one place — one type)
    g3 = g.buffer(-SLIVER / 2, join_style=2).buffer(SLIVER / 2, join_style=2).intersection(g)
    parts = [q for q in getattr(g3, 'geoms', [g3]) if q.geom_type == 'Polygon' and q.area > mm2(BIT_MM2)]
    lost = g.area - sum(q.area for q in parts)
    if lost > mm2(BIT_MM2):
        rep['wall slivers dropped'] += 1
        dg = g.difference(unary_union(parts)) if parts else g
        places['sliver'].append(dict(cls=c, at=[round(v, 1) for v in (dg if not dg.is_empty else g).representative_point().coords[0]], mm2=round(lost * K * K)))
    for q in parts: W1.append([c, q])
GBU = unary_union([b for bs in GB.values() for b in bs]) if GB else None
tree = shapely.STRtree([g for c, g in W1])
for i, (c, g) in enumerate(W1):
    if c == 'column' or g is None or not g.buffer(-THIN / 2, join_style=2).is_empty: continue
    half = g.length / 2; best = None; bl = 0.0
    for j in tree.query(g.buffer(mm(NEAR_MM))):
        if j == i or W1[j][1] is None or W1[j][0] == 'column': continue
        if W1[j][1].buffer(-THIN / 2, join_style=2).is_empty: continue          # thin with thin: no host
        sl = g.buffer(mm(TOUCH_MM)).intersection(W1[j][1].boundary).length
        if sl > bl: best, bl = j, sl
    if best is not None and bl >= 0.3 * half:
        h = W1[best][1]
        # joined with a closing of SLIVER / 2: a gap narrower than SLIVER between the strip and its wall is the wall (a notch of
        # the wall's fill around a strip drawn into it would otherwise stay as a saw of slits)
        u = unary_union([h.buffer(SLIVER / 2, join_style=2), g.buffer(SLIVER / 2, join_style=2)]).buffer(-SLIVER / 2, join_style=2)
        if u.geom_type == 'Polygon':
            places['thin joined'].append(dict(cls=c, to=W1[best][0], at=[round(v, 1) for v in g.representative_point().coords[0]]))
            W1[best][1] = u; W1[i][1] = None; rep[f'thin strip joined its wall ({c} -> {W1[best][0]})'] += 1; continue
    if GBU is not None and g.buffer(mm(TOUCH_MM)).intersection(GBU.boundary).length >= 0.5 * half:
        places['thin along glass'].append(dict(cls=c, at=[round(v, 1) for v in g.representative_point().coords[0]]))
        W1[i][1] = None; rep['thin strip along glass dropped'] += 1
# d) a small body (< SMALL) of a wall class touching a body of the same class at least 3 times bigger: a piece or a mark drawn
#    into the wall (a wedge, a triangle of a wall panel) — it is that wall: joined, and the notch of the wall's fill around it is
#    closed (a closing of half the piece's size, only around the piece), so the face goes straight past it (ПЗ-2, З-1.1)
SMALL = 0.01e6 / (K * K)
W1 = [[c, g] for c, g in W1 if g is not None]
tree = shapely.STRtree([g for c, g in W1])
for i, (c, g) in enumerate(W1):
    if c == 'column' or g is None or g.area >= SMALL: continue
    hosts = [j for j in tree.query(g.buffer(mm(NEAR_MM))) if j != i and W1[j][1] is not None and W1[j][0] == c
             and W1[j][1].area >= 3 * g.area and W1[j][1].distance(g) <= mm(NEAR_MM)]
    if not hosts: continue
    j = max(hosts, key=lambda q: W1[q][1].area); h = W1[j][1]
    m_ = g.minimum_rotated_rectangle; xs = list(m_.exterior.coords)
    r = max(SLIVER, max(RG.dist(xs[0], xs[1]), RG.dist(xs[1], xs[2])) / 2)
    u0 = unary_union([h.buffer(mm(JOIN_SMALL_MM), join_style=2), g.buffer(mm(JOIN_SMALL_MM), join_style=2)]).buffer(-mm(JOIN_SMALL_MM), join_style=2)
    cl = u0.buffer(r, join_style=2).buffer(-r, join_style=2).intersection(g.buffer(2 * r, join_style=2))
    u = unary_union([u0, cl]).buffer(mm(JOIN_SMALL_MM), join_style=2).buffer(-mm(JOIN_SMALL_MM), join_style=2)
    if u.geom_type != 'Polygon' or len(u.interiors) > len(h.interiors): continue
    places['small piece joined its wall'].append(dict(cls=c, at=[round(v, 1) for v in g.representative_point().coords[0]],
                                                      mm2=round(g.area * K * K), closed_mm2=round((u.area - h.area - g.area) * K * K)))
    W1[j][1] = u; W1[i][1] = None; rep[f'small piece joined its wall ({c})'] += 1
# e) one place — one type (ПЗ-4, З-1.1): where bodies of two classes overlap, the overlap is the stronger class's (a column, then
#    an outer wall, a capital wall, a block partition, GKL): the weaker body is cut by the stronger one; its slivers go
RANK = {'column': 6, 'ext': 5, 'cap': 4, 'blk': 3, 'gkl': 2}          # «самый основной слой»: наружная > капитальная > штучная > ГКЛ
                                                                       # (к ОЧ-86, В9-1 клиент А 4; колонна — сама по себе)
def cut_overlaps(WL, stage):
    WL = [[c, g] for c, g in WL if g is not None]
    tr = shapely.STRtree([g for c, g in WL])
    for i in range(len(WL)):
        for j in tr.query(WL[i][1]):
            if j <= i or WL[i][1] is None or WL[j][1] is None or WL[i][0] == WL[j][0]: continue
            a, b = (i, j) if RANK.get(WL[i][0], 0) < RANK.get(WL[j][0], 0) else (j, i)        # a — the weaker
            x = WL[a][1].intersection(WL[b][1])
            if x.area * K * K / 1e6 <= 0.0005: continue
            rest = WL[a][1].difference(WL[b][1])
            rest = rest.buffer(-SLIVER / 2, join_style=2).buffer(SLIVER / 2, join_style=2).intersection(rest)
            parts = [q for q in getattr(rest, 'geoms', [rest]) if q.geom_type == 'Polygon' and q.area > mm2(BIT_MM2)]
            parts = [Polygon(RG.clean_ring(list(q.exterior.coords)), [RG.clean_ring(list(h.coords)) for h in q.interiors]) for q in parts]
            parts = [q if q.is_valid else q.buffer(0) for q in parts]
            places['overlap cut (one place — one type)'].append(dict(stage=stage, weak=WL[a][0], strong=WL[b][0],
                                                                     at=[round(v, 1) for v in x.representative_point().coords[0]], mm2=round(x.area * K * K)))
            rep[f'overlap cut ({WL[a][0]} by {WL[b][0]}, {stage})'] += 1
            WL[a][1] = parts[0] if parts else None
            for q in parts[1:]: WL.append([WL[a][0], q])
    return [(c, g) for c, g in WL if g is not None]
W1 = cut_overlaps(W1, 'source')
W1 = [(c, g) for c, g in W1 if g is not None]
WU = unary_union([g for c, g in W1 if c != 'column'])
for k, bs in GB.items():
    nb = []
    for b in bs:
        b2 = b.difference(WU) if b.intersects(WU) else b
        for q in getattr(b2, 'geoms', [b2]):
            if q.geom_type == 'Polygon' and q.area > mm2(PIECE_MM2) and not q.buffer(-SLIVER / 2).is_empty: nb.append(q)
    if sum(q.area for q in nb) < sum(b.area for b in bs) - 1e-6: rep['glass bands cut by walls'] += 1     # 1e-6 pt²: the float tolerance of a sum, not a threshold
    GB[k] = nb
print('walls', len(W), '->', len(W1), dict(rep), T())
# ------------------------------------------------------------------------------------------------ 3. face lines
FL = RG.FaceLines()
edges = []
for k, (c, g) in enumerate(W1):
    edges += RG.face_edges(g, ('w', k))
for k, bs in GB.items():
    for j, b in enumerate(bs): edges += RG.face_edges(b, ('g', k, j))
CORE = [k for k, o in enumerate(objs) if o['key'] == 'coreblock']
for k in CORE:
    for i in objs[k]['ids']:
        p = P[i]
        if p['kind'] == 'fill' and len(p['p']) >= 3:
            g = Polygon(p['p'], p.get('holes', [])).buffer(0)
            if g.geom_type == 'Polygon': edges += RG.face_edges(g, ('c', i))
for o in objs:                         # the precise source lines of the glass partitions
    if o['key'] in ('glass', 'lpart'):
        for i in o['ids']:
            p = P[i]
            if p['kind'] == 'line':
                for a, b in zip(p['p'][:-1], p['p'][1:]): edges.append((tuple(a), tuple(b), ('l', i), None))
# the openings of the doors (Э7о: a closed rectangle as thick as its wall) pin their lines: the faces of the wall at a door and
# its jambs stay where the opening is (doors_fit: a door fits its opening within 10 mm; a face line moved by up to TOL would put
# the door off its opening)
PINS = set(); nop = 0
for k, o in enumerate(objs):
    if o['key'] != 'door' or not o['ids']: continue
    for i in o.get('draw', o['ids']):
        p = P[i]
        if p.get('synthetic') and p['kind'] == 'line' and len(p['p']) == 5 and RG.dist(p['p'][0], p['p'][-1]) < 1e-6:
            g = Polygon(p['p'][:-1])
            if g.is_valid and g.area > 0:
                edges += RG.face_edges(g, ('d', k)); PINS.add(('d', k)); nop += 1
            break
FL.add_edges(edges, pins=PINS)
print('face lines', len(FL.L), 'from', len(edges), 'edges; door openings pinned', nop, T())
# objects drawn over a wall (a wall screen): a recess of the wall face under one is the wall itself (З-4)
COVER = unary_union([Polygon(P[i]['p'], P[i].get('holes', [])).buffer(0) for o in objs if o['key'] == 'equip'
                     for i in o['ids'] if P[i]['kind'] == 'fill' and len(P[i]['p']) >= 3])
st = collections.Counter()
W2 = []
for wi, (c, g) in enumerate(W1):
    if c == 'column':
        r = RG.rectangle_of(g, RG.TOL)
        if r is not None and nverts(g) > 4: rep['columns made rectangles'] += 1; W2.append((c, r))
        else:
            cl = Polygon(RG.clean_ring(list(g.exterior.coords)), [RG.clean_ring(list(h.coords)) for h in g.interiors])
            W2.append((c, cl if cl.is_valid else g))
        continue
    ng, s = RG.regularize_polygon(g, FL, cover=COVER, pid=('w', wi))
    if s.get('fallback') or s.get('fallback_poly'):
        # a ring that cannot be cleaned: its slits and saws narrower than SLIVER closed first (area within 1 %), then again
        gc = g.buffer(SLIVER / 2, join_style=2).buffer(-SLIVER / 2, join_style=2)
        if gc.geom_type == 'Polygon' and abs(gc.area - g.area) <= 0.01 * g.area:
            ng2, s2 = RG.regularize_polygon(gc, FL, cover=COVER, pid=('w', wi))
            if not (s2.get('fallback') or s2.get('fallback_poly')):
                ng, s = ng2, s2; s['closed slits first'] = 1
    st.update({c + ':' + k_: v for k_, v in s.items()}); W2.append((c, ng))
    if s.get('fallback') or s.get('fallback_poly'): places['fallback'].append(dict(cls=c, at=[round(v, 1) for v in g.representative_point().coords[0]], rings=s.get('fallback', 0), poly=s.get('fallback_poly', 0)))
W2 = cut_overlaps(W2, 'cleaned')
for k, bs in GB.items():
    nb = []
    for j, b in enumerate(bs):
        nb_, s = RG.regularize_polygon(b, FL, pid=('g', k, j)); st.update({'glass:' + k_: v for k_, v in s.items()})
        r = RG.rectangle_of(nb_, RG.TOL)
        nb.append(r if r is not None else nb_)
    GB[k] = nb
print('regularized', dict(st), T())
# glass objects: one fill and one closed outline per band (same points) instead of the source fill and its open lines
for k, bs in GB.items():
    o = objs[k]; sq = min((P[i]['seq'] for i in o['ids']), default=0)
    fcol = next((P[i]['col'] for i in o['ids'] if P[i]['kind'] == 'fill'), (0.0, 0.0, 1.0))
    falpha = next((P[i].get('alpha', 1.0) for i in o['ids'] if P[i]['kind'] == 'fill'), 0.5)
    lcol = next((P[i]['col'] for i in o['ids'] if P[i]['kind'] == 'line'), (0.0, 0.0, 0.0))
    v0 = sum(len(P[i]['p']) for i in o['ids'])
    ids = []
    for b in bs:
        ring = RG.clean_ring(list(b.exterior.coords))
        ids.append(new_prim(P[o['ids'][0]]['layer'], 'fill', ring, fcol, alpha=falpha, seq=sq))
        ids.append(new_prim(P[o['ids'][0]]['layer'], 'line', ring + [ring[0]], lcol, seq=sq, closed=True))
    ids += GKEEP.get(k, [])
    o['ids_src'] = list(o['ids']); o['ids'] = ids
    rep['glass objects as bands'] += 1; st['glass points before'] += v0; st['glass points after'] += sum(len(P[i]['p']) for i in ids)
# core blocks: their fill rings on the face lines
for k in CORE:
    for i in objs[k]['ids']:
        p = P[i]
        if p['kind'] == 'fill' and len(p['p']) >= 3:
            g = Polygon(p['p'], p.get('holes', [])).buffer(0)
            if g.geom_type != 'Polygon': continue
            ng, s = RG.regularize_polygon(g, FL); st.update({'core:' + k_: v for k_, v in s.items()})
            old = g.exterior
            p['p'] = RG.clean_ring(list(ng.exterior.coords)); p['holes'] = [RG.clean_ring(list(h.coords)) for h in ng.interiors]
            # the closed outline line that traces this fill — the same points (one contour, one set of points; ПЗ-2)
            for j in objs[k]['ids']:
                q = P[j]
                if q['kind'] != 'line' or len(q['p']) < 4 or RG.dist(q['p'][0], q['p'][-1]) > mm(NEAR_MM): continue
                if LineString(q['p']).hausdorff_distance(old) <= mm(NEAR_MM):
                    q['p'] = list(p['p']) + [p['p'][0]]; st['core: outline line = fill'] += 1
# ------------------------------------------------------------------------------------------------ 4. massive furniture
def orthogonal(ring, tol_deg=3.0):
    """a rectilinear ring (every edge within tol of the main axis or across it) with exact right angles"""
    g = Polygon(ring); m = g.minimum_rotated_rectangle; xs = list(m.exterior.coords)
    ax = math.atan2(xs[1][1] - xs[0][1], xs[1][0] - xs[0][0])
    n = len(ring); L = []
    for k in range(n):
        a, b = ring[k], ring[(k + 1) % n]; th = math.atan2(b[1] - a[1], b[0] - a[0])
        d = (th - ax) % (math.pi / 2)
        dev = math.degrees(min(d, math.pi / 2 - d))
        if dev > tol_deg: return None
        q = round((th - ax) / (math.pi / 2)); th2 = ax + q * math.pi / 2
        L.append((((a[0] + b[0]) / 2, (a[1] + b[1]) / 2), (math.cos(th2), math.sin(th2))))
    out = []
    for k in range(n):
        q = RG._isect(L[k - 1], L[k])
        if q is None: return None
        out.append(q)
    out = RG.clean_ring(out)
    return out if RG.ring_ok(ring, out, TOL_F) else None
# З-8 (owner 09.10.2026: «Тут срезался угол массивной мебели.»): the габарит outline covers every part of the item. A source fill
# of the item that touches its outline and sticks out of it by more than COVER_A, within the outline's rectangle (it fills a cut
# corner or a notch of the outline, it is not a new protrusion: a chair back at a desk lies outside the desk's rectangle), — the
# outline grows to it. Spikes and hairs thinner than 2·SPIKE (a line of the outline running out to a corner and back) are opened
# away when that changes the area by less than 2 %. A rectangle outline is the item's type figure (one size for one type of desk,
# Т10.7) — it does not grow; the part that sticks out is thicker than 2·SPIKE (not a hair of the drawing).
COVER_A = mm2(461.56832); SPIKE = mm(7.206)            # 461.6 mm² (v010: 0.2 pt²); 7.2 mm (v010: 0.15 pt)
def opened(g):
    u = g.buffer(-SPIKE, join_style=2).buffer(SPIKE, join_style=2)
    if u.is_empty: return None
    if u.geom_type != 'Polygon': u = max(getattr(u, 'geoms', [u]), key=lambda q: q.area)
    u = Polygon(u.exterior)
    return u if u.is_valid and abs(u.area - g.area) <= 0.02 * g.area else None
def grow_to_parts(o, g):
    box_ = g.minimum_rotated_rectangle.buffer(mm(BOX_MM), join_style=2); add = []
    for i in o['ids']:
        p = P[i]
        if p.get('synthetic') or p['kind'] != 'fill' or len(p['p']) < 3: continue
        f = Polygon(p['p'], p.get('holes', [])).buffer(0)
        if f.is_empty or f.distance(g) > mm(NEAR_MM): continue
        out_ = f.difference(g)
        if out_.area <= COVER_A or not box_.covers(out_) or out_.buffer(-SPIKE, join_style=2).is_empty: continue
        add.append(f)
    if not add: return None
    u = unary_union([g] + [f.buffer(mm(JOIN_MM), join_style=2) for f in add]).buffer(-mm(JOIN_MM), join_style=2)
    if u.geom_type != 'Polygon': u = max(getattr(u, 'geoms', [u]), key=lambda q: q.area)
    u = Polygon(u.exterior); u2 = opened(u)
    return u2 if u2 is not None else u
fst = collections.Counter()
for k, o in enumerate(objs):
    if o['key'] not in MASSIVE or not o.get('outline'): continue
    ids = o['outline']; ring0 = [tuple(v) for v in P[ids[0]]['p']]
    if len(ring0) < 3: continue
    c = RG.clean_ring(ring0)
    g = Polygon(c)
    if not g.is_valid or g.area <= 0: fst['outline invalid (kept)'] += 1; continue
    gg = grow_to_parts(o, g) if len(c) != 4 else None
    if gg is not None and gg.is_valid and gg.area > g.area:
        places['outline grown to its parts (З-8)'].append(dict(key=o['key'], at=[round(v, 1) for v in g.centroid.coords[0]],
                                                              mm2=round((gg.area - g.area) * K * K)))
        g = gg; c = RG.clean_ring(list(g.exterior.coords)); fst['grown to its parts (З-8)'] += 1
    else:
        go = opened(g)
        if go is not None and go.exterior.hausdorff_distance(g.exterior) > mm(NEAR_MM):
            g = go; c = RG.clean_ring(list(g.exterior.coords)); fst['spike opened'] += 1
    LF = RG.FaceLines(tol=TOL_F, ang=1.0, min_len=40 * MM); LF.add_edges(RG.face_edges(g, ('f', k)))
    r1, s = RG.regularize_ring(RG.clean_ring(list(RG.oriented(g).exterior.coords)), LF, TOL_F)
    new = r1 if RG.ring_ok(c, r1, TOL_F) else c
    rr = RG.rectangle_of(Polygon(new), TOL_F)
    if rr is not None: new = RG.clean_ring(list(rr.exterior.coords)); fst['rectangle'] += 1
    else:
        og = orthogonal(new)
        if og is not None: new = og; fst['right angles'] += 1
        else: fst['cleaned'] += 1
    if len(new) < len(ring0) - (1 if ring0[0] == ring0[-1] else 0) or rr is not None:
        places['furniture'].append(dict(key=o['key'], at=[round(v, 1) for v in g.centroid.coords[0]], before=len(ring0), after=len(new)))
    fst['points before'] += len(ring0); fst['points after'] += len(new)
    for j, i in enumerate(ids[:2]):
        P[i]['p'] = list(new) + ([new[0]] if P[i]['kind'] == 'line' else [])
print('massive furniture outlines', dict(fst), T())
# ------------------------------------------------------------------------------------------------ write
WD2 = dict(WD); WD2['bodies'] = W2
pickle.dump(WD2, open('walls_r.pkl', 'wb'))
D2 = dict(D); D2['P'] = P; pickle.dump(D2, open('prims_r.pkl', 'wb'))
pickle.dump(O, open('objects.pkl', 'wb'))
vb = sum(nverts(g) for c, g in W); va = sum(nverts(g) for c, g in W2)
res = dict(report=dict(rep), regularize=dict(st), furniture=dict(fst), wall_points_before=vb, wall_points_after=va,
           face_lines=len(FL.L), tol_mm=round(RG.TOL * K, 1), junction_mm=[round(RG.JUNC_L * K), round(RG.JUNC_R * K)],
           sliver_mm=round(SLIVER * K), places={k: v for k, v in places.items()})
res['places']['junction and recess'] = [dict(kind=k_, at=[round(v, 1) for v in c_], mm2=round(a_ * K * K)) for k_, c_, a_ in RG.LOG]
json.dump(res, open('regular.json', 'w'), ensure_ascii=False, indent=1)
print('wall points', vb, '->', va, '| glass', st['glass points before'], '->', st['glass points after'], T())
