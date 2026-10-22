# Lines inside a window (pt) grouped as horizontal / vertical with their extents, owners in a run and stroke colour
#   (code 008, Т4-11: the tool of test 4 of client A 4, review/ of the code):
#   python3 lines_in.py RUN_DIR x0 y0 x1 y1 [minlen=2]
import sys, os, pickle, collections
d = sys.argv[1]; b = tuple(map(float, sys.argv[2:6])); ml = float(sys.argv[6]) if len(sys.argv) > 6 else 2.0
P = pickle.load(open(os.path.join(d, 'seq.pkl'), 'rb'))[0]; I = pickle.load(open(os.path.join(d, 'inst_final.pkl'), 'rb'))
WP = pickle.load(open(os.path.join(d, 'wallprims.pkl'), 'rb'))
own = {}
for n, q in enumerate(I):
    for i in q['prims']: own[i] = q['key'] + str(n)
H = collections.defaultdict(list); V = collections.defaultdict(list)
for i, p in enumerate(P):
    if p[0] != 'l': continue
    (x0, y0), (x1, y1) = p[4][0], p[4][-1]
    if min(x0, x1) < b[0] or max(x0, x1) > b[2] or min(y0, y1) < b[1] or max(y0, y1) > b[3]: continue
    o = 'WALL' if i in WP else own.get(i, 'FREE')
    c = tuple(round(v, 2) for v in (p[2] or ())); w = round(p[1] or 0, 2)
    if abs(y1 - y0) < 0.05 and abs(x1 - x0) >= ml: H[round(y0, 2)].append((round(min(x0, x1), 2), round(max(x0, x1), 2), o, c, w))
    elif abs(x1 - x0) < 0.05 and abs(y1 - y0) >= ml: V[round(x0, 2)].append((round(min(y0, y1), 2), round(max(y0, y1), 2), o, c, w))
print('horizontal')
for y in sorted(H): print(' y', y, sorted(H[y]))
print('vertical')
for x in sorted(V): print(' x', x, sorted(V[x]))
