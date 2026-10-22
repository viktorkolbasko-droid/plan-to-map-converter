# ocg/start_ocg.py - code 009: the first step of the layer route (ocg/run_ocg.sh), a stop in seconds before anything is
#   computed, with the reason (plan/00, step 1; plan/rules/20 §3.8, fields OCG_*):
#   - cfg has the sheet's layer table OCG_LAYERS; every layer has a role of ocg/sheet.py ROLES, one role per layer;
#   - every OCG layer of the PDF has a record in the table ("слой без записи" - the table was made for another sheet or
#     the sheet changed: the layer's render, e2_inventory.py, then a record);
#   - the fields the steps read: MM_PER_PT, ORIGIN_PT, OCG_GLASS_COLORS, OCG_DESK_TOP, OCG_TOP_DRAW, OCG_ELEM_L (layers of the
#     table), OCG_RASTER_ROLES (roles), OCG_ORIGIN_AXES, OCG_SCALE_DESK;
#   - scale (code 010, К-3): the thresholds of the steps are in pt of the reference sheet (sheet.REF_MM_PER_PT, a constant
#     of the code) <one example: client-b, 48.04 mm/pt>; a sheet more than 2 % off is read as its copy at the reference
#     scale (norm.py, cfg.SHEET_MM_PER_PT); cfg.OCG_REF_MM_PER_PT / cfg.OCG_SCALE_TOL - a stop (they lifted it silently in
#     009, ПК3-П11); a sheet off without SHEET_MM_PER_PT - a stop, or cfg.OCG_SCALE_OK with a reason of the closed list.
#   python3 start_ocg.py              (floor folder)  exit 0 - ok, 3 - stop; ocg_start.json
#   python3 start_ocg.py --after-e3   after Э3: scale.json against cfg.MM_PER_PT (> 1 %) and cfg.ORIGIN_PT (> 1 pt) - stop when off
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sheet

res = dict(ok=True, stops=[], notes=[])
def stop(s): res['ok'] = False; res['stops'].append(s)

if '--after-e3' in sys.argv:
    try:
        sc = json.load(open('scale.json'))
        med = sc['A']['median']; n = sc['A']['n_inliers']
        if med is None:
            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); from checks.accept import why_kind
            _ok = getattr(sheet.cfg, 'OCG_SCALE_OK', ''); _kind, _miss = why_kind(_ok) if _ok else (None, 'нет cfg.OCG_SCALE_OK')
            if _kind: res['notes'].append(f'масштаб Э3 не измерен (нет размеров) — идёт по cfg.OCG_SCALE_OK ({_kind}): {_ok}')
            else: stop(f'масштаб: Э3 не нашёл размеров — cfg.MM_PER_PT не проверен; проверить вручную и задать cfg.OCG_SCALE_OK с причиной из закрытого списка ({_miss})')
        elif not sheet.K or abs(med / sheet.K - 1) > 0.01:
            # code 011 (ПК4-П14): the message names the field when the field decides what is read - Э3 measures the sheet the
            #   code reads (the copy x NORM_K by SHEET_MM_PER_PT, or the sheet itself)
            if sheet.NORM_K != 1.0:
                stop(f'масштаб: Э3 по {n} размерам на копии листа × {sheet.NORM_K:.4f} (по полю SHEET_MM_PER_PT = {sheet.SHEET_MM_PER_PT:g}) — '
                     f'{med} мм/pt, а копия должна быть в {sheet.REF_MM_PER_PT:g} (cfg.MM_PER_PT — {sheet.K}): расхождение > 1 % — поле неточно: '
                     f'cfg.SHEET_MM_PER_PT = {sheet.SHEET_MM_PER_PT * med / sheet.REF_MM_PER_PT:.4f} (масштаб самого листа; plan/rules/10 §2); '
                     f'если поле верно — cfg не по копии (plan/rules/20 §1)')
            elif abs(med / sheet.REF_MM_PER_PT - 1) > 0.02 and sheet.K and abs(sheet.K / sheet.REF_MM_PER_PT - 1) <= 0.02:
                stop(f'масштаб: Э3 по {n} размерам — {med} мм/pt на самом листе, а cfg.MM_PER_PT — {sheet.K} (в опорном масштабе): '
                     f'cfg размечен по копии, а SHEET_MM_PER_PT не задан'
                     + (f' (поле {sheet.SHEET_MM_PER_PT:g} — в полосе ±2 %, копии нет)' if sheet.SHEET_MM_PER_PT else '')
                     + f' — задать cfg.SHEET_MM_PER_PT = {med} (масштаб самого листа; plan/rules/10 §2)')
            else:
                stop(f'масштаб: Э3 по {n} размерам — {med} мм/pt, в cfg.MM_PER_PT — {sheet.K}: расхождение > 1 % — поправить cfg (plan/rules/20 §1)')
        else: res['notes'].append(f'масштаб Э3 {med} мм/pt по {n} размерам — cfg {sheet.K}')
        o = sc.get('origin', {}).get('origin_pt') or sc.get('origin', {}).get('A1xT')    # code 012: (a, b) of OCG_ORIGIN_AXES - origin_pt
        if o and (abs(o[0] - sheet.OX) > 1 or abs(o[1] - sheet.OY) > 1):
            stop(f'начало координат: Э3 — {o}, в cfg.ORIGIN_PT — {(sheet.OX, sheet.OY)}: расхождение > 1 pt (plan/rules/50 §1)')
        elif o: res['notes'].append(f'начало Э3 {o} — cfg {(sheet.OX, sheet.OY)}')
    except Exception as ex:
        stop(f'scale.json Э3 не прочитан: {ex}')
    json.dump(res, open('ocg_start_e3.json', 'w'), ensure_ascii=False, indent=1)
    print('ocg start after Э3:', 'ok' if res['ok'] else 'СТОП', '|', '; '.join(res['stops'] or res['notes']))
    sys.exit(0 if res['ok'] else 3)

if not sheet.TABLE:
    stop('в cfg нет таблицы слоёв листа OCG_LAYERS: таблица — по рендеру каждого слоя (ocg/e2_inventory.py), блок cfg — '
         'ocg/table2cfg.py (plan/00, шаг 1; plan/rules/20 §3.8)')
roles = {}
for r in sheet.TABLE:
    roles.setdefault(r['layer'], set()).add(r.get('role'))
for l, rs in roles.items():
    if len(rs) > 1: stop(f'у слоя «{l}» несколько ролей {sorted(map(str, rs))}: одна роль на слой')
    bad = [x for x in rs if x not in sheet.ROLES]
    if bad: stop(f'у слоя «{l}» нет роли маршрута (роль {bad[0]!r}): роли — ocg/sheet.py ROLES')
for f in ('MM_PER_PT', 'ORIGIN_PT', 'OCG_DESK_TOP', 'OCG_TOP_DRAW'):                 # required
    if getattr(sheet.cfg, f, None) in (None, '', [], ()): stop(f'нет поля cfg.{f} (plan/rules/20 §3.8)')
for f in ('OCG_GLASS_COLORS', 'OCG_ELEM_L', 'OCG_RASTER_ROLES'):                    # present, may be empty (a sheet without glass, ...)
    if not hasattr(sheet.cfg, f): stop(f'нет поля cfg.{f} (может быть пустым списком; plan/rules/20 §3.8)')
for f in ('OCG_ORIGIN_AXES', 'OCG_SCALE_DESK'):                                     # optional: Э3 measures only what is given
    if not getattr(sheet.cfg, f, None): res['notes'].append(f'cfg.{f} нет — Э3 его не меряет')
# code 012 (stage 2, v010): Э9з e9z_zones.py tells the number and the name of a room among the texts by the sheet's patterns -
#   a stop here, in seconds, not after Э7р (OCG_ROOM_NAME_SKIP_RE may be None: no texts to skip)
import re as _re
for f, none_ok in (('OCG_ROOM_NO_RE', False), ('OCG_ROOM_NAME_RE', False), ('OCG_ROOM_NAME_SKIP_RE', True)):
    if not hasattr(sheet.cfg, f) or (getattr(sheet.cfg, f) in (None, '') and not none_ok):
        stop(f'нет поля cfg.{f} — образец надписи помещения для Э9з (номер «40.10», название; пример — ocg/examples/cfg_federation-40.py)'
             + (' (может быть None)' if none_ok else ''))
    elif getattr(sheet.cfg, f) is not None:
        try: _re.compile(getattr(sheet.cfg, f))
        except _re.error as ex: stop(f'cfg.{f} = {getattr(sheet.cfg, f)!r} — не регулярное выражение: {ex}')
for l in sheet.ELEM_L:
    if l not in roles: stop(f'OCG_ELEM_L: слоя «{l}» нет в таблице слоёв')
for r in sheet.RASTER_ROLES:
    if r not in sheet.ROLES: stop(f'OCG_RASTER_ROLES: роли {r!r} нет')
if sheet.PDF and os.path.exists(sheet.PDF):
    import pymupdf
    d = pymupdf.open(sheet.PDF)
    try: ocgs = d.get_ocgs() or {}
    except Exception: ocgs = {}
    names = sorted({sheet.strip(v.get('name', '')) for v in ocgs.values()})
    miss = [n for n in names if n not in roles]
    res['ocg_layers'] = len(names)
    if miss: stop(f'слой листа без записи в таблице слоёв: {miss[:10]} — запись по рендеру слоя (e2_inventory.py), роль — ocg/sheet.py ROLES')
    extra = [l for l in roles if l not in names]
    if extra: res['notes'].append(f'в таблице есть слои, которых нет на листе: {extra[:10]}')
    # code 012 (СП-4 пп. 1-2, СО-3; ОЧ-63): the content of the layers against the roles and the axis fields (ocg/role_checks.py)
    if not miss and all(len(rs) == 1 and next(iter(rs)) in sheet.ROLES for rs in roles.values()):
        import role_checks
        try: role_checks.check(sheet, stop, res, sheet.PDF)
        except Exception as ex: stop(f'проверка содержимого слоёв (role_checks) упала: {type(ex).__name__}: {ex}')
else:
    stop(f'исходник не найден: cfg.PDF = {sheet.PDF!r}')
# code 010 (К-3; ПК3-П6, ПК3-П11): the reference scale is a property of the code - the fields that lifted the stop silently
#   in code 009 stop the run; a sheet more than 2 % off is read as its copy at 48.04 mm/pt (norm.py, cfg.SHEET_MM_PER_PT)
for f in ('OCG_REF_MM_PER_PT', 'OCG_SCALE_TOL'):
    if hasattr(sheet.cfg, f):
        stop(f'поле cfg.{f} убрано в коде 010: опорный масштаб маршрута — свойство кода ({sheet.REF_MM_PER_PT} мм/pt), лист другого '
             f'масштаба приводится к нему копией (cfg.SHEET_MM_PER_PT; plan/rules/10 §2) — удалить поле из cfg')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); import norm
from checks.accept import why_kind
_k, _st, _nt = norm.decide('ocg', sheet.K, sheet.SHEET_MM_PER_PT, sheet.SRC_PDF)
res['norm'] = dict(k=_k, sheet_mm_per_pt=sheet.SHEET_MM_PER_PT, cfg_mm_per_pt=sheet.K, pdf_read=sheet.PDF, notes=_nt)
res['notes'] += _nt
if _st:
    ok = getattr(sheet.cfg, 'OCG_SCALE_OK', '')
    kind, miss = why_kind(ok) if ok else (None, 'нет cfg.OCG_SCALE_OK')
    if kind and sheet.NORM_K == 1.0 and not sheet.SHEET_MM_PER_PT:
        res['notes'].append(_st[0] + f' — идёт без приведения по cfg.OCG_SCALE_OK ({kind}): {ok}')
    else:
        stop(_st[0] + ('' if sheet.SHEET_MM_PER_PT else f'; без приведения — только cfg.OCG_SCALE_OK с причиной из закрытого списка ({miss})'))
res['roles'] = {r: sorted(sheet.L(r)) for r in sheet.ROLES if sheet.L(r)}
json.dump(res, open('ocg_start.json', 'w'), ensure_ascii=False, indent=1)
if res['ok']:
    print('ocg start: ok — слоёв листа', res.get('ocg_layers'), '| ролей', len(res['roles']), '|', '; '.join(res['notes']))
    sys.exit(0)
print('СТОП ocg start:', '; '.join(res['stops']))
sys.exit(3)
