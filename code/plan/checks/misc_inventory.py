# Check 3.7 (29.09.2026): what is left unclassified. Groups the 'misc' objects (layer A-00, "Прочий элемент") of a
#   floor by shape: identical drawings (same primitives relative to the bbox, rounded to 0.1 pt) form one group, the rest
#   are grouped by size and make-up. Out: misc_inventory.json (groups with count, size, make-up, where) and
#   misc_inventory.png (one example per group over the source, the object in red).
# Run in a floor folder: python3 misc_inventory.py [N groups on the sheet, default 36]
import pickle, sys, math, json, collections, hashlib, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import load, pts, PDF, MM, MM_PER_PT
import pymupdf as fitz
from PIL import Image, ImageDraw, ImageFont
N = int(sys.argv[1]) if len(sys.argv) > 1 else 36
KEYS = ('misc',)
P = load(); I = pickle.load(open('inst_final.pkl', 'rb'))
def bbox(ids):
    q = [p for i in ids for p in pts(P[i])]
    return (min(x for x, y in q), min(y for x, y in q), max(x for x, y in q), max(y for x, y in q))
def sig(ids, b):
    rows = []
    for i in ids:
        p = P[i]; rows.append((p[0], round(p[1] or 0, 2), str(p[2]), str(p[3]), tuple((round(x - b[0], 1), round(y - b[1], 1)) for x, y in pts(p))))
    return hashlib.md5(repr(sorted(rows)).encode()).hexdigest()[:10]
def makeup(ids):
    c = collections.Counter()
    for i in ids:
        p = P[i]
        if p[0] == 'l': c['линии'] += 1
        elif p[0] == 'c': c['дуги'] += 1
        elif p[3] is not None and p[2] is None: c['заливки'] += 1
        else: c['контуры'] += 1
    return dict(c)
def colours(ids):
    c = collections.Counter()
    for i in ids:
        p = P[i]; col = p[2] if p[2] is not None else p[3]
        if col is not None: c[tuple(round(v, 2) for v in col)] += 1
    return [list(k) for k, _ in c.most_common(3)]
G = collections.defaultdict(list)
for n, q in enumerate(I):
    if q['key'] not in KEYS or not q['prims']: continue
    b = bbox(q['prims']); G[sig(q['prims'], b)].append((n, b))
# groups of one: merge by size (50 mm) and make-up
out = []; single = collections.defaultdict(list)
for s, v in G.items():
    if len(v) > 1: out.append(('same', s, v))
    else:
        n, b = v[0]; ids = I[n]['prims']
        w, h = sorted([(b[2] - b[0]) * MM_PER_PT, (b[3] - b[1]) * MM_PER_PT], reverse=True)
        mk = makeup(ids); k = (round(w / 100) * 100, round(h / 100) * 100, tuple(sorted(mk)), min(len(ids), 20) // 5)
        single[k].append((n, b))
for k, v in single.items(): out.append(('similar', repr(k), v))
res = []
for kind, s, v in out:
    n0, b0 = v[0]; ids = I[n0]['prims']
    w, h = (b0[2] - b0[0]) * MM_PER_PT, (b0[3] - b0[1]) * MM_PER_PT
    res.append(dict(kind=kind, sig=s, count=len(v), size_mm=[round(w), round(h)], prims=len(ids), makeup=makeup(ids),
                    colours=colours(ids), at_pt=[[round((b[0] + b[2]) / 2, 1), round((b[1] + b[3]) / 2, 1)] for _, b in v[:40]],
                    inst=[n for n, _ in v], area_mm2=sum(((b[2] - b[0]) * (b[3] - b[1])) * MM_PER_PT ** 2 for _, b in v)))
res.sort(key=lambda r: (-r['count'], -r['area_mm2']))
tot = sum(r['count'] for r in res)
json.dump(dict(objects=tot, groups=len(res), groups_same=sum(1 for r in res if r['kind'] == 'same'), list=res), open('misc_inventory.json', 'w'), ensure_ascii=False, indent=0)
print('misc objects', tot, 'groups', len(res), 'identical-shape groups', sum(1 for r in res if r['kind'] == 'same'),
      'objects in them', sum(r['count'] for r in res if r['kind'] == 'same'))
# sheet: one example per group
pg = fitz.open(PDF)[0]; f = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 11)
T = 200; cols = 6; sel = res[:N]
if not sel:
    # (code 007, Т3-1) a floor with no 'misc' left: PIL cannot write an empty image, and under set -e of run.sh the crash
    #   cancelled every check after this one and the gate itself - the sheet says there is nothing instead
    sh = Image.new('RGB', (cols * (T + 4), 40), 'white')
    ImageDraw.Draw(sh).text((6, 12), '«Прочего» нет: 0 объектов, 0 групп (3.7а)', fill=(0, 0, 0), font=f)
    sh.save('misc_inventory.png'); print('sheet', sh.size, '- no misc groups'); sys.exit(0)
sh = Image.new('RGB', (cols * (T + 4), ((len(sel) + cols - 1) // cols) * (T + 30)), 'white'); d_ = ImageDraw.Draw(sh)
for k, r in enumerate(sel):
    n0 = r['inst'][0]; ids = I[n0]['prims']; b = bbox(ids)
    cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2; h = max(4, max(b[2] - b[0], b[3] - b[1]) * 0.8); Z = T / (2 * h)
    pix = pg.get_pixmap(matrix=fitz.Matrix(Z, Z), clip=fitz.Rect(cx - h, cy - h, cx + h, cy + h))
    im = Image.frombytes('RGB', (pix.width, pix.height), pix.samples).resize((T, T))
    im = Image.blend(im, Image.new('RGB', im.size, 'white'), 0.55); dr = ImageDraw.Draw(im)
    for i in ids:
        q = [((x - cx + h) * Z, (y - cy + h) * Z) for x, y in pts(P[i])]
        if len(q) > 1: dr.line(q + ([q[0]] if P[i][0] == 'qu' else []), fill=(230, 0, 0), width=2)
    x0, y0 = (k % cols) * (T + 4), (k // cols) * (T + 30)
    sh.paste(im, (x0, y0 + 28))
    d_.text((x0 + 2, y0), f"#{k+1}: {r['count']} шт, {r['size_mm'][0]}×{r['size_mm'][1]} мм", fill=(0, 0, 0), font=f)
    d_.text((x0 + 2, y0 + 13), f"{r['prims']} прим., у ({r['at_pt'][0][0]:.0f}, {r['at_pt'][0][1]:.0f})", fill=(90, 90, 90), font=f)
sh.save('misc_inventory.png'); print('sheet', sh.size)
