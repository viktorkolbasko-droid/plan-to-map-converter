# detect8.py - code 008: detectors that take what operator boxes (cfg.MANUAL) and the review loop took on floor 4 of
#   client A, test 4 (proposals/plan/2026-10-06-клиент А-4-тест-4-max-новый-контекст.md, Т4-1...Т4-7). A detector is a rule
#   by a sign of the source, not a box by place (plan/rules/70 §2, rules 24-25, 28): sizes are mm of the building, a
#   tolerance on the sheet is converted through the sheet's scale (MM_PER_PT); rules derived on one building are marked
#   <один пример: клиент А, 4 этаж>.
#   Switched on per floor by cfg.DETECT8 = True: a rule that changes another floor is a field until its places on all
#   floors are looked at (plan/rules/70 §2, rule 10) - as cfg.FIX7 of code 007. cfg.DETECT8_OFF = {'desks', ...} switches
#   single detectors off: 'desks' (Т4-1 outline desks, pedestals and strips of a bench; Т4-6 closed thin rectangles with
#   a seat), 'band' (Т4-2), 'columns' (Т4-3), 'strips' (Т4-5), 'pen' (Т4-6: furniture-pen lines are not light partitions,
#   S12* lists closed rectangles with free room on two sides).
import math, collections
from common import cfg, MM_PER_PT

ON = bool(getattr(cfg, 'DETECT8', False))
OFF = set(getattr(cfg, 'DETECT8_OFF', ()))
def on(name): return ON and name not in OFF
def pt(mm): return mm / MM_PER_PT


# ---------------------------------------------------------------- MANUAL entries: a box or a polygon (Т4-7) - manual8.py
from manual8 import is_poly, poly_pts, bbox_of, poly_geom, element_takes


# ---------------------------------------------------------------- Т4-1, Т4-6: desks drawn by lines
def _col_eq(c, ref, tol=0.02): return c is not None and ref is not None and max(abs(c[j] - ref[j]) for j in range(3)) <= tol
def _axis(a, b, tol=0.02): return abs(a[0] - b[0]) < tol or abs(a[1] - b[1]) < tol
def _ext(a, b, d):
    L = math.dist(a, b)
    if L < 1e-9: return a, b
    u = ((b[0] - a[0]) / L, (b[1] - a[1]) / L)
    return (a[0] - u[0] * d, a[1] - u[1] * d), (b[0] + u[0] * d, b[1] + u[1] * d)
def _rect(f):
    r = f.minimum_rotated_rectangle; xy = list(r.exterior.coords)
    e = sorted([math.dist(xy[0], xy[1]), math.dist(xy[1], xy[2])])
    return r, e
def _gkey(a, b):
    a, b = sorted([(round(a[0], 2), round(a[1], 2)), (round(b[0], 2), round(b[1], 2))]); return (a, b)

def cells_of(P, ids, gap_pt):
    """closed cells of the lines ids: every line is extended at both ends by gap_pt, so a side that stops short of the
    next one (floor 4: 0.7 pt at the glazed partition of axis 8, a piece of 0.6 pt under 3 pt left out) still closes the
    cell; dangles of the extension do not make cells (polygonize drops them)"""
    from shapely.geometry import LineString
    from shapely.ops import unary_union, polygonize
    ls = [LineString(_ext(P[i][4][0], P[i][4][1], gap_pt)) for i in ids]
    if not ls: return []
    return list(polygonize(unary_union(ls)))

def boundary_members(P, f, ids, tol=0.35, share=0.8):
    """lines of ids that lie on the boundary of the cell f (>= share of their length within tol of it)"""
    from shapely.geometry import LineString
    z = f.exterior.buffer(tol); zb = z.bounds; out = []
    for i in ids:
        a, b = P[i][4]
        if max(a[0], b[0]) < zb[0] or min(a[0], b[0]) > zb[2] or max(a[1], b[1]) < zb[1] or min(a[1], b[1]) > zb[3]: continue
        g = LineString([a, b]); L = g.length
        if L < 1e-6:
            if z.contains(g.centroid): out.append(i)
            continue
        if g.intersection(z).length >= share * L: out.append(i)
    return out

def distribute(P, claims, free):
    """claims: [(cell index, [line ids])] in priority order. A line goes to its first claimer; of exact duplicates
    (one side drawn by both neighbours, floor 4: back-to-back desks, a desk and a pedestal) each claimer gets one copy -
    the shared side is an edge of both (Т4-1). Returns {cell index: set(ids)}"""
    by_key = collections.defaultdict(list)
    for k, ids in claims:
        for i in ids:
            if i in free: by_key[_gkey(*P[i][4])].append((k, i))
    got = collections.defaultdict(set); used = set()
    for key, lst in by_key.items():
        copies = sorted({i for _, i in lst}); cells = []
        for k, _ in lst:
            if k not in cells: cells.append(k)
        for n, k in enumerate(cells):
            if n < len(copies): got[k].add(copies[n]); used.add(copies[n])
        for i in copies:
            if i not in used: got[cells[0]].add(i); used.add(i)
    return got

def _over(f, known):
    """the cell lies over a desk found before (step 5, a filled desk): >= 0.5 of its area"""
    from shapely.geometry import box as _bx
    return any(_bx(*b).intersection(f).area >= 0.5 * f.area for b in known)
def outline_desks(P, free, col, seats_near=None, log=print, taken=(), known=()):
    """Т4-1: desks drawn as outlines of one colour (cfg.DESK_OUTLINE_COLOR, floor 4: grey 0.67) without a worktop fill.
    A cell of the free axis-parallel lines of that colour, closed within 60 mm of the building (a gap on the sheet is
    converted by the scale), 1000-2000 x 500-1000 mm - a desk; a narrow cell (150-450 mm wide, >= 900 mm long) along a
    desk - the bench's pedestal ('benchend', >= 300 mm) or the strip in the middle of the block ('screen', < 300 mm).
    Runs before the facade band (step 8), so the band does not take the outer side of a desk at the facade.
    Returns [(key, name, cell polygon, ids)]. <один пример: клиент А, 4 этаж>"""
    gap = pt(60)
    # any angle: a block of desks turned 45 deg at a curved facade is drawn by the same outline (floor 4, NE arc: four
    #   desks 1200 x 700 at 50 deg - an operator box along the axes took armchairs and a convector with them, Т4-7)
    cand = [i for i in free if P[i][0] == 'l' and _col_eq(P[i][2], col) and (_axis(*P[i][4]) or math.dist(*P[i][4]) >= pt(150))]
    # a side that an operator box of another object took still closes the cell (floor 4: the box of the glazed
    #   partition of axis 8 took the left sides of six desks): taken lines close cells, the desk owns only free ones,
    #   and a cell is a desk only when >= 0.5 of its outline is free lines of the outline colour
    clo = [i for i in taken if P[i][0] == 'l' and _col_eq(P[i][2], col) and (_axis(*P[i][4]) or math.dist(*P[i][4]) >= pt(150))]
    from shapely.geometry import LineString as _LS8
    from shapely.strtree import STRtree as _ST8
    _cg = [_LS8(P[i][4]) for i in cand]; _ct = _ST8(_cg) if _cg else None
    def free_share(f):
        if _ct is None: return 0.0
        z = f.exterior.buffer(0.35)
        return sum(_cg[j].intersection(z).length for j in _ct.query(z)) / max(f.exterior.length, 1e-9)
    desks, strips = [], []
    for f in cells_of(P, cand + clo, gap):
        if f.area <= 0: continue
        r, e = _rect(f)
        if r.area <= 0 or f.area / r.area < 0.98: continue
        if clo and free_share(f) < 0.5: continue
        if known and _over(f, known): continue
        a_mm, b_mm = e[0] * MM_PER_PT, e[1] * MM_PER_PT
        if 1000 <= b_mm <= 2000 and 500 <= a_mm <= 1000: desks.append(f)
        elif 150 <= a_mm <= 450 and b_mm >= 900: strips.append((f, a_mm))
    # a desk open on one side (Т4-1): a side of the outline is broken where something else stands at it (floor 4: the
    #   thick outline of a pilaster at the glazing, 3.7 pt). Collinear pieces of one side with a gap up to 400 mm are
    #   bridged by a virtual line; a cell that needs a bridge is a desk only with a seat within 250 mm, and the bridge
    #   owns nothing
    if seats_near is not None and cand:
        from shapely.geometry import LineString
        from shapely.ops import unary_union, polygonize
        rows = collections.defaultdict(list)
        for i in cand:
            a, b = P[i][4]
            if not _axis(a, b): continue                 # bridges join pieces of one axis-parallel side only
            if abs(a[1] - b[1]) < 0.02: rows[('h', round((a[1] + b[1]) / 2 / 0.05))].append((min(a[0], b[0]), max(a[0], b[0]), (a[1] + b[1]) / 2))
            else: rows[('v', round((a[0] + b[0]) / 2 / 0.05))].append((min(a[1], b[1]), max(a[1], b[1]), (a[0] + b[0]) / 2))
        bridges = []
        for (o, _), segs in rows.items():
            segs.sort(); end = segs[0][1]
            for lo, hi, c in segs[1:]:
                if gap < lo - end <= pt(400):
                    bridges.append(LineString([(end, c), (lo, c)] if o == 'h' else [(c, end), (c, lo)]))
                end = max(end, hi)
        if bridges:
            ls = [LineString(_ext(P[i][4][0], P[i][4][1], gap)) for i in cand] + bridges
            bu = unary_union(bridges)
            for f in polygonize(unary_union(ls)):
                if f.area <= 0 or any(d.intersection(f).area > 0.2 * f.area for d in desks): continue
                if f.exterior.intersection(bu.buffer(0.05)).length < 0.5: continue
                r, e = _rect(f)
                if r.area <= 0 or f.area / r.area < 0.98: continue
                a_mm, b_mm = e[0] * MM_PER_PT, e[1] * MM_PER_PT
                if 1000 <= b_mm <= 2000 and 500 <= a_mm <= 1000 and seats_near(f, pt(250)): desks.append(f)
    out = []
    DN, DK = 'Стол рабочий (контур без заливки)', 'desk_o'
    for f in desks: out.append([DK, DN, f])
    for f, a_mm in strips:
        # along desks: the strip's long sides lie on desks' sides over >= 0.5 of the strip's length (a strip along the
        #   middle of a block of four desks touches each desk over half its length)
        adj = sum(f.buffer(0.3).intersection(d.exterior).length for d in desks)
        if adj < 0.5 * max(_rect(f)[1]): continue
        if a_mm >= 300: out.append(['benchend', 'Приставной элемент бенча (тумба)', f])
        else: out.append(['screen', 'Экран настольный / кабель-канал бенча', f])
    claims = [(n, boundary_members(P, f, cand)) for n, (_, _, f) in enumerate(out)]
    got = distribute(P, claims, free)
    res = [(k, nm, f, got.get(n, set())) for n, (k, nm, f) in enumerate(out)]
    log('detect8 outline desks: cells', len(desks), 'strips', len(strips), '->', collections.Counter(k for k, _, _, ids in res if ids))
    return [r for r in res if r[3]]

def line_desks(P, PB, free, seats, log=print, taken=(), known=()):
    """Т4-1 (a desk with a seat), Т4-6 (furniture without a fill is not a partition): a closed rectangle of free thin
    straight lines (<= 0.3 pt pen, any colour) 1000-2000 x 500-1000 mm with a seat (chair, armchair) within 250 mm and
    nothing but its own outline inside - a desk drawn by lines (floor 4: white desk modules at the end of a bench, black
    0.24 outline over a white fill). Without a seat it stays for the gate (S12*).
    seats: [shapely geometry of seat instances]. Returns [(key, name, cell, ids)]. <один пример: клиент А, 4 этаж>"""
    from shapely.strtree import STRtree
    if not seats: return []
    gap = pt(60)
    thin = lambda i: P[i][0] == 'l' and (P[i][1] or 0) <= 0.3 and _axis(*P[i][4]) and math.dist(*P[i][4]) >= pt(150)
    cand = [i for i in free if thin(i)]
    clo = [i for i in taken if thin(i)]                 # sides other objects took close the cell (see outline_desks)
    from shapely.geometry import LineString as _LS8
    _cg = [_LS8(P[i][4]) for i in cand]; _ct = STRtree(_cg) if _cg else None
    def free_share(f):
        if _ct is None: return 0.0
        z = f.exterior.buffer(0.35)
        return sum(_cg[j].intersection(z).length for j in _ct.query(z)) / max(f.exterior.length, 1e-9)
    st = STRtree(seats); d250 = pt(250)
    out = []
    for f in cells_of(P, cand + clo, gap):
        if f.area <= 0: continue
        r, e = _rect(f)
        if r.area <= 0 or f.area / r.area < 0.98: continue
        if clo and free_share(f) < 0.5: continue
        if known and _over(f, known): continue          # the outline of a filled desk of a bench (floor 4: step 7 'screen')
        a_mm, b_mm = e[0] * MM_PER_PT, e[1] * MM_PER_PT
        if not (1000 <= b_mm <= 2000 and 500 <= a_mm <= 1000): continue
        near = [j for j in st.query(f.buffer(d250)) if seats[j].distance(f) <= d250]
        # a seat that stands inside the cell is not a seat at the desk: the cell is a room or a booth
        if not near or any(f.buffer(-0.3).contains(seats[j].centroid) for j in near): continue
        out.append(['desk_src', 'Стол (по исходнику)', f])
    claims = [(n, boundary_members(P, f, cand)) for n, (_, _, f) in enumerate(out)]
    got = distribute(P, claims, free)
    res = [(k, nm, f, got.get(n, set())) for n, (k, nm, f) in enumerate(out)]
    log('detect8 line desks with a seat:', sum(1 for r in res if r[3]))
    return [r for r in res if r[3]]


# ---------------------------------------------------------------- Т4-2, Т4-6: the furniture pen
def furn_pen(p, cols):
    """a line of the furniture pen: the outline colour of desks and chairs (cols), a thin pen (<= 0.3 pt) and no longer
    than furniture (<= 3 m). Floor 4: the inner glazing line along the south facade is drawn in the same grey 0.67 but runs
    for 12 m, a partition in the same grey has a 0.48 pen - neither is furniture"""
    if p[0] not in ('l', 'c') or p[2] is None or (p[1] or 0) > 0.3: return False
    if not any(max(abs(p[2][j] - c[j]) for j in range(3)) <= 0.02 for c in cols): return False
    ps = p[4]; L = sum(math.dist(a, b) for a, b in zip(ps[:-1], ps[1:])) if p[0] == 'l' else math.dist(ps[0], ps[-1])
    return L <= pt(3000)


# ---------------------------------------------------------------- Т4-2: the facade band by the length of a line
def band_share(g, band):
    """share of a line's length inside the band (a fill: share of its area)"""
    if g.geom_type in ('LineString', 'MultiLineString'):
        L = g.length
        return 1.0 if L < 1e-9 and band.contains(g.centroid) else (g.intersection(band).length / L if L > 1e-9 else 0.0)
    A = g.area
    return g.intersection(band).area / A if A > 1e-9 else 0.0


# ---------------------------------------------------------------- Т4-5: finish strips along a wall face
def thin_strip(g):
    """(long side, short side, centre line) of a thin fill, or None"""
    from shapely.geometry import LineString
    r = g.minimum_rotated_rectangle
    if r.area <= 0: return None
    xy = list(r.exterior.coords)[:4]
    e1, e2 = math.dist(xy[0], xy[1]), math.dist(xy[1], xy[2])
    if e1 >= e2: a = ((xy[0][0] + xy[3][0]) / 2, (xy[0][1] + xy[3][1]) / 2); b = ((xy[1][0] + xy[2][0]) / 2, (xy[1][1] + xy[2][1]) / 2); L, W = e1, e2
    else: a = ((xy[0][0] + xy[1][0]) / 2, (xy[0][1] + xy[1][1]) / 2); b = ((xy[3][0] + xy[2][0]) / 2, (xy[3][1] + xy[2][1]) / 2); L, W = e2, e1
    return L, W, LineString([a, b])


# ---------------------------------------------------------------- Т4-4: the front of WC cabins
def wc_fronts(P, PB, free, doors, zones, log=print):
    """Т4-4: a cabin door of a WC is drawn with its leaf closed between two posts and its swing arc. For a door (step 3)
    whose hinge lies in a sanitary zone and whose radius is 600-1000 mm: the leaf in the opening - the free strip along
    the closed position (hinge -> closed end), its long edges parallel to it over >= 0.6 of the leaf, <= 80 mm thick -
    is the leaf ('door45'); the posts at both ends of the strip (free pieces within 120 mm of an end, off the strip) are
    partition ends ('lpartc') - the carriers of the jambs, not accessories. <один пример: клиент А, 4 этаж>
    doors: [(hinge, closed point)]; zones: [(x0, y0, x1, y1)]. Returns [(key, name, ids)]"""
    out = []
    for c, cl in doors:
        if not any(z[0] <= c[0] <= z[2] and z[1] <= c[1] <= z[3] for z in zones): continue
        L = math.dist(c, cl)
        if not (600 <= L * MM_PER_PT <= 1000): continue
        u = ((cl[0] - c[0]) / L, (cl[1] - c[1]) / L); n = (-u[1], u[0])
        def ax(p): return ((p[0] - c[0]) * u[0] + (p[1] - c[1]) * u[1], (p[0] - c[0]) * n[0] + (p[1] - c[1]) * n[1])
        x0, y0, x1, y1 = min(c[0], cl[0]) - 2, min(c[1], cl[1]) - 2, max(c[0], cl[0]) + 2, max(c[1], cl[1]) + 2
        cand = [i for i in free if PB[i][0] >= x0 and PB[i][2] <= x1 and PB[i][1] >= y0 and PB[i][3] <= y1]
        edges = []
        for i in cand:
            if P[i][0] != 'l': continue
            a, b = P[i][4]; la = math.dist(a, b)
            if la < 0.6 * L: continue
            if abs(((b[0] - a[0]) * n[0] + (b[1] - a[1]) * n[1]) / la) > 0.05: continue
            o = ax(a)[1]
            if abs(o) <= 1.2: edges.append((o, la))
        if len(edges) < 2: continue
        # the leaf: the group of long parallel lines <= 80 mm across that carries the most length (a face line of the
        #   partition next to the leaf is long and parallel too - floor 4, east WC: 0.36 pt off the leaf's edge)
        best = None
        for o0, _ in edges:
            grp = [(o, la) for o, la in edges if o0 <= o <= o0 + pt(80)]
            span = max(o for o, _ in grp) - o0
            if span < 0.1: continue
            key = (sum(la for _, la in grp), -span)
            if best is None or key > best[0]: best = (key, o0, o0 + span)
        if best is None: continue
        lo, hi = best[1], best[2]
        leaf = []
        for i in cand:
            q = [ax(v) for v in P[i][4]]
            if all(-0.3 <= s <= L + 0.3 and lo - 0.15 <= t <= hi + 0.15 for s, t in q): leaf.append(i)
        if not leaf: continue
        sl = set(leaf); posts = []
        for i in cand:
            if i in sl: continue
            q = [ax(v) for v in P[i][4]]
            for end in (0.0, L):
                if all(abs(s - end) <= pt(120) and lo - pt(120) <= t <= hi + pt(120) for s, t in q): posts.append(i); break
        out.append(('door45', 'Дверь кабины санузла: полотно в проёме (по исходнику)', leaf))
        if posts: out.append(('lpartc', 'Стойка кабины санузла — деталь перегородки, носитель косяка (по исходнику)', posts))
    log('detect8 WC cabin fronts: leaves', sum(1 for k, _, _ in out if k == 'door45'), 'posts', sum(1 for k, _, _ in out if k == 'lpartc'))
    return out
