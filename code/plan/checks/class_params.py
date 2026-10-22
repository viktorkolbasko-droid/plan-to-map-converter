# Check 3.10 (29.09.2026, owner: "a classified object is parametrised by its geometry"): every recognised object is
#   measured against the range its class allows, and a piece of furniture or equipment must read as one closed shape.
#   (a) size: the object's minimum rotated rectangle, long and short side in mm, against RANGES;
#   (b) colour: a partition joint ('lpartc') >= 250 mm across is not a coloured body - fills of saturation >= 0.1 cover
#       <= 25 % of its bbox
#       (29.09: seats, desk tops and a meeting table were 'partition joints');
#   (c) closed: an object of CLOSED classes is drawn as a closed outline - the ink of its strokes (each grown by half its
#       weight x 1.3) encloses >= 40 % of its convex hull; separate strokes or an open contour fail (a chair half under
#       a desk top encloses 42-45 %: that is the source);
#   (d) the light-partition class holds no furniture: its lines lying on coloured fills (saturation >= 0.1) >= 0.05 m2
#       (desk tops, seats) in metres.
#   Out: class_params.json (per class: count, out of range, open, examples) and class_params.png (the worst 30).
# Run in a floor folder after export (reads assign2.pkl): python3 class_params.py
import pickle, sys, os, json, math, collections
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import load, pts, PDF, MM_PER_PT
from shapely.geometry import LineString, Polygon, MultiPoint, box
from shapely.ops import unary_union
from shapely.strtree import STRtree
P = load(); inst, free = pickle.load(open('assign2.pkl', 'rb'))
# (long side min, long side max, short side min, short side max) in mm; None = no limit
RANGES = {'chair': (350, 1000, 250, 900), 'stool': (250, 700, 250, 700), 'armchair': (550, 1400, 450, 1300),
          'sofa': (900, 3500, 500, 1300), 'desk': (600, 12000, 350, 1800), 'desk_src': (500, 12000, 350, 6000),
          'rtable': (350, 1300, 350, 1300), 'rtable_set': (900, 3200, 900, 3200), 'door': (500, 3200, 50, 3000),
          'plant': (150, 2000, 150, 2000), 'column': (150, 1500, 100, 1500), 'sink': (250, 1800, 250, 900),
          'sink_src': (250, 1200, 200, 900), 'wc': (300, 900, 250, 700), 'stair': (700, 12000, 700, 9000),
          'lift': (900, 7000, 900, 3500), 'convector': (500, 3600, 100, 500), 'wardrobe': (300, 3500, 250, 1200),
          'curtain': (500, 8000, 0, 200), 'screen': (300, 15000, 0, 2500), 'fscreen': (500, 3000, 0, 400),
          'wcacc': (20, 3000, 0, 1500), 'furn_src': (300, 8000, 200, 6000), 'lpartc': (0, None, 0, None)}
# 'desk': a bench row is one desk, up to 9 m (floor 1); 'screen': the leftovers inside twin desks, spread along the bench
#   (plan/rules/40 §2 step 7) - a container, not one screen; 'wcacc': a washroom's accessories may be one object
CLOSED = ('chair', 'stool', 'armchair', 'sofa', 'desk_src', 'rtable', 'sink', 'sink_src', 'wc', 'furn_src', 'convector', 'lift')
# a canonical desk is drawn by its measured block (contour and top, plan/rules/40 §6), not by its primitives: on floor 6 the
#   desk edges are long lines of the light-partition class and the object holds only the white top - not asked here
# a family instance is as closed as its exemplar: a chair pushed under the desk is drawn open in the source (floors 1, 2,
#   6), its exemplar too - then the instance is not asked to be closed. A wardrobe is hangers and a rod: lines by nature.
def neutral(c): return c is None or (abs(c[0] - c[1]) < 0.03 and abs(c[1] - c[2]) < 0.03)
def white_mask(p): return p[0] == 'qu' and p[2] is None and p[3] is not None and min(p[3]) >= 0.97
def sides(ids):
    g = MultiPoint([v for i in ids for v in pts(P[i])]).minimum_rotated_rectangle
    if g.geom_type != 'Polygon': return (g.length * MM_PER_PT, 0.0), g
    c = list(g.exterior.coords); a, b = math.dist(c[0], c[1]), math.dist(c[1], c[2])
    return (max(a, b) * MM_PER_PT, min(a, b) * MM_PER_PT), g
def closed_share(ids):
    ink = []
    for i in ids:
        p = P[i]; q = pts(p)
        if white_mask(p) or len(q) < 2: continue
        if p[0] == 'qu' and p[3] is not None: ink.append(Polygon(q).buffer(0)); continue      # a fill is closed by itself
        ink.append(LineString(q + ([q[0]] if p[0] == 'qu' else [])).buffer(max(0.05, 0.5 * (p[1] or 0)) * 1.3))
    if not ink: return 0.0
    U = unary_union(ink); hull = MultiPoint([v for i in ids for v in pts(P[i])]).convex_hull
    if hull.area <= 0: return 1.0
    filled = unary_union([Polygon(g.exterior) for g in getattr(U, 'geoms', [U]) if g.geom_type == 'Polygon'])
    return filled.area / hull.area
_TO = {}
def tpl_open(t):
    if t not in _TO: _TO[t] = closed_share(list(t)) < 0.5
    return _TO[t]
R = collections.defaultdict(lambda: dict(n=0, out=0, open=0, coloured=0, samples=[]))
bad = []
for n, q in enumerate(inst):
    k = q['key']
    if k not in RANGES or not q['prims']: continue
    r = R[k]; r['n'] += 1
    (L, S), g = sides(q['prims']); lo, hi, slo, shi = RANGES[k]
    why = []
    if L < lo or (hi is not None and L > hi) or S < slo or (shi is not None and S > shi): why.append(f'размер {round(L)}×{round(S)} мм')
    if k == 'lpartc':
        xs = [v for i in q['prims'] for v in pts(P[i])]; b = (min(x for x, y in xs), min(y for x, y in xs), max(x for x, y in xs), max(y for x, y in xs))
        ba = max(1e-6, (b[2] - b[0]) * (b[3] - b[1])); ca = 0.0
        for i in q['prims']:
            p = P[i]
            if p[0] == 'qu' and p[3] is not None and max(p[3]) - min(p[3]) >= 0.1 and not white_mask(p): ca += Polygon(pts(p)).buffer(0).area
        # a body, not a strip: a partition with a coloured infill is thin (< 250 mm) and is a partition
        if ca >= 0.25 * ba and S >= 250: why.append(f'цветная заливка {round(100 * ca / ba)} % рамки'); r['coloured'] += 1
    if k in CLOSED and not ('tpl' in q and tpl_open(tuple(q['tpl']))):
        cs = closed_share(q['prims'])
        if cs < 0.4: why.append(f'контур не замкнут ({round(100 * cs)} % оболочки)'); r['open'] += 1
    if why:
        if any(w.startswith('размер') for w in why): r['out'] += 1
        c = g.centroid; at = [round(c.x, 1), round(c.y, 1)]
        if len(r['samples']) < 20: r['samples'].append(dict(at_pt=at, name=q['name'][:60], why=why))
        bad.append((k, n, at, why, (L, S)))
# (d) light partitions lying on coloured fills (desk tops) - furniture edges in the partition class
# coloured as in reclass rule F: saturation >= 0.1 - the pale tints of glass and floor zones carry partition lines rightly
fills = [Polygon(pts(p)).buffer(0) for p in P if p[0] == 'qu' and p[3] is not None and max(p[3]) - min(p[3]) >= 0.1 and not white_mask(p)]
fills = [g for g in fills if g.area * MM_PER_PT ** 2 >= 0.05e6]
FT = STRtree(fills) if fills else None; on_fill = 0.0; lp = 0.0
for q in inst:
    if q['key'] not in ('lpart', 'lpartc', 'gklpart', 'glasspart', 'railing'): continue
    for i in q['prims']:
        if P[i][0] != 'l': continue
        ln = LineString(P[i][4]); lp += ln.length
        if FT is not None and any(fills[j].buffer(0.05).contains(ln) for j in FT.query(ln)): on_fill += ln.length
J = dict(per_class={k: dict(v) for k, v in sorted(R.items())}, violations=len(bad),
         partition_lines_m=round(lp * MM_PER_PT / 1000), partition_lines_on_coloured_fills_m=round(on_fill * MM_PER_PT / 1000))
json.dump(J, open('class_params.json', 'w'), ensure_ascii=False, indent=0)
print('objects checked', sum(v['n'] for v in R.values()), '| out of range', sum(v['out'] for v in R.values()),
      '| open outline', sum(v['open'] for v in R.values()), '| coloured joints', sum(v['coloured'] for v in R.values()),
      '| partition lines on coloured fills', J['partition_lines_on_coloured_fills_m'], 'of', J['partition_lines_m'], 'm')
for k, v in sorted(R.items()):
    if v['out'] or v['open'] or v['coloured']: print(f"  {k}: {v['n']} objects, size out {v['out']}, open {v['open']}, coloured {v['coloured']}")
# sheet: the worst 30 (size first, then open outlines)
import pymupdf as fitz
from PIL import Image, ImageDraw, ImageFont
bad.sort(key=lambda t: (not any(w.startswith('размер') for w in t[3]), t[0]))
sel = bad[:30]; T = 200; cols = 6; pg = fitz.open(PDF)[0]
f = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 10)
sh = Image.new('RGB', (cols * (T + 4), max(1, (len(sel) + cols - 1) // cols) * (T + 28)), 'white'); d = ImageDraw.Draw(sh)
for k_, (k, n, at, why, (L, S)) in enumerate(sel):
    xs = [v for i in inst[n]['prims'] for v in pts(P[i])]; b = (min(x for x, y in xs), min(y for x, y in xs), max(x for x, y in xs), max(y for x, y in xs))
    cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2; h = max(4, max(b[2] - b[0], b[3] - b[1]) * 0.7); Z = T / (2 * h)
    pix = pg.get_pixmap(matrix=fitz.Matrix(Z, Z), clip=fitz.Rect(cx - h, cy - h, cx + h, cy + h))
    im = Image.frombytes('RGB', (pix.width, pix.height), pix.samples).resize((T, T)); im = Image.blend(im, Image.new('RGB', im.size, 'white'), 0.45)
    dr = ImageDraw.Draw(im)
    for i in inst[n]['prims']:
        qq = [((x - cx + h) * Z, (y - cy + h) * Z) for x, y in pts(P[i])]
        if len(qq) > 1: dr.line(qq, fill=(230, 0, 0), width=1)
    x0, y0 = (k_ % cols) * (T + 4), (k_ // cols) * (T + 28); sh.paste(im, (x0, y0 + 26))
    d.text((x0 + 2, y0), f'{k}: {why[0]}'[:40], fill=(0, 0, 0), font=f); d.text((x0 + 2, y0 + 12), f'у ({at[0]:.0f}, {at[1]:.0f})', fill=(90, 90, 90), font=f)
sh.save('class_params.png')
