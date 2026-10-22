#!/usr/bin/env python3
"""Контактный лист мест look одной проверки (map/rules/80 §3; ОВ22): «исходник | карта» всех мест проверки на одном листе,
под каждым — номер места, координаты и вердикт из --verdicts. Устаревший вердикт виден одним взглядом. Смотреть перед шлюзом.

    python3 review/contact_sheet.py --report acc.json --check Ч-11 --svg plan.svg --source-png work.png \\
        --source-transform a,b,tx,c,d,ty [--verdicts verdicts.json] --out Ч-11_контакт.png [--window-m 3 --cols 6]
Код v007."""
import argparse, json, math, os, sys
import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gate_frames import Scene, font                                     # тот же рендер SVG и тот же исходник во фрейме, что у кадров шлюза

def main():
    ap = argparse.ArgumentParser(description='Контактный лист мест look одной проверки: исходник | карта')
    ap.add_argument('--report', required=True); ap.add_argument('--check', required=True); ap.add_argument('--svg', required=True)
    ap.add_argument('--source-png'); ap.add_argument('--source-transform'); ap.add_argument('--verdicts'); ap.add_argument('--out', required=True)
    ap.add_argument('--window-m', type=float, default=3.0); ap.add_argument('--cols', type=int, default=6); ap.add_argument('--tile', type=int, default=150)
    ap.add_argument('--match', help='только места, чей вердикт подходит под это выражение (например «не исправлен|в находки|ДЕМО»)')
    ap.add_argument('--no-verdict', action='store_true', help='только места без вердикта')
    ap.add_argument('--note', help='только места, чья запись проверки подходит под это выражение (например «по линии листа»)')
    ap.add_argument('--first', type=int, default=0, help='не больше N мест')
    a = ap.parse_args(); R = json.load(open(a.report, encoding='utf-8'))
    c = next((x for x in R['checks'] if x['id'] == a.check), None)
    if c is None: sys.exit(f'{a.check}: нет в отчёте')
    W = [w for w in (c.get('where_all') or c.get('where') or []) if w.get('x') is not None]
    if not W: sys.exit(f'{a.check}: мест с координатами нет — лист не нужен')
    tf = a.source_transform or (','.join(map(str, R['params']['source_transform'])) if R['params'].get('source_transform') else None)
    S = Scene(a.svg, a.source_png, tf, R['params'].get('scale_px_per_m'))
    if R.get('svg_sha256') and R['svg_sha256'] != S.h: sys.exit(f'отчёт — от другого SVG ({R["svg_sha256"][:12]} ≠ {S.h[:12]})')
    V = []
    if a.verdicts:
        D = json.load(open(a.verdicts, encoding='utf-8')); v = D.get(a.check)
        if isinstance(v, str): v = json.load(open(os.path.join(os.path.dirname(os.path.abspath(a.verdicts)), v), encoding='utf-8'))
        if isinstance(v, dict): v = v.get('куски') or v.get('places') or v.get('verdicts') or []
        V = [e for e in v or [] if isinstance(e, dict) and isinstance(e.get('x'), (int, float))]
    import re
    def ver(w):
        e = min(V, key=lambda e: math.hypot(e['x'] - w['x'], e['y'] - w['y']), default=None)
        return e if e is not None and math.hypot(e['x'] - w['x'], e['y'] - w['y']) <= 3 else None
    if a.match: W = [w for w in W if ver(w) is not None and re.search(a.match, str(ver(w).get('вердикт') or ver(w).get('verdict') or ''), re.I)]
    if a.no_verdict: W = [w for w in W if ver(w) is None]
    if a.note: W = [w for w in W if re.search(a.note, str(w.get('note', '')), re.I)]
    if a.first: W = W[:a.first]
    if not W: sys.exit(f'{a.check}: под отбор мест нет')
    t, cols, half = a.tile, a.cols, a.window_m * S.m / 2; cap = 46
    rows = math.ceil(len(W) / cols); tw = 2 * t + 4
    sh = Image.new('RGB', (cols * (tw + 8) + 8, 30 + rows * (t + cap + 8)), (255, 255, 255)); d = ImageDraw.Draw(sh); f1, f2 = font(13), font(10)
    d.text((8, 6), f'{a.check} {c["status"]} — мест {len(W)}; SVG {S.h[:12]}; исходник | карта, окно {a.window_m:g} м', fill=(0, 0, 0), font=f1)
    nv = 0
    for j, w in enumerate(W):
        x0, y0 = 8 + (j % cols) * (tw + 8), 30 + (j // cols) * (t + cap + 8)
        for k, img in enumerate((S.src, S.map)):
            cr = S.crop(img, w['x'], w['y'], half) if img is not None else np.full((t, t, 3), 235, np.uint8)
            sh.paste(Image.fromarray(cr).resize((t, t), Image.LANCZOS), (x0 + k * (t + 4), y0))
            cx, cy = x0 + k * (t + 4) + t / 2, y0 + t / 2; d.ellipse([cx - 5, cy - 5, cx + 5, cy + 5], outline=(230, 0, 0), width=2)
        e = ver(w); nv += e is not None
        vt = (str(e.get('статус') or '') + ' ' + str(e.get('вердикт') or e.get('verdict') or '')).strip() if e else 'вердикта нет'
        d.text((x0, y0 + t + 2), f'{j + 1}. ({w["x"]:.0f}, {w["y"]:.0f}) {str(w.get("note", ""))[:34]}', fill=(60, 60, 60), font=f2)
        for r in range(2): d.text((x0, y0 + t + 15 + 12 * r), vt[r * 48:(r + 1) * 48], fill=(0, 0, 160) if e else (200, 0, 0), font=f2)
    sh.save(a.out, optimize=True); print(json.dumps(dict(check=a.check, places=len(W), with_verdict=nv, out=os.path.abspath(a.out)), ensure_ascii=False))

if __name__ == '__main__': main()
