# Contact sheet of places: for each spot the source (left) and the classification map (right, colours of classmap.py,
#   'misc' red), label on top. spots.json: [["label", cx, cy, half_pt], ...].   python3 spots.py run_dir spots.json out.png [px=380] [cols=2]
import sys, os, json, pickle, importlib.util
import pymupdf as fitz
from PIL import Image, ImageDraw, ImageFont
sys.argv_saved = list(sys.argv)
d = sys.argv[1]; spots = json.load(open(sys.argv[2])); out = sys.argv[3]
PX = int(sys.argv[4]) if len(sys.argv) > 4 else 380; COLS = int(sys.argv[5]) if len(sys.argv) > 5 else 2
sys.argv = [sys.argv[0], d, os.path.join(__import__('tempfile').gettempdir(), '_unused'), '1']
here = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location('classmap_mod', os.path.join(here, 'classmap.py'))
src = open(os.path.join(here, 'classmap.py')).read().split('if BOX:')[0]      # definitions only
g = {'__name__': 'classmap_mod'}; exec(compile(src, 'classmap.py', 'exec'), g); g['LEGEND'] = False
pg = fitz.open(os.path.join(d, g['cfg'].PDF))[0]
F = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 13)
tiles = []
for lab, cx, cy, h in spots:
    Z = PX / (2 * h); g['Z'] = Z
    x0, y0, x1, y1 = cx - h, cy - h, cx + h, cy + h
    pix = pg.get_pixmap(matrix=fitz.Matrix(Z, Z), clip=fitz.Rect(x0, y0, x1, y1))
    a = Image.frombytes('RGB', (pix.width, pix.height), pix.samples)
    g['tile'](x0, y0, x1, y1, os.path.join(__import__('tempfile').gettempdir(), '_spot.png')); b = Image.open(os.path.join(__import__('tempfile').gettempdir(), '_spot.png'))
    t = Image.new('RGB', (2 * PX + 6, PX + 18), 'white'); t.paste(a.resize((PX, PX)), (0, 18)); t.paste(b.resize((PX, PX)), (PX + 6, 18))
    ImageDraw.Draw(t).text((2, 1), f'{lab}  ({cx}, {cy}) ±{h} pt', fill=(0, 0, 0), font=F); tiles.append(t)
rows = (len(tiles) + COLS - 1) // COLS; W = tiles[0].width; H = tiles[0].height
sheet = Image.new('RGB', (COLS * W + (COLS - 1) * 10, rows * H + (rows - 1) * 8), (235, 235, 235))
for n, t in enumerate(tiles): sheet.paste(t, ((n % COLS) * (W + 10), (n // COLS) * (H + 8)))
sheet.save(out); print(out, sheet.size)
