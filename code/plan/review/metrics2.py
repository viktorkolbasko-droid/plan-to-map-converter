# Metrics of two runs side by side (run folders with the check JSONs): python3 metrics2.py runA runB out.json
#   Prints a table: metric | A | B. Everything is read from the files the pipeline wrote - nothing is estimated.
import sys, os, json, pickle, collections, math
A, B, OUT = sys.argv[1:4]
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
def J(d, f):
    p = os.path.join(d, f); return json.load(open(p)) if os.path.exists(p) else {}
def fid_len(d):
    """length-weighted fidelity: off-line length and p95 by length (the check's own p95 counts edges)"""
    cwd = os.getcwd(); os.chdir(d)
    from importlib import reload
    import common; reload(common)
    from shapely.geometry import LineString
    from shapely.strtree import STRtree
    import numpy as np
    P = common.load(); cls = pickle.load(open('cls.pkl', 'rb')); w = pickle.load(open(common.walls_file(), 'rb'))['Wpt']
    L = [LineString(list(p[4]) if p[0] == 'l' else common.bez(p[4], 12)) for i, p in enumerate(P) if p[0] in ('l', 'c') and cls[i] != 'sheet']
    tr = STRtree(L); ds = []; ws = []
    for k, v in w.items():
        for pg_ in v:
            for pg in (list(pg_.geoms) if pg_.geom_type == 'MultiPolygon' else [pg_]):
                for ring in [pg.exterior] + list(pg.interiors):
                    c = list(ring.coords)
                    for a, b in zip(c[:-1], c[1:]):
                        s = LineString([a, b]); m = s.interpolate(0.5, normalized=True)
                        ds.append(L[tr.nearest(m)].distance(m) * common.MM_PER_PT); ws.append(s.length * common.MM_PER_PT)
    os.chdir(cwd)
    ds = np.array(ds); ws = np.array(ws); o = np.argsort(ds); cw = np.cumsum(ws[o]) / ws.sum()
    return dict(off_len_mm=round(float(ws[ds > 0.5].sum())), off_edges_gt2mm=int((ds > 2).sum()),
                p95_len_mm=round(float(ds[o][np.searchsorted(cw, 0.95)]), 2), p99_len_mm=round(float(ds[o][np.searchsorted(cw, 0.99)]), 2))
def M(d):
    R = {}
    I = pickle.load(open(os.path.join(d, 'inst_final.pkl'), 'rb')); I = [q for q in I if q['prims']]
    c = collections.Counter(q['key'] for q in I)
    W = pickle.load(open(os.path.join(d, 'walls_fixed.pkl'), 'rb'))['W']
    R['Стены, м² (все)'] = round(sum(g.area for v in W.values() for g in v) / 1e6, 2)
    for k in ('ext', 'cap', 'gkl', 'blk'): R[f'  из них {k}, м²'] = round(sum(g.area for g in W.get(k, [])) / 1e6, 2)
    R['Объектов всего'] = len(I)
    for k, lab in (('door', 'Двери с дугой'), ('door45', 'Двери «полотно и хорда»'), ('column', 'Колонны'), ('fire', 'Пожарные шкафы'),
                   ('lift', 'Лифты'), ('stair', 'Лестницы'), ('convector', 'Конвекторы'), ('chair', 'Стулья офисные'), ('desk', 'Столы (бенчи)'),
                   ('glass', 'Стекло: объектов'), ('mark', 'Служебные метки'), ('mask', 'Маски'), ('wcacc', 'Аксессуары С/у'), ('misc', '«Прочее»: объектов')):
        R[lab] = c.get(k, 0)
    R['Ключей (классов) в плане'] = len(c)
    mi = J(d, 'misc_inventory.json'); R['«Прочее»: групп'] = mi.get('groups')
    rc = J(d, 'reclass.json'); R['«Прочее»: примитивов после разбора'] = rc.get('misc_prims_left')
    R['«Прочее»: безымянных объектов'] = sum(1 for q in I if q['key'] == 'misc' and q['name'].startswith('Прочий элемент'))
    v = J(d, 'verify.json'); R['Доля классифицированного (verify)'] = v.get('classified_share'); R['Разрывы стен без объяснения (verify)'] = len(v.get('wall_gaps_unexplained', []))
    R['Двери, оба косяка на стене'] = f"{v.get('doors_with_both_jambs_on_carrier')} из {v.get('doors_total')}"
    ink = J(d, 'ink.json'); iks = J(d, 'ink_strict.json')
    R['Чернила: пропущено / лишнее, pt²'] = f"{ink.get('missing_pt2')} / {ink.get('extra_pt2')}"
    R['Чернила строго: пропущено / лишнее, pt²'] = f"{iks.get('missing_pt2')} / {iks.get('extra_pt2')}"
    f = J(d, 'fidelity.json'); R['Контур стен на линиях листа (доля длины)'] = f.get('share_len_on_source_lines'); R['fidelity p95 по числу рёбер, мм'] = f.get('p95_mm')
    fl = fid_len(d); R['fidelity: длина рёбер > 0,5 мм от линий, мм'] = fl['off_len_mm']; R['fidelity: рёбер > 2 мм'] = fl['off_edges_gt2mm']; R['fidelity p95 по длине, мм'] = fl['p95_len_mm']
    g = J(d, 'geomqa.json'); R['geomqa: разрывы, не объяснённые листом'] = sum((g.get('wall_gaps_unexplained_by_source') or {}).values())
    R['geomqa: концы витража со щелью > 20 мм'] = len(g.get('facade_ends_glass_gap_gt_20mm', []))
    r = J(d, 'rooms.json'); R['Помещения: открытых концов'] = r.get('n_open_ends'); R['Марок вне замкнутого помещения'] = len(r.get('tags_not_in_a_closed_room', []))
    cp = J(d, 'class_params.json'); R['Параметры классов: нарушений'] = cp.get('violations') if not isinstance(cp.get('violations'), list) else len(cp.get('violations'))
    we = J(d, 'wall_evidence.json'); R['Пустые тела стен'] = we.get('empty')
    aa = J(d, 'arcs_audit.json'); R['Дуги с узором: полос / ниже 90 %'] = f"{aa.get('bands')} / {aa.get('below')}"
    return R
RA, RB = M(A), M(B)
json.dump(dict(A=RA, B=RB), open(OUT, 'w'), ensure_ascii=False, indent=1)
for k in RA: print(f'{k:48s} | {RA[k]!s:>14} | {RB.get(k)!s:>14}')
