# how exactly do wall outlines follow the source PDF lines?
# (01.10.2026, test of floor 5, T11) p95 by the number of edges grew 1.0 -> 3.78 mm with a better geometry: the 70 edges
#   of false slivers in door openings lay on lines and left the denominator. Now also p95 / p99 by edge length and the
#   length of edges > 0.5 mm off the lines; the bodies the operator drew (cfg.WALL_ADD, cfg.WALL_ZONES) - a line of
#   their own, as in check 3.12: the source has no lines for them (floor 5: the top of the lift-core wall, 236 mm).
from common import *
import numpy as np, json
from shapely.geometry import LineString, Point, box as sbox, Polygon
from shapely.strtree import STRtree
from shapely.ops import unary_union
P=load(); cls=pickle.load(open('cls.pkl','rb'))
w=pickle.load(open(walls_file(),'rb'))['Wpt']
L=[LineString(list(p[4]) if p[0]=='l' else bez(p[4],12)) for i,p in enumerate(P) if p[0] in ('l','c') and cls[i] not in ('sheet',)]
tr=STRtree(L)
def _zone(z):
    if len(z)==4 and all(isinstance(v,(int,float)) for v in z): return sbox(*z)
    return LineString(z[0]).buffer(z[1],cap_style=2)
OPZ=unary_union([Polygon(a['poly']).buffer(0.3) for a in getattr(cfg,'WALL_ADD',[])]+[_zone(z['zone']).buffer(0.3) for z in getattr(cfg,'WALL_ZONES',[])])
d=[]; lens=[]; offlen=0; totlen=0; off05=0.0; dop=[]; lop=[]
for k,v in w.items():
    for pg_ in v:
      # (30.09.2026) geomfix.py may leave a MultiPolygon (a body split by the class-overlap cut): judge each part
      for pg in (list(pg_.geoms) if pg_.geom_type=='MultiPolygon' else [pg_]):
        for ring in [pg.exterior]+list(pg.interiors):
            c=list(ring.coords)
            for a,b in zip(c[:-1],c[1:]):
                seg=LineString([a,b]); m=seg.interpolate(0.5,normalized=True)
                j=tr.nearest(m); dd=L[j].distance(m)
                if not OPZ.is_empty and OPZ.contains(seg): dop.append(dd); lop.append(seg.length); continue
                d.append(dd); lens.append(seg.length); totlen+=seg.length
                if dd>0.1: offlen+=seg.length
                if dd*MM_PER_PT>0.5: off05+=seg.length
d=np.array(d)*MM_PER_PT; lens=np.array(lens)
def wpct(x,wt,q):
    if not len(x): return 0.0
    o=np.argsort(x); cw=np.cumsum(wt[o]); return float(x[o][np.searchsorted(cw,q/100*cw[-1])])
R=dict(edges=len(d),median_mm=round(float(np.median(d)),3),p95_mm=round(float(np.percentile(d,95)),2),max_mm=round(float(d.max()),1),
       share_len_on_source_lines=round(1-offlen/totlen,4),
       p95_by_length_mm=round(wpct(d,lens,95),2),p99_by_length_mm=round(wpct(d,lens,99),2),
       len_off_05mm_mm=round(off05*MM_PER_PT),
       operator_bodies=dict(edges=len(dop),len_mm=round(sum(lop)*MM_PER_PT),max_mm=round(max(dop)*MM_PER_PT,1) if dop else 0.0))
print(R); json.dump(R,open('fidelity.json','w'))
