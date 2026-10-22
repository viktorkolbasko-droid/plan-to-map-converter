# Trace a facade line (plan/rules/20 §3.1) from the glazing panels: fills of one colour, long and thin; for each panel the
# long edge nearer the building centre is taken, edges are chained from a start point by nearest endpoint.
# Usage: python3 facade_trace.py PDF r,g,b minL maxL minW maxW cx,cy x0,y0[,x1,y1 box]  -> prints the polyline (pt)
import sys, math, pymupdf as fitz
from shapely.geometry import Polygon
pdf=sys.argv[1]; col=tuple(float(v) for v in sys.argv[2].split(','))
minL,maxL,minW,maxW=map(float,sys.argv[3:7]); C=tuple(float(v) for v in sys.argv[7].split(','))
st=[float(v) for v in sys.argv[8].split(',')]; BOX=[float(v) for v in sys.argv[9].split(',')] if len(sys.argv)>9 else None
d=fitz.open(pdf); p=d[0]; M=p.rotation_matrix
E=[]
for dr in p.get_drawings():
    f=dr.get('fill')
    if not f or max(abs(f[j]-col[j]) for j in range(3))>0.006: continue
    for it in dr['items']:
        if it[0]=='re': r=it[1]; q=[r.tl*M,r.tr*M,r.br*M,r.bl*M]
        elif it[0]=='qu': qq=it[1]; q=[qq.ul*M,qq.ur*M,qq.lr*M,qq.ll*M]
        else: continue
        g=Polygon([(v.x,v.y) for v in q]).buffer(0)
        if g.is_empty: continue
        if BOX and not (BOX[0]<=g.centroid.x<=BOX[2] and BOX[1]<=g.centroid.y<=BOX[3]): continue
        rr=g.minimum_rotated_rectangle; xy=list(rr.exterior.coords)[:4]
        ed=[(xy[k],xy[(k+1)%4]) for k in range(4)]; L=[math.dist(a,b) for a,b in ed]
        if not (minL<=max(L)<=maxL and minW<=min(L)<=maxW): continue
        lo=[ed[k] for k in range(4) if L[k]>=max(L)-0.01]
        E.append(min(lo,key=lambda s: math.dist(((s[0][0]+s[1][0])/2,(s[0][1]+s[1][1])/2),C)))
print('panels',len(E))
# chain
cur=(st[0],st[1]); used=set(); out=[]
while True:
    best=None
    for k,(a,b) in enumerate(E):
        if k in used: continue
        for u,v in ((a,b),(b,a)):
            dd=math.dist(cur,u)
            if best is None or dd<best[0]: best=(dd,k,u,v)
    if best is None or best[0]>25: break
    _,k,u,v=best; used.add(k)
    if not out or math.dist(out[-1],u)>1.5: out.append(u)
    out.append(v); cur=v
print('chained',len(used),'of',len(E))
print([(round(x,2),round(y,2)) for x,y in out])
