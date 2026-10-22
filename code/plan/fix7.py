# fix7.py - code 007 (draft): the owner's rules from the review of the layer sheets of floor 4 of client A (03.10.2026),
# applied after recognition (after reclass.py, before export.py). proposals/plan/2026-10-03-клиент А-4-разбор-слоёв-
# владельцем.md, пп. 240-266. Each step fixes what a check of checks/gate7.py finds:
#   F0  cfg.NOT_WALL_ZONES - a box the operator has said is not a wall (owner: "Эти блоки похожи на мебель. Там никаких
#       стен не должно быть"): the wall bodies are cut by it, its lines become the named object            (S23*)
#   F1  columns by the family template: thin service ticks and foreign pieces leave the column, a "column" without an
#       I-beam is dissolved, a column whose lines others took gets them back, I-beams of the source that no column
#       holds become columns (also thin ones at the place of a missing pair)                       (S20*, S21*)
#   F2  closed rectangles of furniture size drawn by fallback lines become furniture: a desk where a seat is, a screen
#       strip between desks, the end cell of a row of cabinets, the cell of a stair flight; edges that a facade band or
#       an operator box took come back; a boundary line of several objects is shared by them (п. 240)  (S19*, S17*)
#   F3  partitions hanging in the air, along or across furniture, between a seat and a table: lines of that furniture;
#       a line across a bench - its barrier (part of the desk); at the end of a meeting table - a monitor (S18*)
#   F4  doors: a leaf edge in the swing - the door; a line across the opening - service marking            (S22*)
#   F5  stairs: lines inside the stair - the stair; flights next to it (<= 300 mm, from 3 treads)           (S23*)
#   F6  pieces wedged into a run of glazing - the glazing                                                     (S24*)
#   F7  faces of walls and partitions: a piece of the same pen that a foreign class took goes back (fallback, WC
#       accessories) or is shared (objects)                                                          (S15*, S16*)
#   F8  strokes inside a recognised object - that object; inside a wall body - the wall                       (S26*)
#   F9  WC: wall faces in accessories go back to the walls; a fixture keeps only what its family exemplar holds
#                                                                                                     (S23*, S20*)
#   F10 openings A-23: stair cages and the atrium (owner: "Контур лестничной клетки", "A-23 «Проёмы»"); only where
#       this floor's slab has an opening: a flight only up («ВВЕРХ») or a short flight outside a cage - none (строка 173) (S27*)
#   F11 partition types (owner: hollow double lines - plasterboard, a single thin line - glazing): the atrium
#       boundary - railing, double lines - ГКЛ A-222, single lines - glass A-22G                            (S28*)
#   F14 glass doors: a glass line runs through a door's opening - the door is a glass door, export.py cuts the line
#       between the jambs and draws the door in the glass style on A-32 (owner 04.10.2026, строка 172)        (S22*)
# Files: reads assign2_reclass.pkl (copy of reclass.py's output made by run.sh), walls_pre7.pkl, wallprims_pre7.pkl;
# writes assign2.pkl, walls.pkl, wallprims.pkl, fix7.json (every move with its rule and place).
#   python3 fix7.py          (floor folder; FIX7_STEPS=0,1,2 runs a part)
import os, sys, json, pickle, math, collections, time, statistics, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import load, pts, cfg, MM, MM_PER_PT, kx, ky
from own7 import PART, UNTYPED, GLAZ, LAYER1, OPENING_KEYS, STRUCT_END, SEATS, TABLES, FURN, HOSTS, FALLBACK, unit, \
    sheet_words, stair_needs_opening, door_opening, glass_through, opening_lines, GLASS_KEYS
from shapely.geometry import LineString, Point, MultiPoint, Polygon, box
from shapely.ops import unary_union, polygonize
from shapely.strtree import STRtree
from shapely.prepared import prep
from shapely.affinity import affine_transform
t0 = time.time()
STEPS = set(int(s) for s in os.environ.get('FIX7_STEPS', ','.join(str(n) for n in range(13))).split(','))
def pick(a, b): return a if os.path.exists(a) else b
SRC_A, SRC_WP, SRC_W = pick('assign2_reclass.pkl', 'assign2.pkl'), pick('wallprims_pre7.pkl', 'wallprims.pkl'), pick('walls_pre7.pkl', 'walls.pkl')
# (code 007, regression of 06.10.2026) the steps are switched on per floor: cfg.FIX7 = True (or FIX7_STEPS in the environment).
#   They change a floor drawn before them, and a rule that changes another floor is switched on by a field until all its
#   places on all floors are looked at (plan/rules/70 §2; plan/00, step 7). Floor 5 of client A, run with them by default:
#   F1 dissolved 10 real columns (one median template of two I-beam families), F3 made 72 'WC accessories' of the cabin
#   partitions. Off: the loop's walls and reclass.py's objects go to export unchanged - the drawing of code 006.
if not (getattr(cfg, 'FIX7', False) or os.environ.get('FIX7_STEPS')):
    import shutil
    for a_, b_ in (('walls_pre7.pkl', 'walls.pkl'), ('wallprims_pre7.pkl', 'wallprims.pkl'), ('assign2_reclass.pkl', 'assign2.pkl')):
        if os.path.exists(a_): shutil.copyfile(a_, b_)
    json.dump(dict(off=True, why='cfg.FIX7 не задано: шаги F0–F14 не применялись, чертёж — как у кода 006 (plan/rules/70 §2)', rules={}, spots={},
                   new=0, dropped=0, openings=[], no_opening=[], glass_doors=[]), open('fix7.json', 'w'), ensure_ascii=False, indent=1)
    print('fix7 off: cfg.FIX7 is not set - the steps change a floor only where they are switched on'); sys.exit(0)
inst, free = pickle.load(open(SRC_A, 'rb'))
WP = set(pickle.load(open(SRC_WP, 'rb')))
WD = pickle.load(open(SRC_W, 'rb'))
P = load(); cls = pickle.load(open('cls.pkl', 'rb'))
X0, Y0, X1, Y1 = cfg.WIN
PT = 1 / MM_PER_PT
NOTDRAW = ('sheet', 'axis', 'dim')
N0 = len(inst)
was_empty = [not q['prims'] for q in inst]
own = {}
for k, q in enumerate(inst):
    for i in q['prims']: own[i] = k
SH = collections.defaultdict(set); shby = collections.defaultdict(set)
for k, q in enumerate(inst):
    for i in q.get('shared', []): SH[k].add(i); shby[i].add(k)
dirty = set()
LOG = collections.defaultdict(collections.Counter); SPOTS = collections.defaultdict(list)
def kname(k): return 'WALL' if k == 'WALL' else ('FREE' if k is None else inst[k]['key'])
def okey(i): return 'WALL' if i in WP else (inst[own[i]]['key'] if i in own else 'FREE')
def okeys(i):
    s = {okey(i)}
    for k in shby.get(i, ()): s.add(inst[k]['key'])
    return s
def spot(rule, at, what):
    if len(SPOTS[rule]) < 3000: SPOTS[rule].append(dict(at=[round(at[0], 1), round(at[1], 1)], what=what))
_TRACE = set(int(x) for x in os.environ.get('FIX7_TRACE', '').split(',') if x)
def move(i, k, rule):
    k0 = own.get(i)
    if k0 == k: return False
    if i in _TRACE:
        import traceback; print('TRACE move', i, kname(k0), '->', inst[k]['key'], rule, traceback.extract_stack()[-2].lineno)
    frm = 'WALL' if i in WP else kname(k0)
    WP.discard(i); own[i] = k; dirty.add(k)
    if k0 is not None: dirty.add(k0)
    SH[k].discard(i); shby[i].discard(k)
    LOG[rule][f'{frm} → {inst[k]["key"]}'] += 1
    return True
def to_wall(i, rule):
    k0 = own.pop(i, None)
    if k0 is not None: dirty.add(k0)
    if i not in WP: WP.add(i); LOG[rule][f'{kname(k0)} → WALL'] += 1
def share(i, k, rule):
    if own.get(i) == k or i in SH[k]: return False
    SH[k].add(i); shby[i].add(k); dirty.add(k); LOG[rule][f'общая линия: {okey(i)} + {inst[k]["key"]}'] += 1
    return True
def new_inst(key, name, layer, rule, **kw):
    inst.append(dict(key=key, name=name, layer=layer, prims=[], fix7=rule, **kw)); dirty.add(len(inst) - 1); return len(inst) - 1
def members(k): return [i for i, kk in own.items() if kk == k]
_MEM = None
def mem_index():
    global _MEM
    _MEM = collections.defaultdict(list)
    for i, k in own.items(): _MEM[k].append(i)
    return _MEM
def hull_ids(ids):
    xy = [v for i in ids for v in pts(P[i])]
    if len(xy) < 3: return None
    h = MultiPoint(xy).convex_hull
    return h if h.geom_type == 'Polygon' else None
def pen(i): return (round(P[i][1] or 0, 2), P[i][2])
def pt_mm(mm): return mm / MM_PER_PT
def loc(e): return (round(e[0] * 2) / 2, round(e[1] * 2) / 2)
# ---------------- static geometry of the drawing
LN = []
for i, p in enumerate(P):
    if p[0] != 'l' or cls[i] in NOTDRAW: continue
    a, b = p[4][0], p[4][-1]
    if math.dist(a, b) < 0.02 or not (X0 <= a[0] <= X1 and Y0 <= a[1] <= Y1): continue
    LN.append((i, a, b))
G = [LineString([a, b]) for i, a, b in LN]; T = STRtree(G); POS = {i: n for n, (i, a, b) in enumerate(LN)}
AP = [i for i, p in enumerate(P) if cls[i] not in NOTDRAW and pts(p)]
AB = [box(*MultiPoint(pts(P[i])).bounds) if len(pts(P[i])) > 1 else Point(pts(P[i])[0]) for i in AP]; AT = STRtree(AB)
def near(pt, tol=0.15, skip=None):
    g = Point(pt); return [n for n in T.query(g.buffer(tol)) if n != skip and G[n].distance(g) <= tol]
def prims_inside(poly, tol=0.0):
    """every drawing primitive whose points all lie inside poly (buffered by tol)"""
    pp = prep(poly.buffer(tol)) if tol else prep(poly)
    return [AP[j] for j in AT.query(poly) if all(pp.contains(Point(v)) for v in pts(P[AP[j]]))]
def walls_union():
    return unary_union([g for v in WD['Wpt'].values() for p in v for g in getattr(p, 'geoms', [p])])
WU = walls_union(); WUb = prep(WU.boundary.buffer(0.2)) if not WU.is_empty else None
print('lines', len(LN), 'prims', len(AP), round(time.time() - t0, 1), 's')

def run_of(n, cap=400):
    """the run a line is a piece of: collinear pieces of its pen on its line with gaps <= 0.3 pt"""
    u = unit(LN[n][1], LN[n][2]); nr_ = (-u[1], u[0]); o = LN[n][1][0] * nr_[0] + LN[n][1][1] * nr_[1]
    seen = {n}; st = [n]
    while st and len(seen) < cap:
        m = st.pop()
        for e in (LN[m][1], LN[m][2]):
            for n2 in near(e, 0.3, m):
                if n2 in seen or pen(LN[n2][0]) != pen(LN[n][0]): continue
                u2 = unit(LN[n2][1], LN[n2][2])
                if abs(u[0] * u2[0] + u[1] * u2[1]) < 0.995 or abs(LN[n2][1][0] * nr_[0] + LN[n2][1][1] * nr_[1] - o) > 0.06: continue
                seen.add(n2); st.append(n2)
    return seen
# ====================================================================================== F0 not-wall zones
if 0 in STEPS:
    aff = [kx[0], 0, 0, ky[0], kx[1], ky[1]]
    for z in getattr(cfg, 'NOT_WALL_ZONES', []):
        B = box(*z['box']); ch = set()
        for c, v in WD['Wpt'].items():
            out = []
            for p in v:
                for g in getattr(p, 'geoms', [p]):
                    if not g.intersects(B): out.append(g); continue
                    d = g.difference(B); ch.add(c)
                    out += [x for x in getattr(d, 'geoms', [d]) if x.geom_type == 'Polygon' and x.area >= 0.05]
            WD['Wpt'][c] = out
        for c in ch: WD['W'][c] = [affine_transform(g, aff) for g in WD['Wpt'][c]]
        k = new_inst(z.get('key', 'rack'), z.get('name', 'Шкаф (по исходнику)'), z.get('layer', 'A-76----E-'), 'F0', why=z.get('why', ''))
        n = 0
        for i in prims_inside(B, 0.3):
            if okey(i) in FALLBACK | {'WALL', 'wallline', 'column', 'lpart', 'lpartc'}: move(i, k, 'F0'); n += 1
        spot('F0', ((z['box'][0] + z['box'][2]) / 2, (z['box'][1] + z['box'][3]) / 2), f'не стена: {z.get("name", "")} — тела стен вырезаны {sorted(ch)}, {n} примитивов')
    WU = walls_union(); WUb = prep(WU.boundary.buffer(0.2)) if not WU.is_empty else None
    print('F0', dict(LOG['F0']), round(time.time() - t0, 1), 's')

# ====================================================================================== F1 columns
def rehome(i, avoid, rule):
    """the owner of a line that leaves `avoid`: the object it continues in the same pen, else the host it lies in"""
    if P[i][0] != 'l': return None
    a, b = P[i][4][0], P[i][4][-1]; u = unit(a, b)
    best = None
    for e in (a, b):
        for n in near(e, 0.15, POS.get(i)):
            j = LN[n][0]
            if j == i or own.get(j) == avoid or pen(j) != pen(i): continue
            v = unit(LN[n][1], LN[n][2]); col = abs(u[0] * v[0] + u[1] * v[1]) >= 0.995
            cand = ('WALL' if j in WP else own.get(j))
            if cand is None: continue
            sc = 2 if col else 1
            if best is None or sc > best[0]: best = (sc, cand)
    if best is not None:
        if best[1] == 'WALL':
            if WUb is not None and WUb.contains(LineString([a, b])): to_wall(i, rule); return 'WALL'
            return None
        move(i, best[1], rule); return best[1]
    return None
def mark_inst(name='Служебная метка: черта у колонны (по исходнику)'):
    for k, q in enumerate(inst):
        if q['key'] == 'mark' and q['name'] == name: return k
    return new_inst('mark', name, 'A-AXM---E-', 'F1')
from own7 import is_col_fill, bb_of as _bb_of, ishape as _ishape, best_box as _best_box, ibeam_families, fam_of
def is_grey(c): return is_col_fill(c)
def bb_of(ids): return _bb_of(P, ids)
def ishape(ids, mb): return _ishape(P, ids, mb)
def best_box(ids, tw, th, test=None): return _best_box(P, ids, tw, th, (lambda P_, i_, b_: test(i_, b_)) if test else None)
if 1 in STEPS:
    mem = mem_index()
    # the family template: the grey fill of the I-beam (all 27 filled I-beams of floor 4: 4.08 x 7.20-7.32 pt)
    FD = []
    for k, q in enumerate(inst):
        if q['key'] != 'column' or 'кругл' in q['name'] or 'за стеной' in q['name']: continue
        for i in mem.get(k, []):
            if P[i][0] == 'qu' and is_grey(P[i][3]):
                b_ = bb_of([i]); d_ = sorted([b_[2] - b_[0], b_[3] - b_[1]])
                if d_[0] >= 2.5: FD.append(d_)
    FAMS = ibeam_families(FD); TW, TH = FAMS[0]          # (code 007) a template per family of the floor, not one median
    print('F1 templates', [(round(a, 2), round(b, 2)) for a, b in FAMS], 'from', len(FD), 'fills')
    mk = None
    _OTH = None
    def cladding(k, mb):
        """(code 008, ПК1-П3) the casing and the plates of a column are the column: thin lines of the column that make a
        closed outline (a rounded casing over a flange, a hatched base plate - floor 5 of client A, 271 and more strokes went
        to 'loose' and to desks) - a connected group of >= 6 thin lines outside the I-beam box, within 300 mm of it, touching it within
        0.4 pt, whose lines close a face with the box - stay with the column. A lone thin stroke at the I-beam is still a
        service tick. <один пример: клиент А, 5 этаж>
        Switched off by cfg.FIX7_CLADDING = False"""
        if not getattr(cfg, 'FIX7_CLADDING', True): return set()
        z = pt_mm(300); Z = (mb[0] - z, mb[1] - z, mb[2] + z, mb[3] + z)   # floor 5: casings and plates reach 250 mm off the I-beam
        # outside the I-beam box only: inside it the I-beam's own outline and the owner's rule of service ticks hold
        #   (floor 4: thin ticks along a flange are service marks, owner 03.10.2026)
        thin = [i for i in members(k) if P[i][0] == 'l' and (P[i][1] or 0) < 0.45
                and all(Z[0] <= v[0] <= Z[2] and Z[1] <= v[1] <= Z[3] for v in pts(P[i]))
                and not all(mb[0] - 0.4 <= v[0] <= mb[2] + 0.4 and mb[1] - 0.4 <= v[1] <= mb[3] + 0.4 for v in pts(P[i]))]
        if len(thin) < 6: return set()
        # lines of another object at the column (floor 4: a fire cabinet at the column of axis 6) are not its casing
        global _OTH
        if _OTH is None:
            mem_ = mem_index(); NOT = {'column', 'lpart', 'lpartc', 'loose', 'misc', 'wallline', 'glass', 'facade', 'gklpart', 'glasspart', 'mark'}
            hs = [(k2, hull_ids(mem_.get(k2, []))) for k2, q2 in enumerate(inst) if q2['key'] not in NOT]
            _OTH = [(k2, h.buffer(0.3)) for k2, h in hs if h is not None]
            _OTH = (_OTH, STRtree([h for _, h in _OTH]) if _OTH else None)
        oth, otr = _OTH
        geo = {i: LineString(P[i][4]) for i in thin}
        tr = STRtree([geo[i] for i in thin]); seen = set(); keep = set()
        ib = box(*mb).buffer(0.4)
        for i0 in thin:
            if i0 in seen: continue
            grp = [i0]; seen.add(i0); st = [i0]
            while st:
                a = st.pop()
                for j in tr.query(geo[a].buffer(0.15)):
                    b = thin[j]
                    if b not in seen and geo[a].distance(geo[b]) <= 0.15: seen.add(b); grp.append(b); st.append(b)
            if len(grp) < 6 or not any(geo[i].intersects(ib) for i in grp): continue
            # a casing or a plate: a hatched plate or a rounded casing is drawn by 20+ short pieces; a smaller group must
            #   close a face with the I-beam's box (a casing over a flange is open towards it). Partition ends and ticks are
            #   a few lines and close nothing
            mbx = box(*mb)
            if otr is not None and sum(1 for i in grp if any(oth[j][0] != k and oth[j][1].contains(geo[i]) for j in otr.query(geo[i]))) >= 0.5 * len(grp): continue
            if len(grp) < 20 and not any(f.area >= 0.25 and f.intersection(mbx).area < 0.5 * f.area
                                         for f in polygonize(unary_union([geo[i] for i in grp] + [mbx.exterior]))): continue
            keep |= set(grp)
        return keep
    def foreign_out(k, mb, outline):
        """lines of column k that are not its own: outside the I-beam box, or (filled I-beam) thin long strokes off
        its fill outline - a service tick (owner: "Она сильно по толщине от колонны отличается")"""
        global mk
        fo = []
        keep = cladding(k, mb)
        for i in members(k):
            p = P[i]
            if i in keep: continue
            inside = all(mb[0] - 0.4 <= v[0] <= mb[2] + 0.4 and mb[1] - 0.4 <= v[1] <= mb[3] + 0.4 for v in pts(p))
            if inside:
                if outline is None or p[0] != 'l': continue
                g = LineString(p[4])
                if not ((p[1] or 0) < 0.45 and g.length >= 1.0 and not outline.contains(g)): continue
            fo.append(i)
        left = list(fo)
        for pas in range(6):                          # chains of foreign lines: rehome from the outside in
            nxt = []
            for i in left:
                g = LineString(pts(P[i])) if len(pts(P[i])) > 1 else Point(pts(P[i])[0])
                if not WU.is_empty and WU.buffer(0.2).contains(g): to_wall(i, 'F1'); r = 'WALL'
                else: r = rehome(i, k, 'F1')
                if r is None: nxt.append(i)
                else: spot('F1', g.centroid.coords[0], f'колонна #{k}: чужая линия → {r if r == "WALL" else kname(r)}')
            if len(nxt) == len(left): break
            left = nxt
        for i in left:
            p = P[i]; g = LineString(pts(p)) if len(pts(p)) > 1 else Point(pts(p)[0])
            inside = all(mb[0] - 0.4 <= v[0] <= mb[2] + 0.4 and mb[1] - 0.4 <= v[1] <= mb[3] + 0.4 for v in pts(p))
            if inside and p[0] == 'l' and (p[1] or 0) < 0.45:
                mk = mk if mk is not None else mark_inst()
                move(i, mk, 'F1'); spot('F1', g.centroid.coords[0], f'колонна #{k}: тонкая черта у двутавра → служебная метка'); continue
            nb = [n for n in T.query(g.buffer(0.3)) if own.get(LN[n][0]) not in (k, None) and G[n].distance(g) <= 0.3]
            if nb:
                k2 = own[LN[min(nb, key=lambda n: G[n].distance(g))][0]]
                move(i, k2, 'F1'); spot('F1', g.centroid.coords[0], f'колонна #{k}: чужая линия → {kname(k2)} (рядом)'); continue
            if True:
                lk = next((k2 for k2, q2 in enumerate(inst) if q2['key'] == 'loose'), None)
                lk = lk if lk is not None else new_inst('loose', 'Мелкие элементы исходника (россыпью, не блоком)', 'A-00----E-', 'F1')
                move(i, lk, 'F1'); spot('F1', g.centroid.coords[0], f'колонна #{k}: чужая линия → россыпь')
        return len(fo)
    for k, q in enumerate(list(inst)):
        if q['key'] != 'column' or 'кругл' in q['name']: continue
        ids = members(k)
        Ls = [i for i in ids if P[i][0] == 'l']
        if not Ls:
            # a column whose lines others took (owner: "колонну забрали стол и экран")
            fl = [i for i in ids if P[i][0] == 'qu' and is_grey(P[i][3])]
            if not fl: continue
            mb = bb_of(fl); got = 0
            for i in prims_inside(box(*mb), 0.4):
                if okey(i) not in ('column', 'WALL'): got += move(i, k, 'F1')
            spot('F1', ((mb[0] + mb[2]) / 2, (mb[1] + mb[3]) / 2), f'колонна #{k}: линии двутавра возвращены ({got})'); continue
        thick = [i for i in Ls if (P[i][1] or 0) >= 0.45]
        outline = None
        if 'за стеной' in q['name']:
            mb = bb_of(thick) if thick else bb_of(Ls)
        else:
            fl = [i for i in ids if P[i][0] == 'qu' and is_grey(P[i][3])]
            fd = [bb_of([i]) for i in fl]; fd = [b_ for b_ in fd if fam_of(sorted([b_[2] - b_[0], b_[3] - b_[1]]), FAMS) is not None]
            if fd:
                mb = fd[0]
                outline = unary_union([LineString(pts(P[i]) + [pts(P[i])[0]]) for i in fl]).buffer(0.15)
            else:
                cnt, mb = max((best_box(Ls, tw_, th_, ishape) for tw_, th_ in FAMS), key=lambda r_: r_[0])   # an I-beam drawn without the fill: its outline in any pen, any family
                if cnt < 6:
                    # not a column: no I-beam of the family in it (owner's place: a piece of a cabinet) - dissolve
                    n_ = 0
                    for i in list(ids): n_ += rehome(i, k, 'F1') is not None
                    for i in members(k):
                        hk = None
                        for k2, q2 in enumerate(inst):
                            if k2 != k and q2['key'] in ('rack', 'wardrobe') and q2.get('bbx') and box(*q2['bbx']).buffer(1.0).contains(Point(pts(P[i])[0])): hk = k2; break
                        if hk is not None: move(i, hk, 'F1')
                    q['dissolved'] = True
                    spot('F1', ((min(v[0] for i in ids for v in pts(P[i])) + max(v[0] for i in ids for v in pts(P[i]))) / 2,
                                (min(v[1] for i in ids for v in pts(P[i])) + max(v[1] for i in ids for v in pts(P[i]))) / 2), f'«колонна» #{k}: двутавра нет — распущена')
                    continue
        q['ibeam_box'] = tuple(round(v, 2) for v in mb)
        foreign_out(k, mb, outline)
        # the I-beam's own lines that others took (a web line in a partition): back to the column (owner: "недостающие найти")
        cpen = collections.Counter(pen(i) for i in members(k) if P[i][0] == 'l').most_common(1)
        for i in prims_inside(box(*mb), 0.3):
            if okey(i) in PART | FALLBACK | {'desk', 'desk_o', 'screen', 'stair', 'wallline', 'wcacc', 'fire', 'rack', 'wardrobe'}:
                if P[i][0] == 'l' and cpen and pen(i) != cpen[0][0] and not (outline is not None and outline.contains(LineString(P[i][4]))): continue
                if move(i, k, 'F1'): spot('F1', pts(P[i])[0], f'колонна #{k}: своя линия возвращена от «{okey(i)}»')
    # grey I-beam fills that no column holds (the column at axis 5/Г went into a wardrobe): a column each
    made = 0
    for i, p in enumerate(P):
        if p[0] != 'qu' or not is_grey(p[3]) or okey(i) == 'column': continue
        b_ = bb_of([i]); d_ = sorted([b_[2] - b_[0], b_[3] - b_[1]])
        if fam_of(d_, FAMS) is None: continue
        k = new_inst('column', 'Колонна стальная (двутавр)', 'A-28----E-', 'F1'); frm = okey(i)
        for j in prims_inside(box(*b_), 0.4):
            if okey(j) != 'WALL' and not (P[j][0] == 'l' and (P[j][1] or 0) < 0.45 and math.dist(P[j][4][0], P[j][4][-1]) >= 1.0): move(j, k, 'F1')
        made += 1; spot('F1', ((b_[0] + b_[2]) / 2, (b_[1] + b_[3]) / 2), f'двутавр (заливка) у «{frm}» стал колонной')
    mem = mem_index()
    # I-beams of the source that no column holds: thick clusters of the family size, and thin ones at a missing pair
    TKL = [n for n, (i, a, b) in enumerate(LN) if (P[i][1] or 0) >= 0.55]
    TKs = set(TKL); seen = set()
    ri, rj = TW, TH
    for s in TKL:
        if s in seen: continue
        st = [s]; seen.add(s); cp = []
        while st:
            b_ = st.pop(); cp.append(b_)
            for c_ in T.query(G[b_].buffer(0.15)):
                if c_ in TKs and c_ not in seen and G[b_].distance(G[c_]) <= 0.15: seen.add(c_); st.append(c_)
        xs = [v for n in cp for v in (LN[n][1][0], LN[n][2][0])]; ys = [v for n in cp for v in (LN[n][1][1], LN[n][2][1])]
        w_, h_ = max(xs) - min(xs), max(ys) - min(ys)
        if not (any(abs(min(w_, h_) - ri) <= 0.3 * ri and abs(max(w_, h_) - rj) <= 0.3 * rj for ri, rj in FAMS) and len(cp) >= 6): continue
        ow = collections.Counter(okey(LN[n][0]) for n in cp)
        if ow.get('column', 0) >= 0.5 * len(cp): continue
        k = new_inst('column', 'Колонна стальная (двутавр, по исходнику)', 'A-28----E-', 'F1')
        mb = box(min(xs), min(ys), max(xs), max(ys))
        for i in prims_inside(mb, 0.3):
            if okey(i) not in ('WALL',): move(i, k, 'F1')
        made += 1; spot('F1', mb.centroid.coords[0], f'двутавр у «{ow.most_common(1)[0][0]}» стал колонной')
    # pairs along a wall: at the place of a missing pair, an I-beam of the template size drawn with any pen
    mem_index()
    CC = []
    for k, q in enumerate(inst):
        if q['key'] == 'column' and 'кругл' not in q['name'] and not q.get('dissolved'):
            ids = [i for i in _MEM.get(k, []) if P[i][0] == 'l' and (P[i][1] or 0) >= 0.45]
            if ids:
                xs = [v[0] for i in ids for v in pts(P[i])]; ys = [v[1] for i in ids for v in pts(P[i])]
                CC.append((k, ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2)))
    def partners(k, x, y, ax):
        if ax == 'v': return [k2 for k2, (x2, y2) in CC if k2 != k and abs(x2 - x) <= 1.5 and 8 <= abs(y2 - y) <= 25]
        return [k2 for k2, (x2, y2) in CC if k2 != k and abs(y2 - y) <= 1.5 and 8 <= abs(x2 - x) <= 25]
    pc = dict(CC)
    for ax, crd in (('v', 1), ('h', 0)):
        rows = collections.defaultdict(list)
        for k, cxy in CC: rows[round(cxy[crd] / 3)].append((k, cxy))
        for rk, mem_ in rows.items():
            paired = [(k, cxy) for k, cxy in mem_ if partners(k, cxy[0], cxy[1], ax)]
            if len(paired) < 2: continue
            off = statistics.median(pc[partners(k, cxy[0], cxy[1], ax)[0]][crd] - cxy[crd] for k, cxy in paired)
            for k, cxy in mem_:
                if partners(k, cxy[0], cxy[1], ax): continue
                ex = (cxy[0], cxy[1] + off) if ax == 'v' else (cxy[0] + off, cxy[1])
                # the partner's own template (the pair across the north wall is a T-profile 'behind the wall')
                pk = partners(paired[0][0], paired[0][1][0], paired[0][1][1], ax)[0]
                pids = [i for i in members(pk) if P[i][0] == 'l']
                pxs = [v[0] for i in pids for v in pts(P[i])]; pys = [v[1] for i in pids for v in pts(P[i])]
                tw, th = max(pxs) - min(pxs), max(pys) - min(pys)
                B = box(ex[0] - tw / 2 - 0.8, ex[1] - th / 2 - 0.8, ex[0] + tw / 2 + 0.8, ex[1] + th / 2 + 0.8)
                ids = [i for i in prims_inside(B) if P[i][0] == 'l' and okey(i) not in ('column', 'WALL')]
                if len(ids) < 4:
                    spot('F1', ex, f'пары для колонны #{k} в исходнике нет'); continue
                xs = [v[0] for i in ids for v in pts(P[i])]; ys = [v[1] for i in ids for v in pts(P[i])]
                if abs((max(xs) - min(xs)) - tw) > 0.35 * tw or abs((max(ys) - min(ys)) - th) > 0.35 * th:
                    spot('F1', ex, f'пары для колонны #{k}: в исходнике {max(xs) - min(xs):.1f}×{max(ys) - min(ys):.1f} pt, не профиль'); continue
                k2 = new_inst('column', inst[pk]['name'], 'A-28----E-', 'F1')
                for i in ids: move(i, k2, 'F1')
                made += 1; spot('F1', ex, f'пара колонны #{k}: профиль в исходнике стал колонной')
    print('F1', dict(LOG['F1']), 'new columns', made, round(time.time() - t0, 1), 's')

# ====================================================================================== F2 furniture rectangles
def inst_hulls(keys, mem=None):
    mem = mem or mem_index(); out = []
    for k, q in enumerate(inst):
        if q['key'] in keys:
            h = hull_ids(mem.get(k, []) + list(SH.get(k, ())))
            if h is not None and h.area >= 1.0: out.append((k, h))
    return out
def rect_faces(exclude_keys=('WALL', 'chair', 'roomsep', 'axmark')):
    ids = [n for n, (i, a, b) in enumerate(LN) if G[n].length >= 0.05 and not (okeys(i) & set(exclude_keys))]
    faces = list(polygonize(unary_union([G[n] for n in ids])))
    out = []
    for f in faces:
        r = f.minimum_rotated_rectangle
        if r.area <= 0 or f.area / r.area < 0.95: continue
        cc = list(r.exterior.coords); e = sorted([math.dist(cc[0], cc[1]), math.dist(cc[1], cc[2])])
        out.append((f, r, e))
    return out, ids
def boundary_lines(f, tol=0.35, share_min=0.8):
    z = f.exterior.buffer(tol); res = []
    for n in T.query(z):
        g = G[n]
        if g.length < 0.05: continue
        if g.intersection(z).length >= share_min * g.length: res.append(n)
    return res
if 2 in STEPS:
    mem = mem_index()
    FH = inst_hulls(FURN | HOSTS - {'door', 'door45'}, mem); FHT = STRtree([h for k, h in FH])
    SEATH = inst_hulls(SEATS, mem); STT = STRtree([h for k, h in SEATH]) if SEATH else None
    STH = inst_hulls({'stair'}, mem)
    DOORH = inst_hulls({'door', 'door45'}, mem); DTT = STRtree([h for k, h in DOORH]) if DOORH else None
    RACKS = inst_hulls({'rack', 'wardrobe'}, mem)
    faces, _ = rect_faces()
    FBK = FALLBACK | {'lpart', 'lpartc'}
    SHARE_OK = (FURN | {'column', 'fire', 'lift', 'stair', 'door', 'door45', 'wallline'} | PART | GLAZ) - SEATS
    cand = []
    for f, r, e in faces:
        if not (250 * PT <= e[0] <= 2500 * PT and 280 * PT <= e[1] <= 7600 * PT): continue
        bl = boundary_lines(f)
        tot = sum(G[n].length for n in bl) or 1
        fb = sum(G[n].length for n in bl if okey(LN[n][0]) in FBK | {'facade', 'glass'}) / tot
        if fb < 0.4: continue
        if any(FH[j][1].buffer(0.3).contains(f.buffer(-0.3)) for j in FHT.query(f.representative_point())): continue
        if DTT is not None and any(DOORH[j][1].intersection(f).area > 0.5 for j in DTT.query(f)): continue
        if not WU.is_empty and f.exterior.intersection(WU.buffer(0.3)).length > 0.5 * f.exterior.length: continue
        cand.append((f, r, e, bl))
    print('F2 candidates', len(cand))
    made = collections.Counter()
    def near_seat(f, d=4.0):
        if STT is None: return False
        return any(SEATH[j][1].distance(f) <= d for j in STT.query(f.buffer(d)))
    for f, r, e, bl in sorted(cand, key=lambda t: t[0].area):
        c = f.representative_point().coords[0]
        # stair cells (owner: "кусок лестницы как стены"): small cells next to a stair, <= 300 mm
        st = [k for k, h in STH if h.distance(f) <= 300 * PT]
        if st and e[1] <= 700 * PT:
            k = st[0]; why = 'ячейка марша у лестницы'
        else:
            k = None; why = ''
            sim = []
            for k2, h in RACKS:
                # the end cell of a row (owner: "соседние тумбочки узнаны, а крайние нет"): the row's depth, on the row's line
                if h.distance(f) > 0.8: continue
                rr = list(h.minimum_rotated_rectangle.exterior.coords)
                s1, s2 = (rr[0], rr[1]), (rr[1], rr[2])
                (ra, rb), (rs, rt) = (s1, s2) if math.dist(*s1) >= math.dist(*s2) else (s2, s1)
                depth = math.dist(rs, rt); ur = unit(ra, rb); nr = (-ur[1], ur[0]); hc = h.minimum_rotated_rectangle.centroid; fc_ = f.centroid
                off = abs((fc_.x - hc.x) * nr[0] + (fc_.y - hc.y) * nr[1])
                if abs(e[0] - depth) <= 0.2 * depth + 0.4 and off <= 0.8: sim.append(k2)
            if e[0] <= 420 * PT and e[1] >= 900 * PT and not near_seat(f, 1.0):
                key_, name_, lay_ = 'screen', 'Экран настольный / кабель-канал бенча', 'A-82----E-'; why = 'полоса между столами'
            elif near_seat(f):
                key_, name_, lay_ = 'desk_o', 'Стол рабочий (контур по исходнику)', 'A-82----E-'; why = 'стол: рядом сиденье'
            elif sim:
                key_, name_, lay_ = inst[sim[0]]['key'], inst[sim[0]]['name'], inst[sim[0]]['layer']; why = 'крайняя ячейка ряда шкафов'
            else:
                key_, name_, lay_ = 'furn_src', 'Мебель по контуру (по исходнику, уточнить)', 'A-82----E-'; why = 'мебель по контуру'
            k = new_inst(key_, name_, lay_, 'F2', bbx=tuple(round(v, 2) for v in f.bounds))
        made[why] += 1
        long_side = e[1] + 0.6
        # the furniture's pen: the pen of most of the face's outline by length; a line of another pen (the thick outline
        #   of a pilaster a desk stands at - floor 4 at x 1105, y 520) is not the furniture's edge: shared, not taken
        _fp = collections.Counter()
        for m in bl: _fp[pen(LN[m][0])] += G[m].length
        fpen = _fp.most_common(1)[0][0] if _fp else None
        for n in bl:
            i = LN[n][0]; ok = okey(i)
            if ok in FBK and fpen is not None and pen(i) != fpen and G[n].length >= 1.0: share(i, k, 'F2')
            elif ok in FBK: move(i, k, 'F2')
            elif ok in ('facade', 'glass') and G[n].length <= long_side and (ok == 'glass' or WU.is_empty or G[n].distance(WU) > 0.3):
                # an edge a facade band or an operator box took: the furniture's own line when it ends at the corners
                ends_ok = all(min(math.dist(v, cc) for cc in f.exterior.coords) <= 0.6 for v in (LN[n][1], LN[n][2]))
                if fpen is not None and pen(i) != fpen: share(i, k, 'F2')           # drawn as the glazing / wall, not as the furniture
                elif ends_ok or ok == 'facade': move(i, k, 'F2')
                else: share(i, k, 'F2')
            elif ok in SHARE_OK and own.get(i) != k: share(i, k, 'F2')
        for i in prims_inside(f, 0.25):
            if okey(i) in FBK: move(i, k, 'F2')
        spot('F2', c, f'{why}: {e[1] * MM_PER_PT:.0f}×{e[0] * MM_PER_PT:.0f} мм → {inst[k]["key"]}')
    print('F2', dict(made), dict(LOG['F2']), round(time.time() - t0, 1), 's')

# ====================================================================================== F3 partitions at furniture
if 3 in STEPS:
    # F3a monitors (owner: "в переговорных мониторы для конференц-связи, которые стоят впритык к столу"): own7.monitor_bars -
    #   a thin bar of two parallel thick rows across the end of a table, about as long as the table is wide, free at both
    #   ends, with a stand behind it. Bar and stand become a monitor (A-82), not a partition, not glazing; the table's end
    #   edge drawn only by the bar's near row is shared with the table (п. 240). All monitors of a floor are one family -
    #   the sizes are compared and reported. The same finder is check S18* (gate7.py).
    mem = mem_index(); nmon = 0; MONS = []
    NOMON = {'WALL', 'chair', 'armchair', 'sofa', 'stool', 'column', 'stair', 'lift', 'door', 'door45', 'wc', 'sink', 'wcsink', 'monitor'}
    TBLK = {'mtable', 'rtable', 'desk_src', 'desk_o', 'furn_src', 'desk'}
    from own7 import monitor_bars
    mons, nrows, nbars, rej = monitor_bars(P, LN, G, T, near, okey, [(k, mem.get(k, [])) for k, q in enumerate(inst) if q['key'] in TBLK],
                                           NOMON, lambda poly: prims_inside(poly))
    print('F3a rows', nrows, 'bars', nbars, 'monitors', len(mons), 'rejected off-family', len(rej), round(time.time() - t0, 1), 's')
    for m in rej:
        bc = m['bar'].centroid
        spot('F3', (bc.x, bc.y), f'кандидат в мониторы вне семейства этажа: {m["Lb"] * MM_PER_PT:.0f}×{(m["depth"] + m["thick"]) * MM_PER_PT:.0f} мм — не применён')
    for m in mons:
        mk_ = new_inst('monitor', 'Монитор конференц-связи на стойке (по исходнику)', 'A-82----E-', 'F3', bbx=tuple(round(x, 2) for x in m['bar'].union(m['zone']).bounds))
        n_ = 0
        for i in m['bar_ids'] + m['stand']:
            if okey(i) in NOMON: continue
            n_ += move(i, mk_, 'F3')
        # the table's end edge drawn by the bar's near row: the edge of both (п. 240)
        tbl_edge = True; u = m['u']
        for kp, hp in m['parts']:
            own_edge = [i for i in mem.get(kp, []) if P[i][0] == 'l' and i not in m['bar_ids'] and i in POS and G[POS[i]].distance(m['bar']) <= 0.15
                        and abs(unit(*pts(P[i])[0:2])[0] * u[0] + unit(*pts(P[i])[0:2])[1] * u[1]) >= 0.995 and G[POS[i]].length >= 1.0]
            if not own_edge:
                tbl_edge = False
                for i in m['near_ids']:
                    if i in POS and G[POS[i]].distance(hp) <= 0.3: share(i, kp, 'F3')
        MONS.append((m['Lb'], m['depth'] + m['thick']))
        nmon += 1; bc = m['bar'].centroid
        spot('F3', (bc.x, bc.y), f'монитор у торца стола «{inst[m["k"]]["name"][:30]}»: {m["Lb"] * MM_PER_PT:.0f}×{(m["depth"] + m["thick"]) * MM_PER_PT:.0f} мм, '
             f'{n_} примитивов (стойка {len(m["stand"])})' + ('' if tbl_edge else ', ближняя линия — общая со столом'))
    if MONS:
        mL = statistics.median(m[0] for m in MONS); mD = statistics.median(m[1] for m in MONS)
        odd = [m for m in MONS if abs(m[0] - mL) > 0.15 * mL or abs(m[1] - mD) > 0.3 * mD + 0.3]
        print('F3a monitors', nmon, 'family', round(mL * MM_PER_PT), '×', round(mD * MM_PER_PT), 'мм', 'off-family', len(odd))
        for m in odd: spot('F3', (0, 0), f'монитор вне семейства: {m[0] * MM_PER_PT:.0f}×{m[1] * MM_PER_PT:.0f} мм')
    else:
        print('F3a monitors 0')
    mem = mem_index()
    PL = [n for n, (i, a, b) in enumerate(LN) if okey(i) in PART and G[n].length >= 0.3]
    PLs = set(PL); par = {n: n for n in PL}
    def fnd(x):
        while par[x] != x: par[x] = par[par[x]]; x = par[x]
        return x
    for a in PL:
        for b in T.query(G[a].buffer(0.15)):
            if b in PLs and b != a and G[a].distance(G[b]) <= 0.15: par[fnd(a)] = fnd(b)
    comp = collections.defaultdict(list)
    for n in PL: comp[fnd(n)].append(n)
    ANCH = (STRUCT_END - PART) | {'fire'}                 # a built-in fire cabinet stands in the wall line
    FH = inst_hulls(FURN, mem); FHT = STRtree([h for k, h in FH])
    FU = unary_union([h for k, h in FH]) if FH else None
    TBH = [(k, h) for k, h in FH if inst[k]['key'] in TABLES]; TBT = STRtree([h for k, h in TBH]) if TBH else None
    SEATH = inst_hulls(SEATS, mem); STT = STRtree([h for k, h in SEATH]) if SEATH else None
    MTH = [(k, h) for k, h in FH if inst[k]['key'] in ('mtable', 'rtable')]
    DH = [h for k, h in inst_hulls({'door', 'door45'}, mem)]
    SANZ = [box(*z) for z in getattr(cfg, 'SANZONES', [])]
    WC_PIECES = bool(getattr(cfg, 'FIX7_WC_PIECES', False))
    SANZU = unary_union([z.buffer(2.0) for z in SANZ]) if SANZ else None
    WCN = next((q['name'] for q in inst if q['key'] == 'wcacc'), 'Аксессуар санузла (сушилка, урна, поручень, смыв)')
    def anchored(ns):
        for a in ns:
            for b in T.query(G[a].buffer(0.5)):
                if b in PLs: continue
                ks = okeys(LN[b][0]); d_ = G[a].distance(G[b])
                if ks & ANCH and d_ <= 0.5: return True
            if not WU.is_empty and G[a].distance(WU) <= 0.5: return True
        return False
    def furn_of(g, edge_min=0.5):
        best = None
        for j in FHT.query(g.buffer(0.4)):
            k, h = FH[j]
            on_edge = g.intersection(h.exterior.buffer(0.4)).length / max(g.length, 1e-6)
            inner = h.buffer(-0.5); across = g.intersection(inner).length / max(g.length, 1e-6) if not inner.is_empty else 0
            sc = max(on_edge, across)
            if sc >= edge_min and (best is None or sc > best[0]): best = (sc, k, 'edge' if on_edge >= across else 'across')
        return best
    def end_anchored(n, e):
        for b in near(e, 0.3, n):
            if okeys(LN[b][0]) & STRUCT_END: return True
        return not WU.is_empty and Point(e).distance(WU) <= 0.5
    stats = collections.Counter()
    for root, ns in comp.items():
        if anchored(ns): continue
        g = unary_union([G[n] for n in ns])
        tot = sum(G[n].length for n in ns)
        # (code 007, regression of 06.10.2026) the partitions of WC cabins hold on to the installation frame line: inside an
        #   operator's washroom box a component is not 'hanging' unless the floor takes such pieces as accessories
        #   (FIX7_WC_PIECES) - the same geometry as gate7 S18* (п. 283)
        if SANZ and not WC_PIECES and g.intersection(SANZU).length >= 0.7 * tot: continue
        votes = collections.Counter()
        for n in ns:
            fo = furn_of(G[n])
            if fo: votes[(fo[1], fo[2])] += G[n].length
        tgt = None; why = ''
        if votes and sum(votes.values()) >= 0.5 * tot:
            (k, how), _ = votes.most_common(1)[0]; tgt = k
            why = ('барьер стола' if how == 'across' and inst[k]['key'] in ('desk', 'desk_o', 'desk_src') else
                   'край мебели' if how == 'edge' else 'поперёк мебели')
        if tgt is None and FU is not None and g.intersection(FU.buffer(0.4)).length >= 0.6 * tot:
            # a line across a run of furniture cells (the rod of a wardrobe run, the axis of a bench): the cell holding most
            ov = collections.Counter()
            for j in FHT.query(g.buffer(0.4)):
                k, h = FH[j]; ov[k] += g.intersection(h.buffer(0.4)).length
            tgt = ov.most_common(1)[0][0]; why = 'линия через ряд мебели'
        if tgt is None:
            ds = min([(SEATH[j][1].distance(g), SEATH[j][0], SEATH[j][1]) for j in STT.query(g.buffer(3))] or [(99, None, None)], key=lambda t: t[0]) if STT else (99, None, None)
            dt = min([(TBH[j][1].distance(g), TBH[j][0], TBH[j][1]) for j in TBT.query(g.buffer(3))] or [(99, None, None)], key=lambda t: t[0]) if TBT else (99, None, None)
            # a piece along a seat and not along the table (the armrest rail of a turned chair - floor 4 at x 1047-1088)
            #   is the seat's; a line between a seat and a table is the table's edge (owner's remark)
            along_seat = ds[2] is not None and g.intersection(ds[2].buffer(0.6)).length >= 0.8 * tot
            if ds[0] <= 3 and dt[0] <= 3:
                # across the table's facing edge (an armrest) - the seat's; along it - the table's edge
                nl = max(ns, key=lambda n: G[n].length); uc = unit(LN[nl][1], LN[nl][2])
                rr_ = list(dt[2].minimum_rotated_rectangle.exterior.coords); sc_ = ds[2].centroid
                side_ = min(((rr_[j], rr_[j + 1]) for j in range(4)), key=lambda e_: LineString(e_).distance(sc_))
                ut = unit(*side_)
                if along_seat and abs(uc[0] * ut[0] + uc[1] * ut[1]) < 0.5: tgt = ds[1]; why = 'часть сиденья'
                else: tgt = dt[1]; why = 'между сиденьем и столом: край стола'
            elif along_seat and dt[0] > 3: tgt = ds[1]; why = 'часть сиденья'
        # (code 007, regression of 06.10.2026) a hanging piece inside a washroom box is taken as an accessory only on a floor
        #   whose places of this branch were looked at (cfg.FIX7_WC_PIECES = True; plan/rules/70 §2: a rule that changes
        #   another floor is switched on by a field): on floor 5 of client A the branch made 72 'accessories' of the cabin
        #   partitions, 0.4-2.9 m, and the gate's S4 grew from 2 to 6
        if tgt is None and SANZ and WC_PIECES and g.intersection(unary_union([z.buffer(2.0) for z in SANZ])).length >= 0.7 * tot:
            tgt = new_inst('wcacc', WCN, 'A-74----E-', 'F3'); why = 'принадлежность санузла'
        if tgt is None and tot <= 6.0 and any(h.distance(g) <= 3.0 for h in DH):
            tgt = next((k for k, q in enumerate(inst) if q['key'] == 'doorhw'), None)
            tgt = tgt if tgt is not None else new_inst('doorhw', 'Фурнитура двери (ручка, упор, порог)', 'A-32----E-', 'F3'); why = 'фурнитура двери'
        if tgt is None:
            # a piece of an object it touches (a stool, an accessory, a cabinet): that object
            ct = collections.Counter()
            for n in ns:
                for e in (LN[n][1], LN[n][2]):
                    for b in near(e, 0.3, n):
                        kb = own.get(LN[b][0])
                        if kb is not None and inst[kb]['key'] in ('misc', 'equip', 'furn_src', 'rack', 'wardrobe', 'plant', 'monitor', 'mtable') + (('wcacc',) if WC_PIECES else ()):
                            ct[kb] += 1
            if ct: tgt = ct.most_common(1)[0][0]; why = 'часть соседнего объекта'
        if tgt is None:
            fs = [f for f in polygonize(g) if f.area >= 0.5]
            hb = g.minimum_rotated_rectangle
            if fs and sum(f.area for f in fs) >= 0.5 * max(hb.area, 1e-6):
                cc = list(hb.exterior.coords); e_ = sorted([math.dist(cc[0], cc[1]), math.dist(cc[1], cc[2])])
                if e_[1] <= 2500 * PT:
                    tgt = new_inst('furn_src', 'Мебель по контуру (по исходнику, уточнить)', 'A-82----E-', 'F3'); why = 'замкнутый предмет'
        if tgt is None:
            if tot <= 6.0 and all(not [b for b in near(LN[n][1], 0.2, n) + near(LN[n][2], 0.2, n) if b not in PLs] for n in ns):
                tgt = mark_inst('Служебная разметка (по исходнику)'); why = 'разметка'
        if tgt is None and tot <= 3.0:
            # a detail of up to 190 mm hanging by a wall (a hook, a door stop - floor 4 at x 822, y 184): not a partition
            bx_ = g.bounds
            if max(bx_[2] - bx_[0], bx_[3] - bx_[1]) <= 3.0:
                tgt = next((k for k, q in enumerate(inst) if q['key'] == 'misc' and q['name'].startswith('Мелкая деталь у стены')), None)
                tgt = tgt if tgt is not None else new_inst('misc', 'Мелкая деталь у стены (крючок, упор — по исходнику)', 'A-00----E-', 'F3')
                why = 'мелкая деталь'
        if tgt is None: stats['осталось висеть'] += 1; spot('F3', g.centroid.coords[0], f'висит: {len(ns)} линий, {tot:.1f} pt — не решено'); continue
        for n in ns: move(LN[n][0], tgt, 'F3')
        stats[why] += 1; spot('F3', g.centroid.coords[0], f'{why}: {len(ns)} линий → {inst[tgt]["key"]}')
    # partitions (and glazing lines a band or a box took) along a furniture edge over their whole length: the furniture's
    #   line; a real partition the furniture stands at (both ends at walls or partitions) shares the line with it
    mem = mem_index()
    FACL = unary_union([LineString(f) for f in [list(x) for x in getattr(cfg, 'FACADES', [])] if len(f) >= 2]) if getattr(cfg, 'FACADES', None) else None
    FUb = FU.buffer(0.4) if FU is not None else None
    for n, (i, a, b) in enumerate(LN):
        ok_ = okey(i)
        if ok_ not in PART | GLAZ or G[n].length < 1.0: continue
        if ok_ == 'facade' and FACL is not None and G[n].distance(FACL) <= 2.0: continue     # the glazing itself
        fo = furn_of(G[n], 0.9)
        # code 007 (floor 4, the glazing behind the monitor at x 417-440): a piece of a run that goes on past the furniture
        #   in another pen than the furniture's is the partition / glazing itself, not the furniture's edge
        if fo and FUb is not None:
            pc_ = collections.Counter(pen(j) for j in mem.get(fo[1], []) if P[j][0] == 'l')
            if pc_ and pen(i) != pc_.most_common(1)[0][0]:
                rn = run_of(n)
                if len(rn) > 1 and unary_union([G[m] for m in rn]).difference(FUb).length > 1.0: continue
        if not fo:
            # along a run of cells (a wardrobe run, a bench row): the cells it lies on
            if FU is None or ok_ not in PART or G[n].intersection(FU.boundary.buffer(0.4)).length < 0.9 * G[n].length: continue
            cells = [FH[j][0] for j in FHT.query(G[n].buffer(0.4)) if G[n].intersection(FH[j][1].exterior.buffer(0.4)).length >= 0.15 * G[n].length]
            if not cells: continue
            if end_anchored(n, a) and end_anchored(n, b):
                for k in cells: share(i, k, 'F3')
                stats['общая линия перегородки и ряда мебели'] += 1
            else:
                move(i, max(cells, key=lambda k: G[n].intersection(dict(FH)[k].exterior.buffer(0.4)).length), 'F3'); stats['линия вдоль ряда мебели'] += 1
            continue
        k = fo[1]; h = hull_ids(mem.get(k, []))
        if h is None: continue
        r = h.minimum_rotated_rectangle; cc = list(r.exterior.coords); side = max(math.dist(cc[0], cc[1]), math.dist(cc[1], cc[2]))
        if G[n].length > side + 0.6: continue
        if ok_ in PART and end_anchored(n, a) and end_anchored(n, b):
            stats['общая линия перегородки и мебели'] += share(i, k, 'F3')
        else:
            move(i, k, 'F3'); stats['линия по мебели'] += 1
    print('F3', dict(stats), dict(LOG['F3']), round(time.time() - t0, 1), 's')

# ====================================================================================== F4 doors
if 4 in STEPS:
    stats = collections.Counter(); mk = None
    BLOCKK = PART | GLAZ | {'wallline', 'column'}
    for k, q in enumerate(inst):
        if q['key'] != 'door' or 'door' not in q: continue
        d = q['door']; c, o, cl = d['c'], d['open'], d['closed']
        r = math.dist(c, o); a0 = math.atan2(o[1] - c[1], o[0] - c[0]); a1 = math.atan2(cl[1] - c[1], cl[0] - c[0])
        da = (a1 - a0 + math.pi) % (2 * math.pi) - math.pi
        sector = Polygon([c] + [(c[0] + r * math.cos(a0 + da * t / 16), c[1] + r * math.sin(a0 + da * t / 16)) for t in range(17)])
        if not sector.is_valid or sector.area < 1: continue
        inner = sector.buffer(-0.4); chord = LineString([c, cl]); leaf = LineString([c, o])
        ul = unit(c, o); uc = unit(c, cl)
        for n in T.query(sector):
            i = LN[n][0]
            if own.get(i) == k or okey(i) not in BLOCKK or G[n].length < 1.0: continue
            g = G[n]
            if not ((not inner.is_empty and g.intersects(inner) and g.intersection(inner).length >= 1.0) or g.crosses(chord)): continue
            v = unit(LN[n][1], LN[n][2])
            if abs(v[0] * ul[0] + v[1] * ul[1]) >= 0.985 and g.distance(leaf) <= 1.5:
                move(i, k, 'F4'); stats['кромка полотна → дверь'] += 1
            else:
                mk = mk if mk is not None else mark_inst('Служебная разметка в проёме двери (по исходнику)')
                move(i, mk, 'F4'); stats['линия в проёме → служебная разметка'] += 1
            spot('F4', g.interpolate(0.5, normalized=True).coords[0], f'дверь #{k}: {okey(i)}')
        # the opening between the jambs: lines along it (threshold, marking through the passage) are not walls
        un = unit(c, cl); nrm = (-un[1], un[0]); wd = math.dist(c, cl)
        band = Polygon([(c[0] - nrm[0] * 2.6, c[1] - nrm[1] * 2.6), (cl[0] - nrm[0] * 2.6, cl[1] - nrm[1] * 2.6),
                        (cl[0] + nrm[0] * 2.6, cl[1] + nrm[1] * 2.6), (c[0] + nrm[0] * 2.6, c[1] + nrm[1] * 2.6)])
        for n in T.query(band):
            i = LN[n][0]
            # partitions, and what the WC accessories or the fallback took in the opening (the threshold of a WC door)
            if own.get(i) == k or okey(i) not in PART | {'wcacc', 'misc', 'loose', 'FREE', 'wallline'} or G[n].length < 0.5: continue
            v = unit(LN[n][1], LN[n][2])
            if abs(v[0] * un[0] + v[1] * un[1]) < 0.985: continue
            if G[n].length > wd + 1.0 or G[n].intersection(band).length < 0.7 * G[n].length:
                # a single thin line running through the opening along it: floor marking, not a wall (owner: "служебная
                #   разметка в проходе тоже определилась как стена"); a thick face is left to the wall cut below
                if (P[i][1] or 0) < 0.45 and G[n].intersection(LineString([c, cl]).buffer(0.4)).length >= 0.8 * wd:
                    mk = mk if mk is not None else mark_inst('Служебная разметка в проёме двери (по исходнику)')
                    move(i, mk, 'F4'); stats['тонкая линия через проём → служебная разметка'] += 1
                    spot('F4', G[n].interpolate(0.5, normalized=True).coords[0], f'дверь #{k}: тонкая линия через проём — разметка')
                continue
            hw = next((kk for kk, qq in enumerate(inst) if qq['key'] == 'doorhw'), None)
            hw = hw if hw is not None else new_inst('doorhw', 'Фурнитура двери (ручка, упор, порог)', 'A-32----E-', 'F4')
            move(i, hw, 'F4'); stats['линия в проёме между косяками → порог'] += 1
            spot('F4', G[n].interpolate(0.5, normalized=True).coords[0], f'дверь #{k}: порог или разметка в проёме')
    # wall bodies drawn across a door opening (the diagonal WC partitions): the opening is cut out of the wall, the wall's
    #   lines left in it become the threshold of the door (owner: "проход не может быть перегорожен стеной")
    aff = [kx[0], 0, 0, ky[0], kx[1], ky[1]]; cut_n = 0
    hw = next((kk for kk, qq in enumerate(inst) if qq['key'] == 'doorhw'), None)
    for k, q in enumerate(inst):
        if q['key'] != 'door' or 'door' not in q: continue
        c, cl = q['door']['c'], q['door']['closed']
        pair = [q2['door']['c'] for q2 in inst if q2 is not q and q2['key'] == 'door' and 'door' in q2 and math.dist(q2['door']['closed'], cl) <= 1.6]
        far = pair[0] if pair else cl
        ch = LineString([c, far]); wd = ch.length
        if wd < 4: continue
        inwall = ch.intersection(WU).length if not WU.is_empty else 0
        if inwall < 0.5 * wd: continue
        un = unit(c, far); nrm = (-un[1], un[0]); s0 = (c[0] + un[0] * 0.3, c[1] + un[1] * 0.3); s1 = (far[0] - un[0] * 0.3, far[1] - un[1] * 0.3)
        cutb = Polygon([(s0[0] - nrm[0] * 4, s0[1] - nrm[1] * 4), (s1[0] - nrm[0] * 4, s1[1] - nrm[1] * 4), (s1[0] + nrm[0] * 4, s1[1] + nrm[1] * 4), (s0[0] + nrm[0] * 4, s0[1] + nrm[1] * 4)])
        ch_ = set()
        for cw, v in WD['Wpt'].items():
            out = []
            for p_ in v:
                for g_ in getattr(p_, 'geoms', [p_]):
                    if g_.intersects(ch):
                        d_ = g_.difference(cutb); ch_.add(cw)
                        out += [x for x in getattr(d_, 'geoms', [d_]) if x.geom_type == 'Polygon' and x.area >= 0.05]
                    else: out.append(g_)
            WD['Wpt'][cw] = out
        for cw in ch_: WD['W'][cw] = [affine_transform(g_, aff) for g_ in WD['Wpt'][cw]]
        WU = walls_union(); WUb = prep(WU.boundary.buffer(0.2)) if not WU.is_empty else None
        hw = hw if hw is not None else new_inst('doorhw', 'Фурнитура двери (ручка, упор, порог)', 'A-32----E-', 'F4')
        for i in prims_inside(cutb.buffer(0.6)):
            # wall prims and the unowned strokes the wall's fill covered: now in the opening, drawn as the threshold
            if (i in WP or i not in own) and not WU.buffer(0.1).contains(LineString(pts(P[i])) if len(pts(P[i])) > 1 else Point(pts(P[i])[0])): move(i, hw, 'F4')
        cut_n += 1; spot('F4', ch.interpolate(0.5, normalized=True).coords[0], f'дверь #{k}: стена в проёме вырезана {sorted(ch_)}')
    stats['стена в проёме вырезана'] += cut_n
    for k, q in enumerate(inst):
        if q['key'] != 'door45': continue
        h = hull_ids(members(k))
        if h is None: continue
        inn = h.buffer(-0.3)
        if inn.is_empty: continue
        for n in T.query(inn):
            i = LN[n][0]
            if own.get(i) != k and okey(i) in PART and G[n].intersection(inn).length >= 1.0: move(i, k, 'F4'); stats['линия в полотне → дверь'] += 1
    print('F4', dict(stats), dict(LOG['F4']), round(time.time() - t0, 1), 's')

# ====================================================================================== F5 stairs
if 5 in STEPS:
    mem = mem_index(); stats = collections.Counter()
    STH = inst_hulls({'stair'}, mem)
    for k, h in STH:
        inn = h.buffer(-0.3)
        for i in prims_inside(inn):
            if okey(i) in PART | {'misc', 'loose', 'FREE', 'wallline'} and not (okey(i) == 'FREE' and P[i][0] == 'qu'): stats['внутри лестницы'] += move(i, k, 'F5')
    # flights next to a stair: >= 3 parallel equal treads, 3-8 pt apart, of partitions, <= 300 mm from it
    PL = [n for n, (i, a, b) in enumerate(LN) if okey(i) in PART | {'misc', 'loose'} and 2 <= G[n].length <= 25]
    for k, h in STH:
        zone = h.buffer(300 * PT)
        cand = [n for n in PL if zone.intersects(G[n]) and not h.buffer(-0.3).contains(G[n])]
        groups = collections.defaultdict(list)
        for n in cand:
            a_ = math.degrees(math.atan2(LN[n][2][1] - LN[n][1][1], LN[n][2][0] - LN[n][1][0])) % 180
            groups[(round(a_ / 3), round(G[n].length / 1.0))].append(n)
        for key_, ns in groups.items():
            if len(ns) < 3: continue
            A = math.radians(key_[0] * 3); nx, ny = -math.sin(A), math.cos(A)
            ds = sorted((G[n].centroid.x * nx + G[n].centroid.y * ny, n) for n in ns)
            gaps = [ds[t + 1][0] - ds[t][0] for t in range(len(ds) - 1)]
            run = [ds[0][1]]
            for t, gp in enumerate(gaps):
                if 2.5 <= gp <= 8.5: run.append(ds[t + 1][1])
                else:
                    if len(run) >= 3: break
                    run = [ds[t + 1][1]]
            if len(run) >= 3:
                for n in run: move(LN[n][0], k, 'F5')
                stats['марш у лестницы'] += 1; spot('F5', G[run[0]].centroid.coords[0], f'марш {len(run)} ступеней → лестница #{k}')
    print('F5', dict(stats), dict(LOG['F5']), round(time.time() - t0, 1), 's')

# ====================================================================================== F6 glazing wedges
if 6 in STEPS:
    CAND = [n for n, (i, a, b) in enumerate(LN) if okey(i) in PART | {'wallline'} | GLAZ and G[n].length >= 0.3]
    CS = set(CAND); COS30 = math.cos(math.radians(30)); cont = {}
    for n in CAND:
        for ei, (e, o) in enumerate(((LN[n][1], LN[n][2]), (LN[n][2], LN[n][1]))):
            u = unit(o, e); lst = []
            for m in near(e, 0.2, n):
                if m not in CS: continue
                d0 = math.dist(LN[m][1], e); d1 = math.dist(LN[m][2], e)
                if min(d0, d1) > 0.25: continue
                me = 0 if d0 <= d1 else 1
                v = unit(LN[m][1], LN[m][2]) if me == 0 else unit(LN[m][2], LN[m][1])
                if u[0] * v[0] + u[1] * v[1] >= COS30: lst.append((m, me))
            cont[(n, ei)] = lst
    def reach(n, ei, depth=4):
        fr = [(n, ei)]; sn = {n}
        for d in range(depth):
            nx = []
            for x, xe in fr:
                for m, me in cont[(x, xe)]:
                    if okey(LN[m][0]) in GLAZ: return m
                    if m in sn: continue
                    sn.add(m); nx.append((m, 1 - me))
            fr = nx
        return None
    nw = 0
    for n in CAND:
        if okey(LN[n][0]) in GLAZ: continue
        m0 = reach(n, 0); m1 = reach(n, 1) if m0 is not None else None
        if m0 is not None and m1 is not None:
            k = own.get(LN[m0][0])
            if k is not None: nw += move(LN[n][0], k, 'F6'); spot('F6', G[n].centroid.coords[0], f'вставка {okey(LN[n][0])} → {inst[k]["key"]}')
    print('F6', nw, dict(LOG['F6']), round(time.time() - t0, 1), 's')

# ====================================================================================== F9 WC
def wcacc_faces(rule, stats):
    """WC accessories: a line on a wall face goes to the wall, a line on a partition / wall line / glazing line - to it
    (owner: "в аксессуарах санузлов части стен"); the same thresholds as check S23*"""
    mem = mem_index()
    PARTLN = [n for n, (i, a, b) in enumerate(LN) if okey(i) in PART | {'wallline', 'glass'}]
    PT_ = STRtree([G[n] for n in PARTLN]) if PARTLN else None
    WBND = WU.boundary.buffer(0.3) if not WU.is_empty else None
    for k, q in enumerate(inst):
        if q['key'] != 'wcacc': continue
        for i in list(mem.get(k, [])):
            if P[i][0] != 'l': continue
            g = LineString(P[i][4])
            if g.length < 1.0: continue
            if WBND is not None and g.intersection(WBND).length >= 0.8 * g.length: to_wall(i, rule); stats['грань стены из аксессуаров'] += 1; continue
            if PT_ is not None:
                hit = [PARTLN[j] for j in PT_.query(g.buffer(0.1)) if G[PARTLN[j]].buffer(0.1).intersection(g).length >= 0.8 * g.length]
                if hit: move(i, own[LN[hit[0]][0]], rule); stats['линия перегородки из аксессуаров'] += 1
if 9 in STEPS:
    stats = collections.Counter()
    wcacc_faces('F9', stats)
    mem = mem_index()
    WBND = WU.boundary.buffer(0.3) if not WU.is_empty else None
    # fixtures: what lies outside the exemplar's box placed on the instance is not the fixture's
    for k, q in enumerate(inst):
        if q['key'] not in ('wc', 'sink') or 'tpl' not in q: continue
        tb = q['tplbb']; D = q['D']; an = q['anchor']; t_ = q['t']
        def tf(p): r = (p[0] - an[0], p[1] - an[1]); return (t_[0] + D[0] * r[0] + D[1] * r[1], t_[1] + D[2] * r[0] + D[3] * r[1])
        bx = MultiPoint([tf((tb[0], tb[1])), tf((tb[2], tb[1])), tf((tb[2], tb[3])), tf((tb[0], tb[3]))]).envelope.buffer(0.4)
        for i in list(mem.get(k, [])):
            if all(bx.contains(Point(v)) for v in pts(P[i])): continue
            r = rehome(i, k, 'F9')
            if r is None and P[i][0] == 'l':
                g = LineString(P[i][4])
                if WBND is not None and g.intersection(WBND).length >= 0.6 * g.length: to_wall(i, 'F9'); r = 'WALL'
            if r is not None: stats['лишнее у прибора'] += 1
    print('F9', dict(stats), dict(LOG['F9']), round(time.time() - t0, 1), 's')

# ====================================================================================== F10 openings
OPENINGS = []
if 10 in STEPS:
    mem = mem_index()
    def polys(g): return [g] if g.geom_type == 'Polygon' else [x for x in getattr(g, 'geoms', []) if x.geom_type == 'Polygon']
    M2 = MM_PER_PT ** 2 / 1e6
    WB = [p for v in WD['Wpt'].values() for g in v for p in polys(g)]
    SEPC = [tuple(c) for c in getattr(cfg, 'ROOMSEP_COLORS', [(0.5, 0.0, 0.5)])]
    def is_sep(p): return p[0] == 'l' and p[2] is not None and any(max(abs(p[2][j] - c[j]) for j in range(3)) <= 0.03 for c in SEPC)
    BK = ('lpart', 'lpartc', 'glass', 'facade', 'door45', 'column', 'wallline', 'railing', 'gklpart', 'glasspart', 'loose')
    BL = [LineString(pts(P[i])) for k, q in enumerate(inst) if q['key'] in BK for i in mem.get(k, []) if P[i][0] in ('l', 'c') and not is_sep(P[i])]
    DOORL = [LineString([q['door']['c'], q['door']['closed']]) for q in inst if q['key'] == 'door' and q.get('door')]
    SEPL = [LineString(pts(p)) for p in P if is_sep(p)]
    BU = unary_union([g.buffer(0.15) for g in BL + DOORL + SEPL] + WB)
    rooms = [Polygon(h) for p in polys(BU) for h in p.interiors]; rooms = [r for r in rooms if r.area * M2 >= 1.0]
    RT = STRtree(rooms)
    stairs = [(k, h) for k, h in inst_hulls({'stair'}, mem)]
    by_room = collections.defaultdict(list); alone = []
    for k, h in stairs:
        cand = [int(j) for j in RT.query(h)]
        best = max(cand, key=lambda j: rooms[j].intersection(h).area, default=None)
        if best is not None and rooms[best].intersection(h).area >= 0.5 * h.area: by_room[best].append((k, h))
        else: alone.append((k, h))
    # (04.10.2026, строка 173) an opening only where this floor's slab has one: a flight that only goes up («ВВЕРХ»
    #   without «ВНИЗ») opens the slab of the floor above; outside a closed cage a short flight is a change of level
    #   inside the floor. The same rule decides in S27* (own7.stair_needs_opening)
    WORDS = sheet_words()
    NO_OPENING = []
    def needs(k, h, cage):
        ids_ = mem.get(k, []) + sorted(SH.get(k, ()))
        need, why, info = stair_needs_opening(P, ids_, h, MM_PER_PT, WORDS, in_cage=cage)
        inst[k]['opening_rule'] = dict(need=need, why=why, **info)
        if not need:
            NO_OPENING.append(dict(stair=k, name=inst[k]['name'], why=why, box=[round(v, 1) for v in h.bounds], **info))
            spot('F10', h.representative_point().coords[0], f'{inst[k]["name"]}: без проёма — {why}')
        return need
    for j, ss in by_room.items():
        r = rooms[j]; sa = unary_union([h for k, h in ss]).intersection(r).area
        cage = sa >= r.area / 3 and r.area * M2 <= 80
        ss = [(k, h) for k, h in ss if needs(k, h, cage)]
        if not ss: continue
        if cage: poly = r.buffer(0.2).buffer(-0.2); how = f'помещение: лестница — {sa / r.area:.0%} площади'
        else: poly = unary_union([h for k, h in ss]).minimum_rotated_rectangle.difference(WU); how = f'контур лестницы: помещение {r.area * M2:.0f} м², лестница — {sa / r.area:.0%}'
        OPENINGS.append(dict(kind='stair_cage', name='Проём: лестничная клетка', stairs=[k for k, h in ss], how=how, poly=poly))
    for k, h in alone:
        if not needs(k, h, False): continue
        OPENINGS.append(dict(kind='stair_cage', name='Проём: лестничная клетка', stairs=[k], how='контур лестницы: помещение не замкнуто', poly=h.minimum_rotated_rectangle.difference(WU)))
    OBJ = [h for k, h in inst_hulls({'desk', 'desk_o', 'desk_src', 'chair', 'armchair', 'sofa', 'mtable', 'rtable', 'rack', 'wardrobe', 'stair', 'lift',
                                     'wc', 'sink', 'plant', 'equip', 'reception', 'furn_src'}, mem)]
    TAGS = [Point(q['c']) for q in inst if q['key'] == 'tag' and q.get('c')]
    PU = unary_union([LineString(pts(P[i])).buffer(0.4) for k, q in enumerate(inst) if q['key'] in ('lpart', 'lpartc', 'railing', 'loose') for i in mem.get(k, []) if P[i][0] in ('l', 'c')])
    DU = unary_union([g.buffer(1.0) for g in DOORL]) if DOORL else None
    for r in rooms:
        if r.area * M2 < 10: continue
        if any(o.intersects(r.buffer(-0.5)) for o in OBJ if o.area > 0): continue
        if any(r.contains(t) for t in TAGS): continue
        if DU is not None and r.boundary.intersects(DU): continue
        sh = r.exterior.intersection(PU).length / r.exterior.length
        if sh < 0.7: continue
        OPENINGS.append(dict(kind='atrium', name='Проём: атриум', stairs=[], how=f'контур ограждения: {sh:.0%} края — перегородки', poly=r.buffer(0.2).buffer(-0.2)))
    for o in OPENINGS:
        g = o['poly']; g = max(polys(g), key=lambda x: x.area) if g.geom_type != 'Polygon' else g
        g = Polygon(g.exterior)
        k = new_inst('opening', o['name'], 'A-23----E-', 'F10', poly=[(round(x, 3), round(y, 3)) for x, y in g.exterior.coords], how=o['how'], kind=o['kind'], stairs=o['stairs'])
        o['k'] = k; o['area_m2'] = round(g.area * M2, 1)
        spot('F10', g.representative_point().coords[0], f'{o["name"]}: {o["area_m2"]} м², {o["how"]}')
    print('F10 openings', [(o['kind'], o['area_m2']) for o in OPENINGS], 'no opening:', [(o['stair'], o['why'][:40]) for o in NO_OPENING], round(time.time() - t0, 1), 's')

# ====================================================================================== F11 partition types
if 11 in STEPS:
    mem = mem_index(); stats = collections.Counter()
    if not WU.is_empty:
        WBz = WU.boundary.buffer(0.5); wl = None
        for n, (i, a, b) in enumerate(LN):
            if okey(i) in UNTYPED and G[n].length >= 1.0 and G[n].intersection(WBz).length >= 0.8 * G[n].length:
                wl = wl if wl is not None else new_inst('wallline', 'Линии стен (контур/отделка по исходнику)', 'A-222---E-', 'F11')
                move(i, wl, 'F11'); stats['грань стены'] += 1
    PL = [n for n, (i, a, b) in enumerate(LN) if okey(i) in UNTYPED]
    typ = {}
    ATR = [Polygon(inst[o['k']]['poly']).exterior for o in OPENINGS if o['kind'] == 'atrium']
    ATRB = unary_union(ATR).buffer(2.5) if ATR else None
    PLT = STRtree([G[n] for n in PL]) if PL else None
    for n in PL:
        g = G[n]
        if ATRB is not None and ATRB.contains(g): typ[n] = 'railing'; continue
        if g.length < 0.8: continue
        u = unit(LN[n][1], LN[n][2]); nrm = (-u[1], u[0]); dbl = False
        for j in PLT.query(g.buffer(4.2)):
            m = PL[j]
            if m == n or G[m].length < 0.8: continue
            v = unit(LN[m][1], LN[m][2])
            if abs(u[0] * v[0] + u[1] * v[1]) < 0.995: continue
            off = abs((LN[m][1][0] - LN[n][1][0]) * nrm[0] + (LN[m][1][1] - LN[n][1][1]) * nrm[1])
            if not (0.6 <= off <= 4.2): continue
            s0 = sorted([(LN[m][1][0] - LN[n][1][0]) * u[0] + (LN[m][1][1] - LN[n][1][1]) * u[1], (LN[m][2][0] - LN[n][1][0]) * u[0] + (LN[m][2][1] - LN[n][1][1]) * u[1]])
            ov = min(s0[1], g.length) - max(s0[0], 0)
            if ov >= 0.4 * min(g.length, G[m].length): dbl = True; break
        typ[n] = 'gklpart' if dbl else 'glasspart'
    # short pieces (studs, end caps) take the type of the lines they join
    for n in PL:
        if n in typ: continue
        votes = collections.Counter(typ[m] for e in (LN[n][1], LN[n][2]) for m in near(e, 0.2, n) if m in typ)
        typ[n] = votes.most_common(1)[0][0] if votes else 'glasspart'
    # one continuous wall - one type (owner 03.10.2026: "Тут должен быть один тип стены"): a run of lines meeting end to end
    #   with no junction takes the type of most of its length (a face piece with no partner opposite stays in its wall)
    TS = set(n for n in PL if typ.get(n) in ('gklpart', 'glasspart'))
    adj = collections.defaultdict(set)
    for n in TS:
        for e, o in ((LN[n][1], LN[n][2]), (LN[n][2], LN[n][1])):
            nb = [m for m in near(e, 0.2, n) if G[m].length >= 0.3]
            if len(nb) != 1 or nb[0] not in TS: continue
            m = nb[0]; u1 = unit(o, e)
            if math.dist(LN[m][1], e) <= 0.2: u2 = unit(LN[m][1], LN[m][2])
            elif math.dist(LN[m][2], e) <= 0.2: u2 = unit(LN[m][2], LN[m][1])
            else: continue
            if u1[0] * u2[0] + u1[1] * u2[1] >= math.cos(math.radians(20)): adj[n].add(m); adj[m].add(n)
    seen_ = set(); nfix = 0
    for n in list(adj):
        if n in seen_: continue
        st = [n]; seen_.add(n); ch = []
        while st:
            x = st.pop(); ch.append(x)
            for y in adj[x]:
                if y not in seen_: seen_.add(y); st.append(y)
        w = collections.Counter()
        for x in ch: w[typ[x]] += G[x].length
        t_ = w.most_common(1)[0][0]
        for x in ch:
            if typ[x] != t_: typ[x] = t_; nfix += 1
    stats['тип по всей полосе'] = nfix
    NAMES = {'gklpart': ('Перегородка ГКЛ (полая, без штриховки в исходнике)', 'A-222---E-'),
             'glasspart': ('Перегородка стеклянная (одинарная линия в исходнике)', 'A-22G---E-'),
             'railing': ('Ограждение атриума (по исходнику)', 'A-22G---E-')}
    for t, (nm, lay) in NAMES.items():
        ns = [n for n in PL if typ.get(n) == t]
        if not ns: continue
        par = {n: n for n in ns}; S = set(ns)
        def fnd(x):
            while par[x] != x: par[x] = par[par[x]]; x = par[x]
            return x
        for a in ns:
            for b in T.query(G[a].buffer(0.2)):
                if b in S and b != a and G[a].distance(G[b]) <= 0.2: par[fnd(a)] = fnd(b)
        comps = collections.defaultdict(list)
        for n in ns: comps[fnd(n)].append(n)
        for root, cn in comps.items():
            k = new_inst(t, nm, lay, 'F11')
            for n in cn: move(LN[n][0], k, 'F11')
            stats[t] += len(cn)
    # what is left in the untyped instances (fills, arcs) goes with the nearest typed partition
    mem = mem_index()
    TY = [(n, own[LN[n][0]]) for n in range(len(LN)) if okey(LN[n][0]) in ('gklpart', 'glasspart', 'railing')]
    TYT = STRtree([G[n] for n, k in TY]) if TY else None
    for k, q in enumerate(inst):
        if q['key'] not in UNTYPED: continue
        for i in list(mem.get(k, [])):
            if TYT is None: break
            g = LineString(pts(P[i])) if len(pts(P[i])) > 1 else Point(pts(P[i])[0])
            js = list(TYT.query(g.buffer(1.0)))
            if js:
                j = min(js, key=lambda j: G[TY[j][0]].distance(g)); move(i, TY[j][1], 'F11'); stats['остаток'] += 1
    print('F11', dict(stats), round(time.time() - t0, 1), 's')

# ====================================================================================== F8 strokes inside objects
if 8 in STEPS:
    mem = mem_index(); stats = collections.Counter()
    HL = inst_hulls(HOSTS, mem); HL = [(k, h.buffer(0.3)) for k, h in HL]; HT = STRtree([h for k, h in HL])
    WB = [g.buffer(0.3) for v in WD['Wpt'].values() for p in v for g in getattr(p, 'geoms', [p])]; WTt = STRtree(WB) if WB else None
    for i, p in enumerate(P):
        if p[0] not in ('l', 'c') or cls[i] in NOTDRAW: continue
        if not (okeys(i) <= {'loose', 'misc', 'FREE'}): continue
        q_ = pts(p)
        if len(q_) < 2: continue
        g = LineString(q_)
        if g.length < 0.05: continue
        done = False
        if WTt is not None:
            for j in WTt.query(g):
                if WB[j].contains(g): to_wall(i, 'F8'); stats['в теле стены'] += 1; done = True; break
        if done: continue
        best = None
        for j in HT.query(g):
            k, h = HL[j]
            if h.contains(g) and (best is None or h.area < best[0]): best = (h.area, k)
        if best: move(i, best[1], 'F8'); stats['в ' + inst[best[1]]['key']] += 1
    print('F8', dict(stats), round(time.time() - t0, 1), 's')

# ====================================================================================== F7 faces: pieces and shared lines
def wallline_inst():
    for k, q in enumerate(inst):
        if q['key'] == 'wallline' and q['name'].startswith('Линии стен'): return k
    return new_inst('wallline', 'Линии стен (контур/отделка по исходнику)', 'A-222---E-', 'F7')
if 7 in STEPS:
    stats = collections.Counter()
    OKC = LAYER1 | OPENING_KEYS | {'roomsep'}
    MOVE_BACK = {'loose', 'misc', 'FREE', 'wcacc', 'mark', 'sign'}
    FACL = unary_union([LineString(f) for f in [list(x) for x in getattr(cfg, 'FACADES', [])] if len(f) >= 2]) if getattr(cfg, 'FACADES', None) else None
    _mem7 = mem_index()
    _COLH = [h for h in (hull_ids(_mem7.get(k, [])) for k, q in enumerate(inst) if q['key'] == 'column') if h is not None]
    _COLT = STRtree([h.buffer(0.3) for h in _COLH]) if _COLH else None
    def along_column(g):
        if _COLT is None: return False
        return any(_COLH[j].buffer(0.3).intersection(g).length >= 0.8 * g.length for j in _COLT.query(g))
    CORNER_FB = {'loose', 'misc', 'FREE', 'mark', 'sign'}
    def bridges(b, e):
        """a corner piece of an object continues the face only when its far end holds on structure (a wall stub between a
        column and a wall); the side of an accessory hung on the wall ends at the accessory - check S16* counts the same"""
        q0, q1 = LN[b][1], LN[b][2]; far = q1 if math.dist(q0, e) <= math.dist(q1, e) else q0
        if any(okeys(LN[x][0]) & STRUCT_END for x in near(far, 0.15, b) if G[x].length >= 0.3): return True
        return not WU.is_empty and Point(far).distance(WU) <= 0.15
    def dom_pen(k):
        c = collections.Counter(pen(i) for i in _mem7.get(k, []) if P[i][0] == 'l')
        return c.most_common(1)[0][0] if c else None
    for rnd_ in range(8):
        before_ = sum(sum(c.values()) for c in LOG.values())
        # a partition piece between two furniture lines of its pen (the edge of a bench across the gap between desks)
        for n, (i, p0, p1) in enumerate(LN):
            if okey(i) not in PART or G[n].length > 6.0: continue
            u = unit(p0, p1); ends = []
            for e, sg in ((p0, -1), (p1, 1)):
                fo = None
                for b in near(e, 0.15, n):
                    j = LN[b][0]
                    if okey(j) not in FURN or pen(j) != pen(i): continue
                    v = unit(LN[b][1], LN[b][2])
                    if abs(u[0] * v[0] + u[1] * v[1]) >= 0.995: fo = own[j]; break
                ends.append(fo)
            if ends[0] is not None and ends[1] is not None:
                move(i, ends[0], 'F7'); stats['перегородка-мостик между мебелью → мебель'] += 1
        L1 = [n for n, (i, a, b) in enumerate(LN) if okeys(i) & LAYER1 and G[n].length >= 0.5]
        for a in L1:
            i, p0, p1 = LN[a]
            ka = okey(i)
            if ka == 'WALL': tgt = 'WALL'
            else:
                cand_ = [kk for kk in ([own[i]] if i in own else []) + sorted(shby.get(i, ())) if inst[kk]['key'] in LAYER1]
                tgt = cand_[0] if cand_ else None
            if tgt is None: continue
            ka = 'WALL' if tgt == 'WALL' else inst[tgt]['key']
            for e, o in ((p0, p1), (p1, p0)):
                u = unit(o, e)
                for b in near(e, 0.15, a):
                    j, q0, q1 = LN[b]
                    if okeys(j) & OKC or pen(j) != pen(i): continue
                    v = unit(q0, q1); col = abs(u[0] * v[0] + u[1] * v[1]) >= 0.995
                    beyond = max((q0[0] - e[0]) * u[0] + (q0[1] - e[1]) * u[1], (q1[0] - e[0]) * u[0] + (q1[1] - e[1]) * u[1]) > 0.2
                    if col and not beyond: continue
                    if not col:
                        # a corner of the same pen: only where the layer has nothing else at this end (pieces from 0.3 pt, as
                        #   check S16* counts them), not a duplicate of the face drawn over it, not a line along a column
                        if any(okeys(LN[x][0]) & STRUCT_END for x in near(e, 0.15, a) if x != b and G[x].length >= 0.3): continue
                        if G[b].intersection(G[a].buffer(0.25)).length >= 0.8 * G[b].length: continue
                        if along_column(G[b]): continue
                        if okey(j) not in CORNER_FB and not bridges(b, e): continue
                    kb = okey(j)
                    if kb in FURN | SEATS | {'screen', 'fscreen'} and ka in GLAZ:
                        # the "face" is a furniture edge a glazing band or box took: the furniture's, shared with the glazing
                        #   line only when that line is the glazing itself (on the facade line / inside its box)
                        if ka == 'facade' and (FACL is None or G[a].distance(FACL) > 2.0) and pen(i) == dom_pen(own[j]):
                            move(i, own[j], 'F7'); stats['край мебели из полосы витража'] += 1
                        else: share(i, own[j], 'F7'); stats['общая линия витража и мебели'] += 1
                        continue
                    if tgt == 'WALL':
                        if WUb is not None and WUb.contains(G[b]): to_wall(j, 'F7'); stats['кусок грани стены → стена'] += 1; continue
                        tgt_ = wallline_inst()
                    else: tgt_ = tgt
                    if kb in MOVE_BACK or (kb in PART and False):
                        k0_ = own.get(j); move(j, tgt_, 'F7'); stats[f'кусок грани у «{kb}» → грани'] += 1
                        # its twins go with it: lines of the same owner along it in another pen (the bar of a wall stub
                        #   drawn as two thick lines and a thin one)
                        for n2 in T.query(G[b].buffer(0.3)):
                            j2 = LN[n2][0]
                            if j2 == j or own.get(j2) != k0_ or k0_ is None: continue
                            v2 = unit(LN[n2][1], LN[n2][2]); vb = unit(LN[b][1], LN[b][2])
                            if abs(v2[0] * vb[0] + v2[1] * vb[1]) < 0.995 or G[n2].intersection(G[b].buffer(0.3)).length < 0.8 * G[n2].length: continue
                            move(j2, tgt_, 'F7'); stats['двойник куска грани'] += 1
                    else: stats['общая линия: ' + kb] += share(j, tgt_, 'F7')
                    spot('F7', e, f'грань {ka}: «{kb}»')
        if sum(sum(c.values()) for c in LOG.values()) == before_: break
    print('F7', dict(stats), 'rounds', rnd_ + 1, round(time.time() - t0, 1), 's')
    # F9 again: a face piece F7 gave back to a partition leaves its duplicate in the accessory on that face
    st9 = collections.Counter(); wcacc_faces('F9b', st9); print('F9b', dict(st9))

# ====================================================================================== F12 operator boxes
# an operator box (cfg.MANUAL) took a boundary line of a neighbouring object (the cap of a plasterboard partition at a
#   glazing box, the finish line of a wall behind a fire cabinet): the line is shared with that object (пп. 240, 257) -
#   the same faces check S29* looks at (furniture-size rectangles and narrow closed shapes up to 3000 mm)
if 12 in STEPS:
    stats = collections.Counter(); mem = mem_index()
    def insts_of(i): return ([own[i]] if i in own else []) + sorted(shby.get(i, ()))
    NOTFACE = {'WALL', 'chair', 'roomsep', 'axmark'}
    from detect8 import bbox_of as _bbox8
    for key_, name_, layer_, boxes in getattr(cfg, 'MANUAL', []):
        for bx in map(_bbox8, boxes):          # code 008: a polygon element (Т4-7) - by its bbox
            B = box(bx[0] - 0.6, bx[1] - 0.6, bx[2] + 0.6, bx[3] + 0.6); Bp = prep(B)
            ks = {k for k, q in enumerate(inst) if q['key'] == key_ and q['name'] == name_ and mem.get(k)
                  and sum(1 for i in mem[k] if all(Bp.contains(Point(v)) for v in pts(P[i]))) >= 0.8 * len(mem[k])}
            if not ks: continue
            Z = B.buffer(50.0)
            ids = [n for n in T.query(Z) if G[n].length >= 0.3 and not (okeys(LN[n][0]) & NOTFACE)]
            for f in polygonize(unary_union([G[n] for n in ids])):
                if not f.exterior.intersects(B.buffer(0.3)) or f.intersection(B).area >= 0.5 * f.area: continue
                r = f.minimum_rotated_rectangle
                if r.area <= 0: continue
                cc = list(r.exterior.coords); e = sorted([math.dist(cc[0], cc[1]), math.dist(cc[1], cc[2])]); rq = f.area / r.area
                rect_ = rq >= 0.95 and 250 * PT <= e[0] <= 2500 * PT and 380 * PT <= e[1] <= 3000 * PT
                small_ = rq >= 0.9 and e[0] >= 0.8 and 4.0 <= e[1] <= 3000 * PT and e[0] < 250 * PT
                if not (rect_ or small_): continue
                zone = f.exterior.buffer(0.3); mine = []; other = collections.Counter()
                for n in T.query(zone):
                    if G[n].length < 0.3 or okeys(LN[n][0]) & NOTFACE: continue
                    inter = G[n].intersection(zone).length
                    if inter <= 0: continue
                    ins = set(insts_of(LN[n][0]))
                    if ins & ks and not (ins - ks): mine.append(n)
                    for k2 in ins - ks:
                        if inst[k2]['key'] not in FALLBACK | NOTFACE: other[k2] += inter
                if sum(G[n].intersection(zone).length for n in mine) < 2.0 or not other: continue
                k2 = other.most_common(1)[0][0]
                run_ = set()
                for n in mine:
                    for m in run_of(n):
                        ins = set(insts_of(LN[m][0]))
                        if ins & ks and not (ins - ks): run_.add(m)
                for n in sorted(run_ | set(mine)): stats[f'{key_} + {inst[k2]["key"]}'] += share(LN[n][0], k2, 'F12')
                spot('F12', f.representative_point().coords[0], f'рамка «{name_[:30]}»: край соседа «{inst[k2]["key"]}» — общая линия')
    print('F12', dict(stats), round(time.time() - t0, 1), 's')

# ====================================================================================== F13 furniture pieces in wall bodies
# what a cabinet, a wardrobe or a desk holds inside a wall body (an operator box reaching into the wall, an end cell or a
#   stroke rule that took a hatch piece) is the wall's: furniture does not go into a wall (owner: "Там никаких стен не
#   должно быть" - the converse; check S23* "стена на мебели")
if 13 in STEPS or 12 in STEPS:
    stats = collections.Counter(); mem = mem_index()
    WIN_ = prep(WU.buffer(-0.15)) if not WU.is_empty else None
    if WIN_ is not None:
        for k, q in enumerate(inst):
            if q['key'] not in FURN or q['key'] == 'monitor': continue
            for i in list(mem.get(k, [])):
                if all(WIN_.contains(Point(v)) for v in pts(P[i])): to_wall(i, 'F13'); stats[q['key']] += 1
    print('F13', dict(stats), round(time.time() - t0, 1), 's')

# ====================================================================================== tidy
# a WC accessory left as a sliver (a piece of a threshold, 15 x 0 mm) is not an accessory: it joins the object it touches
mem = mem_index()
for k, q in enumerate(inst):
    if q['key'] != 'wcacc' or not mem.get(k): continue
    xy = [v for i in mem[k] for v in pts(P[i])]
    if max(max(x for x, y in xy) - min(x for x, y in xy), max(y for x, y in xy) - min(y for x, y in xy)) * MM_PER_PT >= 20: continue
    for i in list(mem[k]):
        g = LineString(pts(P[i])) if len(pts(P[i])) > 1 else Point(pts(P[i])[0])
        nb = [n for n in T.query(g.buffer(0.3)) if own.get(LN[n][0]) not in (k, None)]
        if nb: move(i, own[LN[nb[0]][0]], 'tidy'); spot('tidy', pts(P[i])[0], f'обрывок аксессуара → {inst[own[LN[nb[0]][0]]]["key"]}')
# ====================================================================================== F14 glass doors
# (04.10.2026, строка 172) a door whose opening a glass line runs through - the source draws the glass partition
#   unbroken: "Это проём — разрыв"; "такую дверь саму показывать как стеклянную. Показать разрыв, что там есть проход,
#   а саму дверь в другом стиле". Ownership does not change: export.py cuts the glass line between the jambs and draws
#   the door in the glass style on A-32; S22* checks the gap in the DXF (own7.door_opening, own7.glass_through)
GLASS_DOORS = []
if 4 in STEPS or 11 in STEPS:
    for k, q in enumerate(inst):
        if q['key'] != 'door' or 'door' not in q: continue
        a, b = door_opening(inst, k)
        near_ = sorted({LN[n][0] for n in T.query(LineString([a, b]).buffer(1.0))})
        gl = glass_through(P, [(i, okeys(i)) for i in near_], a, b)
        if not gl: continue
        # what is cut: the glass strokes running through and the closed glass panel in the opening, whoever took them
        #   (F4 gave the panel to the threshold) - not the door's own lines, not wall prims
        door_ks = {k} | {k2 for k2, q2 in enumerate(inst) if q2['key'] == 'door' and q2.get('door') and k2 != k
                                and math.dist(q2['door']['closed'], q['door']['closed']) <= 1.6}
        cut = set(gl) | set(opening_lines(P, [(i, okeys(i)) for i in near_ if own.get(i) not in door_ks and i not in WP], a, b))
        q['glass_gap'] = dict(a=[round(a[0], 3), round(a[1], 3)], b=[round(b[0], 3), round(b[1], 3)], prims=sorted(cut), half=0.8)
        q['glass'] = True; dirty.add(k)
        m_ = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
        GLASS_DOORS.append(dict(name=q['name'], at=[round(m_[0], 1), round(m_[1], 1)], width_mm=round(math.dist(a, b) * MM_PER_PT), glass_lines=len(gl), cut_lines=len(cut)))
        spot('F14', m_, f'дверь #{k}: стеклянная — линия стекла рвётся по ширине двери (строка 172)')
    print('F14 glass doors', len(GLASS_DOORS), [(g['at'], g['width_mm']) for g in GLASS_DOORS], round(time.time() - t0, 1), 's')

# ====================================================================================== write
mem = mem_index()
for k, q in enumerate(inst):
    if k in dirty or k >= N0:
        q['prims'] = sorted(mem.get(k, []))
    if SH.get(k):
        q['shared'] = sorted(i for i in SH[k] if own.get(i) != k)
keep = [q for k, q in enumerate(inst) if q['prims'] or q.get('shared') or q.get('poly') or (k < N0 and was_empty[k])]
dropped = len(inst) - len(keep)
pickle.dump((keep, free), open('assign2.pkl', 'wb'))
pickle.dump(WP, open('wallprims.pkl', 'wb'))
pickle.dump(WD, open('walls.pkl', 'wb'))
rep = dict(rules={r: dict(c.most_common()) for r, c in LOG.items()}, spots=SPOTS, new=len(inst) - N0, dropped=dropped,
           openings=[dict(kind=o['kind'], name=o['name'], how=o['how'], area_m2=o.get('area_m2'), stairs=o['stairs']) for o in OPENINGS],
           no_opening=[{kk: vv for kk, vv in o.items() if kk != 'stair'} for o in (NO_OPENING if 10 in STEPS else [])],
           glass_doors=GLASS_DOORS)
json.dump(rep, open('fix7.json', 'w'), ensure_ascii=False, indent=1)
print('fix7: instances', N0, '->', len(keep), '(new', len(inst) - N0, ', emptied', dropped, ')', round(time.time() - t0, 1), 's')
for r, c in LOG.items(): print(' ', r, sum(c.values()), dict(c.most_common(6)))
