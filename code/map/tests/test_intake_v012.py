"""Тест приёма v012 (пакет кода карты v012; УН-3: ОЧ-Б17…Б22, ОЧ-Б6; УН-5 П-1). Без внешних данных: PDF и растры собираются здесь.
Б17 — скан на 40 % листа с /Rotate 90: доля картинки — в повёрнутых координатах (v011 — 0, pdf-empty), класс pdf-scan; native — не повёрнут, сказано.
Б18 — скан с векторной разметкой поверх (заливка, слова) — PDF_SCAN_OVERLAY с числом путей, слов и долей заливки; чистый скан — без него.
Б19 — четыре плитки одной картинки стык в стык — pdf-scan, плиток 4, native — общая рамка; главная картинка и три вставки с поворотом — pdf-composite.
Б20 — intake.md: «work.png = 2,78 × картинка» у скана 72 dpi при рендере 200 dpi.
Б21 — PDF_LOWRES_SCAN только у страницы формата бумаги: скан 100 dpi на A4 — есть; тот же скан на странице 560 × 460 мм — нет; мелкая картинка
на странице не формата бумаги — SMALL_RASTER; в советах нет «5–6 см».
Б22 — RASTER_CUT_EDGE: растр, где линии плана уходят за правый край, — есть (справа ≥ 5); план с полями — нет; пороги — в долях кадра.
Б6 — текст cp1251, прочитанный как latin-1, — TEXT_CP1251_AS_LATIN1 и перекодировка fix_cp1251; французский текст с диакритикой — без флага.
Запуск из любой папки: python3 tests/test_intake_v012.py — код 0, если всё совпало."""
import io, os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np, pymupdf
from PIL import Image, ImageDraw
import source_intake as si
from source_intake import intake
bad = []
def check(name, got, want):
    ok = got == want; print(('ok   ' if ok else 'FAIL ') + name + ('' if ok else f': {got!r} != {want!r}')); ok or bad.append(name)
codes = lambda rep: sorted(w['code'] for w in rep.get('warnings', []))


def plan_img(w, h, margin=0.08, cut_right=False, seed=1):
    """растр «плана»: стены 3 px, перегородки; cut_right — план уходит за правый край (линии до края)"""
    im = Image.new('RGB', (w, h), 'white'); d = ImageDraw.Draw(im); m = int(margin * min(w, h))
    x1 = w + 5 if cut_right else w - m
    d.rectangle([m, m, x1, h - m], outline='black', width=3)
    rng = np.random.default_rng(seed)
    for k in range(1, 12):
        y = m + k * (h - 2 * m) // 12; d.line([(m, y), (x1, y)], fill='black', width=2)
    for k in range(1, 8):
        x = m + k * (w - 2 * m) // 8; d.line([(x, m), (x, h - m)], fill='black', width=2)
    for _ in range(40):
        x, y = rng.integers(m + 10, w - m - 40), rng.integers(m + 10, h - m - 30); d.rectangle([x, y, x + 25, y + 14], outline='black', width=1)
    return im


def png_bytes(im, fmt='PNG'):
    b = io.BytesIO(); im.save(b, fmt, **({'quality': 90} if fmt == 'JPEG' else {})); return b.getvalue()


MM = 72 / 25.4
with tempfile.TemporaryDirectory() as td:
    # Б17: скан на нижних 40 % листа A4 (книжный), /Rotate 90 (УН-3, синтетика bottom40_r90: v011 — pdf-empty)
    doc = pymupdf.open(); W, H = 595, 842; p = doc.new_page(width=W, height=H)
    p.insert_image(pymupdf.Rect(0, 0.6 * H, W, H), stream=png_bytes(plan_img(1654, 936)))
    p.set_rotation(90); pp = os.path.join(td, 'b17.pdf'); doc.save(pp); rep = intake(pp, os.path.join(td, 'o17'))
    f = rep['pdf']['page_facts'][0]
    check('Б17: скан на 40 % листа с /Rotate 90 — pdf-scan, доля картинки 0,40', (rep.get('class'), round(f['image_cover'], 2)), ('pdf-scan', 0.4))
    check('Б17: native — не повёрнут, сказано в intake.md', (rep['native']['page_rotation'], rep['native']['rotated_like_work'], 'не повёрнут' in open(os.path.join(td, 'o17', 'intake.md'), encoding='utf-8').read()), (90, False, True))
    # тот же скан без поворота — как и был
    doc = pymupdf.open(); p = doc.new_page(width=W, height=H); p.insert_image(pymupdf.Rect(0, 0.6 * H, W, H), stream=png_bytes(plan_img(1654, 936)))
    pp = os.path.join(td, 'b17n.pdf'); doc.save(pp); rep = intake(pp, os.path.join(td, 'o17n'))
    check('Б17: тот же скан без /Rotate — pdf-scan, 0,40', (rep.get('class'), round(rep['pdf']['page_facts'][0]['image_cover'], 2)), ('pdf-scan', 0.4))

    # Б18: скан с разметкой поверх
    doc = pymupdf.open(); p = doc.new_page(width=W, height=H); p.insert_image(p.rect, stream=png_bytes(plan_img(1654, 2339)))
    for k in range(4): p.draw_rect(pymupdf.Rect(100 + 90 * k, 200, 170 + 90 * k, 260), color=(1, 0, 0), fill=(1, 1, 1), width=1)
    p.insert_text((100, 300), 'Zona 1', fontname='helv', fontsize=9)
    pp = os.path.join(td, 'b18.pdf'); doc.save(pp); rep = intake(pp, os.path.join(td, 'o18'))
    o = rep.get('overlay') or {}
    check('Б18: скан с разметкой — PDF_SCAN_OVERLAY, путей 4, слов 2, доля заливки > 0', ('PDF_SCAN_OVERLAY' in codes(rep), o.get('paths'), o.get('words'), (o.get('filled_share_of_image') or 0) > 0), (True, 4, 2, True))
    rep = intake(os.path.join(td, 'b17n.pdf'), os.path.join(td, 'o18c'))
    check('Б18: чистый скан — без PDF_SCAN_OVERLAY', 'PDF_SCAN_OVERLAY' in codes(rep), False)

    # Б19: четыре плитки одной картинки 200 dpi стык в стык (2 × 2)
    big = plan_img(1600, 1100); doc = pymupdf.open(); p = doc.new_page(width=1600 * 72 / 200, height=1100 * 72 / 200)
    for i, (x0, y0) in enumerate(((0, 0), (800, 0), (0, 550), (800, 550))):
        tile = big.crop((x0, y0, x0 + 800, y0 + 550)); p.insert_image(pymupdf.Rect(x0 * 0.36, y0 * 0.36, (x0 + 800) * 0.36, (y0 + 550) * 0.36), stream=png_bytes(tile, 'JPEG'))
    pp = os.path.join(td, 'b19.pdf'); doc.save(pp); rep = intake(pp, os.path.join(td, 'o19'))
    n = rep.get('native') or {}
    check('Б19: 4 плитки — pdf-scan, PDF_TILES, плиток 4, native — общая рамка 1600 × 1100', (rep.get('class'), 'PDF_TILES' in codes(rep), n.get('tiles'), n.get('px')), ('pdf-scan', True, 4, [1600, 1100]))
    check('Б19: native плиток — не PDF_NATIVE_RENDER', 'PDF_NATIVE_RENDER' in codes(rep), False)
    # главная картинка + три вставки с поворотом — составной
    doc = pymupdf.open(); p = doc.new_page(width=W, height=H); p.insert_image(p.rect, stream=png_bytes(plan_img(1000, 1414)))
    crop = png_bytes(plan_img(300, 220))
    for k, r in enumerate([(30, 30, 130, 110), (150, 30, 250, 110), (270, 30, 370, 110)]): p.insert_image(pymupdf.Rect(*r), stream=crop, rotate=90 * (k + 1))
    pp = os.path.join(td, 'b19c.pdf'); doc.save(pp); rep = intake(pp, os.path.join(td, 'o19c'))
    check('Б19: главная + 3 вставки с поворотом — pdf-composite, не плитки', (rep.get('class'), rep['pdf']['page_facts'][0].get('tiles')), ('pdf-composite', None))

    # Б20 и Б21: скан 72 dpi на странице 560 × 460 мм (не формат бумаги)
    wpt, hpt = 560 * MM, 460 * MM; im = plan_img(int(wpt), int(hpt))                   # 72 dpi: 1 px = 1 pt
    doc = pymupdf.open(); p = doc.new_page(width=wpt, height=hpt); p.insert_image(p.rect, stream=png_bytes(im, 'JPEG'))
    pp = os.path.join(td, 'b20.pdf'); doc.save(pp); rep = intake(pp, os.path.join(td, 'o20')); md = open(os.path.join(td, 'o20', 'intake.md'), encoding='utf-8').read()
    check('Б20: intake.md — «work.png = 2,78 × картинка»', ('`work.png` = 2,78 × картинка' in md, rep['native']['work_scale_k']), (True, 2.778))
    check('Б21: 72 dpi на странице не формата бумаги — без PDF_LOWRES_SCAN, формат — None', ('PDF_LOWRES_SCAN' in codes(rep), rep['native']['paper']), (False, None))
    doc = pymupdf.open(); p = doc.new_page(width=W, height=H); p.insert_image(p.rect, stream=png_bytes(plan_img(827, 1169), 'JPEG'))   # A4, 100 dpi
    pp = os.path.join(td, 'b21a4.pdf'); doc.save(pp); rep = intake(pp, os.path.join(td, 'o21'))
    check('Б21: 100 dpi на A4 — PDF_LOWRES_SCAN, формат A4', ('PDF_LOWRES_SCAN' in codes(rep), rep['native']['paper']), (True, 'A4'))
    doc = pymupdf.open(); p = doc.new_page(width=wpt, height=hpt); p.insert_image(p.rect, stream=png_bytes(plan_img(800, 657), 'JPEG'))
    pp = os.path.join(td, 'b21s.pdf'); doc.save(pp); rep = intake(pp, os.path.join(td, 'o21s'))
    check('Б21: картинка 800 px на странице не формата бумаги — SMALL_RASTER, без PDF_LOWRES_SCAN', ('SMALL_RASTER' in codes(rep), 'PDF_LOWRES_SCAN' in codes(rep)), (True, False))
    check('Б21 / УН-5 П-1: в советах нет «5–6 см»', any('5–6 см' in si.ADVICE[c] for c in ('SMALL_RASTER', 'PDF_LOWRES_SCAN')), False)
    check('Б21: формат бумаги ± 3 %: Letter, A3 альбомный, 557 × 457 мм — нет', (si.paper_format(612, 792), si.paper_format(1191, 842), si.paper_format(557 * MM, 457 * MM)), ('Letter', 'A3', None))

    # Б22: растр с планом за правым краем — RASTER_CUT_EDGE; с полями — нет; пороги в долях кадра
    for nm, im_, want in (('cut', plan_img(1400, 900, cut_right=True), True), ('ok', plan_img(1400, 900), False), ('cut_big', plan_img(4200, 2700, cut_right=True), True)):
        pth = os.path.join(td, f'b22_{nm}.png'); im_.save(pth); rep = intake(pth, os.path.join(td, f'o22_{nm}'))
        e = rep['raster']['edge_cut']
        check(f'Б22: растр {im_.size[0]} px, {nm} — RASTER_CUT_EDGE {want}', ('RASTER_CUT_EDGE' in codes(rep), e['право'] >= 5 if want else max(e[k] for k in ('лево', 'право', 'верх', 'низ')) < 5), (want, True))
    check('Б22: глубина и ширина — в долях кадра (1400 px: 14 и 28; 4200 px: 42 и 84)', (si.edge_cut(plan_img(1400, 900))['depth_px'], si.edge_cut(plan_img(1400, 900))['run_px'], si.edge_cut(plan_img(4200, 2700))['depth_px']), (14, 28, 42))

    # Б6: текст cp1251, прочитанный как latin-1
    FONT = next((f for f in ('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', '/usr/share/fonts/dejavu/DejaVuSans.ttf') if os.path.exists(f)), None)
    words = ['Переговорная', 'Кабинет руководителя', 'Опенспейс', 'Кухня', 'Библиотека', 'Ресепшн']
    doc = pymupdf.open(); p = doc.new_page(width=1190, height=842)
    for k in range(700): p.draw_line((50 + (k % 70) * 15, 60 + (k // 70) * 70), (60 + (k % 70) * 15, 100 + (k // 70) * 70), width=0.5)
    for k, w_ in enumerate(words): p.insert_text((80, 120 + 40 * k), w_.encode('cp1251').decode('latin-1'), fontname='helv', fontsize=10)
    pp = os.path.join(td, 'b6.pdf'); doc.save(pp); rep = intake(pp, os.path.join(td, 'o6'))
    c = rep['pdf']['page_facts'][0].get('cp1251_as_latin1') or {}
    check('Б6: cp1251 как latin-1 — TEXT_CP1251_AS_LATIN1, пример перекодирован', ('TEXT_CP1251_AS_LATIN1' in codes(rep), any(x[1] == 'Переговорная' for x in c.get('examples', []))), (True, True))
    check('Б6: fix_cp1251 — «Ïåðåãîâîðíàÿ» → «Переговорная»; кириллица — как есть', (si.fix_cp1251('Ïåðåãîâîðíàÿ'), si.fix_cp1251('Кухня')), ('Переговорная', 'Кухня'))
    doc = pymupdf.open(); p = doc.new_page(width=1190, height=842)
    for k in range(700): p.draw_line((50 + (k % 70) * 15, 60 + (k // 70) * 70), (60 + (k % 70) * 15, 100 + (k // 70) * 70), width=0.5)
    for k, w_ in enumerate(['Salle de réunion', 'Bureau du directeur', 'Cafétéria', 'Réception', 'Bibliothèque', 'Espace ouvert']): p.insert_text((80, 120 + 40 * k), w_, fontname='helv', fontsize=10)
    pp = os.path.join(td, 'b6fr.pdf'); doc.save(pp); rep = intake(pp, os.path.join(td, 'o6fr'))
    check('Б6: французский текст с диакритикой — без флага', 'TEXT_CP1251_AS_LATIN1' in codes(rep), False)
print('итог:', 'всё совпало' if not bad else f'расхождений {len(bad)}'); sys.exit(1 if bad else 0)
