"""Vertices and edges of every contour of an engineering-plan DXF (owner 09.10.2026: points of graphs and polygons on the SVG and
on the layer sheets, to see extra points on straight lines). Reads the DXF as delivered: INSERTs are expanded with their transform,
HATCH boundaries and LWPOLYLINE/LINE/SOLID give the true vertices; arcs are flattened only for drawing, never counted as vertices.
Coordinates are returned in sheet pt (x right, y down) through the export transform of e8_export.py.
Code 012 (ocg/, ОЧ-47): ported from the v010 package (tools/dxf_pts.py) without the sheet in the code: the scale (mm/pt) and the
origin of the export come from the floor's cfg (MM_PER_PT, ORIGIN_PT through ocg/sheet.py) - set_frame() or frame_from_sheet()
before load(); without them load() stops (no default sheet)."""
import re, math, collections
import ezdxf
from ezdxf import path as ezpath
K = None; OX = OY = None
def set_frame(k, ox, oy):
    """the export transform of the sheet: mm per pt and the origin in pt (cfg.MM_PER_PT, cfg.ORIGIN_PT)"""
    global K, OX, OY
    if not k or float(k) <= 0: raise SystemExit('dxf_pts: масштаб листа (мм/pt) не задан — cfg.MM_PER_PT')
    K, OX, OY = float(k), float(ox), float(oy)
def frame_from_sheet():
    """the transform from the floor's cfg.py in the cwd (ocg/sheet.py)"""
    import os, sys; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import sheet
    set_frame(sheet.K, sheet.OX, sheet.OY)
def to_pt(x, y):
    if K is None: raise SystemExit('dxf_pts: не задано преобразование выгрузки — set_frame(K, OX, OY) или frame_from_sheet()')
    return (OX + x / K, OY - y / K)
def kind_of(layer, ent, block_key):
    L = layer.upper()
    if block_key: return block_key
    if L.startswith('A-222'): return 'gkl'
    if L.startswith('A-223'): return 'blk'
    if L.startswith('A-221'):
        if ent.dxftype() == 'HATCH': return 'coreblock' if (ent.dxf.get('pattern_name', 'SOLID') or 'SOLID').upper() != 'SOLID' else 'cap'
        return 'coreline' if ent.dxftype() == 'LINE' else 'coreoutline'
    if L.startswith('A-21'): return 'wall_ext'
    if L.startswith('A-28'): return 'column'
    if L.startswith('A-22G'):                       # a glass band: its fill and its closed outline — one type (З-1)
        return 'glass' if ent.dxftype() == 'HATCH' or (ent.dxftype() == 'LWPOLYLINE' and ent.closed) else 'lpart'
    if L.startswith('A-31'): return 'facade'
    if L.startswith('A-921'): return 'room'
    if L.startswith('A-922'): return 'passage'
    if L.startswith('A-92'): return 'zone'
    if L.startswith('A-93'): return 'roomsep'
    if L.startswith('A-90'): return 'dim'
    if L.startswith('A-AXM'): return 'mark'
    if L.startswith('A-AX'): return 'axis'
    if L.startswith('A-00'): return 'unknown'
    return 'other:' + layer
BULGE = {}                 # id(V) -> bulge of each vertex (the arc to the next vertex), for LWPOLYLINE and hatch polyline paths
MIDS = {}                  # id(V) -> {i: the midpoint of the arc from vertex i to the next one, pt} — exact, in the entity's own OCS
def _mid(x1, y1, x2, y2, b):
    """midpoint of a bulge arc in the entity's coordinates: a positive bulge turns counter-clockwise, the arc lies right of p1->p2"""
    return ((x1 + x2) / 2 + b / 2 * (y2 - y1), (y1 + y2) / 2 - b / 2 * (x2 - x1))
def _mids(vs, closed, W):
    n = len(vs); out = {}
    for i, (x, y, b) in enumerate(vs):
        if abs(b) < 1e-9 or (i == n - 1 and not closed): continue
        x2, y2 = vs[(i + 1) % n][:2]; out[i] = W(*_mid(x, y, x2, y2, b))
    return out
def rings_of(e):
    """[(vertices_pt, draw_pt, closed)] for one (already transformed) entity; vertices = true corners only."""
    t = e.dxftype(); out = []
    if t == 'LWPOLYLINE':
        pts = list(e.get_points('xyb')); closed = bool(e.closed)
        ocs = e.ocs(); el = e.dxf.elevation                      # mirrored INSERTs give extrusion -Z: OCS != WCS
        V = [to_pt(w.x, w.y) for w in (ocs.to_wcs((x, y, el)) for x, y, _ in pts)]
        if any(abs(b) > 1e-9 for _, _, b in pts):
            D = [to_pt(v.x, v.y) for v in ezpath.make_path(e).flattening(2.0)]
        else:
            D = V + ([V[0]] if closed and V else [])
        BULGE[id(V)] = [b for _, _, b in pts]
        if any(abs(b) > 1e-9 for _, _, b in pts):
            MIDS[id(V)] = _mids(pts, closed, lambda x, y: (lambda w: to_pt(w.x, w.y))(ocs.to_wcs((x, y, el))))
        out.append((V, D, closed))
    elif t == 'LINE':
        a, b = e.dxf.start, e.dxf.end; V = [to_pt(a.x, a.y), to_pt(b.x, b.y)]; out.append((V, V, False))
    elif t in ('SOLID', 'TRACE'):
        ocs = e.ocs()
        vs = [ocs.to_wcs(v) for v in (e.dxf.vtx0, e.dxf.vtx1, e.dxf.vtx3, e.dxf.vtx2)]; V = [to_pt(v.x, v.y) for v in vs]
        V2 = [p for i, p in enumerate(V) if i == 0 or p != V[i - 1]]
        out.append((V2, V2 + [V2[0]], True))
    elif t == 'HATCH':
        ocs = e.ocs(); hz = e.dxf.elevation.z
        def W(x, y):
            w = ocs.to_wcs((x, y, hz)); return to_pt(w.x, w.y)
        for bp in e.paths:
            if bp.type == ezdxf.entities.BoundaryPathType.POLYLINE:
                vs = [(v[0], v[1], v[2] if len(v) > 2 else 0.0) for v in bp.vertices]
                V = [W(x, y) for x, y, _ in vs]
                BULGE[id(V)] = [b for _, _, b in vs]
                closed = bool(getattr(bp, 'is_closed', True)) or True
                if any(abs(b) > 1e-9 for _, _, b in vs): MIDS[id(V)] = _mids(vs, True, W)
                if any(abs(b) > 1e-9 for _, _, b in vs):
                    D = [W(v.x, v.y) for v in ezpath.from_hatch_polyline_path(bp).flattening(2.0)]
                else:
                    D = V + ([V[0]] if V else [])
                out.append((V, D, True))
            else:
                V = []; D = []
                for ed in bp.edges:
                    et = ed.type.name if hasattr(ed.type, 'name') else str(ed.type)
                    if et.upper().startswith('LINE'):
                        s = W(ed.start[0], ed.start[1]); V.append(s); D += [s, W(ed.end[0], ed.end[1])]
                    else:
                        p = ezpath.Path(); 
                        try:
                            ezpath.add_edges = None
                        except Exception: pass
                        # flatten arc / ellipse / spline edge through a one-edge path
                        sp = ed.start_point if hasattr(ed, 'start_point') else None
                        ep = ed.end_point if hasattr(ed, 'end_point') else None
                        if sp is not None: V.append(W(sp[0], sp[1]))
                        try:
                            if et.upper().startswith('ARC'):
                                a0, a1 = math.radians(ed.start_angle), math.radians(ed.end_angle)
                                if not ed.ccw: a0, a1 = -a0, -a1
                                if a1 < a0: a1 += 2 * math.pi
                                n = max(4, int((a1 - a0) / math.radians(5)))
                                for k in range(n + 1):
                                    a = a0 + (a1 - a0) * k / n
                                    D.append(W(ed.center[0] + ed.radius * math.cos(a), ed.center[1] + ed.radius * math.sin(a)))
                            elif ep is not None and sp is not None:
                                D += [W(sp[0], sp[1]), W(ep[0], ep[1])]
                        except Exception:
                            pass
                if V: out.append((V, D if D else V + [V[0]], True))
    elif t in ('ARC', 'CIRCLE', 'ELLIPSE', 'SPLINE'):
        try:
            D = [to_pt(v.x, v.y) for v in ezpath.make_path(e).flattening(2.0)]
            V = [D[0], D[-1]] if t in ('ARC', 'SPLINE') else []
            out.append((V, D, t == 'CIRCLE'))
        except Exception: pass
    return out
def xgroup(e):
    """the owner's group of an object written by the export as XDATA (UNSPOT: group=N, type=key); '' when absent"""
    try:
        for code, v in e.get_xdata('UNSPOT'):
            if isinstance(v, str) and v.startswith('group='): return v[6:]
    except Exception: pass
    return ''
def xtype(e):
    """the object type the export wrote as XDATA (UNSPOT: type=key); '' when absent"""
    try:
        for code, v in e.get_xdata('UNSPOT'):
            if isinstance(v, str) and v.startswith('type='): return v[5:]
    except Exception: pass
    return ''
def iter_entities(msp):
    """(layer, entity, block_key, obj_id, group) with INSERTs expanded recursively; the INSERT's layer, type key, id and group
    are kept."""
    def rec(ents, layer, key, oid, depth, grp):
        for e in ents:
            if e.dxftype() == 'INSERT' and depth < 4:
                k = key or re.sub(r'^B\d+_', '', e.dxf.name)
                yield from rec(e.virtual_entities(), layer or e.dxf.layer, k, oid, depth + 1, grp)
            else:
                yield (layer or e.dxf.layer, e, key, oid, grp)
    for n, e in enumerate(msp):
        if e.dxftype() == 'INSERT':
            k = re.sub(r'^B\d+_', '', e.dxf.name)
            yield from rec(e.virtual_entities(), e.dxf.layer, k, n, 1, xgroup(e))
        else:
            yield (e.dxf.layer, e, None, n, xgroup(e))
def load(dxf_path):
    doc = ezdxf.readfile(dxf_path); recs = []; texts = 0
    for layer, e, key, oid, grp in iter_entities(doc.modelspace()):
        if e.dxftype() in ('TEXT', 'MTEXT', 'ATTRIB', 'ATTDEF', 'POINT'): texts += 1; continue
        k = kind_of(layer, e, key); xt = xtype(e)
        if k == 'unknown' and xt == 'stray': k = 'stray'           # «прочее» of group 6 (З-12, owner 09.10, В2)
        for V, D, closed in rings_of(e):
            if len(D) >= 2: recs.append(dict(layer=layer, key=k, V=V, D=D, closed=closed, et=e.dxftype(), oid=oid, group=grp,
                                             ltype=(e.dxf.get('linetype', '') if e.dxf.hasattr('linetype') else ''),
                                             B=BULGE.pop(id(V), None), M=MIDS.pop(id(V), None), xt=xt))
    return recs, texts
def turn_deg(a, b, c):
    ux, uy = b[0] - a[0], b[1] - a[1]; vx, vy = c[0] - b[0], c[1] - b[1]
    lu, lv = math.hypot(ux, uy), math.hypot(vx, vy)
    if lu < 1e-9 or lv < 1e-9: return None
    cr = ux * vy - uy * vx; dt = ux * vx + uy * vy
    return math.degrees(math.atan2(cr, dt))
def straight_points(V, closed, tol_deg=0.1, dup_mm=1.0):
    """vertices that do not turn the contour (|turn| < tol_deg) and duplicates closer than dup_mm: candidates for extra points."""
    n = len(V); flags = []
    if n < 3 and not closed:
        return flags
    idx = range(n) if closed else range(1, n - 1)
    for i in idx:
        a, b, c = V[i - 1], V[i], V[(i + 1) % n]
        if math.hypot(b[0] - a[0], b[1] - a[1]) * K < dup_mm:
            flags.append((i, 'dup')); continue
        t = turn_deg(a, b, c)
        if t is not None and abs(t) < tol_deg: flags.append((i, 'straight'))
    return flags
