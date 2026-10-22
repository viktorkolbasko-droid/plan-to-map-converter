"""Walls as ONE planar graph of axes; rooms are its faces (map/rules/40 §2.3, map/rules/70 §2.1-§2.2).

Why: v1 drew every room outline on its own. Neighbours then disagree by 1-3 px and the plan gets doubled
walls (length ratio 1.75 against 1.22 in v2) and short edges (12 against 0). With a single graph a shared
wall exists once, both rooms use the same coordinates and the SVG stroke is centred on one axis.

Pieces:
  * extend_trim   - a partition that stops short of (or runs past) its neighbour is snapped to it;
  * faces         - polygonize walls + virtual lines, subtract faces covered by bigger faces;
  * virtual lines - open boundaries between zones (corridor mouth, dashed CAD zone line): they split faces
                    but are never drawn; a room bounded by a virtual line is an open zone (fill only);
  * free walls    - graph edges with no closed room on either side (partition inside an open space).
"""
import numpy as np
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union, polygonize


def extend_trim(L, others, maxext=26.0, overshoot=0.3):
    """extend both ends along the line to the nearest crossing (up to maxext) and cut what runs past
    the outermost crossings. A line with fewer than 2 crossings is returned unchanged."""
    c = np.array(L.coords, float); p, q = c[0], c[-1]; d = q - p; Ln = np.hypot(*d); u = d / Ln
    ext = LineString([tuple(p - u * maxext), tuple(q + u * maxext)])
    ts = []
    for O in others:
        if O is L or O.is_empty:
            continue
        X = ext.intersection(O)
        pts = [X] if X.geom_type == 'Point' else [g for g in getattr(X, 'geoms', []) if g.geom_type == 'Point']
        ts += [(np.array(pt.coords[0]) - p) @ u for pt in pts]
    if len(ts) < 2:
        return L
    ts = np.array(ts)
    lo = ts[(ts >= -maxext) & (ts <= Ln * 0.5)]; hi = ts[(ts >= Ln * 0.5) & (ts <= Ln + maxext)]
    a = lo[np.argmin(np.abs(lo))] if len(lo) else 0.0
    b = hi[np.argmin(np.abs(hi - Ln))] if len(hi) else Ln
    return LineString([tuple(p + u * (a - overshoot)), tuple(p + u * (b + overshoot))])


def snap_all(lines, fixed=(), maxext=26.0, rounds=2):
    """lines: dict name -> LineString (straight partitions); fixed: lines that are never moved (facade, arcs)"""
    out = dict(lines)
    for _ in range(rounds):
        for k in list(out):
            out[k] = extend_trim(out[k], [out[j] for j in out if j != k] + list(fixed), maxext)
    return out


def dedupe_polyline(P, min_step=0.8):
    """drop interior vertices closer than min_step to the kept predecessor (joins of arcs and straights
    produced 0.4 px edges in v2 before this)"""
    P = np.asarray(P, float); keep = [0]
    for i in range(1, len(P) - 1):
        if np.hypot(*(P[i] - P[keep[-1]])) >= min_step:
            keep.append(i)
    keep.append(len(P) - 1)
    return P[keep]


def faces(walls, virtual, clip, min_area=2.0):
    """faces of walls + virtual lines inside `clip` (the building polygon, slightly buffered).
    Faces covered by a larger face are subtracted from it (polygonize returns faces without holes)."""
    geoms = [g.intersection(clip) for g in list(walls) + list(virtual) if not g.is_empty]
    F = [p for p in polygonize(unary_union([g for g in geoms if not g.is_empty])) if p.area >= min_area]
    F = sorted(F, key=lambda p: -p.area); out = []
    for i, P in enumerate(F):
        inner = [Q for Q in F[i + 1:] if P.buffer(0.05).contains(Q)]
        if inner:
            P = P.difference(unary_union(inner).buffer(0.01))
            if P.geom_type != 'Polygon':
                P = max(P.geoms, key=lambda q: q.area)
        out.append(P)
    return out


def label_test(face_list, labels):
    """every client label in its own face; returns {face index or None: [labels]} for violations.
    Two labels in one face = a missing wall; a label in no face = a hole in the graph."""
    where = {}
    for t, x, y in labels:
        idx = [i for i, P in enumerate(face_list) if P.contains(Point(x, y))]
        where.setdefault(min(idx, key=lambda i: face_list[i].area) if idx else None, []).append(t)
    return {k: v for k, v in where.items() if k is None or len(v) > 1}


def node_edges(lines):
    """split the union of wall lines at every crossing -> list of edge LineStrings"""
    U = unary_union([l for l in lines if not l.is_empty])
    return [g for g in (U.geoms if hasattr(U, 'geoms') else [U]) if g.geom_type == 'LineString']


def sides(edge, rooms, off=1.6):
    """rooms on both sides of an edge (sampled at its middle); rooms: list of dict(poly=...)"""
    m = np.array(edge.interpolate(0.5, normalized=True).coords[0])
    a = np.array(edge.interpolate(max(0, edge.length * 0.5 - 0.5)).coords[0])
    b = np.array(edge.interpolate(min(edge.length, edge.length * 0.5 + 0.5)).coords[0])
    u = (b - a) / max(np.linalg.norm(b - a), 1e-9); n = np.array([-u[1], u[0]])
    res = []
    for sgn in (1, -1):
        p = Point(*(m + sgn * n * off))
        res.append(next((r for r in rooms if r['poly'].contains(p)), None))
    return res


def free_walls(edges, rooms, closed_types):
    """edges that bound no closed room: drawn as separate wall paths (map/rules/70 §1)"""
    out = []
    for L in edges:
        sa, sb = sides(L, rooms)
        if not any(r is not None and r['type'] in closed_types for r in (sa, sb)):
            out.append(L)
    return out


def open_if_virtual(rooms, virtual, tol=0.3):
    """a room with a virtual edge is an open zone: its outline must not be stroked (the stroke would draw
    a wall where the source has none - the SW corridor mouth of floor 14 in v2 before the fix)"""
    V = unary_union([v for v in virtual if not v.is_empty]) if virtual else None
    if V is None:
        return []
    changed = []
    for r in rooms:
        if r['type'] in ('corridor', 'open'):
            continue
        if r['poly'].exterior.intersection(V.buffer(tol)).length > 1.0:
            changed.append(r)
    return changed
