"""ocg/walls_changes.py - code 010 (Т9-9, test 9 of the layer route): what changed between the wall bodies of two runs — area added and removed, the largest pieces (their width
2A/P), the Hausdorff distance, vertices; writes a sample of places (the largest and a random few) for walls_overlay.py.
usage: python3 walls_changes.py before_walls.pkl after_walls.pkl items.json [n_big=8] [n_random=8]   (floor folder: mm per pt of cfg)"""
import pickle, shapely, numpy as np, json, random, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import sheet
from shapely.ops import unary_union
def bodies(f):
    W = pickle.load(open(f, 'rb')); return [(c, q) for c, g in W['bodies'] for q in getattr(g, 'geoms', [g]) if q.geom_type == 'Polygon' and q.area > 0.05]
A = bodies(sys.argv[1]); B = bodies(sys.argv[2]); nb = int(sys.argv[4]) if len(sys.argv) > 4 else 8; nr = int(sys.argv[5]) if len(sys.argv) > 5 else 8
UA = unary_union([g for _, g in A]); UB = unary_union([g for _, g in B])
add = UB.difference(UA); rem = UA.difference(UB); K = sheet.K          # code 010: mm per pt of the floor's cfg (48.04 was the client-b sheet)
pa = [q for q in getattr(add, 'geoms', [add]) if q.area > 1e-5]; pr = [q for q in getattr(rem, 'geoms', [rem]) if q.area > 1e-5]
print('bodies', len(A), len(B), '| area', round(UA.area * K * K / 1e6, 3), round(UB.area * K * K / 1e6, 3), 'm2 | added', len(pa), round(add.area * K * K / 1e6, 4), 'm2 | removed', len(pr), round(rem.area * K * K / 1e6, 4), 'm2')
print('Hausdorff (mm):', round(UA.hausdorff_distance(UB) * K, 1))
big = sorted(pa + pr, key=lambda q: -q.area)
print('largest pieces mm2:', [round(q.area * K * K) for q in big[:12]])
def w(q): return 2 * q.area / q.length * K
print('largest pieces width mm (2A/P):', [round(w(q), 1) for q in big[:12]])
print('verts', sum(len(g.exterior.coords) - 1 + sum(len(h.coords) - 1 for h in g.interiors) for _, g in A), '->', sum(len(g.exterior.coords) - 1 + sum(len(h.coords) - 1 for h in g.interiors) for _, g in B))
random.seed(5); S = big[:nb] + (random.sample(big[nb:], min(nr, len(big) - nb)) if len(big) > nb else [])
I = [[q.representative_point().x, q.representative_point().y, f'{"добавлено" if q in pa else "убрано"} {round(q.area * K * K)} мм², ширина {round(w(q), 1)} мм'] for q in S]
json.dump(I, open(sys.argv[3], 'w'), ensure_ascii=False)
