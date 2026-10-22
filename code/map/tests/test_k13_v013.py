"""Тесты К13.3 и К13.4 (код карты v013; map/rules/83 §1, §5; map/rules/80 §2 — Ч-10, Ч-11, Ч-21, Ч-22, Ч-29, «Проверки без номера Ч»;
строки реестра 354, 358, 387, 391, 413) без внешних данных: маленькие SVG и PNG во временной папке, acceptance_checks.py — отдельным процессом.
  запись места: gaze_deg — от стула к столу, 0 — вправо, 90 — вниз (N 90, E 180, S 270, W 0); room — помещение центра стола; во всех способах
    (records — заливка и номера, линии, растр; places_plan.build — план; render_draft после подрезки; CLI fields);
  Ч-21, Ч-29 — записи без desk и centre: fail «записей N, столов 0: ключи не по схеме»; desk: null — fail; Ч-21 читает transform SVG;
  Ч-29 — точка закрыта: доля #FFB000 в круге ⌀ 0,26 м < 0,9 — fail;
  Ч-10 — d₂ = max(2 px холста, 2q мм), растр с q ≥ 100 мм/px — пороги 85 / 90 %; Ч-10, Ч-11 — «цветные стены» без маски — look и число;
  Ч-22 — стол переговорной со стульями — не нарушение №50; «стол переговорной против стола листа» (± 10 %, стулья) и «помещается» (0,5 м) — look,
  шлюз их не решает.
    python3 tests/test_k13_v013.py        -> «ok N из N» и код 0"""
import io, json, math, os, subprocess, sys, tempfile, traceback, contextlib
HERE = os.path.dirname(os.path.abspath(__file__)); CODE = os.path.dirname(HERE); AC = os.path.join(CODE, 'acceptance_checks.py')
sys.path.insert(0, CODE)
import numpy as np, ezdxf
from PIL import Image, ImageDraw
from shapely.geometry import Polygon

HEAD = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 300">\n<rect x="0" y="0" width="400" height="300" fill="#FFFFFF" stroke="none"/>\n<g id="underlay" display="none"/>\n<g id="rooms">\n'
R1 = '<path id="room-a" data-name="A1" data-type="office" d="M20 20 L200 20 L200 150 L20 150 Z" fill="#F1EBFF" stroke="#CBD2D6" stroke-width="6"/>\n'
R2 = '<path id="room-b" data-name="B2" data-type="office" d="M200 20 L380 20 L380 150 L200 150 Z" fill="#F1EBFF" stroke="#CBD2D6" stroke-width="6"/>\n'
RM = '<path id="room-m" data-name="MR-1" data-type="meeting" d="M20 150 L380 150 L380 280 L20 280 Z" fill="#FFF5EB" stroke="#CBD2D6" stroke-width="6"/>\n'
MID = '</g>\n<g id="glass"/>\n<g id="furniture">\n'
TAIL = '</g>\n<g id="icons"/>\n<g id="labels"/>\n</svg>\n'
DESK = [[60, 60], [120, 60], [120, 90], [60, 90]]                          # стол 1,2 × 0,6 м при 50 px/м, центр (90, 75)

def a3_png(path, desk=DESK, seat=(90, 102), cover=False, size=(400, 300)):
    im = Image.new('RGB', size, 'white'); d = ImageDraw.Draw(im)
    d.polygon([tuple(p) for p in desk], fill='#E6007E'); r = 0.26 * 50 / 2
    d.ellipse([seat[0] - r, seat[1] - r, seat[0] + r, seat[1] + r], fill='#FFB000')
    if cover: d.rectangle([seat[0] - r - 1, seat[1] - r - 1, seat[0] + r + 1, seat[1]], fill='#888888')   # верх точки закрыт
    im.save(path)

def run(svg, extra=(), places=None, a3=None, src=None, files=None):
    d = tempfile.mkdtemp(prefix='t_k13_'); open(os.path.join(d, 'plan.svg'), 'w', encoding='utf-8').write(svg)
    Image.new('RGB', (400, 300), 'white').save(os.path.join(d, 'plan.png'))
    if a3 is None: Image.new('RGB', (400, 300), 'white').save(os.path.join(d, 'a3.png'))
    else: a3(os.path.join(d, 'a3.png'))
    args = ['--svg', 'plan.svg', '--scale-px-per-m', '50', '--final-png', 'plan.png', '--artefact3-png', 'a3.png', '--json', 'out.json']
    if places is not None: json.dump(places, open(os.path.join(d, 'places.json'), 'w', encoding='utf-8')); args += ['--places-json', 'places.json']
    if src is not None: src(os.path.join(d, 'src.png'))
    for k, v in (files or {}).items(): json.dump(v, open(os.path.join(d, k), 'w', encoding='utf-8'))
    r = subprocess.run([sys.executable, AC] + args + list(extra), cwd=d, capture_output=True, text=True)
    if not os.path.exists(os.path.join(d, 'out.json')): raise AssertionError('приёмка упала: ' + r.stderr[-800:])
    J = json.load(open(os.path.join(d, 'out.json'), encoding='utf-8')); J['_dir'] = d
    return {c['id']: c for c in J['checks']}, J
txt = lambda c: json.dumps(c, ensure_ascii=False)

T = []
def test(f): T.append(f); return f

# ---------------------------------------------------------------- К13.3: запись места
@test
def t_gaze_sides():
    from unspot_map.workplaces import gaze_deg
    got = (gaze_deg(10, 0, 10, 10), gaze_deg(20, 10, 10, 10), gaze_deg(10, 20, 10, 10), gaze_deg(0, 10, 10, 10), gaze_deg(10, 10, 10, 10), gaze_deg(None, 1, 2, 3))
    assert got == (90.0, 180.0, 270.0, 0.0, None, None), got               # N 90, E 180, S 270, W 0 (83 §5); стул в центре и нет точки — None
    assert gaze_deg(10.0, 10.0, 20.0, 10.0 + 1e-9) == 0.0                  # 359,99… не становится 360

@test
def t_records_room_gaze():
    from unspot_map.workplaces import records, rooms_svg, finish_records
    d = tempfile.mkdtemp(prefix='t_k13_'); svg = os.path.join(d, 'm.svg'); open(svg, 'w', encoding='utf-8').write(HEAD + R1 + R2 + MID + TAIL)
    F = lambda P: np.asarray(P, float) * 2.0                                # кадр work -> картинка ×2 (картинка вдвое больше холста)
    P = [dict(n='1', desk=Polygon([(30, 30), (60, 30), (60, 45), (30, 45)]), seat=(45, 55), how='стул (линии)'),      # стул снизу -> 270
         dict(n='2', desk=Polygon([(250, 30), (280, 30), (280, 45), (250, 45)]), seat=(240, 37.5), how='стул (линии)')]  # слева -> 0
    R = records(P, F, 100.0, 'lines')
    assert [r['gaze_deg'] for r in R] == [270.0, 0.0] and [r['room'] for r in R] == [None, None], R   # без помещений room — None (ключ есть)
    R = records(P, F, 100.0, 'lines', rooms=rooms_svg(svg, 2.0))
    assert [r['room'] for r in R] == ['A1', 'B2'], R                       # помещение центра стола, имя — data-name
    RR, ng, nr = finish_records([dict(R[0], room='свой')], rooms_svg(svg, 2.0), keep_room=True)
    assert RR[0]['room'] == 'свой' and ng == 0 and nr == 0

@test
def t_draft_regaze_and_fields_cli():
    from unspot_map.workplaces import render_draft
    d = tempfile.mkdtemp(prefix='t_k13_'); Image.new('RGB', (400, 300), 'white').save(os.path.join(d, 'c.png'))
    P = [dict(seat='1', number='1', desk=[[60, 60], [120, 60], [120, 90], [60, 90]], centre=[90, 75], x=90, y=40),
         dict(seat='2', number='2', desk=[[100, 60], [160, 60], [160, 90], [100, 90]], centre=[130, 75], x=130, y=110)]   # столы пересекаются
    with contextlib.redirect_stdout(io.StringIO()):
        recs, info = render_draft(os.path.join(d, 'c.png'), None, P, os.path.join(d, 'a3.png'), 50.0, log=print)
    assert info['clipped'] >= 1 and all(r['gaze_deg'] is not None for r in recs), (info, recs)
    for r in recs:                                                         # gaze_deg — по centre после подрезки
        assert abs(r['gaze_deg'] - math.degrees(math.atan2(r['centre'][1] - r['y'], r['centre'][0] - r['x'])) % 360) < 0.11, r
    svg = os.path.join(d, 'm.svg'); open(svg, 'w', encoding='utf-8').write(HEAD + R1 + R2 + RM + MID + TAIL)
    json.dump(dict(places=P), open(os.path.join(d, 'p.json'), 'w', encoding='utf-8'))
    r = subprocess.run([sys.executable, '-m', 'unspot_map.workplaces', 'fields', '--places', 'p.json', '--svg', 'm.svg', '--image-size', '400,300', '--out', 'o.json'],
                       cwd=d, capture_output=True, text=True, env=dict(os.environ, PYTHONPATH=CODE))
    J = json.load(open(os.path.join(d, 'o.json'), encoding='utf-8'))['places']
    assert r.returncode == 0 and [(q['room'], q['gaze_deg']) for q in J] == [('A1', 90.0), ('A1', 270.0)], (r.stdout, r.stderr, J)

@test
def t_places_plan_gaze():
    from unspot_map import places_plan as PP
    d = tempfile.mkdtemp(prefix='t_k13_'); p = os.path.join(d, 'plan.dxf')
    doc = ezdxf.new(); doc.appids.add('UNSPOT'); msp = doc.modelspace(); doc.layers.add('A-82----E-'); doc.layers.add('A-90----T-')
    for nm, w, h in (('B_desk', 1400, 700), ('B_chair', 500, 500)):
        b = doc.blocks.new(nm); b.add_lwpolyline([(0, 0), (w, 0), (w, h), (0, h)], close=True)
    def ins(nm, x, y, typ):
        e = msp.add_blockref(nm, (x, y), dxfattribs={'layer': 'A-82----E-'}); e.set_xdata('UNSPOT', [(1000, 'group=4'), (1000, 'type=%s' % typ)])
    ins('B_desk', 2000, 2000, 'desk'); ins('B_chair', 2450, 1300, 'chair')      # стул ниже стола в мм -> на карте ниже (y px растёт) -> S, 270
    ins('B_desk', 2000, 5000, 'desk'); ins('B_chair', 2450, 5800, 'chair')      # стул выше -> N, 90
    for s_, x, y in (('1', 2500, 2250), ('2', 2500, 5250)):
        e = msp.add_text(s_, dxfattribs={'layer': 'A-90----T-', 'height': 200, 'insert': (x, y)}); e.dxf.true_color = 0xFF007F
    doc.saveas(p)
    svg = os.path.join(d, 'map.svg')                                           # кадр мм -> px: x·0,05 + 100, 1100 − y·0,05
    open(svg, 'w').write('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 1200"><g id="rooms">'
                         '<path id="room-f-1" data-name="Опен" data-type="open" d="M150 700 L300 700 L300 1100 L150 1100 Z" fill="#EBF5FF" stroke="none"/></g></svg>')
    pl, *_ = PP.build(p, np.array([[0.05, 0.0], [0.0, -0.05]]), np.array([100.0, 1100.0]), 50.0, svg, 'shift', log=lambda s: None)
    got = sorted((r['number'], r['gaze_deg'], r['room']) for r in pl)
    assert got == [('1', 270.0, 'Опен'), ('2', 90.0, 'Опен')], got

# ---------------------------------------------------------------- Ч-21, Ч-29: ключи, desk: null, точка закрыта, transform
@test
def t_keys_not_schema():
    P = [dict(seat='1', desk_polygon=DESK, desk_centre=[90, 75], chair_point=[90, 102])]
    C, _ = run(HEAD + R1 + R2 + MID + TAIL, places=P, a3=a3_png)
    for i in ('Ч-21', 'Ч-29'):
        assert C[i]['status'] == 'fail' and 'записей 1, столов 0: ключи записи не по схеме map/rules/83 §5' in txt(C[i]), C[i]

@test
def t_desk_null():
    P = [dict(seat='1', desk=DESK, centre=[90, 75], x=90, y=102), dict(seat='2', desk=None, x=300, y=100)]
    C, _ = run(HEAD + R1 + R2 + MID + TAIL, places=P, a3=a3_png)
    assert C['Ч-21']['status'] == 'fail' and 'место 2: desk: null' in txt(C['Ч-21']), C['Ч-21']
    assert C['Ч-29']['status'] == 'fail' and 'место 2: desk: null' in txt(C['Ч-29']), C['Ч-29']

@test
def t_c29_dot_closed():
    P = [dict(seat='1', desk=DESK, centre=[90, 75], x=90, y=102)]
    C, _ = run(HEAD + R1 + R2 + MID + TAIL, places=P, a3=a3_png)
    assert C['Ч-29']['status'] == 'pass' and 'точек закрыто 0' in C['Ч-29']['value'] and '13,0 px' in C['Ч-29']['value'], C['Ч-29']   # ⌀ 0,26 м × 50 px/м
    C, _ = run(HEAD + R1 + R2 + MID + TAIL, places=P, a3=lambda p: a3_png(p, cover=True))
    assert C['Ч-29']['status'] == 'fail' and 'точка закрыта' in txt(C['Ч-29']), C['Ч-29']

@test
def t_c21_transform():
    tab = '<g id="cab-1" transform="{}"><path d="M60 60 L100 60 L100 80 L60 80 Z" fill="none" stroke="#CBD2D6" stroke-width="1"/></g>\n'
    C, _ = run(HEAD + R1 + R2 + MID + tab.format('translate(0 0)') + TAIL)
    assert C['Ч-21']['status'] == 'pass', C['Ч-21']
    C, _ = run(HEAD + R1 + R2 + MID + tab.format('translate(120 0)') + TAIL)   # шкаф 180…220 — на стене x = 200: виден только с transform
    assert C['Ч-21']['status'] == 'fail' and 'cab-1: в стене' in txt(C['Ч-21']), C['Ч-21']
    assert C['Ч-26']['status'] == 'fail', C['Ч-26']                         # transform в сданном SVG по-прежнему запрещён (map/rules/82 §2-бис)

@test
def t_tf_matrix():
    sys.path.insert(0, CODE); import acceptance_checks as A
    M = A.tf_matrix('translate(5 0) rotate(90 10 10) scale(2)')
    p = M @ np.array([10.0, 5.0, 1.0])                                     # scale -> (20, 10); rotate 90 вокруг (10, 10) -> (10, 20); translate -> (15, 20)
    assert np.allclose(p[:2], [15, 20]), p
    assert np.allclose(A.tf_matrix('matrix(1 0 0 1 3 4)') @ [1, 1, 1], [4, 5, 1])

# ---------------------------------------------------------------- Ч-10, Ч-11: q ≥ 100 мм/px и цветные стены
ONE = '<path id="room-a" data-name="1" data-type="office" d="M20 20 L380 20 L380 280 L20 280 Z" fill="#F1EBFF" stroke="#CBD2D6" stroke-width="6"/>\n'
def wall_src(k, colour=None):
    """исходник в k раз грубее холста (X = k·x): тушь по контуру помещения, кусок верхней стены x 100…200 (8 % длины) сдвинут на 80 px холста"""
    def make(path):
        W, H = 400 * 4, 300 * 4; im = Image.new('RGB', (W, H), 'white'); d = ImageDraw.Draw(im); c = colour or (0, 0, 0); w = 12 * 4
        for (x0, y0, x1, y1) in ((20, 20, 100, 20), (200, 20, 380, 20), (380, 20, 380, 280), (380, 280, 20, 280), (20, 280, 20, 20), (100, 100, 200, 100)):
            d.line([(x0 * 4, y0 * 4), (x1 * 4, y1 * 4)], fill=c, width=w)
        im.resize((round(400 / k), round(300 / k)), Image.LANCZOS).save(path)
    return make

@test
def t_c10_coarse_raster():
    C, _ = run(HEAD + ONE + MID + TAIL, ['--source-png', 'src.png', '--source-transform', '1,0,0,0,1,0'], src=wall_src(1))
    c = C['Ч-10']; assert c['status'] == 'fail' and 'q = 20,0 мм/px' in c['value'] and 'd₂ ≥ 95 %' in c['threshold'], c        # 50 px/м: 1 px = 20 мм
    C, _ = run(HEAD + ONE + MID + TAIL, ['--source-png', 'src.png', '--source-transform', '6,0,0,0,6,0'], src=wall_src(6))
    c = C['Ч-10']; assert c['status'] in ('pass', 'look') and 'q = 120,0 мм/px' in c['value'] and 'd₂ ≥ 85 %' in c['threshold'], c   # 6 px холста = 120 мм
    v = float(c['value'].split(' %')[0].replace(',', '.')); assert 85 <= v < 95, v                                          # та же доля: fail на точном, не fail на грубом

@test
def t_c10_c11_colored_walls():
    ext = ['--source-png', 'src.png', '--source-transform', '1,0,0,0,1,0']
    C, _ = run(HEAD + ONE + MID + TAIL, ext, src=wall_src(1, colour=(200, 30, 30)))
    assert C['Ч-10']['status'] == 'fail', C['Ч-10']                                          # без признака: нейтральной туши нет — fail
    C, _ = run(HEAD + ONE + MID + TAIL, ext + ['--colored-walls'], src=wall_src(1, colour=(200, 30, 30)))
    for i in ('Ч-10', 'Ч-11'):
        c = C[i]; assert c['status'] == 'look' and 'цветной туши' in c['value'] and 'не покрыто маской нейтральной туши' in c['value'], c
    n = int(C['Ч-10']['value'].split('не покрыто маской нейтральной туши ')[1].split(' px')[0]); assert n > 1000, n

# ---------------------------------------------------------------- Ч-22 и проверки без номера Ч: стол переговорной
def table(dy=0):
    """стол 2,0 × 0,4 м (y 205…225) и 4 стула символом 2904:15155 сверху и снизу; dy — сдвиг по y"""
    return ('<g id="mtable-1" data-type="meeting-table">' + f'<path d="M150 {205 + dy} L250 {205 + dy} L250 {225 + dy} L150 {225 + dy} Z" fill="none" stroke="#CBD2D6" stroke-width="1"/>\n' +
            ''.join(f'<g data-figma="2904:15155"><path d="M{x - 9} {y + dy - 10} L{x + 9} {y + dy - 10} L{x + 9} {y + dy + 10} L{x - 9} {y + dy + 10} Z" fill="none" stroke="#CBD2D6" stroke-width="1"/></g>\n'
                    for x in (175, 225) for y in (192, 238)) + '</g>\n')
TABLE = table()                                                            # стулья 182…248; помещение внутри стен 153…277 — зазор 29 px = 0,58 м
SHEET = dict(frame='plan', tables=[dict(poly=[[150, 205], [250, 205], [250, 225], [150, 225]])])
CHAIRS4 = dict(frame='plan', chairs=[[175, 192], [225, 192], [175, 238], [225, 238]])

@test
def t_c22_meeting_table():
    C, _ = run(HEAD + R1 + R2 + RM + MID + TABLE + TAIL)
    assert C['Ч-22']['status'] == 'pass' and 'канон (строка 354)' in C['Ч-22']['value'], C['Ч-22']
    sofa = '<g data-figma="2904:14117"><path d="M60 200 L120 200 L120 220 L60 220 Z" fill="none" stroke="#CBD2D6" stroke-width="1"/></g>\n'
    C, _ = run(HEAD + R1 + R2 + RM + MID + TABLE + sofa + TAIL)
    assert C['Ч-22']['status'] == 'fail' and '(№50)' in txt(C['Ч-22']), C['Ч-22']                          # прочая мебель переговорной — по-прежнему нет

@test
def t_mr_sheet_check():
    C, J = run(HEAD + R1 + R2 + RM + MID + TABLE + TAIL)
    assert C['БЧ-стол-лист']['status'] == 'skip' and C['БЧ-стол-лист'].get('no_gate'), C['БЧ-стол-лист']    # нет входов листа
    C, _ = run(HEAD + R1 + R2 + RM + MID + TABLE + TAIL, ['--sheet-tables', 'st.json', '--chairs-json', 'ch.json'], files={'st.json': SHEET, 'ch.json': CHAIRS4})
    assert C['БЧ-стол-лист']['status'] == 'pass', C['БЧ-стол-лист']
    big = dict(SHEET, tables=[dict(poly=[[144, 203], [256, 203], [256, 227], [144, 227]])])     # лист: 2,24 × 0,48 м против 2,0 × 0,4 — на 12 % и 20 % больше
    C, _ = run(HEAD + R1 + R2 + RM + MID + TABLE + TAIL, ['--sheet-tables', 'st.json', '--chairs-json', 'ch.json'],
               files={'st.json': big, 'ch.json': dict(CHAIRS4, chairs=CHAIRS4['chairs'] + [[140, 215], [260, 215]])})
    c = C['БЧ-стол-лист']; assert c['status'] == 'look' and '± 10 %' in txt(c) and 'стульев на карте 4, на листе 6' in txt(c), c
    near = dict(SHEET, tables=[dict(poly=[[146, 204.5], [254, 204.5], [254, 225.5], [146, 225.5]])])   # + 8 % и + 5 % — в допуске
    C, _ = run(HEAD + R1 + R2 + RM + MID + TABLE + TAIL, ['--sheet-tables', 'st.json'], files={'st.json': near})
    assert C['БЧ-стол-лист']['status'] == 'pass' and 'не сверено' in C['БЧ-стол-лист']['value'], C['БЧ-стол-лист']

@test
def t_mr_fit_and_gate():
    C, _ = run(HEAD + R1 + R2 + RM + MID + TABLE + TAIL)
    assert C['БЧ-стол-стена']['status'] == 'pass', C['БЧ-стол-стена']                   # зазор до стены ≥ 0,5 м
    tight = table(-20)                                                     # стол к верхней стене: зазор 9 px = 0,18 м < 0,5 м
    C, J = run(HEAD + R1 + R2 + RM + MID + tight + TAIL, ['--gate'])
    c = C['БЧ-стол-стена']; assert c['status'] == 'look' and 'тесно' in txt(c), c
    assert not any('БЧ' in s_ for s_ in J['gate']['stops']), J['gate']['stops']            # шлюз проверки без номера Ч не решает
    assert sum(J['summary'].values()) == len([k for k in C if k.startswith('Ч-')]), J['summary']

ok = 0
for f in T:
    try: f(); ok += 1; print('ok  ', f.__name__)
    except Exception: print('FAIL', f.__name__); traceback.print_exc()
print(f'ok {ok} из {len(T)}'); sys.exit(0 if ok == len(T) else 1)
