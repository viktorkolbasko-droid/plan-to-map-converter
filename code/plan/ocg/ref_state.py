"""ocg/ref_state.py - code 012 (#95 Р1, Р2): the state folder of a run - the files as they were at the export of the result.

Р2: the run's journal (runlog.py) must be valid - no script or module changed during the run; else STOP.
Р1: the state is the one the export step (e8_export.py) started from: every state file (*.pkl) with the SHA-256 the journal
wrote before the first export - from the run folder when unchanged, else from the store state/<sha>.pkl; a file overwritten
and not stored - STOP. Every export step and every check whose report the measures read (checks_ocg.py, doors_fit.py,
doors_check.py, wallcls_ocg.py) must have started from the same state of the measured files (objects, primitives, walls,
passages, rooms) - a report taken from another stage - STOP (the v010 reference took furniture from the stage before Э7р).
reexport() - Р1 for a reference: the export again from the state folder (blocks and DXF of both results) and the DXF compared
with the delivered ones: dxfgeo_cmp.py - 0 differences, dxfcmp.py - the same composition (the file hash cannot serve: ezdxf
writes the time of the save into the header)."""
import json, os, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import runlog

EXPORT = 'e8_export.py'
REPORT_SCRIPTS = ('checks_ocg.py', 'doors_fit.py', 'doors_check.py', 'wallcls_ocg.py')
NOT_MEASURED = ('blocks.pkl', 'blocks_outline.pkl', 'hidden.pkl')        # rebuilt by the export itself or a keyed cache


class Stop(Exception):
    pass


def _measured(st):
    return {f: h for f, h in st.items() if f not in NOT_MEASURED}


def prepare(run, dst, legacy_no_journal=False):
    """fills the folder dst (new) with links to the run's files, the state files as at the export; returns info dict"""
    run = os.path.abspath(run); info = dict(run=run)
    J = runlog.load(run)
    if J is None:
        if not legacy_no_journal: raise Stop(f'нет журнала прогона {runlog.JOURNAL} в {run} (Р2): прогон без хешей кода не сверяется')
        info['journal'] = dict(ok=False, reasons=['журнала нет — взято без Р2 по флагу --legacy-no-journal']); exp = None
    else:
        ok, reasons = runlog.verify(run)
        info['journal'] = dict(ok=ok, reasons=reasons, started_utc=J.get('started_utc'), steps=len(J.get('steps', [])), env=J.get('env'))
        if not ok: raise Stop('прогон недействителен (Р2): ' + '; '.join(reasons[:6]))
        # check of step 11: the export again and the measures run in this process's environment - its parameters of the result
        #   (runlog.env_params: curves.py CV_*, WIDTH_MM, ZONES_IN_DXF) must be the run's; a journal before the check has no 'env'
        if 'env' in J and runlog.env_params() != J['env']:
            raise Stop(f'окружение сверки {runlog.env_params()} не то, что у прогона {J["env"]} (curves.py CV_*, WIDTH_MM, ZONES_IN_DXF): '
                       f'повторная выгрузка и меры дадут другой чертёж — задать то же окружение (Р1, Р2)')
        if 'env' not in J: info['journal']['env_note'] = 'журнал без окружения (до проверки шага 11) — параметры окружения прогона не известны'
        exps = [s for s in J['steps'] if s.get('script') == EXPORT]
        if not exps: raise Stop(f'в журнале нет шага выгрузки {EXPORT} — не знаю, с какого состояния снят результат (Р1)')
        exp = exps[0]['state_before']; m0 = _measured(exp)
        for s in exps[1:] + [s for s in J['steps'] if s.get('script') in REPORT_SCRIPTS]:
            m = _measured(s.get('state_before') or {})
            bad = sorted(f for f in set(m0) | set(m) if m0.get(f) != m.get(f))
            if bad: raise Stop(f'шаг {s["name"]} ({s.get("script")}) начат с другого состояния, чем выгрузка: {bad[:6]} — '
                               f'его отчёт или результат не от сданного состояния (Р1)')
        info['state_step'] = exps[0]['name']
    os.makedirs(dst, exist_ok=False)
    src_state = {}
    for f in sorted(os.listdir(run)):
        p = os.path.join(run, f)
        if f in (runlog.STORE,) or f.startswith('.'): continue
        if f.endswith('.pkl') and exp is not None: continue
        os.symlink(p, os.path.join(dst, f))
    if exp is not None:
        for f, h in exp.items():
            p = os.path.join(run, f)
            if os.path.exists(p) and runlog.sha(p) == h: os.symlink(p, os.path.join(dst, f)); src_state[f] = 'прогон'
            elif runlog.stored(run, h): os.symlink(runlog.stored(run, h), os.path.join(dst, f)); src_state[f] = 'state/' + h[:12]
            else: raise Stop(f'{f}: на выгрузке был SHA-256 {h[:12]}, файл с тех пор переписан и не сохранён в state/ (Р1) — эталон не снять')
    info['state_files'] = src_state
    return info


def _run(cmd, cwd, env=None, log=None):
    e = dict(os.environ); e.update(env or {}); e.setdefault('PYTHONHASHSEED', '0')
    e['PYTHONPATH'] = os.path.dirname(HERE) + (os.pathsep + e['PYTHONPATH'] if e.get('PYTHONPATH') else '')
    r = subprocess.run(cmd, cwd=cwd, env=e, capture_output=True, text=True)
    if log: open(log, 'a').write(f'$ {" ".join(cmd)}\n{r.stdout}\n{r.stderr}\nrc={r.returncode}\n')
    return r


def reexport(state, delivered, export_script=None):
    """Р1: the export again in the state folder and the DXF compared with the delivered ones.
    delivered: {name: path of a delivered DXF}; the default export writes re_out/ (detail) and re_out_outline/ (outline) with the
    same file names; export_script - a bash script run as `bash <script> <ocg dir>` in the state folder instead (it must write
    the same). Returns [dict(file, same_geometry, same_composition, ...)]; raises Stop when a DXF is missing or differs."""
    log = os.path.join(state, 'reexport.log')
    for f in ('blocks.pkl', 'blocks_outline.pkl', 'hidden.pkl'):        # the export rebuilds them in the state folder, not in the run
        p = os.path.join(state, f)
        if os.path.islink(p): os.unlink(p)
    if export_script:
        r = _run(['bash', export_script, HERE], state, log=log)
        if r.returncode: raise Stop(f'повторная выгрузка упала (rc {r.returncode}): {log}')
    else:
        for env, script in (({}, 'e7_blocks.py'), ({'OUTDIR': 're_out'}, 'e8_export.py'),
                            ({'VARIANT': 'outline'}, 'e7_blocks.py'), ({'VARIANT': 'outline', 'OUTDIR': 're_out_outline'}, 'e8_export.py')):
            os.makedirs(os.path.join(state, env.get('OUTDIR', 're_out')), exist_ok=True)
            r = _run([sys.executable, os.path.join(HERE, script)], state, env, log)
            if r.returncode: raise Stop(f'повторная выгрузка: {script} {env} упал (rc {r.returncode}) — {log}')
    rows = []
    for name, path in delivered.items():
        sub = 're_out_outline' if name.startswith('габаритный') else 're_out'
        new = os.path.join(state, sub, os.path.basename(path))
        if not os.path.exists(new): raise Stop(f'повторная выгрузка не дала {os.path.basename(path)} ({name}) — эталон не принят (Р1)')
        g = _run([sys.executable, os.path.join(HERE, 'dxfgeo_cmp.py'), path, new], state, log=log)
        c = _run([sys.executable, os.path.join(HERE, 'dxfcmp.py'), path, new], state, log=log)
        comp_same = c.returncode == 0 and 'differing keys 0' in c.stdout and 'in blocks' not in c.stdout and not any(l.startswith('top ') for l in c.stdout.splitlines())
        rows.append(dict(file=name, same_geometry=g.returncode == 0, geometry=g.stdout.strip().splitlines()[0] if g.stdout.strip() else g.stderr[-300:],
                         same_composition=comp_same))
    bad = [r for r in rows if not (r['same_geometry'] and r['same_composition'])]
    if bad: raise Stop('выгрузка из снятого состояния — не тот чертёж, что сдан (Р1): ' + '; '.join(f"{r['file']}: {r['geometry']}" for r in bad))
    return rows


def delivered_dxf(run, out_name):
    """the delivered DXF of a run of ocg/run_ocg.sh: {'подробный': out/<OUT>_engineering.dxf, 'габаритный': out_outline/<OUT>_outline.dxf,
    'подробный зоны': out/<OUT>_zones.dxf when present}"""
    d = {'подробный': os.path.join(run, 'out', f'{out_name}_engineering.dxf'), 'габаритный': os.path.join(run, 'out_outline', f'{out_name}_outline.dxf')}
    z = os.path.join(run, 'out', f'{out_name}_zones.dxf')
    if os.path.exists(z): d['подробный зоны'] = z
    return {k: v for k, v in d.items() if os.path.exists(v)}


def out_name(cfg_path):
    """cfg.OUT of the floor without importing the route (ocg/sheet.py would need the PDF and the whole table)"""
    import importlib.util
    sp = importlib.util.spec_from_file_location('cfg_ref', cfg_path); m = importlib.util.module_from_spec(sp); sp.loader.exec_module(m)
    return getattr(m, 'OUT', 'plan'), m


def measure(state, d1, d2, zd, tmp_json, tmp_pkl):
    """ref_measures.py in the state folder (its own process): -> (numbers record, geometry)"""
    import pickle
    r = _run([sys.executable, os.path.join(HERE, 'ref_measures.py'), tmp_json, tmp_pkl, d1 or '', d2 or ''] + ([zd] if zd else []), state,
             log=os.path.join(state, 'measures.log'))
    if r.returncode: raise Stop('меры прогона не сняты: ' + (r.stdout + r.stderr).strip()[-800:])
    return json.load(open(tmp_json, encoding='utf-8')), pickle.load(open(tmp_pkl, 'rb'))
