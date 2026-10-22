# Owner question tile, three frames + our plan (plan/rules/70 §2 pp. 12, 20): the whole floor with the place circled and the
#   other places of the same kind dotted; the surroundings - source and our classification side by side; the source
#   close up without overlays (thin red frame). Caption: what we see, what is drawn now, the question.
#   python3 qtile.py run_dir spec.json out_dir
#   spec: [{"num": 1, "title": "...", "places": [[x0,y0,x1,y1], ...], "see": "...", "did": "...", "ask": "..."}, ...]
import sys, os, json, textwrap, importlib.util
import pymupdf as fitz
from PIL import Image, ImageDraw, ImageFont
d, spec_f, out = sys.argv[1], sys.argv[2], sys.argv[3]; os.makedirs(out, exist_ok=True)
here = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(here, 'classmap.py')).read().split('if BOX:')[0]
sys.argv = [sys.argv[0], d, os.path.join(__import__('tempfile').gettempdir(), '_q'), '1']
g = {'__name__': 'classmap_q'}; exec(compile(src, 'classmap.py', 'exec'), g); g['LEGEND'] = True
cfg = g['cfg']; pg = fitz.open(os.path.join(d, cfg.PDF))[0]
FD = '/usr/share/fonts/truetype/dejavu/'
fb = ImageFont.truetype(FD + 'DejaVuSans-Bold.ttf', 20); fm = ImageFont.truetype(FD + 'DejaVuSans.ttf', 16); fs = ImageFont.truetype(FD + 'DejaVuSans.ttf', 13)
def wrap_px(text, font, width):
    """lines of text no wider than width pixels in this font; a word longer than the width is cut by characters"""
    out, cur = [], ''
    for w in text.split():
        t = (cur + ' ' + w) if cur else w
        if font.getlength(t) <= width: cur = t; continue
        if cur: out.append(cur)
        while font.getlength(w) > width:
            k = len(w)
            while k > 1 and font.getlength(w[:k]) > width: k -= 1
            out.append(w[:k]); w = w[k:]
        cur = w
    if cur: out.append(cur)
    return out
def render(x0, y0, x1, y1, Z, fade=0.0):
    pix = pg.get_pixmap(matrix=fitz.Matrix(Z, Z), clip=fitz.Rect(x0, y0, x1, y1))
    im = Image.frombytes('RGB', (pix.width, pix.height), pix.samples)
    return Image.blend(im, Image.new('RGB', im.size, 'white'), fade) if fade else im
for q in json.load(open(spec_f)):
    P_ = q['places']; m = P_[q.get('main', 0)]
    # frame 1: whole floor
    X0, Y0, X1, Y1 = cfg.WIN; Z1 = 880 / (X1 - X0)
    f1 = render(X0, Y0, X1, Y1, Z1, 0.45); d1 = ImageDraw.Draw(f1)
    for k, b in enumerate(P_):
        cx, cy = ((b[0] + b[2]) / 2 - X0) * Z1, ((b[1] + b[3]) / 2 - Y0) * Z1
        r = max(10, max(b[2] - b[0], b[3] - b[1]) * Z1 / 2 + 8)
        if b is m: d1.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(230, 0, 0), width=4)
        else: d1.ellipse([cx - 7, cy - 7, cx + 7, cy + 7], outline=(255, 130, 0), width=3)
    # frame 2: surroundings, source | our plan
    cx, cy = (m[0] + m[2]) / 2, (m[1] + m[3]) / 2; h = max(q.get('half', 60), (m[2] - m[0]) / 2 + 12, (m[3] - m[1]) / 2 + 12)
    Z2 = 430 / (2 * h); b2 = (cx - h, cy - h, cx + h, cy + h)
    f2a = render(*b2, Z2); d2 = ImageDraw.Draw(f2a)
    d2.rectangle([(m[0] - b2[0]) * Z2 - 3, (m[1] - b2[1]) * Z2 - 3, (m[2] - b2[0]) * Z2 + 3, (m[3] - b2[1]) * Z2 + 3], outline=(230, 0, 0), width=2)
    g['Z'] = Z2; g['tile'](*b2, os.path.join(__import__('tempfile').gettempdir(), '_q2.png')); f2b = Image.open(os.path.join(__import__('tempfile').gettempdir(), '_q2.png')).convert('RGB')
    ImageDraw.Draw(f2b).rectangle([(m[0] - b2[0]) * Z2 - 3, (m[1] - b2[1]) * Z2 - 3, (m[2] - b2[0]) * Z2 + 3, (m[3] - b2[1]) * Z2 + 3], outline=(0, 0, 0), width=1)
    # frame 3: close-up source
    w3 = max(m[2] - m[0], m[3] - m[1]) + 6; Z3 = min(40, 430 / w3)
    c3 = (cx - w3 / 2, cy - w3 / 2, cx + w3 / 2, cy + w3 / 2); f3 = render(*c3, Z3); d3 = ImageDraw.Draw(f3)
    d3.rectangle([(m[0] - c3[0]) * Z3 - 2, (m[1] - c3[1]) * Z3 - 2, (m[2] - c3[0]) * Z3 + 2, (m[3] - c3[1]) * Z3 + 2], outline=(230, 0, 0), width=1)
    # caption - wrapped by the width of the picture in pixels of its font (code 007, п. 294: at 138 characters the end of
    #   a long line went past the edge of a 1200 px picture)
    W = max(f1.width, f2a.width + f2b.width + f3.width + 30) + 20
    lines = [(fb, t) for t in wrap_px(f"Вопрос {q['num']}. {q['title']}", fb, W - 20)]
    for lab, key in (('Что видим', 'see'), ('Как нарисовано сейчас', 'did'), ('Вопрос', 'ask')):
        if q.get(key):
            for t in wrap_px(f'{lab}: {q[key]}', fm, W - 20): lines.append((fm, t))
    capH = 14 + sum(30 if f_ is fb else 22 for f_, _ in lines)
    H = capH + f1.height + 30 + max(f2a.height, f3.height) + 40
    sh = Image.new('RGB', (W, H), 'white'); ds = ImageDraw.Draw(sh); y = 10
    for f_, t in lines: ds.text((10, y), t, fill=(0, 0, 0), font=f_); y += 30 if f_ is fb else 22
    ds.text((10, y + 2), '1 — весь этаж (красный круг — место, оранжевые — такие же места)', fill=(90, 90, 90), font=fs)
    sh.paste(f1, (10, y + 20)); y2 = y + 20 + f1.height + 12
    ds.text((10, y2), '2 — окружение: исходник', fill=(90, 90, 90), font=fs); ds.text((20 + f2a.width, y2), 'наш план (цвет — класс, красный — «прочее»)', fill=(90, 90, 90), font=fs)
    ds.text((30 + f2a.width + f2b.width, y2), '3 — исходник крупно', fill=(90, 90, 90), font=fs)
    sh.paste(f2a, (10, y2 + 18)); sh.paste(f2b, (20 + f2a.width, y2 + 18)); sh.paste(f3, (30 + f2a.width + f2b.width, y2 + 18))
    fn = os.path.join(out, f"q_{q['num']:02d}.png"); sh.save(fn); print(fn, sh.size)
