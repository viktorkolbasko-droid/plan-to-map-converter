# manual8.py - code 008 (Т4-7): an element of a cfg.MANUAL record is a box (x0, y0, x1, y1) or a polygon -
#   dict(poly=[(x, y), ...]) or a list of >= 3 points. No dependency on cfg: tools of the floor comparison folder read it too.
def is_poly(b):
    """a MANUAL box element is a box (x0, y0, x1, y1) or a polygon: dict(poly=[(x, y), ...]) or a list of >= 3 points"""
    if isinstance(b, dict): return 'poly' in b
    return len(b) >= 3 and all(isinstance(v, (tuple, list)) and len(v) == 2 for v in b)
def poly_pts(b): return [tuple(v) for v in (b['poly'] if isinstance(b, dict) else b)]
def bbox_of(b):
    """the bbox of a MANUAL element (a box is its own bbox)"""
    if not is_poly(b): return tuple(b)
    xs = [v[0] for v in poly_pts(b)]; ys = [v[1] for v in poly_pts(b)]
    return (min(xs), min(ys), max(xs), max(ys))
_PG = {}
def poly_geom(b, pad):
    from shapely.geometry import Polygon
    from shapely.prepared import prep
    k = (tuple(poly_pts(b)), pad)
    if k not in _PG:
        g = Polygon(poly_pts(b)); g = g if g.is_valid else g.buffer(0)
        _PG[k] = prep(g.buffer(pad, join_style=2))
    return _PG[k]
def element_takes(b, prim_bb, prim_geom_fn, pad=0.6):
    """the MANUAL element takes the primitive: a box - the primitive's bbox inside the box + pad (as code 007);
    a polygon - the primitive's geometry inside the polygon grown by pad (a turned block of desks, Т4-7)"""
    if not is_poly(b):
        q = prim_bb; return q[0] >= b[0] - pad and q[2] <= b[2] + pad and q[1] >= b[1] - pad and q[3] <= b[3] + pad
    x0, y0, x1, y1 = bbox_of(b); q = prim_bb
    if not (q[0] >= x0 - pad and q[2] <= x1 + pad and q[1] >= y0 - pad and q[3] <= y1 + pad): return False
    return poly_geom(b, pad).contains(prim_geom_fn())


