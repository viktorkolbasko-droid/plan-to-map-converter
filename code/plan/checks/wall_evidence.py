# Check 3.12 (29.09.2026): every wall body is drawn so in the source - its inside carries a pattern or a fill. Found on
#   floor 2 by the tile of check 3.11: the lobby between the curved glazing and the panoramic lift (about 3 m2) and a
#   quarter of the lift car were 'plasterboard' since the morning, and no check saw it - the body's outline lies on source
#   lines (fidelity), and ink compares strokes, not fills.
#   Each wall body (the union of one class) is shrunk by 1.2 pt (75 mm): a wall drawn by its outline only is thinner
#   than that and leaves nothing. In what is left, the evidence is
#     - pattern strokes that reach into it: the recogniser's hatch lines (hat3.pkl) and neutral strokes 0.2-15 pt
#       that are no dashes of a dashed line (a dash, >= 1.5 pt, has a collinear neighbour of its style within 8 pt);
#     - fills of any colour but white (the grey of capital walls).
#   A place farther than 7 pt (0.45 m) from every such stroke and outside the fills is empty; each empty piece
#   >= 0.15 m2 is listed - its place, class, area - with a tile: source | walls over the source.
#   Operator bodies are not asked: cfg WALL_ZONES and WALL_ADD.
#   Out: wall_evidence.json, wall_evidence.png.
# Run in a floor folder after the walls (reads walls.pkl, hat3.pkl): python3 wall_evidence.py [walls.pkl] [out prefix]
import pickle, sys, os, json, math, collections, importlib.util
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import load, pts, PDF, MM_PER_PT
from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union
from shapely.strtree import STRtree
from shapely.prepared import prep
WP = sys.argv[1] if len(sys.argv) > 1 else 'walls.pkl'; OUTP = sys.argv[2] if len(sys.argv) > 2 else 'wall_evidence'
P = load(); W = pickle.load(open(WP, 'rb'))['Wpt']; H = pickle.load(open('hat3.pkl', 'rb'))
_sp = importlib.util.spec_from_file_location('cfg', 'cfg.py'); cfg = importlib.util.module_from_spec(_sp); _sp.loader.exec_module(cfg)
def zg(z):
    return box(*z) if len(z) == 4 and all(isinstance(v, (int, float)) for v in z) else LineString(z[0]).buffer(z[1], cap_style=2)
OP = unary_union([zg(z['zone']) for z in getattr(cfg, 'WALL_ZONES', [])] + [Polygon(e['poly']) for e in getattr(cfg, 'WALL_ADD', [])])
M2 = 1e6 / MM_PER_PT ** 2                                            # pt2 in one m2
cls = pickle.load(open('cls.pkl', 'rb'))
# pattern strokes: the recogniser's hatch lines, and any neutral stroke 0.5-15 pt that is not a dash of a dashed line
#   (a dash has a collinear neighbour of its style within 8 pt: the dashed lines of floor 2's lobby are no hatch; the sparse
#   hatch of the north wall of floor 2 is not in the recogniser's list, its strokes end on a thin line inside the band)
def _neu(c): return c is not None and abs(c[0] - c[1]) < 0.03 and abs(c[1] - c[2]) < 0.03 and c[0] <= 0.85
CAND = [i for i, p in enumerate(P) if p[0] == 'l' and cls[i] not in ('dim', 'axis', 'sheet', 'tag') and _neu(p[2]) and 0.2 <= math.dist(*p[4]) <= 15]
CG = [LineString(P[i][4]) for i in CAND]; CT = STRtree(CG) if CG else None
def _ang(i):
    (x1, y1), (x2, y2) = P[i][4]; return math.degrees(math.atan2(y2 - y1, x2 - x1)) % 180
HS = set(H['hat']); PAT = []
for k, i in enumerate(CAND):
    if i not in HS and CG[k].length >= 1.5:                            # marks and dots are no dashes
        a0 = _ang(i); dash = False
        for j in CT.query(CG[k].buffer(8)):
            ii = CAND[j]
            if ii == i or P[ii][1] != P[i][1] or P[ii][2] != P[i][2] or abs(((_ang(ii) - a0) + 90) % 180 - 90) > 1: continue
            L = LineString(P[i][4])
            if all(L.interpolate(L.project(Point(v))).distance(Point(v)) <= 0.1 or True for v in P[ii][4]) and \
               max(abs((v[0] - P[i][4][0][0]) * math.sin(math.radians(a0)) - (v[1] - P[i][4][0][1]) * math.cos(math.radians(a0))) for v in P[ii][4]) <= 0.1:
                dash = True; break
        if dash: continue
    PAT.append(CG[k])
HL = PAT + [LineString(P[i][4]) for i in H['hat'] if P[i][0] == 'l' and i not in set(CAND)]; HT = STRtree(HL) if HL else None
FI = [Polygon(pts(p)).buffer(0) for p in P if p[0] == 'qu' and p[3] is not None and min(p[3]) < 0.97 and len(pts(p)) >= 3]
FT = STRtree(FI) if FI else None
# what is far from any evidence is empty: the core minus the pattern strokes that reach into it, each grown by 7 pt
#   (0.45 m: the sparse hatch of floor 2's walls has a stroke every 0.76 m), minus the fills. A stroke that only borders
#   the core does not count - the diagonals of the panoramic lift's car (floor 2), grey and 11.7 pt long, were taken for
#   the hatch of a capital wall and made a quarter of the car a wall
# on a raster of 0.5 pt: distances to the evidence by the distance transform (buffering 10^4 strokes is too slow)
import numpy as np
from scipy import ndimage
from PIL import Image as _I, ImageDraw as _D
RES = 0.5
allg = [g for v in W.values() for g in v]
X0, Y0, X1, Y1 = unary_union(allg).bounds if allg else (0, 0, 1, 1); X0 -= 10; Y0 -= 10; X1 += 10; Y1 += 10
NX, NY = int((X1 - X0) / RES) + 1, int((Y1 - Y0) / RES) + 1
def px(c): return [((x - X0) / RES, (y - Y0) / RES) for x, y in c]
def mask_polys(gs):
    im = _I.new('1', (NX, NY), 0); d = _D.Draw(im)
    for g in gs:
        for p in getattr(g, 'geoms', [g]):
            if p.geom_type != 'Polygon' or p.is_empty: continue
            d.polygon(px(p.exterior.coords), fill=1)
            for h in p.interiors: d.polygon(px(h.coords), fill=0)
    return np.array(im, dtype=bool)
# the evidence is the part of a pattern stroke inside the core; a fill counts wherever it is
im = _I.new('1', (NX, NY), 0); d = _D.Draw(im)
for g in HL: d.line(px(g.coords), fill=1, width=1)
EV_ALL = np.array(im, dtype=bool)
F_ALL = mask_polys(FI)
rows = []
for k, v in W.items():
    if not v: continue
    U = unary_union(v)
    core = U.buffer(-1.2, join_style=2, mitre_limit=3).buffer(0.2, join_style=2).intersection(U)
    if not OP.is_empty: core = core.difference(OP)
    if core.is_empty: continue
    C = mask_polys([core]); Ev = EV_ALL & C
    far = ndimage.distance_transform_edt(~Ev) * RES > 7 if Ev.any() else np.ones_like(C)
    Em = C & far & ~F_ALL
    lab, n = ndimage.label(Em)
    rows.append(dict(cls=k, core_m2=round(core.area / M2, 2)))
    if n == 0: continue
    area = ndimage.sum(Em, lab, index=range(1, n + 1)) * RES * RES
    sl = ndimage.find_objects(lab)
    for m in range(n):
        if area[m] < 0.15 * M2: continue
        ys, xs = sl[m]; bb = (X0 + xs.start * RES, Y0 + ys.start * RES, X0 + xs.stop * RES, Y0 + ys.stop * RES)
        yy, xx = np.nonzero(lab[sl[m]] == m + 1); cx_ = X0 + (xs.start + xx.mean()) * RES; cy_ = Y0 + (ys.start + yy.mean()) * RES
        rows.append(dict(cls=k, at_pt=[round(float(cx_), 1), round(float(cy_), 1)], m2=round(float(area[m]) / M2, 2), ok=False, bbox_pt=[round(float(x), 1) for x in bb]))
bad = sorted([r for r in rows if r.get('ok') is False], key=lambda r: -r['m2'])
json.dump(dict(core_m2={r['cls']: r['core_m2'] for r in rows if 'core_m2' in r}, empty=len(bad), empty_m2=round(sum(r['m2'] for r in bad), 2), rows=bad), open(OUTP + '.json', 'w'), ensure_ascii=False, indent=0)
print('wall cores', {r['cls']: r['core_m2'] for r in rows if 'core_m2' in r}, 'm2 | empty pieces >= 0.15 m2:', len(bad), round(sum(r['m2'] for r in bad), 2), 'm2')
for r in bad[:30]: print('  ', r['cls'], r['at_pt'], r['m2'], 'm2', 'bbox', r['bbox_pt'])
import pymupdf as fitz
from PIL import Image, ImageDraw, ImageFont
pg = fitz.open(PDF)[0]; f = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 12)
COL = {'cap': (200, 0, 0, 110), 'gkl': (0, 120, 220, 110), 'blk': (0, 170, 60, 110), 'ext': (120, 0, 160, 110)}
tiles = []
for r in bad[:16]:
    x0, y0, x1, y1 = r['bbox_pt']; pad = max(4.0, 0.3 * max(x1 - x0, y1 - y0)); x0 -= pad; y0 -= pad; x1 += pad; y1 += pad
    Z = min(10.0, 300 / max(x1 - x0, y1 - y0)); fr = box(x0, y0, x1, y1)
    pix = pg.get_pixmap(matrix=fitz.Matrix(Z, Z), clip=fitz.Rect(x0, y0, x1, y1))
    src = Image.frombytes('RGB', (pix.width, pix.height), pix.samples)
    im = Image.blend(src, Image.new('RGB', src.size, 'white'), 0.6); d = ImageDraw.Draw(im, 'RGBA')
    for k, v in W.items():
        for g in v:
            g = g.intersection(fr)
            for p in getattr(g, 'geoms', [g]):
                if p.geom_type == 'Polygon' and not p.is_empty:
                    d.polygon([((a - x0) * Z, (b - y0) * Z) for a, b in p.exterior.coords], fill=COL.get(k, (120, 120, 120, 110)))
    t = Image.new('RGB', (src.width * 2 + 10, src.height + 20), 'white'); t.paste(src, (0, 20)); t.paste(im, (src.width + 10, 20))
    ImageDraw.Draw(t).text((4, 2), f"{r['cls']} у ({r['at_pt'][0]:.0f}, {r['at_pt'][1]:.0f}): {r['m2']} м² без штриховки и заливки", fill=(0, 0, 0), font=f)
    tiles.append(t)
if tiles:
    cols = 2; rows_ = (len(tiles) + cols - 1) // cols; Wd = max(t.width for t in tiles); Hh = max(t.height for t in tiles)
    sh = Image.new('RGB', (cols * (Wd + 8), rows_ * (Hh + 8)), (235, 235, 235))
    for n, t in enumerate(tiles): sh.paste(t, ((n % cols) * (Wd + 8), (n // cols) * (Hh + 8)))
    sh.save(OUTP + '.png')
