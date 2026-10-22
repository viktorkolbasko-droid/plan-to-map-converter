#!/usr/bin/env python3
"""bridge_eval.py — сверка геометрии карты из конвертера (bridge_convert.py) с принятой картой того же этажа.
Только чтение. Метрики:
  1. помещения: лучшее IoU для каждого помещения эталона; совпало — IoU ≥ 0,8; номер/имя; закрыто/открыто;
  2. оси стен (контуры закрытых помещений и свободные стены): доля длины эталона ближе 3 / 6 px к осям конвертера
     (полнота) и наоборот (точность);
  3. стекло (окна и стеклянные перегородки) — так же;
  4. проёмы: центр ближе 15 px и длина ±30 %.
Запуск: python3 bridge_eval.py conv.svg ref.svg [--skip-ref room-f5-shaft_9] [--out eval.json] [--crops prefix]"""
import argparse, json, math, re, collections
import numpy as np, cv2
import xml.etree.ElementTree as ET
from svgpathtools import parse_path
from scipy import ndimage
from shapely.geometry import Polygon, LineString
from shapely.ops import unary_union

WALL, GLASS = '#CBD2D6', '#86C5FB'

def sample(d, step=1.0):
    p = parse_path(d); pts = []
    for seg in p:
        L = seg.length(error=1e-3); n = max(2, int(math.ceil(L / step)) + 1)
        pts += [(seg.point(t).real, seg.point(t).imag) for t in np.linspace(0, 1, n)]
    return np.array(pts)

def load(path):
    root = ET.parse(path).getroot(); vb = [float(v) for v in root.get('viewBox').split()]
    W, H = int(vb[2]), int(vb[3])
    rooms, axes, glass, doors = [], [], [], []
    for g in root:
        gid = g.get('id')
        for el in g.iter():
            if el.tag.split('}')[-1] != 'path': continue
            iid, d = el.get('id') or '', el.get('d')
            if not d: continue
            st, sw, fill = el.get('stroke'), el.get('stroke-width'), el.get('fill')
            if gid == 'rooms' and re.match(r'room-', iid):
                P = sample(d, 2.0)
                try: poly = Polygon(P).buffer(0)
                except Exception: continue
                if poly.is_empty or poly.area < 10: continue
                rooms.append(dict(id=iid, name=el.get('data-name') or '', title=el.get('data-title') or '', type=el.get('data-type') or '',
                                  closed=st not in (None, 'none'), glass=st == GLASS, poly=poly))
                if st == WALL: axes.append(sample(d))
                elif st == GLASS: glass.append(sample(d))
            elif gid == 'rooms' and re.match(r'wall-', iid) and st == WALL: axes.append(sample(d))
            elif gid == 'rooms' and re.match(r'door-', iid):
                P = sample(d, 1.0)
                if len(P) >= 3:
                    pg = Polygon(P).buffer(0); r_ = pg.minimum_rotated_rectangle; cs = np.array(r_.exterior.coords)[:4]
                    sides = sorted([np.hypot(*(cs[1] - cs[0])), np.hypot(*(cs[2] - cs[1]))])
                    doors.append(dict(id=iid, c=np.array(pg.centroid.coords[0]), L=sides[1], depth=sides[0]))
            elif gid == 'glass' and st == GLASS: glass.append(sample(d))
    return W, H, rooms, axes, glass, doors

def raster(pts_list, W, H):
    img = np.zeros((H, W), bool)
    for P in pts_list:
        q = np.round(P).astype(int); ok = (q[:, 0] >= 0) & (q[:, 1] >= 0) & (q[:, 0] < W) & (q[:, 1] < H); img[q[ok, 1], q[ok, 0]] = True
    return img

def agree(A, B, W, H):
    """доля длины A ближе 3 / 6 px к B"""
    if not A or not B: return dict(m=0, le3=None, le6=None)
    DB = ndimage.distance_transform_edt(~raster(B, W, H)); P = np.vstack(A)
    q = np.round(P).astype(int); q[:, 0] = q[:, 0].clip(0, W - 1); q[:, 1] = q[:, 1].clip(0, H - 1)
    d = DB[q[:, 1], q[:, 0]]
    return dict(m=round(len(P) / 52.49, 1), le3=round(float(np.mean(d <= 3)), 3), le6=round(float(np.mean(d <= 6)), 3)), d, P

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('conv'); ap.add_argument('ref'); ap.add_argument('--skip-ref', action='append', default=[])
    ap.add_argument('--out'); ap.add_argument('--crops'); ap.add_argument('--px-per-m', type=float, default=52.49)
    a = ap.parse_args(); pxm = a.px_per_m
    W, H, Rc, Ac, Gc, Dc = load(a.conv); W2, H2, Rr, Ar, Gr, Dr = load(a.ref)
    Rr = [r for r in Rr if r['id'] not in a.skip_ref]
    out = collections.OrderedDict(conv=a.conv, ref=a.ref, skip_ref=a.skip_ref)
    # 1. помещения
    rows = []; used = set()
    for r in Rr:
        best = (0, None)
        for j, c in enumerate(Rc):
            if not r['poly'].intersects(c['poly']): continue
            iou = r['poly'].intersection(c['poly']).area / r['poly'].union(c['poly']).area
            if iou > best[0]: best = (iou, j)
        iou, j = best; c = Rc[j] if j is not None else None
        if j is not None and iou >= 0.5: used.add(j)
        rows.append(dict(ref=r['id'], name=r['name'], title=r['title'], ref_closed=r['closed'], iou=round(iou, 3),
                         conv=c['id'] if c else None, conv_name=c['name'] if c else None, conv_closed=c['closed'] if c else None,
                         m2=round(r['poly'].area / pxm ** 2, 1)))
    out['помещений'] = dict(эталон=len(Rr), конвертер=len(Rc), iou_08=sum(z['iou'] >= 0.8 for z in rows), iou_05=sum(z['iou'] >= 0.5 for z in rows),
                            номер_совпал=sum(1 for z in rows if z['iou'] >= 0.5 and z['conv_name'] and z['conv_name'] == z['name']),
                            закрыто_совпало=sum(1 for z in rows if z['iou'] >= 0.5 and z['conv_closed'] == z['ref_closed']),
                            лишние_в_конвертере=[dict(id=c['id'], name=c['name'], m2=round(c['poly'].area / pxm ** 2, 1)) for j, c in enumerate(Rc) if j not in used])
    out['по_помещениям'] = rows
    # площадь, покрытая обеими картами одинаково (по помещениям эталона)
    tot = sum(r['poly'].area for r in Rr); out['площадь_эталона_м2'] = round(tot / pxm ** 2, 1)
    # 2–3. оси и стекло
    ax_rc, d1, P1 = agree(Ar, Ac, W, H); ax_cr, d2, P2 = agree(Ac, Ar, W, H)
    out['оси_стен'] = dict(эталон_к_конвертеру=ax_rc, конвертер_к_эталону=ax_cr)
    g1 = agree(Gr, Gc, W, H); g2 = agree(Gc, Gr, W, H)
    out['стекло'] = dict(эталон_к_конвертеру=g1[0] if isinstance(g1, tuple) else g1, конвертер_к_эталону=g2[0] if isinstance(g2, tuple) else g2)
    # места расхождений осей: куски ≥ 0,5 м
    def chunks(d, P, thr=6):
        far = raster([P[d > thr]], W, H); far = ndimage.binary_dilation(far, iterations=3)
        lab, n = ndimage.label(far); res = []
        for i in range(1, n + 1):
            m = lab == i; L = m.sum() / 7 / pxm
            if L >= 0.5:
                cy, cx = ndimage.center_of_mass(m); res.append((round(L, 1), int(cx), int(cy)))
        return sorted(res, reverse=True)
    out['оси_эталона_без_пары'] = chunks(d1, P1)[:15]
    out['оси_конвертера_без_пары'] = chunks(d2, P2)[:15]
    # 4. проёмы
    hit = 0; miss = []
    for d in Dr:
        c = min(Dc, key=lambda z: np.hypot(*(z['c'] - d['c'])), default=None)
        if c is not None and np.hypot(*(c['c'] - d['c'])) <= 15 and abs(c['L'] - d['L']) <= 0.3 * d['L']: hit += 1
        else: miss.append(dict(id=d['id'], x=int(d['c'][0]), y=int(d['c'][1]), L=round(d['L'], 1)))
    out['проёмы'] = dict(эталон=len(Dr), конвертер=len(Dc), совпало=hit, не_нашлось=miss[:20])
    if a.out: json.dump(out, open(a.out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1, default=str)
    s = {k: v for k, v in out.items() if k not in ('по_помещениям',)}
    print(json.dumps(s, ensure_ascii=False, indent=1, default=str))
    print('\nпомещения эталона (IoU):')
    for z in sorted(rows, key=lambda z: z['iou']):
        print(f"  {z['iou']:.2f}  {z['ref']:24s} «{z['name']}» {'закр' if z['ref_closed'] else 'откр'}  ->  {z['conv']} «{z['conv_name']}» {'закр' if z['conv_closed'] else 'откр'}  {z['m2']} м²")

if __name__ == '__main__': main()
