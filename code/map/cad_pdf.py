#!/usr/bin/env python3
"""DXF → векторный PDF со слоями OCG (И16; черновик чата исходников, 07.10.2026; к cad_intake.py).

Зачем: DWG клиента идёт дальше обычным маршрутом векторного листа со слоями — карта (map/rules/11) и инженерный план
(маршрут по слоям, модуль ocg/), — а не снимками экрана просмотрщика. Слой DXF → слой OCG с тем же именем.

Что переносится: линии, полилинии LWPOLYLINE и старые POLYLINE (дуги по выпуклости, ширина — толщиной линии; сетки граней —
видимыми рёбрами), дуги, окружности, эллипсы — кривыми Безье, как печатает AutoCAD (двери карта ищет по дугам), сплайны
(B-сплайн по узлам), штриховки (сплошные — заливкой, с узором — контуром), SOLID и 3DFACE, тексты TEXT, MTEXT, ATTRIB, выноски
LEADER, блоки — с масштабом, поворотом, зеркалом и вложенностью до 4 уровней; сущность блока на слое «0» и с цветом BYBLOCK
берёт слой и цвет вставки; размеры — их блоками; внешние ссылки, если их DXF дан (xrefs): слои — «ссылка|слой», как в AutoCAD.
Цвет — ACI или true color, 7 — чёрный; толщина — вес линии DXF в мм бумаги. Выключенные и замороженные слои не переносятся, как
не печатает их AutoCAD; их число — в отчёте. Подписи — встроенным шрифтом Nimbus Sans (латиница, кириллица; ширины знаков и
ToUnicode — текст извлекается), с выравниванием и поворотом DXF; знака нет в шрифте — «?». Не рисуются — 3D-тела ACIS (3DSOLID,
REGION: LibreDWG их геометрию не отдаёт), картинки, MULTILEADER, точки; их число по типам — not_drawn, слои тел — solid_layers.

Масштаб листа — 48,04 мм на pt, если единицы чертежа определены уверенно (cad_intake.py, cad.units): опорный масштаб маршрута
по слоям (plan/rules/40 §12, start_ocg.py), приведение не нужно. Единицы не определены — масштаб листа не известен
(mm_per_pt = None): длинная сторона самого большого вида — 3370 pt, как у A0; масштаб — по размерам на листе, как у любого PDF.
Лист — на каждый вид модели (cad.views); сущность — в вид, где её первая точка. Один проход по DXF, без загрузки в память.
Зависимости: numpy, pymupdf; цвет ACI — ezdxf.colors, если есть (иначе — основные 9 цветов и серый)."""
import math, os, re, time

import numpy as np

MM_PER_PT = 48.04                  # опорный масштаб маршрута по слоям: 1 pt листа = 48,04 мм натуры
A0_PT = 3370.0                     # единицы не определены: длинная сторона самого большого вида — 1189 мм, как у листа A0
MAX_PRIMS = 4_000_000              # примитивов на все листы не больше — память и размер PDF
MAX_DEPTH = 4
MARGIN_PT = 36
DRAWN = {'LINE', 'LWPOLYLINE', 'POLYLINE', 'ARC', 'CIRCLE', 'ELLIPSE', 'SPLINE', 'SOLID', 'TRACE', '3DFACE', 'LEADER', 'TEXT', 'ATTRIB',
         'MTEXT', 'INSERT', 'DIMENSION', 'HATCH'}   # прочее на видимых слоях — в отчёт, cad.pdf.not_drawn
SOLID_TYPES = {'3DSOLID', 'REGION', 'BODY', 'SURFACE', 'PLANESURFACE', 'EXTRUDEDSURFACE', 'REVOLVEDSURFACE', 'SWEPTSURFACE',
               'LOFTEDSURFACE', 'NURBSURFACE', 'MESH'}   # тела ACIS: LibreDWG их геометрию не отдаёт (у DWG 2013+ она в разделе AcDs)
MIN_TEXT_PT = 0.1                  # подпись ниже — вырождена (у 48,04 мм/pt это 5 мм натуры), не пишется
_FONT = []                         # Nimbus Sans из pymupdf: латиница и кириллица, ширины знаков и ToUnicode в PDF


def font():
    if not _FONT:
        import pymupdf
        f = pymupdf.Font('helv')
        _FONT.extend([f, {}])
    return _FONT


def gids(s):
    """строка → идентификаторы знаков шрифта (Identity-H); знака нет в шрифте — «?». -> (hex, все ли знаки есть)"""
    f, cache = font()
    out, ok = [], True
    for ch in s.replace('\t', ' '):
        g = cache.get(ch)
        if g is None:
            g = cache[ch] = f.has_glyph(ord(ch))
        if not g:
            ok = False; g = cache.get('?') or cache.setdefault('?', f.has_glyph(ord('?')))
        out.append('%04x' % g)
    return ''.join(out), ok
UNIT_MM = {'мм': 1.0, 'см': 10.0, 'дм': 100.0, 'м': 1000.0, 'дюйм': 25.4, 'фут': 304.8}
try:
    from ezdxf.colors import aci2rgb as _aci
    def aci_rgb(i):
        c = _aci(int(i)); return (c[0] / 255.0, c[1] / 255.0, c[2] / 255.0)
except Exception:                                                # noqa: BLE001 — без ezdxf: основные цвета
    _BASE = {1: (1, 0, 0), 2: (1, 1, 0), 3: (0, 1, 0), 4: (0, 1, 1), 5: (0, 0, 1), 6: (1, 0, 1), 7: (0, 0, 0), 8: (.5, .5, .5), 9: (.75, .75, .75)}
    def aci_rgb(i):
        return _BASE.get(int(i), (.4, .4, .4))


def color_of(aci, true=None):
    if true is not None:
        return ((true >> 16) & 255) / 255.0, ((true >> 8) & 255) / 255.0, (true & 255) / 255.0
    if aci in (7, 255) or aci is None:
        return (0.0, 0.0, 0.0)                                   # белый на чёрном экране — чёрный на бумаге
    rgb = aci_rgb(abs(aci))
    return (0.0, 0.0, 0.0) if rgb == (1.0, 1.0, 1.0) else rgb


def bulge_points(x0, y0, x1, y1, b, step_deg=10.0):
    """дуга полилинии по выпуклости b (тангенс четверти угла) — точки без начальной"""
    if abs(b) < 1e-9:
        return [(x1, y1)]
    ang = 4 * math.atan(b)
    dx, dy = x1 - x0, y1 - y0; chord = math.hypot(dx, dy)
    if chord < 1e-12:
        return [(x1, y1)]
    r = chord / (2 * math.sin(abs(ang) / 2))
    mx, my = (x0 + x1) / 2, (y0 + y1) / 2
    h = r * math.cos(ang / 2) * (1 if b > 0 else -1)            # от середины хорды к центру
    nx, ny = -dy / chord, dx / chord
    cx, cy = mx + nx * h, my + ny * h
    a0 = math.atan2(y0 - cy, x0 - cx)
    n = max(2, int(abs(math.degrees(ang)) / step_deg))
    return [(cx + r * math.cos(a0 + ang * i / n), cy + r * math.sin(a0 + ang * i / n)) for i in range(1, n + 1)]


def arc_points(cx, cy, r, a0, a1, step_deg=10.0):
    """дуга против часовой от a0 до a1 (градусы)"""
    if a1 <= a0:
        a1 += 360.0
    n = max(2, int((a1 - a0) / step_deg))
    return [(cx + r * math.cos(math.radians(a0 + (a1 - a0) * i / n)), cy + r * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]


def ellipse_points(cx, cy, mx, my, ratio, t0, t1, n=48):
    if t1 <= t0:
        t1 += 2 * math.pi
    k = max(4, int(n * (t1 - t0) / (2 * math.pi)))
    bx, by = -my * ratio, mx * ratio                             # малая полуось
    return [(cx + mx * math.cos(t) + bx * math.sin(t), cy + my * math.cos(t) + by * math.sin(t))
            for t in (t0 + (t1 - t0) * i / k for i in range(k + 1))]


def _bez_arc(P, D, t0, span):
    """дуга параметра t0 … t0 + span кривыми Безье по ≤ 90°: P(t) — точка, D(t) — производная. -> элементы ('c', …)"""
    n = max(1, math.ceil(abs(span) / (math.pi / 2) - 1e-9)); d = span / n; k = 4.0 / 3.0 * math.tan(d / 4)
    out, t = [], t0
    for _ in range(n):
        u = t + d
        (x0, y0), (x3, y3), (dx0, dy0), (dx3, dy3) = P(t), P(u), D(t), D(u)
        out.append(('c', x0 + k * dx0, y0 + k * dy0, x3 - k * dx3, y3 - k * dy3, x3, y3))
        t = u
    return out


def arc_bez(cx, cy, r, a0, a1):
    """дуга окружности против часовой от a0 до a1 (градусы) кривыми Безье, как печатает AutoCAD: [начало, ('c', …), …]"""
    if a1 <= a0:
        a1 += 360.0
    t0, span = math.radians(a0), math.radians(a1 - a0)
    P = lambda t: (cx + r * math.cos(t), cy + r * math.sin(t))
    D = lambda t: (-r * math.sin(t), r * math.cos(t))
    return [P(t0)] + _bez_arc(P, D, t0, span)


def ellipse_bez(cx, cy, mx, my, ratio, t0, t1):
    """эллипс по параметру t0 … t1 кривыми Безье"""
    if t1 <= t0:
        t1 += 2 * math.pi
    bx, by = -my * ratio, mx * ratio
    P = lambda t: (cx + mx * math.cos(t) + bx * math.sin(t), cy + my * math.cos(t) + by * math.sin(t))
    D = lambda t: (-mx * math.sin(t) + bx * math.cos(t), -my * math.sin(t) + by * math.cos(t))
    return [P(t0)] + _bez_arc(P, D, t0, t1 - t0)


def bulge_bez(x0, y0, x1, y1, b):
    """дуга полилинии по выпуклости кривыми Безье — элементы без начальной точки"""
    if abs(b) < 1e-9:
        return [(x1, y1)]
    ang = 4 * math.atan(b)
    dx, dy = x1 - x0, y1 - y0; chord = math.hypot(dx, dy)
    if chord < 1e-12:
        return [(x1, y1)]
    r = chord / (2 * math.sin(abs(ang) / 2))
    h = r * math.cos(ang / 2) * (1 if b > 0 else -1)
    cx, cy = (x0 + x1) / 2 - dy / chord * h, (y0 + y1) / 2 + dx / chord * h
    t0 = math.atan2(y0 - cy, x0 - cx)
    P = lambda t: (cx + r * math.cos(t), cy + r * math.sin(t))
    D = lambda t: (-r * math.sin(t), r * math.cos(t))
    out = _bez_arc(P, D, t0, ang)
    out[-1] = out[-1][:5] + (x1, y1)                              # конец — точно вершина полилинии
    return out


def end_of(el):
    """конечная точка элемента пути: (x, y) или ('c', x1, y1, x2, y2, x3, y3)"""
    return (el[5], el[6]) if len(el) == 7 else el


def bspline_points(ctrl, knots, deg, per_span=8):
    """B-сплайн по де Буру; без узлов или при ошибке — ломаная по управляющим точкам"""
    n = len(ctrl)
    if n < 2:
        return ctrl
    if deg < 1 or len(knots) != n + deg + 1:
        return ctrl
    lo, hi = knots[deg], knots[n]
    if hi <= lo:
        return ctrl
    out = []
    m = max(2, per_span * (n - deg))
    for i in range(m + 1):
        t = lo + (hi - lo) * i / m
        k = deg
        while k < n - 1 and knots[k + 1] <= t:
            k += 1
        d = [list(ctrl[j]) for j in range(k - deg, k + 1)]
        for r in range(1, deg + 1):
            for j in range(deg, r - 1, -1):
                den = knots[j + 1 + k - r] - knots[j + k - deg]
                a = 0.0 if den == 0 else (t - knots[j + k - deg]) / den
                d[j] = [(1 - a) * d[j - 1][0] + a * d[j][0], (1 - a) * d[j - 1][1] + a * d[j][1]]
        out.append(tuple(d[deg]))
    return out


MTEXT_CODES = re.compile(r'\\[ACcFfHhQqTtWwp][^;\\]*;|\\[LlOoKkN]|\\S[^;]*;|[{}]')
UNI_RE = re.compile(r'\\[Uu]\+([0-9A-Fa-f]{4})')
STACK_RE = re.compile(r'\\S([^;^#/]*)[\^#/]([^;]*);')


def mtext_clean(s):
    """коды MTEXT и TEXT: \\P — перевод строки, \\U+XXXX — знак, %%c %%d %%p — Ø ° ±; оформление (\\A \\H \\f \\p …, %%u %%o) — убрать"""
    s = UNI_RE.sub(lambda m: chr(int(m.group(1), 16)), s.replace('\\P', '\n').replace('\\~', ' '))
    s = STACK_RE.sub(lambda m: m.group(1) + '/' + m.group(2), s)            # \\S1^2; — дробь
    s = MTEXT_CODES.sub('', s)
    for a, b in (('%%c', 'Ø'), ('%%C', 'Ø'), ('%%d', '°'), ('%%D', '°'), ('%%p', '±'), ('%%P', '±'), ('%%u', ''), ('%%U', ''), ('%%o', ''), ('%%O', ''), ('%%%', '%')):
        s = s.replace(a, b)
    return s


def _f(v, d=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return d


def _i(v, d=0):
    try:
        return int(v)
    except (TypeError, ValueError):
        return d


def parse_entity(t, tags):
    """примитивы сущности в координатах её системы (OCS с зеркалом по z = −1 приведена): список
    ('poly', closed, [(x, y)…]) | ('fill', [[(x, y)…], …]) | ('text', x, y, h, rot, s, ha, va) | ('insert', name, x, y, sx, sy, rot)"""
    g = {}
    for c, v in tags:
        g.setdefault(c, []).append(v)
    first = lambda c, d=None: g[c][0] if c in g else d
    flip = _f(first(230, 1.0)) < 0                                # выдавливание (0, 0, −1) — зеркало по x
    fx = (lambda x: -x) if flip else (lambda x: x)
    out = []
    if t == 'LINE':
        out.append(('poly', False, [(fx(_f(first(10))), _f(first(20))), (fx(_f(first(11))), _f(first(21)))]))
    elif t == 'LWPOLYLINE':
        pts, cur = [], None
        for c, v in tags:
            if c == 10:
                cur = [fx(_f(v)), 0.0, 0.0]; pts.append(cur)
            elif c == 20 and cur is not None:
                cur[1] = _f(v)
            elif c == 42 and cur is not None:
                cur[2] = -_f(v) if flip else _f(v)
        closed = bool(_i(first(70, 0)) & 1)
        if len(pts) >= 2:
            poly = [(pts[0][0], pts[0][1])]
            seq = pts + ([pts[0]] if closed else [])
            for a, b in zip(seq[:-1], seq[1:]):
                poly.extend(bulge_bez(a[0], a[1], b[0], b[1], a[2]))
            wv = [_f(v) for v in g.get(40, []) + g.get(41, [])]
            width = _f(first(43, 0.0)) or (float(np.median(wv)) if wv and max(wv) > 0 else 0.0)   # ширина полилинии — полосой
            out.append(('poly', closed, poly, width) if width > 0 else ('poly', closed, poly))
    elif t == 'POLYLINE':
        out.extend(parse_polyline(tags, g, fx, flip))
    elif t in ('ARC', 'CIRCLE'):
        cx, cy, r = fx(_f(first(10))), _f(first(20)), _f(first(40))
        if r > 0:
            if t == 'CIRCLE':
                out.append(('poly', True, arc_bez(cx, cy, r, 0, 360)))
            else:
                a0, a1 = _f(first(50)), _f(first(51))
                if flip:
                    a0, a1 = 180 - a1, 180 - a0
                out.append(('poly', False, arc_bez(cx, cy, r, a0, a1)))
    elif t == 'ELLIPSE':
        cx, cy = _f(first(10)), _f(first(20)); mx, my = _f(first(11)), _f(first(21))
        out.append(('poly', False, ellipse_bez(cx, cy, mx, my, _f(first(40), 1.0), _f(first(41), 0.0), _f(first(42), 2 * math.pi))))
    elif t == 'SPLINE':
        ctrl = list(zip([_f(v) for v in g.get(10, [])], [_f(v) for v in g.get(20, [])]))
        fit = list(zip([_f(v) for v in g.get(11, [])], [_f(v) for v in g.get(21, [])]))
        pts = fit if len(fit) >= 2 else bspline_points(ctrl, [_f(v) for v in g.get(40, [])], _i(first(71, 3)))
        if len(pts) >= 2:
            out.append(('poly', bool(_i(first(70, 0)) & 1), pts))
    elif t in ('SOLID', 'TRACE', '3DFACE'):
        p = [(fx(_f(first(c))), _f(first(c + 10))) for c in (10, 11, 12, 13) if c in g]
        if len(p) == 4:
            p = [p[0], p[1], p[3], p[2]] if t != '3DFACE' else p
        if len(p) >= 3:
            out.append(('fill', [p]))
    elif t == 'LEADER':
        pts = list(zip([_f(v) for v in g.get(10, [])], [_f(v) for v in g.get(20, [])]))
        if len(pts) >= 2:
            out.append(('poly', False, pts))
    elif t in ('TEXT', 'ATTRIB'):
        s = ''.join(g.get(1, []))
        if s.strip() and not (_i(first(70, 0)) & 1 and t == 'ATTRIB'):           # невидимый атрибут — нет
            ha, va = _i(first(72, 0)), _i(first(74 if t == 'ATTRIB' else 73, 0))
            if ha in (3, 5):                                     # «по ширине» и «вписать» — от первой точки, влево
                ha, va = 0, 0
            x, y = (_f(first(11)), _f(first(21))) if (ha or va) and 11 in g else (_f(first(10)), _f(first(20)))
            out.append(('text', fx(x), y, _f(first(40), 1.0), _f(first(50), 0.0) * (-1 if flip else 1), mtext_clean(s), ha, va))
    elif t == 'MTEXT':
        s = mtext_clean(''.join(g.get(3, [])) + ''.join(g.get(1, [])))
        if s.strip():
            rot = _f(first(50), 0.0)
            if 11 in g:
                rot = math.degrees(math.atan2(_f(first(21)), _f(first(11))))
            att = _i(first(71, 1))
            out.append(('text', fx(_f(first(10))), _f(first(20)), _f(first(40), 1.0), rot, s, {1: 0, 4: 0, 7: 0, 2: 1, 5: 1, 8: 1}.get(att, 2),
                        {1: 3, 2: 3, 3: 3, 4: 2, 5: 2, 6: 2}.get(att, 1)))
    elif t == 'INSERT':
        out.append(('insert', first(2, '?'), fx(_f(first(10))), _f(first(20)), _f(first(41), 1.0) * (-1 if flip else 1), _f(first(42), 1.0),
                    _f(first(50), 0.0) * (-1 if flip else 1)))
    elif t == 'DIMENSION':
        if 2 in g:
            out.append(('insert', first(2), 0.0, 0.0, 1.0, 1.0, 0.0))
    elif t == 'HATCH':
        out.extend(parse_hatch(tags, fx))
    return out


def parse_polyline(tags, g, fx, flip):
    """старая полилиния POLYLINE с вершинами VERTEX: 2D (выпуклости) и 3D — ломаной по x, y; сетка граней (флаг 64) — видимыми
    рёбрами граней; сетка M × N (флаг 16) — строками и столбцами. Опорные точки сплайна (вершина с флагом 16) — не рисуются"""
    fl = _i(g.get(70, ['0'])[0])
    V = []
    for c, vt in tags:
        if c == -1:
            d = {}
            for cc, vv in vt:
                d.setdefault(cc, vv)
            V.append(d)
    out = []
    if fl & 64:
        coords = [(fx(_f(v.get(10))), _f(v.get(20))) for v in V if _i(v.get(70), 0) & 64]
        for v in V:
            vf = _i(v.get(70), 0)
            if vf & 128 and not vf & 64:
                idx = [_i(v.get(c), 0) for c in (71, 72, 73, 74) if _i(v.get(c), 0) != 0]
                for j in range(len(idx)):
                    a, b = idx[j], abs(idx[(j + 1) % len(idx)])
                    if 0 < a <= len(coords) and 0 < b <= len(coords) and a != b:     # отрицательный номер — ребро невидимо
                        out.append(('poly', False, [coords[a - 1], coords[b - 1]]))
        return out
    if fl & 16:
        m, n = _i(g.get(71, ['0'])[0]), _i(g.get(72, ['0'])[0])
        pts = [(fx(_f(v.get(10))), _f(v.get(20))) for v in V]
        if m > 0 and n > 0 and m * n == len(pts):
            out += [('poly', bool(fl & 32), pts[i * n:(i + 1) * n]) for i in range(m)]
            out += [('poly', bool(fl & 1), [pts[i * n + j] for i in range(m)]) for j in range(n)]
        return out
    pts = []
    for v in V:
        if _i(v.get(70), 0) & 16:
            continue
        b = 0.0 if fl & 8 else _f(v.get(42))
        pts.append([fx(_f(v.get(10))), _f(v.get(20)), -b if flip else b])
    closed = bool(fl & 1)
    if len(pts) >= 2:
        poly = [(pts[0][0], pts[0][1])]
        seq = pts + ([pts[0]] if closed else [])
        for a, b in zip(seq[:-1], seq[1:]):
            poly.extend(bulge_bez(a[0], a[1], b[0], b[1], a[2]))
        out.append(('poly', closed, poly))
    return out


def parse_hatch(tags, fx):
    """контуры штриховки: ломаные и рёбра (линия, дуга, эллипс, сплайн); сплошная — заливка, с узором — контур"""
    i, n = 0, len(tags)
    solid = False; paths = []
    while i < n and tags[i][0] != 91:
        if tags[i][0] == 70:
            solid = _i(tags[i][1]) == 1
        i += 1
    if i >= n:
        return []
    npath = _i(tags[i][1]); i += 1
    for _ in range(npath):
        while i < n and tags[i][0] != 92:
            i += 1
        if i >= n:
            break
        ptype = _i(tags[i][1]); i += 1
        pts = []
        if ptype & 2:                                            # ломаная
            hasb = closed = 0; nv = 0
            while i < n and tags[i][0] in (72, 73, 93):
                c, v = tags[i]
                if c == 72: hasb = _i(v)
                elif c == 73: closed = _i(v)
                elif c == 93: nv = _i(v)
                i += 1
            vs = []
            while i < n and len(vs) < nv and tags[i][0] in (10, 20, 42):
                c, v = tags[i]
                if c == 10: vs.append([fx(_f(v)), 0.0, 0.0])
                elif c == 20 and vs: vs[-1][1] = _f(v)
                elif c == 42 and vs: vs[-1][2] = _f(v)
                i += 1
                if len(vs) == nv and i < n and tags[i][0] == 20:
                    vs[-1][1] = _f(tags[i][1]); i += 1
                if len(vs) == nv and i < n and tags[i][0] == 42:
                    vs[-1][2] = _f(tags[i][1]); i += 1
            if vs:
                pts = [(vs[0][0], vs[0][1])]
                seq = vs + [vs[0]]
                for a, b in zip(seq[:-1], seq[1:]):
                    pts.extend(bulge_points(a[0], a[1], b[0], b[1], a[2] if hasb else 0.0))
        else:                                                    # рёбра
            ne = 0
            if i < n and tags[i][0] == 93:
                ne = _i(tags[i][1]); i += 1
            for _e in range(ne):
                while i < n and tags[i][0] != 72:
                    i += 1
                if i >= n:
                    break
                et = _i(tags[i][1]); i += 1
                e = {}; lst = {}
                while i < n and tags[i][0] not in (72, 92, 97, 75):
                    c, v = tags[i]
                    if c in (10, 20, 40):
                        lst.setdefault(c, []).append(v)
                    e.setdefault(c, v); i += 1
                if et == 1:
                    seg = [(fx(_f(e.get(10))), _f(e.get(20))), (fx(_f(e.get(11))), _f(e.get(21)))]
                elif et == 2:
                    a0, a1 = _f(e.get(50)), _f(e.get(51)); ccw = _i(e.get(73), 1)
                    if not ccw:
                        a0, a1 = 360 - a1, 360 - a0
                    seg = arc_points(fx(_f(e.get(10))), _f(e.get(20)), _f(e.get(40)), a0, a1)
                    if not ccw:
                        seg = seg[::-1]
                elif et == 3:
                    seg = ellipse_points(_f(e.get(10)), _f(e.get(20)), _f(e.get(11)), _f(e.get(21)), _f(e.get(40), 1.0),
                                         math.radians(_f(e.get(50))), math.radians(_f(e.get(51), 360.0)))
                elif et == 4:
                    ctrl = list(zip([_f(v) for v in lst.get(10, [])], [_f(v) for v in lst.get(20, [])]))
                    seg = bspline_points(ctrl, [_f(v) for v in lst.get(40, [])], _i(e.get(94), 3))
                else:
                    seg = []
                if seg:
                    pts.extend(seg if not pts else seg[1:] if math.dist(pts[-1], seg[0]) < 1e-9 else seg)
        if len(pts) >= 3:
            paths.append(pts)
    if not paths:
        return []
    return [('fill', paths)] if solid else [('poly', True, p) for p in paths]


def dec_dxf(s):
    """строка DXF: UTF-8; битый байт внутри UTF-8 (так пишет LibreDWG) — убирается, строка остаётся UTF-8; иначе — cp1251"""
    try:
        return s.decode('utf-8')
    except UnicodeDecodeError:
        u = s.decode('utf-8', 'replace')
        bad = u.count('\ufffd'); good = sum(1 for ch in u if ord(ch) > 127) - bad
        return u.replace('\ufffd', '') if good >= 4 * bad else s.decode('cp1251', 'replace')


def read_dxf(path):
    """один проход: слои (цвет, вес, выключен), блоки (база, сущности), сущности модели — сырые теги на сущность"""
    layers, blocks, model = {}, {}, []
    sec = None; cur_sec = False; ent = None; blk = None; tags = None; in_layer = None
    def close():
        nonlocal ent, tags
        if ent is None:
            return
        target = None
        if sec == 'BLOCKS' and blk is not None and ent not in ('BLOCK', 'ENDBLK', 'ATTDEF'):
            target = blocks[blk]['ents']
        elif sec == 'ENTITIES':
            target = model
        if target is not None:
            if ent == 'VERTEX':                                  # вершины старой полилинии — в её теги, кодом −1
                if target and target[-1][0] == 'POLYLINE':
                    target[-1][1].append((-1, tags))
            elif ent != 'SEQEND':
                target.append((ent, tags))
        ent = None; tags = None
    with open(path, 'rb') as f:
        while True:
            c = f.readline()
            if not c:
                break
            v = f.readline()
            try:
                code = int(c.strip())
            except ValueError:
                continue
            if code == 0:
                val = v.strip().decode('ascii', 'replace')
                close(); in_layer = None
                if val == 'SECTION':
                    cur_sec = True; continue
                if val == 'ENDSEC':
                    sec = None; continue
                if val == 'EOF':
                    break
                if sec == 'TABLES' and val == 'LAYER':
                    in_layer = {'color': 7, 'true': None, 'lw': -3, 'off': False, 'frozen': False}; continue
                if sec == 'BLOCKS' and val == 'BLOCK':
                    blk = None; ent = 'BLOCK'; tags = []; continue
                if sec == 'BLOCKS' and val == 'ENDBLK':
                    blk = None; continue
                if sec in ('ENTITIES', 'BLOCKS') and (sec == 'ENTITIES' or blk is not None):
                    ent = val; tags = []
                continue
            s = dec_dxf(v.rstrip(b'\r\n'))
            if cur_sec:
                if code == 2:
                    sec = s.strip(); cur_sec = False
                continue
            if in_layer is not None:
                if code == 2:
                    in_layer['name'] = s.strip(); layers[s.strip()] = in_layer
                elif code == 62:
                    in_layer['color'] = abs(_i(s, 7)); in_layer['off'] = _i(s, 7) < 0
                elif code == 420:
                    in_layer['true'] = _i(s)
                elif code == 370:
                    in_layer['lw'] = _i(s, -3)
                elif code == 70:
                    in_layer['frozen'] = bool(_i(s) & 1)
                continue
            if ent == 'BLOCK':
                if code == 2:
                    blk = s.strip(); blocks[blk] = {'base': [0.0, 0.0], 'ents': [], 'flags': 0}
                elif code in (10, 20) and blk:
                    blocks[blk]['base'][0 if code == 10 else 1] = _f(s)
                elif code == 70 and blk:
                    blocks[blk]['flags'] = _i(s)
                continue
            if ent is not None:
                tags.append((code, s))
    close()
    return layers, blocks, model


def ent_style(tags):
    layer, color, true, lw, paper, invis = '0', 256, None, -1, False, False
    for c, v in tags:
        if c == 8: layer = v.strip()
        elif c == 62: color = _i(v, 256)
        elif c == 420: true = _i(v)
        elif c == 370: lw = _i(v, -1)
        elif c == 67: paper = v.strip() == '1'
        elif c == 60: invis = v.strip() == '1'
    return layer, color, true, lw, paper, invis


def affine(x, y, sx, sy, rot):
    c, s = math.cos(math.radians(rot)), math.sin(math.radians(rot))
    return np.array([[c * sx, -s * sy, x], [s * sx, c * sy, y], [0, 0, 1]], float)


def dxf_to_pdf(dxf, out_pdf, views, mm_per_unit, title='', creator_note='', xrefs=None):
    """PDF со слоями OCG: лист на вид. mm_per_unit — мм в единице DXF; None — единицы не определены: масштаб листа
    не известен, длинная сторона самого большого вида — A0_PT. xrefs — {имя блока внешней ссылки: её DXF}: ссылка
    рисуется по своей вставке, её слои — «ссылка|слой», как в AutoCAD; состояние слоя — из таблицы чертежа, иначе ссылки.
    -> сведения для intake.json"""
    import pymupdf
    t0 = time.time()
    layers, blocks, model = read_dxf(dxf)
    t_read = time.time() - t0
    lay = lambda name: layers.get(name) or {'color': 7, 'true': None, 'lw': -3, 'off': False, 'frozen': False}
    vb = [v['bbox'] for v in views]
    if mm_per_unit:
        k = mm_per_unit / MM_PER_PT                               # единица DXF → pt листа
    else:
        k = A0_PT / max(1e-9, max(max(x1 - x0, y1 - y0) for x0, y0, x1, y1 in vb))
    prims = []                                                    # (вид, слой, цвет, вес мм, примитив в мировых)
    skipped_off = 0; count = [0]
    dim_pairs = []                                                # размеры: (число текста, длина между выносными)
    not_drawn = {}                                                # видимые сущности, которых PDF не рисует: тип → число
    solid_layers = {}                                             # 3D-тела ACIS на видимых слоях: слой → число

    def view_of(x, y):
        for i, (x0, y0, x1, y1) in enumerate(vb):
            mx, my = 0.02 * (x1 - x0), 0.02 * (y1 - y0)
            if x0 - mx <= x <= x1 + mx and y0 - my <= y <= y1 + my:
                return i
        return None

    def emit(pr, M, layer, color, lw, view):
        if count[0] >= MAX_PRIMS:
            return
        tf = lambda p: (M[0, 0] * p[0] + M[0, 1] * p[1] + M[0, 2], M[1, 0] * p[0] + M[1, 1] * p[1] + M[1, 2])
        tfe = lambda e: ('c',) + tf(e[1:3]) + tf(e[3:5]) + tf(e[5:7]) if len(e) == 7 else tf(e)   # кривая — три точки
        kind = pr[0]
        if kind == 'poly':
            pts = [tfe(p) for p in pr[2]]
            v = view if view is not None else view_of(*pts[0])
            if v is not None:
                if len(pr) > 3:                                  # ширина полилинии — в единицах модели, с масштабом вставки
                    prims.append((v, layer, color, lw, ('poly', pr[1], pts, pr[3] * math.sqrt(abs(M[0, 0] * M[1, 1] - M[0, 1] * M[1, 0])))))
                else:
                    prims.append((v, layer, color, lw, ('poly', pr[1], pts)))
                count[0] += 1
        elif kind == 'fill':
            paths = [[tf(p) for p in path] for path in pr[1]]
            v = view if view is not None else view_of(*paths[0][0])
            if v is not None:
                prims.append((v, layer, color, lw, ('fill', paths))); count[0] += 1
        elif kind == 'text':
            x, y = tf((pr[1], pr[2]))
            sc = math.sqrt(abs(M[0, 0] * M[1, 1] - M[0, 1] * M[1, 0]))       # масштаб вставки — по площади
            rot = pr[4] + math.degrees(math.atan2(M[1, 0], M[0, 0]))
            v = view if view is not None else view_of(x, y)
            if v is not None:
                prims.append((v, layer, color, lw, ('text', x, y, pr[3] * sc, rot, pr[5], pr[6], pr[7]))); count[0] += 1

    xcache = {}

    def load_xref(name):
        """внешняя ссылка: слои, блоки и модель её DXF; нет файла или не читается — None"""
        if name not in xcache:
            try:
                xl, xb, xm = read_dxf(xrefs[name])
                xcache[name] = {'layers': xl, 'blocks': xb, 'model': xm, 'prefix': name + '|'}
            except Exception:                                    # noqa: BLE001 — ссылка не роняет PDF: её нет, как без файла
                xcache[name] = None
        return xcache[name]

    def resolve(layer, color, true, lw, parent, ctx=None):
        """слой «0», цвет и вес BYBLOCK — от вставки; BYLAYER — от слоя. В ссылке слой — «ссылка|слой»"""
        pl, pc, plw = parent if parent else ('0', (0.0, 0.0, 0.0), -3)          # BYBLOCK в модели — чёрный
        raw = layer
        if layer == '0' and parent:
            layer = pl
        elif ctx:
            layer = ctx['prefix'] + layer
        L = layers.get(layer) or (ctx['layers'].get(raw) if ctx else None) or lay(layer)
        if true is not None:
            col = color_of(None, true)
        elif color == 0:
            col = pc
        elif color == 256 or color is None:
            col = color_of(L['color'], L['true'])
        else:
            col = color_of(color)
        w = plw if lw == -2 else (L['lw'] if lw == -1 else lw)
        w = 25 if w is None or w < 0 else w
        return layer, col, w, L

    def walk(ents, M, parent, depth, view, ctx=None):
        nonlocal skipped_off
        B = ctx['blocks'] if ctx else blocks
        for t, tags in ents:
            if count[0] >= MAX_PRIMS:
                return
            layer, color, true, lw, paper, invis = ent_style(tags)
            if paper or invis:
                continue
            layer, col, w, L = resolve(layer, color, true, lw, parent, ctx)
            if L['off'] or L['frozen']:
                skipped_off += 1; continue
            if t == 'DIMENSION' and depth == 0:
                dim_check(tags, blocks, dim_pairs)
            if t not in DRAWN:
                not_drawn[t] = not_drawn.get(t, 0) + 1
                if t in SOLID_TYPES:
                    solid_layers[layer] = solid_layers.get(layer, 0) + 1
                continue
            for pr in parse_entity(t, tags):
                if pr[0] == 'insert':
                    name, x, y, sx, sy, rot = pr[1:]
                    b = B.get(name)
                    if not b or depth >= MAX_DEPTH:
                        continue
                    X = None
                    if b['flags'] & 4:                           # внешняя ссылка — из своего DXF, вложенные ссылки — нет
                        X = load_xref(name) if (xrefs and name in xrefs and ctx is None) else None
                        if X is None:
                            continue
                    A = affine(x, y, sx, sy, rot) @ np.array([[1, 0, -b['base'][0]], [0, 1, -b['base'][1]], [0, 0, 1]], float)
                    Mw = M @ A
                    v = view
                    if v is None:                                # вид — по точке вставки; вне видов — по каждому примитиву:
                        v = view_of(Mw[0, 2], Mw[1, 2])          # блок размера вставлен в 0,0, его геометрия — в мировых
                    if X is not None:
                        walk(X['model'], Mw, (layer, col, w), depth + 1, None, X)   # ссылка шире вида — по примитиву
                    else:
                        walk(b['ents'], Mw, (layer, col, w), depth + 1, v, ctx)
                else:
                    emit(pr, M, layer, col, w, view)
    walk(model, np.eye(3), None, 0, None)
    t_geo = time.time() - t0 - t_read
    doc = pymupdf.open()
    ocg = {}
    used = sorted({p[1] for p in prims})
    for name in used:
        ocg[name] = doc.add_ocg(name or '0')
    fnt = font()[0]
    pages = []
    font_ok = True
    num = lambda v: ('%.3f' % v).rstrip('0').rstrip('.')
    for i, (x0, y0, x1, y1) in enumerate(vb):
        W = (x1 - x0) * k + 2 * MARGIN_PT; H = (y1 - y0) * k + 2 * MARGIN_PT
        W, H = min(max(W, 72), 14400), min(max(H, 72), 14400)
        pg = doc.new_page(width=W, height=H)
        Xp = lambda x: (x - x0) * k + MARGIN_PT                     # координаты PDF: y вверх
        Yp = lambda y: (y - y0) * k + MARGIN_PT
        groups = {}
        for v, layer, col, w, pr in prims:
            if v == i:
                wkey = 0 if pr[0] == 'text' else (-max(1, round(pr[3] * k * 100)) if pr[0] == 'poly' and len(pr) > 3 else round(w))
                groups.setdefault((layer, col, wkey, pr[0]), []).append(pr)   # wkey < 0 — ширина полилинии, сотые pt
        # поток содержимого пишется напрямую: путь на сущность, слой — /OC /MCn BDC … EMC (как у листа AutoCAD);
        # подписи — тем же потоком, шрифт FU встроен один на документ. insert_text и Shape pymupdf на каждый вызов
        # переписывают содержимое страницы и на тысячах подписей идут минутами — здесь линейно
        ops, tags = [], {}
        nseg = nt = 0
        has_text = any(key[3] == 'text' for key in groups)
        if has_text:
            pg.insert_font(fontname='FU', fontbuffer=fnt.buffer)
        for (layer, col, w, kind), prs in groups.items():
            tag = tags.setdefault(layer, 'MC%d' % len(tags))
            rgb = ' '.join(num(c) for c in col)
            ops.append('/OC /%s BDC' % tag)
            if kind == 'poly':
                ops.append('%s RG %s w 0 J 0 j' % (rgb, num(-w / 100.0)) if w < 0 else
                           '%s RG %s w 1 J 1 j' % (rgb, num(max(0.1, w / 100.0 / 0.3528))))
                for pr in prs:
                    pts = pr[2]
                    if len(pts) < 2:
                        continue
                    seg = ['%s %s m' % (num(Xp(pts[0][0])), num(Yp(pts[0][1])))]
                    seg += ['%s %s %s %s %s %s c' % (num(Xp(e[1])), num(Yp(e[2])), num(Xp(e[3])), num(Yp(e[4])), num(Xp(e[5])), num(Yp(e[6])))
                            if len(e) == 7 else '%s %s l' % (num(Xp(e[0])), num(Yp(e[1]))) for e in pts[1:]]
                    ops.append(' '.join(seg) + (' h S' if pr[1] else ' S')); nseg += len(pts) - 1
            elif kind == 'fill':
                ops.append('%s rg' % rgb)
                for pr in prs:
                    seg = []
                    for path in pr[1]:
                        if len(path) >= 3:
                            seg.append('%s %s m' % (num(Xp(path[0][0])), num(Yp(path[0][1]))))
                            seg += ['%s %s l' % (num(Xp(x)), num(Yp(y))) for x, y in path[1:]]
                            seg.append('h'); nseg += len(path)
                    if seg:
                        ops.append(' '.join(seg) + ' f*')
            else:
                ops.append('BT /FU 1 Tf %s rg' % rgb)
                for pr in prs:
                    t_ops, ok = text_ops(pr, k, Xp, Yp, fnt, num)
                    ops.extend(t_ops); nt += bool(t_ops); font_ok &= ok
                ops.append('ET')
            ops.append('EMC')
        if ops:
            sx = doc.get_new_xref()
            doc.update_object(sx, '<<>>')
            doc.update_stream(sx, ('q\n' + '\n'.join(ops) + '\nQ\n').encode('latin-1'))
            cont = doc.xref_get_key(pg.xref, 'Contents')
            if cont[0] == 'array':
                doc.xref_set_key(pg.xref, 'Contents', cont[1][:-1] + ' %d 0 R]' % sx)
            elif cont[0] == 'xref':
                doc.xref_set_key(pg.xref, 'Contents', '[%s %d 0 R]' % (cont[1], sx))
            else:
                doc.xref_set_key(pg.xref, 'Contents', '%d 0 R' % sx)
            rk = doc.xref_get_key(pg.xref, 'Resources')              # ресурсы страницы — бывают косвенным объектом
            rx, pre = (int(rk[1].split()[0]), '') if rk[0] == 'xref' else (pg.xref, 'Resources/')
            for layer, tag in tags.items():
                doc.xref_set_key(rx, '%sProperties/%s' % (pre, tag), '%d 0 R' % ocg[layer])
        pages.append({'page': i + 1, 'size_pt': [round(W, 1), round(H, 1)], 'segments': nseg, 'texts': nt, 'bbox': [x0, y0, x1, y1]})
    known = bool(mm_per_unit)
    doc.set_metadata({'producer': 'cad_intake.py (UnSpot): DXF → PDF, слои DXF → OCG', 'creator': 'DWG → DXF (LibreDWG) → PDF %s' % creator_note,
                      'title': title,
                      'subject': ('масштаб %.2f мм/pt; единица DXF = %.4g мм' % (MM_PER_PT, mm_per_unit)) if known else
                                 'масштаб не известен: единицы DXF не определены; длинная сторона вида — %.0f pt (A0)' % A0_PT})
    doc.save(out_pdf, garbage=3, deflate=True)
    doc.close()
    return {'file': os.path.basename(out_pdf), 'mm_per_pt': MM_PER_PT if known else None, 'mm_per_unit': mm_per_unit,
            'pt_per_unit': round(k, 6), 'scale': 'известен' if known else 'не известен — единицы не определены',
            'pages': pages, 'layers': len(used), 'primitives': len(prims), 'capped': count[0] >= MAX_PRIMS,
            'skipped_off_layers': skipped_off, 'texts_all_ok': font_ok, 'dims': dims_summary(dim_pairs), 'not_drawn': dict(sorted(not_drawn.items(), key=lambda kv: -kv[1])), 'xrefs_drawn': sorted(k for k, v in xcache.items() if v), 'solid_layers': dict(sorted(solid_layers.items(), key=lambda kv: -kv[1])[:8]),
            'secs': {'read': round(t_read, 1), 'geometry': round(t_geo, 1), 'write': round(time.time() - t0 - t_read - t_geo, 1)},
            'bytes': os.path.getsize(out_pdf)}


NUM_RE = re.compile(r'\d+(?:[.,]\d+)?')


def dim_check(tags, blocks, pairs):
    """линейный размер модели (повёрнутый или параллельный): (число его текста, длина между точками выносных в единицах
    чертежа) — в pairs. Угловые, радиальные, ординатные — нет"""
    g = {}
    for c, v in tags:
        if c in (2, 13, 23, 14, 24, 50, 70) and c not in g:
            g[c] = v
    kind = _i(g.get(70), 0) & 7
    b = blocks.get(g.get(2)) if g.get(2) else None
    if kind not in (0, 1) or not b or not all(c in g for c in (13, 23, 14, 24)):
        return
    dx, dy = _f(g[14]) - _f(g[13]), _f(g[24]) - _f(g[23])
    if kind == 0:
        a = math.radians(_f(g.get(50), 0.0)); geom = abs(dx * math.cos(a) + dy * math.sin(a))
    else:
        geom = math.hypot(dx, dy)
    if geom <= 1e-9:
        return
    for t, tg in b['ents']:
        if t in ('MTEXT', 'TEXT'):
            for pr in parse_entity(t, tg):
                nums = NUM_RE.findall(pr[5])
                if nums:
                    pairs.append((float(nums[0].replace(',', '.')), geom))
                    return


def dims_summary(pairs):
    """число размера к длине на листе: множитель — самое частое отношение (1 — число в единицах чертежа; 100 — виды на
    листе в 1:100 и т. п.); переписан вручную — отношение дальше 1 % от множителя"""
    if not pairs:
        return {'linear': 0}
    r = np.array([n / g for n, g in pairs])[:3000]
    pos = r[r > 0]
    if not len(pos):
        return {'linear': len(pairs), 'ratio': None, 'text_eq': 0, 'text_ne': len(pairs), 'ne_sample': []}
    lr = np.log(pos)
    near = (np.abs(lr[:, None] - lr[None, :]) <= 0.01).sum(1)     # множитель — самое частое отношение (±1 %), не медиана:
    med = float(np.median(pos[np.abs(lr - lr[int(np.argmax(near))]) <= 0.01]))   # переписанных бывает больше половины
    ok = np.abs(r / med - 1) <= 0.01
    return {'linear': len(pairs), 'ratio': round(med, 4), 'text_eq': int(ok.sum()), 'text_ne': int((~ok).sum()),
            'ne_sample': [[round(g, 1), n] for (n, g), good in zip(pairs, ok) if not good][:5]}


def text_ops(pr, k, Xp, Yp, fnt, num):
    """подпись → операторы PDF: строка на строку, выравнивание DXF (72/73 у TEXT, точка привязки у MTEXT), поворот.
    Базовая линия первой строки — от точки вставки в осях подписи: верх −0,75 кегля, середина −0,35, низ +0,2."""
    _, x, y, h, rot, s, ha, va = pr
    fs = h * k
    if fs < MIN_TEXT_PT:
        return [], True
    lines = s.split('\n')[:20]
    nl, lh = len(lines), fs * 1.25
    if ha == 4:                                                   # TEXT «середина» — по обеим осям
        ha, va = 1, 2
    base = {3: -0.75 * fs, 2: (nl - 1) * lh / 2 - 0.35 * fs, 1: (nl - 1) * lh + 0.2 * fs}.get(va, 0.0)
    c, sn = math.cos(math.radians(rot)), math.sin(math.radians(rot))
    ax, ay = Xp(x), Yp(y)
    out, ok = [], True
    for j, line in enumerate(lines):
        line = line[:200]
        if not line.strip():
            continue
        wl = fnt.text_length(line, fontsize=fs)
        dx = {1: -wl / 2, 2: -wl}.get(ha, 0.0)
        dy = base - j * lh
        hx, good = gids(line)
        ok &= good
        out.append('%s %s %s %s %s %s Tm <%s> Tj' % (num(fs * c), num(fs * sn), num(-fs * sn), num(fs * c),
                                                    num(ax + dx * c - dy * sn), num(ay + dx * sn + dy * c), hx))
    return out, ok
