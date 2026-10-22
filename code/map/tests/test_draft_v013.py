"""Тест черновика 25 / 50 / 100 (v013, К13.1; строка 391, №6; map/rules/83 §6, §1; map/rules/82 §0): unspot_map.workplaces.render_draft,
plan_mask_svg, original_in_frame, seat_diameter_px, number_px_range. Без внешних данных.
  низ — серый оригинал 25 %: out = 255 − 0,25 · (255 − серый); вне контура плана (кольцо + 10 px) — белое;
  середина — чистовик 50 %: α = 0,5 · clip((255 − min RGB) / 6, 0, 1); белое чистовика подложку не закрывает;
  верх — места 100 %: столы #E6007E с отступом 1,5 px, затем номера и точки #FFB000 ⌀ 0,26 м (не меньше 6 px) — точку не закрывает соседний стол;
  кегль номера 13–34 px при 54 px/м; насыщенность вне мест ≤ 0,35 — иначе громко; размер — как у чистовика; пересечения столов — resolve_overlaps.
    python3 tests/test_draft_v013.py — код 0, если всё совпало"""
import os, sys, tempfile, io, contextlib
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from PIL import Image, ImageDraw
from unspot_map.workplaces import render_draft, plan_mask_svg, original_in_frame, seat_diameter_px, number_px_range, count_marks
bad = []
def check(name, got, want):
    ok = got == want; print(('ok   ' if ok else 'FAIL ') + name + ('' if ok else f': {got!r} != {want!r}')); ok or bad.append(name)
def quiet(f, *a, **k):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf): r = f(*a, **k, log=print) if f is render_draft else f(*a, **k)
    return r, buf.getvalue()

check('⌀ точки: 54 px/м -> 14,04 px; 111,8 -> 29,07; 10 -> 6 (не меньше 6 px)',
      (round(seat_diameter_px(54), 2), round(seat_diameter_px(111.8), 2), seat_diameter_px(10)), (14.04, 29.07, 6.0))
check('кегль номера: 54 px/м -> 13–34; 111,8 -> 27–70; 27,02 -> 7–17', (number_px_range(54), number_px_range(111.8), number_px_range(27.02)), ((13, 34), (27, 70), (7, 17)))
with tempfile.TemporaryDirectory() as td:
    W, H = 600, 400
    svg = os.path.join(td, 'plan.svg')                                      # помещение 100..500 × 80..320, стена 6 px, заливка #EBF5FF
    open(svg, 'w').write(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W // 2} {H // 2}"><rect x="0" y="0" width="{W // 2}" height="{H // 2}" fill="#FFFFFF"/>'
                         '<g id="underlay" display="none"/><g id="rooms"><path d="M50 40 L250 40 L250 160 L50 160 Z" fill="#FFFFFF" stroke="#CBD2D6" stroke-width="3"/></g>'
                         '<g id="glass"/><g id="furniture"/><g id="icons"/><g id="labels"><text x="10" y="190">ЗАГОЛОВОК</text></g></svg>')
    clean = Image.new('RGB', (W, H), 'white'); dc = ImageDraw.Draw(clean)
    dc.rectangle([97, 77, 503, 323], outline=(0xCB, 0xD2, 0xD6), width=6); dc.rectangle([300, 200, 340, 240], fill=(0xEB, 0xF5, 0xFF))
    cp = os.path.join(td, 'clean.png'); clean.save(cp)
    m = plan_mask_svg(svg, (W, H))
    check('маска контура: внутри помещения — да; 6 px за стеной — да (запас 10 px); 20 px за стеной — нет; угол листа — нет',
          (bool(m[200, 300]), bool(m[200, 509]), bool(m[200, 525]), bool(m[10, 10])), (True, True, False, False))
    src = np.full((H // 2, W // 2, 3), 100, np.uint8); src[0:20, 0:40] = 0          # оригинал: серый 100 и чёрный «штамп» в углу листа
    sp = os.path.join(td, 'src.png'); Image.fromarray(src).save(sp)
    orig = original_in_frame(sp, [[2, 0, 0], [0, 2, 0]], (W, H))
    check('original_in_frame: ×2 — пиксель (150, 100) = серый 100; штамп (10, 10) = 0', (int(orig[100, 150, 0]), int(orig[10, 10, 0])), (100, 0))
    places = [dict(seat='1', desk=[[150, 150], [220, 150], [220, 185], [150, 185]], centre=[185, 167.5], x=185, y=128),
              dict(seat='2', desk=[[150, 230], [220, 230], [220, 265], [150, 265]], centre=[185, 247.5], x=185, y=236)]
    places[1]['y'] = 190                                                     # точка места 2 лежит на краю стола 1 (у 185): её не закрывает стол
    out = os.path.join(td, 'draft.png')
    (recs, info), log = quiet(render_draft, cp, orig, places, out, 100, inside=m)
    im = np.asarray(Image.open(out).convert('RGB')).astype(int)
    g25 = int(255 - 0.25 * (255 - 100) + 0.5)
    check('размер черновика = размеру чистовика', Image.open(out).size, (W, H))
    check(f'низ: серый 25 % внутри плана (белое чистовика не закрывает) = {g25}', tuple(im[120, 400]), (g25,) * 3)
    check('низ: вне контура плана — белое (штамп листа убран)', (tuple(im[10, 10]), tuple(im[390, 590])), ((255,) * 3, (255,) * 3))
    wall = (0xCB, 0xD2, 0xD6); al = 0.5 * min(1.0, (255 - min(wall)) / 6)
    want = tuple(int(np.clip((255 - 0.25 * (255 - 100)) * (1 - al) + c * al + 0.5, 0, 255)) for c in wall)
    check('середина: стена чистовика 50 % поверх серого', tuple(im[200, 100]), want)
    fill = (0xEB, 0xF5, 0xFF); alf = 0.5 * min(1.0, (255 - min(fill)) / 6)
    want = tuple(int(np.clip((255 - 0.25 * (255 - 100)) * (1 - alf) + c * alf + 0.5, 0, 255)) for c in fill)
    check('середина: заливка чистовика по α = 0,5 · clip((255 − min) / 6)', tuple(im[220, 320]), want)
    check('верх: стол #E6007E, у края — отступ 1,5 px (пиксель на кромке — не стол)', (tuple(im[160, 160]), tuple(im[150, 160]) == (0xE6, 0, 0x7E)), ((0xE6, 0, 0x7E), False))
    row = (np.abs(im[128] - np.array([0xFF, 0xB0, 0])).sum(1) < 30)
    check('верх: точка стула ⌀ 0,26 м при 100 px/м — 26 ± 1 px', abs(int(row.sum()) - 26) <= 1, True)
    check('верх: точка места 2 на кромке стола 1 — не закрыта столом (вторым проходом)', tuple(im[182, 185]), (0xFF, 0xB0, 0))
    check('номер: кегль в пределах 13–34 px при 54 px/м (100 px/м: 24–63)', all(24 <= r['number_px'] <= 63 for r in recs), True)
    check('info: ⌀ точки 26 px, кегль 24–63, насыщенных вне мест 0, без стола 0', (info['seat_d_px'], info['number_px'], info['sat_over'], info['no_desk']), (26.0, [24, 63], 0, []))
    check('count_marks: 2 стола, 2 места', count_marks(out), (2, 2))
    hot = clean.copy(); ImageDraw.Draw(hot).rectangle([400, 100, 450, 150], fill=(255, 0, 0)); hp = os.path.join(td, 'hot.png'); hot.save(hp)
    (r2, i2), log2 = quiet(render_draft, hp, orig, places, os.path.join(td, 'hot_d.png'), 100, inside=m)
    check('насыщенность: красное чистовика вне мест > 0,35 — громко', (i2['sat_over'] > 0, 'ВНИМАНИЕ — вне мест' in log2), (True, True))
    ov = [dict(seat='a', desk=[[150, 150], [220, 150], [220, 185], [150, 185]], x=185, y=128), dict(seat='b', desk=[[210, 150], [280, 150], [280, 185], [210, 185]], x=245, y=128),
          dict(seat='c', desk=None, x=400, y=280)]
    (r3, i3), log3 = quiet(render_draft, cp, orig, ov, os.path.join(td, 'ov.png'), 100, inside=m)
    check('пересечение столов: resolve_overlaps подрезал 2, записи изменены', (i3['clipped'], max(x for x, _ in r3[0]['desk']) <= 215.1, min(x for x, _ in r3[1]['desk']) >= 214.9), (2, True, True))
    check('desk пуст — громко, в info no_desk', (i3['no_desk'], 'без многоугольника стола' in log3), (['c'], True))
    check('count_marks после подрезки: 2 стола, 3 точки', count_marks(os.path.join(td, 'ov.png')), (2, 3))
    (r4, i4), log4 = quiet(render_draft, cp, None, places, os.path.join(td, 'w.png'), 100)
    check('без оригинала и без маски — громко', ('оригинала нет' in log4, 'маски контура плана нет' in log4), (True, True))
print('итог:', 'всё совпало' if not bad else f'расхождений {len(bad)}'); sys.exit(1 if bad else 0)
