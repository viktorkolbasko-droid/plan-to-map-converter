# Through elements (29.09.2026): the operator boxes (cfg.MANUAL) of stairs and lifts of a reference floor, mapped onto
#   another floor by the pair registration of crossfloor.json - a starting point for that floor's own MANUAL boxes, to be
#   checked on the picture and fitted to the floor's own drawing (the registration is good to 60-400 mm).
# Usage (work folder as cwd): python3 xf_boxes.py crossfloor.json REF TARGET [keys=stair,lift] [out.png]
import sys, json, os, importlib.util, math
import numpy as np
from shapely.geometry import box
from shapely.affinity import affine_transform
J = json.load(open(sys.argv[1])); REF, TGT = sys.argv[2], sys.argv[3]
KEYS = (sys.argv[4] if len(sys.argv) > 4 else 'stair,lift').split(','); OUT = sys.argv[5] if len(sys.argv) > 5 else f'xf_boxes_{REF}_{TGT}.png'
def floor(d):
    spec = importlib.util.spec_from_file_location('cfg_' + d, os.path.join(d, 'cfg.py'))
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')); sys.path.insert(0, d)
    cfg = importlib.util.module_from_spec(spec); spec.loader.exec_module(cfg); sys.path.pop(0)
    if len(getattr(cfg, 'AX_X', [])) >= 2 and len(getattr(cfg, 'AX_Y', [])) >= 2:
        kx = np.polyfit(cfg.AX_X, cfg.AX_XMM, 1); ky = np.polyfit(cfg.AX_Y, cfg.AX_YMM, 1)
    else:                                          # no grid on the sheet (floor 6): scale and origin from cfg, as common.py
        k = cfg.MM_PER_PT; ox, oy = cfg.ORIGIN_PT; kx = np.array([k, -k * ox]); ky = np.array([-k, k * oy])
    pdf = [os.path.join(d, f) for f in os.listdir(d) if f.lower().endswith('.pdf')][0]
    return cfg, kx, ky, pdf
ca, ka, la, _ = floor(REF); cb, kb, lb, pdfb = floor(TGT)
key = f'{REF}-{TGT}' if f'{REF}-{TGT}' in J['pairs'] else f'{TGT}-{REF}'
r = J['pairs'][key]['registration']
def ref_to_tgt(g):
    g = affine_transform(g, [ka[0], 0, 0, la[0], ka[1], la[1]])
    if key.startswith(REF + '-'): g = affine_transform(g, [1 / r['s'], 0, 0, 1 / r['s'], -r['tx'] / r['s'], -r['ty'] / r['s']])
    else: g = affine_transform(g, [r['s'], 0, 0, r['s'], r['tx'], r['ty']])
    return affine_transform(g, [1 / kb[0], 0, 0, 1 / lb[0], -kb[1] / kb[0], -lb[1] / lb[0]])
rows = []
from manual8 import bbox_of as _bbox8   # code 008: polygon elements (Т4-7) by their bbox
for m in getattr(ca, 'MANUAL', []):
    if m[0] not in KEYS: continue
    for bx in m[3]:
        g = ref_to_tgt(box(*_bbox8(bx))).bounds; rows.append((m[0], m[1], [round(v, 1) for v in g]))
print(f'# {REF} -> {TGT} by {key}, median {r.get("median_mm")} mm')
for k, n, b in rows: print(f"('{k}','{n}','A-24----E-' if '{k}'=='stair' else 'A-66----E-',[({b[0]},{b[1]},{b[2]},{b[3]})]),")
import pymupdf as fitz
from PIL import Image, ImageDraw, ImageFont
pg = fitz.open(pdfb)[0]; T = 420; f = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 12)
sh = Image.new('RGB', (min(3, len(rows)) * (T + 6), ((len(rows) + 2) // 3) * (T + 22)), 'white'); d = ImageDraw.Draw(sh)
for k_, (k, n, b) in enumerate(rows):
    cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2; h = max(b[2] - b[0], b[3] - b[1]) * 0.8 + 10; Z = T / (2 * h)
    pix = pg.get_pixmap(matrix=fitz.Matrix(Z, Z), clip=fitz.Rect(cx - h, cy - h, cx + h, cy + h))
    im = Image.frombytes('RGB', (pix.width, pix.height), pix.samples).resize((T, T)); dr = ImageDraw.Draw(im)
    dr.rectangle([(b[0] - cx + h) * Z, (b[1] - cy + h) * Z, (b[2] - cx + h) * Z, (b[3] - cy + h) * Z], outline=(230, 0, 0), width=2)
    x0, y0 = (k_ % 3) * (T + 6), (k_ // 3) * (T + 22); sh.paste(im, (x0, y0 + 20))
    d.text((x0 + 2, y0 + 2), f'{n[:48]} {b}', fill=(0, 0, 0), font=f)
sh.save(OUT); print('#', OUT, sh.size)
