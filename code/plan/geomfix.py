# Geometry clean-up of a finished floor (plan/rules/50 §9; the checks are plan/rules/60 §4 / geomqa.py).
# Stage between export and svg, cwd = the floor folder:
#   walls   : edges off 0/90 deg by print noise made exact (vertex groups: shared corners and T-junctions move
#             together), straight runs with two points; walls_fixed.pkl (W mm, Wpt pt) - export's walls.pkl is kept
#             for the recognition regression (compare_runs)
#   DXF     : wall entities rewritten from walls_fixed; in every block and in the loose linework of every layer:
#             duplicate and collinear line pieces merged, straight polylines -> lines, redundant vertices dropped,
#             near-axis pieces snapped the same way; inserts a hair off 0/90 deg turned onto the axis
# Everything moves a vertex by at most 2 print quanta (0.24 pt): below what the source can show, inside the strict
# ink tolerance (0.4 pt). Report -> geomfix.json.
import sys, math, json, pickle, collections
import numpy as np, ezdxf
from shapely.geometry import Polygon, MultiPolygon
from shapely.validation import make_valid
from common import MM_PER_PT, DXF, cfg, kx, ky, in_curved
from geomlib import snap_chains, simplify_run, merge_lines
from wallsdxf import write_walls, WALL_LAYERS
Q = 0.12 * MM_PER_PT             # print quantum of the Revit PDFs, mm
SNAP = 2 * Q
REP = {'quantum_mm': round(Q, 2), 'snap_max_mm': round(SNAP, 2)}
def mm2pt(p): return ((p[0] - kx[1]) / kx[0], (p[1] - ky[1]) / ky[0])
def curved_mm(m): return in_curved(mm2pt(m))
def polys(g): return [g] if g.geom_type == 'Polygon' else [x for x in getattr(g, 'geoms', []) if x.geom_type == 'Polygon']

# ---------------- walls
D = pickle.load(open('walls.pkl', 'rb')); W = D['W']
chains = []; where = []
for k, v in W.items():
    for gi, g in enumerate(v):
        for pi, p in enumerate(polys(g)):
            for ri, r in enumerate([p.exterior] + list(p.interiors)):
                chains.append((list(r.coords)[:-1], True)); where.append((k, gi, pi, ri))
rw = collections.Counter()
snapped = snap_chains(chains, SNAP, curved=curved_mm, report=rw)
rings = collections.defaultdict(dict)
nv0 = nv1 = 0
for (c0, _), (c1, _), (k, gi, pi, ri) in zip(chains, snapped, where):
    s = simplify_run(c1, True, tol=0.2)
    nv0 += len(c0); nv1 += len(s)
    rings[(k, gi, pi)][ri] = s
W2 = {}; bad = []; darea = []; rep_valid = []; slivers = []
def clean_poly(q):
    """rings without collinear vertices; holes thinner than one print quantum (2A/P <= Q) are hairline gaps inside
    the body, not rooms: dropped (plan/rules/60 §4, integrity)"""
    ext = simplify_run(list(q.exterior.coords)[:-1], True, tol=0.2)
    hs = []
    for h in q.interiors:
        hp = Polygon(h)
        if hp.area <= 0 or 2 * hp.area / hp.length <= Q:
            slivers.append((round(hp.area), [round(c) for c in hp.centroid.coords[0]] if hp.area > 0 else None)); continue
        hs.append(simplify_run(list(h.coords)[:-1], True, tol=0.2))
    r = Polygon(ext, hs)
    return r if r.is_valid else q
for k, v in W.items():
    out = []
    for gi, g in enumerate(v):
        parts = []
        for pi, p in enumerate(polys(g)):
            rr = rings[(k, gi, pi)]
            ext = rr[0]; holes = [rr[i] for i in sorted(rr) if i > 0 and len(rr[i]) >= 3]
            q = Polygon(ext, holes) if len(ext) >= 3 else p
            if not q.is_valid:
                # a hairline hole or notch closed by the snap makes the ring touch itself: repair, keep the body
                q2 = make_valid(q); q2 = [x for x in polys(q2) if x.area > 1]
                q = max(q2, key=lambda x: x.area) if q2 else p
                rep_valid.append((k, [round(c) for c in p.centroid.coords[0]]))
            q = clean_poly(q)
            # a snap moves an edge by at most SNAP: more change than the outline x one quantum means it reshaped
            #   the body (keep the original then)
            dA = abs(q.area - p.area); da = dA / max(p.area, 1)
            if dA > p.length * Q:
                bad.append((k, [round(c) for c in p.centroid.coords[0]], round(da, 3))); q = p
            darea.append(da); parts.append(q)
        out.append(parts[0] if len(parts) == 1 else MultiPolygon(parts))
    W2[k] = out
# (28.09.2026) bodies of two classes that did not overlap before the snap must not overlap after it: the snap moved the
#   shared face of one of them across the other (floor 4, cap / gkl: a 0.03 pt sliver). The later class in PRIO gives
#   way - its body loses the overlap, when that is a sliver (<= its outline x one quantum)
from shapely.ops import unary_union
PRIO = ['ext', 'cap', 'blk', 'gkl']
_before = {k: unary_union([p for g in v for p in polys(g)]) for k, v in W.items()}
ov_fixed = []
_keys = [k for k in PRIO if k in W2] + [k for k in W2 if k not in PRIO]
for _i, ka in enumerate(_keys):
    UA = unary_union([p for g in W2[ka] for p in polys(g)])
    for kb in _keys[_i + 1:]:
        if _before[ka].intersection(_before[kb]).area > 1: continue      # they overlapped before the snap: not ours
        new = []
        for g in W2[kb]:
            x_ = g.intersection(UA)
            if x_.area > 0 and x_.area <= g.length * Q:
                g2 = [p for p in polys(g.difference(UA)) if p.area > 1]
                if g2: ov_fixed.append((ka, kb, round(x_.area))); g = g2[0] if len(g2) == 1 else MultiPolygon(g2)
            new.append(g)
        W2[kb] = new
REP['class_overlaps_removed'] = ov_fixed
def to_pt(g):
    def ring(r): return [mm2pt(c) for c in r.coords]
    ps = [Polygon(ring(p.exterior), [ring(h) for h in p.interiors]) for p in polys(g)]
    return ps[0] if len(ps) == 1 else MultiPolygon(ps)
Wpt2 = {k: [to_pt(g) for g in v] for k, v in W2.items()}
D2 = dict(D); D2['W'] = W2; D2['Wpt'] = Wpt2; D2['fixed'] = True
pickle.dump(D2, open('walls_fixed.pkl', 'wb'))
REP['walls'] = dict(rw); REP['walls'].update(ring_vertices_before=nv0, ring_vertices_after=nv1, reverted=bad, repaired=rep_valid, sliver_holes_dropped=slivers,
                                          max_area_change=round(max(darea, default=0), 4))
print('walls', REP['walls'])

# ---------------- DXF
doc = ezdxf.readfile(DXF); msp = doc.modelspace()
for e in list(msp):
    if e.dxf.layer in WALL_LAYERS and e.dxftype() in ('LWPOLYLINE', 'HATCH'): msp.delete_entity(e)
write_walls(msp, W2)
SKIP_LAYERS = WALL_LAYERS | {'A-AX----T-', 'A-AX----D-'}

def fix_layout(layout, entities, rep):
    """entities: LINE / LWPOLYLINE / solid HATCH of one layout (and one layer in modelspace)"""
    lines = collections.defaultdict(list); polys_ = []; hatches = []
    for e in entities:
        t = e.dxftype()
        # (code 007, 05.10.2026) an entity's own colour survives the clean-up: a glass door is drawn in the glass style
        #   (строка 172); entities of one layer and different colours are not merged
        col_ = (e.dxf.get('color', 256), tuple(e.rgb) if e.dxf.hasattr('true_color') and e.rgb else None)
        if t == 'LINE':
            lines[(e.dxf.layer, e.dxf.get('linetype', 'BYLAYER')) + col_].append(((e.dxf.start.x, e.dxf.start.y), (e.dxf.end.x, e.dxf.end.y)))
        elif t == 'LWPOLYLINE':
            if any(abs(b[0]) > 1e-9 for b in e.get_points('b')): continue       # arcs by bulge: keep as they are
            polys_.append(((e.dxf.layer,) + col_, bool(e.closed), [tuple(p[:2]) for p in e.get_points('xy')]))
        elif t == 'HATCH':
            if not e.dxf.solid_fill: continue
            paths = []
            for p in e.paths:
                if not hasattr(p, 'vertices') or any(abs(v[2]) > 1e-9 for v in p.vertices if len(v) > 2): paths = None; break
                paths.append(([(v[0], v[1]) for v in p.vertices], p.path_type_flags))
            if paths is None: continue
            hatches.append((e.dxf.layer, e.rgb, paths))
        else:
            continue
        layout.delete_entity(e)
    # one snap over everything of this layout: lines, polylines and fill boundaries share corners
    chains = []; tags = []
    for lay, ls in lines.items():
        for a, b in ls: chains.append(([a, b], False)); tags.append(('L', lay))
    for lay, closed, pts in polys_: chains.append((pts, closed)); tags.append(('P', lay, closed))
    for hi, (lay, rgb, paths) in enumerate(hatches):
        for pj, (pts, fl) in enumerate(paths): chains.append((pts, True)); tags.append(('H', hi, pj))
    n_in = sum(len(v) for v in lines.values()); nv_in = sum(len(p) for _, _, p in polys_) + sum(len(p) for _, _, ps in hatches for p, _ in ps)
    new = snap_chains(chains, SNAP, report=rep) if chains else []
    L2 = collections.defaultdict(list); P2 = []; H2 = [[lay, rgb, [None] * len(paths)] for lay, rgb, paths in hatches]
    for (pts, closed), tg in zip(new, tags):
        if tg[0] == 'L': L2[tg[1]].append((tuple(pts[0]), tuple(pts[1])))
        elif tg[0] == 'P':
            s = simplify_run(pts, tg[2], tol=0.2)
            if not tg[2] and len(s) == 2: L2[(tg[1][0], 'BYLAYER') + tuple(tg[1][1:])].append((s[0], s[1])); rep['polyline_to_line'] += 1
            elif len(s) >= 2: P2.append((tg[1], tg[2], s))
        else:
            H2[tg[1]][2][tg[2]] = simplify_run(pts, True, tol=0.2)
    n_out = 0
    for lay, ls in L2.items():
        for a, b in merge_lines(ls):
            if math.dist(a, b) < 0.05: continue
            at = {'layer': lay[0]}
            if lay[1] != 'BYLAYER': at['linetype'] = lay[1]
            if lay[2] not in (256, None): at['color'] = lay[2]
            e_ = layout.add_line(a, b, dxfattribs=at); n_out += 1
            if lay[3]: e_.rgb = lay[3]
    nv_out = 0
    for lay, closed, s in P2:
        at = {'layer': lay[0]}
        if lay[1] not in (256, None): at['color'] = lay[1]
        e_ = layout.add_lwpolyline(s, close=closed, dxfattribs=at); nv_out += len(s)
        if lay[2]: e_.rgb = lay[2]
    for (lay, rgb, paths), (_, _, old) in zip(H2, hatches):
        h = layout.add_hatch(dxfattribs={'layer': lay}); h.set_solid_fill()
        if rgb is not None: h.rgb = rgb
        for s, (_, fl) in zip(paths, old):
            if s is None or len(s) < 3: continue
            h.paths.add_polyline_path(s, is_closed=True, flags=fl); nv_out += len(s)
    rep['lines_in'] += n_in; rep['lines_out'] += n_out; rep['vertices_in'] += nv_in; rep['vertices_out'] += nv_out

rb = collections.Counter()
for blk in doc.blocks:
    if blk.name.startswith('*'): continue
    ents = [e for e in blk if e.dxftype() in ('LINE', 'LWPOLYLINE', 'HATCH')]
    if ents: fix_layout(blk, ents, rb)
REP['blocks'] = dict(rb); print('blocks', REP['blocks'])
rm = collections.Counter()
by_layer = collections.defaultdict(list)
for e in msp:
    if e.dxf.layer in SKIP_LAYERS or e.dxftype() not in ('LINE', 'LWPOLYLINE', 'HATCH'): continue
    by_layer[e.dxf.layer].append(e)
for lay, ents in by_layer.items(): fix_layout(msp, ents, rm)
REP['modelspace'] = dict(rm); print('modelspace', REP['modelspace'])

# ---------------- inserts a hair off the axes (<= 3 deg, the far end of the block moves <= SNAP)
def block_radius(name, _c={}):
    if name not in _c:
        r = 0.0
        for e in doc.blocks[name]:
            t = e.dxftype()
            if t == 'LINE': ps = [e.dxf.start, e.dxf.end]
            elif t == 'LWPOLYLINE': ps = [p for p in e.get_points('xy')]
            elif t == 'HATCH': ps = [v for p in e.paths if hasattr(p, 'vertices') for v in p.vertices]
            else: ps = []
            for p in ps: r = max(r, math.hypot(p[0], p[1]))
        _c[name] = r
    return _c[name]
ri = []
for e in msp.query('INSERT'):
    rot = e.dxf.rotation; k90 = round(rot / 90) * 90; d = abs(rot - k90)
    if not (1e-6 < d <= 3): continue
    sx, sy = abs(e.dxf.xscale), abs(e.dxf.yscale)
    mv = block_radius(e.dxf.name) * max(sx, sy) * math.sin(math.radians(d))
    if mv <= SNAP:
        e.dxf.rotation = float(k90 % 360); ri.append((e.dxf.name, round(rot, 3), round(mv, 1)))
    else:
        ri.append((e.dxf.name, round(rot, 3), round(mv, 1), 'kept: real rotation'))
REP['inserts_rotation'] = ri
doc.saveas(DXF)
json.dump(REP, open('geomfix.json', 'w'), ensure_ascii=False, indent=1)
print('inserts', ri[:10])
