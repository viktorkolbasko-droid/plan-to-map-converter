# Dry run of cfg.MANUAL against a finished run (code 008, Т4-7, Т4-11; the tool of test 4 of client A 4): in list order,
#   each record takes the primitives inside one of its elements (a box + 0.6 pt, or a polygon - manual8.py) that are not
#   'early' (walls, families, doors, colour elements, tags, axes, sheet) and not taken by an earlier record; prints per
#   record what it would take, by the current owner key in the run. Keys that are not misc / light partitions / loose /
#   free / wall faces are flagged '!!' - a box that would steal another object or a later step's primitives (cfgread.py
#   stops on them before a run). Code 008: primitives of colour elements and of early steps under a box are shown as
#   'early:<key>' (test 4: door45 and the other colour elements were not shown at all).
#   python3 manual_take.py RUN_DIR [cfg.py]   (default: RUN_DIR/cfg.py)
import sys, os, pickle, collections, importlib.util
d = sys.argv[1]; cf = sys.argv[2] if len(sys.argv) > 2 else os.path.join(d, 'cfg.py')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import manual8
spec = importlib.util.spec_from_file_location('cfgx', cf); cfg = importlib.util.module_from_spec(spec); sys.path.insert(0, d); spec.loader.exec_module(cfg)
P = pickle.load(open(os.path.join(d, 'seq.pkl'), 'rb'))[0]; I = pickle.load(open(os.path.join(d, 'inst_final.pkl'), 'rb')); I = I[0] if isinstance(I, tuple) else I
wpf = os.path.join(d, 'wallprims_pre7.pkl') if os.path.exists(os.path.join(d, 'wallprims_pre7.pkl')) else os.path.join(d, 'wallprims.pkl')
WP = pickle.load(open(wpf, 'rb')); cls = pickle.load(open(os.path.join(d, 'cls.pkl'), 'rb'))
own = {}
for n, q in enumerate(I):
    for i in q['prims']: own[i] = (q['key'], n)
EARLY = {'chair', 'wc', 'sink', 'stool', 'door', 'tag', 'roomsep', 'axis', 'sheet', 'dim', 'sign', 'door45c', 'wcsink', 'glass_c'}
CE = {e['key'] for e in getattr(cfg, 'COLOR_ELEMENTS', [])}
OK = {'misc', 'lpart', 'lpartc', 'loose', 'FREE', 'wallline'}
bb = [(min(v[0] for v in p[4]), min(v[1] for v in p[4]), max(v[0] for v in p[4]), max(v[1] for v in p[4])) for p in P]
from shapely.geometry import LineString, Polygon
def geom(i):
    p = P[i]
    if p[0] in ('l', 'c'): return LineString(p[4])
    g = Polygon(p[4]); return g if g.is_valid else g.buffer(0)
taken = set(); flags = 0
for k, (key, name, layer, boxes) in enumerate(cfg.MANUAL):
    g = collections.Counter(); ex = collections.defaultdict(list); early = collections.Counter()
    for i, b_ in enumerate(bb):
        if i in taken: continue
        if not any(manual8.element_takes(b, b_, lambda i=i: geom(i), 0.6) for b in boxes): continue
        if i in WP or (P[i][0] == 'qu' and P[i][3] == (1.0, 1.0, 1.0)): continue   # walls and white masks are never offered to a box
        o = own.get(i, ('FREE', cls[i]))
        if cls[i] in ('axis', 'sheet', 'dim'): continue
        if o[0] in EARLY or (o[0] in CE and not (o[0] == 'glass' and P[i][0] != 'qu')): early['early:' + o[0]] += 1; continue
        taken.add(i); g[o[0] if o[0] != 'FREE' else 'FREE:' + str(o[1])] += 1; ex[o[0]].append(b_)
    bad = [kk for kk in g if kk.split(':')[0] not in OK and kk != key]
    flags += bool(bad)
    print(('!! ' if bad else '   ') + f'{k:3d} {key:9s} {name[:38]:38s} ' + ', '.join(f'{kk} {v}' for kk, v in g.most_common())
          + (' | ' + ', '.join(f'{kk} {v}' for kk, v in early.most_common()) if early else '')
          + ('   <- ' + ', '.join(f"{kk} {[round(min(t[0] for t in ex[kk]),2), round(min(t[1] for t in ex[kk]),2), round(max(t[2] for t in ex[kk]),2), round(max(t[3] for t in ex[kk]),2)]}" for kk in bad) if bad else '')
          + ('' if g else '   EMPTY'))
print('records', len(cfg.MANUAL), 'flagged', flags)
