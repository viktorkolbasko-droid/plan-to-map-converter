"""Э10 (owner 06.10.2026): the list of objects of the габаритный result — «распознать тип объекта и… габариты, внешний контур,
чтобы его можно было потом изъять из плана и заменить другим объектом». For every object that has an outline ('outline' of
Э7м v3): its type (key and name), layer (ISO 13567 element), the outline in DXF millimetres (the same origin as the DXF:
cfg.ORIGIN_PT, named by cfg.OCG_ORIGIN_NOTE, y up), the centre and the angle of its minimum rotated rectangle (the long side; 0° = along +x of the DXF), the
size (long × short side, mm), the block it is inserted as in the габаритный DXF, and for seats the group of one figure.
Reads objects.pkl, prims (load_prims), blocks_outline.pkl, furniture.json; writes objects_list.json (in the work folder and
in OUTDIR when set). usage: python3 e10_objects_list.py"""
import pickle, json, math, os, sys, collections
import numpy as np
from shapely.geometry import Polygon
import os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import sheet; from e7_comp import load_prims
K = sheet.K; OX, OY = sheet.OX, sheet.OY
def mm(p): return (round(K * p[0] - K * OX, 1), round(-K * p[1] + K * OY, 1))
P = load_prims()['P']; objs = pickle.load(open('objects.pkl', 'rb'))['objs']
BL = pickle.load(open('blocks_outline.pkl', 'rb')) if os.path.exists('blocks_outline.pkl') else dict(assign={}, blocks={})
# code 010 (К-1): МФУ and wall screens - A-82 (№106, №108, row 208)
EL = {'desk': 'A-82', 'chair': 'A-82', 'armchair': 'A-82', 'round': 'A-82', 'table': 'A-82', 'booth': 'A-82', 'mfp': 'A-82',
      'plant': 'A-89', 'equip': 'A-82', 'sink': 'A-73', 'san': 'A-74', 'counter': 'A-76', 'dtable': 'A-82', 'ctable': 'A-82',
      'storage': 'A-82', 'pedestal': 'A-82', 'rtable': 'A-82', 'mtable': 'A-82', 'sofa': 'A-82', 'kitchen': 'A-76', 'coreblock': 'A-221'}
TYPE_RU = {'desk': 'рабочее место (стол)', 'chair': 'кресло офисное', 'armchair': 'кресло мягкое', 'round': 'пуф или столик круглый',
           'table': 'стол или тумба', 'booth': 'кабина для звонков', 'mfp': 'МФУ', 'plant': 'растение', 'equip': 'оборудование',
           'sink': 'мойка', 'san': 'сантехника', 'counter': 'стойка', 'dtable': 'стол обеденный или переговорный', 'ctable': 'столик журнальный',
           'storage': 'стеллаж или шкаф', 'pedestal': 'тумба', 'rtable': 'стол круглый', 'mtable': 'стол переговорный', 'sofa': 'диван',
           'kitchen': 'кухня', 'coreblock': 'ядро: блок существующих конструкций (шахты, стены)'}
rows = []; cnt = collections.Counter()
for k, o in enumerate(objs):
    ol = o.get('outline')
    if not ol or not o['ids']: continue
    ring = [q for q in P[ol[0]]['p']] if P[ol[0]]['kind'] == 'fill' else [q for q in P[ol[-1]]['p']][:-1]
    if len(ring) < 3: continue
    pg = Polygon(ring).buffer(0)
    if pg.is_empty: continue
    r = pg.minimum_rotated_rectangle; c = np.array(r.exterior.coords)[:4]; e1, e2 = c[1] - c[0], c[2] - c[1]
    if np.linalg.norm(e2) > np.linalg.norm(e1): e1, e2 = e2, e1
    ang = math.degrees(math.atan2(-e1[1], e1[0])) % 180.0                     # y up in the DXF
    cen = pg.centroid.coords[0]
    row = dict(id=k, type=o['key'], type_ru=TYPE_RU.get(o['key'], o['key']), name=o.get('name', ''), layer=EL.get(o['key'], o.get('layer')),
               center_mm=list(mm(cen)), angle_deg=round(ang, 1), size_mm=[round(np.linalg.norm(e1) * K), round(np.linalg.norm(e2) * K)],
               area_m2=round(pg.area * K * K / 1e6, 3), outline_mm=[list(mm(q)) for q in ring])
    if k in BL['assign']: row['block'] = f"B{BL['assign'][k][0]:04d}_{BL['blocks'][BL['assign'][k][0]]['key']}"
    rows.append(row); cnt[o['key']] += 1
res = dict(about=f'Объекты габаритного результата: тип, внешний контур в мм DXF (начало {getattr(sheet.cfg, "OCG_ORIGIN_NOTE", "ORIGIN_PT")}, ось y вверх), центр, угол длинной стороны, '
                 'размер, блок вставки. Для замены объекта: удалить вставку блока и поставить другой объект в тот же центр и угол.',
           count=len(rows), by_type=dict(cnt.most_common()), objects=rows)
json.dump(res, open('objects_list.json', 'w'), ensure_ascii=False, indent=1)
if os.environ.get('OUTDIR'): json.dump(res, open(os.path.join(os.environ['OUTDIR'], 'objects_list.json'), 'w'), ensure_ascii=False, indent=1)
print('objects in the list', len(rows), dict(cnt.most_common()))
