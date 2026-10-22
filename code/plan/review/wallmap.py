# Walls by class over the faded source: ext red, cap blue, gkl green, blk orange (fill 40 %, outline).
#   python3 wallmap.py run_dir walls.pkl out_prefix [zoom=4] [cols=4] [rows=2] [x0 y0 x1 y1]
import sys, os, pickle, importlib.util
import pymupdf as fitz
from PIL import Image, ImageDraw, ImageFont
d, wf, pref = sys.argv[1:4]; Z = float(sys.argv[4]) if len(sys.argv) > 4 else 4
C = int(sys.argv[5]) if len(sys.argv) > 5 else 4; R = int(sys.argv[6]) if len(sys.argv) > 6 else 2
BOX = tuple(map(float, sys.argv[7:11])) if len(sys.argv) > 10 else None
spec = importlib.util.spec_from_file_location('cfg', os.path.join(d, 'cfg.py')); cfg = importlib.util.module_from_spec(spec)
sys.path.insert(0, d); spec.loader.exec_module(cfg)
W = pickle.load(open(os.path.join(d, wf), 'rb')); W = W.get('Wpt', W)
COL = {'ext': (220, 0, 0), 'cap': (0, 60, 230), 'gkl': (0, 160, 0), 'blk': (240, 140, 0)}
pg = fitz.open(os.path.join(d, cfg.PDF))[0]
F = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 14)
def tile(x0, y0, x1, y1, out):
    pix = pg.get_pixmap(matrix=fitz.Matrix(Z, Z), clip=fitz.Rect(x0, y0, x1, y1))
    im = Image.frombytes('RGB', (pix.width, pix.height), pix.samples)
    im = Image.blend(im, Image.new('RGB', im.size, 'white'), 0.6).convert('RGBA')
    ov = Image.new('RGBA', im.size, (0, 0, 0, 0)); dr = ImageDraw.Draw(ov)
    for cls, lst in W.items():
        c = COL.get(cls, (120, 0, 120))
        for p in lst:
            for g in getattr(p, 'geoms', [p]):
                if g.bounds[2] < x0 or g.bounds[0] > x1 or g.bounds[3] < y0 or g.bounds[1] > y1: continue
                xy = [((a - x0) * Z, (b - y0) * Z) for a, b in g.exterior.coords]
                dr.polygon(xy, fill=c + (100,), outline=c + (255,))
                for h in g.interiors: dr.polygon([((a - x0) * Z, (b - y0) * Z) for a, b in h.coords], fill=(255, 255, 255, 160), outline=c + (255,))
    im = Image.alpha_composite(im, ov).convert('RGB'); dd = ImageDraw.Draw(im)
    y = 4
    for k, c in COL.items(): dd.rectangle([4, y, 18, y + 14], fill=c); dd.text((22, y - 1), k, fill=(0, 0, 0), font=F); y += 18
    im.save(out); return im.size
if BOX: print(tile(*BOX, pref + '.png'))
else:
    X0, Y0, X1, Y1 = cfg.WIN; wx = (X1 - X0) / C; wy = (Y1 - Y0) / R
    for r in range(R):
        for c in range(C):
            a = (X0 + c * wx - 4, Y0 + r * wy - 4, X0 + (c + 1) * wx + 4, Y0 + (r + 1) * wy + 4)
            print(r, c, tile(*a, f'{pref}_{r}{c}.png'))
