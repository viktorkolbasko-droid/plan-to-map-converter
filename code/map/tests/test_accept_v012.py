"""Тесты приёмки v012 (исполнитель 1) без внешних данных: маленькие SVG и PNG во временной папке, acceptance_checks.py — отдельным процессом.
    python3 tests/test_accept_v012.py        -> «ok N из N» и код 0
Что проверяется (КМ-2, КМ-4, КМ-13):
  Ч-28 — правка: --prev-size W,H другого размера — fail; того же — pass; export.json mode edit без ключа — skip с причиной;
  Ч-09 — вершина на ребре обведённого помещения, которая есть в контуре открытой зоны (Т-узел соседа без обводки), — не лишняя;
  Ч-19 — стекло поверх проёма — fail «закрыт сверху»; проём в стеклянной перегородке без стены — на стекле (тело — и стекло);
  Ч-32 — косое ребро под заливкой колонны — не судится; видимая часть ≥ T или под колонной < 85 % — судится (ПК6-К2);
  Ч-10 — карта по мосту: маска по умолчанию dxf3, рецепт wm1 — look (решение владельца 14.10.2026, ОЧ-25);
  КМ-8 — двери листа: дуга ломаной и куски одной дуги — одна дверь; КМ-13 — формат номера листа из настройки, ни одного номера — громко."""
import os, sys, json, math, subprocess, tempfile, traceback
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); CODE = os.path.dirname(HERE); AC = os.path.join(CODE, 'acceptance_checks.py')
from PIL import Image

HEAD = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 300">\n<rect x="0" y="0" width="400" height="300" fill="#FFFFFF" stroke="none"/>\n<g id="underlay" display="none"/>\n<g id="rooms">\n'
TAIL = '</g>\n<g id="furniture"/>\n<g id="icons"/>\n<g id="labels"/>\n</svg>\n'
R1 = '<path id="room-a" data-name="1" data-type="office" d="M20 20 L200 20 L200 150 L20 150 Z" fill="#F1EBFF" stroke="#CBD2D6" stroke-width="6"/>\n'
R2 = '<path id="room-b" data-name="2" data-type="office" d="M200 20 L380 20 L380 150 L200 150 Z" fill="#F1EBFF" stroke="#CBD2D6" stroke-width="6"/>\n'
DOOR = '<path id="door-1" data-type="door" d="M260 144 L320 144 L320 156 L260 156 Z" fill="#F1EBFF" stroke="none"/>\n'   # глубина 12 = стене, которую мерит Ч-19

def run(svg, extra=(), png=(400, 300), a3=(400, 300), export=None):
    d = tempfile.mkdtemp(prefix='t_acc_'); open(os.path.join(d, 'plan.svg'), 'w', encoding='utf-8').write(svg)
    Image.new('RGB', png, 'white').save(os.path.join(d, 'plan.png')); Image.new('RGB', a3, 'white').save(os.path.join(d, 'a3.png'))
    if export is not None: json.dump(export, open(os.path.join(d, 'plan.png.export.json'), 'w', encoding='utf-8'))
    r = subprocess.run([sys.executable, AC, '--svg', 'plan.svg', '--scale-px-per-m', '50', '--final-png', 'plan.png', '--artefact3-png', 'a3.png',
                        '--json', 'out.json'] + list(extra), cwd=d, capture_output=True, text=True)
    if not os.path.exists(os.path.join(d, 'out.json')): raise AssertionError('приёмка упала: ' + r.stderr[-800:])
    return {c['id']: c for c in json.load(open(os.path.join(d, 'out.json'), encoding='utf-8'))['checks']}

T = []
def test(f): T.append(f); return f

@test
def t_c28_prev_size():
    svg = HEAD + R1 + R2 + DOOR + TAIL
    assert run(svg)['Ч-28']['status'] == 'pass'
    c = run(svg, ['--prev-size', '1200,900'])['Ч-28']; assert c['status'] == 'fail' and 'прежней выгрузки' in json.dumps(c, ensure_ascii=False), c
    assert run(svg, ['--prev-size', '400,300'])['Ч-28']['status'] == 'pass'
    c = run(svg, export=dict(png='plan.png', w=400, h=300, scale=1.0, canvas=[400, 300], mode='edit', prev_size=None))['Ч-28']
    assert c['status'] == 'skip' and 'прежней выгрузки не дан' in str(c.get('reason') or c.get('value')), c

@test
def t_c09_open_zone_tnode():
    room = '<path id="room-a" data-name="1" data-type="office" d="M20 20 L110 20 L200 20 L200 150 L20 150 Z" fill="#F1EBFF" stroke="#CBD2D6" stroke-width="6"/>\n'
    zone = '<path id="room-z" data-name="" data-type="openspace" d="M20 20 L110 20 L110 -60 L20 -60 Z" fill="#EBF5FF" stroke="none"/>\n'
    c = run(HEAD + zone + room + R2 + DOOR + TAIL)['Ч-09']
    assert c['status'] != 'fail', c                                         # (110,20) — угол открытой зоны: Т-узел соседа, не лишняя вершина
    c2 = run(HEAD + room + R2 + DOOR + TAIL)['Ч-09']; assert c2['status'] == 'fail', c2   # без зоны — лишняя вершина

@test
def t_c19_glass_over_door():
    glass = '</g>\n<g id="glass">\n<path id="glasswall-x" d="M250 150 L330 150" fill="none" stroke="#86C5FB" stroke-width="4"/>\n'
    c = run(HEAD + R1 + R2 + DOOR + glass + TAIL)['Ч-19']; assert c['status'] == 'fail' and 'закрыт сверху' in json.dumps(c, ensure_ascii=False), c
    c = run(HEAD + R1 + R2 + DOOR + TAIL)['Ч-19']; assert c['status'] == 'pass', c

@test
def t_c19_door_in_glass():
    z1 = '<path id="room-z1" data-name="" data-type="openspace" d="M20 20 L200 20 L200 150 L20 150 Z" fill="#EBF5FF" stroke="none"/>\n'
    z2 = '<path id="room-z2" data-name="" data-type="openspace" d="M200 20 L380 20 L380 150 L200 150 Z" fill="#EBF5FF" stroke="none"/>\n'
    door = '<path id="door-g" data-type="door" d="M198 60 L202 60 L202 110 L198 110 Z" fill="#EBF5FF" stroke="none"/>\n'
    glass = '</g>\n<g id="glass">\n<path id="glasswall-a" d="M200 20 L200 60" fill="none" stroke="#86C5FB" stroke-width="4"/>\n<path id="glasswall-b" d="M200 110 L200 150" fill="none" stroke="#86C5FB" stroke-width="4"/>\n'
    room = '<path id="room-a" data-name="1" data-type="office" d="M20 150 L380 150 L380 280 L20 280 Z" fill="#F1EBFF" stroke="#CBD2D6" stroke-width="6"/>\n'
    c = run(HEAD + z1 + z2 + room + door + glass + TAIL)['Ч-19']
    assert 'на стене 0' not in json.dumps(c, ensure_ascii=False), c          # П3-9: проём в стекле — на стекле, глубина — толщина линии стекла
    assert 'в стеклянной перегородке (между концами стекла) 1' in c['value'] and 'door-g' not in json.dumps(c['where'], ensure_ascii=False), c

@test
def t_c19_glass_room_stroke_under_door():
    r2g = R2.replace('stroke="#CBD2D6"', 'stroke="#86C5FB"')                 # переговорная со стеклянной обводкой: обводка ниже проёма — проём виден
    c = run(HEAD + R1 + r2g + DOOR + TAIL)['Ч-19']
    assert 'закрыт сверху стеклом или стеной 0' in c['value'], c

@test
def t_c32_under_column():
    room = '<path id="room-a" data-name="1" data-type="office" d="M20 20 L180 20 L200 40 L200 150 L20 150 Z" fill="#F1EBFF" stroke="#CBD2D6" stroke-width="6"/>\n'
    col = '<path id="column-1" data-type="column" d="M170 10 L210 10 L210 50 L170 50 Z" fill="#CBD2D6" stroke="none"/>\n'
    c = run(HEAD + room + R2 + DOOR + col + TAIL)['Ч-32']; assert c['status'] == 'pass' and 'под колонной' in c['value'], c
    c = run(HEAD + room + R2 + DOOR + TAIL)['Ч-32']; assert c['status'] in ('fail', 'look'), c

@test
def t_c32_column_share():
    """ПК6-К2: фаска 0,57 м (28 px), колонна закрывает её долю f от верхнего конца; видимая часть = (1 − f) · 28 px против T = 6 px.
    100 % и 85 % (видно 4 px < T) — не судится; 60 % (видно 11 px ≥ T) и 0 % — судится (копии r2_32col проверяющего)"""
    room = '<path id="room-a" data-name="1" data-type="office" d="M20 20 L180 20 L200 40 L200 150 L20 150 Z" fill="#F1EBFF" stroke="#CBD2D6" stroke-width="6"/>\n'
    col = lambda f: '<path id="column-1" data-type="column" d="M%.2f 5 L215 5 L215 55 L%.2f 55 Z" fill="#CBD2D6" stroke="none"/>\n' % (180 + 20 * (1 - f), 180 + 20 * (1 - f))
    for f, judged in ((1.0, False), (0.85, False), (0.6, True), (0.0, True)):
        c = run(HEAD + room + R2 + DOOR + (col(f) if f > 0 else '') + TAIL)['Ч-32']
        if judged: assert c['status'] in ('fail', 'look') and 'под колонной' not in c['value'], (f, c)
        else: assert c['status'] == 'pass' and 'под колонной 1' in c['value'], (f, c)

@test
def t_c10_bridge_mask_default():
    """решение владельца 14.10.2026 (ОЧ-25): карта по мосту (data-generator="bridge_convert …") — маска Ч-10 по умолчанию dxf3; рецепт wm1 — look с причиной;
    карта не по мосту с wm1 и карта по мосту с dxf3 — без этой записи"""
    import hashlib
    def go(bridge, recipe):
        d = tempfile.mkdtemp(prefix='t_c10_'); W_, H_ = 400, 300
        img = Image.new('L', (W_, H_), 255); mk = Image.new('L', (W_, H_), 0)
        from PIL import ImageDraw
        for im, col in ((img, 0), (mk, 255)):
            dr = ImageDraw.Draw(im)
            for x0, y0, x1, y1 in ((20, 20, 380, 20), (20, 150, 380, 150), (20, 20, 20, 150), (200, 20, 200, 150), (380, 20, 380, 150)):
                dr.line((x0, y0, x1, y1), fill=col, width=7)
        img.convert('RGB').save(os.path.join(d, 'work.png')); mk.save(os.path.join(d, 'mask.png'))
        a_ = np.asarray(mk, np.uint8); h = hashlib.sha256(f'{a_.shape[1]}x{a_.shape[0]}:'.encode() + a_.tobytes()).hexdigest()
        json.dump(dict(recipe=recipe, mask_sha256=h), open(os.path.join(d, 'mask.json'), 'w'))
        svg = HEAD + R1 + R2 + DOOR + TAIL
        if bridge: svg = svg.replace('<svg xmlns="http://www.w3.org/2000/svg"', '<svg xmlns="http://www.w3.org/2000/svg" data-generator="bridge_convert 0.33"')
        open(os.path.join(d, 'plan.svg'), 'w', encoding='utf-8').write(svg)
        Image.new('RGB', (400, 300), 'white').save(os.path.join(d, 'plan.png')); Image.new('RGB', (400, 300), 'white').save(os.path.join(d, 'a3.png'))
        subprocess.run([sys.executable, AC, '--svg', 'plan.svg', '--scale-px-per-m', '50', '--final-png', 'plan.png', '--artefact3-png', 'a3.png', '--source-png', 'work.png',
                        '--source-transform', '1,0,0,0,1,0', '--source-kind', 'vector', '--wall-mask', 'mask.png', '--json', 'out.json'], cwd=d, capture_output=True, text=True)
        return {c['id']: c for c in json.load(open(os.path.join(d, 'out.json'), encoding='utf-8'))['checks']}['Ч-10']
    c = go(True, 'wm1'); s_ = json.dumps(c, ensure_ascii=False)
    assert 'по умолчанию — dxf3' in s_ and c['status'] in ('look', 'fail'), c
    for br, rc in ((False, 'wm1'), (True, 'dxf3')):
        c = go(br, rc); assert 'по умолчанию — dxf3' not in json.dumps(c, ensure_ascii=False), (br, rc, c)

def sheet_pdf(d, draw):
    """лист 400 × 300 pt, 50 pt = 1 м; work.png — рендер ×2 (100 px/м), intake.json — to_pixels ×2"""
    import pymupdf
    doc = pymupdf.open(); pg = doc.new_page(width=400, height=300); draw(pg); pdf = os.path.join(d, 'sheet.pdf'); doc.save(pdf)
    pg = pymupdf.open(pdf)[0]; pg.get_pixmap(matrix=pymupdf.Matrix(2, 2)).save(os.path.join(d, 'work.png'))
    json.dump(dict(render=dict(to_pixels=[2, 0, 0, 2, 0, 0]), chosen_page=1), open(os.path.join(d, 'intake.json'), 'w'))
    return pdf

@test
def t_sheet_doors_polyline_and_pieces():
    import pymupdf
    sys.path.insert(0, CODE); from unspot_map import sheet as S
    def draw(pg):
        h = pymupdf.Point(100, 100); r = 45.0                                   # створка 0,9 м: дуга ломаной из 9 отрезков + полотно
        P = [pymupdf.Point(h.x + r * math.cos(math.radians(a)), h.y - r * math.sin(math.radians(a))) for a in range(0, 91, 10)]
        sh = pg.new_shape(); sh.draw_polyline(P); sh.draw_line(h, P[-1]); sh.finish(color=(0, 0, 0), width=0.5); sh.commit()
        h2 = pymupdf.Point(300, 100)                                           # дуга двумя кусками по 45° (разные пути) + полотно
        for a0, a1 in ((0, 45), (45, 90)):
            Q = [pymupdf.Point(h2.x + r * math.cos(math.radians(a)), h2.y - r * math.sin(math.radians(a))) for a in np.linspace(a0, a1, 7)]
            sh = pg.new_shape(); sh.draw_polyline(Q); sh.finish(color=(0, 0, 0), width=0.5); sh.commit()
        sh = pg.new_shape(); sh.draw_line(h2, pymupdf.Point(h2.x, h2.y - r)); sh.finish(color=(0, 0, 0), width=0.5); sh.commit()
        sh = pg.new_shape(); sh.draw_polyline([pymupdf.Point(20, 250), pymupdf.Point(380, 250)]); sh.finish(color=(0, 0, 0), width=0.5); sh.commit()   # прямая — не дуга
        h3 = pymupdf.Point(200, 200)                                           # распечатанный лист: каждый отрезок дуги — свой путь (Ghostscript)
        Q = [pymupdf.Point(h3.x + r * math.cos(math.radians(a)), h3.y - r * math.sin(math.radians(a))) for a in range(0, 91, 6)]
        for p0, p1 in zip(Q[:-1], Q[1:]):
            sh = pg.new_shape(); sh.draw_line(p0, p1); sh.finish(color=(0, 0, 0), width=0.5); sh.commit()
        sh = pg.new_shape(); sh.draw_line(h3, Q[-1]); sh.finish(color=(0, 0, 0), width=0.5); sh.commit()
    d = tempfile.mkdtemp(prefix='t_sheet_'); pdf = sheet_pdf(d, draw)
    R = S.doors(pdf, os.path.join(d, 'intake.json'), 100.0)
    assert len(R['doors']) == 3, R
    for e in R['doors']: assert abs(e['r_m'] - 0.9) < 0.03 and 80 <= e['sweep'] <= 100, e
    R0 = S.doors(pdf, os.path.join(d, 'intake.json'), 100.0, min_sweep=60.0, piece_min=30.0)
    assert len(R0['doors']) == 3, 'куски одной дуги (по 45°) — одна дверь 90° и при пороге двери 60°'

@test
def t_sheet_numbers_format():
    import pymupdf
    sys.path.insert(0, CODE); from unspot_map import sheet as S
    def draw(pg): pg.insert_text((50, 50), 'A-12', fontsize=10); pg.insert_text((150, 50), 'A-7', fontsize=10)
    d = tempfile.mkdtemp(prefix='t_sheet_'); pdf = sheet_pdf(d, draw)
    R = S.numbers(pdf, os.path.join(d, 'intake.json'), 100.0)
    assert R['numbers'] == [] and 'НИ ОДНОГО' in R['how'], R
    R = S.numbers(pdf, os.path.join(d, 'intake.json'), 100.0, number_re=r'A-\d{1,3}')
    assert sorted(e['n'] for e in R['numbers']) == ['A-12', 'A-7'], R

if __name__ == '__main__':
    ok = 0
    for f in T:
        try: f(); ok += 1; print('ok  ', f.__name__)
        except Exception: print('FAIL', f.__name__); traceback.print_exc()
    print(f'ok {ok} из {len(T)}'); sys.exit(0 if ok == len(T) else 1)
