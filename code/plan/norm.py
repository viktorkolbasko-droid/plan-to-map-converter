# Code 010 (package 4, К-3): the sheet brought to the reference scale of the code at extraction (owner's decision of
#   07.10.2026, №98, row 201; ПК2-П9; plan/rules/10 §2). The thresholds of the code are set in pt on sheets of one scale
#   (Revit route: 63.5 mm/pt, client A; layer route ocg/: 48.04 mm/pt <one example: client-b, floor 40>). A sheet of
#   another scale is not stopped and its thresholds are not converted one by one: the code reads a copy of the sheet
#   whose page is scaled by k = SHEET_MM_PER_PT / REF - every coordinate, pen width, text size, clip and raster of the
#   copy is the sheet's x k, so 1 pt of the copy is REF mm of the building. The DXF stays in mm as before (MM() of the
#   copy's pt).
#   - the copy: two small content streams around the page's own ("q k 0 0 k 0 0 cm" ... "Q"), MediaBox and CropBox x k,
#     rotation, OCG layers and the page's streams unchanged byte for byte; made by the code from the source PDF in every
#     run (rule 30: a run of one command from the source), <stem>__norm<REF>.pdf next to it, norm.json beside it;
#   - cfg of such a floor is written in pt of the copy (one space for the code, cfg and the review tools); the field
#     SHEET_MM_PER_PT is the scale of the sheet itself (probe.py / Э3 on the source); inside the band of the route the
#     sheet goes as it is (k = 1: client A 1-6, 60-70 mm/pt; ocg/ within 2 % of 48.04);
#   - stops (exit 3, before anything is computed): the scale of cfg is off the band and SHEET_MM_PER_PT is not set (cfg
#     written in pt of the sheet - set the field and write cfg on the copy); SHEET_MM_PER_PT is set and the scale of cfg
#     is not the reference one (cfg written in pt of the sheet, not of the copy).
#   python3 norm.py [revit|ocg]      floor folder: the decision, the copy when needed, norm.json; exit 0 - go, 3 - stop
#   python3 norm.py --copy src.pdf K out.pdf    the copy of any PDF scaled by K (also the test sheets x1.5, x1.3)
#   Code 011 (package 5): the copy is reproducible byte for byte (ПК4-П18); the Revit route checks the sheet it reads
#   against cfg - the grid axes of cfg against the axes of the read sheet (gridaxes.py, the rule of probe.py) and the field
#   against the scale of cfg: a forgotten SHEET_MM_PER_PT, a field set on a sheet of the band, an imprecise field - a stop
#   that names the field and its value (ПК4-П14); a sheet without axes found - a note, not a check
import os, sys, json, hashlib, importlib.util
REF = {'revit': 63.5, 'ocg': 48.04}                 # mm per pt of the sheets the thresholds of the route were set on
BAND = {'revit': (60.0, 70.0),                      # the band of the Revit route as before (plan/rules/10 §2): k = 1 inside
        'ocg': (48.04 * 0.98, 48.04 * 1.02)}        # ocg/: 2 % as the stop of code 009 (start_ocg.py)


def factor(sheet_mm_per_pt, route):
    """k for a sheet of this scale: 1 inside the band of the route, else sheet / REF (the copy is k x the sheet)"""
    if not sheet_mm_per_pt: return 1.0
    lo, hi = BAND[route]
    if lo <= sheet_mm_per_pt <= hi: return 1.0
    return float(sheet_mm_per_pt) / REF[route]


def copy_name(pdf, route):
    st, _ = os.path.splitext(pdf)
    return f'{st}__norm{REF[route]:g}.pdf'


def sha256(fn):
    h = hashlib.sha256()
    with open(fn, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''): h.update(b)
    return h.hexdigest()


def make_copy(src, dst, k):
    """the page scaled by k around the origin of the PDF user space: a prefix stream 'q k 0 0 k 0 0 cm', the page's own
    streams, a suffix stream 'Q'; MediaBox and CropBox x k. PyMuPDF reports drawings, texts and pixmaps of the copy in
    the copy's pt (x k of the sheet's)"""
    import pymupdf as fitz
    doc = fitz.open(src)
    for page in doc:
        page.wrap_contents()                         # the page's own q/Q balanced (no effect on a balanced page)
        old = page.get_contents()
        pre = doc.get_new_xref(); doc.update_object(pre, '<<>>'); doc.update_stream(pre, (f'q {k:.10f} 0 0 {k:.10f} 0 0 cm\n').encode())
        suf = doc.get_new_xref(); doc.update_object(suf, '<<>>'); doc.update_stream(suf, b'\nQ\n')
        doc.xref_set_key(page.xref, 'Contents', '[' + ' '.join(f'{x} 0 R' for x in [pre] + list(old) + [suf]) + ']')
        mb = page.mediabox; cb = page.cropbox
        page.set_mediabox(fitz.Rect(mb.x0 * k, mb.y0 * k, mb.x1 * k, mb.y1 * k))
        if cb != mb: page.set_cropbox(fitz.Rect(cb.x0 * k, cb.y0 * k, cb.x1 * k, cb.y1 * k))
    # code 011 (ПК4-П18): the copy keeps the /ID of the source - two copies of one sheet with one k are byte for byte the
    #   same (a new /ID made every copy differ, norm.json could not be checked by the copy's hash across runs)
    doc.save(dst, garbage=0, deflate=False, no_new_id=True)
    return dst


def ensure_copy(pdf, k, route):
    """the copy for this floor: made anew when missing or made from another source or another k (norm.json)"""
    dst = copy_name(pdf, route); meta = 'norm.json'
    want = dict(source=pdf, source_sha256=sha256(pdf), k=round(k, 12), route=route, ref_mm_per_pt=REF[route], copy=dst)
    have = {}
    if os.path.exists(meta):
        try: have = json.load(open(meta))
        except Exception: have = {}
    if not (os.path.exists(dst) and all(have.get(x) == want[x] for x in want) and have.get('copy_sha256') == sha256(dst)):
        make_copy(pdf, dst, k); want['copy_sha256'] = sha256(dst); json.dump(want, open(meta, 'w'), ensure_ascii=False, indent=1)
    return dst


def decide(route, cfg_mm_per_pt, sheet_mm_per_pt, pdf=None):
    """(k, stops, notes) for a floor: cfg_mm_per_pt - the scale of cfg (axes or MM_PER_PT, pt of what the code reads),
    sheet_mm_per_pt - cfg.SHEET_MM_PER_PT, the scale of the source sheet itself"""
    lo, hi = BAND[route]; ref = REF[route]; stops, notes = [], []
    k = factor(sheet_mm_per_pt, route)
    if sheet_mm_per_pt and k == 1.0:
        notes.append(f'лист {sheet_mm_per_pt:g} мм/pt — в полосе {lo:g}–{hi:g}: идёт как есть, k = 1')
    if k != 1.0:
        notes.append(f'лист {sheet_mm_per_pt:g} мм/pt вне полосы {lo:g}–{hi:g}: код читает копию листа в {ref:g} мм/pt, k = {k:.6f}')
        if cfg_mm_per_pt and abs(cfg_mm_per_pt / ref - 1) > 0.02:
            stops.append(f'cfg записан не в pt копии: масштаб по cfg {cfg_mm_per_pt:.3f} мм/pt, у копии — {ref:g} (±2 %). Поля '
                         f'cfg этажа вне полосы — в pt копии листа {copy_name(pdf or "<PDF>", route)} (её делает код; probe.py, gridview — по копии); '
                         f'plan/rules/10 §2')
    elif cfg_mm_per_pt and not (lo <= cfg_mm_per_pt <= hi):
        stops.append(f'масштаб листа {cfg_mm_per_pt:.3f} мм/pt вне полосы {lo:g}–{hi:g} маршрута ({ref:g} мм/pt): лист приводится '
                     f'к опорному масштабу — задать cfg.SHEET_MM_PER_PT = {cfg_mm_per_pt:.4f} (масштаб самого листа) и записать '
                     f'поля cfg в pt копии листа (её делает код, run.sh — заново); plan/rules/10 §2')
    return k, stops, notes


def axes_check(pdf_read, ax_x, ax_y, tol=1.0):
    """code 011 (ПК4-П14): the sheet the code reads against cfg - the grid axes of cfg (AX_X, AX_Y, pt) and the axes of the
    read sheet by the rule of probe.py (gridaxes.py). A copy x k of a sheet has every displayed coordinate x k (about the
    page's corner), so the read sheet is the sheet cfg was written on x s, s = k read / k of cfg: s = 1 - the same sheet;
    else the axes meet at the factor s. Returns dict(status='same' | 'scaled' | 'no-axes' | 'unmatched', s, matched, of)"""
    import pymupdf as fitz
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import gridaxes as GA
    doc = fitz.open(pdf_read); pg = doc[0]
    axes = GA.find_axes(GA.axis_segments(pg), GA.words_of(pg), pg.rect.width, pg.rect.height)
    fx = [a['pos'] for a in axes['v']]; fy = [a['pos'] for a in axes['h']]; n = len(ax_x) + len(ax_y)
    res = dict(found_v=len(fx), found_h=len(fy), cfg_axes=n)
    if len(fx) + len(fy) < 2: res.update(status='no-axes'); return res
    def match(s):
        m = sum(1 for p in ax_x if fx and min(abs(p * s - q) for q in fx) <= tol) + sum(1 for p in ax_y if fy and min(abs(p * s - q) for q in fy) <= tol)
        return m
    m1 = match(1.0)
    if m1 >= 0.6 * n: res.update(status='same', s=1.0, matched=m1, of=n); return res
    cand = sorted({round(q / p, 4) for P_, F_ in ((ax_x, fx), (ax_y, fy)) for p in P_ for q in F_ if p > 1 and 0.3 <= q / p <= 3.0})
    best = max(((match(s), s) for s in cand), default=(0, None))
    if best[1] is not None and best[0] >= 0.6 * n:
        # refine s: least squares over the matched pairs
        prs = [(p, min(fx, key=lambda q: abs(p * best[1] - q))) for p in ax_x if fx] + [(p, min(fy, key=lambda q: abs(p * best[1] - q))) for p in ax_y if fy]
        prs = [(p, q) for p, q in prs if abs(p * best[1] - q) <= tol]
        s_ = sum(p * q for p, q in prs) / sum(p * p for p, q in prs)
        res.update(status='scaled', s=round(s_, 5), matched=best[0], of=n); return res
    res.update(status='unmatched', s=None, matched=m1, of=n); return res


def check_revit(cfg_mm_per_pt, sheet_mm_per_pt, k, pdf_src, pdf_read, ax_x, ax_y):
    """code 011 (ПК4-П14): stops of the Revit route about the scale of the sheet the code reads, each one naming the field
    SHEET_MM_PER_PT - (stops, notes, axes)"""
    ref = REF['revit']; lo, hi = BAND['revit']; stops, notes = [], []
    ax = None
    if len(ax_x) >= 2 and len(ax_y) >= 2 and pdf_read and os.path.exists(pdf_read):
        ax = axes_check(pdf_read, ax_x, ax_y)
    field = f'SHEET_MM_PER_PT = {sheet_mm_per_pt:g}' if sheet_mm_per_pt else 'SHEET_MM_PER_PT не задан'
    if ax and ax['status'] == 'scaled':
        s = ax['s']; k_cfg = k / s          # cfg was written on the source x k_cfg
        if abs(k_cfg - 1) <= 0.01 and cfg_mm_per_pt and lo <= cfg_mm_per_pt <= hi:
            stops.append(f'масштаб листа: {field} задан у листа в полосе — код читает копию листа × {k:.4f}, а оси cfg сходятся с осями '
                         f'самого листа (× 1; {ax["matched"]} из {ax["of"]} осей), и масштаб по осям cfg — {cfg_mm_per_pt:.3f} мм/pt, в полосе '
                         f'{lo:g}–{hi:g}: лист идёт как есть — поле убрать (plan/rules/10 §2)')
        elif abs(k_cfg - 1) <= 0.01:
            pass                             # cfg in pt of the sheet itself, the sheet off the band: the stop of decide() - cfg on the copy
        elif not sheet_mm_per_pt:
            stops.append(f'масштаб листа: SHEET_MM_PER_PT не задан — код читает сам лист, а оси cfg сходятся с осями копии листа × {k_cfg:.4f} '
                         f'({ax["matched"]} из {ax["of"]} осей): cfg размечен по копии — задать cfg.SHEET_MM_PER_PT = {ref * k_cfg:.4f} '
                         f'(масштаб самого листа; plan/rules/10 §2)')
        else:
            stops.append(f'масштаб листа: {field} неточно — код читает копию × {k:.4f}, а оси cfg сходятся с осями копии × {k_cfg:.4f} '
                         f'({ax["matched"]} из {ax["of"]} осей): поле — cfg.SHEET_MM_PER_PT = {ref * k_cfg:.4f} (plan/rules/10 §2)')
    elif ax and ax['status'] == 'unmatched':
        stops.append(f'масштаб листа: оси cfg не сходятся с осями листа, который читает код ({pdf_read}; найдено осей {ax["found_v"]} + {ax["found_h"]}, '
                     f'совпало {ax["matched"]} из {ax["of"]}) ни как есть, ни в другом масштабе: cfg от другого листа или {field} '
                     f'не тот — сверить cfg с листом (review/cfgcheck.py) и поле с probe.py (plan/rules/10 §2, plan/rules/20 §1)')
    elif ax and ax['status'] == 'no-axes':
        notes.append(f'сверка осей cfg с листом не сделана: на листе {pdf_read} не найдено осей по правилу probe.py')
    elif not ax:
        notes.append('сверка осей cfg с листом не сделана: в cfg нет осей AX_X, AX_Y (лист без осей — масштаб только по cfg.MM_PER_PT)')
    if ax and ax['status'] == 'same':
        notes.append(f'оси cfg совпали с осями читаемого листа: {ax["matched"]} из {ax["of"]}')
        # the read sheet is the sheet of cfg: its scale by the axes of cfg must be the reference one on a copy, the field's one in the band
        if k != 1.0 and cfg_mm_per_pt and abs(cfg_mm_per_pt / ref - 1) > 0.02:
            stops.append(f'масштаб листа: {field} неточно — копия × {k:.4f} по полю, оси cfg на ней, но мм между осями дают '
                         f'{cfg_mm_per_pt:.3f} мм/pt вместо {ref:g}: поле — cfg.SHEET_MM_PER_PT = {sheet_mm_per_pt * cfg_mm_per_pt / ref:.4f} '
                         f'(и копия для разметки — с тем же k; plan/rules/10 §2)')
    if k == 1.0 and sheet_mm_per_pt and cfg_mm_per_pt and abs(sheet_mm_per_pt / cfg_mm_per_pt - 1) > 0.02 and not stops:
        stops.append(f'масштаб листа: {field} — лист в полосе {lo:g}–{hi:g} идёт как есть, но поле не сходится с масштабом cfg по осям '
                     f'({cfg_mm_per_pt:.3f} мм/pt): поле убрать или исправить (масштаб самого листа — probe.py; plan/rules/10 §2)')
    return stops, notes, ax


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--copy':
        src, K, out = sys.argv[2], float(sys.argv[3]), sys.argv[4]
        make_copy(src, out, K); print('copy', out, 'k', K, 'sha256', sha256(out)); sys.exit(0)
    route = sys.argv[1] if len(sys.argv) > 1 else 'revit'
    if route == 'ocg':
        sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ocg')); import sheet as S
        cfg_k, sheet_k, pdf, k = S.K, S.SHEET_MM_PER_PT, S.SRC_PDF, S.NORM_K
    else:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import common as S
        cfg_k, sheet_k, pdf, k = S.MM_PER_PT, S.SHEET_MM_PER_PT, S.SRC_PDF, S.NORM_K
    k2, stops, notes = decide(route, cfg_k, sheet_k, pdf)
    axes = None
    if route == 'revit':
        # code 011 (ПК4-П14): the sheet the code reads against cfg - the stops of decide() about the scale of cfg give way to
        #   the ones that name the field when the axes tell which of the two is wrong
        st2, nt2, axes = check_revit(cfg_k, sheet_k, k2, pdf, S.PDF, list(S.AX_X), list(S.AX_Y))
        if st2: stops = st2
        notes += nt2
    res = dict(route=route, ref_mm_per_pt=REF[route], band=BAND[route], cfg_mm_per_pt=cfg_k, sheet_mm_per_pt=sheet_k, k=k2,
               source=pdf, pdf_read=S.PDF, ok=not stops, stops=stops, notes=notes, axes=axes)
    if k2 != 1.0 and os.path.exists('norm.json'):
        res['copy'] = json.load(open('norm.json'))
    json.dump(res, open('norm_decision.json', 'w'), ensure_ascii=False, indent=1)
    if stops:
        print('СТОП масштаб:', '; '.join(stops)); sys.exit(3)
    print('norm:', '; '.join(notes) if notes else f'масштаб cfg {cfg_k:.3f} мм/pt — в полосе маршрута, k = 1, лист как есть')
    sys.exit(0)
