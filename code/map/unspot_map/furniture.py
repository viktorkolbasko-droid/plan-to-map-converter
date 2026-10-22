"""Furniture of the clean plan except workplaces (map/rules/61 §1 'Мебель', map/rules/61 §2).

Extract from the page render WITHOUT text (pdf_source.render(text=False)) warped into the working frame:
the main raster misses the pasted patches (client C 15.05: the meeting table exists only as a rotated patch).

 * tables  = grey fill blobs, rectangles by minAreaRect, round tables by circularity;
 * chairs  = dark blobs split by distance-transform peaks; peaks closer than 0.45 m are ONE chair
            (big armchairs of the patches gave two peaks each before);
 * a chair faces the NEAREST SIDE of its table (perpendicular to it), a round table - its centre;
 * guideline symbols at natural size, 1 px, #CBD2D6; everything clipped to the room minus half a wall.
Thresholds are for grey CAD fills on white; check them on the plan before use."""
import math
import numpy as np
import cv2
from shapely.geometry import Point, Polygon, LineString
from shapely.ops import nearest_points


def blobs(img_bgr, to_work=None, px_per_m=16.8):
    """img_bgr: render in its own pixel frame; to_work: frame.Affine image px -> working frame (None = same).
    Returns dict of lists: tables, chairs, blue, tan (each item has c, box / r in the working frame)."""
    g = img_bgr.mean(2); sat = img_bgr.max(2).astype(int) - img_bgr.min(2).astype(int)
    b, gg, r = [img_bgr[:, :, i].astype(int) for i in range(3)]
    tw = (lambda P: np.atleast_2d(P)) if to_work is None else to_work
    k = 1.0 if to_work is None else to_work.scale()           # work px per image px
    masks = {'gray': (g > 150) & (g < 210) & (sat < 16),
             'blue': (b > r + 30) & (sat > 40) & (g < 230),
             'tan': (r > b + 30) & (r > gg) & (sat > 30) & (g > 120) & (g < 225) & ~((r > 200) & (gg < 90))}
    out = {}
    bm = cv2.morphologyEx((g < 95).astype(np.uint8), cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
    dt = cv2.distanceTransform(bm, cv2.DIST_L2, 5)
    mx = cv2.dilate(dt, np.ones((7, 7), np.uint8))
    img_px_per_m = px_per_m / k
    peaks = np.argwhere((dt == mx) & (dt >= 0.155 * img_px_per_m))   # chair core: half-width >= 0.155 m
    nms = (0.45 * img_px_per_m) ** 2                                  # one chair per 0.45 m
    pk = []
    for y, x in sorted(peaks.tolist(), key=lambda q: -dt[q[0], q[1]]):
        if all((x - a) ** 2 + (y - bb) ** 2 > nms for a, bb in pk):
            pk.append((x, y))
    out['chairs'] = [dict(c=tw([(x + 0.5, y + 0.5)])[0]) for x, y in pk]
    for name, m in masks.items():
        m = cv2.morphologyEx(m.astype(np.uint8), cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
        n, lab, st, _ = cv2.connectedComponentsWithStats(m, connectivity=8)
        items = []
        for i in range(1, n):
            if st[i, 4] < 0.04 * img_px_per_m ** 2:            # < 0.04 m2: noise
                continue
            cc, _ = cv2.findContours((lab == i).astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
            c = max(cc, key=cv2.contourArea)
            (cx, cy), (w, h), a = cv2.minAreaRect(c)
            circ = st[i, 4] / (math.pi * (max(w, h) / 2) ** 2 + 1e-9)
            items.append(dict(c=tw([(cx, cy)])[0], box=tw(cv2.boxPoints(((cx, cy), (w, h), a))),
                              area=st[i, 4] * k * k, w=w * k, h=h * k, circ=circ))
        out['tables' if name == 'gray' else name] = items
    return out


def is_round(t):
    return t['circ'] > 0.62 and abs(t['w'] - t['h']) < 0.22 * max(t['w'], t['h'])


def chair_symbol(c, towards, size):
    """guideline chair (seat + backrest line), backrest away from the table"""
    c = np.asarray(c, float); u = np.asarray(towards, float) - c; L = np.linalg.norm(u)
    u = u / L if L > 1e-6 else np.array([0, 1.0]); n = np.array([-u[1], u[0]]); s = size / 2
    seat = Polygon([tuple(c + u * s * 0.9 + n * s), tuple(c + u * s * 0.9 - n * s),
                    tuple(c - u * s * 0.7 - n * s), tuple(c - u * s * 0.7 + n * s)])
    back = LineString([tuple(c - u * s * 1.05 + n * s * 1.05), tuple(c - u * s * 1.05 - n * s * 1.05)])
    return [seat, back]


def meeting_set(room_poly, B, px_per_m, min_table_m2=0.2, chair_m=0.40, max_chair_dist_m=1.8):
    """tables (rect/round) and chairs of a meeting room, kitchen or lounge; chairs oriented to the table side"""
    P = room_poly.buffer(-1.0); inside = lambda it: P.contains(Point(*it['c']))
    tables = [t for t in B['tables'] if inside(t) and t['area'] >= min_table_m2 * px_per_m ** 2]
    items = []
    tpolys = []
    for t in tables:
        if is_round(t):
            g = Point(*t['c']).buffer(max(t['w'], t['h']) / 2, quad_segs=8); items.append(('round', g))
        else:
            g = Polygon(t['box']); items.append(('table', g))
        tpolys.append(g)
    for ch in B['chairs']:
        if not inside(ch) or not tpolys:
            continue
        p = Point(*ch['c'])
        j = min(range(len(tpolys)), key=lambda k: tpolys[k].distance(p))
        if tpolys[j].distance(p) > max_chair_dist_m * px_per_m:
            continue
        if is_round(tables[j]):
            tc = np.asarray(tables[j]['c'])
        else:
            tc = np.asarray(nearest_points(tpolys[j].exterior, p)[0].coords[0])
        for g in chair_symbol(ch['c'], tc, chair_m * px_per_m):
            items.append(('chair', g))
    return items


def clip_to_room(items, room_poly, half_wall):
    """furniture never enters the wall stroke (map/rules/61 §2.5)"""
    clip = room_poly.buffer(-half_wall)
    out = []
    for kind, g in items:
        g2 = g.intersection(clip)
        if not g2.is_empty:
            out.append((kind, g2))
    return out
