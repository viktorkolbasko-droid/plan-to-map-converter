# table of the pairwise floor comparison (crossfloor.json) for plan/rules/60 §11 and the pass report
import json, sys
J = json.load(open(sys.argv[1]))
N = {'f1': '1', 'f2': '2', 'f3b': '3', 'f4r': '4', 'f5r': '5', 'f6': '6'}
def c(x): return str(x).replace('.', ',').replace('-', '−')
# (30.09.2026) the verdict "draws thick lines only" is gone (owner: internal glazing, plan/rules/60 §11): three columns -
#   the same wall shifted <= 300 mm, glazing instead of the wall, another layout; "same wall" no longer sums the shifted one
rows = ["| Пара | Общая область, м² | Совмещение: сдвиг, мм; масштаб; совпало ≤ 100 мм | Капитальные: IoU | Одинаково, контур ≤ 120 мм, м² | Класс другой, м² | Пропущено (штриховка есть), м² | Та же стена со сдвигом ≤ 300 мм, м² | Остекление вместо стены, м² | Другая планировка, м² | Листы различаются, м² | Витраж совпал | Колонны | Двери в капитальных |",
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
for k, v in J['pairs'].items():
    a, b = k.split('-')
    if 'cap_iou' not in v:
        rows.append(f"| {N[a]}–{N[b]} | {c(v['overlap_m2'])} | — | не сравнивается: общая область < 20 м² | | | | | | | | | | |"); continue
    r = v['registration']; vm = v.get('verdicts_m2', {})
    def s_(pref): return c(round(sum(x for kk, x in vm.items() if kk.startswith(pref)), 2))
    miss = sum(x for kk, x in vm.items() if kk.startswith('missed'))
    miss_s = ', '.join(f"{c(x)} на {N[a] if 'on A' in kk else N[b]}" for kk, x in vm.items() if kk.startswith('missed')) or '0'
    def side_(pref):
        return ', '.join(f"{c(x)} на {N[a] if any(t in kk for t in (' on A', ' of A', ': A ')) else N[b]}" for kk, x in sorted(vm.items()) if kk.startswith(pref)) or '0'
    sh = f"{c(round(r['tx']))}, {c(round(r['ty']))}; {c(r['s'])}; {c(r.get('share_within_100mm'))} / {c(r.get('share_other_side'))}" + (' (через общий кадр)' if r.get('via') else '')
    g = v.get('glazing_matched_share'); g = f"{c(g[0])} / {c(g[1])}" if g else '—'
    col = v.get('columns'); col = f"{col['matched']} из {col['n'][0]} / {col['n'][1]}" if col else '—'
    dr = v.get('doors_in_capital_walls'); dr = f"{dr['matched_within_300mm']} из {dr['n'][0]} / {dr['n'][1]}" if dr else '—'
    rows.append(f"| {N[a]}–{N[b]} | {c(v['overlap_m2'])} | {sh} | {c(v['cap_iou'])} | {s_('same wall, outline')} | {s_('class differs')} | {miss_s} | {side_('same wall on')} | {side_('glazing on')} | {side_('layouts differ')} | {s_('sheets differ')} | {g} | {col} | {dr} |")
print('\n'.join(rows))
