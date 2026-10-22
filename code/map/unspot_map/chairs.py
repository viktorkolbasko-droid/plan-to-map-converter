"""Chairs of the sheet - found apart from the desk search (canon-proposals client A 4, G1-1; map/rules/80 Ch-31; map/rules/82 §0).

Why: Ch-29 compares artifact 3 with the places JSON, not with the sheet. On client A 4, run 1 found desks by one fill
colour and gave a place to 67 % of the chairs; Ch-29 passed. A chair list built independently of the desk search makes
the gap visible: every chair outside a meeting room is a place or gets a verdict "not a place" (lounge, canteen, counter).

How: the chair class of the sheet (map/rules/11 §1, class table: stroke colour and width, or fill colour) -> a mask in px of
work.png -> long straight runs removed (axes, dimension lines, desk edges) -> components of chair size 0.35-0.85 m;
a component with two chairs side by side is split in two. The class is chosen by the author from the class table:
the detector does not guess it.

    python3 -m unspot_map.chairs --pdf sheet.pdf --intake intake.json --stroke 0.67,0.67,0.67 --width 0.24 --px-per-m 43.73 --out chairs.json
    python3 -m unspot_map.chairs --pdf sheet.pdf --intake intake.json --fill 0.97 --px-per-m 43.73 --out chairs.json
    python3 -m unspot_map.chairs --png work.png --rgb 120,120,120 --tol 40 --px-per-m 43.73 --out chairs.json

Output: {"frame": "source", "px_per_m": ..., "how": ..., "chairs": [[x, y], ...]} - px of work.png, the input of
acceptance_checks.py --chairs-json. Checked 02.10.2026 on client A 4 (class 0.24 grey 0.67): 258 chairs of the
reference list within 0.6 m - see the pass report of the merge.
v008 (OV2, OV9): --desk-fill - a chair-size piece on the desk fill of the sheet is a desk end module or a joint of table tops, not a
chair; --join-m - a chair drawn in pieces is assembled into one. Both are keys: without them the detector is as in v007."""
import argparse, json, math
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage


def _colour(v):
    return tuple(float(x) for x in str(v).split(',')) if v not in (None, '') else None


def mask_from_pdf(pdf, page_no, to_pixels, size, stroke=None, width=None, fill=None, tol=0.02, wtol=0.02, max_side_px=None, layer=None):
    """paths of one class -> bool mask (H, W) in px of work.png; to_pixels - intake.json render.to_pixels (pymupdf Matrix).
    v011 (PK4-K4): max_side_px - a path of the class longer than this (a desk or a bench of the same fill) is not a chair part;
    layer - only paths of this layer (OCG) of the sheet"""
    import pymupdf
    doc = pymupdf.open(pdf); page = doc[page_no - 1]; a, b, c, d, e, f = to_pixels
    T = lambda p: (a * p.x + c * p.y + e, b * p.x + d * p.y + f)
    near = lambda col, ref: col is not None and len(col) == len(ref) and max(abs(u - v) for u, v in zip(col, ref)) <= tol
    im = Image.new('L', tuple(size), 0); g = ImageDraw.Draw(im); n = 0
    for x in page.get_drawings():
        if stroke is not None and not (near(x.get('color'), stroke) and (width is None or abs((x.get('width') or 0) - width) <= wtol)): continue
        if fill is not None and not near(x.get('fill'), fill): continue
        if stroke is None and fill is None: continue
        if layer is not None and x.get('layer') != layer: continue
        if max_side_px is not None and max(x['rect'].width, x['rect'].height) * math.hypot(a, b) > max_side_px: continue
        n += 1
        for it in x['items']:
            if it[0] == 'l': g.line([T(it[1]), T(it[2])], fill=255, width=1)
            elif it[0] == 'c': g.line([T(q) for q in it[1:5]], fill=255, width=1)
            elif it[0] in ('re', 'qu'):
                r = it[1]; poly = [T(r.tl), T(r.tr), T(r.br), T(r.bl)] if it[0] == 're' else [T(r.ul), T(r.ur), T(r.lr), T(r.ll)]
                if fill is not None: g.polygon(poly, fill=255)
                else: g.line(poly + [poly[0]], fill=255, width=1)
    return np.asarray(im) > 0, n


def mask_from_png(png, rgb, tol=40):
    c = np.asarray(Image.open(png).convert('RGB')).astype(int)
    return np.all(np.abs(c - np.array(rgb)) <= tol, axis=2)


def detect(mask, px_per_m, lo=0.35, hi=0.85, aspect=1.6, run_m=0.95, exclude=None, join_m=0.0, share=0.5):
    """chair-size components: (x, y) centres in mask px. Straight runs longer than run_m are removed first.
    v008: exclude - desk fill of the sheet (bool mask): a component lying on it by share or more is a desk end module or a joint of
    table tops, not a chair (OV2); join_m - pieces of one chair closer than join_m are assembled into one component (OV9)."""
    k = max(9, int(run_m * px_per_m))
    hl = ndimage.binary_opening(mask, np.ones((1, k))); vl = ndimage.binary_opening(mask, np.ones((k, 1)))
    b = mask & ~ndimage.binary_dilation(hl | vl, iterations=1)
    it = max(1, int(round(join_m * px_per_m / 2)))
    lab, n = ndimage.label(ndimage.binary_dilation(b, iterations=it), structure=np.ones((3, 3)))
    out = []
    for i_, sl in enumerate(ndimage.find_objects(lab)):
        if exclude is not None:
            m_ = lab[sl] == i_ + 1
            if m_.any() and float(exclude[sl][m_].mean()) >= share: continue
        h = (sl[0].stop - sl[0].start) / px_per_m; w = (sl[1].stop - sl[1].start) / px_per_m
        cy, cx = (sl[0].start + sl[0].stop) / 2, (sl[1].start + sl[1].stop) / 2
        if lo <= w <= hi and lo <= h <= hi and max(w, h) / min(w, h) < aspect: out.append((cx, cy))
        elif hi < w <= 2 * hi and lo <= h <= hi: out += [(cx - w * px_per_m / 4, cy), (cx + w * px_per_m / 4, cy)]   # two chairs side by side
        elif hi < h <= 2 * hi and lo <= w <= hi: out += [(cx, cy - h * px_per_m / 4), (cx, cy + h * px_per_m / 4)]
    return [(round(float(x), 1), round(float(y), 1)) for x, y in out]


def main():
    ap = argparse.ArgumentParser(description='chairs of the sheet -> chairs.json for acceptance_checks.py --chairs-json')
    ap.add_argument('--pdf'); ap.add_argument('--page', type=int); ap.add_argument('--intake', help='intake.json of source_intake.py')
    ap.add_argument('--png', help='work.png: chairs by colour'); ap.add_argument('--rgb'); ap.add_argument('--tol', type=float, default=40)
    ap.add_argument('--stroke', help='stroke colour r,g,b 0-1'); ap.add_argument('--width', type=float); ap.add_argument('--fill', help='fill colour r,g,b or grey 0-1')
    ap.add_argument('--px-per-m', type=float, required=True, help='px of work.png per metre'); ap.add_argument('--out', required=True)
    ap.add_argument('--lo', type=float, default=0.35); ap.add_argument('--hi', type=float, default=0.85)
    ap.add_argument('--desk-fill', help='v008 (OV2): desk fill colour of the sheet r,g,b 0-1 (PDF) - a chair-size piece on it is a desk module, not a chair')
    ap.add_argument('--join-m', type=float, default=0.0, help='v008 (OV9): pieces of one chair closer than this, m, are one chair')
    ap.add_argument('--max-path-m', type=float, help='v011 (PK4-K4): a path of the class longer than this, m, is not a chair part (desk or bench of the same fill)')
    ap.add_argument('--layer', help='v011: only paths of this layer (OCG) of the sheet')
    a = ap.parse_args()
    if a.pdf:
        it = json.load(open(a.intake, encoding='utf-8')); r = it['render']
        fill = _colour(a.fill); fill = fill * 3 if fill and len(fill) == 1 else fill
        m, n = mask_from_pdf(a.pdf, a.page or it.get('chosen_page', 1), r['to_pixels'], r['work_size'], _colour(a.stroke), a.width, fill,
                             max_side_px=a.max_path_m * a.px_per_m if a.max_path_m else None, layer=a.layer)
        how = f'PDF: класс stroke={a.stroke} width={a.width} fill={a.fill}' + (f' слой «{a.layer}»' if a.layer else '') + (f', пути не длиннее {a.max_path_m} м' if a.max_path_m else '') + f', путей {n}'
    else:
        m = mask_from_png(a.png, _colour(a.rgb), a.tol); how = f'растр: цвет {a.rgb} ± {a.tol}'
    ex = None
    if a.desk_fill and a.pdf:
        df = _colour(a.desk_fill); df = df * 3 if len(df) == 1 else df
        ex, ne = mask_from_pdf(a.pdf, a.page or it.get('chosen_page', 1), r['to_pixels'], r['work_size'], fill=df); how += f'; без заливки столов {a.desk_fill} ({ne})'
    if a.join_m: how += f'; куски стула в {a.join_m} м — один стул'
    ch = detect(m, a.px_per_m, a.lo, a.hi, exclude=ex, join_m=a.join_m)
    json.dump(dict(frame='source', px_per_m=a.px_per_m, how=how, chairs=[list(c) for c in ch]), open(a.out, 'w', encoding='utf-8'), ensure_ascii=False, indent=0)
    print(json.dumps(dict(chairs=len(ch), how=how), ensure_ascii=False))


if __name__ == '__main__':
    main()
