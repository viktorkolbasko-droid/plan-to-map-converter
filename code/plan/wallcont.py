# A wall that ends before the source wall does (plan/rules/60 §4, integrity; floor 4: the lower stub of the stair
# enclosure was taken by the glazing band and stayed an outline). Used by geomqa.py (check) and walls_vec5.py
# (round 2 takes the strokes as hatch when cfg.WALL_CONTINUATION is on).
#
# Continuation stroke: a line outside the walls that carries the hatch of a wall body on along its band -
#   same width and colour as a hatch stroke of the body (a stroke crossing its band at 20-70 deg) within 8 pt,
#   parallel to it (+-15 deg), length x0.4-2.5, on the band axis (offset across <= 1.5 x half width), with a face
#   line of the band on both sides (lines along the band at 0.5-1.6 half widths: the band itself goes on).
#   Accepted strokes carry the search on, at most 4 steps from the body (a curved stub turns step by step).
#   Lines of identified objects (WC, doors, desks, ...) are theirs and never taken.
import math, collections
import numpy as np
from scipy.spatial import cKDTree
from shapely.geometry import Point, LineString
from shapely.strtree import STRtree
from shapely.prepared import prep

OBJ = ('roomsep', 'sign', 'carpet', 'wcsink', 'wc', 'wcacc', 'sink', 'rack', 'door', 'door45', 'doorhw', 'column', 'desk', 'chair', 'stool', 'cafe', 'convector',
       'tag', 'lift', 'stair', 'rdoor', 'sofa', 'equip', 'fire', 'screen', 'axmark', 'kitchen', 'mtable', 'fscreen')


def _polys(g):
    return [g] if g.geom_type == 'Polygon' else [x for x in getattr(g, 'geoms', []) if x.geom_type == 'Polygon']


def diag_zones(cfg):
    """cfg.DIAG_ZONES as a point test: 45-degree bands whose hatch runs at 0/90 (box or (polyline, half width))"""
    from shapely.geometry import box as _b
    from shapely.prepared import prep as _pp
    Z = [_pp(_b(*z) if len(z) == 4 and all(isinstance(v, (int, float)) for v in z) else LineString(z[0]).buffer(z[1], cap_style=2))
         for z in getattr(cfg, 'DIAG_ZONES', [])]
    return lambda m: any(g.contains(Point(m)) for g in Z)


def continuation(P, cls, own, Wpt, pts, max_steps=4, min_cluster=2, axis_ok=None):
    # (28.09.2026) an outside stroke along an axis (0/90 +- 6 deg) is a door frame or a column flange, not hatch - except
    #   in a 45-degree band (axis_ok(m): cfg.DIAG_ZONES), whose pattern runs at 0/90 (floor 2: 80 strokes of door frames)
    axis_ok = axis_ok or (lambda m: False)
    bodies = [p for v in Wpt.values() for g in v for p in _polys(g)]
    if not bodies: return []
    ang = lambda a, b: math.degrees(math.atan2(b[1] - a[1], b[0] - a[0])) % 180
    # hatch is drawn in a neutral pen (black / grey <= 0.85): coloured dashes (room separation lines) are never hatch
    def neutral(c): return c is not None and abs(c[0] - c[1]) < 0.02 and abs(c[1] - c[2]) < 0.02 and c[0] <= 0.85
    L_ = [(i, p) for i, p in enumerate(P) if p[0] == 'l' and cls[i] not in ('axis', 'dim', 'sheet') and 0.5 <= math.dist(*p[4]) <= 15 and neutral(p[2])]
    Sg = [LineString(p[4]) for i, p in L_]
    pb = [prep(b.buffer(0.3)) for b in bodies]; bt = STRtree(bodies)
    # all lines for the face test
    FL = [(i, pts(p)) for i, p in enumerate(P) if p[0] in ('l', 'c') and cls[i] not in ('axis', 'dim', 'sheet')]
    FG = [LineString(c) for i, c in FL]; ft = STRtree(FG)
    FA = [ang(c[0], c[-1]) for i, c in FL]; FLEN = [g.length for g in FG]
    _bs = {}
    def band_dir(bi, m, r=5.0):
        """direction of the band around m: principal axis of the body outline within r pt (a cut end next to the
        stroke does not turn it: the long faces dominate)"""
        if bi not in _bs:
            bd = bodies[bi].exterior; n = max(4, int(bd.length / 0.3))
            _bs[bi] = np.array([bd.interpolate(t, normalized=True).coords[0] for t in np.linspace(0, 1, n, endpoint=False)])
        A = _bs[bi]; sel = A[np.hypot(A[:, 0] - m.x, A[:, 1] - m.y) <= r]
        if len(sel) < 4: return None
        c = sel - sel.mean(0); u = np.linalg.svd(c, full_matrices=False)[2][0]
        return math.degrees(math.atan2(u[1], u[0])) % 180
    def faces_both_sides(m, fa, hw):
        ux, uy = math.cos(math.radians(fa)), math.sin(math.radians(fa)); nx, ny = -uy, ux
        R = 1.6 * hw + 1.0; pos = neg = False
        for j in ft.query(Point(m).buffer(R)):
            j = int(j)
            if FLEN[j] < 1.0 or abs(((FA[j] - fa) + 90) % 180 - 90) > 20: continue
            q = FG[j].interpolate(FG[j].project(Point(m)))
            s = (q.x - m[0]) * nx + (q.y - m[1]) * ny; t_ = abs((q.x - m[0]) * ux + (q.y - m[1]) * uy)
            if t_ > 3.0: continue
            if 0.5 * hw <= s <= 1.6 * hw + 0.3: pos = True
            elif -1.6 * hw - 0.3 <= s <= -0.5 * hw: neg = True
            if pos and neg: return True
        return False
    inside = []; outside = []
    for k, (i, p) in enumerate(L_):
        m = Point((p[4][0][0] + p[4][1][0]) / 2, (p[4][0][1] + p[4][1][1]) / 2)
        hit = [int(j) for j in bt.query(m.buffer(0.3)) if pb[int(j)].contains(m)]
        if hit:
            fa = band_dir(hit[0], m)
            if fa is not None and 20 <= abs(((ang(*p[4]) - fa) + 90) % 180 - 90) <= 70:   # a hatch stroke (a cap line crosses at 90)
                inside.append((k, hit[0], fa, max(0.3, bodies[hit[0]].exterior.distance(m))))
        elif own.get(i) not in OBJ and sum(Sg[k].intersection(bodies[int(j)].buffer(0.3)).length for j in bt.query(Sg[k])) < 0.5 * Sg[k].length:
            t_ = ang(*p[4])
            if min(t_ % 90, 90 - t_ % 90) <= 6 and not axis_ok((m.x, m.y)): continue
            outside.append(k)
    if not inside or not outside: return []
    refs = [(np.array(((L_[k][1][4][0][0] + L_[k][1][4][1][0]) / 2, (L_[k][1][4][0][1] + L_[k][1][4][1][1]) / 2)), L_[k][1], bi, fa, hw)
            for k, bi, fa, hw in inside]
    cont = []; done = set()
    for step in range(max_steps):
        if not refs: break
        RT = cKDTree(np.array([r[0] for r in refs])); acc = []
        for k in outside:
            if k in done: continue
            i, p = L_[k]; a, b = p[4]; m = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2); t = ang(a, b); Lk = math.dist(a, b)
            for j in sorted(RT.query_ball_point(m, 8.0), key=lambda j: math.dist(refs[j][0], m)):
                rm, p2, bi, fa, hw = refs[j]
                if p2[1] != p[1] or p2[2] != p[2]: continue                   # same stroke width and colour
                if abs(((t - ang(*p2[4])) + 90) % 180 - 90) > 15: continue
                if not (0.4 <= Lk / math.dist(*p2[4]) <= 2.5): continue
                ux, uy = math.cos(math.radians(fa)), math.sin(math.radians(fa))
                dx, dy = m[0] - rm[0], m[1] - rm[1]
                if abs(-dx * uy + dy * ux) > max(1.0, 1.5 * hw): continue   # off the band axis: beside the wall
                fa2 = math.degrees(math.atan2(dy, dx)) % 180 if math.hypot(dx, dy) > 1.0 else fa
                if abs(((fa2 - fa) + 90) % 180 - 90) > 30: fa2 = fa           # the band turns step by step at most
                if not faces_both_sides(m, fa2, hw): continue                 # the band itself goes on here
                cont.append((k, bi, m, step)); done.add(k); acc.append((np.array(m), p, bi, fa2, hw)); break
        refs = acc
    if not cont: return []
    M = np.array([c[2] for c in cont]); par = list(range(len(cont)))
    def f(x):
        while par[x] != x: par[x] = par[par[x]]; x = par[x]
        return x
    for a_, b_ in cKDTree(M).query_pairs(8.0): par[f(a_)] = f(b_)
    cl = collections.defaultdict(list)
    for n in range(len(cont)): cl[f(n)].append(n)
    out = []
    for v in cl.values():
        if len(v) < min_cluster: continue
        ids = [L_[cont[n][0]][0] for n in v]
        offs = []
        for n in v:
            a, b = L_[cont[n][0]][1][4]; L0 = math.dist(a, b); nx, ny = -(b[1] - a[1]) / L0, (b[0] - a[0]) / L0
            offs.append(a[0] * nx + a[1] * ny)
        if max(offs) - min(offs) < 0.5: continue                              # pieces of one line, not a hatch
        out.append(dict(n=len(v), bbox_pt=[round(float(M[v, 0].min()), 1), round(float(M[v, 1].min()), 1), round(float(M[v, 0].max()), 1), round(float(M[v, 1].max()), 1)],
                        owners=collections.Counter(own.get(i, 'free') for i in ids).most_common(3), ids=ids,
                        bodies=sorted({cont[n][1] for n in v})))
    return sorted(out, key=lambda d: -d['n'])
