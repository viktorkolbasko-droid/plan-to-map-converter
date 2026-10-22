"""Э7д (owner 06.10.2026): every door in one structure — the opening, the open leaf, the swing arc.
«Дверь состоит из проема. Это прямоугольник с такой же шириной и толщиной, как стена, и стыкующаяся слева и справа со
стеной. Это открытая дверь, и это дуга, по которой дверь открывается… петли дверей… распознавать, но вектор не включать…
как какие-то служебные метки».
For every door frame of Э6г (geom_report.json: o, u, n; c0..c1 along the wall, t_lo..t_hi across it):
 1. the opening — the rectangle c0..c1 x t_lo..t_hi: its long sides on the faces of the walls on both sides (as they are
    after Э7с, measured at the wall ends), its short sides on the wall ends; a closed outline of 4 points, layer «Двери»;
 2. the swing arc(s) — the door's curves (>= 8 points, on a circle), as drawn; a swing door drawn without its arc (the
    leaf at 15–165° to the opening, hinged at its end) gets the arc from the closed position to the leaf;
 3. the leaf (leaves) — the door's thin long pieces (as long as the arc's radius, at most a quarter as wide), as drawn;
 4. the jamb details (hinges, frame pieces — small pieces at the opening's ends) are recognised and kept as the door's
    service marks ('marks'), not drawn; the contour lines of Э6г give way to the opening.
A door without a frame (not processed by Э6г: across a passage, in a wall drawn as lines) gets one from its own arcs
(test 9, frame_from_door); one without arcs is listed for review. Test 10: two doors in one object (their pieces touch) are
shared out between the frames Э6г found for them; a rebuilt door is named by its own swings (one hinge — single, two —
double), one drawn without a swing — by its opening («полотно без дуги, по исходнику»). The opening's depth is fitted to the
wall later, after the core (Э7о, e7o_openings.py). Reads prims_j.pkl, objects.pkl, walls (load_walls),
geom_report.json; writes prims_d.pkl, objects.pkl, doors.json. usage: python3 e7d_doors.py (after e7j_joints.py)
Code 011 (package 5): an end of an opening off the face of a wall or glass is drawn on to it over the door's frame (reach_faces).
Code 012 (stage 1 of the merge of v009): the name of a door drawn without a swing is by its opening as Э6г or the door
itself framed it (before reach_faces: the frame's faces, not the door's width class, decide how far an end is drawn on)."""
import pickle, json, math, collections, sys, time
import numpy as np, shapely
from shapely.geometry import LineString, Polygon, Point, MultiPolygon
from shapely.ops import unary_union
import os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import sheet; from e7_comp import geom, load_walls
t0 = time.time(); K = sheet.K
def T(): return f'{time.time() - t0:.1f} s'
D0 = pickle.load(open('prims_j.pkl', 'rb')); P = D0['P']
O = pickle.load(open('objects.pkl', 'rb')); objs = O['objs']; owner = O['owner']
W = load_walls()['bodies']; BG = [g for _, g in W]; bt = shapely.STRtree(BG)
GLASS = sheet.GLASS; WALL_L = sheet.L('wall'); DOOR_LAYER = sheet.L1('door')
PG = [geom(p) for p in P if p['kind'] in ('fill', 'wline') and p.get('col') in GLASS and p['layer'] in WALL_L]
PG = [g for g in PG if g.geom_type == 'Polygon' and g.area > 0]; ELEM = BG + PG; et = shapely.STRtree(ELEM)
R = json.load(open('geom_report.json'))['places'].get('doors', [])
# code 011 (ПК4-П13, Т9-11; owner's decision of 07.10.2026, №105: the opening runs from the face of one wall to the face of
#   the other; owner 06.10.2026: «стыкующаяся слева и справа со стеной»): an end of an opening that is not on the face of a
#   wall body or glass (nothing within END_TOL of its side) is drawn on along the opening's axis to the first face the rays
#   from the end meet (3 of 5 rays at 10-90 % of the opening's depth), when the face is within END_MAX and the source draws
#   strokes across the gap - the door's frame (коробка) or the wall layers' lines, inside the opening's band (+0.6 pt), along
#   >= half of the gap: the frame stands there, the gap is not a passage. Thresholds in pt at 48.04 mm/pt: END_TOL 0.3 pt
#   (14 mm, the touch of J1), END_MAX 3 pt (144 mm, the range of a break between bodies, Т9-6) <one example: client-b,
#   floor 40 - the double door 1400 of К-2 (its second end, 107 mm) and the double door 1400 at a corner of walls (79 and
#   27 mm)>. An end left off a face is listed in doors.json and stops the gate (O10, ocg/checks_ocg.py).
END_TOL, END_MAX = 0.3, 3.0
# code 012 (merge of v009, test 10): the thresholds of the test-10 pieces below in mm through the scale of the sheet (K = sheet.K
#   mm/pt; v009 set them in pt at 48.04 mm/pt <one example: client-b, floor 40>): the hinges of one swing share a centre
#   (HINGE_MM, v009 1 pt); a door object near a frame of Э6г (SPLIT_NEAR_MM, v009 1.5 pt); a curve is an arc from ARC_R_MM (v009 3 pt)
HINGE_MM, SPLIT_NEAR_MM, ARC_R_MM = 48.04, 72.06, 144.12          # pt of v009 × 48.04 exactly (step 8: no rounding to 0.1 mm)
_EVL = sheet.L('wall', 'core', 'door')
_evg = [geom(p) for p in P if p['kind'] in ('line', 'fill', 'wline') and p['layer'] in _EVL and not p.get('synthetic') and len(p['p']) >= 2]
_evt = shapely.STRtree(_evg)
def reach_faces(o_, u, n, c0, c1, tl, th):
    """(c0, c1, info): the ends of the opening c0..c1 x tl..th drawn on to the faces of walls or glass where the rule allows"""
    def w(a, b): return o_ + u * a + n * b
    out = [c0, c1]; info = []
    for idx, (a_end, sgn) in enumerate(((c0, -1), (c1, 1))):
        side = LineString([tuple(w(a_end, tl)), tuple(w(a_end, th))])
        near = [ELEM[j].distance(side) for j in et.query(side.buffer(END_TOL + 0.01))]
        if near and min(near) <= END_TOL: info.append(dict(end=idx, what='на грани')); continue
        hits = []
        for t in np.linspace(0.1, 0.9, 5):
            p0 = w(a_end, tl + (th - tl) * t); ray = LineString([tuple(p0), tuple(p0 + u * sgn * END_MAX)])
            ds = [Point(tuple(p0)).distance(ELEM[j].intersection(ray)) for j in et.query(ray) if ELEM[j].intersects(ray)]
            if ds: hits.append(min(ds))
        if len(hits) < 3: info.append(dict(end=idx, what=f'грани нет в {END_MAX} pt')); continue
        g = float(min(hits))
        zone = Polygon([tuple(w(a_end, tl - 0.6)), tuple(w(a_end + sgn * g, tl - 0.6)), tuple(w(a_end + sgn * g, th + 0.6)), tuple(w(a_end, th + 0.6))])
        iv = []
        for q in _evt.query(zone):
            x = _evg[q].intersection(zone)
            if x.is_empty: continue
            cs = [c for pc in getattr(x, 'geoms', [x]) for c in (pc.exterior.coords if pc.geom_type == 'Polygon' else pc.coords)]
            if not cs: continue
            al = [float((np.array(c) - o_) @ u) for c in cs]; iv.append((min(al), max(al)))
        iv.sort(); cov = 0.0; cur = None
        for a, b in iv:
            if cur is None or a > cur[1]: cov += (cur[1] - cur[0]) if cur else 0.0; cur = [a, b]
            else: cur[1] = max(cur[1], b)
        cov += (cur[1] - cur[0]) if cur else 0.0
        if cov < 0.5 * g: info.append(dict(end=idx, what='щель без штрихов — не доведён', gap_mm=round(g * K))); continue
        out[idx] = a_end + sgn * g; info.append(dict(end=idx, what='доведён до грани', gap_mm=round(g * K)))
    return out[0], out[1], info
def live(i): return P[i]['kind'] != 'removed'
def circ(pts):
    A = np.column_stack([pts[:, 0], pts[:, 1], np.ones(len(pts))]); b = -(pts ** 2).sum(1)
    try: a, b2, c = np.linalg.lstsq(A, b, rcond=None)[0]
    except Exception: return None
    cx, cy = -a / 2, -b2 / 2; r = math.sqrt(max(cx * cx + cy * cy - c, 0)); res = np.abs(np.hypot(pts[:, 0] - cx, pts[:, 1] - cy) - r).max()
    return (cx, cy, r, res)
def mrr_dims(g):
    r = g.minimum_rotated_rectangle
    if r.geom_type != 'Polygon': return (g.length, 0.0)
    c = np.array(r.exterior.coords)[:4]; a, b = np.linalg.norm(c[1] - c[0]), np.linalg.norm(c[2] - c[1]); return (max(a, b), min(a, b))
rep = collections.Counter(); rows = []; done = set()
DOORS = [k for k, o in enumerate(objs) if o['key'] == 'door' and o['ids']]
dg = {k: unary_union([geom(P[i]) for i in objs[k]['ids'] if live(i)]) for k in DOORS}
DOORS = [k for k in DOORS if not dg[k].is_empty]; dtree = shapely.STRtree([dg[k] for k in DOORS])
def rebuild(f, ks, kind, depth_own=False):
    o_, u, n = np.array(f[0]), np.array(f[1]), np.array(f[2]); c0, c1, tl, th = f[3], f[4], f[5], f[6]
    def w(a, b): return tuple(o_ + u * a + n * b)
    Rg = Polygon([w(c0, tl), w(c1, tl), w(c1, th), w(c0, th)])
    # the wall faces at the opening's ends: the elements beside it, measured within 1.5 pt of each end
    tt = []
    for a_end, sgn in ((c0, -1), (c1, 1)):
        probe = Polygon([w(a_end + sgn * 0.05, tl - 0.6), w(a_end + sgn * 1.5, tl - 0.6), w(a_end + sgn * 1.5, th + 0.6), w(a_end + sgn * 0.05, th + 0.6)])
        for j in et.query(probe):
            x = ELEM[j].intersection(probe)
            if x.is_empty or x.area < 0.01: continue
            bb = [((np.array(q) - o_) @ n) for q in (x.exterior.coords if x.geom_type == 'Polygon' else [c for g_ in x.geoms if g_.geom_type == 'Polygon' for c in g_.exterior.coords])]
            if bb: tt.append((min(bb), max(bb)))
    if tt: tl2 = float(np.median([a for a, b in tt])); th2 = float(np.median([b for a, b in tt]))
    else: tl2, th2 = tl, th
    if not (0.3 <= th2 - tl2 <= 2 * (th - tl) + 1.0): tl2, th2 = tl, th
    if depth_own: tl2, th2 = tl, th          # code 010 (К-2, №105): a door between the faces of two walls - the depth of its frame
    cf0, cf1 = c0, c1                                              # code 012: the ends before reach_faces (Э7о measures the depth there)
    c0, c1, ends_info = reach_faces(o_, u, n, c0, c1, tl2, th2)     # code 011: both ends on the faces of walls or glass
    ring = [w(c0, tl2), w(c1, tl2), w(c1, th2), w(c0, th2), w(c0, tl2)]
    main = max(ks, key=lambda k: len(objs[k]['ids'])); ids = [i for k in ks for i in objs[k]['ids'] if live(i)]
    arcs, leaves, marks, contour, other = [], [], [], [], []
    for i in ids:
        p = P[i]; g = geom(p); pts = np.array(p['p'], float)
        if p.get('synthetic') or p.get('removed_by') == 'door_contour' or p.get('layer0'): contour.append(i); continue
        if len(pts) >= 8:
            cf = circ(pts)
            if cf and cf[2] > 3 and cf[3] <= 0.08 * cf[2]: arcs.append((i, cf)); continue
        L_, W_ = mrr_dims(g)
        if L_ <= max(2.2, (th2 - tl2) + 0.8) and g.distance(Rg) <= 1.0: marks.append(i); continue
        other.append((i, L_, W_))
    rads = [cf[2] for _, cf in arcs]
    for i, L_, W_ in list(other):                                               # a leaf as long as the radius of one of the arcs
        if rads and any(0.7 * r_ <= L_ <= 1.3 * r_ for r_ in rads) and W_ <= 0.25 * L_: leaves.append(i); other.remove((i, L_, W_))
        elif not rads and 0.35 * (c1 - c0) <= L_ <= 1.2 * (c1 - c0) and W_ <= 0.25 * L_: leaves.append(i); other.remove((i, L_, W_))
    seq = P[ids[0]]['seq']
    # a swing door drawn without its arc: the leaf stands at 15–165° to the opening at one of its ends — the arc is added
    # (centre on the hinge, radius = the leaf, from the closed position across the opening to the open leaf)
    added_arcs = []
    if not arcs:
        for i in leaves:
            g = geom(P[i]); r_ = g.minimum_rotated_rectangle
            if r_.geom_type != 'Polygon': continue
            cc = np.array(r_.exterior.coords)[:4]; e1, e2 = cc[1] - cc[0], cc[2] - cc[1]
            ax_ = e1 if np.linalg.norm(e1) >= np.linalg.norm(e2) else e2; Lh = np.linalg.norm(ax_) / 2; ax_ = ax_ / np.linalg.norm(ax_); cen = cc.mean(0)
            ends = [cen - ax_ * Lh, cen + ax_ * Lh]; hinge = min(ends, key=lambda q: Rg.distance(Point(q))); tip = ends[1] if hinge is ends[0] else ends[0]
            a_h = (hinge - o_) @ u; closed = u if abs(a_h - c0) <= abs(a_h - c1) else -u
            op = (tip - hinge) / max(np.linalg.norm(tip - hinge), 1e-9); ang = math.degrees(math.acos(max(-1, min(1, abs(float(op @ u))))))
            if not (15 <= ang <= 165) or Rg.distance(Point(hinge)) > 1.0: continue
            th0 = math.atan2(closed[1], closed[0]); th1 = math.atan2(op[1], op[0]); dth = (th1 - th0 + math.pi) % (2 * math.pi) - math.pi
            rr = 2 * Lh; pts = [tuple(hinge + rr * np.array([math.cos(th0 + dth * t), math.sin(th0 + dth * t)])) for t in np.linspace(0, 1, 25)]
            aid = len(P); P.append(dict(id=aid, layer=DOOR_LAYER, kind='line', col=(0.0, 0.0, 0.0), p=pts, w=0, seq=seq, alpha=1.0, synthetic=True, swing=True))
            added_arcs.append(aid); rep['двери: дуга добавлена (в исходнике не было)'] += 1
    nid = len(P); P.append(dict(id=nid, layer=DOOR_LAYER, kind='line', col=(0.0, 0.0, 0.0), p=ring, w=0, seq=seq, alpha=1.0, synthetic=True, opening=True))
    for k in ks:
        o = objs[k]
        if k == main:
            o['ids'] = [nid] + [i for i in o['ids'] if i != nid]; owner[nid] = k
            o['draw'] = [nid] + [i for i, _ in arcs] + added_arcs + leaves + [i for i, _, _ in other]
            for a_ in added_arcs: o['ids'].append(a_); owner[a_] = k
            o['marks'] = marks; o['door_struct'] = dict(opening=True, arcs=len(arcs), leaves=len(leaves), marks=len(marks), other=len(other))
            if kind and 'по самой двери' in kind: o['door_struct']['frame'] = 'по самой двери'
            # code 012: the ends reach_faces drew on to the face of a wall or glass - Э7о keeps them where they are and measures the
            #   depth where the end stood before (at the door's frame): 'at' - the middle of the end side, 'back' - how far it was drawn on (pt)
            o['ends_on_face'] = [dict(at=[float(x) for x in w(c0 if e_['end'] == 0 else c1, (tl2 + th2) / 2)], back=float(cf0 - c0 if e_['end'] == 0 else c1 - cf1))
                                 for e_ in ends_info if e_['what'] == 'доведён до грани']
            # test 10 (owner 07.10.2026: «то, что осталось нераспознанным… — это двери»): a door the source draws without its
            # swing arc — a leaf only — is named by its opening, not by a piece taken for an arc nor as «деталь проёма»
            if not arcs and leaves:
                w_ = int(round((cf1 - cf0) * K / 50.0) * 50)        # code 012: the frame's width, before reach_faces drew an end on
                o['name'] = f'Дверь {"двупольная" if len(leaves) >= 2 else "однопольная"} {w_} (полотно без дуги, по исходнику)'
            # test 10: the name by the door's own swings — the hinges are the arcs' centres (the pieces of one swing share a
            # centre, ≤ HINGE_MM): one hinge — a single door of the swing's radius, two — a double one (a door split off a
            # shared object, or one whose pieces were named by a neighbour's arc, gets its own name)
            elif arcs:
                hs = []
                for _, cf in arcs:
                    for h in hs:
                        if math.hypot(h[0] - cf[0], h[1] - cf[1]) <= HINGE_MM / K: h[2] = max(h[2], cf[2]); break
                    else: hs.append([cf[0], cf[1], cf[2]])
                rs = sorted(int(round(h[2] * K / 50.0) * 50) for h in hs)
                if len(rs) == 1: nm = f'Дверь однопольная {rs[0]}'
                elif len(rs) == 2: nm = f'Дверь двупольная {sum(rs)} (створки {rs[1]}+{rs[0]})' if rs[0] != rs[1] else f'Дверь двупольная {sum(rs)}'
                else: nm = None
                if nm and nm != o.get('name'): o['name_e7'] = o.get('name'); o['name'] = nm; rep['двери: имя по своим дугам'] += 1
        else:
            o['draw'] = [i for i in o.get('draw', o['ids']) if i in [x for x, _ in arcs] + leaves + [x for x, _, _ in other]]
            o.setdefault('marks', []); o['marks'] += [i for i in o['ids'] if i in marks]
            if not o['draw']: o['key'] = 'empty'; o['name'] = (o.get('name') or '') + ' → часть двери'
        done.add(k)
    rep['двери: пересобраны'] += 1; rep[f'двери: дуг {len(arcs)}'] += 1; rep[f'двери: полотен {len(leaves)}'] += 1
    if not arcs and not added_arcs: rep['двери: без дуги'] += 1
    if not leaves: rep['двери: полотно не найдено'] += 1
    if other: rep['двери: прочие куски оставлены'] += 1
    for e_ in ends_info:
        if e_['what'] == 'доведён до грани': rep['двери: конец проёма доведён до грани стены или стекла (код 011)'] += 1
        elif e_['what'] != 'на грани': rep['двери: конец проёма без грани стены или стекла рядом (шлюз O10 считает и блоки ядра)'] += 1
    rows.append(dict(at=[round(v, 1) for v in Rg.centroid.coords[0]], kind=kind, opening_mm=round((c1 - c0) * K), wall_mm=round((th2 - tl2) * K),
                     arcs=len(arcs) + len(added_arcs), arcs_added=len(added_arcs), leaves=len(leaves), marks=len(marks), contour_lines_replaced=len(contour), other=len(other)))
    if any(e_['what'] != 'на грани' for e_ in ends_info): rows[-1]['ends'] = ends_info
# test 10: two doors in one object — their pieces touch (a door in a side wall beside a double door), so Э7 made one object;
# Э6г found a frame for each. An object near two or more frames, one of which has no other door object near it, is shared
# out between them: an arc goes to the frame its centre (the hinge) is nearest to, any other piece — to the nearest frame;
# each part but the first becomes a door object of its own (the same layer and kind), then every frame is rebuilt as usual.
def rect_of(f):
    o_, u, n = np.array(f[0]), np.array(f[1]), np.array(f[2])
    return Polygon([tuple(o_ + u * a + n * b) for a, b in ((f[3], f[5]), (f[4], f[5]), (f[4], f[6]), (f[3], f[6]))])
FR = [rect_of(d['frame']) for d in R if d.get('frame')]
nsplit = 0
for k in list(DOORS):
    near = [x for x, Rg in enumerate(FR) if dg[k].distance(Rg) <= SPLIT_NEAR_MM / K]
    if len(near) < 2: continue
    lonely = [x for x in near if not any(k2 != k and dg[k2].distance(FR[x]) <= SPLIT_NEAR_MM / K for k2 in DOORS)]
    if not lonely: continue
    asg = collections.defaultdict(list)
    for i in objs[k]['ids']:
        if not live(i): continue
        pts = np.array(P[i]['p'], float); g = geom(P[i])
        if len(pts) >= 8:
            cf = circ(pts)
            if cf and cf[2] > ARC_R_MM / K and cf[3] <= 0.08 * cf[2]: g = Point(cf[0], cf[1])
        asg[min(near, key=lambda x: FR[x].distance(g))].append(i)
    parts_ = sorted(asg.values(), key=len, reverse=True)
    if len(parts_) < 2: continue
    objs[k]['ids'] = parts_[0]; objs[k]['draw'] = [i for i in objs[k].get('draw', parts_[0]) if i in set(parts_[0])] or parts_[0]
    for ids_ in parts_[1:]:
        k2 = len(objs); objs.append(dict(key='door', layer=objs[k]['layer'], kind=objs[k].get('kind', 'obj'), ids=ids_, draw=list(ids_), name='Дверь'))
        for i in ids_: owner[i] = k2
        DOORS.append(k2); dg[k2] = unary_union([geom(P[i]) for i in ids_])
    dg[k] = unary_union([geom(P[i]) for i in parts_[0]]); nsplit += 1; rep['двери: две двери в одном объекте — разделены'] += 1
if nsplit: dtree = shapely.STRtree([dg[k] for k in DOORS])
for d in R:
    f = d.get('frame')
    if not f: continue
    o_, u, n = np.array(f[0]), np.array(f[1]), np.array(f[2]); c0, c1, tl, th = f[3], f[4], f[5], f[6]
    Rg = Polygon([tuple(o_ + u * a + n * b) for a, b in ((c0, tl), (c1, tl), (c1, th), (c0, th))])
    ks = [DOORS[j] for j in dtree.query(Rg.buffer(1.5)) if dg[DOORS[j]].distance(Rg) <= 1.5 and DOORS[j] not in done]
    if not ks: rep['проём без объекта двери'] += 1; continue
    rebuild(f, ks, d.get('kind'))
# test 9 (owner 07.10.2026 «делай» — «1 дверь без рамки (лист 06)»): a door Э6г found no opening for — it stands across a
# passage from wall to wall, or in a wall drawn as lines, so no wall has a gap there. Its frame is taken from the door
# itself: the hinges are the centres of its swing arcs (circles of >= 8 points); the opening's axis u runs through the
# two hinges of a double door, or from the hinge to the arc's end that is not the open leaf's tip (the closed leaf) of a
# single one; along u — from hinge to hinge (to the closed end), drawn on to an element (wall, glass) within 1.5 pt
# beyond either end; across — the depth of the door's frame pieces at the hinges (small pieces within 1.5 pt of a
# hinge), else that of the walls within 1.5 pt of the ends, else 1 pt (48 mm). Then the door is rebuilt as any other.
def frame_from_door(k):
    ids = [i for i in objs[k]['ids'] if live(i) and not P[i].get('synthetic')]
    arcs_ = []
    for i in ids:
        pts = np.array(P[i]['p'], float)
        if len(pts) >= 8:
            cf = circ(pts)
            if cf and cf[2] > 3 and cf[3] <= 0.08 * cf[2]: arcs_.append((i, cf, pts))
    if not arcs_: return None, 'нет дуги'
    H = [np.array(cf[:2]) for _, cf, _ in arcs_]
    if len(arcs_) >= 2:
        a_, b_ = max(((x, y) for x in range(len(H)) for y in range(x + 1, len(H))), key=lambda xy: np.linalg.norm(H[xy[0]] - H[xy[1]]))
        p0, p1 = H[a_], H[b_]
        if np.linalg.norm(p1 - p0) < 3.0: return None, 'дуги с одним центром'
    else:
        i, cf, pts = arcs_[0]; p0 = H[0]
        others = [geom(P[j]) for j in ids if j != i]
        ends = [pts[0], pts[-1]]
        # the open leaf's tip: the arc end nearest to the door's other pieces' far ends; the closed end is the other one
        def near_leaf(e): return min([g.distance(Point(e)) for g in others] or [9e9])
        tip = min(ends, key=near_leaf); p1 = ends[1] if tip is ends[0] else ends[0]
    u = (p1 - p0) / np.linalg.norm(p1 - p0); n = np.array([-u[1], u[0]]); o_ = p0
    c0, c1 = 0.0, float((p1 - p0) @ u)
    # code 010 (К-2; owner's decision of 07.10.2026, №105, row 207; plan/rules/40 §5, п. 15): the door's frame (коробка) is
    #   part of the door, the opening runs from the face of one wall to the face of the other, its depth - the frame's.
    #   Small wall bodies at an end of the opening (<= 2.2 pt long, <= 1 pt thick, within 2.2 pt of the hinges' line - the
    #   hinges sit on a face of the frame; the frame pieces Э6 made bodies of: client-b, the double door 1400 - two gkl
    #   bodies 70 x 12 mm, ПК3-П15) go to the door: the opening runs through them on to the wall beyond, and they leave the
    #   walls (walls_j.pkl, below)
    box = []
    for j, g in enumerate(BG):
        L_, W_ = mrr_dims(g)
        if L_ > 2.2 or W_ > 1.0: continue
        cc = np.array(g.centroid.coords[0]); a_, b_ = float((cc - o_) @ u), float((cc - o_) @ n)
        if abs(b_) <= 2.2 and (c0 - 2.6 <= a_ <= c0 + 0.5 or c1 - 0.5 <= a_ <= c1 + 2.6): box.append(j)
    BOXB[k] = box
    # along u: on to an element (wall body, glass) within 1.5 pt beyond either end (beyond the frame's bodies), at the door's line
    for sgn in (-1, 1):
        a_end = c0 if sgn < 0 else c1
        bx = [float((np.array(q) - o_) @ u) for j in box for q in BG[j].exterior.coords
              if (sgn < 0 and float((np.array(BG[j].centroid.coords[0]) - o_) @ u) <= c0 + 0.5) or (sgn > 0 and float((np.array(BG[j].centroid.coords[0]) - o_) @ u) >= c1 - 0.5)]
        if bx: a_end = min(bx + [a_end]) if sgn < 0 else max(bx + [a_end])
        ray = LineString([tuple(o_ + u * a_end), tuple(o_ + u * (a_end + sgn * 1.5))])
        js = [j for j in et.query(ray) if j not in box and ELEM[j].intersects(ray)]
        if js:
            d_ = min(ELEM[j].distance(Point(o_ + u * a_end)) for j in js)
            a_end = a_end - d_ if sgn < 0 else a_end + d_
        if sgn < 0: c0 = min(c0, a_end)
        else: c1 = max(c1, a_end)
    # across: the frame pieces at the hinges, else the walls at the ends, else 1 pt
    small = []
    for j in ids:
        g = geom(P[j]); L_, W_ = mrr_dims(g)
        if L_ <= 2.2 and min(g.distance(Point(h)) for h in H) <= 1.5:
            small += [float((np.array(q) - o_) @ n) for q in (g.exterior.coords if g.geom_type == 'Polygon' else g.coords)]
    if small and 0.3 <= max(small) - min(small) <= 3.0: tl, th = min(small), max(small)
    else:
        tt = []
        for a_end in (c0, c1):
            pr = Point(o_ + u * a_end).buffer(1.5)
            for j in et.query(pr):
                x = ELEM[j].intersection(pr)
                if not x.is_empty and x.geom_type == 'Polygon': tt.append(2 * x.area / max(x.length, 1e-9))
        t_ = float(np.median(tt)) * 2 if tt else 1.0
        tl, th = -t_ / 2, t_ / 2
    return [tuple(o_), tuple(u), tuple(n), c0, c1, tl, th], 'ok'
left = [k for k in DOORS if k not in done]; BOXB = {}
for k in left:
    f, why = frame_from_door(k)
    if f is None: rep[f'двери без рамки Э6г — на перепроверку ({why})'] += 1; continue
    rebuild(f, [k], 'рамка по самой двери (Э6г проёма не нашёл)', depth_own=bool(BOXB.get(k))); rep['двери без рамки Э6г — рамка по самой двери'] += 1
    if BOXB.get(k):
        rows[-1]['frame_bodies_to_door'] = [dict(cls=W[j][0], size_mm=[round(v * K) for v in mrr_dims(BG[j])]) for j in BOXB[k]]
        rep['коробка двери: тела стен — в дверь (№105)'] += len(BOXB[k])
# code 010 (К-2, №105): the frame pieces of the doors above leave the walls - walls_j.pkl without them (Э7я, Э9, the export
#   and the checks read it); a body of the raw file that is a MultiPolygon loses only that part
_drop = [BG[j] for js in BOXB.values() for j in js]
if _drop:
    _WJ = pickle.load(open('walls_j.pkl', 'rb')); _nb = []; _gone = 0
    for c, g in _WJ['bodies']:
        parts = [q for q in getattr(g, 'geoms', [g])]
        keep = [q for q in parts if not (q.geom_type == 'Polygon' and any(q.equals_exact(x, 1e-9) or (q.symmetric_difference(x).area <= 1e-9 and abs(q.area - x.area) <= 1e-9) for x in _drop))]
        _gone += len(parts) - len(keep)
        if not keep: continue
        _nb.append((c, keep[0] if len(keep) == 1 else MultiPolygon(keep)) if len(keep) != len(parts) else (c, g))
    _WJ['bodies'] = _nb; pickle.dump(_WJ, open('walls_j.pkl', 'wb'))
    print('door frames: wall bodies to the doors', _gone, 'of', len(_drop))
left = [k for k in DOORS if k not in done]
json.dump(dict(counts=dict(rep), doors=rows, not_rebuilt=[dict(obj=k, name=objs[k].get('name'), at=[round(v, 1) for v in dg[k].centroid.coords[0]]) for k in left]),
          open('doors.json', 'w'), ensure_ascii=False, indent=1)
D1 = dict(D0); D1['P'] = P; pickle.dump(D1, open('prims_d.pkl', 'wb')); pickle.dump(O, open('objects.pkl', 'wb'))
print('doors', dict(rep), T())
