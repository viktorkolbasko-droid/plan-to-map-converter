# source crop with a pt grid (labels every 5 pt) and current walls: gridview.py x0 y0 x1 y1 zoom out
import sys, pickle
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from common import PDF
import pymupdf as fitz
from PIL import Image, ImageDraw, ImageFont
x0, y0, x1, y1, Z = map(float, sys.argv[1:6]); out = sys.argv[6]
pg = fitz.open(PDF)[0]; pix = pg.get_pixmap(matrix=fitz.Matrix(Z, Z), clip=fitz.Rect(x0, y0, x1, y1))
im = Image.frombytes('RGB', (pix.width, pix.height), pix.samples); im = Image.blend(im, Image.new('RGB', im.size, 'white'), 0.35)
d = ImageDraw.Draw(im); f = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 11)
W = pickle.load(open('walls_fixed.pkl', 'rb'))['Wpt']
col = {'ext': (200, 0, 0), 'cap': (0, 0, 220), 'gkl': (0, 150, 0), 'blk': (230, 120, 0)}
for k, v in W.items():
    for g in v:
        for p in ([g] if g.geom_type == 'Polygon' else list(g.geoms)):
            b = p.bounds
            if b[2] < x0 or b[0] > x1 or b[3] < y0 or b[1] > y1: continue
            d.line([((x - x0) * Z, (y - y0) * Z) for x, y in p.exterior.coords], fill=col[k], width=2)
import math
for x in range(int(math.ceil(x0 / 5) * 5), int(x1) + 1, 5):
    d.line([((x - x0) * Z, 0), ((x - x0) * Z, im.height)], fill=(255, 150, 150), width=1); d.text(((x - x0) * Z + 2, 2), str(x), fill=(200, 0, 0), font=f)
for y in range(int(math.ceil(y0 / 5) * 5), int(y1) + 1, 5):
    d.line([(0, (y - y0) * Z), (im.width, (y - y0) * Z)], fill=(150, 150, 255), width=1); d.text((2, (y - y0) * Z + 2), str(y), fill=(0, 0, 200), font=f)
im.save(out); print(im.size)
