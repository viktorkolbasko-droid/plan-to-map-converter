"""Э7о (test 10, owner 07.10.2026): the opening of every door fits its wall. «На слое с дверями ты не везде попадаешь в
проем. Нужно, во-первых, проверить, что толщина проема совпадает с толщиной стены. Не везде они одинаковы. И перепроверить,
посравнивать разные двери с проемами, однотипные на однотипных стенах… классифицировать по группам».
After Э7я (the core blocks are known), for every door rebuilt by Э7д (its opening — a closed rectangle, 'opening'):
 1. the axis — the opening runs along the line of the door's hinges (the arcs' centres; the pieces of one swing share a
    centre): through the two hinges of a double door, from the hinge to the closed end of the swing of a single one. Off by
    more than 5° — listed for review (Э6г joins the pieces of one swing since test 10, so its frame no longer runs along a
    radius of the swing).
 2. the depth, at each end of the opening:
    (a) the section of the element beside the end — wall bodies, glass panes, core blocks cut by lines across the opening
        at 7–58 mm beyond the end (door_slices.section): two consecutive cuts agree (≤ 10 mm), the section is not cut
        short by the line's own end (an element running across the axis: a perpendicular wall's side, a core block's mass)
        and is ≥ 19 mm thick;
    (b) else the jamb of the source — the strokes across the wall at the end (door_slices.jamb: the walls' and the core's
        layers, the door's frame pieces), ≥ 14 mm.
    The two ends: faces within 14 mm — their mean; else the candidate (either end, their common part) that best matches the
    door's frame pieces (IoU of the ranges across), without frame pieces — the common part when it holds at least half of
    the thinner; one end — that end; none — the frame pieces (14–192 mm), else as Э7д drew it.
 3. the ends along the axis: an opening Э7д laid from hinge to hinge (a door Э6г found no opening for) is carried to the
    outer edge of the door's frame pieces at each end (the frame is part of the opening); a short side short of the element
    beyond it (5–72 mm, at the middle of the depth) is moved onto it; a wall body running through the fitted opening (over
    at least half its width) is cut there (walls_o.pkl).
 4. service doors (owner 07.10.2026: «это двери, но служебные в служебные помещения, доступ к шахте лифта, которая не
    используется на этом этаже, либо в какое-то другое служебное помещение»; moved here from Э7я, after the fit): a door
    the source draws without its swing (a leaf only) whose opening lies on the face of a core block (a long side within
    24 mm of the block's outline along ≥ 60 % of it, or the opening inside the block by ≥ 60 % of its area) — into a shaft,
    a lift shaft not used on the floor, a technical room.
Code 012 (stage 1 of the merge of v009 into ocg/; the code of pass v009, route/e7o_openings.py) — the step of the layer
route after Э7я (ocg/run_ocg.sh):
 - the sheet from cfg (ocg/sheet.py): the walls' layers — role 'wall' of cfg.OCG_LAYERS, glass — the fills of
   cfg.OCG_GLASS_COLORS on them, the scale — cfg.MM_PER_PT (sheet.K); every threshold in mm through it (v009 set them in pt
   at 48.04 mm/pt <one example: client-b, floor 40>; the mm here are those pt × 48.04 exactly - step 8: rounded to 0.1 mm
   they moved openings by up to 0.03 mm, and Э7р carried that into the rooms of Э9з); no layer of the walls
   or no scale — a stop with the reason;
 - reads prims_c.pkl (the output of Э7я; a rerun of the step does not read its own prims_o.pkl), objects.pkl, the walls of
   Э7с (walls_j.pkl: walls_o.pkl of an earlier run is removed first);
 - an end of the opening that Э7д drew on to the face of a wall or glass (reach_faces of code 011, «доведён до грани»;
   objects.pkl 'ends_on_face': the end and how far it was drawn on) stays there: the opening runs to the face of the wall
   (owner's decision №105; №112 — the double doors 1400 of client-b, 1644 and 1605 mm), step 3 does not move it — neither
   to the frame's edge nor onto an element farther at the middle of the depth; its depth (step 2) is measured where the end
   stood before reach_faces — at the door's frame, as v009 measured it: the face the end now touches may be the side of a wall
   across the axis, no jamb (the double door 1400 at a corner of walls took a 565 mm «jamb» from it); the wall cut (3b) and
   the service doors (4) as for any door.
Writes prims_o.pkl, objects.pkl, openings.json and, when a wall body ran through a fitted opening, walls_o.pkl (the bodies
cut there). usage: python3 e7o_openings.py   (floor folder, after e7c_core.py)"""
import pickle, json, math, collections, sys, time, os
import numpy as np, shapely
from shapely.geometry import LineString, Polygon, Point
from shapely.ops import unary_union
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import sheet
from e7_comp import geom, load_walls
from door_slices import Carriers, section, Strokes, jamb, JAMB_EX_ROLES
t0 = time.time(); K = sheet.K
def T(): return f'{time.time() - t0:.1f} s'
WALL_L = sheet.L('wall')
if not K: sys.exit('СТОП Э7о: нет масштаба листа cfg.MM_PER_PT — пороги шага в мм не перевести в pt (plan/rules/20 §3.8)')
if not WALL_L: sys.exit('СТОП Э7о: в таблице слоёв cfg.OCG_LAYERS нет слоёв роли wall — проёмы дверей не с чем сверить (ocg/sheet.py ROLES)')
if not os.path.exists('prims_c.pkl'): sys.exit('СТОП Э7о: нет prims_c.pkl — сначала Э7я (e7c_core.py)')
def mm(v): return v / K                                    # a threshold in mm -> pt of the sheet as read
# thresholds in mm (v009 in pt at 48.04 mm/pt): an arc's radius from ARC_R_MM, the hinges of one swing within HINGE_MM, two
# hinges (a hinge and the swing's closed end) at least AXIS_MIN_MM apart; the
# frame pieces' range across the wall MARKS_MM; a section ≥ SEC_MIN_MM, a jamb ≥ JAMB_MIN_MM; faces of two ends one within
# FACE_MM; a depth within DEPTH_MM; a frame piece up to FRAME_MM beyond an end, beyond it by more than STUB_MM; an element
# reaching INSIDE_MM into the opening (looked for EDGE_MM–FACE_MM inside); a gap GAP_MM to the element beyond a short side;
# the wall cut: a band CUT_IN_MM in from the ends, CUT_ON_MM / FACE_MM beyond the sides, pieces from CUT_AREA_MM2, bodies
# kept from KEEP_AREA_MM2; the face of a core block within BLOCK_MM
ARC_R_MM, HINGE_MM, AXIS_MIN_MM = 144.12, 48.04, 144.12                                                    # 3; 1; 3 pt
MARKS_MM, SEC_MIN_MM, JAMB_MIN_MM, FACE_MM = (14.412, 192.16), 19.216, 14.412, 14.412                       # 0.3-4; 0.4; 0.3; 0.3 pt
DEPTH_MM, FRAME_MM, STUB_MM, INSIDE_MM, EDGE_MM, GAP_MM = (14.412, 576.48), 72.06, 4.804, 9.608, 2.402, (4.804, 72.06)    # 0.3-12; 1.5; 0.1; 0.2; 0.05; 0.1-1.5 pt
CUT_IN_MM, CUT_ON_MM, CUT_AREA_MM2, KEEP_AREA_MM2, BLOCK_MM = 2.402, 0.9608, 23.078416, 115.39208, 24.02    # 0.05; 0.02 pt; 0.01, 0.05 pt²; 0.5 pt
D0 = pickle.load(open('prims_c.pkl', 'rb')); P = D0['P']
O = pickle.load(open('objects.pkl', 'rb')); objs = O['objs']
if os.path.exists('walls_o.pkl'): os.remove('walls_o.pkl')          # a rerun starts from the bodies of Э7с, not from its own cut
W = load_walls(skip=('walls_r.pkl', 'walls_o.pkl'))['bodies']        # check of step 11: nor from the bodies of Э7р of an earlier run
GLASS = sheet.GLASS
items = [('стена ' + c, g) for c, g in W]
items += [('стекло', g) for g in (geom(p) for p in P if p['kind'] in ('fill', 'wline') and p.get('col') in GLASS and p['layer'] in WALL_L) if g.geom_type == 'Polygon' and g.area > 0]
blocks = []
for o in objs:
    if o['key'] == 'coreblock' and o.get('outline'):
        g = unary_union([geom(P[i]) for i in o['outline'] if P[i]['kind'] == 'fill'])
        if not g.is_empty: blocks.append(g); items.append(('блок ядра', g))
C = Carriers(items); S = Strokes(P, geom, sheet.L(*JAMB_EX_ROLES))
rep = collections.Counter(); rows = []
def circ(pts):
    A = np.column_stack([pts[:, 0], pts[:, 1], np.ones(len(pts))]); b = -(pts ** 2).sum(1)
    try: a, b2, c = np.linalg.lstsq(A, b, rcond=None)[0]
    except Exception: return None
    cx, cy = -a / 2, -b2 / 2; r = math.sqrt(max(cx * cx + cy * cy - c, 0)); res = np.abs(np.hypot(pts[:, 0] - cx, pts[:, 1] - cy) - r).max()
    return (cx, cy, r, res)
def frame_of(ring):
    cs = np.array(ring, float)[:4]; e1, e2 = cs[1] - cs[0], cs[2] - cs[1]
    if np.linalg.norm(e2) > np.linalg.norm(e1): cs = np.roll(cs, -1, axis=0); e1, e2 = cs[1] - cs[0], cs[2] - cs[1]
    Wd, Th = float(np.linalg.norm(e1)), float(np.linalg.norm(e2)); u = e1 / Wd; n = e2 / max(Th, 1e-9)
    return cs[0], u, n, Wd, Th
def hinge_axis(o):
    """the line of the door's hinges: (u, how) or None"""
    arcs = []
    for i in o['draw']:
        if P[i].get('opening'): continue
        pts = np.array(P[i]['p'], float)
        if len(pts) >= 8 and not np.allclose(pts[0], pts[-1]):
            cf = circ(pts)
            if cf and cf[2] > mm(ARC_R_MM) and cf[3] <= 0.08 * cf[2]: arcs.append((i, cf, pts))
    if not arcs: return None
    hs = []                                                # hinges: pieces of one swing share a centre (<= HINGE_MM)
    for i, cf, pts in arcs:
        for h in hs:
            if math.hypot(h['c'][0] - cf[0], h['c'][1] - cf[1]) <= mm(HINGE_MM): h['pts'].append(pts); h['ids'].append(i); break
        else: hs.append(dict(c=np.array(cf[:2]), r=cf[2], pts=[pts], ids=[i]))
    if len(hs) >= 2:
        a_, b_ = max(((x, y) for x in range(len(hs)) for y in range(x + 1, len(hs))), key=lambda xy: np.linalg.norm(hs[xy[0]]['c'] - hs[xy[1]]['c']))
        v = hs[b_]['c'] - hs[a_]['c']
        if np.linalg.norm(v) < mm(AXIS_MIN_MM): return None
        return v / np.linalg.norm(v), 'через две петли'
    h = hs[0]; c = h['c']
    # the swing's two extreme ends (over all its pieces, by angle round the hinge); the closed end is the one away from
    # the open leaf's tip — the end nearest to the door's other pieces is the tip
    ang = []
    for pts in h['pts']:
        for q in pts: ang.append((math.atan2(q[1] - c[1], q[0] - c[0]), q))
    ref = ang[0][0]
    def un(a): return (a - ref + math.pi) % (2 * math.pi) - math.pi
    lo = min(ang, key=lambda x: un(x[0]))[1]; hi = max(ang, key=lambda x: un(x[0]))[1]
    others = [geom(P[j]) for j in o['draw'] if j not in h['ids'] and not P[j].get('opening') and len(P[j]['p']) >= 2]
    def near_leaf(e): return min([g.distance(Point(e)) for g in others] or [9e9])
    tip = min((lo, hi), key=near_leaf); cl = hi if tip is lo else lo
    v = np.asarray(cl, float) - c
    if np.linalg.norm(v) < mm(AXIS_MIN_MM): return None
    return v / np.linalg.norm(v), 'петля → закрытое полотно'
def marks_range(o, o_, n):
    ts = [float((np.array(q, float) - o_) @ n) for i in o.get('marks', []) for q in P[i]['p']]
    return (min(ts), max(ts)) if ts and mm(MARKS_MM[0]) <= max(ts) - min(ts) <= mm(MARKS_MM[1]) else None
def iou(a, b):
    ov = min(a[1], b[1]) - max(a[0], b[0]); un_ = max(a[1], b[1]) - min(a[0], b[0])
    return max(ov, 0.0) / un_ if un_ > 0 else 0.0
def first_hit(o_, u, n, a_from, a_to, t):
    """the distance along u from a_from to the first element on the line t (towards a_to), or None"""
    a, b = tuple(o_ + u * a_from + n * t), tuple(o_ + u * a_to + n * t)
    pcs = C.cut(a, b)
    if not pcs: return None
    return min(x0 for x0, x1, c in pcs) * abs(a_to - a_from)
nkept = 0
for k, o in enumerate(objs):
    if o['key'] != 'door' or not o.get('draw'): continue
    op = [i for i in o['draw'] if P[i].get('opening') and len(P[i]['p']) >= 4]
    if not op: continue
    oi = op[0]; ring0 = [tuple(q) for q in P[oi]['p']]
    o_, u, n, Wd, Th = frame_of(ring0)
    r = dict(obj=k, name=o.get('name', ''), at=[round(float(v), 1) for v in (o_ + u * Wd / 2 + n * Th / 2)], width0_mm=round(Wd * K), thick0_mm=round(Th * K))
    # code 012: the ends Э7д drew on to a face (reach_faces, code 011) - their side of the frame of this ring and how far they
    #   were drawn on: such an end stays (step 3), its depth is measured where it stood before - at the door's frame (step 2)
    fixed = {}
    for q in o.get('ends_on_face', []):
        a_q = float((np.asarray(q['at'], float) - o_) @ u)
        if min(abs(a_q), abs(a_q - Wd)) <= mm(FACE_MM): fixed[0 if abs(a_q) <= abs(a_q - Wd) else 1] = float(q['back'])
    # 1. the axis
    ha = hinge_axis(o)
    if ha is not None:
        v, how = ha; ang = math.degrees(math.acos(min(1.0, abs(float(v @ u)))))
        r['axis_off_deg'] = round(ang, 1)
        if ang > 5.0: r['axis'] = f'ось проёма не по петлям ({how}): {round(ang, 1)}° — на перепроверку'; rep['проём: ось не по петлям — на перепроверку'] += 1
    # 2. the depth
    ends = []
    for side, (a_end, sgn) in enumerate(((0.0, -1), (Wd, 1))):
        # code 012: an end Э7д drew on to the face of an element (011) has no jamb of its own there - the face of a wall across
        #   the axis is not one (client-b, the double door 1400 at a corner of walls: a 565 mm «jamb»); the section and the
        #   jamb are taken where the end stood before reach_faces, at the door's frame, as v009 took them
        a_m = a_end - sgn * fixed[side] if side in fixed else a_end
        s = section(C, o_, u, n, a_m, sgn, 0.0, Th, K)
        j = jamb(S, o_, u, n, a_m, 0.0, Th, K, marks=o.get('marks', []))
        if s and s['stable'] and not s['clipped'] and s['hi'] - s['lo'] >= mm(SEC_MIN_MM): ends.append(('стена', s['lo'], s['hi'], s['cls']))
        elif j and j['hi'] - j['lo'] >= mm(JAMB_MIN_MM): ends.append(('откос исходника', j['lo'], j['hi'], j['cls']))
        else: ends.append(None)
    got = [e for e in ends if e]; mr = marks_range(o, o_, n)
    if len(got) == 2:
        (s1, lo1, hi1, c1), (s2, lo2, hi2, c2) = got
        sw = [e for e in got if e[0] == 'стена']
        if abs(lo1 - lo2) <= mm(FACE_MM) and abs(hi1 - hi2) <= mm(FACE_MM): lo, hi = (lo1 + lo2) / 2, (hi1 + hi2) / 2; how = f'{s1} / {s2}: среднее граней'
        # a wall at one end, only the source's jamb (or the frame) at the other: the opening is the wall's when the door's
        # frame pieces fit in it (the door stands in that wall; the other end is open or a jamb of a different element)
        elif len(sw) == 1 and (mr is None or (mr[0] >= sw[0][1] - mm(FACE_MM) and mr[1] <= sw[0][2] + mm(FACE_MM))):
            _, lo, hi, _ = sw[0]; how = f'стена у конца {1 if got[0][0] == "стена" else 2} (у другого — откос)'
        else:
            cands = [((lo1, hi1), f'{s1} у конца 1'), ((lo2, hi2), f'{s2} у конца 2')]
            com = (max(lo1, lo2), min(hi1, hi2))
            if com[1] - com[0] >= mm(FACE_MM): cands.append((com, 'общая часть концов'))
            if mr:
                (lo, hi), how = max(cands, key=lambda c_: iou(c_[0], mr)); how += ' (по коробке двери)'
            elif com[1] - com[0] >= 0.5 * min(hi1 - lo1, hi2 - lo2): (lo, hi), how = com, 'общая часть концов'
            else: (lo, hi), how = max(cands[:2], key=lambda c_: c_[0][1] - c_[0][0]), 'конец со стеной толще'
    elif len(got) == 1: _, lo, hi, _ = got[0]; how = f'{got[0][0]} у одного конца'
    elif mr: lo, hi = mr; how = 'коробка двери'
    else: lo, hi = 0.0, Th; how = 'как у Э7д'
    if not (mm(DEPTH_MM[0]) <= hi - lo <= mm(DEPTH_MM[1])): lo, hi = 0.0, Th; how = 'как у Э7д (толщина вне 15–575 мм)'
    r['depth_by'] = how; r['ends'] = [None if e is None else dict(by=e[0], lo_mm=round(e[1] * K), hi_mm=round(e[2] * K), cls=e[3]) for e in ends]
    rep['проём: глубина — ' + how.split(':')[0].split(' (')[0]] += 1
    # 3. the ends along the axis: onto the element beyond a short side (a gap GAP_MM)
    c0, c1 = 0.0, Wd; tm = (lo + hi) / 2; moved = []
    # the door's frame pieces are part of its opening: a short side inside the frame (an opening laid from hinge to hinge,
    # Э7д's frame of a door Э6г found no opening for) is carried to the frame's outer edge (≤ FRAME_MM beyond the end)
    by_marks = set()
    if (o.get('door_struct') or {}).get('frame') == 'по самой двери':
        mu = [float((np.array(q, float) - o_) @ u) for i in o.get('marks', []) for q in P[i]['p']]
        lo_m = [a for a in mu if -mm(FRAME_MM) <= a < 0.0]; hi_m = [a for a in mu if Wd < a <= Wd + mm(FRAME_MM)]
        if 0 not in fixed and lo_m and min(lo_m) < -mm(STUB_MM): moved.append(round(-min(lo_m) * K)); c0 = min(lo_m); by_marks.add(0)
        if 1 not in fixed and hi_m and max(hi_m) > Wd + mm(STUB_MM): moved.append(round((max(hi_m) - Wd) * K)); c1 = max(hi_m); by_marks.add(1)
    for side in (0, 1):
        if side in fixed: continue                                # code 012: Э7д drew this end on to the face of a wall (011)
        if side in by_marks: continue                             # the frame's edge is the end: the stub beyond it is wall
        a_end = c0 if side == 0 else c1; sg = -1 if side == 0 else 1
        inside = first_hit(o_, u, n, a_end - sg * mm(EDGE_MM), a_end - sg * mm(FACE_MM), tm)
        if inside is not None and inside < mm(INSIDE_MM): continue    # the element reaches into the opening — left as it is
        d_ = first_hit(o_, u, n, a_end + sg * 0.0, a_end + sg * mm(GAP_MM[1]), tm)
        if d_ is not None and mm(GAP_MM[0]) <= d_ <= mm(GAP_MM[1]):
            if side == 0: c0 -= d_
            else: c1 += d_
            moved.append(round(d_ * K))
    if fixed: r['ends_kept_e7d'] = sorted(fixed); r['ends_measured_back_mm'] = {str(k_): round(v_ * K) for k_, v_ in sorted(fixed.items())}; nkept += 1
    if moved: rep['проём: торец доведён до стены'] += 1; r['ends_moved_mm'] = moved
    ring = [tuple(map(float, o_ + u * a + n * b)) for a, b in ((c0, lo), (c1, lo), (c1, hi), (c0, hi), (c0, lo))]
    P[oi] = dict(P[oi]); P[oi]['p'] = ring
    r.update(width_mm=round((c1 - c0) * K), thick_mm=round((hi - lo) * K), d_thick_mm=round((hi - lo - Th) * K),
             shift_mm=round(((lo + hi) / 2 - Th / 2) * K), changed=bool(abs(lo) * K > 3 or abs(hi - Th) * K > 3 or moved))
    if r['changed']: rep['проём: изменён'] += 1
    rows.append(r)
if nkept: rep['проём: конец у грани по Э7д (код 011) — оставлен'] = nkept
print('openings fitted:', dict(rep), T())
# 3b. a wall body that runs through a fitted opening (along it over at least half its width) is cut there — the door is a
# gap in the wall (owner row 172); Э6г cut the bodies by its own frame, the fitted opening may be deeper (a lining, a core
# wall) or shifted. Slivers along an opening's side (less than half its width) are left and listed by the check.
_wf = next(f_ for f_ in ('walls_j.pkl', 'walls_e7.pkl', 'walls_geom.pkl', 'walls_clean.pkl', 'walls.pkl') if os.path.exists(f_))
WR = pickle.load(open(_wf, 'rb')); WB = [list(cg) for cg in WR['bodies']]; WBT = shapely.STRtree([g for _, g in WB]); ncut = 0; cut_area = 0.0
for r in rows:
    o = objs[r['obj']]; op = [i for i in o['draw'] if P[i].get('opening')]
    o_, u, n, Wd, Th = frame_of(P[op[0]]['p'])
    def w(a, b): return tuple(o_ + u * a + n * b)
    Rc = Polygon([w(mm(CUT_IN_MM), 0.0), w(Wd - mm(CUT_IN_MM), 0.0), w(Wd - mm(CUT_IN_MM), Th), w(mm(CUT_IN_MM), Th)])
    Rx = Polygon([w(mm(CUT_ON_MM), -mm(FACE_MM)), w(Wd - mm(CUT_ON_MM), -mm(FACE_MM)), w(Wd - mm(CUT_ON_MM), Th + mm(FACE_MM)), w(mm(CUT_ON_MM), Th + mm(FACE_MM))])
    for j in WBT.query(Rc):
        g = WB[j][1]; x = g.intersection(Rc)
        if x.is_empty or x.area < CUT_AREA_MM2 / (K * K): continue
        us = [float((np.array(q) - o_) @ u) for q_ in getattr(x, 'geoms', [x]) if q_.geom_type == 'Polygon' for q in q_.exterior.coords]
        if not us or max(us) - min(us) < 0.5 * Wd: continue
        cut_area += g.intersection(Rx).area; WB[j][1] = g.difference(Rx); ncut += 1; r['wall_cut'] = True
if ncut:
    WR2 = dict(WR); WR2['bodies'] = [(c, q) for c, g in WB for q in getattr(g, 'geoms', [g]) if q.geom_type == 'Polygon' and q.area > KEEP_AREA_MM2 / (K * K)]
    pickle.dump(WR2, open('walls_o.pkl', 'wb'))
rep['проём: стена шла через проём — разрезана'] = ncut
print('wall bodies running through a fitted opening, cut:', ncut, f'({round(cut_area * K * K / 1e6, 3)} m²)', T())
# 4. service doors
nsrv = 0; srv_at = []
if blocks:
    BBz = unary_union([b.boundary for b in blocks]).buffer(mm(BLOCK_MM)); BU = unary_union(blocks)
    for k, o in enumerate(objs):
        if o['key'] != 'door' or not o.get('door_struct') or o['door_struct'].get('arcs', 1) != 0 or not o['door_struct'].get('leaves'): continue
        op = [i for i in o.get('draw', []) if P[i].get('opening') and len(P[i]['p']) >= 4]
        if not op: continue
        cs = np.array(P[op[0]]['p'], float)[:4]; Rg = Polygon(cs)
        sides = [LineString([tuple(cs[q]), tuple(cs[(q + 1) % 4])]) for q in range(4)]; Lmax = max(sd.length for sd in sides)
        on_face = any(sd.length >= 0.8 * Lmax and sd.intersection(BBz).length >= 0.6 * sd.length for sd in sides)
        inside = Rg.area > 0 and Rg.intersection(BU).area >= 0.6 * Rg.area
        if not (on_face or inside): continue
        o['service'] = True
        if 'служебная' not in o['name']:
            o['name'] = o['name'].replace('Дверь ', 'Дверь служебная ', 1).replace(' (полотно без дуги, по исходнику)', ' — в блок ядра: шахта, техпомещение (полотно без дуги, по исходнику)')
        nsrv += 1; c_ = cs.mean(0); srv_at.append(dict(obj=k, at=[round(float(c_[0]), 1), round(float(c_[1]), 1)], by='грань блока' if on_face else 'в блоке'))
print('service doors (a leaf only, on the face of a core block):', nsrv, T())
json.dump(dict(counts=dict(rep), service_doors=nsrv, service_doors_at=srv_at, doors=rows), open('openings.json', 'w'), ensure_ascii=False, indent=1)
D1 = dict(D0); D1['P'] = P; pickle.dump(D1, open('prims_o.pkl', 'wb')); pickle.dump(O, open('objects.pkl', 'wb'))
print('written prims_o.pkl, objects.pkl, openings.json', T())
