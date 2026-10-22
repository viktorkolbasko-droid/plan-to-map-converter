# Step between the final assign and export (29.09.2026, check 3.7, plan/rules/40 §13): an unclassified object ('misc',
#   layer A-00) that is a piece of a recognised object, a column, a round table or pouf, a remnant inside a wall, or a
#   detail of a partition / of the glazing gets its class. In: assign2_pre.pkl (what assign wrote); out: assign2.pkl
#   (inst, free), which export and the checks read - the step can run again and gives the same result.
#   Report: reclass.json - counts and places by rule; checks/reclass_sheet.py draws them.
#   python3 reclass.py [--dry]   (--dry: report only, to reclass_dry.json; assign2.pkl and reclass.json untouched -
#   until 30.09.2026 a dry run overwrote reclass.json, and the floor's report no longer described its assign2.pkl)
# Rules, in this order (the first that fits wins):
#   Z. finish of a wall outside its body: misc linework inside cfg.WALL_FINISH_ZONES goes to the wall's layer.
#   R. round column: two or more concentric closed circles 250-900 mm (or one circle on a grid node) drawn as chains of
#      short thick chords - LPART_CHAINS takes them for curved glass partitions (floor 1: the pairs of 440 mm columns
#      along the south facade). The circles and the misc pieces inside them become one column.
#   A. piece of an object: the misc bbox lies >= 80 % inside the object's bbox grown by 1 pt, and the misc linework
#      touches the object's own (<= 0.1 pt). The object with the largest share takes it. Floors 1, 2, 4, 6: the seat edge,
#      outline or lever of an armchair that the family template does not hold (chairs differ there), door and desk
#      bits, pot rims of plants. Not a carpet (what stands on a carpet is its own object, owner 28.09). A canonical
#      block (chair, desk...) draws what it does not cover as its own raw lines (export, orphans).
#   B. steel column: the object's outline is an I (two flanges joined by a web through their middle) 150-750 mm at any
#      angle, and that outline carries >= 60 % of the object's linework.
#   W. remnant inside the walls: all of the object lies in the wall bodies (<= 0.1 pt): hatch strokes, fill bands.
#   C. round table / pouf: one circle (4piA/P^2 >= 0.9) 350-1300 mm holding everything of the object, little inside it.
#   D. detail of a partition or of the glazing: a small neutral-coloured piece (<= 600 mm, <= 40 primitives) hugging
#      (>= 70 % of its length within 0.8 pt) and touching a light partition, a glass partition or the facade.
# The rest stays 'misc': the catalogue of check 3.7 (checks/misc_inventory.py, misc_catalogue.py) names its groups.
import sys, math, json, collections, pickle, os
from common import *
from shapely.geometry import LineString, Polygon, Point, MultiPoint, box as sbox
from shapely.ops import unary_union, polygonize
from shapely.strtree import STRtree
from shapely.prepared import prep
import numpy as np
from scipy.spatial import cKDTree
DRY = '--dry' in sys.argv
P = load()
_CLS = pickle.load(open('cls.pkl', 'rb'))          # primitive classes (sheet / axis / dim are not drawing)
# the input is what assign wrote (assign2_pre.pkl): run again, the step starts from the same objects; the result goes to
#   assign2.pkl, which export and the checks read
inst, free = pickle.load(open('assign2_pre.pkl' if os.path.exists('assign2_pre.pkl') else 'assign2.pkl', 'rb'))
FABRIC = ('lpart', 'lpartc', 'facade', 'glass', 'wallline', 'loose', 'roomsep', 'zone', 'axmark', 'tag', 'misc', 'grey',
          'sign', 'atrium', 'carpet', 'mark', 'grate', 'mask')   # (30.09) a grate takes nothing: rule A gave it 2 grey paving lines (floor 1)
# (01.10.2026, code 005) a Revit mask (rule M) takes nothing either: a white strip is not the owner of the lines across it.
#   checks/misc_context.py uses the same list - before, a piece touching a mark was 'a fragment of mark' there (floor 4,
#   a stop of the gate) while rule A never gives anything to a mark
GROW = 1.0                                        # pt
def geo(i):
    p = P[i]; q = pts(p)
    if p[0] == 'qu' and len(q) >= 4:
        g = Polygon(q); return g if g.is_valid else g.buffer(0)
    return LineString(q) if len(q) > 1 else Point(q[0])
def bb(ids):
    q = [v for i in ids for v in pts(P[i])]
    return (min(x for x, y in q), min(y for x, y in q), max(x for x, y in q), max(y for x, y in q))
def lines_of(ids):
    out = []
    for i in ids:
        p = P[i]; q = pts(p)
        if len(q) < 2: continue
        if p[0] == 'qu' and p[2] is None and p[3] is not None and min(p[3]) >= 0.97: continue   # white mask
        out.append(LineString(q + ([q[0]] if p[0] == 'qu' else [])))
    return out
def circ_of(poly):
    per = poly.exterior.length
    return (4 * math.pi * poly.area / per ** 2 if per else 0), 2 * math.sqrt(poly.area / math.pi) * MM_PER_PT
moved = {}; REP = collections.defaultdict(list); cnt = collections.Counter(); NEW = []
# ---------------- 0. parts. A 'misc' object is a raster-connected leftover of assign (floor 6: a whole washroom of
#   3 071 primitives; a table with four turned chairs). Its vector-connected parts - primitives touching <= 0.05 pt, a
#   fill together with what lies on it, a white mask by its outline only - are classified one by one.
def _cg(i):
    p = P[i]
    if p[0] == 'qu' and p[2] is None and p[3] is not None and min(p[3]) >= 0.97:
        q = pts(p); return LineString(q + [q[0]]) if len(q) > 1 else Point(q[0])
    return geo(i)
def parts_of(ids):
    if len(ids) == 1: return [list(ids)]
    gs = [_cg(i) for i in ids]; tr = STRtree(gs); par_ = list(range(len(ids)))
    def f_(a):
        while par_[a] != a: par_[a] = par_[par_[a]]; a = par_[a]
        return a
    for k, g in enumerate(gs):
        for j in tr.query(g.buffer(0.05)):
            if j > k and gs[j].distance(g) <= 0.05: par_[f_(j)] = f_(k)
    comp_ = collections.defaultdict(list)
    for k, i in enumerate(ids): comp_[f_(k)].append(i)
    return sorted(comp_.values(), key=lambda c: -len(c))
_objs0 = sum(1 for q in inst if q['key'] == 'misc' and q['prims'])
for n in [n for n, q in enumerate(inst) if q['key'] == 'misc' and q['prims']]:
    ps_ = parts_of(inst[n]['prims'])
    if len(ps_) < 2: continue
    inst[n]['prims'] = ps_[0]
    for c in ps_[1:]: inst.append(dict(key='misc', name=inst[n]['name'], layer=inst[n]['layer'], prims=c))
MISC = [n for n, q in enumerate(inst) if q['key'] == 'misc' and q['prims']]
SPLIT = len(MISC) - _objs0; PARTS0 = len(MISC)
MISC_PRIMS0 = sum(len(inst[n]['prims']) for n in MISC)
AX = [(x, y) for x in AX_X for y in AX_Y] if AX_X and AX_Y else []
def on_node(c): return bool(AX) and min(math.dist(c, a) for a in AX) * MM_PER_PT < 150
# ---------------- R. round columns out of the curved-partition chains
_ek = lambda p: (round(p[0] / 0.06), round(p[1] / 0.06))
circles = []                                       # (centre, D, ids, lpartc instances)
# chains of the curved-partition step plus thick 'misc' chords: a piece left in 'misc' breaks a circle (floor 1)
_own = {}
for n, q in enumerate(inst):
    if q['key'] == 'lpartc' or (q['key'] == 'misc' and q['prims']):
        for i in q['prims']:
            if P[i][0] == 'l' and (q['key'] == 'lpartc' or (P[i][1] or 0) >= 0.45): _own[i] = n
ids = list(_own)
par = {i: i for i in ids}
def fnd(a):
    while par[a] != a: par[a] = par[par[a]]; a = par[a]
    return a
em = collections.defaultdict(list)
for i in ids:
    for e in P[i][4]: em[_ek(e)].append(i)
for v in em.values():
    for j in v[1:]: par[fnd(j)] = fnd(v[0])
comp = collections.defaultdict(list)
for i in ids: comp[fnd(i)].append(i)
for cids in comp.values():
    if len(cids) < 8: continue
    ps = [p for p in polygonize(unary_union([LineString(P[i][4]) for i in cids])) if p.area > 0.5]
    if len(ps) != 1: continue
    ci, D = circ_of(ps[0])
    if ci >= 0.95 and 250 <= D <= 900:
        circles.append(((ps[0].centroid.x, ps[0].centroid.y), D, cids, sorted(set(_own[i] for i in cids if inst[_own[i]]['key'] == 'lpartc'))))
used = set()
for k, (c, D, ids, n) in enumerate(circles):
    if k in used: continue
    grp = [k] + [j for j, (c2, D2, _, _) in enumerate(circles) if j != k and j not in used and math.dist(c, c2) * MM_PER_PT < 0.1 * max(D, D2)]
    if len(grp) < 2 and not on_node(c): continue
    used.update(grp); Dm = max(circles[j][1] for j in grp); cids = [i for j in grp for i in circles[j][2]]
    zone = Point(c).buffer(Dm / 2 / MM_PER_PT + 0.3)
    inside = [m for m in MISC if m not in moved and zone.contains(sbox(*bb(inst[m]['prims'])))]
    # misc objects holding chords of the circles, and those lying inside them
    inside = sorted(set(inside) | set(_own[i] for i in cids if inst[_own[i]]['key'] == 'misc'))
    for m in inside: moved[m] = ('R-piece', len(NEW))
    NEW.append(dict(key='column', name=f'Колонна круглая ⌀{round(Dm / 10) * 10} (по исходнику)', layer='A-28----E-',
                    prims=sorted(set(cids) | set(i for m in inside for i in inst[m]['prims'])), reclass='R',
                    _from=sorted(set(k_ for j in grp for k_ in circles[j][3]))))
    cnt['R'] += 1; REP['R'].append(dict(at_pt=[round(c[0], 1), round(c[1], 1)], d_mm=round(Dm), circles=len(grp), pieces=len(inside)))
# R2. paired round columns (owner 01.10.2026, question 4: "the columns of the same colonnade as on floor 1"). A closed
#   ring of thick dark chords 250-900 mm whose twin - the same diameter +-5 % - is 0.6-1.2 m away: the paired columns
#   of the colonnade outside the glazing, drawn as single rings (floors 2, 4, 5: D 323 mm, 830 mm apart). Rule R takes
#   only concentric rings or a ring on a grid node; these lay in the facade, the partition joints, a plant. A ring the
#   plan already holds as a column counts as a twin and stays as it is.
_r2own = {i: n for n, q in enumerate(inst) if q['key'] in ('facade', 'lpartc', 'lpart', 'misc', 'glass', 'plant', 'axmark', 'loose', 'column') for i in q['prims']}
_r2ids = [i for i in _r2own if P[i][0] == 'l' and (P[i][1] or 0) >= 0.4 and P[i][2] is not None and max(P[i][2]) <= 0.3 and math.dist(*P[i][4][:2]) * MM_PER_PT <= 150]
_r2p = {i: i for i in _r2ids}
def _r2f(a):
    while _r2p[a] != a: _r2p[a] = _r2p[_r2p[a]]; a = _r2p[a]
    return a
_r2em = collections.defaultdict(list)
for i in _r2ids:
    for e in P[i][4]: _r2em[_ek(e)].append(i)
for v in _r2em.values():
    for j in v[1:]: _r2p[_r2f(j)] = _r2f(v[0])
_r2c = collections.defaultdict(list)
for i in _r2ids: _r2c[_r2f(i)].append(i)
_rings2 = []
for cids in _r2c.values():
    if len(cids) < 8: continue
    ps = [p for p in polygonize(unary_union([LineString(P[i][4]) for i in cids])) if p.area > 0.5]
    if len(ps) != 1: continue
    ci, D = circ_of(ps[0])
    if ci >= 0.95 and 250 <= D <= 900 and not any(math.dist((ps[0].centroid.x, ps[0].centroid.y), c_) * MM_PER_PT < 0.1 * D for c_, _, _, _ in circles):
        _rings2.append(((ps[0].centroid.x, ps[0].centroid.y), D, cids, ps[0]))
for k, (c, D, cids, g) in enumerate(_rings2):
    if not any(j != k and abs(D2 - D) <= 0.05 * D and 600 <= math.dist(c, c2) * MM_PER_PT <= 1200 for j, (c2, D2, _, _) in enumerate(_rings2)): continue
    owners_ = sorted(set(_r2own[i] for i in cids))
    if all(inst[n]['key'] == 'column' for n in owners_): continue                 # already a column
    zone = g.buffer(0.3)
    inside = [m for m in MISC if m not in moved and zone.contains(sbox(*bb(inst[m]['prims'])))]
    extra = [i for n in owners_ if inst[n]['key'] != 'column' for i in inst[n]['prims'] if i not in set(cids) and P[i][0] == 'qu' and zone.contains(sbox(*bb([i])))]
    for m in inside: moved[m] = ('R-piece', len(NEW))
    NEW.append(dict(key='column', name=f'Колонна круглая ⌀{round(D / 10) * 10} (колоннада, по исходнику)', layer='A-28----E-',
                    prims=sorted(set(cids) | set(extra) | set(i for m in inside for i in inst[m]['prims'])), reclass='R2',
                    _from=[n for n in owners_ if inst[n]['key'] != 'column']))
    cnt['R2'] += 1; REP['R2'].append(dict(at_pt=[round(c[0], 1), round(c[1], 1)], d_mm=round(D), from_=[inst[n]['key'] for n in owners_]))
# ---------------- Z. the finish of a wall drawn outside its body (cfg.WALL_FINISH_ZONES, floor 2: the teeth along the
#   round wall between axes Д and Г/2): unclassified linework lying in the zone goes to the wall's layer
_FZ = []
for z in getattr(cfg, 'WALL_FINISH_ZONES', []):
    zz = z['zone']
    g_ = sbox(*zz) if len(zz) == 4 and all(isinstance(v, (int, float)) for v in zz) else LineString(zz[0]).buffer(zz[1], cap_style=2)
    _FZ.append((prep(g_.buffer(0.3)), z))
for n in MISC:
    if not _FZ: break
    ls = lines_of(inst[n]['prims'])
    if not ls: continue
    u = unary_union(ls)
    for zp, z in _FZ:
        if zp.contains(u): moved[n] = ('Z', z); break
# code 007: the walls of the loop (walls_pre7.pkl), not fix7's output - run.sh export reruns reclass after fix7 has
#   rewritten walls.pkl, and the step must see the same walls in both modes
_WF = pickle.load(open('walls_pre7.pkl' if os.path.exists('walls_pre7.pkl') else 'walls.pkl', 'rb'))['Wpt']
_WC = {k: prep(unary_union(v).buffer(0.1)) for k, v in _WF.items() if v}
_WUall = prep(unary_union([g for v in _WF.values() for g in v]).buffer(0.1)) if _WF else None
_WSPLIT = getattr(cfg, 'W_SPLIT', False)   # rule W splits a wall-fill piece from the strokes glued to it (see rule W)
_WU25 = prep(unary_union([g for v in _WF.values() for g in v]).buffer(0.25)) if (_WF and _WSPLIT) else None
WL = {'ext': 'A-21----E-', 'cap': 'A-221---E-', 'gkl': 'A-222---E-', 'blk': 'A-223---E-'}
def _neutral_c(c): return c is None or (abs(c[0] - c[1]) < 0.03 and abs(c[1] - c[2]) < 0.03)
def _white_mask(p): return p[0] == 'qu' and p[2] is None and p[3] is not None and min(p[3]) >= 0.97
def _mrr_sides(g):
    r = g.minimum_rotated_rectangle
    if r.geom_type != 'Polygon': return (g.length, 0.0)
    c = list(r.exterior.coords); a, b = math.dist(c[0], c[1]), math.dist(c[1], c[2]); return (max(a, b), min(a, b))
def _owners():
    o = {}
    for n, q in enumerate(inst):
        for i in q['prims']: o[i] = n
    return o
def _new_obj(key, name, layer, ids, rule, **kw):
    """a new object made of primitives taken from their owners (in memory; saved at the end unless --dry)"""
    own = _owners(); s_ = set(ids)
    for n in set(own[i] for i in ids if i in own): inst[n]['prims'] = [i for i in inst[n]['prims'] if i not in s_]
    inst.append(dict(key=key, name=name, layer=layer, prims=sorted(s_), reclass=rule, **kw)); return len(inst) - 1
def _misc_now(): return [n for n, q in enumerate(inst) if q['key'] == 'misc' and q['prims'] and n not in moved]
# ---------------- W, split (cfg.W_SPLIT, 30.09.2026, floor 5 run 2): a piece that holds a wall's own fill (grey, not a
#   white mask) lying in the wall bodies, glued by the raster to strokes outside them (the jamb box of a door at the end of
#   the concrete wall of the NE stair; a 0.02 pt overshoot of a tick), is two things: what lies in the walls (+0.25 pt) is
#   the wall's remnant (rule W), the rest a new 'misc' piece for all the rules below (before rule X, so that an operator
#   entry can name it). Floor 5: 4 pieces of the concrete walls (fill 0.96 and the pattern marks) were 'misc'. Off by default
if _WSPLIT and _WU25 is not None:
    for n in list(MISC):
        if n in moved: continue
        q = inst[n]
        ins_ = [i for i in q['prims'] if _WU25.contains(LineString(pts(P[i]) + ([pts(P[i])[0]] if P[i][0] == 'qu' else []))
                                                   if len(pts(P[i])) > 1 else _WU25.contains(Point(pts(P[i])[0])))]
        if not any(P[i][0] == 'qu' and P[i][3] is not None and not _white_mask(P[i]) for i in ins_): continue
        s_ = set(ins_); rest_ = [i for i in q['prims'] if i not in s_]
        if rest_:                           # all in the walls within 0.25 pt (a 0.02 pt overshoot): rule W, nothing left over
            q['prims'] = sorted(ins_)
            inst.append(dict(key='misc', name=q['name'], layer=q['layer'], prims=sorted(rest_))); MISC.append(len(inst) - 1)
        u_ = unary_union(lines_of(q['prims']))
        moved[n] = ('W', max(_WC, key=lambda k: 1 if _WC[k].contains(u_) else 0)); cnt['W_split'] += 1
        _b = bb(q['prims']); REP['W_split'].append(dict(misc=n, at_pt=[round((_b[0] + _b[2]) / 2, 1), round((_b[1] + _b[3]) / 2, 1)], in_wall=len(ins_), left=len(rest_)))
# ---------------- Z2. the strokes of a wall the operator drew (cfg.WALL_ZONES) that its body did not take - contour and hatch strokes of
#   the round wall of floor 2 left in 'misc' and in the curved-partition chains - are that wall's: covered by its body,
#   they are its body (not drawn again); the rest are its lines on its layer (the owner's floor 2 screenshot, 29.09.2026)
_WZ2 = []
for z in getattr(cfg, 'WALL_ZONES', []):
    zz = z['zone']
    g_ = sbox(*zz) if len(zz) == 4 and all(isinstance(v, (int, float)) for v in zz) else LineString(zz[0]).buffer(zz[1], cap_style=2)
    _WZ2.append((g_, z))
if _WZ2:
    OWN = _owners()
    for g_, z in _WZ2:
        zp = prep(g_.buffer(0.3))
        take_ = [i for i in range(len(P)) if i in OWN and inst[OWN[i]]['key'] in ('misc', 'lpartc') and OWN[i] not in moved
                 and len(pts(P[i])) > 1 and zp.contains(LineString(pts(P[i])))]
        # a stroke the wall body covers (<= 0.4 pt, the tolerance of the strict ink check) is the body's own line and is
        #   not drawn again: drawn raw it lay as a thick patch over the body (floor 2, at the grid line); the rest are
        #   the wall's lines on its layer
        _body = prep(unary_union([g for v in _WF.values() for g in v]).buffer(0.4)) if _WF else None
        covered = [i for i in take_ if _body is not None and _body.contains(LineString(pts(P[i])))]
        rest = [i for i in take_ if i not in set(covered)]
        if covered:
            _cs = set(covered)
            for n_ in set(OWN[i] for i in covered): inst[n_]['prims'] = [i for i in inst[n_]['prims'] if i not in _cs]
        if rest: _new_obj('wallline', 'Линии стены по исходнику (контур, штриховка)', WL.get(z.get('cls'), 'A-221---E-'), rest, 'Z2')
        if take_:
            cnt['Z2'] += 1; b_ = g_.bounds
            REP['Z2'].append(dict(at_pt=[round((b_[0] + b_[2]) / 2, 1), round((b_[1] + b_[3]) / 2, 1)], covered_by_body=len(covered), drawn=len(rest)))
    MISC = [n for n in MISC if inst[n]['prims']]
# ---------------- K, J, P (owner 30.09.2026, groups 17, 18, 21, 22): service marks, drainage grates and railings are
#   drawn as loose strokes that assign scattered over 'misc', the light partitions, their joints and the loose bits.
#   Their primitives are pulled out of those owners into objects of their own (_new_obj). J and P run here, K after
#   rule X (below, before rule A).
#   K. a service mark (groups 21-22; owner: "some mark" -> its own service layer, not an object of the plan): a '+' of
#      two straight lines 95-230 mm (the longer <= 1.1 x the shorter) at 90 +- 3 deg crossing at both their middles
#      (<= 0.15 pt), with the tiny strokes (< 0.45 pt) of a ring around it that lie within 0.6 of the cross length of
#      its centre (the green ⊕ of floor 2). Not in a wall body (a cross of the hatch of floor 2's round wall), not a
#      '#' (a line 0.7-1.3 of an arm, parallel to it within 0.8 pt and overlapping it: the socket sign of floor 2).
#      Floor 1: 11 crosses about 200 mm at corners of walls, stairs and mats; floor 2: 8 green ⊕; floor 6: black and
#      purple crosses at wall corners and columns.
#   J. a drainage grate (group 17; owner: "let it be a drainage grate"): >= 20 dots - pieces of >= 6 tiny strokes
#      20-50 mm across - chained <= 150 mm apart into a grid >= 300 mm both ways and >= 3 rows and columns (floor 1: two
#      of 1.3 x 0.5 m on the paving of the passage to the entrance), with the small fills of its dots.
#   P. a railing (group 18; owner: "some railing, glass or metal, that cannot be passed; it is all the turnstile zone -
#      put it on the layer of walls and glazing"): >= 5 rings - loops of tiny strokes 45-80 mm - in a straight row
#      (<= 0.3 pt off the line, even steps +-25 %, a step <= 4 pt), with what lies on that line beyond the rings, each
#      piece <= 1.5 pt from the previous one: posts (a fabric piece <= 200 mm across centred on the line) and rail
#      strokes (all their points within 0.35 pt of the line, free ones too - floor 6's rails were thin fills that no
#      object held and export did not draw). Floor 6: post - rail - post - 20 rings to the facade; 7 rings from a wall
#      to the turnstiles.
_KF = ('misc', 'lpart', 'lpartc', 'loose')
OWN = _owners(); FREE = set(free)
def _fab(i): return i in OWN and inst[OWN[i]]['key'] in _KF
def _pts2(i): return pts(P[i])
_ek2 = lambda e: (round(e[0] / 0.03), round(e[1] / 0.03))
_tiny = [i for i, p in enumerate(P) if p[0] == 'l' and math.dist(*p[4]) < 0.45 and _fab(i)]
_tp = {i: i for i in _tiny}
def _tf(a):
    while _tp[a] != a: _tp[a] = _tp[_tp[a]]; a = _tp[a]
    return a
_tem = collections.defaultdict(list)
for i in _tiny:
    for e in P[i][4]: _tem[_ek2(e)].append(i)
for v in _tem.values():
    for j in v[1:]: _tp[_tf(j)] = _tf(v[0])
_tcomp = collections.defaultdict(list)
for i in _tiny: _tcomp[_tf(i)].append(i)
DOTS, RINGS = [], []
for c in _tcomp.values():
    if len(c) < 6: continue
    xs = [v[0] for i in c for v in P[i][4]]; ys = [v[1] for i in c for v in P[i][4]]
    w, h = (max(xs) - min(xs)) * MM_PER_PT, (max(ys) - min(ys)) * MM_PER_PT
    if abs(w - h) > 0.3 * max(w, h): continue
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2; d_ = (w + h) / 2
    if 20 <= d_ <= 50 and 20 <= min(w, h): DOTS.append((cx, cy, d_, c))
    R_ = d_ / 2 / MM_PER_PT
    if 45 <= d_ <= 80 and min(math.dist((cx, cy), (x, y)) for x, y in zip(xs, ys)) >= 0.45 * R_:
        RINGS.append((cx, cy, d_, c))
def _chains(items, gap):
    if not items: return []
    A_ = np.array([(a, b) for a, b, _, _ in items]); T_ = cKDTree(A_); lab_ = -np.ones(len(A_), int); k_ = 0
    for s in range(len(A_)):
        if lab_[s] >= 0: continue
        st = [s]; lab_[s] = k_
        while st:
            j = st.pop()
            for m in T_.query_ball_point(A_[j], gap):
                if lab_[m] < 0: lab_[m] = k_; st.append(m)
        k_ += 1
    return [[items[j] for j in np.nonzero(lab_ == l)[0]] for l in range(k_)]
# J. grates
for ch in _chains(DOTS, 150 / MM_PER_PT):
    if len(ch) < 20: continue
    xs = [v[0] for _, _, _, c in ch for i in c for v in P[i][4]]; ys = [v[1] for _, _, _, c in ch for i in c for v in P[i][4]]
    W_, H_ = (max(xs) - min(xs)) * MM_PER_PT, (max(ys) - min(ys)) * MM_PER_PT
    rows_ = len(set(round(y / 0.5) for _, y, _, _ in ch)); cols_ = len(set(round(x / 0.5) for x, _, _, _ in ch))
    if min(W_, H_) < 300 or rows_ < 3 or cols_ < 3: continue
    gb = sbox(min(xs), min(ys), max(xs), max(ys)).buffer(0.3)
    ids_ = [i for _, _, _, c in ch for i in c]
    ids_ += [i for i in range(len(P)) if P[i][0] == 'qu' and P[i][3] is not None and _fab(i) and not _white_mask(P[i])
             and gb.contains(sbox(*bb([i]))) and max(bb([i])[2] - bb([i])[0], bb([i])[3] - bb([i])[1]) * MM_PER_PT <= 60]
    _new_obj('grate', f'Водоотводная решётка {round(W_ / 10) * 10}×{round(H_ / 10) * 10} (по исходнику)', 'A-52----E-', ids_, 'J')
    cnt['J'] += 1; REP['J'].append(dict(at_pt=[round((min(xs) + max(xs)) / 2, 1), round((min(ys) + max(ys)) / 2, 1)], dots=len(ch), size_mm=[round(W_), round(H_)]))
    OWN = _owners()
# P. railings
_axl = [(i, LineString(_pts2(i)) if len(_pts2(i)) > 1 else Point(_pts2(i)[0])) for i in range(len(P))
        if (P[i][0] in ('l', 'qu') and (_fab(i) or i in FREE)) and not _white_mask(P[i])]
_AXT = STRtree([g for _, g in _axl]) if _axl else None
for ch in _chains(RINGS, 4.0):
    if len(ch) < 5 or _AXT is None: continue
    A_ = np.array([(a, b) for a, b, _, _ in ch]); c0 = A_.mean(0); _, _, vt = np.linalg.svd(A_ - c0); u_, n_ = vt[0], vt[1]
    if np.abs((A_ - c0) @ n_).max() > 0.3: continue
    t_ = np.sort((A_ - c0) @ u_); g_ = np.diff(t_)
    if g_.max() > 4.0 or g_.std() > 0.25 * g_.mean(): continue
    t0, t1 = float(t_[0]) - 0.6, float(t_[-1]) + 0.6; ids_ = [i for _, _, _, c in ch for i in c]; used_ = set(ids_)
    p0 = c0 + u_ * (t0 - 45); p1 = c0 + u_ * (t1 + 45); band = LineString([tuple(p0), tuple(p1)]).buffer(1.3, cap_style=2)
    def _iv(q_):
        pr = (np.array(q_) - c0); return float((pr @ u_).min()), float((pr @ u_).max()), float(np.abs(pr @ n_).max())
    pieces = []
    for j in _AXT.query(band):
        i, g = _axl[j]
        if i in used_ or not band.contains(g): continue
        if _WUall is not None and _WUall.contains(g): continue
        a_, b_, off_ = _iv(_pts2(i))
        if off_ <= 0.35 and b_ - a_ >= 0.3: pieces.append((a_, b_, [i]))        # a rail stroke along the line
    seen_ = set()
    for m, q in enumerate(inst):                                               # posts: small fabric pieces on the line
        if q['key'] not in _KF or not q['prims'] or m in seen_: continue
        bx = bb(q['prims'])
        if max(bx[2] - bx[0], bx[3] - bx[1]) * MM_PER_PT > 200: continue
        cc = np.array(((bx[0] + bx[2]) / 2, (bx[1] + bx[3]) / 2)) - c0
        if abs(cc @ n_) > 0.35 or not (t0 - 45 <= cc @ u_ <= t1 + 45): continue
        a_, b_, _ = _iv([v for i in q['prims'] for v in _pts2(i)])
        pieces.append((a_, b_, [i for i in q['prims'] if i not in used_])); seen_.add(m)
    grew = True
    while grew:
        grew = False
        for pc in list(pieces):
            a_, b_, ii = pc
            if (a_ <= t1 + 1.5 and b_ >= t0 - 1.5) and (a_ < t0 or b_ > t1):
                t0, t1 = min(t0, a_), max(t1, b_); ids_ += [i for i in ii if i not in used_]; used_.update(ii); pieces.remove(pc); grew = True
    FREE -= set(ids_)
    _new_obj('railing', 'Ограждение — перила (по исходнику)', 'A-22G---E-', ids_, 'P')
    e0, e1 = c0 + u_ * t0, c0 + u_ * t1
    cnt['P'] += 1; REP['P'].append(dict(at_pt=[round(float(c0[0]), 1), round(float(c0[1]), 1)], rings=len(ch), length_mm=round((t1 - t0) * MM_PER_PT),
                                        ends_pt=[[round(float(e0[0]), 1), round(float(e0[1]), 1)], [round(float(e1[0]), 1), round(float(e1[1]), 1)]]))
    OWN = _owners()
free = [i for i in free if i in FREE]
MISC = _misc_now()
# ---------------- F. a furniture body inside the fabric (29.09.2026, check 3.10). A coloured fill (saturation >= 0.1,
#   or a desk colour) of >= 0.05 m2 and >= 250 mm across (a partition is thinner), outlined by lines along >= half its
#   edge, owned by a light partition, its joints or 'misc', together with the fabric and 'misc' primitives lying on it,
#   is furniture. Floor 1: the seats at the counter; floors 2, 5, 6: desk tops, desk groups and a meeting table were
#   'partition joints' in layer A-22G. A desk colour of the floor (cfg.DESK_FILLS, tan, a light wood >= 500 mm deep)
#   makes it a desk. Pale tints are not bodies: glass, floor zones, landings (floor 1).
_AMIN, _AMAX = 0.05e6 / MM_PER_PT ** 2, 12e6 / MM_PER_PT ** 2
def _warm(c): return c is not None and c[0] >= 0.75 and 0.12 <= c[0] - c[2] <= 0.35 and c[2] <= c[1] <= c[0]   # a light wood / beige top
OWN = _owners(); _FB = []
for i, p in enumerate(P):
    if p[0] != 'qu' or p[3] is None or i not in OWN or _white_mask(p): continue
    # a body is coloured: saturation >= 0.1, or a desk colour; the pale tints of glass, floor zones and landings are not
    #   (floor 1: the olive landings with the concrete hatch, the blue-grey glass of the partitions)
    if inst[OWN[i]]['key'] not in ('lpart', 'lpartc', 'misc') or not (max(p[3]) - min(p[3]) >= 0.1 or is_tan(p[3])): continue
    g = geo(i)
    # the size is judged on the body (touching fills together): a table drawn as wooden planks is a row of thin fills
    #   (floor 6, the meeting table of the octagonal room)
    if g.is_empty or g.geom_type not in ('Polygon', 'MultiPolygon') or g.area < 0.1 * _AMIN: continue
    if _WUall is not None and _WUall.contains(g): continue
    _FB.append((g, i))
_fl = [(LineString(pts(P[i])), i) for i in range(len(P)) if P[i][0] == 'l']
_FLT = STRtree([g for g, _ in _fl]) if _fl else None
_par = list(range(len(_FB)))
def _fp(a):
    while _par[a] != a: _par[a] = _par[_par[a]]; a = _par[a]
    return a
_fbt = STRtree([g for g, _ in _FB]) if _FB else None
for k, (g, i) in enumerate(_FB):
    for j in _fbt.query(g.buffer(0.05)):
        if j > k and _FB[j][0].distance(g) <= 0.05: _par[_fp(j)] = _fp(k)
_bodies = collections.defaultdict(list)
for k in range(len(_FB)): _bodies[_fp(k)].append(k)
_cand = [i for i in range(len(P)) if i in OWN and inst[OWN[i]]['key'] in ('lpart', 'lpartc', 'misc')]
_CG = [geo(i) for i in _cand]; _CT = STRtree(_CG) if _CG else None
for ks in _bodies.values():
    U = unary_union([_FB[k][0] for k in ks])
    if not (_AMIN <= U.area <= _AMAX) or _mrr_sides(U)[1] * MM_PER_PT < 250: continue
    edge = U.boundary
    near = [_fl[j][0] for j in _FLT.query(U.buffer(0.2))] if _FLT is not None else []
    if not near or edge.length <= 0 or edge.intersection(unary_union(near).buffer(0.15)).length < 0.5 * edge.length: continue
    Ub = prep(U.buffer(0.05)); take_ = [_cand[j] for j in _CT.query(U.buffer(0.05)) if Ub.contains(_CG[j])]
    desk = _mrr_sides(U)[1] * MM_PER_PT >= 500 and any(is_tan(P[_FB[k][1]][3]) or _warm(P[_FB[k][1]][3]) for k in ks)
    b_ = U.bounds
    n_ = _new_obj('desk_src' if desk else 'furn_src', 'Стол или группа столов (по исходнику)' if desk else 'Мебель с заливкой (по исходнику)',
                  'A-82----E-', take_, 'F')
    cnt['F:' + ('desk' if desk else 'furniture')] += 1
    REP['F'].append(dict(at_pt=[round((b_[0] + b_[2]) / 2, 1), round((b_[1] + b_[3]) / 2, 1)], prims=len(take_), desk=desk,
                         m2=round(U.area * MM_PER_PT ** 2 / 1e6, 2), fill=[round(v, 2) for v in P[_FB[ks[0]][1]][3]]))
MISC = _misc_now()
# ---------------- L, E. stairs and lifts that no operator box holds (29.09.2026, through elements: floors 1, 2, 6 had no
#   MANUAL stairs or lifts, their treads and cars lay in the light partitions and 'misc'). The lines of light partitions,
#   their joints, 'misc' and the loose bits are looked at.
#   L. a flight: >= 6 parallel lines 700-3000 mm long, of one length (+-10 %), overlapping (>= 70 %), 230-350 mm apart at
#      an even step (+-15 %); not a floor grid - at most two lines cross the treads in their inner part (the walking line).
#      The flight takes the candidate lines within its rectangle grown by 100 mm (treads, strings, arrow, break line).
#   E. a lift car: a cross - two diagonals 1200-4000 mm crossing at both their middles, each a whole line (floor 6) or
#      collinear pieces from the corners (floor 2) - whose four ends are the corners of a rectangle 900-2800 mm a side,
#      drawn around it along >= 50 % of its edge by lines of any class; it takes the candidate lines within the
#      rectangle (outline, cross, door marks). The cross is drawn in neutral strokes: a pink dashed cross (floor 1)
#      marks something overhead.
#   A flight or a car touching an operator's stair or lift (<= 300 mm) joins it: the box missed that part (floor 5).
OWN = _owners()
_LC = [i for i in range(len(P)) if P[i][0] == 'l' and i in OWN and inst[OWN[i]]['key'] in ('lpart', 'lpartc', 'misc', 'loose')]
_LCG = [LineString(P[i][4]) for i in _LC]; _LCT = STRtree(_LCG) if _LCG else None
def _ang(i):
    (x1, y1), (x2, y2) = P[i][4]; return math.degrees(math.atan2(y2 - y1, x2 - x1)) % 180
_tread = [k for k, i in enumerate(_LC) if 700 <= _LCG[k].length * MM_PER_PT <= 3000 and (P[i][1] or 0) <= 0.5]
_bydir = collections.defaultdict(list)
for k in _tread: _bydir[round(_ang(_LC[k])) % 180].append(k)
_used = set(); _flights = []
for a0, ks in _bydir.items():
    ks = ks + _bydir.get((a0 + 1) % 180, [])
    t = math.radians(a0); u = (math.cos(t), math.sin(t)); nrm = (-u[1], u[0])
    def proj(k):
        (x1, y1), (x2, y2) = P[_LC[k]][4]
        o = ((x1 + x2) / 2) * nrm[0] + ((y1 + y2) / 2) * nrm[1]
        s1, s2 = sorted((x1 * u[0] + y1 * u[1], x2 * u[0] + y2 * u[1])); return o, s1, s2
    rows = sorted((proj(k) + (k,)) for k in ks if k not in _used)
    i0 = 0
    while i0 < len(rows):
        run = [rows[i0]]
        for r_ in rows[i0 + 1:]:
            o, s1, s2, k = r_; po, ps1, ps2, pk = run[-1]
            step = (o - po) * MM_PER_PT
            if step < 1: continue                                     # the same line drawn twice
            if step > 350: break
            L1, L2 = ps2 - ps1, s2 - s1
            if 230 <= step and abs(L1 - L2) <= 0.1 * max(L1, L2) and (min(ps2, s2) - max(ps1, s1)) >= 0.7 * min(L1, L2):
                if len(run) >= 2:
                    st0 = (run[1][0] - run[0][0]) * MM_PER_PT
                    if abs(step - st0) > 0.15 * st0: break
                run.append(r_)
        if len(run) >= 6:
            ids_ = [r_[3] for r_ in run]
            rect = unary_union([_LCG[k] for k in ids_]).minimum_rotated_rectangle
            # a floor grid has lines across the treads everywhere; a flight has at most its walking line (and a double)
            inner = rect.buffer(-0.2 * min(_mrr_sides(rect)[1], 1e9) if rect.geom_type == 'Polygon' else 0)
            cross = [j for j in _LCT.query(rect) if j not in ids_ and abs(((_ang(_LC[j]) - a0 + 90) % 180) - 90) >= 80
                     and sum(1 for k in ids_ if _LCG[j].crosses(_LCG[k])) >= 0.6 * len(ids_) and _LCG[j].intersects(inner)]
            if len(cross) <= 2:
                _flights.append((ids_, rect)); _used.update(ids_); i0 += len(run); continue
        i0 += 1
_taken = set()
def _join_or_new(key, name, layer, ids, rule, rect):
    """a flight or a car touching (<= 300 mm) an object of the same class that was there before this step - an operator's
    box that missed a part of its stair or lift (floor 5: the box of the lift core lay 23 pt south of the cars, the box of
    the north-east stair cut its west flight) - joins that object; otherwise it is a new object. Objects made by this
    step are not joined: two flights of one stair stay two flights"""
    hs = [m for m, q in enumerate(inst) if q['key'] == key and q['prims'] and 'reclass' not in q]
    near = sorted((unary_union([geo(i) for i in inst[m]['prims']]).distance(rect), m) for m in hs)
    if near and near[0][0] * MM_PER_PT <= 300:
        m = near[0][1]; own = _owners(); s_ = set(ids)
        for o in set(own[i] for i in ids if i in own):
            if o != m: inst[o]['prims'] = [i for i in inst[o]['prims'] if i not in s_]
        inst[m]['prims'] = sorted(s_ | set(inst[m]['prims'])); return inst[m]['name']
    _new_obj(key, name, layer, ids, rule); return None
_MNL = [i for n in MISC for i in inst[n]['prims'] if P[i][0] != 'l']; _MNG = [geo(i) for i in _MNL]; _MNT = STRtree(_MNG) if _MNG else None
for ids_, rect in _flights:
    z = rect.buffer(100 / MM_PER_PT, join_style=2); zp = prep(z)
    take_ = [_LC[j] for j in _LCT.query(z) if zp.contains(_LCG[j]) and _LC[j] not in _taken]
    take_ += [_MNL[j] for j in (_MNT.query(z) if _MNT is not None else []) if _MNL[j] not in _taken and zp.contains(_MNG[j])]   # arrowheads
    if len(take_) < 6: continue
    _taken.update(take_); b_ = rect.bounds
    j_ = _join_or_new('stair', f'Лестничный марш: {len(ids_)} ступеней (по исходнику)', 'A-24----E-', take_, 'L', rect)
    cnt['L' + (':joined' if j_ else '')] += 1
    REP['L'].append(dict(at_pt=[round((b_[0] + b_[2]) / 2, 1), round((b_[1] + b_[3]) / 2, 1)], treads=len(ids_), prims=len(take_),
                         **({'joined': j_} if j_ else {})))
OWN = _owners()
_LC2 = [i for i in _LC if i not in _taken and inst[OWN[i]]['key'] in ('lpart', 'lpartc', 'misc', 'loose')]
_LG2 = [LineString(P[i][4]) for i in _LC2]; _LT2 = STRtree(_LG2) if _LG2 else None
_cars = []
if _LG2:
    # the cross of a car: two whole diagonals (floor 6) or four pieces from the corners (floor 2). Collinear pieces make
    #   one diagonal; two diagonals crossing at both their middles (<= 4 %) make a cross; the car is the rectangle of the
    #   cross's four ends, which must sit at its corners
    def _diagish(k): a = abs(((_ang(_LC2[k]) + 90) % 180) - 90); return 20 <= a <= 70
    _dk = [k for k, g in enumerate(_LG2) if _diagish(k) and g.length * MM_PER_PT >= 300 and _neutral_c(P[_LC2[k]][2])]
    _CLS = pickle.load(open('cls.pkl', 'rb'))
    _AL = [i for i in range(len(P)) if P[i][0] == 'l' and _CLS[i] not in ('dim', 'axis', 'sheet', 'tag')]
    _ALG = [LineString(P[i][4]) for i in _AL]; _ALT = STRtree(_ALG)
    _dg = []                                       # (a, b) end points of a diagonal
    _usedk = set()
    for k in _dk:
        if k in _usedk: continue
        (x1, y1), (x2, y2) = _LG2[k].coords; a0 = _ang(_LC2[k]); u = (math.cos(math.radians(a0)), math.sin(math.radians(a0)))
        grp = [k]
        for j in _LT2.query(_LG2[k].buffer(3000 / MM_PER_PT)):
            if j == k or j in _usedk or j not in set(_dk) or abs(((_ang(_LC2[j]) - a0 + 90) % 180) - 90) > 1: continue
            # collinear: the four ends lie on the line through the farthest two of them (<= 0.25 pt). Measured along a
            #   short piece's own direction the far piece drifts off by 0.4 pt (floor 2: pieces of 720 mm on a 2.5 m diagonal)
            e4 = list(_LG2[k].coords) + list(_LG2[j].coords)
            fa, fb = max(((a, b) for a in e4 for b in e4), key=lambda t: math.dist(*t)); Lf = LineString([fa, fb])
            if all(Lf.distance(Point(v)) <= 0.25 for v in e4): grp.append(j)
        ends = [v for j in grp for v in _LG2[j].coords]; tt = [(v[0] - x1) * u[0] + (v[1] - y1) * u[1] for v in ends]
        a_, b_ = ends[tt.index(min(tt))], ends[tt.index(max(tt))]
        if 1200 <= math.dist(a_, b_) * MM_PER_PT <= 4000: _dg.append((a_, b_)); _usedk.update(grp)
    for m, (a1, b1) in enumerate(_dg):
        for a2, b2 in _dg[m + 1:]:
            L1, L2 = LineString([a1, b1]), LineString([a2, b2])
            if not L1.crosses(L2): continue
            x_ = L1.intersection(L2); m1 = L1.interpolate(0.5, normalized=True); m2 = L2.interpolate(0.5, normalized=True)
            if x_.distance(m1) > 0.04 * L1.length or x_.distance(m2) > 0.04 * L2.length: continue
            e4 = [a1, b1, a2, b2]; rb = MultiPoint(e4).minimum_rotated_rectangle; L_, S_ = _mrr_sides(rb)
            cc = list(rb.exterior.coords)[:4]
            if not (900 <= S_ * MM_PER_PT and L_ * MM_PER_PT <= 2800): continue
            if max(min(math.dist(e, c_) for c_ in cc) for e in e4) > 0.04 * max(L1.length, L2.length): continue
            # the car's outline is drawn (by lines of any class: floor 2, its sides are wall-class lines in the shaft) -
            #   the chairs turned by 45 degrees between two round tables line up into a false cross (floor 6)
            edge = rb.exterior; near = [_ALG[j] for j in _ALT.query(rb.buffer(0.3)) if _ALG[j].distance(edge) <= 0.2]
            # >= 50 % of the edge: the cars of floors 1-6 have 69-100 % (floor 2: the long sides break at the middle, 69 %),
            #   the false crosses of turned chairs 13-15 %
            if not near or edge.intersection(unary_union(near).buffer(0.2)).length < 0.5 * edge.length: continue
            if not any(r_.equals_exact(rb, 0.5) for r_ in _cars): _cars.append(rb)
for rb in _cars:
    z = rb.buffer(0.3, join_style=2); zp = prep(z)
    take_ = [i for i in _LC2 if i not in _taken and zp.contains(LineString(P[i][4]))]
    if len(take_) < 4: continue
    _taken.update(take_); b_ = rb.bounds
    j_ = _join_or_new('lift', 'Лифт: кабина (по исходнику)', 'A-66----E-', take_, 'E', rb)
    cnt['E' + (':joined' if j_ else '')] += 1
    REP['E'].append(dict(at_pt=[round((b_[0] + b_[2]) / 2, 1), round((b_[1] + b_[3]) / 2, 1)], prims=len(take_),
                         size_mm=[round((b_[2] - b_[0]) * MM_PER_PT), round((b_[3] - b_[1]) * MM_PER_PT)], **({'joined': j_} if j_ else {})))
MISC = _misc_now()
# ---------------- S. a washbasin or sink (owner 29.09: group 12; the drain of group 23): a rounded closed outline
#   found from its drain: a small opening 10-70 mm in the ink of the 'misc' strokes (the drain ring) near the middle of a
#   clean opening 260-600 x 260-500 mm (the basin, >= 0.7 of its hull; at most two such rings: a grille of dots is not a
#   basin; a column's diamond marker 830 mm with an I-beam inside is not either, floor 6; an office chair's 205 mm seat
#   with its column is not either, floor 2).
#   The ink is each stroke grown by half its weight, x 1.3, so that strokes stopping short at a corner still close; the
#   long straight sides of a basin taken for light partitions close it too (floor 6: the pink basins, the whole washroom
#   being one 'misc' piece). The sink takes the 'misc' primitives within 150 mm of the basin and the partition strokes
#   there up to 900 mm long (rim, drain, tap).
def _polys(ids):
    ls = lines_of(ids)
    return sorted([p for p in polygonize(unary_union(ls)) if p.area > 0.02], key=lambda p: -p.area) if ls else []
def _bodies(ids):
    """the strokes grown by half their weight (>= 0.08 pt): what reads as one closed shape on paper is closed"""
    ls = lines_of(ids)
    if not ls: return []
    w = sorted(P[i][1] or 0 for i in ids if P[i][0] in ('l', 'c'))
    r = min(0.3, max(0.08, 0.5 * (w[len(w) // 2] if w else 0)))
    G = unary_union(ls).buffer(r); return sorted(getattr(G, 'geoms', [G]), key=lambda g: -g.area)
def _ccls(i):
    p = P[i]; c = p[2] if (p[0] in ('l', 'c') or p[3] is None) else p[3]
    return 'N' if _neutral_c(c) else tuple(round(v, 1) for v in c)
def _by_colour(ids):
    by = collections.defaultdict(list)
    for i in ids: by[_ccls(i)].append(i)
    return [c for v in by.values() if len(by) > 1 and len(v) >= 4 for c in parts_of(v)]
def _small(g): return max(_mrr_sides(g)) * MM_PER_PT <= 90
_mp = [i for n in MISC for i in inst[n]['prims']]; _MG = [geo(i) for i in _mp]; _MPT = STRtree(_MG) if _MG else None
def _ink(ids, grow=1.0):
    """the ink of the strokes as printed: each line grown by half its weight (>= 0.05 pt) times grow"""
    out = []
    for i in ids:
        p = P[i]; q = pts(p)
        if len(q) < 2 or _white_mask(p): continue
        g = LineString(q + ([q[0]] if p[0] == 'qu' else []))
        out.append(g.buffer(max(0.05, 0.5 * (p[1] or 0)) * grow))
    return unary_union(out) if out else None
def _openings(G):
    return [Polygon(r) for g in getattr(G, 'geoms', [G]) for r in g.interiors] if G is not None and not G.is_empty else []
# a drain is round or a polygon of >= 6 sides (4piA/P^2 >= 0.75): a triangle of a concrete hatch is not (floor 1)
_dr = [h for h in _openings(_ink(_mp, 1.0)) if 10 <= max(_mrr_sides(h)) * MM_PER_PT <= 70 and 4 * math.pi * h.area / h.length ** 2 >= 0.75]
# long straight sides of a basin are often taken for light partitions (floor 6): their strokes close the basin too
_fs = [i for q in inst if q['key'] in ('lpart', 'lpartc') for i in q['prims'] if P[i][0] in ('l', 'c')]
_FG = [LineString(pts(P[i])) for i in _fs]; _FST = STRtree(_FG) if _FG else None
_DT = STRtree([h.centroid for h in _dr]) if _dr else None
_sunk = set(); _seen = []
for d in _dr:
    c = d.centroid
    if any(g.contains(c) for g in _seen): continue
    z = c.buffer(500 / MM_PER_PT)
    near = [_mp[j] for j in _MPT.query(z) if _mp[j] not in _sunk] + ([_fs[j] for j in _FST.query(z)] if _FST is not None else [])
    best = None
    for h in _openings(_ink(near, 1.3)):
        L_, S_ = _mrr_sides(h)
        if not (260 <= S_ * MM_PER_PT <= 500 and L_ * MM_PER_PT <= 600 and L_ <= 2.5 * S_ and h.area >= 0.7 * h.convex_hull.area): continue
        hull = h.convex_hull
        if not (hull.contains(c) and h.centroid.buffer(0.35 * L_).contains(c)): continue
        if best is None or h.area < best.area: best = h
    if best is None: continue
    h = best; hull = h.convex_hull; L_, S_ = _mrr_sides(h)
    ds = [_dr[j] for j in _DT.query(hull) if hull.contains(_dr[j].centroid)]
    top = [e for e in ds if not any(f.area > e.area and f.centroid.distance(e.centroid) * MM_PER_PT <= 90 for f in ds)]
    if len(top) > 2: _seen.append(hull); continue          # a grille of dots, not a basin (the gaps of one drain ring count once)
    outer = h.buffer(150 / MM_PER_PT, join_style=2); op = prep(outer)
    inside = [_mp[j] for j in _MPT.query(outer) if op.contains(_MG[j]) and _mp[j] not in _sunk]
    inside += [_fs[j] for j in (_FST.query(outer) if _FST is not None else []) if op.contains(_FG[j]) and _FG[j].length * MM_PER_PT <= 900]
    _seen.append(hull)
    if len(inside) < 3: continue
    _sunk.update(inside); b_ = h.bounds
    _new_obj('sink_src', f'Умывальник или мойка: чаша {round(L_ * MM_PER_PT / 10) * 10}×{round(S_ * MM_PER_PT / 10) * 10} (по исходнику)', 'A-74----E-', inside, 'S')
    cnt['S'] += 1; REP['S'].append(dict(at_pt=[round((b_[0] + b_[2]) / 2, 1), round((b_[1] + b_[3]) / 2, 1)], prims=len(inside),
                                        basin_mm=[round(L_ * MM_PER_PT), round(S_ * MM_PER_PT)]))
MISC = _misc_now()
# ---------------- T. a turned copy of a recognised object (owner 29.09, groups 10-11): a 'misc' piece congruent to the
#   exemplar of a family (chair, stool, WC...) turned by any angle or mirrored; the family matcher finds only the drawing
#   turned by a multiple of 90 degrees. Congruent: the same total line length (+-10 %) and spread (+-8 %), and after the
#   best turn the mean distance both ways <= 6 % of the spread.
from scipy.spatial import cKDTree
def _samples(ids, masks=False):
    segs = []
    for i in ids:
        p = P[i]
        if _white_mask(p) and not masks: continue
        q = pts(p)
        if p[0] == 'qu': q = q + [q[0]]
        segs += list(zip(q, q[1:]))
    L = sum(math.dist(a, b) for a, b in segs)
    if L <= 0: return None
    st = L / 300; out = []
    for a, b in segs:
        k = max(1, int(math.dist(a, b) / st))
        out += [(a[0] + (b[0] - a[0]) * t / k, a[1] + (b[1] - a[1]) * t / k) for t in range(k)]
    X = np.array(out); c = X.mean(0); X = X - c
    return dict(X=X, L=L, rg=float(np.sqrt((X ** 2).sum(1).mean())), c=c)
_TPL = {}
for q in inst:
    if 'tpl' in q and q['key'] not in ('door', 'desk'):
        k_ = (q['key'], tuple(q['tpl']))
        if k_ not in _TPL:
            d_ = _samples(list(q['tpl']))
            if d_: d_['tree'] = cKDTree(d_['X']); d_['meta'] = (q['key'], q['name'], q['layer']); _TPL[k_] = d_
def _rot(X, a, m):
    c, s = math.cos(a), math.sin(a); Y = X * np.array([1, m]); return Y @ np.array([[c, s], [-s, c]])
def congruent(d, t):
    """best turn (deg) and mirror of piece d onto template t, or None"""
    if abs(d['L'] - t['L']) > 0.1 * t['L'] or abs(d['rg'] - t['rg']) > 0.08 * t['rg']: return None
    best = None
    for m in (1, -1):
        for a in range(0, 360, 3):
            e = float(t['tree'].query(_rot(d['X'], math.radians(a), m))[0].mean())
            if best is None or e < best[0]: best = (e, a, m)
    e, a0, m = best
    for a in np.arange(a0 - 3, a0 + 3.01, 0.5):
        e2 = float(t['tree'].query(_rot(d['X'], math.radians(a), m))[0].mean())
        if e2 < e: e, a0 = e2, a
    Y = _rot(d['X'], math.radians(a0), m); back = float(cKDTree(Y).query(t['X'])[0].mean())
    return (a0, m, max(e, back)) if max(e, back) <= 0.06 * t['rg'] else None
if _TPL:
    for n in MISC:
        if n in moved or not (5 <= len(inst[n]['prims']) <= 1500): continue
        d_ = _samples(inst[n]['prims'])
        if d_ is None: continue
        for k_, t in _TPL.items():
            r_ = congruent(d_, t)
            if r_:
                moved[n] = ('T', (t['meta'], round(float(r_[0])) % 360, r_[1])); break
# ---------------- H. a piece of a floor finish hatch (group 20): a small 'misc' piece (<= 350 mm, <= 6 primitives) lying
#   inside a carpet or a floor zone and drawn in that zone's own stroke colours goes to the zone (a triangle of the
#   "concrete" pattern). Furniture standing on a carpet stays its own object (owner 28.09).
#   (owner 30.09: "the triangles are elements of the carpet, its pattern - part of the carpet whose outline they fall
#   in") a carpet comes before a floor zone under it, and a dash of the pattern is up to 400 mm (floor 6: 358 mm dashes
#   stayed 'misc' at 350)
_ZN = sorted([n for n, q in enumerate(inst) if q['key'] in ('carpet', 'zone') and q['prims']], key=lambda n: inst[n]['key'] != 'carpet')
_ZP = {}
for n in _ZN:
    fills = [geo(i) for i in inst[n]['prims'] if P[i][0] == 'qu' and P[i][3] is not None]
    cols = set(tuple(round(v, 2) for v in P[i][2]) for i in inst[n]['prims'] if P[i][2] is not None)
    if fills: _ZP[n] = (prep(unary_union(fills).buffer(0.05)), cols)
for n in MISC:
    if n in moved or len(inst[n]['prims']) > 6: continue
    b_ = sbox(*bb(inst[n]['prims']))
    if max(_mrr_sides(b_)) * MM_PER_PT > 400: continue
    cols = set(tuple(round(v, 2) for v in P[i][2]) for i in inst[n]['prims'] if P[i][2] is not None)
    for z, (zp, zc) in _ZP.items():
        if zp.contains(b_) and cols and (cols <= zc or all(_neutral_c(c) and 0.35 <= c[0] <= 0.8 for c in cols)):
            moved[n] = ('H', z); break
# ---------------- H2. the pattern of a carpet, stroke by stroke (owner 30.09, group 20: "part of the carpet whose outline
#   they fall in"; floor 6: of the triangles and dashes in the 7 carpets rule H took 1 in 10 - the rest were held by the
#   loose bits (one object of 1217 strokes), by 'misc' pieces of the furniture they touch and by partition joints). A line
#   in the carpet's own stroke colour and weight, <= 400 mm, its middle inside the carpet's fill, goes to the carpet: from
#   the loose bits, a 'misc' piece, a partition joint or no one; from any other object only when that object is drawn in
#   other colours (<= 10 % of its lines in the carpet's) - a dash of the pattern an armchair or a plant took along. The
#   furniture standing on the carpet keeps its own strokes (owner 28.09); a 'misc' piece another rule has recognised is
#   left whole. The carpet's own colours: its lines, or - while it is only a fill, as cfg.COLOR_ELEMENTS makes it (its
#   outline comes from rule H at the end) - the mid grey of rule H (neutral, 0.35-0.8), thin (<= 0.3 pt).
_CPT = [n for n in _ZN if inst[n]['key'] == 'carpet' and n in _ZP]
if _CPT:
    OWN = _owners(); FREE = set(free)
    _sty = lambda i: (tuple(round(v, 2) for v in P[i][2]), round(P[i][1] or 0, 2))
    _L2 = [i for i, p in enumerate(P) if p[0] == 'l' and p[2] is not None and math.dist(*p[4]) * MM_PER_PT <= 400]
    _L2M = np.array([((P[i][4][0][0] + P[i][4][1][0]) / 2, (P[i][4][0][1] + P[i][4][1][1]) / 2) for i in _L2]) if _L2 else np.zeros((0, 2))
    _shr = {}
    def _in_zs(i, zs): return _sty(i) in zs if zs else (_neutral_c(P[i][2]) and 0.35 <= P[i][2][0] <= 0.8 and (P[i][1] or 0) <= 0.3)
    def _foreign(o, zs):
        """object o is drawn in other colours than the carpet's lines (<= 10 % of its lines in them)"""
        if (o, zs) not in _shr:
            ls_ = [i for i in inst[o]['prims'] if P[i][0] == 'l' and P[i][2] is not None]
            _shr[(o, zs)] = sum(1 for i in ls_ if _in_zs(i, zs)) <= 0.1 * max(1, len(ls_))
        return _shr[(o, zs)]
    for z in _CPT:
        zs = frozenset(_sty(i) for i in inst[z]['prims'] if P[i][0] == 'l' and P[i][2] is not None)
        fl_ = [geo(i) for i in inst[z]['prims'] if P[i][0] == 'qu' and P[i][3] is not None]
        if not fl_: continue
        fu_ = unary_union(fl_); zf = prep(fu_); b_ = fu_.bounds
        sel = np.nonzero((_L2M[:, 0] >= b_[0]) & (_L2M[:, 0] <= b_[2]) & (_L2M[:, 1] >= b_[1]) & (_L2M[:, 1] <= b_[3]))[0] if len(_L2M) else []
        take_ = []
        for k in sel:
            i = _L2[k]
            if not _in_zs(i, zs) or not zf.contains(Point(_L2M[k])): continue
            o = OWN.get(i)
            if o is None:
                if i in FREE: take_.append(i)
                continue
            if o == z or o in moved or inst[o]['key'] in ('carpet', 'zone'): continue
            if inst[o]['key'] in ('loose', 'misc', 'lpartc') or _foreign(o, zs): take_.append(i)
        if not take_: continue
        s_ = set(take_); by_ = collections.Counter(inst[OWN[i]]['key'] if i in OWN else 'free' for i in take_)
        for o in set(OWN[i] for i in take_ if i in OWN): inst[o]['prims'] = [i for i in inst[o]['prims'] if i not in s_]
        FREE -= s_; inst[z]['prims'] = sorted(set(inst[z]['prims']) | s_)
        for i in take_: OWN[i] = z
        cnt['H2'] += len(take_)
        REP['H2'].append(dict(carpet=z, at_pt=[round((b_[0] + b_[2]) / 2, 1), round((b_[1] + b_[3]) / 2, 1)], strokes=len(take_), taken_from=dict(by_)))
    free = [i for i in free if i in FREE]
    MISC = [n for n in MISC if inst[n]['prims']]
# ---------------- V. a curtain (group 19): an open wavy line - its length >= 1.3 times its span, the span >= 500 mm, the
#   waves <= 80 mm deep
for n in MISC:
    if n in moved: continue
    ls = lines_of(inst[n]['prims'])
    if not ls or len(inst[n]['prims']) < 8: continue
    u = unary_union(ls); L_, S_ = _mrr_sides(u)
    if L_ * MM_PER_PT >= 500 and S_ * MM_PER_PT <= 80 and u.length >= 1.3 * L_ and not _polys(inst[n]['prims']):
        moved[n] = ('V', round(L_ * MM_PER_PT / 10) * 10)
# ---------------- G. a wardrobe seen from above (group 16): >= 5 short 'misc' lines (150-500 mm) crossing one straight
#   line (the rod) at >= 45 degrees, <= 150 mm apart: the hangers; the rod goes along when it is 'misc' or a light partition
_single = [n for n in MISC if n not in moved and len(inst[n]['prims']) == 1 and P[inst[n]['prims'][0]][0] == 'l'
           and 150 <= math.dist(*P[inst[n]['prims'][0]][4]) * MM_PER_PT <= 500]
_rods = collections.defaultdict(list)
for n in _single:
    g = LineString(P[inst[n]['prims'][0]][4])
    for j in (_FLT.query(g) if _FLT is not None else []):
        rg_, ri = _fl[j]
        if ri == inst[n]['prims'][0] or not rg_.crosses(g): continue
        (x1, y1), (x2, y2) = P[ri][4]; (u1, v1), (u2, v2) = P[inst[n]['prims'][0]][4]
        ang = abs(math.degrees(math.atan2(y2 - y1, x2 - x1) - math.atan2(v2 - v1, u2 - u1))) % 180
        if min(ang, 180 - ang) >= 45 and rg_.length * MM_PER_PT >= 300: _rods[ri].append(n)
for ri, ns in _rods.items():
    ns = [n for n in ns if n not in moved]
    if len(ns) < 5: continue
    rod = LineString(P[ri][4]); ts = sorted(rod.project(LineString(P[inst[n]['prims'][0]][4]).intersection(rod)) for n in ns)
    if max(b - a for a, b in zip(ts, ts[1:])) * MM_PER_PT > 150: continue
    for n in ns[1:]: moved[n] = ('G-piece', ns[0])
    own = _owners(); rn = own.get(ri)
    extra = [ri] if rn is not None and inst[rn]['key'] in ('misc', 'lpart', 'lpartc') and rod.length <= 1.5 * (ts[-1] - ts[0]) + 1 else []
    moved[ns[0]] = ('G', len(ns)); inst[ns[0]]['_take'] = [i for n in ns for i in inst[n]['prims']] + extra
# ---------------- X. groups the owner named (cfg.MISC_GROUPS): the 'misc' piece nearest to the example point and every
#   piece congruent to it on this floor get the given name, and the key and layer when given (an unknown group keeps
#   'misc' and layer A-00, named after its catalogue group); with join=True each piece goes to the nearest recognised
#   object within 'reach' pt instead
def _end_chains(ids):
    """the chains of the strokes of ids joined end to end"""
    par = {i: i for i in ids}
    def f_(a):
        while par[a] != a: par[a] = par[par[a]]; a = par[a]
        return a
    em = collections.defaultdict(list)
    for i in ids:
        q_ = pts(P[i])
        for e in (q_[0], q_[-1]): em[_ek(e)].append(i)
    for v in em.values():
        for j in v[1:]: par[f_(j)] = f_(v[0])
    ch = collections.defaultdict(list)
    for i in ids: ch[f_(i)].append(i)
    return sorted(ch.values(), key=min)
def _loose_ends2(ids):
    """the ends of open strokes that no other stroke of ids continues"""
    deg = collections.Counter(); where = {}
    for i in ids:
        if P[i][0] not in ('l', 'c'): continue
        q_ = pts(P[i])
        for e in (q_[0], q_[-1]): k = _ek(e); deg[k] += 1; where[k] = e
    return [where[k] for k, v in deg.items() if v == 1]
# (30.09.2026, floor 5, run 2) two fields of an entry, both off by default: fills=True - the piece may be white fills only
#   (a Revit masking region: _samples skips white masks, so such an example had no samples and the entry was skipped
#   without a word - 7 of the 9 mask entries of floor 5); only=True - the example piece alone, no congruent search (a
#   single straight stroke is congruent to every stroke of its length on the floor). An entry that names nothing is
#   reported (REP['X_miss'], printed): a silent skip is worse than a loud one
_XMISS = []
# (code 007, Т3-3) one entry per example: an entry whose example piece an earlier entry has already named (written again in
#   a later round for the same group) replaced nothing and named nothing - S3, and the first entry won. Now the last entry
#   wins: the earlier entry's pieces are freed and named by the later one; the pair is reported (REP['X_dup'], a cfglint
#   warning, gate list L4) - the cfg keeps one entry per example. An entry is a duplicate only when no free 'misc' piece is
#   centred within its tol: two entries 0.2 pt apart on two pieces of one place stay two entries.
# (code 007, Т3-2) join=True only for a piece that is a detail of the object next to it, not an object itself:
#   <= MISC_JOIN_MAX_MM (1500 mm) on its longer side and <= MISC_JOIN_MAX_PRIMS (200) primitives. A larger example is not
#   joined: X_miss with the reason, S3 stops (test 3 of floor 4: a 1448 x 3116 mm piece of 8 thousand micro-strokes - a
#   meeting table - glued to an armchair). The limit of the proposal, 400 mm and 40 primitives, stopped two entries of
#   floor 4 that are details (the frame round a closed door leaf, 1349 x 571 mm, 104 primitives; the side of a small
#   flight, 899 x 290 mm, 8 primitives): the defaults are the smallest round values that pass every join piece of floors
#   4 and 5 of client A and stop the piece of test 3 <по примерам 4 и 5 этажей клиент А и теста 3>
_JMAX_MM = getattr(cfg, 'MISC_JOIN_MAX_MM', 1500); _JMAX_N = getattr(cfg, 'MISC_JOIN_MAX_PRIMS', 200)
_XDUP, _XHITS = [], []
_GBY, _GHITS = {}, {}                                  # piece -> the entry that named it; entry -> its pieces
def _gctr(n):
    b = bb(inst[n]['prims']); return ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)
def _gsize(n):
    b = bb(inst[n]['prims']); return sorted([(b[2] - b[0]) * MM_PER_PT, (b[3] - b[1]) * MM_PER_PT], reverse=True)
_GDEFS = list(getattr(cfg, 'MISC_GROUPS', []))
for gi, gdef in enumerate(_GDEFS):
    tol_ = gdef.get('tol', 2.0)
    cands = [n for n in MISC if n not in moved]
    near_free = min(cands, key=lambda n: math.dist(_gctr(n), gdef['at'])) if cands else None
    if (near_free is None or math.dist(_gctr(near_free), gdef['at']) > tol_) and _GBY:
        nd = min(_GBY, key=lambda n: math.dist(_gctr(n), gdef['at']))
        gj = _GBY[nd]; prev_ = _GDEFS[gj]
        if math.dist(_gctr(nd), gdef['at']) <= tol_ and not (prev_.get('join') and prev_.get('split')):
            for n in _GHITS.pop(gj, []):
                moved.pop(n, None); _GBY.pop(n, None)
            _XHITS[:] = [h for h in _XHITS if h['entry'] != gj]
            _XDUP.append(dict(at=list(gdef['at']), replaces=list(prev_['at']), entry=gi, replaced_entry=gj,
                              name=gdef.get('name', ''), replaced_name=prev_.get('name', ''),
                              why='cfglint: две записи MISC_GROUPS на один пример — действует последняя; в cfg оставить одну'))
            print(f"cfglint: MISC_GROUPS entry {gi} at {tuple(gdef['at'])} names the example of entry {gj} at {tuple(prev_['at'])} - the last one wins")
            cands = [n for n in MISC if n not in moved]
    if not cands: _XMISS.append(dict(at=list(gdef['at']), why='no misc pieces left')); break
    ex = min(cands, key=lambda n: math.dist(_gctr(n), gdef['at']))
    bx = bb(inst[ex]['prims'])
    if math.dist(((bx[0] + bx[2]) / 2, (bx[1] + bx[3]) / 2), gdef['at']) > tol_:
        _XMISS.append(dict(at=list(gdef['at']), why='no misc piece centred within tol', nearest=[round((bx[0] + bx[2]) / 2, 1), round((bx[1] + bx[3]) / 2, 1)])); continue
    if gdef.get('join'):
        sz_ = _gsize(ex)
        if sz_[0] > _JMAX_MM or len(inst[ex]['prims']) > _JMAX_N:
            _XMISS.append(dict(at=list(gdef['at']), why=f'join=True для куска {sz_[0]:.0f}×{sz_[1]:.0f} мм, {len(inst[ex]["prims"])} примитивов: '
                               f'join — только деталь ≤ {_JMAX_MM} мм и ≤ {_JMAX_N} примитивов (Т3-2); кусок — объект, его называют классом или рамкой MANUAL',
                               size_mm=[round(sz_[0]), round(sz_[1])], prims=len(inst[ex]['prims']))); continue
    _smp = (lambda ids: _samples(ids, masks=True)) if gdef.get('fills') else _samples
    t = _smp(inst[ex]['prims'])
    if t is None: _XMISS.append(dict(at=list(gdef['at']), why='example has no strokes (white fills only: fills=True)')); continue
    t['tree'] = cKDTree(t['X']); hit = [ex]
    for n in ([] if gdef.get('only') else cands):
        if n == ex: continue
        d_ = _smp(inst[n]['prims'])
        if d_ is not None and abs(len(inst[n]['prims']) - len(inst[ex]['prims'])) <= 0.1 * len(inst[ex]['prims']) and congruent(d_, t): hit.append(n)
    _XHITS.append(dict(entry=gi, at=list(gdef['at']), key=gdef.get('key', 'misc'), layer=gdef.get('layer'), name=gdef.get('name', ''),
                       join=bool(gdef.get('join')), n=len(hit), places=[[round(v, 1) for v in _gctr(n)] for n in hit[:40]]))
    if not (gdef.get('join') and gdef.get('split')):
        _GHITS[gi] = list(hit)
        for n in hit: _GBY[n] = gi
    if gdef.get('join'):
        # the group is a part of the object next to it (floor 1: the arms beside the seats at the counter, which stop
        #   short of the seat by 45-100 mm): each piece goes to the nearest recognised object within 'reach' pt.
        #   split=True (30.09, floor 1: between two seats their arms cross in an X, one 'misc' piece): the piece falls
        #   into its chains of strokes joined end to end, and each chain goes to the object nearest to its loose ends
        hs = [m for m, q in enumerate(inst) if q['key'] not in FABRIC and q['prims']]
        hg = [unary_union([geo(i) for i in inst[m]['prims']]) for m in hs]; ht = STRtree(hg)
        rch = gdef.get('reach', 1.0)
        for n in hit:
            if not gdef.get('split'):
                g = unary_union([geo(i) for i in inst[n]['prims']])
                near = sorted((hg[j].distance(g), hs[j]) for j in ht.query(g.buffer(rch)))
                if near and near[0][0] <= rch: moved[n] = ('A', near[0][1])
                continue
            chs_ = _end_chains(inst[n]['prims']); pcs_ = [n]
            for ids_ in chs_[1:]:                       # each chain after the first becomes a piece of its own
                inst[n]['prims'] = [i for i in inst[n]['prims'] if i not in set(ids_)]
                inst.append(dict(key='misc', name=inst[n]['name'], layer=inst[n]['layer'], prims=sorted(ids_))); pcs_.append(len(inst) - 1)
            for m_ in pcs_:
                ids_ = inst[m_]['prims']; g = unary_union([geo(i) for i in ids_])
                es_ = [Point(e) for e in _loose_ends2(ids_)] or [g.centroid]
                near = sorted((sum(hg[j].distance(e) for e in es_) / len(es_), hs[j]) for j in ht.query(g.buffer(rch)))
                if near and near[0][0] <= rch: moved[m_] = ('A', near[0][1])
    else:
        for n in hit: moved[n] = ('X', gdef)
if _XMISS:
    REP['X_miss'] = _XMISS; print('MISC_GROUPS: entries that named nothing', len(_XMISS), _XMISS)
if _XDUP: REP['X_dup'] = _XDUP
if _XHITS: REP['X_hits'] = _XHITS                  # what each entry named: the gate's S11* checks the 'Unknown' entries by it
EARLY = ('T', 'V', 'G', 'G-piece', 'X')        # classified before A: A attaches their loose bits to them
def _claim(n, ids):
    """object n takes the primitives ids from whoever holds them"""
    own = _owners(); s_ = set(ids)
    for m in set(own[i] for i in ids if i in own):
        if m != n: inst[m]['prims'] = [i for i in inst[m]['prims'] if i not in s_]
    inst[n]['prims'] = sorted(s_ | set(inst[n]['prims']))
def _is_arm(ids):
    """(owner 30.09, group 24) an arm of a seat: open lines only, 250-700 mm long, <= 150 mm deep, curved"""
    if any(P[i][0] == 'qu' for i in ids): return False
    ls = lines_of(ids)
    if not ls: return False
    u = unary_union(ls); L_, S_ = _mrr_sides(u)
    deg = collections.Counter(_ek(e) for i in ids for e in (pts(P[i])[0], pts(P[i])[-1]))
    return 250 <= L_ * MM_PER_PT <= 700 and S_ * MM_PER_PT <= 150 and u.length >= 1.03 * L_ and sum(1 for v in deg.values() if v == 1) >= 2
def apply_one(n, rule, arg):
    q = inst[n]
    if not q['prims'] or rule == 'G-piece': return                       # taken by their head (_take)
    b = bb(q['prims']); at = [round((b[0] + b[2]) / 2, 1), round((b[1] + b[3]) / 2, 1)]
    if rule == 'R-piece': q['prims'] = []; return                         # the column (NEW) holds them
    if rule in ('A', 'A2', 'A3', 'H'):
        h = inst[arg]; cnt[rule + ':' + h['key']] += 1; REP[rule].append(dict(misc=n, into=h['key'], at_pt=at))
        if h['key'] == 'furn_src' and _is_arm(q['prims']): h['_arms'] = h.get('_arms', 0) + 1
        h['prims'] = sorted(set(h['prims']) | set(q['prims'])); q['prims'] = []; return
    q['reclass'] = rule
    if rule == 'Z':
        cnt['Z'] += 1; REP['Z'].append(dict(misc=n, at_pt=at))
        q['key'] = 'wallline'; q['name'] = arg.get('name', 'Отделка стены (по исходнику)'); q['layer'] = WL.get(arg.get('cls'), 'A-221---E-'); return
    if rule == 'G':
        _claim(n, q.pop('_take', q['prims']))
        q['key'], q['name'], q['layer'] = 'wardrobe', 'Гардероб: штанга с плечиками (по исходнику)', 'A-76----E-'
        cnt['G'] += 1; REP['G'].append(dict(misc=n, at_pt=at, hangers=arg)); return
    if rule == 'T':
        (k_, nm_, ly_), a_, m_ = arg
        q['key'], q['layer'] = k_, ly_; q['name'] = f'{nm_} (повёрнуто на {a_}°{", зеркально" if m_ < 0 else ""}, по исходнику)'
        cnt['T:' + k_] += 1; REP['T'].append(dict(misc=n, at_pt=at, key=k_, turn=a_, mirror=m_ < 0)); return
    if rule == 'V':                                   # owner 30.09: a curtain hangs in an opening - the layer of the doors
        q['key'], q['name'], q['layer'] = 'curtain', 'Штора в проёме (по исходнику)', 'A-32----E-'
        cnt['V'] += 1; REP['V'].append(dict(misc=n, at_pt=at, span_mm=arg)); return
    if rule == 'M':
        q['key'], q['name'], q['layer'] = 'mask', 'Маскирующая область (белая заливка, по исходнику)', 'A-AXM---E-'
        cnt['M'] += 1; REP['M'].append(dict(misc=n, at_pt=at, fills=arg)); return
    if rule == 'X':
        q['key'] = arg.get('key', 'misc'); q['name'] = arg['name']; q['layer'] = arg.get('layer', 'A-00----E-')
        cnt['X:' + arg['name'][:40]] += 1; REP['X'].append(dict(misc=n, at_pt=at, name=arg['name'])); return
    cnt[rule if rule not in ('W', 'D') else rule + ':' + (arg if rule == 'W' else inst[arg]['key'])] += 1
    REP[rule].append(dict(misc=n, at_pt=at, **({'into': arg if rule == 'W' else inst[arg]['key']} if rule in ('W', 'D') else {'d_mm': arg})))
    if rule == 'B': q['key'], q['name'], q['layer'] = 'column', 'Колонна стальная (двутавр, по исходнику)', 'A-28----E-'
    elif rule == 'col_round': q['key'], q['name'], q['layer'] = 'column', f'Колонна круглая ⌀{arg} (по исходнику)', 'A-28----E-'
    elif rule == 'C':
        q['key'] = 'rtable'; q['layer'] = 'A-82----E-'
        q['name'] = f'Стол круглый ⌀{arg} (по исходнику)' if arg >= 550 else f'Мебель круглая ⌀{arg}: пуф или приставной стол (по исходнику)'
    elif rule == 'W':
        q['key'] = 'wallline'; q['name'] = 'Штриховка или заливка внутри стены — остаток (по исходнику)'; q['layer'] = WL.get(arg, 'A-221---E-')
    elif rule == 'D':
        f_ = inst[arg]; q['key'] = 'lpartc' if f_['key'] == 'lpart' else f_['key']; q['layer'] = f_['layer']
        q['name'] = {'facade': 'Витраж фасада — деталь (стойка, узел фермы, по исходнику)',
                     'glass': 'Перегородка стеклянная — деталь (по исходнику)'}.get(f_['key'], 'Перегородка без штриховки — деталь (торец, стойка, примыкание, по исходнику)')
APPLIED = set()
for n, (rule, arg) in list(moved.items()):
    if rule in EARLY: apply_one(n, rule, arg); APPLIED.add(n)
# K. service marks (after rule X: a cross inside a furniture group is that group's centre mark)
OWN = _owners()
_FURK = ('rtable_set', 'rtable', 'desk', 'desk_src', 'furn_src', 'chair', 'armchair', 'sofa', 'mtable', 'screen', 'benchend', 'fscreen')
_FURB = [sbox(*bb(q['prims'])).buffer(0.3) for q in inst if q['key'] in _FURK and q['prims']]
_FURT = STRtree(_FURB) if _FURB else None
_CHC = [((lambda b: ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2))(bb(q['prims']))) for q in inst if q['key'] in ('chair', 'armchair', 'chair_arm') and q['prims']]
_CHT = cKDTree(np.array(_CHC)) if _CHC else None
def _table_centre(c):
    """the centre of a ring of >= 3 chairs within 1 m, their centroid <= 250 mm from c (a round table's centre mark)"""
    if _CHT is None: return False
    k_ = _CHT.query_ball_point(c, 1000 / MM_PER_PT)
    if len(k_) < 3: return False
    g_ = np.array([_CHC[m] for m in k_]).mean(0); return math.dist(g_, c) * MM_PER_PT <= 250
_LE = np.array([v for p in P if p[0] == 'l' for v in p[4]]) if any(p[0] == 'l' for p in P) else np.zeros((0, 2))
_LET = cKDTree(_LE) if len(_LE) else None
def _round_centre(c):
    """(30.09.2026) the centre of a round outline 500-1500 mm drawn with chords - a round table whose group with its chairs
    stayed 'misc' (floor 6: a '+' where the other tables have an 'x', so the group did not match the example of rule X):
    >= 12 line ends at one radius (+-5 %) around c, all round it (no gap over 60 deg)"""
    if _LET is None: return False
    idx = _LET.query_ball_point(c, 750 / MM_PER_PT)
    if len(idx) < 12: return False
    v_ = _LE[idx] - np.array(c); r_ = np.hypot(v_[:, 0], v_[:, 1]); a_ = np.degrees(np.arctan2(v_[:, 1], v_[:, 0])) % 360
    for R in np.unique(np.round(r_[r_ >= 250 / MM_PER_PT], 1)):
        k_ = np.abs(r_ - R) <= 0.05 * R
        if k_.sum() < 12: continue
        s_ = np.sort(a_[k_]); gaps = np.diff(np.concatenate([s_, [s_[0] + 360]]))
        if gaps.max() <= 60: return True
    return False
_LK = [i for i, p in enumerate(P) if p[0] == 'l' and 95 <= math.dist(*p[4]) * MM_PER_PT <= 230]
_mid = lambda i: ((P[i][4][0][0] + P[i][4][1][0]) / 2, (P[i][4][0][1] + P[i][4][1][1]) / 2)
_ang = lambda i: math.degrees(math.atan2(P[i][4][1][1] - P[i][4][0][1], P[i][4][1][0] - P[i][4][0][0])) % 180
_KT = cKDTree(np.array([_mid(i) for i in _LK])) if _LK else None
_SH = [i for i, p in enumerate(P) if p[0] == 'l' and math.dist(*p[4]) < 1.0]      # ring strokes of a mark
_SHT = cKDTree(np.array([_mid(i) for i in _SH])) if _SH else None
_kdone = set()
for k, i in enumerate(_LK if _KT is not None else []):
    if i in _kdone or not _fab(i): continue
    for m in _KT.query_ball_point(_mid(i), 0.15):
        j = _LK[m]
        if j == i or j in _kdone or not _fab(j): continue
        if abs(abs(((_ang(i) - _ang(j)) + 90) % 180 - 90) - 90) > 3: continue
        li, lj = math.dist(*P[i][4]), math.dist(*P[j][4])
        if max(li, lj) > 1.1 * min(li, lj): continue
        c_ = _mid(i); L_ = max(li, lj)
        if _WUall is not None and _WUall.contains(Point(c_)): continue
        hashed = False                                                         # a '#': a parallel line of the arm's length beside it
        for mm_ in _KT.query_ball_point(c_, 1.5 * L_):
            o = _LK[mm_]
            if o in (i, j): continue
            for a in (i, j):
                if abs(((_ang(o) - _ang(a)) + 90) % 180 - 90) > 3 or not (0.7 * math.dist(*P[a][4]) <= math.dist(*P[o][4]) <= 1.3 * math.dist(*P[a][4])): continue
                la = LineString(P[a][4]); (ax_, ay_), (bx_, by_) = P[a][4]; ux_, uy_ = (bx_ - ax_) / la.length, (by_ - ay_) / la.length
                off_ = abs((_mid(o)[0] - ax_) * uy_ - (_mid(o)[1] - ay_) * ux_)          # beside the arm, not on its line
                if 0.15 <= off_ <= 0.8 and abs(la.project(Point(_mid(o))) - la.length / 2) <= 0.5 * la.length: hashed = True
        if hashed: continue
        # a cross that belongs to a drawing: it lies in a piece of furniture (the centre mark of a round table among its
        #   chairs, floor 6: after rule X) or amid a ring of chairs, or at the centre of a round outline (30.09: a table
        #   whose group stayed 'misc'), or another stroke of its 'misc' piece touches an arm's end
        own_ = [OWN[i], OWN[j]]
        if _FURT is not None and any(_FURB[m3].contains(Point(c_)) for m3 in _FURT.query(Point(c_))): continue
        if _table_centre(c_) or _round_centre(c_): continue
        if any(inst[o_]['key'] == 'misc' for o_ in own_):
            rest_ = [t for o_ in set(own_) if inst[o_]['key'] == 'misc' for t in inst[o_]['prims'] if t not in (i, j)]
            if rest_:
                ends_ = [Point(v) for a in (i, j) for v in P[a][4]]
                _rl = [LineString(_pts2(t)) for t in rest_ if P[t][0] in ('l', 'c') and len(_pts2(t)) > 1 and LineString(_pts2(t)).length >= 0.45]
                if any(g_.distance(e_) <= 0.05 for g_ in _rl for e_ in ends_): continue
        # the ring: tiny strokes of one colour, off the centre (>= 0.1 of the cross), closed around it (no gap over 90 deg), at
        #   most 40 - the strokes of a column or a symbol the cross stands on are not its ring (floor 6)
        ring_ = []
        _rc = collections.defaultdict(list)
        for m2 in _SHT.query_ball_point(c_, 0.6 * L_):
            t = _SH[m2]
            if t not in (i, j) and _fab(t) and all(math.dist(c_, v) <= 0.6 * L_ for v in P[t][4]): _rc[P[t][2]].append(t)
        for col_, ra in _rc.items():
            rs = [t for t in ra if all(math.dist(c_, v) >= 0.1 * L_ for v in P[t][4])]
            angs = sorted(math.degrees(math.atan2(v[1] - c_[1], v[0] - c_[0])) % 360 for t in rs for v in P[t][4])
            gaps = [b - a for a, b in zip(angs, angs[1:])] + [angs[0] + 360 - angs[-1]] if angs else [360]
            if 6 <= len(rs) and len(ra) <= 40 and max(gaps) <= 90: ring_ += ra     # with the strokes inside the ring (a diamond)
        nm_ = 'Служебная метка ⊕ (по исходнику)' if ring_ else 'Служебная метка «+» (по исходнику)'
        _new_obj('mark', nm_, 'A-AXM---E-', [i, j] + ring_, 'K'); _kdone.update([i, j]); OWN = _owners()
        cnt['K'] += 1; REP['K'].append(dict(at_pt=[round(c_[0], 1), round(c_[1], 1)], arm_mm=round(L_ * MM_PER_PT), ring=len(ring_)))
        break
# K2. a cross at a corner (owner 01.10.2026, question 12: "the same service marks as the crosses at the wall corners of
#   floors 1 and 6"; test of floor 5, T19). Two thin (<= 0.3 pt) dark straight strokes 150-550 mm, axis-parallel, at
#   90 +- 3 deg, at least one of them 'misc', whose axis lines cross at a point X that lies within 1.2 pt of both strokes
#   and of an end of one of them (the junction is often hidden in the thick line of the corner): a '+' whose arms do not
#   cross at their middles (rule K), a 'T' or an 'L'. X is a corner of the fabric - within 1.2 pt of an end of a
#   partition, glass or facade line (>= 1.5 pt) or of a wall body vertex. Not two sides of a drawn square (a stroke
#   parallel to one arm passes the far end of the other), not a line of a recognised object (inside its box: rule A
#   takes it), not inside furniture (rule K's test); a 'misc' arm has an end in free space (no other primitive within
#   0.15 pt) - a junction inside a drawing has its strokes tied at both ends. One arm usually lies on a partition: assign gave it to the
#   partition. Floor 5: 10 places, all boxed one by one in the test. A mark on the service layer.
_K2F = set(free)
_K2L = [i for i, p in enumerate(P) if p[0] == 'l' and len(p[4]) == 2 and p[2] is not None and max(p[2]) <= 0.3
        and (p[1] or 0) <= 0.3 and 150 <= math.dist(*p[4]) * MM_PER_PT <= 550 and i not in _kdone
        and (_fab(i) or i in _K2F) and min(_ang(i) % 90, 90 - _ang(i) % 90) <= 3]
# corners: ends of thick (>= 0.45 pt) partition, facade and wall-finish lines and of glass lines (thin, coloured), >= 1.5 pt;
#   thin light-partition lines are left out - a rack's shelves or a cabin's grid meet them in T-junctions (floor 2)
_K2E = [v for q in inst if q['key'] in ('lpart', 'lpartc', 'glass', 'facade', 'wallline') for i in q['prims'] if P[i][0] == 'l' and math.dist(P[i][4][0], P[i][4][-1]) >= 1.5
        and (q['key'] == 'glass' or (P[i][1] or 0) >= 0.45) for v in (P[i][4][0], P[i][4][-1])]
_K2H = [sbox(*bb(q['prims'])).buffer(GROW, join_style=2) for q in inst if q['key'] not in FABRIC and q['prims']]   # recognised objects: rule A's hosts
_K2HT = STRtree(_K2H) if _K2H else None
def _k2_in_host(i):
    b_ = sbox(*bb([i]))
    return _K2HT is not None and any(_K2H[m].contains(b_) for m in _K2HT.query(b_))
def _k2_square(i, j, X):
    """the arms are two sides of a drawn rectangle: a stroke parallel to one arm passes the far end of the other"""
    for a_, b_ in ((i, j), (j, i)):
        far = max(P[b_][4], key=lambda e: math.dist(e, X)); la = math.dist(*P[a_][4])
        for m in _MT.query_ball_point(far, la / 2 + 0.6):
            o = _K2L[m]
            if o in (i, j) or abs(((_ang(o) - _ang(a_)) + 90) % 180 - 90) > 3 or not (0.7 * la <= math.dist(*P[o][4]) <= 1.3 * la): continue
            if _seg_d(far, o) <= 0.3: return True
    return False
for _g in (g for v in _WF.values() for g in v):
    for _q in (getattr(_g, 'geoms', None) or [_g]):
        if _q.geom_type == 'Polygon': _K2E += [c_ for r_ in [_q.exterior] + list(_q.interiors) for c_ in list(r_.coords)[:-1]]
_K2ET = cKDTree(np.array(_K2E)) if _K2E else None
_K2G = [(i, LineString(pts(P[i]) + ([pts(P[i])[0]] if P[i][0] == 'qu' else []))) for i in range(len(P)) if _CLS[i] not in ('sheet', 'axis', 'dim') and len(pts(P[i])) > 1]
_K2GT = STRtree([g for _, g in _K2G]) if _K2G else None
def _k2_loose(e, skip):
    """no other primitive touches the point e (<= 0.15 pt): the arm ends in free space"""
    pe = Point(e)
    return not any(_K2G[m][0] not in skip and _K2G[m][1].distance(pe) <= 0.15 for m in _K2GT.query(pe.buffer(0.15)))
def _seg_d(c, i):
    (ax_, ay_), (bx_, by_) = P[i][4]; L2 = (bx_ - ax_) ** 2 + (by_ - ay_) ** 2
    t_ = max(0.0, min(1.0, ((c[0] - ax_) * (bx_ - ax_) + (c[1] - ay_) * (by_ - ay_)) / L2)) if L2 else 0.0
    return math.dist(c, (ax_ + t_ * (bx_ - ax_), ay_ + t_ * (by_ - ay_)))
if _K2L and _K2ET is not None:
    _ml = {i: _mid(i) for i in _K2L}; _MT = cKDTree(np.array([_ml[i] for i in _K2L]))
    for i in _K2L:
        if i in _kdone or OWN.get(i) is None or inst[OWN[i]]['key'] != 'misc': continue
        (ax_, ay_), (bx_, by_) = P[i][4]; hor_ = abs(by_ - ay_) < abs(bx_ - ax_)
        for m in _MT.query_ball_point(_ml[i], 550 / MM_PER_PT + 0.3):
            j = _K2L[m]
            if j == i or j in _kdone or abs(abs(((_ang(i) - _ang(j)) + 90) % 180 - 90) - 90) > 3: continue
            (cx_, cy_), (dx_, dy_) = P[j][4]
            X = ((cx_ + dx_) / 2, (ay_ + by_) / 2) if hor_ else ((ax_ + bx_) / 2, (cy_ + dy_) / 2)   # crossing of the two axis lines
            # the junction is often hidden in the thick line of the corner: up to 1.2 pt from each arm
            if _seg_d(X, i) > 1.2 or _seg_d(X, j) > 1.2: continue
            if min(math.dist(X, e) for e in P[i][4] + P[j][4]) > 1.2: continue      # at an end of one of them: not a '+' of rule K
            if _k2_square(i, j, X): continue                                       # two sides of a drawn square, not a cross
            if _k2_in_host(i): continue                                            # a line of a recognised object (rule A takes it)
            # a 'misc' arm ends in free space at least at one end - a junction inside a drawing (furniture, a cabin, a stair, a
            #   grid of thin lines) has its strokes tied to other lines at both ends (floor 1: 88 such places before this test)
            if not all(any(_k2_loose(e, (i, j)) for e in P[t][4]) for t in (i, j) if OWN.get(t) is not None and inst[OWN[t]]['key'] == 'misc'): continue
            if not _K2ET.query_ball_point(X, 1.2): continue                         # at a corner of the fabric
            if _FURT is not None and any(_FURB[m3].contains(Point(X)) for m3 in _FURT.query(Point(X))): continue
            _new_obj('mark', 'Служебная метка: крест в углу (по исходнику)', 'A-AXM---E-', [i, j], 'K2'); _kdone.update([i, j]); OWN = _owners()
            cnt['K2'] += 1; REP['K2'].append(dict(at_pt=[round(X[0], 1), round(X[1], 1)], arms_mm=[round(math.dist(*P[i][4]) * MM_PER_PT), round(math.dist(*P[j][4]) * MM_PER_PT)]))
            break
MISC = _misc_now()
# ---------------- M. a Revit masking region (owner 30.09.2026 for floor 5, test T15 / p. 159: masks are not objects of the
#   plan): a 'misc' piece left by the early rules that is white fills only - no stroke, fill >= 0.97 (along the axes,
#   under furniture and the plant zones; floor 5: 11 such pieces were named one by one). Its boundary is not drawn:
#   under 20 % of it lies on dark strokes (max <= 0.5; the light lines of zones and axes cross masks) - the white fill
#   of a drawn shape is not a mask (floor 6: sofa cushions, panels, 27-100 %; floor 5 masks: 0-15 %). The service layer
def _whiteish(p):
    c_ = [c for c in (p[2], p[3]) if c is not None]
    return bool(c_) and all(min(c) >= 0.94 for c in c_)
for n in MISC:
    if n in moved: continue
    q = inst[n]
    if not q['prims']: continue
    wh_ = [i for i in q['prims'] if _whiteish(P[i])]; rest_ = [i for i in q['prims'] if i not in set(wh_)]
    # white fills and strokes only; or >= 2 white fills with at most 3 dark ticks <= 1 pt (white strips with short black
    #   ticks along the desks, floor 5)
    ticks_ = len(rest_) <= 3 and all(P[i][0] == 'l' and len(P[i][4]) == 2 and math.dist(*P[i][4]) <= 1.0 for i in rest_) and sum(1 for i in wh_ if P[i][0] == 'qu') >= 2
    if not (wh_ and (not rest_ or ticks_)): continue
    # a masking region is drawn as an axis-parallel rectangle: a strip along an axis, a patch under furniture. A rounded
    #   or turned white shape is the fill of a drawing (the cushions of a turned sofa, floor 6)
    def _rect_ok(i):
        g_ = Polygon(pts(P[i])).buffer(0)
        if g_.is_empty or g_.area <= 0: return False
        b_ = g_.bounds; return g_.area / max(1e-9, (b_[2] - b_[0]) * (b_[3] - b_[1])) >= 0.97
    if not all(_rect_ok(i) for i in wh_ if P[i][0] == 'qu'): continue
    # (01.10.2026, code 005) a masking region is >= cfg.MASK_MIN_MM (100 mm) across: the white strips 23-38 mm wide in
    #   the backs of the armchairs of floor 1 (69 of them) are the chairs' own fills - the masks of floor 5 are 145-1227 mm
    _wb = unary_union([Polygon(pts(P[i])).buffer(0) for i in wh_ if P[i][0] == 'qu']).bounds if any(P[i][0] == 'qu' for i in wh_) else None
    if _wb is None or min(_wb[2] - _wb[0], _wb[3] - _wb[1]) * MM_PER_PT < getattr(cfg, 'MASK_MIN_MM', 100): continue
    # a masking region has no outline: the white fill of a drawn shape (a sofa's cushions, a cabinet's panel - floor 6)
    #   has its boundary on that shape's lines. Mask - when < 30 % of the boundary of its white fills lies on strokes
    fl_ = [i for i in wh_ if P[i][0] == 'qu']
    bd_ = unary_union([LineString(pts(P[i]) + [pts(P[i])[0]]) for i in fl_]) if fl_ else None
    if bd_ is not None and bd_.length > 0:
        nb_ = [g for m_, (i_, g) in ((m_, _K2G[m_]) for m_ in _K2GT.query(bd_.buffer(0.12)))
               if P[i_][0] in ('l', 'c') and i_ not in set(q['prims']) and P[i_][2] is not None and max(P[i_][2]) <= 0.5]
        cov_ = bd_.intersection(unary_union(nb_).buffer(0.12)).length / bd_.length if nb_ else 0.0
        if cov_ >= 0.2: continue
    moved[n] = ('M', len(q['prims']))
# (01.10.2026, code 005) M runs before A: A attached a mask lying in the box of a cabinet to the cabinet (floor 5, the
#   white strip at (593.5, 439.1) went into 'Шкафчики / стеллаж' - in run 2 an entry of cfg had named it)
# ---------------- A. pieces of recognised objects
hosts = [n for n, q in enumerate(inst) if q['key'] not in FABRIC and q['prims']]
HB = [sbox(*bb(inst[n]['prims'])).buffer(GROW, join_style=2) for n in hosts]; HT = STRtree(HB)
_hg = {}
def host_geom(n):
    if n not in _hg: _hg[n] = unary_union([geo(i) for i in inst[n]['prims']])
    return _hg[n]
for n in MISC:
    if n in moved: continue
    q = inst[n]; b = sbox(*bb(q['prims'])); ba = max(b.area, 1e-6); g = unary_union([geo(i) for i in q['prims']])
    best = None
    for j in HT.query(b):
        hb = HB[j]; sh = hb.intersection(b).area / ba if b.area > 0 else (1.0 if hb.contains(b) else 0.0)
        if sh < 0.8: continue
        h = hosts[j]
        if host_geom(h).distance(g) > 0.1: continue
        if best is None or sh > best[0]: best = (sh, h)
    if best: moved[n] = ('A', best[1])
# ---------------- A2. an appendage of an object: a 'misc' piece of open lines whose loose ends (>= 2) all touch one
#   object (<= 0.1 pt), lying within that object's bbox grown by half its size (floor 1: the curved arms of the seats
#   at the counter, group 24)
def loose_ends(ids):
    deg = collections.Counter(); where = {}
    for i in ids:
        p = P[i]
        if p[0] not in ('l', 'c'): continue
        q_ = pts(p)
        for e in (q_[0], q_[-1]): k = _ek(e); deg[k] += 1; where[k] = e
    return [where[k] for k, v in deg.items() if v == 1]
def _grow(b, f): w, h = b[2] - b[0], b[3] - b[1]; return (b[0] - f * w, b[1] - f * h, b[2] + f * w, b[3] + f * h)
HB2 = [sbox(*_grow(bb(inst[n]['prims']), 0.5)) for n in hosts]; HT2 = STRtree(HB2) if HB2 else None
for n in MISC:
    if n in moved or HT2 is None: continue
    q = inst[n]
    if not q['prims'] or len(q['prims']) > 60: continue
    e = loose_ends(q['prims'])
    if len(e) < 2: continue
    b = sbox(*bb(q['prims']))
    for j in HT2.query(b):
        if not HB2[j].contains(b): continue
        h = hosts[j]
        if all(host_geom(h).distance(Point(x)) <= 0.1 for x in e): moved[n] = ('A2', h); break
# ---------------- A3. a detail beside an object (29.09.2026, check 3.9a): a 'misc' piece touching exactly one recognised
#   object (<= 0.1 pt), not lying along a light partition, glass or facade, no longer than the object, within the object's bbox
#   grown by its own size, in the object's own colours and line weights - the cistern of a WC whose template holds only
#   the bowl, the back and arms of an office chair (floors 1, 6). Not to a plant: its leaves touch the partitions and
#   zone edges around it. A red label touching a column (floor 1, "ЭЩ"), a grey marker touching a desk and a thick
#   partition stroke touching a plant stay apart.
_fab = [LineString(pts(P[i])) for q in inst if q['key'] in ('lpart', 'lpartc', 'glass', 'facade') for i in q['prims'] if len(pts(P[i])) > 1]
_FABT = STRtree(_fab) if _fab else None
HB3 = [sbox(*_grow(bb(inst[n]['prims']), 1.0)) for n in hosts]; HT3 = STRtree(HB3) if HB3 else None
def _cols(ids): return set(tuple(round(v, 1) for v in (P[i][2] if P[i][2] is not None else P[i][3])) for i in ids if (P[i][2] if P[i][2] is not None else P[i][3]) is not None)
for n in MISC:
    if n in moved or HT3 is None: continue
    q = inst[n]
    if not q['prims'] or len(q['prims']) > 200: continue
    g = unary_union([geo(i) for i in q['prims']]); b = sbox(*bb(q['prims'])); Lp = max(_mrr_sides(g))
    # a piece lying along a partition, glass or the facade is their detail (rule D), not the object's: <= 30 % of its
    #   lines within 0.3 pt of them (a WC cistern or a seat touches a partition at a point, a facade strip runs along it)
    if _FABT is not None:
        ls_ = lines_of(q['prims']); u_ = unary_union(ls_) if ls_ else None
        near_ = [_fab[j] for j in _FABT.query(g.buffer(0.3))]
        if u_ is not None and near_ and u_.length > 0 and u_.intersection(unary_union(near_).buffer(0.3)).length > 0.3 * u_.length: continue
    touch = [hosts[j] for j in HT3.query(b) if HB3[j].contains(b) and host_geom(hosts[j]).distance(g) <= 0.1]
    if len(set(touch)) != 1: continue
    h = touch[0]; hg = host_geom(h)
    if inst[h]['key'] == 'plant' or Lp > max(_mrr_sides(hg)) + 1e-6: continue       # a plant's leaves touch everything around
    pc = _cols(q['prims']); hc = _cols(inst[h]['prims'])
    if not pc <= hc: continue                             # the object's own colours only: a grey diamond is not a desk's
    if max((P[i][1] or 0) for i in q['prims']) > max((P[i][1] or 0) for i in inst[h]['prims']) + 0.05: continue   # a partition stroke
    moved[n] = ('A3', h)
# ---------------- shapes: B (I), then W (inside walls), then C (round)
def mrr_axes(poly):
    r = poly.minimum_rotated_rectangle; c = list(r.exterior.coords)[:4]
    return c[0], (c[1][0] - c[0][0], c[1][1] - c[0][1]), (c[2][0] - c[1][0], c[2][1] - c[1][1])
def is_I(poly):
    """two flanges joined by a web through their middle: the section profile across the web is full near both ends,
    narrow in the middle, and the middle cut lies at the middle of the flange"""
    o, e1, e2 = mrr_axes(poly)
    L1, L2 = math.hypot(*e1), math.hypot(*e2)
    if min(L1, L2) * MM_PER_PT < 150 or max(L1, L2) * MM_PER_PT > 750 or max(L1, L2) > 1.9 * min(L1, L2): return False
    for u, v, Lu in ((e1, e2, L1), (e2, e1, L2)):   # u: along the flanges, v: along the web
        def cut(t):
            p0 = (o[0] + v[0] * t, o[1] + v[1] * t); ln = LineString([p0, (p0[0] + u[0], p0[1] + u[1])])
            return ln.intersection(poly), ln
        # flanges can be thin (floor 6: 8 mm flanges on a 351 mm section) - 60 cuts; a turned flange is cut a little
        #   askew (floor 6), hence 0.6
        prof = [cut((k + 0.5) / 60)[0].length / Lu for k in range(60)]
        if not (min(max(prof[:9]), max(prof[-9:])) >= 0.6 and max(prof[21:39]) <= 0.35): continue
        s, ln = cut(0.5)             # a U / П casing has its bar at one end (floor 2, the column boxes of the facade)
        if not s.is_empty and abs(ln.project(s.centroid) / Lu - 0.5) <= 0.2: return True
    return False
for n in MISC:
    if n in moved: continue
    q = inst[n]; ls = lines_of(q['prims'])
    if not ls: continue
    u = unary_union(ls)
    polys = sorted([p for p in polygonize(u) if p.area > 0.5], key=lambda p: -p.area)
    hull = None
    if polys:
        outer = unary_union(polys); outer = max(getattr(outer, 'geoms', [outer]), key=lambda p: p.area); hull = Polygon(outer.exterior)
    # B. the I outline must carry most of the object: a panel with a post, a partition junction or a door frame can
    #   have an I-shaped hull too (floors 4-6)
    if hull is not None and is_I(hull) and u.intersection(hull.exterior.buffer(0.08)).length >= 0.6 * u.length:
        moved[n] = ('B', None); continue
    # W. all inside the wall bodies (floor 1: the hatch strokes of a turned capital wall; before B the I-beams of the
    #   facade band, which lie in its wall bodies, were taken for wall remnants)
    if _WUall is not None and _WUall.contains(u):
        moved[n] = ('W', max(_WC, key=lambda k: 1 if _WC[k].contains(u) else 0)); continue
    if hull is None: continue
    ci, D = circ_of(hull)
    if ci >= 0.9 and 350 <= D <= 1300:
        bx = bb(q['prims'])
        if max(bx[2] - bx[0], bx[3] - bx[1]) * MM_PER_PT > D * 1.08: continue
        c = hull.centroid; R_ = D / 2 / MM_PER_PT
        # a second circle inside, all of whose lines lie between 0.45 R and 0.9 R (floor 1: two of the 440 mm casings
        #   were left whole in 'misc'), or a circle on a grid node: a column
        inner_ring = sum(g.length for g in ls if g.distance(c) >= 0.45 * R_ and g.hausdorff_distance(c) <= 0.9 * R_)
        if on_node((c.x, c.y)) or inner_ring >= 0.15 * u.length: moved[n] = ('col_round', round(D / 10) * 10); continue
        # a round table has little inside it (a centre mark); an armchair turned in a round outline has its seat and
        #   arms drawn inside (floor 6)
        if u.difference(hull.exterior.buffer(0.1)).length > 0.35 * u.length: continue
        moved[n] = ('C', round(D / 10) * 10)
# ---------------- D. details of partitions and glazing
fl = []; fk = []
for n, q in enumerate(inst):
    if q['key'] in ('lpart', 'lpartc', 'glass', 'facade'):
        for i in q['prims']:
            if P[i][0] in ('l', 'c'): fl.append(LineString(pts(P[i]))); fk.append(n)
FT = STRtree(fl) if fl else None
def _neutral(i):
    c = P[i][2] if P[i][2] is not None else P[i][3]
    return c is None or (abs(c[0] - c[1]) < 0.03 and abs(c[1] - c[2]) < 0.03)
for n in MISC:
    if n in moved or FT is None: continue
    q = inst[n]
    if len(q['prims']) > 40: continue
    bx = bb(q['prims'])
    if max(bx[2] - bx[0], bx[3] - bx[1]) * MM_PER_PT > 600: continue
    if not all(_neutral(i) for i in q['prims']): continue          # a coloured sign or mark is not a partition's detail
    ls = lines_of(q['prims'])
    if not ls: continue
    u = unary_union(ls); L = u.length
    if L <= 0: continue
    near = list(FT.query(u.buffer(0.8)))
    touch = collections.Counter(fk[j] for j in near if fl[j].distance(u) <= 0.06)
    if not touch: continue
    if u.intersection(unary_union([fl[j] for j in near]).buffer(0.8)).length / L < 0.7: continue
    moved[n] = ('D', touch.most_common(1)[0][0])
# ---------------- names of the colour elements follow cfg (an export-only run picks up a renamed element)
# (01.10.2026, code 005) several entries may share a key (floor 5: the hot and the cold water points, both 'water'):
#   a dict by key kept the last entry's name and renamed the first entry's element to it. assign names each element
#   after its own entry; here a name is taken from cfg only when the key has a single entry
_CEN = collections.defaultdict(list)
for c in getattr(cfg, 'COLOR_ELEMENTS', []): _CEN[c['key']].append((c['name'], c['layer']))
_ren = 0
# (cfg.COLOR_OWN_ONLY, 30.09.2026, floor 5) only the colour elements themselves: a key shared with other objects ('glass',
#   'sofa', 'rack' on floor 5; 'door45' of a MANUAL door and a blue glass door on floor 4) renamed every object of that
#   key to the colour element's name. Default on since 01.10.2026 (test of floor 5, T6): floor 4 delivered the MANUAL
#   door at (817.5, 181) under the name of the blue glass door; COLOR_OWN_ONLY = False brings the old naming back
_COWN = getattr(cfg, 'COLOR_OWN_ONLY', True)
for q in inst:
    if q['key'] in _CEN and len(_CEN[q['key']]) == 1 and (not _COWN or q.get('colour')) and (q['name'], q['layer']) != _CEN[q['key']][0]:
        _ren += 1
        if not DRY: q['name'], q['layer'] = _CEN[q['key']][0]
if _ren: cnt['renamed from cfg'] = _ren
# ---------------- apply
for n, (rule, arg) in list(moved.items()):
    if n not in APPLIED: apply_one(n, rule, arg)
# ---------------- chairs (owner 30.09, group 24: "these are the arms of the chairs at the reception; the armchairs next
#   to them are bigger, these are chairs by their size"): a furniture body of rule F <= 0.3 m2 that took an arm (an open
#   curve 250-700 mm, rules A and A2) is a chair with arms
for q in inst:
    if q['key'] == 'furn_src' and q.get('_arms'):
        fl_ = [geo(i) for i in q['prims'] if P[i][0] == 'qu' and P[i][3] is not None and not _white_mask(P[i])]
        a_ = unary_union(fl_).area * MM_PER_PT ** 2 / 1e6 if fl_ else 0.0
        if 0 < a_ <= 0.3:
            q['key'], q['name'] = 'chair_arm', 'Стул с подлокотниками (по исходнику)'; cnt['F:chair_arm'] += 1
    q.pop('_arms', None)
# the frame of such a chair (floor 1, all 17 at the counters: the black outline was taken for a light partition and the
#   grey bands along its back and front for partition joints): the lines and the neutral fills of the light partitions,
#   their joints, 'misc' and the loose bits lying within the chair's body grown by 45 mm (a band is 38 mm) are the
#   chair's
_CHA = [n for n, q in enumerate(inst) if q['key'] == 'chair_arm' and q['prims']]
if _CHA:
    OWN = _owners(); FREE = set(free)
    _PB = np.array([bb([i]) for i in range(len(P))])
    for n in _CHA:
        body = [i for i in inst[n]['prims'] if P[i][0] == 'qu' and P[i][3] is not None and not _white_mask(P[i])]
        if not body: continue
        g_ = 45 / MM_PER_PT; b_ = _PB[body]; x0_, y0_, x1_, y1_ = b_[:, 0].min() - g_, b_[:, 1].min() - g_, b_[:, 2].max() + g_, b_[:, 3].max() + g_
        sel = np.nonzero((_PB[:, 0] >= x0_) & (_PB[:, 1] >= y0_) & (_PB[:, 2] <= x1_) & (_PB[:, 3] <= y1_))[0]
        take_ = [int(i) for i in sel if (int(i) in OWN and inst[OWN[int(i)]]['key'] in ('lpart', 'lpartc', 'misc', 'loose') or int(i) in FREE)
                 and (P[i][0] == 'l' or (P[i][0] == 'qu' and P[i][3] is not None and _neutral_c(P[i][3]) and not _white_mask(P[i])))]
        if not take_: continue
        s_ = set(take_)
        for o in set(OWN[i] for i in take_ if i in OWN): inst[o]['prims'] = [i for i in inst[o]['prims'] if i not in s_]
        FREE -= s_; inst[n]['prims'] = sorted(set(inst[n]['prims']) | s_)
        cnt['chair frame'] += len(take_)
    free = [i for i in free if i in FREE]
# ---------------- (code 008, Т4-3, Г1-1) an I-beam of rule B takes the lines of its web: the web is drawn as two long
#   lines between the flanges (floor 4: eight thin I-beams, 0.72 pt web, 6.6 pt long) and step 12 made them light
#   partitions - the column lost its web and the partition ran through the column. Lines of a light partition that lie
#   inside the section's box (+0.3 pt) and run along its long side go to the column. cfg.DETECT8 (detect8.py)
import detect8 as _d8
if _d8.on('columns') and not DRY:
    _LPI = [k for k, q in enumerate(inst) if q['key'] in ('lpart', 'lpartc') and q['prims']]
    _nweb = 0
    for n, (rule, arg) in moved.items():
        if rule != 'B' or inst[n]['key'] != 'column' or not inst[n]['prims']: continue
        bx = bb(inst[n]['prims']); w_, h_ = bx[2] - bx[0], bx[3] - bx[1]
        for k in _LPI:
            web = [i for i in inst[k]['prims'] if P[i][0] == 'l' and bx[0] - 0.3 <= min(P[i][4][0][0], P[i][4][1][0]) and max(P[i][4][0][0], P[i][4][1][0]) <= bx[2] + 0.3
                   and bx[1] - 0.3 <= min(P[i][4][0][1], P[i][4][1][1]) and max(P[i][4][0][1], P[i][4][1][1]) <= bx[3] + 0.3]
            if not web: continue
            s_ = set(web); inst[k]['prims'] = [i for i in inst[k]['prims'] if i not in s_]
            inst[n]['prims'] = sorted(set(inst[n]['prims']) | s_); _nweb += len(s_)
    cnt['B web lines'] += _nweb
    print('detect8: web lines of rule-B I-beams taken from the light partitions', _nweb)
# ---------------- the layer table (owner 30.09: "choose the codes yourselves; ask when unsure"). Objects that assign or
#   the operator's boxes (cfg MANUAL) put on a layer the table no longer has get the new one, so an export-only run
#   gives the same file as a full one: carpets 83 -> 43 (43 is floor finishes, 83 culinary equipment), switchboards
#   63 -> 61 (61 is electric supply, 63 lighting); the turnstiles go with walls and glazing (owner: "the turnstile zone,
#   its equipment - on the layer where you draw walls and glazing"), the curtains with the doors ("a curtain goes to the
#   layer of the doors, where the doors are")
LAYER_MOVE = {'A-83----E-': 'A-43----E-', 'A-63----E-': 'A-61----E-'}
KEY_LAYER = {'gate': 'A-22G---E-', 'curtain': 'A-32----E-'}
for q in inst:
    lay_ = KEY_LAYER.get(q['key'], LAYER_MOVE.get(q['layer'], q['layer']))
    if lay_ != q['layer']: cnt['layer ' + q['layer'][:5] + ' -> ' + lay_[:5]] += 1; q['layer'] = lay_
if not DRY:
    for d in NEW:                                   # rule R: the circles leave the curved-partition chains
        s_ = set(d['prims'])
        for n in d.pop('_from'): inst[n]['prims'] = [i for i in inst[n]['prims'] if i not in s_]
        inst.append(d)
    inst = [q for q in inst if q['prims'] or q['key'] != 'misc']
    pickle.dump((inst, free), open('assign2.pkl', 'wb'))
left = [q for q in inst if q['key'] == 'misc' and q['prims']]
json.dump(dict(dry=DRY, misc_objects_before=_objs0, misc_parts=PARTS0, split_added=SPLIT, misc_prims_before=MISC_PRIMS0,
               moved=dict(cnt), misc_left=len(left), misc_prims_left=sum(len(q['prims']) for q in left),
               places={k: v[:400] for k, v in REP.items()}), open('reclass_dry.json' if DRY else 'reclass.json', 'w'),
          ensure_ascii=False, indent=0)
print('misc objects', _objs0, '-> parts', PARTS0, '| reclassified', len(moved), dict(cnt), '| left', len(left),
      'objects,', sum(len(q['prims']) for q in left), 'of', MISC_PRIMS0, 'primitives')
