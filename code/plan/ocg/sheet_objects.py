"""ocg/sheet_objects.py - code 010 (package 4): a sheet of places of objects of the габаритный list (Э10, objects_list.json)
by type - the source around each object with its outline and the label «type - DXF layer - name» (К-1: МФУ and wall screens
on A-82; any type for a review sheet). The outlines are mm of the list, back to pt of the sheet the steps read by
cfg.MM_PER_PT and cfg.ORIGIN_PT (ocg/sheet.py). Also counts the block inserts of these types (block name «…_<type>») by
layer in both DXF of the run (detailed and габаритный).
usage: python3 sheet_objects.py out.png types [half_pt=40] [Z=4] [cols=4] [objects_list.json]   (floor folder)
  types: comma list of the list's types, e.g. mfp,equip"""
import sys, os, json, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import sheet
import pymupdf
from PIL import Image, ImageDraw, ImageFont
out, types = sys.argv[1], set(sys.argv[2].split(','))
h = float(sys.argv[3]) if len(sys.argv) > 3 else 40.0; Z = float(sys.argv[4]) if len(sys.argv) > 4 else 4.0
cols = int(sys.argv[5]) if len(sys.argv) > 5 else 4
lst = sys.argv[6] if len(sys.argv) > 6 else os.path.join('out_outline', 'objects_list.json')
DXFS = [os.path.join('out', sheet.OUT + '_engineering.dxf'), os.path.join('out_outline', sheet.OUT + '_outline.dxf')]
K, OX, OY = sheet.K, sheet.OX, sheet.OY
def pt(p): return (OX + p[0] / K, OY - p[1] / K)
rows = [r for r in json.load(open(lst))['objects'] if r['type'] in types]
F = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 12)
pg = pymupdf.open(sheet.PDF)[0]; tiles = []
for n, r in enumerate(rows):
    cx, cy = pt(r['center_mm']); x0, y0 = cx - h, cy - h
    pix = pg.get_pixmap(matrix=pymupdf.Matrix(Z, Z), clip=pymupdf.Rect(x0, y0, cx + h, cy + h), alpha=False)
    im = Image.frombytes('RGB', (pix.width, pix.height), pix.samples); d = ImageDraw.Draw(im)
    ol = [((pt(q)[0] - x0) * Z, (pt(q)[1] - y0) * Z) for q in r.get('outline_mm') or []]
    if len(ol) >= 2: d.line(ol + ol[:1], fill=(0, 170, 60) if r['layer'] == 'A-82' else (230, 0, 0), width=3)
    d.rectangle([0, 0, im.width, 30], fill='white')
    d.text((3, 1), f"{n + 1}. {r['type_ru']} — слой {r['layer']} — {r.get('block', '')}", font=F, fill=(0, 0, 0))
    d.text((3, 15), r['name'][:70], font=F, fill=(60, 60, 60))
    tiles.append(im)
print('objects', len(rows), 'by layer of the list', dict(collections.Counter(r['layer'] for r in rows)))
import ezdxf
for dxf in DXFS:
    if not os.path.exists(dxf): continue
    cnt = collections.Counter(); inner = collections.Counter(); doc = ezdxf.readfile(dxf)
    for e in doc.modelspace().query('INSERT'):
        t = e.dxf.name.rsplit('_', 1)[-1]
        if t in types:
            cnt[(t, e.dxf.layer)] += 1
            for x in doc.blocks[e.dxf.name]: inner[(t, x.dxf.layer)] += 1
    print(os.path.basename(dxf), '| inserts by (type, layer):', dict(cnt), '| entities inside their blocks by layer:', dict(inner))
if tiles:
    tw, th = tiles[0].size; nr = (len(tiles) + cols - 1) // cols
    img = Image.new('RGB', (cols * (tw + 8), nr * (th + 8)), 'white')
    for n, t in enumerate(tiles): img.paste(t, ((n % cols) * (tw + 8), (n // cols) * (th + 8)))
    img.save(out); print(out, img.size)
