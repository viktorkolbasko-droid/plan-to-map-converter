# contact sheet of every place geomqa.py asks to look at: qa_sheet.py out.png  (run in a floor folder)
import json, pickle, sys, math
import os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from common import PDF, kx, ky, cfg, walls_file
import pymupdf as fitz
from PIL import Image, ImageDraw, ImageFont
q = json.load(open('geomqa.json'))
W = pickle.load(open(walls_file(), 'rb'))['Wpt']
pt = lambda m: ((m[0] - kx[1]) / kx[0], (m[1] - ky[1]) / ky[0])
items = []
for g in q['wall_gaps_unexplained']: items.append(('разрыв %d мм %s' % (g['gap_mm'], {'opening (nothing drawn)': 'проём', 'outline wall': 'контур', 'lines - look': 'смотреть'}.get(g.get('source'), '')), pt(g['at_mm']), 14))
for d in q['doors_detail']:
    items.append(('дверь h%d c%d o%d%s' % (d['hinge_gap'], d['closed_gap'], d['overlap'], ' пара' if d['pair'] else ''), pt(d['at_mm']), 16))
for x in q.get('facade_ends', []):
    if x['to_carrier_mm'] > 100 or x['glass_to_carrier_mm'] is None or x['glass_to_carrier_mm'] > 20:
        items.append(('витраж: до носителя %d, стекло %s мм' % (x['to_carrier_mm'], x['glass_to_carrier_mm']), tuple(x['end_pt']), 14))
for o in q['wall_class_overlaps']: items.append(('наложение %s %d мм²' % ('/'.join(o['classes']), o['area_mm2']), pt(o['at_mm']), 10))
skip = getattr(cfg, 'WALL_CONT_SKIP', [])
for c in q['wall_hatch_continuation']:
    b = c['bbox_pt']; sk = any(z[0] <= b[0] and b[2] <= z[2] and z[1] <= b[1] and b[3] <= z[3] for z in skip)
    items.append(('продолж. %d%s' % (c['n'], ' SKIP' if sk else ''), ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2), max(12, (b[2] - b[0]) / 2 + 6, (b[3] - b[1]) / 2 + 6)))
for e in q.get('near_axis_real_unjustified', []): items.append(('ось %s' % e.get('kind', ''), tuple(e.get('at_pt', (0, 0))), 10))
print(len(items), [i[0] for i in items])
if not items: sys.exit()
pg = fitz.open(PDF)[0]; f = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 11)
T = 260; cols = 5; rows = (len(items) + cols - 1) // cols
sheet = Image.new('RGB', (cols * (T + 6), rows * (T + 18)), 'white'); d_ = ImageDraw.Draw(sheet)
col = {'ext': (200, 0, 0), 'cap': (0, 0, 220), 'gkl': (0, 150, 0), 'blk': (230, 120, 0)}
for n, (lab, (cx, cy), h) in enumerate(items):
    Z = T / (2 * h)
    pix = pg.get_pixmap(matrix=fitz.Matrix(Z, Z), clip=fitz.Rect(cx - h, cy - h, cx + h, cy + h))
    im = Image.frombytes('RGB', (pix.width, pix.height), pix.samples).resize((T, T))
    im = Image.blend(im, Image.new('RGB', im.size, 'white'), 0.45); dr = ImageDraw.Draw(im); s = T / (2 * h)
    for kk, v in W.items():
        for g in v:
            for p in ([g] if g.geom_type == 'Polygon' else list(getattr(g, 'geoms', []))):
                b = p.bounds
                if b[2] < cx - h or b[0] > cx + h or b[3] < cy - h or b[1] > cy + h: continue
                for r in [p.exterior] + list(p.interiors):
                    dr.line([((x - cx + h) * s, (y - cy + h) * s) for x, y in r.coords], fill=col.get(kk, (0, 0, 0)), width=2)
    dr.ellipse([T / 2 - 4, T / 2 - 4, T / 2 + 4, T / 2 + 4], outline=(255, 0, 255), width=2)
    r_, c_ = divmod(n, cols); sheet.paste(im, (c_ * (T + 6), r_ * (T + 18) + 16))
    d_.text((c_ * (T + 6), r_ * (T + 18) + 2), f'#{n + 1} {lab} ({cx:.0f},{cy:.0f})', fill='black', font=f)
sheet.save(sys.argv[1]); print(sheet.size)
