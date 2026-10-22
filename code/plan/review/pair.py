# Source crop | class map of a run, side by side, for one or more windows (pt) (code 008, Т4-11; the legend is cut off):
#   python3 pair.py RUN_DIR OUT_DIR name:x0,y0,x1,y1[:zoom] ...
import sys, os, subprocess
from PIL import Image
import pymupdf as fitz
R = os.path.abspath(sys.argv[1]); O = os.path.abspath(sys.argv[2]); CODE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # code 008: the code of this copy
os.makedirs(O, exist_ok=True)
import importlib.util as _iu
_sp = _iu.spec_from_file_location('cfgx', os.path.join(R, 'cfg.py')); _c = _iu.module_from_spec(_sp); sys.path.insert(0, R); _sp.loader.exec_module(_c)
pg = fitz.open(os.path.join(R, _c.PDF))[0]   # code 008: the run's own PDF (cfg.PDF), not f4.pdf
for a in sys.argv[3:]:
    t = a.split(':'); name = t[0]; b = [float(v) for v in t[1].split(',')]; z = float(t[2]) if len(t) > 2 else 8
    pix = pg.get_pixmap(matrix=fitz.Matrix(z, z), clip=fitz.Rect(*b), alpha=False)
    s = Image.frombytes('RGB', (pix.width, pix.height), pix.samples)
    pre = os.path.join(O, name + '_cm')
    L = 190.0 / z      # the legend sits in the top-left 190 px: render a box wider to the left and cut it off
    subprocess.run(['python3', os.path.join(CODE, 'review', 'classmap.py'), R, pre, str(z), '1', '1'] + [str(v) for v in (b[0] - L, b[1], b[2], b[3])],
                   check=True, cwd=R, env=dict(os.environ, PYTHONPATH=CODE), capture_output=True)
    c = Image.open(pre + '.png').convert('RGB'); c = c.crop((c.width - s.width, 0, c.width, c.height))
    W = Image.new('RGB', (s.width + c.width + 6, max(s.height, c.height)), 'white'); W.paste(s, (0, 0)); W.paste(c, (s.width + 6, 0))
    W.save(os.path.join(O, name + '.png')); os.remove(pre + '.png'); print(name, W.size)
