# Wall bodies to DXF (plan/rules/50 §3): outline on the E layer, solid grey poche and the material pattern on the H layer.
WL = {'ext': 'A-21----E-', 'cap': 'A-221---E-', 'gkl': 'A-222---E-', 'blk': 'A-223---E-'}
PAT = {'ext': ('ANSI31', 3.0), 'cap': ('ANSI31', 3.0), 'gkl': ('ANSI37', 2.0), 'blk': ('ANSI32', 3.0)}
WFILL = {'ext': (150, 150, 150), 'cap': (185, 185, 185), 'gkl': (215, 215, 215), 'blk': (205, 196, 180)}
WALL_LAYERS = set(WL.values()) | {v[:-2] + 'H-' for v in WL.values()}


def write_walls(msp, WALLS):
    stats = {}
    for k, ps in WALLS.items():
        lay = WL[k]; hl = lay[:-2] + 'H-'; n = 0; per = 0
        for pg in ps:
            for g in ([pg] if pg.geom_type == 'Polygon' else pg.geoms):
                n += 1; per += g.length
                rings = [list(g.exterior.coords)] + [list(h.coords) for h in g.interiors]
                for r in rings: msp.add_lwpolyline(r, close=True, dxfattribs={'layer': lay})
                # solid grey poche under the pattern (cut walls are filled), then the material pattern
                hs = msp.add_hatch(dxfattribs={'layer': hl}); hs.set_solid_fill(); hs.rgb = WFILL[k]
                hs.paths.add_polyline_path(rings[0], is_closed=True, flags=1)
                for r in rings[1:]: hs.paths.add_polyline_path(r, is_closed=True, flags=0)
                h = msp.add_hatch(dxfattribs={'layer': hl})
                h.set_pattern_fill(PAT[k][0], scale=PAT[k][1] * 20)
                h.paths.add_polyline_path(rings[0], is_closed=True, flags=1)
                for r in rings[1:]: h.paths.add_polyline_path(r, is_closed=True, flags=0)
        stats[k] = dict(n=n, len_m=round(per / 2 / 1000, 1))
    return stats
