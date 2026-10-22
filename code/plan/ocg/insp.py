"""Inspect one place of the sheet (pt): wall bodies, objects and DXF contours that cross a square around (cx, cy).
usage (in the run folder): python3 insp.py cx cy half [dxf] [--dxf-only|--no-dxf]
Prints: wall bodies (class, area pt2, vertices); objects (index, key, name, layer, primitive kinds and vertices);
DXF records (layer, key, entity type, true vertices, closed) — the vertices the owner sees on the point sheets.
Code 012 (v010, route/insp.py — a tool, not a step): the modules of ocg/ from the folder of this file (v010: /home/claude/client-b);
the DXF is read through dxf_pts with the frame of the sheet from cfg (scale and origin, ocg/sheet.py)."""
import sys, os, pickle, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from shapely.geometry import box, Polygon, LineString, Point
from e7_comp import geom, load_prims, load_walls
a = [x for x in sys.argv[1:] if not x.startswith('--')]; flags = {x for x in sys.argv[1:] if x.startswith('--')}
cx, cy, half = map(float, a[:3]); dxf = a[3] if len(a) > 3 else None
B = box(cx - half, cy - half, cx + half, cy + half)
if '--dxf-only' not in flags:
    W = load_walls()['bodies']
    print('== wall bodies')
    for k, (c, g) in enumerate(W):
        if g.intersects(B):
            print(f'  W{k} {c:7s} area {g.area:8.2f} verts {len(g.exterior.coords) - 1:4d} holes {len(g.interiors)} bounds {tuple(round(v, 1) for v in g.bounds)}')
    P = load_prims()['P']; O = pickle.load(open('objects.pkl', 'rb'))['objs']
    print('== objects')
    for k, o in enumerate(O):
        ids = o.get('ids', [])
        gs = [geom(P[i]) for i in ids[:400]]
        if not any(g.intersects(B) for g in gs): continue
        kinds = collections.Counter((P[i]['kind'], P[i]['layer']) for i in ids)
        nv = sum(len(P[i]['p']) for i in ids)
        print(f'  O{k} key={o["key"]} name={o.get("name")} layer={o.get("layer")} ids={len(ids)} verts={nv} outline={len(o.get("outline") or [])} draw={len(o.get("draw") or [])} kinds={dict(kinds)}')
if dxf and '--no-dxf' not in flags:
    import dxf_pts as dp
    dp.frame_from_sheet()
    R, _ = dp.load(dxf)
    print('== DXF contours')
    cnt = collections.Counter()
    for r in R:
        g = LineString(r['D']) if len(r['D']) >= 2 else Point(r['D'][0])
        if not g.intersects(B): continue
        cnt[(r['layer'], r['key'], r['et'])] += 1
        fl = dp.straight_points(r['V'], r['closed'])
        rep = r['closed'] and len(r['V']) > 2 and abs(r['V'][0][0] - r['V'][-1][0]) < 1e-6 and abs(r['V'][0][1] - r['V'][-1][1]) < 1e-6
        print(f'  {r["layer"]:11s} {r["key"]:12s} {r["et"]:10s} oid {r["oid"]:5d} V {len(r["V"]):4d} closed {int(r["closed"])} straight/dup {len(fl)} closing-repeat {int(rep)}')
    print('  summary', dict(cnt))
