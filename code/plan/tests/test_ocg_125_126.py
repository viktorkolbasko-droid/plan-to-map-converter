"""Тесты решений владельца 10.10.2026 №125 и №126 (код 012, шаг 8б) — синтетика.

Запуск: python3 -m pytest -q code/plan/tests
Что проверяют:
- №125 «Как части — вид 012» (Э7к, e7k_classes.py): у кухни из частей подробный результат рисует объединение того, что
  рисовали её части (их 'draw', у части без него — все её примитивы); габарит кухни (заливка + контур) — только в 'outline',
  в 'draw' его нет; состав рисования не зависит от номеров объектов: тот же лист с другим порядком объектов и лишними
  объектами впереди даёт те же примитивы рисования и тот же габарит;
- №126 «Вид 012, поправить проверку» (doors_fit.py): торец на уступе — элемент за торцом идёт поперёк оси проёма и шире
  проёма, касается торца хотя бы частью (в том числе только углом) без зазора — «в проёме», хотя откос (грань поперечной
  стены) длиннее проёма; зазор 30 мм — не «в проёме» (щель 30 мм); элемент поперёк, но уже проёма (откос не покрывает
  глубину) — не «в проёме»;
  щель у торца — зазор, а не непокрытая часть торца (стена тоньше проёма касается торца — щель 0, а не 50 мм до следующей).
"""
import json, os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_ocg_v010 import Base, cfg_text, save, line
from shapely.geometry import box

K = 48.04


def fill(i, layer, x0, y0, x1, y1, k=K):
    s = 1.0 / k
    return dict(id=i, layer=layer, kind='fill', p=[(x0 * s, y0 * s), (x1 * s, y0 * s), (x1 * s, y1 * s), (x0 * s, y1 * s)],
                col=(0.9, 0.9, 0.9), alpha=1.0, seq=i, holes=[])


class KitchenFromParts(Base):
    """№125: two touching sections 600 mm deep along a wall and a sink inside — one kitchen"""
    def state(self, order, dummies, b_first=False):
        s = 1.0 / K
        P = [fill(0, 'Мебель', 0, 0, 1200, 600), line(1, 'Мебель', (100 * s, 100 * s), (1100 * s, 100 * s)),      # section A: draws [0]
             fill(2, 'Мебель', 1200, 0, 2400, 600), line(3, 'Мебель', (1300 * s, 100 * s), (2300 * s, 100 * s)),  # section B: no draw
             fill(4, 'Сантехника', 1500, 100, 1900, 500)]                                                         # a sink in B
        if b_first: P[2]['seq'], P[3]['seq'] = -2, -1        # check of step 11: B (no 'draw') is the first part of the source
        parts = {'A': dict(key='kitchen', layer='A-76', name='Кухня встроенная: секция 1200×600 (по исходнику)', ids=[0, 1], draw=[0], kind='obj'),
                 'B': dict(key='kitchen', layer='A-76', name='Столешница кухонная 1200×600 (по исходнику)', ids=[2, 3], kind='obj'),
                 'S': dict(key='sink', layer='A-75', name='Мойка (по исходнику)', ids=[4], kind='obj')}
        objs = [dict(key='zone', layer='A-92', name='лишний', ids=[], kind='obj') for _ in range(dummies)] + [dict(parts[c]) for c in order]
        for o in objs: o['ids'] = list(o['ids']); o.get('draw') is not None and o.update(draw=list(o['draw']))
        d = self.folder(cfg_text(k=K))
        save(d, 'prims_o.pkl', dict(P=P, T=[])); save(d, 'objects.pkl', dict(objs=objs, owner={}))
        save(d, 'walls_o.pkl', dict(bodies=[('gkl', box(-500 * s, -150 * s, 3000 * s, -20 * s))]))
        return d

    def kitchen(self, d):
        import pickle
        r = self.script(d, 'e7k_classes.py'); self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        O = pickle.load(open(os.path.join(d, 'objects.pkl'), 'rb'))['objs']; P = pickle.load(open(os.path.join(d, 'prims_k.pkl'), 'rb'))['P']
        ks = [o for o in O if o['key'] == 'kitchen' and o['ids']]
        self.assertEqual(len(ks), 1, [o['name'] for o in ks]); o = ks[0]
        out = [tuple(P[i]['p']) for i in o['outline']]
        return set(o['draw']), set(o['ids']), out, o

    def test_draw_is_what_parts_drew_outline_only_in_outline(self):
        dr, ids, out, o = self.kitchen(self.state('ABS', 0))
        self.assertEqual(dr, {0, 2, 3, 4})                       # A drew its top (0); B and the sink — everything
        self.assertTrue(set(o['outline']).isdisjoint(dr))        # the габарит — not in the detailed result
        self.assertEqual(len(o['outline']), 2)
        self.assertTrue({0, 1, 2, 3, 4} <= ids)                  # every primitive of the parts stays the kitchen's own

    def test_independent_of_object_numbers(self):
        ref = self.kitchen(self.state('ABS', 0))[:3]
        for order, dummies in (('BAS', 0), ('SBA', 3), ('BSA', 7)):
            self.assertEqual(self.kitchen(self.state(order, dummies))[:3], ref, f'{order}, {dummies}')

    def test_order_of_drawing_independent_of_object_numbers(self):
        # check of step 11 (the mutant «parts sorted by object number» passed - the sets above were the same): the order of the
        # kitchen's primitives - the z-order of the export - is by the source, whatever the numbers of the objects
        ref = self.kitchen(self.state('ABS', 0))[3]
        for order, dummies in (('BAS', 0), ('SBA', 3)):
            o = self.kitchen(self.state(order, dummies))[3]
            self.assertEqual((o['draw'], o['ids']), (ref['draw'], ref['ids']), f'{order}, {dummies}')

    def test_first_part_without_draw(self):
        # check of step 11 (the mutant «the host's draw only if it had one, as v010» passed - the first part always had 'draw'):
        # the first part of the source has no 'draw' - the kitchen still draws what the parts drew, the габарит only in 'outline'
        dr, ids, out, o = self.kitchen(self.state('ABS', 0, b_first=True))
        self.assertEqual(dr, {0, 2, 3, 4}); self.assertTrue(set(o['outline']).isdisjoint(dr))


def door_state(test, bodies_mm, strokes_mm, k=K):
    """one door 900 mm wide along x (0…900 mm), 100 mm deep (y 0…100); its left end in line with a straight wall"""
    s = 1.0 / k
    ring = [(0, 0), (900 * s, 0), (900 * s, 100 * s), (0, 100 * s), (0, 0)]
    P = [dict(id=0, layer='Двери', kind='line', p=ring, col=(0.0, 0.0, 0.0), alpha=1.0, seq=0, w=0, synthetic=True, opening=True, closed=True)]
    for (a, b) in strokes_mm: P.append(line(len(P), 'Стены', (a[0] * s, a[1] * s), (b[0] * s, b[1] * s)))
    objs = [dict(key='door', layer='A-61', name='Дверь однопольная 800', ids=[0], draw=[0], kind='obj')]
    bodies = [('gkl', box(-2000 * s, 0, 0, 100 * s))] + [('gkl', box(x0 * s, y0 * s, x1 * s, y1 * s)) for x0, y0, x1, y1 in bodies_mm]
    d = test.folder(cfg_text(k=k, layers=[('Стены', 'wall'), ('Двери', 'door'), ('Мебель', 'furniture')]))
    save(d, 'prims_o.pkl', dict(P=P, T=[])); save(d, 'objects.pkl', dict(objs=objs, owner={}))
    save(d, 'walls_o.pkl', dict(bodies=bodies))
    r = test.script(d, 'doors_fit.py'); test.assertEqual(r.returncode, 0, r.stdout + r.stderr)
    return json.load(open(os.path.join(d, 'doors_fit.json')))['all'][0]


class DoorOnStep(Base):
    """№126: the right end of the door against a wall running across its axis"""
    JAMB = [((900, -400), (900, 100))]          # the face of the cross wall: 500 mm, longer than the opening's 100 mm

    def test_step_touching_no_gap_in_opening(self):
        r = door_state(self, [(900, -1000, 1000, 1000)], self.JAMB)
        self.assertEqual(r['status'], 'в проёме', r); self.assertEqual(r['end_gaps_mm'][1], 0); self.assertEqual(r['abut_mm'][1], 0)
        self.assertGreater(r['faces_off_mm'][1][0], 10)          # the jamb alone is off — the step decides

    def test_step_touching_by_corner_only(self):
        r = door_state(self, [(900, 100, 1000, 1500)], [])       # the cross wall starts at the far face: touches the end's corner
        self.assertEqual(r['status'], 'в проёме', r); self.assertEqual(r['end_gaps_mm'][1], 0)

    def test_gap_30mm_is_a_misfit(self):
        r = door_state(self, [(930, -1000, 1030, 1000)], self.JAMB)
        self.assertNotEqual(r['status'], 'в проёме', r); self.assertEqual(r['end_gaps_mm'][1], 30); self.assertFalse(r['gap_ok'])
        self.assertNotIn('abut_mm', r)

    def test_cross_element_shallower_than_opening_is_a_misfit(self):
        r = door_state(self, [(900, -1000, 1000, 1000)], [((900, 20), (900, 80))])
        self.assertNotEqual(r['status'], 'в проёме', r); self.assertNotIn('abut_mm', r)

    def test_gap_is_clearance_not_uncovered_part(self):
        # a thin wall in line (y 60…100) touches the end; a full wall 50 mm farther: v009 measured 50 mm at the middle
        r = door_state(self, [(900, 60, 2000, 100), (950, 0, 2000, 100)], [])
        self.assertEqual(r['end_gaps_mm'][1], 0, r); self.assertTrue(r['gap_ok'])


if __name__ == '__main__':
    unittest.main()
