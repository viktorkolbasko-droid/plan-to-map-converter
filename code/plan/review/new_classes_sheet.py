# Sheet "new classes in place" (plan/rules/60 §9, ref/plan/10 §1, 30.09.2026): for each tile - the source, and the source
# faded with the primitives of the chosen classes drawn in colour. Counters and the ink diff do not show a class that
# took a wrong line; this sheet does. 30.09: the grate took two paving lines, the middle seat of a desk stayed
# furniture, a carpet-pattern stroke went to the zone - all three found here, none by the numbers.
# Make it after reclass of every floor the new rules touch and BEFORE the full export - one fix round, one export.
#   python3 new_classes_sheet.py spec.json out.png
# spec.json:
#   {"title": "What the answers changed: new classes in place", "work": "/home/claude/eng/work",
#    "tiles": [{"floor": "f1", "at": [161.7, 254.8], "half": 16, "keys": ["grate"],
#               "title": "Group 17 -> drainage grate, A-52", "sub": "floor 1, passage between the blocks"}, ...],
#    "colors": {"grate": [0, 90, 200]}}
#   floor - a folder under work (its cfg.py, seq.pkl, assign2.pkl after reclass); at, half - pt of that floor's sheet;
#   keys - object classes (inst key) to colour; colors - optional, over the defaults below.
import pickle, sys, os, json, importlib.util
import pymupdf as fitz
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # code/: cfg.py imports common_cfg
from PIL import Image, ImageDraw, ImageFont
FD = '/usr/share/fonts/truetype/dejavu/'
fb = ImageFont.truetype(FD + 'DejaVuSans-Bold.ttf', 17); f = ImageFont.truetype(FD + 'DejaVuSans.ttf', 14)
COL = {'grate': (0, 90, 200), 'mark': (200, 0, 160), 'chair_arm': (200, 90, 0), 'railing': (0, 140, 60), 'gate': (220, 0, 0),
       'curtain': (0, 120, 200), 'carpet': (120, 60, 180)}
def bez(g, n=12):
    out = []
    for k in range(n):
        t = k / (n - 1)
        out.append(((1 - t) ** 3 * g[0][0] + 3 * (1 - t) ** 2 * t * g[1][0] + 3 * (1 - t) * t * t * g[2][0] + t ** 3 * g[3][0],
                    (1 - t) ** 3 * g[0][1] + 3 * (1 - t) ** 2 * t * g[1][1] + 3 * (1 - t) * t * t * g[2][1] + t ** 3 * g[3][1]))
    return out
def pts(p):
    k, w, sc, fc, g, di = p
    if k == 'l': return list(g)
    if k == 'c': return bez(g)
    return list(g) + [g[0]]
CACHE = {}
def floor(work, fl):
    if fl not in CACHE:
        d = os.path.join(work, fl)
        spec = importlib.util.spec_from_file_location('cfg_' + fl, os.path.join(d, 'cfg.py'))
        sys.path.insert(0, d); cfg = importlib.util.module_from_spec(spec); spec.loader.exec_module(cfg); sys.path.pop(0)
        P = pickle.load(open(os.path.join(d, 'seq.pkl'), 'rb'))[0]; inst, free = pickle.load(open(os.path.join(d, 'assign2.pkl'), 'rb'))
        CACHE[fl] = (P, inst, fitz.open(os.path.join(d, cfg.PDF))[0])
    return CACHE[fl]
def main(spec_path, out):
    S = json.load(open(spec_path, encoding='utf-8')); work = S.get('work', '/home/claude/eng/work')
    col = dict(COL); col.update({k: tuple(v) for k, v in S.get('colors', {}).items()})
    T = 420; tiles = []
    for tl in S['tiles']:
        fl, c, h, keys = tl['floor'], tl['at'], tl['half'], set(tl['keys'])
        P, inst, pg = floor(work, fl)
        x0, y0, x1, y1 = c[0] - h, c[1] - h, c[0] + h, c[1] + h; Z = T / (2 * h)
        pix = pg.get_pixmap(matrix=fitz.Matrix(Z, Z), clip=fitz.Rect(x0, y0, x1, y1))
        src = Image.frombytes('RGB', (pix.width, pix.height), pix.samples).resize((T, T))
        im = Image.blend(src, Image.new('RGB', src.size, 'white'), 0.6); d = ImageDraw.Draw(im)
        n = 0
        for q in inst:
            if q['key'] not in keys or not q['prims']: continue
            cl = col.get(q['key'], (0, 0, 0)); hit = False
            for i in q['prims']:
                v = [((u - x0) * Z, (w - y0) * Z) for u, w in pts(P[i])]
                if any(0 <= a <= T and 0 <= b <= T for a, b in v) and len(v) > 1:
                    d.line(v, fill=cl, width=2); hit = True
            n += hit
        px = 1000 / 63.5 * Z
        for im_ in (src, im):
            dd = ImageDraw.Draw(im_); dd.rectangle([8, T - 14, 8 + px, T - 9], fill=(0, 0, 0)); dd.text((14 + px, T - 24), '1 м', fill=(0, 0, 0), font=f)
        t = Image.new('RGB', (2 * T + 10, T + 52), 'white'); t.paste(src, (0, 52)); t.paste(im, (T + 10, 52)); dt = ImageDraw.Draw(t)
        dt.text((6, 4), tl.get('title', ''), fill=(0, 0, 0), font=fb)
        dt.text((6, 28), tl.get('sub', '') + ' · слева исходник, справа наш класс цветом', fill=(70, 70, 70), font=f)
        tiles.append(t); print(fl, sorted(keys), 'objects in tile:', n)
    cols = 2; rows = (len(tiles) + 1) // 2
    sh = Image.new('RGB', (cols * (tiles[0].width + 12), rows * (tiles[0].height + 12) + 50), (236, 236, 236)); d = ImageDraw.Draw(sh)
    d.text((10, 12), S.get('title', 'Новые классы на месте'), fill=(0, 0, 0), font=fb)
    for k, t in enumerate(tiles): sh.paste(t, ((k % cols) * (t.width + 12), 50 + (k // cols) * (t.height + 12)))
    sh.save(out, optimize=True); print(out, sh.size)
if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
