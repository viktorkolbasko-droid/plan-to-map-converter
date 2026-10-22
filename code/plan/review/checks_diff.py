# Summary of the checks of a run against a base folder (json files), for the review loop.
#   python3 checks_diff.py base_dir run_dir
import sys, json, os
b, r = sys.argv[1], sys.argv[2]
def L(d, f):
    try: return json.load(open(os.path.join(d, f)))
    except Exception: return {}
v0, v1 = L(b, 'verify.json'), L(r, 'verify.json')
for k in ('wall_parts_after_union', 'doors_total', 'doors_with_both_jambs_on_carrier', 'wall_gaps_lt_1100mm', 'wall_gaps_unexplained', 'facade_covered_share', 'classified_share', 'coverage', 'chairs_office', 'desk_places', 'dxf_audit_errors', 'unwalled_xv_strokes', 'unwalled_cap_hatch_strokes', 'facade_ends_to_wall_mm'):
    print(f'verify.{k}:', json.dumps(v0.get(k), ensure_ascii=False)[:160], '->', json.dumps(v1.get(k), ensure_ascii=False)[:160])
for f in ('ink.json', 'ink_strict.json'):
    a, c = L(b, f), L(r, f)
    print(f, 'missing', a.get('missing_pt2'), '->', c.get('missing_pt2'), '| extra', a.get('extra_pt2'), '->', c.get('extra_pt2'), '| components', len(a.get('missing', [])), len(a.get('extra', [])), '->', len(c.get('missing', [])), len(c.get('extra', [])))
f0, f1 = L(b, 'fidelity.json'), L(r, 'fidelity.json'); print('fidelity', f0, '->', f1)
g0, g1 = L(b, 'geomqa.json'), L(r, 'geomqa.json')
for k in ('wall_gaps_unexplained_by_source', 'doors', 'doors_closed_gap_gt_20mm', 'doors_hinge_gap_gt_20mm', 'doors_overlap_gt_20mm', 'facade_ends_glass_gap_gt_20mm', 'wall_class_overlaps', 'near_axis_real_unjustified', 'wall_hatch_continuation_strokes'):
    print(f'geomqa.{k}:', json.dumps(g0.get(k), ensure_ascii=False)[:200], '->', json.dumps(g1.get(k), ensure_ascii=False)[:200])
for f in ('boxcut.json', 'arcs_audit.json', 'wall_evidence.json'):
    a, c = L(b, f), L(r, f)
    print(f, {k: a.get(k) for k in ('cut_by_boxes', 'sheet_by_length_inside', 'bands', 'hatched', 'below', 'empty', 'empty_m2') if k in a}, '->', {k: c.get(k) for k in ('cut_by_boxes', 'sheet_by_length_inside', 'bands', 'hatched', 'below', 'empty', 'empty_m2') if k in c})
c0, c1 = L(b, 'class_params.json'), L(r, 'class_params.json')
print('class_params.violations', c0.get('violations'), '->', c1.get('violations'), '| partition lines on fills', c0.get('partition_lines_on_coloured_fills_m'), '->', c1.get('partition_lines_on_coloured_fills_m'))
for k, v in c1.get('per_class', {}).items():
    if v['out'] or v['open'] or v['coloured']: print('   ', k, {a: v[a] for a in ('n', 'out', 'open', 'coloured')}, [(s['at_pt'], s['why']) for s in v['samples']][:8])
m0, m1 = L(b, 'misc_inventory.json'), L(r, 'misc_inventory.json'); print('misc objects', m0.get('objects'), '->', m1.get('objects'), '| groups', m0.get('groups'), '->', m1.get('groups'))
r0, r1 = L(b, 'reclass.json'), L(r, 'reclass.json'); print('reclass misc left', r0.get('misc_left'), r0.get('misc_prims_left'), '->', r1.get('misc_left'), r1.get('misc_prims_left'))
e0, e1 = L(b, 'ends_audit.json'), L(r, 'ends_audit.json')
print('ends_audit keys', list(e1.keys())[:12])
for k in ('summary', 'by_kind', 'counts'):
    if k in e1: print('ends', k, json.dumps(e0.get(k), ensure_ascii=False)[:300], '->', json.dumps(e1.get(k), ensure_ascii=False)[:300])
ro0, ro1 = L(b, 'rooms.json'), L(r, 'rooms.json')
for k in ('n_open_ends', 'open_ends_by_kind', 'tags_not_in_a_closed_room', 'rooms_with_several_tags', 'along_offset_gt_20mm'):
    print(f'rooms.{k}:', json.dumps(ro0.get(k), ensure_ascii=False)[:200], '->', json.dumps(ro1.get(k), ensure_ascii=False)[:200])
