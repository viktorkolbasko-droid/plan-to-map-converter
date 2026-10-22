# common-frame mm -> each floor's pt: xf_where.py crossfloor.json X Y f1 f2 ...
import sys, json, os, importlib.util, numpy as np
J = json.load(open(sys.argv[1])); X, Y = float(sys.argv[2]), float(sys.argv[3])
for d in sys.argv[4:]:
    spec = importlib.util.spec_from_file_location('cfg_' + d, os.path.join(d, 'cfg.py'))
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')); sys.path.insert(0, d)
    cfg = importlib.util.module_from_spec(spec); spec.loader.exec_module(cfg); sys.path.pop(0)
    kx = np.polyfit(cfg.AX_X, cfg.AX_XMM, 1); ky = np.polyfit(cfg.AX_Y, cfg.AX_YMM, 1)
    r = J['registration'][d]; xm, ym = (X - r['tx']) / r['s'], (Y - r['ty']) / r['s']
    print(d, round((xm - kx[1]) / kx[0], 1), round((ym - ky[1]) / ky[0], 1), 'pt   curved:', getattr(cfg, 'CURVED_ZONES', None), ' axis:', getattr(cfg, 'AXIS_BOXES', None))
