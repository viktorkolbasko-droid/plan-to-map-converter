"""Э7к (owner 09.10.2026, remarks З-10, З-11, З-12, З-13): classes of objects — the reception, the fire hose cabinet, a stray
line, the kitchen; and the owner's group of every object (rows 225, 238 of the registry) for the DXF and the sheets.

 З-10 «Тут на ресепшене один стул распознал, второй нет. И это не рабочие места, это именно ресепшн. Его надо относить в слой
      мебели. С обоими стульями.» — a chair is a workplace (group 4) only when the nearest table-like object within 300 mm is a
      workplace desk; a chair at a counter (стойка), closer to it than to any desk, is furniture (group 3) — both chairs of
      the reception.
 З-11 «Он встроен внутрь стены достаточно прямоугольного контура из четырех точек. Всё мелкие детали можно обрезать и считать
      их частью стены» — a fire hose cabinet (ПК) is one rectangle of four points: the smallest rotated rectangle of its
      drawing (pieces of one cabinet closer than 50 mm are one cabinet); the hose reel, the valve and the rest inside are
      dropped (the inside of the wall). The text «ПК» stays a text.
 З-12 «Разберись, почему у тебя тут появилась ненужная линия» — a straight line of another source layer (furniture), up to
      500 mm, that only touches an engineering object (convector, cabinet, sanitary ware) is not part of it: it was
      glued to the convector by touching. It leaves the object and becomes a stray line (layer A-00, group 6) — kept, the
      source loses nothing; to drop such lines is the owner's decision.
 З-13 «Внутри столовых и кофейпойнтов можно отдельно не распознавать, не выделять раковинную посудомоечную машину, включать её
      в общую встроенную технику столешницы» — a kitchen: the counter along a wall 550–700 mm deep (a kitchen section, or a
      table / sanitary section of that depth with a sink in it or touching a kitchen section), all its touching sections,
      and the sinks, dishwashers and other appliances drawn inside it — one object «Кухня встроенная» (A-76).
Reads prims (load_prims, prims_o.pkl), objects.pkl, walls; writes prims_k.pkl, objects.pkl, classes.json.
Code 012 (stage 2 of the merge of v010 into ocg/; the code of pass v010, route/e7k_classes.py) — the step of the layer route
after Э7о (ocg/run_ocg.sh):
 - the sheet from cfg (ocg/sheet.py): the scale — cfg.MM_PER_PT (v010: K = 48.04 in the code), every threshold in mm through
   it (v010 set two merge tolerances in pt: 0.02 and 0.01 pt = 0.9608 and 0.4804 mm at 48.04 mm/pt <one example: client-b,
   floor 40>; the mm here are those pt × 48.04 exactly — the same numbers on that sheet); no scale — a stop;
 - З-12, the layers of furniture: the source layers of roles 'furniture' and 'plant' of cfg.OCG_LAYERS (v010: the layer names
   containing «мебель» or «furn» — on client-b «Мебель» (furniture) and «09 FURNITURE_1» (plant), the same two layers);
 - З-13, the outline of a kitchen goes on the first source layer of role 'furniture' (v010: the layer «Мебель»), else on the
   layer of the kitchen's first primitive."""
import pickle, json, sys, time, collections, math, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import sheet
import numpy as np, shapely
from shapely.geometry import Polygon, LineString, Point
from shapely.ops import unary_union
from e7_comp import load_prims, load_walls, geom
import regular as RG, curves as CV
t0 = time.time()
def T(): return f'{time.time() - t0:.1f} s'
K = sheet.K
if not K: sys.exit('СТОП Э7к: нет масштаба листа cfg.MM_PER_PT — пороги шага в мм не перевести в pt (plan/rules/20 §3.8)')
MM = 1 / K
def mm(v): return v / K                    # a threshold in mm -> pt of the sheet
KIT_MERGE_MM = 0.9608           # the sections of a kitchen are joined by a closing of this (v010: 0.02 pt)
MULL_MERGE_MM = 0.4804          # the black fills of one facade mullion touch within this (v010: 0.01 pt)
FURN_LAYERS = sheet.L('furniture', 'plant')     # З-12: source layers of furniture (v010: names with «мебель» / «furn»)
KITCHEN_LAYER = sheet.L1('furniture')           # З-13: the layer of a kitchen's outline (v010: «Мебель»)
if not FURN_LAYERS: print('Э7к: в таблице слоёв нет слоёв ролей furniture и plant — правило З-12 (отрезок мебели у инженерного объекта) не применяется')
D = load_prims(skip=('prims_r.pkl', 'prims_k.pkl')); P = D['P']
W = load_walls(skip=('walls_r.pkl',))['bodies']
O = pickle.load(open('objects.pkl', 'rb')); objs = O['objs']
rep = collections.Counter(); places = collections.defaultdict(list)
def new_prim(layer, kind, pts, col, alpha=1.0, seq=0, **kw):
    p = dict(id=len(P), layer=layer, kind=kind, p=[tuple(map(float, v)) for v in pts], col=col, alpha=alpha, seq=seq, synthetic=True)
    if kind == 'fill': p['holes'] = []
    else: p['w'] = 0
    p.update(kw); P.append(p); return p['id']
def foot(o):
    gs = [geom(P[i]) for i in o['ids']]
    gs = [g for g in gs if not g.is_empty]
    return unary_union(gs) if gs else None
def at(g): return [round(v, 1) for v in g.representative_point().coords[0]]
# ------------------------------------------------------------------------------------------------ З-12 stray lines
ENG = {'conv', 'fire', 'san', 'sink'}
for k, o in enumerate(list(objs)):
    if o['key'] not in ENG or len(o['ids']) < 2: continue
    src = [i for i in o['ids'] if not P[i].get('synthetic')]
    if not src: continue
    main = collections.Counter(P[i]['layer'] for i in src).most_common(1)[0][0]
    for i in src:
        p = P[i]
        if p['layer'] == main or p['kind'] != 'line' or len(p['p']) != 2 or p['layer'] not in FURN_LAYERS: continue
        L = math.dist(*p['p']) * K
        if L > 500: continue
        o['ids'].remove(i)
        if 'draw' in o and i in o['draw']: o['draw'].remove(i)
        objs.append(dict(key='stray', layer='A-00', name=f'Отрезок без класса (по исходнику, слой «{p["layer"]}», {round(L)} мм)',
                         ids=[i], kind='obj', group='6'))
        rep['stray line out of an engineering object'] += 1
        places['З-12 stray'].append(dict(from_=o['key'], at=[round(v, 1) for v in p['p'][0]], length_mm=round(L), layer=p['layer']))
print('stray lines', dict(rep), T())
# ------------------------------------------------------------------------------------------------ З-11 fire hose cabinets
FIRE = [k for k, o in enumerate(objs) if o['key'] == 'fire' and o['ids']]
FG = {k: foot(objs[k]) for k in FIRE}
par = {k: k for k in FIRE}
def fnd(a):
    while par[a] != a: par[a] = par[par[a]]; a = par[a]
    return a
for a in FIRE:
    for b in FIRE:
        if a < b and FG[a] is not None and FG[b] is not None and FG[a].distance(FG[b]) * K <= 50: par[fnd(a)] = fnd(b)
grp = collections.defaultdict(list)
for k in FIRE: grp[fnd(k)].append(k)
for r, ks in grp.items():
    U = unary_union([FG[k] for k in ks if FG[k] is not None])
    m = U.minimum_rotated_rectangle
    if m.geom_type != 'Polygon': continue
    ring = RG.clean_ring(list(m.exterior.coords))
    o0 = objs[ks[0]]; sq = min(P[i]['seq'] for k in ks for i in objs[k]['ids'])
    lay = P[o0['ids'][0]]['layer']
    v0 = sum(len(P[i]['p']) for k in ks for i in objs[k]['ids'])
    f_id = new_prim(lay, 'fill', ring, (1.0, 1.0, 1.0), alpha=1.0, seq=sq)
    l_id = new_prim(lay, 'line', ring + [ring[0]], (0.85, 0.0, 0.0), seq=sq, closed=True)
    o0['ids_src'] = [i for k in ks for i in objs[k]['ids']]; o0['ids'] = [f_id, l_id]; o0['draw'] = [f_id, l_id]
    o0['name'] = 'Шкаф пожарный ПК (по исходнику): прямоугольник ниши, детали внутри — устройство стены'
    for k in ks[1:]: objs[k]['ids'] = []; objs[k]['key'] = 'empty'
    xs = ring; a_, b_ = math.dist(xs[0], xs[1]) * K, math.dist(xs[1], xs[2]) * K
    places['З-11 ПК'].append(dict(at=at(m), pieces=len(ks), points_before=v0, size_mm=[round(max(a_, b_)), round(min(a_, b_))]))
    rep['ПК: one rectangle'] += 1
print('fire cabinets', rep['ПК: one rectangle'], T())
# ------------------------------------------------------------------------------------------------ З-13 kitchens
WU = unary_union([g for c, g in W])
FT = {k: foot(o) for k, o in enumerate(objs) if o['key'] in ('kitchen', 'sink', 'san', 'mtable', 'dtable', 'table', 'equip', 'counter') and o['ids']}
def depth_mm(g):
    m = g.minimum_rotated_rectangle
    if m.geom_type != 'Polygon': return None, None
    xs = list(m.exterior.coords); a_, b_ = math.dist(xs[0], xs[1]) * K, math.dist(xs[1], xs[2]) * K
    return min(a_, b_), max(a_, b_)
KIT = {k for k in FT if objs[k]['key'] == 'kitchen'}
SINK = {k for k in FT if objs[k]['key'] == 'sink'}
changed = True
while changed:                                   # a counter section 550–700 mm deep along a wall with a sink or next to a kitchen
    changed = False
    for k, g in FT.items():
        if k in KIT or objs[k]['key'] not in ('san', 'mtable', 'dtable', 'table', 'counter') or g is None: continue
        d_, L_ = depth_mm(g)
        if d_ is None or not (550 <= d_ <= 700) or L_ < 500: continue
        if g.distance(WU) * K > 60: continue                             # along a wall
        has_sink = any(FT[s] is not None and g.buffer(2 * MM).contains(FT[s].centroid) for s in SINK) or objs[k]['key'] == 'san'
        near_kit = any(FT[j] is not None and g.distance(FT[j]) * K <= 30 for j in KIT)
        if has_sink or near_kit:
            places['З-13 counter is a kitchen'].append(dict(was=objs[k]['key'], name=objs[k]['name'], at=at(g), depth_mm=round(d_), length_mm=round(L_)))
            objs[k]['name_before_kitchen'] = objs[k]['name']; objs[k]['key'] = 'kitchen'; objs[k]['layer'] = 'A-76'
            KIT.add(k); changed = True; rep['counter section -> kitchen'] += 1
# touching sections — one kitchen; the sinks and appliances inside — parts of it
par = {k: k for k in KIT}
for a in KIT:
    for b in KIT:
        if a < b and FT[a].distance(FT[b]) * K <= 30: par[fnd(a)] = fnd(b)
grp = collections.defaultdict(list)
for k in KIT: grp[fnd(k)].append(k)
def part_order(k):
    """the order of the parts of a kitchen — by the source drawing (the smallest seq and id of the part's primitives), not by the
    number of the object nor by the order of a set (owner 10.10.2026, №125: «выбор не зависит от номеров объектов»)"""
    ids = objs[k]['ids']
    return (min(P[i]['seq'] for i in ids), min(ids)) if ids else (math.inf, math.inf)
for r, ks in sorted(grp.items(), key=lambda kv: min(part_order(k) for k in kv[1])):
    ks = sorted(ks, key=part_order)
    U = unary_union([FT[k].buffer(mm(KIT_MERGE_MM), join_style=2) for k in ks]).buffer(-mm(KIT_MERGE_MM), join_style=2)
    inside = sorted([s for s in set(SINK) | {j for j in FT if objs[j]['key'] == 'equip'}
                     if FT[s] is not None and objs[s]['ids'] and U.buffer(3 * MM).contains(FT[s])], key=part_order)
    if len(ks) == 1 and not inside: continue
    # owner 10.10.2026, №125 «Как части — вид 012»: «Рисуется то, что рисовали части; габарит кухни — только в габаритном
    # результате; выбор не зависит от номеров объектов». The detailed result draws the union of what the parts drew (each part's
    # 'draw', or all its primitives when it has none), whatever part keeps the object; the габарит (fill + outline, below) goes to
    # 'outline' only (v010: the first part in the order of the set KIT kept the object, and a first part without 'draw' made the
    # detailed result draw every primitive of every part and the габарит — the drawing depended on the numbers of the objects).
    parts = ks + inside
    host = ks[0]; o0 = objs[host]
    ids_all, drawn, seen_i, seen_d = [], [], set(), set()
    part_rec = []
    for k in parts:
        o_ = objs[k]; dr = o_.get('draw', o_['ids'])
        part_rec.append(dict(key=o_['key'], name=o_.get('name_before_kitchen') or o_.get('name'), own_draw='draw' in o_,
                             prims=len(o_['ids']), drawn=len(dr)))
        ids_all += [i for i in o_['ids'] if not (i in seen_i or seen_i.add(i))]
        drawn += [i for i in dr if not (i in seen_d or seen_d.add(i))]
    o0['ids'] = ids_all; o0['draw'] = drawn
    for k in parts[1:]:
        objs[k]['ids'] = []; objs[k]['key'] = 'empty'
    # one outline (габарит): the union of the sections, its rectangle when it is one
    U2 = U if U.geom_type == 'Polygon' else max(U.geoms, key=lambda q: q.area)
    rr = RG.rectangle_of(U2, 15 * MM)
    ring = RG.clean_ring(list((rr if rr is not None else U2).exterior.coords))
    sq = min(P[i]['seq'] for i in o0['ids'])
    lay_k = KITCHEN_LAYER or P[o0['ids'][0]]['layer']
    f_id = new_prim(lay_k, 'fill', ring, (1.0, 1.0, 1.0), alpha=1.0, seq=sq)
    l_id = new_prim(lay_k, 'line', ring + [ring[0]], (0.0, 0.0, 0.0), seq=sq, closed=True)
    o0['ids'] += [f_id, l_id]; o0['outline'] = [f_id, l_id]
    d_, L_ = depth_mm(U2)
    o0['name'] = f'Кухня встроенная: столешница {round(L_ / 50) * 50}×{round(d_ / 50) * 50} с мойкой и техникой (по исходнику)' if inside or \
        any(objs[k].get('name_before_kitchen') for k in ks) else f'Кухня встроенная: {len(ks)} секции, {round(L_ / 50) * 50}×{round(d_ / 50) * 50} (по исходнику)'
    places['З-13 kitchen'].append(dict(at=at(U2), sections=len(ks), parts_inside=[objs[s].get('name') for s in inside], size_mm=[round(L_), round(d_)],
                                       parts=part_rec, drawn=len(drawn), prims=len(o0['ids'])))
    rep['kitchens: one object'] += 1; rep['sinks and appliances merged into a kitchen'] += len(inside)
print('kitchens', dict((k, v) for k, v in rep.items() if 'kitchen' in k or 'sink' in k), T())
# ------------------------------------------------------------------------------------------------ З-5 facade glazing
# Owner: «опорные конструкции… все однотипные, одинакового размера и одинаковой формы. И в идеале они должны получиться в четыре
# точки… свести к одной фигуре… проверить друг на друга на размер. И линия стекла… от опоры к опоре… Выявлять структуру и размер
# секций и приводить к собиранию по возможности одинаковых секций.»
#  1. a mullion — the touching black fills of the facade frame; its smallest rotated rectangle;
#  2. mullions of one size within MUL_TOL (15 mm) — one type: the median size, every one of them that rectangle (4 points) at its
#     own centre and angle; a mullion of its own size stays its own rectangle (no unique shapes of dozens of points);
#  3. a section — the glass between two neighbouring mullions; a straight run of sections (direction within 2°) whose lengths
#     differ less than SEC_TOL from their mean — equal sections: the inner mullions are spaced evenly between the end ones
#     (moved at most SEC_MOVE), the glass goes from mullion face to mullion face.
MUL_TOL = 15.0; SEC_TOL = 0.02; SEC_MOVE = 40.0          # mm, share, mm
FR = [k for k, o in enumerate(objs) if o['key'] == 'facade' and o.get('name', '').startswith('Витраж фасадный: рама')]
GLS = [k for k, o in enumerate(objs) if o['key'] == 'facade' and o.get('name', '').startswith('Витраж фасадный: остекление')]
mull = []                                                 # dict(c, u, w, l, ids, frame)
for k in FR:
    o = objs[k]
    fi = [i for i in o['ids'] if P[i]['kind'] == 'fill' and len(P[i]['p']) >= 3]
    G = [(i, Polygon(P[i]['p'], P[i].get('holes', [])).buffer(0)) for i in fi]
    G = [(i, g) for i, g in G if not g.is_empty]
    if not G: continue
    U = unary_union([g.buffer(mm(MULL_MERGE_MM)) for i, g in G])
    for q in getattr(U, 'geoms', [U]):
        mem = [i for i, g in G if q.intersects(g)]
        m = q.minimum_rotated_rectangle
        if m.geom_type != 'Polygon': continue
        xs = np.array(m.exterior.coords)[:4]; e1, e2 = xs[1] - xs[0], xs[2] - xs[1]
        if np.linalg.norm(e1) < np.linalg.norm(e2): e1, e2 = e2, e1
        L_, W_ = np.linalg.norm(e1) * K, np.linalg.norm(e2) * K
        if L_ > 600: continue                                # not a mullion (a long frame piece)
        mull.append(dict(c=xs.mean(0), u=e1 / np.linalg.norm(e1), l=L_, w=W_, ids=mem, frame=k,
                         seq=min(P[i]['seq'] for i in mem), col=P[mem[0]]['col'], alpha=P[mem[0]].get('alpha', 1.0)))
# types by size: single linkage in (width, length) at 10 mm, a type no wider than 2 MUL_TOL
order = sorted(range(len(mull)), key=lambda j: (mull[j]['w'], mull[j]['l']))
par_m = list(range(len(mull)))
def fm(a):
    while par_m[a] != a: par_m[a] = par_m[par_m[a]]; a = par_m[a]
    return a
for x in range(len(mull)):
    for y in range(x + 1, len(mull)):
        if abs(mull[x]['w'] - mull[y]['w']) <= 10 and abs(mull[x]['l'] - mull[y]['l']) <= 10: par_m[fm(x)] = fm(y)
tg = collections.defaultdict(list)
for j in range(len(mull)): tg[fm(j)].append(j)
types = []
for mem in tg.values():
    W_ = [mull[j]['w'] for j in mem]; L_ = [mull[j]['l'] for j in mem]
    if max(W_) - min(W_) > 2 * MUL_TOL or max(L_) - min(L_) > 2 * MUL_TOL:      # a chain of sizes too long: each its own type
        for j in mem: types.append(dict(mem=[j]))
    else: types.append(dict(mem=mem))
for t in types:
    t['w'] = float(np.median([mull[j]['w'] for j in t['mem']])); t['l'] = float(np.median([mull[j]['l'] for j in t['mem']]))
    for j in t['mem']: mull[j]['tw'], mull[j]['tl'] = t['w'], t['l']
def mrect(m):
    u = m['u']; v = np.array([-u[1], u[0]]); hl, hw = m['tl'] / K / 2, m['tw'] / K / 2; c = m['c']
    return [tuple(c + a * u * hl + b * v * hw) for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
# glass lines and the mullions at their ends
MT = shapely.STRtree([Polygon(mrect(m)) for m in mull]) if mull else None
secs = []                                                 # dict(k, i, a, b, ma, mb)
for k in GLS:
    o = objs[k]
    for i in o['ids']:
        p = P[i]
        if p['kind'] != 'line' or len(p['p']) < 2: continue
        a, b = np.array(p['p'][0], float), np.array(p['p'][-1], float)
        def near(q):
            best = None
            for j in MT.query(Point(q).buffer(300 / K)):
                d = Polygon(mrect(mull[j])).distance(Point(q)) * K
                if d <= 300 and (best is None or d < best[0]): best = (d, j)
            return best[1] if best else None
        secs.append(dict(k=k, i=i, a=a, b=b, ma=near(a), mb=near(b)))
# straight runs of sections: a chain of mullions through the glass lines
nb = collections.defaultdict(list)
for s_ in secs:
    if s_['ma'] is not None and s_['mb'] is not None and s_['ma'] != s_['mb']:
        nb[s_['ma']].append(s_['mb']); nb[s_['mb']].append(s_['ma'])
moved = []; runs_eq = []
seen_m = set()
for st0 in list(nb):
    if st0 in seen_m: continue
    chain = [st0]; seen_m.add(st0)                       # walk both ways: a facade that closes on itself is a loop
    for side in (0, 1):
        cur = st0; prev = None if side == 0 or len(chain) < 2 else chain[1]
        part = []
        while True:
            nxt = [x for x in nb[cur] if x != prev and x not in seen_m]
            if not nxt: break
            prev, cur = cur, nxt[0]; part.append(cur); seen_m.add(cur)
        chain = chain + part if side == 0 else part[::-1] + chain
    # runs: split at a corner (a turn over 10°) and where the section length changes (more than SEC_TOL from the run's median)
    C = [mull[j]['c'] for j in chain]
    arcs = [[chain[0]]]
    for q in range(1, len(chain)):
        if len(arcs[-1]) >= 2:
            d1 = C[q - 1] - C[q - 2]; d2 = C[q] - C[q - 1]
            if abs(math.degrees(math.atan2(d1[0] * d2[1] - d1[1] * d2[0], d1 @ d2))) > 10: arcs.append([chain[q - 1]])
        arcs[-1].append(chain[q])
    for arc in arcs:
        run = [arc[0]]
        def flush(run):
            if len(run) < 4: return
            Cr = np.array([mull[j]['c'] for j in run]); sl = np.linalg.norm(np.diff(Cr, axis=0), axis=1) * K
            f = CV.circle(Cr * K)                                   # the facade of this run: an arc (or a line)
            pos = None
            if f is not None and f[3] <= 15 and f[2] > 5000:
                cx, cy, r, _ = f; cc = np.array([cx, cy]) / K
                a0 = math.atan2(*(Cr[0] - cc)[::-1]); a1 = math.atan2(*(Cr[-1] - cc)[::-1])
                da = (a1 - a0 + math.pi) % (2 * math.pi) - math.pi
                pos = [cc + (r / K) * np.array([math.cos(a0 + da * t), math.sin(a0 + da * t)]) for t in np.linspace(0, 1, len(run))]
                rad = [(p_ - cc) / np.linalg.norm(p_ - cc) for p_ in pos]
            else:
                d = Cr[-1] - Cr[0]; e = d / np.linalg.norm(d); off = np.abs((Cr - Cr[0]) @ np.array([-e[1], e[0]])) * K
                if off.max() > 15: return
                pos = [Cr[0] + d * t for t in np.linspace(0, 1, len(run))]; rad = [np.array([-e[1], e[0]])] * len(run)
            sh = [np.linalg.norm(p_ - mull[j]['c']) * K for p_, j in zip(pos, run)]
            if max(sh) > SEC_MOVE: return
            for j, p_, rd in zip(run, pos, rad):
                moved.append(round(float(np.linalg.norm(mull[j]['c'] - p_) * K), 1)); mull[j]['c'] = np.array(p_)
                u = mull[j]['u']
                if abs(abs(float(u @ rd)) - 1) < 1 - math.cos(math.radians(10)): mull[j]['u'] = rd if u @ rd > 0 else -rd
            runs_eq.append(dict(at=[round(v, 1) for v in Cr[0]], sections=len(run) - 1, length_mm=round(float(sl.mean())),
                                spread_before_mm=round(float(sl.max() - sl.min()), 1), max_move_mm=round(max(sh), 1)))
        for j in arc[1:]:
            L_new = math.dist(mull[run[-1]]['c'], mull[j]['c']) * K
            Ls = [math.dist(mull[x]['c'], mull[y]['c']) * K for x, y in zip(run[:-1], run[1:])]
            if Ls and abs(L_new - float(np.median(Ls))) > SEC_TOL * float(np.median(Ls)): flush(run); run = [run[-1]]
            run.append(j)
        flush(run)
# write the mullions (one object each, one type — one figure) and the glass from mullion face to mullion face
for j, m in enumerate(mull):
    fr = objs[m['frame']]
    for i in m['ids']:
        if i in fr['ids']: fr['ids'].remove(i)
        if 'draw' in fr and i in fr['draw']: fr['draw'].remove(i)
    ring = mrect(m)
    f_id = new_prim(P[m['ids'][0]]['layer'], 'fill', ring, m['col'], alpha=m['alpha'], seq=m['seq'])
    l_id = new_prim(P[m['ids'][0]]['layer'], 'line', ring + [ring[0]], (0.0, 0.0, 0.0), seq=m['seq'], closed=True)
    objs.append(dict(key='mullion', layer='A-31', name=f"Витраж фасадный: стойка {round(m['tl'])}×{round(m['tw'])} (одна фигура типа)",
                     ids=[f_id, l_id], draw=[f_id, l_id], kind='obj', group='1'))
def face_hit(q, d, j):
    """the point where the glass line through q (direction d, pointing into the section) meets mullion j's face"""
    poly = Polygon(mrect(mull[j]))
    ln = LineString([tuple(q - d * 400 / K), tuple(q + d * 400 / K)])
    x = poly.exterior.intersection(ln)
    pts = [np.array(g.coords[0]) for g in getattr(x, 'geoms', [x]) if not g.is_empty and g.geom_type == 'Point']
    if not pts: return None
    return max(pts, key=lambda p_: (p_ - q) @ d)            # the face on the section's side
ng = 0
for s_ in secs:
    if s_['ma'] is None or s_['mb'] is None: continue
    a, b = s_['a'], s_['b']; d = (b - a) / np.linalg.norm(b - a)
    a2 = face_hit(a, d, s_['ma']); b2 = face_hit(b, -d, s_['mb'])
    if a2 is None or b2 is None: continue
    P[s_['i']]['p'] = [tuple(a2), tuple(b2)]; ng += 1
lens = collections.Counter(round(math.dist(*P[s_['i']]['p']) * K / 10) * 10 for s_ in secs if s_['ma'] is not None and s_['mb'] is not None)
rep['facade mullions'] = len(mull); rep['facade mullion types'] = len(types); rep['facade glass from mullion to mullion'] = ng
rep['facade runs of equal sections'] = len(runs_eq)
places['З-5 mullion types'] = [dict(size_mm=[round(t['l']), round(t['w'])], count=len(t['mem']),
                                     spread_mm=[round(max(mull[j]['l'] for j in t['mem']) - min(mull[j]['l'] for j in t['mem']), 1),
                                                round(max(mull[j]['w'] for j in t['mem']) - min(mull[j]['w'] for j in t['mem']), 1)]) for t in types]
places['З-5 equal-section runs'] = runs_eq
places['З-5 section lengths'] = sorted(([L, n] for L, n in lens.items()), key=lambda x: -x[1])
places['З-5 mullion moves mm'] = dict(max=max(moved) if moved else 0, mean=round(float(np.mean(moved)), 1) if moved else 0, n=len(moved))
print('facade: mullions', len(mull), 'types', [(round(t['l']), round(t['w']), len(t['mem'])) for t in types], '| glass', ng,
      '| equal runs', len(runs_eq), T())

# ------------------------------------------------------------------------------------------------ groups (rows 225, 238) and З-10
GROUP = {'glass': '1', 'lpart': '1', 'facade': '1', 'mullion': '1', 'coreblock': '1', 'coreline': '1', 'wallline': '1',
         'door': '2', 'lift': '2',
         'mtable': '3', 'rtable': '3', 'sofa': '3', 'armchair': '3', 'round': '3', 'dtable': '3', 'ctable': '3', 'storage': '3',
         'pedestal': '3', 'table': '3', 'booth': '3', 'kitchen': '3', 'counter': '3', 'mfp': '3', 'equip': '3', 'plant': '3',
         'sink': '3', 'chair': '3', 'chairpart': '3', 'group': '3', 'furn': '3',
         'desk': '4',
         'conv': '5', 'fire': '5', 'san': '5',
         'stray': '6',
         'zone': '8', 'corezone': '8', 'shaft': '8', 'roomsep': '8', 'dim': '8', 'measure': '8', 'tagc': '8', 'axis': '8', 'mark': '8'}
TABLES = {k: foot(o) for k, o in enumerate(objs) if o['key'] in ('desk', 'counter', 'mtable', 'dtable', 'table', 'ctable', 'rtable', 'kitchen') and o['ids']}
TT = list(TABLES.items()); TTree = shapely.STRtree([g for k, g in TT]) if TT else None
for k, o in enumerate(objs):
    if o['key'] == 'empty' or not o['ids']: continue
    g_ = GROUP.get(o['key'], '6')
    if o['key'] in ('chair', 'chairpart') and TTree is not None:
        f = foot(o)
        near = []
        for j in TTree.query(f.buffer(300 * MM)):
            kk, tg = TT[j]
            d = f.distance(tg) * K
            if d <= 300: near.append((d, objs[kk]['key'], kk))
        near.sort()
        if near and near[0][1] == 'desk': g_ = '4'
        elif near and near[0][1] == 'counter' and any(n[1] == 'desk' for n in near):
            rep['chairs at a counter (reception) — furniture, not a workplace'] += 1
            places['З-10 reception chairs'].append(dict(at=at(f), counter=objs[near[0][2]]['name'], desk_mm=round(next(n[0] for n in near if n[1] == 'desk'))))
    o['group'] = g_
rep.update({f'group {g}': v for g, v in collections.Counter(o.get('group') for o in objs if o['key'] != 'empty' and o['ids']).items()})
print('groups', {k: v for k, v in rep.items() if k.startswith('group') or 'reception' in k}, T())
# ------------------------------------------------------------------------------------------------ write
D2 = dict(D); D2['P'] = P; pickle.dump(D2, open('prims_k.pkl', 'wb'))
pickle.dump(O, open('objects.pkl', 'wb'))
json.dump(dict(report=dict(rep), places={k: v for k, v in places.items()}), open('classes.json', 'w'), ensure_ascii=False, indent=1)
print('written prims_k.pkl, objects.pkl, classes.json', T())
