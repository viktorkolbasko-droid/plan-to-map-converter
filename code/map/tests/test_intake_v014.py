"""Тест приёма v014 (ПР6 — остаток ОЧ-53 из черновика 0816, часть B паспорта ОЧ-53). Без внешних данных: PDF и растры собираются здесь.
И2 — RASTER_1280: длинная сторона 1280 ± 2 px (свойство файла после мессенджера) — есть; 1283 px и 1100 px — нет; LOWRES_RASTER черновика
не переносится (новых порогов в px нет): 1100 px — без предупреждения о разрешении; 999 px — SMALL_RASTER («первая оценка»);
PDF_SCAN_LOWQ — JPEG картинки скана в PDF качества 30 — есть, 90 — нет; native.jpeg_quality — оценка ± 3; строка в intake.md.
И1 — паспорт: 12 проверок черновика 0816 (П02, П03, П05, П06, П07, П13 по PDF_FEW_LINES, П14, П16, растр, 1280 px, DXF — вызовом passport()
по отчёту части A) + хуки v014: PDF под паролем — без профиля; поле passport без _text в intake.json, раздел intake.md, сбой паспорта — passport_error, приём не падает.
И13/И14/П-239 — альбом из 6 листов черновика 0816: ранги, этажи, кандидаты, walls_pages, PDF_PLAN_CANDIDATES, PDF_MULTI_FLOOR, PDF_WALLS_SHEET,
«Листы-планы» в intake.md; выбор листа — choose_page v011 без изменений (лист 6, у черновика — 4: вопрос ОЧ-54); английские заголовки; эскиз не в счёт.
ПП2 (ПК5-ПП2) — путь в title с расширением файла не Revit (папка Revit, файл план.dwg) — не признак Revit; .rvt, путь без расширения,
обрезанный title («….rv»), подпись «Revit» без пути — признак, как в v013.
Запуск из любой папки: python3 tests/test_intake_v014.py — код 0, если всё совпало."""
import io, json, os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np, pymupdf
from PIL import Image, ImageDraw
import source_intake as si
from source_intake import intake
bad = []
def check(name, got, want):
    ok = got == want; print(('ok   ' if ok else 'FAIL ') + name + ('' if ok else f': {got!r} != {want!r}')); ok or bad.append(name)
codes = lambda rep: sorted(w['code'] for w in rep.get('warnings', []))
td = tempfile.mkdtemp(prefix='intake_v014_')
RES = ('LOWRES_RASTER', 'RASTER_1280', 'SMALL_RASTER')


def frame_png(size, name):
    im = Image.new('RGB', size, 'white'); ImageDraw.Draw(im).rectangle((50, 50, size[0] - 50, size[1] - 50), outline='black', width=4)
    p = os.path.join(td, name); im.save(p); return p


def scan_pdf(q, name):
    im = Image.new('RGB', (1600, 1200), 'white'); dr = ImageDraw.Draw(im)
    for x in range(0, 1600, 37): dr.line((x, 0, x, 1200), fill='black', width=2)
    b = io.BytesIO(); im.save(b, 'JPEG', quality=q)
    doc = pymupdf.open(); pg = doc.new_page(width=800, height=600); pg.insert_image(pg.rect, stream=b.getvalue())
    p = os.path.join(td, name); doc.save(p); doc.close(); return p


# ── И2: растр — признак мессенджера, без нового порога в px ──────────────────────────────────────────────────────────
for size, want in (((1280, 900), ['RASTER_1280']), ((900, 1281), ['RASTER_1280']), ((1283, 900), []), ((1100, 700), []),
                   ((999, 500), ['SMALL_RASTER']), ((2000, 1400), [])):
    rep = intake(frame_png(size, 'r_%dx%d.png' % size), os.path.join(td, 'r_%dx%d' % size))
    check('И2: растр %d × %d — %s' % (size + (want or 'без предупреждений о разрешении',)), [c for c in codes(rep) if c in RES], want)
check('И2: LOWRES_RASTER и LOWRES_RASTER_SIDE не перенесены (новых порогов в px нет)',
      ('LOWRES_RASTER' in si.ADVICE, hasattr(si, 'LOWRES_RASTER_SIDE'), si.SMALL_RASTER_SIDE), (False, False, 1000))

# ── И2: JPEG внутри PDF-скана ─────────────────────────────────────────────────────────────────────────────────────────
for q, want in ((30, True), (90, False)):
    rep = intake(scan_pdf(q, 'scan_q%d.pdf' % q), os.path.join(td, 'scan_q%d' % q))
    jq = (rep.get('native') or {}).get('jpeg_quality')
    check('И2: скан JPEG %d — класс, PDF_SCAN_LOWQ %s, оценка ± 3' % (q, 'есть' if want else 'нет'),
          (rep.get('class'), 'PDF_SCAN_LOWQ' in codes(rep), jq is not None and abs(jq - q) <= 3), ('pdf-scan', want, True))
md = open(os.path.join(td, 'scan_q30', 'intake.md'), encoding='utf-8').read()
check('И2: intake.md — качество JPEG картинки скана', 'качество JPEG ≈' in md, True)

# ── И1: паспорт исходника (passport.py; проверки черновика 0816 + хуки v014) ──────────────────────────────────────────
import passport as pp_mod
def pdf_ps(name, producer='', creator='', title='', layers=(), n=700, words=(), walls=False):
    doc = pymupdf.open(); pg = doc.new_page(width=842, height=595)
    ocs = [doc.add_ocg(x) for x in layers]
    if walls:                                                    # эскиз: мало отрезков (< 500), но длинные — покрывают лист (класс pdf-vector)
        for i in range(n // 2):
            pg.draw_line((80, 60 + i * 470 / (n // 2)), (760, 60 + i * 470 / (n // 2)))
            pg.draw_line((80 + i * 680 / (n // 2), 50), (80 + i * 680 / (n // 2), 540))
    else:
        for i in range(n):
            x, y = 40 + (i % 60) * 12, 40 + (i // 60) * 20
            pg.draw_line((x, y), (x + 8, y), oc=ocs[i % len(ocs)] if ocs else 0)
    for i, w in enumerate(words):
        pg.insert_text((60, 420 + 16 * i), w, fontname='china-s', fontsize=10)
    doc.set_metadata({'producer': producer, 'creator': creator, 'title': title})
    p = os.path.join(td, name); doc.save(p); doc.close()
    return intake(p, os.path.join(td, name + '_out'))
rep = pdf_ps('acad.pdf', 'pdfplot16.hdi 16.01', 'AutoCAD 2022', 'Модель', ['A-WALL', 'A-DOOR', 'A-FURN', 'I-FURN'],
             words=['План 3 этажа  М 1:100', '3000 4500 6000 1200 2400 3600 4800 9000 7200']); ps = rep['passport']
check('И1: AutoCAD — П02, AIA, масштаб на листе', (ps['profile'], ps['layers']['family'], ps['scale_support'].startswith('размеры или масштаб')), ('П02', 'AIA/NCS', True))
check('И1: AutoCAD — ссылка на кэш ref/core/20', ps['cache_ref'], 'ref/core/20-профили-исходников.md, «## П02»')
j = json.load(open(os.path.join(td, 'acad.pdf_out', 'intake.json'), encoding='utf-8'))
check('И1: intake.json — поле passport, без _text и _text_pdf, без passport_error',
      ('passport' in j, '_text' in j, '_text_pdf' in j, 'passport_error' in j), (True, False, False, False))
md = open(os.path.join(td, 'acad.pdf_out', 'intake.md'), encoding='utf-8').read()
check('И1: intake.md — раздел «Паспорт исходника» перед «Предупреждения»',
      ('## Паспорт исходника' in md, md.find('## Паспорт исходника') < md.find('## Предупреждения'), '| Профиль | П02 Вектор AutoCAD |' in md), (True, True, True))
ps = pdf_ps('archicad.pdf', 'PDFTron PDFNet, V6.4', 'ARCHICAD (GSPublisherVersion 1)', '', ['01_Стены', '02_Двери', '03_Мебель'], words=['Кабинет', 'Переговорная'])['passport']
check('И1: ArchiCAD — П03, нумерованные группы и русские слова, подписи по-русски',
      (ps['profile'], ps['layers']['family'], ps['labels']), ('П03', 'нумерованные группы (01_…), русские слова', 'по-русски'))
model = r'\\srv\proj\REVIT\Офис_2.rvt'
ps = pdf_ps('revit.pdf', 'GPL Ghostscript', 'PDF24 Creator', '<' + model.encode('cp1251').hex().upper() + '>')['passport']
check('И1: Revit по пути модели — П16, правила plan/', (ps['profile'], ps['cache_ref'].startswith('профиль одного клиента')), ('П16', True))
ps = pdf_ps('print.pdf', 'GPL Ghostscript 10.04.0', 'PDF24 Creator', 'Untitled', words=['Office plan', 'Meeting room'])['passport']
check('И1: печать без признака программы — П05, размеров нет', (ps['profile'], ps['program'], ps['scale_support'].startswith('размеров на листе нет')),
      ('П05', 'печать в PDF', True))
ps = pdf_ps('design.pdf', 'Adobe PDF library 17.00', 'Adobe Illustrator 27.3')['passport']
check('И1: Illustrator — П06, попросить размер помещения', (ps['profile'], any('размер одного помещения' in a for a in ps['ask_client'])), ('П06', True))
rep = pdf_ps('sketch.pdf', '', 'Google', n=60, walls=True)
check('И1: эскиз 60 длинных отрезков — pdf-vector, PDF_FEW_LINES, П13 (черновик: PDF_SPARSE)',
      (rep.get('class'), 'PDF_FEW_LINES' in codes(rep), rep['passport']['profile']), ('pdf-vector', True, 'П13'))
ps = intake(scan_pdf(30, 'ps_scan.pdf'), os.path.join(td, 'ps_scan'))['passport']
check('И1: скан JPEG 30 — П07, попросить скан от 300 dpi, качество JPEG в паспорте',
      (ps['profile'], any('300 dpi' in a for a in ps['ask_client']), any('JPEG ≈' in q for q in ps['quality'])), ('П07', True, True))
ps = intake(frame_png((1280, 900), 'ps_r1280.png'), os.path.join(td, 'ps_r1280'))['passport']
check('И1: растр — профиль по содержанию, кандидаты П09–П13', (ps['profile'], ps['candidates'], ps['by']), (None, ['П09', 'П10', 'П11', 'П12', 'П13'], 'содержание — глазами'))
check('И1: растр 1280 px — попросить оригинал файлом', any('оригинал файлом' in a for a in ps['ask_client']), True)
import zipfile
p = os.path.join(td, 'plan.docx')
with zipfile.ZipFile(p, 'w') as z:
    z.writestr('[Content_Types].xml', '<Types/>'); z.writestr('word/document.xml', '<w:document/>')
check('И1: Office — П14', intake(p, os.path.join(td, 'docx_out'))['passport']['profile'], 'П14')
ps = pp_mod.passport({'kind': 'dxf', 'class': 'cad-dxf', 'warnings': [], 'cad': {'layers_top': [['Стены', 80], ['Двери', 5]], 'layers_used': 2,
                      'units': {'header': 'мм', 'by_objects': 'мм', 'mismatch': False}, 'pdf': {'mm_per_pt': 48.04}}}, 'Кабинет')
check('И1: DXF (отчёт части A, без cad_intake) — П01, опора масштаба — вектор CAD, 48,04 мм/pt',
      (ps['profile'], ps['scale_support'].startswith('вектор CAD'), '48.04 мм/pt' in ps['scale_support']), ('П01', True, True))
doc = pymupdf.open(); doc.new_page().insert_text((50, 50), 'план'); pe = os.path.join(td, 'enc.pdf')
doc.save(pe, encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw='u', owner_pw='o'); doc.close()
ps = intake(pe, os.path.join(td, 'enc_out'))['passport']
check('И1: PDF под паролем — профиля нет (не П05), попросить PDF без пароля', (ps['profile'], ps['candidates'], 'PDF без пароля' in ps['ask_client']), (None, [], True))
_orig = pp_mod.passport
def _boom(rep, text=''): raise RuntimeError('синтетический сбой паспорта')
pp_mod.passport = _boom
try:
    rep = intake(frame_png((1500, 1000), 'ps_err.png'), os.path.join(td, 'ps_err'))
finally:
    pp_mod.passport = _orig
j = json.load(open(os.path.join(td, 'ps_err', 'intake.json'), encoding='utf-8'))
md = open(os.path.join(td, 'ps_err', 'intake.md'), encoding='utf-8').read()
check('И1: сбой паспорта не роняет приём — класс, passport_error, нет passport, строка в intake.md',
      (j.get('class'), j.get('passport_error', '')[:12], 'passport' in j, 'Паспорт не собран' in md), ('raster', 'RuntimeError', False, True))

# ── И13/И14/П-239: листы-планы по заголовкам — список и предупреждения; выбор листа — choose_page v011 (не меняется, ОЧ-54) ─────────────
def lines(pg, n, x0=40, y0=60, step=6, w=500):
    per = max(1, int(w // step))
    for i in range(n):
        x = x0 + (i % per) * step; y = y0 + (i // per) * 4
        pg.draw_line((x, y), (x + 4, y))
def text(pg, xy, s_, size=14): pg.insert_text(xy, s_, fontname='china-s', fontsize=size)
doc = pymupdf.open()
pg = doc.new_page(width=1190, height=842); text(pg, (60, 50), 'Ведомость рабочих чертежей', 16); lines(pg, 600)          # 1 — содержание
for i, t in enumerate(('План расстановки мебели', 'План потолков', 'Развертки 1-29')): text(pg, (60, 600 + 30 * i), t, 16)
pg = doc.new_page(width=1190, height=842); lines(pg, 5000)                                                                 # 2 — развёртки
for i in range(8): text(pg, (60 + 130 * i, 40), f'Развертки вид {i + 1}', 14)
pg = doc.new_page(width=1190, height=842); lines(pg, 1000); text(pg, (400, 40), 'План вновь возводимых перегородок 2 этаж', 14)   # 3
pg = doc.new_page(width=1190, height=842); lines(pg, 1500)                                                                 # 4 — мебель, два этажа
text(pg, (300, 40), 'План расстановки мебели 2 этаж', 14); text(pg, (300, 440), 'План расстановки мебели 3 этаж', 14)
pg = doc.new_page(width=1190, height=842); lines(pg, 3000); text(pg, (400, 40), 'План расстановки мебели 2 этаж', 14)     # 5 — мебель
pg = doc.new_page(width=1190, height=842); lines(pg, 4000); text(pg, (400, 40), 'План потолков 2 этаж', 14)               # 6 — потолки
for pg in doc: text(pg, (900, 800), 'отдел планирования', 8)                                                               # штамп мелким шрифтом
p_alb = os.path.join(td, 'album.pdf'); doc.save(p_alb); doc.close()
rep = intake(p_alb, os.path.join(td, 'album'))
pf = {f['number']: f for f in rep['pdf']['page_facts']}
check('И13: ранги листов 1–6 (содержание, не план, перегородки, мебель ×2, потолки)', [pf[i]['tier'] for i in range(1, 7)], [8, 5, 2, 1, 1, 3])
want_page, _ = si.choose_page(rep['pdf']['page_facts'], [f for f in rep['pdf']['page_facts'] if f['class'] != 'pdf-empty'])
check('И13: выбор листа не изменён — choose_page v011 (лист 6, по заголовку плана и содержимому; ранг заголовка — ОЧ-54)',
      (rep.get('chosen_page'), want_page['number']), (6, 6))
check('И13: кандидаты — листы 3–6 с рангами', [(c['page'], c['tier']) for c in rep['pdf']['plan_candidates']], [(3, 2), (4, 1), (5, 1), (6, 3)])
check('И14: этажи листа 4 — [2, 3]', pf[4]['floors'], [2, 3])
check('И13/П-239: PDF_PLAN_CANDIDATES есть; лист 6 — один этаж, PDF_MULTI_FLOOR нет; walls_pages [3], PDF_WALLS_SHEET есть',
      ('PDF_PLAN_CANDIDATES' in codes(rep), 'PDF_MULTI_FLOOR' in codes(rep), rep['pdf']['walls_pages'], 'PDF_WALLS_SHEET' in codes(rep)), (True, False, [3], True))
md = open(os.path.join(td, 'album', 'intake.md'), encoding='utf-8').read()
check('И13: intake.md — листы по этажам', ('Листы-планы по заголовкам' in md, '- этаж 3: стр. 4 — план мебели' in md, 'стены — с «Плана перегородок», стр. 3' in md), (True, True, True))
rep4 = intake(p_alb, os.path.join(td, 'album_p4'), page_no=4)
check('И14: --page 4 (два этажа) — PDF_MULTI_FLOOR', (rep4.get('chosen_page'), 'PDF_MULTI_FLOOR' in codes(rep4)), (4, True))
rep3 = intake(p_alb, os.path.join(td, 'album_p3'), page_no=3)
check('П-239: выбран сам «План перегородок» — без PDF_WALLS_SHEET', 'PDF_WALLS_SHEET' in codes(rep3), False)
check('И1+И13: паспорт — выбрать лист и спросить этажи', (any('Листы-планы' in c for c in rep['passport']['cut']),
      any('какие этажи' in a for a in rep['passport']['ask_client'])), (True, True))
doc = pymupdf.open()                                                                                                       # без заголовков
for n in (800, 3000, 1200):
    pg = doc.new_page(width=600, height=400); lines(pg, n)
p_nt = os.path.join(td, 'no_titles.pdf'); doc.save(p_nt); doc.close()
rep = intake(p_nt, os.path.join(td, 'no_titles'))
check('И13: без заголовков — лист 2 (как v011), кандидатов нет, без PDF_PLAN_CANDIDATES и списка в intake.md',
      (rep.get('chosen_page'), rep['pdf']['plan_candidates'], 'PDF_PLAN_CANDIDATES' in codes(rep),
       '**Листы-планы по заголовкам**' in open(os.path.join(td, 'no_titles', 'intake.md'), encoding='utf-8').read()), (2, [], False, False))
doc = pymupdf.open()                                                                                                       # английские заголовки
pg = doc.new_page(width=1190, height=842); lines(pg, 2000); text(pg, (400, 40), 'Furniture Layout - Level 2', 14)
pg = doc.new_page(width=1190, height=842); lines(pg, 2000); text(pg, (400, 40), 'Reflected Ceiling Plan - Level 2', 14)
p_en = os.path.join(td, 'album_en.pdf'); doc.save(p_en); doc.close()
rep = intake(p_en, os.path.join(td, 'album_en'))
check('И13: английские заголовки — ранги [1, 3], этаж 2, PDF_PLAN_CANDIDATES',
      ([f['tier'] for f in rep['pdf']['page_facts']], [f['floors'] for f in rep['pdf']['page_facts']], 'PDF_PLAN_CANDIDATES' in codes(rep)), ([1, 3], [[2], [2]], True))
doc = pymupdf.open()                                                                                                       # эскиз-кандидат не в счёт
pg = doc.new_page(width=842, height=595); lines(pg, 2000); text(pg, (300, 40), 'План 2 этажа', 14)
pg = doc.new_page(width=842, height=595); text(pg, (300, 40), 'План 3 этажа', 14)
for i in range(30):
    pg.draw_line((80, 60 + i * 16), (760, 60 + i * 16)); pg.draw_line((80 + i * 23, 50), (80 + i * 23, 540))
p_sk = os.path.join(td, 'album_sketch.pdf'); doc.save(p_sk); doc.close()
rep = intake(p_sk, os.path.join(td, 'album_sketch'))
check('И13: второй кандидат — эскиз (< 500 отрезков) — в списке, PDF_PLAN_CANDIDATES нет',
      ([(c['page'], c['few_lines']) for c in rep['pdf']['plan_candidates']], 'PDF_PLAN_CANDIDATES' in codes(rep)), ([(1, False), (2, True)], False))

# ── ПП2 (ПК5-ПП2): слово «revit» в пути файла не Revit — не признак Revit ─────────────────────────────────────────────────
def title_pdf(title, name):
    doc = pymupdf.open(); pg = doc.new_page(width=842, height=595); lines(pg, 600)
    doc.set_metadata({'title': title, 'producer': 'GPL Ghostscript', 'creator': 'PDF24 Creator'})
    p = os.path.join(td, name); doc.save(p); doc.close(); return pymupdf.open(p)
for t, want in ((r'C:\Users\ivan\Revit\план.dwg', False),                       # папка пользователя «Revit», файл DWG
                (r'D:\work\Revit\офис.pdf', False),                             # то же, файл PDF
                (r'C:\Users\ivan\Revit\Лист 1.05', True),                       # «.05» — не расширение
                (r'\\srv\proj\REVIT\Офис_2.rvt', True),                         # путь модели
                (r'\\dfs\Share\клиент А\REVIT\клиент А этаж_ivanov', True),       # локальная копия без расширения
                (r'\\dfs\Share\клиент А\REVIT\клиент А этаж_ФХ_.rv', True),        # title обрезан: «.rv» — начало .rvt
                (r'\\srv\proj\Офис.rvt - Лист A101.pdf', True),                 # «.rvt» в имени — признак
                ('Revit 2023', True)):                                          # подпись программы без пути
    got = si.pdf_title(title_pdf(t, 'pp2_%d.pdf' % abs(hash(t))))['revit_sign']
    check('ПП2: «%s» — признак Revit %s' % (t, 'есть' if want else 'нет'), got, want)
h = '<' + r'\\dfs\Share\клиент А\REVIT\клиент А этаж_ФХ_.rvt'.encode('cp1251').hex().upper()[:-3] + '>'      # hex, обрезанный на полубайте
check('ПП2: hex-title, обрезанный на полубайте («….r») — признак Revit сохранён', si.pdf_title(title_pdf(h, 'pp2_hex.pdf'))['revit_sign'], True)

print('итог:', 'всё совпало' if not bad else f'расхождений {len(bad)}'); sys.exit(1 if bad else 0)
