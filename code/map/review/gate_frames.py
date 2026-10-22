#!/usr/bin/env python3
"""Кадры шлюза (map/rules/80 §0, §3; Ф1, п. 2; «Д» п. 9): «исходник · карта · наложение» на каждое место look и fail
и на каждый объект списка кропов кодом. В имени кадра — первые 12 знаков SHA-256 SVG: шлюз (acceptance_checks.py --gate
--frames DIR) сверяет, что кадр снят с этого SVG, есть файл и место то же. Листы обзора — по 12 кадров.

    python3 acceptance_checks.py --svg plan.svg … --json acc.json            # приёмка: места look и fail, список кропов
    python3 review/gate_frames.py --report acc.json --svg plan.svg --source-png work.png --source-transform a,b,tx,c,d,ty \\
        --out frames/ [--verdicts-template v.json --crops-template c.json --accept-template acc_tpl.json] [--only Ч-11,К-12]

Карта — рендер самого SVG (cairosvg), а не PNG поставки: кадр обязан быть снят с проверяемого SVG. Исходник переводится во фрейм
карты матрицей --source-transform. Окно — 3 м вокруг места (`--window-m`), у объектов кропов — по группе (лестница 10 м, …).
Заготовки вердиктов — с именами кадров: автор пишет только «статус» и «вердикт». Код v007; v008 — К-03 и К-08 объектами (ПК1-К9);
v011 — у объекта с контуром (К-11 «модуль:N») контур стола синим поверх исходника и наложения (ПК4-К4)."""
import argparse, hashlib, io, json, math, os, re, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import acceptance_checks as ac                                            # имена кадров и ключи мест — те же, что сверяет шлюз

WIN = {'К-01': 10.0, 'К-02': 6.0, 'К-03': 6.0, 'К-06': 8.0, 'К-07': 3.0, 'К-08': 5.0, 'К-11': 5.0, 'К-12': 8.0}   # окно объекта кропа, м; v008: К-03, К-08 — объектами
PANEL = 300
def font(sz):
    for f in ('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', '/usr/share/fonts/dejavu/DejaVuSans.ttf', 'DejaVuSans.ttf'):
        try: return ImageFont.truetype(f, sz)
        except OSError: pass
    try: return ImageFont.load_default(size=sz)
    except TypeError: return ImageFont.load_default()

class Scene:
    """карта (рендер SVG) и исходник во фрейме карты"""
    def __init__(s, svg, source_png=None, transform=None, scale=None):
        import cairosvg
        s.svg = svg; s.h = hashlib.sha256(open(svg, 'rb').read()).hexdigest()
        txt = open(svg, encoding='utf-8', errors='replace').read(); vb = [float(v) for v in re.findall(ac.NUM, re.search(r'viewBox="([^"]*)"', txt)[1])]
        s.W, s.H = int(round(vb[2])), int(round(vb[3])); s.vb = vb
        png = cairosvg.svg2png(bytestring=txt.encode('utf-8'), output_width=s.W, output_height=s.H, background_color='white')
        s.map = np.asarray(Image.open(io.BytesIO(png)).convert('RGB'))
        s.src = None; s.m = scale or 50.0
        if source_png and transform:
            import cv2
            a, b, tx, c, d, ty = [float(v) for v in transform.split(',')]
            im = np.asarray(Image.open(source_png).convert('RGB'))
            M = np.array([[a, b, tx - vb[0]], [c, d, ty - vb[1]]], float)          # исходник -> px фрейма
            s.src = cv2.warpAffine(im, M, (s.W, s.H), flags=cv2.INTER_AREA if abs(a * d - b * c) < 1 else cv2.INTER_LINEAR, borderValue=(255, 255, 255))
    def crop(s, img, x, y, half):
        x0, y0 = int(round(x - half)), int(round(y - half)); n = int(round(2 * half))
        out = np.full((n, n, 3), 255, np.uint8)
        X0, Y0, X1, Y1 = max(0, x0), max(0, y0), min(s.W, x0 + n), min(s.H, y0 + n)
        if X1 > X0 and Y1 > Y0: out[Y0 - y0:Y1 - y0, X0 - x0:X1 - x0] = img[Y0:Y1, X0:X1]
        return out
    def frame(s, x, y, half, title, note='', poly=None):
        """три панели одного окна: исходник · карта · наложение (исходник серым × карта); метка места — красный круг;
        v011 (ПК4-К4): poly — контур объекта (стол места «модуль:N») синим поверх исходника и наложения"""
        mp = s.crop(s.map, x, y, half)
        sr = s.crop(s.src, x, y, half) if s.src is not None else np.full_like(mp, 235)
        g = sr.mean(2, keepdims=True); ov = (mp.astype(float) * (0.35 + 0.65 * g / 255.0)).astype(np.uint8)
        k = PANEL / mp.shape[0]
        tiles = [Image.fromarray(t).resize((PANEL, PANEL), Image.LANCZOS if k < 1 else Image.NEAREST) for t in (sr, mp, ov)]
        top = 44; im = Image.new('RGB', (3 * PANEL + 4 * 6, PANEL + top + 6), (255, 255, 255)); d = ImageDraw.Draw(im)
        for i, t in enumerate(tiles):
            im.paste(t, (6 + i * (PANEL + 6), top)); c = (6 + i * (PANEL + 6) + PANEL / 2, top + PANEL / 2); r = max(6, 0.25 * s.m * k)
            if poly and i in (0, 2):
                x0_, y0_ = int(round(x - half)), int(round(y - half)); q_ = [(6 + i * (PANEL + 6) + (px - x0_) * k, top + (py - y0_) * k) for px, py in poly]
                d.line(q_ + q_[:1], fill=(0, 70, 255), width=2)
                continue
            d.ellipse([c[0] - r, c[1] - r, c[0] + r, c[1] + r], outline=(230, 0, 0), width=2)
        f1, f2 = font(14), font(12)
        d.text((6, 3), f'{title} · ({x:.0f}, {y:.0f}) · окно {2 * half / s.m:.1f} м · SVG {s.h[:12]}', fill=(0, 0, 0), font=f1)
        d.text((6, 22), (note or '')[:150] + '   [исходник · карта · наложение]', fill=(90, 90, 90), font=f2)
        return im

def sheets(items, out, h, gid, per=12, cols=3):
    """листы обзора: по 12 кадров, 3 в ряд"""
    names = []
    for k in range(0, len(items), per):
        part = items[k:k + per]; ims = [Image.open(p) for p in part]; w = max(i.size[0] for i in ims) // 2; hh = max(i.size[1] for i in ims) // 2
        rows = math.ceil(len(ims) / cols); sh = Image.new('RGB', (cols * w, rows * hh), (255, 255, 255))
        for j, i in enumerate(ims): sh.paste(i.resize((w, hh), Image.LANCZOS), ((j % cols) * w, (j // cols) * hh))
        nm = os.path.join(out, f'{h[:12]}__лист__{gid}__{k // per + 1:02d}.png'); sh.save(nm, optimize=True); names.append(nm)
    return names

def main():
    ap = argparse.ArgumentParser(description='Кадры шлюза: исходник · карта · наложение — на каждое место look и fail и каждый объект кропов')
    ap.add_argument('--report', required=True, help='JSON приёмки (acceptance_checks.py --json) этого SVG')
    ap.add_argument('--svg', required=True); ap.add_argument('--source-png'); ap.add_argument('--source-transform'); ap.add_argument('--out', required=True)
    ap.add_argument('--window-m', type=float, default=3.0, help='окно места look и fail, м'); ap.add_argument('--only', default='', help='только эти Ч-NN и К-NN через запятую')
    ap.add_argument('--verdicts-template'); ap.add_argument('--crops-template'); ap.add_argument('--accept-template')
    ap.add_argument('--no-sheets', action='store_true')
    a = ap.parse_args(); R = json.load(open(a.report, encoding='utf-8'))
    S = Scene(a.svg, a.source_png, a.source_transform or (','.join(map(str, R['params']['source_transform'])) if R['params'].get('source_transform') else None),
              R['params'].get('scale_px_per_m') or 6 * R['params'].get('wall_t_px', 6))
    if R.get('svg_sha256') and R['svg_sha256'] != S.h: sys.exit(f'отчёт {a.report} — от другого SVG ({R["svg_sha256"][:12]} ≠ {S.h[:12]}): кадры не строятся')
    os.makedirs(a.out, exist_ok=True); only = {x.strip() for x in a.only.split(',') if x.strip()}
    made, VT, CT, AT = {}, {'svg_sha256': S.h}, {'svg_sha256': S.h}, {'svg_sha256': S.h}
    for c in R['checks']:
        if c['status'] not in ('look', 'fail') or (only and c['id'] not in only): continue
        W = c.get('where_all') or c.get('where') or []; lst = []
        for j, w in enumerate(W):
            if w.get('x') is None: lst.append(dict(note=w.get('note'), статус='', вердикт='')); continue
            nm = ac.frame_name(S.h, c['id'], ac.place_key(j, w)); p = os.path.join(a.out, nm)
            S.frame(w['x'], w['y'], a.window_m * S.m / 2, f'{c["id"]} {c["status"]} · место {j + 1} из {len(W)}', w.get('note', '')).save(p, optimize=True)
            made.setdefault(c['id'], []).append(p); lst.append(dict(x=w['x'], y=w['y'], note=w.get('note', ''), кадр=nm, статус='', вердикт=''))
        if c['status'] == 'look': VT[c['id']] = lst or [dict(место='весь план', статус='', вердикт='')]
        else: AT[c['id']] = dict(max=len(W), by='', why=dict(kind='', ref='', text=''))
    for g, obs in (R.get('crop_list') or {}).items():
        if only and g not in only: continue
        if g not in ac.OBJ_GROUPS: continue
        CT[g] = {}
        for o in obs:
            nm = ac.frame_name(S.h, g, o['id']); p = os.path.join(a.out, nm)
            half = (max(S.W, S.H) / 2 if o['id'] == 'цвет' else WIN.get(g, 5.0) * S.m / 2)
            S.frame(o['x'], o['y'], half, f'{g} · {o["id"]}', o.get('what', ''), o.get('poly')).save(p, optimize=True)
            made.setdefault(g, []).append(p); CT[g][o['id']] = dict(кадр=nm, статус='', вердикт='')
    for g in (f'К-{j:02d}' for j in range(1, 13)):
        if g not in ac.BY_LOOK and g not in CT and not (only and g not in only): CT[g] = dict(статус='', вердикт='')
    sh = [] if a.no_sheets else [p for g, ps in made.items() for p in sheets(ps, a.out, S.h, g)]
    for f, D in ((a.verdicts_template, VT), (a.crops_template, CT), (a.accept_template, AT)):
        if f: json.dump(D, open(f, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(json.dumps(dict(svg_sha256=S.h, frames={g: len(v) for g, v in made.items()}, sheets=len(sh), out=os.path.abspath(a.out)), ensure_ascii=False))

if __name__ == '__main__': main()
