"""Э7м-б, code 012 (СО-2; owner 09.10.2026, В1 место 3; rows 183, 189): a barrier strip of the wall layers - a part of the desk.
Э6 (e6_walls.py) takes a thin strip of the wall layers out of the wall bodies when one of its ends lies on a desk (outline or
inside) and no end reaches a wall, a column, glass, the core or the facade (walls.pkl 'barriers': polygon, primitive ids, desk
polygon). Э7 leaves such primitives without a body (a partition without hatch, lpart); here, after Э7м, they go to the object of
the desk they touch (A-82: its ids and what it draws), the emptied partition object becomes 'empty' («→ часть стола»).
A barrier whose desk object is not found - a stop (exit 3): a silent leftover would be a hanging line (row 189).
Writes objects.pkl in place and barriers.json."""
import pickle, json, sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import sheet
from shapely.geometry import Polygon, LineString
from shapely.ops import unary_union
W = pickle.load(open('walls.pkl', 'rb')); BAR = W.get('barriers', [])
O = pickle.load(open('objects.pkl', 'rb')); objs = O['objs']; owner = O['owner']
P = pickle.load(open('prims_f.pkl', 'rb'))['P']
FL = sheet.L('furniture'); SKIP = {'empty', 'wall', 'glass', 'lpart', 'wallline', 'coreline', 'dim', 'axis', 'mark', 'zone', 'corezone'}
def geom(p):
    if p['kind'] == 'fill' and len(p['p']) >= 3: return Polygon(p['p'], p.get('holes', [])).buffer(0)
    return LineString(p['p']) if len(p['p']) >= 2 else None
rep = []; bad = []
for b in BAR:
    g = b['g']; tol = 2 * g.area / g.length if g.length else 0.5
    # the desk object: the owner of the furniture fills under the desk polygon Э6 found (most area), not a line class
    cnt = collections.Counter()
    for i, p in enumerate(P):
        if p['layer'] not in FL or p['kind'] != 'fill' or p['kind'] == 'removed': continue
        q = geom(p)
        if q is None or q.is_empty or not q.intersects(b['desk'].buffer(0.05)): continue
        k = owner.get(i) if isinstance(owner, dict) else None
        if isinstance(k, int) and objs[k]['key'] not in SKIP: cnt[k] += q.intersection(b['desk'].buffer(0.05)).area
    if not cnt: bad.append(b['at_pt']); continue
    k = cnt.most_common(1)[0][0]; d = objs[k]
    moved = []; emptied = []
    for i in b['pids']:
        j = owner.get(i)
        if isinstance(j, int) and j != k:
            o = objs[j]; o['ids'] = [x for x in o['ids'] if x != i]
            if 'draw' in o: o['draw'] = [x for x in o['draw'] if x != i]
            if not o['ids'] and o['key'] != 'empty':
                emptied.append(dict(obj=j, key=o['key'])); o['key'] = 'empty'; o['name'] = (o.get('name') or '') + ' → часть стола (барьер, СО-2)'; o.pop('draw', None)
        if i not in d['ids']: d['ids'].append(i)
        if 'draw' in d and i not in d['draw']: d['draw'].append(i)
        owner[i] = k; moved.append(i)
    rep.append(dict(at_pt=b['at_pt'], size_mm=b['size_mm'], desk_obj=k, desk_key=d['key'], desk_name=d['name'], prims=moved, emptied=emptied))
json.dump(dict(barriers=rep, not_found=bad), open('barriers.json', 'w'), ensure_ascii=False, indent=1)
pickle.dump(O, open('objects.pkl', 'wb'))
print('barriers given to desks', len(rep), [(r['at_pt'], r['desk_key'], r['desk_name'][:40]) for r in rep])
if bad:
    print('СТОП: барьер слоя стен без объекта стола у конца —', bad, '(Э6 нашёл заливку стола, Э7м не дал ей объект)'); sys.exit(3)
