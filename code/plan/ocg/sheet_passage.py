"""Review sheet of the passage zones (Э9): the source in grey, wall bodies, furniture outlines, the corridor zone of the
source (lavender) and the computed passage of each open space (green). usage: python3 sheet_passage.py out.png [Z] (code 009: run.sh sheets)"""
import pickle, sys, os
import numpy as np, pymupdf
from PIL import Image, ImageDraw, ImageFont
import os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import sheet; from e7_comp import geom, load_prims, load_walls
out = sys.argv[1]; Z = float(sys.argv[2]) if len(sys.argv) > 2 else 2.0
_B = sheet.RENDER_BOX or tuple(pymupdf.open(sheet.PDF)[0].rect)        # cfg.OCG_RENDER_BOX: the part of the sheet on the review sheets
X0, Y0, X1, Y1 = _B
pg = pymupdf.open(sheet.PDF)[0]
pix = pg.get_pixmap(matrix=pymupdf.Matrix(Z, Z), clip=pymupdf.Rect(X0, Y0, X1, Y1), alpha=False)
im = Image.frombytes('RGB', (pix.width, pix.height), pix.samples).convert('L').convert('RGB')
im = Image.blend(Image.new('RGB', im.size, 'white'), im, 0.45).convert('RGBA')
ov = Image.new('RGBA', im.size, (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
def T(xy): return [((x - X0) * Z, (y - Y0) * Z) for x, y in xy]
def poly(g, fill, outline=None, w=1):
    for q in getattr(g, 'geoms', [g]):
        if q.geom_type != 'Polygon' or q.is_empty: continue
        d.polygon(T(q.exterior.coords), fill=fill, outline=outline, width=w)
        for h in q.interiors: d.polygon(T(h.coords), fill=(255, 255, 255, 0), outline=outline)
PS = pickle.load(open('passage.pkl', 'rb'))
for r in PS['open_spaces']: poly(r, (255, 230, 150, 60), (200, 150, 0, 255), 2)
poly(PS['corridor'], (150, 150, 230, 90))
for p in PS['passage']: poly(p, (0, 170, 80, 120), (0, 120, 50, 255), 2)
for c, g in load_walls()['bodies']: poly(g, (60, 60, 60, 200))
im = Image.alpha_composite(im, ov).convert('RGB')
F = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 22); dd = ImageDraw.Draw(im)
dd.rectangle((10, 10, 1010, 120), fill='white', outline='black')
dd.text((20, 16), f'Зона прохода в open space — схематично; ширина ≥ {round(PS["width_mm"])} мм ({PS.get("width_from", "задано")})', fill='black', font=F)
dd.rectangle((20, 52, 50, 72), fill=(0, 170, 80)); dd.text((60, 50), 'проход: свободный пол, куда входит полоса этой ширины; углы острые, края — прямые', fill='black', font=F)
dd.rectangle((20, 84, 50, 104), fill=(150, 150, 230)); dd.text((60, 82), 'коридор — заливка исходника; жёлтый контур — open space', fill='black', font=F)
im.save(out); print(out, im.size)
