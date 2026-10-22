"""Тест мест v012 (КМ-20, КМ-21) без внешних данных: синтетический DXF плана, синтетические линии листа, синтетический PDF.
КМ-21 (places_plan): номера мест — стиль текста, который стоит на столах (размер «90» на каждом столе — не номер); «3 4» — два номера по ходу строки;
  номер -> стол один к одному; стол руководителя (dtable) с номером — стол места, desk без номера — мебель; стул -> стол от центра стола; тумба у торца —
  ключом pedestal; стол в стене карты: cut — срезан (модуль на месте), shift — сдвинут внутрь, размер прежний; chairs.json — frame plan;
  без номеров — бенч 2,8 м делится на 2 модуля этажа 1,4 м, модуль без стула — не место; без XDATA — класс по слою и блоку, громко.
КМ-20 (desks_lines): стол по опоре четырёх сторон с осевой поверх и стулом у длинной стороны — место; прямоугольник с крестом — стеллаж, не место;
  прямоугольник без стула — не место; растр 100 px/м (LSD) — те же столы; линий нет — громко.
Порядок выбора (workplaces.main): лист без заливки столов и без номеров — способ «lines»; в выводе — «заливка столов: нет; номера: нет».
Запуск из любой папки: python3 tests/test_places_v012.py — код 0, если всё совпало."""
import io, json, math, os, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np, ezdxf
from shapely.geometry import Polygon, Point
from unspot_map import places_plan as PP, desks_lines as DL
bad = []
def check(name, got, want):
    ok = got == want; print(('ok   ' if ok else 'FAIL ') + name + ('' if ok else f': {got!r} != {want!r}')); ok or bad.append(name)
CODE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PPM = 50.0                                                   # px карты на м: кадр мм -> px = 0,05
M, T = np.array([[0.05, 0.0], [0.0, -0.05]]), np.array([100.0, 1100.0])


def block(doc, name, w, h):
    b = doc.blocks.new(name); b.add_lwpolyline([(0, 0), (w, 0), (w, h), (0, h)], close=True); return name


def plan_dxf(path, numbers=True, xdata=True):
    doc = ezdxf.new(); doc.appids.add('UNSPOT'); msp = doc.modelspace()
    for n in ('A-82----E-', 'A-90----T-'): doc.layers.add(n)
    block(doc, 'B_desk', 1400, 700); block(doc, 'B_chair', 500, 500); block(doc, 'B_dtable', 1800, 900); block(doc, 'B_ped', 400, 700); block(doc, 'Bench_2800', 2800, 700)
    def ins(name, x, y, typ, rot=0):
        e = msp.add_blockref(name, (x, y), dxfattribs={'layer': 'A-82----E-', 'rotation': rot})
        if xdata: e.set_xdata('UNSPOT', [(1000, 'group=4'), (1000, 'type=%s' % typ)])
        return e
    def txt(s, x, y, h=200, col=None):
        e = msp.add_text(s, dxfattribs={'layer': 'A-90----T-', 'height': h, 'insert': (x, y)})
        if col: e.dxf.true_color = col
    # ряд из трёх столов 1,4 × 0,7 м с x = 2 000, 3 400, 4 800; стулья — под столами (y < 2 000)
    for k in range(3):
        ins('B_desk', 2000 + 1400 * k, 2000, 'desk'); ins('B_chair', 2450 + 1400 * k, 1300, 'chair')
        txt('90', 2100 + 1400 * k, 2450, 120)                  # размер на каждом столе — не номер
    ins('B_desk', 2000, 5000, 'desk'); ins('B_chair', 2450, 4300, 'chair'); ins('B_ped', 3400, 5000, 'pedestal')    # стол 4 + тумба у торца
    ins('B_dtable', 7000, 5000, 'dtable'); ins('B_chair', 7650, 4300, 'chair'); ins('B_desk', 9000, 5000, 'desk')   # стол руководителя с номером, desk рядом — мебель
    ins('B_desk', 2000, 8000, 'desk'); ins('B_chair', 2450, 8800, 'chair')                                           # стол 6 — у стены (стена — y = 8 000)
    if numbers:
        txt('1', 2500, 2250, col=0xFF007F); txt('3 4', 4900, 2250, col=0xFF007F)    # «3 4» — номера двух столов по ходу строки (стол 3 400 и 4 800)
        txt('5', 2500, 5250, col=0xFF007F); txt('7', 7700, 5300, col=0xFF007F); txt('6', 2500, 8250, col=0xFF007F)
    else:
        ins('Bench_2800', 2000, 11000, 'desk'); ins('B_chair', 2450, 10300, 'chair'); ins('B_chair', 3850, 10300, 'chair')
        ins('Bench_2800', 6000, 11000, 'desk'); ins('B_chair', 6450, 10300, 'chair')       # второй модуль без стула — не место
    doc.saveas(path)


with tempfile.TemporaryDirectory() as td:
    p = os.path.join(td, 'plan.dxf'); plan_dxf(p)
    svg = os.path.join(td, 'map.svg')                       # стена карты по y = 8 000 мм -> px y = 700, толщина 6 px
    open(svg, 'w').write('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 1200"><g id="rooms">'
                         '<path id="wall-f-0" d="M150 700 L300 700" fill="none" stroke="#CBD2D6" stroke-width="6"/></g></svg>')
    logs = []
    pl, ch, fd, peds, info = PP.build(p, M, T, PPM, svg, 'cut', log=logs.append)
    num = sorted(r['number'] for r in pl)
    check('КМ-21: номера — стиль на столах; «90» — не номер; «3 4» — два номера', num, ['1', '3', '4', '5', '6', '7'])
    byn = {r['number']: r for r in pl}
    cx = lambda r: round((r['centre'][0] - 100) / 0.05)
    check('КМ-21: номер -> стол по ходу ряда: 1 -> x 2 700, 3 -> 4 100, 4 -> 5 500 мм', (cx(byn['1']), cx(byn['3']), cx(byn['4'])), (2700, 4100, 5500))
    check('КМ-21: стол руководителя с номером «7» — стол места 1,8 × 0,9 м; desk без номера — мебель', (byn['7']['desk_type'], byn['7']['size_m'], len(fd)), ('dtable', [1.8, 0.9], 1))
    check('КМ-21: место — по стулу у каждого стола', {r['by'] for r in pl}, {'стул'})
    check('КМ-21: тумба у торца стола 5 — ключом pedestal, не в столе', ('pedestal' in byn['5'], byn['5']['size_m']), (True, [1.4, 0.7]))
    check('КМ-21: стол в стене, cut — срезан, модуль на месте (центр по x тот же)', ('clipped_px2' in byn['6'], cx(byn['6'])), (True, 2700))
    pl2, *_ = PP.build(p, M, T, PPM, svg, 'shift', log=lambda s: None)
    b6 = {r['number']: r for r in pl2}['6']
    check('КМ-21: стол в стене, shift — сдвинут внутрь, размер прежний', ('moved_m' in b6, b6['size_m']), (True, [1.4, 0.7]))
    np.save(os.path.join(td, 'M_t.npy'), np.r_[M.ravel(), T])
    r = subprocess.run([sys.executable, '-m', 'unspot_map.places_plan', p, '--frame', os.path.join(td, 'M_t.npy'), '--px-per-m', str(PPM), '--svg', svg,
                        '--out', os.path.join(td, 'places.json'), '--chairs-out', os.path.join(td, 'chairs.json')], cwd=CODE, capture_output=True, text=True)
    pj, cj = json.load(open(os.path.join(td, 'places.json'))), json.load(open(os.path.join(td, 'chairs.json')))
    check('КМ-21: places.json — схема v011 + src plan, умолчание shift; chairs.json — frame plan', (pj['frame'], pj['places'][0]['src'], pj['desk_in_wall'], cj['frame'], len(cj['chairs'])),
          ('artefact3 px', 'plan', 'shift', 'plan', 6))
    p2 = os.path.join(td, 'plan_nonum.dxf'); plan_dxf(p2, numbers=False); logs = []
    pl, ch, fd, peds, info = PP.build(p2, M, T, PPM, None, 'shift', log=logs.append)
    check('КМ-21: без номеров — громко; бенч 2,8 м — 2 модуля 1,4 м; модуль без стула — не место', (any('номеров мест нет' in x for x in logs), info['modules'] - 6, info['modules_without_chair'] >= 1),
          (True, 4, True))
    check('КМ-21: без номеров — мест = модулей со стулом (5 одиночных со стулом + 2 + 1)', info['places'], 8)
    p3 = os.path.join(td, 'plan_noxd.dxf'); plan_dxf(p3, xdata=False); logs = []
    pl, *_ = PP.build(p3, M, T, PPM, None, 'shift', log=logs.append)
    check('КМ-21: без XDATA — класс по слою и блоку, громко; мест 6', (any('нет XDATA' in x for x in logs), len(pl)), (True, 6))

    # КМ-20: столы по линиям (px, 50 px/м): стол 1,4 × 0,7 с осевой поверх и стулом; стол с крестом; стол без стула
    S = []
    def rect(x, y, w, h): S.extend([(x, y, x + w, y), (x + w, y, x + w, y + h), (x + w, y + h, x, y + h), (x, y + h, x, y)])
    def chair(cx_, cy_, r=10):
        for k in range(12):
            a0, a1 = 2 * math.pi * k / 12, 2 * math.pi * (k + 1) / 12; S.append((cx_ + r * math.cos(a0), cy_ + r * math.sin(a0), cx_ + r * math.cos(a1), cy_ + r * math.sin(a1)))
        rect(cx_ - 9, cy_ - 9, 18, 18); rect(cx_ - 6, cy_ - 6, 12, 12); rect(cx_ - 3, cy_ - 3, 6, 6); S.append((cx_ - 10, cy_ + 12, cx_ + 10, cy_ + 12))   # сиденье, спинка
    for k in range(4):
        rect(100 + 75 * k, 100, 70, 35); chair(135 + 75 * k, 155)
    rect(100, 300, 70, 35); S += [(100, 300, 170, 335), (170, 300, 100, 335)]                 # крест — стеллаж
    rect(300, 300, 70, 35)                                                                   # без стула
    for k in range(40): S.append((20 + 12 * k, 117, 26 + 12 * k, 117))                         # осевая пунктиром поверх ряда столов
    for k in range(40): S.append((20 + 12 * k, 600, 26 + 12 * k, 600))
    S = np.array(S, float); logs = []
    D, X, plain, inf = DL.detect(S, PPM, log=logs.append)
    check('КМ-20: вектор — 4 стола со стулом, крест — стеллаж, без стула — не место', (len(D), len(X), len([r for r in plain if Polygon(r['poly']).centroid.x > 290])), (4, 1, 1))
    check('КМ-20: место — со стороны стула (под столом)', all(r['seat'][1] > 135 for r in D), True)
    from PIL import Image, ImageDraw
    im = Image.new('L', (1040, 840), 255); d = ImageDraw.Draw(im)                            # растр 100 px/м: те же линии, толщина 2 px
    for s in S: d.line([(2 * s[0], 2 * s[1]), (2 * s[2], 2 * s[3])], fill=0, width=2)
    g = np.asarray(im)
    D2, X2, plain2, inf2 = DL.detect_raster(g, 100.0, log=lambda s: None)
    check('КМ-20: растр 100 px/м (LSD) — 4 стола со стулом, крест — не место', (len(D2), all(Polygon(r['poly']).centroid.y < 260 for r in D2)), (4, True))
    D3, *_ = DL.detect(np.zeros((0, 4)), PPM, log=logs.append)
    check('КМ-20: линий нет — громко «линии не дали ни одного стола»', (len(D3), any('ни одного стола' in x for x in logs)), (0, True))

    # порядок выбора: PDF без заливки столов и без номеров — способ «lines»
    import pymupdf
    from source_intake import intake
    doc = pymupdf.open(); pg = doc.new_page(width=842, height=595); k = 72 / 25.4 * 10 / 1000    # 1:100: 1 мм натуры = 0,0283 pt
    def prect(x, y, w, h): pg.draw_rect(pymupdf.Rect(x * k, y * k, (x + w) * k, (y + h) * k), color=(0, 0, 0), width=0.3)
    for i in range(4):
        prect(2000 + 1500 * i, 2000, 1400, 700); pg.draw_circle(((2700 + 1500 * i) * k, 3150 * k), 220 * k, color=(0, 0, 0), width=0.3)
        prect(2700 + 1500 * i - 200, 2950, 400, 400)
    for j in range(520): pg.draw_line((5 + j * 1.5, 500), (5 + j * 1.5 + 0.6, 520), color=(0, 0, 0), width=0.2)   # штриховка — линий больше 500
    pg.draw_rect(pymupdf.Rect(600, 400, 600 + 1400 * k, 400 + 700 * k), color=None, fill=(0.7, 0.7, 0.7))         # серая заливка размера стола без номера
    for i, t_ in enumerate(('1', '2', '3', '12')): pg.insert_text((40 + 30 * i, 40), t_, fontsize=8)              # «номера» — оси, не на заливке
    pdf = os.path.join(td, 'sheet.pdf'); doc.save(pdf); rep = intake(pdf, os.path.join(td, 'it'))
    ppm_work = rep['render']['to_pixels'][0] * k * 1000                                      # px work.png на м натуры
    r = subprocess.run([sys.executable, '-m', 'unspot_map.workplaces', '--intake', os.path.join(td, 'it', 'intake.json'), '--src', pdf, '--px-per-m', str(ppm_work),
                        '--out', os.path.join(td, 'wp.json')], cwd=CODE, capture_output=True, text=True)
    w = json.load(open(os.path.join(td, 'wp.json')))
    check('порядок: заливка есть, «номера» (оси) не на заливке — способ «заливка и номера» не годится, громко; способ lines', (w['method'], 'заливка столов (серый 150–215): да' in r.stdout,
          'номера не на заливке столов' in r.stdout), ('lines', True, True))
    check('порядок: по линиям — 4 места', len(w['places']), 4)
print('итог:', 'всё совпало' if not bad else f'расхождений {len(bad)}'); sys.exit(1 if bad else 0)
