"""Тест v014 (ПР3, Б25): единицы чертежа CAD против габарита этажа; громкий отказ без конвертера. DXF собирается здесь (ezdxf).
Запуск: python3 tests/test_cad_units_v014.py — код 0, если всё совпало.
  P1 — «парковка» 50 × 30 м в метрах, шапка $INSUNITS = 1 (дюйм), места размечены линиями (прямоугольников нет), дверей, столов, размеров нет: габарит в единицах
       шапки 1,27 м — не этаж: DWG_UNITS_SUSPECT, rep.stop с причиной и просьбой к клиенту, масштаб work.pdf не задан;
  P2 — та же парковка с рядом машино-мест 2,5 × 5 м (замкнутые полилинии): признак по геометрии даёт «м» — DWG_UNITS, без остановки,
       масштаб 48,04 мм/pt;
  P3 — та же парковка, шапка «м»: шапка правдоподобна — ни DWG_UNITS_SUSPECT, ни остановки;
  P4 — ничья признаков без шапки среди лидеров больше не решается порядком списка (by_objects = None, tie);
  P5 — офис 30 × 15 м в мм, шапка «мм», ряд столов-прямоугольников 1800 × 900 без имени: машино-место не признак (шапка правдоподобна);
  CONV — UNS_DWG2DXF указывает на несуществующий файл, PATH без dwg2dxf: DWG_NO_CONVERTER, класс unsupported, где искали — в cad."""
import os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))      # code/ — без PYTHONPATH
import ezdxf
import cad_intake
from source_intake import intake

bad = []
def check(name, got, want):
    ok = got == want; print(('ok   ' if ok else 'FAIL ') + name + ('' if ok else f': {got!r} != {want!r}')); ok or bad.append(name)
def codes(rep): return sorted(w['code'] for w in rep.get('warnings', []))

td = tempfile.mkdtemp(prefix='cad_units_v014_')

def parking(insunits, stalls=False, name='p'):
    """парковка 50 × 30 м в метрах: контур, колонны 0,5 × 0,5 м (не прямоугольник места), проезд; stalls — ряд мест 2,5 × 5 м"""
    doc = ezdxf.new('R2013'); doc.header['$INSUNITS'] = insunits
    msp = doc.modelspace()
    msp.add_lwpolyline([(0, 0), (50, 0), (50, 30), (0, 30)], close=True, dxfattribs={'layer': 'Contour'})
    for x in range(0, 51, 8):
        for y in (0, 15, 30):
            msp.add_lwpolyline([(x - .25, y - .25), (x + .25, y - .25), (x + .25, y + .25), (x - .25, y + .25)], close=True,
                               dxfattribs={'layer': 'Columns'})
    for y in (12.0, 18.0):
        msp.add_line((0, y), (50, y), dxfattribs={'layer': 'Road'})
    for i in range(17):                                          # разметка мест линиями — не прямоугольники, признака нет
        x = 2 + 2.5 * i
        msp.add_line((x, 1), (x, 6), dxfattribs={'layer': 'Marking'}); msp.add_line((x, 24), (x, 29), dxfattribs={'layer': 'Marking'})
    if stalls:
        for i in range(16):
            x = 2 + 2.5 * i
            msp.add_lwpolyline([(x, 1), (x + 2.5, 1), (x + 2.5, 6), (x, 6)], close=True, dxfattribs={'layer': 'Stalls'})
            msp.add_lwpolyline([(x, 24), (x + 2.5, 24), (x + 2.5, 29), (x, 29)], close=True, dxfattribs={'layer': 'Stalls'})
    p = os.path.join(td, name + '.dxf'); doc.saveas(p)
    return p

# P1 — шапка «дюйм», натура в метрах, сверить не по чему
rep = intake(parking(1), os.path.join(td, 'P1'))
u = rep['cad']['units']
check('P1: класс cad-dxf', rep.get('class'), 'cad-dxf')
check('P1: шапка неправдоподобна (габарит вида ≈ 48–50 дюймов ≈ 1,2–1,3 м < 3 м)', (u['header'], u.get('header_plausible'), 1100 <= u.get('header_span_mm', 0) <= 1300),
      ('дюйм', False, True))
check('P1: DWG_UNITS_SUSPECT и DWG_SCALE_UNKNOWN', ['DWG_UNITS_SUSPECT' in codes(rep), 'DWG_SCALE_UNKNOWN' in codes(rep)], [True, True])
st = rep.get('stop') or {}
check('P1: остановка — код, причина, просьба к клиенту', (st.get('code'), 'дюйм' in st.get('why', ''), 'единиц' in st.get('ask', '')),
      ('DWG_UNITS_SUSPECT', True, True))
check('P1: масштаб work.pdf не задан', (rep['cad'].get('pdf') or {}).get('mm_per_pt'), None)
check('P1: ничья «м»/«фут» не решена порядком списка', (u['by_objects'], u.get('tie')), (None, ['м', 'фут']))
md = open(os.path.join(td, 'P1', 'intake.md'), encoding='utf-8').read()
check('P1: intake.md — раздел CAD и остановка', ('**Чертёж CAD**' in md, '**Остановка (DWG_UNITS_SUSPECT):**' in md), (True, True))
check('P1: _text не в intake.json', '"_text' in open(os.path.join(td, 'P1', 'intake.json'), encoding='utf-8').read(), False)

# P2 — те же единицы, но ряд машино-мест 2,5 × 5 м: признак по геометрии
rep = intake(parking(1, stalls=True, name='p2'), os.path.join(td, 'P2'))
u = rep['cad']['units']
check('P2: машино-места найдены (32 шт., 2,5 × 5)', (u.get('stall') or {}).get('count'), 32)
check('P2: по объектам — м, DWG_UNITS, без остановки', (u['by_objects'], 'DWG_UNITS' in codes(rep), 'DWG_UNITS_SUSPECT' in codes(rep), rep.get('stop')),
      ('м', True, False, None))
check('P2: масштаб work.pdf — 48,04 мм/pt', (rep['cad'].get('pdf') or {}).get('mm_per_pt'), 48.04)

# P3 — шапка «м» правдоподобна
rep = intake(parking(6, name='p3'), os.path.join(td, 'P3'))
check('P3: шапка «м» — без DWG_UNITS_SUSPECT и остановки', ('DWG_UNITS_SUSPECT' in codes(rep), rep.get('stop'), rep['cad']['units'].get('header_plausible')),
      (False, None, True))

# P4 — ничья без шапки: unit_guess на готовом скане
scan = {'dims': [], 'ins_pts': [], 'blocks': {}, 'header': {}, 'rects': []}
g = cad_intake.unit_guess(scan, [{'bbox': [0, 0, 50, 30], 'share': 1.0}])
check('P4: ничья без шапки — by_objects None, tie', (g['by_objects'], g.get('tie'), 'header_span_mm' in g), (None, ['м', 'фут'], False))

# P5 — офис в мм, шапка «мм», столы-прямоугольники 1800 × 900 без имени: машино-место не признак
doc = ezdxf.new('R2013'); doc.header['$INSUNITS'] = 4; msp = doc.modelspace()
msp.add_lwpolyline([(0, 0), (30000, 0), (30000, 15000), (0, 15000)], close=True)
for x in range(1000, 30000, 1000):                               # перегородки — чтобы был вид
    msp.add_line((x, 6000), (x, 9000)); msp.add_line((x, 12000), (x, 15000))
for i in range(12):
    x = 1000 + 2000 * i
    msp.add_lwpolyline([(x, 2000), (x + 1800, 2000), (x + 1800, 2900), (x, 2900)], close=True)
po = os.path.join(td, 'office.dxf'); doc.saveas(po)
rep = intake(po, os.path.join(td, 'P5'))
u = rep['cad']['units']
check('P5: офис мм — без DWG_UNITS, DWG_UNITS_SUSPECT, «машино-место» не в признаках',
      ('DWG_UNITS' in codes(rep), 'DWG_UNITS_SUSPECT' in codes(rep), 'машино-место' in u['evidence'], u['by_objects']), (False, False, False, 'мм'))

# CONV — переменная указывает в пустоту, PATH без конвертера: громко, с тем, где искали
pdwg = os.path.join(td, 'fake.dwg'); open(pdwg, 'wb').write(b'AC1032' + b'\0' * 200)
keep = dict(os.environ)
os.environ['UNS_DWG2DXF'] = os.path.join(td, 'нет', 'dwg2dxf'); os.environ['PATH'] = td
try:
    rep = intake(pdwg, os.path.join(td, 'noconv'))
finally:
    os.environ.clear(); os.environ.update(keep)
cs = rep.get('cad', {}).get('converter_search') or []
check('CONV: DWG_NO_CONVERTER, unsupported', ('DWG_NO_CONVERTER' in codes(rep), rep.get('class')), (True, 'unsupported'))
check('CONV: где искали — UNS_DWG2DXF «нет файла», PATH', (any(c.startswith('UNS_DWG2DXF') and 'нет файла' in c for c in cs), any(c.startswith('PATH') for c in cs)),
      (True, True))
print('итог:', 'всё совпало' if not bad else f'расхождений {len(bad)}'); sys.exit(1 if bad else 0)
