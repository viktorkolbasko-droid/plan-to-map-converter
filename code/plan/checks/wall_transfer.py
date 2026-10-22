# Through elements (29.09.2026, owner: the floors shown whole are the more reliable): the walls a partial sheet has lost
#   (drawn as outlines only) are taken from a reference floor where the same element is drawn as walls.
#   The reference floor's walls of the given classes are mapped onto this sheet by the pair registration of
#   crossfloor.json, clipped to the operator's zone, minus what this sheet already has as walls; every vertex coordinate
#   is snapped to this sheet's own straight thick lines (<= SNAP pt, x to vertical lines, y to horizontal ones), so the
#   added bodies sit on the sheet's lines. Out: the polygons for cfg.WALL_ADD (printed) and a picture to review.
# Usage (work folder as cwd): python3 wall_transfer.py crossfloor.json REF TARGET x0 y0 x1 y1 [classes=cap,ext] [snap=1.6] [out.png]
import sys, json, pickle, os, importlib.util, math
import numpy as np
from shapely.geometry import box, Polygon, LineString
from shapely.affinity import affine_transform
from shapely.ops import unary_union
J = json.load(open(sys.argv[1])); REF, TGT = sys.argv[2], sys.argv[3]; Z = box(*map(float, sys.argv[4:8]))
CL = (sys.argv[8] if len(sys.argv) > 8 else 'cap,ext').split(','); SNAP = float(sys.argv[9]) if len(sys.argv) > 9 else 1.6
OUT = sys.argv[10] if len(sys.argv) > 10 else 'wall_transfer.png'
def floor(d):
    spec = importlib.util.spec_from_file_location('cfg_' + d, os.path.join(d, 'cfg.py'))
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')); sys.path.insert(0, d)
    cfg = importlib.util.module_from_spec(spec); spec.loader.exec_module(cfg); sys.path.pop(0)
    if len(getattr(cfg, 'AX_X', [])) >= 2 and len(getattr(cfg, 'AX_Y', [])) >= 2:
        kx = np.polyfit(cfg.AX_X, cfg.AX_XMM, 1); ky = np.polyfit(cfg.AX_Y, cfg.AX_YMM, 1)
    else:                                          # no grid on the sheet (floor 6): scale and origin from cfg, as common.py
        k = cfg.MM_PER_PT; ox, oy = cfg.ORIGIN_PT; kx = np.array([k, -k * ox]); ky = np.array([-k, k * oy])
    W = pickle.load(open(os.path.join(d, 'walls_fixed.pkl'), 'rb'))['Wpt']
    P = pickle.load(open(os.path.join(d, 'seq.pkl'), 'rb'))[0]
    pdf = [os.path.join(d, f) for f in os.listdir(d) if f.lower().endswith('.pdf')][0]
    return kx, ky, W, P, pdf
ka, la, WA, _, _ = floor(REF); kb, lb, WB, PB, pdfb = floor(TGT)
key = f'{REF}-{TGT}' if f'{REF}-{TGT}' in J['pairs'] else f'{TGT}-{REF}'
r = J['pairs'][key]['registration']
def ref_to_tgt(g):
    g = affine_transform(g, [ka[0], 0, 0, la[0], ka[1], la[1]])
    if key.startswith(REF + '-'): g = affine_transform(g, [1 / r['s'], 0, 0, 1 / r['s'], -r['tx'] / r['s'], -r['ty'] / r['s']])
    else: g = affine_transform(g, [r['s'], 0, 0, r['s'], r['tx'], r['ty']])
    return affine_transform(g, [1 / kb[0], 0, 0, 1 / lb[0], -kb[1] / kb[0], -lb[1] / lb[0]])
have = unary_union([g for v in WB.values() for g in v])
mapped = unary_union([ref_to_tgt(g) for k in CL for g in WA.get(k, [])]).intersection(Z)
# this sheet's straight thick lines in the zone: snap targets
xs, ys = [], []
for p in PB:
    if p[0] != 'l' or (p[1] or 0) < 0.45: continue
    (x1, y1), (x2, y2) = p[4]
    if not LineString(p[4]).intersects(Z.buffer(2)) or math.dist((x1, y1), (x2, y2)) < 2: continue
    if abs(x1 - x2) < 0.05: xs.append((x1 + x2) / 2)
    if abs(y1 - y2) < 0.05: ys.append((y1 + y2) / 2)
xs, ys = np.array(sorted(set(round(v, 2) for v in xs))), np.array(sorted(set(round(v, 2) for v in ys)))
def snap(v, arr):
    if not len(arr): return v
    j = int(np.argmin(np.abs(arr - v))); return float(arr[j]) if abs(arr[j] - v) <= SNAP else v
out = []
for pg in getattr(mapped, 'geoms', [mapped]):
    if pg.geom_type != 'Polygon' or pg.area < 0.5: continue
    q = Polygon([(snap(x, xs), snap(y, ys)) for x, y in pg.exterior.coords]).buffer(0)
    q = q.difference(have.buffer(0.02)).intersection(Z)
    for a in getattr(q, 'geoms', [q]):
        if a.geom_type != 'Polygon' or a.area < 1.0 or 2 * a.area / a.length < 0.8: continue
        a = a.simplify(0.05)
        out.append([(round(x, 2), round(y, 2)) for x, y in list(a.exterior.coords)[:-1]])
mm2 = sum(Polygon(o).area for o in out) * abs(kb[0] * lb[0]) / 1e6
print(f'# {len(out)} bodies, {mm2:.2f} m2, from {REF} by the registration of {key} (median {r.get("median_mm")} mm), snapped <= {SNAP} pt')
print('WALL_ADD=[' + ',\n          '.join(f"dict(cls='cap',poly={o},why='from {REF}')" for o in out) + ']')
# picture
import pymupdf as fitz
from PIL import Image, ImageDraw
x0, y0, x1, y1 = Z.buffer(6).bounds; S = 10
pix = fitz.open(pdfb)[0].get_pixmap(matrix=fitz.Matrix(S, S), clip=fitz.Rect(x0, y0, x1, y1))
im = Image.frombytes('RGB', (pix.width, pix.height), pix.samples); im = Image.blend(im, Image.new('RGB', im.size, 'white'), 0.4); d = ImageDraw.Draw(im)
def poly(ring, col, w=2): d.line([((x - x0) * S, (y - y0) * S) for x, y in ring], fill=col, width=w)
for g in getattr(have, 'geoms', [have]):
    if g.intersects(Z.buffer(6)): poly(list(g.exterior.coords), (0, 0, 220))
for o in out: poly(o + [o[0]], (220, 0, 0), 3)
poly(list(Z.exterior.coords), (0, 160, 0), 1)
im.save(OUT); print('#', OUT, im.size)
