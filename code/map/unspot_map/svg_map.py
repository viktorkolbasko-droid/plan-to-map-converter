"""Clean plan SVG by the canon (map/rules/05 §2, map/rules/70 §1; map/rules/82 §2; map/rules/70 §2.8-§2.9).

 * six groups in the dictionary order: underlay (empty, hidden) / rooms / glass / furniture / icons / labels;
 * literal hex, no transform / class / <image>, stroke set on every element;
 * a closed room = fill + stroke T centred on the shared axis; an open zone = fill only;
 * free walls = separate paths only where no closed room bounds the edge;
 * a door = rectangle (wall thickness + DOOR_EXTRA = 1 px) deep, T or T_EXT via doors[i]['depth'], in the colour of the coloured room (white between two white rooms);
 * a fully glazed facade = one blue path (no grey contour under it, owner 29.09); partition ends = grey
   rectangles on top of the glass; the inner half of the facade band is painted in room colours.
Colours and thicknesses are parameters: take them from the stage canon (map/00 §10), never from this file."""
import numpy as np
from shapely.geometry import Point, Polygon, LineString
from shapely.ops import unary_union, linemerge
from shapely import affinity

WALL = '#CBD2D6'; GLASS = '#86C5FB'
DOOR_EXTRA = 1.0   # a door is deeper than its wall by 1 px (0.5 px per side, anti-aliasing seam, map/rules/11 §12); acceptance Ch-19 uses the
                   # same value (acceptance_checks.OPENING_EXTRA): the opening counts as on the wall within 0.5 px of the wall body (АБ3, v007)


def fmt(v):
    return (f'{v:.1f}'.rstrip('0').rstrip('.')) if abs(v - round(v)) > 1e-9 else str(int(round(v)))


def ring_d(coords):
    """closed ring without zero-length edges after rounding (they count as short edges in the checks)"""
    pts = list(coords)
    if len(pts) > 1 and pts[0] == pts[-1]:
        pts = pts[:-1]
    txt = [f'{fmt(x)} {fmt(y)}' for x, y in pts]
    out = [t for i, t in enumerate(txt) if i == 0 or t != txt[i - 1]]
    if len(out) > 1 and out[-1] == out[0]:
        out = out[:-1]
    return 'M' + ' L'.join(out) + ' Z'


def line_d(coords):
    return 'M' + ' L'.join(f'{fmt(x)} {fmt(y)}' for x, y in coords)


def poly_d(g):
    parts = g.geoms if hasattr(g, 'geoms') else [g]; out = []
    for q in parts:
        if q.geom_type != 'Polygon' or q.is_empty:
            continue
        out.append(ring_d(q.exterior.coords)); out += [ring_d(r.coords) for r in q.interiors]
    return ' '.join(out)


def assemble(rooms, free_edges, doors, facade_ring, partitions, src_to_canvas, size,
             T=6.0, T_EXT=12.0, GLASS_W=8.0, closed_types=frozenset(), wall=WALL, glass=GLASS,
             simplify_tol=0.25, extra_groups=(), floor_id='f'):
    """rooms: dict(id, poly, type, colour, name) in the source frame; free_edges: LineStrings;
    doors: dict(line, colour); facade_ring: closed LineString (facade axis);
    partitions: interior wall lines of the graph (their ends on the facade get grey end rectangles);
    src_to_canvas: frame.Affine; size: (W, H) canvas px. Returns the SVG text."""
    S = src_to_canvas.scale(); A = src_to_canvas.shapely()
    tr = lambda g: affinity.affine_transform(g, A)
    W, H = size
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}">',
           f'<rect x="0" y="0" width="{W}" height="{H}" fill="#FFFFFF" stroke="none"/>',
           '<g id="underlay" display="none"/>', '<g id="rooms">']
    for r in sorted(rooms, key=lambda r: -r['poly'].area):
        P = tr(r['poly'].simplify(simplify_tol, preserve_topology=True))
        attrs = f'data-name="{r.get("name", "")}" data-type="{r["type"]}" d="{poly_d(P)}" fill="{r["colour"]}"'
        if r['type'] in closed_types:
            out.append(f'<path id="room-{floor_id}-{r["id"]}" {attrs} stroke="{wall}" stroke-width="{fmt(T)}" '
                       f'stroke-linejoin="miter" stroke-miterlimit="8"/>')
        else:
            out.append(f'<path id="room-{floor_id}-{r["id"]}" {attrs} stroke="none"/>')
    if free_edges:
        U = unary_union(free_edges); U = U if U.geom_type == 'LineString' else linemerge(U)
        for i, g in enumerate([U] if U.geom_type == 'LineString' else list(U.geoms)):
            out.append(f'<path id="wall-{floor_id}-{i}" d="{line_d(tr(g.simplify(simplify_tol)).coords)}" fill="none" '
                       f'stroke="{wall}" stroke-width="{fmt(T)}" stroke-linecap="square"/>')
    for i, d in enumerate(doors):
        rect = tr(d['line']).buffer((d.get('depth', T) + DOOR_EXTRA) / 2, cap_style=2, join_style=2)   # глубина — толщина своей стены: T или 2T (map/rules/60 §2.1)
        out.append(f'<path id="door-{floor_id}-{i}" d="{poly_d(rect)}" fill="{d["colour"]}" stroke="none"/>')
    out.append('</g>')
    # glass
    out.append('<g id="glass">')
    bld = Polygon(facade_ring.coords)
    band_in = bld.difference(bld.buffer(-(T_EXT / 2) / S, join_style=2))
    for r in rooms:
        b = r['poly'].intersection(band_in)
        if not b.is_empty and b.area > 0.05:
            out.append(f'<path d="{poly_d(tr(b.simplify(0.1)))}" fill="{r["colour"]}" stroke="none"/>')
    ring = bld.buffer((T_EXT / 2 - GLASS_W / 2) / S, join_style=2).exterior
    out.append(f'<path id="facade-glass-{floor_id}" d="{ring_d(tr(ring.simplify(0.2)).coords)}" fill="none" '
               f'stroke="{glass}" stroke-width="{fmt(GLASS_W)}" stroke-linejoin="round"/>')
    for L in partitions:
        if L.geom_type != 'LineString' or L.is_empty:
            continue
        for p in (Point(L.coords[0]), Point(L.coords[-1])):
            if facade_ring.distance(p) < 0.8:
                c = np.array(L.coords); q = c[1] if Point(*c[0]).equals_exact(p, 1e-6) else c[-2]
                u = np.array(p.coords[0]) - q; u = u / max(np.linalg.norm(u), 1e-9); P0 = np.array(p.coords[0])
                seg = LineString([tuple(P0 - u * (T_EXT / 2) / S), tuple(P0 + u * (T_EXT / 2) / S)])
                out.append(f'<path d="{poly_d(tr(seg).buffer(T / 2, cap_style=2, join_style=2))}" fill="{wall}" stroke="none"/>')
    out.append('</g>')
    out += list(extra_groups)
    out.append('</svg>')
    return '\n'.join(out)


PNG_TARGET_LONG = 4000      # v013 (К13.2; строка 390, №6; map/rules/82 §1, 80 Ч-28): новая карта — ≈ 4 000 px по большей стороне; больше — уменьшать,
                            # множитель = 4 000 / большая сторона холста, меньше 1× допустим (⛔ 15.10.2026: «не меньше 1×» и предел 10 000 px сняты)
PNG_MAX_MB = 5.0            # map/rules/82 §1 (П-103, П-245): файл ≤ 5 МБ — сверх него предупреждение, размер в пикселях не меняется


def svg_canvas(svg_path):
    """холст SVG (W, H) в px: viewBox, иначе width/height"""
    import re
    head = open(svg_path, 'rb').read(4096).decode('utf-8', 'replace')
    m = re.search(r'viewBox\s*=\s*["\']\s*([-\d.eE]+)[\s,]+([-\d.eE]+)[\s,]+([-\d.eE]+)[\s,]+([-\d.eE]+)', head)
    if m:
        return float(m[3]), float(m[4])
    w = re.search(r'\swidth\s*=\s*["\']([\d.]+)', head); h = re.search(r'\sheight\s*=\s*["\']([\d.]+)', head)
    if w and h:
        return float(w[1]), float(h[1])
    raise ValueError('у SVG нет viewBox и width/height — холст не определить: %s' % svg_path)


def export_scale(canvas, target=PNG_TARGET_LONG):
    """v013 (строка 390; map/rules/82 §1): множитель новой карты = target / большая сторона холста — и вверх, и вниз (меньше 1× допустим)"""
    return target / max(canvas)


def to_png(svg_path, png_path, scale=None, size=None, export_json=True):
    """v013 (К13.2; строка 390, №6; map/rules/82 §1; 80 Ч-28) — SVG -> PNG для UnSpot.
    * правка уже загруженной карты — size=(W, H) прежней выгрузки: PNG того же размера до пикселя (места UnSpot стоят по пикселям);
    * новая карта — scale=None: множитель export_scale = 4 000 / большая сторона холста (≈ 4 000 px по большей стороне; холст больше —
      уменьшение, множитель меньше 1× допустим); scale=k — множитель задан явно (большая сторона больше 4 000 px — «ВНИМАНИЕ»).
    Холст и SVG не меняются, уменьшается только картинка (№55). Файл больше 5 МБ — «ВНИМАНИЕ» (сжать без смены размера).
    Рядом пишет <png>.export.json: {"png", "w", "h", "scale", "canvas": [W, H], "mode": "new" | "edit", "prev_size": [W, H] | null, "bytes"}
    (+ "warnings" — только если есть: пропорции size не те, что у холста (ПК6-К4 б), явный множитель больше 4 000 px, файл > 5 МБ)
    — Ш×В и множитель для паспорта клиента; печатает их же. Совместимо с v011: to_png(svg, png, (W, H)) — то же, что size=(W, H).
    -> словарь export.json"""
    import cairosvg, json, os
    if isinstance(scale, (tuple, list)) and size is None:      # вызов v011: to_png(svg, png, (W, H))
        scale, size = None, scale
    cw, ch = svg_canvas(svg_path); warn = []
    if size is not None:
        W, H = int(size[0]), int(size[1]); mode, k = 'edit', W / cw
        if max(W, H) > PNG_TARGET_LONG:
            print('to_png: размер прежней выгрузки %d × %d больше %d px по большей стороне: размер не меняю (правка — до пикселя, 82 §1)' % (W, H, PNG_TARGET_LONG))
        h_k = W * ch / cw                                         # ПК6-К4 (б): пропорции size против холста — расхождение больше 2 px искажает PNG
        if abs(H - h_k) > 2:
            warn.append('пропорции размера прежней выгрузки %d × %d не те, что у холста %s × %s (при ширине %d высота %.0f px, расхождение %.1f %%): '
                        'PNG будет искажён — проверить холст и размер прежней выгрузки, сказать менеджеру' % (W, H, format(cw, 'g'), format(ch, 'g'), W, h_k, 100 * (H / h_k - 1)))
    else:
        k = export_scale((cw, ch)) if scale is None else float(scale)
        W, H = max(1, int(round(cw * k))), max(1, int(round(ch * k))); mode = 'new'
        if scale is not None and max(W, H) > PNG_TARGET_LONG:     # 82 §1: картинка больше ≈ 4 000 px — уменьшать; явный множитель — громко
            warn.append('явный множитель ×%s даёт %d × %d px — больше %d px по большей стороне: новую карту уменьшать до ≈ %d px (82 §1, строка 390)'
                        % (format(k, '.3f'), W, H, PNG_TARGET_LONG, PNG_TARGET_LONG))
    for w_ in warn:
        print('to_png: ВНИМАНИЕ — ' + w_)
    cairosvg.svg2png(url=svg_path, write_to=png_path, output_width=W, output_height=H)
    from PIL import Image
    w_, h_ = Image.open(png_path).size
    if (w_, h_) != (W, H):
        raise RuntimeError('to_png: PNG %d × %d вместо %d × %d — размер не тот, выгрузку не сдавать' % (w_, h_, W, H))
    rec = dict(png=os.path.basename(png_path), w=W, h=H, scale=round(k, 4), canvas=[round(cw, 2), round(ch, 2)], mode=mode,
               prev_size=[W, H] if mode == 'edit' else None, bytes=os.path.getsize(png_path))
    mb = rec['bytes'] / 1e6
    if mb > PNG_MAX_MB:
        warn.append('файл %.2f МБ больше %g МБ — сжать без смены размера в пикселях (82 §1)' % (mb, PNG_MAX_MB)); print('to_png: ВНИМАНИЕ — ' + warn[-1])
    if warn: rec['warnings'] = warn                               # ПК6-К4: только при предупреждении — ключи контракта не меняются
    print('to_png: %s — %d × %d px, множитель %s (%s), холст %s × %s, %.2f МБ%s' % (rec['png'], W, H, format(k, '.3f'), 'правка: размер прежней выгрузки' if mode == 'edit' else 'новая карта',
          rec['canvas'][0], rec['canvas'][1], mb, '; БОЛЬШЕ 5 МБ — сжать без смены размера (map/rules/82 §1)' if mb > PNG_MAX_MB else ''))
    if export_json:
        json.dump(rec, open(png_path + '.export.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    return rec
