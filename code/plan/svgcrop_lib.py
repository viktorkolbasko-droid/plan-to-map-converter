import re, cairosvg
from common import kx, ky, SVG

_cache = {}


def _load(src):
    if src not in _cache:
        s = open(src).read()
        m = re.search(r'translate\(([-\d.]+),([-\d.]+)\) scale\(1,-1\)', s)
        _cache[src] = (s, float(m.group(1)), float(m.group(2)))
    return _cache[src]


def crop(x0, y0, x1, y1, W, out, src=SVG):
    """Render the SVG window given in PDF pt (display page coords) to a PNG of width W."""
    s, TX, TY = _load(src)

    def mm(p):
        return (float(kx[0] * p[0] + kx[1]), float(ky[0] * p[1] + ky[1]))

    a = mm((x0, y0)); b = mm((x1, y1))
    X0 = min(a[0], b[0]) + TX; X1 = max(a[0], b[0]) + TX
    Y0 = TY - max(a[1], b[1]); Y1 = TY - min(a[1], b[1])
    s2 = re.sub(r'viewBox="[^"]+" width="[^"]+" height="[^"]+"',
                f'viewBox="{X0:.0f} {Y0:.0f} {X1 - X0:.0f} {Y1 - Y0:.0f}"', s, count=1)
    cairosvg.svg2png(bytestring=s2.encode(), write_to=out, output_width=W)


# ---- fast crop (code 007, 05.10.2026): cairosvg parses the whole drawing for every window - about a minute on a 3 MB
#      floor. Elements far from the window are dropped first (lines, polylines, paths, block references by their
#      insertion point and the block's extent, texts), the rest is rendered as crop() does.
import xml.etree.ElementTree as _ET
_fast = {}
_NS = {'svg': 'http://www.w3.org/2000/svg'}
_NUM = re.compile(r'-?\d+(?:\.\d+)?(?:e-?\d+)?')


def _bb_nums(nums):
    xs = nums[0::2]; ys = nums[1::2]
    return (min(xs), min(ys), max(xs), max(ys)) if xs and ys else None


def _load_fast(src):
    if src not in _fast:
        s = open(src).read()
        m = re.search(r'translate\(([-\d.]+),([-\d.]+)\) scale\(1,-1\)', s)
        TX, TY = float(m.group(1)), float(m.group(2))
        _ET.register_namespace('', 'http://www.w3.org/2000/svg')
        _ET.register_namespace('inkscape', 'http://www.inkscape.org/namespaces/inkscape')
        root = _ET.fromstring(s)
        ext = {}                                    # block id -> radius of its geometry around the insertion point
        for g in root.iter('{http://www.w3.org/2000/svg}g'):
            gid = g.get('id', '')
            if not gid.startswith('b'): continue
            r = 0.0
            for e in g.iter():
                nums = [float(v) for k_ in ('x1', 'y1', 'x2', 'y2', 'points', 'd', 'cx', 'cy') if e.get(k_) for v in _NUM.findall(e.get(k_))]
                if nums: r = max(r, max(abs(v) for v in nums))
            ext[gid] = r
        _fast[src] = (root, TX, TY, ext)
    return _fast[src]


def crop_fast(x0, y0, x1, y1, W, out, src=SVG, margin=1500.0):
    """crop() with the elements outside the window (+ margin mm) left out before rendering"""
    root, TX, TY, ext = _load_fast(src)

    def mm(p):
        return (float(kx[0] * p[0] + kx[1]), float(ky[0] * p[1] + ky[1]))

    a = mm((x0, y0)); b = mm((x1, y1))
    WX0, WX1 = min(a[0], b[0]) - margin, max(a[0], b[0]) + margin
    WY0, WY1 = min(a[1], b[1]) - margin, max(a[1], b[1]) + margin

    def keep_mm(bb):
        return bb is not None and not (bb[2] < WX0 or bb[0] > WX1 or bb[3] < WY0 or bb[1] > WY1)

    import copy
    r2 = copy.deepcopy(root)
    for g in r2.iter('{http://www.w3.org/2000/svg}g'):
        gid = g.get('id', '')
        if gid == 'blocks' or gid.startswith('b'): continue
        for e in list(g):
            tag = e.tag.split('}')[-1]
            if tag == 'g': continue
            bb = None
            if tag == 'line':
                bb = _bb_nums([float(e.get(k_)) for k_ in ('x1', 'y1', 'x2', 'y2')])
            elif tag in ('polyline', 'polygon'):
                bb = _bb_nums([float(v) for v in _NUM.findall(e.get('points', ''))])
            elif tag == 'path':
                bb = _bb_nums([float(v) for v in _NUM.findall(e.get('d', ''))])
            elif tag == 'circle':
                c_ = (float(e.get('cx')), float(e.get('cy'))); r_ = float(e.get('r'))
                bb = (c_[0] - r_, c_[1] - r_, c_[0] + r_, c_[1] + r_)
            elif tag == 'use':
                m_ = re.search(r'translate\(([-\d.]+),([-\d.]+)\)', e.get('transform', ''))
                if m_:
                    ref = (e.get('href') or e.get('{http://www.w3.org/1999/xlink}href') or '').lstrip('#')
                    r_ = ext.get(ref, 5000.0); x_, y_ = float(m_.group(1)), float(m_.group(2))
                    bb = (x_ - r_, y_ - r_, x_ + r_, y_ + r_)
            elif tag == 'text':                         # texts are outside the flipped drawing group: back to mm
                X, Y = float(e.get('x', 0)), float(e.get('y', 0))
                mx, my = X - TX, TY - Y
                bb = (mx - 3000, my - 1000, mx + 3000, my + 1000)
            if bb is not None and not keep_mm(bb): g.remove(e)
    s = _ET.tostring(r2, encoding='unicode')
    X0 = min(a[0], b[0]) + TX; X1 = max(a[0], b[0]) + TX
    Y0 = TY - max(a[1], b[1]); Y1 = TY - min(a[1], b[1])
    s2 = re.sub(r'viewBox="[^"]+" width="[^"]+" height="[^"]+"',
                f'viewBox="{X0:.0f} {Y0:.0f} {X1 - X0:.0f} {Y1 - Y0:.0f}"', s, count=1)
    cairosvg.svg2png(bytestring=s2.encode(), write_to=out, output_width=W)
