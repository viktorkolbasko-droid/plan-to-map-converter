"""Состав объектов DXF инженерного плана по классам таблицы слоёв; сравнение двух DXF (ОЧ-51; СУ-4 п. 1).

Назначение. Слепые плитки не видят класс объекта, когда у двух классов один цвет или объект мал (самопроверка
LOW и MAX, клиент Б, 40 этаж, 08.10.2026: шкафы ПК у LOW — служебные метки, мойки не собраны, а плитки LOW и MAX
одинаковы). Эта мера считает состав чертежа по классам и показывает разницу двух DXF одного листа числом.

Класс — код ISO 13567 слоя DXF (`A-68----E-` → `A-68`) по таблице слоёв кода (`layers_ocg.table()` =
`layers8.table()` + слои маршрута по слоям), с описанием из неё; слой не по форме ISO или без записи в таблице —
своим классом с пометкой «нет в таблице». По каждому классу:
  - objects  — объекты: сущности пространства модели на слоях линий `…E-` (вставка блока — один объект);
  - inserts  — из них вставок блоков;
  - length_m — длина линий объектов, м (вставки раскрываются; дуги и сплайны — ломаной с шагом 5 мм);
  - fills    — сущности на слоях заливки `…H-`; area_m2 — площадь, которую покрывают заливки класса, м²
               (HATCH чёт-нечет, перекрытия — один раз);
  - texts    — тексты и прочее на слоях `…T-` / `…D-`.

Сравнение двух DXF: таблица разниц по классам (B − A) и пометка «0 против N» — класс есть только у одного DXF.
Кроме счёта — перенос объектов между классами: для каждого объекта A ищется объект B того же места (центр рамки
ближе `--tol`, мм) — объект другого класса там же значит «тот же предмет, не тот класс». Начала координат двух
DXF могут различаться (LOW клиент Б — угол рамы витража, MAX — A/1 × A/A), поэтому B сдвигается к A: сдвиг —
по рамке стен, колонн и фасада (`--shift=auto`, по умолчанию) или задан (`--shift=dx,dy`, мм). Расхождение рамок
больше 50 мм после сдвига — стоп: молча сравнивать разные листы нельзя.

Запуск:
  python3 review/dxf_classes.py A.dxf [B.dxf] [--names=LOW,MAX] [--out=classes.json] [--shift=auto|dx,dy]
                                [--tol=150] [--strict]
  --strict — код выхода 1, если какой-то класс есть только у одного из двух DXF («0 против N»).

Выход: таблица в stdout (по классам; при двух DXF — разницы и перенос между классами); `--out` — JSON:
{names, files, sha256, shift_mm, by_class: {класс: {desc, in_table, A: {...}, B: {...}, delta: {...}}},
only_one: [...], moved: [{from, to, n, examples}]}.
"""
import sys, os, re, json, math, hashlib, collections
HERE = os.path.dirname(os.path.abspath(__file__))
for p in (os.path.dirname(HERE), os.path.join(os.path.dirname(HERE), 'ocg'), os.environ.get('PLAN_CODE', ''),
          os.path.join(os.environ.get('PLAN_CODE', ''), 'ocg')):
    if p and p not in sys.path: sys.path.append(p)

ISO = re.compile(r'^([A-Z])-([0-9A-Z]+)-*([A-Z])-$')       # A-221---E- -> ('A', '221', 'E')
ANCHOR = ('A-21', 'A-221', 'A-28', 'A-31')                # classes the shift of two DXFs is measured on: shell of the floor
SHIFT_STOP_MM = 50.0


def layer_table():
    """{слой: описание} — таблица слоёв кода плана (маршрут по слоям, если есть, иначе таблица кода 008+)."""
    try:
        from layers_ocg import table
    except ImportError:
        from layers8 import table
    return {n: d for n, d, *_ in table()}


def split_layer(name):
    """слой → (класс, вид): 'A-68----E-' → ('A-68', 'E'); не ISO → (имя слоя, '?')"""
    m = ISO.match(name or '')
    return (f'{m.group(1)}-{m.group(2)}', m.group(3)) if m else (name or '0', '?')


def class_desc(table):
    """{класс: описание} по слою линий класса, иначе по любому его слою"""
    out = {}
    for n, d in table.items():
        c, k = split_layer(n)
        if k == 'E' or c not in out: out[c] = d.replace(' — заливка', '') if k == 'H' else d
    return out


def sha256(f):
    h = hashlib.sha256()
    with open(f, 'rb') as fh:
        for b in iter(lambda: fh.read(1 << 20), b''): h.update(b)
    return h.hexdigest()


def _flat_len(e):
    from ezdxf import path as ezpath
    try:
        p = ezpath.make_path(e)
    except Exception:
        return 0.0
    v = [(q.x, q.y) for q in p.flattening(distance=5)] if len(p) else []
    return sum(math.dist(a, b) for a, b in zip(v, v[1:]))


def _len_of(e, depth=0):
    if e.dxftype() == 'INSERT':
        if depth > 8: return 0.0
        try:
            return sum(_len_of(v, depth + 1) for v in e.virtual_entities())
        except Exception:
            return 0.0
    if e.dxftype() in ('TEXT', 'MTEXT', 'HATCH', 'SOLID', 'ATTRIB', 'ATTDEF', 'DIMENSION', 'POINT'): return 0.0
    return _flat_len(e)


def hatch_geom(e):
    """HATCH → shapely-фигура чёт-нечет (None — не прочитать)"""
    from ezdxf import path as ezpath
    from shapely.geometry import Polygon
    g = None
    try:
        for p in ezpath.from_hatch(e):
            for sp in (p.sub_paths() if hasattr(p, 'sub_paths') else [p]):
                pts = [(v.x, v.y) for v in sp.flattening(distance=5)]
                if len(pts) >= 3:
                    r = Polygon(pts).buffer(0)
                    g = r if g is None else g.symmetric_difference(r)
    except Exception:
        return None
    return g


def centre(e):
    from ezdxf import bbox
    try:
        b = bbox.extents([e], fast=True)
        if b.has_data: return ((b.extmin.x + b.extmax.x) / 2, (b.extmin.y + b.extmax.y) / 2, b.extmax.x - b.extmin.x, b.extmax.y - b.extmin.y)
    except Exception:
        pass
    return None


def read(f, with_pos=False):
    """Счёт одного DXF: {by_class, objects (с местом, если with_pos), anchor_box, layers, file, sha256}"""
    import ezdxf
    from shapely.ops import unary_union
    doc = ezdxf.readfile(f)
    S = collections.defaultdict(lambda: dict(objects=0, inserts=0, length_m=0.0, fills=0, area_m2=0.0, texts=0, layers=collections.Counter()))
    polys = collections.defaultdict(list); objs = []; anchor = [math.inf, math.inf, -math.inf, -math.inf]
    for e in doc.modelspace():
        lay = e.dxf.get('layer', '0'); c, k = split_layer(lay); s = S[c]; s['layers'][lay] += 1
        if k in ('T', 'D'):
            s['texts'] += 1; continue
        if e.dxftype() == 'HATCH' or k == 'H':
            s['fills'] += 1
            if e.dxftype() == 'HATCH':
                g = hatch_geom(e)
                if g is not None and not g.is_empty: polys[c].append(g)
            continue
        s['objects'] += 1; s['inserts'] += e.dxftype() == 'INSERT'; s['length_m'] += _len_of(e) / 1000.0
        if with_pos or c in ANCHOR:
            q = centre(e)
            if q is None: continue
            if with_pos: objs.append(dict(cls=c, layer=lay, type=e.dxftype(), x=q[0], y=q[1], w=q[2], h=q[3],
                                          block=e.dxf.name if e.dxftype() == 'INSERT' else ''))
            if c in ANCHOR:
                anchor = [min(anchor[0], q[0] - q[2] / 2), min(anchor[1], q[1] - q[3] / 2), max(anchor[2], q[0] + q[2] / 2), max(anchor[3], q[1] + q[3] / 2)]
    for c, v in polys.items():
        try:
            S[c]['area_m2'] = unary_union(v).area / 1e6
        except Exception:
            S[c]['area_m2'] = sum(g.area for g in v) / 1e6
    by = {c: dict(objects=s['objects'], inserts=s['inserts'], length_m=round(s['length_m'], 2), fills=s['fills'], area_m2=round(s['area_m2'], 3),
                  texts=s['texts'], layers=dict(sorted(s['layers'].items()))) for c, s in sorted(S.items())}
    return dict(file=f, sha256=sha256(f), by_class=by, objects=objs, anchor_box=anchor if math.isfinite(anchor[0]) else None)


def measure_shift(a, b):
    """сдвиг (dx, dy) мм, который переносит B в систему A, по рамке стен, колонн и фасада; и расхождение рамок после сдвига"""
    A, B = a['anchor_box'], b['anchor_box']
    if A is None or B is None: raise SystemExit('СТОП: нет стен, колонн или фасада (' + ', '.join(ANCHOR) + ') — сдвиг не измерить; задайте --shift=dx,dy')
    dx = ((A[0] - B[0]) + (A[2] - B[2])) / 2; dy = ((A[1] - B[1]) + (A[3] - B[3])) / 2
    res = max(abs((A[0] - B[0]) - dx), abs((A[1] - B[1]) - dy), abs((A[2] - B[2]) - dx), abs((A[3] - B[3]) - dy))
    return dx, dy, res


def parse_shift(s, a, b):
    if s in (None, '', 'auto'):
        dx, dy, res = measure_shift(a, b)
        if res > SHIFT_STOP_MM:
            raise SystemExit(f'СТОП: рамки стен и фасада двух DXF расходятся на {res:.0f} мм после сдвига (> {SHIFT_STOP_MM:.0f} мм): '
                             'другой лист, масштаб или состав. Сравнение не делаю; сдвиг можно задать --shift=dx,dy')
        return dx, dy, res, 'auto'
    dx, dy = (float(v) for v in s.split(','))
    return dx, dy, None, 'given'


def moved(a, b, dx, dy, tol):
    """перенос между классами: объекты A, у которых на том же месте в B объект другого класса, а своего класса нет"""
    import numpy as np
    from scipy.spatial import cKDTree
    if not a['objects'] or not b['objects']: return []
    PB = np.array([(o['x'] + dx, o['y'] + dy) for o in b['objects']]); T = cKDTree(PB)
    PA = np.array([(o['x'], o['y']) for o in a['objects']]); TA = cKDTree(PA)
    out = collections.defaultdict(list)
    for o in a['objects']:
        idx = T.query_ball_point((o['x'], o['y']), tol)
        if not idx: continue
        same = [i for i in idx if b['objects'][i]['cls'] == o['cls']]
        if same: continue
        sz = math.hypot(o['w'], o['h'])                                       # the same thing: size within 30 %
        cand = [i for i in idx if abs(math.hypot(b['objects'][i]['w'], b['objects'][i]['h']) - sz) <= 0.3 * max(sz, 1.0)]
        # and A has nothing of the B class there: a mark lying on a facade line is not a facade line "moved" (both stay)
        cand = [i for i in cand if not any(a['objects'][j]['cls'] == b['objects'][i]['cls'] for j in TA.query_ball_point(PB[i], tol))]
        if not cand: continue
        i = min(cand, key=lambda i: math.dist((o['x'], o['y']), PB[i]))
        out[(o['cls'], b['objects'][i]['cls'])].append((round(o['x']), round(o['y'])))
    return [dict(src=k[0], dst=k[1], n=len(v), examples=v[:5]) for k, v in sorted(out.items(), key=lambda t: -len(t[1]))]


def compare(a, b, desc, table_cls):
    rows = {}
    for c in sorted(set(a['by_class']) | set(b['by_class'])):
        A = a['by_class'].get(c, {}); B = b['by_class'].get(c, {})
        d = {k: round(B.get(k, 0) - A.get(k, 0), 3) for k in ('objects', 'inserts', 'length_m', 'fills', 'area_m2', 'texts')}
        rows[c] = dict(desc=desc.get(c, 'нет в таблице слоёв'), in_table=c in table_cls, A=A, B=B, delta=d)
    only = [c for c, r in rows.items() if (r['A'].get('objects', 0) == 0) != (r['B'].get('objects', 0) == 0)]
    return rows, only


def fmt(v, nd=1):
    return f'{v:.{nd}f}'.rstrip('0').rstrip('.') if isinstance(v, float) else str(v)


def print_table(rows, names, only):
    a, b = names
    print(f'{"класс":<8} {"описание":<44} {"объекты " + a:>11} {b:>6} {"Δ":>5} | {"длина м " + a:>13} {b:>8} {"Δ":>8} | {"площ м² " + a:>13} {b:>8} {"Δ":>7} | {"тексты " + a:>12} {b:>6} {"Δ":>5}')
    for c, r in rows.items():
        A, B, D = r['A'], r['B'], r['delta']
        mark = '  ← 0 против ' + str(max(A.get('objects', 0), B.get('objects', 0))) if c in only else ''
        if not r['in_table']: mark += '  [нет в таблице]'
        print(f'{c:<8} {r["desc"][:44]:<44} {A.get("objects", 0):>11} {B.get("objects", 0):>6} {D["objects"]:>+5} | '
              f'{A.get("length_m", 0):>13.1f} {B.get("length_m", 0):>8.1f} {D["length_m"]:>+8.1f} | '
              f'{A.get("area_m2", 0):>13.2f} {B.get("area_m2", 0):>8.2f} {D["area_m2"]:>+7.2f} | {A.get("texts", 0):>12} {B.get("texts", 0):>6} {D["texts"]:>+5}{mark}')


def main(argv):
    args = [x for x in argv if not x.startswith('--')]
    opt = dict((x[2:].split('=', 1) + [''])[:2] for x in argv if x.startswith('--'))
    if not args or len(args) > 2: sys.exit(__doc__)
    names = (opt.get('names') or ('A,B' if len(args) == 2 else 'A')).split(',')
    table = layer_table(); desc = class_desc(table); table_cls = set(desc)
    two = len(args) == 2
    R = [read(f, with_pos=two) for f in args]
    out = dict(names=names[:len(args)], files=[r['file'] for r in R], sha256=[r['sha256'] for r in R])
    code = 0
    if not two:
        r = R[0]
        print(f'{"класс":<8} {"описание":<44} {"объекты":>8} {"вставки":>8} {"длина м":>9} {"заливки":>8} {"площ м²":>8} {"тексты":>7}')
        for c, s in r['by_class'].items():
            print(f'{c:<8} {desc.get(c, "нет в таблице слоёв")[:44]:<44} {s["objects"]:>8} {s["inserts"]:>8} {s["length_m"]:>9.1f} {s["fills"]:>8} {s["area_m2"]:>8.2f} {s["texts"]:>7}')
        out['by_class'] = {c: dict(desc=desc.get(c, 'нет в таблице слоёв'), in_table=c in table_cls, **s) for c, s in r['by_class'].items()}
    else:
        a, b = R
        dx, dy, res, how = parse_shift(opt.get('shift'), a, b)
        rows, only = compare(a, b, desc, table_cls)
        mv = moved(a, b, dx, dy, float(opt.get('tol') or 150))
        out.update(shift_mm=dict(dx=round(dx, 1), dy=round(dy, 1), residual=None if res is None else round(res, 1), how=how),
                   by_class=rows, only_one=only, moved=mv)
        print(f'A = {names[0]}: {args[0]}\nB = {names[1]}: {args[1]}\nсдвиг B → A: dx {dx:.1f} мм, dy {dy:.1f} мм'
              + (f', расхождение рамок {res:.1f} мм ({how})' if res is not None else ' (задан)'))
        print_table(rows, names, only)
        print('классы только у одного DXF:', ', '.join(only) if only else 'нет')
        print(f'перенос между классами (то же место ±{fmt(float(opt.get("tol") or 150))} мм, размер ±30 %): {names[0]} → {names[1]}')
        for m in mv: print(f'  {m["src"]} → {m["dst"]}: {m["n"]}   напр. {m["examples"][:2]}')
        if not mv: print('  нет')
        if 'strict' in opt and only: code = 1
    if opt.get('out'):
        json.dump(out, open(opt['out'], 'w'), ensure_ascii=False, indent=1)
    return code


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
