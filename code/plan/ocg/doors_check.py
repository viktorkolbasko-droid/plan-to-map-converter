"""Doors (plan/rules/60 §1): hinge (centre of the door arc) <= 150 mm from a wall, partition, glass, column or facade."""
import pickle, json, math, numpy as np, shapely, collections, sys
from shapely.geometry import Point
from shapely.ops import unary_union
import os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import sheet; from e7_comp import geom
K = sheet.K; PT = sheet.pt
from e7_comp import load_prims; P = load_prims()['P']; O = pickle.load(open('objects.pkl', 'rb'))['objs']; from e7_comp import load_walls; W = load_walls()['bodies']
car = [g for _, g in W] + [geom(P[i]) for o in O if o['key'] in ('glass', 'lpart', 'facade', 'wallline', 'coreline', 'shaft', 'corezone') for i in o['ids']]
ct = shapely.STRtree(car)
rows = []
for o in O:
    if o['key'] != 'door' or 'деталь' in o['name']: continue
    best = None
    for i in o['ids']:
        q = np.array(P[i]['p'])
        if len(q) < 5: continue
        A = np.c_[2 * q[:, 0], 2 * q[:, 1], np.ones(len(q))]; c = np.linalg.lstsq(A, (q ** 2).sum(1), rcond=None)[0]
        r2 = c[2] + c[0] ** 2 + c[1] ** 2
        if r2 <= 0: continue
        r = math.sqrt(r2)
        if np.abs(np.hypot(q[:, 0] - c[0], q[:, 1] - c[1]) - r).max() > PT(0.3) or not (PT(5) <= r <= PT(40)): continue
        if best is None or r > best[2]: best = (c[0], c[1], r)
    if not best: continue
    h = Point(best[0], best[1]); dd = min((car[j].distance(h) for j in ct.query(h.buffer(PT(10)))), default=PT(99)) * K
    rows.append(dict(name=o['name'], hinge=(round(best[0], 1), round(best[1], 1)), d_mm=round(dd)))
bad = [r for r in rows if r['d_mm'] > 150]
json.dump(dict(doors=len(rows), ok=len(rows) - len(bad), bad=bad), open('doors_check.json', 'w'), ensure_ascii=False, indent=1)
print('doors with an arc', len(rows), '| hinge <= 150 mm from a carrier', len(rows) - len(bad), '| farther', len(bad))
for r in bad[:15]: print(r)
