# open ends of room separation lines (rooms.json) on the source with our walls: roomends_sheet.py out.png  (floor folder)
import json, pickle, sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from common import PDF, walls_file
import pymupdf as fitz
from PIL import Image, ImageDraw, ImageFont
r = json.load(open(sys.argv[2] if len(sys.argv) > 2 else 'rooms.json'))
W = pickle.load(open(walls_file(), 'rb'))['Wpt']
E = r['open_ends']
pg = fitz.open(PDF)[0]; f = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 11)
T = 260; cols = 5; rows = max(1, (len(E) + cols - 1) // cols); h = 14
sheet = Image.new('RGB', (cols * (T + 6), rows * (T + 18)), 'white'); d_ = ImageDraw.Draw(sheet)
col = {'ext': (200, 0, 0), 'cap': (0, 0, 220), 'gkl': (0, 150, 0), 'blk': (230, 120, 0)}
for n, e in enumerate(E):
    cx, cy = e['at_pt']; Z = T / (2 * h)
    pix = pg.get_pixmap(matrix=fitz.Matrix(Z, Z), clip=fitz.Rect(cx - h, cy - h, cx + h, cy + h))
    im = Image.frombytes('RGB', (pix.width, pix.height), pix.samples).resize((T, T))
    dr = ImageDraw.Draw(im); s = T / (2 * h)
    for kk, v in W.items():
        for g in v:
            for p in ([g] if g.geom_type == 'Polygon' else list(getattr(g, 'geoms', []))):
                bb = p.bounds
                if bb[2] < cx - h or bb[0] > cx + h or bb[3] < cy - h or bb[1] > cy + h: continue
                dr.line([((x - cx + h) * s, (y - cy + h) * s) for x, y in p.exterior.coords], fill=col.get(kk, (0, 0, 0)), width=1)
    dr.ellipse([T / 2 - 6, T / 2 - 6, T / 2 + 6, T / 2 + 6], outline=(255, 0, 0), width=2)
    r_, c_ = divmod(n, cols); sheet.paste(im, (c_ * (T + 6), r_ * (T + 18) + 16))
    d_.text((c_ * (T + 6), r_ * (T + 18) + 2), f"#{n + 1} {e['gap_mm']} мм до {e['on']} ({cx:.0f},{cy:.0f})", fill='black', font=f)
sheet.save(sys.argv[1]); print(sheet.size, len(E))
