"""Room type by the furniture of the sheet - the owner's rule (rows 176-177, 05.10.2026; map/rules/50 §1, §2; code v008, package 2).

For a room that by its other features looks both like a meeting room and like an office: a table, large or small, with two or more
seats - chairs or armchairs of the sheet - is a meeting room ('meeting'); empty, or a table-like figure without seats - a personal office
('office') by default. Copy rooms ('print') and technical rooms ('technical') have their own type: the rule does not touch them (row 177).
Rooms with workplaces of the places JSON are work rooms, not 'meeting or office': the rule does not touch them either.
Meeting furniture is not drawn on the map (No 50): the decision comes from the SHEET chairs (unspot_map.chairs), never from the map layer.

    from unspot_map.room_types import by_furniture
    rep = by_furniture(rooms, chairs_xy, seats_xy, px_per_m)       # rooms: [dict(id, poly, type, name)] in the frame of the chairs
    for r in rep: ...  r['new'] in ('meeting', 'office', None)      # None - one chair: not decided, a question to the card

Acceptance: Ch-39 (acceptance_checks.py --chairs-json) recomputes the same rule by its own code and lists every room whose map type
disagrees - look, frame K-06. Thresholds: 2 seats (owner's words 'several seats'); a chair within 0.6 m of a place point is that
place's chair, not the room's furniture (map/rules/80 Ch-31)."""
import re
from shapely.geometry import Point

KEEP = re.compile(r'print|copy|копир|печат|technical|техн', re.I)      # own type (row 177)
ASK = re.compile(r'^(meeting|office|cabinet|other|room)?$', re.I)        # 'looks like both' - typed so, or untyped


def by_furniture(rooms, chairs, seats, px_per_m, reach_m=0.6, min_seats=2):
    seats = [tuple(s) for s in seats]; out = []
    free = [c for c in chairs if not any((c[0] - s[0]) ** 2 + (c[1] - s[1]) ** 2 <= (reach_m * px_per_m) ** 2 for s in seats)]
    for r in rooms:
        t = (r.get('type') or '').strip(); nm = r.get('name') or ''
        if KEEP.search(f'{t} {nm}') or not (ASK.match(t) or re.search(r'переговор|кабинет', nm, re.I)): continue
        g = r['poly']
        if any(g.contains(Point(s)) for s in seats): continue               # work room with places
        n = sum(1 for c in free if g.contains(Point(c)))
        new = 'meeting' if n >= min_seats else 'office' if n == 0 else None
        out.append(dict(id=r.get('id'), name=nm, old=t, new=new, chairs=n,
                        why=f'стульев листа {n}: ' + ('стол с местами — переговорная' if new == 'meeting' else 'пусто — личный кабинет' if new == 'office' else 'один стул — не решено, вопрос в карточку')))
    return out


def apply(rooms, report):
    """set the decided type on the rooms (dicts of the drawing pipeline); returns the number of rooms whose type changed"""
    by = {r['id']: r for r in report if r['new']}; n = 0
    for r in rooms:
        x = by.get(r.get('id'))
        if x and r.get('type') != x['new']: r['type'] = x['new']; n += 1
    return n
