# Ink diff: source PDF primitives vs exported DXF, both rasterised at Z px/pt.
# missing = source ink with no output ink within TOL; extra = output ink with no source ink within TOL.
# Usage: python3 inkdiff.py [dxf] [out_prefix]   (env Z=6, TOL=1.0 pt, AMIN=2.0 pt^2)
import os, sys, json, math, pickle, numpy as np, cv2, ezdxf
from ezdxf import disassemble, path as ezpath
from common import kx, ky, load, pts, DXF, cfg
Z = float(os.environ.get('Z', '6')); TOL = float(os.environ.get('TOL', '1.0')); AMIN = float(os.environ.get('AMIN', '2.0'))
dxf = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] else DXF
pref = sys.argv[2] if len(sys.argv) > 2 else 'inkdiff'
X0, Y0, X1, Y1 = [float(v) for v in os.environ['WIN'].split(',')] if os.environ.get('WIN') else cfg.WIN
W, H = int((X1 - X0) * Z), int((Y1 - Y0) * Z)
P = load(); cls = pickle.load(open('cls.pkl', 'rb')); HOLES = pickle.load(open('holes.pkl', 'rb'))
def px(p): return (int(round((p[0] - X0) * Z)), int(round((p[1] - Y0) * Z)))
def mm2pt(x, y): return ((x - kx[1]) / kx[0], (y - ky[1]) / ky[0])
SKIPCLS = ('sheet', 'dim', 'axis')
src = np.zeros((H, W), np.uint8)
for i, p in enumerate(P):
    if cls[i] in SKIPCLS: continue
    if p[0] == 'qu':
        fc = p[3]
        if p[2] is not None and len(p[4]) >= 2:     # an outlined fill: its outline is ink whatever the fill colour
            cv2.polylines(src, [np.array([px(v) for v in p[4]], np.int32)], True, 255, 1)
        if fc is None or max(fc) >= 0.6: continue   # light fills (desk tan, tints) are compared by their outlines only
        m = np.zeros((H, W), np.uint8) if HOLES.get(p[5]) else None
        q = np.array([px(v) for v in p[4]], np.int32)
        if m is None: cv2.fillPoly(src, [q], 255)
        else:
            cv2.fillPoly(m, [q], 255)
            for h in HOLES[p[5]]: cv2.fillPoly(m, [np.array([px(v) for v in h], np.int32)], 0)
            src |= m
        continue
    q = np.array([px(v) for v in pts(p)], np.int32)
    cv2.polylines(src, [q], False, 255, 1)
doc = ezdxf.readfile(dxf); msp = doc.modelspace()
out = np.zeros((H, W), np.uint8); wall = np.zeros((H, W), np.uint8)
WALLH = ('A-21----H-', 'A-221---H-', 'A-222---H-', 'A-223---H-')
def poly_px(vs): return np.array([px(mm2pt(v.x, v.y)) for v in vs], np.int32)
REG = []   # (layer, bbox pt) of every drawn output primitive, for the report
def draw(layer, e, bname=''):
    # the regenerated axis marks and dimensions are left out - but only the drawing's own entities: a block (an operator
    #   object) on those layers is drawn. Before 01.10.2026 (test of floor 5, T14) the layer alone decided, and an
    #   operator's local dimension on A-AX----D- counted as missing ink (18 pt2 in iteration 2)
    if (layer in ('A-AX----T-', 'A-AX----D-') and not bname) or e.dxftype() in ('TEXT', 'MTEXT', 'DIMENSION'): return
    # (code 007) openings A-23 are a derived outline of a stair cage or the atrium (owner 03.10.2026), not source ink;
    #   they are checked by checks/gate7.py S27*
    if layer == 'A-23----E-': return
    if layer == 'A-AX----E-' and e.dxftype() == 'LINE' and (e.dxf.start - e.dxf.end).magnitude > 20000: return   # generated axis lines
    if e.dxftype() == 'HATCH':
        solid = e.dxf.solid_fill
        if not solid: return
        col = e.rgb if e.rgb is not None else (0, 0, 0)
        target = wall if layer in WALLH else (out if max(col) < 153 else None)
        if target is None: return
        # even-odd over all boundary paths
        acc = np.zeros((H, W), np.uint8)
        for pth in ezpath.from_hatch(e):
            vs = list(pth.flattening(5))
            if len(vs) < 3: continue
            t = np.zeros((H, W), np.uint8); cv2.fillPoly(t, [poly_px(vs)], 1); acc ^= t
        target |= (acc * 255).astype(np.uint8)
        return
    for pr in disassemble.to_primitives([e]):
        try: vs = list(pr.vertices())
        except Exception: continue
        if len(vs) < 2: continue
        q = poly_px(vs); cv2.polylines(out, [q], False, 255, 1)
        REG.append((layer, bname, q[:, 0].min() / Z + X0, q[:, 1].min() / Z + Y0, q[:, 0].max() / Z + X0, q[:, 1].max() / Z + Y0))
for e in msp:
    L = e.dxf.layer
    if e.dxftype() == 'INSERT':
        for v in e.virtual_entities():
            lay = v.dxf.layer if v.dxf.layer not in ('0',) else L
            draw(lay if lay.endswith('H-') else L, v, e.dxf.name)
    else: draw(L, e)
# walls: outlines are drawn on E layers; the fill is the wall mask
r = max(1, int(round(TOL * Z)))
ker = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))
allout = out | wall
missing = src & ~cv2.dilate(allout, ker)
extra = out & ~cv2.dilate(src, ker) & ~cv2.dilate(wall, np.ones((3, 3), np.uint8))
def comps(m, tag):
    n, lab, st, _ = cv2.connectedComponentsWithStats(cv2.dilate(m, np.ones((5, 5), np.uint8)))
    res = []
    for k in range(1, n):
        x, y, w, h, a = st[k]
        area = int((m[y:y + h, x:x + w] > 0).sum()) / (Z * Z)
        if area < AMIN and max(w, h) / Z < 3: continue
        res.append(dict(kind=tag, bb=[float(round(x / Z + X0, 1)), float(round(y / Z + Y0, 1)), float(round((x + w) / Z + X0, 1)), float(round((y + h) / Z + Y0, 1))], ink_pt2=round(area, 2)))
    return sorted(res, key=lambda d: -d['ink_pt2'])
M_, E_ = comps(missing, 'missing'), comps(extra, 'extra')
import collections
own = {}
if os.path.exists('inst_final.pkl'):
    for q in pickle.load(open('inst_final.pkl', 'rb')):
        for i in q['prims']: own[i] = q['key']
PBB = [None] * len(P)
def pbb(i):
    if PBB[i] is None:
        v = pts(P[i]); PBB[i] = (min(a for a, b in v), min(b for a, b in v), max(a for a, b in v), max(b for a, b in v))
    return PBB[i]
cand = [i for i in range(len(P)) if cls[i] not in SKIPCLS]
for d in M_:
    b = d['bb']; c = collections.Counter()
    for i in cand:
        q = pbb(i)
        if q[0] <= b[2] and q[2] >= b[0] and q[1] <= b[3] and q[3] >= b[1]: c[own.get(i, 'FREE:' + cls[i])] += 1
    d['src_owner'] = c.most_common(3)
for d in E_:
    b = d['bb']; c = collections.Counter()
    for L, bn, a0, b0, a1, b1 in REG:
        if a0 <= b[2] and a1 >= b[0] and b0 <= b[3] and b1 >= b[1]: c[(L, bn[:24])] += 1
    d['out_layer'] = c.most_common(3)
json.dump(dict(missing=M_, extra=E_, tol_pt=TOL, src_ink_pt2=round(int((src > 0).sum()) / Z / Z), missing_pt2=round(int((missing > 0).sum()) / Z / Z, 1), extra_pt2=round(int((extra > 0).sum()) / Z / Z, 1)), open(pref + '.json', 'w'), ensure_ascii=False, indent=0)
np.save(pref + '_src.npy', src); np.save(pref + '_out.npy', allout)
vis = np.full((H, W, 3), 255, np.uint8); vis[src > 0] = (190, 190, 190); vis[wall > 0] = (225, 225, 225); vis[out > 0] = (120, 120, 120)
vis[cv2.dilate(missing, np.ones((3, 3), np.uint8)) > 0] = (0, 0, 255); vis[cv2.dilate(extra, np.ones((3, 3), np.uint8)) > 0] = (255, 0, 0)
cv2.imwrite(pref + '.png', vis)
print('missing comps', len(M_), 'extra comps', len(E_), 'missing pt2', round(int((missing > 0).sum()) / Z / Z, 1), 'extra pt2', round(int((extra > 0).sum()) / Z / Z, 1))
for d in (M_[:int(os.environ.get('NP', '25'))] + E_[:int(os.environ.get('NP', '25'))]): print(d['kind'], [float(v) for v in d['bb']], d['ink_pt2'], d.get('src_owner') or d.get('out_layer'))
