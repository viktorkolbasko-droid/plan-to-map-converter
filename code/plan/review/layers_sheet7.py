# Layer sheets of the final engineering plan (code 007): per group of layers, every class of objects in its own colour
# over the source sheet in grey. An object draws its own primitives and the boundary lines it shares (п. 240).
#   python3 review/layers_sheet7.py --gray=0.25 --out=DIR --prefix=v7        (floor folder)
import pickle, collections, math, sys, json
import numpy as np, pymupdf
from PIL import Image, ImageDraw, ImageFont
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import load, pts, cfg
Image.MAX_IMAGE_PIXELS = None
Z = 4.0                                   # px per pt
X0, Y0, X1, Y1 = cfg.WIN
W, H = int((X1 - X0) * Z), int((Y1 - Y0) * Z)
P = load()
inst = pickle.load(open('inst_final.pkl', 'rb'))
free = pickle.load(open('assign2.pkl', 'rb'))[1]
from common import walls_file
walls = pickle.load(open(walls_file(), 'rb'))['Wpt']
cls = pickle.load(open('cls.pkl', 'rb'))
wallprims = pickle.load(open('wallprims.pkl', 'rb'))
FB = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'; FR = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
F = {k: ImageFont.truetype(FB if b else FR, s) for k, (s, b) in
     dict(t=(44, True), h=(27, True), b=(22, True), r=(21, False), s=(19, False)).items()}

# ---- faded source: contrast halved (255 - (255 - v) / 2)
pg = pymupdf.open(cfg.PDF)[0]
pix = pg.get_pixmap(matrix=pymupdf.Matrix(Z, Z), alpha=False)
src = Image.frombytes('RGB', (pix.width, pix.height), pix.samples).crop((int(X0 * Z), int(Y0 * Z), int(X0 * Z) + W, int(Y0 * Z) + H))
a = np.asarray(src).astype(np.float32)
BASE = Image.fromarray((255 - (255 - a) * 0.5).astype(np.uint8))
# --gray=K: the source in grey, its ink at K of the original darkness (03.10.2026: K = 0.25 - lines barely visible)
GRAY = next((float(x.split('=')[1]) for x in sys.argv if x.startswith('--gray=')), None)
if GRAY is not None:
    g = a @ np.array([0.299, 0.587, 0.114], dtype=np.float32)
    g = 255 - (255 - g) * GRAY
    BASE = Image.fromarray(np.repeat(g[..., None], 3, axis=2).astype(np.uint8))
NOBASE = '--nobase' in sys.argv
if NOBASE: BASE = Image.new('RGB', (W, H), 'white')

def T(x, y): return ((x - X0) * Z, (y - Y0) * Z)
def hexc(h): return tuple(int(h[i:i + 2], 16) for i in (1, 3, 5))

from own7 import glass_gaps, cut_line
CUT = glass_gaps(inst)                     # (строка 172) the glass line is cut in a glass door's opening, as in the DXF
def draw_prims(dr, ids, col, lw=2, fill_a=90):
    c = hexc(col)
    for i in ids:
        p = P[i]
        if p[0] == 'l' and i in CUT:
            for seg in cut_line(p[4], CUT[i]): dr.line([T(*v) for v in seg], fill=c + (255,), width=lw)
            continue
        q = [T(*v) for v in pts(p)]
        if len(q) < 2: continue
        if p[0] == 'qu':
            if p[3] is not None: dr.polygon(q, fill=c + (fill_a,))
            dr.line(q + [q[0]], fill=c + (255,), width=max(1, lw - 1))
        else:
            dr.line(q, fill=c + (255,), width=lw)

def draw_poly(dr, g, col, fa=150):
    c = hexc(col)
    for poly in getattr(g, 'geoms', [g]):
        ext = [T(*v) for v in poly.exterior.coords]
        dr.polygon(ext, fill=c + (fa,))
        for r in poly.interiors: dr.polygon([T(*v) for v in r.coords], fill=(255, 255, 255, 0))
        dr.line(ext, fill=c + (255,), width=3)
        for r in poly.interiors: dr.line([T(*v) for v in r.coords], fill=c + (255,), width=3)

OPN = [q for q in inst if q['key'] == 'opening' and q.get('poly')]
def draw_open(dr, c):
    cc = hexc(c)
    for o in OPN:
        q = [T(x, y) for x, y in o['poly']]
        dr.polygon(q, fill=cc + (55,)); dr.line(q + [q[0]], fill=cc + (255,), width=6)
byk = collections.defaultdict(list)
for q in inst: byk[q['key']].append(q)
def ids_of(keys, layer=None):
    out = []
    for k in keys:
        for q in byk.get(k, []):
            if layer is None or q['layer'] == layer: out += list(q['prims']) + list(q.get('shared', []))
    return out
def n_of(keys, layer=None): return sum(1 for k in keys for q in byk.get(k, []) if layer is None or q['layer'] == layer)

# texts of the drawing (not the title block, not the axis bubbles)
words = []
for w in pg.get_text('words'):
    r = pymupdf.Rect(w[:4]) * pg.rotation_matrix
    if not (cfg.SHEET_IN[0] <= r.x0 and r.x1 <= cfg.SHEET_IN[2] and cfg.SHEET_IN[1] <= r.y0 and r.y1 <= cfg.SHEET_IN[3]): continue
    if any(b[0] <= r.x0 and r.x1 <= b[2] and b[1] <= r.y0 and r.y1 <= b[3] for b in cfg.AXIS_BOXES): continue
    words.append((r, w[4]))
import re
lev = [w for w in words if re.fullmatch(r'[+-]?\d+[.,]\d{3}', w[1])]
pk = [w for w in words if w[1].startswith('ПК')]
oth = [w for w in words if w not in lev and w not in pk]

# ---- entries: (colour, layer, what, class / how, count, painter)
def E(col, lay, what, how, n, fn): return dict(col=col, lay=lay, what=what, how=how, n=n, fn=fn)
def P_(keys, layer=None, lw=2, fa=90): return lambda dr, c: draw_prims(dr, ids_of(keys, layer), c, lw, fa)
def Wl(k): return lambda dr, c: [draw_poly(dr, g, c) for g in walls[k]]
def Txt(ws): return lambda dr, c: [dr.rectangle([T(r.x0, r.y0), T(r.x1, r.y1)], outline=hexc(c) + (255,), width=3, fill=hexc(c) + (60,)) for r, _ in ws]
def ids_cls(k): return [i for i, c in enumerate(cls) if c == k]
area = lambda k: sum(g.area for g in walls[k]) * cfg_mm2
from common import MM_PER_PT
cfg_mm2 = (MM_PER_PT / 1000) ** 2

G = []
G.append(('1. Стены и перегородки', [
    E('#d62728', 'A-21', 'стены наружные', 'класс ext: тела со штриховкой по оси Д и у лестничного блока; вся полукруглая стена лестницы — один тип ext по зонам WALL_ZONES (решение владельца 03.10.2026: «Тут должен быть один тип стены»)', f'{len(walls["ext"])} тел, {area("ext"):.1f} м²', Wl('ext')),
    E('#1f77b4', 'A-221', 'стены капитальные', 'класс cap: тело с серой штриховкой 45°; ящик между шкафами у лифтов — не стена (NOT_WALL_ZONES, владелец: «Там никаких стен не должно быть»)', f'{len(walls["cap"])} тел, {area("cap"):.1f} м²', Wl('cap')),
    E('#2ca02c', 'A-222', 'перегородки ГКЛ со штриховкой', 'класс gkl: тело с чёрным X-узором; косые перегородки санузла — DIAG_ZONES', f'{len(walls["gkl"])} тел, {area("gkl"):.1f} м²', Wl('gkl')),
    E('#ff7f0e', 'A-223', 'перегородки штучные', 'класс blk: тело с чёрной одиночной штриховкой 45°', f'{len(walls["blk"])} тел, {area("blk"):.1f} м²', Wl('blk')),
    E('#8c564b', 'A-21…A-223', 'грани стен линиями', 'wallline: грани стен вне тела и линии по контуру тела (fix7, F11)', f'{n_of(["wallline"])} наборов', P_(['wallline'], lw=3)),
    E('#00a050', 'A-222', 'перегородки ГКЛ без штриховки (полые)', 'gklpart: двойная линия с рисками стоек или без — гипсокартон (владелец 03.10.2026: «полые стены… гипсокартон»); fix7, F11', f'{n_of(["gklpart"])} перегородок', P_(['gklpart'], lw=3)),
    E('#0060ff', 'A-22G', 'перегородки стеклянные', 'glasspart: одиночная сплошная линия — остекление (владелец: «Стена сплошной тонкой линии: это, видимо, остекление»); fix7, F11', f'{n_of(["glasspart"])} перегородок', P_(['glasspart'], lw=3)),
    E('#00b5b5', 'A-22G', 'ограждение атриума', 'railing: контур проёма атриума — линии ограждения; fix7, F11', f'{n_of(["railing"])}', P_(['railing'], lw=3)),
    E('#9467bd', 'A-22G', 'перегородки без типа', 'lpart / lpartc: должно быть 0 — каждая перегородка с типом (проверка S28*)', f'{n_of(["lpartc","lpart"])} объектов', P_(['lpartc', 'lpart'], lw=4)),
    E('#e377c2', 'A-22G', 'перегородки витражные и остекление', 'glass: перегородки из стоек-профилей и панелей — рамки MANUAL; серо-голубые полосы остекления — элемент по цвету', f'{n_of(["glass"])} объектов', P_(['glass'], lw=3, fa=120)),
    E('#17becf', 'A-31', 'витражи', 'facade: полосы двух линий FACADES — основной витраж и витраж Ecom (середина полукруглой стены — больше не витраж)', f'{n_of(["facade"])} объекта', P_(['facade'], lw=2, fa=110)),
    E('#bcbd22', 'A-28', 'колонны', 'column: двутавры по эталону семейства (заливка 4,08 × 7,2 pt или контур двутавра), Т-профили за северной стеной парами, круглые ⌀320 колоннады; fix7, F1', f'{n_of(["column"])} объектов', P_(['column'], lw=3, fa=140)),
    E('#6a00aa', 'A-23', 'проёмы: лестничные клетки, атриум', 'opening: только там, где проём есть в перекрытии этого этажа (решение владельца 04.10.2026): клетка — помещение, где лестница не меньше трети площади; марш только вверх и короткий марш вне клетки — без проёма; атриум — замкнутый контур ограждения. Только контур, без заливки; fix7, F10', f'{len(OPN)}', draw_open),
]))
G.append(('2. Двери, лестницы, лифты', [
    E('#d62728', 'A-32', 'двери распашные', 'door: дуга открывания + полотно у косяков (doors2.py)', f'{sum(1 for q in byk.get("door", []) if not q.get("glass"))}',
      lambda dr, c: draw_prims(dr, [i for q in byk.get('door', []) if not q.get('glass') for i in list(q['prims']) + list(q.get('shared', []))], c, 3)),
    E('#00a6d6', 'A-32', 'двери стеклянные', 'door + glass_gap: в стеклянной перегородке — проём, линия стекла рвётся по ширине двери, дверь — в стиле стекла (решение владельца 04.10.2026); fix7, F14', f'{sum(1 for q in byk.get("door", []) if q.get("glass"))}',
      lambda dr, c: draw_prims(dr, [i for q in byk.get('door', []) if q.get('glass') for i in list(q['prims']) + list(q.get('shared', []))], c, 5)),
    E('#ff7f0e', 'A-32', 'двери «полотно и хорда», стеклянные', 'door45: двери без дуги (doors45.py) и стеклянные двери витражной перегородки — синий контур (элемент по цвету)', f'{n_of(["door45"])}', P_(['door45'], lw=4)),
    E('#2ca02c', 'A-32', 'фурнитура дверей', 'doorhw: ручки, упоры, пороги (DOOR_HARDWARE) и ручки на косых перегородках (MISC_GROUPS)', f'{n_of(["doorhw"])}', P_(['doorhw'], lw=4, fa=160)),
    E('#1f77b4', 'A-24', 'лестницы', 'stair: 4 рамки MANUAL (в круглой башне, северо-восточная, у санузлов, малая северная) и марш детектора у оси 7', f'{n_of(["stair"])}', P_(['stair'], lw=2, fa=80)),
    E('#e377c2', 'A-66', 'лифты', 'lift: кабина — крест в контуре (правило E); два лифта у оси 4 и квадрат за витражом у осей 12–13 / Б', f'{n_of(["lift"])}', P_(['lift'], lw=3, fa=80)),
]))
G.append(('3. Инженерное оборудование', [
    E('#d62728', 'A-56', 'конвекторы', 'convector: пачки серых штрихов восстановлены в заливку (strokefill.py) у витража; повёрнутый у дуги СВ — MISC_GROUPS', f'{n_of(["convector"])}', P_(['convector'], lw=3, fa=170)),
    E('#ff7f0e', 'A-68', 'пожарные шкафы', 'fire: ПК1, ПК3, ПК4 и шкаф у отдела кадров — рамки MANUAL с пунктиром открывания дверцы', f'{n_of(["fire"])}', P_(['fire'], lw=4, fa=170)),
    E('#1f77b4', 'A-74', 'унитазы', 'wc: семейства по эталонам этого листа — унитаз с бачком и подвесной', f'{n_of(["wc"])}', P_(['wc'], lw=4, fa=140)),
    E('#9467bd', 'A-74', 'умывальники', 'sink / wcsink: круглый умывальник (эталон) и оранжевые тумбы с чашей в кабинах (элемент по цвету)', f'{n_of(["sink","wcsink"])}', P_(['sink', 'wcsink'], lw=3, fa=140)),
    E('#2ca02c', 'A-74', 'аксессуары санузлов', 'wcacc / loose: остальное внутри SANZONES — держатели, поручни; крючки у санузлов (MISC_GROUPS)', f'{n_of(["wcacc"]) + n_of(["loose"], "A-74----E-")}', lambda dr, c: draw_prims(dr, ids_of(['wcacc']) + ids_of(['loose'], 'A-74----E-'), c, 3, 140)),
    E('#7f7f7f', 'A-52 · A-53 · A-57 · A-61 · A-77', 'водоотвод, водоснабжение, вентиляция, щиты, серверное', 'на этом этаже нет', '0', lambda dr, c: None),
]))
G.append(('4. Мебель, оборудование, озеленение, пол', [
    E('#1f77b4', 'A-82', 'кресла и стулья', 'chair: семейства по эталонам листа (кресло офисное, стул переговорной), повёрнутые — MISC_GROUPS и рамка MANUAL', f'{n_of(["chair"])}', P_(['chair'], lw=2)),
    E('#d62728', 'A-82', 'кресла мягкие, диван', 'armchair / sofa: рамки MANUAL', f'{n_of(["armchair","sofa"])}', P_(['armchair', 'sofa'], lw=3, fa=120)),
    E('#ff7f0e', 'A-82', 'столы рабочие (бенчи)', 'desk: тёплая светлая или светло-зелёная (0,87/0,92/0,81) столешница ≥ 1300 × 550–900 мм', f'{n_of(["desk"])}', P_(['desk'], lw=2, fa=120)),
    E('#8c564b', 'A-82', 'столы-контуры и прочие столы', 'desk_o / desk_src / benchend: замкнутые контуры столов у сидений (fix7, F2 — правило владельца «стул и стол — пара»), столы Ecom серым контуром, столы по исходнику, торцы бенчей', f'{n_of(["desk_o","desk_src","benchend"])}', P_(['desk_o', 'desk_src', 'benchend'], lw=3, fa=100)),
    E('#9467bd', 'A-82', 'столы переговорных и круглые', 'mtable / rtable: столы переговорных, круглый стол, модульная мебель Ecom (MANUAL), круглые столы и пуфы (правило C)', f'{n_of(["mtable","rtable"])}', P_(['mtable', 'rtable'], lw=3, fa=110)),
    E('#ff1493', 'A-82', 'мониторы переговорных', 'monitor: узкий замкнутый прямоугольник поперёк торца стола (владелец 03.10.2026: «мониторы для конференц-связи… впритык к столу»); fix7, F3', f'{n_of(["monitor"])}', P_(['monitor'], lw=4, fa=170)),
    E('#17becf', 'A-82', 'экраны и кабель-каналы', 'screen / fscreen: тёмная полоса вдоль середины бенча, экраны между местами', f'{n_of(["screen","fscreen"])}', P_(['screen', 'fscreen'], lw=3, fa=160)),
    E('#e377c2', 'A-82', 'мебель с заливкой и по контуру', 'furn_src: заливка цвета мебели (правило F) и замкнутые контуры мебельного размера без детектора (fix7, F2, F3: «уточнить»)', f'{n_of(["furn_src"])}', P_(['furn_src'], lw=3, fa=120)),
    E('#bcbd22', 'A-76', 'шкафы, гардеробы, встроенная мебель', 'wardrobe / rack: шкафы-гардеробы со штангой и плечиками по секциям, шкафы вдоль перегородок, серая встроенная мебель (MANUAL, MISC_GROUPS)', f'{n_of(["wardrobe","rack"])}', P_(['wardrobe', 'rack'], lw=3, fa=110)),
    E('#006400', 'A-72', 'ресепшн', 'reception: стойка напротив лифтов (MANUAL, уточнить)', f'{n_of(["reception"])}', P_(['reception'], lw=3, fa=120)),
    E('#2ca02c', 'A-89', 'растения', 'plant: цвет растений листа 0,67/0,77/0,72 (PLANT_COLOR)', f'{n_of(["plant"])}', P_(['plant'], lw=2, fa=110)),
    E('#7f7f7f', 'A-43 · A-92', 'ковры, заливки зон', 'на этом этаже нет', '0', lambda dr, c: None),
]))
G.append(('5. Помещения, тексты, служебное', [
    E('#9467bd', 'A-93', 'границы помещений', 'roomsep: пурпурный пунктир (0,5; 0; 0,5) — разделители Revit (COLOR_ELEMENTS)', f'{n_of(["roomsep"])} штрихов', P_(['roomsep'], lw=4)),
    E('#2ca02c', 'A-69', 'знаки у дверей', 'sign: зелёный треугольник и прямоугольник у двери, назначение неизвестно', f'{n_of(["sign"])}', P_(['sign'], lw=4, fa=170)),
    E('#d62728', 'A-90', 'названия и надписи', 'текст PDF внутри чертежа: названия помещений, «ВВЕРХ», «Ecom 282 м.кв.»', f'{len(oth)} слов', Txt(oth)),
    E('#ff7f0e', 'A-91', 'отметки уровня и их рамки', 'текст вида ±N.NNN; рамки вокруг него — MANUAL mark', f'{len(lev)} + {n_of(["mark"], "A-91----E-")} рамок', lambda dr, c: (Txt(lev)(dr, c), draw_prims(dr, ids_of(['mark'], 'A-91----E-'), c, 3, 60))),
    E('#8c564b', 'A-68', 'подписи «ПК»', 'текст, начинающийся с «ПК»', f'{len(pk)}', Txt(pk)),
    E('#1f77b4', 'A-AX', 'оси, марки, размеры', 'класс axis / dim: в DXF регенерируются из cfg', f'{len(ids_cls("axis"))} + {len(ids_cls("dim"))} примитивов', lambda dr, c: draw_prims(dr, ids_cls('axis') + ids_cls('dim'), c, 2, 60)),
    E('#17becf', 'A-AX', 'маркеры у осей', 'axmark: мелочь в рамках OUTSIDE_BOXES', f'{n_of(["axmark"])}', P_(['axmark'], lw=3)),
    E('#e377c2', 'A-AXM', 'служебные метки', 'mark: кресты в углах (правило K2, MISC_GROUPS), маски Revit — не объекты плана', f'{n_of(["mark"], "A-AXM---E-")}', P_(['mark'], 'A-AXM---E-', lw=4)),
]))
# 6: unknowns by name (misc with a name and the S-circles), loose, free primitives
misc = byk['misc'] + byk.get('equip', [])
names = collections.Counter(q['name'].replace('Неизвестное: ', '').replace(' (по исходнику)', '') for q in misc)
top = [n for n, _ in names.most_common(11)]
PAL = ['#d62728', '#1f77b4', '#ff7f0e', '#2ca02c', '#9467bd', '#8c564b', '#e377c2', '#17becf', '#bcbd22', '#006400', '#00008b']
rows6 = []
for n, c in zip(top, PAL):
    sel = [q for q in misc if q['name'].replace('Неизвестное: ', '').replace(' (по исходнику)', '') == n]
    rows6.append(E(c, 'A-00', n, 'нарисовано как в исходнике, названо по картинке места (MISC_GROUPS, MANUAL), класс не определён', f'{len(sel)}',
                   (lambda s: lambda dr, cc: draw_prims(dr, [i for q in s for i in q['prims']], cc, 4, 170))(sel)))
rows6.append(E('#000000', 'A-00', 'россыпь мелочи', 'loose: мелкие штрихи без объекта', f'{n_of(["loose"], "A-00----E-")}', P_(['loose'], 'A-00----E-', lw=4)))
fr = [i for i in free if cls[i] == 'obj' and i not in wallprims]
rows6.append(E('#808000', '—', 'без владельца', 'свободные примитивы, не вошедшие ни в объект, ни в стену (белые маски и линии под заливками — на бумаге не видны)', f'{len(fr)} примитивов', lambda dr, c: draw_prims(dr, fr, c, 3, 60)))
G.append(('6. Нераспознанное и не классифицированное', rows6))

# ---- sheets
LW = 1500
for gi, (title, rows) in enumerate(G, 1):
    if '--only1' in sys.argv and gi != 1: continue
    ov = Image.new('RGBA', (W, H), (0, 0, 0, 0)); dr = ImageDraw.Draw(ov)
    for e in rows: e['fn'](dr, e['col'])
    img = Image.alpha_composite(BASE.convert('RGBA'), ov).convert('RGB')
    sheet = Image.new('RGB', (W + LW, max(H, 200 + 150 * len(rows)) + 120), 'white'); sheet.paste(img, (0, 120))
    d = ImageDraw.Draw(sheet)
    d.text((24, 30), f'клиент А, 4 этаж — код 007-черновик — {title}', font=F['t'], fill=(0, 0, 0))
    d.line([(W, 120), (W, sheet.height)], fill=(200, 200, 200), width=2)
    y = 140; x = W + 30
    d.text((x, y), 'Слой · что · класс и признак · число', font=F['h'], fill=(0, 0, 0)); y += 50
    for e in rows:
        c = hexc(e['col'])
        d.rectangle([x, y + 4, x + 46, y + 40], fill=c if e['n'] != '0' else (230, 230, 230), outline=(0, 0, 0))
        d.text((x + 62, y), f"{e['lay']}  {e['what']}", font=F['b'], fill=(0, 0, 0))
        d.text((x + 62, y + 28), f"число: {e['n']}", font=F['s'], fill=(80, 80, 80))
        # wrap the rule text
        words_, line, yy = e['how'].split(), '', y + 54
        for w_ in words_:
            if d.textlength(line + ' ' + w_, font=F['r']) > LW - 110: d.text((x + 62, yy), line, font=F['r'], fill=(40, 40, 40)); yy += 26; line = w_
            else: line = (line + ' ' + w_).strip()
        if line: d.text((x + 62, yy), line, font=F['r'], fill=(40, 40, 40)); yy += 26
        y = yy + 18
    note = ('Без подложки: только распознанные объекты' if NOBASE else
            f'Подложка — исходник клиента в сером, линии — {round(GRAY * 100)} % исходной насыщенности' if GRAY is not None else
            'Подложка — исходник PDF, контраст ослаблен вдвое')
    d.text((x, sheet.height - 60), note, font=F['s'], fill=(120, 120, 120))
    OD = next((x.split('=', 1)[1] for x in sys.argv if x.startswith('--out=')), '.'); PFX = next((x.split('=', 1)[1] for x in sys.argv if x.startswith('--prefix=')), 'v7')
    out = os.path.join(OD, f'{PFX}_слой_{gi}' + ('_без_подложки' if NOBASE else '_серая_подложка' if GRAY is not None else '') + '.png')
    sheet.save(out, optimize=True); print(out, sheet.size, [(e['what'], e['n']) for e in rows])
