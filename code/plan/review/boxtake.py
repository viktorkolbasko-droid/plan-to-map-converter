# What would a MANUAL box take? Prims fully inside the box (+pad 0.6), grouped by their current owner in the run
#   (families/doors/colour elements/walls are taken earlier in assign and are shown only for information).
#   python3 boxtake.py run_dir x0 y0 x1 y1 [pad=0.6]
import sys, os, pickle, collections
d = sys.argv[1]; b = tuple(map(float, sys.argv[2:6])); pad = float(sys.argv[6]) if len(sys.argv) > 6 else 0.6
P = pickle.load(open(os.path.join(d, 'seq.pkl'), 'rb'))[0]; I = pickle.load(open(os.path.join(d, 'inst_final.pkl'), 'rb'))
WP = pickle.load(open(os.path.join(d, 'wallprims.pkl'), 'rb')); cls = pickle.load(open(os.path.join(d, 'cls.pkl'), 'rb'))
own = {}
for n, q in enumerate(I):
    for i in q['prims']: own[i] = (q['key'], n)
g = collections.defaultdict(list)
for i, p in enumerate(P):
    xs = [v[0] for v in p[4]]; ys = [v[1] for v in p[4]]
    if min(xs) >= b[0] - pad and max(xs) <= b[2] + pad and min(ys) >= b[1] - pad and max(ys) <= b[3] + pad:
        k = ('WALL', cls[i]) if i in WP else own.get(i, ('FREE', cls[i]))
        g[k].append((min(xs), min(ys), max(xs), max(ys)))
EARLY = ('chair', 'wc', 'sink', 'stool', 'door', 'tag', 'roomsep', 'WALL', 'axis', 'sheet', 'dim')
for k, v in sorted(g.items(), key=lambda t: -len(t[1])):
    bb = [round(min(r[0] for r in v), 2), round(min(r[1] for r in v), 2), round(max(r[2] for r in v), 2), round(max(r[3] for r in v), 2)]
    print(('   (early) ' if k[0] in EARLY or k[1] in EARLY else '  TAKE  ') , k, len(v), bb)
