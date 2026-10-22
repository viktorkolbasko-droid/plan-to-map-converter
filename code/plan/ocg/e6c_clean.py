"""Э6в (owner 06.10.2026): straight walls with the fewest points. Rules — plan/rules/50 §9 (geomfix) and plan/rules/60 §4,
3.1 «минимум точек», and the owner's check: an irregularity of a wall outline smaller than the wall's thickness is
suspected not to exist — it is re-checked against the source and removed if the source does not draw it.
For every wall body (gkl, blk, cap; columns are the source's own fills and stay):
 1. irregularities — notches (closing of the body with radius r adds them) and teeth (opening removes them),
    r = min(0.35 pt, t / 3), t = 2A/P of the body; a piece counts if its area >= 0.01 pt² and it is no longer and no
    deeper than the wall thickness t (a long thin piece is a real thin wall, not an irregularity);
 2. re-check: the piece's own outline (the part off the smoothed outline) is drawn in the source if >= 70 % of it lies
    within 0.08 pt of the wall-layer outline lines (hatch strokes and plaster ticks are not outline). Drawn — kept;
    not drawn — an artifact of the face assembly (hatch ends, connectors): the notch is filled / the tooth cut,
    never into a neighbour body;
 3. fewest points — a vertex whose deviation from the line through its neighbours is <= 0.02 pt (1 mm) is dropped
    (Douglas–Peucker, topology kept), as 3.1.
v3 (owner 06.10.2026: «248 неровностей тоньше стены, нарисованных в исходнике, оставить или выпрямлять?… Если на одной прямой
стене много неровностей, большая вероятность, что это погрешность рисовки. Если одна неровность, то нужно проверить и
попытаться распознать, что это ниша, какой-то дополнительный элемент»): the irregularities of one straight side of a body
(the side of the body simplified at 0.6 t) are counted together, drawn in the source or not:
 - >= 2 on one side — a drawing error: all straightened;
 - one — recognised and kept when an element of another kind is drawn at it (<= 0.3 pt: doors, frames, glazing,
   sanitary, heating, equipment, generic models, lifts — ELEM_L, a setting of the floor) or it is a niche (a notch
   >= 300 mm wide, >= 50 mm deep); otherwise straightened when it is shallower than half the wall, kept and listed for
   review when deeper.
Reads walls.pkl, prims.pkl; writes walls_clean.pkl (same structure, bodies cleaned) and walls_clean.json (report).
usage: python3 e6c_clean.py   (run in the sheet folder after e6_walls.py)"""
import pickle, json, math, collections, time, sys
import numpy as np, shapely
from shapely.geometry import LineString, Polygon, MultiPolygon
from shapely.ops import unary_union
import os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import sheet
t0 = time.time(); K = sheet.K
W = pickle.load(open('walls.pkl', 'rb')); B = W['bodies']; H = W['hatch']
P = pickle.load(open('prims.pkl', 'rb'))['P']
WALL_L = sheet.L('wall', 'core')
# source outline: wall-layer lines and fill outlines minus hatch strokes
segs = []
for p in P:
    if p['layer'] not in WALL_L or len(p['p']) < 2: continue
    q = p['p'] + ([p['p'][0]] if p['kind'] == 'fill' else [])
    for a, b in zip(q[:-1], q[1:]):
        if math.dist(a, b) > 1e-3: segs.append(LineString([a, b]))
HB = unary_union([h.buffer(0.03) for h in H])
# elements of other kinds that explain an irregularity of a wall (a setting of the floor: its layer names)
ELEM_L = sheet.ELEM_L      # cfg.OCG_ELEM_L
EG = [LineString(p['p'] + ([p['p'][0]] if p['kind'] == 'fill' else [])) for p in P if p['layer'] in ELEM_L and len(p['p']) >= 2]
EL_ = [p['layer'] for p in P if p['layer'] in ELEM_L and len(p['p']) >= 2]; et_ = shapely.STRtree(EG) if EG else None
def element_at(x, d=0.3):
    if et_ is None: return None
    js = [j for j in et_.query(x.buffer(d)) if EG[j].distance(x) <= d]
    return collections.Counter(EL_[j] for j in js).most_common(1)[0][0] if js else None
st = shapely.STRtree(segs); ht = shapely.STRtree([h for h in H])
def outline_near(g, tol=0.08):
    """length of g within tol of a source outline segment that is not a hatch stroke"""
    near = [segs[j] for j in st.query(g.buffer(tol))]
    if not near: return 0.0
    U = unary_union([s.buffer(tol, cap_style=2) for s in near])
    hs = [H[j] for j in ht.query(g.buffer(tol))]
    if hs: U = U.difference(unary_union([h.buffer(0.03) for h in hs]))
    return g.intersection(U).length
def ring_n(g): return sum(len(r.coords) - 1 for q in getattr(g, 'geoms', [g]) for r in [q.exterior, *q.interiors])
def straight_vertices(g, dev=0.02, turn=10.0):
    """vertices on a straight run: deviation <= dev with turn <= turn deg, or turn <= 0.5 deg (3.1)"""
    n = 0
    for q in getattr(g, 'geoms', [g]):
        for r in [q.exterior, *q.interiors]:
            c = np.array(r.coords)[:-1]; m = len(c)
            for i in range(m):
                a, b, d = c[i - 1], c[i], c[(i + 1) % m]
                u, v = b - a, d - b; lu, lv = np.linalg.norm(u), np.linalg.norm(v)
                if lu < 1e-9 or lv < 1e-9: n += 1; continue
                ang = math.degrees(math.acos(max(-1.0, min(1.0, (u @ v) / lu / lv))))
                w = d - a; lw = np.linalg.norm(w)
                h_ = abs(w[0] * (b - a)[1] - w[1] * (b - a)[0]) / lw if lw > 1e-9 else 0.0
                if ang <= 0.5 or (h_ <= dev and ang <= turn): n += 1
    return n
J = dict(m=2, ml=10.0)
def close_(g, r): return g.buffer(r, join_style=J['m'], mitre_limit=J['ml']).buffer(-r, join_style=J['m'], mitre_limit=J['ml'])
def open_(g, r): return g.buffer(-r, join_style=J['m'], mitre_limit=J['ml']).buffer(r, join_style=J['m'], mitre_limit=J['ml'])
out = []; rep = collections.Counter(); places = []
allb = [g for _, g in B]; bt = shapely.STRtree(allb)
v_before = v_after = s_before = s_after = 0
for k, (c, g0) in enumerate(B):
    if c == 'column': out.append((c, g0)); continue
    v_before += ring_n(g0); s_before += straight_vertices(g0)
    t = 2 * g0.area / g0.length if g0.length > 0 else 0.0; r = min(0.35, t / 3)
    g = g0
    if r >= 0.05:
        others = unary_union([allb[j] for j in bt.query(g0.buffer(0.5)) if j != k])
        sm_c = close_(g0, r); sm_o = open_(g0, r)
        cand = []
        for kind, diff in (('выемка', sm_c.difference(g0)), ('зубец', g0.difference(sm_o))):
            for x in getattr(diff, 'geoms', [diff]):
                if x.geom_type != 'Polygon' or x.area < 0.01: continue
                rr = x.minimum_rotated_rectangle; cc = np.array(rr.exterior.coords)
                L_, W_ = sorted((np.linalg.norm(cc[1] - cc[0]), np.linalg.norm(cc[2] - cc[1])), reverse=True)
                if L_ > max(t, 0.5) or W_ > max(t, 0.5): rep['не неровность: длинный или глубокий кусок (настоящая стена)'] += 1; continue
                # the piece's own outline: its boundary minus the smoothed outline
                own = x.boundary.difference((sm_c if kind == 'выемка' else sm_o).boundary.buffer(0.02))
                L_own = own.length
                drawn = outline_near(own) / L_own if L_own > 1e-6 else 1.0
                if not others.is_empty and x.distance(others) <= 0.05: rep[f'{kind}: у соседнего тела (стык) — не тронута'] += 1; continue
                cand.append((kind, x, L_, W_, drawn))
        # the straight sides of the body: its outline simplified at 0.6 t; irregularities counted per side
        ref = g0.simplify(max(0.6 * t, 0.15), preserve_topology=True); sides = []
        for q in getattr(ref, 'geoms', [ref]):
            if q.geom_type != 'Polygon': continue
            for rg in [q.exterior, *q.interiors]:
                cq = list(rg.coords); sides += [LineString([cq[i], cq[i + 1]]) for i in range(len(cq) - 1)]
        by_side = collections.defaultdict(list)
        for j, (kind, x, L_, W_, drawn) in enumerate(cand):
            e = min(range(len(sides)), key=lambda i: sides[i].distance(x.centroid)) if sides else -1
            by_side[e].append(j)
        for e, js in by_side.items():
            for j in js:
                kind, x, L_, W_, drawn = cand[j]
                if len(js) >= 2: fix, why = True, f'{kind}: {len(js)} на одной прямой стороне — погрешность рисовки, выпрямлена'
                else:
                    el = element_at(x)
                    if el: fix, why = False, f'{kind}: одна, у элемента «{el}» — оставлена'
                    elif kind == 'выемка' and L_ * K >= 300 and W_ * K >= 50: fix, why = False, f'{kind}: одна, ниша >= 300 мм — оставлена'
                    elif drawn < 0.7: fix, why = True, f'{kind}: одна, нет в исходнике — исправлена'
                    elif W_ < 0.5 * t: fix, why = True, f'{kind}: одна, мельче половины стены, не распознана — выпрямлена'
                    else: fix, why = False, f'{kind}: одна, не распознана, глубже половины стены — оставлена, на перепроверку'
                rep[why] += 1
                if fix: g = g.union(x) if kind == 'выемка' else g.difference(x)
                if len(places) < 800: places.append(dict(kind=kind, why=why, at=[round(x.centroid.x, 1), round(x.centroid.y, 1)], area_pt2=round(x.area, 3),
                                                        size_mm=[round(L_ * K), round(W_ * K)], wall_t_mm=round(t * K), drawn=round(drawn, 2), fixed=fix))
    g = g.buffer(0)
    g = g.simplify(0.02, preserve_topology=True)
    for x in getattr(g, 'geoms', [g]):
        if x.geom_type == 'Polygon' and x.area > 0.05:
            out.append((c, x)); v_after += ring_n(x); s_after += straight_vertices(x)
W2 = dict(W); W2['bodies'] = out
pickle.dump(W2, open('walls_clean.pkl', 'wb'))
a0 = unary_union([g for _, g in B]); a1 = unary_union([g for _, g in out])
res = dict(vertices_before=v_before, vertices_after=v_after, straight_run_vertices_before=s_before, straight_run_vertices_after=s_after,
           irregularities=dict(rep), area_added_pt2=round(a1.difference(a0).area, 2), area_removed_pt2=round(a0.difference(a1).area, 2),
           places=places)
json.dump(res, open('walls_clean.json', 'w'), ensure_ascii=False, indent=1)
print('vertices', v_before, '->', v_after, '| on straight runs', s_before, '->', s_after)
for kk, vv in sorted(rep.items()): print(' ', kk, vv)
print('area added', res['area_added_pt2'], 'pt2 removed', res['area_removed_pt2'], 'pt2', round(time.time() - t0, 1), 's')
