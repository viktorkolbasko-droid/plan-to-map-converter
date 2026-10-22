"""Слепые плитки по DXF инженерного плана и случайная выборка кадров (ОЧ-51: В-3 волны 2; п. 182).

Назначение. `review/blind_tiles.py` строит плитки по папке прогона (pkl, cfg); у базы теста часто есть только DXF
(клиент Б, волна 2, В-3: тест 6 — один DXF на Диске). Этот скрипт берёт сами DXF:
  - раскраска — по таблице слоёв кода (`layers_ocg.table()` = `layers8.table()` + слои маршрута): у каждого класса
    ISO (`A-68`, `A-73`, `A-74`, `A-76`, `A-AXM`, …) свой цвет, мойка не сливается с оборудованием, шкаф ПК — со
    служебной меткой (СУ-4 п. 1); слой не по форме ISO или без записи в таблице — ярко-зелёный, число таких
    примитивов — в tiles.json; заливки (`…H-`) — светлым тоном класса, заливка узором — ещё светлее; сначала
    заливки, потом линии (v3 плиток самопроверки);
  - без подписей, которые выдают ответ: тексты, марки и размеры (`…T-`, `…D-`, `A-90`, `A-91`, оси `A-AX`) не
    рисуются; варианты на плитке — «A», «B» в случайном порядке, ключ — отдельно (`.k`: base64 перевёрнутого JSON,
    как у `blind_tiles.py`); легенда — только классы (`legend.png`);
  - кадр одного места у двух DXF — рядом: `tNN.png` = исходник | A | B (или исходник | карта для одного DXF), каждый
    кадр шире плитки на `--margin` (доля, 0,15), граница плитки — тонкой пунктирной рамкой (кадр шире плитки —
    `core/rules/30` §2, СО-1 п. 3); отдельные кадры — `tNN_src.png`, `tNN_A.png`, `tNN_B.png` (`tNN_map.png`);
  - два режима выбора, оба без человека:
      сетка (по умолчанию) — `--grid=4x3` по зданию (`core/rules/30` §2, ТП4);
      случайная выборка (п. 182) — `--sample=N`: N кадров генератором из клеток `--cell` мм со штрихом хотя бы
      одного DXF; зерно — `--seed`, по умолчанию из SHA-256 входных DXF (как К-12 карты: зерно — хеш файла,
      выбор меняется с любой правкой; исполнитель зерно не выбирает).
    Выбор не зависит от того, что на плитках нарисовано по-разному: клетки берутся по объединению штриха вариантов.

Привязка. Варианты рисуются в мм системы первого DXF. Второй DXF сдвигается к первому по рамке стен, колонн и
фасада (`dxf_classes.measure_shift`; стоп при расхождении > 50 мм) или сдвигом из его места на листе. Кроп
исходника (`--pdf=лист.pdf`) нужен с местом первого DXF на листе: `имя=файл.dxf:K:OX:OY` (K — мм на pt, OX, OY —
начало в pt, y вниз: x_pt = X/K + OX, y_pt = OY − Y/K) или `имя=файл.dxf@cfg.py` (MM_PER_PT, ORIGIN_PT читаются
из текста cfg без выполнения). Нет места — стоп, если задан `--pdf`.

Запуск:
  python3 review/blind_tiles_dxf.py OUT_DIR имя1=A.dxf[:K:OX:OY|@cfg.py] [имя2=B.dxf[...]] [--pdf=лист.pdf]
         [--grid=4x3 | --sample=N [--cell=4000] [--seed=N]] [--ppm=60] [--margin=0.15] [--open-key]
  --open-key — ключ A/B ещё и в tiles.json (не для слепой проверки: для разбора после неё).

Выход (OUT_DIR): tNN.png и отдельные кадры; legend.png; tiles.json — режим, зерно, сетка или клетка, число
кандидатов и SHA-256 их списка, сдвиг, SHA-256 DXF, по плитке: рамка в мм (система первого DXF), рамка в pt листа,
файлы; `.k` — ключ (при двух DXF). Имена вариантов в кадрах и в tiles.json не пишутся (только в `.k`).
"""
import sys, os, re, json, math, random, base64, hashlib, colorsys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import dxf_classes as DC

# class colours (ISO code of the DXF layer); a class not here gets a colour from its name (stable)
PAL = {'A-21': (120, 0, 0), 'A-221': (210, 0, 0), 'A-222': (235, 105, 105), 'A-223': (180, 70, 0), 'A-22G': (0, 175, 225),
       'A-23': (130, 130, 0), 'A-24': (0, 110, 60), 'A-28': (90, 45, 0), 'A-31': (0, 0, 230), 'A-32': (0, 150, 0),
       'A-43': (190, 180, 120), 'A-52': (0, 120, 160), 'A-53': (0, 150, 150), 'A-56': (90, 0, 150), 'A-57': (120, 90, 170),
       'A-61': (200, 160, 0), 'A-64': (90, 90, 170), 'A-66': (0, 100, 210), 'A-68': (255, 50, 0), 'A-69': (140, 190, 0),
       'A-72': (150, 90, 40), 'A-73': (240, 0, 200), 'A-74': (130, 0, 200), 'A-76': (140, 85, 30), 'A-77': (60, 60, 60),
       'A-82': (235, 140, 0), 'A-89': (80, 170, 40), 'A-92': (175, 175, 175), 'A-93': (150, 0, 150), 'A-AXM': (185, 185, 185),
       'A-00': (0, 0, 0)}
UNKNOWN = (0, 230, 0)                                   # layer not in the table: loud colour
SKIP = ('A-90', 'A-91', 'A-AX')                         # texts, marks, dimensions, axes: not drawn (they give the answer away)
F = None


def font(sz=16):
    from PIL import ImageFont
    for p in ('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', '/usr/share/fonts/dejavu/DejaVuSans.ttf'):
        if os.path.exists(p): return ImageFont.truetype(p, sz)
    return ImageFont.load_default()


def colour(c):
    if c in PAL: return PAL[c]
    h = int(hashlib.md5(c.encode()).hexdigest()[:4], 16) / 65535.0
    r, g, b = colorsys.hsv_to_rgb(h, 0.8, 0.75); return (int(r * 255), int(g * 255), int(b * 255))


def tint(col, k):
    return tuple(int(255 - (255 - v) * k) for v in col)


def parse_variant(s):
    """'имя=файл.dxf[:K:OX:OY|@cfg.py]' → (имя, файл, place|None)"""
    n, rest = s.split('=', 1)
    if '@' in rest:
        f, c = rest.split('@', 1); return n, f, place_from_cfg(c)
    m = re.match(r'^(.*\.dxf):([-\d.]+):([-\d.]+):([-\d.]+)$', rest, re.I)
    if m: return n, m.group(1), tuple(float(v) for v in m.groups()[1:])
    return n, rest, None


def place_from_cfg(path):
    """MM_PER_PT и ORIGIN_PT из текста cfg (без выполнения: cfg — данные)"""
    t = open(path, encoding='utf-8').read()
    k = re.search(r'^\s*MM_PER_PT\s*=\s*([\d.]+)', t, re.M); o = re.search(r'ORIGIN_PT\s*=\s*\(\s*([-\d.]+)\s*,\s*([-\d.]+)\s*\)', t)
    if not (k and o): raise SystemExit(f'СТОП: в {path} нет MM_PER_PT или ORIGIN_PT — место DXF на листе задайте :K:OX:OY')
    return float(k.group(1)), float(o.group(1)), float(o.group(2))


def primitives(f, table, dx=0.0, dy=0.0):
    """DXF → [(класс, цвет, заливка?, [кольца в мм]), …]; счёт примитивов на слоях без записи в таблице"""
    import ezdxf
    from ezdxf import disassemble
    doc = ezdxf.readfile(f); out = []; unknown = 0
    for pr in disassemble.to_primitives(disassemble.recursive_decompose(doc.modelspace())):
        e = pr.entity; lay = e.dxf.get('layer', '0'); c, k = DC.split_layer(lay)
        if k in ('T', 'D') or c in SKIP or e.dxftype() in ('TEXT', 'MTEXT', 'ATTRIB', 'DIMENSION'): continue
        if lay in table: col = colour(c)
        else: col = UNKNOWN; unknown += 1
        is_h = e.dxftype() in ('HATCH', 'SOLID')
        if is_h:
            solid = e.dxftype() == 'SOLID' or (e.dxf.get('pattern_name', 'SOLID') or 'SOLID').upper() == 'SOLID'
            col = tint(col, 0.55 if solid else 0.3)
        try:
            if pr.path is not None:
                rings = []
                for sp in (pr.path.sub_paths() if hasattr(pr.path, 'sub_paths') else [pr.path]):
                    pts = [(v.x + dx, v.y + dy) for v in sp.flattening(distance=10)]
                    if len(pts) >= 2: rings.append(pts)
                if is_h and rings: out.append((c, col, True, rings))
                else: out.extend((c, col, False, [r]) for r in rings)
            elif pr.mesh is not None:
                for face in pr.mesh.faces_as_vertices():
                    out.append((c, col, True, [[(v.x + dx, v.y + dy) for v in face]]))
        except Exception:
            pass
    boxed = []
    for c, col, h, rings in out:
        xs = [x for r in rings for x, _ in r]; ys = [y for r in rings for _, y in r]
        boxed.append((c, col, h, rings, (min(xs), min(ys), max(xs), max(ys))))
    return boxed, unknown


def render(prims, box, ppm):
    """кадр box (мм) → картинка: ppm — пикселей на метр; y вверх в DXF → вниз на картинке"""
    from PIL import Image, ImageDraw
    x0, y0, x1, y1 = box; s = ppm / 1000.0
    W, H = int(round((x1 - x0) * s)), int(round((y1 - y0) * s))
    im = Image.new('RGB', (W, H), 'white'); d = ImageDraw.Draw(im)
    sel = [p for p in prims if not (p[4][2] < x0 or p[4][0] > x1 or p[4][3] < y0 or p[4][1] > y1)]
    sel.sort(key=lambda p: (not p[2], p[0] != 'A-92'))       # fills first (zones under everything), then lines
    for c, col, h, rings, _ in sel:
        qs = [[((x - x0) * s, (y1 - y) * s) for x, y in r] for r in rings]
        if h:
            if len(qs) == 1:
                if len(qs[0]) >= 3: d.polygon(qs[0], fill=col)
            else:                                              # even-odd: holes stay empty
                m = Image.new('1', (W, H), 0); md = ImageDraw.Draw(m)
                for q in qs:
                    if len(q) >= 3:
                        t = Image.new('1', (W, H), 0); ImageDraw.Draw(t).polygon(q, fill=1)
                        from PIL import ImageChops
                        m = ImageChops.logical_xor(m, t)
                im.paste(col, mask=m)
        else:
            for q in qs: d.line(q, fill=col, width=2 if c not in ('A-92', 'A-AXM') else 1)
    return im


def dashed_rect(im, r, col=(90, 90, 90), step=10):
    from PIL import ImageDraw
    d = ImageDraw.Draw(im); x0, y0, x1, y1 = r
    for a, b, c, e in ((x0, y0, x1, y0), (x1, y0, x1, y1), (x1, y1, x0, y1), (x0, y1, x0, y0)):
        n = max(1, int(math.hypot(c - a, e - b) / step))
        for i in range(0, n, 2):
            t0, t1 = i / n, min(1, (i + 1) / n); d.line([(a + (c - a) * t0, b + (e - b) * t0), (a + (c - a) * t1, b + (e - b) * t1)], fill=col, width=1)


def src_crop(pg, place, box, ppm):
    """кроп листа по рамке box (мм системы первого DXF)"""
    import pymupdf
    from PIL import Image
    K, OX, OY = place; x0, y0, x1, y1 = box
    r = pymupdf.Rect(x0 / K + OX, OY - y1 / K, x1 / K + OX, OY - y0 / K)
    z = ppm / 1000.0 * K
    pix = pg.get_pixmap(matrix=pymupdf.Matrix(z, z), clip=r, alpha=False)
    im = Image.frombytes('RGB', (pix.width, pix.height), pix.samples)
    W, H = int(round((x1 - x0) * ppm / 1000.0)), int(round((y1 - y0) * ppm / 1000.0))
    return im.resize((W, H)) if im.size != (W, H) else im, [round(v, 2) for v in (r.x0, r.y0, r.x1, r.y1)]


def building_box(prims_list):
    xs0, ys0, xs1, ys1 = [], [], [], []
    for P in prims_list:
        for c, col, h, rings, b in P:
            if c in ('A-92', 'A-AXM') or col == UNKNOWN: continue          # the floor: walls, glazing, furniture, ...
            xs0.append(b[0]); ys0.append(b[1]); xs1.append(b[2]); ys1.append(b[3])
    if not xs0: raise SystemExit('СТОП: в DXF нет примитивов классов плана — плитки не строю')
    m = 500.0
    return (min(xs0) - m, min(ys0) - m, max(xs1) + m, max(ys1) + m)


def grid_tiles(bb, nc, nr):
    X0, Y0, X1, Y1 = bb; wx = (X1 - X0) / nc; wy = (Y1 - Y0) / nr
    return [(X0 + c * wx, Y1 - (r + 1) * wy, X0 + (c + 1) * wx, Y1 - r * wy) for r in range(nr) for c in range(nc)]   # rows from the top


def sample_tiles(bb, prims_list, n, cell, seed, min_prims=10):
    """п. 182: кандидаты — клетки cell×cell мм со штрихом хотя бы одного варианта (≥ min_prims примитивов классов плана);
    выбор — random.Random(seed).sample по упорядоченному списку; человек не участвует"""
    X0, Y0, X1, Y1 = bb; nc = max(1, int((X1 - X0) // cell)); nr = max(1, int((Y1 - Y0) // cell))
    cnt = {}
    for P in prims_list:
        for c, col, h, rings, b in P:
            if c in ('A-92',): continue
            for i in range(max(0, int((b[0] - X0) // cell)), min(nc - 1, int((b[2] - X0) // cell)) + 1):
                for j in range(max(0, int((b[1] - Y0) // cell)), min(nr - 1, int((b[3] - Y0) // cell)) + 1):
                    cnt[(i, j)] = cnt.get((i, j), 0) + 1
    cands = sorted(k for k, v in cnt.items() if v >= min_prims)
    if not cands: raise SystemExit('СТОП: нет клеток со штрихом — выборку не строю')
    pick = random.Random(seed).sample(cands, min(n, len(cands)))
    tiles = [(X0 + i * cell, Y0 + j * cell, X0 + (i + 1) * cell, Y0 + (j + 1) * cell) for i, j in pick]
    return tiles, cands


def legend(classes, table_desc, out):
    from PIL import Image, ImageDraw
    rows = sorted(classes); f = font(15)
    im = Image.new('RGB', (760, 26 * len(rows) + 50), 'white'); d = ImageDraw.Draw(im)
    d.text((10, 8), 'Классы слоёв DXF (линии — цвет класса, заливки — светлее; тексты, марки, размеры, оси не рисуются)', fill='black', font=font(12))
    for i, c in enumerate(rows):
        y = 34 + i * 26; col = UNKNOWN if c == '?' else colour(c)
        d.rectangle((10, y, 46, y + 16), fill=tint(col, 0.55), outline=col, width=3)
        d.text((56, y), f'{c}  {table_desc.get(c, "слой без записи в таблице") if c != "?" else "слой без записи в таблице"}', fill='black', font=f)
    im.save(out)


def seed_from(files):
    h = hashlib.sha256(''.join(DC.sha256(f) for f in files).encode()).hexdigest()
    return int(h[:8], 16)


def main(argv):
    from PIL import Image, ImageDraw
    args = [a for a in argv if not a.startswith('--')]
    opt = dict((a[2:].split('=', 1) + [''])[:2] for a in argv if a.startswith('--'))
    if len(args) not in (2, 3): sys.exit(__doc__)
    OUT = args[0]; V = [parse_variant(s) for s in args[1:]]
    os.makedirs(OUT, exist_ok=True)
    ppm = float(opt.get('ppm') or 60); margin = float(opt.get('margin') or 0.15)
    table = DC.layer_table(); tdesc = DC.class_desc(table)
    shift = (0.0, 0.0, None, 'first')
    if len(V) == 2:                                   # second DXF into the system of the first
        if V[0][2] and V[1][2] and abs(V[0][2][0] - V[1][2][0]) < 1e-6:
            K, ox0, oy0 = V[0][2]; _, ox1, oy1 = V[1][2]
            shift = ((ox1 - ox0) * K, (oy0 - oy1) * K, None, 'place')   # X = (x_pt - OX)·K, Y = (OY - y_pt)·K
        else:
            a = DC.read(V[0][1]); b = DC.read(V[1][1]); shift = DC.parse_shift(opt.get('shift'), a, b)
    P = []; unknown = []
    for i, (n, f, pl) in enumerate(V):
        dx, dy = (shift[0], shift[1]) if i == 1 else (0.0, 0.0)
        p, u = primitives(f, table, dx, dy); P.append(p); unknown.append(u)
    pg = None
    if opt.get('pdf'):
        if not V[0][2]: raise SystemExit('СТОП: --pdf задан, а места первого DXF на листе нет (:K:OX:OY или @cfg.py)')
        import pymupdf
        pg = pymupdf.open(opt['pdf'])[int(opt.get('page') or 0)]
    bb = building_box(P)
    files = [f for _, f, _ in V]
    if opt.get('sample'):
        seed = int(opt['seed']) if opt.get('seed') else seed_from(files)
        cell = float(opt.get('cell') or 4000)
        tiles, cands = sample_tiles(bb, P, int(opt['sample']), cell, seed)
        mode = dict(mode='sample', n=int(opt['sample']), cell_mm=cell, seed=seed, seed_from='--seed' if opt.get('seed') else 'sha256 DXF',
                    candidates=len(cands), candidates_sha256=hashlib.sha256(json.dumps(cands).encode()).hexdigest()); pref = 's'
    else:
        nc, nr = (int(v) for v in (opt.get('grid') or '4x3').split('x'))
        seed = int(opt['seed']) if opt.get('seed') else seed_from(files)
        tiles = grid_tiles(bb, nc, nr); mode = dict(mode='grid', grid=f'{nc}x{nr}', seed=seed); pref = 't'
    rnd = random.Random(seed + 1)                     # A/B order: its own stream, the choice of tiles does not depend on it
    key = {}; rec = []; F = font(18)
    classes = set()
    for P_ in P:
        for c, col, *_ in P_: classes.add('?' if col == UNKNOWN else c)
    for t, b in enumerate(tiles, 1):
        tid = f'{pref}{t:02d}'
        mx, my = (b[2] - b[0]) * margin, (b[3] - b[1]) * margin
        fr = (b[0] - mx, b[1] - my, b[2] + mx, b[3] + my)
        s = ppm / 1000.0; inner = ((b[0] - fr[0]) * s, (fr[3] - b[3]) * s, (b[2] - fr[0]) * s, (fr[3] - b[1]) * s)
        panels = []; r = dict(id=tid, box_mm=[round(v, 1) for v in b], frame_mm=[round(v, 1) for v in fr], files={})
        if pg is not None:
            im, rpt = src_crop(pg, V[0][2], fr, ppm); dashed_rect(im, inner); im.save(os.path.join(OUT, f'{tid}_src.png'))
            panels.append(('исходник', im)); r['frame_pt'] = rpt; r['files']['src'] = f'{tid}_src.png'
        if len(V) == 1:
            im = render(P[0], fr, ppm); dashed_rect(im, inner); im.save(os.path.join(OUT, f'{tid}_map.png'))
            panels.append(('карта классов', im)); r['files']['map'] = f'{tid}_map.png'
        else:
            order = [0, 1]; rnd.shuffle(order)
            key[tid] = {lab: V[i][0] for lab, i in zip('AB', order)}
            for lab, i in zip('AB', order):
                im = render(P[i], fr, ppm); dashed_rect(im, inner); im.save(os.path.join(OUT, f'{tid}_{lab}.png'))
                panels.append((lab, im)); r['files'][lab] = f'{tid}_{lab}.png'
        W = sum(im.width for _, im in panels) + 12 * (len(panels) - 1); H = max(im.height for _, im in panels) + 34
        S = Image.new('RGB', (W, H), 'white'); d = ImageDraw.Draw(S); x = 0
        for lab, im in panels:
            S.paste(im, (x, 34)); d.text((x + 6, 6), f'{tid} · {lab}', fill='black', font=F); x += im.width + 12
        S.save(os.path.join(OUT, f'{tid}.png')); r['files']['pair'] = f'{tid}.png'; rec.append(r)
        print(tid, [round(v) for v in b])
    legend(classes, tdesc, os.path.join(OUT, 'legend.png'))
    meta = dict(tool='review/blind_tiles_dxf.py', **mode, ppm=ppm, margin=margin, building_box_mm=[round(v, 1) for v in bb],
                dxf_sha256=[DC.sha256(f) for f in files], shift_second_mm=dict(dx=round(shift[0], 1), dy=round(shift[1], 1),
                residual=None if shift[2] is None else round(shift[2], 1), how=shift[3]) if len(V) == 2 else None,
                unknown_layer_prims=unknown, pdf_sha256=DC.sha256(opt['pdf']) if opt.get('pdf') else None, tiles=rec)
    if len(V) == 2:
        open(os.path.join(OUT, '.k'), 'w').write(base64.b64encode(json.dumps(key, ensure_ascii=False)[::-1].encode()).decode())
        if 'open-key' in opt: meta['key'] = key
    json.dump(meta, open(os.path.join(OUT, 'tiles.json'), 'w'), ensure_ascii=False, indent=1)
    print('плиток', len(rec), '|', mode['mode'], '| зерно', seed, '| сдвиг второго', meta['shift_second_mm'], '| без записи в таблице', unknown,
          '| ключ записан' if len(V) == 2 else '')
    return 0


def read_key(path):
    """ключ .k → {плитка: {A: имя, B: имя}}"""
    return json.loads(base64.b64decode(open(path).read()).decode()[::-1])


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
