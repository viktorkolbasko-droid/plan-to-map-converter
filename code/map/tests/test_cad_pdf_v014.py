"""Тест черновика DXF → PDF со слоями (чат исходников, 07.10.2026; И16; cad_pdf.py): DXF собирается здесь (ezdxf).
Запуск: python3 tests/test_cad_pdf_draft_2026_10_07.py — код 0, если всё совпало.
  слои     — слой DXF → слой OCG с тем же именем; выключенный слой не переносится; блок на слое «0» с цветом BYBLOCK —
             слой и цвет вставки;
  масштаб  — единицы мм: 48,04 мм/pt, отрезок 10 м — 208,16 pt; единицы не определены — вид по A0, mm_per_pt = None;
  геометрия — дуга полилинии по выпуклости, сплошная штриховка — заливкой;
  подписи  — кириллица извлекается, ширина — по шрифту, середина подписи «по центру» — в точке вставки, строки MTEXT по порядку;
  скорость — 3000 подписей пишутся быстрее 10 с (insert_text pymupdf шёл минутами);
  units_sure — единицы уверены только при единственном лидере признаков;
  маршрут  — sheetcheck плана (если найден рядом) ведёт PDF по слоям."""
import json, math, os, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))      # code/ — без PYTHONPATH
import ezdxf
import pymupdf
import cad_pdf
from cad_intake import units_sure

bad = []
def check(name, got, want):
    ok = got == want; print(('ok   ' if ok else 'FAIL ') + name + ('' if ok else f': {got!r} != {want!r}')); ok or bad.append(name)
def near(a, b, tol): return a is not None and abs(a - b) <= tol

td = tempfile.mkdtemp(prefix='cad_pdf_draft_')
doc = ezdxf.new('R2013'); doc.header['$INSUNITS'] = 4
for name, color in (('A-WALL', 1), ('A-FURN', 3), ('A-TEXT', 7), ('A-HATCH', 5), ('A-OFF', 2)):
    doc.layers.add(name, color=color)
doc.layers.get('A-OFF').off()
b = doc.blocks.new('DESK')
b.add_lwpolyline([(0, 0), (1600, 0), (1600, 800), (0, 800)], close=True, dxfattribs={'layer': '0', 'color': 0})
msp = doc.modelspace()
msp.add_line((0, 0), (10000, 0), dxfattribs={'layer': 'A-WALL'})
msp.add_lwpolyline([(0, 5000, 0, 0, 1.0), (2000, 5000, 0, 0, 0)], format='xyseb', dxfattribs={'layer': 'A-WALL'})   # полуокружность R 1000
msp.add_blockref('DESK', (6000, 4000), dxfattribs={'layer': 'A-FURN'})
h = msp.add_hatch(color=5, dxfattribs={'layer': 'A-HATCH'}); h.paths.add_polyline_path([(3000, 3000), (4000, 3000), (4000, 4000), (3000, 4000)], is_closed=True)
msp.add_text('Переговорная 1', height=300, dxfattribs={'layer': 'A-TEXT'}).set_placement((5000, 2000), align=ezdxf.enums.TextEntityAlignment.MIDDLE_CENTER)
msp.add_mtext('Офис\\PОпен-спейс', dxfattribs={'layer': 'A-TEXT', 'char_height': 250, 'insert': (8000, 6000), 'attachment_point': 1})
msp.add_line((0, 1000), (9000, 1000), dxfattribs={'layer': 'A-OFF'})
p = os.path.join(td, 'a.dxf'); doc.saveas(p)
views = [{'bbox': [-1000.0, -1000.0, 11000.0, 7000.0]}]
out = os.path.join(td, 'a.pdf')
info = cad_pdf.dxf_to_pdf(p, out, views, 1.0, title='a.dxf', creator_note='AC1027 AutoCAD 2013')
d = pymupdf.open(out); pg = d[0]
K = cad_pdf.MM_PER_PT
check('слои: OCG — по слоям DXF, выключенного нет, «0» блока — слой вставки', sorted(o['name'] for o in d.get_ocgs().values()),
      ['A-FURN', 'A-HATCH', 'A-TEXT', 'A-WALL'])
check('выключенный слой посчитан', info['skipped_off_layers'], 1)
check('масштаб: 48,04 мм/pt, ширина листа = 12 м / 48,04 + поля', (info['mm_per_pt'], near(pg.rect.width, 12000 / K + 2 * cad_pdf.MARGIN_PT, 0.05)), (K, True))
dr = pg.get_drawings()
H = pg.rect.height
wx = lambda x: (x - cad_pdf.MARGIN_PT) * K - 1000                 # pt страницы → мм модели
wy = lambda y: (H - y - cad_pdf.MARGIN_PT) * K - 1000
lines = [it for g in dr if g.get('layer') == 'A-WALL' for it in g['items'] if it[0] == 'l']
check('отрезок 10 м — 208,16 pt', any(near(math.dist(it[1], it[2]), 10000 / K, 0.01) for it in lines), True)
ys = [wy(pt.y) for g in dr if g.get('layer') == 'A-WALL' for it in g['items'] if it[0] in ('l', 'c') for pt in (it[1], it[-1])]   # дуга — кривой
check('дуга по выпуклости: низ полуокружности — y 4000 мм', near(min(y for y in ys if y > 3000), 4000, 15), True)
furn = [g for g in dr if g.get('layer') == 'A-FURN']
check('блок: слой «0» → A-FURN, BYBLOCK → цвет вставки (зелёный по слою)', [tuple(round(c, 2) for c in g['color']) for g in furn], [(0.0, 1.0, 0.0)])
if furn:
    r = furn[0]['rect']
    check('стол 1600 × 800 мм', (near(r.width * K, 1600, 3), near(r.height * K, 800, 3)), (True, True))
fills = [g for g in dr if g.get('layer') == 'A-HATCH' and g.get('fill') is not None]
check('дуги — кривыми Безье, как у листа AutoCAD: полуокружность — две кривые', sum(1 for g in dr if g.get('layer') == 'A-WALL' for it in g['items'] if it[0] == 'c'), 2)
check('сплошная штриховка — заливка синим', [tuple(round(c, 2) for c in g['fill']) for g in fills], [(0.0, 0.0, 1.0)])
spans = [s for b in pg.get_text('dict')['blocks'] for l in b.get('lines', []) for s in l['spans']]
t = [s for s in spans if s['text'] == 'Переговорная 1']
check('подпись: кириллица извлекается', len(t), 1)
if t:
    bb = pymupdf.Rect(t[0]['bbox']); fs = 300 / K
    check('подпись «по центру»: середина по x — в точке вставки', near(wx((bb.x0 + bb.x1) / 2), 5000, 40), True)
    check('подпись: ширина — по шрифту, не «1 em на знак»', near(bb.width, pymupdf.Font('helv').text_length('Переговорная 1', fontsize=fs), 0.3), True)
m = [s for s in spans if s['text'] in ('Офис', 'Опен-спейс')]
check('MTEXT: две строки, «Офис» выше', [s['text'] for s in sorted(m, key=lambda s: s['bbox'][1])], ['Офис', 'Опен-спейс'])
if m:
    top = min(m, key=lambda s: s['bbox'][1])
    check('MTEXT «верх-лево»: верх первой строки — у точки вставки', near(wy(top['bbox'][1]), 6000, 120), True)
check('метаданные: создатель с «DWG» — признак листа CAD', 'DWG' in (d.metadata.get('creator') or ''), True)
d.close()
# масштаб не известен
info2 = cad_pdf.dxf_to_pdf(p, os.path.join(td, 'b.pdf'), views, None)
d2 = pymupdf.open(os.path.join(td, 'b.pdf'))
check('единицы не определены: mm_per_pt нет, длинная сторона вида — A0', (info2['mm_per_pt'], near(d2[0].rect.width, cad_pdf.A0_PT + 2 * cad_pdf.MARGIN_PT, 0.1)),
      (None, True))
d2.close()
# скорость подписей
doc = ezdxf.new('R2013'); msp = doc.modelspace()
for i in range(3000):
    msp.add_text('Кабинет %d' % i, height=200, dxfattribs={'layer': 'T%d' % (i % 7)}).set_placement((i % 60 * 1000, i // 60 * 1000))
p3 = os.path.join(td, 'c.dxf'); doc.saveas(p3)
info3 = cad_pdf.dxf_to_pdf(p3, os.path.join(td, 'c.pdf'), [{'bbox': [0.0, 0.0, 60000.0, 50000.0]}], 1.0)
check('3000 подписей: все записаны, запись быстрее 10 с', (info3['pages'][0]['texts'], info3['secs']['write'] < 10), (3000, True))
# размеры вдали от начала координат: блок размера вставлен в 0,0, геометрия — в мировых; текст против измерения
doc = ezdxf.new('R2013'); doc.header['$INSUNITS'] = 4; msp = doc.modelspace()
msp.add_line((100000, 100000), (115000, 100000), dxfattribs={'layer': 'A-WALL'})
for x0, txt in ((100000, '<>'), (105000, '4800'), (110000, '<>')):
    dim = msp.add_linear_dim(base=(x0, 99000), p1=(x0, 100000), p2=(x0 + 5000, 100000), text=txt, override={'dimtxt': 250, 'dimasz': 250}, dxfattribs={'layer': 'A-DIMS'}); dim.render()
    dim.dimension.dxf.actual_measurement = 5000.0             # AutoCAD пишет размер в код 42, ezdxf — нет
p5 = os.path.join(td, 'e.dxf'); doc.saveas(p5)
info5 = cad_pdf.dxf_to_pdf(p5, os.path.join(td, 'e.pdf'), [{'bbox': [99000.0, 98000.0, 116000.0, 101000.0]}], 1.0)
wd = [w[4] for w in pymupdf.open(os.path.join(td, 'e.pdf'))[0].get_text('words')]
check('размер вдали от 0,0: числа размеров на листе', ('5000' in wd, '4800' in wd), (True, True))
check('размеры: множитель 1, текст = длине у двух, переписан у одного', (info5['dims']['ratio'], info5['dims']['text_eq'], info5['dims']['text_ne']), (1.0, 2, 1))
# строки DXF: битый байт внутри UTF-8 (LibreDWG) — не cp1251 всей строки
check('строка DXF: UTF-8 с битым байтом, cp1251, ASCII', [cad_pdf.dec_dxf(b) for b in (b'\xa0' + 'либо стойки'.encode('utf-8'), 'Привет'.encode('cp1251'), b'A-WALL')],
      ['либо стойки', 'Привет', 'A-WALL'])
check('коды MTEXT: абзац, шрифт, \\U+, дробь, %%c', [cad_pdf.mtext_clean(t) for t in (r'\pi-750,l750,t750;Прим.\P1. Текст', r'{\fArial|b0|i0|c204|p34;Каб. 12}', r'\U+041A\U+0430\U+0431', r'%%c50\S+0.1^-0.2;')],
      ['Прим.\n1. Текст', 'Каб. 12', 'Каб', 'Ø50+0.1/-0.2'])
# старая полилиния, сетка граней, полилиния с шириной, то, что PDF не рисует
doc = ezdxf.new('R2013'); doc.header['$INSUNITS'] = 4; msp = doc.modelspace()
doc.layers.add('P2D', color=1); doc.layers.add('MESH', color=3); doc.layers.add('WIDE', color=5); doc.layers.add('PT', color=2)
msp.add_polyline2d([(0, 0, 0, 0, 1.0), (2000, 0, 0, 0, 0)], format='xyseb', dxfattribs={'layer': 'P2D'})         # полуокружность вниз
pf = msp.add_polyface(dxfattribs={'layer': 'MESH'})
pf.append_face([(5000, 0, 0), (6000, 0, 0), (6000, 1000, 0), (5000, 1000, 0)])
msp.add_lwpolyline([(0, 3000), (4000, 3000)], dxfattribs={'layer': 'WIDE', 'const_width': 200})
msp.add_point((1000, 1000), dxfattribs={'layer': 'PT'})
p6 = os.path.join(td, 'f.dxf'); doc.saveas(p6)
info6 = cad_pdf.dxf_to_pdf(p6, os.path.join(td, 'f.pdf'), [{'bbox': [-1000.0, -2000.0, 7000.0, 4000.0]}], 1.0)
d6 = pymupdf.open(os.path.join(td, 'f.pdf')); dr6 = d6[0].get_drawings(); H6 = d6[0].rect.height
y6 = lambda y: (H6 - y - cad_pdf.MARGIN_PT) * K - 2000
pts2d = [y6(pt.y) for g in dr6 if g.get('layer') == 'P2D' for it in g['items'] if it[0] in ('l', 'c') for pt in (it[1], it[-1])]
check('старая полилиния POLYLINE: дуга по выпуклости — низ на y −1000 мм', near(min(pts2d) if pts2d else None, -1000, 15), True)
mesh = [it for g in dr6 if g.get('layer') == 'MESH' for it in g['items'] if it[0] == 'l']
check('сетка граней: 4 ребра квадрата 1 × 1 м', (len(mesh), all(near(math.dist(it[1], it[2]) * K, 1000, 3) for it in mesh)), (4, True))
wide = [g for g in dr6 if g.get('layer') == 'WIDE']
check('полилиния шириной 200 мм — линия толщиной 200 мм', near(wide[0].get('width') * K if wide else None, 200, 1), True)
check('не рисуется — в отчёте: POINT', info6['not_drawn'], {'POINT': 1})
d6.close()
# виды приёма — без выключенных слоёв: далёкая линия на выключенном слое не растягивает вид
from source_intake import intake
doc = ezdxf.new('R2013'); doc.header['$INSUNITS'] = 4; msp = doc.modelspace()
doc.layers.add('A-WALL'); doc.layers.add('OFF-3D'); doc.layers.get('OFF-3D').off()
for i in range(40):
    msp.add_line((i * 500, 0), (i * 500, 15000), dxfattribs={'layer': 'A-WALL'})
    msp.add_line((0, i * 375), (20000, i * 375), dxfattribs={'layer': 'A-WALL'})
for i in range(200):
    msp.add_line((900000 + i * 10, 0), (0, 0), dxfattribs={'layer': 'OFF-3D'})
p7 = os.path.join(td, 'g.dxf'); doc.saveas(p7)
rep7 = intake(p7, os.path.join(td, 'g'))
vb = rep7['cad']['views'][0]['bbox'] if rep7['cad'].get('views') else None
check('вид приёма — без выключенного слоя: шире 25 м не стал', vb is not None and vb[2] - vb[0] < 25000, True)
# внешняя ссылка: файл рядом с чертежом под именем «(Клиент) имя» — рисуется по вставке, слои «ссылка|слой»
xd = os.path.join(td, 'xr'); os.makedirs(xd)
base = ezdxf.new('R2013'); base.header['$INSUNITS'] = 4; base.layers.add('A-WALL', color=1); bm = base.modelspace()
for i in range(30):
    bm.add_line((i * 1000, 0), (i * 1000, 20000), dxfattribs={'layer': 'A-WALL'})
bm.add_lwpolyline([(0, 0), (29000, 0), (29000, 20000), (0, 20000)], close=True, dxfattribs={'layer': 'A-WALL'})
base.saveas(os.path.join(xd, '(Клиент) base.dxf'))
host = ezdxf.new('R2013'); host.header['$INSUNITS'] = 4; host.layers.add('A-FURN', color=3); hm = host.modelspace()
host.add_xref_def(filename='C:\\proj\\base.dxf', name='base')
hm.add_blockref('base', (100000, 50000))
for i in range(20):
    hm.add_lwpolyline([(101000 + i * 1300, 55000), (102200 + i * 1300, 55000), (102200 + i * 1300, 55800), (101000 + i * 1300, 55800)], close=True, dxfattribs={'layer': 'A-FURN'})
hp = os.path.join(xd, 'host.dxf'); host.saveas(hp)
rep8 = intake(hp, os.path.join(td, 'h'))
xr = rep8['cad'].get('xrefs') or [{}]
check('ссылка найдена рядом под именем «(Клиент) base.dxf», DWG_XREF нет', (xr[0].get('found'), 'DWG_XREF' in [w['code'] for w in rep8['warnings']]), ('(Клиент) base.dxf', False))
d8 = pymupdf.open(os.path.join(td, 'h', 'work.pdf'))
oc8 = sorted(o['name'] for o in d8.get_ocgs().values())
check('слои PDF: мебель чертежа и стены ссылки «base|A-WALL»', oc8, ['A-FURN', 'base|A-WALL'])
wl = [g for g in d8[0].get_drawings() if g.get('layer') == 'base|A-WALL']
H8 = d8[0].rect.height; vb8 = rep8['cad']['views'][0]['bbox']
u8 = 1.0 / rep8['cad']['pdf']['pt_per_unit']                       # единиц на pt: масштаб листа — какой вышел
ys8 = [(H8 - pt.y - cad_pdf.MARGIN_PT) * u8 + vb8[1] for g in wl for it in g['items'] if it[0] == 'l' for pt in it[1:3]]
check('стены ссылки — 30 линий на месте вставки: y от 50 до 70 м', (sum(1 for g in wl for it in g['items'] if it[0] == 'l'), near(min(ys8), 50000, 30), near(max(ys8), 70000, 30)),
      (30, True, True))
d8.close()
# units_sure
check('units_sure: мм — 2 признака, единственный лидер', units_sure({'header': 'мм', 'by_objects': 'мм', 'score': {'мм': 2, 'см': 1, 'м': 0, 'дюйм': 0, 'фут': 0}}), ('мм', True))
check('units_sure: ничья — не уверены', units_sure({'header': 'дюйм', 'by_objects': 'дюйм', 'score': {'мм': 0, 'см': 1, 'м': 1, 'дюйм': 1, 'фут': 1}})[1], False)
check('units_sure: один признак и шапка — уверены', units_sure({'header': 'м', 'by_objects': 'м', 'score': {'мм': 0, 'см': 0, 'м': 1, 'дюйм': 0, 'фут': 0}}), ('м', True))
# маршрут плана: sheetcheck рядом (разработка: draft/plan; пакет: UNS_PLAN_CODE)
here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sc = [q for q in (os.path.join(os.environ.get('UNS_PLAN_CODE', ''), 'sheetcheck.py'), os.path.join(here, '..', 'plan', 'sheetcheck.py')) if os.path.isfile(q)]
if sc:
    doc = ezdxf.new('R2013'); msp = doc.modelspace()
    for i, name in enumerate(('A-WALL', 'A-DOOR', 'A-GLAZ', 'A-FURN', 'A-COLS', 'A-ANNO')):
        msp.add_line((0, i * 1000), (20000, i * 1000), dxfattribs={'layer': name})
    p4 = os.path.join(td, 'd.dxf'); doc.saveas(p4)
    cad_pdf.dxf_to_pdf(p4, os.path.join(td, 'd.pdf'), [{'bbox': [0.0, 0.0, 20000.0, 6000.0]}], 1.0, creator_note='AC1027')
    w = os.path.join(td, 'sc'); os.makedirs(w)
    r = subprocess.run([sys.executable, sc[0], os.path.join(td, 'd.pdf')], cwd=w, capture_output=True, text=True)
    check('sheetcheck: маршрут по слоям', json.load(open(os.path.join(w, 'sheetcheck.json'))).get('route'), 'layers')
else:
    print('skip sheetcheck: нет sheetcheck.py плана (UNS_PLAN_CODE)')
print('итог:', 'всё совпало' if not bad else 'расхождений %d' % len(bad))
sys.exit(1 if bad else 0)
