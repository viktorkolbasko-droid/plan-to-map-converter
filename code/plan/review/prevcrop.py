# crop of the delivered preview (whole SVG at 6000 px) + the source at the same place: prevcrop.py x0 y0 x1 y1 out [W]
import re, sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from common import kx, ky, SVG, PDF, OUT
import pymupdf as fitz
from PIL import Image
Image.MAX_IMAGE_PIXELS = None
x0, y0, x1, y1 = map(float, sys.argv[1:5]); out = sys.argv[5]; Wd = int(sys.argv[6]) if len(sys.argv) > 6 else 800
s = open(SVG).read(4000)
vb = [float(v) for v in re.search(r'viewBox="([^"]+)"', s).group(1).split()]
m = re.search(r'translate\(([-\d.]+),([-\d.]+)\) scale\(1,-1\)', open(SVG).read()); TX, TY = float(m.group(1)), float(m.group(2))
im = Image.open(OUT + '_preview.png'); k = im.width / vb[2]
def px(p):
    mx, my = kx[0] * p[0] + kx[1], ky[0] * p[1] + ky[1]
    return ((mx + TX - vb[0]) * k, (TY - my - vb[1]) * k)
a, b = px((x0, y0)), px((x1, y1))
c = im.crop((int(min(a[0], b[0])), int(min(a[1], b[1])), int(max(a[0], b[0])), int(max(a[1], b[1])))).convert('RGB')
c = c.resize((Wd, int(Wd * c.height / max(c.width, 1))))
pg = fitz.open(PDF)[0]; Z = Wd / (x1 - x0)
pix = pg.get_pixmap(matrix=fitz.Matrix(Z, Z), clip=fitz.Rect(x0, y0, x1, y1))
sr = Image.frombytes('RGB', (pix.width, pix.height), pix.samples)
sh = Image.new('RGB', (Wd, sr.height + c.height + 10), 'white'); sh.paste(sr, (0, 0)); sh.paste(c, (0, sr.height + 10)); sh.save(out); print(sh.size)
