# cfgread.py - code 008: the check of cfg.py at reading, the second step of run.sh (after sheetcheck.py). Stops in
#   seconds with the list, before anything is computed - a silent refusal is worse than a loud stop:
#   - Т4-13: a layer of cfg (MANUAL, MISC_GROUPS, COLOR_ELEMENTS, FAMILIES) that is not in the layer table of the code
#     (layers8.py) - in AutoCAD such a layer has no description, colour or linetype, and the audit of ezdxf is silent;
#   - Т4-7: a MANUAL element that would take primitives of another class of the previous run in this folder
#     (assign2_pre.pkl - the owners as assign.py left them; else inst_final.pkl) - not 'misc', a light partition, loose bits, free or its own class: the side effects of an own box
#     (floor 4, test 4: a counter took the core of a partition, a cross mark the end of a glass partition, the fire
#     cabinet box a door) - a stop with a picture (cfgread_take.png) until the operator confirms the record:
#     cfg.MANUAL_TAKES_OK = {<record index or name>: 'why'}.
#   python3 cfgread.py          (floor folder)        exit 0 - fine, 3 - stop (cfgread.json)
import os, sys, json, pickle, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import cfg, load, pts, X0, Y0
import layers8, manual8
res = dict(ok=True, layers=[], takes=[])
bad = layers8.cfg_layers(cfg)
for f, n, L in bad: res['layers'].append(dict(field=f, record=n, layer=L))
# Т4-7: dry run of MANUAL against the previous run of this folder - the order of assign.py: records in list order, a
#   primitive an earlier record took is not taken again; primitives of the early steps (families, doors, tags, colour
#   elements - they are taken before MANUAL) and wall primitives are not taken by a box at all (review/manual_take.py)
FALLBACK = {'misc', 'lpart', 'lpartc', 'loose', 'wallline', 'FREE'}   # 'misc', partitions, loose bits, free - not another class
EARLY = {'chair', 'wc', 'sink', 'stool', 'door', 'tag', 'roomsep', 'axis', 'sheet', 'dim', 'sign', 'door45c', 'wcsink', 'glass_c', 'doorhw', 'plant'}
CE = {e['key'] for e in getattr(cfg, 'COLOR_ELEMENTS', []) or []}
OKS = getattr(cfg, 'MANUAL_TAKES_OK', {}) or {}
# the owners of the previous run as assign.py left them (assign2_pre.pkl): what reclass.py and fix7.py moved later (fix7 F1
#   gives a column back its lines from a cabinet box, F3 makes monitors of a meeting table) is not a box's side effect
_PREV = next((f for f in ('assign2_pre.pkl', 'inst_final.pkl') if os.path.exists(f)), None)
if _PREV and os.path.exists('cls.pkl') and os.path.exists('seq.pkl'):
    try:
        P = load(); cls = pickle.load(open('cls.pkl', 'rb'))
        inst = pickle.load(open(_PREV, 'rb')); inst = inst[0] if isinstance(inst, tuple) else inst
        res['previous'] = _PREV
        WP = set()
        for f_ in ('wallprims_pre7.pkl', 'wallprims.pkl'):
            if os.path.exists(f_): WP = set(pickle.load(open(f_, 'rb'))); break
        own = {}; back = set()
        for k, q in enumerate(inst):
            for i in q['prims']: own.setdefault(i, k)
            back |= set(q.get('back8', ()))       # a column's section taken back from a room-size box by rule (detect8, Т4-3)
        PB = []
        for p in P:
            ps = pts(p); xs = [v[0] for v in ps]; ys = [v[1] for v in ps]; PB.append((min(xs), min(ys), max(xs), max(ys)))
        import numpy as np
        A = np.array(PB)
        from shapely.geometry import LineString, Polygon
        def geom(i):
            k = P[i][0]
            if k in ('l', 'c'): return LineString(pts(P[i]))
            g = Polygon(P[i][4]); return g if g.is_valid else g.buffer(0)
        taken = set()
        for n, (key, name, layer, boxes) in enumerate(cfg.MANUAL):
            took = collections.Counter(); ids_ = []
            for b in boxes:
                x0, y0, x1, y1 = manual8.bbox_of(b)
                for i in np.nonzero((A[:, 0] >= x0 - 0.6) & (A[:, 2] <= x1 + 0.6) & (A[:, 1] >= y0 - 0.6) & (A[:, 3] <= y1 + 0.6))[0]:
                    i = int(i)
                    if i in taken or i in WP or cls[i] not in ('obj', 'wall'): continue
                    if P[i][0] == 'qu' and P[i][3] == (1.0, 1.0, 1.0): continue     # a white mask is never offered to a box (assign.py)
                    if i in back: continue
                    if manual8.is_poly(b) and not manual8.element_takes(b, PB[i], lambda i=i: geom(i), 0.6): continue
                    ok_ = inst[own[i]]['key'] if i in own else 'FREE'
                    if ok_ in EARLY or (ok_ in CE and not (ok_ == 'glass' and P[i][0] != 'qu')): continue
                    taken.add(i)
                    if ok_ == key or ok_ in FALLBACK or ok_.startswith('wall'): continue
                    took[ok_] += 1; ids_.append(i)
            if took and not (n in OKS or name in OKS):
                res['takes'].append(dict(record=n, key=key, name=name[:80], foreign=dict(took), at=[round(v, 1) for v in manual8.bbox_of(boxes[0])], ids=ids_[:400]))
    except Exception as ex:
        res['takes_error'] = str(ex)[:300]
res['ok'] = not res['layers'] and not res['takes']
if res['takes']:
    # the picture: each record's place, the primitives it would take from another class in red
    try:
        from PIL import Image, ImageDraw, ImageFont
        Z = 6; T_ = 380; nc = min(4, len(res['takes'])); nr = (len(res['takes']) + nc - 1) // nc
        sh = Image.new('RGB', (nc * (T_ + 8), nr * (T_ + 30)), 'white'); d = ImageDraw.Draw(sh)
        F = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 11)
        for t, r in enumerate(res['takes']):
            bx = r['at']; cx, cy = (bx[0] + bx[2]) / 2, (bx[1] + bx[3]) / 2; half = max(bx[2] - bx[0], bx[3] - bx[1]) / 2 + 6
            z = T_ / (2 * half); ox, oy = (t % nc) * (T_ + 8), (t // nc) * (T_ + 30) + 26
            tr = lambda p: (ox + (p[0] - cx + half) * z, oy + (p[1] - cy + half) * z)
            for i, p in enumerate(P):
                b = PB[i]
                if b[2] < cx - half or b[0] > cx + half or b[3] < cy - half or b[1] > cy + half: continue
                d.line([tr(v) for v in pts(p)], fill=(150, 150, 150), width=1)
            for i in r['ids']: d.line([tr(v) for v in pts(P[i])], fill=(220, 0, 0), width=3)
            for b in cfg.MANUAL[r['record']][3]:
                bb = manual8.bbox_of(b); d.rectangle([tr((bb[0], bb[1])), tr((bb[2], bb[3]))], outline=(130, 0, 200), width=2)
            d.text((ox + 2, oy - 24), f"MANUAL[{r['record']}] {r['key']}: {r['name'][:46]}", fill=(0, 0, 0), font=F)
            d.text((ox + 2, oy - 12), f"берёт чужое: {r['foreign']}", fill=(200, 0, 0), font=F)
        sh.save('cfgread_take.png'); res['picture'] = 'cfgread_take.png'
    except Exception as ex: res['picture_error'] = str(ex)[:200]
for r in res['takes']: r.pop('ids', None)
json.dump(res, open('cfgread.json', 'w'), ensure_ascii=False, indent=1)
if res['ok']:
    print('cfg read: layers in the table, MANUAL takes nothing of another class' + (' (no previous run)' if not _PREV else f' (previous run: {_PREV})'))
    sys.exit(0)
for r in res['layers']: print(f"СТОП cfg: {r['field']}[{r['record']}] — слой {r['layer']} не в таблице слоёв кода (layers8.py, plan/rules/50 §1; Т4-13)")
for r in res['takes']: print(f"СТОП cfg: MANUAL[{r['record']}] {r['key']} «{r['name'][:50]}» у {r['at']} берёт примитивы другого класса прошлого прогона {r['foreign']} — "
                            f"картинка {res.get('picture')}; подтвердить — cfg.MANUAL_TAKES_OK = {{{r['record']}: 'почему'}} (Т4-7)")
sys.exit(3)
