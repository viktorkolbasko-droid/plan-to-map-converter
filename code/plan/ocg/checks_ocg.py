"""Test 8 checks (owner 06.10.2026: «в стенах не должно быть пустот, разрывов, каких-то мелких неровностей. Как можно за
этим следить?») in one report, each a number that must be 0 or is listed with places:
 - walls: vertices, vertices on straight runs (3.1) with the reason each one stays (узел стыка / узкое место / прочее = 0);
 - holes in wall bodies (a void inside a wall) — must be 0;
 - short edges of a wall outline (< 0.8 of the wall's thickness): justified when at a joint (another body or glass
   <= 0.35 pt), at a door opening (<= 1 pt), the end of the wall (an edge across its whole thickness) or drawn by the
   source (test 9: wall strokes along >= half of the edge — «как в исходнике»); the rest — «не оправдан» = 0 or listed;
 - breaks: two wall bodies <= 3 pt apart with no door (its opening, or its frame strokes across the gap), opening or
   glass between them — listed;
 - irregularities thinner than the wall (Э6в): how many straightened, kept at an element, kept for review;
 - walls drawn as lines; hanging lines (both ends free) and hanging lines of the core outline (Э7я);
 - doors (Э7д): rebuilt to the scheme, not rebuilt; core blocks (Э7я); furniture: left for review, seat figures, desks of
   an unfamiliar size. usage: python3 t8_checks.py out.json
Code 009 (ocg/checks_ocg.py, the checks of the layer route for its gate ocg/gate_ocg.py): + doors without the opening of the
scheme (Т8-15) and walls as lines outside the core blocks (test 8 §2, Т8-18); the sheet's layers and glass - cfg (ocg/sheet.py)."""
import pickle, json, sys, collections, math, os
import shapely.ops
import numpy as np, shapely
from shapely.geometry import Point, LineString
from shapely.ops import unary_union
import os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import sheet; from e7_comp import geom, load_prims, load_walls
K = sheet.K; PT = sheet.pt          # code 009: thresholds set in pt on the reference sheet -> this sheet (exact there)
P = load_prims()['P']; O = pickle.load(open('objects.pkl', 'rb')); objs = O['objs']; W = load_walls()['bodies']
def straight_vertices(g, dev=PT(0.02), turn=10.0):
    n = 0
    for r in [g.exterior, *g.interiors]:
        c = np.array(r.coords)[:-1]; m = len(c)
        for i in range(m):
            a, b, d = c[i - 1], c[i], c[(i + 1) % m]; u, v = b - a, d - b; lu, lv = np.linalg.norm(u), np.linalg.norm(v)
            if lu < 1e-9 or lv < 1e-9: n += 1; continue
            ang = math.degrees(math.acos(max(-1.0, min(1.0, (u @ v) / lu / lv)))); w = d - a; lw = np.linalg.norm(w)
            h = abs(w[0] * (b - a)[1] - w[1] * (b - a)[0]) / lw if lw > 1e-9 else 0.0
            if ang <= 0.5 or (h <= dev and ang <= turn): n += 1
    return n
def straight_reasons(B, panes):
    """why a straight-run vertex is still there: 'узел стыка' — its two edges pass by another body or a glass pane (<= 0.35 pt)
    and the joint needs it; 'узкое место' — without it the outline crosses itself; 'прочее' — should be 0 (rule 3.1)"""
    from shapely.geometry import Polygon as _Pg
    BG = [g for _, g in B]; others = BG + panes; tr = shapely.STRtree(others); r = collections.Counter(); ex = collections.defaultdict(list)
    for k, g in enumerate(BG):
        rings = [list(map(tuple, g.exterior.coords[:-1]))] + [list(map(tuple, h.coords[:-1])) for h in g.interiors]
        for ri, c in enumerate(rings):
            m = len(c)
            for i in range(m):
                a, b, d = np.array(c[i - 1]), np.array(c[i]), np.array(c[(i + 1) % m]); u, v = b - a, d - b; lu, lv = np.linalg.norm(u), np.linalg.norm(v)
                if lu > 1e-9 and lv > 1e-9:
                    ang = math.degrees(math.acos(max(-1.0, min(1.0, (u @ v) / lu / lv)))); w = d - a; lw = np.linalg.norm(w)
                    h = abs(w[0] * (b - a)[1] - w[1] * (b - a)[0]) / lw if lw > 1e-9 else 0.0
                    if not (ang <= 0.5 or (h <= PT(0.02) and ang <= 10.0)): continue
                rr = [list(x) for x in rings]; rr[ri] = rr[ri][:i] + rr[ri][i + 1:]
                try: ok = len(rr[ri]) >= 3 and _Pg(rr[0], [x for x in rr[1:] if len(x) >= 3]).is_valid
                except Exception: ok = False
                foot = LineString([tuple(a), tuple(b), tuple(d)])
                near = any(j != k and others[j].distance(foot) <= PT(0.35) for j in tr.query(foot.buffer(PT(0.36))))
                why = 'узкое место' if not ok else 'узел стыка' if near else 'прочее'
                r[why] += 1
                if len(ex[why]) < 20: ex[why].append([round(float(b[0]), 1), round(float(b[1]), 1)])
    return dict(r), dict(ex)
res = {}
nv = sum(len(g.exterior.coords) - 1 + sum(len(h.coords) - 1 for h in g.interiors) for _, g in W)
res['walls'] = dict(bodies=len(W), by_class=dict(collections.Counter(c for c, _ in W)), vertices=nv, straight_run_vertices=sum(straight_vertices(g) for _, g in W),
                    area_m2={c: round(sum(g.area for c2, g in W if c2 == c) * K * K / 1e6, 2) for c in set(c for c, _ in W)})
_GL = sheet.GLASS; _WL = sheet.L('wall')
_panes = [geom(p) for p in P if p['kind'] in ('fill', 'wline') and p.get('col') in _GL and p['layer'] in _WL]
_panes = [g for g in _panes if g.geom_type == 'Polygon' and g.area > 0]
res['walls']['straight_run_reasons'], res['walls']['straight_run_places'] = straight_reasons(W, _panes)
lines_ = collections.Counter(); lines_len = collections.Counter()
for o in objs:
    if o['key'] in ('lpart', 'wallline', 'coreline'):
        lines_[o['key']] += 1; lines_len[o['key']] += sum(geom(P[i]).length for i in o['ids'] if P[i]['kind'] != 'removed') * K / 1000
res['walls_as_lines'] = dict(objects=dict(lines_), length_m={k: round(v, 1) for k, v in lines_len.items()},
                             note='lpart — перегородки без штриховки, оставшиеся линиями; coreline — контур ядра (линии слоёв «Стены»/«Линии»)')
# hanging lines: a line object whose every end touches nothing (0.1 pt) of anything else drawn
LINEK = ('lpart', 'wallline', 'coreline', 'furn', 'deskedge', 'group', 'table')      # «+» marks stand alone by design
allg = [g for _, g in W] + [geom(P[i]) for o in objs if o['key'] not in ('zone', 'corezone', 'axis', 'dim', 'tagc', 'empty') for i in o.get('draw', o['ids']) if P[i]['kind'] != 'removed']
tree = shapely.STRtree(allg); hang = []
for k, o in enumerate(objs):
    if o['key'] not in LINEK or not o['ids'] or 'draw' in o: continue
    gs = [geom(P[i]) for i in o['ids'] if P[i]['kind'] == 'line']
    if not gs: continue
    u = unary_union(gs); ends = []
    for g in getattr(u, 'geoms', [u]):
        if g.geom_type == 'LineString' and not g.is_closed: ends += [Point(g.coords[0]), Point(g.coords[-1])]
    if not ends: continue
    own = set(id(g) for g in gs)
    free = 0
    for e in ends:
        hit = [j for j in tree.query(e.buffer(PT(0.1))) if allg[j].distance(e) <= PT(0.1) and not any(allg[j].equals(g) for g in gs)]
        if not hit: free += 1
    if free == len(ends): hang.append(dict(obj=k, key=o['key'], at=[round(v, 1) for v in u.centroid.coords[0]], length_mm=round(u.length * K)))
res['hanging_lines'] = dict(n=len(hang), by_key=dict(collections.Counter(h['key'] for h in hang)), places=hang[:60])
# ---- holes, short edges, breaks
GL_ = shapely.STRtree(_panes) if _panes else None
DOORR = [geom(P[o['draw'][0]]) for o in objs if o['key'] == 'door' and o.get('draw') and P[o['draw'][0]]['kind'] == 'line' and len(P[o['draw'][0]]['p']) == 5]
DOORR = [LineString(g.coords).convex_hull if g.geom_type == 'LineString' else g for g in DOORR]; DT_ = shapely.STRtree(DOORR) if DOORR else None
BG_ = [g for _, g in W]; BT_ = shapely.STRtree(BG_)
# test 9: a short edge the source draws (strokes or fill edges of the drawing — furniture, dimensions, axes, sprinklers,
# notes not counted — along >= half of it, within 0.08 pt, parallel within 10°) is the client's wall — a step of its
# thickness, a jog — not an artifact of the build
_EX = sheet.L('furniture', 'plant', 'dim', 'fire', 'tag', 'axis')     # code 010: by roles - furniture, plants, dimensions, fire valves, tags, axes
_wsg = [geom(p) for p in P if p['layer'] not in _EX and p['kind'] in ('line', 'fill', 'wline') and not p.get('synthetic') and len(p['p']) >= 2]
_wst = shapely.STRtree(_wsg)
def drawn(a, b, cov=0.5):
    e = LineString([tuple(a), tuple(b)]); L_ = e.length
    if L_ < 1e-9: return True
    u = (np.asarray(b) - np.asarray(a)) / L_; zone = e.buffer(0.08, cap_style=2); s_ = 0.0
    for q in _wst.query(zone):
        x = _wsg[q]; x = x.boundary if x.geom_type == 'Polygon' else x
        it = x.intersection(zone)
        for pc in getattr(it, 'geoms', [it]):
            if pc.geom_type != 'LineString' or pc.length < 1e-6: continue
            v = np.array(pc.coords[-1]) - np.array(pc.coords[0]); v = v / np.linalg.norm(v)
            if abs(float(u @ v)) >= 0.985: s_ += pc.length
    return s_ >= cov * L_
holes = []; short = collections.Counter(); short_pl = []
for k, (c, g) in enumerate(W):
    for h in g.interiors:
        hp = shapely.geometry.Polygon(h)
        holes.append(dict(at=[round(v, 1) for v in hp.centroid.coords[0]], area_pt2=round(hp.area, 3), cls=c))
    if c == 'column': continue
    t = 2 * g.area / g.length if g.length > 0 else 0.0
    for r in [g.exterior, *g.interiors]:
        cs = [np.array(v) for v in list(r.coords)[:-1]]; m = len(cs)
        if m < 3: continue
        def turn(i):                         # signed turn at vertex i (degrees)
            u, v = cs[i] - cs[i - 1], cs[(i + 1) % m] - cs[i]
            return math.degrees(math.atan2(u[0] * v[1] - u[1] * v[0], u @ v))
        for i in range(m):
            a, b = cs[i], cs[(i + 1) % m]; L_ = float(np.linalg.norm(b - a))
            if L_ >= 0.8 * t or L_ < 1e-6: continue
            e = LineString([tuple(a), tuple(b)]); t1, t2 = turn(i), turn((i + 1) % m)
            if abs(t1) <= 25 and abs(t2) <= 25: why = 'дуга или плавный поворот'
            elif any(j != k and BG_[j].distance(e) <= PT(0.35) for j in BT_.query(e.buffer(PT(0.36)))) or (GL_ is not None and any(_panes[j].distance(e) <= PT(0.35) for j in GL_.query(e.buffer(PT(0.36))))): why = 'стык'
            elif DT_ is not None and any(DOORR[j].distance(e) <= PT(1.0) for j in DT_.query(e.buffer(PT(1.0)))): why = 'проём'
            elif t1 * t2 > 0 and abs(t1) >= 60 and abs(t2) >= 60 and L_ >= 0.4 * t: why = 'торец стены'
            elif drawn(a, b): why = 'ступенька — как в исходнике' if t1 * t2 < 0 and abs(t1) >= 60 and abs(t2) >= 60 else 'ребро — как в исходнике'
            elif t1 * t2 < 0 and abs(t1) >= 60 and abs(t2) >= 60 and drawn(cs[i - 1], a) and drawn(b, cs[(i + 2) % m]): why = 'ступенька — как в исходнике'   # both faces drawn: two faces of the client's wall
            elif t1 * t2 < 0 and abs(t1) >= 60 and abs(t2) >= 60: why = 'ступенька — не оправдана'
            else: why = 'прочее — не оправдано'
            short[why] += 1
            if 'не оправдан' in why and len(short_pl) < 300: short_pl.append(dict(at=[round(v, 1) for v in e.centroid.coords[0]], length_mm=round(L_ * K), wall_t_mm=round(t * K), why=why))
for h_ in holes: h_['what'] = 'пустота в стене' if h_['area_pt2'] < PT(PT(10)) else 'помещение внутри кольца стен'
res['walls']['holes'] = dict(n=len(holes), voids=sum(1 for h_ in holes if h_['what'] == 'пустота в стене'), places=holes[:100])
res['walls']['short_edges'] = dict(by_reason=dict(short), not_justified=short_pl)
brk = []
# test 9: a door's frame strokes (its prims on the doors' layer) across the gap — the door's jamb fills it (J6 the same)
_dfr = [geom(P[i]) for o in objs if o['key'] == 'door' for i in o.get('draw', o['ids']) if P[i]['kind'] == 'line' and P[i]['layer'] in sheet.L('door') and len(P[i]['p']) >= 2]
_dft = shapely.STRtree(_dfr) if _dfr else None
for k, (c, g) in enumerate(W):
    for j in BT_.query(g.buffer(PT(3.0))):
        if j <= k: continue
        d = BG_[j].distance(g)
        if not (PT(0.05) < d <= PT(3.0)): continue
        pa, pb = shapely.ops.nearest_points(g, BG_[j]); gap = LineString([pa, pb]).buffer(PT(0.3))
        if DT_ is not None and any(DOORR[q].intersects(gap) for q in DT_.query(gap)): continue
        if _dft is not None and any(_dfr[q].intersects(gap) for q in _dft.query(gap)): continue
        if GL_ is not None and any(_panes[q].intersects(gap) for q in GL_.query(gap)): continue
        # test 9: another body across the gap (>= half of it) — the two do not meet, but the wall is whole: not a break
        seg_ = LineString([pa, pb]); oth_ = [BG_[q] for q in BT_.query(seg_) if q not in (k, j)]
        if oth_ and seg_.intersection(shapely.ops.unary_union(oth_)).length >= 0.5 * seg_.length: continue
        brk.append(dict(at=[round((pa.x + pb.x) / 2, 1), round((pa.y + pb.y) / 2, 1)], gap_mm=round(d * K), classes=[c, W[j][0]]))
res['walls']['breaks_without_door'] = dict(n=len(brk), places=brk[:200])
try:
    WC = json.load(open('walls_clean.json')); res['walls']['irregularities_e6c'] = WC.get('irregularities')
except Exception: pass
try: res['core'] = {k: v for k, v in json.load(open('core.json')).items() if k not in ('connectors_mm',)}
except Exception: pass
try: res['doors_e7d'] = {k: v for k, v in json.load(open('doors.json')).items() if k not in ('doors',)}
except Exception: pass
G = json.load(open('geom_report.json'))
res['doors'] = G['counts']
J = json.load(open('joints.json')); res['joints'] = dict(before=J['before'], after=J['after'], fixes=J['fixes'], door_contour_ends=J['door_contour_ends'])
F = json.load(open('furniture.json')); res['furniture'] = dict(numbers_on_desks=F['numbers_on_desks'], desk_numbers=F['desk_numbers'], desks=F['desks'],
                                                              seat_figures=F['places'].get('seat_figures', [])[:30], desks_unfamiliar_size=F['places'].get('desks_unfamiliar_size', []),
                                                              typical_desk_sizes_mm=F['typical_desk_sizes_mm'], left_for_review=F['left_for_review'],
                                                              by_type=dict(collections.Counter(o['key'] for o in objs if o['key'] in ('desk', 'chair', 'armchair', 'sofa', 'round', 'rtable', 'mtable', 'dtable', 'ctable', 'storage', 'pedestal', 'kitchen', 'table', 'counter'))))
try: res['passage'] = json.load(open('passage.json'))
except Exception: pass
# ---- code 009 (ocg/, package 3): two more measures for the gate of the layer route, on the final objects
# doors (Т8-15): every door (not a detail) is drawn by the scheme "opening - leaf - arc": its drawing holds the opening
#   (a closed rectangle of 4 points across the wall, prim 'opening'); a door without it - not rebuilt or lost its opening
_dn = []
for k, o in enumerate(objs):
    if o['key'] != 'door' or 'деталь' in (o.get('name') or ''): continue
    dr_ = o.get('draw', o['ids'])
    if not any(P[i].get('opening') and P[i]['kind'] != 'removed' for i in dr_):
        g_ = unary_union([geom(P[i]) for i in o['ids'] if P[i]['kind'] != 'removed'] or [Point(0, 0)])
        _dn.append(dict(obj=k, name=o.get('name'), at=[round(v, 1) for v in g_.centroid.coords[0]]))
res['doors_no_opening'] = dict(n=len(_dn), places=_dn[:60])
# joints of the final bodies (3.4; Т8-12), measured here on the bodies the DXF draws (load_walls) - not the report of Э7с
#   itself: an overlap of two bodies > 0.005 pt², a gap (closing of the pair by 0.3 pt minus the pair, in the zone of the
#   joint) > 0.005 pt²
def _measure_joints(BW):
    BG = [g for _, g in BW]; bt = shapely.STRtree(BG); r = collections.Counter(); pl = []
    for a, ga in enumerate(BG):
        for b in bt.query(ga.buffer(PT(0.3))):
            if b <= a: continue
            gb = BG[b]
            if ga.distance(gb) > PT(0.3): continue
            ov = ga.intersection(gb).area
            zone = ga.buffer(PT(0.35)).intersection(gb.buffer(PT(0.35)))
            U = ga.union(gb); seam = U.buffer(PT(0.3), join_style=2).buffer(-PT(0.3), join_style=2).difference(U).intersection(zone)
            pair = '–'.join(sorted((BW[a][0], BW[b][0])))
            if ov > PT(PT(0.005)): r[f'нахлёст {pair}'] += 1
            if seam.area > PT(PT(0.005)): r[f'щель {pair}'] += 1
            if (ov > PT(PT(0.005)) or seam.area > PT(PT(0.005))) and len(pl) < 300:
                c = zone.centroid; pl.append(dict(at=[round(c.x, 1), round(c.y, 1)], pair=pair, overlap_mm2=round(ov * K * K), gap_mm2=round(seam.area * K * K)))
    return dict(r), pl
_jr, _jp = _measure_joints(W)
res['joints_final'] = dict(bodies=_jr, n=sum(_jr.values()), places=_jp[:100])
# walls as lines outside the core (test 8 §2: "стена линией, а не полигоном — 0 вне ядра"; Т8-18): a line object of a wall
#   class (lpart, wallline, coreline) whose lines lie inside the core blocks for < 95 % of their length (+0.3 pt)
_blocks = unary_union([geom(P[i]) for o in objs if o['key'] == 'coreblock' for i in o.get('draw', o['ids'])[:1] if P[i]['kind'] != 'removed']) if any(o['key'] == 'coreblock' for o in objs) else None
_bb = _blocks.buffer(PT(0.3)) if _blocks is not None and not _blocks.is_empty else None
_wl = []
for k, o in enumerate(objs):
    if o['key'] not in ('lpart', 'wallline', 'coreline') or not o['ids']: continue
    gs_ = [geom(P[i]) for i in o.get('draw', o['ids']) if P[i]['kind'] == 'line']      # what the result draws (Э7я keeps only hanging core lines)
    if not gs_: continue
    u_ = unary_union(gs_); L_ = u_.length
    if L_ <= 0: continue
    inside = u_.intersection(_bb).length / L_ if _bb is not None else 0.0
    if inside >= 0.95: continue
    _wl.append(dict(obj=k, key=o['key'], at=[round(v, 1) for v in u_.centroid.coords[0]], length_mm=round(L_ * K), in_core=round(inside, 2)))
res['walls_as_lines_outside_core'] = dict(n=len(_wl), by_key=dict(collections.Counter(w['key'] for w in _wl)),
                                          length_m=round(sum(w['length_mm'] for w in _wl) / 1000, 1), places=_wl[:100])
# code 011 (ПК4-П13, package 5): the ends of door openings on the faces of walls or glass (owner 06.10.2026: «прямоугольник…
#   стыкующаяся слева и справа со стеной»; №105: the opening from the face of one wall to the face of the other). An end of an
#   opening (its short side) farther than END_TOL from every wall body, glass pane and core block is off the face: a gap
#   between the door and the wall that O3 (gaps between bodies) and O8 (the opening exists) do not see. Threshold END_TOL =
#   0.3 pt at 48.04 mm/pt (14 mm, the touch of the joints J1), sheet.pt() for another scale; the gap is written in mm - the
#   nearest distance and the distance along the opening's axis (the median of 5 rays at 10-90 % of its depth, <= 6 pt).
#   Doors named «деталь» (pieces of an opening) are not doors of the scheme - as doors_no_opening.
_END_TOL = PT(0.3)
_core_pg = []
for o in objs:
    if o['key'] != 'coreblock': continue
    for i in o.get('draw', o['ids'])[:1]:
        if P[i]['kind'] == 'removed': continue
        g_ = geom(P[i]); g_ = shapely.geometry.Polygon(g_.coords) if g_.geom_type == 'LineString' and g_.is_closed and len(g_.coords) >= 4 else g_
        if g_.geom_type == 'Polygon' and g_.is_valid: _core_pg.append(g_)
_EE = BG_ + _panes + _core_pg; _EET = shapely.STRtree(_EE)
_de = []; _de_n = 0
for k, o in enumerate(objs):
    if o['key'] != 'door' or 'деталь' in (o.get('name') or ''): continue
    op_ = [i for i in o.get('draw', o['ids']) if P[i].get('opening') and P[i]['kind'] != 'removed' and len(P[i]['p']) >= 4]
    if not op_: continue
    c_ = np.array(P[op_[0]]['p'][:4], float); e01, e12 = np.linalg.norm(c_[1] - c_[0]), np.linalg.norm(c_[2] - c_[1])
    if e01 >= e12: ends_ = [(c_[1], c_[2]), (c_[3], c_[0])]; u_ = (c_[1] - c_[0]) / max(e01, 1e-9)
    else: ends_ = [(c_[0], c_[1]), (c_[2], c_[3])]; u_ = (c_[2] - c_[1]) / max(e12, 1e-9)
    cen_ = c_.mean(0)
    for a_, b_ in ends_:
        _de_n += 1
        side = LineString([tuple(a_), tuple(b_)])
        d_ = min((_EE[j].distance(side) for j in _EET.query(side.buffer(PT(6.0)))), default=None)
        if d_ is not None and d_ <= _END_TOL: continue
        s_ = 1.0 if (((a_ + b_) / 2 - cen_) @ u_) > 0 else -1.0; hs = []
        for t in np.linspace(0.1, 0.9, 5):
            p0 = a_ + (b_ - a_) * t; ray = LineString([tuple(p0), tuple(p0 + u_ * s_ * PT(6.0))])
            ds = [Point(tuple(p0)).distance(_EE[j].intersection(ray)) for j in _EET.query(ray) if _EE[j].intersects(ray)]
            if ds: hs.append(min(ds))
        m_ = (a_ + b_) / 2
        _de.append(dict(obj=k, name=o.get('name'), at=[round(float(m_[0]), 1), round(float(m_[1]), 1)],
                        gap_mm=None if d_ is None else round(d_ * K), along_mm=round(float(np.median(hs)) * K) if len(hs) >= 3 else None))
res['door_ends'] = dict(ends=_de_n, off_face=len(_de), tol_mm=round(_END_TOL * K, 1), places=_de[:100])
# code 012 (СО-2): thin strips of the wall layers with a free end (Э6) - every one with its verdict; barriers given to desks (Э7м-б)
try:
    _ws = json.load(open('walls_stats.json')); _bj = json.load(open('barriers.json')) if os.path.exists('barriers.json') else {}
    res['walls']['free_end_strips'] = dict(n=len(_ws.get('free_strips', [])), by_verdict=dict(collections.Counter(r['verdict'].split(':')[0] for r in _ws.get('free_strips', []))),
                                           places=_ws.get('free_strips', []), barriers_to_desks=_bj.get('barriers', []), barriers_not_found=_bj.get('not_found', []))
except Exception as ex: res['walls']['free_end_strips'] = dict(error=f'{type(ex).__name__}: {ex}')
json.dump(res, open(sys.argv[1], 'w'), ensure_ascii=False, indent=1)
print(json.dumps({k: v for k, v in res.items() if k not in ('hanging_lines',)}, ensure_ascii=False)[:3000])
print('hanging lines', res['hanging_lines']['n'], res['hanging_lines']['by_key'])
print('door ends', res['door_ends']['ends'], 'off the face of a wall or glass', res['door_ends']['off_face'], [(p['at'], p['gap_mm']) for p in res['door_ends']['places'][:6]])
print('holes', res['walls']['holes']['n'], 'voids', res['walls']['holes']['voids'], '| short edges', res['walls']['short_edges']['by_reason'], '| breaks without door', res['walls']['breaks_without_door']['n'])
