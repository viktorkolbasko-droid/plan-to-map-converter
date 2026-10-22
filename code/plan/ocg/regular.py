"""Contour regularization of the engineering plan (owner 09.10.2026, remarks З-1…З-3, З-9; extra points ЛТ-1…ЛТ-3).

Owner: «Это прямая стена, и каждый из участков должен быть в 4 точках… Нужно эти изломы перепроверять на оправданность.
И если неоправданно, то спрямлять стену и упрощать полигон.»

Units — sheet pt (cfg.MM_PER_PT mm/pt). A contour is cleaned in three ways:
 1. clean_ring — the closing repeat of the first point, points closer than DUP (1 mm), points on a straight line
    (deviation < COL_DEV from the chord of the neighbours, any spike included);
 2. face lines (FaceLines) — every long edge of every wall-like contour of the sheet (walls of all classes, glass bands, core
    blocks, the source lines that bound them) is clustered into one face line when its direction differs < ANG and both of its
    ends lie closer than TOL to the line; an edge — even a short jog — whose two ends lie within TOL of a face line is put on that
    line; consecutive edges on one line merge, the corner between two lines is their intersection. A jog, step, kink or chamfer
    smaller than TOL disappears; a step of TOL or more stays (it is in the source: a change of thickness, a niche);
 3. curved runs (≥ 3 vertices turning one way by 0.3–25° at similar edges) are protected: they are arcs, kept as they are here
    and written as arcs at the export.
The face lines are shared by all contours, so walls that touch keep touching after the cleaning, and a wall that continues
another one in line ends up exactly on its line.
Code 012 (stage 2 of the merge of v010 into ocg/; the code of pass v010, route/regular.py): the scale of the sheet from cfg
(ocg/sheet.py: cfg.MM_PER_PT - v010 had K = 48.04 <one example: client-b, floor 40> in the code); every threshold here is in
mm through it (as in v010); no scale - a stop. e8_export.py calls clean_ring on mm points with dup and col_dev in mm."""
import math, collections, os, sys
import numpy as np
import shapely
from shapely.geometry import Polygon, LineString, MultiPolygon, Point
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import sheet
K = sheet.K
if not K: sys.exit('СТОП regular.py: нет масштаба листа cfg.MM_PER_PT — пороги чистки контуров в мм не перевести в pt листа (plan/rules/20 §3.8)')
MM = 1.0 / K
DUP = 1.0 * MM            # ЛТ-2: points closer than 1 mm
COL_DEV = 0.5 * MM        # ЛТ-3: a point closer than 0.5 mm to the chord of its neighbours is on a straight line
TOL = 30.0 * MM           # micro-kink: a jog, step or kink smaller than 30 mm (≈ 1/3 of a 100 mm partition); the two faces of one
                          # contour never share a line, so a band thinner than TOL (glass) keeps its thickness
ANG = 1.5                 # deg: edges of one face line differ less than this (both ends within TOL of the line too)
MIN_LEN = 100.0 * MM      # edges this long or longer make face lines
JUNC = 150.0 * MM         # a run of short edges up to this long between two crossing face lines (a notch, chamfer or jog at a
                          # junction) becomes their intersection


def dist(a, b): return math.hypot(a[0] - b[0], a[1] - b[1])


def seg_dev(a, b, c):
    """distance of b from the line a-c (from the point a when a == c)"""
    L = dist(a, c)
    if L < 1e-12: return dist(a, b)
    return abs((c[0] - a[0]) * (a[1] - b[1]) - (a[0] - b[0]) * (c[1] - a[1])) / L


def turn(a, b, c):
    ux, uy = b[0] - a[0], b[1] - a[1]; vx, vy = c[0] - b[0], c[1] - b[1]
    if math.hypot(ux, uy) < 1e-12 or math.hypot(vx, vy) < 1e-12: return 0.0
    return math.degrees(math.atan2(ux * vy - uy * vx, ux * vx + uy * vy))


def clean_ring(pts, closed=True, dup=DUP, col_dev=COL_DEV, keep=None):
    """ЛТ-1…ЛТ-3: no closing repeat, no points closer than dup, no points on a straight line (spikes included).
    keep — indices that must stay (not used for removal). Returns the list of points (closing point not repeated)."""
    P = [(float(p[0]), float(p[1])) for p in pts]
    if closed and len(P) > 1 and dist(P[0], P[-1]) < dup: P = P[:-1]
    out = []
    for p in P:
        if out and dist(out[-1], p) < dup: continue
        out.append(p)
    if closed:
        while len(out) > 2 and dist(out[0], out[-1]) < dup: out.pop()
    minn = 3 if closed else 2
    changed = True
    while changed and len(out) > minn:
        changed = False; n = len(out)
        for i in (range(n) if closed else range(1, n - 1)):
            a, b, c = out[i - 1], out[i], out[(i + 1) % n]
            if seg_dev(a, b, c) < col_dev or dist(a, b) < dup:       # on the chord of its neighbours (a spike too) or a repeat
                del out[i]; changed = True; break
    return out


def curved_flags(R, closed=True, tmin=0.3, tmax=25.0, ratio=3.0, run=3):
    """flags per vertex: True where the ring runs along an arc — at least `run` consecutive vertices turning the same way by
    tmin..tmax degrees at edges of similar length (ratio). Edges between two curved vertices are curved too."""
    n = len(R); t = [0.0] * n
    rng = range(n) if closed else range(1, n - 1)
    for i in rng: t[i] = turn(R[i - 1], R[i], R[(i + 1) % n])
    ok = [False] * n
    for i in rng:
        a, b, c = R[i - 1], R[i], R[(i + 1) % n]
        l1, l2 = dist(a, b), dist(b, c)
        if tmin <= abs(t[i]) <= tmax and max(l1, l2) <= ratio * max(min(l1, l2), 1e-9): ok[i] = True
    flags = [False] * n
    i = 0
    seq = list(range(n)) + (list(range(n)) if closed else [])
    k = 0
    while k < len(seq):
        if ok[seq[k]]:
            s = math.copysign(1, t[seq[k]]); j = k
            while j < len(seq) and ok[seq[j]] and math.copysign(1, t[seq[j]]) == s and j - k < n: j += 1
            if j - k >= run:
                for q in range(k, j): flags[seq[q]] = True
            k = max(j, k + 1)
        else: k += 1
    return flags


class FaceLines:
    """face lines of the sheet: infinite lines (unit direction u, a point p) with the segments that support them"""
    def __init__(self, tol=TOL, ang=ANG, min_len=MIN_LEN):
        self.tol, self.ang, self.min_len = tol, ang, min_len
        self.L = []                       # dict(u, p, w, c2, s2, sx, sy, segs)
        self.bins = collections.defaultdict(list)
        self.tree = None

    @staticmethod
    def _theta(a, b):
        return math.atan2(b[1] - a[1], b[0] - a[0]) % math.pi

    def _bin(self, th): return int(math.degrees(th) / max(self.ang, 0.1))

    def _cands(self, th):
        nb = int(180 / max(self.ang, 0.1)) + 1; b = self._bin(th)
        for q in (b - 1, b, b + 1):
            yield from self.bins.get(q % nb, [])

    def dline(self, lid, pt):
        F = self.L[lid]; u = F['u']; p = F['p']
        return abs((pt[0] - p[0]) * u[1] - (pt[1] - p[1]) * u[0])

    def angdiff(self, lid, th):
        F = self.L[lid]; d = abs(F['th'] - th) % math.pi
        return math.degrees(min(d, math.pi - d))

    PIN_TOL = 2.0 * MM        # pinned lines (the faces of door openings) closer than this are one line

    def add_edges(self, edges, pins=None):
        """edges: [(a, b, pid, out)] — pid: id of the contour, out: its outward normal (or None). Long edges first; each joins a
        line it fits (angle < ang, both ends within tol) or makes one. The two faces of one contour never share a line (a glass
        band thinner than tol keeps its thickness): an edge does not join a line that holds an edge of its own contour facing
        the other way. pins — pids whose edges fix their lines (v010: the faces and ends of door openings — the walls at a door
        stay where its opening is, the door keeps fitting its opening): they come first, a pinned line does not move when
        other edges join it, and two pinned edges share a line only within PIN_TOL."""
        pins = pins or set()
        E = sorted(((dist(e[0], e[1]),) + tuple(e) for e in edges if dist(e[0], e[1]) >= self.min_len),
                   key=lambda x: (0 if x[3] in pins else 1, -x[0]))
        for L, a, b, pid, out in E:
            pinned = pid in pins
            th = self._theta(a, b); best = None; bd = None
            nl = (-math.sin(th), math.cos(th)); side = 0 if out is None else (1 if out[0] * nl[0] + out[1] * nl[1] > 0 else -1)
            for lid in self._cands(th):
                if self.angdiff(lid, th) > (0.2 if pinned and self.L[lid].get('pin') else self.ang): continue
                if side and (pid, -side) in self.L[lid]['mem']: continue
                d = max(self.dline(lid, a), self.dline(lid, b))
                lim = self.PIN_TOL if (pinned and self.L[lid].get('pin')) else self.tol
                if d <= lim and (bd is None or d < bd): best, bd = lid, d
            if best is None:
                u = ((b[0] - a[0]) / L, (b[1] - a[1]) / L)
                F = dict(th=th, u=u, p=((a[0] + b[0]) / 2, (a[1] + b[1]) / 2), w=L, c2=L * math.cos(2 * th), s2=L * math.sin(2 * th),
                         sx=L * (a[0] + b[0]) / 2, sy=L * (a[1] + b[1]) / 2, segs=[(a, b)], mem={(pid, side)}, pin=pinned)
                self.L.append(F); self.bins[self._bin(th)].append(len(self.L) - 1)
            else:
                F = self.L[best]; F['w'] += L; F['c2'] += L * math.cos(2 * th); F['s2'] += L * math.sin(2 * th)
                F['sx'] += L * (a[0] + b[0]) / 2; F['sy'] += L * (a[1] + b[1]) / 2; F['segs'].append((a, b)); F['mem'].add((pid, side))
                if F.get('pin'): continue                     # a pinned line stays where its opening is
                # the line follows the weighted mean of its edges (direction by doubled angles, point = weighted centroid)
                th2 = 0.5 * math.atan2(F['s2'], F['c2']) % math.pi
                F['u'] = (math.cos(th2), math.sin(th2)); F['p'] = (F['sx'] / F['w'], F['sy'] / F['w'])
                oldb = self._bin(F['th']); F['th'] = th2; nb = self._bin(th2)
                if nb != oldb:
                    self.bins[oldb].remove(best); self.bins[nb].append(best)
        self.merged = self.merge_close()
        self._index()

    def merge_close(self):
        """second pass (ПЗ-2 residue of 09.10.2026): the first pass depends on the order of the edges and lines move as they take
        edges, so one face can end up on two lines a few mm and a fraction of a degree apart — a step or kink that is not in the
        source. Two lines of one direction (< ang) are one line when every segment of the smaller one lies within tol of the
        merged line and no segment of the bigger one gets farther than tol (or than it already is), and no contour has its two
        faces on them (the side guard)."""
        alive = [True] * len(self.L); merged = 0; changed = True
        while changed:
            changed = False
            for i in sorted([q for q in range(len(self.L)) if alive[q]], key=lambda q: -self.L[q]['w']):
                if not alive[i]: continue
                Fi = self.L[i]
                for j in list(self._cands(Fi['th'])):
                    if j == i or not alive[j] or not alive[i]: continue
                    Fj = self.L[j]
                    if Fj.get('pin'): continue                   # a pinned line is never merged into another one
                    if Fj['w'] > Fi['w'] or self.angdiff(j, Fi['th']) > self.ang: continue
                    if any(s and (pid, -s) in Fi['mem'] for pid, s in Fj['mem']): continue
                    if max(max(self.dline(i, a), self.dline(i, b)) for a, b in Fj['segs']) > self.tol: continue
                    w = Fi['w'] + Fj['w']; c2 = Fi['c2'] + Fj['c2']; s2 = Fi['s2'] + Fj['s2']; sx = Fi['sx'] + Fj['sx']; sy = Fi['sy'] + Fj['sy']
                    if Fi.get('pin'): th2, u, p = Fi['th'], Fi['u'], Fi['p']     # into a pinned line: it stays
                    else: th2 = 0.5 * math.atan2(s2, c2) % math.pi; u = (math.cos(th2), math.sin(th2)); p = (sx / w, sy / w)
                    def dl(q): return abs((q[0] - p[0]) * u[1] - (q[1] - p[1]) * u[0])
                    if max(max(dl(a), dl(b)) for a, b in Fj['segs']) > self.tol: continue
                    lim_i = max(self.tol, max(max(self.dline(i, a), self.dline(i, b)) for a, b in Fi['segs']))
                    if max(max(dl(a), dl(b)) for a, b in Fi['segs']) > lim_i: continue
                    oldb = self._bin(Fi['th'])
                    Fi.update(w=w, c2=c2, s2=s2, sx=sx, sy=sy, th=th2, u=u, p=p); Fi['segs'] = Fi['segs'] + Fj['segs']; Fi['mem'] = Fi['mem'] | Fj['mem']
                    nb = self._bin(th2)
                    if nb != oldb: self.bins[oldb].remove(i); self.bins[nb].append(i)
                    self.bins[self._bin(Fj['th'])].remove(j); alive[j] = False; merged += 1; changed = True
        keep = [q for q in range(len(self.L)) if alive[q]]
        self.L = [self.L[q] for q in keep]
        self.bins = collections.defaultdict(list)
        for lid, F in enumerate(self.L): self.bins[self._bin(F['th'])].append(lid)
        return merged

    def _index(self):
        G = []; self.own = []
        for lid, F in enumerate(self.L):
            for a, b in F['segs']:
                G.append(LineString([a, b])); self.own.append(lid)
        self.G = G; self.tree = shapely.STRtree(G) if G else None

    def near(self, a, b, r):
        """face lines with a supporting segment within r of the segment a-b"""
        if self.tree is None: return []
        q = LineString([a, b]) if dist(a, b) > 1e-9 else Point(a)
        out = set()
        for j in self.tree.query(q.buffer(r)):
            if self.G[j].distance(q) <= r: out.add(self.own[j])
        return out

    def fit(self, lid, a, b, ang_check=True, tol=None):
        tol = self.tol if tol is None else tol
        d = max(self.dline(lid, a), self.dline(lid, b))
        if d > tol: return None
        if ang_check and dist(a, b) >= 4 * self.tol and self.angdiff(lid, self._theta(a, b)) > 2 * self.ang: return None
        return d


def _isect(F1, F2):
    """intersection of two lines given as (point, unit direction); None for parallel ones (< 0.3 deg)"""
    (p1, u1), (p2, u2) = F1, F2
    cr = u1[0] * u2[1] - u1[1] * u2[0]
    if abs(cr) < math.sin(math.radians(0.3)): return None
    t = ((p2[0] - p1[0]) * u2[1] - (p2[1] - p1[1]) * u2[0]) / cr
    return (p1[0] + t * u1[0], p1[1] + t * u1[1])


def _proj(F, q):
    p, u = F; t = (q[0] - p[0]) * u[0] + (q[1] - p[1]) * u[1]
    return (p[0] + t * u[0], p[1] + t * u[1])


JUNC_L = 300.0 * MM       # junction run: at most this long in total
JUNC_R = 120.0 * MM       # … and its inner points within this of the corner it becomes (a notch or jog at a T-junction)


def _drop_junction_runs(runs, E, R, n, FL, tol):
    """runs of edges that are on no face line (lid None, not curved), short in total, between two face lines: a notch, jog or
    chamfer at a junction (two crossing lines -> their corner) or on a straight face (the same line on both sides -> a straight
    face). Returns the new list of runs and how many were dropped."""
    dropped = 0
    while True:
        nr = len(runs)
        if nr < 4: return runs, dropped
        k0 = next((i for i in range(nr) if runs[i][3] is not None), None)
        if k0 is None: return runs, dropped
        rr = runs[k0:] + runs[:k0]
        done = False
        i = 0
        while i < nr:
            A = rr[i]
            if A[3] is None: i += 1; continue
            j = i + 1; L = 0.0; inner = []
            while j < i + nr and rr[j % nr][3] is None and not rr[j % nr][4]:
                e0, e1 = rr[j % nr][1], rr[j % nr][2]
                for e in range(e0, e1 + 1):
                    a, b = E[e % len(E)]; L += dist(a, b); inner.append(a)
                j += 1
            if j == i + 1 or j >= i + nr: i += 1; continue
            B = rr[j % nr]
            if B[3] is None or L > JUNC_L: i += 1; continue
            inner = inner[1:]                                  # the first point is the end of A (on its line)
            ok = False
            if B[3] == A[3]:
                F = FL.L[A[3]]; ok = all(FL.dline(A[3], q) <= 2 * tol for q in inner) if inner else True
            else:
                q = _isect(A[0], B[0])
                if q is not None:
                    ok = all(dist(q, v) <= JUNC_R for v in inner) and dist(q, R[(A[2] + 1) % n]) <= JUNC_L
            if ok:
                LOG.append(('junction', R[(A[2] + 1) % n], 0.0))
                if B[3] == A[3]:
                    merged = (A[0], A[1], B[2], A[3], False)
                    rr = rr[:i] + [merged] + rr[j + 1:] if j < nr else [merged] + rr[(j % nr) + 1:i]
                else:
                    rr = rr[:i + 1] + rr[j:] if j < nr else rr[(j % nr):i + 1]
                dropped += 1; done = True; break
            i += 1
        runs = rr
        if not done: return runs, dropped


def _side(FL, lid, a, b):
    L_ = dist(a, b)
    if L_ < 1e-12: return 0
    out_ = ((b[1] - a[1]) / L_, -(b[0] - a[0]) / L_); th_ = FL.L[lid]['th']
    return 1 if out_[0] * -math.sin(th_) + out_[1] * math.cos(th_) > 0 else -1


def _unify_parallel(runs, E, R, n, FL, tol, closed, pid):
    """ПЗ-2 residue: consecutive runs of one face on two face lines of one direction (< ang) that lie within tol of each other —
    next to each other or through a short connector (<= JUNC_L, edges on no line) — go on the dominant line (the one with more
    supporting length): a step or kink smaller than tol is not in the source (the face lines of the sheet cluster within tol
    too; two lines of one face are a leftover of the order of clustering). Not when the dominant line holds the other face of
    this contour (the side guard) or a vertex of the runs would be farther than tol from it."""
    nr = len(runs)
    if nr < 2 or FL is None: return runs, 0
    lidmap = {}
    def canon(l):
        while l in lidmap: l = lidmap[l]
        return l
    nu = 0
    for i in range(nr if closed else nr - 1):
        A = runs[i]
        if A[3] is None or A[4]: continue
        L = 0.0; j = i + 1; ok = True
        while True:
            if j >= i + nr or (not closed and j >= nr): ok = False; break
            Rj = runs[j % nr]
            if Rj[3] is not None: break
            if Rj[4]: ok = False; break
            for e in range(Rj[1], Rj[2] + 1):
                a, b = E[e % len(E)]; L += dist(a, b)
            j += 1
        if not ok or L > JUNC_L: continue
        B = runs[j % nr]
        if B[4]: continue
        la, lb = canon(A[3]), canon(B[3])
        if la == lb or FL.angdiff(la, FL.L[lb]['th']) > FL.ang: continue
        v0 = R[(A[2] + 1) % n]; v1 = R[B[1] % n]
        if FL.dline(la, v1) > tol or FL.dline(lb, v0) > tol: continue
        pa, pb = FL.L[la].get('pin'), FL.L[lb].get('pin')
        if pa and pb: continue                                   # two door openings' lines: each stays
        if pa or pb: dom, sub = (la, lb) if pa else (lb, la)     # a door opening's line is the face there
        else: dom, sub = (la, lb) if FL.L[la]['w'] >= FL.L[lb]['w'] else (lb, la)
        if pid is not None:
            sa = _side(FL, dom, *E[A[1] % len(E)]); sb = _side(FL, dom, *E[B[1] % len(E)])
            if sa != sb or (pid, -sa) in FL.L[dom]['mem']: continue
        verts = [R[e % n] for r_ in (A, B) for e in range(r_[1], r_[2] + 2)]
        if max(FL.dline(dom, q) for q in verts) > tol: continue
        lidmap[sub] = dom; nu += 1
    if not nu: return runs, 0
    new = []
    for r_ in runs:
        if r_[3] is None: new.append(r_); continue
        l_ = canon(r_[3]); F = FL.L[l_]; ln = (F['p'], F['u'])
        if new and new[-1][3] == l_: new[-1] = (ln, new[-1][1], r_[2], l_, False)
        else: new.append((ln, r_[1], r_[2], l_, False))
    if closed and len(new) > 1 and new[0][3] is not None and new[0][3] == new[-1][3]:
        last = new.pop(); new[0] = (new[0][0], last[1], new[0][2], new[0][3], False)
    return new, nu


LOG = []                    # places changed by the junction and recess rules (for the report)
RECESS_DEPTH = 150.0 * MM   # a recess of a wall face as deep as this at most …
RECESS_LEN = 3000.0 * MM    # … and as long, under an object drawn over the wall (a wall screen), is the wall itself (З-4)


def _fill_covered_recesses(runs, R, n, FL, cover):
    """two runs on the same face line with a recess between them that an object drawn over the wall covers (≥ 50 % of the
    recess): the face goes straight under the object (owner, З-4: «Излом стены прошел не по стене, а по контуру висящего
    монитора»). Returns the new runs and how many recesses were filled."""
    filled = 0
    while True:
        nr = len(runs)
        if nr < 4: return runs, filled
        done = False
        for i in range(nr):
            A = runs[i]
            if A[3] is None: continue
            for m_ in range(2, min(nr - 1, 8)):
                B = runs[(i + m_) % nr]
                if B[3] != A[3]: continue
                mid = [runs[(i + q) % nr] for q in range(1, m_)]
                if any(r[4] for r in mid): break
                v0 = R[(A[2] + 1) % n]; v1 = R[B[1] % n]
                pts = [v0]
                for r in mid:
                    for e in range(r[1], r[2] + 1): pts.append(R[(e + 1) % n])
                L = sum(dist(a, b) for a, b in zip(pts[:-1], pts[1:]))
                if L > RECESS_LEN or max(FL.dline(A[3], q) for q in pts) > RECESS_DEPTH: break
                try:
                    reg = Polygon(pts).buffer(0)
                except Exception:
                    break
                if reg.is_empty or reg.area <= 0: break
                if cover.intersection(reg).area >= 0.5 * reg.area:
                    LOG.append(('recess', reg.centroid.coords[0], reg.area))
                    merged = (A[0], A[1], B[2], A[3], False)
                    idx = [(i + q) % nr for q in range(0, m_ + 1)]
                    keep = [runs[k] for k in range(nr) if k not in idx]
                    pos = min(idx) if max(idx) - min(idx) == m_ else 0
                    runs = keep[:pos] + [merged] + keep[pos:]
                    filled += 1; done = True
                break
            if done: break
        if not done: return runs, filled


def regularize_ring(R, FL=None, tol=TOL, closed=True, protect=None, cover=None, junctions=True, pid=None):
    """R — a cleaned ring (no repeat). Puts edges on face lines FL, merges the edges of one line, drops short junction runs,
    intersects consecutive lines. Returns (new ring, stats)."""
    n = len(R)
    if n < (3 if closed else 2): return list(R), dict(n0=n, n1=n)
    prot = protect if protect is not None else curved_flags(R, closed)
    ne = n if closed else n - 1
    E = [(R[k], R[(k + 1) % n]) for k in range(ne)]
    cur = [prot[k] and prot[(k + 1) % n] for k in range(ne)]       # an edge between two curved vertices is curved
    lid = [None] * ne
    if FL is not None:
        # long edges first, then short ones — a short one prefers the line of a neighbour
        order = sorted(range(ne), key=lambda k: -dist(*E[k]))
        for k in order:
            if cur[k]: continue
            a, b = E[k]; cands = FL.near(a, b, 3 * tol)
            short = dist(a, b) < 4 * tol
            pref = [lid[(k - 1) % ne], lid[(k + 1) % ne]] if (closed or 0 < k < ne - 1) else []
            best = None; bd = None
            L_ = dist(a, b); out_ = ((b[1] - a[1]) / L_, -(b[0] - a[0]) / L_) if L_ > 1e-12 else None
            for c in ([x for x in pref if x is not None] if short else []) + list(cands):
                if pid is not None and out_ is not None:
                    th_ = FL.L[c]['th']; side_ = 1 if out_[0] * -math.sin(th_) + out_[1] * math.cos(th_) > 0 else -1
                    if (pid, -side_) in FL.L[c]['mem']:               # the other face of this contour is on that line …
                        if not (FL.L[c].get('pin') and max(FL.dline(c, a), FL.dline(c, b)) <= FL.PIN_TOL):
                            continue                                  # … unless the edge lies on a door opening's line already
                d = FL.fit(c, a, b, ang_check=not short, tol=tol)
                if d is not None and (bd is None or d < bd - 1e-9): best, bd = c, d
                if short and best is not None and c in pref: break
            lid[k] = best
    lines = []                                 # per edge: (point, unit dir) — face line or the edge's own line
    for k in range(ne):
        if lid[k] is not None:
            F = FL.L[lid[k]]; lines.append((F['p'], F['u']))
        else:
            a, b = E[k]; L = dist(a, b)
            lines.append((a, ((b[0] - a[0]) / L, (b[1] - a[1]) / L)) if L > 1e-12 else (a, (1.0, 0.0)))
    runs = []                                   # (line, first edge, last edge, lid, curved)
    for k in range(ne):
        if runs and lid[k] is not None and runs[-1][3] == lid[k]:
            runs[-1] = (runs[-1][0], runs[-1][1], k, lid[k], False)
        else:
            runs.append((lines[k], k, k, lid[k], cur[k]))
    if closed and len(runs) > 1 and runs[0][3] is not None and runs[0][3] == runs[-1][3]:
        last = runs.pop(); runs[0] = (runs[0][0], last[1], runs[0][2], runs[0][3], False)
    nj = 0; nf = 0; nu = 0
    if FL is not None:
        runs, nu = _unify_parallel(runs, E, R, n, FL, tol, closed, pid)
    if closed and FL is not None and cover is not None and not cover.is_empty:
        runs, nf = _fill_covered_recesses(runs, R, n, FL, cover)
    if closed and FL is not None and junctions:
        runs, nj = _drop_junction_runs(runs, E, R, n, FL, tol)
    if len(runs) < (3 if closed else 1):
        return list(R), dict(n0=n, n1=n, fallback='runs')
    out = []
    nr = len(runs)
    for i in range(nr if closed else nr - 1):
        A = runs[i]; B = runs[(i + 1) % nr]
        v0 = R[(A[2] + 1) % n]                  # the original vertex at the end of A
        v1 = R[B[1] % n]                         # the original vertex at the start of B (= v0 when the runs are adjacent)
        q = _isect(A[0], B[0])
        if q is not None and dist(q, v0) <= 3 * tol + dist(v0, v1) + JUNC_R * (v0 != v1):
            out.append(q)
        else:                                    # parallel or far: a real step — both ends, on their lines
            out.append(_proj(A[0], v0)); out.append(_proj(B[0], v1))
    if not closed:
        out = [_proj(runs[0][0], R[0])] + out + [_proj(runs[-1][0], R[-1])]
    out = clean_ring(out, closed=closed)
    return out, dict(n0=n, n1=len(out), junctions=nj, recesses=nf, parallel=nu)


def ring_ok(old, new, tol=TOL, closed=True):
    """the new ring may replace the old one: valid, same orientation, no point of either farther than 2 tol from the other"""
    if len(new) < (3 if closed else 2): return False
    try:
        if closed:
            po, pn = Polygon(old), Polygon(new)
            if not pn.is_valid or pn.area <= 0: return False
            if po.is_valid and po.area > 0 and abs(pn.area - po.area) > max(0.05 * po.area, 2 * tol * pn.length):
                return False
            return LineString(old + [old[0]]).hausdorff_distance(LineString(new + [new[0]])) <= max(2 * tol, JUNC_R, RECESS_DEPTH)
        return LineString(old).hausdorff_distance(LineString(new)) <= max(2 * tol, JUNC_R)
    except Exception:
        return False


def repair_ring(old, new, tol=TOL):
    """a ring that crosses itself after the cleaning (a slit of the source closed by two face lines that cross): its valid
    outline when that is close to the old one (area within 5 %), else None"""
    try:
        pn = Polygon(new)
        if pn.is_valid: return None
        q = pn.buffer(0)
        if q.is_empty: return None
        if q.geom_type == 'MultiPolygon': q = max(q.geoms, key=lambda x: x.area)
        po = Polygon(old).buffer(0)
        if abs(q.area - po.area) > 0.05 * po.area: return None
        r = clean_ring(list(q.exterior.coords))
        return r if len(r) >= 3 else None
    except Exception:
        return None


def regularize_polygon(g, FL=None, tol=TOL, cover=None, pid=None):
    """a shapely Polygon -> regularized Polygon (or the cleaned original when a ring would break); stats"""
    g = oriented(g)
    rings = [list(g.exterior.coords)] + [list(h.coords) for h in g.interiors]
    out = []; st = collections.Counter()
    for k, r in enumerate(rings):
        c = clean_ring(r)
        st['v0'] += len(r) - 1; st['v_clean'] += len(c)
        nr, s = regularize_ring(c, FL, tol, cover=cover, pid=pid)
        if not ring_ok(c, nr, tol): nr = repair_ring(c, nr, tol) or nr
        if not ring_ok(c, nr, tol):                       # the junction or recess rule broke the ring: face lines only
            nr, s = regularize_ring(c, FL, tol, cover=None, junctions=False, pid=pid); st['retry'] += 1
            if not ring_ok(c, nr, tol): nr = repair_ring(c, nr, tol) or nr
        for t_ in (tol * 0.5, tol * 0.25):                # a strip thinner than tol of this contour collapsed: a smaller tol
            if ring_ok(c, nr, tol): break
            nr, s = regularize_ring(c, FL, t_, cover=None, junctions=False, pid=pid); st['retry smaller tol'] += 1
        st['junctions'] += s.get('junctions', 0); st['recesses'] += s.get('recesses', 0); st['parallel'] += s.get('parallel', 0)
        if ring_ok(c, nr, tol): out.append(nr); st['v1'] += len(nr)
        else: out.append(c); st['v1'] += len(c); st['fallback'] += 1
    try:
        p = Polygon(out[0], out[1:])
        if not p.is_valid:
            # the exterior and a hole were cleaned apart and now touch: exterior minus holes, each made valid
            from shapely.ops import unary_union as _uu
            ext = Polygon(out[0]).buffer(0)
            hs = [Polygon(h).buffer(0) for h in out[1:]]
            p2 = ext.difference(_uu(hs)) if hs else ext
            if not p2.is_empty and abs(p2.area - g.area) <= 0.05 * g.area: p = p2; st['repaired'] += 1
            else:
                st['fallback_poly'] += 1
                c = [clean_ring(r) for r in rings]; p = Polygon(c[0], c[1:])
                if not p.is_valid: p = g
    except Exception:
        st['fallback_poly'] += 1; p = g
    return p, st


def rectangle_of(g, tol=TOL):
    """the polygon as its smallest rotated rectangle when it is one (no point of either farther than tol from the other)"""
    m = g.minimum_rotated_rectangle
    if m.geom_type != 'Polygon': return None
    if g.exterior.hausdorff_distance(m.exterior) <= tol and len(g.interiors) == 0: return Polygon(list(m.exterior.coords)[:-1])
    return None


def oriented(g):
    """exterior counter-clockwise, holes clockwise: the material is on the left of every edge"""
    from shapely.geometry.polygon import orient
    return orient(g, 1.0)


def face_edges(g, pid, skip_curved=True):
    """edges of a polygon for FaceLines.add_edges: (a, b, pid, outward normal); edges of curved runs are left out"""
    out = []
    g = oriented(g)
    for r in [g.exterior] + list(g.interiors):
        c = clean_ring(list(r.coords)); n = len(c)
        if n < 3: continue
        fl = curved_flags(c) if skip_curved else [False] * n
        for k in range(n):
            if fl[k] and fl[(k + 1) % n]: continue
            a, b = c[k], c[(k + 1) % n]; L = dist(a, b)
            if L < 1e-9: continue
            out.append((a, b, pid, ((b[1] - a[1]) / L, -(b[0] - a[0]) / L)))
    return out
