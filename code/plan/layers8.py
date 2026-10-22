# layers8.py - code 008 (Т4-13, Т4-14): the table of DXF layers of the engineering plan (plan/rules/50 §1), one place for
#   export.py, the check of cfg at reading (cfgread.py) and the DXF check (verify.py, gate S14*).
#   - every layer a primitive uses is in the table, with a description (Т4-13): a pair '...H-' (fill) is made for every
#     '...E-' of the table - '<description of E> — заливка';
#   - texts lie on '...T-' and '...D-' only (Т4-14): «ПК...» - A-68----T-;
#   - a layer of cfg (MANUAL, MISC_GROUPS, COLOR_ELEMENTS) that is not in the table stops at reading (cfgread.py).
import collections
LAY=[
('A-91----E-','Отметки уровня: рамки вокруг отметки (по исходнику)',7,18),('A-68----T-','Пожарное оборудование — надписи (по исходнику)',7,18),
('A-21----E-','Стены наружные',7,50),('A-21----H-','Стены наружные — штриховка',8,13),
('A-221---E-','Стены внутренние капитальные',7,50),('A-221---H-','Стены внутренние капитальные — штриховка',8,13),
('A-222---E-','Перегородки каркасные (ГКЛ)',7,35),('A-222---H-','Перегородки каркасные — штриховка',8,13),
('A-223---E-','Перегородки из штучных материалов',7,35),('A-223---H-','Перегородки из штучных материалов — штриховка',8,13),
('A-22G---E-','Перегородки без штриховки в исходнике: стеклянные и лёгкие, остекление внутри офиса, турникеты и ограждения',4,25),
('A-23----E-','Проёмы в перекрытии: лестничные клетки и атриум — контур без заливки (решение владельца 03.10.2026)',6,35),('A-24----E-','Лестницы',7,25),
('A-28----E-','Колонны',7,50),('A-28----H-','Колонны — заливка',8,13),
('A-31----E-','Витражи и окна фасада',4,25),('A-32----E-','Двери и шторы в проёмах',3,25),
('A-52----E-','Водоотвод: решётки и трапы',5,25),('A-52----H-','Водоотвод — заливка',8,13),('A-53----E-','Водоснабжение: точки подключения воды (по исходнику)',5,25),('A-53----H-','Водоснабжение — заливка',8,13),('A-56----E-','Отопление: конвекторы',6,25),('A-56----H-','Отопление — заливка',8,13),('A-57----E-','Вентиляционное оборудование',6,25),
('A-61----E-','Электроснабжение: щиты',6,25),('A-66----E-','Лифты',7,25),('A-68----E-','Пожарное оборудование',1,25),
('A-72----E-','Ресепшн',30,25),('A-73----E-','Кухонное оборудование',30,25),('A-73----H-','Кухонное оборудование — заливка',8,13),
('A-74----E-','Сантехника и аксессуары санузлов',5,25),('A-74----H-','Сантехника — заливка',8,13),
('A-76----E-','Шкафы и стеллажи (встроенные/стационарные)',30,25),('A-76----H-','Шкафы и стеллажи — заливка',8,13),
('A-77----E-','Серверное оборудование',6,25),
('A-82----E-','Мебель передвижная',2,18),('A-82----H-','Мебель передвижная — заливка',8,13),
('A-89----E-','Озеленение',3,13),('A-89----H-','Озеленение — заливка',8,13),
('A-90----T-','Марки, названия помещений и надписи (по исходнику)',7,18),('A-91----T-','Отметки уровня (по исходнику)',7,18),('A-AX----E-','Оси координационные',8,18),('A-AX----T-','Марки осей',7,18),('A-AX----D-','Размеры по осям',7,18),('A-AXM---E-','Служебные метки по исходнику: «+», ⊕ (не объекты плана)',8,13),
('A-69----E-','Знаки у дверей (по исходнику; назначение неизвестно — см. «Неизвестное»)',3,18),('A-43----E-','Покрытия пола: ковры (по исходнику)',8,13),('A-43----H-','Ковры — заливка',8,13),('A-93----E-','Границы помещений: линии-разделители (по исходнику)',6,13),('A-00----E-','Не классифицировано (группы — в отчёте проверки 3.7)',8,13),('A-92----E-','Заливки помещений и зон (по исходнику) — контур',8,13),('A-92----H-','Заливки помещений и зон (по исходнику)',8,13),('A-00----H-','Не классифицировано — заливка',8,13),
('A-72----H-','Ресепшн — заливка',8,13),('A-23----H-','Атриум — заливка',8,13),('A-66----H-','Лифты — заливка',8,13),('A-68----H-','Пожарное оборудование — заливка',8,13),('A-24----H-','Лестницы — заливка',8,13),('A-31----H-','Витражи — заливка',8,13),('A-32----H-','Двери — заливка',8,13),('A-22G---H-','Перегородки — заливка',8,13),('A-61----H-','Электроснабжение — заливка',8,13),('A-77----H-','Серверное — заливка',8,13),('A-57----H-','Вентиляция — заливка',8,13),
]

_NAMES = [n for n, d, c, lw in LAY]
def table():
    """the layer table with the '...H-' pair of every '...E-': [(name, description, colour, lineweight)]"""
    out = list(LAY); have = set(_NAMES)
    for n, d, c, lw in LAY:
        if n.endswith('E-') and n[:-2] + 'H-' not in have:
            out.append((n[:-2] + 'H-', d + ' — заливка', 8, 13)); have.add(n[:-2] + 'H-')
    return out
NAMES = {n for n, d, c, lw in table()}
DESC = {n: d for n, d, c, lw in table()}
def text_layer_ok(name): return name.endswith('T-') or name.endswith('D-')
def cfg_layers(cfg):
    """[(field, record, layer)] of cfg records whose layer is not in the table"""
    bad = []
    for n, m in enumerate(getattr(cfg, 'MANUAL', []) or []):
        if len(m) > 2 and m[2] not in NAMES: bad.append(('MANUAL', n, m[2]))
    for n, g in enumerate(getattr(cfg, 'MISC_GROUPS', []) or []):
        if isinstance(g, dict) and g.get('layer') and g['layer'] not in NAMES: bad.append(('MISC_GROUPS', n, g['layer']))
    for n, e in enumerate(getattr(cfg, 'COLOR_ELEMENTS', []) or []):
        if isinstance(e, dict) and e.get('layer') and e['layer'] not in NAMES: bad.append(('COLOR_ELEMENTS', n, e['layer']))
    for n, f in enumerate(getattr(cfg, 'FAMILIES', []) or []):
        if len(f) > 2 and isinstance(f[2], str) and f[2] not in NAMES: bad.append(('FAMILIES', n, f[2]))
    return bad
def dxf_layers(doc):
    """layers the primitives of the model and of the block definitions use: not in the layer table, without a
    description; texts (TEXT, MTEXT) off '...T-' / '...D-' (Т4-13, Т4-14)"""
    used = collections.Counter(); texts = collections.Counter()
    def scan(es, where):
        for e in es:
            L = e.dxf.layer; used[(L, where)] += 1
            if e.dxftype() in ('TEXT', 'MTEXT') and not text_layer_ok(L): texts[L] += 1
    scan(doc.modelspace(), 'model')
    for b in doc.blocks:
        if b.name.startswith('*'): continue
        scan(b, 'block')
    have = {l.dxf.name: (l.description or '') for l in doc.layers}
    names = sorted({L for L, w in used if L != '0'})
    return dict(used=names, unrecorded=[L for L in names if L not in have], no_description=[L for L in names if L in have and not have[L].strip()],
                texts_off_TD=dict(texts))
