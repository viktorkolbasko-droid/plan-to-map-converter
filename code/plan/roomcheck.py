# Room boundaries (plan/rules/60 §5): the purple dashed lines of the sheets are Revit room separation lines (owner,
# 28.09) - the room boundary where no wall stands. Checks, cwd = floor folder, after export/geomfix:
#   closure  : each separation line ends on a wall body, a partition / glazing line, a door or another separation
#              line (<= 1 pt); an open end means the room boundary is not closed there
#   along    : a separation line running along a wall / partition must lie on its face (offset of the part that
#              runs within 1.5 pt of a wall body, parallel to its face)
#   rooms    : walls + partitions + glazing + closed doors + separation lines cut the floor into rooms; each room tag
#              must lie in a room of its own, and no room may leak to the outside
# Writes rooms.json. Usage: python3 roomcheck.py
import sys, math, json, pickle, collections
import numpy as np
from shapely.geometry import LineString, Point, Polygon, MultiPolygon
from shapely.ops import unary_union, polygonize
from shapely.strtree import STRtree
from common import load, pts, cfg, walls_file, MM_PER_PT, FACADES
from geomlib import merge_lines
P = load(); cls = pickle.load(open('cls.pkl', 'rb'))
inst = pickle.load(open('inst_final.pkl', 'rb'))
W = pickle.load(open(walls_file(), 'rb'))['Wpt']
SEP_COL = [tuple(c) for c in getattr(cfg, 'ROOMSEP_COLORS', [(0.5, 0.0, 0.5)])]
def is_sep(p): return p[0] == 'l' and p[2] is not None and any(max(abs(p[2][j] - c[j]) for j in range(3)) <= 0.03 for c in SEP_COL)
def polys(g): return [g] if g.geom_type == 'Polygon' else [x for x in getattr(g, 'geoms', []) if x.geom_type == 'Polygon']
WB = [p for v in W.values() for g in v for p in polys(g)]
WU = unary_union(WB)
R = {}
seg_raw = [tuple(map(tuple, P[i][4])) for i, p in enumerate(P) if is_sep(p) and cls[i] not in ('sheet', 'axis', 'dim')]
R['separation_prims'] = len(seg_raw)
if not seg_raw:
    json.dump(R, open('rooms.json', 'w'), ensure_ascii=False, indent=1); print(R); sys.exit()
# dashes of one line -> one segment (collinear pieces with gaps <= 5 pt: dash 6.8, gap 4.2 pt)
SEG = [s for s in merge_lines(seg_raw, tol=0.2, gap=5.0) if math.dist(*s) >= 1.0]
R['separation_lines'] = len(SEG)
own = {}
for q in inst:
    for i in q['prims']: own[i] = q['key']
def lines_of(keys):
    out = []
    for q in inst:
        if q['key'] in keys:
            for i in q['prims']:
                if P[i][0] in ('l', 'c') and not is_sep(P[i]): out.append(LineString(pts(P[i])))
    return out
PART = lines_of(('lpart', 'lpartc', 'gklpart', 'glasspart', 'railing', 'glass', 'facade', 'door45', 'rdoor', 'column', 'wallline'))
DOORL = [LineString([q['door']['c'], q['door']['closed']]) for q in inst if q['key'] == 'door' and q.get('door')]
PU = unary_union(PART) if PART else LineString()
DU = unary_union(DOORL) if DOORL else LineString()
SG = [LineString(s) for s in SEG]
closure = []; along = []
for k, g in enumerate(SG):
    others = unary_union([SG[j] for j in range(len(SG)) if j != k]) if len(SG) > 1 else LineString()
    ends = []
    for e in (g.coords[0], g.coords[-1]):
        p = Point(e)
        d = dict(wall=WU.distance(p), part=PU.distance(p) if not PU.is_empty else 1e9, door=DU.distance(p) if not DU.is_empty else 1e9,
                 sep=others.distance(p) if not others.is_empty else 1e9)
        best = min(d, key=d.get)
        ends.append(dict(at_pt=[round(e[0], 1), round(e[1], 1)], closed=bool(d[best] <= 1.0), on=best, gap_mm=round(d[best] * MM_PER_PT)))
    closure.append(dict(line=k, length_mm=round(g.length * MM_PER_PT), ends=ends))
    # the part that runs along a wall body (within 1.5 pt): its offset from the body boundary
    near = g.intersection(WU.buffer(1.5))
    if near.length >= 3.0:
        samples = [near.interpolate(t, normalized=True) for t in np.linspace(0.05, 0.95, 10)] if near.geom_type == 'LineString' else \
                  [pp for gg in near.geoms for pp in [gg.interpolate(t, normalized=True) for t in (0.25, 0.5, 0.75)]]
        offs = [WU.boundary.distance(pp) * MM_PER_PT * (1 if not WU.contains(pp) else -1) for pp in samples]
        along.append(dict(line=k, length_mm=round(near.length * MM_PER_PT), offset_mm_median=round(float(np.median(offs))),
                          offset_mm_max=round(float(max(abs(o) for o in offs))), at_pt=[round(near.centroid.x, 1), round(near.centroid.y, 1)]))
R['open_ends'] = [dict(line=c['line'], **e) for c in closure for e in c['ends'] if not e['closed']]
R['n_open_ends'] = len(R['open_ends'])
# (28.09.2026) what an open end is (sheet of floor 5): 'almost' - within 2.5 pt (160 mm) of a boundary: the line ends
#   on the far face or the centre of a partition; 'along' - the line runs over a wall / partition for >= 80 % of its
#   length (a boundary drawn over one that closes the room anyway); 'object' - it stops at another drawn element
#   (a wardrobe, a column casing: not a room boundary here); 'open' - nothing there
_OL = [LineString(pts(P[i])) for i in range(len(P)) if P[i][0] in ('l', 'c') and not is_sep(P[i]) and cls[i] not in ('sheet', 'axis', 'dim')]
_OT = STRtree(_OL)
def _along_share(g):
    nb = g.buffer(3.0); loc = unary_union([WU.intersection(nb), PU.intersection(nb) if not PU.is_empty else LineString()])
    return g.intersection(loc.buffer(2.5)).length / g.length if not loc.is_empty and g.length > 0 else 0.0
_ash = {}
for e in R['open_ends']:
    k = e['line']
    if k not in _ash: _ash[k] = _along_share(SG[k])
    p = Point(e['at_pt'])
    if e['gap_mm'] <= 2.5 * MM_PER_PT: e['kind'] = 'almost'
    elif _ash[k] >= 0.8: e['kind'] = 'along'
    elif any(_OL[int(j)].distance(p) <= 1.0 for j in _OT.query(p.buffer(1.0))): e['kind'] = 'object'
    else: e['kind'] = 'open'
R['open_ends_by_kind'] = dict(collections.Counter(e['kind'] for e in R['open_ends']))
R['along_walls'] = along
R['along_offset_gt_20mm'] = [a for a in along if a['offset_mm_max'] > 20]
# long runs only (>= 1 m): a short piece near a corner meets the wall at an angle, its 'offset' is no face offset
R['along_walls_long'] = [a for a in along if a['length_mm'] >= 1000]
R['along_long_offset_gt_20mm'] = [a for a in R['along_walls_long'] if a['offset_mm_median'] > 20]
# rooms: the holes of the boundary set (walls + partitions + glazing + closed doors + separation lines, lines
#   buffered 0.15 pt); a room that leaks to the outside is no hole
B = [g.buffer(0.15) for g in PART + DOORL + SG] + WB
BU = unary_union(B)
rooms = [Polygon(h) for p in polys(BU) for h in p.interiors]
rooms = [r for r in rooms if r.area * MM_PER_PT ** 2 >= 1.0e6]   # >= 1 m2
tags = [q for q in inst if q['key'] == 'tag']
tag_room = collections.defaultdict(list); lost = []
RT = STRtree(rooms) if rooms else None
for q in tags:
    p = Point(q['c'])
    hit = [int(j) for j in RT.query(p)] if RT is not None else []
    hit = [j for j in hit if rooms[j].contains(p)]
    if hit: tag_room[hit[0]].append(q['text'])
    else: lost.append(q['text'])
R['rooms'] = len(rooms); R['tags'] = len(tags)
R['rooms_with_several_tags'] = [dict(tags=v, area_m2=round(rooms[k].area * MM_PER_PT ** 2 / 1e6, 1), at_pt=[round(rooms[k].centroid.x), round(rooms[k].centroid.y)]) for k, v in tag_room.items() if len(v) > 1]
R['tags_not_in_a_closed_room'] = lost
json.dump(R, open('rooms.json', 'w'), ensure_ascii=False, indent=1)
for k, v in R.items():
    print(k, (len(v), v[:6]) if isinstance(v, list) else v)
# ---- picture rooms.png: rooms tinted, walls grey, partitions blue, doors green, separation lines magenta,
#      open ends red, tags black (red: no closed room or shared room)
if '--png' in sys.argv or True:
    import random
    from PIL import Image, ImageDraw, ImageFont
    Z = 2.0; x0, y0, x1, y1 = cfg.WIN
    im = Image.new('RGB', (int((x1 - x0) * Z), int((y1 - y0) * Z)), 'white'); d = ImageDraw.Draw(im)
    T = lambda p: ((p[0] - x0) * Z, (p[1] - y0) * Z)
    rnd = random.Random(7)
    for r in rooms:
        c = tuple(rnd.randint(170, 240) for _ in range(3)); d.polygon([T(p) for p in r.exterior.coords], fill=c)
    for p in WB: d.polygon([T(c) for c in p.exterior.coords], fill=(110, 110, 110))
    for g in PART: d.line([T(c) for c in g.coords], fill=(40, 110, 220), width=1)
    for g in DOORL: d.line([T(c) for c in g.coords], fill=(0, 150, 0), width=2)
    for g in SG: d.line([T(c) for c in g.coords], fill=(220, 0, 200), width=3)
    for e in R['open_ends']:
        x, y = T(e['at_pt']); d.ellipse([x - 6, y - 6, x + 6, y + 6], outline=(255, 0, 0), width=3)
    f = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 14)
    bad = set(R['tags_not_in_a_closed_room']) | {t for r_ in R['rooms_with_several_tags'] for t in r_['tags']}
    for q in tags:
        x, y = T(q['c']); d.text((x - 6, y - 8), q['text'], fill=(230, 0, 0) if q['text'] in bad else (0, 0, 0), font=f)
    im.save('rooms.png')
