# Check 3.11 (29.09.2026): curved walls are walls along their whole length. Found on floor 2 after the owner's remark
#   on the round wall: the NE arc of the ramp (r 13.6 m) was a wall for 44 % of its core and 2 % of its upper lining,
#   and no check saw it - the strokes are drawn, the ink check is silent, the gaps are longer than 1.5 m.
#   (a) arcs: chains of chords or curves (end to end <= 0.05 pt, one weight and colour), >= 1.5 m long, turning >= 15 deg,
#       on one circle (fit residual <= 0.2 pt), radius 1-60 m;
#   (b) bands: two arcs with one centre (<= 1 pt) and radii 0.8-10 pt apart with no third arc between them, over the
#       angles both cover;
#   (c) a band that carries a pattern - thin strokes (<= 0.35 pt) crossing it (not along it, >= 10 deg), each within the
#       band, >= 1.5 per metre of its middle line - is a wall; the recognised walls must cover >= 90 % of it. The joints
#       of a glass partition drawn in heavy black (floor 5, the meeting room's rounded corner) are no pattern.
#   A band below that is listed with its pattern: the angle of its strokes on the sheet stays the same along the band
#   (a fixed pattern - cfg WALL_ZONES, plan/rules/30 §10) or turns with it (CURVED_ZONES, plan/rules/30 §4); the entry to
#   add is printed. A spiral stair or a ramp's lane lines may be listed too: look at the tile.
#   Out: arcs_audit.json, arcs_audit.png (the listed bands: source | walls over the source).
# Run in a floor folder after the walls (reads walls.pkl): python3 arcs_audit.py [min_cover=0.9] [walls.pkl] [out prefix]
import pickle, sys, os, json, math, collections
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import load, pts, PDF, MM_PER_PT
import numpy as np
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union
from shapely.strtree import STRtree
from shapely.prepared import prep
MINC = float(sys.argv[1]) if len(sys.argv) > 1 else 0.9
P = load(); cls = pickle.load(open('cls.pkl', 'rb'))
WP = sys.argv[2] if len(sys.argv) > 2 else 'walls.pkl'; OUTP = sys.argv[3] if len(sys.argv) > 3 else 'arcs_audit'
W = pickle.load(open(WP, 'rb'))['Wpt']; WU = unary_union([g for v in W.values() for g in v]) if W else Polygon()
M = 1000 / MM_PER_PT                                                   # one metre in pt
ids = [i for i, p in enumerate(P) if p[0] in ('l', 'c') and cls[i] not in ('dim', 'axis', 'sheet', 'tag') and len(pts(p)) >= 2]
from scipy.spatial import cKDTree
# nodes: end points closer than 0.05 pt are one node (rounding would split some of them)
EP = np.array([v for i in ids for v in (pts(P[i])[0], pts(P[i])[-1])]); par = list(range(len(EP)))
def fnd(a):
    while par[a] != a: par[a] = par[par[a]]; a = par[a]
    return a
for a, b in cKDTree(EP).query_pairs(0.05): par[fnd(a)] = fnd(b)
NODE = {}; ends = collections.defaultdict(list)
for k, i in enumerate(ids):
    n0, n1 = fnd(2 * k), fnd(2 * k + 1); NODE[i] = (n0, n1); ends[n0].append(i); ends[n1].append(i)
def fit(X):
    A = np.c_[2 * X[:, 0], 2 * X[:, 1], np.ones(len(X))]; c = np.linalg.lstsq(A, (X ** 2).sum(1), rcond=None)[0]
    r2 = c[2] + c[0] ** 2 + c[1] ** 2
    if r2 <= 0: return None
    r = math.sqrt(r2); return c[0], c[1], r, float(np.abs(np.hypot(X[:, 0] - c[0], X[:, 1] - c[1]) - r).max())
# (a) chains: from a piece, the chain goes on to the piece of the same weight, colour and kind that starts at its end
#     (<= 0.05 pt) or after a gap <= 2 pt (floor 2: the ramp's arc breaks for 1.5 pt at a column), turning <= 10 deg -
#     hatch strokes that end on the line do not stop it; each chain is then cut greedily into pieces on one circle
#     (an arc runs into a straight wall at its ends)
EPT = cKDTree(EP)
def enddir(j, at_end):
    q = pts(P[j]); a, b = (q[-2], q[-1]) if at_end else (q[1], q[0]); L = math.dist(a, b)
    return ((b[0] - a[0]) / L, (b[1] - a[1]) / L) if L > 1e-9 else None
def nextpiece(j, at_end, seen):
    """the piece that goes on from the end (at_end) or the start of piece j, and whether it is walked backwards"""
    q = pts(P[j]); e = q[-1] if at_end else q[0]; d = enddir(j, at_end)
    if d is None: return None
    best = None
    for k in EPT.query_ball_point(e, 2.0):
        jj = ids[k // 2]; start = k % 2 == 0
        if jj == j or jj in seen or P[jj][0] != P[j][0] or P[jj][1] != P[j][1] or P[jj][2] != P[j][2]: continue
        qq = pts(P[jj]); s_ = qq[0] if start else qq[-1]; nx = qq[1] if start else qq[-2]
        L = math.dist(s_, nx)
        if L <= 1e-9: continue
        d2 = ((nx[0] - s_[0]) / L, (nx[1] - s_[1]) / L)
        if d[0] * d2[0] + d[1] * d2[1] < math.cos(math.radians(10)): continue
        g = math.dist(e, s_)
        if g > 0.05:                                                   # across a gap: the gap runs on too
            gd = ((s_[0] - e[0]) / g, (s_[1] - e[1]) / g)
            if d[0] * gd[0] + d[1] * gd[1] < math.cos(math.radians(10)): continue
        if best is None or g < best[0]: best = (g, jj, not start)
    return best
seen = set(); chains = []
for i in ids:
    if i in seen: continue
    q0 = pts(P[i])
    if not (0.3 <= math.dist(q0[0], q0[-1]) <= 0.6 * M): continue      # a chord of an arc is short
    seen.add(i); seq = [(i, False)]                                    # (piece, walked backwards)
    j, fwd = i, True                                                   # forwards from the end of piece i
    while (nb := nextpiece(j, fwd, seen)) is not None:
        _, jj, rev = nb; seen.add(jj); seq.append((jj, rev)); j, fwd = jj, not rev
    j, fwd = i, False                                                  # backwards from its start
    while (nb := nextpiece(j, fwd, seen)) is not None:
        _, jj, rev = nb; seen.add(jj); seq.insert(0, (jj, not rev)); j, fwd = jj, not rev
    if len(seq) < 3: continue
    X = []
    for j, rev in seq:
        q = list(pts(P[j])); q = q[::-1] if rev else q
        X.extend(q[1:] if X and math.dist(X[-1], q[0]) <= 0.05 else q)
    X = np.array(X)
    s0 = 0
    while s0 < len(X) - 3:
        e = s0 + 3
        if (f := fit(X[s0:e + 1])) is None or f[3] > 0.2: s0 += 1; continue
        while e + 1 < len(X) and (g := fit(X[s0:e + 2])) is not None and g[3] <= 0.2: e += 1; f = g
        cx, cy, r, _ = f; Y = X[s0:e + 1]
        L = float(np.hypot(*np.diff(Y, axis=0).T).sum())
        a = np.unwrap(np.arctan2(Y[:, 1] - cy, Y[:, 0] - cx)); a0, a1 = sorted((math.degrees(a[0]), math.degrees(a[-1])))
        if L >= 1.5 * M and 1 * M <= r <= 60 * M and a1 - a0 >= 15:
            sh = (a0 + 180) % 360 - 180 - a0                           # a0 in [-180, 180), a1 = a0 + the turn
            chains.append(dict(c=(cx, cy), r=r, a0=a0 + sh, a1=a1 + sh, n=e - s0, w=P[i][1], X=Y)); s0 = e
        else: s0 += 1          # not an arc (a straight run fits a huge circle into the start of the arc it runs into)
# concentric arcs: a short arc fixes its centre poorly (floor 2: pieces of the ramp's arcs of 15-35 deg put it 2.4 pt
#   apart), so arcs whose centres lie within 2 % of the radius + 1 pt are refitted together - one centre, a radius each
par_ = list(range(len(chains)))
def fc(a):
    while par_[a] != a: par_[a] = par_[par_[a]]; a = par_[a]
    return a
for m, p in enumerate(chains):
    for n_, q in enumerate(chains[:m]):
        if math.dist(p['c'], q['c']) <= 0.02 * max(p['r'], q['r']) + 1 and abs(p['r'] - q['r']) <= 12: par_[fc(m)] = fc(n_)
grp_ = collections.defaultdict(list)
for m in range(len(chains)): grp_[fc(m)].append(m)
for ms in grp_.values():
    if len(ms) < 2: continue
    rows_ = []; rhs = []
    for k, m in enumerate(ms):
        for x, y in chains[m]['X']:
            e_ = [0.0] * len(ms); e_[k] = 1.0; rows_.append([2 * x, 2 * y] + e_); rhs.append(x * x + y * y)
    sol = np.linalg.lstsq(np.array(rows_), np.array(rhs), rcond=None)[0]; cx, cy = sol[0], sol[1]
    rs = [math.sqrt(max(0.0, sol[2 + k] + cx * cx + cy * cy)) for k in range(len(ms))]
    if max(float(np.abs(np.hypot(chains[m]['X'][:, 0] - cx, chains[m]['X'][:, 1] - cy) - rs[k]).max()) for k, m in enumerate(ms)) > 0.3: continue
    for k, m in enumerate(ms):
        Y = chains[m]['X']; a = np.degrees(np.unwrap(np.arctan2(Y[:, 1] - cy, Y[:, 0] - cx))); a0, a1 = float(a.min()), float(a.max())
        sh = (a0 + 180) % 360 - 180 - a0; chains[m].update(c=(cx, cy), r=rs[k], a0=a0 + sh, a1=a1 + sh)
# (b) rings: arcs of one centre (<= 1 pt) and one radius (<= 0.35 pt) are one line drawn in pieces - their angles are
#     merged; bands lie between two rings 0.8-10 pt apart, over the angles both cover and no ring between them covers
def merge(iv):
    out = []
    for a, b in sorted(iv):
        if out and a <= out[-1][1] + 1.0: out[-1][1] = max(out[-1][1], b)
        else: out.append([a, b])
    return out
def inter(A, B):
    out = []
    for a0, a1 in A:
        for b0, b1 in B:
            for s_ in (-360, 0, 360):
                lo, hi = max(a0, b0 + s_), min(a1, b1 + s_)
                if hi > lo: out.append([lo, hi])
    return merge(out)
def minus(A, B):
    out = [list(x) for x in A]
    for b0, b1 in B:
        nxt = []
        for a0, a1 in out:
            for s_ in (-360, 0, 360):
                lo, hi = b0 + s_, b1 + s_
                if hi <= a0 or lo >= a1: continue
                if lo > a0: nxt.append([a0, lo])
                a0 = max(a0, hi)
                if a0 >= a1: break
            if a0 < a1: nxt.append([a0, a1])
        out = nxt
    return out
rings = []
for ch in sorted(chains, key=lambda c: c['r']):
    for R in rings:
        if math.dist(R['c'], ch['c']) <= 1 and abs(R['r'] - ch['r']) <= 0.35:
            R['iv'] = merge(R['iv'] + [[ch['a0'], ch['a1']]]); R['rs'].append(ch['r']); break
    else: rings.append(dict(c=ch['c'], r=ch['r'], rs=[ch['r']], iv=[[ch['a0'], ch['a1']]]))
for R in rings: R['r'] = float(np.mean(R['rs']))
bands = []
for m, p in enumerate(rings):
    for q in rings[m + 1:]:
        if math.dist(p['c'], q['c']) > 1 or not (0.8 <= abs(p['r'] - q['r']) <= 10): continue
        lo_r, hi_r = sorted((p['r'], q['r'])); iv = inter(p['iv'], q['iv'])
        for z in rings:
            if z is not p and z is not q and math.dist(z['c'], p['c']) <= 1 and lo_r + 0.2 < z['r'] < hi_r - 0.2: iv = minus(iv, z['iv'])
        cx, cy = (p['c'][0] + q['c'][0]) / 2, (p['c'][1] + q['c'][1]) / 2
        for o in iv:
            if o[1] - o[0] < 10: continue
            n = max(2, int((o[1] - o[0]) / 1.0) + 1); ts = [math.radians(o[0] + (o[1] - o[0]) * k / (n - 1)) for k in range(n)]
            ring = [(cx + hi_r * math.cos(t), cy + hi_r * math.sin(t)) for t in ts] + [(cx + lo_r * math.cos(t), cy + lo_r * math.sin(t)) for t in ts[::-1]]
            g = Polygon(ring).buffer(0)
            if not g.is_empty and g.area > 0: bands.append(dict(c=(cx, cy), r=(lo_r, hi_r), a=tuple(o), g=g))
# (c) the pattern and the cover of each band. A glazing band (a grey fill over >= 50 % of it, mullions across) is not a
#     wall: it must lie on a facade line of cfg.FACADES (within FACADE_BAND), or its fills belong to the facade or glass
#     partition objects of assign2.pkl
import importlib.util
_sp = importlib.util.spec_from_file_location('cfg', 'cfg.py'); cfg = importlib.util.module_from_spec(_sp); _sp.loader.exec_module(cfg)
_FBW = max(3.0, float(getattr(cfg, 'FACADE_BAND', 14)))
def _zg(z):
    return Polygon([(z[0], z[1]), (z[2], z[1]), (z[2], z[3]), (z[0], z[3])]) if len(z) == 4 and all(isinstance(v, (int, float)) for v in z) else LineString(z[0]).buffer(z[1], cap_style=2)
OPZ = unary_union([_zg(z['zone']) for z in getattr(cfg, 'WALL_ZONES', [])]) if getattr(cfg, 'WALL_ZONES', []) else Polygon()   # the operator's walls: a grey X lining there is no glazing
FZ = unary_union([LineString(f).buffer(_FBW) for f in getattr(cfg, 'FACADES', []) if len(f) >= 2]) if getattr(cfg, 'FACADES', []) else Polygon()
GFI = [i for i, p in enumerate(P) if p[0] == 'qu' and p[3] is not None and abs(p[3][0] - p[3][1]) < 0.03
       and abs(p[3][1] - p[3][2]) < 0.03 and p[3][0] <= 0.85 and len(pts(p)) >= 3]
GF = [Polygon(pts(P[i])).buffer(0) for i in GFI]
GFT = STRtree(GF) if GF else None
# glazing the plan already holds - the facade and the glass partitions (floor 5: the rounded corner of a meeting room)
GLASS = set()
if os.path.exists('assign2.pkl'):
    _inst, _free = pickle.load(open('assign2.pkl', 'rb'))
    GLASS = {i for q in _inst if q['key'] in ('facade', 'glass', 'glass45', 'door45') for i in q['prims']}
LI = [i for i in ids if P[i][0] == 'l']; MID = [Point((P[i][4][0][0] + P[i][4][1][0]) / 2, (P[i][4][0][1] + P[i][4][1][1]) / 2) for i in LI]
MT = STRtree(MID)
rows = []
for b in bands:
    inF = b['g'].intersection(FZ).area / b['g'].area if not FZ.is_empty else 0.0
    if inF >= 0.5: continue                                            # the facade's band
    _gj = [j for j in GFT.query(b['g'])] if GFT is not None else []
    grey = (unary_union([GF[j] for j in _gj]).intersection(b['g']).area / b['g'].area) if _gj else 0.0
    held = (unary_union([GF[j] for j in _gj if GFI[j] in GLASS]).intersection(b['g']).area / b['g'].area) if _gj else 0.0
    if grey >= 0.5 and held >= 0.5 * grey: continue                   # glazing the plan holds as facade or glass
    if GLASS:                                                          # a glass partition's band: its lines are glass
        _in = [LI[j] for j in MT.query(b['g']) if b['g'].contains(MID[j])]
        if _in and sum(1 for i in _in if i in GLASS) >= 0.5 * len(_in): continue
    cx, cy = b['c']; lo_r, hi_r = b['r']; wd = hi_r - lo_r; gp = prep(b['g'].buffer(0.05))
    st = []
    for j in MT.query(b['g']):
        i = LI[j]; (x1, y1), (x2, y2) = P[i][4]; L = math.dist((x1, y1), (x2, y2))
        if L < 0.3 or L > 3 * wd + 1 or (P[i][1] or 0) > 0.35 or not gp.contains(LineString(P[i][4])): continue
        m = MID[j]; pa = math.degrees(math.atan2(m.y - cy, m.x - cx)); t = math.degrees(math.atan2(y2 - y1, x2 - x1)) % 180
        rel = ((t - (pa + 90)) % 180 + 90) % 180 - 90
        if abs(rel) < 10: continue                                     # along the band: a line of the band itself
        st.append((pa, t, rel))
    mid_len = math.radians(b['a'][1] - b['a'][0]) * (lo_r + hi_r) / 2
    dens = len(st) / (mid_len / M) if mid_len > 0 else 0
    if dens < 1.5: continue
    cov = b['g'].intersection(WU).area / b['g'].area
    # glazing: a grey band with few strokes across (mullions, < 6 per metre); a grey band with an X across is the lining of
    #   a wall (floor 2: the plasterboard of the ramp's arc is a grey strip with an X)
    glazing = grey >= 0.5 and dens < 6 and not (not OPZ.is_empty and b['g'].intersection(OPZ).area >= 0.5 * b['g'].area)
    # fixed or turning: the spread of the strokes' sheet angles against the spread of their angles to the band
    def spread(v):
        h = collections.Counter(round(x / 5) * 5 % 180 for x in v); top = h.most_common(2)
        return sum(n for _, n in top) / len(v)
    fixed = spread([t for _, t, _ in st]) >= spread([r for _, _, r in st])
    lo_a, hi_a = b['a']; rc = (lo_r + hi_r) / 2; hw = wd / 2 + 0.1
    entry = (f"FACADES+=[arc_points({cx:.1f},{cy:.1f},{rc:.2f},{lo_a:.1f},{hi_a:.1f},1.0)]  # glazing, not on a facade line" if glazing
             else f"WALL_ZONES+=[dict(zone=(arc_points({cx:.1f},{cy:.1f},{rc:.2f},{lo_a:.1f},{hi_a:.1f},1.0),{hw:.2f}),cls='?',why='arc band')]" if fixed
             else f"CURVED_ZONES+=[(arc_points({cx:.1f},{cy:.1f},{rc:.2f},{lo_a:.1f},{hi_a:.1f},1.0),{hw + 1:.2f})]")
    ok = cov >= MINC and not glazing                                   # a glazing band off the facade lines is listed
    rows.append(dict(centre_pt=[round(float(cx), 2), round(float(cy), 2)], r_pt=[round(float(lo_r), 2), round(float(hi_r), 2)], angles=[round(float(lo_a), 1), round(float(hi_a), 1)],
                     width_mm=round(wd * MM_PER_PT), length_m=round(mid_len / M, 1), strokes=len(st), per_m=round(dens, 1),
                     cover=round(cov, 3), pattern='glazing' if glazing else 'fixed' if fixed else 'turns with the band', ok=ok, entry=None if ok else entry,
                     bbox_pt=[round(v, 1) for v in b['g'].bounds]))
rows.sort(key=lambda r: (r['ok'], r['cover']))
bad = [r for r in rows if not r['ok']]
json.dump(dict(arcs=len(chains), bands=len(bands), hatched=len(rows), below=len(bad), min_cover=MINC, rows=rows), open(OUTP + '.json', 'w'), ensure_ascii=False, indent=0)
print('arcs', len(chains), '| bands', len(bands), '| with a pattern', len(rows), '| covered < %d %%' % round(100 * MINC), len(bad))
for r in bad: print('  ', r['centre_pt'], 'r', r['r_pt'], 'deg', r['angles'], r['length_m'], 'm', 'cover', r['cover'], r['pattern'], '\n     ', r['entry'])
# sheet of the listed bands
import pymupdf as fitz
from PIL import Image, ImageDraw, ImageFont
pg = fitz.open(PDF)[0]; f = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 12)
tiles = []
for r in bad[:12]:
    x0, y0, x1, y1 = r['bbox_pt']; pad = 4; x0 -= pad; y0 -= pad; x1 += pad; y1 += pad
    Z = min(8.0, 460 / max(x1 - x0, y1 - y0))
    pix = pg.get_pixmap(matrix=fitz.Matrix(Z, Z), clip=fitz.Rect(x0, y0, x1, y1))
    src = Image.frombytes('RGB', (pix.width, pix.height), pix.samples)
    im = Image.blend(src, Image.new('RGB', src.size, 'white'), 0.6); d = ImageDraw.Draw(im, 'RGBA')
    for g in getattr(WU, 'geoms', [WU]):
        if g.geom_type == 'Polygon' and g.intersects(Polygon([(x0, y0), (x1, y0), (x1, y1), (x0, y1)])):
            d.polygon([((a - x0) * Z, (b_ - y0) * Z) for a, b_ in g.exterior.coords], fill=(0, 170, 60, 110))
    t = Image.new('RGB', (src.width * 2 + 10, src.height + 34), 'white'); t.paste(src, (0, 34)); t.paste(im, (src.width + 10, 34))
    ImageDraw.Draw(t).text((4, 2), f"центр {r['centre_pt']}, r {r['r_pt']} pt, {r['angles']}°, {r['length_m']} м: стенами покрыто {round(100 * r['cover'])} %, {'витраж не на линии FACADES' if r['pattern'] == 'glazing' else 'узор неподвижный' if r['pattern'] == 'fixed' else 'узор поворачивает с дугой'}", fill=(0, 0, 0), font=f)
    tiles.append(t)
if tiles:
    Wd = max(t.width for t in tiles); H = sum(t.height + 8 for t in tiles); sh = Image.new('RGB', (Wd, H), (235, 235, 235)); y = 0
    for t in tiles: sh.paste(t, (0, y)); y += t.height + 8
    sh.save(OUTP + '.png')
