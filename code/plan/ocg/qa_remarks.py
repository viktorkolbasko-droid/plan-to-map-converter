"""Checks of the owner's remarks of 09.10.2026 (З-1…З-24) on a delivered engineering-plan DXF — the rules of checking.
usage: python3 qa_remarks.py <dxf> <out.json> [zones.dxf]   (code 012, ocg/: ported from the v010 package, tools/qa_remarks.py;
       the scale and origin, the sample room and the passage width - from cfg; check() - the library call)
Every check counts places that break its rule; 0 — the rule holds. The places (sheet pt) go to the JSON for the sheets.
 ПЗ-1  extra points (ЛТ-1…ЛТ-3): the closing repeat of the first point, repeats closer than 1 mm, points on a straight line
       (closer than 0.5 mm to the chord of the neighbours) — in every contour of every layer;
 ПЗ-2  micro-kinks of walls, glass, core and columns (З-1…З-3): a step — two long edges of one direction (< 2°) offset by
       0.5…30 mm and joined by edges shorter than 60 mm; a kink — a turn of 0.1…2° between two edges longer than 100 mm;
 ПЗ-3  a straight wall piece is four points (З-1): a wall, glass or column outline that is its own rectangle (no point farther
       than 2 mm) with more than 4 vertices;
 ПЗ-4  one wall — one type (З-1.1): overlap of wall outlines of different classes or of a wall and a glass band (> 0.001 m²),
       and slivers — wall pieces narrower than 8 mm everywhere;
 ПЗ-5  curves (З-6, ЛТ-4): a run of 6 or more vertices that the arc fitter of the export takes for an arc (curves.py: on one
       circle within 1.5 mm or 0.1 % of the radius, chords alike, each chord within 0.5 % of the radius and 25 mm of its arc)
       over 15° or more — an arc written as points;
 ПЗ-6  the door swing arc is dashed (З-7): every arc of the door layer has the line type DOOR-SWING; a door layer polyline
       that is an arc;
 ПЗ-7  massive furniture (З-8, З-9; outline result): an outline of a table, cabinet, counter, kitchen, sofa with an edge
       shorter than 15 mm between two longer ones, or a corner off a right angle by 1…10° (a cut or skewed corner)."""
import sys, os, json, math, collections, pickle
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))     # code 012: the modules of ocg/ (dxf_pts, curves)
import dxf_pts as dp
import numpy as np
from shapely.geometry import Polygon, LineString
from shapely.ops import unary_union
import shapely
def check(DXF, zones_dxf=None, sample=None, width_mm=None):
    """the checks ПЗ-1…ПЗ-9 and the points of one DXF: dict(dxf, checks, places). zones_dxf - the zones DXF of the floor; sample -
    dict(name, points) of the owner's sample room (cfg.OCG_ROOM_SAMPLE); width_mm - the width of a passage (ПЗ-9)."""
    K = dp.K
    if K is None: raise SystemExit('qa_remarks: не задано преобразование выгрузки (dxf_pts.set_frame / frame_from_sheet)')
    R, _ = dp.load(DXF)
    res = collections.OrderedDict(); places = collections.defaultdict(list)
    def mm(a, b): return math.dist(a, b) * K
    def at(p): return [round(p[0], 1), round(p[1], 1)]
    WALLK = {'gkl', 'blk', 'wall_ext', 'cap', 'coreblock', 'coreoutline', 'column', 'glass', 'lpart', 'facade'}
    # ---------------------------------------------------------------- ПЗ-1
    c1 = collections.Counter()
    for r in R:
        V = r['V']; n = len(V)
        if n < 2: continue
        if r['closed'] and n > 2 and mm(V[0], V[-1]) < 1.0:
            c1['closing repeat'] += 1; places['ПЗ-1'].append(dict(kind='closing repeat', layer=r['layer'], at=at(V[0])))
        rng = range(n) if r['closed'] else range(1, n - 1)
        Bv = r.get('B') or [0.0] * n
        for i in rng:
            if abs(Bv[i - 1]) > 1e-9 or abs(Bv[i % len(Bv)]) > 1e-9: continue      # an end of an arc is a true point
            a, b, c = V[i - 1], V[i], V[(i + 1) % n]
            if mm(a, b) < 1.0 and not (r['closed'] and i == 0 and n > 2 and mm(V[0], V[-1]) < 1.0):
                c1['repeat < 1 mm'] += 1; places['ПЗ-1'].append(dict(kind='repeat', layer=r['layer'], at=at(b))); continue
            L = math.dist(a, c)
            dev = (abs((c[0] - a[0]) * (a[1] - b[1]) - (a[0] - b[0]) * (c[1] - a[1])) / L * K) if L > 1e-12 else mm(a, b)
            if dev < 0.5 and mm(a, b) >= 1.0 and mm(b, c) >= 1.0:
                c1['point on a straight line'] += 1; places['ПЗ-1'].append(dict(kind='straight', layer=r['layer'], at=at(b)))
    res['ПЗ-1 лишние точки'] = dict(c1)
    # ---------------------------------------------------------------- ПЗ-2, ПЗ-3
    c2 = collections.Counter(); c3 = collections.Counter()
    def ang(a, b): return math.atan2(b[1] - a[1], b[0] - a[0])
    for ri, r in enumerate(R):
        if r['key'] not in WALLK or not r['closed'] or r['et'] not in ('LWPOLYLINE', 'HATCH'): continue
        V = r['V']; n = len(V)
        if n < 4: continue
        E = [(V[k], V[(k + 1) % n]) for k in range(n)]
        Lm = [mm(*e) for e in E]
        for k in range(n):
            # kink between two long edges
            a, b = E[k - 1], E[k]
            if Lm[k - 1] >= 100 and Lm[k] >= 100:
                t = abs(math.degrees((ang(*b) - ang(*a) + math.pi) % (2 * math.pi) - math.pi))
                if 0.1 <= t <= 2.0:
                    c2['kink 0.1–2°'] += 1; places['ПЗ-2'].append(dict(kind='kink', layer=r['layer'], at=at(b[0]), deg=round(t, 2), _sig=(r['key'], len(V), round(V[0][0], 2), round(V[0][1], 2)), _ri=ri, _th=ang(*a)))
            # step: long edge, 1–2 short edges, long edge of the same direction
            if Lm[k] >= 100:
                for m_ in (2, 3):
                    j = (k + m_) % n
                    if Lm[j] < 100 or any(Lm[(k + q) % n] >= 60 for q in range(1, m_)): continue
                    a1, a2 = ang(*E[k]), ang(*E[j])
                    d = abs(math.degrees((a2 - a1 + math.pi) % (2 * math.pi) - math.pi))
                    if d > 2.0: continue
                    p, q = E[k]; u = ((q[0] - p[0]), (q[1] - p[1])); L = math.hypot(*u)
                    off = abs(((E[j][0][0] - p[0]) * u[1] - (E[j][0][1] - p[1]) * u[0]) / L) * K
                    if 0.5 <= off <= 30:
                        c2['step 0.5–30 mm'] += 1; places['ПЗ-2'].append(dict(kind='step', layer=r['layer'], at=at(q), mm=round(off, 1), _sig=(r['key'], len(V), round(V[0][0], 2), round(V[0][1], 2)), _ri=ri, _th=a1))
                    break
        if r['et'] == 'LWPOLYLINE' and n > 4 and r['key'] in ('gkl', 'blk', 'wall_ext', 'cap', 'column', 'lpart', 'glass'):
            try:
                g = Polygon(V)
                if g.is_valid and g.area > 0:
                    m = g.minimum_rotated_rectangle
                    if g.exterior.hausdorff_distance(m.exterior) * K <= 2.0:
                        c3[r['key']] += 1; places['ПЗ-3'].append(dict(layer=r['layer'], at=at(g.centroid.coords[0]), points=n))
            except Exception: pass
    # a step or kink is justified only at a junction (owner: «Нужно эти изломы перепроверять на оправданность. И если неоправданно,
    # то спрямлять стену»): another element — a wall of another contour, glass, a column, a door, the facade — within JR of it.
    JR = 150.0 / K
    _JK = WALLK | {'door', 'mullion', 'coreline'}
    _jr = [r for r in R if r['key'] in _JK and len(r['V']) >= 2]
    def _g(r):
        V = r['V']
        try:
            return Polygon(V).buffer(0) if r['closed'] and len(V) >= 3 else LineString(V)
        except Exception:
            return LineString(V)
    _jg = [_g(r) for r in _jr]; _jt = shapely.STRtree(_jg)
    def _sig(r): return (r['key'], len(r['V']), round(r['V'][0][0], 2), round(r['V'][0][1], 2)) if r['V'] else (r['key'], 0)
    from shapely.geometry import Point
    c2j = collections.Counter()
    for pl_ in places['ПЗ-2']:
        pt = Point(pl_['at']); sg = pl_.pop('_sig', None); ri = pl_.pop('_ri', None); th = pl_.pop('_th', 0.0)
        own = LineString(R[ri]['V'] + [R[ri]['V'][0]]) if ri is not None else None
        # an abutting element: an edge of another contour within JR of the place, touching this contour (<= 30 mm), across the face
        # (20…160° to it) — a wall, glass, column, door or mullion that meets the wall here; an element along the face is not one
        hit = False
        for j in _jt.query(pt.buffer(JR)):
            if _sig(_jr[j]) == sg or _jg[j].distance(pt) > JR: continue
            V2 = _jr[j]['V']; E2 = list(zip(V2[:-1], V2[1:])) + ([(V2[-1], V2[0])] if _jr[j]['closed'] else [])
            for a2, b2 in E2:
                if mm(a2, b2) < 50: continue
                sg2 = LineString([a2, b2])
                if sg2.distance(pt) > JR or (own is not None and sg2.distance(own) > 30.0 / K): continue
                d = abs(math.degrees((ang(a2, b2) - th + math.pi) % math.pi))
                if 20.0 <= d <= 160.0: hit = True; break
            if hit: break
        pl_['junction'] = hit
    res['ПЗ-2 микроизломы'] = dict(c2)
    res['ПЗ-3 прямоугольник не в 4 точках'] = dict(c3)
    # ---------------------------------------------------------------- ПЗ-4
    # polygons with their holes — from the solid hatches (one hatch = outer path + hole paths); a GKL casing is a ring around its column
    import ezdxf
    from ezdxf import path as ezpath
    c4 = collections.Counter()
    HK = {'A-222---H-': 'gkl', 'A-223---H-': 'blk', 'A-21----H-': 'wall_ext', 'A-221---H-': 'cap', 'A-28----H-': 'column', 'A-22G---H-': 'glass'}
    doc4 = ezdxf.readfile(DXF)
    polys = collections.defaultdict(list)
    for e in doc4.modelspace():
        if e.dxftype() != 'HATCH' or e.dxf.layer not in HK: continue
        if e.dxf.layer != 'A-22G---H-' and not e.dxf.solid_fill: continue
        if e.dxf.layer == 'A-221---H-' and not e.dxf.solid_fill: continue
        rings = []
        for p in e.paths:
            try:
                pts = [dp.to_pt(v.x, v.y) for v in ezpath.from_hatch_boundary_path(p).flattening(2.0)]
            except Exception:
                continue
            if len(pts) >= 3: rings.append(pts)
        if not rings: continue
        try:
            g = Polygon(rings[0]).buffer(0)
            for h in rings[1:]: g = g.difference(Polygon(h).buffer(0))
            if g.area > 0: polys[HK[e.dxf.layer]].append(g)
        except Exception: pass
    allp = [(k, g) for k, gs in polys.items() for g in gs]
    tree = shapely.STRtree([g for k, g in allp])
    for i, (k, g) in enumerate(allp):
        for j in tree.query(g):
            if j <= i: continue
            k2, g2 = allp[j]
            if k2 == k: continue
            try: a = g.intersection(g2).area * K * K / 1e6
            except Exception: continue
            if a > 0.001:
                c4[f'{k} × {k2}'] += 1; places['ПЗ-4'].append(dict(kind='overlap', classes=[k, k2], at=at(g.intersection(g2).centroid.coords[0]), m2=round(a, 4)))
        if k not in ('glass', 'column') and g.buffer(-4.0 / K, join_style=2).is_empty:
            c4['sliver < 8 mm'] += 1; places['ПЗ-4'].append(dict(kind='sliver', cls=k, at=at(g.representative_point().coords[0])))
    res['ПЗ-4 одна стена — один тип'] = dict(c4)
    # ---------------------------------------------------------------- ПЗ-5
    import curves as CV
    c5 = collections.Counter()
    def circ_runs(V, closed, need=6, span=15.0):
        n = len(V); out = []
        if n < need: return out
        Q = [(x * K, y * K) for x, y in V]
        i = 0
        while i <= n - need:
            j = i + need - 1
            if j >= n: break
            a = CV._arc_ok(Q, i, j)                 # the same test as the fitter of the export (curves.py): what it takes for an arc
            if a is None or abs(math.degrees(a[3])) < span: i += 1; continue
            while j + 1 < n and CV._arc_ok(Q, i, j + 1) is not None: j += 1
            out.append((i, j)); i = j + 1
        return out
    for r in R:
        if len(r['V']) < 6: continue
        for i, j in circ_runs(r['V'], r['closed']):
            c5[r['key']] += 1; places['ПЗ-5'].append(dict(layer=r['layer'], key=r['key'], at=at(r['V'][i]), points=j - i + 1))
    res['ПЗ-5 дуга ломаной'] = dict(c5)
    # ---------------------------------------------------------------- ПЗ-6
    import ezdxf
    doc = ezdxf.readfile(DXF)
    c6 = collections.Counter()
    def walk(ents, lay, depth=0):
        for e in ents:
            if e.dxftype() == 'INSERT' and depth < 3: yield from walk(e.virtual_entities(), lay or e.dxf.layer, depth + 1)
            else: yield (lay or e.dxf.layer, e)
    for lay, e in walk(doc.modelspace(), None):
        if not lay.startswith('A-32'): continue
        if e.dxftype() == 'ARC':
            c6['door arcs'] += 1
            if (e.dxf.get('linetype', 'BYLAYER') or '').upper() != 'DOOR-SWING':
                c6['door arc not dashed'] += 1
        elif e.dxftype() == 'LWPOLYLINE' and len(e) >= 6:
            pts = [(p[0], p[1]) for p in e.get_points('xy')]
            if CV.single_arc(pts) is not None: c6['door arc as a polyline'] += 1
    res['ПЗ-6 дуга двери пунктиром'] = dict(c6)
    # ---------------------------------------------------------------- ПЗ-7
    c7 = collections.Counter()
    MASS = {'desk', 'table', 'mtable', 'dtable', 'ctable', 'storage', 'pedestal', 'counter', 'kitchen', 'sofa', 'mfp', 'equip', 'booth'}
    for r in R:
        if r['key'] not in MASS or not r['closed'] or r['et'] != 'LWPOLYLINE': continue
        V = r['V']; n = len(V)
        if n < 4: continue
        E = [(V[k], V[(k + 1) % n]) for k in range(n)]; Lm = [mm(*e) for e in E]
        for k in range(n):
            if Lm[k] < 15 and Lm[k - 1] >= 15 and Lm[(k + 1) % n] >= 15:
                c7['edge < 15 mm'] += 1; places['ПЗ-7'].append(dict(kind='short edge', key=r['key'], at=at(E[k][0]))); break
        for k in range(n):
            if Lm[k - 1] < 50 or Lm[k] < 50: continue
            t = abs(math.degrees((ang(*E[k]) - ang(*E[k - 1]) + math.pi) % (2 * math.pi) - math.pi))
            dv = min(abs(t - 90), abs(t - 0), abs(t - 180))
            if 1.0 <= dv <= 10.0 and abs(t - 90) < 45:
                c7['corner off 90° by 1–10°'] += 1; places['ПЗ-7'].append(dict(kind='skewed corner', key=r['key'], at=at(E[k][0]), deg=round(t, 1))); break
    res['ПЗ-7 массивная мебель'] = dict(c7)
    # ---------------------------------------------------------------- ПЗ-8 rooms (З-14.2, З-15)
    # a room — a closed polygon on the layer A-921 along the inner faces of the walls: valid, not on a wall or glass deeper than
    # 30 mm (overlap > 0.001 m²), not on another room; the sample of the owner (З-15, «образцовая комната») — 4 points
    c8 = collections.Counter(); c9 = collections.Counter()
    ZDXF = zones_dxf                                    # code 012: the zones DXF of the floor (<OUT>_zones.dxf) - the caller's argument
    zdoc = ezdxf.readfile(ZDXF) if ZDXF and os.path.exists(ZDXF) else doc4          # the zones — a DXF of their own next to the plan's
    res['зоны — файл'] = os.path.basename(ZDXF) if ZDXF and os.path.exists(ZDXF) else 'в DXF плана'
    def zone_polys(layer_prefix):
        """[(polygon with holes from the zone's hatch, points of its outer outline, XDATA of the outline)] — the outline (E) and the
        fill (H) of one zone are matched by the outer ring"""
        outl = []
        for e in zdoc.modelspace():
            if e.dxftype() != 'LWPOLYLINE' or not e.dxf.layer.startswith(layer_prefix) or not e.closed: continue
            xd = {}
            try:
                for code, v in e.get_xdata('UNSPOT'):
                    if isinstance(v, str) and '=' in v: k_, v_ = v.split('=', 1); xd[k_] = v_
            except Exception: pass
            if xd.get('ring', 'outer') != 'outer': continue
            V = [dp.to_pt(v.x, v.y) for v in ezpath.make_path(e).flattening(2.0)]
            try: g0 = Polygon(V).buffer(0)
            except Exception: g0 = None
            outl.append((g0, len(e), xd))
        hat = []
        for e in zdoc.modelspace():
            if e.dxftype() != 'HATCH' or not e.dxf.layer.startswith(layer_prefix): continue
            rings = []
            for p_ in e.paths:
                try: rings.append([dp.to_pt(v.x, v.y) for v in ezpath.from_hatch_boundary_path(p_).flattening(2.0)])
                except Exception: pass
            rings = [r_ for r_ in rings if len(r_) >= 3]
            if not rings: continue
            try:
                o_ = Polygon(rings[0]).buffer(0); g = o_
                for h_ in rings[1:]: g = g.difference(Polygon(h_).buffer(0))
                hat.append((o_, g))
            except Exception: pass
        out = []
        th = shapely.STRtree([o_ for o_, g in hat]) if hat else None
        for g0, nv, xd in outl:
            g = g0
            if g0 is not None and th is not None:
                # the fill of this outline: its outer ring is the outline (symmetric difference under 1 %)
                c_ = [hat[j] for j in th.query(g0) if hat[j][0].symmetric_difference(g0).area <= 0.01 * g0.area + 0.05]
                if c_: g = min(c_, key=lambda q: q[0].symmetric_difference(g0).area)[1]
            out.append((g, nv, xd, None))
        return out
    RM = zone_polys('A-921'); PS = zone_polys('A-922')
    WALLU = unary_union([g for k, gs in polys.items() for g in gs])
    WALLU_IN = WALLU.buffer(-30.0 / K, join_style=2)
    rp = []
    for g, nv, xd, e in RM:
        c8['rooms'] += 1
        if g is None or not g.is_valid or g.area <= 0: c8['invalid'] += 1; continue
        rp.append(g)
        ov = g.intersection(WALLU_IN).area * K * K / 1e6              # deeper than 30 mm into a wall (a face that steps less is one line)
        if ov > 0.001: c8['on a wall'] += 1; places['ПЗ-8'].append(dict(kind='room on a wall', at=at(g.representative_point().coords[0]), m2=round(ov, 4)))
        if nv > 12: c8['more than 12 points'] += 1; places['ПЗ-8'].append(dict(kind='room of many points', at=at(g.representative_point().coords[0]), points=nv))
        if sample and sample.get('name') and sample['name'] in xd.get('name', ''):       # code 012: the owner's sample room - cfg.OCG_ROOM_SAMPLE
            res['ПЗ-8 образец помещения (точек)'] = nv
            res['ПЗ-8 образец помещения — имя'] = sample['name']; res['ПЗ-8 образец помещения — ждём точек'] = sample.get('points')
            if sample.get('points') is not None and nv != sample['points']: c8['sample room: points not as expected'] += 1
    trp = shapely.STRtree(rp) if rp else None
    for i, g in enumerate(rp):
        for j in trp.query(g):
            if j <= i: continue
            a = g.intersection(rp[j]).area * K * K / 1e6
            if a > 0.001: c8['rooms overlap'] += 1; places['ПЗ-8'].append(dict(kind='rooms overlap', at=at(g.intersection(rp[j]).representative_point().coords[0]), m2=round(a, 4)))
    res['ПЗ-8 помещения'] = dict(c8)
    # ---------------------------------------------------------------- ПЗ-9 passages (З-14.3, З-16…З-23)
    # a passage — a closed polygon on the layer A-922: not on walls, not on desks and chairs of workplaces and furniture (≤ 1 % of its
    # area), not narrower than W anywhere (the area its opening by W/2 loses ≤ 1 %), no teeth: corners sharper than 60° and
    # edges shorter than 300 mm between longer ones (the owner: «без зубцов по каждому креслу»)
    WPX = float(width_mm) / K if width_mm else None      # code 012: the width of a passage - cfg.OCG_PASSAGE_W_MM (or the run's passage.json); none - not checked
    res['ПЗ-9 ширина прохода, мм'] = float(width_mm) if width_mm else None
    FURNK = {'desk', 'chair', 'armchair', 'sofa', 'round', 'rtable', 'mtable', 'dtable', 'ctable', 'storage', 'pedestal', 'kitchen',
             'table', 'booth', 'counter', 'plant', 'mfp'}
    fur = []
    for r in R:
        if r['key'] in FURNK and r['closed'] and len(r['D']) >= 4:
            try:
                q = Polygon(r['D']).buffer(0)
                if q.area > 0: fur.append(q)
            except Exception: pass
    FU = unary_union(fur) if fur else Polygon()
    for g, nv, xd, e in PS:
        c9['passages'] += 1
        if g is None or not g.is_valid or g.area <= 0: c9['invalid'] += 1; continue
        A = g.area; pt0 = at(g.representative_point().coords[0])
        a_w = g.intersection(WALLU_IN).area / A
        if a_w > 0.001: c9['on walls'] += 1; places['ПЗ-9'].append(dict(kind='passage on walls', at=pt0, share=round(a_w, 4)))
        a_f = g.intersection(FU).area / A
        if a_f > 0.01: c9['on furniture > 1 %'] += 1; places['ПЗ-9'].append(dict(kind='passage on furniture', at=pt0, share=round(a_f, 4)))
        if WPX is None: c9['width not set'] += 1
        elif xd.get('kind') != 'corridor':                    # a corridor room is a passage as a whole, whatever its width
            op = g.buffer(-WPX / 2, join_style=2, mitre_limit=5.0).buffer(WPX / 2, join_style=2, mitre_limit=5.0)
            a_n = (A - op.intersection(g).area) / A
            if a_n > 0.01: c9['narrower than W > 1 %'] += 1; places['ПЗ-9'].append(dict(kind='narrow part', at=pt0, share=round(a_n, 4)))
        else: c9['corridors'] += 1
        for ring in [g.exterior] + list(g.interiors):
            V = list(ring.coords)[:-1]; n = len(V)
            for k in range(n):
                a_, b_, c_ = V[k - 1], V[k], V[(k + 1) % n]
                t = dp.turn_deg(a_, b_, c_)
                if t is not None and abs(t) > 120:
                    c9['sharp corner < 60°'] += 1; places['ПЗ-9'].append(dict(kind='tooth: sharp corner', at=at(b_), deg=round(180 - abs(t), 1)))
                if mm(b_, c_) < 300 and mm(a_, b_) >= 300 and mm(c_, V[(k + 2) % n]) >= 300:
                    c9['edge < 300 mm'] += 1; places['ПЗ-9'].append(dict(kind='tooth: short edge', at=at(b_), mm=round(mm(b_, c_))))
        c9['points'] += nv
    res['ПЗ-9 проходы'] = dict(c9)
    # ---------------------------------------------------------------- totals
    res['всего точек'] = sum(len(r['V']) for r in R)
    gp = collections.Counter()
    for r in R: gp[str(r.get('group') or '-')] += len(r['V'])
    res['точек по группам'] = dict(sorted(gp.items()))
    # unique places: the outline (E) and the fills (H) of one contour are one place; a check holds when its count is 0
    def _base(l): return l[:-2] if l.endswith(('-E-', '-H-')) else l
    uniq = collections.OrderedDict()
    for chk, lst in places.items():
        seen = set(); out = collections.Counter()
        for p_ in lst:
            kd = p_.get('kind', p_.get('key', ''))
            if chk == 'ПЗ-2': kd += ' у стыка' if p_.get('junction') else ' без стыка'
            key_ = (kd, _base(p_.get('layer', '')), round(p_['at'][0]), round(p_['at'][1]))
            if key_ in seen: continue
            seen.add(key_); out[kd] += 1
        uniq[chk] = dict(out)
    res['уникальные места'] = uniq
    # code 012 (#90 О-1): the objects each check works on - a check with none of them is «—», not 0
    res['база'] = dict(contours=len(R), walls=sum(1 for r in R if r['key'] in WALLK), door_arcs=c6.get('door arcs', 0),
                       massive=sum(1 for r in R if r['key'] in MASS and r['closed']), rooms=c8.get('rooms', 0), passages=c9.get('passages', 0))
    return dict(dxf=DXF, checks=res, places=places)


if __name__ == '__main__':
    # usage: python3 qa_remarks.py <dxf> <out.json> [zones.dxf] - in the floor folder (cfg.py: MM_PER_PT, ORIGIN_PT, OCG_ROOM_SAMPLE,
    #   OCG_PASSAGE_W_MM); ZONES_DXF in the environment as in v010
    dp.frame_from_sheet(); import sheet
    _z = sys.argv[3] if len(sys.argv) > 3 else os.environ.get('ZONES_DXF')
    out = check(sys.argv[1], _z, getattr(sheet.cfg, 'OCG_ROOM_SAMPLE', None), getattr(sheet.cfg, 'OCG_PASSAGE_W_MM', None))
    json.dump(out, open(sys.argv[2], 'w'), ensure_ascii=False, indent=1)
    for k, v in out['checks'].items(): print(k, v)
