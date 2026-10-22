"""Э6 v5: wall bodies by plan/rules/30 on the AutoCAD OCG sheet (route by source layers).
Adaptations to this sheet — each is a decision for the report (the canon is written for Revit sheets):
 1. Hatch candidates — straight segments 0.4–11.5 pt (§2) of the wall layers «Стены наружные», «Стены внутренние».
 2. The 45°/135° sheet test of §2 does not hold on the radial plan: the pattern turns with some walls and stays fixed on others.
    It is replaced by the geometric meaning of §2 п. 5: each end lies ON a line that PASSES the end on both sides
    (T-junction, >= 0.2 pt each way), the line not parallel to the stroke (>= 20°). A corner (the line starts or ends there)
    is not a hatch end: end caps of strips, short sides of glass panes, sides of rectangles.
 3. Pattern test (as SPECK_PATTERN_KEEP, §5): a stroke is hatch if it belongs to a family of >= 3 roughly parallel strokes
    (<= 15°, middles <= 8 pt apart) that end on the same two lines (same source path or collinear), or crosses / meets at
    an end another candidate at >= 30° (X or zigzag). Lone «rungs» between two lines are not a pattern.
 4. Chords of curves (smooth continuation < 10° at both ends) are not hatch (§2 п. 2); X-pairs at any angle (§2 п. 3).
 5. Marks: wall-layer segments < 0.4 pt with a free end (ticks of the plaster layers) are evidence, not line work (§2 п. 6).
 6. Line work (§3.1): wall-layer lines, outlines of thick lines and non-glass fills of the wall layers, glass outlines,
    non-furniture lines within 12 pt of hatch, and BOUND — any line touched by a hatch end.
 7. Faces (§3.2–§3.5, §3.9): connectors <= 0.7 pt to another line, wall face by hatch along its edges, round small face
    not a wall, channels < 0.6 pt (§3.6), cells <= 30 pt2 (five passes). Glass faces (blue/cyan fills) are never walls.
 8. Class (§4) per strip: faces joined across hatch strokes form a strip; class by the pattern of the strip —
    two directions (X, zigzag/V) -> gkl A-222, one direction -> blk A-223; strips without own hatch (finish layers,
    channels) take the class of the neighbour with the longest shared border.
 9. «Стены» black fills are united first: >= 100 pt2 and 2A/P >= 5 -> column A-28, other >= 1 pt -> cap A-221.
Writes walls.pkl and walls_debug.pkl."""
import pickle, numpy as np, math, collections, sys, time, json
import os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import sheet
import shapely
from shapely.geometry import LineString, Polygon, Point, MultiLineString, box
from shapely.ops import unary_union, polygonize
t0 = time.time()
def T(): return f'{time.time() - t0:.1f} s'
CAVITY = '--cavity' in sys.argv
D = pickle.load(open('prims.pkl', 'rb')); P = D['P']
WALL_L = sheet.L('wall'); CORE_L = sheet.L('core')       # layers by role: cfg.OCG_LAYERS (ocg/sheet.py)
FURN_L = sheet.L(*sheet.NONWALL_ROLES)
GLASS = sheet.GLASS
HMIN, HMAX = 0.4, 11.5
C = lambda deg: math.cos(math.radians(deg))
def segs_of(p):
    q = p['p']
    if p['kind'] == 'wline':
        g = LineString(q).buffer(p['w'] / 2, cap_style=2); c = list(g.exterior.coords)
        return [(c[i], c[i + 1]) for i in range(len(c) - 1)]
    if p['kind'] == 'fill':
        out = []
        for ring in [p['p']] + p.get('holes', []):
            out += [(ring[i], ring[i + 1]) for i in range(len(ring) - 1)]
        return out
    return [(q[i], q[i + 1]) for i in range(len(q) - 1)]
# ---------------- segments by category: W wall layers, G glass outlines, O other non-furniture, F furniture/core
A_ = []; B_ = []; CAT = []; PID = []
glass_polys = []; col_fills = []
for p in P:
    L = p['layer']; k = p['kind']
    if L in WALL_L and k in ('fill', 'wline') and p['col'] in GLASS:
        cat = 'G'
        g = Polygon(p['p'], p.get('holes', [])).buffer(0) if k == 'fill' else LineString(p['p']).buffer(p['w'] / 2, cap_style=2)
        if g.area > 0: glass_polys.append(g)
    elif L in WALL_L: cat = 'W'
    elif L in FURN_L: cat = 'F'
    else: cat = 'O'
    if L in CORE_L and k == 'fill' and max(p['col']) < 0.05:
        g = Polygon(p['p'], p.get('holes', [])).buffer(0)
        if g.area > 0: col_fills.append(g)
    for a, b in segs_of(p):
        if math.hypot(b[0] - a[0], b[1] - a[1]) > 1e-3:
            A_.append(a); B_.append(b); CAT.append(cat); PID.append(p['id'])
A_ = np.array(A_); B_ = np.array(B_); CAT = np.array(CAT); PID = np.array(PID); N = len(A_)
V = B_ - A_; LEN = np.hypot(V[:, 0], V[:, 1]); U = V / LEN[:, None]
SEG = [LineString([A_[i], B_[i]]) for i in range(N)]
tree = shapely.STRtree(SEG)
print('segments', dict(collections.Counter(CAT)), T())
isW = CAT == 'W'
def touching(pt, i, tol):
    return [j for j in tree.query(Point(pt).buffer(tol)) if j != i and SEG[j].distance(Point(pt)) <= tol]
# ---------------- marks
mark = np.zeros(N, bool)
for i in np.where(isW & (LEN < HMIN))[0]:
    if not touching(A_[i], i, 0.03) or not touching(B_[i], i, 0.03): mark[i] = True
print('marks (free short ticks)', int(mark.sum()), T())
# ---------------- hatch: T-junction ends
def through(e, i):
    """end e of stroke i lies on a line that passes on both sides of it (T-junction, >= 0.2 pt each way), the line not
    parallel to the stroke (>= 20 deg); a corner (the line starts or ends there) is not a pass-through. The line may be a
    chain of short chords (curves are plotted as 0.24 pt chords): segments within 0.55 pt, <= 12 deg, on the same line.
    End tolerance 0.25 pt (canon 0.15): on the curved walls the pattern stops 0.15-0.24 pt short of the drawn rings."""
    js = [j for j in touching(e, i, 0.25) if not mark[j] and abs(U[i] @ U[j]) < C(8)]
    if not js: return None
    near = [j for j in tree.query(Point(e).buffer(0.55)) if j != i and not mark[j]]
    used = set()
    for j0 in js:
        if j0 in used: continue
        u = U[j0]; n = np.array([-u[1], u[0]]); c0 = n @ A_[j0]
        g = [j for j in near if abs(U[j] @ u) > C(12) and abs(n @ A_[j] - c0) <= 0.08 and abs(n @ B_[j] - c0) <= 0.08
             and SEG[j].distance(Point(e)) <= 0.55]
        used.update(g); te = u @ e
        t = [u @ A_[j] - te for j in g] + [u @ B_[j] - te for j in g]
        if max(t) >= 0.2 and min(t) <= -0.2: return [j for j in g if j in js] or [j0]
    return None
def line_key(g):
    j = g[0]; u = U[j] if (U[j][0] > 1e-9 or (abs(U[j][0]) <= 1e-9 and U[j][1] > 0)) else -U[j]
    n = np.array([-u[1], u[0]]); return (u, float(n @ A_[j]), set(PID[g].tolist()))
def same_line(k1, k2):
    if k1[2] & k2[2]: return True
    return abs(k1[0] @ k2[0]) > C(3) and abs(k1[1] - k2[1]) <= 0.05
cand = np.where(isW & ~mark & (LEN >= HMIN) & (LEN <= HMAX))[0]
T1 = {}; cstat = {}
for i in cand:
    g1 = through(A_[i], i)
    if g1 is None: cstat[i] = 'noT'; continue
    g2 = through(B_[i], i)
    if g2 is None: cstat[i] = 'noT'; continue
    sm = 0
    for e in (A_[i], B_[i]):
        for j in touching(e, i, 0.02):
            if abs(U[i] @ U[j]) > C(10) and (np.hypot(*(A_[j] - e)) < 0.02 or np.hypot(*(B_[j] - e)) < 0.02): sm += 1; break
    if sm == 2: cstat[i] = 'chord'; continue
    T1[i] = (g1, g2, line_key(g1), line_key(g2))
ti = np.array(sorted(T1)); print('T-junction candidates', len(ti), T())
# pattern test
ct = shapely.STRtree([SEG[i] for i in ti]); pos = {i: k for k, i in enumerate(ti)}
par = collections.defaultdict(set); two_dir = set()
for k, i in enumerate(ti):
    mi = (A_[i] + B_[i]) / 2; _, _, a1, a2 = T1[i]
    for kk in ct.query(Point(mi).buffer(8)):
        j = ti[kk]
        if j == i: continue
        c = abs(U[i] @ U[j])
        if c > C(15):
            if np.hypot(*((A_[j] + B_[j]) / 2 - mi)) > 8: continue
            _, _, b1, b2 = T1[j]
            if (same_line(a1, b1) and same_line(a2, b2)) or (same_line(a1, b2) and same_line(a2, b1)): par[i].add(j)
        elif c < C(30):                  # X: the strokes cross; V: they meet end to end and are of similar length (<= 4x)
            if SEG[i].crosses(SEG[j]) or (max(LEN[i], LEN[j]) <= 4 * min(LEN[i], LEN[j])
                                          and min(np.hypot(*(e - f)) for e in (A_[i], B_[i]) for f in (A_[j], B_[j])) <= 0.05):
                two_dir.add(i); two_dir.add(j)
# families: connected components of the parallel graph
fam = {}; nf = 0
for i in ti:
    if i in fam: continue
    st = [i]; fam[i] = nf; comp = [i]
    while st:
        x = st.pop()
        for y in par[x]:
            if y not in fam: fam[y] = nf; st.append(y); comp.append(y)
    nf += 1
fsize0 = collections.Counter(fam.values())
# a family is a pattern only if it runs along its lines: extent of the middles along the end line >= 1.5 x mean length.
# Layer lines of a multi-line wall between two crossing walls are parallel and share their end lines too, but they
# are long and lie side by side (extent ~ layer thickness) — a ladder, not a pattern (column cladding at (690; 402)).
fmem = collections.defaultdict(list)
for i, f_ in fam.items(): fmem[f_].append(i)
fsize = collections.Counter()
for f_, mem in fmem.items():
    if len(mem) < 3: fsize[f_] = len(mem); continue
    w = T1[mem[0]][2][0]                 # direction of the line the strokes end on (along the wall)
    t = [w @ ((A_[i] + B_[i]) / 2) for i in mem]; ext = max(t) - min(t); lm = float(np.mean(LEN[mem]))
    fsize[f_] = len(mem) if ext >= 1.5 * lm else -len(mem)      # negative = ladder, not a pattern
hatch = np.zeros(N, bool); bound = set(); why_h = collections.Counter()
def oblique(i):                       # stroke meets both its lines at 20-70 deg: not a rung, no pattern test needed
    return all(C(70) <= abs(U[i] @ U[g[0]]) <= C(20) for g in T1[i][:2])
for i in ti:
    if fsize[fam[i]] <= -3: ok, w_ = False, 'rejected: ladder'
    elif oblique(i): ok, w_ = True, 'oblique'
    elif fsize[fam[i]] >= 3: ok, w_ = True, 'family>=3'
    elif i in two_dir and LEN[i] <= 6: ok, w_ = True, 'X/V'      # a long line crossed by hatch is a layer line
    else: ok, w_ = False, 'rejected: lone/pair rung'
    why_h[w_] += 1; cstat[i] = w_ + f' fam{fsize[fam[i]]}'
    if ok: hatch[i] = True; bound.update(T1[i][0]); bound.update(T1[i][1])
print('hatch by pattern', dict(why_h), T())
xp = 0
xc = np.where(isW & ~mark & (LEN >= 0.8) & (LEN <= 8))[0]; xset = set(xc.tolist())
for i in xc:
    mi = (A_[i] + B_[i]) / 2
    for j in tree.query(SEG[i]):
        if j <= i or j not in xset: continue
        if np.hypot(*((A_[j] + B_[j]) / 2 - mi)) <= 0.3 and abs(U[i] @ U[j]) < C(20) and SEG[i].crosses(SEG[j]):
            for k in (i, j):
                two_dir.add(k)
                if not hatch[k]: hatch[k] = True; xp += 1
print('X-pairs added', xp, 'hatch total', int(hatch.sum()), T())
HI = np.where(hatch)[0]
H = [SEG[i] for i in HI]; Ht = shapely.STRtree(H)
two = np.array([i in two_dir for i in HI])
print('two-direction strokes', int(two.sum()), 'one-direction', int((~two).sum()), T())
# ---------------- line work, noding, connectors, faces
hz = shapely.prepared.prep(unary_union([h.buffer(12) for h in H]))
# owner 06.10.2026: an axis crossing the void of a column casing split it, and a piece of the void became wall (desks
# 119–126). Excluding the marking layers from the line work was tried: it also moved 3 strips at the core edge (+0,19 m²,
# −0,02 m²) — kept as a proposal; the gap rule below (fat face, little hatch along it) fixes the place alone.
work_idx = [i for i in range(N) if (CAT[i] in ('W', 'G') and not mark[i]) or (CAT[i] == 'O' and hz.intersects(SEG[i]))
            or (CAT[i] == 'F' and i in bound)]
print('line work', len(work_idx), 'of which BOUND furniture/core', sum(1 for i in work_idx if CAT[i] == 'F'), T())
net = unary_union([SEG[i] for i in work_idx])
lines = list(getattr(net, 'geoms', [net]))
endpts = collections.defaultdict(list)
for li, l in enumerate(lines):
    c = l.coords
    for q in (c[0], c[-1]): endpts[(round(q[0], 4), round(q[1], 4))].append((li, q))
dangl = [(v[0][0], Point(v[0][1])) for v in endpts.values() if len(v) == 1]
lt = shapely.STRtree(lines); conn = []
for li, pt in dangl:
    best = None
    for j in lt.query(pt.buffer(0.7)):
        if j == li: continue
        dd = lines[j].distance(pt)
        if dd <= 0.7 and (best is None or dd < best[0]): best = (dd, j)
    if best and best[0] > 1e-7:
        conn.append(LineString([pt, shapely.ops.nearest_points(pt, lines[best[1]])[1]]))
# owner 06.10.2026 (a wall is a closed polygon): the ends of a partition drawn by two parallel lines of the wall layers are
# closed — two free ends <= 2.6 pt apart on parallel lines (<= 3°), the cap across them (>= 70° to the lines)
caps = []
# a free end: a node of the line work where every line leaves to one side (all directions within 20°) — a dangling end, or
# the start of a doubled line; only nodes on the wall layers
def leave(li, q):
    c = np.array(lines[li].coords); a_ = c[0] if math.dist(c[0], q) < 1e-6 else c[-1]; b_ = c[1] if math.dist(c[0], q) < 1e-6 else c[-2]
    v = b_ - a_; L = np.linalg.norm(v); return v / L if L > 0 else None
free = []
for key, v in endpts.items():
    q = v[0][1]; ds = [leave(li, q) for li, _ in v]; ds = [d for d in ds if d is not None]
    if not ds: continue
    m = np.mean(ds, 0); m = m / (np.linalg.norm(m) + 1e-12)
    if all(d @ m >= math.cos(math.radians(20)) for d in ds):
        pt = Point(q)
        if any(isW[i] for i in tree.query(pt.buffer(0.01)) if SEG[i].distance(pt) <= 0.01): free.append((pt, m))
fT = shapely.STRtree([pt for pt, _ in free]) if free else None
for a_, (pt, u1) in enumerate(free):
    for b_ in fT.query(pt.buffer(2.6)):
        if b_ <= a_: continue
        qt, u2 = free[b_]; d = pt.distance(qt)
        if d < 0.15 or d > 2.6 or u1 @ u2 < math.cos(math.radians(3)): continue      # both lines leave the end to one side
        w = (np.array(qt.coords[0]) - np.array(pt.coords[0])) / d
        if abs(w @ u1) > math.cos(math.radians(70)): continue
        caps.append(LineString([pt, qt]))
print('caps closing the free ends of two-line partitions', len(caps), T())
net = unary_union(lines + conn + caps)
faces = [f for f in polygonize(net) if f.area > 1e-6]
print('dangling', len(dangl), 'connectors', len(conn), 'faces', len(faces), T())
GP = unary_union(glass_polys) if glass_polys else Polygon(); gpp = shapely.prepared.prep(GP)
# interiors of objects that sit in or at walls (fire cabinets in niches, doors, sanitary, equipment, heating, frames, lifts)
# are never wall faces: the cells and channels rules filled the ПК niches (decision, as the door strips of §2)
OBJ_L = sheet.L(*sheet.OBJ_ROLES)
HULL_L = sheet.L(*sheet.HULL_ROLES)   # compact objects: footprint = hull
objpolys = []
for L in OBJ_L:
    ls = [SEG[i] for i in range(N) if CAT[i] == 'O' and P[PID[i]]['layer'] == L and hz.intersects(SEG[i])]
    if not ls: continue
    for g in polygonize(unary_union(ls)):
        if g.area >= 0.3: objpolys.append(g.buffer(-0.03))
    if L in HULL_L:                  # outlines of cabinets are often open (door gap, doubled polyline): hull of each cluster
        gs = [LineString(p['p']) for p in P if p['layer'] == L and len(p['p']) >= 2 and hz.intersects(LineString(p['p']))]
        cl = unary_union([g.buffer(0.3) for g in gs])
        for c_ in getattr(cl, 'geoms', [cl]):
            h = unary_union([g for g in gs if g.intersects(c_)]).convex_hull
            if 0.3 <= h.area <= 400: objpolys.append(h.buffer(-0.05))
for p in P:
    if p['layer'] in OBJ_L and p['kind'] == 'fill':
        g = Polygon(p['p'], p.get('holes', [])).buffer(0)
        if g.area >= 0.3 and hz.intersects(g): objpolys.append(g.buffer(-0.03))
OBJ = unary_union([g for g in objpolys if not g.is_empty]) if objpolys else Polygon(); opp = shapely.prepared.prep(OBJ)
print('object interiors near walls', len(objpolys), round(OBJ.area, 1), 'pt2', T())
COLU = unary_union(col_fills) if col_fills else Polygon(); cpp = shapely.prepared.prep(COLU)
def hatch_len(f):
    tot = 0.0; tw = 0.0; ks = set()
    for ring in [f.exterior] + list(f.interiors):
        c = np.array(ring.coords)
        for a, b in zip(c[:-1], c[1:]):
            L = np.linalg.norm(b - a)
            if L < 1e-4: continue
            m = Point((a + b) / 2); u = (b - a) / L
            for k in Ht.query(m.buffer(0.02)):
                if H[k].distance(m) <= 0.02 and abs(U[HI[k]] @ u) > 0.999:
                    tot += L; tw += L * two[k]; ks.add(k); break
    return tot, tw, ks
fa = []
for f in faces:
    A = f.area; Pm = f.length; n = 2 * A / Pm; rp = f.representative_point()
    ban = 'glass' if gpp.contains(rp) else ('column' if cpp.contains(rp) else ('object' if opp.contains(rp) else ''))
    if ban: fa.append(dict(g=f, A=A, n=n, hl=0, hw=0, ks=set(), wall=False, why='', ban=ban)); continue
    hl, hw, ks = hatch_len(f)
    rnd = 4 * math.pi * A / Pm ** 2
    wall = ((A <= 120 and hl >= 0.3) or (n <= 8 and hl >= 1.5 and hl >= 0.04 * Pm)) and not (rnd > 0.88 and A < 40)
    # owner 06.10.2026: a fat face (A > 10 pt², 2A/P >= 1 pt) with hatch along < 5 % of its outline is a gap — the void of
    # a column casing, the wedge between two walls meeting at an angle — not a wall (3 faces, 118 pt², all gaps in the source)
    if wall and A > 10 and n >= 1.0 and hl < 0.05 * Pm: wall = False
    if wall and A > 120:
        r_in = shapely.maximum_inscribed_circle(f, 0.05).length
        if not (r_in <= 6 or hl >= 0.2 * Pm): wall = False
    fa.append(dict(g=f, A=A, n=n, hl=hl, hw=hw, ks=ks, wall=wall, why='hatch' if wall else '', ban=''))
print('faces with hatch along edges', sum(f['wall'] for f in fa), 'banned', dict(collections.Counter(f['ban'] for f in fa if f['ban'])), T())
ft = shapely.STRtree([f['g'] for f in fa])
nb = collections.defaultdict(list); hedge = set()
for i, f in enumerate(fa):
    for j in ft.query(f['g']):
        if j <= i: continue
        x = f['g'].boundary.intersection(fa[j]['g'].boundary)
        if x.is_empty: continue
        s = x.length
        if s <= 1e-4: continue
        nb[i].append((j, s)); nb[j].append((i, s))
        parts = [g for g in getattr(x, 'geoms', [x]) if g.geom_type == 'LineString' and g.length > 1e-4]
        if parts:                      # shared border lies on a hatch stroke -> same strip
            g = max(parts, key=lambda q: q.length); m = g.interpolate(0.5, normalized=True)
            c = np.array(g.coords); u = c[-1] - c[0]; u = u / (np.linalg.norm(u) + 1e-12)
            for k in Ht.query(m.buffer(0.02)):
                if H[k].distance(m) <= 0.02 and abs(U[HI[k]] @ u) > 0.999: hedge.add((i, j)); break
def wall_share(i): return sum(s for j, s in nb[i] if fa[j]['wall']) / fa[i]['g'].length
# test 5: a hatch-less face that touches a column fill is the gap between the column and its casing, not wall
TC = {i for i, f in enumerate(fa) if not f['wall'] and f['hl'] < 0.3 and not COLU.is_empty and f['g'].distance(COLU) <= 0.05}
print('faces at columns kept empty', len(TC))
for it in range(3):
    ch = [i for i, f in enumerate(fa) if not f['wall'] and not f['ban'] and f['n'] < 0.6 and wall_share(i) >= 0.3 and i not in TC]
    for i in ch: fa[i]['wall'] = True; fa[i]['why'] = 'channel'
    if not ch: break
for it in range(5):
    ce = [i for i, f in enumerate(fa) if not f['wall'] and not f['ban'] and f['A'] <= 30 and i not in TC
          and wall_share(i) >= (0.6 if f['n'] < 1 else 0.8) and not (4 * math.pi * f['A'] / f['g'].length ** 2 > 0.88 and f['A'] < 40)]
    for i in ce: fa[i]['wall'] = True; fa[i]['why'] = 'cell'
    if not ce: break
if CAVITY:                              # cavity between two layers of one wall: thin long face, >= 80 % walls around
    for it in range(2):
        cv = [i for i, f in enumerate(fa) if not f['wall'] and not f['ban'] and f['n'] <= 2.0 and wall_share(i) >= 0.8]
        for i in cv: fa[i]['wall'] = True; fa[i]['why'] = 'cavity'
        if not cv: break
# owner 06.10.2026: a wall is a closed polygon of one type, never a line. A partition drawn by two lines of the wall layers
# without hatch is a thin band face: 2A/P <= 2.2 pt (106 mm), long (half-perimeter >= 5 x its thickness), its outline >= 80 %
# on lines of the wall layers — a wall (class from its neighbours, §4). A thin face between a column and its casing
# (2A/P <= 0.6 pt) is no space: the casing meets the column face to face (owner 06.10.2026, joints); the fat void of a
# casing stays empty (the gap rule above, the twins check).
Wsegs = [SEG[i] for i in range(N) if CAT[i] == 'W' and not mark[i]]; WT = shapely.STRtree(Wsegs)
def w_share(g):
    b = g.boundary; near = [Wsegs[k] for k in WT.query(b.buffer(0.03))]
    if not near: return 0.0
    return b.intersection(unary_union([s_.buffer(0.03, cap_style=2) for s_ in near])).length / b.length
nb_ = nt_ = 0
for i, f in enumerate(fa):
    if f['wall'] or f['ban']: continue
    if i in TC:
        if f['n'] <= 0.6: f['wall'] = True; f['why'] = 'joint'; nt_ += 1
        continue
    if f['n'] <= 2.2 and f['g'].length / 2 >= 5 * f['n'] and w_share(f['g']) >= 0.8: f['wall'] = True; f['why'] = 'band'; nb_ += 1
print('owner 06.10: hatch-less partitions as polygons', nb_, '| thin gaps at columns closed', nt_, T())
# code 012 (СО-2; owner 09.10.2026, В1 место 3; rows 183, 189): a thin straight strip of the wall layers with an end on a desk
#   (on its outline or inside) and no end at a wall, a column, glass, the core or the facade is a barrier - a part of the desk
#   (A-82), not a wall body: its faces leave the walls, barrier_desk.py gives its primitives to the desk after Э7м. Every thin
#   strip with a free end gets a verdict (walls_stats.json 'free_strips'). Signs from the source: the ends of the strip; the
#   touch tolerance = the strip's thickness; thin <= 150 mm by cfg.MM_PER_PT; a desk - a fill of cfg.OCG_DESK_TOP on a layer of
#   the role 'furniture' <one example: client-b, tile A11>. The verdict - ocg/barriers.py.
import barriers as _bar
_wf = [i for i, f in enumerate(fa) if f['wall']]
_WU = unary_union([fa[i]['g'] for i in _wf]) if _wf else Polygon()
_comps = [g for g in getattr(_WU, 'geoms', [_WU]) if g.geom_type == 'Polygon' and g.area > 0]
_FL = sheet.L('furniture'); _DT = sheet.DESK_TOP
_desks = []
if _DT and _DT[0] is not None:
    for p in P:
        if p['layer'] in _FL and p['kind'] == 'fill' and p.get('col') and all(abs(a - b) <= 0.02 for a, b in zip(p['col'], _DT)):
            g = Polygon(p['p'], p.get('holes', [])).buffer(0)
            if g.area > 0: _desks.append(g)
_CARL = sheet.L('core', 'facade_frame', 'facade_glass')
_car = [LineString(p['p']) if p['kind'] != 'fill' else Polygon(p['p'], p.get('holes', [])).buffer(0).boundary
        for p in P if p['layer'] in _CARL and len(p['p']) >= 2]
_car += [g for g in getattr(COLU, 'geoms', [COLU]) if not g.is_empty] + [g for g in getattr(GP, 'geoms', [GP]) if not g.is_empty]
free_strips = []; barriers = []
for ci, rec in _bar.strip_verdicts(_comps, _desks, _car, sheet.K):
    free_strips.append(rec)
    if rec['verdict'] != _bar.BARRIER: continue
    g = _comps[ci]; n_ = 0
    for i in _wf:
        if fa[i]['wall'] and g.buffer(0.01).covers(fa[i]['g'].representative_point()): fa[i]['wall'] = False; fa[i]['why'] = 'barrier'; n_ += 1
    pids = sorted({int(PID[k]) for k in range(N) if CAT[k] == 'W' and g.buffer(0.1).covers(SEG[k])})
    barriers.append(dict(g=g, pids=pids, desk=_bar.desk_near(g, _desks, rec['tol_pt']), faces=n_, at_pt=rec['at_pt'], size_mm=rec['size_mm']))
print('code 012 (СО-2): thin wall-layer strips with a free end', len(free_strips), '| barriers given to desks', len(barriers),
      [b['at_pt'] for b in barriers], T())
why = collections.Counter(f['why'] for f in fa if f['wall']); print('wall faces by reason', dict(why), T())
# ---------------- strips and classes
wf = [i for i, f in enumerate(fa) if f['wall']]; wset = set(wf)
adj = collections.defaultdict(list)
for i, j in hedge:
    if i in wset and j in wset: adj[i].append(j); adj[j].append(i)
strip = {}; ns = 0
for i in wf:
    if i in strip: continue
    st = [i]; strip[i] = ns
    while st:
        x = st.pop()
        for y in adj[x]:
            if y not in strip: strip[y] = ns; st.append(y)
    ns += 1
# two-direction pattern inside the strip: a stroke of the strip within 2.5 pt whose direction differs >= 30 deg
kstrip = {}
for i in wf:
    for k in fa[i]['ks']: kstrip.setdefault(k, strip[i])
two_s = np.zeros(len(HI), bool)
for k, s_ in kstrip.items():
    for kk in Ht.query(H[k].buffer(2.5)):
        if kk != k and kstrip.get(kk) == s_ and abs(U[HI[k]] @ U[HI[kk]]) < C(30) and H[k].distance(H[kk]) <= 2.5:
            two_s[k] = True; break
two = two_s | two                        # X-pairs and X/V meetings stay two-direction
# votes for the class (decisions for this sheet):
#  - tick: a rung <= 0.8 pt (>= 70 deg to its line) is a dot of the plaster/GKL sheet pattern of a thin layer: no vote;
#  - degenerate X: a longer rung (>= 70 deg to its line) is the X pattern of the layer seen along one family only — the
#    other family runs along the wall (sheet-fixed 45/135 hatch on a wall along a diagonal): votes two-direction.
#    Only an oblique one-family pattern (20-70 deg) is a single hatch (blk).
def sheet_ang(v): return math.degrees(math.atan2(v[1], v[0])) % 180
vote = np.ones(len(HI)); ntick = ndeg = 0
for k, i in enumerate(HI):
    if i not in T1: continue
    w = T1[i][2][0]; rel = math.degrees(math.acos(min(1.0, abs(U[i] @ w))))
    if rel < 70: continue
    if LEN[i] <= 0.8: vote[k] = 0; ntick += 1; continue
    if not two[k]: two[k] = True; ndeg += 1     # rung: the X of the layer seen along one family (the other runs along the wall)
print('ticks (no vote)', ntick, 'degenerate X rungs', ndeg)
shl = collections.Counter(); shw = collections.Counter()
for k, s_ in kstrip.items(): shl[s_] += H[k].length * vote[k]; shw[s_] += H[k].length * vote[k] * two[k]
SG_ = {}
for i in wf: SG_.setdefault(strip[i], []).append(fa[i]['g'])
sgeo = {s_: unary_union(g) for s_, g in SG_.items()}
def thick(g):                            # 2A/P on the strip opened by 0.02 pt (no zero-width tails, §4)
    o = g.buffer(-0.02).buffer(0.02)
    return 2 * o.area / o.length if o.length > 0 else 0.0
sth = {s_: thick(g) for s_, g in sgeo.items()}
thin = {s_ for s_, t_ in sth.items() if t_ < 0.5}
scls = {s_: ('gkl' if shw[s_] >= 0.5 * shl[s_] else 'blk') for s_ in range(ns) if shl[s_] > 0 and s_ not in thin}
sb = collections.defaultdict(collections.Counter)    # shared border between strips
for i in wf:
    for j, sh in nb[i]:
        if j in wset and strip[j] != strip[i]: sb[strip[i]][strip[j]] += sh
# lining (§4, thin strip takes the class of the body it lines): a strip thinner than 0.6 of a neighbour that shares
# >= 30 % of its half-perimeter takes that neighbour's class; thicker strips first, so a chain of layers follows the main one
inh = 0
for s_ in sorted(scls, key=lambda q: -sth[q]):
    hp = sgeo[s_].length / 2; best = None
    for t_, sh in sb[s_].items():
        if t_ in scls and sth[t_] * 0.6 > sth[s_] and sh >= 0.3 * hp and (best is None or sh > best[0]): best = (sh, t_)
    if best and scls[best[1]] != scls[s_]: scls[s_] = scls[best[1]]; inh += 1
print('lining strips that took the class of the main layer', inh)
pickle.dump(dict(strip=strip, sgeo=sgeo, sth=sth, shl=dict(shl), shw=dict(shw), sb={k: dict(v) for k, v in sb.items()},
                 scls0=dict(scls)), open('walls_strips.pkl', 'wb'))
for it in range(50):                    # thin strips (finish layers) and strips without own hatch: class of the neighbour
    new = {}                            # with the longest shared border
    for s_ in range(ns):
        if s_ in scls: continue
        cnt = collections.Counter()
        for t_, sh in sb[s_].items():
            if t_ in scls: cnt[scls[t_]] += sh
        if cnt: new[s_] = cnt.most_common(1)[0][0]
    if not new: break
    scls.update(new)
for s_ in thin:                          # thin strip with own hatch and no classed neighbour keeps its own pattern
    if s_ not in scls and shl[s_] > 0: scls[s_] = 'gkl' if shw[s_] >= 0.5 * shl[s_] else 'blk'
unres = sum(1 for s in range(ns) if s not in scls)
for s in range(ns): scls.setdefault(s, 'gkl')
# body majority (§4 «класс по большинству»): a blk strip stays blk only if it is a real single-hatch wall —
# one-direction votes >= 20 pt and two-direction share < 0.25; otherwise it takes the majority class of its body
Wb = unary_union([fa[i]['g'] for i in wf]); bl = [g for g in getattr(Wb, 'geoms', [Wb])]
btr = shapely.STRtree(bl); sbody = {}
for s_, g in sgeo.items():
    rp = g.representative_point(); js = [j for j in btr.query(rp) if bl[j].covers(rp)]
    sbody[s_] = js[0] if js else -1
bv = collections.defaultdict(lambda: [0.0, 0.0])
for s_ in range(ns): bv[sbody.get(s_, -1)][0] += shl[s_]; bv[sbody.get(s_, -1)][1] += shw[s_]
sm_ = 0
for s_ in range(ns):
    if scls.get(s_) != 'blk': continue
    real = (shl[s_] - shw[s_]) >= 20 and shw[s_] < 0.25 * max(shl[s_], 1e-9)
    if real: continue
    tot, tw_ = bv[sbody.get(s_, -1)]
    if tot > 0 and tw_ >= 0.5 * tot: scls[s_] = 'gkl'; sm_ += 1
print('blk strips smoothed to the body majority', sm_)
print('strips', ns, 'thin', len(thin), 'by class', dict(collections.Counter(scls.values())), 'without hatch and neighbours', unres, T())
out = []
for cls in ('gkl', 'blk'):
    U_ = unary_union([fa[i]['g'] for i in wf if scls[strip[i]] == cls])
    out += [(cls, g) for g in getattr(U_, 'geoms', [U_]) if g.geom_type == 'Polygon' and g.area > 0.05]
cols = []
for g in getattr(COLU, 'geoms', [COLU]):
    if g.is_empty or g.area <= 0.05: continue
    n = 2 * g.area / g.length
    if g.area >= 100 and n >= 5: cols.append(('column', g))
    elif n >= 1.0: cols.append(('cap', g))
    else: cols.append(('capthin', g))
CC = unary_union([g for c, g in cols if c != 'capthin'])
out2 = []
for cls, g in out:
    d = g.difference(CC) if not CC.is_empty else g
    for x in getattr(d, 'geoms', [d]):
        if x.geom_type == 'Polygon' and x.area > 0.05: out2.append((cls, x))
allb = out2 + [(c, g) for c, g in cols if c != 'capthin']
k = sheet.K
cnt = collections.Counter(c for c, _ in allb); area = collections.defaultdict(float)
for c, g in allb: area[c] += g.area * k * k / 1e6
stats = dict(segments={str(a): b for a, b in collections.Counter(CAT).items()}, marks=int(mark.sum()), tcand=len(ti),
             hatch=int(hatch.sum()), hatch_why=dict(why_h), xpairs=xp, two=int(two.sum()), work=len(work_idx),
             dangling=len(dangl), connectors=len(conn), faces=len(fa), why=dict(why), strips=ns,
             bodies=dict(cnt), area_m2={c: round(a, 2) for c, a in area.items()},
             capthin=sum(1 for c, _ in cols if c == 'capthin'), cavity=CAVITY,
             free_strips=free_strips, barriers=[dict(at_pt=b_['at_pt'], size_mm=b_['size_mm'], pids=b_['pids']) for b_ in barriers])   # code 012, СО-2
pickle.dump(dict(bodies=allb, hatch=H, two=two.tolist(), marks=[SEG[i] for i in np.where(mark)[0]],
                 glass=glass_polys, stats=stats, barriers=barriers), open('walls.pkl', 'wb'))
pickle.dump(dict(faces=[(f['g'], f['wall'], f['why'], f['ban'], round(f['hl'], 3)) for f in fa],
                 work=[SEG[i] for i in work_idx], workcat=[str(CAT[i]) for i in work_idx], conn=conn,
                 hatch=H, two=two.tolist(), marks=[SEG[i] for i in np.where(mark)[0]],
                 rejected=[SEG[i] for i in ti if not hatch[i]], cand=[(SEG[i], cstat.get(i, '?')) for i in cand]),
            open('walls_debug.pkl', 'wb'))
json.dump(stats, open('walls_stats.json', 'w'), ensure_ascii=False, indent=1)
print('bodies', dict(cnt), stats['area_m2'], 'thin «Стены» fills not bodies', stats['capthin'], T())
