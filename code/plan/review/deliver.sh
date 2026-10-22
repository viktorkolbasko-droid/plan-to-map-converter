#!/bin/bash
# Delivery of floors (plan/rules/50 §5): the full preview (the SVG at 6000 px), the overlay on the source (cfg.WIN) and
#   copies of DXF / SVG / previews into the outputs folder. Names follow cfg.OUT: <OUT>_engineering.dxf / .svg,
#   <OUT>_preview.png, <OUT>_overlay_check.png.  Usage: deliver.sh f1 f2 ...   (folder names under $WORK)
C=$(cd "$(dirname "$0")/.." && pwd); O=${OUT:-/mnt/user-data/outputs}; WORK=${WORK:-$C/../work}
for fn in "$@"; do
  f=${fn%%:*}; cd "$WORK/$f" || exit 1
  pre=$(PYTHONPATH=$C python3 -c "from common import OUT; print(OUT)")
  PYTHONPATH=$C python3 $C/render_full.py ${pre}_engineering.svg ${pre}_preview.png 6000
  win=$(PYTHONPATH=$C python3 -c "from common import cfg; print(*cfg.WIN)")
  PYTHONPATH=$C python3 $C/overlay.py $win ${pre}_overlay_check.png
  cp -f ${pre}_engineering.dxf ${pre}_engineering.svg ${pre}_preview.png ${pre}_overlay_check.png "$O/"
  echo "$f -> $pre $(date -u +%H:%M)"
done
