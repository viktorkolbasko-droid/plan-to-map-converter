# Check 3.9, part 1 (29.09.2026): what the operator boxes and the sheet rules dropped that belongs to the drawing.
#   (a) a black primitive of class 'axis' or 'sheet' touching (<= 0.05 pt) a primitive kept in the drawing: the box cuts an
#       element (floor 2: AXIS_BOXES cut the teeth of the round wall at x 110; floor 5: the outer arc of the round wall);
#   (b) a primitive inside SHEET_IN and outside SHEET_BOXES that is 'sheet' by length (SHEET_MAXLEN): only a frame line
#       (>= 1 pt) or a pale mask may be (floors 2, 3, 5: the south glazing band, one line / one fill of 670-760 pt).
#   A kept light grey thin line (>= 0.6) is a grid line and does not count (floor 2: the axis dimension touches a grid
#   line inside the drawing). Out: boxcut.json; both counts must be 0 or explained. Run in a floor folder after objects.py.
import pickle, sys, os, json, collections
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import load, pts, cfg, inboxes
from shapely.geometry import LineString, Point
from shapely.strtree import STRtree
P = load(); cls = pickle.load(open('cls.pkl', 'rb'))
DROP = ('axis', 'sheet')
def _grid_grey(p):   # a light grey thin line is a grid line even when kept (floor 2: a grid line inside the drawing, class lpart)
    c = p[2]; return p[0] == 'l' and c is not None and abs(c[0] - c[1]) < 0.02 and abs(c[1] - c[2]) < 0.02 and c[0] >= 0.6
keep = [i for i, c in enumerate(cls) if c not in DROP + ('dim', 'tag') and not _grid_grey(P[i])]
G = {}
def geo(i):
    if i not in G:
        q = pts(P[i]); G[i] = LineString(q) if len(q) > 1 else Point(q[0])
    return G[i]
kg = [geo(i) for i in keep]; tr = STRtree(kg)
cut = collections.defaultdict(list)
for i, c in enumerate(cls):
    if c not in DROP: continue
    p = P[i]
    if p[2] is not None and not (abs(p[2][0] - p[2][1]) < 0.02 and abs(p[2][1] - p[2][2]) < 0.02 and p[2][0] <= 0.3): continue   # grey = grid lines, bubbles
    if p[2] is None and p[3] is not None and min(p[3]) >= 0.97: continue                                                         # white mask
    g = geo(i); hit = [keep[j] for j in tr.query(g.buffer(0.06)) if kg[j].distance(g) <= 0.05]
    if hit: cut[c].append(dict(prim=i, at_pt=[round(v, 1) for v in pts(p)[0]]))
IN = cfg.SHEET_IN; SB = getattr(cfg, 'SHEET_BOXES', []); ML = getattr(cfg, 'SHEET_MAXLEN', 600)
bylen = []
for i, c in enumerate(cls):
    if c != 'sheet': continue
    q = pts(P[i]); xs = [x for x, y in q]; ys = [y for x, y in q]; b = (min(xs), min(ys), max(xs), max(ys))
    if not inboxes(b, [IN]) or inboxes(b, SB): continue
    p = P[i]
    frame = p[0] == 'l' and (p[1] or 0) >= 1.0; mask = p[0] != 'l' and p[2] is None and p[3] is not None and min(p[3]) >= 0.97
    if not (frame or mask): bylen.append(dict(prim=i, kind=p[0], len_pt=round(max(b[2] - b[0], b[3] - b[1])), bbox=[round(v) for v in b]))
R = dict(cut_by_boxes={k: len(v) for k, v in cut.items()}, cut_samples={k: v[:30] for k, v in cut.items()},
         sheet_by_length_inside=len(bylen), sheet_by_length_samples=bylen[:30])
json.dump(R, open('boxcut.json', 'w'), ensure_ascii=False, indent=0)
print('cut by boxes', R['cut_by_boxes'], '| sheet by length inside the drawing', len(bylen))
