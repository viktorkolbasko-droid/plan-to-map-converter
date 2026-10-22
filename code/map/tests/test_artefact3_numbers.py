"""Тест артефакта 3 (строка 181; ОВ11, Е13): номер места — белым поверх заливки стола, пятна столов считаются по маске заливки до номеров:
unspot_map.workplaces.render_draft (черновик 25 / 50 / 100, v013 — вместо render_variant_c) + count_marks и Ч-29 приёмки дают число пятен = числу мест.
Без внешних данных. Код v007, правка v013 (К13.1).
    python3 tests/test_artefact3_numbers.py — код 0, если всё совпало"""
import os, sys, tempfile, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from PIL import Image
from unspot_map.workplaces import render_draft, count_marks
import acceptance_checks as ac
bad = []
def check(name, got, want):
    ok = got == want; print(('ok   ' if ok else 'FAIL ') + name + ('' if ok else f': {got!r} != {want!r}')); ok or bad.append(name)
with tempfile.TemporaryDirectory() as td:
    W, H = 900, 500; Image.new('RGB', (W, H), 'white').save(os.path.join(td, 'plan.png'))
    places = []
    for i in range(8):                                                    # блок 4 × 2 стола 1,4 × 0,7 м при 50 px/м: 70 × 35 px, номера «201-1» … «201-8»
        x0, y0 = 100 + (i % 4) * 72, 100 + (i // 4) * 37
        D = [[x0, y0], [x0 + 70, y0], [x0 + 70, y0 + 35], [x0, y0 + 35]]
        places.append(dict(seat=f'201-{i + 1}', number=f'201-{i + 1}', desk=D, centre=[x0 + 35, y0 + 17.5], x=x0 + 35, y=y0 - 15 if i < 4 else y0 + 50, by='стул'))
    out = os.path.join(td, 'a3.png'); recs, info = render_draft(os.path.join(td, 'plan.png'), None, places, out, 50)
    check('номер нарисован у каждого стола', all(r.get('number_px', 0) > 0 for r in recs), True)
    im = np.asarray(Image.open(out).convert('RGB')).astype(int)
    white_in_desks = sum(int(((im[int(r['centre'][1]) - 3:int(r['centre'][1]) + 4, int(r['centre'][0]) - 12:int(r['centre'][0]) + 13] > 240).all(2)).sum()) for r in recs)
    check('белый номер поверх заливки', white_in_desks > 0, True)
    d, s = count_marks(out); check('count_marks: пятен столов = мест', d, len(places)); check('count_marks: пятен мест = мест', s, len(places))
    pj = os.path.join(td, 'places.json'); json.dump(dict(places=[dict(number=r['seat'], desk=r['desk'], centre=r['centre'], x=r['x'], y=r['y']) for r in recs]), open(pj, 'w'))
    svg = os.path.join(td, 'plan.svg'); open(svg, 'w').write(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}"><g id="underlay" display="none"/><g id="rooms"/><g id="glass"/><g id="furniture"/><g id="icons"/><g id="labels"/></svg>')
    a = type('A', (), dict(artefact3_png=out, final_png=None, places_json=pj, wall_t=6, outer_wall_px=None, meta=None, scale_px_per_m=50, source_transform=None))()
    root, R = ac.load(svg); P = ac.model(root, R, a); r29 = ac.c29(P, a, None)
    check('Ч-29 приёмки: pass', r29['status'], 'pass')
print('итог:', 'всё совпало' if not bad else f'расхождений {len(bad)}'); sys.exit(1 if bad else 0)
