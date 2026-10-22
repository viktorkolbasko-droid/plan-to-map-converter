#!/usr/bin/env python3
"""Приём исходника карты UnSpot: формат по содержимому, тип PDF, рабочий растр.

    python source_intake.py SRC [--out DIR] [--page N] [--dpi 200] [--max-side 10000]

Пишет в DIR:
  intake.json  — всё, что найдено: формат, хеш оригинала, страницы PDF, предупреждения, маршрут;
  intake.md    — то же таблицей для отчёта прохода (map/rules/80, Ч-01 и Ч-02);
  work.png     — рабочий растр: 8 бит RGB, повёрнут как на экране, прозрачность на белом;
  work_noannot.png — PDF с аннотациями: рендер без них (цветовые маски — map/rules/10 §5.0);
  native_<xref>.png — для скана в PDF: картинка в исходном разрешении, прозрачность на белом;
  preview.png  — уменьшенная копия для просмотра, если рабочий растр больше 4000 px.

Оригинал не меняется. Тип определяется по содержимому, а не по расширению.
v007 (06.10.2026): dc:title — hex-строка «<5C5C…>» декодируется (cp1251, иначе utf-8; хвост неполного байта отбрасывается), путь модели —
в intake.json и intake.md; путь к .rvt или папке REVIT — признак Revit (П3 «Признаки происхождения векторного PDF»).
v005 (02.10.2026): предупреждение PDF_FLATTENED — «распечатанный» векторный лист (map/rules/11 §1); в page_facts — zero_share,
one_item_share, fills_only_re (клиент А, 4 этаж: 60,5 % отрезков нулевой длины; 5 этаж: 69 %).
v011 (07.10.2026, пакет кода 5; измеритель «12», Б1, Б4, Б5): Б1 — у картинки скана уже есть альфа: снять её до маски прозрачности
(Pixmap(pix, 0)); картинку не извлечь — native — рендер её области в исходном разрешении, предупреждение PDF_NATIVE_RENDER;
Б4 — лист альбома — по заголовку страницы («План…», «Схема…», «Расстановка мебели» — план; «Развертки…», «Экспликация…», «Ведомость…» — нет),
без заголовка — по содержимому, как раньше; Б5 — «на листе нет плана» — долей листа: линии плана (без рамки) не короче двух периметров листа
и проходят через ≥ 10 % клеток сетки 40 × 40; меньше 500 отрезков при этом — предупреждение PDF_FEW_LINES (эскиз, схема).
v011, доработки после независимой проверки: Б4 — сначала класс по содержимому по всем листам, внутри лучшего класса листы «другого» заголовка —
в конце, лист с заголовком плана — при содержимом ≥ 0,5 лучшего; строка плана — заголовок, если не мельче 0,6 самой крупной строки словаря на листе
с чертежом (≥ 500 отрезков) и 0,9 — на листе без чертежа; «Схема…» — план только со словом плана офиса; таблица («Экспликация…») — «другой лист»
только без чертежа; Б5 — рамка со штампом в правом нижнем углу (замкнутый прямоугольник у края и сетка штампа): линии между краем
и рамкой, рамка и зона штампа не в счёт (лист «Примечания» — не план), стены у рамки — в счёт; без рамки со штампом — как раньше.
v012 (13.10.2026, пакет кода карты v012, исполнитель 2; УН-3 ОЧ-Б17…Б22, ОЧ-Б6; УН-5 П-1): Б17 — рамка картинки на странице с /Rotate —
× rotation_matrix (доля картинок, clip запасного рендера native); Б18 — PDF_SCAN_OVERLAY: пути или слова поверх скана; Б19 — плитки одной
картинки — один скан (PDF_TILES, native — общая рамка в их dpi); Б20 — intake.md «work.png = k × картинка»; Б21 — PDF_LOWRES_SCAN только
у страницы формата бумаги (A, B, Letter, Legal, Tabloid ± 3 %), иначе — длина картинки, как SMALL_RASTER; советы о разрешении — в мм/px после
масштаба, без «5–6 см»; Б22 — RASTER_CUT_EDGE: план обрезан краем кадра, пороги — в долях длинной стороны кадра; Б6 — текст cp1251,
прочитанный как latin-1, — TEXT_CP1251_AS_LATIN1, заголовок страницы — после перекодировки (fix_cp1251).
v014 (17.10.2026, ПР6 — остаток ОЧ-53 из черновика 0816, часть B паспорта): И2 — RASTER_1280 (длинная сторона 1280 ± 2 px — свойство
файла после мессенджера), PDF_SCAN_LOWQ (JPEG картинки скана в PDF сжат сильнее LOWQ_JPEG; native.jpeg_quality); LOWRES_RASTER черновика
(1000–1300 px) не перенесён — новых порогов в px нет, SMALL_RASTER_SIDE — «первая оценка», решение в мм/px — map/rules/10 §5.7 (Б21-остаток).
И1 — паспорт исходника (passport.py): профиль П01–П16 и сводка для первого ответа — intake.json, поле passport; intake.md, раздел
«Паспорт исходника»; паспорт не роняет приём — passport_error. И13/И14/П-239 — заголовки видов листа (page_titles: ранг, этажи, «План
перегородок»), pdf.plan_candidates и pdf.walls_pages, предупреждения PDF_PLAN_CANDIDATES, PDF_MULTI_FLOOR, PDF_WALLS_SHEET, в intake.md —
«Листы-планы по заголовкам»; лист по-прежнему выбирает choose_page (выбор по рангу заголовка — вопрос владельцу ОЧ-54).
v014 (ПРV — исправления по независимой проверке, 17.10.2026): К2 — любое исключение в ветке CAD ловится: класс cad-error,
DWG_READ_FAILED / DXF_READ_FAILED с коротким текстом ошибки, rep.stop, intake.json и intake.md пишутся, код выхода 2 (было: traceback,
код 1, intake.json нет); подробность предупреждения (путь, ошибка) — из rep._warn_detail в warnings[].what (К2, К5).
Зависимости: Pillow, numpy; для PDF — pymupdf (pip install pymupdf).
"""
import argparse, hashlib, io, json, os, re, sys, zipfile

import numpy as np
from PIL import Image, ImageOps

Image.MAX_IMAGE_PIXELS = 400_000_000          # защита от «бомбы» распаковки: выше — отказ с причиной

VECTOR_MIN_SEGMENTS = 500      # v011 (Б5): меньше отрезков — только предупреждение PDF_FEW_LINES «мало линий»; план или нет — долей листа:
VECTOR_MIN_LENGTH = 2.0        # v011 (Б5): длина линий без рамки — не меньше двух периметров листа
VECTOR_MIN_CELLS = 0.10        # v011 (Б5): и линии проходят через ≥ 10 % клеток сетки 40 × 40 листа
GRID = 40
FRAME_MAX_MM = 30.0            # v011 (Б5, доработка 2): рамка ГОСТ — замкнутый прямоугольник: каждая сторона — прямая (один отрезок или цепочка) в 30 мм от края,
FRAME_SIDE_SHARE = 0.8         #   длиной ≥ 0,8 стороны листа; из таких прямых — ближайшая к краю (стена плана у рамки — внутри неё, синтетика S7)
STAMP_MM = (190.0, 62.0)       # v011 (Б5, доработка 2): основная надпись — в правом нижнем углу рамки: верхняя линия ≥ STAMP_TOP_MM, ниже неё ≥ 3 вертикали сетки
STAMP_TOP_MM = 150.0
GOST_MIN_SIDE_MM = 205.0       # v011 (Б5): лист формата ГОСТ — меньшая сторона ≥ A4
SCAN_MIN_COVER = 0.50          # картинки закрывают больше половины страницы — скан
MIXED_MIN_COVER = 0.30         # картинки 30–50 % страницы и вектор — смешанный
LOWRES_SCAN_DPI = 150          # скан ниже 150 dpi — мелкие детали не читаются
SMALL_RASTER_SIDE = 1000       # длинная сторона меньше — первая оценка: разрешение мерить в мм/px после масштаба (map/rules/10 §5.7; v012, Б21, УН-5 П-1)
# v014 (ПР6, И2/Б21-остаток): порог в px, а не в мм — при приёме масштаба ещё нет, а проверки мм/px после масштаба в коде нет: без порога
#   пропадёт ранний сигнал. Решение о качестве — в мм/px после масштаба (map/rules/10 §5.7: больше 30 мм — модель повторяющихся частей и
#   профили, §5.2); этот порог его не заменяет. Имя для реестра порогов ref/core/21 — SMALL_RASTER_SIDE, род «от растра», «первая оценка».
#   Новых порогов качества в px v014 не добавляет (LOWRES_RASTER_SIDE = 1300 черновика 0816 не перенесён — решение главного чата ПР6).
MESSENGER_SIDES = (1280,)      # v014 (ПР6, И2): длинная сторона 1280 px — так сжимает картинку мессенджер: признак файла (откуда пришёл), не
MESSENGER_TOL_PX = 2           #   порог качества; ± 2 px — округление при повороте и обрезке (черновик 0816: 36 из 266 растров каталога «12»)
PAPER_TOL = 0.03               # v012 (Б21): страница формата бумаги — A0…A6, B0…B6, Letter, Legal, Tabloid ± 3 % по обеим сторонам
PAPER_MM = {**{'A%d' % i: (841 / 2 ** (i / 2), 1189 / 2 ** (i / 2)) for i in range(7)}, **{'B%d' % i: (1000 / 2 ** (i / 2), 1414 / 2 ** (i / 2)) for i in range(7)},
            'Letter': (215.9, 279.4), 'Legal': (215.9, 355.6), 'Tabloid': (279.4, 431.8)}
EDGE_DEPTH = 0.01              # v012 (Б22): «линия уходит за край кадра» — тёмная на всю глубину 1 % длинной стороны кадра (УН-3: 12 px при 838–1393 px),
EDGE_RUN = 0.02                #   шириной 1 px … 2 % длинной стороны (УН-3: 30 px); край с EDGE_MIN и больше такими линиями — RASTER_CUT_EDGE
EDGE_MIN = 5
EDGE_DARK = 120                # тёмное — серый < 120 (УН-3, edgecut.py)
MOJIBAKE_MIN = 3               # v012 (Б6): слов cp1251, прочитанных как latin-1 («Ïåðåãîâîðíàÿ»), — не меньше 3 и не меньше 30 % слов с буквами
MOJIBAKE_SHARE = 0.30
LOWQ_JPEG = 60                 # оценка качества JPEG ниже — артефакты у тонких линий
PREVIEW_SIDE = 4000

ROUTES = {
    'raster': 'map/rules/10 целиком: подготовка §5; фото — §5.4, тёмный CAD — §5.2, слайд — §5.3; масштаб — map/rules/30 §2',
    'pdf-vector': 'map/rules/11 §0–§12: числа из вектора',
    'pdf-scan': 'map/rules/10 целиком: картинка внутри PDF — это скан (map/rules/11 §0)',
    'pdf-mixed': 'map/rules/11 §0, «смешанный»: план — по map/rules/10, зоны и разметка — векторами со страницы',
    'pdf-composite': 'map/rules/10 §5.0: страница из нескольких картинок — таблица состава, рендер с трансформациями',
    'pdf-empty': 'плана на странице нет — спросить клиента, какой лист',
    'office': 'map/rules/10 §5.1: чужой формат — извлечь картинку или лист, не снимать с экрана',
    'svg': 'вектор: числа — из путей SVG, порядок — как у векторного PDF, map/rules/11',
    'unsupported': 'формат не читается — попросить у клиента PDF, PNG или JPEG',
}                              # v014 (ПР3, Б25): маршруты cad-dwg, cad-dxf — cad_intake.ROUTES, подключаются в intake()

CAD_ERROR_ROUTE = ('чертёж CAD не прочитан — ошибка чтения (cad.read_error, rep.stop): попросить у клиента PDF плана со слоями или '
                   'файл чертежа заново')                     # v014 (ПРV-К2): маршрут класса cad-error, если cad_intake не загрузился

# предупреждение → что делать; ссылки — на действующие правила
ADVICE = {
    'EXT_MISMATCH': 'расширение не совпадает с содержимым — тип взят по содержимому',
    'EXIF_ROTATED': 'JPEG повёрнут флагом EXIF; рабочий растр развёрнут как на экране — координаты считать по нему',
    'ALPHA_FLATTENED': 'прозрачность наложена на белый; без этого прозрачный фон становится чёрным и весь лист — «стеной»',
    'PALETTE': 'палитровый PNG переведён в RGB; цвет помещений сверять по рабочему растру',
    'BIT16': '16 бит на канал переведены в 8 бит',
    'CMYK': 'CMYK переведён в RGB; цвета клиента брать по рабочему растру, не по числам CMYK',
    'JPEG_LOWQ': 'сильное сжатие JPEG: у тонких линий «звон» и блоки 8×8 — порог тёмного только после медианы 3×3, стены — медианой профиля (map/rules/10 §5.2)',
    'JPEG_CHROMA': 'цвет в JPEG прорежен (4:2:0): цветные тонкие линии размыты по цвету — стекло и заливки по цвету с допуском',
    'DPI_META': 'DPI в файле — условный, это не масштаб; масштаб — map/rules/30 §2',
    'SMALL_RASTER': 'длинная сторона меньше 1000 px — разрешение мерить в мм/px после масштаба (map/rules/10 §5.7): больше 30 мм — модель '
                    'повторяющихся частей и профили обязательны (§5.2); первая оценка до масштаба — длина этажа / длина плана на растре (без полей, '
                    'рамки, фона фото), не длина растра',
    'LARGE': 'растр больше 50 Мп: для просмотра — preview.png; экспорт ограничивать по длинной стороне (map/rules/82 §1)',
    'MULTI_FRAME': 'в файле несколько кадров — взят первый, остальные перечислены; какой нужен — спросить',
    'DARK_BACKGROUND': 'тёмный фон: CAD-растр — инвертировать (map/rules/10 §5.2); фото тёмного экрана — не инвертировать (map/rules/10 §5.4)',
    'PHOTO': 'снимок камеры или телефона: проверить перспективу до стен (map/rules/10 §5.4)',
    'PDF_ENCRYPTED': 'PDF под паролем — попросить у клиента файл без пароля',
    'PDF_MULTIPAGE': 'в PDF несколько листов с планом — выбран лист лучшего класса (вектор, затем смешанный, затем скан), среди них — по заголовку '
                     '(«План…», «Схема…», «Расстановка мебели»), без заголовка — с наибольшим содержимым; какой нужен — спросить (map/rules/11 §0, «Комплект листов»)',
    'PDF_ROTATED': 'страница повёрнута флагом /Rotate: векторы — в неповёрнутых координатах, рендер — повёрнут; переводить матрицей to_pixels',
    'PDF_OCR_LAYER': 'у скана есть невидимый текстовый слой (OCR): текст — не признак вектора; номера из него брать можно, геометрию — нет',
    'PDF_ANNOTATIONS': 'на странице аннотации: цветовые маски — по work_noannot.png, подложка артефакта 3 — без разметки клиента (map/rules/10 §5.0)',
    'PDF_OCG': 'в PDF слои (OCG): векторы извлекаются и из скрытых слоёв — сверять с рендером',
    'PDF_LOWRES_SCAN': 'скан на странице формата бумаги ниже 150 dpi — мелкие детали могут не читаться: разрешение — в мм/px после масштаба '
                       '(map/rules/10 §5.7); больше 60 мм и стены рисуют с этого листа — в карточку просьба прислать лучше',
    'PDF_SCAN_OVERLAY': 'поверх картинки скана — векторная разметка (пути, слова): в work.png она есть и её заливка закрывает скан; '
                        'стены и места — по native_*.png (без разметки), зоны и подписи — со страницы (map/rules/10 §5.1); доли — в overlay',
    'PDF_TILES': 'картинка скана — из плиток (драйвер печати режет растр): одна картинка — класс скана, native_*.png — общая рамка плиток в их dpi '
                 '(map/rules/10 §5.0)',
    'RASTER_CUT_EDGE': 'план обрезан краем кадра: линии уходят за край — край кадра не стена (map/rules/10 §2, п. 8), рисуется видимый фрагмент '
                       '(§5.4); попросить весь лист; число линий по краям — в edge_cut',
    'TEXT_CP1251_AS_LATIN1': 'текст листа — cp1251, прочитанный как latin-1 («Ïåðåãîâîðíàÿ»): имена и номера — после перекодировки latin-1 → cp1251 '
                             '(source_intake.fix_cp1251); примеры — в page_facts',
    'PDF_ROTATED_INSETS': 'картинки вставлены с поворотом или отражением — брать только рендер с трансформациями (map/rules/10 §5.0)',
    'PDF_SMASK': 'у картинки в PDF есть маска прозрачности: без неё фон картинки чёрный — native_*.png уже наложен на белый',
    'PDF_FLATTENED': '«распечатанный» векторный лист (PDF24, Ghostscript): отрезков нулевой длины больше 20 % или больше 95 % путей из одного '
                     'элемента при заливках только прямоугольниками — до таблицы классов отбросить отрезки нулевой длины, заливку собирать '
                     'объединением полос, пунктир — рядом коротких отрезков (map/rules/11 §1, «распечатанный» лист); доли — в page_facts',
    'NOT_A_PLAN_PAGE': 'на выбранном листе нет ни вектора, ни картинки плана',
    'PDF_FEW_LINES': 'мало линий (меньше 500 отрезков), но линии покрывают лист: эскиз или схема — проверить, что лист — план, масштаб — по размерам '
                     'или известному предмету (map/rules/30 §2)',
    # v014 (ПР6, И2)
    'RASTER_1280': 'длинная сторона 1280 ± 2 px — так сжимает картинку мессенджер: попросить у клиента оригинал файлом (PDF, DWG или '
                   'исходную картинку); до ответа — работать по этому, разрешение — в мм/px после масштаба (map/rules/10 §5.7)',
    'PDF_SCAN_LOWQ': 'картинка скана в PDF сжата JPEG сильнее качества 60: у тонких линий «звон» и блоки 8×8 — порог тёмного только '
                     'после медианы 3×3, стены — медианой профиля (map/rules/10 §5.2); есть лучше — попросить у клиента; оценка — native.jpeg_quality',
    # v014 (ПР6, И13/И14/П-239): только предупреждения и список; лист выбирает choose_page (PDF_MULTIPAGE), выбор по рангу — вопрос ОЧ-54
    'PDF_PLAN_CANDIDATES': 'в PDF несколько листов-планов по заголовкам (план мебели, план этажа или планировка, прочие планы — потолки, полы, '
                           'электрика): лист выбран как в PDF_MULTIPAGE (chosen_by); листы по этажам и рангам — intake.md, «Листы-планы», '
                           'pdf.plan_candidates; какие этажи и какой вариант рисовать — спросить (map/rules/11 §0, «Комплект листов»)',
    'PDF_MULTI_FLOOR': 'на выбранном листе планы нескольких этажей (по заголовкам видов): рисовать каждый этаж отдельно — какой, спросить; '
                       'область этажа — у его заголовка, рамка — pdf.page_facts[].titles[].bbox_pt',
    'PDF_WALLS_SHEET': 'в комплекте есть «План перегородок» (pdf.walls_pages): стены — с него, а не с мебельного, обмерного или '
                       'светильников (map/rules/11 §0, П-239); места и мебель — с выбранного листа; листы сверить по рамке и масштабу',
    'PDF_NATIVE_RENDER': 'картинку скана не извлечь без потерь (своя альфа без цветового пространства) — native_*.png — рендер её области в исходном разрешении',
    # v014 (ПРV-К2): чертёж CAD не прочитан — исключение ветки CAD (текст ошибки — в конце строки предупреждения и в cad.read_error)
    'DWG_READ_FAILED': 'ОСТАНОВКА: DWG не прочитан — ошибка при переводе или разборе (cad.read_error, rep.stop): класс cad-error, '
                       'рисовать не по чему; попросить у клиента PDF плана со слоями или DWG заново',
    'DXF_READ_FAILED': 'ОСТАНОВКА: DXF не прочитан — файл битый или не по формату (cad.read_error, rep.stop): класс cad-error, '
                       'рисовать не по чему; попросить у клиента DXF заново, DWG или PDF плана со слоями',
}

MAGIC = [(b'%PDF-', 'pdf'), (b'\x89PNG\r\n\x1a\n', 'png'), (b'\xff\xd8\xff', 'jpeg'), (b'GIF8', 'gif'),
         (b'II*\x00', 'tiff'), (b'MM\x00*', 'tiff'), (b'BM', 'bmp')]


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def sniff(path):
    """Тип по первым байтам. Возвращает pdf/png/jpeg/gif/tiff/bmp/webp/heic/dwg/dxf/svg/office/zip/unknown."""
    with open(path, 'rb') as f:
        head = f.read(4096)
    for sig, kind in MAGIC:
        if head.startswith(sig):
            return kind
    if head[:4] == b'RIFF' and head[8:12] == b'WEBP':
        return 'webp'
    if head[4:8] == b'ftyp' and head[8:12] in (b'heic', b'heix', b'mif1', b'msf1', b'avif'):
        return 'heic'
    if b'%PDF-' in head[:1024]:                 # мусор перед заголовком — PDF всё равно открывается
        return 'pdf'
    if head[:4] == b'AC10' and head[4:6].isdigit():                     # v014 (ПР3, Б25): DWG «AC1032» — версия AutoCAD
        return 'dwg'
    if re.match(rb'\s*(999\s*\r?\n[^\n]*\n\s*)?0\s*\r?\n\s*SECTION\s*\r?\n', head):   # v014 (ПР3, Б25): DXF текстом (двоичный — нет)
        return 'dxf'
    text = head.lstrip(b'\xef\xbb\xbf').lstrip()
    if text[:5] == b'<?xml' or text[:4] == b'<svg':
        return 'svg' if b'<svg' in head else 'unknown'
    if head[:4] == b'PK\x03\x04':
        try:
            names = zipfile.ZipFile(path).namelist()
            if any(n.startswith(('word/', 'xl/', 'ppt/')) for n in names):
                return 'office'
        except zipfile.BadZipFile:
            pass
        return 'zip'
    return 'unknown'


EXT_OF = {'pdf': {'.pdf'}, 'png': {'.png'}, 'jpeg': {'.jpg', '.jpeg', '.jpe', '.jfif'}, 'gif': {'.gif'},
          'tiff': {'.tif', '.tiff'}, 'bmp': {'.bmp'}, 'webp': {'.webp'}, 'heic': {'.heic', '.heif', '.avif'},
          'svg': {'.svg'}, 'office': {'.docx', '.xlsx', '.pptx'}, 'zip': {'.zip'},
          'dwg': {'.dwg'}, 'dxf': {'.dxf'}}                                # v014 (ПР3, Б25)


def jpeg_quality(im):
    """Оценка качества JPEG по таблице квантования яркости (шкала IJG)."""
    q = getattr(im, 'quantization', None)
    if not q or 0 not in q:
        return None
    std = [16, 11, 10, 16, 24, 40, 51, 61, 12, 12, 14, 19, 26, 58, 60, 55, 14, 13, 16, 24, 40, 57, 69, 56,
           14, 17, 22, 29, 51, 87, 80, 62, 18, 22, 37, 56, 68, 109, 103, 77, 24, 35, 55, 64, 81, 104, 113, 92,
           49, 64, 78, 87, 103, 121, 120, 101, 72, 92, 95, 98, 112, 100, 103, 99]
    t = list(q[0])
    # таблица в Pillow идёт зигзагом; среднее отношение от порядка не зависит
    scale = 100.0 * sum(t) / sum(std)
    quality = 5000.0 / scale if scale > 100 else (200.0 - scale) / 2.0
    return int(round(max(1, min(100, quality))))


def to_rgb8(im, notes):
    """Любой режим Pillow → 8 бит RGB без альфы, прозрачность — на белом."""
    mode = im.mode
    if mode in ('I;16', 'I;16B', 'I;16L', 'I', 'F'):
        a = np.asarray(im).astype(np.float64)
        mx = a.max() if a.size else 0
        if mx > 255:
            a = a / (65535.0 if mx > 4095 else mx) * 255.0
            notes.add('BIT16')
        im = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8), 'L')
        mode = 'L'
    if mode == 'P':
        notes.add('PALETTE')
        im = im.convert('RGBA') if 'transparency' in im.info else im.convert('RGB')
        mode = im.mode
    if mode in ('RGB', 'L') and 'transparency' in im.info:
        im = im.convert('RGBA')
        mode = 'RGBA'
    if mode in ('LA', 'PA', 'La'):
        im = im.convert('RGBA')
        mode = 'RGBA'
    if mode in ('RGBA', 'RGBa'):
        alpha = np.asarray(im.getchannel('A'))
        share = float((alpha < 255).mean())
        if share > 0:
            notes.add('ALPHA_FLATTENED')
        white = Image.new('RGBA', im.size, (255, 255, 255, 255))
        return Image.alpha_composite(white, im.convert('RGBA')).convert('RGB'), share
    if mode == 'CMYK':
        notes.add('CMYK')
        return im.convert('RGB'), 0.0
    if mode == '1':
        return im.convert('L').convert('RGB'), 0.0
    if mode != 'RGB':
        return im.convert('RGB'), 0.0
    return im, 0.0


def light_share(rgb):
    a = np.asarray(rgb.convert('L'))
    return float((a > 200).mean())


def save_work(rgb, out, name='work.png'):
    rgb.save(os.path.join(out, name), optimize=False)
    w, h = rgb.size
    if max(w, h) > PREVIEW_SIDE:
        k = PREVIEW_SIDE / max(w, h)
        rgb.resize((max(1, int(w * k)), max(1, int(h * k))), Image.LANCZOS).save(os.path.join(out, 'preview.png'))


def intake_raster(path, kind, out, rep, notes):
    try:
        im = Image.open(path)
        im.load()
    except Image.DecompressionBombError as e:
        rep['error'] = 'растр больше %d пикселей — отказ распаковки: %s' % (Image.MAX_IMAGE_PIXELS, e)
        return
    except Exception as e:                                       # noqa: BLE001 — формат не читается
        rep['error'] = 'не открывается: %s' % e
        rep['route'] = ROUTES['unsupported']
        return
    r = rep['raster'] = {'mode': im.mode, 'size': list(im.size), 'format': im.format}
    frames = getattr(im, 'n_frames', 1)
    if frames > 1:
        notes.add('MULTI_FRAME')
        r['frames'] = frames
    dpi = im.info.get('dpi')
    if dpi:
        r['dpi_meta'] = [round(float(x), 1) for x in dpi]
        notes.add('DPI_META')
    exif = im.getexif()
    orient = exif.get(274, 1) if exif else 1
    r['exif_orientation'] = orient
    if exif and (exif.get(271) or exif.get(272)):
        r['camera'] = ' '.join(str(exif.get(t, '')).strip() for t in (271, 272)).strip()
        notes.add('PHOTO')
    if kind == 'jpeg':
        r['jpeg_quality'] = jpeg_quality(im)
        try:
            from PIL.JpegImagePlugin import get_sampling
            r['jpeg_sampling'] = {0: '4:4:4', 1: '4:2:2', 2: '4:2:0'}.get(get_sampling(im), 'нет данных')
        except Exception:                                        # noqa: BLE001
            r['jpeg_sampling'] = 'нет данных'
        if r['jpeg_quality'] is not None and r['jpeg_quality'] < LOWQ_JPEG:
            notes.add('JPEG_LOWQ')
        if r['jpeg_sampling'] in ('4:2:0', '4:2:2'):
            notes.add('JPEG_CHROMA')
        r['progressive'] = bool(im.info.get('progressive') or im.info.get('progression'))
    if im.info.get('icc_profile'):
        r['icc_profile'] = True
    if orient not in (1, None):
        notes.add('EXIF_ROTATED')
    im = ImageOps.exif_transpose(im)                             # как на экране
    rgb, alpha_share = to_rgb8(im, notes)
    r['alpha_transparent_share'] = round(alpha_share, 4)
    r['work_size'] = list(rgb.size)
    ls = light_share(rgb)
    r['light_share'] = round(ls, 3)
    if ls < 0.30:
        notes.add('DARK_BACKGROUND')
    if max(rgb.size) < SMALL_RASTER_SIDE:
        notes.add('SMALL_RASTER')
    if any(abs(max(rgb.size) - m) <= MESSENGER_TOL_PX for m in MESSENGER_SIDES):   # v014 (ПР6, И2): сжато мессенджером — признак файла
        notes.add('RASTER_1280')
    if rgb.size[0] * rgb.size[1] > 50_000_000:
        notes.add('LARGE')
    r['edge_cut'] = note_edge_cut(rgb, notes)                    # v012 (Б22): план обрезан краем кадра
    save_work(rgb, out)
    rep['class'] = 'raster'
    rep['route'] = ROUTES['raster']


def paper_format(w_pt, h_pt, tol=PAPER_TOL):
    """v012 (Б21): страница формата бумаги — имя формата (A4, B3, Letter…) или None: обе стороны ± tol, в любой ориентации"""
    a, b = sorted((w_pt * 25.4 / 72, h_pt * 25.4 / 72))
    for name, (s0, s1) in PAPER_MM.items():
        if abs(a - s0) <= tol * s0 and abs(b - s1) <= tol * s1:
            return name
    return None


def _runs(v):
    """длины серий True в одномерном массиве"""
    d = np.diff(np.concatenate([[0], v.astype(np.int8), [0]]))
    return np.flatnonzero(d == -1) - np.flatnonzero(d == 1)


def edge_cut(rgb):
    """v012 (Б22, УН-3): линии плана, которые уходят за край кадра, — по каждому краю: тёмная (серый < EDGE_DARK) серия вдоль края шириной
    1 px … EDGE_RUN длинной стороны, тёмная на всю глубину EDGE_DEPTH длинной стороны от края. Пороги — в долях кадра (УН-3: 12 и 30 px при
    838–1393 px). -> {'лево': n, 'право': n, 'верх': n, 'низ': n, 'depth_px', 'run_px'}"""
    g = np.asarray(rgb.convert('L')) < EDGE_DARK; L = max(g.shape)
    depth = max(3, int(round(EDGE_DEPTH * L))); run = max(2, int(round(EDGE_RUN * L)))
    out = {}
    for name, strip in (('лево', g[:, :depth]), ('право', g[:, -depth:]), ('верх', g[:depth, :].T), ('низ', g[-depth:, :].T)):
        r = _runs(strip.all(axis=1)); out[name] = int(((r >= 1) & (r <= run)).sum())
    out['depth_px'], out['run_px'] = depth, run
    return out


def note_edge_cut(rgb, notes):
    e = edge_cut(rgb)
    if max(e[k] for k in ('лево', 'право', 'верх', 'низ')) >= EDGE_MIN:
        notes.add('RASTER_CUT_EDGE')
    return e


MOJI = re.compile(r'[\u00c0-\u00ff]')


def fix_cp1251(s):
    """v012 (Б6): текст cp1251, прочитанный как latin-1 («Ïåðåãîâîðíàÿ»), -> «Переговорная»; другое — как есть"""
    try:
        return s.encode('latin-1').decode('cp1251')
    except (UnicodeEncodeError, UnicodeDecodeError):
        return s


def is_mojibake(w):
    """слово cp1251, прочитанное как latin-1: из букв — не меньше 60 % в À…ÿ, и перекодировка даёт кириллицу"""
    letters = [c for c in w if c.isalpha()]
    if len(letters) < 2 or sum(bool(MOJI.match(c)) for c in letters) < 0.6 * len(letters):
        return False
    f = fix_cp1251(w)
    return f != w and sum('\u0400' <= c <= '\u04ff' for c in f) >= 0.6 * len(letters)


def union_cover(rects, page_rect, grid=200):
    """Доля страницы под картинками: сетка 200×200, перекрытия не считаются дважды."""
    if not rects:
        return 0.0
    x0, y0, x1, y1 = page_rect
    w, h = max(x1 - x0, 1e-6), max(y1 - y0, 1e-6)
    m = np.zeros((grid, grid), bool)
    for (a, b, c, d) in rects:
        i0 = int(max(0, (a - x0) / w * grid)); i1 = int(min(grid, np.ceil((c - x0) / w * grid)))
        j0 = int(max(0, (b - y0) / h * grid)); j1 = int(min(grid, np.ceil((d - y0) / h * grid)))
        if i1 > i0 and j1 > j0:
            m[j0:j1, i0:i1] = True
    return float(m.mean())


def frame_stamp(a0, a1, W, H):
    """v011 (Б5, доработка 2): рамка у края листа с основной надписью в правом нижнем углу, как в ГОСТ 21.101 (бывает и на листах не по ГОСТ —
    штамп западного образца в том же углу: s045, s270, s177), по отрезкам листа (координаты листа, как его видят, pt). Рамка — замкнутый прямоугольник:
    у каждого края — прямая из одного отрезка или цепочки (рамка, разбитая в узлах штампа) длиной ≥ FRAME_SIDE_SHARE стороны листа в FRAME_MAX_MM
    от края; из таких прямых — ближайшая к краю. Штамп — в правом нижнем углу рамки (STAMP_MM): верхняя линия ≥ STAMP_TOP_MM и ниже неё ≥ 3 вертикали
    сетки. Нет любой из четырёх сторон или штампа — None (контур стен у края — не рамка: эскиз S6) -> ((лево, верх, право, низ), (лево штампа, верх штампа))"""
    mm = 72 / 25.4; d = a1 - a0; tol = 0.5 * mm
    def lines(mask, c):                                          # c = 1 — горизонтали (постоянный y), 0 — вертикали
        return ((a0[mask, c] + a1[mask, c]) / 2, np.minimum(a0[mask, 1 - c], a1[mask, 1 - c]), np.maximum(a0[mask, 1 - c], a1[mask, 1 - c]))
    def cover(L, at, lo=-1e9, hi=1e9):                           # длина объединения отрезков прямой at (± tol) в пределах [lo, hi]
        c, s0, s1 = L; m = np.abs(c - at) < tol; tot, cur = 0.0, None
        for a, b in sorted(zip(np.clip(s0[m], lo, hi), np.clip(s1[m], lo, hi))):
            if cur is None or a > cur[1]:
                tot += (cur[1] - cur[0]) if cur else 0.0; cur = [a, b]
            else: cur[1] = max(cur[1], b)
        return tot + ((cur[1] - cur[0]) if cur else 0.0)
    def side(L, lo, hi, length, from_hi):
        c = L[0]; grp = sorted(set(np.round(c[(c >= lo) & (c <= hi)] / tol).astype(int).tolist()), reverse=from_hi)
        return next((g * tol for g in grp if cover(L, g * tol) >= FRAME_SIDE_SHARE * length), None)
    hor, ver = lines(np.abs(d[:, 1]) < tol, 1), lines(np.abs(d[:, 0]) < tol, 0)
    F = FRAME_MAX_MM * mm
    ft, fb = side(hor, 0, F, W, False), side(hor, H - F, H, W, True)
    fl, fr_ = side(ver, 0, F, H, False), side(ver, W - F, W, H, True)
    if None in (ft, fb, fl, fr_):
        return None
    x_lo = fr_ - STAMP_MM[0] * mm; c, s0, s1 = hor
    tops = sorted(set(np.round(c[(c > fb - STAMP_MM[1] * mm) & (c < fb - 10 * mm)] / tol).astype(int).tolist()))
    st = next((g * tol for g in tops if cover(hor, g * tol, x_lo, fr_ + tol) >= STAMP_TOP_MM * mm), None)
    if st is None:
        return None
    vc, v0, v1 = ver; inside = (vc > x_lo) & (vc < fr_ - tol) & (v0 >= st - tol) & (v1 <= fb + tol) & (v1 - v0 >= 5 * mm)
    if len(set(np.round(vc[inside] / tol).astype(int).tolist())) < 3:
        return None
    m = (np.abs(c - st) < tol) & (s1 > x_lo)
    return (fl, ft, fr_, fb), (float(s0[m].min()) if m.any() else x_lo, st)


# ── v014 (ПР6, И13/И14/П-239): заголовки видов на листе — ранг листа-плана и этажи; из черновика 0816 (стр. 316–411) — только для списка
# кандидатов и предупреждений (PDF_PLAN_CANDIDATES, PDF_MULTI_FLOOR, PDF_WALLS_SHEET); лист выбирает choose_page v011 (выбор по рангу — ОЧ-54)
# Строка-заголовок: не мельче медианы шрифта страницы, до 14 слов. Вид — по началу части строки (части — через «/», «|», «:», «—»;
# нумерация «1.» снимается) или по всей строке до 6 слов (английские «Office Layout», «Ground Floor Plan»).
TITLE_MAX_WORDS = 14
T_CONTENTS = re.compile(r'ведомост\w*\s+(рабочих\s+|основных\s+)?(чертеж|листов|комплект)|^\s*(содержание|оглавление)\b|общие\s+данные'
                        r'|титульный\s+лист|\b(drawing|sheet)\s+(list|index)\b|^\s*contents\b')
T_NEG = re.compile(r'\b(развертк|разрез|узел\b|узл(ы|ов)\b|фасад|спецификац|ведомост|визуализ|схем\w*\s+видов|детал|3d\b|section\b'
                   r'|elevation\b|detail|render)')
T_FURN = re.compile(r'\b(расстановк\w*\s+мебел|мебел\w*\s+и\s+оборуд|план\w*(\s+\S+){0,3}\s+мебел|рассадк|расстановк\w*\s+(рабочих\s+)?мест'
                    r'|furniture\b|seating\b|desk(ing)?\s+(plan|layout)\b|ff&e\b)')
T_OTHER = re.compile(r'\b(план\w*(\s+\S+){0,4}\s+(потолк|пол(ов|а|ы)?\b|напольн|покрыти|освещ|светил|розет|электр|слаботоч|вентил|отоплен'
                     r'|водоснаб|канализ|кондиц|пожарн|демонтаж|окраш|отделк|кабел|сет(и|ей)\b)'
                     r'|(reflected\s+)?ceiling\b|lighting\b|power\b|electrical\b|hvac\b|plumbing\b|demolition\b|finish(es)?\s+plan|flooring\b)')
T_PLAN = re.compile(r'\b(план(а|ы|е|ом|у)?\b|планировк|планировочн|планированн|обмерн|floor\s*plan\b|layout\b|plan\b|general\s+arrangement\b)')
FLOOR_RES = [re.compile(r'(?<![\d.,])(\d{1,3})\s*(?:-?\s*(?:й|ой|ий|ый|го|м))?\s*этаж'),
             re.compile(r'этаж\w*\s*(?:№\s*)?(\d{1,3})(?![\d.,])'),
             re.compile(r'\b(?:floor|level|lvl|уровень)\s*(\d{1,3})\b'),
             re.compile(r'\b(\d{1,3})(?:st|nd|rd|th)\s+floor\b')]
TIER_NAME = {1: 'план мебели', 2: 'план этажа', 3: 'другой план', 4: 'без заголовка', 5: 'не план', 8: 'содержание альбома'}


def norm_text(t):
    return re.sub(r'\s+', ' ', str(t).lower().replace('ё', 'е')).strip()


def line_kind(s):
    """вид строки-заголовка: 1 — план мебели, 2 — план этажа или планировка, 3 — прочий план, 'neg' — развёртка, разрез,
    спецификация…, 'contents' — содержание альбома, None — не заголовок. s — norm_text()."""
    if T_CONTENTS.search(s):
        return 'contents'
    if re.match(r'(см\.|смотр|see\b)', s):                     # ссылка на другой лист, а не заголовок
        return None
    segs = [re.sub(r'^[\s\d.)(№-]+', '', x) for x in re.split(r'\s*[/|:—–]\s*|\s+-\s+', s)]
    segs = [x for x in segs if x]
    short = len(s.split()) <= 6
    if any(T_NEG.match(x) for x in segs):
        return 'neg'
    for kind, rx in ((1, T_FURN), (3, T_OTHER), (2, T_PLAN)):
        if kind == 1 and re.search(r'\bбез\s+мебел|\bwithout\s+furniture', s):
            continue
        if any(rx.match(x) for x in segs) or (short and rx.search(s)):
            return kind
    return 'neg' if T_NEG.search(s) else None


def floors_in(s):
    out = set()
    for rx in FLOOR_RES:
        out |= {int(v) for v in rx.findall(s)}
    return sorted(f for f in out if f <= 150)


def page_titles(page, recode=False):
    """заголовки видов страницы: ранг листа (TIER_NAME), этажи по заголовкам, строки с рамками; recode — текст cp1251, прочитанный как
    latin-1 (v012, Б6), — после перекодировки (v014, ПР6, И13)"""
    import pymupdf
    try:
        d = page.get_text('dict', flags=pymupdf.TEXTFLAGS_TEXT)
    except Exception:                                            # noqa: BLE001 — страница без текста или битая
        return {'tier': 4, 'floors': [], 'titles': []}
    lines = []
    for b in d.get('blocks', []):
        for ln in b.get('lines', []):
            spans = ln.get('spans', [])
            t = ''.join(sp.get('text', '') for sp in spans).strip()
            if recode: t = fix_cp1251(t)                         # v014 (ПР6, И13): как page_title v012 (Б6)
            if t and spans:
                lines.append((t, max(sp.get('size', 0) for sp in spans), ln.get('bbox')))
    if not lines:
        return {'tier': 4, 'floors': [], 'titles': []}
    med = float(np.median([sz for _, sz, _ in lines]))
    titles = []
    for t, sz, bb in lines:
        if sz + 1e-6 < med or len(t.split()) > TITLE_MAX_WORDS or len(t) > 160:
            continue
        s = norm_text(t)
        k = line_kind(s)
        label = k is None and len(s.split()) <= 3                 # «2 этаж», «Level 3» — подпись этажа
        fl = floors_in(s) if (k in (1, 2, 3) or label) else []
        if k is None and not fl:
            continue
        titles.append({'text': t[:120], 'kind': k, 'floors': fl, 'size': round(sz, 1), 'bbox_pt': [round(v, 1) for v in bb]})
        if k == 2 and re.search(r'перегоро[дж]|partition', s):     # «План (вновь возводимых) перегородок» — лист стен, П-239
            titles[-1]['walls'] = True
    pos = [x for x in titles if x['kind'] in (1, 2, 3)]
    if any(x['kind'] == 'contents' for x in titles):
        tier = 8
    elif pos:
        tier = min(x['kind'] for x in pos)
    elif any(x['kind'] == 'neg' for x in titles):
        tier = 5
    else:
        tier = 4
    floors = sorted({f for x in titles if x['kind'] in (1, 2, 3, None) for f in x['floors']})
    titles.sort(key=lambda x: (x['kind'] not in (1, 2, 3), -x['size']))
    return {'tier': tier, 'floors': floors, 'walls_title': any(x.get('walls') for x in titles), 'titles': titles[:12]}




def pdf_page_facts(doc, page):
    import pymupdf
    rect = page.rect                                             # с учётом /Rotate
    unrot = page.cropbox
    drawings = page.get_drawings()
    segments = sum(len(d.get('items', [])) for d in drawings)
    zero, one, fills, fill_re = 0, 0, 0, 0                       # «распечатанный» лист (map/rules/11 §1): нулевые отрезки, пути из одного элемента
    for d in drawings:
        it = d.get('items', [])
        one += len(it) == 1
        if d.get('fill') is not None:
            fills += 1; fill_re += all(x[0] == 're' for x in it)
        for x in it:
            if x[0] == 'l' and abs(x[1].x - x[2].x) < 0.01 and abs(x[1].y - x[2].y) < 0.01: zero += 1
            elif x[0] == 'c' and max(abs(q.x - x[1].x) + abs(q.y - x[1].y) for q in x[2:5]) < 0.01: zero += 1
            elif x[0] == 're' and (x[1].width < 0.01 and x[1].height < 0.01): zero += 1
    P0, P1 = [], []                                              # v011 (Б5): отрезки без рамки листа -> длина и клетки сетки
    W_, H_ = max(rect.width, 1e-6), max(rect.height, 1e-6)
    for d in drawings:
        for x in d.get('items', []):
            if x[0] == 'l': P0.append((x[1].x, x[1].y)); P1.append((x[2].x, x[2].y))
            elif x[0] == 'c': P0.append((x[1].x, x[1].y)); P1.append((x[4].x, x[4].y))
            elif x[0] == 're':
                r = x[1]; c4 = [(r.x0, r.y0), (r.x1, r.y0), (r.x1, r.y1), (r.x0, r.y1)]; P0 += c4; P1 += c4[1:] + c4[:1]
            elif x[0] == 'qu':
                q = x[1]; c4 = [(q.ul.x, q.ul.y), (q.ur.x, q.ur.y), (q.lr.x, q.lr.y), (q.ll.x, q.ll.y)]; P0 += c4; P1 += c4[1:] + c4[:1]
    length_per, cells, gost = 0.0, 0.0, False
    if P0:
        a0, a1 = np.asarray(P0, float), np.asarray(P1, float)
        if page.rotation:                                         # get_drawings — в неповёрнутых координатах: сетка — по неповёрнутому листу
            W_, H_ = max(unrot.width, 1e-6), max(unrot.height, 1e-6)
        x0_, y0_ = (unrot.x0, unrot.y0) if page.rotation else (rect.x0, rect.y0)
        mm = 72 / 25.4                                            # доработка 2 (Б5): рамка ГОСТ со штампом — в координатах листа, как его видят (/Rotate)
        M = page.rotation_matrix if page.rotation else pymupdf.Matrix(1, 0, 0, 1, 0, 0)
        to_v = lambda a: np.stack([M.a * a[:, 0] + M.c * a[:, 1] + M.e, M.b * a[:, 0] + M.d * a[:, 1] + M.f], 1)
        zones = frame_stamp(to_v(a0), to_v(a1), rect.width, rect.height) if min(rect.width, rect.height) >= GOST_MIN_SIDE_MM * mm else None
        gost = zones is not None
        fr = (np.abs(a1[:, 0] - a0[:, 0]) > 0.9 * W_) | (np.abs(a1[:, 1] - a0[:, 1]) > 0.9 * H_)   # рамка одним отрезком на сторону
        if gost:                                                  # доработка 2: рамка ГОСТ найдена — её снимает кольцо; длинная стена плана у рамки
            fr[:] = False                                         # (S7: 0,90 ширины листа) — в счёт
        a0, a1 = a0[~fr], a1[~fr]
        if len(a0):
            ln = np.hypot(*(a1 - a0).T)
            k = np.clip(np.ceil(ln / (min(W_, H_) / GRID) * 2).astype(int), 2, 4 * GRID)   # точек на отрезок: шаг — полклетки
            idx = np.repeat(np.arange(len(k)), k); t = (np.arange(int(k.sum())) - np.repeat(np.cumsum(k) - k, k)) / np.repeat(k - 1, k)
            xy = a0[idx] + (a1[idx] - a0[idx]) * t[:, None]
            # доработка Б5: точки в кольце у края листа и в зоне основной надписи ГОСТ — не в счёт ни длине, ни клеткам (рамка, разбитая
            # в узлах штампа, штамп, доп. графы; лист «Примечания» — не план). Зона штампа — в координатах листа, как его видят (/Rotate)
            keep = np.ones(len(xy), bool)
            if gost:                                              # без рамки ГОСТ со штампом (эскиз S6, s234) — как раньше
                (fl, ft, fr_, fb), (sl, st) = zones; v = to_v(xy); t = 1.0 * mm
                ring = (v[:, 0] < fl + t) | (v[:, 0] > fr_ - t) | (v[:, 1] < ft + t) | (v[:, 1] > fb - t)   # между краем листа и рамкой, сама рамка
                stamp = (v[:, 0] > sl - t) & (v[:, 1] > st - t)
                keep = ~(ring | stamp)
            kept = np.bincount(idx, weights=keep.astype(float), minlength=len(k)) / k
            length_per = float((ln * kept).sum() / (2 * (W_ + H_)))
            gi = np.clip(((xy[keep, 1] - y0_) / H_ * GRID).astype(int), 0, GRID - 1); gj = np.clip(((xy[keep, 0] - x0_) / W_ * GRID).astype(int), 0, GRID - 1)
            cells = float(len(np.unique(gi * GRID + gj)) / GRID ** 2)
    imgs = page.get_image_info(xrefs=True)
    rects, img_rows, rotated = [], [], 0
    rot_m = page.rotation_matrix if page.rotation else pymupdf.Matrix(1, 0, 0, 1, 0, 0)   # v012 (Б17): get_image_info — в неповёрнутых координатах
    for im in imgs:
        bb = (pymupdf.Rect(im['bbox']) * rot_m) & rect
        if bb.is_empty:
            continue
        rects.append((bb.x0, bb.y0, bb.x1, bb.y1))
        a, b, c, d, e, f = im.get('transform', (1, 0, 0, 1, 0, 0))
        rot = abs(b) > 1e-6 or abs(c) > 1e-6 or a < 0 or d < 0
        rotated += bool(rot)
        wpt = max(pymupdf.Rect(im['bbox']).width, 1e-6)
        hpt = max(pymupdf.Rect(im['bbox']).height, 1e-6)
        side_px = max(im.get('width', 0), im.get('height', 0))
        side_pt = max(wpt, hpt)
        img_rows.append({'xref': im.get('xref'), 'px': [im.get('width'), im.get('height')],
                         'bbox_pt': [round(v, 1) for v in im['bbox']],
                         'dpi': round(side_px / (side_pt / 72.0), 1),
                         'rotated_or_mirrored': rot, 'cover': round(bb.width * bb.height / (rect.width * rect.height), 4)})
    cover = union_cover(rects, (rect.x0, rect.y0, rect.x1, rect.y1))
    words = page.get_text('words')
    alpha_words = [w[4] for w in words if any(c.isalpha() for c in w[4])]
    moji = [w for w in alpha_words if is_mojibake(w)]               # v012 (Б6): cp1251, прочитанный как latin-1
    mojibake = len(moji) >= MOJIBAKE_MIN and len(moji) >= MOJIBAKE_SHARE * len(alpha_words)
    invisible = 0
    try:
        for span in page.get_texttrace():
            if span.get('type') == 3:
                invisible += len(span.get('chars', ()))
    except Exception:                                            # noqa: BLE001 — старый pymupdf
        pass
    annots = [a.type[1] for a in page.annots()] if page.annots() else []
    title, title_kind = page_title(page, drawing=segments >= VECTOR_MIN_SEGMENTS, recode=mojibake)
    return {'number': page.number + 1, 'size_pt': [round(rect.width, 1), round(rect.height, 1)],
            'length_per_perimeter': round(length_per, 2), 'line_cells': round(cells, 3), 'frame_stamp': bool(gost), 'title': title, 'title_kind': title_kind,
            'cropbox_pt': [round(unrot.width, 1), round(unrot.height, 1)], 'rotation': page.rotation,
            'paths': len(drawings), 'segments': segments, 'images': img_rows, 'image_cover': round(cover, 3),
            'rotated_images': rotated, 'words': len(words), 'invisible_chars': invisible, 'annotations': annots,
            'zero_share': round(zero / segments, 3) if segments else 0.0, 'one_item_share': round(one / len(drawings), 3) if drawings else 0.0,
            'fills_only_re': bool(fills) and fill_re == fills,
            **page_titles(page, recode=mojibake),                # v014 (ПР6, И13): tier, floors, walls_title, titles
            **({'cp1251_as_latin1': {'words': len(moji), 'of': len(alpha_words), 'examples': [[w, fix_cp1251(w)] for w in moji[:5]]}} if mojibake else {})}


PLAN_TITLE = re.compile(r'^\s*(план\b|планы\b|схема\b.*?(?:расстановк|размещени|планировк|рассадк|мебел|рабочих\s+мест|зонировани)|расстановк|планировк|'
                        r'layout\b|floor\s*plan|seating)', re.I)   # доработка 2 (Б4): «Схема…» — план только со словом плана офиса, «Схема электрическая…» — нейтрально
SHEET_TITLE = re.compile(r'^\s*(развертк|развёртк|разрез|фасад|узл|узел\b|общие\s+данные|титул|содержание|схема\s+видов|'
                         r'схема\s+располож\w*\s+(?:вид|разрез|узл))', re.I)      # тип листа альбома — «другой лист» всегда
TABLE_TITLE = re.compile(r'^\s*(экспликац|ведомост|спецификац)', re.I)   # доработка 3 (Б4): таблица — «другой лист» только без чертежа: на листе
                                                                        # с чертежом таблица «Экспликация» — часть листа плана (синтетика R1)
OTHER_TITLE = re.compile(SHEET_TITLE.pattern + '|' + TABLE_TITLE.pattern, re.I)   # для совместимости: все слова другого листа
TITLE_PLAN_SHARE = 0.6          # v011 (Б4): на листе с чертежом (≥ VECTOR_MIN_SEGMENTS отрезков) строка плана не мельче 0,6 самой крупной строки словаря — заголовок
                                # плана: таблица «Экспликация», «Спецификация» на листе плана бывает крупнее заголовка плана (s400, s077; синтетика T3, T4)
TITLE_TIER = 0.9                # v011 (Б4, доработка): на листе без чертежа — 0,9: строка таблицы «Планировка — …» 10 pt при «Экспликация помещений» 14 pt —
                                # не заголовок (синтетика S2)
TITLE_MIN_CONTENT = 0.5         # v011 (Б4, доработка): лист с заголовком плана выбирается, только если содержимого у него не меньше половины лучшего листа
def page_title(page, drawing=True, recode=False):
    """v011 (Б4): заголовок страницы — строки текста, которые начинаются словом листа плана («План…», «Схема…», «Расстановка мебели») или
    другого листа альбома («Развертки…», «Экспликация…», «Ведомость…», «Схема видов»). Лист плана — если строка плана не мельче TITLE_PLAN_SHARE
    самой крупной из них на листе с чертежом (drawing: ≥ VECTOR_MIN_SEGMENTS отрезков; таблица «Экспликация» или «Спецификация» рядом с планом
    бывает крупнее заголовка плана) и не мельче TITLE_TIER — на листе без чертежа (в экспликации строка «Планировка — открытая» — текст таблицы);
    иначе — самая крупная строка (на развертках подпись «План … (схема)» мелкая). «Схема…» — план только со словом плана офиса. Таблица («Экспликация…»,
    «Ведомость…», «Спецификация…») — «другой лист» только без чертежа; на листе с чертежом она не заголовок (доработка 3: план с нераспознанным
    заголовком «2 этаж. Расстановка мебели» и таблицей «Экспликация» не уходит в конец — синтетика R1). Крупность — среди строк словаря,
    не всей страницы: самая крупная строка страницы бывает подписью помещения или логотипом (s045 — 42 pt при «FLOOR PLAN» 12 pt; s077, s192 —
    логотип 13 pt при заголовке 9 pt) -> (текст, 'plan' | 'other' | None)"""
    C = []
    try:
        for b in page.get_text('dict').get('blocks', []):
            for ln in b.get('lines', []):
                sp = ln.get('spans', []); txt = ' '.join(x.get('text', '') for x in sp).strip()
                if recode: txt = fix_cp1251(txt)                     # v012 (Б6): заголовок — после перекодировки
                if not txt or not sp: continue
                kind = ('other' if SHEET_TITLE.match(txt) or (not drawing and TABLE_TITLE.match(txt))
                        else 'plan' if PLAN_TITLE.match(txt) and not TABLE_TITLE.match(txt) else None)
                if kind is not None: C.append((max(float(x.get('size', 0)) for x in sp), txt[:120], kind))
    except Exception:                                            # noqa: BLE001 — нет текстового слоя
        return None, None
    if not C: return None, None
    top = max(c[0] for c in C); share = TITLE_PLAN_SHARE if drawing else TITLE_TIER
    best = max([c for c in C if c[2] == 'plan' and c[0] >= share * top] or C, key=lambda c: c[0])
    return best[1], best[2]


def has_vector(p):
    """v011 (Б5): на листе есть векторный план — долей листа: линии без рамки не короче VECTOR_MIN_LENGTH периметров и проходят через
    VECTOR_MIN_CELLS клеток сетки, и заголовок страницы — не другого листа альбома (таблица экспликации или ведомости тоже покрывает лист);
    ≥ VECTOR_MIN_SEGMENTS отрезков — вектор, как до v011 (только долей листа — ложное «нет плана» у смешанного листа s415: клеток 7 %)"""
    return p['segments'] >= VECTOR_MIN_SEGMENTS or (p.get('length_per_perimeter', 0) >= VECTOR_MIN_LENGTH and p.get('line_cells', 0) >= VECTOR_MIN_CELLS
                                                    and p.get('title_kind') != 'other')


TILE_DPI_TOL = 0.02            # v012 (Б19): плитки одной картинки — одно dpi ± 2 %
TILE_AREA_TOL = 0.01           #   объединение — прямоугольник: сумма площадей = площадь общей рамки ± 1 %


def tiles_of_one(imgs):
    """v012 (Б19, УН-3): картинки страницы — плитки одной картинки (драйвер печати режет растр): ≥ 2, без поворота и отражения,
    одно dpi (± 2 %), вместе — прямоугольник (сумма площадей = площадь общей рамки ± 1 %, значит, не перекрываются)"""
    if len(imgs) < 2 or any(i['rotated_or_mirrored'] for i in imgs): return False
    d = [i['dpi'] for i in imgs]
    if max(d) > (1 + TILE_DPI_TOL) * min(d): return False
    bb = [i['bbox_pt'] for i in imgs]
    x0, y0 = min(b[0] for b in bb), min(b[1] for b in bb); x1, y1 = max(b[2] for b in bb), max(b[3] for b in bb)
    area = sum((b[2] - b[0]) * (b[3] - b[1]) for b in bb); full = (x1 - x0) * (y1 - y0)
    return full > 0 and abs(area - full) <= TILE_AREA_TOL * full


def classify_page(p):
    visible = [i for i in p['images'] if i['cover'] >= 0.01]
    if tiles_of_one(p['images']):                                # v012 (Б19): плитки — одна картинка, не «составной»
        p['tiles'] = len(p['images'])
        visible = visible[:1]
    vec = has_vector(p)                                          # v011 (Б5): долей листа, а не числом отрезков
    if not vec and p['image_cover'] < 0.05:
        return 'pdf-empty'
    if (p['rotated_images'] >= 1 and len(p['images']) >= 2) or (len(visible) >= 3 and not p.get('tiles')):
        return 'pdf-composite'                                   # клиент В 15 э.: вставки с поворотом
    if p['image_cover'] >= SCAN_MIN_COVER and not vec:
        return 'pdf-scan'
    if p['image_cover'] >= MIXED_MIN_COVER and vec:
        return 'pdf-mixed'
    if vec:
        return 'pdf-vector'
    return 'pdf-scan' if p['image_cover'] >= MIXED_MIN_COVER else 'pdf-empty'


CLASS_RANK = {'pdf-vector': 3, 'pdf-mixed': 2, 'pdf-composite': 1, 'pdf-scan': 1, 'pdf-empty': 0}


def plan_score(p):
    """Лист плана: сначала вектор (числа из вектора, map/rules/11 §0), затем по объёму содержимого."""
    return (CLASS_RANK.get(p.get('class'), 0), p['segments'] + 20000 * p['image_cover'])


def choose_page(pages, plan_pages):
    """v011 (Б4, доработка 2): лист альбома. Сначала класс по содержимому по всем непустым листам (вектор лучше смешанного, смешанный — скана);
    внутри лучшего класса листы с заголовком другого листа альбома («Развертки…», «Экспликация…») — в конце; среди остальных лист с заголовком
    плана — если содержимого у него не меньше TITLE_MIN_CONTENT лучшего, иначе — по содержимому, как v010. Обложка-скан «План расстановки
    мебели» не берётся вместо векторного плана без заголовка (S1, T3), таблица со строкой «Планировка…» — вместо плана (S2) -> (лист, способ)"""
    if not plan_pages:
        return (max(pages, key=plan_score) if pages else None), 'по содержимому'
    best = max(CLASS_RANK.get(p['class'], 0) for p in plan_pages)
    cand = [p for p in plan_pages if CLASS_RANK.get(p['class'], 0) == best]
    base = [p for p in cand if p.get('title_kind') != 'other'] or cand
    top = max(plan_score(p)[1] for p in base)
    titled = [p for p in base if p.get('title_kind') == 'plan' and plan_score(p)[1] >= TITLE_MIN_CONTENT * top]
    chosen = max(titled or base, key=plan_score)
    if titled:
        return chosen, 'по заголовку «%s»' % chosen['title']
    how = 'по содержимому'
    if any(p.get('title_kind') == 'other' for p in cand) and len(base) < len(cand):
        how += ' (листы с заголовком другого листа альбома — в конце)'
    skipped = [p['number'] for p in plan_pages if p.get('title_kind') == 'plan']
    if skipped:
        how += ' (заголовок плана у листа %s — класс ниже или содержимого меньше половины)' % ', '.join(map(str, skipped))
    return chosen, how


def apply_smask(pix, mask):
    """v011 (Б1): маска прозрачности на картинку; у картинки уже есть альфа — снять до маски (Pixmap(pix, 0)), иначе Pixmap(pix, mask)
    падает «color pixmap must not have an alpha channel» (измеритель «12», образец Photoshop). Альфу картинки без цветового пространства
    не снять — ValueError: native берётся рендером области (intake_pdf)"""
    import pymupdf
    if pix.alpha:
        if pix.colorspace is None:
            raise ValueError('у картинки своя альфа без цветового пространства — альфу не снять')
        pix = pymupdf.Pixmap(pix, 0)
    return pymupdf.Pixmap(pix, mask)


def flatten_native(doc, xref, smask):
    """Картинка из PDF в исходном разрешении; маска прозрачности — на белом."""
    import pymupdf
    pix = pymupdf.Pixmap(doc, xref)
    if smask:
        mask = pymupdf.Pixmap(doc, smask)
        pix = apply_smask(pix, mask)
    if pix.colorspace and pix.colorspace.n not in (1, 3):      # CMYK и прочее → RGB
        pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
    mode = {1: 'L', 3: 'RGB'}.get(pix.n - (1 if pix.alpha else 0), 'RGB')
    if pix.alpha:
        im = Image.frombytes(mode + 'A' if mode == 'RGB' else 'LA', (pix.width, pix.height), pix.samples)
    else:
        im = Image.frombytes(mode, (pix.width, pix.height), pix.samples)
    return im


HEXTITLE = re.compile(r'^\s*<?\s*([0-9A-Fa-f]{8,}[0-9A-Fa-f\s]*)\s*>?\s*$')


def decode_title(t):
    """dc:title бывает hex-строкой cp1251, обрезанной на полубайте (П3): «<5C5C6466…» -> путь. -> (текст, способ): способ —
    'text' (как есть), 'hex-utf8' или 'hex-cp1251'. Чётность восстанавливается отбрасыванием последнего полубайта; обрезанный
    многобайтный знак utf-8 в конце — отбрасывается; не utf-8 — cp1251 (любой байт, кроме 0x98, — знак)."""
    s = str(t or '')
    m = HEXTITLE.match(s)
    if not m or not (s.strip().startswith('<') or re.fullmatch(r'[0-9A-Fa-f]+', s.strip())):
        return s, 'text'
    h = re.sub(r'\s', '', m[1])
    b = bytes.fromhex(h[:len(h) // 2 * 2])
    for cut in range(0, 4):
        try:
            return b[:len(b) - cut].decode('utf-8'), 'hex-utf8'
        except UnicodeDecodeError:
            continue
    return b.decode('cp1251', errors='replace'), 'hex-cp1251'


def pdf_title(doc):
    """название PDF: Info /Title и XMP dc:title; hex — декодируется; путь модели и признак Revit"""
    raw = (doc.metadata or {}).get('title', '') or ''
    if not raw:
        try:
            x = doc.get_xml_metadata() or ''
            m = re.search(r'<dc:title>.*?<rdf:li[^>]*>(.*?)</rdf:li>', x, re.S)
            raw = m[1].strip() if m else ''
        except Exception:
            raw = ''
    txt, how = decode_title(raw)
    path = txt if re.search(r'^\\\\|^[A-Za-z]:\\|[\\/]', txt) else ''
    revit = bool(re.search(r'\.rvt\b|[\\/]revit[\\/]|\brevit\b', txt, re.I))
    # v014 (ПР6, ПП2 — ПК5-ПП2): путь с расширением файла не Revit (…\Revit\план.dwg — папка или имя файла пользователя) — не путь модели Revit;
    # расширение, которое может быть началом .rvt/.rfa/.rte (title обрезан на полубайте: «….rv»), и путь без расширения (локальная копия
    # «…_<пользователь>») — как раньше ⟨один пример: клиент А — 4 листа одного клиента; синтетика проверяющего⟩
    ext = re.search(r'\.([A-Za-z][A-Za-z0-9]{1,4})\s*$', path)                  # расширение — с буквы: «Лист 1.05» — не расширение
    if revit and ext and not re.search(r'\.rvt\b', txt, re.I) and not any(r.startswith(ext[1].lower()) for r in ('rvt', 'rfa', 'rte')):
        revit = False
    return dict(title_raw=raw[:600], title=txt[:600], title_decoded=how, model_path=path[:600], revit_sign=revit)


def intake_pdf(path, out, rep, notes, page_no=None, dpi=200, max_side=10000):
    try:
        import pymupdf
    except ImportError:
        rep['error'] = 'нет pymupdf: pip install pymupdf'
        return
    doc = pymupdf.open(path)
    if doc.needs_pass:
        notes.add('PDF_ENCRYPTED')
        rep['class'] = 'pdf-encrypted'
        rep['route'] = ADVICE['PDF_ENCRYPTED']
        return
    pages = [pdf_page_facts(doc, doc[i]) for i in range(min(doc.page_count, 60))]
    for p in pages:
        p['class'] = classify_page(p)
    rep['pdf'] = {'pages': doc.page_count, 'producer': (doc.metadata or {}).get('producer', ''),
                  'creator': (doc.metadata or {}).get('creator', ''), **pdf_title(doc), 'page_facts': pages}
    try:
        if doc.get_ocgs():
            notes.add('PDF_OCG')
            rep['pdf']['ocg'] = [v.get('name') for v in doc.get_ocgs().values()]
    except Exception:                                            # noqa: BLE001
        pass
    plan_pages = [p for p in pages if p['class'] != 'pdf-empty']
    if len(plan_pages) > 1:
        notes.add('PDF_MULTIPAGE')
    # v014 (ПР6, И13/П-239): листы-планы по заголовкам — список и предупреждения; эскиз (вектор < VECTOR_MIN_SEGMENTS отрезков) в счёт
    # «несколько листов-планов» не идёт (черновик 0816, is_sparse); выбор листа не меняется
    cands = [p for p in pages if p.get('tier', 4) <= 3 and p['class'] != 'pdf-empty']
    rep['pdf']['plan_candidates'] = [{'page': p['number'], 'tier': p['tier'], 'what': TIER_NAME[p['tier']], 'floors': p.get('floors', []),
                                      'class': p['class'], 'few_lines': p['class'] in ('pdf-vector', 'pdf-mixed') and p['segments'] < VECTOR_MIN_SEGMENTS,
                                      'title': next((t['text'] for t in p.get('titles', []) if t['kind'] == p['tier']), '')} for p in cands]
    if sum(not c['few_lines'] for c in rep['pdf']['plan_candidates']) > 1:
        notes.add('PDF_PLAN_CANDIDATES')
    rep['pdf']['walls_pages'] = [p['number'] for p in cands if p.get('walls_title')]
    how = 'задан ключом --page'
    if page_no is None:                                          # v011 (Б4): лист альбома — по заголовку страницы, без заголовка — по содержимому
        chosen, how = choose_page(pages, plan_pages)
    else:
        chosen = pages[page_no - 1]
    if chosen is None:
        rep['error'] = 'в PDF нет страниц'
        return
    rep['chosen_page'] = chosen['number']
    rep['chosen_by'] = how
    cls = chosen['class']
    rep['class'] = cls
    rep['route'] = ROUTES[cls]
    if cls == 'pdf-empty':
        notes.add('NOT_A_PLAN_PAGE')
    if len(chosen.get('floors', [])) > 1:                        # v014 (ПР6, И14): на выбранном листе — планы нескольких этажей
        notes.add('PDF_MULTI_FLOOR')
    if rep['pdf']['walls_pages'] and chosen['number'] not in rep['pdf']['walls_pages']:
        notes.add('PDF_WALLS_SHEET')                             # v014 (ПР6, П-239): стены — с «Плана перегородок»
    if cls in ('pdf-vector', 'pdf-mixed') and chosen['segments'] < VECTOR_MIN_SEGMENTS:
        notes.add('PDF_FEW_LINES')                               # v011 (Б5): эскиз — мало линий, но линии покрывают лист
    if chosen['rotation']:
        notes.add('PDF_ROTATED')
    if chosen['invisible_chars'] and cls in ('pdf-scan', 'pdf-composite', 'pdf-mixed'):
        notes.add('PDF_OCR_LAYER')
    if chosen['annotations']:
        notes.add('PDF_ANNOTATIONS')
    if chosen.get('cp1251_as_latin1'):
        notes.add('TEXT_CP1251_AS_LATIN1')                       # v012 (Б6)
    if chosen['rotated_images']:
        notes.add('PDF_ROTATED_INSETS')
    if cls in ('pdf-vector', 'pdf-mixed') and (chosen.get('zero_share', 0) > 0.20 or (chosen.get('one_item_share', 0) > 0.95 and chosen.get('fills_only_re'))):
        notes.add('PDF_FLATTENED')
    page = doc[chosen['number'] - 1]
    long_pt = max(page.rect.width, page.rect.height)
    use_dpi = min(float(dpi), max_side * 72.0 / long_pt)
    mat = page.rotation_matrix * pymupdf.Matrix(use_dpi / 72.0, use_dpi / 72.0)
    pix = page.get_pixmap(matrix=pymupdf.Matrix(use_dpi / 72.0, use_dpi / 72.0), alpha=False, annots=True)
    rgb = Image.frombytes('RGB', (pix.width, pix.height), pix.samples)
    save_work(rgb, out)
    try:                                                         # v014 (ПР6, И1): текст выбранного листа — для паспорта (масштаб, размеры, штамп, язык)
        rep['_text'] = page.get_text()[:200000]
    except Exception:                                            # noqa: BLE001 — нет текстового слоя
        rep['_text'] = ''
    if chosen['annotations']:
        pix2 = page.get_pixmap(matrix=pymupdf.Matrix(use_dpi / 72.0, use_dpi / 72.0), alpha=False, annots=False)
        Image.frombytes('RGB', (pix2.width, pix2.height), pix2.samples).save(os.path.join(out, 'work_noannot.png'))
    rep['render'] = {'dpi': round(use_dpi, 2), 'work_size': [pix.width, pix.height],
                     # точка из get_drawings() (неповёрнутые координаты страницы) → пиксель work.png:
                     'to_pixels': [round(v, 6) for v in (mat.a, mat.b, mat.c, mat.d, mat.e, mat.f)],
                     'light_share': round(light_share(rgb), 3)}
    if rep['render']['light_share'] < 0.30:
        notes.add('DARK_BACKGROUND')
    # скан: главная картинка в исходном разрешении
    if cls in ('pdf-scan', 'pdf-mixed', 'pdf-composite') and chosen['images']:
        main = max(chosen['images'], key=lambda i: i['cover'])
        info = doc.extract_image(main['xref']) or {}
        smask = info.get('smask', 0)
        if smask:
            notes.add('PDF_SMASK')
        jq = None                                                # v014 (ПР6, И2): сжатие JPEG картинки скана — та же оценка, что у растра
        if info.get('ext') in ('jpeg', 'jpg') and info.get('image'):
            try:
                with Image.open(io.BytesIO(info['image'])) as jim:
                    jq = jpeg_quality(jim)
            except Exception:                                    # noqa: BLE001 — оценка не нужна для приёма
                jq = None
            if jq is not None and jq < LOWQ_JPEG:
                notes.add('PDF_SCAN_LOWQ')
        rot_m = page.rotation_matrix if page.rotation else pymupdf.Matrix(1, 0, 0, 1, 0, 0)   # v012 (Б17): clip — в повёрнутых координатах листа
        tiles = chosen.get('tiles') if cls == 'pdf-scan' else None
        if tiles:                                                # v012 (Б19): плитки одной картинки — native = их общая рамка в их dpi
            notes.add('PDF_TILES')
            bbs = [i['bbox_pt'] for i in chosen['images']]
            main = dict(main, bbox_pt=[min(b[0] for b in bbs), min(b[1] for b in bbs), max(b[2] for b in bbs), max(b[3] for b in bbs)])
            k = max(main['dpi'], 72.0) / 72.0
            pn = page.get_pixmap(matrix=pymupdf.Matrix(k, k), clip=(pymupdf.Rect(main['bbox_pt']) * rot_m) & page.rect, alpha=False)
            nat = Image.frombytes('RGB', (pn.width, pn.height), pn.samples)
        else:
            try:
                nat, _ = to_rgb8(flatten_native(doc, main['xref'], smask), notes)
            except Exception as e:                               # noqa: BLE001 — v011 (Б1): картинку не извлечь — рендер её области в исходном разрешении
                notes.add('PDF_NATIVE_RENDER')
                bb = (pymupdf.Rect(main['bbox_pt']) * rot_m) & page.rect; k = max(main['dpi'], 72.0) / 72.0
                pn = page.get_pixmap(matrix=pymupdf.Matrix(k, k), clip=bb, alpha=False)
                nat = Image.frombytes('RGB', (pn.width, pn.height), pn.samples); rep['native_error'] = str(e)[:200]
        name = 'native_%d.png' % main['xref']
        nat.save(os.path.join(out, name))
        rep['native'] = {'file': name, 'xref': main['xref'], 'px': list(nat.size), 'dpi': main['dpi'],
                         'encoding': info.get('ext'), 'smask': bool(smask),
                         'rotated_or_mirrored': main['rotated_or_mirrored'], 'bbox_pt': main['bbox_pt'],
                         # v012 (Б20): work.png = k × картинка — мм/px по work.png делить на k
                         'work_scale_k': round(use_dpi / max(main['dpi'], 1e-6), 3),
                         # v012 (Б17): картинка извлечена в своей ориентации — на странице с /Rotate она не повёрнута, work.png — повёрнут
                         'page_rotation': chosen['rotation'], 'rotated_like_work': bool(tiles) or 'PDF_NATIVE_RENDER' in notes or not chosen['rotation']}
        if tiles:
            rep['native']['tiles'] = tiles
        if jq is not None:
            rep['native']['jpeg_quality'] = jq                   # v014 (ПР6, И2)
        paper = paper_format(page.rect.width, page.rect.height)  # v012 (Б21): dpi страницы — мера только у страницы формата бумаги
        rep['native']['paper'] = paper
        if paper and main['dpi'] < LOWRES_SCAN_DPI:
            notes.add('PDF_LOWRES_SCAN')
        elif not paper and max(nat.size) < SMALL_RASTER_SIDE:
            notes.add('SMALL_RASTER')                            # иначе — длина картинки, как у растра
        if cls == 'pdf-scan':
            rep['native']['edge_cut'] = note_edge_cut(nat, notes)   # v012 (Б22): обрез краем кадра — по картинке скана
    if cls == 'pdf-scan' and (chosen['paths'] or chosen['words']):   # v012 (Б18): разметка поверх скана (у pdf-scan вектора плана нет — has_vector ложно)
        fill_pt = 0.0
        for d in page.get_drawings():
            if d.get('fill') is not None:
                fill_pt += abs(pymupdf.Rect(d['rect']) & page.cropbox)
        main_pt = abs(pymupdf.Rect(rep['native']['bbox_pt'])) if rep.get('native') else 0.0
        rep['overlay'] = {'paths': chosen['paths'], 'words': chosen['words'], 'filled_share_of_image': round(fill_pt / main_pt, 4) if main_pt else None}
        notes.add('PDF_SCAN_OVERLAY')
    notes.discard('PALETTE')                                     # палитра внутри PDF неважна


# v014 (ПР6, И1): паспорт исходника — загрузка модуля и вызов
def _passport_module():
    """v014 (ПР6, И1): passport.py — из папки этого файла (не зависит от sys.path вызывающего)"""
    m = sys.modules.get('passport')
    if m is not None and hasattr(m, 'passport') and hasattr(m, 'PROFILES'):
        return m
    import importlib.util
    spec = importlib.util.spec_from_file_location('passport', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'passport.py'))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); sys.modules['passport'] = m
    return m


def add_passport(rep):
    """v014 (ПР6, И1): паспорт исходника в rep['passport']; текст листа (_text, _text_pdf) — только для паспорта, в intake.json не пишется;
    любая ошибка паспорта — rep['passport_error'], приём не падает"""
    text = rep.pop('_text', '') or ''
    rep.pop('_text_pdf', None)
    try:
        rep['passport'] = _passport_module().passport(rep, text)
    except Exception as e:                                       # noqa: BLE001 — паспорт не роняет приём
        rep.pop('passport', None)
        rep['passport_error'] = ('%s: %s' % (type(e).__name__, e))[:300]


def intake(path, out, page_no=None, dpi=200, max_side=10000):
    os.makedirs(out, exist_ok=True)
    notes = set()
    kind = sniff(path)
    ext = os.path.splitext(path)[1].lower()
    rep = {'file': os.path.basename(path), 'bytes': os.path.getsize(path), 'sha256': sha256(path),
           'kind': kind, 'extension': ext}
    if kind in EXT_OF and ext not in EXT_OF[kind]:
        notes.add('EXT_MISMATCH')
    if kind == 'pdf':
        intake_pdf(path, out, rep, notes, page_no, dpi, max_side)
    elif kind in ('png', 'jpeg', 'gif', 'tiff', 'bmp', 'webp'):
        intake_raster(path, kind, out, rep, notes)
    elif kind == 'heic':
        try:
            import pillow_heif                                       # noqa: F401
            pillow_heif.register_heif_opener()
            intake_raster(path, kind, out, rep, notes)
        except ImportError:
            rep['class'] = 'unsupported'
            rep['route'] = 'HEIC/AVIF: нужен pillow-heif; нет — попросить у клиента JPEG, PNG или PDF'
    elif kind in ('dwg', 'dxf'):                                     # v014 (ПР3, Б25; И7, И16): чертёж CAD — cad_intake.py
        try:                                                         # v014 (ПРV-К2): любое исключение ветки CAD — громко, код 2, intake.json пишется
            import cad_intake
            ADVICE.update(cad_intake.ADVICE); ROUTES.update(cad_intake.ROUTES)
            cad_intake.intake_cad(path, kind, out, rep, notes)
        except Exception as e:                                       # noqa: BLE001
            code = 'DWG_READ_FAILED' if kind == 'dwg' else 'DXF_READ_FAILED'
            err = ('%s: %s' % (type(e).__name__, e)).replace('\n', ' ')[:200]
            rep.setdefault('cad', {})['read_error'] = err
            rep['class'] = 'cad-error'
            rep['route'] = CAD_ERROR_ROUTE
            notes.add(code)
            rep.setdefault('_warn_detail', {})[code] = 'ошибка: ' + err
            st = {'code': code, 'why': 'чертёж не прочитан — %s.' % err, 'ask': 'PDF плана со слоями или файл чертежа заново (DXF или DWG)'}
            if rep.get('stop'):
                rep['stop'].setdefault('also', []).append(st)
            else:
                rep['stop'] = st
            rep.pop('_text', None); rep.pop('_text_pdf', None)
        rep.setdefault('route', ROUTES.get(rep.get('class'), ROUTES['unsupported']))
    elif kind == 'svg':
        rep['class'] = 'svg'
        rep['route'] = ROUTES['svg']
    elif kind == 'office':
        rep['class'] = 'office'
        rep['route'] = ROUTES['office']
    else:
        rep['class'] = 'unsupported'
        rep['route'] = ROUTES['unsupported']
    det = rep.pop('_warn_detail', None) or {}                    # v014 (ПРV-К2, К5): путь, текст ошибки — к тексту предупреждения
    rep['warnings'] = [{'code': c, 'what': ADVICE[c] + (' — %s' % det[c] if c in det else '')} for c in sorted(notes)]
    add_passport(rep)                                            # v014 (ПР6, И1): паспорт исходника; снимает _text и _text_pdf до записи
    rep.pop('_text', None); rep.pop('_text_pdf', None)            # v014 (ПР3, Б25; слияние): страховка — подписи модели CAD не в intake.json
    with open(os.path.join(out, 'intake.json'), 'w', encoding='utf-8') as f:
        json.dump(rep, f, ensure_ascii=False, indent=1)
    with open(os.path.join(out, 'intake.md'), 'w', encoding='utf-8') as f:
        f.write(to_md(rep))
    return rep


def to_md(rep):
    L = ['# Приём исходника — %s' % rep['file'], '',
         '| Что | Значение |', '|---|---|',
         '| Файл | `%s`, %s байт |' % (rep['file'], format(rep['bytes'], ',').replace(',', ' ')),
         '| SHA-256 оригинала (Ч-01) | `%s` |' % rep['sha256'],
         '| Формат по содержимому | %s%s |' % (rep['kind'], ' — расширение %s не совпадает' % rep['extension']
                                               if any(w['code'] == 'EXT_MISMATCH' for w in rep.get('warnings', [])) else ''),
         '| Класс | %s |' % rep.get('class', '—'),
         '| Маршрут | %s |' % rep.get('route', '—')]
    r = rep.get('raster')
    if r:
        L.append('| Растр | %s × %s, режим %s; EXIF-поворот %s; прозрачных пикселей %.1f %%; светлого %.0f %% |' % (
            r['size'][0], r['size'][1], r['mode'], r.get('exif_orientation'), 100 * r.get('alpha_transparent_share', 0),
            100 * r.get('light_share', 0)))
        if 'jpeg_quality' in r:
            L.append('| JPEG | качество ≈ %s, цвет %s |' % (r.get('jpeg_quality'), r.get('jpeg_sampling')))
    p = rep.get('pdf')
    if p:
        L.append('| PDF | листов %s; выбран %s%s; producer «%s» |' % (p['pages'], rep.get('chosen_page'), (' — ' + rep['chosen_by']) if rep.get('chosen_by') and p['pages'] > 1 else '', p.get('producer', '')))
        if p.get('title'):
            L.append('| Название (dc:title) | %s%s |' % (p['title'].replace('|', '\\|'), {'hex-cp1251': ' — декодировано из hex, cp1251',
                                                                                     'hex-utf8': ' — декодировано из hex, utf-8'}.get(p.get('title_decoded'), '')))
        if p.get('model_path'):
            L.append('| Путь модели | `%s`%s |' % (p['model_path'], ' — признак Revit (П3)' if p.get('revit_sign') else ''))
        L += ['', '| Лист | Класс | Размер, pt | /Rotate | Путей | Отрезков | Под картинками | Картинок (с поворотом) | Слов | Невидимых знаков | Аннотаций |',
              '|---|---|---|---|---|---|---|---|---|---|---|']
        for f in p['page_facts']:
            L.append('| %d | %s | %s × %s | %s | %s | %s | %.0f %% | %d (%d) | %s | %s | %d |' % (
                f['number'], f['class'], f['size_pt'][0], f['size_pt'][1], f['rotation'], f['paths'], f['segments'],
                100 * f['image_cover'], len(f['images']), f['rotated_images'], f['words'], f['invisible_chars'],
                len(f['annotations'])))
        cand = p.get('plan_candidates') or []                    # v014 (ПР6, И13/И14/П-239): листы-планы по заголовкам и этажам
        if cand:
            by_floor = {}
            for c in cand:
                for fl in (c['floors'] or [None]):
                    by_floor.setdefault(fl, []).append(c)
            L += ['', '**Листы-планы по заголовкам** (И13; выбран — %s, %s%s):' % (rep.get('chosen_page'), rep.get('chosen_by', '—'),
                  '; стены — с «Плана перегородок», стр. %s (П-239)' % ', '.join(map(str, p['walls_pages'])) if p.get('walls_pages') else ''), '']
            for fl in sorted(by_floor, key=lambda v: (v is None, v or 0)):
                L.append('- %s: %s' % ('этаж %s' % fl if fl is not None else 'этаж не указан', '; '.join(
                    'стр. %d — %s%s%s' % (c['page'], c['what'], ', «%s»' % c['title'].replace('|', '/') if c['title'] else '',
                                          ' (мало линий)' if c.get('few_lines') else '') for c in by_floor[fl])))
        ch = next((f for f in p['page_facts'] if f['number'] == rep.get('chosen_page')), {})
        if ch.get('cp1251_as_latin1'):                           # v012 (Б6)
            c = ch['cp1251_as_latin1']
            L += ['', 'Текст cp1251, прочитанный как latin-1: слов %d из %d; например %s.' % (c['words'], c['of'], ', '.join('«%s» → «%s»' % tuple(x) for x in c['examples'][:3]))]
        if rep.get('render'):
            L += ['', 'Рендер: %s dpi, %s × %s px; матрица «точка PDF → пиксель work.png»: `%s`.' % (
                rep['render']['dpi'], rep['render']['work_size'][0], rep['render']['work_size'][1],
                ', '.join(str(v) for v in rep['render']['to_pixels']))]
        if rep.get('native'):
            n = rep['native']
            L.append('Картинка в исходном разрешении: `%s`, %s × %s px, %s dpi, %s%s%s%s.' % (
                n['file'], n['px'][0], n['px'][1], n['dpi'], n.get('encoding'), ', с маской прозрачности' if n['smask'] else '',
                ', плиток %d — одна картинка, общая рамка' % n['tiles'] if n.get('tiles') else '',
                ', качество JPEG ≈ %s' % n['jpeg_quality'] if n.get('jpeg_quality') is not None else ''))   # v014 (ПР6, И2)
            if n.get('work_scale_k'):                            # v012 (Б20)
                L.append('`work.png` = %s × картинка (dpi рендера / dpi картинки): мм/px по `work.png` — делить на %s.' % (
                    format(n['work_scale_k'], '.2f').replace('.', ','), format(n['work_scale_k'], '.2f').replace('.', ',')))
            if n.get('page_rotation') and not n.get('rotated_like_work'):   # v012 (Б17)
                L.append('Страница повёрнута (/Rotate %s): `%s` — в ориентации самой картинки, не повёрнут; `work.png` — повёрнут, как на экране.' % (
                    n['page_rotation'], n['file']))
            if n.get('paper') is not None or 'paper' in n:
                L.append('Формат страницы: %s.' % (n['paper'] or 'не формат бумаги — dpi страницы не мера разрешения; разрешение — в мм/px после масштаба (map/rules/10 §5.7)'))
        if rep.get('overlay'):                                   # v012 (Б18)
            o = rep['overlay']
            L.append('Разметка поверх скана: путей %s, слов %s, заливка — %s картинки.' % (
                o['paths'], o['words'], ('%.2f %%' % (100 * o['filled_share_of_image'])).replace('.', ',') if o['filled_share_of_image'] is not None else '—'))
    for e in [x for x in ((rep.get('raster') or {}).get('edge_cut'), (rep.get('native') or {}).get('edge_cut')) if x]:   # v012 (Б22)
        if max(e[k] for k in ('лево', 'право', 'верх', 'низ')) >= EDGE_MIN:
            L.append('Линии за краем кадра: слева %d, справа %d, сверху %d, снизу %d (глубина %d px, ширина ≤ %d px).' % (
                e['лево'], e['право'], e['верх'], e['низ'], e['depth_px'], e['run_px']))
    if rep.get('cad'):                                           # v014 (ПР3, Б25): раздел чертежа CAD
        try:                                                     # v014 (ПРV-К2): раздел не собрался — intake.md всё равно пишется
            import cad_intake
            L += cad_intake.md_lines(rep)
        except Exception as e:                                   # noqa: BLE001
            L += ['', '**Чертёж CAD:** раздел не собран — %s: %s' % (type(e).__name__, str(e)[:200])]
            for st in ([rep['stop']] + rep['stop'].get('also', [])) if rep.get('stop') else []:
                L += ['', '**Остановка (%s):** %s Просить у клиента: %s' % (st['code'], st['why'], st['ask'])]
    if rep.get('error'):
        L += ['', '**Ошибка:** %s' % rep['error']]
    if rep.get('passport'):                                      # v014 (ПР6, И1): раздел «Паспорт исходника»
        try:
            L += _passport_module().to_md(rep['passport'])
        except Exception as e:                                   # noqa: BLE001 — паспорт не роняет приём
            L += ['', '## Паспорт исходника', '', 'Раздел не собран: %s: %s' % (type(e).__name__, str(e)[:200])]
    elif rep.get('passport_error'):
        L += ['', '## Паспорт исходника', '', 'Паспорт не собран: %s' % rep['passport_error']]
    L += ['', '## Предупреждения', '']
    L += ['- **%s** — %s' % (w['code'], w['what']) for w in rep.get('warnings', [])] or ['- нет']
    return '\n'.join(L) + '\n'


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('src')
    ap.add_argument('--out', default='intake_out')
    ap.add_argument('--page', type=int)
    ap.add_argument('--dpi', type=float, default=200)
    ap.add_argument('--max-side', type=int, default=10000)
    a = ap.parse_args()
    rep = intake(a.src, a.out, a.page, a.dpi, a.max_side)
    print(json.dumps({k: rep.get(k) for k in ('kind', 'class', 'route', 'chosen_page')}, ensure_ascii=False))
    for w in rep.get('warnings', []):
        print(' -', w['code'], '—', w['what'])
    sys.exit(2 if rep.get('error') or rep.get('stop') or rep.get('class') in ('unsupported', 'pdf-encrypted', 'pdf-empty', 'cad-error') else 0)   # stop — v014 (ПР3, Б25); cad-error — ПРV-К2


if __name__ == '__main__':
    main()
