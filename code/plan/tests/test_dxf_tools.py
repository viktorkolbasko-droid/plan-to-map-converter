"""Маленькие тесты `review/dxf_classes.py` и `review/blind_tiles_dxf.py` на синтетических DXF (ОЧ-51).

Запуск: PLAN_CODE=<папка code/plan> python3 -m unittest discover -s tests -v   (из папки над review/ и tests/)
Что проверяют: разбор слоя ISO; счёт объектов, длины, площади по классам; «0 против N» и перенос класса при другом
начале координат; стоп при разных листах; плитки — сетка, выборка с фиксированным зерном (повторяемость, зависимость
от зерна), знак сдвига по месту на листе, ключ отдельно и без имён вариантов в tiles.json.
"""
import os, sys, json, tempfile, unittest, subprocess
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'review'))
import ezdxf
import dxf_classes as DC
import blind_tiles_dxf as BT


def make_dxf(path, ox=0.0, oy=0.0, pk_layer='A-68----E-', sink_layer='A-73----E-', extra=None):
    """этаж 20 × 10 м: стены-коробка с заливкой, колонна, 3 шкафа ПК и 2 мойки вставками, текст марки"""
    doc = ezdxf.new('R2018'); doc.units = 4; msp = doc.modelspace()
    for n in ('A-221---E-', 'A-221---H-', 'A-28----E-', 'A-28----H-', 'A-68----E-', 'A-73----E-', 'A-AXM---E-', 'A-82----E-', 'A-90----T-', 'XYZ'):
        if n not in doc.layers: doc.layers.add(n)
    blk = doc.blocks.new('BOX'); blk.add_lwpolyline([(0, 0), (600, 0), (600, 300), (0, 300)], close=True)
    def P(x, y): return (x + ox, y + oy)
    msp.add_lwpolyline([P(0, 0), P(20000, 0), P(20000, 10000), P(0, 10000)], close=True, dxfattribs={'layer': 'A-221---E-'})
    h = msp.add_hatch(dxfattribs={'layer': 'A-221---H-'})
    h.paths.add_polyline_path([P(0, 0), P(20000, 0), P(20000, 200), P(0, 200)], is_closed=True)   # 20 × 0,2 = 4 m²
    msp.add_lwpolyline([P(5000, 5000), P(5500, 5000), P(5500, 5500), P(5000, 5500)], close=True, dxfattribs={'layer': 'A-28----E-'})
    for i in range(3): msp.add_blockref('BOX', P(1000 + 3000 * i, 9000), dxfattribs={'layer': pk_layer})
    for i in range(2): msp.add_blockref('BOX', P(15000 + 2000 * i, 3000), dxfattribs={'layer': sink_layer})
    msp.add_text('ПК', dxfattribs={'layer': 'A-90----T-', 'insert': P(1000, 9500)})
    if extra: extra(msp, P)
    doc.saveas(path); return path


class T(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.makedirs(os.path.join(ROOT, 'tests', '_tmp'), exist_ok=True); cls.d = tempfile.mkdtemp(dir=os.path.join(ROOT, 'tests', '_tmp'))
        cls.a = make_dxf(os.path.join(cls.d, 'a.dxf'), 0, 0, pk_layer='A-AXM---E-', sink_layer='A-82----E-')   # "LOW": wrong classes
        cls.b = make_dxf(os.path.join(cls.d, 'b.dxf'), -7000, -3000)                                           # "MAX": other origin

    def test_split_layer(self):
        self.assertEqual(DC.split_layer('A-68----E-'), ('A-68', 'E'))
        self.assertEqual(DC.split_layer('A-AXM---E-'), ('A-AXM', 'E'))
        self.assertEqual(DC.split_layer('A-22G---H-'), ('A-22G', 'H'))
        self.assertEqual(DC.split_layer('0'), ('0', '?'))

    def test_counts(self):
        r = DC.read(self.b)['by_class']
        self.assertEqual(r['A-68']['objects'], 3); self.assertEqual(r['A-68']['inserts'], 3)
        self.assertAlmostEqual(r['A-68']['length_m'], 3 * 1.8, places=2)       # 3 boxes 600 × 300
        self.assertAlmostEqual(r['A-221']['area_m2'], 4.0, places=2)
        self.assertEqual(r['A-90']['texts'], 1); self.assertEqual(r['A-90']['objects'], 0)

    def test_compare_and_moved(self):
        a, b = DC.read(self.a, True), DC.read(self.b, True)
        dx, dy, res, how = DC.parse_shift('auto', a, b)
        self.assertAlmostEqual(dx, 7000, delta=1); self.assertAlmostEqual(dy, 3000, delta=1); self.assertLess(res, 1)
        rows, only = DC.compare(a, b, DC.class_desc(DC.layer_table()), set())
        self.assertEqual(sorted(only), ['A-68', 'A-73', 'A-82', 'A-AXM'])
        self.assertEqual(rows['A-68']['delta']['objects'], 3); self.assertEqual(rows['A-AXM']['delta']['objects'], -3)
        mv = {(m['src'], m['dst']): m['n'] for m in DC.moved(a, b, dx, dy, 150)}
        self.assertEqual(mv, {('A-AXM', 'A-68'): 3, ('A-82', 'A-73'): 2})

    def test_cli_strict(self):
        env = dict(os.environ)
        r = subprocess.run([sys.executable, '-I', os.path.join(ROOT, 'review', 'dxf_classes.py'), self.a, self.b, '--names=L,M', '--strict',
                            '--out=' + os.path.join(self.d, 'c.json')], capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode, 1, r.stderr); self.assertIn('0 против 3', r.stdout)
        j = json.load(open(os.path.join(self.d, 'c.json'))); self.assertEqual(j['only_one'], ['A-68', 'A-73', 'A-82', 'A-AXM'])

    def test_stop_other_sheet(self):
        c = make_dxf(os.path.join(self.d, 'c.dxf'), extra=lambda msp, P: msp.add_lwpolyline([P(0, 0), P(30000, 0)], dxfattribs={'layer': 'A-221---E-'}))
        with self.assertRaises(SystemExit) as e:
            DC.parse_shift('auto', DC.read(self.a), DC.read(c))
        self.assertIn('СТОП', str(e.exception.code))

    def test_place_shift_sign(self):
        # the same point of the sheet: X = (x_pt - OX)·K, Y = (OY - y_pt)·K; second -> first
        K, ox0, oy0, ox1, oy1, xp, yp = 48.04, 523.04, 1557.76, 1151.979, 1444.826, 900.0, 1200.0
        X0, Y0 = (xp - ox0) * K, (oy0 - yp) * K; X1, Y1 = (xp - ox1) * K, (oy1 - yp) * K
        self.assertAlmostEqual(X1 + (ox1 - ox0) * K, X0, places=6); self.assertAlmostEqual(Y1 + (oy0 - oy1) * K, Y0, places=6)
        src = open(os.path.join(ROOT, 'review', 'blind_tiles_dxf.py'), encoding='utf-8').read()
        self.assertIn('shift = ((ox1 - ox0) * K, (oy0 - oy1) * K', src)

    def test_sample_fixed_seed(self):
        P, _ = BT.primitives(self.b, DC.layer_table())
        bb = BT.building_box([P])
        t1, c1 = BT.sample_tiles(bb, [P], 3, 2000, 7, min_prims=1)
        t2, c2 = BT.sample_tiles(bb, [P], 3, 2000, 7, min_prims=1)
        t3, _ = BT.sample_tiles(bb, [P], 3, 2000, 8, min_prims=1)
        self.assertEqual(t1, t2); self.assertEqual(c1, c2); self.assertNotEqual(t1, t3)
        self.assertEqual(len(BT.grid_tiles(bb, 4, 3)), 12)
        self.assertEqual(BT.seed_from([self.a, self.b]), BT.seed_from([self.a, self.b]))
        self.assertNotEqual(BT.seed_from([self.a, self.b]), BT.seed_from([self.b, self.a]))

    def test_tiles_blind_key(self):
        out = os.path.join(self.d, 'tiles')
        r = subprocess.run([sys.executable, '-I', os.path.join(ROOT, 'review', 'blind_tiles_dxf.py'), out, 'LOWNAME=' + self.a, 'MAXNAME=' + self.b,
                            '--grid=2x1', '--ppm=20'], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        meta = open(os.path.join(out, 'tiles.json'), encoding='utf-8').read()
        self.assertNotIn('LOWNAME', meta); self.assertNotIn('MAXNAME', meta)
        key = BT.read_key(os.path.join(out, '.k')); self.assertEqual(sorted(key), ['t01', 't02'])
        self.assertEqual(sorted(key['t01'].values()), ['LOWNAME', 'MAXNAME'])
        j = json.loads(meta); self.assertEqual(j['shift_second_mm']['how'], 'auto'); self.assertAlmostEqual(j['shift_second_mm']['dx'], 7000, delta=1)
        for t in j['tiles']:
            for f in t['files'].values(): self.assertTrue(os.path.exists(os.path.join(out, f)))

    def test_pdf_without_place_stops(self):
        r = subprocess.run([sys.executable, '-I', os.path.join(ROOT, 'review', 'blind_tiles_dxf.py'), os.path.join(self.d, 't2'), 'X=' + self.a,
                            '--pdf=' + os.path.join(self.d, 'none.pdf')], capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0); self.assertIn('СТОП', r.stderr + r.stdout)


if __name__ == '__main__':
    unittest.main()
