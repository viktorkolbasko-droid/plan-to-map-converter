# Gate 7 (code 007, draft): the owner's review of the layer sheets of floor 4 of client A (03.10.2026) as checks.
# proposals/plan/2026-10-03-клиент А-4-разбор-слоёв-владельцем.md, пп. 240-266. Each check finds the kind of error the
# owner found by eye; every place goes to gate7.json with its coordinates (pt, PDF display space) and the reason.
#   S15* face of a wall / partition continued in the source by a line of a foreign owner - a gap in its layer (п. 242)
#   S16* layer contour against the source: a free end in the walls-and-partitions layer where the source goes on,
#        and a short piece between two faces that went to another class (п. 243: "почему разрыв прошёл проверку")
#   S17* seat without a table within 250 mm (п. 244)
#   S18* partition hanging in the air, between a seat and a table, along or across furniture (пп. 245, 258, 259)
#   S19* closed rectangle of furniture size drawn by fallback lines, end cells of rows (пп. 246, 247)
#   S20* family template: columns (I-beam, round) and sanitary fixtures of one family are alike (пп. 248, 253, 264)
#   S21* I-beam columns along a wall in pairs; I-beam-like clusters of thick lines that are not columns (п. 249)
#   S22* doors: recognised, nothing in the swing or across the opening, jambs at both edges (п. 250); a glass door - the
#        glass line cut in the DXF, the door in the glass style (строка 172)
#   S23* walls over furniture, structural lines inside furniture and stairs, wall faces in WC accessories (пп. 251,
#        252, 262, 265)
#   S24* glazing rhythm: pieces of another type wedged into a run of glazing (п. 254)
#   S25* one continuous wall - one type (п. 261)
#   S26* a stroke inside a recognised object left unclassified (п. 266)
#   S27* openings A-23: every stair that passes this floor's slab inside a stair-cell outline, none where the slab has
#        no opening (a flight only up, a short flight outside a cage - строка 173), outlines closed, not over walls (п. 263)
#   S28* every partition has a type (п. 260)
#   S29* an operator box (MANUAL) took an edge of a neighbouring object (п. 257)
# Ownership: own7.Own - an instance owns 'prims' and also draws 'shared' (a boundary line of several objects, п. 240).
# Exit 1 when a stop is left; cfg.GATE7_ACCEPT = {'S18*': dict(max=N, why='...')} accepts what was looked at.
#   python3 checks/gate7.py [out.json]        (floor folder)
import os, sys, json, pickle, math, collections, re, statistics, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import cfg, pts, MM_PER_PT, bez
from own7 import *
from shapely.geometry import LineString, Point, MultiPoint, Polygon, box
from shapely.ops import unary_union, polygonize
from shapely.strtree import STRtree
from shapely.prepared import prep
t0 = time.time()
OUTF = sys.argv[1] if len(sys.argv) > 1 else 'gate7.json'
P, cls, I, WP, W = load_all()
O = Own(I, WP)
X0, Y0, X1, Y1 = cfg.WIN
PT = 1 / MM_PER_PT                                       # pt per mm
NOTDRAW = ('sheet', 'axis', 'dim')
R = collections.OrderedDict()
def rnd(p): return [round(p[0], 1), round(p[1], 1)]
def rec(code, title, stop=True): R[code] = dict(title=title, stop=stop, n=0, spots=[], by=collections.Counter()); return R[code]
def add(code, at, why, kind=None, **kw):
    r = R[code]; r['n'] += 1; r['by'][kind or why] += 1
    if len(r['spots']) < 400: r['spots'].append(dict(at=rnd(at), why=why, kind=kind or why, **kw))
# ---------------- geometry
L = []                                                  # (prim, a, b): straight lines of the drawing
for i, p in enumerate(P):
    if p[0] != 'l' or cls[i] in NOTDRAW: continue
    a, b = p[4][0], p[4][-1]
    if math.dist(a, b) < 0.3: continue
    if not (X0 <= a[0] <= X1 and Y0 <= a[1] <= Y1): continue
    L.append((i, a, b))
G = [LineString([a, b]) for i, a, b in L]; T = STRtree(G)
KEYS = [O.keys(i) for i, a, b in L]
WB = [(c, g) for c, v in W.items() for p in v for g in getattr(p, 'geoms', [p])]
WU = unary_union([g for c, g in WB]) if WB else Polygon()
WUp = prep(WU.buffer(0.15)) if not WU.is_empty else None
WBND = unary_union([g.boundary for c, g in WB]) if WB else None
WBNDp = prep(WBND.buffer(0.15)) if WBND is not None else None
def near(pt, tol=0.15, skip=None):
    g = Point(pt)
    return [n for n in T.query(g.buffer(tol)) if n != skip and G[n].distance(g) <= tol]
def ukey(ks):                                          # a readable owner of a key set
    for k in ('WALL', 'facade', 'glass', 'gklpart', 'glasspart', 'railing', 'lpart', 'lpartc', 'wallline'):
        if k in ks: return k
    return sorted(ks)[0]
INST_HULL = {}
def ihull(k):
    if k not in INST_HULL:
        q = I[k]; ids = list(q['prims']) + list(q.get('shared', []))
        h = None
        if q.get('poly'): h = Polygon(q['poly'])
        elif ids: h = hull_of(P, ids)
        INST_HULL[k] = h
    return INST_HULL[k]
IOWN = {}
def ihull_own(k):
    """the hull of an object's own primitives (a boundary line it shares with a wall does not widen it)"""
    if k not in IOWN:
        q = I[k]; IOWN[k] = hull_of(P, list(q['prims'])) if q['prims'] else None
    return IOWN[k]
def inst_of(keys):
    return [k for k, q in enumerate(I) if q['key'] in keys and (q['prims'] or q.get('shared') or q.get('poly'))]
print('lines', len(L), 'walls', len(WB), round(time.time() - t0, 1), 's')
# ======================================================================================== S15* / S16*
rec('S15*', 'грань стены или перегородки продолжается в исходнике тем же пером, но линией чужого объекта — в слое разрыв (п. 242)')
rec('S16*', 'контур слоя стен и перегородок против исходника: в слое конец, а в исходнике контур идёт дальше тем же пером (п. 243)')
def pen(i): return (round(P[i][1] or 0, 2), P[i][2])
def loc(e): return (round(e[0] * 2) / 2, round(e[1] * 2) / 2)
L1 = [n for n in range(len(L)) if KEYS[n] & LAYER1]
OKCONT = LAYER1 | OPENING_KEYS | {'roomsep'}
FURNISH = FURN | SEATS | {'screen', 'fscreen', 'plant'}
S15 = {}
for a in L1:
    i, p0, p1 = L[a]
    if G[a].length < 1.0: continue
    for e, o in ((p0, p1), (p1, p0)):
        u = unit(o, e)
        for b in near(e, 0.15, a):
            j, q0, q1 = L[b]
            if KEYS[b] & OKCONT or pen(j) != pen(i): continue
            if WBNDp is not None and WBNDp.contains(G[b]): continue
            v = unit(q0, q1)
            if abs(u[0] * v[0] + u[1] * v[1]) < 0.995: continue
            if max((q0[0] - e[0]) * u[0] + (q0[1] - e[1]) * u[1], (q1[0] - e[0]) * u[0] + (q1[1] - e[1]) * u[1]) <= 0.2: continue
            if loc(e) in S15: continue
            kb = ukey(KEYS[b]); S15[loc(e)] = kb
            kind = 'грань переходит в мебель' if KEYS[b] & FURNISH else 'кусок грани у чужого: ' + kb
            add('S15*', e, f'грань «{ukey(KEYS[a])}» продолжает линия «{kb}» тем же пером', kind=kind, len=round(G[b].length, 1))
S16 = set()
# a line along a column (its outline, a tick on it) is the column's, not a continuation of the layer's contour (п. 248)
_COLH = [h for h in (ihull_own(k) for k in inst_of({'column'})) if h is not None]
_COLT = STRtree([h.buffer(0.3) for h in _COLH]) if _COLH else None
def along_column(g):
    if _COLT is None: return False
    return any(_COLH[j].buffer(0.3).intersection(g).length >= 0.8 * g.length for j in _COLT.query(g))
CORNER_FB = {'loose', 'misc', 'FREE', 'mark', 'sign'}
def collinear(a, b):
    u = unit(L[a][1], L[a][2]); v = unit(L[b][1], L[b][2]); return abs(u[0] * v[0] + u[1] * v[1]) >= 0.995
def bridges(b, e):
    """a corner piece of an object continues the contour only when its far end holds on structure (a wall stub between a
    column and a wall); the side of an accessory hung on a wall ends at the accessory"""
    q0, q1 = L[b][1], L[b][2]; far = q1 if math.dist(q0, e) <= math.dist(q1, e) else q0
    if any(KEYS[x] & STRUCT_END for x in near(far, 0.15, b)): return True
    return WUp is not None and WUp.contains(Point(far))
for a in L1:
    i, p0, p1 = L[a]
    if G[a].length < 0.5: continue
    for e in (p0, p1):
        if loc(e) in S15 or loc(e) in S16: continue
        nb = near(e, 0.15, a)
        if any(KEYS[b] & STRUCT_END for b in nb): continue
        if WBNDp is not None and WBNDp.contains(Point(e)): continue
        if WUp is not None and WUp.contains(Point(e)) and 'WALL' not in KEYS[a]: continue
        same = [b for b in nb if pen(L[b][0]) == pen(i) and not (KEYS[b] & OKCONT) and not (WBNDp is not None and WBNDp.contains(G[b]))
                and G[b].intersection(G[a].buffer(0.25)).length < 0.8 * G[b].length          # a duplicate of the face drawn over it is not a gap
                and not along_column(G[b])
                and (KEYS[b] <= CORNER_FB or collinear(a, b) or bridges(b, e))]
        if not same: continue
        S16.add(loc(e)); kb = ukey(set().union(*[KEYS[b] for b in same]))
        add('S16*', e, f'конец «{ukey(KEYS[a])}»: в исходнике контур идёт дальше линией «{kb}», в слое — обрыв',
            kind='грань переходит в мебель' if any(KEYS[b] & FURNISH for b in same) else 'обрыв: ' + kb)
print('S15/S16', R['S15*']['n'], R['S16*']['n'], round(time.time() - t0, 1), 's')
# ======================================================================================== S17*
rec('S17*', 'сиденье без стола ближе 250 мм (п. 244): офисные кресла и стулья переговорных — стоп, мягкая мебель — на просмотр')
# (code 007, regression of 06.10.2026) a seat's table is any work surface: a bar counter for bar stools (floor 5 of client A:
#   9 bar stools 155 mm from 'Барная стойка' stopped as 'seat without a table'), a coffee table for soft seats
SEAT_SURF = TABLES | {'kitchen', 'ctable', 'counter'}
TB = [(k, ihull(k)) for k in inst_of(SEAT_SURF)]; TB = [(k, h) for k, h in TB if h is not None]
TT = STRtree([h for k, h in TB])
GAP = 250 * PT
SEATB = []
for k in inst_of(SEATS):
    q = I[k]; b = q.get('bbx')
    h = box(*b) if b else ihull(k)
    if h is None: continue
    SEATB.append((k, h))
    d = min([TB[j][1].distance(h) for j in TT.query(h.buffer(GAP + 30))] or [999])
    if d > GAP:
        soft = q['key'] in ('armchair', 'sofa')
        add('S17*', (h.centroid.x, h.centroid.y), f'{q["name"][:40]}: ' + (f'стол дальше {d * MM_PER_PT:.0f} мм' if d < 999 else f'стола ближе {(GAP + 30) * MM_PER_PT:.0f} мм нет'),
            kind='мягкая мебель' if soft else 'кресло или стул', soft=soft)
soft_n = R['S17*']['by'].get('мягкая мебель', 0)
print('S17', R['S17*']['n'], 'soft', soft_n, round(time.time() - t0, 1), 's')
# ======================================================================================== S18*
rec('S18*', 'перегородка висит в воздухе, стоит между сиденьем и столом, по краю или поперёк мебели (пп. 245, 258, 259)')
PL = [n for n in range(len(L)) if KEYS[n] & PART]
par = {n: n for n in PL}
def fnd(x):
    while par[x] != x: par[x] = par[par[x]]; x = par[x]
    return x
PLs = set(PL)
for a in PL:
    for b in T.query(G[a].buffer(0.15)):
        if b in PLs and b != a and G[a].distance(G[b]) <= 0.15: par[fnd(a)] = fnd(b)
comp = collections.defaultdict(list)
for n in PL: comp[fnd(n)].append(n)
ANCH = (STRUCT_END - PART) | {'fire'}                    # a built-in fire cabinet stands in the wall line
FH = [(k, ihull_own(k)) for k in inst_of(FURN)]; FH = [(k, h) for k, h in FH if h is not None and h.area >= 2]
FT = STRtree([h for k, h in FH])
ST = STRtree([h for k, h in SEATB]) if SEATB else None
hang = set()
OPG = [Polygon(q['poly']) for q in I if q['key'] == 'opening' and q.get('poly')]
SANZ7 = unary_union([box(*z).buffer(2.0) for z in getattr(cfg, 'SANZONES', [])]) if getattr(cfg, 'SANZONES', []) else None
for c, ns in comp.items():
    anch = False
    for a in ns:
        for b in T.query(G[a].buffer(0.5)):
            if b in PLs: continue
            d_ = G[a].distance(G[b])
            if KEYS[b] & ANCH and d_ <= 0.5: anch = True; break
        if anch: break
        if WU is not None and not WU.is_empty and G[a].distance(WU) <= 0.5: anch = True; break
        if 'railing' in KEYS[a] and any(o.exterior.distance(G[a]) <= 3.0 for o in OPG): anch = True; break   # the railing of an opening
    if anch: continue
    g = unary_union([G[a] for a in ns]); c_ = g.centroid
    # (code 007, regression of 06.10.2026) the partitions of WC cabins hold on to the line of the installation frame, not to a
    #   wall body: a component lying >= 70 % in an operator's washroom box (cfg.SANZONES) is not 'hanging' (floor 5 of client A:
    #   59 places of the cabins, 150 mm off the wall; fix7 F3 made them 'accessories' before - FIX7_WC_PIECES)
    if SANZ7 is not None and g.intersection(SANZ7).length >= 0.7 * g.length: continue
    for a in ns: hang.add(a)
    ds = min([SEATB[j][1].distance(g) for j in ST.query(g.buffer(3))] or [99]) if ST else 99
    dt = min([TB[j][1].distance(g) for j in TT.query(g.buffer(3))] or [99])
    kind = 'между сиденьем и столом' if ds <= 3 and dt <= 3 else 'висит в воздухе'
    add('S18*', (c_.x, c_.y), f'{len(ns)} линий, {g.length:.1f} pt: ни один конец не касается стены, колонны, двери, стекла, фасада', kind=kind)
def end_free(a):
    for e in (L[a][1], L[a][2]):
        if not any(KEYS[b] & STRUCT_END for b in near(e, 0.3, a)) and not (WU is not None and not WU.is_empty and Point(e).distance(WU) <= 0.5): return True
    return False
on_furn = 0
for a in PL:
    if a in hang or G[a].length < 2: continue
    for j in FT.query(G[a].buffer(0.4)):
        k, h = FH[j]
        on_edge = G[a].intersection(h.exterior.buffer(0.4)).length / G[a].length
        inner = h.buffer(-0.5); across = G[a].intersection(inner).length / G[a].length if not inner.is_empty else 0
        if (on_edge >= 0.5 or across >= 0.5) and end_free(a):      # a real partition the furniture stands at holds at both ends
            fk = I[k]['key']
            add('S18*', G[a].interpolate(0.5, normalized=True).coords[0], f'линия перегородки {"по краю" if on_edge >= 0.5 else "поперёк"} «{I[k]["name"][:30]}»',
                kind=('по краю мебели' if on_edge >= 0.5 else 'поперёк мебели'), furn=fk)
            on_furn += 1; break
# monitors at the ends of tables (owner: "мониторы для конференц-связи, которые стоят впритык к столу" - not partitions):
#   the bar and its stand (own7.monitor_bars, the same finder fix7 F3a uses) belong to a monitor, not to a partition, the
#   glazing or the table
_AP = [i for i, p in enumerate(P) if cls[i] not in NOTDRAW and pts(p)]
_AB = [box(*MultiPoint(pts(P[i])).bounds) if len(pts(P[i])) > 1 else Point(pts(P[i])[0]) for i in _AP]; _AT = STRtree(_AB)
def inside_all(poly):
    pp = prep(poly); return [_AP[j] for j in _AT.query(poly) if all(pp.contains(Point(v)) for v in pts(P[_AP[j]]))]
_MON_NO = {'WALL', 'chair', 'armchair', 'sofa', 'stool', 'column', 'stair', 'lift', 'door', 'door45', 'wc', 'sink', 'wcsink'}
_TBLK = {'mtable', 'rtable', 'desk_src', 'desk_o', 'furn_src', 'desk'}
_mons, _nr, _nb, _rej = monitor_bars(P, L, G, T, near, O.key, [(k, list(I[k]['prims'])) for k in inst_of(_TBLK)], _MON_NO, inside_all)
for m in _mons + _rej:
    bad = collections.Counter(O.key(i) for i in m['bar_ids'] + m['stand'] if O.key(i) not in ('monitor', 'equip'))
    bc = m['bar'].centroid
    if m in _rej:
        add('S18*', (bc.x, bc.y), f'кандидат в мониторы вне семейства этажа: {m["Lb"] * MM_PER_PT:.0f} мм — посмотреть', kind='монитор вне семейства')
    elif bad:
        add('S18*', (bc.x, bc.y), f'монитор у торца стола «{I[m["k"]]["name"][:30]}»: его линии у {dict(bad.most_common(4))} — не оборудование',
            kind='монитор у торца стола')
print('S18 monitors', len(_mons), 'off-family', len(_rej))
print('S18', R['S18*']['n'], dict(R['S18*']['by']), round(time.time() - t0, 1), 's')
# ======================================================================================== S19*
rec('S19*', 'замкнутый прямоугольник размера мебели нарисован запасными линиями — мебель не узнана (пп. 246, 247)')
FB_ = FALLBACK | PART
LF = [n for n in range(len(L)) if not ('WALL' in KEYS[n] or KEYS[n] & {'chair', 'roomsep', 'axmark'})]
FACES = list(polygonize(unary_union([G[n] for n in LF])))
TL = STRtree([G[n] for n in LF])
doorh = [ihull(k) for k in inst_of({'door', 'door45'})]; doorh = [h for h in doorh if h is not None]
DT = STRtree(doorh) if doorh else None
HH = [(k, ihull(k)) for k in inst_of(HOSTS)]; HH = [(k, h) for k, h in HH if h is not None and h.area >= 1]; HHT = STRtree([h for k, h in HH])
RECT = []
for f in FACES:
    r = f.minimum_rotated_rectangle
    if r.area <= 0 or f.area / r.area < 0.95: continue
    cc = list(r.exterior.coords); e = sorted([math.dist(cc[0], cc[1]), math.dist(cc[1], cc[2])])
    if not (250 * PT <= e[0] <= 2500 * PT and 380 * PT <= e[1] <= 7600 * PT): continue
    bd = f.exterior; zone = bd.buffer(0.3); cov = collections.Counter(); own_inst = collections.Counter(); lines_ = []
    for j in TL.query(zone):
        n = LF[j]; inter = G[n].intersection(zone)
        if inter.is_empty: continue
        cov[ukey(KEYS[n]) if KEYS[n] & FB_ else sorted(KEYS[n])[0]] += inter.length
        for k in O.insts(L[n][0]): own_inst[k] += inter.length
        lines_.append((n, inter.length))
    tot = sum(cov.values()) or 1
    fb = sum(v for k_, v in cov.items() if k_ in FB_) / tot
    RECT.append(dict(f=f, e=e, fb=fb, cov=cov, own=own_inst, tot=tot, lines=lines_))
    if fb < 0.4: continue
    if any(FH[j][1].buffer(0.2).contains(f.buffer(-0.3)) for j in FT.query(f.representative_point())): continue
    if any(HH[j][1].buffer(0.2).contains(f.buffer(-0.3)) for j in HHT.query(f.representative_point())): continue
    if DT is not None and any(doorh[j].intersection(f).area > 0.5 for j in DT.query(f)): continue
    if WU is not None and not WU.is_empty and bd.intersection(WU.buffer(0.3)).length > 0.5 * bd.length: continue
    rp = f.representative_point()
    add('S19*', (rp.x, rp.y), f'прямоугольник {e[1] * MM_PER_PT:.0f}×{e[0] * MM_PER_PT:.0f} мм, {fb:.0%} контура — запасные классы',
        kind='прямоугольник мебели', b=[round(v, 1) for v in f.bounds])
# (code 007, п. 293а) furniture in the partitions: a closed rectangle of furniture size drawn by the floor's furniture pen and
#   held by a partition class (gklpart, glasspart, lpart, lpartc, railing) - a table whose outline went to the partitions
#   (floor 4, the call booth: 24 lines of the table in 'gklpart', 2 in 'glasspart'). It touches the walls and partitions,
#   so neither L2 nor the fallback test above saw it. The furniture pens are read from the floor itself: the pens (width,
#   colour) holding >= 5 % of the line length of the recognised furniture and seats and < 5 % of the partitions' - a pen
#   the partitions are drawn by too says nothing (floor 4: the chairs and the partitions share black 0.24 pt, the tables
#   are grey 0.67, 0.24 pt).
_fpen, _ppen = collections.Counter(), collections.Counter()
for n in range(len(L)):
    if KEYS[n] & (FURN | SEATS) and not KEYS[n] & PART: _fpen[pen(L[n][0])] += G[n].length
    elif KEYS[n] & PART and not KEYS[n] & (FURN | SEATS): _ppen[pen(L[n][0])] += G[n].length
_ft, _pt = sum(_fpen.values()) or 1, sum(_ppen.values()) or 1
FPENS = {k for k, v in _fpen.items() if v >= 0.05 * _ft and _ppen.get(k, 0) < 0.05 * _pt}
FPEN = sorted(FPENS, key=lambda k: -_fpen[k])
for rr in RECT:
    if not FPENS: break
    f = rr['f']; tot = rr['tot'] or 1
    inpart = sum(ln_ for n, ln_ in rr['lines'] if KEYS[n] & PART and not KEYS[n] & (FURN | SEATS) and pen(L[n][0]) in FPENS)
    if inpart / tot < 0.4: continue
    if any(FH[j][1].buffer(0.2).contains(f.buffer(-0.3)) for j in FT.query(f.representative_point())): continue
    if any(HH[j][1].buffer(0.2).contains(f.buffer(-0.3)) for j in HHT.query(f.representative_point())): continue
    if DT is not None and any(doorh[j].intersection(f).area > 0.5 for j in DT.query(f)): continue
    rp = f.representative_point()
    if any(math.dist(s_['at'], (rp.x, rp.y)) < 0.5 for s_ in R['S19*']['spots']): continue
    e = rr['e']
    add('S19*', (rp.x, rp.y), f'прямоугольник {e[1] * MM_PER_PT:.0f}×{e[0] * MM_PER_PT:.0f} мм пером мебели: {inpart / tot:.0%} контура — у перегородок',
        kind='мебель в перегородках', b=[round(v, 1) for v in f.bounds])
print('S19', R['S19*']['n'], 'faces', len(FACES), 'furniture pen', FPEN, round(time.time() - t0, 1), 's')
# ======================================================================================== S20*
rec('S20*', 'семейство не по эталону: колонны одной формы и толщины, однотипная сантехника одинакова (пп. 248, 253, 264)')
FD = []
for k in inst_of({'column'}):
    q = I[k]
    if 'кругл' in q['name'] or 'за стеной' in q['name']: continue
    for i in q['prims']:
        if P[i][0] == 'qu' and is_col_fill(P[i][3]):
            b_ = bb_of(P, [i]); d_ = sorted([b_[2] - b_[0], b_[3] - b_[1]])
            if d_[0] >= 2.5: FD.append(d_)
FAMS = ibeam_families(FD, default=(4.08, 7.2)); TW, TH = FAMS[0]   # (code 007) a template per family of the floor, as fix7 F1
COLS = []
for k in inst_of({'column'}):
    q = I[k]; ids = list(q['prims']); Ls = [i for i in ids if P[i][0] == 'l']
    fam = 'r' if 'кругл' in q['name'] else 't' if 'за стеной' in q['name'] else 'i'
    if not Ls:
        h = ihull(k); add('S20*', h.centroid.coords[0] if h is not None else (0, 0), f'колонна #{k} без линий: их забрали другие', kind='колонна без линий'); continue
    if fam == 'i':
        mb, outline, how = ibeam_box_fams(P, ids, FAMS)
        if mb is None:
            b_ = bb_of(P, ids); add('S20*', ((b_[0] + b_[2]) / 2, (b_[1] + b_[3]) / 2), f'«колонна» #{k}: двутавра нет — не колонна', kind='не колонна'); continue
    else:
        wmax = max((P[i][1] or 0) for i in Ls); thick = [i for i in Ls if (P[i][1] or 0) >= 0.5 * wmax]
        mb = bb_of(P, thick); outline = None
    COLS.append(dict(k=k, fam=fam, main=list(mb), dims=sorted([mb[2] - mb[0], mb[3] - mb[1]]), round=fam == 'r'))
    why = []
    out_ = 0; thin_ = 0
    for i in ids:
        p = P[i]
        ext = max([max(mb[0] - v[0], v[0] - mb[2], mb[1] - v[1], v[1] - mb[3], 0) for v in pts(p)])
        if ext >= 0.5: out_ += 1; continue
        if outline is not None and p[0] == 'l' and (p[1] or 0) < 0.45 and math.dist(p[4][0], p[4][-1]) >= 1.0 and not outline.contains(LineString(p[4])): thin_ += 1
    if out_: why.append(f'{out_} чужих линий за контуром колонны')
    if thin_: why.append(f'{thin_} тонких черт у двутавра (служебная разметка)')
    if why: add('S20*', ((mb[0] + mb[2]) / 2, (mb[1] + mb[3]) / 2), f'колонна #{k}: ' + '; '.join(why), kind='колонна ' + {'r': 'круглая', 't': 'тавр за стеной', 'i': 'двутавр'}[fam])
for fam_ in ('r', 't'):
    cs = [c for c in COLS if c['fam'] == fam_]
    if len(cs) < 2: continue
    ra = statistics.median(c['dims'][0] for c in cs); rb = statistics.median(c['dims'][1] for c in cs)
    for c in cs:
        a_, b_ = c['dims']
        if abs(a_ - ra) > 0.15 * ra or abs(b_ - rb) > 0.15 * rb:
            m = c['main']; add('S20*', ((m[0] + m[2]) / 2, (m[1] + m[3]) / 2), f'колонна #{c["k"]}: форма {a_:.1f}×{b_:.1f} pt вместо {ra:.1f}×{rb:.1f}', kind='колонна ' + {'r': 'круглая', 't': 'тавр за стеной'}[fam_])
fam = collections.defaultdict(list)
for k in inst_of({'wc', 'sink', 'wcsink', 'urinal'}):
    q = I[k]; h = ihull(k)
    # (Г3-5) a fixture of one line or of points on one line: its hull is not a polygon (fewer than 3 points, a LineString,
    #   a Point, area 0) - not an exception, the fixture is marked degenerate and named in S20*; the family is built without it
    if h is None or h.geom_type != 'Polygon' or h.area <= 0:
        q['degenerate'] = True
        xy = [v for i in list(q['prims']) + list(q.get('shared', [])) for v in pts(P[i])]
        at = (sum(v[0] for v in xy) / len(xy), sum(v[1] for v in xy) / len(xy)) if xy else (0, 0)
        add('S20*', at, f'{q["name"][:30]} #{k}: оболочка вырождена ({h.geom_type if h is not None else "меньше 3 точек"}, '
            f'{len(q["prims"])} прим.) — прибор из одной линии', kind='сантехника: оболочка вырождена')
        continue
    r_ = h.minimum_rotated_rectangle; cc = list(r_.exterior.coords); e = sorted([math.dist(cc[0], cc[1]), math.dist(cc[1], cc[2])])
    ln = sum(math.dist(P[i][4][0], P[i][4][-1]) for i in q['prims'] if P[i][0] == 'l')
    fam[(q['key'], q['name'])].append(dict(k=k, at=(h.centroid.x, h.centroid.y), e=e, n=len(q['prims']), ln=ln))
for (kk, nm), lst in fam.items():
    if len(lst) < 2: continue
    m0 = statistics.median(x['e'][0] for x in lst); m1 = statistics.median(x['e'][1] for x in lst)
    mn = statistics.median(x['n'] for x in lst); ml = statistics.median(x['ln'] for x in lst)
    for x in lst:
        why = []
        if abs(x['e'][0] - m0) > 0.12 * m0 or abs(x['e'][1] - m1) > 0.12 * m1: why.append(f'размер {x["e"][1]:.1f}×{x["e"][0]:.1f} pt вместо {m1:.1f}×{m0:.1f}')
        if abs(x['n'] - mn) > 0.25 * mn: why.append(f'примитивов {x["n"]} вместо ~{mn:.0f}')
        if ml > 0 and abs(x['ln'] - ml) > 0.2 * ml: why.append(f'длина линий {x["ln"]:.0f} вместо ~{ml:.0f} pt')
        if why: add('S20*', x['at'], f'{nm[:30]} #{x["k"]}: ' + '; '.join(why), kind='сантехника')
print('S20', R['S20*']['n'], dict(R['S20*']['by']), round(time.time() - t0, 1), 's')
# ======================================================================================== S21*
rec('S21*', 'колонны вдоль стены — парами; двутавр в исходнике, не ставший колонной (п. 249)')
CC = [(c['k'], ((c['main'][0] + c['main'][2]) / 2, (c['main'][1] + c['main'][3]) / 2)) for c in COLS if not c['round']]
# (code 008, ПК1-П4, №98) the sizes of S21* are of the building: set in pt at 63.5 mm/pt, converted by the scale (ptb)
from common import ptb
def partners(k, x, y, ax):
    if ax == 'v': return [k2 for k2, (x2, y2) in CC if k2 != k and abs(x2 - x) <= ptb(1.5) and ptb(8) <= abs(y2 - y) <= ptb(25)]
    return [k2 for k2, (x2, y2) in CC if k2 != k and abs(y2 - y) <= ptb(1.5) and ptb(8) <= abs(x2 - x) <= ptb(25)]
TKL = [(i, p[4][0], p[4][-1]) for i, p in enumerate(P) if p[0] == 'l' and (p[1] or 0) >= 0.55 and cls[i] not in NOTDRAW
       and X0 <= p[4][0][0] <= X1 and Y0 <= p[4][0][1] <= Y1]
TKG = [LineString([a_, b_]) if math.dist(a_, b_) > 0 else Point(a_) for i, a_, b_ in TKL]; TKT = STRtree(TKG)
def ibeam_at(x, y, r=None):
    """an I-beam of thick lines in the source around (x, y): (box, owners) or None"""
    r = ptb(4.0) if r is None else r
    ids = [j for j in TKT.query(box(x - r, y - r, x + r, y + r))]
    if len(ids) < 6: return None
    xs = [v for j in ids for v in (TKL[j][1][0], TKL[j][2][0])]; ys = [v for j in ids for v in (TKL[j][1][1], TKL[j][2][1])]
    w_, h_ = max(xs) - min(xs), max(ys) - min(ys)
    if not (ptb(2.5) <= min(w_, h_) <= ptb(7.0) and ptb(4.0) <= max(w_, h_) <= ptb(9.5)): return None
    return (min(xs), min(ys), max(xs), max(ys)), collections.Counter(O.key(TKL[j][0]) for j in ids)
for ax, crd in (('v', 1), ('h', 0)):                   # 'v': the pair is across a horizontal wall (same x, other y)
    rows = collections.defaultdict(list)
    for k, c in CC: rows[round(c[crd] / ptb(3))].append((k, c))
    for key_, mem in rows.items():
        paired = [(k, c) for k, c in mem if partners(k, c[0], c[1], ax)]
        if len(paired) < 2: continue                     # not a wall with paired columns
        offs = [CC[[k2 for k2, _ in CC].index(partners(k, c[0], c[1], ax)[0])][1][crd] - c[crd] for k, c in paired]
        off = statistics.median(offs)
        for k, c in mem:
            if partners(k, c[0], c[1], ax): continue
            ex = (c[0], c[1] + off) if ax == 'v' else (c[0] + off, c[1])
            ib = ibeam_at(*ex)
            src = f'; в исходнике на месте пары двутавр у «{ib[1].most_common(1)[0][0]}»' if ib and ib[1].get('column', 0) == 0 else ''
            add('S21*', c, f'колонна #{k} в ряду парных колонн без пары по другую сторону стены{src}', kind='без пары' + (': двутавр не распознан' if src else ''))
for i, p in enumerate(P):
    if p[0] != 'qu' or not is_col_fill(p[3]) or 'column' in O.keys(i): continue
    b_ = bb_of(P, [i]); d_ = sorted([b_[2] - b_[0], b_[3] - b_[1]])
    if fam_of(d_, FAMS) is not None:
        add('S21*', ((b_[0] + b_[2]) / 2, (b_[1] + b_[3]) / 2), f'двутавр (заливка колонны) у «{ukey(O.keys(i))}», не колонна', kind='двутавр не колонна')
TKs = set(range(len(TKL))); seen_ = set()
for a_ in range(len(TKL)):
    if a_ in seen_: continue
    st = [a_]; seen_.add(a_); cp = []
    while st:
        b_ = st.pop(); cp.append(b_)
        for c_ in TKT.query(TKG[b_].buffer(0.15)):
            if c_ not in seen_ and TKG[b_].distance(TKG[c_]) <= 0.15: seen_.add(c_); st.append(c_)
    xs = [v for b_ in cp for v in (TKL[b_][1][0], TKL[b_][2][0])]; ys = [v for b_ in cp for v in (TKL[b_][1][1], TKL[b_][2][1])]
    w_, h_ = max(xs) - min(xs), max(ys) - min(ys)
    if ptb(3.0) <= min(w_, h_) <= ptb(6.0) and ptb(5.5) <= max(w_, h_) <= ptb(9.0) and len(cp) >= 6:   # 190-380 x 350-570 mm
        own_ = collections.Counter(O.key(TKL[b_][0]) for b_ in cp)
        if own_.get('column', 0) < 0.5 * len(cp):
            add('S21*', ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2), f'кластер толстых линий двутавра {w_:.1f}×{h_:.1f} pt — у «{own_.most_common(1)[0][0]}»', kind='двутавр не колонна')
print('S21', R['S21*']['n'], dict(R['S21*']['by']), round(time.time() - t0, 1), 's')
# ======================================================================================== S22*
rec('S22*', 'дверь: распознана, в створе и поперёк проёма нет стен и перегородок, косяки по обоим краям (п. 250)')
BLOCK = PART | GLAZ | {'WALL', 'wallline', 'column'}
DOORS = [(k, I[k]) for k in inst_of({'door'}) if 'door' in I[k]]
SL_ = [n for n in range(len(L)) if KEYS[n] & (LAYER1 | {'column'})]
SLT = STRtree([G[n] for n in SL_]) if SL_ else None
WBl = [g.exterior for c, g in WB]
WBT = STRtree(WBl) if WBl else None
def jamb(pt, r=1.6):
    d = 99; g = Point(pt)
    if SLT is not None: d = min([d] + [G[SL_[j]].distance(g) for j in SLT.query(g.buffer(r))])
    if WBT is not None: d = min([d] + [WBl[j].distance(g) for j in WBT.query(g.buffer(r))])
    if WU is not None and not WU.is_empty and WU.contains(g): d = 0
    return d
# (04.10.2026, строка 172) glass doors: the glass line through the opening is cut between the jambs in the DXF and the
#   door is drawn in the glass style - checked on the DXF itself, not on the decision of fix7.py (F14)
GLASS_DXF = None
def glass_dxf():
    global GLASS_DXF
    if GLASS_DXF is None:
        import ezdxf
        from common import DXF
        GLASS_DXF = []
        try:
            msp_ = ezdxf.readfile(DXF).modelspace()
            for e in msp_:
                if e.dxf.layer != 'A-22G---E-': continue
                ents = list(e.virtual_entities()) if e.dxftype() == 'INSERT' else [e]
                for v in ents:
                    if v.dxftype() == 'LINE': GLASS_DXF.append(LineString([(v.dxf.start.x, v.dxf.start.y), (v.dxf.end.x, v.dxf.end.y)]))
                    elif v.dxftype() == 'LWPOLYLINE':
                        pp = [(x, y) for x, y in v.get_points('xy')]
                        if len(pp) >= 2: GLASS_DXF.append(LineString(pp + ([pp[0]] if v.closed else [])))
        except Exception as ex_: print('S22 glass: DXF not read', ex_)
    return GLASS_DXF
from common import MM
def glass_gap_ok(q):
    """(ok, why): no A-22G line of the DXF runs inside the opening of a glass door; the door block is a glass door"""
    g = q['glass_gap']; a, b = g['a'], g['b']; L0 = math.dist(a, b)
    u = ((b[0] - a[0]) / L0, (b[1] - a[1]) / L0)
    a_ = (a[0] + u[0] * 0.4, a[1] + u[1] * 0.4); b_ = (b[0] - u[0] * 0.4, b[1] - u[1] * 0.4)
    strip = LineString([MM(a_), MM(b_)]).buffer(0.5 * MM_PER_PT, cap_style=2)
    A_, B_ = MM(a), MM(b); um = (B_[0] - A_[0], B_[1] - A_[1]); nm = math.hypot(*um); um = (um[0] / nm, um[1] / nm)
    def along(x):                                       # a piece of glass line along the opening, not a tick across it
        c_ = list(x.coords)
        for p_, r_ in zip(c_, c_[1:]):
            d_ = math.dist(p_, r_)
            if d_ > 1 and abs(um[0] * (r_[1] - p_[1]) - um[1] * (r_[0] - p_[0])) / d_ <= math.sin(math.radians(10)): return True
        return False
    left = sum(x.intersection(strip).length for x in glass_dxf() if x.intersects(strip) and along(x))
    # a stub of the meeting stile or of a jamb is not a line through: the glass line left in the opening would be
    #   most of its width (800-1800 mm)
    if left > max(60.0, 0.1 * L0 * MM_PER_PT): return False, f'линия стекла в проёме не разорвана: {left:.0f} мм'
    if 'стеклян' not in (q.get('block') or ''): return False, 'дверь не в стиле стекла'
    return True, ''
GLASS_OK = 0
for k, q in DOORS:
    d = q['door']; c, o, cl = d['c'], d['open'], d['closed']
    r = math.dist(c, o); a0 = math.atan2(o[1] - c[1], o[0] - c[0]); a1 = math.atan2(cl[1] - c[1], cl[0] - c[0])
    da = (a1 - a0 + math.pi) % (2 * math.pi) - math.pi
    sector = Polygon([c] + [(c[0] + r * math.cos(a0 + da * t / 16), c[1] + r * math.sin(a0 + da * t / 16)) for t in range(17)])
    if not sector.is_valid or sector.area < 1: continue
    inner = sector.buffer(-0.4); chord = LineString([c, cl]); own_ids = set(q['prims']) | set(q.get('shared', []))
    if q.get('glass_gap'): own_ids |= set(q['glass_gap']['prims'])
    hits = collections.Counter()
    for n in T.query(sector):
        if L[n][0] in own_ids or not (KEYS[n] & BLOCK) or G[n].length < 1.0: continue
        if (not inner.is_empty and G[n].intersects(inner) and G[n].intersection(inner).length >= 1.0) or \
           (G[n].crosses(chord) and chord.interpolate(chord.project(G[n].intersection(chord).representative_point())).distance(Point(c)) > 0.6
            and chord.interpolate(chord.project(G[n].intersection(chord).representative_point())).distance(Point(cl)) > 0.6):
            hits[ukey(KEYS[n])] += 1
    issues = []
    if hits: issues.append('в створе или поперёк проёма: ' + ', '.join(f'{a} {b}' for a, b in hits.items()))
    if abs(math.dist(c, o) - math.dist(c, cl)) > 0.08 * math.dist(c, cl): issues.append('полотно и дуга разной длины')
    pair = [k2 for k2, q2 in DOORS if k2 != k and math.dist(q2['door']['closed'], cl) <= 1.6]
    far = I[pair[0]]['door']['c'] if pair else cl
    if jamb(c) > 1.6: issues.append('у петли нет стены или стойки')
    if jamb(far) > 1.6: issues.append('у дальнего края нет стены или стойки')
    m = re.search(r'(\d{3,4})', q['name'])
    if m and not pair and abs(math.dist(c, cl) * MM_PER_PT - int(m.group(1))) > 120: issues.append('ширина не по имени')
    if q.get('glass_gap'):
        ok_, why_ = glass_gap_ok(q)
        if ok_: GLASS_OK += 1
        else: issues.insert(0, 'стеклянная дверь: ' + why_)
    if issues: add('S22*', c, f'дверь #{k}: ' + '; '.join(issues), kind=issues[0].split(':')[0])
print('S22 glass doors: gap and style in the DXF', GLASS_OK)
for k in inst_of({'door45'}):
    if I[k].get('colour'): continue                     # a glass door drawn in the glass partition: the partition holds it
    h = ihull(k)
    if h is None: continue
    inner = h.buffer(-0.3)
    if inner.is_empty: continue
    own_ids = set(I[k]['prims']) | set(I[k].get('shared', []))
    n_ = sum(1 for n in T.query(inner) if L[n][0] not in own_ids and KEYS[n] & BLOCK and G[n].intersection(inner).length >= 1.0)
    if n_: add('S22*', (h.centroid.x, h.centroid.y), f'дверь #{k}: в полотне {n_} линий стен или перегородок', kind='в створе или поперёк проёма')
print('S22', R['S22*']['n'], dict(R['S22*']['by']), round(time.time() - t0, 1), 's')
# ======================================================================================== S23*
rec('S23*', 'стена на мебели, линии стен и перегородок внутри мебели и лестниц, грани стен в аксессуарах санузлов (пп. 251, 252, 262, 265)')
def ihull_body(k):
    """the hull of an object's body: its own primitives from 1 pt (a crumb of a wall junction an operator box took at its
    corner does not stretch the cabinet over the wall)"""
    ids = [i for i in I[k]['prims'] if pts(P[i]) and max(abs(v[0] - pts(P[i])[0][0]) + abs(v[1] - pts(P[i])[0][1]) for v in pts(P[i])) >= 1.0]
    return hull_of(P, ids) if len(ids) >= 2 else None
FHB = [(k, ihull_body(k)) for k, h in FH]; FHB = [(k, h) for k, h in FHB if h is not None and h.geom_type == 'Polygon' and h.area >= 2]
for k, h in FHB:
    for c_, g in WB:
        ov_ = g.intersection(h); a_ = ov_.area
        if a_ < 3 or a_ < 0.03 * h.area: continue
        # a shared boundary is a sliver along the edge; a wall on furniture goes into it (>= 1.5 pt, 95 mm)
        thick_ = max((min(math.dist(*list(p_.minimum_rotated_rectangle.exterior.coords)[0:2]), math.dist(*list(p_.minimum_rotated_rectangle.exterior.coords)[1:3]))
                      for p_ in getattr(ov_, 'geoms', [ov_]) if p_.geom_type == 'Polygon' and p_.area > 0.5), default=0)
        if thick_ >= 1.5:
            add('S23*', (h.centroid.x, h.centroid.y), f'стена {c_} заходит на «{I[k]["name"][:30]}»: {a_ * MM_PER_PT ** 2 / 1e6:.2f} м²', kind='стена на мебели')
LIFTH = [h for h in (ihull(k) for k in inst_of({'lift', 'stair'})) if h is not None]
for c_, g_ in WB:
    for ring in g_.interiors:
        hp = Polygon(ring); a2 = hp.area * MM_PER_PT ** 2 / 1e6
        if 0.05 <= a2 <= 2.5 and not any(h.intersects(hp) for h in LIFTH):
            add('S23*', hp.representative_point().coords[0], f'стена {c_} кольцом вокруг пустого ящика {a2:.2f} м² — это мебель, а не стена', kind='стена-кольцо вокруг ящика')
STRUCTK = PART | {'WALL', 'column', 'glass', 'wallline'}
WUz = WU.buffer(0.3) if WU is not None and not WU.is_empty else None
for k, h in FHB + [(k, ihull(k)) for k in inst_of({'stair'})]:
    if h is None: continue
    inner = h.buffer(-0.35)
    if WUz is not None: inner = inner.difference(WUz)                    # the shared boundary with a wall is not inside
    if inner.is_empty: continue
    own_ids = set(I[k]['prims']) | set(I[k].get('shared', []))
    sk_ = STRUCTK - {'column'} if I[k]['key'] == 'stair' else STRUCTK          # a column in the corner of a stair is a column (п. 262)
    cnt = collections.Counter(ukey(KEYS[n]) for n in T.query(inner) if L[n][0] not in own_ids and KEYS[n] & sk_ and inner.contains(G[n]))
    if cnt:
        add('S23*', (h.centroid.x, h.centroid.y), f'внутри «{I[k]["name"][:30]}»: ' + ', '.join(f'{a} {b}' for a, b in cnt.items()),
            kind='лестница: чужие линии' if I[k]['key'] == 'stair' else 'мебель: чужие линии')
PARTL = [G[n] for n in range(len(L)) if KEYS[n] & (PART | {'wallline', 'glass'})]
PARTB = unary_union(PARTL).buffer(0.1) if PARTL else None
WBd = WBND.buffer(0.3) if WBND is not None else None
wcl = collections.Counter()
for k in inst_of({'wcacc'}):
    for i in I[k]['prims']:
        if P[i][0] != 'l': continue
        g = LineString(P[i][4])
        if g.length < 2: continue
        if (WBd is not None and g.intersection(WBd).length >= 0.8 * g.length) or (PARTB is not None and g.intersection(PARTB).length >= 0.8 * g.length):
            wcl[k] += 1
for k, n_ in wcl.items():
    h = ihull(k); add('S23*', (h.centroid.x, h.centroid.y), f'аксессуар #{k}: {n_} линий на гранях стен и перегородок', kind='аксессуар: грани стен')
print('S23', R['S23*']['n'], dict(R['S23*']['by']), round(time.time() - t0, 1), 's')
# ======================================================================================== S24*
rec('S24*', 'ритм остекления: в цепочку витража вклинились куски другого типа (п. 254)')
CAND = [n for n in range(len(L)) if KEYS[n] & (PART | {'wallline'} | GLAZ)]
CS = set(CAND); COS30 = math.cos(math.radians(30))
cont = {}
for n in CAND:
    for ei, (e, o) in enumerate(((L[n][1], L[n][2]), (L[n][2], L[n][1]))):
        u = unit(o, e); lst = []
        for m in near(e, 0.2, n):
            if m not in CS: continue
            d0 = math.dist(L[m][1], e); d1 = math.dist(L[m][2], e)
            if min(d0, d1) > 0.25: continue
            me = 0 if d0 <= d1 else 1
            v = unit(L[m][1], L[m][2]) if me == 0 else unit(L[m][2], L[m][1])
            if u[0] * v[0] + u[1] * v[1] >= COS30: lst.append((m, me))
        cont[(n, ei)] = lst
def reach_glass(n, ei, depth=4):
    fr = [(n, ei)]; sn = {n}
    for d in range(depth):
        nx = []
        for x, xe in fr:
            for m, me in cont[(x, xe)]:
                if KEYS[m] & GLAZ: return True
                if m in sn: continue
                sn.add(m); nx.append((m, 1 - me))
        fr = nx
    return False
S24 = set()
for n in CAND:
    if KEYS[n] & GLAZ or G[n].length < 0.5: continue
    if reach_glass(n, 0) and reach_glass(n, 1):
        c_ = G[n].interpolate(0.5, normalized=True).coords[0]
        if loc(c_) in S24: continue
        S24.add(loc(c_))
        add('S24*', c_, f'«{ukey(KEYS[n])}» {G[n].length:.1f} pt между модулями остекления', kind=ukey(KEYS[n]))
print('S24', R['S24*']['n'], round(time.time() - t0, 1), 's')
# ======================================================================================== S25*
rec('S25*', 'одна непрерывная стена — один тип: тип меняется посреди полосы, без стыка (п. 261)')
WBp = [(c_, prep(g.buffer(0.3))) for c_, g in WB]
def wtype(n):
    ks = KEYS[n]
    if 'WALL' in ks:
        for c_, pp in WBp:
            if pp.contains(G[n]): return 'стена ' + c_
        return 'стена ?'
    for k_, nm in (('facade', 'фасад'), ('glass', 'стекло'), ('gklpart', 'перегородка ГКЛ'), ('glasspart', 'перегородка стеклянная'),
                   ('railing', 'ограждение'), ('lpart', 'перегородка'), ('lpartc', 'перегородка'), ('wallline', 'линия стены')):
        if k_ in ks: return nm
    return None
WT = {n: wtype(n) for n in range(len(L)) if G[n].length >= 0.8}
WT = {n: t for n, t in WT.items() if t}
seen_ = set()
for a, ta in WT.items():
    i, p0, p1 = L[a]
    for e, o in ((p0, p1), (p1, p0)):
        nb = [b for b in near(e, 0.2, a) if b in WT]
        if len(nb) != 1: continue
        b = nb[0]; tb = WT[b]
        if tb == ta: continue
        # a face line of a wall and its body, or a wall whose body test failed ('стена ?'), are the same wall
        if ('линия стены' in (ta, tb) and (ta.startswith('стена') or tb.startswith('стена'))) or 'стена ?' in (ta, tb): continue
        j, q0, q1 = L[b]
        if math.dist(q0, e) <= 0.2: v2 = unit(q0, q1)
        elif math.dist(q1, e) <= 0.2: v2 = unit(q1, q0)
        else: continue
        v1 = unit(o, e)
        if v1[0] * v2[0] + v1[1] * v2[1] < math.cos(math.radians(20)): continue
        pr = frozenset((a, b))
        if pr in seen_: continue
        seen_.add(pr); add('S25*', e, f'{ta} → {tb} без стыка', kind=' / '.join(sorted((ta, tb))))
print('S25', R['S25*']['n'], dict(R['S25*']['by']), round(time.time() - t0, 1), 's')
# ======================================================================================== S26*
rec('S26*', 'штрих внутри узнанного объекта остался нераспознанным (п. 266)')
HL = [(k, ihull(k)) for k in inst_of(HOSTS)]; HL = [(k, h.buffer(0.3)) for k, h in HL if h is not None]
HT = STRtree([h for k, h in HL])
WBu = [g.buffer(0.3) for c_, g in WB]; WTt = STRtree(WBu) if WBu else None
for i, p in enumerate(P):
    if p[0] not in ('l', 'c') or cls[i] in NOTDRAW: continue
    ks = O.keys(i)
    if not (ks <= {'loose', 'misc', 'FREE'}): continue
    q_ = pts(p)
    if len(q_) < 2: continue
    g = LineString(q_)
    if g.length < 0.05: continue
    host = None
    if WTt is not None:
        for j in WTt.query(g):
            if WBu[j].contains(g): host = 'тело стены'; break
    if host is None:
        for j in HT.query(g):
            k, h = HL[j]
            if h.contains(g): host = I[k]['key']; break
    if host: add('S26*', g.centroid.coords[0], f'штрих «{ukey(ks)}» внутри: {host}', kind=host)
print('S26', R['S26*']['n'], dict(R['S26*']['by']), round(time.time() - t0, 1), 's')
# ======================================================================================== S27*
rec('S27*', 'проёмы A-23: каждая лестница в контуре клетки, контур замкнут и не идёт по телу стены (п. 263)')
OP = [(k, Polygon(I[k]['poly'])) for k, q in enumerate(I) if q['key'] == 'opening' and q.get('poly')]
for k, g in OP:
    if not g.is_valid: add('S27*', g.representative_point().coords[0], f'проём #{k}: контур невалиден', kind='контур невалиден')
    elif WU is not None and not WU.is_empty and g.intersection(WU).area > 0.02 * g.area:
        add('S27*', g.representative_point().coords[0], f'проём #{k} заходит на тела стен: {g.intersection(WU).area:.1f} pt²', kind='по телу стены')
# (04.10.2026, строка 173) an opening only where this floor's slab has one: the same rule as fix7.py (F10),
#   own7.stair_needs_opening - labels «ВВЕРХ» / «ВНИЗ» and tread lines are read here again; the cage flag is F10's
WORDS_ = sheet_words()
for k in inst_of({'stair'}):
    h = ihull(k)
    if h is None: continue
    ids_ = list(I[k]['prims']) + list(I[k].get('shared', []))
    rule_ = I[k].get('opening_rule') or {}
    need_, why_, info_ = stair_needs_opening(P, ids_, h, MM_PER_PT, WORDS_, in_cage=bool(rule_.get('cage')))
    # (code 007, regression of 06.10.2026) the same geometry as F10: a stair outside a cage gets the outline of its own body
    #   less the wall bodies, so the stair is measured less the walls too, and 'inside' is 90 % of that area (floor 5 of
    #   client A: two stairs along walls stopped as 'outside the opening' made for them)
    hw_ = h.difference(WU) if WU is not None and not WU.is_empty else h
    inside_ = hw_.area <= 0 or any(g.buffer(0.5).intersection(hw_).area >= 0.9 * hw_.area for kk, g in OP)
    over_ = any(g.intersection(h).area >= 0.5 * h.area for kk, g in OP)
    if rule_ and rule_.get('need') != need_:
        add('S27*', (h.centroid.x, h.centroid.y), f'лестница #{k}: исправление и проверка решили по-разному — {why_}', kind='решения разошлись')
    elif need_ and not inside_:
        add('S27*', (h.centroid.x, h.centroid.y), f'лестница #{k} вне контура проёма', kind='лестница без проёма')
    elif not need_ and over_:
        add('S27*', (h.centroid.x, h.centroid.y), f'лестница #{k}: проём, которого нет в перекрытии этого этажа — {why_}', kind='проём там, где его нет')
print('S27', R['S27*']['n'], round(time.time() - t0, 1), 's')
# ======================================================================================== S28*
rec('S28*', 'у каждой перегородки есть тип: ГКЛ, стекло, ограждение (п. 260)')
for k in inst_of(UNTYPED):
    for i in I[k]['prims']:
        if P[i][0] == 'l' and math.dist(P[i][4][0], P[i][4][-1]) >= 1.0:
            add('S28*', LineString(P[i][4]).interpolate(0.5, normalized=True).coords[0], f'«{I[k]["key"]}» без типа', kind=I[k]['key'])
print('S28', R['S28*']['n'], round(time.time() - t0, 1), 's')
# ======================================================================================== S29*
rec('S29*', 'рамка MANUAL взяла край соседнего объекта (п. 257)')
S29 = set()
SMALL = []                                              # narrow closed shapes too (a monitor at a table: 1460×150 мм)
for f in FACES:
    r = f.minimum_rotated_rectangle
    if r.area <= 0 or f.area / r.area < 0.9: continue
    cc = list(r.exterior.coords); e = sorted([math.dist(cc[0], cc[1]), math.dist(cc[1], cc[2])])
    if e[0] < 0.8 or e[1] < 4.0 or e[1] > 3000 * PT or e[0] >= 250 * PT: continue
    bd = f.exterior; zone = bd.buffer(0.3); own_inst = collections.Counter(); tot = 0; lines_ = []
    for j in TL.query(zone):
        n = LF[j]; inter = G[n].intersection(zone)
        if inter.is_empty: continue
        tot += inter.length
        for k in O.insts(L[n][0]): own_inst[k] += inter.length
        lines_.append((n, inter.length))
    SMALL.append(dict(f=f, e=e, own=own_inst, tot=tot or 1, lines=lines_))
from detect8 import bbox_of as _bbox8
for key_, name_, layer_, boxes in getattr(cfg, 'MANUAL', []):
    for bx in map(_bbox8, boxes):              # code 008: a polygon element (Т4-7) - by its bbox
        B = box(bx[0] - 0.6, bx[1] - 0.6, bx[2] + 0.6, bx[3] + 0.6); Bp = prep(B)
        ks = set()
        for k, q in enumerate(I):
            if q['key'] != key_ or q['name'] != name_ or not q['prims']: continue
            inn = sum(1 for i in q['prims'] if all(Bp.contains(Point(v)) for v in pts(P[i])))
            if inn >= 0.8 * len(q['prims']): ks.add(k)
        if not ks: continue
        for rr in RECT + SMALL:
            f = rr['f']
            if rr['e'][1] > 3000 * PT: continue                  # a room, not an object
            if f.intersection(B).area >= 0.5 * f.area: continue
            if any(HH[j][1].buffer(0.3).contains(f.buffer(-0.3)) for j in HHT.query(f.representative_point())): continue   # the neighbour is a whole object (its edge shared)
            # what the box's object holds alone: a boundary it shares with the neighbour is drawn by both (п. 240)
            got = sum(ln_ for n, ln_ in rr['lines'] if set(O.insts(L[n][0])) & ks and not (set(O.insts(L[n][0])) - ks))
            same = sum(v for k, v in rr['own'].items() if k not in ks and I[k]['key'] == key_)
            if got >= 2.0 and same < 0.3 * rr['tot']:
                rp = f.representative_point().coords[0]
                if loc(rp) in S29: continue
                S29.add(loc(rp))
                add('S29*', rp, f'рамка «{name_[:30]}» {tuple(round(v, 1) for v in bx)} взяла {got:.1f} pt контура соседнего прямоугольника', kind='рамка взяла край соседа')
print('S29', R['S29*']['n'], round(time.time() - t0, 1), 's')
# ======================================================================================== summary
ACC = getattr(cfg, 'GATE7_ACCEPT', {})
from accept import why_kind                              # code 007: the why is one of four kinds with its link (plan/rules/60 §8)
out = dict(ok=True, checks={}, accepted={})
for code, r in R.items():
    n = r['n']; stopn = n - (soft_n if code == 'S17*' else 0)
    a = ACC.get(code)
    r['by'] = dict(r['by'].most_common())
    status = 'ok' if stopn == 0 else ('принято' if a is not None and stopn <= a.get('max', -1) else 'СТОП')
    rej = None
    if status == 'принято':
        kind, miss = why_kind(a.get('why', ''))
        if kind is None: status, rej = 'СТОП', 'GATE7_ACCEPT не принят: ' + miss
    if status == 'СТОП': out['ok'] = False
    if status == 'принято': out['accepted'][code] = dict(a, why_kind=kind)
    out['checks'][code] = dict(title=r['title'], n=n, stop_n=stopn, status=status, by=r['by'], spots=r['spots'], **({'rejected': rej} if rej else {}))
json.dump(out, open(OUTF, 'w'), ensure_ascii=False, indent=1)
print('GATE7', 'PASS' if out['ok'] else 'STOP', round(time.time() - t0, 1), 's')
for code, r in out['checks'].items():
    print(f'  {code:5s} {r["status"]:7s} {r["n"]:5d}  {r["title"][:90]}' + (f' — {r["rejected"]}' if r.get('rejected') else ''))
    print('         ', dict(list(r['by'].items())[:8]))
sys.exit(0 if out['ok'] else 1)
