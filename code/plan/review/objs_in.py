# Objects of a run whose bbox centre lies in a box (pt): key, name, layer, primitives, bbox.  objs_in.py run_dir x0 y0 x1 y1
import sys, os, pickle, math
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
d = sys.argv[1]; x0, y0, x1, y1 = map(float, sys.argv[2:6])
P = pickle.load(open(os.path.join(d, 'seq.pkl'), 'rb'))[0]
I = pickle.load(open(os.path.join(d, 'inst_final.pkl'), 'rb'))
def bez(g, n=8):
    return [((1-t)**3*g[0][0]+3*(1-t)**2*t*g[1][0]+3*(1-t)*t*t*g[2][0]+t**3*g[3][0],(1-t)**3*g[0][1]+3*(1-t)**2*t*g[1][1]+3*(1-t)*t*t*g[2][1]+t**3*g[3][1]) for t in [k/(n-1) for k in range(n)]]
def pts(p): return list(p[4]) if p[0] == 'l' else (bez(p[4]) if p[0] == 'c' else list(p[4]))
for n, q in enumerate(I):
    if not q['prims']: continue
    ps = [v for i in q['prims'] for v in pts(P[i])]
    b = (min(p[0] for p in ps), min(p[1] for p in ps), max(p[0] for p in ps), max(p[1] for p in ps))
    c = ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)
    if x0 <= c[0] <= x1 and y0 <= c[1] <= y1:
        print(n, q['key'], '|', q['name'][:60], '|', q['layer'], '| prims', len(q['prims']), '| bb', [round(v, 1) for v in b])
