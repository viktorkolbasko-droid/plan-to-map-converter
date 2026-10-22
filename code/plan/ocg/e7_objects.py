"""Э7: objects of the layered AutoCAD sheet. Every primitive goes to exactly one owner: a wall body (its own drawing:
hatch, layer lines, marks inside the body) or an object. Objects are built per source layer (route by OCG layers):
 - wall layers outside the bodies: glass panes (blue/cyan fills + their lines), lines along a body (<= 0.6 pt, parallel):
   wall lines of that body's class; the rest: partitions without hatch (A-22G), components;
 - «Стены»: columns and filled wall ends — bodies (Э6); its lines and thin fills: outline of the core walls (A-221);
 - «Узлы»: strokes — core zone (A-92); grey fills — built-in counters (A-76); «Линии» touching a counter go to it,
   the rest — core zone outline (A-92); «Контур» — core shafts (A-92);
 - doors: parts within 1 pt of each other (arc, leaf, jambs) — one door; name by the arc radius (A-32);
 - fire cabinets, equipment, sanitary, generic models (sinks), heating, lifts, facade, rooms, separators, tags, dims,
   axes, marks — clusters of their layer;
 - furniture: desks = rectangular grey fills 1150-2150 x 500-950 mm with the lines inside them; the rest — components
   (touching <= 0.05 pt); plant leaves («09 FURNITURE_1») join the pot they lie in; raster patches join the object they
   overlap. Names of furniture groups — e7_names.py (catalogue).
Writes objects.pkl: dict(objs=[dict(key, layer, name, ids, kind)], owner={prim id: obj index or 'wall:k'})."""
import pickle, numpy as np, collections, shapely, math, time, sys
from shapely.geometry import LineString, Polygon, Point, box
from shapely.ops import unary_union
import os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import sheet; from e7_comp import geom
t0 = time.time(); K = sheet.K
def T(): return f'{time.time() - t0:.1f} s'
import os
# test 7: the primitives and the walls after Э6в (cleanup) and Э6г (doors, niches) — prims_geom.pkl, walls_geom.pkl
PSRC = 'prims_geom.pkl' if os.path.exists('prims_geom.pkl') else 'prims.pkl'
WSRC = next(f for f in ('walls_geom.pkl', 'walls_clean.pkl', 'walls.pkl') if os.path.exists(f))
D0 = pickle.load(open(PSRC, 'rb')); P = D0['P']
W = pickle.load(open(WSRC, 'rb')); B = W['bodies']
print('sources', PSRC, WSRC)
WALL_L = sheet.L('wall'); GLASS = sheet.GLASS; CORE_L = sheet.L('core')     # layers by role: cfg.OCG_LAYERS (ocg/sheet.py)
# owner 06.10.2026: one element — one class. A wall-layer polyline that runs along a glass pane for a part of its length
# and along something else for the rest (a casing outline that goes on as the lower edge of a glass partition, desks 93–94)
# is split: each run is its own primitive, the run along the glass (>= 80 % of each segment within 0.4 pt of a pane, >= 2 pt)
# then goes to the glass, the rest to its wall. New pieces are appended (id = index, src_id = the original); the original
# becomes kind 'removed'. The primitives as classified are written to prims_e7.pkl — e7_blocks, e8 and the checks read it.
def split_mixed():
    """owner 06.10.2026, one element — one class: a wall-layer polyline is cut into runs by what each segment lies on —
    a glass pane (>= 80 % within 0.4 pt), a wall body (>= 80 % inside or within 0.1 pt of one) or nothing (free);
    runs shorter than 1.5 pt join the neighbour run; a polyline with >= 2 runs becomes its runs (new primitives,
    src_id = the original, the original kind 'removed')"""
    gp = [geom(p) for p in P if p['kind'] != 'removed' and p['layer'] in WALL_L and p['kind'] in ('fill', 'wline') and p['col'] in GLASS]
    gp = [g for g in gp if not g.is_empty]
    GBu = unary_union([g.buffer(0.4) for g in gp]) if gp else Polygon()
    BBu = unary_union([g.buffer(0.1) for _, g in B])
    gpp_, bpp_ = shapely.prepared.prep(GBu), shapely.prepared.prep(BBu)
    n0 = len(P); ns = collections.Counter()
    for i in range(n0):
        p = P[i]
        if p['layer'] not in WALL_L | CORE_L or p['kind'] != 'line' or len(p['p']) < 3: continue
        q = [tuple(map(float, xy)) for xy in p['p']]; ls = LineString(q)
        if not (gpp_.intersects(ls) or bpp_.intersects(ls)): continue
        lab = []; sl = []
        for a_, b_ in zip(q[:-1], q[1:]):
            L = math.dist(a_, b_); sl.append(L); seg = LineString([a_, b_])
            if L <= 0: lab.append(None); continue
            if gpp_.intersects(seg) and seg.intersection(GBu).length >= 0.8 * L: lab.append('glass')
            elif bpp_.intersects(seg) and seg.intersection(BBu).length >= 0.8 * L: lab.append('body')
            else: lab.append('free')
        runs = []
        for k, (f, L) in enumerate(zip(lab, sl)):
            if runs and (runs[-1][0] == f or f is None): runs[-1][2] = k; runs[-1][3] += L
            else: runs.append([f, k, k, L])
        changed = True
        while changed and len(runs) > 1:                       # short runs join the longer neighbour
            changed = False
            for r in range(len(runs)):
                if runs[r][3] < 1.5:
                    nb = [x for x in (r - 1, r + 1) if 0 <= x < len(runs)]; t_ = max(nb, key=lambda x: runs[x][3])
                    lo, hi = sorted((r, t_)); runs[lo] = [runs[t_][0], runs[lo][1], runs[hi][2], runs[lo][3] + runs[hi][3]]; del runs[hi]
                    changed = True; break
            if not changed:
                for r in range(len(runs) - 1):
                    if runs[r][0] == runs[r + 1][0]:
                        runs[r] = [runs[r][0], runs[r][1], runs[r + 1][2], runs[r][3] + runs[r + 1][3]]; del runs[r + 1]; changed = True; break
        if len(runs) < 2: continue
        for f, a_, b_, _ in runs:
            r = dict(p); r['p'] = q[a_:b_ + 2]; r['id'] = len(P); r['src_id'] = p.get('src_id', i); P.append(r)
        p['kind'] = 'removed'; ns[tuple(sorted(set(r[0] for r in runs)))] += 1
    return dict(ns)
print('wall-layer polylines split into runs by host (glass / body / free)', split_mixed(), T())
G = {}
def g_of(i):
    if i not in G: G[i] = geom(P[i])
    return G[i]
objs = []; owner = {}
def new(key, layer, name, ids, kind='obj'):
    k = len(objs); objs.append(dict(key=key, layer=layer, name=name, ids=list(ids), kind=kind))
    for i in ids: owner[i] = k
    return k
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
def dims_mm(ids):
    u = unary_union([g_of(i) for i in ids]); r = u.minimum_rotated_rectangle
    if r.geom_type != 'Polygon': L = r.length; return round(L * K), 0
    c = np.array(r.exterior.coords); a = np.linalg.norm(c[1] - c[0]); b = np.linalg.norm(c[2] - c[1])
    return round(max(a, b) * K), round(min(a, b) * K)
by_layer = collections.defaultdict(list)
for p in P:
    if p['kind'] != 'removed': by_layer[p['layer']].append(p['id'])
# ---------------- walls: what lies inside the bodies is the wall's own drawing
BL = [g for _, g in B]; bt = shapely.STRtree(BL); BU = unary_union(BL); bpp = shapely.prepared.prep(BU.buffer(0.06))
BLB = [b.buffer(0.06) for b in BL]; BRB = [b.boundary.buffer(0.6) for b in BL]; f1_n = [0]
def dissolve(g):                      # a there-and-back polyline counts once
    u = shapely.line_merge(unary_union(g)) if g.geom_type in ('LineString', 'MultiLineString') else g
    return u if not u.is_empty else g
wall_in = collections.defaultdict(list); rest_w = []
for L in WALL_L | CORE_L:
    for i in by_layer[L]:
        p = P[i]
        if L in CORE_L and p['kind'] == 'fill' and max(p['col']) < 0.05:
            g = g_of(i); js = [j for j in bt.query(g) if B[j][0] in ('column', 'cap') and B[j][1].buffer(0.05).covers(g.representative_point())]
            if js: wall_in[js[0]].append(i); continue
        g = g_of(i)
        # owner 06.10.2026 (one element — one class): a «Стены» line along the outline of a column or a filled wall end
        # (>= 80 % within 0.4 pt of it) is that body's outline, not a separate core-wall line
        if L in CORE_L and p['kind'] == 'line' and g.length > 0:
            js = [j for j in bt.query(g.buffer(0.4)) if B[j][0] in ('column', 'cap')]
            if js and g.intersection(unary_union([BL[j].boundary.buffer(0.4) for j in js])).length >= 0.8 * g.length:
                wall_in[max(js, key=lambda j: g.intersection(BL[j].boundary.buffer(0.4)).length)].append(i); continue
        if bpp.contains(g if p['kind'] != 'fill' else g.representative_point()):
            j = next((j for j in bt.query(g.representative_point().buffer(0.06)) if BL[j].distance(g.representative_point()) <= 0.06), None)
            if j is not None: wall_in[j].append(i); continue
        if p['kind'] == 'line' and g.length > 0:      # test 6: >= 90 % of the length inside (hatch strokes stick out 0.1-0.2 pt
            gu = dissolve(g); sh = {j: gu.intersection(BLB[j]).length for j in bt.query(gu)}   # at a slanted outline)
            sh = {j: v for j, v in sh.items() if v > 0}
            if sh and gu.intersection(unary_union([BLB[j] for j in sh])).length >= 0.9 * gu.length:
                wall_in[max(sh, key=sh.get)].append(i); f1_n[0] += 1; continue
        rest_w.append(i)
for j, ids in wall_in.items():
    for i in ids: owner[i] = f'wall:{j}'
print('wall-layer primitives inside bodies', sum(len(v) for v in wall_in.values()), 'of them >= 90 % inside', f1_n[0], 'outside', len(rest_w), T())
# glass panes: blue/cyan fills and wlines of the wall layers, with lines of the wall layers that lie on their outline
glass = [i for i in rest_w if P[i]['kind'] in ('fill', 'wline') and P[i]['col'] in GLASS]
other = [i for i in rest_w if i not in set(glass)]
gu = unary_union([g_of(i).buffer(0.15) for i in glass]) if glass else Polygon(); gpp = shapely.prepared.prep(gu)
GB = [g_of(i).buffer(0.4) for i in glass]; gbt = shapely.STRtree(GB) if GB else None
def near_glass(i):                     # test 6: a pane outline drawn 0.25 pt off its fill (tile 10) is the pane's outline
    if gbt is None or P[i]['kind'] != 'line': return False
    gu = dissolve(g_of(i))
    if gu.length <= 0: return False
    js = gbt.query(gu)
    return len(js) > 0 and gu.intersection(unary_union([GB[j] for j in js])).length >= 0.8 * gu.length
gl_lines = [i for i in other if P[i]['layer'] in WALL_L and (gpp.contains(g_of(i)) or near_glass(i))]
gs_ = set(gl_lines)
for c in comps(glass + gl_lines, 0.15):
    new('glass', 'A-22G', 'Перегородка стеклянная: остекление (по исходнику)', c)
other = [i for i in other if i not in gs_]
# lines along a body (finish, second outline): <= 0.6 pt from the body outline, parallel
cls_of = {j: c for j, (c, _) in enumerate(B)}
LAY = {'gkl': 'A-222', 'blk': 'A-223', 'cap': 'A-221', 'column': 'A-28', 'ext': 'A-21'}
wl = collections.defaultdict(list); rest2 = []
for i in other:
    p = P[i]
    if p['layer'] in CORE_L: rest2.append(i); continue
    g = g_of(i); m = g.interpolate(0.5, normalized=True) if g.geom_type == 'LineString' else g.representative_point()
    js = [j for j in bt.query(m.buffer(0.6)) if BL[j].exterior.distance(m) <= 0.6 or any(h.distance(m) <= 0.6 for h in BL[j].interiors)]
    ok = None
    if js and p['kind'] == 'line' and len(p['p']) >= 2:
        # test 6: the direction is that of the segment holding the middle of the length, and only if that segment carries
        # >= 25 % of the length (the end-to-end vector of a polyline means nothing: a pane outline went to a wall, tile 10)
        q = np.array(p['p']); sl = np.hypot(*(q[1:] - q[:-1]).T); cs = np.cumsum(sl); km = int(np.searchsorted(cs, cs[-1] / 2))
        km = min(km, len(sl) - 1); u = q[km + 1] - q[km] if sl[km] >= 0.25 * cs[-1] else np.zeros(2); Lq = np.linalg.norm(u)
        if Lq > 0:
            u = u / Lq; j = js[0]; ring = BL[j].exterior if BL[j].exterior.distance(m) <= 0.6 else min(BL[j].interiors, key=lambda h: h.distance(m))
            d = ring.project(m); a = ring.interpolate(max(0, d - 0.2)); b = ring.interpolate(min(ring.length, d + 0.2))
            v = np.array(b.coords[0]) - np.array(a.coords[0])
            if np.linalg.norm(v) > 0 and abs(u @ (v / np.linalg.norm(v))) > math.cos(math.radians(10)): ok = j
    elif js and p['kind'] in ('fill', 'wline'): ok = js[0]
    if ok is None and p['kind'] == 'line' and g.length > 0:   # tests 5-6: polyline along the outlines (casing contour, wall + column)
        gu = dissolve(g); sh = {j: gu.intersection(BRB[j]).length for j in bt.query(gu.buffer(0.6))}
        sh = {j: v for j, v in sh.items() if v > 0}       # along the outlines of all bodies together, once; owner: the longest share
        if sh and gu.intersection(unary_union([BRB[j] for j in sh])).length >= 0.6 * gu.length: ok = max(sh, key=sh.get)
    if ok is not None: wl[ok].append(i)
    else: rest2.append(i)
# owner 06.10.2026: a wall is a closed polygon, never a line. A line along a body (finish, second outline, <= 0.6 pt off
# its outline, parallel) is the body's outer face: the strip between the line and the body joins the body (each segment,
# cut every 2 pt, to its nearest points on the body outline when both ends are <= 0.7 pt from it); the line is the body's own.
from shapely.ops import nearest_points
absorbed = collections.Counter(); grown = 0.0; Bg = {j: g for j, (_, g) in enumerate(B)}
for j, ids in wl.items():
    body = Bg[j]; ring = body.boundary; strips = []
    for i in ids:
        p = P[i]
        if p['kind'] != 'line' or len(p['p']) < 2:
            wall_in[j].append(i); absorbed['fill'] += 1; continue
        q = np.array(p['p'], float); pts = [q[0]]
        for a_, b_ in zip(q[:-1], q[1:]):
            n_ = max(1, int(np.linalg.norm(b_ - a_) / 2.0))
            pts += [a_ + (b_ - a_) * t for t in np.linspace(0, 1, n_ + 1)[1:]]
        for a_, b_ in zip(pts[:-1], pts[1:]):
            pa = np.array(nearest_points(ring, Point(a_))[0].coords[0]); pb = np.array(nearest_points(ring, Point(b_))[0].coords[0])
            if np.linalg.norm(pa - a_) > 0.7 or np.linalg.norm(pb - b_) > 0.7: continue
            sq = Polygon([tuple(a_), tuple(b_), tuple(pb), tuple(pa)]).buffer(0)
            if sq.area > 1e-5: strips.append(sq)
        wall_in[j].append(i); absorbed['line'] += 1
    if strips:
        add = unary_union(strips).difference(body)
        if add.area > 1e-4: Bg[j] = body.union(add.buffer(0.005, join_style=2)).buffer(-0.005, join_style=2).union(body); grown += add.area
for j, ids in wl.items():
    for i in ids: owner[i] = f'wall:{j}'
B = [(c, Bg[j]) for j, (c, _) in enumerate(B)]
print('lines along bodies joined to their bodies (walls are polygons)', dict(absorbed), '| body area grown', round(grown, 2), 'pt2', T())
# «Стены» lines and thin fills — outline of the core walls and shafts
st_lines = [i for i in rest2 if P[i]['layer'] in CORE_L]
for c in comps(st_lines, 0.05):
    new('coreline', 'A-221', 'Контур капитальных стен ядра (линии по исходнику)', c)
rest3 = [i for i in rest2 if P[i]['layer'] not in CORE_L]
# partitions without hatch: components of the remaining wall-layer primitives
for c in comps(rest3, 0.7):
    L, Wd = dims_mm(c)
    name = 'Перегородка без штриховки (по исходнику)' if L >= 300 else 'Перегородка без штриховки — деталь (торец, стойка, по исходнику)'
    new('lpart', 'A-22G', name, c)
print('glass', sum(1 for o in objs if o['key'] == 'glass'), '| wall lines', sum(1 for o in objs if o['key'] == 'wallline'),
      '| core outlines', sum(1 for o in objs if o['key'] == 'coreline'), '| partitions w/o hatch', sum(1 for o in objs if o['key'] == 'lpart'), T())
# ---------------- core: «Узлы», «Линии», «Контур»
uz = sheet.ids_of(by_layer, 'core_hatch')
cnt_f = [i for i in uz if P[i]['kind'] == 'fill']; uz_l = [i for i in uz if P[i]['kind'] != 'fill']
li = sheet.ids_of(by_layer, 'core_lines')
counters = comps(cnt_f, 0.3)
cu = [unary_union([g_of(i) for i in c]) for c in counters]
ct = shapely.STRtree(cu) if cu else None
cmem = [list(c) for c in counters]; core_l = []
for i in li + [i for i in uz_l if P[i]['col'][0] > 0.5]:       # grey outline strokes of «Узлы» go with the counters too
    g = g_of(i); js = [j for j in ct.query(g.buffer(0.3)) if cu[j].distance(g) <= 0.3] if ct else []
    # a line belongs to a counter if it lies along it (>= 60 % of the line within 0.6 pt of the counter)
    if js and g.intersection(cu[js[0]].buffer(0.6)).length >= 0.6 * max(g.length, 1e-9): cmem[js[0]].append(i)
    else: core_l.append(i)
for c in cmem:
    L, Wd = dims_mm(c); new('counter', 'A-76', f'Стойка встроенная П-образная (серая заливка, по исходнику) {L}×{Wd}', c)
hatch_core = [i for i in uz_l if P[i]['col'][0] <= 0.5]
new('corezone', 'A-92', 'Ядро здания — штриховка зоны (по исходнику)', hatch_core, kind='zone')
# owner 06.10.2026 (the printer niche at 40.28): a line of «Линии» outside the core zone is service marking, not a wall —
# >= 50 % of its length outside the hull of the core hatch (+1 pt) -> A-AXM
_cz = unary_union([g_of(i) for i in hatch_core]).convex_hull.buffer(1.0) if hatch_core else Polygon()
_out = [i for i in core_l if g_of(i).length > 0 and g_of(i).difference(_cz).length >= 0.5 * g_of(i).length]
core_l = [i for i in core_l if i not in set(_out)]
if _out: new('mark', 'A-AXM', f'Служебная разметка: линия слоя «{sheet.L1("core_lines")}» вне ядра (не стена, решение владельца 06.10)', _out)
print('core_lines outside the core -> marking', len(_out))
new('coreline', 'A-221', f'Контур блоков ядра — линии (слой «{sheet.L1("core_lines")}», строка 150)', [i for i in core_l])   # test 5: row 150 — block outlines are A-221 lines
for c in comps(sheet.ids_of(by_layer, 'shaft'), 0.05):
    new('shaft', 'A-92', 'Шахта в ядре — контур (по исходнику)', c, kind='zone')
print('counters', len(counters), '| core hatch', len(hatch_core), '| core outlines', len(core_l), T())
# ---------------- lifts
_LIFT_L = sheet.L('lift')
lift_ids = [i for L in by_layer if L in _LIFT_L for i in by_layer[L]]
for c in comps(lift_ids, 0.3):
    L, Wd = dims_mm(c); new('lift', 'A-66', f'Лифт: кабина {L}×{Wd}' if L >= 900 else 'Лифт — деталь (по исходнику)', c)
# ---------------- doors: parts within 1 pt -> one door; arcs give radius and swing
def arc_info(ids):
    best = None
    for i in ids:
        q = np.array(P[i]['p'])
        # test 10: a closed polyline is no arc — the 4 corners of a leaf's rectangle lie on a circle (half its diagonal),
        # so a leaf drawn as a closed rectangle passed as an arc of r ≈ 500 mm and named the door by it; an arc of a door
        # is an open polyline of >= 8 points sweeping 30–200°
        if len(q) < 8 or np.allclose(q[0], q[-1]): continue
        A = np.c_[2 * q[:, 0], 2 * q[:, 1], np.ones(len(q))]; c = np.linalg.lstsq(A, (q ** 2).sum(1), rcond=None)[0]
        r2 = c[2] + c[0] ** 2 + c[1] ** 2
        if r2 <= 0: continue
        r = math.sqrt(r2); res = np.abs(np.hypot(q[:, 0] - c[0], q[:, 1] - c[1]) - r).max()
        if res > 0.3 or not (5 <= r <= 40): continue
        a = np.unwrap(np.arctan2(q[:, 1] - c[1], q[:, 0] - c[0])); sw = abs(math.degrees(a[-1] - a[0]))
        if sw < 30 or sw > 200: continue
        if best is None or r > best[0][2]: best = ((c[0], c[1], r), sw)
    return best
door_parts = comps(sheet.ids_of(by_layer, 'door'), 1.0)
nd = 0
for c in door_parts:
    arcs = []
    for i in c:
        ai = arc_info([i])
        if ai: arcs.append(ai)
    L, Wd = dims_mm(c)
    if arcs:
        rs = sorted(round(a[0][2] * K / 50) * 50 for a in arcs)
        if len(arcs) >= 2 and len(set(rs)) <= 2:
            name = f'Дверь двупольная {sum(rs[-2:])} (створки {rs[-1]}+{rs[-2]})' if rs[-1] != rs[-2] else f'Дверь двупольная {2 * rs[-1]}'
        else: name = f'Дверь однопольная {rs[-1]}'
    elif 600 <= L <= 1300 and Wd <= 130:          # test 6: an open leaf with its jamb, no arc drawn (5 doors)
        name = f'Дверь однопольная {round(L / 50) * 50} (полотно без дуги, по исходнику)'
    else: name = f'Дверь — деталь проёма: коробка, упор (по исходнику) {L}×{Wd}'
    new('door', 'A-32', name, c); nd += 1
print('doors', sum(1 for o in objs if o['key'] == 'door' and 'деталь' not in o['name']), '| door details', sum(1 for o in objs if o['key'] == 'door' and 'деталь' in o['name']), T())
# ---------------- layers made of clusters
def by_clusters(role, key, iso, namef, tol):     # every layer of the role (cfg.OCG_LAYERS), in the order of the table
    for c in comps(sheet.ids_of(by_layer, role), tol):
        Lm, Wm = dims_mm(c); new(key, iso, namef(Lm, Wm, c), c)
by_clusters('fire', 'fire', 'A-68', lambda L, W, c: 'Шкаф пожарный ПК (по исходнику)' if L >= 400 else 'Шкаф пожарный ПК — деталь', 2.5)
# code 010 (К-1): wall screens (TV panels) - furniture A-82 (owner's decision of 07.10.2026, №108, row 208; plan/rules/50 §1)
by_clusters('equipment', 'equip', 'A-82', lambda L, W, c: 'Экран настенный (ТВ-панель) с зоной обзора (по исходнику)', 1.0)
# test 6 (3.10): the drain and the tap hole of a sink are separate small paths inside its bowl (39-61 mm, 13 «sinks» out
# of range) — a cluster < 150 mm joins the cluster >= 150 mm whose hull (+1 pt) holds it
_sc = comps(sheet.ids_of(by_layer, 'sink'), 0.6); _big = [c for c in _sc if dims_mm(c)[0] >= 150]
_bh = [unary_union([g_of(i) for i in c]).convex_hull.buffer(1.0) for c in _big]
for c in _sc:
    if dims_mm(c)[0] >= 150: continue
    u = unary_union([g_of(i) for i in c]); js = [j for j, h in enumerate(_bh) if h.contains(u)]
    if js: _big[js[0]].extend(c)
    else: _big.append(c)
for c in _big:
    Lm, Wm = dims_mm(c)
    new('sink', 'A-73', f'Мойка: чаша со смесителем (по исходнику) {Lm}×{Wm}' if Lm >= 150 else 'Мойка — деталь: слив или смеситель (по исходнику)', c)
by_clusters('sanitary', 'san', 'A-74', lambda L, W, c: f'Сантехника {L}×{W}', 0.3)
by_clusters('heating', 'conv', 'A-56', lambda L, W, c: f'Конвектор {round(L / 50) * 50}×{round(W / 50) * 50}', 0.05)
by_clusters('facade_frame', 'facade', 'A-31', lambda L, W, c: 'Витраж фасадный: рама и стойки (по исходнику)', 0.05)
by_clusters('facade_glass', 'facade', 'A-31', lambda L, W, c: 'Витраж фасадный: остекление (по исходнику)', 0.05)
by_clusters('tag', 'tagc', 'A-90', lambda L, W, c: 'Марка помещения — кружок', 0.05)
by_clusters('roomsep', 'roomsep', 'A-93', lambda L, W, c: 'Граница помещения — разделитель', 0.05)
by_clusters('dim', 'dim', 'A-90', lambda L, W, c: 'Размер местный (по исходнику)', 0.3)
by_clusters('mark', 'mark', 'A-AXM', lambda L, W, c: 'Служебная метка «+» (по исходнику)', 0.05)
by_clusters('measure', 'measure', 'A-90', lambda L, W, c: f'Линия обмеров (слой «{sheet.L1("measure")}», по исходнику)', 0.05)
for c in comps(sheet.ids_of(by_layer, 'zone'), 0.05):
    new('zone', 'A-92', 'Помещение — заливка зоны (по исходнику)', c, kind='zone')
for c in comps(sheet.ids_of(by_layer, 'axis'), 0.05):
    new('axis', 'A-AX', 'Ось здания (линии и марки по исходнику)', c)
print('clusters done', collections.Counter(o['key'] for o in objs), T())
# ---------------- furniture
M = sheet.ids_of(by_layer, 'furniture')
desk = []
for i in M:
    p = P[i]
    if p['kind'] != 'fill' or abs(p['col'][0] - sheet.DESK_TOP[0]) > 0.02: continue
    g = g_of(i); r = g.minimum_rotated_rectangle
    if r.geom_type != 'Polygon' or g.area < 0.95 * r.area: continue
    c = np.array(r.exterior.coords); a = np.linalg.norm(c[1] - c[0]) * K; b = np.linalg.norm(c[2] - c[1]) * K
    L_, W_ = max(a, b), min(a, b)
    if 1150 <= L_ <= 2150 and 500 <= W_ <= 950: desk.append((i, r))
# test 6 (п. 201): a desk or table whose top is drawn in pieces (a diagonal splits the fill, a chair pushed under it cuts
# it) is found by its outline — a closed black rectangle 1150-3500 x 500-1500 mm; a round table — by the union of its
# light fills (round, 4πA/P² >= 0.85, ⌀ 600-1600 mm). Chairs around a meeting table then separate as at the desks.
dkind = {}
_dt0 = shapely.STRtree([r for _, r in desk]) if desk else None
def _free(r):
    return _dt0 is None or all(desk[j][1].intersection(r).area < 0.3 * r.area for j in _dt0.query(r))
_lfi = [i for i in M if P[i]['kind'] == 'fill' and P[i]['col'] and abs(P[i]['col'][0] - sheet.DESK_TOP[0]) <= 0.02]
mt0 = shapely.STRtree([g_of(i) for i in M]); Mi0 = np.array(M); sofas = []
_lfg = [g_of(i) for i in _lfi]; _lft = shapely.STRtree(_lfg) if _lfg else None
for i in M:
    p = P[i]
    if p['kind'] != 'line' or len(p['p']) < 5 or max(p['col'] or (0, 0, 0)) > 0.1 or math.dist(p['p'][0], p['p'][-1]) > 0.05: continue
    g = Polygon(p['p']).buffer(0)
    if g.is_empty or g.geom_type != 'Polygon': continue
    r = g.minimum_rotated_rectangle
    if r.geom_type != 'Polygon' or g.area < 0.95 * r.area: continue
    c = np.array(r.exterior.coords); a = np.linalg.norm(c[1] - c[0]) * K; b = np.linalg.norm(c[2] - c[1]) * K
    L_, W_ = max(a, b), min(a, b)
    if not (1150 <= L_ <= 3500 and 500 <= W_ <= 1500 and _free(r)): continue
    tops = [j for j in _lft.query(r) if _lfg[j].intersects(r)] if _lfg else []
    if not tops or unary_union([_lfg[j] for j in tops]).intersection(r).area < 0.5 * r.area: continue   # a top: light fill >= 50 %
    # a sofa is a closed rectangle too: its cushions' rounded corners — >= 12 arcs of one size (black paths of >= 7
    # points, sizes to 10 mm) deep inside it (>= 0.8 pt from the outline). Arcs of the chairs pushed under a meeting table
    # are of mixed sizes (<= 6 of one size on this sheet), the sofa corners 90 mm x 16-20
    arcs = collections.Counter()
    for j in mt0.query(r):
        q = P[Mi0[j]]
        if Mi0[j] == i or q['kind'] != 'line' or len(q['p']) < 7 or max(q['col'] or (0, 0, 0)) > 0.1: continue
        gq = g_of(Mi0[j])
        if not r.buffer(0.3).contains(gq) or r.exterior.distance(gq) < 0.8: continue
        rq = gq.minimum_rotated_rectangle
        if rq.geom_type == 'Polygon':
            cq = np.array(rq.exterior.coords); arcs[round(max(np.linalg.norm(cq[1] - cq[0]), np.linalg.norm(cq[2] - cq[1])) * K / 10)] += 1
    if arcs and arcs.most_common(1)[0][1] >= 12: sofas.append((i, r)); continue
    dkind[len(desk)] = 'desk' if (L_ <= 1650 and W_ <= 950) else 'mtable'; desk.append((i, r))
    _dt0 = shapely.STRtree([q for _, q in desk])
for c in comps(_lfi, 0.3):              # pieces of one top (strips, triangles of a diagonal) with gaps <= 0.6 pt
    u = unary_union([g_of(i) for i in c]).buffer(0.3).buffer(-0.3)
    if u.is_empty or u.geom_type != 'Polygon' or u.length <= 0: continue
    D = 2 * math.sqrt(u.area / math.pi) * K; r = u.minimum_rotated_rectangle
    if 4 * math.pi * u.area / u.length ** 2 >= 0.85 and 600 <= D <= 1600:
        r = u.convex_hull
        if _free(r):
            dkind[len(desk)] = 'rtable'; desk.append((max(c, key=lambda i: g_of(i).area), r))
            _dt0 = shapely.STRtree([q for _, q in desk])
    elif r.geom_type == 'Polygon' and len(c) >= 2 and u.area >= 0.9 * r.area:
        cr = np.array(r.exterior.coords); a = np.linalg.norm(cr[1] - cr[0]) * K; b = np.linalg.norm(cr[2] - cr[1]) * K
        if 1150 <= max(a, b) <= 2150 and 500 <= min(a, b) <= 950 and _free(r):
            dkind[len(desk)] = 'desk'; desk.append((max(c, key=lambda i: g_of(i).area), r))
            _dt0 = shapely.STRtree([q for _, q in desk])
print('desks by fill', sum(1 for n in range(len(desk)) if n not in dkind), '| by outline', sum(1 for v in dkind.values() if v != 'rtable'),
      '(meeting tables', sum(1 for v in dkind.values() if v == 'mtable'), ') | round tables', sum(1 for v in dkind.values() if v == 'rtable'))
dset = set(i for i, _ in desk); taken = set(dset)
for i, r in sofas:                       # test 6: sofa — its outline and everything inside it (cushions)
    rb_ = r.buffer(0.3, join_style=2); ids_ = [i] + [int(Mi0[j]) for j in mt0.query(rb_) if Mi0[j] != i and Mi0[j] not in taken and rb_.contains(g_of(Mi0[j]))]
    L_, W_ = dims_mm([i]); new('sofa', 'A-82', f'Диван {round(L_ / 50) * 50}×{round(W_ / 50) * 50}', ids_); taken.update(ids_)
mt = shapely.STRtree([g_of(i) for i in M]); Mi = np.array(M)
desk_objs = []
def sides(r):
    c = np.array(r.exterior.coords)
    if len(c) != 5: return []                    # round table: no straight sides
    c = c[:4]; return [(c[k], c[(k + 1) % 4]) for k in range(4)]
for i, r in desk:
    rb = r.buffer(0.15, join_style=2); rb2 = r.buffer(1.2, join_style=2); ids = [i]
    sd = sides(r)
    for j in mt.query(rb2):
        q = Mi[j]
        if q in taken or q == i: continue
        gq = g_of(q)
        if rb.contains(gq): ids.append(q); taken.add(q); continue
        # the desk's own outline drawn up to 1.2 pt off its fill (front edge, screen line): a line along a side,
        # >= 0.8 of that side long, both ends near the desk
        if P[q]['kind'] == 'line' and len(P[q]['p']) == 2 and rb2.contains(gq):
            a, b = np.array(P[q]['p'][0]), np.array(P[q]['p'][1]); u = b - a; Lq = np.linalg.norm(u)
            for s0, s1 in sd:
                v = s1 - s0; Ls = np.linalg.norm(v)
                if Ls > 0 and Lq >= 0.8 * Ls and abs(u @ v) / (Lq * Ls) > math.cos(math.radians(3)): ids.append(q); taken.add(q); break
    desk_objs.append(ids)
restM = [i for i in M if i not in taken]
# desk outlines drawn as polylines (a rectangle around one or two desks, up to 1.2 pt off the fill): a line that lies in
# the desks' rectangles (+1.2 pt) and runs along their sides (>= 80 % of it within 1.2 pt of a side) is the desk's own;
# it goes to the desk it overlaps most
DR = [r for _, r in desk]; DU = unary_union([r.buffer(1.2, join_style=2) for r in DR]); dup = shapely.prepared.prep(DU)
DB = unary_union([r.exterior.buffer(1.2) for r in DR]); drt = shapely.STRtree(DR); grabbed = 0
for i in restM:
    if P[i]['kind'] != 'line' or len(P[i]['p']) < 2: continue
    g = dissolve(g_of(i))                 # test 6: the divider polyline of a desk group goes there and back
    on = g.intersection(DB).length
    # a short line inside the desks (+1.2 pt) along their sides, or a long polyline (outline of a group of desks drawn
    # as one path, >= 16 pt) that runs along desk sides for >= 50 % of its length
    if not ((dup.contains(g) and on >= 0.8 * g.length) or (g.length >= 16 and on >= 0.5 * g.length)): continue
    js = list(drt.query(g.buffer(1.2)))
    if not js: continue
    j = max(js, key=lambda j: g.intersection(DR[j].buffer(1.2, join_style=2)).length)
    desk_objs[j].append(i); taken.add(i); grabbed += 1
restM = [i for i in restM if i not in taken]
print('desk outline lines taken by desks', grabbed)
F1 = sheet.ids_of(by_layer, 'plant')
# long straight lines (>= 16 pt = 770 mm, longer than any seat) are edges and screens of desk groups: they tie the chairs
# of a group into one piece; they go to the desk they run along (<= 1.5 pt), the rest is its own object
longl = [i for i in restM if P[i]['kind'] == 'line' and len(P[i]['p']) == 2 and math.dist(*P[i]['p']) >= 16]
ls_ = set(longl); restM = [i for i in restM if i not in ls_]
# test 6 (п. 201): thin strips and polylines along the desks — the front edge or screen of a whole desk group, drawn as one
# fill or one path over 2-4 desks (>= 16 pt long, <= 2 pt thin, >= 80 % within 1.5 pt of the desk sides) — are the group's
# edge, not part of a chair: chairs pushed against the edge touched it and the whole row became one «group» object
DB15 = unary_union([r.exterior.buffer(1.5) for r in DR])
def thin_long(i):
    g = g_of(i); r = g.minimum_rotated_rectangle
    if r.geom_type != 'Polygon': return g.length >= 16
    c = np.array(r.exterior.coords); a = np.linalg.norm(c[1] - c[0]); b = np.linalg.norm(c[2] - c[1])
    return max(a, b) >= 16 and min(a, b) <= 2.0
edge_grp = []
for i in restM:
    if P[i]['kind'] not in ('line', 'wline', 'fill') or not thin_long(i): continue
    g = g_of(i); gl = dissolve(g) if g.geom_type != 'Polygon' else g.exterior
    if gl.length > 0 and gl.intersection(DB15).length >= 0.8 * gl.length: edge_grp.append(i)
eg_ = set(edge_grp); restM = [i for i in restM if i not in eg_]
drect = [(n, r.buffer(1.5, join_style=2)) for n, (i, r) in enumerate(desk)]
dt = shapely.STRtree([r for _, r in drect]); edge_free = []
for i in longl:
    g = g_of(i); js = [j for j in dt.query(g) if drect[j][1].intersection(g).length >= 0.8 * g.length]
    if js: desk_objs[drect[js[0]][0]].append(i)
    else: edge_free.append(i)
# test 6 (п. 201): chairs one by one. The desk edge band (thin light fills and lines along a desk side, drawn in pieces
# between the chairs) touches every chair of a row and made the row one «group» object. Thin pieces (<= 1.6 pt across)
# parallel to a desk side within 2 pt of it are left out of the component graph; afterwards each goes back to the chair
# whose hull (+0.3 pt) holds >= 80 % of it (a stripe of the seat), the rest is the band of the desks
DSIDES = [(np.array(r.exterior.coords)[:4]) if len(r.exterior.coords) == 5 else np.array(r.exterior.coords)[:-1] for r in DR]
DB2 = unary_union([r.exterior.buffer(2.0) for r in DR]); db2p = shapely.prepared.prep(DB2)
def along_desk(i):
    p = P[i]
    if p['kind'] not in ('line', 'wline', 'fill'): return False
    g = g_of(i); r = g.minimum_rotated_rectangle
    if r.geom_type != 'Polygon':
        if g.length <= 0: return False
        c = np.array(g.coords if g.geom_type == 'LineString' else [(0, 0), (0, 0)]); u = c[-1] - c[0]
    else:
        c = np.array(r.exterior.coords); a = c[1] - c[0]; b = c[2] - c[1]
        if min(np.linalg.norm(a), np.linalg.norm(b)) > 1.6: return False
        u = a if np.linalg.norm(a) >= np.linalg.norm(b) else b
    if np.linalg.norm(u) < 1.0 or not db2p.intersects(g): return False
    gl = dissolve(g) if g.geom_type != 'Polygon' else g.exterior
    if gl.intersection(DB2).length < 0.8 * gl.length: return False
    j = min(drt.query(g.buffer(2.0)), key=lambda j: DR[j].exterior.distance(g), default=None)
    if j is None: return False
    u = u / np.linalg.norm(u); q = DSIDES[j]; nq = len(q)
    if nq != 4: return True                      # round table: a thin piece along its rim
    return any(abs(u @ ((q[(k + 1) % 4] - q[k]) / max(np.linalg.norm(q[(k + 1) % 4] - q[k]), 1e-9))) > math.cos(math.radians(10)) for k in range(4))
sep = [i for i in restM if along_desk(i)]; sep_s = set(sep)
restM = [i for i in restM if i not in sep_s]
fc = comps(restM + F1, 0.05)
_hulls = [unary_union([g_of(i) for i in c]).convex_hull.buffer(0.3) for c in fc]; _ht = shapely.STRtree(_hulls)
band = []; back = 0
for i in sep:
    g = g_of(i); gl = dissolve(g) if g.geom_type != 'Polygon' else g
    m = gl.length if gl.geom_type != 'Polygon' else gl.area
    best = None
    for k in _ht.query(g):
        ov = gl.intersection(_hulls[k]); v = ov.length if gl.geom_type != 'Polygon' else ov.area
        if m > 0 and v >= 0.8 * m and (best is None or v > best[0]): best = (v, k)
    if best: fc[best[1]].append(i); back += 1
    else: band.append(i)
print('desk band pieces left out of the chairs', len(band), '| back to their chair', back, T())
fu = [unary_union([g_of(i) for i in c]) for c in fc]; hulls = [u.convex_hull for u in fu]
ht = shapely.STRtree(hulls); par = list(range(len(fc)))
def fnd(a):
    while par[a] != a: par[a] = par[par[a]]; a = par[a]
    return a
f1s = set(F1)
for a, c in enumerate(fc):                 # plant leaves join the pot they lie in (hull covers >= 60 %)
    if not any(i in f1s for i in c): continue
    for b in ht.query(hulls[a]):
        if b != a and hulls[b].area > 0 and hulls[a].intersection(hulls[b]).area >= 0.6 * max(hulls[a].area, 1e-9):
            par[fnd(a)] = fnd(b)
grp = collections.defaultdict(list)
for a, c in enumerate(fc): grp[fnd(a)] += c
fobjs = [c for c in grp.values()]
# fragments: a seat is drawn in pieces with gaps (a chair pushed under a desk shows only its back): pieces join the
# nearest piece within 1.2 pt while the union stays seat-sized (<= 18 pt = 865 mm across); tiny pieces (<= 3 primitives,
# <= 1.5 pt) join the nearest object or desk within 1 pt
def bbox_of(c):
    return unary_union([g_of(i) for i in c]).bounds
def ext_b(b): return max(b[2] - b[0], b[3] - b[1])
bbs = [bbox_of(c) for c in fobjs]; alive = [True] * len(fobjs)
geoms_ = [unary_union([g_of(i) for i in c]) for c in fobjs]
order = sorted(range(len(fobjs)), key=lambda k: ext_b(bbs[k]))
gt = shapely.STRtree(geoms_); merged = 0
for k in order:
    if not alive[k] or ext_b(bbs[k]) > 16: continue
    best = None
    for j in gt.query(geoms_[k].buffer(1.2)):
        if j == k or not alive[j]: continue
        dd = geoms_[j].distance(geoms_[k])
        if dd > 1.2: continue
        b = (min(bbs[j][0], bbs[k][0]), min(bbs[j][1], bbs[k][1]), max(bbs[j][2], bbs[k][2]), max(bbs[j][3], bbs[k][3]))
        if ext_b(b) <= 18 and (best is None or dd < best[0]): best = (dd, j, b)
    if best:
        _, j, b = best; fobjs[j] += fobjs[k]; bbs[j] = b; geoms_[j] = geoms_[j].union(geoms_[k]); alive[k] = False; merged += 1
fobjs = [c for c, a in zip(fobjs, alive) if a]
def ext(c):
    u = unary_union([g_of(i) for i in c]); x0, y0, x1, y1 = u.bounds; return max(x1 - x0, y1 - y0), u
big = [k for k, c in enumerate(fobjs) if not (len(c) <= 3 and ext(c)[0] <= 1.5)]
small = [k for k in range(len(fobjs)) if k not in set(big)]
tgt = [(unary_union([g_of(i) for i in fobjs[k]]), ('f', k)) for k in big] + [(unary_union([g_of(i) for i in ids]), ('d', n)) for n, ids in enumerate(desk_objs)]
tt = shapely.STRtree([g for g, _ in tgt]); moved = 0
for k in small:
    u = ext(fobjs[k])[1]; best = None
    for j in tt.query(u.buffer(1.0)):
        dd = tgt[j][0].distance(u)
        if dd <= 1.0 and (best is None or dd < best[0]): best = (dd, tgt[j][1])
    if best:
        kind, n = best[1]
        (fobjs[n] if kind == 'f' else desk_objs[n]).extend(fobjs[k]); fobjs[k] = []; moved += 1
fobjs = [c for c in fobjs if c]
print('long edge lines', len(longl), '(free', len(edge_free), ') | fragments merged', merged, '| tiny pieces joined', moved)
band_free = []                          # test 6: a band piece goes to the desk it lies along (>= 80 % in its rect + 2 pt)
for i in band:
    g = g_of(i); poly = g.geom_type == 'Polygon'; gl = g if poly else dissolve(g); m = gl.area if poly else gl.length
    js = [j for j in drt.query(g.buffer(2.0))
          if m > 0 and ((gl.intersection(DR[j].buffer(2.0, join_style=2)).area if poly else gl.intersection(DR[j].buffer(2.0, join_style=2)).length) >= 0.8 * m)]
    if js: desk_objs[js[0]].append(i)
    else: band_free.append(i)
edge_grp += band_free
print('desk band pieces to desks', len(band) - len(band_free), '| band of a desk group', len(band_free))
for n, ids in enumerate(desk_objs):
    k_ = dkind.get(n, 'desk')
    if k_ == 'rtable':
        D = 2 * math.sqrt(DR[n].area / math.pi) * K; new('rtable', 'A-82', f'Стол круглый ⌀{round(D / 50) * 50}', ids)
    else:
        L_, W_ = dims_mm([ids[0]])
        new(k_, 'A-82', (f'Стол рабочий {round(L_ / 50) * 50}×{round(W_ / 50) * 50}' if k_ == 'desk' else
                         f'Стол переговорный {round(L_ / 50) * 50}×{round(W_ / 50) * 50}'), ids)
for i in edge_free: new('furn', 'A-82', 'Мебель — линия кромки или экрана столов (по исходнику)', [i])
for c in (comps(edge_grp, 0.05) if edge_grp else []):
    L_, W_ = dims_mm(c); new('deskedge', 'A-82', f'Кромка или экран группы столов (по исходнику) {round(L_ / 50) * 50}', c)
# names of furniture by what it is drawn of (decisions from the catalogue, Э7)
def fname(c):
    L_, W_ = dims_mm(c); n = len(c); cols = collections.Counter(P[i]['col'] for i in c)
    green = sum(v for k, v in cols.items() if k and k[1] > k[0] + 0.15 and k[1] > k[2] + 0.1)
    pink = sum(v for k, v in cols.items() if k and k[0] > 0.9 and 0.4 < k[1] < 0.6 and 0.4 < k[2] < 0.6)
    has_f1 = any(i in f1s for i in c)
    Lr, Wr = round(L_ / 50) * 50, round(W_ / 50) * 50
    if has_f1 or (green >= 5 and not any(P[i]['kind'] == 'fill' and P[i]['col'] == (0.0, 0.502, 0.0) for i in c)):
        return 'plant', 'A-89', f'Растение в кашпо ⌀{Lr}' if Lr >= 250 else 'Растение — лист (по исходнику)'
    if any(P[i]['kind'] == 'fill' and P[i]['col'] == (0.0, 0.502, 0.0) for i in c):
        return 'mfp', 'A-82', f'МФУ (принтер, «print») {Lr}×{Wr}'      # code 010 (К-1): МФУ - furniture A-82 (№106, row 208)
    if pink >= 3: return 'booth', 'A-82', f'Кабина для звонков («Skype») {Lr}×{Wr}'
    if n >= 900 and 750 <= L_ <= 1000: return 'armchair', 'A-82', f'Кресло мягкое {Lr}×{Wr}'
    if L_ < 120: return 'furn', 'A-82', 'Мебель — деталь (по исходнику)'
    if L_ <= 900 and W_ <= 800:
        u = unary_union([g_of(i) for i in c]); rr = 4 * math.pi * u.convex_hull.area / max(u.convex_hull.length, 1e-9) ** 2
        if rr > 0.85 and abs(L_ - W_) < 60 and L_ >= 300: return 'round', 'A-82', f'Пуф или столик круглый ⌀{Lr}'
        # test 6 (п. 201, 3.10): a chair is 350-1000 x 250-900 mm and is named by its family, not by its size;
        # a thin piece (< 150 mm across) is not a chair (16 «chairs 500×0» and 15 «550×50» of tests 2 and 5)
        if L_ >= 350 and W_ >= 250: return 'chair', 'A-82', 'Кресло офисное'
        if W_ < 150: return 'furn', 'A-82', 'Мебель — кромка или линия (по исходнику)'
        return 'chairpart', 'A-82', 'Кресло офисное — видимая часть (задвинуто под стол, по исходнику)'
    if L_ <= 2600: return 'table', 'A-82', f'Стол или диван {Lr}×{Wr} (по исходнику)'
    return 'group', 'A-82', f'Кресла рабочих мест у группы столов и кромки столов {Lr}×{Wr} (по исходнику)'
for c in fobjs:
    key, lay, name = fname(c); new(key, lay, name, c)
# test 6: a «desk» or «table» with a sink bowl on it is a kitchen worktop (a grey 1750×600 top at a sink was a desk)
_sinks = [unary_union([g_of(i) for i in o['ids']]).centroid for o in objs if o['key'] == 'sink' and 'деталь' not in o['name']]
for o in objs:
    if o['key'] not in ('desk', 'table') or not _sinks: continue
    top = g_of(o['ids'][0]).minimum_rotated_rectangle.buffer(0.5) if o['key'] == 'desk' else unary_union([g_of(i) for i in o['ids']]).convex_hull
    if any(top.contains(s_) for s_ in _sinks):
        L_, W_ = dims_mm(o['ids'][:1] if o['key'] == 'desk' else o['ids'])
        o['key'] = 'kitchen'; o['layer'] = 'A-76'; o['name'] = f'Столешница кухонная со встроенной мойкой {round(L_ / 50) * 50}×{round(W_ / 50) * 50} (по исходнику)'
print('desks', len(desk_objs), '| furniture objects', len(fobjs), collections.Counter(fname(c)[0] for c in fobjs).most_common(), T())
# ---------------- anything left (layers not handled) -> report
_TXT_L = sheet.L('text')
left = [p['id'] for p in P if p['id'] not in owner and p['layer'] not in _TXT_L and p['kind'] != 'removed']
print('primitives without owner', len(left), collections.Counter(P[i]['layer'] for i in left).most_common(10))
pickle.dump(dict(objs=objs, owner=owner, wall_in={k: v for k, v in wall_in.items()}), open('objects_e7.pkl', 'wb'))   # Э7м (e7f_furniture.py) writes objects.pkl
_W = dict(W); _W['bodies'] = [(c, q) for c, g in B for q in getattr(g, 'geoms', [g]) if q.geom_type == 'Polygon' and q.area > 0.05]
pickle.dump(_W, open('walls_e7.pkl', 'wb'))      # bodies with the absorbed lines (one polygon each)
D1 = dict(D0); D1['P'] = P; pickle.dump(D1, open('prims_e7.pkl', 'wb'))      # primitives as classified (with split pieces)
print('objects', len(objs), collections.Counter(o['key'] for o in objs).most_common(), T())
