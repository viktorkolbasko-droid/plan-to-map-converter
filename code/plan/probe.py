# Probe a new Revit PDF before configuring the floor: line-class table, grid axes with names and mm, explication,
# suggested windows. Usage: python3 probe.py file.pdf [out_prefix]   (writes <prefix>_probe.json, <prefix>_grid.png)
import sys, re, json, math, collections
import pymupdf as fitz
from PIL import Image, ImageDraw, ImageFont
pdf = sys.argv[1]; pref = sys.argv[2] if len(sys.argv) > 2 else pdf.rsplit('.', 1)[0]
doc = fitz.open(pdf); pg = doc[0]; M = pg.rotation_matrix
PW, PH = pg.rect.width, pg.rect.height          # page.rect is the displayed (rotated) page
dr = pg.get_drawings()
R = dict(pdf=pdf, page=[round(PW), round(PH)], rotation=pg.rotation, creator=doc.metadata.get('creator'), producer=doc.metadata.get('producer'))
# ---- line classes: (kind, width, stroke colour, fill colour) -> count, total length
cl = collections.Counter(); cl_len = collections.Counter()
segs = []
for d in dr:
    w = round(d.get('width') or 0, 2); sc = tuple(round(c, 2) for c in d['color']) if d.get('color') else None
    fc = tuple(round(c, 2) for c in d['fill']) if d.get('fill') else None
    for it in d['items']:
        if it[0] == 'l':
            a = it[1] * M; b = it[2] * M; L = math.hypot(b.x - a.x, b.y - a.y)
            if sc is not None: segs.append((a.x, a.y, b.x, b.y, w, sc))
            cl[('l', w, sc, fc)] += 1; cl_len[('l', w, sc, fc)] += L
        else:
            cl[(it[0], w, sc, fc)] += 1
R['line_classes'] = [dict(kind=k[0], width=k[1], stroke=k[2], fill=k[3], n=n, len_pt=round(cl_len[k])) for k, n in cl.most_common(40)]
# ---- text
words = []
for x in pg.get_text('words'):
    r = fitz.Rect(x[:4]) * M; words.append(((r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2, x[4], (r.x0, r.y0, r.x1, r.y1)))
txt = pg.get_text()
R['explication'] = [(m.group(1), m.group(2).strip(), m.group(3).strip()) for m in re.finditer(r'(?m)^(\d{1,3})\n([^\n]+)\n(\d+(?:[.,]\d+)?\s*м²)$', txt)]
tb = [w for w in words if w[2] in ('Изм.', 'Кол.уч.', 'Лист', 'Стадия', 'Формат')]
R['title_block_words'] = [(w[2], round(w[0]), round(w[1])) for w in tb][:8]
# ---- grid axes: dashed collinear strokes (many pieces, long span), grey or pink, named by their bubbles (gridaxes.py, code 011)
import os as _os; sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
import gridaxes as GA
axes = GA.find_axes(segs, words, PW, PH)
# ---- mm per interval from dimension texts between consecutive axes (chains outside the building)
for o in axes:
    iv = GA.interval_mm(o, axes[o], words); R['intervals_' + o] = iv
ks = []
for o in axes:
    for (a, b), v in zip(zip(axes[o][:-1], axes[o][1:]), R['intervals_' + o]):
        if v: ks.append(v / (b['pos'] - a['pos']))
k = sorted(ks)[len(ks) // 2] if ks else None
R['mm_per_pt_median'] = round(k, 3) if k else None
R['mm_per_pt_spread'] = [round(min(ks), 3), round(max(ks), 3)] if ks else None
def cum(o):
    lst = axes[o]; iv = R['intervals_' + o]; out = [0]
    for (a, b), v in zip(zip(lst[:-1], lst[1:]), iv):
        out.append(out[-1] + (v if v else round((b['pos'] - a['pos']) * (k or 66) / 5) * 5))
    return out
R['axes_v'] = axes['v']; R['axes_h'] = axes['h']
if axes['v']: R['AX_X'] = [a['pos'] for a in axes['v']]; R['AX_XN'] = [a['name'] for a in axes['v']]; R['AX_XMM'] = cum('v')
if axes['h']:   # y axes: mm grows upward -> order by descending y (bottom axis = 0)
    hh = sorted(axes['h'], key=lambda a: -a['pos']); axes['h'] = hh; R['intervals_h'] = GA.interval_mm('h', sorted(hh, key=lambda a: a['pos']), words)[::-1]
    R['AX_Y'] = [a['pos'] for a in hh]; R['AX_YN'] = [a['name'] for a in hh]
    iv = R['intervals_h']; out = [0]
    for (a, b), v in zip(zip(hh[:-1], hh[1:]), iv):
        out.append(out[-1] + (v if v else round((a['pos'] - b['pos']) * (k or 66) / 5) * 5))
    R['AX_YMM'] = out
# code 011 (ПК4-П1): no scale found on the sheet (none of the dimension numbers gives 55-75 mm/pt) - the mm of the axes above
#   would be counted at 66 mm/pt, silently wrong: they are not given; the copies x k of the series 0.50-2.00 show at which
#   k the numbers agree - the scale of the sheet, the field and the copy for cfg (plan/rules/10 §2, plan/rules/20 §1)
if not R['mm_per_pt_median']:
    for f_ in ('AX_XMM', 'AX_YMM'): R.pop(f_, None)
    R['copies_search'] = GA.copies_search({'v': R.get('axes_v', []), 'h': sorted(axes['h'], key=lambda a: a['pos'])}, words) if (axes['v'] or axes['h']) else None
json.dump(R, open(pref + '_probe.json', 'w'), ensure_ascii=False, indent=1, default=str)
# ---- grid thumbnail (every 50 pt) for picking windows and boxes by eye
Z = 1.6; pix = pg.get_pixmap(matrix=fitz.Matrix(Z, Z)); im = Image.frombytes('RGB', (pix.width, pix.height), pix.samples)
im = Image.blend(im, Image.new('RGB', im.size, 'white'), 0.35); dd = ImageDraw.Draw(im)
f = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 11)
for x in range(0, int(PW), 50):
    dd.line([(x * Z, 0), (x * Z, im.height)], fill=(255, 0, 0) if x % 100 == 0 else (255, 170, 170), width=1); dd.text((x * Z + 2, 2), str(x), fill=(200, 0, 0), font=f)
for y in range(0, int(PH), 50):
    dd.line([(0, y * Z), (im.width, y * Z)], fill=(0, 0, 255) if y % 100 == 0 else (170, 170, 255), width=1); dd.text((2, y * Z + 2), str(y), fill=(0, 0, 200), font=f)
im.save(pref + '_grid.png')
print(json.dumps({k_: R[k_] for k_ in ('page', 'rotation', 'mm_per_pt_median', 'mm_per_pt_spread', 'AX_X', 'AX_XN', 'AX_XMM', 'AX_Y', 'AX_YN', 'AX_YMM') if k_ in R}, ensure_ascii=False))
if not R['mm_per_pt_median']:
    _cs = R.get('copies_search')
    print('МАСШТАБ НЕ НАЙДЕН: ни одно число размера между осями не даёт 55–75 мм/pt — мм осей не печатаются (по 66 мм/pt они были бы неверны)')
    if _cs:
        print(f"ПЕРЕБОР КОПИЙ k = 0,50…2,00: размеры сошлись при k = {_cs['band'][0]:.2f}…{_cs['band'][1]:.2f} ({_cs['matched']} из {_cs['of']} интервалов): "
              f"лист — {_cs['sheet_mm_per_pt']} мм/pt; cfg.SHEET_MM_PER_PT = {_cs['sheet_mm_per_pt']}; копия в 63,5 мм/pt — k = {_cs['k']}: "
              f"python3 norm.py --copy {pdf} {_cs['k']} <копия.pdf>, затем probe.py и разметка cfg — по копии (plan/rules/10 §2)")
    else:
        print('ПЕРЕБОР КОПИЙ k = 0,50…2,00: размеры не сошлись ни при одном k — масштаб по размерной надписи и её длине в pt вручную (plan/rules/20 §1)')
# code 010 (К-3; №98): a sheet outside 60-70 mm/pt is read by the code as its copy at 63.5 mm/pt - cfg of such a floor is
#   written in pt of the copy: the field SHEET_MM_PER_PT and probe.py once more on the copy
import norm as _norm
if R.get('mm_per_pt_median') and _norm.factor(R['mm_per_pt_median'], 'revit') != 1.0:
    _k = _norm.factor(R['mm_per_pt_median'], 'revit')
    print(f"МАСШТАБ: лист {R['mm_per_pt_median']} мм/pt вне полосы 60–70 — код читает его копию в 63,5 мм/pt (k = {_k:.6f}): "
          f"cfg.SHEET_MM_PER_PT = {R['mm_per_pt_median']}; копия — python3 norm.py --copy {pdf} {_k:.10f} <копия.pdf>; "
          f"probe.py и разметка cfg — по копии (plan/rules/10 §2)")
print('explication rows', len(R['explication']), R['explication'][:4])
print('line classes (top 12):'); [print(' ', c) for c in R['line_classes'][:12]]
