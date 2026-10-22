# DXF census: entities by layer and type, top level and inside inserts; compares two DXF files.
# usage: python3 dxfcmp.py a.dxf b.dxf
import sys, collections, ezdxf, hashlib
def census(fn):
    doc = ezdxf.readfile(fn); msp = doc.modelspace(); c = collections.Counter(); g = collections.Counter()
    for e in msp:
        c[(e.dxf.layer, e.dxftype())] += 1
        if e.dxftype() == 'INSERT':
            for s in e.virtual_entities(): g[(e.dxf.layer, s.dxftype())] += 1
    return c, g, len(doc.blocks)
a, ga, ba = census(sys.argv[1]); b, gb, bb = census(sys.argv[2])
print('blocks', ba, bb)
keys = sorted(set(a) | set(b))
for k in keys:
    if a[k] != b[k]: print('top', k, a[k], b[k])
for k in sorted(set(ga) | set(gb)):
    if ga[k] != gb[k]: print('in blocks', k, ga[k], gb[k])
print('top-level total', sum(a.values()), sum(b.values()), '| differing keys', sum(1 for k in keys if a[k] != b[k]))
