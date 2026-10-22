# ocg/role_checks.py - code 012 (СП-4 пп. 1-2, СО-3; ОЧ-63): stops of ocg/start_ocg.py before the run that read the CONTENT of
#   the sheet's layers against the roles and the fields of cfg - the errors a weak table makes silently (self-check LOW,
#   08.10.2026: «Спринклеры» -> mark, «Обобщенные модели» -> equipment, «09 FURNITURE_1» -> furniture; OCG_ORIGIN_AXES and
#   OCG_AXIS_TEXT_RE not set: fire cabinets 0 of 18, sinks 0 of 7, axis marks 0 of 25, origin off the axes).
#   Every sign is taken from the source, not from a layer name; thresholds in mm go to pt by cfg.MM_PER_PT.
#   1. Axes (row 184, plan/rules/50 §1). An axis mark = a word inside a closed round face (bubble, 300-3000 mm) of a layer of
#      the role 'axis'. Marks on the sheet and no cfg.OCG_ORIGIN_AXES or cfg.OCG_AXIS_TEXT_RE - stop; a mark the regex does
#      not take - stop (Э8 loses it). The origin: marks fall into families - prefix + kind of the last token (digits /
#      letters), a family has >= 2 marks; the first axis of a family - the least token (a suffix such as «*» loses a tie).
#      With exactly one family of digits and one of letters the origin is the crossing of their first axes; cfg.OCG_ORIGIN_AXES
#      naming another pair - stop. Lifted only by cfg.OCG_ORIGIN_OK = '<reason>' (a sheet where row 184 does not apply).
#   2. Object-sized figures on an annotation role (СП-4 п. 2). A layer of the role 'mark', 'dim' or 'text' holding closed
#      figures (faces of its own lines, or fills) with the long side >= OBJ_MM (300 mm) and the short side >= OBJ_MIN_MM
#      (100 mm: double lines of a dimension are no object) - stop with a picture of the layer (PNG, the figures in red):
#      the role is most likely one of objects (fire, equipment, sink).
#   2b. Round items under a role of rectilinear objects <one example: client-b, two layers of the LOW table>. A layer of
#      the role 'furniture' or 'equipment' without a single fill, whose segments are curves for >= CURVE_SHARE (30 %), with
#      compact clusters of 300-1500 mm - stop with a picture: round items drawn by lines (sinks, plants, sanitary) - the
#      route builds desks and screens from fills and straight sides, it finds nothing here.
#   2, 2b are lifted for one layer by cfg.OCG_ROLE_OK = {'<layer>': '<reason, what the picture shows>'} (an empty reason lifts
#   nothing - check of step 11; the lifted stop is a note of ocg_start.json, the gate repeats it: ocg/gate_ocg.py, «принято старт»).
import math, os, re, collections
import numpy as np

OBJ_MM = 300.0        # СП-4 п. 2: «размером с предмет» - the long side of a figure, mm
OBJ_MIN_MM = 100.0    # the short side of an object-sized figure, mm (a dimension drawn by two lines is a sliver)
BUBBLE_MM = (300.0, 3000.0)   # an axis bubble, mm
CURVE_SHARE = 0.30    # 2b: share of curve segments of a layer without fills <one example>
ITEM_MM = (300.0, 1500.0)     # 2b: a compact item, mm


def _bez(p0, p1, p2, p3, n=8):
    return [((1 - t) ** 3 * p0.x + 3 * (1 - t) ** 2 * t * p1.x + 3 * (1 - t) * t * t * p2.x + t ** 3 * p3.x,
             (1 - t) ** 3 * p0.y + 3 * (1 - t) ** 2 * t * p1.y + 3 * (1 - t) * t * t * p2.y + t ** 3 * p3.y)
            for t in [i / n for i in range(n + 1)]]


def layer_content(dr, strip):
    """{layer (without the prefix): dict(lines=[LineString], fills=[Polygon], n_line, n_curve, n_fill)} from page.get_drawings()"""
    from shapely.geometry import LineString, Polygon
    out = collections.defaultdict(lambda: dict(lines=[], fills=[], n_line=0, n_curve=0, n_fill=0))
    for x in dr:
        if x.get('type') in ('clip', 'group') or not x.get('layer'): continue
        c = out[strip(x['layer'])]
        ring = []
        for it in x['items']:
            if it[0] == 'l':
                a, b = tuple(it[1]), tuple(it[2])
                if abs(a[0] - b[0]) + abs(a[1] - b[1]) > 0.01: c['lines'].append(LineString([a, b])); c['n_line'] += 1; ring += [a, b]
            elif it[0] == 'c':
                q = _bez(*it[1:5]); c['lines'].append(LineString(q)); c['n_curve'] += 1; ring += q
            elif it[0] == 're':
                r = it[1]; q = [(r.x0, r.y0), (r.x1, r.y0), (r.x1, r.y1), (r.x0, r.y1), (r.x0, r.y0)]
                c['lines'].append(LineString(q)); c['n_line'] += 4; ring += q
            elif it[0] == 'qu':
                qd = it[1]; q = [tuple(qd.ul), tuple(qd.ur), tuple(qd.lr), tuple(qd.ll), tuple(qd.ul)]
                c['lines'].append(LineString(q)); c['n_line'] += 4; ring += q
        if 'f' in (x.get('type') or '') and x.get('fill') is not None and len(ring) >= 3:
            c['n_fill'] += 1
            g = Polygon(ring).buffer(0)
            if not g.is_empty: c['fills'].append(g)
    return out


def sides_mm(g, K):
    r = g.minimum_rotated_rectangle
    if r.geom_type != 'Polygon': return (r.length * K, 0.0)
    c = list(r.exterior.coords); a = math.dist(c[0], c[1]); b = math.dist(c[1], c[2])
    return (max(a, b) * K, min(a, b) * K)


def width_mm(g, K):
    """the width of a figure: the diameter of its largest inscribed circle, mm"""
    import shapely
    try: return 2 * shapely.maximum_inscribed_circle(g, 0.05).length * K
    except Exception: return 2 * g.area / max(g.length, 1e-9) * K * 2


def faces(lines):
    from shapely.ops import unary_union, polygonize
    if not lines: return []
    return [f for f in polygonize(unary_union(lines)) if f.area > 1e-6]


def object_figures(c, K):
    """closed figures of a layer (faces of its lines joined per component, fills) of the size of an object: [(Polygon, L, W mm)]"""
    from shapely.ops import unary_union
    fs = faces(c['lines'])
    blocks = []
    if fs:
        u = unary_union([f.buffer(0.05) for f in fs]); blocks = list(getattr(u, 'geoms', [u]))
    out = []
    for g in blocks + c['fills']:
        L, W = sides_mm(g, K)
        if L < OBJ_MM or W < OBJ_MIN_MM: continue
        W = min(W, width_mm(g, K))           # a thin closed zigzag has a wide box and no body
        if W >= OBJ_MIN_MM: out.append((g, round(L), round(W)))
    return out


def round_items(c, K):
    """2b: (share of curves, clusters 300-1500 mm) of a layer without fills; None when the sign does not hold"""
    from shapely.ops import unary_union
    n = c['n_line'] + c['n_curve']
    if c['n_fill'] or not n: return None
    share = c['n_curve'] / n
    if share < CURVE_SHARE: return None
    u = unary_union([l.buffer(0.3) for l in c['lines']]); cl = list(getattr(u, 'geoms', [u]))
    items = [g for g in cl if ITEM_MM[0] <= sides_mm(g, K)[0] <= ITEM_MM[1]]
    return (share, items) if items else None


# ---------------- axes
_MARK = re.compile(r'^(.*?)([0-9]+|[^\W\d_]+)(\W*)$')


def axis_marks(words, axis_lines, K):
    """words inside the bubbles (closed round faces 300-3000 mm) of the axis layers: [(text, x, y)]"""
    from shapely.geometry import Point
    bub = []
    for f in faces(axis_lines):
        L, W = sides_mm(f, K)
        if BUBBLE_MM[0] <= L <= BUBBLE_MM[1] and W >= 0.7 * L: bub.append(f)
    out = []
    for w in words:
        t = w[4].strip()
        if not t or len(t) > 8: continue
        p = Point((w[0] + w[2]) / 2, (w[1] + w[3]) / 2)
        if any(f.contains(p) for f in bub): out.append((t, round(p.x, 1), round(p.y, 1)))
    return out


def _tok_key(tok):
    return (0, int(tok), '') if tok.isdigit() else (1, len(tok), tok.upper())


def axis_families(marks):
    """{(prefix, 'digits'|'letters'): [marks sorted, first first]} - families of >= 2 marks"""
    fam = collections.defaultdict(list)
    for t, *_ in marks:
        m = _MARK.match(t)
        if not m: continue
        pre, tok, suf = m.groups()
        fam[(pre, 'digits' if tok.isdigit() else 'letters')].append((_tok_key(tok), len(suf), t))
    return {k: [t for *_, t in sorted(v)] for k, v in fam.items() if len({x[0] for x in v}) >= 2}


def origin_pair(axes):
    """the two axes cfg.OCG_ORIGIN_AXES puts the origin on: (a, b) - a × b; (across, a1, a2) - a1 × across (Э3)"""
    axes = tuple(axes or ())
    if len(axes) == 2: return frozenset(axes)
    if len(axes) == 3: return frozenset((axes[0], axes[1]))
    return None


# ---------------- picture of a layer
def layer_png(pdf_path, layer_full, figs, path, title=''):
    """the layer alone through the PDF renderer (Э2 way), the figures of the stop in red, framed to the layer"""
    import pymupdf
    from PIL import Image, ImageDraw
    d = pymupdf.open(pdf_path); pg = d[0]
    uis = d.layer_ui_configs()
    for u in uis: d.set_layer_ui_config(u['number'], 0 if u['text'] == layer_full else 2)
    xs = [g.bounds for g in figs] or [tuple(pg.rect)]
    x0 = min(b[0] for b in xs) - 30; y0 = min(b[1] for b in xs) - 30; x1 = max(b[2] for b in xs) + 30; y1 = max(b[3] for b in xs) + 30
    clip = pymupdf.Rect(max(x0, 0), max(y0, 0), min(x1, pg.rect.x1), min(y1, pg.rect.y1))
    z = min(4.0, 2400.0 / max(clip.width, clip.height, 1))
    pix = pg.get_pixmap(matrix=pymupdf.Matrix(z, z), clip=clip)
    im = Image.frombytes('RGB', (pix.width, pix.height), pix.samples); dw = ImageDraw.Draw(im)
    for g in figs:
        b = g.bounds
        dw.rectangle(((b[0] - clip.x0) * z - 3, (b[1] - clip.y0) * z - 3, (b[2] - clip.x0) * z + 3, (b[3] - clip.y0) * z + 3), outline=(220, 0, 0), width=3)
    if title:
        try:
            from PIL import ImageFont; fnt = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 16)
        except Exception: fnt = None
        dw.rectangle((0, 0, im.width, 24), fill='white'); dw.text((4, 3), title, fill=(0, 0, 0), font=fnt)
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True); im.save(path)
    for u in uis: d.set_layer_ui_config(u['number'], 0)
    return path


def check(sheet, stop, res, pdf_path, outdir='start_views'):
    """the stops of СП-4 пп. 1-2 and СО-3; writes res['role_checks']"""
    import pymupdf
    K = sheet.K or sheet.REF_MM_PER_PT
    d = pymupdf.open(pdf_path); pg = d[0]
    dr = pg.get_drawings()
    C = layer_content(dr, sheet.strip)
    # check of step 11: a layer of OCG_ROLE_OK with an empty reason lifts nothing (the field is '<layer>': '<what the picture shows>')
    ok_raw = dict(getattr(sheet.cfg, 'OCG_ROLE_OK', {}) or {})
    ok_roles = {k: str(v).strip() for k, v in ok_raw.items() if str(v or '').strip()}
    empty_ok = lambda L: (f' (cfg.OCG_ROLE_OK для слоя «{L}» задано с пустой причиной — стоп не снимает)' if L in ok_raw and L not in ok_roles else '')
    rc = res.setdefault('role_checks', dict(object_figures={}, round_items={}, axes={}))
    # 2. object-sized closed figures on the annotation roles
    for L in sorted(sheet.L('mark', 'dim', 'text')):
        figs = object_figures(C.get(L, dict(lines=[], fills=[])), K)
        if not figs: continue
        role = sheet.ROLE_OF.get(L)
        png = layer_png(pdf_path, sheet.PREFIX + L, [g for g, *_ in figs], os.path.join(outdir, f'role_{role}_{re.sub(r"[^0-9A-Za-zА-Яа-яЁё]+", "_", L)}.png'),
                        f'{L}: role {role}, {len(figs)} closed figures >= {OBJ_MM:.0f} mm (red)')
        rc['object_figures'][L] = dict(role=role, n=len(figs), sizes_mm=[(a, b) for _, a, b in figs[:12]], png=png)
        msg = (f'слой «{L}» роли {role!r} держит {len(figs)} замкнутых фигур размером с предмет (длинная сторона ≥ {OBJ_MM:.0f} мм, '
               f'короткая ≥ {OBJ_MIN_MM:.0f} мм; первые: {", ".join(f"{a}×{b}" for _, a, b in figs[:4])} мм) — роль, скорее всего, предметная '
               f'(fire, equipment, sink); картинка слоя — {png}. Поправить роль в cfg.OCG_LAYERS; если фигуры — разметка, '
               f"cfg.OCG_ROLE_OK = {{'{L}': '<что на картинке>'}}")
        if L in ok_roles: res['notes'].append(f'роль слоя «{L}» подтверждена cfg.OCG_ROLE_OK: {ok_roles[L]} ({len(figs)} фигур ≥ {OBJ_MM:.0f} мм)')
        else: stop(msg + empty_ok(L))
    # 2b. round items drawn by lines under a role of rectilinear objects
    for L in sorted(sheet.L('furniture', 'equipment')):
        r = round_items(C.get(L, dict(lines=[], fills=[], n_line=0, n_curve=0, n_fill=0)), K)
        if not r: continue
        share, items = r; role = sheet.ROLE_OF.get(L)
        png = layer_png(pdf_path, sheet.PREFIX + L, items[:60], os.path.join(outdir, f'role_{role}_{re.sub(r"[^0-9A-Za-zА-Яа-яЁё]+", "_", L)}.png'),
                        f'{L}: role {role}, no fills, curves {share:.0%}, {len(items)} round items (red)')
        rc['round_items'][L] = dict(role=role, curve_share=round(share, 3), n=len(items), png=png)
        msg = (f'слой «{L}» роли {role!r}: ни одной заливки, дуги — {share:.0%} отрезков (≥ {CURVE_SHARE:.0%}), {len(items)} округлых предметов '
               f'{ITEM_MM[0]:.0f}–{ITEM_MM[1]:.0f} мм — так рисуют мойки, растения, сантехнику, а не столы и экраны; роль, скорее всего, '
               f'sink, plant или sanitary; картинка слоя — {png}. Поправить роль в cfg.OCG_LAYERS или cfg.OCG_ROLE_OK = '
               f"{{'{L}': '<что на картинке>'}}")
        if L in ok_roles: res['notes'].append(f'роль слоя «{L}» подтверждена cfg.OCG_ROLE_OK: {ok_roles[L]}')
        else: stop(msg + empty_ok(L))
    # 1. axes and the origin
    ax_lines = [l for L in sheet.L('axis') for l in C.get(L, dict(lines=[]))['lines']]
    marks = axis_marks(pg.get_text('words'), ax_lines, K) if ax_lines else []
    A = rc['axes']; A['marks'] = [t for t, *_ in marks]
    if not marks:
        res['notes'].append('марок осей на слоях роли axis не найдено — начало по осям не проверяется'); return
    axes = tuple(getattr(sheet.cfg, 'OCG_ORIGIN_AXES', ()) or ()); rx = getattr(sheet.cfg, 'OCG_AXIS_TEXT_RE', None)
    miss = [f for f, v in (('OCG_ORIGIN_AXES', axes), ('OCG_AXIS_TEXT_RE', rx)) if not v]
    if miss:
        stop(f'на слоях роли axis {len(marks)} марок осей ({", ".join(t for t, *_ in marks[:6])}…), а cfg.{" и cfg.".join(miss)} не задано: '
             f'без них начало не на осях и марки не попадут в A-AX----T- (строка 184; plan/rules/50 §1, plan/rules/20 §3.8)')
    if rx:
        lost = [t for t, *_ in marks if not re.fullmatch(rx, t)]
        if lost: stop(f'cfg.OCG_AXIS_TEXT_RE = {rx!r} не берёт {len(lost)} марок осей листа: {lost[:8]} — Э8 их потеряет')
    fam = axis_families(marks); A['families'] = {f'{p}·{k}': v for (p, k), v in fam.items()}
    dig = [v for (p, k), v in fam.items() if k == 'digits']; let = [v for (p, k), v in fam.items() if k == 'letters']
    why_ok = getattr(sheet.cfg, 'OCG_ORIGIN_OK', '')
    if len(dig) != 1 or len(let) != 1:
        m = (f'марки осей не делятся на одно семейство цифр и одно семейство букв (цифр — {len(dig)}, букв — {len(let)}: '
             f'{A["families"]}) — начало по строке 184 не выводится кодом')
        if why_ok: res['notes'].append(m + f'; начало — по cfg.OCG_ORIGIN_OK: {why_ok}')
        elif axes: stop(m + '; проверить cfg.OCG_ORIGIN_AXES по листу и задать cfg.OCG_ORIGIN_OK с причиной')
        return
    first = (dig[0][0], let[0][0]); A['first'] = first
    pair = origin_pair(axes); A['cfg_pair'] = sorted(pair) if pair else None
    if axes and pair != frozenset(first):
        m = (f'начало не на пересечении первых осей двух семейств: cfg.OCG_ORIGIN_AXES = {axes!r} ставит его на '
             f'{" × ".join(sorted(pair)) if pair else "?"}, а по строке 184 — {first[0]} × {first[1]} (plan/rules/50 §1): '
             f'задать OCG_ORIGIN_AXES = {(first[1], first[0])!r} и ORIGIN_PT по Э3')
        if why_ok: res['notes'].append(m + f' — оставлено по cfg.OCG_ORIGIN_OK: {why_ok}')
        else: stop(m)
    elif axes: res['notes'].append(f'начало — оси {first[0]} × {first[1]} (первые оси двух семейств, строка 184)')
