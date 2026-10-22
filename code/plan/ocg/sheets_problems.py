"""Sheets of the problems left for the owner's decision (owner 06.10.2026: «визуализируй проблемы и покажи их картинками,
чтобы я мог оценить и принять решение»). One PNG per group; every crop: left — the source as drawn, right — the result over
the faded source (walls by class, glass, doors, furniture outlines), a red ring at the place, a caption under it.
Groups come from the reports of the run folder: joints.json (body overlaps, glass ends at an angle), furniture.json (left for
review, desks of an unfamiliar size), core.json (hanging lines), doors.json + doors_check.json (doors), walls_clean.json
(irregularities thinner than the wall), checks json (breaks without a door, voids).
usage: python3 sheets_problems.py <out dir> [ocg_checks.json]   (floor folder; code 009: run.sh sheets)"""
import sys, os, json, pickle, math, collections
import numpy as np, pymupdf
from PIL import Image, ImageDraw, ImageFont
import os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import sheet; from e7_comp import geom, load_prims, load_walls
OUT = sys.argv[1]; CHK = sys.argv[2] if len(sys.argv) > 2 else None
os.makedirs(OUT, exist_ok=True); K = sheet.K
P = load_prims()['P']; objs = pickle.load(open('objects.pkl', 'rb'))['objs']; W = load_walls()['bodies']
pg = pymupdf.open(sheet.PDF)[0]
F = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 15); FB = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 17)
WCOL = {'gkl': (230, 140, 40), 'cap': (130, 60, 150), 'column': (90, 90, 90), 'ext': (40, 40, 40), 'blk': (40, 40, 40)}
OCOL = {'door': (20, 140, 60), 'glass': (30, 110, 220), 'chair': (220, 40, 40), 'armchair': (200, 40, 200), 'desk': (170, 110, 50),
        'mtable': (40, 60, 200), 'dtable': (40, 60, 200), 'rtable': (40, 60, 200), 'round': (40, 160, 220), 'sofa': (130, 40, 160),
        'counter': (230, 120, 0), 'storage': (120, 120, 0), 'kitchen': (150, 80, 30), 'coreblock': (130, 60, 150), 'coreline': (230, 0, 0),
        'lpart': (230, 0, 0), 'shaft': (0, 140, 0), 'lift': (200, 0, 200)}
# index of drawn geometry for fast crops
DR = []
for c, g in W: DR.append(('wall', c, g))
for o in objs:
    col = OCOL.get(o['key'])
    if not col or not o['ids']: continue
    for i in (o.get('outline') if o['key'] in ('chair', 'armchair', 'desk', 'mtable', 'dtable', 'rtable', 'round', 'sofa', 'counter', 'storage', 'kitchen') and o.get('outline') else o.get('draw', o['ids'])):
        p = P[i]
        if p['kind'] == 'removed' or len(p['p']) < 2: continue
        DR.append(('obj', o['key'], geom(p)))
import shapely
DT = shapely.STRtree([g for _, _, g in DR])
def crop(x, y, half, cap, Z=None):
    x0, y0, x1, y1 = x - half, y - half, x + half, y + half
    Z = Z or max(3.0, min(14.0, 320.0 / half))
    pix = pg.get_pixmap(matrix=pymupdf.Matrix(Z, Z), clip=pymupdf.Rect(x0, y0, x1, y1), alpha=False)
    src = Image.frombytes('RGB', (pix.width, pix.height), pix.samples)
    res = Image.blend(Image.new('RGB', src.size, 'white'), src.convert('L').convert('RGB'), 0.35).convert('RGBA')
    ov = Image.new('RGBA', res.size, (0, 0, 0, 0)); d = ImageDraw.Draw(ov)
    def T(cs): return [((a - x0) * Z, (b - y0) * Z) for a, b in cs]
    B = shapely.geometry.box(x0, y0, x1, y1)
    for j in DT.query(B):
        kind, c, g = DR[j]
        for q in getattr(g, 'geoms', [g]):
            if q.geom_type == 'Polygon':
                col = WCOL.get(c, (60, 60, 60)) if kind == 'wall' else OCOL.get(c, (0, 0, 0))
                d.polygon(T(q.exterior.coords), fill=col + ((150,) if kind == 'wall' else (40,)), outline=col + (255,))
                for h in q.interiors: d.polygon(T(h.coords), fill=(255, 255, 255, 0), outline=(255, 0, 0, 255))
            elif q.geom_type == 'LineString':
                d.line(T(q.coords), fill=OCOL.get(c, (0, 0, 0)) + (255,), width=2)
    r = 0.12 * half * Z; cx, cy = (x - x0) * Z, (y - y0) * Z
    d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=(255, 0, 0, 255), width=3)
    res = Image.alpha_composite(res, ov).convert('RGB')
    w, h = src.size; im = Image.new('RGB', (2 * w + 8, h + 44), 'white'); im.paste(src, (0, 0)); im.paste(res, (w + 8, 0))
    dd = ImageDraw.Draw(im); dd.text((4, h + 4), cap[:120], fill='black', font=F)
    sbar = 1000 / K * Z; dd.line((w + 12, h - 10, w + 12 + sbar, h - 10), fill='black', width=3); dd.text((w + 16 + sbar, h - 24), '1 м', fill='black', font=F)
    return im
def sheet(name, title, items, half, cols=3, maxn=24):
    items = items[:maxn]
    if not items: return None
    ims = [crop(x, y, half, f'#{n + 1}  {cap}') for n, (x, y, cap) in enumerate(items)]
    sc = 0.6; ims = [i.resize((int(i.width * sc), int(i.height * sc))) for i in ims]
    w = max(i.width for i in ims); h = max(i.height for i in ims); rows = (len(ims) + cols - 1) // cols
    S = Image.new('RGB', (cols * (w + 10) + 10, rows * (h + 10) + 60), 'white'); d = ImageDraw.Draw(S)
    d.text((10, 10), title, fill='black', font=FB); d.text((10, 34), 'слева — исходник; справа — результат поверх бледного исходника; красное кольцо — место', fill='black', font=F)
    for k, im in enumerate(ims): S.paste(im, (10 + (k % cols) * (w + 10), 60 + (k // cols) * (h + 10)))
    f = os.path.join(OUT, name + '.png'); S.save(f); print(f, len(items)); return f
made = {}
J = json.load(open('joints.json')) if os.path.exists('joints.json') else {}
pb = J.get('places_after', {}).get('bodies', []); pp = J.get('places_after', {}).get('panes', [])
made['колонна_и_перегородка'] = sheet('01_kolonna_i_peregorodka', 'Колонна и перегородка заходят друг на друга (нахлёст тел)',
    [(p['at'][0], p['at'][1], f"{p['pair']}, нахлёст {round(p['overlap_pt2'] * K * K / 1e4)} см²") for p in pb if 'column' in p['pair'] and p['overlap_pt2'] > 0.005], 8)
made['торцы_стекла'] = sheet('02_tortsy_stekla_pod_uglom', 'Торец стекла касается стены не всей шириной (другой угол)',
    [(p['at'][0], p['at'][1], f"касание {round(100 * p['contact_share'])} % ширины" + (', нахлёст' if 'нахлёст' in p['what'] else '')) for p in pp if 'угол' in p['what']], 6, maxn=30)
Fj = json.load(open('furniture.json')) if os.path.exists('furniture.json') else {}
left = []
for k, o in enumerate(objs):
    if o['key'] in ('table', 'group', 'furn', 'chairpart', 'deskedge') and o['ids'] and 'draw' not in o:
        g = shapely.unary_union([geom(P[i]) for i in o['ids']]); c = g.centroid
        left.append((c.x, c.y, f"{o['key']}: {o['name'][:60]}"))
made['мебель_без_типа'] = sheet('03_mebel_bez_tipa', 'Мебель без типа — на перепроверку', left, 12)
made['места_незнакомого_размера'] = sheet('04_mesta_neznakomogo_razmera', 'Рабочие места незнакомого размера: достроены до типового или не растут',
    [(r['at'][0], r['at'][1], f"было {r['size_mm'][0]}×{r['size_mm'][1]} → {r.get('to_mm', ['—', '—'])[0]}×{r.get('to_mm', ['—', '—'])[1]}: {r['result']}") for r in Fj.get('places', {}).get('desks_unfamiliar_size', [])], 22)
C = json.load(open('core.json')) if os.path.exists('core.json') else {}
made['висящие_линии_ядра'] = sheet('05_visyashchie_linii_yadra', 'Ядро: линии контура, которые ничего не замыкают (висят)',
    [(h['at'][0], h['at'][1], f"длина {h['length_mm']} мм") for h in C.get('hanging', [])], 14)
DC = json.load(open('doors_check.json')) if os.path.exists('doors_check.json') else {}
DJ = json.load(open('doors.json')) if os.path.exists('doors.json') else {}
dits = [(b['hinge'][0], b['hinge'][1], f"{b['name']}: петля в {b['d_mm']} мм от стены") for b in DC.get('bad', [])]
dits += [(r['at'][0], r['at'][1], f"дверь не пересобрана: {r.get('why', '')}") for r in DJ.get('not_rebuilt', []) if isinstance(r, dict) and 'at' in r]
made['двери'] = sheet('06_dveri', 'Двери: петля дальше 150 мм от стены; двери, не пересобранные по схеме', dits, 14)
WC = json.load(open('walls_clean.json')) if os.path.exists('walls_clean.json') else {}
pl = WC.get('places', [])
fixed = [p for p in pl if p.get('fixed')]; kept = [p for p in pl if not p.get('fixed')]
made['неровности_выпрямлены'] = sheet('07_nerovnosti_vypryamleny', 'Неровности тоньше стены — выпрямлены (много на одной стороне или одна мелкая)',
    [(p['at'][0], p['at'][1], f"{p['why']}; {p['size_mm'][0]}×{p['size_mm'][1]} мм, стена {p['wall_t_mm']} мм") for p in fixed[::max(1, len(fixed) // 24)]], 6)
made['неровности_оставлены'] = sheet('08_nerovnosti_ostavleny', 'Неровности тоньше стены — оставлены (у элемента, ниша, на перепроверку)',
    [(p['at'][0], p['at'][1], f"{p['why']}; {p['size_mm'][0]}×{p['size_mm'][1]} мм") for p in kept], 6)
if CHK and os.path.exists(CHK):
    X = json.load(open(CHK))
    made['разрывы'] = sheet('09_razryvy_bez_dveri', 'Разрывы между стенами без двери, проёма и стекла (<= 3 pt ≈ 144 мм)',
        [(p['at'][0], p['at'][1], f"щель {p['gap_mm']} мм, {'–'.join(p['classes'])}") for p in X['walls']['breaks_without_door']['places']], 8)
    made['пустоты'] = sheet('10_pustoty_v_stenah', 'Пустоты внутри стен (дыры меньше 10 pt²)',
        [(p['at'][0], p['at'][1], f"{round(p['area_pt2'] * K * K / 100)} см²") for p in X['walls']['holes']['places'] if p['what'] == 'пустота в стене'], 5)
    sh = X['walls']['short_edges']['not_justified']
    made['ступеньки'] = sheet('11_stupenki_ne_opravdany', 'Короткие рёбра стены (< 0,8 толщины) без оправдания: ступеньки и прочее',
        [(p['at'][0], p['at'][1], f"{p['why']}: {p['length_mm']} мм, стена {p['wall_t_mm']} мм") for p in sh[::max(1, len(sh) // 24)]], 4)
json.dump({k: v for k, v in made.items() if v}, open(os.path.join(OUT, 'sheets.json'), 'w'), ensure_ascii=False, indent=1)
