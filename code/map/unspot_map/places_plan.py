"""Места артефакта 3 по объектам инженерного плана (v012, КМ-21; ОЧ-59; proposals/map/2026-10-08-клиент Б-40-карта-v03-мост-и-кандидаты П3-7
с дополнением круга 2; В2К-7; ПК5-К4; №90, строки 196, 216).

Если у этажа есть инженерный план (DXF 012/013), места строятся по его объектам, а не по рендеру листа:
 * стол — объект плана `desk` (модуль листа); стол любого другого типа (`mtable`, `dtable`, `table`, `rtable`, `ctable` — переговорный, руководителя,
   журнальный), внутри которого стоит номер клиента, — тоже стол места (клиент Б: номер «1» — на столе руководителя 1,8 × 0,9 м, `desk` рядом —
   приставной); стол плана без номера — мебель (список `furniture_desks`), не место;
 * номер — текст формата номера места (настройка `--number-re`; по умолчанию 1–3 цифры с суффиксом «-N», как `sheet.numbers`); из текстов этого
   формата берутся стили (слой, высота, цвет), которые чаще всего стоят на столах плана (≥ 50 % в 0,3 м от стола): размеры и марки помещений
   того же формата — не номера; текст «127 128 129 130» — четыре номера по ходу строки;
 * номер -> стол — один к одному по этажу (венгерский метод; цена — расстояние до стола, номер внутри — 0, плюс 0,3 расстояния до центра стола:
   ряд с номерами, сдвинутыми на полстола, получает свои модули — ОВ1, Н11);
 * стул — объект плана `chair`; стол -> стул — один к одному от центра своего стола (венгерский метод), стул не на столе, не за чужим столом
   (ОВ21), в 1,2 м; нет стула — точка места на середине длинной стороны у номера (map/rules/82 §0);
 * номеров нет (лист без номеров, клиент А 4 Revit) — место = модуль стола со стулом: бенч делится на модули этажа (медианная длина одиночных столов,
   строка 216: мест в ряду — столько, сколько столов листа), модуль без стула — не место (map/rules/82 §0), громко;
 * тумба `pedestal` (№90, строка 196) — не часть стола: у торца стола — ключом `pedestal` записи места, остальные — `pedestals`;
 * стол в стене карты (`--svg` — карта по мосту): ключ `--desk-in-wall shift|cut`. `shift` (по умолчанию — канон map/rules/61 §3.2, решение
   главного чата 13.10.2026 до ответа владельца на ОЧ-26): стол сдвигается внутрь до внутреннего края стены, размер не меняется — по короткой
   стороне (ОВ20 б), торец в стене — по длинной, не дальше 0,5 м (shift_off); `cut` (П3-7):
   часть стола в теле стены срезается — модуль листа не двигается (Ч-37), сдвиг — только если срезано больше 30 %; касание соседних модулей —
   не накладка: стол на 0,4 px внутрь;
 * без XDATA `UNSPOT type` (DXF 010) — класс по слою A-82 и имени блока (desk|стол / chair|стул|кресл / pedestal|тумб), громко.

Кадр — `M_t.npy` моста (мм -> px карты), свой кадр модуль не выводит. Выход — places.json схемы v011 ({frame, size, px_per_m, source, places:
[{seat, number, by, desk, centre, x, y, size_m, room, gaze_deg, …}]}) с необязательными `src: "plan"`, `desk_type`, `plan_desk`, `pedestal`; chairs.json —
{"frame": "plan", "px_per_m", "how", "chairs": [[x, y], …]} в px карты (вход Ч-31). Артефакт 3 — `--plan-png` (картинка чистовика) через
workplaces.render_draft — черновик 25 / 50 / 100 (v013, map/rules/83 §6; `--underlay` — оригинал в кадре холста, контур плана — по `--svg`).

    python3 -m unspot_map.places_plan plan.dxf --frame M_t.npy --px-per-m 56.72356 --svg plan.svg --out places.json --chairs-out chairs.json
        [--desk-in-wall shift|cut] [--number-re RE] [--plan-png plan.png --a3-out plan_c.png [--underlay canvas.png]]
Тихих отказов нет: объектов плана нет, номеров нет, формат номера не распознан, стол без номера, номер вне стола — строкой в выводе и в `log`."""
import argparse, json, math, re, sys
from collections import Counter, defaultdict
import numpy as np
from scipy.optimize import linear_sum_assignment
from shapely.geometry import Polygon, Point, LineString, MultiPoint
from shapely.ops import unary_union
from shapely.strtree import STRtree

DESK_TYPES = ('desk',)
TABLE_TYPES = ('mtable', 'dtable', 'table', 'rtable', 'ctable')     # стол любого типа с номером внутри — стол места (П3-7, круг 2)
CHAIR_TYPES = ('chair',)
PED_TYPES = ('pedestal',)
NUMBER_RE = r'\d{1,3}(?:-\d{1,2})?'                                   # как sheet.numbers; формат клиента — ключом (ОЧ-Б3)
NEAR_DESK_M = 0.3              # номер «на столе»: в 0,3 м от стола — для выбора стиля номеров
STYLE_SHARE = 0.5              # стиль текста — номера мест, если ≥ 50 % его текстов стоят на столах
UNIQUE_SHARE = 0.8             #   и ≥ 80 % его значений разные (размер «90» на каждом столе — не номер)
CHAIR_REACH_M = 1.2            # стул места — в 1,2 м от центра своего стола (map/rules/82 §0)
CUT_MAX = 0.30                 # cut: срезано больше 30 % — сдвиг (П3-7)
TOUCH_PX = 0.4                 # касание соседних модулей — не накладка: стол на 0,4 px внутрь (П3-7)
PED_GAP_M = 0.15               # тумба у торца стола — не дальше 0,15 м
MODULE_RANGE_M = (0.95, 1.9)   # одиночный стол по длине (КМ-20: 0,95–1,9 м) — для модуля этажа
CHAR_W = 0.6                   # ширина знака TEXT — 0,6 высоты (оценка: позиция номера внутри строки «127 128 129 130»)


# ---------- DXF ----------
def _xd(e):
    d = {}
    if e.has_xdata('UNSPOT'):
        for _, v in e.get_xdata('UNSPOT'):
            if isinstance(v, str) and '=' in v:
                k, _, val = v.partition('='); d[k] = val
    return d


def _pts_of(e):
    """точки примитива (мир, мм) для оболочки; LWPOLYLINE, CIRCLE, ARC, HATCH — в OCS: блок с отражением (масштаб −1) даёт выдавливание
    (0, 0, −1) — переводить в мир (клиент А 4: стулья Revit с yscale −1 без перевода уходят на −x)"""
    t = e.dxftype()
    try:
        if t == 'LWPOLYLINE':
            return [tuple(v)[:2] for v in e.vertices_in_wcs()]
        if t == 'LINE':
            return [tuple(e.dxf.start)[:2], tuple(e.dxf.end)[:2]]
        if t in ('CIRCLE', 'ARC'):
            c, r = e.dxf.center, e.dxf.radius; ocs = e.ocs()
            return [tuple(ocs.to_wcs((c.x + r * math.cos(a), c.y + r * math.sin(a), c.z)))[:2] for a in np.linspace(0, 2 * math.pi, 24, endpoint=False)]
        if t == 'POLYLINE':
            return [tuple(v.dxf.location)[:2] for v in e.vertices]
        if t == 'HATCH':
            out = []; ocs = e.ocs(); el = e.dxf.elevation.z if e.dxf.hasattr('elevation') else 0.0
            for p in e.paths:
                if hasattr(p, 'vertices'):
                    out += [tuple(v)[:2] for v in p.vertices]
                else:
                    for ed in getattr(p, 'edges', []):
                        if hasattr(ed, 'radius') and hasattr(ed, 'center'):      # дуга контура штриховки (круглый стол)
                            out += [(ed.center[0] + ed.radius * math.cos(a_), ed.center[1] + ed.radius * math.sin(a_)) for a_ in np.linspace(0, 2 * math.pi, 24, endpoint=False)]
                        if hasattr(ed, 'start'): out.append(tuple(ed.start)[:2])
                        if hasattr(ed, 'end'): out.append(tuple(ed.end)[:2])
            return [tuple(ocs.to_wcs((x, y, el)))[:2] for x, y in out]
        if t == 'SOLID':
            return [tuple(e.dxf.get(k))[:2] for k in ('vtx0', 'vtx1', 'vtx2', 'vtx3') if e.dxf.hasattr(k)]
    except Exception:                                                  # noqa: BLE001
        return []
    return []


def outline(ins):
    """INSERT -> контур в мм: прямоугольник наименьшей площади вокруг примитивов блока (стол, тумба) или оболочка"""
    pts = []
    for v in ins.virtual_entities():
        if v.dxftype() == 'INSERT':
            pts += [p for q in v.virtual_entities() for p in _pts_of(q)]
        else:
            pts += _pts_of(v)
    if len(pts) < 3:
        return None
    mp = MultiPoint(pts)
    R = mp.minimum_rotated_rectangle
    return R if R.geom_type == 'Polygon' and R.area > 0 else None


BLOCK_GUESS = ((r'desk|стол_?раб|рабоч|бенч|bench', 'desk'), (r'chair|стул|кресл', 'chair'), (r'pedestal|тумб', 'pedestal'),
               (r'стол|table', 'table'))


def read_objects(dxf_path, log=print):
    """DXF плана -> {type: [dict(handle, poly_mm, block)]}; класс — XDATA UNSPOT type, без неё — слой A-82 и имя блока (громко)"""
    import ezdxf
    doc = ezdxf.readfile(dxf_path); msp = doc.modelspace()
    objs, guessed = defaultdict(list), Counter()
    for e in msp.query('INSERT'):
        t = _xd(e).get('type')
        if t is None:
            if not e.dxf.layer.upper().startswith('A-82'):
                continue
            nm = e.dxf.name.lower(); t = next((k for rx, k in BLOCK_GUESS if re.search(rx, nm)), None)
            if t is None:
                continue
            guessed[t] += 1
        if t not in DESK_TYPES + TABLE_TYPES + CHAIR_TYPES + PED_TYPES:
            continue
        P = outline(e)
        if P is None:
            log('места: объект %s %s без контура — пропущен' % (t, e.dxf.handle)); continue
        objs[t].append(dict(handle=e.dxf.handle, poly=P, block=e.dxf.name, layer=e.dxf.layer))
    if guessed:
        log('места: ВНИМАНИЕ — у %d объектов нет XDATA UNSPOT type: класс по слою A-82 и имени блока (%s) — сверить глазами'
            % (sum(guessed.values()), ', '.join('%s %d' % kv for kv in guessed.items())))
    texts = []
    for e in msp.query('TEXT MTEXT'):
        if e.dxftype() == 'TEXT':
            s = e.dxf.text; h = float(e.dxf.height); rot = math.radians(e.dxf.rotation); wf = float(e.dxf.get('width', 1.0) or 1.0)
            hal, val = e.dxf.get('halign', 0), e.dxf.get('valign', 0)
            ins = np.array(tuple(e.dxf.insert)[:2]); al = np.array(tuple(e.dxf.align_point)[:2]) if e.dxf.hasattr('align_point') else ins
        else:
            s = e.plain_text(); h = float(e.dxf.char_height); rot = math.radians(e.dxf.get('rotation', 0.0)); wf = 1.0
            ap = e.dxf.get('attachment_point', 1); hal = {1: 0, 2: 1, 3: 2}[(ap - 1) % 3 + 1]; val = {0: 3, 1: 2, 2: 1}[(ap - 1) // 3]
            ins = np.array(tuple(e.dxf.insert)[:2]); al = ins
        col = e.dxf.get('true_color') if e.dxf.hasattr('true_color') else e.dxf.get('color', 256)
        texts.append(dict(text=s, h=h, rot=rot, wf=wf, hal=hal, val=val, ins=ins, al=al, layer=e.dxf.layer, style=(e.dxf.layer, round(h), col)))
    return objs, texts


def tokens(t, number_re=NUMBER_RE):
    """текст -> [(номер, точка в мм)]: строка «127 128 129 130» — по ходу строки, знак — CHAR_W высоты"""
    s = t['text']; rx = re.compile(r'^(?:%s)$' % number_re); parts = [(m.group(0), m.start()) for m in re.finditer(r'\S+', s)]
    if not parts or not all(rx.match(p) for p, _ in parts):
        return []
    cw = CHAR_W * t['h'] * t['wf']; L = len(s.rstrip()) * cw
    u = np.array([math.cos(t['rot']), math.sin(t['rot'])]); up = np.array([-u[1], u[0]])
    if t['hal'] in (3, 5):                                            # aligned / fit — между insert и align_point
        start = t['ins']; L = max(np.linalg.norm(t['al'] - t['ins']), 1e-6); cw = L / max(len(s.rstrip()), 1)
    elif t['hal'] in (1, 4):
        start = t['al'] - u * L / 2
    elif t['hal'] == 2:
        start = t['al'] - u * L
    else:
        start = t['ins']
    dv = {0: 0.5, 1: 0.5, 2: 0.0, 3: -0.5}.get(t['val'], 0.5) * t['h']      # до середины высоты знаков
    if t['hal'] == 4:
        dv = 0.0
    return [(p, start + u * (i0 + len(p) / 2) * cw + up * dv) for p, i0 in parts]


# ---------- карта ----------
def map_walls(svg_path, T_default=6.0):
    """карта (SVG): линии стен — пути с обводкой rooms/wall/glass/window, их ширина; колонны — заливки data-type=column; помещения — грани с id"""
    from svgpathtools import parse_path
    s = open(svg_path, encoding='utf-8').read()
    lines, cols, rooms = [], [], []
    for m in re.finditer(r'<path\b([^>]*)/?>', s):
        a = m.group(1); g = lambda k: (re.search(r'\b%s="([^"]*)"' % k, a) or [None, None])[1]
        pid, d, st, sw = g('id') or '', g('d'), g('stroke'), g('stroke-width')
        if not d:
            continue
        is_col = g('data-type') == 'column'; is_room = pid.startswith('room-')
        is_wall = bool(st and st != 'none' and re.match(r'(room|wall|glasswall|window|facade)', pid))
        if not (is_col or is_room or is_wall):
            continue                                                   # мебель, проёмы, значки — не нужны
        rings = []
        for sp in parse_path(d).continuous_subpaths():
            P = []
            for seg in sp:
                n = 1 if seg.__class__.__name__ == 'Line' else max(4, int(seg.length() / 3))
                P += [(seg.point(t_).real, seg.point(t_).imag) for t_ in np.linspace(0, 1, n + 1)[:-1]]
            P.append((sp.end.real, sp.end.imag)); rings.append((P, sp.isclosed()))
        if g('data-type') == 'column':
            cols += [Polygon(P).buffer(0) for P, _ in rings if len(P) >= 3]; continue
        if pid.startswith('room-') and len(rings[0][0]) >= 3:
            rooms.append(dict(id=pid, name=g('data-name') or '', type=g('data-type') or '', poly=Polygon(rings[0][0]).buffer(0)))
        if st and st != 'none' and re.match(r'(room|wall|glasswall|window|facade)', pid):
            w = float(sw or T_default)
            for P, closed in rings:
                if len(P) >= 2:
                    lines.append((LineString(P + ([P[0]] if closed else [])), w))
    return lines, cols, rooms


# ---------- места ----------
def to_px(M, t):
    return lambda P: np.asarray(P, float) @ M.T + t


def poly_px(P, F):
    return Polygon(F(np.asarray(P.exterior.coords)))


def choose_numbers(texts, desks_px, F, px_per_m, number_re, log=print):
    """тексты формата номера -> номера мест: стили, чьи тексты стоят на столах (≥ STYLE_SHARE в NEAR_DESK_M) -> [dict(n, x, y, style)]"""
    by = defaultdict(list)
    for t in texts:
        for n, p in tokens(t, number_re):
            by[t['style']].append(dict(n=n, xy=F([p])[0], style=t['style']))
    if not by:
        log('места: ВНИМАНИЕ — текстов формата номера (%s) в DXF нет — номеров нет' % number_re); return []
    if not desks_px:
        return []
    U = unary_union(desks_px).buffer(NEAR_DESK_M * px_per_m); keep = []
    for st, L in sorted(by.items(), key=lambda kv: -len(kv[1])):
        sh = sum(U.contains(Point(q['xy'])) for q in L) / len(L); un = len({q['n'] for q in L}) / len(L)
        ok = sh >= STYLE_SHARE and un >= UNIQUE_SHARE                # номера мест — разные: «90», «140» на столах — размеры
        log('места: тексты формата номера, стиль %s — %d, на столах %.0f %%, разных %.0f %%%s' % (st, len(L), 100 * sh, 100 * un, ' — номера мест' if ok else ' — не номера'))
        if ok:
            keep += L
    if not keep:
        log('места: ВНИМАНИЕ — формат номера не распознан: ни один стиль текстов не стоит на столах (≥ %d %%) — номеров нет' % int(100 * STYLE_SHARE))
    dup = [n for n, c in Counter(q['n'] for q in keep).items() if c > 1]
    if dup:
        log('места: ВНИМАНИЕ — номера повторяются: %s' % ', '.join(sorted(dup)[:20]))
    return [dict(n=q['n'], x=float(q['xy'][0]), y=float(q['xy'][1])) for q in keep]


def _long_axis(D):
    c = np.asarray(D.minimum_rotated_rectangle.exterior.coords)[:4]
    e = [c[(i + 1) % 4] - c[i] for i in range(4)]; k = int(np.argmax([np.linalg.norm(x) for x in e]))
    return c, e[k] / np.linalg.norm(e[k]), np.linalg.norm(e[k]), np.linalg.norm(e[(k + 1) % 4])


def split_modules(D, Lm_px):
    """бенч -> модули этажа (строка 216): n = round(L / Lm), n ≥ 2 только при L ≥ 1,5 Lm; модули равные"""
    c, u, L, S = _long_axis(D); n = max(1, int(round(L / Lm_px))) if L >= 1.5 * Lm_px else 1
    if n == 1:
        return [D]
    ctr = np.asarray(D.minimum_rotated_rectangle.centroid.coords[0]); v = np.array([-u[1], u[0]]); out = []
    for i in range(n):
        m = ctr + u * (-L / 2 + L * (i + 0.5) / n); hl, hs = L / n / 2, S / 2
        out.append(Polygon([tuple(m + u * hl + v * hs), tuple(m - u * hl + v * hs), tuple(m - u * hl - v * hs), tuple(m + u * hl - v * hs)]))
    return out


def assign_chairs(desks, chairs, px_per_m, reach_m=CHAIR_REACH_M):
    """стол -> стул один к одному от центра стола (венгерский); стул не на столе и не за чужим столом -> {i стола: j стула}"""
    if not desks or not chairs:
        return {}
    allD = unary_union(desks); cand = [j for j, c in enumerate(chairs) if not allD.contains(Point(c))]
    tr = STRtree(desks); BIG = 1e9; C = np.full((len(desks), len(cand)), BIG); reach = reach_m * px_per_m
    for i, D in enumerate(desks):
        q = D.centroid
        for jj, j in enumerate(cand):
            c = Point(chairs[j]); d = q.distance(c)
            if d > reach:
                continue
            seg = LineString([(q.x, q.y), (c.x, c.y)])
            if any(int(k) != i and seg.intersection(desks[int(k)]).length > 2 for k in tr.query(seg)):
                continue
            C[i, jj] = d + 0.5 * D.distance(c)
    r, c = linear_sum_assignment(C)
    return {int(i): cand[int(j)] for i, j in zip(r, c) if C[i, j] < BIG}


def side_seat(D, near, px_per_m):
    """точка места без стула — середина длинной стороны стола, ближайшей к номеру (или к центру), на 0,25 м наружу"""
    c, u, L, S = _long_axis(D); ctr = np.asarray(D.centroid.coords[0]); v = np.array([-u[1], u[0]])
    cand = [ctr + v * S / 2, ctr - v * S / 2]; m = min(cand, key=lambda p: np.hypot(*(p - np.asarray(near))))
    o = (m - ctr) / max(np.linalg.norm(m - ctr), 1e-9)
    return tuple(m + o * 0.25 * px_per_m)


SHIFT_MAX_M = 0.5              # shift: стол сдвигается внутрь до внутреннего края стены — не дальше 0,5 м
SHIFT_STEP_PX = 0.25


def shift_off(D, band, px_per_m, max_m=SHIFT_MAX_M, step=SHIFT_STEP_PX, others=None):
    """канон map/rules/61 §3.2: стол выходит из тела стены сдвигом внутрь помещения, размер не меняется. Сначала по короткой стороне (ОВ20 б,
    v008: ряд не съезжает), если так не выйти — по длинной (торец стола в стене); наименьший сдвиг, тело стены — меньше 0,5 px²; на соседний
    стол (others) не наезжает — иначе стол остаётся, громко.
    -> (новый стол, сдвиг px) или None"""
    from shapely import affinity
    c, u, L, S = _long_axis(D); v = np.array([-u[1], u[0]]); best = None
    for axis_rank, ax in ((0, v), (1, u)):
        for sg in (1, -1):
            dvec = ax * sg
            for k in range(1, int(max_m * px_per_m / step) + 1):
                d = k * step
                if best is not None and (axis_rank, d) >= best[0]:
                    break
                Dm = affinity.translate(D, *(dvec * d))
                if Dm.intersection(band).area < 0.5:
                    if others is None or others.is_empty or Dm.intersection(others).area < 0.5:
                        best = ((axis_rank, d), Dm, d)
                    break
        if best is not None:
            return best[1], best[2]
    return None


def desk_in_wall(places, lines, cols, mode, px_per_m, log=print, no_overlap=False):
    """стол в стене карты: shift — канон map/rules/61 §3.2 (shift_off: по короткой стороне, иначе по длинной); cut — срезать, сдвиг, если срезано
    > 30 % (П3-7)"""
    if not lines and not cols:
        return 0, 0
    band = unary_union([L.buffer(w / 2, cap_style=2, join_style=2) for L, w in lines] + cols).buffer(0)
    ncut = nshift = 0
    tr = STRtree([q['desk'] for q in places])
    for i, q in enumerate(places):
        D = q['desk']; X = D.intersection(band)
        if X.area < 0.5:
            continue
        if mode == 'cut':                                      # П3-7: модуль листа не двигается — часть в стене срезается
            C = D.difference(band)
            if C.geom_type != 'Polygon':
                C = max(getattr(C, 'geoms', [C]), key=lambda g: g.area)
            if not C.is_empty and C.area >= (1 - CUT_MAX) * D.area:
                q['desk'] = C.simplify(0.2); q['clipped_px2'] = round(X.area, 1); ncut += 1; continue
        near = q['desk'].buffer(SHIFT_MAX_M * px_per_m + 2)
        # канон (82 §0): стол сдвигается, пересекающиеся столы режутся (resolve); others — только ключом стенда (без наезда на соседа)
        others = unary_union([places[int(j)]['desk'] for j in tr.query(near) if int(j) != i]) if no_overlap else None
        moved = shift_off(q['desk'], band.intersection(near), px_per_m, others=others)
        if moved is not None:
            q['desk'], q['moved'] = moved; nshift += 1
        else:
            log('места: стол %s — в стене, сдвиг до 0,5 м не освобождает%s — оставлен, кадр' % (q['n'], ' (без наезда на соседний стол)' if no_overlap else ''))
    log('места: стол в стене — режим %s: срезано %d, сдвинуто %d' % (mode, ncut, nshift))
    return ncut, nshift


def resolve(places, log=print):
    """накладки столов: часть отходит столу, чей номер дальше от неё; касание — не накладка (0,4 px внутрь)"""
    tr = STRtree([q['desk'] for q in places])
    for i, q in enumerate(places):
        for j in tr.query(q['desk']):
            j = int(j)
            if j <= i:
                continue
            Di, Dj = places[i]['desk'], places[j]['desk']; X = Di.intersection(Dj)
            if X.area <= 0.5:
                continue
            lose = j if X.distance(Point(places[j]['anchor'])) > X.distance(Point(places[i]['anchor'])) else i
            keep = i if lose == j else j
            C = places[lose]['desk'].difference(places[keep]['desk'])
            if C.geom_type != 'Polygon':
                C = max(getattr(C, 'geoms', [C]), key=lambda g: g.area)
            places[lose]['desk'] = C.simplify(0.2); places[lose]['overlap_cut_px2'] = round(X.area, 1)
            log('места: столы %s × %s — накладка %.0f px² отошла %s' % (places[i]['n'], places[j]['n'], X.area, places[lose]['n']))
    for q in places:
        if not q['desk'].is_empty:
            q['size_px'] = _long_axis(q['desk'])[2:]                 # размер стола — до отступа касания 0,4 px
            B = q['desk'].buffer(-TOUCH_PX, join_style=2)
            q['desk'] = B if B.geom_type == 'Polygon' else max(getattr(B, 'geoms', [q['desk']]), key=lambda g: g.area)


def build(dxf_path, M, t, px_per_m, svg=None, desk_in_wall_mode='shift', number_re=NUMBER_RE, log=print):
    """-> (places: [dict], chairs_px, furniture_desks, pedestals, info)"""
    F = to_px(M, t)
    objs, texts = read_objects(dxf_path, log)
    nd = sum(len(objs[k]) for k in DESK_TYPES)
    if not nd and not any(objs[k] for k in TABLE_TYPES):
        log('места: ВНИМАНИЕ — объектов плана (desk) в %s нет — места по плану не построить' % dxf_path)
        return [], [], [], [], dict(mode='нет объектов плана', desks=0)
    desks = [dict(o, type=k, px=poly_px(o['poly'], F)) for k in DESK_TYPES for o in objs[k]]
    tables = [dict(o, type=k, px=poly_px(o['poly'], F)) for k in TABLE_TYPES for o in objs[k]]
    chairs = [tuple(F([np.asarray(o['poly'].centroid.coords[0])])[0]) for k in CHAIR_TYPES for o in objs[k]]
    peds = [poly_px(o['poly'], F) for k in PED_TYPES for o in objs[k]]
    nums = choose_numbers(texts, [d['px'] for d in desks + tables], F, px_per_m, number_re, log)
    places, info = [], dict(desks=len(desks), tables=len(tables), chairs=len(chairs), pedestals=len(peds), numbers=len(nums))
    if nums:
        info['mode'] = 'номера'
        cand = desks + [x for x in tables if any(x['px'].contains(Point(q['x'], q['y'])) for q in nums)]
        for x in cand[len(desks):]:
            _, _, L_, S_ = _long_axis(x['px'])
            log('места: стол места по номеру — объект плана %s «%s» %.2f × %.2f м' % (x['handle'], x['type'], L_ / px_per_m, S_ / px_per_m))
        Cn = np.array([[d['px'].distance(Point(q['x'], q['y'])) + 0.3 * d['px'].centroid.distance(Point(q['x'], q['y'])) for d in cand] for q in nums])
        r, c = linear_sum_assignment(Cn); own = {int(a): int(b) for a, b in zip(r, c)}
        if len(nums) > len(cand):
            log('места: ВНИМАНИЕ — номеров %d больше столов %d: %d номеров без стола' % (len(nums), len(cand), len(nums) - len(cand)))
        far = 0
        for i, q in enumerate(nums):
            if i not in own:
                log('места: номер %s — стола не хватило' % q['n']); continue
            d = cand[own[i]]; dist = d['px'].distance(Point(q['x'], q['y'])) / px_per_m
            if dist > 0.05:
                far += 1; log('места: номер %s вне своего стола — стол плана %s, %.2f м до контура' % (q['n'], d['handle'], dist))
            places.append(dict(n=q['n'], desk=d['px'], plan=d, anchor=(q['x'], q['y'])))
        used = set(own.values()); spare = [cand[k] for k in range(len(cand)) if k not in used]
        info['numbers_off_desk'] = far
    else:
        info['mode'] = 'столы без номеров'
        log('места: ВНИМАНИЕ — номеров мест нет: место = модуль стола плана со стулом; бенч — по модулю этажа (строка 216); сверка глазами')
        single = [_long_axis(d['px'])[2] for d in desks if MODULE_RANGE_M[0] * px_per_m <= _long_axis(d['px'])[2] <= MODULE_RANGE_M[1] * px_per_m]
        Lm = float(np.median(single)) if single else 1.4 * px_per_m
        info['module_m'] = round(Lm / px_per_m, 3)
        mods = []
        for d in desks:
            for k, m in enumerate(split_modules(d['px'], Lm)):
                mods.append(dict(px=m, plan=d, k=k))
        A = assign_chairs([m['px'] for m in mods], chairs, px_per_m)
        nofree = 0
        for i, m in enumerate(mods):
            if i not in A:
                nofree += 1; continue
            places.append(dict(n=None, desk=m['px'], plan=m['plan'], anchor=tuple(np.asarray(m['px'].centroid.coords[0])), chair=A[i]))
        info['modules'] = len(mods); info['modules_without_chair'] = nofree
        log('места: модулей столов %d (модуль %.2f м), со стулом %d, без стула %d — не места' % (len(mods), Lm / px_per_m, len(places), nofree))
        order = sorted(range(len(places)), key=lambda i: (round(places[i]['anchor'][1] / (2 * px_per_m)), places[i]['anchor'][0]))
        for k, i in enumerate(order):
            places[i]['n'] = 'P%03d' % (k + 1)
        spare = []
    if nums:                                                   # стулья — от центра своего стола (модуль листа, до сдвига и среза)
        A = assign_chairs([q['desk'] for q in places], chairs, px_per_m)
        for i, q in enumerate(places):
            if i in A:
                q['chair'] = A[i]
    lines, cols, rooms = map_walls(svg) if svg else ([], [], [])
    if svg:
        desk_in_wall(places, lines, cols, desk_in_wall_mode, px_per_m, log)
    else:
        log('места: карты (--svg) нет — стол в стене не проверен')
    resolve(places, log)
    # тумбы у торца стола
    pedq = list(range(len(peds)))
    for q in places:
        for k in list(pedq):
            if q['desk'].distance(peds[k]) <= PED_GAP_M * px_per_m:
                q['pedestal'] = peds[k]; pedq.remove(k); break
    out = []
    for q in places:
        D = q['desk']; c = D.centroid
        if q.get('chair') is not None:
            seat, how = chairs[q['chair']], 'стул'
        else:
            seat, how = side_seat(D, q['anchor'], px_per_m), 'сторона стола'
        L, S = q.get('size_px') or _long_axis(D)[2:]
        rm = [r for r in rooms if r['poly'].contains(c)]; rm = min(rm, key=lambda r: r['poly'].area) if rm else None
        rec = dict(seat=q['n'], number=q['n'], by=how, desk=[[round(x, 1), round(y, 1)] for x, y in list(D.exterior.coords)[:-1]],
                   centre=[round(c.x, 1), round(c.y, 1)], x=round(float(seat[0]), 1), y=round(float(seat[1]), 1),
                   size_m=[round(L / px_per_m, 2), round(S / px_per_m, 2)], room=(rm['name'] or rm['id']) if rm else None,
                   src='plan', desk_type=q['plan']['type'], plan_desk=q['plan']['handle'])
        if q.get('pedestal') is not None:
            rec['pedestal'] = [[round(x, 1), round(y, 1)] for x, y in list(q['pedestal'].exterior.coords)[:-1]]
        for k in ('clipped_px2', 'overlap_cut_px2'):
            if q.get(k):
                rec[k] = q[k]
        if q.get('moved'):
            rec['moved_m'] = round(q['moved'] / px_per_m, 2)
        out.append(rec)
    out.sort(key=lambda r: (len(str(r['number']).split('-')[0]), str(r['number'])))
    from .workplaces import finish_records                    # v013 (map/rules/83 §5): gaze_deg — от стула к столу; room — уже по помещениям SVG
    out, no_g, _ = finish_records(out, keep_room=True)
    if no_g:
        log('места: ВНИМАНИЕ — без gaze_deg %d: точка стула в центре стола' % no_g)
    if not svg:
        log('места: ВНИМАНИЕ — room не записан: карты (--svg) нет (map/rules/83 §5)')
    n_ch = sum(1 for r in out if r['by'] == 'стул')
    info.update(places=len(out), by_chair=n_ch, by_side=len(out) - n_ch, pedestals_attached=len(peds) - len(pedq),
                furniture_desks=len(spare))
    log('места: мест %d — по стулу %d, по стороне стола %d; тумб у столов %d из %d; столов плана без номера (мебель) %d'
        % (len(out), n_ch, len(out) - n_ch, len(peds) - len(pedq), len(peds), len(spare)))
    for d in spare:
        log('места: стол плана %s «%s» без номера — мебель' % (d['handle'], d['type']))
    fdesks = [dict(type=d['type'], plan_desk=d['handle'], desk=[[round(x, 1), round(y, 1)] for x, y in list(d['px'].exterior.coords)[:-1]]) for d in spare]
    pedl = [[[round(x, 1), round(y, 1)] for x, y in list(peds[k].exterior.coords)[:-1]] for k in pedq]
    return out, [[round(float(x), 1), round(float(y), 1)] for x, y in chairs], fdesks, pedl, info


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('dxf'); ap.add_argument('--frame', required=True, help='M_t.npy моста: мм -> px карты')
    ap.add_argument('--px-per-m', type=float, required=True); ap.add_argument('--svg', help='карта (SVG) — стены, колонны, помещения')
    ap.add_argument('--size', help='W,H картинки (по умолчанию — viewBox карты)')
    ap.add_argument('--out', default='places.json'); ap.add_argument('--chairs-out', default='chairs.json')
    ap.add_argument('--desk-in-wall', choices=('shift', 'cut'), default='shift', help='shift — канон map/rules/61 §3.2 (умолчание); cut — П3-7 (ОЧ-26)')
    ap.add_argument('--number-re', default=NUMBER_RE, help='формат номера места клиента (настройка; по умолчанию 1–3 цифры и «-N»)')
    ap.add_argument('--plan-png'); ap.add_argument('--a3-out'); ap.add_argument('--underlay', help='оригинал в кадре холста (PNG) — низ черновика 25 / 50 / 100; нет — белый (громко)')
    a = ap.parse_args()
    from .zones import load_frame
    M, t = load_frame(a.frame); logs = []
    def log(s):
        print(s); logs.append(s)
    places, chairs, fdesks, peds, info = build(a.dxf, M, t, a.px_per_m, a.svg, a.desk_in_wall, a.number_re, log)
    size = [int(v) for v in a.size.split(',')] if a.size else None
    if size is None and a.svg:
        from .svg_map import svg_canvas
        size = [int(round(v)) for v in svg_canvas(a.svg)]
    json.dump(dict(frame='artefact3 px', size=size, px_per_m=a.px_per_m, source='объекты инженерного плана: %s' % a.dxf.split('/')[-1], src='plan',
                   desk_in_wall=a.desk_in_wall, info=info, places=places, furniture_desks=fdesks, pedestals=peds, log=logs),
              open(a.out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    json.dump(dict(frame='plan', px_per_m=a.px_per_m, how='объекты chair инженерного плана (%s), центр контура, px карты' % a.dxf.split('/')[-1], chairs=chairs),
              open(a.chairs_out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    if a.plan_png and a.a3_out:
        from PIL import Image
        from .workplaces import render_draft, plan_mask_svg
        im = Image.open(a.plan_png); W, H = im.size
        kx = W / size[0] if size else 1.0
        und = None
        if a.underlay:
            import cv2
            und = np.asarray(Image.open(a.underlay).convert('RGB'))
            if und.shape[:2] != (H, W):
                und = cv2.resize(und, (W, H), interpolation=cv2.INTER_AREA if kx < 1 else cv2.INTER_LINEAR)
        P = [dict(p, desk=[[x * kx, y * kx] for x, y in p['desk']] if p.get('desk') else p.get('desk'),
                  centre=[p['centre'][0] * kx, p['centre'][1] * kx] if p.get('centre') else p.get('centre'), x=p['x'] * kx, y=p['y'] * kx) for p in places]
        recs, dinfo = render_draft(a.plan_png, und, P, a.a3_out, a.px_per_m * kx, inside=plan_mask_svg(a.svg, (W, H)) if a.svg else None, log=log)
        if dinfo['clipped']:
            log('места: ВНИМАНИЕ — черновик подрезал %d столов (resolve_overlaps): записи %s — в px картинки черновика' % (dinfo['clipped'], a.out))
            json.dump(dict(frame='artefact3 px', size=[W, H], px_per_m=a.px_per_m * kx, places=recs), open(a.out + '.draft_places.json', 'w', encoding='utf-8'),
                      ensure_ascii=False, indent=1)
    print(json.dumps(info, ensure_ascii=False))
    sys.exit(0 if places else 2)


if __name__ == '__main__':
    main()
