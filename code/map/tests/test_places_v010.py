"""Тест мест v010 (пакет кода 4; К-8, №90, map/rules/61 §2.4): тумба или приставка у торца стола — не часть места, без внешних данных.
* стол и тумба одной заливкой (1,4 + 0,4 = 1,8 м — в диапазоне модуля 1,25–1,85 м; v009 брал компоненту целиком столом) — стол 1,4 м у номера,
  тумба — отдельно, ключом 'pedestal';
* то же, 1,4 + 0,5 = 1,9 м (за диапазоном; v009 ставил модуль по центру компоненты — стол наезжал на тумбу) — так же;
* тумба отдельной компонентой у торца (между столом и тумбой контур листа, как у клиент Б, 40 этаж, места 157, 166, 169, 178) — стол не
  меняется, тумба — ключом 'pedestal';
* контроль: стол без тумбы и стол рядом с соседним столом ряда — без 'pedestal', размер стола прежний.
    python3 tests/test_places_v010.py — код 0, если всё совпало"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from unspot_map.workplaces import build
from unspot_map.frame import Affine
bad = []
def check(name, got, want, tol=None):
    ok = (got is not None and abs(got - want) <= tol) if tol is not None else got == want
    print(('ok   ' if ok else 'FAIL ') + name + ('' if ok else f': {got!r} != {want!r}')); ok or bad.append(name)

ppm = 50.0                                                                  # px на метр; стол 1,4 × 0,7 м = 70 × 35 px
lab = np.zeros((420, 900), np.int32); seats = []; L = 0
def comp(x0, y0, w, h):
    global L; L += 1; lab[y0:y0 + h, x0:x0 + w] = L; return L
for i in range(5):                                                          # ряд из пяти обычных столов — модуль этажа 1,4 × 0,7 м
    comp(40 + 72 * i, 40, 70, 35); seats.append(dict(n=100 + i, x=40 + 72 * i + 35, y=57))
comp(40, 140, 90, 35); seats.append(dict(n=200, x=40 + 35, y=157))          # стол 70 px + тумба 20 px одной заливкой: номер — на столе (слева)
comp(240, 140, 95, 35); seats.append(dict(n=201, x=240 + 95 - 35, y=157))   # стол 70 px + тумба 25 px: тумба слева, номер — справа
comp(440, 240, 70, 35); seats.append(dict(n=202, x=440 + 35, y=257))       # стол; тумба — отдельной компонентой у торца через контур 1 px
comp(511, 240, 21, 36)
comp(640, 240, 70, 35); seats.append(dict(n=203, x=640 + 35, y=257))       # контроль: стол и соседний стол ряда через 2 px — не тумба
comp(712, 240, 70, 35); seats.append(dict(n=204, x=712 + 35, y=257))
P = {p['n']: p for p in build(seats, lab, Affine.scale_shift(1, 1), [], ppm)}
ln = lambda g: round(max(np.hypot(*(np.array(g.exterior.coords[1]) - np.array(g.exterior.coords[0]))),
                         np.hypot(*(np.array(g.exterior.coords[2]) - np.array(g.exterior.coords[1])))) / ppm, 2)
cx = lambda g: round(g.centroid.x, 1)
check('№90: слитые стол и тумба 1,8 м — стол 1,4 м', ln(P[200]['desk']), 1.4, 0.03)
check('№90: слитые 1,8 м — стол у номера (центр 75 px)', cx(P[200]['desk']), 75.0, 1.5)
check('№90: слитые 1,8 м — тумба отдельно (глубина 0,7 м)', ln(P[200]['pedestal']) if 'pedestal' in P[200] else None, 0.7, 0.03)   # длинная сторона тумбы — глубина 0,7 м
check('№90: тумба — у торца, не на столе (центр 120 px)', cx(P[200]['pedestal']) if 'pedestal' in P[200] else None, 120.0, 1.5)
check('№90: слитые 1,9 м — стол 1,4 м', ln(P[201]['desk']), 1.4, 0.03)
check('№90: слитые 1,9 м — стол у номера (центр 300 px)', cx(P[201]['desk']), 300.0, 1.5)
check('№90: слитые 1,9 м — тумба 0,5 м слева (центр 252,5 px)', cx(P[201]['pedestal']) if 'pedestal' in P[201] else None, 252.5, 1.5)
check('№90: тумба отдельной компонентой — стол не меняется (1,4 м)', ln(P[202]['desk']), 1.4, 0.03)
check('№90: тумба отдельной компонентой — найдена у торца', 'pedestal' in P[202], True)
check('контроль: обычный стол — без тумбы', 'pedestal' in P[100], False)
check('контроль: соседний стол ряда — не тумба', ('pedestal' in P[203], 'pedestal' in P[204]), (False, False))
check('контроль: обычный стол — 1,4 м', ln(P[103]['desk']), 1.4, 0.03)
print('итог:', 'всё совпало' if not bad else f'не совпало {len(bad)}: ' + ', '.join(bad)); sys.exit(1 if bad else 0)
