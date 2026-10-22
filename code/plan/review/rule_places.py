# Places of a reclass rule on one sheet (01.10.2026, code 005; plan/rules/70 rule 10: a rule that is on by default is kept
#   only after all its places on all floors have been seen). Per place - the source and the objects of the rule's key in
#   their colour over the faded source; the caption gives what reclass.json says of the place. Run from the floor folder:
#   python3 review/rule_places.py RULE KEY out.png [half_pt=10] [title] [max_places=60]
#   RULE - a key of reclass.json 'places' (R2, K2, M, K, ...); KEY - the object key to draw (column, mark, mask, ...)
import sys, os, json, pickle
import pymupdf
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, os.getcwd()); sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import cfg, load
RULE, KEY, out = sys.argv[1], sys.argv[2], sys.argv[3]
HALF = float(sys.argv[4]) if len(sys.argv) > 4 else 10.0
TITLE = sys.argv[5] if len(sys.argv) > 5 else os.path.basename(os.getcwd())
MAXN = int(sys.argv[6]) if len(sys.argv) > 6 else 60
R = json.load(open('reclass.json')).get('places', {}).get(RULE, [])[:MAXN]
P = load(); I = pickle.load(open('inst_final.pkl', 'rb'))
pg = pymupdf.open(cfg.PDF)[0]; PX = 240; Z = PX / (2 * HALF)
FB = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 12)
FS = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 10)
def g_(i): p = P[i]; return p[4] if p[0] != 'c' else [p[4][0], p[4][3]]
mine = [i for q in I if q['key'] == KEY for i in q['prims']]
def tile(at):
    b = (at[0] - HALF, at[1] - HALF, at[0] + HALF, at[1] + HALF)
    pix = pg.get_pixmap(matrix=pymupdf.Matrix(Z, Z), clip=pymupdf.Rect(*b))
    a = Image.frombytes('RGB', (pix.width, pix.height), pix.samples).resize((PX, PX))
    o = Image.blend(a, Image.new('RGB', a.size, 'white'), 0.7); d = ImageDraw.Draw(o)
    for i in mine:
        g = g_(i); xs = [v[0] for v in g]; ys = [v[1] for v in g]
        if max(xs) < b[0] or min(xs) > b[2] or max(ys) < b[1] or min(ys) > b[3]: continue
        pts = [((v[0] - b[0]) * Z, (v[1] - b[1]) * Z) for v in g]
        if P[i][0] == 'qu' and len(pts) >= 3: d.polygon(pts, outline=(230, 0, 120))
        elif len(pts) > 1: d.line(pts, fill=(230, 0, 120), width=2)
    return a, o
rows = []
for n, r in enumerate(R):
    at = r.get('at_pt') or r.get('at')
    if not at: continue
    a, o = tile(at)
    extra = {k: v for k, v in r.items() if k not in ('at_pt', 'at', 'misc')}
    cap = f"#{n + 1} ({at[0]:.1f}; {at[1]:.1f}) " + json.dumps(extra, ensure_ascii=False)[:70]
    row = Image.new('RGB', (2 * PX + 10, PX + 18), 'white'); dr = ImageDraw.Draw(row)
    dr.text((2, 2), cap, fill=(0, 0, 0), font=FS); row.paste(a, (0, 18)); row.paste(o, (PX + 10, 18)); rows.append(row)
if not rows: print('no places', RULE); sys.exit(0)
COLS = 3; W_ = COLS * (rows[0].width + 8); H_ = 26 + ((len(rows) + COLS - 1) // COLS) * (rows[0].height + 8)
Sh = Image.new('RGB', (W_, H_), (225, 225, 225)); ds = ImageDraw.Draw(Sh)
ds.text((6, 4), f'{TITLE}: правило {RULE}, объекты {KEY} — {len(rows)} мест (слева исходник, справа объекты цветом)', fill=(0, 0, 0), font=FB)
for k, r in enumerate(rows): Sh.paste(r, (8 + (k % COLS) * (r.width + 8), 26 + (k // COLS) * (r.height + 8)))
Sh.save(out); print(out, Sh.size, len(rows))
