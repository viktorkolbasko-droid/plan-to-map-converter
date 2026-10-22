# Is a new DXF the same drawing as the delivered one? (plan/rules/50 §5). Compares layer/type counts, the multiset of
# geometry rounded to 0.1 mm (lines, polylines, block inserts with rotation) and the block definitions.
# 30.09.2026: floors 2 and 5 after the last code came out the same - they did not need a new delivery.
# A closed polyline is compared as a ring - no start vertex, no direction - an open one without direction, a line
#   without direction: the ring order of shapely changes between versions, and the same drawing came out "DIFFERENT"
#   (canon-proposals_2026-09-30-инженерный-план-5-этаж-прогон-2.md, п. 1: 28 wall polylines, compare_runs IoU 1.0).
#   python3 dxfsame.py delivered.dxf new.dxf      exit 0 - same drawing, 1 - differs (the diffs are printed)
import sys, ezdxf, collections
def ring(pts):
    """a closed ring without start and direction: the smaller of both directions, each started at its least vertex"""
    pts = [p for i, p in enumerate(pts) if i == 0 or p != pts[i - 1]]      # repeated vertices are not geometry
    while len(pts) > 1 and pts[0] == pts[-1]: pts = pts[:-1]
    def rot(q):
        k = min(range(len(q)), key=lambda i: q[i]); return tuple(q[k:] + q[:k])
    return min(rot(pts), rot(pts[::-1])) if pts else ()
def path(pts):
    pts = [p for i, p in enumerate(pts) if i == 0 or p != pts[i - 1]]
    return min(tuple(pts), tuple(pts[::-1]))
def sig(fn):
    doc = ezdxf.readfile(fn); c = collections.Counter(); h = collections.Counter()
    for e in doc.modelspace():
        k = (e.dxf.layer, e.dxftype()); c[k] += 1
        try:
            if e.dxftype() == 'LINE': g = tuple(sorted([(round(e.dxf.start.x, 1), round(e.dxf.start.y, 1)), (round(e.dxf.end.x, 1), round(e.dxf.end.y, 1))]))
            elif e.dxftype() == 'LWPOLYLINE':
                q = [(round(x, 1), round(y, 1)) for x, y in e.get_points('xy')]
                g = ('ring', ring(q)) if (e.closed or (len(q) > 2 and q[0] == q[-1])) else ('path', path(q))
            elif e.dxftype() == 'INSERT': g = (e.dxf.name, round(e.dxf.insert.x, 1), round(e.dxf.insert.y, 1), round(e.dxf.rotation, 2))
            else: g = e.dxftype()
        except Exception: g = None
        h[(k, g)] += 1
    blocks = collections.Counter((b.name, len(b)) for b in doc.blocks if not b.name.startswith('*'))
    return c, h, blocks
if __name__ == '__main__':
    a, b = sys.argv[1], sys.argv[2]
    ca, ha, ba = sig(a); cb, hb, bb_ = sig(b)
    dl = {k: (ca.get(k, 0), cb.get(k, 0)) for k in set(ca) | set(cb) if ca.get(k, 0) != cb.get(k, 0)}
    same = not dl and ha == hb and ba == bb_
    print('layer/type count diffs:', dl)
    print('geometry multiset equal:', ha == hb, '| blocks equal:', ba == bb_, '| entities', sum(ca.values()), sum(cb.values()))
    print('SAME DRAWING' if same else 'DIFFERENT')
    sys.exit(0 if same else 1)
