"""Э8: DXF R2018 (mm, ISO 13567 layers) of the layered route, plan/rules/50.
 - origin and scale of the sheet (cfg.ORIGIN_PT, cfg.MM_PER_PT; ocg/sheet.py), y up; walls: outline + solid grey + material pattern (code 006 wallsdxf.write_walls);
 - columns A-28: outline + solid fill of the source colour; room fills A-92----H- first;
 - every object is an INSERT of its block (identical objects share one block, e7_blocks.py); a desk's block is its top
   (the fill); everything else of an object that its block does not reproduce is drawn raw on the object's layer;
 - texts on their places and angles, height = size x 0.72 x mm/pt; the sheet title stays out (SHEET_BOXES).
Writes <OUTDIR>/<cfg.OUT>_engineering.dxf (detailed) or _outline.dxf (габаритный), walls.pkl (W mm / Wpt pt) for geomfix and checks, export_stats.json.
v3 (owner 06.10.2026, two results): VARIANT=outline draws each object's 'outline' (one closed outline: type and габарит,
no inner structure) where it has one, with blocks_outline.pkl; OUTDIR sets the output folder (default out).
Code 009: texts «ПК…» on A-68----T- (Т4-14, S14*); the DXF layer table - layers8.table() and ocg/layers_ocg.EXTRA; texts of
the axes by cfg.OCG_AXIS_TEXT_RE.
Code 012 (stage 2 of the merge: v010, owner's remarks of 09.10.2026): every contour without extra points (ЛТ-1…ЛТ-3,
regular.clean_ring in mm), arcs as arcs (curves.py: bulges, CIRCLE; З-6), the swing arc of a door - an ARC of the linetype
DOOR-SWING (dashed, З-7), the owner's group of every entity - XDATA 'UNSPOT' (group, type; ОЧ-82), stray lines (Э7к) on
A-00, facade mullions on A-31; rooms and passages (Э9з: rooms.pkl, passage.pkl) - a DXF of their own <cfg.OUT>_zones.dxf in
OUTDIR (ZONES_IN_DXF=1 - in the plan's DXF too); a quick necessary test before the cover test of hidden lines."""
import pickle, math, json, collections, sys, re, time
import numpy as np, ezdxf
from shapely.geometry import Polygon, LineString
from shapely.ops import unary_union
import os
_OCG = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.dirname(_OCG)); sys.path.insert(0, _OCG)   # code/, code/ocg/
import sheet
from e7_comp import geom
t0 = time.time()
import os
VAR = os.environ.get('VARIANT', 'detail'); OUTDIR = os.environ.get('OUTDIR', 'out')
K = sheet.K; OX, OY = sheet.OX, sheet.OY
def mm(p): return (K * p[0] - K * OX, -K * p[1] + K * OY)
from e7_comp import load_prims
P = load_prims(); T = P['T']; P = P['P']                 # prims_e7.pkl: with the split pieces (e7_objects.py)
O = pickle.load(open('objects.pkl', 'rb')); objs = O['objs']
BL = pickle.load(open('blocks_outline.pkl' if VAR == 'outline' else 'blocks.pkl', 'rb')); assign = BL['assign']; blocks = BL['blocks']
from e7_comp import load_walls; W = load_walls()['bodies']
from layers_ocg import table as _ocg_table      # code 009: the code's layer table (layers8.py) + the layers of the layer route
LAY = _ocg_table()                               # code 012 (v010): + the zone layers A-921, A-922 (layers_ocg.EXTRA); A-79 stays gone (К-1)
doc = ezdxf.new('R2018', setup=True); doc.units = ezdxf.units.MM; doc.header['$INSUNITS'] = 4; doc.header['$MEASUREMENT'] = 1
for n, d, c, lw in LAY:
    if n not in doc.layers: l = doc.layers.add(n, color=c, lineweight=lw); l.description = d
msp = doc.modelspace()
# ---- remarks З-6, З-7 and extra points ЛТ-1…ЛТ-4 (owner 09.10.2026): every contour without a closing repeat, repeats and points on
# a straight line; a run of points on one circle — an arc (bulge) or a CIRCLE; the swing arc of a door — an ARC, dashed (a path of
# movement, lighter than the door itself)
import regular as RG, curves as CV
if 'UNSPOT' not in doc.appids: doc.appids.new('UNSPOT')          # the owner's group of an object (rows 225, 238) as XDATA
def setx(e, o):
    try: e.set_xdata('UNSPOT', [(1000, f"group={o.get('group', '')}"), (1000, f"type={o['key']}")])
    except Exception: pass
if 'DOOR-SWING' not in doc.linetypes:
    doc.linetypes.add('DOOR-SWING', pattern=[80.0, 50.0, -30.0], description='Дуга раскрытия двери — пунктир (контур движения)')
NSTAT = collections.Counter()
def tidy(q, closed):
    """mm points -> without the closing repeat, repeats < 1 mm and points on a straight line (ЛТ-1…ЛТ-3)"""
    n0 = len(q)
    c = RG.clean_ring(q, closed=closed, dup=1.0, col_dev=0.55)   # 0.55: a margin over the 0.5 mm of the check ПЗ-1
    NSTAT['points in'] += n0; NSTAT['points tidy'] += len(c)
    return c
def draw_curve(target, q, closed, attribs):
    """a polyline of mm points: LINE, LWPOLYLINE with arcs (bulges) or CIRCLE"""
    c = tidy(q, closed)
    if len(c) < 2: return None
    f = CV.fit(c, closed)
    if f and f[0][0] == 'circle':
        _, cx, cy, r = f[0]; NSTAT['circles'] += 1
        return target.add_circle((cx, cy), r, dxfattribs=attribs)
    nb = sum(1 for v in f if v[2]); NSTAT['arcs'] += nb; NSTAT['points out'] += len(f)
    if len(f) == 2 and not closed and not nb: return target.add_line(f[0][:2], f[1][:2], dxfattribs=attribs)
    return target.add_lwpolyline(f, format='xyb', close=closed, dxfattribs=attribs)
def hatch_path(h, q, outer):
    """one boundary ring of a hatch (mm points), with arcs; a circle — two half-circle bulges"""
    c = tidy(q, True)
    if len(c) < 3: return
    f = CV.fit(c, True)
    if f and f[0][0] == 'circle':
        _, cx, cy, r = f[0]; v = [(cx + r, cy, 1.0), (cx - r, cy, 1.0)]
    else: v = f
    h.paths.add_polyline_path(v, is_closed=True, flags=1 if outer else 0)
# a line painted over by a later line of the same geometry is not seen in the source (a black line under a light grey
# one): only the topmost of such duplicates is drawn (z-order of the PDF, checked by the render-based ink check)
import os, hashlib
# cache of these prims: the key holds the coordinates too (test 8: a rerun from E7j moves points without changing their
# number, and a key of the point counts only would reuse a stale cache)
_key = hashlib.sha256(pickle.dumps([(p['id'], p['kind'], p['seq'], [tuple(map(float, q)) for q in p['p']], p.get('holes'), p.get('alpha')) for p in P])).hexdigest()
HIDDEN = None
if os.path.exists('hidden.pkl'):
    _h = pickle.load(open('hidden.pkl', 'rb'))
    if isinstance(_h, dict) and _h.get('key') == _key: HIDDEN = _h['H']
if HIDDEN is None:
    import shapely
    from shapely.geometry import LineString as _LS
    _L = [p for p in P if p['kind'] == 'line' and len(p['p']) >= 2]
    _G = [_LS(p['p']) for p in _L]; _T = shapely.STRtree(_G); HIDDEN = set()
    _OF = [p for p in P if p['kind'] == 'fill' and (p.get('alpha') or 1.0) >= 0.99]          # opaque fills hide what is under
    _OG = [Polygon(p['p'], p.get('holes', [])).buffer(0) for p in _OF]; _OT = shapely.STRtree(_OG) if _OG else None
    for k, (p, g) in enumerate(zip(_L, _G)):
        later = [j for j in _T.query(g.buffer(0.06)) if j != k and (_L[j]['seq'], _L[j]['id']) > (p['seq'], p['id'])]
        lf = [j for j in _OT.query(g) if (_OF[j]['seq'], _OF[j]['id']) > (p['seq'], p['id'])] if _OT is not None else []
        if not later and not lf: continue
        # a quick necessary test first (v010, the same result): the ends and the middle of the line are within the cover's reach
        from shapely.geometry import Point as _Pt
        _q = [_Pt(g.coords[0]), _Pt(g.coords[-1]), g.interpolate(0.5, normalized=True)]
        if not all(any(_G[j].distance(q) <= 0.06 for j in later) or any(_OG[j].distance(q) <= 0.02 for j in lf) for q in _q): continue
        cover = unary_union([_G[j].buffer(0.06, cap_style=2) for j in later] + [_OG[j].buffer(0.02) for j in lf])
        if cover.covers(g): HIDDEN.add(p['id'])
    pickle.dump(dict(key=_key, H=HIDDEN), open('hidden.pkl', 'wb'))
print('lines covered by later lines (not seen in the source, not drawn)', len(HIDDEN))
def E(el): return el.ljust(8, '-') + 'E-'
def Hh(el): return el.ljust(8, '-') + 'H-'
# code 010 (К-1): МФУ and wall screens - A-82 (owner's decision of 07.10.2026, №106, №108, row 208); A-79 is not a layer
OBJLAY = {'desk': 'A-82', 'chair': 'A-82', 'armchair': 'A-82', 'round': 'A-82', 'table': 'A-82', 'group': 'A-82', 'furn': 'A-82',
          'booth': 'A-82', 'chairpart': 'A-82', 'mfp': 'A-82', 'plant': 'A-89', 'equip': 'A-82', 'sink': 'A-73', 'san': 'A-74',
          'conv': 'A-56', 'facade': 'A-31', 'door': 'A-32', 'fire': 'A-68', 'lift': 'A-66', 'counter': 'A-76', 'corezone': 'A-92',
          'shaft': 'A-92', 'zone': 'A-92', 'coreline': 'A-221', 'glass': 'A-22G', 'lpart': 'A-22G', 'tagc': 'A-90', 'roomsep': 'A-93',
          'dim': 'A-90', 'mark': 'A-AXM', 'coreblock': 'A-221', 'axis': 'A-AX', 'measure': 'A-90', 'dtable': 'A-82', 'ctable': 'A-82', 'storage': 'A-82',
          'pedestal': 'A-82', 'rtable': 'A-82', 'mtable': 'A-82', 'sofa': 'A-82', 'armchair': 'A-82', 'kitchen': 'A-76', 'passage': 'A-92', 'stray': 'A-00', 'mullion': 'A-31'}
def elay(o):
    el = o['layer'] if o['key'] == 'wallline' else OBJLAY.get(o['key'], o['layer'])
    if el in ('A-90',): return 'A-90----T-', 'A-90----T-'
    if el == 'A-AXM': return 'A-AXM---E-', 'A-AXM---E-'
    return E(el), (Hh(el) if Hh(el) in doc.layers else E(el))
def rgb(col, alpha):
    a = 1.0 if alpha is None else alpha
    return tuple(int(round(255 * (1 - a * (1 - c)))) for c in col)
def add_prim(lay, p, fn, target, key=None):
    """draw primitive p with point transform fn into target (msp or block); key — the object's type (a door: its swing arc dashed)"""
    lE, lH = lay
    if p['id'] in HIDDEN: return
    if p['kind'] == 'line':
        q = [fn(v) for v in p['p']]
        closed = len(q) > 2 and math.dist(q[0], q[-1]) < 1.0
        if key == 'door' and not closed and len(q) >= CV.MIN_PTS:
            a = CV.single_arc(tidy(q, False))
            if a is not None:                                   # З-7: the swing arc — an ARC, dashed
                (cx, cy), r, s0, e0 = a
                e = target.add_arc((cx, cy), r, s0, e0, dxfattribs={'layer': lE, 'linetype': 'DOOR-SWING'})
                NSTAT['door swing arcs (dashed)'] += 1
                if p['col'] and max(p['col']) > 0.02: e.rgb = rgb(p['col'], 1.0)
                return e
        e = draw_curve(target, q, closed, {'layer': lE})
        if e is not None and p['col'] and max(p['col']) > 0.02: e.rgb = rgb(p['col'], 1.0)
        return e
    if p['kind'] == 'wline':
        g = LineString(p['p']).buffer(p['w'] / 2, cap_style=2)
        rings = [list(g.exterior.coords)]
    else:
        rings = [list(p['p'])] + [list(h) for h in p.get('holes', [])]
    # source colour with the source opacity as hatch transparency (AutoCAD meshes are plotted at 50 %): a black column
    # stays a 50 % black, not black and not a light grey
    h = target.add_hatch(dxfattribs={'layer': lH})
    if p.get('pattern'):                          # Э7я: a block of the core — the source's diagonal hatch as a pattern
        nm_, sc_, an_ = p['pattern']; h.set_pattern_fill(nm_, scale=sc_, angle=an_); h.rgb = rgb(p['col'] or (0, 0, 0), 1.0)
        for k_, r in enumerate(rings):
            if len(r) >= 3: hatch_path(h, [fn(v) for v in r], k_ == 0)
        return h
    h.set_solid_fill(); h.rgb = rgb(p['col'] or (0, 0, 0), 1.0)
    a = p.get('alpha', 1.0)
    if a is not None and a < 0.99: h.transparency = round(1 - a, 3)
    for k_, r in enumerate(rings):
        if len(r) >= 3: hatch_path(h, [fn(v) for v in r], k_ == 0)
    return h
# ---- room fills first (A-92 H), then walls
zone_ids = set()
for o in objs:
    if o['key'] == 'zone':
        for i in o['ids']: add_prim(('A-92----E-', 'A-92----H-'), P[i], mm, msp); zone_ids.add(i)
from wallsdxf import write_walls
Wmm = collections.defaultdict(list); Wpt = collections.defaultdict(list)
for c, g0 in W:
    for g in getattr(g0, 'geoms', [g0]):                 # a body that grew by its lines may be several pieces
        if g.geom_type != 'Polygon' or g.area <= 0.05: continue
        Wpt[c].append(g)
        gm = Polygon([mm(v) for v in g.exterior.coords], [[mm(v) for v in h.coords] for h in g.interiors])
        Wmm[c].append(gm)
from wallsdxf import WL, PAT, WFILL
def write_walls2(msp, WALLS):
    """wallsdxf.write_walls of code 006 with ЛТ-1…ЛТ-4: rings without the closing repeat and extra points, arcs as arcs"""
    stats = {}
    for k, ps in WALLS.items():
        lay = WL[k]; hl = lay[:-2] + 'H-'; n = 0; per = 0
        for pg in ps:
            for g in ([pg] if pg.geom_type == 'Polygon' else pg.geoms):
                n += 1; per += g.length
                rings = [list(g.exterior.coords)] + [list(h.coords) for h in g.interiors]
                for r in rings:
                    e_ = draw_curve(msp, r, True, {'layer': lay})
                    if e_ is not None: setx(e_, dict(group='1', key='wall_' + k))
                hs = msp.add_hatch(dxfattribs={'layer': hl}); hs.set_solid_fill(); hs.rgb = WFILL[k]; setx(hs, dict(group='1', key='wall_' + k))
                for k_, r in enumerate(rings): hatch_path(hs, r, k_ == 0)
                h = msp.add_hatch(dxfattribs={'layer': hl}); h.set_pattern_fill(PAT[k][0], scale=PAT[k][1] * 20); setx(h, dict(group='1', key='wall_' + k))
                for k_, r in enumerate(rings): hatch_path(h, r, k_ == 0)
        stats[k] = dict(n=n, len_m=round(per / 2 / 1000, 1))
    return stats
wstats = write_walls2(msp, {c: Wmm[c] for c in ('ext', 'cap', 'gkl', 'blk') if c in Wmm})
for g in Wmm.get('column', []):
    rings = [list(g.exterior.coords)] + [list(h.coords) for h in g.interiors]
    for r in rings:
        e_ = draw_curve(msp, r, True, {'layer': 'A-28----E-'})
        if e_ is not None: setx(e_, dict(group='1', key='column'))
    h = msp.add_hatch(dxfattribs={'layer': 'A-28----H-'}); h.set_solid_fill(); h.rgb = (0, 0, 0); h.transparency = 0.5; setx(h, dict(group='1', key='column'))
    for k_, r in enumerate(rings): hatch_path(h, r, k_ == 0)
pickle.dump(dict(W=dict(Wmm), Wpt=dict(Wpt)), open(os.path.join(OUTDIR, 'walls.pkl'), 'wb'))
# ---- objects as block inserts
def frame_fn(cen, ang, flip):
    c, s = math.cos(-ang), math.sin(-ang)
    def f(v):                                    # pt world -> block-local mm (y up)
        x, y = v[0] - cen[0], v[1] - cen[1]; X, Y = c * x - s * y, s * x + c * y
        if flip & 1: X, Y = -X, -Y
        if flip & 2: Y = -Y
        return (K * X, -K * Y)
    return f
bdef = {}; nins = 0; nraw = 0; desc_used = collections.Counter()
# owner 06.10.2026: a chair pushed under a desk is under it — seats are drawn first, desks, tables and pedestals over them
SEATS = {'chair', 'chairpart', 'armchair', 'sofa', 'group', 'round'}
order = [k for k, o in enumerate(objs) if o['key'] in SEATS] + [k for k, o in enumerate(objs) if o['key'] not in SEATS]
for k in order:
    o = objs[k]
    if o['key'] in ('zone', 'empty'): continue
    lay = elay(o)
    ids = o['outline'] if VAR == 'outline' and o.get('outline') else o.get('draw', o['ids'])   # Э7м: a desk — the rectangle only; outline: the габарит
    if k in assign:
        bid, ang, flip, cx, cy = assign[k]; b = blocks[bid]; rep = b['rep']
        bname = f'B{bid:04d}_{objs[rep]["key"]}'
        if bname not in bdef:
            blk = doc.blocks.new(name=bname); bdef[bname] = blk
            ro = objs[rep]; rcx, rcy = assign[rep][3], assign[rep][4]; rang = assign[rep][1]
            fn = frame_fn((rcx, rcy), rang, 0)
            body = ro['outline'] if VAR == 'outline' and ro.get('outline') else ro.get('draw', ro['ids'][:1] if ro['key'] == 'desk' else ro['ids'])
            for i in body: add_prim(lay, P[i], fn, blk, ro['key'])
            try: blk.block.description = ro['name']
            except Exception: pass
        rot = -math.degrees(ang) + (180 if flip & 1 else 0)
        ins = msp.add_blockref(bname, mm((cx, cy)), dxfattribs={'layer': lay[0], 'rotation': rot, 'yscale': -1 if flip & 2 else 1})
        setx(ins, o); nins += 1; desc_used[o['name']] += 1
        if o['key'] == 'desk' and 'draw' not in o:   # the desk's own lines that the block (top) does not reproduce: raw
            for i in ids[1:]:
                e_ = add_prim(lay, P[i], mm, msp, o['key']); nraw += 1
                if e_ is not None: setx(e_, o)
    else:
        for i in ids:
            e_ = add_prim(lay, P[i], mm, msp, o['key']); nraw += 1
            if e_ is not None: setx(e_, o)
print('blocks', len(bdef), 'inserts', nins, 'raw primitives', nraw, f'{time.time() - t0:.1f} s')
# ---- zones (owner 09.10.2026, З-14…З-23): rooms and passages — closed polygons to fill on the map, group 7 (Э9з: rooms.pkl,
# passage.pkl); the outline (arcs as arcs) and a light fill, XDATA: group=7, type=room|passage, the room's number and name.
# The zones are not layers of the plan's DXF (owner 07.10.2026, №85: the passage zone — a sheet only; 08.10.2026, row 238: zones —
# for the map): they go to a DXF of their own next to it, <cfg.OUT>_zones.dxf (same origin and units); ZONES_IN_DXF=1 puts
# them into the plan's DXF too (a question to the owner). Code 012: the name of the file from cfg.OUT (v010: federation_t2_zones.dxf).
nz = collections.Counter()
zdoc = ezdxf.new('R2018', setup=True); zdoc.units = ezdxf.units.MM; zdoc.header['$INSUNITS'] = 4; zdoc.header['$MEASUREMENT'] = 1
for n_, d_, c_, lw_ in LAY:
    if n_.startswith(('A-921', 'A-922')): l_ = zdoc.layers.add(n_, color=c_, lineweight=lw_); l_.description = d_
zmsp = zdoc.modelspace()
if 'UNSPOT' not in zdoc.appids: zdoc.appids.new('UNSPOT')
ZIN = os.environ.get('ZONES_IN_DXF') == '1'
def zone_poly(g, lay, rgb_, alpha, xd):
    for target in ([zmsp, msp] if ZIN else [zmsp]):
        for q in getattr(g, 'geoms', [g]):
            if q.geom_type != 'Polygon' or q.is_empty: continue
            rings = [[mm(v) for v in q.exterior.coords]] + [[mm(v) for v in h.coords] for h in q.interiors]
            for k_, r in enumerate(rings):
                e_ = draw_curve(target, r, True, {'layer': lay + 'E-'})
                if e_ is not None:
                    try: e_.set_xdata('UNSPOT', xd + [(1000, 'ring=' + ('outer' if k_ == 0 else 'hole'))])
                    except Exception: pass
            h = target.add_hatch(dxfattribs={'layer': lay + 'H-'}); h.set_solid_fill(); h.rgb = rgb_; h.transparency = alpha
            for k_, r in enumerate(rings): hatch_path(h, r, k_ == 0)
            try: h.set_xdata('UNSPOT', xd)
            except Exception: pass
            if target is zmsp: nz[lay] += 1
if os.path.exists('rooms.pkl'):
    for r in pickle.load(open('rooms.pkl', 'rb'))['rooms']:
        xd = [(1000, 'group=7'), (1000, 'type=room'), (1000, f"kind={r['kind']}"), (1000, f"number={r.get('number', '')}"),
              (1000, f"name={' '.join(r.get('names', []))}"), (1000, f"area_m2={r['area_m2']}")]
        zone_poly(r['poly'], 'A-921---', (255, 214, 140), 0.6, xd)
if os.path.exists('passage.pkl'):
    _PZ = pickle.load(open('passage.pkl', 'rb')); _PK = _PZ.get('kinds') or ['open space'] * len(_PZ['passage'])
    for g, kd in zip(_PZ['passage'], _PK):
        zone_poly(g, 'A-922---', (120, 220, 150), 0.6, [(1000, 'group=7'), (1000, 'type=passage'), (1000, f'kind={kd}')])
zout = os.path.join(OUTDIR, sheet.OUT + '_zones.dxf'); zaud = zdoc.audit(); zdoc.saveas(zout)
print('zones', dict(nz), '->', zout, 'audit errors', len(zaud.errors), '| in the plan DXF too' if ZIN else '')
# ---- texts
SHEET = sheet.SHEET_BOXES                       # cfg.SHEET_BOXES: texts of the sheet frame are not the plan's
AXRE = getattr(sheet.cfg, 'OCG_AXIS_TEXT_RE', None)   # cfg.OCG_AXIS_TEXT_RE: names of the axes
def tlayer(t):
    s = t['text'].strip()
    if AXRE and re.fullmatch(AXRE, s): return 'A-AX----T-', 'axis'
    if s.startswith('ПК'): return 'A-68----T-', 'fire'          # code 009: Т4-14 - a text lies on '...T-' (S14*)
    return 'A-90----T-', 'text'
nt = collections.Counter()
for t in T:
    x0, y0, x1, y1 = t['bbox']
    if any(x0 >= b[0] and x1 <= b[2] and y0 >= b[1] and y1 <= b[3] for b in SHEET): nt['sheet title (not drawn)'] += 1; continue
    lay, kind = tlayer(t)
    ang = -math.degrees(math.atan2(t['dir'][1], t['dir'][0]))
    e = msp.add_text(t['text'], dxfattribs={'layer': lay, 'height': t['size'] * 0.72 * K, 'rotation': ang})
    e.set_placement(mm(t['origin']))
    col = t['color']; r, g, b = (col >> 16) & 255, (col >> 8) & 255, col & 255
    if col: e.rgb = (r, g, b)
    nt[kind] += 1
print('texts', dict(nt))
out = os.path.join(OUTDIR, sheet.OUT + ('_outline.dxf' if VAR == 'outline' else '_engineering.dxf'))
aud = doc.audit(); doc.saveas(out)
st = dict(points=dict(NSTAT), zones=dict(nz), walls=wstats, columns=len(Wmm.get('column', [])), blocks=len(bdef), inserts=nins, raw=nraw, texts=dict(nt),
          audit_errors=len(aud.errors), audit_fixes=len(aud.fixes), objects=dict(collections.Counter(o['name'] for o in objs)))
json.dump(st, open(os.path.join(OUTDIR, 'export_stats.json'), 'w'), ensure_ascii=False, indent=1)
print('saved', out, 'audit errors', len(aud.errors), 'fixes', len(aud.fixes), f'{time.time() - t0:.1f} s')
