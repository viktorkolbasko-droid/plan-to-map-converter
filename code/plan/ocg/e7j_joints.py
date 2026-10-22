"""Э7с (owner 06.10.2026): joints. Where two elements meet — two walls, a lining on a capital wall, a glass pane or a
door at a wall — their faces meet face to face: the end of one lies on the face of the other, parallel to it, with no gap,
no overlap and no other angle. Check and fix, then check again:
 J1 wall body — wall body (touching, <= 0.3 pt): a vertex of one within 0.3 pt of the other's outline but not on it is
    put on it (projection); an overlap is cut from the thinner body (2A/P), a sliver of gap between them (closing 0.3 pt
    minus the two) goes to the thinner body. Columns and filled capital ends (source fills) are never changed.
 J2 glass pane — wall body: the end of a pane within 0.6 pt of a body is extended along the pane to the body and cut by
    it — the end then lies on the body's face (any angle of the face) with no gap and no overlap; only when the body is
    ahead of the end across >= 80 % of the pane's width (rays along the pane), never into the void.
 J3 door contour — its ends lie on the ends of the elements around the opening (moved along the line <= 0.6 pt).
 J4 fewest points (plan/rules/60 §4, 3.1): no vertex on a straight run, no duplicate point; a joint's node stays.
 J4b/J4c micro-steps, small teeth and notches (< 0.3 pt); J5/J5b small overlaps to the stronger body, seams filled.
 J6 (test 9) breaks between bodies 0.05–3 pt apart with wall strokes across the gap (no door, glass, other body): closed.
 J4d (test 9) chains of short edges between longer runs: spikes, steps (the face the source draws stays), noisy corners,
    the jitter of arcs — < 0.3 pt always, < 0.6 pt where the source draws nothing along them.
 J0a/J0b (before J1): wall pieces from twin lines of other layers; straight sides — a straight side has two points.
 Glass (test 9): measured and fitted per pane — a straight segment of glass, its triangles merged (glass_segments).
Measures before and after: gaps (> 0.005 pt² sliver), overlaps (> 0.005 pt²), vertices off the joint line (0.005–0.3 pt),
angle at the joint (> 1°, J2: end edge vs the face it meets).
Reads walls (load_walls: walls_e7.pkl), prims_f.pkl, objects.pkl; writes walls_j.pkl, prims_j.pkl, objects.pkl (pane ids),
joints.json. usage: python3 e7j_joints.py   (in the sheet folder, after e7f_furniture.py)"""
import pickle, json, math, collections, sys, time
import numpy as np, shapely, shapely.affinity
from shapely.geometry import LineString, Polygon, Point
from shapely.ops import unary_union, nearest_points
import os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import sheet; from e7_comp import geom, load_walls
t0 = time.time(); K = sheet.K
def T(): return f'{time.time() - t0:.1f} s'
W = load_walls(); B = [list(cg) for cg in W['bodies']]
D0 = pickle.load(open('prims_f.pkl', 'rb')); P = D0['P']
O = pickle.load(open('objects.pkl', 'rb')); objs = O['objs']; owner = O['owner']
FIXED = {'column', 'cap'}
GLASS = sheet.GLASS; WALL_L = sheet.L('wall'); DOOR_L = sheet.L('door')
def thick(g): return 2 * g.area / g.length if g.length > 0 else 0
def parts(x): return [q for q in getattr(x, 'geoms', [x]) if q.geom_type == 'Polygon' and q.area > 1e-4]
def valid_parts(x):
    """the polygons of a geometry made valid, nested collections flattened (make_valid gives a collection of a multipolygon
    and lines for a self-touching union of triangles)"""
    out = []
    for q in shapely.get_parts(shapely.make_valid(x)):
        out += [r for r in shapely.get_parts(q) if r.geom_type == 'Polygon' and r.area > 1e-4]
    return out
def measure_bodies():
    BG = [g for _, g in B]; bt = shapely.STRtree(BG); r = collections.Counter(); places = []
    for a, ga in enumerate(BG):
        for b in bt.query(ga.buffer(0.3)):
            if b <= a: continue
            gb = BG[b]
            if ga.distance(gb) > 0.3: continue
            ov = ga.intersection(gb).area
            zone = ga.buffer(0.35).intersection(gb.buffer(0.35))
            U = ga.union(gb); seam = U.buffer(0.3, join_style=2).buffer(-0.3, join_style=2).difference(U).intersection(zone)
            off = 0
            pair = '–'.join(sorted((B[a][0], B[b][0])))
            if ov > 0.005: r[f'нахлёст {pair}'] += 1
            if seam.area > 0.005: r[f'щель {pair}'] += 1
            if off: r[f'точки не на линии стыка {pair}'] += off
            if (ov > 0.005 or seam.area > 0.005 or off) and len(places) < 300:
                c = zone.centroid; places.append(dict(at=[round(c.x, 1), round(c.y, 1)], pair=pair, overlap_pt2=round(ov, 3), gap_pt2=round(seam.area, 3), off_points=off))
    return r, places
def panes():
    return [p['id'] for p in P if p['kind'] in ('fill', 'wline') and p['col'] in GLASS and p['layer'] in WALL_L]
def pane_geom(i):
    g = geom(P[i]); return g if g.geom_type == 'Polygon' else None
def pane_ends(g):
    r = g.minimum_rotated_rectangle
    if r.geom_type != 'Polygon': return None
    c = np.array(r.exterior.coords)[:4]; e1 = c[1] - c[0]; e2 = c[2] - c[1]
    if np.linalg.norm(e2) > np.linalg.norm(e1): e1, e2 = e2, e1
    L = np.linalg.norm(e1); u = e1 / L; n = np.array([-u[1], u[0]]); cen = c.mean(0); Wd = np.linalg.norm(e2)
    return cen, u, n, L, Wd
def measure_panes():
    """test 9: measured per pane — a straight segment of glass, its triangles merged (glass_segments) — not per triangle: a
    triangle's «end» is not an end of the pane (tests 7–8 counted 47 «other angle» ends, most of them were triangles)"""
    BG = [g for _, g in B]; bt = shapely.STRtree(BG); r = collections.Counter(); places = []
    for sg in glass_segments():
        if sg['fillr'] < 0.8: r['стекло: гнутая или гранёная лента одной сеткой — торцы не меряются'] += 1; continue
        g = sg['poly']; cen, u, n, L, Wd = sg['c'], sg['u'], sg['n'], sg['L'], sg['W']
        for sgn in (-1, 1):
            tip = cen + sgn * u * L / 2; end = LineString([tip - n * Wd / 2, tip + n * Wd / 2])
            js = [j for j in bt.query(end.buffer(0.6)) if BG[j].distance(end) <= 0.6]
            if not js: continue
            body = unary_union([BG[j] for j in js]); d = body.distance(g); ov = g.intersection(body).area
            # the end lies on the face: the pane's outline along the body (<= 0.03 pt) covers its width
            endzone = Polygon([tuple(tip - n * Wd - sgn * u * 1.0), tuple(tip + n * Wd - sgn * u * 1.0), tuple(tip + n * Wd + sgn * u * 1.0), tuple(tip - n * Wd + sgn * u * 1.0)])
            contact = g.boundary.intersection(body.buffer(0.03)).intersection(endzone).length
            bad = []
            if d > 0.005: r['стекло–стена: щель'] += 1; bad.append('щель')
            if ov > 0.005: r['стекло–стена: нахлёст'] += 1; bad.append('нахлёст')
            if d <= 0.005 and contact < 0.8 * Wd: r['стекло–стена: торец касается грани не всей шириной (другой угол)'] += 1; bad.append('угол')
            if not bad: r['стекло–стена: торец на грани — ок'] += 1
            if bad and len(places) < 300: places.append(dict(at=[round(v, 1) for v in tip], pane=sg['fills'][0], panes=sg['fills'], gap_pt=round(d, 3), overlap_pt2=round(ov, 3), contact_share=round(contact / Wd, 2) if Wd > 0 else 0, what=bad))
    return r, places
def glass_segments():
    """test 9: the straight segments of glass. The source draws a pane as fills split into triangles (a rectangle cut along
    its diagonal); fills of one colour that share a long edge (>= 40 % of the shorter one — the diagonal of the pane, not
    the short end where two panes meet at a kink) are one segment; slivers (< 0.5 pt long) join the segment they touch
    most."""
    segs = []
    GO = collections.defaultdict(list)                     # one group per colour: the triangles of a pane may sit in two objects
    for i in panes():
        g = pane_geom(i)
        if g is None or g.area <= 0 or not isinstance(owner.get(i), int): continue   # a pane inside a wall body is the wall's
        GO[P[i]['col']].append(i)
    for col_, ids in GO.items():
        info = {}
        for i in ids:
            pe = pane_ends(pane_geom(i))
            if pe is not None: info[i] = pe
        big = [i for i in ids if i in info and info[i][3] >= 0.5]; small = [i for i in ids if i not in big]
        par = {i: i for i in big}
        def f_(a_):
            while par[a_] != a_: par[a_] = par[par[a_]]; a_ = par[a_]
            return a_
        tr_ = shapely.STRtree([pane_geom(i) for i in big]) if big else None
        for x_, ia in enumerate(big):
            for y_ in (tr_.query(pane_geom(ia).buffer(0.05)) if tr_ is not None else []):
                ib = big[y_]
                if y_ <= x_: continue
                # the two triangles of one pane share their long edge (the diagonal): >= 40 % of the shorter one's length
                if pane_geom(ia).distance(pane_geom(ib)) > 0.05: continue
                shared = pane_geom(ia).boundary.buffer(0.05).intersection(pane_geom(ib).boundary).length
                if shared >= 0.4 * min(info[ia][3], info[ib][3]): par[f_(ia)] = f_(ib)
        grp = collections.defaultdict(list)
        for i in big: grp[f_(i)].append(i)
        gl = list(grp.values())
        for i in small:
            if not gl: break
            gi = pane_geom(i).buffer(0.05); best_ = max(range(len(gl)), key=lambda j: max(gi.intersection(pane_geom(x)).area for x in gl[j]))
            if max(gi.intersection(pane_geom(x)).area for x in gl[best_]) > 0: gl[best_].append(i)
        for fl in gl:
            U = unary_union([pane_geom(i).buffer(0.01, join_style=2) for i in fl]).buffer(-0.01, join_style=2)
            ps = parts(U)
            if not ps: continue
            S = max(ps, key=lambda q: q.area)
            if not S.is_valid: S = max(valid_parts(S) or [S.buffer(0)], key=lambda q: q.area)
            pe = pane_ends(S)
            if pe is None: continue
            c, u, n, L, Wd = pe
            own_ = collections.Counter()
            for i in fl: own_[owner.get(i) if isinstance(owner.get(i), int) else None] += pane_geom(i).area
            segs.append(dict(obj=own_.most_common(1)[0][0], fills=fl, poly=S, c=c, u=u, n=n, L=L, W=Wd, fillr=S.area / max(L * Wd, 1e-9), col=P[fl[0]]['col'], layer=P[fl[0]]['layer']))
    return segs
def kink_pairs(segs):
    """two straight segments (>= 2 pt long, >= 80 % of their rectangle) whose axes are 3°–30° apart, whose nearest ends are
    within 0.8 pt, and no wall between them (< 30 % of the gap): a kink of a faceted glass partition"""
    BG_ = [g for _, g in B]; bt_ = shapely.STRtree(BG_); out = []
    ok_ = [a_ for a_, sg in enumerate(segs) if sg['L'] >= 2.0 and sg['fillr'] >= 0.8]
    for x_, a_ in enumerate(ok_):
        sa = segs[a_]
        for b_ in ok_[x_ + 1:]:
            sb = segs[b_]
            ang = math.degrees(math.acos(min(1.0, abs(float(sa['u'] @ sb['u'])))))
            if not (3.0 <= ang <= 30.0): continue
            tips = [(float(np.linalg.norm(ta - tb)), ta, tb) for ta in (sa['c'] + sa['u'] * sa['L'] / 2, sa['c'] - sa['u'] * sa['L'] / 2)
                    for tb in (sb['c'] + sb['u'] * sb['L'] / 2, sb['c'] - sb['u'] * sb['L'] / 2)]
            d, ta, tb = min(tips, key=lambda t: t[0])
            if d > 0.8: continue
            gap = Polygon([tuple(ta + sa['n'] * sa['W'] / 2), tuple(ta - sa['n'] * sa['W'] / 2), tuple(tb - sb['n'] * sb['W'] / 2), tuple(tb + sb['n'] * sb['W'] / 2)]).buffer(0.05)
            if gap.area > 0 and sum(BG_[q].intersection(gap).area for q in bt_.query(gap)) > 0.3 * gap.area: continue
            out.append((a_, b_, ang, ta, tb))
    return out
def kink_state(sa, sb, ta, tb):
    """the joint of a kink: the wedge of void at its outer side (closing the two by half their width) and the overlap"""
    U = sa['poly'].union(sb['poly']); r = 0.5 * max(sa['W'], sb['W'])
    disc = Point(tuple((ta + tb) / 2)).buffer(2.5 * max(sa['W'], sb['W']) + 0.5)
    seam = U.buffer(r, join_style=2, mitre_limit=10).buffer(-r, join_style=2, mitre_limit=10).difference(U).intersection(disc).area
    return seam, sa['poly'].intersection(sb['poly']).area
def measure_kinks():
    segs = glass_segments(); r = collections.Counter()
    for a_, b_, ang, ta, tb in kink_pairs(segs):
        seam, ov = kink_state(segs[a_], segs[b_], ta, tb)
        r['стекло–стекло на изломе: состыковано' if seam <= 0.02 and ov <= 0.02 else 'стекло–стекло на изломе: клин пустоты или нахлёст'] += 1
    return r
before_b, pl_b = measure_bodies(); before_p, pl_p = measure_panes()
before_k = measure_kinks(); print('before: glass kinks', dict(before_k))
print('before: bodies', dict(before_b), '| panes', dict(before_p), T())
# ---------------------------------------------------------------------------------------------------------------- J0a bridges
# owner 06.10.2026 («оттуда потерялся кусок стены»): two parallel lines at a wall's thickness (0.4–2.6 pt, 20–125 mm) that
# run side by side and close against wall bodies at both ends are a wall piece, whatever layer the source put them on
# (клиент Б: an L-shaped piece of a partition drawn on «Размеры»). The band between them becomes a body (gkl); the lines
# are the wall's and are not drawn on their own. Lines of furniture, doors, glass and equipment are not candidates.
BRIDGE_KEYS = {'dim', 'lpart', 'wallline', 'mark', 'axis', 'coreline', 'roomsep', 'measure'}
cand = []
for k_, o in enumerate(objs):
    if o['key'] not in BRIDGE_KEYS: continue
    for i in o['ids']:
        p = P[i]
        if p['kind'] == 'line' and len(p['p']) >= 2:
            g = LineString(p['p'])
            if g.length >= 1.0: cand.append((i, k_, g))
ct = shapely.STRtree([g for _, _, g in cand]); BG0 = [g for _, g in B]; bt0 = shapely.STRtree(BG0)
PANES0 = [g for g in (pane_geom(i) for i in panes()) if g is not None and g.area > 0]; pt0 = shapely.STRtree(PANES0) if PANES0 else None
used_l = set(); bridges = []
for a_, (ia, ka, ga) in enumerate(cand):
    if ia in used_l: continue
    for b_ in ct.query(ga.buffer(2.7)):
        ib, kb, gb = cand[b_]
        if b_ <= a_ or ib in used_l or ib == ia: continue
        if not (0.6 <= gb.length / ga.length <= 1.6): continue
        # a line of the source is often a thin outlined strip (a path there and back): compare both ways, 17 samples each
        sa = [ga.interpolate(f, normalized=True) for f in np.linspace(0, 1, 17)]; sb = [gb.interpolate(f, normalized=True) for f in np.linspace(0, 1, 17)]
        da = np.array([gb.distance(q) for q in sa] + [ga.distance(q) for q in sb])
        if not (0.4 <= da.min() and da.max() <= 2.6 and da.max() - da.min() <= 0.5 * da.mean() + 0.1): continue
        r_ = 0.55 * float(da.max())                                             # the band: the two lines and the floor between them
        band = unary_union([ga, gb]).buffer(r_, join_style=2, mitre_limit=2.0).buffer(-r_, join_style=2, mitre_limit=2.0)
        band = max(parts(band), key=lambda q: q.area) if parts(band) else None
        if band is None or not (0.5 * da.mean() <= thick(band) <= 1.6 * da.mean() + 0.3) or band.length / 2 < 3 * da.mean(): continue   # a strip as wide as the gap
        near_b = [j for j in bt0.query(band.buffer(0.3)) if BG0[j].distance(band) <= 0.3]
        if not near_b: continue
        # both ends close against walls: the band touches walls at two places at least 2 widths apart (or two bodies)
        touch = [band.boundary.intersection(BG0[j].buffer(0.3)) for j in near_b]
        tps = [q for t_ in touch for q in getattr(t_, 'geoms', [t_]) if not q.is_empty]
        if len(near_b) < 2 and not (len(tps) >= 2 and max(a.distance(b) for a in tps for b in tps) >= 2 * float(da.mean())): continue
        if band.intersection(unary_union([BG0[j] for j in near_b])).area > 0.3 * band.area: continue   # the body's own outline
        # v3: not where glass stands (a glass partition with the dimension lines beside it is not a wall piece; Эльбрус)
        if pt0 is not None and sum(PANES0[j].intersection(band).area for j in pt0.query(band)) > 0.1 * band.area: continue
        bridges.append(dict(lines=[ia, ib], objs=[ka, kb], band=band, at=[round(v, 1) for v in band.centroid.coords[0]],
                            width_mm=round(float(da.mean()) * K), length_mm=round(ga.length * K), layers=sorted({P[ia]['layer'], P[ib]['layer']})))
        used_l.update({ia, ib}); break
for br in bridges:
    B.append(['gkl', br['band']])
    for i, k_ in zip(br['lines'], br['objs']):
        o = objs[k_]; o['ids'] = [x for x in o['ids'] if x != i]
        if 'draw' in o: o['draw'] = [x for x in o['draw'] if x != i]
        if not o['ids']: o['key'] = 'empty'; o['name'] = (o.get('name') or '') + ' → часть стены'
print('J0a: wall pieces from twin lines of other layers', len(bridges), [(b_['at'], b_['layers'], b_['width_mm'], b_['length_mm']) for b_ in bridges][:20], T())
# ---------------------------------------------------------------------------------------------------------------- J0c core walls
# owner 06.10.2026: «ядро башни… капитальные толстые стены, шахты, лифты… не собраны в замкнутый контур полигона»;
# «контур капитальной стены не замкнулся в полигоне». In the core the source hatches the shafts and draws the capital walls
# as outline-only bands between the core outline and the shaft outlines. A face of that line work (lines of the core
# outline, shafts, lifts, wall layers, bodies; breaks < 0.24 pt closed) is a capital wall when it is: not hatched (hatch
# strokes inside < 1 x its thickness), 0.4–10 pt thick (20–480 mm, 2A/P), long (half-perimeter >= 4 thicknesses, >= 6
# under 1.5 pt), with >= 30 % of its outline on the core outline or along the hatched shafts, no text in it. It becomes a body of class 'cap' (capital wall, A-221);
# lines of the core outline and partitions without hatch that run along it are the wall's and are not drawn on their own.
CORE_K = {'coreline', 'shaft', 'lift', 'corezone'}
core_geo = [geom(P[i]) for o in objs if o['key'] in CORE_K for i in o['ids'] if P[i]['kind'] != 'removed']
core_geo = [g for g in core_geo if not g.is_empty]
ncore = 0; core_absorbed = 0
if core_geo:
    hull = unary_union([g.envelope for g in core_geo]).buffer(1.0)
    WALL_LAYERS = sheet.L('core', 'wall', 'core_lines')
    hatch = unary_union([geom(P[i]) for o in objs if o['key'] == 'corezone' for i in o['ids'] if P[i]['kind'] != 'removed'])
    cl_geo = unary_union([geom(P[i]).boundary if geom(P[i]).geom_type == 'Polygon' else geom(P[i]) for o in objs if o['key'] == 'coreline' for i in o['ids'] if P[i]['kind'] != 'removed'])
    lines_ = [geom(P[i]) for o in objs if o['key'] in ('coreline', 'shaft', 'lift', 'lpart', 'wallline', 'mark') for i in o['ids'] if P[i]['kind'] != 'removed']
    lines_ += [geom(p).boundary if p['kind'] == 'fill' else geom(p) for p in P if p['kind'] in ('line', 'fill') and p['layer'] in WALL_LAYERS
               and isinstance(owner.get(p['id']), int) and objs[owner[p['id']]]['key'] not in ('corezone', 'door', 'dim', 'axis', 'tagc')]
    lines_ = [g if g.geom_type in ('LineString', 'MultiLineString', 'LinearRing') else g.boundary for g in lines_ if not g.is_empty]
    lines_ += [g.boundary for _, g in B if g.intersects(hull)]
    LW = unary_union([g for g in lines_ if g.intersects(hull)]).buffer(0.12)
    faces = [q for q in getattr(hull.difference(LW), 'geoms', [hull.difference(LW)]) if q.geom_type == 'Polygon' and q.area > 1.0]
    labels = [Point((t['bbox'][0] + t['bbox'][2]) / 2, (t['bbox'][1] + t['bbox'][3]) / 2) for t in D0['T']]
    lt = shapely.STRtree(labels) if labels else None
    BGc = [g for _, g in B]; btc = shapely.STRtree(BGc); newc = []
    HZ = hatch.buffer(2.0).buffer(-1.0)                                         # the hatched floor of the core (shafts)
    for f in faces:
        f2 = f.buffer(0.12, join_style=2, mitre_limit=2.0)                     # back to the line centres
        n_ = thick(f2)
        if not (0.4 <= n_ <= 10.0) or f2.length / 2 < (6 if n_ < 1.5 else 4) * n_: continue
        if hatch.intersection(f).length > 1.0 * n_ + 0.5: continue            # hatched: a shaft, not a wall
        side = f2.boundary.intersection(cl_geo.buffer(0.2).union(HZ.buffer(0.6))).length
        if side < 0.3 * f2.length: continue                                     # a capital wall borders the core outline or its shafts
        if lt is not None and any(f.contains(labels[j]) for j in lt.query(f)): continue
        if any(BGc[j].intersection(f2).area > 0.3 * f2.area for j in btc.query(f2)): continue
        newc.append(f2)
    if newc:
        U = unary_union(newc)
        for q in getattr(U, 'geoms', [U]):
            if q.geom_type == 'Polygon' and q.area > 1.0: B.append(['cap', q]); ncore += 1
        CB = U.buffer(0.3)
        for o in objs:                                                           # the outline and stray lines along it are the wall's
            if o['key'] not in ('coreline', 'lpart', 'wallline'): continue
            keep_ = []
            for i in o['ids']:
                g = geom(P[i]); g = g.boundary if g.geom_type == 'Polygon' else g
                if g.length > 0 and g.intersection(CB).length >= 0.8 * g.length: core_absorbed += 1
                else: keep_.append(i)
            if len(keep_) < len(o['ids']):
                o['ids'] = keep_
                if 'draw' in o: o['draw'] = [x for x in o['draw'] if x in keep_]
                if not keep_: o['key'] = 'empty'; o['name'] = (o.get('name') or '') + ' → капитальная стена'
print('J0c: core capital walls as polygons', ncore, '| core faces', len(faces) if core_geo else 0, '| outline lines taken by them', core_absorbed, T())
# ---------------------------------------------------------------------------------------------------------------- J0b straight sides
# owner 06.10.2026: «Если мы видим, что стена прямая, то на прямом участке должны быть две точки в начале и в конце»;
# «в стенах не должно быть пустот, разрывов, каких-то мелких неровностей». Every ring of a body is cut into sides by
# Douglas–Peucker with tolerance tol = min(t/2, 50 mm) (t = 2A/P, the wall's thickness): a step, notch or tooth shallower
# than tol is not a side of its own. Each side is fitted by one straight line (least squares over its length) and the
# vertices are the intersections of neighbouring lines — a straight side has two points. Neighbouring sides within 8°
# keep a short connector (a real step of >= tol). A ring is replaced only when the result is valid and stays within
# 1.5 tol of the old outline; columns and filled ends too (their sides are straight in the source).
def dp_idx(Q, tol):
    keep = {0, len(Q) - 1}; st = [(0, len(Q) - 1)]
    while st:
        i, j = st.pop()
        if j <= i + 1: continue
        a, b = Q[i], Q[j]; ab = b - a; L = np.linalg.norm(ab); seg = Q[i + 1:j]
        d = np.linalg.norm(seg - a, axis=1) if L < 1e-9 else np.abs((seg[:, 0] - a[0]) * ab[1] - (seg[:, 1] - a[1]) * ab[0]) / L
        m = int(np.argmax(d))
        if d[m] > tol: keep.add(i + 1 + m); st += [(i, i + 1 + m), (i + 1 + m, j)]
    return sorted(keep)
def fit_line(S):
    S = np.asarray(S); w = np.linalg.norm(S[1:] - S[:-1], axis=1)
    if w.sum() < 1e-9: return S.mean(0), np.array([1.0, 0.0])
    c = (((S[1:] + S[:-1]) / 2) * w[:, None]).sum(0) / w.sum(); C = np.zeros((2, 2))
    for a_, b_, wi in zip(S[:-1], S[1:], w):
        if wi < 1e-12: continue
        da, db = a_ - c, b_ - c; C += wi * (np.outer(da, da) + np.outer(db, db) + 0.5 * (np.outer(da, db) + np.outer(db, da))) / 3.0
    ev, evec = np.linalg.eigh(C); u = evec[:, int(np.argmax(ev))]
    return c, u / np.linalg.norm(u)
def reg_ring(cs, tol):
    Pq = np.array(cs[:-1], float)
    n = len(Pq)
    if n < 4: return None
    def turn(i):
        u, v = Pq[i] - Pq[i - 1], Pq[(i + 1) % n] - Pq[i]
        if np.linalg.norm(u) < 1e-9 or np.linalg.norm(v) < 1e-9: return 0.0
        return abs(math.atan2(u[0] * v[1] - u[1] * v[0], u @ v)) * min(np.linalg.norm(u), np.linalg.norm(v))
    s0 = max(range(n), key=turn)                                                # start at a strong corner
    Q = np.vstack([Pq[s0:], Pq[:s0], Pq[s0:s0 + 1]]); kp = dp_idx(Q, tol)
    if len(kp) < 4: return None
    lines = [fit_line(Q[kp[k]:kp[k + 1] + 1]) for k in range(len(kp) - 1)]; out = []
    for k in range(len(lines)):
        (c1, u1), (c2, u2) = lines[k - 1], lines[k]; v0 = Q[kp[k]]
        ang = math.degrees(math.acos(min(1.0, abs(float(u1 @ u2)))))
        if ang < 8.0:
            out += [c1 + u1 * ((v0 - c1) @ u1), c2 + u2 * ((v0 - c2) @ u2)]
        else:
            M = np.array([u1, -u2]).T
            x = c1 + u1 * np.linalg.solve(M, c2 - c1)[0]
            out.append(x if np.linalg.norm(x - v0) <= 3 * tol else v0)
    return [tuple(map(float, q)) for q in out]
nreg = collections.Counter(); nvr0 = nvr1 = 0
for e_, (c, g) in enumerate(B):
    t_ = thick(g); tol = min(max(0.5 * t_, 0.1), 50 / K)
    nvr0 += len(g.exterior.coords) - 1 + sum(len(h.coords) - 1 for h in g.interiors)
    ex = reg_ring(list(g.exterior.coords), tol)
    hs = []
    for h in g.interiors:
        hp = Polygon(h)
        if hp.area < 0.05 or 2 * hp.area / max(hp.length, 1e-9) < 0.05: continue      # a sliver hole is not a hole
        rh = reg_ring(list(h.coords), tol); hs.append(rh if rh and len(rh) >= 3 else list(h.coords))
    if ex is None or len(ex) < 3: nreg['оставлено: мало точек'] += 1; nvr1 += len(g.exterior.coords) - 1; continue
    try: ng = Polygon(ex, hs)
    except Exception: ng = None
    if ng is None or not ng.is_valid or ng.is_empty:
        nreg['оставлено: контур пересёк себя'] += 1; nvr1 += len(g.exterior.coords) - 1 + sum(len(h.coords) - 1 for h in g.interiors); continue
    if ng.hausdorff_distance(g) > 1.5 * tol + 0.02 or abs(ng.area - g.area) > 0.08 * g.area + 0.05:
        nreg['оставлено: форма ушла дальше допуска'] += 1; nvr1 += len(g.exterior.coords) - 1 + sum(len(h.coords) - 1 for h in g.interiors); continue
    B[e_][1] = ng; nreg['выпрямлено'] += 1
    nvr1 += len(ng.exterior.coords) - 1 + sum(len(h.coords) - 1 for h in ng.interiors)
print('J0b straight sides: bodies', dict(nreg), '| vertices', nvr0, '->', nvr1, T())
# ---------------------------------------------------------------------------------------------------------------- fewest points
# owner 06.10.2026: a wall with the fewest points — before the joints are fitted (the fit is the last move), vertices on a straight run (deviation
# <= 0.02 pt = 1 mm) are dropped (Douglas–Peucker, topology kept); columns and filled ends stay as the source draws them
nv0 = nv1 = 0
for e_, (c, g) in enumerate(B):
    nv0 += len(g.exterior.coords) + sum(len(h.coords) for h in g.interiors)
    if c in FIXED: nv1 += len(g.exterior.coords) + sum(len(h.coords) for h in g.interiors); continue
    g2 = g.simplify(0.02, preserve_topology=True)
    if g2.geom_type == 'Polygon' and not g2.is_empty and abs(g2.area - g.area) <= 0.01 * g.area + 0.01: B[e_][1] = g2; g = g2
    nv1 += len(g.exterior.coords) + sum(len(h.coords) for h in g.interiors)
print('fewest points before the joints: vertices', nv0, '->', nv1, T())
# ---------------------------------------------------------------------------------------------------------------- J1 fix
def snap_body(a, others):
    g = B[a][1]; changed = 0
    def snap_ring(ring):
        nonlocal changed
        out = []
        for v in np.array(ring.coords):
            pt = Point(v); best = None
            for o in others:
                if o.contains(pt): continue
                d = o.boundary.distance(pt)
                if 0.005 < d <= 0.3 and (best is None or d < best[0]): best = (d, o)
            if best:
                q = nearest_points(best[1].boundary, pt)[0]; out.append((q.x, q.y)); changed += 1
            else: out.append(tuple(v))
        return out
    try:
        ng = Polygon(snap_ring(g.exterior), [snap_ring(h) for h in g.interiors]).buffer(0)
    except Exception: return 0
    if changed and not ng.is_empty and abs(ng.area - g.area) <= 0.2 * g.area: B[a][1] = ng if ng.geom_type == 'Polygon' else max(parts(ng), key=lambda q: q.area)
    return changed
nsnap = nov = ngap = 0
BG = [g for _, g in B]; bt = shapely.STRtree(BG)
order = sorted(range(len(B)), key=lambda a: thick(B[a][1]))                  # thin bodies (linings) move to the thick ones
for a in order:
    if B[a][0] in FIXED: continue
    ga = B[a][1]; nb = [b for b in bt.query(ga.buffer(0.3)) if b != a and B[b][1].distance(ga) <= 0.3]
    if not nb: continue
    nsnap += snap_body(a, [B[b][1] for b in nb if B[b][0] in FIXED or thick(B[b][1]) >= thick(ga)])
    ga = B[a][1]
    for b in nb:
        gb = B[b][1]
        if thick(ga) > thick(gb) and B[b][0] not in FIXED: continue               # the thinner one gives way
        ov = ga.intersection(gb)
        if ov.area > 0.005:
            ng = ga.difference(gb); ps = parts(ng)
            if ps: ga = max(ps, key=lambda q: q.area) if len(ps) > 1 and max(q.area for q in ps) > 0.9 * ng.area else ng; nov += 1
        zone = ga.buffer(0.35).intersection(gb.buffer(0.35)); U = ga.union(gb)
        seam = U.buffer(0.3, join_style=2).buffer(-0.3, join_style=2).difference(U).intersection(zone)
        if seam.area > 0.005:
            ga = ga.union(seam.buffer(0.002)).difference(gb); ngap += 1
    ps = parts(ga)
    if ps: B[a][1] = ga if ga.geom_type == 'Polygon' else max(ps, key=lambda q: q.area) if max(q.area for q in ps) > 0.95 * ga.area else ga
B = [[c, q] for c, g in B for q in parts(g)]                             # one polygon per body
print('J1: vertices put on the joint line', nsnap, '| overlaps cut', nov, '| gaps closed', ngap, T())
# ---------------------------------------------------------------------------------------------------------------- J2 fix
# test 9: per pane — a straight segment of glass, its triangles merged (glass_segments) — not per triangle (a triangle
# extended along the long side of its minimum rectangle is not the pane extended along its axis). A pane that changes
# becomes one fill: its triangles are one pane.
BG = [g for _, g in B]; bt = shapely.STRtree(BG); np2 = 0; nj2_void = 0; nseg_one = 0
def seg_write(sg, poly, why):
    k = sg['obj']; f0 = P[sg['fills'][0]]
    r_ = dict(f0); r_['id'] = len(P); r_['kind'] = 'fill'; r_['p'] = [tuple(map(float, c)) for c in poly.exterior.coords][:-1]; r_['holes'] = []
    r_['src_id'] = f0.get('src_id', f0['id']); r_['joint'] = why; r_['seg_of'] = [P[i].get('src_id', i) for i in sg['fills']]; P.append(r_)
    for i in sg['fills']:
        P[i]['kind'] = 'removed'; P[i]['removed_by'] = why
        ko = owner.get(i)
        if isinstance(ko, int) and ko != k:
            objs[ko]['ids'] = [x for x in objs[ko]['ids'] if x != i]
            if 'draw' in objs[ko]: objs[ko]['draw'] = [x for x in objs[ko]['draw'] if x != i]
    if isinstance(k, int):
        objs[k]['ids'] = [x for x in objs[k]['ids'] if x not in set(sg['fills'])] + [r_['id']]; owner[r_['id']] = k
        if 'draw' in objs[k]: objs[k]['draw'] = [x for x in objs[k]['draw'] if x not in set(sg['fills'])] + [r_['id']]
    return r_['id']
for sg in glass_segments():
    if sg['fillr'] < 0.8: continue
    g = sg['poly']; cen, u, n, L, Wd = sg['c'], sg['u'], sg['n'], sg['L'], sg['W']; ng = g
    for sgn in (-1, 1):
        tip = cen + sgn * u * L / 2; end = LineString([tip - n * Wd / 2, tip + n * Wd / 2])
        js = [j for j in bt.query(end.buffer(0.6)) if BG[j].distance(end) <= 0.6]
        if not js: continue
        body = unary_union([BG[j] for j in js])
        ext = Polygon([tuple(tip - n * Wd / 2 - sgn * u * 0.05), tuple(tip + n * Wd / 2 - sgn * u * 0.05),
                       tuple(tip + n * Wd / 2 + sgn * u * 0.7), tuple(tip - n * Wd / 2 + sgn * u * 0.7)])
        # the body must be ahead of the end across >= 80 % of the pane's width (4 of 5 rays along the pane reach it within
        # 0.7 pt); a body beside the pane does not stop the extension and the pane would grow into the void (test 7: 20 ends)
        hits = sum(1 for o_ in np.linspace(-0.4, 0.4, 5) * Wd
                   if LineString([tuple(tip + n * o_ - sgn * u * 0.05), tuple(tip + n * o_ + sgn * u * 0.7)]).intersects(body))
        if hits < 4: nj2_void += 1; continue
        try: cand = ng.union(ext).difference(body)
        except shapely.errors.GEOSException:
            cand = shapely.difference(shapely.union(ng, ext, grid_size=0.001), shapely.make_valid(body), grid_size=0.001)
        ps = parts(cand)
        if not ps: continue
        main = max(ps, key=lambda q: q.area)
        if abs(main.area - ng.area) <= 0.25 * ng.area: ng = main
    if ng is not g and not ng.equals(g):
        seg_write(sg, ng, 'joint'); np2 += 1
print('J2: glass pane ends put on the wall face', np2, '| ends left as they are (the body is beside, not ahead)', nj2_void, T())
# the fit leaves vertices on straight runs where it cut or joined along a face: those within 0.003 pt (0.15 mm) of the
# line through their neighbours are dropped — the shape and the joints do not move
nvc0 = nvc1 = 0
for e_, (c, g) in enumerate(B):
    if c in FIXED: continue
    nvc0 += len(g.exterior.coords); g2 = g.simplify(0.003, preserve_topology=True)
    if g2.geom_type == 'Polygon' and not g2.is_empty: B[e_][1] = g2
    nvc1 += len(B[e_][1].exterior.coords)
print('collinear vertices left by the fit dropped:', nvc0, '->', nvc1, T())
# ---------------------------------------------------------------------------------------------------------------- J4 fewest points
# owner 06.10.2026 + plan/rules/60 §4, 3.1: no vertex on a straight run — turn <= 0.5°, or deviation <= 0.02 pt (1 mm at
# 1:100 of this sheet; in mm: <= 1 mm) at a turn <= 10° — and no duplicate point, in every body (columns and filled ends too:
# their shape moves by <= 1 mm). A vertex whose two edges pass by another body or a glass pane (<= 0.35 pt) is dropped only when the joint
# stays as it is: the overlap and the seam with that neighbour do not grow (<= 0.0001 pt²); otherwise it is the joint's node and stays.
def straight_ok(a, b, d, dev=0.02, turn=10.0):
    u, v = b - a, d - b; lu, lv = np.linalg.norm(u), np.linalg.norm(v)
    if lu < 1e-9 or lv < 1e-9: return True
    ang = math.degrees(math.acos(max(-1.0, min(1.0, (u @ v) / lu / lv)))); w = d - a; lw = np.linalg.norm(w)
    h = abs(w[0] * (b - a)[1] - w[1] * (b - a)[0]) / lw if lw > 1e-9 else 0.0
    return ang <= 0.5 or (h <= dev and ang <= turn)
def joint_state(g, nbs):
    out = []
    for gb in nbs:
        ov = g.intersection(gb).area
        zone = g.buffer(0.35).intersection(gb.buffer(0.35)); U = g.union(gb)
        out.append((ov, U.buffer(0.3, join_style=2).buffer(-0.3, join_style=2).difference(U).intersection(zone).area))
    return out
PG = [q for q in (pane_geom(i) for i in panes()) if q is not None and q.area > 0]
pt_tree = shapely.STRtree(PG) if PG else None
def nverts(g): return len(g.exterior.coords) - 1 + sum(len(h.coords) - 1 for h in g.interiors)
def fill_slivers(g):
    # a hole of < 0.05 pt² or thinner than 0.05 pt (2A/P) is a sliver between faces, not a hole; v3 (owner 06.10.2026: «в стенах
    # не должно быть пустот, разрывов») — a hole smaller than 10 pt² (0.023 m², 150 × 150 mm) or narrower than the wall
    # (2A/P < its thickness) is a void inside the wall: filled; a bigger hole is a room the wall goes round
    t_ = 2 * g.area / max(g.length, 1e-9)
    hs = [h for h in g.interiors if Polygon(h).area >= 10.0 and 2 * Polygon(h).area / max(Polygon(h).length, 1e-9) >= max(t_, 0.05)]
    return (Polygon(g.exterior, hs) if len(hs) < len(g.interiors) else g), len(g.interiors) - len(hs)
nv40 = nv41 = 0; d4 = collections.Counter()
def fewest(e_, c, g, BG, bt, d4):
    global nv40, nv41
    nbs = [BG[j] for j in bt.query(g.buffer(0.35)) if j != e_ and BG[j].distance(g) <= 0.35]
    if pt_tree is not None: nbs += [PG[j] for j in pt_tree.query(g.buffer(0.35)) if PG[j].distance(g) <= 0.35]
    nv40 += nverts(g); cur, nh = fill_slivers(g); d4['дыры и пустоты внутри тела закрыты'] += nh; keep = set()
    for pass_ in range(12):
        changed = restart = False
        rings = [[np.array(v) for v in cur.exterior.coords[:-1]]] + [[np.array(v) for v in h.coords[:-1]] for h in cur.interiors]
        for ri in range(len(rings)):
            i = 0
            while i < len(rings[ri]) and len(rings[ri]) > 3:
                cr = rings[ri]; a, b, d = cr[i - 1], cr[i], cr[(i + 1) % len(cr)]; key = tuple(np.round(b, 6))
                if key in keep or not straight_ok(a, b, d): i += 1; continue
                rr = [cr[:i] + cr[i + 1:] if k == ri else rings[k] for k in range(len(rings))]
                rebuilt = any(len(h) < 3 for h in rr[1:])            # a hole that loses its last straight vertex is a line: it goes
                try: cand = Polygon([tuple(v) for v in rr[0]], [[tuple(v) for v in h] for h in rr[1:] if len(h) >= 3])
                except Exception: i += 1; continue
                if not cand.is_valid:                                  # dropping it touches another edge (a pinch): keep the main part
                    ps = parts(shapely.make_valid(cand))
                    if not ps: i += 1; continue
                    m_ = max(ps, key=lambda q: q.area)
                    if abs(m_.area - cur.area) > 0.02: i += 1; continue
                    cand = m_; rebuilt = True
                near = [gb for gb in nbs if gb.distance(LineString([tuple(a), tuple(b), tuple(d)])) <= 0.35]   # the outline moves only between a and d
                if near and any(o1 > o0 + 1e-4 or q1 > q0 + 1e-4 for (o0, q0), (o1, q1) in zip(joint_state(cur, near), joint_state(cand, near))):
                    keep.add(key); i += 1; continue
                d4['у стыка' if near else 'на прямом участке'] += 1; cur = cand; changed = True
                if rebuilt: restart = True; break
                rings[ri] = rr[ri]; i = max(i - 1, 0)
            if restart: break
        if not changed: break
    B[e_][1] = cur; nv41 += nverts(cur); d4['оставлено узлов стыка'] += len(keep)

BG = [g for _, g in B]; bt = shapely.STRtree(BG)
for e_, (c, g) in enumerate(B): fewest(e_, c, g, BG, bt, d4)
print('J4 fewest points (3.1): vertices', nv40, '->', nv41, '| dropped', dict(d4), T())
# ---------------------------------------------------------------------------------------------------------------- J4b micro-steps
# owner 06.10.2026 («в стенах не должно быть… каких-то мелких неровностей»): a step of a straight face — two vertices b, c
# with a short edge b–c (<= 0.3 pt, 14 mm at 1:100) between two nearly parallel edges of one direction (<= 5°) offset by
# <= 0.3 pt — is a drawing artifact: b and c go, a joins d when the face a–d turns by <= 3° from both edges (it moves by
# <= 14 mm); not where the joint with a
# neighbour (another body or glass <= 0.35 pt) would get a bigger overlap or seam; the outline must stay valid.
def _ang(u, v):
    lu, lv = np.linalg.norm(u), np.linalg.norm(v)
    if lu < 1e-9 or lv < 1e-9: return 180.0
    return math.degrees(math.acos(max(-1.0, min(1.0, (u @ v) / lu / lv))))
nms = collections.Counter(); BG = [g for _, g in B]; bt = shapely.STRtree(BG)
for e_, (c, g) in enumerate(B):
    nbs = [BG[j] for j in bt.query(g.buffer(0.35)) if j != e_ and BG[j].distance(g) <= 0.35]
    if pt_tree is not None: nbs += [PG[j] for j in pt_tree.query(g.buffer(0.35)) if PG[j].distance(g) <= 0.35]
    cur = g
    for pass_ in range(6):
        changed = False
        rings = [[np.array(v) for v in cur.exterior.coords[:-1]]] + [[np.array(v) for v in h.coords[:-1]] for h in cur.interiors]
        for ri in range(len(rings)):
            cr = rings[ri]; i = 0
            while len(cr) > 4 and i < len(cr):
                m_ = len(cr); a, b, c_, d = cr[(i - 1) % m_], cr[i], cr[(i + 1) % m_], cr[(i + 2) % m_]
                if np.linalg.norm(c_ - b) > 0.3 or _ang(b - a, d - c_) > 5.0 or np.linalg.norm(b - a) < 0.3 or np.linalg.norm(d - c_) < 0.3: i += 1; continue
                u_ = (d - a) / max(np.linalg.norm(d - a), 1e-9); off = max(abs((b - a)[0] * u_[1] - (b - a)[1] * u_[0]), abs((c_ - a)[0] * u_[1] - (c_ - a)[1] * u_[0]))
                if off > 0.3 or _ang(d - a, b - a) > 3.0 or _ang(d - a, d - c_) > 3.0: i += 1; continue      # the joined face turns by <= 3°
                keep_idx = [k for k in range(m_) if k not in (i, (i + 1) % m_)]
                rr = [[cr[k] for k in keep_idx] if k2 == ri else rings[k2] for k2 in range(len(rings))]
                try: cand = Polygon([tuple(v) for v in rr[0]], [[tuple(v) for v in h] for h in rr[1:] if len(h) >= 3])
                except Exception: i += 1; continue
                if not cand.is_valid or abs(cand.area - cur.area) > 0.5 * max(np.linalg.norm(d - a), 1.0) * 0.3: i += 1; continue
                near = [gb for gb in nbs if gb.distance(LineString([tuple(a), tuple(b), tuple(c_), tuple(d)])) <= 0.35]
                if near and any(o1 > o0 + 1e-3 or q1 > q0 + 1e-3 for (o0, q0), (o1, q1) in zip(joint_state(cur, near), joint_state(cand, near))): nms['у стыка — оставлена'] += 1; i += 1; continue
                cur = cand; rings[ri] = rr[ri]; cr = rings[ri]; changed = True; nms['убрана'] += 1
            rings[ri] = cr
        if not changed: break
    B[e_][1] = cur
print('J4b micro-steps of straight faces (<= 0.3 pt):', dict(nms), T())
# ---------------------------------------------------------------------------------------------------------------- J4c small teeth
# the same, for teeth and notches of any shape thinner than 0.3 pt (14 mm at 1:100): the hatch strokes of a wall touching
# its outline leave tiny triangles. Opening and closing of the body by 0.15 pt (mitre: corners stay sharp) find them; a
# piece away from every neighbour (> 0.35 pt: not a joint) and not splitting the body goes; then the fewest points (0.02 pt).
nt4 = collections.Counter(); BG = [g for _, g in B]; bt = shapely.STRtree(BG)
for e_, (c, g) in enumerate(B):
    if c == 'column': continue
    nbs = [BG[j] for j in bt.query(g.buffer(0.4)) if j != e_ and BG[j].distance(g) <= 0.4]
    if pt_tree is not None: nbs += [PG[j] for j in pt_tree.query(g.buffer(0.4)) if PG[j].distance(g) <= 0.4]
    NB = unary_union(nbs) if nbs else None
    r4 = 0.15
    try:
        op = g.buffer(-r4, join_style=2, mitre_limit=5.0).buffer(r4, join_style=2, mitre_limit=5.0)
        cl = op.buffer(r4, join_style=2, mitre_limit=5.0).buffer(-r4, join_style=2, mitre_limit=5.0)
    except Exception: continue
    new = g; n0 = len(parts(g))
    for kind, diff in (('зубец', g.difference(cl)), ('выемка', cl.difference(g))):
        for x in parts(diff):
            if x.area < 1e-4: continue
            if NB is not None and x.distance(NB) <= 0.35: nt4[f'{kind}: у стыка — оставлен(а)'] += 1; continue
            cand = new.difference(x) if kind == 'зубец' else new.union(x)
            if cand.is_empty or len(parts(cand)) > n0: nt4[f'{kind}: разрезала бы тело — оставлен(а)'] += 1; continue
            new = cand; nt4[f'{kind}: убран(а)'] += 1
    if new is not g:
        ps = parts(new.buffer(0))
        if ps:
            q = max(ps, key=lambda q: q.area).simplify(0.02, preserve_topology=True)
            if q.is_valid and abs(q.area - g.area) <= 0.05 * g.area: B[e_][1] = q
print('J4c small teeth and notches (< 0.3 pt):', dict(nt4), T())
# ---------------------------------------------------------------------------------------------------------------- J5 overlaps left
# owner 06.10.2026 («6 мест, где колонна и перегородка заходят друг на друга»): what is left of an overlap of two bodies goes
# to the stronger one — a column over a capital wall over a partition; two partitions of one class overlapping — the
# smaller loses the overlap. Only small overlaps (< 2 pt², 0.5 dm²): a bigger one is a wrong body, listed by the check.
RANK = {'column': 3, 'cap': 2, 'ext': 2, 'gkl': 1, 'blk': 1}; n5 = collections.Counter()
def j5_overlaps():
    BG = [g for _, g in B]; bt = shapely.STRtree(BG)
    for e_ in range(len(B)):
        c, g = B[e_]
        for j in bt.query(g):
            if j == e_: continue
            c2, g2 = B[j]
            if not g.intersects(g2): continue
            ov = g.intersection(g2).area
            if ov <= 1e-6 or ov >= 2.0: continue
            weak = e_ if (RANK.get(c, 1), g.area) < (RANK.get(c2, 1), g2.area) else j
            strong = j if weak == e_ else e_
            cw, gw = B[weak]; cut = gw.difference(B[strong][1])
            ps = parts(cut)
            if not ps: continue
            q = max(ps, key=lambda q: q.area)
            if abs(q.area - gw.area) > ov + 0.05: continue
            B[weak][1] = q; n5[f'{B[weak][0]} уступил {B[strong][0]}'] += 1
            BG[weak] = B[weak][1]
            if weak == e_: g = B[e_][1]
j5_overlaps()
print('J5 small overlaps left to the stronger body:', dict(n5), T())
# J5b seams left: a slit between two bodies that touch (<= 0.3 pt apart; the closing of the pair by 0.3 pt minus the pair,
# in the joint zone; < 2 pt²) is filled into the weaker body — «в стенах не должно быть… разрывов»
def j5b_seams():
    n_ = 0; BG = [g for _, g in B]; bt = shapely.STRtree(BG)
    for a in range(len(B)):
        for b in bt.query(B[a][1].buffer(0.3)):
            if b <= a: continue
            ga, gb = B[a][1], B[b][1]
            if ga.distance(gb) > 0.3: continue
            zone = ga.buffer(0.35).intersection(gb.buffer(0.35)); U = ga.union(gb)
            seam = U.buffer(0.3, join_style=2).buffer(-0.3, join_style=2).difference(U).intersection(zone)
            if seam.area <= 0.005 or seam.area >= 2.0: continue
            w = a if (RANK.get(B[a][0], 1), ga.area) < (RANK.get(B[b][0], 1), gb.area) else b
            cand = B[w][1].union(seam)
            ps = parts(cand)
            if len(ps) != 1 or not ps[0].is_valid: continue
            B[w][1] = ps[0]; n_ += 1
    j5_overlaps()                                        # what the fills touched
    return n_
n5b = j5b_seams()
print('J5b seams between touching bodies filled', n5b, T())
# ---------------------------------------------------------------------------------------------------------------- J6 breaks
# test 9 (owner 06.10.2026: «в стенах не должно быть пустот, разрывов»; 07.10.2026 «делай» — «13 мест, где соседние стены
# не слились»). Two bodies 0.05–3 pt apart (2–144 mm, nearest points) with nothing between them — no door opening (its
# contour crossing the gap strip; the frame strokes beside an opening do not count), no glass, no other body across the gap — while the source draws wall strokes across the gap
# (strokes of the wall layers in the gap's volume — the hull of the two bodies' parts next to it — >= half the gap; a gap
# <= 0.5 pt, 24 mm, is no opening and needs none):
# the wall goes on there, the gap is closed. The fill: the closing of the two bodies by half the gap (mitre joins) within
# the gap's reach, its parts that touch both bodies, no larger than a bridge (1.5 × gap × the thicker wall — else it
# filled a corner); a thin body (a lining) that the closing loses, or a corner — the weaker body's end drawn on across the
# gap; it goes to the weaker body (column > cap > gkl, then the smaller). Gaps with no wall strokes in the source are
# openings and stay.
WALL_L = sheet.L('wall', 'core')     # code 010: the layers of the walls and of the core walls (roles of cfg.OCG_LAYERS)
_ws = [i for i, p in enumerate(P) if p['layer'] in WALL_L and p['kind'] in ('line', 'fill', 'wline') and not p.get('synthetic') and len(p['p']) >= 2]
_wsg = [geom(P[i]) for i in _ws]; _wst = shapely.STRtree(_wsg)
_door_ids = [i for o in objs if o['key'] == 'door' for i in o['ids'] if P[i]['kind'] == 'line' and P[i].get('synthetic') and P[i]['layer'] in DOOR_L and len(P[i]['p']) >= 2]   # the opening's contour (Э6г), not the frame strokes beside it
_dg = [geom(P[i]) for i in _door_ids]; _dt6 = shapely.STRtree(_dg) if _dg else None
# code 011 (Т9-11; №105 - the frame is part of the door): the strokes of a door's frame (коробка) - the small pieces of the
#   doors' layer, <= 2.2 pt (106 mm) long, not the arc, not the leaf - standing in a gap between two bodies are the source's
#   evidence that the wall runs on up to the door: the gap at the jamb is closed like a gap with wall strokes across it,
#   also when the contour of the opening (Э6г) passes by it (the frame is beside the opening, not the opening)
def _mrr_long(g):
    r = g.minimum_rotated_rectangle
    if r.geom_type != 'Polygon': return g.length
    c = np.array(r.exterior.coords)[:4]; return float(max(np.linalg.norm(c[1] - c[0]), np.linalg.norm(c[2] - c[1])))
_fr = [geom(P[i]) for o in objs if o['key'] == 'door' for i in o['ids']
       if P[i]['kind'] in ('line', 'fill') and not P[i].get('synthetic') and P[i]['layer'] in DOOR_L and len(P[i]['p']) >= 2]
_fr = [g for g in _fr if _mrr_long(g) <= 2.2]; _frt = shapely.STRtree(_fr) if _fr else None
n6_frame = 0
_pg6 = [g for g in (pane_geom(i) for i in panes()) if g is not None and g.area > 0]; _pt6 = shapely.STRtree(_pg6) if _pg6 else None
n6 = collections.Counter(); j6_places = []
BG = [g for _, g in B]; bt = shapely.STRtree(BG)
for a in range(len(B)):
    for b in bt.query(B[a][1].buffer(3.0)):
        if b <= a: continue
        ga, gb = B[a][1], B[b][1]; d = ga.distance(gb)
        if not (0.05 < d <= 3.0): continue
        pa_, pb_ = nearest_points(ga, gb); seg = LineString([pa_, pb_]); strip = seg.buffer(0.3, cap_style=2)
        mid = Point((pa_.x + pb_.x) / 2, (pa_.y + pb_.y) / 2)
        def _rec(why_):
            n6[why_] += 1; j6_places.append(dict(at=[round(mid.x, 1), round(mid.y, 1)], gap_mm=round(d * K), classes=[B[a][0], B[b][0]], what=why_))
        # the gap's volume: the hull of the two bodies' parts next to it, the bodies taken out
        gapz = unary_union([ga.intersection(pa_.buffer(d + 0.5)), gb.intersection(pb_.buffer(d + 0.5))]).convex_hull.difference(ga).difference(gb).buffer(0.05)
        # code 011 (Т9-11): the door's frame strokes in the gap's volume (length inside it)
        evf = sum(_fr[q].intersection(gapz).length if _fr[q].geom_type != 'Polygon' else _fr[q].intersection(gapz).area / 0.6 for q in _frt.query(gapz)) if _frt is not None else 0.0
        if evf < 0.5 * d and _dt6 is not None and any(_dg[q].intersects(strip) for q in _dt6.query(strip)): _rec('door in the gap — left'); continue
        if _pt6 is not None and any(_pg6[q].intersects(strip) for q in _pt6.query(strip)): _rec('glass in the gap — left'); continue
        others = [BG[q] for q in bt.query(seg) if q not in (a, b)]
        if others and seg.intersection(unary_union(others)).length >= 0.5 * seg.length: _rec('another body fills the gap — not a break'); continue
        ev = sum(_wsg[q].intersection(gapz).length if _wsg[q].geom_type != 'Polygon' else _wsg[q].intersection(gapz).area / 0.6 for q in _wst.query(gapz))
        if ev + evf < 0.5 * d and d > 0.5: _rec('no wall strokes across the gap — an opening, left'); continue   # <= 0.5 pt (24 mm) is no opening
        _by_frame = evf >= 0.5 * d and ev < 0.5 * d
        r_ = d / 2 + 0.05; U = ga.union(gb); reach = mid.buffer(d + 1.5)
        try: fill = U.buffer(r_, join_style=2, mitre_limit=3).buffer(-r_, join_style=2, mitre_limit=3).difference(U).intersection(reach)
        except shapely.errors.GEOSException: _rec('geometry trouble — left'); continue
        if others: fill = fill.difference(unary_union(others))
        pcs = [q for q in parts(fill) if q.intersects(ga.buffer(0.05)) and q.intersects(gb.buffer(0.05))]
        w = a if (RANK.get(B[a][0], 1), ga.area) < (RANK.get(B[b][0], 1), gb.area) else b
        tw = max(thick(ga), thick(gb)); amax = 1.5 * d * max(tw, 0.3) + 0.5   # a bridge: about the gap times the walls' thickness
        if pcs and unary_union(pcs).area > amax: pcs = []                  # the closing filled a corner, not the gap
        if not pcs:
            # the closing lost the gap (a thin body — a lining; or it filled a corner): the end of a body is drawn on. First
            # along its own axis (the long side of the minimum rectangle of its part next to the gap) to the face of the
            # other — a wall that runs on to the other; then, for a body without a clear axis, its end moved across the gap
            # and the hull of the two. Either is cut by the other body and must be no larger than a bridge.
            opts = []
            for (gw_, gs_, pw_, ps_) in (((ga, gb, pa_, pb_) if w == a else (gb, ga, pb_, pa_)), ((gb, ga, pb_, pa_) if w == a else (ga, gb, pa_, pb_))):
                endp = gw_.intersection(pw_.buffer(max(1.0, 1.5 * d)))
                if endp.is_empty or endp.area <= 1e-4: continue
                rr = endp.minimum_rotated_rectangle; cq = np.array(rr.exterior.coords)[:4]; e1 = cq[1] - cq[0]; e2 = cq[2] - cq[1]
                if np.linalg.norm(e2) > np.linalg.norm(e1): e1, e2 = e2, e1
                v_ = np.array(ps_.coords[0]) - np.array(pw_.coords[0])
                if np.linalg.norm(e1) >= 1.5 * np.linalg.norm(e2) and np.linalg.norm(e1) > 1e-6:
                    u_ = e1 / np.linalg.norm(e1); u_ = u_ if float(u_ @ v_) >= 0 else -u_; n_ = np.array([-u_[1], u_[0]])
                    if float(u_ @ (v_ / max(np.linalg.norm(v_), 1e-9))) >= 0.5:
                        Q = np.array(endp.exterior.coords) if endp.geom_type == 'Polygon' else np.vstack([np.array(q.exterior.coords) for q in parts(endp)])
                        f0 = float((Q @ u_).max()); g0, g1 = float((Q @ n_).min()), float((Q @ n_).max()); f1 = f0 + d + tw + 1.0
                        # the other body must be ahead of the end across its width (4 of 5 rays along the axis reach it)
                        # where each ray first meets the other body: the strip ends at the farthest of these (its near
                        # face) — a strip wider than the other body's end does not run on past it (test 9: a 48 mm stub)
                        hd_ = []
                        for gg in np.linspace(g0 + 0.1 * (g1 - g0), g1 - 0.1 * (g1 - g0), 5):
                            xr = LineString([tuple(u_ * (f0 - 0.05) + n_ * gg), tuple(u_ * f1 + n_ * gg)]).intersection(gs_)
                            if not xr.is_empty: hd_.append(min(float(np.array(c_) @ u_) for q_ in getattr(xr, 'geoms', [xr]) for c_ in (q_.exterior.coords if q_.geom_type == 'Polygon' else q_.coords)))
                        if len(hd_) >= 4:
                            fc_ = max(hd_) + 0.05
                            strip_ = Polygon([tuple(u_ * (f0 - 0.05) + n_ * g0), tuple(u_ * fc_ + n_ * g0), tuple(u_ * fc_ + n_ * g1), tuple(u_ * (f0 - 0.05) + n_ * g1)])
                            # up to the other body's near face: the part of the strip minus it that touches the extended body
                            cut_ = [q for q in parts(strip_.difference(gs_).difference(gw_)) if q.distance(gw_) <= 0.05]
                            if cut_: opts.append(unary_union(cut_))
                mov = shapely.affinity.translate(endp, xoff=float(v_[0]) * 1.05, yoff=float(v_[1]) * 1.05)
                opts.append(unary_union([endp, mov]).convex_hull.difference(gw_).difference(gs_))
            pcs = []
            for ext_ in opts:
                if others: ext_ = ext_.difference(unary_union(others))
                pc_ = [q for q in parts(ext_) if q.intersects(ga.buffer(0.05)) and q.intersects(gb.buffer(0.05))]
                if pc_ and unary_union(pc_).area <= amax: pcs = pc_; break
            if not pcs: _rec('no bridge of a wall\'s size joins them — left'); continue
        add = unary_union(pcs)
        cand = B[w][1].union(add.buffer(0.01, join_style=2)).buffer(-0.01, join_style=2).union(B[w][1])
        ps = parts(cand)
        if len(ps) != 1 or not ps[0].is_valid: _rec('the fill would split the body — left'); continue
        B[w][1] = ps[0]; BG[w] = ps[0]; n6['closed'] += 1
        if _by_frame: n6['closed by the door frame strokes (Т9-11)'] += 1
        j6_places.append(dict(at=[round(mid.x, 1), round(mid.y, 1)], gap_mm=round(d * K), classes=[B[a][0], B[b][0]], what='closed' + (' (door frame, Т9-11)' if _by_frame else ''), to=B[w][0], area_pt2=round(add.area, 3)))
j5_overlaps()
n6b = j5b_seams()                                        # the seams the closed breaks leave at the other body's face
print('J6 breaks between bodies:', dict(n6), '| seams after them filled', n6b, T())
# ---------------------------------------------------------------------------------------------------------------- J4d short edges
# test 9 (owner 07.10.2026 «делай» — «585 коротких рёбер (лист 11)»; 06.10.2026 «в стенах не должно быть… мелких
# неровностей»). What the steps above leave on an outline (bodies J0b could not straighten — arcs, self-crossing — and the
# cuts and fills of J1–J6): chains of short edges between two longer runs. Two passes: the fine one — edges shorter than
# 0.3 pt (14 mm at 1:100), whatever the source draws there (a feature that small is noise at the drawing's scale); the
# coarse one — edges shorter than 0.6 pt (29 mm) that the source does not draw (no stroke or fill edge of the drawing —
# the wall's or of what it meets: a room, equipment, a frame, glazing, a door; furniture, dimensions, axes not counted —
# along >= half of the edge within 0.08 pt, parallel within 10°: the artifact of the build, not the client's wall). In a chain:
#  - spike or tooth: the two runs on one line (<= 5°, the lines <= 0.02 pt — 1 mm — apart), the chain's depth <= half the
#    wall's thickness: the chain goes, the face runs on straight;
#  - step: the runs parallel (<= 5°), offset s <= min(tau, a quarter of the wall's thickness): one run moves onto the line
#    of the other, its far end sliding along its next edge (no tilt: the face keeps its direction) — the run the source
#    draws stays (its strokes along >= half of it), the other moves; both drawn — the source draws two faces: 10 mm apart
#    or more (0.2 pt: a finish, a lining) the step is the client's and stays, closer — a drafting slip, the shorter moves
#    onto the longer, as when neither is drawn; a deeper step is a change of the wall and stays;
#  - noisy corner: the runs at an angle (5°–160°) and every vertex of the chain within tau of the point where the two run
#    lines meet: the chain becomes that point (a sharp corner; on an arc — one vertex of the arc); else a chain shorter
#    than tau in all is one vertex, its middle (the jitter of an arc);
#  - a wall's end (the runs turn back, >= 160°) stays.
# A chain at a joint (another body, a glass pane, or equipment, a window frame, plumbing the source fills <= 0.35 pt —
# test 9: a face moved over the convectors along the facade) changes only when the joint stays as it is (overlap and seam
# not larger); the outline must stay valid and move by <= tau (+ the step). Columns stay as the source draws them.
TAU = 0.3; TAU2 = 0.6
# what the source draws along a face: every stroke and fill edge of the drawing — the wall's own, and the edges of what
# a wall meets (a room's fill ends at the wall's face; equipment, a window frame, glazing, a door, plumbing, a node) —
# but furniture, dimensions, axes, sprinklers and annotations, which lie over the walls without being their edges
# code 010: the layers not counted - by the roles of cfg.OCG_LAYERS (furniture, plants, dimensions, fire valves («sprinklers»
#   <one example: client-b>), room tags, axes) - in v008 these were the names of the client-b layers
EDGE_X = sheet.L('furniture', 'plant', 'dim', 'fire', 'tag', 'axis')
def _edge_layer(l): return l not in EDGE_X
_dsg = [geom(p) for p in P if _edge_layer(p['layer']) and p['kind'] in ('line', 'fill', 'wline') and not p.get('synthetic') and len(p['p']) >= 2]
_dst = shapely.STRtree(_dsg)
# the elements a face must not run into (nor away from, when it touches them): equipment, frames, plumbing
_eg = [g for g in (geom(p) for p in P if p['layer'] in sheet.L('equipment', 'facade_frame', 'sanitary') and p['kind'] == 'fill' and not p.get('synthetic') and len(p['p']) >= 3) if g.geom_type == 'Polygon' and g.area > 0.01]
_et = shapely.STRtree(_eg) if _eg else None
def _inter(p1, u1, p2, u2):
    M = np.array([u1, -u2]).T
    if abs(np.linalg.det(M)) < 1e-9: return None
    s_ = np.linalg.solve(M, p2 - p1); return p1 + s_[0] * u1
def cover(a, b):
    """the share of the edge a–b the source draws: wall strokes or fill edges along it (within 0.08 pt, parallel within 10°)"""
    e = LineString([tuple(a), tuple(b)]); L_ = e.length
    if L_ < 1e-9: return 1.0
    u = (np.asarray(b) - np.asarray(a)) / L_; zone = e.buffer(0.08, cap_style=2); s_ = 0.0
    for q in _dst.query(zone):
        x = _dsg[q]; x = x.boundary if x.geom_type == 'Polygon' else x
        it = x.intersection(zone)
        for pc in getattr(it, 'geoms', [it]):
            if pc.geom_type != 'LineString' or pc.length < 1e-6: continue
            v = np.array(pc.coords[-1]) - np.array(pc.coords[0]); v = v / np.linalg.norm(v)
            if abs(float(u @ v)) >= 0.985: s_ += pc.length
    return min(1.0, s_ / L_)
def drawn(a, b, cov=0.5): return cover(a, b) >= cov
def _chain_opts(cr, t_, tau, undrawn):
    """the changes a ring allows, one per chain of short edges: (new ring, kind, how far the outline moves, the vertices touched)"""
    m = len(cr)
    if m < 5: return []
    L = [float(np.linalg.norm(cr[(i + 1) % m] - cr[i])) for i in range(m)]
    sh = [x < tau for x in L]
    if all(sh) or not any(sh): return []
    out = []
    for i in range(m):
        if not (sh[i] and not sh[i - 1]): continue
        j = i; ch = []
        while sh[j % m] and len(ch) < m: ch.append(j % m); j += 1
        ea, eb = (i - 1) % m, j % m
        A0, A1, B0, B1 = cr[ea], cr[i], cr[eb], cr[(eb + 1) % m]
        ua = (A1 - A0) / L[ea]; ub = (B1 - B0) / L[eb]; an = _ang(ua, ub)
        cv = [(i + q) % m for q in range(len(ch) + 1)]                          # the chain's vertices: A1 .. B0
        if len(set(cv) | {ea, (eb + 1) % m}) < len(cv) + 2: continue           # the ring is the chain
        if undrawn and any(drawn(cr[q], cr[(q + 1) % m]) for q in ch): continue  # the source draws it: the client's wall
        na = np.array([-ua[1], ua[0]]); s_ = abs(float((B0 - A1) @ na))
        dev = max(abs(float((cr[q] - A1) @ na)) for q in cv)
        def ring_wo(rem, ins, at):
            nr = [cr[q] for q in range(m) if q not in rem]
            k_ = sum(1 for q in range(at) if q not in rem); nr.insert(k_, ins); return nr
        if an <= 5.0:
            if s_ <= 0.02:
                if dev > max(0.5 * t_, TAU): continue                            # deeper than half the wall: a niche, not a tooth
                nr = [cr[q] for q in range(m) if q not in set(cv)]
                out.append((nr, 'выступ или зубец на прямой грани', dev, cv)); continue
            if s_ > min(tau, 0.25 * t_): continue                                # a change of the wall's thickness
            # which face stays: the one the source draws (its stroke along >= half of the run); both drawn — the source
            # draws the step itself (two faces of the client's wall), it stays; neither — the shorter run moves
            dA, dB = drawn(A0, A1), drawn(B0, B1)
            if dA and dB and s_ > 0.2: continue                                  # two drawn faces >= 10 mm apart: a finish, a lining
            if (dB and not dA) or (dA == dB and L[ea] <= L[eb]):                 # A moves onto B's line
                ep = (ea - 1) % m; up = cr[ea] - cr[ep]
                if np.linalg.norm(up) < 1e-9: continue
                X = _inter(cr[ep], up / np.linalg.norm(up), B0, ub)
                if X is None or np.linalg.norm(X - A0) > 3 * s_ + 1e-6: continue
                rem = set(cv) | {ea}; out.append((ring_wo(rem, X, min(rem, key=lambda q: (q - ea) % m)), 'ступенька: короткий участок грани — на линию длинного', s_, sorted(rem)))
            else:                                                                # B moves onto A's line
                en = (eb + 1) % m; un = cr[(en + 1) % m] - cr[en]
                if np.linalg.norm(un) < 1e-9: continue
                X = _inter(A1, ua, cr[en], un / np.linalg.norm(un))
                if X is None or np.linalg.norm(X - B1) > 3 * s_ + 1e-6: continue
                rem = set(cv) | {en}; out.append((ring_wo(rem, X, i), 'ступенька: короткий участок грани — на линию длинного', s_, sorted(rem)))
            continue
        if an >= 160.0: continue                                                 # a wall's end
        X = _inter(A1, ua, B0, ub)
        if X is not None and max(float(np.linalg.norm(cr[q] - X)) for q in cv) <= tau and float((X - A0) @ ua) > 0.5 * L[ea] and float((B1 - X) @ ub) > 0.5 * L[eb]:
            out.append((ring_wo(set(cv), X, i), 'угол из мелких рёбер — в точку пересечения граней', max(float(np.linalg.norm(cr[q] - X)) for q in cv), cv)); continue
        if sum(L[q] for q in ch) < tau:
            M_ = np.mean([cr[q] for q in cv], axis=0)
            out.append((ring_wo(set(cv), M_, i), 'дрожь дуги — мелкие рёбра в одну точку', max(float(np.linalg.norm(cr[q] - M_)) for q in cv), cv))
    return out
n4d = collections.Counter()
for tau, undrawn, tag in ((TAU, False, 'до 14 мм'), (TAU2, True, '14–29 мм, исходник не рисует')):
    BG = [g for _, g in B]; bt = shapely.STRtree(BG)
    for e_, (c, g) in enumerate(B):
        if c == 'column': continue
        nbs = [BG[j] for j in bt.query(g.buffer(0.35)) if j != e_ and BG[j].distance(g) <= 0.35]
        if pt_tree is not None: nbs += [PG[j] for j in pt_tree.query(g.buffer(0.35)) if PG[j].distance(g) <= 0.35]
        if _et is not None: nbs += [_eg[j] for j in _et.query(g.buffer(0.35)) if _eg[j].distance(g) <= 0.35]
        cur = g; t_ = thick(g); bad = set()
        for it_ in range(400):
            rings = [[np.array(v) for v in cur.exterior.coords[:-1]]] + [[np.array(v) for v in h.coords[:-1]] for h in cur.interiors]
            done = False
            for ri in range(len(rings)):
                for nr, kind, mv, touched in _chain_opts(rings[ri], t_, tau, undrawn):
                    key_ = (ri, tuple(np.round(rings[ri][touched[0]], 5)), kind)
                    if key_ in bad: continue
                    rr = [nr if k2 == ri else rings[k2] for k2 in range(len(rings))]
                    try: cand = Polygon([tuple(v) for v in rr[0]], [[tuple(v) for v in h] for h in rr[1:] if len(h) >= 3])
                    except Exception: bad.add(key_); continue
                    if not cand.is_valid or cand.is_empty or cand.hausdorff_distance(cur) > tau + mv + 0.02: bad.add(key_); n4d[f'{tag}: оставлено — контур пересёк бы себя или ушёл'] += 1; continue
                    loc = LineString([tuple(rings[ri][q]) for q in touched] + [tuple(rings[ri][touched[-1]])]) if len(touched) > 1 else Point(rings[ri][touched[0]])
                    near = [gb for gb in nbs if gb.distance(loc) <= 0.35 + tau]
                    if near and any(o1 > o0 + 1e-3 or q1 > q0 + 1e-3 for (o0, q0), (o1, q1) in zip(joint_state(cur, near), joint_state(cand, near))):
                        bad.add(key_); n4d[f'{tag}: оставлено у стыка — стык изменился бы'] += 1; continue
                    cur = cand; n4d[f'{tag}: {kind}'] += 1; done = True; break
                if done: break
            if not done: break
        B[e_][1] = cur
print('J4d short edges between longer runs:', dict(n4d), T())
# final pass: the cuts and fills of J4c–J5b leave vertices on straight runs and small holes — 3.1 and the holes again
dfin = collections.Counter(); nv40_, nv41_ = nv40, nv41
BG = [g for _, g in B]; bt = shapely.STRtree(BG)
for e_, (c, g) in enumerate(B): fewest(e_, c, g, BG, bt, dfin)
nv40, nv41 = nv40_, nv41_
print('final pass (3.1 and holes after J4c–J5b):', dict(dfin), T())
# ---------------------------------------------------------------------------------------------------------------- check
W['bodies'] = [(c, g) for c, g in B]
after_b, pl_b2 = measure_bodies(); after_p, pl_p2 = measure_panes()
after_k = measure_kinks(); print('after: glass kinks', dict(after_k))
SOL = unary_union([g for _, g in B] + [pane_geom(i) for i in panes() if pane_geom(i) is not None])
# J3 fix: an end of a door contour within 0.6 pt of the element it meets is moved along the line onto that element's
# outline (the line keeps its direction — it stays on the wall face)
nj3 = 0; SB = SOL.boundary
for p in P:
    if not (p['kind'] == 'line' and p.get('synthetic') and p['layer'] in DOOR_L and len(p['p']) == 2): continue
    a_, b_ = np.array(p['p'][0], float), np.array(p['p'][1], float); u_ = b_ - a_; L_ = np.linalg.norm(u_)
    if L_ < 1e-6: continue
    u_ = u_ / L_; new_ = [a_, b_]
    for e, (pt, sg) in enumerate(((a_, -1), (b_, 1))):
        d = SOL.distance(Point(pt))
        if d <= 0.005 or d > 0.6: continue
        ray = LineString([tuple(pt - sg * u_ * 0.6), tuple(pt + sg * u_ * 0.6)]); x = ray.intersection(SB)
        pts = [np.array(q.coords[0]) for q in getattr(x, 'geoms', [x]) if q.geom_type == 'Point']
        if pts: new_[e] = min(pts, key=lambda q: np.linalg.norm(q - pt)); nj3 += 1
    p['p'] = [tuple(map(float, new_[0])), tuple(map(float, new_[1]))]
print('J3: door contour ends put on the element', nj3, T())
door_ends = collections.Counter()
for p in P:
    if p['kind'] == 'line' and p.get('synthetic') and p['layer'] in DOOR_L:
        for v in (p['p'][0], p['p'][-1]):
            d = SOL.distance(Point(v)); door_ends['на торце элемента (≤ 0,05 pt)' if d <= 0.05 else 'в 0,05–0,6 pt от торца' if d <= 0.6 else 'вдали от стены (дверь без стены рядом)'] += 1
print('after: bodies', dict(after_b), '| panes', dict(after_p), '| door contour ends', dict(door_ends), T())
pickle.dump(W, open('walls_j.pkl', 'wb'))
D1 = dict(D0); D1['P'] = P; pickle.dump(D1, open('prims_j.pkl', 'wb'))
pickle.dump(O, open('objects.pkl', 'wb'))
json.dump(dict(before=dict(bodies=dict(before_b), panes=dict(before_p), glass_kinks=dict(before_k)), after=dict(bodies=dict(after_b), panes=dict(after_p), glass_kinks=dict(after_k)),
               glass='per pane: the triangles of a pane merged into one segment (test 9); kinks between straight panes — see glass_kinks',
               breaks=dict(n6), breaks_seams_filled=n6b, breaks_places=j6_places[:100], short_edges_j4d=dict(n4d),
               fixes=dict(vertices_snapped=nsnap, overlaps_cut=nov, gaps_closed=ngap, pane_ends_fitted=np2, pane_ends_not_ahead=nj2_void), fewest_points=dict(vertices_before=nv40, vertices_after=nv41, **d4), micro_steps=dict(nms), small_teeth=dict(nt4), overlaps_left=dict(n5), seams_filled=n5b, final_pass=dict(dfin), straight_sides=dict(vertices_before=nvr0, vertices_after=nvr1, **nreg), core_walls=dict(bodies=ncore, outline_lines_taken=core_absorbed),
               bridges=[{k: v for k, v in b_.items() if k != 'band'} for b_ in bridges],
               door_contour_ends=dict(door_ends),
               places_before=dict(bodies=pl_b[:120], panes=pl_p[:120]), places_after=dict(bodies=pl_b2[:120], panes=pl_p2[:120])),
          open('joints.json', 'w'), ensure_ascii=False, indent=1)
