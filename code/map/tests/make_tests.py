"""Набор исходников для проверки приёма: один и тот же план client-d в разных форматах и с ловушками."""
import os, io, json, shutil
import numpy as np
from PIL import Image, ImageOps
import pymupdf, cairosvg

SRC = os.environ.get('UNS_INTAKE_REF', '/home/claude/work/layers/client-d/input/raw.png')           # исходник client-d, 1476 × 1296
SVG = os.environ.get('UNS_INTAKE_SVG', '/home/claude/work/layers/client-d/final/client-d_v4-1.svg')
OUT = os.environ.get('UNS_INTAKE_TESTS', '/home/claude/work/intake/tests')
if not os.path.exists(SRC) or not os.path.exists(SVG): raise SystemExit(f'нет исходника {SRC} или SVG {SVG} — задайте UNS_INTAKE_REF и UNS_INTAKE_SVG')
shutil.rmtree(OUT, ignore_errors=True); os.makedirs(OUT)
raw = Image.open(SRC).convert('RGB')
W, H = raw.size
a = np.asarray(raw)
bg = (a.min(axis=2) > 235)                                            # фон листа
cases = {}

def add(name, expect, note):
    cases[name] = {'expect': expect, 'note': note}

raw.save(f'{OUT}/t01_png_rgb.png'); add('t01_png_rgb.png', {'class': 'raster'}, 'PNG RGB, как пришёл')
raw.save(f'{OUT}/t02_jpeg_q90.jpg', quality=90); add('t02_jpeg_q90.jpg', {'class': 'raster', 'warn': ['JPEG_CHROMA']}, 'JPEG 90')
raw.save(f'{OUT}/t03_jpeg_q30.jpg', quality=30); add('t03_jpeg_q30.jpg', {'class': 'raster', 'warn': ['JPEG_LOWQ']}, 'JPEG 30, сильное сжатие')
# EXIF 6: пиксели лежат повёрнутыми на 90° против часовой, показывать — повернуть по часовой
st = raw.transpose(Image.ROTATE_90)
ex = Image.Exif(); ex[274] = 6; ex[271] = 'Apple'; ex[272] = 'iPhone 15'
st.save(f'{OUT}/t04_jpeg_exif6.jpg', quality=92, exif=ex.tobytes())
add('t04_jpeg_exif6.jpg', {'class': 'raster', 'warn': ['EXIF_ROTATED', 'PHOTO'], 'size': [W, H]}, 'JPEG с телефона, флаг поворота EXIF 6')
# PNG с прозрачным фоном: под альфой 0 — чёрный RGB, как при экспорте из многих программ
rgba = np.dstack([a.copy(), np.full((H, W), 255, np.uint8)])
rgba[bg, :3] = 0; rgba[bg, 3] = 0
Image.fromarray(rgba, 'RGBA').save(f'{OUT}/t05_png_alpha.png')
add('t05_png_alpha.png', {'class': 'raster', 'warn': ['ALPHA_FLATTENED']}, 'PNG, прозрачный фон')
# палитра с прозрачным индексом
pal = raw.quantize(colors=64, method=Image.MEDIANCUT)
pa = np.asarray(pal); idx = int(np.bincount(pa[bg]).argmax())
pal.info['transparency'] = idx
pal.save(f'{OUT}/t06_png_palette_trns.png', transparency=idx)
add('t06_png_palette_trns.png', {'class': 'raster', 'warn': ['PALETTE', 'ALPHA_FLATTENED']}, 'PNG-палитра 64 цвета, фон — прозрачный индекс')
# 16 бит серый
g16 = (np.asarray(raw.convert('L')).astype(np.uint32) * 257).astype(np.uint16)
Image.fromarray(g16).save(f'{OUT}/t07_png_gray16.png')
add('t07_png_gray16.png', {'class': 'raster', 'warn': ['BIT16']}, 'PNG 16 бит, серый')
raw.convert('CMYK').save(f'{OUT}/t08_jpeg_cmyk.jpg', quality=92)
add('t08_jpeg_cmyk.jpg', {'class': 'raster', 'warn': ['CMYK']}, 'JPEG CMYK')
raw.save(f'{OUT}/t09_png_named_jpg.jpg', format='PNG')
add('t09_png_named_jpg.jpg', {'class': 'raster', 'kind': 'png', 'warn': ['EXT_MISMATCH']}, 'PNG с расширением .jpg')
Image.fromarray(255 - a).save(f'{OUT}/t10_png_dark.png')
add('t10_png_dark.png', {'class': 'raster', 'warn': ['DARK_BACKGROUND']}, 'тёмный фон, как CAD')
raw.resize((W // 2, H // 2), Image.LANCZOS).save(f'{OUT}/t11_png_small.png')
add('t11_png_small.png', {'class': 'raster', 'warn': ['SMALL_RASTER']}, 'маленький растр 738 px')
raw.save(f'{OUT}/t12_webp.webp', quality=90)
add('t12_webp.webp', {'class': 'raster'}, 'WEBP')

def pdf_with_image(img_bytes, path, dpi=150, rotate=0, ocr=False, extra=None):
    doc = pymupdf.open(); wpt, hpt = W * 72 / dpi, H * 72 / dpi
    p = doc.new_page(width=wpt, height=hpt)
    p.insert_image(p.rect, stream=img_bytes)
    if ocr:                                                           # невидимый слой OCR, как у сканеров
        for i, t in enumerate(['3.01 Кабинет', '3.02 Переговорная', '3.10 Опенспейс', 'Этаж 3']):
            p.insert_text((40 + 120 * i, 60 + 30 * i), t, fontsize=9, render_mode=3, fontname='helv')
    if extra:
        extra(p)
    if rotate:
        p.set_rotation(rotate)
    doc.save(path)

b90 = open(f'{OUT}/t02_jpeg_q90.jpg', 'rb').read()
pdf_with_image(b90, f'{OUT}/t13_pdf_scan.pdf')
add('t13_pdf_scan.pdf', {'class': 'pdf-scan'}, 'PDF со сканом, 150 dpi')
pdf_with_image(b90, f'{OUT}/t14_pdf_scan_ocr.pdf', ocr=True)
add('t14_pdf_scan_ocr.pdf', {'class': 'pdf-scan', 'warn': ['PDF_OCR_LAYER']}, 'скан с невидимым текстом OCR')
pdf_with_image(open(f'{OUT}/t05_png_alpha.png', 'rb').read(), f'{OUT}/t15_pdf_scan_smask.pdf')
add('t15_pdf_scan_smask.pdf', {'class': 'pdf-scan', 'warn': ['PDF_SMASK']}, 'скан PNG с прозрачностью внутри PDF')
small = io.BytesIO(); raw.resize((W // 3, H // 3)).save(small, 'JPEG', quality=85)
pdf_with_image(small.getvalue(), f'{OUT}/t16_pdf_scan_lowres.pdf', dpi=50)
# v012 (Б21): страница 50 dpi — 750 × 659 мм, не формат бумаги: dpi страницы не мера — картинка 492 px, как у растра — SMALL_RASTER
add('t16_pdf_scan_lowres.pdf', {'class': 'pdf-scan', 'warn': ['SMALL_RASTER'], 'no_warn': ['PDF_LOWRES_SCAN']}, 'скан 50 dpi на странице не формата бумаги')
d = pymupdf.open(); p = d.new_page(width=842, height=595); p.insert_image(p.rect, stream=small.getvalue()); d.save(f'{OUT}/t16b_pdf_scan_lowres_a4.pdf')
add('t16b_pdf_scan_lowres_a4.pdf', {'class': 'pdf-scan', 'warn': ['PDF_LOWRES_SCAN']}, 'скан ≈ 42 dpi на A4 (v012, Б21)')
# вектор: SVG v4-1 → PDF
cairosvg.svg2pdf(url=SVG, write_to=f'{OUT}/t17_pdf_vector.pdf')
add('t17_pdf_vector.pdf', {'class': 'pdf-vector'}, 'векторный PDF из чистовика v4-1')
# повёрнутый вектор
d = pymupdf.open(f'{OUT}/t17_pdf_vector.pdf'); d[0].set_rotation(90); d.save(f'{OUT}/t18_pdf_vector_rot90.pdf')
add('t18_pdf_vector_rot90.pdf', {'class': 'pdf-vector', 'warn': ['PDF_ROTATED']}, 'векторный PDF, /Rotate 90')
# смешанный: растр плана под вектором зон
def mixed(path, rotate=0):
    d = pymupdf.open(f'{OUT}/t17_pdf_vector.pdf'); p = d[0]
    p.insert_image(p.rect, stream=b90, overlay=False)
    if rotate:
        p.set_rotation(rotate)
    d.save(path)
mixed(f'{OUT}/t19_pdf_mixed.pdf')
add('t19_pdf_mixed.pdf', {'class': 'pdf-mixed'}, 'картинка плана под векторной разметкой')
# составной: главная картинка + три вставки с поворотом, как клиент В 15 э.
def insets(p):
    crop = io.BytesIO(); raw.crop((200, 200, 500, 420)).save(crop, 'PNG')
    for k, r in enumerate([(30, 30, 130, 110), (150, 30, 250, 110), (270, 30, 370, 110)]):
        p.insert_image(pymupdf.Rect(*r), stream=crop.getvalue(), rotate=90 * (k + 1))
pdf_with_image(b90, f'{OUT}/t20_pdf_composite.pdf', extra=insets)
add('t20_pdf_composite.pdf', {'class': 'pdf-composite', 'warn': ['PDF_ROTATED_INSETS']}, 'картинка плана и три повёрнутые вставки')
# многостраничный: титул и лист плана
d = pymupdf.open(); t = d.new_page(); t.insert_text((72, 100), 'Титульный лист. Альбом планировок', fontname='helv')
d.insert_pdf(pymupdf.open(f'{OUT}/t17_pdf_vector.pdf')); d.save(f'{OUT}/t21_pdf_multipage.pdf')
add('t21_pdf_multipage.pdf', {'class': 'pdf-vector', 'page': 2}, 'титул и лист плана')
# два листа плана
d = pymupdf.open(f'{OUT}/t17_pdf_vector.pdf'); d.insert_pdf(pymupdf.open(f'{OUT}/t13_pdf_scan.pdf')); d.save(f'{OUT}/t22_pdf_two_plans.pdf')
add('t22_pdf_two_plans.pdf', {'class': 'pdf-vector', 'warn': ['PDF_MULTIPAGE']}, 'два листа с планом')
# аннотации клиента поверх вектора
d = pymupdf.open(f'{OUT}/t17_pdf_vector.pdf'); p = d[0]
an = p.add_rect_annot(pymupdf.Rect(100, 100, 300, 250)); an.set_colors(stroke=(1, 0, 0)); an.update()
p.add_text_annot((320, 120), 'Зона отдела продаж'); d.save(f'{OUT}/t23_pdf_annots.pdf')
add('t23_pdf_annots.pdf', {'class': 'pdf-vector', 'warn': ['PDF_ANNOTATIONS']}, 'аннотации клиента')
# под паролем
d = pymupdf.open(f'{OUT}/t17_pdf_vector.pdf')
d.save(f'{OUT}/t24_pdf_encrypted.pdf', encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw='client', owner_pw='owner')
add('t24_pdf_encrypted.pdf', {'class': 'pdf-encrypted', 'warn': ['PDF_ENCRYPTED']}, 'PDF под паролем')
json.dump(cases, open(f'{OUT}/cases.json', 'w'), ensure_ascii=False, indent=1)
print(len(cases), 'cases')

# дополнительные: повёрнутый скан, многокадровый TIFF, EXIF 3 и 8
pdf_with_image(b90, f'{OUT}/t25_pdf_scan_rot90.pdf', rotate=90)
cases['t25_pdf_scan_rot90.pdf'] = {'expect': {'class': 'pdf-scan', 'warn': ['PDF_ROTATED'], 'size_swapped': True}, 'note': 'скан в PDF, /Rotate 90'}
raw.save(f'{OUT}/t26_tiff_2pages.tif', save_all=True, append_images=[raw.convert('L')])
cases['t26_tiff_2pages.tif'] = {'expect': {'class': 'raster', 'warn': ['MULTI_FRAME']}, 'note': 'TIFF из двух страниц'}
for o, tr in ((3, Image.ROTATE_180), (8, Image.ROTATE_270)):
    ex = Image.Exif(); ex[274] = o
    raw.transpose(tr).save(f'{OUT}/t27_jpeg_exif{o}.jpg', quality=92, exif=ex.tobytes())
    cases[f't27_jpeg_exif{o}.jpg'] = {'expect': {'class': 'raster', 'warn': ['EXIF_ROTATED'], 'size': [W, H]}, 'note': f'JPEG, флаг поворота EXIF {o}'}
# v012 (Б17, УН-3): скан на нижних 40 % листа A4, /Rotate 90 — доля картинки в повёрнутых координатах; v011 — pdf-empty (t25 ошибку прячет)
d = pymupdf.open(); p = d.new_page(width=595, height=842); p.insert_image(pymupdf.Rect(0, 0.6 * 842, 595, 842), stream=b90, keep_proportion=False); p.set_rotation(90)
d.save(f'{OUT}/t28_pdf_scan40_rot90.pdf')
cases['t28_pdf_scan40_rot90.pdf'] = {'expect': {'class': 'pdf-scan', 'warn': ['PDF_ROTATED']}, 'note': 'скан на 40 % листа A4, /Rotate 90 (v012, Б17)'}
# v012 (Б19): четыре плитки одной картинки стык в стык — один скан
d = pymupdf.open(); wpt, hpt = W * 72 / 150, H * 72 / 150; p = d.new_page(width=wpt, height=hpt)
for x0, y0 in ((0, 0), (W // 2, 0), (0, H // 2), (W // 2, H // 2)):
    t_ = io.BytesIO(); raw.crop((x0, y0, x0 + W // 2, y0 + H // 2)).save(t_, 'JPEG', quality=90)
    p.insert_image(pymupdf.Rect(x0 * 72 / 150, y0 * 72 / 150, (x0 + W // 2) * 72 / 150, (y0 + H // 2) * 72 / 150), stream=t_.getvalue())
d.save(f'{OUT}/t29_pdf_scan_tiles.pdf')
cases['t29_pdf_scan_tiles.pdf'] = {'expect': {'class': 'pdf-scan', 'warn': ['PDF_TILES']}, 'note': 'скан из 4 плиток одной картинки (v012, Б19)'}
json.dump(cases, open(f'{OUT}/cases.json', 'w'), ensure_ascii=False, indent=1)
print(len(cases), 'cases total')
