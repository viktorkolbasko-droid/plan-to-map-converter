"""bridge_graph.py — общий граф носителей карты по мосту (мост 0.33, код карты v012; перенос кода прохода карты клиент Б v03, 08.10.2026).

Носители геометрии SVG моста — помещения (room-*), свободные стены (wall-*), стекло (glasswall-*), витраж (window-*); проёмы (door-*)
и колонны (column-*) — отдельно. Операция над вершиной идёт во всех носителях сразу: общая вершина остаётся общей (один граф осей,
map/rules/40 §2.3). Каждая правка геометрии — одна операция с откатом (try_op): контуры валидны, накладки не растут, новой щели нет,
длина рёбер на теле стены плана не падает, проёмы не уходят со стены, новых рёбер короче T нет (П3-3 п. 3).
Тело стены плана — растр DXF моста (тела стен, стекло, витраж, колонны), а не тушь листа: мост берёт геометрию только из DXF.
Координаты — px карты."""
import re, math, copy, collections
import xml.etree.ElementTree as ET
import numpy as np
from shapely.geometry import Polygon, LineString, Point
from shapely.ops import unary_union

SVGNS = 'http://www.w3.org/2000/svg'
ET.register_namespace('', SVGNS)
TOK = re.compile(r'[MLAZHVmlazhv]|-?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?')
CARRIERS = ('room', 'wall', 'glass', 'window')


def fmt(v):
    s = ('%.2f' % v).rstrip('0').rstrip('.')
    return '0' if s in ('-0', '') else s


def parse_d(d):
    t = TOK.findall(d); i = 0; subs = []; cur = None; cmd = None; pos = (0.0, 0.0)
    while i < len(t):
        if re.match(r'[A-Za-z]', t[i]):
            cmd = t[i]; i += 1
            if cmd in 'Zz':
                cur['closed'] = True; continue
        if cmd == 'M':
            pos = (float(t[i]), float(t[i + 1])); i += 2
            cur = dict(pts=[pos], arcs={}, closed=False); subs.append(cur); cmd = 'L'
        elif cmd == 'L':
            pos = (float(t[i]), float(t[i + 1])); i += 2; cur['pts'].append(pos)
        elif cmd == 'H':
            pos = (float(t[i]), pos[1]); i += 1; cur['pts'].append(pos)
        elif cmd == 'V':
            pos = (pos[0], float(t[i])); i += 1; cur['pts'].append(pos)
        elif cmd == 'A':
            rx, ry, rot, la, sw, x, y = t[i:i + 7]; i += 7
            cur['arcs'][len(cur['pts']) - 1] = (float(rx), float(ry), float(rot), int(float(la)), int(float(sw)))
            pos = (float(x), float(y)); cur['pts'].append(pos)
        else:
            raise ValueError('unsupported path command %s' % cmd)
    for s in subs:                                   # замкнутое кольцо: повтор первой точки в конце — снять
        if s['closed'] and len(s['pts']) > 1 and math.dist(s['pts'][0], s['pts'][-1]) < 1e-6:
            last = len(s['pts']) - 2
            if last in s['arcs']: s['arcs'][last] = s['arcs'].pop(last)
            s['pts'].pop()
    return subs


def d_of(subs):
    out = []
    for s in subs:
        P = s['pts']; n = len(P)
        if not n: continue
        out.append('M%s %s' % (fmt(P[0][0]), fmt(P[0][1])))
        m = n if s['closed'] else n - 1
        for k in range(m):
            q = P[(k + 1) % n]
            if s['closed'] and k == n - 1:
                if k in s['arcs']:
                    a = s['arcs'][k]; out.append('A%s %s %s %d %d %s %s' % (fmt(a[0]), fmt(a[1]), fmt(a[2]), a[3], a[4], fmt(q[0]), fmt(q[1])))
                break
            if k in s['arcs']:
                a = s['arcs'][k]; out.append('A%s %s %s %d %d %s %s' % (fmt(a[0]), fmt(a[1]), fmt(a[2]), a[3], a[4], fmt(q[0]), fmt(q[1])))
            else:
                out.append('L%s %s' % (fmt(q[0]), fmt(q[1])))
        if s['closed']: out.append('Z')
    return ' '.join(out)


def arc_points(p, q, a, step=2.0):
    """дуга SVG (окружность, rx = ry) p -> q -> промежуточные точки (без p и q)"""
    rx, ry, rot, la, sw = a; r = rx
    x1, y1 = p; x2, y2 = q
    dx, dy = (x1 - x2) / 2, (y1 - y2) / 2; d2 = dx * dx + dy * dy
    if d2 < 1e-12: return []
    r = max(r, math.sqrt(d2))
    f = math.sqrt(max(0.0, (r * r - d2) / d2)) * (-1 if la == sw else 1)
    cx = (x1 + x2) / 2 + f * dy; cy = (y1 + y2) / 2 - f * dx
    t1 = math.atan2(y1 - cy, x1 - cx); t2 = math.atan2(y2 - cy, x2 - cx); dt = t2 - t1
    if sw and dt < 0: dt += 2 * math.pi
    if not sw and dt > 0: dt -= 2 * math.pi
    n = max(2, int(abs(dt) * r / step) + 1)
    return [(cx + r * math.cos(t1 + dt * k / n), cy + r * math.sin(t1 + dt * k / n)) for k in range(1, n)]


def dense(sub):
    P = sub['pts']; n = len(P); out = []
    m = n if sub['closed'] else n - 1
    for k in range(m):
        out.append(P[k])
        if k in sub['arcs']: out += arc_points(P[k], P[(k + 1) % n], sub['arcs'][k])
    if not sub['closed'] and n: out.append(P[-1])
    return out


def kind_of(eid):
    return ('room' if eid.startswith('room-') else 'wall' if eid.startswith('wall-') else 'door' if eid.startswith('door-')
            else 'column' if eid.startswith('column-') else 'glass' if eid.startswith('glasswall-') else 'window' if eid.startswith('window-') else 'raw')


class Model:
    """SVG моста как правимая модель: группы, элементы, кольца и ломаные носителей"""
    def __init__(self, svg_text):
        root = ET.fromstring(svg_text)
        self.root_attrib = dict(root.attrib); self.groups = {}; self.order = []; self.log = []
        for g in root:
            tag = g.tag.split('}')[1]
            if tag != 'g':
                self.order.append(('raw', ET.tostring(g, encoding='unicode').replace(' xmlns="%s"' % SVGNS, ''))); continue
            gid = g.get('id'); self.order.append(('g', gid)); els = []
            for e in g:
                etag = e.tag.split('}')[1]; at = dict(e.attrib); eid = at.get('id', ''); kind = kind_of(eid)
                if etag == 'path' and kind != 'raw':
                    subs = parse_d(at.pop('d')); els.append(dict(kind=kind, id=eid, attrs=at, subs=subs))
                else:
                    els.append(dict(kind='raw', id=eid, xml=ET.tostring(e, encoding='unicode').replace(' xmlns="%s"' % SVGNS, '')))
            self.groups[gid] = els
            if g.attrib.get('display'): self.groups[gid + '#attrs'] = dict(g.attrib)

    def els(self, kind=None):
        for gid, L in self.groups.items():
            if gid.endswith('#attrs'): continue
            for e in L:
                if kind is None or e['kind'] == kind or (isinstance(kind, tuple) and e['kind'] in kind): yield e

    def get(self, eid):
        for e in self.els():
            if e['id'] == eid: return e
        raise KeyError(eid)

    def poly(self, e):
        return Polygon(dense(e['subs'][0]))

    def find(self, at, tol=1.0, kinds=CARRIERS):
        hits = []
        for e in self.els(kinds):
            for si, s in enumerate(e['subs']):
                for k, v in enumerate(s['pts']):
                    if math.dist(v, at) <= tol: hits.append((e, si, k))
        return hits

    def _del_index(self, s, k):
        n = len(s['pts']); arcs = {}
        for i, a in s['arcs'].items():
            if i == k or (i == (k - 1) % n and s['closed']) or (i == k - 1): continue    # дуги, касающиеся вершины, — снимаются
            arcs[i - 1 if i > k else i] = a
        s['pts'].pop(k); s['arcs'] = arcs

    def remove(self, eid):
        for g, L in self.groups.items():
            if isinstance(L, list):
                for e in list(L):
                    if e['id'] == eid: L.remove(e); return True
        raise KeyError(eid)

    def add(self, gid, el):
        self.groups[gid].append(el); return el

    def to_svg(self):
        out = ['<svg %s>' % ' '.join('%s="%s"' % (k, v) for k, v in self.root_attrib.items() if not k.startswith('{'))]
        if 'xmlns' not in self.root_attrib: out[0] = out[0].replace('<svg ', '<svg xmlns="%s" ' % SVGNS, 1)
        for kind, v in self.order:
            if kind == 'raw': out.append(v); continue
            gid = v; L = self.groups[gid]; ga = self.groups.get(gid + '#attrs')
            if ga and ga.get('display') == 'none' and not L:
                out.append('<g id="%s" display="none"/>' % gid); continue
            if not L: out.append('<g id="%s"/>' % gid); continue
            out.append('<g id="%s">' % gid)
            for e in L:
                if e['kind'] == 'raw': out.append(e['xml']); continue
                at = dict(e['attrs']); at.pop('id', None)
                a = ' '.join('%s="%s"' % (k, str(val).replace('"', '&quot;')) for k, val in at.items() if k != 'd')
                out.append('<path id="%s" d="%s" %s/>' % (e['id'], d_of(e['subs']), a))
            out.append('</g>')
        out.append('</svg>')
        return '\n'.join(out)


def stroked(e): return (e['attrs'].get('stroke') or 'none') != 'none'


# ------------------------------------------------------------------ гигиена колец (перенос rings.py v03)
def _area(pts): return Polygon(pts).area if len(pts) >= 3 else 0.0


def clean_ring(s, eps=0.3, log=None, rid=''):
    """повторы, шип туда-обратно, разворот на 180°, перетяжка (кольцо дважды через одну точку): остаётся бо́льшая петля"""
    if not s['closed'] or s['arcs']: return 0
    P = [tuple(v) for v in s['pts']]; ch = 0; changed = True
    while changed and len(P) > 3:
        changed = False; n = len(P)
        for k in range(n):
            if math.dist(P[k], P[(k + 1) % n]) <= eps: P.pop((k + 1) % n); changed = True; ch += 1; break
        if changed: continue
        n = len(P)
        for k in range(n):
            if math.dist(P[(k - 1) % n], P[(k + 1) % n]) <= eps:
                for i in sorted([k, (k + 1) % n], reverse=True): P.pop(i)
                changed = True; ch += 1; break
        if changed: continue
        n = len(P)
        for k in range(n):
            a, b, c = P[(k - 1) % n], P[k], P[(k + 1) % n]
            u = (b[0] - a[0], b[1] - a[1]); v = (c[0] - b[0], c[1] - b[1]); nu, nv = math.hypot(*u), math.hypot(*v)
            if nu > 1e-9 and nv > 1e-9 and (u[0] * v[0] + u[1] * v[1]) / (nu * nv) < -0.9998: P.pop(k); changed = True; ch += 1; break
        if changed: continue
        n = len(P)
        for i in range(n):
            for j in range(i + 2, n):
                if i == 0 and j == n - 1: continue
                if math.dist(P[i], P[j]) <= eps:
                    A = P[i:j]; B = P[j:] + P[:i]; keep = A if _area(A) >= _area(B) else B
                    if log: log('перетяжка %s: петля %.0f px² снята' % (rid, min(_area(A), _area(B))))
                    P = keep; changed = True; ch += 1; break
            if changed: break
    s['pts'] = P
    return ch


def clean_all(M, log=print):
    n = 0
    for e in M.els('room'):
        for s in e['subs']: n += clean_ring(s, log=log, rid=e['id'])
    bad = [e['id'] for e in M.els('room') if len(e['subs'][0]['pts']) < 3 or not M.poly(e).is_valid]
    return n, bad


def dedupe(M, eps=1e-6, kinds=CARRIERS):
    for e in M.els(kinds):
        for s in e['subs']:
            changed = True
            while changed:
                changed = False; P = s['pts']; n = len(P); m = n if s['closed'] else n - 1
                for k in range(m):
                    if math.dist(P[k], P[(k + 1) % n]) <= eps and n > (3 if s['closed'] else 2):
                        M._del_index(s, (k + 1) % n); changed = True; break


# ------------------------------------------------------------------ общий граф и операции с откатом (перенос ortho2.py v03)
def angd(p, q): return math.degrees(math.atan2(q[1] - p[1], q[0] - p[0])) % 180
def adf(u, v): return min(abs(u - v) % 180, 180 - abs(u - v) % 180)
def K(v): return (round(v[0], 3), round(v[1], 3))


class Ctx:
    """параметры правки: px/м, T, маска тела стены плана (растр k, uint8) и оси плана (как Ч-32: до трёх сильных)"""
    def __init__(self, pxm, T, body=None, k=1, lim_m=0.8):
        self.pxm, self.T, self.k, self.LIM = pxm, T, k, lim_m * pxm
        self.body = None
        if body is not None:
            import cv2
            self.body = cv2.dilate((body > 0).astype(np.uint8), np.ones((2 * k + 1, 2 * k + 1), np.uint8)) > 0   # тело ± 1 px карты
        self.AX = [0.0]; self.DIRS = [0.0, 90.0]

    def body_len(self, p, q):
        """длина отрезка p-q (px карты), лежащая на теле стены плана (± 1 px)"""
        L = math.dist(p, q)
        if L < 1e-6 or self.body is None: return 0.0
        n = max(2, int(L) + 1); H, W = self.body.shape; on = 0
        for t in range(n):
            x = (p[0] + (q[0] - p[0]) * t / (n - 1)) * self.k; y = (p[1] + (q[1] - p[1]) * t / (n - 1)) * self.k
            xi, yi = int(x), int(y)
            if 0 <= xi < W and 0 <= yi < H and self.body[yi, xi]: on += 1
        return L * on / n

    def offax(self, t): return min(min((t - a) % 90, 90 - (t - a) % 90) for a in self.AX)

    def area_ok(self, M, rid):
        """КМ-4: площадь помещения после правки косых — в 0,5 % от площади до правки (или в T²/2 у малых), накопленно, а не на операцию"""
        A0 = getattr(self, 'A0', None)
        if not A0 or rid not in A0: return True
        a = M.poly(M.get(rid)).area; return abs(a - A0[rid]) <= max(0.005 * A0[rid], self.T * self.T / 2)


def plan_axes(M):
    """оси плана — как Ч-32 приёмки: направления прямых рёбер mod 90 с долей длины ≥ 5 %, до четырёх"""
    h = np.zeros(180)
    for e in M.els(('room', 'wall', 'window')):
        for s in e['subs']:
            P = s['pts']; n = len(P); m = n if s['closed'] else n - 1
            for i in range(m):
                if i in s['arcs']: continue
                p, q = P[i], P[(i + 1) % n]; L = math.dist(p, q)
                if L > 0: h[int(round(math.degrees(math.atan2(q[1] - p[1], q[0] - p[0])) % 90 * 2)) % 180] += L
    tot, ax = h.sum(), []
    while tot and len(ax) < 4:
        j = int(np.argmax(h)); w = [(j + d) % 180 for d in range(-6, 7)]
        if h[w].sum() < 0.05 * tot: break
        ang = np.angle(np.sum(h[w] * np.exp(1j * np.radians(np.array(w) * 2.0)))) / 4; ax.append(math.degrees(ang) % 90); h[w] = 0
    return ax or [0.0]


def set_axes(M, C, log=None):
    C.A0 = {e['id']: M.poly(e).area for e in M.els('room')}            # КМ-4: площади до правки косых — мера ± 0,5 %
    C.AX = plan_axes(M)[:3]                                   # четвёртая ось на пороге 5 % меняется от правки к правке — правим по трём сильным
    C.DIRS = sorted({round(a % 180, 2) for a in C.AX} | {round((a + 90) % 180, 2) for a in C.AX})
    if log: log('оси плана: ' + ', '.join('%.1f°' % a for a in C.AX))
    return C.AX


class Graph:
    def __init__(self, M):
        self.M = M; self.nb = collections.defaultdict(set); self.arcv = set(); self.fac = set(); self.where = collections.defaultdict(list)
        for e in M.els(CARRIERS):
            for si, s in enumerate(e['subs']):
                P = s['pts']; n = len(P); m = n if s['closed'] else n - 1
                for k, v in enumerate(P):
                    self.where[K(v)].append((e, si, k))
                    if e['kind'] == 'window': self.fac.add(K(v))
                for k in range(m):
                    a, b = K(P[k]), K(P[(k + 1) % n]); self.nb[a].add(b); self.nb[b].add(a)
                    if k in s['arcs']: self.arcv |= {a, b}
        self.pos = {K(v): tuple(v) for e in M.els(CARRIERS) for s in e['subs'] for v in s['pts']}
        self.doorfix = set()                                  # концы рёбер носителей под проёмом — неподвижны (Ч-19)
        doors = [Polygon(e['subs'][0]['pts']).buffer(1.0) for e in M.els('door') if len(e['subs'][0]['pts']) >= 3]
        dtree = None
        if doors:
            from shapely.strtree import STRtree
            dtree = STRtree(doors)
        for e in M.els(CARRIERS):
            for s in e['subs']:
                P = s['pts']; n = len(P); m = n if s['closed'] else n - 1
                for k in range(m):
                    if dtree is None: break
                    seg = LineString([P[k], P[(k + 1) % n]])
                    for j in dtree.query(seg):
                        D = doors[int(j)]
                        if seg.intersects(D) and seg.intersection(D).length > 3: self.doorfix |= {K(P[k]), K(P[(k + 1) % n])}; break

    def deg(self, k): return len(self.nb[k])
    def fixed(self, k): return k in self.arcv or k in self.fac or k in self.doorfix or self.deg(k) >= 3


def oblique_edges(M, C):
    out = []; seen = set()
    for e in M.els(CARRIERS):
        if e['kind'] == 'window': continue
        for s in e['subs']:
            P = s['pts']; n = len(P); closed = s['closed']; m = n if closed else n - 1
            for i in range(m):
                if i in s['arcs']: continue
                p, q = P[i], P[(i + 1) % n]; L = math.dist(p, q)
                if L < 0.8 or L > C.LIM: continue
                t = angd(p, q)
                if C.offax(t) < 8: continue
                cont = (closed or i > 0) and ((i - 1) % n not in s['arcs']) and adf(angd(P[i - 1], p), t) < 6
                cont = cont or ((closed or i + 2 < n) and ((i + 1) % n not in s['arcs']) and adf(angd(q, P[(i + 2) % n]), t) < 6)
                key = tuple(sorted([K(p), K(q)]))
                if cont or key in seen: continue
                seen.add(key); out.append((key, e['id']))
    return out


def line_x(p1, d1, p2, d2):
    den = d1[0] * d2[1] - d1[1] * d2[0]
    if abs(den) < 1e-9: return None
    t = ((p2[0] - p1[0]) * d2[1] - (p2[1] - p1[1]) * d2[0]) / den
    return (p1[0] + t * d1[0], p1[1] + t * d1[1])


def foot(p, a, d):
    L2 = d[0] ** 2 + d[1] ** 2
    if L2 < 1e-12: return (a[0], a[1])                                   # направление нулевой длины (повтор точки) — основание в самой точке
    t = ((p[0] - a[0]) * d[0] + (p[1] - a[1]) * d[1]) / L2
    return (a[0] + t * d[0], a[1] + t * d[1])


def snapshot(M, ids): return {i: copy.deepcopy(M.get(i)['subs']) for i in ids}


def restore(M, snap):
    for i, subs in snap.items(): M.get(i)['subs'] = subs


def pts_bbox(e):
    xs = [v[0] for s_ in e['subs'] for v in s_['pts']]; ys = [v[1] for s_ in e['subs'] for v in s_['pts']]
    return (min(xs), min(ys), max(xs), max(ys)) if xs else (0.0, 0.0, -1.0, -1.0)


def _bb_hit(a, b, pad=0.0): return a[0] - pad <= b[2] and b[0] - pad <= a[2] and a[1] - pad <= b[3] and b[1] - pad <= a[3]


def overlap_of(M, rid):
    e0 = M.get(rid); P = M.poly(e0); tot = 0.0
    if not P.is_valid: return None
    bb = pts_bbox(e0)
    for e in M.els('room'):
        if e['id'] == rid or not _bb_hit(bb, pts_bbox(e), 2.0): continue
        Q = M.poly(e)
        if Q.is_valid: tot += P.intersection(Q).area
    return tot


def short_edges(M, ids, T):
    n_ = 0
    for i in ids:
        for s in M.get(i)['subs']:
            P = s['pts']; n = len(P); m = n if s['closed'] else n - 1
            for k in range(m):
                L = math.dist(P[k], P[(k + 1) % n])
                if 0.01 < L < T: n_ += 1
    return n_


def apply_moves(M, G, moves):
    ids = set()
    for k, to in moves.items():
        for (e, si, idx) in G.where[k]: e['subs'][si]['pts'][idx] = tuple(to); ids.add(e['id'])
    return ids


def dedupe_ids(M, ids, eps=0.01):
    for i in ids:
        for s in M.get(i)['subs']:
            changed = True
            while changed:
                changed = False; P = s['pts']; n = len(P); m = n if s['closed'] else n - 1
                for k in range(m):
                    if math.dist(P[k], P[(k + 1) % n]) <= eps and n > (3 if s['closed'] else 2): M._del_index(s, (k + 1) % n); changed = True; break


def local_cover(M, box):
    from shapely.geometry import box as B_
    W = B_(*box); ps = []
    for e in M.els('room'):
        if not _bb_hit(box, pts_bbox(e), 60.0): continue                 # дуга может выйти за рамку вершин — запас
        P = M.poly(e)
        if P.is_valid and P.intersects(W): ps.append(P.intersection(W))
    return unary_union(ps) if ps else W.buffer(0).difference(W)


def door_cover(M, box):
    """длина обведённых линий носителей внутри прямоугольников проёмов в окне (замена Ч-19: проём на стене)"""
    from shapely.geometry import box as B_
    W = B_(*box); tot = 0.0
    doors = [Polygon(e['subs'][0]['pts']).buffer(-0.5) for e in M.els('door') if len(e['subs'][0]['pts']) >= 3 and _bb_hit(box, pts_bbox(e), 2.0)]
    doors = [D for D in doors if D.intersects(W)]
    if not doors: return 0.0
    for e in M.els(CARRIERS):
        if e['kind'] == 'room' and not stroked(e): continue
        if not _bb_hit(box, pts_bbox(e), 60.0): continue
        for s_ in e['subs']:
            pts = dense(s_) + ([dense(s_)[0]] if s_['closed'] else [])
            if len(pts) < 2: continue
            L = LineString(pts)
            if not L.intersects(W): continue
            for D in doors: tot += L.intersection(D).length
    return tot


def edges_at(G, keys):
    E = set()
    for k in keys:
        for w in G.nb[k]: E.add(tuple(sorted([k, w])))
    return E


LAST_WHY = ''


def valid2(M, e):
    """контур валиден и после округления до точности записи SVG (0,01 px): касание себя в сотых пикселя — не валиден"""
    P = M.poly(e)
    if not P.is_valid or P.area < 1: return False
    if e['subs'][0]['arcs']: return True
    try: return Polygon([(round(x, 2), round(y, 2)) for x, y in P.exterior.coords]).is_valid
    except Exception: return False


def try_op(M, G, C, moves, why, log, allow_short=False):
    """одна операция над вершинами общего графа с откатом (П3-3 п. 3); allow_short — короткие рёбра на одной прямой допустимы (их снимает
    collinear: прямая по пучку)"""
    ids = set()
    for k in moves: ids |= {e['id'] for (e, si, idx) in G.where[k]}
    snap = snapshot(M, ids)
    rooms = [i for i in ids if M.get(i)['kind'] == 'room']
    ov0 = {r: overlap_of(M, r) for r in rooms}; se0 = short_edges(M, ids, C.T)
    pts = [G.pos[k] for k in moves] + list(moves.values())
    box = (min(p[0] for p in pts) - 70, min(p[1] for p in pts) - 70, max(p[0] for p in pts) + 70, max(p[1] for p in pts) + 70)
    cov0 = local_cover(M, box)
    E0 = edges_at(G, moves.keys()); b0 = sum(C.body_len(G.pos[a], G.pos[b]) for a, b in E0)
    newpos = dict(G.pos); newpos.update({k: tuple(v) for k, v in moves.items()})
    b1 = sum(C.body_len(newpos[a], newpos[b]) for a, b in E0)
    L0 = sum(math.dist(G.pos[a], G.pos[b]) for a, b in E0); L1 = sum(math.dist(newpos[a], newpos[b]) for a, b in E0)
    global LAST_WHY
    LAST_WHY = 'тело'
    if C.body is not None and L0 > 0 and L1 > 0 and b1 / L1 < b0 / L0 - 0.05 and b1 < b0 - 3.0: return False   # доля рёбер на теле стены плана падает (Ч-10); зигзаг -> прямая короче — не потеря
    dz = door_cover(M, box)
    apply_moves(M, G, moves); dedupe_ids(M, ids)
    ok = True
    if door_cover(M, box) < dz - 1.0: ok = False; LAST_WHY = 'проём'   # проём уходит со стены (Ч-19)
    if ok and cov0.difference(local_cover(M, box)).area > C.T * C.T / 4: ok = False; LAST_WHY = 'щель'   # новая щель между помещениями больше T²/4 (допуск Ч-14)
    if ok:
        for r in rooms:
            e = M.get(r)
            if len(e['subs'][0]['pts']) < 3: ok = False; LAST_WHY = 'контур'; break
            if not valid2(M, e): ok = False; LAST_WHY = 'контур'; break
            o1 = overlap_of(M, r)
            if o1 is None or (ov0[r] is not None and o1 > ov0[r] + 0.1): ok = False; LAST_WHY = 'накладка'; break   # +0,1 px² на операцию: допуск не копится
            if not C.area_ok(M, r): ok = False; LAST_WHY = 'площадь'; break
    if ok and not allow_short and short_edges(M, ids, C.T) > se0: ok = False; LAST_WHY = 'короткие'
    if not ok:
        restore(M, snap); return False
    log(why); return True


def step(M, C, log, failed=None):
    G = Graph(M); done = 0; seen = set(); LIM, T = C.LIM, C.T; failed = set() if failed is None else failed
    for (a, b), eid in oblique_edges(M, C):
        if a in seen or b in seen or ('s', a, b) in failed: continue
        u, v = a, b
        if u not in G.pos or v not in G.pos: continue
        pu, pv = G.pos[u], G.pos[v]; cand = []
        for (x, y) in ((u, v), (v, u)):
            px, py = G.pos[x], G.pos[y]; fx, fy = G.fixed(x), G.fixed(y)
            ox = [w for w in G.nb[x] if w != y]; oy = [w for w in G.nb[y] if w != x]
            if not fx and not fy and len(ox) == 1 and len(oy) == 1 and x < y:           # обе вершины свободны, по два ребра: фаска -> угол, уступ -> поперёк
                wx, wy = G.pos[ox[0]], G.pos[oy[0]]
                dx = (px[0] - wx[0], px[1] - wx[1]); dy = (py[0] - wy[0], py[1] - wy[1])
                if adf(angd(wx, px), angd(wy, py)) >= 15:
                    X = line_x(px, dx, py, dy)
                    if X and math.dist(X, px) <= LIM and math.dist(X, py) <= LIM: cand.append((math.dist(X, px) + math.dist(X, py), {x: X, y: X}, 'фаска → угол'))
                else:
                    f = foot(px, py, dy)
                    if math.dist(f, py) <= LIM and math.dist(f, px) >= T: cand.append((math.dist(f, py), {y: f}, 'уступ → поперёк'))
                    f2 = foot(py, px, dx)
                    if math.dist(f2, px) <= LIM and math.dist(f2, py) >= T: cand.append((math.dist(f2, px), {x: f2}, 'уступ → поперёк'))
            if fx and not fy and len(oy) == 1 and math.dist(G.pos[oy[0]], py) > 1e-6:      # x неподвижна — y скользит вдоль своего ребра
                wy = G.pos[oy[0]]; dy = (py[0] - wy[0], py[1] - wy[1]); f = foot(px, py, dy)
                if math.dist(f, py) <= LIM:
                    if math.dist(f, px) >= T: cand.append((math.dist(f, py), {y: f}, 'стык → поперёк'))
                    else: cand.append((math.dist(px, py), {y: px}, 'стык → в узел'))
                for w in ox:
                    pw = G.pos[w]; dxw = (px[0] - pw[0], px[1] - pw[1]); X = line_x(px, dxw, py, dy)
                    if X and math.dist(X, py) <= LIM and math.dist(X, px) >= T and C.offax(angd(pw, px)) < 8: cand.append((math.dist(X, py) + 0.5, {y: X}, 'стык → продолжение'))
            if not fx and len(ox) == 0 and G.deg(y) >= 2: cand.append((math.dist(px, py) + 5, {x: py}, 'хвост снят'))   # свободный конец ломаной
        ok_ = False
        for cost, moves, why in sorted(cand, key=lambda c: c[0]):
            if max(math.dist(G.pos[k], t) for k, t in moves.items()) < 0.05: continue      # нулевой сдвиг — не операция (иначе ход повторяется без конца)
            keys = set(moves) | {w for k in moves for w in G.nb[k]}; pos1 = dict(G.pos); pos1.update({k: tuple(t) for k, t in moves.items()})
            if why != 'хвост снят' and local_obl(G, C, keys, pos1) >= local_obl(G, C, keys, G.pos): continue   # косых рёбер у узла не меньше — ход бесполезен
            if try_op(M, G, C, moves, '%s %s (%.0f,%.0f)' % (why, eid, (pu[0] + pv[0]) / 2, (pu[1] + pv[1]) / 2), log):
                done += 1; seen |= {u, v} | set(moves) | {K(t) for t in moves.values()}; G = Graph(M); ok_ = True; break
        if not ok_: failed.add(('s', a, b))                         # все варианты откатились — ребро с теми же вершинами больше не пробовать
    return done


def _del_at(M, G, k):
    """снять вершину k (ключ графа) во всех носителях: индекс — поиском по координате (индексы where устаревают после снятий)"""
    ok = True
    for (e, si, idx) in G.where[k]:
        s_ = e['subs'][si]; P = s_['pts']; done = False
        for j in range(len(P) - 1, -1, -1):
            if K(P[j]) == k and len(P) > (3 if s_['closed'] else 2): M._del_index(s_, j); done = True; break
        ok = ok and done
    return ok


def _unlink(G, k):
    N = list(G.nb[k])
    if len(N) == 2: a, b = N; G.nb[a].discard(k); G.nb[b].discard(k); G.nb[a].add(b); G.nb[b].add(a)
    G.nb.pop(k, None); G.where.pop(k, None); G.pos.pop(k, None)


def collinear(M, log, tol=0.5):
    """вершина степени 2 с прямым продолжением (< tol°) — снимается во всех носителях (Ч-09); один граф, правка по месту"""
    n_ = 0; G = Graph(M)
    for k in list(G.nb.keys()):
        N = G.nb.get(k)
        if N is None or len(N) != 2 or G.fixed(k) or k not in G.pos: continue
        a, b = list(N)
        if a not in G.pos or b not in G.pos: continue
        pa, pb, pk = G.pos[a], G.pos[b], G.pos[k]
        if not (math.dist(pa, pk) < 0.01 or math.dist(pb, pk) < 0.01 or adf(angd(pa, pk), angd(pk, pb)) < tol): continue
        ids = {e['id'] for (e, si, idx) in G.where[k]}; snap = snapshot(M, ids)
        if not _del_at(M, G, k): restore(M, snap); continue
        if any(M.get(i)['kind'] == 'room' and (len(M.get(i)['subs'][0]['pts']) < 3 or not valid2(M, M.get(i))) for i in ids): restore(M, snap); continue
        _unlink(G, k); n_ += 1
    log('collinear removed %d' % n_); return n_


def is_oblique(C, p, q):
    L = math.dist(p, q)
    if L < 0.8 or L > C.LIM: return False
    return C.offax(angd(p, q)) >= 8


def local_obl(G, C, keys, pos):
    """косые рёбра у узлов keys при положениях pos; ребро, которое продолжает соседнее (± 6°, как Ч-32), — не косое"""
    n = 0; seen = set()
    for k in keys:
        for w in G.nb[k]:
            e = tuple(sorted([k, w]))
            if e in seen: continue
            seen.add(e)
            if e[0] in G.arcv and e[1] in G.arcv: continue
            p, q = pos[e[0]], pos[e[1]]
            if not is_oblique(C, p, q): continue
            t = angd(p, q); cont = False
            for x, y in ((e[0], e[1]), (e[1], e[0])):
                for z in G.nb[x]:
                    if z == y or z not in pos or math.dist(pos[z], pos[x]) < 0.8: continue
                    if adf(angd(pos[z], pos[x]), t) < 6: cont = True; break
                if cont: break
            if not cont: n += 1
    return n


def step3(M, C, log, failed=None):
    """узел стыка тоже двигается — вдоль одного из своих рёбер, если у его рёбер косых коротких меньше, а новых нет"""
    G = Graph(M); done = 0; seen = set(); maxd = 0.6 * C.pxm; failed = set() if failed is None else failed
    for (a, b), eid in oblique_edges(M, C):
        if a in seen or b in seen or a not in G.pos or b not in G.pos or ('3', a, b) in failed: continue
        cands = []
        for (x, y) in ((a, b), (b, a)):
            if x in G.arcv or x in G.fac: continue
            px, py = G.pos[x], G.pos[y]
            for w in G.nb[x]:
                if w == y: continue
                pw = G.pos[w]; dvec = (px[0] - pw[0], px[1] - pw[1])
                if math.hypot(*dvec) < 1e-6: continue
                for dd in C.DIRS:
                    r = math.radians(dd); X = line_x(px, dvec, py, (math.cos(r), math.sin(r)))
                    if X is None: continue
                    mv = math.dist(X, px)
                    if mv > maxd or mv < 0.05: continue
                    if 0.01 < math.dist(X, py) < C.T: continue
                    cands.append((mv, {x: X}))
                cands.append((math.dist(px, py) + 1.0, {x: py}))
        best = None
        for mv, moves in sorted(cands, key=lambda c: c[0]):
            keys = set(moves) | {w for k in moves for w in G.nb[k]}
            pos1 = dict(G.pos); pos1.update(moves)
            if local_obl(G, C, keys, pos1) >= local_obl(G, C, keys, G.pos): continue
            if try_op(M, G, C, moves, 'стык-узел %s (%.0f,%.0f) сдвиг %.1f px' % (eid, G.pos[a][0], G.pos[a][1], mv), log): best = moves; break
        if best: done += 1; seen |= {a, b} | set(best) | {K(t) for t in best.values()}; G = Graph(M)
        else: failed.add(('3', a, b))
    return done


def straighten(M, C, log, band=None, R_m=1.2, min_line_m=0.5, failed=None):
    """КМ-4 (П3-3, В2К-3): косой пучок — зигзаг двух контуров и линии стекла у одной прямой, которая не по осям плана (растр моста дал
    V-вмятины и линзы между носителями), — все узлы пучка (связные короткими рёбрами в R_m от косого ребра, в полосе band от прямой между
    двумя узлами пучка не короче min_line_m) — на эту прямую одной операцией с откатом (try_op: контуры валидны, накладки и щели не растут,
    проёмы на стене, тело стены плана); узлы дуг, фасада и под проёмом не двигаются. Прямая из коротких рёбер подряд — не косые рёбра (Ч-32:
    соседи продолжают). -> число операций"""
    band = C.T if band is None else band; failed = set() if failed is None else failed
    G = Graph(M); done = 0; seen = set(); R = R_m * C.pxm; why = collections.Counter()
    for (a, b), eid in oblique_edges(M, C):
        if a in seen or b in seen or a not in G.pos or b not in G.pos or ('l', a, b) in failed: continue
        c = ((G.pos[a][0] + G.pos[b][0]) / 2, (G.pos[a][1] + G.pos[b][1]) / 2)
        S = {a, b}; Q = [a, b]
        while Q:
            x = Q.pop()
            for w in G.nb[x]:
                if w in S or w not in G.pos or math.dist(G.pos[w], c) > R or math.dist(G.pos[x], G.pos[w]) > C.LIM: continue
                S.add(w); Q.append(w)
        nodes = [k for k in S if k in G.pos]
        if len(nodes) < 3 or len(nodes) > 60: failed.add(('l', a, b)); why['узлов %s' % ('< 3' if len(nodes) < 3 else '> 60')] += 1; continue
        best = None
        for i, p in enumerate(nodes):
            pp = G.pos[p]
            for q in nodes[i + 1:]:
                pq = G.pos[q]; L = math.dist(pp, pq)
                if L < min_line_m * C.pxm: continue
                u = ((pq[0] - pp[0]) / L, (pq[1] - pp[1]) / L); inn = []
                for k in nodes:
                    v = G.pos[k]; dx, dy = v[0] - pp[0], v[1] - pp[1]; t = dx * u[0] + dy * u[1]
                    if abs(dx * u[1] - dy * u[0]) <= band and -band <= t <= L + band: inn.append(k)
                if a not in inn or b not in inn: continue
                sc = (len(inn), L)
                if best is None or sc > best[0]: best = (sc, pp, u, inn)
        if best is None: failed.add(('l', a, b)); why['нет прямой'] += 1; continue
        _, pp, u, inn = best; moves = {}; stuck = False
        for k in inn:
            v = G.pos[k]; t = (v[0] - pp[0]) * u[0] + (v[1] - pp[1]) * u[1]; f = (pp[0] + t * u[0], pp[1] + t * u[1])
            if k in G.arcv or k in G.fac or k in G.doorfix:
                if math.dist(v, f) > 1.0: stuck = True                  # неподвижный узел пучка не на прямой — частичная правка даст щель
                continue
            if math.dist(v, f) > 0.05: moves[k] = f
        if stuck: failed.add(('l', a, b)); why['неподвижный узел вне прямой'] += 1; continue
        if not moves: failed.add(('l', a, b)); why['двигать нечего'] += 1; continue
        keys = set(moves) | {w for k in moves for w in G.nb[k]}; pos1 = dict(G.pos); pos1.update(moves)
        if local_obl(G, C, keys, pos1) >= local_obl(G, C, keys, G.pos): failed.add(('l', a, b)); why['косых не меньше'] += 1; continue
        ang = math.degrees(math.atan2(u[1], u[0])) % 180
        if try_op(M, G, C, moves, 'прямая по пучку %s (%.0f,%.0f): узлов %d, %.1f°' % (eid, c[0], c[1], len(moves), ang), log, allow_short=True):
            done += 1; seen |= set(inn) | {K(t) for t in moves.values()}; G = Graph(M)
        else: failed.add(('l', a, b)); why['откат: ' + LAST_WHY] += 1
    log('прямая по пучку: операций %d, не сделано %s' % (done, dict(why))); return done


def thin_deg2(M, C, log, max_off=None, max_len_m=0.8):
    """В2К-3: прореживание — вершина степени 2 (не дуга, не фасад, не под проёмом), смещение от прямой соседей меньше T, хотя бы одно её
    ребро короче 0,8 м, — снимается во всех носителях, той же операцией с откатом (контуры валидны, накладки не растут, новой щели нет,
    проёмы не уходят со стены, доля хорды на теле стены плана — не меньше доли двух рёбер); один граф, правка по месту"""
    max_off = C.T if max_off is None else max_off; n = 0; G = Graph(M); bad = collections.Counter()
    cand = []
    for k, N in G.nb.items():
        if len(N) != 2 or G.fixed(k) or k not in G.pos: continue
        a, b = list(N); pa, pb, pk = G.pos[a], G.pos[b], G.pos[k]; L = math.dist(pa, pb)
        if L < 1e-6: continue
        off = abs((pb[0] - pa[0]) * (pk[1] - pa[1]) - (pb[1] - pa[1]) * (pk[0] - pa[0])) / L
        if off < max_off and min(math.dist(pa, pk), math.dist(pk, pb)) < max_len_m * C.pxm: cand.append((off, k))
    for off0, k in sorted(cand):
        N = G.nb.get(k)
        if N is None or len(N) != 2 or G.fixed(k): continue
        a, bb = list(N); pa, pb, pk = G.pos[a], G.pos[bb], G.pos[k]; L1 = math.dist(pa, pb)
        if L1 < 1e-6: continue
        off = abs((pb[0] - pa[0]) * (pk[1] - pa[1]) - (pb[1] - pa[1]) * (pk[0] - pa[0])) / L1
        if off >= max_off or min(math.dist(pa, pk), math.dist(pk, pb)) >= max_len_m * C.pxm: continue
        L0 = math.dist(pa, pk) + math.dist(pk, pb); b0 = C.body_len(pa, pk) + C.body_len(pk, pb); b1 = C.body_len(pa, pb)
        if C.body is not None and L0 > 0 and b1 < (b0 / L0) * L1 - 3.0: bad['тело'] += 1; continue
        ids = {e['id'] for (e, si, idx) in G.where[k]}; snap = snapshot(M, ids)
        rooms = [i for i in ids if M.get(i)['kind'] == 'room']; ov0 = {r: overlap_of(M, r) for r in rooms}
        box = (pk[0] - 70, pk[1] - 70, pk[0] + 70, pk[1] + 70); cov0 = local_cover(M, box); dz = door_cover(M, box)
        ok = _del_at(M, G, k)
        if not ok: bad['не_снять'] += 1
        if door_cover(M, box) < dz - 1.0: ok = False; bad['проём'] += 1
        if ok and cov0.difference(local_cover(M, box)).area > C.T * C.T / 4: ok = False; bad['щель'] += 1   # допуск Ч-14 — T²/4
        if ok:
            for r in rooms:
                e = M.get(r)
                if len(e['subs'][0]['pts']) < 3 or not valid2(M, e): ok = False; bad['контур'] += 1; break
                o1 = overlap_of(M, r)
                if o1 is None or (ov0[r] is not None and o1 > ov0[r] + 0.1): ok = False; bad['накладка'] += 1; break
                if not C.area_ok(M, r): ok = False; bad['площадь'] += 1; break
        if not ok: restore(M, snap); continue
        _unlink(G, k); n += 1
    log('прореживание вершин степени 2: снято %d, откатов %s' % (n, dict(bad))); return n
