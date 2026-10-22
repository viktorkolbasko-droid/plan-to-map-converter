#!/usr/bin/env python3
"""bridge_convert.py — мост «инженерный план -> геометрия карты UnSpot», 0.33 (13.10.2026, код карты v012; 0.32 — код карты v011, пакет кода 5; 0.31 — код карты v010; 0.30 — 06.10.2026, код карты v009, пакет кода 3).

0.33 (13.10.2026, код карты v012, КМ-1…КМ-11 пакета v012): вход — DXF плана 012/013: класс объекта по XDATA UNSPOT `type` (одна таблица TYPE_CLASS ниже),
без XDATA — по коду элемента ISO, как 0.32; неизвестный type — СТОП с местом (отчёт `неизвестный_type`, код 3); прямоугольник проёма двери
(LWPOLYLINE type=door) — готовый проём по обеим створкам; витраж — по mullion + facade; кривые (bulge, ARC, CIRCLE) — объектами `кривые`;
«ПК» — со слоя 68 любого представления, словарь надписей — из настройки (--cfg). Учёт дверей плана — `двери_плана` (проём или причина).
Топология (КМ-6, КМ-7): ядро листа AutoCAD — одна грань на массив (coreblock/coreline, №104), кабина с унитазом и ниша «ПК» — часть
соседа; через край заливки 92 помещения не сливаются; кабина для звонков (booth) — помещение «маленькая переговорная»; тип грани по
заливке — из настройки (zone_fill_type). Проём по обеим створкам (КМ-9): прямоугольник Э7д плана 012/013, у 010 — две створки блока.
Геометрия — шаги кода прохода v03 общими правилами (bridge_post.py, граф носителей bridge_graph.py; --no-post — без них): короба и
короба «ПК», дуги SVG A по кривым плана, прореживание и правка косых на общем графе с откатом каждой операции, проёмы без стены
и по сечению стены, колонны по телу плана, стекло плана на рёбрах, порядок слоя rooms и резка стекла по проёму, тонкие накладки
помещений, округление до 0,01 px с починкой самокасаний; отчёт шагов — `шаги_v03` и `<отчёт>_шаги.txt`; `помещений` — после всех
снятий (= SVG). Память (КМ-11): центры узлов скелета — суммами по меткам, расстояние лёгких линий — float16, растры после дверей
освобождаются: пик на клиент Б k = 2 — 2,9–3,1 ГБ (0.32 — 3,75).

Решение владельца 30.09.2026 (п. 143): карта UnSpot может брать стены из готового инженерного плана того же этажа
«как исходник геометрии». Конвертер строит только геометрию карты: оси стен одним графом, помещения — грани графа,
проёмы, фасад (глухие участки 2T, остекление), стеклянные перегородки, колонны. Смысл — карточка, цвет по заявке, мебель,
бейджи, рабочие места — делает проход карты по map/00 §3; конвертер его не заменяет и не принимает решений за приёмку.

0.32 (07.10.2026, код карты v011, ПК4-К12, ПК4-К13): колонна-блок с заливкой 28 SOLID внутри блока — по заливке (символ листа), без неё — оболочкой
линий блока; стекло, витраж и проём под коробом колонны обрезаются по коробу (`обрезано_по_коробу` в отчёте).
0.31 (07.10.2026, код карты v010, К-7; №89, строка 195): колонна или короб обшивки у стены, видные на листе отдельным объектом (выступ
от граней стены ≥ её толщины или короб втрое шире стены), — колонной: контур короба поверх стены, стена по сторонам кончается на гранях короба; скрытая
в стене — часть стены; однотипные — одним решением; колонна без заливки 28 — оболочкой блока 28; пустоты коробов снимаются после К6; геометрия стен — как 0.30.
0.30 (решение владельца 03.10.2026, строка 149 — лист AutoCAD читается один раз, инженерным планом; ПФ5, К6–К8):
  * слой -> роль по коду элемента ISO 13567 (поле элемента и поле представления E/H/T имени слоя, plan/rules/50 §1),
    а не по имени слоя одного листа: 21 — фасад, 22x — стены, 22G — стекло (заливка SOLID или блок «стеклянн…») и лёгкие
    (линии без заливки), 28 — колонны, 31 — витраж, 32 — двери, 66 — лифты, 24 — лестницы, 76 — шкафы, 92 — заливки зон,
    93 — разделители, 90…T — надписи;
  * стена, нарисованная только линией (ядро листа AutoCAD: «контуры блоков — линии A-221, тел стен в ядре нет», строка 150) —
    тело толщиной T по линии; узор материала стены (штриховка не SOLID), не покрытый телом, — массив: тело — полоса T
    внутрь от его грани (map/rules/40 §2.10);
  * граница заливки зоны (92) вне стен — виртуальная граница (map/rules/11 §8, «Заливка коридора — кольцо…»);
  * помещение — по марке: марка Revit «номер + Имя NN м²» или номер в кружке со слоя надписей (map/rules/11 §8, п. 2);
    имена — надписи без цифр со слоя надписей; площадь марки не сходится или грань больше 30 % этажа — СТОП с местом
    (код выхода 3, `стоп` в отчёте; К7);
  * К6 — регуляризация: главные направления этажа по длине рёбер (не только оси листа), одна прямая стена — одна координата,
    ступенька меньше T — та же стена (map/rules/40 §2.4), рёбра короче T снимаются;
  * К8 — проём по полотну и хорде блока двери, после регуляризации — на ось своей стены, глубина — толщина своей стены + 1 px
    (svg_map.DOOR_EXTRA, Ч-19).

Вход — DXF инженерного плана (мм, ISO 13567, plan/rules/50 §1). Условности карты, которых нет в инженерном плане:
  * тело стены -> ось: скелет тела; класс по слою: A-21 — фасад 2T, A-221/222/223 — T (map/rules/30 §3);
  * двойная стена с зазором меньше T — одно тело, одна ось (map/rules/40 §2.4);
  * двери считаются закрытыми (map/rules/40 §3.2): проём двери A-32 — по полотну и дуге (хорде) блока, заливается сечением
    стены у косяков; торцы друг против друга ближе 2,2 м — проход; проём — интервал от косяка до косяка, глубина —
    толщина стены, цвет — цветного соседа (map/rules/60 §2.1–§2.3); штора в проёме — граница;
  * лестничная клетка — одно помещение, стенка между маршами — не стена (map/rules/40 §3.3);
  * шкафы A-76, которые закрывают разрыв между двумя торцами стен, — стена по торцам, сами шкафы — мебель
    (решение владельца 02.10.2026: «шкафы выполняют роль стены»); шкафы в углу — мебель (там же: «встроенная мебель»);
  * колонны A-28, кабины санузлов, турникеты и ограждения — не стены (map/rules/40 §2.8, map/rules/61 §2.2);
  * разделители Revit A-93 (пунктир) — склеиваются в линии, это виртуальные границы зон: делят, не рисуются (map/rules/40 §2.9);
  * линии A-22G без штриховки: двойная линия (полутолщина ≥ 2 px) — перегородка, стена, если отделяет помещение;
    одиночная — контур зоны, полосы растений, экраны: делит как виртуальная граница, стеной не рисуется.
Запуск:
  python3 bridge_convert.py plan.dxf out.svg --px-per-m 52.49 [--frame M_t.npy] [--size W,H] [--report out.json]
    [--debug prefix] [--no-stop]
--frame — аффинное мм -> px карты (np.save: M 2×2 построчно, затем t); иначе холст по габариту здания с полями 100 px.
Код выхода: 0 — черновик готов; 3 — СТОП (площадь марки не сходится, грань больше 30 % этажа): SVG и отчёт записаны,
места — `стоп` отчёта; продолжать карту — только разобрав каждое место (--no-stop — код 0, стоп остаётся в отчёте)."""
import argparse, json, math, os, re, sys, collections
import numpy as np, cv2, ezdxf
from ezdxf import path as ezpath
from scipy import ndimage
from skimage.morphology import skeletonize
from skimage.segmentation import watershed
from shapely.geometry import LineString, MultiPoint, Point, Polygon
from shapely import affinity
from shapely.ops import unary_union, polygonize_full, nearest_points
from shapely.strtree import STRtree

VERSION = '0.33'
WALL, GLASS = '#CBD2D6', '#86C5FB'
WALL_H = {'A-21----H-': 'ext', 'A-221---H-': 'int', 'A-222---H-': 'int', 'A-223---H-': 'int'}   # справочно: так названы слои у Revit-плана
DOOR_EXTRA = 1.0                                   # проём глубже стены на 1 px — unspot_map.svg_map.DOOR_EXTRA, acceptance OPENING_EXTRA (Ч-19)

# 0.33 (КМ-1): класс объекта плана 012/013 по XDATA UNSPOT `type` -> класс моста. Одна таблица на оба маршрута плана (AutoCAD со слоями и Revit).
# Роль стены (ext/int) — по коду элемента ISO (21 / 22x), type её уточняет; 'skip' — известный объект, мосту не нужен (мебель, оборудование,
# служебная разметка): не стена и не граница. type, которого нет в таблице, — СТОП с местом (`неизвестный_type`), а не тихо «лёгкая линия».
TYPE_CLASS = {
    'wall_cap': 'wall', 'wall_gkl': 'wall', 'wallline': 'wall', 'gklpart': 'wall',
    'coreblock': 'wall', 'coreline': 'wall',                         # ядро листа AutoCAD: блоки массива и его контурные линии (КМ-6)
    'glass': 'glass', 'glasspart': 'glass', 'lpart': 'light',
    'facade': 'fglass', 'mullion': 'fglass',
    'door': 'door', 'column': 'col', 'lift': 'lift', 'stair': 'stair',
    'counter': 'cab', 'kitchen': 'cab', 'rack': 'cab', 'cabinet': 'cab', 'wardrobe': 'cab',
    'roomsep': 'sep', 'shaft': 'shaft', 'desk': 'desk', 'chair': 'chair', 'booth': 'booth',
    'san': 'san', 'wc': 'san', 'fire': 'fire', 'tagc': 'text',
    'sofa': 'skip', 'armchair': 'skip', 'storage': 'skip', 'pedestal': 'skip', 'dtable': 'skip', 'mtable': 'skip', 'rtable': 'skip',
    'ctable': 'skip', 'table': 'skip', 'round': 'skip', 'reception': 'skip', 'benchend': 'skip', 'screen': 'skip', 'monitor': 'skip',
    'furn_src': 'skip', 'equip': 'skip', 'mfp': 'skip', 'plant': 'skip', 'conv': 'skip', 'convector': 'skip', 'heatband': 'skip',
    'misc': 'skip', 'sign': 'skip', 'wcacc': 'skip', 'wcsink': 'skip', 'sink_src': 'skip', 'stray': 'skip', 'axis': 'skip',
    'mark': 'skip', 'doormark': 'skip', 'dim': 'skip', 'measure': 'skip'}
PK_LABELS = ('ПК',)                                                 # надписи короба пожарного шкафа (П3-12) — по умолчанию; словарь клиента — --cfg pk_labels

def xtype(e):
    """0.33: XDATA UNSPOT type объекта плана 012/013 или None (план 010 и чужие DXF — без XDATA)"""
    try:
        if not e.has_xdata('UNSPOT'): return None
        for code, val in e.get_xdata('UNSPOT'):
            if code == 1000 and str(val).startswith('type='): return str(val)[5:].strip()
    except Exception: return None
    return None

def iso(L):
    """имя слоя ISO 13567 -> (код элемента, код представления): 'A-221---H-' -> ('221', 'H'); 'A-22G---E-' -> ('22G', 'E')"""
    L = str(L or '')
    if len(L) >= 3 and L[1] == '-': return L[2:8].rstrip('-'), (L[8] if len(L) > 8 else '')
    return L, ''

def wall_role(el):
    """роль стены по коду элемента CI/SfB (plan/rules/50 §1): 21… — наружные (2T), 22 и цифра — внутренние (T); 22G — не тело"""
    if el.startswith('21'): return 'ext'
    if re.fullmatch(r'22\d?', el): return 'int'
    return None

ROLE = {'22G': 'light', '28': 'col', '31': 'fglass', '32': 'door', '66': 'lift', '24': 'stair', '76': 'cab', '93': 'sep', '92': 'zone', '90': 'text'}
TYPE_FILL = {'open': '#EBF5FF', 'office': '#F1EBFF', 'meeting': '#FFF5EB', 'lounge': '#F8FFEB', 'kitchen': '#F8FFEB'}   # по типу; по заявке — проход карты
NAME_TYPE = [(r'переговор|конференц', 'meeting'), (r'общая зона|опен|open', 'open'), (r'отдел|кабинет', 'office'),
             (r'кухн|столов|бар', 'kitchen'), (r'отдых|лаунж|ожидан|кабина для сна', 'lounge'), (r'коридор|холл|тамбур', 'corridor'),
             (r'с/у|санузел|туалет|wc', 'wc'), (r'пуи|уборочн', 'cleaning'), (r'склад|архив|кладов', 'storage'),
             (r'раздевал|гардероб', 'wardrobe'), (r'серверн|цод', 'server'), (r'щитов|вент|чиллер|техн', 'tech'),
             (r'лифт', 'lift'), (r'лестниц', 'stair'), (r'шахт', 'shaft')]
NUMRE = r'\d+(?:[.,/-]\d+)*[A-Za-zА-Яа-яЁё]?'                 # номер помещения: 12, 40.18, 3-12, 5а
CLOSED_ALWAYS = {'meeting', 'wc', 'tech', 'server', 'storage', 'lift', 'stair', 'shaft', 'cleaning', 'wardrobe'}
CLS = ['none', 'ext', 'int', 'glass', 'fglass', 'light2', 'light1', 'door', 'cab', 'pass', 'curtain', 'sep', 'outline', 'zone']
CID = {c: i for i, c in enumerate(CLS)}
WEAK = {'light1': 1.0, 'sep': 1.0, 'outline': 1.0, 'none': 1.0, 'pass': 1.0, 'cab': 1.0, 'zone': 0.3}   # слабая граница при слиянии безымянной грани
SOLID = {'ext', 'int', 'glass', 'fglass', 'cab', 'door'}          # торцы этих классов замыкаются проходами
REAL = SOLID | {'light2', 'pass', 'curtain'}                      # граница «настоящего» помещения

def layer_code(L):
    p = L.split('-'); return f'{p[0]}-{p[1]}' if len(p) > 1 else L

def ent_paths(e, tol=1.0):
    if e.dxftype() == 'INSERT':
        for x in e.virtual_entities(): yield from ent_paths(x, tol)
        return
    if e.dxftype() in ('TEXT', 'MTEXT', 'HATCH', 'DIMENSION', 'POINT', 'ATTRIB', 'ATTDEF'): return
    try: p = ezpath.make_path(e)
    except Exception: return
    P = np.array([(v.x, v.y) for v in p.flattening(tol)])
    if len(P) >= 2: yield P

def hatch_rings(h):
    return [R for R in (np.array([(v.x, v.y) for v in p.flattening(1.0)]) for p in ezpath.from_hatch(h)) if len(R) >= 3]

def block_hatch_rings(ins, elem):
    """0.32 (ПК4-К12): кольца заливок SOLID элемента elem внутри блока (вложенные — тоже), мм; слой «0» в блоке — слой вставки"""
    out = []
    for x in ins.virtual_entities():
        if x.dxftype() == 'INSERT': out += block_hatch_rings(x, elem); continue
        if x.dxftype() != 'HATCH' or x.dxf.pattern_name.upper() != 'SOLID': continue
        if iso(x.dxf.layer if x.dxf.layer != '0' else ins.dxf.layer)[0] != elem: continue
        out += hatch_rings(x)
    return out

def circle_of(e):
    """кружок марки: CIRCLE или замкнутая ломаная/полилиния с дугами постоянного радиуса -> (cx, cy, r) мм или None"""
    if e.dxftype() == 'CIRCLE': return float(e.dxf.center[0]), float(e.dxf.center[1]), float(e.dxf.radius)
    try: P = np.array([(v.x, v.y) for v in ezpath.make_path(e).flattening(1.0)])
    except Exception: return None
    if len(P) < 8 or np.hypot(*(P[0] - P[-1])) > 0.05 * np.ptp(P[:, 0]) + 1.0: return None
    c = P.mean(0); r = np.hypot(*(P - c).T)
    return (float(c[0]), float(c[1]), float(r.mean())) if r.mean() > 0 and r.std() / r.mean() < 0.06 else None

def text_centre(e):
    """центр надписи TEXT в мм: точка вставки + половина строки по направлению (≈ 0,6 кегля на знак) — для кружка марки"""
    q = e.dxf.align_point if (e.dxf.hasattr('align_point') and (e.dxf.get('halign', 0) or e.dxf.get('valign', 0))) else e.dxf.insert
    h = float(e.dxf.height); a = math.radians(float(e.dxf.get('rotation', 0) or 0)); u = np.array([math.cos(a), math.sin(a)]); n = np.array([-u[1], u[0]])
    w = 0.6 * h * len(e.dxf.text.strip()); ha, va = e.dxf.get('halign', 0), e.dxf.get('valign', 0)
    p = np.array([float(q[0]), float(q[1])])
    if not (ha or va): p = p + u * w / 2 + n * h / 2
    elif ha in (1, 4): p = p + n * (h / 2 if va in (0, 1) else -h / 2 if va == 3 else 0)
    elif ha == 2: p = p - u * w / 2
    return p, h

def arc_of(e, cls, out, depth=0):
    """0.33 (КМ-8): кривые плана объектами, а не ломаной: bulge LWPOLYLINE, ARC, CIRCLE (и внутри блока) ->
    (класс, cx, cy, r, a0, a1, полная окружность) мм; дуга идёт против часовой от a0 к a1 (градусы)"""
    t = e.dxftype()
    try:
        if t == 'INSERT' and depth < 3:
            for x in e.virtual_entities(): arc_of(x, cls, out, depth + 1)
        elif t == 'CIRCLE': out.append((cls, float(e.dxf.center[0]), float(e.dxf.center[1]), float(e.dxf.radius), 0.0, 360.0, True))
        elif t == 'ARC': out.append((cls, float(e.dxf.center[0]), float(e.dxf.center[1]), float(e.dxf.radius), float(e.dxf.start_angle), float(e.dxf.end_angle), False))
        elif t == 'LWPOLYLINE':
            from ezdxf.math import bulge_to_arc
            P = list(e.get_points('xyb')); n = len(P)
            for i in range(n if e.closed else n - 1):
                x1, y1, bl = P[i]; x2, y2, _ = P[(i + 1) % n]
                if abs(bl) < 1e-9 or math.hypot(x2 - x1, y2 - y1) < 1e-6: continue
                c, a0, a1, r = bulge_to_arc((x1, y1), (x2, y2), bl)
                out.append((cls, float(c.x), float(c.y), float(r), math.degrees(a0), math.degrees(a1), False))
    except Exception: pass

def read_dxf(path, pk_labels=PK_LABELS):
    """DXF инженерного плана -> классы моста. 0.33 (КМ-1): по XDATA UNSPOT `type` (TYPE_CLASS), без XDATA — по коду элемента ISO 13567
    (iso(), wall_role(), ROLE), как 0.32; неизвестный type — в `_unknown` (СТОП); прямоугольник проёма двери — `door_rect`, к своему блоку двери"""
    msp = ezdxf.readfile(path).modelspace(); D = collections.defaultdict(list); unk = collections.Counter(); byx = collections.Counter()
    def cls_of(e):
        ty = xtype(e)
        if ty is None: return None, None
        c = TYPE_CLASS.get(ty)
        if c is None: unk[(e.dxf.layer, ty)] += 1
        else: byx[ty] += 1
        return ty, c
    for h in msp.query('HATCH'):
        el, pr = iso(h.dxf.layer); wr = wall_role(el); solid = h.dxf.pattern_name.upper() == 'SOLID'; R = hatch_rings(h)
        ty, xc = cls_of(h)
        if not R: continue
        if ty in ('coreblock', 'coreline'): D['core_h'].append(R)          # 0.33 (КМ-6): тело ядра-массива по XDATA
        if wr and solid: D[wr].append(R)
        elif wr: D['massif'].append((wr, R))                       # узор материала стены: тело там, где нет SOLID, — массив
        elif el == '22G' and solid: D['glass_h'].append(R)          # стекло перегородок — залитая полоса (лист AutoCAD)
        elif el == '31' and solid: D['fglass_h'].append(R)
        elif el == '28' and solid: D['col_h'].append(R)
        elif el == '92' and solid: D['zone'].append(R)
    for e in msp:
        if e.dxftype() in ('HATCH', 'TEXT', 'MTEXT', 'DIMENSION'): continue
        el, pr = iso(e.dxf.layer); nm = e.dxf.name if e.dxftype() == 'INSERT' else f'({e.dxftype()})'
        ty, xc = cls_of(e)
        if pr == 'T' or el == '90' or xc in ('text', 'skip'): continue
        if xc in ('desk', 'chair', 'booth', 'san', 'fire', 'shaft'):     # 0.33: объекты плана по XDATA — признаки, не стены
            segs = list(ent_paths(e))
            if not segs: continue
            Q = np.vstack(segs)
            if xc == 'shaft': D['shaft'].append(segs); continue
            if len(Q) < 3: continue
            (cx_, cy_), (w_, h_), _ = cv2.minAreaRect(Q.astype(np.float32)); lo_, hi_ = sorted((w_, h_))
            if xc == 'desk':
                if 1100 <= hi_ <= 2200 and 500 <= lo_ <= 1000: D['desk'].append((cx_, cy_))
            elif xc in ('chair', 'san'): D[xc].append((cx_, cy_))
            else: D[xc].append(np.array(MultiPoint([tuple(p) for p in Q]).convex_hull.exterior.coords))
            continue
        if (xc == 'col' or (xc is None and el == '28')) and e.dxftype() == 'INSERT':   # 0.32 (ПК4-К12): колонна-блок — и заливка 28 SOLID внутри блока
            hr = block_hatch_rings(e, '28'); segs = list(ent_paths(e))
            if segs or hr: D['col'].append((nm, segs, hr))
            arc_of(e, 'col', D['curves'])
            continue
        wr = wall_role(el)
        if xc == 'wall' or (xc is None and wr):                      # линии слоёв стен: контур тела или стена одной линией
            segs = list(ent_paths(e))
            if segs:
                D['wline'].append((wr or 'int', segs))
                if ty in ('coreblock', 'coreline'): D['core_l'].append(segs)
                arc_of(e, 'wall', D['curves'])
            continue
        segs = list(ent_paths(e))
        if not segs: continue
        if xc == 'glass' or xc == 'light' or (xc is None and el == '22G'):
            if xc is None and re.search(r'турникет|огражден|обрыв', nm, re.I): D['skip'].append((nm, segs))
            elif xc == 'glass' or (xc is None and re.search(r'стеклянн', nm, re.I) and not re.search(r'без_штриховки', nm, re.I)):
                D['glass'].append((nm, segs)); arc_of(e, 'glass', D['curves'])
            else: D['light'].append((nm, segs))
        elif xc == 'fglass' or (xc is None and el == '31'):
            D['fglass'].append((nm, segs)); arc_of(e, 'fglass', D['curves'])
            if ty == 'mullion' or (xc is None and e.dxftype() == 'INSERT'):    # 0.33 (КМ-1): стойка витража — тело витража между линиями фасада
                Q = np.vstack(segs)
                if len(Q) >= 3: D['mullion'].append(np.array(MultiPoint([tuple(p) for p in Q]).convex_hull.exterior.coords))
        elif xc == 'door' or (xc is None and el == '32'):
            if e.dxftype() == 'INSERT':
                if re.search(r'штора', nm, re.I): D['curtain'].append((nm, segs))
                else:                                       # ось X блока двери — вдоль стены (так чертит инженерный план)
                    r_ = math.radians(e.dxf.rotation); D['door'].append(dict(nm=nm, segs=segs, dir=np.array([math.cos(r_), math.sin(r_)]), rect=None))
            elif xc == 'door' and len(segs) == 1 and len(segs[0]) >= 4 and (getattr(e, 'closed', False) or np.allclose(segs[0][0], segs[0][-1])):
                D['door_rect'].append(segs[0][:-1] if np.allclose(segs[0][0], segs[0][-1]) else segs[0])   # 0.33 (КМ-1, П3-13): проём Э7д по обеим створкам
            else: D['door_misc'].append((nm, segs))          # 0.33: линия слоя дверей без блока и без прямоугольника — не дверь, в отчёт
        elif xc == 'lift' or (xc is None and el == '66'): D['lift'].append((nm, segs))
        elif xc == 'stair' or (xc is None and el == '24'): D['stair'].append((nm, segs))
        elif xc == 'cab' or (xc is None and el == '76'): D['cab'].append((nm, segs))
        elif xc == 'col' or (xc is None and el == '28'): D['col'].append((nm, segs, [])); arc_of(e, 'col', D['curves'])
        elif xc == 'sep' or (xc is None and el == '93'): D['sep'].append((nm, segs))
        elif xc is None and el == '82':                     # стол рабочего места: габарит 1,1–2,2 × 0,5–1,0 м (признак открытой зоны)
            Q = np.vstack(segs)
            if len(Q) >= 3:
                (cx_, cy_), (w_, h_), _ = cv2.minAreaRect(Q.astype(np.float32)); lo_, hi_ = sorted((w_, h_))
                if 1100 <= hi_ <= 2200 and 500 <= lo_ <= 1000: D['desk'].append((cx_, cy_))
    txt, circ = [], []                                  # надписи слоя надписей помещений (90, подслой T) и кружки марок
    def take_text(e, top):
        if e.dxftype() == 'TEXT':
            s = e.dxf.text.strip(); c, h = text_centre(e)
            q = e.dxf.align_point if (top and e.dxf.hasattr('align_point') and (e.dxf.get('halign', 0) or e.dxf.get('valign', 0))) else e.dxf.insert
            txt.append((s, float(q[0]), float(q[1]), float(e.dxf.height), float(c[0]), float(c[1])))
        elif e.dxftype() == 'MTEXT':
            s = e.plain_text().strip(); q = e.dxf.insert; h = float(e.dxf.char_height)
            for i, line in enumerate(s.split('\n')): txt.append((line.strip(), float(q[0]), float(q[1]) - i * 1.6 * h, h, float(q[0]), float(q[1]) - i * 1.6 * h))
    pkre = re.compile(r'^(?:' + '|'.join(re.escape(x) for x in pk_labels) + r')\s*\*?\s*\d*$', re.I) if pk_labels else None
    for e in msp:
        el, pr = iso(e.dxf.layer)
        if el == '68' and e.dxftype() in ('TEXT', 'MTEXT') and pkre is not None:      # 0.33 (КМ-5, П3-12): надпись короба ПК — слой 68 любого представления
            s_ = (e.dxf.text if e.dxftype() == 'TEXT' else e.plain_text()).strip()
            if pkre.match(s_): c_, _ = text_centre(e) if e.dxftype() == 'TEXT' else (np.array([e.dxf.insert[0], e.dxf.insert[1]]), 0); D['pk'].append((float(c_[0]), float(c_[1]), s_))
            continue
        if el != '90' or pr != 'T': continue
        ents = list(e.virtual_entities()) if e.dxftype() == 'INSERT' else [e]
        for x in ents:
            if x.dxftype() in ('TEXT', 'MTEXT'): take_text(x, e.dxftype() != 'INSERT')
            elif x.dxftype() in ('CIRCLE', 'LWPOLYLINE', 'POLYLINE'):
                c = circle_of(x)
                if c: circ.append(c)
    D['text'], D['tagc'] = txt, circ
    if D['door_rect']:                                  # 0.33 (КМ-1): прямоугольник проёма — к блоку двери, который он накрывает (один к одному)
        hulls = []
        for it in D['door']:
            Q = np.vstack(it['segs']) if it['segs'] else np.zeros((0, 2))
            hulls.append(MultiPoint([tuple(p) for p in Q]).convex_hull if len(Q) >= 3 else None)
        pairs = []
        for ri, R in enumerate(D['door_rect']):
            g = Polygon(R).buffer(0).buffer(50)
            for di, hl in enumerate(hulls):
                if hl is not None and g.intersects(hl):
                    a_ = g.intersection(hl).area
                    if a_ > 0: pairs.append((-a_, ri, di))
        used_r, used_d = set(), set()
        for _, ri, di in sorted(pairs):
            if ri in used_r or di in used_d: continue
            used_r.add(ri); used_d.add(di); D['door'][di]['rect'] = D['door_rect'][ri]
        for ri, R in enumerate(D['door_rect']):           # прямоугольник без блока — проём без полотна
            if ri not in used_r: D['door'].append(dict(nm='(прямоугольник проёма)', segs=[], dir=None, rect=R))
    D['_unknown'] = [dict(слой=L, type=t, объектов=n) for (L, t), n in sorted(unk.items())]
    D['_xdata'] = dict(sorted(byx.items()))
    return D

def segs_of(item):
    """0.33: ломаные объекта класса моста — кортеж (имя, ломаные, …) или словарь двери {nm, segs, dir, rect}"""
    return item['segs'] if isinstance(item, dict) else item[1]

def extent_pts(D):
    """точки габарита здания, мм: тела стен; нет тел SOLID — линии стен и массивы (лист, где стены — линиями)"""
    P = [r for cls in ('ext', 'int') for rings in D[cls] for r in rings]
    if not P: P = [Q for wr, segs in D['wline'] for Q in segs] + [r for wr, R in D['massif'] for r in R] + [Q for nm, segs in D['fglass'] for Q in segs]
    return np.vstack(P)

def frame_of(D, pxm, frame, margin=100):
    if frame:
        v = np.load(frame); return v[:4].reshape(2, 2), v[4:]
    allp = extent_pts(D); s = pxm / 1000.0
    M = np.array([[s, 0], [0, -s]]); t = np.array([margin - allp[:, 0].min() * s, margin + allp[:, 1].max() * s])
    return M, t

class Canvas:
    """растр в k раз мельче px карты"""
    def __init__(self, W, H, M, t, k=2): self.W, self.H, self.M, self.t, self.k = W, H, M, t, k
    def px(self, P): return np.asarray(P, float) @ self.M.T + self.t
    def img(self): return np.zeros((self.H * self.k, self.W * self.k), np.uint8)
    def q(self, P_px): return np.round(np.asarray(P_px) * self.k * 8).astype(np.int32)
    def fill(self, img, rings, v=255): cv2.fillPoly(img, [self.q(self.px(r)) for r in rings], v, shift=3)
    def fill_px(self, img, ring_px, v=255): cv2.fillPoly(img, [self.q(ring_px)], v, shift=3)
    def line(self, img, P, w_px=1.0, v=255, mm=True):
        cv2.polylines(img, [self.q(self.px(P) if mm else P)], False, v, max(1, int(round(w_px * self.k))), shift=3)
    def at(self, img, p):
        x, y = int(p[0] * self.k), int(p[1] * self.k)
        return img[y, x] if 0 <= y < img.shape[0] and 0 <= x < img.shape[1] else 0
    def win_fill(self, P, pad):
        """залить кольцо P (мм) в окне растра по его рамке ± pad px растра -> (маска окна, (y0, y1, x0, x1))"""
        q = self.px(P) * self.k
        x0, y0 = (np.floor(q.min(0)).astype(int) - pad).tolist(); x1, y1 = (np.ceil(q.max(0)).astype(int) + pad + 1).tolist()
        x0, y0 = max(x0, 0), max(y0, 0); x1, y1 = min(x1, self.W * self.k), min(y1, self.H * self.k)
        m = np.zeros((max(y1 - y0, 1), max(x1 - x0, 1)), np.uint8)
        cv2.fillPoly(m, [np.round((q - (x0, y0)) * 8).astype(np.int32)], 255, shift=3)
        return m, (y0, y1, x0, x1)

# ------------------------------------------------------------------ двери: проём по полотну и дуге (хорде)
def straight_parts(segs):
    out = []
    for P in segs:
        for a, b in zip(P[:-1], P[1:]):
            if np.hypot(*(b - a)) > 0.3: out.append((a, b))
    return out

def chains(parts, maxlen):
    """короткие отрезки -> цепочки по общим концам (дуги, развёрнутые в отрезки)"""
    key = lambda p: (round(p[0] * 4), round(p[1] * 4))
    short = [(a, b) for a, b in parts if np.hypot(*(b - a)) <= maxlen]
    adj = collections.defaultdict(list)
    for i, (a, b) in enumerate(short): adj[key(a)].append(i); adj[key(b)].append(i)
    seen, out = set(), []
    for i in range(len(short)):
        if i in seen: continue
        seen.add(i); a, b = short[i]; pts = [a, b]
        for direction in (0, 1):
            cur = pts[-1] if direction == 0 else pts[0]
            while True:
                nx = [j for j in adj[key(cur)] if j not in seen]
                if len(nx) != 1: break
                j = nx[0]; seen.add(j); p, q = short[j]
                nxt = q if key(p) == key(cur) else p
                if direction == 0: pts.append(nxt)
                else: pts.insert(0, nxt)
                cur = nxt
        out.append(np.array(pts))
    return out

def door_opening(segs_px, pxm):
    """кандидаты проёма двери (петля, конец, длина): полотно 0,45–1,3 м + точка на 90° от него на той же длине (дуга или хорда),
    и дуга створки — цепочка коротких отрезков с поворотом 60–120°: центр — петля, концы дуги — полотно и проём.
    Полотно (открытое положение) и проём (закрытое) симметричны — выбирает вызывающий по стене у петли."""
    parts = straight_parts(segs_px); ends = np.array([p for ab in parts for p in ab]) if parts else np.zeros((0, 2))
    cand = []
    for a, b in parts:
        L = float(np.hypot(*(b - a)))
        if not (0.45 * pxm <= L <= 1.3 * pxm): continue
        for hinge, tip in ((a, b), (b, a)):
            u = (tip - hinge) / L
            for rot in (np.array([[0, -1], [1, 0]]), np.array([[0, 1], [-1, 0]])):
                v = rot @ u; ideal = hinge + v * L
                d = np.hypot(*(ends - ideal).T)
                j = int(np.argmin(d)) if len(d) else -1
                if j < 0 or d[j] > 0.15 * L: continue
                rel = ends - hinge; r = np.hypot(*rel.T); cosu, cosv = rel @ u, rel @ v
                arc = np.sum((np.abs(r - L) < 0.12 * L) & (cosu > -0.05 * L) & (cosv > -0.05 * L))
                chord = np.sum(np.abs((rel @ (u + v)) / math.sqrt(2) - L / math.sqrt(2)) < 0.05 * L)
                score = min(arc + chord, 10) / 10 - d[j] / L
                cand.append((score + 0.5, hinge.copy(), ends[j].copy(), L))   # полотно нарисовано открытым — проём под 90°
                cand.append((score, hinge.copy(), tip.copy(), L))               # или полотно нарисовано закрытым — проём по нему
    for Q in chains(parts, 0.3 * pxm):
        if len(Q) < 5: continue
        A_ = np.c_[2 * Q, np.ones(len(Q))]; bb = (Q ** 2).sum(1); c = np.linalg.lstsq(A_, bb, rcond=None)[0]
        cx, cy = c[0], c[1]; R = math.sqrt(max(c[2] + cx * cx + cy * cy, 0))
        if not (0.45 * pxm <= R <= 1.3 * pxm): continue
        if np.abs(np.hypot(Q[:, 0] - cx, Q[:, 1] - cy) - R).max() > 0.06 * R: continue
        v0, v1 = Q[0] - (cx, cy), Q[-1] - (cx, cy)
        ang = math.degrees(math.acos(np.clip(v0 @ v1 / (np.hypot(*v0) * np.hypot(*v1)), -1, 1)))
        if not (15 <= ang <= 120): continue                        # 0.30 (К8): и неполная дуга — от 15° (план дорисовал дугу, полотно открыто не на 90°)
        h = np.array([cx, cy]); cand.append((0.5, h, Q[0].copy(), R)); cand.append((0.5, h.copy(), Q[-1].copy(), R))
    cand.sort(key=lambda z: -z[0])
    return cand

def wall_dir(img, C, p, r=30.0):
    """главное направление тела стены около точки p (px карты): (вектор, анизотропия 0..1)"""
    k = C.k; x, y = int(p[0] * k), int(p[1] * k); R = int(r * k)
    win = img[max(0, y - R):y + R, max(0, x - R):x + R] > 0
    ys, xs = np.nonzero(win)
    if len(xs) < 10: return None, 0.0
    Q = np.c_[xs, ys].astype(float); Q -= Q.mean(0)
    w, V = np.linalg.eigh(Q.T @ Q / len(Q))
    return V[:, 1], float((w[1] - w[0]) / (w[1] + w[0] + 1e-9))

def wall_section(walls, C, p, n, reach=40.0):
    """интервал тела стены вдоль нормали n у точки p: (n0, n1) в px карты или None"""
    s = np.arange(-reach, reach + 0.01, 0.5); pts = p + np.outer(s, n)
    v = np.array([C.at(walls, q) > 0 for q in pts])
    if not v.any(): return None
    idx = np.nonzero(v)[0]
    runs = np.split(idx, np.nonzero(np.diff(idx) > 1)[0] + 1)
    run = min(runs, key=lambda r: min(abs(s[r[0]]), abs(s[r[-1]])) if not (s[r[0]] <= 0 <= s[r[-1]]) else 0)
    if min(abs(s[run[0]]), abs(s[run[-1]])) > 8 and not (s[run[0]] <= 0 <= s[run[-1]]): return None
    if s[run[0]] <= -reach + 0.5 or s[run[-1]] >= reach - 0.5: return 'corner'  # упёрлись в предел — стена поперёк: угол, косяк есть, сечения нет
    return float(s[run[0]]), float(s[run[-1]])

# ------------------------------------------------------------------ граф скелета
OFFS = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]

def skel_graph(mask):
    """скелет маски -> центры узлов (кластеры пикселей степени ≠ 2) и рёбра [узел, узел, ломаная px растра]"""
    sk = skeletonize(mask > 0); H, W = sk.shape
    nb = ndimage.convolve(sk.astype(np.uint8), np.ones((3, 3), np.uint8), mode='constant') - sk
    node = sk & (nb != 2)
    lab, nn = ndimage.label(node, structure=np.ones((3, 3)))
    ys_, xs_ = np.nonzero(node); ll_ = lab[ys_, xs_]                      # 0.33 (КМ-11, Н-E11): центры узлов — суммами по меткам, без полноразмерных сеток center_of_mass
    cnt_ = np.bincount(ll_, minlength=nn + 1).astype(float); cnt_[cnt_ == 0] = 1.0
    cxs, cys = np.bincount(ll_, weights=xs_, minlength=nn + 1) / cnt_, np.bincount(ll_, weights=ys_, minlength=nn + 1) / cnt_
    cen = [None] + [np.array([cxs[i], cys[i]]) + 0.5 for i in range(1, nn + 1)]; del ys_, xs_, ll_
    vis = np.zeros_like(sk)
    def nbrs(y, x):
        for dy, dx in OFFS:
            a, b = y + dy, x + dx
            if 0 <= a < H and 0 <= b < W and sk[a, b]: yield a, b
    edges = []
    ys, xs = np.nonzero(node)
    for y, x in zip(ys.tolist(), xs.tolist()):
        c0 = lab[y, x]
        for a, b in nbrs(y, x):
            if node[a, b] or vis[a, b]: continue
            path = [(a, b)]; vis[a, b] = True; prev, cur, c1 = (y, x), (a, b), None
            while True:
                nxt = [p for p in nbrs(*cur) if p != prev]
                nn_ = [p for p in nxt if node[p]]
                fr = [p for p in nxt if not node[p] and not vis[p]]
                if nn_ and not (len(path) == 1 and all(lab[p] == c0 for p in nn_) and fr):
                    c1 = lab[nn_[0]]; break
                if not fr: break
                prev, cur = cur, fr[0]; vis[cur] = True; path.append(cur)
            if c1 is None: continue
            edges.append([c0, c1, np.array([cen[c0]] + [np.array([p[1] + 0.5, p[0] + 0.5]) for p in path] + [cen[c1]])])
    rest = sk & ~vis & ~node
    while rest.any():
        y, x = map(int, np.argwhere(rest)[0]); nn += 1; cen.append(np.array([x + 0.5, y + 0.5])); c0 = nn
        path = [(y, x)]; rest[y, x] = False; vis[y, x] = True; cur = (y, x)
        while True:
            fr = [p for p in nbrs(*cur) if not vis[p]]
            if not fr: break
            cur = fr[0]; vis[cur] = True; rest[cur] = False; path.append(cur)
        P = np.array([cen[c0]] + [np.array([p[1] + 0.5, p[0] + 0.5]) for p in path[1:]] + [cen[c0]])
        if len(P) >= 4: edges.append([c0, c0, P])
    return cen, edges

def plen(P): return float(np.hypot(*np.diff(P, axis=0).T).sum()) if len(P) > 1 else 0.0

def merge_deg2(edges):
    while True:
        deg = collections.Counter(); inc = collections.defaultdict(list)
        for i, (a, b, P) in enumerate(edges): deg[a] += 1; deg[b] += 1; inc[a].append(i); inc[b].append(i)
        done = False; dead = set(); new = []
        for n, d in deg.items():
            if d != 2: continue
            i, j = inc[n]
            if i == j or i in dead or j in dead: continue
            (a1, b1, P1), (a2, b2, P2) = edges[i], edges[j]
            if a1 == b1 or a2 == b2: continue
            P1 = P1 if b1 == n else P1[::-1]; s1 = a1 if b1 == n else b1
            P2 = P2 if a2 == n else P2[::-1]; s2 = b2 if a2 == n else a2
            if s1 == n or s2 == n: continue
            dead |= {i, j}; new.append([s1, s2, np.vstack([P1, P2[1:]])]); done = True
        if not done: return edges
        edges = [e for i, e in enumerate(edges) if i not in dead] + new

class _AtNodes:
    """0.33 (КМ-11): значения растра в узлах скелета (центры cen, с тем же зажимом к краю, что и чтение растра в prune_spurs) — вместо
    полного растра float32 на большом холсте; индексация dt[y, x] и dt.shape — как у массива"""
    def __init__(self, a, cen):
        self.shape = a.shape; H, W = a.shape; self.v = {}
        for c in cen[1:]:
            if c is None: continue
            y, x = min(max(int(c[1]), 0), H - 1), min(max(int(c[0]), 0), W - 1); self.v[(y, x)] = float(a[y, x])
    def __getitem__(self, yx): return self.v[(int(yx[0]), int(yx[1]))]


def prune_spurs(edges, cen, dt, thr_of, rounds=8):
    """срезать отростки: ребро со свободным концом короче порога своего класса"""
    for _ in range(rounds):
        deg = collections.Counter()
        for a, b, P in edges: deg[a] += 1; deg[b] += 1
        keep, cut = [], 0
        for a, b, P in edges:
            fa, fb = deg[a] == 1, deg[b] == 1
            if fa ^ fb:
                j = b if fa else a; y, x = int(cen[j][1]), int(cen[j][0])
                r = dt[min(max(y, 0), dt.shape[0] - 1), min(max(x, 0), dt.shape[1] - 1)]
                if plen(P) < thr_of(P, r): cut += 1; continue
            elif fa and fb and plen(P) < thr_of(P, 0) * 1.5: cut += 1; continue
            keep.append([a, b, P])
        edges = merge_deg2(keep)
        if not cut: break
    return edges

# ------------------------------------------------------------------ торцы и замыкания
def free_ends(E, T, back=6.0):
    """свободные концы рёбер; крючок на конце (последний отрезок короче 2,5T под углом > 55°, косяк двери) — конец в углу"""
    deg = collections.Counter()
    for e in E: deg[e['a']] += 1; deg[e['b']] += 1
    out = []
    for i, e in enumerate(E):
        P = e['P']
        for side, (n, seq) in enumerate(((e['a'], P), (e['b'], P[::-1]))):
            if deg[n] != 1 or len(seq) < 2: continue
            hook = 0
            sp = np.array(LineString(seq).simplify(1.5).coords)
            if len(sp) >= 3:
                s1, s2 = sp[1] - sp[0], sp[2] - sp[1]; l1, l2 = np.hypot(*s1), np.hypot(*s2)
                if l1 < 2.5 * T and l2 > l1 and l1 > 1e-6 and abs(s1 @ s2) / (l1 * l2) < math.cos(math.radians(55)):
                    hook = int(np.argmin(np.hypot(*(seq - sp[1]).T)))
            q = seq[hook:]
            L = np.r_[0, np.cumsum(np.hypot(*np.diff(q, axis=0).T))]; j = min(max(int(np.searchsorted(L, back)), 1), len(q) - 1)
            d = q[0] - q[j]; nrm = np.hypot(*d)
            if nrm > 1e-6: out.append(dict(p=q[0].copy(), d=d / nrm, edge=i, cls=e['cls'], side=side, hook=hook))
    return out

def facing(e1, e2, maxlen, ca):
    v = e2['p'] - e1['p']; L = float(np.hypot(*v))
    if L < 1e-6 or L > maxlen: return None
    u = v / L
    return L if (u @ e1['d'] >= ca and -(u @ e2['d']) >= ca) else None

def ray_hit(p, d, geom, maxlen):
    ray = LineString([p + d * 0.75, p + d * maxlen]); x = ray.intersection(geom)
    if x.is_empty: return None
    pts = []
    for g in getattr(x, 'geoms', [x]):
        if hasattr(g, 'coords'): pts += [np.array(c) for c in g.coords]
    if not pts: return None
    q = min(pts, key=lambda c: float(np.hypot(*(c - p))))
    return q if np.hypot(*(q - p)) > 1.0 else None

def join_dashes(lines, pxm, gap_m=1.0, ang_deg=4.0, off_px=2.0):
    """пунктир разделителя -> сплошные прямые: коллинеарные куски с разрывом до gap_m склеиваются"""
    segs = [np.array(g.coords)[[0, -1]] for g in lines if g.length > 0.2]
    n = len(segs); par = list(range(n))
    def f(i):
        while par[i] != i: par[i] = par[par[i]]; i = par[i]
        return i
    dirs = []
    for s in segs:
        d = s[1] - s[0]; d = d / max(np.hypot(*d), 1e-9); dirs.append(d if (d[0] > 1e-9 or (abs(d[0]) <= 1e-9 and d[1] > 0)) else -d)
    ca = math.cos(math.radians(ang_deg))
    for i in range(n):
        for j in range(i + 1, n):
            if abs(dirs[i] @ dirs[j]) < ca: continue
            nrm = np.array([-dirs[i][1], dirs[i][0]])
            if abs((segs[j].mean(0) - segs[i].mean(0)) @ nrm) > off_px: continue
            ti = sorted(segs[i] @ dirs[i]); tj = sorted(segs[j] @ dirs[i])
            gap = max(tj[0] - ti[1], ti[0] - tj[1])
            if gap <= gap_m * pxm: par[f(i)] = f(j)
    groups = collections.defaultdict(list)
    for i in range(n): groups[f(i)].append(i)
    out = []
    for g in groups.values():
        d = dirs[g[0]]; P = np.vstack([segs[i] for i in g]); tt = P @ d; c = P.mean(0); nrm = np.array([-d[1], d[0]])
        off = (P - c) @ nrm; base = c + nrm * off.mean()
        a, b = base + d * (tt.min() - c @ d), base + d * (tt.max() - c @ d)
        out.append(LineString([a, b]))
    return out

# ------------------------------------------------------------------ дуги
def fit_arcs(P, T):
    """кольцо px -> команды SVG: подряд ≥ 5 коротких рёбер одного знака поворота — дуга A по окружности МНК (ошибка < 0,8 px)"""
    P = np.asarray(P, float)
    if np.allclose(P[0], P[-1]): P = P[:-1]
    n = len(P)
    if n < 6: return 'M' + ' L'.join(f'{x:.1f} {y:.1f}' for x, y in P) + ' Z', 0
    E = np.roll(P, -1, 0) - P; L = np.hypot(*E.T); En = np.roll(E, -1, 0)
    cr = E[:, 0] * En[:, 1] - E[:, 1] * En[:, 0]
    short = L < 3.0 * T
    long_idx = np.nonzero(~short)[0]; start = int(long_idx[0]) + 1 if len(long_idx) else 0
    order = [(start + i) % n for i in range(n)]
    cmds, arcs, i = [f'M{P[order[0]][0]:.1f} {P[order[0]][1]:.1f}'], 0, 0
    while i < n:
        j = i
        while j < n and short[order[j]] and (j == i or np.sign(cr[order[j - 1]]) == np.sign(cr[order[j]]) or abs(cr[order[j]]) < 1e-3): j += 1
        if j - i >= 5:
            Q = np.array([P[order[m % n]] for m in range(i, j + 1)])
            A_ = np.c_[2 * Q, np.ones(len(Q))]; b = (Q ** 2).sum(1); c = np.linalg.lstsq(A_, b, rcond=None)[0]
            cx, cy = c[0], c[1]; R = math.sqrt(max(c[2] + cx * cx + cy * cy, 0))
            res = np.abs(np.hypot(Q[:, 0] - cx, Q[:, 1] - cy) - R).max() if R > 0 else 99
            if 0 < R < 5000 and res < 0.8 and np.hypot(*(Q[-1] - Q[0])) >= 1.0:          # 0.30: дуга с концом в начале — не дуга (SVG A без длины)
                ang = [math.atan2(q[1] - cy, q[0] - cx) for q in Q]
                tot = sum(((ang[m + 1] - ang[m] + math.pi) % (2 * math.pi)) - math.pi for m in range(len(ang) - 1))
                sweep = 1 if tot > 0 else 0; large = 1 if abs(tot) > math.pi else 0
                end = Q[-1]; cmds.append(f'A{R:.1f} {R:.1f} 0 {large} {sweep} {end[0]:.1f} {end[1]:.1f}'); arcs += 1; i = j; continue
        nxt = P[order[(i + 1) % n]]; cmds.append(f'L{nxt[0]:.1f} {nxt[1]:.1f}'); i += 1
    if cmds[-1].startswith('L'): cmds.pop()
    return ' '.join(cmds) + ' Z', arcs

def fit_arcs_open(P, T, tol=1.2):
    """ломаная px -> путь SVG: прямые участки (после упрощения 1 px) — линиями; подряд ≥ 5 коротких звеньев с одним знаком
    поворота и общим поворотом ≥ 15° — дугой A по окружности МНК (ошибка < tol, радиус ≤ 15 м)"""
    g = LineString(P).simplify(1.0); Q = np.array(g.coords); n = len(Q)
    if n < 6: return 'M' + ' L'.join(f'{x:.1f} {y:.1f}' for x, y in Q), 0
    E = np.diff(Q, axis=0); L = np.hypot(*E.T); cr = np.r_[E[:-1, 0] * E[1:, 1] - E[:-1, 1] * E[1:, 0], 0]
    out, arcs, i = [f'M{Q[0][0]:.1f} {Q[0][1]:.1f}'], 0, 0
    while i < n - 1:
        j = i
        while j < n - 1 and L[j] < 12.0 * T and (j == i or np.sign(cr[j - 1]) == np.sign(cr[j]) or abs(cr[j]) < 1e-3): j += 1
        if j - i >= 3:
            R_ = Q[i:j + 1]; A_ = np.c_[2 * R_, np.ones(len(R_))]; b = (R_ ** 2).sum(1); c = np.linalg.lstsq(A_, b, rcond=None)[0]
            cx, cy = c[0], c[1]; R = math.sqrt(max(c[2] + cx * cx + cy * cy, 0))
            res = np.abs(np.hypot(R_[:, 0] - cx, R_[:, 1] - cy) - R).max() if R > 0 else 99
            ang = [math.atan2(q[1] - cy, q[0] - cx) for q in R_]
            tot = sum(((ang[m + 1] - ang[m] + math.pi) % (2 * math.pi)) - math.pi for m in range(len(ang) - 1))
            if res < tol and 3 * T < R < 15 * 52.49 and abs(tot) >= math.radians(15) and np.hypot(*(R_[-1] - R_[0])) >= 1.0:
                out.append(f'A{R:.1f} {R:.1f} 0 {1 if abs(tot) > math.pi else 0} {1 if tot > 0 else 0} {R_[-1][0]:.1f} {R_[-1][1]:.1f}'); arcs += 1; i = j; continue
        out.append(f'L{Q[i + 1][0]:.1f} {Q[i + 1][1]:.1f}'); i += 1
    return ' '.join(out), arcs

def dominant_dirs(items, closed, ang=2.5, min_len=150.0):
    """К6: главные направления этажа — пики длины рёбер по углу (окно ±ang, период 180°), от самого длинного; каждый — не меньше
    min_len px суммарной длины. Лист с радиальными осями даёт свои направления, а не только оси листа (map/rules/40 §2.4)"""
    A, Wt = [], []
    for P, cl in zip(items, closed):
        n = len(P) - (1 if cl and np.allclose(P[0], P[-1]) else 0)
        for i in (range(n) if cl else range(n - 1)):
            d = P[(i + 1) % len(P)] - P[i]; L = float(np.hypot(*d))
            if L >= 3.0: A.append(math.degrees(math.atan2(d[1], d[0])) % 180.0); Wt.append(L)
    A, Wt = np.array(A), np.array(Wt); dirs = []
    if not len(A): return dirs
    rem = np.ones(len(A), bool); grid = np.arange(0, 180, 0.25)
    dd_ = lambda a0: np.abs((A - a0 + 90.0) % 180.0 - 90.0)
    while rem.any():
        w = np.array([Wt[rem & (dd_(a0) <= ang)].sum() for a0 in grid]); j = int(np.argmax(w))
        if w[j] < min_len: break
        mem = rem & (dd_(grid[j]) <= ang); th = np.radians(A[mem] * 2)
        m = (math.degrees(math.atan2((Wt[mem] * np.sin(th)).sum(), (Wt[mem] * np.cos(th)).sum())) / 2.0) % 180.0
        dirs.append(m); rem &= ~(dd_(m) <= ang); rem &= ~mem
    return dirs

def arc_edges(P, T):
    """рёбра дуг кольца (как fit_arcs: подряд ≥ 5 коротких рёбер одного знака поворота, окружность МНК < 0,8 px) — их не трогать"""
    n = len(P); out = np.zeros(n, bool)
    if n < 6: return out
    E = np.roll(P, -1, 0) - P; L = np.hypot(*E.T); En = np.roll(E, -1, 0); cr = E[:, 0] * En[:, 1] - E[:, 1] * En[:, 0]
    short = L < 3.0 * T; i = 0
    while i < n:
        j = i
        while j < n and short[j] and (j == i or np.sign(cr[j - 1]) == np.sign(cr[j]) or abs(cr[j]) < 1e-3): j += 1
        if j - i >= 5:
            Q = P[[m % n for m in range(i, j + 1)]]; A_ = np.c_[2 * Q, np.ones(len(Q))]; c = np.linalg.lstsq(A_, (Q ** 2).sum(1), rcond=None)[0]
            R = math.sqrt(max(c[2] + c[0] ** 2 + c[1] ** 2, 0))
            if 0 < R < 5000 and np.abs(np.hypot(Q[:, 0] - c[0], Q[:, 1] - c[1]) - R).max() < 0.8: out[i:j] = True
            i = j
        else: i += 1
    return out

def clean_ring(P, min_len, min_turn=0.6):
    """замкнутая ломаная: рёбра короче min_len — в середину, вершины с поворотом меньше min_turn° — убрать (до устойчивого)"""
    Q = np.array(P, float)
    if len(Q) > 1 and np.allclose(Q[0], Q[-1]): Q = Q[:-1]
    for _ in range(500):
        n = len(Q)
        if n < 4: break
        E = np.roll(Q, -1, 0) - Q; L = np.hypot(*E.T)
        i = int(np.argmin(L))
        if L[i] < min_len: Q[i] = (Q[i] + Q[(i + 1) % n]) / 2; Q = np.delete(Q, (i + 1) % n, axis=0); continue
        Ep = np.roll(E, 1, 0); cr = Ep[:, 0] * E[:, 1] - Ep[:, 1] * E[:, 0]; dt = (Ep * E).sum(1)
        tn = np.degrees(np.abs(np.arctan2(cr, dt))); j = int(np.argmin(tn))
        if tn[j] < min_turn: Q = np.delete(Q, j, axis=0); continue
        break
    return Q

def regularize(rings, lines, T=6.0, tol=1.5, ang=2.5, merge=0.5, min_dir=150.0, stat=None):
    """К6 (map/rules/40 §2.4): одна прямая стена — одна координата у всех контуров и линий.
    1) главные направления этажа (dominant_dirs); 2) рёбра в ±ang от направления — на него, кластер по смещению (кластер не шире tol);
    3) ступенька меньше T между параллельными рёбрами одного контура — та же стена: кластеры сливаются (смещение — по длине);
       излом от T и больше остаётся (map/rules/11 §3, «Что выпрямляется»); 4) вершина — пересечение прямых соседних рёбер;
    5) рёбра короче T вне дуг стягиваются, вершины на прямой убираются; 6) общие вершины соседей ближе 1 px — одна точка"""
    items = [np.array(r, float) for r in rings] + [np.array(l, float) for l in lines]
    closed = [True] * len(rings) + [False] * len(lines)
    items = [P[:-1] if cl and len(P) > 1 and np.allclose(P[0], P[-1]) else P for P, cl in zip(items, closed)]
    dirs = dominant_dirs(items, closed, ang, min_dir)
    U = [np.array([math.cos(math.radians(a)), math.sin(math.radians(a))]) for a in dirs]; Nn = [np.array([-u[1], u[0]]) for u in U]
    edges = {}                                         # (item, i) -> [dir, offset, length]
    for k_, (P, cl) in enumerate(zip(items, closed)):
        n = len(P)
        for i in (range(n) if cl else range(n - 1)):
            a, b = P[i], P[(i + 1) % n]; d = b - a; L = float(np.hypot(*d))
            if L < 1.0 or not dirs: continue
            an = math.degrees(math.atan2(d[1], d[0])) % 180.0
            dd = [abs((an - x + 90.0) % 180.0 - 90.0) for x in dirs]; j = int(np.argmin(dd))
            if dd[j] <= ang: edges[(k_, i)] = [j, float(Nn[j] @ ((a + b) / 2)), L]
    # кластеры по смещению внутри направления (union-find)
    keys = list(edges); par = {q: q for q in keys}
    def f(q):
        while par[q] != q: par[q] = par[par[q]]; q = par[q]
        return q
    for j in range(len(dirs)):
        E_ = sorted([q for q in keys if edges[q][0] == j], key=lambda q: edges[q][1]); grp = []
        for q in E_:
            if grp and edges[q][1] - edges[grp[-1][0]][1] <= tol: grp[-1].append(q)
            else: grp.append([q])
        for g in grp:
            for q in g[1:]: par[f(q)] = f(g[0])
    def cval():
        acc = collections.defaultdict(lambda: [0.0, 0.0])
        for q in keys: r_ = f(q); acc[r_][0] += edges[q][1] * edges[q][2]; acc[r_][1] += edges[q][2]
        return {r_: v[0] / v[1] for r_, v in acc.items()}
    cv = cval(); n_step = 0
    for k_, (P, cl) in enumerate(zip(items, closed)):                 # ступенька < T: соседние параллельные рёбра — одна стена
        n = len(P); m_ = n if cl else n - 1
        for i in range(m_):
            prv, nxt = (k_, (i - 1) % n), (k_, (i + 1) % n)
            cur = (k_, i)
            if cur in edges and prv in edges and edges[cur][0] == edges[prv][0] and (cl or i > 0):   # излом в ±ang — та же прямая стена
                ra, rb = f(prv), f(cur)
                if ra != rb and abs(cv[ra] - cv[rb]) < T: par[ra] = rb; n_step += 1; cv = cval()
            if not cl and (i == 0 or i + 1 >= m_): continue
            if prv not in edges or nxt not in edges: continue
            L = float(np.hypot(*(P[(i + 1) % n] - P[i])))
            if L >= 2 * T or edges[prv][0] != edges[nxt][0]: continue
            ra, rb = f(prv), f(nxt)
            if ra != rb and abs(cv[ra] - cv[rb]) < T: par[ra] = rb; n_step += 1; cv = cval()
    cv = cval()
    def line_of(q):
        if q not in edges: return None
        j = edges[q][0]; return U[j], Nn[j], cv[f(q)]
    def isect(l1, l2):
        u1, n1, c1 = l1; u2, n2, c2 = l2; A_ = np.array([n1, n2]); det = np.linalg.det(A_)
        if abs(det) < 1e-6: return None
        return np.linalg.solve(A_, np.array([c1, c2]))
    out, n_short = [], 0
    for k_, (P, cl) in enumerate(zip(items, closed)):                 # вершина — пересечение прямых соседних рёбер
        n = len(P); Q = P.copy()
        for i in range(n):
            lin = [line_of((k_, (i - 1) % n)) if (cl or i > 0) else None, line_of((k_, i)) if (cl or i < n - 1) else None]
            lin = [z for z in lin if z is not None]
            if len(lin) == 2 and abs(lin[0][1] @ lin[1][0]) > 1e-3:
                x = isect(*lin)
                if x is not None and np.hypot(*(x - P[i])) <= max(3.0, T): Q[i] = x; continue
            if lin:
                u_, n_, c_ = lin[-1]; Q[i] = P[i] + n_ * (c_ - n_ @ P[i])
        out.append(Q)
    # общие вершины всех контуров и линий — один граф: вершины ближе 1 px — одна точка; ребро короче T (не дуга) стягивается
    # в одну вершину для всех контуров сразу — у соседей не расходится общая стена (Ч-07, Ч-14)
    from scipy.spatial import cKDTree
    sizes = [len(Q) for Q in out]; allv = np.vstack([Q for Q in out if len(Q)]) if any(sizes) else np.zeros((0, 2))
    if not len(allv):
        if stat is not None: stat.update(направлений=[round(x, 2) for x in dirs], ступенек_слито=n_step, коротких_стянуто=0)
        return [None] * len(rings), [None] * len(lines)
    pr = list(range(len(allv)))
    def g(i):
        while pr[i] != i: pr[i] = pr[pr[i]]; i = pr[i]
        return i
    for i, j in cKDTree(allv).query_pairs(min(2.5, T / 2)): pr[g(i)] = g(j)       # одна вершина стыка: ближе T/2 (до 2,5 px)
    grp = collections.defaultdict(list)
    for i in range(len(allv)): grp[g(i)].append(i)
    pos = {r_: allv[v].mean(0) for r_, v in grp.items()}
    ids, o = [], 0
    for sz in sizes: ids.append([g(i) for i in range(o, o + sz)]); o += sz
    def ring_ids(I, cl):
        J = [x for t_, x in enumerate(I) if t_ == 0 or x != I[t_ - 1]]
        if cl and len(J) > 1 and J[0] == J[-1]: J = J[:-1]
        return J
    prot = set()                                                   # рёбра дуг (по контуру до стягивания) — не трогать
    for I, cl in zip(ids, closed):
        if not cl: continue
        J = ring_ids(I, True)
        if len(J) < 6: continue
        ae = arc_edges(np.array([pos[x] for x in J]), T)
        prot |= {frozenset((J[t_], J[(t_ + 1) % len(J)])) for t_ in range(len(J)) if ae[t_]}
    for _ in range(50):
        nb = collections.defaultdict(set)
        for I, cl in zip(ids, closed):
            J = [g(x) for x in I]; J = ring_ids(J, cl)
            m_ = len(J) if cl else len(J) - 1
            for t_ in range(max(m_, 0)): a_, b_ = J[t_], J[(t_ + 1) % len(J)]; nb[a_].add(b_); nb[b_].add(a_)
        E_ = sorted({frozenset((a_, b_)) for a_ in nb for b_ in nb[a_] if a_ != b_}, key=lambda e: np.hypot(*(pos[min(e)] - pos[max(e)])))
        done = set(); changed = False
        for e in E_:
            a_, b_ = sorted(e)
            if a_ in done or b_ in done or e in prot: continue
            if np.hypot(*(pos[a_] - pos[b_])) >= T: break
            da, db = len(nb[a_]), len(nb[b_])
            keep, gone = (a_, b_) if da >= db else (b_, a_)
            pos[keep] = pos[keep] if da != db else (pos[a_] + pos[b_]) / 2
            pr[gone] = keep; done |= {a_, b_}; n_short += 1; changed = True
        if not changed: break
    # фаска: косое ребро от T до 0,8 м (не по главному направлению) между двумя рёбрами, обе вершины — без примыканий (по два соседа):
    # вершины — в пересечение прямых соседних рёбер, если оно ближе длины ребра (map/rules/40 §2.4; Ч-32, Ч-08)
    n_ch = 0
    for _ in range(3):
        nb = collections.defaultdict(set)
        for I, cl in zip(ids, closed):
            J = ring_ids([g(x) for x in I], cl); m_ = len(J) if cl else len(J) - 1
            for t_ in range(max(m_, 0)): a_, b_ = J[t_], J[(t_ + 1) % len(J)]; nb[a_].add(b_); nb[b_].add(a_)
        done = set(); ch = 0
        for a_ in list(nb):
            for b_ in list(nb[a_]):
                if a_ >= b_ or a_ in done or b_ in done or len(nb[a_]) != 2 or len(nb[b_]) != 2: continue
                d_ = pos[b_] - pos[a_]; L = float(np.hypot(*d_))
                if not (T <= L < min_dir / 3.0 * 0.8): continue            # min_dir = 3 м в px -> 0,8 м
                an = math.degrees(math.atan2(d_[1], d_[0])) % 180.0
                if dirs and min(abs((an - x + 90.0) % 180.0 - 90.0) for x in dirs) <= ang: continue
                pa = next(iter(nb[a_] - {b_}), None); pb = next(iter(nb[b_] - {a_}), None)
                if pa is None or pb is None: continue
                u1, u2 = pos[a_] - pos[pa], pos[pb] - pos[b_]; A_ = np.array([[u1[0], -u2[0]], [u1[1], -u2[1]]])
                if abs(np.linalg.det(A_)) < 1e-6: continue
                s_ = np.linalg.solve(A_, pos[b_] - pos[pa]); x = pos[pa] + u1 * s_[0]
                if s_[0] <= 0 or np.hypot(*(x - (pos[a_] + pos[b_]) / 2)) > L: continue
                pos[a_] = x; pr[b_] = a_; done |= {a_, b_}; ch += 1
        n_ch += ch
        if not ch: break
    if stat is not None: stat['фасок_снято'] = n_ch
    # Т-узел: вершина ближе 1,5 px к ребру другого контура (не его конец) — на это ребро, иначе у соседей клин (Ч-14)
    from shapely.strtree import STRtree as _ST
    segs_, own_ = [], []
    for k_, (I, cl) in enumerate(zip(ids, closed)):
        J = ring_ids([g(x) for x in I], cl); m_ = len(J) if cl else len(J) - 1
        for t_ in range(max(m_, 0)): segs_.append((J[t_], J[(t_ + 1) % len(J)])); own_.append(k_)
    geo_ = [LineString([pos[a_], pos[b_]]) for a_, b_ in segs_]; n_tn = 0; tn_tol = 1.5          # Т-узел: ближе 1,5 px — на ребро
    if geo_:
        st_ = _ST(geo_)
        for v_ in list({g(x) for I in ids for x in I}):
            pv = Point(pos[v_]); best_ = None
            for j_ in st_.query(pv.buffer(tn_tol)):
                a_, b_ = segs_[int(j_)]
                if v_ in (a_, b_): continue
                dd_ = geo_[int(j_)].distance(pv)
                if dd_ < tn_tol and (best_ is None or dd_ < best_[0]): best_ = (dd_, a_, b_)
            if best_ is not None and best_[0] > 1e-6:
                A_, B_ = pos[best_[1]], pos[best_[2]]; u_ = B_ - A_; Lu = float(u_ @ u_)
                if Lu > 1e-9:
                    t_ = float((pos[v_] - A_) @ u_) / Lu
                    if 0.0 < t_ < 1.0: pos[v_] = A_ + u_ * t_; n_tn += 1
    if stat is not None: stat['т_узлов_на_ребро'] = n_tn
    res = []
    for I, cl in zip(ids, closed):
        J = ring_ids([g(x) for x in I], cl); Q = np.array([pos[x] for x in J]) if J else np.zeros((0, 2))
        for _ in range(20):                                        # вершины на прямой (отклонение < merge px) — убрать
            n = len(Q)
            if n < (4 if cl else 3): break
            drop = None
            for i in (range(n) if cl else range(1, n - 1)):
                a, b, c = Q[i - 1], Q[i], Q[(i + 1) % n]; L = np.hypot(*(c - a))
                if L > 1e-6 and abs((c - a)[0] * (b - a)[1] - (c - a)[1] * (b - a)[0]) / L < merge and (b - a) @ (c - b) > 0: drop = i; break
            if drop is None: break
            Q = np.delete(Q, drop, axis=0)
        if not cl and J:                                           # свободный конец линии (вершина одного ребра): последнее ребро короче T — по прямой соседнего
            for end in (0, 1):
                if len(nb.get(J[-1] if end else J[0], ())) > 1: continue
                while len(Q) >= 3:
                    A_, B_, C_ = (Q[-1], Q[-2], Q[-3]) if end else (Q[0], Q[1], Q[2])
                    if np.hypot(*(A_ - B_)) >= T: break
                    u_ = B_ - C_; Lu = np.hypot(*u_)
                    nb_ = C_ + u_ * (((A_ - C_) @ u_) / (Lu * Lu)) if Lu > 1e-6 else B_
                    if end: Q = np.vstack([Q[:-2], nb_])
                    else: Q = np.vstack([nb_, Q[2:]])
                    n_short += 1
        res.append(Q)
    out = res
    if stat is not None: stat.update(направлений=[round(x, 2) for x in dirs], ступенек_слито=n_step, коротких_стянуто=n_short)
    res = []
    for Q, cl in zip(out, closed):
        if cl:
            if len(Q) < 3: res.append(None); continue
            res.append(poly_main(Polygon(Q).buffer(0)))
        else:
            res.append(LineString(Q) if len(Q) >= 2 else None)
    return res[:len(rings)], res[len(rings):]

def column_box(cml, cl, cst, B, pxm, k, T, clad_max_m=0.15):
    """0.31 (К-7; №89, map/rules/50 §1, map/rules/11 §4): короб колонны у стены — колонна (метка cl растра cml) и её обшивка.
    Ядро — колонна и замкнутые пустоты у неё (пустоты короба у торцов пилона) не больше 2 площадей колонны + 1 м²; толщина обшивки c —
    кольца вокруг ядра, пока тело стены B занимает в кольце не меньше половины (не дальше clad_max_m); короб — прямоугольник ядра (ядро
    ≥ 85 % своего прямоугольника) или само ядро, расширенные на c. Выступ — от полос стен, примыкающих к коробу (стена вытянута ≥ 1,5 раза,
    толщина — короткая сторона): видна отдельным объектом, если выступ ≥ толщины стены. -> dict(box — px карты, выступ и толщина — м) | None"""
    x, y, w, h = [int(v) for v in cst[cl][:4]]; pad = int(1.5 * pxm * k)
    X0, Y0, X1, Y1 = max(0, x - pad), max(0, y - pad), min(cml.shape[1], x + w + pad), min(cml.shape[0], y + h + pad)
    cm = cml[Y0:Y1, X0:X1] == cl
    if not cm.any(): return None
    Bw = (B[Y0:Y1, X0:X1] > 0) & ~cm
    fr = ~(Bw | cm); lab_, n_ = ndimage.label(fr)
    border = set(np.unique(np.r_[lab_[0], lab_[-1], lab_[:, 0], lab_[:, -1]]).tolist())
    near = cv2.dilate(cm.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0; core = cm.copy(); lim = 2 * cm.sum() + (pxm * k) ** 2
    for l in np.unique(lab_[near & fr]).tolist():
        if l == 0 or l in border: continue
        m = lab_ == l
        if m.sum() <= lim: core |= m
    dt = ndimage.distance_transform_edt(~core); c = 0
    for d in range(1, int(round(clad_max_m * pxm * k)) + 1):                 # толщина обшивки: кольцо, где тело стены — больше половины
        ring = (dt > d - 1) & (dt <= d)
        if not ring.any() or Bw[ring].mean() < 0.5: break
        c = d
    cc, _ = cv2.findContours(core.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not cc: return None
    cp = Polygon(max(cc, key=cv2.contourArea)[:, 0, :].astype(float) + 0.5).buffer(0)
    if cp.is_empty or cp.geom_type != 'Polygon': return None
    mr = cp.minimum_rotated_rectangle; rect = cp.area >= 0.85 * mr.area; base = mr if rect else cp
    box = base.buffer(c, join_style=2) if c else base
    fillb = lambda g: (lambda m: (cv2.fillPoly(m, [np.round(np.array(g.exterior.coords) * 8).astype(np.int32)], 1, shift=3), m)[1])(np.zeros(Bw.shape, np.uint8))
    bm = fillb(box)
    if rect:                                                                   # торцевые стенки короба толще обшивки: тело в 0,12 м за контуром — в короб
        dtb = ndimage.distance_transform_edt(bm == 0); ys, xs = np.nonzero(Bw & (dtb <= 0.12 * pxm * k))
        if len(xs): box = MultiPoint(list(box.exterior.coords) + [(x_ + 0.5, y_ + 0.5) for x_, y_ in zip(xs, ys)]).minimum_rotated_rectangle; bm = fillb(box)
    dtb = ndimage.distance_transform_edt(bm == 0)                              # стены у короба: тело в 0,15–0,55 м от короба — по компонентам
    st_ = ((dtb > 0.15 * pxm * k) & (dtb <= 0.55 * pxm * k) & Bw).astype(np.uint8); n2, lab2, s2, _ = cv2.connectedComponentsWithStats(st_, connectivity=8)
    bands, thick = [], []
    for i in range(1, n2):
        if s2[i, 4] < 0.01 * (pxm * k) ** 2: continue
        ys, xs = np.nonzero(lab2 == i); X = np.c_[xs, ys].astype(float); cq = X.mean(0)
        ev, evec = np.linalg.eigh(np.cov((X - cq).T)); u = evec[:, 1]; n_ = evec[:, 0]   # главные оси: u — вдоль стены
        a_, b_ = np.percentile((X - cq) @ u, [5, 95]), np.percentile((X - cq) @ n_, [5, 95]); L_, t_ = a_[1] - a_[0], b_[1] - b_[0]
        if t_ <= 0 or L_ < 1.5 * t_ or t_ > 0.5 * pxm * k: continue               # не вытянутое или толще 0,5 м — не стена
        c0 = cq + n_ * (b_[0] + b_[1]) / 2
        bands.append(LineString([tuple(c0 - u * 1e5), tuple(c0 + u * 1e5)]).buffer(t_ / 2, cap_style=2)); thick.append(t_)
    if bands:
        tw = float(np.median(thick)); bu = unary_union(bands); rest = box.difference(bu)
        prot = max([bu.distance(Point(v)) for g in getattr(rest, 'geoms', [rest]) if g.geom_type == 'Polygon' for v in g.exterior.coords] or [0.0])
    else:
        tw = T * k; s_ = sorted(np.hypot(*np.diff(np.array(mr.exterior.coords)[:3], axis=0).T)); prot = (s_[0] + 2 * c - tw) / 2
    bmr = box.minimum_rotated_rectangle; S_ = min(np.hypot(*np.diff(np.array(bmr.exterior.coords)[:3], axis=0).T)) if bmr.geom_type == 'Polygon' else 0.0
    poly = affinity.translate(box, X0, Y0); poly = affinity.scale(poly, 1.0 / k, 1.0 / k, origin=(0, 0))
    vis = prot >= tw - 1.0 or S_ >= 3 * tw                                    # выступ от полос стен ≥ толщины или короб втрое шире стены (выступ по обе стороны ≥ толщины)
    return dict(box=poly, prot_m=prot / (pxm * k), t_m=tw / (pxm * k), clad_m=c / (pxm * k), S_m=S_ / (pxm * k), visible=bool(vis), walls=len(bands),
                why='выступ' if prot >= tw - 1.0 else 'ширина ≥ 3 толщин стены' if vis else 'скрыта в стене')

def room_type(name):
    for pat, t in NAME_TYPE:
        if re.search(pat, name, re.I): return t
    return 'other'

def poly_main(g):
    if g is None or g.is_empty: return None
    if g.geom_type == 'Polygon': return g
    ps = [q for q in getattr(g, 'geoms', []) if q.geom_type == 'Polygon']
    return max(ps, key=lambda q: q.area) if ps else None

def union2(p, q): return poly_main(unary_union([p.buffer(0.05, join_style=2), q.buffer(0.05, join_style=2)]).buffer(-0.05, join_style=2))

def core_join(main, part, q, Mi):
    """v012, решение владельца 14.10.2026 (№104): часть ядра `part` (лифт внутри блока ядра), отрезанная от главной грани ядра `main` помещением
    с номером `q`, вырезанным в массиве, — соединить с главной гранью телом массива. Mi — массив, сжатый на T/2 (линия стены помещения — внутри
    массива, край линии — на грани штриховки, map/rules/40 §2.10). Помещение q отдаёт ядру куски своей грани, лежащие в Mi, по одному, пока ядро
    растёт одной гранью и без нового кольца (помещение с номером ядром не обводится). -> (новая грань ядра, новая грань q) | None"""
    q_core = poly_main(q.difference(Mi))
    if q_core is None or q_core.area < 0.5 * q.area: return None
    rest = q.difference(q_core)
    acc = unary_union([main, part]); got = []; nh = len(main.interiors) + len(part.interiors)
    left = [g_ for g_ in getattr(rest, 'geoms', [rest]) if g_.geom_type == 'Polygon' and g_.area >= 0.5]
    grown = True
    while grown and left:
        grown = False
        for g_ in sorted(left, key=lambda z: -z.area):
            if g_.distance(acc) > 0.1: continue
            cand = unary_union([acc, g_]).buffer(0.05, join_style=2).buffer(-0.05, join_style=2)
            if cand.geom_type == 'Polygon' and len(cand.interiors) > nh: continue
            acc = cand; got.append(g_); left.remove(g_); grown = True
    if acc.geom_type != 'Polygon' or not acc.is_valid or not got: return None
    give = unary_union(got); q_new = poly_main(q.difference(give))
    if q_new is None or abs(q_new.area + give.area - q.area) > 0.01 * q.area: return None
    return acc, q_new

# ------------------------------------------------------------------ основной ход
def convert(a):
    T, k, pxm = a.T, a.k, a.px_per_m
    cfg = json.load(open(a.cfg, encoding='utf-8')) if getattr(a, 'cfg', None) else {}   # 0.33: настройка клиента (словарь надписей ПК и пр.)
    D = read_dxf(a.dxf, pk_labels=tuple(cfg.get('pk_labels', PK_LABELS))); M, t = frame_of(D, pxm, a.frame)
    allp = extent_pts(D) @ M.T + t
    W, H = (tuple(map(int, a.size.split(','))) if a.size else (int(allp[:, 0].max() + 100), int(allp[:, 1].max() + 100)))
    C = Canvas(W, H, M, t, k)
    rep = collections.OrderedDict(version=VERSION, dxf=a.dxf, px_per_m=pxm, T=T)
    rep['вход'] = {key: len(v) for key, v in D.items() if not key.startswith('_')}
    rep['классы_по_xdata'] = D['_xdata'] or 'XDATA UNSPOT нет — классы по коду элемента ISO, как 0.32'   # 0.33 (КМ-1)
    rep['неизвестный_type'] = D['_unknown']
    stops = []                                                     # К7 и 0.33: СТОП с местом — код выхода 3
    for u_ in D['_unknown']:                                       # 0.33 (КМ-1): неизвестный type — громко, не молча «лёгкая линия»
        stops.append(dict(что=f"неизвестный type XDATA UNSPOT «{u_['type']}» на слое {u_['слой']} ({u_['объектов']} объектов) — дополнить TYPE_CLASS моста", x=None, y=None))
    kc = lambda mm: np.ones((max(3, int(round(mm / 1000 * pxm * k))) | 1,) * 2, np.uint8)
    # ---- тела по классам (растр k)
    ext, inn, gl, lt, fg = C.img(), C.img(), C.img(), C.img(), C.img()
    for rings in D['ext']: C.fill(ext, rings)
    for rings in D['int']: C.fill(inn, rings)
    # 0.30: колонна (28) и её обшивка — тело стены вокруг (map/rules/11 §4, AutoCAD-лист: «обшивку колонн — по близости к заливкам колонн»):
    # отдельно стоящая (связная часть тел с колонной не больше 2,6 м) — колонна, не стена; у стены — сплошное тело без петли
    # 0.31 (К-7; №89, строка 195): колонна или короб её обшивки у стены, видные на листе отдельным объектом (выступают из граней стены на её
    # толщину и больше), — колонной: контур короба поверх стены — стена по сторонам кончается на гранях короба; скрытая в стене — часть стены;
    # однотипные — одним решением. Геометрия стен и помещений — как 0.30 (колонна у стены — в теле стены; К6 этажа тот же): короб только
    # рисуется, пустоты короба снимаются после К6 (как петля обшивки). Колонна без заливки 28 (лист Revit: двутавр, круглая — линиями блока 28) —
    # выпуклая оболочка блока; стены она не меняет (0.30 её не видел), только рисуется (map/rules/11 §4).
    colm = C.img(); col_free = []; n_col_wall = 0; col_boxes, col_hidden, col_src, blk_free = [], [], [], []
    for i_, R in enumerate(D['col_h']):
        C.fill(colm, R); col_src += [dict(kind='hatch', key=i_, mm=Polygon(P).buffer(0)) for P in R if len(P) >= 3]
    hatched = unary_union([q['mm'] for q in col_src]) if col_src else Polygon(); colb = C.img(); n_blk = 0
    n_blk_h = 0
    for nm, segs, hr in D['col']:                                   # 0.32 (ПК4-К12): у блока есть заливка 28 — колонна по заливке (символ листа), иначе — по линиям
        Q = np.vstack(hr) if hr else np.vstack(segs)
        if len(Q) < 3: continue
        hull = MultiPoint([tuple(p) for p in Q]).convex_hull
        if hull.geom_type != 'Polygon' or hull.area <= 0 or max(np.ptp(Q, axis=0)) > 2600: continue
        if not hatched.is_empty and hull.intersection(hatched).area >= 0.5 * hull.area: continue   # у колонны есть заливка 28
        C.fill(colb, [np.array(hull.exterior.coords)]); n_blk += 1; n_blk_h += bool(hr); col_src.append(dict(kind='block', key=nm, mm=hull))
    for q in col_src:
        mr_ = q['mm'].minimum_rotated_rectangle; sd = sorted(np.hypot(*np.diff(np.array(mr_.exterior.coords)[:3], axis=0).T)) if mr_.geom_type == 'Polygon' else [0, 0]
        q['type'] = re.sub(r'[_\s-]*\d+$', '', str(q['key'])) if q['kind'] == 'block' else f'28 {round(sd[0] / 100) / 10:.1f}×{round(sd[1] / 100) / 10:.1f} м'
        q['px'] = Polygon(C.px(np.array(q['mm'].exterior.coords))).buffer(0)
    Bwall = np.maximum(ext, inn)                                    # тело стен до колонн — для коробов
    lim = 2.6 * pxm * k
    if colm.any():
        cold = cv2.dilate(colm, kc(300))
        bt = (np.maximum(np.maximum(ext, inn), cold) > 0).astype(np.uint8)
        ncc, lab, stt, _ = cv2.connectedComponentsWithStats(bt, connectivity=8); del bt
        ncm, cml, cst, _ = cv2.connectedComponentsWithStats((colm > 0).astype(np.uint8), connectivity=8)
        hit = np.unique(lab[colm > 0]); hit = hit[hit > 0]
        for j in hit.tolist():
            x0, y0, w0, h0 = stt[j][:4]; sub = lab[y0:y0 + h0, x0:x0 + w0] == j
            if max(w0, h0) <= lim:
                for img in (ext, inn): img[y0:y0 + h0, x0:x0 + w0][sub] = 0
                cn_, _ = cv2.findContours(sub.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                if cn_:
                    c_ = max(cn_, key=cv2.contourArea)[:, 0, :].astype(float)
                    if len(c_) >= 3: col_free.append(Polygon((c_ + (x0, y0) + 0.5) / k).buffer(0))
            else:
                w_ = inn[y0:y0 + h0, x0:x0 + w0]; w_[sub & (cold[y0:y0 + h0, x0:x0 + w0] > 0)] = 255; n_col_wall += 1   # как 0.30: колонна у стены — в теле стены
                for cl in np.unique(cml[y0:y0 + h0, x0:x0 + w0][sub & (colm[y0:y0 + h0, x0:x0 + w0] > 0)]).tolist():
                    if cl == 0: continue
                    bx = column_box(cml, cl, cst, Bwall, pxm, k, T)
                    (col_boxes if bx is not None and bx['visible'] else col_hidden).append(bx if bx is not None and bx['visible'] else dict(box=bx))
        del lab
    if colb.any():                                                  # колонны-блоки без заливки: свободная — оболочкой, у стены — коробом или скрыта
        nbm, bml, bst, _ = cv2.connectedComponentsWithStats((colb > 0).astype(np.uint8), connectivity=8)
        near_w = cv2.dilate((Bwall > 0).astype(np.uint8), kc(300))
        for cl in range(1, nbm):
            x0, y0, w0, h0 = [int(v) for v in bst[cl][:4]]; mb = bml[y0:y0 + h0, x0:x0 + w0] == cl
            if not (near_w[y0:y0 + h0, x0:x0 + w0][mb] > 0).any():
                cn_, _ = cv2.findContours(mb.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                if cn_: blk_free.append(Polygon((max(cn_, key=cv2.contourArea)[:, 0, :].astype(float) + (x0, y0) + 0.5) / k).buffer(0))
                continue
            bx = column_box(bml, cl, bst, Bwall, pxm, k, T)
            (col_boxes if bx is not None and bx['visible'] else col_hidden).append(bx if bx is not None and bx['visible'] else dict(box=bx))
    # однотипные колонны этажа — одним решением (№89: «нарисована одна — нарисованы все»): тип — имя блока без номера или размер заливки 28
    drawn_u = unary_union(col_free + blk_free + [b['box'] for b in col_boxes]) if (col_free or blk_free or col_boxes) else Polygon()
    for q in col_src: q['drawn'] = (not drawn_u.is_empty) and q['px'].intersection(drawn_u).area >= 0.5 * q['px'].area
    types_drawn = {q['type'] for q in col_src if q['drawn']}; col_unif = [q for q in col_src if not q['drawn'] and q['type'] in types_drawn]
    rep['колонны'] = dict(отдельно_стоящих=len(col_free) + len(blk_free), в_стенах=n_col_wall, коробом_у_стены=len(col_boxes), скрыто_в_стене=len(col_hidden) - len(col_unif),
                          из_блоков_без_заливки=n_blk - n_blk_h, из_блоков_по_заливке_внутри=n_blk_h, однотипных_дорисовано=len(col_unif),
                          типы={t_: sum(1 for q in col_src if q['type'] == t_) for t_ in sorted({q['type'] for q in col_src})},
                          короба=[dict(x=round(b['box'].centroid.x), y=round(b['box'].centroid.y), выступ_м=round(b['prot_m'], 2), стена_м=round(b['t_m'], 2),
                                       ширина_м=round(b['S_m'], 2), обшивка_м=round(b['clad_m'], 2), стен=b['walls'], почему=b['why']) for b in col_boxes],
                          скрытые=[dict(x=round(h_['box']['box'].centroid.x), y=round(h_['box']['box'].centroid.y), выступ_м=round(h_['box']['prot_m'], 2),
                                        стена_м=round(h_['box']['t_m'], 2), ширина_м=round(h_['box']['S_m'], 2)) for h_ in col_hidden if h_['box'] is not None])
    # 0.30: массив и стены одной линией (лист AutoCAD; ядро — «контуры блоков линиями», строка 150)
    sol_u = [g for g in (Polygon(P).buffer(0) for cls in ('ext', 'int') for R in D[cls] for P in R) if not g.is_empty]
    sol_t = STRtree(sol_u) if sol_u else None                          # тела SOLID, мм: узор на теле — его штриховка, не массив
    tk = max(3, int(round(T * k))); massif_polys, n_massif = [], 0
    for wr, R in D['massif']:
        for P in R:
            g = Polygon(P).buffer(0)
            if g.is_empty or g.area <= 0: continue
            cov = sum(g.intersection(sol_u[int(j)].buffer(50)).area for j in sol_t.query(g)) / g.area if sol_t is not None else 0.0
            if cov > 0.5: continue                                       # узор по телу SOLID — не массив
            m, (y0, y1, x0, x1) = C.win_fill(P, tk + 2)
            if not (m > 0).any(): continue
            band = cv2.bitwise_and(m, cv2.bitwise_not(cv2.erode(m, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * tk + 1, 2 * tk + 1)))))
            img = ext if wr == 'ext' else inn
            img[y0:y1, x0:x1] = np.maximum(img[y0:y1, x0:x1], band); n_massif += 1
            massif_polys.append(Polygon(P).buffer(0))
    cov_d = cv2.dilate(np.maximum(ext, inn), np.ones((4 * k + 1,) * 2, np.uint8))     # покрытое телом ±2 px
    n_wl, wl_m = 0, 0.0
    for wr, segs in D['wline']:
        for P in segs:
            Q = C.px(P); Lc = np.r_[0, np.cumsum(np.hypot(*np.diff(Q, axis=0).T))]
            if Lc[-1] < T: continue
            s = np.arange(0, Lc[-1] + 0.25, 0.5); X = np.c_[np.interp(s, Lc, Q[:, 0]), np.interp(s, Lc, Q[:, 1])]
            out_ = np.array([C.at(cov_d, x) == 0 for x in X]); idx = np.flatnonzero(out_)
            if not len(idx): continue
            for run in np.split(idx, np.flatnonzero(np.diff(idx) > 1) + 1):
                if s[run[-1]] - s[run[0]] < T: continue
                i0, i1 = max(run[0] - 6, 0), min(run[-1] + 6, len(X) - 1)             # +3 px: стык с телом без щели
                img, w = (ext, 2 * T) if wr == 'ext' else (inn, T)
                cv2.polylines(img, [C.q(X[i0:i1 + 1])], False, 255, max(1, int(round(w * k))), shift=3); n_wl += 1; wl_m += s[i1] - s[i0]
            if np.allclose(P[0], P[-1]) and len(P) >= 4 and out_.mean() > 0.5: massif_polys.append(Polygon(P).buffer(0))   # замкнутый контур блока
    rep['стены_линией'] = dict(массивов=n_massif, кусков=n_wl, м=round(wl_m / pxm, 1))
    glh = C.img()                                                  # стекло перегородок заливкой (22G SOLID) — тело стекла
    for R in D['glass_h']: C.fill(glh, R)
    gl = np.maximum(gl, glh)
    for key, img in (('glass', gl), ('light', lt), ('fglass', fg)):
        for nm, segs in D[key]:
            for P in segs: C.line(img, P, 1.0)
    if D['glass_h']: lt[cv2.dilate(glh, np.ones((4 * k + 1,) * 2, np.uint8)) > 0] = 0   # линии 22G по стеклу — его контур, не лёгкая перегородка
    for R in D['fglass_h']: C.fill(fg, R)
    for R in D['mullion']: C.fill(fg, [R])                         # 0.33 (КМ-1): стойки витража — тело витража (план 012/013 без SOLID 31)
    gl = cv2.morphologyEx(gl, cv2.MORPH_CLOSE, kc(160))
    lt = cv2.morphologyEx(lt, cv2.MORPH_CLOSE, kc(160))
    fg = cv2.morphologyEx(fg, cv2.MORPH_CLOSE, kc(260))
    lf = C.img(); lift_in_block = 0                                # шахты лифтов: выпуклая оболочка блока A-66
    mtree = STRtree(massif_polys) if massif_polys else None
    for nm, segs in D['lift']:
        Pm = np.vstack(segs)
        if mtree is not None:                                      # 0.30: лифт внутри замкнутого блока ядра — шахта уже в стенах
            cpt = Point(*Pm.mean(0))
            if any(massif_polys[int(j)].contains(cpt) for j in mtree.query(cpt)): lift_in_block += 1; continue
        Q = np.vstack([C.px(P) for P in segs])
        if len(Q) >= 3:
            hl = cv2.convexHull(Q.astype(np.float32))[:, 0, :]; cv2.polylines(lf, [C.q(hl)], True, 255, max(1, k), shift=3)
    rep['лифтов_в_блоке_ядра'] = lift_in_block
    inn = np.maximum(inn, lf)
    body = np.maximum.reduce([ext, inn, gl, lt, fg])
    # ---- двери: проём заливается сечением стены у косяков (двери закрыты)
    dr = C.img(); doors, door_fail = [], []
    body_d2 = cv2.dilate(body, np.ones((2 * k + 1, 2 * k + 1), np.uint8))      # тело ±2 px — для проверки «стена продолжает проём»
    door_why = {}                                                   # 0.33 (КМ-1): дверь плана, не ставшая проёмом карты, -> причина
    for di_, item in enumerate(D['door']):
        nm, segs = item['nm'], item['segs']; S = [C.px(P) for P in segs]; best = None
        if item.get('rect') is not None:                            # 0.33 (КМ-1, КМ-9, П3-13): прямоугольник проёма Э7д — от косяка до косяка, обе створки
            R_ = C.px(item['rect']); mr_ = Polygon(R_).buffer(0).minimum_rotated_rectangle
            if mr_.geom_type == 'Polygon':
                cs = np.array(mr_.exterior.coords)[:4]; e1, e2 = cs[1] - cs[0], cs[2] - cs[1]
                if np.hypot(*e1) < np.hypot(*e2): e1, e2 = e2, e1
                L = float(np.hypot(*e1)); u = e1 / max(L, 1e-9); n = np.array([-u[1], u[0]]); c_ = cs.mean(0); dpt = float(np.hypot(*e2))
                h, e_ = c_ - u * L / 2, c_ + u * L / 2
                sc = [wall_section(body, C, p, n) for p in (h - u * 3.0, e_ + u * 3.0)]
                ok = [x_ for x_ in sc if x_ and x_ != 'corner']
                n0, n1 = (min(x_[0] for x_ in ok), max(x_[1] for x_ in ok)) if ok else (-max(dpt, T) / 2, max(dpt, T) / 2)
                if n1 - n0 > 40: door_fail.append(nm); door_why[di_] = 'не разобрано: сечение стены у косяков толще 40 px'; continue
                C.fill_px(dr, np.array([h - u * 1.5 + n * n0, e_ + u * 1.5 + n * n0, e_ + u * 1.5 + n * n1, h - u * 1.5 + n * n1]))
                axis_off = (n0 + n1) / 2
                doors.append(dict(name=nm, a=h + n * axis_off, b=e_ + n * axis_off, thick=n1 - n0, kind='door', src=di_, how='прямоугольник',
                                  ext=C.at(ext, h - u * 3 + n * axis_off) > 0 or C.at(ext, e_ + u * 3 + n * axis_off) > 0))
                continue
        cands = door_opening(S, pxm)
        for prior, h, e_, L in cands:
            u = (e_ - h) / L; n = np.array([-u[1], u[0]])
            sc = [wall_section(body, C, p, n) for p in (h - u * 3.0, e_ + u * 3.0)]
            if not any(sc): continue
            jambs = sum(1 for x_ in sc if x_)
            ok = [x_ for x_ in sc if x_ and x_ != 'corner']
            n0_, n1_ = (min(x_[0] for x_ in ok), max(x_[1] for x_ in ok)) if ok else (-T / 2, T / 2)
            ax = (n0_ + n1_) / 2; ss = np.linspace(0.1 * L, 0.9 * L, 17)
            free = np.mean([C.at(body, h + u * q + n * ax) == 0 for q in ss])        # проём — разрыв тела по оси
            same = 0.0
            if len(ok) == 2:                                                       # у проёма косяки — одна стена
                a0, a1 = ok; inter = min(a0[1], a1[1]) - max(a0[0], a1[0]); uni = max(a0[1], a1[1]) - min(a0[0], a1[0])
                same = max(inter, 0) / max(uni, 1e-6)
            wd, an = wall_dir(body, C, h - u * 6.0)
            par = abs(float(wd @ u)) * an if wd is not None else 0.0
            # стена продолжает проём: за концом и за петлёй по линии проёма тело стены (±2 px); у полотна там пусто
            bd = body_d2
            beyond = np.mean([C.at(bd, e_ + u * q) > 0 for q in np.arange(2.0, 20.0, 1.0)])
            behind = np.mean([C.at(bd, h - u * q) > 0 for q in np.arange(2.0, 20.0, 1.0)])
            score = prior + jambs + 2.0 * same + 0.5 * free + 0.5 * par + 2.5 * beyond + 1.0 * behind
            if best is None or score > best[0]: best = (score, h, e_, L, ok if ok else [(-T / 2, T / 2)])
        if best is None: door_fail.append(nm); door_why[di_] = 'не разобрано: полотна и дуги створки не найдено'; continue
        _, h, e_, L, secs = best; u = (e_ - h) / L; n = np.array([-u[1], u[0]])
        # 0.33 (КМ-9, П3-13): вторая створка того же блока — петля у другого косяка, закрытые створки сходятся: проём от косяка до косяка
        merged = False
        for prior2, h2, e2_, L2 in cands:
            if np.hypot(*(h2 - h)) < 0.3 * pxm or np.hypot(*(e2_ - e_)) > 0.15 * pxm: continue
            if abs(float((h2 - h) @ n)) > 3.0 or abs(float((e2_ - h) @ n)) > 3.0: continue
            s2 = float((h2 - h) @ u)
            if not (L + 0.4 * pxm <= s2 <= L + 1.4 * pxm): continue
            e_ = h + u * s2; L = s2; merged = True; break
        n0, n1 = min(s[0] for s in secs), max(s[1] for s in secs)
        if n1 - n0 > 40: door_fail.append(nm); door_why[di_] = 'не разобрано: сечение стены у косяков толще 40 px'; continue
        ring = np.array([h - u * 1.5 + n * n0, e_ + u * 1.5 + n * n0, e_ + u * 1.5 + n * n1, h - u * 1.5 + n * n1])
        C.fill_px(dr, ring)
        # проём вдоль оси: где тела нет
        axis_off = (n0 + n1) / 2; s = np.arange(-12, L + 12, 0.5); pts = h + np.outer(s, u) + n * axis_off
        free = np.array([C.at(body, q) == 0 for q in pts])
        if merged: s0, s1 = 0.0, L                                  # 0.33: две створки — от косяка до косяка, разрыв тела не сужает
        elif free.any() and (s[np.nonzero(free)[0][-1]] - s[np.nonzero(free)[0][0]]) >= 0.5 * L:
            idx = np.nonzero(free)[0]; s0, s1 = s[idx[0]], s[idx[-1]]
        else: s0, s1 = 0.0, L                                       # перегородка сплошная — проём по полотну
        thick = n1 - n0
        doors.append(dict(name=nm, a=h + u * s0 + n * axis_off, b=h + u * s1 + n * axis_off, thick=thick, kind='door', src=di_,
                          how='две створки' if merged else 'полотно и дуга',
                          ext=C.at(ext, h - u * 3 + n * axis_off) > 0 or C.at(ext, e_ + u * 3 + n * axis_off) > 0))
    rep['дверей_не_разобрано'] = door_fail
    del body_d2, cov_d, glh                                          # 0.33 (КМ-11): растры, которые дальше не нужны, — освободить
    # штора в проёме — граница помещения
    curtains = []
    for nm, segs in D['curtain']:
        Q = np.vstack([C.px(P) for P in segs]); c = Q.mean(0); U, Sv, Vt = np.linalg.svd(Q - c); d = Vt[0]
        tt = (Q - c) @ d; curtains.append(LineString([c + d * tt.min(), c + d * tt.max()]))
    walls = np.maximum(body, dr)
    walls = cv2.morphologyEx(walls, cv2.MORPH_CLOSE, np.ones((int(round(T * 0.8 * k)) | 1,) * 2, np.uint8))
    # ---- граф осей и классы рёбер
    cen, edges = skel_graph(walls)
    dt_full = cv2.distanceTransform((walls > 0).astype(np.uint8), cv2.DIST_L2, cv2.DIST_MASK_PRECISE)     # 0.30: float32 точной меры
    dt = _AtNodes(dt_full, cen); del dt_full                         # 0.33 (КМ-11): после скелета и только в узлах — полный растр не живёт до чистки отростков
    rep['скелет'] = dict(узлов=len(cen) - 1, рёбер=len(edges))
    lt_dt = (cv2.distanceTransform((lt > 0).astype(np.uint8), cv2.DIST_L2, cv2.DIST_MASK_PRECISE) / k).astype(np.float16)   # 0.33 (КМ-11): float16 — вдвое меньше памяти
    cls_img = np.zeros(walls.shape, np.uint8)
    for m, c_ in ((lt, 'light1'), (gl, 'glass'), (inn, 'int'), (fg, 'fglass'), (ext, 'ext'), (dr, 'door')): cls_img[m > 0] = CID[c_]
    cls_near = ndimage.grey_dilation(cls_img, size=(5, 5))
    def edge_cls(P):          # P — px растра
        Q = np.round(P).astype(int); Q[:, 0] = Q[:, 0].clip(0, cls_img.shape[1] - 1); Q[:, 1] = Q[:, 1].clip(0, cls_img.shape[0] - 1)
        v = cls_img[Q[:, 1], Q[:, 0]]; v = np.where(v == 0, cls_near[Q[:, 1], Q[:, 0]], v)
        cnt = collections.Counter(v.tolist()); cnt.pop(0, None)
        if not cnt: return 'light1'
        top = CLS[cnt.most_common(1)[0][0]]
        if top == 'door':                      # дверь — по классу стены рядом
            cnt.pop(CID['door']); top = CLS[cnt.most_common(1)[0][0]] if cnt else 'int'
        if top == 'light1':
            th = np.median(lt_dt[Q[:, 1], Q[:, 0]]); top = 'light2' if th >= 2.0 else 'light1'
        return top
    def thr_of(P, r):          # порог отростка, px растра
        c_ = edge_cls(P)
        if c_ == 'fglass': return 0.45 * pxm * k
        if c_ in ('light1', 'light2'): return max(0.25 * pxm * k, 1.5 * r + 2 * k)
        return 1.5 * r + 2 * k
    edges = merge_deg2(edges); edges = prune_spurs(edges, cen, dt, thr_of)
    rep['скелет']['рёбер_после_чистки'] = len(edges)
    E = []
    for a_, b_, P in edges:
        if len(P) < 2: continue
        c_ = edge_cls(P); Pm = P / k
        E.append(dict(a=a_, b=b_, P=Pm, cls=c_, line=LineString(Pm).simplify(a.simplify)))
    rep['рёбра_по_классам_м'] = {c_: round(sum(e['line'].length for e in E if e['cls'] == c_) / pxm, 1) for c_ in sorted({e['cls'] for e in E})}
    # ---- замыкания
    ends = free_ends(E, T); rep['торцов'] = len(ends)
    solid_lines = unary_union([e['line'] for e in E if e['cls'] in SOLID | {'light2'}])
    closes, used = [], set()
    ca = math.cos(math.radians(25))
    def add_close(kind, i, j=None, q=None):
        p = ends[i]['p']; q = ends[j]['p'] if j is not None else q
        closes.append(dict(kind=kind, line=LineString([p, q]))); used.add(i)
        if j is not None: used.add(j)
        for m in ([i] if j is None else [i, j]):          # срезать крючок косяка
            en = ends[m]
            if en['hook']:
                e = E[en['edge']]; P = e['P']
                e['P'] = P[en['hook']:] if en['side'] == 0 else P[:len(P) - en['hook']]
                e['line'] = LineString(e['P']).simplify(0.6)
    # шкафы A-76: два торца у одного блока шкафов — стена по торцам
    cab_wall = []
    for nm, segs in D['cab']:
        Q = np.vstack([C.px(P) for P in segs])
        if len(Q) < 3: continue
        hull0 = Polygon(cv2.convexHull(Q.astype(np.float32))[:, 0, :]); hull = hull0.buffer(1.5 * T)
        mrr = hull0.minimum_rotated_rectangle; cs = np.array(mrr.exterior.coords)[:4]
        sides = [cs[1] - cs[0], cs[2] - cs[1]]; ax = max(sides, key=lambda v: np.hypot(*v)); Lc = float(np.hypot(*ax)); ax = ax / max(Lc, 1e-9)
        cand = [i for i, e in enumerate(ends) if i not in used and hull.contains(Point(e['p']))]
        if len(cand) < 2: continue
        # торцы вдоль шкафов: по оси шкафа, соседние соединяются, если отрезок идёт вдоль шкафов
        tt = np.array([ends[i]['p'] @ ax for i in cand]); order_ = [cand[i] for i in np.argsort(tt)]
        made = False; used0 = set(used)
        for x_, i in enumerate(order_):                       # от каждого торца — к следующему вдоль оси шкафа (торцы сбоку пропускаются)
            if i in used0: continue
            for j in order_[x_ + 1:]:
                if j in used0: continue
                v = ends[j]['p'] - ends[i]['p']; L = float(np.hypot(*v))
                if L < 1e-6 or L > Lc + 2 * T or abs(v @ ax) / L < math.cos(math.radians(20)): continue
                seg = LineString([ends[i]['p'], ends[j]['p']])
                if seg.crosses(solid_lines) or not hull0.buffer(1.5 * T).contains(seg): break
                add_close('cab', i, j); made = True; break
        if made: cab_wall.append(nm)
    rep['шкафы_как_стена'] = cab_wall
    # лифты A-66: торцы у блока — фронт шахт по прямой (двери лифтов — проёмы, map/rules/60 §2.2)
    lift_front = []
    for nm, segs in D['lift']:
        Q = np.vstack([C.px(P) for P in segs])
        if len(Q) < 3: continue
        hull = Polygon(cv2.convexHull(Q.astype(np.float32))[:, 0, :]).buffer(2.5 * T)
        cand = [i for i, e in enumerate(ends) if i not in used and hull.contains(Point(e['p']))]
        if len(cand) < 2: continue
        Pc = np.array([ends[i]['p'] for i in cand]); c0 = Pc.mean(0); U_, S_, Vt_ = np.linalg.svd(Pc - c0); d0 = Vt_[0]
        if len(cand) > 2 and S_[1] / max(len(cand), 1) ** 0.5 > 4.0: continue
        order_ = [cand[i] for i in np.argsort((Pc - c0) @ d0)]
        for i, j in zip(order_[:-1], order_[1:]):
            seg = LineString([ends[i]['p'], ends[j]['p']])
            if seg.length <= 2.5 * pxm and not seg.crosses(solid_lines): add_close('pass', i, j); lift_front.append(nm)
    rep['фронт_лифтов'] = lift_front
    # торцы рядом (любое направление, ≤ 0,5 м) — склейка разрывов фасада и стыков
    pairs = []
    for i in range(len(ends)):
        for j in range(i + 1, len(ends)):
            if ends[i]['cls'] not in SOLID or ends[j]['cls'] not in SOLID: continue
            L = float(np.hypot(*(ends[i]['p'] - ends[j]['p'])))
            if L <= 0.5 * pxm: pairs.append((L, i, j, 'snap'))
            else:
                Lf = facing(ends[i], ends[j], 2.6 * pxm, ca)
                if Lf: pairs.append((Lf + 0.5 * pxm, i, j, 'pass'))
    def crosses_mid(p, q, geom):
        a_, b_ = p + (q - p) * 0.04, p + (q - p) * 0.96
        return LineString([a_, b_]).intersects(geom)
    for L, i, j, kind in sorted(pairs):
        if i in used or j in used: continue
        if crosses_mid(ends[i]['p'], ends[j]['p'], solid_lines): continue
        add_close(kind if kind == 'pass' else 'pass', i, j)
    # одиночный торец стены — луч до стены не длиннее 1,2 м
    for i, e in enumerate(ends):
        if i in used or e['cls'] not in SOLID | {'light2'}: continue
        q = ray_hit(e['p'], e['d'], solid_lines, (2.6 if e['cls'] in SOLID else 0.4) * pxm)
        if q is not None: add_close('pass', i, q=q)
    rep['замыканий'] = collections.Counter(c['kind'] for c in closes)
    # ---- разделители A-93: пунктир -> прямые, концы — до стены
    seps0 = [LineString(C.px(P)) for nm, ss in D['sep'] for P in ss]
    seps = []
    allw = unary_union([e['line'] for e in E] + [c['line'] for c in closes])
    J = join_dashes(seps0, pxm)
    for gi, g in enumerate(J):
        Q = np.array(g.coords); d = Q[1] - Q[0]; d = d / max(np.hypot(*d), 1e-9)
        others = unary_union([allw] + [h for hj, h in enumerate(J) if hj != gi])
        for idx, sg in ((0, -1), (1, 1)):
            if others.distance(Point(Q[idx])) < 1.0: continue          # уже на линии
            q = ray_hit(Q[idx] - sg * d * 0.75, sg * d, others, 2.5 * pxm)
            if q is not None: Q[idx] = q
            else:
                pt = Point(Q[idx]); dd = others.distance(pt)
                if dd < 0.4 * pxm: Q[idx] = np.array(nearest_points(others, pt)[0].coords[0])
        seps.append(LineString(Q))
    rep['разделителей'] = dict(кусков=len(seps0), линий=len(seps))
    # 0.30: граница заливки зоны (92) вне стен — виртуальная граница: край коридора к открытым зонам (map/rules/11 §8, AutoCAD-лист)
    n_zl, zl_m, zlines, zone_px = 0, 0.0, [], None
    if D['zone']:
        Zp = [Polygon(C.px(P)).buffer(0) for R in D['zone'] for P in R]
        Z = unary_union([z for z in Zp if not z.is_empty]).buffer(1.0, join_style=2).buffer(-1.0, join_style=2); zone_px = Z
        far = cv2.dilate(walls, np.ones((int(round((T / 2 + 3) * k)) * 2 + 1,) * 2, np.uint8))     # дальше T/2 + 3 px от тела стены
        allw_z = unary_union([e['line'] for e in E] + [c['line'] for c in closes] + seps)
        for zp in getattr(Z, 'geoms', [Z]):
            if zp.geom_type != 'Polygon' or zp.area < 2.0 * pxm ** 2: continue
            for ring in [zp.exterior] + list(zp.interiors):
                Lr = ring.length; n_ = max(8, int(Lr)); X = np.array([ring.interpolate(i_ / n_, normalized=True).coords[0] for i_ in range(n_ + 1)])
                free_ = np.array([C.at(far, x) == 0 for x in X]); idx = np.flatnonzero(free_)
                if not len(idx): continue
                for run in np.split(idx, np.flatnonzero(np.diff(idx) > 1) + 1):
                    if len(run) < 2 or (run[-1] - run[0]) * Lr / n_ < 0.5 * pxm: continue
                    Q = X[max(run[0] - 1, 0):min(run[-1] + 2, len(X))].copy()
                    for idx_ in (0, -1):                                     # конец — до оси стены рядом
                        pt = Point(Q[idx_])
                        if allw_z.distance(pt) < 2.5 * T: Q[idx_] = np.array(nearest_points(allw_z, pt)[0].coords[0])
                    g = LineString(Q).simplify(0.5)
                    if g.length > 0.5 * pxm: seps.append(g); zlines.append(g); n_zl += 1; zl_m += g.length
    rep['граница_зон'] = dict(линий=n_zl, м=round(zl_m / pxm, 1))
    # ---- контур здания: где по краю нет стен (линия обрыва чертежа), он замыкает зоны виртуальной границей
    bm5 = ndimage.binary_fill_holes(cv2.morphologyEx(walls, cv2.MORPH_CLOSE, kc(5000)) > 0).astype(np.uint8)
    cn, _ = cv2.findContours(bm5, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    outline = []
    if cn:
        big = max(cn, key=cv2.contourArea); ring = LineString(np.vstack([big[:, 0, :], big[:1, 0, :]]) / k + 0.25)
        allw2 = unary_union([e['line'] for e in E] + [c['line'] for c in closes]).buffer(0.25 * pxm)
        rest_ = ring.difference(allw2)
        for g in getattr(rest_, 'geoms', [rest_]):
            if g.geom_type == 'LineString' and g.length > 0.5 * pxm:
                Q = np.array(g.coords)
                for idx in (0, -1):
                    pt = Point(Q[idx]); Q[idx] = np.array(nearest_points(unary_union([e['line'] for e in E]), pt)[0].coords[0])
                outline.append(LineString(Q))
    rep['контур_здания_м'] = round(sum(g.length for g in outline) / pxm, 1)
    # ---- грани
    lines = [e['line'] for e in E] + [c['line'] for c in closes] + seps + outline + curtains
    polys, cuts, dangles, invalid = polygonize_full(unary_union(lines))
    faces = [p for p in getattr(polys, 'geoms', []) if p.area > 0.04 * pxm ** 2]
    bmx = walls.copy()                                              # здание: стены + замыкания + контур там, где стен нет
    for g in [c['line'] for c in closes] + outline + seps:
        cv2.polylines(bmx, [C.q(np.array(g.coords))], False, 255, 2 * k, shift=3)
    bm = ndimage.binary_fill_holes(bmx > 0).astype(np.uint8)
    wl = walls > 0
    def inside_bld(pt): return bool(C.at(bm, (pt.x, pt.y)))
    def mostly_wall(f):
        inner = f.buffer(-1.0)
        if inner.is_empty: return True
        x0, y0, x1, y1 = inner.bounds; x0, y0 = max(int(x0 * k) - 2, 0), max(int(y0 * k) - 2, 0)   # 0.30: окно по рамке грани, не весь холст
        x1, y1 = min(int(x1 * k) + 3, wl.shape[1]), min(int(y1 * k) + 3, wl.shape[0])
        if x1 <= x0 or y1 <= y0: return True
        mm = np.zeros((y1 - y0, x1 - x0), np.uint8)
        for g in getattr(inner, 'geoms', [inner]):
            if g.geom_type == 'Polygon': cv2.fillPoly(mm, [np.round((np.array(g.exterior.coords) * k - (x0, y0)) * 8).astype(np.int32)], 1, shift=3)
        tot = mm.sum()
        return tot == 0 or (wl[y0:y1, x0:x1] & (mm > 0)).sum() / tot > 0.6
    drop_f = []
    keep_f = []
    for f in faces:
        ib, mw = inside_bld(f.representative_point()), mostly_wall(f)
        if ib and not mw: keep_f.append(f)
        elif f.area > 1.0 * pxm ** 2:
            c = f.representative_point(); drop_f.append(dict(x=round(c.x), y=round(c.y), m2=round(f.area / pxm ** 2, 1), вне_здания=not ib, в_теле_стены=mw))
    faces = keep_f; rep['отброшено_граней'] = drop_f
    rep['граней'] = len(faces)
    bld_area = float(bm.sum()) / k ** 2
    if faces and bld_area > 0:                                     # 🔴 map/rules/11 §8: грань больше 30 % этажа — тихий отказ полигонизации
        fmax = max(faces, key=lambda f: f.area)
        if fmax.area > 0.3 * bld_area:
            c = fmax.representative_point(); stops.append(dict(что='грань полигонизации больше 30 % этажа (map/rules/11 §8)', x=round(c.x), y=round(c.y), доля=round(fmax.area / bld_area, 3)))
    # ---- подписи
    tx = [(s_, *C.px([[x, y]])[0], h, *C.px([[cx, cy]])[0]) for s_, x, y, h, cx, cy in D['text']]
    names_m2 = [z for z in tx if re.search(r'м[²2]\s*$', z[0])]
    nums = [z[:4] for z in tx if re.fullmatch(r'\d{1,3}', z[0]) and any(math.hypot(z[1] - n[1], z[2] - n[2]) < 2.0 * pxm for n in names_m2)]
    # 0.30 (ПФ5): номер в кружке слоя надписей — марка помещения, без кружка — номер места (map/rules/11 §8, п. 2)
    sc_ = math.sqrt(abs(np.linalg.det(M)))
    circ = [(*C.px([[cx, cy]])[0], r * sc_) for cx, cy, r in D['tagc'] if 0.15 * pxm <= r * sc_ <= 1.5 * pxm]
    cnums, used_c = [], set()
    if circ:
        cc = np.array([(x, y) for x, y, r in circ]); cr = np.array([r for x, y, r in circ])
        cand_ = []
        for z in tx:
            if not re.fullmatch(NUMRE, z[0]) or z[:4] in nums: continue
            d_ = np.hypot(cc[:, 0] - z[4], cc[:, 1] - z[5]); j = int(np.argmin(d_))
            if d_[j] <= 1.25 * cr[j]: cand_.append((d_[j], j, z))
        for d_, j, z in sorted(cand_, key=lambda w: w[0]):
            if j in used_c: continue
            used_c.add(j); cnums.append((z[0], float(cc[j][0]), float(cc[j][1]), z[3]))
    rep['марки'] = dict(revit=len(nums), кружков=len(circ), в_кружке=len(cnums))
    plain0 = [z for z in tx if not re.search(r'\d', z[0]) and len(z[0]) > 1]
    rep_ = collections.Counter(z[0].strip().lower() for z in plain0)        # надпись, которая повторяется на этаже ≥ 5 раз и не имя типа, — пометка, не имя
    plain1 = sorted([z[:4] for z in plain0 if rep_[z[0].strip().lower()] < 5 or room_type(z[0]) != 'other'], key=lambda z: z[2])
    plain, line_ = [], []                                           # строки имени: сверху вниз, в строке (|Δy| ≤ 0,6 кегля) — слева направо
    for z in plain1:
        if line_ and abs(z[2] - line_[0][2]) > 0.6 * max(line_[0][3] * sc_, 1.0): plain += sorted(line_, key=lambda w: w[1]); line_ = []
        line_.append(z)
    plain += sorted(line_, key=lambda w: w[1])
    rep['надписей_пометок'] = sorted({z[0] for z in plain0 if rep_[z[0].strip().lower()] >= 5 and room_type(z[0]) == 'other'})
    tree = STRtree(faces)
    def face_at(x, y):
        for i in tree.query(Point(x, y)):
            if faces[i].contains(Point(x, y)): return int(i)
        return None
    info = [dict(num='', name='', labels=[], seeds=[]) for _ in faces]
    for s_, x, y, h in nums:
        i = face_at(x, y)
        if i is None: continue
        nm = re.sub(r'\s+\d+([.,]\d+)?\s*м[²2]\s*$', '', min(names_m2, key=lambda n: math.hypot(n[1] - x, n[2] - y))[0]).strip()
        info[i]['seeds'].append((s_, nm, x, y))
        if not info[i]['num']: info[i].update(num=s_, name=nm)
        else: info[i]['labels'].append(s_)
    lost_marks = []
    for s_, x, y, h in cnums:
        i = face_at(x, y)
        if i is None: lost_marks.append(dict(num=s_, x=round(x), y=round(y))); continue
        info[i]['seeds'].append((s_, '', x, y))
        if not info[i]['num']: info[i].update(num=s_, name='')
        else: info[i]['labels'].append(s_)
    rep['марки_вне_граней'] = lost_marks
    for s_, x, y, h in plain:
        i = face_at(x, y)
        if i is not None: info[i]['labels'].append(s_); info[i].setdefault('lab_pts', []).append((s_, x, y))
    def blk_hull(segs):
        Q = np.vstack([C.px(P) for P in segs]); return Polygon(cv2.convexHull(Q.astype(np.float32))[:, 0, :])
    stairs = [(nm, blk_hull(ss)) for nm, ss in D['stair']]
    lifts = [(nm, blk_hull(ss)) for nm, ss in D['lift']]
    # ---- карта классов границ
    cls_map = np.zeros((H, W), np.uint8)
    for s in seps: cv2.polylines(cls_map, [np.round(np.array(s.coords) * 8).astype(np.int32)], False, CID['sep'], 3, shift=3)
    for s in zlines: cv2.polylines(cls_map, [np.round(np.array(s.coords) * 8).astype(np.int32)], False, CID['zone'], 3, shift=3)
    for s in outline: cv2.polylines(cls_map, [np.round(np.array(s.coords) * 8).astype(np.int32)], False, CID['outline'], 3, shift=3)
    for e in sorted(E, key=lambda e: e['cls'] != 'light1'):     # одиночные линии — под остальными
        cv2.polylines(cls_map, [np.round(e['P'] * 8).astype(np.int32)], False, CID[e['cls']], 3, shift=3)
    for c in closes: cv2.polylines(cls_map, [np.round(np.array(c['line'].coords) * 8).astype(np.int32)], False, CID[c['kind']], 3, shift=3)
    for s in curtains: cv2.polylines(cls_map, [np.round(np.array(s.coords) * 8).astype(np.int32)], False, CID['curtain'], 3, shift=3)
    def bshare(f):
        b = f.exterior; n = max(8, int(b.length / 2)); pts = np.array([b.interpolate(i_ / n, normalized=True).coords[0] for i_ in range(n)])
        q = np.round(pts).astype(int); q[:, 0] = q[:, 0].clip(0, W - 1); q[:, 1] = q[:, 1].clip(0, H - 1)
        v = collections.Counter(cls_map[q[:, 1], q[:, 0]].tolist()); tot = sum(v.values())
        return {CLS[c_]: m / tot for c_, m in v.items()}
    def bshare_line(g):
        pts = []
        for part in getattr(g, 'geoms', [g]):
            if part.length <= 0 or not hasattr(part, 'interpolate'): continue
            n = max(2, int(part.length / 2)); pts += [part.interpolate(i_ / n, normalized=True).coords[0] for i_ in range(n + 1)]
        if not pts: return {}
        q = np.round(np.array(pts)).astype(int); q[:, 0] = q[:, 0].clip(0, W - 1); q[:, 1] = q[:, 1].clip(0, H - 1)
        v = collections.Counter(cls_map[q[:, 1], q[:, 0]].tolist()); tot = sum(v.values())
        return {CLS[c_]: m / tot for c_, m in v.items()}
    R = [dict(poly=f, **info[i]) for i, f in enumerate(faces)]
    for r in R:
        r['stair'] = next((nm for nm, h in stairs if r['poly'].intersection(h).area > 0.5 * r['poly'].area), None)
        r['lift'] = next((nm for nm, h in lifts if r['poly'].intersection(h).area > 0.3 * r['poly'].area), None)
    removed = []
    for nm, h in stairs:                                   # лестничная клетка — одно помещение
        grp = [r for r in R if r['stair'] == nm]
        if len(grp) > 1:
            base = max(grp, key=lambda r: r['poly'].area)
            for r in grp:
                if r is base: continue
                removed.append(base['poly'].boundary.intersection(r['poly'].buffer(0.8)))
                base['poly'] = union2(base['poly'], r['poly']); base['labels'] += r['labels']; r['dead'] = True
    R = [r for r in R if not r.get('dead')]
    outside = [r for r in R if not (r['num'] or r['seeds']) and bshare(r['poly']).get('outline', 0) > 0.25]
    rep['снаружи_фасада'] = len(outside); R = [r for r in R if r not in outside]
    tag_m2 = {}                                                   # площадь из марки Revit «Имя  NN м²» — по внутренним граням стен
    for s_, x, y, h in nums:
        nm = min(names_m2, key=lambda n: math.hypot(n[1] - x, n[2] - y))[0]; mm = re.search(r'(\d+([.,]\d+)?)\s*м[²2]\s*$', nm)
        if mm: tag_m2[s_] = float(mm.group(1).replace(',', '.'))
    # ---- в грани несколько номеров (не нашлось замыкания): делим водоразделом свободного места, затравки — номера
    barrier = [e['line'] for e in E] + [c['line'] for c in closes] + seps + outline + curtains
    btree = STRtree(barrier); split_log = []
    def split_face(poly, seeds):
        minx, miny, maxx, maxy = poly.bounds; ox, oy = int(minx) - 2, int(miny) - 2
        w, h = int(maxx - ox) + 4, int(maxy - oy) + 4
        m = np.zeros((h, w), np.uint8); cv2.fillPoly(m, [np.round((np.array(poly.exterior.coords) - (ox, oy)) * 8).astype(np.int32)], 1, shift=3)
        for hole in poly.interiors: cv2.fillPoly(m, [np.round((np.array(hole.coords) - (ox, oy)) * 8).astype(np.int32)], 0, shift=3)
        bar = np.zeros_like(m)
        for j in btree.query(poly):
            cv2.polylines(bar, [np.round((np.array(barrier[j].coords) - (ox, oy)) * 8).astype(np.int32)], False, 1, 2, shift=3)
        free = (m > 0) & (bar == 0); dist = ndimage.distance_transform_edt(free)
        mk = np.zeros((h, w), np.int32)
        for i_, (_, _, x, y) in enumerate(seeds, 1):          # затравка — круг до ближайшей преграды, не больше 0,8 м
            xi, yi = int(x - ox), int(y - oy)
            rr = int(min(0.8 * pxm, dist[min(max(yi, 0), h - 1), min(max(xi, 0), w - 1)] * 0.9)) if 0 <= yi < h and 0 <= xi < w else 3
            cv2.circle(mk, (xi, yi), max(rr, 3), i_, -1)
        mk[~free] = 0
        caps = [tag_m2.get(z[0]) for z in seeds]
        if all(c_ is None for c_ in caps):
            lab = watershed(-dist, mk, mask=m > 0)
        else:                                                     # рост кольцами с ёмкостью: площадь марки × 1,15 (ось шире граней)
            f3 = 3                                                    # рост на сетке 3×3 px — быстрее в 27 раз
            fr3 = free[::f3, ::f3]; lab = mk[::f3, ::f3].copy(); lab[~fr3] = 0
            for i_ in range(1, len(seeds) + 1):
                if not (lab == i_).any():
                    ys_, xs_ = np.nonzero(mk == i_)
                    if len(ys_): lab[min(ys_[0] // f3, lab.shape[0] - 1), min(xs_[0] // f3, lab.shape[1] - 1)] = i_
            capx = [None if c_ is None else c_ * 1.15 * pxm ** 2 / f3 ** 2 for c_ in caps]
            cross = ndimage.generate_binary_structure(2, 1)
            area_ = [int((lab == i_).sum()) for i_ in range(1, len(seeds) + 1)]
            grow_cap = True
            for _ in range(3000):
                moved = False
                for i_ in range(1, len(seeds) + 1):
                    if grow_cap and capx[i_ - 1] is not None and area_[i_ - 1] >= capx[i_ - 1]: continue
                    nb_ = ndimage.binary_dilation(lab == i_, cross) & fr3 & (lab == 0)
                    n_ = int(nb_.sum())
                    if n_: lab[nb_] = i_; area_[i_ - 1] += n_; moved = True
                if not moved:
                    if grow_cap: grow_cap = False; continue          # ёмкости исчерпаны — остаток делят без ёмкости
                    break
            lab = np.kron(lab, np.ones((f3, f3), np.int32))[:h, :w]
            lab = np.pad(lab, ((0, max(0, h - lab.shape[0])), (0, max(0, w - lab.shape[1]))))
            lab[~free & (bar == 0) | (m == 0)] = 0
            # линии-преграды — к ближайшей области
            if (lab == 0).any() and (lab > 0).any():
                _, (iy, ix) = ndimage.distance_transform_edt(lab == 0, return_indices=True); lab = np.where(m > 0, lab[iy, ix], 0)
        out = []
        for i_ in range(1, len(seeds) + 1):
            cn_, _ = cv2.findContours((lab == i_).astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
            if not cn_: out.append(None); continue
            c_ = max(cn_, key=cv2.contourArea)
            if len(c_) < 3: out.append(None); continue
            pg = poly_main(Polygon(c_[:, 0, :] + (ox, oy) + 0.5).buffer(0.5, join_style=2).buffer(-0.5, join_style=2).simplify(1.0).intersection(poly))
            out.append(pg)
        return out
    newR = []
    for r in R:
        if len(r['seeds']) < 2: newR.append(r); continue
        parts = split_face(r['poly'], r['seeds'])
        split_log.append([z[0] for z in r['seeds']])
        for (num_, nm_, x, y), pg in zip(r['seeds'], parts):
            if pg is None or pg.area < 0.3 * pxm ** 2: continue
            lp = r.get('lab_pts') or []                                  # 0.30: надпись — той части, в которой она стоит
            labs = [l_ for l_ in r['labels'] if not re.fullmatch(NUMRE, l_) and not any(l_ == q_[0] for q_ in lp)] + [q_[0] for q_ in lp if pg.buffer(1.0).contains(Point(q_[1], q_[2]))]
            newR.append(dict(poly=pg, num=num_, name=nm_, labels=labs, seeds=[(num_, nm_, x, y)], stair=r.get('stair'), lift=r.get('lift')))
    R = newR; rep['разделено_водоразделом'] = split_log
    # новые границы — виртуальные (там, где под ними нет линии)
    for r in R:
        b = r['poly'].exterior; n_ = max(8, int(b.length / 2))
        for i_ in range(n_):
            x_, y_ = b.interpolate(i_ / n_, normalized=True).coords[0]; xi, yi = int(round(x_)), int(round(y_))
            if 0 <= yi < H and 0 <= xi < W and cls_map[max(0, yi - 2):yi + 3, max(0, xi - 2):xi + 3].max() == 0: cls_map[yi, xi] = CID['sep']
    named = lambda r: bool(r['num'] or r['stair'] or r['lift'] or [l_ for l_ in r['labels'] if not re.fullmatch(r'бар|отдел.*', l_, re.I)])
    # без номера и имени — помещение, только если от соседей отделено настоящими стенами и дверями;
    # граница по догадке (проход, шкафы), одиночной линии или разделителю — сливаем (перегородка двойной линией — граница)
    def neighbours(r, alive, tree, polys0):
        out = []
        for j in tree.query(r['poly'].buffer(1.0)):
            q = alive[int(j)]
            if q is r or q.get('dead') or q['poly'].distance(r['poly']) >= 1.0: continue
            out.append(q)
        return out
    def in_zone(r):                                               # доля грани в заливке зоны 92 (коридор листа)
        a_ = r['poly'].area
        return r['poly'].intersection(zone_px).area / a_ if zone_px is not None and a_ > 0 else 0.0
    n_zone_keep = [0]
    for _pass in range(6):
        alive = [r for r in R if not r.get('dead')]
        tree = STRtree([r['poly'].buffer(2.0) for r in alive]); changed = False      # дерево по рамкам с запасом: соседи растут при слиянии
        for r in sorted([r for r in alive if not named(r)], key=lambda r: r['poly'].area):
            if r.get('dead'): continue
            per = r['poly'].exterior.length; nbr = []
            for q in neighbours(r, alive, tree, None):
                shb = r['poly'].boundary.intersection(q['poly'].buffer(0.8))
                if shb.length <= 1.0: continue
                b2 = bshare_line(shb); weak = sum(v * WEAK.get(c_, 0.0) for c_, v in b2.items())       # 0.30: край зоны — признак листа, слабее догадки
                if zone_px is not None and b2.get('zone', 0) >= 0.5 and (in_zone(r) >= 0.5) != (in_zone(q) >= 0.5): n_zone_keep[0] += 1; continue   # 0.33 (КМ-7, В2К-5): через край заливки 92 не сливать — коридор и открытая зона
                wl_ = shb.length * weak
                if wl_ >= min(1.0 * pxm, 0.25 * per): nbr.append((named(q), wl_, id(q), q))
            if not nbr: continue
            if zone_px is not None and len(nbr) > 1 and in_zone(r) < 0.5:   # 0.30: грань вне заливки коридора (92) — не в коридор, если есть другой сосед
                nz = [z for z in nbr if in_zone(z[3]) < 0.5]
                if nz: nbr = nz
            *_, q = max(nbr, key=lambda z: z[:2])
            removed.append(r['poly'].boundary.intersection(q['poly'].buffer(0.8)))
            q['poly'] = union2(q['poly'], r['poly']); q['labels'] += r['labels']; r['dead'] = True; changed = True
        R = [r for r in R if not r.get('dead')]
        if not changed: break
    # мелкие безымянные грани (< 0,5 м²) без лифта и лестницы — к соседу с самой длинной общей границей
    alive = R; tree = STRtree([r['poly'].buffer(2.0) for r in alive])
    for r in sorted([r for r in alive if not named(r) and r['poly'].area < 0.5 * pxm ** 2], key=lambda r: r['poly'].area):
        nbr = [(r['poly'].boundary.intersection(q['poly'].buffer(0.8)).length, id(q), q) for q in neighbours(r, alive, tree, None)]
        nbr = [z for z in nbr if z[0] > 1.0]
        r['dead'] = True
        if not nbr: continue
        L, _, q = max(nbr, key=lambda z: z[:2])
        q['poly'] = union2(q['poly'], r['poly'])
    R = [r for r in R if not r.get('dead')]
    # 0.30: кабины санузла — ряд мелких безымянных граней (0,8–3,5 м²), чьи двери все уже 0,7 м и ведут в одно помещение: часть его,
    # перегородки кабин не рисуются, дверь кабины — не проём карты (map/rules/11 §8, п. 2; решение 26.09 §1; №30). Одиночная — кладовая, остаётся
    cand_cab = collections.defaultdict(list)
    for r in [r for r in R if not named(r) and 0.8 * pxm ** 2 <= r['poly'].area <= 3.5 * pxm ** 2]:
        dd = [(i_, d) for i_, d in enumerate(doors) if d['kind'] == 'door' and LineString([d['a'], d['b']]).distance(r['poly'].exterior) <= 3.0]
        if not dd or any(np.hypot(*(np.asarray(d['b']) - np.asarray(d['a']))) > 0.7 * pxm for _, d in dd): continue
        tgt = {}
        for i_, d in dd:
            a_, b_ = np.asarray(d['a'], float), np.asarray(d['b'], float); u_ = (b_ - a_) / max(np.hypot(*(b_ - a_)), 1e-9); n_ = np.array([-u_[1], u_[0]])
            for sg in (1, -1):
                pt = Point((a_ + b_) / 2 + sg * n_ * (T + 3))
                q = next((q for q in R if q is not r and q['poly'].contains(pt)), None)
                if q is not None: tgt[id(q)] = q
        if len(tgt) == 1: q = next(iter(tgt.values())); cand_cab[id(q)].append((r, q, [i_ for i_, _ in dd]))
    n_cab, cab_doors = 0, set()
    for grp in cand_cab.values():
        if len(grp) < 2: continue
        for r, q, di in sorted(grp, key=lambda z: z[0]['poly'].area):
            removed.append(r['poly'].boundary.intersection(q['poly'].buffer(0.8)))
            q['poly'] = union2(q['poly'], r['poly']); r['dead'] = True; n_cab += 1; cab_doors |= set(di)
    R = [r for r in R if not r.get('dead')]
    for i_ in cab_doors:
        if 'src' in doors[i_]: door_why[doors[i_]['src']] = 'дверь кабины санузла: кабина — часть санузла (№30)'
    if cab_doors: doors = [d for i_, d in enumerate(doors) if i_ not in cab_doors]
    rep['кабины_санузлов'] = dict(слито=n_cab, дверей_кабин=len(cab_doors))
    # 0.33 (КМ-6; №104, строка 206; В2К-4; Н-E6; П3-14): ядро листа AutoCAD — по одной грани на массив; кабина с унитазом — часть санузла
    san_px = [Point(*C.px([q_])[0]) for q_ in D['san']]
    n_san = lambda poly: sum(1 for q_ in san_px if poly.contains(q_))
    def door_targets(r, R_alive):
        dd = [(i_, d) for i_, d in enumerate(doors) if d['kind'] == 'door' and LineString([d['a'], d['b']]).distance(r['poly'].exterior) <= 3.0]
        tgt = {}
        for i_, d in dd:
            a_, b_ = np.asarray(d['a'], float), np.asarray(d['b'], float); u_ = (b_ - a_) / max(np.hypot(*(b_ - a_)), 1e-9); n_ = np.array([-u_[1], u_[0]])
            for sg in (1, -1):
                pt = Point((a_ + b_) / 2 + sg * n_ * (T + 3)); q = next((q for q in R_alive if q is not r and not q.get('dead') and q['poly'].contains(pt)), None)
                if q is not None: tgt[id(q)] = q
        return dd, list(tgt.values())
    n_cab2, cab2 = 0, set()
    for r in sorted([r for r in R if not named(r) and 0.5 * pxm ** 2 <= r['poly'].area <= 4.0 * pxm ** 2 and n_san(r['poly'])], key=lambda r: r['poly'].area):
        if r.get('dead'): continue
        dd, tg = door_targets(r, R)
        q = tg[0] if len(tg) == 1 and named(tg[0]) else None
        if q is None and not dd:                                    # кабина без двери — к названному соседу с самой длинной общей границей
            nb_ = sorted(((r['poly'].boundary.intersection(q_['poly'].buffer(0.8)).length, id(q_), q_) for q_ in R if q_ is not r and not q_.get('dead') and named(q_)), key=lambda z: z[:2])
            q = nb_[-1][2] if nb_ and nb_[-1][0] > 0.5 * pxm else None
        if q is None: continue                                       # своя дверь в коридор — отдельный санузел (строка 171), тип — по сантехнике
        removed.append(r['poly'].boundary.intersection(q['poly'].buffer(0.8))); q['poly'] = union2(q['poly'], r['poly']) or q['poly']; r['dead'] = True; n_cab2 += 1
        cab2 |= {i_ for i_, _ in dd}
    R = [r for r in R if not r.get('dead')]
    for i_ in cab2:
        if 'src' in doors[i_]: door_why[doors[i_]['src']] = 'дверь кабины с унитазом (A-74): кабина — часть санузла (№30)'
    if cab2: doors = [d for i_, d in enumerate(doors) if i_ not in cab2]
    fire_px = [Polygon(C.px(R_)).buffer(0) for R_ in D['fire'] if len(R_) >= 3]   # шкаф ПК (68 fire) или надпись ПК в малой безымянной грани — ниша соседа, не ядро
    pk_pts = [Point(*C.px([[x_, y_]])[0]) for x_, y_, s_ in D['pk']]
    n_pk = 0
    for r in sorted([r for r in R if not named(r) and r['poly'].area < 1.5 * pxm ** 2], key=lambda r: r['poly'].area):
        if r.get('dead'): continue
        if not (any(f_.intersection(r['poly']).area >= 0.5 * min(f_.area, r['poly'].area) for f_ in fire_px if f_.is_valid) or any(r['poly'].contains(p_) for p_ in pk_pts)): continue
        nb_ = sorted(((r['poly'].boundary.intersection(q_['poly'].buffer(0.8)).length, id(q_), q_) for q_ in R if q_ is not r and not q_.get('dead')), key=lambda z: z[:2])
        if not nb_ or nb_[-1][0] <= 1.0: continue
        q = nb_[-1][2]; removed.append(r['poly'].boundary.intersection(q['poly'].buffer(0.8))); q['poly'] = union2(q['poly'], r['poly']) or q['poly']; r['dead'] = True; n_pk += 1
    R = [r for r in R if not r.get('dead')]
    core_m = unary_union([g_ for g_ in (Polygon(C.px(P)).buffer(0) for Rr in D['core_h'] for P in Rr if len(P) >= 3) if not g_.is_empty and g_.area >= pxm ** 2]) if D['core_h'] else Polygon()
    shaft_c = [g_ for g_ in polygonize_full(unary_union([LineString(C.px(P)) for segs in D['shaft'] for P in segs if len(P) >= 2]))[0].geoms
               if g_.area >= 0.3 * pxm ** 2] if D['shaft'] else []
    real_name = lambda r: bool(r['num'] or [l_ for l_ in r['labels'] if not re.fullmatch(NUMRE, l_) and room_type(l_) not in ('lift', 'stair', 'shaft') and not re.fullmatch(r'бар|отдел.*', l_, re.I)])
    core_rep = dict(массивов=0, граней_до=0, граней_после=0, малых_шахт=0, лифтов_слито_через_массив=0, не_слито=[])
    for Mp in [g_ for g_ in getattr(core_m, 'geoms', [core_m]) if g_.geom_type == 'Polygon' and g_.area >= pxm ** 2]:
        core_rep['массивов'] += 1
        mem = [r for r in R if not r.get('dead') and not real_name(r) and r['poly'].area > 0 and r['poly'].intersection(Mp).area >= 0.6 * r['poly'].area]
        core_rep['граней_до'] += len(mem)
        keep_sh = [r for r in mem if any(r['poly'].intersection(c_).area >= 0.5 * max(r['poly'].area, c_.area) for c_ in shaft_c)]
        for r in keep_sh: r['shaft'] = True
        core_rep['малых_шахт'] += len(keep_sh)
        mem = [r for r in mem if r not in keep_sh]
        par = list(range(len(mem)))
        def f_(i):
            while par[i] != i: par[i] = par[par[i]]; i = par[i]
            return i
        for i in range(len(mem)):
            for j in range(i + 1, len(mem)):
                if mem[i]['poly'].distance(mem[j]['poly']) <= 1.0 and mem[i]['poly'].buffer(1.0).intersection(mem[j]['poly'].buffer(1.0)).area >= 1.0 * pxm: par[f_(i)] = f_(j)
        grp = collections.defaultdict(list)
        for i in range(len(mem)): grp[f_(i)].append(mem[i])
        bases = []
        for g in grp.values():
            base = max(g, key=lambda r: r['poly'].area); base['core'] = True; bases.append(base)
            for r in g:
                if r is base: continue
                u_ = union2(base['poly'], r['poly'])
                if u_ is None or u_.area < base['poly'].area + 0.5 * r['poly'].area: continue
                removed.append(base['poly'].boundary.intersection(r['poly'].buffer(0.8))); base['poly'] = u_; base['labels'] += r['labels']; r['dead'] = True
        # v012, решение владельца 14.10.2026 (№104, map/rules/40 §2.10): лифт внутри блока ядра — и с дверью в холл — часть сплошной грани ядра, не отдельная
        # грань. Часть массива, отрезанная от главной грани помещением с номером, вырезанным в массиве (технич. комната у лифта), соединяется с ней телом
        # массива: помещение с номером отдаёт ядру тело массива (его граница — грань штриховки, линия стены — внутри массива на T/2), ядро — одна грань.
        # Не соединилось одной гранью (нет общего помещения-перемычки, кольцо не одно) — как было, в отчёт «не_слито». Малые шахты без двери — как были.
        main = max(bases, key=lambda r: r['poly'].area) if bases else None
        Mi = Mp.buffer(-T / 2, join_style=2)
        for gb in sorted([b_ for b_ in bases if b_ is not main], key=lambda r: -r['poly'].area):
            if gb.get('dead'): continue
            mem_id = {id(m_) for m_ in mem}
            via = [q for q in R if not q.get('dead') and q is not gb and q is not main and id(q) not in mem_id and not q.get('core') and q['poly'].area > 0
                   and q['poly'].distance(main['poly']) <= 1.0 and q['poly'].distance(gb['poly']) <= 1.0 and q['poly'].intersection(Mi).area > 0]
            done = False
            for q in sorted(via, key=lambda q: -q['poly'].intersection(Mi).area):
                j_ = core_join(main['poly'], gb['poly'], q['poly'], Mi)
                if j_ is None: continue
                removed.append(gb['poly'].boundary.intersection(q['poly'].buffer(0.8))); removed.append(main['poly'].boundary.intersection(q['poly'].buffer(0.8)))
                main['poly'], q['poly'] = j_; main['labels'] += gb['labels']; gb['dead'] = True
                core_rep['лифтов_слито_через_массив'] += 1; done = True; break
            if not done:
                c_ = gb['poly'].representative_point(); core_rep['не_слито'].append(dict(x=round(c_.x), y=round(c_.y), м2=round(gb['poly'].area / pxm ** 2, 1)))
        core_rep['граней_после'] += sum(1 for b_ in bases if not b_.get('dead'))
    R = [r for r in R if not r.get('dead')]
    rep['ядро'] = dict(core_rep, кабин_с_унитазом_слито=n_cab2, дверей_кабин=len(cab2), ниш_ПК_слито=n_pk)
    rooms = []; n_open_desk = 0
    zone_u = unary_union([z for z in (Polygon(C.px(P)).buffer(0) for R in D['zone'] for P in R) if not z.is_empty]) if D['zone'] else None
    desks = [Point(*C.px([q_])[0]) for q_ in D['desk']]
    for r in R:
        nm = r['name'] or ' '.join(l_ for l_ in r['labels'] if not re.fullmatch(r'бар|отдел.*', l_, re.I))
        ty = room_type(nm)
        if r.get('core') or r.get('shaft'): ty, nm = 'shaft', ''             # 0.33 (КМ-6, №104): грань ядра — без номера, без бейджей лифтов и лестниц
        elif ty == 'other' and n_san(r['poly']): ty = 'wc'                   # 0.33 (КМ-6): помещение с унитазом (A-74) — санузел
        if ty == 'other' and r['lift']: ty, nm = 'lift', nm or 'Лифт'
        if ty == 'other' and r['stair']: ty, nm = 'stair', nm or 'Лестница'
        sh = bshare(r['poly']); per_m = r['poly'].exterior.length / pxm
        zone_m = sh.get('zone', 0) * per_m                          # 0.30: край заливки зоны уже 1,2 м — дверной проём, не открытая связь
        virt = sh.get('sep', 0) + sh.get('light1', 0) + sh.get('outline', 0) + (sh.get('zone', 0) if zone_m >= 1.2 else 0.0)
        if ty == 'other' and zone_u is not None and r['poly'].area > 0 and r['poly'].intersection(zone_u).area >= 0.5 * r['poly'].area: ty = cfg.get('zone_fill_type', 'corridor')   # в заливке зоны (92); 0.33 (ОЧ-Б4): тип — из настройки
        nd = sum(1 for q_ in desks if r['poly'].contains(q_)); r['desks'] = nd
        if ty == 'other' and nd >= 4 and r['poly'].area >= 30 * pxm ** 2: ty = 'open'; n_open_desk += 1     # 0.30: открытая зона — столы рабочих мест ⟨один пример⟩
        is_open = ty in ('open', 'corridor') or (virt > 0.05 and ty not in CLOSED_ALWAYS)
        rooms.append(dict(poly=r['poly'], num=r['num'], name=nm.replace('  ', ' ').strip(), type=ty, open=bool(is_open),
                          fill=TYPE_FILL.get(ty, '#FFFFFF'), share={k_: round(v, 3) for k_, v in sh.items()}))
    n_booth = 0                                                    # 0.33 (КМ-7; строка 185): кабина для звонков (объект booth плана) — помещение, «маленькая переговорная»
    for Rb in D['booth']:
        g_ = Polygon(C.px(Rb)).buffer(0)
        if g_.is_empty or g_.area < 0.3 * pxm ** 2: continue
        g_ = g_.minimum_rotated_rectangle
        same = [r for r in rooms if r['poly'].intersection(g_).area >= 0.5 * max(r['poly'].area, g_.area)]
        if same:
            for r in same:
                if r['type'] in ('other', 'open'): r.update(type='meeting', name=r['name'] or 'Кабина для звонков', open=False, fill=TYPE_FILL['meeting'])
        else: rooms.append(dict(poly=g_, num='', name='Кабина для звонков', type='meeting', open=False, fill=TYPE_FILL['meeting'], share={}, booth=True))
        n_booth += 1
    rep['кабин_для_звонков'] = n_booth; rep['край_заливки_92_не_слит'] = n_zone_keep[0]
    rep['помещений'] = len(rooms); rep['открытых_по_столам'] = n_open_desk
    for r in rooms:
        if r['num'] in tag_m2: r['tag_m2'] = tag_m2[r['num']]
    net = lambda p: p.buffer(-0.1 * pxm, join_style=2).area / pxm ** 2        # ось -> внутренние грани: минус 0,1 м по контуру
    rep['площадь_против_марки'] = {r['num']: [round(net(r['poly']), 1), r['tag_m2']] for r in rooms if r.get('tag_m2') and
                                   abs(net(r['poly']) - r['tag_m2']) > max(1.0, 0.15 * r['tag_m2'])}
    n_tag = sum(1 for r in rooms if r.get('tag_m2'))                # К7: площадь марки не сходится — СТОП с местом (map/rules/11 §9)
    for r in rooms:
        if r.get('tag_m2') and r['num'] in rep['площадь_против_марки']:
            c = r['poly'].representative_point(); a_, b_ = rep['площадь_против_марки'][r['num']]
            stops.append(dict(что=f'площадь марки {r["num"]} не сходится: грань {a_} м² против {b_} м² (допуск 15 %, от 1 м²)', x=round(c.x), y=round(c.y), num=r['num']))
    rep['площадь'] = (f'по маркам Revit: в допуске {n_tag - len(rep["площадь_против_марки"])} из {n_tag}' if n_tag else
                      'площадей в марках нет (лист AutoCAD: номер в кружке, имя надписью) — не проверялась')
    dup = [n_ for n_, c_ in collections.Counter(r['num'] for r in rooms if r['num']).items() if c_ > 1]
    rep['номер_дважды'] = dup                                     # один номер у двух помещений — проход карты решает, справочно
    rep['слиплись'] = [[r['num']] + [l_ for l_ in r0['labels'] if re.fullmatch(NUMRE, l_)] for r, r0 in zip(rooms, R)
                       if any(re.fullmatch(NUMRE, l_) for l_ in r0['labels'])]
    # ---- какие рёбра — стены
    room_bnd = unary_union([r['poly'].exterior for r in rooms]).buffer(1.5)
    rem = unary_union([g for g in removed if not g.is_empty]).buffer(1.5) if removed else None
    keep_E, drop = [], collections.Counter()
    for e in E:
        g = e['line']; on_room = g.intersection(room_bnd).length / max(g.length, 1e-6)
        rr = g.intersection(rem).length / max(g.length, 1e-6) if rem is not None else 0
        if e['cls'] == 'light1': drop['light1'] += g.length; continue
        if e['cls'] == 'light2' and (on_room < 0.5 or rr > 0.5): drop['light2'] += g.length; continue
        if e['cls'] == 'light2':
            mid = g.interpolate(0.5, normalized=True); side = [r for r in rooms if r['poly'].buffer(2.0).contains(mid)]
            if side and all(r['open'] for r in side): drop['light2_между_зонами'] += g.length; continue
        if e['cls'] not in ('ext', 'fglass', 'glass') and rr > 0.5: drop[e['cls']] += g.length; continue   # 0.33 (КМ-10, П3-11): стекло 22G внутри одной зоны — рисуется
        keep_E.append(e)
    rep['снято_м'] = {k_: round(v / pxm, 1) for k_, v in drop.items()}
    # ---- проёмы проходов: часть линии замыкания вне тела
    def sides_differ(g):
        mid = np.array(g.interpolate(0.5, normalized=True).coords[0]); d_ = np.array(g.coords[-1]) - np.array(g.coords[0])
        nn_ = np.array([-d_[1], d_[0]]) / max(np.hypot(*d_), 1e-9)
        own = []
        for sg in (1, -1):
            pt = Point(mid + sg * nn_ * 3.0); own.append(next((i_ for i_, r in enumerate(rooms) if r['poly'].contains(pt)), None))
        return own[0] != own[1]
    for c in closes:
        if c['kind'] != 'pass' or not sides_differ(c['line']): continue
        g = c['line']; n = max(2, int(g.length * 2)); pts = np.array([g.interpolate(i_ / n, normalized=True).coords[0] for i_ in range(n + 1)])
        free = np.array([C.at(body, q) == 0 for q in pts])
        if not free.any(): continue
        idx = np.nonzero(free)[0]; a_, b_ = pts[max(idx[0] - 1, 0)], pts[min(idx[-1] + 1, n)]
        if np.hypot(*(b_ - a_)) < 0.45 * pxm: continue
        doors.append(dict(name='проход', a=a_, b=b_, thick=T, kind='pass', ext=C.at(ext, a_) > 0 or C.at(ext, b_) > 0))
    for d in doors:
        g = LineString([d['a'], d['b']]); nb = [r for r in rooms if r['poly'].buffer(1.5).intersects(g)]
        d['fill'] = next((r['fill'] for r in nb if r['fill'] != '#FFFFFF'), '#FFFFFF'); d['depth'] = 2 * T if d['ext'] else T
    rep['проёмов'] = collections.Counter(d['kind'] for d in doors)
    # ---- регуляризация: общие координаты прямых стен у всех помещений и линий
    reg_lines = [np.array(e['line'].coords) for e in keep_E] + [np.array(c['line'].coords) for c in closes if c['kind'] == 'cab']
    st_reg = {}
    if a.no_regularize: rr_, ll_ = [None] * len(rooms), [None] * len(reg_lines); st_reg = dict(выключена=True)   # стенд К6: выход до регуляризации
    else: rr_, ll_ = regularize([np.array(r['poly'].exterior.coords) for r in rooms], reg_lines, T=T, min_dir=3.0 * pxm, stat=st_reg)
    rep['регуляризация'] = st_reg
    for r, g in zip(rooms, rr_):
        if g is not None and g.area > 0.5 * r['poly'].area: r['poly'] = g
    tiny = [r for r in rooms if not r['num'] and not r['name'] and r['poly'].area < 0.5 * pxm ** 2]   # осколок < 0,5 м² после К6 — соседу (Ч-16)
    for r in tiny:
        nbr = [(r['poly'].boundary.intersection(q['poly'].buffer(1.0)).length, i_) for i_, q in enumerate(rooms) if q is not r and q not in tiny]
        nbr = [z for z in nbr if z[0] > 1.0]
        if nbr: q = rooms[max(nbr)[1]]; q['poly'] = union2(q['poly'], r['poly']) or q['poly']
    if tiny: rooms = [r for r in rooms if r not in tiny]
    rep['осколков_после_К6'] = len(tiny)
    for e, g in zip(keep_E, ll_[:len(keep_E)]):
        if g is not None and g.length > 0: e['line'] = g
    cab_ = [c for c in closes if c['kind'] == 'cab']
    for c, g in zip(cab_, ll_[len(keep_E):]):
        if g is not None and g.length > 0: c['line'] = g
    # грань внутри другого помещения без номера и имени, на 30 % и больше — колонна (28): петля обшивки вокруг колонны, не помещение
    # и не стена — колонна рисуется колонной (Ч-14 «вложенное», Ч-07 — короткие рёбра петли)
    colp = [g for g in (Polygon(C.px(P)).buffer(0) for R in D['col_h'] for P in R) if not g.is_empty]
    colu = unary_union(colp) if colp else Polygon()
    inner = [r for r in rooms if not r['num'] and not r['name'] and r['poly'].area < 5 * pxm ** 2 and not colu.is_empty and
             r['poly'].intersection(colu).area >= 0.3 * r['poly'].area and
             any(q is not r and q['poly'].area > r['poly'].area and Polygon(q['poly'].exterior).buffer(1.0).contains(r['poly']) for q in rooms)]
    if inner:
        rooms = [r for r in rooms if r not in inner]
        loop = unary_union([r['poly'].exterior for r in inner]).buffer(1.5)
        keep_E = [e for e in keep_E if e['line'].length <= 0 or e['line'].intersection(loop).length < 0.8 * e['line'].length]
    rep['колонн_в_петле_снято'] = len(inner)
    box_u = unary_union([bx['box'] for bx in col_boxes]) if col_boxes else Polygon()   # 0.31 (К-7): грань без номера и имени на 50 % и больше в коробе
    in_box = [r for r in rooms if not r['num'] and not r['name'] and not box_u.is_empty and r['poly'].intersection(box_u).area >= 0.5 * r['poly'].area]
    if in_box: rooms = [r for r in rooms if r not in in_box]                    # колонны — пустота обшивки, не помещение (короб рисуется поверх)
    rep['пустот_коробов_снято'] = len(in_box)
    # ---- К8: проём — на ось своей стены после регуляризации; глубина — толщина своей стены (T, у фасада 2T) + DOOR_EXTRA (Ч-19)
    shell_u = unary_union([r['poly'].buffer(1.0, join_style=2) for r in rooms]).buffer(-1.0, join_style=2) if rooms else Polygon()
    shell_b = unary_union([LineString(q.exterior.coords) for q in getattr(shell_u, 'geoms', [shell_u]) if q.geom_type == 'Polygon']) if not shell_u.is_empty else LineString()
    wsegs = []
    for r in rooms:
        if r['open']: continue
        P_ = np.array(r['poly'].exterior.coords); wsegs += [(a_, b_) for a_, b_ in zip(P_[:-1], P_[1:]) if np.hypot(*(b_ - a_)) >= 1.0]
    for e in keep_E:
        if e['cls'] in ('glass',): continue
        P_ = np.array(e['line'].coords); wsegs += [(a_, b_) for a_, b_ in zip(P_[:-1], P_[1:]) if np.hypot(*(b_ - a_)) >= 1.0]
    wl_geo = [LineString([a_, b_]) for a_, b_ in wsegs]; wtree = STRtree(wl_geo) if wl_geo else None
    n_snap, no_wall = 0, []
    for d in doors:
        a_, b_ = np.asarray(d['a'], float), np.asarray(d['b'], float); L_ = float(np.hypot(*(b_ - a_)))
        if L_ < 1e-6: continue
        u_ = (b_ - a_) / L_; c_ = (a_ + b_) / 2; best = None
        for j in (wtree.query(Point(c_).buffer(1.5 * T)) if wtree is not None else []):
            p_, q_ = wsegs[int(j)]; v_ = q_ - p_; uv = v_ / np.hypot(*v_)
            if abs(float(uv @ u_)) < math.cos(math.radians(15)): continue
            ds = wl_geo[int(j)].distance(Point(c_))
            if ds <= 1.5 * T and (best is None or ds < best[0]): best = (ds, p_, uv)
        if best is None: no_wall.append(dict(name=d['name'], x=round(float(c_[0])), y=round(float(c_[1])))); d['depth'] = (2 * T if d['ext'] else T) + DOOR_EXTRA - 0.02; continue
        _, p_, uv = best; nv = np.array([-uv[1], uv[0]]); c2 = c_ - nv * float((c_ - p_) @ nv); sg = 1.0 if uv @ u_ >= 0 else -1.0
        d['a'], d['b'] = c2 - sg * uv * L_ / 2, c2 + sg * uv * L_ / 2; n_snap += 1
        on_shell = shell_b.distance(Point(c2)) <= 2.0
        d['depth'] = (2 * T if (on_shell or d['ext']) else T) + DOOR_EXTRA - 0.02     # −0,02 px: запас на округление координат SVG (Ч-19: |глубина − стена| ≤ 1)
    drawn = unary_union([r['poly'].exterior for r in rooms if not r['open']] + [e['line'] for e in keep_E if e['cls'] != 'fglass']).buffer(1.5) if rooms else Polygon()
    n_pass_drop = 0; kept = []
    for d in doors:                                                # проход без нарисованной стены (обе стороны — открытые зоны) — не проём
        sg_ = LineString([d['a'], d['b']])
        if d['kind'] == 'pass' and sg_.length > 0 and sg_.intersection(drawn).length < 0.5 * sg_.length: n_pass_drop += 1; continue
        kept.append(d)
    doors = kept
    rep['проёмы_на_оси'] = dict(на_оси_своей_стены=n_snap, без_стены=no_wall, проходов_без_стены_снято=n_pass_drop)
    # ---- SVG
    def dpath(g):
        cs = np.array(g.coords); return 'M' + ' L'.join(f'{x:.1f} {y:.1f}' for x, y in cs)
    closed_bnd = unary_union([r['poly'].exterior for r in rooms if not r['open']]).buffer(1.5)
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" data-generator="bridge_convert {VERSION}">',
           f'<rect x="0" y="0" width="{W}" height="{H}" fill="#FFFFFF" stroke="none"/>', '<g id="underlay" display="none"/>', '<g id="rooms">']
    narc = 0
    for i, r in enumerate(sorted(rooms, key=lambda r: -r['poly'].area)):
        d, na = fit_arcs(np.array(r['poly'].simplify(0.5).exterior.coords), T); narc += na
        rid = re.sub(r'[^\w-]', '_', r['num'] or r['name'] or str(i)) + f'-{i}'
        attrs = f'id="room-b-{rid}" data-name="{r["num"] or r["name"]}" data-title="{r["name"]}" data-type="{r["type"]}" d="{d}" fill="{r["fill"]}"'
        out.append(f'<path {attrs} stroke="none"/>' if r['open'] else f'<path {attrs} stroke="{WALL}" stroke-width="{T:g}" stroke-linejoin="miter" stroke-miterlimit="8"/>')
    nfree = 0
    for i, e in enumerate(keep_E):
        if e['cls'] == 'fglass': continue                           # 0.30: стеклянная перегородка между открытыми зонами — тоже серая T под линией стекла
        g = e['line']; rest = g if e['cls'] == 'ext' else g.difference(closed_bnd)
        for j, part in enumerate(getattr(rest, 'geoms', [rest])):
            if part.is_empty or part.length < 3 or part.geom_type != 'LineString': continue
            Pp = np.array(part.coords)                                       # 0.30 (К6): у обрезанного конца ребро короче T — без предпоследней вершины
            while len(Pp) >= 3 and np.hypot(*(Pp[-1] - Pp[-2])) < T: Pp = np.delete(Pp, -2, axis=0)
            while len(Pp) >= 3 and np.hypot(*(Pp[0] - Pp[1])) < T: Pp = np.delete(Pp, 1, axis=0)
            if len(Pp) < 2 or (len(Pp) == 2 and np.hypot(*(Pp[1] - Pp[0])) < T): continue
            part = LineString(Pp)
            w = 2 * T if e['cls'] == 'ext' else T
            out.append(f'<path id="wall-b-{i}-{j}" data-class="{e["cls"]}" d="{dpath(part)}" fill="none" stroke="{WALL}" stroke-width="{w:g}" stroke-linecap="square"/>'); nfree += 1
    for i, c in enumerate(closes):
        if c['kind'] == 'cab' and sides_differ(c['line']):
            out.append(f'<path id="wall-b-cab-{i}" data-class="cab" d="{dpath(c["line"])}" fill="none" stroke="{WALL}" stroke-width="{T:g}" stroke-linecap="square"/>')
    for i, g in enumerate(curtains):
        base = g.buffer(T / 2, cap_style=2)
        out.append(f'<path id="curtain-b-{i}-base" data-type="curtain" d="M' + ' L'.join(f'{x:.1f} {y:.1f}' for x, y in base.exterior.coords[:-1]) + ' Z" fill="#FFFFFF" stroke="none"/>')
        out.append(f'<path id="curtain-b-{i}" data-type="curtain" d="{dpath(g)}" fill="none" stroke="{WALL}" stroke-width="2"/>')
    box_draw = unary_union([g_ for g_ in (poly_main(bx['box'].simplify(0.5)) for bx in col_boxes) if g_ is not None and g_.area >= 4]) if col_boxes else Polygon()
    clip_rep = dict(стекло=[], проёмы=[], окна=[])                   # 0.32 (ПК4-К13): стекло и проёмы обрезаются по коробу колонны (короб рисуется поверх стены)
    def clipped(g, kind, i):
        if box_draw.is_empty or not g.intersects(box_draw): return g
        x_ = g.intersection(box_draw); amt = x_.area if g.geom_type in ('Polygon', 'MultiPolygon') else x_.length
        if amt < (0.5 if g.geom_type in ('Polygon', 'MultiPolygon') else 0.5): return g
        c_ = x_.centroid; clip_rep[kind].append(dict(id=i, x=round(c_.x), y=round(c_.y), снято=round(amt / (pxm ** 2 if g.geom_type in ('Polygon', 'MultiPolygon') else pxm), 3)))
        return g.difference(box_draw)
    for i, dd in enumerate(doors):
        rect = LineString([dd['a'], dd['b']]).buffer(dd['depth'] / 2, cap_style=2, join_style=2)
        if rect.geom_type != 'Polygon' or rect.is_empty: continue
        rc_ = clipped(rect, 'проёмы', f'door-b-{i}')
        if rc_ is not rect:                                          # 0.32: проём под коробом — части вне короба
            for j, part in enumerate(g_ for g_ in getattr(rc_, 'geoms', [rc_]) if g_.geom_type == 'Polygon' and g_.area >= 1):
                out.append(f'<path id="door-b-{i}-{j}" data-type="door" data-kind="{dd["kind"]}" d="M' + ' L'.join(f'{x:.2f} {y:.2f}' for x, y in part.exterior.coords[:-1]) + f' Z" fill="{dd["fill"]}" stroke="none"/>')
            continue
        out.append(f'<path id="door-b-{i}" data-type="door" data-kind="{dd["kind"]}" d="M' + ' L'.join(f'{x:.2f} {y:.2f}' for x, y in rect.exterior.coords[:-1]) + f' Z" fill="{dd["fill"]}" stroke="none"/>')
    ncol = 0                                                       # 0.30: колонны 28 — не стены, рисуются заливкой цвета стены (map/rules/40 §2.8)
    for i, g in enumerate(col_free):                               # отдельно стоящая колонна с обшивкой — одним контуром
        g = poly_main(g.simplify(0.5))
        if g is None or g.area < 4: continue
        out.append(f'<path id="column-b-f{i}" data-type="column" d="M' + ' L'.join(f'{x:.1f} {y:.1f}' for x, y in np.array(g.exterior.coords)[:-1]) + f' Z" fill="{WALL}" stroke="none"/>'); ncol += 1
    for i, g in enumerate(blk_free):                               # 0.31: свободная колонна-блок без заливки 28 — выпуклой оболочкой блока
        g = poly_main(g.simplify(0.5))
        if g is None or g.area < 4: continue
        out.append(f'<path id="column-b-k{i}" data-type="column" data-kind="block" d="M' + ' L'.join(f'{x:.1f} {y:.1f}' for x, y in np.array(g.exterior.coords)[:-1]) + f' Z" fill="{WALL}" stroke="none"/>'); ncol += 1
    for i, bx in enumerate(col_boxes):                             # 0.31 (К-7): колонна или короб у стены — контуром короба
        g = poly_main(bx['box'].simplify(0.5))
        if g is None or g.area < 4: continue
        out.append(f'<path id="column-b-box{i}" data-type="column" data-kind="box" d="M' + ' L'.join(f'{x:.1f} {y:.1f}' for x, y in np.array(g.exterior.coords)[:-1]) + f' Z" fill="{WALL}" stroke="none"/>'); ncol += 1
    cf_u = unary_union(col_free + [bx['box'] for bx in col_boxes]) if (col_free or col_boxes) else Polygon()
    hid_u = unary_union([q['px'] for q in col_src if not q['drawn'] and q not in col_unif]) if col_src else Polygon()
    for i, R in enumerate(D['col_h']):
        for j, P in enumerate(R):
            g = Polygon(C.px(P)).buffer(0)
            if g.is_empty or g.geom_type != 'Polygon' or g.area < 4 or cf_u.contains(g.representative_point()): continue
            if not hid_u.is_empty and hid_u.contains(g.representative_point()): continue        # 0.31: скрытая в стене — часть стены, не рисуется
            out.append(f'<path id="column-b-{i}-{j}" data-type="column" d="M' + ' L'.join(f'{x:.1f} {y:.1f}' for x, y in np.array(g.exterior.coords)[:-1]) + f' Z" fill="{WALL}" stroke="none"/>'); ncol += 1
    for i, q in enumerate([q for q in col_unif if q['kind'] == 'block']):   # 0.31: однотипная колонна-блок, скрытая в стене, — дорисована (№89)
        g = poly_main(q['px'].simplify(0.5))
        if g is None or g.area < 4: continue
        out.append(f'<path id="column-b-u{i}" data-type="column" data-kind="same-type" d="M' + ' L'.join(f'{x:.1f} {y:.1f}' for x, y in np.array(g.exterior.coords)[:-1]) + f' Z" fill="{WALL}" stroke="none"/>'); ncol += 1
    rep['колонн'] = ncol
    out += ['</g>', '<g id="glass">']
    nwin = 0
    # 0.30: остеклённый фасад (витраж на 90 % наружного контура и больше) — одна замкнутая линия стекла 8 px у наружного края
    # фасада 2T (map/rules/60 §1, §2.5; Ч-27 «линия стекла», Ч-13); иначе — витражи по участкам, как раньше
    ring_done, fshare = False, 0.0
    big = max([q for q in getattr(shell_u, 'geoms', [shell_u]) if q.geom_type == 'Polygon'], key=lambda q: q.area, default=None) if rooms and not shell_u.is_empty else None
    fg_lines = [e['line'] for e in keep_E if e['cls'] == 'fglass']
    if big is not None and fg_lines:
        fshare = big.exterior.intersection(unary_union(fg_lines).buffer(1.5 * T)).length / max(big.exterior.length, 1e-6)
        if fshare >= 0.9:
            gr = poly_main(big.buffer((2 * T - 8) / 2, join_style=2))
            if gr is not None:
                d_, na_ = fit_arcs(clean_ring(np.array(gr.exterior.simplify(0.5).coords), 2 * T), T); narc += na_
                out.append(f'<path id="window-b-ring" data-type="facade-glass" d="{d_}" fill="none" stroke="{GLASS}" stroke-width="8"/>'); nwin += 1; ring_done = True
    rep['фасад'] = dict(витраж_доля_контура=round(fshare, 3), одной_линией_стекла=ring_done)
    for i, e in enumerate(keep_E):
        if e['cls'] == 'fglass':
            if ring_done: continue
            Q_ = ndimage.uniform_filter1d(e['P'], 5, axis=0, mode='nearest')        # сгладить ступени скелета
            lq_ = LineString(Q_) if len(Q_) >= 2 else None
            lc_ = clipped(lq_, 'окна', f'window-b-{i}') if lq_ is not None and lq_.length > 0 else lq_
            if lc_ is not lq_:                                       # 0.32: витраж под коробом — части вне короба, дуги — тем же подбором
                for j, part in enumerate(g_ for g_ in getattr(lc_, 'geoms', [lc_]) if g_.geom_type == 'LineString' and g_.length >= 2):
                    dd_, na_ = fit_arcs_open(np.array(part.coords), T); narc += na_
                    out.append(f'<path id="window-b-{i}-{j}" d="{dd_}" fill="none" stroke="{GLASS}" stroke-width="8"/>'); nwin += 1
                continue
            dd_, na_ = fit_arcs_open(Q_, T); narc += na_
            out.append(f'<path id="window-b-{i}" d="{dd_}" fill="none" stroke="{GLASS}" stroke-width="8"/>'); nwin += 1
        elif e['cls'] == 'glass':
            gl_ = clipped(e['line'], 'стекло', f'glasswall-b-{i}')
            if gl_ is not e['line']:                                 # 0.32 (ПК4-К13): стекло под коробом — части вне короба
                for j, part in enumerate(g_ for g_ in getattr(gl_, 'geoms', [gl_]) if g_.geom_type == 'LineString' and g_.length >= 2):
                    out.append(f'<path id="glasswall-b-{i}-{j}" d="{dpath(part)}" fill="none" stroke="{GLASS}" stroke-width="4"/>'); nwin += 1
                continue
            out.append(f'<path id="glasswall-b-{i}" d="{dpath(e["line"])}" fill="none" stroke="{GLASS}" stroke-width="4"/>'); nwin += 1
    rep['обрезано_по_коробу'] = clip_rep
    out += ['</g>', '<g id="furniture"/>', '<g id="icons"/>', '<g id="labels"/>', '</svg>']
    svg_text = '\n'.join(out); rep['помещений_по_шагам'] = dict(граней=rep['граней'], после_слияний=rep['помещений'], после_К6=len(rooms))
    if not getattr(a, 'no_post', False):                           # 0.33: шаги геометрии кода прохода v03 общими правилами (bridge_post.py)
        import bridge_post as BP
        arcs_ = BP.circles_from_curves(D['curves'], M, t, pxm)
        pk_px = [(float(q_[0]), float(q_[1]), s_) for (x_, y_, s_) in D['pk'] for q_ in [C.px([[x_, y_]])[0]]]
        bodies_px = [g_ for g_ in (Polygon(C.px(P)).buffer(0) for cls_ in ('ext', 'int') for R in D[cls_] for P in R if len(P) >= 3) if not g_.is_empty and g_.area > 1]
        glass_segs = [LineString(C.px(P)) for nm_, segs_ in D['glass'] for P in segs_ if len(P) >= 2] + \
                     [LineString(np.vstack([C.px(P), C.px(P)[:1]])) for R in D['glass_h'] for P in R if len(P) >= 3]
        bodyx = np.maximum.reduce([ext, inn, gl, fg, colm, colb])
        if os.environ.get('BRIDGE_DUMP'):                           # разработка: входы шагов — в файл (стенд bridge_post без тяжёлой части моста)
            import pickle; pickle.dump(dict(svg=svg_text, pxm=pxm, T=T, body=bodyx, k=k, arcs=arcs_, pk_px=pk_px, bodies_px=bodies_px, glass_segs=glass_segs), open(os.environ['BRIDGE_DUMP'], 'wb'))
        svg_text, prep, plog = BP.run(svg_text, pxm, T, body=bodyx, k=k, arcs=arcs_, pk_px=pk_px, bodies_px=bodies_px, glass_segs=glass_segs)
        del bodyx
        rep['шаги_v03'] = prep; rep['дуги_плана'] = [dict(имя=c_['name'], грани_px=c_['faces'], класс=c_['cls']) for c_ in arcs_]
        if a.report:
            with open(os.path.splitext(a.report)[0] + '_шаги.txt', 'w', encoding='utf-8') as f_: f_.write('\n'.join(plog) + '\n')
        rep['помещений_по_шагам']['в_SVG'] = prep['самопроверка']['помещений']; rep['помещений'] = prep['самопроверка']['помещений']   # КМ-11 (ПК4-К10): после всех снятий
    open(a.out, 'w', encoding='utf-8').write(svg_text)
    rep.update(закрытых=sum(not r['open'] for r in rooms), открытых=sum(r['open'] for r in rooms), дуг=narc, свободных_стен=nfree, стекла=nwin,
               типы=collections.Counter(r['type'] for r in rooms), без_номера=[r['name'] or '?' for r in rooms if not r['num']])
    rep['помещения'] = [dict(num=r['num'], name=r['name'], type=r['type'], open=r['open'], m2=round(r['poly'].area / pxm ** 2, 1),
                             share=r['share']) for r in rooms]
    if a.debug:
        dbg = np.full((H, W, 3), 255, np.uint8)
        dbg[cv2.resize((walls > 0).astype(np.uint8), (W, H), interpolation=cv2.INTER_AREA) > 0] = (225, 225, 225)
        rng = np.random.default_rng(1)
        for r in rooms:
            col = tuple(int(v) for v in rng.integers(150, 250, 3)); cv2.fillPoly(dbg, [np.round(np.array(r['poly'].exterior.coords) * 8).astype(np.int32)], col, shift=3)
        colE = {'ext': (60, 60, 60), 'int': (110, 110, 110), 'glass': (230, 150, 40), 'fglass': (200, 90, 0), 'light2': (0, 140, 255), 'light1': (120, 200, 255), 'door': (0, 120, 0)}
        for e in E: cv2.polylines(dbg, [np.round(e['P'] * 8).astype(np.int32)], False, colE.get(e['cls'], (0, 0, 0)), 1, shift=3)
        for e in keep_E: cv2.polylines(dbg, [np.round(np.array(e['line'].coords) * 8).astype(np.int32)], False, colE.get(e['cls'], (0, 0, 0)), 3, shift=3)
        for c in closes: cv2.polylines(dbg, [np.round(np.array(c['line'].coords) * 8).astype(np.int32)], False, {'pass': (0, 0, 230), 'cab': (200, 0, 200)}[c['kind']], 2, shift=3)
        for s in seps: cv2.polylines(dbg, [np.round(np.array(s.coords) * 8).astype(np.int32)], False, (0, 200, 200), 1, shift=3)
        for d in doors: cv2.line(dbg, tuple(np.round(d['a']).astype(int)), tuple(np.round(d['b']).astype(int)), (0, 200, 0) if d['kind'] == 'door' else (0, 0, 255), 4)
        for e in ends: cv2.circle(dbg, tuple(np.round(e['p']).astype(int)), 4, (0, 0, 255), 1)
        for r in rooms:
            c = r['poly'].representative_point(); cv2.putText(dbg, f"{r['num'] or r['name'][:10]}{'' if not r['open'] else '*'}", (int(c.x) - 10, int(c.y)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 1)
        cv2.imwrite(a.debug + '_graph.png', dbg)
    # 0.33 (КМ-1): учёт дверей плана — каждая дверь плана: проём карты или причина
    got = collections.Counter(d['src'] for d in doors if 'src' in d)
    why_ = collections.Counter(door_why.get(i_, 'не учтена — ошибка учёта моста') for i_ in range(len(D['door'])) if not got.get(i_))
    rep['двери_плана'] = dict(всего=len(D['door']), проёмов=sum(1 for i_ in range(len(D['door'])) if got.get(i_)),
                              по_прямоугольнику=sum(1 for d in doors if d.get('how') == 'прямоугольник'), две_створки=sum(1 for d in doors if d.get('how') == 'две створки'),
                              причины=dict(why_), линий_слоя_дверей_без_блока=len(D['door_misc']))
    wn = []                                                        # 0.33 (КМ-9): ширина проёма против ширины в имени блока («проём_1199x119», маршрут Revit)
    for d in doors:
        m_ = re.search(r'про[её]м_(\d{3,4})x\d+', str(d.get('name', '')))
        if m_ and 'src' in d: wn.append((round(float(np.hypot(*(np.asarray(d['b']) - np.asarray(d['a'])))) / pxm - int(m_.group(1)) / 1000.0, 3), d['name'], d.get('how')))
    rep['двери_плана']['ширина_против_имени'] = dict(дверей=len(wn), больше_0_1_м=[dict(разница_м=a_, имя=b_, как=c_) for a_, b_, c_ in wn if abs(a_) > 0.1])
    rep['двери_плана']['две_створки_места'] = [dict(x=round(float((np.asarray(d['a'])[0] + np.asarray(d['b'])[0]) / 2)), y=round(float((np.asarray(d['a'])[1] + np.asarray(d['b'])[1]) / 2)),
                                                   ширина_м=round(float(np.hypot(*(np.asarray(d['b']) - np.asarray(d['a'])))) / pxm, 2)) for d in doors if d.get('how') == 'две створки']
    rep['стоп'] = stops
    return rep

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('dxf'); ap.add_argument('out'); ap.add_argument('--px-per-m', type=float, default=52.49); ap.add_argument('--frame')
    ap.add_argument('--T', type=float, default=6.0); ap.add_argument('--k', type=int, default=2); ap.add_argument('--report')
    ap.add_argument('--size', help='W,H холста; по умолчанию — по габариту + поля'); ap.add_argument('--debug', help='префикс картинок разбора')
    ap.add_argument('--simplify', type=float, default=0.6, help='допуск упрощения осей, px (Дуглас — Пекер)')
    ap.add_argument('--no-regularize', action='store_true', help='без шага К6 — только для сравнения «до/после» (стенд)')
    ap.add_argument('--no-stop', action='store_true', help='СТОП не меняет код выхода (места всё равно в отчёте, ключ `стоп`)')
    ap.add_argument('--no-post', action='store_true', help='0.33: без шагов bridge_post (стенд «до/после»)')
    ap.add_argument('--cfg', help='0.33: настройка клиента JSON: pk_labels — надписи короба ПК (по умолчанию «ПК»)')
    a = ap.parse_args(); rep = convert(a)
    if a.report: json.dump(rep, open(a.report, 'w', encoding='utf-8'), ensure_ascii=False, indent=1, default=str)
    print(json.dumps({k_: v for k_, v in rep.items() if k_ != 'помещения'}, ensure_ascii=False, default=str))
    if rep.get('стоп'):
        print(f"СТОП: {len(rep['стоп'])} мест(а) — {'; '.join(str(z.get('что')) + f' ({z.get(chr(120))}, {z.get(chr(121))})' for z in rep['стоп'][:8])}", file=sys.stderr)
        if not a.no_stop: sys.exit(3)

if __name__ == '__main__': main()
