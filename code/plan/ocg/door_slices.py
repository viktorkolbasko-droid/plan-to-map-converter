"""Test 10 (owner 07.10.2026: «На слое с дверями ты не везде попадаешь в проем. Нужно… проверить, что толщина проема совпадает
с толщиной стены»). The wall's cross-section beside a door's opening, by slices: a line across the opening's axis (along n),
at a distance δ beyond the opening's end (along u), cut by the carriers (wall bodies, glass panes, core blocks); the pieces
of the cut are merged along n where they touch (≤ TOUCH_MM); the merged piece over the opening (overlapping its [t0, t1] or
nearest within NEAR_MM) is the wall's section at δ: its faces lo..hi. Slices at δ = SLICE_MM beyond the end: the section is
«stable» when two consecutive slices agree within STABLE_MM on both faces — a straight wall; it is «clipped» when it reaches
the slice's own end (±REACH_MM) — the carrier runs across the opening's axis (the side of a perpendicular wall, a block).
Code 012 (stage 1 of the merge of v009 into ocg/; the code of pass v009, route/door_slices.py): every threshold in mm,
turned into pt of the sheet as read by k = mm per pt (sheet.K, cfg.MM_PER_PT) that the caller passes - v009 set them in pt
at 48.04 mm/pt <one example: client-b, floor 40>, the mm below are those pt × 48.04 exactly (step 8: no rounding to 0.1 mm -
the rounded slices moved openings by up to 0.03 mm, and Э7р, which pins the walls' face lines to the openings, carried it into
the rooms of Э9з); the layers that are not
jambs - by the roles of the sheet's layer table (JAMB_EX_ROLES -> the caller's sheet.L(...)), no layer name of one sheet.
The module reads no cfg itself: e7o_openings.py and doors_fit.py pass k and the layers.
section(C, o_, u, n, a_end, sgn, t0, t1, k) -> dict(lo, hi, cls, stable, clipped, at, all) or None (lo, hi, at - pt)
jamb(S, o_, u, n, a_end, t0, t1, k, marks)  -> dict(lo, hi, cls) or None"""
import numpy as np, shapely
from shapely.geometry import LineString, Polygon
SLICE_MM = (7.206, 19.216, 38.432, 57.648)   # v009 DELTAS 0.15, 0.4, 0.8, 1.2 pt: the slices beyond the opening's end
REACH_MM = 384.32                    # v009 R = 8 pt: half the slice across the axis
TOUCH_MM = 2.402                     # 0.05 pt: pieces of one cut that touch along n are one piece
NEAR_MM = 28.824                     # 0.6 pt: a piece off the opening's band farther than this is not its wall
STABLE_MM = 9.608                    # 0.2 pt (≈ 10 mm): two consecutive slices agree on both faces
CLIP_MM = 0.4804                     # 0.01 pt: the section reaches the slice's own end - clipped
# the jamb lines of the source at an opening's end: strokes across the wall (within 14° of n, JAMB_COS), at the end
# (|along u − a_end| ≤ JAMB_WIN_MM), JAMB_LMIN_MM–JAMB_LMAX_MM long (longer — the face of a wall running across the opening's
# axis, not a jamb); their extents along n merged where they touch (≤ JAMB_TOUCH_MM); the merged run over the opening
# (overlapping [t0, t1] or within JAMB_NEAR_MM) is the jamb: lo..hi
JAMB_WIN_MM, JAMB_LMIN_MM, JAMB_LMAX_MM, JAMB_TOUCH_MM, JAMB_NEAR_MM, JAMB_COS = 16.814, 9.608, 576.48, 7.206, 14.412, 0.97   # v009: 0.35; 0.2; 12; 0.15; 0.3 pt
# roles of the sheet's layers whose strokes are not jambs (v009 named the layers of one sheet: «Мебель», «09 FURNITURE_1»,
# «Размеры», «Спринклеры», «Аннотация», «Помещения», «Двери», «Узлы», the axes' layer and «…A-LIFT»): furniture, plants,
# dimensions, fire cabinets, room tags, room fills, other doors' strokes, details (the sides of a niche or a riser behind a
# service door run on from its jamb — not the wall's jamb), axes, the lift's own block (the lift, not a wall). The jambs are
# the strokes of the walls' and the core's layers and the door's own frame pieces (its marks).
JAMB_EX_ROLES = ('furniture', 'plant', 'dim', 'fire', 'tag', 'zone', 'door', 'core_hatch', 'axis', 'lift')


class Carriers:
    def __init__(self, items):            # items: [(class, polygon)]
        self.items = [(c, g) for c, g in items if g is not None and not g.is_empty]
        self.tree = shapely.STRtree([g for _, g in self.items])

    def cut(self, a, b):                  # the pieces of the line a–b inside the carriers: [(t0, t1, class)] along the line (0..1)
        L = LineString([a, b]); out = []; A = np.array(a, float); D = np.array(b, float) - A; LL = float(D @ D)
        for j in self.tree.query(L):
            c, g = self.items[j]; x = g.intersection(L)
            if x.is_empty: continue
            for q in getattr(x, 'geoms', [x]):
                if q.geom_type != 'LineString' or q.length < 1e-6: continue
                ts = [float((np.array(p) - A) @ D) / LL for p in q.coords]
                out.append((min(ts), max(ts), c))
        return out


def merged(pieces, tol):
    pieces = sorted(pieces); M = []
    for a, b, c in pieces:
        if M and a <= M[-1][1] + tol: M[-1][1] = max(M[-1][1], b); M[-1][2].add(c)
        else: M.append([a, b, {c}])
    return M


def section(C, o_, u, n, a_end, sgn, t0, t1, k, deltas_mm=SLICE_MM):
    if not k: raise SystemExit('door_slices.section: нет масштаба листа (k = cfg.MM_PER_PT) — пороги в мм не перевести в pt')
    o_, u, n = np.asarray(o_, float), np.asarray(u, float), np.asarray(n, float); tm = (t0 + t1) / 2
    R = REACH_MM / k; res = []
    for dl_mm in deltas_mm:
        dl = dl_mm / k
        base = o_ + u * (a_end + sgn * dl)
        a, b = base + n * (tm - R), base + n * (tm + R)
        ps = [(tm - R + 2 * R * x0, tm - R + 2 * R * x1, c) for x0, x1, c in C.cut(tuple(a), tuple(b))]
        M = merged(ps, TOUCH_MM / k)
        best = None
        for lo, hi, cs in M:
            ov = min(hi, t1) - max(lo, t0); gap = max(lo - t1, t0 - hi, 0.0)
            if ov <= 0 and gap > NEAR_MM / k: continue
            key = (ov if ov > 0 else -gap)
            if best is None or key > best[0]: best = (key, lo, hi, cs)
        if best is None: res.append(None); continue
        _, lo, hi, cs = best
        res.append(dict(d=dl, lo=lo, hi=hi, cls='/'.join(sorted(cs)), clipped=(lo <= tm - R + CLIP_MM / k or hi >= tm + R - CLIP_MM / k)))
    # the first stable pair
    for i in range(len(res) - 1):
        x, y = res[i], res[i + 1]
        if x and y and abs(x['lo'] - y['lo']) <= STABLE_MM / k and abs(x['hi'] - y['hi']) <= STABLE_MM / k:
            return dict(lo=x['lo'], hi=x['hi'], cls=x['cls'], stable=True, clipped=x['clipped'] or y['clipped'], at=x['d'], all=res)
    first = next((x for x in res if x), None)
    if not first: return None
    return dict(lo=first['lo'], hi=first['hi'], cls=first['cls'], stable=False, clipped=first['clipped'], at=first['d'], all=res)


class Strokes:
    """the strokes that may be a jamb: lines, fills, wide lines of the source (not synthetic), not on the layers ex_layers
    (the caller: sheet.L(*JAMB_EX_ROLES))"""
    def __init__(self, P, geom, ex_layers):
        ex = frozenset(ex_layers)
        self.P = P; self.idx = [i for i, p in enumerate(P) if p['kind'] in ('line', 'fill', 'wline') and len(p['p']) >= 2 and not p.get('synthetic')
                                and p['layer'] not in ex]
        self.G = [geom(P[i]) for i in self.idx]; self.tree = shapely.STRtree(self.G)


def jamb(S, o_, u, n, a_end, t0, t1, k, marks=()):
    if not k: raise SystemExit('door_slices.jamb: нет масштаба листа (k = cfg.MM_PER_PT) — пороги в мм не перевести в pt')
    win, lmin, lmax = JAMB_WIN_MM / k, JAMB_LMIN_MM / k, JAMB_LMAX_MM / k
    o_, u, n = np.asarray(o_, float), np.asarray(u, float), np.asarray(n, float)
    box = Polygon([tuple(o_ + u * (a_end - win) + n * (t0 - lmax)), tuple(o_ + u * (a_end + win) + n * (t0 - lmax)),
                   tuple(o_ + u * (a_end + win) + n * (t1 + lmax)), tuple(o_ + u * (a_end - win) + n * (t1 + lmax))])
    ids = [S.idx[j] for j in S.tree.query(box)] + [i for i in marks if len(S.P[i]['p']) >= 2]
    iv = []
    for i in ids:
        pts = np.array(S.P[i]['p'], float)
        for a, b in zip(pts[:-1], pts[1:]):
            d = b - a; L = float(np.linalg.norm(d))
            if L < lmin or L > lmax or abs(float(d @ n)) / L < JAMB_COS: continue
            ua, ub = float((a - o_) @ u) - a_end, float((b - o_) @ u) - a_end
            if max(abs(ua), abs(ub)) > win: continue
            ta, tb = sorted([float((a - o_) @ n), float((b - o_) @ n)])
            iv.append((ta, tb, S.P[i]['layer'] + ('·рамка' if i in marks else '')))
    if not iv: return None
    M = merged(iv, JAMB_TOUCH_MM / k); best = None
    for lo, hi, cs in M:
        ov = min(hi, t1) - max(lo, t0); gap = max(lo - t1, t0 - hi, 0.0)
        if ov <= 0 and gap > JAMB_NEAR_MM / k: continue
        key = ov if ov > 0 else -gap
        if best is None or key > best[0]: best = (key, lo, hi, cs)
    if best is None: return None
    return dict(lo=best[1], hi=best[2], cls='/'.join(sorted(best[3])))
