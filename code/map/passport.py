"""Паспорт исходника (И1; черновик чата исходников, 07.10.2026): профиль П01–П16 по признакам файла и короткая сводка
для первого ответа — программа, слои, опора масштаба, язык подписей, качество, что вырезать, что попросить у клиента,
ссылка на строку кэша профилей `ref/core/20-профили-исходников.md`.

Профиль — как сделан файл (формат, программа, вектор или растр). Где профиль решает содержание — растр: чертёж, карта, фото,
БТИ, эскиз, — паспорт даёт кандидатов и пишет «по содержанию — глазами». Правила — те же, что у каталога «12»
(`00-каталог-исходников-maps-design__v003`): программа — по creator, producer и title; профиль — по классу приёма и программе.
v014 (17.10.2026, ПР6, И1): перенесён в код карты из черновика 0816 с тремя правками — эскиз (П13) — по PDF_FEW_LINES приёма v011+
(у черновика — PDF_SPARSE); LOWRES_RASTER не читается (в v014 его нет: новых порогов в px нет, И2/Б21-остаток);
PDF под паролем (класс pdf-encrypted) — профиль не определяется (у черновика выходил П05), просьба «PDF без пароля».
v014 (ПРV-Т10, 17.10.2026): при остановке приёма (rep.stop, в том числе stop.also) — её просьба (stop.ask) первой в «Попросить у
клиента», строка «Остановка» в паспорте; остановка по единицам (DWG_UNITS_SUSPECT) — единицы шапки не выдаются за опору масштаба:
«шапка под сомнением»."""
import re

PROFILES = {
    'П01': 'Исходник CAD: DWG', 'П02': 'Вектор AutoCAD', 'П03': 'Вектор ArchiCAD', 'П04': 'Вектор прочих CAD: nanoCAD, CET и др.',
    'П05': 'Вектор, «печать в PDF», программа неизвестна', 'П06': 'Вектор дизайна: SVG, PDF из графредактора', 'П07': 'PDF-скан',
    'П08': 'PDF смешанный и составной', 'П09': 'Растр: скриншот или экспорт чертежа', 'П10': 'Растр: дизайн-планировка, готовая карта, брошюра',
    'П11': 'Фото плана на бумаге или экране', 'П12': 'План БТИ', 'П13': 'Эскиз и простая схема', 'П14': 'Документ Office: PPTX, DOCX, XLSX, VSDX',
    'П15': 'Не план', 'П16': 'Вектор Revit'}
CACHE = 'ref/core/20-профили-исходников.md'
# программа по creator | producer | title — порядок важен (как у каталога «12», плюс Keynote, Photoshop, Affinity, Inkscape)
PROGRAMS = [('revit', 'Revit'), ('.rvt', 'Revit'), ('pdfplot', 'AutoCAD'), ('autocad', 'AutoCAD'), ('dwg to pdf', 'AutoCAD'),
            ('archicad', 'ArchiCAD'), ('gspublisher', 'ArchiCAD'), ('oda pdf', 'nanoCAD/ODA'), ('nanocad', 'nanoCAD/ODA'), ('gcad', 'nanoCAD/ODA'),
            ('cet', 'CET Designer'), ('corel', 'CorelDRAW'), ('.cdr', 'CorelDRAW'), ('visio', 'Visio'), ('illustrator', 'Illustrator'),
            ('indesign', 'Illustrator'), ('figma', 'Figma'), ('keynote', 'Keynote'), ('affinity', 'Illustrator'), ('inkscape', 'Illustrator'),
            ('photoshop', 'Photoshop'), ('word', 'Office'), ('powerpoint', 'Office'), ('excel', 'Office'), ('publisher', 'Office'),
            ('canon', 'сканер/МФУ'), ('xerox', 'сканер/МФУ'), ('versalink', 'сканер/МФУ'), ('contentreader', 'сканер/МФУ'), ('\\scan', 'сканер/МФУ'),
            ('remplanner', 'Remplanner'), ('google', 'Google')]
PRINTERS = ('print to pdf', 'pscript', 'pdf24', 'ghostscript', 'macos', 'quartz', 'dopdf', 'pdfium', 'cairo', 'ios version')
RESAVERS = ('ilovepdf', 'sambox', 'pdfsam', 'pdftron', 'pdftk', 'smallpdf', 'pdftools', 'cloudconvert', 'hummus', 'pdflib', 'acrobat', 'adobe psl',
            'distiller', 'pdf squeezer', 'adobe pdf library')
CAD = {'AutoCAD', 'ArchiCAD', 'nanoCAD/ODA', 'CET Designer', 'Revit', 'Remplanner', 'CAD (вероятно)'}
DESIGN = {'Illustrator', 'CorelDRAW', 'Visio', 'Office', 'Google', 'Figma', 'Keynote'}
# семейства имён слоёв (как у профилей v002)
L_AIA = re.compile(r'^\s*([AGISMEPLC])-[A-Z]{3,4}', re.I)
L_REV = re.compile(r'Обобщенн|Общие ребра|Штриховка разреза|Марки (вырез|помещ)|Каркас_Импост|Элементы узлов|^Перекрыти|Generic Models|Curtain (Wall|Panel)'
                   r'|Room Separation|Линии подступенков|Линии свеса|_Сверху_', re.I)
L_NUM = re.compile(r'^\d\d[_\s.]')
L_RU = re.compile(r'стен|перегор|двер|окн|мебел|колон|оси\b|размер|текст|штрих|помещ|сантех|лестн|оборуд', re.I)
T_SCALE = re.compile(r'(?:\bМ|\bM|масштаб|scale)?\s*1\s*[:/]\s*(25|50|75|100|125|150|200|250|300|400|500|1000)\b', re.I)
T_DIM = re.compile(r'(?<![\d.,])(?:[1-9]\d{3}|[1-9]\d{4})(?![\d.,])')
T_STAMP = re.compile(r'\b(Изм\.?|Лист|Листов|Стадия|Разраб|Пров\.?|Н\.\s?контр|Формат|ГИП|Sheet\s*No|Drawn\s*by|Checked|Revision)\b', re.I)
T_LEGEND = re.compile(r'(Условные\s+обозначения|Экспликация|Легенда|Legend|Explication|Key\s*plan)', re.I)
T_BTI = re.compile(r'(БТИ|Мосгор|ГБУ|Поэтажный\s+план|технический\s+паспорт|Ростехинвентаризация)', re.I)


def program_of(producer, creator, title):
    s = ('%s | %s | %s' % (creator or '', producer or '', title or '')).lower()
    for k, v in PROGRAMS:
        if k in s:
            return v
    if 'модель' in s or s.strip().endswith('model') or 'layout1' in s or '| model' in s:
        return 'CAD (вероятно)'
    if any(k in s for k in PRINTERS):
        return 'печать в PDF'
    if any(k in s for k in RESAVERS):
        return 'пересохранён / неизвестно'
    return 'неизвестно'


def layer_family(names):
    n = [x for x in (names or []) if x]
    if not n:
        return 'нет слоёв'
    fam = []
    if sum(1 for x in n if L_AIA.match(x)) >= 3: fam.append('AIA/NCS')
    if sum(1 for x in n if L_REV.search(x)) >= 2: fam.append('категории Revit')
    if sum(1 for x in n if L_NUM.match(x)) >= 3: fam.append('нумерованные группы (01_…)')
    if sum(1 for x in n if L_RU.search(x)) >= 2: fam.append('русские слова')
    return ', '.join(fam) if fam else 'технические/непонятные'


def text_facts(t):
    t = t or ''
    cyr = len(re.findall(r'[А-Яа-яЁё]', t)); lat = len(re.findall(r'[A-Za-z]', t))
    return {'chars': len(t.strip()), 'cyr': cyr, 'lat': lat, 'scale': sorted(set(T_SCALE.findall(t)))[:5], 'dims': len(T_DIM.findall(t)),
            'stamp': len(T_STAMP.findall(t)), 'legend': len(T_LEGEND.findall(t)), 'bti': len(T_BTI.findall(t))}


def lang_of(tf):
    if tf['cyr'] > 1.5 * tf['lat']: return 'по-русски'
    if tf['lat'] > 1.5 * tf['cyr']: return 'по-английски'
    return 'по-русски и по-английски' if tf['chars'] > 40 else 'текста нет'


def passport(rep, text=''):
    """rep — отчёт приёма (intake.json до записи); text — текст выбранной страницы PDF или подписи DWG. -> dict"""
    kind, cls = rep.get('kind'), rep.get('class')
    warns = set(w['code'] if isinstance(w, dict) else w for w in rep.get('warnings', []))
    p = rep.get('pdf') or {}; cad = rep.get('cad') or {}; ras = rep.get('raster') or {}
    tf = text_facts(text)
    out = {'profile': None, 'candidates': [], 'by': 'файл', 'program': None, 'layers': None, 'scale_support': None,
           'labels': lang_of(tf), 'quality': [], 'cut': [], 'ask_client': [], 'look': []}
    # программа и профиль
    if kind in ('dwg', 'dxf'):
        out['program'] = 'AutoCAD DWG' if kind == 'dwg' else 'DXF'
        prof = 'П01'
    elif kind == 'svg':
        out['program'] = 'SVG'; prof = 'П06'
    elif kind == 'office':
        out['program'] = 'Office'; prof = 'П14'
    elif kind == 'pdf':
        prog = program_of(p.get('producer'), p.get('creator'), p.get('title'))
        out['program'] = prog
        if cls == 'pdf-encrypted':                               # v014 (ПР6, И1): под паролем — признаков нет, профиль не П05
            prof = None; out['by'] = 'PDF под паролем — профиль после файла без пароля'
        elif cls == 'pdf-scan':
            prof = 'П07'
        elif cls in ('pdf-mixed', 'pdf-composite'):
            prof = 'П08'
        elif cls == 'pdf-empty':
            prof = None; out['candidates'] = ['П13', 'П15']; out['by'] = 'содержание — глазами'
        elif 'PDF_FEW_LINES' in warns:                            # v014 (ПР6, И1): эскиз — PDF_FEW_LINES приёма v011+ (черновик: PDF_SPARSE)
            prof = 'П13'
        elif prog == 'Revit' or p.get('revit_sign'):
            prof = 'П16'
        elif prog == 'AutoCAD':
            prof = 'П02'
        elif prog == 'ArchiCAD':
            prof = 'П03'
        elif prog in CAD:
            prof = 'П04'
        elif prog in DESIGN:
            prof = 'П06'
        else:
            prof = 'П05'
        if tf['bti'] >= 2 and prof in ('П05', 'П07', 'П08'):
            out['candidates'] = [prof, 'П12']; out['look'].append('в тексте листа — слова БТИ: если это поэтажный план БТИ — профиль П12')
    elif kind in ('png', 'jpeg', 'gif', 'tiff', 'bmp', 'webp', 'heic'):
        out['program'] = 'растр'
        prof = None; out['by'] = 'содержание — глазами'
        out['candidates'] = ['П11'] + ['П09', 'П10', 'П12', 'П13'] if 'PHOTO' in warns else ['П09', 'П10', 'П11', 'П12', 'П13']
        out['look'].append('что нарисовано: чертёж — П09, дизайн-планировка или готовая карта — П10, фото — П11, БТИ — П12, эскиз — П13, не план — П15')
    else:
        prof = 'П15' if cls == 'unsupported' else None
        out['program'] = kind
    out['profile'] = prof
    if prof and not out['candidates']:
        out['candidates'] = [prof]
    # слои
    if kind == 'pdf':
        names = p.get('ocg') or []
        out['layers'] = {'count': len(names), 'family': layer_family(names)}
    elif cad.get('layers_top'):
        names = [n for n, _ in cad['layers_top']]
        out['layers'] = {'count': cad.get('layers_used'), 'family': layer_family(names)}
    # опора масштаба
    vector = cls in ('pdf-vector', 'pdf-mixed', 'svg') or kind in ('dwg', 'dxf')
    stops = ([rep['stop']] + list(rep['stop'].get('also') or [])) if isinstance(rep.get('stop'), dict) else []   # v014 (ПРV-Т10)
    stop_codes = [st.get('code') for st in stops]
    if kind in ('dwg', 'dxf'):
        u = cad.get('units') or {}; cp = cad.get('pdf') or {}
        out['scale_support'] = 'вектор CAD: единицы — %s%s' % (u.get('by_objects') or u.get('header') or 'не определены',
                                                                 '' if not u.get('mismatch') else ' (в шапке — %s)' % u.get('header'))
        if 'DWG_UNITS_SUSPECT' in stop_codes:                    # v014 (ПРV-Т10): остановка по единицам — шапка не опора
            out['scale_support'] = ('вектор CAD: единицы не определены — шапка под сомнением (в шапке — %s; остановка DWG_UNITS_SUSPECT, '
                                    'intake.md, «Остановка»): масштаб — не по шапке и не по габариту' % (u.get('header') or 'не заданы'))
        elif cp.get('mm_per_pt'):
            out['scale_support'] += '; work.pdf — %.2f мм/pt' % cp['mm_per_pt']
        elif cp:
            out['scale_support'] += '; единицы не уверены — масштаб work.pdf не известен: по размерам на листе'
    elif vector and (tf['dims'] >= 8 or tf['scale']):
        out['scale_support'] = 'размеры или масштаб на листе%s' % (' (1:%s)' % ', 1:'.join(tf['scale']) if tf['scale'] else ', чисел-размеров %d' % tf['dims'])
    elif vector:
        out['scale_support'] = 'размеров на листе нет — по мебели и дверям (map/rules/30 §2)'
    elif tf['scale']:
        out['scale_support'] = 'масштаб в тексте 1:%s — проверить по мебели' % ', 1:'.join(tf['scale'])
    else:
        out['scale_support'] = 'по мебели и дверям (map/rules/30 §2)'
    # качество
    if ras:
        side = max(ras.get('work_size') or ras.get('size') or [0])
        out['quality'].append('растр %d px%s' % (side, ', JPEG ≈ %s' % ras['jpeg_quality'] if ras.get('jpeg_quality') else ''))
    n = rep.get('native') or {}
    if n.get('dpi'):
        out['quality'].append('скан %s dpi%s' % (n['dpi'], ', JPEG ≈ %s' % n['jpeg_quality'] if n.get('jpeg_quality') else ''))
    for code, what in (('PDF_FLATTENED', '«распечатанный» вектор'), ('SMALL_RASTER', 'меньше 1000 px — первая оценка'),
                       ('RASTER_1280', '1280 px — после мессенджера'), ('JPEG_LOWQ', 'JPEG сильно сжат'), ('PDF_SCAN_LOWQ', 'JPEG скана сильно сжат'),
                       ('PDF_LOWRES_SCAN', 'скан ниже 150 dpi'), ('DARK_BACKGROUND', 'тёмный фон'), ('PHOTO', 'снимок камеры')):
        if code in warns:
            out['quality'].append(what)
    # что вырезать и выбрать
    if tf['stamp'] >= 2: out['cut'].append('штамп')
    if tf['legend']: out['cut'].append('легенду или экспликацию')
    if 'PDF_PLAN_CANDIDATES' in warns or 'PDF_MULTIPAGE' in warns: out['cut'].append('выбрать лист (intake.md, «Листы-планы»)')
    if warns & {'PDF_MULTI_FLOOR', 'DWG_MULTI_VIEW'}: out['cut'].append('этаж или вид — каждый отдельной картой')
    # что попросить у клиента
    ask = out['ask_client']
    if warns & {'RASTER_1280', 'SMALL_RASTER'}: ask.append('оригинал файлом, а не картинку из мессенджера')
    if warns & {'PDF_LOWRES_SCAN', 'PDF_SCAN_LOWQ'}: ask.append('скан от 300 dpi или исходный PDF')
    if 'DWG_NO_CONVERTER' in warns or 'DWG_CONVERT_FAILED' in warns: ask.append('PDF из той же модели со слоями')
    if 'DWG_IMAGES_MISSING' in warns: ask.append('файлы вставленных картинок или PDF')
    if 'DWG_XREF' in warns: ask.append('файлы внешних ссылок или PDF целиком')
    if warns & {'PDF_PLAN_CANDIDATES', 'PDF_MULTI_FLOOR', 'DWG_MULTI_VIEW'}: ask.append('какие этажи и какой вариант рисовать')
    if prof == 'П06': ask.append('размер одного помещения; есть ли чертёж под картой')
    if prof == 'П13': ask.append('план здания, если есть')
    if 'П11' in out['candidates'][:1]: ask.append('скан или PDF вместо фото')
    if prof == 'П15': ask.append('план этажа')
    if cls == 'pdf-encrypted': ask.append('PDF без пароля')     # v014 (ПР6, И1)
    if stops:                                                    # v014 (ПРV-Т10): просьба остановки — первой; опора — intake.md, «Остановка»
        ask[:0] = ['%s (остановка %s)' % (st['ask'], st.get('code')) for st in stops if st.get('ask')]
        out['stop'] = stop_codes
    # ссылка на кэш
    if prof == 'П16':
        out['cache_ref'] = 'профиль одного клиента — правила plan/ целиком (plan/00)'
    elif prof:
        out['cache_ref'] = '%s, «## %s»' % (CACHE, prof)
    else:
        out['cache_ref'] = ('%s — профиль по содержанию: %s' % (CACHE, ', '.join(out['candidates'])) if out['candidates']
                            else '%s — %s' % (CACHE, out['by']))   # v014 (ПР6, И1): кандидатов нет (PDF под паролем)
    out['profile_name'] = PROFILES.get(prof) if prof else None
    return out


def to_md(ps):
    """раздел «Паспорт исходника» для intake.md"""
    if not ps:
        return []
    prof = (('%s %s' % (ps['profile'], ps['profile_name'])) if ps['profile'] else
            'по содержанию — глазами: ' + ', '.join(ps['candidates']) if ps['candidates'] else ps['by'])   # v014 (ПР6, И1): без кандидатов — причина
    L = ['', '## Паспорт исходника', '', '| Что | Значение |', '|---|---|',
         '| Профиль | %s%s |' % (prof, ' (кандидаты: %s)' % ', '.join(ps['candidates']) if ps['profile'] and len(ps['candidates']) > 1 else ''),
         '| Строка кэша профилей | %s |' % ps['cache_ref'],
         '| Программа | %s |' % (ps['program'] or '—')]
    if ps['layers']:
        L.append('| Слои | %s, %s |' % (ps['layers']['count'], ps['layers']['family']))
    L += ['| Опора масштаба | %s |' % ps['scale_support'], '| Подписи | %s |' % ps['labels'],
          '| Качество | %s |' % ('; '.join(ps['quality']) or '—'), '| Вырезать и выбрать | %s |' % ('; '.join(ps['cut']) or '—'),
          '| Попросить у клиента | %s |' % ('; '.join(ps['ask_client']) or '—')]
    if ps.get('stop'):                                           # v014 (ПРV-Т10)
        L.append('| Остановка | %s — приём остановлен: опора — intake.md, «Остановка» |' % ', '.join(c or '—' for c in ps['stop']))
    if ps['look']:
        L.append('| Посмотреть глазами | %s |' % '; '.join(ps['look']))
    return L
