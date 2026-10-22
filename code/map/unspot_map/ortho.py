"""micro_ortho: short oblique edges of room outlines -> straight walls (canon-proposals client A 4, G1-4; map/00 §3 step 7a, map/rules/40 §2.4).

Why: a graph of wall axes leaves traces at thick walls, columns and T-joints: chamfers 0.1-0.8 m, V-dents, oblique jogs.
On client A 4, run 2b, the zoom crops found 35 such places on v2 while Ch-07, Ch-08 and Ch-09 saw 3; after this step 3
remained and the agreement of walls with the designer rose by 2.6-2.8 p.p. Rule: a vertex only where the source has a
break (map/rules/40 §2.4). Check: acceptance_checks.py Ch-32 (oblique edges), crops K-10 at 4-6x.

micro_ortho() - the algorithm of run 2b (work/v2/geom.py, 02.10.2026) on a planar graph: rings {room: [[vertex key, ...]]},
pos {key: np.array}, arc_edges {(u, v): name}; tolerances of 2b were in pt of its sheet (1 pt = 0.063497 m) and are scaled
to the map unit (unit_m). Steps: manual line_set / moves (options), V-dents, tiny edges, Lambda-notches, chamfers -> corner,
jogs between parallel axis lines -> merge or perpendicular. A vertex moves only along its other edges; `fixed` - never.

run() - the same on a delivered SVG: room outlines of the group `rooms` (stroke #CBD2D6, straight segments; outlines with
curves stay as they are, their vertices are fixed). After the step the result is checked: every outline valid, no new
overlap of rooms, nothing beyond the shell, no new edge shorter than T. If a check fails, nothing is written and the
report names the reason - fix those places by hand from the Ch-32 list.

    python3 -m unspot_map.ortho plan.svg plan_ortho.svg --px-per-m 52.49 [--max-len-m 0.8] [--report r.json]
"""
import argparse, json, math, re
import xml.etree.ElementTree as ET
import numpy as np
from shapely.geometry import Polygon, Point
from shapely.ops import unary_union

WALL = '#CBD2D6'
NUM = r'[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?'


def _parse(d):
    """straight path -> [[(x, y), ...]] closed subpaths; None if the path has curves or open subpaths"""
    tok = re.findall(r'[A-Za-z]|' + NUM, d or ''); i, cmd, x, y, sub, out, start = 0, None, 0.0, 0.0, [], [], None
    na = dict(M=2, L=2, H=1, V=1)
    while i < len(tok):
        if tok[i].isalpha():
            cmd = tok[i]; i += 1
            if cmd in 'Zz':
                if sub: out.append(sub)
                sub, (x, y) = [], start or (x, y); continue
        C = (cmd or '?').upper()
        if C not in na: return None
        a = [float(v) for v in tok[i:i + na[C]]]; i += na[C]; rel = cmd.islower()
        if C == 'M':
            if sub: return None                                             # open subpath
            x, y = (x + a[0], y + a[1]) if rel else (a[0], a[1]); start = (x, y); sub = [(x, y)]; cmd = 'l' if rel else 'L'; continue
        if C == 'L': x, y = (x + a[0], y + a[1]) if rel else (a[0], a[1])
        elif C == 'H': x = x + a[0] if rel else a[0]
        elif C == 'V': y = y + a[0] if rel else a[0]
        sub.append((x, y))
    if sub: return None
    return [s[:-1] if len(s) > 1 and math.dist(s[0], s[-1]) < 1e-6 else s for s in out]


def _fmt(v):
    s = f'{v:.2f}'.rstrip('0').rstrip('.'); return '0' if s in ('-0', '') else s



def micro_ortho(rings, pos, arc_edges, mo, log=print, unit_m=0.063497, fixed=()):
    """v3 (по зумам приёмки v2, Z7–Z11): мелкие косые рёбра контуров — след графа осей у толстых стен и колонн.
    1) line_set — ручное: группа точной оси (рёбра одной координаты, связные) целиком на заданную координату;
    2) V-вмятина: вершина между двумя короткими рёбрами, соседи которых на одной прямой оси, — на эту прямую;
    3) фаска: цепочка до трёх коротких косых рёбер между двумя длинными непараллельными прямыми — в точку пересечения;
    4) уступ: короткое косое ребро между параллельными прямыми: короткий отрезок (< jog_short) — на соседнюю прямую;
       оба длинные — ребро перпендикулярно (ступенька остаётся, её видит Ч-08 и сверяет кроп).
    Вершина двигается, только если её прочие рёбра параллельны сдвигу (стена удлиняется или укорачивается, но не косит)."""
    MM = unit_m; K = 0.063497 / unit_m                       # допуски 2б заданы в pt листа (1 pt = 0,063497 м) -> единицы карты
    lim = mo.get('max_len_m', 0.8) / MM
    st = dict(line_set=0, vnotch=0, chamfer=0, jog_merge=0, jog_ortho=0, skipped=0)
    acts = []

    def ring_iter():
        for k, rr in rings.items():
            for ks in rr:
                yield k, ks

    def is_arc(u, v):
        return (u, v) in arc_edges or (v, u) in arc_edges

    def dist(u, v):
        return float(np.linalg.norm(pos[v] - pos[u]))

    def ang(u, v):
        d = pos[v] - pos[u]
        return math.degrees(math.atan2(d[1], d[0])) % 180

    def adiff(a, b):
        d = abs(a - b) % 180
        return min(d, 180 - d)

    def offax(t):
        return min(t % 90, 90 - t % 90)

    def run_len(ks, i, step):
        # длина прямой, к которой примыкает ребро (ks[i], ks[i+step]) — по кольцу, пока направление в пределах 0,5°
        n = len(ks); a, b = ks[i % n], ks[(i + step) % n]
        if a == b:
            return 0.0
        t = ang(a, b); L = dist(a, b); j = i + step
        for _ in range(n):
            u, w = ks[j % n], ks[(j + step) % n]
            if u == w or is_arc(u, w) or adiff(ang(u, w), t) > 0.5:
                break
            L += dist(u, w); j += step
        return L

    def nbrs():
        nb = {}
        for k, ks in ring_iter():
            n = len(ks)
            for i in range(n):
                a, b = ks[i], ks[(i + 1) % n]
                if a != b:
                    nb.setdefault(a, set()).add(b); nb.setdefault(b, set()).add(a)
        return nb

    def can_move(v, m, ignore, nb):
        if v in fixed: return False
        L = float(np.linalg.norm(m))
        if L < 1e-9:
            return True
        for w in nb.get(v, ()):
            if w in ignore:
                continue
            if is_arc(v, w):
                return False
            e = pos[w] - pos[v]; le = float(np.linalg.norm(e))
            if le < 1e-9:
                continue
            if le < lim and offax(math.degrees(math.atan2(e[1], e[0])) % 180) >= 8:
                continue                                  # соседнее короткое косое ребро — само дефект, его поправит следующий шаг
            s = abs(float(e[0] * m[1] - e[1] * m[0])) / (le * L)
            if s > 0.05 and L > mo.get('free_move', 0.3) * K:
                return False
        return True

    def merge(keep, gone):
        for k, ks in ring_iter():
            if gone not in ks:
                continue
            for i in range(len(ks)):
                if ks[i] == gone:
                    ks[i] = keep
            i = 0
            while len(ks) > 1 and i < len(ks):
                if ks[i] == ks[(i + 1) % len(ks)]:
                    del ks[i]
                else:
                    i += 1
        for (u, w) in list(arc_edges):
            if gone in (u, w):
                nm = arc_edges.pop((u, w)); u2 = keep if u == gone else u; w2 = keep if w == gone else w
                if u2 != w2:
                    arc_edges[(u2, w2)] = nm
        pos.pop(gone, None)

    # 1) ручные прямые
    for it in mo.get('line_set', []):
        ax = 1 if it['axis'] == 'y' else 0
        x0, y0 = it['pt']
        v0 = min(pos, key=lambda k: (pos[k][0] - x0) ** 2 + (pos[k][1] - y0) ** 2)
        if math.dist(pos[v0], (x0, y0)) > it.get('tol', 1.0):
            log('micro_ortho: line_set — нет вершины у', it['pt']); continue
        c0 = float(pos[v0][ax]); nb = nbrs(); grp = {v0}; stack = [v0]
        rng = it.get('range')
        while stack:
            v = stack.pop()
            for w in nb.get(v, ()):
                if w in grp or is_arc(v, w):
                    continue
                if abs(float(pos[w][ax]) - c0) < 0.02 * K and (rng is None or rng[0] <= float(pos[w][1 - ax]) <= rng[1]):
                    grp.add(w); stack.append(w)
        for v in grp:
            pos[v][ax] = it['to']
        st['line_set'] += 1; acts.append(('line_set', it['pt'], len(grp), round(c0, 2), it['to']))
    seen_ch = set()
    # 1а) ручные сдвиги вершин с слиянием: вершина в точку, где уже есть вершина, — одна вершина (без повтора в кольцах)
    for it in mo.get('moves', []):
        fx, fy = it['from']
        v = min(pos, key=lambda k: (pos[k][0] - fx) ** 2 + (pos[k][1] - fy) ** 2)
        if math.dist(pos[v], (fx, fy)) > 0.5:
            log('micro_ortho: move — нет вершины у', it['from']); continue
        tgt = [w for w in pos if w != v and math.dist(pos[w], it['to']) < 0.05]
        if tgt:
            merge(tgt[0], v); acts.append(('move_merge', it['from'], it['to']))
        else:
            pos[v] = np.array(it['to'], float); acts.append(('move', it['from'], it['to']))
        st['moves'] = st.get('moves', 0) + 1
    for it_pass in range(mo.get('passes', 6)):
        changed = False
        # 2) V-вмятины
        nb = nbrs()
        for k, ks in ring_iter():
            n = len(ks)
            if n < 5:
                continue
            for i in range(n):
                p, a, b, c, q = ks[i - 2], ks[i - 1], ks[i], ks[(i + 1) % n], ks[(i + 2) % n]
                if len({p, a, b, c, q}) < 5 or is_arc(a, b) or is_arc(b, c) or is_arc(p, a) or is_arc(c, q):
                    continue
                if dist(a, b) > lim or dist(b, c) > lim or dist(p, a) < 0.3 / MM or dist(c, q) < 0.3 / MM:
                    continue
                t1, t2 = ang(p, a), ang(c, q)
                if offax(t1) > 0.5 or offax(t2) > 0.5 or adiff(t1, t2) > 0.5:
                    continue
                ax = 1 if adiff(t1, 0) < 1 else 0; o = 1 - ax
                if abs(float(pos[a][ax] - pos[c][ax])) > 0.3 * K:
                    continue
                lv = float(pos[a][ax] + pos[c][ax]) / 2; d = float(pos[b][ax]) - lv
                if abs(d) < 0.05 * K or abs(d) > mo.get('vnotch_max', 4.0) * K:
                    continue
                if not (min(pos[a][o], pos[c][o]) < pos[b][o] < max(pos[a][o], pos[c][o])):
                    continue
                m = np.zeros(2); m[ax] = -d
                if not can_move(b, m, {a, c}, nb):
                    st['skipped'] += 1; acts.append(('vnotch_skip', [round(float(v), 2) for v in pos[b]])); continue
                acts.append(('vnotch', [round(float(v), 2) for v in pos[b]], round(-d, 2)))
                pos[b][ax] = lv; pos[a][ax] = lv; pos[c][ax] = lv
                st['vnotch'] += 1; changed = True
        # 2а) рёбра короче 0,5 pt — в одну вершину; «Λ»-надрез над коротким отрезком оси — на отрезок
        again = True; guard = 0
        while again and guard < 300:
            again = False; guard += 1; nb = nbrs()
            for k, ks in ring_iter():
                n = len(ks)
                for i in range(n):
                    a, b = ks[i], ks[(i + 1) % n]
                    if a == b or is_arc(a, b) or dist(a, b) >= mo.get('tiny_pt', 0.5) * K:
                        continue
                    m = (pos[b] - pos[a]) / 2
                    if can_move(a, m, {b}, nb) and can_move(b, -m, {a}, nb):
                        acts.append(('tiny', [round(float(v), 2) for v in pos[a]], round(dist(a, b), 2)))
                        pos[a] = pos[a] + m; merge(a, b); st['tiny'] = st.get('tiny', 0) + 1; changed = True; again = True
                        break
                if again:
                    break
        nb = nbrs()
        for k, ks in ring_iter():
            n = len(ks)
            if n < 5:
                continue
            for i in range(n):
                a, b, c = ks[i - 1], ks[i], ks[(i + 1) % n]
                if len({a, b, c}) < 3 or is_arc(a, b) or is_arc(b, c) or dist(a, c) > 1.2 / MM or dist(a, c) < 1e-6:
                    continue
                if dist(a, b) > lim or dist(b, c) > lim or offax(ang(a, b)) < 8 or offax(ang(b, c)) < 8 or offax(ang(a, c)) > 1.0:
                    continue
                u = (pos[c] - pos[a]) / dist(a, c); t = float((pos[b] - pos[a]) @ u)
                if not (0.05 * dist(a, c) < t < 0.95 * dist(a, c)):
                    continue
                q = pos[a] + t * u; dd = float(np.linalg.norm(pos[b] - q))
                if dd < 0.05 * K or dd > mo.get('vnotch_max', 4.0) * K:
                    continue
                if not can_move(b, q - pos[b], {a, c}, nb):
                    continue
                acts.append(('lambda', [round(float(v), 2) for v in pos[b]], round(dd, 2))); pos[b] = q
                st['lambda'] = st.get('lambda', 0) + 1; changed = True
        # 3) фаски
        again = True; guard = 0
        while again and guard < 300:
            again = False; guard += 1
            nb = nbrs()
            for k, ks in ring_iter():
                n = len(ks)
                if n < 5:
                    continue
                for i in range(n):
                    p, a = ks[i - 1], ks[i]
                    if p == a or is_arc(p, a) or run_len(ks, i, -1) < 0.5 / MM:
                        continue
                    t1 = ang(p, a); chain = [a]; total = 0.0; j = i; z = zn = None
                    for _ in range(3):
                        u, w = ks[j % n], ks[(j + 1) % n]
                        if u == w or is_arc(u, w):
                            break
                        L = dist(u, w)
                        if L < 1e-6 or L > lim or adiff(ang(u, w), t1) < 8:
                            break
                        chain.append(w); total += L; j += 1
                        nx = ks[(j + 1) % n]
                        if nx not in chain and not is_arc(w, nx) and run_len(ks, j, 1) >= 0.5 / MM:
                            t2 = ang(w, nx)
                            axis_pair = offax(t1) < 0.5 and offax(t2) < 0.5
                            if adiff(t1, t2) >= 20 and all(adiff(ang(chain[x], chain[x + 1]), t2) >= 8 and
                                                           offax(ang(chain[x], chain[x + 1])) >= 8 for x in range(len(chain) - 1)):
                                z, zn = w, nx
                                break
                    if z is None or total > mo.get('chamfer_max_m', 1.0) / MM:
                        continue
                    P1 = pos[a]; d1 = pos[a] - pos[p]; P2 = pos[z]; d2 = pos[zn] - pos[z]
                    den = float(d1[0] * d2[1] - d1[1] * d2[0])
                    if abs(den) < 1e-9:
                        continue
                    s = float((P2[0] - P1[0]) * d2[1] - (P2[1] - P1[1]) * d2[0]) / den
                    cpt = P1 + s * d1
                    tz = float((cpt - P2) @ d2) / float(d2 @ d2)
                    if s < -0.98 or tz > 0.98:
                        continue                                   # угол — за пределами соседних рёбер
                    if np.linalg.norm(cpt - pos[a]) > min(1.0 / MM, 2 * total) or np.linalg.norm(cpt - pos[z]) > min(1.0 / MM, 2 * total):
                        continue
                    sig = (tuple(np.round(pos[a], 2)), tuple(np.round(pos[z], 2)), tuple(np.round(cpt, 2)))
                    if sig in seen_ch:
                        continue
                    seen_ch.add(sig)
                    if float(np.linalg.norm(cpt - pos[a])) < 1e-6 and float(np.linalg.norm(cpt - pos[z])) < 1e-6 and len(chain) == 2:
                        continue
                    ma = can_move(a, cpt - pos[a], {p, chain[1]}, nb); mz = can_move(z, cpt - pos[z], {zn, chain[-2]}, nb)
                    mi = all(can_move(v, cpt - pos[v], set(chain), nb) for v in chain[1:-1])
                    if not mi or not (ma or mz):
                        key = ('chamfer_skip', [round(float(v), 2) for v in pos[a]])
                        if key not in acts:
                            st['skipped'] += 1; acts.append(key)
                        continue
                    acts.append(('chamfer', [round(float(v), 2) for v in pos[a]], [round(float(v), 2) for v in pos[z]], [round(float(v), 2) for v in cpt], len(chain) - 1, 'оба' if ma and mz else ('a' if ma else 'z')))
                    if ma and mz:                                  # оба конца — в угол
                        pos[a] = cpt.copy()
                        for v in chain[1:]:
                            merge(a, v)
                    elif ma:                                       # конец z — стык с другой стеной: остаётся, a — в угол
                        pos[a] = cpt.copy()
                        for v in chain[1:-1]:
                            merge(a, v)
                        if math.dist(pos[a], pos[z]) < 1e-6:
                            merge(z, a)
                    else:                                          # конец a — стык: остаётся, z — в угол
                        pos[z] = cpt.copy()
                        for v in chain[1:-1]:
                            merge(z, v)
                        if math.dist(pos[a], pos[z]) < 1e-6:
                            merge(a, z)
                    st['chamfer'] += 1; changed = True; again = True
                    break
                if again:
                    break
        # 4) уступы между параллельными прямыми
        nb = nbrs()
        for k, ks in ring_iter():
            n = len(ks)
            if n < 5:
                continue
            for i in range(n):
                p, a, b, q = ks[i - 1], ks[i], ks[(i + 1) % n], ks[(i + 2) % n]
                if len({p, a, b, q}) < 4 or is_arc(p, a) or is_arc(a, b) or is_arc(b, q):
                    continue
                L = dist(a, b)
                if L > lim or L < 1e-6 or dist(p, a) < 1e-6 or dist(b, q) < 1e-6:
                    continue
                t1, t2 = ang(p, a), ang(b, q)
                if adiff(t1, t2) > 1.0 or adiff(ang(a, b), t1) < 8 or offax(t1) > 0.5:
                    continue                                          # только прямые осей: косые стены сводит snap_dirs
                u = (pos[a] - pos[p]) / dist(p, a); nrm = np.array([-u[1], u[0]])
                off = float(nrm @ (pos[b] - pos[a])); along = float(u @ (pos[b] - pos[a]))
                if abs(off) < 0.05 * K or abs(off) > mo.get('jog_max', 5.5) * K or abs(along) < 0.05 * K:
                    continue
                l1, l2 = dist(p, a), dist(b, q)
                small = abs(off) < mo.get('t_pt', 1.8) * K               # уступ меньше T: перпендикуляр дал бы ребро < T (Ч-07)
                if small or min(l1, l2) < mo.get('jog_short_m', 0.45) / MM:
                    opts_ = [([p, a], off * nrm), ([b, q], -off * nrm)]
                    if l2 < l1:
                        opts_.reverse()
                    done = False
                    for mv, m in opts_:
                        if all(can_move(v, m, {p, a, b, q}, nb) for v in mv):
                            acts.append(('jog_merge', [round(float(v), 2) for v in pos[a]], round(off, 2)))
                            for v in mv:
                                pos[v] = pos[v] + m
                            st['jog_merge'] += 1; changed = True; nb = nbrs(); done = True
                            break
                    if done:
                        continue
                    if small:
                        key = ('jog_skip', [round(float(v), 2) for v in pos[a]])
                        if key not in acts:
                            st['skipped'] += 1; acts.append(key)
                        continue
                m = -along * u
                if can_move(b, m, {a, q}, nb):
                    acts.append(('jog_ortho', [round(float(v), 2) for v in pos[b]], round(off, 2))); pos[b] = pos[b] + m
                elif can_move(a, -m, {p, b}, nb):
                    acts.append(('jog_ortho', [round(float(v), 2) for v in pos[a]], round(off, 2))); pos[a] = pos[a] - m
                else:
                    key = ('jog_skip', [round(float(v), 2) for v in pos[a]])
                    if key not in acts:
                        st['skipped'] += 1; acts.append(key)
                    continue
                st['jog_ortho'] += 1; changed = True; nb = nbrs()
        if not changed:
            break
    for r in [k for k, rr in rings.items() if any(len(ks) < 3 for ks in rr)]:
        log('micro_ortho: вырожденное кольцо у', r)
    st['passes'] = it_pass + 1
    log('micro_ortho:', st)
    for a_ in acts:
        log('  ', a_)
    return st


def _graph(svg_in):
    ET.register_namespace('', 'http://www.w3.org/2000/svg')
    tree = ET.parse(svg_in); root = tree.getroot(); rooms = next((g for g in root if g.get('id') == 'rooms'), None)
    if rooms is None: raise SystemExit('нет группы rooms')
    els, fixed_pts, key, pos, rings, sw = [], [], {}, {}, {}, []
    def vid(p):
        k = (round(p[0] / 0.05), round(p[1] / 0.05))
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if (k[0] + dx, k[1] + dy) in key: return key[(k[0] + dx, k[1] + dy)]
        key[k] = len(pos); pos[len(pos)] = np.array(p, float); return key[k]
    for el in rooms.iter():
        tag = el.tag.split('}')[-1]
        if (el.get('stroke') or '').upper() != WALL or tag not in ('path', 'polygon'): continue
        if tag == 'path':
            sp = _parse(el.get('d'))
            if sp is None: fixed_pts += [(float(a), float(b)) for a, b in zip(*[iter(re.findall(NUM, el.get('d') or ''))] * 2)]; continue
        else:
            v = [float(z) for z in re.findall(NUM, el.get('points', ''))]; sp = [list(zip(v[::2], v[1::2]))]
        k = len(els); els.append((el, tag)); sw.append(float(el.get('stroke-width') or 0)); rings[k] = [[vid(p) for p in r] for r in sp]
    fixed = set()
    for p in fixed_pts:
        q = (round(p[0] / 0.05), round(p[1] / 0.05))
        fixed |= {key[(q[0] + dx, q[1] + dy)] for dx in (-1, 0, 1) for dy in (-1, 0, 1) if (q[0] + dx, q[1] + dy) in key}
    return tree, els, sw, rings, pos, fixed


def _check(rings, pos, sw, T):
    """outline polygons; (invalid, overlap px2 of rooms, area beyond the shell of rooms, edges shorter than T)"""
    P = {k: [Polygon([tuple(pos[i]) for i in r]) for r in rr if len(r) >= 3] for k, rr in rings.items()}
    inner = [g for k, gs in P.items() if sw[k] < 1.5 * T for g in gs]; bad = sum(not g.is_valid for gs in P.values() for g in gs)
    ov = 0.0
    for i, g in enumerate(inner):
        for h in inner[i + 1:]:
            if g.is_valid and h.is_valid and g.bounds[0] <= h.bounds[2] and h.bounds[0] <= g.bounds[2] and g.bounds[1] <= h.bounds[3] and h.bounds[1] <= g.bounds[3]:
                ov += g.intersection(h).area
    short = sum(1 for rr in rings.values() for r in rr for t in range(len(r)) if 0.8 <= float(np.linalg.norm(pos[r[(t + 1) % len(r)]] - pos[r[t]])) < T)
    return bad, ov, short


def run(svg_in, svg_out, px_per_m, max_len_m=0.8, mo=None, log=print):
    tree, els, sw, rings, pos, fixed = _graph(svg_in)
    T = float(np.median([w for w in sw if w > 0])) if sw else 6.0
    shell = unary_union([Polygon([tuple(pos[i]) for i in r]).buffer(0) for rr in rings.values() for r in rr if len(r) >= 3])
    ext = unary_union([q.exterior for q in getattr(shell, 'geoms', [shell])])
    fac = {i for i, p in pos.items() if ext.distance(Point(p)) < 0.5} | {i for k, rr in rings.items() if sw[k] >= 1.5 * T for r in rr for i in r}
    b0 = _check(rings, pos, sw, T); pos0 = {k: v.copy() for k, v in pos.items()}; rings0 = {k: [list(r) for r in rr] for k, rr in rings.items()}
    o = dict(max_len_m=max_len_m); o.update(mo or {}); o.setdefault('t_pt', T / (0.063497 * px_per_m))   # T карты в pt 2б: t_pt · K = T
    st = micro_ortho(rings, pos, {}, o, log=lambda *x: None, unit_m=1.0 / px_per_m, fixed=fixed | fac)
    b1 = _check(rings, pos, sw, T)
    sh1 = unary_union([Polygon([tuple(pos[i]) for i in r]).buffer(0) for k, rr in rings.items() if sw[k] < 1.5 * T for r in rr if len(r) >= 3])
    out_ = sh1.difference(shell.buffer(0.5)).area
    why = [w for w, c in (('невалидный контур', b1[0] > b0[0]), (f'накладки помещений {b1[1] - b0[1]:.1f} px²', b1[1] > b0[1] + 0.5),
                          (f'рёбра короче T: {b0[2]} -> {b1[2]}', b1[2] > b0[2]), (f'за оболочкой {out_:.1f} px²', out_ > 0.5)) if c]
    if why:
        rings.clear(); rings.update(rings0); pos.clear(); pos.update(pos0)
    for k, (el, tag) in enumerate(els):
        subs = [[pos[i] for i in r] for r in rings[k] if len(r) >= 3]
        if not subs: continue
        if tag == 'path': el.set('d', ' '.join('M' + 'L'.join(f'{_fmt(p[0])} {_fmt(p[1])}' for p in s) + 'Z' for s in subs))
        else: el.set('points', ' '.join(f'{_fmt(p[0])},{_fmt(p[1])}' for p in subs[0]))
    if not why: tree.write(svg_out, encoding='utf-8', xml_declaration=False)
    rep = dict(applied=not why, why=why, stat={k: v for k, v in st.items()}, T=T)
    log(json.dumps(rep, ensure_ascii=False)); return rep


def main():
    ap = argparse.ArgumentParser(description='micro_ortho: short oblique edges of room outlines -> straight walls')
    ap.add_argument('svg'); ap.add_argument('out'); ap.add_argument('--px-per-m', type=float, required=True)
    ap.add_argument('--max-len-m', type=float, default=0.8); ap.add_argument('--options', help='JSON: line_set, moves, passes, ... (2b)'); ap.add_argument('--report')
    a = ap.parse_args(); r = run(a.svg, a.out, a.px_per_m, a.max_len_m, json.load(open(a.options, encoding='utf-8')) if a.options else None)
    if a.report: json.dump(r, open(a.report, 'w', encoding='utf-8'), ensure_ascii=False, indent=1, default=float)
    raise SystemExit(0 if r['applied'] else 1)


if __name__ == '__main__':
    main()
