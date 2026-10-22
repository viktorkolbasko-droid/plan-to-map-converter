# Geometry QA of a finished floor (plan/rules/60 §4): run in a floor folder after export.
#   3.1 minimum vertices: redundant polygon vertices (on a straight run), mergeable collinear line pieces
#   3.2 axis alignment: edges / lines / block rotations a little off 0/90 deg
#   3.3 wall integrity: gaps between wall bodies and what justifies each
#   3.4 joints: door jambs and glazing ends against the walls, hairline gaps between wall bodies
# Usage: python3 geomqa.py [walls.pkl] [dxf] [out.json]
import sys, os, math, json, pickle, collections
import numpy as np, ezdxf
from shapely.geometry import Polygon, LineString, Point, MultiPolygon
from shapely.ops import unary_union, nearest_points
from shapely.strtree import STRtree
from common import MM_PER_PT, DXF, cfg, load, MM, walls_file, pts, FACADES
WPATH = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] else walls_file()
DPATH = sys.argv[2] if len(sys.argv) > 2 else DXF
OUT = sys.argv[3] if len(sys.argv) > 3 else 'geomqa.json'
W = pickle.load(open(WPATH, 'rb'))['W']
inst = pickle.load(open('inst_final.pkl', 'rb'))
R = {}
Q = 0.12 * MM_PER_PT            # print quantum of the Revit PDFs (0.12 pt) in mm
def polys(g):
    return [g] if g.geom_type == 'Polygon' else [x for x in getattr(g, 'geoms', []) if x.geom_type == 'Polygon']
ALLW = [p for v in W.values() for g in v for p in polys(g)]
WU = unary_union(ALLW)
BODIES = polys(WU)
# ---------------- 3.1 redundant vertices of wall rings
def ring_redundant(coords, ang_tol=0.5, dist_tol=1.0):
    c = list(coords)[:-1]; n = len(c); red = 0
    if n < 4: return n, 0
    for i in range(n):
        a, b, d = c[i - 1], c[i], c[(i + 1) % n]
        L = math.dist(a, d)
        if math.dist(a, b) < 0.5 or math.dist(b, d) < 0.5: red += 1; continue      # near-duplicate vertex
        if L < 1e-9: continue
        dev = abs((d[0] - a[0]) * (a[1] - b[1]) - (a[0] - b[0]) * (d[1] - a[1])) / L   # distance of b from chord a-d
        t1 = math.atan2(b[1] - a[1], b[0] - a[0]); t2 = math.atan2(d[1] - b[1], d[0] - b[0])
        turn = abs((math.degrees(t2 - t1) + 180) % 360 - 180)
        if turn <= ang_tol or dev <= dist_tol and turn <= 10: red += 1
    return n, red
nv = nr = 0
for p in ALLW:
    for r in [p.exterior] + list(p.interiors):
        a, b = ring_redundant(r.coords); nv += a; nr += b
R['wall_ring_vertices'] = nv; R['wall_ring_redundant'] = nr
# ---------------- 3.2 wall edges off the axes
def axis_dev(a, b):
    """(angle to the nearest axis deg, lateral offset mm, length mm)"""
    dx, dy = b[0] - a[0], b[1] - a[1]; L = math.hypot(dx, dy)
    if L < 1e-9: return 0, 0, 0
    t = math.degrees(math.atan2(dy, dx)) % 90
    d = min(t, 90 - t)
    lat = min(abs(dy), abs(dx))
    return d, lat, L
bins = collections.Counter(); off = []; real = []
from common import in_curved, kx as _kx, ky as _ky
def _pt(p): return ((p[0] - _kx[1]) / _kx[0], (p[1] - _ky[1]) / _ky[0])
for p in ALLW:
    for r in [p.exterior] + list(p.interiors):
        c = list(r.coords)
        for n_, (a, b) in enumerate(zip(c, c[1:])):
            d, lat, L = axis_dev(a, b)
            if L < 1: continue
            if d == 0 or lat < 0.01: bins['axis'] += 1
            elif d <= 10 and lat <= 2 * Q: bins['near_axis_snap'] += 1; off.append((lat, d, L))
            elif d <= 10:
                bins['near_axis_real'] += 1
                # a visible angle is justified when it is a chord of a curve (curved zone, or a neighbour turning
                #   by 0.2-25 deg the same way) or when the source draws a straight line at that angle there
                pa, pb = c[n_ - 1] if n_ > 0 else c[-2], c[n_ + 2] if n_ + 2 < len(c) else c[1]
                def turn(u, v):
                    t_ = math.degrees(math.atan2(v[1], v[0]) - math.atan2(u[1], u[0])); return (t_ + 180) % 360 - 180
                t1 = turn((a[0] - pa[0], a[1] - pa[1]), (b[0] - a[0], b[1] - a[1])); t2 = turn((b[0] - a[0], b[1] - a[1]), (pb[0] - b[0], pb[1] - b[1]))
                m = _pt(((a[0] + b[0]) / 2, (a[1] + b[1]) / 2))
                why = 'curve' if in_curved(m) or 0.2 < abs(t1) < 25 or 0.2 < abs(t2) < 25 else 'straight'
                real.append(dict(at_pt=[round(m[0], 1), round(m[1], 1)], angle=round(d, 2), length_mm=round(L), kind=why))
            elif abs(d - 45) <= 1: bins['diag45'] += 1
            else: bins['other'] += 1
# a straight slanted edge: is there a source line along it at the same angle (the source draws the slant)?
if real:
    _P0 = load(); _cls0 = pickle.load(open('cls.pkl', 'rb'))
    _SL = [(i, p) for i, p in enumerate(_P0) if p[0] == 'l' and _cls0[i] not in ('axis', 'dim', 'sheet') and math.dist(*p[4]) >= 0.8]
    _SG = STRtree([LineString(p[4]) for i, p in _SL])
    for e in real:
        if e['kind'] != 'straight': continue
        m = Point(e['at_pt']); ok = False
        for j in _SG.query(m.buffer(1.0)):
            a_, b_ = _SL[int(j)][1][4]; t_ = math.degrees(math.atan2(b_[1] - a_[1], b_[0] - a_[0])) % 90; d_ = min(t_, 90 - t_)
            # (28.09.2026) a source line at least 0.6 of the edge (floor 2: the teeth of a sawtooth wall edge are 1.9 pt)
            if abs(d_ - e['angle']) <= 0.5 and LineString([a_, b_]).distance(m) <= 1.0 and math.dist(a_, b_) >= 0.6 * e['length_mm'] / MM_PER_PT: ok = True; break
        e['kind'] = 'straight, drawn so in the source' if ok else 'straight, NOT in the source'
R['wall_edges'] = dict(bins)
R['near_axis_real_kinds'] = dict(collections.Counter(e['kind'] for e in real))
R['near_axis_real_unjustified'] = [e for e in real if e['kind'] == 'straight, NOT in the source']
R['wall_edges_snap_lateral_mm'] = {'max': round(max([o[0] for o in off], default=0), 1),
                                   'p95': round(float(np.percentile([o[0] for o in off], 95)) if off else 0, 1)}
# ---------------- DXF: polylines, lines, rotations
doc = ezdxf.readfile(DPATH)
def seg_stats(layout, tag):
    st = collections.Counter(); lines = collections.defaultdict(list)
    for e in layout:
        t = e.dxftype()
        if t == 'LWPOLYLINE':
            pts = [tuple(p[:2]) for p in e.get_points('xy')]
            closed = e.closed
            if closed and len(pts) > 2 and pts[0] != pts[-1]: pts = pts + [pts[0]]
            n, red = ring_redundant(pts) if closed and len(pts) >= 4 else (len(pts), 0)
            if not closed and len(pts) >= 3:
                for a, b, d in zip(pts, pts[1:], pts[2:]):
                    t1 = math.atan2(b[1] - a[1], b[0] - a[0]); t2 = math.atan2(d[1] - b[1], d[0] - b[0])
                    if abs((math.degrees(t2 - t1) + 180) % 360 - 180) <= 0.5: red += 1
            st['poly'] += 1; st['poly_vertices'] += len(pts); st['poly_redundant'] += red
            for a, b in zip(pts, pts[1:]):
                d, lat, L = axis_dev(a, b)
                if L >= 1 and 0 < d <= 10 and 0.01 <= lat <= 2 * Q: st['poly_seg_near_axis'] += 1
        elif t == 'LINE':
            a = (e.dxf.start.x, e.dxf.start.y); b = (e.dxf.end.x, e.dxf.end.y)
            st['lines'] += 1
            d, lat, L = axis_dev(a, b)
            if L >= 1 and 0 < d <= 10 and 0.01 <= lat <= 2 * Q: st['line_near_axis'] += 1
            lines[e.dxf.layer].append((a, b))
    # collinear pieces that touch or overlap (same layer): each merge removes one entity
    mergeable = 0
    for lay, ls in lines.items():
        groups = collections.defaultdict(list)
        for a, b in ls:
            L = math.dist(a, b)
            if L < 0.5: continue
            t = math.atan2(b[1] - a[1], b[0] - a[0]) % math.pi
            nx, ny = -math.sin(t), math.cos(t)
            off_ = a[0] * nx + a[1] * ny
            groups[(round(math.degrees(t) / 0.2), round(off_ / 1.0))].append((a, b, t))
        for g in groups.values():
            if len(g) < 2: continue
            t = g[0][2]; ux, uy = math.cos(t), math.sin(t)
            iv = sorted(tuple(sorted((a[0] * ux + a[1] * uy, b[0] * ux + b[1] * uy))) for a, b, _ in g)
            end = iv[0][1]
            for s, e_ in iv[1:]:
                if s <= end + 0.5: mergeable += 1; end = max(end, e_)
                else: end = e_
    st['lines_mergeable'] = mergeable
    return st
ms = seg_stats(doc.modelspace(), 'msp')
bs = collections.Counter()
for blk in doc.blocks:
    if blk.name.startswith('*'): continue
    bs.update(seg_stats(blk, blk.name))
R['dxf_modelspace'] = dict(ms); R['dxf_blocks'] = dict(bs)
rot = collections.Counter(); rot_ex = []
for e in doc.modelspace().query('INSERT'):
    r = e.dxf.rotation % 90; d = min(r, 90 - r)
    if 0.01 < d <= 3:
        rot[e.dxf.name.split('_')[0]] += 1; rot_ex.append((e.dxf.name, round(e.dxf.rotation, 2)))
R['inserts_near_axis'] = dict(rot); R['inserts_near_axis_examples'] = rot_ex[:12]
# ---------------- 3.3 gaps between wall bodies
tree = STRtree(BODIES)
doors = [q for q in inst if q['key'] == 'door' and q.get('hinge_mm')]
DP = [Point(q['hinge_mm']) for q in doors] + [Point(q['closed_mm']) for q in doors]
def lines_of(keys):
    out = []
    P = load() if not hasattr(lines_of, 'P') else lines_of.P
    lines_of.P = P
    for q in inst:
        if q['key'] in keys:
            for i in q['prims']:
                if P[i][0] == 'l': out.append(LineString([MM(P[i][4][0]), MM(P[i][4][1])]))
    return out
CARRIER = unary_union([l.buffer(30) for l in lines_of(('facade', 'glass', 'lpart', 'lpartc', 'gklpart', 'glasspart', 'railing', 'rdoor', 'door45', 'stair', 'lift', 'column'))])
gaps = []
for i, A in enumerate(BODIES):
    for j in tree.query(A.buffer(1500)):
        j = int(j)
        if j <= i: continue
        B = BODIES[j]; d = A.distance(B)
        if not (0.5 < d <= 1500): continue
        pa, pb = nearest_points(A, B); mid = Point((pa.x + pb.x) / 2, (pa.y + pb.y) / 2)
        door = min((mid.distance(p) for p in DP), default=1e9) <= max(700, d)
        carr = CARRIER.distance(mid) <= 60
        gaps.append(dict(gap_mm=round(d), at_mm=[round(mid.x), round(mid.y)], door=bool(door), element=bool(carr), pair=[i, j]))
R['wall_gaps'] = len(gaps)
R['wall_gaps_hairline_le_20mm'] = sum(1 for g in gaps if g['gap_mm'] <= 20)
R['wall_gaps_unexplained'] = [g for g in gaps if not g['door'] and not g['element'] and g['gap_mm'] > 20]
# (28.09.2026) what the source draws in an unexplained gap - a strip 300 mm wide from one body to the other, 30 mm
#   off each body: nothing (thin lines and room separation lines aside) -> an opening of the source (a passage without
#   a door); thick lines along the strip over >= 60 % of the gap -> a wall the source draws as an outline only (no
#   hatch: drawn as lines, plan/rules/30); anything else -> look at it
_Pg = load(); _clsg = pickle.load(open('cls.pkl', 'rb'))
_colk = {c_['key'] for c_ in getattr(cfg, 'COLOR_ELEMENTS', [])}
_ownc = {i for q in inst if q['key'] in _colk and (not getattr(cfg, 'COLOR_OWN_ONLY', True) or q.get('colour')) for i in q['prims']}   # (cfg.COLOR_OWN_ONLY, 30.09.2026) see reclass.py
_SL = [(i, LineString([MM(v) for v in pts(_Pg[i])])) for i in range(len(_Pg)) if _Pg[i][0] in ('l', 'c') and _clsg[i] not in ('axis', 'dim', 'sheet') and i not in _ownc]
_ST = STRtree([g for i, g in _SL])
for g in R['wall_gaps_unexplained']:
    A_, B_ = BODIES[g['pair'][0]], BODIES[g['pair'][1]]
    pa, pb = nearest_points(A_, B_); L_ = pa.distance(pb)
    ux, uy = (pb.x - pa.x) / L_, (pb.y - pa.y) / L_
    seg = LineString([(pa.x + ux * 30, pa.y + uy * 30), (pb.x - ux * 30, pb.y - uy * 30)])
    strip = seg.buffer(150, cap_style=2)
    along = 0.0; other = 0
    for j in _ST.query(strip):
        i, ln = _SL[int(j)]
        part = ln.intersection(strip)
        if part.is_empty or part.length < 1: continue
        c_ = list(ln.coords); dx, dy = c_[-1][0] - c_[0][0], c_[-1][1] - c_[0][1]; n_ = math.hypot(dx, dy)
        par = n_ > 0 and abs(dx * ux + dy * uy) / n_ >= math.cos(math.radians(15))
        if _Pg[i][1] >= 0.45 and par: along = max(along, part.length)
        elif _Pg[i][1] >= 0.2: other += 1
    g['source'] = ('outline wall' if along >= 0.6 * seg.length else 'opening (nothing drawn)' if other == 0 else 'lines - look')
R['wall_gaps_unexplained_by_source'] = dict(collections.Counter(g['source'] for g in R['wall_gaps_unexplained']))
# ---------------- 3.3b a wall that ends before the source wall does: hatch strokes outside the walls that go on
#   with the hatch of a wall body next to them (same colour and width, parallel within 12 deg to its nearest stroke,
#   length x0.4-2.5, within 8 pt of it), both ends on other lines (hatch ends on the band outline). Floor 4: the
#   lower stub of the stair enclosure was taken by the glazing band and stayed an outline.
def _hatch_continuation():
    from wallcont import continuation, diag_zones
    own_ = {}
    for q in inst:
        for i in q['prims']: own_[i] = q['key']
    return continuation(load(), pickle.load(open('cls.pkl', 'rb')), own_, pickle.load(open(WPATH, 'rb'))['Wpt'], pts, axis_ok=diag_zones(cfg))
R['wall_hatch_continuation'] = _hatch_continuation()
R['wall_hatch_continuation_strokes'] = sum(d['n'] for d in R['wall_hatch_continuation'])
for d in R['wall_hatch_continuation']:
    b_ = d['bbox_pt']; d['skip'] = any(z[0] <= b_[0] and b_[2] <= z[2] and z[1] <= b_[1] and b_[3] <= z[3] for z in getattr(cfg, 'WALL_CONT_SKIP', []))
R['wall_hatch_continuation_not_reviewed'] = sum(1 for d in R['wall_hatch_continuation'] if not d['skip'])
# ---------------- 3.4 joints: a door meets its jambs on both sides - a wall body, a light / glass partition, the
#   glazing, a column, or a jamb piece drawn at the opening (frame, cubicle post: a small shape within 3 pt of the
#   hinge / closed end). Gap = distance of the hinge / closed end from them (> 20 mm reported); overlap = length of the
#   closed-leaf line inside wall bodies (> 20 mm reported). Pair leaves meet each other at the closed end.
_P = load()
def _lines_of(keys):
    out = []
    for q in inst:
        if q['key'] in keys:
            for i in q['prims']:
                if _P[i][0] in ('l', 'c'): out.append(LineString([MM(v) for v in pts(_P[i])]))
    return out
_carr = [WU] + [l.buffer(6) for l in _lines_of(('lpart', 'lpartc', 'gklpart', 'glasspart', 'railing', 'glass', 'facade', 'column', 'door45', 'rdoor'))]
_jam_keys = ('wcacc', 'misc', 'wallline', 'loose', 'doorhw', 'lpart', 'lpartc', 'gklpart', 'glasspart', 'railing', 'doorframe')   # doorframe: an operator's name for a jamb box (floor 5, 30.09)
_jam = []
for q in inst:
    if q['key'] not in _jam_keys: continue
    for i in q['prims']:
        ps_ = [MM(v) for v in pts(_P[i])]
        xs_, ys_ = [p[0] for p in ps_], [p[1] for p in ps_]
        if max(xs_) - min(xs_) <= 3 * MM_PER_PT and max(ys_) - min(ys_) <= 3 * MM_PER_PT:
            _jam.append((LineString(ps_) if len(ps_) > 1 else Point(ps_[0])).buffer(6))
_JT = STRtree(_jam) if _jam else None
CARR = unary_union(_carr)
WUi = WU.buffer(-6)
jam = []
for q in doors:
    H = Point(q['hinge_mm']); C = Point(q['closed_mm'])
    def gap(p):
        d = CARR.distance(p)
        if _JT is not None and d > 20:
            near = [_jam[int(j)] for j in _JT.query(p.buffer(3 * MM_PER_PT))]
            if near: d = min(d, min(g.distance(p) for g in near))
        return d
    dh = gap(H); dc = gap(C)
    op = LineString([q['hinge_mm'], q['closed_mm']])
    # (28.09.2026) only a leaf that goes into the wall counts: the part of the closed-leaf line inside a wall body
    #   deeper than 25 mm somewhere. The fire-cabinet door ПК6 (floor 1) lies along the wall face, 13 mm in:
    #   'overlap 480 mm' was the face itself
    ins = op.intersection(WU); intr = 0.0
    if ins.length > 0:
        _pp = [g_.interpolate(t, normalized=True) for g_ in (getattr(ins, 'geoms', None) or [ins]) if g_.length > 0 for t in np.linspace(0, 1, 11)]
        _dep = max((WU.boundary.distance(x) for x in _pp if WU.contains(x)), default=0.0)
        if _dep > 25: intr = ins.length
    jam.append(dict(name=q['name'], at_mm=[round(H.x), round(H.y)], hinge_gap=round(dh), closed_gap=round(dc),
                    overlap=round(intr), pair=bool(q.get('pair'))))
R['doors'] = len(jam)
R['doors_hinge_gap_gt_20mm'] = sum(1 for j in jam if j['hinge_gap'] > 20)
R['doors_closed_gap_gt_20mm'] = sum(1 for j in jam if j['closed_gap'] > 20 and not j['pair'])
R['doors_overlap_gt_20mm'] = sum(1 for j in jam if j['overlap'] > 20)
R['doors_detail'] = [j for j in jam if j['hinge_gap'] > 20 or (j['closed_gap'] > 20 and not j['pair']) or j['overlap'] > 20][:60]
# glazing ends: each facade line end should meet a wall body or a column (mm)
_col = unary_union([l.buffer(6) for l in _lines_of(('column',))]) if any(q['key'] == 'column' for q in inst) else None
fe = []
for f in FACADES:
    for e in (f[0], f[-1]):
        p = Point(MM(e)); d = WU.distance(p)
        if _col is not None and not _col.is_empty: d = min(d, _col.distance(p))
        fe.append(round(d))
R['facade_ends_gap_mm'] = fe
# (28.09.2026) the facade line of cfg is the axis of the glazing band, the drawn glazing is the source's own glass
#   lines (instance 'facade'). The joint is the drawn glass against its carrier - a wall body, a column, a partition
#   or a wall drawn as outline (lpart, lpartc, wallline, glass lines): glass_to_carrier_mm > 20 is a gap in the drawing
_gl = [l for l in _lines_of(('facade',))]
_GT = STRtree(_gl) if _gl else None
# (cfg.GLAZING_CARRIERS_EXTRA, 30.09.2026, floor 5: ('lift',)) the glazing may end at another carrier - the portal of a
#   panoramic lift; default (): other floors do not change
_cr = unary_union([WU] + [l.buffer(6) for l in _lines_of(('column', 'lpart', 'lpartc', 'gklpart', 'glasspart', 'railing', 'wallline', 'glass') + tuple(getattr(cfg, 'GLAZING_CARRIERS_EXTRA', ())))])
fe2 = []
for f in FACADES:
    for e in (f[0], f[-1]):
        p = Point(MM(e)); dc = _cr.distance(p)
        zone = p.buffer(max(600.0, 1.5 * dc))
        near = [_gl[int(j)] for j in _GT.query(zone)] if _GT is not None else []
        cz = _cr.intersection(p.buffer(max(600.0, 1.5 * dc) + 300))
        g2c = min((l.distance(cz) for l in near), default=None) if not cz.is_empty else None
        fe2.append(dict(end_pt=[round(e[0], 1), round(e[1], 1)], to_wall_mm=round(WU.distance(p)), to_carrier_mm=round(dc),
                        glass_to_carrier_mm=None if g2c is None else round(g2c)))
R['facade_ends'] = fe2
R['facade_ends_glass_gap_gt_20mm'] = [x for x in fe2 if x['glass_to_carrier_mm'] is None or x['glass_to_carrier_mm'] > 20]
# wall bodies of different classes must not overlap (joints of walls)
ov = []
cls_polys = [(k, p) for k, v in W.items() for g in v for p in polys(g)]
ct = STRtree([p for k, p in cls_polys])
for i_, (k, p) in enumerate(cls_polys):
    for j_ in ct.query(p):
        j_ = int(j_)
        if j_ <= i_ or cls_polys[j_][0] == k: continue
        a_ = p.intersection(cls_polys[j_][1]).area
        if a_ > 1000: ov.append(dict(classes=[k, cls_polys[j_][0]], area_mm2=round(a_), at_mm=[round(c) for c in p.intersection(cls_polys[j_][1]).centroid.coords[0]]))
R['wall_class_overlaps'] = ov
json.dump(R, open(OUT, 'w'), ensure_ascii=False, indent=1)
for k, v in R.items():
    if k in ('doors_detail', 'wall_gaps_unexplained', 'inserts_near_axis_examples', 'wall_hatch_continuation', 'wall_class_overlaps', 'near_axis_real_unjustified', 'facade_ends', 'facade_ends_glass_gap_gt_20mm'): print(k, len(v) if isinstance(v, list) else v, v[:6] if isinstance(v, list) else '')
    else: print(k, v)
