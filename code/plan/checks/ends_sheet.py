# Sheet of check 3.9a (29.09.2026): the open ends of objects that should be closed whose continuation in the source was
#   left in 'misc' - the object is not assembled whole there, or the source is drawn so. One tile per end: the source around
#   the end point, the object in blue, the 'misc' pieces nearby in red, the end circled.
# Run in a floor folder after ends_audit.py: python3 ends_sheet.py out.png [N=30] [kind="piece left unclassified"]
import pickle, sys, os, json, random, collections
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import load, pts, PDF
import pymupdf as fitz
from PIL import Image, ImageDraw, ImageFont
out = sys.argv[1]; N = int(sys.argv[2]) if len(sys.argv) > 2 else 30; KIND = sys.argv[3] if len(sys.argv) > 3 else 'piece left unclassified'
P = load(); inst, free = pickle.load(open('assign2.pkl', 'rb')); J = json.load(open('ends_audit.json'))
closed = {k for k, v in J['by_key'].items() if not v.get('open_by_nature')}
rows = [r for r in J['splits'] if r['kind'] == KIND and r['key'] in closed]
# a sample spread over the classes: at most N // 3 of one class
random.seed(3); random.shuffle(rows); per = collections.Counter(); sel = []
for r in rows:
    if per[r['key']] >= max(1, N // 3): continue
    per[r['key']] += 1; sel.append(r)
    if len(sel) >= N: break
pg = fitz.open(PDF)[0]; f = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 11)
T = 220; cols = 6; h = 10.0; Z = T / (2 * h)
misc = [i for q in inst if q['key'] == 'misc' for i in q['prims']]
sh = Image.new('RGB', (cols * (T + 4), max(1, (len(sel) + cols - 1) // cols) * (T + 16)), 'white'); d = ImageDraw.Draw(sh)
for k, r in enumerate(sel):
    x, y = r['at_pt']
    pix = pg.get_pixmap(matrix=fitz.Matrix(Z, Z), clip=fitz.Rect(x - h, y - h, x + h, y + h))
    im = Image.frombytes('RGB', (pix.width, pix.height), pix.samples).resize((T, T)); im = Image.blend(im, Image.new('RGB', im.size, 'white'), 0.5)
    dr = ImageDraw.Draw(im)
    def draw(ids, col):
        for i in ids:
            q = [((a - x + h) * Z, (b - y + h) * Z) for a, b in pts(P[i])]
            if len(q) > 1 and any(0 <= u <= T and 0 <= v <= T for u, v in q): dr.line(q, fill=col, width=2)
    draw(inst[r['inst']]['prims'] if r['inst'] < len(inst) else [], (0, 60, 220)); draw(misc, (230, 0, 0))
    dr.ellipse([T / 2 - 7, T / 2 - 7, T / 2 + 7, T / 2 + 7], outline=(0, 160, 0), width=2)
    x0, y0 = (k % cols) * (T + 4), (k // cols) * (T + 16); sh.paste(im, (x0, y0 + 14))
    d.text((x0 + 2, y0), f"{r['key']} ({x:.0f},{y:.0f})", fill=(0, 0, 0), font=f)
sh.save(out); print(KIND, len(rows), 'shown', len(sel), dict(per), sh.size)
