# ocg/gate_ocg.py - code 009 (package 3): the acceptance gate of the layer route, the last step of ocg/run_ocg.sh.
#   Exit 1 - the floor is not to be delivered: the stops are printed and written to ocg_gate.json (plan/rules/60 §8).
#   The checks are requirements to the result of any route (plan/rules/70, rule 30; plan/rules/60 §4): they are counted on
#   the final bodies and objects (ocg_checks.json, ocg_wallcls.json) and on both DXF (ocg_layers_*.json, ocg_compose.json).
#
#   Stop | what | report | threshold
#   O0   | a check failed or wrote no report (not accepted)                       | checks_failed.txt, reports | 0
#   O1   | 3.1: a vertex on a straight run of a wall outline without a reason     | ocg_checks.json walls.straight_run_reasons['прочее'] | 0
#   O2   | 3.3: a void in a wall (a hole < 10 pt² or thinner than the wall)       | walls.holes.voids | 0
#   O3   | 3.3: a break - two bodies <= 3 pt apart, no door, opening or glass     | walls.breaks_without_door | 0
#   O4   | 3.4: an overlap or a gap of two bodies at a joint after Э7с            | joints.after.bodies | 0
#   O5   | an irregularity: a short edge (< 0.8 of the wall) not justified        | walls.short_edges.by_reason[…не оправдан…] | 0
#   O6   | ТП3: a line of a wall layer along a body, not in the body's class      | ocg_wallcls.json | 0
#   O7   | a wall as lines, not a polygon, outside the core blocks                | walls_as_lines_outside_core | 0
#   O8   | a door without the opening of the scheme (Т8-15); a hinge > 150 mm     | doors_no_opening; doors_check.json | 0
#   O9   | the composition of a DXF differs from the checked result (cfg.OCG_REF_DXF, OCG_REF_DXF_OUTLINE) | ocg_compose.json | 0
#   O10  | (code 011) an end of a door opening off the face of a wall or glass: > 0.3 pt at 48.04 mm/pt (14 mm), sheet.pt()
#        | from every wall body, glass pane and core block - a gap between the door and the wall (ПК4-П13) | door_ends | 0
#   S14* | a DXF layer without a record or a description, a text off …T-/…D- (not accepted; plan/rules/50 §1) | ocg_layers_*.json | 0
#   Lists (do not stop): hanging lines, irregularities left for review (Э6в), glass ends at another angle, furniture without a type.
#   Accept a stop - cfg.OCG_GATE_ACCEPT = {'O3': dict(max=N, why='…')}: as GATE_ACCEPT, the reason is one of the four kinds
#   with its link (checks/accept.py); a number above max stops again. O0 and S14* are not accepted.
#   Check of step 11: O0 also when ocg_checks.json lacks a record the stops read (no silent 0); the stops of the start lifted
#   by OCG_ROLE_OK, OCG_ORIGIN_OK, OCG_SCALE_OK (notes of ocg_start*.json) - lines «принято старт» and info.start_lifted.
import os, sys, json
_O = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, _O); sys.path.insert(0, os.path.join(os.path.dirname(_O), 'checks'))
import sheet
from accept import why_kind            # checks/accept.py: the closed list of reasons (plan/rules/60 §8)

ACC = getattr(sheet.cfg, 'OCG_GATE_ACCEPT', {}) or {}
NO_ACCEPT = {'O0', 'S14*'}
stops = []; lists = {}; info = {}


def ld(f):
    try: return json.load(open(f))
    except Exception: return None


def stop(code, n, what, places=None):
    if n <= 0: return
    a = ACC.get(code)
    if a and code not in NO_ACCEPT:
        k, miss = why_kind(a.get('why'))
        if k and n <= int(a.get('max', -1)):
            stops.append(dict(code=code, n=n, what=what, accepted=True, kind=k, why=a.get('why'), places=(places or [])[:20])); return
        what = what + (f' — OCG_GATE_ACCEPT не принят: {miss}' if not k else f' — OCG_GATE_ACCEPT: принято не больше {a.get("max")}')
    stops.append(dict(code=code, n=n, what=what, accepted=False, places=(places or [])[:20]))


failed = [l.strip() for l in open('checks_failed.txt')] if os.path.exists('checks_failed.txt') else []
need = {'checks': 'ocg_checks.json', 'doors': 'doors_check.json', 'layers': 'ocg_layers_detail.json', 'layers2': 'ocg_layers_outline.json',
        'wallcls': 'ocg_wallcls.json', 'compose': 'ocg_compose.json'}
miss = [f for s, f in need.items() if ld(f) is None]
stop('O0', len(failed) + len(miss), f'проверка упала или не написала отчёт: упали {failed}, нет отчёта {miss} (не принимается)')
C = ld('ocg_checks.json') or {}
# check of step 11 (code 012): a report without the records the stops below read is no report - O0, as door_ends (code 011),
#   not a silent 0 of O1-O5, O7, O8 (.get(…, 0) of a record that is not there)
if C:
    _lost = [k for k in ('walls', 'walls_as_lines_outside_core', 'doors_no_opening') if not isinstance(C.get(k), dict)]
    if isinstance(C.get('walls'), dict):
        _lost += [f'walls.{k}' for k in ('straight_run_reasons', 'holes', 'short_edges', 'breaks_without_door') if not isinstance(C['walls'].get(k), dict)]
    if not isinstance(C.get('joints_final'), dict) and not isinstance(((C.get('joints') or {}).get('after') or {}).get('bodies'), dict):
        _lost.append('joints_final / joints.after.bodies')
    stop('O0', len(_lost), f'ocg_checks.json без записей, которые читают остановки: {_lost} — проверка не отработала, нули не ставятся (не принимается)')
w = C.get('walls', {})
r31 = (w.get('straight_run_reasons') or {}).get('прочее', 0)
stop('O1', r31, '3.1: вершина на прямом участке контура стены без причины (узел стыка, узкое место) (plan/rules/60 §4)',
     (w.get('straight_run_places') or {}).get('прочее'))
ho = w.get('holes') or {}
stop('O2', ho.get('voids', 0), '3.3: пустота в стене — дыра тела < 10 pt² или уже стены (Т8-12)',
     [h for h in ho.get('places', []) if h.get('what') == 'пустота в стене'])
br = w.get('breaks_without_door') or {}
stop('O3', br.get('n', 0), '3.3: разрыв — два тела ближе 3 pt без двери, проёма и стекла между ними (plan/rules/60 §4)', br.get('places'))
jf = C.get('joints_final')                       # measured by checks_ocg.py on the bodies the DXF draws; else the report of Э7с
jb = (jf or {}).get('bodies') if jf else (((C.get('joints') or {}).get('after') or {}).get('bodies') or {})
stop('O4', sum(jb.values()), f'3.4: нахлёст или щель двух тел на стыке (итоговые тела): {jb} (Т8-12)', (jf or {}).get('places'))
se = (w.get('short_edges') or {})
nj = sum(v for k, v in (se.get('by_reason') or {}).items() if 'не оправдан' in k)
stop('O5', nj, f'неровность: короткое ребро (< 0,8 толщины стены) без оправдания — ступенька или прочее: {se.get("by_reason")} (Т8-11, Т8-12)',
     se.get('not_justified'))
WC = ld('ocg_wallcls.json') or {}
stop('O6', WC.get('n', 0), f'ТП3: линия слоя стен вдоль тела стены не в классе этого тела: {WC.get("by_key")}, {WC.get("length_m")} м', WC.get('places'))
wl = C.get('walls_as_lines_outside_core') or {}
stop('O7', wl.get('n', 0), f'стена линиями, а не полигоном, вне блоков ядра: {wl.get("by_key")}, {wl.get("length_m")} м (Т8-18; тест 8 §2)', wl.get('places'))
dn = C.get('doors_no_opening') or {}
DC = ld('doors_check.json') or {}
stop('O8', dn.get('n', 0) + len(DC.get('bad', [])), f'дверь без проёма схемы «проём — полотно — дуга» {dn.get("n", 0)} (Т8-15); '
     f'петля дальше 150 мм от носителя {len(DC.get("bad", []))} (plan/rules/60 §1)', (dn.get('places') or []) + DC.get('bad', []))
de = C.get('door_ends')
if de is None: stop('O0', 1, 'ocg_checks.json без door_ends — проверка концов проёмов не отработала (код 011; не принимается)')
else: stop('O10', de.get('off_face', 0), f'конец проёма двери не на грани стены или стекла: дальше {de.get("tol_mm")} мм (0,3 pt при 48,04 мм/pt) '
           f'от тел стен, стекла и блоков ядра — щель между дверью и стеной (ПК4-П13; №105; plan/rules/40 §5, п. 15); концов {de.get("ends")}',
           de.get('places'))
CP = ld('ocg_compose.json') or {}
for r in CP.get('checked', []):
    if not r.get('same'):
        stop('O9', max(1, r.get('only_ref', 0) + r.get('only_new', 0)), f'состав DXF не тот, что у проверенного итога ({r["field"]}): '
             f'объектов {r.get("top_total")}, по слою и типу {list((r.get("top_diff") or {}).items())[:6]}, только в эталоне {r.get("only_ref")}, '
             f'только в новом {r.get("only_new")} (plan/00, шаг 9)', r.get('examples'))
info['compose'] = dict(checked=[r.get('field') for r in CP.get('checked', [])], skipped=CP.get('skipped'))
for f in ('ocg_layers_detail.json', 'ocg_layers_outline.json'):
    L = ld(f) or {}
    n = len(L.get('no_record') or {}) + len(L.get('no_description') or {}) + sum((L.get('texts_off_TD') or {}).values())
    stop('S14*', n, f'{f}: слой DXF без записи {L.get("no_record")} или без описания {L.get("no_description")}, тексты не на …T-/…D- '
         f'{L.get("texts_off_TD")} (plan/rules/50 §1; не принимается)')
lists['висящие линии'] = (C.get('hanging_lines') or {}).get('n')
lists['ядро: висящие линии'] = (C.get('core') or {}).get('hanging_lines')
irr = (w.get('irregularities_e6c') or {})
lists['неровности: оставлены на перепроверку (Э6в)'] = sum(v for k, v in irr.items() if 'перепроверк' in k)
pa = ((C.get('joints') or {}).get('after') or {}).get('panes') or {}
lists['торцы стекла под другим углом'] = sum(v for k, v in pa.items() if 'другой угол' in k)
fu = C.get('furniture') or {}
_lr = fu.get('left_for_review')
lists['мебель без типа'] = sum(v for v in _lr.values() if isinstance(v, (int, float))) if isinstance(_lr, dict) else (len(_lr) if isinstance(_lr, list) else _lr)
info['walls'] = dict(bodies=w.get('bodies'), vertices=w.get('vertices'), straight_run=w.get('straight_run_reasons'))
# check of step 11 (code 012): the stops of ocg/start_ocg.py lifted by a field of cfg (OCG_ROLE_OK, OCG_ORIGIN_OK, OCG_SCALE_OK) are
#   written by the start as notes only - the gate repeats them, so the report of the floor shows every lifted stop (as accepted ones)
info['start_lifted'] = [n for f in ('ocg_start.json', 'ocg_start_e3.json') for n in ((ld(f) or {}).get('notes') or [])
                        if any(k in n for k in ('cfg.OCG_ROLE_OK', 'cfg.OCG_ORIGIN_OK', 'cfg.OCG_SCALE_OK'))]
hard = [s for s in stops if not s['accepted']]
res = dict(ok=not hard, stops=stops, lists=lists, info=info)
json.dump(res, open('ocg_gate.json', 'w'), ensure_ascii=False, indent=1, default=str)
for s in stops:
    print(f"  {'принято' if s['accepted'] else 'СТОП':8s} {s['code']:5s} {s['n']:6d}  {s['what'][:230]}" + (f" | почему: {s['why'][:200]}" if s['accepted'] else ''))
for n_ in info['start_lifted']: print(f"  {'принято':8s} старт  снято полем cfg: {n_[:300]}")
print('  на просмотр:', ' | '.join(f'{k} {v}' for k, v in lists.items()))
print('GATE OCG', 'пройден' if not hard else 'STOP — сдача запрещена', f'(остановок {len(hard)}, принято {len(stops) - len(hard)})')
sys.exit(0 if not hard else 1)
