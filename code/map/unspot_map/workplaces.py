"""Artifact 3 places (map/rules/83; map/rules/82 §0; map/rules/61 §3, map/rules/70 §2.10) and the draft 25 / 50 / 100 (map/rules/83 §6).

One seat = one desk module; the seat mark is where the person sits (at the chair); desks never overlap and
never enter walls; the colour search finds exactly as many desk spots and seat spots as JSON places.

What made v2 exact where v1 was not (v1: 30 desk spots for 31 seats, 58 for 63; marks on the numbers):
 * desks from the page render at 4x the page, WITHOUT text: the thin divider lines between modules survive,
   so most modules are separate components (on the main 789 px raster whole blocks merged);
 * a component with >1 seat number, or larger than a module, is split by a GRID of the median module of the
   floor; the grid orientation is chosen so that each number->chair direction runs across the module
   (a chair sits at a long side), seats are assigned to the nearest free cell;
 * the seat mark = the nearest chair outside the desk within 1.2 m of the number; no chair -> the long side
   of the module nearest to the number;
 * desks pushed out of walls (map/rules/61 §3.2), overlapping pairs clipped along the bisector.
Only the client's numbered seats are placed; client markup such as 'these desks are not added to the map'
removes seats (read it with pdf_source.inventory).
v007 (owner 05.10.2026, ref/core/10 row 181; map/rules/82 §0): the seat NUMBER from the places JSON is written in white at the desk
centre on top of the desk fill; the colour search counts desk spots on the fill mask before the numbers (holes filled, ОВ11, Е13).
v008 (package 2; OV1, OV10, OV20 b, OV21, N11): numbers -> chairs one to one over the floor (Hungarian method, assign_chairs), a chair
behind another desk is not a candidate (behind_other_desk); keep_off_walls moves a desk only along its short side, away from the wall.
v010 (пакет кода 4; К-8, №90, map/rules/61 §2.4): a pedestal (тумба, приставка) at the short end of a desk is not part of the seat: one fill
for the desk and the pedestal - the desk is the floor module at the number's end (split_end_piece); a separate fill component at the end -
end_pieces; both go to the place record as 'pedestal' for the furniture layer, never into the desk.
v013 (К13.1; строка 391, №6; map/rules/83 §6, §1): artefact 3 is the draft 25 / 50 / 100 — render_draft (grey original 25 %, white outside the
plan ring + 10 px; clean plan 50 % on non-empty pixels; places 100 %: all desks first, then numbers and seat dots). The seat dot is 0,26 m at the
picture scale (not less than 6 px), the number size is 13–34 px of a 54 px/m canvas rescaled to the picture. render_variant_c (multiply 60 %)
is removed (map/rules/82 §0: one scheme). CLI: python3 -m unspot_map.workplaces draft --help.
v013 (К13.3; map/rules/83 §5, строка 391): every place record gets room (the map room of the desk centre, rooms of the SVG) and gaze_deg
(direction from the chair to the desk, 0 — right, 90 — down; N 90, E 180, S 270, W 0) — finish_records, in every method (records: fill+numbers,
lines, raster; places_plan.build: plan; render_draft and the draft CLI after resolve_overlaps). CLI: python3 -m unspot_map.workplaces fields --help."""
import math
import numpy as np
import cv2
from scipy import ndimage
from shapely.geometry import Point, Polygon, LineString
from shapely.ops import unary_union
from shapely import affinity
from PIL import Image, ImageDraw


def desk_components(render_notext, lo=150, hi=215, sat_max=18, conn=4):
    g = render_notext.mean(2); sat = render_notext.max(2).astype(int) - render_notext.min(2).astype(int)
    m = cv2.morphologyEx(((g > lo) & (g < hi) & (sat < sat_max)).astype(np.uint8), cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    n, lab, st, _ = cv2.connectedComponentsWithStats(m, connectivity=conn)
    return lab


def _rect(lab, l):
    cc, _ = cv2.findContours((lab == l).astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    return cv2.minAreaRect(max(cc, key=cv2.contourArea))


def behind_other_desk(lab, q, c, own, step=1.0):
    """OV21 (v008): the segment number -> chair crosses ANOTHER desk component of the render: the chair belongs to the row opposite"""
    d = np.hypot(*(np.asarray(c, float) - np.asarray(q, float))); n = max(2, int(d / step))
    for t in np.linspace(0.0, 1.0, n)[1:-1]:
        x, y = np.asarray(q, float) + t * (np.asarray(c, float) - np.asarray(q, float))
        v = lab[int(np.clip(round(y), 0, lab.shape[0] - 1)), int(np.clip(round(x), 0, lab.shape[1] - 1))]
        if v and v != own: return True
    return False


def assign_chairs(seat_pts, seat_lab, chairs, lab, reach_px, chair_lab=None):
    """OV1, OV10, N11 (v008): numbers -> chairs one to one over the whole floor (Hungarian method on distance), not 'nearest chair' per
    number: a row whose numbers are shifted by half a desk gets its chairs in order along the row, no chair goes to two numbers.
    A chair on its own desk component or behind another desk (OV21) is not a candidate. -> {index of seat: index of chair}"""
    from scipy.optimize import linear_sum_assignment
    if not len(seat_pts) or not len(chairs): return {}
    S = np.asarray(seat_pts, float); C = np.asarray(chairs, float); D = np.hypot(*(S[:, None, :] - C[None, :, :]).transpose(2, 0, 1))
    BIG = 1e9; cost = np.where(D < reach_px, D, BIG)
    for i, j in zip(*np.nonzero(cost < BIG)):
        cl = chair_lab[j] if chair_lab is not None else 0
        if (cl and cl == seat_lab[i]) or behind_other_desk(lab, S[i], C[j], seat_lab[i]): cost[i, j] = BIG
    r, c = linear_sum_assignment(cost)
    return {int(i): int(j) for i, j in zip(r, c) if cost[i, j] < BIG}


PED_M = (0.25, 0.65)        # v010 (К-8, №90): тумба или приставка у торца стола — длина вдоль стола, м
PED_DEPTH_TOL_M = 0.15      # глубина тумбы — как глубина стола ± 0,15 м


def _box(c, u, L, n, S):
    """прямоугольник: центр c, ось u длиной L, поперёк n шириной S -> 4 вершины"""
    return np.array([c + u * L / 2 + n * S / 2, c - u * L / 2 + n * S / 2, c - u * L / 2 - n * S / 2, c + u * L / 2 - n * S / 2])


def split_end_piece(rect, q, Lm_px, Sm_px, ppm):
    """v010 (К-8; №90, map/rules/61 §2.4): стол и тумба у торца одной заливкой (контура между ними на листе нет) — компонента длиннее модуля
    этажа на PED_M (0,25–0,65 м) при глубине стола: стол — модуль Lm у торца со стороны номера (номер — на столе, не на тумбе), остаток — тумба,
    отдельный предмет мебели. Стол сверяется по размеру с другими столами этажа (владелец: «стол распознаётся отдельно и проверяется по
    размерам с другими столами»). -> (стол, тумба) — 4 вершины в px рендера, или None, если это не стол с тумбой"""
    (cx, cy), (w, h), ang = rect; c0 = np.array([cx, cy]); b = cv2.boxPoints(rect)
    e1, e2 = b[1] - b[0], b[2] - b[1]; L1, L2 = np.linalg.norm(e1), np.linalg.norm(e2)
    (u, L, S) = (e1 / L1, L1, L2) if L1 >= L2 else (e2 / L2, L2, L1); n = np.array([-u[1], u[0]])
    extra = (L - Lm_px) / ppm
    if not (PED_M[0] <= extra <= PED_M[1]) or abs(S - Sm_px) / ppm > PED_DEPTH_TOL_M: return None
    s = float((np.asarray(q, float) - c0) @ u); sg = -1.0 if s < 0 else 1.0    # номер — ближе к торцу стола
    cd = c0 + u * sg * (L - Lm_px) / 2; cp = c0 - u * sg * Lm_px / 2
    return _box(cd, u, Lm_px, n, S), _box(cp, u, L - Lm_px, n, S)


def end_pieces(lab, desk_px, own_labels, ppm, Sm_px, gap_m=0.10, ang_deg=10.0, objs=None):
    """v010 (К-8; №90): тумба отдельной компонентой заливки столов у торца стола (между ними — контур листа, как у клиент Б, 40 этаж):
    компонента без номера места, длина вдоль стола PED_M, глубина — как у стола ± 0,15 м, ось — по оси стола ± ang_deg, торец — не дальше gap_m.
    -> 4 вершины тумбы в px рендера или None"""
    D = np.asarray(desk_px, float); c0 = D.mean(0); e = [D[(i + 1) % 4] - D[i] for i in range(4)]; k = int(np.argmax([np.linalg.norm(x) for x in e]))
    u = e[k] / np.linalg.norm(e[k]); L = np.linalg.norm(e[k]); best = None
    for sg in (-1.0, 1.0):
        p = c0 + u * sg * (L / 2 + PED_M[1] * ppm / 2)                       # середина возможной тумбы за торцом
        x0, y0 = int(max(0, p[0] - PED_M[1] * ppm)), int(max(0, p[1] - PED_M[1] * ppm))
        x1, y1 = int(min(lab.shape[1], p[0] + PED_M[1] * ppm + 1)), int(min(lab.shape[0], p[1] + PED_M[1] * ppm + 1))
        if x1 <= x0 or y1 <= y0: continue
        for l in np.unique(lab[y0:y1, x0:x1]):
            if l == 0 or l in own_labels: continue
            sl = objs[int(l) - 1] if objs is not None else ndimage.find_objects((lab == l).astype(np.int32))[0]
            if sl is None or max(sl[0].stop - sl[0].start, sl[1].stop - sl[1].start) > 1.5 * (PED_M[1] * ppm + Sm_px): continue   # крупная — не тумба
            ys, xs = np.nonzero(lab[sl] == l); ys, xs = ys + sl[0].start, xs + sl[1].start
            if not len(xs) or len(xs) > 4 * (PED_M[1] * ppm) * (Sm_px + PED_DEPTH_TOL_M * ppm): continue
            (qx, qy), (w, h), a = cv2.minAreaRect(np.c_[xs, ys].astype(np.float32)); bx = cv2.boxPoints(((qx, qy), (w, h), a))
            f1, f2 = bx[1] - bx[0], bx[2] - bx[1]
            alongs = [abs(f1 @ u) / max(np.linalg.norm(f1), 1e-9), abs(f2 @ u) / max(np.linalg.norm(f2), 1e-9)]
            j = int(np.argmax(alongs)); la, ld = (np.linalg.norm(f1), np.linalg.norm(f2)) if j == 0 else (np.linalg.norm(f2), np.linalg.norm(f1))
            if alongs[j] < math.cos(math.radians(ang_deg)) or not (PED_M[0] <= la / ppm <= PED_M[1]) or abs(ld - Sm_px) / ppm > PED_DEPTH_TOL_M: continue
            s = float((np.array([qx, qy]) - c0) @ u) * sg
            if abs(s - (L / 2 + la / 2)) > gap_m * ppm + 2: continue          # вплотную к торцу (зазор — контур листа)
            if abs(float((np.array([qx, qy]) - c0) @ np.array([-u[1], u[0]]))) > PED_DEPTH_TOL_M * ppm: continue
            if best is None or abs(s - (L / 2 + la / 2)) < best[0]: best = (abs(s - (L / 2 + la / 2)), bx)
    return None if best is None else best[1]


def build(seats, lab, work_to_img, chairs_work, px_per_m, module_range=((1.25, 1.85), (0.55, 0.95)), chair_reach_m=1.2):
    """seats: [dict(n, x, y)] in the work frame (the number position); lab: desk components of the render;
    work_to_img: frame.Affine work -> render px; chairs_work: [(x, y)]. Returns [dict(n, desk, seat, how)] (work frame).
    v008: the chair of a number - one to one over the floor (assign_chairs: OV1, OV10, N11), never behind another desk (OV21).
    v010 (К-8; №90, map/rules/61 §2.4): тумба или приставка у торца стола — не часть места: стол и тумба одной заливкой — стол по модулю
    этажа у номера (split_end_piece), тумба отдельной компонентой у торца (end_pieces) — в записи места ключом 'pedestal' (рабочий кадр):
    её рисует шаг мебели предметом слоя furniture, в место и в стол она не входит."""
    toR = work_to_img; toX = work_to_img.inv()
    ppm = px_per_m * work_to_img.scale()                       # render px per metre
    chairs = [toR([c])[0] for c in chairs_work]
    lab_at = lambda p: lab[int(np.clip(round(p[1]), 0, lab.shape[0] - 1)), int(np.clip(round(p[0]), 0, lab.shape[1] - 1))]
    comp = {}
    for s in seats:
        q = toR([(s['x'], s['y'])])[0]; l = lab_at(q)
        if l == 0:
            x, y = int(round(q[0])), int(round(q[1]))
            win = lab[max(0, y - 12):y + 13, max(0, x - 12):x + 13]; vals = win[win > 0]
            l = int(np.bincount(vals).argmax()) if len(vals) else 0
        comp[s['n']] = (l, q)
    rects = {l: _rect(lab, l) for l in {v[0] for v in comp.values() if v[0]}}
    share = {}
    for n_, (l, q) in comp.items():
        share.setdefault(l, []).append(n_)
    (L0, L1), (S0, S1) = module_range
    std = [(max(w, h) / ppm, min(w, h) / ppm) for l, (c, (w, h), a) in rects.items()
           if len(share[l]) == 1 and L0 <= max(w, h) / ppm <= L1 and S0 <= min(w, h) / ppm <= S1]
    Lm, Sm = float(np.median([a for a, b in std])), float(np.median([b for a, b in std]))

    def near_chair(q, l):
        cs = [c for c in chairs if lab_at(c) != l and np.hypot(*(c - q)) < chair_reach_m * ppm and not behind_other_desk(lab, q, c, l)]
        return min(cs, key=lambda c: np.hypot(*(c - q))) if cs else None

    cell, ped = {}, {}
    for l, members in share.items():
        if l == 0:
            continue
        if len(members) == 1:                                   # v010 (К-8): стол и тумба одной заливкой — стол по модулю этажа, тумба отдельно
            sp_ = split_end_piece(rects[l], comp[members[0]][1], Lm * ppm, Sm * ppm, ppm)
            if sp_ is not None:
                cell[members[0]], ped[members[0]] = sp_
                continue
        (cx, cy), (w, h), ang = rects[l]
        single = len(members) == 1 and L0 <= max(w, h) / ppm <= L1 and S0 <= min(w, h) / ppm <= S1
        if single:
            continue
        box = cv2.boxPoints(((cx, cy), (w, h), ang)); c0 = np.array([cx, cy])
        e1 = box[1] - box[0]; e2 = box[2] - box[1]; La_, Lb_ = np.linalg.norm(e1), np.linalg.norm(e2)
        u1, u2 = e1 / La_, e2 / Lb_
        best = None
        for ua, La, ub, Lb in ((u1, La_, u2, Lb_), (u2, Lb_, u1, La_)):
            na = max(1, int(round(La / (Lm * ppm)))); nb = max(1, int(round(Lb / (Sm * ppm))))
            if na * nb < len(members):
                continue
            err = abs(La / na - Lm * ppm) / (Lm * ppm) + abs(Lb / nb - Sm * ppm) / (Sm * ppm)
            al = []
            for nn in members:
                q = comp[nn][1]; ch = near_chair(q, l)
                if ch is not None:
                    dv = (ch - q) / max(np.hypot(*(ch - q)), 1e-9); al.append(abs(dv @ ub))
            err -= 0.6 * (np.mean(al) if al else 0.0)          # chairs sit at the long side
            if best is None or err < best[0]:
                best = (err, ua, La, na, ub, Lb, nb)
        if best is None:
            ua, La, ub, Lb = (u1, La_, u2, Lb_) if La_ >= Lb_ else (u2, Lb_, u1, La_); na, nb = len(members), 1
        else:
            _, ua, La, na, ub, Lb, nb = best
        cells = []
        for i in range(na):
            for j in range(nb):
                ctr = c0 + ua * (-La / 2 + La * (i + 0.5) / na) + ub * (-Lb / 2 + Lb * (j + 0.5) / nb)
                hw, hd = min(Lm * ppm, La / na) / 2, min(Sm * ppm, Lb / nb) / 2
                cells.append((ctr, np.array([ctr + ua * hw + ub * hd, ctr - ua * hw + ub * hd,
                                             ctr - ua * hw - ub * hd, ctr + ua * hw - ub * hd])))
        pairs = sorted((np.hypot(*(cells[k][0] - comp[nn][1])), nn, k) for nn in members for k in range(len(cells)))
        taken, done = set(), set()
        for _, nn, k in pairs:
            if nn in done or k in taken:
                continue
            cell[nn] = cells[k][1]; taken.add(k); done.add(nn)
    places, objs = [], None
    order = sorted(seats, key=lambda s: s['n'])
    A_ = assign_chairs([comp[s['n']][1] for s in order], [comp[s['n']][0] for s in order], chairs, lab, chair_reach_m * ppm, [lab_at(c) for c in chairs])
    for i_, s in enumerate(order):
        l, q = comp[s['n']]
        if l == 0:
            places.append(dict(n=s['n'], desk=None, seat=(s['x'], s['y']), how='стол не найден')); continue
        D = cell.get(s['n'])
        if D is None:
            (cx, cy), (w, h), ang = rects[l]; D = cv2.boxPoints(((cx, cy), (w, h), ang))
        pb = ped.get(s['n'])
        if pb is None and len(share.get(l, [])) == 1:          # v010 (К-8): тумба отдельной компонентой у торца — предмет мебели
            objs = objs if objs is not None else ndimage.find_objects(lab)
            pb = end_pieces(lab, D, set(share), ppm, Sm * ppm, objs=objs)
        Dp = Polygon(toX(D)); ch = chairs[A_[i_]] if i_ in A_ else None
        if ch is not None:
            seat, how = tuple(toX([ch])[0]), 'стул'
        else:
            cc = np.array(Dp.exterior.coords[:4]); ed = sorted([(cc[i], cc[(i + 1) % 4]) for i in range(4)],
                                                              key=lambda e: -np.hypot(*(e[1] - e[0])))[:2]
            p = Point(s['x'], s['y']); e = min(ed, key=lambda e: LineString([tuple(e[0]), tuple(e[1])]).distance(p))
            mid = (e[0] + e[1]) / 2; o = mid - np.asarray(Dp.centroid.coords[0]); o /= np.linalg.norm(o)
            seat, how = tuple(mid + o * 0.25 * px_per_m), 'сторона стола'
        places.append(dict(n=s['n'], desk=Dp, seat=seat, how=how, **({'pedestal': Polygon(toX(pb))} if pb is not None else {})))
    return places


def keep_off_walls(places, wall_lines, half_wall, step=0.25, iters=25, band=None):
    """map/rules/61 §3.2: a desk that runs into a wall moves into the room up to the wall's inner edge, size kept.
    v012: band - the wall body, ready (places_plan: one union for the floor, not per desk); without it - as v011"""
    band = unary_union(wall_lines).buffer(half_wall) if band is None else band
    for q in places:
        D = q['desk']
        if D is None:
            continue
        for _ in range(iters):
            X = D.intersection(band)
            if X.area < 1e-3:
                break
            c = np.array(D.centroid.coords[0]); d = c - np.array(X.centroid.coords[0])
            if np.linalg.norm(d) < 1e-6:
                break
            cc = np.array(D.exterior.coords[:4]); ax = [cc[1] - cc[0], cc[2] - cc[1]]
            a = min(ax, key=lambda v: np.linalg.norm(v)); a = a / np.linalg.norm(a); a = a if a @ d > 0 else -a   # v008 (ОВ20 б): только по короткой стороне — от стены, не вдоль ряда
            if abs(a @ d) < 1e-6: break
            D = affinity.translate(D, *(a * step)); q['moved'] = q.get('moved', 0) + step
        q['desk'] = D
    return places


def resolve_overlaps(places):
    """no two desks overlap: clip the pair along the bisector of their centres"""
    for i in range(len(places)):
        for j in range(i + 1, len(places)):
            Di, Dj = places[i]['desk'], places[j]['desk']
            if Di is None or Dj is None or Di.intersection(Dj).area <= 0.01:
                continue
            ci, cj = np.array(Di.centroid.coords[0]), np.array(Dj.centroid.coords[0]); m = (ci + cj) / 2
            u = (cj - ci) / np.linalg.norm(cj - ci); v = np.array([-u[1], u[0]]); B = 1e4
            Hi = Polygon([tuple(m + v * B), tuple(m + v * B - u * B), tuple(m - v * B - u * B), tuple(m - v * B)])
            Hj = Polygon([tuple(m + v * B), tuple(m + v * B + u * B), tuple(m - v * B + u * B), tuple(m - v * B)])
            places[i]['desk'] = Di.intersection(Hi); places[j]['desk'] = Dj.intersection(Hj)
    return places


FONTS = ('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', '/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf', 'DejaVuSans-Bold.ttf',
         '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf')


def _font(px):
    from PIL import ImageFont
    for f in FONTS:
        try:
            return ImageFont.truetype(f, px)
        except OSError:
            pass
    return None


def draw_number(d, desk_poly, text, colour='#FFFFFF', max_px=14, min_px=6, margin=2.0):
    """row 181: the seat number in white at the desk centre over the desk fill. The largest size whose text box, with a 2 px margin,
    lies inside the drawn desk: then the number is a hole of the fill and the desk stays one colour spot. Returns the size or 0 (not drawn:
    no font, or the desk is too small even at min_px - the record says so, never silently)."""
    c = desk_poly.centroid
    for px in range(max_px, min_px - 1, -1):
        f = _font(px)
        if f is None:
            return 0
        x0, y0, x1, y1 = d.textbbox((0, 0), str(text), font=f, anchor='mm')
        box = Polygon([(c.x + x0 - margin, c.y + y0 - margin), (c.x + x1 + margin, c.y + y0 - margin), (c.x + x1 + margin, c.y + y1 + margin), (c.x + x0 - margin, c.y + y1 + margin)])
        if desk_poly.contains(box):
            d.text((c.x, c.y), str(text), fill=colour, font=f, anchor='mm')
            return px
    return 0


# ================================================================ v013 (К13.1; строка 391, №6): артефакт 3 — черновик 25 / 50 / 100
# Канон — map/rules/83 §6 и §1, map/rules/82 §0 («Как совмещать — черновик 25 / 50 / 100»). Прежняя сборка render_variant_c («Умножение» 60 %)
# убрана: схема одна, «Умножение» — не стандарт и не запасной путь (82 §0, ⛔ 15.10.2026, строка 391).
DRAFT_DENSITY = 0.25        # 83 §6 п. 1: серый оригинал, плотность 25 % (строка 359): out = 255 − 0,25 · (255 − серый)
DRAFT_ALPHA = 0.50          # 83 §6 п. 2: чистовик 50 %, α = 0,5 · clip((255 − min RGB) / 6, 0, 1)
DRAFT_RING_PX = 10          # 83 §6 п. 1: вне контура плана — белое; контур — наружное кольцо плана с запасом 10 px (px картинки)
DESK_COLOUR, SEAT_COLOUR, DESK_INSET = '#E6007E', '#FFB000', 1.5   # 83 §1, 82 §0 «Как собирается»
SEAT_D_M, SEAT_D_MIN_PX = 0.26, 6                   # 83 §1: точка стула ⌀ 0,26 м по масштабу картинки, не меньше 6 px (строки 356, 393)
NUM_REF_PPM, NUM_MIN_PX, NUM_MAX_PX = 54.0, 13, 34  # 83 §1, §6: кегль номера ≥ 13 px и ≤ 34 px холста при 54 px/м — пересчёт на масштаб картинки
DRAFT_SAT_MAX = 0.35        # 83 §6 п. 3: вне мест насыщенность пикселя ≤ 0,35
DRAFT_MAX_MB = 5.0          # 83 §6 п. 4, 82 §1: файл ≤ 5 МБ


def seat_diameter_px(px_per_m):
    """83 §1: ⌀ точки стула в px картинки = 0,26 м × px/м картинки, не меньше 6 px (14 px при 54 px/м)"""
    return max(float(SEAT_D_MIN_PX), SEAT_D_M * float(px_per_m))


def number_px_range(px_per_m):
    """83 §1, §6: (min, max) кегля номера в px картинки — 13 и 34 px холста при 54 px/м, пересчёт на px/м картинки"""
    k = float(px_per_m) / NUM_REF_PPM
    return max(1, int(round(NUM_MIN_PX * k))), max(1, int(round(NUM_MAX_PX * k)))


def plan_mask_svg(svg_path, size, ring_px=DRAFT_RING_PX):
    """83 §6 п. 1: маска «внутри контура плана» в px картинки size=(W, H): группы rooms и glass SVG чистовика, наружное кольцо (дыры залиты)
    с запасом ring_px. Пустая маска — ValueError (не «всё белое» молча)."""
    import io, re, cairosvg
    import xml.etree.ElementTree as ET
    W, H = size
    root = ET.parse(svg_path).getroot()
    ns = root.tag[:-3] if root.tag.endswith('svg') else ''
    for ch in list(root):
        if not (ch.tag == ns + 'g' and ch.get('id') in ('rooms', 'glass')):
            root.remove(ch)
    if not len(root):
        raise ValueError('plan_mask_svg: в SVG нет групп rooms и glass — контур плана не построить: %s' % svg_path)
    png = cairosvg.svg2png(bytestring=ET.tostring(root), output_width=W, output_height=H, background_color='white')
    im = np.asarray(Image.open(io.BytesIO(png)).convert('RGB'))
    m = ndimage.binary_fill_holes(im.min(axis=2) < 250)
    if not m.any():
        raise ValueError('plan_mask_svg: группы rooms и glass пустые — контур плана не построить: %s' % svg_path)
    r = int(math.ceil(ring_px)); yy, xx = np.mgrid[-r:r + 1, -r:r + 1]
    return cv2.dilate(m.astype(np.uint8), ((xx ** 2 + yy ** 2) <= ring_px ** 2).astype(np.uint8)) > 0


def original_in_frame(source, M, size, page=0):
    """83 §6 п. 1: оригинал в кадре картинки чистовика тем же масштабом. source — растр (PNG/JPG) или PDF; M — 2×3: px растра (у PDF — pt
    страницы в повороте страницы) -> px картинки; size=(W, H). Вне листа — белое. -> RGB uint8 H×W"""
    W, H = size; M = np.asarray(M, float).reshape(2, 3)
    if str(source).lower().endswith('.pdf'):
        import pymupdf
        pg = pymupdf.open(source)[page]
        pm = pg.get_pixmap(matrix=pymupdf.Matrix(M[0, 0], M[1, 0], M[0, 1], M[1, 1], 0, 0), alpha=False)
        a = np.frombuffer(pm.samples, np.uint8).reshape(pm.height, pm.width, pm.n)[:, :, :3]
        T = np.array([[1.0, 0, M[0, 2] + pm.x], [0, 1.0, M[1, 2] + pm.y]])
    else:
        a = np.asarray(Image.open(source).convert('RGB')); T = M
    return cv2.warpAffine(np.ascontiguousarray(a), T, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=(255, 255, 255))


def _num(rec):
    return str(rec.get('number') if rec.get('number') not in (None, '') else rec.get('seat'))


def render_draft(clean_png, original_rgb, places, out_png, px_per_m, inside=None, density=DRAFT_DENSITY, alpha=DRAFT_ALPHA,
                 overlaps=True, log=print):
    """Артефакт 3 — черновик 25 / 50 / 100 (map/rules/83 §6; 82 §0; строка 391). Размер — картинки чистовика clean_png, до пикселя.
      1. низ — оригинал original_rgb (H×W×3 в кадре картинки, original_in_frame; None — белый) в сером 0,299 R + 0,587 G + 0,114 B,
         плотность density: out = 255 − density · (255 − серый); вне inside (маска контура плана, plan_mask_svg) — белое;
      2. середина — чистовик, только непустые пиксели: α = alpha · clip((255 − min RGB) / 6, 0, 1), out = низ · (1 − α) + чистовик · α;
      3. верх — места 100 %: сначала все столы #E6007E с отступом 1,5 px, затем вторым проходом номера (штатная draw_number, кегль по
         number_px_range) и точки стульев #FFB000 ⌀ seat_diameter_px — точку не закрывает соседний стол.
    places — записи JSON мест в px картинки (ключи 83 §5: seat/number, desk, centre, x, y, …). Пересекающиеся столы — штатной resolve_overlaps
    (overlaps=True); подрезанный стол меняет desk и centre записи — вернувшиеся записи писать в JSON (места строятся один раз, 83 §6).
    px_per_m — px на метр КАРТИНКИ. -> (записи, info); info: size, seat_d_px, number_px, clipped, no_desk, no_number, sat_over, sat_max, bytes."""
    clean = np.asarray(Image.open(clean_png).convert('RGB'))
    H, W = clean.shape[:2]
    if original_rgb is None:
        log('черновик: ВНИМАНИЕ — оригинала нет: нижний слой белый (только для проверки Ч-29, не для сдачи)')
        under = np.full((H, W), 255.0)
    else:
        if original_rgb.shape[:2] != (H, W):
            raise ValueError('render_draft: оригинал %d × %d, картинка чистовика %d × %d — оригинал не в кадре чистовика' % (original_rgb.shape[1], original_rgb.shape[0], W, H))
        o = original_rgb.astype(float)
        under = 0.299 * o[:, :, 0] + 0.587 * o[:, :, 1] + 0.114 * o[:, :, 2]
    if inside is None:
        log('черновик: ВНИМАНИЕ — маски контура плана нет: оригинал вне плана (рамка, легенда, штамп) не убран (83 §6 п. 1)')
    else:
        under = np.where(inside, under, 255.0)
    base = 255.0 - density * (255.0 - under)
    al = (alpha * np.clip((255.0 - clean.min(axis=2).astype(float)) / 6.0, 0, 1))[:, :, None]
    mid = base[:, :, None] * (1 - al) + clean.astype(float) * al
    img = Image.fromarray(np.clip(mid + 0.5, 0, 255).astype(np.uint8)); d = ImageDraw.Draw(img)
    recs = [dict(r) for r in places]
    no_desk = [_num(r) for r in recs if not r.get('desk')]
    for n in no_desk:
        log('черновик: ВНИМАНИЕ — место %s без многоугольника стола (desk пуст): стол не нарисован, Ч-29 — fail (83 §1)' % n)
    Q = [dict(n=_num(r), desk=Polygon(r['desk']) if r.get('desk') else None) for r in recs]
    clipped = 0
    if overlaps:
        before = [q['desk'] for q in Q]
        resolve_overlaps(Q)
        for r, q, b in zip(recs, Q, before):
            if q['desk'] is not None and b is not None and not q['desk'].equals(b):
                g = q['desk'] if q['desk'].geom_type == 'Polygon' else max(q['desk'].geoms, key=lambda g_: g_.area)
                q['desk'] = g; clipped += 1
                r['desk'] = [[round(x, 1), round(y, 1)] for x, y in np.asarray(g.exterior.coords)[:-1]]
                r['centre'] = [round(g.centroid.x, 1), round(g.centroid.y, 1)]
        if clipped:
            log('черновик: столов подрезано resolve_overlaps — %d: desk и centre записей изменены, JSON писать из возвращённых записей' % clipped)
    finish_records(recs)                                           # v013 (83 §5): gaze_deg — по desk и centre после подрезки; room не трогается
    inner = []
    for q in Q:                                                    # проход 1: все столы
        Di = q['desk'].buffer(-DESK_INSET, join_style=2) if q['desk'] is not None else None
        if Di is not None and not Di.is_empty:
            Di = Di if Di.geom_type == 'Polygon' else max(Di.geoms, key=lambda g_: g_.area)
            d.polygon([tuple(v) for v in np.asarray(Di.exterior.coords)], fill=DESK_COLOUR)
        inner.append(Di if Di is not None and not Di.is_empty else None)
    lo, hi = number_px_range(px_per_m); no_number = []
    for r, q, Di in zip(recs, Q, inner):                           # проход 2: номера ...
        if Di is None:
            continue
        r['number_px'] = draw_number(d, Di, q['n'], '#FFFFFF', max_px=hi, min_px=lo)
        if not r['number_px']:
            no_number.append(q['n'])
    for n in no_number:
        log('черновик: ВНИМАНИЕ — номер места %s не нарисован: стол меньше номера кеглем %d px (83 §1) или нет шрифта' % (n, lo))
    sd = seat_diameter_px(px_per_m); rr = sd / 2
    for r in recs:                                                 # ... и точки стульев — последними, их не закрывает соседний стол
        if r.get('x') is None or r.get('y') is None:
            log('черновик: ВНИМАНИЕ — место %s без точки стула (x, y)' % _num(r)); continue
        d.ellipse([r['x'] - rr, r['y'] - rr, r['x'] + rr, r['y'] + rr], fill=SEAT_COLOUR)
    out = np.asarray(img).astype(float)
    pm = Image.new('L', (W, H), 0); dm = ImageDraw.Draw(pm)       # насыщенность вне мест (83 §6 п. 3): маска мест с запасом 2 px на сглаживание
    for q in Q:
        if q['desk'] is not None:
            g = q['desk'].buffer(2)
            for g_ in (g.geoms if hasattr(g, 'geoms') else [g]):
                dm.polygon([tuple(v) for v in np.asarray(g_.exterior.coords)], fill=255)
    for r in recs:
        if r.get('x') is not None and r.get('y') is not None:
            dm.ellipse([r['x'] - rr - 2, r['y'] - rr - 2, r['x'] + rr + 2, r['y'] + rr + 2], fill=255)
    mx, mn = out.max(axis=2), out.min(axis=2)
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-9), 0)[np.asarray(pm) == 0]
    sat_over = int((sat > DRAFT_SAT_MAX + 1e-9).sum()); sat_max = round(float(sat.max()) if sat.size else 0.0, 3)
    if sat_over:
        log('черновик: ВНИМАНИЕ — вне мест %d px насыщеннее %.2f (макс. %.3f): «других насыщенных цветов нет» нарушено (83 §6 п. 3)' % (sat_over, DRAFT_SAT_MAX, sat_max))
    img.save(out_png, optimize=True)
    import os
    b = os.path.getsize(out_png)
    if b / 1e6 > DRAFT_MAX_MB:
        log('черновик: ВНИМАНИЕ — файл %.2f МБ > 5 МБ: сжать без смены размера в px (82 §1)' % (b / 1e6))
    info = dict(size=[W, H], px_per_m=round(float(px_per_m), 3), seat_d_px=round(sd, 2), number_px=[lo, hi], density=density, alpha=alpha,
                places=len(recs), clipped=clipped, no_desk=no_desk, no_number=no_number, sat_over=sat_over, sat_max=sat_max, bytes=b)
    log('черновик: %s — %d × %d px, мест %d, ⌀ точки %.1f px, кегль номера %d–%d px, подрезано %d, без стола %d, без номера %d, насыщенность вне мест макс. %.3f, %.2f МБ'
        % (os.path.basename(out_png), W, H, len(recs), sd, lo, hi, clipped, len(no_desk), len(no_number), sat_max, b / 1e6))
    return recs, info


def _affine6(s):
    v = [float(x) for x in str(s).split(',')]
    if len(v) != 6:
        raise SystemExit('--source-transform: нужно 6 чисел a,b,tx,c,d,ty')
    return np.array(v).reshape(2, 3)


def draft_main(argv=None):
    """python3 -m unspot_map.workplaces draft --clean чистовик.png --svg чистовик.svg --places places.json --px-per-m <px холста на м>
         --source исходник.png|.pdf --source-transform a,b,tx,c,d,ty --out черновик.png [--places-out places.json] [--page 0]
    --source-transform — px исходника (у PDF — pt страницы) -> px холста SVG, как у acceptance_checks; на картинку чистовика пересчитывается
    отношением её размера к viewBox. --px-per-m — px холста на метр (как --scale-px-per-m приёмки). Канон — map/rules/83 §6."""
    import argparse, json, os
    from .svg_map import svg_canvas
    ap = argparse.ArgumentParser(prog='unspot_map.workplaces draft', description='артефакт 3 — черновик 25 / 50 / 100 (map/rules/83 §6)')
    ap.add_argument('--clean', required=True); ap.add_argument('--svg', required=True); ap.add_argument('--places', required=True)
    ap.add_argument('--px-per-m', type=float, required=True); ap.add_argument('--source'); ap.add_argument('--source-transform')
    ap.add_argument('--page', type=int, default=0); ap.add_argument('--out', required=True); ap.add_argument('--places-out')
    a = ap.parse_args(argv)
    W, H = Image.open(a.clean).size; cw, ch = svg_canvas(a.svg); kx, ky = W / cw, H / ch
    if abs(kx - ky) > 2 / min(W, H) * max(kx, ky):
        print('черновик: ВНИМАНИЕ — пропорции картинки %d × %d и viewBox %g × %g разные (×%.4f и ×%.4f)' % (W, H, cw, ch, kx, ky))
    orig = None
    if a.source:
        if not a.source_transform:
            raise SystemExit('--source без --source-transform: кадр оригинала не известен — по догадке не совмещаю')
        M = np.diag([kx, ky]) @ _affine6(a.source_transform)
        orig = original_in_frame(a.source, M, (W, H), a.page)
    J = json.load(open(a.places, encoding='utf-8')); P = J['places'] if isinstance(J, dict) else J
    recs, info = render_draft(a.clean, orig, P, a.out, a.px_per_m * (kx + ky) / 2, inside=plan_mask_svg(a.svg, (W, H)))
    recs, no_g, no_r = finish_records(recs, rooms_svg(a.svg, (kx + ky) / 2), keep_room=True)   # v013 (83 §5): room — по SVG, если не записан
    if no_g or no_r:
        print('черновик: ВНИМАНИЕ — без gaze_deg %d, без room %d (83 §5)' % (no_g, no_r))
    if a.places_out:
        if isinstance(J, dict):
            J = dict(J); J['places'] = recs
        else:
            J = recs
        json.dump(J, open(a.places_out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    elif info['clipped']:
        print('черновик: ВНИМАНИЕ — столы подрезаны, а --places-out не дан: JSON и картинка разошлись (83 §6)')
    json.dump(info, open(a.out + '.draft.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(json.dumps({k: v for k, v in info.items() if k not in ('no_desk', 'no_number')}, ensure_ascii=False))
    return 0 if not (info['no_desk'] or info['sat_over']) else 1


def count_marks(png, desk=(0xE6, 0x00, 0x7E), seat=(0xFF, 0xB0, 0x00), min_area=30):
    """colour search check: spots of desk colour and of seat colour (must equal the number of places); desk spots - on the fill mask
    before the numbers: a white number over the fill is a hole, holes are filled (ОВ11, Е13)"""
    im = cv2.imread(png); b, g, r = [im[:, :, i].astype(int) for i in range(3)]
    md = ndimage.binary_fill_holes((abs(r - desk[0]) < 40) & (g < 60) & (abs(b - desk[2]) < 50)).astype(np.uint8)
    ms = ((r > 230) & (abs(g - seat[1]) < 35) & (b < 60)).astype(np.uint8)
    cnt = lambda m: sum(1 for s in cv2.connectedComponentsWithStats(m)[2][1:] if s[4] > min_area)
    return cnt(md), cnt(ms)


# ================================================================ v012 (КМ-20, КМ-21): выбор способа мест и запуск
SOURCE_ORDER = ('plan', 'fill+numbers', 'lines', 'raster')     # порядок выбора способа (PLANMAP КМ-20; строка 299)
NUM_ON_FILL = 0.5              # способ «заливка и номера» — если на заливке столов стоит ≥ 50 % текстов формата номера (клиент А 2: 118 «номеров» —
                               # оси, отметки, экспликация; на заливке — единицы: способ не годится, идём по линиям)


def desk_fill_count(lab, render_ppm, module_range=((0.95, 1.9), (0.45, 0.95))):
    """сколько компонент заливки столов размера стола — признак «у листа есть заливка столов» класса lo–hi"""
    (L0, L1), (S0, S1) = module_range; n = 0
    for sl in ndimage.find_objects(lab):
        if sl is None: continue
        h, w = (sl[0].stop - sl[0].start) / render_ppm, (sl[1].stop - sl[1].start) / render_ppm
        a, b = max(h, w), min(h, w)
        if L0 * 0.8 <= a <= L1 * 1.6 and S0 * 0.8 <= b <= S1 * 1.2: n += 1
    return n


def records(places, F, px_per_m, src, rooms=None):
    """места (кадр work.png, Polygon) -> записи places.json в кадре F (work -> картинка): seat, number, by, desk, centre, x, y, size_m, src,
    room, gaze_deg (v013, 83 §5: rooms — rooms_svg(...) в px картинки; None — room пишется None)"""
    out = []
    for q in places:
        if q.get('desk') is None:
            out.append(dict(seat=str(q.get('n')), number=str(q.get('n')), by=q.get('how'), desk=None, x=round(float(F([q['seat']])[0][0]), 1),
                            y=round(float(F([q['seat']])[0][1]), 1), src=src)); continue
        D = Polygon(F(np.asarray(q['desk'].exterior.coords)[:-1])); c = D.centroid; s = F([q['seat']])[0]
        R = D.minimum_rotated_rectangle; cc = np.asarray(R.exterior.coords)[:4]
        a, b = np.hypot(*(cc[1] - cc[0])), np.hypot(*(cc[2] - cc[1]))
        rec = dict(seat=str(q.get('n')), number=str(q.get('n')), by=q.get('how'), desk=[[round(x, 1), round(y, 1)] for x, y in np.asarray(D.exterior.coords)[:-1]],
                   centre=[round(c.x, 1), round(c.y, 1)], x=round(float(s[0]), 1), y=round(float(s[1]), 1),
                   size_m=q.get('size_m') or [round(max(a, b) / px_per_m, 2), round(min(a, b) / px_per_m, 2)], src=src)
        if q.get('pedestal') is not None:
            rec['pedestal'] = [[round(x, 1), round(y, 1)] for x, y in F(np.asarray(q['pedestal'].exterior.coords)[:-1])]
        out.append(rec)
    return finish_records(out, rooms)[0]


# ================================================================ v013 (К13.3; map/rules/83 §5, строка 391): поля room и gaze_deg записи места
def gaze_deg(x, y, cx, cy):
    """83 §5: направление от стула (x, y) к столу (центр cx, cy), градусы в px картинки: 0 — вправо, 90 — вниз, [0, 360);
    стул сверху стола (N) — 90, справа (E) — 180, снизу (S) — 270, слева (W) — 0. Нет точки или стул в центре стола — None"""
    if any(v is None for v in (x, y, cx, cy)):
        return None
    dx, dy = float(cx) - float(x), float(cy) - float(y)
    if math.hypot(dx, dy) < 1e-9:
        return None
    g = round(math.degrees(math.atan2(dy, dx)) % 360.0, 1)
    return 0.0 if g >= 360.0 else g


def rooms_svg(svg_path, k=1.0):
    """помещения карты (пути room-… слоя rooms, как places_plan.map_walls) в px картинки; k — px картинки на px холста -> [dict(id, name, type, poly)]"""
    from .places_plan import map_walls
    _, _, rooms = map_walls(svg_path)
    return [dict(id=r['id'], name=r['name'] or r['id'], type=r['type'], poly=affinity.scale(r['poly'], k, k, origin=(0, 0)))
            for r in rooms if not r['poly'].is_empty]


def room_of(pt, rooms):
    """83 §5: имя (data-name) или id наименьшего помещения карты, где точка; нет — None"""
    p = Point(float(pt[0]), float(pt[1])); h = [r for r in rooms if r['poly'].contains(p)]
    return min(h, key=lambda r: r['poly'].area)['name'] if h else None


def finish_records(recs, rooms=None, keep_room=False):
    """83 §5: у каждой записи — gaze_deg (от точки стула x, y к центру стола centre; нет centre — к середине desk) и room (помещение центра
    стола; без стола — точки стула). rooms — rooms_svg(...) в px картинки; None — room не вычисляется (нет ключа — пишется None, громко у вызывающего).
    keep_room — room, уже записанный (исполнителем, по объектам плана), не менять. -> (записи, без gaze_deg, без room)"""
    no_g = no_r = 0
    for r in recs:
        c = r.get('centre')
        if c is None and r.get('desk'):
            c = [float(v) for v in np.mean(np.asarray(r['desk'], float)[:, :2], axis=0)]
        r['gaze_deg'] = gaze_deg(r.get('x'), r.get('y'), *(c if c is not None else (None, None)))
        no_g += r['gaze_deg'] is None
        if rooms is not None and not (keep_room and r.get('room') not in (None, '')):
            pt = c if c is not None else ((r['x'], r['y']) if r.get('x') is not None and r.get('y') is not None else None)
            r['room'] = room_of(pt, rooms) if pt is not None else None
        r.setdefault('room', None)
        no_r += r.get('room') in (None, '')
    return recs, no_g, no_r


def fields_main(argv=None):
    """python3 -m unspot_map.workplaces fields --places places.json --svg чистовик.svg (--image картинка.png | --image-size W,H) --out places.json [--keep-room]
    Дописать room и gaze_deg (map/rules/83 §5) в JSON мест, собранный вручную или другим способом: координаты — px картинки (артефакт 3),
    помещения — пути room-… SVG, пересчёт на картинку — размер картинки к viewBox. Ключи не по схеме (desk_polygon, desk_centre, chair_point) — громко,
    не переименовываются: приёмка читает только desk, centre, x, y (Ч-21, Ч-29)."""
    import argparse, json
    from .svg_map import svg_canvas
    ap = argparse.ArgumentParser(prog='unspot_map.workplaces fields', description='room и gaze_deg записи места (map/rules/83 §5)')
    ap.add_argument('--places', required=True); ap.add_argument('--svg', required=True); ap.add_argument('--image'); ap.add_argument('--image-size')
    ap.add_argument('--out', required=True); ap.add_argument('--keep-room', action='store_true', help='room, уже записанный в JSON, не менять')
    a = ap.parse_args(argv)
    cw, ch = svg_canvas(a.svg)
    if a.image:
        W, H = Image.open(a.image).size
    elif a.image_size:
        W, H = (int(v) for v in a.image_size.split(','))
    else:
        raise SystemExit('нужен --image или --image-size: координаты JSON — px картинки, помещения — px холста (83 §5)')
    k = (W / cw + H / ch) / 2
    J = json.load(open(a.places, encoding='utf-8')); P = J['places'] if isinstance(J, dict) else J
    if P and not any(r.get('desk') or r.get('centre') for r in P):
        print('места: ВНИМАНИЕ — ни у одной записи нет desk и centre: ключи не по схеме map/rules/83 §5 — приёмка даст fail «записей %d, столов 0» (Ч-21, Ч-29)' % len(P))
    P, no_g, no_r = finish_records(P, rooms_svg(a.svg, k), keep_room=a.keep_room)
    if no_g:
        print('места: ВНИМАНИЕ — без gaze_deg %d: нет точки стула (x, y) или центра стола' % no_g)
    if no_r:
        print('места: ВНИМАНИЕ — без room %d: центр стола вне помещений room-… SVG' % no_r)
    if isinstance(J, dict):
        J = dict(J); J['places'] = P
    else:
        J = P
    json.dump(J, open(a.out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(json.dumps(dict(places=len(P), no_gaze=no_g, no_room=no_r, image=[W, H], k=round(k, 4)), ensure_ascii=False))
    return 0 if not (no_g or no_r) else 1


def main():
    """python3 -m unspot_map.workplaces --intake intake.json --src лист.pdf|work.png --px-per-m <px work.png на м> --out places.json
         [--plan-dxf plan.dxf --frame M_t.npy --map-px-per-m X --svg plan.svg --desk-in-wall shift|cut]   (способ 1 — объекты плана)
         [--desk-fill 150,215] [--numbers numbers.json] [--chairs-json chairs.json]                        (способ 2 — заливка и номера, v011)
         [--source-transform a,b,tx,c,d,ty]  (work.png -> картинка карты; без него — кадр work.png, frame «source»)
    Порядок (КМ-20): есть объекты плана -> по плану; иначе есть заливка столов и номера -> как v011; иначе вектор -> по линиям; растр -> LSD
    и строка «сверка глазами обязательна». В выводе и в places.json — «у листа есть заливка столов / номера: да/нет» и выбранный способ."""
    import argparse, json
    ap = argparse.ArgumentParser(description='места артефакта 3: выбор способа (план -> заливка и номера -> линии -> растр)')
    ap.add_argument('--intake', required=True); ap.add_argument('--src', required=True); ap.add_argument('--px-per-m', type=float, required=True)
    ap.add_argument('--out', default='places.json'); ap.add_argument('--chairs-out')
    ap.add_argument('--plan-dxf'); ap.add_argument('--frame'); ap.add_argument('--map-px-per-m', type=float); ap.add_argument('--svg')
    ap.add_argument('--desk-in-wall', choices=('shift', 'cut'), default='shift')
    ap.add_argument('--desk-fill', default='150,215', help='класс заливки столов листа: серый lo,hi (map/rules/61 §2.4; по умолчанию — как v011)')
    ap.add_argument('--numbers', help='номера листа (sheet.numbers JSON, кадр work.png); без ключа — текстовый слой листа')
    ap.add_argument('--chairs-json', help='стулья листа (unspot_map.chairs, frame source) — для способа 2')
    ap.add_argument('--source-transform', help='a,b,tx,c,d,ty: px work.png -> px картинки карты (как у acceptance_checks)')
    ap.add_argument('--force', choices=SOURCE_ORDER, help='способ задан вручную (для стенда)')
    ap.add_argument('--image-size', help='v013: W,H картинки артефакта 3 — для room по помещениям --svg (по умолчанию картинка = холст SVG)')
    ap.add_argument('--stroke-max', type=float, help='способ «линии»: штрихи листа не светлее этого серого (по умолчанию 0,7 — инструмент 24.09); класс — из паспорта листа')
    a = ap.parse_args()
    from .frame import Affine
    logs = []
    def log(s):
        print(s); logs.append(s)
    it = json.load(open(a.intake, encoding='utf-8')); cls = it.get('class', '')
    T = Affine(np.array([float(v) for v in a.source_transform.split(',')]).reshape(2, 3)) if a.source_transform else Affine(np.eye(3))
    frame = 'artefact3 px' if a.source_transform else 'source'
    ppm_out = a.px_per_m * T.scale()
    places, how, chairs_out, extra = [], None, None, {}
    fill_n = num_n = None
    # 1. объекты инженерного плана
    if (a.force in (None, 'plan')) and a.plan_dxf:
        if not a.frame or not a.map_px_per_m:
            raise SystemExit('--plan-dxf: нужны --frame (M_t.npy моста) и --map-px-per-m')
        from . import places_plan
        from .zones import load_frame
        M, t = load_frame(a.frame)
        recs, ch, fdesks, peds, info = places_plan.build(a.plan_dxf, M, t, a.map_px_per_m, a.svg, a.desk_in_wall, log=log)
        if recs:
            places, how, chairs_out, extra = recs, 'plan', dict(frame='plan', px_per_m=a.map_px_per_m, how='объекты chair плана', chairs=ch), \
                dict(info=info, furniture_desks=fdesks, pedestals=peds)
            frame, ppm_out = 'artefact3 px', a.map_px_per_m
        else:
            log('места: ВНИМАНИЕ — по объектам плана мест нет — следующий способ')
    vector = it.get('kind') == 'pdf' and cls in ('pdf-vector', 'pdf-mixed')
    # 2. заливка столов и номера (v011)
    if how is None and a.force in (None, 'fill+numbers') and vector:
        from .pdf_source import render
        from .frame import Affine as _A
        zoom = 4.0; dpi = it['render']['dpi']; pno = it['chosen_page']
        img = render(a.src, pno - 1, zoom=zoom, text=False)
        lo, hi = (float(v) for v in a.desk_fill.split(','))
        lab = desk_components(img, lo=lo, hi=hi)
        work_to_img = _A.scale_shift(zoom / (dpi / 72.0), zoom / (dpi / 72.0))
        fill_n = desk_fill_count(lab, a.px_per_m * work_to_img.scale())
        if a.numbers:
            nums = json.load(open(a.numbers, encoding='utf-8')).get('numbers', [])
        else:
            from .sheet import numbers as _numbers
            nums = _numbers(a.src, a.intake, a.px_per_m, page=pno)['numbers']
        num_n = len(nums)
        on = 0                                                   # номера на заливке столов (окно 12 px рендера, как build)
        for q in nums:
            x, y = work_to_img([(q['x'], q['y'])])[0]; x, y = int(round(x)), int(round(y))
            win = lab[max(0, y - 12):y + 13, max(0, x - 12):x + 13]; on += bool((win > 0).any())
        log('места: у листа заливка столов (серый %g–%g): %s (%d компонент размера стола); номера мест: %s (%d, на заливке %d)' % (
            lo, hi, 'да' if fill_n else 'нет', fill_n, 'да' if num_n else 'нет', num_n, on))
        if fill_n and num_n and on < max(3, NUM_ON_FILL * num_n):
            log('места: ВНИМАНИЕ — номера не на заливке столов (%d из %d): заливка и номера листа — не столы мест, способ «заливка и номера» '
                'не годится — следующий способ' % (on, num_n))
        if fill_n and num_n and on >= max(3, NUM_ON_FILL * num_n):
            chairs_w = []
            if a.chairs_json:
                cj = json.load(open(a.chairs_json, encoding='utf-8')); chairs_w = [tuple(c[:2]) for c in cj.get('chairs', [])]
            P = build([dict(n=q['n'], x=q['x'], y=q['y']) for q in nums], lab, work_to_img, chairs_w, a.px_per_m)
            nf = sum(1 for q in P if q['desk'] is None)
            if nf:
                log('места: ВНИМАНИЕ — номеров без стола на заливке: %d («стол не найден»)' % nf)
            places, how = records([q for q in P if q['desk'] is not None], T, ppm_out, 'numbers'), 'fill+numbers'
    # 3. линии вектора
    if how is None and a.force in (None, 'lines') and vector:
        from . import desks_lines as DL
        S = DL.pdf_segments(a.src, it['chosen_page'], it['render']['to_pixels'], **({'stroke_max': a.stroke_max} if a.stroke_max else {}))
        D, X, plain, info = DL.detect(S, a.px_per_m, log=log)
        P = [dict(q, n='L%03d' % (i + 1)) for i, q in enumerate(sorted(DL.to_places(D, a.px_per_m), key=lambda q: (round(q['seat'][1] / (2 * a.px_per_m)), q['seat'][0])))]
        places, how = records(P, T, ppm_out, 'lines'), 'lines'
        chairs_out = dict(frame='source', px_per_m=a.px_per_m, how='стулья у столов по линиям (центр линий стула), px work.png', chairs=DL.chairs_of(D))
        extra = dict(info=info, crossed=len(X), plain=len(plain))
    # 4. растр
    if how is None and a.force in (None, 'raster', 'lines'):
        from . import desks_lines as DL
        from PIL import Image
        src_png = a.src if not a.src.lower().endswith('.pdf') else None
        if src_png is None:
            import os
            src_png = os.path.join(os.path.dirname(a.intake), 'work.png')
        g = np.asarray(Image.open(src_png).convert('L'))
        D, X, plain, info = DL.detect_raster(g, a.px_per_m, log=log)
        P = [dict(q, n='L%03d' % (i + 1)) for i, q in enumerate(sorted(DL.to_places(D, a.px_per_m), key=lambda q: (round(q['seat'][1] / (2 * a.px_per_m)), q['seat'][0])))]
        places, how = records(P, T, ppm_out, 'lines'), 'raster'
        chairs_out = dict(frame='source', px_per_m=a.px_per_m, how='стулья у столов по LSD (центр линий стула), px work.png', chairs=DL.chairs_of(D))
        extra = dict(info=info, crossed=len(X), plain=len(plain))
        log('места: растр — СВЕРКА ГЛАЗАМИ ОБЯЗАТЕЛЬНА (map/rules/82 §0): поиск по LSD пропускает 9–34 % столов (проба 24.09)')
    if not places:
        log('места: ВНИМАНИЕ — мест 0: ни один способ не дал столов (%s) — места вручную, сверка глазами' % (how or 'способ не выбран'))
    else:                                                          # v013 (83 §5): room и gaze_deg — во всех способах
        rooms = None
        if how != 'plan' and a.svg and frame == 'artefact3 px':
            from .svg_map import svg_canvas
            cw_, ch_ = svg_canvas(a.svg); k_ = float(a.image_size.split(',')[0]) / cw_ if a.image_size else 1.0
            if not a.image_size:
                log('места: room — по помещениям --svg, картинка = холст SVG (--image-size не дан)')
            rooms = rooms_svg(a.svg, k_)
        elif how != 'plan':
            log('места: ВНИМАНИЕ — room не записан: нужны --svg карты и кадр картинки (--source-transform) — map/rules/83 §5; дописать: '
                'python3 -m unspot_map.workplaces fields')
        places, no_g, no_r = finish_records(places, rooms, keep_room=(how == 'plan'))
        if no_g:
            log('места: ВНИМАНИЕ — без gaze_deg %d: нет точки стула или центра стола (83 §5)' % no_g)
        if no_r and rooms is not None:
            log('места: ВНИМАНИЕ — без room %d: центр стола вне помещений SVG (83 §5)' % no_r)
    json.dump(dict(frame=frame, px_per_m=ppm_out, source='workplaces: способ %s' % how, method=how, desk_fill=fill_n, numbers=num_n,
                   places=places, log=logs, **extra), open(a.out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    if a.chairs_out and chairs_out:
        json.dump(chairs_out, open(a.chairs_out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(json.dumps(dict(method=how, places=len(places), desk_fill=fill_n, numbers=num_n), ensure_ascii=False))
    raise SystemExit(0 if places else 2)


if __name__ == '__main__':
    import sys
    if sys.argv[1:2] == ['draft']:
        raise SystemExit(draft_main(sys.argv[2:]))
    if sys.argv[1:2] == ['fields']:
        raise SystemExit(fields_main(sys.argv[2:]))
    main()
