"""Маленькие тесты `ocg/door_slices.py`, `ocg/e7o_openings.py`, `ocg/doors_fit.py` (код 012, этап 1 слияния v009: Т10-2).

Запуск: PLAN_CODE=<папка code/plan> python3 -m unittest discover -s tests -v   (из папки над ocg/ и tests/)
Что проверяют: сечение стены у конца проёма — грани прямой стены, «стабильно», «обрезано» у стены поперёк оси;
одна и та же стена в двух масштабах листа (48,04 и 24,02 мм/pt) — те же мм (пороги в мм через масштаб листа);
откос исходника — штрихи поперёк стены у конца, штрихи слоёв-исключений (по ролям) не считаются; Э7о и doors_fit без
слоёв роли wall или без масштаба — громкий стоп с причиной, а не пустой отчёт.
"""
import os, sys, tempfile, unittest, subprocess
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'ocg'))
from shapely.geometry import Polygon, box
import door_slices as DS


def walls_at(k, thick_mm=100.0, gap_mm=900.0, cross=False):
    """a wall along x with an opening gap_mm wide at x = 0..gap; the wall's faces at y = 0..thick (mm), drawn at k mm/pt.
    cross: the right part is a wall running across the axis (along y), 1000 mm long"""
    s = 1.0 / k
    left = box(-2000 * s, 0, 0, thick_mm * s)
    right = box(gap_mm * s, -500 * s, (gap_mm + thick_mm) * s, 500 * s) if cross else box(gap_mm * s, 0, (gap_mm + 2000) * s, thick_mm * s)
    return DS.Carriers([('стена gkl', left), ('стена gkl', right)])


class T(unittest.TestCase):
    def test_section_straight_wall(self):
        k = 48.04; C = walls_at(k); s = 1.0 / k
        r = DS.section(C, (0, 0), (1, 0), (0, 1), 900 * s, 1, 0.0, 100 * s, k)
        self.assertTrue(r['stable']); self.assertFalse(r['clipped'])
        self.assertAlmostEqual(r['lo'] * k, 0.0, delta=0.5); self.assertAlmostEqual(r['hi'] * k, 100.0, delta=0.5)
        self.assertEqual(r['cls'], 'стена gkl')

    def test_section_same_mm_at_two_scales(self):
        out = []
        for k in (48.04, 24.02):
            C = walls_at(k, thick_mm=125.0); s = 1.0 / k
            r = DS.section(C, (0, 0), (1, 0), (0, 1), 0.0, -1, 0.0, 125 * s, k)    # the left end, looking left
            out.append((round(r['lo'] * k, 1), round(r['hi'] * k, 1), r['stable']))
        self.assertEqual(out[0], out[1])
        self.assertEqual(out[0], (0.0, 125.0, True))

    def test_section_clipped_by_cross_wall(self):
        k = 48.04; C = walls_at(k, cross=True); s = 1.0 / k
        r = DS.section(C, (0, 0), (1, 0), (0, 1), 900 * s, 1, 0.0, 100 * s, k)
        self.assertTrue(r['clipped'])                       # the wall beyond the end runs across the axis: 1000 mm > 2 × 384 mm

    def test_jamb_and_excluded_roles(self):
        k = 48.04; s = 1.0 / k
        P = [dict(id=0, layer='Стены внутренние', kind='line', p=[(900 * s, -5 * s), (900 * s, 105 * s)]),     # a jamb across the wall
             dict(id=1, layer='Мебель', kind='line', p=[(905 * s, -300 * s), (905 * s, 300 * s)])]              # furniture: not a jamb
        from shapely.geometry import LineString
        geom = lambda p: LineString(p['p'])
        S = DS.Strokes(P, geom, ex_layers={'Мебель'})
        self.assertEqual(S.idx, [0])
        j = DS.jamb(S, (0, 0), (1, 0), (0, 1), 900 * s, 0.0, 100 * s, k)
        self.assertAlmostEqual(j['lo'] * k, -5.0, delta=0.5); self.assertAlmostEqual(j['hi'] * k, 105.0, delta=0.5)
        self.assertEqual(j['cls'], 'Стены внутренние')
        S2 = DS.Strokes(P, geom, ex_layers={'Мебель', 'Стены внутренние'})
        self.assertIsNone(DS.jamb(S2, (0, 0), (1, 0), (0, 1), 900 * s, 0.0, 100 * s, k))

    def test_no_scale_stops(self):
        C = walls_at(48.04)
        with self.assertRaises(SystemExit): DS.section(C, (0, 0), (1, 0), (0, 1), 0.0, -1, 0.0, 2.0, 0)

    def _run(self, script, cfg_text):
        os.makedirs(os.path.join(ROOT, 'tests', '_tmp'), exist_ok=True); d = tempfile.mkdtemp(dir=os.path.join(ROOT, 'tests', '_tmp'))
        open(os.path.join(d, 'cfg.py'), 'w', encoding='utf-8').write(cfg_text)
        env = dict(os.environ, PYTHONPATH=ROOT)
        return subprocess.run([sys.executable, os.path.join(ROOT, 'ocg', script)], cwd=d, capture_output=True, text=True, env=env)

    def test_e7o_and_doors_fit_stop_without_wall_role(self):
        cfg = ("PDF = None\nMM_PER_PT = 48.04\nORIGIN_PT = (0, 0)\n"
               "OCG_LAYERS = [dict(layer='Двери', role='door'), dict(layer='Мебель', role='furniture')]\n")
        for script, word in (('e7o_openings.py', 'СТОП Э7о'), ('doors_fit.py', 'СТОП doors_fit')):
            r = self._run(script, cfg)
            self.assertNotEqual(r.returncode, 0, script); self.assertIn(word, r.stderr + r.stdout); self.assertIn('роли wall', r.stderr + r.stdout)

    def test_e7o_stops_without_scale(self):
        cfg = "PDF = None\nORIGIN_PT = (0, 0)\nOCG_LAYERS = [dict(layer='Стены', role='wall')]\n"
        r = self._run('e7o_openings.py', cfg)
        self.assertNotEqual(r.returncode, 0); self.assertIn('MM_PER_PT', r.stderr + r.stdout)


class E7oEnds(unittest.TestCase):
    """check of step 11 (code 012, commit 756edc2): Э7о keeps an end Э7д drew on to a face ('ends_on_face') and measures the
    depth where that end stood before (at the door's frame); a rerun reads the bodies of Э7с (walls_j.pkl), not of Э7р.
    One door 900 mm wide along x (0…900 mm), 100 mm deep; the left end in line with a straight wall."""
    K = 48.04

    def run_e7o(self, bodies_mm, strokes_mm, ends_on_face=(), walls_r_mm=None):
        import pickle, json, shutil
        s = 1.0 / self.K
        d = tempfile.mkdtemp(prefix='e7o_'); self.addCleanup(shutil.rmtree, d, True)
        open(os.path.join(d, 'cfg.py'), 'w', encoding='utf-8').write(
            "PDF = None\nMM_PER_PT = 48.04\nORIGIN_PT = (0, 0)\nOCG_GLASS_COLORS = []\n"
            "OCG_LAYERS = [dict(layer='Стены', role='wall'), dict(layer='Двери', role='door'), dict(layer='Мебель', role='furniture')]\n")
        ring = [(0, 0), (900 * s, 0), (900 * s, 100 * s), (0, 100 * s), (0, 0)]
        P = [dict(id=0, layer='Двери', kind='line', p=ring, col=(0.0, 0.0, 0.0), alpha=1.0, seq=0, w=0, synthetic=True, opening=True)]
        for a, b in strokes_mm:
            P.append(dict(id=len(P), layer='Стены', kind='line', p=[(a[0] * s, a[1] * s), (b[0] * s, b[1] * s)], col=(0.0, 0.0, 0.0), alpha=1.0, seq=len(P), w=0))
        door = dict(key='door', layer='A-32', name='Дверь однопольная 900', ids=[0], draw=[0], marks=[], kind='obj',
                    ends_on_face=[dict(at=[x * s, y * s], back=bk * s) for (x, y), bk in ends_on_face])
        bx = lambda c, x0, y0, x1, y1: (c, box(x0 * s, y0 * s, x1 * s, y1 * s))
        pickle.dump(dict(P=P, T=[]), open(os.path.join(d, 'prims_c.pkl'), 'wb'))
        pickle.dump(dict(objs=[door], owner={0: 0}), open(os.path.join(d, 'objects.pkl'), 'wb'))
        pickle.dump(dict(bodies=[bx('gkl', *b) for b in bodies_mm]), open(os.path.join(d, 'walls_j.pkl'), 'wb'))
        if walls_r_mm is not None:      # the bodies of Э7р of an earlier run, left in the folder
            pickle.dump(dict(bodies=[bx('blk', *b) for b in walls_r_mm]), open(os.path.join(d, 'walls_r.pkl'), 'wb'))
        env = dict(os.environ, PYTHONPATH=ROOT, PYTHONHASHSEED='0')
        r = subprocess.run([sys.executable, os.path.join(ROOT, 'ocg', 'e7o_openings.py')], cwd=d, capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return json.load(open(os.path.join(d, 'openings.json')))['doors'][0]

    LEFT = (-2000, 0, 0, 100)                      # the straight wall in line with the left end
    CROSS = (900, -1000, 1000, 1000)               # a wall across the axis at the right end (its side is the face)

    def test_depth_measured_where_the_end_stood(self):
        # Э7д drew the right end 200 mm on from the frame (x 700) to the face of the cross wall; the frame's stroke at x 700 is the
        # jamb (10…90 mm); at the face itself there is no jamb - the depth is the mean of the wall (0…100) and the jamb: 90 mm
        r = self.run_e7o([self.LEFT, self.CROSS], [((700, 10), (700, 90))], ends_on_face=[((900, 50), 200)])
        self.assertEqual(r['ends_kept_e7d'], [1]); self.assertEqual(r['ends_measured_back_mm'], {'1': 200})
        self.assertEqual(r['ends'][1]['by'], 'откос исходника', r); self.assertEqual(r['thick_mm'], 90, r)
        self.assertEqual(r['width_mm'], 900)

    def test_end_on_face_not_moved(self):
        # a body 20 mm beyond the right end: an ordinary end goes on to it (step 3), the end Э7д drew on to a face stays
        r = self.run_e7o([self.LEFT, (920, 0, 2920, 100)], [])
        self.assertEqual(r['width_mm'], 920, r)
        r = self.run_e7o([self.LEFT, (920, 0, 2920, 100)], [], ends_on_face=[((900, 50), 5)])
        self.assertEqual(r['width_mm'], 900, r); self.assertNotIn('ends_moved_mm', r)

    def test_rerun_reads_walls_of_e7c_not_e7r(self):
        r = self.run_e7o([self.LEFT, (900, 0, 2900, 100)], [], walls_r_mm=[self.LEFT, (900, 0, 2900, 100)])
        self.assertEqual(r['ends'][0]['cls'], 'стена gkl', r); self.assertEqual(r['ends'][1]['cls'], 'стена gkl', r)


if __name__ == '__main__':
    unittest.main()
