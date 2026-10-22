"""Э7я (owner 06.10.2026): the core of the tower in closed polygons. «Еще пример не замкнутости: когда линии висят в воздухе
либо контур капитальной стены не замкнулся в полигоне»; «ядро башни неточно расположено. Там есть капитальные толстые стены,
там есть шахты, лифты, которые не собраны в замкнутый контур полигона».
The source draws the core as blocks of existing structure (shafts, stairs, lifts in thick walls) — thin outline lines
(coreline: the wall layer, the «Линии» layer) and a diagonal hatch over the blocks (corezone). Here:
 1. the outline lines and the outlines of the core fills are joined: two free ends within 1.5 pt of each other (also the
    two ends of one open outline) get a straight connector, a free end within 1.5 pt of another line — to its nearest
    point (a gap of the drawing); then the line work is cut into faces (polygonize);
 2. a face is a block of the core when the hatch covers it: hatch length inside / face area >= 0.12 per pt (the source
    hatch is one line every 3.9 pt: 0.26 per pt; a face half covered is still the block's);
 3. a block = the union of touching hatched faces — one closed polygon (with a hole where a face inside is not hatched);
    the outlines inside a block (inner faces: a shaft in its walls) are its inner structure (the detailed result);
 4. a line of the core outline that bounds no face after the joins: inside a block — the block's inner structure (an
    open inner outline), elsewhere — hanging in the air: listed with its length and place, still drawn in the detailed
    result, left out of the габаритный one.
The block is drawn as its closed outline (A-221 E) and the source's hatch as a pattern (A-221 H, 45°, its spacing); the raw
hatch lines and the outline lines it replaces are no longer drawn. Lifts and shafts keep their own objects.
Reads objects.pkl, prims (load_prims chain); writes prims_c.pkl, objects.pkl, core.json. usage: python3 e7c_core.py (after e7d)"""
import pickle, json, math, collections, sys, time
import numpy as np, shapely
from shapely.geometry import LineString, Polygon, Point
from shapely.ops import unary_union, polygonize, nearest_points
from scipy.spatial import cKDTree
import os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import sheet; from e7_comp import geom, load_prims
t0 = time.time(); K = sheet.K
def T(): return f'{time.time() - t0:.1f} s'
D0 = load_prims(); P = D0['P']
O = pickle.load(open('objects.pkl', 'rb')); objs = O['objs']; owner = O['owner']
def live(i): return P[i]['kind'] != 'removed'
HZ = [i for o in objs if o['key'] == 'corezone' for i in o['ids'] if live(i) and P[i]['kind'] == 'line']
CL = [(k, i) for k, o in enumerate(objs) if o['key'] == 'coreline' for i in o['ids'] if live(i) and not P[i].get('synthetic')]
if not HZ or not CL:
    json.dump(dict(blocks=0, note='нет штриховки ядра или контура ядра'), open('core.json', 'w'), ensure_ascii=False, indent=1)
    D1 = dict(D0); pickle.dump(D1, open('prims_c.pkl', 'wb')); print('no core hatch or core outline'); sys.exit(0)
hz = [geom(P[i]) for i in HZ]; ht = shapely.STRtree(hz)
# hatch direction and spacing (for the pattern)
ang = [math.degrees(math.atan2(g.coords[-1][1] - g.coords[0][1], g.coords[-1][0] - g.coords[0][0])) % 180 for g in hz if g.length > 0]
a0 = collections.Counter(round(a) for a in ang).most_common(1)[0][0]; th = math.radians(a0); nv = np.array([-math.sin(th), math.cos(th)])
offs = np.array(sorted(set(round(float(np.array(g.coords[0]) @ nv), 2) for g, a in zip(hz, ang) if abs(a - a0) < 2)))
dd = np.diff(offs); dd = dd[dd > 0.5]; spacing = float(np.median(dd)) if len(dd) else 3.9
lines = []
for k, i in CL:
    g = geom(P[i])
    lines.append((k, i, g.exterior if g.geom_type == 'Polygon' else g))
U = unary_union([g for _, _, g in lines])
segs = [g for g in getattr(U, 'geoms', [U]) if g.geom_type == 'LineString']
cnt = collections.Counter()
for g in segs:
    for e in (g.coords[0], g.coords[-1]): cnt[(round(e[0], 3), round(e[1], 3))] += 1
dang = [e for e, c in cnt.items() if c == 1]
st = shapely.STRtree(segs); conn = []; used_e = set()
# free ends first to each other (mutual nearest within 1.5 pt — also the two ends of one open outline), then to the nearest
# point of another line
if dang:
    DE = np.array(dang); dt_ = cKDTree(DE)
    for a in range(len(dang)):
        if a in used_e: continue
        ds, js = dt_.query(DE[a], k=min(4, len(dang)))
        for d, b in zip(np.atleast_1d(ds), np.atleast_1d(js)):
            b = int(b)
            if b == a or b in used_e or d > 1.5 or d < 1e-6: continue
            _, back = dt_.query(DE[b], k=min(4, len(dang)))
            if a in [int(x) for x in np.atleast_1d(back)]:
                conn.append(LineString([dang[a], dang[b]])); used_e |= {a, b}; break
for a, e in enumerate(dang):
    if a in used_e: continue
    p = Point(e); best = None
    for j in st.query(p.buffer(1.5)):
        d = segs[j].distance(p)
        if 1e-6 < d <= 1.5:
            q = nearest_points(p, segs[j])[1]
            if best is None or d < best[0]: best = (d, q)
    if best: conn.append(LineString([e, best[1].coords[0]]))
faces = [f for f in polygonize(unary_union(segs + conn)) if f.area >= 1.0]
def density(f): return sum(hz[j].intersection(f).length for j in ht.query(f)) / f.area
hat = [f for f in faces if density(f) >= 0.12]
blocks = unary_union([f.buffer(0.01, join_style=2) for f in hat]).buffer(-0.01, join_style=2)
blocks = [b for b in getattr(blocks, 'geoms', [blocks]) if b.geom_type == 'Polygon' and b.area >= 5.0]
# inner structure: the boundaries of hatched faces inside a block (not on its outline)
inner = unary_union([f.exterior for f in hat]).difference(unary_union([b.boundary for b in blocks]).buffer(0.05))
inner = [g for g in getattr(inner, 'geoms', [inner]) if g.geom_type == 'LineString' and g.length >= 1.0]
# lines that bound no face: inside a block (>= 80 % of it within 0.3 pt) — the block's inner structure (an open inner
# outline of a shaft's walls); elsewhere — hanging in the air
FB = unary_union([f.boundary for f in faces]).buffer(0.05) if faces else None
BZ = unary_union(blocks).buffer(0.3) if blocks else None
hang = []; hang_ids = set(); inner_open = []
for k, i, g in lines:
    if g.length <= 0: continue
    on = g.intersection(FB).length if FB is not None else 0.0
    if on >= 0.5 * g.length: continue
    if BZ is not None and g.intersection(BZ).length >= 0.8 * g.length: inner_open.append(g); continue
    hang.append(dict(at=[round(v, 1) for v in g.interpolate(0.5, normalized=True).coords[0]], length_mm=round(g.length * K), obj=k)); hang_ids.add(i)
inner += [g for g in inner_open if g.geom_type == 'LineString']
# objects: one per block
TOP = (0.75, 0.75, 0.75)
def new_prim(kind, pts, col, **kw):
    r = dict(id=len(P), layer=sheet.L1('core'), kind=kind, col=col, p=[tuple(map(float, q)) for q in pts], w=0, seq=0, alpha=1.0, synthetic=True); r.update(kw); P.append(r); return r['id']
nb = 0
for b in blocks:
    f_id = new_prim('fill', list(b.exterior.coords)[:-1], (0.35, 0.35, 0.35), holes=[list(h.coords)[:-1] for h in b.interiors],
                    pattern=('ANSI31', round(spacing * K / 3.175, 2), round((-a0) % 180, 1)))
    l_ids = [new_prim('line', list(r.coords), (0.0, 0.0, 0.0)) for r in [b.exterior, *b.interiors]]
    in_ids = [new_prim('line', list(g.coords), (0.0, 0.0, 0.0)) for g in inner if b.buffer(0.1).contains(g)]
    k = len(objs); objs.append(dict(key='coreblock', layer='A-221', kind='obj', ids=[f_id] + l_ids + in_ids,
                                    name=f'Ядро — блок существующих конструкций (шахты, стены) {round(b.area * K * K / 1e6, 1)} м²',
                                    draw=[f_id] + l_ids + in_ids, outline=[f_id] + l_ids, block_no=nb))
    for i in [f_id] + l_ids + in_ids: owner[i] = k
    nb += 1
# test 9 (Т8-18): a line of the class «partition without hatch» (lpart) that lies in a block (>= 95 % of its length within
# 0.3 pt of it) is a line of the core, not a partition: the block's inner structure (the detailed result only)
nlp = 0; lp_len = 0.0
if blocks:
    BB = [b.buffer(0.3) for b in blocks]
    for k, o in enumerate(objs):
        if o['key'] != 'lpart' or not o['ids']: continue
        gs = [(i, geom(P[i])) for i in o.get('draw', o['ids']) if live(i) and len(P[i]['p']) >= 2]
        L_ = sum(g.length for _, g in gs)
        if L_ <= 0: continue
        best = max(range(len(blocks)), key=lambda b_: sum(g.intersection(BB[b_]).length for _, g in gs))
        if sum(g.intersection(BB[best]).length for _, g in gs) < 0.95 * L_: continue
        kb = next(kk for kk, ob in enumerate(objs) if ob['key'] == 'coreblock' and ob.get('block_no') == best)
        ids_ = [i for i, _ in gs]
        objs[kb]['ids'] += ids_; objs[kb]['draw'] += ids_
        for i in ids_: owner[i] = kb
        o['ids'] = [i for i in o['ids'] if i not in set(ids_)]; o.pop('draw', None)
        if not o['ids']: o['key'] = 'empty'
        nlp += 1; lp_len += L_
print('lines of partitions inside core blocks -> the blocks\' inner structure:', nlp, f'{round(lp_len * K / 1000, 1)} m', T())
# the raw hatch and the outline lines the blocks replace are not drawn; hanging lines stay in the detailed result only
for o in objs:
    if o['key'] == 'corezone' and o['ids']: o['draw'] = []
    if o['key'] == 'coreline' and o['ids']:
        o['draw'] = [i for i in o['ids'] if i in hang_ids]; o['outline'] = []
res = dict(blocks=nb, block_area_m2=round(sum(b.area for b in blocks) * K * K / 1e6, 1), faces=len(faces), hatched_faces=len(hat),
           free_ends=len(dang), connectors=len(conn), connectors_mm=[round(c.length * K) for c in conn][:200],
           hatch_angle_deg=a0, hatch_spacing_mm=round(spacing * K), inner_lines=len(inner),
           hanging_lines=len(hang), hanging_length_m=round(sum(h['length_mm'] for h in hang) / 1000, 1), hanging=hang[:200],
           outline_length_m=round(sum(g.length for _, _, g in lines) * K / 1000, 1),
           partition_lines_into_blocks=nlp, partition_lines_into_blocks_m=round(lp_len * K / 1000, 1))
json.dump(res, open('core.json', 'w'), ensure_ascii=False, indent=1)
D1 = dict(D0); D1['P'] = P; pickle.dump(D1, open('prims_c.pkl', 'wb')); pickle.dump(O, open('objects.pkl', 'wb'))
print('core: outline lines', len(lines), f'({res["outline_length_m"]} m)', '| free ends', len(dang), '| joined by connectors', len(conn),
      '| faces', len(faces), '| hatched', len(hat), '| blocks (closed polygons)', nb, f'{res["block_area_m2"]} m²',
      '| inner lines', len(inner), '| hanging lines', len(hang), f'{res["hanging_length_m"]} m', '| hatch', a0, 'deg', res['hatch_spacing_mm'], 'mm', T())
