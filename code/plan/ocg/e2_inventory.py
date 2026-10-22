"""Э2: class table of the AutoCAD sheet by OCG layer (zero-length segments dropped, PDF_FLATTENED) and a render of every
layer alone through the PDF renderer itself (set_layer_ui_config), plus a contact sheet with names. Writes inventory/."""
import pymupdf, numpy as np, json, collections, os, sys, math, pickle, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import sheet
from PIL import Image, ImageDraw, ImageFont
os.makedirs('inventory', exist_ok=True)
F = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 18)
d = pymupdf.open(sheet.PDF); pg = d[0]
t0 = time.time()
dr = pg.get_drawings(extended=True)
pickle.dump(dr, open('drawings_ext.pkl', 'wb'))
print('drawings', len(dr), round(time.time() - t0, 1), 's')
rows = collections.defaultdict(lambda: [0, 0, 0.0])   # paths, segments, length
zero = collections.Counter(); total = collections.Counter()
for x in dr:
    if x['type'] in ('clip', 'group'): continue
    L = sheet.strip(x.get('layer')) or '—'
    col = tuple(round(v, 2) for v in x['color']) if x.get('color') else None
    fil = tuple(round(v, 2) for v in x['fill']) if x.get('fill') else None
    w = round(x.get('width') or 0, 2); fo = round(x.get('fill_opacity') or 1, 2); so = round(x.get('stroke_opacity') or 1, 2)
    n = 0; ln = 0.0
    for it in x['items']:
        total[L] += 1
        if it[0] == 'l':
            l = math.hypot(it[2].x - it[1].x, it[2].y - it[1].y)
            if l < 0.01: zero[L] += 1; continue
            n += 1; ln += l
        elif it[0] == 'c':
            l = abs(it[4] - it[1]); n += 1; ln += l
        elif it[0] in ('re', 'qu'):
            n += 1
    if n == 0: continue
    k = (L, x['type'], col, fil, w, fo, so)
    r = rows[k]; r[0] += 1; r[1] += n; r[2] += ln
tab = sorted(([*k, *v] for k, v in rows.items()), key=lambda r: (r[0], -r[8]))
json.dump(dict(rows=tab, zero=zero, total=total), open('inventory/classes.json', 'w'), ensure_ascii=False, indent=0, default=str)
with open('inventory/classes.md', 'w') as f:
    f.write('| Слой OCG | Вид | Обводка | Заливка | Толщина | Непрозр. заливки | Путей | Отрезков | Длина, pt |\n|---|---|---|---|---|---|---|---|---|\n')
    for r in tab:
        f.write('| %s | %s | %s | %s | %s | %s | %d | %d | %.0f |\n' % (r[0], r[1], r[2], r[3], r[4], r[5], r[7], r[8], r[9]))
    f.write('\nОтрезков нулевой длины по слоям (выброшены до таблицы, PDF_FLATTENED): ' + ', '.join('%s %d из %d' % (k, zero[k], total[k]) for k in sorted(zero, key=lambda k: -zero[k])) + '\n')
print('table rows', len(tab), 'zero-length', sum(zero.values()), 'of', sum(total.values()))
# per-layer render through the PDF renderer
uis = d.layer_ui_configs(); Z = 0.42
tiles = []
for u in uis:
    for v in uis: d.set_layer_ui_config(v['number'], 2)
    d.set_layer_ui_config(u['number'], 0)
    pix = d[0].get_pixmap(matrix=pymupdf.Matrix(Z, Z), clip=pymupdf.Rect(*sheet.RENDER_BOX) if sheet.RENDER_BOX else d[0].rect)   # cfg.OCG_RENDER_BOX
    im = Image.frombytes('RGB', (pix.width, pix.height), pix.samples)
    ink = int((np.asarray(im.convert('L')) < 245).sum())
    name = sheet.strip(u['text'])
    im.save('inventory/layer_%02d.png' % u['number'])
    t = Image.new('RGB', (im.width, im.height + 28), 'white'); t.paste(im, (0, 28))
    ImageDraw.Draw(t).text((4, 3), '%d. %s — %d px чернил' % (u['number'], name, ink), fill='black', font=F)
    ImageDraw.Draw(t).rectangle((0, 0, t.width - 1, t.height - 1), outline=(180, 180, 180))
    tiles.append(t)
for v in uis: d.set_layer_ui_config(v['number'], 0)
cols = 6; w, h = tiles[0].size; rows_n = (len(tiles) + cols - 1) // cols
S = Image.new('RGB', (cols * w, rows_n * h), 'white')
for i, t in enumerate(tiles): S.paste(t, ((i % cols) * w, (i // cols) * h))
S.save('inventory/layers_sheet.png'); print('sheet', S.size, round(time.time() - t0, 1), 's')
