# Machine time of the pipeline runs of a floor (core/rules/30 §3: agent and machine apart): every run*.log of
# run.sh - the sum of its "<step> <seconds>s" lines, the start estimated from the file time, the gate lines.
#   python3 ops/runtimes.py FLOOR_DIR [log ...]          (default: every run*.log in the folder, by time)
import re, os, sys, glob, datetime as dt
d = sys.argv[1] if len(sys.argv) > 1 else '.'
names = sys.argv[2:] or sorted((os.path.basename(p) for p in glob.glob(os.path.join(d, 'run*.log'))), key=lambda n: os.path.getmtime(os.path.join(d, n)))
tot = 0
for n in names:
    p = os.path.join(d, n)
    if not os.path.exists(p): continue
    end = dt.datetime.fromtimestamp(os.path.getmtime(p), dt.timezone.utc).replace(tzinfo=None); s = 0; steps = []
    for l in open(p, errors='replace'):
        m = re.match(r'^(\w+)\s+(\d+)s\s*$', l.strip())
        if m: s += int(m.group(2)); steps.append(m.group(1))
    tot += s
    gate = [l.strip()[:100] for l in open(p, errors='replace') if l.strip().startswith(('STOP', 'принято', 'GATE', 'PASS'))]
    print(f'{n:22s} start~{(end - dt.timedelta(seconds=s)):%H:%M:%S} end {end:%H:%M:%S} UTC  machine {s // 60}m{s % 60:02d}s  steps {len(steps)} from {steps[0] if steps else "-"}')
    for g in gate: print('      ', g)
print('total machine', tot // 60, 'min', tot % 60, 's')
