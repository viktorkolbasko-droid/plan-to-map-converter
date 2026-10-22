"""Six review sheets of the result by layer groups, each class in its own colour, legend «Слой · что · признак · число».
With the source underlay at half strength, or without it. usage: python3 sheets_layers.py out_dir [nounder] (code 009: run.sh sheets)"""
import pickle, sys, collections, math, os
import numpy as np, pymupdf
from PIL import Image, ImageDraw, ImageFont
from shapely.geometry import LineString, Polygon
import os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import sheet; from e7_comp import geom
VAR = os.environ.get('VARIANT', 'detail')
OUTD = sys.argv[1]; UNDER = not (len(sys.argv) > 2 and sys.argv[2] == 'nounder'); os.makedirs(OUTD, exist_ok=True)
from e7_comp import load_prims; P = load_prims(); T = P['T']; P = P['P']
O = pickle.load(open('objects.pkl', 'rb'))['objs']; from e7_comp import load_walls; W = load_walls()['bodies']
_B = sheet.RENDER_BOX or tuple(pymupdf.open(sheet.PDF)[0].rect)        # cfg.OCG_RENDER_BOX: the part of the sheet on the review sheets
X0, Y0, X1, Y1 = _B; Z = float(os.environ.get('Z', '3')); LW = 900
F = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 17); FB = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 22)
pg = pymupdf.open(sheet.PDF)[0]
def base():
    w, h = int((X1 - X0) * Z), int((Y1 - Y0) * Z)
    if UNDER:
        pix = pg.get_pixmap(matrix=pymupdf.Matrix(Z, Z), clip=pymupdf.Rect(X0, Y0, X1, Y1), alpha=False)
        im = Image.frombytes('RGB', (pix.width, pix.height), pix.samples)
        im = Image.blend(Image.new('RGB', im.size, (255, 255, 255)), im.convert('L').convert('RGB'), 0.65)   # grey, 35 % brighter (owner 06.10)
    else: im = Image.new('RGB', (w, h), (255, 255, 255))
    return im
def Tr(xy): return [((x - X0) * Z, (y - Y0) * Z) for x, y in xy]
def draw_prims(d, ids, col, width=2):
    for i in ids:
        p = P[i]
        if p['kind'] == 'line' and len(p['p']) >= 2: d.line(Tr(p['p']), fill=col + (255,), width=width)
        elif p['kind'] in ('fill', 'wline'):
            g = geom(p)
            for part in getattr(g, 'geoms', [g]):
                if part.geom_type == 'Polygon': d.polygon(Tr(part.exterior.coords), fill=col + (110,), outline=col + (255,))
def draw_poly(d, g, col, a=170):
    for part in getattr(g, 'geoms', [g]):
        if part.geom_type == 'Polygon':
            d.polygon(Tr(part.exterior.coords), fill=col + (a,), outline=col + (255,))
            for h in part.interiors: d.polygon(Tr(h.coords), fill=(255, 255, 255, 200))
# class rows: (layer, what, sign, colour, selector)
def objsel(f): return [o for o in O if f(o)]
WL = {'gkl': ('A-222', 'перегородки каркасные ГКЛ', 'X-узор или зигзаг между линиями слоёв стен', (230, 120, 20)),
      'blk': ('A-223', 'перегородки штучные', 'одиночная штриховка под углом', (40, 150, 60)),
      'cap': ('A-221', 'капитальные: торцы-заливки у ядра', 'чёрная заливка слоя «Стены», не колонна', (200, 30, 30)),
      'column': ('A-28', 'колонны и пилоны', 'чёрная заливка «Стены» ≥ 100 pt², 2A/P ≥ 5', (70, 70, 70))}
SHEETS = [
 ('1 Стены и перегородки', [
   ('walls', 'gkl'), ('walls', 'blk'), ('walls', 'cap'), ('walls', 'column'),
   ('obj', ('A-221', 'ядро: блоки существующих конструкций — замкнутые полигоны', 'грани контура ядра под штриховкой зоны', (130, 60, 150), lambda o: o['key'] == 'coreblock')),
   ('obj', ('A-221', 'контур ядра: линии, которые ничего не замыкают', 'линии слоя «Стены» вне граней блоков', (150, 0, 0), lambda o: o['key'] == 'coreline' and o.get('draw'))),
   ('obj', ('A-22G', 'остекление перегородок', 'синие и голубые заливки слоёв стен', (0, 110, 230), lambda o: o['key'] == 'glass')),
   ('obj', ('A-22G', 'перегородки без штриховки', 'линии слоёв стен вне тел', (120, 70, 200), lambda o: o['key'] == 'lpart')),
   ('obj', ('A-222', 'линии стен: отделка, второй контур', '≤ 0,6 pt вдоль тела, параллельно', (240, 170, 60), lambda o: o['key'] == 'wallline')),
   ('obj', ('A-31', 'витраж фасада', 'слои «Рама», «Остекление»', (0, 170, 170), lambda o: o['key'] == 'facade'))]),
 ('2 Двери, лестницы, лифты', [
   ('obj', ('A-32', 'двери', 'слой «Двери»: дуга, полотно, коробка', (20, 140, 40), lambda o: o['key'] == 'door' and 'деталь' not in o['name'] and 'без дуги' not in o['name'] and not o.get('service'))),
   ('obj', ('A-32', 'двери служебные — в блок ядра', 'полотно без дуги на грани блока ядра: шахта, техпомещение', (0, 170, 170), lambda o: o['key'] == 'door' and o.get('service'))),
   ('obj', ('A-32', 'двери без дуги', 'полотно с коробкой, дуги в исходнике нет', (0, 90, 160), lambda o: o['key'] == 'door' and 'без дуги' in o['name'] and not o.get('service'))),
   ('obj', ('A-32', 'детали проёмов', 'части «Дверей» без дуги', (150, 200, 60), lambda o: o['key'] == 'door' and 'деталь' in o['name'])),
   ('obj', ('A-66', 'лифты: кабины', 'слои A-LIFT, LDCar', (200, 0, 160), lambda o: o['key'] == 'lift'))]),
 ('3 Инженерное оборудование', [
   ('obj', ('A-56', 'конвекторы', 'слой «Отопление»', (220, 110, 0), lambda o: o['key'] == 'conv')),
   ('obj', ('A-68', 'шкафы пожарные ПК', 'слой «Спринклеры», подпись «ПК»', (220, 0, 0), lambda o: o['key'] == 'fire')),
   ('obj', ('A-74', 'сантехника', 'слой «Сантехника»', (0, 90, 220), lambda o: o['key'] == 'san')),
   ('obj', ('A-73', 'мойки: чаша со смесителем', 'слой «Обобщенные модели»', (0, 170, 200), lambda o: o['key'] == 'sink' and 'деталь' not in o['name'])),
   ('obj', ('A-73', 'мойки — детали', 'слив или смеситель отдельно', (120, 0, 200), lambda o: o['key'] == 'sink' and 'деталь' in o['name']))]),
 ('4 Мебель, оборудование, озеленение, пол', [
   ('obj', ('A-82', 'столы рабочие', 'серая заливка или контур 1150–2150 × 500–950 мм', (190, 120, 40), lambda o: o['key'] == 'desk')),
   ('obj', ('A-82', 'кресла офисные — одна фигура на группу одинаковых', 'кусок мебели 350–1000 × 250–900 мм; фигура — средняя по группе', (230, 60, 60), lambda o: o['key'] in ('chair', 'chairpart'))),
   ('obj', ('A-82', 'столы переговорные', 'замкнутый контур > 1650 × 950 мм со светлой заливкой', (0, 120, 200), lambda o: o['key'] == 'mtable')),
   ('obj', ('A-82', 'столы круглые', 'круглая светлая заливка ⌀ 600–1600 мм', (0, 180, 220), lambda o: o['key'] == 'rtable')),
   ('obj', ('A-82', 'диваны', '≥ 12 скруглённых углов подушек одного размера', (130, 60, 180), lambda o: o['key'] == 'sofa')),
   ('obj', ('A-82', 'мягкие кресла, пуфы', 'кусок мебели по размеру и форме', (200, 100, 220), lambda o: o['key'] in ('armchair', 'round'))),
   ('obj', ('A-76', 'кухня встроенная', 'столешница с мойкой и секции вдоль стены', (150, 90, 40), lambda o: o['key'] == 'kitchen')),
   ('obj', ('A-82', 'столы обеденные', '≥ 2 стула у стола, рядом кухня', (230, 140, 0), lambda o: o['key'] == 'dtable')),
   ('obj', ('A-82', 'столики журнальные', 'прямоугольник у мягкой мебели', (160, 120, 220), lambda o: o['key'] == 'ctable')),
   ('obj', ('A-82', 'стеллажи и шкафы', 'узкий длинный прямоугольник', (100, 100, 160), lambda o: o['key'] == 'storage')),
   ('obj', ('A-82', 'тумбы приставные', 'прямоугольник у стола', (170, 140, 90), lambda o: o['key'] == 'pedestal')),
   ('obj', ('A-82', 'кромки групп столов', 'тонкие полосы вдоль сторон столов', (240, 200, 0), lambda o: o['key'] == 'deskedge')),
   ('obj', ('A-82', 'кресла у групп столов — не разделены', 'кресла, связанные кромками столов', (255, 0, 120), lambda o: o['key'] == 'group')),
   ('obj', ('A-82', 'стол или тумба', 'прямоугольник мебели без соседей-подсказок', (90, 90, 90), lambda o: o['key'] == 'table' and 'draw' in o)),
   ('obj', ('A-82', 'кабины для звонков «Skype»', 'розовая заливка', (255, 80, 160), lambda o: o['key'] == 'booth')),
   ('obj', ('A-82', 'МФУ «print», экраны настенные', 'зелёный квадрат; слой «Оборудование»', (0, 150, 70), lambda o: o['key'] in ('mfp', 'equip'))),
   ('obj', ('A-89', 'растения в кашпо', 'слой «09 FURNITURE_1» и кашпо', (60, 160, 0), lambda o: o['key'] == 'plant')),
   ('obj', ('A-76', 'стойки', 'серые заливки слоя «Узлы»; замкнутый контур буквой Г или П', (230, 120, 0), lambda o: o['key'] == 'counter')),
   ('obj', ('A-82', 'кромки и экраны столов, детали', 'длинные линии и мелочь мебели', (120, 120, 120), lambda o: o['key'] == 'furn'))]),
 ('5 Помещения, тексты, служебное', [
   ('obj', ('A-92', 'помещения и ядро: заливки, штриховка, шахты', 'слои «Помещения», «Узлы», «Контур»', (150, 150, 230), lambda o: o['key'] in ('zone', 'corezone', 'shaft'))),
   ('passage', ('A-92', 'зона прохода в open space — схематично', 'свободный пол шириной не меньше длинной стороны рабочего стола, связан с дверями и коридором', (0, 170, 80), None)),
   ('obj', ('A-93', 'границы помещений', 'слой «Линии разделители»', (160, 0, 160), lambda o: o['key'] == 'roomsep')),
   ('obj', ('A-90', 'марки помещений, размеры, обмеры', 'кружки «Аннотации», «Размеры»', (40, 40, 40), lambda o: o['key'] in ('tagc', 'dim', 'measure'))),
   ('obj', ('A-AX', 'оси', 'слой «AB_оси»', (130, 130, 130), lambda o: o['key'] == 'axis')),
   ('obj', ('A-AXM', 'служебные метки «+»', 'слой «0»', (0, 140, 140), lambda o: o['key'] == 'mark')),
   ('text', ('A-90', 'надписи', 'номера мест, помещений, размеры, названия', (0, 0, 200), None))]),
 ('6 Нераспознанное и неточно распознанное', [
   ('obj', ('A-00', 'не классифицировано', '—', (255, 0, 0), lambda o: o['layer'] == 'A-00')),
   ('obj', ('A-22G', 'детали перегородок без штриховки', 'кусок < 300 мм', (120, 70, 200), lambda o: o['key'] == 'lpart' and 'деталь' in o['name'])),
   ('obj', ('A-82', 'мебель без типа — на перепроверку', 'не прямоугольник, соседи не подсказали', (230, 60, 60), lambda o: (o['key'] in ('table', 'group', 'furn', 'chairpart') and 'draw' not in o))),
   ('obj', ('A-32', 'детали проёмов без дуги', 'части «Дверей»', (150, 200, 60), lambda o: o['key'] == 'door' and 'деталь' in o['name']))]),
]
for title, rows in SHEETS:
    im = base().convert('RGBA'); ov = Image.new('RGBA', im.size, (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
    leg = []
    for kind, spec in rows:
        if kind == 'walls':
            lay, what, sign, col = WL[spec]; n = 0
            for c, g in W:
                if c == spec: draw_poly(d, g, col); n += 1
            leg.append((lay, what, sign, n, col))
        elif kind == 'passage':
            lay, what, sign, col, _ = spec; n = 0
            if os.path.exists('passage.pkl'):
                for g in pickle.load(open('passage.pkl', 'rb'))['passage']: draw_poly(d, g, col, 90); n += 1
            leg.append((lay, what, sign, n, col))
        elif kind == 'obj':
            lay, what, sign, col, f = spec; os_ = objsel(f)
            for o in os_: draw_prims(d, o['outline'] if VAR == 'outline' and o.get('outline') else o.get('draw', o['ids']), col)
            leg.append((lay, what, sign, len(os_), col))
        else:
            lay, what, sign, col, _ = spec
            for t in T:
                x0, y0, x1, y1 = t['bbox']; d.rectangle(Tr([(x0, y0), (x1, y1)]), outline=col + (255,), width=1)
            leg.append((lay, what, sign, len(T), col))
    im = Image.alpha_composite(im, ov).convert('RGB')
    S = Image.new('RGB', (im.width + LW, max(im.height, 300)), (255, 255, 255)); S.paste(im, (0, 0))
    dd = ImageDraw.Draw(S); x = im.width + 15; y = 15
    dd.text((x, y), title, fill=(0, 0, 0), font=FB); y += 40
    dd.text((x, y), 'Слой · что · признак · число', fill=(90, 90, 90), font=F); y += 30
    for lay, what, sign, n, col in leg:
        dd.rectangle([x, y + 3, x + 22, y + 21], fill=col)
        dd.text((x + 30, y), f'{lay} · {what} · {n}', fill=(0, 0, 0), font=F); y += 22
        words = sign.split(); line = ''
        for w_ in words:
            if len(line) + len(w_) > 62: dd.text((x + 30, y), line, fill=(90, 90, 90), font=F); y += 20; line = ''
            line += w_ + ' '
        dd.text((x + 30, y), line, fill=(90, 90, 90), font=F); y += 30
    dd.text((x, S.height - 60), ('Подложка — исходник в сером, осветлён на 35 %' if UNDER else 'Без подложки исходника') + ('; габаритный результат: тип и внешний контур' if VAR == 'outline' else '; подробный результат'), fill=(90, 90, 90), font=F)
    fn = os.path.join(OUTD, f'layer_{title[0]}' + ('_gabarit' if VAR == 'outline' else '') + ('' if UNDER else '_bez-podlozhki') + '.png')
    S.save(fn); print(fn, S.size)
