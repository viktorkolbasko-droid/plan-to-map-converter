"""ocg/walls_overlay.py - code 010 (Т9-9, test 9 of the layer route): the outlines of the wall bodies of two runs over the source in colour — before (blue, thick) and after (red,
thin); one tile per place, h pt around it, Z px per pt. For the owner's «было — стало» of the walls (J4d, J6).
usage: python3 walls_overlay.py out.png items.json h Z cols before_walls.pkl after_walls.pkl   (floor folder: the sheet of cfg - ocg/sheet.py)
items.json: [[x, y, "подпись"], ...]"""
import pickle, sys, json, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import sheet
import pymupdf, shapely
from PIL import Image, ImageDraw, ImageFont
out, items, h, Z, cols, fa, fb = sys.argv[1], json.load(open(sys.argv[2])), float(sys.argv[3]), float(sys.argv[4]), int(sys.argv[5]), sys.argv[6], sys.argv[7]
F = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 12)
pg = pymupdf.open(sheet.PDF)[0]               # code 010: the sheet the steps read (the copy at the reference scale, if any)
def bodies(f):
    W = pickle.load(open(f, 'rb')); return [q for c, g in W['bodies'] for q in getattr(g, 'geoms', [g]) if q.geom_type == 'Polygon' and q.area > 0.05]
A, B = bodies(fa), bodies(fb); tiles = []
for n, it in enumerate(items):
    x, y, lab = it[:3]; x0, y0, x1, y1 = x - h, y - h, x + h, y + h
    pix = pg.get_pixmap(matrix=pymupdf.Matrix(Z, Z), clip=pymupdf.Rect(x0, y0, x1, y1), alpha=False)
    im = Image.frombytes('RGB', (pix.width, pix.height), pix.samples); d = ImageDraw.Draw(im)
    box = shapely.geometry.box(x0, y0, x1, y1)
    def T(p): return ((p[0] - x0) * Z, (p[1] - y0) * Z)
    for G, col, w in ((A, (0, 90, 255), 5), (B, (230, 0, 0), 2)):
        for g in G:
            if not g.intersects(box): continue
            for r in [g.exterior, *g.interiors]: d.line([T(q) for q in r.coords], fill=col, width=w)
    d.rectangle([0, 0, im.width, 16], fill='white'); d.text((3, 1), f'{n + 1}. {lab}  (синий — до, красный — после)', font=F, fill=(0, 0, 0))
    tiles.append(im)
tw, th = tiles[0].size; rows = (len(tiles) + cols - 1) // cols
img = Image.new('RGB', (cols * (tw + 8), rows * (th + 8)), 'white')
for n, t in enumerate(tiles): img.paste(t, ((n % cols) * (tw + 8), (n // cols) * (th + 8)))
img.save(out); print(out, img.size)
