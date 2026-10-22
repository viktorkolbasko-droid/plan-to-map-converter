# walls of floor A mapped onto floor B's source (pair registration of crossfloor.json): xf_transfer_view.py crossfloor.json A B x0 y0 x1 y1 zoom out
#   (B box in B pt). Walls of B in blue, walls of A mapped in red.
import sys, json, pickle, os, importlib.util
import numpy as np, pymupdf as fitz
from PIL import Image, ImageDraw, ImageFont
from shapely.affinity import affine_transform
from shapely.geometry import box
J = json.load(open(sys.argv[1])); A, B = sys.argv[2], sys.argv[3]; x0, y0, x1, y1, Z = map(float, sys.argv[4:9]); out = sys.argv[9]
def floor(d):
    spec = importlib.util.spec_from_file_location('cfg_' + d, os.path.join(d, 'cfg.py'))
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')); sys.path.insert(0, d)
    cfg = importlib.util.module_from_spec(spec); spec.loader.exec_module(cfg); sys.path.pop(0)
    kx = np.polyfit(cfg.AX_X, cfg.AX_XMM, 1); ky = np.polyfit(cfg.AX_Y, cfg.AX_YMM, 1)
    wf = os.path.join(d, 'walls_fixed.pkl')
    pdf = [os.path.join(d, f) for f in os.listdir(d) if f.lower().endswith('.pdf')][0]
    return kx, ky, pickle.load(open(wf, 'rb'))['Wpt'], pdf
ka, la, WA, _ = floor(A); kb, lb, WB, pdfb = floor(B)
key = f'{A}-{B}' if f'{A}-{B}' in J['pairs'] else f'{B}-{A}'
r = J['pairs'][key]['registration']        # frame of the pair's first floor: p = s * p_second + t
def a_pt_to_b_pt(g):
    g = affine_transform(g, [ka[0], 0, 0, la[0], ka[1], la[1]])                         # A pt -> A mm
    if key.startswith(A + '-'):  g = affine_transform(g, [1 / r['s'], 0, 0, 1 / r['s'], -r['tx'] / r['s'], -r['ty'] / r['s']])   # A frame -> B mm
    else: g = affine_transform(g, [r['s'], 0, 0, r['s'], r['tx'], r['ty']])            # A = second floor: A mm -> B mm
    return affine_transform(g, [1 / kb[0], 0, 0, 1 / lb[0], -kb[1] / kb[0], -lb[1] / lb[0]])   # B mm -> B pt
pg = fitz.open(pdfb)[0]; pix = pg.get_pixmap(matrix=fitz.Matrix(Z, Z), clip=fitz.Rect(x0, y0, x1, y1))
im = Image.frombytes('RGB', (pix.width, pix.height), pix.samples); im = Image.blend(im, Image.new('RGB', im.size, 'white'), 0.4); d = ImageDraw.Draw(im)
def draw(W, col, tf=None):
    for k, v in W.items():
        for g in v:
            for p in ([g] if g.geom_type == 'Polygon' else list(g.geoms)):
                q = tf(p) if tf else p
                if not q.intersects(box(x0, y0, x1, y1)): continue
                d.line([((x - x0) * Z, (y - y0) * Z) for x, y in q.exterior.coords], fill=col, width=2)
draw(WB, (0, 0, 220)); draw(WA, (220, 0, 0), a_pt_to_b_pt)
im.save(out); print(im.size, key, r)
