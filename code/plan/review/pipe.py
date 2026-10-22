#!/usr/bin/env python3
"""Resumable runner of run.sh (code 008, Т4-11, Г1-13; from the test of client A 1, 06.10.2026): the same steps in the same
order as run.sh of code 008, with the same clean-ups and the same log_<step>.txt files.

Why: a container restart silently kills a background run.sh (plan/00, step 4, п. 166). This runner keeps a state file in
the floor folder; after a restart `pipe.py run` resumes from the first step not finished (the interrupted step is re-run
from scratch - every step reads its inputs and rewrites its outputs). run.sh stays the reference: a step added there is
added here in the same place.

  python3 pipe.py start all|prep|loop|export|manual   # write the plan of steps (does not run anything)
  python3 pipe.py run [budget_s]                      # run pending steps; stop before a step once the budget is spent
  python3 pipe.py status
Run inside the floor folder. Step lines go to pipe.log: "<step> <seconds>s rc=<rc>", the last line "END <mode> ...".
A check that fails does not stop the run (as run.sh: checks_failed.txt, the gate stops on S0); sheetcheck / cfgread exit 3
stops it; mode 'manual' - one assign against the walls of the last loop, the gate preliminary (QUICK=1).
"""
import json, os, shutil, subprocess, sys, time

C = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))     # the code folder of this copy
PY = 'python3'
S = {   # step -> command (as in run.sh of code 008)
    'sheetcheck': [PY, f'{C}/sheetcheck.py'], 'cfgread': [PY, f'{C}/cfgread.py'],
    'extract': [PY, f'{C}/extract2.py'],
    'rm_prep': None,
    'strokefill': [PY, f'{C}/strokefill.py'], 'hatch': [PY, f'{C}/walls2.py'], 'wallmask': [PY, f'{C}/walls3.py'],
    'classes': [PY, f'{C}/objects.py'], 'objr': [PY, '-c', 'from rmatch import full; full()'],
    'desks': [PY, f'{C}/desks.py'], 'doors': [PY, f'{C}/doors2.py'], 'doors45': [PY, f'{C}/doors45.py'],
    'columns': [PY, f'{C}/columns.py'],
    'rm_loop': None, 'walls_manual': None,
    'assign_r1': [PY, f'{C}/assign.py'], 'walls_r1': [PY, f'{C}/walls_vec5.py'], 'wallprims_r1': [PY, f'{C}/wallprims.py'],
    'assign_r2': [PY, f'{C}/assign.py'], 'walls_r2': [PY, f'{C}/walls_vec5.py'], 'wallprims_r2': [PY, f'{C}/wallprims.py'],
    'assign': [PY, f'{C}/assign.py'], 'pre7': None,
    'reclass': [PY, f'{C}/reclass.py'], 'copy_reclass': None, 'fix7': [PY, f'{C}/fix7.py'],
    'export': [PY, f'{C}/export.py'], 'geomfix': [PY, f'{C}/geomfix.py'], 'svg': [PY, f'{C}/svgexport.py'], 'rm_reports': None,
    'verify': [PY, f'{C}/verify.py'], 'fidelity': [PY, f'{C}/fidelity.py'],
    'ink': [PY, f'{C}/inkdiff.py', '', 'ink'], 'ink_strict': [PY, f'{C}/inkdiff.py', '', 'ink_strict'],
    'geomqa': [PY, f'{C}/geomqa.py'], 'rooms': [PY, f'{C}/roomcheck.py'], 'boxcut': [PY, f'{C}/checks/boxcut.py'],
    'miscinv': [PY, f'{C}/checks/misc_inventory.py', '36'], 'miscctx': [PY, f'{C}/checks/misc_context.py'],
    'ends': [PY, f'{C}/checks/ends_audit.py'], 'params': [PY, f'{C}/checks/class_params.py'],
    'arcs': [PY, f'{C}/checks/arcs_audit.py'], 'wev': [PY, f'{C}/checks/wall_evidence.py'],
    'gate7': [PY, f'{C}/checks/gate7.py'], 'gate': [PY, f'{C}/checks/gate.py'],
}
CHECKS = {'verify', 'fidelity', 'ink', 'ink_strict', 'geomqa', 'rooms', 'boxcut', 'miscinv', 'miscctx', 'ends', 'params', 'arcs', 'wev'}
HEAVY = {'ink', 'ink_strict', 'ends', 'arcs'}             # left out in the quick round (run.sh manual)
REPORTS = ['checks_failed.txt', 'verify.json', 'fidelity.json', 'ink.json', 'ink_strict.json', 'geomqa.json', 'rooms.json', 'boxcut.json',
           'misc_inventory.json', 'misc_inventory.png', 'misc_context.json', 'ends_audit.json', 'class_params.json', 'arcs_audit.json',
           'wall_evidence.json', 'gate7.json', 'gate.json']
HEAD = ['sheetcheck', 'cfgread']
PREP = ['rm_prep', 'strokefill', 'hatch', 'wallmask', 'classes', 'objr', 'desks', 'doors', 'doors45', 'columns']
LOOP = ['rm_loop', 'assign_r1', 'walls_r1', 'wallprims_r1', 'assign_r2', 'walls_r2', 'wallprims_r2', 'assign', 'pre7']
EXPORT = ['reclass', 'copy_reclass', 'fix7', 'export', 'geomfix', 'svg', 'rm_reports', 'verify', 'fidelity', 'ink', 'ink_strict', 'geomqa',
          'rooms', 'boxcut', 'miscinv', 'miscctx', 'ends', 'params', 'arcs', 'wev', 'gate7', 'gate']
PLAN = {'all': HEAD + ['extract'] + PREP + LOOP + EXPORT, 'prep': HEAD + PREP + LOOP + EXPORT, 'loop': HEAD + LOOP + EXPORT,
        'export': HEAD + EXPORT, 'manual': HEAD + ['walls_manual', 'assign'] + [s for s in EXPORT if s not in HEAVY]}
ST = '.pipe_state.json'


def log(s):
    with open('pipe.log', 'a') as f: f.write(s + '\n')
    print(s, flush=True)


def save(st):
    json.dump(st, open(ST + '.tmp', 'w')); os.replace(ST + '.tmp', ST)


def rm(*fs):
    for f in fs:
        if os.path.exists(f): os.remove(f)


def main():
    cmd = sys.argv[1]
    if cmd == 'start':
        mode = sys.argv[2]; st = dict(mode=mode, steps=PLAN[mode], done=[], started=time.strftime('%H:%M:%S', time.gmtime()))
        save(st); log(f'START {mode} {st["started"]} UTC'); return
    st = json.load(open(ST))
    if cmd == 'status':
        rest = [s for s in st['steps'] if s not in st['done']]
        print(st['mode'], 'done', len(st['done']), 'of', len(st['steps']), '| next', rest[:3], '| end', st.get('end')); return
    budget = float(sys.argv[2]) if len(sys.argv) > 2 else 1e9; t0 = time.time()
    env = dict(os.environ, PYTHONPATH=C)
    if st['mode'] == 'manual': env['QUICK'] = '1'
    for s in st['steps']:
        if s in st['done']: continue
        if time.time() - t0 > budget: log(f'PAUSE before {s}'); return
        if S[s] is None:
            if s == 'rm_prep': rm('objr.npy', 'olab.npy', 'lab.npy', 'wallprims.pkl', 'walls.pkl', 'assign2.pkl', 'assign2_pre.pkl', 'doors45.json')
            elif s == 'rm_loop': rm('wallprims.pkl')
            elif s == 'walls_manual':
                if not (os.path.exists('walls_pre7.pkl') and os.path.exists('wallprims_pre7.pkl')):
                    log('STOP manual: no walls of a loop (walls_pre7.pkl) - pipe.py start loop first'); st['end'] = 'STOP manual'; save(st); return
                shutil.copyfile('walls_pre7.pkl', 'walls.pkl'); shutil.copyfile('wallprims_pre7.pkl', 'wallprims.pkl')
            elif s == 'pre7': shutil.copyfile('walls.pkl', 'walls_pre7.pkl'); shutil.copyfile('wallprims.pkl', 'wallprims_pre7.pkl')
            elif s == 'copy_reclass': shutil.copyfile('assign2.pkl', 'assign2_reclass.pkl')
            elif s == 'rm_reports': rm(*REPORTS)
            st['done'].append(s); save(st); continue
        e = dict(env)
        if s == 'ink_strict': e.update(TOL='0.4', AMIN='0.4')
        ts = time.time()
        with open(f'log_{s}.txt', 'w') as lf:
            rc = subprocess.run(S[s], stdout=lf, stderr=subprocess.STDOUT, env=e).returncode
        log(f'{s} {int(time.time() - ts)}s rc={rc}')
        if s in HEAD and rc != 0:
            log(f'STOP {s} (exit {rc}) - see log_{s}.txt'); st['end'] = f'STOP {s}'; save(st); return
        if rc != 0 and s in CHECKS:
            with open('checks_failed.txt', 'a') as f: f.write(s + '\n')
        elif rc != 0 and s not in ('gate', 'gate7'):
            log(f'FAIL {s}'); st['end'] = f'FAIL {s}'; save(st); return
        st['done'].append(s); save(st)
        if s == 'gate':
            st['end'] = f'END {st["mode"]} rc={rc} {time.strftime("%H:%M:%S", time.gmtime())}'; save(st); log(st['end'])


if __name__ == '__main__':
    main()
