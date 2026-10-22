"""Э9з — zones: rooms and passages as closed polygons to fill with colour on the map (owner 09.10.2026, remarks З-14…З-23).

Owner, З-14: «Мне нужно, чтобы был определен внутренний контур помещения, то есть по внутренней грани стен, о стеклении дверей
была выделена площадь помещения, чтобы потом эту зону можно было залить каким-то цветом на карте, чтобы ее подсветить. То же
самое относится к проходам.» З-15 (переговорная «образцовая комната»): the room polygon — 4 points along the inner faces of the partitions;
door openings closed along the wall line; furniture and labels do not change it.

ROOMS. Solid = wall bodies of every class (walls_r: cleaned on the face lines), glass bands, partitions drawn by lines, the core
(its blocks and the lines of its capital walls), the facade (frames and glass) and the door openings (the opening rectangle of
Э6г, as thick as its wall: the room is closed along the wall line). The floor is the inside of the facade; a room is a piece of
the floor minus the solid, at least ROOM_MIN in area and ROOM_W wide (a gap between two walls is not a room). Its outline is
put on the face lines of the solid (the same lines as the walls — a room touches its walls exactly, no extra points). A room
gets the texts inside it (number «40.10», name «образцовая комната»), its desks; ≥ 4 desks — an open space; no desks, no furniture to
speak of and ≥ 3 doors — a corridor.

PASSAGES (owner З-16: «По определению проходов внутри OpenSpace я пока не могу сформировать четких правил, поэтому на разных
картинках покажу линиями, как бы я ожидал, что пройдет зона прохода»; З-17: «там, где есть стена, проход, очевидно, проходит
вдоль стены»; З-18…З-23 — the owner's lines). Rule drawn from the owner's lines ⟨один пример — this floor⟩:
 1. zones of furniture: items of the open space (desks with their chairs, tables, cabinets, sofas, kitchens…) closer than GAP
    to each other make one zone — its smallest rotated rectangle (a group of desks is bounded by straight sides, З-22);
 2. blocks: zones and small obstacles (free-standing columns, З-20) closer than W to each other — no passage between them, it
    would be narrower than W — make one block: their convex hull, a straight line tangent to a row of groups (З-21: «одна
    прямая по огибающей кромке кресел»); when the hull swallows free floor (more than HULL_X of the closing) — the closing;
 3. passage = the open space minus the blocks, opened by a square of side W (narrower strips are not a passage; corners stay
    straight), the pieces that reach a door or a corridor or are ≥ POCKET in area; along a wall its side is the wall's face
    (the solid bounds the open space, З-17…З-19: one straight line, the door openings closed along the wall line);
 4. the outline on the face lines of the walls and blocks with TOL_P (jogs under 100 mm go), the fewest points.
A corridor room is a passage as a whole.
W — the passage width: the long side of the typical workplace desk (furniture.json), as in Э9 (owner 06.10.2026).
Writes rooms.pkl, passage.pkl (the format of Э9: passage, open_spaces, corridor, width_mm…) and zones.json.
Code 012 (stage 2 of the merge of v010 into ocg/; the code of pass v010, route/e9z_zones.py) — the step of the layer route after
Э7р, instead of Э9 (ocg/run_ocg.sh):
 - the sheet from cfg (ocg/sheet.py): the scale — cfg.MM_PER_PT (v010: K = 48.04 in the code), every threshold in mm through it
   (v010 set the small tolerances in pt — 0.001–0.5 pt, 4 pt² — at 48.04 mm/pt <one example: client-b, floor 40>; the mm here
   are those pt × 48.04, the same numbers on that sheet); no scale — a stop;
 - the texts of a room (v010: regular expressions of client-b in the code) — cfg.OCG_ROOM_NO_RE (the number of a room, the
   whole text, e.g. «40.10»), cfg.OCG_ROOM_NAME_RE (a name: found in the text) and cfg.OCG_ROOM_NAME_SKIP_RE (texts that look
   like a name and are not one — notes, the sheet's title; None — none); a field missing — a stop;
 - the owner's sample room (v010: «образцовая комната» in the code) — cfg.OCG_ROOM_SAMPLE['name'] (zones.json 'sample_room'); none — not
   reported."""
import pickle, json, math, re, sys, time, collections, os
import numpy as np, shapely
from shapely.geometry import Polygon, MultiPolygon, LineString, Point
from shapely.ops import unary_union as _uu
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import sheet
from e7_comp import geom, load_prims, load_walls
import regular as RG
t0 = time.time(); K = sheet.K
if not K: sys.exit('СТОП Э9з: нет масштаба листа cfg.MM_PER_PT — пороги шага в мм не перевести в pt (plan/rules/20 §3.8)')
MM = 1 / K
def mm(v): return v / K                    # a threshold in mm -> pt of the sheet
_NO = object()
def _cfg_re(name, none_ok=False):
    v = getattr(sheet.cfg, name, _NO)
    if v is _NO or (v is None and not none_ok):
        sys.exit(f'СТОП Э9з: в cfg нет {name} — по какому образцу узнавать номер и название помещения среди надписей листа '
                 f'(v010 держал образец клиент Б в коде; cfg этажа — ocg/examples/cfg_federation-40.py)')
    if v is None: return None
    try: return re.compile(v)
    except re.error as e: sys.exit(f'СТОП Э9з: cfg.{name} = {v!r} — не регулярное выражение: {e}')
ROOM_NO_RE = _cfg_re('OCG_ROOM_NO_RE')                       # v010: r'\d{1,3}\.\d{2}' (fullmatch)
ROOM_NAME_RE = _cfg_re('OCG_ROOM_NAME_RE')                   # v010: r'[А-Яа-яЁё]{3,}' (search)
ROOM_NAME_SKIP_RE = _cfg_re('OCG_ROOM_NAME_SKIP_RE', True)   # v010: r'(СУЩ|ПК|офис|План|столы)' (match at the start)
SAMPLE = (getattr(sheet.cfg, 'OCG_ROOM_SAMPLE', None) or {}).get('name')
# thresholds in mm (v010 in pt at 48.04 mm/pt): the grid of a fallback union GRID_MM; a door opening longer by OPEN_EXT_MM across
# the wall; the outside of the floor within EDGE_MM of the hull; a line of an item thickened to ITEM_LINE_MM; labels within
# LABEL_MM of a room; desks, items, passages within NEAR_ROOM_MM of a room; a door into a room within DOOR_MM; an engineering item
# in an open space from WALL_ITEM_MM2
GRID_MM, OPEN_EXT_MM, EDGE_MM, ITEM_LINE_MM, LABEL_MM = 0.04804, 2.402, 24.02, 5.7648, 0.4804     # 0.001, 0.05, 0.5, 0.12, 0.01 pt
NEAR_ROOM_MM, DOOR_MM, WALL_ITEM_MM2 = 24.02, 9.608, 9231.3664                                    # 0.5, 0.2 pt; 4 pt²
def T(): return f'{time.time() - t0:.1f} s'
def m2(a): return round(a * K * K / 1e6, 2)
def unary_union(gs):
    gs = [g for g in gs if g is not None and not g.is_empty]
    if not gs: return Polygon()
    try: return _uu(gs)
    except Exception: return shapely.union_all([shapely.make_valid(g) for g in gs], grid_size=mm(GRID_MM))
def polys(g): return [q for q in getattr(g, 'geoms', [g]) if q.geom_type == 'Polygon' and not q.is_empty]
ROOM_MIN = 0.5e6 * MM * MM          # 0.5 m²
VOID_MAX = 2.0e6 * MM * MM          # a piece without a door, a label or a desk under 2 m² — a void inside walls, not a room
ROOM_W = 300 * MM                   # a room at least 300 mm wide somewhere
GAP = 300 * MM                      # items of one zone
CH = 600 * MM                       # the envelope of a group: gaps between its chairs up to 1200 mm are closed
HULL_X = 1.15
POCKET = 6.0e6 * MM * MM            # 6 m²
TOL_P = 300 * MM                    # passage outline: jogs under 300 mm go (the edge of a row of groups — one line)
def desk_long_mm():
    try:
        S_ = json.load(open('furniture.json')).get('typical_desk_sizes_mm') or []
        if S_: return float(max(S_, key=lambda r: r[2])[0])
    except Exception: pass
    return None
DESK_MM = desk_long_mm()
WIDTH_MM = float(os.environ.get('WIDTH_MM') or DESK_MM or 1400.0); WIDTH = WIDTH_MM * MM
WIDTH_FROM = 'WIDTH_MM' if os.environ.get('WIDTH_MM') else ('длинная сторона типового рабочего стола' if DESK_MM else 'умолчание 1400 мм')
D = load_prims(); P = D['P']; TX = D['T']
O = pickle.load(open('objects.pkl', 'rb')); objs = O['objs']
W = load_walls()['bodies']
print('passage width', round(WIDTH_MM), 'mm —', WIDTH_FROM, T())
# ------------------------------------------------------------------------------------------------ solid
def ofills(o, ids=None):
    out = []
    for i in (ids if ids is not None else o['ids']):
        p = P[i]
        if p['kind'] == 'fill' and len(p['p']) >= 3:
            g = Polygon(p['p'], p.get('holes', [])).buffer(0)
            if not g.is_empty: out.append(g)
    return out
def olines(o, w):
    out = []
    for i in o['ids']:
        p = P[i]
        if p['kind'] == 'line' and len(p['p']) >= 2:
            out.append(LineString(p['p']).buffer(w / 2, cap_style=2, join_style=2))
    return out
WALLS = unary_union([g for c, g in W])
COLS = [g for c, g in W if c == 'column']
GLASS = unary_union([g for o in objs if o['key'] == 'glass' and o['ids'] for g in ofills(o)] +
                    [g for o in objs if o['key'] in ('glass', 'lpart') and o['ids'] for g in olines(o, 40 * MM)])
CORE = unary_union([g for o in objs if o['key'] == 'coreblock' and o['ids'] for g in ofills(o)] +
                   [g for o in objs if o['key'] == 'coreline' and o['ids'] for g in olines(o, 40 * MM)])
FAC = unary_union([g for o in objs if o['key'] in ('facade', 'mullion') and o['ids'] for g in ofills(o) + olines(o, 40 * MM)])
GR = json.load(open('geom_report.json')); OPEN = []
for d in GR['places'].get('doors', []):
    f = d.get('frame')
    if not f: continue
    o_, u_, n_ = np.array(f[0]), np.array(f[1]), np.array(f[2]); c0, c1, tl, th = f[3], f[4], f[5], f[6]
    e = mm(OPEN_EXT_MM)
    OPEN.append(Polygon([tuple(o_ + u_ * a + n_ * b) for a, b in ((c0, tl - e), (c1, tl - e), (c1, th + e), (c0, th + e))]))
OPENU = unary_union(OPEN)
# a partition drawn by two lines without a fill is solid between its lines (closing of 75 mm: up to 150 mm thick), and the whole
# solid is closed by SLIT: a slit narrower than 2·SLIT between two solid pieces (a glass band that stops short of its wall) is
# not a way into the next room
SLIT = 60 * MM
LPS = unary_union([g for o in objs if o['key'] in ('lpart', 'coreline') or (o['key'] == 'glass' and not ofills(o))
                   for g in olines(o, 40 * MM) if o['ids']])
LPS = LPS.buffer(75 * MM, join_style=2).buffer(-75 * MM, join_style=2) if not LPS.is_empty else LPS
# a wall screen (TV panel) on a wall or in a gap of it is the wall there (З-4: the wall goes straight under the screen)
_W0 = unary_union([WALLS, GLASS, LPS]).buffer(50 * MM)
def _thin(g, w):
    m = g.minimum_rotated_rectangle
    if m.geom_type != 'Polygon': return False
    xs = list(m.exterior.coords); return min(RG.dist(xs[0], xs[1]), RG.dist(xs[1], xs[2])) <= w
EQW = unary_union([g for o in objs if o['key'] == 'equip' and o['ids'] for g in ofills(o) if g.intersects(_W0) and _thin(g, 200 * MM)])
SOLID = unary_union([WALLS, GLASS, CORE, FAC, LPS, EQW]).buffer(SLIT, join_style=2).buffer(-SLIT, join_style=2)
# the floor: the inside of the facade — the biggest hole of the solid's hull band, else the hull itself
hull = SOLID.convex_hull
outside = [q for q in polys(hull.difference(SOLID)) if q.intersects(hull.exterior.buffer(mm(EDGE_MM)))]
FLOOR = hull.difference(unary_union(outside)) if outside else hull
print('solid', m2(SOLID.area), 'm² | floor', m2(FLOOR.area), 'm² | door openings', len(OPEN), '| outside pieces', len(outside), T())
# ------------------------------------------------------------------------------------------------ face lines of the solid
# the face lines of the rooms — the edges of the solid itself (the room is its complement): a room edge goes on the face it lies
# on, ROOM_TOL at most (micro-kinks of mixed sources — wall, glass, a line partition — under 10 mm go; two rooms on the two sides of
# a wall never meet, a room never goes into a wall deeper than ROOM_TOL)
ROOM_TOL = 100 * MM
def inner_face_lines(poly, tol):
    """face lines of one room's own edges, each moved to the innermost of its edges (towards the room)"""
    FLr = RG.FaceLines(tol=tol, ang=1.5, min_len=100 * MM)
    FLr.add_edges(RG.face_edges(poly, ('room',)))
    for F in FLr.L:
        sides = {s_ for _, s_ in F['mem'] if s_}
        if len(sides) != 1: continue
        sd = sides.pop(); th = F['th']; nl = (-math.sin(th), math.cos(th)); n_in = (-nl[0] * sd, -nl[1] * sd)
        m = max((q[0] - F['p'][0]) * n_in[0] + (q[1] - F['p'][1]) * n_in[1] for a, b in F['segs'] for q in (a, b))
        F['p'] = (F['p'][0] + n_in[0] * m, F['p'][1] + n_in[1] * m)
    FLr._index()
    return FLr
FL = RG.FaceLines(tol=ROOM_TOL, ang=1.0, min_len=100 * MM)
edges = []
SOLO = unary_union([SOLID, OPENU])
ROOM_IN = 30 * MM
SOLO_IN = SOLO.buffer(-ROOM_IN, join_style=2)
for j, q in enumerate(polys(SOLO)): edges += RG.face_edges(q, ('s', j))
FL.add_edges(edges)
print('face lines', len(FL.L), T())
def clean_poly(g, FL_, tol):
    ng, s = RG.regularize_polygon(g, FL_, tol=tol)
    if s.get('fallback') or s.get('fallback_poly') or not ng.is_valid:
        c = [RG.clean_ring(list(r.coords)) for r in [g.exterior] + list(g.interiors)]
        try:
            ng2 = Polygon(c[0], [h for h in c[1:] if len(h) >= 3])
            if ng2.is_valid: return ng2, 'cleaned'
        except Exception: pass
        return g, 'kept'
    return ng, 'face lines'
def mrr(g):
    m = g.minimum_rotated_rectangle
    return m if m.geom_type == 'Polygon' else g.convex_hull
# ------------------------------------------------------------------------------------------------ rooms
free = FLOOR.difference(SOLID).difference(OPENU)
cand = [q for q in polys(free) if q.area >= ROOM_MIN and not q.buffer(-ROOM_W / 2, join_style=2).is_empty]
TXT = []
for t in TX:
    s = t['text'].strip(); b = t['bbox']
    TXT.append((Point((b[0] + b[2]) / 2, (b[1] + b[3]) / 2), s))
def is_room_no(s): return ROOM_NO_RE.fullmatch(s) is not None
def is_name(s): return ROOM_NAME_RE.search(s) is not None and not (ROOM_NAME_SKIP_RE is not None and ROOM_NAME_SKIP_RE.match(s))
DESKG = [(k, Polygon(P[o['draw'][0]]['p']) if o.get('draw') and P[o['draw'][0]]['kind'] == 'fill' else None) for k, o in enumerate(objs)
         if o['key'] == 'desk' and o['ids']]
DESKG = [(k, g if g is not None and g.is_valid else None) for k, g in DESKG]
def foot(o):
    ids = o.get('outline') or o.get('draw') or o['ids']
    fs = ofills(o, ids)
    if fs: return unary_union(fs)
    gs = []
    for i in ids:
        p = P[i]
        if p['kind'] == 'removed' or len(p['p']) < 2: continue
        g = geom(p)
        if not g.is_empty: gs.append(g.buffer(mm(ITEM_LINE_MM)) if g.geom_type in ('LineString', 'MultiLineString') else g)
    return unary_union(gs).convex_hull if gs else None
FURN = {'desk', 'chair', 'chairpart', 'armchair', 'sofa', 'round', 'rtable', 'mtable', 'dtable', 'ctable', 'storage', 'pedestal',
        'kitchen', 'table', 'group', 'furn', 'booth', 'mfp', 'plant', 'counter', 'sink', 'equip', 'san', 'fire', 'conv'}
ITEMS = []
for k, o in enumerate(objs):
    if o['key'] not in FURN or not o['ids']: continue
    g = foot(o)
    if g is None or g.is_empty or g.area <= 0: continue
    ITEMS.append((k, o['key'], g))
IT = shapely.STRtree([g for k, key, g in ITEMS])
rooms = []; st = collections.Counter()
for q in cand:
    g, how = clean_poly(q, FL, 10 * MM); st['room outline: ' + how] += 1
    # З-15: one straight line along a wall whose face steps by less than ROOM_TOL (a glass band thinner than its GKL, a lining):
    # the line at the innermost face — the room never goes into the wall, a recess under ROOM_TOL is left out («образцовая комната» — 4 points)
    if g.is_valid and g.geom_type == 'Polygon':
        g2, how2 = clean_poly(g, inner_face_lines(g, ROOM_TOL), 2 * ROOM_TOL)
        if g2.is_valid and g2.geom_type == 'Polygon':
            # a bump of the solid shallower than ROOM_IN (an end cap, a panel's edge) stays under the room's straight line; a
            # deeper one is cut out of the room
            if not g2.intersection(SOLO_IN).is_empty:
                g2 = g2.difference(SOLO)
                g2 = max(polys(g2), key=lambda x: x.area) if polys(g2) else None
            if g2 is not None and g2.area >= 0.95 * g.area:
                g = Polygon(RG.clean_ring(list(g2.exterior.coords)), [RG.clean_ring(list(h.coords)) for h in g2.interiors if len(h.coords) > 3])
                if not g.is_valid: g = g.buffer(0)
                st['room outline: inner faces'] += 1
    if not g.is_valid or g.area <= 0: g = q
    if g.geom_type != 'Polygon':
        big = max(polys(g), key=lambda x: x.area) if polys(g) else None
        g = big if big is not None and big.area >= 0.98 * q.area else q; st['room outline: kept (pieces)'] += 1
    rp = g.buffer(mm(LABEL_MM))
    lab = [s for p, s in TXT if rp.contains(p) and (is_room_no(s) or is_name(s))]
    nos = [s for s in lab if is_room_no(s)]; names = [s for s in lab if not is_room_no(s)]
    desks = [k for k, dg in DESKG if dg is not None and q.buffer(mm(NEAR_ROOM_MM)).contains(dg.centroid)]
    its = [ITEMS[j] for j in IT.query(q) if q.buffer(mm(NEAR_ROOM_MM)).contains(ITEMS[j][2].representative_point())]
    fa = sum(x[2].area for x in its if x[1] not in ('conv', 'fire', 'san'))
    nd = sum(1 for op in OPEN if op.buffer(mm(DOOR_MM)).intersects(q))
    if nd == 0 and q.area < VOID_MAX and not desks and not names and not nos:
        st['void inside walls (not a room)'] += 1; continue          # the hollow of a casing or a shaft: no door, < 2 m²
    mq = mrr(q); xs_ = list(mq.exterior.coords); sides = sorted([RG.dist(xs_[0], xs_[1]), RG.dist(xs_[1], xs_[2])])
    long_ = sides[1] >= 2.5 * max(sides[0], 1e-9)
    # a corridor: no desks, hardly any furniture, three doors or more, long (or a big hall of doors: a lift lobby)
    kind = 'open space' if len(desks) >= 4 else ('corridor' if nd >= 3 and fa <= 0.05 * q.area and not names
                                                 and (long_ or q.area >= 30e6 * MM * MM) else 'room')
    nv = len(g.exterior.coords) - 1 + sum(len(h.coords) - 1 for h in g.interiors)
    rooms.append(dict(poly=g, raw=q, kind=kind, number=nos[0] if nos else '', numbers=nos, names=names, desks=len(desks), doors=nd,
                      area_m2=m2(g.area), points=nv, at=[round(v, 1) for v in g.representative_point().coords[0]]))
    st['rooms: ' + kind] += 1
# cabins of a WC (owner 26.09.2026, map/rules/11 §8.2: «перегородки кабин не рисуются, санузел — одно помещение»): a small room
# (< CABIN_MAX) with a door and nothing else in it, whose door opens into another room, — part of that room: joined with it through
# the door, the partitions between the cabins closed (≤ 2·CABIN_GAP thick)
CABIN_MAX = 2.5e6 * MM * MM; CABIN_GAP = 100 * MM
cab = [i for i, r in enumerate(rooms) if r['raw'].area < CABIN_MAX and r['doors'] >= 1 and not r['desks'] and not r['names'] and not r['numbers']]
host = {}
for i in cab:
    q = rooms[i]['raw']
    for op in OPEN:
        if not op.buffer(mm(DOOR_MM)).intersects(q): continue
        cands = [j for j, r in enumerate(rooms) if j != i and j not in cab and op.buffer(mm(DOOR_MM)).intersects(r['raw'])]
        if cands: host[i] = max(cands, key=lambda j: rooms[j]['raw'].area); break
grp = collections.defaultdict(list)
for i, j in host.items(): grp[j].append(i)
# cabins next to a cabin that has a host (a row of cabins, doors into a common lobby) follow it
for i in cab:
    if i in host: continue
    for i2, j in list(host.items()):
        if rooms[i]['raw'].distance(rooms[i2]['raw']) <= 2 * CABIN_GAP: grp[j].append(i); host[i] = j; break
drop = set()
for j, mem in grp.items():
    parts = [rooms[j]['raw']] + [rooms[i]['raw'] for i in mem]
    ops = [op for op in OPEN if any(op.buffer(mm(DOOR_MM)).intersects(x) for x in parts)]
    u = unary_union(parts + [op.intersection(unary_union(parts).buffer(3 * CABIN_GAP)) for op in ops])
    u = u.buffer(CABIN_GAP, join_style=2).buffer(-CABIN_GAP, join_style=2)
    u = max(polys(u), key=lambda x: x.area) if polys(u) else rooms[j]['raw']
    g, how = clean_poly(u, inner_face_lines(u, ROOM_TOL), 2 * ROOM_TOL)
    if not g.is_valid or g.geom_type != 'Polygon': g = u
    nv = len(g.exterior.coords) - 1 + sum(len(h.coords) - 1 for h in g.interiors)
    k0 = rooms[j]['kind']
    rooms[j].update(poly=g, raw=u, area_m2=m2(g.area), points=nv, cabins=len(mem),
                    kind='room' if k0 == 'corridor' and len(mem) >= 2 else k0)     # a lobby of WC cabins is the WC, not a corridor
    print('   cabins', len(mem), 'joined', k0, '->', rooms[j]['kind'], rooms[j]['at'])
    drop |= set(mem); st['cabins joined their room'] += len(mem)
rooms = [r for i, r in enumerate(rooms) if i not in drop]
print('rooms', len(rooms), dict(st), T())
# ------------------------------------------------------------------------------------------------ passages
def mrr(g):
    m = g.minimum_rotated_rectangle
    return m if m.geom_type == 'Polygon' else g.convex_hull
RECT_X = 1.6
def rect_angle(g):
    m = g.minimum_rotated_rectangle
    if m.geom_type != 'Polygon': return 0.0
    xs = list(m.exterior.coords); a, b = xs[0], xs[1]
    if RG.dist(xs[1], xs[2]) > RG.dist(a, b): a, b = xs[1], xs[2]
    return math.atan2(b[1] - a[1], b[0] - a[0])
def aligned_box(g, th):
    c, s_ = math.cos(-th), math.sin(-th)
    pts = [(c * x - s_ * y, s_ * x + c * y) for q in polys(g) for x, y in q.exterior.coords]
    if not pts: return g
    X = [p[0] for p in pts]; Y = [p[1] for p in pts]
    c2, s2 = math.cos(th), math.sin(th)
    return Polygon([(c2 * x - s2 * y, s2 * x + c2 * y) for x, y in ((min(X), min(Y)), (max(X), min(Y)), (max(X), max(Y)), (min(X), max(Y)))])
def clusters(geoms, gap):
    """indices of geometries closer than gap — connected groups"""
    n = len(geoms); parent = list(range(n))
    def fnd(a):
        while parent[a] != a: parent[a] = parent[parent[a]]; a = parent[a]
        return a
    tr = shapely.STRtree(geoms)
    for i, g in enumerate(geoms):
        for j in tr.query(g.buffer(gap)):
            if j > i and geoms[j].distance(g) < gap: parent[fnd(i)] = fnd(j)
    gr = collections.defaultdict(list)
    for i in range(n): gr[fnd(i)].append(i)
    return list(gr.values())
PASS = []; PINFO = []; ZONES_DBG = []
corr_rooms = [r for r in rooms if r['kind'] == 'corridor']
CORR = unary_union([r['poly'] for r in corr_rooms])
SQ = dict(join_style=2, mitre_limit=5.0)
for ri, r in enumerate(rooms):
    if r['kind'] != 'open space': continue
    R0 = r['poly']; Rb = R0.buffer(mm(NEAR_ROOM_MM))
    its = [ITEMS[j] for j in IT.query(R0) if Rb.contains(ITEMS[j][2].representative_point())]
    its = [x for x in its if x[1] not in ('conv', 'fire', 'san', 'sink') or x[2].area > WALL_ITEM_MM2 * MM * MM]     # wall-mounted bits stay out
    if not its: continue
    geoms = [x[2] for x in its]
    zones = []; zst = collections.Counter(); zang = []
    for grp in clusters(geoms, GAP):
        u = unary_union([geoms[i] for i in grp])
        # the envelope of the group: gaps between chairs up to 2·CH closed (the edge of a row of chairs is one line, «без
        # зубцов по каждому креслу», З-16)
        c_ = u.buffer(CH, **SQ).buffer(-CH, **SQ)
        if c_.is_empty: c_ = u
        # a group of desks is a rectangle in the frame of its desks (З-22: «огибается прямыми гранями прямоугольника»), the
        # chairs pulled out included; not when that swallows free floor (an L of groups: more than RECT_X of the envelope)
        dk = [geoms[i] for i in grp if its[i][1] == 'desk']
        th = rect_angle(max(dk, key=lambda g: g.area) if dk else c_)
        m_ = aligned_box(u, th)
        if m_.area <= RECT_X * c_.area: zones.append(m_); zst['rectangle'] += 1; zang.append(th)
        else: zones += polys(c_); zst['envelope'] += 1; zang += [th] * len(polys(c_))
    # small obstacles inside the open space: the holes of its outline (free-standing columns, shafts) up to 4 m²
    obst = []
    for h in R0.interiors:
        hg = Polygon(h.coords)
        if hg.area > 4.0e6 * MM * MM: continue
        # a free-standing column next to a group is bounded by a line along the group's edge (З-20: «колонна вне площадки»):
        # its box in the frame of the nearest zone
        if zones:
            j = min(range(len(zones)), key=lambda q: zones[q].distance(hg))
            if zones[j].distance(hg) < WIDTH: hg = aligned_box(hg, zang[j])
        obst.append(hg)
    allz = zones + obst
    # pairs of zones closer than W: the gap between them is no passage — bridged by the pair's convex hull (a tangent line
    # along a row, З-21) or, when the hull would swallow free floor (more than HULL_X of the closing), by the closing; the
    # bridge is pairwise, so a chain of groups does not fill the floor between its far ends (the crossing of З-20 stays)
    blocks = list(allz); tz = shapely.STRtree(allz); nb_ = collections.Counter()
    for i, a in enumerate(allz):
        for j in tz.query(a.buffer(WIDTH)):
            if j <= i or allz[j].distance(a) >= WIDTH: continue
            u = unary_union([a, allz[j]]); hullb = u.convex_hull
            clos = u.buffer(WIDTH / 2, **SQ).buffer(-WIDTH / 2, **SQ).intersection(hullb)
            if hullb.area <= HULL_X * max(clos.area, u.area): blocks.append(hullb); nb_['hull'] += 1
            else: blocks.append(clos); nb_['closing'] += 1
    ZONES_DBG.append(dict(room=ri, zones=allz, bridges=dict(nb_)))
    BL = unary_union(blocks)
    pz = R0.difference(BL)
    op = pz.buffer(-WIDTH / 2, **SQ).buffer(WIDTH / 2, **SQ).intersection(pz)
    keep = []
    for q in polys(op):
        if q.area < 1.0e6 * MM * MM: continue
        touches = q.buffer(mm(NEAR_ROOM_MM)).intersects(OPENU) or (not CORR.is_empty and q.buffer(mm(NEAR_ROOM_MM)).intersects(CORR))
        if touches or q.area >= POCKET: keep.append(q)
    if not keep: continue
    # the outline on the face lines of the walls and of the blocks
    FL2 = RG.FaceLines(tol=TOL_P, ang=3.0, min_len=300 * MM)
    e2 = []
    for q in polys(R0): e2 += RG.face_edges(q, ('r', ri))
    for j, b in enumerate(blocks):
        for q in polys(b): e2 += RG.face_edges(q, ('b', ri, j))
    FL2.add_edges(e2)
    FL3 = RG.FaceLines(tol=30 * MM, ang=1.0, min_len=100 * MM); FL3.add_edges(e2)
    outp = []
    for q in keep:
        g, how = clean_poly(q, FL2, TOL_P); st['passage outline: ' + how] += 1
        # the cleaned outline stays on the free floor: inside the open space and off the blocks of furniture; spikes thinner than
        # 200 mm go; then the outline goes back onto the lines of the open space and of the blocks exactly (30 mm): no steps
        # where the coarse line crossed the wall's face (ПЗ-9: «без изломов у дверей», З-18)
        g = g.intersection(R0.difference(BL)) if g.is_valid else q
        g = g.buffer(-100 * MM, join_style=2).buffer(100 * MM, join_style=2).intersection(g)
        for q2 in polys(g):
            if q2.area < 1.0e6 * MM * MM: continue
            q3, how3 = clean_poly(q2, FL3, 30 * MM)
            q3 = q3.intersection(R0.difference(BL)) if q3.is_valid else q2
            for q4 in polys(q3):
                ex_ = RG.clean_ring(list(q4.exterior.coords))
                if len(ex_) < 3: continue
                hs_ = [h for h in (RG.clean_ring(list(h.coords)) for h in q4.interiors) if len(h) >= 3]
                q5 = Polygon(ex_, hs_)
                if not q5.is_valid: q5 = q4
                if q5.area >= 1.0e6 * MM * MM: outp.append(q5)
    if not outp: continue
    pz2 = unary_union(outp)
    PASS.append(pz2)
    nv = sum(len(q.exterior.coords) - 1 + sum(len(h.coords) - 1 for h in q.interiors) for q in polys(pz2))
    PINFO.append(dict(room=ri, at=r['at'], desks=r['desks'], open_space_m2=r['area_m2'], passage_m2=m2(pz2.area),
                      share=round(pz2.area / R0.area, 2), zones=dict(zst), bridges=dict(nb_), parts=len(polys(pz2)), points=nv))
PKIND = ['open space'] * len(PASS)
for r in corr_rooms:
    PASS.append(r['poly']); PKIND.append('corridor')
    PINFO.append(dict(room=rooms.index(r), at=r['at'], corridor=True, passage_m2=r['area_m2'], points=r['points']))
print('passages', len(PASS), '| area', m2(sum(p.area for p in PASS)), 'm²', dict(st), T())
# ------------------------------------------------------------------------------------------------ write
OS = [r['poly'] for r in rooms if r['kind'] == 'open space']
pickle.dump(dict(passage=PASS, kinds=PKIND, open_spaces=OS, corridor=CORR, width_mm=WIDTH * K, width_from=WIDTH_FROM, tol_mm=TOL_P * K,
                 info=PINFO, zones_dbg=ZONES_DBG), open('passage.pkl', 'wb'))
pickle.dump(dict(rooms=[{k: v for k, v in r.items() if k != 'raw'} for r in rooms]), open('rooms.pkl', 'wb'))
bel = [r for r in rooms if SAMPLE and any(SAMPLE in s for s in r['names'])]          # cfg.OCG_ROOM_SAMPLE (v010: «образцовая комната»)
res = dict(width_mm=round(WIDTH_MM), width_from=WIDTH_FROM, stats=dict(st), rooms=len(rooms),
           rooms_by_kind=dict(collections.Counter(r['kind'] for r in rooms)),
           room_points=dict(collections.Counter(min(r['points'], 12) for r in rooms)),
           sample_room=dict(name=SAMPLE, rooms=[dict(points=r['points'], area_m2=r['area_m2'], number=r['number']) for r in bel]),
           rooms_list=[{k: v for k, v in r.items() if k not in ('poly', 'raw')} for r in rooms], passages=PINFO)
json.dump(res, open('zones.json', 'w'), ensure_ascii=False, indent=1)
print('sample room', SAMPLE, res['sample_room']['rooms'], '| room points', res['room_points'], T())
