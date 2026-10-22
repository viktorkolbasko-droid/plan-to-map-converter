#!/usr/bin/env python3
"""bridge_selfcheck.py — карта из конвертера против своего инженерного плана (без эталонной карты и без исходника).
Полнота: доля осевой длины тел стен инженерного плана (A-21/221/222/223, стекло A-22G/A-31), у которой ось карты ближе 6 px.
Точность: доля длины осей карты, лежащих ближе 6 px к телу стены или стеклу инженерного плана.
Плюс сводка отчёта конвертера: помещений, с номером, площадь против марки Revit, слипшиеся, проёмы.
v009 (мост 0.30): слои — по коду элемента ISO 13567 (bridge_convert.read_dxf): ещё стекло заливкой (22G, 31), стены одной линией и
грани массивов (план листа AutoCAD); К7 — СТОП моста (`стоп` отчёта) и площадь по маркам — в сводке.
v011 (мост 0.32, ПК4-К13): «короб против туши листа» — контур каждого короба колонны (column-b-box*) против всей туши плана (линии
и границы заливок DXF): доля точек контура дальше BOX_INK_M от туши; p90 дальше BOX_INK_M — короб шире рамки обшивки листа, место — в
`короб_против_туши` с флагом.
v012 (мост 0.33, КМ-11): помещения SVG — `невалидных`, `накладок` (допуск Ч-14: T²/4, вложенное ≥ 98 % — не накладка), `помещений_в_SVG`
против отчёта моста.
Запуск: python3 bridge_selfcheck.py plan.dxf conv.svg conv.json [--frame M_t.npy] [--px-per-m 52.49]"""
import argparse, json, math, sys, os, collections, re
import numpy as np, cv2
from scipy import ndimage
from skimage.morphology import skeletonize
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bridge_convert as B
import bridge_eval as EV

BOX_INK_M = 0.15                                           # v011: контур короба дальше 0,15 м от туши плана на 10 % длины и больше — короб шире рамки листа

def plan_ink(D, C):
    """v011: вся тушь плана в px карты: линии и границы заливок всех классов read_dxf"""
    ink = C.img()
    for cls in ('ext', 'int'):
        for rings in D[cls]:
            for P in rings: C.line(ink, np.vstack([P, P[:1]]), 1.0)
    for key in ('col_h', 'glass_h', 'fglass_h', 'zone'):
        for R in D[key]:
            for P in R: C.line(ink, np.vstack([P, P[:1]]), 1.0)
    for wr, R in D['massif']:
        for P in R: C.line(ink, np.vstack([P, P[:1]]), 1.0)
    for wr, segs in D['wline']:
        for P in segs: C.line(ink, P, 1.0)
    for key in ('glass', 'fglass', 'light', 'door', 'cab', 'sep', 'lift', 'stair', 'col', 'skip', 'curtain'):
        for item in D[key]:
            for P in B.segs_of(item): C.line(ink, P, 1.0)
            if key == 'col' and len(item) > 2:
                for P in item[2]: C.line(ink, np.vstack([P, P[:1]]), 1.0)
    return ink > 0

def boxes_vs_ink(svg, ink, pxm, thr_m=BOX_INK_M):
    """v011 (ПК4-К13): короба колонн SVG моста против туши плана -> [{id, x, y, p90_м, max_м, доля_дальше, флаг}]"""
    dist = ndimage.distance_transform_edt(~ink); H, W = ink.shape; out = []
    t = open(svg, encoding='utf-8').read()
    for m in re.finditer(r'<path ([^>]*)/>', t):
        at = dict(re.findall(r'([\w-]+)="([^"]*)"', m.group(1)))
        if at.get('data-type') != 'column' or at.get('data-kind') != 'box': continue
        pts = np.array([tuple(map(float, z.split())) for z in re.findall(r'[ML]\s*([-\d.]+ [-\d.]+)', at['d'])])
        if len(pts) < 3: continue
        Q = np.vstack([pts, pts[:1]]); smp = []
        for a_, b_ in zip(Q[:-1], Q[1:]):
            n_ = max(2, int(np.hypot(*(b_ - a_)))); smp.append(a_ + (b_ - a_) * np.linspace(0, 1, n_, endpoint=False)[:, None])
        S = np.vstack(smp); ix = np.clip(np.round(S[:, 0]).astype(int), 0, W - 1); iy = np.clip(np.round(S[:, 1]).astype(int), 0, H - 1)
        d = dist[iy, ix] / pxm; p90 = float(np.percentile(d, 90)); far = float(np.mean(d > thr_m)); c = pts.mean(0)
        out.append(dict(id=at.get('id'), x=round(float(c[0])), y=round(float(c[1])), p90_м=round(p90, 3), max_м=round(float(d.max()), 3), доля_дальше=round(far, 3),
                        флаг=p90 > thr_m))
    return out

def svg_rooms(svg, T, n_rep):
    """v012 (КМ-11, Ф1-2, ПК4-К10, Н-E11): помещения SVG моста после всех шагов — валидность контуров и накладки, допуск как Ч-14 (T²/4;
    вложенное ≥ 98 % меньшего — не накладка); число помещений SVG против отчёта моста"""
    import bridge_graph as BG
    from shapely.strtree import STRtree
    M = BG.Model(open(svg, encoding='utf-8').read()); R = [e for e in M.els('room') if e['subs'] and len(e['subs'][0]['pts']) >= 3]
    G = [M.poly(e) for e in R]; inv = [e['id'] for e, g in zip(R, G) if not g.is_valid]; ov, nest = [], 0
    ok = [g if g.is_valid else g.buffer(0) for g in G]; tr = STRtree(ok)
    for i, g in enumerate(ok):
        for j in (int(j) for j in tr.query(g) if int(j) > i):
            x = g.intersection(ok[j]).area
            if x > T * T / 4:
                if x >= 0.98 * min(g.area, ok[j].area): nest += 1
                else: ov.append(dict(a=R[i]['id'], b=R[j]['id'], px2=round(x, 1)))
    return collections.OrderedDict(помещений_в_SVG=len(R), помещений_как_в_отчёте=len(R) == n_rep, невалидных=inv, накладок=len(ov),
                                   накладок_px2=round(sum(o['px2'] for o in ov), 1), накладки=ov[:30], вложенных=nest)

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('dxf'); ap.add_argument('svg'); ap.add_argument('report')
    ap.add_argument('--frame'); ap.add_argument('--px-per-m', type=float, default=52.49); ap.add_argument('--out')
    a = ap.parse_args(); pxm = a.px_per_m
    D = B.read_dxf(a.dxf); M, t = B.frame_of(D, pxm, a.frame)
    W, H, Rc, Ac, Gc, Dc = EV.load(a.svg); C = B.Canvas(W, H, M, t, 1)
    body = C.img()
    for cls in ('ext', 'int'):
        for rings in D[cls]: C.fill(body, rings)
    glass = C.img()
    for key in ('glass', 'fglass'):
        for item in D[key]:
            for P in B.segs_of(item): C.line(glass, P, 1.0)
    for key in ('glass_h', 'fglass_h'):                      # v009: стекло заливкой (лист AutoCAD)
        for R in D[key]: C.fill(glass, R)
    for wr, segs in D['wline']:                              # v009: линии слоёв стен (контуры тел и стены одной линией)
        for P in segs: C.line(body, P, 1.0)
    for wr, R in D['massif']:                                # v009: грань массива
        for P in R: C.line(body, np.vstack([P, P[:1]]), 1.0)
    glass = cv2.morphologyEx(glass, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    ref = (body > 0) | (glass > 0)                         # полнота — по телам стен и стеклу
    sup = C.img()                                           # опора для точности: ещё лёгкие перегородки, двери, шкафы, разделители
    for key in ('light', 'door', 'cab', 'sep', 'lift', 'stair'):
        for item in D[key]:
            for P_ in B.segs_of(item): C.line(sup, P_, 1.0)
    supp = ref | (sup > 0)
    sk = skeletonize(ref)
    conv = EV.raster(Ac + Gc, W, H)
    Dconv = ndimage.distance_transform_edt(~conv); Dref = ndimage.distance_transform_edt(~supp)
    ys, xs = np.nonzero(sk); rec = float(np.mean(Dconv[ys, xs] <= 6)) if len(xs) else None
    P = np.vstack(Ac + Gc) if (Ac or Gc) else np.zeros((0, 2)); q = np.round(P).astype(int)
    q[:, 0] = q[:, 0].clip(0, W - 1); q[:, 1] = q[:, 1].clip(0, H - 1)
    prec = float(np.mean(Dref[q[:, 1], q[:, 0]] <= 6)) if len(q) else None
    r = json.load(open(a.report, encoding='utf-8'))
    out = collections.OrderedDict(
        dxf=a.dxf, стены_плана_м=round(len(xs) / pxm, 1), полнота_осей=round(rec, 3) if rec is not None else None,
        оси_карты_м=round(len(P) / pxm, 1), точность_осей=round(prec, 3) if prec is not None else None,
        помещений=r['помещений'], закрытых=r['закрытых'], открытых=r['открытых'],
        с_номером=sum(1 for p in r['помещения'] if p['num']), с_именем=sum(1 for p in r['помещения'] if p['name']),
        марок_с_площадью=len([p for p in r['помещения'] if p['num']]), площадь_не_сходится=r.get('площадь_против_марки', {}),
        слиплись=r.get('слиплись', []), деление_водоразделом=r.get('разделено_водоразделом', []),
        проёмов=r.get('проёмов'), замыканий=r.get('замыканий'), шкафы_как_стена=r.get('шкафы_как_стена'),
        снято_м=r.get('снято_м'), рёбра_м=r.get('рёбра_по_классам_м'), площадь=r.get('площадь'), стоп=r.get('стоп'), марки=r.get('марки'))
    out.update(svg_rooms(a.svg, r.get('T', 6.0), r['помещений']))   # v012 (КМ-11): валидность и накладки помещений SVG, счёт помещений
    bx = boxes_vs_ink(a.svg, plan_ink(D, C), pxm)               # v011 (ПК4-К13): короб против туши листа
    out['короб_против_туши'] = dict(порог_м=BOX_INK_M, коробов=len(bx), шире_рамки=[b for b in bx if b['флаг']], все=bx)
    if a.out: json.dump(out, open(a.out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1, default=str)
    print(json.dumps(out, ensure_ascii=False, default=str))

if __name__ == '__main__': main()
