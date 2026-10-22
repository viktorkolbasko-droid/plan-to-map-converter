"""Тест приёма v011 (пакет кода 5; измеритель «12», Б1, Б4, Б5). Без внешних данных: PDF собираются здесь.
Б1 — маска прозрачности на картинке, у которой уже есть альфа: apply_smask снимает альфу (Pixmap(pix, 0)); картинка JPEG 2000 со своей альфой без
цветового пространства и с /SMask — приём не падает (v010: «color pixmap must not have an alpha channel»), native — рендер области (PDF_NATIVE_RENDER).
Б4 — альбом: титул, экспликация, план (с таблицей «Экспликация» тем же кеглем), развертки со «схемой видов», ведомость — лист плана по заголовку
(v010 — развертки, больше отрезков).
Б5 — эскиз из немногих линий на весь лист — pdf-vector и PDF_FEW_LINES (v010 — pdf-empty); титул (рамка, штамп) — pdf-empty.
Доработка после независимой проверки (синтетика проверяющего, собрана здесь заново): S1 — обложка-скан «ПЛАН РАССТАНОВКИ МЕБЕЛИ» и векторный
план без заголовка словаря — выбран план (лучший класс); S2 — экспликация со строкой «Планировка — открытая» 10 pt при заголовке 14 pt и план
без текста — выбран план, экспликация — pdf-empty; S3 (пустой ГОСТ, рамка разбита в узлах штампа), S3c (рамка одним отрезком на сторону),
S3d (лист «Примечания» с доп. графами и таблицей изменений) — pdf-empty.
Доработка 2 (повторная проверка, синтетика T2–T4 собрана здесь заново): T2 — «Схема электрическая принципиальная…» и план без заголовка — выбран
план («Схема…» без слова плана офиса — нейтрально); T3 — обложка-скан без текста и план с «План 2 этажа» 12 pt при «Экспликация помещений» 14 pt —
выбран план (класс — первым); T4 — тот же план с «Спецификация мебели» 14 pt и развертки с большим числом отрезков — выбран план (на листе с чертежом
строка плана не мельче 0,6 самой крупной строки словаря — заголовок плана).
Доработка 2 (Б5): S6 — эскиз на А4 без рамки, стены в 15 мм от края — pdf-vector и PDF_FEW_LINES (контур стен у края — не рамка: нет штампа);
S7 — разреженный план на А3 по ГОСТ, стены в 8 мм внутри рамки — pdf-vector и PDF_FEW_LINES (рамка — ближайшая к краю прямая, кольцо — между краем и рамкой).
Доработка 3 (третья проверка): R1 — план с заголовком «2 этаж. Расстановка мебели» (слово листа не первое) и таблицей «Экспликация помещений»
14 pt + «Схема кабельных трасс» с меньшим содержимым — выбран план (таблица на листе с чертежом — не «другой» заголовок); R2 — «Планировка 2 этажа» и
«Схема расстановки мебели 3 этажа» — выбран лист с большим содержимым по заголовку; R3 — разреженный план А3 по ГОСТ, стены в 2 мм внутри рамки — pdf-vector.
Запуск из любой папки: python3 tests/test_intake_v011.py — код 0, если всё совпало."""
import io, os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np, pymupdf
from PIL import Image
from source_intake import intake, apply_smask
FONT = next((f for f in ('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', '/usr/share/fonts/dejavu/DejaVuSans.ttf') if os.path.exists(f)), None)
bad = []
def check(name, got, want):
    ok = got == want; print(('ok   ' if ok else 'FAIL ') + name + ('' if ok else f': {got!r} != {want!r}')); ok or bad.append(name)

# Б1: картинка с альфой + маска -> альфа картинки снята, альфа результата — маска
W, H = 40, 30
rgba = np.zeros((H, W, 4), np.uint8); rgba[..., :3] = 90; rgba[..., 3] = 255; rgba[:, :10, 3] = 0
pix = pymupdf.Pixmap(pymupdf.csRGB, W, H, rgba.tobytes(), True)
m = np.full((H, W), 255, np.uint8); m[:5] = 0; msk = pymupdf.Pixmap(pymupdf.csGRAY, W, H, m.tobytes(), False)
try: pymupdf.Pixmap(pix, msk); check('Б1: Pixmap(pix, mask) на картинке с альфой падает (как в v010)', 'не упало', 'упало')
except Exception: check('Б1: Pixmap(pix, mask) на картинке с альфой падает (как в v010)', 'упало', 'упало')
r = apply_smask(pix, msk); a = np.frombuffer(r.samples, np.uint8).reshape(H, W, r.n)[..., -1]
check('Б1: apply_smask — альфа результата = маска', (r.alpha, int(a[:5].max()), int(a[5:, :10].min())), (1, 0, 255))

def text(pg, xy, s, size): pg.insert_text(xy, s, fontsize=size, fontname='dj', fontfile=FONT)
with tempfile.TemporaryDirectory() as td:
    # Б1: JPEG 2000 со своей альфой без цветового пространства и /SMask
    b = io.BytesIO(); Image.fromarray(np.dstack([np.full((300, 400, 3), 60, np.uint8), np.full((300, 400), 255, np.uint8)]), 'RGBA').save(b, 'JPEG2000')
    doc = pymupdf.open(); pg = doc.new_page(width=600, height=450)
    xm = doc.get_new_xref(); doc.update_object(xm, '<< /Type /XObject /Subtype /Image /Width 400 /Height 300 /ColorSpace /DeviceGray /BitsPerComponent 8 >>')
    doc.update_stream(xm, np.full((300, 400), 255, np.uint8).tobytes())
    xi = doc.get_new_xref(); doc.update_object(xi, f'<< /Type /XObject /Subtype /Image /Width 400 /Height 300 /Filter /JPXDecode /SMask {xm} 0 R >>')
    doc.update_stream(xi, b.getvalue(), compress=False)
    doc.xref_set_key(pg.xref, 'Resources', f'<< /XObject << /Im1 {xi} 0 R >> >>')
    cx = doc.get_new_xref(); doc.update_object(cx, '<< >>'); doc.update_stream(cx, b'q 600 0 0 450 0 0 cm /Im1 Do Q'); doc.xref_set_key(pg.xref, 'Contents', f'{cx} 0 R')
    p1 = os.path.join(td, 'b1.pdf'); doc.save(p1)
    rep = intake(p1, os.path.join(td, 'o1')); codes = [w['code'] for w in rep['warnings']]
    check('Б1: приём не падает, класс pdf-scan', (rep.get('class'), os.path.exists(os.path.join(td, 'o1', rep.get('native', {}).get('file', '-')))), ('pdf-scan', True))
    check('Б1: предупреждение PDF_NATIVE_RENDER', 'PDF_NATIVE_RENDER' in codes, True)
    if FONT:
        # Б4: альбом
        doc = pymupdf.open(); WW, HH = 1190, 842
        def frame(pg): pg.draw_rect(pymupdf.Rect(20, 20, WW - 20, HH - 20), color=(0, 0, 0), width=1)
        def plan(pg, x0, y0, n):
            pg.draw_rect(pymupdf.Rect(x0, y0, x0 + 900, y0 + 540), color=(0, 0, 0), width=2)
            for k in range(n): x = x0 + 20 + (k % 10) * 86; y = y0 + 280 + (k // 10) * 20; pg.draw_rect(pymupdf.Rect(x, y, x + 28, y + 12), color=(0, 0, 0), width=0.5); pg.draw_circle((x + 14, y + 16), 3, color=(0, 0, 0), width=0.3)
        pg = doc.new_page(width=WW, height=HH); frame(pg); text(pg, (300, 300), 'Общие данные', 36)
        pg = doc.new_page(width=WW, height=HH); frame(pg); text(pg, (80, 80), 'Экспликация помещений', 28)
        for r_ in range(31): pg.draw_line((80, 110 + r_ * 16), (740, 110 + r_ * 16), color=(0, 0, 0), width=0.4)
        pg = doc.new_page(width=WW, height=HH); frame(pg); text(pg, (80, 70), 'План 2 этажа. Расстановка мебели', 28); text(pg, (700, 70), 'Экспликация помещений', 28); plan(pg, 80, 100, 120)   # экспликация на листе плана тем же кеглем
        pg = doc.new_page(width=WW, height=HH); frame(pg); text(pg, (80, 80), 'Развертки стен 2 этажа', 28); text(pg, (820, 480), 'Схема видов', 12)
        for bb in range(6):
            for k in range(300): pg.draw_line((60 + bb * 180, 120 + k), (220 + bb * 180, 160 + k), color=(0.3, 0.3, 0.3), width=0.2)
        pg = doc.new_page(width=WW, height=HH); frame(pg); text(pg, (80, 80), 'Ведомость отделки помещений', 28)
        p4 = os.path.join(td, 'b4.pdf'); doc.save(p4); rep = intake(p4, os.path.join(td, 'o4'))
        check('Б4: лист альбома — по заголовку «План…»', (rep.get('chosen_page'), (rep.get('chosen_by') or '')[:12]), (3, 'по заголовку'))
        check('Б4: заголовки страниц', [f.get('title_kind') for f in rep['pdf']['page_facts']], ['other', 'other', 'plan', 'other', 'other'])
        # Б5: эскиз и титул
        doc = pymupdf.open(); pg = doc.new_page(width=842, height=595); pg.draw_rect(pymupdf.Rect(60, 60, 780, 540), color=(0, 0, 0), width=2)
        for x in (240, 420, 600): pg.draw_line((x, 60), (x, 300), color=(0, 0, 0), width=1)
        pg.draw_line((60, 300), (780, 300), color=(0, 0, 0), width=1)
        for k in range(24): x = 90 + (k % 12) * 55; y = 360 + (k // 12) * 70; pg.draw_rect(pymupdf.Rect(x, y, x + 40, y + 20), color=(0, 0, 0), width=0.5); pg.draw_circle((x + 20, y + 30), 6, color=(0, 0, 0), width=0.3)
        text(pg, (90, 180), 'Переговорная', 12); p5 = os.path.join(td, 'b5.pdf'); doc.save(p5); rep = intake(p5, os.path.join(td, 'o5'))
        check('Б5: эскиз — pdf-vector и PDF_FEW_LINES', (rep.get('class'), 'PDF_FEW_LINES' in [w['code'] for w in rep['warnings']]), ('pdf-vector', True))
        doc = pymupdf.open(); pg = doc.new_page(width=842, height=595); pg.draw_rect(pymupdf.Rect(20, 20, 822, 575), color=(0, 0, 0), width=1)
        pg.draw_rect(pymupdf.Rect(520, 480, 822, 575), color=(0, 0, 0), width=0.7); text(pg, (200, 280), 'Титульный лист', 30)
        p6 = os.path.join(td, 'b6.pdf'); doc.save(p6); rep = intake(p6, os.path.join(td, 'o6'))
        check('Б5: титул — pdf-empty', rep.get('class'), 'pdf-empty')
        # доработка Б4: S1 — обложка-скан с заголовком плана и векторный план без заголовка словаря
        doc = pymupdf.open(); pg = doc.new_page(width=WW, height=HH); frame(pg)
        g = np.random.default_rng(5).integers(60, 200, (300, 400), dtype=np.uint8); b = io.BytesIO(); Image.fromarray(g, 'L').save(b, 'PNG')
        pg.insert_image(pymupdf.Rect(200, 200, 900, 700), stream=b.getvalue()); text(pg, (150, 150), 'ПЛАН РАССТАНОВКИ МЕБЕЛИ', 40)
        pg = doc.new_page(width=WW, height=HH); frame(pg); text(pg, (80, 70), 'FURNITURE LAYOUT, LEVEL 2', 20); plan(pg, 80, 100, 120)
        p7 = os.path.join(td, 's1.pdf'); doc.save(p7); rep = intake(p7, os.path.join(td, 'o7'))
        check('Б4/S1: обложка-скан с заголовком плана — выбран векторный план', (rep.get('chosen_page'), [f['class'] for f in rep['pdf']['page_facts']]), (2, ['pdf-scan', 'pdf-vector']))
        # S2 — экспликация со строкой «Планировка — открытая» мельче заголовка таблицы и план без текста
        doc = pymupdf.open(); pg = doc.new_page(width=WW, height=HH); frame(pg); text(pg, (80, 80), 'Экспликация помещений', 14)
        for r_ in range(16): pg.draw_line((80, 100 + r_ * 22), (700, 100 + r_ * 22), color=(0, 0, 0), width=0.4)
        for x_ in (80, 160, 560, 700): pg.draw_line((x_, 100), (x_, 430), color=(0, 0, 0), width=0.4)
        for r_ in range(14): text(pg, (90, 116 + r_ * 22), 'Планировка — открытая' if r_ == 6 else 'Помещение %d' % (r_ + 1), 10)
        pg = doc.new_page(width=WW, height=HH); frame(pg); plan(pg, 80, 100, 120)
        p8 = os.path.join(td, 's2.pdf'); doc.save(p8); rep = intake(p8, os.path.join(td, 'o8'))
        check('Б4/S2: экспликация со строкой «Планировка…» — выбран план', (rep.get('chosen_page'), [(f['class'], f['title_kind']) for f in rep['pdf']['page_facts']]),
              (2, [('pdf-empty', 'other'), ('pdf-vector', None)]))
        # доработка Б5: листы ГОСТ A3 без плана — S3 (рамка разбита в узлах штампа), S3c (рамка одним отрезком на сторону), S3d («Примечания»)
        k = 72 / 25.4
        def gost(pg, broken, notes):
            L = lambda a, b_, c, d: pg.draw_line((a * k, b_ * k), (c * k, d * k), color=(0, 0, 0), width=0.7)
            if broken: L(20, 5, 415, 5); L(20, 5, 20, 292); L(20, 292, 230, 292); L(230, 292, 415, 292); L(415, 5, 415, 237); L(415, 237, 415, 292)
            else: pg.draw_rect(pymupdf.Rect(20 * k, 5 * k, 415 * k, 292 * k), color=(0, 0, 0), width=0.7)
            for y in range(242, 292, 5): L(230, y, 295, y)
            for x in (237, 247, 270, 285, 295): L(x, 237, x, 292)
            L(295, 252, 415, 252); L(295, 277, 415, 277); L(230, 237, 415, 237)
            for y in (257, 262, 267, 272): L(365, y, 415, y)
            for x in (365, 380, 395): L(x, 252, x, 277)
            for t_, xy in (('Изм.', (231, 290)), ('Лист', (238, 290)), ('Стадия', (366, 256)), ('Лист', (381, 256))): text(pg, (xy[0] * k, xy[1] * k), t_, 7)
            if notes:                                             # доп. графы у поля подшивки, таблица изменений над штампом, текст примечаний
                L(8, 147, 8, 292); L(20, 147, 20, 292)
                for y in (147, 172, 207, 232, 257, 292): L(8, y, 20, y)
                for y in (212, 217, 222, 227, 232): L(230, y, 415, y)
                for x in (230, 240, 260, 300, 340, 415): L(x, 212, x, 232)
                text(pg, (40 * k, 30 * k), 'Примечания', 14)
                for i_ in range(8): text(pg, (40 * k, (42 + i_ * 8) * k), '%d. Размеры даны в миллиметрах; отметки — в метрах.' % (i_ + 1), 10)
        for nm, br, nt in (('S3', True, False), ('S3c', False, False), ('S3d', True, True)):
            doc = pymupdf.open(); pg = doc.new_page(width=420 * k, height=297 * k); gost(pg, br, nt)
            pp = os.path.join(td, nm + '.pdf'); doc.save(pp); rep = intake(pp, os.path.join(td, 'o' + nm))
            check('Б5/%s: лист ГОСТ без плана — pdf-empty, NOT_A_PLAN_PAGE' % nm, (rep.get('class'), 'NOT_A_PLAN_PAGE' in [w['code'] for w in rep['warnings']]), ('pdf-empty', True))
        # доработка 2: T2 — «Схема электрическая…» (≥ 500 отрезков) и план без заголовка с большим содержимым
        doc = pymupdf.open(); pg = doc.new_page(width=WW, height=HH); frame(pg); text(pg, (80, 70), 'Схема электрическая принципиальная щита ЩР-1', 14)
        for g_ in range(12):
            for k_ in range(45): pg.draw_line((100 + g_ * 70, 100 + k_ * 14), (100 + g_ * 70, 112 + k_ * 14), color=(0, 0, 0), width=0.4)
        pg = doc.new_page(width=WW, height=HH); frame(pg); plan(pg, 80, 100, 120)
        pp = os.path.join(td, 't2.pdf'); doc.save(pp); rep = intake(pp, os.path.join(td, 'oT2'))
        check('Б4/T2: «Схема электрическая…» — нейтрально, выбран план по содержимому', (rep.get('chosen_page'), [f['title_kind'] for f in rep['pdf']['page_facts']]), (2, [None, None]))
        # T3 — обложка-скан без текста и план, где «Экспликация помещений» крупнее заголовка плана
        doc = pymupdf.open(); pg = doc.new_page(width=WW, height=HH); frame(pg)
        g = np.random.default_rng(7).integers(60, 200, (300, 400), dtype=np.uint8); b = io.BytesIO(); Image.fromarray(g, 'L').save(b, 'PNG')
        pg.insert_image(pymupdf.Rect(200, 200, 900, 700), stream=b.getvalue())
        pg = doc.new_page(width=WW, height=HH); frame(pg); text(pg, (80, 70), 'План 2 этажа', 12); text(pg, (700, 70), 'Экспликация помещений', 14); plan(pg, 80, 100, 120)
        pp = os.path.join(td, 't3.pdf'); doc.save(pp); rep = intake(pp, os.path.join(td, 'oT3'))
        check('Б4/T3: обложка-скан и план с крупной экспликацией — выбран план', (rep.get('chosen_page'), [(f['class'], f['title_kind']) for f in rep['pdf']['page_facts']]),
              (2, [('pdf-scan', None), ('pdf-vector', 'plan')]))
        # T4 — план со «Спецификация мебели» крупнее заголовка плана и развертки с большим числом отрезков
        doc = pymupdf.open(); pg = doc.new_page(width=WW, height=HH); frame(pg); text(pg, (80, 70), 'План 2 этажа. Расстановка мебели', 12); text(pg, (700, 70), 'Спецификация мебели', 14); plan(pg, 80, 100, 120)
        pg = doc.new_page(width=WW, height=HH); frame(pg); text(pg, (80, 80), 'Развертки стен 2 этажа', 14)
        for bb in range(6):
            for k_ in range(300): pg.draw_line((60 + bb * 180, 120 + k_), (220 + bb * 180, 160 + k_), color=(0.3, 0.3, 0.3), width=0.2)
        pp = os.path.join(td, 't4.pdf'); doc.save(pp); rep = intake(pp, os.path.join(td, 'oT4'))
        check('Б4/T4: план с крупной спецификацией и развертки — выбран план по заголовку', (rep.get('chosen_page'), (rep.get('chosen_by') or '')[:12]), (1, 'по заголовку'))
        # доработка 2 (Б5): S6 — эскиз А4, стены в 15 мм от края, без рамки и штампа; S7 — разреженный план А3 ГОСТ, стены в 8 мм внутри рамки
        def L2(pg, a, b_, w=0.4): pg.draw_line((a[0] * k, a[1] * k), (b_[0] * k, b_[1] * k), color=(0, 0, 0), width=w)
        def walls2(pg, x0, y0, x1, y1, xs, yh):
            for a, b_ in (((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))): L2(pg, a, b_, 2)
            for x in xs: L2(pg, (x, y0), (x, yh), 1)
            L2(pg, (x0, yh), (x1, yh), 1)
        def desks2(pg, n, nx, x0, dx, y0, dy):
            for q in range(n):
                x = x0 + (q % nx) * dx; y = y0 + (q // nx) * dy
                pg.draw_rect(pymupdf.Rect(x * k, y * k, (x + 14) * k, (y + 7) * k), color=(0, 0, 0), width=0.5); pg.draw_circle(((x + 7) * k, (y + 11) * k), 2 * k, color=(0, 0, 0), width=0.3)
        doc = pymupdf.open(); pg = doc.new_page(width=297 * k, height=210 * k)
        walls2(pg, 15, 15, 282, 195, (90, 160, 230), 90); desks2(pg, 24, 12, 30, 20, 110, 40); text(pg, (30 * k, 50 * k), 'Переговорная', 10)
        pp = os.path.join(td, 's6.pdf'); doc.save(pp); rep = intake(pp, os.path.join(td, 'oS6'))
        check('Б5/S6: эскиз А4, стены у края — pdf-vector и PDF_FEW_LINES', (rep.get('class'), 'PDF_FEW_LINES' in [w['code'] for w in rep['warnings']]), ('pdf-vector', True))
        doc = pymupdf.open(); pg = doc.new_page(width=420 * k, height=297 * k); pg.draw_rect(pymupdf.Rect(20 * k, 5 * k, 415 * k, 292 * k), color=(0, 0, 0), width=1.4)
        pg.draw_rect(pymupdf.Rect(230 * k, 237 * k, 415 * k, 292 * k), color=(0, 0, 0), width=0.6)
        for q in range(1, 11): L2(pg, (230, 237 + q * 5), (295, 237 + q * 5), 0.3)
        for v_ in (7, 17, 40, 55, 65, 135, 150, 165): L2(pg, (230 + v_, 237), (230 + v_, 292))
        walls2(pg, 28, 13, 407, 227, (100, 180, 260, 340), 110); desks2(pg, 30, 15, 40, 24, 130, 45)
        pp = os.path.join(td, 's7.pdf'); doc.save(pp); rep = intake(pp, os.path.join(td, 'oS7'))
        check('Б5/S7: разреженный план А3 ГОСТ, стены у рамки — pdf-vector и PDF_FEW_LINES', (rep.get('class'), 'PDF_FEW_LINES' in [w['code'] for w in rep['warnings']], rep['pdf']['page_facts'][0].get('frame_stamp')), ('pdf-vector', True, True))
        # доработка 3: R1 — план с нераспознанным заголовком и таблицей «Экспликация» крупнее + «Схема кабельных трасс» (≥ 500 отрезков, меньше)
        doc = pymupdf.open(); pg = doc.new_page(width=WW, height=HH); frame(pg); text(pg, (80, 70), '2 этаж. Расстановка мебели', 12); text(pg, (700, 70), 'Экспликация помещений', 14); plan(pg, 80, 100, 120)
        pg = doc.new_page(width=WW, height=HH); frame(pg); text(pg, (80, 70), 'Схема кабельных трасс 2 этажа', 14)
        for q in range(110):
            x = 100 + (q % 22) * 40; y = 120 + (q // 22) * 120
            for j_ in range(5): pg.draw_line((x, y + j_ * 18), (x + (9 if j_ % 2 else -9), y + (j_ + 1) * 18), color=(0, 0, 0), width=0.3)
        pp = os.path.join(td, 'r1.pdf'); doc.save(pp); rep = intake(pp, os.path.join(td, 'oR1'))
        check('Б4/R1: план с нераспознанным заголовком и экспликацией — выбран план', (rep.get('chosen_page'), [(f['class'], f['title_kind']) for f in rep['pdf']['page_facts']]),
              (1, [('pdf-vector', None), ('pdf-vector', None)]))
        # R2 — два листа с заголовком плана: выбран лист с большим содержимым
        doc = pymupdf.open(); pg = doc.new_page(width=WW, height=HH); frame(pg); text(pg, (80, 70), 'Планировка 2 этажа', 14); plan(pg, 80, 100, 140)
        pg = doc.new_page(width=WW, height=HH); frame(pg); text(pg, (80, 70), 'Схема расстановки мебели 3 этажа', 14); plan(pg, 80, 100, 120)
        pp = os.path.join(td, 'r2.pdf'); doc.save(pp); rep = intake(pp, os.path.join(td, 'oR2'))
        check('Б4/R2: два листа с заголовком плана — по содержимому среди них', (rep.get('chosen_page'), (rep.get('chosen_by') or '')[:12], [f['title_kind'] for f in rep['pdf']['page_facts']]),
              (1, 'по заголовку', ['plan', 'plan']))
        # R3 — разреженный план А3 ГОСТ, стены в 2 мм внутри рамки
        doc = pymupdf.open(); pg = doc.new_page(width=420 * k, height=297 * k); pg.draw_rect(pymupdf.Rect(20 * k, 5 * k, 415 * k, 292 * k), color=(0, 0, 0), width=1.4)
        pg.draw_rect(pymupdf.Rect(230 * k, 237 * k, 415 * k, 292 * k), color=(0, 0, 0), width=0.6)
        for q in range(1, 11): L2(pg, (230, 237 + q * 5), (295, 237 + q * 5), 0.3)
        for v_ in (7, 17, 40, 55, 65, 135, 150, 165): L2(pg, (230 + v_, 237), (230 + v_, 292))
        walls2(pg, 22, 7, 413, 231, (100, 180, 260, 340), 110); desks2(pg, 30, 15, 40, 24, 130, 45)
        pp = os.path.join(td, 'r3.pdf'); doc.save(pp); rep = intake(pp, os.path.join(td, 'oR3'))
        check('Б5/R3: план А3 ГОСТ, стены в 2 мм от рамки — pdf-vector и PDF_FEW_LINES', (rep.get('class'), 'PDF_FEW_LINES' in [w['code'] for w in rep['warnings']], rep['pdf']['page_facts'][0].get('frame_stamp')), ('pdf-vector', True, True))
    else:
        print('нет шрифта DejaVuSans — Б4 и Б5 не проверены'); bad.append('шрифт')
print('итог:', 'всё совпало' if not bad else f'расхождений {len(bad)}'); sys.exit(1 if bad else 0)
