"""Wall-body mask of a vector sheet by a fixed recipe (map/rules/80 Ch-10, Ch-11; N23, T4-1, T4-2, E12, OV13; code v008, package 2).

Why: one map gave Ch-10 93.6 % or 95.1 % depending on a hand-made mask recipe, maps of two tests lost 15-30 points on each other's masks
(client-b, 40th floor, test 4, N23): while the mask is not code, Ch-10 is not a measure. This builder has ONE recipe; its id, parameters
and the SHA-256 of the mask go to the Ch-10 row and the pass report. A mask 'of one's own for a test' only with an entry in the impact log.

Recipe wm1 (classes of the sheet are chosen by the author from the class table, map/rules/11 §1 - the builder does not guess them):
  1. wall, column and glass classes -> ink at work.png scale (fills as polygons, strokes at their width, at least 1 px);
  2. wall faces are closed by a disk of the thin-wall thickness t_m: a wall drawn by two faces without an axis between them is a solid body
     ('D' p. 2: closing by 3.5 pt raised Ch-10 95.4 -> 97.4 % on the same map);
  3. massif (core, pylon) - by the sheet itself, not by a class name: wall body deeper than t_m from its faces (a body thicker than 2 t_m);
     ONLY a band t_m at the faces is wall body (T4-2, N24): a wall drawn inside the massif deeper than t_m from the face is off the body and
     the acceptance lists it as 'wall inside the massif' (look) when it runs along the face; a wall across the massif (a section of the
     massif along a neighbour wall, E6) is not listed. The rest of the massif is written as value 100: not body, 'massif' for the
     acceptance. An optional hatched class --massif (a massif drawn by hatch only) is closed into a region and added to the body first.
     Chosen on the stand of package 2 against 'massif outside the mask, faces as a separate input' (E12): one input, the same Ch-10, Ch-11.
Values of the PNG: 255 - wall body, 100 - massif interior (not body), 0 - other. acceptance_checks.py --wall-mask reads > 127 as body,
65..127 as massif; the sidecar <mask>.json gives the recipe and hashes.

    python3 -m unspot_map.wall_mask --pdf sheet.pdf --intake intake.json --px-per-m 57.87 --t-m 0.17 \\
        --wall 'layer=PDF _Стены наружные' --wall 'layer=PDF _Стены внутренние' --wall 'layer=PDF _Стены' \\
        --glass 'fill=0,1,1' --massif 'layer=PDF _Узлы' --out mask.png        # -> mask.png, mask.json"""
import argparse, hashlib, json, math, os
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

RECIPE = 'wm1'


def _cls(s):
    """'layer=…' | 'stroke=r,g,b[;width=w]' | 'fill=r,g,b' -> dict"""
    out = {}
    for part in str(s).split(';'):
        k, _, v = part.partition('=')
        k = k.strip()
        if k == 'layer': out['layer'] = v
        elif k in ('stroke', 'fill'): out[k] = tuple(float(x) for x in v.split(','))
        elif k == 'width': out['width'] = float(v)
    return out


def _match(x, c, tol=0.02):
    near = lambda col, ref: col is not None and len(col) == len(ref) and max(abs(u - v) for u, v in zip(col, ref)) <= tol
    if 'layer' in c and (x.get('layer') or '') != c['layer']: return False
    if 'stroke' in c and not near(x.get('color'), c['stroke']): return False
    if 'width' in c and abs((x.get('width') or 0) - c['width']) > 0.02: return False
    if 'fill' in c and not near(x.get('fill'), c['fill']): return False
    return True


def _draw(D, T, size, classes, scale):
    """drawings of the classes -> L image 0/255 (fills as polygons, strokes at their width in px, >= 1)"""
    im = Image.new('L', tuple(size), 0); g = ImageDraw.Draw(im); n = 0
    for x in D:
        if not any(_match(x, c) for c in classes): continue
        n += 1; w = max(1, int(round((x.get('width') or 0) * scale))); fill = x.get('fill') is not None; stroke = x.get('color') is not None
        for it in x['items']:
            if it[0] == 'l': pts = [T(it[1]), T(it[2])]
            elif it[0] == 'c': pts = [T(q) for q in it[1:5]]
            elif it[0] == 're': r = it[1]; pts = [T(r.tl), T(r.tr), T(r.br), T(r.bl)]
            elif it[0] == 'qu': q = it[1]; pts = [T(q.ul), T(q.ur), T(q.lr), T(q.ll)]
            else: continue
            if fill and len(pts) >= 3: g.polygon(pts, fill=255)
            if stroke or not fill: g.line(pts + ([pts[0]] if it[0] in ('re', 'qu') else []), fill=255, width=w)
        if fill:                                                              # a filled path made of 'l' items: one polygon
            poly = [T(it[1]) for it in x['items'] if it[0] == 'l']
            if len(poly) >= 3: g.polygon(poly, fill=255)
    return np.asarray(im) > 0, n


def _disk(px):
    r = max(1, int(round(px / 2))); y, x = np.ogrid[-r:r + 1, -r:r + 1]; return x * x + y * y <= r * r


def build(pdf, intake, px_per_m, t_m, wall, glass=(), massif=(), massif_close_m=0.35, page=None):
    import pymupdf
    it = json.load(open(intake, encoding='utf-8')); r = it['render']; a, b, c, d, e, f = r['to_pixels']; size = r['work_size']
    T = lambda p: (a * p.x + c * p.y + e, b * p.x + d * p.y + f); scale = math.sqrt(abs(a * d - b * c))
    doc = pymupdf.open(pdf); pg = doc[(page or it.get('chosen_page', 1)) - 1]; D = pg.get_drawings()
    W_, nw = _draw(D, T, size, wall, scale)
    G_, ng = _draw(D, T, size, glass, scale) if glass else (np.zeros(W_.shape, bool), 0)
    k = t_m * px_per_m
    try:
        import cv2
        close = lambda m, px: cv2.morphologyEx(m.astype(np.uint8), cv2.MORPH_CLOSE, _disk(px).astype(np.uint8)) > 0
        erode = lambda m, px: cv2.erode(m.astype(np.uint8), _disk(2 * px).astype(np.uint8)) > 0
    except ImportError:
        close = lambda m, px: ndimage.binary_closing(m, _disk(px)) | m
        erode = lambda m, px: ndimage.binary_erosion(m, _disk(2 * px))
    B = close(W_, k); nm = 0                                                 # step 2: faces closed by the thin-wall thickness
    if massif:                                                               # a hatched massif class (optional): hatch -> region, gaps < 0.25 m² filled
        H_, nm = _draw(D, T, size, massif, scale); C = close(H_, massif_close_m * px_per_m); hl, nh = ndimage.label(ndimage.binary_fill_holes(C) & ~C)
        if nh:
            sz = ndimage.sum(np.ones_like(hl), hl, range(1, nh + 1)); C = C | np.isin(hl, np.flatnonzero(sz < 0.25 * px_per_m ** 2) + 1)
        B = B | C
    Dp = ndimage.distance_transform_edt(B)                                   # step 3: depth inside the body
    M = Dp > k                                                               # deeper than t_m from a face: only in a body thicker than 2 t_m - massif, pylon
    body = (B & ~M) | G_                                                     # wall body = a band t_m at every face (T4-2, N24)
    out = np.zeros(W_.shape, np.uint8); out[M & ~body] = 100; out[body] = 255
    return out, dict(recipe=RECIPE, t_m=t_m, massif_close_m=massif_close_m, px_per_m=px_per_m, wall=[_ser(c) for c in wall], glass=[_ser(c) for c in glass],
                     massif=[_ser(c) for c in massif], paths=dict(wall=nw, glass=ng, massif=nm), size=list(size),
                     body_share=round(float((out == 255).mean()), 5), massif_share=round(float((out == 100).mean()), 5))


def _ser(c):
    return {k: (list(v) if isinstance(v, tuple) else v) for k, v in c.items()}


def mask_sha(arr):
    """SHA-256 of the mask values (not of the PNG bytes: the encoder may differ): shape + values 0 / 100 / 255"""
    a = np.asarray(arr, np.uint8); return hashlib.sha256(f'{a.shape[1]}x{a.shape[0]}:'.encode() + a.tobytes()).hexdigest()


def read_meta(mask_png):
    """the sidecar of a mask: <mask>.json -> dict or None"""
    p = os.path.splitext(mask_png)[0] + '.json'
    try: return json.load(open(p, encoding='utf-8'))
    except (OSError, ValueError): return None


def main():
    ap = argparse.ArgumentParser(description='wall-body mask of a vector sheet by the fixed recipe wm1 -> mask.png + mask.json')
    ap.add_argument('--pdf', required=True); ap.add_argument('--intake', required=True); ap.add_argument('--page', type=int)
    ap.add_argument('--px-per-m', type=float, required=True, help='px of work.png per metre')
    ap.add_argument('--t-m', type=float, required=True, help='thin-wall thickness of the sheet, m: closing of faces and the massif band')
    ap.add_argument('--wall', action='append', default=[], help="class: 'layer=…' | 'stroke=r,g,b;width=w' | 'fill=r,g,b'")
    ap.add_argument('--glass', action='append', default=[]); ap.add_argument('--massif', action='append', default=[])
    ap.add_argument('--massif-close-m', type=float, default=0.35, help='hatch spacing of the massif class, m: closing into a region')
    ap.add_argument('--out', required=True)
    x = ap.parse_args()
    if not x.wall: raise SystemExit('wall_mask: no wall class (--wall): the builder does not guess classes')
    m, meta = build(x.pdf, x.intake, x.px_per_m, x.t_m, [_cls(s) for s in x.wall], [_cls(s) for s in x.glass], [_cls(s) for s in x.massif], x.massif_close_m, x.page)
    Image.fromarray(m).save(x.out)
    meta.update(mask_sha256=mask_sha(m), png_sha256=hashlib.sha256(open(x.out, 'rb').read()).hexdigest(),
                source_sha256=hashlib.sha256(open(x.pdf, 'rb').read()).hexdigest())
    json.dump(meta, open(os.path.splitext(x.out)[0] + '.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(json.dumps({k: meta[k] for k in ('recipe', 'mask_sha256', 'body_share', 'massif_share', 'paths')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
