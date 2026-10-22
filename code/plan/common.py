# Common setup for the engineering-plan pipeline. Every script runs with cwd = the floor's work folder,
# which holds cfg.py (per-floor settings) and the source PDF. Coordinates: PDF display space, pt, x right, y down.
import pickle, math, os, sys, importlib
import numpy as np
sys.path.insert(0, os.getcwd())
cfg = importlib.import_module('cfg')
S = getattr(cfg, 'S', 6)                           # raster resolution, px per pt
X0, Y0, X1, Y1 = cfg.WIN                           # drawing window (pt); rasters and diffs use it
W, H = int((X1 - X0) * S), int((Y1 - Y0) * S)
PDF = cfg.PDF; OUT = cfg.OUT                       # source pdf, output prefix (OUT_engineering.dxf/.svg)
DXF = OUT + '_engineering.dxf'; SVG = OUT + '_engineering.svg'
AX_X = list(getattr(cfg, 'AX_X', [])); AX_XMM = list(getattr(cfg, 'AX_XMM', [])); AX_XN = list(getattr(cfg, 'AX_XN', []))
AX_Y = list(getattr(cfg, 'AX_Y', [])); AX_YMM = list(getattr(cfg, 'AX_YMM', [])); AX_YN = list(getattr(cfg, 'AX_YN', []))
if len(AX_X) >= 2 and len(AX_Y) >= 2:              # mm from the grid axes (origin = axes AX_X[0] / AX_Y[0])
    kx = np.polyfit(AX_X, AX_XMM, 1); ky = np.polyfit(AX_Y, AX_YMM, 1)
else:                                              # no grid: scale and origin given in cfg
    k = cfg.MM_PER_PT; ox, oy = cfg.ORIGIN_PT
    kx = np.array([k, -k * ox]); ky = np.array([-k, k * oy])
MM_PER_PT = float(abs(kx[0]))
# (code 010, К-3; №98, row 201) the sheet at the reference scale of the code: a sheet outside 60-70 mm/pt is read as a copy
#   at 63.5 mm/pt made from the source (norm.py: the page x k, k = SHEET_MM_PER_PT / 63.5); cfg of such a floor is in pt of
#   the copy, so the axes above give ~63.5 mm/pt. Inside the band - the sheet as it is (k = 1, PDF and cfg untouched).
#   norm.py (run.sh, step after cfgread) stops a cfg that does not fit the copy; here the copy is only made and read.
SRC_PDF = PDF
SHEET_MM_PER_PT = float(getattr(cfg, 'SHEET_MM_PER_PT', 0) or 0) or None
import norm as _norm
NORM_K = _norm.factor(SHEET_MM_PER_PT, 'revit')
if NORM_K != 1.0 and os.path.exists(SRC_PDF):
    PDF = _norm.ensure_copy(SRC_PDF, NORM_K, 'revit'); cfg.PDF = PDF   # every step and check reads the copy (cfg.PDF too)
# (code 008, №98, Р2) building thresholds of the pipeline were set in pt on sheets of ~63.5 mm/pt (client A). A threshold
#   of the building (a size of an object, a band, a gap between parts) is converted to this sheet: ptb(v) - v pt at
#   63.5 mm/pt; a tolerance of the drawing itself (pen widths, a line's precision) stays in pt. The stop for a scale
#   outside 60-70 mm/pt (plan/rules/10 §2) is lifted for the thresholds converted so far (list - plan/code/90, 008)
REF_MM_PER_PT = 63.5
def ptb(v): return v * REF_MM_PER_PT / MM_PER_PT
def MM(p): return (float(np.polyval(kx, p[0])), float(np.polyval(ky, p[1])))
def T(p): return (int(round((p[0] - X0) * S)), int(round((p[1] - Y0) * S)))
def bez(g, n=12):
    out = []
    for t in np.linspace(0, 1, n):
        out.append(((1 - t) ** 3 * g[0][0] + 3 * (1 - t) ** 2 * t * g[1][0] + 3 * (1 - t) * t * t * g[2][0] + t ** 3 * g[3][0],
                    (1 - t) ** 3 * g[0][1] + 3 * (1 - t) ** 2 * t * g[1][1] + 3 * (1 - t) * t * t * g[2][1] + t ** 3 * g[3][1]))
    return out
def pts(p):
    k, w, sc, fc, g, di = p
    if k == 'l': return list(g)
    if k == 'c': return bez(g)
    return list(g) + [g[0]]
def load(): return pickle.load(open('seq.pkl', 'rb'))[0]
def inboxes(b, boxes):
    """bbox b=(x0,y0,x1,y1) lies inside one of the boxes"""
    return any(b[0] >= z[0] and b[2] <= z[2] and b[1] >= z[1] and b[3] <= z[3] for z in boxes)
def mm_len(pt_len): return pt_len * MM_PER_PT
def pt_len(mm): return mm / MM_PER_PT
def is_tan(c):
    """desk / worktop fill: colours listed in cfg.DESK_FILLS (+-0.02), else a warm light colour"""
    if c is None: return False
    lst = getattr(cfg, 'DESK_FILLS', None)
    if lst: return any(max(abs(c[j] - t[j]) for j in range(3)) < 0.02 for t in lst)
    if any(max(abs(c[j] - t[j]) for j in range(3)) < 0.02 for t in getattr(cfg, 'DESK_FILLS_EXTRA', [])): return True   # floor 4: light green desks
    return c[0] >= 0.75 and c[1] >= 0.65 and c[2] <= 0.78 and c[0] - c[2] >= 0.08
FACADES = [list(f) for f in getattr(cfg, 'FACADES', [])] or ([list(cfg.FACADE)] if getattr(cfg, 'FACADE', None) else [])
def facade_lines():
    from shapely.geometry import LineString
    return [LineString(f) for f in FACADES if len(f) >= 2]
def facade_band_widths(default):
    """half width (pt) of the glazing band of each facade line: cfg.FACADE_BANDS {index: pt} over cfg.FACADE_BAND
    (floor 4: the narrow stair glazing between two hatched wall stubs - a 14 pt band took the stub's hatch)"""
    fb = getattr(cfg, 'FACADE_BANDS', {})
    return [fb.get(i, default) for i in range(len(FACADES)) if len(FACADES[i]) >= 2]
def facade_band(default):
    """the glazing band: each facade line buffered by its half width. A line with its own width (cfg.FACADE_BANDS) ends
    flat (28.09.2026): it runs up to the walls it meets (floor 4: the stair glazing between two hatched stubs), and a
    round end would reach into them"""
    from shapely.ops import unary_union
    fb = getattr(cfg, 'FACADE_BANDS', {})
    idx = [i for i in range(len(FACADES)) if len(FACADES[i]) >= 2]
    return unary_union([ln.buffer(w, cap_style=2 if k in fb else 1) for k, ln, w in zip(idx, facade_lines(), facade_band_widths(default))])
def facade_multi():
    from shapely.geometry import MultiLineString
    return MultiLineString([list(f) for f in FACADES if len(f) >= 2]) if FACADES else None
# curved-wall zones (cfg.CURVED_ZONES): a box (x0,y0,x1,y1) or a band (centre polyline [(x,y),...], half width) -
#   a box around a big arc (floor 1, east facade) would also take the furniture inside it
def _curved_geoms():
    from shapely.geometry import LineString, box
    out = []
    for z in getattr(cfg, 'CURVED_ZONES', []):
        if len(z) == 4 and all(isinstance(v, (int, float)) for v in z): out.append(('box', z))
        else: out.append(('band', LineString(z[0]).buffer(z[1], cap_style=2)))
    return out
_CG = None
def in_curved(p):
    global _CG
    if _CG is None:
        from shapely.prepared import prep
        _CG = [(k, g if k == 'box' else prep(g)) for k, g in _curved_geoms()]
    from shapely.geometry import Point
    for k, g in _CG:
        if k == 'box':
            if g[0] <= p[0] <= g[2] and g[1] <= p[1] <= g[3]: return True
        elif g.contains(Point(p[0], p[1])): return True
    return False
from common_cfg import arc_points
_ZG = {}
def zone_contains(name, p):
    """point in any zone of cfg.<name>: boxes (x0,y0,x1,y1) or bands (centre polyline, half width)"""
    if name not in _ZG:
        from shapely.geometry import LineString
        from shapely.prepared import prep
        out = []
        for z in getattr(cfg, name, []):
            if len(z) == 4 and all(isinstance(v, (int, float)) for v in z): out.append(('box', z))
            else: out.append(('band', prep(LineString(z[0]).buffer(z[1], cap_style=2))))
        _ZG[name] = out
    from shapely.geometry import Point
    for k, g in _ZG[name]:
        if k == 'box':
            if g[0] <= p[0] <= g[2] and g[1] <= p[1] <= g[3]: return True
        elif g.contains(Point(p[0], p[1])): return True
    return False

def walls_file():
    """the final walls: walls_fixed.pkl (geomfix.py) when it is newer than walls.pkl, else walls.pkl"""
    if os.path.exists('walls_fixed.pkl') and os.path.getmtime('walls_fixed.pkl') >= os.path.getmtime('walls.pkl'):
        return 'walls_fixed.pkl'
    return 'walls.pkl'
