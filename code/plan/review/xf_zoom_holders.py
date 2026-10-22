# Place zoom for a crossfloor verdict (plan/rules/60 §11): floors A and B at one point of the pair frame - the source,
# each floor's recognised walls, and the floor's thin strokes coloured by who holds them: red - free or held by a
# class that may carry hatch (HATCH_KEYS, as crossfloor.py), orange - held by an object (not hatch evidence).
# Answers "whose strokes made the hatch evidence here": 30.09.2026 the false "missed" places were plant spokes,
# letters, a fire-hose reel, chords of a curved facade.
#   python3 xf_zoom_holders.py A B X_mm Y_mm HALF_mm out.png
# Run in the crossfloor folder (crossfloor.json and links to the floor folders). X_mm, Y_mm - point of the pair frame
# (at_mm of cap_differences); HALF_mm - half size of the view. XF_HATCH_MIN / XF_HATCH_MAX - stroke length window, pt.
import sys, json, pickle, os, importlib.util, collections, math
import numpy as np
import pymupdf as fitz
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # code/: cfg.py imports common_cfg
from PIL import Image, ImageDraw, ImageFont
HATCH_KEYS = ('lpart', 'lpartc', 'wallline', 'loose', 'misc', 'grey', 'roomsep', 'atrium', 'zone')
LMIN = float(os.environ.get('XF_HATCH_MIN', 1.0)); LMAX = float(os.environ.get('XF_HATCH_MAX', 14.0))
J = json.load(open('crossfloor.json'))
A, B, X, Y, H, out = sys.argv[1], sys.argv[2], float(sys.argv[3]), float(sys.argv[4]), float(sys.argv[5]), sys.argv[6]
def floor(d):
    spec = importlib.util.spec_from_file_location('cfg_' + d, os.path.join(d, 'cfg.py'))
    sys.path.insert(0, d); cfg = importlib.util.module_from_spec(spec); spec.loader.exec_module(cfg); sys.path.pop(0)
    AX_X, AX_XMM, AX_Y, AX_YMM = [list(getattr(cfg, k, [])) for k in ('AX_X', 'AX_XMM', 'AX_Y', 'AX_YMM')]
    if len(AX_X) >= 2 and len(AX_Y) >= 2: kx = np.polyfit(AX_X, AX_XMM, 1); ky = np.polyfit(AX_Y, AX_YMM, 1)
    else:
        k = cfg.MM_PER_PT; ox, oy = cfg.ORIGIN_PT; kx = np.array([k, -k * ox]); ky = np.array([-k, k * oy])
    wf = os.path.join(d, 'walls_fixed.pkl'); wf = wf if os.path.exists(wf) else os.path.join(d, 'walls.pkl')
    P = pickle.load(open(os.path.join(d, 'seq.pkl'), 'rb'))[0]; inst = pickle.load(open(os.path.join(d, 'inst_final.pkl'), 'rb'))
    return cfg, kx, ky, pickle.load(open(wf, 'rb'))['Wpt'], os.path.join(d, cfg.PDF), P, inst
col = {'ext': (200, 0, 0), 'cap': (0, 0, 220), 'gkl': (0, 150, 0), 'blk': (230, 120, 0)}
f = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 14)
PR = J['pairs'][f'{A}-{B}']['registration']; ims = []
for d in (A, B):
    r = dict(s=1.0, tx=0.0, ty=0.0) if d == A else PR
    xm, ym = (X - r['tx']) / r['s'], (Y - r['ty']) / r['s']
    cfg, kx, ky, W, pdf, P, inst = floor(d)
    cx, cy = (xm - kx[1]) / kx[0], (ym - ky[1]) / ky[0]; h = abs(H / kx[0])
    T = 900; pg = fitz.open(pdf)[0]; Z = T / (2 * h)
    pix = pg.get_pixmap(matrix=fitz.Matrix(Z, Z), clip=fitz.Rect(cx - h, cy - h, cx + h, cy + h))
    src = Image.frombytes('RGB', (pix.width, pix.height), pix.samples).resize((T, T))
    im = Image.blend(src, Image.new('RGB', src.size, 'white'), 0.55); dr = ImageDraw.Draw(im); s = T / (2 * h)
    own = {}
    for q in inst:
        for i in q['prims']: own[i] = q['key']
    cnt = collections.Counter()
    for i, p in enumerate(P):
        if p[0] != 'l': continue
        (ax, ay), (bx, by) = p[4]
        if not (cx - h <= (ax + bx) / 2 <= cx + h and cy - h <= (ay + by) / 2 <= cy + h): continue
        L = math.dist((ax, ay), (bx, by)); k = own.get(i, 'FREE')
        if LMIN <= L <= LMAX and (p[1] or 0) < 0.45:
            cnt[k] += 1; ev = k == 'FREE' or k in HATCH_KEYS
            dr.line([((ax - cx + h) * s, (ay - cy + h) * s), ((bx - cx + h) * s, (by - cy + h) * s)],
                    fill=(220, 0, 0) if ev else (255, 150, 0), width=2)
    for kk, v in W.items():
        for g in v:
            for p in ([g] if g.geom_type == 'Polygon' else list(getattr(g, 'geoms', []))):
                bb = p.bounds
                if bb[2] < cx - h or bb[0] > cx + h or bb[3] < cy - h or bb[1] > cy + h: continue
                dr.line([((x - cx + h) * s, (y - cy + h) * s) for x, y in p.exterior.coords], fill=col.get(kk, (0, 0, 0)), width=3)
    dr.ellipse([T / 2 - 6, T / 2 - 6, T / 2 + 6, T / 2 + 6], outline=(255, 0, 0), width=2)
    dr.text((6, 6), f'{d}: ({cx:.1f}, {cy:.1f}) pt  thin strokes {LMIN:g}-{LMAX:g} pt by holder: {dict(cnt.most_common(6))}', fill=(0, 0, 0), font=f)
    w = Image.new('RGB', (T * 2 + 10, T), 'white'); w.paste(src, (0, 0)); w.paste(im, (T + 10, 0)); ims.append(w)
    print(d, dict(cnt.most_common(8)))
sh = Image.new('RGB', (ims[0].width, ims[0].height * 2 + 10), 'white'); sh.paste(ims[0], (0, 0)); sh.paste(ims[1], (0, ims[0].height + 10)); sh.save(out); print(out)
