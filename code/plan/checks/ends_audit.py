# Checks 3.8 and 3.9 (29.09.2026): open ends of the result against the source.
#   Every primitive has an owner in the result: an object (instance of inst_final.pkl), the walls (wallprims.pkl), or
#   nothing - dropped as sheet / axis / dimension / tag, or a white mask. An object's linework is "closed" where each end
#   of its lines meets another line of the same object (<= TOL). An open end is then looked up in the source:
#     - the source continues there with a primitive of ANOTHER owner -> the object lost a piece to that owner
#       ('split': a seat line left in 'misc', a partition end cap in 'misc', teeth of a wall dropped as 'axis');
#     - nothing continues -> the object is open in the source as well (a door swing, a single line) - reported only.
#   Out: ends_audit.json - per object key: objects, open ends, where the continuation went; the split list with places;
#        for each 'misc' object: the owners it continues into (what it is a piece of).
# Run in a floor folder after the final assign: python3 ends_audit.py
import pickle, sys, json, collections, os, math
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import load, pts, MM_PER_PT
from shapely.geometry import LineString, Point
from shapely.strtree import STRtree
TOL = 0.06                      # pt, ~4 mm at 1:100 on A2 (floors 1, 2, 6), ~2 mm on A3 (floors 3-5)
P = load(); cls = pickle.load(open('cls.pkl', 'rb')); I = pickle.load(open('inst_final.pkl', 'rb'))
WP = pickle.load(open('wallprims.pkl', 'rb')) if os.path.exists('wallprims.pkl') else set()
own = {}
for n, q in enumerate(I):
    for i in q['prims']: own[i] = n
def owner(i):
    if i in own: return ('obj', own[i])
    if i in WP: return ('walls', None)
    c = cls[i]
    if c in ('axis', 'sheet', 'dim', 'tag'): return ('dropped:' + c, None)
    return ('none', None)
def okind(o):
    k, n = o
    return I[n]['key'] if k == 'obj' else k
AXC = [tuple(c) for c in getattr(__import__('common').cfg, 'AXIS_COLORS', [(0.67, 0.67, 0.67), (1.0, 0.67, 0.67)])]
def grid_line(i):
    """a grid axis line or a dimension line crosses the drawing: an object's line ending on it is not cut by it"""
    p = P[i]
    return cls[i] == 'dim' or (cls[i] == 'axis' and p[2] is not None and any(max(abs(p[2][j] - c[j]) for j in range(3)) < 0.02 for c in AXC + [(0.83, 0.83, 0.83)]))
FAMILIES_K = ('wc', 'sink', 'chair', 'stool', 'armchair')
COLLECTORS = ('wcacc', 'loose', 'lpartc', 'screen')
def kind_of(key, k_):
    """what the continuation means for the object"""
    if k_ in ('misc', 'loose', 'none'): return 'piece left unclassified'
    # (01.10.2026, test of floor 5, T3) a family holds only part of its drawing - a toilet its bowl - when the rest went to
    #   a collecting class (the neck and base with the cistern in 'toilet accessories'): that is a piece left over too, not
    #   a stop against a neighbour. Floor 5: 3 toilets of 9 were open (26-27 % of the hull) and passed as 'ends on another'
    if key in FAMILIES_K and k_ in COLLECTORS: return 'piece left unclassified'
    if k_.startswith('dropped'): return 'cut: dropped as ' + k_.split(':')[1]
    if k_ == key: return 'same kind, another object'
    if k_ == 'walls': return 'ends on a wall'
    return 'ends on another object'
G = [None] * len(P); idx = []
for i, p in enumerate(P):
    q = pts(p)
    if len(q) < 2: continue
    if p[0] == 'qu' and p[2] is None and p[3] is not None and min(p[3]) >= 0.97: continue    # white masks
    G[i] = LineString(q); idx.append(i)
TR = STRtree([G[i] for i in idx])
def touching(pt, skip):
    """source primitives touching the point, other than skip"""
    P_ = Point(pt); out = []
    for j in TR.query(P_.buffer(TOL)):
        i = idx[j]
        if i == skip or grid_line(i): continue
        if G[i].distance(P_) <= TOL: out.append(i)
    return out
# open lines: ends of 'l' and 'c' (a 'qu' is closed)
OPEN_BY_NATURE = ('door', 'door45', 'rdoor', 'roomsep', 'axmark', 'tag', 'zone', 'stair', 'lpart', 'lpartc', 'gklpart', 'glasspart', 'railing', 'facade',
                  'glass', 'wallline', 'loose', 'doorhw', 'sign', 'atrium', 'grey')
stat = collections.defaultdict(lambda: collections.Counter()); stat2 = collections.defaultdict(lambda: collections.Counter()); objs = collections.Counter(); objs_open = collections.Counter()
splits = []; misc_into = collections.defaultdict(collections.Counter)
for n, q in enumerate(I):
    key = q['key']; ids = [i for i in q['prims'] if G[i] is not None]
    if not ids: continue
    objs[key] += 1; S = set(q['prims']); opened = False
    for i in ids:
        p = P[i]
        if p[0] == 'qu': continue
        for e in (G[i].coords[0], G[i].coords[-1]):
            t = touching(e, i)
            if any(j in S for j in t): continue                     # closed within the object
            opened = True
            others = collections.Counter(okind(owner(j)) for j in t)
            if not t: stat[key]['open in the source too'] += 1; continue
            k_ = others.most_common(1)[0][0]
            stat[key][kind_of(key, k_)] += 1; stat2[key][k_] += 1
            if key == 'misc': misc_into[n][k_] += 1
            if len(splits) < 40000: splits.append(dict(key=key, inst=n, into=k_, kind=kind_of(key, k_), at_pt=[round(e[0], 2), round(e[1], 2)]))
    if opened: objs_open[key] += 1
by_key = {}
for key in sorted(objs, key=lambda k: -objs[k]):
    by_key[key] = dict(objects=objs[key], with_open_ends=objs_open[key], open_by_nature=key in OPEN_BY_NATURE,
                       ends=dict(stat[key].most_common()), into=dict(stat2[key].most_common(8)))
json.dump(dict(tol_pt=TOL, by_key=by_key, splits=splits,
               misc_into={str(n): dict(c) for n, c in misc_into.items()}), open('ends_audit.json', 'w'), ensure_ascii=False, indent=0)
print('%-10s %6s %6s  ends: where the source continues' % ('key', 'objs', 'open'))
for key, v in by_key.items():
    e = v['ends']; tot = sum(e.values())
    if not tot: continue
    print('%-10s %6d %6d  %s%s' % (key, v['objects'], v['with_open_ends'], ', '.join(f'{k}: {c}' for k, c in list(e.items())[:6]),
                                   '  (open by nature)' if v['open_by_nature'] else ''))
