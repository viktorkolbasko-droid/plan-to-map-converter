"""Тест черновика приёма чертежа CAD (чат исходников, 07.10.2026; И7, И16): DXF собирается здесь (ezdxf), DWG — из него же,
если есть LibreDWG (dwgwrite); нет — проверка DWG пропускается с пометкой. Запуск: python3 tests/test_cad_intake_draft_2026_10_07.py —
код 0, если всё совпало.
  A — один этаж в мм, в шапке «м»: DWG_UNITS, единицы по объектам — мм (размеры, двери, столы, габарит);
  B — два этажа рядом с подписями «2 этаж», «3 этаж»: DWG_MULTI_VIEW, два вида, этажи 2 и 3;
  C — оросители, картинка без файла, внешняя ссылка, блоки семейств Revit: DWG_ENGINEERING, DWG_IMAGES_MISSING, DWG_XREF,
      DWG_FROM_REVIT;
  без конвертера — DWG не читается: DWG_NO_CONVERTER, класс unsupported.
v014 (ПРV-Т6): пропуск — строкой «skip …» с причиной (нет конвертера; нет dwgwrite — LibreDWG без записи DWG; dwgwrite не записал),
не «ok»; итог считает проверки и пропуски отдельно."""
import json, os, shutil, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))      # code/ — без PYTHONPATH (К4, К5)
import ezdxf
import cad_intake
from source_intake import intake

bad, skipped, passed = [], [], [0]                                # v014 (ПРV-Т6): пропуски — отдельно от ok
def skip(name):
    print('skip ' + name); skipped.append(name)
def check(name, got, want):
    ok = got == want; print(('ok   ' if ok else 'FAIL ') + name + ('' if ok else f': {got!r} != {want!r}')); ok or bad.append(name); passed[0] += ok
def codes(rep): return sorted(w['code'] for w in rep.get('warnings', []))

def floor(doc, msp, dx=0.0, label=None, furniture=True):
    """этаж 30 × 15 м в мм: контур, перегородки, двери и столы блоками, размеры"""
    msp.add_lwpolyline([(dx, 0), (dx + 30000, 0), (dx + 30000, 15000), (dx, 15000)], close=True, dxfattribs={'layer': 'Стены'})
    for x in range(5000, 30000, 5000):
        msp.add_line((dx + x, 0), (dx + x, 6000), dxfattribs={'layer': 'Перегородки'})
        msp.add_line((dx + x, 9000), (dx + x, 15000), dxfattribs={'layer': 'Перегородки'})
    msp.add_line((dx, 6000), (dx + 30000, 6000), dxfattribs={'layer': 'Перегородки'})
    msp.add_line((dx, 9000), (dx + 30000, 9000), dxfattribs={'layer': 'Перегородки'})
    for x in range(1000, 30000, 5000):
        msp.add_blockref('Дверь 900', (dx + x, 6000), dxfattribs={'layer': 'Двери'})
    if furniture:
        for i in range(12):
            msp.add_blockref('Стол 1600x800', (dx + 1200 + 2400 * i, 11000), dxfattribs={'layer': 'Мебель'})
    for x in range(0, 30000, 5000):
        dim = msp.add_linear_dim(base=(dx + x, -1500), p1=(dx + x, 0), p2=(dx + x + 5000, 0)); dim.render()
        dim.dimension.dxf.actual_measurement = 5000.0             # AutoCAD пишет размер в код 42, ezdxf — нет
    if label:
        msp.add_text(label, height=600, dxfattribs={'layer': 'Подписи'}).set_placement((dx + 12000, 7000))
    for i in range(60):                                          # подписи помещений — точки вида
        msp.add_text('Кабинет %d' % i, height=250, dxfattribs={'layer': 'Подписи'}).set_placement((dx + 500 + (i % 12) * 2400, 2000 + (i // 12) * 2500))

def new_doc(insunits):
    doc = ezdxf.new('R2013'); doc.header['$INSUNITS'] = insunits
    b = doc.blocks.new('Дверь 900'); b.add_line((0, 0), (900, 0)); b.add_arc((0, 0), 900, 0, 90)
    b = doc.blocks.new('Стол 1600x800'); b.add_lwpolyline([(0, 0), (1600, 0), (1600, 800), (0, 800)], close=True)
    return doc

td = tempfile.mkdtemp(prefix='cad_intake_draft_')
# A — единицы
doc = new_doc(6); floor(doc, doc.modelspace()); pa = os.path.join(td, 'A.dxf'); doc.saveas(pa)
rep = intake(pa, os.path.join(td, 'A'))
u = rep['cad']['units']
check('A: класс cad-dxf', rep.get('class'), 'cad-dxf')
check('A: единицы — шапка м, по объектам мм, DWG_UNITS', (u['header'], u['by_objects'], 'DWG_UNITS' in codes(rep)), ('м', 'мм', True))
check('A: признаки единиц — размеры, дверь, стол, габарит', sorted(u['evidence']), sorted(['размеры', 'дверь', 'стол', 'габарит вида']))
check('A: один вид, без DWG_MULTI_VIEW', (len(rep['cad']['views']), 'DWG_MULTI_VIEW' in codes(rep)), (1, False))
check('A: превью записано', os.path.exists(os.path.join(td, 'A', 'dxf_preview.png')), True)
# B — два этажа рядом
doc = new_doc(4); msp = doc.modelspace(); floor(doc, msp, 0, '2 этаж'); floor(doc, msp, 60000, '3 этаж')
pb = os.path.join(td, 'B.dxf'); doc.saveas(pb)
rep = intake(pb, os.path.join(td, 'B'))
check('B: два вида и DWG_MULTI_VIEW', (len(rep['cad']['views']), 'DWG_MULTI_VIEW' in codes(rep)), (2, True))
check('B: этажи видов', sorted(v['floors'] for v in rep['cad']['views']), [[2], [3]])
check('B: единицы мм без DWG_UNITS', (rep['cad']['units']['by_objects'], 'DWG_UNITS' in codes(rep)), ('мм', False))
# C — инженерия, картинка, ссылка, Revit
doc = new_doc(4); msp = doc.modelspace(); floor(doc, msp, furniture=False)
b = doc.blocks.new('Ороситель вниз'); b.add_circle((0, 0), 60)
for i in range(120):
    msp.add_blockref('Ороситель вниз', (1500 + (i % 12) * 2400, 1000 + (i // 12) * 1300), dxfattribs={'layer': 'ПТ_оросители'})
idef = doc.add_image_def(filename='скан_этажа.png', size_in_pixel=(640, 360))
msp.add_image(idef, insert=(0, 0), size_in_units=(30000, 15000))
doc.add_xref_def(filename='Подложка_АР.dwg', name='Подложка_АР'); msp.add_blockref('Подложка_АР', (0, 0))
for i in range(3):
    b = doc.blocks.new('Basic Wall - Generic 200mm-%d-Level 1' % (412300 + i)); b.add_line((0, 0), (4000, 0))
    msp.add_blockref('Basic Wall - Generic 200mm-%d-Level 1' % (412300 + i), (0, 16000 + 500 * i))
pc = os.path.join(td, 'C.dxf'); doc.saveas(pc)
rep = intake(pc, os.path.join(td, 'C'))
check('C: DWG_ENGINEERING, DWG_IMAGES_MISSING, DWG_XREF, DWG_FROM_REVIT',
      [c in codes(rep) for c in ('DWG_ENGINEERING', 'DWG_IMAGES_MISSING', 'DWG_XREF', 'DWG_FROM_REVIT')], [True] * 4)
check('C: картинка без файла и ссылка названы', (rep['cad']['images']['missing'], [x['name'] for x in rep['cad']['xrefs']]), (1, ['Подложка_АР']))
open(os.path.join(td, 'скан_этажа.png'), 'wb').write(b'\x89PNG\r\n\x1a\n')                         # файл картинки рядом — уже не пропажа
rep = intake(pc, os.path.join(td, 'C2'))
check('C: файл картинки рядом — без DWG_IMAGES_MISSING', 'DWG_IMAGES_MISSING' in codes(rep), False)
# DWG — через LibreDWG, если он есть
exe = cad_intake.find_converter()
w = os.path.join(os.path.dirname(exe), 'dwgwrite') if exe else None
if w and os.path.exists(w):
    env = dict(os.environ); lib = os.path.join(os.path.dirname(os.path.dirname(exe)), 'lib')
    env['LD_LIBRARY_PATH'] = lib + (':' + env['LD_LIBRARY_PATH'] if env.get('LD_LIBRARY_PATH') else '')
    pd = os.path.join(td, 'A.dwg')
    subprocess.run([w, '-y', '-o', pd, pa], env=env, capture_output=True, timeout=300)
    if os.path.exists(pd) and os.path.getsize(pd) > 0:
        rep = intake(pd, os.path.join(td, 'A_dwg'))                  # dwgwrite 0.14 теряет сущности модели — проверяется путь DWG → DXF
        check('DWG: LibreDWG — DWG переведён в DXF, класс cad-dwg, шапка прочитана',
              (rep.get('class'), (rep.get('cad', {}).get('convert') or {}).get('exit') in (0, 1), rep['cad']['header'].get('$INSUNITS')), ('cad-dwg', True, 6))
    else:
        skip('DWG: dwgwrite не записал DWG из DXF — проверка DWG→DXF пропущена')
elif exe:                                                        # v014 (ПРV-Т6): конвертер есть, а записи DWG нет — не «LibreDWG не найден»
    skip('DWG: нет dwgwrite (LibreDWG без записи DWG) — проверка DWG→DXF пропущена (рядом с %s; полный LibreDWG — UNS_DWG2DXF)' % exe)
else:
    skip('DWG: LibreDWG не найден — проверка DWG→DXF пропущена (рецепт сборки — README)')
# без конвертера
pdwg = os.path.join(td, 'fake.dwg'); open(pdwg, 'wb').write(b'AC1032' + b'\0' * 200)
keep = cad_intake.find_converter; cad_intake.find_converter = lambda: None
rep = intake(pdwg, os.path.join(td, 'noconv'))
cad_intake.find_converter = keep
check('без конвертера: DWG_NO_CONVERTER, unsupported', ('DWG_NO_CONVERTER' in codes(rep), rep.get('class')), (True, 'unsupported'))
print('итог:', ('всё совпало' if not bad else f'расхождений {len(bad)}') + f'; проверок {passed[0] + len(bad)}, пропусков {len(skipped)}')   # v014 (ПРV-Т6)
sys.exit(1 if bad else 0)
