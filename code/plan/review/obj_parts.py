# Connected parts of one object of inst_final.pkl (prims touching <= tol pt, bbox test) with bbox, count, colours.
#   python3 obj_parts.py run_dir obj_index [tol=0.15] [min_prims=1]
import sys, os, pickle, collections
d = sys.argv[1]; n = int(sys.argv[2]); tol = float(sys.argv[3]) if len(sys.argv) > 3 else 0.15
mn = int(sys.argv[4]) if len(sys.argv) > 4 else 1
P = pickle.load(open(os.path.join(d, 'seq.pkl'), 'rb'))[0]; I = pickle.load(open(os.path.join(d, 'inst_final.pkl'), 'rb'))
ids = I[n]['prims']; print(I[n]['key'], I[n]['name'], len(ids))
B = {i: (min(v[0] for v in P[i][4]), min(v[1] for v in P[i][4]), max(v[0] for v in P[i][4]), max(v[1] for v in P[i][4])) for i in ids}
par = {i: i for i in ids}
def f(x):
    while par[x] != x: par[x] = par[par[x]]; x = par[x]
    return x
L = sorted(ids, key=lambda i: B[i][0])
for a_k, a in enumerate(L):
    for b in L[a_k + 1:]:
        if B[b][0] > B[a][2] + tol: break
        if B[b][1] <= B[a][3] + tol and B[a][1] <= B[b][3] + tol: par[f(a)] = f(b)
g = collections.defaultdict(list)
for i in ids: g[f(i)].append(i)
rows = []
for k, v in g.items():
    if len(v) < mn: continue
    bb = (min(B[i][0] for i in v), min(B[i][1] for i in v), max(B[i][2] for i in v), max(B[i][3] for i in v))
    cols = collections.Counter(str(P[i][2] if P[i][0] != 'qu' else P[i][3]) for i in v)
    rows.append((len(v), [round(x, 2) for x in bb], dict(cols.most_common(3))))
for r in sorted(rows, key=lambda r: (r[1][0], r[1][1])): print(r)
