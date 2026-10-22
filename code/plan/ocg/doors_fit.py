"""Test 10 check (owner 07.10.2026: «На слое с дверями ты не везде попадаешь в проем… проверить, что толщина проема совпадает
с толщиной стены… посравнивать разные двери с проемами, однотипные на однотипных стенах… классифицировать по группам. Если
они относятся к одной группе и на одной стене стоят, то они должны быть почти наверняка одной толщины и ширины»).
For every door with an opening (a closed rectangle, Э7д/Э7о), measured again here:
 - the reference at each end: the section of the element beyond the end (door_slices.section: wall bodies, glass panes,
   core blocks; stable, not cut short, ≥ 19 mm) or else the source's jamb (door_slices.jamb, ≥ 14 mm);
 - faces: the opening's long sides against the reference's faces at each end (mm); fit — both ≤ 10 mm at every end with a
   reference; «по одному концу» — fits one end while the references of the two ends differ by > 14 mm (different walls on
   the two sides: a box and a thin wall, a column);
 - ends: the gap between a short side and the element beyond it — the clearance (the distance from the short side to the
   carriers in the band of the opening's depth beyond the end, up to 72 mm; owner 10.10.2026, №126: «щель — зазор, а не
   непокрытая часть торца»; v009: along the axis at the middle of the depth, so a side that touches a step of the wall only
   in part showed the uncovered part as a gap);
 - an end on a step (owner 10.10.2026, №126 «Вид 012, поправить проверку»: «Проём от грани до грани, 1605 мм, без щелей;
   doors_fit считает торец на уступе „в проёме“, если щели нет»): where the element beyond the end runs across the opening's
   axis (the section is clipped — the side of a perpendicular wall, a step, a block — or there is none), its faces say nothing
   of the opening's depth; such an end fits when it touches the element at least in part with no clearance over GAP_MM and
   the element's faces (its jamb or section, if found) cover the opening's depth within FIT_MM — the element is wider than
   the opening ('abut_mm' of the end); an element that falls short of a face of the opening stays a misfit;
 - walls in the opening: the area of wall bodies inside the opening (> 115 mm², written in pt² as v009 did);
 - groups: doors of one kind (the name: single/double, the width, the leaves; service), the class of the elements at the
   ends and their thickness (to 10 mm) — one width and one thickness expected: members off the group's median (width
   > 20 mm, thickness > 10 mm) are listed.
Code 012 (stage 1 of the merge of v009 into ocg/; the code of pass v009, route/doors_fit.py): a check of the layer route
(ocg/run_ocg.sh, after the checks of ocg/checks_ocg.py) — a report, not a stop of the gate (a crash — O0 like any check);
the sheet from cfg (ocg/sheet.py: the walls' layers — role 'wall', glass — cfg.OCG_GLASS_COLORS, the scale — cfg.MM_PER_PT),
thresholds in mm through the scale (v009: pt at 48.04 mm/pt <one example: client-b, floor 40>). The JSON is of the schema
of v009 (route/regress_check.py and route/make_reference.py read it): doors, status, end_gap_over_10mm, walls_in_opening,
groups, groups_with_off, all — the same keys and units (walls_in_opening_pt2 — pt² of the sheet).
usage: python3 doors_fit.py [out.json, default doors_fit.json]   (floor folder, after e7o_openings.py)"""
import pickle, json, sys, collections, re, os
import numpy as np, shapely
from shapely.geometry import Polygon, LineString
from shapely.ops import unary_union
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import sheet
from e7_comp import geom, load_prims, load_walls
from door_slices import Carriers, section, Strokes, jamb, JAMB_EX_ROLES, TOUCH_MM
K = sheet.K; WALL_L = sheet.L('wall')
if not K: sys.exit('СТОП doors_fit: нет масштаба листа cfg.MM_PER_PT — пороги проверки в мм не перевести в pt (plan/rules/20 §3.8)')
if not WALL_L: sys.exit('СТОП doors_fit: в таблице слоёв cfg.OCG_LAYERS нет слоёв роли wall (ocg/sheet.py ROLES)')
OUTF = sys.argv[1] if len(sys.argv) > 1 else 'doors_fit.json'
SEC_MIN_MM, JAMB_MIN_MM, RAY_MM, FACE_MM, WALL_IN_MM2 = 19.216, 14.412, 72.06, 14.412, 115.39208   # v009: 0.4; 0.3; 1.5; 0.3 pt; 0.05 pt² - pt × 48.04 exactly (step 8; check of step 11: were rounded to 0.1 mm)
FIT_MM, GAP_MM, GROUP_W_MM, GROUP_T_MM = 10, 10, 20, 10                                # v009: in mm
P = load_prims()['P']; O = pickle.load(open('objects.pkl', 'rb'))['objs']; W = load_walls()['bodies']
GLASS = sheet.GLASS
items = [('стена ' + c, g) for c, g in W]
items += [('стекло', g) for g in (geom(p) for p in P if p['kind'] in ('fill', 'wline') and p.get('col') in GLASS and p['layer'] in WALL_L) if g.geom_type == 'Polygon' and g.area > 0]
for o in O:
    if o['key'] == 'coreblock' and o.get('outline'):
        g = unary_union([geom(P[i]) for i in o['outline'] if P[i]['kind'] == 'fill'])
        if not g.is_empty: items.append(('блок ядра', g))
C = Carriers(items); S = Strokes(P, geom, sheet.L(*JAMB_EX_ROLES)); BT = shapely.STRtree([g for _, g in W])
def kind_of(name):
    m = re.match(r'Дверь (служебная )?(однопольная|двупольная) (\d+)( \(створки [^)]*\))?', name or '')
    return ' '.join(x.strip() for x in (m.group(1) or '', m.group(2), m.group(3), m.group(4) or '') if x) if m else (name or '')[:30]
def end_gap(o_, u, n, a_end, sgn, Th):
    """the clearance between the opening's short side at a_end and the carriers beyond it (pt): the distance from the side to
    the carriers inside the band of the opening's depth (widened by TOUCH_MM: a carrier whose face is the side's own line
    touches it) out to RAY_MM beyond the end; None — no carrier there (owner 10.10.2026, №126: a gap is a clearance, not the
    part of the side left uncovered)"""
    ray, tw = RAY_MM / K, TOUCH_MM / K
    side = LineString([tuple(o_ + u * a_end), tuple(o_ + u * a_end + n * Th)])
    band = Polygon([tuple(o_ + u * a_end + n * (-tw)), tuple(o_ + u * (a_end + sgn * ray) + n * (-tw)),
                    tuple(o_ + u * (a_end + sgn * ray) + n * (Th + tw)), tuple(o_ + u * a_end + n * (Th + tw))])
    ds = [side.distance(x) for j in C.tree.query(band) for x in [C.items[j][1].intersection(band)] if not x.is_empty]
    return min(ds) if ds else None
rows = []
for k, o in enumerate(O):
    if o['key'] != 'door' or not o.get('draw'): continue
    op = [i for i in o['draw'] if P[i].get('opening') and len(P[i]['p']) >= 4]
    if not op: continue
    cs = np.array(P[op[0]]['p'], float)[:4]; e1, e2 = cs[1] - cs[0], cs[2] - cs[1]
    if np.linalg.norm(e2) > np.linalg.norm(e1): cs = np.roll(cs, -1, axis=0); e1, e2 = cs[1] - cs[0], cs[2] - cs[1]
    Wd, Th = float(np.linalg.norm(e1)), float(np.linalg.norm(e2)); u = e1 / Wd; n = e2 / max(Th, 1e-9); o_ = cs[0]
    Rg = Polygon(cs)
    refs = []; gaps = []; abut = []
    for a_end, sgn in ((0.0, -1), (Wd, 1)):
        s = section(C, o_, u, n, a_end, sgn, 0.0, Th, K); j = jamb(S, o_, u, n, a_end, 0.0, Th, K, marks=o.get('marks', []))
        if s and s['stable'] and not s['clipped'] and s['hi'] - s['lo'] >= SEC_MIN_MM / K: refs.append(('стена', s['lo'], s['hi'], s['cls']))
        elif j and j['hi'] - j['lo'] >= JAMB_MIN_MM / K: refs.append(('откос', j['lo'], j['hi'], j['cls']))
        else: refs.append(None)
        g_ = end_gap(o_, u, n, a_end, sgn, Th); gaps.append(None if g_ is None else round(g_ * K))
        # №126, an end on a step: the element beyond runs across the axis (a clipped section, or none), the end touches it with
        # no clearance over GAP_MM, and its faces (the reference, if any) do not fall short of the opening's faces — it is
        # wider than the opening (a step, the side of a thicker wall), not shallower nor shifted (that stays «мимо»)
        across = s is None or bool(s['clipped']); rf = refs[-1]
        covers = rf is None or (rf[1] <= FIT_MM / K and rf[2] >= Th - FIT_MM / K)
        abut.append(round(g_ * K) if across and covers and g_ is not None and g_ * K <= GAP_MM else None)
    fit = []
    for rf in refs:
        if rf is None: fit.append(None); continue
        fit.append((round((0.0 - rf[1]) * K), round((Th - rf[2]) * K)))
    inwall = sum(W[j][1].intersection(Rg).area for j in BT.query(Rg))
    r = dict(obj=k, name=o.get('name', ''), kind=kind_of(o.get('name', '')), service=bool(o.get('service')), at=[round(float(v), 1) for v in cs.mean(0)],
             width_mm=round(Wd * K), thick_mm=round(Th * K),
             ends=[None if rf is None else dict(by=rf[0], cls=rf[3], lo_mm=round(rf[1] * K), hi_mm=round(rf[2] * K), wall_mm=round((rf[2] - rf[1]) * K)) for rf in refs],
             faces_off_mm=fit, end_gaps_mm=gaps, walls_in_opening_pt2=round(inwall, 3))
    if any(a_ is not None for a_ in abut): r['abut_mm'] = abut          # №126: an end on a step, touching with no clearance
    ok_ends = [(f is not None and abs(f[0]) <= FIT_MM and abs(f[1]) <= FIT_MM) or a_ is not None for f, a_ in zip(fit, abut)]
    has = [rf is not None or a_ is not None for rf, a_ in zip(refs, abut)]
    got = [rf for rf in refs if rf]
    differ = len(got) == 2 and (abs(got[0][1] - got[1][1]) > FACE_MM / K or abs(got[0][2] - got[1][2]) > FACE_MM / K)
    if not any(has): st = 'нет опоры: ни стены, ни откоса у концов'
    elif all(ok for ok, h in zip(ok_ends, has) if h): st = 'в проёме'
    elif differ and any(ok_ends): st = 'по одному концу (стены у концов разные)'
    else: st = 'мимо проёма'
    r['status'] = st
    r['gap_ok'] = all(g is None or g <= GAP_MM for g in gaps); r['walls_ok'] = inwall * K * K <= WALL_IN_MM2
    cls = '/'.join(sorted(set(rf[3].split('/')[0] for rf in got))) if got else 'нет'
    wall = int(round(np.median([(rf[2] - rf[1]) * K for rf in got]) / 10.0) * 10) if got else 0
    r['group'] = f"{r['kind']} | {cls} {wall}"
    rows.append(r)
G = collections.defaultdict(list)
for r in rows: G[r['group']].append(r)
groups = []
for key, rs in sorted(G.items(), key=lambda kv: -len(kv[1])):
    mw = float(np.median([r['width_mm'] for r in rs])); mt = float(np.median([r['thick_mm'] for r in rs]))
    off = [dict(obj=r['obj'], at=r['at'], width_mm=r['width_mm'], thick_mm=r['thick_mm'], status=r['status']) for r in rs if abs(r['width_mm'] - mw) > GROUP_W_MM or abs(r['thick_mm'] - mt) > GROUP_T_MM]
    groups.append(dict(group=key, n=len(rs), median_width_mm=round(mw), median_thick_mm=round(mt), widths=sorted(r['width_mm'] for r in rs), thicks=sorted(r['thick_mm'] for r in rs), off=off))
res = dict(doors=len(rows), status=dict(collections.Counter(r['status'] for r in rows)),
           end_gap_over_10mm=[dict(obj=r['obj'], at=r['at'], gaps=r['end_gaps_mm']) for r in rows if not r['gap_ok']],
           walls_in_opening=[dict(obj=r['obj'], at=r['at'], pt2=r['walls_in_opening_pt2']) for r in rows if not r['walls_ok']],
           groups=groups, groups_with_off=sum(1 for g in groups if g['off']), all=rows)
json.dump(res, open(OUTF, 'w'), ensure_ascii=False, indent=1)
print('doors', res['doors'], '|', res['status'], '| end gaps > 10 mm', len(res['end_gap_over_10mm']), '| walls in the opening', len(res['walls_in_opening']),
      '| groups', len(groups), '| groups with members off', res['groups_with_off'])
