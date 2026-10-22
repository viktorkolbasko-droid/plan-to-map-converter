"""ocg/ba_view.py - code 010 (test 9 pass code, labels from BA_BEFORE / BA_AFTER). Before / after crops for the owner's examples: the source | the result before (a run folder) | the result now (a run
folder). The result: wall bodies (orange — ГКЛ, purple — capital, grey — columns), glass (blue), doors (green), furniture
by type (as drawn: 'draw'; or 'outline' with VARIANT=outline), core blocks (purple).
usage: python3 ba_view.py out.png before_dir after_dir 'x0,y0,x1,y1|подпись;...'   (labels: env BA_BEFORE, BA_AFTER)"""
import sys, os, pickle, json
import numpy as np, pymupdf, shapely
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from e7_comp import geom   # code 010: ocg/
out, d0, d1, spec = sys.argv[1:5]; VAR = os.environ.get('VARIANT', 'detail')
WINS = [(tuple(map(float, s.split('|')[0].split(','))), s.split('|')[1] if '|' in s else '') for s in spec.split(';') if s.strip()]
F = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 16); FB = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 18)
WCOL = {'gkl': (230, 140, 40), 'cap': (130, 60, 150), 'column': (90, 90, 90), 'ext': (40, 40, 40), 'blk': (40, 150, 60)}
OCOL = {'door': (20, 140, 60), 'glass': (30, 110, 220), 'chair': (220, 40, 40), 'chairpart': (220, 40, 40), 'armchair': (200, 40, 200), 'desk': (170, 110, 50),
        'mtable': (40, 60, 200), 'dtable': (40, 60, 200), 'rtable': (40, 60, 200), 'round': (40, 160, 220), 'sofa': (130, 40, 160), 'ctable': (40, 150, 150),
        'table': (40, 150, 150), 'counter': (230, 120, 0), 'storage': (120, 120, 0), 'pedestal': (120, 120, 0), 'kitchen': (150, 80, 30), 'coreblock': (130, 60, 150),
        'coreline': (230, 0, 0), 'lpart': (120, 70, 200), 'furn': (0, 0, 0), 'deskedge': (0, 0, 0), 'group': (0, 0, 0)}
def load(d):
    cwd = os.getcwd(); os.chdir(d)
    try:
        from e7_comp import load_prims, load_walls
        P = load_prims()['P']; O = pickle.load(open('objects.pkl', 'rb'))['objs']; W = load_walls()['bodies']
    finally: os.chdir(cwd)
    items = [('wall', c, g) for c, g in W]
    for o in O:
        col = OCOL.get(o['key'])
        if not col or not o['ids']: continue
        loose = 'draw' not in o and o['key'] in ('furn', 'deskedge', 'group', 'table', 'chairpart')
        ids = o['outline'] if VAR == 'outline' and o.get('outline') else o.get('draw', o['ids'])
        for i in ids:
            p = P[i]
            if p['kind'] == 'removed' or len(p['p']) < 2: continue
            items.append(('loose' if loose else 'obj', o['key'], geom(p)))
    return items, shapely.STRtree([g for _, _, g in items])
try:                                     # code 010: the sheet of the floor folder (cfg.py - ocg/sheet.py), else src.pdf of the run
    import sheet; _pdf = sheet.PDF
except SystemExit: _pdf = os.path.join(d1, 'src.pdf')
pg = pymupdf.open(_pdf)[0]
A = load(d0); B = load(d1)
def render(src, it, win, Z):
    x0, y0, x1, y1 = win; items, tr = it
    res = Image.blend(Image.new('RGB', src.size, 'white'), src.convert('L').convert('RGB'), 0.3).convert('RGBA')
    ov = Image.new('RGBA', res.size, (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
    def T(cs): return [((a - x0) * Z, (b - y0) * Z) for a, b in cs]
    # polygons first, lines over them: a big polygon drawn later (a core block) must not wipe the lines in the overlay
    js = sorted(tr.query(shapely.geometry.box(*win)), key=lambda j: (0 if items[j][2].geom_type in ('Polygon', 'MultiPolygon') else 1, -items[j][2].area))
    for j in js:
        kind, c, g = items[j]
        col = WCOL.get(c, (60, 60, 60)) if kind == 'wall' else OCOL.get(c, (0, 0, 0))
        for q in getattr(g, 'geoms', [g]):
            if q.geom_type == 'Polygon':
                d.polygon(T(q.exterior.coords), fill=col + ((150,) if kind == 'wall' else (45,)), outline=col + (255,))
                for h in q.interiors: d.polygon(T(h.coords), fill=(255, 255, 255, 255), outline=(255, 0, 0, 255))
            elif q.geom_type == 'LineString':
                if kind == 'loose':
                    cs = T(q.coords)
                    for a_, b_ in zip(cs[:-1], cs[1:]): d.line([a_, b_], fill=(0, 0, 0, 255), width=1)
                else: d.line(T(q.coords), fill=col + (255,), width=2)
    return Image.alpha_composite(res, ov).convert('RGB')
rows = []
for win, cap in WINS:
    x0, y0, x1, y1 = win; Z = 520.0 / max(x1 - x0, y1 - y0)
    pix = pg.get_pixmap(matrix=pymupdf.Matrix(Z, Z), clip=pymupdf.Rect(x0, y0, x1, y1), alpha=False)
    src = Image.frombytes('RGB', (pix.width, pix.height), pix.samples)
    a = render(src, A, win, Z); b = render(src, B, win, Z); w, h = src.size
    im = Image.new('RGB', (3 * w + 20, h + 34), 'white'); im.paste(src, (0, 34)); im.paste(a, (w + 10, 34)); im.paste(b, (2 * w + 20, 34))
    dd = ImageDraw.Draw(im); dd.text((4, 6), cap, fill='black', font=FB)
    dd.text((w + 14, 36), os.environ.get('BA_BEFORE', 'было'), fill=(120, 0, 0), font=F); dd.text((2 * w + 24, 36), os.environ.get('BA_AFTER', 'стало'), fill=(0, 100, 0), font=F)
    rows.append(im)
W_ = max(r.width for r in rows); S = Image.new('RGB', (W_, sum(r.height + 12 for r in rows)), 'white'); y = 0
for r in rows: S.paste(r, (0, y)); y += r.height + 12
S.save(out); print(out, S.size)
