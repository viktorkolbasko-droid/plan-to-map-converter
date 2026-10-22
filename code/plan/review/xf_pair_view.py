# side by side: floor A and floor B sources with their walls at a place given in the common frame (= floor A mm)
# usage: xf_pair_view.py crossfloor.json A B x_mm y_mm half_mm out.png   (run in the xf folder with floor symlinks)
import sys, json, pickle, os, importlib.util
import numpy as np
import pymupdf as fitz
from PIL import Image, ImageDraw, ImageFont
J = json.load(open(sys.argv[1])); A, B = sys.argv[2], sys.argv[3]
X, Y, H = float(sys.argv[4]), float(sys.argv[5]), float(sys.argv[6]); out = sys.argv[7]
def floor(d):
    spec = importlib.util.spec_from_file_location('cfg_' + d, os.path.join(d, 'cfg.py'))
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')); sys.path.insert(0, d)
    cfg = importlib.util.module_from_spec(spec); spec.loader.exec_module(cfg); sys.path.pop(0)
    AX_X, AX_XMM, AX_Y, AX_YMM = [list(getattr(cfg, k, [])) for k in ('AX_X', 'AX_XMM', 'AX_Y', 'AX_YMM')]
    if len(AX_X) >= 2 and len(AX_Y) >= 2: kx = np.polyfit(AX_X, AX_XMM, 1); ky = np.polyfit(AX_Y, AX_YMM, 1)
    else:
        k = cfg.MM_PER_PT; ox, oy = cfg.ORIGIN_PT; kx = np.array([k, -k * ox]); ky = np.array([-k, k * oy])
    wf = os.path.join(d, 'walls_fixed.pkl'); wf = wf if os.path.exists(wf) else os.path.join(d, 'walls.pkl')
    pdf = [os.path.join(d, f) for f in os.listdir(d) if f.lower().endswith('.pdf')][0]
    return cfg, kx, ky, pickle.load(open(wf, 'rb'))['Wpt'], pdf
f = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 14)
col = {'ext': (200, 0, 0), 'cap': (0, 0, 220), 'gkl': (0, 150, 0), 'blk': (230, 120, 0)}
ims = []
PR = J['pairs'].get(f'{A}-{B}', {}).get('registration')      # pair frame = floor A mm
for d in (A, B):
    r = dict(s=1.0, tx=0.0, ty=0.0) if d == A else PR
    xm, ym = (X - r['tx']) / r['s'], (Y - r['ty']) / r['s']            # common frame -> floor mm
    cfg, kx, ky, W, pdf = floor(d)
    cx, cy = (xm - kx[1]) / kx[0], (ym - ky[1]) / ky[0]; h = abs(H / kx[0])   # -> floor pt
    T = 700; Z = T / (2 * h)
    pg = fitz.open(pdf)[0]
    pix = pg.get_pixmap(matrix=fitz.Matrix(Z, Z), clip=fitz.Rect(cx - h, cy - h, cx + h, cy + h))
    im = Image.frombytes('RGB', (pix.width, pix.height), pix.samples).resize((T, T))
    im = Image.blend(im, Image.new('RGB', im.size, 'white'), 0.35); dr = ImageDraw.Draw(im); s = T / (2 * h)
    for kk, v in W.items():
        for g in v:
            for p in ([g] if g.geom_type == 'Polygon' else list(getattr(g, 'geoms', []))):
                bb = p.bounds
                if bb[2] < cx - h or bb[0] > cx + h or bb[3] < cy - h or bb[1] > cy + h: continue
                dr.line([((x - cx + h) * s, (y - cy + h) * s) for x, y in p.exterior.coords], fill=col.get(kk, (0, 0, 0)), width=2)
    dr.text((6, 6), f'{d}: ({cx:.0f}, {cy:.0f}) pt', fill=(0, 0, 0), font=f)
    ims.append(im)
sheet = Image.new('RGB', (ims[0].width * 2 + 10, ims[0].height), 'white'); sheet.paste(ims[0], (0, 0)); sheet.paste(ims[1], (ims[0].width + 10, 0))
sheet.save(out); print(sheet.size)
