# Compare two runs of the same floor (reproducibility check, plan/rules/60 §10).
# Usage: python3 compare_runs.py RUN_A RUN_B [out_prefix]   (run folders with walls.pkl, inst_final.pkl, *_engineering.dxf)
import sys, os, glob, json, math, pickle, collections
import numpy as np, cv2, ezdxf
from ezdxf import disassemble, path as ezpath
from shapely.ops import unary_union
A, B = sys.argv[1], sys.argv[2]; pref = sys.argv[3] if len(sys.argv) > 3 else 'cmp'
def ld(d, f): return pickle.load(open(os.path.join(d, f), 'rb'))
R = {}
# ---- walls: IoU per class (mm polygons)
wa, wb = ld(A, 'walls.pkl')['W'], ld(B, 'walls.pkl')['W']
tot_a = unary_union([g for v in wa.values() for g in v]); tot_b = unary_union([g for v in wb.values() for g in v])
def iou(x, y):
    u = x.union(y).area; return round(x.intersection(y).area / u, 4) if u else 1.0
R['walls_iou_total'] = iou(tot_a, tot_b)
R['walls_area_m2'] = [round(tot_a.area / 1e6, 2), round(tot_b.area / 1e6, 2)]
R['walls_symdiff_m2'] = round(tot_a.symmetric_difference(tot_b).area / 1e6, 3)
R['walls_iou_by_class'] = {k: iou(unary_union(wa.get(k, [])), unary_union(wb.get(k, []))) for k in sorted(set(wa) | set(wb))}
sd = tot_a.symmetric_difference(tot_b)
R['walls_diff_parts'] = sorted([dict(area_m2=round(g.area / 1e6, 3), at_mm=[round(g.centroid.x), round(g.centroid.y)]) for g in getattr(sd, 'geoms', [sd]) if g.area > 20000], key=lambda d: -d['area_m2'])[:15]
# ---- instances: counts by key and matching by (key, centre within 150 mm)
ia, ib = ld(A, 'inst_final.pkl'), ld(B, 'inst_final.pkl')
ca = collections.Counter(q['key'] for q in ia); cb = collections.Counter(q['key'] for q in ib)
R['instances_diff'] = {k: [ca[k], cb[k]] for k in sorted(set(ca) | set(cb)) if ca[k] != cb[k]}
def centres(I):
    out = collections.defaultdict(list)
    for q in I:
        if q.get('bbmm'): out[q['key']].append(((q['bbmm'][0] + q['bbmm'][2]) / 2, (q['bbmm'][1] + q['bbmm'][3]) / 2, q.get('block', ''), q.get('rot', 0)))
    return out
xa, xb = centres(ia), centres(ib); unm = []; blockdiff = []
for k in set(xa) | set(xb):
    lb = list(xb.get(k, []))
    for c in xa.get(k, []):
        j = min(range(len(lb)), key=lambda j: math.dist(c[:2], lb[j][:2]), default=None)
        if j is None or math.dist(c[:2], lb[j][:2]) > 150: unm.append(('only_A', k, [round(c[0]), round(c[1])])); continue
        if k in ('door', 'convector', 'desk', 'chair') and (abs(((c[3] - lb[j][3]) + 180) % 360 - 180) > 0.5): blockdiff.append((k, [round(c[0]), round(c[1])], c[3], lb[j][3]))
        lb.pop(j)
    unm += [('only_B', k, [round(c[0]), round(c[1])]) for c in lb]
R['instances_unmatched'] = unm[:40]; R['n_unmatched'] = len(unm)
R['rotation_differences'] = blockdiff[:20]
# ---- drawings: raster of both DXFs, XOR beyond 1 px
def dxf_of(d): return sorted(glob.glob(os.path.join(d, '*_engineering.dxf')))[0]
def raster(fn, box, Z=0.1):   # Z px per mm
    doc = ezdxf.readfile(fn); msp = doc.modelspace(); x0, y0, x1, y1 = box
    Wd, Hd = int((x1 - x0) * Z) + 1, int((y1 - y0) * Z) + 1
    m = np.zeros((Hd, Wd), np.uint8)
    def px(v): return (int(round((v.x - x0) * Z)), int(round((y1 - v.y) * Z)))
    def draw(e):
        if e.dxftype() in ('TEXT', 'MTEXT', 'DIMENSION'): return
        if e.dxftype() == 'HATCH':
            if not e.dxf.solid_fill: return
            for pth in ezpath.from_hatch(e):
                vs = list(pth.flattening(20))
                if len(vs) >= 3: cv2.fillPoly(m, [np.array([px(v) for v in vs], np.int32)], 255)
            return
        for pr in disassemble.to_primitives([e]):
            try: vs = list(pr.vertices())
            except Exception: continue
            if len(vs) >= 2: cv2.polylines(m, [np.array([px(v) for v in vs], np.int32)], False, 255, 1)
    for e in msp:
        if e.dxftype() == 'INSERT':
            for v in e.virtual_entities(): draw(v)
        else: draw(e)
    return m
bb = tot_a.union(tot_b).bounds; box = (bb[0] - 3000, bb[1] - 3000, bb[2] + 3000, bb[3] + 3000)
ma, mb = raster(dxf_of(A), box), raster(dxf_of(B), box)
k3 = np.ones((3, 3), np.uint8)
onlyA = ma & ~cv2.dilate(mb, k3); onlyB = mb & ~cv2.dilate(ma, k3)
R['drawing_px'] = [int((ma > 0).sum()), int((mb > 0).sum())]; R['drawing_only_A_px'] = int((onlyA > 0).sum()); R['drawing_only_B_px'] = int((onlyB > 0).sum())
def comps(m):
    n, lab, st, _ = cv2.connectedComponentsWithStats(cv2.dilate(m, np.ones((5, 5), np.uint8)))
    return sorted([dict(px=int(st[k][4]), at_mm=[round(box[0] + (st[k][0] + st[k][2] / 2) / 0.1), round(box[3] - (st[k][1] + st[k][3] / 2) / 0.1)]) for k in range(1, n) if st[k][4] > 30], key=lambda d: -d['px'])[:15]
R['drawing_only_A'] = comps(onlyA); R['drawing_only_B'] = comps(onlyB)
vis = np.full(ma.shape + (3,), 255, np.uint8); vis[ma > 0] = (170, 170, 170); vis[mb > 0] = (170, 170, 170)
vis[cv2.dilate(onlyA, k3) > 0] = (0, 0, 255); vis[cv2.dilate(onlyB, k3) > 0] = (255, 0, 0)
cv2.imwrite(pref + '.png', vis)
json.dump(R, open(pref + '.json', 'w'), ensure_ascii=False, indent=1)
for k, v in R.items(): print(k, v if not isinstance(v, list) or len(v) < 8 else v[:8])
