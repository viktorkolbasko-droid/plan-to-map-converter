# Grid axes of a Revit sheet and the scale by the dimension texts between them - the rule of probe.py (code 005-010),
#   one module for probe.py and norm.py (code 011, package 5: ПК4-П1, ПК4-П14). Coordinates - the displayed (rotated)
#   page of PyMuPDF, pt, x right, y down.
#   - an axis: dashed collinear strokes (>= 5 pieces, the span >= 0.3 of the page), grey or pink, with a bubble - a name
#     next to one of its ends (a grid axis always has one; unnamed collinear strokes are rows of furniture);
#   - the mm of an interval: a number of 3-5 digits between two neighbouring axes whose ratio mm / pt is a scale of the
#     route's band (55-75 mm/pt on the sheet itself; on a copy x k the same sheet gives the ratio / k).
import re, math, collections

NOTNAME = {'ПК'}
NAME = re.compile(r'^[А-ЯA-Z]?(/?\d{1,2}|[А-ЯA-Z](/\d)?)$|^\d{1,2}$|^[А-ЯЁ](/\d)?$|^[А-ЯЁ]\s?/\s?\d$')


def greyish(c):
    return c is not None and ((abs(c[0] - c[1]) < 0.03 and abs(c[1] - c[2]) < 0.03 and 0.45 <= c[0] <= 0.85) or
                              (c[0] > 0.95 and abs(c[1] - c[2]) < 0.03 and 0.5 < c[1] < 0.8))


def segments(pg, dr=None):
    """straight strokes of the page in displayed pt: (x0, y0, x1, y1, width, stroke colour) - probe.py's list"""
    M = pg.rotation_matrix; segs = []
    for d in (dr if dr is not None else pg.get_drawings()):
        w = round(d.get('width') or 0, 2); sc = tuple(round(c, 2) for c in d['color']) if d.get('color') else None
        for it in d['items']:
            if it[0] == 'l' and sc is not None:
                a = it[1] * M; b = it[2] * M; segs.append((a.x, a.y, b.x, b.y, w, sc))
    return segs


def axis_segments(pg):
    """the strokes find_axes() looks at (straight, grey or pink), fast: the C list of the drawings (get_cdrawings), the
    colour tested before the points are turned to the displayed page - the same list as segments() filtered by greyish()"""
    a, b, c, d, e, f = tuple(pg.rotation_matrix); segs = []
    for dr in pg.get_cdrawings():
        col = dr.get('color')
        if not col: continue
        sc = tuple(round(v, 2) for v in col)
        if not greyish(sc): continue
        w = round(dr.get('width') or 0, 2)
        for it in dr['items']:
            if it[0] == 'l':
                (x0, y0), (x1, y1) = it[1], it[2]
                segs.append((a * x0 + c * y0 + e, b * x0 + d * y0 + f, a * x1 + c * y1 + e, b * x1 + d * y1 + f, w, sc))
    return segs


def words_of(pg):
    import pymupdf as fitz
    M = pg.rotation_matrix; out = []
    for x in pg.get_text('words'):
        r = fitz.Rect(x[:4]) * M; out.append(((r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2, x[4], (r.x0, r.y0, r.x1, r.y1)))
    return out


def find_axes(segs, words, PW, PH):
    """{'v': [...], 'h': [...]}: pos, n, span, lo, hi, color, name - named axes only"""
    grp = collections.defaultdict(list)
    for x0, y0, x1, y1, w, sc in segs:
        if not greyish(sc): continue
        if abs(x0 - x1) < 0.03 and abs(y0 - y1) > 0.3: grp[('v', round((x0 + x1) / 2, 1))].append((min(y0, y1), max(y0, y1), sc, (x0 + x1) / 2))
        elif abs(y0 - y1) < 0.03 and abs(x0 - x1) > 0.3: grp[('h', round((y0 + y1) / 2, 1))].append((min(x0, x1), max(x0, x1), sc, (y0 + y1) / 2))
    axes = {'v': [], 'h': []}
    for (o, c), v in grp.items():
        span = max(r[1] for r in v) - min(r[0] for r in v)
        ext = PH if o == 'v' else PW
        if len(v) >= 5 and span >= 0.3 * ext:
            pos = round(sum(r[3] for r in v) / len(v), 2)
            axes[o].append(dict(pos=pos, n=len(v), span=round(span), lo=round(min(r[0] for r in v), 1), hi=round(max(r[1] for r in v), 1),
                                color=collections.Counter(r[2] for r in v).most_common(1)[0][0]))
    for o in axes:   # merge duplicates within 0.3 pt
        axes[o].sort(key=lambda a: a['pos']); m = []
        for a in axes[o]:
            if m and abs(a['pos'] - m[-1]['pos']) < 0.3:
                if a['n'] > m[-1]['n']: m[-1] = a
            else: m.append(a)
        axes[o] = m

    def name_for(o, a, across=4):
        best = None
        for w in words:
            if not NAME.match(w[2].replace(' ', '')) or w[2] in NOTNAME: continue
            if o == 'v':
                if abs(w[0] - a['pos']) > across: continue
                d = min(abs(w[1] - a['lo']), abs(w[1] - a['hi']))
            else:
                if abs(w[1] - a['pos']) > across: continue
                d = min(abs(w[0] - a['lo']), abs(w[0] - a['hi']))
            if d < 40 and (best is None or d < best[0]): best = (d, w[2].replace(' ', ''))
        return best[1] if best else None
    for o in axes:
        for a in axes[o]:
            a['name'] = name_for(o, a)
            if a['name'] is None:                      # bubble moved off the axis with a leader: wider search, flag it
                n2 = name_for(o, a, across=16); a['name'] = (n2 + '?') if n2 else None
        axes[o] = [a for a in axes[o] if a['name']]    # a grid axis always has a bubble; unnamed collinear strokes are furniture rows
    return axes


def interval_mm(o, lst, words, band=(55, 75), k=1.0):
    """mm of each interval between neighbouring axes of the list (sorted by pos): the dimension number between them whose
    ratio number / (interval x k) lies in the band, the nearest to the middle; None - no such number. k - the copy factor
    (a copy x k of the sheet: the interval x k, the number the same)"""
    out = []
    for a, b in zip(lst[:-1], lst[1:]):
        lo, hi = a['pos'], b['pos']; best = None
        for w in words:
            if not re.fullmatch(r'\d{3,5}', w[2]): continue
            c = w[0] if o == 'v' else w[1]
            if lo < c < hi:
                val = int(w[2]); kk = val / ((hi - lo) * k)
                if band[0] <= kk <= band[1] and (best is None or abs(c - (lo + hi) / 2) < abs(best[1] - (lo + hi) / 2)): best = (val, c)
        out.append(best[0] if best else None)
    return out


def scale(axes, words, k=1.0):
    """(median mm per pt of the sheet x k, spread, intervals matched, intervals) by the dimension numbers between the axes"""
    ks = []; n = 0
    for o in axes:
        lst = sorted(axes[o], key=lambda a: a['pos']); iv = interval_mm(o, lst, words, k=k); n += len(iv)
        for (a, b), v in zip(zip(lst[:-1], lst[1:]), iv):
            if v: ks.append(v / ((b['pos'] - a['pos']) * k))
    med = sorted(ks)[len(ks) // 2] if ks else None
    return med, ([min(ks), max(ks)] if ks else None), len(ks), n


def copies_search(axes, words, ks=None):
    """code 011 (ПК4-П1): a sheet outside 55-75 mm/pt - the scale is not found on the sheet itself; the copies x k for k of
    the series 0.50-2.00 (step 0.01: a copy's pt are the sheet's x k - the series is computed on the positions, no PDF is
    written) - at which k the dimension numbers between the axes agree (most intervals matched, spread <= 1 %); returns
    dict(k=…, sheet_mm_per_pt=…, matched=…, of=…, band=[k_lo, k_hi]) or None"""
    rows = []
    for i in range(50, 201):
        k = i / 100.0
        med, spr, m, n = scale(axes, words, k)
        if med and m >= 2 and (spr[1] - spr[0]) / med <= 0.01: rows.append((m, k, med, n))
    if not rows: return None
    mbest = max(r[0] for r in rows); ok = [r for r in rows if r[0] == mbest]
    sheet = ok[0][2] * ok[0][1]                       # mm per pt of the sheet itself (the copy's x k)
    return dict(k=round(sheet / 63.5, 4), sheet_mm_per_pt=round(sheet, 3), matched=mbest, of=ok[0][3], band=[ok[0][1], ok[-1][1]])
