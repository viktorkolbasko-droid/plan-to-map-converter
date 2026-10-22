"""Маска тела стены исходника из инженерного плана (DXF, мм) -> PNG в px исходника карты; рецепт по умолчанию — dxf3 (код карты v012).
python3 wall_mask_from_dxf.py plan.dxf M_t.npy 'a,b,tx,c,d,ty' W H out.png [--t-m 0.1] [--recipe dxf1|dxf2|dxf3]
  Решение владельца 14.10.2026 (ОЧ-25): Ч-10 карты по мосту из DXF — маска dxf3 по умолчанию; растр и скан — wm1 (unspot_map.wall_mask), как было.
  (M_t: мм -> px карты; a..ty: исходник -> px карты; W H — размер исходника, px)

Рецепт dxf2 (v009, пакет кода 3): слои — по коду элемента ISO 13567 (bridge_convert.iso/wall_role), а не по имени слоя одного
листа, — так маска строится и с плана листа AutoCAD (решение владельца 03.10.2026, строка 149):
  * тело (255): заливки SOLID стен 21… и 22x, колонны 28; стекло — заливки SOLID 22G и 31, линии и блоки 22G и 31 (как dxf1);
  * стена одной линией (линия слоя стен вне тела SOLID — ядро листа AutoCAD, строка 150) — полоса t_m по линии;
  * массив — узор материала стены (штриховка не SOLID), не покрытый телом SOLID: полоса t_m у грани — тело, глубже — зона массива
    (100), как рецепт wm1 unspot_map.wall_mask (Н23, Т4-1).
Рецепт dxf3 (v012, КМ-12; ОЧ-25, П3-6, Н-E3, В2К-6): классы — читателем моста 0.33 (XDATA UNSPOT type, без XDATA — код ISO): тело (255) — заливки
SOLID стен и колонн, колонны-блоки, стекло заливкой; стена одной линией и контур тела вне SOLID — полоса t_m; массив — узор стены без SOLID и тела
ядра (coreblock, coreline): полоса t_m у грани — тело, глубже — 100; витраж — тело между линиями facade и стойками mullion (замыкание 0,3 м);
стекло 22G линиями и лёгкие перегородки (lpart) — полоса t_m. Только из DXF плана, прошедшего шлюз, или эталона (map/rules/80, Ч-10).
Рецепт dxf1 (v008) — только SOLID-штриховки слоёв A-21/A-221/A-222/A-223 и стекло-блоки A-31, A-22G: на плане листа AutoCAD в нём нет
стекла заливкой и стен ядра линиями.
Рядом — <маска>.json: рецепт, SHA-256 значений маски и DXF; acceptance_checks.py пишет их в строку Ч-10 и в gate.json."""
import sys, os, json, hashlib, argparse, numpy as np, cv2, ezdxf
from ezdxf import path as ezpath
from shapely.geometry import Polygon
from shapely.strtree import STRtree
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bridge_convert import iso, wall_role, ent_paths

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument('dxf'); ap.add_argument('mt'); ap.add_argument('tf'); ap.add_argument('W', type=int); ap.add_argument('H', type=int); ap.add_argument('out')
ap.add_argument('--t-m', type=float, default=0.1, help='толщина тонкой стены, м: полоса стены одной линией и массива (dxf2)')
ap.add_argument('--recipe', default='dxf3', choices=('dxf1', 'dxf2', 'dxf3'), help='рецепт маски; по умолчанию dxf3 — решение владельца 14.10.2026 (ОЧ-25)')
a = ap.parse_args(); W, H = a.W, a.H
v = np.load(a.mt); M, t = v[:4].reshape(2, 2), v[4:]
A = np.linalg.inv(np.r_[np.array(list(map(float, a.tf.split(',')))).reshape(2, 3), [[0, 0, 1]]])
def src(P): X = np.asarray(P) @ M.T + t; return X @ A[:2, :2].T + A[:2, 2]
def q(P): return np.round(src(P) * 8).astype(np.int32)
msp = ezdxf.readfile(a.dxf).modelspace()
img = np.zeros((H, W), np.uint8); gl = np.zeros((H, W), np.uint8); n = m = nl = nmass = 0
px_per_mm = abs(np.linalg.det(M @ A[:2, :2])) ** 0.5
tpx = max(1, int(round(a.t_m * 1000 * px_per_mm)))
if a.recipe == 'dxf3':
    from bridge_convert import read_dxf, segs_of
    from shapely.geometry import MultiPoint
    D = read_dxf(a.dxf); img = np.zeros((H, W), np.uint8); gl = np.zeros((H, W), np.uint8); massif = np.zeros((H, W), np.uint8); fgi = np.zeros((H, W), np.uint8)
    for key in ('ext', 'int', 'col_h', 'glass_h'):
        for R in D[key]:
            Rq = [q(r) for r in R if len(r) >= 3]
            if Rq: cv2.fillPoly(img, Rq, 255, shift=3); n += 1
    for nm, segs, hr in D['col']:
        Q = np.vstack(hr) if hr else (np.vstack(segs) if segs else np.zeros((0, 2)))
        if len(Q) >= 3: cv2.fillPoly(img, [q(np.array(MultiPoint([tuple(p_) for p_ in Q]).convex_hull.exterior.coords))], 255, shift=3); n += 1
    sol = [Polygon(r).buffer(0) for key in ('ext', 'int') for R in D[key] for r in R if len(r) >= 3]; st = STRtree(sol) if sol else None
    rings = [r for wr, R in D['massif'] for r in R] + [r for R in D['core_h'] for r in R]
    for r in rings:                                                 # массив: узор стены без SOLID и тело ядра — полоса t_m у грани тело, глубже 100
        if len(r) < 3: continue
        g = Polygon(r).buffer(0)
        if g.is_empty or g.area <= 0: continue
        cov = sum(g.intersection(sol[int(j)].buffer(50)).area for j in st.query(g)) / g.area if st is not None else 0.0
        if cov > 0.5: continue
        mk = np.zeros((H, W), np.uint8); cv2.fillPoly(mk, [q(r)], 255, shift=3)
        er = cv2.erode(mk, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * tpx + 1, 2 * tpx + 1)))
        img[(mk > 0) & (er == 0)] = 255; massif[er > 0] = 100; nmass += 1
    covd = cv2.dilate(img, np.ones((5, 5), np.uint8))
    for wr, segs in D['wline']:                                     # стена одной линией и контур тела вне SOLID — полоса t_m
        for P in segs:
            S = src(P); X = np.round(S).astype(int); ok = (X[:, 0] >= 0) & (X[:, 1] >= 0) & (X[:, 0] < W) & (X[:, 1] < H)
            if not ok.any() or (covd[X[ok, 1], X[ok, 0]] > 0).mean() > 0.5: continue
            cv2.polylines(img, [np.round(S * 8).astype(np.int32)], False, 255, thickness=tpx, shift=3); nl += 1
    for nm, segs in D['fglass']:                                    # витраж: линии facade и стойки mullion -> тело замыканием 0,3 м
        for P in segs: cv2.polylines(fgi, [np.round(src(P) * 8).astype(np.int32)], False, 255, thickness=1, shift=3)
    for R in D['mullion']: cv2.fillPoly(fgi, [q(R)], 255, shift=3)
    for R in D['fglass_h']:
        for r in R:
            if len(r) >= 3: cv2.fillPoly(fgi, [q(r)], 255, shift=3)
    kf = max(3, int(round(0.3 * 1000 * px_per_mm)) | 1)
    fgi = cv2.morphologyEx(fgi, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (kf, kf))); img = np.maximum(img, fgi); m += 1
    for key in ('glass', 'light'):                                  # стекло 22G линиями и лёгкие перегородки — полоса t_m
        for it in D[key]:
            for P in segs_of(it): cv2.polylines(gl, [np.round(src(P) * 8).astype(np.int32)], False, 255, thickness=tpx, shift=3); m += 1
    how = ('рецепт dxf3 (v012, КМ-12): классы — читателем моста 0.33 (XDATA type, без XDATA — код ISO): заливки SOLID стен, колонн и стекла, колонны-блоки; '
           'стена одной линией (полоса t_m); массив и тело ядра (полоса t_m у грани — тело, глубже — 100); витраж — тело между facade и mullion '
           '(замыкание 0,3 м); стекло 22G и лёгкие перегородки линиями — полоса t_m (bridge/wall_mask_from_dxf.py)')
elif a.recipe == 'dxf1':
    WALLH = {'A-21----H-', 'A-221---H-', 'A-222---H-', 'A-223---H-'}
    for h in msp.query('HATCH'):
        if h.dxf.layer not in WALLH or h.dxf.pattern_name.upper() != 'SOLID': continue
        rings = [q(np.array([(p_.x, p_.y) for p_ in p.flattening(1.0)])) for p in ezpath.from_hatch(h)]
        rings = [r for r in rings if len(r) >= 3]
        if rings: cv2.fillPoly(img, rings, 255, shift=3); n += 1
    for ins in msp.query('INSERT'):
        if ins.dxf.layer not in ('A-31----E-', 'A-22G---E-'): continue
        for e in ins.virtual_entities():
            try: pp = ezpath.make_path(e)
            except Exception: continue
            P = np.array([(p_.x, p_.y) for p_ in pp.flattening(1.0)])
            if len(P) >= 2: cv2.polylines(gl, [q(P)], False, 255, thickness=3, shift=3); m += 1
    how = 'SOLID-штриховки слоёв стен A-21/A-221/A-222/A-223 и стекло A-31, A-22G инженерного плана (bridge/wall_mask_from_dxf.py)'
    massif = np.zeros((H, W), np.uint8)
else:
    sol, mas = [], []
    for h in msp.query('HATCH'):
        el, pr = iso(h.dxf.layer); wr = wall_role(el); solid = h.dxf.pattern_name.upper() == 'SOLID'
        R = [np.array([(p_.x, p_.y) for p_ in p.flattening(1.0)]) for p in ezpath.from_hatch(h)]; R = [r for r in R if len(r) >= 3]
        if not R: continue
        if (wr or el == '28') and solid:
            cv2.fillPoly(img, [q(r) for r in R], 255, shift=3); n += 1; sol += [Polygon(r).buffer(0) for r in R]
        elif wr: mas += R
        elif el in ('22G', '31') and solid: cv2.fillPoly(gl, [q(r) for r in R], 255, shift=3); m += 1
    st = STRtree(sol) if sol else None
    massif = np.zeros((H, W), np.uint8)
    for r in mas:                                                  # массив: не покрытый телом SOLID узор материала стены
        g = Polygon(r).buffer(0)
        if g.is_empty or g.area <= 0: continue
        cov = sum(g.intersection(sol[int(j)].buffer(50)).area for j in st.query(g)) / g.area if st is not None else 0.0
        if cov > 0.5: continue
        mk = np.zeros((H, W), np.uint8); cv2.fillPoly(mk, [q(r)], 255, shift=3)
        er = cv2.erode(mk, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * tpx + 1, 2 * tpx + 1)))
        img[(mk > 0) & (er == 0)] = 255; massif[er > 0] = 100; nmass += 1
    covd = cv2.dilate(img, np.ones((5, 5), np.uint8))
    for e in msp:                                                  # линии слоёв стен вне тела SOLID — стена одной линией; стекло 22G, 31 — линиями
        if e.dxftype() in ('HATCH', 'TEXT', 'MTEXT', 'DIMENSION'): continue
        el, pr = iso(e.dxf.layer)
        if pr == 'T': continue
        wr = wall_role(el)
        if not wr and el not in ('22G', '31'): continue
        for P in ent_paths(e):
            S = src(P)
            if wr:
                X = np.round(S).astype(int); ok = (X[:, 0] >= 0) & (X[:, 1] >= 0) & (X[:, 0] < W) & (X[:, 1] < H)
                if not ok.any() or (covd[X[ok, 1], X[ok, 0]] > 0).mean() > 0.5: continue
                cv2.polylines(img, [np.round(S * 8).astype(np.int32)], False, 255, thickness=tpx, shift=3); nl += 1
            else: cv2.polylines(gl, [np.round(S * 8).astype(np.int32)], False, 255, thickness=3, shift=3); m += 1
    how = ('рецепт dxf2 (v009): по коду элемента ISO 13567 — заливки SOLID стен 21…/22x и колонн 28, стена одной линией (полоса t_m), '
           'массив (узор стены без тела SOLID: полоса t_m у грани — тело, глубже — 100), стекло 22G и 31 заливкой и линиями (bridge/wall_mask_from_dxf.py)')
gl = cv2.morphologyEx(gl, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
both = np.maximum(img, gl); both[(both == 0) & (massif == 100)] = 100
cv2.imwrite(a.out, both)
sha = hashlib.sha256(f'{both.shape[1]}x{both.shape[0]}:'.encode() + both.astype(np.uint8).tobytes()).hexdigest()
json.dump(dict(recipe=a.recipe, how=how, size=[W, H], t_m=a.t_m if a.recipe in ('dxf2', 'dxf3') else None, mask_sha256=sha,
               dxf_sha256=hashlib.sha256(open(a.dxf, 'rb').read()).hexdigest(), source_transform=a.tf),
          open(os.path.splitext(a.out)[0] + '.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(f'рецепт {a.recipe}: тел стен {n}, массивов {nmass}, стен одной линией {nl}, стекла {m}; пикселей: тело {int((both == 255).sum())}, '
      f'массив {int((both == 100).sum())}; {W}×{H} -> {a.out}; SHA-256 значений {sha[:16]}…')
