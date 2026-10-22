"""Тест глифов бейджей v013 (ОЧ-167; строка 412 ref/map/11; map/kit/70, п. 3-4): unspot_map/glyphs.py — BADGES, badge_svg, scale_path.
Без внешних данных. `dinner` — «вилка и нож» из пина points 21:36 (глиф 21:41, вектор 21:42) файла «Client Maps by Claude»:
  исходный путь выгрузки Figma (24 x 24, без сдвига) вшит сюда; глиф бейджа = он же со сдвигом (3; 3), цвет #62677A;
  кружок #E1E7EB r 15; нет transform; все точки глифа — внутри кружка; масштаб d = 60 — ровно 2x; id 21:41 — в GLYPH_KIND приёмки; `food` — чашка map/kit/70.
    python3 tests/test_glyphs_v013.py        -> «ok N из N» и код 0"""
import io, os, re, sys, traceback
HERE = os.path.dirname(os.path.abspath(__file__)); CODE = os.path.dirname(HERE)
sys.path.insert(0, CODE)
import numpy as np, cairosvg
from PIL import Image
from unspot_map import glyphs as G

FIGMA_D = "M18.3 3.99847V19.9985C18.3 20.4405 17.942 20.7985 17.5 20.7985C17.058 20.7985 16.7 20.4405 16.7 19.9985V11.5985H14.3C13.858 11.5985 13.5 11.2405 13.5 10.7985V7.19847C13.5 6.25847 13.737 5.50047 14.134 4.90447C14.528 4.31447 15.047 3.93047 15.542 3.68347C16.124 3.39247 16.786 3.22147 17.437 3.19947C17.891 3.18447 18.3 3.52847 18.3 3.99847ZM16.7 4.93947C15.641 5.26347 15.1 6.11447 15.1 7.19847V9.99847H16.7V4.93947ZM7.901 3.69847C8.343 3.69847 8.701 4.05647 8.701 4.49847V8.86347C9.123 8.94247 9.503 8.91847 9.503 8.39747V4.39747C9.503 3.95547 9.861 3.59747 10.303 3.59747C10.745 3.59747 11.103 3.95547 11.103 4.39747V8.39747C11.103 9.05447 10.909 9.61447 10.483 10.0035C10.076 10.3755 9.576 10.4805 9.188 10.4975C9.019 10.5045 8.855 10.4965 8.701 10.4795V19.9985C8.701 20.4405 8.343 20.7985 7.901 20.7985C7.46 20.7985 7.101 20.4405 7.101 19.9985V10.4915C6.979 10.4995 6.851 10.5025 6.721 10.4975C6.32 10.4815 5.804 10.3825 5.379 10.0255C4.923 9.64247 4.703 9.07547 4.703 8.39747V4.39747C4.703 3.95547 5.061 3.59747 5.503 3.59747C5.945 3.59747 6.303 3.95547 6.303 4.39747V8.39747C6.303 8.90247 6.66 8.93547 7.101 8.88547V4.49847C7.101 4.05647 7.46 3.69847 7.901 3.69847Z"            # путь `Vector` узла 21:42 из выгрузки Figma MCP 16.10.2026, 24 x 24, как есть

def raster(svg, w, h, S=8):
    png = cairosvg.svg2png(bytestring=svg.encode('utf-8'), output_width=int(w * S), output_height=int(h * S), background_color='white')
    return np.asarray(Image.open(io.BytesIO(png)).convert('RGB')).astype(int)

def t_dinner_same_as_figma_shifted():
    ref = ('<svg xmlns="http://www.w3.org/2000/svg" width="30" height="30" viewBox="0 0 30 30"><g transform="translate(3 3)">'
           '<path fill-rule="evenodd" clip-rule="evenodd" d="' + FIGMA_D + '" fill="#62677A"/></g></svg>')
    mine = '<svg xmlns="http://www.w3.org/2000/svg" width="30" height="30" viewBox="0 0 30 30">' + G.glyph_svg('dinner') + '</svg>'
    a, b = raster(ref, 30, 30), raster(mine, 30, 30)
    diff = np.abs(a - b).max(axis=2); n = int((diff > 40).sum())
    assert n <= 8, ('пикселей с расхождением > 40 при 8x: %d' % n)         # округление 0,01 px = 0,08 px при 8x
    assert (a != 255).any(), 'пусто'

def t_badge_structure():
    s = G.badge_svg('dinner')
    assert s.startswith('<g data-badge="dinner" data-figma="21:41"><circle cx="15" cy="15" r="15" fill="#E1E7EB"/>'), s[:120]
    assert 'transform' not in s and s.count('<path') == 1 and s.count('#62677A') == 1 and 'fill="#FFFFFF"' not in s.upper()
    assert set(re.findall(r'[A-Za-z]', G.BADGES['dinner'].split(' d="')[1].split('"')[0])) <= set('MLHVCZ')

def t_glyph_inside_circle():
    svg = '<svg xmlns="http://www.w3.org/2000/svg" width="30" height="30" viewBox="0 0 30 30">' + G.glyph_svg('dinner') + '</svg>'
    S = 8; m = (raster(svg, 30, 30, S) != 255).any(axis=2); ys, xs = np.where(m)
    r = np.hypot((xs + 0.5) / S - 15, (ys + 0.5) / S - 15).max()
    assert r < 15 - 3, r                                                         # поле от кромки кружка не меньше 3 px (глиф 24 x 24 с полем 3)
    assert xs.min() / S > 3 and ys.min() / S > 3 and (xs.max() + 1) / S < 27 and (ys.max() + 1) / S < 27

def t_scale_2x():
    one = raster('<svg xmlns="http://www.w3.org/2000/svg" width="30" height="30" viewBox="0 0 30 30">' + G.badge_svg('dinner') + '</svg>', 30, 30, 8)
    two = raster('<svg xmlns="http://www.w3.org/2000/svg" width="60" height="60" viewBox="0 0 60 60">' + G.badge_svg('dinner', 30, 30, 60) + '</svg>', 60, 60, 4)
    assert one.shape == two.shape, (one.shape, two.shape)
    n = int((np.abs(one - two).max(axis=2) > 40).sum()); assert n <= 400, n      # те же 480 x 480 px; разница — только сглаживание кромки

def t_offset():
    s = G.badge_svg('dinner', 100, 50, 30)
    assert '<circle cx="100" cy="50" r="15"' in s and 'd="M106.3 42V58C' in s, s[:200]   # сдвиг (85; 35): M21.3 7 -> M106.3 42

def t_scale_path_loud():
    try: G.scale_path('M0 0A5 5 0 0 1 10 10'); raise AssertionError('A принята молча')
    except ValueError: pass

def t_food_kept_and_kind_registered():
    assert G.BADGES['food'].count('<path') == 5 and G.FIGMA['food'] == '2904:12722'
    src = open(os.path.join(CODE, 'acceptance_checks.py'), encoding='utf-8').read()
    assert "'21:41': 'dinner'" in src and "'2904:12722': 'kitchen'" in src

T = [t_dinner_same_as_figma_shifted, t_badge_structure, t_glyph_inside_circle, t_scale_2x, t_offset, t_scale_path_loud, t_food_kept_and_kind_registered]
ok = 0
for f in T:
    try: f(); ok += 1; print('ok  ', f.__name__)
    except Exception: print('FAIL', f.__name__); traceback.print_exc()
print(f'ok {ok} из {len(T)}'); sys.exit(0 if ok == len(T) else 1)
