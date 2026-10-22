# Overlay of every cfg.py field on the source sheet, to check the operator's decisions field by field (plan/rules/20 §1-§3).
#   python3 cfgcheck.py out_prefix [zoom=3] [cols=3] [rows=2]   (floor folder)
# Colours: SHEET_IN blue, AXIS_BOXES magenta, OUTSIDE_BOXES orange, SHEET_BOXES grey, DIM_X/DIM_Y cyan dashed,
#   CURVED_ZONES green, EXT_ZONES red outline, FACADES cyan thick, WALL_ADD red fill, SANZONES brown,
#   MANUAL purple with index, FAMILIES exemplar boxes black, axes thin blue.
import sys, os, math, importlib.util
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pymupdf as fitz
from PIL import Image, ImageDraw, ImageFont
from shapely.geometry import LineString, Polygon, box
spec = importlib.util.spec_from_file_location('cfg', 'cfg.py'); cfg = importlib.util.module_from_spec(spec); sys.path.insert(0, os.getcwd()); spec.loader.exec_module(cfg)
pref = sys.argv[1]; Z = float(sys.argv[2]) if len(sys.argv) > 2 else 3.0
C = int(sys.argv[3]) if len(sys.argv) > 3 else 3; R = int(sys.argv[4]) if len(sys.argv) > 4 else 2
pg = fitz.open(cfg.PDF)[0]
import manual8 as detect8   # code 008: MANUAL elements may be polygons (Т4-7)
F = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 13)
def zgeom(z):
    if len(z) == 4 and all(isinstance(v, (int, float)) for v in z): return box(*z)
    return LineString(z[0]).buffer(z[1], cap_style=2)
def draw_all(x0, y0, x1, y1, out):
    pix = pg.get_pixmap(matrix=fitz.Matrix(Z, Z), clip=fitz.Rect(x0, y0, x1, y1))
    im = Image.frombytes('RGB', (pix.width, pix.height), pix.samples)
    im = Image.blend(im, Image.new('RGB', im.size, 'white'), 0.35).convert('RGBA')
    ov = Image.new('RGBA', im.size, (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
    T = lambda p: ((p[0] - x0) * Z, (p[1] - y0) * Z)
    def rect(b, col, w=2, fill=None):
        d.rectangle([T((b[0], b[1])), T((b[2], b[3]))], outline=col, width=w, fill=fill)
    def poly(g, col, w=2, fill=None):
        for p in getattr(g, 'geoms', [g]):
            d.polygon([T(c) for c in p.exterior.coords], outline=col, fill=fill)
            d.line([T(c) for c in p.exterior.coords], fill=col, width=w)
    for x in getattr(cfg, 'AX_X', []): d.line([T((x, y0)), T((x, y1))], fill=(60, 90, 255, 120), width=1)
    for y in getattr(cfg, 'AX_Y', []): d.line([T((x0, y)), T((x1, y))], fill=(60, 90, 255, 120), width=1)
    rect(cfg.SHEET_IN, (0, 0, 255, 255), 3)
    for b in getattr(cfg, 'SHEET_BOXES', []): rect(b, (120, 120, 120, 255), 3, (120, 120, 120, 40))
    for b in getattr(cfg, 'AXIS_BOXES', []): rect(b, (220, 0, 220, 255), 3, (220, 0, 220, 30))
    for b in getattr(cfg, 'OUTSIDE_BOXES', []): rect(b, (255, 140, 0, 255), 2, (255, 140, 0, 25))
    for x in getattr(cfg, 'DIM_X', []): d.line([T((x, y0)), T((x, y1))], fill=(0, 190, 190, 255), width=2)
    for y in getattr(cfg, 'DIM_Y', []): d.line([T((x0, y)), T((x1, y))], fill=(0, 190, 190, 255), width=2)
    for z in getattr(cfg, 'CURVED_ZONES', []): poly(zgeom(z), (0, 170, 0, 255), 3, (0, 170, 0, 40))
    for z in getattr(cfg, 'EXT_ZONES', []): poly(zgeom(z), (230, 0, 0, 255), 2, (230, 0, 0, 25))
    for f in getattr(cfg, 'FACADES', []):
        d.line([T(p) for p in f], fill=(0, 200, 230, 255), width=4)
        for p in f: d.ellipse([T(p)[0] - 3, T(p)[1] - 3, T(p)[0] + 3, T(p)[1] + 3], outline=(0, 120, 160, 255))
    for e in getattr(cfg, 'WALL_ADD', []): poly(Polygon(e['poly']), (255, 0, 0, 255), 2, (255, 0, 0, 110))
    for z in getattr(cfg, 'WALL_ZONES', []): poly(zgeom(z['zone']), (0, 120, 0, 255), 2, (0, 200, 0, 60))
    for b in getattr(cfg, 'SANZONES', []) or []: rect(b, (140, 80, 20, 255), 3)
    for n, (key, name, layer, boxes) in enumerate(cfg.MANUAL):
        for b in boxes:
            if detect8.is_poly(b): poly(Polygon(detect8.poly_pts(b)), (130, 0, 200, 255), 2, (130, 0, 200, 30)); b = detect8.bbox_of(b)   # code 008, Т4-7
            else: rect(b, (130, 0, 200, 255), 2, (130, 0, 200, 30))
            d.text((T((b[0], b[1]))[0] + 2, T((b[0], b[1]))[1] + 1), f'M{n}', fill=(90, 0, 150, 255), font=F)
    for fam in cfg.FAMILIES:
        if fam[3] != 'LIB': rect(fam[3], (0, 0, 0, 255), 3); d.text(T((fam[3][0], fam[3][3] + 0.5)), fam[0], fill=(0, 0, 0, 255), font=F)
    im = Image.alpha_composite(im, ov).convert('RGB'); im.save(out); return im.size
X0, Y0, X1, Y1 = cfg.WIN
x0a, y0a = 0, 0; x1a, y1a = pg.rect.width, pg.rect.height
print('overview', draw_all(0, 0, pg.rect.width, pg.rect.height, pref + '_overview.png') if Z else None)
wx = (X1 - X0) / C; wy = (Y1 - Y0) / R
for r in range(R):
    for c in range(C):
        a = (X0 + c * wx - 8, Y0 + r * wy - 8, X0 + (c + 1) * wx + 8, Y0 + (r + 1) * wy + 8)
        print(r, c, [round(v) for v in a], draw_all(*a, f'{pref}_{r}{c}.png'))
