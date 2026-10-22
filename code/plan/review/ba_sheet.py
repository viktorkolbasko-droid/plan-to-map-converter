# before / after of the walls over the source: ba_sheet.py prev_walls.pkl cx cy half zoom title out.png [before label]
#   (floor folder; the label says which delivery 'before' is, default 'Было')
import sys, pickle
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from common import PDF, walls_file
import pymupdf as fitz
from PIL import Image, ImageDraw, ImageFont
prev, cx, cy, h, Z, title, out = sys.argv[1], *map(float, sys.argv[2:6]), sys.argv[6], sys.argv[7]
BEFORE = sys.argv[8] if len(sys.argv) > 8 else 'Было'
f = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 20)
pg = fitz.open(PDF)[0]
def panel(wp, col, lab):
    pix = pg.get_pixmap(matrix=fitz.Matrix(Z, Z), clip=fitz.Rect(cx - h, cy - h, cx + h, cy + h))
    im = Image.frombytes('RGB', (pix.width, pix.height), pix.samples).convert('RGBA')
    ov = Image.new('RGBA', im.size, (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
    W = pickle.load(open(wp, 'rb'))['Wpt']
    for v in W.values():
        for g in v:
            for p in ([g] if g.geom_type == 'Polygon' else list(getattr(g, 'geoms', []))):
                b = p.bounds
                if b[2] < cx - h or b[0] > cx + h or b[3] < cy - h or b[1] > cy + h: continue
                pts = [((x - cx + h) * Z, (y - cy + h) * Z) for x, y in p.exterior.coords]
                d.polygon(pts, fill=col + (70,)); d.line(pts, fill=col + (255,), width=3)
    im = Image.alpha_composite(im, ov).convert('RGB'); dd = ImageDraw.Draw(im)
    dd.rectangle([0, 0, im.width, 34], fill='white'); dd.text((8, 6), lab, fill=(0, 0, 0), font=f)
    return im
a = panel(prev, (220, 30, 30), BEFORE); b = panel(walls_file(), (20, 90, 220), 'Стало')
s = Image.new('RGB', (a.width + b.width + 12, a.height + 40), 'white'); s.paste(a, (0, 40)); s.paste(b, (a.width + 12, 40))
ImageDraw.Draw(s).text((8, 8), title, fill=(0, 0, 0), font=f)
s.save(out); print(s.size)
