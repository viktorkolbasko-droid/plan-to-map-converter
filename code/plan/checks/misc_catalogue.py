# Catalogue sheet for the owner: chosen examples of unclassified objects, each with its label.
#   misc_catalogue.py spec.json out.png - spec: [[floor_dir, x_pt, y_pt, "label", "counts"], ...] (work dir as cwd)
import pickle, sys, json, os, math, textwrap, importlib.util
import pymupdf as fitz
from PIL import Image, ImageDraw, ImageFont
spec = json.load(open(sys.argv[1])); out = sys.argv[2]
f = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 12); fb = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 12)
T = 230; cols = 5; LH = 58
sh = Image.new('RGB', (cols * (T + 6), ((len(spec) + cols - 1) // cols) * (T + LH + 6)), 'white'); d_ = ImageDraw.Draw(sh)
CACHE = {}
for k, (fl, x, y, label, cnt) in enumerate(spec):
    if fl not in CACHE:
        sys.path.insert(0, os.path.join(os.getcwd(), fl))
        P = pickle.load(open(os.path.join(fl, 'seq.pkl'), 'rb'))[0]; I = pickle.load(open(os.path.join(fl, 'inst_final.pkl'), 'rb'))
        J = json.load(open(os.path.join(fl, 'misc_context.json')))
        pdf = [os.path.join(fl, g) for g in os.listdir(fl) if g.lower().endswith('.pdf')][0]
        CACHE[fl] = (P, I, J, fitz.open(pdf)[0])
    P, I, J, pg = CACHE[fl]
    r = min(J['list'], key=lambda r: math.dist(r['at_pt'], (x, y)))
    def pts(p):
        k_, w, sc, fc, g, di = p
        if k_ == 'l': return list(g)
        if k_ == 'c':
            import numpy as np
            return [((1-t)**3*g[0][0]+3*(1-t)**2*t*g[1][0]+3*(1-t)*t*t*g[2][0]+t**3*g[3][0], (1-t)**3*g[0][1]+3*(1-t)**2*t*g[1][1]+3*(1-t)*t*t*g[2][1]+t**3*g[3][1]) for t in np.linspace(0, 1, 12)]
        return list(g) + [g[0]]
    ids = I[r['inst']]['prims']; q = [p for i in ids for p in pts(P[i])]
    b = (min(a for a, _ in q), min(c for _, c in q), max(a for a, _ in q), max(c for _, c in q))
    cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2; h = max(5, max(b[2] - b[0], b[3] - b[1]) * 0.75); Z = T / (2 * h)
    pix = pg.get_pixmap(matrix=fitz.Matrix(Z, Z), clip=fitz.Rect(cx - h, cy - h, cx + h, cy + h))
    im = Image.frombytes('RGB', (pix.width, pix.height), pix.samples).resize((T, T))
    im = Image.blend(im, Image.new('RGB', im.size, 'white'), 0.5); dr = ImageDraw.Draw(im)
    for i in ids:
        qq = [((a - cx + h) * Z, (c - cy + h) * Z) for a, c in pts(P[i])]
        if len(qq) > 1: dr.line(qq, fill=(230, 0, 0), width=2)
    x0, y0 = (k % cols) * (T + 6), (k // cols) * (T + LH + 6)
    sh.paste(im, (x0, y0 + LH)); d_.rectangle([x0, y0 + LH, x0 + T - 1, y0 + LH + T - 1], outline=(180, 180, 180))
    yy = y0 + 2
    for n_, line in enumerate(textwrap.wrap(f'{k+1}. {label}', 30)[:3]): d_.text((x0 + 2, yy), line, fill=(0, 0, 0), font=fb); yy += 14
    d_.text((x0 + 2, y0 + LH - 15), cnt, fill=(70, 70, 70), font=f)
sh.save(out); print(sh.size)
