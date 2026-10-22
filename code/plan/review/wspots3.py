# Walls "source | run A | run B" (wallmap.py colours: ext red, cap blue, gkl green, blk orange over the faded source)
#   python3 wspots3.py runA runB spots.json out.png [px=300] [labelA] [labelB];  spots: [["caption", cx, cy, half], ...]
import sys, os, json, subprocess
import pymupdf as fitz
from PIL import Image, ImageDraw, ImageFont
A, B, sp, out = sys.argv[1:5]; PX = int(sys.argv[5]) if len(sys.argv) > 5 else 300
LA = sys.argv[6] if len(sys.argv) > 6 else 'стены, прогон 1'; LB = sys.argv[7] if len(sys.argv) > 7 else 'стены, прогон 2'
here = os.path.dirname(os.path.abspath(__file__))
pg = fitz.open(os.path.join(A, [l.split('=')[1].split(';')[0].strip().strip("'") for l in open(os.path.join(A, 'cfg.py')) if l.startswith('PDF=')][0]))[0]
FB = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 15); FS = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 13)
rows = []
for cap, x, y, h in json.load(open(sp)):
    Z = PX / (2 * h); b = (x - h, y - h, x + h, y + h)
    pix = pg.get_pixmap(matrix=fitz.Matrix(Z, Z), clip=fitz.Rect(*b)); ims = [Image.frombytes('RGB', (pix.width, pix.height), pix.samples)]
    for d, t in ((A, 'a'), (B, 'b')):
        subprocess.run(['python3', os.path.join(here, 'wallmap.py'), d, 'walls_fixed.pkl', os.path.join(__import__('tempfile').gettempdir(), '_w3') + t, str(Z), '1', '1'] + [str(v) for v in b], capture_output=True)
        ims.append(Image.open(os.path.join(__import__('tempfile').gettempdir(), '_w3') + t + '.png').convert('RGB'))
    ims = [i.resize((PX, PX)) for i in ims]
    r = Image.new('RGB', (3 * PX + 20, PX + 42), 'white'); d = ImageDraw.Draw(r); d.text((4, 2), cap, fill=(0, 0, 0), font=FB)
    for k, (im, lab) in enumerate(zip(ims, ('исходник', LA, LB))):
        r.paste(im, (k * (PX + 10), 40)); d.text((k * (PX + 10) + 4, 21), lab, fill=(90, 90, 90), font=FS)
    rows.append(r)
S = Image.new('RGB', (rows[0].width, sum(r.height for r in rows) + 6 * len(rows)), (225, 225, 225)); yy = 0
for r in rows: S.paste(r, (0, yy)); yy += r.height + 6
S.save(out); print(out, S.size)
