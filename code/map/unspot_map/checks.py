"""Checks of a finished clean plan, from its SVG and the source (map/rules/80 §9.1, §9.4; map/rules/82 §2).

Role (02.10.2026): quick numbers on the wall graph WHILE drawing, in the source frame. They are not the acceptance.
The acceptance and the delivery gate is acceptance_checks.py (map/rules/80 §0, §2): one list Ch-01...Ch-30, one set of thresholds.
THRESHOLDS below are the same values as map/rules/80; if they ever differ, map/rules/80 and acceptance_checks.py win.

Every check returns a number with a threshold; the pass report carries the table (see REPORT_KEYS).
This is what makes quality independent of how long a model thinks: a plan is accepted by numbers,
not by the author's impression. Thresholds are the values v2 reached on client C; tighten, never loosen.

  svg: groups and order, hidden empty underlay, forbidden attributes, literal hex, stroke attribute
  shape: edges shorter than the interior wall, steps (a short edge between two parallel edges)
  walls vs source: share of wall axis on source ink (+-2 px / +-3 px of the source raster),
                   wall length off the source (> 3 px), doubled walls (raw / effective length)
  facade: vertices, edges shorter than 1 canvas px
  rooms: closed rooms without a door, labels outside rooms, two labels in one room
  furniture: furniture paths entering walls
  artifact 3: desk spots = seat spots = JSON places; PNG sizes equal; PNG <= 5 MB
"""
import os
import re
import xml.etree.ElementTree as ET
import numpy as np
import cv2
from shapely.geometry import Polygon, LineString, Point
from shapely.ops import unary_union

NS = '{http://www.w3.org/2000/svg}'
GROUPS = ['underlay', 'rooms', 'glass', 'furniture', 'icons', 'labels']
THRESHOLDS = dict(short_edges=0, steps=0, wall_on_ink_2px=0.95, wall_on_ink_3px=0.98, doubling=1.3,
                  facade_edges_under_1px=0, closed_without_door=0, labels_outside=0, furniture_in_walls=0,
                  forbidden=0, nonhex=0, no_stroke_attr=0)


def parse_d(d):
    """M/L/C/Q/A/H/V/Z -> [(points, closed)]; curves and arcs keep their end points"""
    out, cur = [], []
    toks = re.findall(r'[MLZCQAHVmlzcqahv]|-?\d*\.?\d+(?:e-?\d+)?', d)
    i, cmd = 0, None; npar = {'M': 2, 'L': 2, 'C': 6, 'Q': 4, 'A': 7, 'H': 1, 'V': 1}
    while i < len(toks):
        t = toks[i]
        if t.isalpha():
            cmd = t.upper(); i += 1
            if cmd == 'Z':
                if cur: out.append((cur, True)); cur = []
            elif cmd == 'M' and cur:
                out.append((cur, False)); cur = []
            continue
        k = npar.get(cmd, 2); v = [float(x) for x in toks[i:i + k]]; i += k
        if len(v) < k: break
        if cmd in ('M', 'L'): cur.append((v[0], v[1]))
        elif cmd == 'C': cur.append((v[4], v[5]))
        elif cmd == 'Q': cur.append((v[2], v[3]))
        elif cmd == 'A': cur.append((v[5], v[6]))
        elif cmd == 'H' and cur: cur.append((v[0], cur[-1][1]))
        elif cmd == 'V' and cur: cur.append((cur[-1][0], v[0]))
    if cur: out.append((cur, False))
    return out


def svg_inventory(path):
    root = ET.parse(path).getroot()
    groups = [k for k in root if k.tag == NS + 'g']
    res = dict(order=[g.get('id') for g in groups], size_kb=round(os.path.getsize(path) / 1024, 1))
    bad, nohex, nostroke, pts = [], [], 0, {}
    for g in groups:
        gid = g.get('id'); n = 0
        for el in g.iter():
            if el is g: continue
            tag = el.tag.replace(NS, '')
            for a in ('transform', 'class'):
                if el.get(a) is not None: bad.append((gid, tag, a))
            if tag in ('image', 'use'): bad.append((gid, tag, 'element'))
            for a in ('fill', 'stroke'):
                v = el.get(a)
                if v is not None and v != 'none' and not re.fullmatch(r'#[0-9A-Fa-f]{6}', v): nohex.append((gid, tag, a, v))
            if tag in ('path', 'line', 'polyline', 'polygon', 'rect', 'circle') and el.get('stroke') is None: nostroke += 1
            if tag == 'path': n += sum(len(p) for p, _ in parse_d(el.get('d', '')))
            elif tag == 'line': n += 2
            elif tag in ('polygon', 'polyline'): n += len(el.get('points', '').split())
            elif tag == 'circle': n += 1
        pts[gid] = n
    und = [g for g in groups if g.get('id') == 'underlay']
    res['order_ok'] = res['order'] == GROUPS
    res['underlay_ok'] = bool(und) and len(list(und[0])) == 0 and (
        und[0].get('display') == 'none' or 'display:none' in (und[0].get('style') or '').replace(' ', ''))
    res.update(forbidden=len(bad), nonhex=len(nohex), no_stroke_attr=nostroke, points=sum(pts.values()), points_by_group=pts,
               font_sizes=sorted({el.get('font-size') for el in root.iter(NS + 'text')}))
    return res, root


def rooms_from_svg(root, to_src):
    """[(Polygon in the source frame, stroked?, data-type)] for the paths of the rooms group"""
    out = []
    for g in root.iter(NS + 'g'):
        if g.get('id') != 'rooms': continue
        for el in g:
            iden = el.get('id') or ''
            if el.tag != NS + 'path' or iden.startswith(('door', 'wall')): continue
            for p, _ in parse_d(el.get('d', '')):
                if len(p) >= 3:
                    out.append((Polygon(to_src(np.array(p))), el.get('stroke') not in (None, 'none'), el.get('data-type')))
    return out


def wall_axes(root, to_src, wall='#CBD2D6'):
    """drawn wall axes: outlines of stroked room paths, free wall paths, grey <line> walls"""
    L = []
    for g in root.iter(NS + 'g'):
        if g.get('id') != 'rooms': continue
        for el in g:
            tag = el.tag.replace(NS, ''); iden = el.get('id') or ''
            if tag == 'path' and not iden.startswith('door') and el.get('stroke') not in (None, 'none'):
                for p, closed in parse_d(el.get('d', '')):
                    P = to_src(np.array(p))
                    if closed or iden.startswith('room'): P = np.vstack([P, P[:1]])
                    if len(P) >= 2: L.append(LineString(P))
            if tag == 'line' and el.get('stroke') == wall:
                L.append(LineString(to_src(np.array([[float(el.get('x1')), float(el.get('y1'))], [float(el.get('x2')), float(el.get('y2'))]]))))
    return L


def door_shapes(root, to_src, px_per_canvas):
    """door openings in the source frame: door-* paths, or coloured <line> openings (older plans)"""
    D = []
    for g in root.iter(NS + 'g'):
        if g.get('id') != 'rooms': continue
        for el in g:
            tag = el.tag.replace(NS, ''); iden = el.get('id') or ''
            if tag == 'path' and iden.startswith('door'):
                D += [Polygon(to_src(np.array(p))) for p, _ in parse_d(el.get('d', '')) if len(p) >= 3]
            if tag == 'line' and el.get('stroke') not in (None, 'none', '#CBD2D6'):
                P = to_src(np.array([[float(el.get('x1')), float(el.get('y1'))], [float(el.get('x2')), float(el.get('y2'))]]))
                D.append(LineString(P).buffer(float(el.get('stroke-width', '6')) / 2 * px_per_canvas, cap_style=2))
    return D


def short_edges_and_steps(polys, T_src):
    """edges shorter than the interior wall (T in source px) and steps (short edge between parallel edges)"""
    se = st = 0
    for P, stroked, _ in polys:
        if not stroked: continue
        c = np.array(P.exterior.coords)[:-1]; n = len(c)
        if n < 4: continue
        e = [c[(i + 1) % n] - c[i] for i in range(n)]; Ls = [np.hypot(*v) for v in e]
        for i in range(n):
            if Ls[i] < T_src:
                se += 1
                a, b = e[(i - 1) % n], e[(i + 1) % n]
                if Ls[(i - 1) % n] > 1e-6 and Ls[(i + 1) % n] > 1e-6 and (a @ b) / (np.hypot(*a) * np.hypot(*b)) > 0.995:
                    st += 1
    return se, st


class Ink:
    """distance to source ink (dark CAD lines, red client marks excluded) in source px"""
    def __init__(self, raster_bgr, src_to_raster, thr=225, sat_max=60):
        g = raster_bgr.mean(2); sat = raster_bgr.max(2).astype(int) - raster_bgr.min(2).astype(int)
        dark = ((g < thr) & (sat < sat_max)).astype(np.uint8)
        self.dt = cv2.distanceTransform(1 - dark, cv2.DIST_L2, 5); self.A = src_to_raster; self.k = 1.0 / src_to_raster.scale()

    def dist(self, P):
        Q = self.A(P); h, w = self.dt.shape
        xi = np.clip(np.round(Q[:, 0]).astype(int), 0, w - 1); yi = np.clip(np.round(Q[:, 1]).astype(int), 0, h - 1)
        return self.dt[yi, xi] * self.k


def _sample(lines, step):
    pts = []
    for g in lines:
        n = max(2, int(g.length / step) + 1)
        pts += [g.interpolate(t).coords[0] for t in np.linspace(0, g.length, n)]
    return np.array(pts)


def walls_vs_source(axes, doors, facade, ink, px_per_m, facade_band=4.0):
    """share of the (deduplicated) interior wall axis on source ink, wall length off the source, doubling"""
    U = unary_union(axes)
    parts = [U] if U.geom_type == 'LineString' else [g for g in U.geoms if g.geom_type == 'LineString']
    P = _sample(parts, 0.5)
    Dall = unary_union(doors) if doors else None
    keep = np.array([facade.distance(Point(*p)) > facade_band and (Dall is None or not Dall.contains(Point(*p))) for p in P])
    d = ink.dist(P[keep])
    inner = Polygon(facade.coords).buffer(-facade_band)
    I = U.intersection(inner)
    eff = I.buffer(1.5, cap_style=2).area / 3.0
    return dict(wall_on_ink_2px=round(float((d <= 2.0).mean()), 3), wall_on_ink_3px=round(float((d <= 3.0).mean()), 3),
                off_source_m=round(float((d > 3.0).sum()) * 0.5 / px_per_m, 1),
                doubling=round(float(I.length / eff), 3) if eff > 0 else None)


def facade_stats(root, to_src, canvas_px_per_src):
    """vertices of the facade glass path and its edges shorter than 1 canvas px (micro-zigzag)"""
    glass = [el for g in root.iter(NS + 'g') if g.get('id') == 'glass' for el in g if el.tag == NS + 'path']
    ring = max(glass, key=lambda el: len(el.get('d', '')))
    p = np.array(parse_d(ring.get('d', ''))[0][0]); seg = np.hypot(*np.diff(p, axis=0).T)
    return dict(facade_vertices=len(p), facade_edges_under_1px=int((seg < 1.0).sum()))


def labels_in_rooms(polys, labels):
    """client labels: outside any room / two labels in one room"""
    rooms = [P for P, _, _ in polys]; where = []
    for t, x, y in labels:
        c = [i for i, P in enumerate(rooms) if P.contains(Point(x, y))]
        where.append(min(c, key=lambda i: rooms[i].area) if c else None)
    from collections import Counter
    C = Counter(w for w in where if w is not None)
    return dict(labels=len(labels), labels_outside=sum(1 for w in where if w is None),
                labels_sharing_room=sum(v for v in C.values() if v > 1))


def closed_without_door(polys, doors, min_area_src=0.0, skip=('lift',)):
    D = [d.buffer(0.8) for d in doors]
    return sum(1 for P, stroked, t in polys if stroked and t not in skip and P.area >= min_area_src
               and not any(P.exterior.intersects(d) for d in D))


def furniture_in_walls(root, to_src, polys, half_wall_src):
    walls = unary_union([P.exterior for P, s, _ in polys if s]).buffer(half_wall_src)
    bad = tot = 0
    for g in root.iter(NS + 'g'):
        if g.get('id') != 'furniture': continue
        for el in g:
            for p, _ in parse_d(el.get('d', '')):
                if len(p) < 2: continue
                tot += 1; bad += int(LineString(to_src(np.array(p))).intersection(walls).length > 0.3)
    return dict(furniture_paths=tot, furniture_in_walls=bad)


def png_checks(clean_png, placement_png, n_places, count_marks):
    from PIL import Image
    a, b = Image.open(clean_png).size, Image.open(placement_png).size
    desks, seats = count_marks(placement_png)
    return dict(png_size_equal=a == b, png_mb=round(os.path.getsize(placement_png) / 1e6, 2),
                desk_spots=desks, seat_spots=seats, places=n_places, marks_ok=(desks == seats == n_places))


def verdict(row):
    """compare a metrics row with THRESHOLDS; returns the list of failures"""
    f = []
    for k, t in THRESHOLDS.items():
        if k not in row or row[k] is None: continue
        v = row[k]
        ok = v >= t if k.startswith('wall_on_ink') else (v <= t)
        if not ok: f.append((k, v, t))
    return f
