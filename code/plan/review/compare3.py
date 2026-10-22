# Sheet "source | run A | run B" for chosen places: the source crop and the classification map of each run (classmap.py
#   colours: walls black, 'misc' red and thick, free light grey), a caption per row.
#   python3 compare3.py runA runB spots.json out.png [px=330] [labelA] [labelB]
#   spots.json: [["caption", cx, cy, half_pt], ...]
import sys, os, json
import pymupdf as fitz
from PIL import Image, ImageDraw, ImageFont
A, B, spots_f, out = sys.argv[1:5]
PX = int(sys.argv[5]) if len(sys.argv) > 5 else 330
LA = sys.argv[6] if len(sys.argv) > 6 else 'прогон 1'; LB = sys.argv[7] if len(sys.argv) > 7 else 'прогон 2'
here = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(here, 'classmap.py')).read().split('if BOX:')[0]
def loader(d):
    sys.argv = [sys.argv[0], d, os.path.join(__import__('tempfile').gettempdir(), '_c3'), '1']
    g = {'__name__': 'cm_' + os.path.basename(os.path.dirname(d))}; exec(compile(src, 'classmap.py', 'exec'), g); g['LEGEND'] = True; return g
GA, GB = loader(A), loader(B)
pg = fitz.open(os.path.join(A, GA['cfg'].PDF))[0]
FB = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 15)
FS = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 13)
rows = []
for cap, cx, cy, h in json.load(open(spots_f)):
    Z = PX / (2 * h); b = (cx - h, cy - h, cx + h, cy + h)
    pix = pg.get_pixmap(matrix=fitz.Matrix(Z, Z), clip=fitz.Rect(*b)); s = Image.frombytes('RGB', (pix.width, pix.height), pix.samples)
    tiles = [s.resize((PX, PX))]
    for g, tag in ((GA, 'a'), (GB, 'b')):
        g['Z'] = Z; g['tile'](*b, os.path.join(__import__('tempfile').gettempdir(), f'_c3{tag}.png')); tiles.append(Image.open(os.path.join(__import__('tempfile').gettempdir(), f'_c3{tag}.png')).convert('RGB').resize((PX, PX)))
    r = Image.new('RGB', (3 * PX + 20, PX + 44), 'white'); d = ImageDraw.Draw(r)
    d.text((4, 2), cap, fill=(0, 0, 0), font=FB)
    for k, (t, lab) in enumerate(zip(tiles, ('исходник', LA, LB))):
        r.paste(t, (k * (PX + 10), 40)); d.text((k * (PX + 10) + 4, 21), lab, fill=(90, 90, 90), font=FS)
    rows.append(r)
S = Image.new('RGB', (rows[0].width, sum(r.height for r in rows) + 6 * len(rows)), (225, 225, 225)); y = 0
for r in rows: S.paste(r, (0, y)); y += r.height + 6
S.save(out); print(out, S.size)
