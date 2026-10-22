# the same place (common frame of crossfloor.json, mm) on several floors: xf_multi_view.py crossfloor.json X Y half out.png f1 f2 ...
import sys, json, pickle, os, importlib.util
import numpy as np, pymupdf as fitz
from PIL import Image, ImageDraw, ImageFont
J = json.load(open(sys.argv[1])); X, Y, H = map(float, sys.argv[2:5]); out = sys.argv[5]; FL = sys.argv[6:]
NAME = {'f1': '1 этаж', 'f2': '2 этаж', 'f3b': '3 этаж', 'f4r': '4 этаж', 'f5r': '5 этаж', 'f6': '6 этаж'}
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
    return kx, ky, pickle.load(open(wf, 'rb'))['Wpt'], pdf
f = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 16)
col = {'ext': (200, 0, 0), 'cap': (0, 0, 220), 'gkl': (0, 150, 0), 'blk': (230, 120, 0)}
ims = []
for d in FL:
    r = J['registration'][d]; xm, ym = (X - r['tx']) / r['s'], (Y - r['ty']) / r['s']
    kx, ky, W, pdf = floor(d)
    cx, cy = (xm - kx[1]) / kx[0], (ym - ky[1]) / ky[0]; h = abs(H / kx[0]); T = 520; Z = T / (2 * h)
    pix = fitz.open(pdf)[0].get_pixmap(matrix=fitz.Matrix(Z, Z), clip=fitz.Rect(cx - h, cy - h, cx + h, cy + h))
    im = Image.frombytes('RGB', (pix.width, pix.height), pix.samples).resize((T, T))
    im = Image.blend(im, Image.new('RGB', im.size, 'white'), 0.3); dr = ImageDraw.Draw(im); s = T / (2 * h)
    for kk, v in W.items():
        for g in v:
            for p in ([g] if g.geom_type == 'Polygon' else list(getattr(g, 'geoms', []))):
                bb = p.bounds
                if bb[2] < cx - h or bb[0] > cx + h or bb[3] < cy - h or bb[1] > cy + h: continue
                dr.line([((x - cx + h) * s, (y - cy + h) * s) for x, y in p.exterior.coords], fill=col.get(kk, (0, 0, 0)), width=2)
    dr.rectangle([0, 0, 120, 24], fill='white'); dr.text((4, 3), NAME.get(d, d), fill=(0, 0, 0), font=f)
    ims.append(im)
sh = Image.new('RGB', (len(ims) * 526, 520), 'white')
for n, im in enumerate(ims): sh.paste(im, (n * 526, 0))
sh.save(out); print(sh.size)
