# Sheet of the places of one gate7 check: for each place - the source (left) and what the result made of it (right:
# lines coloured by class over the grey source, the place in a red ring). Used to look at every place a check finds.
#   python3 checks/spot_sheet.py gate7.json S18* out.png [max=40] [R=10] [Z=14]      (floor folder)
import sys, os, json, pickle, math, collections
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np, pymupdf
from PIL import Image, ImageDraw, ImageFont
from common import cfg, pts
from own7 import Own, load_all, PART, GLAZ
J = json.load(open(sys.argv[1])); code = sys.argv[2]; out = sys.argv[3]
NMAX = int(sys.argv[4]) if len(sys.argv) > 4 else 40; R = float(sys.argv[5]) if len(sys.argv) > 5 else 10.0; Z = float(sys.argv[6]) if len(sys.argv) > 6 else 14
P, cls, I, WP, W = load_all()
O = Own(I, WP)
COL = {'WALL': (90, 90, 90), 'lpart': (200, 0, 200), 'lpartc': (200, 0, 200), 'gklpart': (0, 150, 0), 'glasspart': (0, 120, 255), 'railing': (0, 190, 190),
       'glass': (0, 90, 255), 'facade': (0, 180, 230), 'wallline': (120, 70, 20), 'column': (160, 160, 0), 'door': (230, 0, 0), 'door45': (230, 0, 0),
       'desk': (240, 120, 0), 'desk_o': (240, 120, 0), 'desk_src': (240, 120, 0), 'screen': (255, 170, 60), 'chair': (30, 80, 200), 'rack': (150, 110, 0),
       'wardrobe': (150, 110, 0), 'furn_src': (240, 90, 120), 'mtable': (240, 120, 0), 'stair': (120, 0, 160), 'loose': (255, 0, 0), 'misc': (255, 0, 0),
       'FREE': (255, 0, 0), 'mark': (128, 128, 128), 'wcacc': (0, 140, 90), 'monitor': (255, 0, 160)}
FB = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 15); FR = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 13)
pg = pymupdf.open(cfg.PDF)[0]
spots = J['checks'][code]['spots'][:NMAX]
T = int(2 * R * Z); NC = 3; cw = 2 * T + 24; ch = T + 54
sheet = Image.new('RGB', (NC * cw + 10, ((len(spots) + NC - 1) // NC) * ch + 70), 'white'); d0 = ImageDraw.Draw(sheet)
d0.text((10, 8), f'{code} — {J["checks"][code]["title"][:120]}', font=FB, fill=(0, 0, 0))
d0.text((10, 32), f'мест {J["checks"][code]["n"]}, показано {len(spots)}. Слева исходник, справа результат по классам: пурпур — перегородка без типа, зелёный — ГКЛ, синий — стекло, '
        'оранжевый — столы, красный — нераспознанное', font=FR, fill=(60, 60, 60))
idx = collections.defaultdict(list)
for i, p in enumerate(P):
    q = pts(p)
    if q: idx[(int(q[0][0] // 20), int(q[0][1] // 20))].append(i)
for n, s in enumerate(spots):
    cx, cy = s['at']; x0, y0 = cx - R, cy - R
    pix = pg.get_pixmap(matrix=pymupdf.Matrix(Z, Z), clip=pymupdf.Rect(cx - R, cy - R, cx + R, cy + R), alpha=False)
    A = Image.frombytes('RGB', (pix.width, pix.height), pix.samples).resize((T, T))
    g = np.asarray(A).astype(np.float32) @ np.array([0.299, 0.587, 0.114], dtype=np.float32); g = 255 - (255 - g) * 0.25
    B = Image.fromarray(np.repeat(g[..., None], 3, axis=2).astype(np.uint8)); dB = ImageDraw.Draw(B)
    def tr(v): return ((v[0] - x0) * Z, (v[1] - y0) * Z)
    for gx in range(int((cx - R - 20) // 20), int((cx + R + 20) // 20) + 1):
        for gy in range(int((cy - R - 20) // 20), int((cy + R + 20) // 20) + 1):
            for i in idx.get((gx, gy), []):
                p = P[i]
                if p[0] == 'qu' or cls[i] in ('sheet', 'axis', 'dim'): continue
                q = pts(p)
                if not any(abs(v[0] - cx) <= R + 1 and abs(v[1] - cy) <= R + 1 for v in q): continue
                ks = O.keys(i); k = O.key(i)
                c = COL.get(k, (60, 60, 60))
                dB.line([tr(v) for v in q], fill=c, width=max(2, int((p[1] or 0.24) * Z * 0.5)))
                if len(ks) > 1:
                    for k2 in ks - {k}:
                        if k2 in COL: dB.line([tr(v) for v in q], fill=COL[k2], width=1)
    for D_ in (A, B):
        dd = ImageDraw.Draw(D_); dd.ellipse([T / 2 - 18, T / 2 - 18, T / 2 + 18, T / 2 + 18], outline=(255, 0, 0), width=2)
    x = 6 + (n % NC) * cw; y = 60 + (n // NC) * ch
    sheet.paste(A, (x, y)); sheet.paste(B, (x + T + 6, y))
    d0.text((x, y + T + 3), f'{n + 1}. x {cx:.0f}, y {cy:.0f}: {s["why"][:80]}', font=FR, fill=(0, 0, 0))
    d0.text((x, y + T + 19), s['why'][80:160], font=FR, fill=(0, 0, 0))
sheet.save(out); print(out, sheet.size)
