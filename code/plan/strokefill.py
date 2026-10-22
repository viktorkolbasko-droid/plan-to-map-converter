# Revit prints the solid fill of a rotated region as dense parallel strokes (0.24 pt wide, 0.12-0.24 pt apart).
# Restore every such group as ONE fill polygon; absorb the micro-lines and fill slices lying inside it.
# In: prims.pkl (extract2.py). Out: seq.pkl (used by every later step), strokefill.json (report).
import pickle, math, json, collections, os, shutil
import numpy as np
from shapely.geometry import LineString, Polygon, box
from shapely.ops import unary_union
from shapely.strtree import STRtree
P = pickle.load(open('prims.pkl', 'rb'))          # raw extraction (extract2.py); result goes to seq.pkl
# white strokes are Revit print masks (they blank out parts of the lines below them), not geometry: invisible on
#   paper, but a DXF/SVG line would be visible. They still count as cover in the hidden-fill test (stage 3), then are
#   dropped from seq.pkl. Floor 3 has none; floor 4 has 12 thousand.
WHITE = set(i for i, p in enumerate(P) if p[0] in ('l', 'c') and p[2] == (1.0, 1.0, 1.0))
MINLEN, GAP, MINN, MINW = 1.5, 0.30, 8, 1.2
def dark(c): return c is not None and max(c) < 0.5
# stroke colour of a printed solid: black/dark as on floor 3, or neutral grey up to 0.8 (floor 4: grey 0.67 convectors
# of the other tenant's zone). Checked: floor 3 has no grey groups, its result is unchanged.
def solid_stroke(c): return c is not None and (max(c) < 0.5 or (c[0] == c[1] == c[2] and c[0] <= 0.8))
cand = [i for i, p in enumerate(P) if p[0] == 'l' and solid_stroke(p[2]) and math.dist(*p[4]) >= MINLEN]
angs = []
for i in cand:
    (a, b) = P[i][4]
    ang = math.degrees(math.atan2(b[1] - a[1], b[0] - a[0])) % 180
    if ang > 179.5: ang -= 180
    angs.append((ang, i))
angs.sort()
byang = []; cur_ = []
for ang, i in angs:
    if cur_ and ang - cur_[-1][0] > 0.4: byang.append(cur_); cur_ = []
    cur_.append((ang, i))
if cur_: byang.append(cur_)
groups = []
for grp_ in byang:
    ids = [i for _, i in grp_]
    th = math.radians(sum(a for a, _ in grp_) / len(grp_)); d = (math.cos(th), math.sin(th)); nrm = (-d[1], d[0])
    rec = []
    for i in ids:
        a, b = P[i][4]
        off = a[0] * nrm[0] + a[1] * nrm[1]
        t0, t1 = sorted([a[0] * d[0] + a[1] * d[1], b[0] * d[0] + b[1] * d[1]])
        rec.append((off, t0, t1, i))
    rec.sort()
    # graph: neighbours = offset within GAP and spans overlapping >= 50 % of the shorter; groups = components
    par = list(range(len(rec)))
    def fd(x):
        while par[x] != x: par[x] = par[par[x]]; x = par[x]
        return x
    for x in range(len(rec)):
        y = x + 1
        while y < len(rec) and rec[y][0] - rec[x][0] <= GAP:
            lo = max(rec[x][1], rec[y][1]); hi = min(rec[x][2], rec[y][2])
            if hi - lo >= 0.5 * min(rec[x][2] - rec[x][1], rec[y][2] - rec[y][1]): par[fd(x)] = fd(y)
            y += 1
    comp = collections.defaultdict(list)
    for x in range(len(rec)): comp[fd(x)].append(rec[x])
    for cc in comp.values():
        if len(cc) < MINN: continue
        med = sorted(r[2] - r[1] for r in cc)[len(cc) // 2]
        cc = [r for r in cc if abs((r[2] - r[1]) - med) <= 0.25 * med]   # a long neighbour line (room boundary) is not part of the fill
        offs = [r[0] for r in cc]
        if len(cc) >= MINN and max(offs) - min(offs) >= MINW: groups.append([r[3] for r in cc])
print('stroke-fill groups', len(groups))
# stage 2: axis-aligned solids printed as stacks of thin fill slices (<= 0.13 pt) of one colour
slices = collections.defaultdict(list)
for i, p in enumerate(P):
    if p[0] != 'qu' or not dark(p[3]) or len(p[4]) < 3: continue
    xs = [a for a, b in p[4]]; ys = [b for a, b in p[4]]
    if min(max(xs) - min(xs), max(ys) - min(ys)) <= 0.13: slices[p[3]].append(i)
sgroups = []
for colr, ids in slices.items():
    gs = [Polygon(P[i][4]).buffer(0.02) for i in ids]
    u = unary_union(gs); comps_ = list(getattr(u, 'geoms', [u]))
    t = STRtree(gs)
    for cpt in comps_:
        mem = [ids[j] for j in t.query(cpt, predicate='intersects')]
        if len(mem) < 5: continue
        r = cpt.minimum_rotated_rectangle; xy = list(r.exterior.coords)
        e = sorted([math.dist(xy[0], xy[1]), math.dist(xy[1], xy[2])])
        if e[0] < 1.0: continue
        sgroups.append((mem, cpt.buffer(-0.02).simplify(0.02), colr))
print('slice solids', len(sgroups))

polys = []
for g in groups:
    u = unary_union([LineString(P[i][4]).buffer(max(P[i][1], 0.24) / 2 + 0.02, cap_style=2) for i in g])
    u = u.buffer(0.06).buffer(-0.06)
    if u.geom_type != 'Polygon': u = max(getattr(u, 'geoms', [u]), key=lambda x: x.area)
    polys.append(u.simplify(0.02))
# absorb micro strokes and slices inside each solid polygon
geoms = []
for p in P:
    if p[0] == 'qu': geoms.append(Polygon(p[4]) if len(p[4]) >= 3 else LineString(p[4]))
    elif p[0] == 'c': geoms.append(LineString([p[4][0], p[4][3]]))
    else: geoms.append(LineString(p[4]))
tree = STRtree(geoms)
drop = set(); newp = []; rep = []
ALL = [(g, poly, None) for g, poly in zip(groups, polys)] + [(m, pl, c) for m, pl, c in sgroups]
for g, poly, fcol in ALL:
    zone = poly.buffer(0.15)
    mem = set(g)
    col = fcol if fcol is not None else collections.Counter(P[i][2] for i in g).most_common(1)[0][0]
    for j in tree.query(zone, predicate='contains'):
        p = P[j]
        if p[0] == 'l' and (dark(p[2]) or p[2] == col): mem.add(int(j))      # the group's own colour too (grey solids)
        elif p[0] == 'qu' and (dark(p[3]) or p[3] == col): mem.add(int(j))
    if poly.geom_type != 'Polygon': poly = max(getattr(poly, 'geoms', [poly]), key=lambda x: x.area)
    drop |= mem
    ext = [tuple(map(float, c)) for c in list(poly.exterior.coords)[:-1]]
    seq = min(P[i][5] if not isinstance(P[i][5], tuple) else P[i][5][0] for i in g)
    newp.append(('qu', 0, None, tuple(col), tuple(ext), ('sf', len(newp))))
    b = poly.bounds
    rep.append(dict(kind='strokes' if fcol is None else 'slices', col=col, n=len(g), absorbed=len(mem), bb=[round(v, 2) for v in b], area=round(poly.area, 2), seq=seq))
# stage 3: thin fills that are invisible in the source (>= 95 % covered by strokes painted after them) are not reproduced
def seqof(p):
    s_ = p[5]
    return s_[0] if isinstance(s_, tuple) and isinstance(s_[0], (int, float)) else (s_ if isinstance(s_, (int, float)) else 10**9)
SL = [(i, LineString(p[4]).buffer(max(p[1], 0.24) / 2, cap_style=2)) for i, p in enumerate(P) if p[0] == 'l' and i not in drop]
st = STRtree([g for _, g in SL])
hidden = 0
for i, p in enumerate(P):
    if p[0] != 'qu' or i in drop or p[3] is None or p[3] == (1.0, 1.0, 1.0) or len(p[4]) < 3: continue
    g = Polygon(p[4])
    if not g.is_valid: g = g.buffer(0)
    if g.is_empty: continue
    r = g.minimum_rotated_rectangle; xy = list(r.exterior.coords)
    if min(math.dist(xy[0], xy[1]), math.dist(xy[1], xy[2])) > 0.6: continue
    sq = seqof(p)
    cov = [SL[j][1] for j in st.query(g) if seqof(P[SL[j][0]]) > sq]
    if cov and g.difference(unary_union(cov)).area <= 0.05 * g.area:
        drop.add(i); hidden += 1
print('hidden thin fills dropped', hidden)
out = [p for i, p in enumerate(P) if i not in drop and i not in WHITE]
print('white mask strokes dropped', len(WHITE - drop))
# insert the solid polygons in paint order next to their first stroke
def sk(p):
    s = p[5]
    if isinstance(s, tuple): return s[0] + 0.5 if isinstance(s[0], (int, float)) else rep[s[1]]['seq']
    return s
out += newp
out.sort(key=sk)
pickle.dump((out, []), open('seq.pkl', 'wb'))
json.dump(rep, open('strokefill.json', 'w'), indent=0)
print('solids', len(newp), 'prims dropped', len(drop), 'prims', len(P), '->', len(out))
print(collections.Counter((r['kind'], r['col']) for r in rep))
for r in sorted(rep, key=lambda r: -r['area'])[:12]: print(r)
