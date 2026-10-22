"""Тесты эталона и сверки на регресс маршрута по слоям (ОЧ-47, ОЧ-130; код 012): `ocg/ref_lib.py`, `ocg/runlog.py`,
`ocg/ref_state.py`, `ocg/make_reference.py`, `ocg/regress_check.py` — на синтетике, без листа клиента.

Запуск: python3 -m unittest discover -s tests -v   (из папки code/plan)
Что проверяют:
 - самосверка: эталон против самого себя — «ПРОЙДЕНО», 0 регрессий и изменений;
 - искусственная регрессия (пустота в стене, пропавшая дверь, мебель без пары, хуже ПЗ, +6 % точек) — «НЕ ПРОЙДЕНО» со списком;
 - О-1: мера без объектов своего класса — «—», не 0; «—» в прогоне при числе в эталоне — регрессия; «—» в эталоне — изменение;
 - Р4: берутся файлы с наибольшим __vNNN; у наибольшей версии нет пары — стоп; без версий — reference.json (v001);
 - Р2: скрипт, изменённый во время прогона, — шаг стоп, журнал недействителен, сверка — стоп;
 - Р1: эталон из синтетического прогона — повторная выгрузка тем же чертежом принимается (новый __v001), другим — стоп, в папку
   эталона ничего не пишется; файл состояния, переписанный после выгрузки, берётся из state/; сверка прогона с его эталоном — «ПРОЙДЕНО».
"""
import json, os, pickle, shutil, subprocess, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OCG = os.path.join(ROOT, 'ocg'); sys.path.insert(0, OCG)
import ref_lib, runlog, ref_state                                      # noqa: E402
from shapely.geometry import Polygon, box                              # noqa: E402

K = 48.04


def numbers(doors=3, voids=0, desks=10, qa_pts=1000, pz1=2, rooms=2):
    st = {'в проёме': doors - 1, 'мимо проёма': 1} if doors else {}
    q = lambda: {'уникальные места': {'ПЗ-1': {'straight': pz1}, 'ПЗ-8': {'room on a wall': 1} if rooms else {}},
                 'ПЗ-6 дуга двери пунктиром': {'door arcs': doors * 2} if doors else {},
                 'ПЗ-8 образец помещения (точек)': 4, 'ПЗ-8 образец помещения — имя': 'Образец', 'всего точек': qa_pts,
                 'база': dict(contours=50, walls=5, door_arcs=doors * 2, massive=desks, rooms=rooms, passages=0)}
    return dict(measures_version=ref_lib.MEASURES_VERSION,
                walls=dict(bodies=4, voids=voids, short_edges_not_justified=1, straight_run_vertices=0, breaks_without_door=0),
                checks_tail=dict(hanging_lines=dict(n=0), furniture=dict(left_for_review={})),
                doors=dict(n=doors, status=st, end_gap_over_10mm=0, walls_in_opening=0, groups=1, groups_with_off=0, service=None),
                objects_by_key=dict(door=doors, desk=desks), furniture=dict(desks=desks, numbers_on_desks=desks),
                ocg=dict(o1_straight_other=0, o4_joints_final=0, o6_wallcls=0, o7_lines_outside_core=0, o8_doors_no_opening=0 if doors else None,
                         o8_hinge_far=0 if doors else None, o10_door_ends_off=0 if doors else None, s14_layers=0),
                qa={'подробный': q(), 'габаритный': q()}, pz10_outline_vs_detailed={'2': dict(n=0, by_type={})})


def geometry(doors=3, desks=10, rooms=2):
    return dict(walls=[('gkl', box(0, 0, 100, 2)), ('gkl', box(0, 0, 2, 50)), ('column', box(40, 20, 42, 22))],
                panes=box(100, 0, 140, 1), blocks=[box(60, 30, 80, 45)],
                doors=[dict(name=f'Дверь однопольная 900 ({i})', service=False, ring=[[10 + 20 * i, 0], [28.7 + 20 * i, 0], [28.7 + 20 * i, 2], [10 + 20 * i, 2]]) for i in range(doors)],
                furniture=[dict(key='desk', name='Стол', c=[10 + 5 * i, 30], area=12.0, bounds=[0, 0, 1, 1]) for i in range(desks)],
                passage=[box(5, 5, 90, 15)],
                rooms=[dict(poly=box(3 + 40 * i, 3, 38 + 40 * i, 18), number=f'1.{i}', kind='room', points=4, area_m2=1.0) for i in range(rooms)])


class Compare(unittest.TestCase):
    def test_self_passes(self):
        o = ref_lib.compare(numbers(), geometry(), numbers(), geometry(), K)
        res = ref_lib.result(o, dict(measures=dict(code=ref_lib.MEASURES_VERSION, reference=ref_lib.MEASURES_VERSION, run=ref_lib.MEASURES_VERSION, same=True)))
        self.assertEqual(res['verdict'], 'ПРОЙДЕНО'); self.assertEqual(res['regressions'], []); self.assertEqual(res['changes'], [])
        self.assertGreater(len(res['same']), 20)

    def test_regression_fails(self):
        g = geometry(); g['doors'] = g['doors'][:2]                          # a door of the reference is lost
        g['furniture'] = g['furniture'][:-1]                               # a desk of the reference has no pair
        g['walls'] = [('gkl', box(0, 0, 100, 2)), ('column', box(40, 20, 42, 22))]   # a wall body is gone (IoU < 0.98)
        n = numbers(voids=1, pz1=3, qa_pts=1061)                            # a void, one more ПЗ-1 place, +6.1 % points
        o = ref_lib.compare(numbers(), geometry(), n, g, K)
        txt = '\n'.join(o.regress)
        self.assertIn('стены.voids: эталон 0 → 1', txt)
        self.assertIn('двери эталона без пары: 1', txt)
        self.assertIn('мебель эталона без пары того же класса в 100 мм: 1', txt)
        self.assertIn('стены gkl: IoU', txt)
        self.assertIn('подробный.ПЗ-1.straight: эталон 2 → 3', txt)
        self.assertIn('подробный.точек в DXF: эталон 1000 → 1061', txt)
        self.assertEqual(ref_lib.result(o, {})['verdict'], 'НЕ ПРОЙДЕНО')

    def test_better_is_a_change_not_a_regression(self):
        n = numbers(qa_pts=950); n['walls']['short_edges_not_justified'] = 0
        o = ref_lib.compare(numbers(), geometry(), n, geometry(), K)
        self.assertEqual(o.regress, [])
        self.assertTrue(any('short_edges_not_justified: эталон 1 → 0' in x for x in o.changes))

    def test_dash_not_zero(self):
        # no doors on both sides: every door measure is «—», not 0 (О-1)
        o = ref_lib.compare(numbers(doors=0), geometry(doors=0), numbers(doors=0), geometry(doors=0), K)
        self.assertIn('двери.в проёме: —', o.dash); self.assertIn('двери.end_gap_over_10mm: —', o.dash)
        self.assertIn('двери эталона без пары: —', o.dash)
        self.assertIn('подробный.ПЗ-6 дуги дверей пунктиром: —', o.dash)
        self.assertFalse(any(x.startswith('двери.в проёме: 0') for x in o.same))
        self.assertEqual(o.regress, [])
        # the reference has doors, the run none: «—» in the run is a regression
        o = ref_lib.compare(numbers(), geometry(), numbers(doors=0), geometry(doors=0), K)
        self.assertTrue(any(x.startswith('двери.в проёме: эталон 2 → —') for x in o.regress))
        # no rooms in either: the ПЗ-8 places are «—»
        o = ref_lib.compare(numbers(rooms=0), geometry(rooms=0), numbers(rooms=0), geometry(rooms=0), K)
        self.assertIn('помещения эталона без пары (IoU ≥ 0,95): —', o.dash)
        # a measure the reference has not (a reference of v010: no ocg section) - a change, not a regression
        r = numbers(); r.pop('ocg'); r['walls'].pop('breaks_without_door')
        o = ref_lib.compare(r, geometry(), numbers(), geometry(), K)
        self.assertEqual(o.regress, [])
        self.assertTrue(any(x.startswith('стены.breaks_without_door: эталон —') for x in o.changes))

    def test_objects_absent_in_reference_are_a_change(self):
        # check of step 11 (О-1): passages, glass, core blocks the reference has not - a change (IoU 0 made them a regression);
        # the run has none of them while the reference has - a regression
        r = geometry(); r['passage'] = []; r['panes'] = None; r['blocks'] = []
        o = ref_lib.compare(numbers(), r, numbers(), geometry(), K)
        self.assertEqual(o.regress, [], o.regress)
        for s in ('проходы: эталон —', 'стекло: эталон —', 'блоки ядра: эталон —'): self.assertTrue(any(x.startswith(s) for x in o.changes), (s, o.changes))
        o = ref_lib.compare(numbers(), geometry(), numbers(), r, K)
        for s in ('проходы: эталон', 'стекло: эталон', 'блоки ядра: эталон'):
            self.assertTrue(any(x.startswith(s) and x.endswith('(в прогоне не на чем мерить)') for x in o.regress), (s, o.regress))


class PickVersion(unittest.TestCase):
    def setUp(self): self.d = tempfile.mkdtemp()
    def tearDown(self): shutil.rmtree(self.d)

    def touch(self, *names):
        for n in names:
            with open(os.path.join(self.d, n), 'w') as f: f.write('{}')

    def test_greatest(self):
        self.touch('reference.json', 'reference_geom.pkl', 'reference__v002.json', 'reference_geom__v002.pkl', 'reference__v010.json', 'reference_geom__v010.pkl')
        j, p, v = ref_lib.pick(self.d)
        self.assertEqual(v, 'v010'); self.assertTrue(j.endswith('reference__v010.json')); self.assertTrue(p.endswith('reference_geom__v010.pkl'))
        self.assertEqual(ref_lib.next_version(self.d), 11)

    def test_top_without_pair_stops(self):
        self.touch('reference__v002.json', 'reference_geom__v002.pkl', 'reference__v003.json')
        with self.assertRaises(ValueError): ref_lib.pick(self.d)

    def test_unversioned(self):
        self.touch('reference.json', 'reference_geom.pkl')
        self.assertEqual(ref_lib.pick(self.d)[2], 'v001'); self.assertEqual(ref_lib.next_version(self.d), 2)


class Journal(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(); self.cwd = os.getcwd(); os.chdir(self.d)
        self.s = os.path.join(self.d, 'step_a.py'); open(self.s, 'w').write('import helper_mod\nprint(1)\n')
        open(os.path.join(self.d, 'helper_mod.py'), 'w').write('X = 1\n')
    def tearDown(self): os.chdir(self.cwd); shutil.rmtree(self.d)

    def test_changed_script_stops(self):
        runlog.begin(None, self.d)
        self.assertEqual(runlog.pre('a', ['python3', self.s], self.d), []); runlog.post('a', 0, self.d)
        J = runlog.load(self.d); self.assertIn(os.path.join(self.d, 'helper_mod.py'), J['steps'][0]['code'])   # the loaded module is hashed
        self.assertTrue(runlog.verify(self.d)[0])
        open(os.path.join(self.d, 'helper_mod.py'), 'w').write('X = 2\n')                                      # the module changed in the run
        bad = runlog.pre('b', ['python3', self.s], self.d)
        self.assertTrue(bad and 'helper_mod.py' in bad[0])
        ok, why = runlog.verify(self.d); self.assertFalse(ok); self.assertTrue(any('helper_mod.py' in w for w in why))
        r = subprocess.run([sys.executable, os.path.join(OCG, 'runlog.py'), 'verify', self.d], capture_output=True, text=True)
        self.assertEqual(r.returncode, 3)

    def test_env_change_stops(self):
        # check of step 11: an environment parameter of the result (curves.py CV_*) changed during the run - the run is invalid
        old = os.environ.pop('CV_RATIO', None)
        try:
            runlog.begin(None, self.d)
            self.assertEqual(runlog.pre('a', ['python3', self.s], self.d), []); runlog.post('a', 0, self.d)
            self.assertNotIn('CV_RATIO', runlog.load(self.d)['env'])
            os.environ['CV_RATIO'] = '3.0'
            bad = runlog.pre('b', ['python3', self.s], self.d)
            self.assertTrue(bad and 'CV_RATIO' in bad[-1], bad)
            self.assertFalse(runlog.verify(self.d)[0])
        finally:
            os.environ.pop('CV_RATIO', None)
            if old is not None: os.environ['CV_RATIO'] = old
        self.assertEqual(runlog.env_params({'CV_HOME': '/x', 'CV_RATIO': '3'}), {'CV_RATIO': '3'})   # exact names, not a prefix

    def test_every_env_read_of_the_route_is_classified(self):
        # check of step 11: a variable a module of ocg/ reads is either a parameter of the result (runlog.ENV_KEYS - journalled, Р2)
        # or a service one (runlog.ENV_SERVICE); a new read in neither list fails here, not silently in a run
        import re
        pat = re.compile(r"""(?:environ\.get|environ\[|getenv)\(?\s*['"]([A-Z0-9_]+)['"]""")
        found = {}
        for f in sorted(os.listdir(OCG)):
            if f.endswith('.py'):
                for v in pat.findall(open(os.path.join(OCG, f), encoding='utf-8').read()): found.setdefault(v, f)
        known = set(runlog.ENV_KEYS) | set(runlog.ENV_SERVICE) | {'PYTHONHASHSEED', 'PYTHONPATH'}
        self.assertEqual({v: f for v, f in found.items() if v not in known}, {})
        self.assertTrue({'CV_RATIO', 'WIDTH_MM', 'ZONES_IN_DXF'} <= set(found))       # the scan sees the reads

    def test_state_store(self):
        runlog.begin(None, self.d); pickle.dump({'v': 1}, open('objects.pkl', 'wb'))
        runlog.pre('a', ['python3', self.s], self.d); runlog.post('a', 0, self.d)
        h1 = runlog.load(self.d)['steps'][0]['state_after']['objects.pkl']
        pickle.dump({'v': 2}, open('objects.pkl', 'wb'))
        runlog.pre('b', ['python3', self.s], self.d); runlog.post('b', 0, self.d)
        self.assertEqual(pickle.load(open(runlog.stored(self.d, h1), 'rb')), {'v': 1})


# ---------------------------------------------------------------- a synthetic run of the layer route
CFG = """PDF = None
OUT = 'synth'
TITLE = 'synthetic'
MM_PER_PT = 48.04; ORIGIN_PT = (0.0, 0.0)
OCG_GLASS_COLORS = [(0.0, 0.0, 1.0)]
OCG_LAYERS = [dict(layer='W', role='wall'), dict(layer='D', role='door'), dict(layer='F', role='furniture')]
OCG_ROOM_SAMPLE = None
OCG_PASSAGE_W_MM = 1400
"""


def write_dxf(path, shift=0.0):
    import ezdxf
    doc = ezdxf.new('R2018'); msp = doc.modelspace()
    for n in ('A-222---E-', 'A-222---H-', 'A-82----E-'): doc.layers.add(n)
    s = lambda pts: [(x * K + shift, -y * K) for x, y in pts]
    msp.add_lwpolyline(s([(0, 0), (100, 0), (100, 2), (0, 2)]), close=True, dxfattribs={'layer': 'A-222---E-'})
    h = msp.add_hatch(dxfattribs={'layer': 'A-222---H-'}); h.paths.add_polyline_path(s([(0, 0), (100, 0), (100, 2), (0, 2)]), is_closed=True)
    msp.add_lwpolyline(s([(10, 30), (13, 30), (13, 34), (10, 34)]), close=True, dxfattribs={'layer': 'A-82----E-'})
    doc.saveas(path)


def make_run(d, report_from_other_state=False):
    """report_from_other_state (check of step 11): objects.pkl changes between the exports and the check doors_fit - its report
    is not of the delivered state (Р1)"""
    os.makedirs(d); open(os.path.join(d, 'cfg.py'), 'w').write(CFG)
    P = [dict(id=0, kind='fill', p=[(100, 0), (140, 0), (140, 1), (100, 1)], layer='W', col=(0.0, 0.0, 1.0), seq=0),
         dict(id=1, kind='line', p=[(10, 0), (28.7, 0), (28.7, 2), (10, 2), (10, 0)], layer='D', opening=True, seq=1),
         dict(id=2, kind='fill', p=[(10, 30), (13, 30), (13, 34), (10, 34)], layer='F', seq=2)]
    pickle.dump(dict(P=P, T=[]), open(os.path.join(d, 'prims.pkl'), 'wb'))
    pickle.dump(dict(bodies=[('gkl', box(0, 0, 100, 2)), ('column', box(40, 20, 42, 22))]), open(os.path.join(d, 'walls.pkl'), 'wb'))
    objs = [dict(key='door', name='Дверь однопольная 900', ids=[1], draw=[1]), dict(key='desk', name='Стол', ids=[2])]
    json.dump(dict(walls=dict(bodies=2, vertices=8, area_m2={'gkl': 0.46}, straight_run_vertices=0, straight_run_reasons={},
                              holes=dict(n=0, voids=0), short_edges=dict(by_reason={}), breaks_without_door=dict(n=0)),
                   hanging_lines=dict(n=0), furniture=dict(left_for_review={}), joints_final=dict(n=0), walls_as_lines_outside_core=dict(n=0),
                   doors_no_opening=dict(n=0), door_ends=dict(ends=2, off_face=0)), open(os.path.join(d, 'ocg_checks.json'), 'w'))
    json.dump(dict(doors=1, status={'в проёме': 1}, end_gap_over_10mm=[], walls_in_opening=[], groups=[{}], groups_with_off=0),
              open(os.path.join(d, 'doors_fit.json'), 'w'))
    json.dump(dict(desks=1, numbers_on_desks=1), open(os.path.join(d, 'furniture.json'), 'w'))
    for sub, f in (('out', 'synth_engineering.dxf'), ('out_outline', 'synth_outline.dxf')):
        os.makedirs(os.path.join(d, sub)); write_dxf(os.path.join(d, sub, f))
    fake = os.path.join(d, '_fake_steps'); os.makedirs(fake)
    for s in ('doors_fit.py',): open(os.path.join(fake, s), 'w').write('print(1)\n')
    # the journal as run_ocg.sh writes it: objects.pkl is overwritten AFTER the export (the v010 case) - the store keeps it
    runlog.begin(None, d)
    pickle.dump(dict(objs=objs), open(os.path.join(d, 'objects.pkl'), 'wb'))
    for name, script in (('e8', os.path.join(OCG, 'e8_export.py')), ('e82', os.path.join(OCG, 'e8_export.py')),
                         ('checks', os.path.join(OCG, 'checks_ocg.py')), ('doors_fit', os.path.join(fake, 'doors_fit.py'))):
        if report_from_other_state and name == 'doors_fit':
            pickle.dump(dict(objs=objs[:1]), open(os.path.join(d, 'objects.pkl'), 'wb'))
        assert runlog.pre(name, ['python3', script], d) == []; runlog.post(name, 0, d)
    pickle.dump(dict(objs=objs + [dict(key='desk', name='Стол лишний', ids=[2])]), open(os.path.join(d, 'objects.pkl'), 'wb'))
    return d


SAME = 'mkdir -p re_out re_out_outline && cp out/*.dxf re_out/ && cp out_outline/*.dxf re_out_outline/\n'


class EndToEnd(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d = tempfile.mkdtemp(); cls.run_ = make_run(os.path.join(cls.d, 'run'))
        cls.same = os.path.join(cls.d, 'same.sh'); open(cls.same, 'w').write(SAME)
        cls.other = os.path.join(cls.d, 'other.sh')
        open(cls.other, 'w').write(SAME + f'"{sys.executable}" -c "import sys; sys.path.insert(0, \'{os.path.dirname(os.path.abspath(__file__))}\'); '
                                   f'import test_reference as t; t.write_dxf(\'re_out/synth_engineering.dxf\', shift=5.0)"\n')
    @classmethod
    def tearDownClass(cls): shutil.rmtree(cls.d)

    def mk(self, ref, script):
        return subprocess.run([sys.executable, os.path.join(OCG, 'make_reference.py'), self.run_, ref, '--name', 'синтетика', '--export-script', script],
                              capture_output=True, text=True)

    def test_1_reference_accepted_and_selfcheck(self):
        ref = os.path.join(self.d, 'ref_ok')
        r = self.mk(ref, self.same); self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        R = json.load(open(os.path.join(ref, 'reference__v001.json')))
        self.assertEqual(R['measures_version'], ref_lib.MEASURES_VERSION)
        self.assertEqual(R['numbers']['objects_by_key'], {'door': 1, 'desk': 1})          # the state at the export, not the later objects.pkl
        self.assertTrue(R['state']['state_files']['objects.pkl'].startswith('state/'))
        self.assertEqual(R['numbers']['ocg']['o6_wallcls'], None)                         # no ocg_wallcls.json - «—»
        self.assertTrue(os.path.exists(os.path.join(ref, 'result__v001', 'подробный__synth_engineering.dxf')))
        out = os.path.join(self.d, 'regress.json')
        r = subprocess.run([sys.executable, os.path.join(OCG, 'regress_check.py'), self.run_, ref, out], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        res = json.load(open(out)); self.assertEqual(res['verdict'], 'ПРОЙДЕНО'); self.assertTrue(res['measures']['same'])
        self.assertEqual(res['reference_files']['version'], 'v001')
        r = subprocess.run([sys.executable, os.path.join(OCG, 'regress_check.py'), '--self', ref], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr); self.assertIn('ПРОЙДЕНО', r.stdout)
        r = self.mk(ref, self.same); self.assertEqual(r.returncode, 0, r.stdout + r.stderr)              # a second one - a new file, v002
        self.assertTrue(os.path.exists(os.path.join(ref, 'reference__v002.json')))
        self.assertEqual(ref_lib.pick(ref)[2], 'v002')

    def test_2_other_drawing_stops(self):
        ref = os.path.join(self.d, 'ref_bad')
        r = self.mk(ref, self.other)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr); self.assertIn('Р1', r.stdout)
        self.assertFalse(os.path.exists(ref) and any(f.startswith('reference') for f in os.listdir(ref)))

    def test_3_changed_code_stops(self):
        run2 = make_run(os.path.join(self.d, 'run2'))
        with open(os.path.join(run2, 'cfg.py'), 'a') as f: f.write('# changed after the start of the run\n')
        r = subprocess.run([sys.executable, os.path.join(OCG, 'regress_check.py'), run2, os.path.join(self.d, 'ref_ok')], capture_output=True, text=True)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr); self.assertIn('Р2', r.stdout)
        r = self.mk(os.path.join(self.d, 'ref_r2'), self.same)
        self.assertEqual(r.returncode, 0)                      # the first run is untouched
        r = subprocess.run([sys.executable, os.path.join(OCG, 'make_reference.py'), run2, os.path.join(self.d, 'ref_r2b'), '--export-script', self.same],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 2); self.assertIn('Р2', r.stdout)

    def test_4_other_measures_not_valid(self):
        ref = os.path.join(self.d, 'ref_old'); r = self.mk(ref, self.same); self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        p = os.path.join(ref, 'reference__v001.json'); R = json.load(open(p)); R.pop('measures_version'); json.dump(R, open(p, 'w'))
        r = subprocess.run([sys.executable, os.path.join(OCG, 'regress_check.py'), self.run_, ref], capture_output=True, text=True)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr); self.assertIn('РАЗНЫЕ ВЕРСИИ МЕР', r.stdout)
        r = subprocess.run([sys.executable, os.path.join(OCG, 'regress_check.py'), self.run_, ref, '--allow-other-measures'], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('РАЗНЫЕ ВЕРСИИ МЕР', r.stdout)                 # check of step 11: the flag is said in the head (35 §3, п. 5)

    def test_6_allow_missing_is_said(self):
        # check of step 11: a needed report let off by OCG_REF_ALLOW_MISSING - «СНЯТ СТОП» in the output, allowed_missing in the head
        run3 = make_run(os.path.join(self.d, 'run3')); os.remove(os.path.join(run3, 'doors_fit.json'))
        e = dict(os.environ, OCG_REF_ALLOW_MISSING='doors_fit')
        ref = os.path.join(self.d, 'ref_allow')
        r = subprocess.run([sys.executable, os.path.join(OCG, 'make_reference.py'), run3, ref, '--export-script', self.same], capture_output=True, text=True)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)                                   # without the variable - a stop
        r = subprocess.run([sys.executable, os.path.join(OCG, 'make_reference.py'), run3, ref, '--export-script', self.same], capture_output=True, text=True, env=e)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr); self.assertIn('СНЯТ СТОП OCG_REF_ALLOW_MISSING', r.stdout)
        self.assertEqual(json.load(open(os.path.join(ref, 'reference__v001.json')))['allowed_missing'], ['doors_fit.json'])
        out = os.path.join(self.d, 'regress_allow.json')
        r = subprocess.run([sys.executable, os.path.join(OCG, 'regress_check.py'), run3, ref, out], capture_output=True, text=True, env=e)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr); self.assertIn('СНЯТ СТОП OCG_REF_ALLOW_MISSING', r.stdout)
        self.assertEqual(json.load(open(out))['allowed_missing'], dict(run=['doors_fit.json'], reference=['doors_fit.json']))

    def test_8_report_of_another_state_stops(self):
        # check of step 11 (Р1; the mutant «no state check» of ref_state passed all 13 tests): a check started from another state
        # than the export - its report is not of the delivered drawing - the reference and the check stop
        run4 = make_run(os.path.join(self.d, 'run4'), report_from_other_state=True)
        r = subprocess.run([sys.executable, os.path.join(OCG, 'make_reference.py'), run4, os.path.join(self.d, 'ref_r1x'), '--export-script', self.same],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr); self.assertIn('начат с другого состояния', r.stdout)
        self.assertIn('doors_fit', r.stdout)
        ref = os.path.join(self.d, 'ref_r1base'); r = self.mk(ref, self.same); self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        r = subprocess.run([sys.executable, os.path.join(OCG, 'regress_check.py'), run4, ref], capture_output=True, text=True)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr); self.assertIn('начат с другого состояния', r.stdout)

    def test_7_crash_is_a_stop(self):
        # check of step 11: a crash of the check (here a reference without its numbers) - STOP, exit 2, not exit 1 «НЕ ПРОЙДЕНО»
        ref = os.path.join(self.d, 'ref_crash'); r = self.mk(ref, self.same); self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        p = os.path.join(ref, 'reference__v001.json'); R = json.load(open(p)); R.pop('numbers'); json.dump(R, open(p, 'w'))
        r = subprocess.run([sys.executable, os.path.join(OCG, 'regress_check.py'), self.run_, ref], capture_output=True, text=True)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr); self.assertIn('STOP regress_check: сверка упала', r.stdout)

    def test_5_other_env_stops(self):
        # check of step 11: the journal keeps the environment of the result; a check in another one (curves.py CV_*) - STOP
        ref = os.path.join(self.d, 'ref_env'); r = self.mk(ref, self.same); self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(json.load(open(os.path.join(ref, 'reference__v001.json')))['state']['journal']['env'], runlog.env_params())
        e = dict(os.environ, CV_RATIO='3.0')
        r = subprocess.run([sys.executable, os.path.join(OCG, 'regress_check.py'), self.run_, ref], capture_output=True, text=True, env=e)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr); self.assertIn('окружение', r.stdout)


if __name__ == '__main__':
    unittest.main()
