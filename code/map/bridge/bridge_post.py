"""bridge_post.py — шаги геометрии моста 0.33 после сборки SVG (код карты v012; перенос кода прохода карты клиент Б v03, 08.10.2026,
общими правилами, без точечных правок по координатам). Каждый шаг — признак из DXF плана или из геометрии карты, пороги — в м и долях T.

Порядок (run): короба колонн (П3-1) -> дуги плана (П3-4, КМ-8) -> короба ПК у колонн (П3-12) -> стены короче 1 м в санузле и в проёме,
двери кабин внутри санузла (П3-14, КМ-6) -> прореживание и косые рёбра на общем графе (В2К-3, П3-3, КМ-4) -> проёмы без стены и у концов
стен (П3-5, К8, КМ-3) -> проём по сечению стены -> размер колонн по телу плана (П3-2, КМ-5) -> стекло плана на рёбрах помещений (П3-11,
КМ-10) -> порядок слоя rooms, стекло режется по проёму и коробу (П3-10, КМ-2) -> концы стен до грани короба (П3-1 п. 4) -> коллинеарные
вершины (Ч-09) -> самопроверка: контуры валидны, накладок нет (КМ-11).
Можно гонять и отдельно на SVG моста: python3 bridge_post.py in.svg out.svg --px-per-m P [--T 6] (без входов DXF — шаги, которым нужен план,
пропускаются с записью в отчёт)."""
import math, collections, json, sys, argparse
import numpy as np
from shapely.geometry import Polygon, LineString, Point, MultiPoint
from shapely.ops import unary_union
from shapely.strtree import STRtree
import bridge_graph as BG
from bridge_graph import dense, stroked

WALL = '#CBD2D6'


def _log_to(L): return lambda s: L.append(str(s))


# ------------------------------------------------------------------ П3-1: под коробом колонны (перенос boxes.py v03)
def runs_inside(P, inside, closed):
    n = len(P); out = []
    if not any(inside): return out
    if closed and all(inside): return [list(range(n))]
    start = next(k for k in range(n) if not inside[k]) if closed else 0
    cur = []
    for t in range(n):
        k = (start + t) % n
        if inside[k]: cur.append(k)
        elif cur: out.append(cur); cur = []
    if cur: out.append(cur)
    return out


def boxes_clean(M, pxm, T, log):
    """свободная стена в коробе ≥ 95 % — снять; частью — резать по грани, хвост < 0,3 м снять, короткий конец у грани — продолжением;
    контур помещения, стекла, витража через короб — хорда вход -> выход (три и больше входов — через одну общую точку)"""
    cols = {e['id']: Polygon(dense(e['subs'][0])).buffer(0) for e in M.els('column') if len(e['subs'][0]['pts']) >= 3}
    cols = {k: v for k, v in cols.items() if not v.is_empty}
    stat = collections.Counter()
    for e in list(M.els(('wall', 'glass'))):
        new_subs = []
        for s in e['subs']:
            if len(s['pts']) < 2: continue
            L = LineString(dense(s))
            if s['arcs']: new_subs.append(s); continue
            hit = [c for c in cols.values() if c.buffer(1.5).intersects(L)]
            if not hit: new_subs.append(s); continue
            U = unary_union(hit)
            if L.intersection(U.buffer(1.5)).length >= 0.95 * L.length: stat['стен_снято'] += 1; continue
            rest = L.difference(U)
            parts = [rest] if rest.geom_type == 'LineString' else list(getattr(rest, 'geoms', []))
            parts = [p for p in parts if p.geom_type == 'LineString' and p.length >= 0.3 * pxm]
            if len(parts) == 1 and abs(parts[0].length - L.length) < 0.01: new_subs.append(s); continue
            stat['стен_обрезано'] += 1; Bd = U.boundary
            for p in parts:
                c = [tuple(v) for v in p.coords]
                for end in (0, 1):
                    if end == 1: c.reverse()
                    if len(c) >= 3 and Bd.distance(Point(c[0])) < 0.05 and math.dist(c[0], c[1]) < T:
                        q, r_ = c[2], c[1]; dx, dy = r_[0] - q[0], r_[1] - q[1]; ln = math.hypot(dx, dy)
                        X = LineString([r_, (r_[0] + dx / ln * 40, r_[1] + dy / ln * 40)]).intersection(Bd) if ln > 1e-9 else None
                        pts_ = ([X] if X is not None and X.geom_type == 'Point' else list(getattr(X, 'geoms', []))) if X is not None else []
                        if pts_: X = min(pts_, key=lambda g: g.distance(Point(r_))); c = [(X.x, X.y)] + c[2:]; stat['хвост_доведён'] += 1
                        else: c = c[1:]; stat['хвост_снят'] += 1
                    if end == 1: c.reverse()
                new_subs.append(dict(pts=c, arcs={}, closed=False))
        if not new_subs: M.remove(e['id'])
        else: e['subs'] = new_subs
    allk = ('room', 'glass', 'window')
    for cid, cp in cols.items():
        inner = cp.buffer(-0.01); Bb = cp.exterior; recs = []
        for e in M.els(allk):
            for s in e['subs']:
                P = s['pts']; ins = [inner.contains(Point(v)) for v in P]
                for r in runs_inside(P, ins, s['closed']):
                    n = len(P)
                    if not s['closed'] and (r[0] == 0 or r[-1] == n - 1): recs = None; break
                    recs.append((e, s, r, P[(r[0] - 1) % n], P[(r[-1] + 1) % n]))
                if recs is None: break
            if recs is None: break
        if recs is None: stat['короб_пропущен_открытый_конец'] += 1; continue
        if not recs: continue
        def cross(p, q):
            if Bb.distance(Point(p)) < 0.05: return tuple(p)
            X = LineString([p, q]).intersection(Bb)
            pts_ = [X] if X.geom_type == 'Point' else [g for g in getattr(X, 'geoms', []) if g.geom_type == 'Point']
            if not pts_: return None
            g = min(pts_, key=lambda g: g.distance(Point(p))); return (g.x, g.y)
        Q = []
        def rep(p):
            for q in Q:
                if math.dist(p, q) <= 1.5: return q
            Q.append(p); return p
        plan = []
        for (e, s, r, a, b) in recs:
            P = s['pts']; E = cross(a, P[r[0]]); X = cross(b, P[r[-1]])
            if E is None or X is None: plan = None; break
            plan.append((e, s, r, rep(E), rep(X), a, b))
        if plan is None or not Q: stat['короб_пропущен_нет_пересечения'] += 1; continue
        J = None
        if len(Q) >= 3:
            dirs = {}
            for (e, s, r, E, X, a, b) in plan:
                for pnt, out in ((E, a), (X, b)):
                    if math.dist(pnt, out) > 1e-6: dirs.setdefault(pnt, (pnt[0] - out[0], pnt[1] - out[1]))
            ang = lambda u, v: abs(math.degrees(math.atan2(u[0] * v[1] - u[1] * v[0], u[0] * v[0] + u[1] * v[1])))
            best = None
            for i in range(len(Q)):
                for k in range(i + 1, len(Q)):
                    u, v = dirs.get(Q[i]), dirs.get(Q[k])
                    if u and v and ang(u, v) > 170: best = (Q[i], Q[k])
            if best:
                A, Bp = best; others = [q for q in Q if q not in best]; dx, dy = Bp[0] - A[0], Bp[1] - A[1]; L2 = dx * dx + dy * dy
                feet = [(A[0] + ((q[0] - A[0]) * dx + (q[1] - A[1]) * dy) / L2 * dx, A[1] + ((q[0] - A[0]) * dx + (q[1] - A[1]) * dy) / L2 * dy) for q in others]
                J = (sum(f[0] for f in feet) / len(feet), sum(f[1] for f in feet) / len(feet)) if feet else None
            else: J = (sum(q[0] for q in Q) / len(Q), sum(q[1] for q in Q) / len(Q))
        per = {}
        for (e, s, r, E, X, a, b) in plan: per.setdefault(id(s), (s, []))[1].append((r, E, X))
        for sid, (s, items) in per.items():
            P = s['pts']; n = len(P); drop = set(); ins_at = {}
            for (r, E, X) in items:
                drop |= set(r); ins_at[r[0]] = [E] if E == X else ([E, X] if J is None else [E, J, X])
            out = []; arcs = {}
            for k in range(n):
                if k in drop:
                    if k in ins_at: out += [tuple(v) for v in ins_at[k]]
                    continue
                if k in s['arcs']: arcs[len(out)] = s['arcs'][k]
                out.append(tuple(P[k]))
            s['pts'] = out; s['arcs'] = arcs
        stat['коробов_через_хорду'] += 1
    BG.dedupe(M)
    log('короба (П3-1): %s' % dict(stat)); return dict(stat)


# ------------------------------------------------------------------ П3-4, КМ-8: дуги (перенос arcs.py v03; окружности — из кривых DXF)
def _ang(c, v): return math.degrees(math.atan2(v[1] - c[1], v[0] - c[0]))


def _in_span(a, a0, a1, m):
    w = (a1 - a0) % 360; t = (a - a0 + m) % 360
    return t <= w + 2 * m


def circles_from_curves(curves, M_, t_, pxm, min_r_m=0.4, max_r_m=15.0):
    """кривые DXF (класс, cx, cy, r, a0, a1, полная) мм -> окружности осей px: центр, r оси (середина граней), пролёт (углы px, против
    часовой в координатах карты); грани одной стены — концентрические дуги с общим центром (± 0,05 м) и перекрытием пролёта"""
    det = np.linalg.det(M_); s = math.sqrt(abs(det)); flip = det < 0
    C = []
    for cls, cx, cy, r, a0, a1, full in curves:
        if not (min_r_m * 1000 <= r <= max_r_m * 1000) or cls not in ('wall', 'glass', 'fglass'): continue
        c = np.array([cx, cy]) @ M_.T + t_
        if full: sp = (0.0, 359.9)
        elif flip: sp = ((-a1) % 360, (-a0) % 360)
        else: sp = (a0 % 360, a1 % 360)
        C.append(dict(c=c, rp=r * s, sp=sp, cls=cls))                     # s — px карты на мм плана
    out = []; used = [False] * len(C)
    for i in range(len(C)):
        if used[i]: continue
        grp = [i]; used[i] = True
        for j in range(i + 1, len(C)):
            if used[j] or np.hypot(*(C[j]['c'] - C[i]['c'])) > 0.05 * pxm or abs(C[j]['rp'] - C[i]['rp']) > 0.6 * pxm: continue
            grp.append(j); used[j] = True
        rs = sorted({round(C[g]['rp'], 2) for g in grp}); c = np.mean([C[g]['c'] for g in grp], axis=0)
        r_ax = (min(rs) + max(rs)) / 2 if len(rs) > 1 else rs[0]
        a0s = [C[g]['sp'] for g in grp]; amin = min(a[0] for a in a0s); amax = max(a[0] + ((a[1] - a[0]) % 360) for a in a0s)
        out.append(dict(name='дуга (%.0f,%.0f) r %.2f м' % (c[0], c[1], r_ax / pxm), c=(float(c[0]), float(c[1])), r=float(r_ax),
                        span=(amin % 360, amax % 360) if amax - amin < 359 else (0.0, 359.9), faces=rs, cls=C[grp[0]]['cls']))
    return out


def arcs_apply(M, arcs, tol=6.0, margin=8.0, log=print):
    """цепочка вершин носителя у окружности (|d − r| ≤ tol, угол в пролёте ± margin) -> одна дуга SVG A между концами цепочки во всех
    носителях сразу; узел другого носителя внутри цепочки делит дугу на две"""
    ALLK = ('room', 'wall', 'glass', 'window'); stat = collections.Counter()
    for A in arcs:
        c = A['c']; r = A['r']; a0, a1 = A['span']
        near = lambda v: abs(math.dist(v, c) - r) <= tol and _in_span(_ang(c, v), a0, a1, margin)
        nb = collections.defaultdict(set)
        for e in M.els(ALLK):
            for s in e['subs']:
                P = s['pts']; n = len(P)
                for k, v in enumerate(P):
                    if not near(v): continue
                    for j in ((k - 1) % n if (s['closed'] or k > 0) else None, (k + 1) % n if (s['closed'] or k < n - 1) else None):
                        if j is not None: nb[tuple(v)].add(tuple(P[j]))
        junction = lambda v: any(not near(u) for u in nb[tuple(v)]) or sum(1 for u in nb[tuple(v)] if near(u)) > 2
        made = 0
        for e in M.els(ALLK):
            for s in e['subs']:
                P = s['pts']; n = len(P); flags = [near(v) for v in P]
                if sum(flags) < 2: continue
                idx = list(range(n))
                if s['closed'] and not all(flags):
                    st = next(k for k in range(n) if not flags[k]); idx = [(st + t) % n for t in range(n)]
                runs = []; cur = []
                for k in idx:
                    if flags[k]: cur.append(k)
                    elif cur: runs.append(cur); cur = []
                if cur: runs.append(cur)
                newarcs = {}; drop = set()
                for run in runs:
                    if len(run) < 2: continue
                    key = {k for k in run[1:-1] if junction(P[k])}
                    pieces = []; cur = [run[0]]
                    for k in run[1:]:
                        cur.append(k)
                        if k in key: pieces.append(cur); cur = [k]
                    if len(cur) > 1: pieces.append(cur)
                    for pc in pieces:
                        p, q = P[pc[0]], P[pc[-1]]
                        if math.dist(p, q) < 3: continue
                        sweep = sum((_ang(c, P[pc[t + 1]]) - _ang(c, P[pc[t]]) + 180) % 360 - 180 for t in range(len(pc) - 1))
                        if abs(sweep) < 4 and len(pc) < 3: continue
                        if not s['closed'] and pc[-1] == pc[0]: continue
                        rr = (math.dist(p, c) + math.dist(q, c)) / 2
                        newarcs[pc[0]] = (round(rr, 2), round(rr, 2), 0.0, 1 if abs(sweep) > 180 else 0, 1 if sweep > 0 else 0)
                        drop |= set(pc[1:-1]); made += 1
                if not newarcs: continue
                out = []; arcs_ = {}
                for k in range(n):
                    if k in drop: continue
                    if k in newarcs: arcs_[len(out)] = newarcs[k]
                    elif k in s['arcs']: arcs_[len(out)] = s['arcs'][k]
                    out.append(P[k])
                s['pts'] = out; s['arcs'] = arcs_
        stat[A['name']] = made
    log('дуги (П3-4): %s' % dict(stat)); return dict(stat)


def count_arcs(M):
    """дуг SVG A у носителей и ломаных дуг (подряд ≥ 5 коротких рёбер одного знака поворота на одной окружности, < 1 px)"""
    nA = 0; poly = 0
    for e in M.els(('room', 'wall', 'glass', 'window')):
        for s in e['subs']:
            nA += len(s['arcs']); P = np.array(s['pts']); n = len(P)
            if n < 6: continue
            m = n if s['closed'] else n - 1; i = 0
            E = [P[(k + 1) % n] - P[k] for k in range(m)]; L = [float(np.hypot(*v)) for v in E]
            cr = [E[k][0] * E[(k + 1) % m][1] - E[k][1] * E[(k + 1) % m][0] for k in range(m)]
            while i < m:
                j = i
                while j < m and L[j] < 18 and (j == i or np.sign(cr[j - 1]) == np.sign(cr[j])) and j not in s['arcs']: j += 1
                if j - i >= 5:
                    Q = np.array([P[(t) % n] for t in range(i, j + 1)]); A_ = np.c_[2 * Q, np.ones(len(Q))]; cc = np.linalg.lstsq(A_, (Q ** 2).sum(1), rcond=None)[0]
                    R = math.sqrt(max(cc[2] + cc[0] ** 2 + cc[1] ** 2, 0))
                    if 0 < R < 5000 and np.abs(np.hypot(Q[:, 0] - cc[0], Q[:, 1] - cc[1]) - R).max() < 1.0: poly += 1
                    i = j
                else: i += 1
    return nA, poly


# ------------------------------------------------------------------ П3-12: короб ПК у колонны (перенос pkbox.py v03; тела стен и надписи — из DXF)
def pk_boxes(M, pk_px, bodies_px, pxm, T, log):
    """тело стен плана у надписи ПК (надписи — из настройки), открытое радиусом половины толщины перегородки — связная часть у надписи,
    прямоугольник от 0,25 м², заполненный ≥ 80 %; карта закрывает его телом стен и колонн меньше чем на 50 % — короб колонны (№89);
    перегородка между нишами — стеной, если её нет"""
    if not pk_px or not bodies_px:
        log('короба ПК (П3-12): надписей %d, тел стен %d — пропуск' % (len(pk_px), len(bodies_px))); return 0
    r_open, near, snap = 0.07 * pxm, 0.8 * pxm, 0.21 * pxm
    tree = STRtree(bodies_px); B = map_body(M); n = 0
    tmpl = next(iter(M.els('column')), None); wt = next(iter(M.els('wall')), None)
    for k, (x, y, txt) in enumerate(pk_px):
        p = Point(x, y); nb_ = [bodies_px[int(j)] for j in tree.query(p.buffer(near)) if bodies_px[int(j)].distance(p) < near]
        if not nb_: continue
        U = unary_union(nb_).buffer(0.2).buffer(-0.2); O = U.buffer(-r_open, join_style=2).buffer(r_open, join_style=2)
        parts = [g for g in getattr(O, 'geoms', [O]) if g.geom_type == 'Polygon' and g.area > 0]
        if not parts: continue
        g = min(parts, key=lambda g: g.distance(p))
        if g.distance(p) > snap: continue
        R = g.minimum_rotated_rectangle
        if R.area / pxm ** 2 < 0.25 or g.area / R.area < 0.8: continue
        cov = R.intersection(B).area / R.area if not B.is_empty else 0.0
        if cov >= 0.5: log('ПК у (%.0f,%.0f): короб %.2f м² закрыт стенами карты на %.0f %% — не дорисован' % (x, y, R.area / pxm ** 2, 100 * cov)); continue
        if tmpl is None: log('ПК у (%.0f,%.0f): колонн на карте нет — шаблона короба нет, пропуск' % (x, y)); continue
        at = dict(tmpl['attrs']); at['id'] = 'column-b-pk%d' % k; at['data-kind'] = 'box'; at['data-note'] = 'ПК'
        M.add('rooms', dict(kind='column', id=at['id'], attrs=at, subs=[dict(pts=[tuple(round(c, 2) for c in v) for v in list(R.exterior.coords)[:-1]], arcs={}, closed=True)]))
        n += 1; log('ПК у (%.0f,%.0f): короб %.2f м² (закрыт картой на %.0f %%) — коробом колонны (№89)' % (x, y, R.area / pxm ** 2, 100 * cov))
        for j, t in enumerate(getattr(U.difference(O.buffer(0.5)), 'geoms', [U.difference(O.buffer(0.5))])):
            if t.is_empty or t.geom_type != 'Polygon' or t.area < 20 or t.distance(R) > 2: continue
            Qr = t.minimum_rotated_rectangle; c = list(Qr.exterior.coords)[:4]; a, b2 = math.dist(c[0], c[1]), math.dist(c[1], c[2])
            if max(a, b2) < 0.4 * pxm or min(a, b2) > snap: continue
            if a >= b2: p1 = ((c[1][0] + c[2][0]) / 2, (c[1][1] + c[2][1]) / 2); p2 = ((c[3][0] + c[0][0]) / 2, (c[3][1] + c[0][1]) / 2)
            else: p1 = ((c[0][0] + c[1][0]) / 2, (c[0][1] + c[1][1]) / 2); p2 = ((c[2][0] + c[3][0]) / 2, (c[2][1] + c[3][1]) / 2)
            Lp = LineString([p1, p2])
            if wt is None or Lp.buffer(3.0).intersection(B).area / Lp.buffer(3.0).area >= 0.5: continue
            at2 = dict(wt['attrs']); at2['id'] = 'wall-b-pk%d-%d' % (k, j)
            M.add('rooms', dict(kind='wall', id=at2['id'], attrs=at2, subs=[dict(pts=[p1, p2], arcs={}, closed=False)]))
            log('ПК у (%.0f,%.0f): перегородка между нишами %.2f м — стеной' % (x, y, Lp.length / pxm))
    return n


def map_body(M, T=6.0):
    L = []
    for e in M.els(('room', 'wall', 'glass', 'window')):
        if not stroked(e): continue
        w = float(e['attrs'].get('stroke-width', T))
        for s in e['subs']:
            P = dense(s); P = P + ([P[0]] if s['closed'] else [])
            if len(P) > 1: L.append(LineString(P).buffer(w / 2, cap_style=2, join_style=2))
    L += [Polygon(dense(e['subs'][0])).buffer(0) for e in M.els('column') if len(e['subs'][0]['pts']) >= 3]
    return unary_union(L) if L else Polygon()


# ------------------------------------------------------------------ П3-14, КМ-6: стены короче 1 м в санузле и в проёме, двери кабин в санузле
def sides(M, D):
    B = D.buffer(2.0); out = []
    for e in M.els('room'):
        P = M.poly(e)
        if P.is_valid and P.intersects(B):
            a = P.intersection(B).area
            if a > 1: out.append((a, e))
    return [e for a, e in sorted(out, key=lambda x: -x[0])]


def short_walls(M, pxm, log):
    """свободная стена короче 1 м внутри помещения санузла или в проёме двери, не касающаяся двумя концами других стен, — не стена
    (коробка двери, полотно, стенки кабин); дверь кабины внутри санузла — не проём (строка 30; исключение — строка 171)"""
    doors = {e['id']: Polygon(e['subs'][0]['pts']).buffer(0) for e in M.els('door') if len(e['subs'][0]['pts']) >= 3}
    wc = [M.poly(e).buffer(-1.0) for e in M.els('room') if 'wc' in (e['attrs'].get('data-type') or '')]
    LN, ID = [], []
    for e in M.els(('room', 'wall', 'glass', 'window')):
        if e['kind'] == 'room' and not stroked(e): continue
        for s_ in e['subs']:
            if len(s_['pts']) >= 2: LN.append(LineString(dense(s_) + ([dense(s_)[0]] if s_['closed'] else []))); ID.append(e['id'])
    for e in M.els('column'):
        if len(e['subs'][0]['pts']) >= 3: LN.append(Polygon(dense(e['subs'][0])).exterior); ID.append(e['id'])
    TR = STRtree(LN) if LN else None
    st = collections.Counter()
    for e in list(M.els('wall')):
        Ls = [LineString(dense(s_)) for s_ in e['subs'] if len(s_['pts']) >= 2]
        if not Ls: continue
        L = unary_union(Ls)
        if L.length >= 1.0 * pxm: continue
        inwc = any(w.contains(L) for w in wc); indoor = any(D.buffer(1.0).intersection(L).length >= 0.5 * L.length for D in doors.values())
        if not (inwc or indoor): continue
        ends = [Point(Ls[0].coords[0]), Point(Ls[-1].coords[-1])]
        touch = sum(1 for p in ends if TR is not None and any(ID[int(j)] != e['id'] and LN[int(j)].distance(p) <= 1.5 for j in TR.query(p.buffer(1.5))))
        if touch >= 2 and not indoor: continue
        M.remove(e['id']); st['в_санузле' if inwc else 'в_проёме'] += 1
    removed = []
    for eid, D in doors.items():
        S = sides(M, D)
        if S and 'wc' in (S[0]['attrs'].get('data-type') or '') and M.poly(S[0]).buffer(-1.0).contains(D):
            M.remove(eid); st['дверей_кабин_в_санузле'] += 1; removed.append(eid)
    log('стены < 1 м и двери кабин (П3-14): %s' % dict(st)); return dict(st), removed


# ------------------------------------------------------------------ П3-5, К8, КМ-3: проёмы без стены и у концов стен (перенос finish.py v03)
def on_wall_len(M, D):
    L = 0.0; core = D.buffer(-0.5)
    for e in M.els(('room', 'wall', 'glass', 'window')):
        if e['kind'] == 'room' and not stroked(e): continue
        for s in e['subs']:
            if len(s['pts']) < 2: continue
            L += LineString(dense(s) + ([dense(s)[0]] if s['closed'] else [])).intersection(core).length
    return L


def door_axis(Q):
    D = Polygon(Q); R = list(D.minimum_rotated_rectangle.exterior.coords)[:4]
    e01, e12 = math.dist(R[0], R[1]), math.dist(R[1], R[2])
    if e01 >= e12: a = ((R[1][0] + R[2][0]) / 2, (R[1][1] + R[2][1]) / 2); b = ((R[3][0] + R[0][0]) / 2, (R[3][1] + R[0][1]) / 2); return a, b, e01, e12
    a = ((R[0][0] + R[1][0]) / 2, (R[0][1] + R[1][1]) / 2); b = ((R[2][0] + R[3][0]) / 2, (R[2][1] + R[3][1]) / 2); return a, b, e12, e01


def wall_tmpl(M, T):
    w = next(iter(M.els('wall')), None)
    return dict(w['attrs']) if w is not None else {'data-class': 'int', 'fill': 'none', 'stroke': WALL, 'stroke-width': '%g' % T, 'stroke-linecap': 'square'}


def doors_without_wall(M, pxm, T, log, need=0.9):
    """проём на стене меньше чем на половину — стена по оси проёма до стен по сторонам (ПК3-К17, map/rules/40 §2.9);
    проём на стене меньше чем на 90 % — стена по своей оси под всем проёмом, концы на T/2 внутрь (П3-5, дополнение круга 2)"""
    st = collections.Counter(); tmpl = wall_tmpl(M, T); lines = None; out = []
    def carrier_lines():
        L = []
        for e in M.els(('room', 'wall', 'glass', 'window', 'column')):
            if e['kind'] == 'room' and not stroked(e): continue
            for s in e['subs']:
                pts = dense(s) + ([dense(s)[0]] if (s['closed'] or e['kind'] == 'column') else [])
                if len(pts) >= 2: L.append(LineString(pts))
        return unary_union(L)
    for d in list(M.els('door')):
        Q = d['subs'][0]['pts']
        if len(Q) < 4: continue
        D = Polygon(Q); a_, b_, lng, dep = door_axis(Q)
        f = on_wall_len(M, D) / lng if lng else 1.0
        if f >= need or dep < T - 0.5: continue                           # проём в стекле (4 px) — стена под ним не нужна
        if f < 0.5:                                                       # без стены: стена по оси до стен по сторонам
            if lines is None: lines = carrier_lines()
            ux, uy = (a_[0] - b_[0]) / lng, (a_[1] - b_[1]) / lng; ends = []
            for (p, sgn) in ((a_, 1), (b_, -1)):
                X = LineString([p, (p[0] + sgn * ux * 80, p[1] + sgn * uy * 80)]).intersection(lines)
                pts = [X] if X.geom_type == 'Point' else [g for g in getattr(X, 'geoms', []) if g.geom_type == 'Point']
                if not pts and X.geom_type in ('LineString', 'MultiLineString'): pts = [Point(cc) for g in getattr(X, 'geoms', [X]) for cc in g.coords]
                ends.append(min(pts, key=lambda g: g.distance(Point(p))) if pts else None)
            if None not in ends:
                at = dict(tmpl); at['id'] = 'wall-b-d%d' % st['стена_по_оси']
                M.add('rooms', dict(kind='wall', id=at['id'], attrs=at, subs=[dict(pts=[(round(ends[0].x, 2), round(ends[0].y, 2)), (round(ends[1].x, 2), round(ends[1].y, 2))], arcs={}, closed=False)]))
                st['стена_по_оси'] += 1; lines = None; out.append(dict(id=d['id'], how='стена по оси до стен по сторонам', м=round(ends[0].distance(ends[1]) / pxm, 2))); continue
        u = ((b_[0] - a_[0]) / lng, (b_[1] - a_[1]) / lng); h = T / 2
        p1 = (round(a_[0] + u[0] * h, 2), round(a_[1] + u[1] * h, 2)); p2 = (round(b_[0] - u[0] * h, 2), round(b_[1] - u[1] * h, 2))
        at = dict(tmpl); at['id'] = 'wall-b-u%d' % st['стена_под_проёмом']
        M.add('rooms', dict(kind='wall', id=at['id'], attrs=at, subs=[dict(pts=[p1, p2], arcs={}, closed=False)]))
        st['стена_под_проёмом'] += 1; lines = None; out.append(dict(id=d['id'], how='на стене %.0f %% — стена под проёмом' % (100 * f)))
    log('проёмы без стены (КМ-3): %s' % dict(st)); return out


def body_union(M):
    parts = []
    for e in M.els(('room', 'wall', 'glass', 'window')):
        sw = float(e['attrs'].get('stroke-width') or 0)
        if not stroked(e) or sw <= 0: continue
        for s in e['subs']:
            P = dense(s)
            if len(P) < 2: continue
            parts.append(LineString(P + ([P[0]] if s['closed'] else [])).buffer(sw / 2, cap_style=3 if e['kind'] == 'wall' else 2, join_style=2))
    for e in M.els('column'):
        if len(e['subs'][0]['pts']) >= 3: parts.append(Polygon(dense(e['subs'][0])).buffer(0))
    return unary_union(parts) if parts else Polygon()


def reseat(M, T, log):
    """проём на своей стене после правок осей: по сечению тела стены через свой центр — глубина = сечению, центр — на его середине;
    направление — по стене, если повёрнут к ней больше чем на 2°; ширина не меняется (П3-5)"""
    B = body_union(M); st = collections.Counter(); segs = []
    for e in M.els(('room', 'wall', 'glass', 'window')):
        if not stroked(e): continue
        for s in e['subs']:
            P = dense(s); P = P + ([P[0]] if s['closed'] else [])
            for i in range(len(P) - 1):
                if math.dist(P[i], P[i + 1]) > 1: segs.append(LineString([P[i], P[i + 1]]))
    tr = STRtree(segs) if segs else None
    for d in M.els('door'):
        Q = [tuple(v) for v in d['subs'][0]['pts']]
        if len(Q) != 4: continue
        D = Polygon(Q); c = np.array(D.centroid.coords[0]); e1 = np.subtract(Q[1], Q[0]); e2 = np.subtract(Q[2], Q[1])
        if np.linalg.norm(e1) < 1e-6 or np.linalg.norm(e2) < 1e-6: continue
        if np.linalg.norm(e1) >= np.linalg.norm(e2): u, w, h = e1 / np.linalg.norm(e1), np.linalg.norm(e1), np.linalg.norm(e2)
        else: u, w, h = e2 / np.linalg.norm(e2), np.linalg.norm(e2), np.linalg.norm(e1)
        best = None
        for j in (tr.query(D.buffer(1.0)) if tr is not None else []):
            g = segs[int(j)]; L = g.intersection(D.buffer(1.0)).length
            p, q = np.array(g.coords[0]), np.array(g.coords[-1]); v = (q - p) / np.linalg.norm(q - p)
            if abs(float(np.dot(v, u))) < math.cos(math.radians(12)): continue
            if best is None or L > best[0]: best = (L, v)
        if best is not None:
            v = best[1] if np.dot(best[1], u) > 0 else -best[1]
            if math.degrees(math.acos(min(1.0, abs(float(np.dot(v, u)))))) > 2.0: u = v; st['повёрнут'] += 1
        n = np.array([-u[1], u[0]])
        sec = LineString([tuple(c - n * 3 * T), tuple(c + n * 3 * T)]).intersection(B)
        parts = [sec] if sec.geom_type == 'LineString' else [g for g in getattr(sec, 'geoms', []) if g.geom_type == 'LineString']
        parts = [g for g in parts if g.length > 0 and g.distance(Point(c)) < 2.0]
        if not parts: st['без_стены'] += 1; continue
        g = min(parts, key=lambda g: g.distance(Point(c))); th = g.length; mid = np.array(g.interpolate(0.5, normalized=True).coords[0])
        if th > 2.6 * T: st['сечение_толще_2T'] += 1; continue                 # угол или стык стен — сечения нет, проём не трогать
        off = float(np.dot(mid - c, n)); cc = c + n * off
        if abs(off) <= 0.3 and abs(th - h) <= 0.3 and best is None: continue
        hw, hh = w / 2, th / 2
        R = [tuple(np.round(cc + u * hw + n * hh, 2)), tuple(np.round(cc - u * hw + n * hh, 2)), tuple(np.round(cc - u * hw - n * hh, 2)), tuple(np.round(cc + u * hw - n * hh, 2))]
        if abs(off) > 0.3 or abs(th - h) > 0.3: st['переставлен'] += 1
        d['subs'] = [dict(pts=R, arcs={}, closed=True)]
    log('проёмы по сечению стены (П3-5): %s' % dict(st)); return dict(st)


# ------------------------------------------------------------------ П3-2, КМ-5: размер колонны по телу плана (перенос colsize.py v03)
def colsize(M, C, log):
    """колонна или короб сжимается на d px (0…12), при котором контур ложится на тело стены плана: доля контура на теле растёт на 0,2
    и больше и доходит до 0,9; свободная стена и стекло, кончавшиеся на прежней грани, продлеваются до новой (№89)"""
    if C.body is None: log('колонны по телу плана (П3-2): маски нет — пропуск'); return {}
    def onbody(L):
        P = list(L.coords); tot = on = 0.0
        for i in range(len(P) - 1): tot += math.dist(P[i], P[i + 1]); on += C.body_len(P[i], P[i + 1])
        return on / tot if tot else 0.0
    st = collections.Counter(); out = []
    for e in list(M.els('column')):
        if len(e['subs'][0]['pts']) < 3: continue
        Bc = Polygon(dense(e['subs'][0])).buffer(0)
        if Bc.is_empty or Bc.geom_type != 'Polygon': continue
        row = []
        for d in range(0, 13):
            Bd = Bc.buffer(-d, join_style=2)
            if Bd.is_empty or Bd.geom_type != 'Polygon': break
            row.append(onbody(Bd.exterior))
        if not row: continue
        best = int(np.argmax(row))
        if best == 0 or row[best] < 0.9 or row[best] - row[0] < 0.2: st['как_у_моста'] += 1; continue
        Bn = Bc.buffer(-best, join_style=2).simplify(0.2); old = Bc.exterior
        e['subs'] = [dict(pts=[tuple(round(c, 2) for c in v) for v in list(Bn.exterior.coords)[:-1]], arcs={}, closed=True)]
        n_ext = 0
        for w in M.els(('wall', 'glass')):
            for s in w['subs']:
                P = s['pts']
                if len(P) < 2: continue
                for end in (0, -1):
                    p = P[end]; q = P[1] if end == 0 else P[-2]
                    if old.distance(Point(p)) > 1.0: continue
                    dx, dy = p[0] - q[0], p[1] - q[1]; L = math.hypot(dx, dy)
                    if L < 1e-6: continue
                    X = LineString([p, (p[0] + dx / L * (best + 3), p[1] + dy / L * (best + 3))]).intersection(Bn.exterior)
                    pts = [X] if X.geom_type == 'Point' else [g for g in getattr(X, 'geoms', []) if g.geom_type == 'Point']
                    if pts: g = min(pts, key=lambda g: g.distance(Point(p))); P[end] = (round(g.x, 2), round(g.y, 2)); n_ext += 1
        st['сжато'] += 1; out.append(dict(id=e['id'], px=best, м=round(best / C.pxm, 3), на_теле=[round(row[0], 2), round(row[best], 2)], стен_продлено=n_ext))
    log('колонны по телу плана (П3-2): %s' % dict(st)); return dict(сводка=dict(st), список=out)


# ------------------------------------------------------------------ П3-11, КМ-10: стекло плана на ребре помещения (перенос fixes_r1.glass_from_sheet v03)
def glass_from_plan(M, glass_segs, pxm, log, share=0.6, tol=5.0, max_deg=8.0):
    """ребро помещения с обводкой, вдоль которого стекло плана (в 5 px, параллельно ± 8°) покрывает ≥ 60 % его длины вне проёмов,
    а стекла карты на нём нет, — стекло карты по ребру; цепочка рёбер — одна линия"""
    S = [g for g in glass_segs if g.length >= 3]
    if not S: log('стекло плана на рёбрах (П3-11): стекла плана нет'); return 0
    St = STRtree(S)
    mg = unary_union([LineString(dense(q)) for e in M.els(('glass', 'window')) for q in e['subs'] if len(q['pts']) >= 2]).buffer(3.0)
    doors = unary_union([Polygon(e['subs'][0]['pts']).buffer(1.0) for e in M.els('door') if len(e['subs'][0]['pts']) >= 3])
    ang = lambda a, b: math.degrees(math.atan2(b[1] - a[1], b[0] - a[0])) % 180
    marked = {}
    for e in M.els('room'):
        if not stroked(e): continue
        for q in e['subs']:
            P = q['pts']; n = len(P)
            for k in range(n):
                if k in q['arcs']: continue
                a, b = tuple(P[k]), tuple(P[(k + 1) % n]); seg = LineString([a, b])
                if seg.length < 4: continue
                key = tuple(sorted([(round(a[0], 1), round(a[1], 1)), (round(b[0], 1), round(b[1], 1))]))
                if key in marked or seg.intersection(mg).length >= 0.5 * seg.length: continue
                th = ang(a, b)
                par = [S[int(j)] for j in St.query(seg.buffer(tol)) if S[int(j)].distance(seg) < tol and
                       min(abs(ang(*S[int(j)].coords[:2]) - th), 180 - abs(ang(*S[int(j)].coords[:2]) - th)) < max_deg]
                if not par: continue
                free = seg.difference(doors); L = free.length
                if L < 4: continue
                if free.intersection(unary_union([x.buffer(tol, cap_style=2) for x in par])).length >= share * L: marked[key] = (a, b)
    edges = list(marked.values()); used = [False] * len(edges); chains = []
    for i in range(len(edges)):
        if used[i]: continue
        used[i] = True; ch = [edges[i][0], edges[i][1]]; grow = True
        while grow:
            grow = False
            for j in range(len(edges)):
                if used[j]: continue
                a, b = edges[j]
                if math.dist(a, ch[-1]) < 0.3: ch.append(b); used[j] = True; grow = True
                elif math.dist(b, ch[-1]) < 0.3: ch.append(a); used[j] = True; grow = True
                elif math.dist(b, ch[0]) < 0.3: ch.insert(0, a); used[j] = True; grow = True
                elif math.dist(a, ch[0]) < 0.3: ch.insert(0, b); used[j] = True; grow = True
        chains.append(ch)
    tmpl = next(iter(M.els('glass')), None); n = 0
    at0 = dict(tmpl['attrs']) if tmpl is not None else {'fill': 'none', 'stroke': '#86C5FB', 'stroke-width': '4'}
    for k, ch in enumerate(chains):
        if LineString(ch).length < 0.4 * pxm: continue
        at = dict(at0); at['id'] = 'glasswall-b-sh%d' % k
        M.add('glass', dict(kind='glass', id=at['id'], attrs=at, subs=[dict(pts=[tuple(p) for p in ch], arcs={}, closed=False)])); n += 1
    log('стекло плана на рёбрах помещений (П3-11): линий %d' % n); return n


# ------------------------------------------------------------------ П3-10, КМ-2: порядок слоя rooms, стекло по проёму и коробу (перенос fixes_r1 v03)
def zorder(M, log):
    L = M.groups['rooms']; rank = {'room': 0, 'wall': 2, 'door': 3, 'column': 4}
    before = [e['id'] for e in L]
    rk = lambda e: (1 if stroked(e) else 0) if e['kind'] == 'room' else rank.get(e['kind'], 5)
    L.sort(key=rk)
    log('порядок слоя rooms: без обводки → с обводкой → стены → проёмы → колонны (переставлено %d)' % sum(1 for a, b in zip(before, [e['id'] for e in L]) if a != b))


def _cut_sub(s, cutter):
    P = [tuple(v) for v in s['pts']]; A = s['arcs']; n = len(P)
    out = []; cur = None if cutter.contains(Point(P[0])) else dict(pts=[P[0]], arcs={}, closed=False)
    def flush():
        nonlocal cur
        if cur is not None and len(cur['pts']) >= 2 and LineString(cur['pts']).length >= 2.0: out.append(cur)
        cur = None
    for k in range(n - 1):
        a, b = P[k], P[k + 1]
        if k in A:                                                       # дуга режется только целиком
            if cur is None: cur = dict(pts=[a], arcs={}, closed=False)
            cur['arcs'][len(cur['pts']) - 1] = A[k]; cur['pts'].append(b); continue
        seg = LineString([a, b]); X = seg.intersection(cutter)
        parts = [g for g in getattr(X, 'geoms', [X]) if g.geom_type == 'LineString' and g.length > 0.01]
        if not parts:
            if cur is None: cur = dict(pts=[a], arcs={}, closed=False)
            cur['pts'].append(b); continue
        iv = sorted((min(seg.project(Point(g.coords[0]), True), seg.project(Point(g.coords[-1]), True)),
                     max(seg.project(Point(g.coords[0]), True), seg.project(Point(g.coords[-1]), True))) for g in parts)
        pt = lambda t: (round(a[0] + (b[0] - a[0]) * t, 2), round(a[1] + (b[1] - a[1]) * t, 2)); t = 0.0
        for t0, t1 in iv:
            if t0 > t + 1e-6:
                if cur is None: cur = dict(pts=[pt(t)], arcs={}, closed=False)
                cur['pts'].append(pt(t0))
            flush(); t = max(t, t1)
        if t < 1 - 1e-6: cur = dict(pts=[pt(t), b], arcs={}, closed=False)
    flush()
    return out


def cut_glass(M, log):
    doors = [Polygon(e['subs'][0]['pts']).buffer(0.3, join_style=2) for e in M.els('door') if len(e['subs'][0]['pts']) >= 3]
    cols = [Polygon(dense(e['subs'][0])).buffer(0) for e in M.els('column') if len(e['subs'][0]['pts']) >= 3]
    st = collections.Counter()
    for name, cutter in (('проём', unary_union(doors) if doors else Polygon()), ('короб', unary_union(cols) if cols else Polygon())):
        if cutter.is_empty: continue
        for e in list(M.els('glass')):
            new = []
            for s in e['subs']:
                if s['closed'] or len(s['pts']) < 2: new.append(s); continue
                g = LineString(dense(s))
                if not g.intersects(cutter) or g.intersection(cutter).length < 0.5: new.append(s); continue
                new += _cut_sub(s, cutter); st[name] += 1
            e['subs'] = new
            if not new: M.remove(e['id']); st['стекло_снято_целиком'] += 1
    log('стекло режется по проёмам и коробам (П3-10): %s' % dict(st)); return dict(st)


def walls_to_boxes(M, pxm, log, reach_m=0.26):
    """конец свободной стены или стекла, не дошедший до грани короба колонны на ≤ 0,26 м по своему направлению, — до грани (№89)"""
    cols = [Polygon(dense(e['subs'][0])).buffer(0) for e in M.els('column') if len(e['subs'][0]['pts']) >= 3]
    n = 0; reach = reach_m * pxm
    for e in M.els(('wall', 'glass')):
        for s in e['subs']:
            P = s['pts']
            if s['closed'] or len(P) < 2: continue
            for end in (0, -1):
                p = P[end]; q = P[1] if end == 0 else P[-2]
                if any(Cc.distance(Point(p)) <= 2.5 for Cc in cols): continue
                near = [Cc for Cc in cols if Cc.distance(Point(p)) <= reach]
                L = math.dist(p, q)
                if not near or L < 1: continue
                u = ((p[0] - q[0]) / L, (p[1] - q[1]) / L); ray = LineString([p, (p[0] + u[0] * reach, p[1] + u[1] * reach)])
                pts = [h for Cc in near for h in getattr(ray.intersection(Cc.buffer(2.0, join_style=2).exterior), 'geoms', [ray.intersection(Cc.buffer(2.0, join_style=2).exterior)]) if h.geom_type == 'Point']
                if not pts: continue
                h = min(pts, key=lambda h: h.distance(Point(p)))
                if h.distance(Point(p)) < 0.8: continue
                hp = (round(h.x, 2), round(h.y, 2))
                if end == 0: P.insert(0, hp); s['arcs'] = {k + 1: v for k, v in s['arcs'].items()}
                else: P.append(hp)
                n += 1
    log('концы стен и стекла до грани короба (П3-1 п. 4): %d' % n); return n


def collinear_all(M, log, tol=0.5):
    """Ч-09: вершина с изломом < 0,5° — у свободной стены и стекла снимается всегда; у помещений — если коллинеарна во всех кольцах,
    где есть, и не конец стены или стекла (иначе это узел графа — Т-узел соседа)"""
    def turn(P, k, closed):
        n = len(P)
        if not closed and (k == 0 or k == n - 1): return None
        a, b, c = P[(k - 1) % n], P[k], P[(k + 1) % n]
        return abs((math.degrees(math.atan2(c[1] - b[1], c[0] - b[0]) - math.atan2(b[1] - a[1], b[0] - a[0])) + 180) % 360 - 180)
    n_del = 0
    for _ in range(5):
        changed = 0
        for e in M.els(('wall', 'glass')):
            for s in e['subs']:
                k = 1
                while k < len(s['pts']) - 1:
                    t = turn(s['pts'], k, False)
                    if (k - 1) not in s['arcs'] and k not in s['arcs'] and t is not None and t < tol: M._del_index(s, k); changed += 1; continue
                    k += 1
        cand = {}
        for e in M.els('room'):
            for s in e['subs']:
                P = s['pts']; n = len(P)
                for k in range(n):
                    if k in s['arcs'] or ((k - 1) % n) in s['arcs']: continue
                    t = turn(P, k, True)
                    if t is not None and (t < tol or t > 180 - tol): cand[(round(P[k][0], 1), round(P[k][1], 1))] = P[k]   # v012: и шип (разворот)
        for key, v in cand.items():
            hits = M.find(v, 0.3); ok = True
            for e, si, k in hits:
                s = e['subs'][si]; P = s['pts']
                if e['kind'] != 'room' or k in s['arcs'] or ((k - 1) % len(P)) in s['arcs']: ok = False; break
                t = turn(P, k, True)
                if t is None or tol <= t <= 180 - tol: ok = False; break
            if not ok: continue
            snap = BG.snapshot(M, {e['id'] for e, si, k in hits})
            for e, si, k in sorted(hits, key=lambda h: -h[2]):
                if len(e['subs'][si]['pts']) > 3: M._del_index(e['subs'][si], k)
            if not all(BG.valid2(M, e) for e, si, k in hits): BG.restore(M, snap); continue
            changed += 1
        for e in M.els('room'):                                                 # v012: шип (разворот на месте) — вершина-остриё снимается в этом кольце
            for s in e['subs']:
                k = 0
                while k < len(s['pts']) and len(s['pts']) > 3:
                    P = s['pts']; n = len(P)
                    if k in s['arcs'] or ((k - 1) % n) in s['arcs']: k += 1; continue
                    t = turn(P, k, True)
                    if t is None or t <= 180 - tol: k += 1; continue
                    snap = BG.snapshot(M, {e['id']}); M._del_index(s, k)
                    if not BG.valid2(M, e): BG.restore(M, snap); k += 1; continue
                    changed += 1
        for _ in range(50):                                                     # v012: ребро короче 0,8 px (Ч-09) — узлы сливаются во всех носителях (граф)
            G = BG.Graph(M); hit = None
            for e in M.els('room'):
                for s in e['subs']:
                    P = s['pts']; n = len(P)
                    for k in range(n):
                        j = (k + 1) % n
                        if k in s['arcs'] or math.dist(P[k], P[j]) >= 0.8 or BG.K(P[k]) == BG.K(P[j]): continue
                        a_, b_ = BG.K(P[k]), BG.K(P[j])
                        if b_ in G.arcv and a_ in G.arcv: continue
                        if b_ in G.arcv or b_ in G.fac: a_, b_ = b_, a_
                        hit = (a_, b_); break
                    if hit: break
                if hit: break
            if not hit: break
            a_, b_ = hit; ids = {q['id'] for (q, si, idx) in G.where[b_]} | {q['id'] for (q, si, idx) in G.where[a_]}; snap = BG.snapshot(M, ids)
            BG.apply_moves(M, G, {b_: G.pos[a_]}); BG.dedupe_ids(M, ids)
            if not all(len(M.get(i)['subs'][0]['pts']) >= 3 and BG.valid2(M, M.get(i)) for i in ids if M.get(i)['kind'] == 'room'):
                BG.restore(M, snap); break
            changed += 1
        n_del += changed
        if not changed: break
    zero = [e['id'] for e in M.els(('wall', 'glass')) if all(math.dist(v, e['subs'][0]['pts'][0]) < 0.8 for s_ in e['subs'] for v in s_['pts'])]
    for i in zero: M.remove(i)                                                  # v012: стена нулевой длины (конец доведён до короба) — «повтор точки» Ч-09
    log('Ч-09: коллинеарных вершин и шипов снято %d, стен нулевой длины %d' % (n_del, len(zero))); return n_del


# ------------------------------------------------------------------ КМ-11: самопроверка после всех шагов
def fix_overlaps(M, T, log):
    """КМ-11 (Ф1-2, ПК4-К10): тонкая накладка двух помещений (линза между двумя контурами одной стены после К6: ширина меньше 2T) —
    вычитается из помещения без дуг (из большего, если дуг нет у обоих): его контур идёт по контуру соседа; результат — один валидный
    контур, площадь меняется на площадь линзы; вложенное (≥ 98 % меньшего) и толстая накладка — не трогаются, остаются в отчёте"""
    R = [e for e in M.els('room') if len(e['subs']) == 1 and len(e['subs'][0]['pts']) >= 3]
    P = {e['id']: M.poly(e) for e in R}; tree = STRtree([P[e['id']] for e in R]); done, left = [], []
    for i, e in enumerate(R):
        for j in (int(j) for j in tree.query(P[e['id']]) if int(j) > i):
            f = R[j]; A, B_ = P[e['id']], P[f['id']]
            if not (A.is_valid and B_.is_valid): continue
            x = A.intersection(B_)
            if x.area <= 1.0: continue
            if x.area >= 0.98 * min(A.area, B_.area): continue                 # вложенное — не накладка (как Ч-14)
            if not x.buffer(-T).is_empty: left.append('%s × %s %.0f px² (толще 2T)' % (e['id'], f['id'], x.area)); continue   # линза двух контуров одной стены — до 2T
            order = sorted((g for g in (e, f) if not g['subs'][0]['arcs']), key=lambda g: -P[g['id']].area)
            ok = False
            for g in order:
                other = f if g is e else e; G0 = P[g['id']]; N = G0.difference(P[other['id']])
                if N.geom_type != 'Polygon' or not N.is_valid or N.is_empty or abs(G0.area - N.area - x.area) > 1.0 or len(N.interiors): continue
                pts = [(round(a, 3), round(b, 3)) for a, b in list(N.exterior.coords)[:-1]]
                if Polygon(pts).area * Polygon(G0.exterior.coords).area < 0: continue
                if G0.exterior.is_ccw != N.exterior.is_ccw: pts = pts[::-1]
                snap = BG.snapshot(M, {g['id']}); g['subs'][0]['pts'] = pts; g['subs'][0]['arcs'] = {}
                Q = M.poly(g)
                if Q.is_valid and abs(Q.area - N.area) < 1.0: P[g['id']] = Q; ok = True; done.append('%s − %s: %.0f px²' % (g['id'], other['id'], x.area)); break
                BG.restore(M, snap)
            if not ok: left.append('%s × %s %.0f px²' % (e['id'], f['id'], x.area))
    log('тонкие накладки помещений вычтены (КМ-11): %d %s; остались %s' % (len(done), done[:6], left[:6]))
    return dict(вычтено=done, осталось=left)


def round_and_fix(M, T, log, nd=2, pxm=None):
    """координаты — к точности записи SVG (0,01 px) в памяти, затем помещение, которое после округления самопересекается (вершина в
    сотых пикселя от чужого ребра того же контура), чинится снятием вершины у места пересечения во всех носителях (граф), если контуры
    валидны и площадь меняется меньше T²; иначе — громко в отчёт"""
    import re as _re
    from shapely.validation import explain_validity
    rep_ = 0
    for e in M.els():
        for s_ in e.get('subs') or []:
            s_['pts'] = [(round(v[0], nd), round(v[1], nd)) for v in s_['pts']]
            changed = True                                                      # повтор точки после округления (Ч-09) — снять
            while changed:
                changed = False; Q = s_['pts']; n = len(Q); m = n if s_['closed'] else n - 1
                for k in range(m):
                    if Q[k] == Q[(k + 1) % n] and n > (3 if s_['closed'] else 2): M._del_index(s_, (k + 1) % n); rep_ += 1; changed = True; break
    fixed, left = [], []
    lobe = max(2 * T * T, 0.25 * pxm * pxm) if pxm else 2 * T * T              # контур дважды проходит одну вершину (восьмёрка): петля меньше 0,25 м² — снять
    for e in M.els('room'):
        for s_ in e['subs']:
            for _ in range(5):
                P = s_['pts']; seen = {}; hit = None
                for i, v in enumerate(P):
                    if v in seen: hit = (seen[v], i); break
                    seen[v] = i
                if not hit: break
                j0, i1 = hit; L1 = P[j0:i1]; L2 = P[i1:] + P[:j0]
                a1 = Polygon(L1).area if len(L1) >= 3 else 0.0; a2 = Polygon(L2).area if len(L2) >= 3 else 0.0
                if min(a1, a2) >= lobe: break
                idx = list(range(j0 + 1, i1 + 1)) if a1 <= a2 else list(range(i1 + 1, len(P))) + list(range(0, j0 + 1))
                if len(P) - len(idx) < 3: break
                for k in sorted(idx, reverse=True): M._del_index(s_, k)
                fixed.append('%s: петля %.0f px² снята' % (e['id'], min(a1, a2)))
    for _ in range(20):
        bad = [e for e in M.els('room') if len(e['subs'][0]['pts']) >= 3 and not M.poly(e).is_valid]
        if not bad: break
        e = bad[0]; m = _re.search(r'\[(-?[\d.]+)\s+(-?[\d.]+)\]', explain_validity(M.poly(e)))
        if not m: left.append(e['id']); break
        x, y = float(m.group(1)), float(m.group(2)); G = BG.Graph(M); done = False
        cand = sorted((k for k in G.pos if abs(G.pos[k][0] - x) < 2 * T and abs(G.pos[k][1] - y) < 2 * T), key=lambda k: math.dist(G.pos[k], (x, y)))
        trials = [(k,) for k in cand] + [(k1, k2) for i1, k1 in enumerate(cand[:6]) for k2 in cand[i1 + 1:6] if k2 in G.nb[k1]]   # одна вершина, потом пара соседних
        for ks in trials:
            ids = set()
            for k in ks: ids |= {q['id'] for (q, si, idx) in G.where[k]}
            snap = BG.snapshot(M, ids); a0 = {i: M.poly(M.get(i)).area for i in ids if M.get(i)['kind'] == 'room'}
            if not all(BG._del_at(M, G, k) for k in ks): BG.restore(M, snap); continue
            ok = all(len(M.get(i)['subs'][0]['pts']) >= 3 and BG.valid2(M, M.get(i)) and abs(M.poly(M.get(i)).area - a0[i]) < 2 * T * T for i in a0)
            if ok: fixed.append('%s (%.1f,%.1f) вершин %d' % (e['id'], G.pos[ks[0]][0], G.pos[ks[0]][1], len(ks))); done = True; break
            BG.restore(M, snap)
        if not done and not e['subs'][0]['arcs'] and len(e['subs']) == 1:     # иначе — buffer(0): один контур, площадь — та же ± T²
            P0 = M.poly(e); Q = P0.buffer(0)
            if Q.geom_type == 'MultiPolygon': Q = max(Q.geoms, key=lambda g: g.area)
            if Q.geom_type == 'Polygon' and Q.is_valid and abs(Q.area - P0.area) < T * T and not len(Q.interiors):
                pts = [(round(a, nd), round(b, nd)) for a, b in list(Q.exterior.coords)[:-1]]
                snap = BG.snapshot(M, {e['id']}); e['subs'][0]['pts'] = pts
                if BG.valid2(M, e): fixed.append('%s buffer(0)' % e['id']); done = True
                else: BG.restore(M, snap)
        if not done: left.append(e['id']); break
    log('округление до 0,01 px: повторов точек снято %d; самопересечений починено %d %s; осталось %s' % (rep_, len(fixed), fixed[:6], left))
    return dict(повторов_снято=rep_, починено=fixed, осталось=left)


def selfcheck(M, pxm):
    R = [(e['id'], M.poly(e)) for e in M.els('room') if len(e['subs'][0]['pts']) >= 3]
    bad = [i for i, p in R if not p.is_valid]; ov = []; nest = []
    good = [(i, p) for i, p in R if p.is_valid]
    if good:
        tr = STRtree([p for i, p in good])
        for a_, (i, p) in enumerate(good):
            for j in tr.query(p):
                j = int(j)
                if j <= a_: continue
                x = p.intersection(good[j][1]).area
                if x > 2.0:
                    rec = dict(a=i, b=good[j][0], px2=round(x, 1), x=round(p.intersection(good[j][1]).centroid.x), y=round(p.intersection(good[j][1]).centroid.y))
                    (nest if x >= 0.98 * min(p.area, good[j][1].area) else ov).append(rec)   # вложенное (кабина в открытой зоне) — не накладка, как Ч-14
    return dict(помещений=len(R), невалидных=bad, накладок=len(ov), накладки=ov[:30], вложенных=len(nest))


# ------------------------------------------------------------------ весь ход
def run(svg_text, pxm, T, body=None, k=1, arcs=None, pk_px=None, bodies_px=None, glass_segs=None, log=None, no_ortho=False):
    """SVG моста -> SVG после шагов v03 (общими правилами) и отчёт шагов"""
    import time as _t
    L = []; log0 = log or _log_to(L); rep = collections.OrderedDict(); T0 = [_t.time()]
    def log(x):
        log0('%6.1f с  %s' % (_t.time() - T0[0], x)); print('%6.1f с  %s' % (_t.time() - T0[0], str(x)[:200]), file=sys.stderr, flush=True)
    M = BG.Model(svg_text); Cx = BG.Ctx(pxm, T, body=body, k=k)
    rep['короба'] = boxes_clean(M, pxm, T, log); rep['кольца_после_коробов'] = BG.clean_all(M, log=log)[0]
    rep['дуги'] = arcs_apply(M, arcs or [], log=log) if arcs else 'кривых плана нет (план 010 — дуги ломаными; К6 моста подбирает дуги сам)'
    BG.clean_all(M, log=log)
    rep['короба_ПК'] = pk_boxes(M, pk_px or [], bodies_px or [], pxm, T, log)
    rep['стены_в_санузле_и_проёме'], rep['двери_кабин_сняты'] = short_walls(M, pxm, log)
    if not no_ortho:
        BG.set_axes(M, Cx, log)
        rep['прореживание'] = BG.thin_deg2(M, Cx, log); BG.clean_all(M, log=log)
        nl = 0; fl = set()
        for p in range(3):
            d = BG.straighten(M, Cx, log, failed=fl); nl += d; BG.collinear(M, log=lambda x: None)
            if not d: break
        rep['прямая_по_пучку'] = nl; BG.clean_all(M, log=log)
        tot = 0; failed = set()
        for it in range(6):
            a_ = 0
            for p in range(6):
                d = BG.step(M, Cx, log, failed); a_ += d
                if not d: break
            b_ = 0
            for p in range(4):
                d = BG.step3(M, Cx, log, failed); b_ += d
                if not d: break
            BG.clean_all(M, log=log); tot += a_ + b_
            if a_ + b_ == 0: break
        rep['косые_операций'] = tot; rep['коллинеарных'] = BG.collinear(M, log)
        rep['косых_осталось'] = len(BG.oblique_edges(M, Cx))
    rep['проёмы_без_стены'] = doors_without_wall(M, pxm, T, log)
    rep['проёмы_по_сечению'] = reseat(M, T, log)
    rep['колонны_по_плану'] = colsize(M, Cx, log)
    rep['стекло_плана_на_рёбрах'] = glass_from_plan(M, glass_segs or [], pxm, log)
    zorder(M, log); rep['стекло_разрезано'] = cut_glass(M, log); BG.clean_all(M, log=log)
    rep['концы_до_короба'] = walls_to_boxes(M, pxm, log)
    rep['накладки_вычтены'] = fix_overlaps(M, T, log)
    rep['Ч-09_коллинеарных'] = collinear_all(M, log)
    nA, npoly = count_arcs(M); rep['дуг_A'] = nA; rep['дуг_ломаных'] = npoly
    rep['округление'] = round_and_fix(M, T, log, pxm=pxm)
    collinear_all(M, lambda x: log('после округления: ' + str(x)))
    rep['самопроверка'] = selfcheck(M, pxm)
    return M.to_svg(), rep, L


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('svg'); ap.add_argument('out'); ap.add_argument('--px-per-m', type=float, required=True); ap.add_argument('--T', type=float, default=6.0)
    ap.add_argument('--report'); ap.add_argument('--no-ortho', action='store_true')
    a = ap.parse_args()
    s, rep, L = run(open(a.svg, encoding='utf-8').read(), a.px_per_m, a.T, no_ortho=a.no_ortho)
    open(a.out, 'w', encoding='utf-8').write(s)
    if a.report: json.dump(dict(rep, журнал=L), open(a.report, 'w', encoding='utf-8'), ensure_ascii=False, indent=1, default=str)
    print(json.dumps(rep, ensure_ascii=False, default=str)[:3000])


if __name__ == '__main__': main()
