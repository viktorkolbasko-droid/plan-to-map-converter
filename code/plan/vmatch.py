from common import *
from collections import defaultdict
P=load(); cls=pickle.load(open('cls.pkl','rb'))
Q=0.05
def seg(p):
    k,w,sc,fc,g,di=p
    if k=='l': return g[0],g[1]
    if k=='c': return g[0],g[3]
    return None
# (cfg.FAMILY_WALLCLS=True) candidates also among prims the raster wall mask called 'wall': a chair turned by 45 deg
#   has 45-deg edges that the raster mask takes for hatch (floor 5, room 14) - it could never be matched, and its
#   back then became a false wall
_FC=('obj','wall') if getattr(cfg,'FAMILY_WALLCLS',False) else ('obj',)
OBJ=[i for i,c in enumerate(cls) if c in _FC and P[i][0] in ('l','c')]
hashp=defaultdict(list)
for i in OBJ:
    a,b=seg(P[i])
    hashp[(round(a[0]/Q),round(a[1]/Q))].append(i); hashp[(round(b[0]/Q),round(b[1]/Q))].append(i)
bylen=defaultdict(list)
for i in OBJ:
    a,b=seg(P[i]); bylen[round(math.dist(a,b),1)].append(i)
DIH=[(1,0,0,1),(0,-1,1,0),(-1,0,0,-1),(0,1,-1,0),(-1,0,0,1),(0,1,1,0),(1,0,0,-1),(0,-1,-1,0)]
def ap(D,p): return (D[0]*p[0]+D[1]*p[1], D[2]*p[0]+D[3]*p[1])
def find_seg(a,b,tol=0.22):
    cand=set()
    for p in (a,):
        kx,ky=round(p[0]/Q),round(p[1]/Q)
        for dx in (-4,-3,-2,-1,0,1,2,3,4):
            for dy in (-4,-3,-2,-1,0,1,2,3,4): cand.update(hashp.get((kx+dx,ky+dy),[]))
    for i in cand:
        s=seg(P[i])
        if (math.dist(s[0],a)<tol and math.dist(s[1],b)<tol) or (math.dist(s[0],b)<tol and math.dist(s[1],a)<tol): return i
    return None
def template(bbox, extra_filter=None):
    x0,y0,x1,y1=bbox
    t=[i for i in OBJ if all(x0<=q[0]<=x1 and y0<=q[1]<=y1 for q in seg(P[i]))]
    if extra_filter: t=[i for i in t if extra_filter(P[i])]
    return t
def match(tidx, minfrac=0.9, used=None, anchor="rare", DEDUP=2.5):
    return match_segs([seg(P[i]) for i in tidx], minfrac, anchor, DEDUP)
def match_segs(segs, minfrac=0.9, anchor="rare", DEDUP=2.5):
    """segs: template segments ((x0,y0),(x1,y1)) in this floor's pt; instances may be rotated by 90 deg steps / mirrored"""
    lens=[math.dist(*s) for s in segs]
    # anchor: longest segment with rare length
    order=sorted(range(len(segs)),key=lambda j:(len(bylen[round(lens[j],1)]),-lens[j]))
    anc=[j for j in order if lens[j]>1.0][0] if anchor=='rare' else max(range(len(segs)),key=lambda j:lens[j])
    ta,tb=segs[anc]
    cx=sum((s[0][0]+s[1][0])/2 for s in segs)/len(segs); cy=sum((s[0][1]+s[1][1])/2 for s in segs)/len(segs)
    rel=[((s[0][0]-ta[0],s[0][1]-ta[1]),(s[1][0]-ta[0],s[1][1]-ta[1])) for s in segs]
    relc=(cx-ta[0],cy-ta[1])
    found=[]; seen=[]
    L=round(lens[anc],1)
    cands=[c for dl in (-0.3,-0.2,-0.1,0,0.1,0.2,0.3) for c in bylen.get(round(L+dl,1),[])]
    for ci in cands:
        a,b=seg(P[ci])
        for D in DIH:
            for (pa,pb) in ((a,b),(b,a)):
                d=ap(D,(tb[0]-ta[0],tb[1]-ta[1]))
                if math.dist((pa[0]+d[0],pa[1]+d[1]),pb)>0.25: continue
                hit=[]; miss=0
                for (r0,r1) in rel:
                    q0=ap(D,r0); q1=ap(D,r1)
                    k=find_seg((pa[0]+q0[0],pa[1]+q0[1]),(pa[0]+q1[0],pa[1]+q1[1]))
                    if k is None: miss+=1
                    else: hit.append(k)
                    if miss>(1-minfrac)*len(rel)+0.5: break
                if miss<=(1-minfrac)*len(rel):
                    c=ap(D,relc); c=(pa[0]+c[0],pa[1]+c[1])
                    if any(math.dist(c,s)<DEDUP for s in seen): continue
                    seen.append(c); found.append(dict(D=D,t=pa,c=c,prims=sorted(set(hit)),anchor=ta))
    return found

def match_segs_any(segs, minfrac=0.9, DEDUP=2.5, seen=None):
    """match_segs at ANY rotation angle (floor 4: armchairs turned 30-60 deg in the Ecom zone).
    The anchor (longest template segment) is mapped onto every source segment of its length; the rotation - and the
    mirror - follow from that pair. Poses within 0.5 deg of a multiple of 90 deg are left to match_segs (the D4 pass),
    and centres already found (`seen`) are skipped, so this pass only adds truly rotated instances."""
    # centre from the full template; the test uses only its structural segments (>= 1 pt): a turned instance's
    #   micro-strokes are re-quantised by the printer and do not match one by one (the absorption step in assign.py
    #   then takes the micro-strokes lying on the turned template)
    cx=sum((s[0][0]+s[1][0])/2 for s in segs)/len(segs); cy=sum((s[0][1]+s[1][1])/2 for s in segs)/len(segs)
    segs=[s for s in segs if math.dist(*s)>=1.0] or segs
    lens=[math.dist(*s) for s in segs]
    found=[]; seen=list(seen or [])
    # anchors: the 4 longest segments - in a turned instance the longest one may be split or hidden
    for anc in sorted(range(len(segs)),key=lambda j:-lens[j])[:4]:
        found+=_any_from(segs,lens,anc,cx,cy,minfrac,DEDUP,seen)
    return found
def _any_from(segs,lens,anc,cx,cy,minfrac,DEDUP,seen):
    ta,tb=segs[anc]
    rel=[((s[0][0]-ta[0],s[0][1]-ta[1]),(s[1][0]-ta[0],s[1][1]-ta[1])) for s in segs]
    relc=(cx-ta[0],cy-ta[1])
    tht=math.atan2(tb[1]-ta[1],tb[0]-ta[0])
    found=[]
    L=round(lens[anc],1)
    cands=[c for dl in (-0.3,-0.2,-0.1,0,0.1,0.2,0.3) for c in bylen.get(round(L+dl,1),[])]
    for ci in cands:
        a,b=seg(P[ci])
        for (pa,pb) in ((a,b),(b,a)):
            th=math.atan2(pb[1]-pa[1],pb[0]-pa[0])
            for mir in (1,-1):
                phi=th-tht if mir==1 else th+tht
                deg=math.degrees(phi)%90
                if min(deg,90-deg)<0.5: continue
                c_,s_=math.cos(phi),math.sin(phi)
                D=(c_,-s_*mir,s_,c_*mir)          # R(phi) @ diag(1,mir)
                hit=[]; miss=0
                for (r0,r1) in rel:
                    q0=ap(D,r0); q1=ap(D,r1)
                    k=find_seg((pa[0]+q0[0],pa[1]+q0[1]),(pa[0]+q1[0],pa[1]+q1[1]))
                    if k is None: miss+=1
                    else: hit.append(k)
                    if miss>(1-minfrac)*len(rel)+0.5: break
                if miss<=(1-minfrac)*len(rel):
                    c=ap(D,relc); c=(pa[0]+c[0],pa[1]+c[1])
                    if any(math.dist(c,s)<DEDUP for s in seen): continue
                    seen.append(c); found.append(dict(D=D,t=pa,c=c,prims=sorted(set(hit)),anchor=ta,anyangle=round(math.degrees(phi),1)))
    return found

# ---- family library: templates saved from one floor, matched on others (same Revit families, same print scale +-3 %)
import json, os
LIB=os.path.join(os.path.dirname(os.path.abspath(__file__)),'families_lib.json')
def save_lib(entries):
    """entries: [(key,name,layer,tidx,minfrac)] from this floor -> library (segments relative to the template centre, in mm)"""
    lib=json.load(open(LIB)) if os.path.exists(LIB) else {}
    for key,name,layer,tidx,mf in entries:
        sg=[seg(P[i]) for i in tidx]
        cx=sum((a[0]+b[0])/2 for a,b in sg)/len(sg); cy=sum((a[1]+b[1])/2 for a,b in sg)/len(sg)
        lib[key]=dict(name=name,layer=layer,minfrac=mf,segs_mm=[[(a[0]-cx)*MM_PER_PT,(a[1]-cy)*MM_PER_PT,(b[0]-cx)*MM_PER_PT,(b[1]-cy)*MM_PER_PT] for a,b in sg])
    json.dump(lib,open(LIB,'w'),ensure_ascii=False,indent=0)
def lib_segs(key):
    lib=json.load(open(LIB)); e=lib[key]
    return e,[((x0/MM_PER_PT,y0/MM_PER_PT),(x1/MM_PER_PT,y1/MM_PER_PT)) for x0,y0,x1,y1 in e['segs_mm']]
