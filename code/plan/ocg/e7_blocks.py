"""Э7 blocks: identical objects (same key) -> one block, at any angle and mirrored. An object's frame: centre of its
minimum rotated rectangle, x along the long side; four poses (0/180 deg, mirrored or not). Candidates share a signature
(number and kinds of primitives, size to 0.25 pt, ink length to 0.5 pt); equal if the symmetric Hausdorff distance of
points sampled every 0.25 pt along the ink is <= 0.15 pt (7 mm) in one of the poses.
Writes blocks.pkl: {obj index: (block id, angle_rad, mirror, cx, cy)}, blocks: {block id: dict(rep, key, n)}.
v3 (owner 06.10.2026, two results): VARIANT=outline takes each object's 'outline' (one closed outline) where it has one and
writes blocks_outline.pkl; the default (detail) takes 'draw'."""
import pickle, numpy as np, math, collections, time, sys
from scipy.spatial import cKDTree
from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union
import os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import sheet; from e7_comp import geom
t0 = time.time()
import os
VAR = os.environ.get('VARIANT', 'detail')
D = pickle.load(open('objects.pkl', 'rb')); from e7_comp import load_prims; P = load_prims()['P']; objs = D['objs']
def body(o):
    if VAR == 'outline' and o.get('outline'): return o['outline']
    return o.get('draw', o['ids'][:1] if o['key'] == 'desk' else o['ids'])
SKIP = {'coreblock', 'corezone', 'zone', 'axis', 'dim', 'lpart', 'wallline', 'coreline', 'facade', 'shaft', 'glass', 'roomsep', 'measure', 'empty'}
def frame(o):
    ids = body(o)
    u = unary_union([geom(P[i]) for i in ids if P[i]['kind'] != 'removed'])
    if u.is_empty: return None
    r = u.minimum_rotated_rectangle
    if r.is_empty or r.geom_type != 'Polygon' or len(r.exterior.coords) < 4: return None
    c = np.array(r.exterior.coords)[:4]; e1 = c[1] - c[0]; e2 = c[2] - c[1]
    ax = e1 if np.linalg.norm(e1) >= np.linalg.norm(e2) else e2; ang = math.atan2(ax[1], ax[0])
    cen = c.mean(0); L = max(np.linalg.norm(e1), np.linalg.norm(e2)); Wd = min(np.linalg.norm(e1), np.linalg.norm(e2))
    return cen, ang, L, Wd
def lum(c): return 1.0 if c is None else 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]
def samples(o, dark=None):
    """ink points every 0.25 pt; dark=True/False keeps only dark (luminance < 0.75) / light primitives"""
    out = []
    for i in body(o):      # a desk's block is its top (the fill); VARIANT=outline: the object's outline
        if dark is not None and ((lum(P[i]['col']) < 0.75) != dark): continue
        q = np.array(P[i]['p'])
        if P[i]['kind'] == 'fill': q = np.vstack([q, q[:1]])
        for a, b in zip(q[:-1], q[1:]):
            n = max(1, int(np.linalg.norm(b - a) / 0.25)); t = np.linspace(0, 1, n + 1)[:, None]
            out.append(a + (b - a) * t)
    return np.vstack(out) if out else np.zeros((0, 2))
def to_frame(X, cen, ang, flip):
    if len(X) == 0: return X
    c, s = math.cos(-ang), math.sin(-ang); Y = (X - cen) @ np.array([[c, s], [-s, c]])
    if flip & 1: Y = Y * np.array([-1, -1])          # 180 deg
    if flip & 2: Y = Y * np.array([1, -1])           # mirror
    return Y
info = {}
for k, o in enumerate(objs):
    if o['key'] in SKIP: continue
    f = frame(o)
    if f is None: continue
    cen, ang, L, Wd = f
    kinds = tuple(sorted(collections.Counter(P[i]['kind'] for i in o['ids']).items()))
    ink = sum(LineString(P[i]['p']).length for i in body(o) if len(P[i]['p']) >= 2)
    info[k] = dict(key=o['key'], L=L, W=Wd, ink=ink, cen=cen, ang=ang)
# candidates: same key, size within 0.3 pt, ink length within 3 % (the PDF splits paths differently per instance,
# so the number of primitives is not compared)
groups = collections.defaultdict(list)
for k, v in sorted(info.items(), key=lambda kv: (kv[1]['key'], kv[1]['L'], kv[1]['W'])):
    placed = False
    for g in groups[v['key']]:
        r = info[g[0]]
        if abs(r['L'] - v['L']) <= 0.3 and abs(r['W'] - v['W']) <= 0.3 and abs(r['ink'] - v['ink']) <= 0.03 * max(r['ink'], 1e-9):
            g.append(k); placed = True; break
    if not placed: groups[v['key']].append([k])
groups = {(key, n): g for key, gs in groups.items() for n, g in enumerate(gs)}
blocks = {}; assign = {}; nb = 0
for sig, mem in groups.items():
    reps = []                                 # (block id, canonical points, kdtree)
    for k in mem:
        # dark and light ink are compared separately: a block must not draw black what an instance has light grey
        XD, XL = samples(objs[k], True), samples(objs[k], False); cen, ang = info[k]['cen'], info[k]['ang']; done = False
        tol = 0.3 if objs[k]['key'] == 'door' else 0.15             # doors: 20 mm of the canon is 0.42 pt here, above the strict ink tolerance 0.4 pt: 0.3 pt (14 mm)
        def haus(Y, R, RT):
            if len(Y) == 0 and len(R) == 0: return 0.0
            if len(Y) == 0 or len(R) == 0: return 9e9
            return max(RT.query(Y)[0].max(), cKDTree(Y).query(R)[0].max())
        for bid, RD, RDT, RL, RLT in reps:
            for flip in range(4):
                YD0, YL0 = to_frame(XD, cen, ang, flip), to_frame(XL, cen, ang, flip)
                if haus(YD0, RD, RDT) <= 0.6 and haus(YL0, RL, RLT) <= 0.6:
                    # refine the pose: rigid ICP of the instance (in the block frame) onto the block, 4 rounds
                    Y = np.vstack([q for q in (YD0, YL0) if len(q)]); Rall = np.vstack([q for q in (RD, RL) if len(q)]); RT_ = cKDTree(Rall)
                    th = 0.0; tt = np.zeros(2)
                    for _ in range(4):
                        c_, s_ = math.cos(th), math.sin(th); Yc = Y @ np.array([[c_, s_], [-s_, c_]]) + tt
                        idx = RT_.query(Yc)[1]; Mt = Rall[idx]
                        mu1, mu2 = Yc.mean(0), Mt.mean(0); Hm = (Yc - mu1).T @ (Mt - mu2); U_, S_, Vt = np.linalg.svd(Hm)
                        Rm = (U_ @ Vt).T
                        if np.linalg.det(Rm) < 0: Vt[1] *= -1; Rm = (U_ @ Vt).T
                        dth = math.atan2(Rm[1, 0], Rm[0, 0]); th += dth
                        c_, s_ = math.cos(th), math.sin(th); Yc = Y @ np.array([[c_, s_], [-s_, c_]])
                        tt = (Mt - Yc).mean(0) if False else (Rall[RT_.query(Yc + tt)[1]] - Yc).mean(0)
                    c_, s_ = math.cos(th), math.sin(th); rot = np.array([[c_, s_], [-s_, c_]])
                    YDr = YD0 @ rot + tt if len(YD0) else YD0; YLr = YL0 @ rot + tt if len(YL0) else YL0
                    if haus(YDr, RD, RDT) <= tol and haus(YLr, RL, RLT) <= tol:
                        # world = cen + Rot(ang) F Rot(-th)(L - tt)  ->  new angle and centre of the insert
                        Fm = np.diag([-1.0 if flip & 1 else 1.0, (-1.0 if flip & 1 else 1.0) * (-1.0 if flip & 2 else 1.0)])
                        ca, sa = math.cos(ang), math.sin(ang); Ra = np.array([[ca, -sa], [sa, ca]])
                        Rmt = np.array([[c_, s_], [-s_, c_]])          # Rot(-th)
                        shift = Ra @ Fm @ Rmt @ tt; ncen = np.array(cen) - shift
                        nang = ang - th if not (flip & 2) else ang + th
                        assign[k] = (bid, nang, flip, ncen[0], ncen[1]); blocks[bid]['n'] += 1; done = True; break
            if done: break
        if not done:
            YD, YL = to_frame(XD, cen, ang, 0), to_frame(XL, cen, ang, 0)
            reps.append((nb, YD, cKDTree(YD) if len(YD) else None, YL, cKDTree(YL) if len(YL) else None))
            blocks[nb] = dict(rep=k, key=objs[k]['key'], n=1); assign[k] = (nb, ang, 0, cen[0], cen[1]); nb += 1
pickle.dump(dict(assign=assign, blocks=blocks), open('blocks_outline.pkl' if VAR == 'outline' else 'blocks.pkl', 'wb'))
rep = collections.Counter(); inst = collections.Counter()
for b in blocks.values(): rep[b['key']] += 1; inst[b['key']] += b['n']
print('blocks', nb, '| repeated blocks', sum(1 for b in blocks.values() if b['n'] > 1), '| instances', len(assign), f'{time.time() - t0:.1f} s')
for k in sorted(rep, key=lambda q: -inst[q]): print(f'  {k}: {inst[k]} objects -> {rep[k]} blocks')
