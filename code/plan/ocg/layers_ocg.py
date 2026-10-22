# ocg/layers_ocg.py - code 009: the DXF layers of the layer route and the DXF check S14* (Т4-13, Т4-14) for it.
#   The table is the code's table (layers8.table(), plan/rules/50 §1) plus the layers the layer route adds (EXTRA). Every
#   layer an entity of the DXF uses must be in it with a description; texts lie on '...T-' and '...D-' only.
#   python3 layers_ocg.py <dxf> [out.json]     without out.json: exit 0 - no stop, 1 - S14*: layers without a record, texts off
#   T/D; with out.json (run_ocg.sh) - exit 0, the gate reads the report
import os, sys, json, collections
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # the code folder: layers8.py
from layers8 import table as _code_table

# layers of the layer route that the code table does not have (test 2-8 of the layer route; plan/code/90, 009). Code 010
#   (К-1): A-79 is gone - МФУ and wall screens are furniture A-82 (owner's decision of 07.10.2026, №106, №108, row 208)
EXTRA = [('A-221---T-', 'Подписи', 7, 18),
         # code 012 (v010, З-14…З-23): the zones - rooms and passages as polygons to fill on the map; e8_export.py writes them to
         #   the DXF of the zones <cfg.OUT>_zones.dxf (and to the plan's DXF only with ZONES_IN_DXF=1)
         ('A-921---E-', 'Помещения: внутренний контур по граням стен, остекления и проёмов — полигон под заливку (группа 7, З-14, З-15)', 30, 25),
         ('A-921---H-', 'Помещения — заливка полигона', 31, 13),
         ('A-922---E-', 'Проходы: зона прохода — полигон под заливку (группа 7, З-14.3, З-16…З-23)', 94, 25),
         ('A-922---H-', 'Проходы — заливка полигона', 92, 13)]


def table():
    out = list(_code_table()); have = {n for n, *_ in out}
    for r in EXTRA:
        if r[0] not in have: out.append(r); have.add(r[0])
    return out


def check(dxf_path):
    import ezdxf
    doc = ezdxf.readfile(dxf_path); T = {n: d for n, d, *_ in table()}
    used = collections.Counter(); texts_off = collections.Counter()

    def see(e, where):
        L = e.dxf.get('layer', '0'); used[L] += 1
        if e.dxftype() in ('TEXT', 'MTEXT') and not (L.endswith('T-') or L.endswith('D-')): texts_off[L] += 1
    for e in doc.modelspace():
        see(e, '*MODEL')
    for b in doc.blocks:
        if b.name.startswith('*'): continue
        for e in b: see(e, b.name)
    desc = {l.dxf.name: (l.description or '') for l in doc.layers}
    no_rec = {L: n for L, n in used.items() if L != '0' and L not in T}
    no_desc = {L: n for L, n in used.items() if L != '0' and L in T and not desc.get(L)}     # in the table, but the DXF layer has no description (or is not defined)
    return dict(layers_used=len(used), no_record=no_rec, no_description=no_desc, texts_off_TD=dict(texts_off),
                stop=bool(no_rec or no_desc or texts_off))


if __name__ == '__main__':
    r = check(sys.argv[1])
    if len(sys.argv) > 2: json.dump(r, open(sys.argv[2], 'w'), ensure_ascii=False, indent=1)
    print('S14*:', 'СТОП' if r['stop'] else 'ok', '| слоёв', r['layers_used'], '| без записи', r['no_record'], '| без описания', r['no_description'],
          '| тексты не на T/D', r['texts_off_TD'])
    sys.exit(0 if len(sys.argv) > 2 else (1 if r['stop'] else 0))     # with out.json (run_ocg.sh) the gate decides: exit 0
