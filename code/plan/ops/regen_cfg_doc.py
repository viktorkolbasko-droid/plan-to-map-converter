# Rebuild engplan_95 (cfg.py of all client A floors) from the floor folders. Written only when a cfg changed; the
# history row (argv[1]) is added only then.
#   python3 regen_cfg_doc.py ["| date | pass | what changed |"]      ENG_WORK, ENG_DOCS - folders (defaults below)
import re, sys, os
DOC = os.path.join(os.environ.get('ENG_DOCS', '/home/claude/eng/docs'), 'engplan_95-cfg-клиент А.md')
W = os.environ.get('ENG_WORK', '/home/claude/eng/work')
FLOORS = [('1', 'f1'), ('2', 'f2'), ('3', 'f3b'), ('4', 'f4r'), ('5', 'f5r'), ('6', 'f6')]
ROW = sys.argv[1] if len(sys.argv) > 1 else None
s0 = open(DOC, encoding='utf-8').read(); s = s0
for n, f in FLOORS:
    body = open(f'{W}/{f}/cfg.py', encoding='utf-8').read().rstrip('\n')
    pat = re.compile(r"(## " + n + r" этаж\n\n```python\n).*?(\n```\n)", re.S)
    assert len(pat.findall(s)) == 1, n
    s = pat.sub(lambda m: m.group(1) + body + m.group(2), s)
if s == s0:
    print('unchanged', len(s)); sys.exit(0)
if ROW:
    s = re.sub(r"(\| Дата \| Кто \| Что изменено \|\n\|---\|---\|---\|\n(?:\|.*\|\n)*)", lambda m: m.group(1) + ROW + '\n', s, count=1)
open(DOC, 'w', encoding='utf-8').write(s); print('CHANGED', len(s))
