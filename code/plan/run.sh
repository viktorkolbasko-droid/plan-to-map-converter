#!/bin/bash
# Engineering plan pipeline. Run inside a floor folder that holds cfg.py and the PDF:
#   cd work/f3 && bash ../../code/run.sh            (all steps)
#   bash ../../code/run.sh loop                     (from the assign <-> walls loop on)
#   bash ../../code/run.sh export                   (export and everything after it)
#   bash ../../code/run.sh manual                   (code 008: one assign against the last loop's walls, quick checks)
#   An AutoCAD sheet with OCG layers goes to the layer route ocg/run_ocg.sh (code 009): all | walls | joints | export | gate
set -e
C=$(dirname "$(readlink -f "$0")"); export PYTHONPATH="$C"
t() { local s=$(date +%s); local n=$1; shift; "$@" > log_$n.txt 2>&1 || { echo "FAIL $n"; tail -20 log_$n.txt; exit 1; }; echo "$n $(( $(date +%s)-s ))s"; }
# (code 007, Т3-1) a check that fails does not cancel the checks after it nor the gate: it is written to checks_failed.txt,
#   and the gate stops on it (S0) - under set -e one crash of misc_inventory.py on a floor without 'misc' left no gate at all
c() { local s=$(date +%s); local n=$1; shift; if "$@" > log_$n.txt 2>&1; then echo "$n $(( $(date +%s)-s ))s"; else echo "FAIL $n - the gate stops (S0)"; echo "$n" >> checks_failed.txt; tail -5 log_$n.txt; fi; }
FROM=${1:-all}
# (code 007, Р16) the class of the sheet first (plan/00, step 1). Code 009 (package 3): the route goes by the class -
#   exit 0 Revit - the pipeline below, as in 008; exit 4 an AutoCAD sheet with OCG layers - the layer route, module ocg/
#   (ocg/run_ocg.sh, the same arguments); exit 3 a sheet of an unknown class - a stop with the reason and a question
SC=0; python3 $C/sheetcheck.py > log_sheetcheck.txt 2>&1 || SC=$?
if [ $SC = 4 ]; then cat log_sheetcheck.txt; exec bash $C/ocg/run_ocg.sh "$@"; fi
[ $SC = 0 ] || { cat log_sheetcheck.txt; echo "STOP sheet class - run.sh is not started on this sheet (plan/00, step 1)"; exit 3; }
# (code 008, Т4-13, Т4-7) cfg at reading: layers of cfg in the layer table, MANUAL boxes that would take another class of
#   the previous run (cfgread_take.png) - a stop in seconds before anything is computed
python3 $C/cfgread.py > log_cfgread.txt 2>&1 || { cat log_cfgread.txt; echo "STOP cfg - fix cfg.py or confirm the record (cfg.MANUAL_TAKES_OK)"; exit 3; }
# (code 010, К-3; №98) the scale: a sheet outside 60-70 mm/pt is read as its copy at 63.5 mm/pt (norm.py, cfg.SHEET_MM_PER_PT);
#   a cfg that does not fit the copy - a stop in seconds; inside the band - the sheet as it is
python3 $C/norm.py revit > log_norm.txt 2>&1 || { cat log_norm.txt; echo "STOP scale - plan/rules/10 §2"; exit 3; }
head -1 log_norm.txt
if [ "$FROM" = "all" ]; then
  t extract   python3 $C/extract2.py            # vector extraction with clip masks -> prims.pkl, holes.pkl
fi
if [ "$FROM" = "all" ] || [ "$FROM" = "prep" ]; then
  rm -f objr.npy olab.npy lab.npy wallprims.pkl walls.pkl assign2.pkl assign2_pre.pkl doors45.json
  t strokefill python3 $C/strokefill.py         # stroke-fills -> solid polygons, hidden thin fills dropped -> seq.pkl
  t hatch     python3 $C/walls2.py              # geometric hatch candidates
  t wallmask  python3 $C/walls3.py              # raster wall mask (only for the first classification)
  t classes   python3 $C/objects.py             # sheet / axis / dim / tag / wall / obj
  t objr      python3 -c "from rmatch import full; full()"
  t desks     python3 $C/desks.py
  t doors     python3 $C/doors2.py
  t doors45   python3 $C/doors45.py             # doors 'leaf in the opening + open leaf and chord' (plan/rules/40 §3)
  t columns   python3 $C/columns.py
fi
# (code 008, Т4-9) run.sh manual - the quick round: only MANUAL, MISC_GROUPS or exemplars changed and the keys do not change
#   the FURN / NOHATCH sets of the walls - one assign against the walls of the last loop (walls_pre7.pkl), no two wall
#   rounds; the heavy checks (both ink checks, arcs, ends) are left for the delivery: the gate is preliminary (QUICK=1)
if [ "$FROM" = "manual" ]; then
  [ -s walls_pre7.pkl ] && [ -s wallprims_pre7.pkl ] || { echo "STOP manual: no walls of a loop (walls_pre7.pkl) - run.sh loop first"; exit 3; }
  cp walls_pre7.pkl walls.pkl; cp wallprims_pre7.pkl wallprims.pkl
  t assign  python3 $C/assign.py
  export QUICK=1
fi
if [ "$FROM" != "export" ] && [ "$FROM" != "manual" ]; then
rm -f wallprims.pkl                                # round 1 always starts without vector walls (same as a full run)
for r in 1 2; do                                  # objects <-> vector walls feedback, two rounds
  t assign_r$r python3 $C/assign.py
  t walls_r$r  python3 $C/walls_vec5.py
  t wallprims_r$r python3 $C/wallprims.py
done
t assign    python3 $C/assign.py                  # final objects against the final walls
cp walls.pkl walls_pre7.pkl; cp wallprims.pkl wallprims_pre7.pkl   # code 007: fix7.py starts from the loop's walls
fi
t reclass   python3 $C/reclass.py                 # unclassified pieces -> their objects, columns, round tables, details (plan/rules/40 §13)
cp assign2.pkl assign2_reclass.pkl
t fix7      python3 $C/fix7.py                    # code 007: the owner's rules of 03.10.2026 (columns, furniture, doors, faces, types, openings)
t export    python3 $C/export.py
t geomfix   python3 $C/geomfix.py                 # axis snapping, straight runs, merged line pieces (plan/rules/50 §9)
t svg       python3 $C/svgexport.py
# (code 007) the reports of the checks are written anew by this run: a report left from an earlier run would let the gate
#   read stale numbers when its check fails
rm -f checks_failed.txt verify.json fidelity.json ink.json ink_strict.json geomqa.json rooms.json boxcut.json misc_inventory.json \
      misc_inventory.png misc_context.json ends_audit.json class_params.json arcs_audit.json wall_evidence.json gate7.json gate.json
c verify    python3 $C/verify.py
c fidelity  python3 $C/fidelity.py
if [ -z "$QUICK" ]; then
c ink       python3 $C/inkdiff.py "" ink
TOL=0.4 AMIN=0.4 c ink_strict python3 $C/inkdiff.py "" ink_strict
fi
c geomqa    python3 $C/geomqa.py                  # geometry checks (plan/rules/60 §4)
c rooms     python3 $C/roomcheck.py               # room boundaries (plan/rules/60 §5)
c boxcut    python3 $C/checks/boxcut.py           # 3.9: drawing cut by operator boxes, 'sheet' by length (plan/rules/60 §6)
c miscinv   python3 $C/checks/misc_inventory.py 36   # 3.7: unclassified objects by shape, sheet of groups
c miscctx   python3 $C/checks/misc_context.py     # 3.7: piece of an object / touches the fabric / on its own
[ -z "$QUICK" ] && c ends      python3 $C/checks/ends_audit.py       # 3.8-3.9: open ends of the result against the source
c params    python3 $C/checks/class_params.py     # 3.10: classified objects against their class sizes, closed outlines (plan/rules/60 §6)
[ -z "$QUICK" ] && c arcs      python3 $C/checks/arcs_audit.py       # 3.11: arcs with a pattern are walls along their length, glazing on FACADES (plan/rules/60 §7)
c wev       python3 $C/checks/wall_evidence.py    # 3.12: every wall body holds a pattern or a fill (plan/rules/60 §7)
G7=0; s_=$(date +%s); python3 $C/checks/gate7.py > log_gate7.txt 2>&1 || G7=1   # code 007: the owner's checks S15*-S29*
echo "gate7 $(( $(date +%s)-s_ ))s status $G7"; grep -E "GATE7|СТОП|принято" log_gate7.txt | head -20
[ -s gate7.json ] || { echo "gate7 did not finish:"; tail -8 log_gate7.txt; }
G=0; t_=$(date +%s); python3 $C/checks/gate.py > log_gate.txt 2>&1 || G=1   # acceptance gate: exit 1 - the floor is not to be delivered (plan/rules/60 §8)
echo "gate $(( $(date +%s)-t_ ))s status $G"; grep -E "^GATE|STOP|принято|на просмотр" log_gate.txt | head -30
[ -s gate.json ] || { echo "gate did not finish:"; tail -8 log_gate.txt; }
[ $G7 = 0 ] || { echo "GATE7 STOP"; exit 1; }
[ $G = 0 ] || { echo "GATE STOP"; exit 1; }
echo "run.sh done $(date -u +%Y-%m-%dT%H:%M:%SZ)"
