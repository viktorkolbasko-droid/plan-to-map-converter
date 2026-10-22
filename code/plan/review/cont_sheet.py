# continuation clusters of geomqa.json with their strokes in magenta: cont_sheet.py out.png [json]  (floor folder)
import json, pickle, sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from common import PDF, walls_file
import pymupdf as fitz
from PIL import Image, ImageDraw, ImageFont
q = json.load(open(sys.argv[2] if len(sys.argv) > 2 else 'geomqa.json'))
P = pickle.load(open('seq.pkl', 'rb'))[0]
W = pickle.load(open(walls_file(), 'rb'))['Wpt']
CL = q['wall_hatch_continuation']
pg = fitz.open(PDF)[0]; f = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 11)
T = 300; cols = 4; rows = max(1, (len(CL) + cols - 1) // cols)
sheet = Image.new('RGB', (cols * (T + 6), rows * (T + 18)), 'white'); d_ = ImageDraw.Draw(sheet)
col = {'ext': (200, 0, 0), 'cap': (0, 0, 220), 'gkl': (0, 150, 0), 'blk': (230, 120, 0)}
for n, c in enumerate(CL):
    b = c['bbox_pt']; cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2; h = max(6, (b[2] - b[0]) / 2 + 4, (b[3] - b[1]) / 2 + 4); Z = T / (2 * h)
    pix = pg.get_pixmap(matrix=fitz.Matrix(Z, Z), clip=fitz.Rect(cx - h, cy - h, cx + h, cy + h))
    im = Image.frombytes('RGB', (pix.width, pix.height), pix.samples).resize((T, T))
    im = Image.blend(im, Image.new('RGB', im.size, 'white'), 0.45); dr = ImageDraw.Draw(im); s = T / (2 * h)
    for kk, v in W.items():
        for g in v:
            for p in ([g] if g.geom_type == 'Polygon' else list(getattr(g, 'geoms', []))):
                bb = p.bounds
                if bb[2] < cx - h or bb[0] > cx + h or bb[3] < cy - h or bb[1] > cy + h: continue
                dr.line([((x - cx + h) * s, (y - cy + h) * s) for x, y in p.exterior.coords], fill=col.get(kk, (0, 0, 0)), width=2)
    for i in c['ids']:
        dr.line([((x - cx + h) * s, (y - cy + h) * s) for x, y in P[i][4]], fill=(255, 0, 255), width=3)
    r_, c_ = divmod(n, cols); sheet.paste(im, (c_ * (T + 6), r_ * (T + 18) + 16))
    d_.text((c_ * (T + 6), r_ * (T + 18) + 2), f"#{n + 1} n{c['n']} ({cx:.0f},{cy:.0f}) {c['owners'][0][0]}{' SKIP' if c.get('skip') else ''}", fill='black', font=f)
sheet.save(sys.argv[1]); print(sheet.size, len(CL))
