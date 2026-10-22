# ocg/compose_ocg.py - code 009: the composition of the DXF against the checked result (plan/00, step 9; plan/rules/70,
#   rule 30): cfg.OCG_REF_DXF (detailed) and cfg.OCG_REF_DXF_OUTLINE (габаритный) - DXF files of the checked result.
#   Census by layer and type (dxfcmp) and the geometry of every entity of the model space and of the blocks to 0.1 mm without
#   handles and the header (dxfgeo_cmp: ezdxf writes the time of saving, the hash of the file changes on every run).
#   No reference in cfg - the check is skipped (written so); a difference - a stop of the gate (O9) until the new result is
#   checked and becomes the reference, or the difference is accepted with its reason (cfg.OCG_GATE_ACCEPT).
#   python3 compose_ocg.py out.json       (floor folder)
import os, sys, json, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sheet
import ezdxf
from dxfgeo_cmp import census as geo_census


def census(fn):
    doc = ezdxf.readfile(fn); msp = doc.modelspace(); c = collections.Counter(); g = collections.Counter()
    for e in msp:
        c[(e.dxf.layer, e.dxftype())] += 1
        if e.dxftype() == 'INSERT':
            for s in e.virtual_entities(): g[(e.dxf.layer, s.dxftype())] += 1
    return c, g, len(doc.blocks)


def compare(ref, new):
    a, ga, ba = census(ref); b, gb, bb = census(new)
    top = {f'{k[0]}/{k[1]}': [a[k], b[k]] for k in sorted(set(a) | set(b)) if a[k] != b[k]}
    inb = {f'{k[0]}/{k[1]}': [ga[k], gb[k]] for k in sorted(set(ga) | set(gb)) if ga[k] != gb[k]}
    A = geo_census(ref); B = geo_census(new); oa = A - B; ob = B - A
    ex = [dict(side='ref', n=n, where=k[0], type=k[1], layer=k[2], geom=str(k[3])[:160]) for k, n in list(oa.items())[:10]] + \
         [dict(side='new', n=n, where=k[0], type=k[1], layer=k[2], geom=str(k[3])[:160]) for k, n in list(ob.items())[:10]]
    return dict(ref=ref, new=new, blocks=[ba, bb], top_total=[sum(a.values()), sum(b.values())], top_diff=top, in_blocks_diff=inb,
                entities=[sum(A.values()), sum(B.values())], only_ref=sum(oa.values()), only_new=sum(ob.values()), examples=ex,
                same=(not top and not inb and not oa and not ob and ba == bb))


res = dict(checked=[], skipped=[])
for field, new in (('OCG_REF_DXF', os.path.join('out', sheet.OUT + '_engineering.dxf')),
                   ('OCG_REF_DXF_OUTLINE', os.path.join('out_outline', sheet.OUT + '_outline.dxf'))):
    ref = getattr(sheet.cfg, field, None)
    if not ref: res['skipped'].append(f'{field}: нет в cfg — сверка состава не сделана'); continue
    if not os.path.exists(ref) or not os.path.exists(new):
        res['checked'].append(dict(field=field, ref=ref, new=new, error='нет файла', same=False)); continue
    r = compare(ref, new); r['field'] = field; res['checked'].append(r)
res['differ'] = sum(1 for r in res['checked'] if not r.get('same'))
json.dump(res, open(sys.argv[1] if len(sys.argv) > 1 else 'ocg_compose.json', 'w'), ensure_ascii=False, indent=1)
for r in res['checked']:
    print(r['field'], 'тот же' if r.get('same') else 'ОТЛИЧИЕ', '| блоков', r.get('blocks'), '| объектов', r.get('top_total'), '| только в эталоне',
          r.get('only_ref'), '| только в новом', r.get('only_new'), '|', list(r.get('top_diff', {}).items())[:6])
for s in res['skipped']: print(s)
