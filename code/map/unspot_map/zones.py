"""Помещения и проходы карты — полигонами из файла зон инженерного плана (v012, КМ-23; ОЧ-Б26; строка 272; proposals/both/2026-10-09-
помещения-и-проходы-полигонами Z1–Z3, решение владельца 09.10.2026 В1: «карта берёт полигоны из файла зон»).

Вход — `<OUT>_zones.dxf` рядом с DXF плана (plan/rules/50 §5): помещения — слой `A-921…E-` (контур; дуги — bulge, колонны-пустоты — CIRCLE),
проходы — `A-922…E-`; заливки `…H-` — не читаются (это те же контуры). XDATA `UNSPOT`: `group=7`, `type=room|passage`, `kind`, `number`, `name`,
`area_m2`, `ring=outer|hole`. Без XDATA — по слою (`A-921` — room, `A-922` — passage), кольцо — по вложенности, громко в отчёте.
Словарь `kind` у маршрутов плана разный: `open space` (AutoCAD, `ocg/`) и `open_space` (Revit) — здесь одно слово: пробелы и дефисы -> `_`,
нижний регистр (находка к плану 013 — PLANMAP §7 п. 6).

Кадр — тот же, что у моста: `M_t.npy` (np.save: матрица 2 × 2 построчно, затем t; мм -> px карты; `bridge_convert.py --frame`); свой кадр модуль
не выводит. Выход — `zones.json`: [{"type", "kind", "number", "name", "area_m2", "outer": [[x, y], …], "holes": [[[x, y], …], …]}] в px карты,
плюс справочные `area_m2_calc`, `valid`, `src`. Самопроверка (`selfcheck`): каждый полигон валиден, накладок между зонами 0 (порог — 0,01 м²),
площадь против `area_m2` ± 1 %.

Заливка на карте — группа путей в слое `rooms` под стенами (`data-zone`, `data-kind`) — только ключом `--fill`: по умолчанию выключено,
пока владелец не решил, включать ли её (решение главного чата 13.10.2026 по Р-3; словарь слоёв не меняется — седьмого слоя нет).
Цвет заливки — по типу из канона (map/rules/71 §1, строка 12) или из `--colours` JSON {kind: "#RRGGBB"}; тип без цвета — fill="none",
громко. Канон и числа отрисовки здесь не задаются: цвета канона — только как умолчание для четырёх типов строки 12.

    python3 -m unspot_map.zones <zones.dxf> --frame M_t.npy --out zones.json [--svg plan.svg --fill --svg-out plan_zones.svg] [--colours c.json]
    -> код 0; 3 — самопроверка не прошла (невалидный полигон, накладка, площадь вне ± 1 %), список — в выводе и в zones.json.check"""
import argparse, json, math, re, sys
import numpy as np
from shapely.geometry import Polygon, Point
from shapely.ops import unary_union
from shapely.validation import explain_validity

AREA_TOL = 0.01          # площадь полигона против area_m2 листа зон — ± 1 %
OVERLAP_M2 = 0.01        # накладка двух зон больше 0,01 м² — ошибка
ARC_TOL_MM = 5.0         # дуга bulge -> ломаная: стрелка прогиба хорды ≤ 5 мм (на карте 56,7 px/м — 0,3 px)
CANON_FILL = {'meeting': '#FFF5EB', 'open_space': '#EBF5FF', 'kitchen': '#F8FFEB', 'cabinet': '#F1EBFF'}   # строка 12 (№15) — умолчание


def norm_kind(k):
    """`open space`, `Open-Space`, `open_space` -> `open_space`"""
    return re.sub(r'[\s\-]+', '_', str(k or '').strip().lower()) or None


def load_frame(path):
    """M_t.npy моста: [a, b, c, d, tx, ty] — px = [[a, b], [c, d]] @ мм + t"""
    v = np.load(path).ravel()
    if v.size != 6:
        raise ValueError('кадр %s: ожидается 6 чисел (2 × 2 построчно, затем t), есть %d' % (path, v.size))
    return v[:4].reshape(2, 2), v[4:6]


def arc_points(p0, p1, bulge, tol=ARC_TOL_MM):
    """точки дуги bulge от p0 до p1, без p0, с p1: угол дуги 4·atan(bulge), стрелка хорды каждого куска ≤ tol"""
    p0, p1 = np.asarray(p0, float), np.asarray(p1, float)
    if abs(bulge) < 1e-9:
        return [p1]
    th = 4 * math.atan(bulge); c = np.linalg.norm(p1 - p0)
    if c < 1e-9:
        return [p1]
    r = c / (2 * abs(math.sin(th / 2)))
    n = max(1, int(math.ceil(abs(th) / (2 * math.acos(max(-1.0, min(1.0, 1 - tol / r)))))) if r > tol else 1)
    mid = (p0 + p1) / 2; u = (p1 - p0) / c; nrm = np.array([-u[1], u[0]])
    ctr = mid + nrm * (c / 2) * (1 - bulge * bulge) / (2 * bulge)      # bulge = tan(θ/4): центр — по левой нормали на (c/2)·ctg(θ/2), знак — у θ
    a0 = math.atan2(p0[1] - ctr[1], p0[0] - ctr[0])
    return [ctr + r * np.array([math.cos(a0 + th * i / n), math.sin(a0 + th * i / n)]) for i in range(1, n + 1)]


def ring_of(e, tol=ARC_TOL_MM):
    """LWPOLYLINE (с bulge) или CIRCLE -> кольцо точек в мм; число дуг"""
    if e.dxftype() == 'CIRCLE':
        cw = e.ocs().to_wcs(e.dxf.center); c = np.array([cw[0], cw[1]], float); r = float(e.dxf.radius)
        n = max(12, int(math.ceil(math.pi / math.acos(max(-1.0, 1 - tol / r)))) if r > tol else 12)
        return [c + r * np.array([math.cos(2 * math.pi * i / n), math.sin(2 * math.pi * i / n)]) for i in range(n)], 1
    pts = list(e.get_points('xyb')); out, arcs = [], 0
    ocs = e.ocs() if tuple(e.dxf.extrusion) != (0, 0, 1) else None     # контур в OCS (выдавливание −Z) — в мир, после дуг
    m = len(pts)
    for i in range(m if e.closed else m - 1):
        x0, y0, b = pts[i]; x1, y1, _ = pts[(i + 1) % m]
        if not out:
            out.append(np.array([x0, y0], float))
        if abs(b) > 1e-9:
            arcs += 1
        out += arc_points((x0, y0), (x1, y1), b, tol)
    if len(out) > 1 and np.allclose(out[0], out[-1]):
        out = out[:-1]
    if ocs is not None:
        out = [np.array(ocs.to_wcs((p[0], p[1], e.dxf.elevation))[:2]) for p in out]
    return out, arcs


def _xd(e):
    d = {}
    if e.has_xdata('UNSPOT'):
        for _, v in e.get_xdata('UNSPOT'):
            if isinstance(v, str) and '=' in v:
                k, _, val = v.partition('='); d[k] = val
    return d


def read_zones(dxf_path, log=print):
    """файл зон -> [dict(type, kind, number, name, area_m2, outer_mm: Polygon, holes_mm: [Polygon], arcs, src)] в мм"""
    import ezdxf
    doc = ezdxf.readfile(dxf_path); msp = doc.modelspace()
    outers, holes, noxd, skipped = [], [], 0, {}
    for e in msp:
        lay = e.dxf.layer.upper()
        m = re.match(r'A-92([12])-*E-?$', lay)
        if not m:
            continue
        if e.dxftype() not in ('LWPOLYLINE', 'CIRCLE'):                   # ПК6-К3: сущность слоя зон другого типа — не молча
            skipped[e.dxftype()] = skipped.get(e.dxftype(), 0) + 1
            continue
        xd = _xd(e)
        if not xd:
            noxd += 1
        ring, arcs = ring_of(e)
        if len(ring) < 3:
            log('зоны: контур из %d точек (слой %s, %s) — пропущен' % (len(ring), e.dxf.layer, e.dxf.handle)); continue
        P = Polygon(ring)
        rec = dict(type=xd.get('type') or ('room' if m[1] == '1' else 'passage'), kind=norm_kind(xd.get('kind')), kind_src=xd.get('kind'),
                   number=xd.get('number') or None, name=xd.get('name') or None, area_m2=float(xd['area_m2']) if xd.get('area_m2') else None, area_src=xd.get('area_m2'),
                   poly=P, arcs=arcs, handle=e.dxf.handle, src='xdata' if xd else 'слой')
        ring_kind = xd.get('ring') or ('hole' if e.dxftype() == 'CIRCLE' else None)
        (holes if ring_kind == 'hole' else outers).append(rec) if ring_kind else outers.append(dict(rec, guess=True))
    if noxd:
        log('зоны: ВНИМАНИЕ — %d контуров без XDATA UNSPOT: тип — по слою (A-921 — помещение, A-922 — проход), кольцо — по вложенности' % noxd)
    if skipped:
        log('зоны: ВНИМАНИЕ — на слоях A-921/A-922 пропущено %d объектов не LWPOLYLINE/CIRCLE (%s): контуром зоны они не читаются — проверить файл зон'
            % (sum(skipped.values()), ', '.join('%s %d' % kv for kv in sorted(skipped.items()))))
    read_zones.skipped = dict(skipped)
    guess = [r for r in outers if r.get('guess')]                      # без XDATA: кольцо внутри другого контура того же слоя — пустота
    for r in guess:
        host = [q for q in outers if q is not r and q['type'] == r['type'] and q['poly'].area > r['poly'].area and q['poly'].contains(r['poly'].representative_point())]
        if host:
            outers.remove(r); holes.append(r)
    zones = []
    for r in outers:
        zones.append(dict(r, holes=[]))
    for h in holes:
        # пустота несёт номер своего помещения (XDATA) — хозяин по номеру; без номера — наименьший контур, который её целиком содержит и
        # больше её (помещение внутри open space — само не хозяин пустоты, которую оно заполняет: клиент А 4, «Ecom» и комнаты 38–44)
        inner = h['poly'].buffer(-1.0) if h['poly'].area > 4 else h['poly']
        host = [z for z in zones if h['number'] and z['number'] == h['number'] and z['type'] == h['type'] and z['poly'].contains(inner)]
        host = host or [z for z in zones if z['type'] == h['type'] and z['poly'].area > 1.02 * h['poly'].area and z['poly'].contains(inner)]
        host = host or [z for z in zones if z['poly'].area > 1.02 * h['poly'].area and z['poly'].contains(inner)]
        if not host:
            log('зоны: пустота %s (%s) вне всех контуров — пропущена' % (h['handle'], h['type'])); continue
        min(host, key=lambda z: z['poly'].area)['holes'].append(h)
    for z in zones:
        P = Polygon(z['poly'].exterior.coords, [h['poly'].exterior.coords for h in z['holes']])
        z['poly'] = P
        z['arcs'] += sum(h['arcs'] for h in z['holes'])
    return zones


def selfcheck(zones, tol=AREA_TOL, overlap_m2=OVERLAP_M2):
    """валидность, накладки, площадь против area_m2 (мм² -> м²) -> (список ошибок, сводка)"""
    errs = []
    for i, z in enumerate(zones):
        z['area_m2_calc'] = round(z['poly'].area / 1e6, 3)
        z['valid'] = bool(z['poly'].is_valid)
        if not z['valid']:
            errs.append('невалиден: %s %s (%s)' % (z['type'], z['number'] or z['handle'], explain_validity(z['poly'])))
        # допуск — ± 1 % или половина последнего знака area_m2 листа зон («3.7» — ± 0,05 м²), что больше
        dec = len(str(z.get('area_src') or '').partition('.')[2]); half = 0.5 * 10 ** (-dec) if z.get('area_src') else 0.0
        if z['area_m2'] and abs(z['area_m2_calc'] - z['area_m2']) > max(tol * z['area_m2'], half + 1e-9):
            errs.append('площадь %s %s: %.2f м² против %.2f м² листа зон (%.1f %%)' % (z['type'], z['number'] or z['handle'], z['area_m2_calc'], z['area_m2'],
                                                                                   100 * (z['area_m2_calc'] / z['area_m2'] - 1)))
    from shapely.strtree import STRtree
    P = [z['poly'].buffer(0) for z in zones]; tr = STRtree(P); over = []
    for i, p in enumerate(P):
        for j in tr.query(p):
            j = int(j)
            if j <= i or zones[i]['type'] != zones[j]['type']:      # проход лежит в open space по построению (Z2) — накладка только внутри типа
                continue
            a = p.intersection(P[j]).area / 1e6
            if a > overlap_m2:
                over.append((i, j, a)); errs.append('накладка %s %s × %s %s: %.3f м²' % (zones[i]['type'], zones[i]['number'] or zones[i]['handle'],
                                                                                  zones[j]['type'], zones[j]['number'] or zones[j]['handle'], a))
    rooms_u = unary_union([p for p, z in zip(P, zones) if z['type'] == 'room']) if any(z['type'] == 'room' for z in zones) else None
    out_share = []
    for p, z in zip(P, zones):                                       # проход вне помещений листа зон — доля в сводку (справочно)
        if z['type'] == 'passage' and rooms_u is not None and p.area > 0:
            out_share.append(round(p.difference(rooms_u).area / p.area, 3))
    summ = dict(проходы_вне_помещений_доля_макс=max(out_share) if out_share else None, помещений=sum(z['type'] == 'room' for z in zones), проходов=sum(z['type'] == 'passage' for z in zones),
                пустот=sum(len(z['holes']) for z in zones), дуг=sum(z['arcs'] for z in zones), невалидных=sum(not z['valid'] for z in zones),
                накладок=len(over), площадь_вне_допуска=sum(1 for e in errs if e.startswith('площадь')),
                kind={k: sum(1 for z in zones if z['kind'] == k) for k in sorted({z['kind'] for z in zones}, key=str)})
    return errs, summ


def to_px(zones, M, t):
    """мм -> px карты кадром моста; кольца — списками точек"""
    T = lambda ring: [[round(float(x), 2), round(float(y), 2)] for x, y in (np.asarray(ring.coords)[:-1] @ M.T + t)]
    out = []
    for z in zones:
        out.append(dict(type=z['type'], kind=z['kind'], number=z['number'], name=z['name'], area_m2=z['area_m2'], outer=T(z['poly'].exterior),
                        holes=[T(r) for r in z['poly'].interiors], area_m2_calc=z.get('area_m2_calc'), valid=z.get('valid'), src=z['src'],
                        **({'kind_src': z['kind_src']} if z.get('kind_src') and z['kind_src'] != z['kind'] else {})))
    return out


def fill_paths(zones_px, colours=None, floor_id='f', log=print):
    """группа заливок зон (слой rooms, под стенами): <path data-zone data-kind fill stroke="none"/>; тип без цвета — fill="none", громко"""
    from .svg_map import ring_d
    col = dict(CANON_FILL, **(colours or {})); out, nocol = [], []
    for i, z in enumerate(zones_px):
        c = col.get(z['kind']) or col.get(z['type'])
        if not c:
            nocol.append(z['kind'] or z['type']); c = 'none'
        d = ' '.join([ring_d(z['outer'])] + [ring_d(h) for h in z['holes']])
        nm = (z.get('number') or '') if not z.get('name') else ('%s %s' % (z.get('number') or '', z['name'])).strip()
        out.append(f'<path id="zone-{floor_id}-{i}" data-zone="{z["type"]}" data-kind="{z["kind"] or ""}" data-name="{nm}" d="{d}" fill="{c}" '
                   f'fill-rule="evenodd" stroke="none"/>')
    if nocol:
        log('зоны: ВНИМАНИЕ — нет цвета для %s: fill="none" (цвет — --colours или канон map/rules/71 §1)' % ', '.join(sorted(set(map(str, nocol)))))
    return out


def insert_under_walls(svg_text, paths):
    """заливки зон — первыми в <g id="rooms">: под помещениями с обводкой, свободными стенами и проёмами (порядок rooms — PLANMAP КМ-2)"""
    m = re.search(r'<g id="rooms"[^>]*>', svg_text)
    if not m:
        raise ValueError('в SVG нет группы <g id="rooms"> — заливку зон некуда положить (словарь слоёв map/rules/05 §2)')
    grp = '<g id="rooms-zones" data-layer="rooms">' + ''.join(paths) + '</g>'
    return svg_text[:m.end()] + grp + svg_text[m.end():]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('dxf'); ap.add_argument('--frame', required=True, help='M_t.npy моста (мм -> px карты)')
    ap.add_argument('--out', default='zones.json'); ap.add_argument('--svg'); ap.add_argument('--svg-out')
    ap.add_argument('--fill', action='store_true', help='заливка зон в слое rooms под стенами (по умолчанию выключено, решение Р-3)')
    ap.add_argument('--colours', help='JSON {kind: "#RRGGBB"} — цвет заливки по kind; умолчание — канон строки 12 для четырёх типов')
    a = ap.parse_args()
    zones = read_zones(a.dxf); errs, summ = selfcheck(zones)
    M, t = load_frame(a.frame); zp = to_px(zones, M, t)
    warn = []
    if not zones:
        warn.append('в %s нет контуров A-921/A-922 — zones.json пустой' % a.dxf)
    elif not any(z['type'] == 'passage' for z in zones):                # ПК6-К3: проходов нет — громко, а не «проходов 0» молча
        warn.append('проходов A-922 в файле нет (у маршрута Revit — норма, у AutoCAD — проверить план)')
    for w_ in warn:
        print('зоны: ВНИМАНИЕ — ' + w_)
    if getattr(read_zones, 'skipped', None):                              # уже сказано выводом read_zones — здесь только в сводку
        warn.append('пропущено объектов слоёв A-921/A-922 не LWPOLYLINE/CIRCLE: %s' % ', '.join('%s %d' % kv for kv in sorted(read_zones.skipped.items())))
    summ['предупреждения'] = warn
    json.dump(dict(source=a.dxf, frame=a.frame, zones=zp, check=dict(summ, ошибки=errs)), open(a.out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(json.dumps(summ, ensure_ascii=False)); [print(' -', e) for e in errs]
    if a.fill:
        if not a.svg or not a.svg_out:
            sys.exit('--fill: нужны --svg (карта) и --svg-out')
        txt = open(a.svg, encoding='utf-8').read()
        open(a.svg_out, 'w', encoding='utf-8').write(insert_under_walls(txt, fill_paths(zp, json.load(open(a.colours)) if a.colours else None)))
        print('заливка зон: %d путей в rooms под стенами -> %s' % (len(zp), a.svg_out))
    elif a.svg_out:
        print('заливка зон выключена (по умолчанию, Р-3): --svg-out без --fill не пишется')
    sys.exit(3 if errs else 0)


if __name__ == '__main__':
    main()
