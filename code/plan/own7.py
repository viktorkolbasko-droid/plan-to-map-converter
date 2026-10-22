# Ownership of primitives for code 007 (draft, owner's review of floor 4 of client A, 03.10.2026).
# An instance owns q['prims'] (exclusive, as before) and also draws q.get('shared', []) - a boundary line it shares
# with the objects that line separates (proposals п. 240: "три объекта... полноценная стена, полноценная мебель,
# полноценная колонна"). WALL = a primitive inside a wall body (wallprims.pkl).
import pickle, math, collections, os, statistics
from common import load, pts, cfg
PART = {'lpart', 'lpartc', 'gklpart', 'glasspart', 'railing'}          # partitions without hatch (typed or not)
UNTYPED = {'lpart', 'lpartc'}                                           # partitions whose type is not known (п. 260)
GLAZ = {'glass', 'facade'}
LAYER1 = PART | GLAZ | {'wallline', 'WALL'}                             # sheet 1: walls, partitions, glazing (lines)
OPENING_KEYS = {'door', 'door45', 'doorhw', 'opening'}
STRUCT_END = LAYER1 | OPENING_KEYS | {'column', 'stair', 'lift'}        # what a wall / partition may end at
SEATS = {'chair', 'armchair', 'sofa', 'stool'}
TABLES = {'desk', 'desk_o', 'desk_src', 'mtable', 'rtable', 'benchend', 'reception', 'furn_src'}
FURN = TABLES | {'rack', 'wardrobe', 'sofa', 'armchair', 'fscreen', 'screen', 'monitor', 'cabinet'}
HOSTS = FURN | SEATS | {'door', 'door45', 'column', 'stair', 'lift', 'wc', 'sink', 'wcsink', 'fire', 'equip', 'plant', 'convector'}
FALLBACK = {'lpart', 'lpartc', 'misc', 'loose', 'FREE'}


class Own:
    """who owns / draws each primitive: prims + shared of every instance, WALL for wallprims"""

    def __init__(self, I, WP):
        self.I = I; self.WP = WP
        self.own = {}; self.sh = collections.defaultdict(list)
        for k, q in enumerate(I):
            for i in q['prims']: self.own[i] = k
            for i in q.get('shared', []): self.sh[i].append(k)

    def keys(self, i):
        s = set()
        if i in self.WP: s.add('WALL')
        if i in self.own: s.add(self.I[self.own[i]]['key'])
        for k in self.sh.get(i, ()): s.add(self.I[k]['key'])
        return s or {'FREE'}

    def key(self, i):
        """the primary owner: WALL, else the owning instance, else FREE"""
        if i in self.WP: return 'WALL'
        if i in self.own: return self.I[self.own[i]]['key']
        return 'FREE'

    def insts(self, i):
        out = []
        if i in self.own: out.append(self.own[i])
        out += self.sh.get(i, [])
        return out


def load_all(walls=True):
    from common import walls_file
    P = load(); cls = pickle.load(open('cls.pkl', 'rb')); I = pickle.load(open('inst_final.pkl', 'rb'))
    WP = pickle.load(open('wallprims.pkl', 'rb')) if os.path.exists('wallprims.pkl') else set()
    W = pickle.load(open(walls_file(), 'rb'))['Wpt'] if walls else {}
    return P, cls, I, WP, W


def hull_of(P, ids):
    from shapely.geometry import MultiPoint
    xy = [v for i in ids for v in pts(P[i])]
    if len(xy) < 3: return None
    return MultiPoint(xy).convex_hull


def unit(a, b):
    d = (b[0] - a[0], b[1] - a[1]); n = math.hypot(*d) or 1.0
    return (d[0] / n, d[1] / n)


# ---- the I-beam family template (owner 03.10.2026: "У всех колонн одна форма, одна толщина"): on floor 4 the grey fill
#      of the I-beam is 4.08 x 7.2 pt; an I-beam drawn without the fill is found by its outline in any pen
def is_col_fill(c, ref=None):
    ref = ref if ref is not None else getattr(cfg, 'COLUMN_FILL', 0.36)
    return c is not None and max(c) - min(c) <= 0.05 and abs(c[0] - ref) <= 0.04


def bb_of(P, ids):
    xs = [v[0] for i in ids for v in pts(P[i])]; ys = [v[1] for i in ids for v in pts(P[i])]
    return (min(xs), min(ys), max(xs), max(ys))


def ishape(P, ids, mb):
    """an I in the box: a web along the long side through the middle, flanges across both ends"""
    w_, h_ = mb[2] - mb[0], mb[3] - mb[1]; vert = h_ >= w_
    cx, cy = (mb[0] + mb[2]) / 2, (mb[1] + mb[3]) / 2; L_, S_ = max(w_, h_), min(w_, h_)
    web = fl0 = fl1 = False
    for i in ids:
        if P[i][0] != 'l': continue
        (ax, ay), (bx, by) = P[i][4][0], P[i][4][-1]
        if not all(mb[0] - 0.4 <= x <= mb[2] + 0.4 and mb[1] - 0.4 <= y <= mb[3] + 0.4 for x, y in ((ax, ay), (bx, by))): continue
        ln = math.dist((ax, ay), (bx, by))
        along = abs(bx - ax) <= 0.05 if vert else abs(by - ay) <= 0.05
        across = abs(by - ay) <= 0.05 if vert else abs(bx - ax) <= 0.05
        if along and ln >= 0.6 * L_ and abs(((ax + bx) / 2 - cx) if vert else ((ay + by) / 2 - cy)) <= 0.6: web = True
        if across and ln >= 0.7 * S_:
            pos = (ay + by) / 2 if vert else (ax + bx) / 2; lo, hi = (mb[1], mb[3]) if vert else (mb[0], mb[2])
            if abs(pos - lo) <= 0.6: fl0 = True
            if abs(pos - hi) <= 0.6: fl1 = True
    return web and fl0 and fl1


def best_box(P, ids, tw, th, test=None):
    """the placement of a tw x th box (both turns) that holds most of the lines and passes test(P, ids, box)"""
    cands = []
    for w_, h_ in ((tw, th), (th, tw)):
        xs = set(); ys = set()
        for i in ids:
            for v in pts(P[i]): xs.update((round(v[0], 2), round(v[0] - w_, 2))); ys.update((round(v[1], 2), round(v[1] - h_, 2)))
        for x0 in xs:
            for y0 in ys:
                B = (x0 - 0.3, y0 - 0.3, x0 + w_ + 0.3, y0 + h_ + 0.3)
                n = sum(1 for i in ids if all(B[0] <= v[0] <= B[2] and B[1] <= v[1] <= B[3] for v in pts(P[i])))
                if n >= 6: cands.append((n, (x0, y0, x0 + w_, y0 + h_)))
    for n, b in sorted(cands, key=lambda t: -t[0]):
        if test is None or test(P, ids, b): return n, b
    return (0, None)


def ibeam_families(dims, dw=0.6, dh=0.8, default=(4.08, 7.26)):
    """(code 007, regression of 06.10.2026) the I-beam families of a floor from the sizes of their grey fills [(short, long)
    pt]: a family is the median of the fills within dw x dh of it. One median for the whole floor made a template of no
    family where a floor has two (floor 5 of client A: 4.08 x 7.2 and 4.68 x 5.04 pt -> 4.44 x 6.12), and F1 dissolved ten
    real columns. No fill on the floor - the old default (floor 4 of client A) <один пример>"""
    import statistics
    fams = []
    for d in sorted(dims):
        for f in fams:
            if abs(d[0] - f['c'][0]) <= dw and abs(d[1] - f['c'][1]) <= dh:
                f['m'].append(d); f['c'] = (statistics.median(x[0] for x in f['m']), statistics.median(x[1] for x in f['m'])); break
        else: fams.append(dict(m=[d], c=tuple(d)))
    fams.sort(key=lambda f: -len(f['m']))
    return [f['c'] for f in fams] or [default]


def fam_of(d, fams, dw=0.6, dh=0.8):
    """the family (tw, th) the sorted size d of a fill belongs to, or None"""
    return next((f for f in fams if abs(d[0] - f[0]) <= dw and abs(d[1] - f[1]) <= dh), None)


def ibeam_box_fams(P, ids, fams):
    """ibeam_box tried with every family of the floor: the first that finds the I-beam"""
    res = (None, None, 'двутавра нет')
    for tw, th in fams:
        r = ibeam_box(P, ids, tw, th)
        if r[0] is not None: return r
        res = r
    return res


def ibeam_box(P, ids, tw, th):
    """(box, outline or None, how) of the I-beam among ids: its fill, else its outline; (None, None, why) if none"""
    from shapely.geometry import LineString
    from shapely.ops import unary_union
    fl = [i for i in ids if P[i][0] == 'qu' and is_col_fill(P[i][3])]
    for i in fl:
        b = bb_of(P, [i]); d = sorted([b[2] - b[0], b[3] - b[1]])
        if abs(d[0] - tw) <= 0.6 and abs(d[1] - th) <= 0.8:
            return b, unary_union([LineString(pts(P[j]) + [pts(P[j])[0]]) for j in fl]).buffer(0.15), 'заливка'
    Ls = [i for i in ids if P[i][0] == 'l']
    n, b = best_box(P, Ls, tw, th, ishape)
    if b is None: return None, None, 'двутавра нет'
    return b, None, 'контур'


# ---- monitors at the ends of tables (owner 03.10.2026: "в переговорных мониторы для конференц-связи, которые стоят
#      впритык к столу" - equipment, not a partition): a thin bar of two parallel thick rows (13-80 mm apart, w >= 0.45 pt)
#      across the end of a table, 0.8 x the table's width .. width + 500 mm long (from 600 mm), free at both ends (not a
#      piece of a partition between mullions), with a stand behind it (what lies within the bar's length and 160 mm and does
#      not run on past them; a fill or >= 3 pieces). The bar is found first and the table after it, so a table that took the
#      monitor is measured without it. Used by fix7.py (F3a, the fix) and checks/gate7.py (S18*, the check).
def monitor_bars(P, LN, G, T, near, key_of, tables, nomon, inside, used=None):
    """inside(poly) -> ids of all drawing primitives (lines, fills, curves) lying in poly. Returns (monitors, rows, bars,
    rejected): a candidate off the family of the floor's monitors (>= 3 alike: length 15 %, depth 30 %) is rejected"""
    from shapely.geometry import Point, Polygon, MultiPoint
    from shapely.ops import unary_union
    from shapely.strtree import STRtree
    from common import MM_PER_PT
    PT_ = 1 / MM_PER_PT
    used = set() if used is None else used
    def pen(i): return (round(P[i][1] or 0, 2), P[i][2])
    def canon(n):
        a, b = LN[n][1], LN[n][2]; u = unit(a, b)
        if u[0] < -1e-9 or (abs(u[0]) <= 1e-9 and u[1] < 0): u = (-u[0], -u[1])
        nr = (-u[1], u[0]); t = sorted((a[0] * u[0] + a[1] * u[1], b[0] * u[0] + b[1] * u[1]))
        return math.atan2(u[1], u[0]), a[0] * nr[0] + a[1] * nr[1], t[0], t[1], u, nr
    TK = [n for n, (i, a, b) in enumerate(LN) if (P[i][1] or 0) >= 0.45 and G[n].length >= 1.5 and key_of(i) not in nomon]
    CN = {n: canon(n) for n in TK}
    rows = []; RB = collections.defaultdict(list)                     # row: [angle, offset, t0, t1, u, nr, [n]]
    for n in sorted(TK, key=lambda n: (round(CN[n][0], 2), round(CN[n][1], 1), CN[n][2])):
        an, o, t0_, t1_, u, nr = CN[n]; hit = None
        for da in (-1, 0, 1):
            for do in (-1, 0, 1):
                for r in RB.get((round(an * 100) + da, round(o * 10) + do), ()):
                    if abs(r[0] - an) <= 0.009 and abs(r[1] - o) <= 0.06 and t0_ <= r[3] + 1.2 and t1_ >= r[2] - 1.2 and pen(LN[r[6][0]][0]) == pen(LN[n][0]):
                        hit = r; break
                if hit: break
            if hit: break
        if hit: hit[2] = min(hit[2], t0_); hit[3] = max(hit[3], t1_); hit[6].append(n)
        else:
            r = [an, o, t0_, t1_, u, nr, [n]]; rows.append(r); RB[(round(an * 100), round(o * 10))].append(r)
    bars = []; BYA = collections.defaultdict(list)
    for r in rows:
        if 600 * PT_ - 0.8 <= r[3] - r[2] <= 2600 * PT_ + 0.8: BYA[round(r[0] * 100)].append(r)
    for ak, rs in BYA.items():
        cand = sorted(rs + list(BYA.get(ak + 1, ())), key=lambda r: r[1])
        for a_ in range(len(cand)):
            for b_ in range(a_ + 1, len(cand)):
                ra, rb = cand[a_], cand[b_]
                if rb[1] - ra[1] > 1.3: break
                if abs(ra[0] - rb[0]) > 0.009 or rb[1] - ra[1] < 0.2: continue
                if abs(ra[2] - rb[2]) > 0.4 or abs(ra[3] - rb[3]) > 0.4: continue
                if not (600 * PT_ <= min(ra[3], rb[3]) - max(ra[2], rb[2]) <= 2600 * PT_): continue
                bars.append((ra, rb))
    TBL = [(k, ids) for k, ids in tables if ids]
    TBLH = [hull_of(P, ids) for k, ids in TBL]
    TBL = [t for t, h in zip(TBL, TBLH) if h is not None and h.geom_type == 'Polygon']; TBLH = [h for h in TBLH if h is not None and h.geom_type == 'Polygon']
    TBLT = STRtree(TBLH) if TBLH else None
    def rect(u, nr, t0_, t1_, o0, o1):
        return Polygon([(u[0] * t + nr[0] * o, u[1] * t + nr[1] * o) for t, o in ((t0_, o0), (t1_, o0), (t1_, o1), (t0_, o1))])
    def runs_out(lines, inside):
        """the lines of the zone that are pieces of a run of their pen (collinear, gaps <= 0.3 pt) that leaves the zone:
        chains are built per line of the plane (angle, offset), so a zone of thousands of tiny strokes stays cheap"""
        grp = collections.defaultdict(list)                       # (angle, offset, pen) -> [(t0, t1, n)]
        for n in lines:
            an, o, t0_, t1_, u, nr = canon(n)
            grp[(round(an * 100), round(o * 20), pen(LN[n][0]))].append((t0_, t1_, n))
        chains = {}                                               # group -> [[t0, t1, [n]]]
        for g, iv in grp.items():
            iv.sort(); ch = []
            for t0_, t1_, n in iv:
                if ch and t0_ <= ch[-1][1] + 0.3: ch[-1][1] = max(ch[-1][1], t1_); ch[-1][2].append(n)
                else: ch.append([t0_, t1_, [n]])
            chains[g] = ch
        S_ = set(lines); bad = set()
        for n in T.query(inside):
            if n in S_ or inside.contains(G[n]) or not G[n].intersects(inside.buffer(0.3)): continue
            an, o, t0_, t1_, u, nr = canon(n); pn = pen(LN[n][0])
            for da in (-1, 0, 1):
                for do in (-1, 0, 1):
                    for c in chains.get((round(an * 100) + da, round(o * 20) + do, pn), ()):
                        if t0_ <= c[1] + 0.3 and t1_ >= c[0] - 0.3: bad.update(c[2])
        return bad
    def continues(r, rows_ids):
        an, o, t0r, t1r, u, nr, ids = r
        for t_, sg in ((t0r, -1), (t1r, 1)):
            e = (u[0] * t_ + nr[0] * o, u[1] * t_ + nr[1] * o)
            for n2 in T.query(Point(e).buffer(1.5)):
                if n2 in rows_ids or pen(LN[n2][0]) != pen(LN[ids[0]][0]) or G[n2].distance(Point(e)) > 1.5: continue
                a2, o2, s0, s1, u2, nr2 = canon(n2)
                if abs(a2 - an) > 0.009 or abs(o2 - o) > 0.06: continue
                if (sg > 0 and s1 > t_ + 0.1) or (sg < 0 and s0 < t_ - 0.1): return True
        return False
    out = []; zones = []
    for ra, rb in bars:
        if any(LN[n][0] in used for n in ra[6] + rb[6]): continue
        u, nr = ra[4], ra[5]; t0_, t1_ = max(ra[2], rb[2]), min(ra[3], rb[3]); Lb = t1_ - t0_
        olo, ohi = min(ra[1], rb[1]), max(ra[1], rb[1])
        bar = rect(u, nr, t0_, t1_, olo, ohi)
        if any(z.intersects(bar) for z in zones): continue
        rids = set(ra[6]) | set(rb[6])
        if continues(ra, rids) or continues(rb, rids): continue
        # free-standing: nothing of walls, partitions or glazing holds the bar at its ends (a piece of a partition between
        #   mullions is held by the mullions; a monitor's bar ends in the air)
        held = False; barb = bar.buffer(0.1)
        for c_ in (rect(u, nr, t0_ - 0.5, t0_ + 0.05, olo - 0.3, ohi + 0.3), rect(u, nr, t1_ - 0.05, t1_ + 0.5, olo - 0.3, ohi + 0.3)):
            for n in T.query(c_):
                if n in rids or G[n].length < 0.3 or not G[n].intersects(c_): continue
                if G[n].difference(barb).length < 0.3: continue             # a thin duplicate of the bar's own line
                if key_of(LN[n][0]) in LAYER1: held = True; break
            if held: break
        if held: continue
        parts = []
        for j in (TBLT.query(bar.buffer(1.5)) if TBLT is not None else ()):
            k, ids = TBL[j]; body_xy = []
            for i in ids:
                q_ = pts(P[i])
                if all(t0_ - 0.5 <= v_[0] * u[0] + v_[1] * u[1] <= t1_ + 0.5 and olo - 2.8 <= v_[0] * nr[0] + v_[1] * nr[1] <= ohi + 2.8 for v_ in q_): continue
                body_xy += q_
            h = MultiPoint(body_xy).convex_hull if len(body_xy) >= 3 else None
            if h is not None and h.geom_type == 'Polygon' and h.distance(bar) <= 1.0: parts.append((k, h))
        if not parts: continue
        h = unary_union([h for kk, h in parts]).convex_hull
        k = min(parts, key=lambda t: t[1].distance(bar))[0]
        r = h.minimum_rotated_rectangle; cc = list(r.exterior.coords)
        e1, e2 = (cc[0], cc[1]), (cc[1], cc[2])
        (la, lb), (sa, sb) = (e1, e2) if math.dist(*e1) >= math.dist(*e2) else (e2, e1)
        Lt, St = math.dist(la, lb), math.dist(sa, sb); v = unit(sa, sb); ul = unit(la, lb)
        if abs(u[0] * v[0] + u[1] * v[1]) < 0.98 or not (max(0.8 * St, 600 * PT_) <= Lb <= St + 500 * PT_): continue
        ctr = r.centroid; bc = bar.centroid
        if abs((bc.x - ctr.x) * ul[0] + (bc.y - ctr.y) * ul[1]) < Lt / 2 - 1.5: continue
        side = 1 if (h.centroid.x - bc.x) * nr[0] + (h.centroid.y - bc.y) * nr[1] < 0 else -1
        zone = rect(u, nr, t0_ - 0.3, t1_ + 0.3, ohi, ohi + 2.5) if side > 0 else rect(u, nr, t0_ - 0.3, t1_ + 0.3, olo - 2.5, olo)
        zb = zone.buffer(0.05)
        allc = [i for i in inside(zb) if key_of(i) not in nomon and i not in used]
        POSl = {LN[n][0]: n for n in T.query(zb)}
        runs = runs_out([POSl[i] for i in allc if i in POSl], zb)
        far = ohi if side > 0 else olo
        def dep(v_): return abs((v_[0] * nr[0] + v_[1] * nr[1]) - far)
        cut = min([dep(LN[n][1]) for n in runs if abs(unit(LN[n][1], LN[n][2])[0] * u[0] + unit(LN[n][1], LN[n][2])[1] * u[1]) >= 0.995] + [2.5]) - 0.05
        stand = [i for i in allc if not (i in POSl and POSl[i] in runs) and all(dep(v_) <= cut for v_ in pts(P[i]))]
        if not any(P[i][0] == 'qu' for i in stand) and len(stand) < 3: continue       # a monitor stands on a stand
        near_row = ra if abs(ra[1] - (olo if side > 0 else ohi)) < 1e-6 else rb
        out.append(dict(bar=bar, zone=zone, cut=cut, side=side, far=far, nr=nr, u=u, Lb=Lb, thick=ohi - olo,
                        bar_ids=[LN[n][0] for n in ra[6] + rb[6]], near_ids=[LN[n][0] for n in near_row[6]],
                        stand=stand, depth=max([dep(v_) for i in stand for v_ in pts(P[i])] + [0.0]), parts=parts, k=k))
        zones.append(bar.union(zone).envelope)
    rejected = []
    if len(out) >= 3:
        mL = statistics.median(m['Lb'] for m in out); mD = statistics.median(m['depth'] + m['thick'] for m in out)
        keep = []
        for m in out:
            if abs(m['Lb'] - mL) > 0.15 * mL or abs(m['depth'] + m['thick'] - mD) > 0.3 * mD + 0.3: rejected.append(m)
            else: keep.append(m)
        out = keep
    return out, len(rows), len(bars), rejected


# ---------------------------------------------------------------- stairs and openings A-23 (owner 04.10.2026, строка 173)
# "На слое несущих конструкций показывай проём там, где он есть. А на слое дверей и выходов нужно показывать
# лестницы, идущие вверх и вниз." A flight that only goes up from this floor passes through the slab of the floor
# above: its opening is drawn on that plan, not here. A short flight is a change of level inside the floor - no slab
# opening at all. fix7.py (F10) and checks/gate7.py (S27*) decide with the same function (п. 283).
_WORDS = None
def sheet_words(pdf=None):
    """words of the sheet in display pt: [(text, x0, y0, x1, y1)] (page rotation applied, as export.py does)"""
    global _WORDS
    if _WORDS is None:
        import pymupdf
        pg = pymupdf.open(pdf or cfg.PDF)[0]; M = pg.rotation_matrix; _WORDS = []
        for b in pg.get_text('dict')['blocks']:
            for ln in b.get('lines', []):
                for s in ln['spans']:
                    t = s['text'].strip()
                    if t:
                        r = pymupdf.Rect(s['bbox']) * M
                        _WORDS.append((t, r.x0, r.y0, r.x1, r.y1))
    return _WORDS

def tread_lines(P, ids, mm_per_pt):
    """the longest flight of a stair: parallel lines of one length (+-12 %) at least 0.5 m long, each 195-400 mm from
    the next one (a tread is 230-350 mm, rule L); a doubled stroke (< 30 mm) does not break the run"""
    L = []
    for i in ids:
        p = P[i]
        if p[0] != 'l': continue
        a, b = p[4][0], p[4][-1]; d = math.dist(a, b)
        if d * mm_per_pt < 500: continue
        L.append((math.degrees(math.atan2(b[1] - a[1], b[0] - a[0])) % 180, d, ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)))
    best = 0
    for ang0, d0, _ in L:
        grp = [(d, c) for ang, d, c in L if min(abs(ang - ang0), 180 - abs(ang - ang0)) <= 3 and abs(d - d0) <= 0.12 * d0]
        if len(grp) <= best: continue
        th = math.radians(ang0); nr = (-math.sin(th), math.cos(th))
        offs = sorted(set(round((c[0] * nr[0] + c[1] * nr[1]) * mm_per_pt) for d, c in grp))
        run = mx = 1
        for x, y in zip(offs, offs[1:]):
            g = y - x
            if g < 30: continue
            run = run + 1 if 195 <= g <= 400 else 1
            mx = max(mx, run)
        best = max(best, mx)
    return best

SHORT_FLIGHT = 9      # fewer tread lines than this: a change of level (a floor-to-floor flight has 9 and more)
def stair_needs_opening(P, ids, hull, mm_per_pt, words=None, margin=4.0, in_cage=False):
    """(need, why, info). need=False: no opening in this floor's slab - the flight only goes up (labels «ВВЕРХ» and no
    «ВНИЗ» at the stair), or, outside a closed stair cage, it is a short flight without «ВНИЗ» (a change of level
    inside the floor). A stair in a closed cage (F10: the stair is at least a third of the room) is cut by the plan
    plane and drawn with fewer treads - its tread count says nothing"""
    words = sheet_words() if words is None else words
    zone = hull.buffer(margin); up = down = False
    from shapely.geometry import box as _box
    for t, x0, y0, x1, y1 in words:
        tu = t.upper()
        if ('ВВЕРХ' in tu or 'ВНИЗ' in tu) and zone.intersects(_box(x0, y0, x1, y1)):
            up |= 'ВВЕРХ' in tu; down |= 'ВНИЗ' in tu
    n = tread_lines(P, ids, mm_per_pt)
    info = dict(up=up, down=down, tread_lines=n)
    if up and not down:
        return False, 'марш только вверх: «ВВЕРХ» без «ВНИЗ» — проём в перекрытии этажа выше (строка 173)', info
    info['cage'] = in_cage
    if n < SHORT_FLIGHT and not down and not in_cage:
        return False, f'короткий марш, {n} линий ступеней: смена уровня внутри этажа — проёма в перекрытии нет (строка 173)', info
    return True, ('марш вниз' if down else 'лестница через этажи'), info


# ---------------------------------------------------------------- glass doors (owner 04.10.2026, строка 172)
# "Это проём — разрыв"; "такую дверь саму показывать как стеклянную. Показать разрыв, что там есть проход, а саму
# дверь в другом стиле." A door whose opening a glass line runs through (the source draws the glass partition
# unbroken): the glass line is cut between the jambs, the door is drawn in the glass style on A-32.
GLASS_KEYS = {'glasspart', 'glass'}
def door_opening(I, k):
    """(hinge, far edge) of a door: the far edge is the hinge of the other leaf of a pair, else the closed end"""
    d = I[k]['door']; c, cl = d['c'], d['closed']
    for k2, q2 in enumerate(I):
        if k2 != k and q2['key'] == 'door' and q2.get('door') and math.dist(q2['door']['closed'], cl) <= 1.6:
            return c, q2['door']['c']
    return c, cl

def glass_through(P, ids_keys, a, b, tol=0.6, ang=5.0, cover=0.6):
    """line prims of glass owners lying along the opening a-b: parallel (<= ang deg), both ends within tol pt of the
    opening's line, overlapping the opening; together they cover >= cover of it (a line may be drawn in pieces).
    ids_keys: [(prim id, owner keys)]"""
    L0 = math.dist(a, b)
    if L0 < 1.0: return []
    u = unit(a, b); nr = (-u[1], u[0]); got = []
    def t_(p): return (p[0] - a[0]) * u[0] + (p[1] - a[1]) * u[1]
    def o_(p): return (p[0] - a[0]) * nr[0] + (p[1] - a[1]) * nr[1]
    for i, ks in ids_keys:
        p = P[i]
        if p[0] != 'l' or not (ks & GLASS_KEYS): continue
        s, e = p[4][0], p[4][-1]
        if math.dist(s, e) < 0.5: continue
        v = unit(s, e)
        if abs(u[0] * v[1] - u[1] * v[0]) > math.sin(math.radians(ang)): continue
        ts, te = t_(s), t_(e)
        if abs(te - ts) < 1e-6: continue
        t0, t1 = sorted((ts, te))
        lo, hi = max(t0, 0.0), min(t1, L0)
        if hi - lo <= 0.05: continue
        def off(t, ts=ts, te=te, os_=o_(s), oe=o_(e)): return os_ + (oe - os_) * (t - ts) / (te - ts)
        if max(abs(off(lo)), abs(off(hi))) > tol: continue         # the line near the opening, where it overlaps it
        got.append((i, lo, hi))
    if not got: return []
    iv = sorted((lo, hi) for i, lo, hi in got); covered = 0.0; cur = None
    for lo, hi in iv:
        if cur is None or lo > cur[1]: covered += (cur[1] - cur[0]) if cur else 0.0; cur = [lo, hi]
        else: cur[1] = max(cur[1], hi)
    covered += cur[1] - cur[0]
    return [i for i, lo, hi in got] if covered >= cover * L0 else []

def opening_lines(P, ids_keys, a, b, tol=0.8, ang=5.0, min_overlap=3.0):
    """every line lying along a door opening a-b, whoever holds it: parallel (<= ang deg), within tol pt of the
    opening's line where it overlaps it, overlapping it by >= min_overlap pt. In a glass door these are the glass
    partition strokes running through and the closed glass panel; tiny jamb details (< min_overlap) stay.
    ids_keys: [(prim id, owner keys)] - the caller leaves out the door's own lines and wall prims"""
    L0 = math.dist(a, b)
    if L0 < 1.0: return []
    u = unit(a, b); nr = (-u[1], u[0]); out = []
    def t_(p): return (p[0] - a[0]) * u[0] + (p[1] - a[1]) * u[1]
    def o_(p): return (p[0] - a[0]) * nr[0] + (p[1] - a[1]) * nr[1]
    for i, ks in ids_keys:
        p = P[i]
        if p[0] != 'l': continue
        s, e = p[4][0], p[4][-1]
        if math.dist(s, e) < min_overlap: continue
        v = unit(s, e)
        if abs(u[0] * v[1] - u[1] * v[0]) > math.sin(math.radians(ang)): continue
        ts, te = t_(s), t_(e)
        if abs(te - ts) < 1e-6: continue
        lo, hi = max(min(ts, te), 0.0), min(max(ts, te), L0)
        if hi - lo < min_overlap: continue
        def off(t, ts=ts, te=te, os_=o_(s), oe=o_(e)): return os_ + (oe - os_) * (t - ts) / (te - ts)
        if max(abs(off(lo)), abs(off(hi))) > tol: continue
        out.append(i)
    return out

def Point_(p):
    from shapely.geometry import Point as _P
    return _P(p)

def gap_strip(a, b, half=0.8):
    """the cut of a glass line in a door opening: the strip between the jambs, half pt across, flat ends"""
    from shapely.geometry import LineString as _LS
    return _LS([a, b]).buffer(half, cap_style=2)

def glass_gaps(I):
    """{prim id: [strip, ...]} from the doors fix7.py marked as glass doors (q['glass_gap'])"""
    out = collections.defaultdict(list)
    for q in I:
        g = q.get('glass_gap')
        if not g: continue
        s = gap_strip(g['a'], g['b'], g.get('half', 0.8))
        for i in g['prims']: out[i].append(s)
    return out

def cut_line(pts_, strips):
    """pieces of a polyline outside the strips (list of point lists)"""
    from shapely.geometry import LineString as _LS
    from shapely.ops import unary_union as _UU
    g = _LS(pts_).difference(_UU(strips))
    parts = [g] if g.geom_type == 'LineString' else [x for x in getattr(g, 'geoms', []) if x.geom_type == 'LineString']
    return [list(x.coords) for x in parts if not x.is_empty and x.length > 0]
