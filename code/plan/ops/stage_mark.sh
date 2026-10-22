#!/bin/bash
# The time journal of a pass (core/rules/30 §3): a UTC mark at the start of each stage, in timing.tsv of the current
# folder (or $TIMING). Durations - ops/timetable.py. From the effort test (client A, floor 4, 03.10.2026; п. 227).
#   bash ops/stage_mark.sh <stage> [note]
F=${TIMING:-timing.tsv}
[ -f "$F" ] || printf "stage\tutc\tnote\n" > "$F"
printf "%s\t%s\t%s\n" "$1" "$(date -u +%FT%TZ)" "${2:-}" >> "$F"
tail -1 "$F"
