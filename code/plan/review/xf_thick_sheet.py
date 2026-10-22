# Owner's list of the places where one floor's source draws only thick lines (no hatch) where the other floor has a
#   capital wall (29.09.2026, plan/rules/60 §11, rule 100: >= 0.8 m2 goes to the owner as a list with pictures, not accepted
#   silently). The cells of crossfloor.json with that verdict are merged per pair and side (<= 1.6 m apart); each place
#   >= MIN m2 gets a tile: both floors' sources side by side at the place, with their walls (xf_pair_view.py).
# (30.09.2026) the verdict "thick lines only" is gone (owner: glazing inside the office, plan/rules/60 §11); the sheet is now
#   for any verdict by its beginning, VERDICT (default "missed": every place of it is looked at on pictures - a missed
#   wall is fixed, a false one is a fault of the check, canon-proposals 130)
# Usage (in the crossfloor folder with the floor links): python3 xf_thick_sheet.py crossfloor.json out_prefix [MIN=0.8] [K=8] [VERDICT=missed]
#   Out: out_prefix_list.json and sheets out_prefix_1.png, _2.png ... of K tiles.
import sys, json, os, subprocess, math, collections
from PIL import Image, ImageDraw, ImageFont
J = json.load(open(sys.argv[1])); pref = sys.argv[2]; MIN = float(sys.argv[3]) if len(sys.argv) > 3 else 0.8
K = int(sys.argv[4]) if len(sys.argv) > 4 else 8
VERDICT = sys.argv[5] if len(sys.argv) > 5 else 'missed'
TITLE = {'missed': 'пропущено: штриховка есть', 'same wall on': 'та же стена со сдвигом', 'glazing on': 'остекление вместо стены', 'layouts differ': 'другая планировка'}.get(VERDICT, VERDICT)
HERE = os.path.dirname(os.path.abspath(__file__))
rows = []
for key, pr in J['pairs'].items():
    A, B = key.split('-', 1)
    cells = [d for d in pr.get('cap_differences', []) if d.get('verdict', '').startswith(VERDICT)]
    for side in set(d['side'] for d in cells):
        cs = [d for d in cells if d['side'] == side]
        par = list(range(len(cs)))
        def f(a):
            while par[a] != a: par[a] = par[par[a]]; a = par[a]
            return a
        for i in range(len(cs)):
            for j in range(i + 1, len(cs)):
                if math.dist(cs[i]['at_mm'], cs[j]['at_mm']) <= 1600: par[f(j)] = f(i)
        grp = collections.defaultdict(list)
        for i in range(len(cs)): grp[f(i)].append(cs[i])
        for g in grp.values():
            m2 = sum(d['area_m2'] for d in g)
            if m2 < MIN: continue
            w = [d['area_m2'] for d in g]; x = sum(d['at_mm'][0] * a for d, a in zip(g, w)) / sum(w); y = sum(d['at_mm'][1] * a for d, a in zip(g, w)) / sum(w)
            hatch = max(d.get('hatch_per_m', 0) for d in g)
            rows.append(dict(pair=key, a=A, b=B, wall_on=side.replace('only_', ''), m2=round(m2, 2), at_mm=[round(x), round(y)],
                             cells=len(g), hatch_per_m_max=hatch))
rows.sort(key=lambda r: -r['m2'])
json.dump(rows, open(pref + '_list.json', 'w'), ensure_ascii=False, indent=0)
print(len(rows), 'places >=', MIN, 'm2')
f = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 16); fs = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 13)
tiles = []
for k, r in enumerate(rows):
    tmp = f'{pref}_tile_{k:02d}.png'
    subprocess.run([sys.executable, os.path.join(HERE, 'xf_pair_view.py'), sys.argv[1], r['a'], r['b'], str(r['at_mm'][0]), str(r['at_mm'][1]), '3000', tmp],
                   check=True, capture_output=True)
    im = Image.open(tmp); im = im.resize((im.width // 2, im.height // 2))
    other = r['b'] if r['wall_on'] == r['a'] else r['a']
    t = Image.new('RGB', (im.width, im.height + 44), 'white'); d = ImageDraw.Draw(t); t.paste(im, (0, 44))
    d.text((6, 3), f"{k + 1}. {r['pair']}: стена на {r['wall_on']}, на {other} — {TITLE}, {r['m2']} м²", fill=(0, 0, 0), font=f)
    d.text((6, 24), f"место в кадре пары {r['at_mm']} мм; клеток {r['cells']}; штриховка на {other} до {r['hatch_per_m_max']} штр./м", fill=(80, 80, 80), font=fs)
    tiles.append(t); os.remove(tmp)
for s in range(0, len(tiles), K):
    part = tiles[s:s + K]; W = max(t.width for t in part); H = sum(t.height + 8 for t in part)
    sh = Image.new('RGB', (W, H), (235, 235, 235)); y = 0
    for t in part: sh.paste(t, (0, y)); y += t.height + 8
    out = f'{pref}_{s // K + 1}.png'; sh.save(out); print(out, sh.size)
