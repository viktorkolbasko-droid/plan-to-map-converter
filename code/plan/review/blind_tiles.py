# Tiles for the independent check (plan/rules/60 §9, core/rules/30 §2) and for the blind A/B test of two runs
# (core/rules/30 §3). The building is cut into a grid (4 x 3 by default); for each tile:
#   one run   - tNN_src.png (the source) and tNN_map.png (classification map, colours of review/classmap.py):
#               the checker sees only these and counts the class errors per tile;
#   two runs  - tNN_src.png, tNN_A.png, tNN_B.png: the A/B order drawn at random per tile; the key goes to
#               out_dir/.k (base64 of reversed JSON), the evaluator is not told where it is.
# The grid covers the drawing: the bounds of every primitive of the plan (not sheet, axes, dimensions, tags) plus
# 0.5 m, inside cfg.WIN.
#   python3 review/blind_tiles.py RUN_DIR [RUN2_DIR] OUT_DIR [--grid=4x3] [--seed=20261003] [--zoom=4]
# Made from the test tool blind.py of the effort test (client A, floor 4, 03.10.2026; proposals п. 227), without its
# fixed paths and building box.
import sys, os, json, random, base64, subprocess, pickle
import pymupdf
from PIL import Image
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
args = [a for a in sys.argv[1:] if not a.startswith('--')]
opt = dict(a[2:].split('=', 1) for a in sys.argv[1:] if a.startswith('--') and '=' in a)
if len(args) == 2: R1, R2, OUT = args[0], None, args[1]
elif len(args) == 3: R1, R2, OUT = args
else: sys.exit(__doc__ or 'usage: blind_tiles.py RUN_DIR [RUN2_DIR] OUT_DIR [--grid=4x3] [--seed=N] [--zoom=Z]')
NC, NR = (int(v) for v in opt.get('grid', '4x3').split('x'))
SEED = int(opt.get('seed', 20261003)); Z = float(opt.get('zoom', 4.0))
sys.path.insert(0, HERE); os.chdir(R1)
from common import cfg, MM_PER_PT, load, pts
P = load(); cls = pickle.load(open('cls.pkl', 'rb'))
xs, ys = [], []
for i, p in enumerate(P):                               # everything drawn on the plan: walls, glazing, furniture
    if cls[i] in ('sheet', 'axis', 'dim', 'tag'): continue
    for x, y in pts(p): xs.append(x); ys.append(y)
m = 500 / MM_PER_PT; X0w, Y0w, X1w, Y1w = cfg.WIN
BX0, BY0 = max(X0w, min(xs) - m), max(Y0w, min(ys) - m); BX1, BY1 = min(X1w, max(xs) + m), min(Y1w, max(ys) + m)
pg = pymupdf.open(cfg.PDF)[0]
os.makedirs(OUT, exist_ok=True)
rnd = random.Random(SEED); key = {}
wx = (BX1 - BX0) / NC; wy = (BY1 - BY0) / NR
env = dict(os.environ, PYTHONPATH=HERE)
def cmap(run, pref, b):
    subprocess.run(['python3', os.path.join(HERE, 'review', 'classmap.py'), run, pref, str(Z), '1', '1'] + [str(v) for v in b],
                   check=True, env=env, cwd=run, capture_output=True)
n = 0
for r in range(NR):
    for c in range(NC):
        n += 1
        b = (BX0 + c * wx, BY0 + r * wy, BX0 + (c + 1) * wx, BY0 + (r + 1) * wy)
        pix = pg.get_pixmap(matrix=pymupdf.Matrix(Z, Z), clip=pymupdf.Rect(*b), alpha=False)
        Image.frombytes('RGB', (pix.width, pix.height), pix.samples).save(os.path.join(OUT, f't{n:02d}_src.png'))
        if R2 is None:
            cmap(os.path.abspath(R1), os.path.join(os.path.abspath(OUT), f't{n:02d}_map'), b)
            key[f't{n:02d}'] = dict(box=[round(v, 1) for v in b])
        else:
            order = [R1, R2]; rnd.shuffle(order)
            key[f't{n:02d}'] = dict(A='run1' if order[0] == R1 else 'run2', B='run1' if order[1] == R1 else 'run2', box=[round(v, 1) for v in b])
            for lab, d in zip('AB', order): cmap(os.path.abspath(d), os.path.join(os.path.abspath(OUT), f't{n:02d}_{lab}'), b)
        print(n, [round(v) for v in b])
if R2 is None: json.dump(key, open(os.path.join(OUT, 'tiles.json'), 'w'), ensure_ascii=False, indent=1)
else: open(os.path.join(OUT, '.k'), 'w').write(base64.b64encode(json.dumps(key)[::-1].encode()).decode())
print('tiles', n, 'grid', f'{NC}x{NR}', 'building box', [round(v, 1) for v in (BX0, BY0, BX1, BY1)], 'key written' if R2 else 'tiles.json')
