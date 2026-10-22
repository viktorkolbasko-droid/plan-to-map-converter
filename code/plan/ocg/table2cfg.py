# ocg/table2cfg.py - code 009: a sheet's layer table (JSON of plan/00, step 1: layer -> part -> class -> key -> ISO layer,
#   made by the render of every layer alone, e2_inventory.py) -> the block OCG_LAYERS of the floor's cfg.py.
#   The role of each layer (ocg/sheet.py ROLES) is guessed from the keys and classes of its rows; a layer whose role the
#   tool cannot tell gets role=None, and the first step of the route (start_ocg.py) stops on it until the operator sets it.
#   A row naming several layers ('A; …B; …C') is split: every layer gets the row.
#   python3 table2cfg.py <table.json> [roles.json]      roles.json - {layer: role} set by the operator, wins over the guess
#   prints the cfg block to stdout; code 012 (СП-4 п. 3): before the records of each layer - a comment with the sign the role
#   was chosen by (key -> BY_KEY, first row of the core, word of the facade class, roles.json), the same lines to stderr
import json, sys, re

BY_KEY = {'column': 'core', 'cap': 'core', 'coreline': 'core', 'gkl': 'wall', 'blk': 'wall', 'gkl / blk': 'wall', 'glass': 'wall',
          'lpart': 'wall', 'shaft': 'shaft', 'lift': 'lift', 'door': 'door', 'conv': 'heating', 'fire': 'fire', 'equip': 'equipment',
          'desk': 'furniture', 'chair / furn': 'furniture', 'chair': 'furniture', 'furn': 'furniture', 'mfp': 'furniture',
          'booth': 'furniture', 'plant': 'plant', 'san': 'sanitary', 'sink': 'sink', 'tagc': 'tag', 'zone': 'zone',
          'roomsep': 'roomsep', 'dim': 'dim', 'axis': 'axis', 'mark': 'mark', 'measure': 'measure', 'text': 'text', None: 'empty'}


def guess(rows):
    return guess_why(rows)[0]


def guess_why(rows):
    """the role of a layer and the sign it was chosen by (code 012, СП-4 п. 3): (role or None, why)"""
    keys = [r.get('ключ') for r in rows]
    if set(keys) & {'corezone', 'counter'}:          # the core hatch and its counters, or the lines of the core blocks
        first = keys[0]
        role = 'core_hatch' if first == 'corezone' else ('core_lines' if first == 'counter' else None)
        return role, (f'ключи {keys}: первая строка — {first!r} -> {role}' if role else f'ключи {keys}: corezone/counter не первой строкой — роль не выводится')
    if 'facade' in keys:
        cls = ' '.join(r.get('класс') or '' for r in rows).lower()
        role = 'facade_frame' if 'рам' in cls else ('facade_glass' if 'остекл' in cls else None)
        return role, (f'ключ facade, в классе «{"рам" if role == "facade_frame" else "остекл"}» -> {role}' if role else 'ключ facade, в классе нет «рам»/«остекл» — роль не выводится')
    roles = {BY_KEY.get(k) for k in keys}
    if len(roles) == 1:
        role = next(iter(roles))
        if role is None: return None, f'ключ(и) {sorted(set(map(str, keys)))} нет в словаре BY_KEY — роль не выводится'
        return role, f'ключ(и) {sorted(set(map(str, keys)))} -> {role} (BY_KEY)'
    return None, f'ключи {sorted(set(map(str, keys)))} дают разные роли {sorted(map(str, roles))} — одна роль на слой, задать в roles.json'


def main():
    T = json.load(open(sys.argv[1], encoding='utf-8')); roles = json.load(open(sys.argv[2], encoding='utf-8')) if len(sys.argv) > 2 else {}
    pre = (T.get('исходник') or {}).get('префикс_имён_слоёв', '')
    rows = {}
    for r in T['слои']:
        prev = None
        for name in re.split(r';\s*', r['слой']):
            name = name.strip()
            if name.startswith('…') and prev: name = prev[:prev.rfind('$') + 1] + name[1:]     # «…LDCar-AM_0»: the prefix of the name before
            elif pre and not name.startswith(pre): continue                                  # a note in the cell, not a layer
            prev = name
            name = name[len(pre):] if pre and name.startswith(pre) else name
            rows.setdefault(name, []).append(r)
    print('OCG_LAYER_PREFIX = %r' % pre)
    print('OCG_LAYERS = [   # the sheet\'s layer table (ocg/sheet.py): layer without the prefix, role of the route, class rows of the table')
    why_all = []
    for name, rs in rows.items():
        g, why = guess_why(rs)
        role = roles.get(name, g)
        if name in roles: why = f'roles.json оператора -> {roles[name]}' + (f' (по ключам было бы {g})' if g != roles[name] else '')
        why_all.append((name, role, why))
        print('    # «%s»: роль %r — признак: %s' % (name, role, why))
        for r in rs:
            print('    dict(layer=%r, role=%r, part=%r, cls=%r, key=%r, iso=%r),' % (name, role, r.get('часть'), r.get('класс'), r.get('ключ'), r.get('слой_iso')))
    print(']')
    # code 012 (СП-4 п. 3): the sign of every role also to stderr - the operator reads it before start_ocg.py checks the content
    for name, role, why in why_all: print(f'роль слоя «{name}»: {role!r} — {why}', file=sys.stderr)


if __name__ == '__main__':
    main()
