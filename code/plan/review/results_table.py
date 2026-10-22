# tables for the pass report and plan/rules/60: acceptance, geometry checks (3.1-3.4), room boundaries (3.6)
import json, os, pickle
from shapely.ops import unary_union
W = os.environ.get('WORK', os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'work'))   # floor folders
S = os.environ.get('SNAP', '.')                                   # folder with the snapshots of the previous delivery
floors = [('1', 'f1'), ('2', 'f2'), ('3', 'f3b'), ('4', 'f4r'), ('5', 'f5r'), ('6', 'f6')]
def c(x): return str(x).replace('.', ',')
def area(p):
    Wd = pickle.load(open(p, 'rb'))['W']; return unary_union([g for v in Wd.values() for g in v]).area / 1e6
A = ["| Этаж | Стены, м² (сдано 28.09 утром) | Двери: косяки / всего | Фасад покрыт | Классифицировано | Контур на линиях PDF, p95 мм | Чернила: обычный | строгий |", "|---|---|---|---|---|---|---|---|"]
G = ["| Этаж | Вершин стен: до → после | Линий в блоках: до → после | Рёбра у оси: шум / видимые (кривые + косые исходника) | Разрывы без объяснения: проём / контур / смотреть | Продолжение штриховки: кластеров (не просмотрено) / штрихов | Двери: зазор > 20 мм / заход > 70 мм | Стекло не дошло до носителя > 20 мм | Наложения классов |",
     "|---|---|---|---|---|---|---|---|---|"]
Rm = ["| Этаж | Разделителей: штрихов → линий | Концов: замкнуто / почти (≤ 160 мм) / у объекта / вдоль стены / открыто | Вдоль стен ≥ 1 м: участков, отступ от грани (медиана), мм | Помещений | Марок: вне помещения / две в одном |", "|---|---|---|---|---|---|"]
for n, f in floors:
    d = os.path.join(W, f)
    R = json.load(open(d + '/verify.json')); F = json.load(open(d + '/fidelity.json'))
    ik = json.load(open(d + '/ink.json')); iks = json.load(open(d + '/ink_strict.json'))
    q = json.load(open(d + '/geomqa.json')); g = json.load(open(d + '/geomfix.json'))
    wa = area(d + '/walls.pkl'); wp = area(f'{S}/prev_{f}/walls.pkl') if os.path.exists(f'{S}/prev_{f}/walls.pkl') else None
    A.append(f"| {n} | {c(round(wa, 1))} ({c(round(wp, 1)) if wp else '—'}) | {R['doors_with_both_jambs_on_carrier']} / {R['doors_total']} | {c(R['facade_covered_share'])} | {c(R['classified_share'])} | {c(F['share_len_on_source_lines'])}, {c(F['p95_mm'])} | {len(ik['missing'])} / {len(ik['extra'])} | {len(iks['missing'])} / {len(iks['extra'])} |")
    we = q['wall_edges']; dd = q['doors_detail']; rk = q.get('near_axis_real_kinds', {})
    over70 = sum(1 for x in dd if x['overlap'] > 70); gap20 = sum(1 for x in dd if x['hinge_gap'] > 20 or (x['closed_gap'] > 20 and not x['pair']))
    bs = q.get('wall_gaps_unexplained_by_source', {})
    gaps = f"{bs.get('opening (nothing drawn)', 0)} / {bs.get('outline wall', 0)} / {bs.get('lines - look', 0)}"
    fe = len(q.get('facade_ends_glass_gap_gt_20mm', []))
    G.append(f"| {n} | {g['walls']['ring_vertices_before']} → {g['walls']['ring_vertices_after']} | {g['blocks'].get('lines_in')} → {g['blocks'].get('lines_out')} | {we.get('near_axis_snap', 0)} / {we.get('near_axis_real', 0)} ({rk.get('curve', 0)} + {rk.get('straight, drawn so in the source', 0)}; без объяснения {len(q.get('near_axis_real_unjustified', []))}) | {gaps} | {len(q['wall_hatch_continuation'])} ({q.get('wall_hatch_continuation_not_reviewed', '?')}) / {q['wall_hatch_continuation_strokes']} | {gap20} / {over70} | {fe} из {len(q.get('facade_ends', []))} | {len(q['wall_class_overlaps'])} |")
    if os.path.exists(d + '/rooms.json'):
        r = json.load(open(d + '/rooms.json'))
        if r.get('separation_prims'):
            k = r.get('open_ends_by_kind', {}); tot = 2 * r['separation_lines']
            al = sorted(r.get('along_walls_long', []), key=lambda a: -a['length_mm'])
            als = ', '.join(f"{c(round(a['length_mm'] / 1000, 1))} м — {a['offset_mm_median']}" for a in al) if al else '—'
            Rm.append(f"| {n} | {r['separation_prims']} → {r['separation_lines']} | {tot - r['n_open_ends']} / {k.get('almost', 0)} / {k.get('object', 0)} / {k.get('along', 0)} / {k.get('open', 0)} | {len(al)}: {als} | {r['rooms']} | {len(r['tags_not_in_a_closed_room'])} / {len(r['rooms_with_several_tags'])} |")
        else: Rm.append(f"| {n} | нет в исходнике | — | — | — | — |")
print('\n'.join(A)); print(); print('\n'.join(G)); print(); print('\n'.join(Rm))
