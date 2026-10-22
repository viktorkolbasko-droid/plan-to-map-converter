# Sheet "source / before / after" for the places the owner pointed at (plan/rules/50 §5).
# Usage: python3 compare_spots.py spots.json out.png OLD.svg OLD_full.png NEW.svg NEW_full.png
#   spots.json: [{"title": "...", "box": [x0,y0,x1,y1]}]  (pt, display coords)
import sys, json, re
import pymupdf as fitz
from PIL import Image, ImageDraw, ImageFont
from common import kx, ky, PDF
Image.MAX_IMAGE_PIXELS = None
spots = json.load(open(sys.argv[1])); out = sys.argv[2]
class Full:
    def __init__(self, src, png):
        s = open(src).read(4000); vb = re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', s); self.Wd = float(vb.group(1))
        m = re.search(r'translate\(([-\d.]+),([-\d.]+)\) scale\(1,-1\)', open(src).read()); self.TX, self.TY = float(m.group(1)), float(m.group(2))
        self.im = Image.open(png).convert('RGB'); self.k = self.im.width / self.Wd
    def crop(self, x0, y0, x1, y1, W):
        mm = lambda p: (kx[0] * p[0] + kx[1], ky[0] * p[1] + ky[1]); a = mm((x0, y0)); b = mm((x1, y1))
        X0 = (min(a[0], b[0]) + self.TX) * self.k; X1 = (max(a[0], b[0]) + self.TX) * self.k
        Y0 = (self.TY - max(a[1], b[1])) * self.k; Y1 = (self.TY - min(a[1], b[1])) * self.k
        c = self.im.crop((int(X0), int(Y0), int(X1), int(Y1))); return c.resize((W, int(W * c.height / max(c.width, 1))), Image.LANCZOS)
OLD = Full(sys.argv[3], sys.argv[4]); NEW = Full(sys.argv[5], sys.argv[6])
pg = fitz.open(PDF)[0]
f = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 22); fs = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 20)
W = 620; G = 16; rows = []
for sp in spots:
    x0, y0, x1, y1 = sp['box']; z = W / (x1 - x0)
    pix = pg.get_pixmap(matrix=fitz.Matrix(z, z), clip=fitz.Rect(x0, y0, x1, y1)); a = Image.frombytes('RGB', (pix.width, pix.height), pix.samples)
    b = OLD.crop(x0, y0, x1, y1, W); c = NEW.crop(x0, y0, x1, y1, W); h = max(a.height, b.height, c.height)
    row = Image.new('RGB', (3 * W + 2 * G, h + 44), 'white'); d = ImageDraw.Draw(row); d.text((4, 8), sp['title'], fill=(0, 0, 0), font=f)
    for k, im in enumerate((a, b, c)):
        x = k * (W + G); row.paste(im, (x, 44)); d.rectangle([x, 44, x + W - 1, 44 + im.height - 1], outline=(170, 170, 170))
    rows.append(row)
hdr = Image.new('RGB', (3 * W + 2 * G, 40), 'white'); d = ImageDraw.Draw(hdr)
for k, t in enumerate(('Исходный PDF (Revit)', 'Было — прошлая версия', 'Стало — исправлено')):
    d.text((k * (W + G) + 6, 8), t, fill=(60, 60, 60) if k < 2 else (0, 110, 40), font=fs)
H = 40 + sum(r.height + 24 for r in rows); img = Image.new('RGB', (3 * W + 2 * G, H), 'white'); img.paste(hdr, (0, 0)); y = 40
for r in rows: img.paste(r, (0, y)); y += r.height + 24
img.save(out, optimize=True); print(img.size)
