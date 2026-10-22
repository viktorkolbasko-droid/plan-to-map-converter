"""Door openings on the wall graph (map/rules/60 §1 'Дверной проём', map/rules/60 §2.1-§2.3).

On CAD furniture plans the wall lines usually run through the doorway, so 'a gap in the wall ink' finds
nothing. A door is found by its drawing: a leaf starting at the wall, perpendicular to it, plus a quarter
arc back to the wall, with an empty swing sector. The detector misses doors whose leaf is drawn at an angle,
double doors of halls and lift doors (no leaf at all). Therefore the rule is not 'run the detector', but:

  1. detector on every edge;
  2. CHECK: every closed room (except shafts) has >= 1 door; lifts get a door on the lobby side (map/rules/60 §2.2);
  3. every failure is looked at on a crop and closed by a manual door or explained in the report.
"""
import math
import numpy as np
from shapely.geometry import LineString, Point
from shapely.ops import substring


def find_doors(gray_at, L, step=1.0, thr=236, rmin=8.0, rmax=26.0, arc_min=0.7, facade=None, facade_gap=7.0):
    """gray_at(P: (n,2) array in the working frame) -> gray values. Lengths in working-frame px.
    rmin..rmax = leaf length range (0.5-1.5 m at 16.8 px/m). Returns [dict(a0, a1, R, score)]."""
    n = max(2, int(L.length / step) + 1); ds = np.linspace(0, L.length, n)
    pts = np.array([L.interpolate(d).coords[0] for d in ds])
    tg = np.gradient(pts, axis=0); tg /= np.linalg.norm(tg, axis=1)[:, None] + 1e-9
    nm = np.c_[-tg[:, 1], tg[:, 0]]
    ts = np.arange(1.5, rmax + 3, 0.5)
    sample = lambda P: gray_at(P.reshape(-1, 2)).reshape(P.shape[:-1])
    cands = []
    for side in (1, -1):
        P = pts[:, None, :] + side * nm[:, None, :] * ts[None, :, None]
        vals = np.minimum.reduce([sample(P + tg[:, None, :] * o) for o in (-1.0, 0.0, 1.0)])
        ink = vals < thr
        for i in range(n):
            row = ink[i]
            if not row[:3].any():                       # the leaf starts at the wall
                continue
            k = 0
            while k < len(row) and (row[k] or (k + 1 < len(row) and row[k + 1])):
                k += 1
            Lf = ts[min(k, len(ts) - 1)]
            if not (rmin <= Lf <= rmax):
                continue
            for dirn in (1, -1):
                u = dirn * tg[i]; nn = side * nm[i]
                hits = tot = 0
                for a in np.arange(10, 81, 5):          # the arc from the leaf tip back to the wall
                    t = math.radians(a); d = u * math.cos(t) + nn * math.sin(t)
                    rs = np.arange(Lf - 2.0, Lf + 2.01, 0.5)
                    v = sample(pts[i][None, :] + rs[:, None] * d[None, :])
                    tot += 1; hits += int(v.min() < thr)
                sc = hits / tot
                if sc < arc_min:
                    continue
                emp = tot2 = 0                          # the swing sector must be empty
                for a in np.arange(20, 71, 10):
                    t = math.radians(a); d = u * math.cos(t) + nn * math.sin(t)
                    rs = np.arange(3.0, Lf - 3.0, 1.0)
                    if len(rs) == 0:
                        continue
                    v = sample(pts[i][None, :] + rs[:, None] * d[None, :])
                    tot2 += len(rs); emp += int((v < thr).sum())
                if tot2 and emp / tot2 > 0.12:
                    continue
                far = pts[i] + nn * Lf * 0.7 + u * Lf * 0.7
                if facade is not None and (facade.distance(Point(*pts[i])) < facade_gap or facade.distance(Point(*far)) < facade_gap):
                    continue                            # columns and mullions at the facade are not doors
                cands.append(dict(s=ds[i], R=Lf, dir=dirn, score=sc))
    cands.sort(key=lambda c: (-c['score'], -c['R'])); keep = []
    for c in cands:                                     # non-maximum suppression along the wall
        a0, a1 = sorted([c['s'], c['s'] + c['dir'] * c['R']])
        if any(min(a1, k['a1']) - max(a0, k['a0']) > 0.3 * (a1 - a0) for k in keep):
            continue
        c['a0'], c['a1'] = max(0.0, a0), min(L.length, a1); keep.append(c)
    return keep


def snap_manual(edges, point, width, max_dist=3.0):
    """a manual door: centred at the projection of `point` on the nearest edge, `width` long, clipped to the edge.
    Returns (edge index, door segment) or None when no wall is near (then the point is wrong - look again)."""
    p = Point(*point)
    ei, L = min(enumerate(edges), key=lambda t: t[1].distance(p))
    if L.distance(p) > max_dist:
        return None
    s0 = L.project(p)
    return ei, substring(L, max(0.0, s0 - width / 2), min(L.length, s0 + width / 2))


def rooms_without_doors(rooms, door_segments, skip_types=('lift',), min_area=0.0, tol=0.8):
    """closed rooms whose outline touches no door (map/rules/80 §9: every room behind a door is reachable)"""
    D = [d.buffer(tol) for d in door_segments]
    out = []
    for r in rooms:
        if r['type'] in skip_types or r['poly'].area < min_area:
            continue
        if not any(r['poly'].exterior.intersects(d) for d in D):
            out.append(r)
    return out
