"""Test 8: the geometry of two DXF files compared entity by entity, apart from handles and the header (ezdxf writes the time
of the save, so the hash of the file changes on every run even when the drawing is the same). Every entity of the model space
and of every block -> (block, type, layer, geometry rounded to 10^-D mm, text, colour); the two multisets are compared.
Complements dxfcmp.py (the census by layer and type) for "сверка состава DXF" of plan/00, step 9.
usage: python3 dxfgeo_cmp.py a.dxf b.dxf [D=1]      exit 0 — the same geometry"""
import sys, collections, ezdxf
D = int(sys.argv[3]) if len(sys.argv) > 3 else 1
def r(v): return tuple(round(float(x), D) for x in v)
def edge(ed):
    out = [type(ed).__name__]
    for k in ('start', 'end', 'center', 'radius', 'start_angle', 'end_angle', 'ccw', 'major_axis', 'ratio'):
        if hasattr(ed, k):
            v = getattr(ed, k)
            out.append(round(float(v), D) if isinstance(v, (int, float)) and not isinstance(v, bool) else (v if isinstance(v, bool) else r(v)))
    return tuple(out)
def sig(e, where):
    t = e.dxftype(); L = e.dxf.get('layer', '')
    if t == 'LINE': g = (r(e.dxf.start), r(e.dxf.end))
    elif t == 'LWPOLYLINE': g = (tuple(r(p) for p in e.get_points('xyb')), bool(e.closed))
    elif t == 'POLYLINE': g = (tuple(r(v.dxf.location) for v in e.vertices), bool(e.is_closed))
    elif t == 'CIRCLE': g = (r(e.dxf.center), round(e.dxf.radius, D))
    elif t == 'ARC': g = (r(e.dxf.center), round(e.dxf.radius, D), round(e.dxf.start_angle, 3), round(e.dxf.end_angle, 3))
    elif t == 'TEXT': g = (e.dxf.text, r(e.dxf.insert), round(e.dxf.height, D), round(e.dxf.rotation, 3), e.dxf.halign, e.dxf.valign)
    elif t == 'MTEXT': g = (e.text, r(e.dxf.insert))
    elif t == 'INSERT': g = (e.dxf.name, r(e.dxf.insert), round(e.dxf.rotation, 3), round(e.dxf.xscale, 4), round(e.dxf.yscale, 4))
    elif t == 'HATCH':
        ps = []
        for p in e.paths:
            if hasattr(p, 'vertices'): ps.append(('poly',) + tuple(r(v[:2]) for v in p.vertices))
            else: ps.append(('edges',) + tuple(edge(ed) for ed in p.edges))
        g = (e.dxf.pattern_name, e.dxf.solid_fill, round(e.dxf.get('pattern_angle', 0), 3), round(e.dxf.get('pattern_scale', 1), 4), tuple(ps))
    elif t == 'SOLID': g = tuple(r(e.dxf.get(k)) for k in ('vtx0', 'vtx1', 'vtx2', 'vtx3'))
    else: g = (t,)
    return (where, t, L, g, e.dxf.get('color', None), e.dxf.get('true_color', None))
def census(fn):
    doc = ezdxf.readfile(fn); c = collections.Counter()
    for e in doc.modelspace(): c[sig(e, '*MODEL')] += 1
    for b in doc.blocks:
        if b.name.startswith('*'): continue
        for e in b: c[sig(e, b.name)] += 1
    return c
if __name__ == '__main__':
    a = census(sys.argv[1]); b = census(sys.argv[2])
    only_a = a - b; only_b = b - a
    print('entities', sum(a.values()), sum(b.values()), '| only in the first', sum(only_a.values()), '| only in the second', sum(only_b.values()))
    for k, n in list(only_a.items())[:8]: print('  first only ', n, k[:3], str(k[3])[:160])
    for k, n in list(only_b.items())[:8]: print('  second only', n, k[:3], str(k[3])[:160])
    sys.exit(0 if not only_a and not only_b else 1)
