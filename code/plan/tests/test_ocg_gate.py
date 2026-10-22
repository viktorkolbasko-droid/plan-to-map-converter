"""Тесты шлюза маршрута по слоям `ocg/gate_ocg.py` (проверка шага 11, код 012) — на синтетических отчётах, без листа клиента.

Запуск: python3 -m pytest -q tests/test_ocg_gate.py   (из папки code/plan)
Что проверяют:
 - чистые отчёты — шлюз пройден (exit 0);
 - `ocg_checks.json` без записи, которую читают остановки (walls и её части, joints_final, walls_as_lines_outside_core,
   doors_no_opening), — остановка O0, а не молчаливый 0 у O1–O5, O7, O8; старая форма `joints.after.bodies` принимается;
 - остановки старта, снятые полями cfg (OCG_ROLE_OK, OCG_ORIGIN_OK, OCG_SCALE_OK; заметки `ocg_start*.json`), — строками
   «принято старт» в выводе шлюза и в `ocg_gate.json` info.start_lifted.
"""
import copy, json, os, shutil, subprocess, sys, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GATE = os.path.join(ROOT, 'ocg', 'gate_ocg.py')
CFG = "PDF = None\nOUT = 't'\nMM_PER_PT = 48.04; ORIGIN_PT = (0.0, 0.0)\nOCG_LAYERS = [dict(layer='W', role='wall')]\n"
CHECKS = dict(walls=dict(bodies=1, vertices=4, straight_run_reasons={}, holes=dict(n=0, voids=0, places=[]), short_edges=dict(by_reason={}, not_justified=[]),
                         breaks_without_door=dict(n=0, places=[])),
              joints_final=dict(bodies={}, n=0, places=[]), walls_as_lines_outside_core=dict(n=0), doors_no_opening=dict(n=0),
              door_ends=dict(ends=0, off_face=0, tol_mm=14.4, places=[]), hanging_lines=dict(n=0), furniture=dict(left_for_review={}))
OTHER = {'doors_check.json': dict(bad=[]), 'ocg_wallcls.json': dict(n=0), 'ocg_compose.json': dict(checked=[], skipped='нет OCG_REF_DXF'),
         'ocg_layers_detail.json': dict(no_record={}, no_description={}, texts_off_TD={}),
         'ocg_layers_outline.json': dict(no_record={}, no_description={}, texts_off_TD={})}


class Gate(unittest.TestCase):
    def run_gate(self, checks, extra=None):
        d = tempfile.mkdtemp(prefix='gate_'); self.addCleanup(shutil.rmtree, d, True)
        with open(os.path.join(d, 'cfg.py'), 'w', encoding='utf-8') as f: f.write(CFG)
        for name, data in dict(OTHER, **{'ocg_checks.json': checks}, **(extra or {})).items():
            with open(os.path.join(d, name), 'w', encoding='utf-8') as f: json.dump(data, f, ensure_ascii=False)
        r = subprocess.run([sys.executable, GATE], cwd=d, capture_output=True, text=True)
        with open(os.path.join(d, 'ocg_gate.json'), encoding='utf-8') as f: g = json.load(f)
        return r.returncode, r.stdout + r.stderr, g

    def test_clean_reports_pass(self):
        rc, out, g = self.run_gate(CHECKS)
        self.assertEqual(rc, 0, out); self.assertIn('пройден', out); self.assertEqual(g['stops'], [])

    def test_missing_record_is_O0_not_zero(self):
        for path in (('walls',), ('walls', 'holes'), ('walls', 'breaks_without_door'), ('joints_final',), ('doors_no_opening',),
                     ('walls_as_lines_outside_core',)):
            C = copy.deepcopy(CHECKS); d_ = C
            for k in path[:-1]: d_ = d_[k]
            d_.pop(path[-1])
            rc, out, g = self.run_gate(C)
            self.assertEqual(rc, 1, f'{path}: {out}')
            o0 = [s for s in g['stops'] if s['code'] == 'O0' and not s['accepted']]
            self.assertTrue(o0 and path[-1] in o0[0]['what'], f'{path}: {g["stops"]}')

    def test_joints_after_of_older_report_is_enough(self):
        C = copy.deepcopy(CHECKS); C.pop('joints_final'); C['joints'] = dict(after=dict(bodies={}))
        rc, out, g = self.run_gate(C)
        self.assertEqual(rc, 0, out)

    def test_lifted_start_stops_are_listed(self):
        notes = ['роль слоя «Шкафы» подтверждена cfg.OCG_ROLE_OK: разметка на картинке (3 фигур ≥ 300 мм)', 'начало — оси 1 × A (первые оси)']
        e3 = ['масштаб Э3 не измерен (нет размеров) — идёт по cfg.OCG_SCALE_OK (так в исходнике): кадр places/x.png']
        rc, out, g = self.run_gate(CHECKS, {'ocg_start.json': dict(ok=True, stops=[], notes=notes), 'ocg_start_e3.json': dict(ok=True, stops=[], notes=e3)})
        self.assertEqual(rc, 0, out)
        self.assertEqual(len(g['info']['start_lifted']), 2, g['info'])
        lines = [l for l in out.splitlines() if 'принято' in l and 'старт' in l]
        self.assertEqual(len(lines), 2, out); self.assertIn('cfg.OCG_ROLE_OK', lines[0]); self.assertIn('cfg.OCG_SCALE_OK', lines[1])


class StandCases(unittest.TestCase):
    """check of step 11: a stand given an unknown case ran nothing and printed «поймано 0 из 0» / «0 caught of 0» - a stop now"""
    def test_unknown_case_stops(self):
        for script, bad in ((os.path.join(ROOT, 'ocg', 'stand_ocg.py'), 'Z'), (os.path.join(ROOT, 'review', 'gate_stand.py'), 'V1')):
            d = tempfile.mkdtemp(prefix='stand_'); self.addCleanup(shutil.rmtree, d, True)
            out = os.path.join(d, 'out')
            r = subprocess.run([sys.executable, script, os.path.join(d, 'no_run'), os.path.join(d, 'no_code'), out, bad], capture_output=True, text=True)
            self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr); self.assertIn(bad, r.stdout + r.stderr)
            self.assertFalse(os.path.exists(out), script)

    def test_groups_of_gate_stand_are_its_want_calls(self):
        import re
        src = open(os.path.join(ROOT, 'review', 'gate_stand.py'), encoding='utf-8').read()
        m = re.search(r"^GROUPS = \(([^)]*)\)", src, re.M)
        self.assertEqual(set(re.findall(r"want\('([^']+)'\)", src)), set(re.findall(r"'([^']+)'", m.group(1))))


if __name__ == '__main__':
    unittest.main()
