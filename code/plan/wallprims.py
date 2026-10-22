from common import *
import shapely
from shapely.geometry import LineString, Point
from shapely.ops import unary_union
from shapely.prepared import prep
P=load(); cls=pickle.load(open('cls.pkl','rb'))
w=pickle.load(open('walls.pkl','rb'))['Wpt']
U=unary_union([p for v in w.values() for p in v])
Ub=prep(U.buffer(0.08))
WP=set()
# (01.10.2026, owner's answer 8) a colour element with in_walls=True (water connection points: red and blue stroke-filled
#   symbols in the wall under the bar, floor 5) lies inside a wall body but is not the wall: its primitives stay out of
#   the wall prims, and assign gives them to the element
_KEEP=[(ce['colors'],ce.get('boxes') or [cfg.SHEET_IN]) for ce in getattr(cfg,'COLOR_ELEMENTS',[]) if ce.get('in_walls')]
def _keep(p):
    c=p[2] if p[2] is not None else p[3]
    if c is None or not _KEEP: return False
    xs=[v[0] for v in p[4]]; ys=[v[1] for v in p[4]]
    return any(any(max(abs(c[j]-z[j]) for j in range(3))<=0.03 for z in cols) and any(min(xs)>=b[0]-0.3 and max(xs)<=b[2]+0.3 and min(ys)>=b[1]-0.3 and max(ys)<=b[3]+0.3 for b in bxs) for cols,bxs in _KEEP)
for i,p in enumerate(P):
    if cls[i] in ('axis','sheet','dim'): continue
    if _keep(p): continue
    if p[0] in ('l','c'):
        g=LineString(list(p[4]) if p[0]=='l' else bez(p[4],8))
        if Ub.contains(g): WP.add(i)
pickle.dump(WP,open('wallprims.pkl','wb'))
print('wall prims',len(WP))
