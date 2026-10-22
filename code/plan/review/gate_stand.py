# Stand of corruptions for the gates (code 007; Р30 and Р3 of the summary of 03.10.2026, п. 287): copies of a finished run of
#   a floor, each with one known defect put in, and the gates run again on the copy - each one must stop on its defect.
#   A gate that passes a corrupted copy is not a gate. Cases (each finds its place on the floor by features, not by
#   coordinates, so the stand runs on any floor that has such places):
#     A  a fragment of a table left as 'misc' and accepted by GATE_ACCEPT (S1 and S2 with a why of the closed list) -> S2
#     B  an 'Unknown' group without the owner's answer and without the picture of its question -> S11*;
#        B+ the same with cfg.QUESTIONS and the picture in questions/ -> no S11* (control)
#     C1 a table drawn by partition lines: its object becomes a light partition ('gklpart') -> S19* / S12*
#     C2 a frame round a level mark drawn by partition lines -> S13*
#     D  a glass door with the glass line left through its opening in the DXF -> S22*
#     E  an extra MISC_GROUPS entry where no 'misc' piece is -> reclass.py, X_miss -> S3;
#        E2 a second entry on the example of an entry (a later round) -> X_dup, the last name wins, list L4, no S3 (control);
#        E3 join=True on a piece larger than the limit (MISC_JOIN_MAX_MM, MISC_JOIN_MAX_PRIMS) -> X_miss with the reason -> S3
#     F  a why without a kind of the closed list (GATE_ACCEPT and GATE7_ACCEPT) -> the stop stays
#     G  a floor without 'misc' left: misc_inventory.py writes the sheet (Т3-1); a check that failed -> S0
#   code 008:
#     H  a DXF layer without a record in the layer table and a text «ПК…» on A-68----E- -> S14* (Т4-13, Т4-14)
#     I1 a MANUAL record on a layer the code table does not have -> cfgread.py exit 3 (Т4-13)
#     I2 a MANUAL box over a column of the run - it takes primitives of another class -> cfgread.py exit 3 (Т4-7)
#     J1 outline desks of the detector (Т4-1) given back to the light partitions -> S19* / S12* / S17* / S18*
#     J2 I-beam columns given to the light partitions (Т4-3) -> S21* / S20*
#   code 011 (package 5, ПК4-П14, ПК4-П1): the scale of the sheet the code reads against cfg (norm.py revit, a stop in seconds;
#   the copy x k of the floor's sheet is made in the case folder by norm.py --copy) - each must stop naming the field:
#     N1 SHEET_MM_PER_PT = 79.375 set on a sheet of the band (63.5) - the code would read a copy x 1.25 with cfg of the sheet
#     N2 the sheet x 0.8, cfg in pt of its copy at 63.5 (the floor's cfg), SHEET_MM_PER_PT forgotten
#     N3 the sheet x 0.8, the field 3 % too large (the copy x 1.2875, cfg on the copy x 1.25)
#     N4 the sheet x 0.8, the field 3 % too small and cfg on the copy made with it (axes / 1.03) - mm between the axes off
#     N5 SHEET_MM_PER_PT = 70 on a sheet of the band (cfg 63.5 by its axes) - the field and cfg disagree
#     N+ control: the sheet x 0.8 with the right field - goes (exit 0)
#     P  probe.py on the sheet x 0.8 (79.4 mm/pt, out of 55-75): no mm of the axes, the copies x k show k ~ 1.25
#   python3 gate_stand.py <run dir of the floor> <code dir> <out dir> [cases, e.g. A,B,D]
#   Writes <out dir>/stand.json and prints the table: case - defect - expected stop - what stopped - caught.
import os, sys, json, shutil, subprocess, pickle, math, re, copy, time
RUN, CODE, OUT = [os.path.abspath(a) for a in sys.argv[1:4]]
ONLY = sys.argv[4].split(',') if len(sys.argv) > 4 else None
GROUPS = ('A', 'B', 'C1', 'C2', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'V', 'N')     # the groups of want() below
# check of step 11 (step 10: «V1» ran nothing and printed «stand: 0 caught of 0»): an unknown group is a stop, not an empty stand
if ONLY and set(ONLY) - set(GROUPS): sys.exit(f'STOP gate_stand: групп {sorted(set(ONLY) - set(GROUPS))} нет — известные: {",".join(GROUPS)} (случай V1 — группа V)')
DEFAULT = 'Прочий элемент (не классифицирован)'
os.makedirs(OUT, exist_ok=True)
def mk(case):
    d = os.path.join(OUT, case)
    if os.path.exists(d): shutil.rmtree(d)
    shutil.copytree(RUN, d, ignore=shutil.ignore_patterns('*.npy', '*_full.png', '__pycache__', 'log_*.txt'))   # copy2: mtimes kept
    return d
def run(d, scripts, env=None):
    out = []
    for s in scripts:
        e = dict(os.environ, PYTHONPATH=CODE, **(env or {})); t0 = time.time()
        r = subprocess.run(['python3', os.path.join(CODE, s)], cwd=d, env=e, capture_output=True, text=True)
        out.append(dict(script=s, rc=r.returncode, s=round(time.time() - t0, 1), tail=(r.stdout + r.stderr)[-1500:]))
    return out
def gates(d):
    g = json.load(open(os.path.join(d, 'gate.json'))) if os.path.exists(os.path.join(d, 'gate.json')) else None
    g7 = json.load(open(os.path.join(d, 'gate7.json'))) if os.path.exists(os.path.join(d, 'gate7.json')) else None
    stops = {}
    if g: stops.update({s['code']: dict(n=s['n'], what=s['what'][:220]) for s in g['stops']})
    if g7: stops.update({c: dict(n=r['stop_n'], what=(r.get('rejected') or r['title'])[:220], by=dict(list(r['by'].items())[:4]))
                         for c, r in g7['checks'].items() if r['status'] == 'СТОП'})
    return stops, g, g7
def cfg_append(d, text):
    with open(os.path.join(d, 'cfg.py'), 'a', encoding='utf-8') as f: f.write('\n# ---- gate_stand: corruption of this copy\n' + text + '\n')
def ld(d, f): return pickle.load(open(os.path.join(d, f), 'rb'))
def dump(d, f, x): pickle.dump(x, open(os.path.join(d, f), 'wb'))
sys.path.insert(0, CODE)
BASE_STOPS = None
RES = []
def record(case, defect, expect, d, extra=None):
    stops, g, g7 = gates(d)
    new = {c: v for c, v in stops.items() if c not in BASE_STOPS or v['n'] > BASE_STOPS[c]['n'] or v['what'] != BASE_STOPS[c]['what']}
    allof = (extra or {}).pop('all', False)
    caught = ((all if allof else any)(c in new for c in expect)) if expect else not any(c in new for c in (extra or {}).get('must_not', []))
    RES.append(dict(case=case, defect=defect, expect=expect, new_stops=new, caught=caught, **(extra or {})))
    print(f"{case:3s} {'ПОЙМАНО' if caught else 'НЕ ПОЙМАНО':10s} ждём {expect or 'нет остановки ' + str((extra or {}).get('must_not'))} | новые остановки: "
          + ', '.join(f"{c} {v['n']}" for c, v in new.items()))
def want(c): return ONLY is None or c in ONLY
# ---------------------------------------------------------------- base: the gates on an untouched copy
d0 = mk('base'); run(d0, ['checks/gate7.py', 'checks/gate.py'])
BASE_STOPS, _, _ = gates(d0)
print('base stops:', {c: v['n'] for c, v in BASE_STOPS.items()})
I0 = ld(RUN, 'inst_final.pkl'); P = pickle.load(open(os.path.join(RUN, 'seq.pkl'), 'rb'))[0]
def bbox(ids):
    q = [v for i in ids for v in (P[i][4] if P[i][0] in ('l', 'c', 'qu') else P[i][4])]
    xs = [x for x, y in q]; ys = [y for x, y in q]
    return min(xs), min(ys), max(xs), max(ys)
TABLES = ('desk', 'desk_o', 'mtable', 'desk_src')
# ---------------------------------------------------------------- A: a fragment accepted
if want('A'):
    d = mk('A'); I = ld(d, 'inst_final.pkl')
    k = max((k for k, q in enumerate(I) if q['key'] in TABLES and len([i for i in q['prims'] if P[i][0] == 'l']) >= 8), key=lambda k: len(I[k]['prims']))
    ls = [i for i in I[k]['prims'] if P[i][0] == 'l']; b = bbox(ls); cx = (b[0] + b[2]) / 2
    frag = [i for i in ls if max(x for x, y in P[i][4]) <= cx][:max(3, len(ls) // 3)]
    I[k]['prims'] = [i for i in I[k]['prims'] if i not in set(frag)]
    I.append(dict(key='misc', name=DEFAULT, layer='A-00----E-', prims=sorted(frag)))
    dump(d, 'inst_final.pkl', I)
    run(d, ['checks/misc_inventory.py', 'checks/misc_context.py'])
    ctx = json.load(open(os.path.join(d, 'misc_context.json')))
    nfr = sum(v for c, v in ctx.get('summary', {}).items() if c.startswith('fragment'))
    cfg_append(d, f"GATE_ACCEPT = dict(GATE_ACCEPT, S1=dict(max=3, why='решение владельца, строка 135 (ref/core/10): группа посмотрена'), "
                  f"S2=dict(max=5, why='решение владельца, строка 164 (ref/core/10): обрывок посмотрен'))")
    run(d, ['checks/gate.py'])
    record('A', f'обрывок стола #{k} ({len(frag)} линий) — «прочее», S1 и S2 приняты GATE_ACCEPT с причиной из списка; misc_context: fragment {nfr}', ['S2'], d)
# ---------------------------------------------------------------- B: 'Unknown' without the picture of its question
if want('B'):
    d = mk('B'); I = ld(d, 'inst_final.pkl')
    names = {}
    for q in I:
        if q['prims'] and q['name'] != DEFAULT and (q.get('layer') == 'A-00----E-' or str(q['name']).startswith('Неизвестное')): names.setdefault(q['name'], 0); names[q['name']] += 1
    nm = max(names, key=names.get) if names else None
    if nm:
        new = re.sub(r'\s*[—-]?\s*назначение неизвестно\s*\(владел\w*\s+[\d.]+\)|\s*\(владел\w*\s+[\d.]+\)', '', nm) + ' — уточнить'
        for q in I:
            if q['name'] == nm: q['name'] = new
        dump(d, 'inst_final.pkl', I); run(d, ['checks/gate.py'])
        record('B', f'группа «Неизвестного» «{new[:60]}» ({names[nm]} шт.) без ответа владельца и без картинки вопроса', ['S11*'], d)
        d = mk('B+'); I = ld(d, 'inst_final.pkl')
        for q in I:
            if q['name'] == nm: q['name'] = new
        dump(d, 'inst_final.pkl', I); os.makedirs(os.path.join(d, 'questions'), exist_ok=True)
        from PIL import Image
        Image.new('RGB', (40, 20), 'white').save(os.path.join(d, 'questions', 'N1_stand.png'))
        cfg_append(d, f"QUESTIONS = {{{new!r}: 'questions/N1_stand.png'}}")
        run(d, ['checks/gate.py'])
        record('B+', 'то же, у группы картинка вопроса questions/N1_stand.png (контроль)', [], d, dict(must_not=['S11*']))
    else: RES.append(dict(case='B', defect='на этаже нет группы «Неизвестного»', caught=None))
# ---------------------------------------------------------------- C1: a table in the partitions
if want('C1'):
    d = mk('C1'); I = ld(d, 'inst_final.pkl')
    cand = [k for k, q in enumerate(I) if q['key'] in TABLES and q['prims'] and 'кабин' in q['name']]
    if not cand:
        cand = sorted((k for k, q in enumerate(I) if q['key'] in TABLES and len(q['prims']) >= 6), key=lambda k: -len(I[k]['prims']))[:1]
    k = cand[0]; nm0 = I[k]['name']
    I[k].update(key='gklpart', name='Перегородка ГКЛ (стенд: стол в перегородках)', layer='A-22----E-')
    for f_ in ('block', 'bbmm'): I[k].pop(f_, None)
    dump(d, 'inst_final.pkl', I); run(d, ['checks/gate7.py', 'checks/gate.py'])
    record('C1', f'стол #{k} «{nm0[:50]}» отдан перегородке ГКЛ — мебель в перегородках', ['S19*', 'S12*'], d)
# ---------------------------------------------------------------- C2: a level frame in the partitions
if want('C2'):
    d = mk('C2'); W = json.load(open(os.path.join(d, 'words.json')))
    lv = [w for w in W if re.fullmatch(r'[+±-]?\d{1,2}[.,]\d{3}', str(w[2]).strip())]
    if lv:
        w = lv[0]; b = w[3]; x0, y0, x1, y1 = b[0] - 1.2, b[1] - 1.0, b[2] + 1.2, b[3] + 1.0
        seq = pickle.load(open(os.path.join(d, 'seq.pkl'), 'rb')); P2 = seq[0]; cls = ld(d, 'cls.pkl')
        n0 = len(P2); pen = (0.24, (0.0, 0.0, 0.0))
        for a_, b_ in (((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))):
            P2.append(('l', pen[0], pen[1], None, (a_, b_), 10 ** 7 + len(P2)))
            cls.append('obj') if isinstance(cls, list) else None
        pickle.dump(seq, open(os.path.join(d, 'seq.pkl'), 'wb')); dump(d, 'cls.pkl', cls)
        I = ld(d, 'inst_final.pkl'); I.append(dict(key='lpart', name='Перегородка без штриховки (стенд: рамка отметки)', layer='A-22----E-', prims=list(range(n0, n0 + 4))))
        dump(d, 'inst_final.pkl', I); run(d, ['checks/gate.py'])
        record('C2', f'рамка вокруг отметки «{w[2]}» у ({w[0]:.0f}, {w[1]:.0f}) нарисована линиями перегородки', ['S13*'], d)
    else: RES.append(dict(case='C2', defect='на листе нет отметок уровня', caught=None))
# ---------------------------------------------------------------- D: glass without its gap at a glass door
if want('D'):
    d = mk('D'); I = ld(d, 'inst_final.pkl')
    gd = [q for q in I if q.get('glass_gap')]
    if gd:
        import ezdxf
        from importlib import util as _u
        os.chdir(d); sys.argv = [sys.argv[0]]
        import common as _c
        q = gd[0]; a, b = q['glass_gap']['a'], q['glass_gap']['b']
        doc = ezdxf.readfile(_c.DXF); msp = doc.modelspace()
        msp.add_line(_c.MM(a), _c.MM(b), dxfattribs={'layer': 'A-22G---E-'}); doc.saveas(_c.DXF); os.chdir(OUT)
        run(d, ['checks/gate7.py', 'checks/gate.py'])
        record('D', f'у стеклянной двери «{q["name"][:40]}» линия стекла через проём оставлена в DXF', ['S22*'], d)
    else: RES.append(dict(case='D', defect='на этаже нет стеклянной двери в перегородке', caught=None))
# ---------------------------------------------------------------- E: MISC_GROUPS entries
if want('E'):
    import importlib.util as iu
    sp = iu.spec_from_file_location('cfgx', os.path.join(RUN, 'cfg.py')); cx = iu.module_from_spec(sp); sp.loader.exec_module(cx)
    G = list(getattr(cx, 'MISC_GROUPS', []))
    X0, Y0, X1, Y1 = cx.WIN
    d = mk('E'); cfg_append(d, f"MISC_GROUPS = list(MISC_GROUPS) + [dict(at=({X0 + 3:.1f}, {Y0 + 3:.1f}), name='Лишняя запись (стенд)')]")
    run(d, ['reclass.py', 'checks/gate.py'])
    record('E', f'лишняя запись MISC_GROUPS в углу листа ({X0 + 3:.0f}, {Y0 + 3:.0f}), где «прочего» нет', ['S3'], d)
    unk = [g for g in G if 'key' not in g and not g.get('join')]
    if unk:
        g = unk[0]; d = mk('E2')
        cfg_append(d, f"MISC_GROUPS = list(MISC_GROUPS) + [dict({', '.join(f'{k}={v!r}' for k, v in g.items() if k != 'name')}, name='Стенд: повтор записи, новое имя')]")
        r_ = run(d, ['reclass.py'])
        inst2, _ = ld(d, 'assign2.pkl'); got = [q['name'] for q in inst2 if q['name'] == 'Стенд: повтор записи, новое имя']
        rj = json.load(open(os.path.join(d, 'reclass.json')))['places']
        run(d, ['checks/gate.py'])
        record('E2', f'вторая запись на пример записи {tuple(g["at"])} (следующий круг) с новым именем', [], d,
               dict(must_not=['S3'], x_dup=len(rj.get('X_dup', [])), last_name_won=len(got)))
    # E3: join on a large piece - the largest 'misc' piece before the step X
    I1, _ = ld(RUN, 'assign2_pre.pkl')
    big = [q for q in I1 if q['key'] == 'misc' and len(q['prims']) > 10]
    if big:
        q = max(big, key=lambda q: len(q['prims'])); b = bbox(q['prims'])
        lim = '' if len(q['prims']) > getattr(cx, 'MISC_JOIN_MAX_PRIMS', 200) else f"MISC_JOIN_MAX_PRIMS = {len(q['prims']) - 1}   # below the largest piece of this floor\n"
        d = mk('E3'); cfg_append(d, lim + f"MISC_GROUPS = [dict(at=({(b[0] + b[2]) / 2:.2f}, {(b[1] + b[3]) / 2:.2f}), join=True, reach=2.0, tol=3.0)] + list(MISC_GROUPS)")
        run(d, ['reclass.py', 'checks/gate.py'])
        rj = json.load(open(os.path.join(d, 'reclass.json')))['places']
        record('E3', f'join=True на кусок «прочего» {len(q["prims"])} примитивов у ({(b[0] + b[2]) / 2:.0f}, {(b[1] + b[3]) / 2:.0f})' + (' (предел копии ниже куска)' if lim else ''), ['S3'], d,
               dict(x_miss_why=[m.get('why', '')[:120] for m in rj.get('X_miss', [])][:3]))
# ---------------------------------------------------------------- F: a why without a kind
if want('F'):
    d = mk('F')
    cfg_append(d, "GATE_ACCEPT = {k: dict(v, why='посмотрено, так и есть') for k, v in GATE_ACCEPT.items()}\n"
                  "GATE7_ACCEPT = {k: dict(v, why='посмотрено по исходнику') for k, v in GATE7_ACCEPT.items()}")
    run(d, ['checks/gate7.py', 'checks/gate.py'])
    acc0 = [s_['code'] for s_ in json.load(open(os.path.join(d0, 'gate.json')))['accepted']] + list(json.load(open(os.path.join(d0, 'gate7.json')))['accepted'])
    if not acc0:                                       # nothing accepted on this floor: accept one stop of the base with a bad why
        c0 = next(iter(BASE_STOPS), None)
        if c0: cfg_append(d, f"GATE_ACCEPT = dict(GATE_ACCEPT, **{{{c0!r}: dict(max=999, why='посмотрено, так и есть')}})"); run(d, ['checks/gate.py']); acc0 = [c0]
    record('F', 'причина GATE_ACCEPT и GATE7_ACCEPT без вида: «посмотрено, так и есть»; принятые на базе: ' + ', '.join(acc0), acc0, d, dict(all=True))
# ---------------------------------------------------------------- G: a floor without 'misc'; a failed check
if want('G'):
    d = mk('G'); I = ld(d, 'inst_final.pkl')
    for q in I:
        if q['key'] == 'misc': q['key'] = 'equip'
    dump(d, 'inst_final.pkl', I)
    r_ = run(d, ['checks/misc_inventory.py'])
    ok_png = os.path.exists(os.path.join(d, 'misc_inventory.png'))
    os.remove(os.path.join(d, 'misc_context.json')); open(os.path.join(d, 'checks_failed.txt'), 'w').write('miscctx\n')
    run(d, ['checks/gate.py'])
    record('G', f'«прочего» нет: misc_inventory.py — код {r_[0]["rc"]}, лист {"есть" if ok_png else "нет"}; затем отчёт misc_context.json пропал, шаг miscctx упал', ['S0'], d,
           dict(misc_inventory_rc=r_[0]['rc']))
# ---------------------------------------------------------------- code 008: H - DXF layers (Т4-13, Т4-14)
if want('H'):
    import ezdxf
    d = mk('H'); dx = [f for f in os.listdir(d) if f.endswith('_engineering.dxf')][0]
    doc = ezdxf.readfile(os.path.join(d, dx)); msp = doc.modelspace()
    msp.add_line((0, 0), (1000, 0), dxfattribs={'layer': 'A-99----E-'})                 # a layer the table does not have
    msp.add_text('ПК-стенд', height=250, dxfattribs={'layer': 'A-68----E-'})            # a text on an 'E-' sub-layer
    doc.saveas(os.path.join(d, dx))
    run(d, ['verify.py', 'checks/gate.py'])
    record('H', 'в DXF линия на слое A-99----E- без записи в таблице и текст «ПК…» на A-68----E-', ['S14*'], d)
# ---------------------------------------------------------------- code 008: I - cfg at reading (Т4-13, Т4-7)
def cfgread_case(case, defect, text):
    d = mk(case); cfg_append(d, text)
    r = run(d, ['cfgread.py'])[0]
    caught = r['rc'] == 3
    RES.append(dict(case=case, defect=defect, expect=['cfgread: выход 3'], new_stops={'cfgread': dict(n=r['rc'], what=r['tail'][-220:])}, caught=caught))
    print(f"{case:3s} {'ПОЙМАНО' if caught else 'НЕ ПОЙМАНО':10s} ждём cfgread выход 3 | выход {r['rc']}: {r['tail'].strip().splitlines()[-1][:160] if r['tail'].strip() else ''}")
if want('I'):
    cfgread_case('I1', 'запись MANUAL со слоем A-99----E-, которого нет в таблице слоёв кода', "MANUAL = list(MANUAL) + [('equip', 'стенд: слой не из таблицы', 'A-99----E-', [(0, 0, 1, 1)])]")
    I0 = ld(RUN, 'inst_final.pkl'); I0 = I0[0] if isinstance(I0, tuple) else I0
    P0 = pickle.load(open(os.path.join(RUN, 'seq.pkl'), 'rb'))[0]
    col = next((q for q in I0 if q['key'] == 'column' and q['prims']), None)
    if col:
        ps = [tuple(v) for i in col['prims'] for v in P0[i][4]]   # control points bound the primitive
        bx = (min(p[0] for p in ps) - 0.1, min(p[1] for p in ps) - 0.1, max(p[0] for p in ps) + 0.1, max(p[1] for p in ps) + 0.1)
        cfgread_case('I2', f'рамка MANUAL «шкаф» на колонне у ({(bx[0] + bx[2]) / 2:.0f}, {(bx[1] + bx[3]) / 2:.0f}) — берёт примитивы другого класса', 
                     f"MANUAL = [('rack', 'стенд: рамка на колонне', 'A-76----E-', [{tuple(round(v, 2) for v in bx)}])] + list(MANUAL)")
# ---------------------------------------------------------------- code 008: J - what a detector of code 008 takes, undone
#   (a copy per detector): without the detector the object goes back to the class it had before 008 - the gates must stop
if want('J'):
    def undo(case, keys, to, why, expect, pick=None):
        d = mk(case); I = ld(d, 'inst_final.pkl')
        ks = [k for k, q in enumerate(I) if q['key'] in keys and q['prims'] and (pick is None or pick(q))]
        if not ks: RES.append(dict(case=case, defect=why + ' — на этаже нет таких объектов', expect=expect, new_stops={}, caught=None)); print(case, 'нет объектов'); return
        for k in ks[:6]:
            I[k].update(key=to[0], name=to[1], layer=to[2])
            for f_ in ('block', 'bbmm', 'tpl', 'c'): I[k].pop(f_, None)
        dump(d, 'inst_final.pkl', I); run(d, ['checks/gate7.py', 'checks/gate.py'])
        record(case, f'{why}: {min(6, len(ks))} шт.', expect, d)
    LP = ('lpart', 'Перегородка без штриховки в исходнике (стеклянная/лёгкая)', 'A-22G---E-')
    undo('J1', ('desk_o',), LP, 'столы-контуры детектора (Т4-1) отданы перегородке, как до 008', ['S19*', 'S12*', 'S17*', 'S18*'])
    undo('J2', ('column',), LP, 'колонны-двутавры отданы перегородке, как стенка двутавра до 008 (Т4-3)', ['S21*', 'S20*'],
         pick=lambda q: 'кругл' not in q['name'])
# ---------------------------------------------------------------- code 012: V - a fixture of one line (Г3-5): its hull is
#   degenerate (points on one line) - gate7 must not fall, the fixture goes to S20* as «оболочка вырождена»
if want('V'):
    d = mk('V1'); I = ld(d, 'inst_final.pkl')
    ks = [k for k, q in enumerate(I) if q['key'] in ('wc', 'sink', 'wcsink', 'urinal') and q['prims']]
    lines = [i for i, p in enumerate(P) if p[0] == 'l' and len(p[4]) == 2 and math.dist(p[4][0], p[4][1]) >= 1]
    hz = {}
    for i in lines:                                      # two lines of the sheet on one horizontal: 4 points on one line
        a, b = P[i][4]
        if a[1] == b[1]: hz.setdefault(round(a[1], 3), []).append(i)
    pair = next((v[:2] for v in hz.values() if len(v) >= 2), None)
    if not ks or pair is None: RES.append(dict(case='V1', defect='прибор из одной линии — на этаже нет сантехники или пары линий на одной прямой', caught=None))
    else:
        k = ks[0]; I[k]['prims'] = list(pair); I[k].pop('shared', None); I[k].pop('poly', None)
        dump(d, 'inst_final.pkl', I)
        if os.path.exists(os.path.join(d, 'gate7.json')): os.remove(os.path.join(d, 'gate7.json'))   # not the report of the copied run
        r = run(d, ['checks/gate7.py'])[0]
        g7 = json.load(open(os.path.join(d, 'gate7.json'))) if os.path.exists(os.path.join(d, 'gate7.json')) else None
        deg = [s_ for s_ in (g7['checks']['S20*']['spots'] if g7 else []) if s_['kind'] == 'сантехника: оболочка вырождена']
        fell = 'Traceback' in r['tail']
        caught = (not fell) and g7 is not None and len(deg) == 1
        RES.append(dict(case='V1', defect=f'прибор #{k} из одной линии: две линии листа {pair} на одной прямой', expect=['gate7 не падает', 'S20* «оболочка вырождена» 1'],
                        new_stops={'gate7': dict(n=len(deg), what=('УПАЛ: ' + r['tail'].strip().splitlines()[-1][:160]) if fell else (deg[0]['why'] if deg else 'нет строки'))}, caught=caught))
        print(f"V1  {'ПОЙМАНО' if caught else 'НЕ ПОЙМАНО':10s} ждём gate7 без падения и S20* «оболочка вырождена» | "
              + (('упал: ' + r['tail'].strip().splitlines()[-1][:160]) if fell else f'строк {len(deg)}: ' + (deg[0]['why'] if deg else '')))
# ---------------------------------------------------------------- code 011: N - the scale of the sheet read against cfg
if want('N'):
    import importlib.util as iu
    sp = iu.spec_from_file_location('cfgn', os.path.join(RUN, 'cfg.py')); cn = iu.module_from_spec(sp); sp.loader.exec_module(cn)
    SRC = os.path.join(RUN, cn.PDF); stem = os.path.splitext(os.path.basename(cn.PDF))[0]; X08 = stem + 'x08.pdf'
    def scale_case(case, defect, add, sheet08, rc_want, want_text):
        d = os.path.join(OUT, case)
        if os.path.exists(d): shutil.rmtree(d)
        os.makedirs(d); shutil.copy2(os.path.join(RUN, 'cfg.py'), d)
        if sheet08:
            subprocess.run(['python3', os.path.join(CODE, 'norm.py'), '--copy', SRC, '0.8', os.path.join(d, X08)], capture_output=True, text=True)
            add = f"PDF = {X08!r}\n" + add
        else: os.symlink(SRC, os.path.join(d, os.path.basename(cn.PDF)))
        cfg_append(d, add)
        r = run(d, ['norm.py'])[0]
        caught = r['rc'] == rc_want and want_text in r['tail']
        RES.append(dict(case=case, defect=defect, expect=[f'norm.py: выход {rc_want} «{want_text}»'], new_stops={'norm': dict(n=r['rc'], what=r['tail'][-300:])}, caught=caught))
        print(f"{case:3s} {'ПОЙМАНО' if caught else 'НЕ ПОЙМАНО':10s} ждём norm.py выход {rc_want} «{want_text}» | выход {r['rc']}: {r['tail'].strip()[:200]}")
    scale_case('N1', 'SHEET_MM_PER_PT = 79,375 у листа в полосе (63,5): код читал бы копию × 1,25 с cfg листа', 'SHEET_MM_PER_PT = 63.5 / 0.8', False, 3, 'поле убрать')
    scale_case('N2', 'лист × 0,8, cfg — по копии в 63,5 мм/pt, SHEET_MM_PER_PT забыт', '', True, 3, 'SHEET_MM_PER_PT не задан')
    scale_case('N3', 'лист × 0,8, поле на 3 % больше (копия × 1,2875, cfg по копии × 1,25)', 'SHEET_MM_PER_PT = 63.5 / 0.8 * 1.03', True, 3, 'неточно')
    scale_case('N4', 'лист × 0,8, поле на 3 % меньше и cfg по копии с тем же k (оси ÷ 1,03)', 'SHEET_MM_PER_PT = 63.5 / 0.8 / 1.03\nAX_X = [v / 1.03 for v in AX_X]; AX_Y = [v / 1.03 for v in AX_Y]', True, 3, 'мм между осями')
    scale_case('N5', 'SHEET_MM_PER_PT = 70 у листа в полосе: поле и масштаб cfg по осям (63,5) расходятся', 'SHEET_MM_PER_PT = 70.0', False, 3, 'не сходится')
    scale_case('N+', 'лист × 0,8, поле верное (контроль)', 'SHEET_MM_PER_PT = 63.5 / 0.8', True, 0, 'оси cfg совпали')
    # P: probe.py on the sheet x 0.8 - no mm of the axes, the copies x k (ПК4-П1)
    d = os.path.join(OUT, 'P'); shutil.rmtree(d, ignore_errors=True); os.makedirs(d)
    subprocess.run(['python3', os.path.join(CODE, 'norm.py'), '--copy', SRC, '0.8', os.path.join(d, X08)], capture_output=True, text=True)
    r = subprocess.run(['python3', os.path.join(CODE, 'probe.py'), X08, 'x08'], cwd=d, capture_output=True, text=True); out_ = r.stdout + r.stderr
    pj = json.load(open(os.path.join(d, 'x08_probe.json'))) if os.path.exists(os.path.join(d, 'x08_probe.json')) else {}
    cs = pj.get('copies_search') or {}
    caught = (pj.get('mm_per_pt_median') is None and 'AX_XMM' not in pj and 'AX_YMM' not in pj and abs((cs.get('k') or 0) - 1.25) <= 0.01)
    RES.append(dict(case='P', defect='probe.py на листе × 0,8 (79,4 мм/pt, вне 55–75)', expect=['мм осей нет; перебор копий: k ≈ 1,25'],
                    new_stops={'probe': dict(n=r.returncode, what=(cs and f"k {cs.get('k')}, лист {cs.get('sheet_mm_per_pt')} мм/pt, сошлось {cs.get('matched')} из {cs.get('of')}") or out_[-200:])}, caught=caught))
    print(f"P   {'ПОЙМАНО' if caught else 'НЕ ПОЙМАНО':10s} ждём: мм осей нет, перебор копий k ≈ 1,25 | median {pj.get('mm_per_pt_median')}, AX_XMM {'есть' if 'AX_XMM' in pj else 'нет'}, перебор {cs}")
json.dump(dict(run=RUN, code=CODE, base_stops=BASE_STOPS, cases=RES), open(os.path.join(OUT, 'stand.json'), 'w'), ensure_ascii=False, indent=1)
print('stand:', sum(1 for r in RES if r.get('caught')), 'caught of', sum(1 for r in RES if r.get('caught') is not None))
