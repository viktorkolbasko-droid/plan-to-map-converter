# List the geometry that differs between two DXF of the same floor (multiset of dxfsame.py, 0.1 mm), with layer and place.
#   python3 dxfdiff_list.py A.dxf B.dxf [N=40]
import sys, os, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dxfsame import sig
a, b = sys.argv[1], sys.argv[2]; N = int(sys.argv[3]) if len(sys.argv) > 3 else 40
ca, ha, ba = sig(a); cb, hb, bb = sig(b)
onlyA = ha - hb; onlyB = hb - ha
print('only in A:', sum(onlyA.values()), '| only in B:', sum(onlyB.values()))
for name, d in (('A', onlyA), ('B', onlyB)):
    by = collections.Counter()
    for (k, g), n in d.items(): by[k] += n
    print(name, dict(by))
    for (k, g), n in list(d.items())[:N]:
        gg = g if not isinstance(g, tuple) or len(g) <= 12 else g[:12] + ('...', len(g))
        print(' ', name, k, n, gg)
print('blocks only A:', ba - bb, '| only B:', bb - ba)
