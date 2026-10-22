"""Э3: scale mm/pt two independent ways and the origin from the axes.
 A. Every number on the layers of the role 'dim' (cfg.OCG_LAYERS): its dimension line (nearest long segment parallel to the
    text), the two extension stubs crossing it (perpendicular, an end within 1.5 pt of the line); measured = distance between
    the stubs; mm/pt = value / measured.
 B. Desks of a known size: grey desk fills (cfg.OCG_DESK_TOP) nearest to the labels cfg.OCG_SCALE_DESK['label'], their
    rotated rectangle sides = cfg.OCG_SCALE_DESK['mm'] <one example: client-b, «140x90» = 1400 x 900 mm>.
 Origin: the axes cfg.OCG_ORIGIN_AXES[1] and [2] crossing the axis [0] (fit lines through the axis dash chains); code 012: two
 names (a, b) - the crossing a × b (row 184: the first axes of the two families, start_ocg.py checks the pair).
 Code 009: scale.json is compared with cfg.MM_PER_PT and cfg.ORIGIN_PT by ocg/start_ocg.py --after-e3 (stop when off)."""
import pickle, math, re, json, sys, os, numpy as np, pymupdf
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import sheet
from shapely.geometry import Polygon, Point
from shapely.ops import unary_union
dr = pickle.load(open('drawings_ext.pkl', 'rb'))
d = pymupdf.open(sheet.PDF); words = d[0].get_text('words')
def segs_of(layers):
    out = []
    for x in dr:
        if x.get('layer') not in layers or x['type'] in ('clip', 'group'): continue
        for it in x['items']:
            if it[0] == 'l':
                a = np.array([it[1].x, it[1].y]); b = np.array([it[2].x, it[2].y])
                if np.linalg.norm(b - a) > 0.05: out.append((a, b))
    return out
S = segs_of(sheet.full('dim'))
res = []
for w in words:
    if not re.fullmatch(r'\d{3,5}', w[4]): continue
    v = float(w[4]); c = np.array([(w[0] + w[2]) / 2, (w[1] + w[3]) / 2])
    # text direction from the line it sits on: candidates = long segments within 6 pt of the text centre
    best = None
    for a, b in S:
        L = np.linalg.norm(b - a)
        if L < 8: continue
        u = (b - a) / L; n = np.array([-u[1], u[0]])
        dn = abs((c - a) @ n); t = (c - a) @ u
        if dn < 6 and -2 < t < L + 2 and (best is None or dn < best[0]): best = (dn, a, b, u, n, L)
    if best is None: continue
    _, a, b, u, n, L = best
    stubs = []
    for p, q in S:
        l2 = np.linalg.norm(q - p)
        if l2 < 0.8 or l2 > 12: continue
        e = (q - p) / l2
        if abs(e @ u) > 0.05: continue                         # perpendicular to the dimension line
        for end in (p, q):
            if abs((end - a) @ n) < 1.5:                       # an end on (near) the dimension line
                t = (end - a) @ u
                if -1 < t < L + 1: stubs.append(t)
    if len(stubs) < 2: continue
    stubs = sorted(set(round(s, 2) for s in stubs))
    meas = stubs[-1] - stubs[0]
    if meas < 3: continue
    res.append(dict(text=w[4], value=v, line_pt=round(L, 2), measured_pt=round(meas, 3), stubs=len(stubs), mm_per_pt=round(v / meas, 3), at=[round(c[0], 1), round(c[1], 1)]))
if len(res) >= 3:                  # code 009: a sheet without measured dimensions - the scale is not measured, start_ocg.py stops
    k = np.array([r['mm_per_pt'] for r in res])
    med = float(np.median(k)); mad = float(np.median(np.abs(k - med)))
    inl = [r for r in res if abs(r['mm_per_pt'] - med) <= max(3 * 1.4826 * mad, 0.2)]
    ki = np.array([r['mm_per_pt'] for r in inl])
    A = dict(n_numbers=len(res), n_inliers=len(inl), median=round(med, 3), mean_inliers=round(float(ki.mean()), 3), std_inliers=round(float(ki.std()), 3),
             p05_p95=[round(float(np.percentile(ki, 5)), 3), round(float(np.percentile(ki, 95)), 3)])
    # regression value ~ measured (through 0) on inliers
    x = np.array([r['measured_pt'] for r in inl]); y = np.array([r['value'] for r in inl])
    A['regression_through_0'] = round(float((x @ y) / (x @ x)), 3)
    A['resid_mm_p95'] = round(float(np.percentile(np.abs(y - A['regression_through_0'] * x), 95)), 1)
else: A = dict(n_numbers=len(res), n_inliers=0, median=None)
# B. desks of a known size (cfg.OCG_SCALE_DESK: the label and its sides, mm; the grey of the top - cfg.OCG_DESK_TOP)
FURN = sheet.full('furniture'); SD = sheet.SCALE_DESK or {}; DL, (DLONG, DSHORT) = SD.get('label', ''), tuple(SD.get('mm', (1, 1)))
fills = []
for xd in dr:
    if xd.get('layer') not in FURN or 'f' not in xd['type'] or not xd.get('fill'): continue
    for it in xd['items']: pass
labels = [w for w in words if DL and w[4].lower().replace('х', 'x') == DL]
from collections import defaultdict
# desk fills: union of the grey triangle meshes per drawing near each label
B = []
for w in labels:
    c = Point((w[0] + w[2]) / 2, (w[1] + w[3]) / 2)
    polys = []
    for xd in dr:
        if xd.get('layer') not in FURN or 'f' not in xd['type'] or not xd.get('fill'): continue
        r = xd['rect']
        if r.x1 < c.x - 25 or r.x0 > c.x + 25 or r.y1 < c.y - 25 or r.y0 > c.y + 25: continue
        if abs(xd['fill'][0] - sheet.DESK_TOP[0]) > 0.02: continue
        pts = []; ps = []
        for it in xd['items']:
            if it[0] == 'l': pts.append((it[1].x, it[1].y)); pts.append((it[2].x, it[2].y))
        # triangles as consecutive point triples of closed subpaths
        q = [(it[1].x, it[1].y) for it in xd['items'] if it[0] == 'l']
        for i in range(0, len(q) - 2, 3):
            try:
                pg = Polygon(q[i:i + 3])
                if pg.is_valid and pg.area > 0: ps.append(pg)
            except Exception: pass
        if ps: polys.append(unary_union(ps).buffer(0.02).buffer(-0.02))
    if not polys: continue
    U = unary_union(polys)
    parts = list(getattr(U, 'geoms', [U]))
    best = None
    for p in parts:
        if p.area < 50: continue
        rr = p.minimum_rotated_rectangle; xy = np.array(rr.exterior.coords)[:4]
        e = sorted([np.linalg.norm(xy[(i + 1) % 4] - xy[i]) for i in range(2)])
        dist = p.distance(c)
        if best is None or dist < best[0]: best = (dist, e, p.area / rr.area)
    if best and best[0] < 5:
        B.append(dict(at=[round(c.x, 1), round(c.y, 1)], short_pt=round(best[1][0], 2), long_pt=round(best[1][1], 2), fill=round(best[2], 2),
                      mm_per_pt_long=round(DLONG / best[1][1], 2), mm_per_pt_short=round(DSHORT / best[1][0], 2)))
# origin from axes
AX = segs_of(sheet.full('axis'))
def axis_line(label):
    w = [w for w in words if w[4] == label][0]; c = np.array([(w[0] + w[2]) / 2, (w[1] + w[3]) / 2])
    best = None
    for a, b in AX:
        L = np.linalg.norm(b - a)
        if L < 5: continue
        u = (b - a) / L; n = np.array([-u[1], u[0]]); off = n @ a
        if abs(n @ c - off) > 12: continue
        if min(np.linalg.norm(a - c), np.linalg.norm(b - c)) > 200: continue
        pts = [q for p1, p2 in AX for q in (p1, p2) if abs(n @ q - off) < 0.6 and abs(abs(((p2 - p1) / max(np.linalg.norm(p2 - p1), 1e-9)) @ u) - 1) < 2e-3]
        if best is None or len(pts) > len(best): best = pts
    P = np.array(best); m = P.mean(0); _, _, vt = np.linalg.svd(P - m)
    return m, vt[0], len(P), float(np.ptp(P @ vt[0]))
def cross(l1, l2):
    (m1, d1, *_), (m2, d2, *_) = l1, l2
    t = np.linalg.solve(np.array([d1, -d2]).T, m2 - m1); return m1 + t[0] * d1
_ax = sheet.ORIGIN_AXES            # cfg.OCG_ORIGIN_AXES: (the axis across, axis 1, axis 2) at the origin; none - the origin is not measured
if len(_ax) == 3 and all(any(w[4] == n for w in words) for n in _ax):
    T = axis_line(_ax[0]); A1 = axis_line(_ax[1]); A1s = axis_line(_ax[2])
    o1 = cross(A1, T); o2 = cross(A1s, T); o3 = cross(A1, A1s)
    O = dict(T_dir_deg=round(math.degrees(math.atan2(T[1][1], T[1][0])) % 180, 3), T_points=T[2], T_span_pt=round(T[3], 1),
             A1_points=A1[2], A1s_points=A1s[2], A1xT=[round(v, 3) for v in o1], A1sxT=[round(v, 3) for v in o2], A1xA1s=[round(v, 3) for v in o3],
             spread_pt=round(float(max(np.linalg.norm(o1 - o2), np.linalg.norm(o1 - o3), np.linalg.norm(o2 - o3))), 3))
elif len(_ax) == 2 and all(any(w[4] == n for w in words) for n in _ax):   # code 012 (СО-3): (axis a, axis b) - origin a × b, row 184
    La = axis_line(_ax[0]); Lb = axis_line(_ax[1]); o = cross(La, Lb)
    O = dict(axes=list(_ax), a_points=La[2], b_points=Lb[2], a_span_pt=round(La[3], 1), b_span_pt=round(Lb[3], 1),
             angle_deg=round(math.degrees(math.acos(min(1.0, abs(float(La[1] @ Lb[1]))))), 3), origin_pt=[round(v, 3) for v in o])
else: O = dict(skipped='cfg.OCG_ORIGIN_AXES не задано или марок осей нет на листе: начало не измерено, только cfg.ORIGIN_PT')
out = dict(A=A, B=B, origin=O, samples=res[:400])
json.dump(out, open('scale.json', 'w'), ensure_ascii=False, indent=1)
print(json.dumps(dict(A=A, B=B[:20], n_B=len(B), origin=O), ensure_ascii=False, indent=1))
