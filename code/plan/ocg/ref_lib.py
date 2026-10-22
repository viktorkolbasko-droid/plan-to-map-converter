"""ocg/ref_lib.py - code 012 (ОЧ-47, ОЧ-130): the core of the regress check - a run's numbers and geometry against the
reference of its sheet («не хуже эталона»: #63 §2 п. 3; the measures of #88 Э2; #95 Р4; #90 О-1). Pure functions, no cfg and
no route state: make_reference.py and regress_check.py feed it, a test feeds it synthetic dicts.

Rules (every line of the result is one of them, with its tolerance):
 - numbers «не хуже»: lower is better - voids, breaks without a door, unjustified short edges, vertices on straight runs,
   hanging lines, furniture without a type, doors off their opening, walls in openings, end gaps, door groups with members
   off, the stops of the ocg gate (O1, O4, O6, O7, O8, O10, S14*); higher is better - doors in their opening, numbers on desks;
 - counts «как в эталоне»: doors, service doors, objects of each class, rooms - a difference is a change to look at;
 - geometry: wall bodies of each class IoU >= 0.98 and the places differing by > 0.05 m²; glass, core blocks IoU >= 0.98;
   every door of the reference - a door of the same name within 0.5 m, its opening within 10 mm; every furniture object -
   one of the same class within 100 mm, area within 10 %; passages - IoU >= 0.90, area within 5 %;
 - the remark checks ПЗ-1…ПЗ-9 of both results by unique places - not more (door arcs dashed, ПЗ-6 - not fewer; the sample
   room - not more points); points of the DXF - more than +5 % is a regression; rooms - every room of the reference has one
   of the run with IoU >= 0.95; ПЗ-10 (габаритный against подробный) - groups 2, 4, 6, 7, 8 not more than the reference.
О-1: a measure with no objects of its class is «—» (None), never 0. Both «—» - a «—» line; the reference has a number and
the run «—» - a regression (nothing left to measure); the reference «—» and the run a number - a change (a new measure or new
objects). The measures version is written in the head of the result (MEASURES_VERSION; a reference without one - 'v010').
Р4: the files of the reference with the greatest __vNNN are taken (pick())."""
import collections, glob, json, math, os, pickle, re

MEASURES_VERSION = 'ocg-012.2'     # the version of the measures (what make_reference.py takes and how); change it with any change of a measure
# ocg-012.2 (step 8b, owner 10.10.2026 №126): doors_fit — the gap at an end is the clearance, an end on a step touching with no
# clearance fits («в проёме»); ocg-012.1 — the measures of step 8 (reference v003 of v010)
LEGACY_VERSION = 'v010'            # a reference made by route/make_reference.py of the v010 package (no measures_version)
DASH = '—'
LOWER_OCG = (('O1 вершины на прямых без причины', 'o1_straight_other'), ('O4 нахлёст или щель итоговых тел', 'o4_joints_final'),
             ('O6 линия стены не своего класса', 'o6_wallcls'), ('O7 стена линиями вне ядра', 'o7_lines_outside_core'),
             ('O8 дверь без проёма схемы', 'o8_doors_no_opening'), ('O8 петля дальше 150 мм', 'o8_hinge_far'),
             ('O10 конец проёма не на грани', 'o10_door_ends_off'), ('S14* слои DXF без записи', 's14_layers'))
_V = re.compile(r'__v(\d{3})\.(json|pkl)$')


# ------------------------------------------------------------------ Р4: the reference files with the greatest __vNNN
def pick(ref_dir):
    """(json path, pkl path, 'vNNN'): the greatest NNN that has both files; files without __vNNN only when the folder has no
    versioned files at all ('v001'). Raises ValueError when the greatest json and pkl versions differ or nothing is there."""
    vs = collections.defaultdict(dict)
    for f in os.listdir(ref_dir):
        m = _V.search(f)
        if m and f.startswith(('reference__', 'reference_geom__')): vs[int(m.group(1))][m.group(2)] = os.path.join(ref_dir, f)
    if vs:
        top = max(vs)
        if set(vs[top]) != {'json', 'pkl'}:
            raise ValueError(f'эталон {ref_dir}: у наибольшей версии v{top:03d} нет пары json + pkl ({sorted(vs[top])}) — стоп, не беру меньшую молча')
        return vs[top]['json'], vs[top]['pkl'], f'v{top:03d}'
    j, p = os.path.join(ref_dir, 'reference.json'), os.path.join(ref_dir, 'reference_geom.pkl')
    if os.path.exists(j) and os.path.exists(p): return j, p, 'v001'
    raise ValueError(f'в {ref_dir} нет файлов эталона (reference__vNNN.json + reference_geom__vNNN.pkl)')


def next_version(ref_dir):
    """the NNN for a new reference in the folder: greatest + 1 (a reference folder is never overwritten)"""
    if not os.path.isdir(ref_dir): return 1
    ns = [int(m.group(1)) for f in os.listdir(ref_dir) for m in [_V.search(f)] if m]
    if ns: return max(ns) + 1
    return 2 if os.path.exists(os.path.join(ref_dir, 'reference.json')) else 1


def load(ref_dir):
    j, p, v = pick(ref_dir)
    R = json.load(open(j, encoding='utf-8')); G = pickle.load(open(p, 'rb'))
    return R, G, dict(json=os.path.basename(j), pkl=os.path.basename(p), version=v)


def measures_version(R):
    return R.get('measures_version') or LEGACY_VERSION


# ------------------------------------------------------------------ the comparison
class Out:
    def __init__(self): self.regress, self.changes, self.same, self.dash = [], [], [], []

    def num(self, path, a, b, better):
        if a is None and b is None: self.dash.append(f'{path}: {DASH}'); return
        if a is None: self.changes.append(f'{path}: эталон {DASH} → {b} (в эталоне меры нет — новая мера или новые объекты)'); return
        if b is None: self.regress.append(f'{path}: эталон {a} → {DASH} (в прогоне не на чем мерить)'); return
        if b == a: self.same.append(f'{path}: {b}'); return
        worse = (b > a) if better == 'lower' else (b < a)
        (self.regress if worse else self.changes).append(f'{path}: эталон {a} → {b}')


def _get(d, *ks):
    for k in ks:
        if not isinstance(d, dict) or k not in d: return None
        d = d[k]
    return d


def _num(v):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def _doors_base(n):
    """О-1: the door measures are «—» when there are no doors"""
    return bool(_num(_get(n, 'doors', 'n')))


def _U(gs):
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    gs = [g for g in gs if g is not None and not g.is_empty]
    return unary_union(gs) if gs else Polygon()


def iou(a, b):
    if a.is_empty and b.is_empty: return None
    un = a.union(b).area
    return a.intersection(b).area / un if un > 0 else None


def _rnd(p): return [round(x, 1) for x in p]


def compare(R, RG, N, NG, K):
    """the run (N numbers, NG geometry) against the reference (R, RG); K - mm per pt of the sheet (areas and distances).
    Returns Out with the lists; R and N are the 'numbers' dicts."""
    import numpy as np
    from shapely.geometry import Polygon
    o = Out(); rn, nn = R, N
    # walls
    rw, nw = rn.get('walls') or {}, nn.get('walls') or {}
    wb_r, wb_n = bool(_num(rw.get('bodies'))), bool(_num(nw.get('bodies')))
    for k_ in ('voids', 'short_edges_not_justified', 'straight_run_vertices'):
        o.num(f'стены.{k_}', _num(rw.get(k_)) if wb_r else None, _num(nw.get(k_)) if wb_n else None, 'lower')
    o.num('стены.breaks_without_door', _num(rw.get('breaks_without_door')) if wb_r else None, _num(nw.get('breaks_without_door')) if wb_n else None, 'lower')
    # doors (doors_fit)
    rd, nd_ = rn.get('doors') or {}, nn.get('doors') or {}
    db_r, db_n = _doors_base(rn), _doors_base(nn)
    for k_ in ('end_gap_over_10mm', 'walls_in_opening', 'groups_with_off'):
        o.num(f'двери.{k_}', _num(rd.get(k_)) if db_r else None, _num(nd_.get(k_)) if db_n else None, 'lower')
    o.num('двери.в проёме', (rd.get('status') or {}).get('в проёме', 0) if db_r else None, (nd_.get('status') or {}).get('в проёме', 0) if db_n else None, 'higher')
    o.num('двери.мимо проёма', (rd.get('status') or {}).get('мимо проёма', 0) if db_r else None, (nd_.get('status') or {}).get('мимо проёма', 0) if db_n else None, 'lower')
    rf, nf = rn.get('furniture') or {}, nn.get('furniture') or {}
    o.num('мебель.номера на столах', _num(rf.get('numbers_on_desks')) if _num(rf.get('desks')) else None,
          _num(nf.get('numbers_on_desks')) if _num(nf.get('desks')) else None, 'higher')
    for path, a, b in (('двери.число', rd.get('n'), nd_.get('n')), ('двери.служебные', rd.get('service'), nd_.get('service'))):
        if a != b: o.changes.append(f'{path}: эталон {DASH if a is None else a} → {DASH if b is None else b} (проверить)')
    ra, na = rn.get('objects_by_key') or {}, nn.get('objects_by_key') or {}
    for key in sorted(set(ra) | set(na)):
        a, b = ra.get(key, 0), na.get(key, 0)
        if a != b: o.changes.append(f'объекты.{key}: эталон {a} → {b} (проверить)')
    # the checks: hanging lines; furniture without a type (lower is better)
    o.num('проверки.hanging_lines.n', _num(_get(rn, 'checks_tail', 'hanging_lines', 'n')), _num(_get(nn, 'checks_tail', 'hanging_lines', 'n')), 'lower')
    def untyped(n):
        if not _num(_get(n, 'furniture', 'desks')) and not (n.get('objects_by_key') or {}): return None
        lr = _get(n, 'checks_tail', 'furniture', 'left_for_review')
        if isinstance(lr, dict): return sum(v for v in lr.values() if isinstance(v, (int, float)))
        if isinstance(lr, list): return len(lr)
        return _num(lr)
    o.num('мебель.без типа', untyped(rn), untyped(nn), 'lower')
    # the stops of the ocg gate (new with code 012; a reference of v010 has none of them - «—»)
    ro, no = rn.get('ocg') or {}, nn.get('ocg') or {}
    for label, k_ in LOWER_OCG: o.num(f'шлюз ocg.{label}', _num(ro.get(k_)), _num(no.get(k_)), 'lower')
    # geometry: walls by class
    def line_walls(cls, a, b):
        v = iou(a, b)
        if v is None: o.dash.append(f'стены {cls}: {DASH}'); return
        diff = a.symmetric_difference(b); big = [q for q in getattr(diff, 'geoms', [diff]) if q.geom_type == 'Polygon' and q.area * K * K / 1e6 > 0.05]
        line = f'стены {cls}: IoU {v:.4f}, мест с разницей > 0,05 м² — {len(big)}' + (': ' + '; '.join(f'{_rnd(q.centroid.coords[0])} {round(q.area * K * K / 1e6, 2)} м²' for q in big[:8]) if big else '')
        (o.regress if v < 0.98 else o.changes if big else o.same).append(line)
    for cls in sorted(set(c for c, _ in RG.get('walls', [])) | set(c for c, _ in NG.get('walls', []))):
        line_walls(cls, _U([g for c, g in RG['walls'] if c == cls]), _U([g for c, g in NG.get('walls', []) if c == cls]))
    for nm_, a, b in (('стекло', RG.get('panes') or Polygon(), NG.get('panes') or Polygon()), ('блоки ядра', _U(RG.get('blocks', [])), _U(NG.get('blocks', [])))):
        v = iou(a, b)
        if v is None: o.dash.append(f'{nm_}: {DASH}'); continue
        # О-1 (check of step 11): none in the reference - «—» there, a change (IoU 0 made it a regression); none in the run - a regression
        if a.is_empty: o.changes.append(f'{nm_}: эталон {DASH} → {round(b.area * K * K / 1e6, 2)} м² (в эталоне нет — новые объекты)'); continue
        if b.is_empty: o.regress.append(f'{nm_}: эталон {round(a.area * K * K / 1e6, 2)} м² → {DASH} (в прогоне не на чем мерить)'); continue
        (o.regress if v < 0.98 else o.same if v > 0.999 else o.changes).append(f'{nm_}: IoU {v:.4f}')
    # doors
    if not RG.get('doors'):
        o.dash.append(f'двери эталона без пары: {DASH}')
    else:
        ndp = [(Polygon(d['ring']), d) for d in NG.get('doors', [])]; lost = []; moved = []
        base = lambda s: s.split(' (')[0].replace('служебная ', '')
        for d in RG['doors']:
            pa = Polygon(d['ring']); ca = pa.centroid
            cand = [(pb.centroid.distance(ca), pb, db) for pb, db in ndp if base(db['name']) == base(d['name'])]
            cand = [c_ for c_ in cand if c_[0] <= 0.5 / K * 1000]
            if not cand: lost.append(f"{d['name'][:40]} {_rnd(ca.coords[0])}"); continue
            _, pb, db = min(cand, key=lambda c_: c_[0])
            def wt(p):
                cs = np.array(p.exterior.coords)[:4]; a_, b_ = np.linalg.norm(cs[1] - cs[0]), np.linalg.norm(cs[2] - cs[1]); return max(a_, b_) * K, min(a_, b_) * K
            (wa, ta), (wb, tb) = wt(pa), wt(pb)
            if abs(wa - wb) > 10 or abs(ta - tb) > 10 or pa.symmetric_difference(pb).area * K * K > 0.02 * 1e6:
                moved.append(f"{d['name'][:40]} {_rnd(ca.coords[0])}: {round(wa)}×{round(ta)} → {round(wb)}×{round(tb)}")
        (o.regress if lost else o.same).append(f'двери эталона без пары: {len(lost)}' + (': ' + '; '.join(lost[:10]) if lost else ''))
        (o.changes if moved else o.same).append(f'двери с другим проёмом (> 10 мм): {len(moved)}' + (': ' + '; '.join(moved[:12]) if moved else ''))
    # furniture
    if not RG.get('furniture'):
        o.dash.append(f'мебель эталона без пары того же класса в 100 мм: {DASH}')
    else:
        byk = collections.defaultdict(list)
        for f in NG.get('furniture', []): byk[f['key']].append(f)
        fl = collections.Counter(); fm = []
        for f in RG['furniture']:
            cs_ = [g for g in byk.get(f['key'], []) if math.hypot(g['c'][0] - f['c'][0], g['c'][1] - f['c'][1]) * K <= 100]
            if not cs_: fl[f['key']] += 1; continue
            g = min(cs_, key=lambda g: math.hypot(g['c'][0] - f['c'][0], g['c'][1] - f['c'][1]))
            if f['area'] > 0 and abs(g['area'] - f['area']) > 0.10 * f['area']: fm.append(f"{f['name'][:30]} {_rnd(f['c'])}")
        (o.regress if sum(fl.values()) else o.same).append(f'мебель эталона без пары того же класса в 100 мм: {sum(fl.values())} {dict(fl)}')
        (o.changes if fm else o.same).append(f'мебель с площадью не в 10 %: {len(fm)}' + (': ' + '; '.join(fm[:10]) if fm else ''))
    # passages
    a, b = _U(RG.get('passage', [])), _U(NG.get('passage', []))
    v = iou(a, b)
    if v is None: o.dash.append(f'проходы: {DASH}')
    elif a.is_empty: o.changes.append(f'проходы: эталон {DASH} → {round(b.area * K * K / 1e6, 1)} м² (в эталоне проходов нет — новые объекты; О-1)')
    elif b.is_empty: o.regress.append(f'проходы: эталон {round(a.area * K * K / 1e6, 1)} м² → {DASH} (в прогоне не на чем мерить)')
    else:
        ar = (b.area / a.area - 1) if a.area else 0
        (o.regress if v < 0.90 or abs(ar) > 0.05 else o.same if v > 0.999 else o.changes).append(f'проходы: IoU {v:.3f}, площадь {ar * 100:+.1f} %')
    # ПЗ-1…ПЗ-9 by unique places, ПЗ-6, the sample room, the points of the DXF
    rq, nq = rn.get('qa') or {}, nn.get('qa') or {}
    for tag in sorted(set(rq) | set(nq)):
        if tag not in nq: o.regress.append(f'{tag}: в прогоне нет проверок ПЗ'); continue
        if tag not in rq: o.changes.append(f'{tag}: в эталоне нет проверок ПЗ — новый результат'); continue
        a_q, b_q = rq[tag], nq[tag]; a_u, b_u = a_q.get('уникальные места', {}), b_q.get('уникальные места', {})
        for chk in sorted(set(a_u) | set(b_u)):
            ba, bb = _qa_base(a_q, chk), _qa_base(b_q, chk)
            for kind in sorted(set(a_u.get(chk, {})) | set(b_u.get(chk, {}))):
                o.num(f'{tag}.{chk}.{kind}', a_u.get(chk, {}).get(kind, 0) if ba else None, b_u.get(chk, {}).get(kind, 0) if bb else None, 'lower')
        k6 = 'ПЗ-6 дуга двери пунктиром'
        arcs = lambda q: (q.get(k6) or {}).get('door arcs', 0) or None          # О-1: no door arcs at all - «—»
        o.num(f'{tag}.ПЗ-6 дуги дверей пунктиром', arcs(a_q), arcs(b_q), 'higher')
        (na_, va), (nb_, vb) = _sample(a_q), _sample(b_q)
        o.num(f'{tag}.ПЗ-8 «{na_ or nb_ or "образец"}», точек', va, vb, 'lower')
        a, b = a_q.get('всего точек'), b_q.get('всего точек')
        if a and b and b != a:
            (o.regress if b > a * 1.05 else o.changes).append(f'{tag}.точек в DXF: эталон {a} → {b} ({(b / a - 1) * 100:+.1f} %; больше +5 % — регресс)')
        elif a and b: o.same.append(f'{tag}.точек в DXF: {b}')
        else: o.num(f'{tag}.точек в DXF', a or None, b or None, 'lower')
    # rooms
    rr, nr = RG.get('rooms', []), NG.get('rooms', [])
    if not rr:
        o.dash.append(f'помещения эталона без пары (IoU ≥ 0,95): {DASH}')
        if nr: o.changes.append(f'помещения.число: эталон {DASH} → {len(nr)} (в эталоне помещений нет)')
    else:
        lost_r, more_pts = [], []
        for r in rr:
            best = max(((iou(r['poly'], q['poly']) or 0.0, q) for q in nr), key=lambda x: x[0], default=(0.0, None))
            if best[0] < 0.95:
                lost_r.append(f"{r['number'] or r['kind']} {_rnd(r['poly'].representative_point().coords[0])} IoU {best[0]:.2f}"); continue
            if (best[1].get('points') or 0) > (r.get('points') or 0): more_pts.append(f"{r['number'] or r['kind']}: {r['points']} → {best[1]['points']}")
        (o.regress if lost_r else o.same).append(f'помещения эталона без пары (IoU ≥ 0,95): {len(lost_r)}' + (': ' + '; '.join(lost_r[:10]) if lost_r else ''))
        (o.changes if more_pts else o.same).append(f'помещения с бо́льшим числом точек: {len(more_pts)}' + (': ' + '; '.join(more_pts[:10]) if more_pts else ''))
        if len(rr) != len(nr): o.changes.append(f'помещения.число: эталон {len(rr)} → {len(nr)} (проверить)')
    # ПЗ-10: the габаритный result against the подробный one
    ra, na = rn.get('pz10_outline_vs_detailed') or {}, nn.get('pz10_outline_vs_detailed') or {}
    for g in sorted(set(ra) | set(na)):
        if g in ('3', '5'): continue                    # groups 3 and 5 differ by design (furniture, sanitary: outlines only)
        a, b = (ra.get(g) or {}).get('n', 0), (na.get(g) or {}).get('n', 0)
        if g in ('2', '4', '6', '7', '8'): o.num(f'ПЗ-10 группа {g}: отличий габаритного от подробного', a, b, 'lower')
        elif a != b: o.changes.append(f"ПЗ-10 группа {g}: отличий габаритного от подробного эталон {a} {(ra.get(g) or {}).get('by_type')} → {b} {(na.get(g) or {}).get('by_type')} (проверить)")
        else: o.same.append(f'ПЗ-10 группа {g}: {b}')
    return o


def _qa_base(q, chk):
    """О-1: does the check have objects to work on in this result? (the new 'база' record; a v010 result - from its counts)"""
    b = q.get('база')
    if chk == 'ПЗ-8':
        n = b.get('rooms') if b else (q.get('ПЗ-8 помещения') or {}).get('rooms', 0)
    elif chk == 'ПЗ-9':
        n = b.get('passages') if b else (q.get('ПЗ-9 проходы') or {}).get('passages', 0)
    elif chk == 'ПЗ-6':
        n = b.get('door_arcs') if b else (q.get('ПЗ-6 дуга двери пунктиром') or {}).get('door arcs', 0)
    elif chk == 'ПЗ-7':
        n = b.get('massive', 1) if b else 1
    else:
        n = b.get('contours', 1) if b else 1
    return bool(n)


def _sample(q):
    """(name, points) of the owner's sample room: the code-012 record or the v010 key «ПЗ-8 образец «<имя>» (точек, ждём N)»"""
    if 'ПЗ-8 образец помещения (точек)' in q: return q.get('ПЗ-8 образец помещения — имя'), _num(q['ПЗ-8 образец помещения (точек)'])
    for k, v in q.items():
        m = re.match(r'ПЗ-8 образец «(.+?)»', k)
        if m: return m.group(1), _num(v)
    return None, None


def result(o, head):
    """the result dict of a check: head (reference, files, measures versions, run) + verdict + lists"""
    verdict = 'ПРОЙДЕНО' if not o.regress else 'НЕ ПРОЙДЕНО'
    return dict(head, verdict=verdict, counts=dict(regressions=len(o.regress), changes=len(o.changes), same=len(o.same), dash=len(o.dash)),
                regressions=o.regress, changes=o.changes, same=o.same, dash=o.dash)


def print_result(res):
    h = res.get('measures') or {}
    print(f"меры: код {h.get('code')} | эталон {h.get('reference')} | прогон {h.get('run')}" + ('' if h.get('same') else ' — РАЗНЫЕ ВЕРСИИ МЕР (О-1)'))
    am = res.get('allowed_missing')                   # check of step 11: a lifted stop is said in the head
    if am: print(f"  СНЯТ СТОП OCG_REF_ALLOW_MISSING: нет отчётов — прогон {am.get('run')}, эталон {am.get('reference')}: их меры «—»")
    print(res['verdict'], '| регрессий', len(res['regressions']), '| изменений', len(res['changes']), '| без изменений', len(res['same']), f'| «{DASH}»', len(res['dash']))
    for x in res['regressions']: print('  РЕГРЕСС:', x)
    for x in res['changes']: print('  изменение:', x)
