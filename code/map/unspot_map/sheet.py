"""Inputs of the acceptance from the vector sheet (map/rules/80 Ch-36, Ch-37, Ch-38; code v008, package 2): doors, glass and seat numbers
of the sheet, found apart from the drawing of the map - the same idea as unspot_map.chairs for Ch-31 (G1-1): a list built independently of
the map makes a missing door, a glass partition drawn as a grey wall or a desk away from its number visible.

* doors - by geometry, not by layer name (owner row 182/R56: the layer name is not the purpose): a quarter arc of a leaf 0.5-1.3 m with a
  sweep of 40-120 deg (E5: a door opened at 52 deg is a door), its centre is the hinge; three or more arcs around one centre are a round
  table, not doors (E5). A class filter (--layer / --stroke) only narrows the search when the author knows the door class.
  v012 (KM-8; P3-4, OCh-B2): an arc drawn as a polyline (a flattened sheet: runs of short lines turning one way) is an arc too; pieces of one
  arc (same centre within 0.03 m, radius within 3 %, ends within 0.05 m, together no more than 120 deg) are one door: a piece counts from
  15 deg (--piece-min), the door - from 40 deg after merging (--min-sweep), as before. A sheet printed to PDF (Ghostscript: every segment is
  a path of its own) - segments joined end to end into chains (chain_arcs) and fitted the same way.
  Leaves without an arc (E16): narrow rectangles 0.5-1.05 x <= 0.09 m of the door class, given by --leaf-layer / --leaf-stroke.
* glass - the glass class of the sheet chosen by the author from the class table (map/rules/11 §1): stroke colour and width, fill colour or
  layer; the detector does not guess it. Filled thin rectangles give their centre line.
* numbers - seat numbers of the text layer: 1-3 digits with an optional suffix '-1' (T3-1: '201-1'); four glued digits are two numbers.
  v012 (KM-13): the number format is a setting of the client (--number-re, --no-glued4), not a rule; no number found - a loud line in 'how'
  and on stderr, and acceptance Ch-37 is look, not pass.

    python3 -m unspot_map.sheet doors   --pdf sheet.pdf --intake intake.json --px-per-m 57.87 [--layer 'PDF _Двери'] --out doors.json
    python3 -m unspot_map.sheet glass   --pdf sheet.pdf --intake intake.json --px-per-m 57.87 --layer 'PDF _Остекление' --out glass.json
    python3 -m unspot_map.sheet numbers --pdf sheet.pdf --intake intake.json --px-per-m 57.87 --out numbers.json

Output: px of work.png ({"frame": "source", "px_per_m", "how", "doors" | "segments" | "numbers"}) - the inputs of acceptance_checks.py
--sheet-doors, --sheet-glass, --sheet-numbers. Thresholds are in metres (px of work.png through --px-per-m), not in pt of one sheet."""
import argparse, json, math, re
from collections import Counter
import numpy as np


def _colour(v):
    if v in (None, ''): return None
    t = tuple(float(x) for x in str(v).split(','))
    return t * 3 if len(t) == 1 else t


def _near(col, ref, tol=0.02):
    return col is not None and ref is not None and len(col) == len(ref) and max(abs(u - v) for u, v in zip(col, ref)) <= tol


def _open(pdf, page, intake):
    import pymupdf
    it = json.load(open(intake, encoding='utf-8')); r = it['render']
    doc = pymupdf.open(pdf); pg = doc[(page or it.get('chosen_page', 1)) - 1]; a, b, c, d, e, f = r['to_pixels']
    T = lambda p: (a * p.x + c * p.y + e, b * p.x + d * p.y + f)
    return pg, T, it


def _select(pg, layer=None, stroke=None, width=None, fill=None, wtol=0.02):
    for x in pg.get_drawings():
        if layer is not None and (x.get('layer') or '') != layer: continue
        if stroke is not None and not (_near(x.get('color'), stroke) and (width is None or abs((x.get('width') or 0) - width) <= wtol)): continue
        if fill is not None and not _near(x.get('fill'), fill): continue
        yield x


def _bez(p0, p1, p2, p3, n=12):
    t = np.linspace(0, 1, n)[:, None]
    return (1 - t) ** 3 * p0 + 3 * (1 - t) ** 2 * t * p1 + 3 * (1 - t) * t ** 2 * p2 + t ** 3 * p3


def _circle(P):
    """least-squares circle through points -> (cx, cy, r, rms)"""
    x, y = P[:, 0], P[:, 1]; A = np.c_[2 * x, 2 * y, np.ones(len(x))]; bb = x * x + y * y
    (cx, cy, c0), *_ = np.linalg.lstsq(A, bb, rcond=None); r = math.sqrt(max(c0 + cx * cx + cy * cy, 0.0))
    return cx, cy, r, float(np.sqrt(np.mean((np.hypot(x - cx, y - cy) - r) ** 2)))


def arcs(pg, T, px_per_m, rng=(0.5, 1.3), sweep=(40.0, 120.0), min_lines=4, max_turn=25.0, **cls):
    """chains of Bezier curves that are circular arcs: [(hinge, end a, end b, r m, sweep deg)] in px of work.png;
    v012 (KM-8): runs of >= min_lines short lines turning one way by < max_turn deg per step (an arc flattened to a polyline) - the same fit"""
    out = []
    for x in _select(pg, **cls):
        chain = []; lines = []
        items = x['items'] + [('end',)]
        for it in items:
            if it[0] == 'l':
                p0, p1 = np.array(T(it[1]), float), np.array(T(it[2]), float)
                if lines and (np.hypot(*(lines[-1] - p0)) > 0.5 or not _turn_ok(lines, p1, max_turn)):
                    _flush_lines(lines, out, px_per_m, rng, sweep, min_lines); lines = []
                if not lines: lines = [p0]
                lines.append(p1)
            elif lines: _flush_lines(lines, out, px_per_m, rng, sweep, min_lines); lines = []
            if it[0] == 'c':
                q = [np.array(T(p), float) for p in it[1:5]]
                if chain and np.hypot(*(chain[-1][-1] - q[0])) > 0.5:
                    _flush(chain, out, px_per_m, rng, sweep); chain = []
                chain.append(_bez(*q))
            else:
                if chain: _flush(chain, out, px_per_m, rng, sweep); chain = []
    return out


def _turn_ok(P, p, max_turn):
    """the next point keeps the run an arc: turn < max_turn deg and of the same sign as the turns before"""
    if len(P) < 2: return True
    a, b = P[-2], P[-1]; u, v = b - a, p - b
    if np.hypot(*u) < 1e-9 or np.hypot(*v) < 1e-9: return False
    t = math.degrees(math.atan2(u[0] * v[1] - u[1] * v[0], u @ v))
    if abs(t) >= max_turn or abs(t) < 0.2: return False
    if len(P) >= 3:
        w = P[-2] - P[-3]; t0 = math.atan2(w[0] * u[1] - w[1] * u[0], w @ u)
        if t0 * t < 0: return False
    return True


def _flush_lines(P, out, px_per_m, rng, sweep, min_lines):
    if len(P) - 1 >= min_lines: _flush([np.asarray(P, float)], out, px_per_m, rng, sweep)


def chain_arcs(pg, T, px_per_m, rng=(0.5, 1.3), sweep=(15.0, 120.0), min_lines=4, max_turn=25.0, min_len_m=0.003, tol=0.6, **cls):
    """v012 (КМ-8): дуга листа, распечатанного в PDF (Ghostscript и т. п.), — сотни отдельных путей по одному отрезку: отрезки, которые
    стыкуются концами (узел — ровно два конца, в tol px), собираются в цепочки, цепочка режется по знаку и величине поворота и
    подбирается окружностью тем же способом, что кривые и ломаные одного пути"""
    import collections
    segs = {}
    for x in _select(pg, **cls):
        for it in x['items']:
            if it[0] != 'l': continue
            p, q = T(it[1]), T(it[2])
            if math.dist(p, q) < min_len_m * px_per_m: continue
            k = tuple(sorted(((round(p[0] / tol), round(p[1] / tol)), (round(q[0] / tol), round(q[1] / tol)))))
            if k[0] != k[1]: segs.setdefault(k, (np.array(p, float), np.array(q, float)))   # дубль отрезка — один
    S = list(segs.items()); nb = collections.defaultdict(list)
    for i, (k, pq) in enumerate(S): nb[k[0]].append(i); nb[k[1]].append(i)
    used = [False] * len(S); out = []
    def other(i, node):
        k = S[i][0]; return k[1] if k[0] == node else k[0]
    def pt(i, node):
        k, (p, q) = S[i]; return p if k[0] == node else q
    for i in range(len(S)):
        if used[i]: continue
        used[i] = True; k = S[i][0]; ends = [k[0], k[1]]; pts = [pt(i, k[0]), pt(i, k[1])]
        for side in (1, 0):
            node = ends[side]
            while len(nb[node]) == 2:
                cand = [c for c in nb[node] if not used[c]]
                if not cand: break
                j = cand[0]; used[j] = True; node = other(j, node); v = pt(j, node)
                if side == 1: pts.append(v)
                else: pts.insert(0, v)
        if len(pts) - 1 < min_lines: continue
        run = [pts[0], pts[1]]                                                 # цепочка -> куски одного знака поворота
        for v in pts[2:]:
            if _turn_ok(run, v, max_turn): run.append(v)
            else:
                _flush_lines(run, out, px_per_m, rng, sweep, min_lines); run = [run[-1], v]
        _flush_lines(run, out, px_per_m, rng, sweep, min_lines)
    return out


def merge_pieces(A, px_per_m, c_m=0.03, r_tol=0.03, end_m=0.05, max_sweep=120.0):
    """pieces of one arc (same centre, same radius, touching ends) -> one arc; the sweep adds up"""
    A = list(A); used = [False] * len(A); out = []
    for i in range(len(A)):
        if used[i]: continue
        h, a, b, r, s = A[i]; used[i] = True; grow = True
        while grow:
            grow = False
            for j in range(len(A)):
                if used[j]: continue
                h2, a2, b2, r2, s2 = A[j]
                if math.dist(h, h2) > c_m * px_per_m or abs(r2 - r) > r_tol * r or s + s2 > max_sweep + 5: continue   # две дуги у одной петли (маятниковая дверь) — не одна
                for e1, e2, na, nb in ((b, a2, a, b2), (b, b2, a, a2), (a, a2, b, b2), (a, b2, b, a2)):
                    if math.dist(e1, e2) <= end_m * px_per_m:
                        a, b = na, nb; s = s + s2; used[j] = True; grow = True; break
        out.append((h, a, b, r, s))
    return out


def _flush(chain, out, px_per_m, rng, sweep):
    P = np.concatenate(chain)
    if len(P) < 3: return None
    cx, cy, r, rms = _circle(P); rm = r / px_per_m
    if not (rng[0] <= rm <= rng[1]) or rms > 0.04 * r: return None
    a0, a1 = P[0], P[-1]; u, v = a0 - (cx, cy), a1 - (cx, cy)
    ang = [math.degrees(math.atan2(q[1] - cy, q[0] - cx)) for q in P]; sw = abs(float(np.sum(np.diff(np.unwrap(np.radians(ang))))))
    sw = math.degrees(sw)
    if not (sweep[0] <= sw <= sweep[1]): return None
    out.append(((cx, cy), tuple(a0), tuple(a1), rm, sw))
    return None


def _ink(work):
    from PIL import Image
    g = np.asarray(Image.open(work).convert('L')); return g


def leaf(g, h, e, px_per_m, need=0.75, thr=235, win_m=0.04):
    """the leaf of a swing door: any non-white line of the sheet along the straight line hinge -> arc end on >= need of its length,
    within win_m of the line (a leaf is a thin light-grey rectangle: its edge is off the hinge-end line by its thickness). A rounded corner
    of a glass room, a rounded counter or a curved wall has no line from its centre: not a door"""
    H, Wd = g.shape; t = np.linspace(0.1, 0.9, 21); P = np.asarray(h, float)[None] + t[:, None] * (np.asarray(e, float) - np.asarray(h, float))[None]
    k = max(1, int(round(win_m * px_per_m))); ok = 0
    for x, y in P:
        x0, y0 = int(round(x)), int(round(y))
        if k <= x0 < Wd - k and k <= y0 < H - k and g[y0 - k:y0 + k + 1, x0 - k:x0 + k + 1].min() < thr: ok += 1
    return ok >= need * len(P)


def doors(pdf, intake, px_per_m, page=None, layer=None, stroke=None, width=None, leaf_layer=None, leaf_stroke=None, work=None, min_sweep=40.0, piece_min=15.0):
    pg, T, it = _open(pdf, page, intake)
    cls = {k: v for k, v in (('layer', layer), ('stroke', stroke), ('width', width)) if v is not None}
    A0 = arcs(pg, T, px_per_m, sweep=(min(piece_min, min_sweep), 120.0), **cls)   # куски дуги — от piece_min, дверь — от min_sweep после склейки
    A0 += chain_arcs(pg, T, px_per_m, sweep=(min(piece_min, min_sweep), 120.0), **cls)   # дуги из отдельных путей-отрезков (распечатанный лист)
    A = [z for z in merge_pieces(A0, px_per_m) if min_sweep <= z[4] <= 120.0]     # v012 (KM-8): pieces of one arc - one door
    import os
    work = work or os.path.join(os.path.dirname(os.path.abspath(intake)), 'work.png'); g = _ink(work) if os.path.exists(work) else None
    C = np.array([h for h, a, b, r, s in A], float).reshape(-1, 2)
    keep = []; noleaf = 0
    for i, (h, a, b, r, s) in enumerate(A):                               # round table: 3+ arcs around one centre (E5)
        if len(C) and int((np.hypot(*(C - h).T) <= 0.05 * px_per_m).sum()) >= 3: continue
        if g is not None and not (leaf(g, h, a, px_per_m) or leaf(g, h, b, px_per_m)): noleaf += 1; continue   # no leaf - not a door
        if any(math.dist(h, k['hinge']) <= 0.03 * px_per_m and min(math.dist(a, k['a']) + math.dist(b, k['b']), math.dist(a, k['b']) + math.dist(b, k['a'])) <= 0.1 * px_per_m
               for k in keep): continue   # duplicate (v012: either direction - a path and its chain of segments are one arc)
        keep.append(dict(hinge=[round(h[0], 1), round(h[1], 1)], a=[round(a[0], 1), round(a[1], 1)], b=[round(b[0], 1), round(b[1], 1)], kind='arc',
                         r_m=round(r, 3), sweep=round(s, 1)))
    if leaf_layer or leaf_stroke:                                          # leaves without an arc (E16): thin rectangles of the door class
        for x in _select(pg, **{k: v for k, v in (('layer', leaf_layer), ('stroke', leaf_stroke)) if v is not None}):
            if any(i[0] == 'c' for i in x['items']): continue
            pts = np.array([T(p) for i in x['items'] for p in (i[1:] if i[0] in ('l',) else ([i[1].tl, i[1].tr, i[1].br, i[1].bl] if i[0] == 're' else [i[1].ul, i[1].ur, i[1].lr, i[1].ll] if i[0] == 'qu' else []))], float)
            if len(pts) < 4: continue
            import cv2
            (cx, cy), (w, h), ang = cv2.minAreaRect(pts.astype(np.float32)); L, Wd = max(w, h) / px_per_m, min(w, h) / px_per_m
            if not (0.5 <= L <= 1.05 and Wd <= 0.09): continue
            u = np.array([math.cos(math.radians(ang)), math.sin(math.radians(ang))]) if w >= h else np.array([-math.sin(math.radians(ang)), math.cos(math.radians(ang))])
            p0, p1 = np.array([cx, cy]) - u * max(w, h) / 2, np.array([cx, cy]) + u * max(w, h) / 2
            if any(math.dist(p0, k['hinge']) < 0.6 * px_per_m or math.dist(p1, k['hinge']) < 0.6 * px_per_m for k in keep if k['kind'] == 'arc'): continue
            keep.append(dict(hinge=[round(float(p0[0]), 1), round(float(p0[1]), 1)], a=[round(float(p1[0]), 1), round(float(p1[1]), 1)], b=None, kind='leaf', r_m=round(L, 3)))
    how = f'дуги створок 0,5–1,3 м (кривые и ломаные, куски одной дуги — одна дверь: {len(A0)} -> {len(A)}), раствор {min_sweep:g}–120°, полотно от петли к концу дуги' + (f' (без полотна отброшено {noleaf})' if g is not None else ' — НЕ проверено: нет work.png') + \
          (f'; класс {cls}' if cls else '; все классы') + (f'; полотна без дуги — {leaf_layer or leaf_stroke}' if leaf_layer or leaf_stroke else '')
    return dict(frame='source', px_per_m=px_per_m, how=how, doors=keep)


def glass(pdf, intake, px_per_m, page=None, layer=None, stroke=None, width=None, fill=None, min_m=0.1):
    pg, T, it = _open(pdf, page, intake); seg = []
    cls = {k: v for k, v in (('layer', layer), ('stroke', stroke), ('width', width), ('fill', fill)) if v is not None}
    if not cls: raise SystemExit('glass: class of the sheet is required (--layer / --stroke / --fill): the detector does not guess it')
    for x in _select(pg, **cls):
        for i in x['items']:
            if i[0] == 'l': seg.append([T(i[1]), T(i[2])])
            elif i[0] == 'c': seg += [[tuple(p), tuple(q)] for p, q in zip(_bez(*[np.array(T(p), float) for p in i[1:5]], n=6)[:-1], _bez(*[np.array(T(p), float) for p in i[1:5]], n=6)[1:])]
            elif i[0] in ('re', 'qu'):
                r = i[1]; P = [T(r.tl), T(r.tr), T(r.br), T(r.bl)] if i[0] == 're' else [T(r.ul), T(r.ur), T(r.lr), T(r.ll)]
                e = [(P[k], P[(k + 1) % 4]) for k in range(4)]; e.sort(key=lambda z: -math.dist(*z))
                if math.dist(*e[2]) <= 0.15 * px_per_m:                      # filled thin rectangle -> centre line
                    a0, a1 = e[0]; b0, b1 = (e[1] if math.dist(e[1][0], a0) < math.dist(e[1][1], a0) else e[1][::-1])
                    seg.append([((a0[0] + b0[0]) / 2, (a0[1] + b0[1]) / 2), ((a1[0] + b1[0]) / 2, (a1[1] + b1[1]) / 2)])
                else: seg += [list(z) for z in e]
    seg = [[[round(p[0], 1), round(p[1], 1)], [round(q[0], 1), round(q[1], 1)]] for p, q in seg if math.dist(p, q) >= 0.02 * px_per_m]
    return dict(frame='source', px_per_m=px_per_m, how=f'класс стекла листа {cls}', segments=seg)


NUMBER_RE = r'\d{1,3}(?:-\d{1,2})?'


def numbers(pdf, intake, px_per_m, page=None, number_re=NUMBER_RE, glued4=True):
    """v012 (KM-13): number_re - the format of a seat number of this client (a setting, default: 1-3 digits with '-N'); glued4 - four glued
    digits are two numbers (client C '1516'), a setting too; no number found - loud"""
    import sys
    pg, T, it = _open(pdf, page, intake); out = []; R = re.compile(number_re)
    for x0, y0, x1, y1, t, *_ in pg.get_text('words'):
        t = t.strip()
        if R.fullmatch(t): out.append(dict(n=t, x=round(T(_P((x0 + x1) / 2, (y0 + y1) / 2))[0], 1), y=round(T(_P((x0 + x1) / 2, (y0 + y1) / 2))[1], 1)))
        elif glued4 and re.fullmatch(r'\d{4}', t):                         # two glued numbers (client C: '1516')
            for n_, dx in ((t[:2], -(x1 - x0) / 4), (t[2:], (x1 - x0) / 4)):
                q = T(_P((x0 + x1) / 2 + dx, (y0 + y1) / 2)); out.append(dict(n=n_, x=round(q[0], 1), y=round(q[1], 1)))
    how = f'текстовый слой листа: формат номера {number_re!r} (настройка клиента)' + ('; четыре цифры подряд — два номера' if glued4 else '')
    if not out:
        how += ' — НИ ОДНОГО НОМЕРА: формат номера листа другой (настройка --number-re) или номеров нет; Ч-37 — look'
        print('sheet numbers: ни одного номера по формату ' + repr(number_re) + ' — проверить формат номера листа (--number-re)', file=sys.stderr)
    return dict(frame='source', px_per_m=px_per_m, how=how, number_re=number_re, numbers=out)


class _P:
    def __init__(s, x, y): s.x, s.y = x, y


def main():
    ap = argparse.ArgumentParser(description='doors, glass, seat numbers of the vector sheet -> JSON for acceptance_checks.py --sheet-*')
    ap.add_argument('what', choices=('doors', 'glass', 'numbers')); ap.add_argument('--pdf', required=True); ap.add_argument('--intake', required=True)
    ap.add_argument('--page', type=int); ap.add_argument('--px-per-m', type=float, required=True, help='px of work.png per metre')
    ap.add_argument('--layer'); ap.add_argument('--stroke'); ap.add_argument('--width', type=float); ap.add_argument('--fill')
    ap.add_argument('--leaf-layer'); ap.add_argument('--leaf-stroke'); ap.add_argument('--work', help='work.png of the intake (default: next to intake.json)'); ap.add_argument('--out', required=True)
    ap.add_argument('--min-sweep', type=float, default=40.0, help='v012: smallest sweep of a door arc after merging pieces, deg')
    ap.add_argument('--piece-min', type=float, default=15.0, help='v012: smallest sweep of a piece of an arc (flattened sheets), deg')
    ap.add_argument('--number-re', default=NUMBER_RE, help='v012: format of one seat number of this client (regex, whole word)')
    ap.add_argument('--no-glued4', action='store_true', help='v012: four glued digits are one number, not two')
    a = ap.parse_args()
    if a.what == 'doors': R = doors(a.pdf, a.intake, a.px_per_m, a.page, a.layer, _colour(a.stroke), a.width, a.leaf_layer, _colour(a.leaf_stroke), a.work, a.min_sweep, a.piece_min); n = len(R['doors'])
    elif a.what == 'glass': R = glass(a.pdf, a.intake, a.px_per_m, a.page, a.layer, _colour(a.stroke), a.width, _colour(a.fill)); n = len(R['segments'])
    else: R = numbers(a.pdf, a.intake, a.px_per_m, a.page, a.number_re, not a.no_glued4); n = len(R['numbers'])
    json.dump(R, open(a.out, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    print(json.dumps(dict(what=a.what, n=n, how=R['how']), ensure_ascii=False))


if __name__ == '__main__':
    main()
