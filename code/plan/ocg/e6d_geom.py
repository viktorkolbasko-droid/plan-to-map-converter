"""Э6г (owner 06.10.2026): geometry of openings, niches and joints, before the objects (Э7).
 1. Doors — one look for every door (test 10: the pieces of one swing — one centre and radius, touching spans — are one
    arc, merge_arcs). The opening of a door is the gap in its wall or partition between the ends of the
    elements on both sides (wall bodies, glass panes). Its contour is two lines on the faces of the wall from end to end.
    Lines of the wall layers that run through the opening are that contour: their pieces inside the opening go to the
    layer «Двери» (they become the door's, not the wall's); where the opening is empty the contour is added (synthetic).
    The wall and the glass are cut in the opening (owner row 172: at a door the wall breaks).
 2. Niches — a screen on a wall cannot be closed by the wall on both sides: it stands in a niche. Lines of the wall
    layers across the niche in front of the screen go to the screen's layer «Оборудование»; a wall body in front of it
    is cut.
Reads walls_clean.pkl (Э6в) or walls.pkl, prims.pkl. Writes walls_geom.pkl (same structure), prims_geom.pkl (prims with
the split pieces, kind 'removed' for the originals, 'layer0' = the source layer of a moved piece, 'synthetic' for added
lines) and geom_report.json. usage: python3 e6d_geom.py   (in the sheet folder, after e6c_clean.py)"""
import pickle, json, math, collections, time, sys, os
import numpy as np, shapely
from shapely.geometry import LineString, Polygon, MultiPolygon, Point, box
from shapely.ops import unary_union
import os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import sheet; from e7_comp import geom
t0 = time.time(); K = sheet.K
def T(): return f'{time.time() - t0:.1f} s'
WSRC = 'walls_clean.pkl' if os.path.exists('walls_clean.pkl') else 'walls.pkl'
W = pickle.load(open(WSRC, 'rb')); B = [list(cg) for cg in W['bodies']]
D0 = pickle.load(open('prims.pkl', 'rb')); P = D0['P']
WALL_L = sheet.L('wall'); WALL_ALL = WALL_L | sheet.L('core')
GLASS = sheet.GLASS; EQ_L = sheet.L('equipment'); EQ_LAYER = sheet.L1('equipment'); DOOR_L = sheet.L('door'); DOOR_LAYER = sheet.L1('door')
rep = collections.Counter(); places = collections.defaultdict(list)
def live(p): return p['kind'] != 'removed'
def parts(x, kind):
    return [q for q in getattr(x, 'geoms', [x]) if q.geom_type == kind and (q.length > 1e-3 if kind == 'LineString' else q.area > 1e-4)]
class Frame:
    def __init__(s, o, u):
        s.o = np.array(o, float); s.u = np.array(u, float) / np.linalg.norm(u); s.n = np.array([-s.u[1], s.u[0]])
    def loc(s, xy): d = np.asarray(xy, float) - s.o; return d @ s.u, d @ s.n
    def w(s, a, b): return tuple(s.o + a * s.u + b * s.n)
    def rect(s, a0, a1, b0, b1): return Polygon([s.w(a0, b0), s.w(a1, b0), s.w(a1, b1), s.w(a0, b1)])
def comps(ids, tol):
    gs = [geom(P[i]) for i in ids]; t = shapely.STRtree(gs); par = list(range(len(ids)))
    def f(a):
        while par[a] != a: par[a] = par[par[a]]; a = par[a]
        return a
    for a, g in enumerate(gs):
        for b in t.query(g.buffer(tol)):
            if b > a and gs[b].distance(g) <= tol: par[f(a)] = f(b)
    out = collections.defaultdict(list)
    for a, i in enumerate(ids): out[f(a)].append(i)
    return list(out.values())
def arc_fit(i, min_sw=30):
    q = np.array(P[i]['p'], float)
    if P[i]['kind'] != 'line' or len(q) < 8: return None    # an arc is drawn by many short steps (a rectangle is cyclic too)
    A = np.c_[2 * q[:, 0], 2 * q[:, 1], np.ones(len(q))]; c = np.linalg.lstsq(A, (q ** 2).sum(1), rcond=None)[0]
    r2 = c[2] + c[0] ** 2 + c[1] ** 2
    if r2 <= 0: return None
    r = math.sqrt(r2); res = np.abs(np.hypot(q[:, 0] - c[0], q[:, 1] - c[1]) - r).max()
    if res > 0.3 or not (5 <= r <= 40): return None
    a = np.unwrap(np.arctan2(q[:, 1] - c[1], q[:, 0] - c[0])); sw = abs(math.degrees(a[-1] - a[0]))
    if sw < min_sw or sw > 200 or np.abs(np.degrees(np.diff(a))).max() > 20: return None
    mid = q[len(q) // 2]
    return dict(i=i, c=np.array([c[0], c[1]]), r=r, sw=sw, e0=q[0], e1=q[-1], mid=mid)
def split_line(i, region, new_layer=None, flag=None):
    """split line prim i by region: pieces inside get new_layer (layer0 = source layer) and the flag; returns ids inside"""
    p = P[i]; g = LineString(p['p'])
    pi = parts(g.intersection(region), 'LineString'); po = parts(g.difference(region), 'LineString')
    if not pi: return []
    if not po and new_layer is None: return [i]
    ins = []
    for q in pi:
        r = dict(p); r['p'] = [tuple(map(float, c)) for c in q.coords]; r['id'] = len(P); r['src_id'] = p.get('src_id', i)
        if new_layer: r['layer0'] = p.get('layer0', p['layer']); r['layer'] = new_layer
        if flag: r[flag] = True
        P.append(r); ins.append(r['id'])
    for q in po:
        r = dict(p); r['p'] = [tuple(map(float, c)) for c in q.coords]; r['id'] = len(P); r['src_id'] = p.get('src_id', i); P.append(r)
    p['kind'] = 'removed'; p['removed_by'] = flag or 'split'
    return ins
def cut_fill(i, region, flag):
    """glass or wall fill minus region: the remaining pieces are new fills"""
    p = P[i]; g = geom(p); rest = g.difference(region)
    if rest.area >= g.area - 1e-4: return False
    for q in parts(rest, 'Polygon'):
        r = dict(p); r['p'] = [tuple(map(float, c)) for c in q.exterior.coords][:-1]; r['holes'] = [[tuple(map(float, c)) for c in h.coords][:-1] for h in q.interiors]
        r['id'] = len(P); r['src_id'] = p.get('src_id', i); P.append(r)
    p['kind'] = 'removed'; p['removed_by'] = flag
    return True
# index of live wall-layer lines and glass fills (rebuilt after each phase)
def index():
    global WLI, WLG, WLT, GFI, GFG, GFT, BG, BT, SOL, SOLT
    WLI = [p['id'] for p in P if live(p) and p['layer'] in WALL_ALL and p['kind'] == 'line' and len(p['p']) >= 2]
    WLG = [LineString(P[i]['p']) for i in WLI]; WLT = shapely.STRtree(WLG)
    GFI = [p['id'] for p in P if live(p) and p['layer'] in WALL_L and p['kind'] in ('fill', 'wline') and p['col'] in GLASS]
    GFG = [geom(P[i]) for i in GFI]; GFT = shapely.STRtree(GFG) if GFG else None
    BG = [g for _, g in B]; BT = shapely.STRtree(BG)
    SOL = BG + GFG; SOLT = shapely.STRtree(SOL)
index()
# ======================================================================================== 2. niches (before the doors)
def niches():
    eq = [p['id'] for p in P if live(p) and p['layer'] in EQ_L]
    for c in comps(eq, 1.0):
        fills = [geom(P[i]) for i in c if P[i]['kind'] == 'fill' and max(P[i]['col']) > 0.5 and P[i]['col'][0] > 0.8]
        if not fills: continue
        E = unary_union(fills); r = E.minimum_rotated_rectangle; cc = np.array(r.exterior.coords)[:4]
        e1 = cc[1] - cc[0]; e2 = cc[2] - cc[1]
        if np.linalg.norm(e2) > np.linalg.norm(e1): e1, e2 = e2, e1
        F = Frame(E.centroid.coords[0], e1)
        js = [j for j in BT.query(E.buffer(1.5)) if BG[j].distance(E) <= 1.0]
        if not js: rep['ниша: экран не у стены'] += 1; continue
        # the room side: where the view lines of the screen go; else the side with less wall
        lines = [P[i] for i in c if P[i]['kind'] == 'line']
        sgn = 0.0
        for p in lines:
            for xy in p['p']: sgn += F.loc(xy)[1]
        if abs(sgn) < 1e-6:
            bu = unary_union([BG[j] for j in js]); ex = [F.loc(xy) for xy in np.array(E.exterior.coords)]
            s0 = min(a for a, _ in ex); s1 = max(a for a, _ in ex)
            sgn = bu.intersection(F.rect(s0, s1, -3, 0)).area - bu.intersection(F.rect(s0, s1, 0, 3)).area
        if sgn < 0: F = Frame(F.o, -F.u)                       # n points to the room
        ex = [F.loc(xy) for q in getattr(E, 'geoms', [E]) for xy in np.array(q.exterior.coords)]
        s_lo = min(a for a, _ in ex); s_hi = max(a for a, _ in ex); t_fr = max(b for _, b in ex)
        bu = unary_union([BG[j] for j in js])
        # the niche opening: the void just behind the front face, around the screen
        V = F.rect(s_lo - 4, s_hi + 4, t_fr - 0.35, t_fr - 0.05).difference(bu)
        vs = [v for v in parts(V, 'Polygon') if v.intersects(F.rect(s_lo, s_hi, t_fr - 0.35, t_fr - 0.05))]
        if not vs: rep['ниша: нет проёма за экраном'] += 1; continue
        a = min(F.loc(xy)[0] for v in vs for xy in v.exterior.coords); b = max(F.loc(xy)[0] for v in vs for xy in v.exterior.coords)
        front = F.rect(a - 0.02, b + 0.02, t_fr - 0.3, t_fr + 1.2)
        # wall bodies in front of the screen: cut
        cut = 0.0
        for j in js:
            x = B[j][1].intersection(F.rect(a, b, t_fr + 0.02, t_fr + 1.2))
            if x.area > 0.01:
                B[j][1] = B[j][1].difference(F.rect(a, b, t_fr + 0.02, t_fr + 1.2)); cut += x.area
        # lines of the wall layers across the niche: to the screen
        moved = 0.0
        for k in WLT.query(front):
            i = WLI[k]
            if not live(P[i]): continue
            g = WLG[k]; x = g.intersection(front)
            for q in parts(x, 'LineString'):
                d = np.array(q.coords[-1]) - np.array(q.coords[0]); L = np.linalg.norm(d)
                if L < 0.5 * (b - a) or abs(d @ F.u) / L < 0.98: continue
                ids = split_line(i, front, EQ_LAYER, 'niche_front'); moved += sum(LineString(P[n]['p']).length for n in ids)
                break
        rep['ниши: экранов у стены'] += 1
        if moved: rep['ниши: линия стены перед экраном → экрану'] += 1
        if cut: rep['ниши: тело стены перед экраном вырезано'] += 1
        places['niches'].append(dict(at=[round(v, 1) for v in E.centroid.coords[0]], opening_mm=round((b - a) * K), screen_mm=round((s_hi - s_lo) * K),
                                     line_moved_pt=round(moved, 2), body_cut_pt2=round(cut, 3)))
niches(); index()
print('niches', dict((k, v) for k, v in rep.items() if k.startswith('ниш')), T())
# ======================================================================================== 1. doors
def leaf_of(c, H, r):
    """the door's leaf: a line with a vertex at the hinge (<= 2 pt) and one at >= 0.6 r from it"""
    out = []
    for i in c:
        if P[i]['kind'] != 'line': continue
        d = [np.linalg.norm(np.array(xy, float) - H) for xy in P[i]['p']]
        if min(d) <= 2.0 and max(d) >= 0.6 * r: out.append(i)
    return out
ARC_CENTRE_MM = 48.04   # test 10 (v009: 1 pt at 48.04 mm/pt, exactly - step 8): the centres of the pieces of one swing; in pt of the sheet - / K
def merge_arcs(arcs):
    """test 10: one swing drawn as several pieces (an arc split by a crossing line) is one arc — the pieces of one centre
    (<= ARC_CENTRE_MM, 48 mm; code 012: in mm through the scale of the sheet, sheet.K) and radius (<= 5 %) whose angular
    spans touch (<= 12°) are joined: the ends are the extreme ones, the sweep
    the total, the middle — on the circle at the middle angle; 'ii' — the ids of all pieces. Without it a piece's end was
    taken for the closed leaf's end: the opening ran along a radius of the swing (a frame at an angle to the wall) and a
    second piece of the same swing made a phantom door"""
    out = []; used = set()
    for x, a in enumerate(arcs):
        if x in used: continue
        grp = [a]; used.add(x); grew = True
        while grew:
            grew = False
            for y, b in enumerate(arcs):
                if y in used: continue
                if any(np.linalg.norm(b['c'] - g['c']) <= ARC_CENTRE_MM / K and abs(b['r'] - g['r']) <= 0.05 * max(b['r'], g['r']) for g in grp):
                    grp.append(b); used.add(y); grew = True
        if len(grp) == 1: out.append(a); continue
        c = np.mean([g['c'] for g in grp], 0); r = float(np.mean([g['r'] for g in grp]))
        iv = []
        for g in grp:
            a0 = math.atan2(g['e0'][1] - c[1], g['e0'][0] - c[0]); am = math.atan2(g['mid'][1] - c[1], g['mid'][0] - c[0]); a1 = math.atan2(g['e1'][1] - c[1], g['e1'][0] - c[0])
            d1 = (am - a0 + math.pi) % (2 * math.pi) - math.pi; d2 = (a1 - am + math.pi) % (2 * math.pi) - math.pi
            lo, hi = (a0, a0 + d1 + d2) if d1 + d2 >= 0 else (a0 + d1 + d2, a0)
            iv.append([lo, hi])
        ref = iv[0][0]
        for v in iv:                                        # into one window around the first piece
            while v[0] - ref > math.pi: v[0] -= 2 * math.pi; v[1] -= 2 * math.pi
            while ref - v[0] > math.pi: v[0] += 2 * math.pi; v[1] += 2 * math.pi
        iv.sort(); runs = [list(iv[0])]
        for v in iv[1:]:
            if v[0] <= runs[-1][1] + math.radians(12): runs[-1][1] = max(runs[-1][1], v[1])
            else: runs.append(list(v))
        if len(runs) > 1: out += grp; continue               # pieces of one circle that do not touch: left as they are
        lo, hi = runs[0]; sw = math.degrees(hi - lo)
        if sw > 200: out += grp; continue
        def pt(t): return np.array([c[0] + r * math.cos(t), c[1] + r * math.sin(t)])
        out.append(dict(i=grp[0]['i'], ii=[g['i'] for g in grp], c=c, r=r, sw=sw, e0=pt(lo), e1=pt(hi), mid=pt((lo + hi) / 2)))
        rep['двери: дуга из кусков — одна дуга'] += 1
    return out
def units(c):
    """doors in a component of the layer «Двери»: arcs paired into double doors (radii within 25 %, hinges r1 + r2 apart,
    both leaves to one side), the rest single"""
    # pieces of a swing may be short (an arc split near its end): fitted from 5°, kept as arcs from 30° after the merge
    arcs = sorted([a for a in merge_arcs([a for a in (arc_fit(i, 5) for i in c) if a]) if a['sw'] >= 30], key=lambda a: -a['r']); used = set(); out = []
    for x in range(len(arcs)):
        if x in used: continue
        for y in range(x + 1, len(arcs)):
            if y in used: continue
            a_, b_ = arcs[x], arcs[y]; d = np.linalg.norm(a_['c'] - b_['c'])
            if b_['r'] < 0.4 * a_['r'] or not (0.8 <= d / (a_['r'] + b_['r']) <= 1.25): continue     # leaves 1000 + 500 too
            F = Frame(a_['c'], b_['c'] - a_['c'])
            if F.loc(a_['mid'])[1] * F.loc(b_['mid'])[1] <= 0: continue
            out.append(('двупольная', [a_, b_])); used |= {x, y}; break
        if x not in used: out.append(('однопольная', [arcs[x]])); used.add(x)
    return out
def frame_single(c, a0):
    H = a0['c']; r = a0['r']; lv = leaf_of(c, H, r)
    tips = [np.array(xy, float) for i in lv for xy in P[i]['p'] if 0.75 * r <= np.linalg.norm(np.array(xy, float) - H) <= 1.15 * r]
    cands = []
    for S in (a0['e0'], a0['e1']):
        F = Frame(H, S - H)
        if F.loc(a0['mid'])[1] < 0: F.n = -F.n
        L0 = np.linalg.norm(S - H)
        sides = sum(1 for sd in (0, 1) if side_band(F, L0, sd))
        leaf_ok = bool(tips) and min(np.linalg.norm(v - S) for v in tips) > 0.3 * r
        cands.append((sides + (0.5 if leaf_ok else 0), F, L0))
    _, F, L0 = max(cands, key=lambda x: x[0])
    return F, L0, lv
def probe(F, s, tmax=6.0):
    """intervals of t covered by bodies and glass on the line s = const (|t| <= tmax)"""
    seg = LineString([F.w(s, -tmax), F.w(s, tmax)]); out = []
    for k in SOLT.query(seg):
        x = SOL[k].intersection(seg)
        for q in parts(x, 'LineString'):
            ts = sorted(F.loc(xy)[1] for xy in q.coords); out.append((ts[0], ts[-1], k))
    return out
def side_band(F, L0, side):
    """the wall next to the opening on one side: bodies or glass that hold the hinge line (|t| <= 0.6)"""
    for d in (1.2, 1.6, 2.0, 2.5, 3.0, 4.0, 5.0):
        s = -d if side == 0 else L0 + d
        iv = sorted([v for v in probe(F, s) if v[1] - v[0] > 0.15], key=lambda v: v[0])
        if not iv: continue
        grp = []; cur = None
        for v in iv:
            if cur and v[0] <= cur[1] + 0.12: cur = [cur[0], max(cur[1], v[1]), cur[2] + [v]]
            else:
                if cur: grp.append(cur)
                cur = [v[0], v[1], [v]]
        grp.append(cur)
        hit = [g for g in grp if g[0] <= 0.6 and g[1] >= -0.6 and g[0] > -5.95 and g[1] < 5.95]
        # the wall runs along the opening: on its middle line it extends along u at least as far as it is thick
        # (a perpendicular wall or a column at the jamb is thick across and short along)
        hit = [g for g in hit if extent_u(F, s, (g[0] + g[1]) / 2, [v[2] for v in g[2]]) >= min(4.0, 0.8 * (g[1] - g[0]))]
        if hit:
            g = min(hit, key=lambda g: min(abs(g[0]), abs(g[1])))
            return s, g[0], g[1], g[2]
    return None
def extent_u(F, s, t, ks):
    seg = LineString([F.w(s - 12, t), F.w(s + 12, t)]); best = 0.0
    for k in ks:
        for q in parts(SOL[k].intersection(seg), 'LineString'):
            ss = sorted(F.loc(xy)[0] for xy in q.coords)
            if ss[0] - 0.05 <= s <= ss[-1] + 0.05: best = max(best, ss[-1] - ss[0])
    return best
def line_band(F, L0, side):
    """a wall drawn by lines only: two faces (clusters of crossings of the wall-layer lines, 0.35 pt) around the hinge line"""
    for d in (1.2, 1.6, 2.0, 2.5, 3.0, 4.0):
        s = -d if side == 0 else L0 + d
        seg = LineString([F.w(s, -6), F.w(s, 6)]); ts = []
        for k in WLT.query(seg):
            x = WLG[k].intersection(seg)
            for q in getattr(x, 'geoms', [x]):
                if q.geom_type == 'Point': ts.append(F.loc(q.coords[0])[1])
        ts.sort(); cl = []
        for t in ts:
            if cl and t - cl[-1][1] <= 0.35: cl[-1][1] = t
            else: cl.append([t, t])
        bands = [(cl[k][0], cl[k + 1][1]) for k in range(len(cl) - 1) if 0.25 <= cl[k + 1][0] - cl[k][1] <= 8]
        bands = [bd for bd in bands if bd[0] <= 0.6 and bd[1] >= -0.6]
        if bands: return min(bands, key=lambda bd: min(abs(bd[0]), abs(bd[1])))
    return None
def element_end(F, L0, side, s_hit, t, ks):
    """the s of the end of the element hit at s_hit on the face line t (the piece containing s_hit)"""
    seg = LineString([F.w(-L0 - 8, t), F.w(2 * L0 + 8, t)]); best = None
    for k in ks:
        for q in parts(SOL[k].intersection(seg), 'LineString'):
            ss = sorted(F.loc(xy)[0] for xy in q.coords)
            if ss[0] - 0.05 <= s_hit <= ss[-1] + 0.05: best = (ss[0], ss[-1])
    if best is None: return None, False
    if side == 0: return best[1], best[1] > L0 * 0.6          # (end, the element crosses the opening)
    return best[0], best[0] < L0 * 0.4
def frame_noarc(c, others):
    """a door drawn as a leaf without an arc (it may be drawn open at any angle): the leaf base is its end at the wall; the
    opening runs from the base to the far jamb — a small part of the layer «Двери» at 0.55–1.5 leaf lengths from the base
    (in this sheet the far jambs are separate parts); without one, along the wall perpendicular to the leaf"""
    best = None
    for i in c:
        if P[i]['kind'] != 'line': continue
        g = LineString(P[i]['p']); r_ = g.minimum_rotated_rectangle
        if r_.geom_type != 'Polygon': continue
        cc = np.array(r_.exterior.coords)[:4]; e1 = cc[1] - cc[0]; e2 = cc[2] - cc[1]
        if np.linalg.norm(e2) > np.linalg.norm(e1): e1, e2 = e2, e1
        Lf, Wf = np.linalg.norm(e1), np.linalg.norm(e2)
        if 12 <= Lf <= 28 and Wf <= 2.7 and (best is None or Lf > best[0]): best = (Lf, i, cc, e1)
    if best is None: return None
    Lf, i, cc, e1 = best; v = e1 / np.linalg.norm(e1); ctr = cc.mean(0)
    ends = [ctr - v * Lf / 2, ctr + v * Lf / 2]
    rest = [np.array(xy, float) for j in c if j != i for xy in P[j]['p']]          # the hinge jamb is at the base
    if rest: dist = [min(np.linalg.norm(r - e) for r in rest) for e in ends]
    else:
        dist = [min((g.distance(Point(e)) for g in SOL), default=99) for e in ends]
        if min(dist) > 3: dist = [min((g.distance(Point(e)) for g in WLG), default=99) for e in ends]
    base, tip = (ends[0], ends[1]) if dist[0] <= dist[1] else (ends[1], ends[0])
    cands = []
    for k, (oc, oct) in enumerate(others):
        if oc is c: continue
        d = np.linalg.norm(oct - base)
        if 0.55 * Lf <= d <= 1.5 * Lf: cands.append((abs(d - Lf), k, oct))
    if cands:
        _, k, far = min(cands, key=lambda x: x[0])
        # both jambs stand in the wall: the line through their centres runs along it (the leaf base is off it by the leaf)
        hj = [np.array(xy, float) for j in c if j != i for xy in P[j]['p']]
        H = np.mean(hj, 0) if hj and min(np.linalg.norm(x - base) for x in hj) <= 2.0 else base
        F = Frame(H, far - H); L0 = np.linalg.norm(far - H)
        if F.loc(tip)[1] < 0: F.n = -F.n
        return F, L0, [i], others[k][0]
    u = np.array([-v[1], v[0]]); best_f = None
    for sg in (1, -1):
        F = Frame(base, sg * u)
        if F.loc(tip)[1] < 0: F.n = -F.n
        mid = probe(F, Lf / 2); ok = side_band(F, Lf, 0) or line_band(F, Lf, 0)
        free = not any(v_[0] <= 0.6 and v_[1] >= -0.6 for v_ in mid)
        sc = (2 if free else 0) + (1 if ok else 0)
        if best_f is None or sc > best_f[0]: best_f = (sc, F)
    return best_f[1], Lf, [i], None
def door_unit(c, kind, arcs, F, L0, lv):
    arc_ids = [x for a in arcs for x in a.get('ii', [a['i']])]
    hinges = [F.loc(a['c'])[0] for a in arcs] if arcs else [0.0]
    own = [i for i in c if i not in arc_ids and i not in lv]
    jam = [F.loc(xy) for i in own for xy in P[i]['p']]
    near0 = [a for a, b in jam if a <= 2.5 and abs(b) <= 4]; near1 = [a for a, b in jam if a >= L0 - 2.5 and abs(b) <= 4]
    b0 = side_band(F, L0, 0); b1 = side_band(F, L0, 1); how = 'тела/стекло'
    if b0 and b1: t_lo = (b0[1] + b1[1]) / 2; t_hi = (b0[2] + b1[2]) / 2
    elif b0 or b1: bb = b0 or b1; t_lo, t_hi = bb[1], bb[2]
    else:
        l0 = line_band(F, L0, 0); l1 = line_band(F, L0, 1)
        if l0 or l1:
            ls = [x for x in (l0, l1) if x]; t_lo = sum(x[0] for x in ls) / len(ls); t_hi = sum(x[1] for x in ls) / len(ls); how = 'линии стены'
        else:
            tt = [b for a, b in jam if (a <= 2.5 or a >= L0 - 2.5) and abs(b) <= 4]
            if not tt: rep['двери: нет стены и коробки — не тронуты'] += 1; return
            t_lo, t_hi = min(tt), max(tt); how = 'коробка'
    if t_hi - t_lo < 0.3: rep['двери: толщина стены < 15 мм — не тронуты'] += 1; return
    ends = []
    for side, bb in ((0, b0), (1, b1)):
        e = None; crossing = False
        if bb:
            ks = [v[2] for v in bb[3]]
            es = [element_end(F, L0, side, bb[0], t, ks) for t in (t_lo + 0.05, t_hi - 0.05)]
            es = [x for x in es if x[0] is not None]
            if es:
                crossing = any(x[1] for x in es)
                if not crossing: e = max(x[0] for x in es) if side == 0 else min(x[0] for x in es)
        if e is None: e = (min(near0) if near0 else 0.0) if side == 0 else (max(near1) if near1 else L0)
        ends.append((e, crossing, bb is not None))
    c0, c1 = ends[0][0], ends[1][0]
    if c1 - c0 < 0.6 * L0 or c1 - c0 > 1.6 * L0 + 6:
        rep['двери: проём не по полотну — не тронуты'] += 1
        places['doors_skipped'].append(dict(at=[round(v, 1) for v in F.w(L0 / 2, 0)], why='проём не по полотну', c0=round(c0, 2), c1=round(c1, 2), L0=round(L0, 2), ends=ends)); return
    R = F.rect(c0, c1, t_lo - 0.6, t_hi + 0.6); Rc = F.rect(c0 + 0.02, c1 - 0.02, t_lo - 0.6, t_hi + 0.6)
    bcut = 0.0
    for j in BT.query(R):
        x = B[j][1].intersection(Rc)
        if x.area > 0.01: B[j][1] = B[j][1].difference(Rc); bcut += x.area
    gcut = 0
    if GFT is not None:
        for k in GFT.query(R):
            i = GFI[k]
            if live(P[i]) and cut_fill(i, Rc, 'door_gap'): gcut += 1
    Rin = F.rect(c0 + 0.02, c1 - 0.02, t_lo - 0.45, t_hi + 0.45); cov = {0: [], 1: []}; moved = 0
    for k in WLT.query(Rin):
        i = WLI[k]
        if not live(P[i]): continue
        ok = False
        for q in parts(WLG[k].intersection(Rin), 'LineString'):
            d = np.array(q.coords[-1]) - np.array(q.coords[0]); L = np.linalg.norm(d)
            if L >= 1.0 and abs(d @ F.u) / L >= 0.98: ok = True
        if not ok: continue
        for n in split_line(i, Rin, DOOR_LAYER, 'door_contour'):
            g = LineString(P[n]['p']); tm = F.loc(g.interpolate(0.5, normalized=True).coords[0])[1]
            side = 0 if abs(tm - t_lo) <= abs(tm - t_hi) else 1
            if min(abs(tm - t_lo), abs(tm - t_hi)) <= 0.45: cov[side].append(g)
            moved += 1
    added = 0; seq = P[(arc_ids or lv or c)[0]]['seq']
    for side, t in ((0, t_lo), (1, t_hi)):
        span = F.rect(c0, c1, t - 0.45, t + 0.45)
        got = unary_union([g.intersection(span) for g in cov[side]]).length if cov[side] else 0.0
        if got < 0.8 * (c1 - c0):
            P.append(dict(id=len(P), layer=DOOR_LAYER, kind='line', col=(0.0, 0.0, 0.0), p=[F.w(c0, t), F.w(c1, t)], w=0, seq=seq, alpha=1.0,
                          synthetic=True)); added += 1
    rep['двери: обработано'] += 1; rep[f'двери: {kind}'] += 1; rep[f'двери: стена найдена по: {how}'] += 1
    if moved: rep['двери: контур был в исходнике → двери'] += 1
    if added == 2: rep['двери: контур добавлен (проём был пуст)'] += 1
    elif added == 1: rep['двери: добавлена одна линия контура'] += 1
    if bcut: rep['двери: тело стены разорвано в проёме'] += 1
    if gcut: rep['двери: стекло разорвано в проёме'] += 1
    if any(e[1] for e in ends): rep['двери: стена шла через проём'] += 1
    places['doors'].append(dict(at=[round(v, 1) for v in F.w((c0 + c1) / 2, (t_lo + t_hi) / 2)], kind=kind, wall_by=how,
                                opening_mm=round((c1 - c0) * K), wall_mm=round((t_hi - t_lo) * K), moved_lines=moved, added_lines=added,
                                body_cut_pt2=round(bcut, 3), glass_cut=gcut, crossing=[e[1] for e in ends], wall_on_sides=[e[2] for e in ends],
                                frame=[[round(v, 3) for v in F.o], [round(v, 4) for v in F.u], [round(v, 4) for v in F.n], round(c0, 3), round(c1, 3), round(t_lo, 3), round(t_hi, 3)]))
def doors():
    dl = [p['id'] for p in P if live(p) and p['layer'] in DOOR_L]
    CC = comps(dl, 1.0); U = [units(c) for c in CC]
    UG = [unary_union([geom(P[i]) for i in c]) for c in CC]
    longl = [any(P[i]['kind'] == 'line' and LineString(P[i]['p']).length >= 12 for i in c) for c in CC]
    # small parts without an arc and a leaf: far jambs of doors drawn without an arc
    small = [(CC[k], np.array(UG[k].centroid.coords[0])) for k in range(len(CC)) if not U[k] and not longl[k] and UG[k].length < 15]
    taken = set()
    for k, c in enumerate(CC):
        us = U[k]
        if not us:
            if not longl[k]: continue                                   # a jamb part: goes with its door
            fr = frame_noarc(c, small)
            if fr is None:
                rep['двери: деталь без полотна и дуги — не тронута'] += 1
                places['doors_skipped'].append(dict(at=[round(v, 1) for v in UG[k].centroid.coords[0]], why='деталь', n=len(c))); continue
            F, L0, lv, far = fr
            if far is not None: taken.add(tuple(far)); c = c + far
            door_unit(c, 'однопольная без дуги', [], F, L0, lv); continue
        for kind, arcs in us:
            if kind == 'двупольная':
                a_, b_ = arcs; F = Frame(a_['c'], b_['c'] - a_['c']); L0 = np.linalg.norm(b_['c'] - a_['c'])
                if F.loc((a_['mid'] + b_['mid']) / 2)[1] < 0: F.n = -F.n
                lv = leaf_of(c, a_['c'], a_['r']) + leaf_of(c, b_['c'], b_['r'])
            else:
                F, L0, lv = frame_single(c, arcs[0])
            if not (8 <= L0 <= (52 if kind == 'двупольная' else 45)):
                rep['двери: странная ширина проёма — не тронуты'] += 1
                places['doors_skipped'].append(dict(at=[round(v, 1) for v in F.w(L0 / 2, 0)], why='ширина', L0=round(L0, 2))); continue
            door_unit(c, kind, arcs, F, L0, lv)
    for c, ctr in small:
        if tuple(c) not in taken:
            rep['двери: деталь без полотна и дуги — не тронута'] += 1
            places['doors_skipped'].append(dict(at=[round(v, 1) for v in ctr], why='деталь (коробка без двери)', n=len(c)))
doors(); index()
print('doors', {k: v for k, v in rep.items() if k.startswith('двер')}, T())
W2 = dict(W); W2['bodies'] = [(c, g) for c, g in B if not g.is_empty]
# bodies split into pieces by a cut stay one body per piece
W2['bodies'] = [(c, q) for c, g in W2['bodies'] for q in parts(g.buffer(0), 'Polygon') if q.area > 0.05]
pickle.dump(W2, open('walls_geom.pkl', 'wb'))
D1 = dict(D0); D1['P'] = P; pickle.dump(D1, open('prims_geom.pkl', 'wb'))
json.dump(dict(source_walls=WSRC, counts=dict(rep), places=places), open('geom_report.json', 'w'), ensure_ascii=False, indent=1)
print('written walls_geom.pkl, prims_geom.pkl', T())
