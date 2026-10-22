#!/usr/bin/env python3
"""Приём чертежа CAD — DWG и DXF (черновик чата исходников, 07.10.2026; И7, И16; к source_intake.py).

DWG переводится в DXF конвертером LibreDWG (`dwg2dxf`), DXF читается одним проходом без загрузки в память — так читаются и
DXF на сотни мегабайт. Пишет в папку приёма:
  work.dxf          — DXF из DWG (DXF клиента не копируется: читается на месте);
  dxf_preview.png   — превью модели: линии, дуги, полилинии без раскрытия блоков; красные точки — вставки блоков, синие рамки — виды;
  intake.json, поле cad — шапка, единицы, виды, слои, блоки, картинки и ссылки, признаки выгрузки из Revit.

Пять проверок (каждая — предупреждение с причиной; числа — в cad):
  DWG_UNITS        — единицы в шапке не сходятся с единицами по объектам: размерам, дверям, столам, габариту этажа;
  DWG_MULTI_VIEW   — в модели несколько видов (этажей, вариантов) или подписи разных этажей в одном — рисовать один: какой, спросить;
  DWG_ENGINEERING  — раздел не архитектурный: больше трети сущностей — на слоях инженерных систем или больше четверти вставок —
                     их элементы (оросители, светильники, приборы);
  DWG_IMAGES_MISSING, DWG_XREF — картинки и внешние ссылки не приложены: части чертежа нет в файле;
  DWG_FROM_REVIT   — выгрузка из Revit: имена блоков «семейство - тип-номер-вид», геометрия в блоках в десятки раз больше модели.
Затем — work.pdf (cad_pdf.py): векторный PDF, слой DXF → слой OCG, лист на вид; масштаб 48,04 мм/pt, если единицы уверены
(units_sure), иначе DWG_SCALE_UNKNOWN и лист по A0; work.pdf принимается как PDF — рендер, листы, слои (поля pdf, render).
  DWG_DIM_OVERRIDE — у четверти размеров текст переписан вручную (cad.pdf.dims);
  DWG_3D_SOLIDS    — на видимых слоях 3D-тела ACIS: их в work.pdf нет (cad.pdf.not_drawn, solid_layers).
Виды и превью — без выключенных и замороженных слоёв. Внешняя ссылка, файл которой лежит рядом (то же имя или «(Клиент) имя»),
читается и рисуется вместе с чертежом; DWG_XREF — только о тех, файлов которых нет.
Конвертер не найден — DWG_NO_CONVERTER и рецепт сборки (README пакета); DXF читается и без него.

Конвертер ищется так: переменная UNS_DWG2DXF, затем dwg2dxf в PATH, затем ~/tools/ldwg/bin/dwg2dxf (рецепт сборки — README).
Переменная задана, а файла нет, он не исполняемый или не запускается — предупреждение DWG_CONVERTER_ENV_BAD с путём и причиной
(v014, ПРV-К5), поиск идёт дальше — в PATH и ~/tools/ldwg; не нашёлся нигде — ещё и DWG_NO_CONVERTER (cad.converter_search).
Зависимости: numpy, Pillow.

v014 (ПР3, Б25; перенос части A черновика 0816 в код карты v013):
  - хуки в source_intake.py — sniff, EXT_OF, диспетчер в intake(), раздел cad в to_md (md_lines), маршруты — ROUTES здесь;
  - Б25: шапка $INSUNITS даёт габарит вида, невозможный для этажа здания (длинная сторона < FLOOR_MIN_MM или > FLOOR_MAX_MM),
    а объектов для сверки нет или они не сходятся на одной единице — DWG_UNITS_SUSPECT, остановка (rep.stop: причина и что
    просить у клиента); ничья признаков между единицами больше не решается порядком списка — cad.units.tie, by_objects = None;
  - новый признак по геометрии, не по имени: «машино-место» — повторяющийся прямоугольник 2,2–2,8 × 4,5–5,5 м (замкнутая
    полилиния из 4 вершин или рамка блока), от STALL_MIN_REPEAT одинаковых ⟨один пример: синтетика «парковка»⟩.
v014 (ПР4, Б24; внешние ссылки громко):
  - DWG_XREF_EMPTY — найденная рядом ссылка пуста (0 сущностей модели) или не читается: предупреждение, причина — cad.xrefs[].empty;
  - DWG_XREF_PLAN_MISSING — план лежит во внешней ссылке, которой нет или которая пуста: остановка rep.stop (xref_plan_check; доли
    и пороги XREF_* — в cad.xref_plan); второстепенная недостающая ссылка (у файла есть свой план или найдена другая непустая ссылка) —
    только DWG_XREF.
v014 (ПРV — исправления по независимой проверке, 17.10.2026):
  - К1: модель пуста или почти пуста (геометрии модели меньше MODEL_MIN_GEOM сущностей, точек меньше VIEW_MIN_POINTS — видов нет)
    или work.pdf не построен — остановка rep.stop (DWG_MODEL_EMPTY или DWG_PDF_FAILED: причина и что просить), код выхода 2;
    маршрут — без work.pdf (ROUTE_NO_PDF);
  - К2: исключение при чтении чертежа — в source_intake.intake(): класс cad-error, DWG_READ_FAILED / DXF_READ_FAILED с текстом ошибки,
    rep.stop, intake.json пишется, код выхода 2; пустой ответ конвертера на --version и незапускаемый конвертер — не исключение;
  - К3: $EXTMIN/$EXTMAX пусты — габарит для DWG_XREF_PLAN_MISSING — по геометрии модели (своей и точкам вставок ссылок); габарит
    вырожден (только точки) — доля своей геометрии по числу сущностей, не занятая доля габарита — 1;
  - К5: плохой UNS_DWG2DXF — DWG_CONVERTER_ENV_BAD с путём (не молча);
  - К10: $INSUNITS вне словаря — в intake.md «код N — не из словаря», не «не заданы»."""
import collections, math, os, re, shutil, subprocess, time

import numpy as np
from PIL import Image, ImageDraw

DWG_VERSIONS = {'AC1009': 'R11/R12', 'AC1012': 'R13', 'AC1014': 'R14', 'AC1015': 'AutoCAD 2000', 'AC1018': 'AutoCAD 2004',
                'AC1021': 'AutoCAD 2007', 'AC1024': 'AutoCAD 2010', 'AC1027': 'AutoCAD 2013', 'AC1032': 'AutoCAD 2018'}
INSUNITS = {1: 'дюйм', 2: 'фут', 4: 'мм', 5: 'см', 6: 'м', 14: 'дм'}
# v014 (ПРV-К10): коды $INSUNITS AutoCAD вне словаря приёма — только для подписи в intake.md («код 7 (км) — не из словаря»)
INSUNITS_OTHER = {3: 'миля', 7: 'км', 8: 'микродюйм', 9: 'мил', 10: 'ярд', 11: 'ангстрем', 12: 'нм', 13: 'мкм', 15: 'дам', 16: 'гм',
                  17: 'Гм', 18: 'а. е.', 19: 'св. год', 20: 'парсек', 21: 'фут США', 22: 'дюйм США', 23: 'ярд США', 24: 'миля США'}
UNIT_M = {'мм': 0.001, 'см': 0.01, 'дм': 0.1, 'м': 1.0, 'дюйм': 0.0254, 'фут': 0.3048}
CANDIDATES = ('мм', 'см', 'м', 'дюйм', 'фут')
# правдоподобные размеры в метрах: медиана размеров чертежа, дверь, стол, габарит вида этажа
PLAUSIBLE = {'размеры': (0.3, 15.0), 'дверь': (0.6, 1.3), 'стол': (0.6, 2.4), 'габарит вида': (8.0, 300.0),
             'машино-место': (4.5, 5.5)}   # v014 (Б25): длинная сторона; короткая — STALL_M[0], считается только при споре с шапкой
DOOR_RE = re.compile(r'двер|door|\bдв[\b_\d-]|^д[\d_-]|^dr[\d_-]', re.I)
DESK_RE = re.compile(r'стол|desk|table|workstation|bench|рабоч\w*\s*мест', re.I)
ENG_RE = re.compile(r'ороси|спринкл|пожар|\bапт\b|\bпт[_\s-]|водопр|канализ|\bвк[_\s-]|\bк1\b|\bв1\b|отоплен|\bов[_\s-]|вентил|кондиц|воздух|'
                    r'электр|\bэо[_\s-]|\bэм[_\s-]|освещ|светил|розет|кабел|слаботоч|\bсс[_\s-]|\bскс\b|сигнализ|'
                    r'sprinkl|fire|plumb|sanit|hvac|duct|mech|electr|lighting|power|cable|^[mepf]-', re.I)
ARCH_RE = re.compile(r'стен|wall|перегор|partition|двер|door|окн|window|витраж|curtain|мебел|furn|колонн|column', re.I)
REVIT_BLOCK_RE = re.compile(r'\s-\s.+-\d{5,9}-|^basic wall|^curtain wall|семейство|^m_[a-z]|-\d{6,9}-.*\b(level|floor|этаж)\b', re.I)
FLOOR_RES = [re.compile(r'(?<![\d.,])(\d{1,3})\s*(?:-?\s*(?:й|ой|ий|ый|го|м))?\s*этаж', re.I), re.compile(r'этаж\w*\s*(?:№\s*)?(\d{1,3})(?![\d.,])', re.I),
             re.compile(r'\b(?:floor|level)\s*(\d{1,3})\b', re.I), re.compile(r'\b(\d{1,3})(?:st|nd|rd|th)\s+floor\b', re.I)]
XREF_GEOM_TYPES = {'LINE', 'LWPOLYLINE', 'POLYLINE', 'ARC', 'CIRCLE', 'ELLIPSE', 'SPLINE', 'HATCH', 'SOLID', 'MLINE', '3DFACE',
                   '3DSOLID', 'REGION', 'INSERT'}   # v014 (ПР4, Б24): геометрия модели; текст, размеры, картинки — не геометрия
POINT_TYPES = {'LINE', 'LWPOLYLINE', 'VERTEX', 'ARC', 'CIRCLE', 'INSERT', 'TEXT', 'MTEXT', 'DIMENSION', 'SPLINE', 'ELLIPSE', 'SOLID',
               '3DFACE', 'POINT', 'IMAGE', 'ATTRIB'}
# v014 (ПР3, Б25): габарит вида, невозможный для этажа здания, — по длинной стороне вида в единицах шапки, мм
FLOOR_MIN_MM = 3_000           # меньше 3 м — не этаж (лестничная клетка и та больше)
FLOOR_MAX_MM = 2_000_000       # больше 2 км — не этаж (самые длинные здания ≈ 1,5 км)
# v014 (ПР3, Б25): машино-место — объект известного размера по геометрии (не по имени): повторяющийся прямоугольник
STALL_M = ((2.2, 2.8), (4.5, 5.5))   # короткая и длинная сторона, м ⟨один пример: синтетика «парковка 50 × 30 м»⟩
STALL_ASPECT = (0.40, 0.62)          # короткая / длинная — без единиц: 2,2 / 5,5 … 2,8 / 4,5
STALL_MIN_REPEAT = 4                 # одинаковых (± 2 %) прямоугольников не меньше — ряд мест, а не случайный прямоугольник
STALL_TOL = 0.02
MAX_RECTS = 200_000
# v014 (ПР4, Б24): план лежит во внешней ссылке, которой нет или которая пуста — доли, не имена. ⟨один пример: синтетика «хост с одной
# вставкой ссылки»; настоящего файла с остановкой в наборе нет — образец 1 и образец 2 не стоп, образец 3 Арендаторы 6 — не стоп⟩
XREF_OWN_SHARE_MAX = 0.25      # доля сущностей модели, принадлежащих самому файлу (без вставок ссылок, рамки и штампа), не больше
XREF_GAP_MIN = 0.50            # доля габарита чертежа ($EXTMIN–$EXTMAX), не занятая собственной геометрией (там, где лежит ссылка), не меньше
XREF_FRAME_SPAN = 0.50         # рамка листа: линия, прямоугольник или блок с длинной стороной не меньше этой доли габарита
XREF_STAMP_ZONE = (0.55, 0.25) # штамп: правая 45 % и нижняя 25 % габарита (x от доли, y до доли) — геометрия там не считается своей
# v014 (ПРV-К1): модель пуста или почти пуста — остановка, work.pdf не обещается. Числа сущностей, не px и не мм:
VIEW_MIN_POINTS = 50           # точек сущностей модели (с вставками и найденными ссылками) меньше — видов нет, work.pdf не строится (find_views)
MODEL_MIN_GEOM = 10            # сущностей геометрии модели (XREF_GEOM_TYPES, видимые слои; с сущностями найденных ссылок) меньше — «почти пусто»:
                               #   текст, размеры и картинки без линий — не план ⟨синтетика ПРV: tiny.dxf — 3 линии; у реальных DWG — тысячи⟩
MAX_GEOM = 500_000             # сущностей модели, у которых хранится рамка, — память
MAX_SEGMENTS = 3_000_000
MAX_BLOCK_SEGMENTS = 4_000_000   # отрезков в блоках хранится не больше — память
ADVICE = {
    'DWG_NO_CONVERTER': 'DWG без конвертера не читается: собрать LibreDWG по рецепту (README пакета; ≈ 15 мин) или указать его в '
                        'UNS_DWG2DXF (где искали — cad.converter_search); до того — попросить у клиента PDF со слоями (map/rules/20 §2)',
    'DWG_CONVERT_FAILED': 'LibreDWG не перевёл DWG в DXF — причина в cad.convert; попросить у клиента PDF со слоями или DXF',
    'DWG_UNITS': 'единицы в шапке не сходятся с единицами по объектам (cad.units): брать единицы по объектам — размеры, двери, столы, '
                 'габарит этажа; масштаб — map/rules/30 §2',
    'DWG_MULTI_VIEW': 'в модели несколько видов — этажи, варианты или листы с рамками (cad.views, рамки — на dxf_preview.png): рисовать '
                      'каждый вид отдельно — какой, спросить; вид выбирать по подписи и составу',
    'DWG_ENGINEERING': 'раздел не архитектурный: инженерных систем больше трети сущностей или четверти вставок (cad.engineering): стены и мебель — по '
                       'архитектурным слоям, остальные слои отключить',
    'DWG_IMAGES_MISSING': 'в чертеже вставлены картинки, файлов которых нет рядом (cad.images): часть плана может быть картинкой — '
                          'попросить у клиента файлы картинок или PDF',
    'DWG_XREF': 'в чертеже внешние ссылки, файлов которых рядом нет (cad.xrefs, found = null): их геометрии в файле нет — попросить у '
                'клиента файлы ссылок или PDF целиком. Файл ссылки рядом с чертежом (то же имя или «(Клиент) имя») читается сам',
    # v014 (ПР4, Б24): ссылка пуста — предупреждение; план в недостающей ссылке — остановка
    'DWG_XREF_EMPTY': 'внешняя ссылка найдена рядом, но пуста или не читается (cad.xrefs[].empty — причина): её геометрии в чертеже нет — '
                      'попросить у клиента рабочий файл ссылки или DWG с внедрёнными ссылками (Bind/eTransmit); это не молчание, а потеря части чертежа',
    'DWG_XREF_PLAN_MISSING': 'ОСТАНОВКА: сам план лежит во внешней ссылке, которой нет рядом или которая пуста (cad.xref_plan, rep.stop): у файла '
                             'почти нет собственной геометрии, а ссылка занимает большую часть габарита. Рисовать нечего — попросить у клиента файл '
                             'ссылки или DWG с внедрёнными ссылками (Bind/eTransmit), либо PDF плана',
    'DWG_FROM_REVIT': 'выгрузка из Revit (cad.revit): слои — категории Revit, стены и мебель — блоками семейств; геометрия блоков '
                      'раскрывается при чтении, имена семейств — подсказка класса',
    # v014 (ПРV-К1): work.pdf не построен — остановка, а не «успех» с маршрутом через work.pdf
    'DWG_PDF_FAILED': 'ОСТАНОВКА: векторный PDF из DXF не собран — причина в cad.pdf_error (rep.stop): work.pdf нет, маршрут через него '
                      'не идёт; DXF и превью есть — разобрать причину или попросить у клиента PDF плана со слоями',
    'DWG_MODEL_EMPTY': 'ОСТАНОВКА: в пространстве модели нет плана — геометрии меньше MODEL_MIN_GEOM сущностей или точек меньше '
                       'VIEW_MIN_POINTS (cad.model_empty, rep.stop): видов нет, work.pdf не построен. План может лежать в листе '
                       '(Layout) или во внешней ссылке — попросить у клиента DWG с планом в модели или PDF плана',
    'DWG_CONVERTER_ENV_BAD': 'переменная UNS_DWG2DXF задана, но по её пути конвертера нет, он не исполняемый или не запускается '
                             '(путь и причина — здесь и в cad.converter_search): исправить переменную; до того DWG переводит '
                             'конвертер, найденный дальше (PATH, ~/tools/ldwg), если он есть',
    'DWG_DIM_OVERRIDE': 'у четверти размеров и больше текст переписан вручную и не равен геометрии (cad.pdf.dims): масштаб по числам '
                        'размеров ненадёжен; известный масштаб work.pdf (cad.pdf.mm_per_pt) — по построению; сверять только по '
                        'размерам с неизменённым текстом',
    'DWG_3D_SOLIDS': 'часть элементов на видимых слоях — 3D-тела ACIS (3DSOLID, REGION; cad.pdf.not_drawn, слои — cad.pdf.solid_layers): '
                     'их геометрии в DXF нет, в work.pdf они не нарисованы — так могут пропасть столы. Сверить с PDF клиента или попросить '
                     'PDF, напечатанный из AutoCAD',
    'DWG_SCALE_UNKNOWN': 'единицы чертежа не определены уверенно (cad.units): work.pdf — без известного масштаба, вид по формату A0 '
                         '(cad.pdf.scale); масштаб — по размерам на листе, как у любого PDF (map/rules/30 §2; маршрут по слоям — Э3); '
                         'подсказка — cad.pdf.dims.ratio: число размера к длине на листе (100 — виды на листе в 1:100)',
    'DWG_UNITS_SUSPECT': 'ОСТАНОВКА: единицы в шапке ($INSUNITS) дают габарит вида, невозможный для этажа здания, а объектов известного '
                         'размера (размеры, двери, столы, машино-места) для сверки нет или они не сходятся на одной единице (cad.units.suspect, '
                         'rep.stop): масштаб не брать ни по шапке, ни по габариту. Спросить у клиента единицы чертежа или длину одного '
                         'элемента в натуре (стена, пролёт, машино-место), либо PDF с размерами (map/rules/30 §2)',
}

# v014 (ПР3, Б25): маршруты классов чертежа CAD — подключаются в source_intake.intake() (ROUTES.update)
# v014 (ПРV-К1): маршрут, когда work.pdf нет (пустая модель, PDF не собран) — не обещает work.pdf
ROUTE_NO_PDF = ('чертёж CAD прочитан, но work.pdf НЕ построен — остановка (intake.md, «Остановка»; cad.model_empty или cad.pdf_error): '
                'рисовать не по чему; что есть — шапка, слои, превью dxf_preview.png (если записано); что просить — rep.stop.ask')
ROUTES = {
    'cad-error': 'чертёж CAD не прочитан — ошибка чтения (cad.read_error, rep.stop): попросить у клиента PDF плана со слоями или DXF '
                 'заново; разбор ошибки — по тексту в предупреждении',          # v014 (ПРV-К2)
    'cad-dwg': 'чертёж CAD: DWG → DXF (work.dxf) → work.pdf — векторный лист со слоями OCG, лист на вид (cad.pdf); масштаб — 48,04 мм/pt, '
               'если единицы определены (cad.pdf.mm_per_pt), иначе — по размерам на листе (DWG_SCALE_UNKNOWN). Дальше — как лист CAD со '
               'слоями: карта — map/rules/11, числа из вектора; инженерный план — маршрут по слоям (ocg/); вид этажа — cad.views, '
               'единицы — cad.units; рамки видов — dxf_preview.png',
    'cad-dxf': 'чертёж CAD в DXF → work.pdf — векторный лист со слоями OCG, лист на вид (cad.pdf); масштаб — 48,04 мм/pt, если единицы '
               'определены (cad.pdf.mm_per_pt), иначе — по размерам на листе. Дальше — как лист CAD со слоями: карта — map/rules/11; '
               'инженерный план — маршрут по слоям (ocg/); вид этажа — cad.views, единицы — cad.units',
}


def dwg_version(path):
    with open(path, 'rb') as f:
        head = f.read(6)
    v = head.decode('ascii', 'replace')
    return v, DWG_VERSIONS.get(v, 'неизвестная версия')


CONVERTER_SEARCH = []                                            # v014: где искали конвертер и что нашли — в cad.converter_search


CONVERTER_ENV_BAD = []                                           # v014 (ПРV-К5): плохой UNS_DWG2DXF — «путь — причина»; читает intake_cad


def _conv_env(exe):
    """окружение запуска конвертера: библиотека LibreDWG рядом с бинарём (../lib) — в LD_LIBRARY_PATH"""
    env = dict(os.environ)
    lib = os.path.join(os.path.dirname(os.path.dirname(exe)), 'lib')
    if os.path.isdir(lib):
        env['LD_LIBRARY_PATH'] = lib + (':' + env['LD_LIBRARY_PATH'] if env.get('LD_LIBRARY_PATH') else '')
    return env


def _runs(exe):
    """v014 (ПРV-К5): конвертер запускается? `--version` — None, если да; иначе причина (ошибка запуска, нет библиотеки — код 126/127)"""
    try:
        r = subprocess.run([exe, '--version'], capture_output=True, env=_conv_env(exe), timeout=30)
    except subprocess.TimeoutExpired:
        return 'не запускается: --version не ответил за 30 с'
    except OSError as e:
        return 'не запускается: %s: %s' % (type(e).__name__, str(e)[:120])
    if r.returncode in (126, 127):
        return 'не запускается: код %d, %s' % (r.returncode, (r.stderr or b'').decode('utf-8', 'replace').strip()[:120])
    return None


def find_converter():
    """dwg2dxf: UNS_DWG2DXF, затем PATH, затем ~/tools/ldwg/bin. Каждая попытка — в CONVERTER_SEARCH (громко, не тихий пропуск).
    v014 (ПРV-К5): UNS_DWG2DXF задан, но файла нет, он не исполняемый или не запускается — запись в CONVERTER_ENV_BAD (предупреждение
    DWG_CONVERTER_ENV_BAD с путём), поиск идёт дальше; раньше плохая переменная молча подменялась конвертером из PATH."""
    CONVERTER_SEARCH.clear(); CONVERTER_ENV_BAD.clear()
    env = os.environ.get('UNS_DWG2DXF')
    for src, p in (('UNS_DWG2DXF', env), ('PATH', shutil.which('dwg2dxf')), ('~/tools/ldwg', os.path.expanduser('~/tools/ldwg/bin/dwg2dxf'))):
        if not p:
            CONVERTER_SEARCH.append('%s: не задан' % src if src != 'PATH' else 'PATH: dwg2dxf нет')
            continue
        if os.path.isfile(p) and os.access(p, os.X_OK):
            why = _runs(p)                                       # v014 (ПРV-К5): исполняемый, но не запускается — тоже не найден
            if why is None:
                CONVERTER_SEARCH.append('%s: %s' % (src, p))
                return p
        else:
            why = 'нет файла' if not os.path.isfile(p) else 'не исполняемый'
        CONVERTER_SEARCH.append('%s: %s — %s' % (src, p, why))
        if src == 'UNS_DWG2DXF':
            CONVERTER_ENV_BAD.append('UNS_DWG2DXF=%s — %s' % (p, why))
    return None


def convert(path, out, exe, timeout=900, name='work.dxf'):
    """DWG → DXF той же версии. Возвращает (путь DXF или None, сведения)."""
    dxf = os.path.join(out, name)
    env = _conv_env(exe)
    t0 = time.time()
    info = {'converter': exe}
    try:
        ver = subprocess.run([exe, '--version'], capture_output=True, env=env, timeout=30)
        lines = (ver.stdout or ver.stderr or b'').decode('utf-8', 'replace').strip().splitlines()   # v014 (ПРV-К2): пустой ответ — не IndexError
        info['converter_version'] = lines[0][:60] if lines else '— (пустой ответ на --version)'
        r = subprocess.run([exe, '-y', '-o', dxf, path], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, env=env, timeout=timeout)
        info.update(exit=r.returncode, stderr_tail=(r.stderr or b'')[-400:].decode('utf-8', 'replace'))   # LibreDWG печатает и cp1251
    except subprocess.TimeoutExpired:
        info.update(exit='timeout')
    except OSError as e:                                         # v014 (ПРV-К2): конвертер не запускается — DWG_CONVERT_FAILED, не traceback
        info.update(exit='не запускается: %s: %s' % (type(e).__name__, str(e)[:120]))
    info['secs'] = round(time.time() - t0, 1)
    ok = os.path.exists(dxf) and os.path.getsize(dxf) > 0 and info.get('exit') in (0, 1)   # 1 — предупреждения LibreDWG, DXF есть
    if ok:
        info['dxf_bytes'] = os.path.getsize(dxf)
    return (dxf if ok else None), info


def dec_dxf(s):
    """строка DXF: UTF-8; битый байт внутри UTF-8 (так пишет LibreDWG) — убирается, строка остаётся UTF-8; иначе — cp1251"""
    try:
        return s.decode('utf-8')
    except UnicodeDecodeError:
        u = s.decode('utf-8', 'replace')
        bad = u.count('\ufffd'); good = sum(1 for ch in u if ord(ch) > 127) - bad
        return u.replace('\ufffd', '') if good >= 4 * bad else s.decode('cp1251', 'replace')


def _val(b):
    return dec_dxf(b.rstrip(b'\r\n'))


def scan_dxf(path):
    """Один проход по тегам DXF (код, значение): шапка, слои, блоки (число сущностей, рамка, флаги, путь ссылки), сущности модели
    (тип, слой, первая точка, отрезки для превью, вставки, размеры, тексты), картинки и их файлы."""
    hdr, layers_tab, blocks = {}, {}, {}
    ents_by_layer, ents_by_type, inserts = collections.Counter(), collections.Counter(), collections.Counter()
    pts, ins_pts, segs, dims, texts, images, imagedefs = [], [], [], [], [], 0, []
    rects = []                                                   # v014 (Б25): замкнутые прямоугольники модели — (короткая, длинная)
    mg, mg_total = [], [0]                                       # v014 (ПР4, Б24): геометрия модели — (тип, x0, y0, x1, y1, имя); число сущностей без ATTRIB/SEQEND/VERTEX
    sec, var, ent, blk, cur = None, None, None, None, None
    prev_vertex = None

    bsegs, bins, bstore = {}, {}, [0]                            # блоки: отрезки, вложенные вставки; всего отрезков в блоках

    def face_record(d):
        """вершина-грань сетки (флаг 128 без 64): координат нет, это номера вершин — не точка"""
        f = d.get('vflags', 0)
        return bool(f & 128) and not f & 64

    def hidden(d):
        """слой выключен или заморожен — AutoCAD его не печатает: не в виды, не в превью, не в рамки блоков"""
        L = layers_tab.get(d.get('layer', '0'))
        return bool(L and (L['off'] or L['frozen']))

    def ent_segs(t, d, pv):
        """отрезки сущности для превью: линия, полилиния, дуга и окружность (12 хорд), вершина старой полилинии"""
        xy, out = d.get('xy', []), []
        if t == 'LINE' and xy and d.get('xy2'):
            out.append((xy[0][0], xy[0][1], d['xy2'][0], d['xy2'][1]))
        elif t == 'LWPOLYLINE' and len(xy) >= 2:
            q = xy + ([xy[0]] if d.get('closed') else [])
            out.extend((q[i][0], q[i][1], q[i + 1][0], q[i + 1][1]) for i in range(len(q) - 1))
        elif t in ('ARC', 'CIRCLE') and xy and d.get('r'):
            (cx, cy), r = xy[0], d['r']
            a0, a1 = (math.radians(d.get('a0', 0.0)), math.radians(d.get('a1', 360.0))) if t == 'ARC' else (0.0, 2 * math.pi)
            if a1 < a0:
                a1 += 2 * math.pi
            for i in range(12):
                u, v = a0 + (a1 - a0) * i / 12, a0 + (a1 - a0) * (i + 1) / 12
                out.append((cx + r * math.cos(u), cy + r * math.sin(u), cx + r * math.cos(v), cy + r * math.sin(v)))
        elif t == 'VERTEX' and xy and pv is not None and not face_record(d):
            out.append((pv[0], pv[1], xy[0][0], xy[0][1]))
        return out

    def flush(e):
        """сущность закончилась: в блок — рамка, отрезки, вложенные вставки; в модель — счёт, точки, отрезки"""
        nonlocal images, prev_vertex
        if e is None:
            return
        t, d = e['type'], e
        if t == 'POLYLINE':
            prev_vertex = None
        xy = d.get('xy', [])
        if sec == 'BLOCKS':
            if blk is not None and t not in ('BLOCK', 'ENDBLK') and hidden(d) and d.get('layer', '0') != '0':   # «0» в блоке — слой вставки
                blocks[blk]['n'] += 1
            elif blk is not None and t not in ('BLOCK', 'ENDBLK'):
                b = blocks[blk]; b['n'] += 1
                for x, y in (xy[:400] + ([d['xy2']] if d.get('xy2') else [])):
                    b['bb'][0] = min(b['bb'][0], x); b['bb'][1] = min(b['bb'][1], y); b['bb'][2] = max(b['bb'][2], x); b['bb'][3] = max(b['bb'][3], y)
                if t in ('ARC', 'CIRCLE') and xy and d.get('r'):
                    (x, y), r = xy[0], d['r']
                    b['bb'][0] = min(b['bb'][0], x - r); b['bb'][1] = min(b['bb'][1], y - r); b['bb'][2] = max(b['bb'][2], x + r); b['bb'][3] = max(b['bb'][3], y + r)
                if bstore[0] < MAX_BLOCK_SEGMENTS:
                    sg = ent_segs(t, d, prev_vertex)
                    if sg:
                        bsegs.setdefault(blk, []).extend(sg); bstore[0] += len(sg)
                if t == 'INSERT' and xy:
                    bins.setdefault(blk, []).append((d.get('name', '?'), xy[0][0], xy[0][1], d.get('sx', 1.0), d.get('sy', 1.0), d.get('rot', 0.0)))
            if t == 'VERTEX' and xy and not face_record(d):
                prev_vertex = xy[0]
            elif t == 'SEQEND':
                prev_vertex = None
            return
        if sec != 'ENTITIES' or d.get('paper'):
            return
        ents_by_type[t] += 1; ents_by_layer[d.get('layer', '0')] += 1
        hid = hidden(d)
        if t not in ('ATTRIB', 'SEQEND', 'VERTEX'):             # v014 (ПР4, Б24): сущность модели для доли «своей» геометрии
            mg_total[0] += 1
            if t in XREF_GEOM_TYPES and not hid and len(mg) < MAX_GEOM:
                if t == 'LINE' and xy and d.get('xy2'):
                    mg.append((t, min(xy[0][0], d['xy2'][0]), min(xy[0][1], d['xy2'][1]), max(xy[0][0], d['xy2'][0]), max(xy[0][1], d['xy2'][1]), ''))
                elif t == 'LWPOLYLINE' and xy:
                    mg.append((t, min(p[0] for p in xy), min(p[1] for p in xy), max(p[0] for p in xy), max(p[1] for p in xy), ''))
                elif t in ('POLYLINE', 'HATCH', 'MLINE', '3DSOLID', 'REGION', '3DFACE', 'SOLID') or not xy:
                    mg.append((t, math.nan, math.nan, math.nan, math.nan, d.get('name', '')))      # координат у сущности нет: считается, в рамку не входит
                elif t == 'ARC' or t == 'CIRCLE':
                    r_ = d.get('r', 0.0); mg.append((t, xy[0][0] - r_, xy[0][1] - r_, xy[0][0] + r_, xy[0][1] + r_, ''))
                else:                                           # INSERT, ELLIPSE, SPLINE: первая точка
                    mg.append((t, xy[0][0], xy[0][1], xy[0][0], xy[0][1], d.get('name', '')))
        if t in POINT_TYPES and xy and not hid and not face_record(d):
            pts.append(xy[0])
        if t == 'LWPOLYLINE' and not hid and len(rects) < MAX_RECTS:   # v014 (Б25): прямоугольник — признак машино-места
            r = rect_sides(xy, d.get('closed'))
            if r:
                rects.append(r)
        if t == 'INSERT':
            inserts[d.get('name', '?')] += 1
            if xy and not hid:
                ins_pts.append((xy[0][0], xy[0][1], d.get('name', '?'), d.get('sx', 1.0), d.get('sy', 1.0), d.get('rot', 0.0)))
        elif t == 'DIMENSION' and d.get('meas') is not None:
            dims.append(d['meas'])
        elif t in ('TEXT', 'MTEXT', 'ATTRIB') and d.get('text') and xy:
            if len(texts) < 50000:
                texts.append((xy[0][0], xy[0][1], d['text'][:120]))
        elif t == 'IMAGE':
            images += 1
        if len(segs) < MAX_SEGMENTS and not hid:
            segs.extend(ent_segs(t, d, prev_vertex))
        if t == 'VERTEX' and xy and not face_record(d):
            prev_vertex = xy[0]
        elif t == 'SEQEND':
            prev_vertex = None

    with open(path, 'rb') as f:
        while True:
            c = f.readline()
            if not c:
                break
            v = f.readline()
            try:
                code = int(c.strip())
            except ValueError:
                continue
            if code == 0:
                val = v.strip().decode('ascii', 'replace')
                flush(ent); ent = None
                if val == 'SECTION':
                    cur = 'SECTION'; continue
                if val == 'ENDSEC':
                    sec = None; continue
                if val == 'EOF':
                    break
                if sec == 'TABLES':
                    ent = {'type': val} if val == 'LAYER' else None
                    if ent is not None:
                        ent['table'] = True
                    continue
                if sec == 'BLOCKS' and val == 'BLOCK':
                    ent = {'type': 'BLOCK', 'block_head': True}; continue
                if sec == 'BLOCKS' and val == 'ENDBLK':
                    blk = None; continue
                if sec == 'OBJECTS':
                    ent = {'type': val, 'obj': True} if val == 'IMAGEDEF' else None
                    continue
                if sec in ('ENTITIES', 'BLOCKS'):
                    ent = {'type': val}
                continue
            if cur == 'SECTION':
                if code == 2:
                    sec = _val(v).strip(); cur = None
                continue
            if sec == 'HEADER':
                if code == 9:
                    var = _val(v).strip()
                elif var in ('$ACADVER', '$DWGCODEPAGE') and code in (1, 3):
                    hdr[var] = _val(v).strip()
                elif var in ('$INSUNITS', '$MEASUREMENT', '$LUNITS') and code == 70:
                    hdr[var] = int(v.strip() or 0)
                elif var in ('$EXTMIN', '$EXTMAX') and code in (10, 20):
                    hdr.setdefault(var, [None, None])[0 if code == 10 else 1] = float(v.strip() or 0)
                continue
            if ent is None:
                continue
            if ent.get('table'):                                  # LAYER
                if code == 2:
                    ent['name'] = _val(v).strip(); layers_tab[ent['name']] = {'off': False, 'frozen': False}
                elif code == 70 and 'name' in ent:
                    fl = int(v.strip() or 0); layers_tab[ent['name']]['frozen'] = bool(fl & 1)
                elif code == 62 and 'name' in ent:
                    layers_tab[ent['name']]['off'] = int(v.strip() or 0) < 0
                continue
            if ent.get('obj'):                                    # IMAGEDEF: путь к файлу
                if code == 1:
                    imagedefs.append(_val(v).strip())
                continue
            if ent.get('block_head'):                             # BLOCK: имя, флаги, путь ссылки
                if code == 2:
                    blk = _val(v).strip(); blocks[blk] = {'n': 0, 'flags': 0, 'xref': '', 'base': [0.0, 0.0], 'bb': [math.inf, math.inf, -math.inf, -math.inf]}
                elif code in (10, 20) and blk:
                    blocks[blk]['base'][0 if code == 10 else 1] = float(v.strip() or 0)
                elif code == 70 and blk:
                    blocks[blk]['flags'] = int(v.strip() or 0)
                elif code == 1 and blk:
                    blocks[blk]['xref'] = _val(v).strip()
                continue
            t = ent['type']
            if code == 8:
                ent['layer'] = _val(v).strip()
            elif code == 67:
                ent['paper'] = v.strip() == b'1'
            elif code == 10:
                ent.setdefault('xy', []).append([float(v.strip() or 0), 0.0])
            elif code == 20 and ent.get('xy'):
                ent['xy'][-1][1] = float(v.strip() or 0)
            elif code == 11 and t == 'LINE':
                ent['xy2'] = [float(v.strip() or 0), 0.0]
            elif code == 21 and t == 'LINE' and ent.get('xy2') is not None:
                ent['xy2'][1] = float(v.strip() or 0)
            elif code == 40 and t in ('ARC', 'CIRCLE'):
                ent['r'] = float(v.strip() or 0)
            elif code == 50 and t == 'ARC':
                ent['a0'] = float(v.strip() or 0)
            elif code == 51 and t == 'ARC':
                ent['a1'] = float(v.strip() or 0)
            elif code == 70 and t == 'LWPOLYLINE':
                ent['closed'] = bool(int(v.strip() or 0) & 1)
            elif code == 70 and t == 'VERTEX':
                ent['vflags'] = int(v.strip() or 0)
            elif code == 2 and t == 'INSERT':
                ent['name'] = _val(v).strip()
            elif code == 41 and t == 'INSERT':
                ent['sx'] = float(v.strip() or 1)
            elif code == 42 and t == 'INSERT':
                ent['sy'] = float(v.strip() or 1)
            elif code == 50 and t == 'INSERT':
                ent['rot'] = float(v.strip() or 0)
            elif code == 42 and t == 'DIMENSION':
                ent['meas'] = float(v.strip() or 0)
            elif code in (1, 3) and t in ('TEXT', 'MTEXT', 'ATTRIB'):
                ent['text'] = (ent.get('text', '') + _val(v))[:400]
        flush(ent)
    bsegs = {k: np.asarray(v, float).reshape(-1, 4) for k, v in bsegs.items()}
    for b in blocks.values():
        bb = b['bb']
        b['size'] = [round(bb[2] - bb[0], 3), round(bb[3] - bb[1], 3)] if bb[0] < math.inf else None
        del b['bb']
    return dict(header=hdr, layers_table=layers_tab, blocks=blocks, ents_by_layer=ents_by_layer, ents_by_type=ents_by_type,
                inserts=inserts, pts=np.asarray(pts, float).reshape(-1, 2), ins_pts=ins_pts, segs=np.asarray(segs, float).reshape(-1, 4),
                block_segs=bsegs, block_inserts=bins,
                dims=dims, texts=texts, images=images, imagedefs=imagedefs, rects=rects, geom=mg, model_total=mg_total[0])


def expand_inserts(scan, cap=MAX_SEGMENTS, depth=3):
    """блоки, вставленные в модель, — в отрезки модели: точка вставки, масштаб, поворот, базовая точка блока; вложенные — до 3 уровней"""
    out, total = [], 0
    def go(name, M, lvl):
        nonlocal total
        if total >= cap or lvl > depth:
            return
        b = scan['blocks'].get(name) or {}
        base = b.get('base', [0.0, 0.0])
        sg = scan['block_segs'].get(name)
        if sg is not None and len(sg):
            p = sg.reshape(-1, 2) - base
            q = p @ M[:, :2].T + M[:, 2]
            out.append(q.reshape(-1, 4)); total += len(sg)
        for nm, x, y, sx, sy, rot in scan['block_inserts'].get(name, [])[:2000]:
            go(nm, M @ np.vstack([affine(x - base[0], y - base[1], sx, sy, rot), [0, 0, 1]]), lvl + 1)
    for x, y, nm, sx, sy, rot in scan['ins_pts']:
        if total >= cap:
            break
        go(nm, affine(x, y, sx, sy, rot), 1)
    return np.vstack(out) if out else np.zeros((0, 4))


def find_xref_file(xpath, base_dir, exclude=None):
    """файл внешней ссылки рядом с исходником: то же имя, иначе — имя, которое им кончается («(Клиент) имя.dwg»)"""
    name = os.path.basename((xpath or '').replace('\\', '/')).strip()
    if not name.lower().endswith(('.dwg', '.dxf')):
        return None
    try:
        files = sorted(f for f in os.listdir(base_dir) if os.path.isfile(os.path.join(base_dir, f)))
    except OSError:
        return None
    ex = os.path.abspath(exclude) if exclude else None
    for test in (lambda f: f.lower() == name.lower(), lambda f: f.lower().endswith(name.lower())):
        for f in files:
            if test(f) and os.path.abspath(os.path.join(base_dir, f)) != ex:
                return os.path.join(base_dir, f)
    return None


def resolve_xrefs(path, out, s, blocks, notes):
    """внешние ссылки модели: файл рядом с исходником — в DXF (xref_N.dxf), его отрезки и точки — в координаты модели по каждой
    вставке. -> (записи cad.xrefs, {блок ссылки: DXF}, отрезки, точки)"""
    recs, dxfs, segs, pts = [], {}, [], []
    base_dir = os.path.dirname(os.path.abspath(path))
    for i, (k, b) in enumerate(sorted((k, b) for k, b in blocks.items() if b['flags'] & 4)):
        rec = {'name': k, 'path': b['xref'], 'found': None, 'searched': base_dir}      # v014 (ПР4, Б24): где искали
        recs.append(rec)
        f = find_xref_file(b['xref'], base_dir, exclude=path)
        if not f:
            continue
        rec['found'] = os.path.basename(f)
        xd = f
        if f.lower().endswith('.dwg'):
            exe = find_converter()
            if not exe:
                rec['empty'] = 'файл найден, но в DXF не переведён: конвертер DWG не найден'          # v014 (ПР4, Б24)
                continue
            xd, rec['convert'] = convert(f, out, exe, name='xref_%d.dxf' % (i + 1))
            if not xd:
                rec['empty'] = 'файл найден, но не читается: LibreDWG не перевёл его в DXF (cad.xrefs[].convert)'   # v014 (ПР4, Б24)
                continue
        try:                                                                                          # v014 (ПР4, Б24): нечитаемый файл — не молчание
            xs = scan_dxf(xd)
        except Exception as e:                                                                        # noqa: BLE001
            rec['empty'] = 'файл найден, но не читается: %s: %s' % (type(e).__name__, str(e)[:120])
            continue
        xsegs = np.vstack([xs['segs'], expand_inserts(xs, cap=MAX_SEGMENTS // 2)])
        xpts = np.vstack([xs['pts'], np.asarray([(x, y) for x, y, *_ in xs['ins_pts']], float).reshape(-1, 2),
                          xsegs.reshape(-1, 2)[::max(1, len(xsegs) // 200000)]])          # концы отрезков — рамка вида
        n = 0
        for x, y, nm, sx, sy, rot in s['ins_pts']:
            if nm != k:
                continue
            M = affine(x, y, sx, sy, rot); base = np.asarray(b['base'], float)
            segs.append(((xsegs.reshape(-1, 2) - base) @ M[:, :2].T + M[:, 2]).reshape(-1, 4))
            pts.append((xpts - base) @ M[:, :2].T + M[:, 2]); n += 1
        rec.update(dxf=os.path.basename(xd), inserts=n, entities=int(sum(xs['ents_by_type'].values())),
                   units=INSUNITS.get(xs['header'].get('$INSUNITS')))
        if not rec['entities']:                                                                       # v014 (ПР4, Б24): найдена, но пуста
            rec['empty'] = 'файл найден и читается, но в пространстве модели 0 сущностей'
        if n:
            dxfs[k] = xd
    if any(r['name'] not in dxfs for r in recs):
        notes.add('DWG_XREF')
    if any(r.get('empty') for r in recs):                                                             # v014 (ПР4, Б24)
        notes.add('DWG_XREF_EMPTY')
    return recs, dxfs, segs, pts


def affine(x, y, sx, sy, rot):
    c, s_ = math.cos(math.radians(rot)), math.sin(math.radians(rot))
    return np.array([[c * sx, -s_ * sy, x], [s_ * sx, c * sy, y]], float)


def split_bands(ink, g, tq, min_part=0.10):
    """вид → части по пустым полосам маски (строки, затем столбцы): строка пуста, если в ней не больше 1 % ширины вида
    (метки обреза, точки); полоса — от 1 % высоты вида и 3 px. Деление принимается, если частей две и больше, в каждой
    10 % линий вида и больше и подписей этажей не больше одного номера на часть, а номера частей разные. -> части или None"""
    def cut(g, axis):
        x0, y0, x1, y1, c = g
        sub = ink[y0:y1 + 1, x0:x1 + 1]
        prof = sub.sum(axis=1) if axis == 0 else sub.sum(axis=0)
        across = sub.shape[1] if axis == 0 else sub.shape[0]
        empty = prof <= max(2, 0.01 * across)
        L = len(prof); runs = []; i = 0
        while i < L:
            if empty[i]:
                j = i
                while j + 1 < L and empty[j + 1]:
                    j += 1
                if i > 0 and j < L - 1 and j - i + 1 >= max(3, 0.01 * L):
                    runs.append((i + j) // 2)
                i = j + 1
            else:
                i += 1
        if not runs:
            return [g]
        edges = [0] + runs + [L - 1]
        out = []
        for a, b in zip(edges[:-1], edges[1:]):
            box = (x0, y0 + a, x1, y0 + b) if axis == 0 else (x0 + a, y0, x0 + b, y1)
            part = ink[box[1]:box[3] + 1, box[0]:box[2] + 1]
            ys, xs = np.nonzero(part)
            if len(ys):
                out.append([box[0] + int(xs.min()), box[1] + int(ys.min()), box[0] + int(xs.max()), box[1] + int(ys.max()), int(len(ys))])
        return out
    parts = [q for p in cut(g, 0) for q in cut(p, 1)]
    tot = sum(p[4] for p in parts) or 1
    parts = [p for p in parts if p[4] >= min_part * tot]
    if len(parts) < 2:
        return None
    fl = [{f for x, y, fs in tq if p[0] <= x <= p[2] and p[1] <= y <= p[3] for f in fs} for p in parts]
    if any(len(f) > 1 for f in fl) or len({min(f) for f in fl if f}) < sum(1 for f in fl if f):
        return None
    return parts


def find_views(segs, pts, side=600, min_ink=0.10, max_views=8, texts=()):
    """виды модели. Линии и точки сущностей — в маску 600 px по длинной стороне (рамка — перцентили точек 0,2–99,8), расширение
    7 × 7, связные области. Области, чьи рамки перекрываются, — один вид (островки мебели, легенда внутри рамки листа). Вид —
    группа с 10 % линий маски и больше: штамп, стрелка севера и разбросанные подписи видом не становятся. Групп больше 8 или нет
    ни одной — вид один, весь чертёж."""
    from PIL import ImageFilter
    if len(pts) < VIEW_MIN_POINTS:                               # v014 (ПРV-К1): именованный порог; видов нет — intake_cad останавливает (DWG_MODEL_EMPTY)
        return [], None
    lo = np.percentile(pts, 0.2, axis=0); hi = np.percentile(pts, 99.8, axis=0)
    span = np.maximum(hi - lo, 1e-9)
    k = (side - 1) / span.max()
    W, H = int(span[0] * k) + 1, int(span[1] * k) + 1
    im = Image.new('L', (W, H), 0); d = ImageDraw.Draw(im)
    for a, b, c, e in segs[:MAX_SEGMENTS]:
        d.line([((a - lo[0]) * k, H - 1 - (b - lo[1]) * k), ((c - lo[0]) * k, H - 1 - (e - lo[1]) * k)], fill=255)
    q = np.clip(((pts - lo) * k).astype(int), 0, [W - 1, H - 1])
    ink = np.asarray(im).copy(); ink[H - 1 - q[:, 1], q[:, 0]] = 255
    ink = ink > 0
    m = np.asarray(Image.fromarray(ink.astype(np.uint8) * 255).filter(ImageFilter.MaxFilter(7))) > 0
    lab = np.zeros(m.shape, np.int32); n = 0; groups = []
    for sy, sx in zip(*np.nonzero(m)):
        if lab[sy, sx]:
            continue
        n += 1; stack = [(sy, sx)]; lab[sy, sx] = n; y0 = y1 = sy; x0 = x1 = sx
        while stack:
            y, x = stack.pop()
            y0, y1, x0, x1 = min(y0, y), max(y1, y), min(x0, x), max(x1, x)
            for yy, xx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
                if 0 <= yy < H and 0 <= xx < W and m[yy, xx] and not lab[yy, xx]:
                    lab[yy, xx] = n; stack.append((yy, xx))
        groups.append([x0, y0, x1, y1, 0])
    if not groups:
        return [], (lo, hi)
    cnt = np.bincount(lab[ink], minlength=n + 1)
    for i, g in enumerate(groups, 1):
        g[4] = int(cnt[i])
    area = lambda g: (g[2] - g[0] + 1) * (g[3] - g[1] + 1)
    merged = True
    while merged:                                                # перекрытые рамки — один вид
        merged = False
        for i in range(len(groups)):
            for j in range(i + 1, len(groups)):
                A, B = groups[i], groups[j]
                ix = min(A[2], B[2]) - max(A[0], B[0]) + 1; iy = min(A[3], B[3]) - max(A[1], B[1]) + 1
                if ix > 0 and iy > 0 and ix * iy >= 0.05 * min(area(A), area(B)):
                    groups[i] = [min(A[0], B[0]), min(A[1], B[1]), max(A[2], B[2]), max(A[3], B[3]), A[4] + B[4]]
                    del groups[j]; merged = True
                    break
            if merged:
                break
    total = sum(g[4] for g in groups)
    keep = [g for g in groups if g[4] >= min_ink * total]
    if len(keep) > max_views or not keep:
        keep = [[min(g[0] for g in groups), min(g[1] for g in groups), max(g[2] for g in groups), max(g[3] for g in groups), total]]
    if texts:                                                    # вид с подписями разных этажей — делится по пустым полосам
        tq = [(int((x - lo[0]) * k), H - 1 - int((y - lo[1]) * k), floors_in(t)) for x, y, t in texts if len(t.split()) <= 6]
        tq = [(x, y, f) for x, y, f in tq if f]
        out = []
        for g in keep:
            parts = split_bands(ink, g, tq) if len({f for x, y, fs in tq if g[0] <= x <= g[2] and g[1] <= y <= g[3] for f in fs}) >= 2 else None
            out.extend(parts or [g])
        keep = out[:max_views] if len(out) <= max_views else keep
    views = []
    for x0, y0, x1, y1, c in keep:
        X0, X1 = lo[0] + x0 / k, lo[0] + (x1 + 1) / k
        Y0, Y1 = lo[1] + (H - 1 - y1) / k, lo[1] + (H - y0) / k
        views.append({'bbox': [round(float(X0), 2), round(float(Y0), 2), round(float(X1), 2), round(float(Y1), 2)], 'share': round(c / max(1, total), 3)})
    views.sort(key=lambda v: (-v['bbox'][3], v['bbox'][0]))    # сверху вниз, слева направо
    return views, (lo, hi)


def floors_in(s):
    out = set()
    for rx in FLOOR_RES:
        out |= {int(v) for v in rx.findall(s)}
    return sorted(f for f in out if f <= 150)


def rect_sides(xy, closed):
    """v014 (Б25): замкнутая полилиния из 4 вершин (или 5 с повтором первой) с прямыми углами (|cos| < 0,02) -> (короткая, длинная)"""
    q = [tuple(p) for p in xy]
    if len(q) == 5 and math.dist(q[0], q[4]) <= 1e-6 * max(1.0, max(abs(v) for p in q for v in p)):
        q = q[:4]; closed = True
    if len(q) != 4 or not closed:
        return None
    v = [(q[(i + 1) % 4][0] - q[i][0], q[(i + 1) % 4][1] - q[i][1]) for i in range(4)]
    L = [math.hypot(*w) for w in v]
    if min(L) <= 0:
        return None
    for i in range(4):
        a, b = v[i], v[(i + 1) % 4]
        if abs(a[0] * b[0] + a[1] * b[1]) > 0.02 * L[i] * L[(i + 1) % 4]:
            return None
    return (min(L), max(L))


def stall_evidence(scan):
    """v014 (Б25): ряд одинаковых прямоугольников с пропорцией машино-места (STALL_ASPECT) — замкнутые полилинии модели и рамки
    вставленных блоков (кроме дверей и столов по имени). -> {'short', 'long', 'count'} самой частой группы или None. Без единиц:
    единицу выбирает unit_guess — какая из них переводит группу в 2,2–2,8 × 4,5–5,5 м."""
    cand = list(scan.get('rects') or [])
    for x, y, name, sx, sy, rot in scan['ins_pts']:
        b = scan['blocks'].get(name) or {}
        if b.get('size') and not DOOR_RE.search(name) and not DESK_RE.search(name):
            w, h = b['size'][0] * abs(sx), b['size'][1] * abs(sy)
            if w > 0 and h > 0:
                cand.append((min(w, h), max(w, h)))
    cand = [(a, b) for a, b in cand if STALL_ASPECT[0] <= a / b <= STALL_ASPECT[1]]
    if len(cand) < STALL_MIN_REPEAT:
        return None
    step = math.log(1 + STALL_TOL)
    groups = collections.defaultdict(list)
    for a, b in cand:
        groups[(round(math.log(a) / step), round(math.log(b) / step))].append((a, b))
    key, best = max(groups.items(), key=lambda kv: len(kv[1]))
    if len(best) < STALL_MIN_REPEAT:
        return None
    return {'short': round(float(np.median([a for a, _ in best])), 4), 'long': round(float(np.median([b for _, b in best])), 4), 'count': len(best)}


def view_span(scan, views):
    """длинная сторона самого большого вида в единицах чертежа; видов нет — по $EXTMIN/$EXTMAX шапки"""
    if views:
        big = max(views, key=lambda v: v['share'])['bbox']
        return max(big[2] - big[0], big[3] - big[1])
    lo, hi = scan['header'].get('$EXTMIN'), scan['header'].get('$EXTMAX')
    if lo and hi and None not in lo + hi and hi[0] > lo[0]:
        return max(hi[0] - lo[0], hi[1] - lo[1])
    return None


def unit_guess(scan, views):
    """единицы по объектам: для каждой кандидатной единицы — сколько признаков попадает в правдоподобный размер"""
    ev = {}
    if scan['dims']:
        ev['размеры'] = float(np.median(np.abs(scan['dims'])))
    door, desk = [], []
    for x, y, name, sx, sy, rot in scan['ins_pts']:
        b = scan['blocks'].get(name) or {}
        if not b.get('size'):
            continue
        s = max(b['size']) * max(abs(sx), abs(sy))
        if s <= 0:
            continue
        if DOOR_RE.search(name):
            door.append(s)
        elif DESK_RE.search(name):
            desk.append(s)
    if len(door) >= 2:
        ev['дверь'] = float(np.median(door))
    if len(desk) >= 2:
        ev['стол'] = float(np.median(desk))
    if views:
        big = max(views, key=lambda v: v['share'])['bbox']
        ev['габарит вида'] = max(big[2] - big[0], big[3] - big[1])
    header = INSUNITS.get(scan['header'].get('$INSUNITS'))
    # v014 (ПР3, Б25): шапка против габарита — длинная сторона вида в единицах шапки, мм; вне FLOOR_MIN_MM…FLOOR_MAX_MM — не этаж
    span = view_span(scan, views)
    span_mm = span * UNIT_M[header] * 1000 if (span and header in UNIT_M) else None
    implausible = span_mm is not None and not FLOOR_MIN_MM <= span_mm <= FLOOR_MAX_MM
    stall = stall_evidence(scan)
    if stall and implausible:                                    # машино-место — признак только для спора с шапкой ⟨один пример: синтетика⟩
        ev['машино-место'] = stall['long']
    score = {}
    for u in CANDIDATES:
        k = UNIT_M[u]
        score[u] = sum(1 for key, val in ev.items() if PLAUSIBLE[key][0] <= val * k <= PLAUSIBLE[key][1]
                       and (key != 'машино-место' or STALL_M[0][0] <= stall['short'] * k <= STALL_M[0][1]))
    best = max(score.values()) if score else 0
    tops = [u for u in CANDIDATES if score[u] == best]
    # v014 (Б25): ничья без шапки среди лидеров — единица не выбирается порядком списка (было: tops[0] молча)
    guess = None if best == 0 else (header if header in tops else (tops[0] if len(tops) == 1 else None))
    out = {'header': header, 'by_objects': guess, 'evidence': {k: round(v, 3) for k, v in ev.items()}, 'score': score,
           'mismatch': bool(best >= 2 and guess and header != guess)}
    if best and len(tops) > 1 and header not in tops:
        out['tie'] = tops
    if span_mm is not None:
        out['header_span_mm'] = round(span_mm, 1)
        out['header_plausible'] = not implausible
    if stall:
        out['stall'] = stall
    return out


def units_sure(u):
    """единицы для масштаба PDF: уверенно — одна единица набрала больше всех признаков и их не меньше двух, или один признак
    и та же единица в шапке. -> (единица, уверенно ли)"""
    unit = u.get('by_objects') or u.get('header')
    sc = u.get('score') or {}
    best = max(sc.values()) if sc else 0
    tops = [k for k, v in sc.items() if v == best]
    sure = unit in UNIT_M and len(tops) == 1 and tops[0] == unit and (best >= 2 or (best == 1 and u.get('header') == unit))
    return unit, sure


def units_suspect(u, rep, notes):
    """v014 (ПР3, Б25): шапка даёт габарит вида не этажа (header_plausible = False), а объекты не дают уверенной другой единицы —
    DWG_UNITS_SUSPECT и остановка rep.stop: причина и что просить у клиента. Объекты дают уверенную другую единицу — это DWG_UNITS
    (mismatch), не остановка."""
    if u.get('header_plausible') is not False:
        return
    unit, sure = units_sure(u)
    if sure and unit != u['header']:
        return
    span_m = u['header_span_mm'] / 1000
    why = ('в шапке $INSUNITS — %s: длинная сторона вида — %s м, а этаж здания — от %s до %s м; объектов известного размера '
           '(размеры, двери, столы, машино-места) %s.' % (
               u['header'], ('%.3g' % span_m).replace('.', ','), FLOOR_MIN_MM // 1000, FLOOR_MAX_MM // 1000,
               'нет' if not set(u['evidence']) - {'габарит вида'} else 'мало или они не сходятся на одной единице (счёт: %s)' % ', '.join(
                   '%s %d' % kv for kv in u['score'].items() if kv[1])))
    u['suspect'] = why
    notes.add('DWG_UNITS_SUSPECT')
    rep['stop'] = {'code': 'DWG_UNITS_SUSPECT', 'why': why,
                   'ask': 'в каких единицах чертёж (мм, см, м) или длину одного элемента в натуре — стены, пролёта между осями, '
                          'машино-места; либо PDF с размерами'}


def xref_plan_check(s, blocks, recs, rep, notes, cad):
    """v014 (ПР4, Б24): план лежит во внешней ссылке, которой нет рядом или которая пуста, — DWG_XREF_PLAN_MISSING и остановка rep.stop.
    Признак — доли, без имён: (1) доля сущностей модели, принадлежащих самому файлу — геометрия (линии, полилинии, дуги, штриховки,
    вставки блоков; текст и размеры — не геометрия), кроме вставок ссылок, рамки листа (линия, прямоугольник или блок длиной от
    XREF_FRAME_SPAN габарита) и штампа (правый нижний угол габарита, XREF_STAMP_ZONE), — от всех сущностей модели без ATTRIB/SEQEND/VERTEX;
    (2) доля габарита чертежа ($EXTMIN–$EXTMAX; AutoCAD считает его с учётом ссылок), не занятая рамкой собственной геометрии, — там
    лежит ссылка. Остановка — обе доли за порогами и нет найденной непустой ссылки, которая могла бы нести план. Ссылка без вставок в
    модель не в счёт. Числа — в cad.xref_plan всегда, когда в модель вставлена недостающая или пустая ссылка."""
    bad = [r for r in recs if (r['found'] is None or r.get('empty')) and s['inserts'].get(r['name'], 0) > 0]
    if not bad:
        return
    ok_x = [r for r in recs if r['found'] and not r.get('empty') and r.get('inserts')]
    names = {r['name'] for r in recs}
    g = [e for e in s['geom'] if not (e[0] == 'INSERT' and e[5] in names)]          # вставки ссылок — не своя геометрия
    n_xins = len(s['geom']) - len(g)
    hdr = s['header']; lo, hi = hdr.get('$EXTMIN'), hdr.get('$EXTMAX')
    ext, ext_src = None, None
    if lo and hi and None not in lo and None not in hi and hi[0] > lo[0] and hi[1] > lo[1]:
        ext, ext_src = (lo[0], lo[1], hi[0], hi[1]), 'header'
    else:                                                            # v014 (ПРV-К3): шапка пуста (1e+20 / −1e+20) — габарит по геометрии
        arr = np.array([e[1:5] for e in s['geom'] if not math.isnan(e[1])], float).reshape(-1, 4)   # своя геометрия и точки вставок ссылок
        if len(arr):
            ext, ext_src = (arr[:, 0].min(), arr[:, 1].min(), arr[:, 2].max(), arr[:, 3].max()), 'geometry'
    flat = ext is None or ext[2] - ext[0] <= 0 or ext[3] - ext[1] <= 0   # v014 (ПРV-К3): габарита нет или он вырожден — только точки
    rec = {'missing': [{'name': r['name'], 'path': r['path'], 'found': r['found'], 'empty': r.get('empty'), 'inserts': s['inserts'].get(r['name'], 0)}
                       for r in bad], 'extents': [round(v, 1) for v in ext] if ext else None, 'extents_source': ext_src, 'xref_inserts': n_xins,
           'model_entities': s['model_total'], 'own_geometry': len(g)}
    cad['xref_plan'] = rec
    span = 0.0 if flat else max(ext[2] - ext[0], ext[3] - ext[1])
    sx, sy = (0.0, 0.0) if flat else (ext[2] - ext[0], ext[3] - ext[1])
    own, frame, stamp = [], 0, 0
    for t_, x0, y0, x1, y1, nm in g:
        if flat:                                                     # v014 (ПРV-К3): без габарита рамки и штампа не выделить — всё своё
            own.append((x0, y0, x1, y1))
        elif t_ == 'INSERT' and (blocks.get(nm) or {}).get('size') and max(blocks[nm]['size']) >= XREF_FRAME_SPAN * span:
            frame += 1                                               # блок размером с лист — рамка
        elif not math.isnan(x0) and t_ in ('LINE', 'LWPOLYLINE') and max(x1 - x0, y1 - y0) >= XREF_FRAME_SPAN * span:
            frame += 1                                               # длинная линия или рамка-прямоугольник
        elif not math.isnan(x0) and x0 >= ext[0] + XREF_STAMP_ZONE[0] * sx and y1 <= ext[1] + XREF_STAMP_ZONE[1] * sy:
            stamp += 1                                               # штамп в правом нижнем углу
        else:
            own.append((x0, y0, x1, y1))
    total = max(1, s['model_total'])
    share = len(own) / total
    pts = np.array([o for o in own if not math.isnan(o[0])], float).reshape(-1, 4)
    if len(pts) >= 50:                                               # хвост подписей и случайных линий не растягивает рамку
        bb = (np.percentile(pts[:, 0], 0.5), np.percentile(pts[:, 1], 0.5), np.percentile(pts[:, 2], 99.5), np.percentile(pts[:, 3], 99.5))
    elif len(pts):
        bb = (pts[:, 0].min(), pts[:, 1].min(), pts[:, 2].max(), pts[:, 3].max())
    else:
        bb = None
    covered = 0.0
    if flat:                                                         # v014 (ПРV-К3): габарит вырожден — своя геометрия площади не занимает: свободно всё
        rec['extents_flat'] = ('габарит чертежа не определён: $EXTMIN/$EXTMAX пусты, а геометрия модели — %s' % (
            'только точки вставок ссылок или линия' if ext else 'без координат')) + '; не занятая доля — 1, доля своей — по числу сущностей'
    elif bb:
        ix = max(0.0, min(bb[2], ext[2]) - max(bb[0], ext[0])); iy = max(0.0, min(bb[3], ext[3]) - max(bb[1], ext[1]))
        covered = ix * iy / (sx * sy)
    gap = 1 - covered
    rec.update(judged=True, own_geometry_ex=len(own), frame=frame, stamp=stamp, own_share=round(share, 4), own_bbox_cover=round(covered, 4),
               xref_gap=round(gap, 4), thresholds={'own_share_max': XREF_OWN_SHARE_MAX, 'gap_min': XREF_GAP_MIN})
    if ok_x:                                                         # найденная непустая ссылка может нести план: доли — справка, не остановка
        rec.update(stop=False, why='есть найденная непустая ссылка (%s): план может лежать в ней — остановки нет, предупреждения остаются' %
                   ', '.join(r['name'] for r in ok_x))
        return
    if share > XREF_OWN_SHARE_MAX or gap < XREF_GAP_MIN:
        rec['stop'] = False
        return
    rec['stop'] = True
    pc = lambda v: ('%.0f' % (100 * v)).replace('.', ',') + ' %'
    what = '; '.join('«%s» (путь в чертеже: %s; %s; вставок в модель %d)' % (
        r['name'], r['path'] or 'не задан', ('искали рядом с исходником, в папке %s, по имени «%s» или оканчивающемуся на него — не нашли' % (
            r['searched'], os.path.basename((r['path'] or '').replace('\\', '/')) or '—') if r['found'] is None else
            'найден «%s», но %s' % (r['found'], r.get('empty'))), s['inserts'].get(r['name'], 0)) for r in bad)
    why = ('сам план лежит во внешней ссылке, которой нет или которая пуста: %s. Собственной геометрии у файла почти нет: своё — %s '
           'сущностей модели (%d из %d; вставок ссылок %d, рамка %d, штамп %d не считаются), порог %s; не занято своей геометрией %s '
           'габарита чертежа, порог %s.' % (what, pc(share), len(own), s['model_total'], n_xins, frame, stamp, pc(XREF_OWN_SHARE_MAX), pc(gap),
                                            pc(XREF_GAP_MIN)))
    ask = 'пришлите файл %s (внешняя ссылка), или DWG с внедрёнными ссылками (Bind/eTransmit)' % ', '.join('«%s»' % r['name'] for r in bad)
    notes.add('DWG_XREF_PLAN_MISSING')
    add_stop(rep, {'code': 'DWG_XREF_PLAN_MISSING', 'why': why, 'ask': ask})   # остановка по единицам уже есть — обе видны


def add_stop(rep, st):
    """v014 (ПРV-К1): остановка в rep.stop; если она уже есть — в rep.stop.also (видны все)"""
    if rep.get('stop'):
        rep['stop'].setdefault('also', []).append(st)
    else:
        rep['stop'] = st


def warn_detail(rep, code, text):
    """v014 (ПРV-К2, К5): подробность к предупреждению (путь, текст ошибки) — source_intake.intake() дописывает её к warnings[].what"""
    rep.setdefault('_warn_detail', {})[code] = text


def intake_cad(path, kind, out, rep, notes):
    """чертёж CAD → rep['cad'] и предупреждения. v014 (ПРV-К5): плохой UNS_DWG2DXF — DWG_CONVERTER_ENV_BAD с путём при любом исходе,
    и при исключении (его ловит source_intake.intake(), ПРV-К2)"""
    CONVERTER_ENV_BAD.clear()
    env_bad = []
    try:
        _intake_cad(path, kind, out, rep, notes, env_bad)
    finally:
        env_bad = sorted(set(env_bad + CONVERTER_ENV_BAD))
        if env_bad:
            rep.setdefault('cad', {})['converter_env_bad'] = env_bad
            notes.add('DWG_CONVERTER_ENV_BAD')
            warn_detail(rep, 'DWG_CONVERTER_ENV_BAD', '; '.join(env_bad))


def _intake_cad(path, kind, out, rep, notes, env_bad):
    rep['cad'] = cad = {}
    dxf = path
    if kind == 'dwg':
        cad['dwg_version'] = dwg_version(path)
        exe = find_converter()
        cad['converter_search'] = list(CONVERTER_SEARCH)
        env_bad.extend(CONVERTER_ENV_BAD)                        # v014 (ПРV-К5): поиск для ссылок ниже очищает список — сохранить
        if not exe:
            notes.add('DWG_NO_CONVERTER')
            rep['class'] = 'unsupported'
            rep['route'] = ADVICE['DWG_NO_CONVERTER']
            return
        dxf, cad['convert'] = convert(path, out, exe)
        if not dxf:
            notes.add('DWG_CONVERT_FAILED')
            rep['class'] = 'unsupported'
            rep['route'] = ADVICE['DWG_CONVERT_FAILED']
            return
    t0 = time.time()
    s = scan_dxf(dxf)
    cad['scan_secs'] = round(time.time() - t0, 1)
    cad['header'] = s['header']
    cad['entities_model'] = int(sum(s['ents_by_type'].values()))
    cad['types_top'] = s['ents_by_type'].most_common(12)
    cad['layers_used'] = len(s['ents_by_layer'])
    cad['layers_top'] = s['ents_by_layer'].most_common(25)
    blocks = {k: v for k, v in s['blocks'].items() if not k.lower().startswith(('*model_space', '*paper_space'))}
    in_blocks = sum(b['n'] for b in blocks.values())
    cad['blocks'] = {'defined': len(blocks), 'entities_in_blocks': in_blocks, 'inserts_model': int(sum(s['inserts'].values())),
                     'top': s['inserts'].most_common(15)}
    t1 = time.time()
    xrefs, xref_dxf, xsegs, xpts = resolve_xrefs(path, out, s, blocks, notes)     # внешние ссылки, если их файлы рядом
    cad['xrefs'] = xrefs[:20]
    xref_plan_check(s, blocks, xrefs, rep, notes, cad)           # v014 (ПР4, Б24): план во внешней ссылке, которой нет или которая пуста
    allsegs = np.vstack([s['segs'], expand_inserts(s, cap=max(0, MAX_SEGMENTS - len(s['segs'])))] + xsegs)
    cad['expand_secs'] = round(time.time() - t1, 1)
    vpts = np.vstack([s['pts'], np.asarray([(x, y) for x, y, *_ in s['ins_pts']], float).reshape(-1, 2)] + xpts)
    views, rng = find_views(allsegs, vpts, texts=s['texts'])
    for v in views:                                          # подписи этажа внутри вида
        x0, y0, x1, y1 = v['bbox']
        fl = set()
        for x, y, t in s['texts']:
            if x0 <= x <= x1 and y0 <= y <= y1 and len(t.split()) <= 6:
                fl |= set(floors_in(t))
        v['floors'] = sorted(fl)[:6]
    cad['views'] = views
    # v014 (ПРV-К1): модель пуста или почти пуста — видов нет или геометрии меньше MODEL_MIN_GEOM: остановка, work.pdf не строится
    xnames = {r['name'] for r in xrefs}
    geom_n = sum(1 for e in s['geom'] if not (e[0] == 'INSERT' and e[5] in xnames and e[5] not in xref_dxf)) + sum(
        r.get('entities') or 0 for r in xrefs if r['name'] in xref_dxf)
    model_empty = not views or geom_n < MODEL_MIN_GEOM
    if model_empty:
        cad['model_empty'] = {'geometry_entities': geom_n, 'model_entities': s['model_total'], 'view_points': int(len(vpts)), 'views': len(views),
                              'thresholds': {'model_min_geom': MODEL_MIN_GEOM, 'view_min_points': VIEW_MIN_POINTS}}
        notes.add('DWG_MODEL_EMPTY')
        add_stop(rep, {'code': 'DWG_MODEL_EMPTY',
                       'why': 'в пространстве модели плана нет или он почти пуст: сущностей геометрии %d (порог %d), точек сущностей для '
                              'видов %d (порог %d), всего сущностей модели %d, видов %d — work.pdf не построен.' % (
                                  geom_n, MODEL_MIN_GEOM, len(vpts), VIEW_MIN_POINTS, s['model_total'], len(views)),
                       'ask': 'DWG или DXF, где план лежит в пространстве модели (не только в листе Layout и не во внешней ссылке), '
                              'или PDF плана со слоями'})
    if len(views) >= 2 or any(len(v['floors']) >= 2 for v in views):     # видов несколько или в одном виде подписи разных этажей
        notes.add('DWG_MULTI_VIEW')
    # 1. единицы
    cad['units'] = unit_guess(s, views)
    if cad['units']['mismatch'] or (cad['units']['header'] is None and cad['units']['by_objects']):
        notes.add('DWG_UNITS')
    units_suspect(cad['units'], rep, notes)                       # v014 (ПР3, Б25)
    # 2. инженерный раздел
    tot = max(1, cad['entities_model'])
    eng_l = {k: n for k, n in s['ents_by_layer'].items() if ENG_RE.search(k)}
    arch_l = {k: n for k, n in s['ents_by_layer'].items() if ARCH_RE.search(k) and not ENG_RE.search(k)}
    eng_i = sum(n for k, n in s['inserts'].items() if ENG_RE.search(k))
    cad['engineering'] = {'share_layers': round(sum(eng_l.values()) / tot, 3), 'share_inserts': round(eng_i / max(1, sum(s['inserts'].values())), 3),
                          'layers_top': sorted(eng_l.items(), key=lambda kv: -kv[1])[:10], 'arch_share': round(sum(arch_l.values()) / tot, 3)}
    if cad['engineering']['share_layers'] > 1 / 3 or cad['engineering']['share_inserts'] > 1 / 4:
        notes.add('DWG_ENGINEERING')
    # 3. картинки и внешние ссылки
    base = os.path.dirname(os.path.abspath(path))
    missing = [p for p in s['imagedefs'] if not (os.path.exists(p) or os.path.exists(os.path.join(base, os.path.basename(p.replace('\\', '/')))))]
    cad['images'] = {'in_model': s['images'], 'files': len(s['imagedefs']), 'missing': len(missing), 'missing_sample': missing[:8]}
    if missing or (s['images'] and not s['imagedefs']):
        notes.add('DWG_IMAGES_MISSING')
    # 4. выгрузка из Revit
    rv = [k for k in blocks if REVIT_BLOCK_RE.search(k)]
    ratio = in_blocks / max(1, cad['entities_model'])
    cad['revit'] = {'family_blocks': len(rv), 'sample': rv[:6], 'blocks_to_model': round(ratio, 1)}
    if len(rv) >= 3:
        notes.add('DWG_FROM_REVIT')
    # И16: векторный PDF со слоями OCG — лист на вид; дальше — обычный маршрут листа CAD со слоями
    if views and not model_empty:
        try:
            import cad_pdf
            unit, sure = units_sure(cad['units'])
            note = '%s %s' % (cad.get('dwg_version', ('DXF', ''))[0], cad.get('dwg_version', ('', ''))[1])
            cad['pdf'] = info = cad_pdf.dxf_to_pdf(dxf, os.path.join(out, 'work.pdf'), views, cad_pdf.UNIT_MM.get(unit) if sure else None,
                                                   title=os.path.basename(path), creator_note=note, xrefs=xref_dxf)
            info['units'] = unit if sure else None
            if not sure:
                notes.add('DWG_SCALE_UNKNOWN')
            if sum(n for t, n in info.get('not_drawn', {}).items() if t in cad_pdf.SOLID_TYPES) >= 10:
                notes.add('DWG_3D_SOLIDS')
            dm = info.get('dims') or {}
            if dm.get('text_ne', 0) >= 10 and dm['text_ne'] >= 0.25 * dm.get('linear', 0):
                notes.add('DWG_DIM_OVERRIDE')
            import source_intake as _si                              # приём PDF — рендер, листы, слои, как у листа AutoCAD
            sub, sn = {}, set()
            _si.intake_pdf(os.path.join(out, 'work.pdf'), out, sub, sn)
            for key in ('pdf', 'render', 'chosen_page', 'chosen_by'):
                if key in sub:
                    rep[key] = sub[key]
            notes |= {c for c in sn if c in ('PDF_OCG', 'PDF_MULTIPAGE', 'PDF_PLAN_CANDIDATES', 'PDF_MULTI_FLOOR', 'PDF_WALLS_SHEET')}
            rep['_text_pdf'] = sub.pop('_text', '')
        except Exception as e:                                   # noqa: BLE001 — PDF не роняет приём: остаются DXF и превью
            cad['pdf_error'] = ('%s: %s' % (type(e).__name__, e))[:300]
            notes.add('DWG_PDF_FAILED')
        if 'DWG_PDF_FAILED' not in notes and not os.path.isfile(os.path.join(out, 'work.pdf')):   # v014 (ПРV-К1): «собран», а файла нет
            cad['pdf_error'] = 'work.pdf не записан'
            notes.add('DWG_PDF_FAILED')
        if 'DWG_PDF_FAILED' in notes:                            # v014 (ПРV-К1): work.pdf нет — остановка, не «успех»
            add_stop(rep, {'code': 'DWG_PDF_FAILED', 'why': 'векторный PDF из DXF не собран: %s — work.pdf нет.' % cad['pdf_error'],
                           'ask': 'PDF плана со слоями, напечатанный из AutoCAD, или DXF заново'})
    # превью модели
    seg = allsegs
    if rng is not None and len(seg):
        lo, hi = rng
        if views:                                                # превью — по рамкам видов с полем 5 %: разбросанные подписи не мельчат план
            vb = np.array([v['bbox'] for v in views], float)
            lo = np.array([vb[:, 0].min(), vb[:, 1].min()]); hi = np.array([vb[:, 2].max(), vb[:, 3].max()])
            pad = 0.05 * (hi - lo); lo, hi = lo - pad, hi + pad
        W = 2400; k = W / max(1e-9, hi[0] - lo[0]); H = max(50, int((hi[1] - lo[1]) * k) + 1)
        if H > 4000:
            k *= 4000 / H; W = max(50, int((hi[0] - lo[0]) * k) + 1); H = 4000
        im = Image.new('RGB', (W, H), 'white'); d = ImageDraw.Draw(im)
        X = lambda x: (x - lo[0]) * k
        Y = lambda y: H - (y - lo[1]) * k
        for a, b, c, e in seg[:MAX_SEGMENTS]:
            d.line([(X(a), Y(b)), (X(c), Y(e))], fill=(0, 0, 0), width=1)
        for x, y, *_ in s['ins_pts'][:200000]:
            d.point((X(x), Y(y)), fill=(220, 0, 0))
        for i, v in enumerate(views, 1):
            x0, y0, x1, y1 = v['bbox']
            d.rectangle([X(x0), Y(y1), X(x1), Y(y0)], outline=(0, 90, 230), width=3)
            d.text((X(x0) + 6, Y(y1) + 6), 'view %d' % i, fill=(0, 90, 230))      # шрифт Pillow по умолчанию — без кириллицы
        im.save(os.path.join(out, 'dxf_preview.png'))
        cad['preview'] = {'file': 'dxf_preview.png', 'size': [W, H], 'segments': int(min(len(seg), MAX_SEGMENTS))}
    rep['class'] = 'cad-dwg' if kind == 'dwg' else 'cad-dxf'
    if not os.path.isfile(os.path.join(out, 'work.pdf')) or model_empty or 'DWG_PDF_FAILED' in notes:
        rep['route'] = ROUTE_NO_PDF                              # v014 (ПРV-К1): маршрут не обещает work.pdf, которого нет
    rep['_text'] = '\n'.join(t for _, _, t in s['texts'][:5000])          # подписи модели — для паспорта (И1), в intake.json не пишутся


def md_lines(rep):
    """v014 (ПР3, Б25): раздел чертежа CAD для intake.md (вызывается из source_intake.to_md)."""
    c, L = rep.get('cad') or {}, ['', '**Чертёж CAD**', '', '| Что | Значение |', '|---|---|']
    if c.get('dwg_version'):
        L.append('| DWG | %s (%s)%s |' % (c['dwg_version'][0], c['dwg_version'][1], '; в DXF за %s с, %s байт' % (
            c['convert'].get('secs'), format(c['convert'].get('dxf_bytes', 0), ',').replace(',', ' ')) if c.get('convert') else ''))
    if c.get('converter_search') and not c.get('convert'):
        L.append('| Конвертер | не найден: %s |' % '; '.join(c['converter_search']))
    if c.get('converter_env_bad'):                               # v014 (ПРV-К5): плохая переменная — видно в intake.md, не только в json
        L.append('| Конвертер — UNS_DWG2DXF | %s; поиск: %s |' % ('; '.join(c['converter_env_bad']), '; '.join(c.get('converter_search') or []) or '—'))
    if c.get('read_error'):                                      # v014 (ПРV-К2)
        L.append('| Ошибка чтения | %s |' % c['read_error'].replace('|', '/'))
    try:                                                         # v014 (ПРV-К2): приём прерван ошибкой — сведения неполные, md всё равно пишется
        L += _md_model(c, rep)
    except (KeyError, TypeError, IndexError):
        L.append('| Модель | сведения неполные — приём прерван (cad.read_error) |')
    if rep.get('stop'):
        for st in [rep['stop']] + rep['stop'].get('also', []):                                   # v014 (ПР4, Б24): остановок может быть две
            L += ['', '**Остановка (%s):** %s Просить у клиента: %s' % (st['code'], st['why'], st['ask'])]
    return L


def units_header_md(c):
    """v014 (ПРV-К10): единицы шапки для intake.md: из словаря — имя; нет $INSUNITS или 0 — «не заданы»; другой код — «код N — не из словаря»"""
    u = c.get('units') or {}
    if u.get('header'):
        return u['header']
    raw = (c.get('header') or {}).get('$INSUNITS')
    if raw in (None, 0):
        return 'не заданы'
    return 'код %s%s — не из словаря приёма (%s)' % (raw, ' (%s)' % INSUNITS_OTHER[raw] if raw in INSUNITS_OTHER else '',
                                                      ', '.join(INSUNITS.values()))


def _md_model(c, rep):
    L = []
    if 'entities_model' in c:
        u = c['units']
        L += ['| Модель | сущностей %s, слоёв %s, блоков %s (в них %s сущностей), вставок %s |' % (
                  c['entities_model'], c['layers_used'], c['blocks']['defined'], c['blocks']['entities_in_blocks'], c['blocks']['inserts_model']),
              '| Единицы | в шапке — %s; по объектам — %s%s; признаки: %s |' % (units_header_md(c), u['by_objects'] or 'не определены',   # v014 (ПРV-К10)
                  ' (ничья: %s)' % ', '.join(u['tie']) if u.get('tie') else '',
                  ', '.join('%s %s' % (k, v) for k, v in u['evidence'].items()) or 'нет'),
              '| Виды в модели | %s |' % ('; '.join('%d: %s%s, %.0f %% сущностей' % (i, v['bbox'], ', этаж ' + ', '.join(map(str, v['floors']))
                  if v['floors'] else '', 100 * v['share']) for i, v in enumerate(c['views'], 1)) or 'нет — work.pdf не построен'),   # v014 (ПРV-К1): было «один»
              '| Инженерные системы | слои — %.0f %% сущностей, вставки — %.0f %%; архитектурные слои — %.0f %% |' % (
                  100 * c['engineering']['share_layers'], 100 * c['engineering']['share_inserts'], 100 * c['engineering']['arch_share']),
              '| Картинки и ссылки | картинок в модели %s, файлов %s, нет рядом %s; внешних ссылок %s |' % (
                  c['images']['in_model'], c['images']['files'], c['images']['missing'], len(c['xrefs'])),
              '| Revit | блоков-семейств %s; сущностей в блоках на одну в модели — %s |' % (c['revit']['family_blocks'], c['revit']['blocks_to_model'])]
        if u.get('suspect'):
            L.append('| Единицы — остановка | %s |' % u['suspect'])
        if c.get('model_empty'):                                 # v014 (ПРV-К1)
            me = c['model_empty']
            L.append('| Модель — остановка | плана нет или почти пусто: геометрии %s (порог %s), точек для видов %s (порог %s), видов %s — '
                     'work.pdf не построен |' % (me['geometry_entities'], me['thresholds']['model_min_geom'], me['view_points'],
                                                 me['thresholds']['view_min_points'], me['views']))
    return L
