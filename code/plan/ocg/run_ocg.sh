#!/bin/bash
# ocg/run_ocg.sh - code 009 (package 3): the layer route of the engineering plan - an AutoCAD sheet with OCG layers
#   (plan/00, step 1; owner's decision of 03.10.2026, rows 148-149). run.sh hands such a sheet over here (sheetcheck.py exit 4);
#   run in the floor folder that holds cfg.py (with the sheet's layer table OCG_LAYERS) and the PDF:
#     bash ../../code/run.sh            all: from the PDF (Э2 inventory, Э3 scale, Э5 extract) to DXF, SVG, checks, gate
#     bash ../../code/run.sh walls      from Э6 (prims.pkl of Э5 kept)
#     bash ../../code/run.sh joints     from Э7с (objects_f.pkl and prims_f.pkl of a full run kept: walls, doors, core changed)
#     bash ../../code/run.sh export     from Э7b (blocks, DXF, SVG, list of objects)
#     bash ../../code/run.sh gate       only the checks and the gate
#     bash ../../code/run.sh sheets     review sheets of a finished run into sheets/: problems with pictures, layer groups of both
#                                       results, the passage zone (post_t8.sh of the pass code)
#   Steps: Э2 e2_inventory -> Э3 e3_scale -> (scale and origin against cfg) -> Э5 e5_extract -> Э6 e6_walls -> Э6в e6c_clean ->
#   Э6г e6d_geom -> Э7 e7_objects -> Э7м e7f_furniture -> Э7м-б barrier_desk -> Э7с e7j_joints -> Э7д e7d_doors -> Э7я e7c_core ->
#   Э7о e7o_openings -> Э7к e7k_classes -> Э7р e7r_regular -> Э9з e9z_zones ->
#   detailed result (Э7b, Э8, SVG: out/) -> габаритный result (Э7b, Э8, SVG: out_outline/) -> Э10 list of objects ->
#   checks (measures 3.1-3.4 on the final bodies, doors, ТП3 class of wall lines, S14* layers of both DXF, composition against
#   cfg.OCG_REF_DXF; code 012: doors_fit - openings against the walls, a report) -> gate (ocg/gate_ocg.py: exit 1 - not to be
#   delivered; plan/rules/60 §8; plan/rules/70, rule 30).
#   Code 012 (stage 1 of the merge of v009): Э7о after Э7я - openings fitted to the walls (prims_o.pkl, walls_o.pkl - the
#   load_prims / load_walls chains read them first, so walls and joints reruns remove them with the other states).
#   Code 012 (stage 2, the merge of v010 - owner's remarks of 09.10.2026, З-1…З-24): after Э7о - Э7к e7k_classes (classes: facade
#   mullions, ПК, kitchens, stray lines, the reception, the owner's group of every object), Э7р e7r_regular (one wall - one type,
#   the face lines, the fewest points, massive furniture), Э9з e9z_zones instead of Э9 (rooms and passages as polygons: rooms.pkl,
#   passage.pkl; the DXF of the zones out/<OUT>_zones.dxf); prims_k.pkl, prims_r.pkl, walls_r.pkl - read first by the chains,
#   removed by the walls and joints reruns; objects_o.pkl, objects_k.pkl - the objects after Э7о and after Э7к (as v010).
#   Delivery - from a full run of one command (rule 30). Same step names in the logs as the pass code of test 8 (log_<step>.txt).
set -e
O=$(dirname "$(readlink -f "$0")"); C=$(dirname "$O"); export PYTHONPATH="$C"
# the order of sets of strings (layer names, keys) is fixed: a run repeats the order and the ids of objects of another run
#   (the geometry did not depend on it - test 8, two full runs; the ids in the reports did)
export PYTHONHASHSEED=0
# code 012 (#95 Р2, Р1): every step is journalled by runlog.py - before it the SHA-256 of its script and the modules it loads
#   (a file changed since the start of the run -> STOP, exit 3: the run is invalid), after it the hashes of the state files
#   and their contents in state/ (the reference is taken from the state at the export - ocg/make_reference.py)
J() { python3 $O/runlog.py "$@" >> log_runlog.txt 2>&1; }
t() { local s=$(date +%s); local n=$1; shift; J pre $n "$@" || { echo "STOP $n - Р2: код маршрута изменён во время прогона"; tail -5 log_runlog.txt; exit 3; }
      local rc=0; "$@" > log_$n.txt 2>&1 || rc=$?; J post $n $rc
      [ $rc = 0 ] || { echo "FAIL $n"; tail -20 log_$n.txt; exit 1; }; echo "$n $(( $(date +%s)-s ))s"; }
c() { local s=$(date +%s); local n=$1; shift; J pre $n "$@" || { echo "STOP $n - Р2: код маршрута изменён во время прогона"; tail -5 log_runlog.txt; exit 3; }
      local rc=0; "$@" > log_$n.txt 2>&1 || rc=$?; J post $n $rc
      if [ $rc = 0 ]; then echo "$n $(( $(date +%s)-s ))s"; else echo "FAIL $n - the gate stops (O0)"; echo "$n" >> checks_failed.txt; tail -5 log_$n.txt; fi; }
FROM=${1:-all}
case "$FROM" in all|walls|joints|export|gate|sheets) ;; *) echo "STOP: run.sh $FROM - the layer route knows all | walls | joints | export | gate | sheets"; exit 3;; esac
python3 $O/start_ocg.py > log_start_ocg.txt 2>&1 || { cat log_start_ocg.txt; echo "STOP ocg start - fix cfg.py (plan/rules/20 §3.8)"; exit 3; }
head -1 log_start_ocg.txt
OUTN=$(python3 -c "import sys; sys.path.insert(0, '$O'); import sheet; print(sheet.OUT)")
TITLE=$(python3 -c "import sys; sys.path.insert(0, '$O'); import sheet; print(sheet.TITLE)")
mkdir -p out out_outline
if [ "$FROM" = "sheets" ]; then
  mkdir -p sheets
  c sheets_problems python3 $O/sheets_problems.py sheets/problems ocg_checks.json
  c sheets_layers python3 $O/sheets_layers.py sheets
  VARIANT=outline c sheets_layers2 python3 $O/sheets_layers.py sheets
  c sheet_passage python3 $O/sheet_passage.py sheets/zona-prohoda.png 2
  echo "run.sh sheets done (ocg) $(date -u +%Y-%m-%dT%H:%M:%SZ)"; exit 0
fi
if [ "$FROM" = "all" ] || [ ! -s run_journal.json ]; then rm -rf state; python3 $O/runlog.py begin "$0" > log_runlog.txt 2>&1; fi   # Р2: a new journal
if [ "$FROM" = "all" ]; then
  mkdir -p inventory
  t e2 python3 $O/e2_inventory.py                # Э2: class table by OCG layer, render of every layer alone
  t e3 python3 $O/e3_scale.py                    # Э3: scale two ways, origin from the axes
  python3 $O/start_ocg.py --after-e3 > log_start_ocg_e3.txt 2>&1 || { cat log_start_ocg_e3.txt; echo "STOP scale/origin of Э3 against cfg"; exit 3; }
  t e5 python3 $O/e5_extract.py                  # Э5: primitives with their layer -> prims.pkl
fi
if [ "$FROM" = "all" ] || [ "$FROM" = "walls" ]; then
  [ -s prims.pkl ] || { echo "STOP walls: no prims.pkl of Э5 - run.sh (all) first"; exit 3; }
  rm -f prims_o.pkl walls_o.pkl prims_c.pkl prims_d.pkl prims_f.pkl prims_j.pkl walls_j.pkl objects.pkl objects_e7.pkl objects_f.pkl walls_e7.pkl walls_geom.pkl \
        prims_geom.pkl walls_clean.pkl prims_e7.pkl blocks.pkl blocks_outline.pkl prims_k.pkl prims_r.pkl walls_r.pkl objects_o.pkl objects_k.pkl rooms.pkl passage.pkl
  t e6 python3 $O/e6_walls.py                    # Э6: wall bodies by the layers of the walls
  t e6c python3 $O/e6c_clean.py                  # Э6в: irregularities thinner than the wall (Т8-11)
  t e6d python3 $O/e6d_geom.py                   # Э6г: niches and door openings
  t e7 python3 $O/e7_objects.py                  # Э7: objects by layer (cfg.OCG_LAYERS roles)
  t e7f python3 $O/e7f_furniture.py              # Э7м: furniture v3 - types, one figure, габарит outlines
  t e7fb python3 $O/barrier_desk.py              # Э7м-б (012, СО-2): barrier strips of the wall layers -> the desk they touch
  cp -p objects.pkl objects_f.pkl                # the state after Э7м, for run.sh joints
fi
if [ "$FROM" = "joints" ]; then
  [ -s objects_f.pkl ] && [ -s prims_f.pkl ] || { echo "STOP joints: no objects_f.pkl / prims_f.pkl of a full run"; exit 3; }
  rm -f prims_o.pkl walls_o.pkl prims_c.pkl prims_d.pkl prims_j.pkl walls_j.pkl blocks.pkl blocks_outline.pkl prims_k.pkl prims_r.pkl walls_r.pkl \
        objects_o.pkl objects_k.pkl rooms.pkl passage.pkl; cp -p objects_f.pkl objects.pkl
fi
if [ "$FROM" = "all" ] || [ "$FROM" = "walls" ] || [ "$FROM" = "joints" ]; then
  t e7j python3 $O/e7j_joints.py                 # Э7с: joints, voids, steps, overlaps (Т8-12, Т8-13)
  t e7d python3 $O/e7d_doors.py                  # Э7д: doors - opening, leaf, arc (Т8-15)
  t e7c python3 $O/e7c_core.py                   # Э7я: core blocks - closed polygons (Т8-14)
  t e7o python3 $O/e7o_openings.py               # Э7о: openings fitted to the walls, service doors (Т10-1…Т10-3; code 012)
  cp -p objects.pkl objects_o.pkl                # the objects after Э7о (v010: for a rerun from Э7к)
  t e7k python3 $O/e7k_classes.py                # Э7к: facade mullions, ПК, kitchens, stray lines, reception, groups (З-5, З-10…З-13; code 012)
  cp -p objects.pkl objects_k.pkl                # the objects after Э7к
  t e7r python3 $O/e7r_regular.py                # Э7р: one wall - one type, face lines, the fewest points (З-1…З-4, З-8, З-9; code 012)
  t e9z python3 $O/e9z_zones.py                  # Э9з: rooms and passages as polygons (З-14…З-23; code 012, instead of Э9)
fi
if [ "$FROM" != "gate" ]; then
  t e7b python3 $O/e7_blocks.py                                   # blocks of the detailed result
  OUTDIR=out t e8 python3 $O/e8_export.py                         # DXF of the detailed result
  t e8s python3 $O/e8s_svg.py out/${OUTN}_engineering.dxf out/${OUTN}_engineering.svg "$TITLE"
  VARIANT=outline t e7b2 python3 $O/e7_blocks.py                  # blocks of the габаритный result (Т8-1)
  VARIANT=outline OUTDIR=out_outline t e82 python3 $O/e8_export.py
  t e8s2 python3 $O/e8s_svg.py out_outline/${OUTN}_outline.dxf out_outline/${OUTN}_outline.svg "$TITLE — габаритный результат"
  OUTDIR=out_outline t e10 python3 $O/e10_objects_list.py         # Э10: list of objects for replacement
fi
# checks write their reports anew; a check that fails stops the gate (O0), it does not cancel the checks after it
rm -f checks_failed.txt ocg_checks.json doors_check.json doors_fit.json ocg_layers_detail.json ocg_layers_outline.json ocg_wallcls.json ocg_compose.json ocg_gate.json
c checks python3 $O/checks_ocg.py ocg_checks.json                              # measures 3.1-3.4 on the final bodies (plan/rules/60 §4)
c doors python3 $O/doors_check.py                                              # hinge <= 150 mm from a carrier (plan/rules/60 §1)
c doors_fit python3 $O/doors_fit.py doors_fit.json                             # code 012 (Т10-2): openings against the walls, ends, groups - a report
c layers python3 $O/layers_ocg.py out/${OUTN}_engineering.dxf ocg_layers_detail.json      # S14*: layers and texts of the DXF
c layers2 python3 $O/layers_ocg.py out_outline/${OUTN}_outline.dxf ocg_layers_outline.json
c wallcls python3 $O/wallcls_ocg.py ocg_wallcls.json                          # ТП3: a wall-layer line along a body, not in its class
c compose python3 $O/compose_ocg.py ocg_compose.json                          # composition against cfg.OCG_REF_DXF (when set)
G=0; s_=$(date +%s); python3 $O/gate_ocg.py > log_gate_ocg.txt 2>&1 || G=1
echo "gate_ocg $(( $(date +%s)-s_ ))s status $G"; grep -E "^GATE|СТОП|принято|на просмотр" log_gate_ocg.txt | head -30
[ -s ocg_gate.json ] || { echo "gate_ocg did not finish:"; tail -8 log_gate_ocg.txt; }
python3 $O/runlog.py verify > log_runlog_verify.txt 2>&1 || { cat log_runlog_verify.txt; echo "GATE OCG STOP - Р2: прогон недействителен"; exit 3; }
[ $G = 0 ] || { echo "GATE OCG STOP"; exit 1; }
echo "run.sh done (ocg) $(date -u +%Y-%m-%dT%H:%M:%SZ)"
