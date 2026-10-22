# ocg/sheet.py - code 009 (package 3): the sheet of the layer route. Everything the module ocg/ knows about one sheet comes
#   from the floor's cfg.py and the sheet's layer table in it: the names of the source layers, the colours of glass and of
#   desk tops, the layers of "elements of another kind" (ELEM_L), the scale and the origin, the sheet title box. The code
#   of ocg/ has no name of a layer, no colour and no scale of one sheet (core/rules/10 §1, п. 7; plan/rules/70, rule 28).
#
#   The mechanism "layer -> class": every source layer of the sheet (an OCG layer, name without OCG_LAYER_PREFIX) has a
#   record in cfg.OCG_LAYERS with its ROLE - what the steps of the route do with its primitives (the vocabulary below) - and
#   the class rows of the sheet's layer table (part of the layer -> class -> key -> ISO layer), as the table was made by
#   the render of every layer alone (plan/00, step 1). A step asks for the layers of a role: L('wall'), ids_of(by, 'door').
#   A new sheet: its layer table -> `python3 ocg/table2cfg.py table.json` -> the records with the roles guessed from the
#   keys; a role the tool cannot guess stays None, and the first step of the route (ocg/start_ocg.py) stops on it.
#
#   Thresholds of the steps in pt were set on one sheet at REF_MM_PER_PT = 48.04 mm/pt <one example: client-b, floor
#   40> - a property of the code (code 010, К-3, ПК3-П6, ПК3-П11: cfg.OCG_REF_MM_PER_PT and cfg.OCG_SCALE_TOL are gone,
#   start_ocg.py stops a cfg that still has them). A sheet more than 2 % off is read as its copy at 48.04 mm/pt made from
#   the source (norm.py; cfg.SHEET_MM_PER_PT - the scale of the sheet itself, cfg in pt of the copy): every threshold in pt
#   holds as it was set. Within 2 % the sheet goes as it is and pt(v) converts the thresholds that use it (v x REF / K).
#   A sheet off the band without SHEET_MM_PER_PT runs only with cfg.OCG_SCALE_OK - a reason of the closed list.
import os, sys, importlib.util

ROLES = {   # role of a source layer -> what the route does with it (step that reads the role)
    'wall':         'перегородки и стены с телом: штриховка, контур, стекло (заливки цвета OCG_GLASS_COLORS) — тела стен Э6, Э6в, Э6г, Э7, Э7с',
    'core':         'капитальные стены ядра: чёрные заливки — колонны и торцы, линии — контур ядра (Э6, Э7, Э7я)',
    'core_lines':   'линии контура блоков ядра и стоек (Э7, Э7с, Э7я)',
    'core_hatch':   'штриховка зоны ядра (тёмная) и стойки (серые заливки) (Э7)',
    'shaft':        'контур шахт (Э7)',
    'lift':         'лифты: кабина, рама (Э7)',
    'door':         'двери: дуга, полотно, коробка (Э6г, Э7, Э7д)',
    'facade_frame': 'витраж фасадный: рама и стойки (Э7)',
    'facade_glass': 'витраж фасадный: остекление (Э7)',
    'heating':      'конвекторы (Э7)',
    'fire':         'пожарные шкафы (Э7)',
    'equipment':    'оборудование: экраны и их зоны (Э6г, Э7)',
    'furniture':    'мебель: столы, кресла, МФУ, кабины (Э3, Э7, Э7м)',
    'plant':        'растения (Э7)',
    'sanitary':     'сантехника (Э7)',
    'sink':         'мойки: чаша, слив, смеситель (Э7)',
    'tag':          'марки помещений — кружки (Э7)',
    'zone':         'заливки зон помещений (Э5, Э7)',
    'roomsep':      'линии-разделители помещений (Э7)',
    'dim':          'размеры (Э3, Э7)',
    'axis':         'оси здания (Э3, Э7)',
    'mark':         'служебные метки «+» (Э7)',
    'measure':      'линии обмеров (Э7)',
    'text':         'надписи (Э7: без объекта)',
    'empty':        'пустой слой (только отрезки нулевой длины)',
}
# roles whose lines are not wall linework in Э6 (furniture, annotation, core marks): category F of e6_walls.py
NONWALL_ROLES = ('furniture', 'plant', 'text', 'zone', 'axis', 'dim', 'tag', 'mark', 'core_hatch', 'shaft', 'core_lines', 'roomsep')
# roles of compact objects of another kind (Э6: their outlines are not wall linework; hull — footprint by the hull)
OBJ_ROLES = ('fire', 'equipment', 'sanitary', 'door', 'heating', 'sink', 'facade_frame', 'facade_glass')
HULL_ROLES = ('fire', 'equipment', 'sanitary', 'sink', 'heating')


def _load_cfg():
    p = os.path.join(os.getcwd(), 'cfg.py')
    if not os.path.exists(p): sys.exit('ocg: нет cfg.py в папке этажа ' + os.getcwd())
    sp = importlib.util.spec_from_file_location('cfg', p); m = importlib.util.module_from_spec(sp); sp.loader.exec_module(m)
    return m


cfg = _load_cfg()
PDF = getattr(cfg, 'PDF', None)
SRC_PDF = PDF                                                        # the source sheet (sheetcheck.py reads it)
OUT = getattr(cfg, 'OUT', 'plan')
TITLE = getattr(cfg, 'TITLE', OUT)
PREFIX = getattr(cfg, 'OCG_LAYER_PREFIX', '')
TABLE = list(getattr(cfg, 'OCG_LAYERS', []) or [])
ROLE_OF = {}
ORDER = []                                   # layers in the order of the table
for r in TABLE:
    if r['layer'] not in ROLE_OF: ORDER.append(r['layer'])
    ROLE_OF.setdefault(r['layer'], r.get('role'))
K = float(getattr(cfg, 'MM_PER_PT', 0) or 0)                       # mm per pt of the sheet (Э3 measures it, start_ocg.py compares)
OX, OY = tuple(getattr(cfg, 'ORIGIN_PT', (0.0, 0.0)))              # origin of the DXF in pt (plan/rules/50 §1)
SHEET_BOXES = [tuple(b) for b in getattr(cfg, 'SHEET_BOXES', [])]   # texts inside are the sheet's, not the plan's
GLASS = {tuple(float(v) for v in c) for c in getattr(cfg, 'OCG_GLASS_COLORS', [])}
DESK_TOP = tuple(getattr(cfg, 'OCG_DESK_TOP', (None, None, None)))  # fill of a desk top as the source draws it
TOP_DRAW = tuple(getattr(cfg, 'OCG_TOP_DRAW', ()))                  # the light top as the source shows it (fill x opacity over white)
ELEM_L = set(getattr(cfg, 'OCG_ELEM_L', []))                        # Э6в: layers of elements of another kind that explain an irregularity
RASTER_ROLES = tuple(getattr(cfg, 'OCG_RASTER_ROLES', ()))          # Э5: roles of the layers that hold raster patches
RENDER_BOX = getattr(cfg, 'OCG_RENDER_BOX', None)                   # Э2: the part of the page the layer renders show
SCALE_DESK = getattr(cfg, 'OCG_SCALE_DESK', None)                   # Э3, way B: dict(label='140x90', mm=(1400, 900))
ORIGIN_AXES = tuple(getattr(cfg, 'OCG_ORIGIN_AXES', ()))            # Э3: (axis across, axis 1, axis 2) - names of the axes at the origin
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); import norm as _norm
REF_MM_PER_PT = _norm.REF['ocg']                                    # code 010: scale at which the pt thresholds were set - not from cfg
SHEET_MM_PER_PT = float(getattr(cfg, 'SHEET_MM_PER_PT', 0) or 0) or None   # code 010: the scale of the source sheet itself
NORM_K = _norm.factor(SHEET_MM_PER_PT, 'ocg')                         # 1 within 2 % of REF; else the copy is the sheet x NORM_K
if NORM_K != 1.0 and PDF and os.path.exists(PDF):
    PDF = _norm.ensure_copy(PDF, NORM_K, 'ocg')                     # every step reads the copy at REF mm/pt
F = (REF_MM_PER_PT / K) if K else 1.0


def pt(v):
    """a threshold set in pt on the reference sheet -> pt of this sheet (exactly v on the reference sheet)"""
    return v * F


def L(*roles):
    """source layers (names without the prefix) of the given roles"""
    return frozenset(l for l in ORDER if ROLE_OF.get(l) in roles)


def L1(role):
    """the first layer of a role (a step that adds primitives of the role puts them on it); '' when the sheet has none"""
    return next((l for l in ORDER if ROLE_OF.get(l) == role), '')


def full(*roles):
    """full OCG names (with the prefix) of the layers of the roles"""
    return frozenset(PREFIX + l for l in L(*roles))


def ids_of(by_layer, role):
    """primitive ids of a role from a {layer: [ids]} index, layers in the order of the table"""
    out = []
    for l in ORDER:
        if ROLE_OF.get(l) == role: out += by_layer.get(l, [])
    return out


def strip(name):
    return (name or '').replace(PREFIX, '', 1) if PREFIX and (name or '').startswith(PREFIX) else (name or '')


def iso_of_layer(layer):
    """ISO layers of the class rows of a source layer (documentation of the table; the steps decide by role and key)"""
    return sorted({r.get('iso') for r in TABLE if r['layer'] == layer and r.get('iso')})
