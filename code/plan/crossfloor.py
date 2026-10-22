# Pairwise comparison of the floors of one building (plan/rules/60 §11): capital elements - capital / external walls,
# glazing, columns, doors in capital walls. Sheets cover different parts of the building (client A: 1-2 whole floor,
# 3-5 the lower part, 6 the upper part without axes), and their axis dimensions disagree (axis Д: 30000 / 30100 /
# 30705), so the floors are registered by their capital walls, not by axis names: phase correlation of the wall masks
# for the shift, then ICP (shift + scale) on the wall outlines. Each pair is compared only where both sheets draw.
#   same element  -> drawn the same? class of the wall, its outline (symmetric difference), thickness
#   difference    -> justified? the other sheet's source ink at that place: wall hatch there = our recognition
#                    missed it on that floor; no ink = the sheets differ (a real difference or a sheet that does not
#                    draw that part)
# Usage (from the work folder): XF_REF=f3 python3 crossfloor.py f1 f2 f3 f4 f5 f6   -> crossfloor.json, crossfloor_*.png
#   XF_REF - the reference floor of the common frame, required: a typical floor fits the others best (client A: f3b).
#   Until 30.09.2026 the first floor of the list was a silent default - the frame came from the ground floor.
import sys, os, math, json, pickle, importlib.util, itertools, collections
import numpy as np, cv2
from shapely.geometry import Polygon, MultiPolygon, LineString, Point, box
from shapely.ops import unary_union
from shapely.affinity import affine_transform
from shapely.strtree import STRtree
from shapely.prepared import prep
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
FLOORS = sys.argv[1:]
if not os.environ.get('XF_REF'):
    sys.exit('crossfloor.py: set XF_REF=<reference floor> - a typical floor, plan/rules/60 §11 (client A: XF_REF=f3b). '
             'There is no default: the first floor of the list gave a wrong frame on 30.09.2026')
if os.environ['XF_REF'] not in FLOORS: sys.exit(f"crossfloor.py: XF_REF={os.environ['XF_REF']} is not among the floors {FLOORS}")
def polys(g): return [g] if g.geom_type == 'Polygon' else [x for x in getattr(g, 'geoms', []) if x.geom_type == 'Polygon']

def load_floor(d):
    spec = importlib.util.spec_from_file_location('cfg_' + os.path.basename(d), os.path.join(d, 'cfg.py'))
    cfg = importlib.util.module_from_spec(spec); sys.path.insert(0, d); spec.loader.exec_module(cfg); sys.path.pop(0)
    AX_X, AX_XMM, AX_Y, AX_YMM = [list(getattr(cfg, k, [])) for k in ('AX_X', 'AX_XMM', 'AX_Y', 'AX_YMM')]
    if len(AX_X) >= 2 and len(AX_Y) >= 2: kx = np.polyfit(AX_X, AX_XMM, 1); ky = np.polyfit(AX_Y, AX_YMM, 1)
    else:
        k = cfg.MM_PER_PT; ox, oy = cfg.ORIGIN_PT; kx = np.array([k, -k * ox]); ky = np.array([-k, k * oy])
    wf = os.path.join(d, 'walls_fixed.pkl'); wf = wf if os.path.exists(wf) else os.path.join(d, 'walls.pkl')
    _wf = pickle.load(open(wf, 'rb')); W = _wf['W']
    Wpt = _wf.get('Wpt', {})
    inst = pickle.load(open(os.path.join(d, 'inst_final.pkl'), 'rb'))
    P = pickle.load(open(os.path.join(d, 'seq.pkl'), 'rb'))[0]; cls = pickle.load(open(os.path.join(d, 'cls.pkl'), 'rb'))
    MM = lambda p: (float(np.polyval(kx, p[0])), float(np.polyval(ky, p[1])))
    cap = unary_union([p for k in ('cap', 'ext') for g in W.get(k, []) for p in polys(g)])
    allw = unary_union([p for v in W.values() for g in v for p in polys(g)])
    def lines(keys):
        out = []
        for q in inst:
            if q['key'] in keys:
                for i in q['prims']:
                    if P[i][0] == 'l': out.append(LineString([MM(P[i][4][0]), MM(P[i][4][1])]))
        return out
    glaz = unary_union(lines(('facade',))) if any(q['key'] == 'facade' for q in inst) else LineString()
    cols = [Point(q['ins']) for q in inst if q['key'] == 'column' and q.get('ins')]
    doors = [(Point(q['hinge_mm']), Point(q['closed_mm']), q['name']) for q in inst if q['key'] == 'door' and q.get('hinge_mm')]
    lifts = [Point(q['ins']) for q in inst if q['key'] in ('lift', 'stair') and q.get('ins')]
    # (29.09.2026) what the sheet draws = the hull of its OWN drawing (every primitive but sheet / axis / dimension / tag
    #   and white masks), not of the recognised walls: a wall the recognition missed at the edge of the sheet (floor 2,
    #   the round wall at axes Д - Г/2) was outside the compared area and could never be reported
    from shapely.geometry import MultiPoint
    _pp = []
    for i, p in enumerate(P):
        if cls[i] in ('sheet', 'axis', 'dim', 'tag'): continue
        if p[0] == 'qu' and p[2] is None and p[3] is not None and min(p[3]) >= 0.97: continue
        for v in (p[4][0], p[4][-1]): _pp.append(MM(v))
    src_hull = MultiPoint(_pp).convex_hull if _pp else Point(0, 0)
    # (30.09.2026) the floor's own wall bodies in pt: a hatch stroke inside them is that wall's (see src_ink)
    allw_pt = unary_union([p for v in Wpt.values() for g in v for p in polys(g)])
    return dict(name=os.path.basename(d), cfg=cfg, kx=kx, ky=ky, MM=MM, W=W, cap=cap, allw=allw, glaz=glaz, cols=cols,
                doors=doors, lifts=lifts, P=P, cls=cls, inst=inst, src_hull=src_hull,
                allw_pt=prep(allw_pt.buffer(0.1)) if not allw_pt.is_empty else None)

F = {f: load_floor(f) for f in FLOORS}

# ---------------- registration to the first floor: shift by phase correlation of the capital-wall masks, then ICP
RES = 50.0   # mm per px for the correlation
def mask(g, bounds):
    x0, y0, x1, y1 = bounds; Wd, Hd = int((x1 - x0) / RES) + 1, int((y1 - y0) / RES) + 1
    m = np.zeros((Hd, Wd), np.float32)
    for p in polys(g):
        cv2.fillPoly(m, [np.array([((x - x0) / RES, (y1 - y) / RES) for x, y in p.exterior.coords], np.int32)], 1.0)
        for h in p.interiors: cv2.fillPoly(m, [np.array([((x - x0) / RES, (y1 - y) / RES) for x, y in h.coords], np.int32)], 0.0)
    return m
def samples(g, step=150.0):
    out = []
    for p in polys(g):
        for r in [p.exterior] + list(p.interiors):
            n = max(2, int(r.length / step))
            out += [r.interpolate(t, normalized=True).coords[0] for t in np.linspace(0, 1, n, endpoint=False)]
    return np.array(out)
from scipy.spatial import cKDTree
def register(A, B, guess=None):
    """transform (s, tx, ty): B -> A frame, p_A = s * p_B + t"""
    ga, gb = A['cap'], B['cap']
    bx = ga.bounds; by = gb.bounds
    big = (min(bx[0], by[0]) - 20000, min(bx[1], by[1]) - 20000, max(bx[2], by[2]) + 20000, max(bx[3], by[3]) + 20000)
    ma, mb = mask(ga, big), mask(gb, big)
    # phase correlation
    Fa = np.fft.fft2(ma); Fb = np.fft.fft2(mb)
    Rr = Fa * np.conj(Fb); Rr /= np.abs(Rr) + 1e-9
    c = np.real(np.fft.ifft2(Rr)); iy, ix = np.unravel_index(np.argmax(c), c.shape)
    if iy > c.shape[0] / 2: iy -= c.shape[0]
    if ix > c.shape[1] / 2: ix -= c.shape[1]
    SA = samples(ga); SB = samples(gb); ta = cKDTree(SA)
    # (29.09.2026) several starts, the best fit wins: the phase-correlation peak, no shift (the axis frames of two
    #   sheets are within ~0.7 m of each other), and the guess given by the caller (through the first floor). The
    #   ground floor shares only the core with the others, and its correlation peak was 28 m off
    best = None
    for tx0, ty0 in [(ix * RES, -iy * RES), (0.0, 0.0)] + ([tuple(guess)] if guess is not None else []):
        r_ = _icp(SA, SB, ta, tx0, ty0)
        if best is None or r_['inliers_100'] > best['inliers_100']: best = r_
    return best
def _icp(SA, SB, ta, tx, ty):
    """(29.09.2026) shift first, scale last, with a fixed window that tightens 600 -> 300 -> 150 -> 100 mm: the
    60-percentile window of the first version let the ground floor (walls the others do not have) drift 7 m away
    with the scale on its bound"""
    s = 1.0
    for thr, fit_s in ((600.0, False), (300.0, False), (150.0, True), (100.0, True)):
        for it in range(30):
            Q = SB * s + np.array([tx, ty]); d, j = ta.query(Q)
            k = d <= thr
            if k.sum() < 20: break
            Pm, Qm = SA[j[k]], SB[k]
            mp, mq = Pm.mean(0), Qm.mean(0)
            s_new = s
            if fit_s:
                s_new = float(np.sum((Pm - mp) * (Qm - mq)) / max(np.sum((Qm - mq) ** 2), 1e-9))
                s_new = min(1.02, max(0.98, s_new))
            t_new = mp - s_new * mq
            done = abs(s_new - s) < 1e-6 and np.hypot(*(t_new - np.array([tx, ty]))) < 0.1
            s, (tx, ty) = s_new, t_new
            if done: break
    Q = SB * s + np.array([tx, ty]); d, _ = ta.query(Q)
    dA, _ = cKDTree(Q).query(SA)
    return dict(s=round(s, 6), tx=round(float(tx), 1), ty=round(float(ty), 1), median_mm=round(float(np.median(d)), 1),
                share_within_100mm=round(float((d <= 100).mean()), 3), share_other_side=round(float((dA <= 100).mean()), 3),
                inliers_100=int((d <= 100).sum()))
# the common frame (overview picture, starting guesses): a typical floor fits the others best (XF_REF; the ground
#   floor shares only the core with them)
REF = os.environ['XF_REF']; REG = {REF: dict(s=1.0, tx=0.0, ty=0.0, median_mm=0.0, share_within_100mm=1.0)}
def _good(r): return max(r.get('share_within_100mm') or 0, r.get('share_other_side') or 0) >= 0.3   # one side matches 30 %
for f in [g for g in FLOORS if g != REF]:
    REG[f] = register(F[REF], F[f])
# a sheet with no good overlap with the reference (6: the upper part only): through the best registered other floor
for f in [g for g in FLOORS if g != REF and not _good(REG[g])]:
    best = max((register(F[g], F[f]) | {'via': g} for g in FLOORS if g not in (f, REF) and _good(REG[g])), key=lambda r: r['inliers_100'], default=None)
    if best and _good(best):
        g = best['via']; r0 = REG[g]
        REG[f] = dict(s=round(r0['s'] * best['s'], 6), tx=round(r0['s'] * best['tx'] + r0['tx'], 1), ty=round(r0['s'] * best['ty'] + r0['ty'], 1),
                      median_mm=best['median_mm'], share_within_100mm=best['share_within_100mm'], share_other_side=best['share_other_side'],
                      inliers_100=best['inliers_100'], via=g)
print('registration', REG)
def T(f, g):
    r = REG[f]; return affine_transform(g, [r['s'], 0, 0, r['s'], r['tx'], r['ty']])
def Tp(f, p):
    r = REG[f]; return (r['s'] * p[0] + r['tx'], r['s'] * p[1] + r['ty'])

# ---------------- per floor in the common frame
C = {}
for f in FLOORS:
    d = F[f]
    # what the sheet draws: the hull of its walls and glazing (sheets 3-5 draw the lower part, 6 the upper part)
    _g = [T(f, d['allw'])] + ([T(f, d['glaz'])] if not d['glaz'].is_empty else [])
    foot = unary_union(_g + [T(f, d['src_hull'])]).convex_hull.buffer(200)
    C[f] = dict(cap=T(f, d['cap']), allw=T(f, d['allw']), glaz=T(f, d['glaz']) if not d['glaz'].is_empty else d['glaz'],
                cols=[Point(Tp(f, (p.x, p.y))) for p in d['cols']], doors=[(Point(Tp(f, (h.x, h.y))), Point(Tp(f, (c.x, c.y))), n) for h, c, n in d['doors']],
                foot=foot, W={k: T(f, unary_union([p for g in v for p in polys(g)])) for k, v in d['W'].items()})

# ---------------- source ink at a place (in the common frame) on floor f: hatch-like strokes and thick lines
_INK = {}; _INKI = {}
# (30.09.2026) a stroke that the floor's own pipeline made part of an object of its own - a plant, a chair, a sink, a
#   letter - or of the glazing (the mullions and chords of floor 6's curved curtain wall) is not a wall's hatch. This
#   leans on the classification, as the verdict "glazing instead of the wall" does (owner 30.09). The strokes of the light
#   partitions, their joints, wall lines, the loose bits, 'misc' and free strokes still count: the light partitions take
#   everything long, and a missed wall's hatch is there. Chords of one line are not left out: the fixed pattern of floor
#   2's ramp wall is drawn as chains of collinear segments (95 % of its strokes)
HATCH_KEYS = ('lpart', 'lpartc', 'wallline', 'loose', 'misc', 'grey', 'roomsep', 'atrium', 'zone')
def _ink_index(f):
    if f not in _INK:
        d = F[f]; H = []; Tk = []; TkI = []
        own_ = {i: q['key'] for q in d['inst'] for i in q['prims']}
        for i, p in enumerate(d['P']):
            if p[0] != 'l' or d['cls'][i] in ('axis', 'dim', 'sheet'): continue
            (ax, ay), (bx, by) = p[4]; m = ((ax + bx) / 2, (ay + by) / 2)
            L = math.dist((ax, ay), (bx, by)); t = math.degrees(math.atan2(by - ay, bx - ax)) % 180
            # (29.09.2026) any angle, thin: a fixed pattern on a curve is not at 45 deg to the sheet (floor 2, 37/127 deg)
            # (30.09.2026) >= 1 pt (63 mm): the strokes of real hatch in floor 2's walls are 1.2-6.7 pt (p10-p90, 94 % >= 1 pt);
            #   0.4-0.6 pt are the chords of small circles - the valve symbol by floor 6's fire-hose cabinet
            if 1.0 <= L <= 14 and (p[1] or 0) < 0.45 and own_.get(i, 'misc') in HATCH_KEYS: H.append((m[0], m[1], t))
            if p[1] and p[1] >= 0.45: Tk.append((m[0], m[1], t)); TkI.append(i)
        _INK[f] = (np.array(H) if H else np.zeros((0, 3)), np.array(Tk) if Tk else np.zeros((0, 3)))
        _INKI[f] = TkI
    return _INK[f]
def _local_dir(gp):
    """direction (deg) of the piece's outline nearest to a point: hatch crosses a band, the chords of a curved glass
    line run along it (29.09.2026: floor 6's curved glazing counted as 'wall hatch' against floor 1's curved wall)"""
    segs = []
    for pl in polys(gp):
        # (30.09.2026) a curved outline is a chain of chords shorter than 0.2 pt: simplified first (0.05 pt), else only the
        #   straight cut edges were left and a curved wall's "direction" was 0 or 90 deg
        pl = pl.simplify(0.05)
        for ring in [pl.exterior] + list(pl.interiors):
            c_ = list(ring.coords)
            segs += [LineString([u, v]) for u, v in zip(c_, c_[1:]) if math.dist(u, v) > 0.2]
    tr = STRtree(segs) if segs else None
    def f_(x, y):
        if tr is None: return None
        j = tr.nearest(Point(x, y)); sg = segs[int(j)]; (u, v) = list(sg.coords)
        return math.degrees(math.atan2(v[1] - u[1], v[0] - u[0])) % 180
    return f_
def src_ink(f, g, r=None, parent=None):
    """hatch-like strokes and thick lines of floor f's source inside g (g in a frame where p = s * p_f + t, r).
    (30.09.2026) The direction a hatch stroke is judged against is the outline of the wall around the piece (parent):
    the edges where the grid or the common area cut the piece are not the wall's - along them the chords of floor 6's
    curved glazing crossed "at 34 deg". A stroke inside floor f's own wall bodies is that wall's hatch, not a missed wall's: floor 2's light walls
    drawn with an X pattern next to floor 1's capital wall (the other floor's walls covered 30-40 % of the piece)."""
    d = F[f]; r = r or REG[f]
    inv = [1 / r['s'], 0, 0, 1 / r['s'], -r['tx'] / r['s'], -r['ty'] / r['s']]
    kx, ky = d['kx'], d['ky']
    topt = lambda g_: affine_transform(affine_transform(g_, inv), [1 / kx[0], 0, 0, 1 / ky[0], -kx[1] / kx[0], -ky[1] / ky[0]])
    gp = topt(g)                                                  # floor f pt
    x0, y0, x1, y1 = gp.bounds; out = []; ld = _local_dir(topt(parent) if parent is not None else gp)
    own_ = d.get('allw_pt')
    par_n = 0
    for n_, A in enumerate(_ink_index(f)):
        if not len(A): out.append(0); continue
        k = (A[:, 0] >= x0) & (A[:, 0] <= x1) & (A[:, 1] >= y0) & (A[:, 1] <= y1)
        if n_ == 0:   # hatch: crosses the piece at >= 20 deg to its outline there
            def _cross(x, y, t):   # a hatch stroke crosses the band at 20-70 deg to its outline; 0/90 are furniture, frames
                d_ = ld(x, y)
                if d_ is None: return min(abs(t - 45), abs(t - 135)) <= 6
                a_ = abs(((t - d_) + 90) % 180 - 90); return 20 <= a_ <= 70
            ts_ = [t for x, y, t in A[k] if gp.contains(Point(x, y)) and _cross(x, y, t)
                   and (own_ is None or not own_.contains(Point(x, y)))]
            out.append(len(ts_)); par_n = _parallel(ts_)
        else: out.append(sum(1 for x, y, t in A[k] if gp.contains(Point(x, y))))
    return out[0], out[1], par_n
def _parallel(ts, tol=5.0):
    """(30.09.2026) the strokes of a hatch are parallel: the largest family of stroke angles within +-tol deg, with the
    family at right angles to it (a cross hatch). The spokes of plant symbols, letters, the chords of a fire-hose reel and
    the details of a curtain wall run every way (floors 1-6: 13 places of 'missed' that were none)"""
    if not ts: return 0
    a = np.array(ts) % 180.0; best = 0
    for t0 in a:
        d1 = np.abs((a - t0 + 90) % 180 - 90); d2 = np.abs((a - t0) % 180 - 90)
        best = max(best, int(((d1 <= tol) | (d2 <= tol)).sum()))
    return best

GLAZ_KEYS = ('lpart', 'lpartc', 'glass', 'facade', 'railing', 'gate')
def thick_share(f, g, r=None):
    """(owner 30.09.2026) the share of floor f's thick lines inside g (frame p = s * p_f + t) that our pipeline drew as
    glazing or light partitions - A-22G and A-31"""
    d = F[f]; r = r or REG[f]
    if '_own' not in d:
        d['_own'] = {i: q['key'] for q in d['inst'] for i in q['prims']}
    inv = [1 / r['s'], 0, 0, 1 / r['s'], -r['tx'] / r['s'], -r['ty'] / r['s']]
    kx, ky = d['kx'], d['ky']
    gp = affine_transform(affine_transform(g, inv), [1 / kx[0], 0, 0, 1 / ky[0], -kx[1] / kx[0], -ky[1] / ky[0]])
    A = _ink_index(f)[1]; I = _INKI[f]
    if not len(A): return 0.0, 0
    x0, y0, x1, y1 = gp.bounds
    k = np.nonzero((A[:, 0] >= x0) & (A[:, 0] <= x1) & (A[:, 1] >= y0) & (A[:, 1] <= y1))[0]
    ins = [I[j] for j in k if gp.contains(Point(A[j, 0], A[j, 1]))]
    if not ins: return 0.0, 0
    return sum(1 for i in ins if d['_own'].get(i) in GLAZ_KEYS) / len(ins), len(ins)
# ---------------- pairs: each pair is registered directly (29.09.2026) - through the first floor the residual of a
#   ground floor unlike the rest (median 256 mm for floor 3) spoilt every pair
def frame(f, r):
    """floor f in the frame p = s * p_f + t (r)"""
    d = F[f]
    TT = lambda g: affine_transform(g, [r['s'], 0, 0, r['s'], r['tx'], r['ty']])
    TP = lambda p: (r['s'] * p[0] + r['tx'], r['s'] * p[1] + r['ty'])
    _g = [TT(d['allw'])] + ([TT(d['glaz'])] if not d['glaz'].is_empty else [])
    return dict(cap=TT(d['cap']), allw=TT(d['allw']), glaz=TT(d['glaz']) if not d['glaz'].is_empty else d['glaz'],
                cols=[Point(TP((p.x, p.y))) for p in d['cols']], doors=[(Point(TP((h.x, h.y))), Point(TP((c.x, c.y))), n) for h, c, n in d['doors']],
                foot=unary_union(_g + [TT(d['src_hull'])]).convex_hull.buffer(200), W={k: TT(unary_union([p for g in v for p in polys(g)])) for k, v in d['W'].items()})
ID = dict(s=1.0, tx=0.0, ty=0.0)
CELL = float(os.environ.get('XF_CELL', 1500))
def cells(dd):
    """(29.09.2026) difference pieces cut by a CELL-mm grid: the verdict is local. A 20 m piece that joins an outline-only
    wall to a missed round wall (floor 2 against floor 3) averaged the round wall's 8.8 strokes per metre down to 3.9"""
    out = []
    for p in polys(dd):
        x0, y0, x1, y1 = p.bounds
        for i in range(int(math.floor(x0 / CELL)), int(math.floor(x1 / CELL)) + 1):
            for j in range(int(math.floor(y0 / CELL)), int(math.floor(y1 / CELL)) + 1):
                bx_ = box(i * CELL, j * CELL, (i + 1) * CELL, (j + 1) * CELL); q = p.intersection(bx_)
                for r in polys(q):
                    # >= 0.05 m2, >= 40 mm thick; with the cell's box (the direction of the wall's outline around it, src_ink)
                    if r.area >= 0.05e6 and 2 * r.area / r.length >= 40: out.append((r, bx_))
    return out
OUT = dict(registration=REG, pairs={})
for a, b in itertools.combinations(FLOORS, 2):
    ra, rb = REG[a], REG[b]                       # the guess through the common frame, b -> first floor -> a
    g0 = ((rb['tx'] - ra['tx']) / ra['s'], (rb['ty'] - ra['ty']) / ra['s'])
    rp = register(F[a], F[b], guess=g0)           # b -> a, directly
    Ca, Cb = frame(a, ID), frame(b, rp); CC = {a: Ca, b: Cb}; RR = {a: ID, b: rp}
    ov = Ca['foot'].intersection(Cb['foot'])
    if ov.area < 20e6:            # < 20 m2 in common: nothing to compare
        OUT['pairs'][f'{a}-{b}'] = dict(overlap_m2=round(ov.area / 1e6, 1)); continue
    ov_in = ov.buffer(-100)       # off the very edge of what both draw
    A = Ca['cap'].intersection(ov_in); B = Cb['cap'].intersection(ov_in)
    inter = A.intersection(B); ua = A.union(B)
    res = dict(registration=rp, overlap_m2=round(ov.area / 1e6, 1), cap_iou=round(inter.area / ua.area, 3) if ua.area else None,
               cap_m2=[round(A.area / 1e6, 2), round(B.area / 1e6, 2)])
    diffs = []
    for side, X, Y, other in (('only_' + a, A, B, b), ('only_' + b, B, A, a)):
        dd = X.difference(Y.buffer(60)); Xfull = (Ca if side == 'only_' + a else Cb)['cap']
        for p, bx_ in cells(dd):
            # (30.09.2026) the direction a hatch stroke is judged against: the outline of this floor's own capital wall
            #   around the cell (+600 mm), uncut - not the edges where the grid, the common area or the other floor's
            #   walls cut the piece (floor 6's curved glazing ran "at 34 deg" to the common area's straight edge)
            par_ = Xfull.intersection(bx_.buffer(600, join_style=2))
            # is the difference in the other sheet's source?
            n_h, n_t, n_par = src_ink(other, p.buffer(-20) if p.buffer(-20).area > 0 else p, RR[other], parent=par_)
            # is it covered by any wall on the other floor (drawn as a partition there = class difference)?
            cov = CC[other]['allw'].intersection(p).area / p.area
            # the same wall drawn a little differently: the piece is thin and lies along the other floor's wall
            thin = 2 * p.area / p.length <= 120 and Y.buffer(150).intersection(p).area / p.area > 0.8
            # (28.09.2026) hatch is dense - 8-15 strokes per metre of wall: a few 45-deg strokes along a 30 m piece are lift
            #   crosses and door marks, not the wall's hatch (floor 5: the lift core drawn as outlines only). 29.09: 6 per
            #   metre, and only strokes that cross the piece (_local_dir): the teeth of floor 2's sawtooth stair wall gave
            #   4.3, desks and chairs 3-4. The other floor's walls cover >= 40 % of the piece: the same wall, another class
            #   or thickness (floor 2 draws the east wall as two thin walls, floor 4 as one capital)
            #   30.09: only the parallel strokes count (_parallel) - the density is of the hatch's own family
            L_m = max(p.length / 2 / 1000, 0.1); dens = n_par / L_m
            verdict = ('class differs on ' + other) if cov >= 0.4 else ('same wall, outline differs by <= 120 mm' if thin else
                       (('missed on ' + other + ' (source has wall hatch)') if n_par >= 2 and dens >= 6 else
                        ('source of ' + other + ' draws thick lines only' if n_t >= 2 else 'sheets differ')))
            # (owner 30.09.2026: "the thick lines are glazing inside the office ... as on the facade, where a blind wall
            #   goes over into curtain walling") thick lines without hatch are not a missed wall; which case it is:
            #   - the other floor's own walls within 300 mm hold >= half the piece's area: the same wall, shifted (curved
            #     walls of another radius, the cores of lifts and stairs);
            #   - else >= half of the thick lines are drawn as glazing or light partitions there: glazing instead of the wall;
            #   - else the floors' layouts differ (sanitary cabins, doors, open space)
            gl_, nt_ = 0.0, 0
            if verdict.startswith('source of'):
                near_ = CC[other]['allw'].intersection(p.buffer(300)).area / p.area
                gl_, nt_ = thick_share(other, p.buffer(-20) if p.buffer(-20).area > 0 else p, RR[other])
                verdict = ('same wall on ' + other + ', shifted <= 300 mm' if near_ >= 0.5 else
                           ('glazing on ' + other + ' instead of the wall' if gl_ >= 0.5 else 'layouts differ: ' + other + ' draws other objects there'))
            diffs.append(dict(side=side, area_m2=round(p.area / 1e6, 2), at_mm=[round(c) for c in p.centroid.coords[0]],
                              width_mm=round(2 * p.area / p.length), other_hatch_strokes=n_h, other_hatch_parallel=n_par, other_thick_lines=n_t,
                              other_wall_cover=round(cov, 2), hatch_per_m=round(dens, 1), other_thick_glazing_share=round(gl_, 2), verdict=verdict))
    res['cap_differences'] = sorted(diffs, key=lambda d: -d['area_m2'])
    res['verdicts'] = dict(collections.Counter(d['verdict'].replace(a, 'A').replace(b, 'B') for d in diffs))
    res['verdicts_m2'] = {k: round(sum(d['area_m2'] for d in diffs if d['verdict'].replace(a, 'A').replace(b, 'B') == k), 2) for k in res['verdicts']}
    # class of the same wall: area of A-cap over B's classes
    cm = {}
    for k, g in Cb['W'].items():
        x = A.intersection(g.intersection(ov_in)).area
        if x > 0.01e6: cm[k] = round(x / 1e6, 2)
    res['cap_of_' + a + '_as_classes_of_' + b] = cm
    # glazing
    ga, gb = Ca['glaz'], Cb['glaz']
    if not ga.is_empty and not gb.is_empty:
        ga_i, gb_i = ga.intersection(ov_in), gb.intersection(ov_in)
        res['glazing_m'] = [round(ga_i.length / 1000, 1), round(gb_i.length / 1000, 1)]
        res['glazing_matched_share'] = [round(ga_i.intersection(gb.buffer(150)).length / max(ga_i.length, 1), 3),
                                        round(gb_i.intersection(ga.buffer(150)).length / max(gb_i.length, 1), 3)]
    # columns
    ca = [p for p in Ca['cols'] if ov_in.contains(p)]; cb = [p for p in Cb['cols'] if ov_in.contains(p)]
    if ca or cb:
        tb = cKDTree([(p.x, p.y) for p in cb]) if cb else None
        m = sum(1 for p in ca if tb is not None and tb.query((p.x, p.y))[0] <= 200)
        res['columns'] = dict(n=[len(ca), len(cb)], matched=m)
    # doors in capital walls
    def cap_doors(f):
        g = CC[f]['cap'].buffer(100)
        return [(h, c, n) for h, c, n in CC[f]['doors'] if ov_in.contains(h) and g.contains(h)]
    da, db = cap_doors(a), cap_doors(b)
    if da or db:
        tb = cKDTree([((h.x + c.x) / 2, (h.y + c.y) / 2) for h, c, n in db]) if db else None
        mm_ = [(n, round(tb.query(((h.x + c.x) / 2, (h.y + c.y) / 2))[0])) for h, c, n in da] if tb is not None else []
        res['doors_in_capital_walls'] = dict(n=[len(da), len(db)], matched_within_300mm=sum(1 for n, d in mm_ if d <= 300))
    OUT['pairs'][f'{a}-{b}'] = res
    print(a, b, {k: v for k, v in res.items() if k != 'cap_differences'}, 'diffs', len(res['cap_differences']))
    # picture of the pair: common area (grey), capital walls of A (red) and B (blue), differences by verdict
    bx = ov.bounds; Z = 0.025; x0, y0, x1, y1 = bx[0] - 1000, bx[1] - 1000, bx[2] + 1000, bx[3] + 1000
    im = np.full((int((y1 - y0) * Z) + 1, int((x1 - x0) * Z) + 1, 3), 255, np.uint8)
    def pp(g): return [np.array([((x - x0) * Z, (y1 - y) * Z) for x, y in r.coords], np.int32) for p in polys(g) for r in [p.exterior]]
    cv2.fillPoly(im, pp(ov), (240, 240, 240))
    VC = {'class': (0, 170, 255), 'same wall': (0, 200, 0), 'missed': (0, 0, 255), 'thick': (200, 0, 200), 'sheets': (130, 130, 130)}
    for dd_ in res['cap_differences']:
        pass
    for side, X, Y, other in (('A', A, B, b), ('B', B, A, a)):
        dd = X.difference(Y.buffer(60))
        for p, _ in cells(dd):
            v = next((d['verdict'] for d in res['cap_differences'] if d['at_mm'] == [round(c) for c in p.centroid.coords[0]]), '')
            col = next((c for k, c in VC.items() if k in v), (130, 130, 130))
            cv2.fillPoly(im, pp(p), col)
    for g, col in ((A, (60, 60, 220)), (B, (220, 120, 40))):
        for r in pp(g): cv2.polylines(im, [r], True, col, 1)
    cv2.imwrite(f'crossfloor_{a}-{b}.png', im)
json.dump(OUT, open('crossfloor.json', 'w'), ensure_ascii=False, indent=1)
# ---------------- picture: all floors' capital walls in the common frame (one colour per floor)
allb = unary_union([C[f]['foot'] for f in FLOORS]).bounds
Z = 0.02; x0, y0, x1, y1 = allb
im = np.full((int((y1 - y0) * Z) + 20, int((x1 - x0) * Z) + 20, 3), 255, np.uint8)
PAL = [(220, 60, 60), (60, 140, 220), (60, 170, 60), (200, 120, 0), (150, 60, 200), (0, 160, 160)]
for n, f in enumerate(FLOORS):
    for p in polys(C[f]['cap']):
        pts_ = np.array([((x - x0) * Z + 10, (y1 - y) * Z + 10) for x, y in p.exterior.coords], np.int32)
        cv2.polylines(im, [pts_], True, PAL[n % len(PAL)][::-1], 1)
cv2.imwrite('crossfloor_overlay.png', im)
