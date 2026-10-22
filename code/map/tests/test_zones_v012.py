"""Тест полигонов зон v012 (КМ-23; ОЧ-Б26; Z1–Z3): unspot_map.zones на синтетическом файле зон, без внешних данных.
* помещение A-921 с XDATA (kind «open space» с пробелом -> open_space), пустота-колонна CIRCLE (ring=hole, номер хозяина), помещение с дугой bulge,
  проход A-922 внутри open space — не накладка; площадь против area_m2 ± 1 %; кадр M_t (мм -> px) как у моста;
* контур без XDATA — по слою, громко; пустота без XDATA — по вложенности;
* заливка — первой группой в <g id="rooms"> (под стенами), с data-zone и data-kind; без --fill SVG не пишется (по умолчанию выключено, Р-3);
* ПК6-К3: файл без проходов A-922 и сущности слоёв зон не LWPOLYLINE/CIRCLE — «ВНИМАНИЕ» в выводе и в check.предупреждения.
Запуск из любой папки: python3 tests/test_zones_v012.py — код 0, если всё совпало."""
import json, math, os, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np, ezdxf
from unspot_map import zones as Z
bad = []
def check(name, got, want):
    ok = got == want; print(('ok   ' if ok else 'FAIL ') + name + ('' if ok else f': {got!r} != {want!r}')); ok or bad.append(name)

CODE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
with tempfile.TemporaryDirectory() as td:
    doc = ezdxf.new(); doc.appids.add('UNSPOT'); msp = doc.modelspace()
    for n in ('A-921----E-', 'A-921----H-', 'A-922----E-', 'X-921'): doc.layers.add(n)
    def poly(pts, layer, xd=None, bulges=None):
        e = msp.add_lwpolyline([(x, y, 0, 0, b) for (x, y), b in zip(pts, bulges or [0] * len(pts))], format='xyseb', close=True, dxfattribs={'layer': layer})
        if xd: e.set_xdata('UNSPOT', [(1000, '%s=%s' % kv) for kv in xd.items()])
        return e
    base = dict(group='7', type='room')
    # open space 20 × 10 м с колонной ⌀ 0,6 м: площадь 200 − 0,283 м²
    poly([(0, 0), (20000, 0), (20000, 10000), (0, 10000)], 'A-921----E-', dict(base, kind='open space', number='1.01', name='', area_m2='199.72', ring='outer'))
    c = msp.add_circle((5000, 5000), 300, dxfattribs={'layer': 'A-921----E-'}); c.set_xdata('UNSPOT', [(1000, x) for x in ('group=7', 'type=room', 'kind=open space', 'number=1.01', 'ring=hole')])
    # переговорная 4 × 4 м с полукруглым торцом (дуга bulge 1 на стороне 4 м): 16 + π·2²/2 = 22,283 м²
    poly([(25000, 0), (29000, 0), (29000, 4000), (25000, 4000)], 'A-921----E-', dict(base, kind='meeting', number='1.02', name='образцовая комната', area_m2='22.28', ring='outer'),
         bulges=[0, 1, 0, 0])
    # проход внутри open space
    poly([(1000, 1000), (19000, 1000), (19000, 2500), (1000, 2500)], 'A-922----E-', dict(group='7', type='passage', kind='open space', area_m2='27', ring='outer'))
    # без XDATA: помещение и пустота в нём (по вложенности)
    poly([(0, 20000), (6000, 20000), (6000, 26000), (0, 26000)], 'A-921----E-')
    poly([(2000, 22000), (3000, 22000), (3000, 23000), (2000, 23000)], 'A-921----E-')
    pp = os.path.join(td, 'f_zones.dxf'); doc.saveas(pp)
    logs = []; zs = Z.read_zones(pp, log=logs.append); errs, summ = Z.selfcheck(zs)
    check('зоны: помещений 3 (2 с XDATA + 1 по слою), проходов 1, пустот 2', (summ['помещений'], summ['проходов'], summ['пустот']), (3, 1, 2))
    check('зоны: kind «open space» -> open_space, исходное слово сохранено', ({z['kind'] for z in zs if z['number'] == '1.01'}, zs[0].get('kind_src')), ({'open_space'}, 'open space'))
    check('зоны: самопроверка — ошибок 0 (проход в open space — не накладка; площади ± 1 %)', errs, [])
    m = next(z for z in zs if z['number'] == '1.02')
    check('зоны: дуга bulge — площадь 22,28 м² ± 1 %, дуг 1', (abs(m['poly'].area / 1e6 - 22.283) < 0.01 * 22.283, m['arcs']), (True, 1))
    check('зоны: без XDATA — громко в журнале', any('без XDATA' in x for x in logs), True)
    M = np.array([[0.05, 0], [0, -0.05]]); t = np.array([100.0, 2000.0]); zp = Z.to_px(zs, M, t)
    o = next(z for z in zp if z['number'] == '1.01')
    check('зоны: кадр M_t — мм -> px, пустота — в holes', (o['outer'][0], len(o['holes'])), ([100.0, 2000.0], 1))
    np.save(os.path.join(td, 'M_t.npy'), np.array([0.05, 0, 0, -0.05, 100.0, 2000.0]))
    svg = os.path.join(td, 'plan.svg')
    open(svg, 'w').write('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 2000"><g id="underlay" display="none"/><g id="rooms">'
                         '<path id="room-f-1" d="M100 2000 L1100 2000 L1100 1500 L100 1500 Z" fill="#EBF5FF" stroke="#CBD2D6" stroke-width="6"/></g></svg>')
    r = subprocess.run([sys.executable, '-m', 'unspot_map.zones', pp, '--frame', os.path.join(td, 'M_t.npy'), '--out', os.path.join(td, 'z.json'), '--svg', svg,
                        '--svg-out', os.path.join(td, 'z_off.svg')], cwd=CODE, capture_output=True, text=True)
    check('зоны: без --fill заливка не пишется (по умолчанию выключено, Р-3)', (os.path.exists(os.path.join(td, 'z_off.svg')), 'выключена' in r.stdout), (False, True))
    r = subprocess.run([sys.executable, '-m', 'unspot_map.zones', pp, '--frame', os.path.join(td, 'M_t.npy'), '--out', os.path.join(td, 'z.json'), '--svg', svg,
                        '--svg-out', os.path.join(td, 'z_on.svg'), '--fill'], cwd=CODE, capture_output=True, text=True)
    s = open(os.path.join(td, 'z_on.svg')).read()
    check('зоны: --fill — группа заливок первой в rooms, под помещением с обводкой; data-zone, data-kind', (s.index('rooms-zones') < s.index('room-f-1'), 'data-zone="room"' in s, 'data-kind="open_space"' in s, 'fill="#EBF5FF"' in s),
          (True, True, True, True))
    check('зоны: тип без цвета — fill="none" и громко', ('fill="none"' in s, 'нет цвета' in r.stdout), (True, True))
    check('зоны: zones.json — схема контракта', sorted(k for k in json.load(open(os.path.join(td, 'z.json')))['zones'][0] if k in ('type', 'kind', 'number', 'name', 'area_m2', 'outer', 'holes')),
          sorted(['type', 'kind', 'number', 'name', 'area_m2', 'outer', 'holes']))
    check('зоны: норма kind', (Z.norm_kind('Open Space'), Z.norm_kind('open-space'), Z.norm_kind(None)), ('open_space', 'open_space', None))
    check('зоны: проходы есть — предупреждения нет (ПК6-К3)', ('проходов A-922 в файле нет' in r.stdout, json.load(open(os.path.join(td, 'z.json')))['check']['предупреждения']), (False, []))
    # ПК6-К3: файл зон без A-922 и с сущностью слоя зон не LWPOLYLINE/CIRCLE — громко, а не «проходов 0» молча
    doc2 = ezdxf.new(); doc2.appids.add('UNSPOT'); m2 = doc2.modelspace()
    for n in ('A-921----E-', 'A-922----E-'): doc2.layers.add(n)
    e = m2.add_lwpolyline([(0, 0), (4000, 0), (4000, 4000), (0, 4000)], close=True, dxfattribs={'layer': 'A-921----E-'})
    e.set_xdata('UNSPOT', [(1000, x) for x in ('group=7', 'type=room', 'kind=meeting', 'number=2.01', 'area_m2=16', 'ring=outer')])
    m2.add_line((0, 0), (4000, 4000), dxfattribs={'layer': 'A-922----E-'})
    m2.add_line((0, 4000), (4000, 0), dxfattribs={'layer': 'A-921----E-'})
    p2 = os.path.join(td, 'noA922_zones.dxf'); doc2.saveas(p2)
    r = subprocess.run([sys.executable, '-m', 'unspot_map.zones', p2, '--frame', os.path.join(td, 'M_t.npy'), '--out', os.path.join(td, 'z2.json')], cwd=CODE, capture_output=True, text=True)
    w2 = json.load(open(os.path.join(td, 'z2.json')))['check']['предупреждения']
    check('зоны: без A-922 — «ВНИМАНИЕ — проходов A-922 в файле нет» (ПК6-К3)', ('ВНИМАНИЕ — проходов A-922 в файле нет' in r.stdout, r.returncode), (True, 0))
    check('зоны: пропущенные сущности слоёв зон — счёт по типу (ПК6-К3)', ('пропущено 2 объектов не LWPOLYLINE/CIRCLE (LINE 2)' in r.stdout, any('LINE 2' in x for x in w2), len(w2)), (True, True, 2))
print('итог:', 'всё совпало' if not bad else f'расхождений {len(bad)}'); sys.exit(1 if bad else 0)
