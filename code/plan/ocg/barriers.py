"""code 012 (СО-2; owner 09.10.2026, В1 место 3; rows 183, 189): thin strips of the wall layers with a free end and their verdict.
A strip - a wall body component that is thin (<= THIN_MM), at least MIN_LEN_MM long, >= 4 x its thickness and straight (>= 80 %
of its rotated rectangle). Its ends - the short sides of the rectangle. An end is at a wall when another wall body or a carrier
(column, glass, core, facade) lies within the touch tolerance = the strip's thickness; on a desk - a desk fill within the same
tolerance (on its outline or inside). Verdict: an end on a desk and no end at a wall - a barrier, a part of the desk (A-82),
not a wall body; one end at a wall - a wall; both ends free and no desk - a wall to review (a hanging strip, row 189).
Strips with both ends at walls are ordinary partitions and are not listed. Thresholds in mm go to pt by K (mm/pt)."""
import math
import shapely
from shapely.geometry import LineString

THIN_MM = 150.0
MIN_LEN_MM = 300.0      # a sliver of a joint is no strip
BARRIER = 'стол: барьер — часть стола (A-82), не тело стены (СО-2)'


def strip_verdicts(comps, desks, carriers, K):
    """comps - wall body polygons (pt), desks - desk fill polygons, carriers - columns, glass, core and facade geometry;
    -> [(index in comps, record)] for every strip with a free end"""
    ct = shapely.STRtree(comps) if comps else None
    dt = shapely.STRtree(desks) if desks else None
    rt = shapely.STRtree(carriers) if carriers else None
    out = []
    for ci, g in enumerate(comps):
        rr = g.minimum_rotated_rectangle
        if rr.geom_type != 'Polygon': continue
        c = list(rr.exterior.coords)[:4]; e01 = math.dist(c[0], c[1]); e12 = math.dist(c[1], c[2])
        th, ln = min(e01, e12), max(e01, e12)
        if th * K > THIN_MM or ln * K < MIN_LEN_MM or ln < 4 * th or g.area < 0.8 * rr.area: continue
        ends = [LineString([c[0], c[1]]), LineString([c[2], c[3]])] if e01 < e12 else [LineString([c[1], c[2]]), LineString([c[3], c[0]])]
        tol = th                                             # the touch tolerance = the strip's thickness

        def near(q, tree, geoms, skip=None):
            return tree is not None and any(j != skip and geoms[j].distance(q) <= tol for j in tree.query(q.buffer(tol)))
        v = [dict(wall=near(q, ct, comps, ci) or near(q, rt, carriers), desk=near(q, dt, desks)) for q in ends]
        if all(x['wall'] for x in v): continue
        if any(x['desk'] for x in v) and not any(x['wall'] for x in v): verdict = BARRIER
        elif any(x['wall'] for x in v): verdict = 'стена: один конец на стене, колонне, стекле или фасаде'
        else: verdict = 'стена, на просмотр: оба конца свободны, стола у концов нет (строка 189 — висячая)'
        m = g.centroid
        out.append((ci, dict(at_pt=[round(m.x, 2), round(m.y, 2)], size_mm=[round(ln * K), round(th * K)], tol_pt=round(tol, 3),
                             ends=['стол' if x['desk'] else ('стена' if x['wall'] else 'свободный') for x in v], verdict=verdict)))
    return out


def desk_near(g, desks, tol):
    """the desk fills within tol of a barrier (the desk it is given to)"""
    from shapely.ops import unary_union
    return unary_union([d for d in desks if d.distance(g) <= tol])
