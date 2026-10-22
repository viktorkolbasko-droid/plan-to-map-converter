"""ocg/runlog.py - code 012 (ОЧ-47, #95 Р1 and Р2): the journal of a run of the layer route.

Р2 (owner's rule of the reference, 09.10.2026: «код прогона не меняется во время прогона»). Before every step the journal
writes the SHA-256 of the step's script and of every module of the route the script loads (imports found in its source,
recursively, inside the code folders; cfg.py of the floor, which ocg/sheet.py loads). A script or module whose hash differs
from the hash it had at its first step of the run makes the run INVALID: the step stops (exit 3), and `verify` - called by the
reference and the regress check and before a delivery - refuses the run. A new run is the only way out. The same for the
environment variables that change the result (env_params: curves.py CV_*, WIDTH_MM, ZONES_IN_DXF; check of step 11).

Р1 (the reference is taken from the state that gave the delivered files). After every step the journal writes the SHA-256
of every state file (*.pkl in the run folder) and keeps every new content of them in state/<sha>.pkl (once per content:
objects.pkl that a later step overwrites stays retrievable as it was at the export). Off: OCG_STATE_STORE=0 (then a state
file overwritten after the export stops the reference - make_reference.py).

usage (ocg/run_ocg.sh):
  python3 runlog.py begin <runner script>          a new journal run_journal.json in the run folder (the cwd)
  python3 runlog.py pre  <step> <cmd ...>          before a step: hashes of its code; exit 3 if the code changed in the run
  python3 runlog.py post <step> <rc>               after a step: hashes of the state, the store of the state
  python3 runlog.py verify [run folder]            exit 0 - valid; 3 - invalid (reasons printed); 2 - no journal
Library: load(run), verify(run) -> (ok, reasons), step_state(run, script_name) -> the state before the first step with it."""
import ast, hashlib, json, os, shutil, sys, time

JOURNAL = 'run_journal.json'
STORE = 'state'
VERSION = 1
# code 012, check of step 11 (Р2): the environment variables that change what a step draws are code parameters of the run -
#   curves.py CV_TOL_REL, CV_RATIO, CV_SAG_CAP, CV_RES_CAP (arcs of e8_export.py, the facade arc of e7k_classes.py, ПЗ-5 of
#   qa_remarks.py), e9z_zones.py WIDTH_MM (the width of a passage), e8_export.py ZONES_IN_DXF (zones in the plan's DXF).
#   begin writes them (journal 'env'), pre compares them before every step - a change in the run makes it INVALID like a changed
#   script; ref_state.prepare stops a reference or a regress check made with other values than the run's (the export again and
#   the measures run in the caller's environment). Exact names, not a prefix: a variable of another program must not stop a check;
#   ENV_SERVICE - the variables a step reads that do not change the drawing (tests/test_reference.py: every read is in one list).
ENV_KEYS = ('WIDTH_MM', 'ZONES_IN_DXF', 'CV_TOL_REL', 'CV_RATIO', 'CV_SAG_CAP', 'CV_RES_CAP')
ENV_SERVICE = ('VARIANT', 'OUTDIR',              # set by run_ocg.sh per step (the detailed / габаритный result, the output folder)
               'OCG_STATE_STORE', 'OCG_REF_ALLOW_MISSING',   # the journal's store; the reference and regress check (said in their head)
               'S14D_DEBUG', 'S14C_DUMP', 'PASS_DEBUG',      # debug prints and dumps
               'TOL_MM',                         # e9_passage.py - not a step of run_ocg.sh since 012 (Э9з instead)
               'ZONES_DXF', 'Z', 'BA_BEFORE', 'BA_AFTER')    # command line tools: qa_remarks.py, sheets_layers.py, ba_view.py


def env_params(environ=None):
    """{name: value} of the environment variables of the route that change its result (ENV_KEYS)"""
    e = os.environ if environ is None else environ
    return {k: e[k] for k in sorted(e) if k in ENV_KEYS}


def sha(path, block=1 << 20):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        while True:
            b = f.read(block)
            if not b: break
            h.update(b)
    return h.hexdigest()


def utc():
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def _code_dirs(script):
    """folders where a module of the route is looked for: the script's folder, PYTHONPATH, code/plan and its checks/"""
    ds = [os.path.dirname(os.path.abspath(script))]
    ds += [os.path.abspath(p) for p in os.environ.get('PYTHONPATH', '').split(os.pathsep) if p]
    here = os.path.dirname(os.path.abspath(__file__)); plan = os.path.dirname(here)
    ds += [here, plan, os.path.join(plan, 'checks')]
    out = []
    for d in ds:
        if os.path.isdir(d) and d not in out: out.append(d)
    return out


def _imports(path):
    try: tree = ast.parse(open(path, encoding='utf-8').read(), path)
    except Exception: return set()
    names = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            for a in n.names: names.add(a.name.split('.')[0])
        elif isinstance(n, ast.ImportFrom) and n.module and not n.level:
            names.add(n.module.split('.')[0])
    return names


def modules(script):
    """the script and every module of the route it loads (by its imports, recursively): [abs paths]"""
    dirs = _code_dirs(script); seen = []; todo = [os.path.abspath(script)]
    while todo:
        p = todo.pop()
        if p in seen: continue
        seen.append(p)
        for name in sorted(_imports(p)):
            for d in dirs:
                f = os.path.join(d, name + '.py')
                if os.path.exists(f):
                    if os.path.abspath(f) not in seen: todo.append(os.path.abspath(f))
                    break
    return seen


def _state(run):
    return {f: sha(os.path.join(run, f)) for f in sorted(os.listdir(run)) if f.endswith('.pkl') and os.path.isfile(os.path.join(run, f))}


def load(run='.'):
    p = os.path.join(run, JOURNAL)
    return json.load(open(p, encoding='utf-8')) if os.path.exists(p) else None


def _save(J, run='.'):
    p = os.path.join(run, JOURNAL); tmp = p + '.tmp'
    json.dump(J, open(tmp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1); os.replace(tmp, p)


def begin(runner=None, run='.'):
    J = dict(version=VERSION, started_utc=utc(), run=os.path.abspath(run), python=sys.version.split()[0],
             hashseed=os.environ.get('PYTHONHASHSEED'), env=env_params(), files={}, steps=[], invalid=[])
    if runner and os.path.exists(runner): J['files'][os.path.abspath(runner)] = sha(runner)
    cfg = os.path.join(run, 'cfg.py')
    if os.path.exists(cfg): J['files'][os.path.abspath(cfg)] = sha(cfg)
    _save(J, run); return J


def _script_of(cmd):
    return next((c for c in cmd if c.endswith('.py')), None)


def pre(step, cmd, run='.'):
    """hashes of the step's code; a file changed since its first hash in this run - the run is invalid (returns reasons)"""
    J = load(run)
    if J is None: J = begin(None, run)
    script = _script_of(cmd); files = modules(script) if script else []
    cfg = os.path.join(run, 'cfg.py')
    if os.path.exists(cfg): files.append(os.path.abspath(cfg))
    code = {}; bad = []
    for f in files:
        h = sha(f); code[f] = h
        h0 = J['files'].setdefault(f, h)
        if h0 != h: bad.append(f'{f}: SHA-256 {h0[:12]} в начале прогона → {h[:12]} перед шагом {step}')
    env = env_params(); env0 = J.setdefault('env', env)              # check of step 11: the result's parameters of the environment
    if env != env0: bad.append(f'окружение маршрута {env0} в начале прогона → {env} перед шагом {step} (curves.py CV_*, WIDTH_MM, ZONES_IN_DXF)')
    J['steps'].append(dict(name=step, start_utc=utc(), cmd=[os.path.basename(c) if c.endswith('.py') else c for c in cmd],
                           script=os.path.basename(script) if script else None, code=code, state_before=_state(run)))
    if bad: J['invalid'] += bad
    _save(J, run); return bad


def post(step, rc, run='.'):
    J = load(run)
    if J is None or not J['steps'] or J['steps'][-1]['name'] != step:
        J = J or begin(None, run); J['steps'].append(dict(name=step, start_utc=None, code={}, state_before={}))
        J['invalid'].append(f'шаг {step}: нет записи перед шагом (pre) — код шага не хеширован')
    st = _state(run); s = J['steps'][-1]; s.update(end_utc=utc(), rc=int(rc), state_after=st)
    if os.environ.get('OCG_STATE_STORE', '1') != '0':
        d = os.path.join(run, STORE); os.makedirs(d, exist_ok=True)
        for f, h in st.items():
            dst = os.path.join(d, h + '.pkl')
            if not os.path.exists(dst): shutil.copyfile(os.path.join(run, f), dst + '.tmp'); os.replace(dst + '.tmp', dst)
    _save(J, run)


def verify(run='.'):
    """(ok, reasons): every code file hashed in the run still has its first hash; no step recorded a change"""
    J = load(run)
    if J is None: return False, [f'нет журнала прогона {JOURNAL} (Р2: прогон без хешей кода не сверяется и не сдаётся)']
    reasons = list(J.get('invalid', []))
    for f, h0 in J.get('files', {}).items():
        if not os.path.exists(f): reasons.append(f'{f}: файла кода нет (был в прогоне)'); continue
        h = sha(f)
        if h != h0: reasons.append(f'{f}: изменён после начала прогона (SHA-256 {h0[:12]} → {h[:12]})')
    if not J.get('steps'): reasons.append('в журнале нет шагов')
    for s in J.get('steps', []):
        if 'end_utc' not in s: reasons.append(f'шаг {s["name"]}: не закончен')
    return not reasons, reasons


def step_state(J, script):
    """the state (file -> sha) before the first step that runs <script>; None when no step runs it"""
    for s in J.get('steps', []):
        if s.get('script') == script: return s.get('state_before') or {}
    return None


def stored(run, h):
    p = os.path.join(run, STORE, h + '.pkl')
    return p if os.path.exists(p) else None


if __name__ == '__main__':
    a = sys.argv[1:]
    if not a: sys.exit(__doc__)
    if a[0] == 'begin': begin(a[1] if len(a) > 1 else None); print('runlog: журнал начат', JOURNAL)
    elif a[0] == 'pre':
        bad = pre(a[1], a[2:])
        if bad:
            print('STOP Р2: код маршрута изменён во время прогона — прогон недействителен, сверка и сдача — только после нового прогона:')
            for b in bad: print('  ', b)
            sys.exit(3)
    elif a[0] == 'post': post(a[1], a[2] if len(a) > 2 else 0)
    elif a[0] == 'verify':
        run = a[1] if len(a) > 1 else '.'
        if load(run) is None: print(f'STOP Р2: нет журнала прогона {os.path.join(run, JOURNAL)}'); sys.exit(2)
        ok, rs = verify(run)
        if ok: print('runlog: прогон действителен — код не менялся'); sys.exit(0)
        print('STOP Р2: прогон недействителен:'); [print('  ', r) for r in rs]; sys.exit(3)
    else: sys.exit(__doc__)
