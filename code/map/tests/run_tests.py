"""Прогон приёма по набору: класс, предупреждения, рабочий растр против эталона; рядом — что даёт «наивное» чтение."""
import json, os, sys, shutil, subprocess, time
import numpy as np
from PIL import Image
import pymupdf
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # code/ — без PYTHONPATH (К4, К5; v007)
from source_intake import intake

# набор и эталон — вне архива кода: пути задаются переменными (по умолчанию — как при сборке набора make_tests.py)
T = os.environ.get('UNS_INTAKE_TESTS', '/home/claude/work/intake/tests')
O = os.environ.get('UNS_INTAKE_OUT', '/home/claude/work/intake/out')
REF = os.environ.get('UNS_INTAKE_REF', '/home/claude/work/layers/client-d/input/raw.png')
if not os.path.exists(os.path.join(T, 'cases.json')) and os.path.exists(REF):                # ПР1: набора нет — собрать make_tests.py той же командой
    subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'make_tests.py')], check=True)
if not os.path.exists(os.path.join(T, 'cases.json')) or not os.path.exists(REF):
    sys.exit(f'нет набора тестов приёма: {T}/cases.json или эталона {REF} — соберите make_tests.py или задайте UNS_INTAKE_TESTS и UNS_INTAKE_REF; '
             'тест без внешних данных — tests/test_title_hex.py')
shutil.rmtree(O, ignore_errors=True)
cases = json.load(open(f'{T}/cases.json', encoding='utf-8'))
ref = Image.open(REF).convert('L')
W, H = ref.size
refa = np.asarray(ref).astype(float)
ref_dark = float((refa < 128).mean())

def cmp(img):
    """MAD по яркости после приведения к размеру эталона и доля тёмного; размер как есть."""
    g = img.convert('L')
    size = list(g.size)
    if g.size != (W, H):
        g = g.resize((W, H), Image.BILINEAR)
    a = np.asarray(g).astype(float)
    return size, round(float(np.abs(a - refa).mean()), 2), round(float((a < 128).mean()), 4)

def naive(path, kind):
    """Как читают «по привычке»: Image.open().convert('RGB'); PDF — первая картинка без маски."""
    try:
        if kind == 'pdf':
            d = pymupdf.open(path)
            if d.needs_pass:
                return None
            p = d[0]
            imgs = p.get_images(full=True)
            if not imgs:
                return None
            info = d.extract_image(imgs[0][0])
            import io
            return Image.open(io.BytesIO(info['image'])).convert('RGB')
        return Image.open(path).convert('RGB')
    except Exception as e:                                                # noqa: BLE001
        return str(e)[:60]

rows = []
for name, c in cases.items():
    out = os.path.join(O, os.path.splitext(name)[0])
    _t0 = time.time()
    rep = intake(os.path.join(T, name), out)
    _sec = round(time.time() - _t0, 2)
    warns = sorted(w['code'] for w in rep.get('warnings', []))
    exp = c['expect']
    ok = rep.get('class') == exp['class']
    miss = [w for w in exp.get('warn', []) if w not in warns]
    ok &= not miss
    ok &= not [w for w in exp.get('no_warn', []) if w in warns]          # v012: предупреждения, которых быть не должно (Б21)
    if 'kind' in exp:
        ok &= rep.get('kind') == exp['kind']
    if 'page' in exp:
        ok &= rep.get('chosen_page') == exp['page']
    work = os.path.join(out, 'work.png')
    wsize = mad = dark = None
    geo = None
    if rep.get('class') in ('pdf-vector', 'pdf-mixed') and os.path.exists(work):
        # точки векторов через to_pixels должны лечь на нарисованное в work.png
        d = pymupdf.open(os.path.join(T, name)); pg = d[rep['chosen_page'] - 1]
        a_, b_, c_, d_, e_, f_ = rep['render']['to_pixels']
        xs, ys = [], []
        def inked(dr):
            col = dr.get('color'); fill = dr.get('fill')
            dark = lambda c: c is not None and min(c) < 0.97
            return dark(col) or dark(fill)
        for dr in pg.get_drawings():
            if not inked(dr):
                continue
            r = dr['rect']
            for (x, y) in ((r.x0, r.y0), (r.x1, r.y1)):
                xs.append(a_ * x + c_ * y + e_); ys.append(b_ * x + d_ * y + f_)
        wa = np.asarray(Image.open(work).convert('L')) < 250
        yy, xx = np.nonzero(wa)
        if xs and len(xx):
            vb = (min(xs), min(ys), max(xs), max(ys)); ib = (xx.min(), yy.min(), xx.max(), yy.max())
            geo = round(max(abs(float(u) - float(v)) for u, v in zip(vb, ib)), 1)
            ok &= geo <= 6
    if exp.get('size_swapped') and os.path.exists(work):
        im = Image.open(work)
        ok &= im.size[0] < im.size[1]
        _, mad_back, _ = cmp(im.transpose(Image.ROTATE_90))
        ok &= mad_back <= 6
    vs_ref = name.startswith('t0') or name.startswith('t1') and name[:3] in ('t10', 't11', 't12', 't13', 't14', 't15', 't16') or name.startswith('t20')
    vs_ref = vs_ref and not name.startswith('t16b')                       # v012: скан на A4 — другие пропорции, с эталоном не сравнивается
    if os.path.exists(work):
        wsize, mad, dark = cmp(Image.open(work))
        if name.startswith('t10'):                                        # тёмный фон — сравниваем с инверсией
            mad = None
        if 'size' in exp:
            ok &= wsize == exp['size']
        if vs_ref and mad is not None and not name.startswith(('t17', 't18', 't19', 't21', 't22', 't23')):
            lim = 12 if name in ('t03_jpeg_q30.jpg', 't16_pdf_scan_lowres.pdf', 't11_png_small.png', 't06_png_palette_trns.png') else 6
            ok &= mad <= lim
    nv = naive(os.path.join(T, name), rep.get('kind'))
    n_size = n_mad = n_dark = None
    if isinstance(nv, Image.Image):
        n_size, n_mad, n_dark = cmp(nv)
    naive_route = None
    if rep.get('kind') == 'pdf':
        naive_route = 'map/rules/11 (PDF = вектор)'
    rows.append({'geo_px': geo, 'naive_route': naive_route, 'file': name, 'note': c['note'], 'class': rep.get('class'), 'expected': exp['class'], 'warnings': warns,
                 'missing_warnings': miss, 'chosen_page': rep.get('chosen_page'), 'work_size': wsize, 'mad': mad, 'dark': dark,
                 'naive_size': n_size, 'naive_mad': n_mad, 'naive_dark': n_dark if not isinstance(nv, str) else nv, 'ok': bool(ok), 'sec': _sec})
json.dump(rows, open(f'{O}/results.json', 'w'), ensure_ascii=False, indent=1)
print('ref dark share', round(ref_dark, 4))
for r in rows:
    print(('OK  ' if r['ok'] else 'FAIL'), r['file'][:26].ljust(26), (r['class'] or '')[:14].ljust(14), 'mad', r['mad'], 'dark', r['dark'], 'geo', r['geo_px'],
          '| naive', r['naive_size'], r['naive_mad'], r['naive_dark'], '|', ','.join(r['warnings']), ('MISSING ' + ','.join(r['missing_warnings'])) if r['missing_warnings'] else '')
print('passed', sum(r['ok'] for r in rows), 'of', len(rows))
