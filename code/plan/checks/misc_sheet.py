# Sheet of unclassified objects of one category (misc_context.json): groups by size (100 mm) and number of primitives,
#   the largest groups first, one example each over the source (object in red). misc_sheet.py <category> out.png [N]
import pickle, sys, json, collections, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import load, pts, PDF
import pymupdf as fitz
from PIL import Image, ImageDraw, ImageFont
cat, out = sys.argv[1], sys.argv[2]; N = int(sys.argv[3]) if len(sys.argv) > 3 else 24
P = load(); I = pickle.load(open('inst_final.pkl', 'rb')); J = json.load(open('misc_context.json'))
rows = [r for r in J['list'] if r['cat'] == cat]
G = collections.defaultdict(list)
for r in rows: G[(round(max(r['size_mm']) / 100), round(min(r['size_mm']) / 100), min(r['prims'], 30) // 3)].append(r)
grp = sorted(G.values(), key=lambda v: (-len(v), -max(v[0]['size_mm'])))[:N]
pg = fitz.open(PDF)[0]; f = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 11)
T = 200; cols = 6
sh = Image.new('RGB', (cols * (T + 4), ((len(grp) + cols - 1) // cols) * (T + 30)), 'white'); d_ = ImageDraw.Draw(sh)
for k, v in enumerate(grp):
    r = v[0]; ids = I[r['inst']]['prims']; q = [p for i in ids for p in pts(P[i])]
    b = (min(x for x, y in q), min(y for x, y in q), max(x for x, y in q), max(y for x, y in q))
    cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2; h = max(5, max(b[2] - b[0], b[3] - b[1]) * 0.75); Z = T / (2 * h)
    pix = pg.get_pixmap(matrix=fitz.Matrix(Z, Z), clip=fitz.Rect(cx - h, cy - h, cx + h, cy + h))
    im = Image.frombytes('RGB', (pix.width, pix.height), pix.samples).resize((T, T))
    im = Image.blend(im, Image.new('RGB', im.size, 'white'), 0.55); dr = ImageDraw.Draw(im)
    for i in ids:
        qq = [((x - cx + h) * Z, (y - cy + h) * Z) for x, y in pts(P[i])]
        if len(qq) > 1: dr.line(qq + ([qq[0]] if P[i][0] == 'qu' else []), fill=(230, 0, 0), width=2)
    x0, y0 = (k % cols) * (T + 4), (k // cols) * (T + 30)
    sh.paste(im, (x0, y0 + 28))
    d_.text((x0 + 2, y0), f"{len(v)} шт, {r['size_mm'][0]}×{r['size_mm'][1]} мм", fill=(0, 0, 0), font=f)
    d_.text((x0 + 2, y0 + 13), f"{r['prims']} прим., ({r['at_pt'][0]:.0f}, {r['at_pt'][1]:.0f})", fill=(90, 90, 90), font=f)
sh.save(out); print(cat, len(rows), 'groups', len(G), 'sheet', sh.size)
