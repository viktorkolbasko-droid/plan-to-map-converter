# Checklist B of the test-4 preregistration (proto/prereg.md): the data behind each item for one run folder
#   (code 008, Т4-11: the facts of the rules - arcs, glazing, columns, doors, signs, fire cabinets, convectors, seats,
#   room separators, «Неизвестное», stairs and lifts, L2 - one line each; the items are those of floor 4 of client A).
#   python3 checklist.py RUN_DIR
import sys, os, json, pickle, collections, math
d = sys.argv[1]
P = pickle.load(open(os.path.join(d, 'seq.pkl'), 'rb'))[0]; I = pickle.load(open(os.path.join(d, 'inst_final.pkl'), 'rb'))
J = lambda f: json.load(open(os.path.join(d, f))) if os.path.exists(os.path.join(d, f)) else {}
def bb(ids):
    xs = [v[0] for i in ids for v in P[i][4]]; ys = [v[1] for i in ids for v in P[i][4]]
    return [round(min(xs), 1), round(min(ys), 1), round(max(xs), 1), round(max(ys), 1)]
K = collections.Counter(q['key'] for q in I if q['prims'])
by = lambda k: [q for q in I if q['key'] == k and q['prims']]
arcs = J('arcs_audit.json'); print('1 arcs 3.11:', {k: arcs.get(k) for k in list(arcs)[:6]})
fac = by('facade'); print('2 facade objects', len(fac), 'verify facade covered', J('verify.json').get('facade_covered_share'), 'ends', J('verify.json').get('facade_ends_to_wall_mm'))
cols = by('column'); print('3 columns', len(cols), collections.Counter(q['name'] for q in cols))
d45 = by('door45'); print('4 door45', len(d45), collections.Counter((q['name'][:50], q['layer']) for q in d45))
sg = by('sign'); print('5 sign', len(sg), set(q['name'] for q in sg))
fi = by('fire'); print('6 fire', len(fi), set(q['layer'] for q in fi))
cv = by('convector'); print('7 convector', len(cv), [bb(q['prims'])[:2] for q in cv])
ch = by('chair'); print('8 chairs', len(ch), collections.Counter(q['name'] for q in ch), 'verify chairs_office', J('verify.json').get('chairs_office'))
ro = J('rooms.json'); print('9 rooms', {k: ro[k] for k in ro if not isinstance(ro[k], (list, dict))})
unk = [q for q in I if q['prims'] and q['name'].startswith('Неизвестное')]
print('10 unknown', len(unk), collections.Counter(q['name'] for q in unk))
print('   booth', [(q['key'], q['name']) for q in I if 'кабин' in q['name'] and 'звонк' in q['name']])
g = J('gate.json'); L = g.get('lists', {})
print('11 stairs', K['stair'], 'lifts', K['lift'], 'L3 level frames', len(L.get('L3', {}).get('level_frames', [])), 'L3 lines outside walls', L.get('L3', {}).get('lines_outside_walls'))
print('12 L2', L.get('L2', {}).get('n'), L.get('L2', {}).get('places'))
print('gate ok', g.get('ok'), 'stops', [(s['code'], s['n']) for s in g.get('stops', [])], 'accepted', g.get('accepted'))
