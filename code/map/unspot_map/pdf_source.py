"""Source assembly for a PDF page that carries raster images (extends map/rules/10 §5.1).

A page is not "one picture". On the client C sheet a page held:
  * the main plan raster (789 x 669 px for a whole floor);
  * pasted raster patches with their own transforms - rotated and mirrored furniture (9 on floor 15);
  * a vector text layer - room numbers and the client's seat numbers (exact, no OCR needed);
  * vector line art - callout boxes and leaders of the client;
  * annotations - FreeText "these desks are not added to the map", a Line arrow and an ink loop (Stamp).
v1 took the patches without their transforms: the meeting table of 15.05 and the artifact-3 underlay were wrong.

Rules this module implements:
  * inventory the page first (images with transforms, text, drawings, annotations) and report it;
  * the page render with transforms applied (MuPDF) is the source for furniture, desks and the underlay;
  * masks (desks, chairs) come from the render WITHOUT text and annotations;
  * the underlay of artifact 3 comes from the render WITH text (seat numbers visible), without client markup;
  * annotations are client instructions: they go to the plan card and change what is drawn or placed.
"""
import re
import numpy as np
import cv2
import fitz  # PyMuPDF

from .frame import Affine


def inventory(doc, pno):
    """what the page is made of; put this table into the pass report"""
    p = doc[pno]
    imgs = []
    for im in p.get_image_info(xrefs=True):
        a, b, c, d, e, f = im['transform']
        imgs.append(dict(xref=im['xref'], bbox=[round(v, 1) for v in im['bbox']],
                         size=(im['width'], im['height']),
                         rotation_deg=round(float(np.degrees(np.arctan2(b, a))), 1),
                         mirrored=(a * d - b * c) < 0,
                         transform=[round(v, 3) for v in im['transform']]))
    colors = {}
    for blk in p.get_text('dict')['blocks']:
        for line in blk.get('lines', []):
            for s in line['spans']:
                k = '#%06X' % s['color']; colors[k] = colors.get(k, 0) + 1
    annots = [dict(type=a.type[1], rect=[round(v, 1) for v in a.rect],
                   content=(a.info.get('content') or '').replace('\u2028', ' ').strip())   # U+2028 — разделитель строк в тексте аннотации
              for a in (p.annots() or [])]
    return dict(page=pno, size_pt=(p.rect.width, p.rect.height), images=imgs,
                n_words=len(p.get_text('words')), text_colors=colors,
                n_drawings=len(p.get_drawings()), annotations=annots)


def render(pdf_path, pno, zoom=4.0, text=True, annots=False):
    """BGR page render with image transforms applied.
    text=False removes the text layer (images and line art stay) - use it for colour masks.
    annots=False drops the client markup (the markup is read separately with inventory())."""
    d = fitz.open(pdf_path); p = d[pno]
    if not text:
        for blk in p.get_text('dict')['blocks']:
            for line in blk.get('lines', []):
                for s in line['spans']:
                    p.add_redact_annot(fitz.Rect(s['bbox']), fill=False)
        p.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE,
                           graphics=fitz.PDF_REDACT_LINE_ART_NONE,
                           text=fitz.PDF_REDACT_TEXT_REMOVE)
    if not annots:
        for a in list(p.annots() or []):
            p.delete_annot(a)
    pix = p.get_pixmap(matrix=fitz.Matrix(zoom, zoom), annots=annots)
    img = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, pix.n)[:, :, :3]
    return img[:, :, ::-1].copy()


def main_image(doc, pno):
    """the largest image of the page and the affine page pt -> its pixels"""
    info = doc[pno].get_image_info(xrefs=True)
    im = max(info, key=lambda i: (i['bbox'][2] - i['bbox'][0]) * (i['bbox'][3] - i['bbox'][1]))
    a, b, c, d, e, f = im['transform']                       # unit square -> page
    unit_to_page = Affine([[a, c, e], [b, d, f], [0, 0, 1]])
    px_to_unit = Affine.scale_shift(1.0 / im['width'], 1.0 / im['height'])
    return im, (unit_to_page @ px_to_unit).inv()             # page -> image px


def render_in_frame(render_img, zoom, page_to_frame, size):
    """warp a page render (zoom px per pt) into a raster frame of `size` (W, H); pixel k covers [k, k+1)"""
    page_to_render = Affine.scale_shift(zoom, zoom)
    frame_to_render = page_to_render @ page_to_frame.inv()
    c = Affine.scale_shift(1, 1, 0.5, 0.5); ci = Affine.scale_shift(1, 1, -0.5, -0.5)
    M = ci @ frame_to_render @ c
    return cv2.warpAffine(render_img, M.M[:2], size, flags=cv2.WARP_INVERSE_MAP | cv2.INTER_AREA,
                          borderValue=(255, 255, 255))


def patch_regions(main_raster, render_frame, thr=60, min_area=300):
    """where the page differs from its main raster: pasted patches, callouts, line art (x, y, w, h)"""
    d = np.abs(render_frame.astype(int) - main_raster.astype(int)).mean(2)
    m = cv2.dilate((d > thr).astype(np.uint8), np.ones((5, 5), np.uint8))
    n, lab, st, _ = cv2.connectedComponentsWithStats(m)
    return [tuple(int(v) for v in st[k, :4]) for k in range(1, n) if st[k, 4] >= min_area]


def words(doc, pno, page_to_frame):
    """text layer in a frame: dict(t, x, y, h) at the word centre"""
    out = []
    for x0, y0, x1, y1, t, *_ in doc[pno].get_text('words'):
        X, Y = page_to_frame([((x0 + x1) / 2, (y0 + y1) / 2)])[0]
        out.append(dict(t=t, x=float(X), y=float(Y), h=float((y1 - y0) * page_to_frame.scale()),
                        w=float((x1 - x0) * page_to_frame.scale())))
    return out


def seat_numbers(ws, inside=None, glued=True):
    """client seat numbers. A 4-digit token is two glued 2-digit numbers (client C: '1516').
    `inside(x, y)` filters out legends and callouts outside the building."""
    out = []
    for w in ws:
        t = w['t']
        if glued and re.fullmatch(r'\d{4}', t):
            for n, dx in ((t[:2], -w['w'] / 4), (t[2:], w['w'] / 4)):
                out.append(dict(n=int(n), x=w['x'] + dx, y=w['y']))
        elif re.fullmatch(r'\d{1,3}', t):
            out.append(dict(n=int(t), x=w['x'], y=w['y']))
    if inside is not None:
        out = [s for s in out if inside(s['x'], s['y'])]
    return out


def check_seat_list(seats):
    """numbers must form the client's list: no duplicates, no gaps (map/rules/61 §1 'список исходника')"""
    ns = sorted(s['n'] for s in seats)
    dups = sorted({n for n in ns if ns.count(n) > 1})
    gaps = [n for n in range(ns[0], ns[-1] + 1) if n not in ns] if ns else []
    return dict(count=len(ns), first=ns[0] if ns else None, last=ns[-1] if ns else None, duplicates=dups, gaps=gaps)
