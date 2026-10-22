# Stage durations of a pass from the live marks of ops/stage_mark.sh (core/rules/30 §3): a stage starts at its mark
# and ends at the next one; the last one ends at end_utc (default - now). Prints the table for the pass report.
#   python3 ops/timetable.py [timing.tsv] [end_utc YYYY-MM-DDTHH:MM:SSZ]
import sys, datetime as dt
f = sys.argv[1] if len(sys.argv) > 1 else 'timing.tsv'
rows = [l.rstrip('\n').split('\t') for l in open(f) if l.strip() and not l.startswith('stage')]
P = lambda s: dt.datetime.strptime(s, '%Y-%m-%dT%H:%M:%SZ')
marks = [(r[0], P(r[1]), r[2] if len(r) > 2 else '') for r in rows if len(r) > 1 and r[1]]
end = P(sys.argv[2]) if len(sys.argv) > 2 else dt.datetime.now(dt.timezone.utc).replace(microsecond=0, tzinfo=None)
marks.append(('конец', end, ''))
print('| Этап | Начало, UTC | Конец, UTC | Мин | Заметка |'); print('|---|---|---|---|---|')
for (a, t0, n), (b, t1, _) in zip(marks, marks[1:]):
    print(f'| {a} | {t0:%H:%M:%S} | {t1:%H:%M:%S} | {(t1 - t0).total_seconds() / 60:.1f} | {n} |')
