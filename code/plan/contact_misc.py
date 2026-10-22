# Contact sheet of the largest unclassified clusters, to name them in cfg.MANUAL (plan/rules/20 §3.5).
# Usage: python3 contact_misc.py [N=40] [out.png]
import sys, pickle
import pymupdf as fitz
from PIL import Image, ImageDraw, ImageFont
from common import load, pts, PDF
N = int(sys.argv[1]) if len(sys.argv) > 1 else 40; out = sys.argv[2] if len(sys.argv) > 2 else 'misc_contact.png'
P = load(); inst = pickle.load(open('inst_final.pkl', 'rb'))
def bb(q):
    ps = [p for i in q['prims'] for p in pts(P[i])]; return (min(p[0] for p in ps), min(p[1] for p in ps), max(p[0] for p in ps), max(p[1] for p in ps))
ms = sorted([q for q in inst if q['key'] in ('misc',) and q['prims']], key=lambda q: -len(q['prims']))[:N]
pg = fitz.open(PDF)[0]; T = 260; cols = 5
f = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 12)
rows = (len(ms) + cols - 1) // cols; sheet = Image.new('RGB', (cols * (T + 10), rows * (T + 40)), 'white'); d = ImageDraw.Draw(sheet)
for k, q in enumerate(ms):
    b = bb(q); m = max(b[2] - b[0], b[3] - b[1]) * 0.35 + 4
    r = fitz.Rect(b[0] - m, b[1] - m, b[2] + m, b[3] + m); z = T / max(r.width, r.height)
    pix = pg.get_pixmap(matrix=fitz.Matrix(z, z), clip=r); im = Image.frombytes('RGB', (pix.width, pix.height), pix.samples)
    x, y = (k % cols) * (T + 10), (k // cols) * (T + 40); sheet.paste(im, (x, y + 28))
    dd = ImageDraw.Draw(sheet); dd.rectangle([x + (b[0] - r.x0) * z, y + 28 + (b[1] - r.y0) * z, x + (b[2] - r.x0) * z, y + 28 + (b[3] - r.y0) * z], outline=(220, 0, 0))
    d.text((x, y + 2), f'#{k} n={len(q["prims"])}', fill=(0, 0, 0), font=f); d.text((x, y + 14), f'({b[0]:.0f},{b[1]:.0f},{b[2]:.0f},{b[3]:.0f})', fill=(90, 90, 90), font=f)
sheet.save(out); print(out, len(ms))
