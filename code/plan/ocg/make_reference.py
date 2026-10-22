"""ocg/make_reference.py - code 012 (ОЧ-47, ОЧ-130; #63 §2 п. 1, #95 Р1, Р2, Р4): the reference of a sheet from a run of the
layer route that the owner accepted by eye - numbers of the checks, objects by class, geometry and the result files.
usage: python3 make_reference.py <run folder> <reference folder> [--name "<name>"] [--export-script <bash>] [--legacy-no-journal]
Order (every failure is a STOP with the reason, exit 2; nothing is written into the reference folder then):
 1. Р2 - the run's journal is valid: no script or module of the route changed during the run (runlog.py);
 2. Р1 - the state folder: the state files as they were at the export (journal + state/<sha>.pkl), every check report taken
    from that same state (ref_state.prepare);
 3. Р1 - the export again from that state: the DXF of both results (and of the zones, when delivered) the same drawing as the
    delivered ones - dxfgeo_cmp.py 0 differences, dxfcmp.py the same composition (ref_state.reexport);
 4. the measures (ref_measures.py, version ref_lib.MEASURES_VERSION) on that state and the delivered DXF;
 5. Р4 - written as NEW files reference__vNNN.json, reference_geom__vNNN.pkl (NNN = the greatest in the folder + 1) and the result
    files in result__vNNN/ with their SHA-256; nothing in the folder is overwritten.
--legacy-no-journal: a run of a code without the journal (before 012) - Р2 cannot be checked; the head of the reference says so."""
import argparse, hashlib, json, os, pickle, shutil, sys, tempfile, time

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import ref_lib, ref_state


def sha(f):
    return hashlib.sha256(open(f, 'rb').read()).hexdigest()


def make(run, ref, name=None, export_script=None, legacy=False, keep_tmp=False):
    run = os.path.abspath(run); ref = os.path.abspath(ref)
    cfg = os.path.join(run, 'cfg.py')
    if not os.path.exists(cfg): raise ref_state.Stop(f'в папке прогона нет cfg.py: {run}')
    out, _ = ref_state.out_name(cfg)
    dl = ref_state.delivered_dxf(run, out)
    if 'подробный' not in dl or 'габаритный' not in dl: raise ref_state.Stop(f'в прогоне нет DXF обоих результатов (out/{out}_engineering.dxf, out_outline/{out}_outline.dxf)')
    tmp = tempfile.mkdtemp(prefix='ocg_ref_'); state = os.path.join(tmp, 'state')
    try:
        info = ref_state.prepare(run, state, legacy)
        info['reexport'] = ref_state.reexport(state, dl, export_script)
        M, G = ref_state.measure(state, dl['подробный'], dl['габаритный'], dl.get('подробный зоны'), os.path.join(tmp, 'm.json'), os.path.join(tmp, 'g.pkl'))
        n = ref_lib.next_version(ref); v = f'v{n:03d}'
        os.makedirs(ref, exist_ok=True)
        rd = os.path.join(ref, f'result__{v}'); os.makedirs(rd, exist_ok=False)
        files = {}
        for d_, tag in ((os.path.join(run, 'out'), 'подробный'), (os.path.join(run, 'out_outline'), 'габаритный')):
            for f in sorted(os.listdir(d_)) if os.path.isdir(d_) else []:
                if f.endswith(('.dxf', '.svg', '.json')):
                    src = os.path.join(d_, f); shutil.copyfile(src, os.path.join(rd, f'{tag}__{f}')); files[f'{tag}/{f}'] = sha(src)
        jp, pp = os.path.join(ref, f'reference__{v}.json'), os.path.join(ref, f'reference_geom__{v}.pkl')
        for p in (jp, pp):
            if os.path.exists(p): raise ref_state.Stop(f'{p} уже есть — папка эталона не перезаписывается')
        R = dict(name=name or os.path.basename(run), version=v, made_utc=time.strftime('%Y-%m-%d %H:%M', time.gmtime()), run=run,
                 measures_version=ref_lib.MEASURES_VERSION, mm_per_pt=M['mm_per_pt'], numbers=M['numbers'], qa_places=M.get('qa_places'),
                 files_sha256=files, state=info,
                 # check of step 11: the needed reports let off by OCG_REF_ALLOW_MISSING - in the head, not only inside numbers
                 allowed_missing=M['numbers'].get('allowed_missing') or [],
                 rules='ocg/regress_check.py: «не хуже» по числам проверок, геометрия стен, двери, мебель, проходы, ПЗ-1…ПЗ-10, помещения — допуски в ocg/ref_lib.py')
        json.dump(R, open(jp, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        shutil.copyfile(os.path.join(tmp, 'g.pkl'), pp)
        return dict(json=jp, pkl=pp, version=v, files=len(files), json_sha256=sha(jp), pkl_sha256=sha(pp), reexport=info['reexport'],
                    allowed_missing=R['allowed_missing'])
    finally:
        if not keep_tmp: shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('run'); ap.add_argument('ref'); ap.add_argument('--name'); ap.add_argument('--export-script')
    ap.add_argument('--legacy-no-journal', action='store_true'); ap.add_argument('--keep-tmp', action='store_true')
    a = ap.parse_args()
    try:
        r = make(a.run, a.ref, a.name, a.export_script, a.legacy_no_journal, a.keep_tmp)
    except ref_state.Stop as e:
        print('STOP make_reference:', e); sys.exit(2)
    except Exception as e:      # check of step 11: a crash is a STOP (exit 2) with its reason, as every failure of the docstring
        import traceback; traceback.print_exc()
        print(f'STOP make_reference: упал — {type(e).__name__}: {e}'); sys.exit(2)
    print('эталон', r['version'], '->', r['json'], '| файлов результата', r['files'], '| SHA-256 json', r['json_sha256'][:16], 'pkl', r['pkl_sha256'][:16])
    if r['allowed_missing']: print(f"  СНЯТ СТОП OCG_REF_ALLOW_MISSING: нет отчётов {r['allowed_missing']} — их меры в эталоне «—»")
    for x in r['reexport']: print('  Р1:', x['file'], '— тот же чертёж' if x['same_geometry'] and x['same_composition'] else 'ОТЛИЧИЕ', '|', x['geometry'])
