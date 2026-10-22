"""Curves in the DXF (owner 09.10.2026, remark З-6; ЛТ-4): «Пример: круглые колонны, дугообразные части помещений, круглые
столы. Если ты умеешь строить кривые, то давай попытаемся описывать эти объекты кривой, особенно там, где круг, а не пытаться
обвести её множеством точек.»

The source draws a circle or an arc with Bézier curves; the extraction flattens them into many points. Here a run of points that
lies on one circle (within TOL_ABS or TOL_REL of the radius, turning one way, at least MIN_PTS points, at least MIN_SPAN degrees)
becomes one arc: a bulge of the DXF polyline (LWPOLYLINE, HATCH boundary) — two vertices instead of dozens; a closed contour that is
one circle becomes a CIRCLE (or two half-circle bulges in a hatch boundary). Coordinates — mm of the DXF (y up).
fit(points, closed) -> list of (x, y, bulge); bulge of a vertex is the arc to the next vertex (0 — a straight segment)."""
import math
import numpy as np
TOL_ABS = 1.5            # mm: a point is on the circle when this close …
TOL_REL = float(__import__('os').environ.get('CV_TOL_REL', 0.004))   # … or within 0.4 % of the radius (a Bézier quarter circle is within 0.03 %), RES_CAP at most; v010: without the cap 0.4 % let a room
                         # outline of long straight walls with steps of 0.1 m pass for an arc of 36 m (22 m² of error)
import os as _os
CHORD_RATIO = float(_os.environ.get('CV_RATIO', 4.0))        # the chords of one arc are alike (a flattened curve); straight walls of any lengths are not an arc
SAG_CAP = float(_os.environ.get('CV_SAG_CAP', 25.0))   # a chord's sagitta to its arc ≤ 25 mm
RES_CAP = float(_os.environ.get('CV_RES_CAP', 15.0))   # the vertex residual of a big circle ≤ 15 mm
MIN_PTS = 4              # at least 4 points (3 chords) make an arc
MIN_SPAN = 8.0           # deg
MAX_CHORD = 25.0         # deg: a chord turns less than this around the centre (an octagon is not a circle)
MIN_SAGITTA = 1.0        # mm: an "arc" flatter than this is a straight line


def circle(P):
    """algebraic (Kåsa) fit: centre, radius, max |distance - r|"""
    A = np.asarray(P, float)
    x, y = A[:, 0], A[:, 1]
    M = np.column_stack([x, y, np.ones(len(A))]); b = x * x + y * y
    try:
        c, *_ = np.linalg.lstsq(M, b, rcond=None)
    except Exception:
        return None
    cx, cy = c[0] / 2, c[1] / 2; r2 = c[2] + cx * cx + cy * cy
    if r2 <= 0: return None
    r = math.sqrt(r2); res = float(np.max(np.abs(np.hypot(x - cx, y - cy) - r)))
    return cx, cy, r, res


def _ang(c, p): return math.atan2(p[1] - c[1], p[0] - c[0])


def _span(c, P):
    """signed angle swept from P[0] to P[-1] around c, chord by chord; None if the turning changes direction or a chord is big"""
    tot = 0.0; sgn = 0
    for a, b in zip(P[:-1], P[1:]):
        d = (_ang(c, b) - _ang(c, a) + math.pi) % (2 * math.pi) - math.pi
        if abs(math.degrees(d)) > MAX_CHORD or abs(d) < 1e-12: return None
        s = 1 if d > 0 else -1
        if sgn and s != sgn: return None
        sgn = s; tot += d
    return tot


def _arc_ok(P, i, j):
    q = P[i:j + 1]
    ch = [math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(q[:-1], q[1:])]
    if len(ch) >= 3 and max(ch[1:-1] or ch) > CHORD_RATIO * max(min(ch[1:-1] or ch), 1e-9): return None
    f = circle(q)
    if f is None: return None
    cx, cy, r, res = f
    if res > max(TOL_ABS, min(TOL_REL * r, RES_CAP)): return None
    # each chord of a flattened curve stays close to its arc: a chord's sagitta ≤ SAG_CAP — straight walls of metres with vertices
    # on a big circle are not an arc (v010: a room outline, chords of 5–12 m on r = 37–57 m, sagittas 0.1–0.5 m)
    smax = SAG_CAP
    for a, b in zip(q[:-1], q[1:]):
        L2 = (math.hypot(b[0] - a[0], b[1] - a[1]) / 2) ** 2
        if L2 >= r * r or r - math.sqrt(r * r - L2) > smax: return None
    sp = _span((cx, cy), q)
    if sp is None: return None
    sag = r * (1 - math.cos(min(abs(sp), math.pi) / 2))
    if sag < MIN_SAGITTA: return None
    return cx, cy, r, sp


def fit(P, closed=False):
    """points (mm, no closing repeat for closed) -> [(x, y, bulge)]; a full circle -> [('circle', cx, cy, r)]"""
    n = len(P)
    if n < MIN_PTS: return [(p[0], p[1], 0.0) for p in P]
    if closed and n >= 8:
        f = circle(P)
        if f is not None:
            cx, cy, r, res = f
            sp = _span((cx, cy), list(P) + [P[0]])
            if res <= max(TOL_ABS, TOL_REL * r) and sp is not None and abs(abs(sp) - 2 * math.pi) < 0.01:
                return [('circle', cx, cy, r)]
    Q = list(P)
    if closed:
        # start at the sharpest corner, so that no arc is cut by the start of the ring
        def tn(k):
            a, b, c = Q[k - 1], Q[k], Q[(k + 1) % n]
            u = (b[0] - a[0], b[1] - a[1]); v = (c[0] - b[0], c[1] - b[1])
            return abs(math.atan2(u[0] * v[1] - u[1] * v[0], u[0] * v[0] + u[1] * v[1]))
        k0 = max(range(n), key=tn)
        Q = Q[k0:] + Q[:k0] + [Q[k0]]
    m = len(Q); out = []; i = 0
    while i < m - 1:
        best = None; j = i + MIN_PTS - 1
        while j < m:
            a = _arc_ok(Q, i, j)
            if a is None: break
            best = (j, a); j += 1
        if best is not None and abs(math.degrees(best[1][3])) >= MIN_SPAN:
            j, (cx, cy, r, sp) = best
            out.append((Q[i][0], Q[i][1], math.tan(sp / 4))); i = j
        else:
            out.append((Q[i][0], Q[i][1], 0.0)); i += 1
    if not closed: out.append((Q[-1][0], Q[-1][1], 0.0))
    return out


def single_arc(P):
    """an open run that is one arc: (centre, radius, start angle, end angle in deg, counter-clockwise) or None"""
    if len(P) < MIN_PTS: return None
    a = _arc_ok(list(P), 0, len(P) - 1)
    if a is None or abs(math.degrees(a[3])) < MIN_SPAN: return None
    cx, cy, r, sp = a
    s = math.degrees(_ang((cx, cy), P[0])); e = math.degrees(_ang((cx, cy), P[-1]))
    return (cx, cy), r, (s if sp > 0 else e), (e if sp > 0 else s)
