# Acceptance gate - the last step of run.sh (01.10.2026, test of floor 5:
#   proposals/plan/2026-10-01-выводы-теста-5-этажа.md, p. 153). Exit 1 - the floor is not to be
#   delivered: the reasons are printed as a list and written to gate.json. Why: floor 5 v01 went out with thresholds of
#   plan/rules/60 unmet - 73 unnamed groups of 'misc', 3 pieces that are parts of objects, 4 toilet accessories out of size.
#   run.sh did not check them, and a run with minimal effort never opened those files.
# Stops (plan/rules/60, the summary table):
#   S1  'misc' objects with the default name - unnamed (3.7a): 0. A group is named by a class (a rule, MANUAL) or by a
#       MISC_GROUPS entry without a key - a row of 'Unknown' with its own name (plan/rules/20 §3.8);
#   S2  'fragment of <object>' after reclass.py (misc_context.json, 3.7b): 0;
#   S3  MISC_GROUPS entries that named nothing (reclass.json, places.X_miss): 0;
#   S4  'wcacc' out of its class size (class_params.json, 3.10): 0 - a SANZONES box wider than the toilets or a merge
#       across cabins (plan/rules/20 §3.3); coloured joints of partitions: 0;
#   S5  ink, normal and strict: 0 / 0 components (plan/rules/60 §2);
#   S6  boxcut: 0 and 0 (3.9b);  S7  empty wall bodies >= 0.15 m2: 0 (3.12);  S8  arcs with a pattern under 90 %: 0 (3.11);
#   S9  wall polygons valid, DXF audit errors 0 (§1);
#   S10 walls against the delivered round (cfg.GATE_PREV or env GATE_PREV = its walls_fixed.pkl): every piece >= 0.01 m2
#       gone or added lies in a box of cfg.GATE_WALLS_OK = [dict(box=(x0,y0,x1,y1), why='...')] - looked at, meant.
# A stop the operator has looked at and accepts for this delivery: cfg.GATE_ACCEPT = {'S1': dict(max=N, why='...')}.
#   The gate passes it while the count is <= max and prints it as accepted; gate.json keeps the why for the README of
#   the delivery. A count above max stops again - the acceptance is for what was looked at, not for what comes next.
# Code 007 (plan/rules/60 §8; proposals 218, Р3 of the summary of 03.10.2026; owner's decision of 04.10.2026, строка 164):
#   - the why of an acceptance is one of four kinds with its link (checks/accept.py): a why without a kind accepts nothing;
#   - S0  a check of run.sh failed or its report is missing (checks_failed.txt, the reports the gate reads) - not acceptable:
#         a gate that reads no report passes silently;
#   - S2  'part of an object' is not acceptable: a fragment is named by a rule, a MANUAL box or a MISC_GROUPS entry;
#   - S11* every group of 'Unknown' (layer A-00, a name of its own) has the picture of its question - cfg.QUESTIONS =
#         {'<name>': 'questions/N<n>_<slug>.png'} or the entry's q='...', the file in the floor folder - or the owner's answer
#         in its name, '(владелец ДД.ММ.ГГГГ)' ('already answered', п. 292); one entry names one group of one kind: at most
#         cfg.UNKNOWN_MAX_PER_ENTRY (20) places (reclass.json, X_hits);
#   - S12* closed rectangles of furniture size in the partitions (was the list L2) and S13* frames round a level mark in the
#         partitions (was L3) are stops: a verdict per place - cfg.GATE_PLACES = {'S12*': [dict(at=(x, y), why='...')]},
#         a why of the closed list within 3 pt of the place - or the whole stop by GATE_ACCEPT;
#   - L4  MISC_GROUPS entries replaced by a later entry on the same example (reclass.json, X_dup): a cfglint warning.
# Code 008:
#   - S14* DXF layers (Т4-13, Т4-14): a layer a primitive uses (model and block definitions) without a record in the layer
#         table or without a description, a TEXT / MTEXT off '...T-' / '...D-' (verify.json, dxf_layer_check) - not acceptable;
#   - S12* with cfg.DETECT8: also closed rectangles of partition lines with free room on two sides or more (Т4-6);
#   - QUICK=1 (run.sh manual): a preliminary gate without both ink checks and the arcs - never a pass (exit 2).
# Lists to look at (printed and in gate.json, they do not stop):
#   L1 MANUAL boxes > 20 m2 and objects of one box > 1500 primitives - 'the box took what is not its own' (M24 of floor
#      5: the shaft of the panoramic lift, 3 convectors, a plant and furniture in the box of a glass partition);
#   L2 closed rectangles of light-partition lines ('lpart', 'lpartc', 'gklpart', 'glasspart', 'railing') of furniture size, 0.3-3 m, touching no wall and
#      no glass - 'furniture in the partitions';
#   L3 light-partition frames around a level text '±N.NNN' and light-partition lines outside the outline of the walls -
#      'drawing signs in the partitions' (a break line, level frames, local dimensions on floor 5).
#   python3 checks/gate.py            (floor folder; reads the reports of run.sh, writes gate.json)
import os, sys, json, pickle, re, math, collections
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import cfg, load, pts, MM_PER_PT
from accept import why_kind
from shapely.geometry import LineString, Polygon, Point, box
from shapely.ops import unary_union, polygonize
from shapely.strtree import STRtree
K2 = MM_PER_PT * MM_PER_PT / 1e6                  # pt2 -> m2
def J(f, d=None):
    try: return json.load(open(f))
    except Exception: return d
ACC = getattr(cfg, 'GATE_ACCEPT', {})
NO_ACCEPT = ('S0', 'S2', 'S14*')                   # code 007: not acceptable at all (plan/rules/60 §8); code 008: S14* - a layer is fixed in the table, not accepted
stops, accepted, lists = [], [], {}
def stop(code, n, what, where=None):
    a = ACC.get(code)
    rec = dict(code=code, n=n, what=what, where=(where or [])[:30])
    if n <= 0: return
    if a is not None and code in NO_ACCEPT:
        rec['what'] += f' — {code} не принимается GATE_ACCEPT (plan/rules/60 §8)'; stops.append(rec); return
    if a is not None and n <= a.get('max', -1):
        kind, miss = why_kind(a.get('why', ''))
        if kind is None:
            rec['what'] += f' — GATE_ACCEPT не принят: {miss}'; stops.append(rec); return
        rec['why'] = a.get('why', ''); rec['why_kind'] = kind; accepted.append(rec)
    else: stops.append(rec)
# S0 the checks of run.sh: a failed step or a missing report
_failed = [l.strip() for l in open('checks_failed.txt')] if os.path.exists('checks_failed.txt') else []
_need = ['inst_final.pkl', 'reclass.json', 'verify.json', 'ink.json', 'ink_strict.json', 'boxcut.json', 'misc_inventory.json',
         'misc_context.json', 'class_params.json', 'arcs_audit.json', 'wall_evidence.json']
# (code 008, Т4-9) QUICK=1 - the quick round of run.sh manual: both ink checks, arcs and ends are left for the delivery;
#   the gate is preliminary - it lists the other stops and never passes (exit 2): a floor is delivered after a full round
QUICK = bool(os.environ.get('QUICK'))
HEAVY = ('ink.json', 'ink_strict.json', 'arcs_audit.json')
if QUICK: _need = [f for f in _need if f not in HEAVY]
_miss = [f for f in _need if not os.path.exists(f)]
stop('S0', len(_failed) + len(_miss), f"проверки run.sh не отработали: шаги {_failed}, нет отчётов {_miss} — шлюз без отчёта не пропускает",
     [])
P = load()
inst = pickle.load(open('inst_final.pkl', 'rb'))
DEFAULT = 'Прочий элемент (не классифицирован)'
# S1 unnamed 'misc'
un = [q for q in inst if q['key'] == 'misc' and q['prims'] and q['name'] == DEFAULT]
def centre(q):
    xs = [v for i in q['prims'] for v in pts(P[i])]
    return [round((min(x for x, y in xs) + max(x for x, y in xs)) / 2, 1), round((min(y for x, y in xs) + max(y for x, y in xs)) / 2, 1)]
inv = J('misc_inventory.json', {})
gid = {}
for k, g in enumerate(inv.get('list', [])):
    for n in g.get('inst', []): gid[n] = k
_idx = {id(q): n for n, q in enumerate(inst)}
ung = len(set(gid.get(_idx[id(q)], ('solo', _idx[id(q)])) for q in un))
stop('S1', len(un), f"безымянных объектов «прочего» {len(un)} в {ung} группах (3.7а): каждая группа — класс, MANUAL или строка «Неизвестного» в MISC_GROUPS",
     [centre(q) for q in un[:30]])
# S2 fragments of objects
ctx = J('misc_context.json', {})
fr = {k: v for k, v in ctx.get('summary', {}).items() if k.startswith('fragment')}
stop('S2', sum(fr.values()), f"«часть объекта» после reclass.py (3.7б): {fr}",
     [r['at_pt'] for r in ctx.get('list', []) if str(r.get('cat', '')).startswith('fragment')])
# S3 MISC_GROUPS entries that named nothing
xm = J('reclass.json', {}).get('places', {}).get('X_miss', [])
stop('S3', len(xm), 'записей MISC_GROUPS, которые ничего не назвали' + ('; причины: ' + '; '.join(f"{tuple(r.get('at', []))} — {r.get('why', '')}" for r in xm[:5]) if xm else ''),
     [r.get('at') for r in xm])
# S4 class sizes
cp = J('class_params.json', {}).get('per_class', {})
w = cp.get('wcacc', {})
stop('S4', w.get('out', 0), "аксессуаров санузла вне размеров класса (3.10): рамка SANZONES шире санузлов или склейка через кабины",
     [s['at_pt'] for s in w.get('samples', []) if any(str(x).startswith('размер') for x in s.get('why', []))])
col = sum(v.get('coloured', 0) for v in cp.values())
stop('S4c', col, 'цветных узлов перегородок (3.10)')
# S5 ink
for f, code in (() if QUICK else (('ink.json', 'S5'), ('ink_strict.json', 'S5s'))):
    d = J(f, {})
    if not d: stop(code, 1, f'нет {f}'); continue
    m = d['missing'] if isinstance(d['missing'], int) else len(d['missing']); e = d['extra'] if isinstance(d['extra'], int) else len(d['extra'])
    stop(code, m + e, f'{f}: пропуск {m}, лишнее {e} компонент (plan/rules/60 §2)')
# S6 boxcut
b = J('boxcut.json', {})
cut = b.get('cut_by_boxes', {}); cutn = sum(cut.values()) if isinstance(cut, dict) else int(cut or 0)
stop('S6', cutn + int(b.get('sheet_by_length_inside', 0) or 0), 'выброшено рамками и «рамкой» по длине (3.9б)')
# S7 empty wall bodies, S8 arcs
we = J('wall_evidence.json', {})
stop('S7', int(we.get('empty', 0) or 0), f"пустых тел стен ≥ 0,15 м² (3.12): {we.get('empty_m2')} м²")
ar = J('arcs_audit.json', {})
if not QUICK: stop('S8', int(ar.get('below', 0) or 0), 'полос дуг с узором, покрытых стенами меньше 90 % (3.11)')
# S9 validity
v = J('verify.json', {})
stop('S9', (0 if v.get('walls_valid', False) else 1) + int(v.get('dxf_audit_errors', 0) or 0), 'стены невалидны или ошибки DXF audit')
# S14* (code 008, Т4-13, Т4-14) DXF layers: every layer a primitive uses (model and block definitions) has a record
#   with a description in the layer table; texts only on '...T-' and '...D-'
_lc = v.get('dxf_layer_check')
if _lc is None: stop('S14*', 1, 'verify.json без проверки слоёв DXF (dxf_layer_check): verify.py кода 008 не отработал')
else:
    _ln = len(_lc.get('unrecorded', [])) + len(_lc.get('no_description', [])) + sum((_lc.get('texts_off_TD') or {}).values())
    stop('S14*', _ln, f"слои DXF: без записи в таблице {_lc.get('unrecorded')}, без описания {_lc.get('no_description')}, тексты вне …T-/…D- {_lc.get('texts_off_TD')} "
         "(plan/rules/50 §1, §3; таблица — layers8.py)")
# S10 walls against the delivered round
prev = os.environ.get('GATE_PREV') or getattr(cfg, 'GATE_PREV', None)
WF = 'walls_fixed.pkl' if os.path.exists('walls_fixed.pkl') else 'walls.pkl'
Wn = pickle.load(open(WF, 'rb'))['Wpt']
diffs = []
if prev and os.path.exists(prev):
    Wp = pickle.load(open(prev, 'rb'))['Wpt']
    ok = [tuple(z['box']) for z in getattr(cfg, 'GATE_WALLS_OK', [])]
    for c in sorted(set(Wn) | set(Wp)):
        a_, b_ = unary_union(Wp.get(c, [])), unary_union(Wn.get(c, []))
        for kind, g in (('пропало', a_.difference(b_)), ('добавилось', b_.difference(a_))):
            for q in (getattr(g, 'geoms', None) or [g]):
                if q.is_empty or q.geom_type != 'Polygon' or q.area * K2 < 0.01: continue
                rp = q.representative_point()
                if any(z[0] <= rp.x <= z[2] and z[1] <= rp.y <= z[3] for z in ok): continue
                diffs.append(dict(cls=c, kind=kind, m2=round(q.area * K2, 3), at=[round(rp.x, 1), round(rp.y, 1)]))
    stop('S10', len(diffs), f'кусков стен ≥ 0,01 м², изменившихся против прошлого круга ({prev}) и не отмеченных в GATE_WALLS_OK', [d_['at'] for d_ in diffs])
# L1 operator boxes
big = []
from detect8 import bbox_of as _bbox8
for key, name, layer, boxes in getattr(cfg, 'MANUAL', []):
    for bx in map(_bbox8, boxes):              # code 008: a polygon element (Т4-7) - by its bbox
        a2 = (bx[2] - bx[0]) * (bx[3] - bx[1]) * K2
        if a2 > 20: big.append(dict(name=name[:60], m2=round(a2, 1), box=[round(x, 1) for x in bx]))
FABRIC = ('wall', 'lpart', 'lpartc', 'gklpart', 'glasspart', 'railing', 'opening', 'facade', 'glass', 'zone', 'roomsep', 'wallline', 'misc', 'loose', 'stair', 'carpet')
heavy = [dict(key=q['key'], name=q['name'][:60], prims=len(q['prims']), at=centre(q)) for q in inst if q['key'] not in FABRIC and len(q['prims']) > 1500]
lists['L1'] = dict(boxes_gt_20m2=big, objects_gt_1500_prims=heavy)
# L2 / L3 light partitions
lp_ids = [i for q in inst if q['key'] in ('lpart', 'lpartc', 'gklpart', 'glasspart', 'railing') for i in q['prims'] if P[i][0] == 'l']
segs = [LineString(P[i][4]) for i in lp_ids if len(P[i][4]) >= 2]
WU = unary_union([g for c in Wn.values() for g in c]) if Wn else Polygon()
glass = unary_union([LineString(P[i][4]) for q in inst if q['key'] in ('glass', 'facade') for i in q['prims'] if P[i][0] == 'l' and len(P[i][4]) >= 2])
furn, frames = [], []
import detect8 as _d8
_D8F = _d8.on('pen') or _d8.on('desks')
_LPT = STRtree(segs) if segs else None
def _free_sides(pg, r):
    """sides of the rectangle with free room in front: 300 mm out of the side's middle is not in a wall body and the
    way there crosses no other partition or glass line"""
    xy = list(r.exterior.coords)[:4]; cx_, cy_ = r.centroid.x, r.centroid.y; n_ = 0; d_ = _d8.pt(300)
    for a_, b_ in zip(xy, xy[1:] + xy[:1]):
        m_ = ((a_[0] + b_[0]) / 2, (a_[1] + b_[1]) / 2); v_ = (m_[0] - cx_, m_[1] - cy_); L_ = math.hypot(*v_) or 1
        o_ = (m_[0] + v_[0] / L_ * d_, m_[1] + v_[1] / L_ * d_); w_ = LineString([(m_[0] + v_[0] / L_ * 0.4, m_[1] + v_[1] / L_ * 0.4), o_])
        if not WU.is_empty and WU.contains(Point(o_)): continue
        if not glass.is_empty and glass.intersects(w_): continue
        if _LPT is not None and any(segs[j].intersects(w_) for j in _LPT.query(w_)): continue
        n_ += 1
    return n_
words = J('words.json', [])
lvl = [w_ for w_ in words if re.fullmatch(r'[+±-]?\d{1,2}[.,]\d{3}', str(w_[2]).strip())]
if segs:
    for pg in polygonize(unary_union(segs)):
        r = pg.minimum_rotated_rectangle
        if r.area <= 0 or pg.area / r.area < 0.9: continue
        xy = list(r.exterior.coords); s1, s2 = math.dist(xy[0], xy[1]) * MM_PER_PT, math.dist(xy[1], xy[2]) * MM_PER_PT
        L_, S_ = max(s1, s2), min(s1, s2)
        c = pg.representative_point()
        if any(pg.contains(Point(w_[0], w_[1])) for w_ in lvl) and L_ <= 2500: frames.append(dict(size_mm=[round(L_), round(S_)], at=[round(c.x, 1), round(c.y, 1)]))
        elif 300 <= S_ and L_ <= 3000 and pg.distance(WU) > 0.3 and (glass.is_empty or pg.distance(glass) > 0.3):
            furn.append(dict(size_mm=[round(L_), round(S_)], at=[round(c.x, 1), round(c.y, 1)]))
        elif _D8F and 300 <= S_ <= 1200 and L_ <= 3000 and _free_sides(pg, r) >= 2:
            # (code 008, Т4-6) furniture without a fill stands at a wall too: a closed rectangle of partition lines with
            #   free room on two sides or more is a candidate (floor 4, test 4: L2 = 2 at 18 pieces of furniture taken
            #   for partitions - outline desks, white desks, a counter, cabinets)
            furn.append(dict(size_mm=[round(L_), round(S_)], at=[round(c.x, 1), round(c.y, 1)], d8='free sides'))
hull = unary_union([WU, glass]).convex_hull.buffer(2) if not WU.is_empty else None
outside = [s for s in segs if hull is not None and not hull.contains(s.interpolate(0.5, normalized=True))]
# S12* / S13* (code 007; proposal 218, п. 3): the lists L2 and L3 are stops, a verdict per place (cfg.GATE_PLACES)
GPL = getattr(cfg, 'GATE_PLACES', {})
def per_place(code, places):
    left, ok_, bad = [], [], []
    for pl in places:
        v = [e for e in GPL.get(code, []) if math.dist(e['at'], pl['at']) <= 3.0]
        if not v: left.append(pl); continue
        kind, miss = why_kind(v[0].get('why', ''))
        if kind is None: pl = dict(pl, verdict_rejected=miss); left.append(pl); bad.append(pl)
        else: ok_.append(dict(pl, why=v[0]['why'], why_kind=kind))
    return left, ok_, bad
f_left, f_ok, f_bad = per_place('S12*', furn)
stop('S12*', len(f_left), f"замкнутых прямоугольников размера мебели в перегородках (бывший список L2): вердикт на каждое место — класс правилом, "
     f"рамка MANUAL или GATE_PLACES с причиной из закрытого списка{'; отклонено вердиктов ' + str(len(f_bad)) if f_bad else ''}",
     [p_['at'] for p_ in f_left])
r_left, r_ok, r_bad = per_place('S13*', frames)
stop('S13*', len(r_left), f"рамок вокруг отметки уровня в перегородках (бывший список L3): знак чертежа — не перегородка; вердикт на каждое место"
     f"{'; отклонено вердиктов ' + str(len(r_bad)) if r_bad else ''}", [p_['at'] for p_ in r_left])
lists['L2'] = dict(n=len(furn), places=furn[:40], verdicts=f_ok[:40])
lists['L3'] = dict(level_frames=frames[:40], frame_verdicts=r_ok[:40], lines_outside_walls=len(outside),
                   lines_outside_walls_at=[[round(s.interpolate(0.5, normalized=True).x, 1), round(s.interpolate(0.5, normalized=True).y, 1)] for s in outside[:30]])
# S11* 'Unknown' (code 007; plan/rules/60 §8, строка 135, п. 292): every group has the picture of its question or the owner's answer
QS = dict(getattr(cfg, 'QUESTIONS', {}))
for gdef in getattr(cfg, 'MISC_GROUPS', []):
    if gdef.get('q') and gdef.get('name'): QS.setdefault(gdef['name'], gdef['q'])
ANS = re.compile(r'владел\w*\s+\d{1,2}\.\d{1,2}\.\d{4}', re.I)
# a group of 'Unknown' is named by the operator: a MISC_GROUPS entry without a key (it keeps 'misc' and A-00), a MANUAL box on
#   A-00, or a name starting with 'Неизвестное'; what a rule of the code named on A-00 ('Мелкая деталь у стены', 'loose')
#   is a class, not a question
UN_CFG = {g['name'] for g in getattr(cfg, 'MISC_GROUPS', []) if g.get('name') and g.get('key', 'misc') == 'misc' and not g.get('join')}
UN_CFG |= {m[1] for m in getattr(cfg, 'MANUAL', []) if len(m) > 2 and m[2] == 'A-00----E-'}
ug = collections.OrderedDict()
for q in inst:
    if not q['prims'] or q['name'] == DEFAULT: continue
    if q['name'] in UN_CFG or str(q['name']).startswith('Неизвестное'):
        ug.setdefault(q['name'], []).append(q)
u_stop, u_answered, u_asked = [], [], []
for nm, qs in ug.items():
    if ANS.search(nm): u_answered.append(dict(name=nm[:120], n=len(qs))); continue
    pic = QS.get(nm)
    if pic and os.path.exists(pic): u_asked.append(dict(name=nm[:120], n=len(qs), picture=pic)); continue
    u_stop.append(dict(name=nm[:120], n=len(qs), at=centre(qs[0]), picture=pic, why='картинка не найдена: ' + pic if pic else 'нет картинки вопроса'))
UMAX = getattr(cfg, 'UNKNOWN_MAX_PER_ENTRY', 20)
xh = [h for h in J('reclass.json', {}).get('places', {}).get('X_hits', []) if h.get('key', 'misc') == 'misc' and not h.get('join') and h.get('n', 0) > UMAX]
stop('S11*', len(u_stop) + len(xh), f"групп «Неизвестного» без картинки вопроса {len(u_stop)} (cfg.QUESTIONS или q= в записи — файл questions/…png в папке этажа; "
     f"ответ владельца — «(владелец ДД.ММ.ГГГГ)» в имени); записей «Неизвестного» шире {UMAX} мест — {len(xh)}: одна запись — одна группа одного вида",
     [u['at'] for u in u_stop] + [h['at'] for h in xh])
lists['unknown'] = dict(groups=len(ug), objects=sum(len(v) for v in ug.values()), answered=u_answered[:40], asked=u_asked[:40],
                        no_picture=u_stop[:40], wide_entries=xh[:20])
# L4 MISC_GROUPS duplicates (Т3-3): the later entry won, the cfg should keep one
lists['L4'] = dict(misc_groups_duplicates=J('reclass.json', {}).get('places', {}).get('X_dup', [])[:40])
res = dict(ok=not stops and not QUICK, stops=stops, accepted=accepted, lists=lists, walls_vs_prev=diffs[:200], prev=prev, preliminary=QUICK)
json.dump(res, open('gate.json', 'w'), ensure_ascii=False, indent=1)
print('GATE', 'PASS' if not stops else 'STOP — сдача запрещена')
for r in stops: print('  STOP', r['code'], r['n'], '-', r['what'])
for r in accepted: print('  принято', r['code'], r['n'], '-', r['what'], '| почему:', r.get('why', ''))
print('  на просмотр: рамок MANUAL > 20 м²', len(big), '| объектов > 1500 примитивов', len(heavy), '| мебель в перегородках', len(furn),
      f'(вердиктов {len(f_ok)})', '| рамки отметок в перегородках', len(frames), f'(вердиктов {len(r_ok)})', '| линий перегородок вне контура стен', len(outside),
      '| «Неизвестное»:', len(ug), 'групп, уже отвечено', len(u_answered), ', с картинкой', len(u_asked),
      '| дубли MISC_GROUPS', len(lists['L4']['misc_groups_duplicates']))
if QUICK: print('  ПРЕДВАРИТЕЛЬНЫЙ шлюз (run.sh manual, QUICK=1): сверки чернил и дуг не делались — сдача только после полного круга'); sys.exit(2 if not stops else 1)
sys.exit(0 if not stops else 1)
