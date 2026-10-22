#!/usr/bin/env python3
"""acceptance_checks.py v3 (02.10.2026) — приёмка карты UnSpot по списку Ч-01…Ч-30 и шлюз сдачи (--gate): SVG-чистовик (артефакт 2), по желанию PNG, артефакт 3, JSON мест, исходник.
Статусы: pass; fail; look — посмотреть глазами; skip — нет данных или проверяется процедурой, с причиной; info — справочно. «Где» — px фрейма.
Код выхода 1 — есть fail. Зависимости: numpy, scipy, shapely ≥ 2, Pillow; cv2 — справка S13. Кривые и дуги A — точками через ≈ 2 px (v1: дуга — хордой); короткие рёбра и изломы меряются только на прямых отрезках.
v2: открытые зоны — помещения; смешанный фасад; колонны — не стены; символы гайдлайна не проверяются как своя геометрия;
стрелка входа — не бейдж; №40 — номер на цветной заливке #62677A; №50/№75 — мебели переговорных нет, растения можно;
пороги Ч-10, Ч-12, Ч-20, Ч-22 — как в map/rules/80; Ч-10 и Ч-11 по маске тела стены (--source-kind vector --wall-mask);
шлюз: fail — только через реестр принятого (--accept: max мест и причина), look — вердикт на каждое место (--verdicts),
skip — строка «чем проверено» (--notes), протокол К-01…К-12 (--crops). v013: transform применяется при чтении SVG (map/rules/80 Ч-21); Ч-26 его по-прежнему запрещает.
v3: --outer-wall-px — толщина фасада, px фрейма (по умолчанию 2T): перенос карты с решением владельца «геометрия как есть» — толщина как у источника;
Ч-19 сверяет заливку проёма с заливками сторон — помещений, открытых зон и зон поверх помещений, которых проём касается (буфер 1,5 px):
проём — цвета своей комнаты, между цветным и белым — цвета цветного (map/rules/60 §1, map/rules/60 §2.3); нет сторон — look.
v4 (02.10.2026, клиент А 4: три прогона, canon-proposals Г1, Г2): Ч-31 стулья листа без места (--chairs-json); Ч-32 косые рёбра короче 0,8 м;
Ч-33 бейджи против признаков листа — квадрат с диагоналями от 1,5 м — лифт или шахта, не WC (детектор — по --source-png); Ч-34 закрытое
помещение без мебели и мест при мебели на листе; Ч-10 растром — по телу стены: тушь, закрытая на толщину класса, справочно — отклонение оси
от середины тела; Ч-18 — лифт по data-type словом; Ч-23 — помещение по объекту, не по имени; Ч-24 — указатель выноски через чужое закрытое
помещение — look; шлюз — список кропов кодом (crop_list), вердикт на каждый объект, перенос вердикта неизменившегося кадра (пиксели равны).
v7 (06.10.2026, код карты v007, пакет кода 1): шлюз — причина принятого видом из закрытого списка и ссылкой, svg_sha256 в реестрах, вердикт на каждое
место со статусом и кадром этого SVG (review/gate_frames.py), перенос — только с кадром этого круга, gate.json с версией кода и SHA-256 приёмки;
ложные срабатывания: Ч-09 Т-узел соседа, Ч-14 колонна, Ч-17 номер в имени, Ч-18 шахта по типу, Ч-19 глубина T + 1 и проём по типу и id,
Ч-26 символ гайдлайна без stroke, Ч-29 пятна по маске до номеров, Ч-31 номер строкой, кухни, деталь стола, Ч-32 линия исходника в 0,3 м.
v8 (06.10.2026, код карты v008, пакет кода 2): новые Ч-35 связность от входа (проходимое растром: помещения, проёмы, виртуальные границы),
Ч-36 двери листа без проёма карты и дверь лифта не в холл (--sheet-doors), Ч-37 артефакт 3 против листа — стол на модуле листа, номер в своём
столе (--sheet-numbers), Ч-38 стекло листа без стекла карты (--sheet-glass), Ч-39 тип помещения по мебели листа (строки 176–177; --chairs-json);
Ч-21 — стол места в слое furniture (Е18); Ч-10 — рецепт и SHA-256 маски (unspot_map.wall_mask), стена внутри массива — look (Н24, Т4-2);
шлюз — К-03 и К-08 объектами кода (ПК1-К9), файлы шагов круга (Р22). Вход с листа — skip с причиной, если не дан.
v10 (07.10.2026, код карты v010, пакет кода 4; ответы владельца 07.10, строки 203–205): Ч-32 — оправданное косое ребро (по линии листа того же
направления и 90° к соседям или по главному направлению здания, ± 2,5°, способ К6) не в счёт и не в look (К-4; №103, №109); Ч-37 — столы на модуле
листа — все: доля < 100 % — fail, каждый стол мимо модуля — объект К-11 списка кропов (К-5; №102); Ч-35 — у отрезанной части, где помещения офиса
открываются только в общие помещения здания (лестница, венткамера, шахта), — подсказка «потерянная дверь листа» в месте (К-6; №101).
v11 (07.10.2026, код карты v011, пакет кода 5; ПК4-К3, К4, К16): Ч-37 — мера desk_module: точка длинной стороны, закрытая стулом листа (--chairs-json, круг 0,35 м)
или другим предметом листа (в окне 0,1 м тушь не параллельна стороне), не мерится; длина стола — против модуля листа ± 0,1 м (торцы модуля — нейтральная тушь
поперёк стола на ≥ 60 % глубины в 0,45 м от торца; тумба у торца, №90, — не ошибка); объект К-11 «модуль:N» несёт контур стола (poly) для кадра; при fail —
объекты К-11 «стул:N» и «два-места:N+M»; К-03 — пара «коридор × коридор» по rid, не id().
v13 (16.10.2026, код карты v013, К13.3, К13.4; map/rules/80 §2, map/rules/83 §1, §5; строки 354, 358, 387, 413): SVG читается с применением transform;
Ч-21, Ч-29 — записи без desk и centre: fail «записей N, столов 0: ключи записи не по схеме map/rules/83 §5», desk: null — fail; Ч-29 — точка закрыта:
доля #FFB000 в круге ⌀ 0,26 м (не меньше 6 px) < 0,9 — fail; Ч-10 — d₂ = max(2 px холста, 2q мм), d₃ = max(3 px холста, 3q мм), растр с q ≥ 100 мм/px —
≥ 85 % / ≥ 90 %; Ч-10, Ч-11 — признак «цветные стены» (--colored-walls) без --wall-mask: look, число непокрытой цветной туши; Ч-22 — стол переговорной
со стульями — не нарушение №50 (строка 354); проверки без номера Ч (шлюз их не решает): «стол переговорной против стола листа» (± 10 %, число
стульев; --sheet-tables, --chairs-json; строка 413) и «стол переговорной помещается» (зазор до стены ≥ 0,5 м) — look."""
import argparse, hashlib, json, math, os, random, re, sys
from collections import Counter, defaultdict
from types import SimpleNamespace as NS
import xml.etree.ElementTree as ET
import numpy as np, shapely
from PIL import Image, ImageDraw
from scipy import ndimage
from shapely import affinity
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import linemerge, unary_union
from shapely.strtree import STRtree
from shapely.validation import make_valid

LAYERS = ['underlay', 'rooms', 'glass', 'furniture', 'icons', 'labels']                        # map/rules/05 §2
WALL, GLASS, BADGE, GLYPH = '#CBD2D6', '#86C5FB', '#E1E7EB', '#62677A'                          # map/rules/40 §1, map/rules/60 §1, map/rules/70 §1
PLANTS = {'2904:13030', '3070:1014'}                                                          # растения гайдлайна (№75)
ENTRY = {'2904:12530'}                                                                         # стрелка входа
PALETTE = {'#' + c for c in ('FFEBEB FFEEEB FFF1EB FFF5EB FFF8EB FFFCEB FFFFEB FCFFEB F8FFEB F5FFEB F4FFEB EEFFEB EBFFEB '
           'EBFFEE EBFFF1 EBFFF5 EBFFF8 EBFFFC EBFFFF EBFCFF EBF8FF EBF5FF EBF1FF EBEEFF EBEBFF EEEBFF F1EBFF F8EBFF FCEBFF '
           'FFEBFF FFEBFC FFEBF8 FFEBF5 FFEBF1 FFEBEE FFFFFF F4F4F4').split()}      # кольцо 35 (map/rules/71 §1), белый, «не используется»
NUM = r'[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?'
OPENING_EXTRA = 1.0       # проём глубже стены на 1 px (по 0,5 px на сторону — сглаживание, map/rules/11 §12): та же величина, что unspot_map.svg_map.DOOR_EXTRA (АБ3)
DOOR_T = re.compile(r'^\s*(door|opening|doorway|проём|проем|двер)', re.I)           # v007: проём — по data-type / data-kind (АБ4)
DOOR_ID = re.compile(r'(^|[-_\s])(door|opening|doorway|проём|проем|двер)', re.I)      # без типа — по id: svg_map пишет door-<этаж>-<i>
SHAFT, OPEN, DOOR = (re.compile(p, re.I) for p in (r'shaft|niche|duct|riser|lift|шахт|ниш|стояк|лифт',
                     r'open|corridor|hall|lobby|коридор|опен|холл', r'door|opening|passage|проём|проем|двер|проход'))
# v4: тип помещения — по data-type словом; нет типа — по началу имени (Ч-18, Ч-24, Ч-33, Ч-34, список кропов). «Холл у лифтов» — не лифт
KIND = [('lift', r'\b(lift|elevator|лифт)\b', r'^\s*(лифт|lift|elevator)\b'),
        ('shaft', r'shaft|duct|riser|niche|шахт|стояк|ниш', r'^\s*(шахт|стояк|ниша|shaft|duct|riser)'),
        ('void', r'void|atrium|пустот|атриум|второй свет', r'^\s*(пустот|атриум|второй свет|void|atrium)'),
        ('stair', r'stair|лестн|марш', r'^\s*(лестн|stair)'),
        ('wc', r'\bwc\b|toilet|restroom|сануз|туалет|\bс/у\b|уборная', r'^\s*(wc|с/у|санузел|туалет|уборная)'),
        ('meeting', r'meet|conference|переговор|конференц', r'(переговор|конференц|meeting)'),
        ('kitchen', r'kitchen|canteen|pantry|dining|coffee|кухн|столов|кофе', r'(кухн|столов|кофе|kitchen|pantry)'),
        ('corridor', r'corr|hall|lobby|foyer|vestib|коридор|холл|вестиб|тамбур', r'^\s*(коридор|холл|вестиб|тамбур|corridor|hall|lobby)'),
        ('openspace', r'open|опен', r'^\s*(опен|open)'),
        ('tech', r'tech|server|electr|щит|венткам|сервер|кроссов|техпом', r'(щитов|венткам|сервер|кроссов|техпом|техническ)')]
def rkind(r):
    """тип помещения для проверок v4: lift, shaft, void, stair, wc, meeting, kitchen, corridor (коридор, холл), openspace, tech, other"""
    if r is None: return None
    for k, t, n in KIND:
        if re.search(t, r.type, re.I) if r.type else re.search(n, r.name or '', re.I): return k
    return 'other'
Q_COARSE_MM = 100.0       # v13 (строка 358): растр с q ≥ 100 мм/px — пороги Ч-10 ≥ 85 % при d₂ и ≥ 90 % при d₃ (map/rules/80 Ч-10)
C10_FINE, C10_COARSE = (0.95, 0.98), (0.85, 0.90)
SEAT_RGB, SEAT_TOL = (0xFF, 0xB0, 0x00), (12, 20, 30)                    # точка стула #FFB000 (map/rules/83 §1); допуск — как у пятен мест Ч-29
SEAT_D_M, SEAT_D_MIN_PX, SEAT_SHARE = 0.26, 6.0, 0.9                     # v13 (map/rules/80 Ч-29, map/rules/83 §1): круг ⌀ 0,26 м, не меньше 6 px; доля цвета ≥ 0,9
MR_TOL, MR_GAP_M = 0.10, 0.5                                             # v13: стол переговорной ± 10 % к столу листа (строка 413); зазор до стены ≥ 0,5 м (map/rules/80 §2)
MR_TABLE_FIGMA = {'2904:15151': 6, '2916:1518': 12, '2904:15864': 8, '2904:15881': 4, '3239:3259': 4, '2904:15170': 0,   # map/kit/61: столы переговорных; число — стульев в символе
                  '5:2': None, '34:2': None, '34:34': None, '34:72': None, '35:2': None, '35:28': None, '35:48': None, '35:62': None, '36:2': None,
                  '36:28': None, '36:54': None, '36:68': None, '36:86': None, '37:2': None, '37:48': None, '37:82': None, '38:2': None, '38:46': None,
                  '39:2': None, '30:47': None, '32:65': None, '32:83': None, '33:2': None}   # map/kit/63: столы легенды «Client Maps by Claude» (3:7, bufer); стульев — не записано
MR_CHAIR_FIGMA = {'2904:15155'}                                          # map/kit/61: стул
MR_TABLE_RE, MR_CHAIR_RE = re.compile(r'table|стол', re.I), re.compile(r'chair|стул', re.I)
GLYPH_KIND = {'2904:12707': 'wc', '2984:2362': 'wc', '2984:2366': 'wc', '2904:12788': 'lift', '2904:12897': 'lift', '2904:12898': 'lift',
              '2904:12795': 'stair', '2904:12716': 'tech', '2904:12761': 'tech', '2904:12722': 'kitchen',
              '21:41': 'dinner'}   # map/kit/70-глифы-гайдлайна-svg.md; v013: 21:41 — «вилка и нож» из пина points «Client Maps by Claude» (строка 412, ОЧ-167)

# ------------------------------------------------------------------ мелочи
pc = lambda v, d=1: f'{100 * v:.{d}f} %'.replace('.', ',')
fx = lambda v, d=1: f'{v:,.{d}f}'.replace(',', ' ').replace('.', ',')
def W(p, note=''):
    ok = p is not None and np.isfinite(np.asarray(p, float)).all()
    return dict(x=round(float(p[0]), 1) if ok else None, y=round(float(p[1]), 1) if ok else None, note=note)
def row(i, name, val, thr, st, where=(), reason=None, s=()):
    w = list(where); r = dict(id=i, s=list(s), name=name, value=val, threshold=thr, status=st, where=w[:40], where_total=len(w))
    if len(w) > 40: r['where_all'] = w                                    # полный список мест — для вердиктов шлюза
    return {**r, 'reason': reason} if reason else r
def cnt(i, name, w, thr='0', bad='fail', val=None, s=()): return row(i, name, val or str(len(w)), thr, bad if w else 'pass', w, s=s)
def skip(i, name, why, val='—', s=()): return row(i, name, val, '—', 'skip', reason=why, s=s)
def num(v, d=0.0):
    m = re.match(rf'\s*({NUM})', str(v)) if v is not None else None
    return float(m[1]) if m else d
def hexc(v):
    if v is None: return None
    v = v.strip(); k = v.lower(); m = re.fullmatch(r'#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})', v)
    if k in ('none', 'transparent', 'white', 'black'): return {'white': '#FFFFFF', 'black': '#000000'}.get(k, 'none')
    return ('#' + (''.join(c * 2 for c in m[1]) if len(m[1]) == 3 else m[1])).upper() if m else v
def parts(g, k='Polygon'):
    if g is None or g.is_empty: return []
    if g.geom_type == k: return [g]
    if g.geom_type == 'LinearRing' and k == 'LineString': return [LineString(g.coords)]
    return [q for x in getattr(g, 'geoms', []) for q in parts(x, k)]
lines = lambda g: parts(g, 'LineString')
def shell(g):
    ps = parts(g); t = sum(q.area for q in ps)
    return unary_union([Polygon(q.exterior) for q in ps if q.area >= 0.01 * t]) if ps else Polygon()
ext = lambda g: unary_union([q.exterior for q in parts(g)]) if not g.is_empty else LineString()
band = lambda g, w: g.buffer(w / 2, cap_style='flat', join_style='mitre', mitre_limit=5)
turn = lambda u, v: math.degrees(abs(math.atan2(u[0] * v[1] - u[1] * v[0], u[0] * v[0] + u[1] * v[1])))
def sides(g):
    """короткая и длинная сторона минимального прямоугольника, единичный вектор вдоль длинной"""
    mr = g.minimum_rotated_rectangle
    if mr.geom_type != 'Polygon': return 0.0, 0.0, None
    c = np.array(mr.exterior.coords[:3]); e1, e2 = c[1] - c[0], c[2] - c[1]; l1, l2 = float(np.hypot(*e1)), float(np.hypot(*e2))
    return (l2, l1, e1 / l1) if l1 >= l2 else (l1, l2, e2 / max(l2, 1e-9))
def at(r):
    if not r.poly.is_empty: return r.poly.representative_point().coords[0]
    return r.subs[0][0][0] if r.subs else (num(r.a.get('x', r.a.get('x1'))), num(r.a.get('y', r.a.get('y1'))))
def raster(gs, w, h, M=None):
    im = Image.new('1', (w, h), 0); d = ImageDraw.Draw(im)                        # пиксель k = [k, k+1)
    for q in (q for g in gs for q in parts(affinity.affine_transform(g, M) if M else g)):
        d.polygon([(x - .5, y - .5) for x, y in q.exterior.coords], fill=1)
        for i in q.interiors: d.polygon([(x - .5, y - .5) for x, y in i.coords], fill=0)
    return np.asarray(im, bool)

# ------------------------------------------------------------------ разбор SVG
TOK, NA = re.compile(r'[A-Za-z]|' + NUM), dict(M=2, L=2, H=1, V=1, C=6, S=4, Q=4, T=2, A=7)
def bez(c, t):
    c = np.array(c, float)
    while len(c) > 1: c = c[:-1] * (1 - t) + c[1:] * t
    return tuple(c[0])
def arc_pts(x0, y0, rx, ry, phi, fa, fs, x1, y1, step=2.0):
    """дуга SVG A (конечные точки, SVG 1.1 F.6.5) -> точки через ≈ step px, без начальной"""
    if rx == 0 or ry == 0 or (x0, y0) == (x1, y1): return [(x1, y1)]
    rx, ry = abs(rx), abs(ry); ph = math.radians(phi % 360); cp, sp = math.cos(ph), math.sin(ph)
    dx, dy = (x0 - x1) / 2, (y0 - y1) / 2; xp, yp = cp * dx + sp * dy, -sp * dx + cp * dy
    lam = (xp / rx) ** 2 + (yp / ry) ** 2
    if lam > 1: rx, ry = rx * math.sqrt(lam), ry * math.sqrt(lam)
    den = rx * rx * yp * yp + ry * ry * xp * xp
    co = (math.sqrt(max(0.0, (rx * rx * ry * ry - den) / den)) if den else 0.0) * (-1 if fa == fs else 1)
    cxp, cyp = co * rx * yp / ry, -co * ry * xp / rx
    cx, cy = cp * cxp - sp * cyp + (x0 + x1) / 2, sp * cxp + cp * cyp + (y0 + y1) / 2
    ang = lambda ux, uy, vx, vy: math.atan2(ux * vy - uy * vx, ux * vx + uy * vy)
    t1 = ang(1, 0, (xp - cxp) / rx, (yp - cyp) / ry); dt = ang((xp - cxp) / rx, (yp - cyp) / ry, (-xp - cxp) / rx, (-yp - cyp) / ry)
    if not fs and dt > 0: dt -= 2 * math.pi
    elif fs and dt < 0: dt += 2 * math.pi
    n = max(2, int(math.ceil(abs(dt) * max(rx, ry) / step))); out = []
    for k in range(1, n + 1):
        tt = t1 + dt * k / n; ex, ey = rx * math.cos(tt), ry * math.sin(tt); out.append((cp * ex - sp * ey + cx, sp * ex + cp * ey + cy))
    out[-1] = (x1, y1)
    return out
def parse_d(d, step=2.0):
    """d -> [(точки, замкнут Z, вершин, вершины команд [(индекс точки, вид отрезка, который в неё приходит: 'M', 'L' прямой, 'C' кривой)])]"""
    t, out, i, cmd, x, y, s0, pts, nv, vx = TOK.findall(d or ''), [], 0, None, 0.0, 0.0, (0.0, 0.0), [], 0, []
    def flush(z):
        nonlocal pts, nv, vx
        if z and len(pts) > 1 and math.dist(pts[0], pts[-1]) < 1e-6:
            pts.pop(); nv -= 1
            if vx and vx[-1][0] == len(pts): vx[0] = (0, vx.pop()[1])     # замыкающий отрезок — вид последней команды
        elif z and vx: vx[0] = (0, 'L')                                      # Z дорисовывает прямую к началу
        if pts: out.append((pts, z, max(nv, 1), vx))
        pts, nv, vx = [], 0, []
    while i < len(t):
        if t[i].isalpha(): cmd = t[i]; i += 1
        C = (cmd or '?').upper()
        if C == 'Z': flush(True); (x, y), cmd = s0, None; continue
        if C not in NA or len(t[i:i + NA[C]]) < NA[C] or any(v.isalpha() for v in t[i:i + NA[C]]): break
        a = [float(v) for v in t[i:i + NA[C]]]; i += NA[C]
        ox, oy = (x, y) if cmd.islower() else (0.0, 0.0)
        P = [(a[0] + ox, y)] if C == 'H' else [(x, a[0] + oy)] if C == 'V' else [(a[5] + ox, a[6] + oy)] if C == 'A' else \
            [(a[k] + ox, a[k + 1] + oy) for k in range(0, len(a), 2)]
        if C == 'M': flush(False); pts, nv, s0, cmd, vx = [P[0]], 1, P[0], 'l' if cmd == 'm' else 'L', [(0, 'M')]; x, y = P[0]; continue
        if not pts: pts, nv, vx = [(x, y)], 1, [(0, 'M')]
        if C in 'CSQT':
            ctrl = [(x, y)] * (2 if C in 'ST' else 1) + P; ln = sum(math.dist(p, q) for p, q in zip(ctrl[:-1], ctrl[1:]))
            n = max(4, int(math.ceil(ln / step))); pts += [bez(ctrl, s) for s in np.linspace(0, 1, n + 1)[1:]]; kind = 'C'
        elif C == 'A': pts += arc_pts(x, y, a[0], a[1], a[2], a[3] != 0, a[4] != 0, *P[-1], step=step); kind = 'C'
        else: pts.append(P[-1]); kind = 'L'
        vx.append((len(pts) - 1, kind)); (x, y), nv = pts[-1], nv + 1
    flush(False)
    return out
def geom(r):
    """[(точки, замкнут, вершин)]; вершины команд и вид отрезков — в r.vxs (кривые не меряются как рёбра)"""
    a, t, g = r.a, r.tag, lambda k: num(r.a.get(k))
    L4 = lambda n: [(i, 'L') for i in range(n)]
    if t == 'path': S4 = parse_d(a.get('d'))
    elif t == 'rect': x, y, w, h = g('x'), g('y'), g('width'), g('height'); S4 = [([(x, y), (x + w, y), (x + w, y + h), (x, y + h)], True, 4, L4(4))] if w > 0 < h else []
    elif t in ('circle', 'ellipse'):
        rx, ry = (g('r'), g('r')) if t == 'circle' else (g('rx'), g('ry'))
        S4 = [([(g('cx') + rx * math.cos(u), g('cy') + ry * math.sin(u)) for u in np.linspace(0, 2 * math.pi, 33)[:-1]], True, 4, [(i, 'C') for i in range(32)])]
    elif t == 'line': S4 = [([(g('x1'), g('y1')), (g('x2'), g('y2'))], False, 2, [(0, 'M'), (1, 'L')])]
    elif t in ('polyline', 'polygon'):
        v = [float(z) for z in re.findall(NUM, a.get('points', ''))]; n = len(v) // 2
        S4 = [(list(zip(v[::2], v[1::2])), t == 'polygon', n, L4(n) if t == 'polygon' else [(0, 'M')] + [(i, 'L') for i in range(1, n)])]
    else: S4 = []
    S4 = [s for s in S4 if s[0] and np.isfinite(np.asarray(s[0], float)).all()]
    r.vxs = [s[3] for s in S4]
    return [s[:3] for s in S4]
def poly_of(S):
    g = Polygon()
    for p, c, k in S: q = unary_union(parts(make_valid(Polygon(p)))); g = q if g.is_empty else g.symmetric_difference(q)   # evenodd
    return g if g.is_empty else unary_union(parts(make_valid(g)))
TF_OP = re.compile(r'(matrix|translate|scale|rotate|skewX|skewY)\s*\(([^)]*)\)')
def tf_matrix(s):
    """v13 (map/rules/80 Ч-21): атрибут transform SVG -> матрица 3×3; операции — слева направо, как в SVG"""
    M = np.eye(3)
    for op, args in TF_OP.findall(s or ''):
        v = [float(z) for z in re.findall(NUM, args)]; T = np.eye(3)
        if op == 'matrix' and len(v) == 6: T = np.array([[v[0], v[2], v[4]], [v[1], v[3], v[5]], [0, 0, 1.0]])
        elif op == 'translate' and v: T[0, 2], T[1, 2] = v[0], (v[1] if len(v) > 1 else 0.0)
        elif op == 'scale' and v: T[0, 0], T[1, 1] = v[0], (v[1] if len(v) > 1 else v[0])
        elif op == 'rotate' and v:
            c, s_ = math.cos(math.radians(v[0])), math.sin(math.radians(v[0])); T = np.array([[c, -s_, 0], [s_, c, 0], [0, 0, 1.0]])
            if len(v) == 3: T = np.array([[1, 0, v[1]], [0, 1, v[2]], [0, 0, 1.0]]) @ T @ np.array([[1, 0, -v[1]], [0, 1, -v[2]], [0, 0, 1.0]])
        elif op == 'skewX' and v: T[0, 1] = math.tan(math.radians(v[0]))
        elif op == 'skewY' and v: T[1, 0] = math.tan(math.radians(v[0]))
        M = M @ T
    return M
def load(path):
    root, R = ET.parse(path).getroot(), []
    def walk(el, layer, inh, depth, inst=None, fig=None, M=None, anc=()):
        a = {k.split('}')[-1]: v for k, v in el.attrib.items()}
        a.update((k.strip(), v.strip()) for k, v in re.findall(r'([\w-]+)\s*:\s*([^;]+)', a.get('style', '')))
        st = {**inh, **{k: a[k] for k in ('fill', 'stroke', 'stroke-width', 'font-family', 'font-size', 'text-anchor', 'visibility') if k in a}}
        st['display'] = 'none' if 'none' in (inh.get('display'), a.get('display')) else ''
        tag = el.tag.split('}')[-1]; layer = (a.get('id') if tag == 'g' else None) if depth == 1 else layer
        if depth == 2: inst = a.get('id') or f'#{len(R)}'                         # экземпляр — прямой потомок группы слоя
        fig = a.get('data-figma') or fig                                           # внутри символа гайдлайна
        if a.get('transform'): M = (np.eye(3) if M is None else M) @ tf_matrix(a['transform'])   # v13: матрица родителей и своя
        r = NS(tag=tag, layer=layer, id=a.get('id', ''), a=a, st=st, el=el, depth=depth, inst=inst, figma=fig, M=M); r.subs = geom(r)
        if M is not None and not np.allclose(M, np.eye(3)):                       # v13 (map/rules/80 Ч-21): геометрия — в координатах холста
            r.subs = [([tuple(M[:2, :2] @ np.asarray(q, float) + M[:2, 2]) for q in p], c, k) for p, c, k in r.subs]
        r.fill, r.stroke = hexc(st.get('fill', '#000000')), hexc(st.get('stroke', 'none'))
        r.sw = num(st.get('stroke-width', 1), 1) if r.stroke not in (None, 'none') else 0.0
        if M is not None and r.sw: r.sw *= math.sqrt(abs(float(np.linalg.det(M[:2, :2]))))   # v13: толщина линии — под тем же преобразованием
        r.hidden = st['display'] == 'none' or st.get('visibility') == 'hidden'
        r.name, r.type = a.get('data-name') or a.get('label') or r.id, a.get('data-type') or a.get('data-kind') or ''
        r.poly = poly_of([s for s in r.subs if (s[1] or r.fill != 'none') and len(s[0]) >= 3]); r.nv = sum(s[2] for s in r.subs)
        r.valid = all(Polygon(s[0]).is_valid for s in r.subs if len(s[0]) >= 3)
        r.curves = len(re.findall(r'[CcSsQqTtAa]', a.get('d', ''))) if tag == 'path' else int(tag in ('circle', 'ellipse'))
        r.idx, r.anc = len(R), anc; R.append(r)
        for ch in el:
            if isinstance(ch.tag, str): walk(ch, layer, st, depth + 1, inst, fig, M, anc + (r.idx,))
    walk(root, None, {}, 0)
    return root, R

# ------------------------------------------------------------------ модель плана
def clean(V, K, closed):
    """убрать повторы точек, коллинеарные (< 0,5°) вершины и шипы (> 179,5°) между двумя прямыми -> (вершины, виды отрезков, [(точка, почему)])"""
    Q, QK, col = [], [], []
    for p, k in zip(map(tuple, V), K):
        if Q and math.dist(Q[-1], p) < 1e-6: col.append((p, 'повтор точки'))
        else: Q.append(p); QK.append(k)
    if closed and len(Q) > 1 and math.dist(Q[0], Q[-1]) < 1e-6: Q.pop(); QK[0] = QK.pop(); col.append((Q[0], 'повтор точки'))
    i = 0
    while len(Q) > (3 if closed else 2) and i < len(Q):
        if not closed and i in (0, len(Q) - 1): i += 1; continue
        j = (i + 1) % len(Q)
        if QK[i] != 'L' or QK[j] != 'L': i += 1; continue                 # стык с кривой — не вершина ломаной
        a, b, c = Q[i - 1], Q[i], Q[j]; t = turn((b[0] - a[0], b[1] - a[1]), (c[0] - b[0], c[1] - b[1]))
        if t < 0.5 or t > 179.5: col.append((b, f'{t:.2f}°')); Q.pop(i); QK.pop(i); i = max(i - 1, 0)
        else: i += 1
    return Q, QK, col
def clean_pts(pts, closed):
    return clean(pts, ['L'] * len(pts), closed)[0]
def model(root, R, a):
    P = NS(root=root, R=R, notes=[], SRC=False, TX=None, BG=None); vb = [float(v) for v in re.findall(NUM, root.get('viewBox', ''))]
    P.vb = vb if len(vb) == 4 else None; P.W, P.H = (round(vb[2]), round(vb[3])) if P.vb else (0, 0)
    vis = lambda L: [r for r in R if r.layer == L and r.subs and not r.hidden]
    RM, P.GL = vis('rooms'), vis('glass')
    iscol = lambda r: bool(re.match(r'colum', r.id or '', re.I) or re.search(r'colum|колонн', f'{r.type} {r.inst or ""}', re.I))
    iscur = lambda r: bool(re.search(r'curtain|штор', f'{r.id} {r.type} {r.inst or ""}', re.I))
    P.cols, P.curt = [r for r in RM if iscol(r)], [r for r in RM if iscur(r)]
    RM = [r for r in RM if not iscol(r) and not iscur(r)]                   # колонны и шторы — не стены и не наружный контур
    zc, edge, fil = (lambda r: all(s[1] for s in r.subs)), (lambda r: r.stroke in (WALL, GLASS) and r.sw > 0), (lambda r: r.fill != 'none')
    grey = [r for r in RM if not edge(r) and r.fill == WALL and not r.poly.is_empty]
    sw = Counter(round(r.sw, 2) for r in RM if r.stroke == WALL and r.sw > 0 and fil(r))
    T = a.wall_t or (sw.most_common(1)[0][0] if sw else None)
    if not T: T = 6.0; P.notes.append('T не определена — 6 px, задайте --wall-t')
    P.T = T; P.TO = getattr(a, 'outer_wall_px', None) or 2 * T                # толщина фасада: канон 2T; перенос «геометрия как есть» — как у источника
    if P.TO != 2 * T: P.notes.append(f'толщина фасада — --outer-wall-px {fx(P.TO)} px: перенос с решением владельца «геометрия как есть»')
    P.rooms = [r for r in RM if edge(r) and (fil(r) or zc(r) and r.sw < 1.5 * T)]
    P.outer = [r for r in RM if r.stroke == WALL and r.sw >= 1.5 * T and not fil(r) and zc(r)]
    P.free = [r for r in RM if r.stroke == WALL and r.sw > 0 and not fil(r) and not zc(r)]
    P.odd = [r for r in RM if r.stroke not in (None, 'none', WALL, GLASS)]
    isbar = lambda r: r.nv <= 5 and sides(r.poly)[0] <= 2.5 * T
    P.bars, P.wallpolys = [r for r in grey if isbar(r)], [r for r in grey if not isbar(r)]
    P.ops, P.zones, faces = [], [], []
    for r in RM:
        if edge(r) or not fil(r) or r.fill == WALL or r.poly.is_empty: continue
        h = f'{r.id} {r.name} {r.type}'                                     # v007 (АБ4): проём — по типу, без типа — по id; имя не в счёт; тип помещения или зоны — не проём
        if (DOOR_T.search(r.type) if r.type else DOOR_ID.search(r.id or '') or (sides(r.poly)[0] <= 2.5 * T and not re.search(r'room|zone|зон|помещ', r.id or '', re.I))): P.ops.append(r)
        elif P.rooms or re.search(r'zone|зон', h, re.I): P.zones.append(r)
        else: faces.append(r)
    P.open = [z for z in P.zones if re.match(r'room', z.id or '', re.I) or (z.type and not re.search(r'zone|зон|dept|отдел|base|door|двер|window|окн', f'{z.type} {z.id}', re.I))]
    P.faces = not P.rooms and bool(faces)                                   # стены — залитым телом, помещения — заливки
    if P.faces: P.rooms = faces
    ru = unary_union([r.poly for r in P.rooms]) if P.rooms else Polygon()
    P.shell = shell(unary_union([ru] + [r.poly for r in grey + P.ops]) if P.faces else unary_union([ru] + [z.poly for z in P.open]))   # открытые зоны — внутри здания
    gp = []
    for r in P.GL + [r for r in P.rooms if r.stroke == GLASS]:
        if r.stroke == GLASS and r.sw > 0: gp += [band(LineString(p + [p[0]] if c else p), r.sw) for p, c, k in r.subs if len(p) > 1]
        if r.fill == GLASS and not r.poly.is_empty: gp.append(r.poly)
    P.glass = unary_union(gp) if gp else Polygon()
    gt = []                                                                 # v012 (КМ-2): стекло слоя glass — выше слоя rooms: только оно закрывает проём сверху
    for r in P.GL:
        if r.stroke == GLASS and r.sw > 0: gt += [band(LineString(p + [p[0]] if c else p), r.sw) for p, c, k in r.subs if len(p) > 1]
        if r.fill == GLASS and not r.poly.is_empty: gt.append(r.poly)
    P.glass_top = unary_union(gt) if gt else Polygon()
    P.gends = []                                                            # v012 (КМ-2, П3-9): концы линий стекла — проём стеклянной перегородки стоит между ними
    for r in P.GL:
        if r.stroke != GLASS or r.sw <= 0: continue
        for p, c, k in r.subs:
            if c or len(p) < 2: continue
            for e0, e1 in ((p[0], p[1]), (p[-1], p[-2])):
                dv = np.asarray(e0, float) - np.asarray(e1, float); nv = float(np.hypot(*dv))
                if nv > 1e-6: P.gends.append((np.asarray(e0, float), dv / nv, r.sw))
    P.gring = [r for r in P.GL if r.stroke == GLASS and zc(r) and not r.poly.is_empty and r.poly.area >= 0.5 * max(P.shell.area, 1)]
    # наружный контур: серый путь; иначе ось по линии стекла (она у наружного края: сдвиг (TO − w)/2, TO — толщина фасада); иначе оболочка помещений
    P.ring = unary_union([r.poly for r in P.outer]) if P.outer else unary_union(
        [r.poly.buffer(-max(0.0, P.TO - r.sw) / 2, join_style='mitre', mitre_limit=5) for r in P.gring]) if P.gring else P.shell
    P.fac, P.ring_line = ext(P.ring), ext(P.ring if P.outer else P.shell)    # S6 меряет контур не по самому стеклу
    P.ringv = np.array([v for q in parts(P.ring) for v in clean_pts(q.exterior.coords[:-1], True)] or np.zeros((0, 2)))
    P.facade = [r for r in P.free if r.sw >= 1.5 * T]                      # глухие участки смешанного фасада — серые пути 2T
    P.mixed = not P.outer and not P.gring and bool(P.facade)
    wp = [] if P.faces else [band(r.poly.boundary, r.sw) for r in P.rooms]
    wp += [band(r.poly.boundary, r.sw) for r in P.outer] + [band(LineString(p), r.sw) for r in P.free for p, c, k in r.subs if len(p) > 1]
    wp += [r.poly for r in grey] + [r.poly for r in P.GL if r.fill == WALL and not r.poly.is_empty]
    wp += [band(LineString(p), r.sw) for r in P.cols if r.sw > 0 for p, c, k in r.subs if len(p) > 1] + [r.poly for r in P.cols if r.fill != 'none' and not r.poly.is_empty]
    if not P.outer and not P.faces and not P.ring.is_empty: wp.append(band(P.fac, P.TO))    # фасад TO (2T) без серого пути
    P.body = unary_union(wp) if wp else Polygon()
    sv = lambda r: zip(r.subs, r.vxs)
    P.shp = [] if P.faces else [(p, True, r.sw, 'room', r, v) for r in P.rooms for (p, c, k), v in sv(r)]
    P.shp += [(p, True, r.sw, 'outer', r, v) for r in P.outer for (p, c, k), v in sv(r)] + [(p, False, r.sw, 'free', r, v) for r in P.free for (p, c, k), v in sv(r)]
    P.shp += [] if P.outer else [(p, True, P.TO, 'outer', r, v) for r in P.gring for (p, c, k), v in sv(r) if c]
    P.shp += [(p, True, T, 'wallpoly', r, v) for r in P.wallpolys for (p, c, k), v in sv(r)]
    P.rooms_all = P.rooms + ([] if P.faces else P.open)
    meta = json.load(open(a.meta, encoding='utf-8')) if a.meta else {}; rf = meta.get('raw_to_frame') or {}
    est = meta.get('scale_px_per_m_raw') or meta.get('scale_estimate_px_per_m_raw')
    P.scale = a.scale_px_per_m or meta.get('scale_px_per_m') or (est * rf.get('scale', 1) if est else None)
    P.scale_src = None if not P.scale else '--scale-px-per-m' if a.scale_px_per_m else 'meta.json' + (' (оценка)' if 'scale_estimate_px_per_m_raw' in meta else '')
    P.m = P.scale or 6 * T                                                  # 1 м в px фрейма
    tf = a.source_transform or (f"{rf['scale']},0,{rf['tx']},0,{rf['scale']},{rf['ty']}" if 'scale' in rf else None)
    P.tf = [float(v) for v in tf.split(',')] if tf else None
    return P
def at_facade(p, q, P):
    """ребро на наружном контуре одним концом в вершине излома фасада — исключение map/rules/40 §2.4"""
    if P.fac.is_empty or not len(P.ringv) or max(P.fac.distance(Point(p)), P.fac.distance(Point(q))) > 0.6: return False
    return np.hypot(*(P.ringv[None] - np.array([p, q])[:, None]).transpose(2, 0, 1)).min() <= 0.6
def shape(P):
    T, S = P.T, dict(edges=0, short=[], steps=[], izlom=[], col=[], near=[], close=[], zero=0, rect=0, tnode=0)
    CL = [clean([pts[i] for i, _ in vx], [k for _, k in vx], closed) for pts, closed, tc, kind, r, vx in P.shp]
    J, JI = [], []                                                         # v007 (Т3-4, ОВ26): узлы — углы и концы контуров и линий стекла
    for ci, (Q, QK, col) in enumerate(CL): J += [tuple(q) for q in Q]; JI += [ci] * len(Q)
    for gi, r in enumerate(P.GL):
        for p, c, k in r.subs: q = clean_pts(p, c); J += [tuple(z) for z in q]; JI += [-1 - gi] * len(q)
    for zi, z in enumerate(P.zones):                                       # v012 (КМ-13, Н-E1): Т-узел и среди контуров без обводки — открытая зона тоже сосед
        for p, c, k in z.subs: q = clean_pts(p, c); J += [tuple(t_) for t_ in q]; JI += [-100000 - zi] * len(q)
    from scipy.spatial import cKDTree
    KT = cKDTree(np.array(J, float)) if J else None
    tnode = lambda p, ci: KT is not None and any(JI[j] != ci for j in KT.query_ball_point(p, 0.25))   # Т-узел: у соседа здесь угол или конец
    for ci, (pts, closed, tc, kind, r, vx) in enumerate(P.shp):
        Q, QK, col = CL[ci]; tn = [(p, why) for p, why in col if why.endswith('°') and float(why[:-1]) < 0.5 and tnode(p, ci)]
        S['tnode'] += len(tn); S['col'] += [W(p, f'{kind} {r.name}: {why}') for p, why in col if (p, why) not in tn]   # общий узел с соседом — не лишняя вершина
        n = len(Q); m = n if closed else n - 1
        if m < 1: continue
        E = [(Q[(i + 1) % n][0] - Q[i][0], Q[(i + 1) % n][1] - Q[i][1]) for i in range(m)]; L = [math.hypot(*e) for e in E]
        st = [QK[(i + 1) % n] == 'L' for i in range(m)]                        # прямой ли отрезок i (от вершины i к i + 1)
        S['edges'] += sum(st); S['rect'] += kind == 'room' and n == 4 and all(st) and len(r.subs) == 1
        S['near'] += [W(Q[i], f'{kind} {r.name}: {turn(E[i - 1], E[i % m]):.1f}°') for i in (range(n) if closed else range(1, n - 1))
                      if st[i - 1] and st[i % m] and not 3 <= turn(E[i - 1], E[i % m]) <= 177]
        for i in range(m):
            if not st[i]: continue
            p, q = Q[i], Q[(i + 1) % n]; fac = kind != 'outer' and L[i] < T and at_facade(p, q, P)
            w = W(((p[0] + q[0]) / 2, (p[1] + q[1]) / 2), f'{kind} {r.name}: {L[i]:.1f} px' + (' — у примыкания к фасаду' if fac else ''))
            if L[i] < T: S['short'].append((w, fac))
            if L[i] < 0.8: S['close'].append(w); S['zero'] += np.allclose(np.round(p, 1), np.round(q, 1))
            u, v = E[i - 1], E[(i + 1) % m]
            if L[i] < 2 * T and (closed or 0 < i < m - 1) and st[i - 1] and st[(i + 1) % m] and \
                    u[0] * v[0] + u[1] * v[1] >= math.cos(math.radians(3)) * math.hypot(*u) * math.hypot(*v):
                S['steps' if L[i] < tc else 'izlom'].append((w, fac))
    return S
# ------------------------------------------------------------------ общие данные: подписи, бейджи, JSON мест, исходник
def texts(P):
    """подписи: текст, рамка (0,55 кегля на знак); номер помещения — текст в labels вне плашки выноски"""
    if P.TX is None:
        P.TX = []
        for r in P.R:
            if r.tag != 'text' or r.hidden: continue
            s, x, y, t = num(r.st.get('font-size', 16), 16), num(r.a.get('x')), num(r.a.get('y')), ''.join(r.el.itertext()).strip()
            w = 0.55 * s * len(t); x0 = x - {'middle': w / 2, 'end': w}.get(r.st.get('text-anchor'), 0)
            P.TX.append(NS(r=r, t=t, s=s, fill=hexc(r.st.get('fill', '#000000')), fam=r.st.get('font-family', '—'), pt=Point(x, y),
                           box=box(x0, y - 0.72 * s, x0 + w, y + 0.2 * s)))
        LB = [r for r in P.R if r.layer == 'labels' and r.subs and not r.hidden]
        P.plq = [r for r in LB if r.fill != 'none' and not r.poly.is_empty and any(r.poly.contains(t.pt) for t in P.TX)]
        P.lead = [r for r in LB if r.stroke not in (None, 'none') and r.fill == 'none' and any(not s[1] for s in r.subs)]
        for t in P.TX: t.num = t.r.layer == 'labels' and not any(q.poly.contains(t.pt) for q in P.plq)
    return P.TX
def badges(P):
    """рамки бейджей: круглые, самые крупные в icons (≥ 0,8 наибольшей); остальное в icons — глифы; стрелка входа — не бейдж"""
    if P.BG is None:
        ent = lambda r: bool(re.search(r'entr|entry|вход|arrow', r.inst or '', re.I) or r.figma in ENTRY)
        P.entr = {r.inst for r in P.R if r.layer == 'icons' and ent(r)}
        IC = [r for r in P.R if r.layer == 'icons' and not r.hidden and not ent(r)]; D = [r for r in IC if r.subs and not r.poly.is_empty]
        def dia(r):
            x0, y0, x1, y1 = r.poly.bounds; w = x1 - x0
            return w if w > 0 and abs(w - (y1 - y0)) <= 1 and (r.tag in ('circle', 'ellipse') or r.tag == 'rect' and num(r.a.get('rx', r.a.get('ry'))) >= 0.4 * w
                                                                or abs(r.poly.area - math.pi * w * w / 4) <= 0.08 * r.poly.area) else 0.0
        top = max(map(dia, D), default=0); B = [r for r in D if top and dia(r) >= 0.8 * top]
        G = {r.inst: r for r in P.R if r.depth == 2}
        def kind(r):                                                       # v4: тип бейджа — по id глифа гайдлайна, иначе по id и data-kind экземпляра
            k = GLYPH_KIND.get(r.figma or '')
            if k: return k
            g = G.get(r.inst); h = f"{r.inst or ''} {r.id} " + (f"{g.a.get('data-kind', '')} {g.a.get('data-type', '')}" if g is not None else '')
            return 'wc' if re.search(r'\bwc\b|toilet|туалет|сануз', h, re.I) else 'lift' if re.search(r'lift|лифт', h, re.I) else \
                'stair' if re.search(r'stair|лестн', h, re.I) else 'other'
        P.BG = NS(IC=IC, B=B, gl=[r for r in D if r not in B], dia=dia, kind=kind)
    return P.BG
def room_at(P, pt):
    """наименьшее помещение или открытая зона, где точка; нет — None"""
    h = [q for q in P.rooms_all if q.poly.contains(Point(pt))]
    return min(h, key=lambda q: q.poly.area) if h else None
def places(a):
    if not a.places_json: return None
    pj = json.load(open(a.places_json, encoding='utf-8'))
    return [p for p in (pj.get('places', []) if isinstance(pj, dict) else pj) if isinstance(p, dict)]
def _xy(v):
    """точка [x, y] или {x, y}; иначе None: номер места строкой («201-1») — не координата (Т3-9)"""
    if isinstance(v, dict): v = [v.get('x'), v.get('y')]
    if isinstance(v, (list, tuple)) and len(v) >= 2 and all(isinstance(c, (int, float)) and not isinstance(c, bool) and math.isfinite(c) for c in v[:2]):
        return [float(v[0]), float(v[1])]
    return None
def _dc(p):
    try: return [float(z) for z in np.mean(np.asarray(p['desk'], float)[:, :2], axis=0)] if p.get('desk') and len(p['desk']) >= 3 else None
    except (TypeError, ValueError, IndexError): return None
def seat_pt(p):
    """точка места, px картинки: seat, если это точка; иначе x, y записи; иначе центр стола"""
    return _xy(p.get('seat')) or _xy([p.get('x'), p.get('y')]) or _xy(p.get('centre')) or _dc(p)
def centre_pt(p):
    """центр стола, px картинки: centre или середина многоугольника стола"""
    return _xy(p.get('centre')) or _dc(p)
def chair_pt(p):
    """v13: точка стула записи (map/rules/83 §5: x, y; или seat, если это точка) — без запасного центра стола; нет — None"""
    return _xy(p.get('seat')) or _xy([p.get('x'), p.get('y')])
def keys_check(pl):
    """v13 (map/rules/80 Ч-21, Ч-29; map/rules/83 §5): записей N > 0, а ни у одной нет desk и centre — строка причины; иначе None"""
    if not pl or any(p.get('desk') or centre_pt(p) for p in pl): return None
    ks = sorted({k for p in pl for k in p})
    return (f'записей {len(pl)}, столов 0: ключи записи не по схеме map/rules/83 §5 (desk, centre, x, y); в записях — ' + ', '.join(ks[:12]) + ('…' if len(ks) > 12 else ''))
PKEYS = ('number', 'n', 'num', 'seat_number', 'label', 'name', 'id')
def pnum(p, i=0):
    """номер места строкой: number, n, … id; у записи артефакта 3 номер — в seat (render_variant_c), если seat — не точка"""
    for k in PKEYS:
        if p.get(k) not in (None, ''): return str(p[k])
    if p.get('seat') not in (None, '') and _xy(p.get('seat')) is None: return str(p['seat'])
    return f'#{i + 1}'
def source(P, a):
    """исходник: нейтральная тёмная тушь (порог Оцу; цветные обводки и метки — не стена, map/rules/30 §1.5), расстояния до неё"""
    if P.SRC is False:
        P.SRC = None
        if a.source_png and P.tf:
            ta, tb, tx, tc, td, ty = P.tf; Ai = np.linalg.inv([[ta, tb, tx], [tc, td, ty], [0, 0, 1]])
            im = Image.open(a.source_png).convert('RGB'); c = np.asarray(im).astype(int); g = np.asarray(im.convert('L'))
            h = np.bincount(g.ravel(), minlength=256) / g.size; w, mu = np.cumsum(h), np.cumsum(h * np.arange(256))
            lvl = a.source_dark or int(np.clip(np.argmax((mu[-1] * w - mu) ** 2 / (w * (1 - w) + 1e-12)), 100, 215))
            dark = (g < lvl) & (c.max(2) - c.min(2) < 40); mask = None; massif = None; mmeta = None
            if a.wall_mask:                                                    # маска тела стены исходника (вектор): > 127 — стена; 65…127 — массив (v008, wm1)
                mv = np.asarray(Image.open(a.wall_mask).convert('L')); mk = mv > 127
                if mk.shape == g.shape: mask = mk; massif = (mv > 64) & ~mk; mmeta = mask_recipe(a.wall_mask, mv)
                else: P.notes.append(f'--wall-mask {mk.shape[::-1]} не равна исходнику {g.shape[::-1]} — не используется')
            P.SRC = NS(Ai=Ai, M=[Ai[0, 0], Ai[0, 1], Ai[1, 0], Ai[1, 1], Ai[0, 2], Ai[1, 2]], A2=np.array(P.tf).reshape(2, 3), k=math.sqrt(abs(ta * td - tb * tc)), rgb=c.astype(np.uint8),
                       lvl=lvl, dark=dark, dist=ndimage.distance_transform_edt(~dark),
                       mask=mask, mdist=ndimage.distance_transform_edt(~mask) if mask is not None else None, cl={}, X=None, massif=massif, mmeta=mmeta,
                       light=(g < max(lvl, 220)) & (c.max(2) - c.min(2) < 40),           # v4: тонкие серые линии — диагонали шахт (Ч-33)
                       colour=(g < lvl) & (c.max(2) - c.min(2) >= 40), CW=None)          # v13 (строка 387): цветная тушь — тёмное, но не нейтральное (порог нейтрали — тот же 40)
    return P.SRC
MASK_BRIDGE = 'dxf3'                                                         # решение владельца 14.10.2026 (ОЧ-25): маска Ч-10 карты по мосту из DXF — dxf3; растр, скан — wm1
def is_bridge(P):
    """карта по мосту: корень SVG — data-generator="bridge_convert …" (bridge/bridge_convert.py)"""
    return bool(re.search(r'<svg[^>]*\bdata-generator="bridge_convert', (getattr(P, 'text', '') or '')[:20000], re.S))
def mask_recipe(path, mv):
    """рецепт маски тела стены (v008, Н23, Т4-1): <маска>.json построителя unspot_map.wall_mask; хеш значений маски сверяется -> dict"""
    a_ = np.asarray(mv, np.uint8); h = hashlib.sha256(f'{a_.shape[1]}x{a_.shape[0]}:'.encode() + a_.tobytes()).hexdigest()
    try: m = json.load(open(os.path.splitext(path)[0] + '.json', encoding='utf-8'))
    except (OSError, ValueError): m = None
    if not isinstance(m, dict) or not m.get('recipe'): return dict(recipe=None, sha=h, ok=False, why='маска без рецепта (нет <маска>.json построителя unspot_map.wall_mask) — маска по рецепту, а не подбором')
    if m.get('mask_sha256') != h: return dict(recipe=m.get('recipe'), sha=h, ok=False, why=f'маска не та, что в рецепте {m.get("recipe")}: SHA-256 значений {h[:12]}… ≠ {str(m.get("mask_sha256"))[:12]}…')
    return dict(recipe=m['recipe'], sha=h, ok=True, why='', t_m=m.get('t_m'))
def pic(P, a):
    """px картинки на px фрейма: JSON мест — в px картинки (map/rules/82 §0)"""
    f = a.artefact3_png or a.final_png
    if not f or not P.vb: return 1.0, 1.0
    w, h = Image.open(f).size; return w / P.vb[2], h / P.vb[3]
def desk_blobs(img, rgb, tol):
    """пятна столов по маске заливки до номеров (строка 181; Е13, ОВ11): номер места поверх заливки — дыра маски, дыры заполняются;
    -> (метки, крупные пятна, всего пятен, индексы ближайшего пятна для центра места не дальше 6 px)"""
    c = np.asarray(img.convert('RGB')).astype(int); m = ndimage.binary_fill_holes(np.all(np.abs(c - np.array(rgb)) <= np.array(tol), axis=2))
    lab, n = ndimage.label(m); sz = ndimage.sum(m, lab, range(1, n + 1)) if n else np.zeros(0)
    keep = {i + 1 for i, s_ in enumerate(sz) if s_ >= max(20, 0.25 * float(np.median(sz)))}
    d, ind = ndimage.distance_transform_edt(lab == 0, return_indices=True)
    return lab, keep, n, (d, ind)
def blobs(img, rgb, tol):
    """пятна цвета rgb ± tol: метки и маска; мелкие (< 25 % медианы, < 20 px) отброшены"""
    c = np.asarray(img.convert('RGB')).astype(int); m = np.all(np.abs(c - np.array(rgb)) <= np.array(tol), axis=2)
    lab, n = ndimage.label(m); sz = ndimage.sum(m, lab, range(1, n + 1)) if n else np.zeros(0)
    return lab, {i + 1 for i, s in enumerate(sz) if s >= max(20, 0.25 * float(np.median(sz)))}, n

# ------------------------------------------------------------------ Ч-01 – Ч-05: исходник и заявка
def c01(P, a, S):
    nm = 'Исходник: оригинал, хеш не изменён'
    if not a.source_png: return skip('Ч-01', nm, 'проверяется процедурой: хеш артефакта 1 = imageHash исходника (map/rules/30 §1.1); исходник не дан')
    h = hashlib.sha1(open(a.source_png, 'rb').read()).hexdigest()
    if a.source_hash: return row('Ч-01', nm, f'sha1 {h[:16]}…', f'= {a.source_hash[:16]}…', 'pass' if h.startswith(a.source_hash.lower()) else 'fail')
    return skip('Ч-01', nm, 'проверяется процедурой: сверить sha1 с imageHash в отчёте (map/rules/30 §1.1); эталон хеша — --source-hash', val=f'sha1 {h[:16]}…')
def c02(P, a, S):
    return skip('Ч-02', 'Состав страницы PDF в отчёте', 'проверяется процедурой: таблица картинок с поворотами, слов и аннотаций страницы — в отчёте прохода (отчёт клиент В §3.1)')
def c03(P, a, S):
    nm = 'Масштаб двумя способами: заданный и по столам JSON'
    ds = [max(sides(Polygon(p['desk']))[:2]) / max(p['size_m']) / pic(P, a)[0] for p in places(a) or [] if p.get('desk') and p.get('size_m')]
    if not ds or not P.scale: return skip('Ч-03', nm, 'проверяется процедурой: второй способ, map/rules/30 §2.2' + ('; масштаб не дан' if not P.scale else '; в JSON мест нет столов с size_m'), s=['S12.scale'])
    k = float(np.median(ds)); d = abs(k / P.scale - 1)
    return row('Ч-03', nm, f'{fx(P.scale, 2)} px/м ({P.scale_src}) и {fx(k, 2)} по столам: {pc(d)}', '≤ 10 %; иначе S4 и метры неверны', 'pass' if d <= 0.1 else 'fail', s=['S12.scale'])
def c04(P, a, S):
    nm = 'Места по легенде = места в JSON'; pl = places(a)
    if a.legend_seats is None or pl is None:
        return skip('Ч-04', nm, 'проверяется процедурой: число мест из легенды листа, отчёт клиент В §3.2' + (f'; мест в JSON {len(pl)}' if pl is not None else ''))
    return row('Ч-04', nm, f'легенда {a.legend_seats}, JSON {len(pl)}', 'равно', 'pass' if a.legend_seats == len(pl) else 'fail')
def c05(P, a, S):
    nm = 'Номера мест: без дублей и пропусков'; pl = places(a)
    if pl is None: return skip('Ч-05', nm, 'проверяется процедурой: номера мест — из текстового слоя исходника; JSON мест не дан')
    key = next((k for k in ('number', 'num', 'seat_number', 'label', 'name', 'id') if any(k in p for p in pl)), None)
    v = [str(p.get(key, '')) for p in pl]; dup = [x for x, n in Counter(v).items() if n > 1]; grp = defaultdict(list)
    for x in v:
        if (m := re.fullmatch(r'(.*?)(\d+)', x)): grp[m[1]].append(int(m[2]))
    gap = [f'{k}{i}' for k, L in grp.items() for i in sorted(set(range(min(L), max(L) + 1)) - set(L))]
    return row('Ч-05', nm, f'поле «{key}»: {len(v)}, дублей {len(dup)}, пропусков {len(gap)}; сверка с текстовым слоем — процедурой', '0 дублей; пропуск — look',
               'fail' if dup else 'look' if gap else 'pass', [W(None, f'дубль {x}') for x in dup] + [W(None, f'пропуск {x}') for x in gap])

# ------------------------------------------------------------------ Ч-06 – Ч-13: стены и контур
def c06(P, a, S):
    nm = 'Удвоение стен: сырая длина осей / эффективная'
    if P.faces: return skip('Ч-06', nm, 'стены — залитым полигоном: осей нет, удвоение не определено — см. Ч-27')
    L = [r.poly.boundary for r in P.rooms + P.outer] + [LineString(p) for r in P.free for p, c, k in r.subs if len(p) > 1]
    if not L: return skip('Ч-06', nm, 'путей стен нет')
    U = unary_union(L); eff = U.buffer(1.5, cap_style='flat').area / 3
    return row('Ч-06', nm, f'{fx(U.length / eff, 2)}; без слияния общих осей — {fx(sum(g.length for g in L) / eff, 2)}', '≤ 1,3; эффективная — полоса ±1,5 px / 3',
               'pass' if U.length / eff <= 1.3 else 'fail')
def c07(P, a, S):
    nm = 'Рёбра короче T; доля > 2 % — сборка по маске'; n, sh = S['edges'], S['short']
    if not n: return skip('Ч-07', nm, 'контуров стен нет — см. Ч-27', s=['S3.short_edges'])
    bad = [w for w, f in sh if not f]; k = len(sh) / n
    return row('Ч-07', nm, f'{len(sh)} из {n} ({pc(k, 2)}), у фасада {len(sh) - len(bad)}' + ('; > 2 % — сборка по маске' if k > 0.02 else ''), f'0 при T = {fx(P.T)} px; у фасада — look',
               'fail' if bad or k > 0.02 else 'look' if sh else 'pass', [w for w, f in sh], s=['S3.short_edges'])
def c08(P, a, S):
    nm = 'Ступеньки и изломы между параллельными рёбрами'; st, iz = S['steps'], S['izlom']; bad = [w for w, f in st if not f]
    if not S['edges']: return skip('Ч-08', nm, 'контуров стен нет — см. Ч-27', s=['S3.steps', 'S3.izloms'])
    return row('Ч-08', nm, f'ступенек {len(st)}, у фасада {len(st) - len(bad)}; изломов {len(iz)}', 'ступенек 0; излом < 2T — есть ли на исходнике, look',
               'fail' if bad else 'look' if st or iz else 'pass', [w for w, f in st + iz], s=['S3.steps', 'S3.izloms'])
def c09(P, a, S):
    nm = 'Коллинеарные вершины, рёбра < 0,8 px и нулевые при 0,1 px'; c, z, nr = S['col'], S['close'], S['near']
    if not S['edges']: return skip('Ч-09', nm, 'контуров стен нет — см. Ч-27', s=['S2.collinear', 'S3.near_collinear'])
    return row('Ч-09', nm, f'коллинеарных (< 0,5°), шипов, повторов {len(c)}; рёбер < 0,8 px {len(z)}, нулевых при 0,1 px {S["zero"]}; почти коллинеарных (0,5–3°) {len(nr)}' +
               (f'; Т-узлов соседа {S["tnode"]} — не лишние' if S.get('tnode') else ''),
               '0; почти коллинеарные — look', 'fail' if c or z else 'look' if nr else 'pass', c + z + nr, s=['S2.collinear', 'S3.near_collinear'])
def _closed(src, px):
    """тушь, закрытая на толщину класса (px исходника): полая стена — сплошное тело (Ч-10 v4); (маска, расстояние до неё)"""
    k = max(3, int(math.ceil(1.25 * px)) | 1)
    if k not in src.cl:
        try:
            import cv2; m = cv2.morphologyEx(src.dark.astype(np.uint8), cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))) > 0
        except ImportError:
            y, x = np.ogrid[-(k // 2):k // 2 + 1, -(k // 2):k // 2 + 1]; m = ndimage.binary_closing(src.dark, x * x + y * y <= (k // 2) ** 2) | src.dark
        src.cl[k] = (m, ndimage.distance_transform_edt(~m))
    return src.cl[k]
def _mid_off(M, q, nr, R):
    """|сдвиг| точек q (px исходника) от середины тела M по нормали nr: тело под точкой или ближайшее в пределах R; шире окна — nan"""
    o = np.arange(-R, R + 0.25, 0.5); xy = q[:, None, :] + o[None, :, None] * nr[None, None, :]; H, Wd = M.shape
    ix, iy = np.floor(xy[..., 0]).astype(int), np.floor(xy[..., 1]).astype(int); ok = (ix >= 0) & (iy >= 0) & (ix < Wd) & (iy < H)
    v = np.zeros(ix.shape, bool); v[ok] = M[iy[ok], ix[ok]]; out = np.full(len(q), np.nan); c = len(o) // 2
    for i, rw in enumerate(v):
        idx = np.flatnonzero(rw)
        if not len(idx): continue
        j = idx[np.argmin(np.abs(idx - c))]; lo = hi = j
        while lo > 0 and rw[lo - 1]: lo -= 1
        while hi < len(rw) - 1 and rw[hi + 1]: hi += 1
        if lo > 0 and hi < len(rw) - 1: out[i] = abs((o[lo] + o[hi]) / 2)
    return out
def src_q(P, src):
    """v13: q — мм на px исходника = 1000 · (px холста на px исходника) / (px холста на м); масштаб не дан — None"""
    return 1000.0 * src.k / P.m if P.scale else None
def colour_walls(P, a, src):
    """v13 (map/rules/80 Ч-10, Ч-11; строка 387): цветная тушь исходника против маски нейтральной туши, закрытой на толщину класса (мера Ч-10 растра),
    и против наших стен -> dict(всего, не покрыто маской, из них у наших стен в d₃) в px исходника"""
    if src.CW is None:
        H, Wd = src.dark.shape; m = _closed(src, P.T / src.k)[0] | _closed(src, 2 * P.T / src.k)[0]
        un = src.colour & ~m; d3 = max(3.0 / src.k, 3.0)
        near = ndimage.distance_transform_edt(~raster([P.body], Wd, H, src.M)) <= d3
        src.CW = dict(total=int(src.colour.sum()), uncovered=int(un.sum()), near=int((un & near).sum()), d3=d3)
    return src.CW
def cw_note(cw, src):
    return (f'цветные стены (--colored-walls), маски --wall-mask нет: цветной туши {cw["total"]} px исходника, не покрыто маской нейтральной туши '
            f'{cw["uncovered"]} px, из них у наших стен (в d₃ = {fx(cw["d3"])} px исходника) — {cw["near"]} px; мера по нейтральной туши цветные стены не видит — '
            'look, не fail (решение владельца 15.10.2026, №2, строка 387)')
def c10(P, a, S):
    vec = a.source_kind == 'vector'
    nm = 'Точность: наши стены ' + ('на теле стены исходника (вектор)' if vec else 'на теле стены исходника — тушь, закрытая на толщину класса: d₂ и d₃ или ½ толщины (растр)'); src = source(P, a)
    if not src: return skip('Ч-10', nm, 'нужны --source-png и --source-transform (или --meta)', s=['S13.precision'])
    if vec and src.mask is None:
        return skip('Ч-10', nm, 'векторный исходник: мера map/rules/80 — наши стены на теле стены исходника; дайте --wall-mask (маска тела стены в px исходника): '
                    'тушь растра на векторном листе — ещё мебель и штриховка', s=['S13.precision'])
    opn = unary_union([r.poly.buffer(0.5) for r in P.ops]) if P.ops else Polygon(); H, Wd = src.dark.shape
    d2, d3 = max(2.0 / src.k, 2.0), max(3.0 / src.k, 3.0)                     # v13: px исходника — max(2 px холста, 2q мм), max(3 px холста, 3q мм) (map/rules/80 Ч-10)
    q_mm = src_q(P, src); coarse = q_mm is not None and q_mm >= Q_COARSE_MM; th1, th2 = C10_COARSE if coarse else C10_FINE
    inner = unary_union([r.poly.boundary for r in P.rooms] + [LineString(p) for r in P.free for p, c, k in r.subs if len(p) > 1])
    tot = s1 = s2 = 0.0; runs = []; offs = []
    for geo, t in ((inner.difference(P.ring_line.buffer(1.0)).difference(opn), P.T), (P.ring_line.difference(opn), 2 * P.T)):
        M, D = (src.mask, src.mdist) if vec else _closed(src, t / src.k)        # v4: растр — тело стены из туши, закрытой на толщину класса
        for ln in lines(geo):
            n = max(2, int(ln.length) + 1); xy = shapely.get_coordinates(shapely.line_interpolate_point(ln, np.linspace(0, ln.length, n)))
            q = xy @ src.Ai[:2, :2].T + src.Ai[:2, 2]; ix, iy = np.floor(q[:, 0]).astype(int), np.floor(q[:, 1]).astype(int)
            inb = (ix >= 0) & (iy >= 0) & (ix < Wd) & (iy < H); d = np.full(n, np.inf); d[inb] = D[iy[inb], ix[inb]]; half = t / src.k / 2
            ok1 = d <= (0.5 if vec else max(d2, half)); ok2 = d <= (3.0 if vec else max(d3, half))
            tot += ln.length; s1 += ln.length * ok1.mean(); s2 += ln.length * ok2.mean(); e = np.flatnonzero(np.diff(np.r_[0, (~ok2).astype(int), 0]))
            runs += [((j - i) * ln.length / (n - 1), xy[(i + j - 1) // 2]) for i, j in zip(e[::2], e[1::2]) if (j - i) * ln.length / (n - 1) > P.m]
            cs = np.asarray(ln.coords, float)                                    # справочно: ось от середины тела стены (Г2-1)
            for p0, p1 in zip(cs[:-1], cs[1:]):
                L = math.dist(p0, p1)
                if L < 2: continue
                u = (p1 - p0) / L; k = max(1, int(L // 3)); pts = p0 + np.outer((np.arange(k) + 0.5) / k * L, u)
                ns = src.Ai[:2, :2] @ np.array([-u[1], u[0]]); ns = ns / (np.hypot(*ns) or 1.0)
                offs.append(_mid_off(M, pts @ src.Ai[:2, :2].T + src.Ai[:2, 2], ns, t / src.k + 4) * src.k / P.m)
    p1, p2 = (s1 / tot, s2 / tot) if tot else (0.0, 0.0); runs.sort(key=lambda z: -z[0]); wh = [W(p, f'стена без опоры {fx(L / P.m)} м') for L, p in runs]
    deep, rec = [], ''
    if vec:                                                                 # v008: маска по рецепту — рецепт и хеш в строке; стена внутри массива — look (Н24, Т4-2)
        mm = src.mmeta or {}; rec = f'; маска: рецепт {mm.get("recipe")}, SHA-256 значений {mm.get("sha", "")[:16]}…' if mm.get('ok') else f'; {mm.get("why", "маска без рецепта")}'
        if src.massif is not None and src.massif.any():
            Dm = ndimage.distance_transform_edt(src.massif)                 # глубина в массиве за полосой T; градиент — от грани внутрь
            for ln in lines(inner.difference(opn)):
                cs = np.asarray(ln.coords, float)
                for q0, q1 in zip(cs[:-1], cs[1:]):
                    L = math.dist(q0, q1)
                    if L < 0.5 * P.m: continue
                    n = int(L) + 1; xy = q0 + np.outer(np.linspace(0, 1, n), q1 - q0); q = xy @ src.Ai[:2, :2].T + src.Ai[:2, 2]
                    ix, iy = np.floor(q[:, 0]).astype(int), np.floor(q[:, 1]).astype(int); inb = (ix >= 1) & (iy >= 1) & (ix < Wd - 1) & (iy < H - 1)
                    u = src.Ai[:2, :2] @ ((q1 - q0) / L); u = u / (np.hypot(*u) or 1.0); bad = np.zeros(n, bool)
                    j = np.flatnonzero(inb); j = j[src.massif[iy[j], ix[j]] & (src.mdist[iy[j], ix[j]] > 0.5)]
                    if not len(j): continue
                    gx = Dm[iy[j], ix[j] + 1] - Dm[iy[j], ix[j] - 1]; gy = Dm[iy[j] + 1, ix[j]] - Dm[iy[j] - 1, ix[j]]; gn = np.hypot(gx, gy)
                    bad[j] = (gn > 0) & (np.abs(gx * u[0] + gy * u[1]) < 0.34 * np.where(gn > 0, gn, 1))   # вдоль грани (±20°): стена ушла с грани внутрь массива
                    e = np.flatnonzero(np.diff(np.r_[0, bad.astype(int), 0]))
                    deep += [((jj - ii) * L / (n - 1), xy[(ii + jj - 1) // 2]) for ii, jj in zip(e[::2], e[1::2]) if (jj - ii) * L / (n - 1) >= 0.5 * P.m]
        deep.sort(key=lambda z: -z[0])
    of = np.concatenate(offs) if offs else np.zeros(0); of = of[np.isfinite(of)]
    mid = (f'; справочно: ось от середины тела — медиана {fx(100 * float(np.median(of)))} см, в пределах 6 см — {pc(float((of <= 0.06).mean()))}' +
           ('' if P.scale else ' (1 м ≈ 6T)')) if len(of) else ''
    if vec:
        dw = [W(p, f'стена внутри массива ядра или пилона глубже полосы T от грани: {fx(L / P.m)} м') for L, p in deep]
        nr = [] if (src.mmeta or {}).get('ok') else [W(None, (src.mmeta or {}).get('why', 'маска без рецепта'))]
        if (src.mmeta or {}).get('ok') and is_bridge(P) and str(src.mmeta.get('recipe')) != MASK_BRIDGE:   # решение владельца 14.10.2026 (ОЧ-25): карта по мосту — dxf3
            nr.append(W(None, f'карта по мосту из DXF: маска Ч-10 по умолчанию — {MASK_BRIDGE} (bridge/wall_mask_from_dxf.py --recipe {MASK_BRIDGE}; решение владельца '
                              f'14.10.2026, ОЧ-25); рецепт {src.mmeta.get("recipe")} — не по умолчанию'))
            rec += f'; карта по мосту — маска по умолчанию {MASK_BRIDGE}'
        return row('Ч-10', nm, f'{pc(p1)} на теле стены, {pc(p2)} в 3 px из {fx(tot / P.m)} м; без опоры длиннее 1 м — {len(runs)}; внутри массива от 0,5 м — {len(dw)}' + mid + rec,
                   f'на теле стены ≥ 95 % (map/rules/80); стена внутри массива, маска без рецепта и у карты по мосту маска не {MASK_BRIDGE} — look', 'fail' if p1 < 0.95 else 'look' if dw or nr else 'pass',
                   nr + dw + (wh if p1 < 0.95 or not (dw or nr) else []), s=['S13.precision'])
    qs = (f'q = {fx(q_mm)} мм/px' if q_mm is not None else 'q не известно (масштаб не дан) — пороги обычного растра') + f'; d₂ = {fx(d2 * src.k)} px холста, d₃ = {fx(d3 * src.k)} px холста'
    val = f'{pc(p1)} в d₂, {pc(p2)} в d₃ из {fx(tot / P.m)} м ({qs}; тёмное < {src.lvl}, закрытие на толщину класса); без опоры длиннее 1 м — {len(runs)}' + mid
    thr = (f'd₂ ≥ {pc(th1, 0)} и d₃ ≥ {pc(th2, 0)}' + (' — растр с q ≥ 100 мм/px (строка 358); куски без опоры длиннее 1 м — кропы с вердиктом' if coarse else '') +
           '; d₂ = max(2 px холста, 2q мм), d₃ = max(3 px холста, 3q мм) (map/rules/80); цветные стены без --wall-mask — look (строка 387)')
    ok = p1 >= th1 and p2 >= th2; st = 'pass' if ok and not (coarse and runs) else 'look' if ok else 'fail'
    if getattr(a, 'colored_walls', False) and src.mask is None:              # v13 (строка 387): признак «цветные стены», готовой маски нет — look, не fail, число в отчёт
        cw = colour_walls(P, a, src); val += '; ' + cw_note(cw, src); st = 'look'; wh = [W(None, cw_note(cw, src))] + wh
    return row('Ч-10', nm, val, thr, st, wh, s=['S13.precision'])
def c11(P, a, S):
    nm = 'Стены исходника дальше толщины от наших: куски ≥ 0,5 м'; src = source(P, a)
    if not src: return skip('Ч-11', nm, 'нужны --source-png и --source-transform (или --meta)', s=['S13.coverage'])
    usem = a.source_kind == 'vector' and src.mask is not None
    base = src.mask if usem else ndimage.binary_closing(src.dark, np.ones((3, 3)))
    t = P.T / src.k; dn = ndimage.distance_transform_edt(~raster([P.body], src.dist.shape[1], src.dist.shape[0], src.M))
    lab, n = ndimage.label(base & (dn > t), structure=np.ones((3, 3))); Lm, out = 0.5 * P.m / src.k, []
    for i, sl in enumerate(ndimage.find_objects(lab)):                     # вытянутый кусок: длина ≥ 0,5 м, ширина 1,5 px … 4T по главным осям
        if max(sl[0].stop - sl[0].start, sl[1].stop - sl[1].start) < 0.7 * Lm: continue
        ys, xs = np.nonzero(lab[sl] == i + 1); q = np.c_[xs + sl[1].start + .5, ys + sl[0].start + .5]
        e = np.linalg.eigvalsh(np.cov(q.T)); L, w = math.sqrt(12 * max(e[1], 0)), math.sqrt(12 * max(e[0], 0))
        if L >= Lm and 1.5 <= w <= 4 * t: out.append((L * src.k / P.m, src.A2[:, :2] @ q.mean(0) + src.A2[:, 2]))
    out.sort(key=lambda z: -z[0])
    near = P.shell.buffer(P.m) if not P.shell.is_empty else None              # поле листа — дальше 1 м за оболочкой здания
    ins = [(L, c) for L, c in out if near is None or near.contains(Point(c))]; field = len(out) - len(ins)
    val = ('тело стены (--wall-mask)' if usem else 'нейтральная тушь') + f': кусков {len(ins)}, из них ≥ 1 м — {sum(L >= 1 for L, c in ins)}' + \
          (f'; длиннейший {fx(ins[0][0])} м' if ins else '') + (f'; на поле листа за контуром — ещё {field}, в список не идут' if field else '')
    wh = [W(c, f'кусок {fx(L)} м') for L, c in ins]; st = 'look' if ins else 'pass'
    if getattr(a, 'colored_walls', False) and src.mask is None:              # v13 (строка 387): цветные стены до готовой маски — look, число непокрытой цветной туши
        cw = colour_walls(P, a, src); val += '; ' + cw_note(cw, src); st = 'look'; wh = [W(None, cw_note(cw, src))] + wh
    return row('Ч-11', nm, val, 'список — look: пропущенная стена, стена толще класса или мебель; цветные стены без --wall-mask — look и число (строка 387)', st, wh, s=['S13.coverage'])
def c12(P, a, S):
    wr = ([] if P.faces else P.rooms) + P.outer + P.free + P.gring + P.wallpolys; arc = [r for r in wr if r.curves]; nm = 'Дуги в стенах: каждая — кроп К-08'
    if arc: return row('Ч-12', nm, f'путей с кривыми {len(arc)}, кривых {sum(r.curves for r in arc)}', 'каждая дуга — кроп К-08 с вердиктом (map/rules/80)', 'look',
                       [W(at(r), f'{r.name}: кривых {r.curves}') for r in arc])
    return row('Ч-12', nm, f'кривых нет ни в одном из {len(wr)} путей стен', 'скруглённые стены исходника — проверить глазами', 'look')
def c13(P, a, S):
    src = P.outer or P.gring; rings = [p for r in src for p, c, k in r.subs if c] if src else [list(q.exterior.coords)[:-1] for q in parts(P.shell)]
    if not rings: return skip('Ч-13', 'Звенья наружного контура < 1 px', 'наружного контура нет')
    bad = []
    for p in rings:
        q = np.array(p + [p[0]]); d = np.hypot(*np.diff(q, axis=0).T); bad += [W((q[i] + q[i + 1]) / 2, f'звено {d[i]:.2f} px') for i in np.flatnonzero(d < 1.0)]
    what = 'серый путь' if P.outer else 'линия стекла' if P.gring else 'оболочка помещений'
    return cnt('Ч-13', 'Звенья наружного контура < 1 px', bad, val=f'{what}: точек {sum(map(len, rings))}, звеньев < 1 px {len(bad)}')

# ------------------------------------------------------------------ Ч-14 – Ч-18: помещения
def c14(P, a, S):
    T, rs, nm = P.T, P.rooms, 'Помещения валидны, без накладок, щели < 0,5 %'
    if not rs: return skip('Ч-14', nm, 'помещений нет', s=['S5.overlaps', 'S5.gaps'])
    G = [r.poly for r in rs]; tree = STRtree(G); ov, nest = [], []
    for i, g in enumerate(G):
        for j in (int(j) for j in tree.query(g) if j > i):
            if (x := g.intersection(G[j])).area > T * T / 4:
                (nest if x.area >= 0.98 * min(g.area, G[j].area) else ov).append(W(x.representative_point().coords[0], f'{rs[i].name} × {rs[j].name}: {fx(x.area, 0)} px²'))
    A = P.ring.area or 1.0; cov = unary_union(G + ([r.poly for r in P.wallpolys + P.bars + P.ops] if P.faces else [z.poly for z in P.open]))
    col = [r.poly for r in P.cols if not r.poly.is_empty] + [band(LineString(p), r.sw) for r in P.cols if r.sw > 0 for p, c, k in r.subs if len(p) > 1]
    gap, out_ = P.ring.difference(unary_union([cov] + col)), cov.difference(P.ring.buffer(0.5)); gp = sorted([q for q in parts(gap) if q.area > T * T], key=lambda q: -q.area)   # v007: колонна — не щель
    inv = [W(at(r), f'{r.name}: контур самопересекается') for r in rs if not r.valid]
    return row('Ч-14', nm, f'невалидных {len(inv)}; накладок {len(ov)}, вложенных {len(nest)}; щели {fx(gap.area, 0)} px² ({pc(gap.area / A, 3)}), за контуром {fx(out_.area, 0)} px²' +
               (f'; колонн в покрытии {len(P.cols)}' if P.cols else ''),
               f'0; 0 (допуск T²/4); < 0,5 %; вложенное и щель > T² — look', 'fail' if inv or ov or max(gap.area, out_.area) / A >= 0.005 else 'look' if nest or gp else 'pass',
               inv + ov + nest + [W(q.representative_point().coords[0], f'щель {fx(q.area, 0)} px²') for q in gp], s=['S5.overlaps', 'S5.gaps'])
def c15(P, a, S):
    rs = P.rooms_all
    if not rs: return skip('Ч-15', 'Самое большое помещение', 'помещений нет', s=['S5.largest'])
    big = max(rs, key=lambda r: r.poly.area); sh = big.poly.area / (P.ring.area or 1.0)
    st = 'pass' if sh <= 0.3 else 'look' if not big.type or OPEN.search(big.type) else 'fail'
    return row('Ч-15', 'Самое большое помещение ≤ 30 % этажа', f'{big.name} ({big.type or "тип?"}): {pc(sh)}', '≤ 30 %; опенспейс, коридор — look', st,
               [] if st == 'pass' else [W(at(big), big.name)], s=['S5.largest'])
def c16(P, a, S):
    nm = 'Осколки < 0,5 м², кроме шахт и ниш'
    if not P.scale or not P.rooms: return skip('Ч-16', nm, 'нет масштаба: --scale-px-per-m или --meta' if P.rooms else 'помещений нет', s=['S4.fragments'])
    m2 = P.scale ** 2; small = sorted([r for r in P.rooms_all if r.poly.area < 0.5 * m2], key=lambda r: r.poly.area)
    ok = [r for r in small if SHAFT.search(f'{r.type} {r.name} {r.id}')]; lo = min(P.rooms_all, key=lambda r: r.poly.area)
    return row('Ч-16', nm, f'{len(small)}' + (f', шахт и ниш {len(ok)}' if small else '') + f'; самое малое — {lo.name} {fx(lo.poly.area / m2, 2)} м²',
               f'0 (0,5 м² = {fx(0.5 * m2, 0)} px² при {fx(P.scale)} px/м)', 'fail' if len(small) > len(ok) else 'look' if ok else 'pass',
               [W(at(r), f'{r.name} ({r.type or "тип?"}): {fx(r.poly.area / m2, 2)} м²' + (' — шахта или ниша' if r in ok else '')) for r in small], s=['S4.fragments'])
def c17(P, a, S):
    nm = 'Номера помещений: в своём помещении, по одному'; N = [t for t in texts(P) if t.num]
    if not N: return skip('Ч-17', nm, 'номеров помещений в labels нет: нумерация — по карточке, map/rules/72 §1')
    out_, alien, per = [], [], defaultdict(list)
    for t in N:
        c = t.box.centroid; h = [r for r in P.rooms_all if r.poly.contains(c)]
        if not h: out_.append(W(c.coords[0], f'«{t.t}» вне помещений')); continue
        rm = min(h, key=lambda r: r.poly.area); per[rm.name].append(t)
        rn = numtok(rm.a.get('data-number') or rm.name); tn = numtok(t.t)        # v007 (Е15): «кабинет 40.04» — номер 40.04
        if rn and tn and rm.name.strip() != t.t.strip() and not set(tn) & set(rn): alien.append(W(c.coords[0], f'«{t.t}» в помещении {rm.name}'))
    two = [W(v[0].box.centroid.coords[0], f'{k}: номеров {len(v)}') for k, v in per.items() if len(v) > 1]
    return row('Ч-17', nm, f'{len(N)}; вне помещений {len(out_)}; по два в помещении {len(two)}; чужой номер {len(alien)}', 'вне помещений — 0; два и чужой — look',
               'fail' if out_ else 'look' if two or alien else 'pass', out_ + two + alien)
def numtok(s):
    """номера в строке: 40.04, 12, 5-12, 3а"""
    return re.findall(r'\d+(?:[.,/-]\d+)*[A-Za-zА-Яа-яЁё]?(?![\d])', str(s or ''))
def c18(P, a, S):
    nm = 'Закрытые помещения ≥ 1,4 м² — с проёмом на границе'
    if not P.scale or not P.rooms: return skip('Ч-18', nm, 'нет масштаба: --scale-px-per-m или --meta' if P.rooms else 'помещений нет')
    D = unary_union([d.poly.buffer(0.8) for d in P.ops]) if P.ops else Polygon()
    no = [r for r in P.rooms if r.poly.area >= 1.4 * P.scale ** 2 and not r.poly.boundary.intersects(D)]
    sh = [r for r in no if r.type and re.search(KIND[1][1], r.type, re.I)]; no = [r for r in no if r not in sh]   # v007 (АБ13): шахта, ниша, стояк по data-type — кроп К-02
    lift = [r for r in no if rkind(r) == 'lift']; rest = [r for r in no if r not in lift]                # v4: по data-type словом, не по подстроке имени
    return row('Ч-18', nm, f'без проёма {len(rest)}' + (f'; лифтов без двери {len(lift)}' if lift else '') + (f'; шахт по типу {len(sh)} — К-02' if sh else ''),
               '0 или объяснение: шахта, ниша; лифт — дверь со стороны холла', 'look' if no else 'pass',
               [W(at(r), f'{r.name} ({r.type or "тип?"}), {fx(r.poly.area / P.scale ** 2)} м²') for r in rest] + [W(at(r), f'лифт {r.name}: дверь со стороны холла?') for r in lift])

# ------------------------------------------------------------------ Ч-19 – Ч-25: проёмы, стекло, мебель, значки, подписи, цвета
def c19(P, a, S):
    T, nm = P.T, 'Проёмы на стене: глубина = стене ±1 px, по оси ±1 px; заливка — цвет одной из сторон'
    if not P.ops: return row('Ч-19', nm, 'проёмов нет', 'двери — проёмами', 'fail', s=['S7.openings']) if len(P.rooms) > 1 else skip('Ч-19', nm, 'помещений меньше двух', s=['S7.openings'])
    U = P.rooms_all + [z for z in P.zones if z not in P.rooms_all]          # стороны проёма: помещения, открытые зоны и зоны поверх помещений
    tr = STRtree([q.poly for q in U]) if U else None; bad, lk, wd, nc, n0 = [], [], [], 0, 0
    BG_ = unary_union([P.body, P.glass]) if not P.glass.is_empty else P.body   # v012 (КМ-2, П3-9, Н-E2): тело — стены, обводки и стекло: проём в стекле — на стекле
    order = {id(r_): i for i, r_ in enumerate(P.R)}; cover_n = 0; ng = 0
    later = [(order.get(id(r_), -1), band(r_.poly.boundary, r_.sw) if r_ in P.rooms else unary_union([band(LineString(p_), r_.sw) for p_, c_, k_ in r_.subs if len(p_) > 1]))
             for r_ in P.rooms + P.free if r_.sw > 0]
    for r in P.ops:
        g = r.poly; s, l, u = sides(g); c = np.array(g.centroid.coords[0]); nr = np.array([-u[1], u[0]]) if u is not None else np.array([0.0, 1.0])
        ins = g.intersection(BG_.buffer(OPENING_EXTRA / 2)).area / g.area if g.area else 0.0     # v007 (АБ3): T + 1 px svg_map — на стене
        q = min(lines(LineString([c - nr * 3 * T, c + nr * 3 * T]).intersection(BG_)), key=lambda z: z.distance(Point(c)), default=None)
        th = q.length if q is not None and q.distance(Point(c)) < 0.5 else 0.0; off = abs(float(np.dot(np.array(q.centroid.coords[0]) - c, nr))) if th else 0.0
        gb = glass_bridge(P, g, c, u, l, s) if ins < 0.9 and u is not None else None
        if gb is not None:                                                  # v012 (КМ-2, П3-9, Н-E2): проём в стеклянной перегородке — между концами линий стекла одной прямой:
            ins, off, sw_g = 1.0, gb[0], gb[1]; ng += 1                     # «на стекле»; глубина — от линии стекла до стены (T + 1 px), ось — прямая концов стекла
            why = [m for m, b in ((f'глубина {fx(s)} вне {fx(sw_g)}…{fx(T + OPENING_EXTRA)} (стекло — стена)', s < sw_g - 1 or s > T + OPENING_EXTRA + 1), (f'с оси стекла на {fx(off)} px', off > 1)) if b]
        else:
            why = [m for m, b in ((f'на стене {pc(ins, 0)}', ins < 0.9), (f'глубина {fx(s)} ≠ стене {fx(th)}', th > 0 and abs(s - th) > 1), (f'с оси на {fx(off)} px', off > 1)) if b]
        wd.append(l)
        # цвет (map/rules/60 §1, map/rules/60 §2.3): проём — цвета своей комнаты, между цветным и белым — цвета цветного, то есть = заливке одной из сторон
        nb = [U[int(j)] for j in tr.query(g.buffer(1.5), predicate='intersects')] if tr is not None else []
        fs = sorted({str(z.fill).upper() for z in nb if z is not r and z.fill not in (None, 'none')}); fc = str(r.fill).upper()
        if not fs: n0 += 1; nw = 'сторон не найдено — цвет не сверен'
        else: nw = None; nc += fc in fs
        if fs and fc not in fs: why.append(f'цвет {fc} ≠ сторон ({", ".join(fs)})')
        gm = LineString([c - (u if u is not None else np.array([1.0, 0.0])) * max(l / 2 - T, 0.5), c + (u if u is not None else np.array([1.0, 0.0])) * max(l / 2 - T, 0.5)]).buffer(max(s, 1.0) / 2, cap_style='flat')
        gm = gm.intersection(g) if gm.intersects(g) else gm                 # средняя часть проёма: без зон косяков по T (квадратный конец стены у косяка — не «закрыт»)
        if gm.area > 0:                                                     # v012 (КМ-2, В2К-1, П3-10): проём виден — стекло (слой glass выше rooms) и стена, нарисованная после проёма, его не закрывают
            gc = gm.intersection(P.glass_top).area / gm.area if not P.glass_top.is_empty else 0.0   # обводка стеклом помещения под проёмом — ниже проёма, не закрывает
            oi = order.get(id(r), -1); wc_ = unary_union([b_ for o_, b_ in later if o_ > oi and b_.intersects(gm)]) if later else Polygon()
            wcv = gm.intersection(wc_).area / gm.area if not wc_.is_empty else 0.0
            if gc + wcv > 0.06: why.append(f'закрыт сверху: стеклом {pc(gc, 0)}, стеной {pc(wcv, 0)}'); cover_n += 1
        if why: bad.append(W(c, f'{r.id}: ' + ', '.join(why + ([nw] if nw else []))))
        elif nw: lk.append(W(c, f'{r.id}: {nw}'))
    return row('Ч-19', nm, f'{len(P.ops)}, в норме {len(P.ops) - len(bad) - len(lk)}; ширина: медиана {fx(float(np.median(wd)) / P.m, 2)} м, макс. {fx(max(wd) / P.m, 2)} м'
               f'; цвет: по сторонам {nc} из {len(P.ops)}' + (f', сторон не найдено {n0}' if n0 else '') + f'; закрыт сверху стеклом или стеной {cover_n}' +
               (f'; в стеклянной перегородке (между концами стекла) {ng}' if ng else ''), 'все', 'fail' if bad else 'look' if lk else 'pass', bad + lk, s=['S7.openings'])
def glass_bridge(P, g, c, u, l, s, ang=10.0):
    """v012 (КМ-2, П3-9, Н-E2): проём в стеклянной перегородке без стены под ним: с обеих сторон проёма вдоль его оси — конец линии стекла
    (в max(T, 0,15 м) от проёма, направление ± ang° к оси проёма). -> (смещение центра проёма с продолжения ближайшей линии стекла, px;
    толщина стекла) или None"""
    if not getattr(P, 'gends', None): return None
    lim = max(P.T, 0.15 * P.m) if P.m else P.T; ca = math.cos(math.radians(ang)); sides_ = {-1: None, 1: None}
    for e, dv, sw in P.gends:
        if abs(float(dv @ u)) < ca: continue
        t = float((e - c) @ u)
        if abs(t) < l / 2 - lim or abs(t) > l / 2 + lim: continue
        if abs(float((e - c) @ np.array([-u[1], u[0]]))) > max(s, P.T): continue
        k = 1 if t > 0 else -1
        if sides_[k] is None or abs(abs(t) - l / 2) < abs(abs(float((sides_[k][0] - c) @ u)) - l / 2): sides_[k] = (e, sw, dv)
    if sides_[-1] is None or sides_[1] is None: return None
    off = min(abs(float((c - e) @ np.array([-dv[1], dv[0]]))) for e, sw, dv in sides_.values())   # ось — продолжение линии стекла (у перегородки с изломом у двери — ближайшей)
    return off, max(sides_[-1][1], sides_[1][1])
def c20(P, a, S):
    L, nm = P.ring_line, 'Стекло на наружном контуре, доля длины'
    if L.is_empty: return skip('Ч-20', nm, 'наружный контур не найден', s=['S6.glass'])
    buf = 4 * P.T / 3; near = P.glass.buffer(buf) if not P.glass.is_empty else Polygon(); k = L.intersection(near).length / L.length
    un = lines(L.difference(near) if not near.is_empty else L); pcs = sorted([q for q in lines(linemerge(un)) if q.length > P.m] if un else [], key=lambda q: -q.length)
    wh = [W(q.interpolate(0.5, normalized=True).coords[0], f'без стекла {fx(q.length / P.m)} м') for q in pcs]
    val = f'{pc(k)} контура ({fx(L.length / P.m)} м); без стекла длиннее 1 м — {len(pcs)}' + ('' if P.scale else ' (1 м ≈ 6T: масштаба нет)')
    if a.glazed_facade: return row('Ч-20', nm, val, f'≥ 95 % (фасад остеклён), буфер {fx(buf)} px; без стекла > 1 м — look', 'fail' if k < 0.95 else 'look' if pcs else 'pass', wh, s=['S6.glass'])
    return row('Ч-20', nm, val, 'как на исходнике; > 1 м без стекла — look', 'look' if pcs else 'pass', wh, s=['S6.glass'])
def c21(P, a, S):
    nm = 'Мебель и столы не в стенах; стол на столе — 0'; F = [r for r in P.R if r.layer == 'furniture' and r.subs and not r.hidden]; pl = places(a)
    if not F and pl is None: return skip('Ч-21', nm, 'мебели и JSON мест нет', s=['S8.in_walls', 'S8.overlaps'])
    inst = defaultdict(list)
    for r in F: inst[r.inst or r.id].append(r)                               # предмет — экземпляр, части символа — одно целое
    inw = []
    for k, rs in inst.items():
        x = sum(r.poly.intersection(P.body).area for r in rs if not r.poly.is_empty); xl = sum(LineString(p).intersection(P.body).length for r in rs for p, c, kk in r.subs if not c and len(p) > 1)
        if x > 0.5 or xl > 1: inw.append(W(at(rs[0]), f'{k}: в стене {fx(x)} px²' + (f', линий {fx(xl)} px' if xl > 1 else '')))
    U = {k: unary_union([r.poly for r in rs if not r.poly.is_empty]) for k, rs in inst.items()}; U = {k: g for k, g in U.items() if not g.is_empty}
    keys = list(U); tr = STRtree([U[k] for k in keys]) if keys else None; ov, nest = [], []
    for i, k in enumerate(keys):
        for j in (int(j) for j in tr.query(U[k]) if j > i):
            x = U[k].intersection(U[keys[j]])
            if x.area <= 0.5: continue
            (nest if x.area >= 0.95 * min(U[k].area, U[keys[j]].area) else ov).append(W(x.representative_point().coords[0], f'{k} × {keys[j]}: {fx(x.area)} px²'))
    kx, ky = pic(P, a); dk = [(p.get('id'), make_valid(Polygon([(x / kx, y / ky) for x, y in p['desk']]))) for p in pl or [] if p.get('desk')]
    kc = keys_check(pl)                                                      # v13 (map/rules/80 Ч-21): записи не по схеме — fail, а не pass «столов 0»
    nod = [] if kc else [W((lambda q: (q[0] / kx, q[1] / ky) if q else None)(seat_pt(p)), f'место {pnum(p, k)}: desk: null — стол не разобран, в стенах не проверен (map/rules/83 §1, §5)')
           for k, p in enumerate(pl or []) if not p.get('desk')]
    dw = [W(d.centroid.coords[0], f'стол {i}: в стене {fx(x)} px²') for i, d in dk if (x := d.intersection(P.body).area) > 0.5]
    dd = [W(d.centroid.coords[0], f'стол {i} × {j}') for n, (i, d) in enumerate(dk) for j, e in dk[n + 1:] if d.intersection(e).area > 0.5]
    FK = [k for k in keys if not re.search(r'plant|растен|flower|озелен', k or '', re.I) and not any(r.figma in PLANTS for r in inst[k])]   # v008 (Е18): стол места — не предмет
    ftr = STRtree([U[k] for k in FK]) if FK else None; fm = []; dkn = [pnum(p, k) for k, p in enumerate(pl or []) if p.get('desk')]
    for n, (i, d) in enumerate(dk):
        if ftr is None or d.area <= 0: continue
        x = sum(d.intersection(U[FK[int(j)]]).area for j in ftr.query(d))
        if x > 0.5 * d.area: fm.append(W(d.centroid.coords[0], f'стол места {dkn[n]} в слое furniture: {pc(x / d.area, 0)} площади — рабочие места в чистовик не идут (map/rules/61 §3.3)'))
    kw = [W(None, kc)] if kc else []
    return row('Ч-21', nm, f'предметов {len(inst)}: в стенах {len(inw)}, пересечений {len(ov)}, вложений {len(nest)} (мойка в столешнице и т. п. — справочно)' +
               (f'; столов {len(dk)}: в стенах {len(dw)}, стол на столе {len(dd)}, стол места в furniture {len(fm)}' if pl is not None else '; JSON мест не дан') +
               (f'; {kc}' if kc else '') + (f'; мест с desk: null — {len(nod)}' if nod else ''),
               '0; 0; записи без desk и centre — fail «записей N, столов 0», desk: null — fail (map/rules/80 Ч-21, Ч-29); пересечения предметов и стол места в furniture (Е18) — look',
               'fail' if inw or dw or dd or kw or nod else 'look' if ov or fm else 'pass', kw + nod + inw + dw + dd + ov + fm, s=['S8.in_walls', 'S8.overlaps'])
def own_tag(r): return f"{r.a.get('id', '')} {r.a.get('data-type', '')} {r.a.get('data-name', '')} {r.a.get('data-kind', '')}"
def mr_kind(rs):
    """v13 (строка 354; map/rules/61 §1, §3.1): экземпляр мебели — стол переговорной ('table': символ стола map/kit/61, стол легенды map/kit/63 или
    id/тип со словом table|стол) или стул ('chair': символ стула map/kit/61 или id/тип со словом chair|стул); иначе None"""
    if any(r.a.get('data-figma') in MR_TABLE_FIGMA or MR_TABLE_RE.search(own_tag(r)) for r in rs): return 'table'
    if any(r.a.get('data-figma') in MR_CHAIR_FIGMA or MR_CHAIR_RE.search(own_tag(r)) for r in rs): return 'chair'
    return None
def furn_all(P):
    """все видимые элементы слоя furniture глубже слоя, и группы без своей геометрии (id, data-figma стола и стула — у группы), по экземпляру"""
    D = defaultdict(list)
    for r in P.R:
        if r.layer == 'furniture' and r.depth >= 2 and not r.hidden: D[r.inst or r.id].append(r)
    return D
def inst_geom(rs): return unary_union([r.poly for r in rs if not r.poly.is_empty] + [LineString(p) for r in rs for p, c, kk in r.subs if len(p) > 1])
def inst_pt(rs):
    g = inst_geom(rs); return None if g.is_empty else g.representative_point()
def c22(P, a, S):
    nm = 'Мебель 1 px #CBD2D6 без заливки; мебели переговорных, кроме стола со стульями, нет (№50; строка 354)'; F = [r for r in P.R if r.layer == 'furniture' and r.subs and not r.hidden]
    if not F: return skip('Ч-22', nm, 'в furniture нет элементов', s=['S8.style'])
    own = [r for r in F if not r.figma]                                       # своя геометрия; элементы символа гайдлайна — канон символа
    bad = [W(at(r), f'{r.id} {r.type}: {r.stroke} {fx(r.sw)} px, заливка {r.fill}') for r in own if r.stroke != WALL or abs(r.sw - 1) > 0.05 or r.tag != 'line' and r.fill != 'none']
    meet = [r for r in P.rooms_all if re.search(r'meeting|переговор|conference', f'{r.type} {r.name} {r.a.get("data-title", "")}', re.I)]
    inst = defaultdict(list)
    for r in F: inst[r.inst or r.id].append(r)
    m50, mr_ok, allK = [], 0, furn_all(P)
    for k, rs in inst.items():
        if re.search(r'plant|растен|flower|озелен', k or '', re.I) or any(r.figma in PLANTS for r in rs): continue   # №75: растения в переговорных рисуем
        if mr_kind(allK.get(k, rs)) and any(m.poly.contains(c_) for m in meet for c_ in [inst_pt(rs)] if c_ is not None): mr_ok += 1; continue   # v13 (строка 354): стол переговорной со стульями — рисуем
        g = unary_union([r.poly for r in rs if not r.poly.is_empty] + [LineString(p) for r in rs for p, c, kk in r.subs if len(p) > 1])
        if g.is_empty: continue
        c = g.representative_point(); mm = [m for m in meet if m.poly.contains(c)]
        if mm: m50.append(W(c.coords[0], f'{k} в переговорной {mm[0].name} (№50)'))
    return row('Ч-22', nm, f'{len(F)} элементов, своих {len(own)}, не по канону {len(bad)}; предметов в переговорных {len(m50)}' + (f'; столов и стульев переговорных {mr_ok} — канон (строка 354)' if mr_ok else ''),
               '0 и 0; растения в переговорных — можно (№75); стол переговорной со стульями — можно (строка 354)',
               'fail' if bad or m50 else 'pass', bad + m50, s=['S8.style'])
def c23(P, a, S):
    nm = 'Бейджи: один размер, в помещении, не на подписи и не на бейдже'; bg = badges(P); B = bg.B
    if not B: return skip('Ч-23', nm, 'в icons нет круглых рамок бейджей', s=['S9.size', 'S9.in_room', 'S9.glyphs'])
    sz = Counter(round(bg.dia(r), 1) for r in B); out_, look, per, rid = [], [], Counter(), {}
    for r in B:
        c = r.poly.centroid; h = [q for q in P.rooms_all if q.poly.contains(c)]
        if not h: out_.append(W(c.coords[0], f'{r.id or "бейдж"} вне помещений')); continue
        rm = min(h, key=lambda q: q.poly.area); per[id(rm)] += 1; rid[id(rm)] = rm                 # v4: по объекту — одноимённые помещения не сливаются
        if r.poly.intersection(P.body).area > 0.1 * r.poly.area: look.append(W(c.coords[0], f'{r.id or "бейдж"} на стене, {rm.name}'))
    look += [W(at(rid[k]), f'{rid[k].name}: бейджей {v}') for k, v in per.items() if v > 1]
    bl = [W(r.poly.centroid.coords[0], f'бейдж на подписи «{t.t[:20]}»') for r in B for t in texts(P) if r.poly.intersection(t.box).area > 1]
    bb = [W(r.poly.centroid.coords[0], 'бейдж на бейдже') for i, r in enumerate(B) for q in B[i + 1:] if r.poly.intersection(q.poly).area > 1]
    gw = [W(at(r), f'<{r.tag}> растр') for r in bg.IC if r.tag in ('image', 'use', 'foreignObject')] + [W(at(r), f'бейдж {r.fill}') for r in B if r.fill != BADGE] + \
         [W(at(r), f'глиф {r.fill}') for r in bg.gl if r.fill not in (GLYPH, 'none')] + [W(at(r), 'бейдж без глифа') for r in B if not any(r.poly.contains(g.poly.centroid) for g in bg.gl)]
    return row('Ч-23', nm, f'{len(B)}, ⌀ ' + ', '.join(f'{fx(k)} px ({fx(k / P.m, 2)} м)' for k in sz) + f'; вне помещений {len(out_)}; на подписи {len(bl)}; на бейдже {len(bb)}; '
               f'глифы не по канону {len(gw)}; на стене или по два {len(look)}; стрелок входа {len(P.entr)} (не бейдж)', f'один размер; 0; 0; 0; глиф {GLYPH} на {BADGE}; на стене — look',
               'fail' if len(sz) > 1 or out_ or bl or bb or gw else 'look' if look else 'pass', out_ + bl + bb + gw + look, s=['S9.size', 'S9.in_room', 'S9.glyphs'])
def c24(P, a, S):
    nm = 'Подписи: номера 24 px, #CBD2D6 на белом и #62677A на цвете (map/rules/72 §1, №40), выноски вне контура'; TX = texts(P)
    if not TX: return skip('Ч-24', nm, '<text> нет: номера и выноски — по карточке', s=['S10.font', 'S10.callouts', 'S10.text_on_wall'])
    def want(t):                                                         # №40: на цветной заливке — #62677A, на белом — #CBD2D6
        h = [r for r in P.rooms_all + P.zones if r.poly.contains(t.box.centroid)]
        f = min(h, key=lambda r: r.poly.area).fill if h else '#FFFFFF'
        return WALL if f in ('#FFFFFF', 'none', None) else GLYPH
    N = [t for t in TX if t.num]; nb = [W(t.box.centroid.coords[0], f'«{t.t}»: {fx(t.s, 0)} px, {t.fill} (ожидается {want(t)}), {t.fam[:20]}') for t in N if abs(t.s - 24) > 0.5 or t.fill != want(t)]
    nf = [W(t.box.centroid.coords[0], f'«{t.t}»: шрифт {t.fam[:30]}') for t in N if 'inter' not in t.fam.lower()]
    outl = [W(t.box.centroid.coords[0], f'«{t.t[:30]}» в {t.r.layer}') for t in TX if t.r.layer != 'labels']
    tips = [max((r.subs[0][0][0], r.subs[-1][0][-1]), key=lambda e: min((q.poly.exterior.distance(Point(e)) for q in P.plq), default=0)) for r in P.lead]
    co = [W(at(r), f'плашка {r.id} на плане') for r in P.plq if r.poly.intersection(P.ring).area > 1] + [W(e, 'линия выноски не заходит в план') for e in tips if not P.ring.buffer(1).contains(Point(e))]
    ow = [W(t.box.centroid.coords[0], f'«{t.t[:30]}» на стене') for t in TX if t.box.area and t.box.intersection(P.body).area > 0.1 * t.box.area]
    for r, e in zip(P.lead, tips):                                       # v4: указатель — не через чужое закрытое помещение, шахту, пустоту (map/rules/72 §2)
        ln = unary_union([LineString(p) for p, c, k in r.subs if len(p) > 1]); tg = room_at(P, e)
        for q in P.rooms:
            if q is tg or rkind(q) == 'corridor' or q.poly.contains(Point(e)): continue        # коридор и холл — можно; чужая зона отдела — нет
            x = ln.intersection(q.poly.buffer(-P.T))
            if x.length > P.T: co.append(W(x.representative_point().coords[0], f'указатель {r.id or "выноски"} через {q.name} ({rkind(q)}): {fx(x.length / P.m)} м'))
    fam = Counter(t.fam.split(',')[0].strip(" '\"").lower() for t in TX)                # семейство — по первому имени, запасные не в счёт
    return row('Ч-24', nm, f'номеров {len(N)}, не по канону — {len(nb)}; выносок {len(P.plq)}, замечаний {len(co)}; текст на стене {len(ow)}; вне labels {len(outl)}; шрифтов {len(fam)}',
               'номера — 24 px, цвет по заливке, Inter; в labels; выноски и текст на стене — look', 'fail' if nb or outl else 'look' if co or ow or nf or len(fam) > 1 else 'pass',
               nb + outl + co + ow + nf, s=['S10.font', 'S10.callouts', 'S10.text_on_wall'])
def c25(P, a, S):
    nm = 'Цвета: палитра map/rules/71 §1, цвета клиента, файл помещение → цвет'
    if not P.rooms: return skip('Ч-25', nm, 'помещений нет', s=['S11.palette', 'S11.map'])
    src = open(a.palette_extra, encoding='utf-8').read() if a.palette_extra and os.path.exists(a.palette_extra) else a.palette_extra or ''
    extra = {hexc('#' + c) for c in re.findall(r'(?<![0-9a-fA-F])([0-9a-fA-F]{6})(?![0-9a-fA-F])', src)}
    zu = unary_union([z.poly for z in P.zones]) if P.zones else Polygon(); area, who = Counter(), defaultdict(list)
    for r in P.rooms + P.zones: area[r.fill] += r.poly.area if r in P.zones or zu.is_empty else r.poly.difference(zu).area; who[r.fill].append(r)
    tot, outp = sum(area.values()) or 1.0, [c for c in area if c not in PALETTE | extra and c != 'none']
    mis, chk = [], []
    if a.colour_map:
        cm = json.load(open(a.colour_map, encoding='utf-8')); bn, bt = cm.get('by_name', cm), cm.get('by_type', {})
        chk = [(r, hexc(bn.get(r.name) or bt.get(r.type))) for r in P.rooms if bn.get(r.name) or bt.get(r.type)]
        mis = [W(at(r), f'{r.name} ({r.type}): {r.fill}, ожидается {e}') for r, e in chk if r.fill != e]
    return row('Ч-25', nm, f'{len(area)} заливок: ' + ', '.join(f'{c} {pc(v / tot)}' for c, v in area.most_common()) + f'; вне палитры {len(outp)}' + (f' (цветов клиента дано {len(extra)})' if extra else '') +
               (f'; по файлу сверено {len(chk)}, расходится {len(mis)}' if a.colour_map else '; файла --colour-map нет'), 'вне палитры — look; расхождение с файлом — fail',
               'fail' if mis else 'look' if outp else 'pass', mis + [W(at(r), f'{c}: {r.name}') for c in outp for r in who[c][:3]], s=['S11.palette', 'S11.map'])

# ------------------------------------------------------------------ Ч-26 – Ч-30: SVG, картинки, артефакт 3, поставка
NUMA = {'d', 'points', 'x', 'y', 'width', 'height', 'x1', 'y1', 'x2', 'y2', 'cx', 'cy', 'r', 'rx', 'ry', 'transform', 'viewBox', 'stroke-width'}
def c26(P, a, S):
    R, vb, E = P.R, P.vb, lambda rs, why: [W(at(r), f'<{r.tag}> {r.id} в {r.layer}: {why}') for r in rs]
    top = [r for r in R if r.depth == 1]; g = [r.id for r in top if r.tag == 'g']
    bg = lambda r: r.tag == 'rect' and r.fill in ('#FFFFFF', 'none') and vb and r.poly.area >= 0.99 * vb[2] * vb[3]
    ex = [r for r in top if r.tag not in ('title', 'desc', 'defs', 'metadata', 'namedview', 'g') and not bg(r)]
    bu = [k for k in ('width', 'height') if P.root.get(k) and not re.fullmatch(rf'\s*{NUM}\s*(px)?\s*', P.root.get(k))]
    u = next((r for r in top if r.tag == 'g' and r.id == 'underlay'), None); k = sum(1 for c in u.el.iter()) - 1 if u else 0
    uok = u is not None and (u.st['display'] == 'none' or u.st.get('visibility') == 'hidden') and not k
    ras = [r for r in R if r.tag in ('image', 'feImage', 'foreignObject') or any(k.endswith('href') and re.search(r'data:image|\.(png|jpe?g|gif|webp|bmp|tiff?)\b', v, re.I) for k, v in r.a.items())]
    b64 = len(re.findall(r'data:image|;base64,', P.text)); nan = [r for r in R if any(k in NUMA and re.search(r'nan|inf', v, re.I) for k, v in r.a.items())]
    tc = [r for r in R if 'transform' in r.a or 'class' in r.a or r.tag == 'style' or 'var(' in ''.join(r.a.values())]
    nh = [r for r in R if any(k in r.a and r.a[k].strip().lower() != 'none' and not re.fullmatch(r'#[0-9a-fA-F]{3}|#[0-9a-fA-F]{6}', r.a[k].strip()) for k in ('fill', 'stroke'))]
    ns = [r for r in R if r.layer in LAYERS and r.tag in ('path', 'line', 'polyline', 'polygon', 'rect', 'circle', 'ellipse') and 'stroke' not in r.a
          and not (r.figma and r.stroke in (None, 'none'))]                # v007 (АБ10): внутри символа гайдлайна нет атрибута — нет обводки; унаследованная — нарушение
    soft = [r for r in R if 'style' in r.a or r.tag == 'g' and any(k in r.a for k in ('fill', 'stroke', 'stroke-width'))] + [r for r in R if r.layer != 'underlay' and (r.subs or r.tag == 'text') and r.hidden]
    must = ([] if P.faces else P.rooms) + P.outer + P.gring; opn = [r for r in must if not all(s[1] for s in r.subs)]
    hard = (not vb) or bu or g != LAYERS or ex or not uok or ras or b64 or nan or tc or nh or ns or opn
    return row('Ч-26', 'Гигиена SVG: словарь групп, underlay, растр, transform, hex, stroke, замкнутость',
               (f'viewBox {fx(vb[2], 0)} × {fx(vb[3], 0)}' if vb else 'viewBox нет') +
               f'; группы {"по словарю" if g == LAYERS else ", ".join(g) or "нет"}' + (f', вне слоёв {len(ex)}' if ex else '') + f'; underlay {"пуста и скрыта" if uok else "не пуста или видна"}'
               f'; растр {len(ras)}, base64 {b64}; nan {len(nan)}; transform, class, CSS {len(tc)}; не hex {len(nh)}; без stroke {len(ns)}; незамкнутых {len(opn)} из {len(must)}; style, скрытое {len(soft)}',
               'всё — 0 и по словарю; style и скрытое — look', 'fail' if hard else 'look' if soft else 'pass',
               E(ex, 'вне слоёв') + E(ras, 'растр') + E(nan, 'nan') + E(tc, 'transform, class') + E(nh, 'не hex') + E(ns, 'нет stroke') + E(opn, 'не замкнут') + E(soft, 'style или скрыт'),
               s=['S1.viewbox', 'S1.layers', 'S1.underlay', 'S1.raster', 'S1.nan', 'S1.svg_tech', 'S1.closed'])
def c27(P, a, S):
    T, rs = P.T, P.rooms; wb = [] if P.faces else [r for r in rs if r.stroke == WALL and abs(r.sw - T) > 0.26] + P.odd
    tw = '2T' if P.TO == 2 * T else f'{fx(P.TO)} px'                       # толщина фасада: канон 2T или --outer-wall-px
    if P.outer:
        o = P.outer[0]; hd = None if P.faces or not rs else P.shell.boundary.hausdorff_distance(P.fac)
        ook, od = abs(o.sw - P.TO) <= 1 and (hd is None or hd <= T), f'серый путь {fx(o.sw)} px' + (f', от помещений {fx(hd)} px' if hd is not None else '')
    elif P.gring: ook, od = True, f'линия стекла {fx(P.gring[0].sw)} px, серого пути нет'
    elif P.mixed:                                                          # глухие участки — серые пути 2T, остальное — линия стекла
        Lr = P.ring_line; cover = unary_union([band(LineString(p), r.sw + 2) for r in P.facade for p, c, k in r.subs if len(p) > 1] + ([P.glass.buffer(2)] if not P.glass.is_empty else []))
        cv = Lr.intersection(cover).length / Lr.length if Lr.length else 0.0; wbad = [r for r in P.facade if abs(r.sw - P.TO) > 1]
        ook, od = cv >= 0.95 and not wbad, f'смешанный: глухие пути {tw} ({len(P.facade)}) и стекло покрывают {pc(cv)} контура' + (f'; толщина не {tw} у {len(wbad)}' if wbad else '')
    elif P.TO < 1.5 * T:                                                   # фасад тонкий, как внутренняя стена: наружный контур — обводки помещений T
        ook, od = True, f'фасад — обводки помещений (перенос «геометрия как есть», --outer-wall-px {fx(P.TO)} px)'
    else: ook, od = False, f'нет ни серого пути {tw}, ни линии стекла'
    L = unary_union([r.poly.boundary for r in P.outer]) if P.outer else unary_union([LineString(p) for r in P.facade for p, c, k in r.subs if len(p) > 1]) if P.mixed else None
    sw_ = max(r.sw for r in P.outer) if P.outer else 2.0
    sh = L.intersection(P.glass.buffer(sw_ / 2 + 1)).length / L.length if L is not None and not L.is_empty and not P.glass.is_empty else 0.0
    n = [0 if P.faces else sum(r.nv for r in rs), sum(r.nv for r in P.outer), sum(r.nv for r in P.free), sum(r.nv for r in P.bars + P.wallpolys)]; tot = sum(n)
    hard = P.faces or not rs or wb or not ook or sh >= (0.1 if P.mixed else 0.9) or P.wallpolys or (a.ref_points and tot > a.ref_points)
    return row('Ч-27', 'Стены SVG по канону: контуры с обводкой T, контур 2T или стекло, без полигона, точки',
               (f'помещений с обводкой нет, заливок {len(rs)}' if P.faces or not rs else f'{len(rs)} помещений, обводка {fx(T)} px у {len(rs) - len(wb)}, прямоугольников {S["rect"]}') +
               f'; контур: {od}; серый под стеклом {pc(sh)}; залитых полигонов {len(P.wallpolys)}; точек {tot} = ' + ' + '.join(map(str, n)),
               f'обводка = T; {tw if P.TO == 2 * T else "фасад " + tw + " (--outer-wall-px)"} ±1 px; < 90 % под стеклом; полигонов 0; точек ≤ {a.ref_points or "эталона (--ref-points)"}', 'fail' if hard else 'pass',
               ([W(at(r), r.name) for r in rs] if P.faces else [W(at(r), f'{r.name}: {r.stroke} {fx(r.sw)} px') for r in wb]) + [W(at(r), f'{r.id}: {r.nv} точек') for r in P.wallpolys],
               s=['S2.rooms', 'S2.outer', 'S2.grey_under_glass', 'S2.wall_polygon', 'S2.points'])
def c28(P, a, S):
    nm = 'Картинки: PNG чистовика = PNG артефакта 3, ≤ 10 000 px, ≤ 5 МБ; правка — Ш×В как у прежней выгрузки'
    if not a.final_png and not a.artefact3_png: return skip('Ч-28', nm, 'не даны --final-png и --artefact3-png', s=['S12.final_png', 'S12.size'])
    im = {k: (Image.open(f).size, os.path.getsize(f) / 2 ** 20) for k, f in (('чистовик', a.final_png), ('артефакт 3', a.artefact3_png)) if f}
    ref = im['чистовик'][0] if 'чистовик' in im else (P.W, P.H)
    thr = 'размеры равны до пикселя; пропорции viewBox; ≤ 10 000 px; ≤ 5 МБ; правка — Ш×В как у прежней выгрузки, до пикселя (--prev-size W,H)'
    ex = None                                                               # v012 (КМ-13, #86 П-4; строка 298): <png>.export.json, который пишет svg_map.to_png, — справочно
    if a.final_png and os.path.exists(a.final_png + '.export.json'):
        try: ex = json.load(open(a.final_png + '.export.json', encoding='utf-8'))
        except Exception: ex = {'mode': '?'}
    prev = None
    if getattr(a, 'prev_size', None):
        try: prev = tuple(int(v) for v in str(a.prev_size).replace('x', ',').replace('×', ',').split(','))[:2]
        except ValueError: return row('Ч-28', nm, f'--prev-size «{a.prev_size}» не разобран — нужно W,H', thr, 'fail', [W(None, 'ключ --prev-size не разобран')], s=['S12.final_png', 'S12.size'])
    if prev is None and isinstance(ex, dict) and ex.get('mode') == 'edit':
        return skip('Ч-28', nm, 'размер прежней выгрузки не дан: правка карты (export.json: mode edit) без ключа --prev-size W,H' +
                    (f'; в export.json prev_size {ex.get("prev_size")} — справочно' if ex.get('prev_size') else ''), s=['S12.final_png', 'S12.size'])
    bad = [W(None, f'{k}: {w} × {h}, {fx(mb)} МБ') for k, ((w, h), mb) in im.items() if max(w, h) > 10000 or mb > 5 or (P.vb and abs(w / h - P.vb[2] / P.vb[3]) > 2 / min(w, h))]
    same = 'артефакт 3' not in im or im['артефакт 3'][0] == ref
    if prev is not None:
        for k, ((w, h), mb) in im.items():
            if (w, h) != prev: bad.append(W(None, f'{k}: {w} × {h} ≠ прежней выгрузки {prev[0]} × {prev[1]} — правка: размер прежней выгрузки, до пикселя'))
    val = '; '.join(f'{k} {w} × {h} px, {fx(mb)} МБ' for k, ((w, h), mb) in im.items()) + ('' if 'чистовик' in im else f'; сравнение с viewBox {ref[0]} × {ref[1]}')
    if prev is not None: val += f'; прежняя выгрузка {prev[0]} × {prev[1]} (--prev-size)'
    if isinstance(ex, dict): val += f'; export.json: режим {ex.get("mode")}, множитель {ex.get("scale")}'
    return row('Ч-28', nm, val, thr, 'pass' if same and not bad else 'fail', bad + ([] if same else [W(None, 'размеры не равны')]), s=['S12.final_png', 'S12.size'])
def c29(P, a, S):
    nm = 'Артефакт 3: пятна столов #E6007E (по маске заливки до номеров) = пятна мест #FFB000 = места JSON; столы не в стенах'; pl = places(a)
    if not a.artefact3_png or pl is None: return skip('Ч-29', nm, 'нужны --artefact3-png и --places-json', s=['S12.blobs'])
    img = Image.open(a.artefact3_png); lab, keep, n, (dd, di) = desk_blobs(img, (0xE6, 0x00, 0x7E), (12, 25, 15)); _, seats, _ = blobs(img, (0xFF, 0xB0, 0x00), (12, 20, 30))
    cen = [q for q in (centre_pt(p) for p in pl) if q is not None]
    def hat(x, y):                                                       # v007 (Е13): метка пятна в центре места или в ближайшем пикселе пятна до 6 px
        iy, ix = min(max(int(y), 0), lab.shape[0] - 1), min(max(int(x), 0), lab.shape[1] - 1)
        return int(lab[iy, ix]) if lab[iy, ix] or dd[iy, ix] > 6 else int(lab[di[0][iy, ix], di[1][iy, ix]])
    hit = [hat(x, y) for x, y in cen]
    kc = keys_check(pl); wk = [W(None, kc)] if kc else []                  # v13 (map/rules/80 Ч-29): ключи не по схеме — fail с причиной
    kx_, ky_ = pic(P, a)
    fr_ = lambda q: None if q is None else (q[0] / kx_, q[1] / ky_)          # «Где» — px фрейма
    if not kc:
        wk += [W(fr_(seat_pt(p)), f'место {pnum(p, k)}: desk: null — нет многоугольника стола (map/rules/83 §1, §7)') for k, p in enumerate(pl) if not p.get('desk')]
        wk += [W(fr_(centre_pt(p)), f'место {pnum(p, k)}: нет точки стула (x, y) (map/rules/83 §5)') for k, p in enumerate(pl) if chair_pt(p) is None]
    ppm = P.m * (kx_ + ky_) / 2; dpx = max(SEAT_D_MIN_PX, SEAT_D_M * ppm); rr = dpx / 2   # v13: ⌀ точки — map/rules/83 §1, px картинки
    rgb = np.asarray(img.convert('RGB')).astype(np.int16); Hh, Ww = rgb.shape[:2]; shares, shut = [], []
    for k, p in enumerate(pl):                                           # v13 (map/rules/80 Ч-29): доля #FFB000 в круге точки ≥ 0,9, иначе точка закрыта — стоп
        q = chair_pt(p)
        if q is None: continue
        x0, x1, y0, y1 = max(0, int(math.floor(q[0] - rr)) - 1), min(Ww, int(math.ceil(q[0] + rr)) + 2), max(0, int(math.floor(q[1] - rr)) - 1), min(Hh, int(math.ceil(q[1] + rr)) + 2)
        yy, xx = np.mgrid[y0:y1, x0:x1]; inn = (xx + 0.5 - q[0]) ** 2 + (yy + 0.5 - q[1]) ** 2 <= rr * rr   # пиксель k = [k, k+1), центр k + 0,5 (как raster)
        if not inn.any(): shut.append(W(fr_(q), f'место {pnum(p, k)}: точка вне картинки')); continue
        okc = np.all(np.abs(rgb[y0:y1, x0:x1] - np.array(SEAT_RGB)) <= np.array(SEAT_TOL), axis=2)
        sh = float(okc[inn].mean()); shares.append(sh)
        if sh < SEAT_SHARE: shut.append(W(fr_(q), f'место {pnum(p, k)}: точка закрыта (или меньше ⌀ 0,26 м) — доля #FFB000 в круге ⌀ {fx(dpx)} px {pc(sh, 0)} < 90 % (map/rules/80 Ч-29, map/rules/83 §1)'))
    wk += shut
    wh = [W(q, 'место JSON без пятна стола') for q, h in zip(cen, hit) if h not in keep]
    wh += [W((x, y), 'пятно стола без места JSON') for y, x in (ndimage.center_of_mass(lab > 0, lab, sorted(keep - set(hit))) if keep - set(hit) else [])]
    kx, ky = pic(P, a); body = raster([P.body], img.size[0], img.size[1], [kx, 0, 0, ky, -(P.vb[0] if P.vb else 0) * kx, -(P.vb[1] if P.vb else 0) * ky])
    inw = ndimage.sum(body, lab, sorted(keep)) if keep else []
    wh += [W((x / kx, y / ky), f'пятно стола в стене: {int(v)} px') for (y, x), v in zip(ndimage.center_of_mass(lab > 0, lab, sorted(keep)) if keep else [], inw) if v > 5]
    return row('Ч-29', nm, f'столов {len(keep)}, мест {len(seats)}, в JSON {len(pl)}' + (f'; мелких пятен {n - len(keep)}' if n > len(keep) else '') + f'; пятен в стенах {sum(1 for v in inw if v > 5)}' +
               (f'; {kc}' if kc else '') + f'; точек закрыто {len(shut)} (круг ⌀ {fx(dpx)} px = 0,26 м' + ('' if P.scale else ', масштаб не дан — 1 м ≈ 6T') +
               (f', доля #FFB000 мин. {pc(min(shares), 0)}' if shares else '') + ')',
               'три числа равны; в стенах — 0; у каждого места desk и точка стула, desk: null — fail; записи без desk и centre — fail; доля #FFB000 в круге точки ≥ 90 % (map/rules/80 Ч-29)',
               'pass' if len(keep) == len(seats) == len(pl) and not wh and not wk else 'fail', wk + wh, s=['S12.blobs'])
def c30(P, a, S):
    got = [k for k, v in (('SVG', a.svg), ('PNG чистовика', a.final_png), ('артефакт 3', a.artefact3_png), ('JSON мест', a.places_json), ('исходник', a.source_png)) if v]
    return skip('Ч-30', 'Поставка: три артефакта и JSON мест', 'проверяется по списку файлов поставки (map/rules/82 §0, §3-бис)', val='дано: ' + ', '.join(got), s=['S12.delivery'])


# ------------------------------------------------------------------ Ч-31 – Ч-34: полнота и смысл против листа (v4, canon-proposals клиент А 4, Г1, Г2)
def plan_axes(P):
    """оси плана: направления прямых рёбер (mod 90°) с долей длины ≥ 5 %, до четырёх; нет рёбер — 0°"""
    h = np.zeros(180)                                                       # шаг 0,5°
    for pts, closed, tc, kind, r, vx in P.shp:
        Q, QK, _ = clean([pts[i] for i, _ in vx], [k for _, k in vx], closed); n = len(Q)
        for i in range(n if closed else n - 1):
            if QK[(i + 1) % n] != 'L': continue
            p, q = Q[i], Q[(i + 1) % n]; L = math.dist(p, q)
            if L > 0: h[int(round(math.degrees(math.atan2(q[1] - p[1], q[0] - p[0])) % 90 * 2)) % 180] += L
    tot, ax = h.sum(), []
    while tot and len(ax) < 4:
        j = int(np.argmax(h)); w = [(j + d) % 180 for d in range(-6, 7)]
        if h[w].sum() < 0.05 * tot: break
        ang = np.angle(np.sum(h[w] * np.exp(1j * np.radians(np.array(w) * 2.0)))) / 4; ax.append(math.degrees(ang) % 90); h[w] = 0
    return ax or [0.0]
def offax(t, ax):
    """угол t (°) от ближайшей оси плана, 0…45°"""
    return min(min((t - a) % 90, 90 - (t - a) % 90) for a in ax)
JUST_DEG = 2.5                                                              # v010 (К-4): допуск «90° к соседям» и «по главному направлению» — как у К6 моста
JOIN_DEG = 60.0                                                             # v010 (К-4, ПК4-К1): по главному направлению — только стык стен: каждый сосед под ≥ 60° к ребру
COL_HIDE = 0.85                                                             # v012 (ПК6-К2): ребро не судится, только если под заливкой колонны ≥ 85 % длины И видимая часть < T
                                                                            # (излом одной стены на 6–35° — косой уступ моста радиального здания, не оправдание) ⟨один пример: клиент Б, 40 этаж⟩
def main_dirs(P, ang=JUST_DEG, peak_m=3.0, edge_m=0.8):
    """v010 (К-4; №103, №109): главные направления здания — способом К6 моста (bridge_convert.dominant_dirs): пики суммарной длины прямых
    рёбер контуров по углу, окно ± ang, период 180°, от самого длинного, пик — от peak_m метров. В пики идут рёбра не короче edge_m (0,8 м —
    граница Ч-32): короткие косые рёбра — кандидаты Ч-32 — сами себя главным направлением не делают. -> [°]"""
    if getattr(P, 'MDIRS', None) is not None: return P.MDIRS
    A_, Wt = [], []
    for pts, closed, tc, kind, r, vx in P.shp:
        Q, QK, _ = clean([pts[i] for i, _ in vx], [k for _, k in vx], closed); n = len(Q)
        for i in range(n if closed else n - 1):
            if QK[(i + 1) % n] != 'L': continue
            p, q = Q[i], Q[(i + 1) % n]; L = math.dist(p, q)
            if L >= edge_m * P.m: A_.append(math.degrees(math.atan2(q[1] - p[1], q[0] - p[0])) % 180.0); Wt.append(L)
    A_, Wt = np.array(A_), np.array(Wt); dirs = []
    if len(A_):
        rem = np.ones(len(A_), bool); grid = np.arange(0, 180, 0.25); dd_ = lambda a0: np.abs((A_ - a0 + 90.0) % 180.0 - 90.0)
        while rem.any():
            w = np.array([Wt[rem & (dd_(a0) <= ang)].sum() for a0 in grid]); j = int(np.argmax(w))
            if w[j] < peak_m * P.m: break
            mem = rem & (dd_(grid[j]) <= ang); th = np.radians(A_[mem] * 2)
            m_ = (math.degrees(math.atan2((Wt[mem] * np.sin(th)).sum(), (Wt[mem] * np.cos(th)).sum())) / 2.0) % 180.0
            dirs.append(m_); rem &= ~(dd_(m_) <= ang); rem &= ~mem
    P.MDIRS = dirs
    return dirs
def on_sheet(P, a, p, q, R_m=0.3, tol=10.0, need=0.6):
    """v007 («Д» п. 1, Е11, ОВ27): есть ли на исходнике линия того же направления, что ребро p-q карты, в R_m метров от него. Признак — по
    градиенту туши исходника: края линии листа, параллельной ребру, дают градиент поперёк ребра (±tol°) вдоль need его длины на одном
    смещении; тело стены у прямого угла даёт градиенты по осям и косой линией не считается. Нет исходника — None (не проверено)."""
    src = source(P, a)
    if src is None: return None
    A, b = src.Ai[:2, :2], src.Ai[:2, 2]; P0, Q0 = A @ np.asarray(p, float) + b, A @ np.asarray(q, float) + b; L = float(np.hypot(*(Q0 - P0)))
    if L < 4: return False                                                # короче 4 px исходника — не судим: остаётся нарушением
    u = (Q0 - P0) / L; n = np.array([-u[1], u[0]]); R = R_m * P.m / src.k + 2; H, Wd = src.rgb.shape[:2]
    x0, y0 = int(max(0, min(P0[0], Q0[0]) - R - 3)), int(max(0, min(P0[1], Q0[1]) - R - 3)); x1, y1 = int(min(Wd, max(P0[0], Q0[0]) + R + 4)), int(min(H, max(P0[1], Q0[1]) + R + 4))
    if x1 - x0 < 5 or y1 - y0 < 5: return False
    g = ndimage.gaussian_filter(src.rgb[y0:y1, x0:x1].astype(float).mean(2), 0.8); gx, gy = ndimage.sobel(g, 1), ndimage.sobel(g, 0); mg = np.hypot(gx, gy)
    yy, xx = np.nonzero(mg >= 120)
    if not len(xx): return False
    al = np.abs(gx[yy, xx] * n[0] + gy[yy, xx] * n[1]) / mg[yy, xx] >= math.cos(math.radians(tol))        # градиент поперёк ребра
    rel = np.c_[xx + x0 + 0.5, yy + y0 + 0.5] - P0; t, d = rel @ u, rel @ n
    k = al & (t >= 0) & (t <= L) & (np.abs(d) <= R)
    if not k.any(): return False
    tb, db = np.floor(t[k]).astype(int), np.round(d[k]).astype(int); nt = int(math.floor(L)) + 1; best = 0
    for d0 in np.unique(db):                                              # одно смещение ±1 px: доля длины ребра с краем линии листа
        best = max(best, len(np.unique(tb[np.abs(db - d0) <= 1])))
    return best >= need * nt
def arc_run_edges(Q, QK, closed, T):
    """v012 (КМ-8): рёбра ломаной дуги — подряд ≥ 5 прямых рёбер короче 3T с одним знаком поворота на одной окружности (остаток < 1 px,
    поворот ≥ 15°): кривая, а не косые рёбра — Ч-32 их не судит -> множество индексов рёбер"""
    n = len(Q); m = n if closed else n - 1; out = set()
    if m < 5: return out
    E = [(Q[(i + 1) % n][0] - Q[i][0], Q[(i + 1) % n][1] - Q[i][1]) for i in range(m)]; L = [math.hypot(*e) for e in E]
    cr = [E[i][0] * E[(i + 1) % m][1] - E[i][1] * E[(i + 1) % m][0] for i in range(m)]
    st = [QK[(i + 1) % n] == 'L' and 0 < L[i] < 3 * T for i in range(m)]; i = 0
    while i < m:
        j = i; sg = np.sign(cr[i]) if abs(cr[i]) > 1e-9 else 0.0
        while j < m and st[j] and (j == i or (sg != 0 and np.sign(cr[j - 1]) == sg)): j += 1
        if j - i >= 5:
            Z = np.array([Q[t % n] for t in range(i, j + 1)], float); A_ = np.c_[2 * Z, np.ones(len(Z))]; c_ = np.linalg.lstsq(A_, (Z ** 2).sum(1), rcond=None)[0]
            R = math.sqrt(max(c_[2] + c_[0] ** 2 + c_[1] ** 2, 0))
            ang = [math.atan2(z[1] - c_[1], z[0] - c_[0]) for z in Z]; tot = abs(sum(((ang[t + 1] - ang[t] + math.pi) % (2 * math.pi)) - math.pi for t in range(len(ang) - 1)))
            if 0 < R < 5000 and np.abs(np.hypot(Z[:, 0] - c_[0], Z[:, 1] - c_[1]) - R).max() < 1.0 and tot >= math.radians(15): out |= set(range(i, j))
            i = j
        else: i += 1
    return out
def on_mask(P, a, p, q, R_m=0.3, tol=10.0, need=0.6):
    """v012 (КМ-13, ПК4-К2): «линия листа» у короткого ребра с векторной маской тела стены — ребро на теле стены листа (≥ need точек в 1 px)
    и направление тела у ребра (главная ось пикселей тела в окне max(ребро, R_m)) ± tol° к ребру; X-штриховка и стык тел — не линия"""
    src = source(P, a)
    if src is None or src.mask is None: return None
    A, b = src.Ai[:2, :2], src.Ai[:2, 2]; P0, Q0 = A @ np.asarray(p, float) + b, A @ np.asarray(q, float) + b; L = float(np.hypot(*(Q0 - P0)))
    if L < 2: return False
    H, Wd = src.mask.shape; n_ = max(3, int(L) + 1); xy = P0 + np.outer(np.linspace(0, 1, n_), Q0 - P0)
    ix, iy = np.floor(xy[:, 0]).astype(int), np.floor(xy[:, 1]).astype(int); ok = (ix >= 0) & (iy >= 0) & (ix < Wd) & (iy < H)
    if not ok.any(): return False
    d = np.full(n_, np.inf); d[ok] = src.mdist[iy[ok], ix[ok]]
    if (d <= 1.0).mean() < need: return False
    c = (P0 + Q0) / 2; Rw = max(L, R_m * P.m / src.k) / 2 + 2; x0, y0 = int(max(0, c[0] - Rw)), int(max(0, c[1] - Rw)); x1, y1 = int(min(Wd, c[0] + Rw + 1)), int(min(H, c[1] + Rw + 1))
    yy, xx = np.nonzero(src.mask[y0:y1, x0:x1])
    if len(xx) < 6: return False
    X = np.c_[xx, yy].astype(float); X -= X.mean(0); w_, V_ = np.linalg.eigh(X.T @ X / len(X))
    if w_[1] <= 1.5 * max(w_[0], 1e-9): return False                     # тело без направления (стык, пятно) — не линия листа
    u = (Q0 - P0) / L; return abs(float(V_[:, 1] @ u)) >= math.cos(math.radians(tol))
def oblique(P, a=None):
    """косые рёбра (Г1-4): прямое ребро короче 0,8 м под углом ≥ 8° к осям плана, которое соседи не продолжают (± 6°);
    v007: у каждого — есть ли на исходнике линия того же направления в 0,3 м (on_sheet).
    v010 (К-4; №103, №109): оправданное ребро — по линии листа того же направления И стыкуется с соседями под 90° (± 2,5°: каждый сосед
    по контуру — прямой и под 90°) ИЛИ идёт по главному направлению здания (main_dirs, ± 2,5°) и стыкуется с другими стенами (каждый сосед — прямой,
    под ≥ 60°: излом одной стены — не оправдание; сосед-кривая не судится) — в счёт не идёт и в look не показывается.
    -> [(место, у фасада, по линии листа, оправдано: '' | '90° к соседям' | 'главное направление')], оси"""
    if P.faces: return [], plan_axes(P)
    ax, lim, out, seen = plan_axes(P), 0.8 * P.m, [], set()
    ang = lambda p, q: math.degrees(math.atan2(q[1] - p[1], q[0] - p[0])) % 180
    adf = lambda u, v: min(abs(u - v) % 180, 180 - abs(u - v) % 180)
    md = None
    cu = unary_union([r_.poly for r_ in P.cols if r_.fill not in (None, 'none') and not r_.poly.is_empty]) if P.cols else Polygon()
    P.OBL_SKIP = dict(колонна=0, дуга=0)
    vm = a is not None and a.source_kind == 'vector' and getattr(a, 'wall_mask', None)
    for pts, closed, tc, kind, r, vx in P.shp:
        Q, QK, _ = clean([pts[i] for i, _ in vx], [k for _, k in vx], closed); n = len(Q); m = n if closed else n - 1
        arc_e = arc_run_edges(Q, QK, closed, P.T)
        for i in range(m):
            if QK[(i + 1) % n] != 'L': continue
            p, q = Q[i], Q[(i + 1) % n]; L = math.dist(p, q)
            if L < 0.8 or L > lim: continue                                      # < 0,8 px — Ч-09
            t = ang(p, q); o = offax(t, ax)
            if o < 8: continue
            if i in arc_e: P.OBL_SKIP['дуга'] += 1; continue                    # v012 (КМ-8): ломаная дуга — кривая, не судится
            if not cu.is_empty:                                                 # v012 (КМ-4, В2К-3): под заливкой колонны — не видно;
                hid = LineString([p, q]).intersection(cu).length                # ПК6-К2: видимый косой огрызок (вне колонны ≥ T или под ней < 85 %) — судится
                if hid >= COL_HIDE * L and L - hid < P.T: P.OBL_SKIP['колонна'] += 1; continue
            cont = (closed or i > 0) and QK[i] == 'L' and adf(ang(Q[i - 1], p), t) < 6
            cont = cont or ((closed or i + 2 < n) and QK[(i + 2) % n] == 'L' and adf(ang(q, Q[(i + 2) % n]), t) < 6)
            key = tuple(sorted([tuple(np.round(p, 1)), tuple(np.round(q, 1))]))
            if cont or key in seen: continue
            seen.add(key); c = ((p[0] + q[0]) / 2, (p[1] + q[1]) / 2)
            fac = kind == 'outer' or (not P.fac.is_empty and max(P.fac.distance(Point(p)), P.fac.distance(Point(q))) <= P.TO / 2 + 1)
            sh = (on_mask(P, a, p, q) if vm else on_sheet(P, a, p, q)) if a is not None else None   # v012 (КМ-13, ПК4-К2): с маской — по телу маски ± 10°
            just = ''
            if sh:                                                             # v010 (К-4): оправдано — только по линии листа
                nb = ([(QK[i] == 'L', ang(Q[i - 1], p))] if closed or i > 0 else []) + ([(QK[(i + 2) % n] == 'L', ang(q, Q[(i + 2) % n]))] if closed or i + 2 < n else [])
                if nb and all(st_ and abs(adf(u_, t) - 90) <= JUST_DEG for st_, u_ in nb): just = '90° к соседям'
                elif all(adf(u_, t) >= JOIN_DEG for st_, u_ in nb if st_):     # стык с другими стенами, а не излом одной стены (прямой сосед под < 60° — косой уступ, V-вмятина);
                                                                                # сосед-кривая (дуга фасада) — угол по хорде не судим, как «соседи не продолжают»
                    md = main_dirs(P) if md is None else md
                    if any(adf(t, d_) <= JUST_DEG for d_ in md): just = 'главное направление'
            out.append((W(c, f'{kind} {r.name}: {fx(L / P.m, 2)} м, {o:.0f}° к осям' + (' — фасад' if fac else '') + (' — по линии листа' if sh else '') + (f' — оправдано: {just}' if just else '')), fac, sh, just))
    return out, ax
def c32(P, a, S):
    nm = 'Косые рёбра: прямое короче 0,8 м под углом к осям плана, соседи его не продолжают (фаска, косой уступ, V-вмятина); на исходнике — линия того же направления в 0,3 м?'
    if P.faces or not P.shp: return skip('Ч-32', nm, 'контуров стен нет — см. Ч-27')
    ob, ax = oblique(P, a); J = [o for o in ob if o[3]]; ob = [o for o in ob if not o[3]]   # v010 (К-4): оправданные — не в счёт и не в look
    bad = [w for w, f, sh, j in ob if not f and not sh]; ls = sum(1 for w, f, sh, j in ob if sh and not f)   # v007: по линии листа — look
    jt = (f'; оправдано {len(J)} (по линии листа и 90° к соседям {sum(1 for o in J if o[3].startswith("90"))}, по главному направлению {sum(1 for o in J if o[3].startswith("глав"))}) — не в счёт'
          if J else '')
    sk = getattr(P, 'OBL_SKIP', {}); jt += (f'; под колонной {sk.get("колонна")} — не видно, не судится' if sk.get('колонна') else '') + (f'; на ломаной дуге {sk.get("дуга")} — кривая, не судится' if sk.get('дуга') else '')
    return row('Ч-32', nm, f'{len(ob)}, у фасада {sum(1 for w, f, sh, j in ob if f)}' + (f', по линии листа {ls}' if ls else '') + jt + '; оси плана ' + ', '.join(f'{v:.1f}°' for v in ax),
               '0; оправданное — по линии листа того же направления и 90° к соседям или по главному направлению здания (± 2,5°; стык с соседями под ≥ 60°) — не в счёт (№103, №109); '
               'у фасада и по линии листа — look', 'fail' if bad else 'look' if ob else 'pass', [w for w, f, sh, j in ob])

def crosses(P, a):
    """квадраты с диагоналями листа (лифт, шахта): пара длинных косых отрезков туши, пересекающихся в серединах, стороны прямоугольника
    по концам — тушь; штриховка (параллельные внутри) — не квадрат. -> [dict(c=(x, y) px фрейма, w, h — м)] или None"""
    src = source(P, a)
    if not src or not P.scale: return None
    if src.X is not None: return src.X
    try: import cv2
    except ImportError: src.X = []; P.notes.append('Ч-33: нет cv2 — квадраты листа не искались'); return src.X
    A2 = np.array(P.tf).reshape(2, 3); pxm = P.m / src.k; d8 = src.light.astype(np.uint8)
    Hh, Ww = d8.shape; tl = max(360, int(4 * pxm)); st = int(0.75 * tl); LL = []        # по плиткам: на всём листе вероятностный Хаф тонкие диагонали теряет
    for y0 in range(0, max(1, Hh - tl // 4), st):
        for x0 in range(0, max(1, Ww - tl // 4), st):
            t_ = d8[y0:y0 + tl, x0:x0 + tl] * 255
            if t_.sum() == 0: continue
            L = cv2.HoughLinesP(t_, 1, np.pi / 720, max(20, int(0.6 * pxm)), minLineLength=max(20, int(1.2 * pxm)), maxLineGap=max(3, int(0.06 * pxm)))
            if L is not None: LL.append(L.reshape(-1, 4).astype(float) + [x0, y0, x0, y0])
    if not LL: src.X = []; return src.X
    ax = plan_axes(P); seg = []
    for x1, y1, x2, y2 in np.concatenate(LL):
        p, q = A2[:, :2] @ (x1, y1) + A2[:, 2], A2[:, :2] @ (x2, y2) + A2[:, 2]; t = math.degrees(math.atan2(q[1] - p[1], q[0] - p[0])) % 180
        if 18 <= offax(t, ax) <= 45: seg.append((p, q, t))
    mrg = []                                                                # слить перекрывающиеся куски одной прямой
    for p, q, t in sorted(seg, key=lambda z: -math.dist(z[0], z[1])):
        u = (q - p) / math.dist(p, q); nrm = np.array([-u[1], u[0]]); hit = None
        for k, (P0, Q0, T0) in enumerate(mrg):
            U0 = (Q0 - P0) / math.dist(P0, Q0); a0, b0 = sorted((float(np.dot(p - P0, U0)), float(np.dot(q - P0, U0))))
            if min(abs(t - T0), 180 - abs(t - T0)) < 2.5 and abs(np.dot(p - P0, nrm)) < 4 and abs(np.dot(q - P0, nrm)) < 4 \
                    and a0 <= math.dist(P0, Q0) + 0.15 * P.m and b0 >= -0.15 * P.m: hit = k; break    # куски одной прямой — перекрываются или с зазором до 0,15 м
        if hit is None: mrg.append((p, q, t)); continue
        P0, Q0, T0 = mrg[hit]; U = (Q0 - P0) / math.dist(P0, Q0); ts = [0.0, math.dist(P0, Q0), float(np.dot(p - P0, U)), float(np.dot(q - P0, U))]
        mrg[hit] = (P0 + U * min(ts), P0 + U * max(ts), T0)
    ink = cv2.dilate(d8, np.ones((7, 7), np.uint8)) > 0; Ai = src.Ai; H, Wd = ink.shape
    def side_ok(p, q):
        n = max(2, int(math.dist(p, q))); xy = np.linspace(p, q, n) @ Ai[:2, :2].T + Ai[:2, 2]; ix, iy = xy[:, 0].astype(int), xy[:, 1].astype(int)
        ok = (ix >= 0) & (iy >= 0) & (ix < Wd) & (iy < H); return ok.any() and ink[iy[ok], ix[ok]].mean() >= 0.6
    dg = cv2.dilate(d8, np.ones((3, 3), np.uint8)) > 0
    def diag_ok(p, q):                                                   # диагональ из угла в угол — тушь на половине длины и больше
        n = max(2, int(math.dist(p, q))); xy = np.linspace(p, q, n) @ Ai[:2, :2].T + Ai[:2, 2]; ix, iy = xy[:, 0].astype(int), xy[:, 1].astype(int)
        ok = (ix >= 0) & (iy >= 0) & (ix < Wd) & (iy < H); return ok.any() and dg[iy[ok], ix[ok]].mean() >= 0.5
    out = []
    for i in range(len(mrg)):
        for j in range(i + 1, len(mrg)):
            (p1, q1, t1), (p2, q2, t2) = mrg[i], mrg[j]; da = min(abs(t1 - t2), 180 - abs(t1 - t2))
            l1, l2 = math.dist(p1, q1), math.dist(p2, q2)
            if da < 35 or min(l1, l2) < 0.4 * max(l1, l2): continue
            if not any(abs(((t1 - x) % 180 + (t2 - x) % 180 - 180 + 90) % 180 - 90) < 6 for x in ax): continue   # диагонали прямоугольника по осям — зеркальны
            d1, d2 = q1 - p1, q2 - p2; den = d1[0] * d2[1] - d1[1] * d2[0]
            if abs(den) < 1e-9: continue
            s1 = ((p2[0] - p1[0]) * d2[1] - (p2[1] - p1[1]) * d2[0]) / den; s2 = ((p2[0] - p1[0]) * d1[1] - (p2[1] - p1[1]) * d1[0]) / den
            if not (-0.05 <= s1 <= 1.05 and -0.05 <= s2 <= 1.05) or abs((s1 if l1 >= l2 else s2) - 0.5) > 0.15: continue   # пересечение — в середине длинной
            c = p1 + d1 * s1; u1, u2 = d1 / l1, d2 / l2                     # диагонали прямоугольника равны и делятся пополам: углы — от пересечения
            h = max(math.dist(c, p1), math.dist(c, q1), math.dist(c, p2), math.dist(c, q2))   # на большую половину — диагональ бывает недорисована
            C = [c - u1 * h, c - u2 * h, c + u1 * h, c + u2 * h]              # по кругу: концы диагоналей чередуются
            sd = [math.dist(C[k], C[(k + 1) % 4]) for k in range(4)]
            if sum(side_ok(C[k], C[(k + 1) % 4]) for k in range(4)) < 3 or not (diag_ok(C[0], C[2]) and diag_ok(C[1], C[3])): continue
            rect = Polygon(C)
            if not rect.is_valid or rect.area <= 0: continue
            par = sum(1 for k, (p, q, t) in enumerate(mrg) if k not in (i, j) and min(min(abs(t - t1), 180 - abs(t - t1)), min(abs(t - t2), 180 - abs(t - t2))) < 3
                      and rect.buffer(-0.1 * P.m).contains(Point((p + q) / 2)))
            if par >= 2: continue                                           # штриховка, не квадрат
            w, h = (sd[0] + sd[2]) / 2 / P.m, (sd[1] + sd[3]) / 2 / P.m
            if min(w, h) >= 0.9 and not any(math.dist(c, o['c']) < 0.3 * P.m for o in out): out.append(dict(c=(float(c[0]), float(c[1])), w=w, h=h))
    src.X = out; return out
def c33(P, a, S):
    nm = 'Бейджи против признаков листа: квадрат с диагоналями от 1,5 м — лифт или шахта, бейдж не WC; бейдж WC — не в лифте и не в шахте'
    bg = badges(P); X = crosses(P, a); bad, lk = [], []
    bk = [(r, bg.kind(r), room_at(P, r.poly.centroid.coords[0])) for r in bg.B]
    for r, k, rm in bk:
        rk = rkind(rm)
        if k == 'wc' and rk in ('lift', 'shaft', 'void'): bad.append(W(r.poly.centroid.coords[0], f'бейдж WC в помещении {rm.name} ({rm.type or rk})'))
        if k == 'lift' and rk == 'wc': bad.append(W(r.poly.centroid.coords[0], f'бейдж лифта в санузле {rm.name}'))
    for x in X or []:
        rm = room_at(P, x['c']); rk = rkind(rm); ks = {k for r, k, q in bk if q is rm and rm is not None}; sz = f'{fx(x["w"], 2)} × {fx(x["h"], 2)} м'
        if rm is None: lk.append(W(x['c'], f'квадрат с диагоналями {sz} вне помещений')); continue
        if 'wc' in ks: (bad if min(x['w'], x['h']) >= 1.5 else lk).append(W(x['c'], f'квадрат с диагоналями {sz} — помещение {rm.name} с бейджем WC'))
        elif min(x['w'], x['h']) >= 1.5 and rk not in ('lift', 'shaft', 'void', 'stair') and 'lift' not in ks:
            lk.append(W(x['c'], f'квадрат с диагоналями {sz} в помещении {rm.name} ({rm.type or rk}): лифт или шахта?'))
    sg = json.load(open(a.sheet_signs, encoding='utf-8')) if a.sheet_signs else []
    sg = sg.get('signs', []) if isinstance(sg, dict) else sg; A2 = np.array(P.tf).reshape(2, 3) if P.tf else None; wcs = []
    for e in sg:
        c = np.array([e['x'], e['y']], float)
        if e.get('frame', 'source') == 'source':
            if A2 is None: continue
            c = A2[:, :2] @ c + A2[:, 2]
        rm = room_at(P, c); k = str(e.get('kind', '')).lower()
        if k == 'wc': wcs.append(rm)
        if rm is not None and k in ('wc', 'lift', 'stair', 'tech') and not any(q is rm and kk == k for r, kk, q in bk):
            lk.append(W(c, f'знак листа «{e.get("note") or k}» — в {rm.name} нет бейджа {k}'))
    if sg and any(e.get('kind') == 'wc' for e in sg):
        lk += [W(r.poly.centroid.coords[0], f'бейдж WC в {rm.name}: на листе нет знака санузла') for r, k, rm in bk if k == 'wc' and rm is not None and not any(q is rm for q in wcs)]
    xs = 'не искались: нет --source-png, --source-transform или масштаба' if X is None else f'{len(X)}, от 1,5 м — {sum(min(x["w"], x["h"]) >= 1.5 for x in X)}'
    return row('Ч-33', nm, f'бейджей {len(bk)}: WC {sum(k == "wc" for _, k, _ in bk)}, лифт {sum(k == "lift" for _, k, _ in bk)}; квадратов с диагоналями листа {xs}; '
               f'знаков из --sheet-signs {len(sg)}', 'WC в лифте, шахте или в квадрате с диагоналями от 1,5 м — 0; прочее — look', 'fail' if bad else 'look' if lk else 'pass', bad + lk)

def desk_fill(P, a, dk, r_m=0.12, share=0.5):
    """v007 (Н11, Н25, ОВ2, «Д» п. 10): «стул» на заливке стола листа — стык столешниц или торцевой модуль, а не стул. Признак — из исходника:
    цвет заливки столов — медиана исходника в центрах столов JSON (только чтобы узнать цвет); стул — контур без заливки, круг r_m вокруг
    его точки (без пикселей туши) на этом цвете меньше чем на долю share. Заливки нет (белая, тушь) или исходника нет — признак не работает:
    ничего не исключает"""
    src = source(P, a)
    if src is None or not dk: return lambda c: False
    H, Wd = src.rgb.shape[:2]; at_ = lambda q: src.Ai[:2, :2] @ np.asarray(q, float) + src.Ai[:2, 2]
    cs = [at_(d.representative_point().coords[0]) for d in dk]; cs = [q for q in cs if 0 <= q[0] < Wd and 0 <= q[1] < H]
    if len(cs) < 3: return lambda c: False
    v = np.array([src.rgb[int(q[1]), int(q[0])] for q in cs], int); col = np.median(v, axis=0)
    if col.min() >= 235 or col.max() <= 100 or np.mean(np.abs(v - col).max(1) <= 30) < 0.6: return lambda c: False   # заливки нет или столы разного цвета
    rp = max(2, int(round(r_m * P.m / src.k))); yy, xx = np.mgrid[-rp:rp + 1, -rp:rp + 1]; disk = xx * xx + yy * yy <= rp * rp
    def f(c):                                                            # доля цвета стола — среди пикселей без туши: разделитель столешниц не мешает
        q = at_(c); x0, y0 = int(round(q[0])), int(round(q[1]))
        if x0 - rp < 0 or y0 - rp < 0 or x0 + rp >= Wd or y0 + rp >= H: return False
        w = src.rgb[y0 - rp:y0 + rp + 1, x0 - rp:x0 + rp + 1].astype(int); free = disk & ~src.dark[y0 - rp:y0 + rp + 1, x0 - rp:x0 + rp + 1]
        if free.sum() < 0.3 * disk.sum(): return False                     # круг почти весь на туши — не судим: остаётся стулом
        return float(np.mean((np.abs(w - col).max(2) <= 30)[free])) >= share
    return f
def c31(P, a, S):
    nm = 'Стулья листа без места: стул у стола вне переговорной — место JSON или вердикт «не место»'; pl = places(a)
    if not a.chairs_json: return skip('Ч-31', nm, 'нет списка стульев листа (--chairs-json): unspot_map.chairs по классу стульев листа или список вручную')
    if pl is None: return skip('Ч-31', nm, 'нет JSON мест (--places-json)')
    cj = json.load(open(a.chairs_json, encoding='utf-8')); fr = cj.get('frame', 'source') if isinstance(cj, dict) else 'source'
    ch = cj.get('chairs', []) if isinstance(cj, dict) else cj
    xy = np.array([[c['x'], c['y']] if isinstance(c, dict) else list(c)[:2] for c in ch], float).reshape(-1, 2)
    if not len(xy): return skip('Ч-31', nm, 'в списке стульев листа 0: класс стульев не найден — полнота мест не сверена (v008: пустой список — не pass)')
    if fr == 'source':
        if not P.tf: return skip('Ч-31', nm, 'стулья — в px исходника: нужен --source-transform')
        A2 = np.array(P.tf).reshape(2, 3); xy = xy @ A2[:, :2].T + A2[:, 2]
    kx, ky = pic(P, a)
    st = np.array([q for q in (seat_pt(p) for p in pl) if q is not None], float).reshape(-1, 2) / [kx, ky]   # v007 (Т3-9): номер «201-1» — не координата
    near = P.shell.buffer(P.m) if not P.shell.is_empty else None; keep, inm, ink, fld, dpt = [], 0, 0, 0, 0
    meet, kit = [q for q in P.rooms_all if rkind(q) == 'meeting'], [q for q in P.rooms_all if rkind(q) == 'kitchen']   # v007 («Д» п. 10): стулья кухонь — не места
    dk = [make_valid(Polygon([(x / kx, y / ky) for x, y in np.asarray(p['desk'], float)[:, :2]])) for p in pl if p.get('desk') and len(p['desk']) >= 3]
    dk = [d for d in dk if not d.is_empty]; dtr = STRtree(dk) if dk else None; onfill = desk_fill(P, a, dk)
    for i, c in enumerate(xy):
        pt = Point(c)
        if near is not None and not near.contains(pt): fld += 1
        elif any(m.poly.contains(pt) for m in meet): inm += 1
        elif any(m.poly.contains(pt) for m in kit): ink += 1
        elif (dtr is not None and len(dtr.query(pt, predicate='dwithin', distance=0.1 * P.m)) >= 2) or onfill(c): dpt += 1   # v007 (Н11, Н25, ОВ2): стык двух столов, заливка стола листа — не стул
        else: keep.append(i)
    D = np.hypot(*(xy[keep][:, None, :] - st[None, :, :]).transpose(2, 0, 1)) if keep and len(st) else np.zeros((len(keep), 0))
    mi, mj = set(), set()
    for d, i, j in sorted((D[i, j], i, j) for i, j in zip(*np.nonzero(D <= 0.6 * P.m))):     # один стул — одно место, ближайшие первыми
        if i not in mi and j not in mj: mi.add(i); mj.add(j)
    miss = [W(xy[k], 'стул без места' + (f' — {rm.name}' if (rm := room_at(P, xy[k])) is not None else '')) for n, k in enumerate(keep) if n not in mi]
    ne = len(keep); got = ne - len(miss)
    return row('Ч-31', nm, f'стульев листа {len(xy)}: в переговорных {inm}, в кухнях {ink}, деталь стола (стык двух столов JSON, заливка стола листа) {dpt}, за контуром {fld}; с местом {got} из {ne}' + (f' ({pc(got / ne)})' if ne else '') +
               f'; мест JSON {len(pl)}, из них без стула листа {len(st) - len(mj)}', 'каждый стул вне переговорных — место или вердикт «не место»: лаунж, столовая, стойка',
               'look' if miss else 'pass', miss)

def c34(P, a, S):
    nm = 'Закрытое помещение без мебели и мест, а на листе в нём мебель'; src = source(P, a)
    if not src or not P.scale: return skip('Ч-34', nm, 'нужны --source-png, --source-transform и масштаб')
    F = [r for r in P.R if r.layer == 'furniture' and r.subs and not r.hidden]; inst = defaultdict(list)
    for r in F: inst[r.inst or r.id].append(r)
    fp = [g.representative_point() for g in (unary_union([r.poly for r in rs if not r.poly.is_empty] + [LineString(p) for r in rs for p, c, k in r.subs if len(p) > 1]) for rs in inst.values()) if not g.is_empty]
    kx, ky = pic(P, a); fp += [Point(np.mean(p['desk'], axis=0) / [kx, ky]) for p in places(a) or [] if p.get('desk')]
    pxm = P.m / src.k; Hh, Ww = src.dark.shape; out, n = [], 0
    for q in P.rooms:
        if rkind(q) not in ('other', 'kitchen', 'openspace') or q.poly.area < 3 * P.m ** 2 or any(q.poly.contains(p) for p in fp): continue
        n += 1; g = affinity.affine_transform(q.poly, src.M).buffer(-max(0.3 * pxm, 1.5 * P.T / src.k))
        for o in P.ops:
            if o.poly.distance(q.poly) < 1: g = g.difference(affinity.affine_transform(o.poly, src.M).buffer((sides(o.poly)[1] + 0.2 * P.m) / src.k))
        if g.is_empty: continue
        x0, y0, x1, y1 = (int(v) for v in (max(0, g.bounds[0] - 1), max(0, g.bounds[1] - 1), min(Ww, g.bounds[2] + 2), min(Hh, g.bounds[3] + 2)))
        if x1 - x0 < 3 or y1 - y0 < 3: continue
        m = raster([g], x1 - x0, y1 - y0, [1, 0, 0, 1, -x0, -y0]) & src.light[y0:y1, x0:x1]   # мебель листа бывает светло-серой (Revit 0,24)
        lab, k = ndimage.label(m, structure=np.ones((3, 3))); big, ln = 0, 0.0
        for sl in ndimage.find_objects(lab):
            h_, w_ = (sl[0].stop - sl[0].start) / pxm, (sl[1].stop - sl[1].start) / pxm
            fil = float(m[sl].sum()) / max(1, (sl[0].stop - sl[0].start) * (sl[1].stop - sl[1].start))
            if max(h_, w_) >= 0.5 and min(h_, w_) >= 0.12 and fil <= 0.5: big += 1; ln += float(m[sl].sum()) / pxm     # сплошное — колонна, короб, знак
        if big >= 2 or ln >= 3.0: out.append(W(at(q), f'{q.name} ({q.type or "тип?"}): мебели и мест нет, на листе — фигур {big}, ≈ {fx(ln)} м линий'))
    return row('Ч-34', nm, f'закрытых помещений от 3 м² без мебели и мест {n}, на листе в них мебель — {len(out)}', 'look: мебель пропущена или на листе не мебель (map/rules/61 §2)',
               'look' if out else 'pass', out)

# ------------------------------------------------------------------ Ч-35 – Ч-39: смысл карты против листа (v008, пакет кода 2; группа 2 сводки 06.10)
# Входы с листа — как --chairs-json: {"frame": "source"|"plan", "<ключ>": [...]}; строит unspot_map.sheet (вектор) или автор. Нет входа — skip с причиной.
NOGO = ('lift', 'shaft', 'void')                                           # не цель связности: у лифта — своя проверка (Ч-18, Ч-36)
def sheet_json(path, key):
    """вход с листа -> (записи, кадр, весь JSON)"""
    D = json.load(open(path, encoding='utf-8'))
    if isinstance(D, dict): return D.get(key, []), D.get('frame', 'source'), D
    return D, 'source', {}
def to_frame(P, xy, fr):
    """точки листа -> px фрейма: «source» — по --source-transform (нет его — None), «plan» — как есть"""
    xy = np.asarray(xy, float).reshape(-1, 2)
    if fr != 'source': return xy
    if not P.tf: return None
    A2 = np.array(P.tf).reshape(2, 3); return xy @ A2[:, :2].T + A2[:, 2]
def place_pts(P, a):
    """точки мест JSON и столы во фрейме: [(номер, точка | None, стол | None)]"""
    pl = places(a) or []; kx, ky = pic(P, a); out = []
    for i, p in enumerate(pl):
        s = seat_pt(p); d = None
        if p.get('desk') and len(p['desk']) >= 3:
            try: d = make_valid(Polygon([(float(x) / kx, float(y) / ky) for x, y in [tuple(v[:2]) for v in p['desk']]]))
            except (TypeError, ValueError): d = None
        out.append((pnum(p, i), (s[0] / kx, s[1] / ky) if s is not None else None, d if d is not None and not d.is_empty else None))
    return out
def free_space(P):
    """проходимое растром (Ч-35): помещения и открытые зоны без тела стены, проёмы — проход; 4-связность: угол стены не протекает"""
    if getattr(P, 'FREE', None) is None:
        Wd, Hd = (P.W, P.H) if P.W else (int(P.shell.bounds[2]) + 2, int(P.shell.bounds[3]) + 2)
        k = min(1.0, max(math.sqrt(2.4e7 / max(Wd * Hd, 1)), 2.5 / max(P.T, 0.5))); M = [k, 0, 0, k, 0, 0]
        w, h = int(math.ceil(Wd * k)) + 2, int(math.ceil(Hd * k)) + 2
        R = raster([q.poly for q in P.rooms_all] + [o.poly for o in P.ops], w, h, M)
        B = raster([P.body], w, h, M) if not P.body.is_empty else np.zeros((h, w), bool)
        O = raster([through(o.poly, P.TO) for o in P.ops], w, h, M) if P.ops else np.zeros((h, w), bool)
        lab, n = ndimage.label((R & ~B) | O); d, ind = ndimage.distance_transform_edt(lab == 0, return_indices=True)
        P.FREE = NS(lab=lab, n=n, k=k, d=d, ind=ind, w=w, h=h)
    return P.FREE
def through(g, depth):
    """проём насквозь: прямоугольник проёма, продлённый поперёк стены на depth с каждой стороны, — дверь в фасаде глубиной T проходит полосу 2T"""
    s_, l_, u = sides(g)
    if u is None or l_ <= 0: return g.buffer(0.5)
    c = np.array(g.centroid.coords[0]); n = np.array([-u[1], u[0]]); hl, hd = l_ / 2, s_ / 2 + depth
    return Polygon([tuple(c + u * hl + n * hd), tuple(c - u * hl + n * hd), tuple(c - u * hl - n * hd), tuple(c + u * hl - n * hd)]).buffer(0.5)
def free_label(F, pt, r_px):
    """метка проходимой части в точке фрейма; на стене или мебели — ближайшая в r_px; нет — 0"""
    x, y = int(math.floor(pt[0] * F.k)), int(math.floor(pt[1] * F.k))
    if not (0 <= x < F.w and 0 <= y < F.h): return 0
    if F.lab[y, x]: return int(F.lab[y, x])
    return int(F.lab[F.ind[0][y, x], F.ind[1][y, x]]) if F.d[y, x] <= r_px * F.k else 0
def labels_in(F, g):
    """px проходимого по меткам внутри многоугольника g (px фрейма) -> Counter"""
    if g is None or g.is_empty: return Counter()
    x0, y0, x1, y1 = g.bounds; X0, Y0 = max(0, int(x0 * F.k) - 1), max(0, int(y0 * F.k) - 1); X1, Y1 = min(F.w, int(x1 * F.k) + 2), min(F.h, int(y1 * F.k) + 2)
    if X1 <= X0 or Y1 <= Y0: return Counter()
    m = raster([g], X1 - X0, Y1 - Y0, [F.k, 0, 0, F.k, -X0, -Y0]); v = F.lab[Y0:Y1, X0:X1][m]
    return Counter(v[v > 0].tolist())
def entries(P):
    """центры стрелок входа (map/rules/70 §1, «Вход»), px фрейма"""
    badges(P); out = []
    for k in sorted(P.entr, key=str):
        pts = [q for r in P.R if r.inst == k and r.layer == 'icons' for p, c, kk in r.subs for q in p]
        if pts: out.append(tuple(np.mean(np.asarray(pts, float), axis=0)))
    return out
def reach(P, a):
    """связность от входа: старт, достижимые метки и разбор целей -> NS (Ч-35; Ф3, АБ1, «Д» п. 3)"""
    if getattr(P, 'REACH', None) is not None: return P.REACH
    F = free_space(P); en = entries(P); start, how = set(), ''
    for c in en: start |= set(labels_in(F, Point(c).buffer(0.6 * P.m)))
    if start: how = f'стрелка входа ({len(en)})'
    else:
        cor = Counter()
        for q in P.rooms_all:
            if rkind(q) in ('corridor', 'openspace') or (q in P.open and rkind(q) == 'other' and not q.type): cor.update(labels_in(F, q.poly))
        if not cor: cor = Counter({l: int(v) for l, v in zip(*np.unique(F.lab[F.lab > 0], return_counts=True))})
        if cor: start = {max(cor, key=cor.get)}
        how = ('стрелки входа нет — ' if not en else 'стрелка входа вне проходимого — ') + 'старт: крупнейшая связная часть коридоров и холлов'
    share = lambda g: (lambda c: (sum(v for l, v in c.items() if l in start) / sum(c.values())) if c else None)(labels_in(F, g))
    P.REACH = NS(F=F, start=start, how=how, share=share, entries=en)
    return P.REACH
def c35(P, a, S):
    nm = 'Связность от входа: от стрелки входа по помещениям, проёмам и виртуальным границам — до каждой открытой зоны, коридора и помещения с местами'
    if not P.rooms_all: return skip('Ч-35', nm, 'помещений нет')
    R_ = reach(P, a); F = R_.F
    if not R_.start: return skip('Ч-35', nm, 'проходимого нет: помещения не растрируются')
    part = defaultdict(lambda: NS(rooms=[], seats=[], key=False, open=False))   # отрезанная часть проходимого -> что в ней (одно место на часть)
    for n_, s, d in place_pts(P, a):
        if s is None: continue
        l = free_label(F, s, 0.6 * P.m)
        if l and l not in R_.start: part[l].seats.append(n_); part[l].key = True
    D = unary_union([o.poly.buffer(0.8) for o in P.ops]) if P.ops else Polygon(); n18 = 0
    for q in P.rooms_all:
        if rkind(q) in NOGO: continue
        c = labels_in(F, q.poly); tot = sum(c.values())
        if not tot or sum(v for l, v in c.items() if l in R_.start) >= 0.5 * tot: continue
        l = max((l for l in c if l not in R_.start), key=c.get)
        key = q in P.open or rkind(q) == 'corridor'
        if not key and (not P.scale or q.poly.area < 1.4 * P.scale ** 2): continue
        if not key and not q.poly.boundary.intersects(D) and not part[l].rooms: n18 += 1; part[l].n18 = True; continue   # без проёма — это Ч-18
        part[l].rooms.append(q); part[l].key |= key; part[l].open |= q in P.open
    common = defaultdict(list)                                              # v010 (К-6; №101): общие помещения здания в отрезанной части
    for q in P.rooms_all:
        if not is_common(q): continue
        cq = labels_in(F, q.poly)
        if cq and (l := max(cq, key=cq.get)) not in R_.start: common[l].append(q)   # часть — по преобладающей метке помещения
    bad, lk, nh = [], [], 0
    for l, v in part.items():
        if not v.rooms and not v.seats: continue
        kr = [q for q in v.rooms if q in P.open or rkind(q) == 'corridor'] or v.rooms                      # место — на открытой зоне или коридоре части
        big = max(kr, key=lambda q: q.poly.area) if kr else None; c = at(big) if big is not None else None
        if c is None: c = next(s for n_, s, d in place_pts(P, a) if s is not None and str(n_) in map(str, v.seats))
        nm_ = ', '.join(f'{q.name} ({q.type or rkind(q)})' for q in sorted(v.rooms, key=lambda q: -q.poly.area)[:4]) + (f' и ещё {len(v.rooms) - 4}' if len(v.rooms) > 4 else '')
        txt = f'отрезано от входа: {nm_ or "место вне помещений"}' + (f'; мест {len(v.seats)} (' + ', '.join(map(str, v.seats[:4])) + ('…' if len(v.seats) > 4 else '') + ')' if v.seats else '')
        off = [q for q in v.rooms if not is_common(q) and (rkind(q) in OFFICE or q in P.open)]               # помещения офиса: санузлы, их коридор, кухня, зоны, места
        cm = {id(q): q for q in common.get(l, [])}
        if (off or v.seats) and cm:                                         # потерянная дверь листа: офис открывается только в общие помещения здания
            nh += 1; on = ', '.join(q.name or rkind(q) for q in sorted(off, key=lambda q: -q.poly.area)[:3]) or f'мест {len(v.seats)}'
            txt += (f'; подсказка — потерянная дверь листа? {on} открываются только в общие помещения здания (' + ', '.join(q.name or rkind(q) for q in list(cm.values())[:3]) +
                    '): так на листе — проход в офис по map/rules/50 §2 строкой карточки, Ч-35 заново (№101)')
        (bad if v.key else lk).append(W(c, txt))
    nseat = sum(len(v.seats) for v in part.values())
    return row('Ч-35', nm, f'старт — {R_.how}; частей проходимого {F.n}; отрезанных частей с открытой зоной, коридором или местами {len(bad)} (мест {nseat}), '
               f'с прочими помещениями за проёмом {len(lk)}' + (f'; помещений без проёма — {n18}, это Ч-18' if n18 else '') + (f'; с подсказкой «потерянная дверь листа» {nh}' if nh else ''),
               'открытая зона, коридор, холл и место — 0 (fail); прочее помещение за проёмом — look; одно место — одна отрезанная часть', 'fail' if bad else 'look' if lk else 'pass', bad + lk)
OFFICE = ('wc', 'corridor', 'kitchen', 'openspace', 'meeting')               # v010 (К-6): помещения, которые служат офису (map/rules/50 §2, №101); и открытые зоны, и места
VENT = re.compile(r'вент\.?\s*кам|венткам|вентиляц|\bvent', re.I)
def is_common(q):
    """общее помещение здания (map/rules/50 §2, «Потерянная дверь листа»; №101): лестничная клетка, венткамера, шахта, лифт"""
    return rkind(q) in ('stair', 'shaft', 'lift') or bool(VENT.search(f'{q.name or ""} {q.type or ""}'))
def lift_doors(P):
    """дверь лифта — в холл (Т4-7): проёмы лифта, за которыми нет коридора, холла или открытой зоны -> места"""
    out = []
    for r in P.rooms_all:
        if rkind(r) != 'lift': continue
        ops = [o for o in P.ops if o.poly.buffer(0.8).intersects(r.poly.boundary)]
        if not ops: continue                                                # без двери — Ч-18
        nb = {id(q): q for o in ops for q in P.rooms_all if q is not r and q.poly.intersects(o.poly.buffer(1.5))}
        if not any(rkind(q) in ('corridor', 'openspace') or q in P.open for q in nb.values()):
            out.append(W(at(r), f'лифт {r.name}: дверь не в холл — за ней ' + (', '.join(f'{q.name} ({q.type or rkind(q)})' for q in list(nb.values())[:2]) or 'ничего')))
    return out
def c36(P, a, S):
    nm = 'Двери листа: у каждой — проём карты ближе 0,5 м; дверь лифта — в холл'
    lf = lift_doors(P)
    if not a.sheet_doors:
        why = 'нет дверей листа (--sheet-doors: python3 -m unspot_map.sheet doors …) — двери листа не сверены'
        if lf: return row('Ч-36', nm, f'двери листа не даны — не сверены; лифтов с дверью не в холл {len(lf)}', 'дверь лифта — в холл; двери листа — skip без входа', 'look', lf)
        return skip('Ч-36', nm, why)
    E, fr, meta = sheet_json(a.sheet_doors, 'doors'); dl, n = [], 0; leaves = []
    ops = STRtree([o.poly for o in P.ops]) if P.ops else None; Gs = [o.poly for o in P.ops]
    near = P.shell.buffer(P.m) if not P.shell.is_empty else None; fld = wc = small = 0
    wcs = [q for q in P.rooms_all if rkind(q) == 'wc']
    for e in E:
        pts = [e.get('hinge') or e.get('c')] + [e.get(k) for k in ('a', 'b') if e.get(k) is not None]
        if any(p is None for p in pts[:2]): continue
        q = to_frame(P, pts, fr)
        if q is None: return skip('Ч-36', nm, 'двери листа — в px исходника: нужен --source-transform')
        H_, ends = q[0], q[1:]; r_m = max(math.dist(H_, z) for z in ends) / P.m; n += 1
        if near is not None and not near.contains(Point(H_)): fld += 1; continue
        if r_m < 0.55: small += 1; continue                                 # шкаф, лючок: створка уже 0,55 м (Ф4)
        mids = [Point((H_ + z) / 2) for z in ends]
        rm = next((w for w in wcs if w.poly.contains(mids[0]) and w.poly.boundary.distance(mids[0]) > 0.3 * P.m and w.poly.boundary.distance(Point(H_)) > 0.15 * P.m), None)
        if rm is not None: wc += 1; continue                               # кабина санузла внутри помещения WC — не проём карты (№30)
        hit = ops is not None and any(Gs[int(j)].distance(m) <= 0.5 * P.m for m in mids for j in ops.query(m.buffer(0.5 * P.m)))
        leaves.append((np.asarray(H_, float), r_m, mids))
        if not hit: dl.append(W(((H_[0] + ends[0][0]) / 2, (H_[1] + ends[0][1]) / 2), f'дверь листа ({e.get("kind", "arc")}, {fx(r_m, 2)} м' + (f', {e["note"]}' if e.get('note') else '') + ') без проёма карты' + (f' — {rm_.name}' if (rm_ := room_at(P, (H_[0], H_[1]))) is not None else '')))
    wdt = []                                                               # v012 (КМ-9, П3-13): ширина проёма карты против двери листа от косяка до косяка (обе створки)
    for o in P.ops:
        s_, l_, u_ = sides(o.poly)
        if u_ is None: continue
        c_ = np.array(o.poly.centroid.coords[0]); lv = [(H_, r_) for H_, r_, mids in leaves if any(o.poly.distance(m_) <= 0.5 * P.m for m_ in mids)
                                                        and abs(float((H_ - c_) @ np.array([-u_[1], u_[0]]))) <= 0.4 * P.m and abs(float((H_ - c_) @ u_)) <= l_ / 2 + 0.6 * P.m]
        if not lv: continue
        hs = sorted(float((H_ - c_) @ u_) for H_, r_ in lv)
        w_sh = (hs[-1] - hs[0]) / P.m if len(lv) >= 2 and hs[-1] - hs[0] >= 0.4 * P.m else max(r_ for H_, r_ in lv)
        if abs(l_ / P.m - w_sh) > 0.3: wdt.append(W(c_, f'{o.id}: проём {fx(l_ / P.m, 2)} м против двери листа {fx(w_sh, 2)} м (створок {len(lv)}) — расхождение больше 0,3 м'))
    return row('Ч-36', nm, f'дверей листа {n}: без проёма карты {len(dl)}; кабины санузлов {wc}, створка < 0,55 м {small}, за контуром {fld}; лифтов с дверью не в холл {len(lf)}' +
               f'; ширина проёма против листа (> 0,3 м) {len(wdt)}' + (f'; вход: {meta.get("how")}' if meta.get('how') else ''),
               'каждая дверь листа — проём карты в 0,5 м или вердикт: кабина санузла, шкаф, вне охвата; лифт — дверь в холл; ширина проёма — от косяка до косяка листа ± 0,3 м', 'look' if dl or lf or wdt else 'pass', dl + lf + wdt)
MOD_SIDE = 0.8          # доля измеренных точек длинных сторон на краю модуля листа (Ч-37, ОВ20 г)
MOD_TOL_M = 0.1         # окно по нормали к стороне стола, м
MOD_LEN_M = 0.1         # v011 (ПК4-К4): длина стола против модуля листа — ± м
MOD_SEEN = 0.5          # v011 (ПК4-К4): измерено меньше половины точек (край закрыт предметами листа) — мера стол не видит: стол — объект К-11
MOD_END_WIN_M = 0.45    # v011 (ПК4-К4): торец модуля листа ищется в 0,45 м от торца стола JSON
MOD_END_COVER = 0.6     # v011 (ПК4-К4): торец модуля листа — край туши поперёк стола (±20°) на ≥ 60 % его глубины
CHAIR_R_M = 0.35        # v011 (ПК4-К4): стул листа из --chairs-json — круг 0,35 м: край стола под ним не мерится
OUT_M = 0.35            # v011 (ПК4-К4, стенд 37): предмет, закрывающий край, лежит и снаружи стола — тушь в 0,1–0,35 м наружу от стороны (стул, задвинутый к столу)
def sheet_chairs(P, a):
    """v011: стулья листа (--chairs-json) в px исходника -> массив (N, 2) | None"""
    if getattr(P, 'CHS', False) is False:
        P.CHS = None; f = getattr(a, 'chairs_json', None); src = source(P, a)
        if f and src is not None:
            cj = json.load(open(f, encoding='utf-8')); fr = cj.get('frame', 'source') if isinstance(cj, dict) else 'source'
            ch = cj.get('chairs', []) if isinstance(cj, dict) else cj
            xy = np.array([[c['x'], c['y']] if isinstance(c, dict) else list(c)[:2] for c in ch], float).reshape(-1, 2)
            if len(xy): P.CHS = xy if fr == 'source' else xy @ src.Ai[:2, :2].T + src.Ai[:2, 2]
    return P.CHS
def desk_module(P, a, d, tol_m=MOD_TOL_M, thr=60.0, cos_=0.94, debug=None):
    """v011 (ПК4-К4): стол JSON (px фрейма) против модуля листа -> dict | None.
    Длинные стороны: точка — «край», если в tol_m по нормали есть край туши, ПАРАЛЛЕЛЬНЫЙ стороне (градиент вдоль нормали, ±20°): случайные края
    (стулья, штриховка, плитка пола) не засчитываются (ОВ20 г). Точка без такого края, где в окне есть тушь, но край её не параллелен стороне,
    — край закрыт предметом листа поверх стола (стул, задвинутый к столу, номер места): не мерится; точка в круге CHAIR_R_M стула листа
    (--chairs-json) без края — закрыта стулом, не мерится. share — доля «края» среди измеренных, seen — доля измеренных.
    Длина: торец модуля листа — край туши поперёк стола (±20°) на ≥ MOD_END_COVER его глубины в MOD_END_WIN_M от торца стола JSON;
    видны оба — L_mod, |L − L_mod| > MOD_LEN_M — стол не того размера. ok — share ≥ 0,8, seen ≥ 0,5 и длина сошлась (или торцы не видны)"""
    src = source(P, a)
    if src is None: return None
    mr = d.minimum_rotated_rectangle
    if mr.geom_type != 'Polygon': return None
    C = np.asarray(mr.exterior.coords, float)[:4] @ src.Ai[:2, :2].T + src.Ai[:2, 2]
    e = sorted(((C[i], C[(i + 1) % 4]) for i in range(4)), key=lambda z: -float(np.hypot(*(z[1] - z[0]))))
    Lpx = float(np.hypot(*(e[0][1] - e[0][0]))); Dpx = float(np.hypot(*(e[2][1] - e[2][0])))
    if Lpx < 2 or Dpx < 1: return None
    H, Wd = src.rgb.shape[:2]; k_ = P.m / src.k                               # px исходника на м
    t = tol_m * k_ + 1.0; W_ = MOD_END_WIN_M * k_
    x0, y0 = int(max(0, C[:, 0].min() - W_ - t - 4)), int(max(0, C[:, 1].min() - W_ - t - 4)); x1, y1 = int(min(Wd, C[:, 0].max() + W_ + t + 5)), int(min(H, C[:, 1].max() + W_ + t + 5))
    if x1 - x0 < 5 or y1 - y0 < 5: return None
    g = ndimage.gaussian_filter(src.rgb[y0:y1, x0:x1].astype(float).mean(2), 0.8); gx, gy = ndimage.sobel(g, 1), ndimage.sobel(g, 0); mg = np.hypot(gx, gy)
    CH = sheet_chairs(P, a); rc = CHAIR_R_M * k_
    cen0 = C.mean(0); dk_ = src.dark[y0:y1, x0:x1]
    def outward_ink(p0, n):                                                 # предмет листа поверх края — и снаружи стола: тушь в полосе 0,1–0,35 м наружу от стороны
        no = n if float((p0 - cen0) @ n) >= 0 else -n; dd = np.arange(MOD_TOL_M * k_, OUT_M * k_ + 0.01, 1.0)
        q_ = p0 + dd[:, None] * no[None]; jx, jy = np.round(q_[:, 0] - x0).astype(int), np.round(q_[:, 1] - y0).astype(int)
        ok_ = (jx >= 0) & (jy >= 0) & (jx < x1 - x0) & (jy < y1 - y0)
        return bool(ok_.any() and (np.any(mg[jy[ok_], jx[ok_]] >= thr) or np.any(dk_[jy[ok_], jx[ok_]])))
    hit = miss = closed = chair = wall = fill = 0
    if getattr(P, 'WB1', None) is None:                                      # v012 (КМ-13, ПК5-К2): сторона стола на линии стены — край стены, не модуля: не мерится
        WB = P.body.buffer(1.0) if not P.body.is_empty else Polygon(); gs_ = [g_ for g_ in getattr(WB, 'geoms', [WB]) if not g_.is_empty]
        import shapely as _sh; [_sh.prepare(g_) for g_ in gs_]; P.WB1 = (gs_, STRtree(gs_) if gs_ else None)
    gs_, WBt = P.WB1
    on_wall = lambda q_: WBt is not None and any(gs_[int(j)].contains(Point(*q_)) for j in WBt.query(Point(*q_)))
    lum = src.rgb[y0:y1, x0:x1].astype(float).mean(2)
    for c0, c1 in (e[0], e[1]):
        L = float(np.hypot(*(c1 - c0))); u = (c1 - c0) / L; n = np.array([-u[1], u[0]]); off = np.arange(-t, t + 0.01, 0.5)
        for s_ in np.linspace(0.05, 0.95, max(5, int(L / 2))):
            p0 = c0 + u * s_ * L; pts = p0 + off[:, None] * n[None]; ix, iy = np.round(pts[:, 0] - x0).astype(int), np.round(pts[:, 1] - y0).astype(int)
            ok = (ix >= 0) & (iy >= 0) & (ix < x1 - x0) & (iy < y1 - y0)
            if not ok.any(): kind = 'miss'
            elif on_wall(src.A2[:, :2] @ p0 + src.A2[:, 2]): kind = 'wall'
            else:
                m_, gx_, gy_ = mg[iy[ok], ix[ok]], gx[iy[ok], ix[ok]], gy[iy[ok], ix[ok]]
                if np.any((m_ >= thr) & (np.abs(gx_ * n[0] + gy_ * n[1]) >= cos_ * m_)): kind = 'hit'
                elif CH is not None and float(np.hypot(*(CH - p0).T).min()) <= rc: kind = 'chair'
                elif np.any(m_ >= thr) and outward_ink(p0, n): kind = 'closed'
                elif not np.any(m_ >= thr) and (lum[iy[ok], ix[ok]] < 245).mean() >= 0.8: kind = 'fill'   # v012 (ПК5-К12): заливка стула на крае стола без туши — край закрыт, не «мимо»
                else: kind = 'miss'
            hit += kind == 'hit'; miss += kind == 'miss'; closed += kind == 'closed'; chair += kind == 'chair'; wall += kind == 'wall'; fill += kind == 'fill'
            if debug is not None: debug.append((float(p0[0]), float(p0[1]), kind))
    tot = hit + miss + closed + chair + fill; seen = hit + miss; closed += fill        # точки на стене карты — не мерятся и в счёт не идут (ПК5-К2)
    share = hit / seen if seen else None
    cen = C.mean(0); u = (e[0][1] - e[0][0]) / Lpx; n = np.array([-u[1], u[0]]); hl = Lpx / 2; hd = Dpx / 2   # торцы модуля листа
    S_ = np.arange(-(hl + W_), hl + W_ + 0.01, 0.5); T_ = np.arange(-0.8 * hd, 0.8 * hd + 0.01, 1.0)
    pts = cen[None, None, :] + S_[:, None, None] * u[None, None, :] + T_[None, :, None] * n[None, None, :]
    ix, iy = np.round(pts[..., 0] - x0).astype(int), np.round(pts[..., 1] - y0).astype(int); ok = (ix >= 0) & (iy >= 0) & (ix < x1 - x0) & (iy < y1 - y0)
    ix, iy = np.clip(ix, 0, x1 - x0 - 1), np.clip(iy, 0, y1 - y0 - 1); m_, gx_, gy_ = mg[iy, ix], gx[iy, ix], gy[iy, ix]
    rgb_ = src.rgb[y0:y1, x0:x1].astype(int); lum_, chr_ = rgb_.sum(2), rgb_.max(2) - rgb_.min(2); best_l = np.full(ix.shape, 10 ** 6); best_c = np.zeros(ix.shape, int)
    for dd in (-2, -1, 0, 1, 2):                                            # тушь торца — нейтральная: самый тёмный пиксель у края (±2 px вдоль стола) без цвета;
        jx = np.clip(np.round(pts[..., 0] - x0 + dd * u[0]).astype(int), 0, x1 - x0 - 1); jy = np.clip(np.round(pts[..., 1] - y0 + dd * u[1]).astype(int), 0, y1 - y0 - 1)
        l_ = lum_[jy, jx]; sel = l_ < best_l; best_l = np.where(sel, l_, best_l); best_c = np.where(sel, chr_[jy, jx], best_c)   # цветные номера мест — не торец
    perp = ok & (m_ >= thr) & (np.abs(gx_ * u[0] + gy_ * u[1]) >= cos_ * m_) & (best_c < 40)
    perp = ndimage.maximum_filter1d(perp.astype(np.uint8), 5, axis=0) > 0         # ±1 px вдоль стола
    free_ = ndimage.minimum_filter1d((ok & (best_c < 40)).astype(np.uint8), 5, axis=0) > 0   # точки сечения под цветной надписью — не в счёт покрытия
    nf = free_.sum(1); cov = np.where(nf >= 0.3 * max(1, perp.shape[1]), (perp & free_).sum(1) / np.maximum(nf, 1), 0.0) if perp.shape[1] else np.zeros(len(S_))
    lab, nl = ndimage.label(cov >= MOD_END_COVER)
    runs = [(float(S_[sl[0]][0]), float(S_[sl[0]][-1])) for sl in ndimage.find_objects(lab)] if nl else []   # полоса торца: линия и её толщина, двойная линия
    near = lambda z: min((min(max(z, r0), r1) for r0, r1 in runs if abs(min(max(z, r0), r1) - z) <= W_), key=lambda v: abs(v - z), default=None)   # ближайшая к торцу JSON точка полосы
    em, ep = near(-hl), near(hl)
    Lm = (ep - em) / k_ if em is not None and ep is not None and ep > em else None; Ld = Lpx / k_
    if debug is not None:
        for s_ in (em, ep):
            if s_ is not None: q_ = cen + u * s_; debug.append((float(q_[0] - n[0] * hd), float(q_[1] - n[1] * hd), 'end', float(q_[0] + n[0] * hd), float(q_[1] + n[1] * hd)))
    why = []
    if share is None or tot == 0 or seen < MOD_SEEN * tot: why.append(f'край закрыт предметами листа на {pc(1 - seen / tot if tot else 1.0, 0)} — мера стол не видит')
    elif share < MOD_SIDE: why.append(f'длинные стороны на краю модуля листа — {pc(share, 0)}')
    if Lm is not None and abs(Ld - Lm) > MOD_LEN_M: why.append(f'длина {fx(Ld, 2)} м ≠ модуль листа {fx(Lm, 2)} м')
    elif Lm is None and (em is None) != (ep is None):                      # v012 (КМ-13, ПК5-К1): виден один торец модуля — сдвиг вдоль стороны и короткий стол
        off = ((-hl) - em) / k_ if em is not None else (ep - hl) / k_         # > 0 — торец модуля снаружи стола, < 0 — стол заходит за торец модуля
        if off < -MOD_LEN_M or MOD_LEN_M < off < PED_M[0]: why.append(f'торец модуля листа в {fx(abs(off), 2)} м ' + ('внутри стола' if off < 0 else 'за торцом стола') + ' (второй торец не виден) — сдвиг вдоль или стол не того размера')
    return dict(share=share, seen=seen / tot if tot else 0.0, closed=closed, chair=chair, wall=wall, fill=fill, n=tot, L=Ld, L_mod=Lm,
                ends=[None if em is None else round((em + hl) / k_, 3), None if ep is None else round((ep - hl) / k_, 3)], ok=not why, why=why, pedestal=False)
PED_M = (0.25, 0.65)    # v011: тумба у торца стола (№90; unspot_map.workplaces, К-8): модуль листа длиннее стола на 0,25–0,65 м с одного торца
def pedestal_ok(R, floor_m):
    """v011: длина не сошлась, но один торец модуля листа — у торца стола (≤ 0,1 м), а другой дальше на 0,25–0,65 м и стол — модуль этажа (± 0,1 м):
    это стол с тумбой у торца (№90, тумба — не часть места) — не ошибка длины"""
    if R['L_mod'] is None or floor_m is None or abs(R['L'] - floor_m) > MOD_LEN_M or None in R['ends']: return False
    e0, e1 = R['ends']                                                     # < 0 у первого и > 0 у второго — торец модуля листа снаружи стола
    return (abs(e1) <= MOD_LEN_M and PED_M[0] <= -e0 <= PED_M[1]) or (abs(e0) <= MOD_LEN_M and PED_M[0] <= e1 <= PED_M[1])
def module_share(P, a, d, tol_m=MOD_TOL_M, thr=60.0, cos_=0.94, debug=None):
    """доля измеренных точек длинных сторон стола на краю модуля листа (Ч-37; ОВ20 г) — как desk_module -> доля | None (v008–v010 — тот же вызов;
    v011: точки, закрытые стулом или другим предметом листа, не мерятся)"""
    r = desk_module(P, a, d, tol_m, thr, cos_, debug=debug)
    return None if r is None else r['share']
def long_sides(d):
    """две длинные стороны модуля стола (край столешницы): короткие стороны модуля длинного стола на листе часто без линии раздела"""
    mr = d.minimum_rotated_rectangle
    if mr.geom_type != 'Polygon': return []
    c = list(mr.exterior.coords)[:4]; e = [(c[i], c[(i + 1) % 4]) for i in range(4)]
    e.sort(key=lambda z: -math.dist(*z)); return [LineString(z) for z in e[:2]]
def desk_modules(P, a):
    """стол JSON мест против модуля листа по каждому столу (Ч-37; список кропов К-11, v010) -> [(номер, стол, запись desk_module)];
    v011 (ПК4-К4): точки, закрытые стулом листа, не мерятся; длина — против модуля листа ± 0,1 м"""
    if getattr(P, 'MODS', None) is None:
        P.MODS = []
        if places(a) is not None and source(P, a):
            for n_, s, d in place_pts(P, a):
                if d is None: continue
                r = desk_module(P, a, d)
                if r is not None: P.MODS.append((n_, d, r))
            Lm = [r['L_mod'] for n_, d, r in P.MODS if r['L_mod'] is not None and abs(r['L'] - r['L_mod']) <= MOD_LEN_M]   # модуль этажа — по листу: медиана сошедшихся
            P.MOD_FLOOR = float(np.median(Lm)) if len(Lm) >= 3 else None
            for n_, d, r in P.MODS:
                if any(w.startswith('длина') for w in r['why']) and pedestal_ok(r, P.MOD_FLOOR):
                    r['why'] = [w for w in r['why'] if not w.startswith('длина')]; r['ok'] = not r['why']; r['pedestal'] = True
    return P.MODS
def desk_note(n_, r):
    """v011: место стола мимо модуля листа — причины меры (ПК4-К4) строкой"""
    return f'стол места {n_}: ' + '; '.join(r['why']) + (f' (закрыто предметами листа {pc(1 - r["seen"], 0)})' if r['seen'] < 1 else '') + ' — кроп К-11'
def seat_conflicts(P, a):
    """стул за чужим столом и два места на одном стуле — по JSON мест (ОВ21, Н11) -> ([(номер, стул)], [(номер, номер, стул)])"""
    if getattr(P, 'SEATX', None) is None:
        pp = place_pts(P, a); fo, tw = [], []
        dks = [(n_, s, d) for n_, s, d in pp if d is not None]; tr_ = STRtree([d for n_, s, d in dks]) if dks else None
        for i, (n_, s, d) in enumerate(dks):
            if s is None: continue
            ln = LineString([d.centroid.coords[0], s])
            if any(int(j) != i and dks[int(j)][2].intersection(ln).length > 0.1 * P.m for j in tr_.query(ln)): fo.append((n_, s))
        ss = [(n_, s) for n_, s, d in pp if s is not None]
        if len(ss) > 1:
            from scipy.spatial import cKDTree
            kt = cKDTree(np.array([s for n_, s in ss], float))
            for i, j in sorted(kt.query_pairs(0.2 * P.m)): tw.append((ss[i][0], ss[j][0], ss[i][1]))
        P.SEATX = (fo, tw)
    return P.SEATX
def c37(P, a, S):
    nm = 'Артефакт 3 против листа: номер места — в своём столе; стол — на модуле листа (≥ 80 % измеренных точек длинных сторон в 0,1 м от параллельного края туши, длина — модуль листа ± 0,1 м)'
    pl = places(a); src = source(P, a)
    if pl is None: return skip('Ч-37', nm, 'нет JSON мест (--places-json)')
    if not src: return skip('Ч-37', nm, 'нужны --source-png и --source-transform: стол сверяется с листом')
    pp = place_pts(P, a); bad_d, recs = [], []                              # v008: край модуля листа — параллельный стороне стола, в 0,1 м (ОВ20 г)
    for n_, d, r in desk_modules(P, a):                                     # v011 (ПК4-К4): закрытое стулом и предметом листа не мерится; длина — модуль листа ± 0,1 м
        recs.append(r)
        if not r['ok']: bad_d.append(W(d.centroid.coords[0], desk_note(n_, r)))
    sh_d = [r['share'] for r in recs if r['share'] is not None]
    kd = float(np.mean([r['ok'] for r in recs])) if recs else None
    bad_n, kn, nn, miss = [], None, 0, 0
    if a.sheet_numbers:
        NB, fr, meta = sheet_json(a.sheet_numbers, 'numbers'); pos = defaultdict(list)
        for e in NB:
            q = to_frame(P, [e['x'], e['y']], fr)
            if q is None: return skip('Ч-37', nm, 'номера листа — в px исходника: нужен --source-transform')
            pos[str(e.get('n', e.get('number', ''))).strip()].append(q[0])
        okn = 0
        for n_, s, d in pp:
            if d is None: continue
            ps = pos.get(str(n_).strip())
            if not ps: miss += 1; continue
            nn += 1; g = d.buffer(0.05 * P.m)
            if any(g.contains(Point(p)) for p in ps): okn += 1
            else: bad_n.append(W(min(ps, key=lambda p: d.distance(Point(p))), f'номер {n_} листа вне своего стола: {fx(min(d.distance(Point(p)) for p in ps) / P.m, 2)} м'))
        kn = okn / nn if nn else None
    fo, tw = seat_conflicts(P, a)                                           # v008 (ОВ21, Н11): стул за чужим столом; два места на одном стуле — по JSON мест
    bad_b = [W(s, f'место {n_}: стул за чужим столом — отрезок «стол — стул» пересекает другой стол (ОВ21) — кроп К-11 «стул:{n_}» при fail') for n_, s in fo] + \
            [W(s, f'места {i} и {j} на одном стуле (ближе 0,2 м) — кроп К-11 «два-места:{i}+{j}» при fail') for i, j, s in tw]
    fail_n = kn is not None and kn < 0.95                                  # Ф6: номер в своём столе
    fail_d = bool(bad_d)                                                    # v010 (К-5; №102, строка 204): столы на модуле — все, доля < 100 % — fail; стол мимо модуля — кроп К-11
    nside = sum(1 for r in recs if any(w.startswith('длинные') for w in r['why'])); nlen = sum(1 for r in recs if any(w.startswith('длина') for w in r['why']))
    nclo = sum(1 for r in recs if any(w.startswith('край закрыт') for w in r['why'])); nchk = sum(1 for r in recs if r['L_mod'] is not None)
    val = (f'столов {len(recs)}: на модуле листа {pc(kd)} (медиана доли длинных сторон {pc(float(np.median(sh_d)), 0) if sh_d else "—"})' +
           (f', мимо модуля {len(bad_d)}: стороны {nside}, длина {nlen}, край закрыт {nclo}' if bad_d else '') +
           f'; длина сверена у {nchk} (оба торца модуля листа видны), модуль этажа по листу {fx(P.MOD_FLOOR, 2) + " м" if getattr(P, "MOD_FLOOR", None) else "—"}' +
           (f', тумба у торца (№90) {sum(1 for r in recs if r.get("pedestal"))}' if any(r.get('pedestal') for r in recs) else '') +
           f'; закрыто стулом листа (--chairs-json) точек {sum(r["chair"] for r in recs)}' + ('' if getattr(a, 'chairs_json', None) else ' — стулья листа не даны') if recs else 'столов в JSON нет') + \
          (f'; номер в своём столе {pc(kn)} из {nn}' + (f', номера нет на листе {miss}' if miss else '') if a.sheet_numbers and kn is not None else '; номера листа не даны (--sheet-numbers) — не сверены' if not a.sheet_numbers else '; номеров листа с местами JSON нет')
    val += f'; стул за чужим столом и два места на одном стуле — {len(bad_b)}'
    no_num = bool(a.sheet_numbers and recs and nn == 0)                    # v012 (КМ-13): ни одного номера листа у мест JSON — формат номера (настройка) не тот: look, не pass
    if no_num: val += '; номера листа: ни одного совпадения с номерами мест — формат номера листа (unspot_map.sheet numbers --number-re) проверить — look'
    st = 'fail' if fail_n or fail_d else 'look' if bad_n or bad_b or no_num else 'pass' if recs and a.sheet_numbers else 'skip'
    P.CH37 = st
    if st == 'skip': return skip('Ч-37', nm, ('номера листа не даны (--sheet-numbers: python3 -m unspot_map.sheet numbers …) — номер в своём столе не сверен; ' if not a.sheet_numbers else '') + val, s=())
    return row('Ч-37', nm, val, 'номер в своём столе ≥ 95 % мест (Ф6), иначе fail; столы на модуле листа (0,1 м, ОВ20 г; v011: точки, закрытые стулом или другим предметом листа, '
               'не мерятся, длина — модуль листа ± 0,1 м, ПК4-К4) — все: доля < 100 % — fail (№102), стол мимо модуля — кроп К-11 «модуль:N»; '
               'стул за чужим столом, место на чужом стуле — look, кроп К-11 (при fail — «стул:N», «два-места:N»)', st, bad_n + bad_d + bad_b)
def c38(P, a, S):
    nm = 'Стекло листа под стеклом карты: доля длины без участков дверей; участки без стекла от 1 м'
    if not a.sheet_glass: return skip('Ч-38', nm, 'нет стекла листа (--sheet-glass: python3 -m unspot_map.sheet glass …) — внутреннее стекло не сверено')
    E, fr, meta = sheet_json(a.sheet_glass, 'segments'); L = []
    for s in E:
        q = to_frame(P, s, fr)
        if q is None: return skip('Ч-38', nm, 'стекло листа — в px исходника: нужен --source-transform')
        if len(q) >= 2 and LineString(q).length > 0: L.append(LineString(q))
    if not L: return skip('Ч-38', nm, 'в --sheet-glass нет отрезков')
    U = unary_union(L); near = P.shell.buffer(0.5 * P.m) if not P.shell.is_empty else None
    if near is not None: U = U.intersection(near)
    if P.ops: U = U.difference(unary_union([o.poly.buffer(0.1 * P.m) for o in P.ops]))          # ОВ24: доля — без участков дверей
    tot = U.length
    if tot <= 0: return skip('Ч-38', nm, 'стекла листа в контуре здания нет')
    tl = max(1.5 * P.T, 0.15 * P.m); G = P.glass.buffer(tl) if not P.glass.is_empty else Polygon(); k = U.intersection(G).length / tot if not G.is_empty else 0.0
    un = U.difference(G) if not G.is_empty else U; pcs = sorted([g for g in lines(linemerge(lines(un))) if g.length >= P.m], key=lambda g: -g.length) if not un.is_empty else []
    wh, cs = [], []
    for g in pcs:                                                          # двойная линия стекла листа — одно место
        c = g.interpolate(0.5, normalized=True)
        if any(c.distance(o) < 0.3 * P.m for o in cs): continue
        cs.append(c); rm = room_at(P, c.coords[0]); wh.append(W(c.coords[0], f'стекло листа {fx(g.length / P.m)} м без стекла карты' + (f' — {rm.name}' if rm is not None else '')))
    return row('Ч-38', nm, f'{pc(k)} стекла листа ({fx(tot / P.m)} м) под стеклом карты в {fx(tl / P.m, 2)} м; без стекла от 1 м — {len(wh)}' + (f'; вход: {meta.get("how")}' if meta.get('how') else ''),
               'стекло листа — стеклом карты (map/rules/60 §1, Ф7); участок без стекла от 1 м — look: серая стена или «не размечать» строкой блока Б', 'look' if wh else 'pass', wh)
TYPE_KEEP = re.compile(r'print|copy|копир|печат|technical|техн', re.I)   # копировальные и технические — своим типом (строка 177)
TYPE_ASK = re.compile(r'^(meeting|office|cabinet|other|room)?$', re.I)   # «похоже и на переговорную, и на кабинет»
def furniture_types(P, a):
    """тип по мебели листа (строки 176–177; map/rules/50 §1): стол с ≥ 2 местами (стулья, кресла листа, не места JSON) — meeting;
    пусто — office; помещения с местами, print, technical — не трогаются -> [(помещение, тип по правилу, стульев)] или None"""
    if not a.chairs_json: return None
    cj = json.load(open(a.chairs_json, encoding='utf-8')); fr = cj.get('frame', 'source') if isinstance(cj, dict) else 'source'
    ch = cj.get('chairs', []) if isinstance(cj, dict) else cj
    if not ch: return None                                                 # пустой список стульев — тип по мебели не сверен (не «все кабинеты»)
    xy = to_frame(P, [[c['x'], c['y']] if isinstance(c, dict) else list(c)[:2] for c in ch], fr)
    if xy is None: return None
    st = np.array([s for n_, s, d in place_pts(P, a) if s is not None], float).reshape(-1, 2)
    free = [c for c in xy if not len(st) or np.hypot(*(st - c).T).min() > 0.6 * P.m]          # стул места — не мебель комнаты
    out = []
    for q in P.rooms:
        t = (q.type or '').strip()
        if TYPE_KEEP.search(f'{t} {q.name}') or not (TYPE_ASK.match(t) or re.search(r'переговор|кабинет', q.name or '', re.I)): continue
        if len(st) and any(q.poly.contains(Point(s)) for s in st): continue
        n_ = sum(1 for c in free if q.poly.contains(Point(c)))
        out.append((q, 'meeting' if n_ >= 2 else 'office' if n_ == 0 else None, n_))
    return out
def c39(P, a, S):
    nm = 'Тип помещения по мебели листа: стол с ≥ 2 местами — переговорная, пусто — личный кабинет; копировальные и технические — своим типом'
    T_ = furniture_types(P, a)
    if T_ is None: return skip('Ч-39', nm, 'нет стульев листа (--chairs-json), список пуст или нет преобразования: тип по мебели не сверен')
    lk = [W(at(q), f'{q.name}: на карте {q.type or "без типа"}, по мебели листа — {t} (стульев {n_})') for q, t, n_ in T_
          if (t == 'meeting' and rkind(q) != 'meeting') or (t == 'office' and rkind(q) == 'meeting')]
    return row('Ч-39', nm, f'помещений под правило {len(T_)}: по мебели листа переговорных {sum(t == "meeting" for _, t, _ in T_)}, кабинетов {sum(t == "office" for _, t, _ in T_)}, '
               f'не решено (один стул) {sum(t is None for _, t, _ in T_)}; тип карты расходится — {len(lk)}', 'расхождение — look, кадр К-06: тип в карточке и цвет своего типа',
               'look' if lk else 'pass', lk)

# ------------------------------------------------------------------ v13: проверки без номера Ч (map/rules/80 §2, «Проверки без номера Ч»): шлюз их не решает
MEET_RE = re.compile(r'meeting|переговор|conference', re.I)
def mr_units(P):
    """столы переговорных карты: [dict(room, top — столешница, geom — стол со стульями, chairs — стульев карты | None, key)]. Стол — экземпляр слоя furniture
    (символ стола map/kit/61, стол легенды map/kit/63 или id/тип со словом table|стол); группа столов (`meeting-tables`) — по прямым потомкам-столам;
    стулья — внутри стола (символ стула, id «chair|стул», число стульев символа map/kit/61) и отдельные экземпляры-стулья той же переговорной"""
    allK = furn_all(P)
    meet = [q for q in P.rooms_all if MEET_RE.search(f'{q.type} {q.name} {q.a.get("data-title", "")}')]
    room_of = lambda pt: min([q for q in meet if q.poly.contains(pt)], key=lambda q: q.poly.area, default=None) if pt is not None else None
    geo = lambda rs: [r for r in rs if r.subs]
    is_t = lambda r: r.a.get('data-figma') in MR_TABLE_FIGMA or bool(MR_TABLE_RE.search(own_tag(r)))
    is_c = lambda r: r.a.get('data-figma') in MR_CHAIR_FIGMA or bool(MR_CHAIR_RE.search(own_tag(r)))
    units, loose = [], []
    for k, rs in allK.items():
        kind = mr_kind(rs); g_ = geo(rs); rm = room_of(inst_pt(g_)) if g_ else None
        if not kind or rm is None: continue
        if kind == 'chair': loose.append((rm, inst_geom(g_))); continue
        root = min(rs, key=lambda r: r.depth)
        sub = [] if root.a.get('data-figma') in MR_TABLE_FIGMA else [r for r in rs if r.depth == root.depth + 1 and is_t(r)]
        for u in (sub or [root]):
            us = [r for r in rs if r is u or u.idx in r.anc]
            ch_roots = [r for r in us if r is not u and is_c(r)]
            ch_roots = [r for r in ch_roots if not any(c.idx in r.anc for c in ch_roots)]
            known = [MR_TABLE_FIGMA[r.a['data-figma']] for r in us if r.a.get('data-figma') in MR_TABLE_FIGMA]
            n_ch = len(ch_roots) + sum(v for v in known if v) if (ch_roots or any(v is not None for v in known)) else None
            inch = {r.idx for c in ch_roots for r in us if r is c or c.idx in r.anc}
            tops = [r.poly for r in us if r.subs and r.idx not in inch and not r.poly.is_empty]
            g = inst_geom(geo(us))
            if tops and not g.is_empty: units.append(dict(room=room_of(g.representative_point()) or rm, top=max(tops, key=lambda t: t.area), geom=g, chairs=n_ch, key=u.a.get('id') or k))
    for rm, g in loose:                                                  # отдельный стул — к ближайшему столу своей переговорной
        cand = [u for u in units if u['room'] is rm]
        if not cand: continue
        u = min(cand, key=lambda u: u['top'].distance(g)); u['geom'] = u['geom'].union(g); u['chairs'] = (u['chairs'] or 0) + 1
    return units
def sheet_tables(P, a):
    """столы листа (--sheet-tables) в px фрейма -> [Polygon] | None"""
    f = getattr(a, 'sheet_tables', None)
    if not f: return None
    T_, fr, D = sheet_json(f, 'tables')
    if not T_ and isinstance(D, dict) and D.get('furniture_desks'): T_, fr = [dict(poly=d['desk']) for d in D['furniture_desks'] if d.get('desk')], 'plan'   # places_plan: кадр карты
    out = []
    for t in T_:
        pts = to_frame(P, (t.get('poly') or t.get('desk')) if isinstance(t, dict) else t, fr)
        if pts is not None and len(pts) >= 3: out.append(make_valid(Polygon(pts)))
    return out
def sheet_meet_chairs(P, a, rm):
    """стулья листа (--chairs-json) в переговорной, кроме стульев мест JSON (0,6 м — как Ч-39) -> число | None"""
    if not a.chairs_json: return None
    cj = json.load(open(a.chairs_json, encoding='utf-8')); fr = cj.get('frame', 'source') if isinstance(cj, dict) else 'source'
    ch = cj.get('chairs', []) if isinstance(cj, dict) else cj
    xy = to_frame(P, [[c['x'], c['y']] if isinstance(c, dict) else list(c)[:2] for c in ch], fr) if ch else np.zeros((0, 2))
    if xy is None: return None
    st = np.array([s_ for n_, s_, d in place_pts(P, a) if s_ is not None], float).reshape(-1, 2)
    return sum(1 for c in xy if rm.poly.contains(Point(c)) and (not len(st) or np.hypot(*(st - c).T).min() > 0.6 * P.m))
def x_mr_sheet(P, a, S):
    i, nm = 'БЧ-стол-лист', 'Стол переговорной против стола листа: габарит ± 10 % по каждой стороне, число стульев равно (без номера Ч; строка 413)'
    U = mr_units(P)
    if not U: return dict(skip(i, nm, 'столов переговорных на карте нет'), no_gate=True)
    ST = sheet_tables(P, a); look, notes, by_room = [], [], defaultdict(list)
    if ST is None: notes.append('столов листа нет (--sheet-tables) — габарит не сверен')
    if not a.chairs_json: notes.append('стульев листа нет (--chairs-json) — число стульев не сверено')
    for u in U:
        by_room[id(u['room'])].append(u); s1, l1, _ = sides(u['top']); c = u['top'].centroid
        if ST is not None:
            cand = [t for t in ST if u['room'].poly.intersects(t)]
            t = max(cand, key=lambda t: (t.intersection(u['top']).area, -t.centroid.distance(c)), default=None)
            if t is None: look.append(W(c.coords[0], f'{u["room"].name}: стол карты {fx(l1 / P.m, 2)} × {fx(s1 / P.m, 2)} м — стола листа в переговорной нет'))
            else:
                s2, l2, _ = sides(t); dl, ds = l1 / max(l2, 1e-9) - 1, s1 / max(s2, 1e-9) - 1
                if abs(dl) > MR_TOL + 1e-9 or abs(ds) > MR_TOL + 1e-9:
                    look.append(W(c.coords[0], f'{u["room"].name}: стол карты {fx(l1 / P.m, 2)} × {fx(s1 / P.m, 2)} м, листа {fx(l2 / P.m, 2)} × {fx(s2 / P.m, 2)} м — '
                                                f'{"+" if dl >= 0 else ""}{pc(dl, 0)} и {"+" if ds >= 0 else ""}{pc(ds, 0)}, допуск ± 10 %'))
    for us in by_room.values():
        rm = us[0]['room']; n_s = sheet_meet_chairs(P, a, rm); n_m = None if any(u['chairs'] is None for u in us) else sum(u['chairs'] for u in us)
        if n_s is None: continue
        if n_m is None: look.append(W(at(rm), f'{rm.name}: стульев листа {n_s}, на карте число стульев не определено (символ без числа стульев)'))
        elif n_m != n_s: look.append(W(at(rm), f'{rm.name}: стульев на карте {n_m}, на листе {n_s}'))
    if ST is None and not a.chairs_json: return dict(skip(i, nm, '; '.join(notes), val=f'столов переговорных на карте {len(U)}'), no_gate=True)
    return dict(row(i, nm, f'столов переговорных на карте {len(U)}, расхождений {len(look)}' + ''.join(f'; {t}' for t in notes),
                    'габарит ± 10 % по каждой стороне, стульев столько же, сколько на листе; расхождение — look с кропом К-06 (строка 413); шлюз не решает', 'look' if look else 'pass', look), no_gate=True)
def x_mr_fit(P, a, S):
    i, nm = 'БЧ-стол-стена', 'Стол переговорной помещается: габарит со стульями в комнате, зазор до стены ≥ 0,5 м (без номера Ч)'
    U = mr_units(P)
    if not U: return dict(skip(i, nm, 'столов переговорных на карте нет'), no_gate=True)
    look, gaps = [], []
    for u in U:
        rm = u['room']; inner = rm.poly.buffer(-rm.sw / 2, join_style='mitre') if rm.sw else rm.poly; g = u['geom']
        if inner.is_empty or not inner.buffer(1e-6).contains(g):
            look.append(W(g.representative_point().coords[0], f'{rm.name}: стол со стульями выходит за внутреннюю грань стены — не помещается')); continue
        gp = inner.boundary.distance(g) / P.m; gaps.append(gp)
        if gp < MR_GAP_M - 1e-9: look.append(W(g.representative_point().coords[0], f'{rm.name}: тесно — зазор стола со стульями до стены {fx(gp, 2)} м < 0,5 м'))
    return dict(row(i, nm, f'столов переговорных {len(U)}; тесно или не помещается — {len(look)}' + (f'; наименьший зазор {fx(min(gaps), 2)} м' if gaps else '') +
                    ('' if P.scale else ' (масштаб не дан — 1 м ≈ 6T)'), 'зазор ≥ 0,5 м; меньше — «тесно», look с кропом (map/rules/80 §2); шлюз не решает', 'look' if look else 'pass', look), no_gate=True)
EXTRA = [x_mr_sheet, x_mr_fit]
# ------------------------------------------------------------------ список кропов кодом (map/rules/80 §3; Г1-2)
OBJ_GROUPS = ('К-01', 'К-02', 'К-03', 'К-06', 'К-07', 'К-08', 'К-11', 'К-12')   # вердикт — на каждый объект списка; v008: К-03, К-08 — объектами (ПК1-К9)
BY_LOOK = {'К-04': ('Ч-18',), 'К-09': ('Ч-20',), 'К-10': ('Ч-07', 'Ч-08', 'Ч-11', 'Ч-16', 'Ч-32')}   # места — вердикты look своих Ч (--verdicts)
def crop_list(P, a):
    """{К-NN: [{id, x, y, what}]} — что смотреть; размер списка задаёт план, а не автор"""
    L, ids = defaultdict(list), Counter()
    def add(g, oid, pt, what):
        ids[(g, oid)] += 1; oid = oid if ids[(g, oid)] == 1 else f'{oid}#{ids[(g, oid)]}'
        L[g].append(dict(id=oid, x=round(float(pt[0]), 1), y=round(float(pt[1]), 1), what=what))
    rid = lambda q: q.id or q.name or 'помещение'
    for q in P.rooms_all:
        k = rkind(q); c = at(q)
        if k == 'stair': add('К-01', rid(q), c, f'лестница {q.name}')
        if k in ('lift', 'shaft'): add('К-02', rid(q), c, f'{"лифт" if k == "lift" else "шахта"} {q.name}')
        if k in ('kitchen', 'meeting'): add('К-06', rid(q), c, f'{"кухня" if k == "kitchen" else "переговорная"} {q.name}')
    for x in crosses(P, a) or []:
        rm = room_at(P, x['c'])
        if rm is None or rkind(rm) not in ('lift', 'shaft'): add('К-02', f'квадрат@{x["c"][0]:.0f},{x["c"][1]:.0f}', x['c'], f'квадрат с диагоналями листа {fx(x["w"], 2)} × {fx(x["h"], 2)} м' + (f' в {rm.name}' if rm else ''))
    for q in P.rooms_all:                                                  # v008 (ПК1-К9): К-03 — концы коридоров и примыкания к открытым зонам
        if rkind(q) != 'corridor': continue
        s_, l_, u = sides(q.poly)
        if u is not None and l_ >= 3 * s_ and l_ >= 2 * P.m:
            c0 = np.array(q.poly.centroid.coords[0])
            for k_, sg in ((1, -1), (2, 1)): add('К-03', f'{rid(q)}:конец{k_}', c0 + sg * u * max(l_ / 2 - 0.5 * s_, 0), f'конец коридора {q.name}')
        for z in P.rooms_all:
            if z is q or not (z in P.open or rkind(z) in ('openspace', 'corridor')) or (rkind(z) == 'corridor' and (rid(z), tuple(at(z))) < (rid(q), tuple(at(q)))): continue   # v011 (ПК4-К16): пара «коридор × коридор» — по rid, а не id(): id объекта не переворачивается между версиями
            x = q.poly.boundary.intersection(z.poly.buffer(max(P.T, 1.0)))
            if x.length >= 0.5 * P.m: add('К-03', f'{rid(q)}×{rid(z)}', x.interpolate(0.5, normalized=True).coords[0], f'примыкание коридора {q.name} к {z.name}')
    seen8 = []                                                             # К-08 — углы и изломы фасада от 10°, дуги стен — объектами
    for g in parts(P.ring):
        R_ = clean_pts(list(g.exterior.coords)[:-1], True); n_ = len(R_)
        for i in range(n_):
            a_, b_, c_ = R_[i - 1], R_[i], R_[(i + 1) % n_]; t_ = turn((b_[0] - a_[0], b_[1] - a_[1]), (c_[0] - b_[0], c_[1] - b_[1]))
            if t_ >= 10 and min(math.dist(a_, b_), math.dist(b_, c_)) >= 0.3 * P.m and not any(math.dist(b_, o) < 0.5 * P.m for o in seen8):
                seen8.append(b_); add('К-08', f'угол@{b_[0]:.0f},{b_[1]:.0f}', b_, f'угол или излом фасада {t_:.0f}°')
    def on_curve(r):                                                       # точка объекта дуги — на середине криволинейной части пути, не внутри помещения
        cv = [pts[i] for (pts, c_, k_), vx in zip(r.subs, r.vxs) for i, kk in vx if kk == 'C']
        return cv[len(cv) // 2] if cv else at(r)
    for r in ([] if P.faces else P.rooms) + P.outer + P.free + P.gring + P.wallpolys:
        if r.curves: add('К-08', f'дуга:{r.id or r.name}', on_curve(r), f'дуга стены {r.name}: кривых {r.curves} — Ч-12')
    bg = badges(P)
    for b in bg.B:
        c = b.poly.centroid
        if any(t.box.distance(c) <= 40 + bg.dia(b) / 2 for t in texts(P)): add('К-07', b.inst or b.id or 'бейдж', c.coords[0], 'бейдж у подписи ближе 40 px')
    pl = places(a) or []; kx, ky = pic(P, a)
    dk = [(p, make_valid(Polygon([(x / kx, y / ky) for x, y in p['desk']]))) for p in pl if p.get('desk') and len(p['desk']) >= 3]
    if dk:
        U = unary_union([d.buffer(0.1 * P.m) for p, d in dk]); best = {}
        for b in parts(U):
            n = sum(1 for p, d in dk if b.contains(d.centroid)); rm = room_at(P, b.representative_point().coords[0]); k = id(rm)
            if n and (k not in best or n > best[k][1]): best[k] = (b, n, rm)
        for b, n, rm in best.values(): add('К-11', f'блок:{rid(rm) if rm else "вне помещений"}', b.representative_point().coords[0], f'блок столов, мест {n}' + (f', {rm.name}' if rm else ''))
    for n, p in enumerate(pl):
        how = str(p.get('how') or p.get('method') or ''); pt = seat_pt(p)
        if re.search(r'сторон|не найден|side|not.?found', how, re.I) and pt is not None:      # v007: ключ — номер места, а не None#N («Д» п. 9)
            add('К-11', pnum(p, n), np.array(pt) / [kx, ky], f'место «{how}»')
    for n_, d, r in desk_modules(P, a):                                    # v010 (К-5; №102): каждый стол мимо модуля листа — объект К-11 с вердиктом
        if not r['ok']:                                                    # v011 (ПК4-К4): причины меры в «what», контур стола — в кадр поверх листа (poly)
            add('К-11', f'модуль:{n_}', d.centroid.coords[0], f'стол места {n_} мимо модуля листа (Ч-37): ' + '; '.join(r['why']))
            L[('К-11')][-1]['poly'] = [[round(float(x), 1), round(float(y), 1)] for x, y in list(d.exterior.coords)[:-1]]
    if getattr(P, 'CH37', None) == 'fail':                                 # v011 (ПК4-К3): при fail Ч-37 его места look — объектами К-11 с вердиктом
        fo, tw = seat_conflicts(P, a)
        for n_, s_ in fo: add('К-11', f'стул:{n_}', s_, f'место {n_}: стул за чужим столом (Ч-37, ОВ21)')
        for i, j, s_ in tw: add('К-11', f'два-места:{i}+{j}', s_, f'места {i} и {j} на одном стуле (Ч-37)')
    rs = sorted([q for q in P.rooms if rkind(q) != 'corridor'], key=lambda q: (rid(q), at(q)))
    rng = random.Random(int(hashlib.sha256((P.text or '').encode()).hexdigest()[:12], 16))   # генератор, не автор: зерно — хеш SVG
    for q in rng.sample(rs, min(3, len(rs))): add('К-12', rid(q), at(q), f'случайное помещение {q.name}')
    add('К-12', 'цвет', (P.W / 2, P.H / 2), 'весь план рядом со словами заявки о цвете — Ч-25')
    return {k: L[k] for k in sorted(L)}

# ------------------------------------------------------------------ шлюз сдачи (map/rules/80 §0, стоп-правило кодом) — v007: честность шлюза
# Ф1, Р1–Р4, Н18, Т3-2, Т4-11, «Д» п. 9, ОВ12, ОВ14, ОВ22: причина принятого — вид из закрытого списка и ссылка; реестры — с SHA-256 SVG;
# вердикт — на каждое место, со статусом и кадром этого круга (review/gate_frames.py: в имени кадра — хеш SVG); перенос — только с кадром
# этого круга; «не исправлено», «в находки», «не нарисован» не переносятся; в gate.json — версия кода и SHA-256 приёмки.
CODE_DIR = os.path.dirname(os.path.abspath(__file__))
WHY_KINDS = {'false_fail': 'ложный fail проверки — ссылка на предложение «proposals/map|both|plan/….md»',
             'owner': 'решение владельца — строка реестра «ref/core/10, строка N»',
             'question': 'открытый вопрос владельцу — «core/rules/20, вопрос N» или файл картинки вопроса (map/rules/50 §2)',
             'source': 'так нарисовано на исходнике — кадр места этого SVG (review/gate_frames.py)'}
WHY_REF = {'false_fail': re.compile(r'proposals/(map|both|plan)/\S+\.md', re.I), 'owner': re.compile(r'ref/core/10\D{0,40}?\d+', re.I),
           'question': re.compile(r'core/rules/20\D{0,40}?\d+', re.I)}
STATUS_V = {'совпадает': 'совпадает', 'match': 'совпадает', 'исправлено': 'исправлено', 'fixed': 'исправлено',
            'объяснено': 'объяснено', 'explained': 'объяснено', 'вопрос': 'вопрос', 'question': 'вопрос'}
NO_CARRY = re.compile(r'не\s+исправлен|в\s+находк|не\s+нарисован', re.I)   # такой вердикт без нового кадра не переносится (ОВ22)
sha256f = lambda p: hashlib.sha256(open(p, 'rb').read()).hexdigest()
def safe(s): return re.sub(r'[^0-9A-Za-zА-Яа-яЁё.@#,_+-]+', '_', str(s)).strip('_')[:64] or '_'
def frame_name(h, gid, key):
    """имя кадра: <первые 12 знаков SHA-256 SVG>__<Ч-NN | К-NN>__<ключ места или объекта>.png (review/gate_frames.py)"""
    return f'{h[:12]}__{gid}__{safe(key)}.png'
def place_key(i, w):
    """ключ места look и fail: номер в списке проверки и координаты, px фрейма"""
    return f'{i + 1:03d}' + (f'__x{w["x"]:.0f}_y{w["y"]:.0f}' if w.get('x') is not None else '')
def code_id():
    """версия кода и SHA-256 приёмки: канонический код — тот, что совпадает с code/MANIFEST.json выпуска (map/rules/80 §1, шаг 11)"""
    h = sha256f(os.path.abspath(__file__)); mp = os.path.join(CODE_DIR, 'MANIFEST.json')
    try: man = json.load(open(mp, encoding='utf-8'))
    except Exception: return dict(version=None, made_utc=None, acceptance_checks_sha256=h, canonical=False, why='нет code/MANIFEST.json рядом с кодом приёмки')
    ok = man.get('files', {}).get('acceptance_checks.py', {}).get('sha256') == h
    return dict(version=man.get('version'), made_utc=man.get('made_utc'), acceptance_checks_sha256=h, canonical=ok,
                why='' if ok else f'acceptance_checks.py отличается от code/MANIFEST.json v{man.get("version")} — код не канонический')
def _jload(f):
    D = json.load(open(f, encoding='utf-8')) if f else {}
    return D if isinstance(D, dict) else {'_список': D}
def _vtext(e): return str((e.get('вердикт') or e.get('verdict') or '') if isinstance(e, dict) else (e or '')).strip()
def vstatus(e):
    """статус вердикта (Ф1, п. 2): совпадает | исправлено: что | объяснено: почему | вопрос: № — полем «статус» или началом вердикта"""
    t = _vtext(e); s = str(e.get('статус') or e.get('status') or '').strip().lower() if isinstance(e, dict) else ''
    m = re.match(r'\s*(совпадает|исправлено|объяснено|вопрос|match|fixed|explained|question)\b', t, re.I)
    st = STATUS_V.get(s or (m[1].lower() if m else ''))
    if not st: return None, 'нет статуса (совпадает | исправлено | объяснено | вопрос)'
    rest = t[m.end():] if m else t
    if st != 'совпадает' and len(re.sub(r'^[\s:—–-]+', '', rest)) < 3: return None, f'«{st}» без пояснения: что, почему или номер'
    if st == 'вопрос' and not re.search(r'\d', t): return None, '«вопрос» без номера'
    return st, ''
class Gate:
    """сверки одного прогона шлюза: SVG, его хеш, папки кадров"""
    def __init__(s, a, h):
        s.a, s.h, s.bases = a, h, [d for d in [a.frames] + [os.path.dirname(os.path.abspath(f)) for f in (a.verdicts, a.crops, a.accept) if f] if d]
    def path(s, f):
        if not f: return None
        return next((q for q in ([f] if os.path.isabs(f) else [os.path.join(b, f) for b in s.bases] + [f]) if os.path.exists(q)), None)
    def frame(s, f, gid, check=None):
        """кадр этого круга: имя — с хешем этого SVG и id группы, место — то же, файл есть -> (путь, '') | (None, почему)"""
        if not f: return None, 'нет кадра'
        b = os.path.basename(str(f))
        if not b.startswith(s.h[:12] + '__'): return None, f'кадр {b} снят не с этого SVG (в имени нет {s.h[:12]})'
        if f'__{gid}__' not in b: return None, f'кадр {b} — не {gid}'
        if check is not None and not check(b): return None, f'кадр {b} — другого места или объекта'
        p = s.path(str(f))
        return (p, '') if p else (None, f'нет файла кадра {b}')
    def verdict(s, e, gid, check=None, need_frame=True):
        """вердикт места или объекта: статус, кадр этого круга; перенос {вердикт, кадр, из} — пиксели кадров равны -> ошибка | ''.
        Кадр не обязателен только у места без координат: его кадр код не строит (дубль номера, весь план)"""
        if not isinstance(e, dict): return 'вердикт строкой — нужен {"статус", "вердикт", "кадр"}' if _vtext(e) else 'нет вердикта'
        st, why = vstatus(e)
        if not st: return why
        f = e.get('кадр') or e.get('frame')
        if not f and not need_frame: return ''
        p, why = s.frame(f, gid, check)
        if not p: return why
        if e.get('из') or e.get('from'):
            if NO_CARRY.search(_vtext(e)): return f'вердикт «{_vtext(e)[:40]}» не переносится — нужен новый вердикт по кадру этого круга (map/rules/80 §3; ОВ22)'
            q = s.path(str(e.get('из') or e.get('from')))
            if not q: return f'нет прежнего кадра {e.get("из") or e.get("from")}'
            x, y = (np.asarray(Image.open(f).convert('RGB')) for f in (p, q))
            if x.shape != y.shape or not np.array_equal(x, y): return f'кадр изменился против {os.path.basename(q)} — вердикт заново'
        return ''
def _near(name, x, y, tol=3.0):
    m = re.search(r'__x(-?\d+)_y(-?\d+)', name)
    return bool(m) and abs(int(m[1]) - x) <= tol + 0.5 and abs(int(m[2]) - y) <= tol + 0.5
def _vplaces(v, G):
    """вердикты look: список мест, файл с ним (путь — от папки файла вердиктов) или {'куски': [...]}; {'n': N} без мест — ошибка"""
    if isinstance(v, str):
        p = G.path(v)
        if not p: return None, f'нет файла вердиктов {v}'
        v = json.load(open(p, encoding='utf-8'))
    if isinstance(v, dict):
        if 'n' in v and not any(k in v for k in ('куски', 'places', 'verdicts', 'места')):
            return None, 'вердикт числом {"n": N} без мест — нужен вердикт на каждое место с координатами (Ф1, п. 1)'
        v = v.get('куски') or v.get('places') or v.get('verdicts') or v.get('места') or []
    return [e for e in (v or []) if isinstance(e, dict)], ''
STEP_FILES = (('0', 'приём исходника', 'intake.md', None), ('12', 'стулья листа', 'chairs.json', 'chairs_json'), ('12', 'места', 'places.json', 'places_json'))   # map/00 §3, короткий путь (Р22)
def step_files(a):
    """файлы шагов круга (v008, Р22): шаг 0 — intake.md, шаг 12 — chairs.json и places.json; файл — ключом приёмки или в папке круга
    (--round-dir, иначе папка SVG); intake.md — ещё рядом с исходником -> [(шаг, что, файл, путь | None)]"""
    rd = getattr(a, 'round_dir', None) or os.path.dirname(os.path.abspath(a.svg)); out = []
    for st, what, fn, key in STEP_FILES:
        p = getattr(a, key, None) if key else None
        cand = ([p] if p else []) + [os.path.join(rd, fn)] + ([os.path.join(os.path.dirname(os.path.abspath(a.source_png)), fn)] if fn == 'intake.md' and a.source_png else [])
        out.append((st, what, fn, next((c for c in cand if c and os.path.exists(c)), None)))
    return out
def gate_eval(res, a, CL=None, h=None, cid=None):
    """стоп-правило кодом, v007. fail — запись реестра с видом причины и ссылкой; look — вердикт со статусом и кадром этого круга
    на каждое место; skip — строка «чем проверено»; кропы — вердикт со статусом и кадром на каждый объект списка кодом; реестры — от этого SVG"""
    A, V, N, K = (_jload(f) for f in (a.accept, a.verdicts, a.notes, a.crops)); G = Gate(a, h); stops, acc, rev, notes = [], [], [], []
    cid = cid or code_id()
    if not cid['canonical']: stops.append(f'код: {cid["why"]} — числа и шлюз считает только канонический код (map/rules/80 §1, шаг 11)')
    for st, what, fn, pth in step_files(a):                                # v008 (Р22): нет файла шага — стоп с именем шага (map/00 §3, короткий путь)
        key = next((k for s_, w_, f_, k in STEP_FILES if f_ == fn), None)
        if not pth: stops.append(f'нет файла шага {st} «{what}»: {fn} — ни ключом приёмки, ни в папке круга (map/00 §3, короткий путь)')
        elif key and not getattr(a, key, None): stops.append(f'файл шага {st} «{what}» {os.path.basename(pth)} лежит в папке круга, но не дан ключом --{key.replace("_", "-")}: приёмка его не видит')
    for nm, D, need in (('--accept', A, a.accept), ('--verdicts', V, a.verdicts), ('--crops', K, a.crops), ('--notes', N, False)):
        g = str(D.get('svg_sha256') or '').strip().lower()
        if need and not g: stops.append(f'{nm} {os.path.basename(need)}: нет svg_sha256 — нельзя проверить, что реестр от этой карты (SHA-256 SVG — {h})')
        elif g and g != h: stops.append(f'{nm} {os.path.basename(need or "?") if need else ""}: РЕЕСТР ОТ ДРУГОЙ КАРТЫ — svg_sha256 {g[:12]}…, проверяемый SVG {h[:12]}…')
    for c in res:
        if c.get('no_gate'): continue                                     # v13: проверки без номера Ч шлюз не решает (map/rules/80 §2)
        i, st, n = c['id'], c['status'], c.get('where_total') or 0; W_ = c.get('where_all') or c.get('where') or []
        if st == 'fail':
            e = A.get(i) or {}
            if not e: stops.append(f'{i}: fail не принят — нужна запись реестра --accept: max мест, why {{kind, ref, text}}, by'); continue
            w = e.get('why')
            if not isinstance(w, dict):
                stops.append(f'{i}: причина строкой — нужен why {{"kind": false_fail | owner | question | source, "ref": ссылка, "text": пояснение}} (map/rules/80 §0, п. 3)'); continue
            k, ref = str(w.get('kind') or '').strip(), str(w.get('ref') or '').strip()
            if k not in WHY_KINDS: stops.append(f'{i}: вид причины «{k}» — не из закрытого списка: ' + ', '.join(WHY_KINDS)); continue
            if not ref: stops.append(f'{i}: причина {k} без ссылки — {WHY_KINDS[k]}'); continue
            if k == 'source':
                p, why = G.frame(ref, i)
                if not p: stops.append(f'{i}: причина source — {why}; нужен кадр места этого SVG'); continue
            elif k == 'question' and G.path(ref) and re.search(r'\.(png|jpe?g)$', ref, re.I): pass
            elif not WHY_REF[k].search(ref): stops.append(f'{i}: ссылка «{ref[:60]}» не по виду {k} — {WHY_KINDS[k]}'); continue
            if max(n, 1) > int(e.get('max', 0)): stops.append(f'{i}: мест {n} больше принятых {e.get("max")} — новые места, посмотреть'); continue
            acc.append(dict(id=i, n=n, max=e.get('max'), kind=k, ref=ref, why=str(w.get('text') or ''), by=e.get('by', 'чат')))
        elif st == 'look':
            vs, err = _vplaces(V.get(i), G) if i in V else ([], '')
            if err: stops.append(f'{i}: {err}'); continue
            bad, got = [], 0
            for j, w in enumerate(W_ or [dict(x=None, y=None, note=c.get('value', ''))]):
                if w.get('x') is not None:
                    cand = [e for e in vs if isinstance(e.get('x'), (int, float)) and isinstance(e.get('y'), (int, float)) and math.hypot(e['x'] - w['x'], e['y'] - w['y']) <= 3]
                    e = min(cand, key=lambda e: math.hypot(e['x'] - w['x'], e['y'] - w['y'])) if cand else None
                    chk = (lambda b, w=w: _near(b, w['x'], w['y']))
                else:                                                     # место без координат: по тексту места; у look без мест — запись без x, y
                    e = next((e for e in vs if e.get('x') is None and (not W_ or str(e.get('note') or e.get('место') or '') == str(w.get('note')))), None); chk = None
                why = G.verdict(e, i, chk, need_frame=w.get('x') is not None) if e is not None else 'нет вердикта'
                if why: bad.append(f'{place_key(j, w)}: {why}')
                else: got += 1
            if bad: stops.append(f'{i}: look — вердиктов {got} из {max(len(W_), 1)}; ' + '; '.join(bad[:3]) + (f'; … ещё {len(bad) - 3}' if len(bad) > 3 else ''))
            else: rev.append(dict(id=i, got=got, need=max(len(W_), 1)))
        elif st == 'skip':
            if str(N.get(i, '')).strip(): notes.append(dict(id=i, note=N[i]))
            else: stops.append(f'{i}: skip — нет строки «чем проверено» (--notes)')
    miss, crops, CL = [], [], CL or {}
    for g in (f'К-{j:02d}' for j in range(1, 13)):
        if g in BY_LOOK: continue                                         # места — вердикты look своих Ч (--verdicts)
        v, ob = K.get(g), CL.get(g, []) if g in OBJ_GROUPS else []
        if not ob:                                                        # строкой: статус обязателен, кадр — если дан, этого круга
            e = v if isinstance(v, dict) and ('вердикт' in v or 'verdict' in v or 'статус' in v) else dict(вердикт=v) if isinstance(v, str) else None
            if not e or not _vtext(e) and not e.get('статус'): miss.append(g); continue
            st_, why = vstatus(e)
            if not st_: stops.append(f'{g}: {why}'); continue
            if e.get('кадр'):
                p, why = G.frame(e['кадр'], g)
                if not p: stops.append(f'{g}: {why}'); continue
            crops.append(dict(id=g, got=1, need=1, carried=0)); continue
        if not isinstance(v, dict) or 'вердикт' in v or 'verdict' in v:
            stops.append(f'{g}: нужен вердикт на каждый объект списка кодом ({len(ob)}): ' + ', '.join(o['id'] for o in ob[:5]) + ('…' if len(ob) > 5 else '')); continue
        bad, nc = [], 0
        for o in ob:
            e = v.get(o['id']); why = G.verdict(e, g, lambda b, o=o: b == frame_name(h, g, o['id'])) if e else 'нет вердикта'
            if why: bad.append(f'{o["id"]}: {why}')
            elif isinstance(e, dict) and (e.get('из') or e.get('from')): nc += 1
        if bad:
            tail = ' — вердикты К-12 давать последними, после последней правки SVG (map/rules/80 §3)' if g == 'К-12' else ''
            stops.append(f'{g}: вердиктов {len(ob) - len(bad)} из {len(ob)}; ' + '; '.join(bad[:3]) + (f'; … ещё {len(bad) - 3}' if len(bad) > 3 else '') + tail)
        crops.append(dict(id=g, got=len(ob) - len(bad), need=len(ob), carried=nc))
    if miss: stops.append('протокол просмотра: нет вердикта ' + ', '.join(miss) + ('' if a.crops else ' (--crops)'))
    return dict(ok=not stops, stops=stops, accepted=acc, reviewed=rev, notes=notes, crops=crops, svg_sha256=h, code=cid)

# ------------------------------------------------------------------ отчёт
STATUS = ('pass', 'fail', 'look', 'skip', 'info')
CHECKS = [globals()[f'c{i:02d}'] for i in range(1, 40)]                     # v008: Ч-35…Ч-39
def run(a):
    root, R = load(a.svg); P = model(root, R, a); P.text = open(a.svg, encoding='utf-8', errors='replace').read()
    try: S = shape(P)
    except Exception as e: S = dict(edges=0, short=[], steps=[], izlom=[], col=[], near=[], close=[], zero=0, rect=0, tnode=0); P.notes.append(f'форма не посчитана: {e}')
    res = []
    for i, f in enumerate(CHECKS, 1):
        try: res.append(f(P, a, S))
        except Exception as e: res.append(row(f'Ч-{i:02d}', 'проверка упала — ошибка, не пропуск', f'{type(e).__name__}: {e}', '—', 'fail'))
    for f in EXTRA:                                                       # v13: проверки без номера Ч — после Ч-NN, шлюз их не решает
        try: res.append(f(P, a, S))
        except Exception as e: res.append(dict(row(f.__name__, 'проверка без номера Ч упала — ошибка, не пропуск', f'{type(e).__name__}: {e}', '—', 'fail'), no_gate=True))
    res.sort(key=lambda c: (not c['id'].startswith('Ч-'), c['id'])); n = Counter(c['status'] for c in res if not c.get('no_gate'))
    try: CL = crop_list(P, a)
    except Exception as e: CL = {}; P.notes.append(f'список кропов не построен: {type(e).__name__}: {e}')
    h = sha256f(a.svg); cid = code_id()
    rep = dict(version=11, svg=os.path.abspath(a.svg), svg_sha256=h, code=cid, params=dict(wall_t_px=P.T, outer_wall_px=P.TO, scale_px_per_m=P.scale, scale_source=P.scale_src, glazed_facade=a.glazed_facade,
               source_transform=P.tf, source_kind=a.source_kind, wall_mask=bool(a.wall_mask), wall_mask_recipe=(lambda m: m and {k: m.get(k) for k in ('recipe', 'sha', 'ok', 'why')})((P.SRC.mmeta if P.SRC else None)),
               walls_as_faces=P.faces, mixed_facade=P.mixed, notes=P.notes), summary={k: n.get(k, 0) for k in STATUS}, checks=res,
               crop_list=CL)
    if a.gate: rep['gate'] = gate_eval(res, a, CL, h, cid)
    return rep
def to_md(rep):
    p, s, e = rep['params'], rep['summary'], lambda t: str(t).replace('|', '\\|').replace('\n', ' ')
    L = [f'# Приёмка карты — {os.path.basename(rep["svg"])}', '', f'T = {fx(p["wall_t_px"])} px; масштаб ' + (f'{fx(p["scale_px_per_m"], 2)} px/м ({p["scale_source"]})' if p['scale_px_per_m'] else 'не дан') +
         f'; фасад остеклён — {"да" if p["glazed_facade"] else "не указано"}' + ''.join(f'; {n}' for n in p['notes']), '', '**Итог:** ' + ' · '.join(f'{k} {s[k]}' for k in STATUS if s[k] or k != 'info'), '',
         'pass — пройдено, fail — нарушено, look — посмотреть глазами, skip — нет данных или процедура, info — справочно; координаты — px фрейма.', '',
         '| Проверка | Значение | Порог | Статус | Где |', '|---|---|---|---|---|']
    for c in rep['checks']:
        wh = c.get('reason') or '; '.join((f'{w["x"]:.0f}, {w["y"]:.0f} ' if w['x'] is not None else '') + w['note'] for w in c['where'][:3]) + (f'; … ещё {c["where_total"] - 3}' if c['where_total'] > 3 else '')
        L.append(f'| **{c["id"]}** {e(c["name"])} | {e(c["value"])} | {e(c["threshold"])} | {c["status"]} | {e(wh)} |')
    if 'gate' in rep:
        g = rep['gate']; L += ['', f'## Шлюз сдачи — {"пройден" if g["ok"] else "стоп: сдавать нельзя"}', '']
        cd = g.get('code') or {}
        L += [f'SVG SHA-256 `{g.get("svg_sha256", "")}`; код карты v{cd.get("version") or "?"}' + (f' ({cd.get("made_utc")} UTC)' if cd.get('made_utc') else '') +
              f', `acceptance_checks.py` SHA-256 `{cd.get("acceptance_checks_sha256", "")[:16]}…` — ' + ('канонический' if cd.get('canonical') else 'НЕ канонический'), '']
        L += [f'- **стоп** — {x}' for x in g['stops']]
        if g['accepted']:                                                # всё принятое без исправления — таблицей владельцу (map/rules/80 §0, п. 3; §6, п. 7)
            L += ['', '**Принято без исправления** — в итоговое сообщение владельцу:', '', '| Ч-NN | Мест (принято) | Вид причины | Ссылка | Пояснение | Кто |', '|---|---|---|---|---|---|']
            L += [f'| {x["id"]} | {x["n"]} ({x["max"]}) | {x["kind"]} | {e(x["ref"])} | {e(x["why"])} | {e(x["by"])} |' for x in g['accepted']] + ['']
        L += [f'- разобрано: {x["id"]} — вердиктов {x["got"]} из {x["need"]}' for x in g['reviewed']] + [f'- процедура: {x["id"]} — {x["note"]}' for x in g['notes']]
        L += [f'- кропы {x["id"]}: вердиктов {x["got"]} из {x["need"]}' + (f', перенесено {x["carried"]}' if x.get('carried') else '') for x in g.get('crops', [])]
    if rep.get('crop_list'):
        L += ['', '## Список кропов кодом (map/rules/80 §3)', '', '| К | Объектов | Первые |', '|---|---|---|']
        L += [f'| {k} | {len(v)} | ' + e('; '.join(f'{o["id"]} — {o["what"]}' for o in v[:3])) + (f'; … ещё {len(v) - 3}' if len(v) > 3 else '') + ' |' for k, v in rep['crop_list'].items()]
    return '\n'.join(L) + '\n'
def main():
    ap = argparse.ArgumentParser(description='Приёмка карты UnSpot: Ч-01…Ч-39')
    for k, h in (('svg', 'SVG чистовика, артефакт 2'), ('scale-px-per-m', 'px фрейма на метр'), ('wall-t', 'T, px; иначе по обводке помещений'), ('palette-extra', 'цвета клиента: hex через запятую или файл'),
                 ('colour-map', 'JSON {"by_name": {...}, "by_type": {...}}'), ('ref-points', 'точек стен у эталона'), ('final-png', ''), ('artefact3-png', 'картинка C'), ('places-json', ''),
                 ('source-png', 'исходник-растр'), ('source-transform', 'исходник → фрейм a,b,tx,c,d,ty: X = a·x + b·y + tx, Y = c·x + d·y + ty'), ('source-dark', 'порог тёмного 0–255; иначе Оцу'),
                 ('source-hash', 'imageHash исходника для Ч-01 (sha1, можно начало)'), ('legend-seats', 'мест по легенде листа для Ч-04'), ('meta', 'meta.json: raw_to_frame, масштаб'), ('json', ''), ('md', '')):
        ap.add_argument('--' + k, help=h, required=k == 'svg', type={'scale-px-per-m': float, 'wall-t': float, 'ref-points': int, 'source-dark': int, 'legend-seats': int}.get(k, str))
    ap.add_argument('--glazed-facade', action='store_true', help='фасад остеклён целиком: стекло ≥ 95 %% контура')
    ap.add_argument('--prev-size', help='v012 (Ч-28, #86 П-4, строка 298): правка карты — Ш×В прежней выгрузки «W,H»: PNG — того же размера до пикселя')
    ap.add_argument('--outer-wall-px', type=float, help='толщина наружной стены (фасада), px фрейма; по умолчанию 2T. Ставить только при переносе карты '
                    'с решением владельца «геометрия как есть»: толщина как у источника (Ч-19, Ч-21, Ч-27 и тело стены — по ней)')
    ap.add_argument('--source-kind', choices=('raster', 'vector'), default='raster', help='класс исходника из intake.md: вектор — Ч-10 и Ч-11 по маске тела стены')
    ap.add_argument('--wall-mask', help='PNG того же размера, что --source-png: белое — тело стены исходника (вектор)')
    ap.add_argument('--colored-walls', action='store_true', help='v13 (строка 387): признак исходника «цветные стены» — стены нарисованы цветом, а не нейтральной тушью '
                    '(ставит исполнитель по приёму исходника; порога признака в каноне нет): без --wall-mask Ч-10 и Ч-11 — look и число непокрытой цветной туши')
    ap.add_argument('--sheet-tables', help='v13 (строка 413): столы листа — {"frame": "source"|"plan", "tables": [{"poly": [[x, y], …]}]} или places.json кода мест '
                    '(ключ furniture_desks, кадр карты) — для проверки «стол переговорной против стола листа»')
    ap.add_argument('--gate', action='store_true', help='шлюз сдачи: код выхода 1, пока не закрыты fail, look, skip и кропы; итог — ещё и в gate.json')
    for k, h in (('accept', 'реестр принятого: {"svg_sha256": "…", "Ч-NN": {"max": мест, "why": {"kind": "false_fail|owner|question|source", "ref": "…", "text": "…"}, "by": "чат"}}'),
                 ('verdicts', 'вердикты look: {"svg_sha256": "…", "Ч-NN": [{x, y, "статус", "вердикт", "кадр"}] | файл}'),
                 ('notes', 'skip: {"Ч-NN": "чем проверено"}'),
                 ('crops', 'протокол просмотра: {"svg_sha256": "…", "К-01": {"<id объекта>": {"статус", "вердикт", "кадр"[, "из"]}}, "К-03": {"статус", "вердикт"}, …}'),
                 ('frames', 'папка кадров review/gate_frames.py: имена кадров — с хешем этого SVG'),
                 ('gate-json', 'итог шлюза с версией кода и хешами входов; по умолчанию gate.json рядом с --json'),
                 ('chairs-json', 'стулья листа для Ч-31: {"frame": "source"|"plan", "chairs": [[x, y], …]} — unspot_map.chairs'),
                 ('sheet-signs', 'знаки листа для Ч-33: [{"kind": "wc"|"lift"|"stair"|"tech", "x", "y", "frame": "source"|"plan", "note"}]'),
                 ('sheet-doors', 'двери листа для Ч-36: {"frame": "source"|"plan", "doors": [{"hinge": [x, y], "a": [x, y], "b": [x, y] | null, "kind": "arc"|"leaf"}]} — unspot_map.sheet doors'),
                 ('sheet-glass', 'стекло листа для Ч-38: {"frame": "source"|"plan", "segments": [[[x, y], [x, y]], …]} — unspot_map.sheet glass'),
                 ('sheet-numbers', 'номера мест листа для Ч-37: {"frame": "source"|"plan", "numbers": [{"n": "12", "x", "y"}]} — unspot_map.sheet numbers'),
                 ('crop-list-out', 'список кропов кодом — в JSON'), ('crops-template', 'заготовка --crops: объекты списка с пустыми вердиктами'),
                 ('round-dir', 'папка круга: файлы шагов (intake.md, chairs.json, places.json) — шлюз сверяет, что они на месте; по умолчанию — папка SVG')):
        ap.add_argument('--' + k, help=h)
    a = ap.parse_args(); rep = run(a); md = to_md(rep)
    if a.crop_list_out: json.dump(rep.get('crop_list', {}), open(a.crop_list_out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    if a.crops_template:                                                  # v007: статус и кадр на каждый объект; кадры строит review/gate_frames.py
        h = rep['svg_sha256']; ob = lambda g, o: dict(статус='', вердикт='', кадр=frame_name(h, g, o['id']))
        tp = {'svg_sha256': h, **{g: ({o['id']: ob(g, o) for o in rep['crop_list'][g]} if g in OBJ_GROUPS and rep.get('crop_list', {}).get(g) else dict(статус='', вердикт=''))
                                   for g in (f'К-{j:02d}' for j in range(1, 13)) if g not in BY_LOOK}}
        json.dump(tp, open(a.crops_template, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    if a.json: json.dump(rep, open(a.json, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    if a.gate:                                                            # gate.json: итог, версия кода, SHA-256 приёмки и всех входов (Ф1, п. 4; Р4)
        gj = a.gate_json or os.path.join(os.path.dirname(os.path.abspath(a.json)) if a.json else '.', 'gate.json')
        ins = {k: dict(path=os.path.abspath(f), sha256=sha256f(f)) for k, f in (('svg', a.svg), ('final_png', a.final_png), ('artefact3_png', a.artefact3_png),
               ('places_json', a.places_json), ('source_png', a.source_png), ('chairs_json', a.chairs_json), ('wall_mask', a.wall_mask), ('sheet_doors', a.sheet_doors),
               ('sheet_glass', a.sheet_glass), ('sheet_numbers', a.sheet_numbers), ('sheet_signs', a.sheet_signs), ('accept', a.accept),
               ('verdicts', a.verdicts), ('notes', a.notes), ('crops', a.crops)) if f and os.path.exists(f)}
        json.dump(dict(rep['gate'], made_utc=__import__('datetime').datetime.now(__import__('datetime').timezone.utc).strftime('%Y-%m-%d %H:%M'), inputs=ins,
                       wall_mask=rep['params'].get('wall_mask_recipe'), step_files={f'{st} {fn}': p_ for st, w_, fn, p_ in step_files(a)},
                       summary=rep['summary']), open(gj, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    if a.md: open(a.md, 'w', encoding='utf-8').write(md)
    print(md); sys.exit((0 if rep['gate']['ok'] else 1) if a.gate else (1 if rep['summary']['fail'] else 0))

if __name__ == '__main__': main()
