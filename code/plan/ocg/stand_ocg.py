# ocg/stand_ocg.py - code 009: the stand of corruptions for the gate of the layer route (as review/gate_stand.py for the
#   Revit gates; Р30 and Р3 of the summary of 03.10.2026, п. 287). Copies of a finished run of the layer route, each with one
#   known defect put into its final result, and the checks and the gate run again (`run.sh gate`) - each copy must stop on
#   its defect: a stop that the clean copy does not have, or a larger number. A gate that passes a corrupted copy is not a gate.
#   Each case finds its place by features (the class of a body, the shape of its outline, a rebuilt door), not by coordinates.
#     W  a wall as lines: a body of a partition is taken out of the walls and its outline becomes a line object   -> O7
#     N  an irregularity: a notch (a step in and out, a third of the wall deep) on the longest straight side of a body -> O5
#     D  a door without its opening: the opening of a door rebuilt by the scheme is taken out of its drawing     -> O8
#     L  a layer without a record: a line of the detailed DXF on a layer the table does not have                  -> S14*
#     T  ТП3: a line of a wall layer along a body (0.1 pt off its side), owned by a light partition               -> O6
#     V  a void: a hole of 2 pt² inside a body                                                                     -> O2
#     J  an overlap at a joint: a body of a partition that touches another body grows by 0.3 pt into it                -> O4
#     S  a layer of the sheet without a record: the sheet's table in cfg loses one layer -> start_ocg.py stops (exit 3) before Э2
#   code 010 (package 4):
#     M  К-1: an МФУ back on A-79 - a line of the detailed DXF on A-79----E- (the layer is gone, №106, №108)          -> S14*
#     R  К-3, ПК3-П11: cfg.OCG_REF_MM_PER_PT = 60 - the field that lifted the scale stop silently in 009              -> start exit 3
#     K  К-3: the scale of cfg 60 mm/pt (off 2 % of 48.04) without cfg.SHEET_MM_PER_PT                               -> start exit 3
#     Q  К-3: the same with cfg.OCG_SCALE_OK = a reason outside the closed list (checks/accept.py)                  -> start exit 3
#   code 011 (package 5):
#     E  ПК4-П13: the end of a door opening off the face of the wall - one end of the opening of a door whose both ends are on
#        the faces of walls is moved 2 pt (96 mm) into the opening along its axis                                     -> O10
#     Q  (ПК4-П16) caught by «нет вида причины» - the words only a reason outside the closed list prints (K does not)
#     Q+ control: the scale 60 mm/pt with cfg.OCG_SCALE_OK = a reason of the closed list - start_ocg goes on (exit 0)
#     R2 ПК4-П16: cfg.OCG_SCALE_TOL = 0.5 - the other field that lifted the scale stop silently in 009              -> start exit 3
#     F1 ПК4-П14: cfg in pt of the copy (48.04), SHEET_MM_PER_PT forgotten - Э3 measures the sheet itself (scale.json 62.45)
#                                                                         -> start --after-e3 exit 3 «SHEET_MM_PER_PT не задан»
#     F2 ПК4-П14: SHEET_MM_PER_PT 3 % too large - the copy by the field is at 46.64 mm/pt by Э3  -> start --after-e3 exit 3 «поле неточно»
#   The clean copy gets cfg.OCG_REF_DXF / OCG_REF_DXF_OUTLINE = its own DXF (composition check O9 on, 0 differences).
#   code 012 (merge of v009): the final state of a run is that of Э7о - prims_o.pkl, and walls_o.pkl when Э7о cut a body (the
#   load_prims / load_walls chains read them first): the copies keep them, the cases corrupt the file the checks read (PF, WF).
#   code 012 (merge of v010): the final state is that of Э7р - prims_r.pkl, walls_r.pkl (Э7к: prims_k.pkl) - read first by the
#   chains; the copies keep them, PF and WF pick them first.
#   python3 stand_ocg.py <run dir> <code dir> <out dir> [cases, e.g. W,N]     -> <out dir>/stand.json and the table
import os, sys, json, shutil, subprocess, pickle, time, math
RUN, CODE, OUT = [os.path.abspath(a) for a in sys.argv[1:4]]
ONLY = sys.argv[4].split(',') if len(sys.argv) > 4 else None
CASES = ['BASE', 'W', 'N', 'D', 'L', 'T', 'V', 'J', 'S', 'M', 'R', 'K', 'Q', 'E', 'Q+', 'R2', 'F1', 'F2']
# check of step 11: an unknown case name ran only BASE and printed «поймано 0 из 0» - a stand that checks nothing must not pass
if ONLY and set(ONLY) - set(CASES): sys.exit(f'СТОП stand_ocg: случаев {sorted(set(ONLY) - set(CASES))} нет — известные: {",".join(CASES[1:])}')
os.makedirs(OUT, exist_ok=True)
KEEP = ('cfg.py', 'prims_r.pkl', 'prims_k.pkl', 'prims_o.pkl', 'prims_c.pkl', 'objects.pkl', 'walls_r.pkl', 'walls_o.pkl', 'walls_j.pkl',
        'joints.json', 'core.json', 'doors.json', 'openings.json', 'geom_report.json', 'furniture.json', 'walls_clean.json', 'passage.json',
        'sheetcheck.json', 'rooms.pkl', 'passage.pkl', 'classes.json', 'regular.json', 'zones.json')


def mk(case):
    d = os.path.join(OUT, case)
    if os.path.exists(d): shutil.rmtree(d)
    os.makedirs(d)
    for f in KEEP:
        if os.path.exists(os.path.join(RUN, f)): shutil.copy2(os.path.join(RUN, f), d)
    for sub in ('out', 'out_outline'):
        os.makedirs(os.path.join(d, sub))
        for f in os.listdir(os.path.join(RUN, sub)):
            if f.endswith('.dxf') or f.endswith('.json'): shutil.copy2(os.path.join(RUN, sub, f), os.path.join(d, sub))
    import importlib.util
    sp = importlib.util.spec_from_file_location('cfg_', os.path.join(d, 'cfg.py')); m = importlib.util.module_from_spec(sp); sp.loader.exec_module(m)
    os.symlink(os.path.join(RUN, m.PDF), os.path.join(d, m.PDF))
    os.makedirs(os.path.join(d, 'ref'))
    shutil.copy2(os.path.join(RUN, 'out', m.OUT + '_engineering.dxf'), os.path.join(d, 'ref'))
    shutil.copy2(os.path.join(RUN, 'out_outline', m.OUT + '_outline.dxf'), os.path.join(d, 'ref'))
    with open(os.path.join(d, 'cfg.py'), 'a', encoding='utf-8') as f:
        f.write(f"\n# ---- stand_ocg: the checked result of this copy - its own DXF before the corruption\nOCG_REF_DXF = 'ref/{m.OUT}_engineering.dxf'\n"
                f"OCG_REF_DXF_OUTLINE = 'ref/{m.OUT}_outline.dxf'\n")
    return d, m


def gate(d):
    t0 = time.time()
    r = subprocess.run(['bash', os.path.join(CODE, 'ocg', 'run_ocg.sh'), 'gate'], cwd=d, capture_output=True, text=True)
    g = json.load(open(os.path.join(d, 'ocg_gate.json'))) if os.path.exists(os.path.join(d, 'ocg_gate.json')) else None
    st = {s['code']: s['n'] for s in (g or {}).get('stops', []) if not s['accepted']}
    return st, r.returncode, round(time.time() - t0, 1), (r.stdout + r.stderr)[-600:]


def ld(d, f): return pickle.load(open(os.path.join(d, f), 'rb'))
def PF(d): return next(f for f in ('prims_r.pkl', 'prims_k.pkl', 'prims_o.pkl', 'prims_c.pkl') if os.path.exists(os.path.join(d, f)))   # the prims the checks read (load_prims)
def WF(d): return next(f for f in ('walls_r.pkl', 'walls_o.pkl', 'walls_j.pkl') if os.path.exists(os.path.join(d, f)))                  # the bodies the checks read (load_walls)
def dump(d, f, x): pickle.dump(x, open(os.path.join(d, f), 'wb'))


def body_pick(W, cls='gkl'):
    """a body of the class with the longest straight side, away from the other bodies (>= 2 pt)"""
    from shapely.geometry import LineString
    best = None
    for j, (c, g) in enumerate(W['bodies']):
        if c != cls or g.geom_type != 'Polygon': continue
        cs = list(g.exterior.coords)
        for a, b in zip(cs[:-1], cs[1:]):
            L = math.dist(a, b)
            if best is None or L > best[0]:
                seg = LineString([a, b]); mid = seg.interpolate(0.5, normalized=True)
                if any(k != j and g2.distance(mid) < 2.0 for k, (c2, g2) in enumerate(W['bodies'])): continue
                best = (L, j, a, b)
    return best


RES = []
cases = [c for c in CASES if ONLY is None or c in ONLY or c == 'BASE']
base = None
for case in cases:
    d, m = mk(case)
    # the stand edits pickles of the run; the layer of a new line - the first 'wall' layer of the sheet's table
    WL = next((r['layer'] for r in m.OCG_LAYERS if r.get('role') == 'wall'), '')
    expect, defect, where = [], '', None
    if case == 'W':
        W = ld(d, WF(d)); D0 = ld(d, PF(d)); O = ld(d, 'objects.pkl')
        b = body_pick(W); j = b[1]; c, g = W['bodies'][j]
        P = D0['P']; nid = len(P)
        P.append(dict(id=nid, layer=WL, kind='line', col=(0.0, 0.0, 0.0), p=[tuple(map(float, q)) for q in g.exterior.coords], w=0, seq=0, alpha=1.0, synthetic=True))
        k = len(O['objs']); O['objs'].append(dict(key='lpart', layer='A-22G', name='stand W: тело стены линиями', ids=[nid], kind='obj', draw=[nid]))
        O['owner'][nid] = k; W['bodies'] = [x for i, x in enumerate(W['bodies']) if i != j]
        dump(d, WF(d), W); dump(d, PF(d), D0); dump(d, 'objects.pkl', O)
        expect, defect, where = ['O7'], f'тело {c} {round(g.area, 1)} pt² — контуром-линией (lpart)', [round(v, 1) for v in g.centroid.coords[0]]
    elif case == 'N':
        from shapely.geometry import Polygon
        W = ld(d, WF(d)); b = body_pick(W); L, j, a, bb = b; c, g = W['bodies'][j]
        t = 2 * g.area / g.length; cs = list(g.exterior.coords)[:-1]; i = next(i for i in range(len(cs)) if cs[i] == a and cs[(i + 1) % len(cs)] == bb)
        ux, uy = (bb[0] - a[0]) / L, (bb[1] - a[1]) / L; nx, ny = -uy, ux
        if not g.contains(Polygon([a, bb, (bb[0] + nx * t / 2, bb[1] + ny * t / 2), (a[0] + nx * t / 2, a[1] + ny * t / 2)]).centroid): nx, ny = -nx, -ny
        dep = t / 3; s0, s1 = L * 0.45, L * 0.45 + max(0.5, t / 2)
        p1 = (a[0] + ux * s0, a[1] + uy * s0); p2 = (a[0] + ux * s1, a[1] + uy * s1)
        notch = [p1, (p1[0] + nx * dep, p1[1] + ny * dep), (p2[0] + nx * dep, p2[1] + ny * dep), p2]
        ring = cs[:i + 1] + notch + cs[i + 1:]
        g2 = Polygon(ring, [list(h.coords) for h in g.interiors])
        W['bodies'][j] = (c, g2); dump(d, WF(d), W)
        expect, defect, where = ['O5'], f'выемка {round(dep * m.MM_PER_PT)} мм на прямой стороне тела {c} (толщина {round(t * m.MM_PER_PT)} мм), valid={g2.is_valid}', [round(v, 1) for v in p1]
    elif case == 'D':
        O = ld(d, 'objects.pkl'); D0 = ld(d, PF(d)); P = D0['P']
        k = next(k for k, o in enumerate(O['objs']) if o['key'] == 'door' and o.get('door_struct') and any(P[i].get('opening') for i in o.get('draw', [])))
        o = O['objs'][k]; nid = next(i for i in o['draw'] if P[i].get('opening'))
        o['draw'] = [i for i in o['draw'] if i != nid]; o['ids'] = [i for i in o['ids'] if i != nid]; P[nid]['kind'] = 'removed'
        dump(d, 'objects.pkl', O); dump(d, PF(d), D0)
        expect, defect, where = ['O8'], f'у двери «{o.get("name")}» убран проём схемы', [round(v, 1) for v in P[nid]['p'][0]]
    elif case == 'L':
        import ezdxf
        fn = os.path.join(d, 'out', m.OUT + '_engineering.dxf'); doc = ezdxf.readfile(fn)
        doc.modelspace().add_line((0, 0), (1000, 0), dxfattribs={'layer': 'X-STAND--E-'}); doc.saveas(fn)
        expect, defect, where = ['S14*'], 'линия подробного DXF на слое X-STAND--E-, которого нет в таблице слоёв', [0, 0]
    elif case == 'M':
        import ezdxf
        fn = os.path.join(d, 'out', m.OUT + '_engineering.dxf'); doc = ezdxf.readfile(fn)
        doc.modelspace().add_lwpolyline([(0, 0), (600, 0), (600, 600), (0, 600)], close=True, dxfattribs={'layer': 'A-79----E-'}); doc.saveas(fn)
        expect, defect, where = ['S14*'], 'МФУ 600 × 600 мм на слое A-79----E- (слоя нет с кода 010, №106, №108)', [0, 0]
    elif case == 'T':
        W = ld(d, WF(d)); D0 = ld(d, PF(d)); O = ld(d, 'objects.pkl'); P = D0['P']
        L, j, a, bb = body_pick(W); c, g = W['bodies'][j]
        ux, uy = (bb[0] - a[0]) / L, (bb[1] - a[1]) / L; nx, ny = -uy, ux
        if g.contains(__import__('shapely').geometry.Point((a[0] + bb[0]) / 2 + nx * 0.1, (a[1] + bb[1]) / 2 + ny * 0.1)): nx, ny = -nx, -ny
        nid = len(P); P.append(dict(id=nid, layer=WL, kind='line', col=(0.0, 0.0, 0.0), p=[(a[0] + nx * 0.1, a[1] + ny * 0.1), (bb[0] + nx * 0.1, bb[1] + ny * 0.1)],
                                     w=0, seq=0, alpha=1.0, synthetic=True))
        k = len(O['objs']); O['objs'].append(dict(key='lpart', layer='A-22G', name='stand T: линия стены в чужом классе', ids=[nid], kind='obj', draw=[nid]))
        O['owner'][nid] = k; dump(d, PF(d), D0); dump(d, 'objects.pkl', O)
        expect, defect, where = ['O6'], f'линия слоя «{WL}» вдоль тела {c} в 0,1 pt, класс — lpart', [round(v, 1) for v in a]
    elif case == 'V':
        from shapely.geometry import Polygon, Point
        W = ld(d, WF(d))
        j = max((j for j, (c, g) in enumerate(W['bodies']) if c != 'column' and g.geom_type == 'Polygon'), key=lambda j: 2 * W['bodies'][j][1].area / W['bodies'][j][1].length)
        c, g = W['bodies'][j]; p = g.representative_point(); r = 0.7
        hole = Point(p.x, p.y).buffer(r, 4)
        g2 = g.difference(hole) if g.buffer(-r * 1.2).contains(Point(p.x, p.y)) else g
        W['bodies'][j] = (c, g2); dump(d, WF(d), W)
        expect, defect, where = ['O2'], f'дыра {round(hole.area, 2)} pt² в теле {c}, вставлена={g2 is not g}', [round(p.x, 1), round(p.y, 1)]
    if case == 'E':
        import numpy as np
        from shapely.geometry import LineString
        O = ld(d, 'objects.pkl'); D0 = ld(d, PF(d)); P = D0['P']; W = ld(d, WF(d))
        BG = [q for _, g in W['bodies'] for q in getattr(g, 'geoms', [g]) if q.geom_type == 'Polygon']
        best = None
        for k, o in enumerate(O['objs']):
            if o['key'] != 'door' or 'деталь' in (o.get('name') or ''): continue
            op = [i for i in o.get('draw', []) if P[i].get('opening') and P[i]['kind'] != 'removed' and len(P[i]['p']) >= 4]
            if not op: continue
            c = np.array(P[op[0]]['p'][:4], float); e01, e12 = np.linalg.norm(c[1] - c[0]), np.linalg.norm(c[2] - c[1])
            if e01 < e12: continue                                   # the ring of Э7д: c0-c1 along the axis
            ends = [LineString([tuple(c[1]), tuple(c[2])]), LineString([tuple(c[3]), tuple(c[0])])]
            if all(min(g.distance(e) for g in BG) <= 0.3 for e in ends) and (best is None or e01 > best[0]): best = (e01, k, op[0])
        L, k, i = best; ring = [list(p) for p in P[i]['p']]; c = np.array(ring[:4], float); u = (c[1] - c[0]) / np.linalg.norm(c[1] - c[0])
        for j in (1, 2): ring[j] = [ring[j][0] - u[0] * 2.0, ring[j][1] - u[1] * 2.0]       # the end c1 moved 2 pt back along the axis
        ring[4] = list(ring[0]); P[i]['p'] = [tuple(p) for p in ring]; dump(d, PF(d), D0)
        expect, defect, where = ['O10'], f'у двери «{O["objs"][k].get("name")}» конец проёма отодвинут от стены на 2 pt ({round(2 * m.MM_PER_PT)} мм)', [round(v, 1) for v in ring[1]]
    if case == 'J':
        W = ld(d, WF(d)); BG = [g for _, g in W['bodies']]
        j = next(j for j, (c, g) in enumerate(W['bodies']) if c == 'gkl' and g.geom_type == 'Polygon'
                 and any(k != j and BG[k].distance(g) <= 0.05 and BG[k].intersection(g).area < 1e-4 for k in range(len(BG))))
        c, g = W['bodies'][j]; W['bodies'][j] = (c, g.buffer(0.3, join_style=2)); dump(d, WF(d), W)
        expect, defect, where = ['O4'], f'тело {c} у стыка выросло на 0,3 pt в соседнее', [round(v, 1) for v in g.centroid.coords[0]]
    if case == 'S':
        drop = next(r['layer'] for r in reversed(m.OCG_LAYERS) if r.get('role') not in ('empty', None))
        with open(os.path.join(d, 'cfg.py'), 'a', encoding='utf-8') as f:
            f.write(f"\n# ---- stand_ocg S: the sheet's table without the layer {drop!r}\nOCG_LAYERS = [r for r in OCG_LAYERS if r['layer'] != {drop!r}]\n")
        t0 = time.time(); r_ = subprocess.run(['python3', os.path.join(CODE, 'ocg', 'start_ocg.py')], cwd=d, capture_output=True, text=True)
        out_ = (r_.stdout + r_.stderr).strip(); ok_ = r_.returncode == 3 and 'без записи' in out_
        RES.append(dict(case=case, defect=f'в таблице слоёв cfg нет слоя «{drop}»', where=None, expect=['start_ocg exit 3'], stops={'start': r_.returncode},
                        new={'start': r_.returncode}, caught=ok_, rc=r_.returncode, s=round(time.time() - t0, 1), tail=out_[-400:]))
        print(f"{case:4s} {'поймано' if ok_ else 'НЕ ПОЙМАНО':12s} ждём start_ocg exit 3 | rc {r_.returncode} | {out_[:200]}", flush=True)
        continue
    if case in ('R', 'K', 'Q', 'Q+', 'R2', 'F1', 'F2'):
        # code 011 (ПК4-П16): Q is caught by «нет вида причины» - printed only for a reason outside the closed list (the
        #   output of K has «закрытого списка» too); Q+ - the control, a reason of the closed list goes on (exit 0);
        #   R2 - OCG_SCALE_TOL; F1, F2 (ПК4-П14) - the scale of Э3 on the sheet read against cfg, the stop names the field
        add, want, what, rc_want, args = {
            'R': ("OCG_REF_MM_PER_PT = 60.0\n", 'убрано', 'в cfg поле OCG_REF_MM_PER_PT = 60 (снимало стоп масштаба молча в 009)', 3, []),
            'K': ("MM_PER_PT = 60.0\n", 'вне полосы', 'масштаб cfg 60 мм/pt, SHEET_MM_PER_PT нет', 3, []),
            'Q': ("MM_PER_PT = 60.0\nOCG_SCALE_OK = 'так надо'\n", 'нет вида причины', 'масштаб 60 мм/pt и OCG_SCALE_OK без вида причины', 3, []),
            'Q+': ("MM_PER_PT = 60.0\nOCG_SCALE_OK = 'так в исходнике: масштаб листа 60 мм/pt по размерам — кадр places/scale_60.png'\n",
                   'идёт без приведения', 'масштаб 60 мм/pt и OCG_SCALE_OK с причиной из закрытого списка (контроль)', 0, []),
            'R2': ("OCG_SCALE_TOL = 0.5\n", 'убрано', 'в cfg поле OCG_SCALE_TOL = 0.5 (снимало стоп масштаба молча в 009)', 3, []),
            'F1': ("", 'SHEET_MM_PER_PT не задан', 'cfg в pt копии (48,04), SHEET_MM_PER_PT забыт — Э3 по самому листу 62,45 мм/pt', 3, ['--after-e3']),
            'F2': (f"SHEET_MM_PER_PT = {48.04 * 1.3 * 1.03:.4f}\n", 'поле неточно', 'SHEET_MM_PER_PT на 3 % больше, копия по полю — Э3 по ней 46,64 мм/pt', 3, ['--after-e3']),
        }[case]
        with open(os.path.join(d, 'cfg.py'), 'a', encoding='utf-8') as f: f.write(f"\n# ---- stand_ocg {case}\n" + add)
        if case in ('F1', 'F2'):
            sc_ = json.load(open(os.path.join(RUN, 'scale.json')))
            sc_['A']['median'] = round(48.04 * 1.3, 3) if case == 'F1' else round(48.04 / 1.03, 3)
            json.dump(sc_, open(os.path.join(d, 'scale.json'), 'w'))
        t0 = time.time(); r_ = subprocess.run(['python3', os.path.join(CODE, 'ocg', 'start_ocg.py')] + args, cwd=d, capture_output=True, text=True)
        out_ = (r_.stdout + r_.stderr).strip(); ok_ = r_.returncode == rc_want and want in out_
        RES.append(dict(case=case, defect=what, where=None, expect=[f'start_ocg exit {rc_want}'], stops={'start': r_.returncode},
                        new={'start': r_.returncode}, caught=ok_, rc=r_.returncode, s=round(time.time() - t0, 1), tail=out_[-400:]))
        print(f"{case:4s} {'поймано' if ok_ else 'НЕ ПОЙМАНО':12s} ждём start_ocg {' '.join(args)} exit {rc_want} «{want}» | rc {r_.returncode} | {out_[:200]}", flush=True)
        continue
    st, rc, s, tail = gate(d)
    if case == 'BASE': base = st
    new = {c: n for c, n in st.items() if c not in base or n > base[c]}
    caught = bool(expect) and all(c in new for c in expect)
    RES.append(dict(case=case, defect=defect or 'чистая копия (с эталоном состава)', where=where, expect=expect, stops=st, new=new,
                    caught=caught if case != 'BASE' else None, rc=rc, s=s, tail=tail if not st else ''))
    print(f"{case:4s} {('поймано' if caught else 'НЕ ПОЙМАНО') if case != 'BASE' else 'база':12s} ждём {expect} | новые {new} | rc {rc} | {s} с | {defect}", flush=True)
json.dump(RES, open(os.path.join(OUT, 'stand.json'), 'w'), ensure_ascii=False, indent=1)
n = sum(1 for r in RES if r['case'] != 'BASE'); k = sum(1 for r in RES if r['caught'])
print(f'стенд: поймано {k} из {n}')
