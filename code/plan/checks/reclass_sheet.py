# Sheet of what reclass.py moved, by rule (reclass.json): reclass_sheet.py RULE out.png [N] [filter-into] [half_pt]
#   One tile per place: the source around the place's point (at_pt), the point circled; the header says where it went.
#   Places are read by their point, not by object number: the step cuts 'misc' objects into pieces in memory (29.09.2026),
#   so the numbers in reclass.json are not the numbers of assign2.pkl. Run in a floor folder, before (--dry) or after:
#   the fresher of reclass.json / reclass_dry.json is drawn, and the script prints which one (dry = not applied).
import sys, json, os, random
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import PDF, MM_PER_PT
import pymupdf as fitz
from PIL import Image, ImageDraw, ImageFont
rule, out = sys.argv[1], sys.argv[2]; N = int(sys.argv[3]) if len(sys.argv) > 3 else 30
flt = sys.argv[4] if len(sys.argv) > 4 and sys.argv[4] != '-' else None; H = float(sys.argv[5]) if len(sys.argv) > 5 else None
REPORT = max([p for p in ('reclass.json', 'reclass_dry.json') if os.path.exists(p)], key=os.path.getmtime)
J = json.load(open(REPORT)); print('report:', REPORT, '- dry run, not applied' if J.get('dry') else '- applied')
rows = [r for r in J['places'].get(rule, []) if flt is None or r.get('into') == flt]
random.seed(1); rows = rows if len(rows) <= N else random.sample(rows, N)
pg = fitz.open(PDF)[0]; f = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 11)
T = 220; cols = 6
sh = Image.new('RGB', (cols * (T + 4), max(1, (len(rows) + cols - 1) // cols) * (T + 16)), 'white'); d_ = ImageDraw.Draw(sh)
for k, r in enumerate(rows):
    x, y = r['at_pt']
    size_mm = max([v for key in ('size_mm', 'basin_mm') for v in (r.get(key) or [])] + [r.get('d_mm') or 0, r.get('span_mm') or 0, 600])
    h = H or max(6.0, 0.9 * size_mm / MM_PER_PT); Z = T / (2 * h)
    pix = pg.get_pixmap(matrix=fitz.Matrix(Z, Z), clip=fitz.Rect(x - h, y - h, x + h, y + h))
    im = Image.frombytes('RGB', (pix.width, pix.height), pix.samples).resize((T, T)); dr = ImageDraw.Draw(im)
    dr.ellipse([T / 2 - 8, T / 2 - 8, T / 2 + 8, T / 2 + 8], outline=(230, 0, 0), width=2)
    x0, y0 = (k % cols) * (T + 4), (k // cols) * (T + 16); sh.paste(im, (x0, y0 + 14))
    info = {kk: v for kk, v in r.items() if kk not in ('at_pt', 'misc')}
    d_.text((x0 + 2, y0), f"{rule} ({x:.0f},{y:.0f}) {info}"[:40], fill=(0, 0, 0), font=f)
sh.save(out); print(rule, len(J['places'].get(rule, [])), 'shown', len(rows), sh.size, 'from', REPORT)
