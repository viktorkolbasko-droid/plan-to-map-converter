# "Было — стало" on the delivered drawing itself: for each place - the source, the SVG of one run and the SVG of
# another, the same window side by side (svgcrop_lib renders the SVG window given in PDF pt). Unlike before_after.py,
# which colours primitives by class, this shows what the client gets: cut lines, door styles, A-23 outlines.
#   python3 review/ba_svg.py OLD.svg NEW.svg places.json out.png [W=520] ["было: …"] ["стало: …"] ["title"]
#   places.json: [{"n": 1, "title": "...", "box": [x0, y0, x1, y1], "note": "..."}, ...]   (pt, PDF display space)
# Run from a floor folder of either run (cfg.py, the PDF; both runs - the same source and the same cfg frame).
import os, sys, json, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pymupdf
from PIL import Image, ImageDraw, ImageFont
from common import cfg
from svgcrop_lib import crop_fast as crop
OLD, NEW, PL, OUT = sys.argv[1:5]
WD = int(sys.argv[5]) if len(sys.argv) > 5 else 520
LAB0 = sys.argv[6] if len(sys.argv) > 6 else 'было'
LAB1 = sys.argv[7] if len(sys.argv) > 7 else 'стало'
TITLE = sys.argv[8] if len(sys.argv) > 8 else 'Было — стало: исходник и выдача SVG'
FB = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 17)
FR = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 14)
pg = pymupdf.open(cfg.PDF)[0]
def src_img(b):
    z = WD / (b[2] - b[0])
    pix = pg.get_pixmap(matrix=pymupdf.Matrix(z, z), clip=pymupdf.Rect(*b), alpha=False)
    return Image.frombytes('RGB', (pix.width, pix.height), pix.samples)
def svg_img(svg, b):
    fd, p = tempfile.mkstemp(suffix='.png'); os.close(fd)
    crop(b[0], b[1], b[2], b[3], WD, p, src=svg)
    im = Image.open(p).convert('RGBA'); os.remove(p)
    bg = Image.new('RGBA', im.size, 'white'); bg.alpha_composite(im)
    return bg.convert('RGB')
tiles = []
for pl in json.load(open(PL)):
    b = pl['box']
    ims = [(src_img(b), 'исходник'), (svg_img(OLD, b), LAB0), (svg_img(NEW, b), LAB1)]
    h = max(im.height for im, _ in ims)
    notes = pl.get('note', '').split('\n') if pl.get('note') else []
    head = 30 + 18 * len(notes)
    tw = max([3 * WD + 40, int(FB.getlength(f"{pl['n']}. {pl['title']}")) + 20] + [int(FR.getlength(l_)) + 20 for l_ in notes])
    t = Image.new('RGB', (tw, h + head + 26), 'white'); d = ImageDraw.Draw(t)
    d.text((6, 4), f"{pl['n']}. {pl['title']}", font=FB, fill=(0, 0, 0))
    for k_, line in enumerate(notes): d.text((6, 28 + 18 * k_), line, font=FR, fill=(70, 70, 70))
    for k_, (im, lab) in enumerate(ims):
        x_ = 6 + k_ * (WD + 14)
        t.paste(im, (x_, head)); d.rectangle([x_, head, x_ + im.width - 1, head + im.height - 1], outline=(200, 200, 200))
        d.text((x_, head + h + 4), lab, font=FR, fill=(0, 0, 0))
    tiles.append(t)
Wt = max(t.width for t in tiles + [Image.new('RGB', (int(FB.getlength(TITLE)) + 20, 1))])
S = Image.new('RGB', (Wt, sum(t.height + 14 for t in tiles) + 44), 'white'); d = ImageDraw.Draw(S)
d.text((8, 10), TITLE, font=FB, fill=(0, 0, 0))
y = 40
for t in tiles: S.paste(t, (0, y)); y += t.height + 14
S.save(OUT, optimize=True); print(OUT, S.size)
