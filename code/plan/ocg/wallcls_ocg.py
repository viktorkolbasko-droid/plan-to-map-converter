# ocg/wallcls_ocg.py - code 009: ТП3 (client-b, test 5; plan/rules/40 §12): the class of the lines of the wall layers.
#   A line of a layer of the walls (roles 'wall' and 'core' of cfg.OCG_LAYERS) that the result draws, lying along a wall body
#   (>= 60 % of its length within 0.6 pt of the body's outline), but not in the class of that body - a light partition
#   (lpart), a wall line or a core line - is a stop of the gate (test 2 delivered 631 such objects and no check saw them).
#   The line of a body that the body itself owns ('wall:j') or that a glass pane, a door, a core block owns is not counted.
#   Final state: prims_c.pkl > ... (load_prims), objects.pkl, walls_j.pkl (load_walls).
#   python3 wallcls_ocg.py out.json        (floor folder)
import os, sys, json, pickle, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sheet
import shapely
from shapely.ops import unary_union
from e7_comp import geom, load_prims, load_walls
K = sheet.K
P = load_prims()['P']; O = pickle.load(open('objects.pkl', 'rb')); objs = O['objs']; owner = O.get('owner', {})
W = load_walls()['bodies']
WL = sheet.L('wall', 'core')
LINE_KEYS = ('lpart', 'wallline', 'coreline')          # classes of lines that are not a body
BB = [g.boundary.buffer(sheet.pt(0.6)) for _, g in W]; bt = shapely.STRtree(BB)
rows = []; seen = collections.Counter()
for k, o in enumerate(objs):
    if o['key'] not in LINE_KEYS: continue
    for i in o.get('draw', o['ids']):
        p = P[i]
        if p['kind'] != 'line' or p['layer'] not in WL or len(p['p']) < 2: continue
        g = geom(p); L_ = g.length
        if L_ <= 0: continue
        js = list(bt.query(g))
        if not js: continue
        along = {j: g.intersection(BB[j]).length for j in js}
        j = max(along, key=along.get)
        if along[j] >= 0.6 * L_:
            seen[o['key']] += 1
            rows.append(dict(prim=i, obj=k, key=o['key'], body_class=W[j][0], length_mm=round(L_ * K), along=round(along[j] / L_, 2),
                             at=[round(v, 1) for v in g.interpolate(0.5, normalized=True).coords[0]]))
res = dict(about='ТП3: линия слоя стен вдоль тела стены (≥ 60 % длины в 0,6 pt от контура), но не в классе этого тела', n=len(rows),
           by_key=dict(seen), length_m=round(sum(r['length_mm'] for r in rows) / 1000, 1), places=rows[:200])
json.dump(res, open(sys.argv[1] if len(sys.argv) > 1 else 'ocg_wallcls.json', 'w'), ensure_ascii=False, indent=1)
print('ТП3: линий слоя стен вдоль тела не в его классе', len(rows), dict(seen), res['length_m'], 'м')
