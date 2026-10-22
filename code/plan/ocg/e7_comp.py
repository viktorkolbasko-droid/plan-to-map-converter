"""Э7 step 1: connected components of a layer's primitives (touching <= tol) -> comp ids, with simple stats."""
import pickle, numpy as np, collections, shapely, sys, time, math
from shapely.geometry import LineString, Polygon, Point
def geom(p):
    if p['kind'] == 'fill':
        g = Polygon(p['p'], p.get('holes', [])).buffer(0)
        return g if not g.is_empty else LineString(p['p'])
    if p['kind'] == 'wline': return LineString(p['p']).buffer(p['w'] / 2, cap_style=2)
    return LineString(p['p']) if len(p['p']) >= 2 else Point(p['p'][0])
def load_prims(skip=()):
    """primitives as classified: prims_r.pkl (Э7р glass bands, core blocks and furniture outlines regularized) > prims_k.pkl (Э7к classes: ПК, kitchens, stray lines) > prims_o.pkl (Э7о openings fitted to the walls) > prims_c.pkl (Э7я core) > prims_d.pkl (Э7д doors) > prims_j.pkl (Э7с joints) > prims_f.pkl (Э7м furniture) > prims_e7.pkl (with the pieces of split polylines, e7_objects.py) if present, else prims.pkl"""
    import os
    return pickle.load(open(next(f for f in ('prims_r.pkl', 'prims_k.pkl', 'prims_o.pkl', 'prims_c.pkl', 'prims_d.pkl', 'prims_j.pkl', 'prims_f.pkl', 'prims_e7.pkl', 'prims.pkl') if os.path.exists(f) and f not in skip), 'rb'))
def load_walls(skip=()):
    """wall bodies as exported: walls_r.pkl (Э7р: one type per wall, on the face lines) > walls_o.pkl (Э7о: cut in the fitted door openings) > walls_j.pkl (Э7с joints) > walls_e7.pkl (Э7: lines along bodies joined) > walls_geom.pkl (Э6г: doors, niches, joints) > walls_clean.pkl (Э6в) > walls.pkl (Э6)"""
    import os
    W = pickle.load(open(next(f for f in ('walls_r.pkl', 'walls_o.pkl', 'walls_j.pkl', 'walls_e7.pkl', 'walls_geom.pkl', 'walls_clean.pkl', 'walls.pkl') if os.path.exists(f) and f not in skip), 'rb'))
    W['bodies'] = [(c, q) for c, g in W['bodies'] for q in getattr(g, 'geoms', [g]) if q.geom_type == 'Polygon' and q.area > 0.05]
    return W
def components(ps, tol=0.05):
    G = [geom(p) for p in ps]; t = shapely.STRtree(G)
    par = list(range(len(G)))
    def f(a):
        while par[a] != a: par[a] = par[par[a]]; a = par[a]
        return a
    for i, g in enumerate(G):
        for j in t.query(g.buffer(tol)):
            if j > i and G[j].distance(g) <= tol: par[f(i)] = f(j)
    return [f(i) for i in range(len(G))], G
if __name__ == '__main__':
    t0 = time.time()
    P = pickle.load(open('prims.pkl', 'rb'))['P']; L = sys.argv[1]
    ps = [p for p in P if p['layer'] == L and len(p['p']) >= 1]
    cid, G = components(ps)
    cc = collections.Counter(cid); print(L, 'prims', len(ps), 'components', len(cc), round(time.time() - t0, 1), 's')
    sz = np.array(list(cc.values())); print('sizes p50/p90/p99/max', np.percentile(sz, [50, 90, 99]).round(), sz.max())
