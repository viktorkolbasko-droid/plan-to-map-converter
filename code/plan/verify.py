from common import *
import json, collections, importlib, ezdxf
from shapely.geometry import Point, LineString, Polygon
from shapely.ops import unary_union, nearest_points
P=load(); cls=pickle.load(open('cls.pkl','rb'))
inst=pickle.load(open('inst_final.pkl','rb'))
WALLS=pickle.load(open(walls_file(),'rb'))['W']
R={}
allw=[g for k,v in WALLS.items() for g in v]
R['walls_valid']=all(g.is_valid for g in allw)
U=unary_union(allw)
R['wall_parts_after_union']=len(U.geoms) if U.geom_type=='MultiPolygon' else 1
# carriers: walls + light partitions + facade prims as lines (mm)
def lines_of(key):
    ls=[]
    for q in inst:
        if q['key'] in (key if isinstance(key,tuple) else (key,)):
            for i in q['prims']:
                if P[i][0]=='l': ls.append(LineString([MM(P[i][4][0]),MM(P[i][4][1])]))
    return ls
carrier=unary_union(allw+[l.buffer(20) for l in lines_of(('lpart','lpartc','gklpart','glasspart','railing','glass'))+lines_of('facade')])
colz=unary_union([Point(q['ins']).buffer(450) for q in inst if q['key']=='column' and q.get('ins')])
# doors
dres=[]
for q in inst:
    if q['key']!='door': continue
    Hh=Point(q['hinge_mm']); A=Point(q['closed_mm'])
    dh=carrier.distance(Hh); da=carrier.distance(A)
    dres.append(dict(name=q['name'],hinge_mm=[round(Hh.x),round(Hh.y)],d_hinge=round(dh),d_jamb=round(da),ok=bool((dh<=150 and da<=150) or (q.get('pair') and dh<=150)),pair=bool(q.get('pair'))))
R['doors_total']=len(dres); R['doors_with_both_jambs_on_carrier']=sum(d['ok'] for d in dres)
R['doors_problem']=[d for d in dres if not d['ok']]
# gaps between wall pieces without an opening
parts=list(U.geoms) if U.geom_type=='MultiPolygon' else [U]
doorpts=[Point(MM(q['door']['c'])) for q in inst if q['key']=='door']+[Point(q['ins']) for q in inst if q['key'] in ('door45',)]
gaps=[]
for i in range(len(parts)):
    for j in range(i+1,len(parts)):
        dd=parts[i].distance(parts[j])
        if 1.0<dd<1100:
            a,b=nearest_points(parts[i],parts[j]); mid=Point((a.x+b.x)/2,(a.y+b.y)/2)
            near_door=min((mid.distance(p) for p in doorpts),default=1e9)<1300
            near_door=near_door or any(Point(q['ins']).distance(mid)<3000 for q in inst if q['key']=='lift' and q.get('ins'))
            near_carrier=carrier.difference(parts[i].buffer(1)).difference(parts[j].buffer(1)).distance(mid)<60 or colz.distance(mid)<60
            gaps.append(dict(gap_mm=round(dd),at_mm=[round(mid.x),round(mid.y)],door_near=near_door,other_element=near_carrier))
R['wall_gaps_lt_1100mm']=len(gaps); R['bridged_gaps']=pickle.load(open(walls_file(),'rb')).get('bridges')
R['wall_gaps_unexplained']=[g for g in gaps if not g['door_near'] and not g['other_element']]
# facade coverage
fac=unary_union([l.buffer(700) for l in lines_of('facade')]+[Point(q['ins']).buffer(1500) for q in inst if q['key']=='convector']+allw)
_fls=[LineString([MM(p) for p in f]) for f in FACADES]
_tot=sum(f.length for f in _fls) or 1
R['facade_path_len_m']=round(_tot/1000,1); R['facade_covered_share']=round(sum(f.intersection(fac).length for f in _fls)/_tot,3) if _fls else None
# coverage of source prims
src=[i for i,c in enumerate(cls) if c in ('obj','wall') and not (P[i][0]=='qu' and P[i][3]==(1.0,1.0,1.0))]
owner={}
for q in inst:
    for i in q['prims']: owner[i]=q['key']
wallset=set(i for i,c in enumerate(cls) if c=='wall')
import os as _os
if _os.path.exists('wallprims.pkl'): wallset|=set(pickle.load(open('wallprims.pkl','rb')))   # prims inside the vector walls
cnt=collections.Counter()
for i in src:
    k='wall' if i in wallset else owner.get(i,'NONE')
    cnt['misc' if k=='misc' else ('none' if k=='NONE' else 'classified')]+=1
R['source_prims']=len(src); R['coverage']=dict(cnt); R['classified_share']=round(cnt['classified']/len(src),4)
misc_bb=[]
for q in inst:
    if q['key']=='misc' and len(q['prims'])>30:
        ps=[MM(p) for i in q['prims'] for p in pts(P[i])]
        misc_bb.append(dict(n=len(q['prims']),bbox_mm=[round(min(p[0] for p in ps)),round(min(p[1] for p in ps)),round(max(p[0] for p in ps)),round(max(p[1] for p in ps))]))
R['misc_big']=misc_bb
# chairs vs places
R['chairs_office']=sum(1 for q in inst if q['key']=='chair')
R['desk_places']=sum(q.get('places',0) for q in inst if q['key']=='desk')
# DXF sanity
doc=ezdxf.readfile(DXF)
aud=doc.audit(); R['dxf_audit_errors']=len(aud.errors); R['dxf_layers']=len(doc.layers); R['dxf_blocks']=len([b for b in doc.blocks if not b.name.startswith('*')])
# (code 008, Т4-13, Т4-14) layers without a record or a description, texts off '...T-' / '...D-' (gate S14*)
from layers8 import dxf_layers as _dxf_layers
R['dxf_layer_check']=_dxf_layers(doc)
R['dxf_inserts']=len(doc.modelspace().query('INSERT'))
json.dump(R,open('verify.json','w'),ensure_ascii=False,indent=1)
for k,v in R.items():
    if isinstance(v,list): print(k,len(v), v[:6])
    else: print(k,v)
R['facade_ends_to_wall_mm']=[[round(U.distance(Point(MM(f[0])))),round(U.distance(Point(MM(f[-1]))))] for f in FACADES]
lay=collections.Counter(); 
for e in doc.modelspace().query('INSERT'): lay[e.dxf.layer]+=1
R['inserts_by_layer']=dict(sorted(lay.items()))
json.dump(R,open('verify.json','w'),ensure_ascii=False,indent=1)
print('facade ends',R['facade_ends_to_wall_mm']); print(R['inserts_by_layer'])

# X / V pattern strokes outside the final walls (45/135 deg pairs crossing or meeting at 90 deg): a cluster of 4+
#   is a partition band that was not recognised as a wall (floor 4: plants over the planter along a partition).
def _xv_clusters():
    from shapely.strtree import STRtree as _T
    from shapely.prepared import prep as _prep
    from scipy.spatial import cKDTree as _K
    _own={}
    for q in inst:
        for i in q['prims']: _own[i]=q['key']
    WPT=pickle.load(open(walls_file(),'rb'))['Wpt']
    WU=_prep(unary_union([g for v in WPT.values() for g in v]).buffer(0.3))
    ang=lambda a,b: math.degrees(math.atan2(b[1]-a[1],b[0]-a[0]))%180
    C=[]
    for i,p in enumerate(P):
        if p[0]!='l': continue
        a,b=p[4]; L=math.dist(a,b); t=ang(a,b)
        if not (0.5<=L<=8) or min(abs(t-45),abs(t-135))>2: continue
        col=p[2]
        if not (col and abs(col[0]-col[1])<0.02 and abs(col[1]-col[2])<0.02 and col[0]<=0.85): continue
        if WU.contains(Point((a[0]+b[0])/2,(a[1]+b[1])/2)): continue
        if _own.get(i) in ('chair','wc','sink','stool','desk','door','convector','tag','cafe','rdoor','column'): continue
        C.append(i)
    if not C: return []
    Gc=[LineString(P[i][4]) for i in C]; tr=_T(Gc); xs=set()
    for k,i in enumerate(C):
        a,b=P[i][4]; t=ang(a,b)
        for j in tr.query(Gc[k].buffer(0.08)):
            if j==k: continue
            a2,b2=P[C[j]][4]
            if abs(((t-ang(a2,b2))+90)%180-90)<80: continue
            if Gc[k].crosses(Gc[j]) or min(math.dist(e,f) for e in (a,b) for f in (a2,b2))<=0.08: xs.add(k); xs.add(j)
    ids=sorted(xs); pts_=np.array([((P[C[k]][4][0][0]+P[C[k]][4][1][0])/2,(P[C[k]][4][0][1]+P[C[k]][4][1][1])/2) for k in ids])
    par=list(range(len(ids)))
    def f(x):
        while par[x]!=x: par[x]=par[par[x]]; x=par[x]
        return x
    for a_,b_ in _K(pts_).query_pairs(4.0): par[f(a_)]=f(b_)
    cl=collections.defaultdict(list)
    for k in range(len(ids)): cl[f(k)].append(k)
    out=[]
    for v in cl.values():
        if len(v)<4: continue
        x0,y0=pts_[v,0].min(),pts_[v,1].min(); x1,y1=pts_[v,0].max(),pts_[v,1].max()
        out.append(dict(n=len(v),bbox_pt=[round(float(x0),1),round(float(y0),1),round(float(x1),1),round(float(y1),1)],
                        owners=collections.Counter(_own.get(C[ids[k]]) for k in v).most_common(3)))
    return sorted(out,key=lambda d:-d['n'])
R['unwalled_xv_clusters']=_xv_clusters()
R['unwalled_xv_strokes']=sum(d['n'] for d in R['unwalled_xv_clusters'])
# (29.09.2026) the same at ANY angle: a Revit pattern does not turn with a curved wall (floor 2: the round wall at axes
#   Д - Г/2, a fixed 37/127-degree cross) - thin strokes (< 0.45 pt, 0.5-8 pt, not along the sheet axes +-6 deg) outside the
#   walls that CROSS a perpendicular one (80-100 deg); clusters of 6+ linked within 4 pt. Furniture corners meet at their
#   ends and do not cross, so they are not counted.
def _xany_clusters():
    from shapely.strtree import STRtree as _T
    from shapely.prepared import prep as _prep
    from scipy.spatial import cKDTree as _K
    _own={}
    for q in inst:
        for i in q['prims']: _own[i]=q['key']
    WPT=pickle.load(open(walls_file(),'rb'))['Wpt']
    WU=_prep(unary_union([g for v in WPT.values() for g in v]).buffer(0.3))
    ang=lambda a,b: math.degrees(math.atan2(b[1]-a[1],b[0]-a[0]))%180
    C=[]
    for i,p in enumerate(P):
        if p[0]!='l' or (p[1] or 0)>=0.45: continue
        a,b=p[4]; L=math.dist(a,b); t=ang(a,b)
        if not (0.5<=L<=8) or min(t%90,90-t%90)<=6: continue
        col=p[2]
        if not (col and abs(col[0]-col[1])<0.02 and abs(col[1]-col[2])<0.02 and col[0]<=0.85): continue
        if WU.contains(Point((a[0]+b[0])/2,(a[1]+b[1])/2)): continue
        if _own.get(i) in ('chair','wc','sink','stool','desk','door','convector','tag','cafe','rdoor','column','plant'): continue
        C.append(i)
    if not C: return []
    Gc=[LineString(P[i][4]) for i in C]; tr=_T(Gc); xs=set()
    for k,i in enumerate(C):
        t=ang(*P[i][4])
        for j in tr.query(Gc[k]):
            if j==k: continue
            d_=abs(((t-ang(*P[C[j]][4]))+90)%180-90)
            if d_<80: continue
            if Gc[k].crosses(Gc[j]): xs.add(k); xs.add(j)
    ids=sorted(xs)
    if not ids: return []
    pts_=np.array([((P[C[k]][4][0][0]+P[C[k]][4][1][0])/2,(P[C[k]][4][0][1]+P[C[k]][4][1][1])/2) for k in ids])
    par=list(range(len(ids)))
    def f(x):
        while par[x]!=x: par[x]=par[par[x]]; x=par[x]
        return x
    for a_,b_ in _K(pts_).query_pairs(4.0): par[f(a_)]=f(b_)
    cl=collections.defaultdict(list)
    for k in range(len(ids)): cl[f(k)].append(k)
    out=[]
    for v in cl.values():
        if len(v)<6: continue
        x0,y0=pts_[v,0].min(),pts_[v,1].min(); x1,y1=pts_[v,0].max(),pts_[v,1].max()
        out.append(dict(n=len(v),bbox_pt=[round(float(x0),1),round(float(y0),1),round(float(x1),1),round(float(y1),1)],
                        owners=collections.Counter(_own.get(C[ids[k]]) for k in v).most_common(3)))
    return sorted(out,key=lambda d:-d['n'])
R['unwalled_xany_clusters']=_xany_clusters()
R['unwalled_xany_strokes']=sum(d['n'] for d in R['unwalled_xany_clusters'])
# capital-wall hatch outside walls: the grey hatch of existing walls (0.40-0.55, 45/135 +-2 deg, 0.5-14 pt) runs in one
#   direction only, so the X/V check does not see it (floor 1: a whole capital wall along the lifts was lines).
#   Clusters of 3+ strokes linked within 9 pt; the owners say what took them. Floor 6's 0.49 column casings are cfg.NOHATCH_COLORS.
def _cap_clusters():
    from scipy.spatial import cKDTree as _K
    from shapely.prepared import prep as _prep
    _own={}
    for q in inst:
        for i in q['prims']: _own[i]=q['key']
    WPT=pickle.load(open(walls_file(),'rb'))['Wpt']
    WU=_prep(unary_union([g for v in WPT.values() for g in v]).buffer(0.3))
    _nh=getattr(cfg,'NOHATCH_COLORS',[])
    C=[]
    for i,p in enumerate(P):
        if p[0]!='l' or cls[i] in ('axis','sheet','dim'): continue
        a,b=p[4]; L=math.dist(a,b); t=math.degrees(math.atan2(b[1]-a[1],b[0]-a[0]))%180
        if not (0.5<=L<=14) or min(abs(t-45),abs(t-135))>2: continue
        col=p[2]
        if not (col and abs(col[0]-col[1])<0.02 and abs(col[1]-col[2])<0.02 and 0.40<=col[0]<=0.55): continue
        if any(max(abs(col[j]-z[j]) for j in range(3))<=0.015 for z in _nh): continue
        if WU.contains(Point((a[0]+b[0])/2,(a[1]+b[1])/2)): continue
        C.append(i)
    if len(C)<4: return []
    pts_=np.array([((P[i][4][0][0]+P[i][4][1][0])/2,(P[i][4][0][1]+P[i][4][1][1])/2) for i in C])
    par=list(range(len(C)))
    def f(x):
        while par[x]!=x: par[x]=par[par[x]]; x=par[x]
        return x
    for a_,b_ in _K(pts_).query_pairs(9.0): par[f(a_)]=f(b_)      # the pitch of a thick wall's hatch is up to 8 pt
    cl=collections.defaultdict(list)
    for k in range(len(C)): cl[f(k)].append(k)
    out=[]
    for v in cl.values():
        if len(v)<3: continue
        out.append(dict(n=len(v),bbox_pt=[round(float(pts_[v,0].min()),1),round(float(pts_[v,1].min()),1),round(float(pts_[v,0].max()),1),round(float(pts_[v,1].max()),1)],
                        owners=collections.Counter(_own.get(C[k]) for k in v).most_common(3)))
    return sorted(out,key=lambda d:-d['n'])
R['unwalled_cap_hatch_clusters']=_cap_clusters()
R['unwalled_cap_hatch_strokes']=sum(d['n'] for d in R['unwalled_cap_hatch_clusters'])
print('unwalled cap hatch',R['unwalled_cap_hatch_strokes'],R['unwalled_cap_hatch_clusters'][:6])
json.dump(R,open('verify.json','w'),ensure_ascii=False,indent=1)
