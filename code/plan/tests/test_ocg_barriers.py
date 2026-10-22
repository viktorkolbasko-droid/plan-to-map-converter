"""Тесты барьера у стола (СО-2, код 012): `ocg/barriers.py` (вердикт полос слоя стен со свободным концом) и
`ocg/barrier_desk.py` (полоса отдаётся объекту стола после Э7м).

Запуск: python3 -m unittest discover -s code/plan/tests -v   (из корня репозитория)
Синтетика в pt при 48,04 мм/pt: полоса 1 × 20 pt (48 × 961 мм); стол — заливка; стена — тело; допуск касания = толщина полосы.
"""
import os, sys, json, pickle, pickle, shutil, tempfile, unittest, subprocess
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OCG = os.path.join(ROOT, 'ocg'); sys.path.insert(0, OCG)
import barriers as BR
from shapely.geometry import box, Polygon


def dump(o, p):
    with open(p, 'wb') as f: pickle.dump(o, f)


def wtext(p, t):
    with open(p, 'w', encoding='utf-8') as f: f.write(t)


def rtext(p):
    with open(p, encoding='utf-8') as f: return f.read()


def rjson(p):
    with open(p, encoding='utf-8') as f: return json.load(f)


def rpickle(p):
    with open(p, 'rb') as f: return pickle.load(f)

K = 48.04
STRIP = box(100, 100, 101, 120)                       # вертикальная полоса, концы y = 100 и y = 120
DESK = box(90, 95, 110, 100.5)                        # верхний конец полосы — на столе (внутри заливки)
WALL_FAR = box(200, 0, 205, 300)


class StripVerdicts(unittest.TestCase):
    def v(self, comps, desks=(), car=()):
        return [r for _, r in BR.strip_verdicts(list(comps), list(desks), list(car), K)]

    def test_barrier_one_end_on_desk_other_free(self):
        r = self.v([STRIP, WALL_FAR], [DESK])
        self.assertEqual(len(r), 1); self.assertEqual(r[0]['verdict'], BR.BARRIER)
        self.assertEqual(sorted(r[0]['ends']), ['свободный', 'стол'])

    def test_end_on_desk_but_other_end_at_wall_stays_wall(self):
        wall = box(95, 120.5, 106, 130)                # нижний конец в 0,5 pt от стены (< толщины 1 pt)
        r = self.v([STRIP, wall], [DESK])
        self.assertTrue(r[0]['verdict'].startswith('стена: один конец'))

    def test_column_or_facade_counts_as_wall(self):
        col = box(99, 121, 103, 125)                   # колонна в 1 pt от конца — на границе допуска
        r = self.v([STRIP], [DESK], [col])
        self.assertTrue(r[0]['verdict'].startswith('стена'))

    def test_touch_tolerance_is_thickness(self):
        desk_far = box(90, 95, 110, 98.9)              # 1,1 pt от конца при толщине 1 pt — не касается
        r = self.v([STRIP], [desk_far])
        self.assertTrue(r[0]['verdict'].startswith('стена, на просмотр'))

    def test_both_ends_at_walls_not_listed(self):
        self.assertEqual(self.v([STRIP, box(95, 95, 106, 99.5), box(95, 120.5, 106, 125)], [DESK]), [])

    def test_thick_short_or_bent_not_a_strip(self):
        self.assertEqual(self.v([box(100, 100, 104, 120)], [DESK]), [])          # 192 мм толщины > 150 мм
        self.assertEqual(self.v([box(100, 100, 101, 105)], [DESK]), [])          # 240 мм длины < 300 мм
        L = Polygon([(100, 100), (101, 100), (101, 119), (120, 119), (120, 120), (100, 120)])
        self.assertEqual(self.v([L], [DESK]), [])                                # уголок — не прямая полоса


class BarrierToDesk(unittest.TestCase):
    def test_lpart_goes_to_desk_object(self):
        d = tempfile.mkdtemp(); self.addCleanup(shutil.rmtree, d, True)
        wtext(os.path.join(d, 'cfg.py'), "PDF = 'x.pdf'\nMM_PER_PT = 48.04\nOCG_LAYERS = [dict(layer='M', role='furniture'), dict(layer='W', role='wall')]\n")
        P = [dict(id=0, layer='M', kind='fill', p=list(DESK.exterior.coords), col=(0.843,) * 3),
             dict(id=1, layer='W', kind='line', p=list(STRIP.exterior.coords), col=(0, 0, 0)),
             dict(id=2, layer='M', kind='line', p=[(90, 95), (110, 95)], col=(0, 0, 0))]
        objs = [dict(key='counter', layer='A-82', name='Стойка', ids=[2, 0], draw=[2], kind='obj'),
                dict(key='lpart', layer='A-22G', name='Перегородка без штриховки', ids=[1], kind='obj')]
        dump(dict(objs=objs, owner={0: 0, 2: 0, 1: 1}, wall_in={}), os.path.join(d, 'objects.pkl'))
        dump(dict(P=P, T=[]), os.path.join(d, 'prims_f.pkl'))
        dump(dict(bodies=[], barriers=[dict(g=STRIP, pids=[1], desk=DESK, faces=1, at_pt=[100.5, 110], size_mm=[961, 48])]),
             os.path.join(d, 'walls.pkl'))
        r = subprocess.run([sys.executable, os.path.join(OCG, 'barrier_desk.py')], cwd=d, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        O = rpickle(os.path.join(d, 'objects.pkl'))
        self.assertIn(1, O['objs'][0]['ids']); self.assertIn(1, O['objs'][0]['draw']); self.assertEqual(O['owner'][1], 0)
        self.assertEqual(O['objs'][1]['key'], 'empty')
        self.assertEqual(rjson(os.path.join(d, 'barriers.json'))['barriers'][0]['desk_key'], 'counter')

    def test_no_desk_object_stops(self):
        d = tempfile.mkdtemp(); self.addCleanup(shutil.rmtree, d, True)
        wtext(os.path.join(d, 'cfg.py'), "PDF = 'x.pdf'\nMM_PER_PT = 48.04\nOCG_LAYERS = [dict(layer='M', role='furniture'), dict(layer='W', role='wall')]\n")
        dump(dict(objs=[dict(key='lpart', layer='A-22G', name='-', ids=[0], kind='obj')], owner={0: 0}, wall_in={}), os.path.join(d, 'objects.pkl'))
        dump(dict(P=[dict(id=0, layer='W', kind='line', p=list(STRIP.exterior.coords), col=(0, 0, 0))], T=[]), os.path.join(d, 'prims_f.pkl'))
        dump(dict(bodies=[], barriers=[dict(g=STRIP, pids=[0], desk=DESK, faces=1, at_pt=[100.5, 110], size_mm=[961, 48])]), os.path.join(d, 'walls.pkl'))
        r = subprocess.run([sys.executable, os.path.join(OCG, 'barrier_desk.py')], cwd=d, capture_output=True, text=True)
        self.assertEqual(r.returncode, 3, r.stdout + r.stderr); self.assertIn('СТОП', r.stdout)


if __name__ == '__main__':
    unittest.main()
