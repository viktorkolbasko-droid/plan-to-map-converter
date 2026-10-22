"""ocg/regress_check.py - code 012 (ОЧ-47, ОЧ-130; #63 §2 пп. 2–5, #88 Э2, #95 Р2, Р4, #90 О-1): a run of the layer route
against the reference of its sheet - «не опускаться ниже эталона» (owner 07.10.2026).
usage: python3 regress_check.py <run folder> <reference folder> [out.json] [--allow-other-measures] [--legacy-no-journal]
       python3 regress_check.py --self <reference folder> [out.json] [--mm-per-pt K | --cfg cfg.py]     the reference against itself
Order: Р2 - the run's journal valid (else STOP); Р1 - the measures on the state at the export (ref_state.py); Р4 - the reference
files with the greatest __vNNN; О-1 - one version of the measures: the head of the result names the version of the code, of the
reference and of the run; when the reference was measured by another version the check is NOT VALID (exit 2) - re-make the
reference from its state with this code (make_reference.py), or pass --allow-other-measures (the head then says so).
Result: ПРОЙДЕНО (exit 0) - no regression; НЕ ПРОЙДЕНО (exit 1) with the list; every difference that is not a regression is
listed as «изменение» for the owner; a measure with nothing to measure - «—». STOP (exit 2) - the check could not be made
(check of step 11: a crash too, not exit 1). Reports let off by OCG_REF_ALLOW_MISSING - allowed_missing of the head, «СНЯТ СТОП».
The report line of a pass with a change of the process (#63 §2 п. 5): the reference, the verdict, the numbers of regressions and
changes, the path of this JSON."""
import argparse, importlib.util, json, os, shutil, sys, tempfile, time

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import ref_lib, ref_state


def head(R, rinfo, run_version, run, extra=None):
    mv = ref_lib.measures_version(R)
    h = dict(reference=R.get('name'), reference_files=rinfo, measures=dict(code=ref_lib.MEASURES_VERSION, reference=mv, run=run_version,
             same=(mv == run_version)), run=run, made_utc=time.strftime('%Y-%m-%d %H:%M', time.gmtime()))
    h.update(extra or {}); return h


def check_run(run, ref, allow_other=False, legacy=False):
    R, RG, rinfo = ref_lib.load(ref)
    run = os.path.abspath(run); cfg = os.path.join(run, 'cfg.py')
    if not os.path.exists(cfg): raise ref_state.Stop(f'в папке прогона нет cfg.py: {run}')
    out, _ = ref_state.out_name(cfg); dl = ref_state.delivered_dxf(run, out)
    tmp = tempfile.mkdtemp(prefix='ocg_regress_')
    try:
        info = ref_state.prepare(run, os.path.join(tmp, 'state'), legacy)
        M, NG = ref_state.measure(os.path.join(tmp, 'state'), dl.get('подробный'), dl.get('габаритный'), dl.get('подробный зоны'),
                                  os.path.join(tmp, 'm.json'), os.path.join(tmp, 'g.pkl'))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    N = M['numbers']; K = M['mm_per_pt']; rk = R.get('mm_per_pt')
    if rk and abs(rk - K) > 1e-6: raise ref_state.Stop(f'масштаб эталона {rk} мм/pt и прогона {K} мм/pt разные — не тот лист')
    # check of step 11: the needed reports let off by OCG_REF_ALLOW_MISSING - of the run and of the reference - go to the head (loud)
    am = dict(run=N.get('allowed_missing') or [], reference=R.get('allowed_missing') or (R.get('numbers') or {}).get('allowed_missing') or [])
    h = head(R, rinfo, N.get('measures_version'), run, dict(journal=info.get('journal'), state_step=info.get('state_step'), state_files=info.get('state_files'),
                                                         allowed_missing=am if am['run'] or am['reference'] else None))
    o = ref_lib.compare(R['numbers'], RG, N, NG, K)
    res = ref_lib.result(o, h)
    if not h['measures']['same']:
        if allow_other: res['measures']['note'] = 'разные версии мер — сверка по флагу --allow-other-measures (О-1: числа разных версий в одну таблицу не ставятся)'
        else: res['verdict'] = 'НЕ ГОДНО — разные версии мер (О-1)'
    return res


def check_self(ref, K=None):
    R, RG, rinfo = ref_lib.load(ref)
    K = R.get('mm_per_pt') or K
    if not K: raise ref_state.Stop('у эталона нет mm_per_pt — передай --mm-per-pt или --cfg <cfg.py листа>')
    h = head(R, rinfo, ref_lib.measures_version(R), f'эталон {rinfo["version"]} сам с собой', dict(mm_per_pt=K))
    return ref_lib.result(ref_lib.compare(R['numbers'], RG, R['numbers'], RG, K), h)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('a'); ap.add_argument('b', nargs='?'); ap.add_argument('out', nargs='?')
    ap.add_argument('--self', action='store_true'); ap.add_argument('--mm-per-pt', type=float); ap.add_argument('--cfg')
    ap.add_argument('--allow-other-measures', action='store_true'); ap.add_argument('--legacy-no-journal', action='store_true')
    a = ap.parse_args()
    try:
        if a.self:
            K = a.mm_per_pt
            if a.cfg and not K:
                sp = importlib.util.spec_from_file_location('cfg_ref', a.cfg); m = importlib.util.module_from_spec(sp); sp.loader.exec_module(m); K = getattr(m, 'MM_PER_PT', None)
            res = check_self(a.a, K); outf = a.b
        else:
            if not a.b: ap.error('нужны <папка прогона> <папка эталона>')
            res = check_run(a.a, a.b, a.allow_other_measures, a.legacy_no_journal); outf = a.out
    except (ref_state.Stop, ValueError) as e:
        print('STOP regress_check:', e); sys.exit(2)
    except Exception as e:      # check of step 11: a crash is a STOP (exit 2), not «НЕ ПРОЙДЕНО» (exit 1, the traceback's code)
        import traceback; traceback.print_exc()
        print(f'STOP regress_check: сверка упала — {type(e).__name__}: {e}'); sys.exit(2)
    if outf: json.dump(res, open(outf, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    ref_lib.print_result(res)
    sys.exit(0 if res['verdict'] == 'ПРОЙДЕНО' else 1 if res['verdict'] == 'НЕ ПРОЙДЕНО' else 2)
