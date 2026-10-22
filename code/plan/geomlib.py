# Geometry clean-up primitives (plan/rules/50 §9): axis snapping by vertex groups, straight runs with two points,
# merging of duplicate / collinear line pieces. Coordinates in mm. Used by geomfix.py on walls, blocks and loose lines.
import math, collections
import numpy as np
from scipy.spatial import cKDTree

EPS_NODE = 0.3      # points closer than this are one vertex (shared corners of neighbouring polygons / lines)
TJ = 0.6            # a vertex this close to another element's edge is a T-junction: it keeps lying on that edge
MICRO = 1.0         # lateral offset below this is numerical noise: snapped on any element


class UF:
    def __init__(s, n): s.p = list(range(n))
    def f(s, x):
        while s.p[x] != x:
            s.p[x] = s.p[s.p[x]]; x = s.p[x]
        return x
    def u(s, a, b):
        a, b = s.f(a), s.f(b)
        if a != b: s.p[a] = b


def axis_dev(dx, dy):
    """(angle to the nearest axis in deg, lateral offset, intended orientation 'H'/'V')"""
    t = math.degrees(math.atan2(dy, dx)) % 90
    return min(t, 90 - t), min(abs(dx), abs(dy)), ('H' if abs(dx) >= abs(dy) else 'V')


def turn_deg(d1, d2):
    a = math.degrees(math.atan2(d2[1], d2[0]) - math.atan2(d1[1], d1[0]))
    return (a + 180) % 360 - 180


def snap_chains(chains, snap_max, curved=None, report=None, debug=None):
    """chains: list of (points [(x,y)...], closed bool). Returns chains with snapped coordinates (same structure).
    An edge a little off 0/90 deg is made exact by giving its two vertices one common x (vertical) or y (horizontal);
    vertices are shared, so the neighbouring polygons / lines move with them and stay joined.
      exact      : lateral < 0.01 mm - joins its group, keeps the group on its coordinate (weight = length)
      micro      : lateral <= MICRO and angle <= 10 deg
      quantum    : lateral <= snap_max (2 print quanta) and not a chord of an arc, not in a curved zone, and
                   angle <= 10 deg
      cap        : the same, angle <= 30 deg, between two parallel faces on the axes (a skewed end cap)
      step       : a Z-step <= snap_max between two parallel faces on the axes that go on in the same direction:
                   the two faces become one straight face (a step below the print resolution is not in the source:
                   floor 1 - the wall outline ran inside one thick source line on two levels)
    A group whose members spread over more than snap_max is left as it is (a real step / slope, not print noise).
    curved(point) -> True where edges are arcs by design (cfg.CURVED_ZONES): only micro there."""
    R = report if report is not None else collections.Counter()
    pts = []; owner = []
    for ci, (c, closed) in enumerate(chains):
        for pi, p in enumerate(c): pts.append(p); owner.append((ci, pi))
    if not pts: return chains
    A = np.array(pts, float)
    uf = UF(len(A))
    for i, j in cKDTree(A).query_pairs(EPS_NODE): uf.u(i, j)
    root = [uf.f(i) for i in range(len(A))]
    ids = {r: k for k, r in enumerate(sorted(set(root)))}
    node = [ids[r] for r in root]; N = len(ids)
    NX = np.zeros((N, 2)); cnt = np.zeros(N)
    for i, n in enumerate(node): NX[n] += A[i]; cnt[n] += 1
    NX /= cnt[:, None]
    # edges: (n1, n2, chain, index); context = previous / next edge of the same chain, or the only other edge at a
    # node of degree 2 (separate LINE entities that continue each other)
    E = []; base = 0; chain_edges = []
    for ci, (c, closed) in enumerate(chains):
        k = len(c); idx = [node[base + t] for t in range(k)]; ce = []
        rng = range(k) if closed else range(k - 1)
        for t in rng:
            a, b = idx[t], idx[(t + 1) % k]
            if a == b: continue
            ce.append(len(E)); E.append((a, b))
        chain_edges.append((ce, closed)); base += k
    if not E: return chains
    deg = collections.defaultdict(list)
    for e, (a, b) in enumerate(E): deg[a].append(e); deg[b].append(e)
    prev = [None] * len(E); nxt = [None] * len(E)
    for ce, closed in chain_edges:
        for t, e in enumerate(ce):
            if t > 0 or closed and len(ce) > 1: prev[e] = ce[t - 1]
            if t < len(ce) - 1 or closed and len(ce) > 1: nxt[e] = ce[(t + 1) % len(ce)]
    for e, (a, b) in enumerate(E):
        if prev[e] is None and len(deg[a]) == 2: prev[e] = [x for x in deg[a] if x != e][0]
        if nxt[e] is None and len(deg[b]) == 2: nxt[e] = [x for x in deg[b] if x != e][0]
    def vec(e, at=None):
        a, b = E[e]; return (NX[b][0] - NX[a][0], NX[b][1] - NX[a][1])
    info = []
    for e, (a, b) in enumerate(E):
        dx, dy = vec(e); L = math.hypot(dx, dy); ang, lat, o = axis_dev(dx, dy)
        info.append((L, ang, lat, o))
    def axis_like(e):
        if e is None: return False
        L, ang, lat, o = info[e]
        return lat < 0.01 or ang <= 0.6 or (lat <= MICRO and ang <= 10)
    def oriented(e):
        return info[e][3]
    def dir_at(e, n):
        """direction of edge e pointing away from node n"""
        a, b = E[e]; d = vec(e); return d if a == n else (-d[0], -d[1])
    def turn_at(e, nb, n):
        """turn of the walk e -> nb through their common node n (0 = straight on)"""
        u, v = dir_at(e, n), dir_at(nb, n)
        th = abs(turn_deg(u, v))          # angle between the two edges seen from n
        return 180 - th
    def arc_chord(e):
        a, b = E[e]
        for nb, n in ((prev[e], a), (nxt[e], b)):
            if nb is None or axis_like(nb) or n not in E[nb]: continue
            if 0.2 < turn_at(e, nb, n) < 25: return True
        return False
    ux = UF(N); uy = UF(N)
    wX = np.zeros(N); wY = np.zeros(N)
    exX = np.zeros(N, bool); exY = np.zeros(N, bool)     # the vertex lies on an exact edge
    grouped = [None] * len(E)
    def step_of(e):
        """a Z-step: both neighbours on the axes and parallel, the walk goes on in the same direction and the faces are
        at most snap_max apart -> the orientation of the faces (their common coordinate is merged), else None"""
        pe, ne = prev[e], nxt[e]
        if not (axis_like(pe) and axis_like(ne)): return None
        op = oriented(pe)
        if oriented(ne) != op: return None
        a, b = E[e]
        if a not in E[pe] or b not in E[ne]: return None
        u, v = dir_at(pe, a), dir_at(ne, b)
        if u[0] * v[0] + u[1] * v[1] >= 0: return None          # U-turn: the end of a thin element, not a step
        dx, dy = vec(e); off = abs(dy) if op == 'H' else abs(dx)
        if off < 0.01 or off > snap_max: return None
        # the faces must be long compared with the step (a real notch has short sides)
        if min(info[pe][0], info[ne][0]) < 3 * off: return None
        return op
    for e, (a, b) in enumerate(E):
        L, ang, lat, o = info[e]
        if L < 1e-6: continue
        kind = None; go = o
        sp = step_of(e)
        m = ((NX[a][0] + NX[b][0]) / 2, (NX[a][1] + NX[b][1]) / 2)
        if sp is not None and not (curved is not None and curved(m)):
            kind = 'step'; go = sp                               # merge the two faces through this edge
        elif lat < 0.01: kind = 'exact'
        elif lat <= MICRO and ang <= 10: kind = 'micro'
        elif lat <= snap_max:
            if curved is not None and curved(m): R['skip_curved_zone'] += 1
            elif arc_chord(e): R['skip_arc_chord'] += 1
            elif ang <= 10: kind = 'quantum'
            elif ang <= 30 and axis_like(prev[e]) and axis_like(nxt[e]) and oriented(prev[e]) == oriented(nxt[e]) != o:
                kind = 'cap'                                     # a skewed end cap between two faces
            else: R['skip_context'] += 1
        if kind is None: continue
        grouped[e] = kind
        if kind != 'exact':
            R['snap_' + kind] += 1
            if debug is not None: debug.append(dict(edge=(tuple(NX[a]), tuple(NX[b])), kind=kind, L=round(L, 1), ang=round(ang, 2), lat=round(lat, 2)))
        w = L if kind == 'exact' else 0.1 * L
        if go == 'H':
            uy.u(a, b); wY[a] += w; wY[b] += w
            if kind == 'exact': exY[a] = exY[b] = True
        else:
            ux.u(a, b); wX[a] += w; wX[b] += w
            if kind == 'exact': exX[a] = exX[b] = True
        if kind == 'step' and lat < 0.01 and o != go:            # an exact perpendicular step keeps its own coordinate too
            (ux if o == 'V' else uy).u(a, b)
    # T-junctions: a vertex lying on another element's grouped edge keeps lying on it
    try:
        from shapely.strtree import STRtree
        from shapely.geometry import LineString, Point
        G = [e for e in range(len(E)) if grouped[e]]
        if G:
            lines = [LineString([NX[E[e][0]], NX[E[e][1]]]) for e in G]
            tr = STRtree(lines)
            for n in range(N):
                p = Point(NX[n])
                for k in tr.query(p.buffer(TJ)):
                    e = G[int(k)]; a, b = E[e]
                    if n in (a, b) or lines[int(k)].distance(p) > TJ: continue
                    # the vertex must project inside the edge (not near its ends: that is a corner, not a T)
                    t = lines[int(k)].project(p)
                    if t < TJ or t > lines[int(k)].length - TJ: continue
                    if info[e][3] == 'H': uy.u(n, a); R['tjunction'] += 1
                    else: ux.u(n, a); R['tjunction'] += 1
    except Exception as ex:
        R['tjunction_error'] = str(ex)
    newX = NX.copy()
    for axis, U_, w, ex in ((0, ux, wX, exX), (1, uy, wY, exY)):
        groups = collections.defaultdict(list)
        for n in range(N): groups[U_.f(n)].append(n)
        for g in groups.values():
            if len(g) < 2: continue
            vals = NX[g, axis]; ws = w[g] + 1e-6
            if vals.max() - vals.min() <= 1e-9: continue
            if debug is not None: debug.append(dict(axis='xy'[axis], nodes=[tuple(NX[n]) for n in g], w=[float(w[n]) for n in g], exact=[bool(ex[n]) for n in g]))
            if vals.max() - vals.min() > snap_max:
                R['group_spread_skipped'] += 1; continue
            xv = NX[[n for n in g if ex[n]], axis]
            if len(xv) and xv.max() - xv.min() > MICRO: R['group_two_faces_merged'] += 1   # a step below the print resolution
            o = np.argsort(vals); sv = vals[o]; cs = np.cumsum(ws[o]); k = int(np.searchsorted(cs, cs[-1] / 2))
            k = min(k, len(sv) - 1); v = float(sv[k])
            if abs(cs[k] - cs[-1] / 2) <= 0.05 * cs[-1] and k + 1 < len(sv): v = float((sv[k] + sv[k + 1]) / 2)   # tie
            newX[g, axis] = v
    mv = np.hypot(*(newX - NX).T)
    R['nodes_moved'] += int((mv > 1e-6).sum()); R['max_move_mm'] = max(R.get('max_move_mm', 0), round(float(mv.max()), 2))
    out = []; base = 0
    for ci, (c, closed) in enumerate(chains):
        k = len(c)
        out.append(([tuple(newX[node[base + t]]) for t in range(k)], closed)); base += k
    return out


def simplify_run(c, closed, tol=0.2):
    """drop vertices that lie on the straight run between their neighbours (within tol mm of the new edge, checked
    against every dropped original vertex) and repeated vertices; a straight run keeps its two end points"""
    pts = []
    for p in c:
        if not pts or math.dist(p, pts[-1]) > 1e-6: pts.append(tuple(p))
    if closed and len(pts) > 1 and math.dist(pts[0], pts[-1]) <= 1e-6: pts.pop()
    if len(pts) < (4 if closed else 3): return pts
    def seg_dist(p, a, b):
        dx, dy = b[0] - a[0], b[1] - a[1]; L2 = dx * dx + dy * dy
        if L2 < 1e-12: return math.dist(p, a)
        t = max(0, min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L2))
        return math.dist(p, (a[0] + t * dx, a[1] + t * dy))
    if closed:
        # start at the sharpest corner so a straight run is never split at the ring start
        def turn_at(i):
            a, b, d = pts[i - 1], pts[i], pts[(i + 1) % len(pts)]
            return abs(turn_deg((b[0] - a[0], b[1] - a[1]), (d[0] - b[0], d[1] - b[1])))
        s = max(range(len(pts)), key=turn_at); pts = pts[s:] + pts[:s]
        seq = pts + [pts[0]]
    else:
        seq = pts
    keep = [seq[0]]; run = []
    for i in range(1, len(seq) - 1):
        cand = seq[i + 1]
        if all(seg_dist(q, keep[-1], cand) <= tol for q in run + [seq[i]]):
            run.append(seq[i]); continue
        keep.append(seq[i]); run = []
    keep.append(seq[-1])
    if closed:
        keep = keep[:-1]
        if len(keep) >= 3:     # the start vertex itself
            a, b, d = keep[-1], keep[0], keep[1]
            if seg_dist(b, a, d) <= tol and len(keep) > 3: keep = keep[1:]
    return keep


def merge_lines(lines, tol=0.15, gap=0.3):
    """lines: [(a, b)] in mm. Duplicates (either direction) dropped; collinear pieces that touch or overlap merged
    into one line (all original end points within tol of it). Returns the new list."""
    out = []
    # axis lines: exact grouping by coordinate, interval union
    H = collections.defaultdict(list); V = collections.defaultdict(list); rest = []
    hs = []; vs = []
    for a, b in lines:
        if math.dist(a, b) < 1e-6: continue
        if abs(a[1] - b[1]) <= tol and abs(a[0] - b[0]) > 10 * abs(a[1] - b[1]): hs.append(((a[1] + b[1]) / 2, tuple(sorted((a[0], b[0])))))
        elif abs(a[0] - b[0]) <= tol and abs(a[1] - b[1]) > 10 * abs(a[0] - b[0]): vs.append(((a[0] + b[0]) / 2, tuple(sorted((a[1], b[1])))))
        else: rest.append((tuple(a), tuple(b)))
    # coordinates within tol of each other are one line (dashes printed a quantum apart, floor 5)
    for src, dst in ((hs, H), (vs, V)):
        src.sort(); cur = []
        def flush(cur):
            if not cur: return
            w = [iv[1] - iv[0] for _, iv in cur]; c = sum(v * wi for (v, _), wi in zip(cur, w)) / max(sum(w), 1e-9)
            dst[c].extend(iv for _, iv in cur)
        for v, iv in src:
            if cur and v - cur[-1][0] > tol: flush(cur); cur = []
            cur.append((v, iv))
        flush(cur)
    def union(iv):
        iv = sorted(iv); res = [list(iv[0])]
        for s, e in iv[1:]:
            if s <= res[-1][1] + gap: res[-1][1] = max(res[-1][1], e)
            else: res.append([s, e])
        return res
    for y, iv in H.items():
        for s, e in union(iv): out.append(((s, y), (e, y)))
    for x, iv in V.items():
        for s, e in union(iv): out.append(((x, s), (x, e)))
    if not rest: return out
    # other lines: union-find over touching / overlapping collinear pieces
    n = len(rest); uf = UF(n)
    D = []
    for a, b in rest:
        L = math.dist(a, b); D.append(((b[0] - a[0]) / L, (b[1] - a[1]) / L, L))
    ends = np.array([p for a, b in rest for p in (a, b)])
    tr = cKDTree(ends)
    def coll(i, j):
        ux, uy, _ = D[i]; a = rest[i][0]
        for p in rest[j]:
            if abs((p[0] - a[0]) * uy - (p[1] - a[1]) * ux) > tol: return False
        vx, vy, _ = D[j]; a2 = rest[j][0]
        for p in rest[i]:
            if abs((p[0] - a2[0]) * vy - (p[1] - a2[1]) * vx) > tol: return False
        return True
    for i, j in tr.query_pairs(gap + 1e-6):
        i_, j_ = i // 2, j // 2
        if i_ != j_ and coll(i_, j_): uf.u(i_, j_)
    # overlaps without shared end points (a piece lying inside another): midpoints near a line
    try:
        from shapely.strtree import STRtree
        from shapely.geometry import LineString
        G = [LineString(r) for r in rest]; st = STRtree(G)
        for i, g in enumerate(G):
            for j in st.query(g.buffer(tol)):
                j = int(j)
                if j <= i or uf.f(i) == uf.f(j): continue
                if coll(i, j) and g.distance(G[j]) <= gap: uf.u(i, j)
    except Exception:
        pass
    grp = collections.defaultdict(list)
    for i in range(n): grp[uf.f(i)].append(i)
    for g in grp.values():
        if len(g) == 1: out.append(rest[g[0]]); continue
        P_ = np.array([p for i in g for p in rest[i]])
        c = P_.mean(0); u = np.linalg.svd(P_ - c)[2][0]
        t = (P_ - c) @ u; lo, hi = t.argmin(), t.argmax()
        a, b = c + t[lo] * u, c + t[hi] * u
        # one line only if the union of the pieces has no hole
        iv = sorted(tuple(sorted(((np.array(rest[i][0]) - c) @ u, (np.array(rest[i][1]) - c) @ u))) for i in g)
        pieces = union(iv)
        for s, e in pieces: out.append((tuple(c + s * u), tuple(c + e * u)))
    return out
