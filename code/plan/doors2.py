# Door swings: arcs built from chains of polyline pieces / Bezier curves, circle fit, leaf = lone line hinge->arc end.
# Output doors.json: hinge c, R (pt), leaf end, closed end, arc prim ids, leaf prim id, sweep (deg).
from common import *
import json, collections
P = load(); cls = pickle.load(open('cls.pkl', 'rb'))
OK = ('obj', 'wall')
def bpts(g, n=10): return bez(g, n)
segs = []   # (prim, a, b, dir_a (unit, pointing into seg), dir_b (unit, pointing out of seg), samples, kind)
def unit(v):
    n = math.hypot(*v); return (v[0] / n, v[1] / n) if n > 1e-9 else (0.0, 0.0)
for i, p in enumerate(P):
    if cls[i] not in OK: continue
    if p[0] == 'l':
        a, b = p[4]; L = math.dist(a, b)
        if 0.9 <= L <= 7.5:
            d = unit((b[0] - a[0], b[1] - a[1])); segs.append((i, a, b, d, d, [a, b], 'l', L))
    elif p[0] == 'c':
        g = p[4]; s = bpts(g, 12)
        L = sum(math.dist(u, v) for u, v in zip(s, s[1:]))
        if 1.0 <= L <= 40:
            segs.append((i, g[0], g[3], unit((s[1][0] - s[0][0], s[1][1] - s[0][1])), unit((s[-1][0] - s[-2][0], s[-1][1] - s[-2][1])), s, 'c', L))
G = 0.06
grid = collections.defaultdict(list)
def gk(p): return (int(math.floor(p[0] / G)), int(math.floor(p[1] / G)))
for j, s in enumerate(segs):
    for e, pnt in ((0, s[1]), (1, s[2])): grid[gk(pnt)].append((j, e))
def near(pnt):
    x, y = gk(pnt); out = []
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1): out += grid.get((x + dx, y + dy), [])
    return [(j, e) for j, e in out if math.dist(segs[j][1 if e == 0 else 2], pnt) <= 0.07]
def turn(d1, d2): return math.degrees(math.atan2(d1[0] * d2[1] - d1[1] * d2[0], d1[0] * d2[0] + d1[1] * d2[1]))
used = set(); chains = []
for j0 in range(len(segs)):
    if j0 in used: continue
    chain = [(j0, False)]; used.add(j0); sign = 0
    for side in (1, 0):   # grow forward from end, then backward from start
        while True:
            jl, rev = chain[-1] if side == 1 else chain[0]
            s = segs[jl]
            if side == 1:
                pnt = s[1] if rev else s[2]; dout = (-s[3][0], -s[3][1]) if rev else s[4]
            else:
                pnt = s[2] if rev else s[1]; dout = (-s[4][0], -s[4][1]) if rev else (-s[3][0], -s[3][1])
            best = None
            for k, e in near(pnt):
                if k in used: continue
                t = segs[k]
                din = t[3] if e == 0 else (-t[4][0], -t[4][1])
                tt = turn(dout, din)
                if abs(tt) > 40: continue
                if sign and abs(tt) > 2 and (tt > 0) != (sign > 0): continue
                if s[6] == 'l' and t[6] == 'l' and not (0.4 <= t[7] / s[7] <= 2.5): continue
                if best is None or abs(tt) < abs(best[2]): best = (k, e, tt)
            if best is None: break
            k, e, tt = best
            if abs(tt) > 2 and not sign: sign = 1 if tt > 0 else -1
            used.add(k)
            if side == 1: chain.append((k, e == 1))
            else: chain.insert(0, (k, e == 0))
    if len(chain) >= 2 or segs[chain[0][0]][6] == 'c': chains.append(chain)
def samples(chain):
    out = []
    for j, rev in chain:
        s = segs[j][5]; s = s[::-1] if rev else s
        out += s if not out else s[1:]
    return out
def fit(ps):
    A = np.array([[x, y, 1.0] for x, y in ps]); bb = np.array([-(x * x + y * y) for x, y in ps])
    try: sol = np.linalg.lstsq(A, bb, rcond=None)[0]
    except Exception: return None
    cx, cy = -sol[0] / 2, -sol[1] / 2; r2 = cx * cx + cy * cy - sol[2]
    if r2 <= 0: return None
    R = math.sqrt(r2); dev = [abs(math.dist((cx, cy), p) - R) for p in ps]
    return (cx, cy), R, max(dev), math.sqrt(sum(d * d for d in dev) / len(dev))
arcs = []
for ch in chains:
    ps = samples(ch)
    if len(ps) < 4: continue
    f = fit(ps)
    if not f: continue
    c, R, mx, rms = f
    # Revit tessellates arcs with vertices ON the circle: an end piece whose far vertex is off the circle is a
    # jamb/partition stub that continued the chain tangentially -> drop it and refit
    for _ in range(4):
        if len(ch) < 2: break
        e0 = ps[0]; e1 = ps[-1]
        d0 = abs(math.dist(c, e0) - R); d1 = abs(math.dist(c, e1) - R)
        if max(d0, d1) <= 0.06: break
        ch = ch[1:] if d0 >= d1 else ch[:-1]
        ps = samples(ch)
        if len(ps) < 4: break
        f = fit(ps)
        if not f: break
        c, R, mx, rms = f
    if len(ps) < 4 or not (5 <= R <= 32) or mx > 0.35 or rms > 0.12: continue
    a0 = math.atan2(ps[0][1] - c[1], ps[0][0] - c[0]); a1 = math.atan2(ps[-1][1] - c[1], ps[-1][0] - c[0])
    sweep = abs((math.degrees(a1 - a0) + 180) % 360 - 180)
    if not (35 <= sweep <= 100): continue
    arcs.append(dict(c=c, R=R, p0=ps[0], p1=ps[-1], arc=[segs[j][0] for j, _ in ch], sweep=sweep, rms=rms))
print('chains', len(chains), 'arcs', len(arcs))
# leaves
LN = [(i, P[i][4]) for i, p in enumerate(P) if p[0] == 'l' and cls[i] in OK and math.dist(*p[4]) > 3]
from shapely.strtree import STRtree
from shapely.geometry import LineString, Point
LG = [LineString(g) for _, g in LN]; tree = STRtree(LG)
def lone(k):
    i, (a, b) = LN[k]; d = unit((b[0] - a[0], b[1] - a[1])); L = math.dist(a, b)
    for m in tree.query(LG[k].buffer(0.8)):
        if m == k: continue
        _, (u, v) = LN[m]; e = unit((v[0] - u[0], v[1] - u[1]))
        if abs(d[0] * e[1] - d[1] * e[0]) > 0.035: continue
        # projection overlap
        t = sorted([((u[0] - a[0]) * d[0] + (u[1] - a[1]) * d[1]), ((v[0] - a[0]) * d[0] + (v[1] - a[1]) * d[1])])
        ov = min(L, t[1]) - max(0, t[0])
        off = abs((u[0] - a[0]) * d[1] - (u[1] - a[1]) * d[0])
        if ov > 0.5 * L and off <= 0.8: return False
    return True
doors = []
for d in arcs:
    c, R = d['c'], d['R']; cand = {}
    for k in tree.query(Point(c).buffer(0.8)):
        i, (a, b) = LN[k]
        for u, v in ((a, b), (b, a)):
            if math.dist(u, c) > 0.7 or abs(math.dist(v, c) - R) > 1.2: continue
            for end in ('p0', 'p1'):
                if math.dist(v, d[end]) < 1.3: cand.setdefault(end, []).append((k, lone(k)))
    pick = None
    for end in ('p0', 'p1'):
        for k, ln in cand.get(end, []):
            if ln and (pick is None or not pick[2]): pick = (end, k, True)
            elif pick is None: pick = (end, k, False)
    # floor 5: the panel is drawn closed in the opening (a thick rectangle = several parallel lines, never lone) and
    #   the open leaf is a thin lone line whose start is up to 1 pt off the fitted arc centre (the arc is not centred
    #   exactly on the hinge). A lone line to the OTHER arc end beats a non-lone pick (leaf and closed end swap);
    #   a second lone line to the same end changes nothing (floors 3-4: leaves drawn as thin double lines).
    if pick is not None and not pick[2]:
        for k in tree.query(Point(c).buffer(1.1)):
            i, (a, b) = LN[k]
            for u, v in ((a, b), (b, a)):
                if math.dist(u, c) > 1.0 or abs(math.dist(v, c) - R) > 1.2: continue
                for end in ('p0', 'p1'):
                    if end != pick[0] and math.dist(v, d[end]) < 1.3 and lone(k): pick = (end, k, True)
    if pick is None: print('no leaf', [round(v, 1) for v in c], round(R * MM_PER_PT)); continue
    end, k, ln = pick
    if not ln and len(cand) == 2: print('ambiguous leaf', [round(v, 1) for v in c])
    i, (a, b) = LN[k]; far = a if math.dist(a, c) > math.dist(b, c) else b
    other = 'p1' if end == 'p0' else 'p0'
    d.update(leaf=i, leaf_end=far, closed=d[other], lone=ln)
    doors.append(d)
json.dump(doors, open('doors.json', 'w'))
print('doors', len(doors), collections.Counter(round(x['R'] * MM_PER_PT, -1) for x in doors))
