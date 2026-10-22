# contact sheet: source around given prims, the prim in red, current walls in blue: strokesheet.py ids.json out.png [N]
import pickle, sys, json, math
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from common import load, pts, PDF
import pymupdf as fitz
from PIL import Image, ImageDraw, ImageFont
ids = json.load(open(sys.argv[1])); out = sys.argv[2]; N = int(sys.argv[3]) if len(sys.argv) > 3 else 30
P = load(); W = pickle.load(open('walls_fixed.pkl' if __import__('os').path.exists('walls_fixed.pkl') else 'walls.pkl', 'rb'))['Wpt']
pg = fitz.open(PDF)[0]; f = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 11)
T = 220; cols = 6; ids = ids[:N]
sh = Image.new('RGB', (cols * (T + 4), ((len(ids) + cols - 1) // cols) * (T + 16)), 'white'); d_ = ImageDraw.Draw(sh)
for n, i in enumerate(ids):
    q = pts(P[i]); cx = sum(x for x, y in q) / len(q); cy = sum(y for x, y in q) / len(q); h = 8; Z = T / (2 * h)
    pix = pg.get_pixmap(matrix=fitz.Matrix(Z, Z), clip=fitz.Rect(cx - h, cy - h, cx + h, cy + h))
    im = Image.frombytes('RGB', (pix.width, pix.height), pix.samples).resize((T, T))
    im = Image.blend(im, Image.new('RGB', im.size, 'white'), 0.45); dr = ImageDraw.Draw(im)
    for k, v in W.items():
        for g in v:
            for p in ([g] if g.geom_type == 'Polygon' else list(g.geoms)):
                bb = p.bounds
                if bb[2] < cx - h or bb[0] > cx + h or bb[3] < cy - h or bb[1] > cy + h: continue
                dr.line([((x - cx + h) * Z, (y - cy + h) * Z) for x, y in p.exterior.coords], fill=(0, 0, 220), width=1)
    dr.line([((x - cx + h) * Z, (y - cy + h) * Z) for x, y in q], fill=(230, 0, 0), width=3)
    sh.paste(im, ((n % cols) * (T + 4), (n // cols) * (T + 16) + 14)); d_.text(((n % cols) * (T + 4) + 2, (n // cols) * (T + 16)), f'{i} ({cx:.0f},{cy:.0f})', fill=(0, 0, 0), font=f)
sh.save(out); print(sh.size)
