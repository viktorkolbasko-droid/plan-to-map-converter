# Vector extraction honouring PDF clip paths and painter's-order occlusion.
import pymupdf as fitz, pickle, math, time, numpy as np
import shapely
from shapely.geometry import Polygon, LineString, MultiLineString, MultiPolygon, GeometryCollection
from shapely.ops import unary_union
from shapely.strtree import STRtree
t0=time.time()
from common import PDF
pg=fitz.open(PDF)[0]; M=pg.rotation_matrix
def T(p): q=fitz.Point(p)*M; return (q.x,q.y)
def bez(p0,p1,p2,p3,n=10):
    return [((1-t)**3*p0[0]+3*(1-t)**2*t*p1[0]+3*(1-t)*t*t*p2[0]+t**3*p3[0],(1-t)**3*p0[1]+3*(1-t)**2*t*p1[1]+3*(1-t)*t*t*p2[1]+t**3*p3[1]) for t in np.linspace(0,1,n)]
def rings_of(items):
    rings=[]; cur=[]
    for it in items:
        t=it[0]
        if t=='re':
            r=it[1]; rings.append([T((r.x0,r.y0)),T((r.x1,r.y0)),T((r.x1,r.y1)),T((r.x0,r.y1))]); continue
        if t=='qu':
            q=it[1]; rings.append([T(q.ul),T(q.ur),T(q.lr),T(q.ll)]); continue
        seg=[T(it[1]),T(it[2])] if t=='l' else bez(T(it[1]),T(it[2]),T(it[3]),T(it[4]))
        if cur and math.dist(cur[-1],seg[0])<1e-3: cur.extend(seg[1:])
        else:
            if len(cur)>=3: rings.append(cur)
            cur=list(seg)
    if len(cur)>=3: rings.append(cur)
    return rings
def area_geom(items,even_odd):
    ps=[]
    for r in rings_of(items):
        p=Polygon(r)
        if not p.is_valid: p=p.buffer(0)
        if not p.is_empty and p.area>1e-6: ps.append(p)
    if not ps: return None
    if even_odd:
        g=ps[0]
        for p in ps[1:]: g=g.symmetric_difference(p)
    else: g=unary_union(ps)
    return g if not g.is_empty else None
def col(c): return tuple(round(v,2) for v in c) if c else None
dr=pg.get_drawings(extended=True)
clip=None
fills=[]   # (seq, geom, fc)
strokes=[] # (seq, kind, w, sc, geometry pts)
seq=0
for d in dr:
    if d['type']=='clip':
        clip=area_geom(d['items'],d.get('even_odd',True)); continue
    lvl=d.get('level',0)
    seq+=1
    if d['type'] in ('f','fs') and d.get('fill') is not None:
        g=area_geom(d['items'],d.get('even_odd',False))
        if g is not None:
            if lvl>=1 and clip is not None: g=g.intersection(clip)
            if not g.is_empty and g.area>1e-5: fills.append((seq,g,col(d['fill'])))
    if d['type'] in ('s','fs') and d.get('color') is not None:
        w=round(d.get('width') or 0,2); sc=col(d['color'])
        for it in d['items']:
            if it[0]=='l':
                a,b=T(it[1]),T(it[2])
                if math.dist(a,b)>=0.05: strokes.append((seq,'l',w,sc,[a,b]))
            elif it[0]=='c': strokes.append((seq,'c',w,sc,[T(it[1]),T(it[2]),T(it[3]),T(it[4])]))
            elif it[0]=='re':
                r=it[1]; q=[T((r.x0,r.y0)),T((r.x1,r.y0)),T((r.x1,r.y1)),T((r.x0,r.y1))]
                for a,b in zip(q,q[1:]+q[:1]): strokes.append((seq,'l',w,sc,[a,b]))
            elif it[0]=='qu':
                q=it[1]; q=[T(q.ul),T(q.ur),T(q.lr),T(q.ll)]
                for a,b in zip(q,q[1:]+q[:1]): strokes.append((seq,'l',w,sc,[a,b]))
print('fills',len(fills),'strokes',len(strokes),round(time.time()-t0,1),'s')
# ---- occlusion
fseq=np.array([f[0] for f in fills]); fgeo=[f[1] for f in fills]
fsh=[g.buffer(-0.04) for g in fgeo]          # shrink: lines lying on a fill edge stay visible
tree=STRtree(fsh)
sgeo=[LineString(s[4] if s[1]=='l' else bez(*s[4])) for s in strokes]
sseq=np.array([s[0] for s in strokes])
pairs=tree.query(sgeo,predicate='intersects')
occ={}
for si,fi in zip(*pairs):
    if fseq[fi]>sseq[si]: occ.setdefault(si,[]).append(fi)
print('strokes touched by later fills',len(occ))
prims=[]
nhid=0; ncut=0
for si,s in enumerate(strokes):
    seqi,kind,w,sc,g=s
    if si not in occ:
        prims.append((kind,w,sc,None,tuple(g),seqi)); continue
    cov=unary_union([fsh[fi] for fi in occ[si]])
    vis=sgeo[si].difference(cov)
    if vis.is_empty: nhid+=1; continue
    if vis.equals(sgeo[si]): prims.append((kind,w,sc,None,tuple(g),seqi)); continue
    ncut+=1
    parts=[vis] if vis.geom_type=='LineString' else [x for x in getattr(vis,'geoms',[]) if x.geom_type=='LineString']
    for ln in parts:
        c=list(ln.coords)
        for a,b in zip(c[:-1],c[1:]):
            if math.dist(a,b)>=0.05: prims.append(('l',w,sc,None,(a,b),seqi))
print('hidden strokes',nhid,'cut strokes',ncut)
HOLES={}
nf=0
for fi,(seqi,g,fc) in enumerate(fills):
    polys=[g] if g.geom_type=='Polygon' else [x for x in getattr(g,'geoms',[]) if x.geom_type=='Polygon']
    for j,p in enumerate(polys):
        if p.area<0.004: continue
        p=p.simplify(0.005)
        ext=list(p.exterior.coords)[:-1]
        if len(ext)<3: continue
        key=(seqi,j); holes=[list(h.coords)[:-1] for h in p.interiors if Polygon(h).area>0.004]
        if holes: HOLES[key]=holes
        prims.append(('qu',0,None,fc,tuple(ext),key)); nf+=1
print('visible fill polygons',nf,'with holes',len(HOLES))
# restore paint order
def sk(p): return p[5][0]+0.5 if isinstance(p[5],tuple) else p[5]
prims.sort(key=sk)
pickle.dump(prims,open('prims.pkl','wb')); pickle.dump(HOLES,open('holes.pkl','wb'))
pickle.dump((prims,[]),open('seq.pkl','wb'))
print('prims',len(prims),round(time.time()-t0,1),'s')
