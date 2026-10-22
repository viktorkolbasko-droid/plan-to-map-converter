"""Тест PNG для UnSpot v012, правка v013 (К13.2; строка 390, №6; map/rules/82 §1, 80 Ч-28): svg_map.to_png(svg, png, scale=None, size=None) и <png>.export.json.
Новая карта: множитель = 4 000 / большая сторона холста, и вверх, и вниз: холст 1 200 px -> 4 000 px (×3,33); 4 596 px -> 4 000 px (×0,870);
6 000 × 8 000 -> 3 000 × 4 000 (×0,5); 12 000 px -> 4 000 px; меньше 1× — без предупреждения (⛔ 15.10.2026: «не меньше 1×» и предел 10 000 px сняты).
Явный множитель больше 4 000 px — «ВНИМАНИЕ».
Правка: size=(W, H) прежней выгрузки — до пикселя; вызов v011 to_png(svg, png, (W, H)) — то же. export.json — ключи контракта PLANMAP §2.2.
ПК6-К4 (б): size другой пропорции (> 2 px) — «ВНИМАНИЕ» в выводе и "warnings" в export.json.
Запуск из любой папки: python3 tests/test_png_v012.py — код 0, если всё совпало."""
import json, os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from PIL import Image
from unspot_map.svg_map import to_png, export_scale
bad = []
def check(name, got, want):
    ok = got == want; print(('ok   ' if ok else 'FAIL ') + name + ('' if ok else f': {got!r} != {want!r}')); ok or bad.append(name)


def svg(path, W, H):
    open(path, 'w').write(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}"><rect x="0" y="0" width="{W}" height="{H}" fill="#FFFFFF"/>'
                          f'<rect x="{W * 0.1}" y="{H * 0.1}" width="{W * 0.8}" height="{H * 0.8}" fill="#EBF5FF" stroke="#CBD2D6" stroke-width="6"/></svg>')


with tempfile.TemporaryDirectory() as td:
    s = os.path.join(td, 'a.svg'); svg(s, 1200, 800); p = os.path.join(td, 'a.png'); r = to_png(s, p)
    check('новая карта: холст 1 200 × 800 -> 4 000 × 2 667, ×3,333', (Image.open(p).size, r['scale'], r['mode']), ((4000, 2667), 3.3333, 'new'))
    e = json.load(open(p + '.export.json'))
    check('export.json: ключи контракта', sorted(k for k in e if k != 'bytes'), sorted(['png', 'w', 'h', 'scale', 'canvas', 'mode', 'prev_size']))
    check('export.json: значения', (e['png'], e['w'], e['h'], e['canvas'], e['prev_size']), ('a.png', 4000, 2667, [1200, 800], None))
    s = os.path.join(td, 'b.svg'); svg(s, 4596, 4585); p = os.path.join(td, 'b.png'); r = to_png(s, p)
    check('новая карта: холст 4 596 × 4 585 -> ×0,870, 4 000 × 3 990 (меньше 1× допустим)', (Image.open(p).size, r['scale'], 'warnings' in r), ((4000, 3990), 0.8703, False))
    s = os.path.join(td, 'c.svg'); svg(s, 12000, 600); p = os.path.join(td, 'c.png'); r = to_png(s, p)
    check('новая карта: холст 12 000 × 600 -> 4 000 × 200 (меньше 1×)', (Image.open(p).size, r['scale'] < 1), ((4000, 200), True))
    s = os.path.join(td, 'c2.svg'); svg(s, 6000, 8000); p = os.path.join(td, 'c2.png'); r = to_png(s, p)
    check('новая карта: холст 6 000 × 8 000 -> ×0,5, 3 000 × 4 000', (Image.open(p).size, r['scale']), ((3000, 4000), 0.5))
    s = os.path.join(td, 'd.svg'); svg(s, 1200, 800); p = os.path.join(td, 'd.png'); r = to_png(s, p, size=(3600, 2400))
    check('правка: size=(3 600, 2 400) — до пикселя, mode edit, prev_size', (Image.open(p).size, r['mode'], r['prev_size']), ((3600, 2400), 'edit', [3600, 2400]))
    p = os.path.join(td, 'e.png'); r = to_png(s, p, size=(3601, 2399))
    check('правка: нечётный размер 3 601 × 2 399 — до пикселя', Image.open(p).size, (3601, 2399))
    p = os.path.join(td, 'f.png'); to_png(s, p, (1234, 823))
    check('вызов v011 to_png(svg, png, (W, H)) — как size', Image.open(p).size, (1234, 823))
    p = os.path.join(td, 'g.png'); r = to_png(s, p, scale=2)
    check('явный множитель scale=2: 2 400 × 1 600', (Image.open(p).size, r['mode']), ((2400, 1600), 'new'))
    import io, contextlib
    def loud(*a_, **k_):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf): r_ = to_png(*a_, **k_)
        return r_, buf.getvalue()
    s = os.path.join(td, 'h.svg'); svg(s, 20000, 8000); p = os.path.join(td, 'h.png'); r, out = loud(s, p)
    check('холст 20 000 × 8 000 -> ×0,2, 4 000 × 1 600, без «ВНИМАНИЕ» и без warnings (меньше 1× допустим, строка 390)',
          (Image.open(p).size, r['scale'], 'ВНИМАНИЕ' in out, 'warnings' in json.load(open(p + '.export.json'))), ((4000, 1600), 0.2, False, False))
    s = os.path.join(td, 'j.svg'); svg(s, 1200, 800); p = os.path.join(td, 'j.png'); r, out = loud(s, p, scale=4)
    check('явный множитель ×4 -> 4 800 × 3 200: больше 4 000 px — «ВНИМАНИЕ» и warnings', (Image.open(p).size, 'ВНИМАНИЕ — явный множитель' in out,
          any('больше 4000 px' in w for w in r.get('warnings', []))), ((4800, 3200), True, True))
    s = os.path.join(td, 'k.svg'); svg(s, 4596, 4585); p = os.path.join(td, 'k.png'); r, out = loud(s, p, size=(3600, 2400))
    check('ПК6-К4 (б): size другой пропорции (3 600 × 2 400 при холсте 4 596 × 4 585) — «ВНИМАНИЕ — пропорции», размер — до пикселя',
          (Image.open(p).size, 'ВНИМАНИЕ — пропорции' in out, bool(r.get('warnings'))), ((3600, 2400), True, True))
    p = os.path.join(td, 'm.png'); r, out = loud(s, p, size=(4596, 4585))
    check('ПК6-К4: size своей пропорции — без предупреждений, ключа warnings нет', ('ВНИМАНИЕ' in out, 'warnings' in r), (False, False))
    check('export_scale: 3 000 -> 1,333; 3 500 × 4 600 -> 0,870; 9 000 -> 0,444; 20 000 -> 0,2',
          (round(export_scale((3000, 2000)), 3), round(export_scale((3500, 4600)), 3), round(export_scale((9000, 100)), 3), export_scale((20000, 100))), (1.333, 0.87, 0.444, 0.2))
print('итог:', 'всё совпало' if not bad else f'расхождений {len(bad)}'); sys.exit(1 if bad else 0)
