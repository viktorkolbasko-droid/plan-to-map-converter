"""ocg/ref_measures.py - code 012 (ОЧ-47, ОЧ-130): the numbers and the geometry of one run of the layer route, the same for
the reference (make_reference.py) and for the run checked against it (regress_check.py). Version - ref_lib.MEASURES_VERSION.
Runs in a STATE FOLDER (ref_state.py: cfg.py and the state files as they were at the export, the reports of the checks, the
DXF of both results) - its own process, so ocg/sheet.py reads that folder's cfg.py.
usage: python3 ref_measures.py <out.json> <out_geom.pkl> <detail.dxf> <outline.dxf> [zones.dxf]     (cwd - the state folder)

Where each measure comes from (the reports of ocg/run_ocg.sh; the v010 package read chk/t8_checks.json - ocg_checks.json is its
superset with the same schema):
 walls       ocg_checks.json walls: bodies, vertices, area, vertices on straight runs, voids, unjustified short edges, breaks
 checks_tail ocg_checks.json without walls (hanging lines, furniture left without a type, joints, doors of Э7д, …)
 doors       doors_fit.json (the opening against the walls at its ends, groups) + openings.json (service doors, when present)
 ocg         the stops of the gate as numbers: O1, O4, O6 (ocg_wallcls.json), O7, O8 (+ doors_check.json), O10, S14* (ocg_layers_*.json)
 objects     objects.pkl of the export state: counts by class, seats by kind; furniture.json; passage.pkl/.json; rooms.pkl
 qa, pz10    qa_remarks.py on both DXF (+ the zones DXF), dxf_pts.py - ПЗ-10 габаритный against подробный by group and type
A report the measures need and the run has not - STOP (exit 2), not 0; OCG_REF_ALLOW_MISSING='doors_fit,openings' lets the
named ones be «—» and writes them to numbers.missing_reports and numbers.allowed_missing (check of step 11: make_reference.py
and regress_check.py put allowed_missing into the head of their result and print «СНЯТ СТОП»)."""
import collections, json, os, pickle, sys

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
NEED = {'ocg_checks.json': 'checks_ocg.py', 'doors_fit.json': 'doors_fit.py'}
OPTIONAL = ('furniture.json', 'passage.json', 'openings.json', 'doors_check.json', 'ocg_wallcls.json', 'ocg_layers_detail.json',
            'ocg_layers_outline.json', 'passage.pkl', 'rooms.pkl')


def _ld(f):
    return json.load(open(f, encoding='utf-8')) if os.path.exists(f) else None


def main(out_json, out_pkl, d1, d2, zd=None):
    import numpy as np
    from shapely.ops import unary_union
    import sheet, ref_lib
    from e7_comp import geom, load_prims, load_walls
    import dxf_pts as dp, qa_remarks
    K = sheet.K
    if not K: sys.exit('STOP ref_measures: cfg.MM_PER_PT не задан')
    allow = {x.strip() for x in os.environ.get('OCG_REF_ALLOW_MISSING', '').split(',') if x.strip()}
    missing = [f for f in NEED if not os.path.exists(f)]
    hard = [f for f in missing if f.split('.')[0] not in allow]
    if hard: sys.exit(f'STOP ref_measures: нет отчётов {hard} (их пишут {[NEED[f] for f in hard]}); меры не ставятся в 0 молча — '
                      f'прогон без них не сверяется (OCG_REF_ALLOW_MISSING — только явно, с причиной в отчёте)')
    allowed = [f for f in missing if f not in hard]      # check of step 11: the lifted stop goes to numbers.allowed_missing - the head
    if allowed: print(f'СНЯТ СТОП ref_measures: нет отчётов {allowed} — их меры «—» по OCG_REF_ALLOW_MISSING')   # of the result says it
    P = load_prims()['P']; O = pickle.load(open('objects.pkl', 'rb'))['objs']; W = load_walls()['bodies']
    C = _ld('ocg_checks.json') or {}; D = _ld('doors_fit.json')
    FJ = _ld('furniture.json') or {}; PJ = _ld('passage.json') or {}; OJ = _ld('openings.json')
    def ogeom(o, ids=None):
        gs = [geom(P[i]) for i in (ids if ids is not None else o.get('draw', o['ids'])) if P[i]['kind'] != 'removed' and len(P[i]['p']) >= 2]
        gs = [g.buffer(0) if g.geom_type == 'Polygon' else g for g in gs if not g.is_empty]
        return unary_union(gs) if gs else None
    # ---------------- geometry
    doors = []
    for o in O:
        if o['key'] != 'door' or not o.get('draw'): continue
        op = [i for i in o['draw'] if P[i].get('opening')]
        if not op: continue
        doors.append(dict(name=o.get('name', ''), service=bool(o.get('service')), ring=np.array(P[op[0]]['p'], float)[:4].tolist()))
    furn = []
    for o in O:
        if o['key'] in ('door', 'corezone', 'coreline', 'wallline', 'empty', 'dim', 'axis', 'zone', 'measure') or not o['ids']: continue
        g = ogeom(o)
        if g is None or g.is_empty: continue
        furn.append(dict(key=o['key'], name=o.get('name', ''), c=list(g.centroid.coords[0]), area=g.area, bounds=list(g.bounds)))
    WL = sheet.L('wall')
    panes = [geom(p) for p in P if p['kind'] in ('fill', 'wline') and p.get('col') in sheet.GLASS and p['layer'] in WL and len(p['p']) >= 3]
    panes = [g for g in panes if g.geom_type == 'Polygon' and g.area > 0]
    blocks = [ogeom(o, o['outline']) for o in O if o['key'] == 'coreblock' and o.get('outline')]
    PS = pickle.load(open('passage.pkl', 'rb')) if os.path.exists('passage.pkl') else {'passage': []}
    RM = pickle.load(open('rooms.pkl', 'rb'))['rooms'] if os.path.exists('rooms.pkl') else []
    G = dict(walls=[(c, g) for c, g in W], panes=unary_union(panes) if panes else None, blocks=[b for b in blocks if b is not None],
             doors=doors, furniture=furn, passage=PS['passage'],
             rooms=[dict(poly=r['poly'], number=r.get('number', ''), kind=r.get('kind', ''), points=r.get('points'), area_m2=r.get('area_m2')) for r in RM])
    # ---------------- numbers
    cnt = collections.Counter(o['key'] for o in O if o['ids'] and o['key'] not in ('empty',))
    seats = collections.Counter(o.get('name', '').split(' (')[0] for o in O if o['key'] in ('chair', 'armchair') and o['ids'])
    wl = C.get('walls') or {}; se = (wl.get('short_edges') or {}).get('by_reason', {})
    N = dict(measures_version=ref_lib.MEASURES_VERSION)
    N['walls'] = dict(bodies=wl.get('bodies'), vertices=wl.get('vertices'), area_m2=wl.get('area_m2'), straight_run_vertices=wl.get('straight_run_vertices'),
                      voids=(wl.get('holes') or {}).get('voids'), short_edges_not_justified=sum(v for k, v in se.items() if 'не оправдан' in k),
                      short_edges_by_reason=se, breaks_without_door=(wl.get('breaks_without_door') or {}).get('n'))
    N['checks_tail'] = {k: C[k] for k in C if k != 'walls'}
    N['doors'] = dict(n=D['doors'], status=D['status'], end_gap_over_10mm=len(D['end_gap_over_10mm']), walls_in_opening=len(D['walls_in_opening']),
                      groups=len(D['groups']), groups_with_off=D['groups_with_off'], service=OJ.get('service_doors') if OJ else None) if D else dict(n=None)
    N['objects_by_key'] = dict(cnt); N['seats_by_kind'] = dict(seats)
    N['furniture'] = dict(desks=FJ.get('desks'), numbers_on_desks=FJ.get('numbers_on_desks'),
                          workplace_seats=FJ.get('workplace_seats', {}).get('counts') if isinstance(FJ.get('workplace_seats'), dict) else None)
    N['passage'] = dict(zones=len(PS['passage']), area_m2=round(sum(p.area for p in PS['passage']) * K * K / 1e6, 1),
                        open_spaces=[dict(at=r['at'], passage_m2=r['passage_m2'], vertices=r['vertices']) for r in PJ.get('open_spaces', [])])
    # the stops of the gate as numbers (lower is better); a report the run has not - «—»
    WC = _ld('ocg_wallcls.json'); DC = _ld('doors_check.json')
    jf = C.get('joints_final'); ndoors = sum(1 for o in O if o['key'] == 'door')
    def nn(d, k='n'): return d.get(k) if isinstance(d, dict) else None
    lay = [_ld(f) for f in ('ocg_layers_detail.json', 'ocg_layers_outline.json')]
    N['ocg'] = dict(o1_straight_other=(wl.get('straight_run_reasons') or {}).get('прочее', 0) if wl.get('bodies') else None,
                    o4_joints_final=nn(jf) if jf is not None else None,
                    o6_wallcls=nn(WC), o7_lines_outside_core=nn(C.get('walls_as_lines_outside_core')),
                    o8_doors_no_opening=nn(C.get('doors_no_opening')) if ndoors else None,
                    o8_hinge_far=len(DC.get('bad', [])) if DC is not None and ndoors else None,
                    o10_door_ends_off=nn(C.get('door_ends'), 'off_face') if ndoors else None,
                    s14_layers=sum(len(L.get('no_record') or {}) + len(L.get('no_description') or {}) + sum((L.get('texts_off_TD') or {}).values()) for L in lay)
                    if all(L is not None for L in lay) else None)
    N['missing_reports'] = sorted(set(missing) | {f for f in OPTIONAL if not os.path.exists(f)})
    N['allowed_missing'] = allowed                       # the needed reports the run has not, let by OCG_REF_ALLOW_MISSING
    # ---------------- ПЗ-1…ПЗ-9, ПЗ-10 on the DXF of both results
    dp.set_frame(sheet.K, sheet.OX, sheet.OY)
    sample = getattr(sheet.cfg, 'OCG_ROOM_SAMPLE', None); width = getattr(sheet.cfg, 'OCG_PASSAGE_W_MM', None)
    qa = {}; qa_places = {}
    for d_, tag in ((d1, 'подробный'), (d2, 'габаритный')):
        if d_ and os.path.exists(d_):
            r = qa_remarks.check(d_, zd if zd and os.path.exists(zd) else None, sample, width)
            qa[tag] = r['checks']; qa_places[tag] = r['places']
    N['qa'] = qa
    N['rooms'] = dict(n=len(RM), area_m2=round(sum(r.get('area_m2') or 0 for r in RM), 1), points=sum(r.get('points') or 0 for r in RM),
                      by_kind=dict(collections.Counter(r.get('kind', '') for r in RM)))
    def pz10(a, b):
        def sig(r):
            pts = r['V'] if r['V'] else r['D'][:3]
            return (r['key'], r['et'], tuple(sorted((round(x, 1), round(y, 1)) for x, y in pts)))
        A = collections.defaultdict(dict); B = collections.defaultdict(dict)
        for recs, M_ in ((dp.load(a)[0], A), (dp.load(b)[0], B)):
            for r in recs: M_[r.get('group') or '-'][sig(r)] = r.get('xt') or r['key']
        out = {}
        for g in sorted(set(A) | set(B)):
            da, db = A.get(g, {}), B.get(g, {}); diff = [da.get(s) or db.get(s) for s in set(da) ^ set(db)]
            out[g] = dict(n=len(diff), by_type=dict(collections.Counter(diff)))
        return out
    N['pz10_outline_vs_detailed'] = pz10(d1, d2) if d1 and d2 and os.path.exists(d1) and os.path.exists(d2) else {}
    json.dump(dict(numbers=N, mm_per_pt=K, qa_places=qa_places), open(out_json, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    pickle.dump(G, open(out_pkl, 'wb'))
    print('ref_measures', ref_lib.MEASURES_VERSION, '| doors', len(doors), '| furniture objects', len(furn), '| wall bodies', len(W), '| qa', sorted(qa))


if __name__ == '__main__':
    a = sys.argv[1:]
    if len(a) < 4: sys.exit(__doc__)
    main(a[0], a[1], a[2], a[3], a[4] if len(a) > 4 else None)
