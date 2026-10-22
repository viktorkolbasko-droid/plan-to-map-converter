"""Тесты моста 0.33 (код карты v012, исполнитель 1) без внешних данных: синтетический DXF плана 012/013 (ezdxf) и SVG моста.
    python3 tests/test_bridge_v012.py        -> «ok N из N» и код 0; любая ошибка — код 1
Что проверяется:
  КМ-1 — читатель: класс по XDATA UNSPOT type, без XDATA — по коду ISO; неизвестный type — в `_unknown`; прямоугольник проёма двери
         (LWPOLYLINE type=door) — к своему блоку двери; кривые (bulge, CIRCLE) — объектами; «ПК» со слоя 68 любого представления;
  КМ-4 — граф носителей: общая вершина снимается во всех носителях; прореживание снимает вершину на прямой; откат при накладке;
  КМ-8 — дуга SVG A по окружности кривой плана; КМ-2 — стекло режется по проёму; порядок слоя rooms;
  решение владельца 14.10.2026 (№104) — лифт внутри блока ядра, отрезанный помещением с номером, — одна грань ядра через тело массива (core_join)."""
import os, sys, math, tempfile, traceback, json
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'bridge'))
import numpy as np
import ezdxf
import bridge_convert as B
import bridge_graph as BG
import bridge_post as BP

def xdata(e, t):
    e.set_xdata('UNSPOT', [(1000, 'group=1'), (1000, f'type={t}')])

def make_dxf(path, unknown=False, with_xdata=True):
    doc = ezdxf.new(); doc.appids.add('UNSPOT'); msp = doc.modelspace()
    for L in ('A-222---H-', 'A-222---E-', 'A-32----E-', 'A-22G---E-', 'A-68----E-', 'A-31----E-', 'A-82----E-'): doc.layers.add(L)
    h = msp.add_hatch(dxfattribs={'layer': 'A-222---H-'}); h.paths.add_polyline_path([(0, 0), (6000, 0), (6000, 120), (0, 120)], is_closed=True)
    if with_xdata: xdata(h, 'wall_gkl')
    blk = doc.blocks.new('B0001_door'); blk.add_line((0, 0), (900, 0)); blk.add_arc((0, 0), 900, 0, 90)
    ins = msp.add_blockref('B0001_door', (2000, 60), dxfattribs={'layer': 'A-32----E-'})
    if with_xdata: xdata(ins, 'door')
    if with_xdata:
        r = msp.add_lwpolyline([(1950, 0), (2950, 0), (2950, 120), (1950, 120)], close=True, dxfattribs={'layer': 'A-32----E-'}); xdata(r, 'door')
    g = msp.add_lwpolyline([(0, 3000, 0), (3000, 3000, 0.5), (4000, 3500, 0)], format='xyb', dxfattribs={'layer': 'A-22G---E-'})
    if with_xdata: xdata(g, 'glass')
    c = msp.add_circle((5000, 5000), 400, dxfattribs={'layer': 'A-222---E-'})
    if with_xdata: xdata(c, 'wall_gkl')
    msp.add_text('ПК', dxfattribs={'layer': 'A-68----E-', 'height': 200, 'insert': (100, 2000)})
    if unknown:
        u = msp.add_line((0, 0), (10, 10), dxfattribs={'layer': 'A-82----E-'}); xdata(u, 'flux_capacitor')
    doc.saveas(path)

T = []
def test(f): T.append(f); return f

@test
def t_type_table():
    for t in ('door', 'mullion', 'facade', 'wall_cap', 'coreblock', 'coreline', 'glass', 'lpart', 'column', 'shaft', 'roomsep', 'desk', 'chair',
              'wallline', 'gklpart', 'glasspart', 'wcacc', 'booth', 'san', 'fire', 'tagc', 'dim'):
        assert t in B.TYPE_CLASS, t
    assert B.TYPE_CLASS['door'] == 'door' and B.TYPE_CLASS['mullion'] == 'fglass' and B.TYPE_CLASS['lpart'] == 'light' and B.TYPE_CLASS['desk'] == 'desk'

@test
def t_read_xdata():
    d = tempfile.mkdtemp(prefix='t_bridge_'); p = os.path.join(d, 'plan.dxf'); make_dxf(p)
    D = B.read_dxf(p)
    assert len(D['int']) == 1, 'стена SOLID — int'
    assert len(D['door']) == 1 and D['door'][0]['rect'] is not None, 'прямоугольник проёма — к блоку двери'
    assert len(D['door_rect']) == 1 and not D['door_misc'], D['door_misc']
    assert len(D['glass']) == 1, 'LWPOLYLINE type=glass — стекло, не лёгкая линия'
    assert any(c[0] == 'glass' and not c[6] for c in D['curves']), 'bulge стекла — кривой'
    assert any(c[0] == 'wall' and c[6] for c in D['curves']), 'CIRCLE стены — окружностью'
    assert len(D['pk']) == 1, '«ПК» со слоя 68 представления E'
    assert D['_unknown'] == [] and D['_xdata'].get('door') == 2

@test
def t_read_unknown():
    d = tempfile.mkdtemp(prefix='t_bridge_'); p = os.path.join(d, 'plan.dxf'); make_dxf(p, unknown=True)
    D = B.read_dxf(p)
    assert D['_unknown'] and D['_unknown'][0]['type'] == 'flux_capacitor', D['_unknown']

@test
def t_read_no_xdata():
    d = tempfile.mkdtemp(prefix='t_bridge_'); p = os.path.join(d, 'plan.dxf'); make_dxf(p, with_xdata=False)
    D = B.read_dxf(p)
    assert len(D['int']) == 1 and len(D['door']) == 1 and D['door'][0]['rect'] is None
    assert not D['glass'] and len(D['light']) == 1, 'без XDATA и без «стеклянн» в имени — лёгкая линия, как 0.32'
    assert D['_xdata'] == {} and D['_unknown'] == []

SVG = '''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 300">
<rect x="0" y="0" width="400" height="300" fill="#FFFFFF" stroke="none"/>
<g id="underlay" display="none"/>
<g id="rooms">
<path id="room-b-1-0" data-name="1" data-title="" data-type="other" d="M10 10 L110 10 L210 10 L210 110 L10 110 Z" fill="#FFFFFF" stroke="#CBD2D6" stroke-width="6"/>
<path id="room-b-2-1" data-name="2" data-title="" data-type="other" d="M210 10 L310 10 L310 110 L210 110 Z" fill="#FFFFFF" stroke="#CBD2D6" stroke-width="6"/>
<path id="door-b-0" data-type="door" data-kind="door" d="M240 107 L280 107 L280 113 L240 113 Z" fill="#FFFFFF" stroke="none"/>
</g>
<g id="glass">
<path id="glasswall-b-0" d="M220 110 L300 110" fill="none" stroke="#86C5FB" stroke-width="4"/>
</g>
<g id="furniture"/>
<g id="icons"/>
<g id="labels"/>
</svg>'''

@test
def t_model_roundtrip_and_collinear():
    M = BG.Model(SVG); assert len(list(M.els('room'))) == 2 and len(list(M.els('door'))) == 1
    n = BG.collinear(M, log=lambda s: None)
    assert n == 1 and len(M.get('room-b-1-0')['subs'][0]['pts']) == 4, 'вершина (110,10) на прямой — снята'
    out = M.to_svg(); M2 = BG.Model(out); assert len(list(M2.els('room'))) == 2

@test
def t_thin_rollback():
    s = SVG.replace('M10 10 L110 10 L210 10', 'M10 10 L110 13 L210 10')     # вершина в 3 px от прямой, рёбра длиннее 0,8 м при 100 px/м — не прореживается
    M = BG.Model(s); C = BG.Ctx(100.0, 6.0); n = BG.thin_deg2(M, C, log=lambda x: None); assert n == 0
    M = BG.Model(s); C = BG.Ctx(400.0, 6.0); n = BG.thin_deg2(M, C, log=lambda x: None); assert n == 1, 'ребро короче 0,8 м и смещение < T — снято'

@test
def t_cut_glass_and_zorder():
    M = BG.Model(SVG); BP.cut_glass(M, log=lambda x: None)
    g = M.get('glasswall-b-0'); xs = sorted(v[0] for s_ in g['subs'] for v in s_['pts'])
    assert len(g['subs']) == 2 and not any(240 < x < 280 for x in xs), 'стекло разрезано по проёму'
    s = SVG.replace('<path id="door-b-0"', '<path id="wall-b-9" d="M0 0 L5 0" fill="none" stroke="#CBD2D6" stroke-width="6"/>\n<path id="door-b-0"')
    s = s.replace('<path id="room-b-2-1"', '<path id="door-b-1" data-type="door" d="M1 1 L2 1 L2 2 L1 2 Z" fill="#FFFFFF"/>\n<path id="room-b-2-1"')
    M = BG.Model(s); BP.zorder(M, log=lambda x: None); kinds = [e['kind'] for e in M.groups['rooms'] if e['kind'] != 'raw']
    assert kinds == sorted(kinds, key=lambda k: {'room': 0, 'wall': 2, 'door': 3, 'column': 4}[k]), kinds

@test
def t_arcs():
    pts = [(100 + 50 * math.cos(math.radians(a)), 100 + 50 * math.sin(math.radians(a))) for a in range(0, 91, 10)]
    d = 'M' + ' L'.join(f'{x:.2f} {y:.2f}' for x, y in pts)
    s = SVG.replace('</g>\n<g id="glass">', f'<path id="wall-b-5" d="{d}" fill="none" stroke="#CBD2D6" stroke-width="6"/>\n</g>\n<g id="glass">')
    M = BG.Model(s); BP.arcs_apply(M, [dict(name='тест', c=(100.0, 100.0), r=50.0, span=(0.0, 90.0))], log=lambda x: None)
    w = M.get('wall-b-5')['subs'][0]; assert len(w['pts']) == 2 and len(w['arcs']) == 1, w
    assert 'A50' in BG.d_of([w])

@test
def t_circles_from_curves():
    M_ = np.array([[0.05, 0.0], [0.0, -0.05]]); t_ = np.array([0.0, 500.0])
    arcs = BP.circles_from_curves([('wall', 1000.0, 1000.0, 900.0, 0.0, 90.0, False), ('wall', 1000.0, 1000.0, 1100.0, 0.0, 90.0, False)], M_, t_, 50.0)
    assert len(arcs) == 1 and abs(arcs[0]['r'] - 50.0) < 1e-6, arcs      # ось — середина граней 0,9 и 1,1 м -> 1,0 м = 50 px

@test
def t_core_join_lift():
    """решение владельца 14.10.2026 (№104): лифт внутри блока ядра, отрезанный помещением с номером, вырезанным в массиве, — часть одной грани ядра:
    помещение отдаёт ядру тело массива (полосы штриховки), ядро — одна грань без кольца; помещение — по грани штриховки (сжатой на T/2)"""
    from shapely.geometry import Polygon, box
    Mp = box(0, 0, 100, 200).difference(box(15, 80, 100, 120))           # массив ядра буквой «С»: выемка под помещение открыта вправо
    lift, block, q = box(5, 5, 95, 75), box(5, 125, 95, 195), box(5, 75, 95, 125)   # грани графа по осям стен
    Mi = Mp.buffer(-3, join_style=2)                                      # T = 6
    j = B.core_join(block, lift, q, Mi)
    assert j is not None, 'лифт не соединён'
    core, q_new = j
    assert core.geom_type == 'Polygon' and not core.interiors and core.is_valid, core.wkt
    assert abs(core.area + q_new.area - (lift.area + block.area + q.area)) < 1.0, 'площади сохраняются'
    assert abs(q_new.area - (95 - 12) * (123 - 77)) < 1.0 and q_new.bounds[0] > 11, q_new.bounds
    assert core.intersection(q_new).area < 0.5, 'помещение с номером не внутри ядра'
    Mr = box(0, 0, 100, 200).difference(box(15, 80, 85, 120))            # выемка закрыта со всех сторон: тело массива в грани помещения — кольцо
    qr = box(5, 75, 95, 125)
    j2 = B.core_join(block, lift, qr, Mr.buffer(-3, join_style=2))
    assert j2 is None, 'тело массива вокруг помещения — одним кольцом: ядро помещение не обводит, лифт — «не_слито» в отчёте, грань — как была'
    j3 = B.core_join(block, lift, box(5, 75, 95, 125), box(200, 0, 300, 200))  # помещение не в массиве — не соединять
    assert j3 is None

if __name__ == '__main__':
    ok = 0
    for f in T:
        try: f(); ok += 1; print('ok  ', f.__name__)
        except Exception: print('FAIL', f.__name__); traceback.print_exc()
    print(f'ok {ok} из {len(T)}'); sys.exit(0 if ok == len(T) else 1)
