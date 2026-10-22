"""Тест v014 (ПР4, Б24): внешняя ссылка DWG/DXF — громкая остановка вместо тихого пустого плана. DXF собирается здесь (ezdxf).
Запуск: python3 tests/test_cad_xref_v014.py — код 0, если всё совпало.
  X1 — хост без своей геометрии (рамка листа, штамп, одна вставка ссылки), файла ссылки нет: DWG_XREF_PLAN_MISSING, rep.stop с именем,
       путём, где искали, долями и просьбой «пришлите файл <имя> … Bind/eTransmit»; код выхода 2 (проверяется через source_intake.main);
  X2 — хост с планом (стены, комнаты) и второстепенной ссылкой без файла: DWG_XREF, остановки нет, доли — в cad.xref_plan;
  X3 — найденная рядом ПУСТАЯ ссылка (0 сущностей) у хоста с планом: DWG_XREF_EMPTY (раньше — молчание), остановки нет;
  X4 — хост без своей геометрии и пустая найденная ссылка: DWG_XREF_EMPTY и остановка (причина — «файл найден … 0 сущностей»);
  X5 — хост без своей геометрии, но ссылка найдена и содержит план: ни остановки, ни DWG_XREF_EMPTY;
  X6 — нечитаемый (мусорный) файл ссылки рядом: DWG_XREF_EMPTY, не молчание, остановка у хоста без плана;
  X7 — ссылка объявлена, но в модель не вставлена, хост без геометрии: остановки по ссылке нет (ссылка не в счёт); v014 (ПРV-К1) —
       остановка DWG_MODEL_EMPTY (в модели плана нет);
  X8 — хост без геометрии, ссылка без файла и в шапке нет габарита: остановка по пустоте собственной геометрии."""
import io, os, sys, tempfile, contextlib
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))      # code/ — без PYTHONPATH
import ezdxf
import cad_intake
import source_intake
from source_intake import intake

bad = []
def check(name, got, want):
    ok = got == want; print(('ok   ' if ok else 'FAIL ') + name + ('' if ok else f': {got!r} != {want!r}')); ok or bad.append(name)
def codes(rep): return sorted(w['code'] for w in rep.get('warnings', []))

td = tempfile.mkdtemp(prefix='cad_xref_v014_')
W, H = 60000, 40000        # лист 60 × 40 м в мм

def host(name, xref=None, plan=False, insert=True, extents=True, stamp=True):
    """хост: рамка листа, штамп в правом нижнем углу, подписи; plan — стены и комнаты; xref = (имя блока, файл ссылки)"""
    d = os.path.join(td, name); os.makedirs(d, exist_ok=True)
    doc = ezdxf.new('R2013'); doc.header['$INSUNITS'] = 4
    msp = doc.modelspace()
    msp.add_lwpolyline([(0, 0), (W, 0), (W, H), (0, H)], close=True, dxfattribs={'layer': 'Frame'})
    if stamp:
        x0, y0 = 0.80 * W, 0.02 * H
        for dx, dy in ((0, 0), (0.18 * W, 0), (0, 0.06 * H), (0.18 * W, 0.06 * H)):
            msp.add_line((x0, y0 + dy), (x0 + 0.18 * W, y0 + dy), dxfattribs={'layer': 'Stamp'})
        for i in range(4):
            msp.add_line((x0 + i * 0.045 * W, y0), (x0 + i * 0.045 * W, y0 + 0.06 * H), dxfattribs={'layer': 'Stamp'})
    for i in range(12):
        msp.add_text('Lt %d' % i, dxfattribs={'insert': (0.80 * W + 100, 0.03 * H + 80 * i), 'height': 60, 'layer': 'Text'})
    if plan:
        for i in range(40):                                      # комнаты 4,5 × 5 м, по четыре стороны
            x, y = 3000 + (i % 10) * 5000, 5000 + (i // 10) * 6500
            msp.add_lwpolyline([(x, y), (x + 4500, y), (x + 4500, y + 5000), (x, y + 5000)], close=True, dxfattribs={'layer': 'Walls'})
        for i in range(120):
            msp.add_line((3000 + i * 400, 4000), (3000 + i * 400, 4500), dxfattribs={'layer': 'Axes'})
    if xref:
        nm, fn = xref
        doc.add_xref_def(fn, nm)
        if insert:
            msp.add_blockref(nm, (0, 0))
    if extents:
        doc.header['$EXTMIN'] = (0, 0, 0); doc.header['$EXTMAX'] = (W, H, 0)
    p = os.path.join(d, 'host.dxf'); doc.saveas(p)
    return p, d

def ref_file(d, fn, with_plan=False, empty=False, garbage=False):
    p = os.path.join(d, fn)
    if garbage:
        open(p, 'w').write('this is not a drawing\nat all\n' * 40); return p
    doc = ezdxf.new('R2013'); doc.header['$INSUNITS'] = 4
    msp = doc.modelspace()
    if with_plan:
        for i in range(60):
            x, y = 3000 + (i % 10) * 5000, 5000 + (i // 10) * 5500
            msp.add_lwpolyline([(x, y), (x + 4500, y), (x + 4500, y + 5000), (x, y + 5000)], close=True)
    doc.saveas(p)
    return p

def run(p, name):
    return intake(p, os.path.join(td, 'out_' + name))

# X1 — план только во внешней ссылке, файла нет
p, d = host('x1', xref=('PLAN_AR', r'Y:\project\ar\PLAN_AR.dwg'))
rep = run(p, 'x1'); st = rep.get('stop') or {}; xp = rep['cad'].get('xref_plan') or {}
check('X1: класс cad-dxf', rep.get('class'), 'cad-dxf')
check('X1: DWG_XREF и DWG_XREF_PLAN_MISSING', ['DWG_XREF' in codes(rep), 'DWG_XREF_PLAN_MISSING' in codes(rep)], [True, True])
check('X1: остановка — код', st.get('code'), 'DWG_XREF_PLAN_MISSING')
check('X1: why — имя, путь, где искали, доли', [s in st.get('why', '') for s in ('PLAN_AR', r'Y:\project\ar\PLAN_AR.dwg', d, '%', 'порог')], [True] * 5)
check('X1: ask — «пришлите файл …», Bind/eTransmit', ('пришлите файл «PLAN_AR»' in st.get('ask', ''), 'Bind/eTransmit' in st.get('ask', '')), (True, True))
check('X1: доли — своё ≤ порога, не занято ≥ порога', (xp.get('own_share', 1) <= cad_intake.XREF_OWN_SHARE_MAX, xp.get('xref_gap', 0) >= cad_intake.XREF_GAP_MIN),
      (True, True))
check('X1: рамка и штамп не считаются своими', (xp.get('frame', 0) >= 1, xp.get('stamp', 0) >= 4), (True, True))
md = open(os.path.join(td, 'out_x1', 'intake.md'), encoding='utf-8').read()
check('X1: intake.md — остановка', '**Остановка (DWG_XREF_PLAN_MISSING):**' in md, True)
rc = None
sv = sys.argv, sys.stdout
try:
    sys.argv = ['source_intake.py', p, '--out', os.path.join(td, 'out_x1m')]
    with contextlib.redirect_stdout(io.StringIO()):
        try:
            rc = source_intake.main()
        except SystemExit as e:
            rc = e.code
finally:
    sys.argv, sys.stdout = sv
check('X1: код выхода 2', rc, 2)

# X2 — есть свой план, ссылка второстепенна и без файла
p, d = host('x2', xref=('ENG_EOM', r'Y:\project\eom\ENG_EOM.dwg'), plan=True)
rep = run(p, 'x2'); xp = rep['cad'].get('xref_plan') or {}
check('X2: DWG_XREF, без остановки и без PLAN_MISSING', ('DWG_XREF' in codes(rep), rep.get('stop'), 'DWG_XREF_PLAN_MISSING' in codes(rep)), (True, None, False))
check('X2: доли записаны, своя доля выше порога', (xp.get('judged'), xp.get('stop'), xp.get('own_share', 0) > cad_intake.XREF_OWN_SHARE_MAX), (True, False, True))

# X3 — найденная пустая ссылка у хоста с планом
p, d = host('x3', xref=('EMPTYREF', 'empty_ref.dxf'), plan=True); ref_file(d, 'empty_ref.dxf', empty=True)
rep = run(p, 'x3'); x = rep['cad']['xrefs'][0]
check('X3: DWG_XREF_EMPTY, остановки нет', ('DWG_XREF_EMPTY' in codes(rep), rep.get('stop')), (True, None))
check('X3: запись ссылки — найдена, 0 сущностей, причина', (x['found'], x.get('entities'), '0 сущностей' in (x.get('empty') or '')), ('empty_ref.dxf', 0, True))

# X4 — хост без плана и пустая найденная ссылка
p, d = host('x4', xref=('EMPTYREF', 'empty_ref.dxf')); ref_file(d, 'empty_ref.dxf', empty=True)
rep = run(p, 'x4'); st = rep.get('stop') or {}
check('X4: DWG_XREF_EMPTY и остановка', ('DWG_XREF_EMPTY' in codes(rep), st.get('code')), (True, 'DWG_XREF_PLAN_MISSING'))
check('X4: why — найден, 0 сущностей', ('найден «empty_ref.dxf»' in st.get('why', ''), '0 сущностей' in st.get('why', '')), (True, True))

# X5 — хост без плана, ссылка найдена и содержит план
p, d = host('x5', xref=('GOODREF', 'good_ref.dxf')); ref_file(d, 'good_ref.dxf', with_plan=True)
rep = run(p, 'x5'); xp = rep['cad'].get('xref_plan')
check('X5: ни остановки, ни EMPTY, ни DWG_XREF', (rep.get('stop'), 'DWG_XREF_EMPTY' in codes(rep), 'DWG_XREF' in codes(rep)), (None, False, False))
check('X5: cad.xref_plan нет (ссылка найдена и непуста)', xp, None)

# X6 — мусорный файл ссылки
p, d = host('x6', xref=('BADREF', 'bad_ref.dxf')); ref_file(d, 'bad_ref.dxf', garbage=True)
rep = run(p, 'x6'); st = rep.get('stop') or {}
check('X6: DWG_XREF_EMPTY (не молчание) и остановка у хоста без плана', ('DWG_XREF_EMPTY' in codes(rep), st.get('code')), (True, 'DWG_XREF_PLAN_MISSING'))

# X7 — ссылка объявлена, но не вставлена
p, d = host('x7', xref=('NOINS', 'noins.dwg'), insert=False)
rep = run(p, 'x7')
# v014 (ПРV-К1): хост без плана — теперь остановка DWG_MODEL_EMPTY (пустая модель — не «успех»); проверка X7 — что ссылка без вставок
# не даёт остановки по ссылке (DWG_XREF_PLAN_MISSING), а не что остановок нет вовсе
st7 = rep.get('stop') or {}
check('X7: ссылка без вставок не даёт остановки по ссылке (остановка — только DWG_MODEL_EMPTY)',
      ([st7.get('code')] + [a['code'] for a in st7.get('also', [])], 'DWG_XREF_PLAN_MISSING' in codes(rep)), (['DWG_MODEL_EMPTY'], False))

# X8 — габарита в шапке нет, своей геометрии нет совсем
p, d = host('x8', xref=('PLAN_AR', 'plan_ar.dwg'), extents=False, stamp=False)
rep = run(p, 'x8'); st = rep.get('stop') or {}
check('X8: остановка и без $EXTMIN/$EXTMAX (габарит — по рамке)', st.get('code'), 'DWG_XREF_PLAN_MISSING')

print('\nитог: %s' % ('всё совпало' if not bad else 'не совпало: ' + ', '.join(bad)))
sys.exit(1 if bad else 0)
