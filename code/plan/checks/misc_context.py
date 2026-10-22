# Check 3.7, part 2 (29.09.2026): where the unclassified ('misc') objects sit. For each one: the classified object whose
#   outline holds it (a fragment of that object: a seat line left out of a chair), the building fabric it touches (walls,
#   light partitions, glazing), or nothing (a thing of its own). Out: misc_context.json, printed summary.
import pickle, sys, json, collections, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import load, pts, MM_PER_PT
from shapely.geometry import LineString, Point, Polygon, box
from shapely.strtree import STRtree
from shapely.ops import unary_union
P = load(); I = pickle.load(open('inst_final.pkl', 'rb'))
W = pickle.load(open('walls_fixed.pkl' if os.path.exists('walls_fixed.pkl') else 'walls.pkl', 'rb'))['Wpt']
# (01.10.2026, code 005) the same fabric as reclass.py (rule A): marks, grates, masks, signs, the atrium and carpets hold
#   nothing - a piece touching a mark is not 'a fragment of mark' (floor 4: a stop of the gate the rules could never clear)
FABRIC = ('lpart', 'lpartc', 'gklpart', 'glasspart', 'railing', 'facade', 'glass', 'wallline', 'loose', 'roomsep', 'zone', 'axmark', 'tag', 'misc', 'grey',
          'sign', 'atrium', 'carpet', 'mark', 'grate', 'mask')
def geo(i):
    q = pts(P[i]); return LineString(q) if len(q) > 1 else Point(q[0])
def bb(ids):
    q = [p for i in ids for p in pts(P[i])]
    return box(min(x for x, y in q), min(y for x, y in q), max(x for x, y in q), max(y for x, y in q))
hosts = [(n, q) for n, q in enumerate(I) if q['key'] not in FABRIC and q['prims']]
HB = [bb(q['prims']).buffer(1.0) for n, q in hosts]; HT = STRtree(HB)
fab = [i for q in I if q['key'] in FABRIC and q['key'] != 'misc' for i in q['prims']]
FG = [geo(i) for i in fab]; FT = STRtree(FG) if FG else None
WU = unary_union([g for v in W.values() for g in v]).buffer(0.1)
res = []; C = collections.Counter(); CN = collections.Counter()
for n, q in enumerate(I):
    if q['key'] != 'misc' or not q['prims']: continue
    b = bb(q['prims']); g = unary_union([geo(i) for i in q['prims']])
    host = None; best = 0
    for j in HT.query(b):
        hb = HB[j]; a = hb.intersection(b.buffer(0.01)).area / max(b.buffer(0.01).area, 1e-9)
        if a >= 0.8:
            hq = hosts[j][1]
            # touching the host's own drawing (<= 0.1 pt): a fragment, not just something lying on a desk
            hg = unary_union([geo(i) for i in hq['prims']])
            if hg.distance(g) <= 0.1 and a > best: best = a; host = hq['key']
    touch = []
    if host is None:
        if g.intersects(WU): touch.append('walls')
        if FT is not None:
            for j in FT.query(g.buffer(0.1)):
                if FG[j].distance(g) <= 0.05:
                    k = next(qq['key'] for qq in I if fab[j] in qq['prims']) if False else None
                    touch.append('fabric'); break
    cat = ('fragment of ' + host) if host else ('touches ' + '+'.join(sorted(set(touch))) if touch else 'standalone')
    C[cat] += 1; CN[cat] += len(q['prims'])
    w_, h_ = (b.bounds[2] - b.bounds[0]) * MM_PER_PT, (b.bounds[3] - b.bounds[1]) * MM_PER_PT
    res.append(dict(inst=n, cat=cat, size_mm=[round(w_), round(h_)], prims=len(q['prims']), at_pt=[round(b.centroid.x, 1), round(b.centroid.y, 1)]))
json.dump(dict(summary=dict(C), prims=dict(CN), list=res), open('misc_context.json', 'w'), ensure_ascii=False, indent=0)
print('misc', sum(C.values()))
for k, v in C.most_common(): print('   %-28s %5d objects %6d prims' % (k, v, CN[k]))
