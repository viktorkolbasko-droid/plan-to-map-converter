"""Тест процедур мест v008 (пакет кода 2; ОВ1, ОВ2, ОВ9, ОВ10, ОВ20 б, ОВ21, Н11): без внешних данных.
* assign_chairs — номера ряда, сдвинутые на полстола, получают стулья один к одному и по порядку вдоль ряда (ближайший стул отдал бы
  один стул двум номерам); стул за чужим столом (ряд напротив) — не кандидат;
* keep_off_walls — стол, упёршийся торцом в стену, вдоль ряда не двигается; упёршийся длинной стороной — уходит от стены;
* unspot_map.chairs.detect — кусок размером со стул на заливке стола (торцевой модуль) — не стул; стул из двух кусков — один стул.
    python3 tests/test_places_v008.py — код 0, если всё совпало"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from shapely.geometry import Polygon, LineString
from unspot_map.workplaces import assign_chairs, behind_other_desk, keep_off_walls
from unspot_map.chairs import detect
bad = []
def check(name, got, want):
    ok = got == want; print(('ok   ' if ok else 'FAIL ') + name + ('' if ok else f': {got!r} != {want!r}')); ok or bad.append(name)

ppm = 50.0                                                                  # px на метр
lab = np.zeros((400, 600), int)                                             # ряд из трёх столов 1,4 × 0,7 м (70 × 35 px) и ряд напротив
for i in range(3):
    lab[100:135, 100 + 72 * i:170 + 72 * i] = 1 + i                         # верхний ряд — метки 1..3
    lab[137:172, 100 + 72 * i:170 + 72 * i] = 4 + i                         # нижний ряд спиной к спине — метки 4..6
# номера верхнего ряда сдвинуты влево на полстола (ОВ1): 100+35-36, …; стулья — над серединами столов
nums = [(100 + 72 * i + 35 - 36, 117.0) for i in range(3)]; nl = [lab[117, int(x)] or 1 + i for i, (x, y) in enumerate(nums)]
chairs = [(135.0 + 72 * i, 85.0) for i in range(3)] + [(135.0 + 72 * i, 190.0) for i in range(3)]   # верх — свои, низ — ряда напротив
chl = [0] * 6
# «ближайший стул» — два номера на одном стуле
near = [int(np.argmin([np.hypot(c[0] - x, c[1] - y) for c in chairs[:3]])) for x, y in nums]
check('ОВ1: ближайший стул отдаёт один стул двум номерам (так было)', len(set(near)) < 3, True)
A = assign_chairs(nums, nl, chairs, lab, 1.2 * ppm, chl)
check('ОВ1, ОВ10, Н11: один к одному и по порядку вдоль ряда', [A.get(i) for i in range(3)], [0, 1, 2])
check('ОВ21: стул ряда напротив — за чужим столом', behind_other_desk(lab, (135.0, 117.0), (135.0, 190.0), 1), True)
check('ОВ21: свой стул — не за чужим столом', behind_other_desk(lab, (135.0, 117.0), (135.0, 85.0), 1), False)
A2 = assign_chairs([(135.0, 150.0)], [4], [(135.0, 85.0)], lab, 2.0 * ppm, [0])
check('ОВ21: номер нижнего ряда не берёт стул за верхним столом', A2, {})

# keep_off_walls (ОВ20 б): стена у торца — вдоль ряда стол не двигается; стена вдоль длинной стороны — уходит от неё по короткой
D = Polygon([(100, 100), (170, 100), (170, 135), (100, 135)])
P1 = keep_off_walls([dict(desk=D)], [LineString([(172, 50), (172, 200)])], 4.0)[0]
check('ОВ20 б: торец у стены — стол вдоль ряда не сдвинут', round(P1['desk'].centroid.x, 1), 135.0)
P2 = keep_off_walls([dict(desk=D)], [LineString([(50, 133), (250, 133)])], 4.0)[0]
check('ОВ20 б: длинная сторона у стены — сдвиг по короткой', P2['desk'].centroid.y < 117.5 and round(P2['desk'].centroid.x, 1) == 135.0, True)

# детектор стульев (ОВ2, ОВ9)
m = np.zeros((300, 400), bool)
def ring(x0, y0, w, h): m[y0, x0:x0 + w] = m[y0 + h - 1, x0:x0 + w] = True; m[y0:y0 + h, x0] = m[y0:y0 + h, x0 + w - 1] = True
ring(50, 50, 25, 25)                                                       # стул 0,5 м
ring(150, 50, 25, 25)                                                      # «стул» на заливке стола — торцевой модуль
ring(250, 50, 25, 12); ring(250, 63, 25, 12)                               # стул из двух кусков (сиденье и спинка), зазор 1 px
fill = np.zeros_like(m); fill[45:85, 140:185] = True
base = detect(m, ppm)
check('без ключей — как v007: торцевой модуль считается стулом', any(abs(x - 162) < 6 for x, y in base), True)
ex = detect(m, ppm, exclude=fill)
check('ОВ2: кусок на заливке стола — не стул', any(abs(x - 162) < 6 for x, y in ex), False)
check('ОВ2: настоящий стул остаётся', any(abs(x - 62) < 6 for x, y in ex), True)
j = detect(m, ppm, exclude=fill, join_m=0.06)
check('ОВ9: стул из двух кусков — один стул', sum(1 for x, y in j if abs(x - 262) < 8), 1)
print('итог:', 'всё совпало' if not bad else f'не совпало {len(bad)}: ' + ', '.join(bad)); sys.exit(1 if bad else 0)
