"""Столы и места по линиям листа — вектор и растр (v012, КМ-20; ОЧ-87; решение владельца 09.10.2026 №123, строка 299: «учить код искать по линиям»;
proposals/map/2026-10-09-места-по-линиям-и-код-v011, вариант а; map/rules/82 §0 «Как найти столы», map/rules/11 §10).

Основа — инструмент 24.09.2026 (прежняя редакция map/code/61, Диск «11», id 1aMOx2ELZMYqvOXoZIpMAUGwHSgT9poMt): wpdet.py и chairfeat.py перенесены
без изменения порогов; вход и выход — под код карты:
 * стол — прямоугольник 0,95–1,9 × 0,45–0,95 м по опоре четырёх сторон (find_rects): осевые и прочие линии поверх стола поиск не ломают;
 * осевые — по повторяемости длин штрихов (axis_mask); на растре — много коротких кусков (loose);
 * прямоугольник с крестом — стеллаж или шкаф, не место (решение владельца 24.09.2026, строка 24): список `crossed`, в места не идёт;
 * составной прямоугольник (стол + короб МФУ) отбрасывается (atomic); внутри стола — не больше 3 м линии на м²;
 * стул — полоса 0,05–0,55 м у длинной стороны (обрезанная по помещению, если помещения даны): ≥ 3 м линии на м², комок 0,3–1,0 × ≥ 0,2 м
   у середины стороны, ≥ 2 направлений линий; место — центр линий стула; прямоугольник без стула — не место (`plain`);
 * растр — отрезки LSD плитками 600 px (перекрытие 120), растр приводится к ≈ 100 px/м (лучшее разрешение пробы 24.09), плотности делятся на
   кратность края LSD; после поиска на растре — **сверка глазами обязательна** (map/rules/82 §0): пропуски 9–34 % на пробе 24.09.

Единицы — метры; вход — отрезки в px рабочего растра (`work.png` приёма) и px/м этого растра. Вектор: штрихи PDF (`page.get_drawings()`,
чёрные и серые, «l», «re», «c», «qu») переводятся матрицей `render.to_pixels` из intake.json. Выход — места в кадре work.png:
[dict(desk: Polygon, seat: (x, y), how: 'стул (линии)', src: 'lines', size_m, conf)], стеллажи `crossed`, прямоугольники без стула `plain`.
Ни одного стола — громко («линии не дали ни одного стола»), не «мест 0» молча.

Порядок выбора способа и запуск — `unspot_map.workplaces` (main): план -> заливка и номера -> линии -> растр LSD."""
import math, bisect
import numpy as np
from shapely.geometry import Polygon, LineString, Point, box
from shapely.strtree import STRtree

RASTER_PPM = 100.0             # растр приводится к ≈ 100 px/м (проба 24.09: 54 px/м — 23 из 35, 100 — 31–32, 150 — 27)
RASTER_PPM_RANGE = (80.0, 130.0)
RASTER_PPM_MIN = 45.0          # v012: ниже — громко: проба 24.09 — от 54 px/м; s124 «12» (23 px/м) — 7 из 7 ложных
RASTER = dict(rho_tol_m=0.02, gap_tol_m=0.06, cov_min=0.75, ang_tol=2.0, perp_tol=2.0)
CHAIR = dict(dens=3.0, span_v=0.2, span_u=(0.3, 1.0), off_u=0.3, div=2)
INTERIOR_MAX = 3.0             # м линии на м² внутри стола — больше: штриховка, стеллаж, короб
STROKE_MAX = 0.7               # штрихи PDF: нейтральные (серые и чёрные) не светлее 0,7 (24.09). Светлее — ключом `--stroke-max` из паспорта листа:
                               # клиент Б (мебель 0,81–0,84) при 0,9 — 171 стол против 168, клиент А 2 при 0,9 — 240 мест у стула против 261
BENCH_L_M = (1.9, 7.2)         # v012: бенч — прямоугольник глубины стола длиннее 1,9 м (до 7,2 м): делится по стульям у длинной стороны
SLOT_GAP_M = 0.12              #   стулья — комки линий в полосе 0,05–0,55 м, разделённые пустотой ≥ 0,12 м, шириной 0,3–1,0 м
SLOT_W_M = (0.3, 1.0)          #   «длинный стол на N стульев — N столов» (map/rules/61 §3.1); модуль L/N — 0,95–1,9 м, иначе не делится
# ---------------------------------------------------------------- перенесено из инструмента 24.09 (wpdet.py) без изменения порогов

# ---------------------------------------------------------------- geometry helpers
def seg_len(S):
    return np.hypot(S[:, 2] - S[:, 0], S[:, 3] - S[:, 1])

def seg_ang(S):
    return np.degrees(np.arctan2(S[:, 3] - S[:, 1], S[:, 2] - S[:, 0])) % 180.0

def unit(th):
    t = math.radians(th); return np.array([math.cos(t), math.sin(t)])

def merge_iv(ivs, gap):
    ivs = sorted(ivs); out = []
    for a, b in ivs:
        if out and a <= out[-1][1] + gap: out[-1][1] = max(out[-1][1], b)
        else: out.append([a, b])
    return out

_COVER_CACHE = {}


def cover(ivs, a, b):
    """доля [a, b], покрытая интервалами ivs (отсортированы, не перекрываются — merge_iv). v012: поиск первого интервала — bisect по концам
    (кэш по id списка): на этаже у линии сотни интервалов, а запросов — миллионы; результат тот же"""
    if b <= a: return 0.0
    key = id(ivs); ce = _COVER_CACHE.get(key)
    if ce is None or ce[0] is not ivs:
        ce = (ivs, [e for _, e in ivs]); _COVER_CACHE[key] = ce
        if len(_COVER_CACHE) > 200000: _COVER_CACHE.clear(); _COVER_CACHE[key] = ce
    ends = ce[1]; tot = 0.0
    for k in range(bisect.bisect_right(ends, a), len(ivs)):
        s, e = ivs[k]
        if s >= b: break
        lo, hi = max(s, a), min(e, b)
        if hi > lo: tot += hi - lo
    return tot / (b - a)

# ---------------------------------------------------------------- axis lines (dashed grid)
def axis_mask(S, upm, min_frac=0.75, rho_tol_m=0.02, loose=False):
    """Grid axes: collinear dashes of one or two repeating lengths running across nearly the whole drawing.
    Only the dash segments are marked — a wall or desk edge lying on the same line is kept."""
    L = seg_len(S); th = seg_ang(S); bad = np.zeros(len(S), bool)
    ext = max(S[:, [0, 2]].max() - S[:, [0, 2]].min(), S[:, [1, 3]].max() - S[:, [1, 3]].min())
    q_unit = 0.02 * upm
    for base in (0.0, 90.0):
        sel = np.where((adist(th, base) < 0.5) & (L > 0.05 * upm))[0]
        if not len(sel): continue
        d, n = unit(base), unit(base + 90)
        mid = (S[sel, :2] + S[sel, 2:]) / 2
        rho = mid @ n; order = np.argsort(rho)
        groups = []; cur = [order[0]]
        for a, b in zip(order[:-1], order[1:]):
            if rho[b] - rho[cur[0]] <= rho_tol_m * upm: cur.append(b)
            else: groups.append(cur); cur = [b]
        groups.append(cur)
        for g in groups:
            ids = sel[g]
            if len(ids) < 8: continue
            q = np.round(L[ids] / q_unit).astype(int)
            vals, cnts = np.unique(q, return_counts=True)
            top = vals[np.argsort(-cnts)][:2]
            dash = np.zeros(len(ids), bool)
            for t in top: dash |= np.abs(q - t) <= 1
            if loose:
                # raster: LSD cuts dashes at every crossing, so lengths do not repeat; many short pieces instead
                t0a = np.minimum(S[ids, :2] @ d, S[ids, 2:] @ d); t1a = np.maximum(S[ids, :2] @ d, S[ids, 2:] @ d)
                span_a = t1a.max() - t0a.min()
                if len(ids) >= 12 and (t1a - t0a).max() < 0.2 * span_a:
                    dash = np.ones(len(ids), bool)
            if dash.sum() < 8: continue
            dids = ids[dash]
            t0 = np.minimum(S[dids, :2] @ d, S[dids, 2:] @ d); t1 = np.maximum(S[dids, :2] @ d, S[dids, 2:] @ d)
            span = t1.max() - t0.min()
            covd = sum(b - a for a, b in merge_iv(list(zip(t0, t1)), 0))
            if span > min_frac * ext and covd / span < 0.9:
                bad[dids] = True
    return bad

# ---------------------------------------------------------------- dominant directions
def dir_peaks(S, upm, min_len_m=0.25, min_total_m=4.0, bin_deg=0.5, nms_deg=3.0):
    """Dominant directions of long segments: length-weighted histogram, non-maximum suppression within
    `nms_deg`, then refined to the length-weighted circular mean of the member segments."""
    L = seg_len(S); th = seg_ang(S)
    k = L >= min_len_m * upm
    nb = int(round(180 / bin_deg))
    h = np.zeros(nb)
    np.add.at(h, (np.floor(th[k] / bin_deg).astype(int)) % nb, L[k] / upm)
    hs = h + np.roll(h, 1) + np.roll(h, -1)
    cand = [i for i in range(nb) if hs[i] >= min_total_m and hs[i] >= hs[(i - 1) % nb] and hs[i] > hs[(i + 1) % nb]]
    cand.sort(key=lambda i: -hs[i])
    chosen = []
    for i in cand:
        p = (i + 0.5) * bin_deg
        if any(adist(p, q) < nms_deg for q in chosen): continue
        chosen.append(p)
    out = []
    for p in chosen:
        dth = adist(th[k], p)
        m = dth <= 2 * bin_deg
        a2 = np.radians(2 * th[k][m]); w = L[k][m]
        out.append((math.degrees(math.atan2((w * np.sin(a2)).sum(), (w * np.cos(a2)).sum())) / 2) % 180)
    return sorted(out)

def adist(a, b):
    x = np.abs(np.asarray(a) - b) % 180.0
    return np.minimum(x, 180.0 - x)

def lines_in_frame(S, theta_sel, ang_tol, ax_off, ax_t, rho_tol, gap_tol, min_len=0.0):
    """Collinear lines of segments with direction ~theta_sel: list of (offset along ax_off, merged intervals along ax_t)."""
    th = seg_ang(S); L = seg_len(S)
    idx = np.where((adist(th, theta_sel) <= ang_tol) & (L >= min_len))[0]
    if not len(idx): return []
    P0, P1 = S[idx, :2], S[idx, 2:]
    rho = ((P0 + P1) / 2) @ ax_off
    t0 = np.minimum(P0 @ ax_t, P1 @ ax_t); t1 = np.maximum(P0 @ ax_t, P1 @ ax_t)
    order = np.argsort(rho); out = []; cur = [order[0]]
    def flush(c):
        r = float(np.average(rho[c], weights=(t1[c] - t0[c]) + 1e-9))
        out.append((r, merge_iv(list(zip(t0[c], t1[c])), gap_tol)))
    for a, b in zip(order[:-1], order[1:]):
        if rho[b] - rho[cur[0]] <= rho_tol: cur.append(b)
        else: flush(cur); cur = [b]
    flush(cur)
    return out

def family(S, theta, ang_tol, rho_tol, gap_tol, min_len=0.0):
    return lines_in_frame(S, theta, ang_tol, unit(theta + 90), unit(theta), rho_tol, gap_tol, min_len)

# ---------------------------------------------------------------- rectangles with edge support
def find_rects(S, upm, L_rng=(0.95, 1.9), D_rng=(0.45, 0.95), cov_min=0.85, ang_tol=0.6, perp_tol=1.0,
               rho_tol_m=0.012, gap_tol_m=0.02, peaks=None):
    rho_tol, gap_tol, tol = rho_tol_m * upm, gap_tol_m * upm, 0.02 * upm
    peaks = dir_peaks(S, upm) if peaks is None else peaks
    rects = []
    done = set()
    for ia_, th in enumerate(peaks):
        jb = [j for j, t in enumerate(peaks) if adist(t, th + 90) <= perp_tol]
        if not jb:                                                       # v012: пик th + 90 подавлен соседним пиком (штриховка 88°) —
            if any(frozenset(x) == frozenset((ia_, -1)) for x in done): continue   # пара с самим th + 90
            jb = [-1]
        if frozenset((ia_, jb[0])) in done: continue
        done.add(frozenset((ia_, jb[0])))
        d, n = unit(th), unit(th + 90)
        A = lines_in_frame(S, th, ang_tol, n, d, rho_tol, gap_tol)          # lines v = const, intervals in u
        B = lines_in_frame(S, th + 90, ang_tol, d, n, rho_tol, gap_tol)     # lines u = const, intervals in v
        Bu = [b[0] for b in B]
        smin = min(L_rng[0], D_rng[0]) * upm; smax = max(L_rng[1], D_rng[1]) * upm
        for ia in range(len(A)):
            va, iva = A[ia]
            ea = (iva[0][0], iva[-1][1])
            for ib in range(ia + 1, len(A)):
                vb, ivb = A[ib]
                side = vb - va
                if side > smax: break
                if side < smin: continue
                eb = (ivb[0][0], ivb[-1][1])
                lo, hi = max(ea[0], eb[0]) - tol, min(ea[1], eb[1]) + tol
                if hi - lo < smin: continue
                k0, k1 = bisect.bisect_left(Bu, lo), bisect.bisect_right(Bu, hi)
                cands = [B[k][0] for k in range(k0, k1) if cover(B[k][1], va, vb) >= cov_min]
                for p in range(len(cands)):
                    for q in range(p + 1, len(cands)):
                        u1, u2 = cands[p], cands[q]; side2 = u2 - u1
                        Lm, Dm = max(side, side2) / upm, min(side, side2) / upm
                        if not (L_rng[0] <= Lm <= L_rng[1] and D_rng[0] <= Dm <= D_rng[1]): continue
                        if cover(iva, u1, u2) < cov_min or cover(ivb, u1, u2) < cov_min: continue
                        C = [u1 * d + va * n, u2 * d + va * n, u2 * d + vb * n, u1 * d + vb * n]
                        rects.append(dict(poly=[tuple(map(float, c)) for c in C], L=Lm, D=Dm,
                                          ang=(th if side2 >= side else th + 90) % 180))
    return dedupe(rects, 0.03 * upm)

def dedupe(rects, tol):
    out = []
    for r in rects:
        c = np.mean(r['poly'], axis=0)
        if any(np.hypot(*(c - np.mean(o['poly'], axis=0))) < tol and abs(r['L'] - o['L']) < 0.03 and abs(r['D'] - o['D']) < 0.03 for o in out):
            continue
        out.append(r)
    return out

# ---------------------------------------------------------------- maximal segments (for diagonals)
def maximal_segments(S, upm, ang_tol=0.8, rho_tol_m=0.012, gap_tol_m=0.03, min_len_m=0.1):
    """Merge collinear pieces into maximal segments; each merged line gets its own direction (total least squares)."""
    th = seg_ang(S); L = seg_len(S)
    keep = np.where(L >= 0.02 * upm)[0]
    order = keep[np.argsort(th[keep])]
    out = []
    i = 0
    gap = gap_tol_m * upm; rtol = rho_tol_m * upm
    while i < len(order):
        j = i
        while j + 1 < len(order) and th[order[j + 1]] - th[order[i]] <= 2 * ang_tol: j += 1
        grp = order[i:j + 1]
        tm = float(np.average(th[grp], weights=L[grp]))
        d, n = unit(tm), unit(tm + 90)
        P0, P1 = S[grp, :2], S[grp, 2:]
        rho = ((P0 + P1) / 2) @ n
        o = np.argsort(rho); clusters = []; cur = [o[0]]
        for a, b in zip(o[:-1], o[1:]):
            if rho[b] - rho[cur[0]] <= rtol: cur.append(b)
            else: clusters.append(cur); cur = [b]
        clusters.append(cur)
        for c in clusters:
            t0 = np.minimum(P0[c] @ d, P1[c] @ d); t1 = np.maximum(P0[c] @ d, P1[c] @ d)
            srt = np.argsort(t0); runs = []; cur_run = [srt[0]]; hi = t1[srt[0]]
            for k in srt[1:]:
                if t0[k] <= hi + gap: cur_run.append(k); hi = max(hi, t1[k])
                else: runs.append(cur_run); cur_run = [k]; hi = t1[k]
            runs.append(cur_run)
            for run in runs:
                ids = np.array(c)[run]
                pts = np.vstack([P0[ids], P1[ids]])
                ctr = pts.mean(axis=0)
                if len(ids) == 1:
                    dd = P1[ids[0]] - P0[ids[0]]; dd = dd / np.linalg.norm(dd)
                else:
                    _, _, vt = np.linalg.svd(pts - ctr); dd = vt[0]
                pr = (pts - ctr) @ dd
                if pr.max() - pr.min() >= min_len_m * upm:
                    p, q = ctr + pr.min() * dd, ctr + pr.max() * dd
                    out.append((p[0], p[1], q[0], q[1]))
        i = j + 1
    return np.array(out) if out else np.zeros((0, 4))


def diag_candidates(S, upm, ang_tol=1.0, rho_tol_m=0.015, piece_gap_m=0.02, join_gap_m=0.1, min_piece_m=0.15):
    """Pieces of straight lines, plus every pair of consecutive collinear pieces joined over a gap up to
    `join_gap_m` (raster: LSD breaks a diagonal where the other one crosses it). Longer chains are not built,
    so a diagonal running on through the next rectangle of a grid does not swallow its neighbour."""
    Pc = maximal_segments(S, upm, ang_tol=ang_tol, rho_tol_m=rho_tol_m, gap_tol_m=piece_gap_m, min_len_m=min_piece_m)
    if not len(Pc): return Pc
    th = seg_ang(Pc); out = [tuple(p) for p in Pc]
    order = np.argsort(th); i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and th[order[j + 1]] - th[order[i]] <= 2 * ang_tol: j += 1
        grp = order[i:j + 1]
        tm = float(np.mean(th[grp])); d, n = unit(tm), unit(tm + 90)
        rho = ((Pc[grp, :2] + Pc[grp, 2:]) / 2) @ n
        t0 = np.minimum(Pc[grp, :2] @ d, Pc[grp, 2:] @ d); t1 = np.maximum(Pc[grp, :2] @ d, Pc[grp, 2:] @ d)
        o = np.argsort(rho); cl = []; cur = [o[0]]
        for a, b in zip(o[:-1], o[1:]):
            if rho[b] - rho[cur[0]] <= rho_tol_m * upm: cur.append(b)
            else: cl.append(cur); cur = [b]
        cl.append(cur)
        for c in cl:
            c = sorted(c, key=lambda q: t0[q])
            for a_, b_ in zip(c[:-1], c[1:]):
                gap = t0[b_] - t1[a_]
                if -0.01 * upm <= gap <= join_gap_m * upm:
                    ia, ib = grp[a_], grp[b_]
                    pa = Pc[ia, :2] if (Pc[ia, :2] @ d) < (Pc[ia, 2:] @ d) else Pc[ia, 2:]
                    pb = Pc[ib, 2:] if (Pc[ib, 2:] @ d) > (Pc[ib, :2] @ d) else Pc[ib, :2]
                    out.append((pa[0], pa[1], pb[0], pb[1]))
        i = j + 1
    return np.array(out)

# ---------------------------------------------------------------- crossed rectangles
def find_crossed(S, upm, L_rng=(0.95, 1.9), D_rng=(0.45, 0.95), mid_tol=0.03, len_tol=0.04, support=None,
                 slack=1.0, snap=None, merge=None, final_slack=1.0):
    """Schematic desk = rectangle with both diagonals. Pair maximal segments of equal length crossing at their
    midpoints; the rectangle is built on the symmetry axes of the X. `slack` < 1 accepts X shorter than the frame
    (raster: LSD stops short of the corners); `snap` then moves the edges onto the frame lines."""
    M = diag_candidates(S, upm, **merge) if merge is not None else maximal_segments(S, upm)
    if not len(M): return []
    L = seg_len(M)
    dmin = math.hypot(L_rng[0], D_rng[0]) * upm * 0.97 * slack; dmax = math.hypot(L_rng[1], D_rng[1]) * upm * 1.03
    k = np.where((L >= dmin) & (L <= dmax))[0]
    if len(k) < 2: return []
    mids = (M[k, :2] + M[k, 2:]) / 2
    from scipy.spatial import cKDTree
    T = cKDTree(mids)
    out = []
    for a, b in T.query_pairs(mid_tol * dmax):
        i, j = k[a], k[b]
        if abs(L[i] - L[j]) > len_tol * max(L[i], L[j]): continue
        if np.hypot(*(mids[a] - mids[b])) > mid_tol * L[i]: continue
        d1 = (M[i, 2:] - M[i, :2]) / L[i]; d2 = (M[j, 2:] - M[j, :2]) / L[j]
        if abs(d1 @ d2) > math.cos(math.radians(20)): continue
        if d1 @ d2 < 0: d2 = -d2
        a1 = d1 + d2; a1 /= np.linalg.norm(a1); a2 = d1 - d2; a2 /= np.linalg.norm(a2)
        pts = np.array([M[i, :2], M[i, 2:], M[j, :2], M[j, 2:]]); c = pts.mean(axis=0)
        h1 = np.abs((pts - c) @ a1).mean(); h2 = np.abs((pts - c) @ a2).mean()
        if h1 < h2: a1, a2, h1, h2 = a2, a1, h2, h1                   # a1 = long axis
        P = [c - a1 * h1 - a2 * h2, c + a1 * h1 - a2 * h2, c + a1 * h1 + a2 * h2, c - a1 * h1 + a2 * h2]
        Lm, Dm = 2 * h1 / upm, 2 * h2 / upm
        if not (L_rng[0] * slack <= Lm <= L_rng[1] and D_rng[0] * slack <= Dm <= D_rng[1]): continue
        r = dict(poly=[tuple(map(float, p)) for p in P], L=Lm, D=Dm, ang=math.degrees(math.atan2(a1[1], a1[0])) % 180)
        if snap is not None:
            r = snap(r)
            if not (L_rng[0] * final_slack <= r['L'] <= L_rng[1] and D_rng[0] * final_slack <= r['D'] <= D_rng[1]): continue
            _, uu, _, _, _ = rect_frame(r); r['ang'] = math.degrees(math.atan2(uu[1], uu[0])) % 180
        if support is not None:
            Q = r['poly']; r['frame_support'] = min(support(Q[m], Q[(m + 1) % 4]) for m in range(4))
        out.append(r)
    return dedupe(out, 0.03 * upm)

# ---------------------------------------------------------------- edge support and ink bands
class SegIndex:
    def __init__(self, S):
        self.S = S
        self.G = [LineString([(s[0], s[1]), (s[2], s[3])]) for s in S]
        self.tree = STRtree(self.G)
        self.th = seg_ang(S)

    def support(self, p, q, tol, ang_tol=3.0):
        p, q = np.asarray(p, float), np.asarray(q, float)
        e = LineString([p, q]); L = e.length
        if L == 0: return 0.0
        d = (q - p) / L; th = math.degrees(math.atan2(d[1], d[0])) % 180
        ivs = []
        for i in self.tree.query(e.buffer(tol)):
            if min(abs(self.th[i] - th), 180 - abs(self.th[i] - th)) > ang_tol: continue
            s = self.S[i]
            if e.distance(self.G[i]) > tol: continue
            a, b = (np.array(s[:2]) - p) @ d, (np.array(s[2:]) - p) @ d
            ivs.append((max(0, min(a, b)), min(L, max(a, b))))
        return cover(merge_iv([iv for iv in ivs if iv[1] > iv[0]], 0), 0, L)

    def ink(self, poly):
        """Length of line inside a polygon and its centroid."""
        tot = 0.0; cx = cy = 0.0
        for i in self.tree.query(poly):
            g = self.G[i].intersection(poly)
            if g.is_empty: continue
            ln = g.length
            if ln <= 0: continue
            c = g.centroid; tot += ln; cx += c.x * ln; cy += c.y * ln
        return tot, ((cx / tot, cy / tot) if tot > 0 else None)

def rect_frame(r):
    """Centre, unit vector along the long side, unit normal, half-length, half-depth."""
    P = np.array(r['poly']); c = P.mean(axis=0)
    e1, e2 = P[1] - P[0], P[2] - P[1]
    if np.linalg.norm(e1) >= np.linalg.norm(e2): du, dv = e1, e2
    else: du, dv = e2, e1
    hl, hd = np.linalg.norm(du) / 2, np.linalg.norm(dv) / 2
    return c, du / (2 * hl), dv / (2 * hd), hl, hd

def band(r, side, upm, near_m=0.05, far_m=0.55, frac=0.8):
    c, u, v, hl, hd = rect_frame(r)
    s = 1 if side > 0 else -1
    a, b = hd + near_m * upm, hd + far_m * upm
    w = hl * frac
    pts = [c + s * v * a - u * w, c + s * v * a + u * w, c + s * v * b + u * w, c + s * v * b - u * w]
    return Polygon([tuple(p) for p in pts])

def free_distance(r, side, upm, room, obstacles, reach_m=1.5, frac=0.6, step_m=0.05):
    """Free floor in front of one long side: march outwards in thin slices while the slice is inside the room
    and does not run into another piece of furniture."""
    from shapely.prepared import prep
    c, u, v, hl, hd = rect_frame(r)
    s = 1 if side > 0 else -1
    w = hl * frac
    room_ok = room.buffer(0.03 * upm)
    obst = [prep(g) for g in obstacles]
    obst_g = obstacles
    dist = 0.0
    while dist < reach_m - 1e-9:
        a, b = hd + (dist + 0.005) * upm, hd + (dist + step_m) * upm
        sl = Polygon([tuple(c + s * v * a - u * w), tuple(c + s * v * a + u * w), tuple(c + s * v * b + u * w), tuple(c + s * v * b - u * w)])
        if sl.intersection(room_ok).area < 0.8 * sl.area: break
        hit = False
        for pg, g in zip(obst, obst_g):
            if pg.intersects(sl) and g.intersection(sl).area > 0.1 * sl.area: hit = True; break
        if hit: break
        dist += step_m
    return dist

def atomic(rects, upm):
    """Drop a rectangle that is subdivided by another desk-size rectangle inside it (desk + printer box, etc.)."""
    P = [Polygon(r['poly']) for r in rects]
    keep = []
    for i, R in enumerate(P):
        Rb = R.buffer(0.02 * upm)
        if any(j != i and P[j].area < 0.9 * R.area and Rb.contains(P[j]) for j in range(len(P))): continue
        keep.append(rects[i])
    return keep

def snap_rect(r, idx, upm, max_shift_m=0.1, step_m=0.0025, tol_m=0.008):
    """Move each edge along its normal to the offset with the best line support (raster: LSD stops short of corners,
    strokes have two edges). Returns a new rectangle dict."""
    c, u, v, hl, hd = rect_frame(r)
    shifts = np.arange(-max_shift_m, max_shift_m + 1e-9, step_m) * upm
    def best(axis, half, other_axis, other_half, sign):
        sc = []
        for sh in shifts:
            h = half + sh
            p = c + sign * axis * h - other_axis * other_half * 0.9; q = c + sign * axis * h + other_axis * other_half * 0.9
            sc.append(idx.support(p, q, tol=max(tol_m * upm, 1.0), ang_tol=4.0))
        sc = np.array(sc)
        if sc.max() < 0.5: return half
        good = sc >= sc.max() - 0.05
        # contiguous blocks of well-supported offsets; take the block nearest to the current edge, use its centre
        blocks = []; cur = None
        for k, g_ in enumerate(good):
            if g_ and cur is None: cur = [k, k]
            elif g_: cur[1] = k
            elif cur is not None: blocks.append(cur); cur = None
        if cur is not None: blocks.append(cur)
        def dist(b):
            lo, hi = shifts[b[0]], shifts[b[1]]
            return 0.0 if lo <= 0 <= hi else min(abs(lo), abs(hi))
        near = min(blocks, key=dist)
        lo, hi = shifts[near[0]], shifts[near[1]]
        return half + (0.0 if lo <= 0 <= hi else (lo if abs(lo) < abs(hi) else hi))
    hv_p = best(v, hd, u, hl, +1); hv_m = best(v, hd, u, hl, -1)
    hu_p = best(u, hl, v, hd, +1); hu_m = best(u, hl, v, hd, -1)
    cc = c + v * (hv_p - hv_m) / 2 + u * (hu_p - hu_m) / 2
    HL, HD = (hu_p + hu_m) / 2, (hv_p + hv_m) / 2
    P = [cc - u * HL - v * HD, cc + u * HL - v * HD, cc + u * HL + v * HD, cc - u * HL + v * HD]
    o = dict(r); o['poly'] = [tuple(map(float, p)) for p in P]
    o['L'], o['D'] = max(HL, HD) * 2 / upm, min(HL, HD) * 2 / upm
    return o

# ---------------------------------------------------------------- crossed rectangles, robust to broken diagonals
def find_crossed_robust(S, upm, idx, L_rng=(0.95, 1.9), D_rng=(0.45, 0.95), merge=None, min_arm_m=0.2,
                        sup_tol_m=0.02, min_edge_support=0.6, final_slack=0.95):
    """Raster: LSD often breaks or shortens a diagonal, so lengths and midpoints are unreliable. Here an X is
    two candidate diagonals that physically cross, each reaching at least `min_arm_m` on both sides of the
    crossing. The half-diagonal h (the same for both diagonals of a rectangle) is then found by maximising the
    support of the four frame edges c ± h·d1, c ± h·d2."""
    M = diag_candidates(S, upm, **(merge or {}))
    if not len(M): return []
    L = seg_len(M)
    k = np.where(L >= 2 * min_arm_m * upm)[0]
    G = [LineString([(M[i, 0], M[i, 1]), (M[i, 2], M[i, 3])]) for i in k]
    tree = STRtree(G)
    hmin = 0.5 * math.hypot(L_rng[0], D_rng[0]) * final_slack; hmax = 0.5 * math.hypot(L_rng[1], D_rng[1])
    seen = []; out = []
    tol = sup_tol_m * upm
    def rect_score(c, d1, d2, h):
        P = [c + h * d1, c + h * d2, c - h * d1, c - h * d2]
        sc = [idx.support(P[m], P[(m + 1) % 4], tol=tol, ang_tol=4.0) for m in range(4)]
        return min(sc), float(np.mean(sc)), P
    for a in range(len(k)):
        for b in tree.query(G[a]):
            if b <= a: continue
            i, j = k[a], k[b]
            d1 = (M[i, 2:] - M[i, :2]) / L[i]; d2 = (M[j, 2:] - M[j, :2]) / L[j]
            if abs(d1 @ d2) > math.cos(math.radians(20)): continue
            x = G[a].intersection(G[b])
            if x.is_empty or x.geom_type != 'Point': continue
            c = np.array([x.x, x.y])
            ti = (c - M[i, :2]) @ d1; tj = (c - M[j, :2]) @ d2
            arm = min(ti, L[i] - ti, tj, L[j] - tj)
            if arm < min_arm_m * upm: continue
            if any(np.hypot(*(c - q)) < 0.05 * upm for q in seen): continue
            # coarse-to-fine search of the half-diagonal
            best = (-1, -1, None, None)
            for h in np.arange(hmin, hmax + 1e-9, 0.02) * upm:
                mn, mean, P = rect_score(c, d1, d2, h)
                if mean > best[1]: best = (mn, mean, P, h)
            h0 = best[3]
            for h in np.arange(h0 - 0.02 * upm, h0 + 0.02 * upm + 1e-9, 0.0025 * upm):
                mn, mean, P = rect_score(c, d1, d2, h)
                if mean > best[1] + 1e-9 or (abs(mean - best[1]) < 1e-9 and h < best[3]): best = (mn, mean, P, h)
            mn, mean, P, h = best
            if mn < min_edge_support: continue
            e1, e2 = np.hypot(*(P[1] - P[0])), np.hypot(*(P[2] - P[1]))
            Lm, Dm = max(e1, e2) / upm, min(e1, e2) / upm
            if not (L_rng[0] * final_slack <= Lm <= L_rng[1] and D_rng[0] * final_slack <= Dm <= D_rng[1]): continue
            long_edge = (P[0], P[1]) if e1 >= e2 else (P[1], P[2])
            ang = math.degrees(math.atan2(long_edge[1][1] - long_edge[0][1], long_edge[1][0] - long_edge[0][0])) % 180
            seen.append(c)
            out.append(dict(poly=[tuple(map(float, p)) for p in P], L=Lm, D=Dm, ang=ang, frame_support=mn))
    return dedupe(out, 0.03 * upm)

# ---------------------------------------------------------------- chair features (chairfeat.py, 24.09)
def band_features(idx, r, side, upm, room):
    """Ink in the band next to one long side, clipped to the room: density, direction diversity, span, centre offset."""
    B = band(r, side, upm); Bc = B.intersection(room)
    if Bc.is_empty or Bc.area < 0.5 * B.area: return None
    c, u, v, hl, hd = rect_frame(r)
    tot = 0.0; hist = np.zeros(8); us, vs, ws = [], [], []
    for i in idx.tree.query(Bc):
        g = idx.G[i].intersection(Bc)
        if g.is_empty or g.length <= 0: continue
        ln = g.length; tot += ln
        hist[int((idx.th[i] % 180) // 22.5) % 8] += ln
        for part in getattr(g, 'geoms', [g]):
            for p in part.coords:
                us.append((np.array(p) - c) @ u); vs.append(abs((np.array(p) - c) @ v)); ws.append(ln)
    if tot == 0: return dict(dens=0.0, div=0, span_u=0, span_v=0, off_u=0, cen=None)
    us, vs = np.array(us), np.array(vs)
    div = int((hist / tot >= 0.08).sum())
    cu = float(np.average(us, weights=ws)); cv = float(np.average(vs, weights=ws))
    cen = c + cu * u + (1 if side > 0 else -1) * cv * v
    return dict(dens=tot / upm / (Bc.area / upm ** 2), div=div, span_u=(us.max() - us.min()) / upm,
                span_v=(vs.max() - vs.min()) / upm, off_u=abs(cu) / (2 * hl), cen=(float(cen[0]), float(cen[1])))

def interior_density(idx, r, upm, inset_m=0.05):
    P = Polygon(r['poly']).buffer(-inset_m * upm, join_style=2)
    if P.is_empty: return 0.0
    ln, _ = idx.ink(P)
    return ln / upm / (P.area / upm ** 2)


# ================================================================ v012: плитки для целого листа
TILE_M = 10.0                  # v012: целый этаж — плитками 10 × 10 м с перекрытием 2,5 м (больше стола 1,9 м): find_rects на листе 2 × 1 м
TILE_OVERLAP_M = 2.5           #   (фотостудия) и на этаже 60 м с 2 000 линий одного направления (клиент А 2) — одна и та же процедура


def clip_segments(S, x0, y0, x1, y1):
    """отрезки, обрезанные прямоугольником (Лианг — Барски); вне — выброшены"""
    P0, d = S[:, :2], S[:, 2:] - S[:, :2]; t0 = np.zeros(len(S)); t1 = np.ones(len(S)); ok = np.ones(len(S), bool)
    for p, q in ((-d[:, 0], P0[:, 0] - x0), (d[:, 0], x1 - P0[:, 0]), (-d[:, 1], P0[:, 1] - y0), (d[:, 1], y1 - P0[:, 1])):
        par = np.abs(p) < 1e-12; ok &= ~(par & (q < 0))
        with np.errstate(divide='ignore', invalid='ignore'):
            r = np.where(par, 0, q / np.where(par, 1, p))
        t0 = np.where(~par & (p < 0), np.maximum(t0, r), t0); t1 = np.where(~par & (p > 0), np.minimum(t1, r), t1)
    ok &= t0 < t1
    A = P0 + d * t0[:, None]; B = P0 + d * t1[:, None]
    return np.c_[A, B][ok]


def find_rects_tiled(S, upm, tile_m=TILE_M, overlap_m=TILE_OVERLAP_M, peaks=None, **kw):
    """find_rects по плиткам (линия, идущая через весь этаж, — локальна в плитке); дубли на перекрытии — dedupe"""
    if not len(S): return []
    peaks = dir_peaks(S, upm) if peaks is None else peaks
    X0, Y0 = S[:, [0, 2]].min(), S[:, [1, 3]].min(); X1, Y1 = S[:, [0, 2]].max(), S[:, [1, 3]].max()
    step = (tile_m - overlap_m) * upm; size = tile_m * upm; out = []
    if X1 - X0 <= size and Y1 - Y0 <= size:
        return find_rects(S, upm, peaks=peaks, **kw)
    for y in np.arange(Y0, max(Y1 - overlap_m * upm, Y0 + 1), step):
        for x in np.arange(X0, max(X1 - overlap_m * upm, X0 + 1), step):
            T = clip_segments(S, x, y, x + size, y + size)
            T = T[seg_len(T) > 1e-6]
            if len(T) < 4: continue
            pk = dir_peaks(T, upm)                                   # направления — свои у плитки (у этажа их десятки: дуги, штриховки)
            if pk:
                out += find_rects(T, upm, peaks=pk, **kw)
    return dedupe(out, 0.03 * upm)


# ================================================================ v012: вход и выход кода карты
def is_chair(f):
    return (f is not None and f['dens'] >= CHAIR['dens'] and f['span_v'] >= CHAIR['span_v'] and
            CHAIR['span_u'][0] <= f['span_u'] <= CHAIR['span_u'][1] and f['off_u'] <= CHAIR['off_u'] and f['div'] >= CHAIR['div'])


def iou(P, Q):
    u = P.union(Q).area
    return P.intersection(Q).area / u if u else 0.0


def dedupe_iou(R, key, thr=0.75):
    """почти одинаковые прямоугольники (стол и тот же стол, замкнутый линией стены) — один, лучший по key"""
    R = sorted(R, key=key); keep = []
    for r in R:
        P = Polygon(r['poly'])
        if any(iou(P, Polygon(o['poly'])) > thr for o in keep): continue
        keep.append(r)
    return keep


def _bez(p0, p1, p2, p3, n=6):
    t = np.linspace(0, 1, n + 1)[:, None]
    P = (1 - t) ** 3 * np.array(p0) + 3 * (1 - t) ** 2 * t * np.array(p1) + 3 * (1 - t) * t ** 2 * np.array(p2) + t ** 3 * np.array(p3)
    return [(P[i][0], P[i][1], P[i + 1][0], P[i + 1][1]) for i in range(n)]


def pdf_segments(pdf, page_no, to_pixels, stroke_max=STROKE_MAX, clip=None, fills=False):
    """штрихи страницы PDF -> отрезки (N × 4) в px work.png: нейтральные чёрные и серые (как инструмент 24.09); to_pixels — intake.json.
    v012: fills — и контуры нейтральных заливок без обводки (ключом: у клиент Б заливка мебели — тысячи мелких кусков, внутри стола их
    контуры дают «штриховку» — стол уходит в plain)"""
    import pymupdf
    doc = pymupdf.open(pdf); pg = doc[page_no - 1]; a, b, c, d, e, f = to_pixels
    S = []
    for dr in pg.get_drawings():
        sc = dr.get('color')
        if (sc is None or len(sc) < 3) and fills and dr.get('fill') is not None and len(dr['fill']) >= 3:
            sc = dr['fill']                                              # контур заливки — как штрих её цвета
        if sc is None or len(sc) < 3: continue
        r_, g_, b_ = sc[:3]
        if not (abs(r_ - g_) < 0.02 and abs(g_ - b_) < 0.02 and r_ <= stroke_max): continue
        for it in dr.get('items', []):
            k = it[0]
            if k == 'l': S.append((it[1].x, it[1].y, it[2].x, it[2].y))
            elif k == 're':
                R = it[1]; S += [(R.x0, R.y0, R.x1, R.y0), (R.x1, R.y0, R.x1, R.y1), (R.x1, R.y1, R.x0, R.y1), (R.x0, R.y1, R.x0, R.y0)]
            elif k == 'qu':
                q = it[1]; P = [q.ul, q.ur, q.lr, q.ll]; S += [(P[i].x, P[i].y, P[(i + 1) % 4].x, P[(i + 1) % 4].y) for i in range(4)]
            elif k == 'c':
                S += _bez(*[(p.x, p.y) for p in it[1:5]])
    S = np.array(S, float).reshape(-1, 4)
    if not len(S): return S
    X0 = a * S[:, 0] + c * S[:, 1] + e; Y0 = b * S[:, 0] + d * S[:, 1] + f
    X1 = a * S[:, 2] + c * S[:, 3] + e; Y1 = b * S[:, 2] + d * S[:, 3] + f
    S = np.c_[X0, Y0, X1, Y1]
    S = S[seg_len(S) > 1e-6]
    R = np.round(S, 1); sw = (R[:, 0] > R[:, 2]) | ((R[:, 0] == R[:, 2]) & (R[:, 1] > R[:, 3]))      # одинаковые отрезки — один
    R[sw] = R[sw][:, [2, 3, 0, 1]]; S = np.unique(R, axis=0)
    if clip is not None:
        x0, y0, x1, y1 = clip; m = ((S[:, [0, 2]].mean(1) >= x0) & (S[:, [0, 2]].mean(1) <= x1) & (S[:, [1, 3]].mean(1) >= y0) & (S[:, [1, 3]].mean(1) <= y1))
        S = S[m]
    return S


def lsd_segments(gray, min_len_px=3, tile=600, overlap=120):
    """LSD плитками: LSD судит отрезок по размеру всей картинки — на большом плане теряет короткие куски (24.09)"""
    import cv2
    lsd = cv2.createLineSegmentDetector(cv2.LSD_REFINE_STD)
    H, Wd = gray.shape; out = []; step = tile - overlap
    for y in range(0, max(H - overlap, 1), step):
        for x in range(0, max(Wd - overlap, 1), step):
            t = gray[y:y + tile, x:x + tile]
            if t.min() > 200: continue
            lines = lsd.detect(t)[0]
            if lines is None: continue
            S = lines.reshape(-1, 4).astype(float); S[:, [0, 2]] += x; S[:, [1, 3]] += y; out.append(S)
    if not out: return np.zeros((0, 4))
    S = np.vstack(out)
    return S[seg_len(S) >= min_len_px]


def edge_multiplicity(gray, S):
    from skimage.morphology import skeletonize
    sk = skeletonize(gray < 160).sum()
    return max(1.0, float(seg_len(S).sum()) / max(sk, 1))


def _room_of(poly, rooms):
    """помещение стола: наибольшая доля площади стола; rooms — [Polygon] или None (тогда — весь лист)"""
    P = Polygon(poly)
    if not rooms: return None, 1.0
    best = (None, 0.0)
    for Q in rooms:
        if not Q.intersects(P): continue
        a = Q.intersection(P).area / P.area
        if a > best[1]: best = (Q, a)
    return best


def chair_slots(idx, r, side, upm, room, mult=1.0, bin_m=0.02):
    """v012: стулья вдоль длинной стороны бенча — комки линий в полосе 0,05–0,55 м по всей длине (обрезанной помещением): проекция длины линий
    на ось стола, комки через пустоту ≥ SLOT_GAP_M, ширина SLOT_W_M, плотность ≥ CHAIR dens -> [(центр вдоль оси, м; точка стула)]"""
    B = band(r, side, upm, frac=1.0); Bc = B.intersection(room) if room is not None else B
    if Bc.is_empty or Bc.area < 0.5 * B.area: return []
    c, u, v, hl, hd = rect_frame(r); nb = int(2 * hl / (bin_m * upm)) + 1; h = np.zeros(nb); vv = np.zeros(nb)
    A, B = [], []
    for i in idx.tree.query(Bc):
        g = idx.G[i].intersection(Bc)
        if g.is_empty or g.length <= 0: continue
        for part in getattr(g, 'geoms', [g]):
            P = np.asarray(part.coords)
            if len(P) >= 2: A.append(P[:-1]); B.append(P[1:])
    if A:                                                                # отрезки -> точки через полкорзины (векторно)
        A, B = np.vstack(A), np.vstack(B); L = np.hypot(*(B - A).T); n = np.maximum(2, (L / (bin_m * upm / 2)).astype(int) + 1)
        idx_ = np.repeat(np.arange(len(A)), n); t = (np.arange(n.sum()) - np.repeat(np.cumsum(n) - n, n)) / np.repeat(n - 1, n)
        Q = A[idx_] + (B[idx_] - A[idx_]) * t[:, None]; w = (L / n)[idx_]
        k = (((Q - c) @ u + hl) / (bin_m * upm)).astype(int); ok = (k >= 0) & (k < nb)
        np.add.at(h, k[ok], w[ok]); np.add.at(vv, k[ok], (np.abs((Q - c) @ v) * w)[ok])
    on = h > 0; gap = int(round(SLOT_GAP_M / bin_m)); out = []; k = 0
    while k < nb:
        if not on[k]: k += 1; continue
        j = k; last = k
        while j + 1 < nb and (on[j + 1] or (j + 1 - last) <= gap):
            j += 1
            if on[j]: last = j
        w = (last - k + 1) * bin_m; ink = h[k:last + 1].sum() / upm / mult
        if SLOT_W_M[0] <= w <= SLOT_W_M[1] and ink / (w * 0.5) >= CHAIR['dens']:
            cu = (np.average(np.arange(k, last + 1), weights=h[k:last + 1] + 1e-9) + 0.5) * bin_m * upm - hl
            cv = vv[k:last + 1].sum() / max(h[k:last + 1].sum(), 1e-9)
            out.append((cu / upm, tuple(c + cu * u + (1 if side > 0 else -1) * cv * v)))
        k = last + 1
    return out


def split_bench(r, slots, upm):
    """бенч -> N модулей по стульям одной стороны: модуль L/N, место — стул своего модуля"""
    c, u, v, hl, hd = rect_frame(r); N = len(slots); out = []
    for i in range(N):
        m = c + u * (-hl + 2 * hl * (i + 0.5) / N); w = hl / N
        P = [m - u * w - v * hd, m + u * w - v * hd, m + u * w + v * hd, m - u * w + v * hd]
        mid = (-hl + 2 * hl * (i + 0.5) / N) / upm
        s = min(slots, key=lambda q: abs(q[0] - mid))
        out.append(dict(poly=[tuple(map(float, p)) for p in P], L=2 * w / upm, D=2 * hd / upm, seat=s[1], seat_confidence='bench', kind='drawn', interior=0.0))
    return out


def detect(S, upm, rooms=None, raster=False, mult=1.0, room_in=0.9, axis=True, log=print):
    """отрезки (px) и px/м -> (столы с местом, кресты-стеллажи, прямоугольники без стула, сводка); rooms — помещения в px или None"""
    ax = axis_mask(S, upm, loose=raster) if axis and len(S) else np.zeros(len(S), bool)
    S = S[~ax]
    info = dict(segments=int(len(S)), axis_removed=int(ax.sum()))
    if len(S) < 4:
        log('по линиям: ВНИМАНИЕ — отрезков нет (%d) — линии не дали ни одного стола' % len(S)); return [], [], [], dict(info, rects=0, crossed=0)
    idx = SegIndex(S)
    if raster:
        peaks = dir_peaks(S, upm)
        rects = atomic(find_rects_tiled(S, upm, L_rng=(0.95, BENCH_L_M[1]), cov_min=RASTER['cov_min'], ang_tol=RASTER['ang_tol'], perp_tol=RASTER['perp_tol'],
                                        rho_tol_m=RASTER['rho_tol_m'], gap_tol_m=RASTER['gap_tol_m'], peaks=peaks), upm)
        crossed = find_crossed_robust(S, upm, idx, merge=dict(ang_tol=1.0, rho_tol_m=0.015, piece_gap_m=0.02, join_gap_m=0.1))
        cmin = 0.5
    else:
        rects = atomic(find_rects_tiled(S, upm, L_rng=(0.95, BENCH_L_M[1]), peaks=dir_peaks(S, upm)), upm)
        crossed = find_crossed(S, upm, support=lambda p, q: idx.support(p, q, tol=0.03 * upm)); cmin = 0.6
    info.update(rects=len(rects), crossed=len(crossed))
    big = box(*S[:, :2].min(0), *S[:, :2].max(0)).buffer(upm) if not rooms else None
    X = []
    for r in crossed:
        Q, a = _room_of(r['poly'], rooms)
        if a < room_in or r.get('frame_support', 1) < cmin: continue
        r.update(kind='crossed'); X.append(r)
    Xp = [Polygon(r['poly']) for r in X]
    D, plain, nb = [], [], 0
    for r in rects:
        P = Polygon(r['poly'])
        if any(P.intersection(Q).area > 0.5 * min(P.area, Q.area) for Q in Xp): continue
        Q, a = _room_of(r['poly'], rooms)
        if a < room_in: continue
        Q = Q if Q is not None else big
        if r['L'] > BENCH_L_M[0]:                                        # v012: бенч — по стульям длинной стороны
            if interior_density(idx, r, upm) / mult > INTERIOR_MAX: plain.append(r); continue
            sl = [chair_slots(idx, r, s, upm, Q, mult) for s in (+1, -1)]
            k = int(np.argmax([len(x) for x in sl])); N = len(sl[k])
            if N >= 2 and 0.95 <= r['L'] / N <= 1.9:
                D += split_bench(r, sl[k], upm); nb += 1
            else:
                plain.append(r)
            continue
        r['interior'] = round(interior_density(idx, r, upm) / mult, 2)
        f = [band_features(idx, r, s, upm, Q) for s in (+1, -1)]
        for x in f:
            if x is not None: x['dens'] /= mult
        ok = [is_chair(x) for x in f]
        if r['interior'] > INTERIOR_MAX or not any(ok):
            plain.append(r); continue
        best = int(np.argmax([x['dens'] for x in f])) if all(ok) else ok.index(True)
        r.update(kind='drawn', seat=f[best]['cen'], seat_side=(+1, -1)[best], seat_confidence='low' if all(ok) else 'high')
        D.append(r)
    D = dedupe_iou(D, key=lambda r: (r['interior'], Polygon(r['poly']).area))
    X = dedupe_iou(X, key=lambda r: Polygon(r['poly']).area)
    info.update(desks=len(D), benches=nb, crossed_kept=len(X), plain=len(plain), rooms_clip=bool(rooms))
    if not rooms:
        log('по линиям: помещений нет — полоса стула не обрезана по помещению (стул за стеной возможен — сверка глазами)')
    if not D:
        log('по линиям: ВНИМАНИЕ — линии не дали ни одного стола со стулом (прямоугольников размера стола %d, без стула %d, крестов %d)'
            % (len(rects), len(plain), len(X)))
    return D, X, plain, info


def detect_raster(gray, px_per_m, rooms=None, log=print):
    """растр -> места: приведение к ≈ 100 px/м, LSD плитками, тот же поиск с допусками растра; координаты — в px входного растра"""
    import cv2
    k = 1.0
    if px_per_m < RASTER_PPM_MIN:
        log('по линиям (растр): ВНИМАНИЕ — %.0f px/м ниже проверенного (54 px/м на пробе 24.09): найденное — только кандидаты, на s124 «12» '
            '(23 px/м) все 7 — ложные (кабины, шкафы); места — вручную, сверка глазами' % px_per_m)
    if not (RASTER_PPM_RANGE[0] <= px_per_m <= RASTER_PPM_RANGE[1]):
        k = RASTER_PPM / px_per_m
        gray = cv2.resize(gray, (max(1, int(round(gray.shape[1] * k))), max(1, int(round(gray.shape[0] * k)))),
                          interpolation=cv2.INTER_AREA if k < 1 else cv2.INTER_CUBIC)
        log('по линиям (растр): растр приведён к %.0f px/м (×%.3f) — разрешение пробы 24.09' % (RASTER_PPM, k))
    upm = px_per_m * k
    S = lsd_segments(gray); mult = edge_multiplicity(gray, S) if len(S) else 1.0
    R = [Polygon(np.asarray(Q.exterior.coords) * k) for Q in rooms] if rooms else None
    if R:
        from shapely.ops import unary_union
        from shapely.prepared import prep
        inside = prep(unary_union(R).buffer(0.1 * upm))
        keep = np.array([inside.contains(Point((s[0] + s[2]) / 2, (s[1] + s[3]) / 2)) for s in S], bool) if len(S) else np.zeros(0, bool)
        S = S[keep]
    D, X, plain, info = detect(S, upm, R, raster=True, mult=mult, log=log)
    back = lambda r: dict(r, poly=[(x / k, y / k) for x, y in r['poly']], **({'seat': (r['seat'][0] / k, r['seat'][1] / k)} if r.get('seat') else {}))
    info.update(edge_multiplicity=round(mult, 2), raster_scale=round(k, 4))
    log('по линиям (растр): столов со стулом %d, крестов %d, без стула %d — СВЕРКА ГЛАЗАМИ ОБЯЗАТЕЛЬНА (map/rules/82 §0)' % (len(D), len(X), len(plain)))
    return [back(r) for r in D], [back(r) for r in X], [back(r) for r in plain], info


def to_places(D, px_per_m, src='lines'):
    """столы по линиям -> записи мест в кадре work.png (как вход workplaces / render_draft): desk Polygon, seat, how, size_m"""
    out = []
    for r in D:
        out.append(dict(desk=Polygon(r['poly']), seat=tuple(r['seat']), how='стул (линии)', src=src, size_m=[round(r['L'], 2), round(r['D'], 2)],
                        conf=r.get('seat_confidence')))
    return out


def chairs_of(D):
    """стулья, найденные у столов (центр линий стула), — для Ч-31, кадр work.png"""
    return [[round(float(r['seat'][0]), 1), round(float(r['seat'][1]), 1)] for r in D if r.get('seat')]
