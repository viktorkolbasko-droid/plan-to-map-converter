# Clusters of primitives of one own colour of the sheet (stroke or fill), with their owners.
#   python3 colour_clusters.py run_dir r g b [tol=0.12] [link_pt=3]
import sys, os, pickle, collections, math
import numpy as np
from scipy.spatial import cKDTree
d = sys.argv[1]; C = tuple(map(float, sys.argv[2:5])); tol = float(sys.argv[5]) if len(sys.argv) > 5 else 0.12
link = float(sys.argv[6]) if len(sys.argv) > 6 else 3.0
P = pickle.load(open(os.path.join(d, 'seq.pkl'), 'rb'))[0]
I = pickle.load(open(os.path.join(d, 'inst_final.pkl'), 'rb'))
WP = pickle.load(open(os.path.join(d, 'wallprims.pkl'), 'rb'))
own = {}
for n, q in enumerate(I):
    for i in q['prims']: own[i] = q['key']
def col(p): return p[2] if p[0] != 'qu' else (p[3] if p[3] is not None else p[2])
def near(c): return c is not None and all(abs(c[k] - C[k]) <= tol for k in range(3))
ids = [i for i, p in enumerate(P) if near(col(p))]
pts = np.array([[sum(v[0] for v in P[i][4]) / len(P[i][4]), sum(v[1] for v in P[i][4]) / len(P[i][4])] for i in ids])
par = list(range(len(ids)))
def f(a):
    while par[a] != a: par[a] = par[par[a]]; a = par[a]
    return a
for a, b in cKDTree(pts).query_pairs(link):
    ra, rb = f(a), f(b)
    if ra != rb: par[ra] = rb
g = collections.defaultdict(list)
for k in range(len(ids)): g[f(k)].append(ids[k])
rows = []
for r, ks in g.items():
    xs = [v[0] for i in ks for v in P[i][4]]; ys = [v[1] for i in ks for v in P[i][4]]
    ow = collections.Counter('wall' if i in WP else own.get(i, 'FREE') for i in ks)
    kinds = collections.Counter((P[i][0], P[i][1]) for i in ks)
    rows.append((len(ks), [round(min(xs), 1), round(min(ys), 1), round(max(xs), 1), round(max(ys), 1)], dict(ow), dict(kinds)))
rows.sort(key=lambda r: (r[1][1] // 25, r[1][0]))
print('prims', len(ids), 'clusters', len(rows))
for r in rows: print(r)
