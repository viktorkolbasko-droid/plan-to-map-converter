"""Тест v014 (ПРV — исправления по независимой проверке приёма, 17.10.2026). DXF собираются здесь (ezdxf); DWG — заглушка «AC1032»,
конвертер — сценарий оболочки, который кладёт заранее собранный DXF (настоящий LibreDWG не нужен). Запуск: python3 tests/test_cad_fixes_v014.py —
код 0, если всё совпало.
  К1 — пустой и почти пустой DXF (0 сущностей; 3 линии; только подписи), DWG без сущностей модели, work.pdf не собран: остановка
       DWG_MODEL_EMPTY / DWG_PDF_FAILED, код выхода 2, work.pdf нет, маршрут — ROUTE_NO_PDF; обычный этаж — без остановки, work.pdf есть;
  К2 — битый DXF, DWG с битым DXF после конвертера, исключение внутри разбора: класс cad-error, DXF_READ_FAILED / DWG_READ_FAILED
       с текстом ошибки, rep.stop, intake.json и intake.md записаны, код 2; конвертер с пустым --version — не исключение;
  К3 — $EXTMIN/$EXTMAX пусты, своей геометрии нет: DWG_XREF_PLAN_MISSING по габариту из геометрии (judged = True); с планом — нет;
  К5 — UNS_DWG2DXF на несуществующий, неисполняемый, незапускаемый файл: DWG_CONVERTER_ENV_BAD с путём, DWG переведён конвертером из PATH;
       запасного нет — ещё и DWG_NO_CONVERTER;
  К10 — $INSUNITS 7 и 99: в intake.md «код N … — не из словаря», а не «не заданы»; 0 — «не заданы»;
  Т10 — паспорт при остановке: stop.ask — первым в «Попросить у клиента», единицы шапки — «под сомнением» при DWG_UNITS_SUSPECT;
  Т6 — test_cad_intake_v014 при конвертере без dwgwrite печатает «skip … нет dwgwrite», итог считает пропуски отдельно."""
import json, os, stat, subprocess, sys, tempfile
CODE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, CODE)                                         # code/ — без PYTHONPATH
import ezdxf
import cad_intake
import cad_pdf
from source_intake import intake

bad = []
def check(name, got, want):
    ok = got == want; print(('ok   ' if ok else 'FAIL ') + name + ('' if ok else f': {got!r} != {want!r}')); ok or bad.append(name)
def codes(rep): return sorted(w['code'] for w in rep.get('warnings', []))
def stops(rep):
    st = rep.get('stop') or {}
    return [st.get('code')] + [a['code'] for a in st.get('also', [])] if st else []

td = tempfile.mkdtemp(prefix='cad_fixes_v014_')
SI = os.path.join(CODE, 'source_intake.py')
BASE_PATH = os.pathsep.join(p for p in os.environ.get('PATH', '').split(os.pathsep) if not os.path.exists(os.path.join(p, 'dwg2dxf')))

def main_rc(src, name, env_extra=None, path=None):
    """source_intake.py как из командной строки: код выхода и intake.json"""
    out = os.path.join(td, name)
    env = {k: v for k, v in os.environ.items() if k not in ('PYTHONPATH', 'UNS_DWG2DXF')}
    env['PATH'] = path if path is not None else os.environ.get('PATH', '')
    env.update(env_extra or {})
    r = subprocess.run([sys.executable, SI, src, '--out', out], capture_output=True, env=env, timeout=600)
    js = os.path.join(out, 'intake.json')
    return r.returncode, (json.load(open(js, encoding='utf-8')) if os.path.exists(js) else None), out, r

def floor_doc(insunits=4):
    """обычный этаж 30 × 15 м в мм: контур, перегородки, двери, столы, размеры"""
    doc = ezdxf.new('R2013'); doc.header['$INSUNITS'] = insunits; msp = doc.modelspace()
    b = doc.blocks.new('Дверь 900'); b.add_line((0, 0), (900, 0)); b.add_arc((0, 0), 900, 0, 90)
    b = doc.blocks.new('Стол 1600x800'); b.add_lwpolyline([(0, 0), (1600, 0), (1600, 800), (0, 800)], close=True)
    msp.add_lwpolyline([(0, 0), (30000, 0), (30000, 15000), (0, 15000)], close=True, dxfattribs={'layer': 'Стены'})
    for x in range(5000, 30000, 5000):
        msp.add_line((x, 0), (x, 6000), dxfattribs={'layer': 'Перегородки'}); msp.add_line((x, 9000), (x, 15000), dxfattribs={'layer': 'Перегородки'})
    for x in range(1000, 30000, 5000):
        msp.add_blockref('Дверь 900', (x, 6000), dxfattribs={'layer': 'Двери'})
    for i in range(12):
        msp.add_blockref('Стол 1600x800', (1200 + 2400 * i, 11000), dxfattribs={'layer': 'Мебель'})
    for i in range(60):
        msp.add_text('Кабинет %d' % i, height=250).set_placement((500 + (i % 12) * 2400, 2000 + (i // 12) * 2500))
    return doc

def save(doc, name):
    p = os.path.join(td, name); doc.saveas(p); return p

def fake_conv(dirname, dxf_src=None, version='fake 1.0', runnable=True):
    """dwg2dxf-заглушка: --version печатает version; перевод — копия dxf_src в путь после -o"""
    d = os.path.join(td, dirname); os.makedirs(d, exist_ok=True); p = os.path.join(d, 'dwg2dxf')
    if runnable:
        body = '#!/bin/sh\nif [ "$1" = "--version" ]; then %s exit 0; fi\n%s\n' % (
            ('echo "%s";' % version) if version else '', ('cp "%s" "$3"' % dxf_src) if dxf_src else 'exit 3')
    else:
        body = '\x7fELF-not-really-a-binary'                    # исполняемый, но не запускается (Exec format error)
    open(p, 'w').write(body); os.chmod(p, os.stat(p).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return p

DWG = os.path.join(td, 'stub.dwg'); open(DWG, 'wb').write(b'AC1032' + b'\0' * 200)

# ---------- К1: пустая и почти пустая модель, work.pdf не собран ----------
p_ok = save(floor_doc(), 'floor.dxf')
rc, rep, out, _ = main_rc(p_ok, 'k1_floor')
check('К1 контроль: обычный этаж — без остановки, work.pdf есть, код 0, маршрут через work.pdf',
      (rc, rep.get('stop'), os.path.exists(os.path.join(out, 'work.pdf')), rep['route'] != cad_intake.ROUTE_NO_PDF), (0, None, True, True))

doc = ezdxf.new('R2013'); doc.header['$INSUNITS'] = 4
p0 = save(doc, 'empty.dxf')
rc, rep, out, _ = main_rc(p0, 'k1_empty')
check('К1: пустой DXF — DWG_MODEL_EMPTY, остановка, код 2, work.pdf нет',
      (rc, stops(rep), 'DWG_MODEL_EMPTY' in codes(rep), os.path.exists(os.path.join(out, 'work.pdf'))), (2, ['DWG_MODEL_EMPTY'], True, False))
check('К1: пустой DXF — маршрут не обещает work.pdf, класс cad-dxf', (rep['route'] == cad_intake.ROUTE_NO_PDF, rep['class']), (True, 'cad-dxf'))
check('К1: остановка — why и ask заданы', bool(rep['stop'].get('why')) and bool(rep['stop'].get('ask')), True)

doc = ezdxf.new('R2013'); doc.header['$INSUNITS'] = 4
for i in range(3):
    doc.modelspace().add_line((0, i * 1000), (5000, i * 1000))
p3 = save(doc, 'tiny.dxf')
rc, rep, out, _ = main_rc(p3, 'k1_tiny')
md = open(os.path.join(out, 'intake.md'), encoding='utf-8').read()
check('К1: 3 линии — DWG_MODEL_EMPTY, код 2, cad.model_empty: 3 сущности', (rc, stops(rep), rep['cad']['model_empty']['geometry_entities']), (2, ['DWG_MODEL_EMPTY'], 3))
check('К1: intake.md — «Остановка (DWG_MODEL_EMPTY)», виды — «нет», а не «один»',
      ('**Остановка (DWG_MODEL_EMPTY)' in md, '| Виды в модели | нет' in md, '| Виды в модели | один' in md), (True, True, False))

doc = ezdxf.new('R2013'); doc.header['$INSUNITS'] = 4
for i in range(80):                                              # только подписи: точек на виды хватает, геометрии нет
    doc.modelspace().add_text('Комната %d' % i, height=250).set_placement(((i % 10) * 3000, (i // 10) * 2000))
pt = save(doc, 'texts_only.dxf')
rc, rep, out, _ = main_rc(pt, 'k1_texts')
check('К1: только подписи (видов есть, геометрии 0 < MODEL_MIN_GEOM) — DWG_MODEL_EMPTY, work.pdf не строится',
      (rc, stops(rep), len(rep['cad']['views']) >= 1, os.path.exists(os.path.join(out, 'work.pdf'))), (2, ['DWG_MODEL_EMPTY'], True, False))
check('К1: пороги — именованные константы, числа сущностей', (cad_intake.MODEL_MIN_GEOM, cad_intake.VIEW_MIN_POINTS), (10, 50))

conv_empty = fake_conv('conv_empty', dxf_src=p0)                 # DWG, после перевода — DXF без сущностей
rc, rep, out, _ = main_rc(DWG, 'k1_dwg_empty', path=os.path.dirname(conv_empty) + os.pathsep + BASE_PATH)
check('К1: DWG без сущностей модели — cad-dwg, DWG_MODEL_EMPTY, код 2', (rep['class'], stops(rep), rc), ('cad-dwg', ['DWG_MODEL_EMPTY'], 2))

keep = cad_pdf.dxf_to_pdf
def boom(*a, **k): raise RuntimeError('синтетический сбой PDF')
cad_pdf.dxf_to_pdf = boom
rep = intake(p_ok, os.path.join(td, 'k1_pdf_failed'))
cad_pdf.dxf_to_pdf = keep
check('К1: work.pdf не собран — DWG_PDF_FAILED, остановка, маршрут без work.pdf',
      ('DWG_PDF_FAILED' in codes(rep), stops(rep), rep['route'] == cad_intake.ROUTE_NO_PDF), (True, ['DWG_PDF_FAILED'], True))
check('К1: причина сбоя — в why', 'синтетический сбой PDF' in rep['stop']['why'], True)

# ---------- К2: исключения ветки CAD ----------
pb = os.path.join(td, 'broken.dxf')
open(pb, 'w').write('0\nSECTION\n2\nENTITIES\n0\nLINE\n8\n0\n10\nabc\n20\n0\n11\n1\n21\n1\n0\nENDSEC\n0\nEOF\n')
rc, rep, out, r = main_rc(pb, 'k2_broken')
w = next((x for x in (rep or {}).get('warnings', []) if x['code'] == 'DXF_READ_FAILED'), {})
check('К2: битый DXF — код 2, intake.json есть, класс cad-error', (rc, rep is not None, (rep or {}).get('class')), (2, True, 'cad-error'))
check('К2: DXF_READ_FAILED с текстом ошибки, rep.stop, без traceback',
      ('ValueError' in w.get('what', ''), stops(rep), b'Traceback' in r.stderr), (True, ['DXF_READ_FAILED'], False))
check('К2: intake.md записан, ошибка в нём', 'ValueError' in open(os.path.join(out, 'intake.md'), encoding='utf-8').read(), True)

conv_broken = fake_conv('conv_broken', dxf_src=pb)
rc, rep, out, r = main_rc(DWG, 'k2_dwg_broken', path=os.path.dirname(conv_broken) + os.pathsep + BASE_PATH)
check('К2: DWG, после перевода битый DXF — cad-error, DWG_READ_FAILED, код 2',
      (rep['class'], 'DWG_READ_FAILED' in codes(rep), rc, b'Traceback' in r.stderr), ('cad-error', True, 2, False))

conv_nover = fake_conv('conv_nover', dxf_src=p_ok, version='')  # пустой ответ на --version (было: IndexError)
rc, rep, out, r = main_rc(DWG, 'k2_nover', path=os.path.dirname(conv_nover) + os.pathsep + BASE_PATH)
check('К2: конвертер с пустым --version — не исключение, DWG переведён, cad-dwg, код 0',
      (rep['class'], rc, b'Traceback' in r.stderr, rep['cad']['convert']['converter_version'].startswith('—')), ('cad-dwg', 0, False, True))

keep = cad_intake.scan_dxf
def boom2(*a, **k): raise MemoryError('синтетика: память')
cad_intake.scan_dxf = boom2
rep = intake(p_ok, os.path.join(td, 'k2_scan'))
cad_intake.scan_dxf = keep
check('К2: исключение внутри разбора (MemoryError) — cad-error, DXF_READ_FAILED, текст в cad.read_error',
      (rep['class'], 'DXF_READ_FAILED' in codes(rep), 'MemoryError' in rep['cad'].get('read_error', '')), ('cad-error', True, True))
check('К2: intake.json записан при исключении', os.path.exists(os.path.join(td, 'k2_scan', 'intake.json')), True)

# ---------- К3: пустые $EXTMIN/$EXTMAX ----------
def xhost(name, plan=False, ref=None):
    d = os.path.join(td, name); os.makedirs(d, exist_ok=True)
    doc = ezdxf.new('R2013'); doc.header['$INSUNITS'] = 4; msp = doc.modelspace()
    doc.add_xref_def(ref or 'plan_ar.dxf', 'PLAN_AR'); msp.add_blockref('PLAN_AR', (0, 0))
    msp.add_text('План', dxfattribs={'insert': (100, 100)})
    if plan:
        for i in range(60):                                      # 60 комнат: точек на виды хватает (VIEW_MIN_POINTS)
            x, y = 3000 + (i % 10) * 5000, 5000 + (i // 10) * 5500
            msp.add_lwpolyline([(x, y), (x + 4500, y), (x + 4500, y + 5000), (x, y + 5000)], close=True)
    p = os.path.join(d, 'host.dxf'); doc.saveas(p)               # ezdxf пишет $EXTMIN/$EXTMAX = 1e+20 / −1e+20 — «пусто»
    return p, d

p, d = xhost('k3_missing')
rep = intake(p, os.path.join(td, 'k3_missing_out')); xp = rep['cad'].get('xref_plan') or {}
check('К3: шапка без габарита — подтверждено (1e+20)', rep['cad']['header'].get('$EXTMIN', [0])[0] >= 1e19, True)
check('К3: ссылки нет, своей геометрии нет — DWG_XREF_PLAN_MISSING (было: judged False, без остановки)',
      ('DWG_XREF_PLAN_MISSING' in codes(rep), stops(rep)[:1], xp.get('judged'), xp.get('extents_source')), (True, ['DWG_XREF_PLAN_MISSING'], True, 'geometry'))
p, d = xhost('k3_empty', ref='empty_ref.dxf')
e = ezdxf.new('R2013'); e.header['$INSUNITS'] = 4; e.saveas(os.path.join(d, 'empty_ref.dxf'))
rep = intake(p, os.path.join(td, 'k3_empty_out'))
check('К3: найдена пустая ссылка — DWG_XREF_EMPTY и DWG_XREF_PLAN_MISSING', ('DWG_XREF_EMPTY' in codes(rep), stops(rep)[:1]), (True, ['DWG_XREF_PLAN_MISSING']))
p, d = xhost('k3_plan', plan=True)
rep = intake(p, os.path.join(td, 'k3_plan_out')); xp = rep['cad'].get('xref_plan') or {}
check('К3: с собственным планом — без остановки, габарит по геометрии, доли посчитаны',
      (stops(rep), xp.get('judged'), xp.get('extents_source'), xp.get('own_share', 0) > cad_intake.XREF_OWN_SHARE_MAX), ([], True, 'geometry', True))

# ---------- К5: плохой UNS_DWG2DXF ----------
conv_ok = fake_conv('conv_ok', dxf_src=p_ok)
for label, envp in (('нет файла', os.path.join(td, 'нет', 'dwg2dxf')), ('не исполняемый', p_ok),
                    ('не запускается', fake_conv('conv_elf', runnable=False))):
    rc, rep, out, r = main_rc(DWG, 'k5_' + label.replace(' ', '_'), env_extra={'UNS_DWG2DXF': envp},
                              path=os.path.dirname(conv_ok) + os.pathsep + BASE_PATH)
    w = next((x for x in rep.get('warnings', []) if x['code'] == 'DWG_CONVERTER_ENV_BAD'), {})
    check('К5: UNS_DWG2DXF — %s: DWG_CONVERTER_ENV_BAD с путём и причиной' % label, (envp in w.get('what', ''), label in w.get('what', '')), (True, True))
    check('К5: UNS_DWG2DXF — %s: DWG переведён конвертером из PATH, cad-dwg' % label,
          (rep['class'], rep['cad']['convert']['converter'] == conv_ok), ('cad-dwg', True))
md = open(os.path.join(out, 'intake.md'), encoding='utf-8').read()
check('К5: intake.md — строка «Конвертер — UNS_DWG2DXF» с путём', '| Конвертер — UNS_DWG2DXF | UNS_DWG2DXF=' in md, True)
rc, rep, out, r = main_rc(DWG, 'k5_no_fallback', env_extra={'UNS_DWG2DXF': os.path.join(td, 'нет', 'dwg2dxf'), 'HOME': td}, path=BASE_PATH)
check('К5: запасного конвертера нет — DWG_CONVERTER_ENV_BAD и DWG_NO_CONVERTER, unsupported, код 2',
      ('DWG_CONVERTER_ENV_BAD' in codes(rep), 'DWG_NO_CONVERTER' in codes(rep), rep['class'], rc), (True, True, 'unsupported', 2))
rc, rep, out, r = main_rc(DWG, 'k5_good_env', env_extra={'UNS_DWG2DXF': conv_ok}, path=BASE_PATH)
check('К5 контроль: рабочий UNS_DWG2DXF — без DWG_CONVERTER_ENV_BAD', ('DWG_CONVERTER_ENV_BAD' in codes(rep), rep['class']), (False, 'cad-dwg'))

# ---------- К10: $INSUNITS вне словаря ----------
for code_, want in ((7, 'в шапке — код 7 (км) — не из словаря'), (99, 'в шапке — код 99 — не из словаря'), (0, 'в шапке — не заданы')):
    p = save(floor_doc(code_), 'insunits_%d.dxf' % code_)
    rep = intake(p, os.path.join(td, 'k10_%d' % code_))
    md = open(os.path.join(td, 'k10_%d' % code_, 'intake.md'), encoding='utf-8').read()
    check('К10: $INSUNITS %d — «%s»' % (code_, want), (want in md, code_ == 0 or 'в шапке — не заданы' not in md), (True, True))

# ---------- Т10: паспорт при остановке ----------
doc = ezdxf.new('R2013'); doc.header['$INSUNITS'] = 4; msp = doc.modelspace()   # «мм» в шапке, координаты в метрах: этаж 30 мм
msp.add_lwpolyline([(0, 0), (30, 0), (30, 20), (0, 20)], close=True)
for i in range(40):
    x, y = (i % 10) * 3, (i // 10) * 4
    msp.add_line((x, y), (x + 2, y + 1)); msp.add_line((x, y + 1), (x + 2, y))
p = save(doc, 'mm_header_m_geom.dxf')
rep = intake(p, os.path.join(td, 't10_units')); ps = rep.get('passport') or {}
check('Т10: остановка по единицам (контроль)', stops(rep)[:1], ['DWG_UNITS_SUSPECT'])
check('Т10: «Попросить у клиента» — первой просьба остановки', ps['ask_client'][0].startswith(rep['stop']['ask']), True)
check('Т10: опора масштаба — «шапка под сомнением», единицы шапки не выданы за опору',
      ('шапка под сомнением' in ps['scale_support'], ps['scale_support'].startswith('вектор CAD: единицы — мм')), (True, False))
md = open(os.path.join(td, 't10_units', 'intake.md'), encoding='utf-8').read()
check('Т10: в паспорте intake.md — строка «Остановка»', '| Остановка | DWG_UNITS_SUSPECT' in md, True)
p, d = xhost('t10_xref')
rep = intake(p, os.path.join(td, 't10_xref_out')); ps = rep.get('passport') or {}
check('Т10: остановка по ссылке — просьба прислать файл ссылки в паспорте (было: пусто)',
      any('пришлите файл «PLAN_AR»' in a for a in ps['ask_client']), True)

# ---------- Т6: пропуск в test_cad_intake_v014 ----------
wrap = os.path.join(td, 'wrapbin'); os.makedirs(wrap, exist_ok=True)
fake_conv('wrapbin', dxf_src=p_ok)                               # конвертер есть, dwgwrite рядом нет
env = {k: v for k, v in os.environ.items() if k not in ('PYTHONPATH', 'UNS_DWG2DXF')}; env['PATH'] = wrap + os.pathsep + BASE_PATH
r = subprocess.run([sys.executable, os.path.join(CODE, 'tests', 'test_cad_intake_v014.py')], capture_output=True, env=env, timeout=600)
o = r.stdout.decode('utf-8', 'replace')
check('Т6: пропуск — «skip … нет dwgwrite (LibreDWG без записи DWG)», не «ok … LibreDWG не найден»',
      ('skip DWG: нет dwgwrite (LibreDWG без записи DWG)' in o, 'ok   DWG: LibreDWG не найден' in o), (True, False))
check('Т6: итог считает пропуски отдельно', ('пропусков 1' in o.strip().splitlines()[-1], r.returncode), (True, 0))

print('итог:', 'всё совпало' if not bad else f'расхождений {len(bad)}: ' + ', '.join(bad)); sys.exit(1 if bad else 0)
